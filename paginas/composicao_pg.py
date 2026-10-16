import pandas as pd
import streamlit as st

from paginas import painel_dados
from solar import composicao, graficos, graficos_analise

PERIODOS = ("Últimos 12 meses", "Desde o início", "Um mês")


def _meses_do_periodo(meses: list[str], periodo: str) -> list[str] | None:
    if periodo == "Últimos 12 meses":
        return meses[-12:]
    if periodo == "Um mês":
        escolhido = st.selectbox("Mês", meses[::-1], format_func=graficos.mes_legivel, key="composicao_mes")
        return [escolhido]
    return None


def _projecao_fio_b(p: painel_dados.Painel, uc: str | None, meses: list[str]) -> None:
    """Fio B dos últimos 12 meses (qualquer período escolhido acima) levado a 100%."""
    modelo = p.modelo
    if not modelo or modelo.pct_base <= 0 or modelo.pct_base >= 1:
        return
    ao_ano = composicao.compor(p.df_economia, meses[-12:], uc).fio_b * 12 / len(meses[-12:])
    cheio = ao_ano / modelo.pct_base
    st.info(f"Hoje o Fio B está em {modelo.pct_base:.0%}. Com o mesmo consumo compensado e a tarifa de hoje, ele custaria "
            f"**{graficos.rs_md(ao_ano)} por ano** agora e **{graficos.rs_md(cheio)} por ano** quando chegar a 100% em 2029 "
            f"(+{graficos.rs_md(cheio - ao_ano)}/ano). É o principal custo da conta que ainda vai crescer.",
            icon=":material/trending_up:")


def _tabela_por_unidade(p: painel_dados.Painel, meses: list[str] | None) -> None:
    linhas = []
    for uc in p.df_economia["uc"].unique():
        c = composicao.compor(p.df_economia, meses, uc)
        if c.real or c.economia:
            linhas.append({"unidade": p.nomes.get(uc, uc), "sem_usina": c.sem_usina, "real": c.real, "economia": c.economia,
                           "fio_b": c.fio_b, "cip": c.cip, "multa_juros": c.multa_juros})
    tabela = pd.DataFrame(linhas).sort_values("real", ascending=False)
    moeda = lambda rotulo: st.column_config.NumberColumn(rotulo, format="R$ %.0f")
    st.dataframe(
        tabela, width="stretch", hide_index=True,
        column_config={"unidade": "Unidade", "sem_usina": moeda("Sem a usina"), "real": moeda("Conta real"),
                       "economia": moeda("Economia"), "fio_b": moeda("Fio B"), "cip": moeda("Iluminação pública"),
                       "multa_juros": moeda("Multa e juros")},
        alt="Tabela com a conta sem usina, a conta real e a economia de cada unidade no período",
    )


def render() -> None:
    st.title("Para onde vai cada real da conta")
    st.caption("Se a usina compensa toda a energia, por que ainda sobra conta? Aqui está a resposta, em reais, nas suas faturas.")
    p = painel_dados.carregar()
    if p is None:
        st.info("Nenhuma fatura salva ainda. Envie e confirme faturas para ver a composição.")
        return

    meses = sorted(p.df_economia["mes_ref"].unique())
    col_unidade, col_periodo = st.columns([1, 2])
    with col_unidade:
        nomes = {"Todas as unidades": None, **{p.nomes.get(uc, uc): uc for uc in p.df_economia["uc"].unique()}}
        uc = nomes[st.selectbox("Unidade", list(nomes))]
    with col_periodo:
        periodo = st.segmented_control("Período", PERIODOS, default=PERIODOS[0], key="composicao_periodo") or PERIODOS[0]
    selecionados = _meses_do_periodo(meses, periodo)

    c = composicao.compor(p.df_economia, selecionados, uc)
    if not c.real and not c.economia:
        st.warning("Não há faturas dessa unidade nesse período.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Conta sem a usina", graficos.rs(c.sem_usina))
    c2.metric("Conta real", graficos.rs(c.real), delta=f"-{graficos.rs(c.economia)}", delta_color="inverse")
    c3.metric("Economia", f"{100 * c.economia / c.sem_usina:.0f}% da conta" if c.sem_usina else "—")

    st.plotly_chart(graficos_analise.grafico_cascata(c), width="stretch")
    nao_evitavel = c.fio_b + c.beneficio_scee + c.cip + c.bandeira
    if c.real:
        st.markdown(f"**{100 * nao_evitavel / c.real:.0f}% da conta que sobra** é Fio B, benefício tarifário, iluminação pública e bandeira — "
                    f"custos que a compensação não elimina.")
    st.plotly_chart(graficos_analise.grafico_composicao(c), width="stretch")
    st.caption("Laranja: custos que nascem da compensação (Fio B e benefício tarifário). Cinza: custos que existiriam sem usina. "
               "Azul: energia que ainda é cobrada por kWh.")

    _projecao_fio_b(p, uc, meses)

    with st.expander("Como a economia é calculada", icon=":material/help:"):
        st.markdown(
            "A economia de cada fatura é **o que a energia compensada custaria pela tarifa cheia** (a mesma tarifa por kWh "
            "que a Equatorial cobra no consumo não compensado) **menos o Fio B e o benefício tarifário** que a própria fatura "
            "cobra por causa da compensação. Iluminação pública, multa, bandeira e custo de disponibilidade existem com ou "
            "sem usina e por isso não entram."
        )
    st.subheader("Por unidade")
    _tabela_por_unidade(p, selecionados)
