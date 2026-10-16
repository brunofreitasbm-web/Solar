import streamlit as st

from solar import benchmarks, configuracoes, creditos, economia, financiamento, geracao, graficos, roi
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
    col1.metric("Economia acumulada", graficos.rs(economia_total, 2))
    col2.metric("ROI até hoje", f"{acumulado['roi_pct'].iloc[-1]:.1f}%" if cfg.completo else "—")
    col3.metric("Mês de payback", payback or "ainda não atingido")
    col4.metric("TIR mensal", f"{tir * 100:.2f}%" if tir else "—")

    if cfg.completo and not payback:
        previsto = roi.mes_payback_projetado(
            resumo, cfg.investimento_total, cfg.degradacao_anual, cfg.reajuste_tarifa_anual
        )
        if previsto:
            falta = cfg.investimento_total - economia_total
            st.info(f"Na tendência dos últimos 12 meses ({graficos.rs_md(resumo.tail(12)['economia_rs'].mean(), 2)}/mês, "
                     f"com reajuste de tarifa e degradação dos painéis), a economia acumulada deve alcançar o "
                     f"investimento total em **{previsto}** — faltam {graficos.rs_md(falta, 2)}.",
                     icon=":material/calendar_month:")

    st.plotly_chart(graficos.grafico_economia_mensal(resumo), width="stretch")

    if cfg.completo:
        st.plotly_chart(graficos.grafico_saldo_acumulado(acumulado, payback), width="stretch")

        if cfg.parcela_mensal:
            st.subheader("Financiamento: a economia está cobrindo a parcela?")
            fluxo = financiamento.fluxo_com_financiamento(resumo, cfg)
            meses_cobertos = (fluxo["saldo_liquido_rs"] >= 0) & (fluxo["parcela_rs"] > 0)
            meses_financiados = fluxo["parcela_rs"] > 0
            c1, c2, c3 = st.columns(3)
            c1.metric("Parcela mensal", graficos.rs(cfg.parcela_mensal, 2))
            c2.metric("Meses em que a economia cobriu a parcela",
                      f"{meses_cobertos.sum()} de {meses_financiados.sum()}")
            c3.metric("Saldo líquido acumulado (economia − parcelas)",
                      graficos.rs(fluxo['saldo_liquido_acumulado_rs'].iloc[-1], 2))
            if fluxo["saldo_liquido_acumulado_rs"].iloc[-1] < 0:
                st.warning("A economia ainda não cobre a parcela em nenhum mês — o financiamento está "
                           "sendo pago com outra renda, não com a economia da usina.",
                           icon=":material/trending_down:")
            st.plotly_chart(graficos.grafico_economia_vs_parcela(fluxo), width="stretch")
            termino = financiamento.mes_parcelas_termina(cfg)
            if termino:
                st.caption(f"Parcelas até {termino} · total financiado {graficos.rs_md(cfg.valor_financiado, 2)}")

            if fluxo["saldo_liquido_acumulado_rs"].iloc[-1] < 0:
                equilibrio = financiamento.mes_ponto_equilibrio(
                    resumo, cfg, cfg.degradacao_anual, cfg.reajuste_tarifa_anual
                )
                if equilibrio:
                    st.info(f"Ponto de equilíbrio projetado — quando a economia acumulada finalmente "
                             f"cobre todas as parcelas pagas até então — na tendência atual: **{equilibrio}**.",
                             icon=":material/balance:")

        st.subheader("Comparação com renda fixa")
        comparativo = benchmarks.comparar_com_investimento(cfg.investimento_total, cfg.data_investimento, economia_total)
        c1, c2, c3 = st.columns(3)
        c1.metric("Usina (economia)", graficos.rs(comparativo['economia_acumulada_rs'], 2))
        c2.metric("Se fosse CDI", graficos.rs(comparativo['cdi_valor_final_rs'], 2) if comparativo["cdi_valor_final_rs"] else "—")
        c3.metric("Se fosse IPCA", graficos.rs(comparativo['ipca_valor_final_rs'], 2) if comparativo["ipca_valor_final_rs"] else "—")

        media_mensal = resumo.tail(12)["economia_rs"].mean()
        projecao = roi.projecao_25_anos(media_mensal, cfg.investimento_total, cfg.degradacao_anual, cfg.reajuste_tarifa_anual)
        st.plotly_chart(graficos.grafico_roi_projetado(projecao, cfg.investimento_total), width="stretch")

    st.subheader("Saldo de créditos por unidade")
    st.dataframe(
        creditos.saldo_por_unidade(df_faturas), width="stretch", hide_index=True,
        column_config={
            "uc": st.column_config.TextColumn("UC"),
            "apelido": st.column_config.TextColumn("Unidade"),
            "geradora": st.column_config.CheckboxColumn("Geradora"),
            "mes_ref": st.column_config.TextColumn("Última fatura"),
            "saldo_creditos_kwh": st.column_config.NumberColumn("Saldo de créditos", format="%.0f kWh"),
        },
        alt="Tabela com o saldo de créditos de energia (kWh) mais recente de cada unidade",
    )
    st.caption(creditos.sugestao_rateio(creditos.saldo_por_unidade(df_faturas)))

    expirando = creditos.creditos_a_expirar(df_faturas)
    if not expirando.empty:
        st.warning("Créditos perto de expirar (validade de 60 meses):", icon=":material/timer:")
        st.dataframe(
            expirando, width="stretch", hide_index=True,
            column_config={
                "uc": st.column_config.TextColumn("UC"),
                "apelido": st.column_config.TextColumn("Unidade"),
                "mes_ref": st.column_config.TextColumn("Mês do crédito"),
                "credito_gerado_kwh": st.column_config.NumberColumn("Crédito", format="%.0f kWh"),
                "meses_para_expirar": st.column_config.NumberColumn("Expira em", format="%d meses"),
            },
            alt="Tabela de créditos de energia perto de expirar",
        )

    geradoras = df_faturas[df_faturas["geradora"]]
    if not geradoras.empty:
        alertas = geracao.avaliar_geracao(geradoras, cfg.performance_ratio)
        if not alertas.empty:
            st.subheader("Geração real vs. esperada")
            alertas = alertas.assign(razao_pct=alertas["razao"] * 100)
            st.dataframe(
                alertas, width="stretch", hide_index=True,
                column_order=["uc", "mes_ref", "geracao_real_kwh", "geracao_esperada_kwh", "razao_pct", "alerta"],
                column_config={
                    "uc": st.column_config.TextColumn("UC"),
                    "mes_ref": st.column_config.TextColumn("Mês"),
                    "geracao_real_kwh": st.column_config.NumberColumn("Geração real", format="%.0f kWh"),
                    "geracao_esperada_kwh": st.column_config.NumberColumn("Geração esperada", format="%.0f kWh"),
                    "razao_pct": st.column_config.ProgressColumn("% do esperado", format="%.0f%%", min_value=0, max_value=120),
                    "alerta": st.column_config.CheckboxColumn("Abaixo do esperado"),
                    "razao": None,
                },
                alt="Tabela comparando geração real e esperada por mês",
            )
            baixas = alertas[alertas["alerta"]]
            if not baixas.empty:
                st.warning(f"{len(baixas)} mês(es) com geração abaixo do esperado — "
                           "verifique sujeira nos painéis ou inversor.", icon=":material/solar_power:")
