import streamlit as st
import google.generativeai as genai
import requests
from datetime import datetime

# ─────────────────────────────────────────────
# DESIGN
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
# CREDENCIAIS
# ─────────────────────────────────────────────
GEMINI_API_KEY = "AIzaSyAgQCZg-qs20vQjxJKzP1Pixfy9J5CYHdI"
AIRTABLE_TOKEN = "patA2VZHkIf8LEPM5.cc750f2f807f7504960653c22af51f66b015bc8593e5f518883726f7bea3c9c4"
AIRTABLE_BASE_ID = "appIOOSIJlPk8IcNe"
AIRTABLE_TABLE_ID = "tblN4RYIPzQfjNEhi"

# ─────────────────────────────────────────────
# MAPA DE MODELOS ATUALIZADO (Abril 2026)
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
# FUNÇÕES
# ─────────────────────────────────────────────
def salvar_no_airtable(dados):
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
        elif response.status_code == 401:
            st.error("❌ Token Airtable inválido.")
        elif response.status_code == 403:
            st.error("❌ Sem permissão de escrita no Airtable.")
        else:
            st.error(f"Erro Airtable ({response.status_code}): {response.text[:200]}")
        return False
    except Exception as e:
        st.error(f"Erro de conexão Airtable: {e}")
        return False

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎬 Configurações")
    st.success("✅ Credenciais carregadas")
    
    st.markdown("**🧠 Modelo Gemini**")
    opcao_modelo = st.selectbox("Versão:", list(mapa_modelos.keys()))
    modelo_id = mapa_modelos[opcao_modelo]

    st.markdown("**📏 Tamanho**")
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

prompt_base = st.text_area("Estilo do Narrador", "Narrador sábio, tom emocional, sem tópicos, máxima retenção.", height=100)
titulos_raw = st.text_area("Títulos (um por linha)", height=180)
titulos = [t.strip() for t in titulos_raw.split('\n') if t.strip()]

if st.button("🚀 INICIAR FÁBRICA", type="primary", use_container_width=True):
    if not titulos:
        st.error("Insira pelo menos um título.")
        st.stop()

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(modelo_id)
        st.success(f"✅ Usando: **{opcao_modelo}**")
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

            # Airtable
            dados = {
                "ID": custom_id,
                "Título": t,
                "Roteiro": texto_final,
                "Idioma": idioma_sel,
                "Data": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            
            if salvar_no_airtable(dados):
                st.success(f"✅ `{custom_id}` salvo no Airtable!")
            
            st.download_button(f"⬇️ Baixar {custom_id}.txt", texto_final, f"{custom_id}.txt", key=custom_id)

        except Exception as e:
            st.error(f"Erro ao gerar `{custom_id}`: {str(e)}")
