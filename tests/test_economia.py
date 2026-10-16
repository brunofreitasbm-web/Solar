import pandas as pd

from solar.economia import percentual_fio_b, percentual_fio_b_ano, resumo_mensal, tabela_economia


def _fatura(**over):
    base = dict(uc="1", mes_ref="2025-06", consumo_kwh=371.0, compensado_kwh=332.14, tarifa_kwh=1.255084,
                fio_b_rs=76.72, beneficio_rs=55.70, data_pedido_conexao="2024-01-01", total_rs=232.47)
    base.update(over)
    return base


def _tabela(*linhas, tusd=0.69, padrao=0.0):
    return tabela_economia(pd.DataFrame(linhas), tusd, padrao)


def test_isento_fio_b_antes_da_lei_14300():
    assert percentual_fio_b("2026-06", "2022-12-01") == 0.0


def test_percentual_fio_b_por_ano():
    assert percentual_fio_b("2026-06", "2024-01-01") == 0.60
    assert percentual_fio_b_ano(2028) == 0.90
    assert percentual_fio_b_ano(2029) == 1.0
    assert percentual_fio_b_ano(2022) == 0.0


def test_economia_e_valor_da_energia_compensada_menos_remanescentes_da_fatura():
    # Fatura real UC 101 jun/2025: 332,14 kWh × R$1,255084 − Fio B 76,72 − benefício 55,70
    economia = _tabela(_fatura()).loc[0, "economia_rs"]
    assert round(economia, 2) == round(332.14 * 1.255084 - 76.72 - 55.70, 2)


def test_sem_compensacao_economia_zero():
    assert _tabela(_fatura(compensado_kwh=0.0)).loc[0, "economia_rs"] == 0.0


def test_economia_nunca_negativa():
    assert _tabela(_fatura(fio_b_rs=900.0)).loc[0, "economia_rs"] == 0.0


def test_tarifa_ausente_usa_mediana_das_outras_unidades_no_mes():
    tudo_compensado = _fatura(uc="2", tarifa_kwh=None, compensado_kwh=100.0, fio_b_rs=0.0, beneficio_rs=0.0)
    outra = _fatura(uc="3", tarifa_kwh=1.20, compensado_kwh=0.0)
    tabela = _tabela(tudo_compensado, outra)
    assert round(tabela.loc[tabela["uc"] == "2", "economia_rs"].iloc[0], 2) == 120.0


def test_sem_composicao_estima_fio_b_pela_regra_da_lei():
    linha = _fatura(fio_b_rs=None, beneficio_rs=None, compensado_kwh=100.0, tarifa_kwh=1.30)
    # 100×1,30 − 100×0,69×0,45 (2025) = 130 − 31,05
    assert round(_tabela(linha).loc[0, "economia_rs"], 2) == 98.95


def test_resumo_mensal_soma_as_unidades():
    tabela = _tabela(_fatura(uc="1"), _fatura(uc="2"))
    resumo = resumo_mensal(tabela)
    assert len(resumo) == 1
    assert round(resumo.loc[0, "economia_rs"], 2) == round(2 * (332.14 * 1.255084 - 132.42), 2)
