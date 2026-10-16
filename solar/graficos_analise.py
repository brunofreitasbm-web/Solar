"""Gráficos das análises (composição da conta, rateio, sazonalidade, simuladores). Mesma
paleta e formatação de `graficos.py`."""

import pandas as pd
import plotly.graph_objects as go

from solar.composicao import Composicao
from solar.expansao import Demanda
from solar.graficos import (
    COR_ECONOMIA, COR_GRADE, COR_INVESTIMENTO, COR_PARCELA, COR_TEXTO_MUTED, eixo_x_categoria, eixo_y_moeda,
    layout_base, mes_legivel, rs,
)

COR_CUSTO_DA_COMPENSACAO = "#D97706"   # laranja — custos que nascem da compensação (Fio B, benefício)
COR_CUSTO_FIXO = "#64748B"             # cinza — CIP, multa, bandeira: existem com ou sem usina
MESES_ABREV = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def grafico_cascata(c: Composicao) -> go.Figure:
    """Da conta que existiria sem a usina até a conta real: o que a compensação abate e o
    que ela traz de volta (Fio B e benefício tarifário)."""
    passos = [
        ("Conta sem a usina", c.sem_usina, "absolute"),
        ("Energia compensada (abate)", -c.energia_compensada, "relative"),
        ("Fio B (GD2)", c.fio_b, "relative"),
        ("Benefício tarifário SCEE", c.beneficio_scee, "relative"),
        ("Outros ajustes", c.outros_ajustes, "relative"),
        ("Conta real", c.real, "total"),
    ]
    passos = [p for p in passos if abs(p[1]) >= 0.5 or p[2] != "relative"]
    fig = go.Figure(go.Waterfall(
        x=[p[0] for p in passos], y=[p[1] for p in passos], measure=[p[2] for p in passos],
        text=[rs(p[1]) for p in passos], textposition="outside",
        increasing=dict(marker=dict(color=COR_PARCELA)), decreasing=dict(marker=dict(color=COR_ECONOMIA)),
        totals=dict(marker=dict(color=COR_INVESTIMENTO)), connector=dict(line=dict(color=COR_GRADE)),
        hovertemplate="%{x}<br>%{text}<extra></extra>",
    ))
    fig.update_layout(**layout_base(
        "Da conta sem usina até a conta real",
        f"a compensação abate {rs(c.energia_compensada)} mas traz {rs(c.fio_b + c.beneficio_scee)} de volta — economia líquida de {rs(c.economia)}",
    ))
    fig.update_layout(showlegend=False)
    fig.update_yaxes(**eixo_y_moeda())
    fig.update_xaxes(showgrid=False, tickangle=0)
    return fig


def grafico_composicao(c: Composicao) -> go.Figure:
    """Composição da conta real. Laranja = custos da compensação; cinza = custos que
    existiriam sem usina."""
    cores = {
        "Energia cobrada": COR_INVESTIMENTO, "Fio B (GD2)": COR_CUSTO_DA_COMPENSACAO,
        "Benefício tarifário SCEE": COR_CUSTO_DA_COMPENSACAO, "Bandeira": COR_CUSTO_FIXO,
        "Iluminação pública (CIP)": COR_CUSTO_FIXO, "Multa e juros": COR_PARCELA, "Outros": COR_GRADE,
    }
    partes = {k: v for k, v in c.partes_da_conta.items() if abs(v) >= 0.5}
    nomes = list(partes)[::-1]
    fig = go.Figure(go.Bar(
        x=[partes[n] for n in nomes], y=nomes, orientation="h", marker_color=[cores[n] for n in nomes],
        text=[f"{rs(partes[n])} · {100 * partes[n] / c.real:.0f}%" for n in nomes], textposition="outside",
        hovertemplate="%{y}<br>%{text}<extra></extra>",
    ))
    fig.update_layout(**layout_base("O que compõe a conta que você paga", f"total pago: {rs(c.real)}"))
    fig.update_layout(showlegend=False, margin=dict(l=10, r=10, t=60, b=10))
    fig.update_xaxes(gridcolor=COR_GRADE, tickprefix="R$ ", separatethousands=True, range=[min(0, min(partes.values())), max(partes.values()) * 1.5])
    fig.update_yaxes(showgrid=False)
    return fig


