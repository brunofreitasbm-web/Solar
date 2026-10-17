"""Auditoria das faturas: procura cobranças e compensações que não batem com o que a fatura
deveria mostrar, para você reclamar com a Equatorial com números na mão."""

import pandas as pd

from solar.auditoria import ciclo, compensacao, config, encargos, fio_b, saldo
from solar.auditoria.achado import Achado

REGRAS = (saldo.auditar, compensacao.auditar, fio_b.auditar, ciclo.auditar, encargos.auditar)


def auditar(df: pd.DataFrame) -> list[Achado]:
    """Todos os achados, do mais grave e recente para o menos."""
    if df.empty:
        return []
    recentes = sorted(df["mes_ref"].unique())[-config.MESES_ANALISADOS:]
    achados = [a for regra in REGRAS for a in regra(df) if a.mes_ref in recentes]
    ordem = {"erro": 0, "aviso": 1}
    return sorted(achados, key=lambda a: (ordem[a.gravidade], _inverter(a.mes_ref), a.uc))


def _inverter(mes_ref: str) -> str:
    return "".join(chr(255 - ord(c)) for c in mes_ref)
