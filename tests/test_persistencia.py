import sqlite3

import pytest

from solar import db
from solar.faturas import repositorio
from solar.faturas.modelo import Fatura
from solar.faturas.parser_equatorial import interpretar

TEXTO = """
DATA DE EMISSÃO: 10/06/2025
BRUNO PINTO FREITAS 09/05/2025 10/06/2025 32 11/07/2025
2.673.440.013-48 https://dfe-portal.svrs.rs.gov.br/NFE/Consulta
06/2025 25/06/2025 R$ 232,47 10/06/2025 às 18:35:08
de energia na modalidade Distribuição Percentual das seguintes UCs: 3033711769(13%),2.312.367.013-40(12,40%). Unidade
Consumo (kWh) 38,85 1,255084 0,938450 3,05 9,26 48,76 PIS 295,60 1,3751 4,06
Consumo Compensado (kWh) 332,14 0,941109 0,703500 19,53 59,39 312,58
Parc. Inj. s/ Desc. - GD2 (kWh) 332,14 0,230987 0,175335 4,87 13,62 76,72
Benefício Tarifário Bruto SCEE 14,66 41,04 231,13
Adicional Bandeira 0,11 0,33 1,73 OUT/24 414
Adicional Bandeira 0,12 0,35 1,86 NOV/24 522
Benefício Tarifário Líquido SCEE -175,43 S FEV/25 444
Cip-Ilum Pub Pref Munic 42,74
Multa 4,51
Juros 0,45
58108183 Consumo ATIVO TOTAL 80.056 80.427 1,00 371 kWh
"""


def test_parser_le_datas_composicao_e_rateio():
    f = interpretar(TEXTO)
    assert (f.vencimento, f.emissao, f.proxima_leitura) == ("2025-06-25", "2025-06-10", "2025-07-11")
    assert (f.consumo_rs, f.fio_b_rs, f.beneficio_rs) == (48.76, 76.72, 55.70)
    assert (f.bandeira_rs, f.cip_rs, f.multa_rs, f.juros_rs) == (3.59, 42.74, 4.51, 0.45)
    assert f.outros_rs == 0.0  # as linhas fecham exatamente no total da fatura
    assert f.rateio == {"3033711769": 13.0, "231236701340": 12.4}


def test_parser_fatura_sem_composicao_devolve_none_e_deixa_o_resto_em_outros():
    f = interpretar("06/2025 25/06/2025 R$ 100,00 10/06/2025 às 18:35:08\n2.673.440.013-48 https://x\nConsumo ATIVO TOTAL 1 2 1,00 1 kWh")
    assert f.fio_b_rs is None and f.cip_rs is None and f.rateio == {}
    assert f.outros_rs == 100.0


@pytest.fixture
def banco(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "CAMINHO_DB", tmp_path / "solar.db")
    return tmp_path / "solar.db"


def test_migracao_acrescenta_colunas_sem_perder_dados(banco):
    con = sqlite3.connect(banco)
    con.execute("CREATE TABLE unidades (uc TEXT PRIMARY KEY, apelido TEXT NOT NULL DEFAULT '', endereco TEXT NOT NULL DEFAULT '', "
                "geradora INTEGER NOT NULL DEFAULT 0, kwp REAL, lat REAL, lon REAL, data_pedido_conexao TEXT)")
    con.execute("CREATE TABLE faturas (id INTEGER PRIMARY KEY AUTOINCREMENT, uc TEXT NOT NULL, mes_ref TEXT NOT NULL, "
                "consumo_kwh REAL NOT NULL DEFAULT 0, injetado_kwh REAL NOT NULL DEFAULT 0, compensado_kwh REAL NOT NULL DEFAULT 0, "
                "saldo_creditos_kwh REAL NOT NULL DEFAULT 0, credito_rs REAL, tarifa_kwh REAL, total_rs REAL NOT NULL DEFAULT 0, "
                "bandeira TEXT NOT NULL DEFAULT '', arquivo TEXT NOT NULL DEFAULT '', origem TEXT NOT NULL DEFAULT 'manual', UNIQUE (uc, mes_ref))")
    con.execute("INSERT INTO faturas (uc, mes_ref, total_rs) VALUES ('1', '2025-01', 99.5)")
    con.commit()
    con.close()

    with db.conexao() as c:
        colunas = {l["name"] for l in c.execute("PRAGMA table_info(faturas)")}
        total = c.execute("SELECT total_rs FROM faturas").fetchone()["total_rs"]
    assert {"vencimento", "fio_b_rs", "rateio_json", "cip_rs"} <= colunas
    assert total == 99.5


def test_salvar_e_ler_preserva_composicao_e_rateio(banco):
    repositorio.salvar(Fatura(uc="1", mes_ref="2026-09", total_rs=100.0, fio_b_rs=12.5, vencimento="2026-10-17",
                              rateio={"2": 30.0}, injetado_kwh=10.0))
    df = repositorio.tabela()
    linha = df.iloc[0]
    assert linha["fio_b_rs"] == 12.5 and linha["vencimento"] == "2026-10-17"
    assert linha["rateio"] == {"2": 30.0}
    assert bool(linha["geradora"])  # injetou energia → sugerida como geradora


def test_reimportar_substitui_a_fatura_do_mesmo_mes(banco):
    repositorio.salvar(Fatura(uc="1", mes_ref="2026-09", total_rs=100.0))
    repositorio.salvar(Fatura(uc="1", mes_ref="2026-09", total_rs=150.0))
    df = repositorio.tabela()
    assert len(df) == 1 and df.iloc[0]["total_rs"] == 150.0
