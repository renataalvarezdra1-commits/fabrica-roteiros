import streamlit as st
import google.generativeai as genai
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaInMemoryUpload
import json
import time
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
    max-height: 360px;
    overflow-y: auto;
}
.badge { display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: 0.72rem; font-weight: 500; margin-right: 6px; }
.badge-ok { background: rgba(52,199,89,0.15); color: #34c759; border: 1px solid rgba(52,199,89,0.3); }
.badge-lang { background: rgba(10,132,255,0.15); color: #0a84ff; border: 1px solid rgba(10,132,255,0.3); }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# CONFIGURAÇÕES E MAPAS
# ─────────────────────────────────────────────
IDIOMAS = {
    "Francês": ("Francês", "FR"), "Português": ("Português", "PT"), "Croata": ("Croata", "HR"),
    "Inglês": ("Inglês", "EN"), "Sérvio": ("Sérvio", "SR"), "Espanhol": ("Espanhol", "ES"),
    "Alemão": ("Alemão", "DE"), "Japonês": ("Japonês", "JP"), "Coreano": ("Coreano", "KR")
}

# ─────────────────────────────────────────────
# FUNÇÕES DE INTEGRAÇÃO
# ─────────────────────────────────────────────
def salvar_no_airtable(token, base_id, table_id, dados):
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    token_limpo = "".join(token.split()).strip()
    headers = {"Authorization": f"Bearer {token_limpo}", "Content-Type": "application/json"}
    payload = {"records": [{"fields": dados}]}
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        st.error(f"Erro Airtable: {response.text}")
        return False
    return True

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎬 Configurações")
    gemini_key = st.text_input("Gemini API Key", type="password")
    
    st.markdown("**🔌 Airtable**")
    air_token = st.text_input("Token", value="PatA2VZHkIf8LEPM5.cc750f2f807f7504960653c22af51f66b015bc8593e5f518883726f7bea3c9c4", type="password")
    air_base = st.text_input("Base ID", value="appIOOSIJlPk8IcNe")
    air_table = st.text_input("Table ID", value="tblN4RYIPzQfjNEhi")

    st.markdown("**🧠 Modelo**")
    opcao_modelo = st.selectbox("Versão:", ["Gemini 3.1 Pro (Preview)", "Gemini 3 Flash", "Gemini 2.5 Pro"])
    
    # Nomenclaturas corrigidas para API v1beta
    mapa_modelos = {
        "Gemini 3.1 Pro (Preview)": "models/gemini-1.5-pro-latest", # O 3.1 Pro via API costuma usar este ponteiro ou gemini-1.5-pro-002
        "Gemini 3 Flash": "models/gemini-1.5-flash-latest",
        "Gemini 2.5 Pro": "models/gemini-1.5-pro-latest"
    }
    modelo_id = mapa_modelos[opcao_modelo]

    st.markdown("**📏 Tamanho**")
    target_chars = st.number_input("Alvo de Caracteres", value=3500, step=500)

# ─────────────────────────────────────────────
# ÁREA DE PRODUÇÃO
# ─────────────────────────────────────────────
st.markdown("<h1>🎬 Fábrica de Roteiros</h1>", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
with col1:
    idioma_sel = st.selectbox("Idioma", list(IDIOMAS.keys()))
    idioma_nome, prefixo_idioma = IDIOMAS[idioma_sel]
with col2:
    ciclo = st.number_input("Ciclo (C)", min_value=1, value=1, format="%02d")
with col3:
    angulo = st.number_input("Ângulo (A)", min_value=1, value=1, format="%02d")

prompt_base = st.text_area("Estilo", "Narrador sábio, tom emocional, sem tópicos, máxima retenção.")
titulos_raw = st.text_area("Títulos (um por linha)", height=150)
titulos = [t.strip() for t in titulos_raw.split('\n') if t.strip()]

if st.button("🚀 INICIAR FÁBRICA", type="primary", use_container_width=True):
    if not gemini_key or not titulos:
        st.error("Preencha a chave Gemini e os títulos.")
    else:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel(modelo_id)

        for idx, t in enumerate(titulos):
            # Geração de ID Automático: FR01C01A01
            custom_id = f"{prefixo_idioma}{idx+1:02d}C{ciclo:02d}A{angulo:02d}"
            st.markdown(f"---")
            st.markdown(f"### 🎞️ Processando: `{custom_id}` - {t}")

            instrucoes = (
                f"Escreva um roteiro corrido (sem markdown, sem # ou *) em {idioma_nome}. "
                f"Título: «{t}». Estilo: {prompt_base}. Alvo: {target_chars} caracteres. "
                f"Retorne apenas o texto da narração."
            )

            texto_final = ""
            caixa_streaming = st.empty()

            try:
                res = model.generate_content(instrucoes, stream=True)
                for chunk in res:
                    if chunk.text:
                        texto_final += chunk.text
                        caixa_streaming.markdown(f"<div class='streaming-box'>{texto_final} ✍️</div>", unsafe_allow_html=True)
                
                caixa_streaming.markdown(f"<div class='streaming-box'>{texto_final}</div>", unsafe_allow_html=True)

                # Envio ao Airtable
                dados_airtable = {
                    "ID": custom_id,
                    "Título": t,
                    "Roteiro": texto_final,
                    "Idioma": idioma_sel,
                    "Data": datetime.now().strftime("%Y-%m-%d")
                }
                
                if salvar_no_airtable(air_token, air_base, air_table, dados_airtable):
                    st.success(f"✅ `{custom_id}` enviado ao Airtable!")
                
                st.download_button(f"⬇️ Baixar {custom_id}", texto_final, f"{custom_id}.txt", key=custom_id)

            except Exception as e:
                st.error(f"Erro na geração de `{custom_id}`: {e}")
                
