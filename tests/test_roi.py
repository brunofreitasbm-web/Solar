import pandas as pd

from solar import roi
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


def test_payback_projetado_usa_tendencia_recente():
    resumo = pd.DataFrame({
        "mes_ref": [f"2025-{m:02d}" for m in range(1, 13)],
        "economia_rs": [1000.0] * 12,
    })
    mes = roi.mes_payback_projetado(resumo, investimento=18000, degradacao_anual=0.0, reajuste_tarifa_anual=0.0)
    # já economizou 12000; faltam 6000 a 1000/mês => mais 6 meses, chegando em 2026-06
    assert mes == "2026-06"


def test_payback_projetado_ja_atingido():
    resumo = pd.DataFrame({"mes_ref": ["2025-01", "2025-02"], "economia_rs": [600.0, 600.0]})
    assert roi.mes_payback_projetado(resumo, investimento=1000) == "2025-01"
