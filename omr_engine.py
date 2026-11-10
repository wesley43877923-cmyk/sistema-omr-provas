"""
OMR Generator + Processor — Versão Corrigida para Imagens Torcidas e Múltiplos Formatos de Gabarito.
"""

import io
import cv2
import numpy as np
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


class OMRGenerator:
  """Gera cartões-resposta em PDF com marcadores de ancoragem e QR Code nativo."""

  @staticmethod
  def generate_pdf(
      df_alunos,
      num_questoes=30,
      num_alternativas=4,
      escola_padrao='Escola Exemplo',
      disciplina_padrao='Geral',
  ):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4  # 595.27 x 841.89 points

    letras = ['A', 'B', 'C', 'D', 'E'][:num_alternativas]

    for idx, row in df_alunos.iterrows():
      matricula = str(row.get('matricula', f'ID_{idx+1}'))
      nome = str(row.get('nome', f'Aluno {idx+1}'))
      turma = str(row.get('turma', 'Turma A'))
      escola = str(row.get('escola', escola_padrao))
      disciplina = str(row.get('disciplina', disciplina_padrao))

      # MARCADORES DE ANCORAGEM (4 cantos)
      marker_size = 20
      margin = 30
      c.setFillColor(colors.black)
      c.rect(
          margin,
          height - margin - marker_size,
          marker_size,
          marker_size,
          fill=1,
          stroke=0,
      )
      c.rect(
          width - margin - marker_size,
          height - margin - marker_size,
          marker_size,
          marker_size,
          fill=1,
          stroke=0,
      )
      c.rect(margin, margin, marker_size, marker_size, fill=1, stroke=0)
      c.rect(
          width - margin - marker_size,
          margin,
          marker_size,
          marker_size,
          fill=1,
          stroke=0,
      )

      # QR CODE
      qr_data = f'ID:{matricula}|NOME:{nome}|TURMA:{turma}|Q:{num_questoes}|ALT:{num_alternativas}'
      qr_widget = QrCodeWidget(qr_data)
      qr_widget.barWidth = 70
      qr_widget.barHeight = 70

      qr_drawing = Drawing(70, 70)
      qr_drawing.add(qr_widget)

      qr_x = width - margin - marker_size - 80
      qr_y = height - margin - marker_size - 75
      qr_drawing.drawOn(c, qr_x, qr_y)

      # CABEÇALHO
      c.setFont('Helvetica-Bold', 14)
      c.drawString(
          margin + marker_size + 15, height - margin - 15, escola.upper()
      )

      c.setFont('Helvetica-Bold', 10)
      c.drawString(
          margin + marker_size + 15,
          height - margin - 35,
          f'DISCIPLINA: {disciplina.upper()}',
      )
      c.drawString(
          margin + marker_size + 15, height - margin - 50, f'TURMA: {turma}'
      )

      c.setFont('Helvetica', 10)
      c.drawString(
          margin + marker_size + 15, height - margin - 68, f'ALUNO(A): {nome}'
      )
      c.drawString(
          margin + marker_size + 15,
          height - margin - 83,
          f'MATRÍCULA: {matricula}',
      )

      c.setLineWidth(1)
      c.setStrokeColor(colors.black)
      c.line(margin + 10, height - 135, width - margin - 10, height - 135)

      # GRADE DE RESPOSTAS
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

      c.setFont('Helvetica-Bold', 9)

      for q_idx in range(1, num_questoes + 1):
        col = (q_idx - 1) // q_per_col
        row_in_col = (q_idx - 1) % q_per_col

        x_base = margin + col * col_width + 20
        y_pos = start_y - (row_in_col * row_height)

        c.drawString(x_base, y_pos - 3, f'{q_idx:02d}.')

        for opt_idx, letra in enumerate(letras):
          circle_x = x_base + 35 + (opt_idx * 26)
          c.circle(circle_x, y_pos, radius, fill=0, stroke=1)
          c.setFont('Helvetica', 8)
          c.drawString(circle_x - 3, y_pos - 3, letra)
          c.setFont('Helvetica-Bold', 9)

      c.setFont('Helvetica-Oblique', 8)
      c.drawString(
          margin + 30,
          margin + 15,
          'Instruções: Preencha totalmente o círculo da alternativa escolhida'
          ' com caneta preta ou azul escuro.',
      )

      c.showPage()

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


