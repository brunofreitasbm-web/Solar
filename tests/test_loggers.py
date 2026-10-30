from datetime import date

import pandas as pd
import pytest

from solar import alertas, db
from solar.loggers import comparativo, repositorio, strings
from solar.loggers.solplanet import FalhaLogger, interpretar

BRUTO = {
    "flg": 1, "tim": "20261030150951", "tmp": 560, "fac": 5998, "pac": 1458, "sac": 1458, "qac": 12,
    "eto": 322135, "etd": 497, "hto": 7193, "pf": 99, "wan": 0, "err": 0,
    "vac": [2296], "iac": [64], "vpv": [2704, 2813, 2902], "ipv": [191, 191, 194], "str": [],
}


@pytest.fixture(autouse=True)
def banco_temporario(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "CAMINHO_DB", tmp_path / "teste.db")
    monkeypatch.setattr(db, "CAMINHO_DB_LEITURAS", tmp_path / "leituras.db")


def test_interpretar_converte_unidades():
    leitura = interpretar(BRUTO)
    assert leitura.lida_em == "2026-10-30T15:09:51"
    assert leitura.potencia_w == 1458
    assert leitura.energia_dia_kwh == 49.7
    assert leitura.energia_total_kwh == 32213.5
    assert leitura.temperatura_c == 56.0
    assert leitura.tensao_ac_v == 229.6
    assert leitura.frequencia_hz == 59.98


def test_interpretar_rejeita_resposta_incompleta():
    with pytest.raises(FalhaLogger):
        interpretar({"flg": 1})


def test_gravar_leitura_nao_duplica_e_agrega_por_dia():
    repositorio.gravar_leitura("AP1", interpretar(BRUTO))
    repositorio.gravar_leitura("AP1", interpretar(BRUTO))
    repositorio.gravar_leitura("AP1", interpretar({**BRUTO, "tim": "20261030170000", "etd": 520}))
    assert repositorio.geracao_diaria("AP1") == [{"dia": "2026-10-30", "kwh": 52.0}]


def test_interpretar_le_tensao_e_corrente_das_strings():
    leitura = interpretar(BRUTO)
    assert leitura.tensoes_pv_v == (270.4, 281.3, 290.2)
    assert leitura.correntes_pv_a == (1.91, 1.91, 1.94)


def test_string_que_funcionava_e_caiu_gera_alerta():
    assert strings.indices_em_falha([386.4, 5.3, 402.1], [390.0, 380.0, 405.0], 1681) == [1]


def test_string_que_nunca_teve_painel_nao_alerta():
    assert strings.indices_em_falha([386.4, 5.3, 402.1], [390.0, 6.0, 405.0], 1681) == []


def test_sem_geracao_relevante_nao_alerta():
    assert strings.indices_em_falha([2.0, 1.0], [390.0, 380.0], 80) == []


def test_historico_guarda_maior_tensao_por_string():
    repositorio.gravar_leitura("AP1", interpretar({**BRUTO, "vpv": [3000, 100]}))
    repositorio.gravar_leitura("AP1", interpretar({**BRUTO, "tim": "20261030160000", "vpv": [2000, 3500]}))
    assert repositorio.maior_tensao_por_string("AP1", 3650) == [300.0, 350.0]


def test_alerta_de_string_aparece_na_central_de_alertas():
    from datetime import datetime, timedelta
    agora = datetime.now().strftime("%Y%m%d%H%M%S")
    ontem = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d%H%M%S")
    repositorio.cadastrar_logger("AP1", "Praia 1", "192.168.1.18")
    repositorio.gravar_leitura("AP1", interpretar({**BRUTO, "tim": ontem, "vpv": [3000, 3000], "ipv": [1, 1]}))
    repositorio.gravar_leitura("AP1", interpretar({**BRUTO, "tim": agora, "vpv": [3000, 40], "ipv": [190, 0]}))
    lista = alertas.de_loggers()
    assert len(lista) == 1 and "string 2" in lista[0].texto and lista[0].gravidade == "erro"


def test_importar_loggers_de_outro_banco_nao_duplica(tmp_path, monkeypatch):
    origem = tmp_path / "origem.db"
    monkeypatch.setattr(db, "CAMINHO_DB", origem)
    repositorio.cadastrar_logger("AP1", "Praia 1", "192.168.1.18")
    monkeypatch.setattr(db, "CAMINHO_DB", tmp_path / "destino.db")
    assert repositorio.importar_loggers(str(origem)) == 1
    assert repositorio.importar_loggers(str(origem)) == 0
    assert [l["sn"] for l in repositorio.listar_loggers()] == ["AP1"]


def _leitura_total(sn: str, quando: str, eto_kwh: float) -> None:
    repositorio.gravar_leitura(sn, interpretar({**BRUTO, "tim": quando, "eto": int(eto_kwh * 10)}))


def test_situacao_do_ciclo():
    assert comparativo.situacao(900, 1000) == "ok"
    assert comparativo.situacao(1040, 1000) == "ok"  # dentro da margem de alinhamento do ciclo
    assert comparativo.situacao(1200, 1000) == "inconsistente"
    assert comparativo.situacao(900, None) == "sem_dados"


