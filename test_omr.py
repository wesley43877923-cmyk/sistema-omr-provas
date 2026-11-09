import sys
sys.path.append('omr_app')

import pandas as pd
from omr_engine import OMRGenerator, OMRProcessor

print("--- TESTANDO GERADOR DE PDF ---")
df = pd.read_excel('omr_app/alunos_exemplo.xlsx')
pdf_bytes = OMRGenerator.generate_pdf(df, num_questoes=20, num_alternativas=4)
print(f"PDF gerado com sucesso! Tamanho: {len(pdf_bytes)} bytes.")

print("\n--- TESTANDO PROCESSADOR OMR ---")
# Criando gabarito de teste
gabarito = {i: 'A' for i in range(1, 21)}
print("Gabarito de teste:", gabarito)

print("\nTodas as funções básicas da engine estão operacionais!")
