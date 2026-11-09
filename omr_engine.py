import cv2
import numpy as np
import pandas as pd
import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.barcode.qr import QrCodeWidget

class OMRGenerator:
    """Gera cartões-resposta em PDF com marcadores de ancoragem e QR Code nativo."""
    
    @staticmethod
    def generate_pdf(df_alunos, num_questoes=30, num_alternativas=4, escola_padrao="Escola Exemplo", disciplina_padrao="Geral"):
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4 # 595.27 x 841.89 points
        
        letras = ['A', 'B', 'C', 'D', 'E'][:num_alternativas]
        
        for idx, row in df_alunos.iterrows():
            matricula = str(row.get('matricula', f'ID_{idx+1}'))
            nome = str(row.get('nome', f'Aluno {idx+1}'))
            turma = str(row.get('turma', 'Turma A'))
            escola = str(row.get('escola', escola_padrao))
            disciplina = str(row.get('disciplina', disciplina_padrao))
            
            # --- MARCADORES DE ANCORAGEM (4 cantos) ---
            marker_size = 20
            margin = 30
            c.setFillColor(colors.black)
            c.rect(margin, height - margin - marker_size, marker_size, marker_size, fill=1, stroke=0)
            c.rect(width - margin - marker_size, height - margin - marker_size, marker_size, marker_size, fill=1, stroke=0)
            c.rect(margin, margin, marker_size, marker_size, fill=1, stroke=0)
            c.rect(width - margin - marker_size, margin, marker_size, marker_size, fill=1, stroke=0)
            
            # --- QR CODE NATIVO ---
            qr_data = f"ID:{matricula}|NOME:{nome}|TURMA:{turma}|Q:{num_questoes}|ALT:{num_alternativas}"
            qr_widget = QrCodeWidget(qr_data)
            qr_widget.barWidth = 70
            qr_widget.barHeight = 70
            
            qr_drawing = Drawing(70, 70)
            qr_drawing.add(qr_widget)
            
            qr_x = width - margin - marker_size - 80
            qr_y = height - margin - marker_size - 75
            qr_drawing.drawOn(c, qr_x, qr_y)
            
            # --- CABEÇALHO ---
            c.setFont("Helvetica-Bold", 14)
            c.drawString(margin + marker_size + 15, height - margin - 15, escola.upper())
            
            c.setFont("Helvetica-Bold", 10)
            c.drawString(margin + marker_size + 15, height - margin - 35, f"DISCIPLINA: {disciplina.upper()}")
            c.drawString(margin + marker_size + 15, height - margin - 50, f"TURMA: {turma}")
            
            c.setFont("Helvetica", 10)
            c.drawString(margin + marker_size + 15, height - margin - 68, f"ALUNO(A): {nome}")
            c.drawString(margin + marker_size + 15, height - margin - 83, f"MATRÍCULA: {matricula}")
            
            c.setLineWidth(1)
            c.setStrokeColor(colors.black)
            c.line(margin + 10, height - 135, width - margin - 10, height - 135)
            
            # --- GRADE DE RESPOSTAS ---
            if num_questoes <= 15:
                num_cols = 1
            elif num_questoes <= 30:
                num_cols = 2
            else:
                num_cols = 3
                
            q_per_col = (num_questoes + num_cols - 1) // num_cols
            col_width = (width - 2 * margin) / num_cols
            
            start_y = height - 165
            row_height = 28
            radius = 7
            
            c.setFont("Helvetica-Bold", 9)
            
            for q_idx in range(1, num_questoes + 1):
                col = (q_idx - 1) // q_per_col
                row_in_col = (q_idx - 1) % q_per_col
                
                x_base = margin + col * col_width + 20
                y_pos = start_y - (row_in_col * row_height)
                
                c.drawString(x_base, y_pos - 3, f"{q_idx:02d}.")
                
                for opt_idx, letra in enumerate(letras):
                    circle_x = x_base + 35 + (opt_idx * 26)
                    c.circle(circle_x, y_pos, radius, fill=0, stroke=1)
                    c.setFont("Helvetica", 8)
                    c.drawString(circle_x - 3, y_pos - 3, letra)
                    c.setFont("Helvetica-Bold", 9)
            
            c.setFont("Helvetica-Oblique", 8)
            c.drawString(margin + 30, margin + 15, "Instruções: Preencha totalmente o círculo da alternativa escolhida com caneta preta ou azul escuro.")
            
            c.showPage()
            
        c.save()
        buffer.seek(0)
        return buffer.getvalue()


