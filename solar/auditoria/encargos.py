import pandas as pd

from solar.auditoria.achado import Achado, reais


def auditar(df: pd.DataFrame) -> list[Achado]:
    """Só a fatura mais recente de cada unidade: o histórico de atrasos já aparece em Vencimentos."""
    achados = []
    for _, f in df.sort_values("mes_ref").groupby("uc").tail(1).iterrows():
        multa, juros = pd.Series([f["multa_rs"], f["juros_rs"]]).fillna(0.0)
        if multa + juros <= 0:
            continue
        achados.append(Achado(
            f["uc"], f["mes_ref"], "aviso", "Multa ou juros na fatura",
            f"Esta fatura trouxe {reais(multa)} de multa e {reais(juros)} de juros e correção.",
            "Se o pagamento estava em dia, conteste; senão, ative o lembrete em Vencimentos.",
        ))
    return achados
