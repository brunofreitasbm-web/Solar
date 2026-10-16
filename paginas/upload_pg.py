from pathlib import Path

import streamlit as st

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
    st.caption("Arraste os PDFs das contas de energia, ou aponte para uma pasta no seu PC. O app lê "
               "automaticamente e, se faltar algum dado, você revisa na próxima tela.")

    aba_upload, aba_pasta = st.tabs(["Arrastar arquivos", "Ler de uma pasta"])

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
