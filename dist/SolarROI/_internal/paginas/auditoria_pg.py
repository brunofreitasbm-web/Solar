import streamlit as st

from paginas import painel_dados, ui
from solar import auditoria
from solar.auditoria import config as cfg
from solar.auditoria.achado import Achado

TODAS = "Todas as unidades"


def _cartao(achado: Achado, nomes: dict[str, str]) -> None:
    mostrar = st.error if achado.gravidade == "erro" else st.warning
    icone = ":material/error:" if achado.gravidade == "erro" else ":material/warning:"
    texto = f"**{nomes.get(achado.uc, achado.uc)} · {achado.mes_ref} — {achado.titulo}**  \n{achado.explicacao}"
    mostrar(texto.replace("$", r"\$"), icon=icone)
    st.caption(f"O que fazer: {achado.acao}".replace("$", r"\$"))


def render() -> None:
    st.title("Auditoria da fatura")
    st.caption(f"Confere compensação, créditos, Fio B e ciclo de leitura dos últimos {cfg.MESES_ANALISADOS} meses "
               "e aponta o que vale reclamar com a Equatorial.")
    p = painel_dados.carregar()
    if p is None:
        ui.sem_faturas()
        return

    achados = auditoria.auditar(p.df)
    if not achados:
        st.success("Nenhuma divergência encontrada nas faturas carregadas.", icon=":material/check_circle:")
        return

    escolha = st.selectbox("Unidade", [TODAS, *sorted({p.nomes.get(a.uc, a.uc) for a in achados})])
    visiveis = [a for a in achados if escolha in (TODAS, p.nomes.get(a.uc, a.uc))]
    st.markdown(f"**{len(visiveis)} ponto(s) para conferir**")
    for a in visiveis:
        _cartao(a, p.nomes)
