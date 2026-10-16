"""Otimizador de rateio: compara como cada geradora distribui a energia entre as unidades
com o consumo real de cada uma e sugere os percentuais que deixam menos crédito parado e
menos consumo pago a tarifa cheia."""

from dataclasses import dataclass

import pandas as pd

from solar import config


@dataclass
class ResultadoRateio:
    tabela: pd.DataFrame
    producao_kwh_mes: float
    demanda_kwh_mes: float
    descoberto_atual_kwh: float     # consumo que não está coberto pelo rateio de hoje
    descoberto_sugerido_kwh: float
    ganho_mensal_rs: float          # valor mensal do consumo que passaria a ser coberto
    saldo_parado_kwh: float
    saldo_parado_rs: float


def sugerir_percentuais(
    demanda: dict[str, float], valor_kwh: dict[str, float], producao: float, sem_sobra: frozenset[str] = frozenset()
) -> dict[str, float]:
    """Percentual (soma 100, duas casas — como a Equatorial aceita) que cada unidade deve
    receber de cada geradora. Se sobra energia, reparte a sobra proporcional à demanda entre
    as unidades que podem recebê-la (fora de `sem_sobra`); se falta, cobre primeiro as
    unidades onde o kWh compensado vale mais."""
    demanda = {uc: d for uc, d in demanda.items() if d > 0}
    total = sum(demanda.values())
    if not demanda or producao <= 0:
        return {uc: 0.0 for uc in demanda}

    if producao >= total:
        sobra = producao - total
        favorecidas = {uc: d for uc, d in demanda.items() if uc not in sem_sobra} or demanda
        base_sobra = sum(favorecidas.values())
        alocado = {uc: d + (sobra * d / base_sobra if uc in favorecidas else 0.0) for uc, d in demanda.items()}
        reparte = producao
    else:
        alocado, restante = {}, producao
        for uc in sorted(demanda, key=lambda u: valor_kwh.get(u, 0.0), reverse=True):
            alocado[uc] = min(demanda[uc], restante)
            restante -= alocado[uc]
        reparte = producao

    pct = {uc: round(100 * a / reparte, 2) for uc, a in alocado.items()}
    maior = max(pct, key=pct.get)
    pct[maior] = round(pct[maior] + (100 - sum(pct.values())), 2)
    return pct


def _percentual_atual(ultimas: pd.DataFrame, geradoras: list[str]) -> dict[str, dict[str, float]]:
    """{uc receptora: {uc geradora: %}} lido do rateio impresso na última fatura de cada UC."""
    atual = {}
    for uc, linha in ultimas.iterrows():
        rateio = linha["rateio"] if isinstance(linha["rateio"], dict) else {}
        atual[uc] = {g: pct for g, pct in rateio.items() if g in geradoras}
    return atual


def analisar(
    df_economia: pd.DataFrame, nomes: dict[str, str], meses_base: int = 6, horizonte_saldo_meses: int = 12
) -> ResultadoRateio | None:
    """`horizonte_saldo_meses`: em quantos meses o crédito já acumulado numa unidade deve ser
    consumido — a unidade recebe menos energia nova e a sobra vai para quem está descoberto."""
    meses = sorted(df_economia["mes_ref"].unique())[-meses_base:]
    base = df_economia[df_economia["mes_ref"].isin(meses)]
    ultimas = df_economia.sort_values("mes_ref").groupby("uc").tail(1).set_index("uc")

    producao = base[base["geradora"]].groupby("uc")["injetado_kwh"].sum() / len(meses)
    producao = producao[producao > 0]
    if producao.empty:
        return None

    consumo = base.groupby("uc")["consumo_kwh"].sum() / len(meses)
    compensado = base.groupby("uc")["compensado_kwh"].sum()
    economia = base.groupby("uc")["economia_rs"].sum()
    medio = economia.sum() / compensado.sum() if compensado.sum() > 0 else 0.0
    valor_kwh = (economia / compensado.where(compensado > 0)).fillna(medio)

    demanda = (consumo - config.DISPONIBILIDADE_KWH).clip(lower=0)
    saldo = ultimas["saldo_creditos_kwh"].reindex(consumo.index).fillna(0.0)
    consumo_do_saldo = saldo / horizonte_saldo_meses
    atual = _percentual_atual(ultimas, list(producao.index))
    alocado_atual = pd.Series(
        {uc: sum(pct / 100 * producao[g] for g, pct in atual.get(uc, {}).items()) for uc in consumo.index}
    )
    demanda_alvo = (demanda - consumo_do_saldo).clip(lower=0)
    com_saldo = frozenset(saldo[saldo > 0.5].index)
    sugerido = sugerir_percentuais(demanda_alvo.to_dict(), valor_kwh.to_dict(), producao.sum(), com_saldo)
    alocado_sugerido = pd.Series({uc: sugerido.get(uc, 0.0) / 100 * producao.sum() for uc in consumo.index})

    def descoberto(alocado: pd.Series) -> pd.Series:
        falta = (demanda - alocado).clip(lower=0)
        return (falta - pd.concat([falta, consumo_do_saldo], axis=1).min(axis=1)).clip(lower=0)

    descoberto_atual = descoberto(alocado_atual)
    descoberto_sugerido = descoberto(alocado_sugerido)

    tabela = pd.DataFrame({
        "uc": consumo.index,
        "unidade": [nomes.get(uc, uc) for uc in consumo.index],
        "consumo_kwh": consumo.values,
        "demanda_kwh": demanda.values,
        "rateio_atual": [
            " + ".join(f"{nomes.get(g, g)} {pct:.2f}%" for g, pct in atual.get(uc, {}).items() if pct > 0) or "—"
            for uc in consumo.index
        ],
        "alocado_atual_kwh": alocado_atual.values,
        "sugerido_pct": [sugerido.get(uc, 0.0) for uc in consumo.index],
        "alocado_sugerido_kwh": alocado_sugerido.values,
        "descoberto_atual_kwh": descoberto_atual.values,
        "saldo_kwh": saldo.values,
        "meses_para_zerar_saldo": [
            saldo[uc] / (demanda[uc] - alocado_sugerido[uc]) if demanda[uc] - alocado_sugerido[uc] > 0.5 and saldo[uc] > 0 else None
            for uc in consumo.index
        ],
        "saldo_rs": (saldo * valor_kwh.reindex(consumo.index)).values,
    }).sort_values("consumo_kwh", ascending=False).reset_index(drop=True)

    ganho = float(((descoberto_atual - descoberto_sugerido) * valor_kwh.reindex(consumo.index)).sum())
    return ResultadoRateio(
        tabela=tabela,
        producao_kwh_mes=float(producao.sum()),
        demanda_kwh_mes=float(demanda.sum()),
        descoberto_atual_kwh=float(descoberto_atual.sum()),
        descoberto_sugerido_kwh=float(descoberto_sugerido.sum()),
        ganho_mensal_rs=ganho,
        saldo_parado_kwh=float(saldo.sum()),
        saldo_parado_rs=float(tabela["saldo_rs"].sum()),
    )
