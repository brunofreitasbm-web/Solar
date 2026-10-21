"""Comparação do retorno da usina com CDI/IPCA — resposta a "e se tivesse investido em renda fixa?"."""

from datetime import date

import pandas as pd
import requests

from solar.config import BCB_SERIE_CDI_MENSAL, BCB_SERIE_IPCA_MENSAL, BCB_SERIE_URL
from solar.db import gravar_cache, ler_cache

TIMEOUT_S = 30


class FalhaBenchmark(Exception):
    pass


def _serie_mensal(codigo_serie: int, data_inicial: str) -> pd.DataFrame:
    chave = f"bcb_serie_{codigo_serie}_{data_inicial}"
    cache = ler_cache(chave)
    if cache and cache[1][:10] == date.today().isoformat():
        return pd.DataFrame(cache[0])
    url = BCB_SERIE_URL.format(serie=codigo_serie)
    parametros = {"formato": "json", "dataInicial": data_inicial}
    try:
        resposta = requests.get(url, params=parametros, timeout=TIMEOUT_S)
        resposta.raise_for_status()
        dados = resposta.json()
    except (requests.RequestException, ValueError) as erro:
        if cache:
            return pd.DataFrame(cache[0])
        raise FalhaBenchmark("Não foi possível consultar o Banco Central agora.") from erro
    gravar_cache(chave, dados)
    return pd.DataFrame(dados)


def _data_inicial_br(data_investimento: str) -> str:
    d = date.fromisoformat(data_investimento)
    return d.strftime("%d/%m/%Y")


def retorno_acumulado(codigo_serie: int, data_investimento: str) -> pd.DataFrame:
    """Retorna, mês a mês desde `data_investimento`, o valor acumulado de R$1 investido
    na série do BCB (taxa mensal composta)."""
    df = _serie_mensal(codigo_serie, _data_inicial_br(data_investimento))
    df["valor"] = pd.to_numeric(df["valor"].str.replace(",", "."), errors="coerce") / 100
    df["fator"] = (1 + df["valor"]).cumprod()
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df["mes_ref"] = df["data"].dt.strftime("%Y-%m")
    return df[["mes_ref", "fator"]]


def comparar_com_investimento(
    investimento: float, data_investimento: str, economia_acumulada_rs: float
) -> dict:
    """Quanto o mesmo investimento teria virado no CDI e no IPCA, versus o que a usina
    já devolveu em economia — tudo até o mês mais recente disponível em cada série."""
    resultado = {"economia_acumulada_rs": economia_acumulada_rs}
    for nome, serie in (("cdi", BCB_SERIE_CDI_MENSAL), ("ipca", BCB_SERIE_IPCA_MENSAL)):
        try:
            fatores = retorno_acumulado(serie, data_investimento)
            fator_final = fatores["fator"].iloc[-1] if not fatores.empty else 1.0
        except FalhaBenchmark:
            fator_final = None
        resultado[f"{nome}_valor_final_rs"] = investimento * fator_final if fator_final else None
    return resultado


def cdi_anual_medio(meses: int = 12) -> float | None:
    """CDI dos últimos `meses` meses, composto e anualizado — referência do custo de
    oportunidade do dinheiro (ex.: quanto rende o valor que seria usado para amortizar)."""
    try:
        df = _serie_mensal(BCB_SERIE_CDI_MENSAL, _data_inicial_br(date(date.today().year - 2, 1, 1).isoformat()))
    except FalhaBenchmark:
        return None
    taxas = pd.to_numeric(df["valor"].str.replace(",", "."), errors="coerce").dropna().tail(meses) / 100
    return float((1 + taxas).prod() ** (12 / len(taxas)) - 1) if len(taxas) else None
