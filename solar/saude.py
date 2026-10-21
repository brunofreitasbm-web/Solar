"""Saúde das usinas: compara a geração de cada geradora com o próprio histórico."""

import pandas as pd

from solar import geracao

LIMIAR_RELATIVO = 0.8  # abaixo de 80% do que a própria usina costuma render
MESES_PARA_QUEDA_PERSISTENTE = 2


def avaliar(df_geradoras: pd.DataFrame, performance_ratio: float) -> pd.DataFrame:
    """A fatura só informa a energia injetada (sem o autoconsumo), então a razão contra a
    NASA fica sempre abaixo de 100%. Por isso o alerta usa a razão relativa à mediana da usina."""
    base = geracao.avaliar_geracao(df_geradoras, performance_ratio)
    if base.empty:
        return base
    mediana = base.groupby("uc")["razao"].transform("median")
    base["razao_relativa"] = base["razao"] / mediana
    base["alerta"] = base["razao_relativa"] < LIMIAR_RELATIVO
    return base


def quedas_persistentes(avaliacao: pd.DataFrame) -> list[str]:
    """UCs cujos últimos meses seguidos ficaram todos abaixo do limiar."""
    if avaliacao.empty:
        return []
    ucs = []
    for uc, grupo in avaliacao.sort_values("mes_ref").groupby("uc"):
        ultimos = grupo.tail(MESES_PARA_QUEDA_PERSISTENTE)
        if len(ultimos) == MESES_PARA_QUEDA_PERSISTENTE and ultimos["alerta"].all():
            ucs.append(uc)
    return ucs
