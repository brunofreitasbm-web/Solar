from dataclasses import replace
from datetime import date

import pandas as pd
import streamlit as st

from paginas import painel_dados
from solar import ampliacao, benchmarks, expansao, geracao, graficos, graficos_analise, unidades
from solar.ampliacao import Premissas, UsinaPlanejada

BASE_MEDIDA = "Medido nas suas usinas"
BASE_NASA = "Teórico (NASA)"
CUSTO_POR_KWP_SEM_REFERENCIA = 4000.0


def _formulario(u: UsinaPlanejada | None) -> None:
    chave = f"usina_{u.id if u else 'nova'}"
    atual = u or UsinaPlanejada(nome="", paineis=0, potencia_painel_w=0.0)
    with st.form(chave):
        c1, c2 = st.columns(2)
        with c1:
            nome = st.text_input("Nome", value=atual.nome, placeholder="Ex.: Clínica FaçaAmigos")
            endereco = st.text_input("Endereço", value=atual.endereco)
            status = st.segmented_control("Situação", ampliacao.STATUS, default=atual.status)
            paineis = st.number_input("Quantidade de placas", min_value=0, value=atual.paineis, step=1)
            potencia = st.number_input("Potência de cada placa (W)", min_value=0.0, value=atual.potencia_painel_w, step=5.0)
            inversor = st.text_input("Inversor (modelo)", value=atual.inversor)
            potencia_inv = st.number_input("Potência do inversor (kW)", min_value=0.0, value=atual.potencia_inversor_kw, step=0.5)
        with c2:
            uc = st.text_input("Número da UC (quando a conta chegar)", value=atual.uc,
                               help="Com a UC informada, a unidade já fica marcada como geradora com os kWp certos e a primeira fatura entra sozinha.")
            custo = st.number_input("Investimento total (R$) — 0 para estimar", min_value=0.0, value=atual.custo_total or 0.0, step=1_000.0)
            financiado = st.number_input("Valor financiado (R$)", min_value=0.0, value=atual.valor_financiado or 0.0, step=1_000.0)
            parcela = st.number_input("Valor da parcela (R$)", min_value=0.0, value=atual.parcela_mensal or 0.0, step=50.0)
            parcelas = st.number_input("Quantidade de parcelas", min_value=0, value=atual.qtd_parcelas or 0, step=1)
            consumo = st.number_input("Consumo mensal estimado da unidade (kWh)", min_value=0.0, value=atual.consumo_kwh_mes or 0.0, step=50.0,
                                      help="Sem fatura ainda, é a principal incógnita: a economia depende do quanto a unidade consome. Use a média de uma unidade parecida ou a estimativa do integrador.")
            simult = st.slider("Consumo no mesmo instante da geração (%)", 0, 100, round(atual.simultaneidade * 100), step=5,
                               help="Parte do consumo que acontece de dia, com o sol. Essa energia não passa pela rede, não paga Fio B e vale a tarifa cheia. Uma clínica que funciona de dia fica em 40–60%.")
            operacao = st.date_input("Início da operação (previsto)", value=date.fromisoformat(atual.data_operacao) if atual.data_operacao else None, format="DD/MM/YYYY")
        enviar = st.form_submit_button("Salvar usina", type="primary")

    if not enviar:
        return
    if not nome.strip() or not paineis or not potencia:
        st.error("Preencha o nome, a quantidade de placas e a potência de cada placa.")
        return
    ampliacao.salvar(replace(
        atual, nome=nome.strip(), endereco=endereco.strip(), status=status or atual.status, paineis=int(paineis), potencia_painel_w=potencia,
        inversor=inversor.strip(), potencia_inversor_kw=potencia_inv, uc=uc, custo_total=custo or None, valor_financiado=financiado or None,
        parcela_mensal=parcela or None, qtd_parcelas=int(parcelas) or None, consumo_kwh_mes=consumo or None, simultaneidade=simult / 100,
        data_operacao=operacao.isoformat() if operacao else None))
    st.success("Usina salva.")
    st.rerun()


