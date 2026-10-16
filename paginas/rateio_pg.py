import streamlit as st

from paginas import painel_dados
from solar import graficos, graficos_analise, rateio


def _pedido_para_a_distribuidora(r: rateio.ResultadoRateio) -> str:
    linhas = [f"{l.unidade}: {l.sugerido_pct:.2f}%".replace(".", ",") for l in r.tabela.itertuples() if l.sugerido_pct > 0]
    return "Percentual de rateio sugerido (aplicar a cada usina geradora):\n" + "\n".join(linhas)


def render() -> None:
    st.title("Rateio de créditos")
    st.caption("Cada usina distribui a energia entre as unidades por percentual. Aqui está se esses percentuais "
               "combinam com o consumo real e o que pedir para a Equatorial mudar.")
    p = painel_dados.carregar()
    if p is None:
        st.info("Nenhuma fatura salva ainda.")
        return

    horizonte = st.slider("Em quantos meses consumir o saldo de créditos já acumulado", 3, 36, 12,
                          help="Unidades com saldo acumulado recebem menos energia nova até gastá-lo; a sobra vai para quem está descoberto.")
    r = rateio.analisar(p.df_economia, p.nomes, horizonte_saldo_meses=horizonte)
    if r is None:
        st.info("Não encontrei unidades geradoras com energia injetada. Marque as geradoras em **Unidades**.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Geração das usinas (kWh/mês)", graficos.num(r.producao_kwh_mes))
    c2.metric("Compensável (kWh/mês)", graficos.num(r.demanda_kwh_mes),
              help="Consumo de cada unidade acima do custo de disponibilidade (100 kWh nas trifásicas).")
    c3.metric("Sem cobertura hoje (kWh/mês)", graficos.num(r.descoberto_atual_kwh),
              delta=f"{graficos.rs(r.ganho_mensal_rs)}/mês a mais na conta" if r.ganho_mensal_rs > 0.5 else None, delta_color="inverse")
    c4.metric("Saldo parado (kWh)", graficos.num(r.saldo_parado_kwh), delta=graficos.rs(r.saldo_parado_rs), delta_color="off",
              help="Créditos acumulados nas unidades, valorizados pelo que cada kWh compensado vale hoje. Vencem em 60 meses.")

    if r.ganho_mensal_rs > 0.5 or r.saldo_parado_kwh > 100:
        st.warning(
            f"Com o rateio de hoje, cerca de {graficos.num(r.descoberto_atual_kwh)} kWh/mês de consumo ainda são pagos a tarifa cheia "
            f"({graficos.rs_md(r.ganho_mensal_rs)}/mês) enquanto {graficos.num(r.saldo_parado_kwh)} kWh de créditos ficam parados em outras unidades.",
            icon=":material/swap_horiz:")
    else:
        st.success("O rateio atual está equilibrado com o consumo.", icon=":material/check_circle:")

    st.plotly_chart(graficos_analise.grafico_rateio(r.tabela), width="stretch")
    st.dataframe(
        r.tabela, width="stretch", hide_index=True,
        column_order=["unidade", "consumo_kwh", "rateio_atual", "alocado_atual_kwh", "sugerido_pct",
                      "alocado_sugerido_kwh", "saldo_kwh", "meses_para_zerar_saldo"],
        column_config={
            "unidade": "Unidade",
            "consumo_kwh": st.column_config.NumberColumn("Consumo", format="%.0f kWh"),
            "rateio_atual": "Rateio de hoje",
            "alocado_atual_kwh": st.column_config.NumberColumn("Recebe hoje", format="%.0f kWh"),
            "sugerido_pct": st.column_config.NumberColumn("% sugerido", format="%.2f%%"),
            "alocado_sugerido_kwh": st.column_config.NumberColumn("Recebe sugerido", format="%.0f kWh"),
            "saldo_kwh": st.column_config.NumberColumn("Saldo de créditos", format="%.0f kWh"),
            "meses_para_zerar_saldo": st.column_config.NumberColumn("Meses para gastar o saldo", format="%.0f"),
        },
        alt="Tabela com o consumo, o rateio de hoje e o rateio sugerido de cada unidade",
    )

    st.subheader("O que pedir à Equatorial")
    st.code(_pedido_para_a_distribuidora(r), language=None)
    st.caption("Use o mesmo percentual em cada usina geradora (a soma de cada usina precisa fechar 100%). A mudança vale a partir "
               "do ciclo seguinte ao pedido. Os percentuais usam o consumo e a geração médios dos últimos 6 meses — revise se algo mudar.")
