
import os
from openai import OpenAI
from pinecone import Pinecone
from PyPDF2 import PdfReader
from dotenv import load_dotenv
import sys

# Carrega .env
dotenv_path = sys.argv[2] if len(sys.argv) > 2 else ".env"
load_dotenv(dotenv_path=dotenv_path)

# Carrega variáveis do .env
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")


# Debug
print("✅ .env carregado de:", dotenv_path)
print("🔑 PINECONE_API_KEY lido:", PINECONE_API_KEY[:8] + "...")
print("📍 PINECONE_HOST:", PINECONE_HOST)

# Debug (depois de carregar tudo!)
print("✅ .env carregado de:", dotenv_path)
print("🔑 PINECONE_API_KEY lido:", PINECONE_API_KEY[:8] + "...")
print("📍 PINECONE_HOST:", PINECONE_HOST)

# Verifica se está tudo certo
if not all([OPENAI_API_KEY, PINECONE_API_KEY, PINECONE_ENVIRONMENT, PINECONE_INDEX_NAME, PINECONE_HOST]):
    raise ValueError("⚠️ Erro: Uma ou mais variáveis de ambiente não foram carregadas corretamente do .env.")

# Inicializa clientes
client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY, environment=PINECONE_ENVIRONMENT)
index = pc.Index(PINECONE_INDEX_NAME)

from PyPDF2 import PdfReader
from PIL import Image
import pytesseract
import io

def extrair_texto_pdf(caminho):
    texto = ""
    reader = PdfReader(caminho)
    for i, page in enumerate(reader.pages):
        try:
            texto_pagina = page.extract_text()
            if texto_pagina:
                texto += texto_pagina
            else:
                # OCR caso não tenha texto
                xObject = page['/Resources']['/XObject'].get_object()
                for obj in xObject:
                    if xObject[obj]['/Subtype'] == '/Image':
                        data = xObject[obj]._data
                        image = Image.open(io.BytesIO(data))
                        texto += pytesseract.image_to_string(image)
        except Exception as e:
            print(f"Erro ao processar página {i+1} com OCR: {e}")
    texto_limpo = texto.strip()
    if len(texto_limpo) > 8000:
        print(f"⚠️ Documento {os.path.basename(caminho)} muito longo ({len(texto_limpo)} caracteres). Usando os primeiros 2000 caracteres.")
        return texto_limpo[:2000]
    return texto_limpo

def extrair_dados_chave(texto):
    prompt = f"""Você é um advogado especialista em regulação da ANS. Extraia do texto os seguintes itens de forma estruturada:
- Número da NIP
- Protocolo
- Número da demanda
- Nome da parte reclamante
- Nome da operadora
- Argumento da reclamante
- Decisão da operadora
- Justificativa da decisão da operadora

Texto:
{texto}
"""

    resposta = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Você é um especialista jurídico em regulação da ANS."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    return resposta.choices[0].message.content.strip()

# Caminho da pasta
import sys
pasta = sys.argv[1]
arquivos = sorted(list(set([f for f in os.listdir(pasta) if f.endswith(".pdf")])))


def gerar_resumo_dos_documentos(dados_lista):
    prompt = f"""Você é um advogado regulatório da ANS. Resuma as informações abaixo em um parágrafo técnico claro, que represente o contexto da reclamação e a justificativa da operadora. Seja objetivo e inclua os principais pontos jurídicos e de cobertura.

Dados:
{dados_lista}
"""
    resposta = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Você é um especialista em regulação da ANS."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    return resposta.choices[0].message.content.strip()


def buscar_normativas_vigentes(query_text):
    embedding = client.embeddings.create(
        input=[query_text],
        model="text-embedding-3-large"
    ).data[0].embedding

    resposta = index.query(
        vector=embedding,
        top_k=5,
        include_metadata=True,
        filter={"vigente": "sim"}
    )

    normativas = []
    for match in resposta.matches:
        texto = match.metadata.get("texto", "")
        if texto:
            normativas.append(texto.strip())
    return "\n\n".join(normativas)

import re

def identificar_normas_genericas(resumo, normativas_texto):
    """
    Dado um resumo e um conjunto de textos de normativas da ANS,
    retorna uma lista das normas mais relevantes com base em similaridade textual.
    """
    normas_relevantes = {}
    padrao_rn = re.compile(r'RN ?\d{3}/\d{4}')

    for normativa in normativas_texto:
        nome_rn = None
        match = padrao_rn.search(normativa)
        if match:
            nome_rn = match.group(0)

        if nome_rn:
            intersecao = set(resumo.lower().split()) & set(normativa.lower().split())
            if len(intersecao) > 3:
                normas_relevantes[nome_rn] = normativa

    return list(normas_relevantes.keys()), list(normas_relevantes.values())

