"""Economia mensal por unidade consumidora.

Economia = o que a energia compensada custaria pela tarifa cheia (sem usina) menos o que a
fatura ainda cobra por causa da compensação (Fio B e benefício tarifário SCEE). CIP, multa,
bandeira e custo de disponibilidade existem com ou sem usina, então não entram na conta.
"""

import pandas as pd

from solar import config


def percentual_fio_b_ano(ano: int) -> float:
    """Lei 14.300/2022, regra de transição (GD II): 15% em 2023 até 90% em 2028, 100% depois."""
    if ano > 2028:
        return config.FIO_B_APOS_2028
    return config.FIO_B_PERCENTUAL_POR_ANO.get(ano, 0.0)


def percentual_fio_b(mes_ref: str, data_pedido_conexao: str | None) -> float:
    """Usinas com pedido de conexão ANTES de 07/01/2023 ficam isentas do Fio B até 2045."""
    if not data_pedido_conexao or data_pedido_conexao < config.DATA_CORTE_LEI_14300:
        return 0.0
    return percentual_fio_b_ano(int(mes_ref[:4]))


def _tarifa_efetiva(df: pd.DataFrame, padrao: float) -> pd.Series:
    """R$/kWh (com tributos) da energia que teria sido cobrada sem compensação. Vem da linha
    de consumo da própria fatura; quando ela não existe (tudo compensado), usa a mediana das
    outras unidades no mesmo mês, depois a mais próxima da própria unidade, depois a ANEEL."""
    mediana_mes = df.groupby("mes_ref")["tarifa_kwh"].transform("median")
    da_unidade = df.groupby("uc")["tarifa_kwh"].transform(lambda s: s.ffill().bfill())
    efetiva = df["tarifa_kwh"].fillna(mediana_mes).fillna(da_unidade)
    return efetiva.fillna(padrao if padrao else float("nan"))


def economia_da_fatura(linha: pd.Series, tarifa_tusd_kwh: float) -> float:
    compensado_kwh = linha["compensado_kwh"] or 0.0
    if compensado_kwh <= 0:
        return 0.0

    if pd.notna(linha["fio_b_rs"]) or pd.notna(linha["beneficio_rs"]):
        remanescente = (0.0 if pd.isna(linha["fio_b_rs"]) else linha["fio_b_rs"]) + (
            0.0 if pd.isna(linha["beneficio_rs"]) else linha["beneficio_rs"]
        )
    else:  # fatura sem a composição (ex.: lida pela IA): estima o Fio B pela regra da lei
        percentual = percentual_fio_b(linha["mes_ref"], linha["data_pedido_conexao"])
        remanescente = compensado_kwh * tarifa_tusd_kwh * percentual

    return max(linha["valor_compensado_rs"] - remanescente, 0.0)


def tabela_economia(df_faturas: pd.DataFrame, tarifa_tusd_kwh: float, tarifa_padrao_kwh: float = 0.0) -> pd.DataFrame:
    df = df_faturas.sort_values(["uc", "mes_ref"]).copy()
    for coluna in ("fio_b_rs", "beneficio_rs", "data_pedido_conexao"):
        if coluna not in df:
            df[coluna] = None
    df["tarifa_ef"] = _tarifa_efetiva(df, tarifa_padrao_kwh)
    df["valor_compensado_rs"] = df["compensado_kwh"] * df["tarifa_ef"]
    df["economia_rs"] = df.apply(lambda l: economia_da_fatura(l, tarifa_tusd_kwh), axis=1)
    return df.sort_values(["mes_ref", "uc"]).reset_index(drop=True)


def resumo_mensal(df_economia: pd.DataFrame) -> pd.DataFrame:
    return (
        df_economia.groupby("mes_ref", as_index=False)
        .agg(economia_rs=("economia_rs", "sum"), consumo_kwh=("consumo_kwh", "sum"), total_rs=("total_rs", "sum"))
        .sort_values("mes_ref")
    )
