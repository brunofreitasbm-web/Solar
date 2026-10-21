"""Fila de faturas lidas que ainda esperam revisão. Fica no banco para sobreviver a recarregar a página."""

import json
from dataclasses import asdict

from solar.db import conexao
from solar.faturas.extracao import ResultadoExtracao
from solar.faturas.modelo import Fatura


def adicionar(resultado: ResultadoExtracao) -> None:
    dados = json.dumps({"fatura": asdict(resultado.fatura), "aviso": resultado.aviso})
    with conexao() as con:
        con.execute("INSERT OR REPLACE INTO faturas_pendentes (arquivo, dados_json) VALUES (?, ?)",
                    (resultado.fatura.arquivo, dados))


def listar() -> list[ResultadoExtracao]:
    with conexao() as con:
        linhas = con.execute("SELECT dados_json FROM faturas_pendentes ORDER BY id").fetchall()
    resultados = []
    for linha in linhas:
        dados = json.loads(linha["dados_json"])
        resultados.append(ResultadoExtracao(Fatura(**dados["fatura"]), dados["aviso"]))
    return resultados


def contar() -> int:
    with conexao() as con:
        return con.execute("SELECT COUNT(*) FROM faturas_pendentes").fetchone()[0]


def remover(arquivo: str) -> None:
    with conexao() as con:
        con.execute("DELETE FROM faturas_pendentes WHERE arquivo = ?", (arquivo,))
