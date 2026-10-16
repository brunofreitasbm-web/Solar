import pandas as pd

from solar.configuracoes import Configuracoes
from solar.financiamento import fluxo_com_financiamento, mes_parcelas_termina, parcelas_por_mes


def _cfg(**over):
    base = dict(parcela_mensal=1000.0, qtd_parcelas=3, data_primeira_parcela="2024-12-12")
    base.update(over)
    return Configuracoes(**base)


def test_parcelas_por_mes_gera_sequencia_mensal():
    parcelas = parcelas_por_mes(_cfg())
    assert parcelas == {"2024-12": 1000.0, "2025-01": 1000.0, "2025-02": 1000.0}


def test_sem_financiamento_configurado_retorna_vazio():
    assert parcelas_por_mes(Configuracoes()) == {}


def test_mes_parcelas_termina():
    assert mes_parcelas_termina(_cfg()) == "2025-02"


def test_fluxo_com_financiamento_calcula_saldo_liquido():
    resumo = pd.DataFrame({"mes_ref": ["2024-12", "2025-01", "2025-04"], "economia_rs": [800.0, 1500.0, 900.0]})
    fluxo = fluxo_com_financiamento(resumo, _cfg())
    assert fluxo.loc[fluxo["mes_ref"] == "2024-12", "saldo_liquido_rs"].iloc[0] == -200.0
    assert fluxo.loc[fluxo["mes_ref"] == "2025-01", "saldo_liquido_rs"].iloc[0] == 500.0
    # fora do período financiado (parcela 0)
    assert fluxo.loc[fluxo["mes_ref"] == "2025-04", "saldo_liquido_rs"].iloc[0] == 900.0


def test_ponto_equilibrio_projeta_quando_saldo_ainda_negativo():
    from solar.financiamento import mes_ponto_equilibrio
    resumo = pd.DataFrame({
        "mes_ref": [f"2025-{m:02d}" for m in range(1, 13)],
        "economia_rs": [1200.0] * 12,
    })
    cfg = _cfg(parcela_mensal=1000.0, qtd_parcelas=12, data_primeira_parcela="2025-01-05")
    mes = mes_ponto_equilibrio(resumo, cfg, degradacao_anual=0.0, reajuste_tarifa_anual=0.0)
    # saldo líquido acumulado em 12 meses: 12*(1200-1000) = 2400 > 0 já dentro do histórico
    assert mes == "2025-12"


def test_ponto_equilibrio_ja_positivo_retorna_ultimo_mes():
    from solar.financiamento import mes_ponto_equilibrio
    resumo = pd.DataFrame({"mes_ref": ["2025-01"], "economia_rs": [5000.0]})
    cfg = Configuracoes()
    assert mes_ponto_equilibrio(resumo, cfg) == "2025-01"
