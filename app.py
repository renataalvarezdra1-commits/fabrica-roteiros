        
                import streamlit as st
import google.generativeai as genai
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaInMemoryUpload
import json

# --- CONFIGURAÇÕES DA INTERFACE ---
st.set_page_config(page_title="Fábrica de Roteiros v3.2", layout="wide")
st.title("🎬 Fábrica de Roteiros em Lote")

# --- CONEXÃO COM GOOGLE DRIVE ---
def autenticar_drive(credentials_info):
    # FIX Bug 3: Scopes explícitos para evitar erro de permissão silencioso
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
# FIX Bug 1 & 2: Estado persistente para Drive e log de status
if "drive_service" not in st.session_state:
    st.session_state.drive_service = None
if "pasta_idioma_id" not in st.session_state:
    st.session_state.pasta_idioma_id = None
if "drive_ok" not in st.session_state:
    st.session_state.drive_ok = False
if "drive_erro" not in st.session_state:
    st.session_state.drive_erro = ""
if "log_status" not in st.session_state:
    st.session_state.log_status = []  # Lista de dicts: {titulo, status, obs}
if "roteiros_gerados" not in st.session_state:
    st.session_state.roteiros_gerados = {}  # {titulo: texto}

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

    # --- FIX Bug 2 & 3: Conexão Drive com erro detalhado ---
    st.header("☁️ Google Drive")
    if st.button("🔌 Conectar ao Drive"):
        st.session_state.drive_ok = False
        st.session_state.drive_erro = ""
        try:
            drive_creds = json.loads(st.secrets["gcp_json"])
            svc = autenticar_drive(drive_creds)
            # Testa a conexão antes de confirmar
            svc.files().list(pageSize=1, fields="files(id)").execute()
            st.session_state.drive_service = svc
            st.session_state.drive_ok = True
        except KeyError:
            st.session_state.drive_erro = "Secret 'gcp_json' não encontrado."
        except json.JSONDecodeError:
            st.session_state.drive_erro = "JSON inválido no secret 'gcp_json'."
        except Exception as e:
            st.session_state.drive_erro = f"Erro de autenticação: {e}"

    if st.session_state.drive_ok:
        st.success("✅ Drive conectado")
    elif st.session_state.drive_erro:
        st.error(f"❌ {st.session_state.drive_erro}")
    else:
        st.warning("⚠️ Drive não conectado — apenas download manual.")

    # --- LOG DE STATUS ---
    if st.session_state.log_status:
        st.header("📋 Log de Produção")
        for entrada in st.session_state.log_status:
            icone = (
                "✅" if entrada["status"] == "ok"
                else "⚠️" if entrada["status"] == "drive_falhou"
                else "❌"
            )
            st.markdown(
                f"{icone} **{entrada['titulo'][:30]}...**  \n"
                f"_{entrada['obs']}_"
            )

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

st.caption(f"Fila atual: **{len(titulos)} roteiros** | Custo estimado: **US$ {custo_unitario * len(titulos):.3f}**")

# --- FIX Bug 1: Botões de reenvio fora do loop de geração ---
# Exibe roteiros já gerados com opção de reenvio persistente
if st.session_state.roteiros_gerados:
    st.subheader("📤 Reenviar ao Drive")
    for titulo_salvo, texto_salvo in st.session_state.roteiros_gerados.items():
        nome_arq = f"{titulo_salvo.replace('/', '-')}.txt"
        col_a, col_b = st.columns([3, 1])
        with col_a:
            st.caption(f"📄 {titulo_salvo[:60]}")
        with col_b:
            if st.button(f"Reenviar", key=f"reenviar_{titulo_salvo}"):
                if not st.session_state.drive_ok:
                    st.error("Drive não conectado. Use o botão 'Conectar ao Drive' na sidebar.")
                else:
                    try:
                        # Garante que a pasta do idioma existe
                        if not st.session_state.pasta_idioma_id:
                            st.session_state.pasta_idioma_id = obter_ou_criar_pasta(
                                idioma_alvo, pasta_principal_id,
                                st.session_state.drive_service
                            )
                        upload_to_drive(
                            nome_arq, texto_salvo,
                            st.session_state.pasta_idioma_id,
                            st.session_state.drive_service
                        )
                        st.success(f"✅ '{titulo_salvo[:40]}' enviado!")
                    except Exception as e:
                        st.error(f"Erro no reenvio: {e}")
    st.divider()

