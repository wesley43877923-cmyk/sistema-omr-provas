# 📝 Sistema OMR - Leitor e Corretor Automatizado de Cartões-Resposta

Aplicação web desenvolvida em Python (Streamlit + OpenCV + ReportLab) para automação completa de avaliações escolares.

## 🚀 Como Executar o Projeto

### 1. Requisitos Prévios
Certifique-se de ter o Python 3.9 ou superior instalado em sua máquina.

### 2. Instalação das Dependências
Abra o terminal na pasta do projeto e execute:

```bash
pip install -r requirements.txt
```

### 3. Executando a Aplicação Web
Rode o comando do Streamlit no terminal:

```bash
streamlit run app.py
```

A aplicação será aberta automaticamente no seu navegador padrão no endereço `http://localhost:8501`.

---

## 🛠️ Funcionalidades

1. **Aba 1 - Gerador de Cartões-Resposta (PDF)**:
   - Faz leitura de turmas via arquivo Excel ou CSV (`matricula`, `nome`, `turma`, `escola`, `disciplina`).
   - Ajusta dinamicamente a quantidade de questões (1 a 45) e o número de alternativas (A a E).
   - Desenha 4 marcadores de ancoragem nos cantos do papel A4 para correção de perspectiva via OpenCV.
   - Insere QR Code nativo no topo com metadados codificados (`ID`, `PROVA`, `QTDE_QUESTOES`).

2. **Aba 2 - Leitor OMR e Corretor Automatizado**:
   - Cadastro fácil do gabarito oficial na tela.
   - Upload em lote das imagens/fotos digitalizadas dos cartões dos alunos.
   - Identificação do aluno por QR Code e cálculo de acertos/nota.
   - Download do relatório consolidado final em planilha `.xlsx`.
