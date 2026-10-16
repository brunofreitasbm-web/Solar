"""Usinas em instalação: cadastro da ficha técnica e projeção de geração, economia e retorno
antes de existir a primeira fatura. Para onde vai cada kWh: consumo simultâneo na própria
unidade (tarifa cheia, sem Fio B), créditos abatidos na unidade, créditos para outras unidades."""

from dataclasses import asdict, dataclass, replace

import numpy_financial as npf

from solar import config, unidades
from solar.db import conexao
from solar.expansao import ResultadoExpansao, simular_expansao
from solar.projecao import ModeloEconomia

RELACAO_CC_CA_MAXIMA = 1.5
STATUS = ("Em instalação", "Operando")


@dataclass
class UsinaPlanejada:
    nome: str
    paineis: int
    potencia_painel_w: float
    id: int | None = None
    endereco: str = ""
    uc: str = ""
    status: str = STATUS[0]
    inversor: str = ""
    potencia_inversor_kw: float = 0.0
    custo_total: float | None = None
    valor_financiado: float | None = None
    parcela_mensal: float | None = None
    qtd_parcelas: int | None = None
    data_operacao: str | None = None
    consumo_kwh_mes: float | None = None
    simultaneidade: float = 0.4
    lat: float | None = None
    lon: float | None = None

    @property
    def kwp(self) -> float:
        return self.paineis * self.potencia_painel_w / 1000

    @property
    def relacao_cc_ca(self) -> float | None:
        return self.kwp / self.potencia_inversor_kw if self.potencia_inversor_kw else None


@dataclass
class Premissas:
    rendimento_kwh_kwp_mes: float
    valor_direto_kwh: float       # R$ evitado por kWh consumido na hora (tarifa cheia com tributos)
    valor_credito_kwh: float      # R$ evitado por kWh compensado depois (já sem Fio B e encargos)
    lacuna_outras_unidades_kwh: float
    custo_por_kwp_estimado: float
    reajuste_anual: float
    degradacao_anual: float
    desconto_anual: float


@dataclass
class ProjecaoUsina:
    geracao_kwh_mes: float
    direto_kwh: float
    creditos_unidade_kwh: float
    creditos_outras_kwh: float
    sobra_kwh: float
    economia_mes: float
    custo_total: float
    custo_estimado: bool
    financiamento_juros_mensal: float | None
    expansao: ResultadoExpansao


def valor_liquido_usina_nova(modelo: ModeloEconomia) -> float:
    """R$ por kWh compensado numa usina nova (GD III): Fio B a 100% e desconto extra de encargos."""
    return (modelo.bruto_kwh - modelo.remanescente_kwh - modelo.fio_b_cheio_kwh) * (1 - config.DESCONTO_USINA_NOVA)


def rendimento_medido(df, lista: list[unidades.Unidade], sazonalidade: dict[int, float] | None, meses: int = 6) -> float | None:
    """kWh injetados por kWp ao mês nas usinas já operando, sem o efeito da estação do ano.
    Só conta a energia injetada: o que a usina consome na hora fica de fora, então é um piso."""
    por_usina = []
    for u in lista:
        if not (u.geradora and u.kwp):
            continue
        recentes = df[(df["uc"] == u.uc) & (df["injetado_kwh"] > 0)].sort_values("mes_ref").tail(meses)
        if recentes.empty:
            continue
        fator = recentes["mes_ref"].map(lambda m: (sazonalidade or {}).get(int(m[5:7]), 1.0) or 1.0)
        por_usina.append(((recentes["injetado_kwh"] / fator).mean(), u.kwp))
    total_kwp = sum(k for _, k in por_usina)
    return sum(g for g, _ in por_usina) / total_kwp if total_kwp else None


def geracao_mensal(kwp: float, rendimento: float, sazonalidade: dict[int, float] | None) -> list[float]:
    return [kwp * rendimento * (sazonalidade or {}).get(m, 1.0) for m in range(1, 13)]


def _financiamento(u: UsinaPlanejada, custo: float) -> tuple[float | None, float]:
    if not (u.valor_financiado and u.parcela_mensal and u.qtd_parcelas):
        return None, 0.0
    juros = float(npf.rate(u.qtd_parcelas, -u.parcela_mensal, u.valor_financiado, 0))
    return juros, max(1 - u.valor_financiado / custo, 0.0)


def projetar(u: UsinaPlanejada, p: Premissas) -> ProjecaoUsina:
    geracao = u.kwp * p.rendimento_kwh_kwp_mes
    consumo = u.consumo_kwh_mes or 0.0
    direto = min(u.simultaneidade * consumo, geracao)
    injetado = geracao - direto
    na_unidade = min(injetado, max(consumo - direto - config.DISPONIBILIDADE_KWH, 0.0))
    em_outras = min(injetado - na_unidade, p.lacuna_outras_unidades_kwh)
    uteis = direto + na_unidade + em_outras
    economia = direto * p.valor_direto_kwh + (na_unidade + em_outras) * p.valor_credito_kwh

    custo = u.custo_total or p.custo_por_kwp_estimado * u.kwp
    juros, entrada_pct = _financiamento(u, custo)
    resultado = simular_expansao(
        u.kwp, custo / u.kwp, p.rendimento_kwh_kwp_mes, economia / uteis if uteis else 0.0, p.reajuste_anual,
        p.degradacao_anual, p.desconto_anual, juros, u.qtd_parcelas or 48, entrada_pct, uteis,
    )
    return ProjecaoUsina(geracao, direto, na_unidade, em_outras, geracao - uteis, economia, custo,
                         not u.custo_total, juros, resultado)


def listar() -> list[UsinaPlanejada]:
    with conexao() as con:
        linhas = con.execute("SELECT * FROM usinas_planejadas ORDER BY id").fetchall()
    return [UsinaPlanejada(**dict(l)) for l in linhas]


def salvar(usina: UsinaPlanejada) -> int:
    usina = replace(usina, uc="".join(c for c in usina.uc if c.isdigit()))
    dados = asdict(usina)
    with conexao() as con:
        cursor = con.execute(
            f"INSERT OR REPLACE INTO usinas_planejadas ({', '.join(dados)}) VALUES ({', '.join(':' + c for c in dados)})", dados)
        usina_id = usina.id or cursor.lastrowid
    _sincronizar_unidade(usina)
    return usina_id


def _sincronizar_unidade(u: UsinaPlanejada) -> None:
    """Com o número da UC informado, a unidade já nasce marcada como geradora e com os kWp certos
    — a primeira fatura que chegar cai nela sem mais cadastro."""
    if not u.uc:
        return
    unidades.garantir(u.uc, u.endereco, True)
    atual = next(x for x in unidades.listar() if x.uc == u.uc)
    unidades.salvar(replace(atual, kwp=u.kwp, apelido=atual.apelido or u.nome, endereco=atual.endereco or u.endereco,
                            lat=atual.lat or u.lat, lon=atual.lon or u.lon))


def excluir(usina_id: int) -> None:
    with conexao() as con:
        con.execute("DELETE FROM usinas_planejadas WHERE id = ?", (usina_id,))
