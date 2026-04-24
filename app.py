import streamlit as st
import google.generativeai as genai
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaInMemoryUpload
import time
import re
import json #

# Interface do App
st.set_page_config(page_title="Fábrica de Roteiros", layout="wide")
st.title("🎬 Fábrica de Roteiros em Lote")

# Funções de Autenticação e Drive
def autenticar_drive(credentials_info):
    creds = service_account.Credentials.from_service_account_info(credentials_info)
    return build('drive', 'v3', credentials=creds)

def obter_ou_criar_pasta(nome_pasta, parent_id, drive_service):
    query = f"mimeType='application/vnd.google-apps.folder' and name='{nome_pasta}' and '{parent_id}' in parents and trashed=false"
    results = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])
    if not items:
        file_metadata = {'name': nome_pasta, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent_id]}
        folder = drive_service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')
    return items[0].get('id')

def upload_to_drive(nome_arquivo, conteudo, folder_id, drive_service):
    file_metadata = {'name': nome_arquivo, 'parents': [folder_id]}
    media = MediaInMemoryUpload(conteudo.encode('utf-8'), mimetype='text/plain')
    drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()

# Configurações na Barra Lateral
with st.sidebar:
    st.header("🔑 Configurações")
    gemini_key = st.text_input("Gemini API Key", type="password")
    pasta_principal_id = st.text_input("ID Pasta Principal", value="1RH-VwGnJTj_avH2Dg3KNDthPNsSiamgp")
    min_chars = st.number_input("Mínimo de caracteres", value=2000)
    target_chars = st.number_input("Alvo de caracteres", value=3500)

# Campos de Produção
col1, col2 = st.columns(2)
with col1:
    idioma_alvo = st.selectbox("Idioma", ["Francês", "Português", "Croata", "Inglês", "Sérvio"])
    pais_alvo = st.text_input("País de referência", "França")
with col2:
    prompt_base = st.text_area("Instruções de Estilo", "Texto dinâmico, sem tópicos, focado em retenção.")

titulos_raw = st.text_area("Títulos dos Vídeos (um por linha)")

# Lógica de Geração com QA
def gerar_roteiro(titulo, prompt_base, idioma, pais, min_c, target_c):
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel('gemini-1.5-pro')
    instrucoes = f"Escreva um roteiro corrido (sem tópicos/hashtags) em {idioma} para o público da {pais}. Título: {titulo}. Estilo: {prompt_base}. Alvo: {target_c} caracteres."
    
    for _ in range(3):
        res = model.generate_content(instrucoes)
        texto = res.text.strip()
        if len(texto) >= min_c and "#" not in texto and "*" not in texto:
            return texto, "QUALIDADE OK"
        time.sleep(1)
    return texto, "QUALIDADE BAIXA"

# Botão de Ação
if st.button("🚀 Iniciar Produção"):
    if not gemini_key or not titulos_raw:
        st.error("Preencha a chave e os títulos.")
    else:
        try:
            drive_creds = json.loads(st.secrets["gcp_json"])
            drive_service = autenticar_drive(drive_creds)
            pasta_idioma_id = obter_ou_criar_pasta(idioma_alvo, pasta_principal_id, drive_service)
            
            titulos = [t.strip() for t in titulos_raw.split('\n') if t.strip()]
            for t in titulos:
                with st.status(f"Criando: {t}..."):
                    roteiro, qa = gerar_roteiro(t, prompt_base, idioma_alvo, pais_alvo, min_chars, target_chars)
                    upload_to_drive(f"{t}.txt", roteiro, pasta_idioma_id, drive_service)
            st.success("Tudo pronto e salvo no Drive!")
        except Exception as e:
            st.error(f"Erro: {e}")
