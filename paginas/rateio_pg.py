from datetime import date

import streamlit as st

from paginas import painel_dados, ui
from solar import config, graficos, graficos_analise, rateio, rateio_pdf

USINAS_GERADORAS = ("231236701340", "458420701358")


def _pedido_para_a_distribuidora(r: rateio.ResultadoRateio) -> str:
    linhas = [f"{l.unidade}: {l.sugerido_pct:.2f}%".replace(".", ",") for l in r.tabela.itertuples() if l.sugerido_pct > 0]
    return "Percentual de rateio sugerido (aplicar a cada usina geradora):\n" + "\n".join(linhas)


def _aviso_sobra_das_prioritarias(r: rateio.ResultadoRateio, prioridade: list[str]) -> None:
    sobrando = r.tabela[r.tabela["unidade"].isin(prioridade) & (r.tabela["alocado_sugerido_kwh"] > r.tabela["demanda_kwh"] + 50)]
    for l in sobrando.itertuples():
        guardado = f", sobre {graficos.num(l.saldo_kwh)} kWh já parados lá" if l.saldo_kwh > 100 else ""
        st.warning(f"{l.unidade} vai receber {graficos.num(l.alocado_sugerido_kwh)} kWh/mês para um consumo de {graficos.num(l.demanda_kwh)} kWh/mês: "
                   f"{graficos.num(l.alocado_sugerido_kwh - l.demanda_kwh)} kWh/mês viram crédito acumulado{guardado}.", icon=":material/inventory_2:")


def _botao_lista(uc_geradora: str, itens: list[dict]) -> None:
    info = rateio_pdf.DADOS_UNIDADES[uc_geradora]
    nome_arquivo = f"Lista_de_Rateio_{info['apelido']}.pdf"

    # Gerado só no clique: o PDF não precisa ser redesenhado a cada ajuste de filtro.
    def _gerar() -> bytes:
        return rateio_pdf.desenhar_pdf_rateio(
            caminho_saida=str(config.PASTA_DADOS / "rateio" / nome_arquivo), conta_contrato_geradora=info["conta_contrato"],
            local_solicitacao=info["municipio"], data_solicitacao=date.today().strftime("%d/%m/%Y"), itens_rateio=itens,
        ).read_bytes()

    st.download_button(
        f"Baixar lista — Usina {info['apelido']}", data=_gerar, file_name=nome_arquivo, mime="application/pdf",
        type="primary", width="stretch", icon=":material/picture_as_pdf:", on_click="ignore",
        help=f"Formulário preenchido com a Conta Contrato de {info['apelido']} ({info['conta_contrato']}) e os percentuais sugeridos.",
    )


def _listas_oficiais(r: rateio.ResultadoRateio) -> None:
    st.subheader("Listas de rateio prontas para a Equatorial")
    st.caption("No formato oficial da Equatorial Pará, com contas contrato, classes, endereços e os percentuais sugeridos acima.")
    itens = rateio_pdf.montar_itens_rateio({l.unidade: l.sugerido_pct for l in r.tabela.itertuples() if l.sugerido_pct > 0})
    for coluna, uc in zip(st.columns(len(USINAS_GERADORAS)), USINAS_GERADORAS):
        with coluna:
            _botao_lista(uc, itens)


def render() -> None:
    st.title("Rateio de créditos")
    st.caption("Cada usina distribui a energia entre as unidades por percentual. Aqui está se esses percentuais "
               "combinam com o consumo real e o que pedir para a Equatorial mudar.")
    p = painel_dados.carregar()
    if p is None:
        ui.sem_faturas()
        return

    horizonte = st.slider("Em quantos meses consumir o saldo de créditos já acumulado", 3, 36, 12,
                          help="Unidades com saldo acumulado recebem menos energia nova até gastá-lo; a sobra vai para quem está descoberto.")
    nome_uc = {nome: uc for uc, nome in p.nomes.items()}
    maior_saldo = p.df_economia.sort_values("mes_ref").groupby("uc").tail(1).nlargest(1, "saldo_creditos_kwh")["uc"].map(p.nomes).tolist()
    col_esvaziar, col_prioridade = st.columns(2)
    with col_esvaziar:
        esvaziar = st.multiselect("Esvaziar o saldo de créditos de", list(nome_uc), default=maior_saldo,
                                  help="Essas unidades passam a receber 0% das usinas; o consumo delas gasta o saldo acumulado.")
    with col_prioridade:
        prioridade = st.multiselect("Enviar a sobra de energia preferencialmente para", list(nome_uc),
                                    default=[n for n in ("101", "701") if n in nome_uc],
                                    help="Essas unidades são cobertas por inteiro e recebem a energia que sobra das usinas.")
    r = rateio.analisar(p.df_economia, p.nomes, horizonte_saldo_meses=horizonte,
                        esvaziar=frozenset(nome_uc[n] for n in esvaziar), prioritarias=frozenset(nome_uc[n] for n in prioridade))
    if r is None:
        ui.estado_vazio("**Nenhuma unidade geradora com energia injetada.** Marque quais unidades têm usina para calcular o rateio.",
                        "unidades", "Marcar as geradoras")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Geração das usinas (kWh/mês)", graficos.num(r.producao_kwh_mes), border=True)
    c2.metric("Compensável (kWh/mês)", graficos.num(r.demanda_kwh_mes),
              help="Consumo de cada unidade acima do custo de disponibilidade (100 kWh nas trifásicas).", border=True)
    c3.metric("Sem cobertura hoje (kWh/mês)", graficos.num(r.descoberto_atual_kwh),
              delta=f"{graficos.rs(r.ganho_mensal_rs)}/mês a mais na conta" if r.ganho_mensal_rs > 0.5 else None, delta_color="inverse", border=True)
    c4.metric("Saldo parado (kWh)", graficos.num(r.saldo_parado_kwh), delta=graficos.rs(r.saldo_parado_rs), delta_color="off",
              help="Créditos acumulados nas unidades, valorizados pelo que cada kWh compensado vale hoje. Vencem em 60 meses.", border=True)

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
    _aviso_sobra_das_prioritarias(r, prioridade)
    st.caption("Use o mesmo percentual em cada usina geradora (a soma de cada usina precisa fechar 100%). A mudança vale a partir "
               "do ciclo seguinte ao pedido. Os percentuais usam o consumo e a geração médios dos últimos 6 meses — revise se algo mudar.")

    st.divider()
    _listas_oficiais(r)
