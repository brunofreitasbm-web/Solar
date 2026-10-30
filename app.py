from pathlib import Path

import streamlit as st

from paginas import navegacao, painel_dados, ui
from solar import backup, configuracoes
from solar.loggers import agendador

ASSETS = Path(__file__).parent / "assets"

st.set_page_config(
    page_title="Solar ROI",
    page_icon=":material/solar_power:",
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


def _barra_lateral() -> None:
    st.logo(str(ASSETS / "logo.svg"), icon_image=str(ASSETS / "icone.svg"), size="large")
    with st.sidebar:
        lista = painel_dados.alertas_atuais(painel_dados.carregar())
        if lista:
            graves = sum(a.gravidade == "erro" for a in lista)
            cor = "red" if graves else "orange"
            with st.container(border=True):
                st.markdown(f":{cor}[:material/notifications_active:] **{len(lista)} alerta(s)** pedem atenção")
                ui.link_para("dashboard", "Ver alertas")


_backup_automatico()
agendador.iniciar()
nav = st.navigation(navegacao.construir(), position="sidebar", expanded=True)
_barra_lateral()
ui.mostrar_avisos()
nav.run()
