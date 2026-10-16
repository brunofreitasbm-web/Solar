from pathlib import Path

import streamlit as st

from solar import equatorial
from solar.faturas.extracao import extrair
from solar.faturas.importacao import salvar_se_completa


def _processar(nome_bytes: list[tuple[str, bytes]], salvar_direto: bool) -> None:
    pendentes = st.session_state.setdefault("faturas_pendentes", [])
    processados = st.session_state.setdefault("arquivos_processados", set())

    novos = [(nome, b) for nome, b in nome_bytes if nome not in processados]
    if not novos:
        st.success(f"{len(nome_bytes)} arquivo(s) já processado(s). Veja a fila em **Revisar leitura**.")
        return

    salvas = 0
    barra = st.progress(0.0, text="Lendo faturas…")
    for i, (nome, pdf) in enumerate(novos):
        resultado = extrair(nome, pdf)
        if salvar_direto and salvar_se_completa(resultado):
            salvas += 1
        else:
            pendentes.append(resultado)
        processados.add(nome)
        barra.progress((i + 1) / len(novos), text=f"Lendo {nome}…")
    barra.empty()
    st.cache_data.clear()

    na_fila = len(novos) - salvas
    if salvas:
        st.success(f"{salvas} fatura(s) lida(s) por completo e já salva(s).")
    if na_fila:
        st.warning(f"{na_fila} fatura(s) precisam da sua revisão — vá para **Revisar leitura**.")


def render() -> None:
    st.title("Enviar faturas")
    st.caption("Baixe automaticamente da Equatorial ou envie os PDFs das contas de energia. O app lê "
               "automaticamente e, se faltar algum dado, você revisa na próxima tela.")

    aba_equatorial, aba_upload, aba_pasta = st.tabs(["⚡ Baixar da Equatorial", "Arrastar arquivos", "Ler de uma pasta"])

    with aba_equatorial:
        st.subheader("Download automático da Equatorial Pará")
        st.caption("Acesse sua conta da Equatorial direto pelo app sem precisar esperar o e-mail chegar. "
                   "A sessão fica salva no seu computador para os próximos meses.")

        col_status, col_acao = st.columns([2, 1])
        with col_status:
            autenticado = equatorial.PASTA_PERFIL.exists()
            if autenticado:
                st.success("Perfil de acesso da Equatorial configurado neste computador.")
            else:
                st.info("Nenhuma sessão salva ainda. Clique ao lado para conectar uma vez.")

        with col_acao:
            if st.button("Conectar na Equatorial", help="Abre uma janela do Chrome para você fazer o login da Equatorial uma única vez."):
                with st.spinner("Abrindo janela de login da Equatorial…"):
                    msg = equatorial.abrir_sessao_login()
                    st.info(msg)
                    st.rerun()

        st.divider()

        st.write("### Baixar e importar faturas")
        col_opc1, col_opc2 = st.columns([2, 1])
        with col_opc1:
            salvar_auto = st.checkbox(
                "Salvar direto as faturas completas no banco", value=True,
                help="Se a leitura de todos os valores estiver 100% certa, já grava direto sem precisar de revisão manual."
            )
        with col_opc2:
            modo_visivel = st.checkbox(
                "Abrir janela visível do navegador", value=True,
                help="Útil caso a Equatorial solicite confirmação visual de acesso ou captcha."
            )

        if st.button("🚀 Baixar faturas recentes agora", type="primary"):
            status_box = st.empty()
            barra = st.progress(0.1, text="Conectando à Equatorial…")

            def _atualizar_progresso(texto: str):
                status_box.caption(f"ℹ️ {texto}")

            try:
                barra.progress(0.3, text="Acessando portal da Equatorial…")
                arquivos = equatorial.baixar_faturas_equatorial(
                    callback_progresso=_atualizar_progresso,
                    headless=not modo_visivel,
                )
                barra.progress(0.7, text=f"{len(arquivos)} fatura(s) baixada(s). Extraindo dados…")

                if not arquivos:
                    status_box.empty()
                    barra.empty()
                    st.warning("Nenhuma fatura nova foi encontrada para download no momento. "
                               "Verifique se você está conectado na conta ou tente novamente com a janela visível.")
                else:
                    nome_bytes = [(arq.name, arq.read_bytes()) for arq in arquivos]
                    barra.progress(0.9, text="Processando dados das faturas…")
                    _processar(nome_bytes, salvar_direto=salvar_auto)
                    barra.empty()
                    status_box.empty()

            except Exception as e:
                barra.empty()
                status_box.empty()
                st.error(f"Erro durante a conexão com a Equatorial: {e}")

        with st.expander("💡 Dica: Receber faturas por WhatsApp e e-mail", expanded=False):
            st.markdown(
                """
                - **WhatsApp Oficial da Equatorial (Clara)**: Adicione o número `(91) 3217-8200` e envie `2ª via` para receber o PDF na hora pelo WhatsApp.
                - **Ativar Fatura Digital**: Na Agência Virtual da Equatorial, clique em **Solicitar fatura por e-mail** para restabelecer o envio automático mensal.
                """
            )

    with aba_upload:
        arquivos = st.file_uploader(
            "Faturas em PDF", type="pdf", accept_multiple_files=True,
            help="Pode soltar várias de uma vez, de endereços e meses diferentes.",
        )
        if arquivos:
            _processar([(a.name, a.read()) for a in arquivos], salvar_direto=False)
        else:
            st.info("Nenhum arquivo enviado ainda. Assim que você soltar os PDFs aqui, eles aparecem "
                     "na fila de revisão.")

    with aba_pasta:
        caminho = st.text_input(
            "Caminho da pasta",
            help="Lê todos os PDFs dessa pasta e das subpastas — útil quando você organiza as "
                 "faturas por endereço, uma subpasta por unidade.",
            placeholder=r"C:\Users\bruno\Downloads\Solar Contas Energia",
        )
        salvar_direto = st.checkbox(
            "Salvar direto as faturas lidas por completo", value=True,
            help="Só vão para a fila de revisão as que tiverem algum campo faltando. Desmarque para revisar todas.",
        )
        if st.button("Ler faturas da pasta", type="primary", disabled=not caminho):
            pasta = Path(caminho)
            if not pasta.is_dir():
                st.error(f"Pasta não encontrada: {caminho}")
            else:
                pdfs = sorted(pasta.rglob("*.pdf"))
                if not pdfs:
                    st.warning("Nenhum PDF encontrado nessa pasta (nem nas subpastas).")
                else:
                    st.caption(f"{len(pdfs)} PDF(s) encontrado(s).")
                    _processar([(str(p.relative_to(pasta)), p.read_bytes()) for p in pdfs], salvar_direto)

