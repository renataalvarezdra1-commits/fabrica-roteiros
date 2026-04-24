import streamlit as st
import google.generativeai as genai
import requests
import json
import time
from datetime import datetime

# ─────────────────────────────────────────────
# DESIGN — Apple Sequoia Dark
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Fábrica de Roteiros Pro",
    page_icon="🎬",
    layout="wide"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@300;400;500;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'SF Pro Display', -apple-system, sans-serif;
        background-color: #1c1c1e;
        color: #f5f5f7;
    }
    
    .stApp { background: #1c1c1e; }
    
    /* Streaming Box */
    .streaming-box {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(10, 132, 255, 0.3);
        border-radius: 12px;
        padding: 20px;
        font-size: 0.95rem;
        line-height: 1.6;
        color: #e5e5ea;
        white-space: pre-wrap;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] { background: #161617; border-right: 1px solid #333; }
    
    /* Buttons */
    .stButton>button {
        border-radius: 8px;
        font-weight: 500;
        transition: 0.2s;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# CONFIGURAÇÕES E MAPAS
# ─────────────────────────────────────────────
IDIOMAS_MAP = {
    "Francês": "FR", "Português": "PT", "Croata": "HR", 
    "Inglês": "EN", "Sérvio": "SR", "Espanhol": "ES", "Alemão": "DE"
}

# ─────────────────────────────────────────────
# FUNÇÃO AIRTABLE
# ─────────────────────────────────────────────
def salvar_no_airtable(token, base_id, table_name, dados):
    url = f"https://api.airtable.com/v0/{base_id}/{table_name}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {"records": [{"fields": dados}]}
    response = requests.post(url, headers=headers, json=payload)
    return response.status_code == 200

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.title("🎬 Configurações")
    
    st.header("🔑 Conectividade")
    gemini_key = st.text_input("Gemini API Key", type="password")
    airtable_token = st.text_input("Airtable Access Token", value="PatA2VZHkIf8LEPM5.cc750f2f807f7504960653c22af51f66b015bc8593e5f518883726f7bea3c9c4", type="password")
    airtable_base_id = st.text_input("Airtable Base ID", value="appVpY8rPjE1XlH0e") # Extraído do link ou preencher
    airtable_table = st.text_input("Nome da Tabela", value="Roteiros Produção")

    st.header("🧠 Inteligência")
    modelo_id = st.selectbox("Versão do Motor", ["models/gemini-3.1-pro-preview", "models/gemini-3-flash"])
    
    st.header("📏 Parâmetros")
    target_chars = st.number_input("Alvo de Caracteres", value=3500)
    
    st.divider()
    st.caption("Fábrica de Roteiros v3.3 - 2026")

# ─────────────────────────────────────────────
# ÁREA DE PRODUÇÃO
# ─────────────────────────────────────────────
st.title("🚀 Produção Internacional")

col_id, col_ciclo, col_ang = st.columns(3)

with col_id:
    idioma_sel = st.selectbox("Idioma do Lote", list(IDIOMAS_MAP.keys()))
    prefixo_idioma = IDIOMAS_MAP[idioma_sel]

with col_ciclo:
    ciclo = st.number_input("Ciclo (C)", min_value=1, value=1, format="%02d")

with col_ang:
    angulo = st.number_input("Ângulo (A)", min_value=1, value=1, format="%02d")

prompt_estilo = st.text_area("Instruções de Estilo", "Narrador sábio, tom emocional, sem tópicos, focado em retenção.")
titulos_raw = st.text_area("Títulos dos Vídeos (Um por linha)", height=150, placeholder="Ex: A sabedoria do silêncio")

# ─────────────────────────────────────────────
# EXECUÇÃO
# ─────────────────────────────────────────────
if st.button("🚀 INICIAR FÁBRICA", type="primary", use_container_width=True):
    if not gemini_key or not titulos_raw:
        st.error("Por favor, preencha a chave Gemini e os títulos.")
    else:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel(modelo_id)
        
        titulos = [t.strip() for t in titulos_raw.split('\n') if t.strip()]
        
        for idx, t in enumerate(titulos):
            # Gerar ID Automático: FR01C02A02
            # Idioma + Indice do vídeo no lote + Ciclo + Angulo
            video_num = f"{idx+1:02d}"
            custom_id = f"{prefixo_idioma}{video_num}C{ciclo:02d}A{angulo:02d}"
            
            st.markdown(f"### 🎞️ Processando: `{custom_id}` - {t}")
            
            instrucoes = f"""
            Escreva um roteiro de vídeo longo em {idioma_sel}.
            REGRAS: 
            1. Use APENAS texto corrido (sem markdown, sem #, sem *).
            2. Alvo: {target_chars} caracteres.
            3. Estilo: {prompt_estilo}.
            4. Título do vídeo: {t}.
            Retorne apenas a narração.
            """
            
            texto_final = ""
            caixa_streaming = st.empty()
            
            try:
                # Streaming na tela
                response = model.generate_content(instrucoes, stream=True)
                for chunk in response:
                    texto_final += chunk.text
                    caixa_streaming.markdown(f"<div class='streaming-box'>{texto_final}✍️</div>", unsafe_allow_html=True)
                
                caixa_streaming.markdown(f"<div class='streaming-box'>{texto_final}</div>", unsafe_allow_html=True)
                
                # Salvar no Airtable
                dados_airtable = {
                    "ID": custom_id,
                    "Título": t,
                    "Roteiro": texto_final,
                    "Idioma": idioma_sel,
                    "Data": datetime.now().strftime("%Y-%m-%d")
                }
                
                if salvar_no_airtable(airtable_token, airtable_base_id, airtable_table, dados_airtable):
                    st.success(f"✅ Roteiro `{custom_id}` enviado para o Airtable com sucesso!")
                else:
                    st.error(f"❌ Erro ao enviar `{custom_id}` para o Airtable. Verifique o Base ID e nomes das colunas.")
                
                st.download_button(f"⬇️ Baixar Local: {custom_id}", texto_final, f"{custom_id}.txt", key=custom_id)
                
            except Exception as e:
                st.error(f"Erro na geração do vídeo {t}: {e}")
            
            st.divider()

        st.balloons()
        st.success("🏁 Lote de produção finalizado!")
