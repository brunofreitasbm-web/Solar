import streamlit as st

from solar import unidades
from solar.faturas import repositorio
from solar.faturas.modelo import Fatura

CAMPOS_EDITAVEIS = (
    ("uc", "Unidade consumidora"), ("mes_ref", "Mês de referência (AAAA-MM)"),
    ("consumo_kwh", "Consumo (kWh)"), ("injetado_kwh", "Injetado (kWh)"),
    ("compensado_kwh", "Compensado (kWh)"), ("saldo_creditos_kwh", "Saldo de créditos (kWh)"),
    ("credito_rs", "Crédito na fatura (R$)"), ("tarifa_kwh", "Tarifa (R$/kWh)"),
    ("total_rs", "Total a pagar (R$)"), ("bandeira", "Bandeira"), ("endereco", "Endereço"),
)


def _editar_fatura(fatura: Fatura, indice: int) -> Fatura:
    col1, col2, col3 = st.columns(3)
    colunas = [col1, col2, col3]
    valores = {}
    for i, (campo, rotulo) in enumerate(CAMPOS_EDITAVEIS):
        with colunas[i % 3]:
            valor_atual = getattr(fatura, campo)
            chave = f"{campo}_{indice}"
            if isinstance(valor_atual, str):
                valores[campo] = st.text_input(rotulo, value=valor_atual, key=chave)
            else:
                valores[campo] = st.number_input(rotulo, value=float(valor_atual or 0), key=chave)
    for campo, valor in valores.items():
        setattr(fatura, campo, valor)
    return fatura


def render() -> None:
    st.title("Revisar leitura")
    pendentes = st.session_state.get("faturas_pendentes", [])

    if not pendentes:
        st.info("Nenhuma fatura na fila. Envie PDFs na página **Enviar faturas**.")
        return

    st.caption(f"{len(pendentes)} fatura(s) aguardando confirmação.")
    unidades_existentes = {u.uc: u for u in unidades.listar()}

    for i, resultado in enumerate(list(pendentes)):
        fatura = resultado.fatura
        titulo = f"{fatura.arquivo} — UC {fatura.uc or '?'} / {fatura.mes_ref or '?'}"
        with st.expander(titulo, expanded=bool(resultado.aviso or fatura.campos_faltando)):
            if resultado.aviso:
                st.warning(resultado.aviso)
            if fatura.campos_faltando:
                st.caption(f"Campos não lidos automaticamente: {', '.join(fatura.campos_faltando)}")

            fatura = _editar_fatura(fatura, i)
            sugestao_geradora = fatura.tem_geracao or unidades_existentes.get(fatura.uc, type("_", (), {"geradora": False})()).geradora
            geradora = st.checkbox("É geradora (tem usina nesta unidade)", value=sugestao_geradora, key=f"geradora_{i}")

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Confirmar e salvar", key=f"salvar_{i}", type="primary"):
                    repositorio.salvar(fatura)
                    unidade = unidades_existentes.get(fatura.uc)
                    if unidade is None:
                        from solar.unidades import Unidade
                        unidade = Unidade(uc=fatura.uc, endereco=fatura.endereco)
                    unidade.geradora = geradora
                    unidades.salvar(unidade)
                    st.session_state["faturas_pendentes"].remove(resultado)
                    st.rerun()
            with col_b:
                if st.button("Descartar", key=f"descartar_{i}"):
                    st.session_state["faturas_pendentes"].remove(resultado)
                    st.rerun()
