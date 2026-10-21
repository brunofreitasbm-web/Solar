"""Carrega e calcula uma vez os dados que várias páginas usam (faturas, economia, tarifa,
modelo de projeção) e guarda em cache até o banco mudar."""

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from solar import alertas, configuracoes, economia, geracao, projecao, unidades
from solar.config import CAMINHO_DB
from solar.configuracoes import Configuracoes
from solar.faturas import pendentes as fila, repositorio
from solar.projecao import ModeloEconomia
from solar.tarifa import aneel


@dataclass
class Painel:
    cfg: Configuracoes
    tarifa: aneel.TarifaVigente | None
    df: pd.DataFrame              # faturas como salvas
    df_economia: pd.DataFrame     # faturas + economia por fatura
    resumo: pd.DataFrame          # economia por mês, todas as unidades
    nomes: dict[str, str]
    coordenadas: list[tuple[float, float]]
    sazonal_nasa: dict[int, float] | None
    modelo: ModeloEconomia | None


@st.cache_data(show_spinner="Calculando a partir das suas faturas…", ttl=900)
def _calcular(versao_banco: int) -> Painel | None:
    df = repositorio.tabela()
    if df.empty:
        return None
    cfg = configuracoes.carregar()
    try:
        tarifa = aneel.tarifa_de_hoje()
    except aneel.FalhaTarifa:
        tarifa = None
    tusd = tarifa.tusd_kwh if tarifa else 0.0
    padrao = tarifa.com_tributos(cfg.icms, cfg.pis_cofins) if tarifa else 0.0

    df_economia = economia.tabela_economia(df, tusd, padrao)
    lista = unidades.listar()
    coordenadas = [(u.lat, u.lon) for u in lista if u.geradora and u.lat and u.lon]
    sazonal_nasa = geracao.fatores_sazonais_nasa(coordenadas) if coordenadas else None
    return Painel(
        cfg=cfg, tarifa=tarifa, df=df, df_economia=df_economia, resumo=economia.resumo_mensal(df_economia),
        nomes={u.uc: u.nome for u in lista}, coordenadas=coordenadas, sazonal_nasa=sazonal_nasa,
        modelo=projecao.calibrar(df_economia, prior_sazonal=sazonal_nasa),
    )


def carregar() -> Painel | None:
    """Os cálculos só se repetem quando o arquivo do banco muda."""
    return _calcular(CAMINHO_DB.stat().st_mtime_ns if CAMINHO_DB.exists() else 0)


def alertas_atuais(p: Painel | None) -> list[alertas.Alerta]:
    em_revisao = fila.contar()
    if p is None:
        return alertas.reunir(repositorio.tabela().iloc[0:0], {}, 0.0, em_revisao)
    return alertas.reunir(p.df, p.nomes, p.cfg.performance_ratio, em_revisao)
