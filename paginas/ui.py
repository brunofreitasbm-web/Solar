"""Peças de interface repetidas entre páginas: estados vazios com próximo passo, avisos que
sobrevivem ao st.rerun, confirmação de exclusão e conversão de datas ISO."""

from collections.abc import Callable
from datetime import date

import streamlit as st

from paginas import navegacao

CHAVE_AVISOS = "_avisos_pendentes"


def avisar(mensagem: str, icone: str = ":material/check_circle:") -> None:
    """Agenda um toast para a próxima execução — um st.success antes de st.rerun nunca aparece."""
    st.session_state.setdefault(CHAVE_AVISOS, []).append((mensagem, icone))


def mostrar_avisos() -> None:
    for mensagem, icone in st.session_state.pop(CHAVE_AVISOS, []):
        st.toast(mensagem, icon=icone)


def link_para(url: str, rotulo: str | None = None) -> None:
    st.page_link(navegacao.pagina(url), label=rotulo)


def estado_vazio(mensagem: str, url: str, rotulo: str) -> None:
    """Mensagem útil + o atalho para resolver, para o usuário nunca ficar sem saída."""
    with st.container(border=True):
        st.markdown(mensagem)
        link_para(url, rotulo)


def sem_faturas() -> None:
    estado_vazio("**Ainda não há faturas salvas.** Esta página aparece assim que a primeira conta de energia for lida.",
                 "enviar-faturas", "Enviar a primeira fatura")


@st.dialog("Confirmar exclusão")
def _dialogo_exclusao(mensagem: str, acao: Callable[[], None], sucesso: str) -> None:
    st.markdown(mensagem)
    st.caption("Essa ação não pode ser desfeita.")
    cancelar, excluir = st.columns(2)
    if cancelar.button("Cancelar", width="stretch", key="dialogo_cancelar"):
        st.rerun()
    if excluir.button("Excluir definitivamente", type="primary", width="stretch", icon=":material/delete:", key="dialogo_excluir"):
        acao()
        avisar(sucesso, ":material/delete:")
        st.rerun()


def botao_excluir(rotulo: str, mensagem: str, acao: Callable[[], None], sucesso: str, key: str) -> None:
    if st.button(rotulo, key=key, icon=":material/delete:", type="tertiary"):
        _dialogo_exclusao(mensagem, acao, sucesso)


def data_ou_none(texto: str | None) -> date | None:
    try:
        return date.fromisoformat(texto) if texto else None
    except ValueError:
        return None


def iso_ou_vazio(valor: date | None) -> str:
    return valor.isoformat() if valor else ""
