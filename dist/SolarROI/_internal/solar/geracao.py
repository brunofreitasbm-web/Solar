"""Alerta de baixa geração: compara a geração esperada pela irradiação solar da região
(NASA POWER) com a geração real (injetado_kwh das faturas) de cada usina."""

from datetime import date

import pandas as pd
import requests

from solar.config import LIMIAR_ALERTA_GERACAO, NASA_POWER_URL
from solar.db import gravar_cache, ler_cache

TIMEOUT_S = 30
PARAMETRO_IRRADIACAO = "ALLSKY_SFC_SW_DWN"  # kWh/m²/dia, média mensal


class FalhaGeracao(Exception):
    pass


def _irradiacao_mensal(lat: float, lon: float) -> dict[str, float]:
    """kWh/m²/dia por mês (climatologia 2001-2020), ponto mais próximo das coordenadas."""
    chave = f"nasa_power_{lat:.3f}_{lon:.3f}"
    cache = ler_cache(chave)
    if cache:
        return cache[0]
    parametros = {
        "parameters": PARAMETRO_IRRADIACAO, "community": "RE",
        "latitude": lat, "longitude": lon, "format": "JSON",
        "start": "2001", "end": "2020",
    }
    try:
        resposta = requests.get(NASA_POWER_URL, params=parametros, timeout=TIMEOUT_S)
        resposta.raise_for_status()
        dados = resposta.json()["properties"]["parameter"][PARAMETRO_IRRADIACAO]
    except (requests.RequestException, KeyError, ValueError) as erro:
        raise FalhaGeracao("Não foi possível consultar a NASA POWER agora.") from erro
    # A API devolve uma chave "AAAAMM" por ano-mês (2001-2020); -999 marca ausência de dado.
    # Faz a climatologia manualmente: média de cada mês (01-12) pelos 20 anos.
    por_mes: dict[str, list[float]] = {f"{m:02d}": [] for m in range(1, 13)}
    for chave_data, valor in dados.items():
        mes = chave_data[-2:]
        if mes in por_mes and valor >= 0:
            por_mes[mes].append(valor)
    mensal = {mes: sum(vs) / len(vs) for mes, vs in por_mes.items() if vs}
    gravar_cache(chave, mensal)
    return mensal


def geracao_esperada_kwh(lat: float, lon: float, kwp: float, mes_ref: str, performance_ratio: float) -> float | None:
    """Energia esperada no mês = irradiação do mês × kWp × performance ratio × dias do mês."""
    try:
        irradiacao = _irradiacao_mensal(lat, lon)
    except FalhaGeracao:
        return None
    mes = mes_ref[5:7]
    irradiacao_dia = irradiacao.get(mes)
    if irradiacao_dia is None or irradiacao_dia < 0:  # NASA usa -999 para "sem dado"
        return None
    dias_no_mes = pd.Period(mes_ref).days_in_month
    return irradiacao_dia * kwp * performance_ratio * dias_no_mes


def avaliar_geracao(df_faturas_geradoras: pd.DataFrame, performance_ratio: float) -> pd.DataFrame:
    """Para cada fatura de unidade geradora com lat/lon/kWp configurados, calcula a razão
    geração real / esperada e marca alerta quando abaixo do limiar."""
    linhas = []
    for _, linha in df_faturas_geradoras.iterrows():
        if pd.isna(linha.get("lat")) or pd.isna(linha.get("lon")) or not linha.get("kwp"):
            continue
        esperado = geracao_esperada_kwh(linha["lat"], linha["lon"], linha["kwp"], linha["mes_ref"], performance_ratio)
        if esperado is None or esperado <= 0:
            continue
        razao = linha["injetado_kwh"] / esperado
        linhas.append({
            "uc": linha["uc"], "mes_ref": linha["mes_ref"],
            "geracao_real_kwh": linha["injetado_kwh"], "geracao_esperada_kwh": esperado,
            "razao": razao, "alerta": razao < LIMIAR_ALERTA_GERACAO,
        })
    return pd.DataFrame(linhas)


def fatores_sazonais_nasa(coordenadas: list[tuple[float, float]]) -> dict[int, float] | None:
    """Fator de cada mês pela irradiação × dias (média 1), na média das usinas — serve de
    âncora para a sazonalidade medida, que com poucos meses de histórico é ruidosa."""
    acumulado = {m: 0.0 for m in range(1, 13)}
    for lat, lon in coordenadas:
        try:
            irradiacao = _irradiacao_mensal(lat, lon)
        except FalhaGeracao:
            return None
        for mes in range(1, 13):
            dias = pd.Period(f"2025-{mes:02d}").days_in_month
            acumulado[mes] += irradiacao.get(f"{mes:02d}", 0.0) * dias
    media = sum(acumulado.values()) / 12
    return {m: v / media for m, v in acumulado.items()} if media > 0 else None


def rendimento_kwh_kwp_mes(coordenadas: list[tuple[float, float]], performance_ratio: float) -> float | None:
    """Energia média que 1 kWp gera por mês (irradiação × dias × performance ratio),
    na média das coordenadas informadas."""
    totais = []
    for lat, lon in coordenadas:
        try:
            irradiacao = _irradiacao_mensal(lat, lon)
        except FalhaGeracao:
            return None
        anual = sum(irradiacao.get(f"{m:02d}", 0.0) * pd.Period(f"2025-{m:02d}").days_in_month for m in range(1, 13))
        totais.append(anual * performance_ratio / 12)
    return sum(totais) / len(totais) if totais else None
