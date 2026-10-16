import streamlit as st

from paginas import (
    composicao_pg, configuracoes_pg, dashboard_pg, rateio_pg, revisao_pg, simulador_pg, unidades_pg, upload_pg,
    vencimentos_pg,
)
from solar import backup, configuracoes

st.set_page_config(page_title="Solar ROI", page_icon="☀️", layout="wide")

PAGINAS = {
    "📤 Enviar faturas": upload_pg.render,
    "✅ Revisar leitura": revisao_pg.render,
    "🏠 Unidades": unidades_pg.render,
    "📊 Dashboard": dashboard_pg.render,
    "💸 Composição da conta": composicao_pg.render,
    "🔁 Rateio de créditos": rateio_pg.render,
    "🏦 Simulador": simulador_pg.render,
    "📅 Vencimentos": vencimentos_pg.render,
    "⚙️ Configurações": configuracoes_pg.render,
}


def _backup_automatico() -> None:
    """Uma vez por sessão: se o último backup tem mais de uma semana, faz outro."""
    if st.session_state.get("backup_verificado"):
        return
    st.session_state["backup_verificado"] = True
    try:
        backup.backup_automatico_se_necessario(configuracoes.carregar().pasta_backup or None)
    except OSError as erro:
        st.sidebar.warning(f"Não consegui fazer o backup automático: {erro}. Confira a pasta em Configurações.")


_backup_automatico()
st.sidebar.title("☀️ Solar ROI")
pagina = st.sidebar.radio("Navegação", list(PAGINAS))
PAGINAS[pagina]()
