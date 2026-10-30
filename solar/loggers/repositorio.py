import json
from datetime import datetime, timedelta

from solar.db import conexao, conexao_leituras
from solar.loggers.solplanet import Leitura


def cadastrar_logger(sn: str, nome: str, ip: str, porta: int = 8484, uc: str | None = None) -> None:
    with conexao() as con:
        con.execute(
            """INSERT INTO loggers (sn, nome, ip, porta, uc) VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(sn) DO UPDATE SET nome = excluded.nome, ip = excluded.ip, porta = excluded.porta,
                                             uc = COALESCE(excluded.uc, loggers.uc)""",
            (sn, nome, ip, porta, uc),
        )


def atualizar_ip(sn: str, ip: str) -> None:
    with conexao() as con:
        con.execute("UPDATE loggers SET ip = ? WHERE sn = ?", (ip, sn))


def vincular_unidade(sn: str, uc: str | None) -> None:
    with conexao() as con:
        con.execute("UPDATE loggers SET uc = ? WHERE sn = ?", (uc, sn))


def importar_loggers(caminho_origem: str) -> int:
    """Copia os loggers cadastrados em outro banco (ex.: o de uma instalação anterior). Devolve quantos copiou."""
    with conexao() as con:
        con.execute("ATTACH DATABASE ? AS origem", (caminho_origem,))
        try:
            con.execute("INSERT OR IGNORE INTO loggers (sn, nome, ip, porta) SELECT sn, nome, ip, porta FROM origem.loggers")
            copiados = con.execute("SELECT changes()").fetchone()[0]
        finally:
            con.commit()
            con.execute("DETACH DATABASE origem")
    return copiados


def listar_loggers() -> list[dict]:
    with conexao() as con:
        return [dict(l) for l in con.execute("SELECT sn, nome, ip, porta, uc FROM loggers ORDER BY nome")]


def gravar_leitura(sn: str, leitura: Leitura) -> None:
    with conexao_leituras() as con:
        con.execute(
            """INSERT OR IGNORE INTO leituras_logger
               (sn, lida_em, potencia_w, energia_dia_kwh, energia_total_kwh,
                temperatura_c, tensao_ac_v, frequencia_hz, codigo_erro, tensoes_pv_json, correntes_pv_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (sn, leitura.lida_em, leitura.potencia_w, leitura.energia_dia_kwh, leitura.energia_total_kwh,
             leitura.temperatura_c, leitura.tensao_ac_v, leitura.frequencia_hz, leitura.codigo_erro,
             json.dumps(leitura.tensoes_pv_v), json.dumps(leitura.correntes_pv_a)),
        )


def geracao_diaria(sn: str) -> list[dict]:
    """Maior energia_dia_kwh registrada em cada dia (o contador do inversor zera à meia-noite)."""
    with conexao_leituras() as con:
        linhas = con.execute(
            """SELECT substr(lida_em, 1, 10) AS dia, MAX(energia_dia_kwh) AS kwh
               FROM leituras_logger WHERE sn = ? GROUP BY dia ORDER BY dia""",
            (sn,),
        )
        return [dict(l) for l in linhas]


def remover_logger(sn: str) -> None:
    with conexao_leituras() as con:
        con.execute("DELETE FROM leituras_logger WHERE sn = ?", (sn,))
    with conexao() as con:
        con.execute("DELETE FROM loggers WHERE sn = ?", (sn,))


def ultima_leitura(sn: str) -> dict | None:
    with conexao_leituras() as con:
        linha = con.execute(
            "SELECT * FROM leituras_logger WHERE sn = ? ORDER BY lida_em DESC LIMIT 1", (sn,)
        ).fetchone()
    if not linha:
        return None
    leitura = dict(linha)
    leitura["tensoes_pv_v"] = json.loads(leitura.pop("tensoes_pv_json") or "[]")
    leitura["correntes_pv_a"] = json.loads(leitura.pop("correntes_pv_json") or "[]")
    return leitura


def curva_do_dia(sn: str, dia: str) -> list[dict]:
    with conexao_leituras() as con:
        linhas = con.execute(
            "SELECT lida_em, potencia_w FROM leituras_logger WHERE sn = ? AND substr(lida_em, 1, 10) = ? ORDER BY lida_em",
            (sn, dia),
        )
        return [dict(l) for l in linhas]


def maior_tensao_por_string(sn: str, dias: int) -> list[float]:
    """Maior tensão já lida em cada string nos últimos `dias` — mostra quais strings já estiveram em uso."""
    desde = (datetime.now() - timedelta(days=dias)).isoformat(timespec="seconds")
    with conexao_leituras() as con:
        linhas = con.execute(
            "SELECT tensoes_pv_json FROM leituras_logger WHERE sn = ? AND lida_em >= ? AND tensoes_pv_json IS NOT NULL",
            (sn, desde),
        ).fetchall()
    maiores: list[float] = []
    for linha in linhas:
        for i, v in enumerate(json.loads(linha["tensoes_pv_json"])):
            if i >= len(maiores):
                maiores.append(v)
            else:
                maiores[i] = max(maiores[i], v)
    return maiores


def ultima_leitura_ate(sn: str, limite: str) -> dict | None:
    """Última leitura gravada em ou antes de `limite` (ISO). O contador total só avança, então serve de marco de data."""
    with conexao_leituras() as con:
        linha = con.execute(
            "SELECT lida_em, energia_total_kwh FROM leituras_logger WHERE sn = ? AND lida_em <= ? ORDER BY lida_em DESC LIMIT 1",
            (sn, limite),
        ).fetchone()
    return dict(linha) if linha else None