def _alerta_inversor(u: UsinaPlanejada) -> None:
    relacao = u.relacao_cc_ca
    if relacao is None:
        return
    if relacao > ampliacao.RELACAO_CC_CA_MAXIMA:
        st.warning(f"As placas somam {graficos.num(relacao, 2)}× a potência do inversor: acima de {ampliacao.RELACAO_CC_CA_MAXIMA} o inversor limita a geração nas horas de pico.",
                   icon=":material/warning:")
    else:
        st.info(f"Relação placas/inversor de {graficos.num(relacao, 2)}×: dentro do recomendado (até {ampliacao.RELACAO_CC_CA_MAXIMA}). "
                f"Em dias de sol forte o inversor corta uma fração pequena do pico, sem perda relevante no ano.", icon=":material/check_circle:")


def _premissas(p: painel_dados.Painel, u: UsinaPlanejada, rendimento: float, lacuna: float) -> Premissas:
    cfg = p.cfg
    kwp_existente = sum(x.kwp or 0 for x in unidades.listar() if x.geradora and x.uc != u.uc)
    custo_kwp = cfg.investimento_total / kwp_existente if cfg.investimento_total and kwp_existente else CUSTO_POR_KWP_SEM_REFERENCIA
    return Premissas(
        rendimento_kwh_kwp_mes=rendimento, valor_direto_kwh=p.modelo.bruto_kwh, valor_credito_kwh=ampliacao.valor_liquido_usina_nova(p.modelo),
        lacuna_outras_unidades_kwh=lacuna, custo_por_kwp_estimado=custo_kwp, reajuste_anual=cfg.reajuste_tarifa_anual,
        degradacao_anual=cfg.degradacao_anual, desconto_anual=benchmarks.cdi_anual_medio() or 0.13,
    )


def _destino_da_energia(r: ampliacao.ProjecaoUsina) -> None:
    linhas = [
        ("Consumida na hora na própria unidade", r.direto_kwh, "tarifa cheia, sem Fio B"),
        ("Créditos abatidos na própria unidade", r.creditos_unidade_kwh, "tarifa cheia menos Fio B e encargos"),
        ("Créditos para as outras unidades", r.creditos_outras_kwh, "só se houver consumo descoberto"),
        ("Sem consumo para abater", r.sobra_kwh, "vira saldo de créditos sem uso"),
    ]
    tabela = pd.DataFrame(linhas, columns=["Para onde vai", "kWh por mês", "Como vale"])
    st.dataframe(tabela, hide_index=True, width="stretch", alt="Para onde vai a energia da usina nova",
                 column_config={"kWh por mês": st.column_config.NumberColumn(format="%.0f")})


