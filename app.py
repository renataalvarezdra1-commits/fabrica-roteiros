import streamlit as st
import google.generativeai as genai
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaInMemoryUpload
import time
import re
import json

# --- CONFIGURAÇÕES DA INTERFACE ---
st.set_page_config(page_title="Fábrica de Roteiros v3.1", layout="wide")
st.title("🎬 Fábrica de Roteiros em Lote")

# --- CONEXÃO COM GOOGLE DRIVE ---
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

# --- BARRA LATERAL (CONFIGURAÇÕES & CUSTO) ---
with st.sidebar:
    st.header("🔑 Configurações")
    gemini_key = st.text_input("Gemini API Key", type="password")
    pasta_principal_id = st.text_input("ID Pasta Principal", value="1RH-VwGnJTj_avH2Dg3KNDthPNsSiamgp")
    
    st.header("🧠 Motor da IA")
    opcao_modelo = st.selectbox(
        "Selecione a Versão:", 
        ["Gemini 3.1 Pro (Preview)", "Gemini 3 Flash"]
    )
    modelo_id = "models/gemini-3.1-pro-preview" if "3.1" in opcao_modelo else "models/gemini-3-flash"
    
    st.header("📏 Parâmetros")
    min_chars = st.number_input("Mínimo caracteres", value=2000)
    target_chars = st.number_input("Alvo caracteres", value=3500)

    # --- CÁLCULO DE CUSTO ESTIMADO ---
    st.header("💰 Estimativa de Custo")
    num_roteiros = st.empty() # Reservado para contagem
    
    # Preços Gemini 3.1 Pro (Ref: Abril 2026)
    price_in = 2.00 / 1_000_000
    price_out = 12.00 / 1_000_000
    
    # Estimativa por roteiro (aprox 1200 tokens)
    custo_unitario = (300 * price_in) + ((target_chars/4) * price_out)
    st.info(f"Custo aprox. por roteiro: **US$ {custo_unitario:.4f}**")

# --- CORPO DO APP ---
col1, col2 = st.columns(2)
with col1:
    idioma_alvo = st.selectbox("Idioma", ["Francês", "Português", "Croata", "Inglês", "Sérvio", "Espanhol"])
    pais_alvo = st.text_input("País de referência", "França")
with col2:
    prompt_base = st.text_area("Instruções de Estilo", "Texto dinâmico, sem tópicos, foco em retenção.")

titulos_raw = st.text_area("Títulos dos Vídeos (um por linha)", height=150)
titulos = [t.strip() for t in titulos_raw.split('\n') if t.strip()]
num_roteiros.write(f"Fila atual: **{len(titulos)} roteiros**")
st.sidebar.write(f"Custo total da fila: **US$ {custo_unitario * len(titulos):.3f}**")

# --- LÓGICA DE PRODUÇÃO ---
if st.button("🚀 Iniciar Produção em Lote"):
    if not gemini_key or not titulos:
        st.error("Preencha os dados necessários.")
    else:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel(modelo_id)
        
        # Drive Setup
        drive_service = None
        pasta_idioma_id = None
        try:
            drive_creds = json.loads(st.secrets["gcp_json"])
            drive_service = autenticar_drive(drive_creds)
            pasta_idioma_id = obter_ou_criar_pasta(idioma_alvo, pasta_principal_id, drive_service)
        except:
            st.warning("⚠️ Drive em modo manual.")

        for t in titulos:
            st.subheader(f"📝 Processando: {t}")
            
            instrucoes = f"Escreva um roteiro corrido (sem # ou *) em {idioma_alvo} ({pais_alvo}). Título: {t}. Estilo: {prompt_base}. Alvo: {target_chars} caracteres."
            
            texto_final = ""
            # Slot de texto para streaming
            caixa_streaming = st.empty()
            
            try:
                # GERAÇÃO EM TEMPO REAL
                res = model.generate_content(instrucoes, stream=True)
                for chunk in res:
                    texto_final += chunk.text
                    caixa_streaming.write(texto_final + " ✍️")
                
                caixa_streaming.markdown(texto_final) # Texto limpo ao final
                
                # QA Simples
                tem_markdown = "#" in texto_final or "*" in texto_final
                if len(texto_final) < min_chars or tem_markdown:
                    st.error("⚠️ Falha no critério de qualidade (Curto ou com Markdown).")
                
                # AÇÕES DE SALVAMENTO
                nome_arq = f"{t.replace('/', '-')}.txt"
                
                c_download, c_drive = st.columns(2)
                with c_download:
                    st.download_button("⬇️ Baixar TXT", data=texto_final, file_name=nome_arq)
                
                with c_drive:
                    # Tenta automático primeiro
                    try:
                        if drive_service and pasta_idioma_id:
                            upload_to_drive(nome_arq, texto_final, pasta_idioma_id, drive_service)
                            st.success("✅ Salvo no Drive!")
                        else:
                            if st.button(f"📤 Reenviar: {t}"):
                                upload_to_drive(nome_arq, texto_final, pasta_idioma_id, drive_service)
                                st.success("Enviado!")
                    except Exception as e:
                        st.error("Erro no Drive (Cota). Use o download.")
            
            except Exception as e:
                st.error(f"Erro na geração: {e}")
            
            st.divider()
