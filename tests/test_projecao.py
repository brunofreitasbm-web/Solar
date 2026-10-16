import pandas as pd

from solar import projecao
from solar.projecao import ModeloEconomia, calibrar, projecao_anual, sazonalidade, serie_futura


def _modelo(**over):
    base = dict(bruto_kwh=1.30, remanescente_kwh=0.15, fio_b_cheio_kwh=0.50, pct_base=0.60, kwh_mes=4000.0,
                sazonalidade={m: 1.0 for m in range(1, 13)}, mes_base="2026-09")
    base.update(over)
    return ModeloEconomia(**base)


def _resumo(valor=3000.0):
    return pd.DataFrame({"mes_ref": [f"2026-{m:02d}" for m in range(1, 10)], "economia_rs": [valor] * 9})


def _injecao(*series: tuple[str, list[float]], inicio="2025-01"):
    linhas = []
    ano, mes = map(int, inicio.split("-"))
    for uc, valores in series:
        a, m = ano, mes
        for v in valores:
            linhas.append({"uc": uc, "mes_ref": f"{a}-{m:02d}", "injetado_kwh": v, "geradora": True})
            a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return pd.DataFrame(linhas)


def test_liquido_base_desconta_fio_b_e_remanescente():
    assert round(_modelo().liquido_kwh_base, 3) == round(1.30 - 0.15 - 0.50 * 0.60, 3)


def test_fio_b_escalonado_reduz_a_economia_futura():
    resumo = _resumo()
    com = serie_futura(resumo, 36, 0.0, 0.0, _modelo(), escalar_fio_b=True)
    sem = serie_futura(resumo, 36, 0.0, 0.0, _modelo(), escalar_fio_b=False)
    assert sum(v for _, v in com) < sum(v for _, v in sem)
    # em 2029 o Fio B vai a 100%: (1,30 − 0,15 − 0,50) × 4000
    em_2029 = [v for mes, v in com if mes.year == 2029][0]
    assert round(em_2029, 0) == round((1.30 - 0.15 - 0.50) * 4000, 0)


def test_sem_escalar_mantem_o_percentual_de_hoje():
    sem = serie_futura(_resumo(), 12, 0.0, 0.0, _modelo(), escalar_fio_b=False)
    assert all(round(v) == round(_modelo().liquido_kwh_base * 4000) for _, v in sem)


def test_reajuste_aumenta_e_degradacao_reduz():
    base = serie_futura(_resumo(), 24, 0.0, 0.0, _modelo(), False)[-1][1]
    assert serie_futura(_resumo(), 24, 0.06, 0.0, _modelo(), False)[-1][1] > base
    assert serie_futura(_resumo(), 24, 0.0, 0.05, _modelo(), False)[-1][1] < base


def test_serie_sem_modelo_parte_da_media_recente():
    futuro = serie_futura(_resumo(3000.0), 3, 0.0, 0.0)
    assert [round(v) for _, v in futuro] == [3000, 3000, 3000]
    assert str(futuro[0][0]) == "2026-10"


def test_sazonalidade_neutra_sem_dados():
    assert sazonalidade(pd.DataFrame({"uc": [], "mes_ref": [], "injetado_kwh": [], "geradora": []})) == {m: 1.0 for m in range(1, 13)}


def test_sazonalidade_normalizada_em_media_1():
    ano = [3000, 2800, 2600, 2700, 3000, 3300, 3500, 3600, 3500, 3400, 3200, 3100]
    df = _injecao(("A", [100, 200] + ano + ano), inicio="2024-11")  # 2 meses de partida + 2 anos
    fatores = sazonalidade(df)
    assert round(sum(fatores.values()) / 12, 6) == 1.0
    assert fatores[8] > fatores[3]  # agosto gera mais que março


def test_meses_de_partida_sao_descartados():
    df = _injecao(("A", [500, 900, 3000, 3000, 3000]))
    series = projecao._injecao_por_usina(df)
    assert list(series["A"]) == [3000, 3000, 3000]


def test_segunda_usina_nao_aparece_como_degradacao_negativa_nem_crescimento():
    a = [3000.0] * 24
    b = [0.0] * 12 + [1500.0] * 12   # entrou no segundo ano
    df = _injecao(("A", a), ("B", b))
    variacao, n = projecao.degradacao_observada(df)
    assert abs(variacao) < 1e-9 and n > 0


def test_producao_anual_equivalente_soma_as_usinas():
    df = _injecao(("A", [3000.0] * 14), ("B", [1000.0] * 14))
    assert round(projecao.producao_anual_equivalente(df)) == 4000


def test_calibrar_recupera_o_fio_b_cheio():
    base = pd.DataFrame({
        "uc": ["1"] * 6, "mes_ref": [f"2026-{m:02d}" for m in range(4, 10)], "compensado_kwh": [1000.0] * 6,
        "valor_compensado_rs": [1300.0] * 6, "fio_b_rs": [300.0] * 6, "beneficio_rs": [150.0] * 6,
        "injetado_kwh": [1000.0] * 6, "geradora": [True] * 6,
    })
    modelo = calibrar(base)
    assert round(modelo.fio_b_cheio_kwh, 3) == 0.5     # 0,30 R$/kWh a 60% → 0,50 a 100%
    assert round(modelo.bruto_kwh, 3) == 1.3 and round(modelo.remanescente_kwh, 3) == 0.15


def test_projecao_anual_acumula_reais_e_projetados():
    resumo = pd.DataFrame({"mes_ref": [f"2025-{m:02d}" for m in range(1, 13)], "economia_rs": [1000.0] * 12})
    tabela = projecao_anual(resumo, investimento=24000, n_anos=3, reajuste=0.0, degradacao=0.0)
    assert list(tabela["ano"]) == [1, 2, 3]
    assert round(tabela["economia_acumulada_rs"].iloc[-1]) == 36000
    assert round(tabela["roi_acumulado_pct"].iloc[-1]) == 50