def _resultado(p: painel_dados.Painel, u: UsinaPlanejada) -> None:
    lista = unidades.listar()
    medido = ampliacao.rendimento_medido(p.df, lista, p.modelo.sazonalidade if p.modelo else None)
    coordenadas = [(u.lat, u.lon)] if u.lat and u.lon else p.coordenadas
    nasa = geracao.rendimento_kwh_kwp_mes(coordenadas, p.cfg.performance_ratio) if coordenadas else None
    if not p.modelo or not (medido or nasa):
        st.info("Preciso das faturas das usinas atuais (e das coordenadas delas, em **Unidades**) para projetar a geração.")
        return

    opcoes = [o for o, v in ((BASE_MEDIDA, medido), (BASE_NASA, nasa)) if v]
    base = st.segmented_control("Rendimento da usina", opcoes, default=opcoes[0],
                                help="Medido: quanto cada kWp das suas usinas injetou de fato nos últimos 6 meses (conservador, não conta o consumo na hora). "
                                     "Teórico: irradiação da NASA × eficiência do sistema.") or opcoes[0]
    rendimento = medido if base == BASE_MEDIDA else nasa
    outro = nasa if base == BASE_MEDIDA else medido

    demanda = expansao.analisar_demanda(p.df_economia, p.cfg.degradacao_anual, p.modelo.sazonalidade)
    lacuna = demanda.lacuna_em(0, p.cfg.degradacao_anual) if demanda else 0.0
    premissas = _premissas(p, u, rendimento, lacuna)
    consumo_assumido = not u.consumo_kwh_mes
    if consumo_assumido:
        u = replace(u, consumo_kwh_mes=round(u.kwp * rendimento, -1))
    projecao = ampliacao.projetar(u, premissas)
    r = projecao.expansao

    a, b, c, d = st.columns(4)
    a.metric("Potência das placas", f"{graficos.num(u.kwp, 2)} kWp", help=f"{u.paineis} placas × {u.potencia_painel_w:,.0f} W.")
    b.metric("Geração estimada", f"{graficos.num(projecao.geracao_kwh_mes)} kWh/mês", help=f"{graficos.num(rendimento)} kWh por kWp ao mês ({base.lower()}).")
    c.metric("Economia por mês (inicial)", graficos.rs(projecao.economia_mes))
    d.metric("Investimento" + (" (estimado)" if projecao.custo_estimado else ""), graficos.rs(projecao.custo_total))
    e, f, g, h = st.columns(4)
    e.metric("Payback", f"{r.payback_meses / 12:.1f} anos" if r.payback_meses else "não se paga em 25 anos")
    f.metric("TIR", f"{r.tir_anual * 100:.1f}% a.a." if r.tir_anual is not None and r.tir_anual > -0.99 else "—")
    g.metric("Valor presente (VPL)", graficos.rs(r.vpl), help=f"Ganho acima de aplicar o mesmo dinheiro no CDI de {premissas.desconto_anual * 100:.1f}% a.a.")
    h.metric("Parcela" if r.parcela_mensal else "Financiamento", graficos.rs(r.parcela_mensal) if r.parcela_mensal else "à vista",
             help=f"Juros implícitos de {(projecao.financiamento_juros_mensal or 0) * 100:.2f}% ao mês." if r.parcela_mensal else None)

    if consumo_assumido:
        st.warning(f"Ainda sem consumo informado: assumi que a unidade consome o que a usina gera ({graficos.num(u.consumo_kwh_mes)} kWh/mês). "
                   "Informe o consumo estimado em **Editar dados da usina** — a economia depende dele, porque as suas usinas atuais já produzem mais do que "
                   "as outras unidades consomem e a usina nova só gera economia onde ela mesma tem consumo.", icon=":material/bolt:")
    if projecao.custo_estimado:
        st.caption(f"Investimento estimado pelo custo por kWp da sua primeira usina ({graficos.rs_md(projecao.custo_total / u.kwp)}/kWp). "
                   "Informe o valor real do contrato acima para o retorno ficar exato.")
    if projecao.sobra_kwh > 0.5 and u.consumo_kwh_mes:
        st.info(f"{graficos.num(projecao.sobra_kwh)} kWh/mês não têm consumo para abater e viram créditos parados. Se isso se confirmar com as faturas, "
                "vale ajustar o rateio ou redimensionar o consumo da unidade.", icon=":material/info:")

    mensal = ampliacao.geracao_mensal(u.kwp, rendimento, p.modelo.sazonalidade)
    alternativa = ampliacao.geracao_mensal(u.kwp, outro, p.modelo.sazonalidade) if outro else None
    st.plotly_chart(graficos_analise.grafico_geracao_prevista(mensal, base, alternativa, BASE_NASA if base == BASE_MEDIDA else BASE_MEDIDA), width="stretch")
    _destino_da_energia(projecao)
    _carteira(p, u, projecao, demanda)
    _comparar_com_real(p, u, mensal)


