from docx import Document
import tempfile
from io import BytesIO

import streamlit as st
import os
import tempfile
import shutil
from pathlib import Path
import subprocess

st.set_page_config(page_title="Gerador de Cartas ANS", layout="centered")
st.title("📄 Geração de Carta-Resposta à ANS")
st.write("Faça upload dos arquivos da NIP (PDF ou DOCX). O sistema irá processar e gerar a carta automaticamente com base nos dados extraídos.")

uploaded_files = st.file_uploader(
    "Envie os arquivos (PDF, DOC, DOCX)",
    type=["pdf", "doc", "docx"],
    accept_multiple_files=True
)
if uploaded_files:
    st.info("🔄 Processando documentos...")
    
    # Cria pasta temporária para simular ~/Downloads/documentos_ans
    temp_dir = tempfile.mkdtemp()
    documentos_ans_path = os.path.join(temp_dir, "documentos_ans")
    os.makedirs(documentos_ans_path, exist_ok=True)

    # Salva os arquivos enviados na pasta temporária
    for file in uploaded_files:
        file_path = os.path.join(documentos_ans_path, file.name)
        with open(file_path, "wb") as f:
            f.write(file.read())

    # Cria .env temporário se necessário
    env_path = os.path.join(temp_dir, ".env")
    if not os.path.exists(env_path):
        with open(env_path, "w") as f:
            f.write("OPENAI_API_KEY=your_openai_key\n")
            f.write("PINECONE_API_KEY=your_pinecone_key\n")
            f.write("PINECONE_ENVIRONMENT=your_pinecone_env\n")
            f.write("PINECONE_INDEX_NAME=flowiseans2\n")

    # Copia o script original para o diretório temporário

    # Substitui o caminho ~/Downloads/documentos_ans pelo caminho temporário
    script_code = script_code.replace('os.path.expanduser("~/Downloads/documentos_ans")', f'"{documentos_ans_path}"')
    script_code = script_code.replace('dotenv_path=os.path.expanduser("~/Downloads/.env")', f'dotenv_path="{env_path}"')

    st.success("✅ Carta gerada com sucesso!")
    st.subheader("📝 Resultado:")
    st.code(result.stdout, language="markdown")

    if "===== CARTA FINAL COM CAMPOS PREENCHIDOS =====" in result.stdout:
        carta_texto = result.stdout.split("===== CARTA FINAL COM CAMPOS PREENCHIDOS =====")[-1].strip()

        # Cria documento Word
        doc = Document()
        for par in carta_texto.split("\n"):
            doc.add_paragraph(par)

        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)

        st.download_button(
            label="📥 Baixar Carta em formato Word (.docx)",
            data=buffer,
            file_name="carta_resposta_ans.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )


    # Limpeza
    shutil.rmtree(temp_dir)
