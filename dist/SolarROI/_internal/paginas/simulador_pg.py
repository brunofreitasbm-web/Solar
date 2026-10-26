from datetime import date

import pandas as pd
import streamlit as st

from paginas import painel_dados, ui
from solar import ampliacao, benchmarks, config, expansao, financiamento, geracao, graficos, graficos_analise

MODOS = {"Reduzir o prazo (mantém a parcela)": "prazo", "Reduzir a parcela (mantém o prazo)": "parcela"}
VALORES_COMPARADOS = (5_000, 10_000, 20_000, 30_000, 50_000)


def _equilibrio(p: painel_dados.Painel, sim: financiamento.Amortizacao | None = None) -> str | None:
    cfg = p.cfg
    parametros = dict(degradacao_anual=cfg.degradacao_anual, reajuste_tarifa_anual=cfg.reajuste_tarifa_anual, modelo=p.modelo)
    if sim is None:
        return financiamento.mes_ponto_equilibrio(p.resumo, cfg, **parametros)
    return financiamento.mes_ponto_equilibrio(p.resumo, cfg, parcelas=sim.parcelas, desembolso_extra=sim.valor, **parametros)


def _quitacao(p: painel_dados.Painel) -> None:
    cfg = p.cfg
    taxa = financiamento.taxa_mensal(cfg)
    if not taxa:
        ui.estado_vazio("**Sem financiamento cadastrado.** Informe valor, parcela, quantidade e data da 1ª parcela para simular a quitação.",
                        "configuracoes", "Cadastrar o financiamento")
        return

    hoje = date.today()
    pagas = financiamento.parcelas_pagas(cfg, hoje)
    saldo = financiamento.saldo_devedor(cfg, pagas)
    restantes = cfg.qtd_parcelas - pagas
    cdi = benchmarks.cdi_anual_medio()
    anual = (1 + taxa) ** 12 - 1

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Custo do financiamento", f"{anual * 100:.1f}% a.a.", help=f"{taxa * 100:.2f}% ao mês, embutido no contrato.", border=True)
    c2.metric("CDI (12 meses)", f"{cdi * 100:.1f}% a.a." if cdi else "—", border=True)
    c3.metric("Saldo devedor estimado", graficos.rs(saldo), help="Valor presente das parcelas que faltam, pela taxa do contrato. Confirme o valor exato com o banco.", border=True)
    c4.metric("Parcelas restantes", f"{restantes} de {cfg.qtd_parcelas}", border=True)
    if cdi and anual > cdi:
        st.info(f"O financiamento custa {anual * 100:.1f}% ao ano e o CDI rende {cdi * 100:.1f}%: cada real usado para amortizar "
                f"rende mais que o mesmo real aplicado — desde que não falte caixa para imprevistos.", icon=":material/percent:")
    if restantes <= 0:
        st.success("O financiamento já foi quitado.")
        return

    col_valor, col_modo = st.columns([1, 1])
    with col_valor:
        valor = st.number_input("Quanto amortizar hoje (R$)", min_value=0.0, max_value=float(round(saldo, 2)), value=min(20_000.0, float(round(saldo, 0))), step=1_000.0)
    with col_modo:
        modo = MODOS[st.radio("Como abater", list(MODOS), help="Reduzir o prazo poupa mais juros; reduzir a parcela alivia o caixa de cada mês.")]

    sim = financiamento.simular_amortizacao(cfg, valor, modo, hoje)
    antes, depois = _equilibrio(p), _equilibrio(p, sim)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Juros economizados", graficos.rs(sim.juros_economizados), border=True)
    m2.metric("Parcela" if modo == "parcela" else "Parcelas restantes",
              graficos.rs(sim.parcela_nova) if modo == "parcela" else f"{sim.restantes_depois} (era {sim.restantes_antes})", border=True)
    m3.metric("Saldo devedor depois", graficos.rs(sim.saldo_depois), border=True)
    m4.metric("Ponto de equilíbrio", graficos_analise.mes_legivel_ou_traco(depois), delta=f"antes: {graficos_analise.mes_legivel_ou_traco(antes)}", delta_color="off",
              help="Mês em que a economia acumulada cobre tudo o que saiu do bolso (parcelas e esta amortização).", border=True)
    if cdi and valor > 0:
        rendimento = valor * ((1 + cdi) ** (restantes / 12) - 1)
        veredito = "amortizar rende mais" if sim.juros_economizados > rendimento else "aplicar rende mais"
        st.caption(f"Se esse dinheiro fosse aplicado no CDI até o fim do contrato, renderia {graficos.rs_md(rendimento)} brutos "
                   f"(antes do imposto) contra {graficos.rs_md(sim.juros_economizados)} de juros economizados: {veredito}.")

    comparados = [v for v in VALORES_COMPARADOS if v < saldo] + [saldo]
    linhas = [{"rotulo": "Quitar" if v == saldo else graficos.rs(v), "valor": v,
               "juros_economizados": financiamento.simular_amortizacao(cfg, v, "prazo", hoje).juros_economizados} for v in comparados]
    cenarios = pd.DataFrame(linhas)
    cdi_rs = cenarios["valor"].map(lambda v: v * ((1 + cdi) ** (restantes / 12) - 1)) if cdi else None
    st.plotly_chart(graficos_analise.grafico_quitacao(cenarios, cdi_rs), width="stretch")
    st.caption("Simulação com a taxa implícita do contrato (valor financiado × parcelas), sem IOF, tarifas ou seguros. Peça ao banco o "
               "saldo devedor e o desconto de juros para amortização antecipada antes de decidir.")


