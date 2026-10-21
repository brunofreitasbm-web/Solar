from pathlib import Path

import streamlit as st

from paginas import ui
from solar import equatorial
from solar.faturas import pendentes as fila
from solar.faturas.extracao import extrair
from solar.faturas.importacao import salvar_se_completa


def _processar(nome_bytes: list[tuple[str, bytes]], salvar_direto: bool) -> None:
    processados = st.session_state.setdefault("arquivos_processados", set())

    novos = [(nome, b) for nome, b in nome_bytes if nome not in processados]
    if not novos:
        st.info(f"{len(nome_bytes)} arquivo(s) já lido(s) nesta sessão.", icon=":material/done_all:")
        if fila.contar():
            ui.link_para("revisar-leitura", "Ver a fila de revisão")
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
        st.success(f"{salvas} fatura(s) lida(s) por completo e já salva(s).", icon=":material/check_circle:")
        ui.link_para("dashboard", "Ver no Dashboard")
    if na_fila:
        st.warning(f"{na_fila} fatura(s) precisam da sua revisão antes de entrar no histórico.", icon=":material/fact_check:")
        ui.link_para("revisar-leitura", f"Revisar {na_fila} fatura(s) agora")


def _status_conexao() -> None:
    col_status, col_acao = st.columns([2, 1], vertical_alignment="center")
    with col_status:
        if equatorial.PASTA_PERFIL.exists():
            st.success("Acesso à Equatorial configurado neste computador.", icon=":material/verified_user:")
        else:
            st.info("**Passo 1:** conecte sua conta uma única vez. A sessão fica salva para os próximos meses.",
                    icon=":material/link:")
    with col_acao:
        if st.button("Conectar na Equatorial", icon=":material/login:", width="stretch",
                     help="Abre uma janela do Chrome para você fazer o login da Equatorial uma única vez."):
            with st.spinner("Abrindo janela de login da Equatorial…"):
                ui.avisar(equatorial.abrir_sessao_login(), ":material/info:")
            st.rerun()


def _baixar(salvar_auto: bool, modo_visivel: bool) -> None:
    status_box = st.empty()
    barra = st.progress(0.1, text="Conectando à Equatorial…")
    try:
        barra.progress(0.3, text="Acessando o portal da Equatorial…")
        arquivos = equatorial.baixar_faturas_equatorial(
            callback_progresso=lambda texto: status_box.caption(texto), headless=not modo_visivel,
        )
    except Exception as erro:
        barra.empty()
        status_box.empty()
        st.error(f"Não consegui baixar da Equatorial: {erro}. Tente de novo com **Abrir janela visível** marcado "
                 "ou clique em **Conectar na Equatorial** para refazer o login.", icon=":material/error:")
        return
    barra.empty()
    status_box.empty()
    if not arquivos:
        st.warning("Nenhuma fatura nova encontrada. Confira se o login ainda vale ou tente com a janela visível.",
                   icon=":material/search_off:")
        return
    _processar([(arq.name, arq.read_bytes()) for arq in arquivos], salvar_direto=salvar_auto)


def _aba_equatorial() -> None:
    st.caption("Baixe as faturas direto da sua conta, sem esperar o e-mail chegar.")
    _status_conexao()

    st.markdown("**Passo 2:** baixe e importe as faturas")
    col_opc1, col_opc2 = st.columns(2)
    salvar_auto = col_opc1.checkbox(
        "Salvar direto as faturas lidas por completo", value=True,
        help="Se todos os valores forem lidos, a fatura já entra no histórico sem revisão manual.")
    modo_visivel = col_opc2.checkbox(
        "Abrir janela visível do navegador", value=True,
        help="Necessário quando a Equatorial pede confirmação de acesso ou bloqueia o navegador invisível.")
    st.caption(f":material/cloud_sync: As faturas baixadas são copiadas para `{equatorial.config.PASTA_GOOGLE_DRIVE}`.")

    if st.button("Baixar faturas recentes", type="primary", icon=":material/download:"):
        _baixar(salvar_auto, modo_visivel)

    with st.expander("Outras formas de receber as faturas", icon=":material/lightbulb:"):
        st.markdown(
            "- **WhatsApp da Equatorial (Clara):** adicione `(91) 3217-8200` e envie `2ª via` para receber o PDF na hora.\n"
            "- **Fatura digital:** na Agência Virtual, clique em **Solicitar fatura por e-mail** para voltar a receber todo mês."
        )


def _aba_arquivos() -> None:
    arquivos = st.file_uploader(
        "Faturas em PDF", type="pdf", accept_multiple_files=True,
        help="Pode soltar várias de uma vez, de endereços e meses diferentes.",
    )
    if arquivos:
        _processar([(a.name, a.read()) for a in arquivos], salvar_direto=False)
    else:
        st.caption("Assim que você soltar os PDFs aqui, eles são lidos e vão para a fila de revisão.")


def _aba_pasta() -> None:
    caminho = st.text_input(
        "Caminho da pasta",
        help="Lê todos os PDFs dessa pasta e das subpastas — útil quando você organiza as "
             "faturas por endereço, uma subpasta por unidade.",
        placeholder=r"C:\Users\bruno\Downloads\Solar Contas Energia",
    )
    pasta = Path(caminho.strip().strip('"')) if caminho.strip() else None
    if pasta and not pasta.is_dir():
        st.error("Pasta não encontrada. Copie o caminho pela barra de endereço do Explorador de Arquivos e cole aqui.",
                 icon=":material/folder_off:")
    salvar_direto = st.checkbox(
        "Salvar direto as faturas lidas por completo", value=True, key="pasta_salvar_direto",
        help="Só vão para a fila de revisão as que tiverem algum campo faltando. Desmarque para revisar todas.",
    )
    if st.button("Ler faturas da pasta", type="primary", icon=":material/folder_open:", disabled=not (pasta and pasta.is_dir())):
        pdfs = sorted(pasta.rglob("*.pdf"))
        if not pdfs:
            st.warning("Nenhum PDF encontrado nessa pasta (nem nas subpastas).", icon=":material/search_off:")
            return
        st.caption(f"{len(pdfs)} PDF(s) encontrado(s).")
        _processar([(str(p.relative_to(pasta)), p.read_bytes()) for p in pdfs], salvar_direto)


def render() -> None:
    st.title("Enviar faturas")
    st.caption("O app lê cada conta de energia sozinho. Se faltar algum dado, você revisa na próxima tela.")

    aba_equatorial, aba_upload, aba_pasta = st.tabs([
        ":material/bolt: Baixar da Equatorial", ":material/upload: Arrastar arquivos", ":material/folder: Ler de uma pasta",
    ])
    with aba_equatorial:
        _aba_equatorial()
    with aba_upload:
        _aba_arquivos()
    with aba_pasta:
        _aba_pasta()
