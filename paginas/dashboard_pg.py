
import streamlit as st

from paginas import painel_dados
from solar import benchmarks, creditos, financiamento, geracao, graficos, graficos_analise, projecao, roi, vencimentos


def _mes(mes: str | None) -> str:
    return graficos_analise.mes_legivel_ou_traco(mes)


def _aviso_vencimentos(p: painel_dados.Painel) -> None:
    previsoes = vencimentos.proximos_vencimentos(p.df, p.nomes)
    proximas = previsoes[(previsoes["dias"] <= 7)]
    if proximas.empty:
        return
    itens = ", ".join(f"{l.unidade} ({'hoje' if l.dias == 0 else 'amanhã' if l.dias == 1 else f'em {l.dias} dias' if l.dias > 0 else f'há {-l.dias} dias'})"
                      for l in proximas.itertuples())
    st.warning(f"Faturas previstas para esta semana: {itens}. Veja a página **Vencimentos** para baixar lembretes.",
               icon=":material/event_upcoming:")


def _kpis(p: painel_dados.Painel, acumulado, payback_previsto: str | None) -> None:
    cfg, resumo = p.cfg, p.resumo
    economia_total = resumo["economia_rs"].sum()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Economia acumulada", graficos.rs(economia_total, 2))
    col2.metric("Economia nos últimos 12 meses", graficos.rs(resumo.tail(12)["economia_rs"].sum(), 2))
    col3.metric("ROI até hoje", f"{acumulado['roi_pct'].iloc[-1]:.1f}%" if cfg.completo else "—")
    payback = roi.mes_payback(acumulado)
    col4.metric("Payback" if payback else "Payback previsto", _mes(payback or payback_previsto))


def _projecao_e_premissas(p: painel_dados.Painel) -> tuple[str | None, str | None, str | None]:
    """Payback e ponto de equilíbrio em três cenários; devolve (payback c/ Fio B, equilíbrio c/ Fio B, payback s/ Fio B)."""
    cfg, resumo, modelo = p.cfg, p.resumo, p.modelo
    parametros = dict(degradacao_anual=cfg.degradacao_anual, reajuste_tarifa_anual=cfg.reajuste_tarifa_anual)
    pb_com = roi.mes_payback_projetado(resumo, cfg.investimento_total, modelo=modelo, escalar_fio_b=True, **parametros)
    pb_sem = roi.mes_payback_projetado(resumo, cfg.investimento_total, modelo=modelo, escalar_fio_b=False, **parametros)
    eq_com = financiamento.mes_ponto_equilibrio(resumo, cfg, modelo=modelo, escalar_fio_b=True, **parametros) if cfg.parcela_mensal else None
    return pb_com, eq_com, pb_sem


def _bloco_financiamento(p: painel_dados.Painel, eq_com: str | None) -> None:
    cfg = p.cfg
    st.subheader("Financiamento: a economia está cobrindo a parcela?")
    fluxo = financiamento.fluxo_com_financiamento(p.resumo, cfg)
    cobertos = ((fluxo["saldo_liquido_rs"] >= 0) & (fluxo["parcela_rs"] > 0)).sum()
    financiados = (fluxo["parcela_rs"] > 0).sum()
    saldo = fluxo["saldo_liquido_acumulado_rs"].iloc[-1]
    taxa = financiamento.taxa_mensal(cfg)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Parcela mensal", graficos.rs(cfg.parcela_mensal, 2))
    c2.metric("Meses com economia ≥ parcela", f"{cobertos} de {financiados}")
    c3.metric("Saldo líquido acumulado", graficos.rs(saldo), help="Economia menos parcelas pagas até hoje.")
    c4.metric("Custo do financiamento", f"{((1 + taxa) ** 12 - 1) * 100:.1f}% a.a." if taxa else "—",
              help="Taxa embutida no valor financiado × parcelas. Compare com o CDI antes de decidir amortizar.")
    ultimos = fluxo[fluxo["parcela_rs"] > 0].tail(6)
    if len(ultimos) and (ultimos["saldo_liquido_rs"] >= 0).all():
        st.success("Nos últimos 6 meses a economia cobriu a parcela todos os meses.", icon=":material/trending_up:")
    elif saldo < 0:
        st.warning(f"Em média, nos últimos 6 meses a economia {'cobre' if ultimos['saldo_liquido_rs'].mean() >= 0 else 'ficou'} "
                   f"{graficos.rs_md(abs(ultimos['saldo_liquido_rs'].mean()))} {'acima' if ultimos['saldo_liquido_rs'].mean() >= 0 else 'abaixo'} da parcela.",
                   icon=":material/trending_down:")
    st.plotly_chart(graficos.grafico_economia_vs_parcela(fluxo), width="stretch")
    termino = financiamento.mes_parcelas_termina(cfg)
    if termino:
        st.caption(f"Parcelas até {_mes(termino)} · total financiado {graficos.rs_md(cfg.valor_financiado, 2)}")
    if saldo < 0 and eq_com:
        st.info(f"Ponto de equilíbrio projetado — quando a economia acumulada cobre todas as parcelas pagas: "
                f"**{_mes(eq_com)}** (já contando a subida do Fio B).", icon=":material/balance:")


