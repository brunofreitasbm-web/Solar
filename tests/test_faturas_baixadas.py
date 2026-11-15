from solar.faturas.baixadas import FaturasConhecidas


def test_detecta_pdf_repetido_mesmo_com_outro_nome(tmp_path):
    (tmp_path / "janeiro.pdf").write_bytes(b"conteudo-a")
    conhecidas = FaturasConhecidas([tmp_path])

    assert conhecidas.ja_existe(b"conteudo-a")
    assert not conhecidas.ja_existe(b"conteudo-b")


def test_nome_livre_nao_sobrescreve_pdf_diferente(tmp_path):
    (tmp_path / "fatura.pdf").write_bytes(b"a")
    conhecidas = FaturasConhecidas([tmp_path])

    assert conhecidas.nome_livre("fatura.pdf") == "fatura_2.pdf"
    conhecidas.registrar("fatura_2.pdf", b"b")
    assert conhecidas.nome_livre("fatura.pdf") == "fatura_3.pdf"
    assert conhecidas.nome_livre("outra.pdf") == "outra.pdf"