def test_geracao_do_periodo_usa_contador_dos_dois_inversores():
    _leitura_total("A", "20260101170000", 1000)
    _leitura_total("A", "20260131170000", 1400)
    _leitura_total("B", "20260101170000", 500)
    _leitura_total("B", "20260131170000", 800)
    assert comparativo.geracao_no_periodo(["A", "B"], date(2026, 1, 1), date(2026, 1, 31)) == 700


def test_geracao_do_periodo_sem_marco_numa_ponta_devolve_none():
    _leitura_total("A", "20260101170000", 1000)
    assert comparativo.geracao_no_periodo(["A"], date(2026, 1, 1), date(2026, 1, 31)) is None
    assert comparativo.geracao_no_periodo([], date(2026, 1, 1), date(2026, 1, 31)) is None


def test_geracao_do_periodo_ignora_contador_que_voltou_a_zero():
    _leitura_total("A", "20260101170000", 1000)
    _leitura_total("A", "20260131170000", 5)
    assert comparativo.geracao_no_periodo(["A"], date(2026, 1, 1), date(2026, 1, 31)) is None


def test_ciclos_da_unidade_comparam_com_a_fatura():
    repositorio.cadastrar_logger("A", "Inv 1", "192.168.1.17", uc="UC1")
    _leitura_total("A", "20260110170000", 1000)
    _leitura_total("A", "20260209170000", 1900)
    faturas = pd.DataFrame([
        {"uc": "UC1", "mes_ref": "2026-01", "emissao": "2026-01-10", "injetado_kwh": 800.0},
        {"uc": "UC1", "mes_ref": "2026-02", "emissao": "2026-02-09", "injetado_kwh": 700.0},
        {"uc": "OUTRA", "mes_ref": "2026-02", "emissao": "2026-02-09", "injetado_kwh": 1.0},
    ])
    (ciclo,) = comparativo.ciclos_da_unidade("UC1", faturas)
    assert (ciclo.mes_ref, ciclo.geracao_kwh, ciclo.injetado_kwh) == ("2026-02", 900, 700)
    assert ciclo.situacao == "ok" and ciclo.autoconsumo_kwh == 200


def test_ciclo_com_intervalo_absurdo_e_descartado():
    faturas = pd.DataFrame([
        {"uc": "UC1", "mes_ref": "2026-01", "emissao": "2026-01-10", "injetado_kwh": 800.0},
        {"uc": "UC1", "mes_ref": "2026-05", "emissao": "2026-05-10", "injetado_kwh": 700.0},
    ])
    assert comparativo.ciclos_da_unidade("UC1", faturas) == []


def _geradora(meses_injetado: list[tuple[str, str, float]]) -> pd.DataFrame:
    return pd.DataFrame([{"uc": "UC1", "mes_ref": m, "emissao": e, "injetado_kwh": i, "lat": -1.0, "lon": -47.0, "kwp": 20.0,
                          "geradora": True} for m, e, i in meses_injetado])


@pytest.fixture
def irradiacao_fixa(monkeypatch):
    from solar import geracao
    monkeypatch.setattr(geracao, "_irradiacao_mensal", lambda lat, lon: {f"{m:02d}": 5.0 for m in range(1, 13)})


def test_alerta_usa_geracao_do_logger_quando_ha_ciclo_medido(irradiacao_fixa):
    from solar import saude
    repositorio.cadastrar_logger("A", "Inv 1", "192.168.1.17", uc="UC1")
    _leitura_total("A", "20260910170000", 1000)
    _leitura_total("A", "20261010170000", 1000 + 30 * 5 * 20 * 0.78)  # exatamente o esperado em 30 dias
    df = _geradora([("2026-09", "2026-09-10", 500.0), ("2026-10", "2026-10-10", 900.0)])
    av = saude.avaliar(df, 0.78).set_index("mes_ref")
    assert av.loc["2026-10", "fonte"] == "logger" and av.loc["2026-09", "fonte"] == "fatura"
    assert av.loc["2026-10", "razao"] == pytest.approx(1.0, rel=0.01)
    assert not av.loc["2026-10", "alerta"]


def test_logger_com_geracao_baixa_dispara_alerta_mesmo_sem_historico(irradiacao_fixa):
    from solar import saude
    repositorio.cadastrar_logger("A", "Inv 1", "192.168.1.17", uc="UC1")
    _leitura_total("A", "20260910170000", 1000)
    _leitura_total("A", "20261010170000", 1000 + 0.5 * 30 * 5 * 20 * 0.78)  # metade do esperado
    df = _geradora([("2026-09", "2026-09-10", 300.0), ("2026-10", "2026-10-10", 290.0)])
    av = saude.avaliar(df, 0.78).set_index("mes_ref")
    assert av.loc["2026-10", "alerta"]


def test_ciclo_inconsistente_do_logger_volta_para_a_fatura(irradiacao_fixa):
    from solar import saude
    repositorio.cadastrar_logger("A", "Inv 1", "192.168.1.17", uc="UC1")
    _leitura_total("A", "20260910170000", 1000)
    _leitura_total("A", "20261010170000", 1100)  # gerou 100, mas a Equatorial faturou 900 injetados
    df = _geradora([("2026-09", "2026-09-10", 800.0), ("2026-10", "2026-10-10", 900.0)])
    av = saude.avaliar(df, 0.78).set_index("mes_ref")
    assert av.loc["2026-10", "fonte"] == "fatura"
