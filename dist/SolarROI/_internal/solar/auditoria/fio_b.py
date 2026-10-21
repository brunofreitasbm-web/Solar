"""Fio B por kWh compensado, já dividido pelo percentual da Lei 14.300 do ano, deve ficar estável
mês a mês (muda só nos reajustes). Um salto sinaliza erro de cálculo ou de enquadramento."""

import pandas as pd

from solar import config
from solar.auditoria import config as cfg
from solar.auditoria.achado import Achado, reais


def _percentual_do_ano(mes_ref: str) -> float:
    ano = int(mes_ref[:4])
    return config.FIO_B_PERCENTUAL_POR_ANO.get(ano, config.FIO_B_APOS_2028 if ano > 2028 else 0.0)


def _fio_b_cheio_por_kwh(f) -> float | None:
    percentual = _percentual_do_ano(f["mes_ref"])
    if not f["fio_b_rs"] or not f["compensado_kwh"] or not percentual:
        return None
    return f["fio_b_rs"] / f["compensado_kwh"] / percentual


def auditar(df: pd.DataFrame) -> list[Achado]:
    achados = []
    for uc, g in df[~df["geradora"]].sort_values("mes_ref").groupby("uc"):
        g = g.assign(valor=g.apply(_fio_b_cheio_por_kwh, axis=1)).dropna(subset=["valor"])
        for i in range(len(g)):
            base = g["valor"].iloc[max(0, i - cfg.MESES_BASE_FIO_B):i]
            if len(base) < cfg.MINIMO_MESES_FIO_B:
                continue
            f, mediana = g.iloc[i], base.median()
            desvio = f["valor"] / mediana - 1
            if abs(desvio) <= cfg.TOLERANCIA_FIO_B:
                continue
            achados.append(Achado(
                uc, f["mes_ref"], "aviso", "Fio B fora do padrão",
                f"O Fio B cobrado por kWh compensado ficou {desvio * 100:+.0f}% em relação à mediana dos "
                f"{len(base)} meses anteriores ({reais(f['fio_b_rs'])} sobre {f['compensado_kwh']:.0f} kWh).",
                "Confira o percentual do Fio B aplicado (Lei 14.300) e a data de conexão das geradoras.",
            ))
    return achados
