import streamlit as st

from paginas import configuracoes_pg, dashboard_pg, revisao_pg, unidades_pg, upload_pg

st.set_page_config(page_title="Solar ROI", page_icon="☀️", layout="wide")

PAGINAS = {
    "📤 Enviar faturas": upload_pg.render,
    "✅ Revisar leitura": revisao_pg.render,
    "🏠 Unidades": unidades_pg.render,
    "📊 Dashboard": dashboard_pg.render,
    "⚙️ Configurações": configuracoes_pg.render,
}

st.sidebar.title("☀️ Solar ROI")
pagina = st.sidebar.radio("Navegação", list(PAGINAS))
PAGINAS[pagina]()
