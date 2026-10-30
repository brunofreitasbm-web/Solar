from solar.db import conexao
from solar.loggers.solplanet import Leitura


def cadastrar_logger(sn: str, nome: str, ip: str, porta: int = 8484) -> None:
    with conexao() as con:
        con.execute(
            "INSERT OR REPLACE INTO loggers (sn, nome, ip, porta) VALUES (?, ?, ?, ?)", (sn, nome, ip, porta)
        )


def listar_loggers() -> list[dict]:
    with conexao() as con:
        return [dict(l) for l in con.execute("SELECT sn, nome, ip, porta FROM loggers ORDER BY nome")]


def gravar_leitura(sn: str, leitura: Leitura) -> None:
    with conexao() as con:
        con.execute(
            """INSERT OR IGNORE INTO leituras_logger
               (sn, lida_em, potencia_w, energia_dia_kwh, energia_total_kwh,
                temperatura_c, tensao_ac_v, frequencia_hz, codigo_erro)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (sn, leitura.lida_em, leitura.potencia_w, leitura.energia_dia_kwh, leitura.energia_total_kwh,
             leitura.temperatura_c, leitura.tensao_ac_v, leitura.frequencia_hz, leitura.codigo_erro),
        )


def geracao_diaria(sn: str) -> list[dict]:
    """Maior energia_dia_kwh registrada em cada dia (o contador do inversor zera à meia-noite)."""
    with conexao() as con:
        linhas = con.execute(
            """SELECT substr(lida_em, 1, 10) AS dia, MAX(energia_dia_kwh) AS kwh
               FROM leituras_logger WHERE sn = ? GROUP BY dia ORDER BY dia""",
            (sn,),
        )
        return [dict(l) for l in linhas]
