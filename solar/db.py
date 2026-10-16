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
CREATE TABLE IF NOT EXISTS config (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cache_web (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
);
"""


@contextmanager
def conexao():
    CAMINHO_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(CAMINHO_DB)
    con.row_factory = sqlite3.Row
    try:
        con.executescript(SCHEMA)
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
