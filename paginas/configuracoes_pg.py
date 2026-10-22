from dataclasses import replace
from datetime import datetime
from pathlib import Path

import streamlit as st

from paginas import ui
from solar import backup, config, configuracoes, telegram
from solar.tarifa import aneel


def _investimento(cfg: configuracoes.Configuracoes) -> dict:
    st.subheader("Investimento")
    col1, col2 = st.columns(2)
    investimento = col1.number_input("Investimento total (R$)", value=cfg.investimento_total, min_value=0.0, step=1_000.0)
    data_inv = col2.date_input("Data do investimento", value=ui.data_ou_none(cfg.data_investimento), format="DD/MM/YYYY",
                               help="Normalmente a data em que a usina foi paga ou começou a operar.")
    if not investimento or not data_inv:
        st.caption(":orange[:material/info:] Com o valor e a data, o Dashboard passa a mostrar ROI e payback.")

    st.subheader("Financiamento (opcional)")
    st.caption("Se parte do investimento foi financiada, informe a parcela para ver se a economia já está cobrindo-a.")
    c1, c2, c3, c4 = st.columns(4)
    financiado = c1.number_input("Valor financiado (R$)", value=cfg.valor_financiado, min_value=0.0, step=1_000.0)
    parcela = c2.number_input("Parcela mensal (R$)", value=cfg.parcela_mensal, min_value=0.0, step=50.0)
    qtd = c3.number_input("Quantidade de parcelas", value=cfg.qtd_parcelas, min_value=0, step=1)
    primeira = c4.date_input("1ª parcela", value=ui.data_ou_none(cfg.data_primeira_parcela), format="DD/MM/YYYY")
    if parcela and not (financiado and qtd and primeira):
        st.caption(":orange[:material/info:] Para simular a quitação, preencha também valor financiado, quantidade e data da 1ª parcela.")
    return dict(investimento_total=investimento, data_investimento=ui.iso_ou_vazio(data_inv), valor_financiado=financiado,
                parcela_mensal=parcela, qtd_parcelas=int(qtd), data_primeira_parcela=ui.iso_ou_vazio(primeira))


def _tributos_e_projecao(cfg: configuracoes.Configuracoes) -> dict:
    st.subheader("Tributos e projeção")
    c1, c2, c3 = st.columns(3)
    icms = c1.number_input("ICMS (%)", value=cfg.icms * 100, min_value=0.0, max_value=100.0) / 100
    pis_cofins = c2.number_input("PIS/COFINS (%)", value=cfg.pis_cofins * 100, min_value=0.0, max_value=100.0) / 100
    performance = c3.number_input("Performance ratio da usina", value=cfg.performance_ratio, min_value=0.1, max_value=1.0, step=0.01,
                                  help="Eficiência real do sistema frente à irradiação teórica. Usinas residenciais ficam entre 0,75 e 0,85.")
    c4, c5 = st.columns(2)
    degradacao = c4.number_input("Degradação anual dos painéis (%)", value=cfg.degradacao_anual * 100,
                                 min_value=0.0, max_value=5.0, step=0.1) / 100
    reajuste = c5.number_input("Reajuste anual estimado da tarifa (%)", value=cfg.reajuste_tarifa_anual * 100,
                               min_value=0.0, max_value=30.0, step=0.5) / 100
    return dict(icms=icms, pis_cofins=pis_cofins, performance_ratio=performance, degradacao_anual=degradacao, reajuste_tarifa_anual=reajuste)


def _difere(atual, novo) -> bool:
    # Percentuais passam por ×100 ÷100 nos campos; sem arredondar, todo float pareceria alterado.
    return round(atual, 9) != round(novo, 9) if isinstance(atual, float) else atual != novo


def _botao_salvar(cfg: configuracoes.Configuracoes, novos: dict) -> None:
    nova = replace(cfg, **novos)
    alterado = any(_difere(getattr(cfg, campo), valor) for campo, valor in novos.items())
    col_botao, col_status = st.columns([1, 3], vertical_alignment="center")
    if col_botao.button("Salvar configurações", type="primary", icon=":material/save:", disabled=not alterado, width="stretch"):
        configuracoes.salvar(nova)
        ui.avisar("Configurações salvas.")
        st.rerun()
    col_status.caption(":orange[:material/edit:] Há alterações não salvas." if alterado else ":material/check: Tudo salvo.")


def _historico_backups(pasta: str) -> None:
    try:
        existentes = backup.listar_backups(pasta or None)
    except OSError:
        existentes = []
    if not existentes:
        st.caption("Ainda não há backups nessa pasta.")
        return
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
        if st.button("Restaurar este backup", disabled=not confirma, type="primary", icon=":material/restore:"):
            seguranca = backup.restaurar_backup(Path(escolhido))
            st.cache_data.clear()
            ui.avisar(f"Banco restaurado. A cópia do banco anterior ficou em {seguranca.name}.")
            st.rerun()


