import pytest

from solar import db
from solar.loggers import repositorio
from solar.loggers.solplanet import FalhaLogger, interpretar

BRUTO = {
    "flg": 1, "tim": "20261030150951", "tmp": 560, "fac": 5998, "pac": 1458, "sac": 1458, "qac": 12,
    "eto": 322135, "etd": 497, "hto": 7193, "pf": 99, "wan": 0, "err": 0,
    "vac": [2296], "iac": [64], "vpv": [2704, 2813, 2902], "ipv": [191, 191, 194], "str": [],
}


@pytest.fixture(autouse=True)
def banco_temporario(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "CAMINHO_DB", tmp_path / "teste.db")


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
