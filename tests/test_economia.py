import pandas as pd

from solar.economia import economia_da_fatura, percentual_fio_b


def _linha(**over):
    base = dict(compensado_kwh=100.0, credito_rs=None, tarifa_kwh=1.30, mes_ref="2026-06",
                data_pedido_conexao="2024-01-01")
    base.update(over)
    return pd.Series(base)


def test_isento_fio_b_antes_da_lei_14300():
    assert percentual_fio_b("2026-06", "2022-12-01") == 0.0


def test_percentual_fio_b_2026():
    assert percentual_fio_b("2026-06", "2024-01-01") == 0.60


def test_economia_usa_credito_da_fatura_quando_disponivel():
    linha = _linha(credito_rs=135.0)
    valor = economia_da_fatura(linha, tarifa_tusd_kwh=0.69)
    # 135 - (100 * 0.69 * 0.60) = 135 - 41.4 = 93.6
    assert round(valor, 2) == 93.60


def test_economia_calcula_pela_tarifa_quando_sem_credito_na_fatura():
    linha = _linha(credito_rs=None, tarifa_kwh=1.30)
    valor = economia_da_fatura(linha, tarifa_tusd_kwh=0.69)
    # (100*1.30) - (100*0.69*0.60) = 130 - 41.4 = 88.6
    assert round(valor, 2) == 88.60


def test_economia_nunca_negativa():
    linha = _linha(credito_rs=10.0, compensado_kwh=100.0)
    valor = economia_da_fatura(linha, tarifa_tusd_kwh=5.0)
    assert valor == 0.0


def test_sem_compensacao_economia_zero():
    linha = _linha(compensado_kwh=0.0)
    assert economia_da_fatura(linha, tarifa_tusd_kwh=0.69) == 0.0
