import pandas as pd

from solar.rateio import analisar, sugerir_percentuais


def test_percentuais_somam_100_com_duas_casas():
    pct = sugerir_percentuais({"a": 333.0, "b": 333.0, "c": 334.0}, {}, 1000.0)
    assert round(sum(pct.values()), 2) == 100.0
    assert all(round(v, 2) == v for v in pct.values())


def test_sobra_de_energia_e_repartida_proporcional_a_demanda():
    pct = sugerir_percentuais({"a": 100.0, "b": 300.0}, {}, 800.0)
    assert pct == {"a": 25.0, "b": 75.0}


def test_unidade_sem_sobra_recebe_so_o_que_consome():
    pct = sugerir_percentuais({"a": 100.0, "b": 100.0}, {}, 400.0, sem_sobra=frozenset({"a"}))
    # a recebe exatamente 100 de 400; b fica com o resto
    assert pct["a"] == 25.0 and pct["b"] == 75.0


def test_falta_de_energia_cobre_primeiro_quem_tem_kwh_mais_valioso():
    pct = sugerir_percentuais({"barato": 500.0, "caro": 500.0}, {"barato": 0.5, "caro": 1.2}, 600.0)
    assert pct["caro"] == round(100 * 500 / 600, 2)
    assert pct["barato"] == round(100 * 100 / 600, 2)


def test_sem_producao_ou_demanda_devolve_zeros():
    assert sugerir_percentuais({"a": 100.0}, {}, 0.0) == {"a": 0.0}
    assert sugerir_percentuais({}, {}, 100.0) == {}


def _fatura(uc, mes, consumo, compensado, economia, injetado=0.0, geradora=False, saldo=0.0, rateio=None):
    return {"uc": uc, "mes_ref": mes, "consumo_kwh": consumo, "compensado_kwh": compensado, "economia_rs": economia,
            "injetado_kwh": injetado, "geradora": geradora, "saldo_creditos_kwh": saldo, "rateio": rateio or {}}


def _df(meses=("2026-08", "2026-09")):
    linhas = []
    for m in meses:
        linhas += [
            _fatura("G", m, 100, 0, 0, injetado=1000.0, geradora=True),
            _fatura("A", m, 600, 500, 400, saldo=0.0, rateio={"G": 30.0}),    # recebe 300, consome 500 → descoberta
            _fatura("B", m, 500, 400, 320, saldo=600.0, rateio={"G": 70.0}),  # recebe 700, consome 400 → sobra
        ]
    return pd.DataFrame(linhas)


def test_analise_identifica_descoberta_e_saldo_parado():
    r = analisar(_df(), {"G": "Geradora", "A": "A", "B": "B"}, meses_base=2)
    a = r.tabela.set_index("uc").loc["A"]
    assert round(a["alocado_atual_kwh"]) == 300 and round(a["descoberto_atual_kwh"]) == 200
    assert r.saldo_parado_kwh == 600
    assert r.ganho_mensal_rs > 0


def test_analise_sugere_mais_para_quem_esta_descoberto_e_menos_para_quem_tem_saldo():
    r = analisar(_df(), {}, meses_base=2).tabela.set_index("uc")
    assert r.loc["A", "sugerido_pct"] > 30.0
    assert r.loc["B", "sugerido_pct"] < 70.0
    assert round(r["sugerido_pct"].sum(), 2) == 100.0


def test_sem_geradora_nao_ha_analise():
    df = _df()
    df["injetado_kwh"] = 0.0
    assert analisar(df, {}, meses_base=2) is None
