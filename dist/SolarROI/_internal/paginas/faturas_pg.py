from io import BytesIO

import pandas as pd
import streamlit as st

from paginas import painel_dados, ui
from solar import config, graficos
from solar.faturas import repositorio

COLUNAS_PLANILHA = {
    "mes_ref": "Mês", "unidade": "Unidade", "uc": "UC", "consumo_kwh": "Consumo (kWh)",
    "injetado_kwh": "Injetado (kWh)", "compensado_kwh": "Compensado (kWh)", "saldo_creditos_kwh": "Saldo de créditos (kWh)",
    "total_rs": "Total (R$)", "economia_rs": "Economia (R$)", "vencimento": "Vencimento", "pago_em": "Pago em",
}


def _planilha(df: pd.DataFrame) -> bytes:
    saida = BytesIO()
    df.rename(columns=COLUNAS_PLANILHA).to_excel(saida, index=False, sheet_name="Faturas")
    return saida.getvalue()


def _filtrar(df: pd.DataFrame) -> pd.DataFrame:
    c1, c2 = st.columns(2)
    unidades_sel = c1.multiselect("Unidades", sorted(df["unidade"].unique()), placeholder="Todas as unidades")
    anos = sorted(df["mes_ref"].str[:4].unique(), reverse=True)
    anos_sel = c2.multiselect("Anos", anos, placeholder="Todos os anos")
    if unidades_sel:
        df = df[df["unidade"].isin(unidades_sel)]
    if anos_sel:
        df = df[df["mes_ref"].str[:4].isin(anos_sel)]
    return df


def _detalhe(linha: pd.Series) -> None:
    st.subheader(f"{linha['unidade']} · {linha['mes_ref']}")
    pdf = config.PASTA_PDFS / str(linha["arquivo"]) if linha["arquivo"] else None
    c1, c2 = st.columns(2)
    if pdf and pdf.is_file():
        c1.download_button("Baixar o PDF da fatura", pdf.read_bytes(), file_name=pdf.name, mime="application/pdf",
                           icon=":material/picture_as_pdf:", width="stretch", on_click="ignore")
    else:
        c1.caption("O PDF desta fatura não está arquivado.")
    with c2:
        ui.botao_excluir("Excluir esta fatura", f"Excluir a fatura {linha['mes_ref']} de **{linha['unidade']}**?",
                         lambda: (repositorio.excluir(int(linha["id"])), st.cache_data.clear()),
                         "Fatura excluída.", key=f"excluir_fatura_{linha['id']}")


def render() -> None:
    st.title("Faturas")
    st.caption("Todo o histórico lido. Selecione uma linha para baixar o PDF ou excluir.")
    p = painel_dados.carregar()
    if p is None:
        ui.sem_faturas()
        return

    df = p.df_economia.assign(
        unidade=lambda d: d["uc"].map(p.nomes),
        vencimento=lambda d: pd.to_datetime(d["vencimento"], errors="coerce"),
        pago_em=lambda d: pd.to_datetime(d["pago_em"], errors="coerce"),
    ).sort_values("mes_ref", ascending=False)
    df = _filtrar(df)
    if df.empty:
        st.info("Nenhuma fatura com esses filtros.", icon=":material/filter_alt_off:")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Faturas", len(df), border=True)
    c2.metric("Total pago", graficos.rs(df["total_rs"].sum(), 2), border=True)
    c3.metric("Economia", graficos.rs(df["economia_rs"].sum(), 2), border=True)

    st.download_button("Exportar para Excel", _planilha(df[list(COLUNAS_PLANILHA)]), file_name="faturas_solar.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       icon=":material/download:", on_click="ignore")

    evento = st.dataframe(
        df, width="stretch", hide_index=True, on_select="rerun", selection_mode="single-row",
        column_order=list(COLUNAS_PLANILHA),
        column_config={
            "mes_ref": "Mês", "unidade": "Unidade", "uc": "UC",
            "consumo_kwh": st.column_config.NumberColumn("Consumo", format="%.0f kWh"),
            "injetado_kwh": st.column_config.NumberColumn("Injetado", format="%.0f kWh"),
            "compensado_kwh": st.column_config.NumberColumn("Compensado", format="%.0f kWh"),
            "saldo_creditos_kwh": st.column_config.NumberColumn("Saldo de créditos", format="%.0f kWh"),
            "total_rs": st.column_config.NumberColumn("Total", format="R$ %.2f"),
            "economia_rs": st.column_config.NumberColumn("Economia", format="R$ %.2f"),
            "vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"),
            "pago_em": st.column_config.DateColumn("Pago em", format="DD/MM/YYYY"),
        },
        alt="Tabela com todas as faturas lidas",
    )
    if evento.selection.rows:
        _detalhe(df.iloc[evento.selection.rows[0]])
