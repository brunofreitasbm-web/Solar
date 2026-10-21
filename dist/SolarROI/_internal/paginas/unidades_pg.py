from datetime import date

import streamlit as st

from paginas import ui
from solar import unidades
from solar.unidades import Unidade

INICIO_LEI_14300 = date(2023, 1, 7)


def _campos_usina(u: Unidade, geradora: bool) -> tuple[float, float, float, date | None]:
    kwp = st.number_input("Potência instalada (kWp)", value=float(u.kwp or 0), min_value=0.0, key=f"kwp_{u.uc}", disabled=not geradora)
    c_lat, c_lon = st.columns(2)
    lat = c_lat.number_input("Latitude", value=float(u.lat or 0), min_value=-90.0, max_value=90.0, format="%.5f",
                             key=f"lat_{u.uc}", disabled=not geradora, help="No Google Maps, clique com o botão direito na usina e copie o primeiro número.")
    lon = c_lon.number_input("Longitude", value=float(u.lon or 0), min_value=-180.0, max_value=180.0, format="%.5f",
                             key=f"lon_{u.uc}", disabled=not geradora, help="O segundo número copiado do Google Maps.")
    pedido = st.date_input("Data do pedido de conexão da usina", value=ui.data_ou_none(u.data_pedido_conexao), format="DD/MM/YYYY",
                           key=f"pedido_{u.uc}", disabled=not geradora,
                           help="Define a regra do Fio B pela Lei 14.300: pedidos antes de 07/01/2023 são isentos.")
    if geradora:
        faltando = [nome for nome, valor in (("potência", kwp), ("latitude", lat), ("longitude", lon)) if not valor]
        if faltando:
            st.caption(f":orange[:material/info:] Sem {', '.join(faltando)}, o alerta de baixa geração fica desligado para esta usina.")
        if pedido:
            st.caption("Fio B: " + ("isenta até 2045 (pedido antes da Lei 14.300)." if pedido < INICIO_LEI_14300 else "cobrança escalonada da Lei 14.300."))
    return kwp, lat, lon, pedido


def _cartao(u: Unidade) -> None:
    icone = ":material/solar_power:" if u.geradora else ":material/home:"
    with st.expander(f"{u.nome} — UC {u.uc}", icon=icone):
        col1, col2 = st.columns(2)
        with col1:
            apelido = st.text_input("Apelido", value=u.apelido, key=f"apelido_{u.uc}", placeholder="Ex.: Casa da praia")
            endereco = st.text_input("Endereço", value=u.endereco, key=f"endereco_{u.uc}")
            geradora = st.toggle("Tem usina nesta unidade (geradora)", value=u.geradora, key=f"gerad_{u.uc}")
        with col2:
            kwp, lat, lon, pedido = _campos_usina(u, geradora)

        col_salvar, col_excluir = st.columns([1, 1], vertical_alignment="center")
        if col_salvar.button("Salvar alterações", key=f"salvar_u_{u.uc}", type="primary", icon=":material/save:"):
            unidades.salvar(Unidade(
                uc=u.uc, apelido=apelido.strip(), endereco=endereco.strip(), geradora=geradora,
                kwp=kwp or None, lat=lat or None, lon=lon or None, data_pedido_conexao=ui.iso_ou_vazio(pedido) or None,
            ))
            ui.avisar(f"{apelido.strip() or u.nome} salva.")
            st.rerun()
        with col_excluir:
            ui.botao_excluir("Excluir unidade e faturas", f"Excluir **{u.nome}** (UC {u.uc}) e **todas as faturas** dela?",
                             lambda: unidades.excluir(u.uc), f"{u.nome} excluída.", key=f"excluir_{u.uc}")


def render() -> None:
    st.title("Unidades consumidoras")
    st.caption("Marque quais unidades têm usina e informe potência e coordenadas para ligar o alerta de baixa geração.")

    lista = unidades.listar()
    if not lista:
        ui.estado_vazio("**Nenhuma unidade cadastrada ainda.** Cada fatura enviada cria a unidade dela automaticamente.",
                        "enviar-faturas", "Enviar a primeira fatura")
        return

    geradoras = sum(u.geradora for u in lista)
    st.caption(f"{len(lista)} unidade(s), {geradoras} com usina.")
    for u in sorted(lista, key=lambda x: (not x.geradora, x.nome)):
        _cartao(u)
