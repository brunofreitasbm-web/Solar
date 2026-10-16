import streamlit as st

from solar import configuracoes
from solar.tarifa import aneel


def render() -> None:
    st.title("Configurações")

    cfg = configuracoes.carregar()
    st.subheader("Investimento")
    col1, col2 = st.columns(2)
    with col1:
        investimento = st.number_input("Investimento total (R$)", value=cfg.investimento_total, min_value=0.0)
    with col2:
        data_investimento = st.text_input("Data do investimento (AAAA-MM-DD)", value=cfg.data_investimento)

    st.subheader("Tributos e projeção")
    col3, col4, col5 = st.columns(3)
    with col3:
        icms = st.number_input("ICMS (%)", value=cfg.icms * 100, min_value=0.0, max_value=100.0) / 100
    with col4:
        pis_cofins = st.number_input("PIS/COFINS (%)", value=cfg.pis_cofins * 100, min_value=0.0, max_value=100.0) / 100
    with col5:
        performance_ratio = st.number_input("Performance ratio da usina", value=cfg.performance_ratio,
                                             min_value=0.1, max_value=1.0, step=0.01)
    col6, col7 = st.columns(2)
    with col6:
        degradacao = st.number_input("Degradação anual dos painéis (%)", value=cfg.degradacao_anual * 100,
                                      min_value=0.0, max_value=5.0, step=0.1) / 100
    with col7:
        reajuste = st.number_input("Reajuste anual estimado da tarifa (%)", value=cfg.reajuste_tarifa_anual * 100,
                                    min_value=0.0, max_value=30.0, step=0.5) / 100

    if st.button("Salvar configurações", type="primary"):
        configuracoes.salvar(configuracoes.Configuracoes(
            investimento_total=investimento, data_investimento=data_investimento,
            icms=icms, pis_cofins=pis_cofins, degradacao_anual=degradacao,
            reajuste_tarifa_anual=reajuste, performance_ratio=performance_ratio,
        ))
        st.success("Salvo.")

    st.divider()
    st.subheader("Tarifa de energia (ANEEL)")
    col_a, col_b = st.columns([3, 1])
    with col_b:
        atualizar = st.button("Atualizar tarifa")
    try:
        tarifa = aneel.tarifa_de_hoje(forcar=atualizar)
        with col_a:
            st.metric("Tarifa B1 Equatorial PA sem tributos", f"R$ {tarifa.sem_tributos:.4f}/kWh")
        c1, c2, c3 = st.columns(3)
        c1.metric("TE", f"R$ {tarifa.te_kwh:.4f}/kWh")
        c2.metric("TUSD", f"R$ {tarifa.tusd_kwh:.4f}/kWh")
        c3.metric("Com tributos", f"R$ {tarifa.com_tributos(icms, pis_cofins):.4f}/kWh")
        st.caption(f"Vigência: {tarifa.inicio_vigencia} a {tarifa.fim_vigencia} · consultado em {tarifa.consultado_em}")
    except aneel.FalhaTarifa as erro:
        st.error(str(erro))
