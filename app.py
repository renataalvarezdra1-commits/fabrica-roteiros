import streamlit as st
import google.generativeai as genai
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaInMemoryUpload
import json
import time
from datetime import datetime

# ─────────────────────────────────────────────
# DESIGN — Apple Sequoia
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Fábrica de Roteiros",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@300;400;500;600&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');

/* ── Base ── */
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Inter', sans-serif;
    background-color: #1c1c1e;
    color: #f5f5f7;
}

/* ── Background ── */
.stApp {
    background: linear-gradient(160deg, #1c1c1e 0%, #2c2c2e 50%, #1c1c1e 100%);
    min-height: 100vh;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: rgba(28, 28, 30, 0.85);
    backdrop-filter: blur(20px);
    border-right: 1px solid rgba(255,255,255,0.08);
}
[data-testid="stSidebar"] * { color: #f5f5f7 !important; }

/* ── Titles ── */
h1 {
    font-size: 2rem !important;
    font-weight: 600 !important;
    letter-spacing: -0.02em !important;
    color: #f5f5f7 !important;
}
h2, h3 {
    font-weight: 500 !important;
    letter-spacing: -0.01em !important;
    color: #e5e5ea !important;
}

/* ── Cards / containers ── */
.roteiro-card {
    background: rgba(44, 44, 46, 0.7);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 16px;
    padding: 20px 24px;
    margin-bottom: 16px;
    backdrop-filter: blur(10px);
    transition: border-color 0.2s;
}
.roteiro-card:hover { border-color: rgba(255,255,255,0.2); }

.roteiro-titulo {
    font-size: 1rem;
    font-weight: 600;
    color: #f5f5f7;
    margin-bottom: 4px;
}
.roteiro-meta {
    font-size: 0.78rem;
    color: #8e8e93;
    margin-bottom: 12px;
}
.roteiro-preview {
    font-size: 0.85rem;
    color: #aeaeb2;
    line-height: 1.55;
    max-height: 80px;
    overflow: hidden;
    position: relative;
}
.roteiro-preview::after {
    content: '';
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 30px;
    background: linear-gradient(transparent, rgba(44,44,46,0.9));
}

/* ── Pill badges ── */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 500;
    margin-right: 6px;
}
.badge-ok   { background: rgba(52,199,89,0.15);  color: #34c759; border: 1px solid rgba(52,199,89,0.3); }
.badge-warn { background: rgba(255,159,10,0.15); color: #ff9f0a; border: 1px solid rgba(255,159,10,0.3); }
.badge-err  { background: rgba(255,69,58,0.15);  color: #ff453a; border: 1px solid rgba(255,69,58,0.3); }
.badge-lang { background: rgba(10,132,255,0.15); color: #0a84ff; border: 1px solid rgba(10,132,255,0.3); }

/* ── Buttons ── */
.stButton > button {
    background: rgba(255,255,255,0.07) !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    border-radius: 10px !important;
    color: #f5f5f7 !important;
    font-weight: 500 !important;
    transition: all 0.2s !important;
}
.stButton > button:hover {
    background: rgba(255,255,255,0.13) !important;
    border-color: rgba(255,255,255,0.25) !important;
}

/* ── Primary button ── */
div[data-testid="stButton"]:has(button[kind="primary"]) button,
.stButton > button[data-testid*="primary"] {
    background: linear-gradient(135deg, #0a84ff, #007aff) !important;
    border: none !important;
    color: white !important;
}

/* ── Inputs ── */
input, textarea, .stTextInput input, .stTextArea textarea {
    background: rgba(44,44,46,0.8) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 10px !important;
    color: #f5f5f7 !important;
}
input:focus, textarea:focus {
    border-color: #0a84ff !important;
    box-shadow: 0 0 0 3px rgba(10,132,255,0.15) !important;
}

/* ── Select ── */
.stSelectbox > div > div {
    background: rgba(44,44,46,0.8) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 10px !important;
    color: #f5f5f7 !important;
}

/* ── Alerts ── */
.stSuccess { background: rgba(52,199,89,0.1) !important; border-color: rgba(52,199,89,0.3) !important; }
.stWarning { background: rgba(255,159,10,0.1) !important; border-color: rgba(255,159,10,0.3) !important; }
.stError   { background: rgba(255,69,58,0.1)  !important; border-color: rgba(255,69,58,0.3)  !important; }
.stInfo    { background: rgba(10,132,255,0.1) !important; border-color: rgba(10,132,255,0.3) !important; }

/* ── Divider ── */
hr { border-color: rgba(255,255,255,0.08) !important; }

/* ── Number input ── */
.stNumberInput input { text-align: center; }

/* ── Streaming box ── */
.streaming-box {
    background: rgba(28,28,30,0.9);
    border: 1px solid rgba(10,132,255,0.3);
    border-radius: 14px;
    padding: 18px 22px;
    font-size: 0.88rem;
    line-height: 1.65;
    color: #e5e5ea;
    max-height: 360px;
    overflow-y: auto;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); border-radius: 3px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# IDIOMAS
# ─────────────────────────────────────────────
IDIOMAS = {
    # Europeus principais
    "🇫🇷 Francês":      ("Francês",   "França"),
    "🇩🇪 Alemão":       ("Alemão",    "Alemanha"),
    "🇮🇹 Italiano":     ("Italiano",  "Itália"),
    "🇪🇸 Espanhol":     ("Espanhol",  "Espanha"),
    "🇵🇹 Português (PT)":("Português","Portugal"),
    "🇳🇱 Holandês":     ("Holandês",  "Países Baixos"),
    "🇵🇱 Polonês":      ("Polonês",   "Polônia"),
    "🇷🇴 Romeno":       ("Romeno",    "Romênia"),
    "🇨🇿 Tcheco":       ("Tcheco",    "República Tcheca"),
    "🇭🇺 Húngaro":      ("Húngaro",   "Hungria"),
    "🇸🇪 Sueco":        ("Sueco",     "Suécia"),
    "🇳🇴 Norueguês":    ("Norueguês", "Noruega"),
    "🇩🇰 Dinamarquês":  ("Dinamarquês","Dinamarca"),
    "🇫🇮 Finlandês":    ("Finlandês", "Finlândia"),
    "🇬🇷 Grego":        ("Grego",     "Grécia"),
    "🇷🇸 Sérvio":       ("Sérvio",    "Sérvia"),
    "🇭🇷 Croata":       ("Croata",    "Croácia"),
    "🇸🇰 Eslovaco":     ("Eslovaco",  "Eslováquia"),
    "🇧🇬 Búlgaro":      ("Búlgaro",   "Bulgária"),
    "🇺🇦 Ucraniano":    ("Ucraniano", "Ucrânia"),
    "🇷🇺 Russo":        ("Russo",     "Rússia"),
    "🇹🇷 Turco":        ("Turco",     "Turquia"),
    # Globais
    "🇧🇷 Português (BR)":("Português","Brasil"),
    "🇺🇸 Inglês":       ("Inglês",    "Estados Unidos"),
    "🇯🇵 Japonês":      ("Japonês",   "Japão"),
    "🇰🇷 Coreano":      ("Coreano",   "Coreia do Sul"),
    "🇸🇦 Árabe":        ("Árabe",     "Arábia Saudita"),
    "🇮🇳 Hindi":        ("Hindi",     "Índia"),
}

# ─────────────────────────────────────────────
# GOOGLE DRIVE
# ─────────────────────────────────────────────
def autenticar_drive(credentials_info):
    scopes = ["https://www.googleapis.com/auth/drive"]  # FIX: scope completo
    creds = service_account.Credentials.from_service_account_info(
        credentials_info, scopes=scopes
    )
    return build('drive', 'v3', credentials=creds)

def obter_ou_criar_pasta(nome_pasta, parent_id, drive_service):
    nome_safe = nome_pasta.replace("'", "\\'")
    query = (
        f"mimeType='application/vnd.google-apps.folder' "
        f"and name='{nome_safe}' "
        f"and '{parent_id}' in parents "
        f"and trashed=false"
    )
    results = drive_service.files().list(
        q=query, spaces='drive', fields='files(id, name)'
    ).execute()
    items = results.get('files', [])
    if not items:
        meta = {
            'name': nome_pasta,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
        folder = drive_service.files().create(body=meta, fields='id').execute()
        return folder.get('id')
    return items[0].get('id')

def upload_to_drive(nome_arquivo, conteudo, folder_id, drive_service):
    meta = {'name': nome_arquivo, 'parents': [folder_id]}
    media = MediaInMemoryUpload(conteudo.encode('utf-8'), mimetype='text/plain')
    drive_service.files().create(body=meta, media_body=media, fields='id').execute()

# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────
defaults = {
    "drive_service":    None,
    "drive_ok":         False,
    "drive_erro":       "",
    "pasta_cache":      {},   # {idioma_label: folder_id}
    "historico":        [],   # lista de dicts
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎬 Fábrica de Roteiros")
    st.markdown("---")

    st.markdown("**🔑 API Key**")
    gemini_key = st.text_input("Gemini API Key", type="password", label_visibility="collapsed")

    st.markdown("**📁 Pasta no Drive**")
    pasta_principal_id = st.text_input(
        "ID", value="1RH-VwGnJTj_avH2Dg3KNDthPNsSiamgp", label_visibility="collapsed"
    )

    st.markdown("**🧠 Modelo**")
    opcao_modelo = st.selectbox(
        "Modelo", ["Gemini 3.1 Pro (Preview)", "Gemini 3 Flash"], label_visibility="collapsed"
    )
    modelo_id = (
        "models/gemini-3.1-pro-preview"
        if "3.1" in opcao_modelo
        else "models/gemini-3-flash"
    )

    st.markdown("**📏 Tamanho**")
    col_a, col_b = st.columns(2)
    with col_a:
        min_chars = st.number_input("Mín.", value=2000, step=500)
    with col_b:
        target_chars = st.number_input("Alvo", value=14000, step=500)

    st.markdown("---")

    # Custo
    price_out = 12.00 / 1_000_000
    price_in  = 2.00  / 1_000_000
    custo_unit = (300 * price_in) + ((target_chars / 4) * price_out)
    st.markdown(
        f"<div style='font-size:0.8rem;color:#8e8e93'>💰 ~US$ {custo_unit:.4f} / roteiro</div>",
        unsafe_allow_html=True
    )

    st.markdown("---")

    # Conexão Drive
    st.markdown("**☁️ Google Drive**")
    if st.button("🔌 Conectar", use_container_width=True):
        st.session_state.drive_ok = False
        st.session_state.drive_erro = ""
        st.session_state.pasta_cache = {}
        try:
            creds_raw = json.loads(st.secrets["gcp_json"])
            svc = autenticar_drive(creds_raw)
            svc.files().list(pageSize=1, fields="files(id)").execute()
            st.session_state.drive_service = svc
            st.session_state.drive_ok = True
        except KeyError:
            st.session_state.drive_erro = "Secret 'gcp_json' não encontrado."
        except json.JSONDecodeError:
            st.session_state.drive_erro = "JSON inválido no secret 'gcp_json'."
        except Exception as e:
            st.session_state.drive_erro = str(e)

    if st.session_state.drive_ok:
        st.success("✅ Drive conectado")
    elif st.session_state.drive_erro:
        st.error(f"❌ {st.session_state.drive_erro}")
    else:
        st.caption("⚠️ Não conectado — só download.")

# ─────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────
st.markdown("<h1>🎬 Fábrica de Roteiros</h1>", unsafe_allow_html=True)
st.markdown(
    "<p style='color:#8e8e93;margin-top:-12px;margin-bottom:28px;font-size:0.95rem'>"
    "Geração em lote · Streaming · Drive automático</p>",
    unsafe_allow_html=True
)

tab_produzir, tab_historico = st.tabs(["✍️ Produzir", "📚 Histórico"])

# ═══════════════════════════════════════════════
# TAB 1 — PRODUZIR
# ═══════════════════════════════════════════════
with tab_produzir:
    col1, col2 = st.columns([1, 1])
    with col1:
        idioma_label = st.selectbox("Idioma", list(IDIOMAS.keys()))
        idioma_nome, pais_alvo = IDIOMAS[idioma_label]
    with col2:
        prompt_base = st.text_area(
            "Instruções de estilo",
            value="Narrador idoso sábio, texto corrido sem tópicos, "
                  "ritmo emocional, sem markdown, máxima retenção.",
            height=100,
        )

    titulos_raw = st.text_area("Títulos (um por linha)", height=140, placeholder="Cole os títulos aqui...")
    titulos = [t.strip() for t in titulos_raw.split('\n') if t.strip()]

    if titulos:
        st.caption(
            f"📋 {len(titulos)} roteiro(s) · "
            f"~US$ {custo_unit * len(titulos):.4f} estimado"
        )

    iniciar = st.button("🚀 Iniciar Produção", type="primary", use_container_width=True)

    if iniciar:
        if not gemini_key:
            st.error("Insira a Gemini API Key na sidebar.")
        elif not titulos:
            st.error("Adicione pelo menos um título.")
        else:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel(modelo_id)

            for idx, titulo in enumerate(titulos):
                st.markdown(f"---")
                st.markdown(f"**{idx+1}/{len(titulos)} · {titulo}**")

                instrucoes = (
                    f"Escreva um roteiro corrido (sem # ou * ou markdown) "
                    f"em {idioma_nome} para o país {pais_alvo}. "
                    f"Título: «{titulo}». "
                    f"Estilo: {prompt_base}. "
                    f"Alvo: {target_chars} caracteres. "
                    f"Retorne apenas o texto do roteiro, sem títulos, sem cabeçalhos."
                )

                texto_final = ""
                caixa = st.empty()
                ts_inicio = time.time()

                try:
                    res = model.generate_content(instrucoes, stream=True)
                    for chunk in res:
                        if chunk.text:
                            texto_final += chunk.text
                            caixa.markdown(
                                f"<div class='streaming-box'>{texto_final} ✍️</div>",
                                unsafe_allow_html=True
                            )

                    caixa.markdown(
                        f"<div class='streaming-box'>{texto_final}</div>",
                        unsafe_allow_html=True
                    )

                    duracao = round(time.time() - ts_inicio, 1)
                    chars = len(texto_final)
                    tem_md = "#" in texto_final or "**" in texto_final

                    # QA badges
                    badges = []
                    if chars >= min_chars and not tem_md:
                        badges.append("<span class='badge badge-ok'>✓ Aprovado</span>")
                    if chars < min_chars:
                        badges.append(f"<span class='badge badge-warn'>⚠ Curto ({chars} chars)</span>")
                    if tem_md:
                        badges.append("<span class='badge badge-err'>⚠ Markdown detectado</span>")
                    badges.append(f"<span class='badge badge-lang'>{idioma_label}</span>")
                    badges.append(f"<span class='badge' style='color:#8e8e93;border-color:rgba(255,255,255,0.1)'>{chars:,} chars · {duracao}s</span>")

                    st.markdown(" ".join(badges), unsafe_allow_html=True)

                    # Salva no histórico
                    entrada = {
                        "titulo":   titulo,
                        "idioma":   idioma_label,
                        "pais":     pais_alvo,
                        "texto":    texto_final,
                        "chars":    chars,
                        "aprovado": chars >= min_chars and not tem_md,
                        "drive":    False,
                        "ts":       datetime.now().strftime("%d/%m/%Y %H:%M"),
                    }

                    # Tenta Drive
                    nome_arq = f"{titulo[:60].replace('/', '-')}.txt"
                    if st.session_state.drive_ok:
                        try:
                            # Garante pasta do idioma
                            if idioma_label not in st.session_state.pasta_cache:
                                folder_id = obter_ou_criar_pasta(
                                    idioma_nome, pasta_principal_id,
                                    st.session_state.drive_service
                                )
                                st.session_state.pasta_cache[idioma_label] = folder_id
                            upload_to_drive(
                                nome_arq, texto_final,
                                st.session_state.pasta_cache[idioma_label],
                                st.session_state.drive_service
                            )
                            entrada["drive"] = True
                            st.success("✅ Salvo no Drive")
                        except Exception as e:
                            st.warning(f"⚠️ Drive falhou: {e}")

                    st.session_state.historico.append(entrada)

                    st.download_button(
                        "⬇️ Baixar TXT",
                        data=texto_final,
                        file_name=nome_arq,
                        key=f"dl_{idx}_{titulo[:20]}"
                    )

                except Exception as e:
                    st.error(f"Erro na geração: {e}")
                    st.session_state.historico.append({
                        "titulo": titulo, "idioma": idioma_label, "pais": pais_alvo,
                        "texto": "", "chars": 0, "aprovado": False, "drive": False,
                        "ts": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    })

            st.success(f"🏁 Lote concluído — {len(titulos)} roteiro(s) processado(s).")

# ═══════════════════════════════════════════════
# TAB 2 — HISTÓRICO
# ═══════════════════════════════════════════════
with tab_historico:
    if not st.session_state.historico:
        st.markdown(
            "<div style='text-align:center;color:#8e8e93;padding:60px 0'>"
            "<div style='font-size:3rem'>📭</div>"
            "<div style='margin-top:12px'>Nenhum roteiro gerado ainda</div>"
            "</div>",
            unsafe_allow_html=True
        )
    else:
        total = len(st.session_state.historico)
        aprovados = sum(1 for r in st.session_state.historico if r["aprovado"])
        no_drive  = sum(1 for r in st.session_state.historico if r["drive"])

        c1, c2, c3 = st.columns(3)
        c1.metric("Total", total)
        c2.metric("Aprovados", aprovados)
        c3.metric("No Drive", no_drive)

        st.markdown("---")

        # Botão apagar tudo
        col_titulo, col_apagar = st.columns([4, 1])
        with col_titulo:
            st.markdown(f"**{total} roteiro(s)**")
        with col_apagar:
            if st.button("🗑 Apagar tudo", use_container_width=True):
                st.session_state.historico = []
                st.rerun()

        # Lista de roteiros
        indices_apagar = []
        for i, r in enumerate(st.session_state.historico):
            drive_badge = (
                "<span class='badge badge-ok'>☁️ Drive</span>" if r["drive"]
                else "<span class='badge badge-warn'>⬇️ Local</span>"
            )
            qa_badge = (
                "<span class='badge badge-ok'>✓ OK</span>" if r["aprovado"]
                else "<span class='badge badge-err'>⚠ QA</span>"
            )

            preview = r["texto"][:200].replace("<", "&lt;").replace(">", "&gt;") if r["texto"] else "— erro na geração —"

            st.markdown(f"""
            <div class='roteiro-card'>
                <div class='roteiro-titulo'>{r['titulo']}</div>
                <div class='roteiro-meta'>
                    {r['idioma']} · {r['chars']:,} chars · {r['ts']}
                    &nbsp;{drive_badge} {q