def _bloco_projecao(p: painel_dados.Painel, pb_com: str | None, pb_sem: str | None) -> None:
    cfg, modelo = p.cfg, p.modelo
    st.subheader("Projeção de 25 anos")
    parametros = dict(reajuste=cfg.reajuste_tarifa_anual, degradacao=cfg.degradacao_anual, modelo=modelo)
    com = projecao.projecao_anual(p.resumo, cfg.investimento_total, escalar_fio_b=True, **parametros)
    sem = projecao.projecao_anual(p.resumo, cfg.investimento_total, escalar_fio_b=False, **parametros)
    st.plotly_chart(graficos_analise.grafico_projecoes([
        ("Fio B sobe até 100% em 2029 (Lei 14.300)", com, "#D97706", "solid"),
        ("Fio B congelado em %.0f%%" % (modelo.pct_base * 100), sem, "#15803D", "dash"),
    ], cfg.investimento_total), width="stretch")
    if pb_com and pb_sem and pb_com != pb_sem:
        st.caption(f"A subida do Fio B adia o payback de {_mes(pb_sem)} para {_mes(pb_com)}.")


def _premissas_medidas(p: painel_dados.Painel) -> None:
    modelo = p.modelo
    with st.expander("Premissas medidas nas suas faturas", icon=":material/science:"):
        st.markdown(
            f"- **Fio B de hoje:** {modelo.pct_base:.0%} do valor cheio de {graficos.rs_md(modelo.fio_b_cheio_kwh, 3)}/kWh. "
            f"Em 2027 vai a 75%, em 2028 a 90% e em 2029 a 100%.\n"
            f"- **Valor da energia compensada:** {graficos.rs_md(modelo.bruto_kwh, 3)}/kWh pela tarifa cheia; "
            f"sobram {graficos.rs_md(modelo.liquido_kwh_base, 3)}/kWh depois do Fio B e do benefício tarifário.\n"
            f"- **Energia compensada por mês:** {modelo.kwh_mes:,.0f} kWh (média do ano, sem efeito de estação)."
        )
        medida = projecao.degradacao_observada(p.df)
        if medida:
            variacao, n = medida
            st.markdown(f"- **Variação anual da geração:** {variacao:+.1%} ({n} meses comparáveis com o ano anterior). "
                        f"{'Sem sinal de degradação, mas ' if variacao > -0.005 else ''}um ano de dados é pouco para medir os {p.cfg.degradacao_anual:.1%}/ano assumidos.")
        st.plotly_chart(graficos_analise.grafico_sazonalidade(modelo.sazonalidade, p.sazonal_nasa), width="stretch")


