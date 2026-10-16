from dataclasses import asdict, dataclass, fields

from solar import config
from solar.db import conexao


@dataclass
class Configuracoes:
    investimento_total: float = 0.0
    data_investimento: str = ""
    valor_financiado: float = 0.0
    parcela_mensal: float = 0.0
    qtd_parcelas: int = 0
    data_primeira_parcela: str = ""
    icms: float = config.PADRAO_ICMS
    pis_cofins: float = config.PADRAO_PIS_COFINS
    degradacao_anual: float = config.PADRAO_DEGRADACAO_ANUAL
    reajuste_tarifa_anual: float = config.PADRAO_REAJUSTE_TARIFA_ANUAL
    performance_ratio: float = config.PADRAO_PERFORMANCE_RATIO

    @property
    def completo(self) -> bool:
        return self.investimento_total > 0 and bool(self.data_investimento)


def carregar() -> Configuracoes:
    with conexao() as con:
        salvos = {l["chave"]: l["valor"] for l in con.execute("SELECT chave, valor FROM config")}
    valores = {}
    for campo in fields(Configuracoes):
        if campo.name in salvos:
            bruto = salvos[campo.name]
            if campo.type is float or campo.type == "float":
                valores[campo.name] = float(bruto)
            elif campo.type is int or campo.type == "int":
                valores[campo.name] = int(bruto)
            else:
                valores[campo.name] = bruto
    return Configuracoes(**valores)


def salvar(cfg: Configuracoes) -> None:
    with conexao() as con:
        con.executemany(
            "INSERT OR REPLACE INTO config (chave, valor) VALUES (?, ?)",
            [(k, str(v)) for k, v in asdict(cfg).items()],
        )
