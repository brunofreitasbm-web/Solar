import streamlit as st

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


def _page_upload() -> None:
    from paginas import upload_pg
    upload_pg.render()


def _page_revisao() -> None:
    from paginas import revisao_pg
    revisao_pg.render()


def _page_rateio() -> None:
    from paginas import rateio_pg
    rateio_pg.render()


def _page_dashboard() -> None:
    from paginas import dashboard_pg
    dashboard_pg.render()


def _page_composicao() -> None:
    from paginas import composicao_pg
    composicao_pg.render()


def _page_unidades() -> None:
    from paginas import unidades_pg
    unidades_pg.render()


def _page_vencimentos() -> None:
    from paginas import vencimentos_pg
    vencimentos_pg.render()


def _page_simulador() -> None:
    from paginas import simulador_pg
    simulador_pg.render()


def _page_nova_usina() -> None:
    from paginas import nova_usina_pg
    nova_usina_pg.render()


def _page_configuracoes() -> None:
    from paginas import configuracoes_pg
    configuracoes_pg.render()


paginas = {
    "Operações": [
        st.Page(_page_upload, title="Enviar faturas", icon=":material/upload_file:", url_path="enviar-faturas"),
        st.Page(_page_revisao, title="Revisar leitura", icon=":material/fact_check:", url_path="revisar-leitura"),
        st.Page(_page_rateio, title="Rateio de créditos", icon=":material/swap_horiz:", url_path="rateio-creditos"),
    ],
    "Visão Geral": [
        st.Page(_page_dashboard, title="Dashboard", icon=":material/dashboard:", url_path="dashboard", default=True),
        st.Page(_page_composicao, title="Composição da conta", icon=":material/pie_chart:", url_path="composicao-conta"),
        st.Page(_page_unidades, title="Unidades", icon=":material/home:", url_path="unidades"),
        st.Page(_page_vencimentos, title="Vencimentos", icon=":material/calendar_month:", url_path="vencimentos"),
    ],
    "Planejamento": [
        st.Page(_page_simulador, title="Simulador", icon=":material/calculate:", url_path="simulador"),
        st.Page(_page_nova_usina, title="Nova usina", icon=":material/solar_power:", url_path="nova-usina"),
    ],
    "Sistema": [
        st.Page(_page_configuracoes, title="Configurações", icon=":material/settings:", url_path="configuracoes"),
    ],
}

nav = st.navigation(paginas, position="sidebar", expanded=True)
nav.run()
