import plotly.express as px
import streamlit as st

from solar import benchmarks, configuracoes, creditos, economia, financiamento, geracao, roi
from solar.faturas import repositorio
from solar.tarifa import aneel


def render() -> None:
    st.title("Dashboard")

    df_faturas = repositorio.tabela()
    if df_faturas.empty:
        st.info("Nenhuma fatura salva ainda. Envie e confirme faturas nas páginas anteriores.")
        return

    cfg = configuracoes.carregar()
    if not cfg.completo:
        st.warning("Informe o investimento total e a data em **Configurações** para ver o ROI.")

    try:
        tarifa = aneel.tarifa_de_hoje()
        tarifa_tusd = tarifa.tusd_kwh
        tarifa_padrao = tarifa.com_tributos(cfg.icms, cfg.pis_cofins)
    except aneel.FalhaTarifa as erro:
        st.error(str(erro))
        tarifa_tusd, tarifa_padrao = 0.0, 0.0

    df_economia = economia.tabela_economia(df_faturas, tarifa_tusd, tarifa_padrao)
    resumo = economia.resumo_mensal(df_economia)
    acumulado = roi.serie_acumulada(resumo, cfg.investimento_total)

    economia_total = resumo["economia_rs"].sum()
    payback = roi.mes_payback(acumulado)
    tir = roi.tir_mensal(cfg.investimento_total, resumo["economia_rs"].tolist()) if cfg.completo else None

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Economia acumulada", f"R$ {economia_total:,.2f}")
    col2.metric("ROI até hoje", f"{acumulado['roi_pct'].iloc[-1]:.1f}%" if cfg.completo else "—")
    col3.metric("Mês de payback", payback or "ainda não atingido")
    col4.metric("TIR mensal", f"{tir * 100:.2f}%" if tir else "—")

    st.plotly_chart(
        px.bar(resumo, x="mes_ref", y="economia_rs", title="Economia mensal (R$)",
               labels={"mes_ref": "Mês", "economia_rs": "Economia (R$)"}),
        use_container_width=True,
    )

    if cfg.completo:
        st.plotly_chart(
            px.line(acumulado, x="mes_ref", y="saldo_rs", title="Saldo acumulado vs. investimento",
                    labels={"mes_ref": "Mês", "saldo_rs": "Saldo (R$)"}),
            use_container_width=True,
        )

        if cfg.parcela_mensal:
            st.subheader("Financiamento: a economia está cobrindo a parcela?")
            fluxo = financiamento.fluxo_com_financiamento(resumo, cfg)
            meses_cobertos = (fluxo["saldo_liquido_rs"] >= 0) & (fluxo["parcela_rs"] > 0)
            meses_financiados = fluxo["parcela_rs"] > 0
            c1, c2, c3 = st.columns(3)
            c1.metric("Parcela mensal", f"R$ {cfg.parcela_mensal:,.2f}")
            c2.metric("Meses em que a economia cobriu a parcela",
                      f"{meses_cobertos.sum()} de {meses_financiados.sum()}")
            c3.metric("Saldo líquido acumulado (economia − parcelas)",
                      f"R$ {fluxo['saldo_liquido_acumulado_rs'].iloc[-1]:,.2f}")
            if fluxo["saldo_liquido_acumulado_rs"].iloc[-1] < 0:
                st.warning("A economia ainda não cobre a parcela em nenhum mês — o financiamento está "
                           "sendo pago com outra renda, não com a economia da usina.")
            st.plotly_chart(
                px.bar(fluxo, x="mes_ref", y=["economia_rs", "parcela_rs"], barmode="group",
                       title="Economia vs. parcela, mês a mês",
                       labels={"mes_ref": "Mês", "value": "R$", "variable": ""}),
                use_container_width=True,
            )
            termino = financiamento.mes_parcelas_termina(cfg)
            if termino:
                st.caption(f"Parcelas até {termino} · total financiado R$ {cfg.valor_financiado:,.2f}")

        st.subheader("Comparação com renda fixa")
        comparativo = benchmarks.comparar_com_investimento(cfg.investimento_total, cfg.data_investimento, economia_total)
        c1, c2, c3 = st.columns(3)
        c1.metric("Usina (economia)", f"R$ {comparativo['economia_acumulada_rs']:,.2f}")
        c2.metric("Se fosse CDI", f"R$ {comparativo['cdi_valor_final_rs']:,.2f}" if comparativo["cdi_valor_final_rs"] else "—")
        c3.metric("Se fosse IPCA", f"R$ {comparativo['ipca_valor_final_rs']:,.2f}" if comparativo["ipca_valor_final_rs"] else "—")

        st.subheader("Projeção de 25 anos")
        media_mensal = resumo["economia_rs"].mean()
        projecao = roi.projecao_25_anos(media_mensal, cfg.investimento_total, cfg.degradacao_anual, cfg.reajuste_tarifa_anual)
        st.plotly_chart(
            px.line(projecao, x="ano", y="roi_acumulado_pct", title="ROI acumulado projetado (%)",
                    labels={"ano": "Ano", "roi_acumulado_pct": "ROI acumulado (%)"}),
            use_container_width=True,
        )

    st.subheader("Saldo de créditos por unidade")
    st.dataframe(creditos.saldo_por_unidade(df_faturas), use_container_width=True, hide_index=True)
    st.caption(creditos.sugestao_rateio(creditos.saldo_por_unidade(df_faturas)))

    expirando = creditos.creditos_a_expirar(df_faturas)
    if not expirando.empty:
        st.warning("Créditos perto de expirar (validade de 60 meses):")
        st.dataframe(expirando, use_container_width=True, hide_index=True)

    geradoras = df_faturas[df_faturas["geradora"]]
    if not geradoras.empty:
        alertas = geracao.avaliar_geracao(geradoras, cfg.performance_ratio)
        if not alertas.empty:
            st.subheader("Geração real vs. esperada")
            st.dataframe(alertas, use_container_width=True, hide_index=True)
            baixas = alertas[alertas["alerta"]]
            if not baixas.empty:
                st.warning(f"{len(baixas)} mês(es) com geração abaixo do esperado — "
                           "verifique sujeira nos painéis ou inversor.")
