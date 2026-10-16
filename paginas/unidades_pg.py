import streamlit as st

from solar import unidades
from solar.unidades import Unidade


def render() -> None:
    st.title("Unidades consumidoras")
    st.caption("Marque quais unidades têm usina (geradoras) e informe coordenadas e potência "
               "para o alerta de baixa geração.")

    lista = unidades.listar()
    if not lista:
        st.info("Nenhuma unidade cadastrada ainda — envie uma fatura para criar a primeira.")

    for u in lista:
        with st.expander(f"{u.nome} — UC {u.uc}", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                apelido = st.text_input("Apelido", value=u.apelido, key=f"apelido_{u.uc}")
                endereco = st.text_input("Endereço", value=u.endereco, key=f"endereco_{u.uc}")
                geradora = st.checkbox("É geradora", value=u.geradora, key=f"gerad_{u.uc}")
            with col2:
                kwp = st.number_input("Potência instalada (kWp)", value=float(u.kwp or 0), key=f"kwp_{u.uc}",
                                       disabled=not geradora)
                lat = st.number_input("Latitude", value=float(u.lat or 0), format="%.5f", key=f"lat_{u.uc}",
                                       disabled=not geradora)
                lon = st.number_input("Longitude", value=float(u.lon or 0), format="%.5f", key=f"lon_{u.uc}",
                                       disabled=not geradora)
                data_pedido = st.text_input(
                    "Data do pedido de conexão da usina (AAAA-MM-DD)",
                    value=u.data_pedido_conexao or "", key=f"pedido_{u.uc}", disabled=not geradora,
                    help="Define a regra do Fio B pela Lei 14.300: antes de 07/01/2023 é isento.",
                )

            col_salvar, col_excluir = st.columns(2)
            with col_salvar:
                if st.button("Salvar", key=f"salvar_u_{u.uc}", type="primary"):
                    unidades.salvar(Unidade(
                        uc=u.uc, apelido=apelido, endereco=endereco, geradora=geradora,
                        kwp=kwp or None, lat=lat or None, lon=lon or None,
                        data_pedido_conexao=data_pedido or None,
                    ))
                    st.success("Salvo.")
                    st.rerun()
            with col_excluir:
                if st.button("Excluir unidade e suas faturas", key=f"excluir_{u.uc}"):
                    unidades.excluir(u.uc)
                    st.rerun()
