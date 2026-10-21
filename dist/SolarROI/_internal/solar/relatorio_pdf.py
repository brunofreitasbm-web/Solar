"""Relatório mensal em PDF: o resumo de uma página para guardar ou mandar a quem acompanha as contas."""

from io import BytesIO

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from solar.alertas import Alerta
from solar.graficos import mes_legivel, num, rs


def _tabela(cabecalho: list[str], linhas: list[list[str]]) -> Table:
    t = Table([cabecalho, *linhas], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E40AF")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9), ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
    ]))
    return t


def _por_unidade(d: pd.DataFrame, nomes: dict[str, str]) -> Table:
    linhas = [[nomes.get(l.uc, l.uc), num(l.consumo_kwh), num(l.compensado_kwh), num(l.total_rs, 2), num(l.economia_rs, 2),
               num(l.saldo_creditos_kwh)] for l in d.sort_values("total_rs", ascending=False).itertuples()]
    return _tabela(["Unidade", "Consumo (kWh)", "Compensado (kWh)", "Total (R$)", "Economia (R$)", "Saldo (kWh)"], linhas)


def _a_pagar(a_pagar: pd.DataFrame) -> Table:
    linhas = [[l.unidade, mes_legivel(l.mes_ref), l.vencimento.strftime("%d/%m/%Y"), num(l.total_rs, 2)] for l in a_pagar.itertuples()]
    return _tabela(["Unidade", "Fatura", "Vencimento", "Valor (R$)"], linhas)


def gerar(df_economia: pd.DataFrame, nomes: dict[str, str], mes: str, alertas: list[Alerta], a_pagar: pd.DataFrame) -> bytes:
    """`df_economia` precisa ter a coluna `economia_rs`; `mes` é AAAA-MM."""
    d = df_economia[df_economia["mes_ref"] == mes]
    estilos = getSampleStyleSheet()
    normal = estilos["Normal"]
    saida = BytesIO()
    doc = SimpleDocTemplate(saida, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
                            title=f"Relatório solar {mes}")
    historia = [Paragraph(f"Relatório solar — {mes_legivel(mes)}", estilos["Title"])]

    if d.empty:
        historia.append(Paragraph("Nenhuma fatura carregada para este mês.", normal))
    else:
        historia += [
            Paragraph(f"Economia do mês: <b>{rs(d['economia_rs'].sum(), 2)}</b> · Total das faturas: <b>{rs(d['total_rs'].sum(), 2)}</b> · "
                      f"Energia compensada: <b>{num(d['compensado_kwh'].sum())} kWh</b> · Energia injetada: <b>{num(d['injetado_kwh'].sum())} kWh</b>",
                      normal),
            Spacer(1, 0.5 * cm), Paragraph("Por unidade", estilos["Heading2"]), _por_unidade(d, nomes),
        ]

    historia += [Spacer(1, 0.5 * cm), Paragraph("Faturas a pagar", estilos["Heading2"])]
    historia.append(Paragraph("Todas as faturas carregadas estão pagas.", normal) if a_pagar.empty else _a_pagar(a_pagar))

    historia += [Spacer(1, 0.5 * cm), Paragraph("Alertas", estilos["Heading2"])]
    historia += [Paragraph(f"• {a.texto}", normal) for a in alertas] or [Paragraph("Nenhum alerta no momento.", normal)]
    doc.build(historia)
    return saida.getvalue()