# --- LÓGICA DE PRODUÇÃO ---
if st.button("🚀 Iniciar Produção em Lote"):
    if not gemini_key or not titulos:
        st.error("Preencha a API Key e pelo menos um título.")
    else:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel(modelo_id)

        # Cria pasta no Drive se conectado
        if st.session_state.drive_ok and not st.session_state.pasta_idioma_id:
            try:
                st.session_state.pasta_idioma_id = obter_ou_criar_pasta(
                    idioma_alvo, pasta_principal_id, st.session_state.drive_service
                )
            except Exception as e:
                st.warning(f"Não foi possível criar pasta no Drive: {e}")

        # Limpa log anterior
        st.session_state.log_status = []

        for t in titulos:
            st.subheader(f"📝 Processando: {t}")
            log_entry = {"titulo": t, "status": "erro", "obs": ""}

            instrucoes = (
                f"Escreva um roteiro corrido (sem # ou *) em {idioma_alvo} ({pais_alvo}). "
                f"Título: {t}. Estilo: {prompt_base}. Alvo: {target_chars} caracteres."
            )

            texto_final = ""
            caixa_streaming = st.empty()

            try:
                res = model.generate_content(instrucoes, stream=True)
                for chunk in res:
                    if chunk.text:
                        texto_final += chunk.text
                        caixa_streaming.write(texto_final + " ✍️")

                caixa_streaming.markdown(texto_final)

                # QA
                tem_markdown = "#" in texto_final or "*" in texto_final
                muito_curto = len(texto_final) < min_chars
                if muito_curto or tem_markdown:
                    aviso = []
                    if muito_curto:
                        aviso.append(f"curto ({len(texto_final)} chars)")
                    if tem_markdown:
                        aviso.append("contém markdown")
                    st.warning(f"⚠️ Qualidade: {', '.join(aviso)}")

                # Salva no session state para permitir reenvio posterior
                st.session_state.roteiros_gerados[t] = texto_final

                nome_arq = f"{t.replace('/', '-')}.txt"

                # Download sempre disponível
                st.download_button(
                    "⬇️ Baixar TXT",
                    data=texto_final,
                    file_name=nome_arq,
                    key=f"dl_{t}"
                )

                # Drive: tenta envio automático
                if st.session_state.drive_ok and st.session_state.pasta_idioma_id:
                    try:
                        upload_to_drive(
                            nome_arq, texto_final,
                            st.session_state.pasta_idioma_id,
                            st.session_state.drive_service
                        )
                        log_entry["status"] = "ok"
                        log_entry["obs"] = f"Salvo no Drive · {len(texto_final)} chars"
                        st.success("✅ Salvo no Drive!")
                    except Exception as e:
                        log_entry["status"] = "drive_falhou"
                        log_entry["obs"] = f"Gerado, Drive falhou: {e}"
                        st.warning(f"⚠️ Drive falhou: {e}. Use Download ou Reenviar acima.")
                else:
                    log_entry["status"] = "drive_falhou"
                    log_entry["obs"] = "Gerado · Drive não conectado"

            except Exception as e:
                log_entry["obs"] = str(e)
                st.error(f"Erro na geração: {e}")

            st.session_state.log_status.append(log_entry)
            st.divider()

        st.success(f"🏁 Lote concluído! {len(titulos)} roteiros processados.")
        st.rerun()
                