def _tabelas_creditos_e_geracao(p: painel_dados.Painel) -> None:
    st.subheader("Saldo de créditos por unidade")
    saldos = creditos.saldo_por_unidade(p.df)
    st.dataframe(
        saldos, width="stretch", hide_index=True,
        column_config={
            "uc": st.column_config.TextColumn("UC"), "apelido": st.column_config.TextColumn("Unidade"),
            "geradora": st.column_config.CheckboxColumn("Geradora"),
            "mes_ref": st.column_config.TextColumn("Última fatura"),
            "saldo_creditos_kwh": st.column_config.NumberColumn("Saldo de créditos", format="%.0f kWh"),
        },
        alt="Tabela com o saldo de créditos de energia (kWh) mais recente de cada unidade",
    )
    st.caption(creditos.sugestao_rateio(saldos) + " Veja a página **Rateio** para o cálculo dos percentuais.")

    expirando = creditos.creditos_a_expirar(p.df)
    if not expirando.empty:
        st.warning("Créditos perto de expirar (validade de 60 meses):", icon=":material/timer:")
        st.dataframe(
            expirando, width="stretch", hide_index=True,
            column_config={
                "uc": st.column_config.TextColumn("UC"), "apelido": st.column_config.TextColumn("Unidade"),
                "mes_ref": st.column_config.TextColumn("Mês do crédito"),
                "credito_gerado_kwh": st.column_config.NumberColumn("Crédito", format="%.0f kWh"),
                "meses_para_expirar": st.column_config.NumberColumn("Expira em", format="%d meses"),
            },
            alt="Tabela de créditos de energia perto de expirar",
        )

    geradoras = p.df[p.df["geradora"]]
    if geradoras.empty:
        return
    alertas = geracao.avaliar_geracao(geradoras, p.cfg.performance_ratio)
    if alertas.empty:
        return
    st.subheader("Geração real vs. esperada")
    alertas = alertas.assign(razao_pct=alertas["razao"] * 100)
    st.dataframe(
        alertas, width="stretch", hide_index=True,
        column_order=["uc", "mes_ref", "geracao_real_kwh", "geracao_esperada_kwh", "razao_pct", "alerta"],
        column_config={
            "uc": st.column_config.TextColumn("UC"), "mes_ref": st.column_config.TextColumn("Mês"),
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
        st.warning(f"{len(baixas)} mês(es) com geração abaixo do esperado — verifique sujeira nos painéis ou inversor.",
                   icon=":material/solar_power:")


def render() -> None:
    st.title("Dashboard")
    p = painel_dados.carregar()
    if p is None:
        st.info("Nenhuma fatura salva ainda. Envie e confirme faturas nas páginas anteriores.")
        return

    cfg = p.cfg
    if not cfg.completo:
        st.warning("Informe o investimento total e a data em **Configurações** para ver o ROI.")
    if p.tarifa is None:
        st.error("Não foi possível consultar a tarifa da ANEEL; a economia de faturas sem a linha de consumo ficou menos precisa.")

    _aviso_vencimentos(p)
    acumulado = roi.serie_acumulada(p.resumo, cfg.investimento_total)
    pb_com, eq_com, pb_sem = _projecao_e_premissas(p) if cfg.completo and p.modelo else (None, None, None)
    _kpis(p, acumulado, pb_com)

    if cfg.completo and pb_com and not roi.mes_payback(acumulado):
        falta = cfg.investimento_total - p.resumo["economia_rs"].sum()
        st.info(f"Na tendência das suas faturas — com sazonalidade, reajuste de tarifa, degradação dos painéis e a subida do Fio B — "
                f"a economia acumulada deve alcançar o investimento total em **{_mes(pb_com)}**. Faltam {graficos.rs_md(falta, 2)}.",
                icon=":material/calendar_month:")

    st.plotly_chart(graficos.grafico_economia_mensal(p.resumo), width="stretch")
    if cfg.completo:
        st.plotly_chart(graficos.grafico_saldo_acumulado(acumulado, roi.mes_payback(acumulado)), width="stretch")
        if cfg.parcela_mensal:
            _bloco_financiamento(p, eq_com)

        st.subheader("Comparação com renda fixa")
        economia_total = p.resumo["economia_rs"].sum()
        comparativo = benchmarks.comparar_com_investimento(cfg.investimento_total, cfg.data_investimento, economia_total)
        c1, c2, c3 = st.columns(3)
        c1.metric("Usina (economia)", graficos.rs(comparativo["economia_acumulada_rs"], 2))
        c2.metric("Se fosse CDI", graficos.rs(comparativo["cdi_valor_final_rs"], 2) if comparativo["cdi_valor_final_rs"] else "—")
        c3.metric("Se fosse IPCA", graficos.rs(comparativo["ipca_valor_final_rs"], 2) if comparativo["ipca_valor_final_rs"] else "—")
        st.caption("A comparação é do valor investido que seria devolvido pelo CDI/IPCA contra a economia acumulada da usina; "
                   "a usina continua economizando depois do payback, a renda fixa devolveria só o capital corrigido.")

        if p.modelo:
            _bloco_projecao(p, pb_com, pb_sem)
    if p.modelo:
        _premissas_medidas(p)
    _tabelas_creditos_e_geracao(p)
