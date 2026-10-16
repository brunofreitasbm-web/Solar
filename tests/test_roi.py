import pandas as pd

from solar.roi import mes_payback, serie_acumulada, tir_mensal


def test_payback_quando_economia_supera_investimento():
    resumo = pd.DataFrame({"mes_ref": ["2026-01", "2026-02", "2026-03"], "economia_rs": [400, 400, 400]})
    acumulado = serie_acumulada(resumo, investimento=1000)
    assert mes_payback(acumulado) == "2026-03"


def test_sem_payback_quando_economia_nao_cobre():
    resumo = pd.DataFrame({"mes_ref": ["2026-01", "2026-02"], "economia_rs": [100, 100]})
    acumulado = serie_acumulada(resumo, investimento=1000)
    assert mes_payback(acumulado) is None


def test_tir_mensal_fluxo_positivo():
    taxa = tir_mensal(1000, [100] * 12)
    assert taxa is not None and taxa > 0
