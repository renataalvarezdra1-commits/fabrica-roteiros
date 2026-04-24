import streamlit as st
import google.generativeai as genai
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaInMemoryUpload
import time
import re
import json

# --- CONFIGURAÇÕES DA INTERFACE ---
st.set_page_config(page_title="Fábrica de Roteiros", layout="wide")
st.title("🎬 Fábrica de Roteiros em Lote")

# --- CONEXÃO COM GOOGLE DRIVE ---
def autenticar_drive(credentials_info):
    creds = service_account.Credentials.from_service_account_info(credentials_info)
    return build('drive', 'v3', credentials=creds)

def obter_ou_criar_pasta(nome_pasta, parent_id, drive_service):
    """Verifica se a subpasta do idioma existe; se não, cria."""
    query = f"mimeType='application/vnd.google-apps.folder' and name='{nome_pasta}' and '{parent_id}' in parents and trashed=false"
    results = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])
    
    if not items:
        file_metadata = {
            'name': nome_pasta,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
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
    opcao_modelo = st.radio(
        "Selecione a Qualidade:", 
        ["Modo Premium (Gemini 2.5 Pro)", "Modo Econômico (Gemini 3 Flash)"],
        help="O Modo Premium tem vocabulário mais rico e segue regras estritas. O Flash é ultrarrápido e barato."
    )
    # Define o ID do modelo com base na escolha
    modelo_id = 'gemini-2.5-pro' if "Premium" in opcao_modelo else 'gemini-3-flash'
    
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

# --- MOTOR DE GERAÇÃO COM SISTEMA DE QUALIDADE (QA) ---
def gerar_roteiro(titulo, prompt_base, idioma, pais, min_c, target_c, modelo_escolhido):
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel(modelo_escolhido)
    
    instrucoes = f"""
    Crie um roteiro para narração de IA. 
    REGRAS CRÍTICAS:
    1. APENAS TEXTO CORRIDO. É terminantemente proibido usar formatação markdown (sem #, sem **, sem tópicos enumerados).
    2. IDIOMA: {idioma}. CONTEXTO CULTURAL: {pais}.
    3. TAMANHO ALVO: aproximadamente {target_c} caracteres.
    4. ESTILO: {prompt_base}.
    
    Título do Vídeo: {titulo}
    Comece o texto diretamente pela narração.
    """
    
    for tentativa in range(3):
        try:
            res = model.generate_content(instrucoes)
            texto = res.text.strip()
            
            # Verificação de Qualidade (QA)
            tem_markdown = bool(re.search(r'#|\*|- |[0-9]\.', texto))
            
            if len(texto) >= min_c and not tem_markdown:
                return texto, "QUALIDADE OK"
            else:
                instrucoes += f"\n\nERRO: O texto anterior ficou com {len(texto)} caracteres (mínimo é {min_c}) ou usou formatação proibida. REESCREVA APENAS TEXTO CORRIDO."
                time.sleep(2)
        except Exception as e:
            # Se a chave da API for recusada, ele aborta na hora e devolve o erro real
            return f"ERRO DA API: {str(e)}", "FALHA"
            
    return texto, "QUALIDADE BAIXA (Passou com ressalvas após 3 tentativas)"

# --- EXECUÇÃO EM LOTE ---
if st.button("🚀 Iniciar Produção em Lote"):
    if not gemini_key or not titulos_raw:
        st.error("Preencha a chave do Gemini e a lista de títulos antes de começar.")
    else:
        try:
            # 1. Autenticação e Preparação de Pastas
            drive_creds = json.loads(st.secrets["gcp_json"])
            drive_service = autenticar_drive(drive_creds)
            
            with st.spinner(f"Preparando pasta para '{idioma_alvo}' no Google Drive..."):
                pasta_idioma_id = obter_ou_criar_pasta(idioma_alvo, pasta_principal_id, drive_service)
            
            # 2. Início da Fila de Produção
            titulos = [t.strip() for t in titulos_raw.split('\n') if t.strip()]
            progresso = st.progress(0)
            
            for i, t in enumerate(titulos):
                with st.status(f"Escrevendo roteiro: {t}...", expanded=True) as status:
                    st.write(f"Usando modelo: `{modelo_id}`")
                    
                    roteiro, qa = gerar_roteiro(t, prompt_base, idioma_alvo, pais_alvo, min_chars, target_chars, modelo_id)
                    
                    # SE A API RECUSAR A CHAVE, MOSTRA O ERRO GIGANTE EM VERMELHO
                    if qa == "FALHA":
                        st.error(f"🚨 A Geração Falhou!\n\nDetalhes do Erro:\n{roteiro}")
                        status.update(label=f"Falha: {t}", state="error")
                    else:
                        st.write(f"Status QA: {qa} | Tamanho final: {len(roteiro)} caracteres.")
                        nome_arquivo = f"{t.replace('/', '-')}.txt"
                        upload_to_drive(nome_arquivo, roteiro, pasta_idioma_id, drive_service)
                        st.write(f"✅ Arquivo salvo no Drive.")
                        status.update(label=f"Concluído: {t}", state="complete")
                
                progresso.progress((i + 1) / len(titulos))
                time.sleep(2) # Pausa para evitar rate limit da API
                
            if qa != "FALHA":
                st.success("Toda a fila de produção foi finalizada e enviada para o Drive!")
            
        except Exception as e:
            st.error(f"Erro no processo de salvamento do Google Drive: {e}")
