"""Projeção da economia futura calibrada nas faturas: escalada do Fio B (Lei 14.300),
sazonalidade e degradação medidas na própria usina."""

from dataclasses import dataclass

import pandas as pd

from solar import config
from solar.economia import percentual_fio_b_ano


@dataclass
class ModeloEconomia:
    bruto_kwh: float          # R$/kWh da energia compensada pela tarifa cheia
    remanescente_kwh: float   # R$/kWh de benefício tarifário que continua na fatura
    fio_b_cheio_kwh: float    # R$/kWh de Fio B se fosse 100%
    pct_base: float           # % de Fio B vigente nos meses usados na calibração
    kwh_mes: float            # kWh compensados por mês, já sem o efeito da estação do ano
    sazonalidade: dict[int, float]  # fator por mês do ano (média 1)
    mes_base: str             # último mês observado

    @property
    def liquido_kwh_base(self) -> float:
        return self.bruto_kwh - self.remanescente_kwh - self.fio_b_cheio_kwh * self.pct_base


MESES_DE_PARTIDA = 2  # os primeiros meses de uma usina trazem energia acumulada/parcial


def _injecao_por_usina(df: pd.DataFrame) -> dict[str, pd.Series]:
    """Injeção mensal de cada geradora, sem os meses zerados nem os de partida — assim a
    entrada de uma segunda usina não aparece como "crescimento" ou "estação"."""
    series = {}
    geradoras = df[df["geradora"].astype(bool)] if len(df) else df
    for uc, grupo in (geradoras.groupby("uc") if len(geradoras) else []):
        ativa = grupo.set_index("mes_ref")["injetado_kwh"]
        ativa = ativa[ativa > 0].sort_index().iloc[MESES_DE_PARTIDA:]
        if not ativa.empty:
            series[uc] = ativa
    return series


def sazonalidade(df: pd.DataFrame, prior: dict[int, float] | None = None) -> dict[int, float]:
    """Fator de cada mês do ano (média 1), medido usina a usina. Meses com poucas
    observações são puxados para `prior` (ex.: climatologia da NASA) ou para 1."""
    prior = prior or {m: 1.0 for m in range(1, 13)}
    series = _injecao_por_usina(df)
    if not series:
        return dict(prior)
    somas: dict[int, float] = {}
    contagens: dict[int, float] = {}
    for serie in series.values():
        media, peso = serie.mean(), serie.mean()
        for mes_ref, valor in serie.items():
            mes = int(mes_ref[5:7])
            somas[mes] = somas.get(mes, 0.0) + peso * valor / media
            contagens[mes] = contagens.get(mes, 0.0) + peso
    fatores = {}
    for mes in range(1, 13):
        n = len([1 for s in series.values() for m in s.index if int(m[5:7]) == mes])
        observado = somas[mes] / contagens[mes] if mes in somas else prior[mes]
        fatores[mes] = prior[mes] + (observado - prior[mes]) * n / (n + 1)
    media_fatores = sum(fatores.values()) / 12
    return {m: f / media_fatores for m, f in fatores.items()}


def producao_anual_equivalente(df: pd.DataFrame, fatores: dict[int, float] | None = None) -> float:
    """Injeção média mensal de todas as usinas se cada uma operasse o ano inteiro: tira o
    efeito da estação (cada mês dividido pelo seu fator) e dos meses de partida."""
    fatores = fatores or {m: 1.0 for m in range(1, 13)}
    total = 0.0
    for serie in _injecao_por_usina(df).values():
        recente = serie.tail(12)
        total += sum(v / fatores[int(m[5:7])] for m, v in recente.items()) / len(recente)
    return total


def degradacao_observada(df: pd.DataFrame) -> tuple[float, int] | None:
    """Variação anual da injeção de cada usina comparando o mesmo mês em anos seguidos.
    Mistura degradação, clima e ampliações — é referência, não medida exata."""
    razoes = []
    for serie in _injecao_por_usina(df).values():
        for mes_ref, valor in serie.items():
            anterior = f"{int(mes_ref[:4]) - 1}{mes_ref[4:]}"
            if anterior in serie.index:
                razoes.append(valor / serie[anterior] - 1)
    return (sum(razoes) / len(razoes), len(razoes)) if razoes else None


