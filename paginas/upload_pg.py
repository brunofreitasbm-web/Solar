import streamlit as st

from solar.faturas.extracao import extrair


def render() -> None:
    st.title("Enviar faturas")
    st.caption("Arraste os PDFs das contas de energia. O app lê automaticamente e, se faltar algum "
               "dado, você revisa na próxima tela.")

    arquivos = st.file_uploader(
        "Faturas em PDF", type="pdf", accept_multiple_files=True,
        help="Pode soltar várias de uma vez, de endereços e meses diferentes.",
    )

    if not arquivos:
        st.info("Nenhum arquivo enviado ainda. Assim que você soltar os PDFs aqui, eles aparecem "
                 "na fila de revisão.")
        return

    pendentes = st.session_state.setdefault("faturas_pendentes", [])
    ja_processados = {p.fatura.arquivo for p in pendentes} | {
        f for f in st.session_state.setdefault("arquivos_processados", set())
    }

    novos = [a for a in arquivos if a.name not in ja_processados]
    if not novos:
        st.success(f"{len(arquivos)} arquivo(s) já processado(s). Veja a fila em **Revisar leitura**.")
        return

    barra = st.progress(0.0, text="Lendo faturas…")
    for i, arquivo in enumerate(novos):
        resultado = extrair(arquivo.name, arquivo.read())
        pendentes.append(resultado)
        st.session_state["arquivos_processados"].add(arquivo.name)
        barra.progress((i + 1) / len(novos), text=f"Lendo {arquivo.name}…")
    barra.empty()

    st.success(f"{len(novos)} fatura(s) lida(s). Vá para **Revisar leitura** para confirmar os dados.")
