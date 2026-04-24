import streamlit as st
import google.generativeai as genai
import requests
import json
import time
from datetime import datetime

# ─────────────────────────────────────────────
# DESIGN — Apple Sequoia Dark
# ─────────────────────────────────────────────
st.set_page_config(page_title="Fábrica de Roteiros Pro v3.4", page_icon="🎬", layout="wide")

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
        margin-bottom: 10px;
    }
    .error-box {
        background-color: rgba(255, 75, 75, 0.1);
        border: 1px solid #ff4b4b;
        border-radius: 8px;
        padding: 15px;
        color: #ff4b4b;
        font-family: monospace;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# FUNÇÃO AIRTABLE COM DIAGNÓSTICO DETALHADO
# ─────────────────────────────────────────────
def salvar_no_airtable(token, base_id, table_id, dados):
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {"records": [{"fields": dados}]}
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            return True, "Sucesso"
        else:
            # Captura o erro detalhado do Airtable
            error_info = response.json().get('error', {})
            error_msg = f"Status {response.status_code}: {error_info.get('type')} - {error_info.get('message')}"
            
            # Se o erro for de campo desconhecido, tentamos listar quais campos causaram o erro
            if "UNKNOWN_FIELD_NAME" in error_msg:
                error_msg += "\n\nVerifique se os nomes das colunas no Airtable estão IGUAIS ao código (ID, Título, Roteiro, Idioma, Data)."
            
            return False, error_msg
            
    except Exception as e:
        return False, f"Falha na conexão: {str(e)}"

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.title("🎬 Configurações")
    gemini_key = st.text_input("Gemini API Key", type="password")
    
    st.markdown("---")
    st.subheader("🔌 Airtable Connection")
    airtable_token = st.text_input("Access Token", value="PatA2VZHkIf8LEPM5.cc750f2f807f7504960653c22af51f66b015bc8593e5f518883726f7bea3c9c4", type="password")
    airtable_base_id = st.text_input("Base ID", value="appIOOSIJlPk8IcNe")
    airtable_table_id = st.text_input("Table ID", value="tblN4RYIPzQfjNEhi")

    st.markdown("---")
    modelo_id = st.selectbox("Motor Gemini", ["models/gemini-3.1-pro-preview", "models/gemini-3-flash"])
    target_chars = st.number_input("Alvo de Caracteres", value=3500)

# ─────────────────────────────────────────────
# ÁREA DE PRODUÇÃO
# ─────────────────────────────────────────────
st.title("🚀 Produção em Lote Internacional")

IDIOMAS_MAP = {"Francês": "FR", "Português": "PT", "Croata": "HR", "Inglês": "EN", "Sérvio": "SR", "Espanhol": "ES", "Alemão": "DE"}

col_id, col_ciclo, col_ang = st.columns(3)
with col_id:
    idioma_sel = st.selectbox("Idioma", list(IDIOMAS_MAP.keys()))
    prefixo_idioma = IDIOMAS_MAP[idioma_sel]
with col_ciclo:
    ciclo = st.number_input("Ciclo (C)", min_value=1, value=1, format="%02d")
with col_ang:
    angulo = st.number_input("Ângulo (A)", min_value=1, value=1, format="%02d")

prompt_estilo = st.text_area("Estilo Narrativo", "Narrador sábio, tom emocional, sem tópicos, foco em retenção.")
titulos_raw = st.text_area("Lista de Títulos (um por linha)", height=150)

# ─────────────────────────────────────────────
# LOGICA DE EXECUÇÃO
# ─────────────────────────────────────────────
if st.button("🚀 INICIAR FÁBRICA", type="primary", use_container_width=True):
    if not gemini_key or not titulos_raw:
        st.error("Preencha a chave Gemini e forneça os títulos.")
    else:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel(modelo_id)
        titulos = [t.strip() for t in titulos_raw.split('\n') if t.strip()]
        
        for idx, t in enumerate(titulos):
            # Formatação do ID customizado
            video_num = idx + 1
            custom_id = f"{prefixo_idioma}{video_num:02d}C{ciclo:02d}A{angulo:02d}"
            
            st.markdown(f"### 🎞️ Vídeo: `{custom_id}`")
            
            texto_final = ""
            caixa_streaming = st.empty()
            
            try:
                # Prompt de geração
                prompt = (f"Escreva um roteiro longo em {idioma_sel}. "
                          f"Use APENAS texto corrido, sem markdown, sem hashtags. "
                          f"Título: {t}. Estilo: {prompt_estilo}. Alvo: {target_chars} caracteres.")
                
                response = model.generate_content(prompt, stream=True)
                
                for chunk in response:
                    texto_final += chunk.text
                    caixa_streaming.markdown(f"<div class='streaming-box'>{texto_final}✍️</div>", unsafe_allow_html=True)
                
                caixa_streaming.markdown(f"<div class='streaming-box'>{texto_final}</div>", unsafe_allow_html=True)
                
                # Preparação dos dados para o Airtable
                # NOTA: Os nomes à esquerda DEVEM ser idênticos aos do Airtable
                dados = {
                    "ID": custom_id,
                    "Título": t,
                    "Roteiro": texto_final,
                    "Idioma": idioma_sel,
                    "Data": datetime.now().strftime("%Y-%m-%d")
                }
                
                # Tentativa de salvamento
                sucesso, mensagem = salvar_no_airtable(airtable_token, airtable_base_id, airtable_table_id, dados)
                
                if sucesso:
                    st.success(f"✅ `{custom_id}` enviado com sucesso!")
                else:
                    st.markdown(f"""<div class="error-box">
                    <b>❌ FALHA NO ENVIO ({custom_id})</b><br>
                    {mensagem}
                    </div>""", unsafe_allow_html=True)
                
                st.download_button(f"⬇️ Baixar {custom_id}", texto_final, f"{custom_id}.txt", key=custom_id)
                
            except Exception as e:
                st.error(f"Erro no processamento do vídeo {idx+1}: {e}")
            
            st.divider()
            time.sleep(1) # Pequena pausa para evitar bloqueio da API

        st.balloons()
                
