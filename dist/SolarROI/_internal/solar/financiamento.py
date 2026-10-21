"""Fluxo de caixa do financiamento: compara a economia de cada mês com a parcela, projeta o
ponto de equilíbrio e simula amortização antecipada."""

from dataclasses import dataclass
from datetime import date

import numpy_financial as npf
import pandas as pd

from solar import config
from solar.configuracoes import Configuracoes
from solar.datas import mes_ref, somar_meses
from solar.projecao import ModeloEconomia, serie_futura

TOLERANCIA_SALDO_RS = 0.005


def _inicio(cfg: Configuracoes) -> date:
    return date.fromisoformat(cfg.data_primeira_parcela)


def parcelas_por_mes(cfg: Configuracoes) -> dict[str, float]:
    """{mes_ref: valor da parcela} para cada mês em que há parcela do financiamento."""
    if not cfg.parcela_mensal or not cfg.qtd_parcelas or not cfg.data_primeira_parcela:
        return {}
    inicio = _inicio(cfg)
    return {mes_ref(somar_meses(inicio, n)): cfg.parcela_mensal for n in range(cfg.qtd_parcelas)}


def fluxo_com_financiamento(resumo_mensal: pd.DataFrame, cfg: Configuracoes) -> pd.DataFrame:
    """Para cada mês: economia, parcela (0 fora do período financiado) e o saldo líquido
    (economia − parcela) — mostra se a usina já está se pagando mês a mês."""
    df = resumo_mensal.copy()
    df["parcela_rs"] = df["mes_ref"].map(parcelas_por_mes(cfg)).fillna(0.0)
    df["saldo_liquido_rs"] = df["economia_rs"] - df["parcela_rs"]
    df["saldo_liquido_acumulado_rs"] = df["saldo_liquido_rs"].cumsum()
    return df


def mes_parcelas_termina(cfg: Configuracoes) -> str | None:
    parcelas = parcelas_por_mes(cfg)
    return max(parcelas) if parcelas else None


def mes_ponto_equilibrio(
    resumo_mensal: pd.DataFrame,
    cfg: Configuracoes,
    degradacao_anual: float = config.PADRAO_DEGRADACAO_ANUAL,
    reajuste_tarifa_anual: float = config.PADRAO_REAJUSTE_TARIFA_ANUAL,
    meses_base: int = 12,
    modelo: ModeloEconomia | None = None,
    escalar_fio_b: bool = True,
    parcelas: dict[str, float] | None = None,
    desembolso_extra: float = 0.0,
) -> str | None:
    """Mês em que o saldo líquido acumulado (economia − parcelas pagas − desembolsos
    extras) deixa de ser negativo. Diferente do payback total, que ignora o custo mensal
    do financiamento. `parcelas` substitui o cronograma original (ex.: após amortizar)."""
    if resumo_mensal.empty:
        return None
    fluxo = fluxo_com_financiamento(resumo_mensal, cfg)
    saldo = fluxo["saldo_liquido_acumulado_rs"].iloc[-1] - desembolso_extra
    if saldo >= 0:
        return fluxo["mes_ref"].iloc[-1]

    cronograma = parcelas_por_mes(cfg) if parcelas is None else parcelas
    futuro = serie_futura(resumo_mensal, 600, reajuste_tarifa_anual, degradacao_anual, modelo, escalar_fio_b, meses_base)
    for mes, economia in futuro:
        saldo += economia - cronograma.get(str(mes), 0.0)
        if saldo >= 0:
            return str(mes)
    return None


def taxa_mensal(cfg: Configuracoes) -> float | None:
    """Taxa de juros mensal embutida no financiamento (valor financiado × parcelas)."""
    if not (cfg.valor_financiado and cfg.parcela_mensal and cfg.qtd_parcelas):
        return None
    return float(npf.rate(cfg.qtd_parcelas, -cfg.parcela_mensal, cfg.valor_financiado, 0))


def parcelas_pagas(cfg: Configuracoes, hoje: date) -> int:
    if not cfg.data_primeira_parcela:
        return 0
    inicio = _inicio(cfg)
    return sum(1 for n in range(cfg.qtd_parcelas) if somar_meses(inicio, n) <= hoje)


def saldo_devedor(cfg: Configuracoes, pagas: int) -> float:
    """Valor presente das parcelas que faltam, descontado pela taxa do contrato."""
    r, restantes = taxa_mensal(cfg), cfg.qtd_parcelas - pagas
    if restantes <= 0:
        return 0.0
    return cfg.parcela_mensal * (1 - (1 + r) ** -restantes) / r


@dataclass
class Amortizacao:
    valor: float                 # quanto foi efetivamente amortizado
    modo: str                    # "prazo" (mantém a parcela) ou "parcela" (mantém o prazo)
    taxa_mensal: float
    pagas: int
    restantes_antes: int
    saldo_antes: float
    saldo_depois: float
    parcela_nova: float
    restantes_depois: int
    juros_antes: float           # juros que ainda seriam pagos sem amortizar
    juros_depois: float
    parcelas: dict[str, float]   # cronograma completo (já pagas + novas) por mês

    @property
    def juros_economizados(self) -> float:
        return self.juros_antes - self.juros_depois

    @property
    def quitou(self) -> bool:
        return self.saldo_depois <= TOLERANCIA_SALDO_RS


def _cronograma(saldo: float, r: float, parcela: float) -> list[float]:
    pagamentos = []
    while saldo > TOLERANCIA_SALDO_RS:
        juros = saldo * r
        if parcela <= juros:
            raise ValueError("A parcela não cobre os juros do saldo devedor.")
        pagamento = min(parcela, saldo + juros)
        saldo = saldo + juros - pagamento
        pagamentos.append(pagamento)
    return pagamentos


def simular_amortizacao(cfg: Configuracoes, valor: float, modo: str, hoje: date | None = None) -> Amortizacao:
    """Simula pagar `valor` hoje. "prazo" mantém a parcela e encurta o contrato (poupa mais
    juros); "parcela" mantém o prazo e reduz a parcela (alivia o caixa mensal)."""
    hoje = hoje or date.today()
    r = taxa_mensal(cfg)
    pagas = parcelas_pagas(cfg, hoje)
    restantes = cfg.qtd_parcelas - pagas
    saldo_antes = saldo_devedor(cfg, pagas)
    valor = min(valor, saldo_antes)
    saldo_depois = saldo_antes - valor

    if saldo_depois <= TOLERANCIA_SALDO_RS:
        novas, parcela_nova = [], 0.0
    elif modo == "prazo":
        parcela_nova = cfg.parcela_mensal
        novas = _cronograma(saldo_depois, r, parcela_nova)
    else:
        parcela_nova = float(-npf.pmt(r, restantes, saldo_depois))
        novas = _cronograma(saldo_depois, r, parcela_nova)

    inicio = _inicio(cfg)
    ultimo_mes_pago = mes_ref(somar_meses(inicio, pagas - 1))
    originais = {m: v for m, v in parcelas_por_mes(cfg).items() if m <= ultimo_mes_pago}
    futuras = {mes_ref(somar_meses(inicio, pagas + i)): p for i, p in enumerate(novas)}
    return Amortizacao(
        valor=valor, modo=modo, taxa_mensal=r, pagas=pagas, restantes_antes=restantes,
        saldo_antes=saldo_antes, saldo_depois=saldo_depois, parcela_nova=parcela_nova,
        restantes_depois=len(novas), juros_antes=restantes * cfg.parcela_mensal - saldo_antes,
        juros_depois=sum(novas) - saldo_depois, parcelas={**originais, **futuras},
    )
