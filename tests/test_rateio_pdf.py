from pathlib import Path
from solar import rateio_pdf

def test_gerar_pdf_rateio(tmp_path):
    saida = tmp_path / "teste_rateio.pdf"
    itens = [
        {
            "pct": 50.0,
            "conta_contrato": "3024187216",
            "classe": "Residencial",
            "endereco": "Rua Teste, 123",
        },
        {
            "pct": 50.0,
            "conta_contrato": "3032480739",
            "classe": "Comercial",
            "endereco": "Av Teste, 456",
        }
    ]
    pdf = rateio_pdf.desenhar_pdf_rateio(
        caminho_saida=saida,
        conta_contrato_geradora="3032332055",
        local_solicitacao="Salinópolis-PA",
        data_solicitacao="16/10/2026",
        itens_rateio=itens,
    )
    assert pdf.exists()
    assert pdf.stat().st_size > 1000

def test_montar_itens_rateio():
    dist = {"Marambaia": 32.99, "Icoaraci": 28.57, "101": 21.16}
    itens = rateio_pdf.montar_itens_rateio(dist)
    assert len(itens) == 3
    assert itens[0]["conta_contrato"] == "3024187216"
    assert itens[0]["pct"] == 32.99
