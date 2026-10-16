from datetime import date


def somar_meses(d: date, meses: int) -> date:
    """Soma meses mantendo o dia, ou o último dia do mês quando ele não existe (31 → 30/28)."""
    total = d.year * 12 + d.month - 1 + meses
    ano, mes0 = divmod(total, 12)
    mes = mes0 + 1
    primeiro_do_proximo = date(ano + (mes == 12), mes % 12 + 1, 1)
    ultimo_dia = (primeiro_do_proximo - date(ano, mes, 1)).days
    return date(ano, mes, min(d.day, ultimo_dia))


def mes_ref(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"