def _bloco_backup(cfg: configuracoes.Configuracoes) -> None:
    st.subheader("Backup")
    st.caption(f"O app faz um backup do banco a cada {config.DIAS_ENTRE_BACKUPS_AUTOMATICOS} dias e guarda os "
               f"{config.BACKUPS_MANTIDOS} mais recentes. Aponte a pasta para o Google Drive, OneDrive ou Dropbox do seu PC "
               "para a cópia sair do computador sozinha.")
    col_pasta, col_salvar = st.columns([3, 1], vertical_alignment="bottom")
    pasta = col_pasta.text_input("Pasta dos backups", value=cfg.pasta_backup, placeholder=str(config.PASTA_BACKUP),
                                 help="Vazio usa a pasta 'backups' dentro do projeto.").strip().strip('"')
    if col_salvar.button("Usar esta pasta", disabled=pasta == cfg.pasta_backup, width="stretch"):
        configuracoes.salvar(replace(configuracoes.carregar(), pasta_backup=pasta))
        ui.avisar("Pasta de backup atualizada.")
        st.rerun()
    if pasta and not Path(pasta).is_dir():
        st.error("Pasta não encontrada. Crie a pasta ou copie o caminho pela barra de endereço do Explorador de Arquivos.",
                 icon=":material/folder_off:")

    incluir_pdfs = st.checkbox("Incluir os PDFs das faturas", value=False, help="Aumenta bastante o tamanho; o banco já guarda tudo o que foi lido.")
    if st.button("Fazer backup agora", icon=":material/backup:"):
        try:
            with st.spinner("Copiando o banco…"):
                arquivo = backup.fazer_backup(pasta or None, incluir_pdfs)
            st.success(f"Backup salvo em {arquivo} ({arquivo.stat().st_size / 1024:,.0f} KB).", icon=":material/check_circle:")
        except OSError as erro:
            st.error(f"Não consegui salvar o backup nessa pasta: {erro}. Confira se ela existe e se você pode gravar nela.")
    _historico_backups(pasta)


def _bloco_telegram() -> None:
    st.subheader("Aviso no Telegram")
    st.caption("Cada fatura que entrar no histórico é enviada ao Telegram com a unidade, o valor, o Pix copia e cola "
               "e o código de barras. Cada UC/mês é avisado uma única vez. "
               "Para criar o bot: abra o @BotFather no Telegram, envie /newbot e copie o token.")
    cfg = telegram.carregar()
    token = st.text_input("Token do bot", value=cfg.token, type="password", help="Fica salvo só neste computador.").strip()
    col_chat, col_achar = st.columns([3, 1], vertical_alignment="bottom")
    chat_id = col_chat.text_input("ID do chat", value=cfg.chat_id, key="telegram_chat_id_campo",
                                  help="Envie /start ao seu bot e use o botão ao lado para preencher sozinho.").strip()
    if col_achar.button("Descobrir meu ID", disabled=not token, width="stretch"):
        try:
            st.session_state["telegram_chat_id_campo"] = telegram.descobrir_chat_id(token)
            st.rerun()
        except telegram.FalhaTelegram as erro:
            st.error(str(erro), icon=":material/error:")
    ativo = st.toggle("Avisar no Telegram ao importar uma fatura", value=cfg.ativo, disabled=not (token and chat_id))

    novo = telegram.ConfigTelegram(token, chat_id, ativo)
    col_salvar, col_teste = st.columns(2)
    if col_salvar.button("Salvar Telegram", icon=":material/save:", disabled=novo == cfg, width="stretch"):
        telegram.salvar(novo)
        ui.avisar("Telegram configurado.")
        st.rerun()
    if col_teste.button("Enviar mensagem de teste", icon=":material/send:", disabled=not novo.pronto, width="stretch"):
        try:
            telegram.enviar("Solar ROI: o aviso de faturas por Telegram está funcionando.", novo)
            st.success("Mensagem enviada. Confira no Telegram.", icon=":material/check_circle:")
        except telegram.FalhaTelegram as erro:
            st.error(str(erro), icon=":material/error:")


def _bloco_tarifa(icms: float, pis_cofins: float) -> None:
    st.subheader("Tarifa de energia (ANEEL)")
    col_a, col_b = st.columns([3, 1], vertical_alignment="center")
    atualizar = col_b.button("Atualizar tarifa", icon=":material/refresh:", width="stretch")
    try:
        with st.spinner("Consultando a ANEEL…"):
            tarifa = aneel.tarifa_de_hoje(forcar=atualizar)
    except aneel.FalhaTarifa as erro:
        st.error(f"{erro} Tente **Atualizar tarifa** em alguns minutos.", icon=":material/cloud_off:")
        return
    col_a.metric("Tarifa B1 Equatorial PA sem tributos", f"R$ {tarifa.sem_tributos:.4f}/kWh", border=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("TE", f"R$ {tarifa.te_kwh:.4f}/kWh", border=True)
    c2.metric("TUSD", f"R$ {tarifa.tusd_kwh:.4f}/kWh", border=True)
    c3.metric("Com tributos", f"R$ {tarifa.com_tributos(icms, pis_cofins):.4f}/kWh", border=True)
    st.caption(f"Vigência: {tarifa.inicio_vigencia} a {tarifa.fim_vigencia} · consultado em {tarifa.consultado_em}")


def render() -> None:
    st.title("Configurações")
    cfg = configuracoes.carregar()
    novos = _investimento(cfg) | _tributos_e_projecao(cfg)
    _botao_salvar(cfg, novos)
    st.divider()
    _bloco_tarifa(novos["icms"], novos["pis_cofins"])
    st.divider()
    _bloco_telegram()
    st.divider()
    _bloco_backup(cfg)
