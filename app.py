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

# --- BARRA LATERAL (CONFIGURAÇÕES) ---
with st.sidebar:
    st.header("🔑 Configurações")
    gemini_key = st.text_input("Gemini API Key", type="password")
    pasta_principal_id = st.text_input("ID Pasta Principal", value="1RH-VwGnJTj_avH2Dg3KNDthPNsSiamgp")
    
    st.header("🧠 Motor da IA")
    opcao_modelo = st.selectbox(
        "Selecione a Versão do Gemini:", 
        [
            "Gemini 3.1 Pro (Preview)", 
            "Gemini 3 Flash",
            "Gemini 1.5 Pro (Estável)"
        ]
    )
    
    # IDs atualizados conforme documentação de Abril/2026
    mapa_modelos = {
        "Gemini 3.1 Pro (Preview)": "models/gemini-3.1-pro-preview",
        "Gemini 3 Flash": "models/gemini-3-flash",
        "Gemini 1.5 Pro (Estável)": "models/gemini-1.5-pro-latest"
    }
    modelo_id = mapa_modelos[opcao_modelo]
    
    st.header("📏 Parâmetros de Texto")
    min_chars = st.number_input("Mínimo de caracteres", value=2000)
    target_chars = st.number_input("Alvo de caracteres", value=3500)

# --- CORPO DO APP ---
col1, col2 = st.columns(2)
with col1:
    idioma_alvo = st.selectbox("Idioma", ["Francês", "Português", "Croata", "Inglês", "Sérvio", "Espanhol"])
    pais_alvo = st.text_input("País de referência", "França")
with col2:
    prompt_base = st.text_area("Instruções de Estilo", "Texto dinâmico, envolvente, focado em alta retenção.")

titulos_raw = st.text_area("Títulos dos Vídeos (um por linha)", height=150)

# --- EXECUÇÃO COM STREAMING ---
if st.button("🚀 Iniciar Produção em Lote"):
    if not gemini_key or not titulos_raw:
        st.error("Preencha a chave do Gemini e a lista de títulos.")
    else:
        genai.configure(api_key=gemini_key)
        
        # Tenta inicializar o modelo selecionado
        try:
            model = genai.GenerativeModel(modelo_id)
        except:
            st.warning(f"Modelo {modelo_id} não respondeu. Tentando fallback para 1.5-pro...")
            model = genai.GenerativeModel("models/gemini-1.5-pro-latest")
        
        drive_service = None
        pasta_idioma_id = None
        try:
            drive_creds = json.loads(st.secrets["gcp_json"])
            drive_service = autenticar_drive(drive_creds)
            with st.spinner("Acessando Google Drive..."):
                pasta_idioma_id = obter_ou_criar_pasta(idioma_alvo, pasta_principal_id, drive_service)
        except:
            st.warning("⚠️ Drive inacessível. Use os botões de download.")

        titulos = [t.strip() for t in titulos_raw.split('\n') if t.strip()]
        
        for i, t in enumerate(titulos):
            st.markdown(f"### 📝 Roteiro: {t}")
            
            instrucoes = f"""
            Escreva um roteiro corrido em {idioma_alvo} para o público da {pais_alvo}. 
            REGRAS: 1. Apenas texto corrido. 2. Sem Markdown (#, *, tópicos). 
            3. Alvo: {target_chars} caracteres. 4. Estilo: {prompt_base}.
            Título: {t}. Comece direto no texto.
            """
            
            texto_final = ""
            status_qa = "FALHA"
            
            for tentativa in range(3):
                st.caption(f"Tentativa {tentativa+1}/3...")
                caixa_texto = st.empty()
                texto_parcial = ""
                
                try:
                    res = model.generate_content(instrucoes, stream=True)
                    for chunk in res:
                        texto_parcial += chunk.text
                        caixa_texto.info(texto_parcial + " ✍️")
                    
                    caixa_texto.success(texto_parcial)
                    
                    # Verificação de QA (Markdown e Tamanho)
                    tem_markdown = bool(re.search(r'#|\*|- |[0-9]\.', texto_parcial))
                    if len(texto_parcial) >= min_chars and not tem_markdown:
                        texto_final = texto_parcial
                        status_qa = "OK"
                        break
                    else:
                        instrucoes += "\n\nAVISO: O texto anterior falhou no tamanho ou formato. Refaça apenas texto corrido e longo."
                        time.sleep(2)
                except Exception as e:
                    st.error(f"Erro na API: {e}")
                    break
            
            if status_qa == "OK":
                nome_arq = f"{t.replace('/', '-')}.txt"
                salvo = False
                if drive_service and pasta_idioma_id:
                    try:
                        upload_to_drive(nome_arq, texto_final, pasta_idioma_id, drive_service)
                        st.write("✅ Salvo no Drive.")
                        salvo = True
                    except: pass
                
                if not salvo:
                    st.download_button(label=f"⬇️ Baixar {nome_arq}", data=texto_final, file_name=nome_arq)
            
            st.divider()