def grafico_projecoes(cenarios: list[tuple[str, pd.DataFrame, str, str]], investimento: float) -> go.Figure:
    """Várias projeções de ROI acumulado no mesmo eixo: (nome, tabela, cor, traço)."""
    fig = go.Figure()
    for nome, df, cor, traco in cenarios:
        fig.add_scatter(
            x=df["ano"], y=df["roi_acumulado_pct"], mode="lines", name=nome, line=dict(color=cor, width=2.5, dash=traco),
            hovertemplate=f"{nome}<br>ano %{{x}}: %{{y:.0f}}%<extra></extra>",
        )
        positivo = df[df["roi_acumulado_pct"] >= 0]
        if not positivo.empty:
            ano0 = int(positivo.iloc[0]["ano"])
            fig.add_scatter(x=[ano0], y=[0], mode="markers+text", marker=dict(size=9, color=cor), showlegend=False,
                            text=[f"ano {ano0}"], textposition="top center", textfont=dict(size=11, color=cor),
                            hoverinfo="skip")
    fig.add_hline(y=0, line_dash="dot", line_color=COR_TEXTO_MUTED, line_width=1)
    fig.update_layout(**layout_base(
        "Projeção de 25 anos", f"ROI acumulado sobre {rs(investimento)}, contando de quando a usina começou (marcador = ano do payback)"))
    fig.update_yaxes(title="ROI acumulado", ticksuffix="%", gridcolor=COR_GRADE, zeroline=False)
    fig.update_xaxes(title="Ano de vida da usina", showgrid=False, dtick=5)
    return fig


def grafico_sazonalidade(medida: dict[int, float], nasa: dict[int, float] | None) -> go.Figure:
    fig = go.Figure()
    fig.add_bar(x=MESES_ABREV, y=[medida[m] for m in range(1, 13)], name="Usada na projeção (medida + NASA)",
                marker_color=COR_ECONOMIA, hovertemplate="%{x}: %{y:.2f}×<extra></extra>")
    if nasa:
        fig.add_scatter(x=MESES_ABREV, y=[nasa[m] for m in range(1, 13)], mode="lines+markers", name="Irradiação NASA (clima de 20 anos)",
                        line=dict(color=COR_INVESTIMENTO, width=2, dash="dot"), hovertemplate="%{x}: %{y:.2f}×<extra></extra>")
    fig.add_hline(y=1, line_color=COR_TEXTO_MUTED, line_width=1, annotation_text="média do ano",
                  annotation_position="top left", annotation_font=dict(size=11, color=COR_TEXTO_MUTED))
    fig.update_layout(**layout_base("Sazonalidade da geração", "quanto cada mês gera em relação à média do ano"))
    fig.update_yaxes(gridcolor=COR_GRADE, tickformat=".2f", ticksuffix="×", range=[0.6, 1.4])
    fig.update_xaxes(**eixo_x_categoria())
    return fig


def grafico_rateio(tabela: pd.DataFrame) -> go.Figure:
    """Consumo que pode ser compensado × energia que cada unidade recebe hoje × sugerida."""
    t = tabela[tabela["demanda_kwh"] + tabela["alocado_atual_kwh"] + tabela["alocado_sugerido_kwh"] > 0]
    fig = go.Figure()
    fig.add_bar(x=t["unidade"], y=t["demanda_kwh"], name="Consumo compensável", marker_color=COR_GRADE,
                hovertemplate="%{x}<br>consumo: %{y:,.0f} kWh<extra></extra>")
    fig.add_bar(x=t["unidade"], y=t["alocado_atual_kwh"], name="Recebe hoje", marker_color=COR_PARCELA,
                hovertemplate="%{x}<br>recebe hoje: %{y:,.0f} kWh<extra></extra>")
    fig.add_bar(x=t["unidade"], y=t["alocado_sugerido_kwh"], name="Recebe com o rateio sugerido", marker_color=COR_ECONOMIA,
                hovertemplate="%{x}<br>sugerido: %{y:,.0f} kWh<extra></extra>")
    fig.update_layout(**layout_base("Quanto cada unidade consome e quanto recebe (kWh/mês)",
                                      "barra vermelha acima da cinza = crédito sobrando; abaixo = consumo pago a tarifa cheia"))
    fig.update_layout(barmode="group", bargap=0.25)
    fig.update_yaxes(gridcolor=COR_GRADE, ticksuffix=" kWh", separatethousands=True)
    fig.update_xaxes(**eixo_x_categoria())
    return fig


