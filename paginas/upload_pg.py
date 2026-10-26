from pathlib import Path

import streamlit as st

from paginas import ui
from solar import config, equatorial
from solar.faturas import pendentes as fila
from solar.faturas.extracao import extrair
from solar.faturas.importacao import salvar_se_completa


def _processar(nome_bytes: list[tuple[str, bytes]], salvar_direto: bool) -> None:
    processados = st.session_state.setdefault("arquivos_processados", set())

    novos = [(nome, b) for nome, b in nome_bytes if nome not in processados]
    if not novos:
        st.info("Todos os arquivos selecionados já foram lidos nesta sessão.", icon=":material/done_all:")
        if fila.contar():
            ui.link_para("revisar-leitura", "Ver faturas pendentes de revisão")
        return

    salvas = 0
    barra = st.progress(0.0, text="Lendo faturas…")
    for i, (nome, pdf) in enumerate(novos):
        barra.progress(i / len(novos), text=f"Lendo {nome} ({i + 1} de {len(novos)})…")
        resultado = extrair(nome, pdf)
        if salvar_direto and salvar_se_completa(resultado):
            salvas += 1
        else:
            fila.adicionar(resultado)
        processados.add(nome)
    barra.empty()
    st.cache_data.clear()

    na_fila = len(novos) - salvas
    if salvas:
        st.success(f"{salvas} fatura(s) lida(s) com sucesso e salvas no histórico.", icon=":material/check_circle:")
        ui.link_para("dashboard", "Ver no Dashboard")
    if na_fila:
        st.warning(f"{na_fila} fatura(s) precisam da sua revisão de leitura.", icon=":material/fact_check:")
        ui.link_para("revisar-leitura", f"Revisar {na_fila} fatura(s) agora")


def _aba_google_drive() -> None:
    pasta_drive = config.PASTA_GOOGLE_DRIVE
    pasta_existe = pasta_drive.exists()

    with st.container(border=True):
        st.markdown("#### :material/cloud_sync: Sincronização automática com o Google Drive")
        st.caption(f"Pasta monitorada: `{pasta_drive}`")

        if not pasta_existe:
            st.error(
                "A pasta do Google Drive não foi localizada neste computador. "
                "Confirme se o aplicativo do Google Drive está instalado ou altere o caminho em Configurações.",
                icon=":material/folder_off:",
            )
            return

        todos_drive, novos_drive = equatorial.obter_arquivos_drive()

        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Total no Google Drive", len(todos_drive), border=True)
        col_m2.metric("Já cadastradas", len(todos_drive) - len(novos_drive), border=True)
        col_m3.metric("Novas para importar", len(novos_drive), border=True)

        col_opc1, col_opc2 = st.columns(2)
        salvar_direto = col_opc1.checkbox(
            "Salvar direto faturas lidas por completo",
            value=True,
            key="drive_salvar_direto",
            help="Se todos os dados forem lidos com segurança, já entram no histórico sem revisão manual.",
        )
        reimportar_todas = col_opc2.checkbox(
            "Reimportar todos os arquivos da pasta",
            value=False,
            key="drive_reimportar_todas",
            help="Marque se quiser reler mesmo as contas que já constam no banco.",
        )

        alvos = todos_drive if reimportar_todas else novos_drive

        if alvos:
            rotulo = f"Importar {len(alvos)} fatura(s) do Google Drive"
            if st.button(rotulo, type="primary", icon=":material/sync:", width="stretch"):
                _processar([(str(p.name), p.read_bytes()) for p in alvos], salvar_direto=salvar_direto)
        else:
            st.success("Tudo em dia! Todas as faturas desta pasta já estão registradas no histórico.", icon=":material/task_alt:")


def _aba_equatorial() -> None:
    st.markdown("#### :material/bolt: Conexão e download na Agência Virtual da Equatorial")
    st.caption("Acesso direto ao portal de faturas da Equatorial Pará.")

    tem_sessao = equatorial.tem_sessao_salva()

    with st.container(border=True):
        col_info, col_btn_auth = st.columns([2, 1], vertical_alignment="center")
        with col_info:
            if tem_sessao:
                st.success("Sessão da Equatorial memorizada neste computador.", icon=":material/verified_user:")
            else:
                st.info("Nenhuma sessão salva ainda. O sistema abrirá a janela para seu primeiro acesso.", icon=":material/info:")
        with col_btn_auth:
            rotulo_auth = "Reconectar / Testar" if tem_sessao else "Conectar conta"
            if st.button(rotulo_auth, icon=":material/login:", width="stretch",
                         help="Abre o navegador para você entrar com Google ou CPF/senha e salvar o acesso."):
                caixa = st.empty()
                with st.spinner("Abrindo janela do navegador… Conclua a identificação na tela aberta."):
                    ok, msg = equatorial.abrir_sessao_login(callback_progresso=lambda t: caixa.caption(t))
                caixa.empty()
                if ok:
                    st.success(msg, icon=":material/check_circle:")
                else:
                    st.warning(msg, icon=":material/warning:")
                st.rerun()

    st.markdown("**Opções de download automático**")
    col_c1, col_c2 = st.columns(2)
    salvar_auto = col_c1.checkbox(
        "Salvar direto faturas lidas por completo",
        value=True,
        key="eqtl_salvar_auto",
        help="As faturas com leitura completa entram automaticamente no banco de dados.",
    )
    modo_visivel = col_c2.checkbox(
        "Abrir janela visível do navegador (Recomendado)",
        value=True,
        key="eqtl_modo_visivel",
        help="Evita bloqueios do firewall anti-robô da Equatorial. Você poderá acompanhar o download em tempo real.",
    )

    st.caption(f":material/sync_alt: As faturas baixadas são salvas e copiadas para `{config.PASTA_GOOGLE_DRIVE}`.")

    if st.button("Baixar faturas da Equatorial agora", type="primary", icon=":material/download:", width="stretch"):
        status_box = st.empty()
        barra = st.progress(0.1, text="Conectando à Equatorial…")
        try:
            barra.progress(0.3, text="Acessando área de 2ª via e faturas…")
            arquivos = equatorial.baixar_faturas_equatorial(
                callback_progresso=lambda texto: status_box.caption(texto),
                headless=not modo_visivel,
            )
        except Exception as erro:
            barra.empty()
            status_box.empty()
            st.error(
                f"Não foi possível baixar da Equatorial: {erro}",
                icon=":material/error:",
            )
            return

        barra.empty()
        status_box.empty()
        if not arquivos:
            st.warning(
                "Nenhum arquivo novo foi baixado no portal. "
                "Confirme se as faturas do mês já foram emitidas pela Equatorial.",
                icon=":material/search_off:",
            )
            return

        _processar([(arq.name, arq.read_bytes()) for arq in arquivos], salvar_direto=salvar_auto)


