"""Consumo fora do padrão: compara o último mês de cada unidade com a média dos meses anteriores."""

import pandas as pd

LIMIAR_DESVIO = 0.30
MESES_DE_BASE = 6
MINIMO_DE_MESES = 3


def consumo_fora_do_padrao(df: pd.DataFrame, limiar: float = LIMIAR_DESVIO) -> pd.DataFrame:
    colunas = ["uc", "mes_ref", "consumo_kwh", "media_kwh", "desvio_pct"]
    linhas = []
    for uc, grupo in df.sort_values("mes_ref").groupby("uc"):
        anteriores = grupo["consumo_kwh"].iloc[:-1].tail(MESES_DE_BASE)
        media = anteriores.mean()
        if len(anteriores) < MINIMO_DE_MESES or not media > 0:
            continue
        ultimo = grupo.iloc[-1]
        desvio = ultimo["consumo_kwh"] / media - 1
        if abs(desvio) > limiar:
            linhas.append({"uc": uc, "mes_ref": ultimo["mes_ref"], "consumo_kwh": float(ultimo["consumo_kwh"]),
                           "media_kwh": float(media), "desvio_pct": float(desvio * 100)})
    return pd.DataFrame(linhas, columns=colunas)
