import streamlit as st
import google.generativeai as genai
import requests
from datetime import datetime

# ─────────────────────────────────────────────
# DESIGN — Apple Sequoia
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Fábrica de Roteiros Pro",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@300;400;500;600&display=swap');
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
    background-color: #1c1c1e;
    color: #f5f5f7;
}
.stApp { background: linear-gradient(160deg, #1c1c1e 0%, #2c2c2e 50%, #1c1c1e 100%); min-height: 100vh; }
[data-testid="stSidebar"] { background: rgba(28, 28, 30, 0.85); backdrop-filter: blur(20px); border-right: 1px solid rgba(255,255,255,0.08); }
h1 { font-size: 2rem !important; font-weight: 600 !important; letter-spacing: -0.02em !important; color: #f5f5f7 !important; }
.streaming-box {
    background: rgba(28,28,30,0.9);
    border: 1px solid rgba(10,132,255,0.3);
    border-radius: 14px;
    padding: 18px 22px;
    font-size: 0.88rem;
    line-height: 1.65;
    color: #e5e5ea;
    max-height: 420px;
    overflow-y: auto;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# CONFIGURAÇÕES (CREDENCIAIS)
# ─────────────────────────────────────────────
st.sidebar.markdown("### 🔑 Credenciais")

GEMINI_API_KEY = st.sidebar.text_input(
    "Gemini API Key", 
    type="password",
    value="",  # Deixe vazio - você insere aqui
    help="Cole sua chave do Google Gemini"
)

AIRTABLE_TOKEN = st.sidebar.text_input(
    "Airtable Token (PAT)", 
    type="password",
    value="",  # Deixe vazio
    help="Personal Access Token do Airtable"
)

AIRTABLE_BASE_ID = st.sidebar.text_input(
    "Airtable Base ID", 
    value="appIOOSIJlPk8IcNe",
    help="ID da sua Base"
)

AIRTABLE_TABLE_ID = st.sidebar.text_input(
    "Airtable Table ID", 
    value="tblN4RYIPzQfjNEhi",
    help="ID da tabela"
)

# ─────────────────────────────────────────────
# MAPA DE MODELOS (Atualizado 2026)
# ─────────────────────────────────────────────
IDIOMAS = {
    "Francês": ("Francês", "FR"), "Português": ("Português", "PT"), "Croata": ("Croata", "HR"),
    "Inglês": ("Inglês", "EN"), "Sérvio": ("Sérvio", "SR"), "Espanhol": ("Espanhol", "ES"),
    "Alemão": ("Alemão", "DE"), "Japonês": ("Japonês", "JP"), "Coreano": ("Coreano", "KR")
}

mapa_modelos = {
    "Gemini 3.1 Pro Preview (Recomendado)": "gemini-3.1-pro-preview",
    "Gemini 3 Flash Preview": "gemini-3-flash-preview",
    "Gemini 2.5 Pro (Fallback)": "gemini-2.5-pro",
}

# ─────────────────────────────────────────────
# FUNÇÃO AIRTABLE
# ─────────────────────────────────────────────
def salvar_no_airtable(dados):
    if not AIRTABLE_TOKEN or not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_ID:
        st.error("❌ Preencha as credenciais do Airtable na barra lateral.")
        return False
    
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {"records": [{"fields": dados}]}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            return True
        else:
            st.error(f"Erro Airtable ({response.status_code}): {response.text[:300]}")
            return False
    except Exception as e:
        st.error(f"Erro de conexão Airtable: {e}")
        return False

# ─────────────────────────────────────────────
# SIDEBAR - Configurações
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🧠 Configurações da Geração")
    opcao_modelo = st.selectbox("Modelo Gemini:", list(mapa_modelos.keys()))
    modelo_id = mapa_modelos[opcao_modelo]

    target_chars = st.number_input("Alvo de Caracteres", value=3500, step=500)

# ─────────────────────────────────────────────
# ÁREA PRINCIPAL
# ─────────────────────────────────────────────
st.markdown("<h1>🎬 Fábrica de Roteiros Pro</h1>", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
with col1:
    idioma_sel = st.selectbox("Idioma", list(IDIOMAS.keys()))
    idioma_nome, prefixo_idioma = IDIOMAS[idioma_sel]
with col2:
    ciclo = st.number_input("Ciclo (C)", min_value=1, value=1, format="%02d")
with col3:
    angulo = st.number_input("Ângulo (A)", min_value=1, value=1, format="%02d")

prompt_base = st.text_area("Estilo do Narrador", 
                          "Narrador sábio, tom emocional, sem tópicos, máxima retenção.", 
                          height=100)
titulos_raw = st.text_area("Títulos (um por linha)", height=180)
titulos = [t.strip() for t in titulos_raw.split('\n') if t.strip()]

if st.button("🚀 INICIAR FÁBRICA", type="primary", use_container_width=True):
    if not GEMINI_API_KEY:
        st.error("❌ Insira a Gemini API Key na barra lateral.")
        st.stop()
    if not titulos:
        st.error("❌ Insira pelo menos um título.")
        st.stop()

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(modelo_id)
        st.success(f"✅ Modelo carregado: **{opcao_modelo}**")
    except Exception as e:
        st.error(f"Erro ao conectar com Gemini: {e}")
        st.stop()

    for idx, t in enumerate(titulos):
        custom_id = f"{prefixo_idioma}{idx+1:02d}C{ciclo:02d}A{angulo:02d}"
        
        st.markdown("---")
        st.markdown(f"### 🎞️ Processando: `{custom_id}` — {t}")

        instrucoes = f"""
        Escreva um roteiro corrido (sem markdown, sem # ou *) em {idioma_nome}.
        Título: «{t}».
        Estilo: {prompt_base}.
        Alvo aproximado: {target_chars} caracteres.
        Retorne APENAS o texto da narração.
        """

        texto_final = ""
        caixa_streaming = st.empty()

        try:
            res = model.generate_content(instrucoes, stream=True)
            for chunk in res:
                if chunk.text:
                    texto_final += chunk.text
                    caixa_streaming.markdown(f"<div class='streaming-box'>{texto_final} ✍️</div>", unsafe_allow_html=True)
            
            caixa_streaming.markdown(f"<div class='streaming-box'>{texto_final}</div>", unsafe_allow_html=True)

            # Dados para Airtable
            dados = {
                "ID": custom_id,
                "Título": t,
                "Roteiro": texto_final,
                "Idioma": idioma_sel,
                "Data": datetime.now().strftime("%Y-%m-%d")
            }
            
            if salvar_no_airtable(dados):
                st.success(f"✅ `{custom_id}` salvo no Airtable!")
            
            st.download_button(
                label=f"⬇️ Baixar {custom_id}.txt",
                data=texto_final,
                file_name=f"{custom_id}.txt",
                mime="text/plain",
                key=f"download_{idx}"
            )

        except Exception as e:
            st.error(f"Erro ao gerar `{custom_id}`: {str(e)}")             
