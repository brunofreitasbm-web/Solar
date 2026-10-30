import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from solar.config import CAMINHO_DB

SCHEMA = """
CREATE TABLE IF NOT EXISTS unidades (
    uc TEXT PRIMARY KEY,
    apelido TEXT NOT NULL DEFAULT '',
    endereco TEXT NOT NULL DEFAULT '',
    geradora INTEGER NOT NULL DEFAULT 0,
    kwp REAL,
    lat REAL,
    lon REAL,
    data_pedido_conexao TEXT
);
CREATE TABLE IF NOT EXISTS faturas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uc TEXT NOT NULL REFERENCES unidades(uc),
    mes_ref TEXT NOT NULL,
    consumo_kwh REAL NOT NULL DEFAULT 0,
    injetado_kwh REAL NOT NULL DEFAULT 0,
    compensado_kwh REAL NOT NULL DEFAULT 0,
    saldo_creditos_kwh REAL NOT NULL DEFAULT 0,
    credito_rs REAL,
    tarifa_kwh REAL,
    total_rs REAL NOT NULL DEFAULT 0,
    bandeira TEXT NOT NULL DEFAULT '',
    arquivo TEXT NOT NULL DEFAULT '',
    origem TEXT NOT NULL DEFAULT 'manual',
    UNIQUE (uc, mes_ref)
);
CREATE TABLE IF NOT EXISTS usinas_planejadas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    endereco TEXT NOT NULL DEFAULT '',
    uc TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Em instalação',
    paineis INTEGER NOT NULL,
    potencia_painel_w REAL NOT NULL,
    inversor TEXT NOT NULL DEFAULT '',
    potencia_inversor_kw REAL NOT NULL DEFAULT 0,
    custo_total REAL,
    valor_financiado REAL,
    parcela_mensal REAL,
    qtd_parcelas INTEGER,
    data_operacao TEXT,
    consumo_kwh_mes REAL,
    simultaneidade REAL NOT NULL DEFAULT 0.4,
    lat REAL,
    lon REAL
);
CREATE TABLE IF NOT EXISTS config (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS faturas_pendentes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    arquivo TEXT NOT NULL UNIQUE,
    dados_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cache_web (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS telegram_enviados (
    uc TEXT NOT NULL,
    mes_ref TEXT NOT NULL,
    enviado_em TEXT NOT NULL,
    PRIMARY KEY (uc, mes_ref)
);
CREATE TABLE IF NOT EXISTS loggers (
    sn TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    ip TEXT NOT NULL,
    porta INTEGER NOT NULL DEFAULT 8484
);
CREATE TABLE IF NOT EXISTS leituras_logger (
    sn TEXT NOT NULL,
    lida_em TEXT NOT NULL,
    potencia_w REAL,
    energia_dia_kwh REAL,
    energia_total_kwh REAL,
    temperatura_c REAL,
    tensao_ac_v REAL,
    frequencia_hz REAL,
    codigo_erro INTEGER,
    tensoes_pv_json TEXT,
    correntes_pv_json TEXT,
    PRIMARY KEY (sn, lida_em)
);
"""

# Colunas acrescentadas depois da primeira versão — aplicadas por migração, sem apagar dados.
COLUNAS_FATURAS_NOVAS = (
    ("vencimento", "TEXT"), ("emissao", "TEXT"), ("proxima_leitura", "TEXT"),
    ("consumo_rs", "REAL"), ("fio_b_rs", "REAL"), ("beneficio_rs", "REAL"),
    ("bandeira_rs", "REAL"), ("cip_rs", "REAL"), ("multa_rs", "REAL"),
    ("juros_rs", "REAL"), ("outros_rs", "REAL"), ("rateio_json", "TEXT"),
    ("pix_copia_cola", "TEXT"), ("codigo_barras", "TEXT"),
    ("pago_em", "TEXT"), ("valor_pago", "REAL"),
)


COLUNAS_LEITURAS_NOVAS = (("tensoes_pv_json", "TEXT"), ("correntes_pv_json", "TEXT"))


def _migrar(con: sqlite3.Connection) -> None:
    leituras = {l["name"] for l in con.execute("PRAGMA table_info(leituras_logger)")}
    for nome, tipo in COLUNAS_LEITURAS_NOVAS:
        if nome not in leituras:
            con.execute(f"ALTER TABLE leituras_logger ADD COLUMN {nome} {tipo}")
    existentes = {l["name"] for l in con.execute("PRAGMA table_info(faturas)")}
    for nome, tipo in COLUNAS_FATURAS_NOVAS:
        if nome not in existentes:
            con.execute(f"ALTER TABLE faturas ADD COLUMN {nome} {tipo}")
    con.execute(
        """UPDATE unidades SET data_pedido_conexao =
           substr(data_pedido_conexao, 1, 4) || '-' || substr(data_pedido_conexao, 5, 2) || '-' || substr(data_pedido_conexao, 7, 2)
           WHERE data_pedido_conexao GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]'"""
    )


@contextmanager
def conexao():
    CAMINHO_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(CAMINHO_DB)
    con.row_factory = sqlite3.Row
    try:
        con.executescript(SCHEMA)
        _migrar(con)
        yield con
        con.commit()
    finally:
        con.close()


def ler_cache(chave: str) -> tuple[object, str] | None:
    with conexao() as con:
        linha = con.execute("SELECT valor, atualizado_em FROM cache_web WHERE chave = ?", (chave,)).fetchone()
    return (json.loads(linha["valor"]), linha["atualizado_em"]) if linha else None


def gravar_cache(chave: str, valor: object) -> None:
    with conexao() as con:
        con.execute(
            "INSERT OR REPLACE INTO cache_web (chave, valor, atualizado_em) VALUES (?, ?, ?)",
            (chave, json.dumps(valor), datetime.now().isoformat(timespec="seconds")),
        )
