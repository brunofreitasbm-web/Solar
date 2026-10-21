import streamlit as st

from paginas import painel_dados, ui
from datetime import date

from solar import graficos, pagamentos, vencimentos
from solar.faturas import repositorio


def _situacao(linha) -> str:
    if linha.dias > 1:
        texto = f"vence em {linha.dias} dias"
    elif linha.dias == 1:
        texto = "vence amanhã"
    elif linha.dias == 0:
        texto = "vence hoje"
    else:
        texto = f"venceu há {-linha.dias} dias — confirme o pagamento"
    return texto + (" · fatura ainda não carregada" if linha.aguardando_fatura else "")


def _a_pagar(p: painel_dados.Painel) -> None:
    st.subheader("Faturas a pagar")
    abertas = pagamentos.a_pagar(p.df, p.nomes)
    if abertas.empty:
        st.success("Todas as faturas carregadas estão pagas.", icon=":material/check_circle:")
        return
    st.caption("Última fatura carregada de cada unidade que ainda não foi marcada como paga.")
    for l in abertas.itertuples():
        situacao = f"venceu há {-l.dias} dias" if l.vencida else ("vence hoje" if l.dias == 0 else f"vence em {l.dias} dias")
        with st.container(border=True):
            c1, c2 = st.columns([3, 2], vertical_alignment="center")
            c1.markdown(f"**{l.unidade}** · fatura {l.mes_ref} · {graficos.rs(l.total_rs, 2)}  \n"
                        f"{':red[' + situacao + ']' if l.vencida else situacao} ({l.vencimento.strftime('%d/%m/%Y')})")
            if c2.button("Marcar como paga", key=f"paga_{l.uc}_{l.mes_ref}", icon=":material/check:", width="stretch"):
                repositorio.marcar_paga(l.uc, l.mes_ref, date.today().isoformat(), l.total_rs)
                st.cache_data.clear()
                ui.avisar(f"Fatura {l.mes_ref} de {l.unidade} marcada como paga.")
                st.rerun()


def render() -> None:
    st.title("Vencimentos")
    st.caption("Previsão do próximo vencimento de cada unidade e o custo dos atrasos que já aconteceram.")
    p = painel_dados.carregar()
    if p is None:
        ui.sem_faturas()
        return

    previsoes = vencimentos.proximos_vencimentos(p.df, p.nomes)
    if previsoes.empty:
        ui.estado_vazio("**As faturas salvas não trazem a data de vencimento.** Reenvie os PDFs para o app ler essa informação.",
                        "enviar-faturas", "Reenviar faturas")
        return

    aguardando = previsoes[previsoes["aguardando_fatura"]]
    if not aguardando.empty:
        st.warning("Estas faturas já deveriam ter saído e ainda não foram carregadas: " + ", ".join(aguardando["unidade"]) +
                   ". Envie os PDFs para manter o histórico sem buracos.", icon=":material/upload_file:")
        ui.link_para("enviar-faturas", "Enviar faturas")

    _a_pagar(p)
    previsoes = previsoes.assign(situacao=[_situacao(l) for l in previsoes.itertuples()])
    st.dataframe(
        previsoes, width="stretch", hide_index=True,
        column_order=["unidade", "vencimento_previsto", "total_rs", "situacao", "ultima_fatura", "ultimo_vencimento"],
        column_config={
            "unidade": "Unidade",
            "vencimento_previsto": st.column_config.DateColumn("Vencimento previsto", format="DD/MM/YYYY"),
            "total_rs": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
            "situacao": "Situação",
            "ultima_fatura": "Última fatura carregada",
            "ultimo_vencimento": st.column_config.DateColumn("Último vencimento", format="DD/MM/YYYY"),
        },
        alt="Tabela com o próximo vencimento previsto de cada unidade",
    )

    st.caption("A data é prevista pelo ciclo de leitura da última fatura e pode variar alguns dias. Confira no site ou app da Equatorial.")
    _lembretes(previsoes)
    _encargos(p)


def _data_br(valor) -> str:
    return valor.strftime("%d/%m/%Y") if hasattr(valor, "strftime") else str(valor)


def _lembretes(previsoes) -> None:
    st.subheader("Lembretes na agenda")
    st.caption(f"Os eventos levam valor, Chave Pix e convite para `{vencimentos.EMAIL_ISABELA}`.")
    st.download_button(
        "Baixar todos os lembretes (.ics)", vencimentos.gerar_ics(previsoes, meses=6).encode("utf-8"),
        file_name="vencimentos_solar_com_pix.ics", mime="text/calendar", icon=":material/calendar_add_on:", on_click="ignore",
        help="Importe no Google Agenda: cria os eventos dos próximos 6 meses com aviso prévio.",
    )
    with st.expander("Ou adicione uma fatura por vez no Google Agenda", icon=":material/event:"):
        for _, prev in previsoes.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([3, 2], vertical_alignment="center")
                c1.markdown(f"**{prev['unidade']}** · :material/event: {_data_br(prev['vencimento_previsto'])} · {graficos.rs(prev['total_rs'])}")
                c2.link_button("Adicionar no Google Agenda", vencimentos.link_google_agenda(prev), icon=":material/open_in_new:",
                               width="stretch", help="Abre o Google Agenda já preenchido com valor, Pix e Isabela convidada.")
                if prev.get("pix_copia_cola"):
                    st.code(prev["pix_copia_cola"], language="text")


def _encargos(p: painel_dados.Painel) -> None:
    st.subheader("Quanto os atrasos já custaram")
    encargos = vencimentos.encargos_por_atraso(p.df, p.nomes)
    total_encargos = encargos["encargos_rs"].sum()
    com_encargo, faturas = int(encargos["com_encargo"].sum()), int(encargos["faturas"].sum())
    c1, c2, c3 = st.columns(3)
    c1.metric("Multa, juros e correção pagos", graficos.rs(total_encargos, 2), border=True)
    c2.metric("Faturas pagas com encargo", f"{com_encargo} de {faturas}", delta=f"{100 * com_encargo / max(faturas, 1):.0f}%", delta_color="off", border=True)
    c3.metric("Por mês, em média", graficos.rs(total_encargos / max(p.df['mes_ref'].nunique(), 1), 2), border=True)
    if faturas and com_encargo / faturas > 0.3:
        st.warning("A maior parte das faturas é paga depois do vencimento. Colocar as contas em débito automático zera esse custo "
                   "e dispensa os lembretes.", icon=":material/autopay:")
    st.dataframe(
        encargos, width="stretch", hide_index=True,
        column_order=["unidade", "faturas", "com_encargo", "pct_faturas", "multa_rs", "juros_rs", "encargos_rs"],
        column_config={
            "unidade": "Unidade", "faturas": "Faturas", "com_encargo": "Com encargo",
            "pct_faturas": st.column_config.ProgressColumn("% com encargo", format="%.0f%%", min_value=0, max_value=100),
            "multa_rs": st.column_config.NumberColumn("Multa", format="R$ %.2f"),
            "juros_rs": st.column_config.NumberColumn("Juros e correção", format="R$ %.2f"),
            "encargos_rs": st.column_config.NumberColumn("Total", format="R$ %.2f"),
        },
        alt="Tabela com multa e juros pagos por unidade",
    )
