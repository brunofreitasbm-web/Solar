import streamlit as st

from paginas import painel_dados
from solar import graficos, vencimentos


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


def render() -> None:
    st.title("Vencimentos")
    st.caption("Previsão do próximo vencimento de cada unidade e o custo dos atrasos que já aconteceram.")
    p = painel_dados.carregar()
    if p is None:
        st.info("Nenhuma fatura salva ainda.")
        return

    previsoes = vencimentos.proximos_vencimentos(p.df, p.nomes)
    if previsoes.empty:
        st.info("As faturas salvas não trazem a data de vencimento. Reenvie-as para atualizar.")
        return

    aguardando = previsoes[previsoes["aguardando_fatura"]]
    if not aguardando.empty:
        st.warning("Estas faturas já deveriam ter saído e ainda não foram carregadas: " + ", ".join(aguardando["unidade"]) +
                   ". Baixe os PDFs e envie em **Enviar faturas** para manter o histórico sem buracos.", icon=":material/upload_file:")

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

    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        st.download_button(
            "Baixar lembretes (.ics com cópia para Isabela)", vencimentos.gerar_ics(previsoes, meses=6).encode("utf-8"),
            file_name="vencimentos_solar_com_pix.ics", mime="text/calendar", icon=":material/calendar_add_on:",
            help="Importe no Google Agenda: cria eventos com aviso prévio, cópia para Isabela, valor e Chave Pix.",
        )
    with col_btn2:
        st.caption(f"📅 Convidada automática nos eventos: `{vencimentos.EMAIL_ISABELA}`")

    # Atalhos rápidos para adicionar cada fatura direto no Google Agenda com 1 clique
    with st.expander("⚡ Adicionar direto no Google Agenda (1 clique com PIX e cópia para Isabela)", expanded=True):
        for _, prev in previsoes.iterrows():
            c1, c2, c3, c4 = st.columns([2, 1.5, 1.5, 2])
            c1.write(f"**{prev['unidade']}**")
            venc_fmt = prev['vencimento_previsto'].strftime('%d/%m/%Y') if hasattr(prev['vencimento_previsto'], 'strftime') else str(prev['vencimento_previsto'])
            c2.write(f"📅 {venc_fmt}")
            c3.write(f"💰 {graficos.rs(prev['total_rs'])}")
            link_cal = vencimentos.link_google_agenda(prev)
            c4.link_button("📅 Adicionar no Google Agenda", link_cal, help="Abre o Google Agenda pré-preenchido com valor, PIX e Isabela convidada")
            if prev.get("pix_copia_cola"):
                st.code(prev["pix_copia_cola"], language="text")

    st.caption("A data é prevista pelo ciclo de leitura da última fatura e pode variar alguns dias. Confira no site ou app da Equatorial.")

    st.subheader("Quanto os atrasos já custaram")
    encargos = vencimentos.encargos_por_atraso(p.df, p.nomes)
    total_encargos = encargos["encargos_rs"].sum()
    com_encargo, faturas = int(encargos["com_encargo"].sum()), int(encargos["faturas"].sum())
    c1, c2, c3 = st.columns(3)
    c1.metric("Multa, juros e correção pagos", graficos.rs(total_encargos, 2))
    c2.metric("Faturas pagas com encargo", f"{com_encargo} de {faturas}", delta=f"{100 * com_encargo / faturas:.0f}%", delta_color="off")
    c3.metric("Por mês, em média", graficos.rs(total_encargos / max(p.df['mes_ref'].nunique(), 1), 2))
    if com_encargo / faturas > 0.3:
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