class OMRProcessor:
  """Processador OMR robusto com alinhamento por perspectiva e suporte flexível a gabaritos."""

  @staticmethod
  def process_card(image_bytes, gabarito):
    np_arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if img is None:
      return {'status': 'Erro: Imagem inválida'}

    # 1. Leitura do QR Code
    meta = OMRProcessor.read_qrcode(img)

    num_questoes = int(meta.get('Q', len(gabarito) if gabarito else 30))
    num_alternativas = int(meta.get('ALT', 4))

    # 2. Retificação por Perspectiva Homográfica
    warped = OMRProcessor.rectify_image(img)

    # 3. Leitura da Grade de Respostas
    respostas_aluno = OMRProcessor.read_bubbles(
        warped, num_questoes, num_alternativas
    )

    # 4. Normalização do Gabarito (Aceita dict, list, tuple ou str)
    dict_gabarito = {}
    if isinstance(gabarito, dict):
      dict_gabarito = {int(k): v for k, v in gabarito.items()}
    elif isinstance(gabarito, (list, tuple, str)):
      dict_gabarito = {i + 1: val for i, val in enumerate(gabarito)}

    # 5. Comparação e Apuração
    acertos = 0
    erros = []
    total_q = len(dict_gabarito) if dict_gabarito else num_questoes

    for q in range(1, total_q + 1):
      resp_correta = dict_gabarito.get(q)
      resp_aluno = respostas_aluno.get(q, 'EM_BRANCO')

      if resp_correta and resp_aluno == resp_correta:
        acertos += 1
      elif resp_correta:
        erros.append(f'Q{q:02d}({resp_aluno})')

    nota = round((acertos / total_q) * 10, 2) if total_q > 0 else 0

    return {
        'status': 'Sucesso',
        'matricula': meta.get('ID', 'N/A'),
        'nome': meta.get('NOME', 'Desconhecido'),
        'turma': meta.get('TURMA', 'N/A'),
        'acertos': acertos,
        'total_questoes': total_q,
        'nota': nota,
        'questoes_erradas': ', '.join(erros),
        'respostas_detectadas': respostas_aluno,
    }

  @staticmethod
  def read_qrcode(img):
    qr_detector = cv2.QRCodeDetector()
    tentativas = [img]

    if len(img.shape) == 3:
      gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
      tentativas.append(gray)
      tentativas.append(cv2.equalizeHist(gray))
      _, bin_img = cv2.threshold(
          gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
      )
      tentativas.append(bin_img)
      tentativas.append(
          cv2.resize(
              gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC
          )
      )

    data = None
    for t in tentativas:
      try:
        d, _, _ = qr_detector.detectAndDecode(t)
        if d:
          data = d
          break
      except Exception:
        continue

    meta = {}
    if data:
      for p in data.split('|'):
        if ':' in p:
          k, v = p.split(':', 1)
          meta[k] = v
    return meta

  @staticmethod
  def find_4_corner_markers(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    h, w = gray.shape
    page_area = h * w

    corners = OMRProcessor._find_markers_by_zone(gray, h, w, page_area)
    if corners is not None and OMRProcessor._validate_corners(corners, h, w):
      return corners

    corners = OMRProcessor._find_sheet_contour(gray, h, w, page_area)
    if corners is not None and OMRProcessor._validate_corners(corners, h, w):
      return corners

    return None

  @staticmethod
  def _validate_corners(corners, h, w):
    if corners is None:
      return False
    tl, tr, bl, br = corners

    if not (tl[0] < w * 0.45 and tl[1] < h * 0.45):
      return False
    if not (tr[0] > w * 0.55 and tr[1] < h * 0.45):
      return False
    if not (bl[0] < w * 0.45 and bl[1] > h * 0.55):
      return False
    if not (br[0] > w * 0.55 and br[1] > h * 0.55):
      return False

    xs = [p[0] for p in corners]
    ys = [p[1] for p in corners]
    bbox_area = (max(xs) - min(xs)) * (max(ys) - min(ys))
    return bbox_area >= (h * w) * 0.20

  @staticmethod
  def _find_markers_by_zone(gray, h, w, page_area):
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, thresh_otsu = cv2.threshold(
        blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    _, thresh_fixed = cv2.threshold(blur, 127, 255, cv2.THRESH_BINARY_INV)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))

    for thresh in [thresh_otsu, thresh_fixed]:
      thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
      contours, _ = cv2.findContours(
          thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
      )

      area_min = page_area * 0.0001
      area_max = page_area * 0.05
      blobs = []
      for c in contours:
        area = cv2.contourArea(c)
        if area_min < area < area_max:
          M = cv2.moments(c)
          if M['m00'] != 0:
            cx = M['m10'] / M['m00']
            cy = M['m01'] / M['m00']
            blobs.append((cx, cy, area))

      if len(blobs) >= 4:
        result = OMRProcessor._pick_corner_blobs(blobs, h, w)
        if result is not None:
          return result

    return None

  @staticmethod
  def _pick_corner_blobs(blobs, h, w):
    zx = w * 0.35
    zy = h * 0.35

    cantos_alvo = {'TL': (0, 0), 'TR': (w, 0), 'BL': (0, h), 'BR': (w, h)}
    zone_bounds = {
        'TL': (0, zx, 0, zy),
        'TR': (w - zx, w, 0, zy),
        'BL': (0, zx, h - zy, h),
        'BR': (w - zx, w, h - zy, h),
    }

    corners = {}
    for nome, (x0, x1, y0, y1) in zone_bounds.items():
      alvo_x, alvo_y = cantos_alvo[nome]
      candidatos = [
          (b[0], b[1], b[2])
          for b in blobs
          if x0 <= b[0] < x1 and y0 <= b[1] < y1
      ]

      if not candidatos:
        rzx, rzy = w * 0.50, h * 0.50
        if nome == 'TL':
          candidatos = [
              (b[0], b[1], b[2]) for b in blobs if b[0] < rzx and b[1] < rzy
          ]
        elif nome == 'TR':
          candidatos = [
              (b[0], b[1], b[2])
              for b in blobs
              if b[0] >= w - rzx and b[1] < rzy
          ]
        elif nome == 'BL':
          candidatos = [
              (b[0], b[1], b[2])
              for b in blobs
              if b[0] < rzx and b[1] >= h - rzy
          ]
        else:
          candidatos = [
              (b[0], b[1], b[2])
              for b in blobs
              if b[0] >= w - rzx and b[1] >= h - rzy
          ]

      if not candidatos:
        return None

      best = min(
          candidatos, key=lambda b: (b[0] - alvo_x) ** 2 + (b[1] - alvo_y) ** 2
      )
      corners[nome] = (best[0], best[1])

    return np.float32(
        [corners['TL'], corners['TR'], corners['BL'], corners['BR']]
    )

  @staticmethod
  def _find_sheet_contour(gray, h, w, page_area):
    _, thresh = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    thresh = cv2.erode(thresh, kernel, iterations=1)

    contours, _ = cv2.findContours(
        thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if not contours:
      return None

    sheet = max(contours, key=cv2.contourArea)
    if cv2.contourArea(sheet) < page_area * 0.3:
      return None

    peri = cv2.arcLength(sheet, True)
    approx = cv2.approxPolyDP(sheet, peri * 0.02, True)

    if len(approx) >= 4:
      pts = approx.reshape(-1, 2)
      s = pts.sum(axis=1)
      diff = np.diff(pts, axis=1).flatten()
      return np.float32([
          pts[np.argmin(s)],
          pts[np.argmin(diff)],
          pts[np.argmax(diff)],
          pts[np.argmax(s)],
      ])

    return None

  @staticmethod
  def rectify_image(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    corners = OMRProcessor.find_4_corner_markers(img)

    if corners is not None:
      scale_x = 1000.0 / 595.27
      scale_y = 1414.0 / 841.89

      cx_left = 40.0 * scale_x
      cx_right = (595.27 - 40.0) * scale_x
      cy_top = 40.0 * scale_y
      cy_bottom = (841.89 - 40.0) * scale_y

      dst_pts = np.float32([
          [cx_left, cy_top],
          [cx_right, cy_top],
          [cx_left, cy_bottom],
          [cx_right, cy_bottom],
      ])

      matrix = cv2.getPerspectiveTransform(corners, dst_pts)
      return cv2.warpPerspective(gray, matrix, (1000, 1414))

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

    blur = cv2.GaussianBlur(gray_img, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 21, 7
    )

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

        # Janela de busca com tolerância espacial leve
        best_count = 0
        for dy in [-2, 0, 2]:
          for dx in [-2, 0, 2]:
            roi = thresh[
                max(0, cy + dy - 14) : min(1414, cy + dy + 14),
                max(0, cx + dx - 14) : min(1000, cx + dx + 14),
            ]
            cnt = cv2.countNonZero(roi)
            if cnt > best_count:
              best_count = cnt

        counts.append(best_count)

      max_idx = int(np.argmax(counts))
      max_val = counts[max_idx]
      other_avg = (sum(counts) - max_val) / max(1, (len(counts) - 1))

      if max_val > 140 and (max_val - other_avg) > 40:
        respostas[q_idx] = letras[max_idx]
      else:
        respostas[q_idx] = 'EM_BRANCO'

    return respostas
