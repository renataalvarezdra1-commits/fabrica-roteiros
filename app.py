import streamlit as st
import google.generativeai as genai
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaInMemoryUpload
import json
import time
import re

# --- CONFIGURAÇÕES DA INTERFACE ---
st.set_page_config(page_title="Fábrica de Roteiros v3.2", layout="wide")
st.title("🎬 Fábrica de Roteiros em Lote")

# --- CONEXÃO COM GOOGLE DRIVE ---
def autenticar_drive(credentials_info):
    # FIX: Scopes explícitos para evitar erro de permissão silencioso
    scopes = ["https://www.googleapis.com/auth/drive.file"]
    creds = service_account.Credentials.from_service_account_info(
        credentials_info, scopes=scopes
    )
    return build('drive', 'v3', credentials=creds)

def obter_ou_criar_pasta(nome_pasta, parent_id, drive_service):
    query = (
        f"mimeType='application/vnd.google-apps.folder' "
        f"and name='{nome_pasta}' "
        f"and '{parent_id}' in parents "
        f"and trashed=false"
    )
    results = drive_service.files().list(
        q=query, spaces='drive', fields='files(id, name)'
    ).execute()
    items = results.get('files', [])
    if not items:
        file_metadata = {
            'name': nome_pasta,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
        folder = drive_service.files().create(
            body=file_metadata, fields='id'
        ).execute()
        return folder.get('id')
    return items[0].get('id')

def upload_to_drive(nome_arquivo, conteudo, folder_id, drive_service):
    file_metadata = {'name': nome_arquivo, 'parents': [folder_id]}
    media = MediaInMemoryUpload(conteudo.encode('utf-8'), mimetype='text/plain')
    drive_service.files().create(
        body=file_metadata, media_body=media, fields='id'
    ).execute()

# --- INICIALIZA SESSION STATE ---
if "drive_service" not in st.session_state:
    st.session_state.drive_service = None
if "pasta_idioma_id" not in st.session_state:
    st.session_state.pasta_idioma_id = None
if "drive_ok" not in st.session_state:
    st.session_state.drive_ok = False
if "drive_erro" not in st.session_state:
    st.session_state.drive_erro = ""
if "log_status" not in st.session_state:
    st.session_state.log_status = []
if "roteiros_gerados" not in st.session_state:
    st.session_state.roteiros_gerados = {}

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("🔑 Configurações")
    gemini_key = st.text_input("Gemini API Key", type="password")
    pasta_principal_id = st.text_input(
        "ID Pasta Principal", value="1RH-VwGnJTj_avH2Dg3KNDthPNsSiamgp"
    )

    st.header("🧠 Motor da IA")
    opcao_modelo = st.selectbox(
        "Selecione a Versão:",
        ["Gemini 3.1 Pro (Preview)", "Gemini 3 Flash"]
    )
    modelo_id = (
        "models/gemini-3.1-pro-preview"
        if "3.1" in opcao_modelo
        else "models/gemini-3-flash"
    )

    st.header("📏 Parâmetros")
    min_chars = st.number_input("Mínimo caracteres", value=2000)
    target_chars = st.number_input("Alvo caracteres", value=3500)

    st.header("💰 Estimativa de Custo")
    price_in = 2.00 / 1_000_000
    price_out = 12.00 / 1_000_000
    custo_unitario = (300 * price_in) + ((target_chars / 4) * price_out)
    st.info(f"Custo aprox. por roteiro: **US$ {custo_unitario:.4f}**")

    st.header("☁️ Google Drive")
    if st.button("🔌 Conectar ao Drive"):
        st.session_state.drive_ok = False
        st.session_state.drive_erro = ""
        try:
            # Tenta carregar o segredo gcp_json
            if "gcp_json" in st.secrets:
                drive_creds = json.loads(st.secrets["gcp_json"])
            else:
                # Fallback para o formato antigo se necessário
                drive_creds = st.secrets["gcp_service_account"]
            
            svc = autenticar_drive(drive_creds)
            svc.files().list(pageSize=1, fields="files(id)").execute()
            st.session_state.drive_service = svc
            st.session_state.drive_ok = True
        except Exception as e:
            st.session_state.drive_erro = f"Erro: {e}"

    if st.session_state.drive_ok:
        st.success("✅ Drive conectado")
    elif st.session_state.drive_erro:
        st.error(f"❌ {st.session_state.drive_erro}")

# --- CORPO DO APP ---
col1, col2 = st.columns(2)
with col1:
    idioma_alvo = st.selectbox(
        "Idioma", ["Francês", "Português", "Croata", "Inglês", "Sérvio", "Espanhol"]
    )
    pais_alvo = st.text_input("País de referência", "França")
with col2:
    prompt_base = st.text_area(
        "Instruções de Estilo", "Texto dinâmico, sem tópicos, foco em retenção."
    )

titulos_raw = st.text_area("Títulos dos Vídeos (um por linha)", height=150)
titulos = [t.strip() for t in titulos_raw.split('\n') if t.strip()]

st.caption(f"Fila atual: **{len(titulos)} roteiros** | Custo: **US$ {custo_unitario * len(titulos):.3f}**")

# --- REENVIO MANUAL ---
if st.session_state.roteiros_gerados:
    with st.expander("📤 Gerenciar Roteiros Gerados (Reenvio)"):
        for tit, txt in st.session_state.roteiros_gerados.items():
            col_t, col_b = st.columns([4, 1])
            col_t.write(f"📄 {tit}")
            if col_b.button("Reenviar", key=f"re_{tit}"):
                if st.session_state.drive_ok:
                    try:
                        pasta_id = obter_ou_criar_pasta(idioma_alvo, pasta_principal_id, st.session_state.drive_service)
                        upload_to_drive(f"{tit}.txt", txt, pasta_id, st.session_state.drive_service)
                        st.toast(f"✅ Enviado: {tit}")
                    except Exception as e: st.error(f"Erro: {e}")
                else: st.warning("Conecte o Drive primeiro.")

# --- LÓGICA DE PRODUÇÃO ---
if st.button("🚀 Iniciar Produção em Lote"):
    if not gemini_key or not titulos:
        st.error("Preencha a chave e os títulos.")
    else:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel(modelo_id)

        # Prepara a pasta do idioma
        if st.session_state.drive_ok:
            try:
                st.session_state.pasta_idioma_id = obter_ou_criar_pasta(
                    idioma_alvo, pasta_principal_id, st.session_state.drive_service
                )
            except: pass

        for t in titulos:
            st.subheader(f"📝 Escrevendo: {t}")
            instrucoes = f"Escreva um roteiro corrido em {idioma_alvo} ({pais_alvo}). Sem # ou *. Título: {t}. Estilo: {prompt_base}. Alvo: {target_chars} chars."
            
            texto_final = ""
            caixa_streaming = st.empty()

            try:
                res = model.generate_content(instrucoes, stream=True)
                for chunk in res:
                    texto_final += chunk.text
                    caixa_streaming.info(texto_final + " ✍️")
                
                caixa_streaming.success(texto_final)
                st.session_state.roteiros_gerados[t] = texto_final
                
                # Tenta upload automático
                if st.session_state.drive_ok and st.session_state.pasta_idioma_id:
                    nome_arq = f"{t.replace('/', '-')}.txt"
                    upload_to_drive(nome_arq, texto_final, st.session_state.pasta_idioma_id, st.session_state.drive_service)
                    st.write("✅ Salvo no Drive!")
                
                st.download_button("⬇️ Baixar TXT", texto_final, f"{t}.txt", key=f"dl_{t}")
            except Exception as e:
                st.error(f"Erro: {e}")
            st.divider()
                
