"""Paleta, formatação e templates compartilhados dos gráficos do dashboard — moeda em
pt-BR, cores semânticas (verde = economia/positivo, vermelho = parcela/déficit, azul =
referência/investimento) e anotações de contexto em vez de só traçar a linha."""

import pandas as pd
import plotly.graph_objects as go

COR_ECONOMIA = "#15803D"     # verde — dinheiro que entrou
COR_PARCELA = "#DC2626"      # vermelho — dinheiro que saiu (financiamento)
COR_INVESTIMENTO = "#1E40AF"  # azul — referência/meta
COR_SALDO_POSITIVO = "#15803D"
COR_SALDO_NEGATIVO = "#DC2626"
COR_GRADE = "#E2E8F0"
COR_TEXTO_MUTED = "#64748B"

FONTE = dict(family="Inter, -apple-system, sans-serif", size=13, color="#1E293B")

MESES_PT = {1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
            7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez"}


def mes_legivel(mes_ref: str) -> str:
    """'2026-09' -> 'set/26'"""
    ano, mes = mes_ref.split("-")
    return f"{MESES_PT[int(mes)]}/{ano[2:]}"


def rs(valor: float, casas: int = 0) -> str:
    """Formata em R$ no padrão pt-BR: milhar com ponto, decimal com vírgula."""
    texto = f"{valor:,.{casas}f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return f"R$ {texto}"


def rs_md(valor: float, casas: int = 0) -> str:
    """Igual a `rs`, mas com o cifrão escapado — use dentro de st.info/warning/success/
    markdown, onde um "$" sem escape dispara interpretação de LaTeX e come o texto entre
    dois cifrões."""
    return rs(valor, casas).replace("R$", r"R\$")


def layout_base(titulo: str, subtitulo: str = "") -> dict:
    titulo_html = f"<b>{titulo}</b>"
    if subtitulo:
        titulo_html += f"<br><span style='font-size:12px;color:{COR_TEXTO_MUTED}'>{subtitulo}</span>"
    return dict(
        title=dict(text=titulo_html, font=dict(size=16, family=FONTE["family"], color="#0F172A")),
        font=FONTE,
        plot_bgcolor="white",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=60, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    font=dict(size=12)),
        hoverlabel=dict(bgcolor="white", font_size=13, bordercolor=COR_GRADE),
        separators=",.",  # formatação pt-BR: vírgula decimal, ponto de milhar
    )


def eixo_y_moeda(titulo: str = "") -> dict:
    return dict(title=titulo, gridcolor=COR_GRADE, tickprefix="R$ ", tickformat=",.0f",
                zeroline=True, zerolinecolor=COR_GRADE, separatethousands=True)


def eixo_x_categoria() -> dict:
    return dict(showgrid=False)


def grafico_economia_mensal(resumo: pd.DataFrame) -> go.Figure:
    """Barras verdes com rótulo de valor direto (bom para até ~30 meses) e uma linha
    tracejada da média, para o olho comparar cada mês sem precisar calcular de cabeça."""
    media = resumo["economia_rs"].mean()
    meses = [mes_legivel(m) for m in resumo["mes_ref"]]

    fig = go.Figure()
    fig.add_bar(
        x=meses, y=resumo["economia_rs"], marker_color=COR_ECONOMIA, name="Economia do mês",
        text=[rs(v) for v in resumo["economia_rs"]], textposition="outside",
        textfont=dict(size=10, color=COR_TEXTO_MUTED),
        hovertemplate="%{x}<br>Economia: %{text}<extra></extra>",
    )
    fig.add_hline(
        y=media, line_dash="dash", line_color=COR_TEXTO_MUTED, line_width=1,
        annotation_text=f"média {rs(media)}/mês", annotation_position="top left",
        annotation_font=dict(size=11, color=COR_TEXTO_MUTED),
    )
    fig.update_layout(**layout_base("Economia mensal", "quanto a compensação de energia valeu em R$ a cada mês"))
    fig.update_yaxes(**eixo_y_moeda())
    fig.update_xaxes(**eixo_x_categoria())
    return fig


