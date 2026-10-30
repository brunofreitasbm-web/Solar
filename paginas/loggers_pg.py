from datetime import date, datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from paginas import painel_dados, ui
from solar.loggers import coleta, comparativo, repositorio, strings

MINUTOS_ONLINE = 15
DIAS_HISTORICO = 30
SITUACAO_CICLO = {
    "ok": "Coerente",
    "inconsistente": ":red[Injetado maior que o gerado]",
    "sem_dados": "Sem leituras do logger nas datas do ciclo",
}


def _unidades_geradoras(p: painel_dados.Painel | None) -> dict[str, str]:
    if p is None:
        return {}
    ucs = p.df[p.df["geradora"] == 1]["uc"].unique()
    return {uc: p.nomes.get(uc, uc) for uc in ucs}


def _minutos_desde(lida_em: str) -> float:
    return (datetime.now() - datetime.fromisoformat(lida_em)).total_seconds() / 60


def _formulario_novo(unidades: dict[str, str]) -> None:
    with st.expander("Adicionar data logger", expanded=not repositorio.listar_loggers(), icon=":material/add:"):
        with st.form("novo_logger", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nome = c1.text_input("Nome", placeholder="Casa de praia - inversor 1")
            sn = c2.text_input("Número de série do inversor", placeholder="AP00100522440448",
                               help="Está no app Solplanet, na tela do inversor.")
            c3, c4 = st.columns([3, 1])
            ip = c3.text_input("Endereço IP do logger", placeholder="192.168.0.50",
                               help="Veja na lista de dispositivos do roteador. Deixe o IP fixo para ele não mudar.")
            porta = c4.number_input("Porta", value=8484, min_value=1, max_value=65535)
            uc = st.selectbox("Unidade geradora (para comparar com a fatura)", [None, *unidades],
                              format_func=lambda u: "Escolher depois" if u is None else unidades[u])
            if st.form_submit_button("Salvar logger", icon=":material/save:", type="primary"):
                if not (nome.strip() and sn.strip() and ip.strip()):
                    st.error("Preencha nome, número de série e IP.")
                else:
                    repositorio.cadastrar_logger(sn.strip(), nome.strip(), ip.strip(), int(porta), uc)
                    ui.avisar(f"Logger '{nome.strip()}' salvo. A primeira leitura chega em até 5 minutos.")
                    st.rerun()


def _strings(logger: dict, leitura: dict) -> None:
    tensoes, correntes = leitura["tensoes_pv_v"], leitura["correntes_pv_a"]
    if not tensoes:
        return
    em_falha = strings.strings_em_falha(logger["sn"], leitura)
    for i, (v, a) in enumerate(zip(tensoes, correntes), start=1):
        texto = f"String {i}: {v:.0f} V · {a:.2f} A"
        st.caption(f":red[:material/error: {texto}]" if i - 1 in em_falha else texto)
    if em_falha:
        nomes = ", ".join(str(i + 1) for i in em_falha)
        st.error(f"A string {nomes} está sem tensão com o inversor gerando. Confira conectores e disjuntores dos painéis.")


def _vinculo(logger: dict, unidades: dict[str, str]) -> None:
    opcoes = [None, *unidades]
    atual = logger["uc"] if logger["uc"] in opcoes else None
    escolhida = st.selectbox("Unidade geradora", opcoes, index=opcoes.index(atual), key=f"uc_{logger['sn']}",
                             format_func=lambda u: "Sem vínculo" if u is None else unidades[u])
    if escolhida != atual:
        repositorio.vincular_unidade(logger["sn"], escolhida)
        ui.avisar("Vínculo salvo.")
        st.rerun()


def _cartao(logger: dict, unidades: dict[str, str]) -> None:
    leitura = repositorio.ultima_leitura(logger["sn"])
    with st.container(border=True):
        st.markdown(f"**{logger['nome']}** · `{logger['ip']}`")
        if not leitura:
            st.caption("Sem leituras ainda. Clique em *Coletar agora* ou aguarde a próxima coleta automática.")
        else:
            minutos = _minutos_desde(leitura["lida_em"])
            if minutos <= MINUTOS_ONLINE:
                st.caption(":green[:material/circle:] Online")
            else:
                st.caption(f":gray[:material/circle:] Sem resposta há {int(minutos // 60)}h{int(minutos % 60):02d}min "
                           "(normal à noite, quando o inversor desliga)")
            c1, c2 = st.columns(2)
            c1.metric("Potência agora", f"{leitura['potencia_w'] / 1000:.2f} kW")
            c2.metric("Gerou hoje", f"{leitura['energia_dia_kwh']:.1f} kWh")
            c3, c4 = st.columns(2)
            c3.metric("Total acumulado", f"{leitura['energia_total_kwh']:,.0f} kWh".replace(",", "."))
            c4.metric("Temperatura", f"{leitura['temperatura_c']:.0f} °C")
            _strings(logger, leitura)
            if leitura["codigo_erro"]:
                st.error(f"O inversor reportou o código de erro {leitura['codigo_erro']}. Veja o manual da Solplanet.")
        _vinculo(logger, unidades)
        ui.botao_excluir("Remover logger", f"Remover **{logger['nome']}** e todo o histórico de leituras dele?",
                         lambda: repositorio.remover_logger(logger["sn"]), "Logger removido.", f"rm_{logger['sn']}")


def _curva(loggers: list[dict], dia: date) -> None:
    fig = go.Figure()
    for l in loggers:
        pontos = repositorio.curva_do_dia(l["sn"], dia.isoformat())
        if pontos:
            df = pd.DataFrame(pontos)
            fig.add_scatter(x=pd.to_datetime(df["lida_em"]), y=df["potencia_w"] / 1000, name=l["nome"], mode="lines")
    if not fig.data:
        st.info("Nenhuma leitura neste dia.")
        return
    fig.update_layout(yaxis_title="kW", margin=dict(t=16, b=0, l=0, r=0), hovermode="x unified", legend_orientation="h")
    st.plotly_chart(fig, width="stretch")


def _historico(loggers: list[dict]) -> None:
    linhas = [{"dia": d["dia"], "logger": l["nome"], "kwh": d["kwh"]}
              for l in loggers for d in repositorio.geracao_diaria(l["sn"])]
    if not linhas:
        st.info("O histórico diário aparece depois do primeiro dia completo de coleta.")
        return
    df = pd.DataFrame(linhas)
    df = df[df["dia"] >= (date.today() - timedelta(days=DIAS_HISTORICO)).isoformat()]
    fig = go.Figure()
    for nome, grupo in df.groupby("logger"):
        fig.add_bar(x=grupo["dia"], y=grupo["kwh"], name=nome)
    fig.update_layout(barmode="stack", yaxis_title="kWh", margin=dict(t=16, b=0, l=0, r=0), legend_orientation="h")
    st.plotly_chart(fig, width="stretch")
    st.caption(f"Total nos últimos {DIAS_HISTORICO} dias: {df['kwh'].sum():,.0f} kWh".replace(",", "."))


def _comparativo(loggers: list[dict], p: painel_dados.Painel | None, unidades: dict[str, str]) -> None:
    st.subheader("Comparativo com a Equatorial")
    vinculadas = [uc for uc in unidades if any(l["uc"] == uc for l in loggers)]
    if p is None or not vinculadas:
        st.info("Vincule os loggers a uma unidade geradora (no cartão de cada um) para comparar com as faturas.")
        return
    st.caption("Geração medida pelos inversores no intervalo entre duas leituras do medidor, contra a energia injetada "
               "que a Equatorial faturou. O injetado é menor que o gerado porque parte da energia é consumida no local; "
               "a diferença é o autoconsumo estimado. A margem de erro é de cerca de um dia de geração por ciclo.")
    for uc in vinculadas:
        ciclos = comparativo.ciclos_da_unidade(uc, p.df)
        st.markdown(f"**{unidades[uc]}**")
        if not ciclos:
            st.caption("Ainda não há dois ciclos de fatura com data de emissão para comparar. Envie as faturas em PDF.")
            continue
        tabela = pd.DataFrame([{
            "Fatura": c.mes_ref,
            "Ciclo": f"{c.inicio:%d/%m} a {c.fim:%d/%m}",
            "Gerado (logger, kWh)": None if c.geracao_kwh is None else round(c.geracao_kwh),
            "Injetado (Equatorial, kWh)": round(c.injetado_kwh),
            "Autoconsumo estimado (kWh)": None if c.autoconsumo_kwh is None else round(c.autoconsumo_kwh),
            "Situação": SITUACAO_CICLO[c.situacao],
        } for c in ciclos])
        st.dataframe(tabela, hide_index=True, width="stretch")
        if any(c.situacao == "inconsistente" for c in ciclos):
            st.warning("Em algum ciclo a Equatorial faturou mais energia injetada do que os inversores geraram. "
                       "Confira se os loggers cobrem toda a usina e se o contador do inversor não foi zerado.")


def _coletar_agora() -> None:
    with st.spinner("Consultando os loggers..."):
        resultado = coleta.coletar_todos()
    falhas = {nome: erro for nome, erro in resultado.items() if erro}
    for nome, erro in falhas.items():
        st.warning(f"**{nome}:** {erro}")
    if resultado and not falhas:
        ui.avisar("Leituras atualizadas.")
        st.rerun()


def render() -> None:
    st.title("Geração dos loggers")
    st.caption("Geração real lida direto dos inversores Solplanet, sem depender do aplicativo. "
               "A coleta é automática a cada 5 minutos enquanto o app estiver aberto.")
    loggers = repositorio.listar_loggers()
    painel = painel_dados.carregar()
    unidades = _unidades_geradoras(painel)
    _formulario_novo(unidades)
    if not loggers:
        return

    if st.button("Coletar agora", icon=":material/refresh:"):
        _coletar_agora()

    for coluna, logger in zip(st.columns(min(len(loggers), 3)), loggers):
        with coluna:
            _cartao(logger, unidades)

    st.subheader("Potência ao longo do dia")
    dia = st.date_input("Dia", value=date.today(), max_value=date.today(), format="DD/MM/YYYY")
    _curva(loggers, dia)

    st.subheader("Geração por dia")
    _historico(loggers)

    _comparativo(loggers, painel, unidades)
