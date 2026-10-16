from datetime import datetime
from pathlib import Path

import streamlit as st

from solar import backup, config, configuracoes
from solar.tarifa import aneel


def _bloco_backup(cfg: configuracoes.Configuracoes) -> str:
    """Desenha a seção de backup e devolve a pasta digitada (salva junto com as configurações)."""
    st.divider()
    st.subheader("Backup")
    st.caption(f"O app faz um backup do banco automaticamente a cada {config.DIAS_ENTRE_BACKUPS_AUTOMATICOS} dias e guarda os "
               f"{config.BACKUPS_MANTIDOS} mais recentes. Aponte a pasta para o Google Drive, OneDrive ou Dropbox do seu PC "
               "para a cópia sair do computador sozinha.")
    pasta = st.text_input("Pasta dos backups", value=cfg.pasta_backup, placeholder=str(config.PASTA_BACKUP),
                          help="Vazio usa a pasta 'backups' dentro do projeto. Salve as configurações para aplicar.")
    incluir_pdfs = st.checkbox("Incluir os PDFs das faturas", value=False, help="Aumenta bastante o tamanho; o banco já guarda tudo o que foi lido.")

    if st.button("Fazer backup agora", icon=":material/backup:"):
        try:
            arquivo = backup.fazer_backup(pasta or None, incluir_pdfs)
            st.success(f"Backup salvo em {arquivo} ({arquivo.stat().st_size / 1024:,.0f} KB).")
        except OSError as erro:
            st.error(f"Não consegui salvar o backup nessa pasta: {erro}. Confira se ela existe e se você pode gravar nela.")

    try:
        existentes = backup.listar_backups(pasta or None)
    except OSError:
        existentes = []
    if not existentes:
        st.info("Ainda não há backups nessa pasta.")
        return pasta
    st.dataframe(
        [{"arquivo": a.name, "feito_em": datetime.fromtimestamp(a.stat().st_mtime), "tamanho_kb": a.stat().st_size / 1024} for a in existentes[:5]],
        hide_index=True, width="stretch",
        column_config={"arquivo": "Arquivo", "feito_em": st.column_config.DatetimeColumn("Feito em", format="DD/MM/YYYY HH:mm"),
                       "tamanho_kb": st.column_config.NumberColumn("Tamanho", format="%.0f KB")},
        alt="Lista dos backups mais recentes",
    )
    with st.expander("Restaurar um backup", icon=":material/restore:"):
        escolhido = st.selectbox("Backup", existentes, format_func=lambda a: a.name)
        confirma = st.checkbox("Entendo que isso substitui todos os dados atuais (uma cópia do banco de hoje é guardada ao lado).")
        if st.button("Restaurar", disabled=not confirma, type="primary"):
            seguranca = backup.restaurar_backup(Path(escolhido))
            st.cache_data.clear()
            st.success(f"Banco restaurado. A cópia do banco anterior ficou em {seguranca.name}. Recarregue a página.")
    return pasta


def render() -> None:
    st.title("Configurações")

    cfg = configuracoes.carregar()
    st.subheader("Investimento")
    col1, col2 = st.columns(2)
    with col1:
        investimento = st.number_input("Investimento total (R$)", value=cfg.investimento_total, min_value=0.0)
    with col2:
        data_investimento = st.text_input("Data do investimento (AAAA-MM-DD)", value=cfg.data_investimento)

    st.subheader("Financiamento (opcional)")
    st.caption("Se parte do investimento foi financiado, informe a parcela para ver se a economia já está cobrindo-a.")
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    with col_f1:
        valor_financiado = st.number_input("Valor financiado (R$)", value=cfg.valor_financiado, min_value=0.0)
    with col_f2:
        parcela_mensal = st.number_input("Parcela mensal (R$)", value=cfg.parcela_mensal, min_value=0.0)
    with col_f3:
        qtd_parcelas = st.number_input("Quantidade de parcelas", value=cfg.qtd_parcelas, min_value=0, step=1)
    with col_f4:
        data_primeira_parcela = st.text_input("1ª parcela (AAAA-MM-DD)", value=cfg.data_primeira_parcela)

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

    pasta_backup = _bloco_backup(cfg)

    if st.button("Salvar configurações", type="primary"):
        configuracoes.salvar(configuracoes.Configuracoes(
            investimento_total=investimento, data_investimento=data_investimento,
            valor_financiado=valor_financiado, parcela_mensal=parcela_mensal,
            qtd_parcelas=int(qtd_parcelas), data_primeira_parcela=data_primeira_parcela,
            icms=icms, pis_cofins=pis_cofins, degradacao_anual=degradacao,
            reajuste_tarifa_anual=reajuste, performance_ratio=performance_ratio,
            pasta_backup=pasta_backup,
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