def gerar_carta_resposta(resumo_dos_documentos, normativas_relevantes):

    prompt = f"""Você é um advogado redigindo uma resposta formal à ANS em nome da operadora. A carta deve seguir o formato jurídico abaixo, com linguagem técnica e respeitosa, e conter as seções nominais em caixa alta. Sempre respeite a decisão da reclamada. Use obrigatoriamente todos os campos extraídos abaixo. Se algum estiver ausente, não mencione. Cite, sempre que possível, o artigo correspondente.

**ESTRUTURA DA CARTA**:
- Data no topo à direita (formato: "São Paulo, 27 de março de 2025.")
- Endereçamento formal à ANS no topo: "AGÊNCIA NACIONAL DE SAÚDE SUPLEMENTAR - ANS
Avenida Augusto Severo, nº 84, 11º andar - Glória
CEP 20021-040 - Rio de Janeiro/RJ"
- Título: "ASSUNTO: RESPOSTA À NOTIFICAÇÃO DE INTERMEDIAÇÃO PRELIMINAR – NIP Nº [número da NIP] – PROTOCOLO Nº [protocolo] – DEMANDA Nº [número da demanda]"
- Primeiro parágrafo: "A ASSOCIAÇÃO DE SAÚDE DO VALE - LEVMED, pessoa jurídica de direito privado, inscrita no CNPJ sob nº 35.657.268/0001-85, registro ANS nº 422321, com sede à Rua Epitácio Pessoa, nº 651, bairro Centro, na cidade de Jaraguá do Sul/SC, vem informar o que segue."
- Corpo dividido em três seções com títulos em caixa alta:

**I – DA NOTIFICAÇÃO DE INTERMEDIAÇÃO PRELIMINAR**  
Descreva brevemente a solicitação da beneficiária, os itens solicitados, argumentos da reclamante e posicionamento inicial da operadora.

**II – DA COBERTURA ASSISTENCIAL**  
Explique tecnicamente e juridicamente a negativa, com base nas resoluções mais recentes da ANS (exemplo RN nº 558/2022 ou 465/2021), citando argumentos objetivos, evitando termos vagos.

**III – DO PEDIDO**  
Finalização pedindo arquivamento da NIP e reafirmando a conformidade da operadora com as normas regulatórias da ANS.

- Assinatura final genérica:  
"ASSOCIAÇÃO DE SAÚDE DO VALE – LEVMED"

Normativas vigentes da ANS para referência:
{normativas_relevantes}

Informações extraídas:
{resumo_dos_documentos}
"""
    resposta = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Você é um advogado especialista em regulação da ANS."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    return resposta.choices[0].message.content.strip()


# Atualizamos o loop para gerar a carta após extrair os dados

for nome in sorted(arquivos):
    caminho = os.path.join(pasta, nome)
    print(f"📄 Processando: {nome}")
    texto = extrair_texto_pdf(caminho)
    if not texto:
        continue  # pula arquivos muito grandes ou vazios
    dados = extrair_dados_chave(texto)
    print("===== DADOS EXTRAÍDOS =====")
    print(dados)
    todos_os_dados_extraidos.append(dados)

# Verificação de segurança: só continuar se tiver dados
if not todos_os_dados_extraidos:
    print("⚠️ Nenhum dado extraído. Carta não será gerada.")
    exit()

# Novo: gerar resumo técnico dos dados extraídos
resumo = gerar_resumo_dos_documentos(todos_os_dados_extraidos)

# Novo: buscar normativas relevantes com base no resumo
normativas_texto = buscar_normativas_vigentes(resumo)
nomes_rns, textos_relevantes = identificar_normas_genericas(resumo, normativas_texto.split("\n\n"))

# Novo: gerar a carta usando o resumo e as normas
print("===== GERANDO CARTA FINAL UNIFICADA =====")
carta_final = gerar_carta_resposta(resumo, "\n\n".join(textos_relevantes))
print(carta_final)

# Função auxiliar para extrair valores de campos
def extrair_valor(texto, campo):
    for linha in texto.split("\n"):
        if campo in linha:
            return linha.split(":", 1)[1].strip()
    return "DADO NÃO ENCONTRADO"

# Procurar o primeiro conjunto com NIP, protocolo e demanda
nip = protocolo = demanda = "DADO NÃO ENCONTRADO"

for dados in todos_os_dados_extraidos:
    if "Número da NIP" in dados and "Protocolo" in dados and "Número da demanda" in dados:
        n = extrair_valor(dados, "Número da NIP")
        p = extrair_valor(dados, "Protocolo")
        d = extrair_valor(dados, "Número da demanda")
        if all(x not in [None, "", "Não mencionado no texto", "Não fornecido", "Não informado", "Não disponível no texto"] for x in [n, p, d]):
            nip, protocolo, demanda = n, p, d
            break
# Substituir os campos no texto da carta
carta_final = carta_final.replace("[número da NIP]", nip)
carta_final = carta_final.replace("[protocolo]", protocolo)
carta_final = carta_final.replace("[número da demanda]", demanda)

print("\n===== CARTA FINAL COM CAMPOS PREENCHIDOS =====\n")
print(carta_final)
print("===== CARTA FINAL COM CAMPOS PREENCHIDOS =====")
print(carta_final)
