"""Economia mensal por unidade consumidora e valorização de créditos pela tarifa vigente."""


import pandas as pd

from solar import config


def percentual_fio_b(mes_ref: str, data_pedido_conexao: str | None) -> float:
    """Lei 14.300/2022: usinas com pedido de conexão ANTES de 07/01/2023 ficam isentas
    do Fio B sobre a energia compensada até 2045. As demais pagam um percentual crescente
    do Fio B ano a ano, de 2023 (15%) a 2028 (90%); de 2029 em diante, 100%."""
    if not data_pedido_conexao or data_pedido_conexao < config.DATA_CORTE_LEI_14300:
        return 0.0
    ano = int(mes_ref[:4])
    return config.FIO_B_PERCENTUAL_POR_ANO.get(ano, config.FIO_B_APOS_2028)


def economia_da_fatura(linha: pd.Series, tarifa_tusd_kwh: float, tarifa_padrao_kwh: float = 0.0) -> float:
    """Economia do mês = valor da energia compensada (direto da fatura, se houver, senão
    kWh compensado × tarifa cheia) − Fio B incidente sobre essa energia (Lei 14.300)."""
    compensado_kwh = linha["compensado_kwh"] or 0.0
    if compensado_kwh <= 0:
        return 0.0

    tarifa_cheia = linha["tarifa_kwh"] or tarifa_padrao_kwh
    valor_compensado = linha["credito_rs"] if pd.notna(linha["credito_rs"]) else compensado_kwh * tarifa_cheia

    percentual = percentual_fio_b(linha["mes_ref"], linha["data_pedido_conexao"])
    fio_b = compensado_kwh * tarifa_tusd_kwh * percentual

    return max(valor_compensado - fio_b, 0.0)


def tabela_economia(df_faturas: pd.DataFrame, tarifa_tusd_kwh: float, tarifa_padrao_kwh: float = 0.0) -> pd.DataFrame:
    df = df_faturas.copy()
    df["economia_rs"] = df.apply(lambda l: economia_da_fatura(l, tarifa_tusd_kwh, tarifa_padrao_kwh), axis=1)
    return df


def resumo_mensal(df_economia: pd.DataFrame) -> pd.DataFrame:
    return (
        df_economia.groupby("mes_ref", as_index=False)
        .agg(economia_rs=("economia_rs", "sum"), consumo_kwh=("consumo_kwh", "sum"), total_rs=("total_rs", "sum"))
        .sort_values("mes_ref")
    )