def calibrar(df_economia: pd.DataFrame, meses_base: int = 6, prior_sazonal: dict[int, float] | None = None) -> ModeloEconomia | None:
    meses = sorted(df_economia["mes_ref"].unique())[-meses_base:]
    base = df_economia[df_economia["mes_ref"].isin(meses)]
    kwh_total = base["compensado_kwh"].sum()
    if kwh_total <= 0:
        return None

    fatores = sazonalidade(df_economia, prior_sazonal)
    por_mes = base.groupby("mes_ref")["compensado_kwh"].sum()
    kwh_mes = sum(v / fatores[int(m[5:7])] for m, v in por_mes.items()) / len(por_mes)

    mes_base = meses[-1]
    pct_base = percentual_fio_b_ano(int(mes_base[:4]))
    fio_b_base_kwh = base["fio_b_rs"].fillna(0).sum() / kwh_total
    return ModeloEconomia(
        bruto_kwh=base["valor_compensado_rs"].sum() / kwh_total,
        remanescente_kwh=base["beneficio_rs"].fillna(0).sum() / kwh_total,
        fio_b_cheio_kwh=fio_b_base_kwh / pct_base if pct_base > 0 else 0.0,
        pct_base=pct_base,
        kwh_mes=kwh_mes,
        sazonalidade=fatores,
        mes_base=mes_base,
    )


def _economia_do_mes(m: ModeloEconomia, mes: pd.Period, k: int, reajuste: float, degradacao: float, escalar_fio_b: bool) -> float:
    pct = percentual_fio_b_ano(mes.year) if escalar_fio_b else m.pct_base
    crescimento_tarifa = (1 + reajuste) ** (k / 12)
    liquido_kwh = (m.bruto_kwh - m.remanescente_kwh - m.fio_b_cheio_kwh * pct) * crescimento_tarifa
    kwh = m.kwh_mes * m.sazonalidade[mes.month] * (1 - degradacao) ** (k / 12)
    return max(liquido_kwh, 0.0) * kwh


def serie_futura(
    resumo: pd.DataFrame,
    n_meses: int,
    reajuste: float = config.PADRAO_REAJUSTE_TARIFA_ANUAL,
    degradacao: float = config.PADRAO_DEGRADACAO_ANUAL,
    modelo: ModeloEconomia | None = None,
    escalar_fio_b: bool = True,
    meses_base: int = 12,
) -> list[tuple[pd.Period, float]]:
    """Economia projetada para os próximos `n_meses`. Sem `modelo`, usa a média dos últimos
    `meses_base` meses crescendo com o reajuste líquido da degradação."""
    ultimo = pd.Period(resumo["mes_ref"].max())
    if modelo is None:
        fator_mensal = ((1 + reajuste) / (1 + degradacao)) ** (1 / 12)
        economia = resumo.tail(meses_base)["economia_rs"].mean()
        saida = []
        for k in range(1, n_meses + 1):
            saida.append((ultimo + k, economia))
            economia *= fator_mensal
        return saida
    return [(ultimo + k, _economia_do_mes(modelo, ultimo + k, k, reajuste, degradacao, escalar_fio_b))
            for k in range(1, n_meses + 1)]


def projecao_anual(
    resumo: pd.DataFrame,
    investimento: float,
    n_anos: int = config.VIDA_UTIL_ANOS,
    **parametros,
) -> pd.DataFrame:
    """Economia por ano de vida da usina: meses já ocorridos (reais) + projeção até `n_anos`."""
    reais = list(resumo.sort_values("mes_ref")["economia_rs"])
    futuros = [v for _, v in serie_futura(resumo, max(n_anos * 12 - len(reais), 0), **parametros)]
    valores = reais + futuros
    linhas, acumulado = [], 0.0
    for ano in range(1, n_anos + 1):
        economia_ano = sum(valores[(ano - 1) * 12: ano * 12])
        acumulado += economia_ano
        linhas.append({
            "ano": ano, "economia_anual_rs": economia_ano, "economia_acumulada_rs": acumulado,
            "roi_acumulado_pct": (acumulado / investimento - 1) * 100 if investimento else 0.0,
        })
    return pd.DataFrame(linhas)