class OMRProcessor:
    """Processador OMR com alinhamento de perspectiva automático pelos 4 marcadores de canto."""
    
    @staticmethod
    def process_card(image_bytes, gabarito):
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        if img is None:
            return {"status": "Erro: Imagem inválida"}
            
        # 1. Tenta decodificar QR Code
        meta = OMRProcessor.read_qrcode(img)
        
        num_questoes = int(meta.get('Q', len(gabarito) if gabarito else 30))
        num_alternativas = int(meta.get('ALT', 4))
        
        # 2. Correção de perspectiva alinhada aos marcadores
        warped = OMRProcessor.rectify_image(img)
        
        # 3. Leitura das bolinhas
        respostas_aluno = OMRProcessor.read_bubbles(warped, num_questoes, num_alternativas)
        
        acertos = 0
        erros = []
        
        for q in range(1, num_questoes + 1):
            resp_correta = gabarito.get(q) or gabarito.get(str(q))
            resp_aluno = respostas_aluno.get(q, 'EM_BRANCO')
            
            if resp_correta and resp_aluno == resp_correta:
                acertos += 1
            elif resp_correta:
                erros.append(f"Q{q:02d}({resp_aluno})")
                
        total_q = len(gabarito) if gabarito else num_questoes
        nota = round((acertos / total_q) * 10, 2) if total_q > 0 else 0
        
        return {
            "status": "Sucesso",
            "matricula": meta.get('ID', 'N/A'),
            "nome": meta.get('NOME', 'Desconhecido'),
            "turma": meta.get('TURMA', 'N/A'),
            "acertos": acertos,
            "total_questoes": total_q,
            "nota": nota,
            "questoes_erradas": ", ".join(erros)
        }

    @staticmethod
    def read_qrcode(img):
        qr_detector = cv2.QRCodeDetector()
        data, bbox, _ = qr_detector.detectAndDecode(img)
        
        # Se falhar, tenta aplicar contraste/nitidez na imagem para tentar ler o QR Code
        if not data:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            enhanced = cv2.equalizeHist(gray)
            data, _, _ = qr_detector.detectAndDecode(enhanced)
            
        meta = {}
        if data:
            parts = data.split('|')
            for p in parts:
                if ':' in p:
                    k, v = p.split(':', 1)
                    meta[k] = v
        return meta

    @staticmethod
    def rectify_image(img):
        """Localiza os 4 marcadores quadrados nos cantos e aplica transformação de perspectiva."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        
        # Binarização para encontrar marcadores pretos
        _, thresh = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        img_h, img_w = gray.shape
        centers = []
        
        for c in contours:
            area = cv2.contourArea(c)
            # Marcadores de canto têm tamanho razoável proporcional à página
            if (img_w * img_h * 0.0001) < area < (img_w * img_h * 0.03):
                x, y, w, h = cv2.boundingRect(c)
                aspect_ratio = float(w) / h
                if 0.7 <= aspect_ratio <= 1.3:
                    M = cv2.moments(c)
                    if M["m00"] != 0:
                        centers.append((int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])))
                        
        # Se encontrar os 4 cantos, aplica transformação de perspectiva
        if len(centers) >= 4:
            centers = sorted(centers, key=lambda p: p[1]) # ordena por Y
            top_pts = sorted(centers[:2], key=lambda p: p[0]) # 2 superiores (TL, TR)
            bot_pts = sorted(centers[-2:], key=lambda p: p[0]) # 2 inferiores (BL, BR)
            
            pts1 = np.float32([top_pts[0], top_pts[1], bot_pts[0], bot_pts[1]])
            
            # Posições de referência padrão do PDF A4 em pixels (1000 x 1414)
            margin_x = int(30 * (1000.0 / 595.27)) + 15
            margin_y_top = int(30 * (1414.0 / 841.89)) + 15
            margin_y_bot = 1414 - margin_y_top
            
            pts2 = np.float32([
                [margin_x, margin_y_top],
                [1000 - margin_x, margin_y_top],
                [margin_x, margin_y_bot],
                [1000 - margin_x, margin_y_bot]
            ])
            
            matrix = cv2.getPerspectiveTransform(pts1, pts2)
            warped = cv2.warpPerspective(gray, matrix, (1000, 1414))
            return warped
            
        # Fallback se não encontrar marcadores: apenas redimensiona
        return cv2.resize(gray, (1000, 1414))

    @staticmethod
    def read_bubbles(gray_img, num_questoes, num_alternativas):
        letras = ['A', 'B', 'C', 'D', 'E'][:num_alternativas]
        
        scale_x = 1000.0 / 595.27
        scale_y = 1414.0 / 841.89
        
        if num_questoes <= 15:
            num_cols = 1
        elif num_questoes <= 30:
            num_cols = 2
        else:
            num_cols = 3
            
        q_per_col = (num_questoes + num_cols - 1) // num_cols
        col_width_pdf = (595.27 - 60) / num_cols
        
        # Limiarização adaptativa otimizada para caneta preta e azul
        blur = cv2.GaussianBlur(gray_img, (5, 5), 0)
        thresh = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                        cv2.THRESH_BINARY_INV, 21, 7)
        respostas = {}
        
        for q_idx in range(1, num_questoes + 1):
            col = (q_idx - 1) // q_per_col
            row_in_col = (q_idx - 1) % q_per_col
            
            y_pdf_top = 165 + row_in_col * 28
            x_base_pdf = 30 + col * col_width_pdf + 20
            
            cy = int(y_pdf_top * scale_y)
            counts = []
            
            for opt_idx in range(num_alternativas):
                cx = int((x_base_pdf + 35 + opt_idx * 26) * scale_x)
                roi = thresh[max(0, cy-14):min(1414, cy+14), max(0, cx-14):min(1000, cx+14)]
                counts.append(cv2.countNonZero(roi))
                
            max_idx = np.argmax(counts)
            max_val = counts[max_idx]
            other_avg = (sum(counts) - max_val) / max(1, (len(counts) - 1))
            
            # Limiar ajustado para aceitar preenchimento com caneta azul ou preta
            if max_val > 140 and (max_val - other_avg) > 40:
                respostas[q_idx] = letras[max_idx]
            else:
                respostas[q_idx] = "EM_BRANCO"
                
        return respostas
