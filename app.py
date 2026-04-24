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
    opcao_modelo = st.radio(
        "Selecione a Qualidade:", 
        [
            "Premium Max (Gemini 3.1 Pro)", 
            "Premium (Gemini 2.5 Pro)", 
            "Econômico (Gemini 3 Flash)"
        ],
        help="O 3.1 Pro é o mais avançado. O Flash é o mais rápido."
    )
    
    # Define o ID do modelo com base na escolha
    if "3.1" in opcao_modelo:
        modelo_id = 'gemini-3.1-pro'
    elif "2.5" in opcao_modelo:
        modelo_id = 'gemini-2.5-pro'
    else:
        modelo_id = 'gemini-3-flash'
    
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
        st.error("Preencha a chave do Gemini e a lista de títulos antes de começar.")
    else:
        # Configura a IA
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel(modelo_id)
        
        # Tenta conectar no Drive (se falhar, não impede a geração do texto na tela)
        drive_service = None
        pasta_idioma_id = None
        try:
            drive_creds = json.loads(st.secrets["gcp_json"])
            drive_service = autenticar_drive(drive_creds)
            with st.spinner(f"Verificando pasta '{idioma_alvo}' no Drive..."):
                pasta_idioma_id = obter_ou_criar_pasta(idioma_alvo, pasta_principal_id, drive_service)
        except Exception as e:
            st.warning("Aviso: Conexão com Google Drive falhou ou cota excedida. Os roteiros serão gerados apenas aqui na tela para você copiar/baixar.")

        titulos = [t.strip() for t in titulos_raw.split('\n') if t.strip()]
        
        for i, t in enumerate(titulos):
            st.markdown(f"### 📝 Escrevendo: {t}")
            
            instrucoes = f"""
            Crie um roteiro para narração de IA. 
            REGRAS CRÍTICAS:
            1. APENAS TEXTO CORRIDO. É terminantemente proibido usar formatação markdown (sem #, sem **, sem tópicos enumerados).
            2. IDIOMA: {idioma_alvo}. CONTEXTO CULTURAL: {pais_alvo}.
            3. TAMANHO ALVO: aproximadamente {target_chars} caracteres.
            4. ESTILO: {prompt_base}.
            Título do Vídeo: {t}
            Comece o texto diretamente pela narração.
            """
            
            texto_final = ""
            status_qa = "FALHA"
            
            # Loop de Tentativas (QA)
            for tentativa in range(3):
                st.caption(f"Tentativa {tentativa + 1}/3 - Analisando e gerando...")
                caixa_texto = st.empty() # Cria um espaço vazio na tela para o texto ao vivo
                texto_parcial = ""
                
                try:
                    # Geração em Tempo Real (Streaming)
                    res = model.generate_content(instrucoes, stream=True)
                    for chunk in res:
                        texto_parcial += chunk.text
                        # Atualiza a tela ao vivo com um cursor simulado
                        caixa_texto.info(texto_parcial + " ✍️")
                    
                    # Quando termina, remove o cursor
                    caixa_texto.success(texto_parcial)
                    
                    # Validação de Qualidade
                    tem_markdown = bool(re.search(r'#|\*|- |[0-9]\.', texto_parcial))
                    
                    if len(texto_parcial) >= min_chars and not tem_markdown:
                        texto_final = texto_parcial
                        status_qa = "OK"
                        break # Se passou no teste, sai do loop
                    else:
                        instrucoes += f"\n\nERRO: O texto anterior ficou com {len(texto_parcial)} caracteres (mínimo é {min_chars}) ou usou formatação proibida. REESCREVA APENAS TEXTO CORRIDO."
                        st.warning("⚠️ O texto não atingiu o padrão de qualidade (tamanho ou formatação). Refazendo...")
                        time.sleep(2)
                        
                except Exception as e:
                    st.error(f"Erro na API do Gemini: {e}")
                    break
            
            # Pós-Processamento: Salvar no Drive ou Exibir Download
            if status_qa == "OK":
                nome_arquivo = f"{t.replace('/', '-')}.txt"
                
                # Tenta enviar pro Drive
                salvo_no_drive = False
                if drive_service and pasta_idioma_id:
                    try:
                        upload_to_drive(nome_arquivo, texto_final, pasta_idioma_id, drive_service)
                        st.write("✅ **Salvo automaticamente no Google Drive!**")
                        salvo_no_drive = True
                    except Exception as e:
                        pass # Silencia o erro do Drive porque vamos dar o botão de download
                
                # Se o Drive bloqueou (erro 403), cria um botão de Download direto no aplicativo
                if not salvo_no_drive:
                    st.download_button(
                        label=f"⬇️ Baixar Roteiro: {nome_arquivo}",
                        data=texto_final,
                        file_name=nome_arquivo,
                        mime="text/plain"
                    )
            else:
                st.error("❌ Falha crítica: A IA não conseguiu gerar um roteiro dentro das regras após 3 tentativas.")
                
            st.divider() # Linha de separação entre os vídeos
