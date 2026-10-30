import pytest

from solar import db
from solar import alertas
from solar.loggers import repositorio, strings
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
