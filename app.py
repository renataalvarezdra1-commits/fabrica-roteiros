import streamlit as st
import google.generativeai as genai
import requests
import json
import time
from datetime import datetime

# ─────────────────────────────────────────────
# DESIGN — Apple Sequoia Dark
# ─────────────────────────────────────────────
st.set_page_config(page_title="Fábrica de Roteiros Pro v3.5", page_icon="🎬", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@300;400;500;600&display=swap');
    html, body, [class*="css"] { font-family: 'SF Pro Display', sans-serif; background-color: #1c1c1e; color: #f5f5f7; }
    .stApp { background: #1c1c1e; }
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
    .error-box {
        background-color: rgba(255, 75, 75, 0.1);
        border: 1px solid #ff4b4b;
        border-radius: 8px;
        padding: 15px;
        color: #ff4b4b;
        font-family: monospace;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# FUNÇÃO AIRTABLE — VERSÃO BLINDADA
# ─────────────────────────────────────────────
def salvar_no_airtable(token, base_id, table_id, dados):
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    
    # Limpeza profunda do token (remove espaços, tabs e quebras de linha)
    token_limpo = "".join(token.split())
    
    headers = {
        "Authorization": f"Bearer {token_limpo}",
        "Content-Type": "application/json"
    }
    
    payload = {"records": [{"fields": dados}]}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            return True, "Sucesso"
        else:
            try:
                msg_erro = response.json().get('error', {}).get('message', response.text)
            except:
                msg_erro = response.text
            return False, f"Status {response.status_code}: {msg_erro}"
            
    except Exception as e:
        return False, f"Erro de conexão: {str(e)}"

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.title("🎬 Configurações")
    gemini_key = st.text_input("Gemini API Key", type="password")
    
    st.markdown("---")
    st.subheader("🔌 Airtable Connection")
    # Token inserido conforme enviado, mas com limpeza automática no envio
    airtable_token = st.text_input("Access Token", value="PatA2VZHkIf8LEPM5.cc750f2f807f7504960653c22af51f66b015bc8593e5f518883726f7bea3c9c4", type="password")
    airtable_base_id = st.text_input("Base ID", value="appIOOSIJlPk8IcNe")
    airtable_table_id = st.text_input("Table ID", value="tblN4RYIPzQfjNEhi")

    modelo_id = st.selectbox("Motor Gemini", ["models/gemini-3.1-pro-preview", "models/gemini-3-flash"])
    target_chars = st.number_input("Alvo de Caracteres", value=3500)

# ─────────────────────────────────────────────
# ÁREA DE PRODUÇÃO
# ─────────────────────────────────────────────
st.title("🚀 Produção em Lote")

IDIOMAS_MAP = {
    "Francês": "FR", "Português": "PT", "Croata": "HR", 
    "Inglês": "EN", "Sérvio": "SR", "Espanhol": "ES", "Alemão": "DE"
}

col_id, col_ciclo, col_ang = st.columns(3)
with col_id:
    idioma_sel = st.selectbox("Idioma", list(IDIOMAS_MAP.keys()))
with col_ciclo:
    ciclo = st.number_input("Ciclo (C)", min_value=1, value=1, format="%02d")
with col_ang:
    angulo = st.number_input("Ângulo (A)", min_value=1, value=1, format="%02d")

prompt_estilo = st.text_area("Estilo Narrativo", "Narrador sábio, tom emocional, sem tópicos.")
titulos_raw = st.text_area("Lista de Títulos (um por linha)", height=150)

if st.button("🚀 INICIAR FÁBRICA", type="primary", use_container_width=True):
    if not gemini_key or not titulos_raw:
        st.error("Preencha a chave Gemini e os títulos.")
    else:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel(modelo_id)
        titulos = [t.strip() for t in titulos_raw.split('\n') if t.strip()]
        
        for idx, t in enumerate(titulos):
            # Formatação do ID: FR01C01A01
            custom_id = f"{IDIOMAS_MAP[idioma_sel]}{idx+1:02d}C{ciclo:02d}A{angulo:02d}"
            
            st.markdown(f"### 🎞️ Vídeo: `{custom_id}`")
            
            texto_final = ""
            caixa_streaming = st.empty()
            
            try:
                # Prompt direto
                prompt = (f"Escreva um roteiro longo em {idioma_sel}. "
                          f"Use APENAS texto corrido, sem markdown. "
                          f"Título: {t}. Estilo: {prompt_estilo}. Alvo: {target_chars} caracteres.")
                
                response = model.generate_content(prompt, stream=True)
                for chunk in response:
                    texto_final += chunk.text
                    caixa_streaming.markdown(f"<div class='streaming-box'>{texto_final}✍️</div>", unsafe_allow_html=True)
                
                caixa_streaming.markdown(f"<div class='streaming-box'>{texto_final}</div>", unsafe_allow_html=True)
                
                # Dados para Airtable
                dados = {
                    "ID": custom_id,
                    "Título": t,
                    "Roteiro": texto_final,
                    "Idioma": idioma_sel,
                    "Data": datetime.now().strftime("%Y-%m-%d")
                }
                
                # Salvamento
                sucesso, mensagem = salvar_no_airtable(airtable_token, airtable_base_id, airtable_table_id, dados)
                
                if sucesso:
                    st.success(f"✅ `{custom_id}` enviado ao Airtable!")
                else:
                    st.markdown(f'<div class="error-box"><b>❌ ERRO AIRTABLE</b><br>{mensagem}</div>', unsafe_allow_html=True)
                
                st.download_button(f"⬇️ Baixar {custom_id}", texto_final, f"{custom_id}.txt", key=f"dl_{custom_id}")
                
            except Exception as e:
                st.error(f"Erro: {e}")
            st.divider()

        st.balloons()
