"""Seção do Dashboard com filtros de unidade e período: mapa, heatmap, saldo de créditos e relatório."""

from datetime import date

import pandas as pd
import streamlit as st

from paginas import painel_dados
from solar import graficos, graficos_analise, pagamentos, relatorio_pdf, unidades


def _filtros(df: pd.DataFrame) -> pd.DataFrame:
    c1, c2 = st.columns(2)
    escolhidas = c1.multiselect("Unidades", sorted(df["unidade"].unique()), placeholder="Todas as unidades", key="analise_unidades")
    periodo = c2.selectbox("Período", ("Últimos 12 meses", "Desde o início"), key="analise_periodo")
    if escolhidas:
        df = df[df["unidade"].isin(escolhidas)]
    return df[df["mes_ref"].isin(sorted(df["mes_ref"].unique())[-12:])] if periodo == "Últimos 12 meses" else df


def _mapa() -> None:
    usinas = [u for u in unidades.listar() if u.lat and u.lon]
    if not usinas:
        st.caption("Informe latitude e longitude das usinas em Unidades para vê-las no mapa.")
        return
    mapa = pd.DataFrame({"lat": [u.lat for u in usinas], "lon": [u.lon for u in usinas], "kwp": [u.kwp or 1 for u in usinas]})
    st.map(mapa, size="kwp", zoom=8)
    st.caption("Usinas geradoras; o tamanho do ponto acompanha a potência instalada (kWp).")


def _relatorio(p: painel_dados.Painel) -> None:
    st.subheader("Relatório mensal")
    meses = sorted(p.df_economia["mes_ref"].unique(), reverse=True)
    mes = st.selectbox("Mês do relatório", meses, format_func=graficos.mes_legivel, key="relatorio_mes")
    pdf = relatorio_pdf.gerar(p.df_economia, p.nomes, mes, painel_dados.alertas_atuais(p), pagamentos.a_pagar(p.df, p.nomes, date.today()))
    st.download_button("Baixar relatório em PDF", pdf, file_name=f"relatorio_solar_{mes}.pdf", mime="application/pdf",
                       icon=":material/picture_as_pdf:", on_click="ignore")


def render(p: painel_dados.Painel) -> None:
    st.subheader("Análise por unidade")
    df = p.df_economia.assign(unidade=lambda d: d["uc"].map(p.nomes))
    df = _filtros(df)
    if df.empty:
        st.info("Nenhuma fatura com esses filtros.", icon=":material/filter_alt_off:")
        return
    st.plotly_chart(graficos_analise.grafico_heatmap(df, "consumo_kwh", "Consumo por unidade e mês",
                                                     "mais escuro = mais consumo", " kWh", "Blues"), width="stretch")
    st.plotly_chart(graficos_analise.grafico_heatmap(df, "economia_rs", "Economia por unidade e mês",
                                                     "mais escuro = mais economia", "", "Greens"), width="stretch")
    st.plotly_chart(graficos_analise.grafico_saldo_creditos(df), width="stretch")
    _mapa()
    _relatorio(p)
