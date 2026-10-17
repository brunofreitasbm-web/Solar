import re

import streamlit as st

from paginas import navegacao, ui
from solar import unidades
from solar.faturas import repositorio
from solar.faturas.modelo import Fatura
from solar.unidades import Unidade

CAMPOS_EDITAVEIS = (
    ("uc", "Unidade consumidora *"), ("mes_ref", "Mês de referência (AAAA-MM) *"),
    ("consumo_kwh", "Consumo (kWh)"), ("injetado_kwh", "Injetado (kWh)"),
    ("compensado_kwh", "Compensado (kWh)"), ("saldo_creditos_kwh", "Saldo de créditos (kWh)"),
    ("credito_rs", "Crédito na fatura (R$)"), ("tarifa_kwh", "Tarifa (R$/kWh)"),
    ("total_rs", "Total a pagar (R$)"), ("bandeira", "Bandeira"), ("endereco", "Endereço"),
)
MES_VALIDO = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _erros(fatura: Fatura) -> list[str]:
    erros = []
    if not str(fatura.uc).strip():
        erros.append("Informe o número da unidade consumidora (está no topo da fatura).")
    if not MES_VALIDO.match(str(fatura.mes_ref).strip()):
        erros.append("O mês de referência precisa estar no formato AAAA-MM, por exemplo 2026-09.")
    return erros


def _editar_fatura(fatura: Fatura, indice: int) -> Fatura:
    colunas = st.columns(3)
    for i, (campo, rotulo) in enumerate(CAMPOS_EDITAVEIS):
        with colunas[i % 3]:
            valor_atual = getattr(fatura, campo)
            chave = f"{campo}_{indice}"
            if isinstance(valor_atual, str):
                novo = st.text_input(rotulo, value=valor_atual, key=chave)
            else:
                novo = st.number_input(rotulo, value=float(valor_atual or 0), key=chave)
            setattr(fatura, campo, novo)
    return fatura


def _salvar(fatura: Fatura, geradora: bool, existente: Unidade | None) -> None:
    repositorio.salvar(fatura)
    unidade = existente or Unidade(uc=fatura.uc, endereco=fatura.endereco)
    unidade.geradora = geradora
    unidades.salvar(unidade)


def _remover_da_fila(resultado, liberar_reenvio: bool) -> None:
    st.session_state[navegacao.CHAVE_PENDENTES].remove(resultado)
    if liberar_reenvio:
        st.session_state.get("arquivos_processados", set()).discard(resultado.fatura.arquivo)


def _cartao(i: int, resultado, unidades_existentes: dict[str, Unidade]) -> None:
    fatura = resultado.fatura
    titulo = f"{fatura.arquivo} — UC {fatura.uc or '?'} / {fatura.mes_ref or '?'}"
    precisa_atencao = bool(resultado.aviso or fatura.campos_faltando)
    icone = ":material/error:" if precisa_atencao else ":material/check_circle:"
    with st.expander(titulo, expanded=precisa_atencao, icon=icone):
        if resultado.aviso:
            st.warning(resultado.aviso, icon=":material/warning:")
        if fatura.campos_faltando:
            st.caption(f"Não consegui ler: **{', '.join(fatura.campos_faltando)}**. Confira na fatura e preencha abaixo.")

        fatura = _editar_fatura(fatura, i)
        existente = unidades_existentes.get(fatura.uc)
        geradora = st.checkbox("É geradora (tem usina nesta unidade)", value=fatura.tem_geracao or bool(existente and existente.geradora),
                               key=f"geradora_{i}")
        erros = _erros(fatura)
        for erro in erros:
            st.error(erro, icon=":material/edit:")

        col_a, col_b = st.columns(2)
        if col_a.button("Confirmar e salvar", key=f"salvar_{i}", type="primary", icon=":material/save:", disabled=bool(erros), width="stretch"):
            _salvar(fatura, geradora, existente)
            _remover_da_fila(resultado, liberar_reenvio=False)
            ui.avisar(f"Fatura de {fatura.mes_ref} da UC {fatura.uc} salva.")
            st.rerun()
        if col_b.button("Tirar da fila", key=f"descartar_{i}", icon=":material/remove_done:", width="stretch",
                        help="Remove sem salvar. Você pode enviar o mesmo PDF de novo depois."):
            _remover_da_fila(resultado, liberar_reenvio=True)
            ui.avisar(f"{fatura.arquivo} saiu da fila.", ":material/remove_done:")
            st.rerun()


def render() -> None:
    st.title("Revisar leitura")
    pendentes = st.session_state.get(navegacao.CHAVE_PENDENTES, [])

    if not pendentes:
        ui.estado_vazio("**Tudo revisado.** Nenhuma fatura esperando confirmação.", "enviar-faturas", "Enviar mais faturas")
        return

    st.caption(f"{len(pendentes)} fatura(s) aguardando confirmação. Campos com * são obrigatórios; as que precisam de atenção já vêm abertas.")
    unidades_existentes = {u.uc: u for u in unidades.listar()}
    for i, resultado in enumerate(list(pendentes)):
        _cartao(i, resultado, unidades_existentes)
