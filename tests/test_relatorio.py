import pandas as pd

from solar import alertas, pagamentos, relatorio_pdf


def _df() -> pd.DataFrame:
    return pd.DataFrame(dict(uc=["1"], mes_ref=["2026-09"], consumo_kwh=[100.0], compensado_kwh=[50.0], injetado_kwh=[10.0],
                             total_rs=[80.0], economia_rs=[40.0], saldo_creditos_kwh=[5.0]))


def test_relatorio_gera_pdf_com_dados():
    vazio = pagamentos.a_pagar(_df().assign(vencimento="", pago_em=None), {})
    assert relatorio_pdf.gerar(_df(), {"1": "Casa"}, "2026-09", [], vazio).startswith(b"%PDF")


def test_relatorio_de_mes_sem_fatura_e_com_alerta_nao_quebra():
    vazio = pagamentos.a_pagar(_df().assign(vencimento="", pago_em=None), {})
    alerta = alertas.Alerta("erro", "Fatura vencida", "vencimentos", "Ver")
    assert relatorio_pdf.gerar(_df(), {}, "2026-01", [alerta], vazio).startswith(b"%PDF")