def _carteira(p: painel_dados.Painel, u: UsinaPlanejada, projecao: ampliacao.ProjecaoUsina, demanda: expansao.Demanda | None) -> None:
    st.subheader("Com a usina nova, a carteira fica assim")
    kwp_atual = sum(x.kwp or 0 for x in unidades.listar() if x.geradora and x.uc != u.uc)
    producao_atual = demanda.producao_kwh_mes if demanda else 0.0
    a, b, c = st.columns(3)
    a.metric("Potência total (kWp)", graficos.num(kwp_atual + u.kwp, 1), delta=f"+{graficos.num(u.kwp, 1)} da usina nova")
    b.metric("Geração total (kWh/mês)", graficos.num(producao_atual + projecao.geracao_kwh_mes), delta=f"+{graficos.num(projecao.geracao_kwh_mes)}")
    c.metric("Sobra de geração das usinas atuais", graficos.num(demanda.sobra_kwh_mes) + " kWh/mês" if demanda else "—",
             help="Já existe geração sobrando nas usinas atuais; por isso a economia da usina nova vem do consumo da própria unidade.")


def _comparar_com_real(p: painel_dados.Painel, u: UsinaPlanejada, previsto: list[float]) -> None:
    if not u.uc:
        st.subheader("Próximo passo")
        st.markdown("Quando a primeira conta chegar: informe o **número da UC** acima e salve; depois envie o PDF em **Enviar faturas**. "
                    "A unidade já fica como geradora com os kWp certos e o retorno passa a usar a geração real.")
        return
    real = p.df[p.df["uc"] == u.uc].sort_values("mes_ref")
    if real.empty:
        st.info("A UC já está vinculada. Envie a primeira fatura em **Enviar faturas** para comparar a geração real com a prevista.")
        return
    tabela = real[["mes_ref", "injetado_kwh"]].copy()
    tabela["previsto"] = tabela["mes_ref"].map(lambda m: previsto[int(m[5:7]) - 1])
    tabela["mes_ref"] = tabela["mes_ref"].map(graficos.mes_legivel)
    st.subheader("Real × previsto")
    st.dataframe(tabela, hide_index=True, width="stretch", alt="Energia injetada real contra a prevista, mês a mês",
                 column_config={"mes_ref": "Mês", "injetado_kwh": st.column_config.NumberColumn("Injetado (real)", format="%.0f kWh"),
                                "previsto": st.column_config.NumberColumn("Geração prevista", format="%.0f kWh")})


def render() -> None:
    st.title("Nova usina")
    st.caption("Usinas em instalação: ficha técnica, geração esperada e retorno estimado antes de a primeira conta chegar.")
    p = painel_dados.carregar()
    usinas = ampliacao.listar()
    if p is None or not p.modelo:
        st.info("Envie as faturas das usinas atuais primeiro: a projeção da nova usina usa o rendimento e a tarifa delas.")
        return
    if not usinas:
        st.info("Nenhuma usina em instalação cadastrada. Preencha a ficha abaixo.")
        _formulario(None)
        return

    escolhida = usinas[0] if len(usinas) == 1 else st.selectbox("Usina", usinas, format_func=lambda x: x.nome)
    st.subheader(escolhida.nome)
    st.caption(f"{escolhida.status} · {escolhida.paineis} × {escolhida.potencia_painel_w:,.0f} W · {escolhida.inversor or 'inversor não informado'}"
               + (f" · {escolhida.endereco}" if escolhida.endereco else ""))
    _alerta_inversor(escolhida)
    _resultado(p, escolhida)

    with st.expander("Editar dados da usina"):
        _formulario(escolhida)
        if st.button("Excluir esta usina", key=f"excluir_{escolhida.id}"):
            ampliacao.excluir(escolhida.id)
            st.rerun()
    with st.expander("Cadastrar outra usina"):
        _formulario(None)
