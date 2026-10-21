from datetime import date

import pandas as pd
import pytest

from solar import alertas, anomalias, db, pagamentos, saude
from solar.faturas import repositorio
from solar.faturas.modelo import Fatura


def test_a_pagar_considera_so_a_ultima_fatura_sem_pagamento():
    df = pd.DataFrame(dict(uc=["1", "1", "2"], mes_ref=["2026-08", "2026-09", "2026-09"],
                           vencimento=["2026-09-10", "2026-10-10", "2026-10-25"], total_rs=[10.0, 20.0, 30.0],
                           pago_em=[None, None, "2026-10-01"]))
    r = pagamentos.a_pagar(df, {"1": "Casa"}, hoje=date(2026, 10, 17))
    assert list(r["unidade"]) == ["Casa"] and r["mes_ref"].iloc[0] == "2026-09"
    assert bool(r["vencida"].iloc[0]) and r["dias"].iloc[0] == -7


def test_a_pagar_sem_vencimento_devolve_vazio_com_colunas():
    df = pd.DataFrame(dict(uc=["1"], mes_ref=["2026-09"], vencimento=[""], total_rs=[1.0], pago_em=[None]))
    assert list(pagamentos.a_pagar(df, {}).columns) == pagamentos.COLUNAS


def test_consumo_fora_do_padrao_so_marca_desvio_grande():
    meses = [f"2026-0{m}" for m in range(1, 6)]
    df = pd.DataFrame(dict(uc=["1"] * 5, mes_ref=meses, consumo_kwh=[100.0, 100.0, 100.0, 100.0, 200.0]))
    r = anomalias.consumo_fora_do_padrao(df)
    assert len(r) == 1 and r["desvio_pct"].iloc[0] == pytest.approx(100.0)
    assert anomalias.consumo_fora_do_padrao(df.assign(consumo_kwh=[100.0, 100, 100, 100, 110])).empty


def test_consumo_com_pouco_historico_nao_alerta():
    df = pd.DataFrame(dict(uc=["1"] * 2, mes_ref=["2026-01", "2026-02"], consumo_kwh=[100.0, 500.0]))
    assert anomalias.consumo_fora_do_padrao(df).empty


def test_queda_persistente_exige_meses_seguidos_abaixo_do_limiar():
    av = pd.DataFrame(dict(uc=["1"] * 3 + ["2"] * 3, mes_ref=["2026-01", "2026-02", "2026-03"] * 2,
                           alerta=[False, True, True, True, True, False]))
    assert saude.quedas_persistentes(av) == ["1"]


def test_alertas_sem_faturas_so_traz_revisao():
    r = alertas.reunir(pd.DataFrame(), {}, 0.78, em_revisao=2)
    assert [a.pagina for a in r] == ["revisar-leitura"]


@pytest.fixture
def banco(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "CAMINHO_DB", tmp_path / "solar.db")


def test_pagamento_sobrevive_a_reimportar_a_fatura(banco):
    repositorio.salvar(Fatura(uc="1", mes_ref="2026-09", total_rs=100.0))
    repositorio.marcar_paga("1", "2026-09", "2026-10-05", 100.0)
    repositorio.salvar(Fatura(uc="1", mes_ref="2026-09", total_rs=150.0))
    linha = repositorio.tabela().iloc[0]
    assert linha["total_rs"] == 150.0 and linha["pago_em"] == "2026-10-05"
    repositorio.desmarcar_paga("1", "2026-09")
    assert repositorio.tabela().iloc[0]["pago_em"] is None
