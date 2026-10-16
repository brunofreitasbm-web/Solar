"""Previsão de vencimentos, calendário (.ics) para lembretes e custo dos atrasos pagos."""

from datetime import date, datetime, timedelta, timezone

import pandas as pd

from solar.datas import mes_ref, somar_meses

PRAZO_PADRAO_DIAS = 7  # emissão → vencimento quando não há fatura anterior para medir
DIAS_PARA_CONSIDERAR_FATURA_ATRASADA = 5


def _data(iso: str | None) -> date | None:
    return date.fromisoformat(iso) if isinstance(iso, str) and iso else None


def proximos_vencimentos(df: pd.DataFrame, nomes: dict[str, str], hoje: date | None = None) -> pd.DataFrame:
    """Prevê o próximo vencimento de cada unidade pela leitura seguinte e pelo prazo
    emissão→vencimento da última fatura. `aguardando_fatura` indica que a fatura do ciclo
    já deveria ter saído e ainda não foi carregada."""
    hoje = hoje or date.today()
    linhas = []
    for uc, grupo in df.sort_values("mes_ref").groupby("uc"):
        ultima = grupo.iloc[-1]
        vencimento, emissao, proxima_leitura = _data(ultima["vencimento"]), _data(ultima["emissao"]), _data(ultima["proxima_leitura"])
        if vencimento is None:
            continue
        prazo = (vencimento - emissao).days if emissao else PRAZO_PADRAO_DIAS
        if proxima_leitura:
            emissao_prevista = proxima_leitura + timedelta(days=1)
            previsto = emissao_prevista + timedelta(days=prazo)
        else:
            emissao_prevista, previsto = None, somar_meses(vencimento, 1)

        aguardando = bool(emissao_prevista and emissao_prevista + timedelta(days=DIAS_PARA_CONSIDERAR_FATURA_ATRASADA) <= hoje)
        while previsto + timedelta(days=30) < hoje:  # histórico antigo: rola para o ciclo atual
            previsto = somar_meses(previsto, 1)
        linhas.append({
            "uc": uc, "unidade": nomes.get(uc, uc), "ultima_fatura": ultima["mes_ref"],
            "ultimo_vencimento": vencimento, "vencimento_previsto": previsto,
            "dias": (previsto - hoje).days, "aguardando_fatura": aguardando,
        })
    return pd.DataFrame(linhas).sort_values("vencimento_previsto").reset_index(drop=True)


def gerar_ics(previsoes: pd.DataFrame, meses: int = 6, agora: datetime | None = None) -> str:
    """Calendário para importar no Google Agenda/Outlook, com lembrete 3 dias e 1 dia antes."""
    agora = agora or datetime.now(timezone.utc)
    carimbo = agora.strftime("%Y%m%dT%H%M%SZ")
    linhas = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Solar ROI//Vencimentos//PT-BR", "CALSCALE:GREGORIAN"]
    for _, p in previsoes.iterrows():
        for k in range(meses):
            data = somar_meses(p["vencimento_previsto"], k)
            linhas += [
                "BEGIN:VEVENT",
                f"UID:{p['uc']}-{mes_ref(data)}@solar-roi",
                f"DTSTAMP:{carimbo}",
                f"DTSTART;VALUE=DATE:{data:%Y%m%d}",
                f"SUMMARY:Vence fatura de energia - {p['unidade']}",
                "DESCRIPTION:Data prevista pelo ciclo de leitura da última fatura. Confira o valor e "
                "a data no site ou app da Equatorial. Débito automático evita multa e juros.",
                "BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Fatura vence em 3 dias", "TRIGGER:-P3D", "END:VALARM",
                "BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Fatura vence amanhã", "TRIGGER:-P1D", "END:VALARM",
                "END:VEVENT",
            ]
    linhas.append("END:VCALENDAR")
    return "\r\n".join(linhas) + "\r\n"


def encargos_por_atraso(df: pd.DataFrame, nomes: dict[str, str]) -> pd.DataFrame:
    """Multa, juros e correção cobrados nas faturas — sinal de pagamento após o vencimento."""
    d = df.copy()
    d["multa_rs"] = d["multa_rs"].fillna(0.0)
    d["juros_rs"] = d["juros_rs"].fillna(0.0)
    d["com_encargo"] = (d["multa_rs"] + d["juros_rs"]) > 0
    tabela = d.groupby("uc").agg(
        faturas=("mes_ref", "count"), com_encargo=("com_encargo", "sum"),
        multa_rs=("multa_rs", "sum"), juros_rs=("juros_rs", "sum"),
    ).reset_index()
    tabela["unidade"] = tabela["uc"].map(lambda uc: nomes.get(uc, uc))
    tabela["encargos_rs"] = tabela["multa_rs"] + tabela["juros_rs"]
    tabela["pct_faturas"] = 100 * tabela["com_encargo"] / tabela["faturas"]
    return tabela.sort_values("encargos_rs", ascending=False).reset_index(drop=True)
