import streamlit as st

from paginas import (
    composicao_pg, configuracoes_pg, dashboard_pg, nova_usina_pg, rateio_pg, revisao_pg, simulador_pg, unidades_pg, upload_pg,
    vencimentos_pg,
)
from solar import backup, configuracoes

st.set_page_config(
    page_title="Solar ROI",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="auto",
)


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

with st.sidebar:
    st.markdown("### ☀️ Solar ROI")
    st.caption("Gestão & Retorno Fotovoltaico")

paginas = {
    "Operações": [
        st.Page(upload_pg.render, title="Enviar faturas", icon=":material/upload_file:"),
        st.Page(revisao_pg.render, title="Revisar leitura", icon=":material/fact_check:"),
        st.Page(rateio_pg.render, title="Rateio de créditos", icon=":material/swap_horiz:"),
    ],
    "Visão Geral": [
        st.Page(dashboard_pg.render, title="Dashboard", icon=":material/dashboard:"),
        st.Page(composicao_pg.render, title="Composição da conta", icon=":material/pie_chart:"),
        st.Page(unidades_pg.render, title="Unidades", icon=":material/home:"),
        st.Page(vencimentos_pg.render, title="Vencimentos", icon=":material/calendar_month:"),
    ],
    "Planejamento": [
        st.Page(simulador_pg.render, title="Simulador", icon=":material/calculate:"),
        st.Page(nova_usina_pg.render, title="Nova usina", icon=":material/solar_power:"),
    ],
    "Sistema": [
        st.Page(configuracoes_pg.render, title="Configurações", icon=":material/settings:"),
    ],
}

nav = st.navigation(paginas, position="sidebar", expanded=True)
nav.run()
