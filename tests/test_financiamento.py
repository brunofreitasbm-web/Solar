from datetime import date

import pandas as pd

from solar.configuracoes import Configuracoes
from solar.financiamento import (
    fluxo_com_financiamento, mes_parcelas_termina, mes_ponto_equilibrio, parcelas_pagas,
    parcelas_por_mes, saldo_devedor, simular_amortizacao, taxa_mensal,
)


def _cfg(**over):
    base = dict(parcela_mensal=1000.0, qtd_parcelas=3, data_primeira_parcela="2024-12-12")
    base.update(over)
    return Configuracoes(**base)


def _cfg_real():
    return Configuracoes(valor_financiado=100000.0, parcela_mensal=3463.72, qtd_parcelas=48,
                         data_primeira_parcela="2024-12-12")


HOJE = date(2026, 10, 16)


def test_parcelas_por_mes_gera_sequencia_mensal():
    assert parcelas_por_mes(_cfg()) == {"2024-12": 1000.0, "2025-01": 1000.0, "2025-02": 1000.0}


def test_sem_financiamento_configurado_retorna_vazio():
    assert parcelas_por_mes(Configuracoes()) == {}


def test_mes_parcelas_termina():
    assert mes_parcelas_termina(_cfg()) == "2025-02"


def test_fluxo_com_financiamento_calcula_saldo_liquido():
    resumo = pd.DataFrame({"mes_ref": ["2024-12", "2025-01", "2025-04"], "economia_rs": [800.0, 1500.0, 900.0]})
    fluxo = fluxo_com_financiamento(resumo, _cfg())
    assert fluxo.loc[fluxo["mes_ref"] == "2024-12", "saldo_liquido_rs"].iloc[0] == -200.0
    assert fluxo.loc[fluxo["mes_ref"] == "2025-01", "saldo_liquido_rs"].iloc[0] == 500.0
    assert fluxo.loc[fluxo["mes_ref"] == "2025-04", "saldo_liquido_rs"].iloc[0] == 900.0  # fora do período


def test_ponto_equilibrio_dentro_do_historico():
    resumo = pd.DataFrame({"mes_ref": [f"2025-{m:02d}" for m in range(1, 13)], "economia_rs": [1200.0] * 12})
    cfg = _cfg(parcela_mensal=1000.0, qtd_parcelas=12, data_primeira_parcela="2025-01-05")
    assert mes_ponto_equilibrio(resumo, cfg, 0.0, 0.0) == "2025-12"


def test_ponto_equilibrio_ja_positivo_retorna_ultimo_mes():
    resumo = pd.DataFrame({"mes_ref": ["2025-01"], "economia_rs": [5000.0]})
    assert mes_ponto_equilibrio(resumo, Configuracoes()) == "2025-01"


def test_ponto_equilibrio_projeta_quando_saldo_negativo():
    resumo = pd.DataFrame({"mes_ref": ["2025-01", "2025-02"], "economia_rs": [500.0, 500.0]})
    cfg = _cfg(parcela_mensal=1000.0, qtd_parcelas=2, data_primeira_parcela="2025-01-05")
    # saldo −1000; depois das parcelas, +500/mês → equilíbrio dois meses após o fim
    assert mes_ponto_equilibrio(resumo, cfg, 0.0, 0.0) == "2025-04"


def test_taxa_implicita_do_contrato_real():
    assert round(taxa_mensal(_cfg_real()) * 100, 2) == 2.30


def test_parcelas_pagas_conta_pelo_dia_do_vencimento():
    assert parcelas_pagas(_cfg_real(), date(2026, 10, 11)) == 22
    assert parcelas_pagas(_cfg_real(), date(2026, 10, 12)) == 23


def test_saldo_devedor_no_inicio_e_o_valor_financiado():
    assert round(saldo_devedor(_cfg_real(), 0), 0) == 100000


def test_amortizar_encurta_prazo_mantendo_parcela_e_poupa_juros():
    sim = simular_amortizacao(_cfg_real(), 20000.0, "prazo", HOJE)
    assert sim.pagas == 23 and sim.restantes_antes == 25
    assert sim.parcela_nova == 3463.72
    assert sim.restantes_depois < sim.restantes_antes
    assert sim.juros_economizados > 0
    assert round(sim.saldo_antes - sim.saldo_depois, 2) == 20000.0


def test_amortizar_reduzindo_parcela_mantem_prazo():
    sim = simular_amortizacao(_cfg_real(), 20000.0, "parcela", HOJE)
    assert sim.restantes_depois in (sim.restantes_antes, sim.restantes_antes - 1)
    assert sim.parcela_nova < 3463.72


def test_prazo_poupa_mais_juros_que_parcela():
    prazo = simular_amortizacao(_cfg_real(), 20000.0, "prazo", HOJE)
    parcela = simular_amortizacao(_cfg_real(), 20000.0, "parcela", HOJE)
    assert prazo.juros_economizados > parcela.juros_economizados


def test_quitar_zera_o_cronograma_futuro():
    sim = simular_amortizacao(_cfg_real(), 10**9, "prazo", HOJE)
    assert sim.quitou and sim.restantes_depois == 0
    assert max(sim.parcelas) == "2026-10"  # só as 23 parcelas já pagas


def test_cronograma_amortizado_entra_no_ponto_de_equilibrio():
    resumo = pd.DataFrame({"mes_ref": [f"2026-{m:02d}" for m in range(1, 10)], "economia_rs": [3000.0] * 9})
    cfg = _cfg_real()
    sim = simular_amortizacao(cfg, 30000.0, "prazo", HOJE)
    base = mes_ponto_equilibrio(resumo, cfg, 0.0, 0.0)
    depois = mes_ponto_equilibrio(resumo, cfg, 0.0, 0.0, parcelas=sim.parcelas, desembolso_extra=sim.valor)
    assert base is not None and depois is not None
