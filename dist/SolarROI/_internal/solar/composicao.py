"""Para onde vai cada real da conta: da conta hipotética sem usina até a conta real, e a
composição do que foi efetivamente pago."""

from dataclasses import dataclass

import pandas as pd


@dataclass
class Composicao:
    sem_usina: float            # o que seria pago sem a usina
    energia_compensada: float   # valor da energia compensada pela tarifa cheia (abate)
    fio_b: float                # Fio B cobrado sobre a energia compensada (soma de volta)
    beneficio_scee: float       # benefício tarifário SCEE líquido (soma de volta)
    outros_ajustes: float       # diferença que fecha a conta (sem composição, arredondamentos)
    real: float                 # o que foi pago
    economia: float

    # composição do que foi pago
    energia_cobrada: float
    bandeira: float
    cip: float
    multa_juros: float
    outros: float

    @property
    def partes_da_conta(self) -> dict[str, float]:
        return {
            "Energia cobrada": self.energia_cobrada, "Fio B (GD2)": self.fio_b,
            "Benefício tarifário SCEE": self.beneficio_scee, "Bandeira": self.bandeira,
            "Iluminação pública (CIP)": self.cip, "Multa e juros": self.multa_juros, "Outros": self.outros,
        }


def _soma(df: pd.DataFrame, coluna: str) -> float:
    return float(df[coluna].fillna(0.0).sum())


def compor(df_economia: pd.DataFrame, meses: list[str] | None = None, uc: str | None = None) -> Composicao:
    df = df_economia
    if meses is not None:
        df = df[df["mes_ref"].isin(meses)]
    if uc is not None:
        df = df[df["uc"] == uc]

    real, economia = _soma(df, "total_rs"), _soma(df, "economia_rs")
    compensada, fio_b, beneficio = _soma(df, "valor_compensado_rs"), _soma(df, "fio_b_rs"), _soma(df, "beneficio_rs")
    sem_usina = real + economia
    return Composicao(
        sem_usina=sem_usina, energia_compensada=compensada, fio_b=fio_b, beneficio_scee=beneficio,
        outros_ajustes=real - (sem_usina - compensada + fio_b + beneficio), real=real, economia=economia,
        energia_cobrada=_soma(df, "consumo_rs"), bandeira=_soma(df, "bandeira_rs"), cip=_soma(df, "cip_rs"),
        multa_juros=_soma(df, "multa_rs") + _soma(df, "juros_rs"), outros=_soma(df, "outros_rs"),
    )
