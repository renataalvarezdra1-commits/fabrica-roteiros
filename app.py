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
    # Seletor atualizado com as versões de Abril de 2026
    opcao_modelo = st.selectbox(
        "Selecione a Versão do Gemini:", 
        [
            "Gemini 3.1 Pro (Melhor Raciocínio)", 
            "Gemini 2.5 Pro (Estável)", 
            "Gemini 3 Flash (Rápido e Barato)",
            "Gemini 1.5 Pro (Versão de Legado)"
        ]
    )
    
    # Mapeamento técnico dos IDs para evitar Erro 404
    mapa_modelos = {
        "Gemini 3.1 Pro (Melhor Raciocínio)": "models/gemini-3.1-pro-latest",
        "Gemini 2.5 Pro (Estável)": "models/gemini-2.5-pro",
        "Gemini 3 Flash (Rápido e Barato)": "models/gemini-3-flash",
        "Gemini 1.5 Pro (Versão de Legado)": "models/gemini-1.5-pro-latest"
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

# --- EXECUÇÃO EM LOTE COM STREAMING ---
if st.button("🚀 Iniciar Produção em Lote"):
    if not gemini_key or not titulos_raw:
        st.error("Preencha a chave do Gemini e a lista de títulos.")
    else:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel(modelo_id)
        
        drive_service = None
        pasta_idioma_id = None
        try:
            # Tenta carregar credenciais do Streamlit Secrets
            drive_creds = json.loads(st.secrets["gcp_json"])
            drive_service = autenticar_drive(drive_creds)
            with st.spinner(f"Acessando pasta '{idioma_alvo}'..."):
                pasta_idioma_id = obter_ou_criar_pasta(idioma_alvo, pasta_principal_id, drive_service)
        except Exception:
            st.warning("⚠️ Google Drive inacessível (Cota ou Permissão). Use os botões de download abaixo.")

        titulos = [t.strip() for t in titulos_raw.split('\n') if t.strip()]
        
        for i, t in enumerate(titulos):
            st.markdown(f"### 📝 Título: {t}")
            
            instrucoes = f"""
            Crie um roteiro para narração de IA. 
            REGRAS CRÍTICAS:
            1. APENAS TEXTO CORRIDO. Proibido Markdown (sem #, sem **, sem tópicos).
            2. IDIOMA: {idioma_alvo}. CONTEXTO: {pais_alvo}.
            3. TAMANHO: Aproximadamente {target_chars} caracteres.
            4. ESTILO: {prompt_base}.
            Título do Vídeo: {t}
            Comece diretamente pela narração.
            """
            
            texto_final = ""
            status_qa = "FALHA"
            
            for tentativa in range(3):
                st.caption(f"Tentativa {tentativa + 1}/3 usando {modelo_id}...")
                caixa_texto = st.empty()
                texto_parcial = ""
                
                try:
                    res = model.generate_content(instrucoes, stream=True)
                    for chunk in res:
                        texto_parcial += chunk.text
                        caixa_texto.info(texto_parcial + " ✍️")
                    
                    caixa_texto.success(texto_parcial)
                    
                    # QA: Verifica Markdown e Tamanho
                    tem_markdown = bool(re.search(r'#|\*|- |[0-9]\.', texto_parcial))
                    if len(texto_parcial) >= min_chars and not tem_markdown:
                        texto_final = texto_parcial
                        status_qa = "OK"
                        break
                    else:
                        instrucoes += f"\n\nERRO: O texto anterior falhou no QA (Tamanho: {len(texto_parcial)}). REESCREVA APENAS TEXTO CORRIDO E LONGO."
                        time.sleep(2)
                except Exception as e:
                    st.error(f"Erro na API: {e}")
                    break
            
            if status_qa == "OK":
                nome_arquivo = f"{t.replace('/', '-')}.txt"
                salvo = False
                if drive_service and pasta_idioma_id:
                    try:
                        upload_to_drive(nome_arquivo, texto_final, pasta_idioma_id, drive_service)
                        st.write("✅ Salvo no Drive.")
                        salvo = True
                    except: pass
                
                if not salvo:
                    st.download_button(label=f"⬇️ Baixar {nome_arquivo}", data=texto_final, file_name=nome_arquivo)
            
            st.divider()