def grafico_saldo_acumulado(acumulado: pd.DataFrame, payback: str | None) -> go.Figure:
    """Área que cresce com a economia acumulada; linha zero marca o ponto em que a usina
    "se pagou" — e anota o mês exato se o payback já ocorreu."""
    meses = [mes_legivel(m) for m in acumulado["mes_ref"]]
    cores_pontos = [COR_SALDO_POSITIVO if v >= 0 else COR_SALDO_NEGATIVO for v in acumulado["saldo_rs"]]

    fig = go.Figure()
    fig.add_scatter(
        x=meses, y=acumulado["saldo_rs"], mode="lines+markers", line=dict(color=COR_INVESTIMENTO, width=2),
        marker=dict(size=5, color=cores_pontos), fill="tozeroy",
        fillcolor="rgba(30,64,175,0.08)", name="Saldo acumulado",
        hovertemplate="%{x}<br>Saldo: R$ %{y:,.0f}<extra></extra>",
    )
    fig.add_hline(y=0, line_color=COR_TEXTO_MUTED, line_width=1,
                   annotation_text="investimento coberto", annotation_position="bottom right",
                   annotation_font=dict(size=11, color=COR_TEXTO_MUTED))
    if payback:
        idx = list(acumulado["mes_ref"]).index(payback)
        fig.add_annotation(
            x=meses[idx], y=acumulado["saldo_rs"].iloc[idx], text=f"🎉 payback em {mes_legivel(payback)}",
            showarrow=True, arrowhead=2, ax=0, ay=-40, bgcolor="white", bordercolor=COR_SALDO_POSITIVO,
            font=dict(size=12, color=COR_SALDO_POSITIVO),
        )
    fig.update_layout(**layout_base("Saldo acumulado vs. investimento",
                                      "economia acumulada menos o valor investido"))
    fig.update_yaxes(**eixo_y_moeda())
    fig.update_xaxes(**eixo_x_categoria())
    return fig


def grafico_economia_vs_parcela(fluxo: pd.DataFrame) -> go.Figure:
    """Barras pareadas verde (economia) / vermelho (parcela) por mês — o olho vê
    imediatamente em quais meses a barra verde não alcança a vermelha."""
    financiados = fluxo[fluxo["parcela_rs"] > 0]
    meses = [mes_legivel(m) for m in financiados["mes_ref"]]

    fig = go.Figure()
    fig.add_bar(x=meses, y=financiados["economia_rs"], name="Economia", marker_color=COR_ECONOMIA,
                hovertemplate="%{x}<br>Economia: R$ %{y:,.0f}<extra></extra>")
    fig.add_bar(x=meses, y=financiados["parcela_rs"], name="Parcela", marker_color=COR_PARCELA,
                hovertemplate="%{x}<br>Parcela: R$ %{y:,.0f}<extra></extra>")
    fig.update_layout(**layout_base("Economia vs. parcela, mês a mês",
                                      "a economia precisa alcançar a barra vermelha para o financiamento se pagar sozinho"))
    fig.update_layout(barmode="group", bargap=0.25)
    fig.update_yaxes(**eixo_y_moeda())
    fig.update_xaxes(**eixo_x_categoria())
    return fig


def grafico_roi_projetado(projecao: pd.DataFrame, investimento: float) -> go.Figure:
    """Linha de ROI acumulado com uma referência em 0% (ponto de equilíbrio nominal) e
    rótulo no ano em que o ROI vira positivo."""
    fig = go.Figure()
    fig.add_scatter(
        x=projecao["ano"], y=projecao["roi_acumulado_pct"], mode="lines", line=dict(color=COR_INVESTIMENTO, width=2.5),
        fill="tozeroy", fillcolor="rgba(30,64,175,0.08)", name="ROI acumulado",
        hovertemplate="ano %{x}<br>ROI: %{y:.0f}%<extra></extra>",
    )
    fig.add_hline(y=0, line_dash="dash", line_color=COR_TEXTO_MUTED, line_width=1)
    ano_payback = projecao[projecao["roi_acumulado_pct"] >= 0]
    if not ano_payback.empty:
        ano0 = ano_payback.iloc[0]
        fig.add_annotation(
            x=ano0["ano"], y=0, text=f"payback: ano {int(ano0['ano'])}", showarrow=True,
            arrowhead=2, ax=30, ay=-30, bgcolor="white", bordercolor=COR_SALDO_POSITIVO,
            font=dict(size=12, color=COR_SALDO_POSITIVO),
        )
    fig.update_layout(**layout_base("Projeção de 25 anos",
                                      f"ROI acumulado sobre o investimento de {rs(investimento)}, "
                                      "com reajuste de tarifa e degradação dos painéis"))
    fig.update_yaxes(title="ROI acumulado", ticksuffix="%", gridcolor=COR_GRADE, zeroline=False)
    fig.update_xaxes(title="Ano", showgrid=False, dtick=5)
    return fig