def _expansao(p: painel_dados.Painel) -> None:
    cfg, modelo = p.cfg, p.modelo
    if not modelo:
        ui.estado_vazio("**Ainda não há faturas com energia compensada.** Envie as faturas das unidades que recebem créditos.",
                        "enviar-faturas", "Enviar faturas")
        return
    demanda = expansao.analisar_demanda(p.df_economia, cfg.degradacao_anual, modelo.sazonalidade)
    rendimento = None
    if p.coordenadas:
        rendimento = geracao.rendimento_kwh_kwp_mes(p.coordenadas, cfg.performance_ratio)
    if not demanda or not rendimento:
        ui.estado_vazio("**Faltam dados para analisar a expansão:** pelo menos 6 meses de geração e as coordenadas das usinas.",
                        "unidades", "Informar as coordenadas")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Geração das usinas (kWh/mês)", graficos.num(demanda.producao_kwh_mes), border=True)
    c2.metric("Demanda compensável (kWh/mês)", graficos.num(demanda.demanda_kwh_mes), border=True)
    c3.metric("Sobra de geração (kWh/mês)", graficos.num(demanda.sobra_kwh_mes), delta=f"{100 * demanda.sobra_kwh_mes / demanda.demanda_kwh_mes:.0f}% da demanda", delta_color="off", border=True)
    c4.metric("Demanda cresce (kWh/mês por ano)", graficos.num(demanda.crescimento_kwh_mes_por_ano), border=True)
    if demanda.meses_ate_faltar is None:
        st.success("A geração cobre a demanda pelos próximos 10 anos na tendência atual. Ampliar agora não geraria economia.", icon=":material/check_circle:")
    elif demanda.meses_ate_faltar == 0:
        st.warning("A demanda já supera a geração.", icon=":material/trending_up:")
    else:
        st.success(f"A geração cobre a demanda por mais {demanda.meses_ate_faltar} meses (~{demanda.meses_ate_faltar / 12:.1f} anos). "
                   f"Ampliar antes disso só acumularia créditos sem uso.", icon=":material/check_circle:")
    st.plotly_chart(graficos_analise.grafico_demanda_vs_geracao(demanda, cfg.degradacao_anual), width="stretch")

    st.subheader("Simular uma ampliação")
    kwp_atual = demanda.producao_kwh_mes / rendimento
    custo_padrao = cfg.investimento_total / kwp_atual if cfg.investimento_total else 4000.0
    liquido_novo = ampliacao.valor_liquido_usina_nova(modelo)
    taxa_contrato = financiamento.taxa_mensal(cfg)
    cdi = benchmarks.cdi_anual_medio() or 0.13

    st.caption(f"Potência instalada estimada pela geração e pela irradiação: ~{kwp_atual:,.0f} kWp ({rendimento:,.0f} kWh por kWp ao mês). "
               f"Isso vale {graficos.rs_md(custo_padrao)} por kWp no seu investimento.")
    a, b, c = st.columns(3)
    with a:
        meses_horizonte = st.slider("Daqui a quantos meses a demanda extra será usada", 12, 96, 36, step=6)
        kwh_uteis = st.number_input("Demanda extra a cobrir (kWh/mês)", min_value=0.0, value=float(round(demanda.lacuna_em(meses_horizonte, cfg.degradacao_anual))), step=50.0,
                                    help="Quanto de consumo novo a ampliação realmente compensaria. Energia acima disso não gera economia.")
        kwp = st.number_input("Potência a adicionar (kWp)", min_value=1.0, value=float(max(round(kwh_uteis / rendimento), 5)), step=1.0)
    with b:
        custo = st.number_input("Custo por kWp (R$)", min_value=500.0, value=float(round(custo_padrao, -1)), step=100.0)
        valor_kwh = st.number_input("Valor líquido do kWh compensado (R$)", min_value=0.05, value=float(round(liquido_novo, 3)), step=0.01, format="%.3f",
                                    help=f"Tarifa cheia menos Fio B a 100% e benefício, com {config.DESCONTO_USINA_NOVA:.0%} a menos para Fio A e encargos que usinas novas (GD III) não compensam. Estimativa.")
        desconto = st.number_input("Taxa de desconto (% a.a.)", min_value=0.0, value=round(cdi * 100, 1), step=0.5) / 100
    with c:
        financiar = st.checkbox("Financiar", value=False)
        juros = st.number_input("Juros (% ao mês)", min_value=0.1, value=round((taxa_contrato or 0.02) * 100, 2), step=0.1, disabled=not financiar) / 100
        entrada = st.number_input("Entrada (%)", min_value=0.0, max_value=100.0, value=20.0, step=5.0, disabled=not financiar) / 100

    r = expansao.simular_expansao(kwp, custo, rendimento, valor_kwh, cfg.reajuste_tarifa_anual, cfg.degradacao_anual, desconto,
                                  juros if financiar else None, 48, entrada, kwh_uteis)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Investimento", graficos.rs(r.capex), border=True)
    m2.metric("Economia por mês (inicial)", graficos.rs(r.economia_mes_inicial), help=f"{r.kwh_mes:,.0f} kWh/mês aproveitados.", border=True)
    m3.metric("Payback", f"{r.payback_meses / 12:.1f} anos" if r.payback_meses else "não se paga em 25 anos", border=True)
    m4.metric("TIR", f"{r.tir_anual * 100:.1f}% a.a." if r.tir_anual is not None else "—", border=True)
    if r.vpl > 0:
        st.success(f"Compensa: o valor presente é {graficos.rs_md(r.vpl)} acima do que o CDI de {desconto * 100:.1f}% a.a. entregaria.", icon=":material/check_circle:")
    else:
        st.error(f"Não compensa: o valor presente fica {graficos.rs_md(abs(r.vpl))} abaixo do que o CDI de {desconto * 100:.1f}% a.a. entregaria.", icon=":material/cancel:")
    if r.parcela_mensal:
        st.caption(f"Financiada: parcela de {graficos.rs_md(r.parcela_mensal)} por 48 meses, {graficos.rs_md(r.juros_total)} de juros.")
    st.caption("Estimativa: usinas novas (GD III) compensam menos que a sua; confirme as regras e o preço com o integrador.")


def render() -> None:
    st.title("Simulador")
    p = painel_dados.carregar()
    if p is None:
        ui.sem_faturas()
        return
    aba_quitacao, aba_expansao = st.tabs(
        [":material/savings: Quitação antecipada", ":material/add_circle: Ampliar a usina"],
        key="simulador_aba_ativa",  # sem key, cada slider/number_input volta pra 1ª aba a cada rerun
    )
    with aba_quitacao:
        _quitacao(p)
    with aba_expansao:
        _expansao(p)