def _aba_brechas_alternativas() -> None:
    st.markdown("#### :material/lightbulb: Formas mais rápidas e sem bloqueios para obter faturas")
    st.caption("Canais oficiais da Equatorial que evitam filas, captchas e instabilidades no site.")

    col1, col2 = st.columns(2)

    with col1:
        with st.container(border=True):
            st.markdown("##### :material/chat: WhatsApp Oficial da Equatorial (Clara)")
            st.markdown(
                "A assistente virtual **Clara** envia o PDF oficial da fatura diretamente pelo WhatsApp "
                "em menos de 1 minuto, sem qualquer firewall ou captcha."
            )
            st.markdown("**Número:** `(91) 3217-8200`")
            st.link_button(
                "Abrir WhatsApp da Clara (Pedir 2ª via)",
                url="https://wa.me/559132178200?text=2a%20via",
                icon=":material/send:",
                type="primary",
                width="stretch",
            )
            st.caption("Assim que receber o PDF no WhatsApp, solte-o na pasta do Google Drive ou na aba de arquivos.")

    with col2:
        with st.container(border=True):
            st.markdown("##### :material/mail: Fatura Digital por E-mail")
            st.markdown(
                f"Cadastre o recebimento da fatura por e-mail (`{config.EMAIL_ISABELA}`). "
                "Todo mês a conta chega em PDF no seu e-mail logo após o fechamento do ciclo de leitura."
            )
            st.markdown(
                "- Sem atraso de entrega física;\n"
                "- Arquivos já organizados por mês;\n"
                "- Pode ser sincronizado diretamente na pasta do Google Drive."
            )
            st.link_button(
                "Agência Virtual: Cadastrar Fatura por E-mail",
                url="https://agenciavirtual.equatorialenergia.com.br/",
                icon=":material/open_in_new:",
                width="stretch",
            )


def _aba_arquivos() -> None:
    st.markdown("#### :material/upload_file: Enviar arquivos PDF avulsos")
    arquivos = st.file_uploader(
        "Selecione ou arraste as faturas em PDF",
        type="pdf",
        accept_multiple_files=True,
        help="Você pode enviar múltiplas contas de energia de uma única vez.",
    )
    if arquivos:
        _processar([(a.name, a.read()) for a in arquivos], salvar_direto=False)
    else:
        st.caption("Solte seus arquivos PDF acima para iniciar o processamento.")


def _aba_pasta() -> None:
    st.markdown("#### :material/folder_open: Importar de outra pasta no computador")
    caminho = st.text_input(
        "Caminho completo da pasta",
        placeholder=r"C:\Users\bruno\Downloads\Contas Energia",
        help="Lê todos os PDFs dessa pasta e das subpastas.",
    )
    pasta = Path(caminho.strip().strip('"')) if caminho.strip() else None
    if pasta and not pasta.is_dir():
        st.error("Pasta não encontrada. Verifique o caminho digitado.", icon=":material/folder_off:")

    salvar_direto = st.checkbox(
        "Salvar direto faturas lidas por completo",
        value=True,
        key="pasta_avulsa_salvar_direto",
        help="Faturas com dados completos entram no histórico sem necessidade de revisão.",
    )

    if st.button("Ler PDFs desta pasta", type="primary", icon=":material/folder:",
                 disabled=not (pasta and pasta.is_dir()), width="stretch"):
        pdfs = sorted(pasta.rglob("*.pdf"))
        if not pdfs:
            st.warning("Nenhum PDF encontrado na pasta selecionada.", icon=":material/search_off:")
            return
        st.caption(f"{len(pdfs)} PDF(s) encontrado(s).")
        _processar([(str(p.relative_to(pasta)), p.read_bytes()) for p in pdfs], salvar_direto)


def render() -> None:
    st.title("Enviar faturas")
    st.caption("Importe suas contas de energia da Equatorial pelo Google Drive, pelo portal web ou por arquivos.")

    aba_drive, aba_eqtl, aba_brechas, aba_upload, aba_pasta = st.tabs([
        ":material/cloud_sync: Google Drive",
        ":material/bolt: Agência Virtual",
        ":material/lightbulb: WhatsApp & E-mail",
        ":material/upload_file: Arrastar arquivos",
        ":material/folder: Outra pasta",
    ])

    with aba_drive:
        _aba_google_drive()
    with aba_eqtl:
        _aba_equatorial()
    with aba_brechas:
        _aba_brechas_alternativas()
    with aba_upload:
        _aba_arquivos()
    with aba_pasta:
        _aba_pasta()