def grafico_demanda_vs_geracao(d: Demanda, degradacao_anual: float, anos: int = 8) -> go.Figure:
    meses = list(range(0, anos * 12 + 1, 3))
    producao = [d.producao_kwh_mes * (1 - degradacao_anual) ** (k / 12) for k in meses]
    demanda = [d.demanda_kwh_mes + d.crescimento_kwh_mes_por_ano * k / 12 for k in meses]
    fig = go.Figure()
    fig.add_scatter(x=[k / 12 for k in meses], y=producao, mode="lines", name="Geração (com degradação)",
                    line=dict(color=COR_ECONOMIA, width=2.5), hovertemplate="em %{x:.1f} anos: %{y:,.0f} kWh/mês<extra></extra>")
    fig.add_scatter(x=[k / 12 for k in meses], y=demanda, mode="lines", name="Demanda compensável (tendência)",
                    line=dict(color=COR_PARCELA, width=2.5, dash="dash"), hovertemplate="em %{x:.1f} anos: %{y:,.0f} kWh/mês<extra></extra>")
    if d.meses_ate_faltar is not None:
        fig.add_vline(x=d.meses_ate_faltar / 12, line_dash="dot", line_color=COR_TEXTO_MUTED,
                      annotation_text="a demanda passa a geração", annotation_position="top left",
                      annotation_font=dict(size=11, color=COR_TEXTO_MUTED))
    fig.update_layout(**layout_base("Geração × demanda nos próximos anos", "enquanto a linha verde estiver acima da vermelha, ampliar não gera economia"))
    fig.update_yaxes(gridcolor=COR_GRADE, ticksuffix=" kWh", separatethousands=True)
    fig.update_xaxes(title="Anos a partir de hoje", showgrid=False)
    return fig


def grafico_quitacao(cenarios: pd.DataFrame, cdi_rs: pd.Series | None = None) -> go.Figure:
    """Para cada valor amortizado: juros que deixam de ser pagos × rendimento do mesmo
    dinheiro aplicado no CDI até o fim do contrato."""
    fig = go.Figure()
    fig.add_bar(x=cenarios["rotulo"], y=cenarios["juros_economizados"], name="Juros economizados ao amortizar",
                marker_color=COR_ECONOMIA, text=[rs(v) for v in cenarios["juros_economizados"]], textposition="outside",
                hovertemplate="%{x}<br>%{text}<extra></extra>")
    if cdi_rs is not None:
        fig.add_bar(x=cenarios["rotulo"], y=cdi_rs, name="Rendimento no CDI (bruto)", marker_color=COR_INVESTIMENTO,
                    text=[rs(v) for v in cdi_rs], textposition="outside", hovertemplate="%{x}<br>%{text}<extra></extra>")
    fig.update_layout(**layout_base("Vale mais amortizar ou aplicar?", "mesmo dinheiro, mesmo período: juros do financiamento × rendimento no CDI"))
    fig.update_layout(barmode="group", bargap=0.25)
    fig.update_yaxes(**eixo_y_moeda())
    fig.update_xaxes(**eixo_x_categoria())
    return fig


def mes_legivel_ou_traco(mes: str | None) -> str:
    return mes_legivel(mes) if mes else "—"
