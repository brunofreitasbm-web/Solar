from dataclasses import dataclass, field

CAMPOS_OBRIGATORIOS = ("uc", "mes_ref", "consumo_kwh", "total_rs")
CAMPOS_GERACAO = ("injetado_kwh", "compensado_kwh")


@dataclass
class Fatura:
    uc: str = ""
    mes_ref: str = ""  # AAAA-MM
    consumo_kwh: float = 0.0
    injetado_kwh: float = 0.0
    compensado_kwh: float = 0.0
    saldo_creditos_kwh: float = 0.0
    credito_rs: float | None = None  # "Benefício Tarifário Líquido SCEE" da fatura (informativo)
    tarifa_kwh: float | None = None  # R$/kWh com tributos cobrado sobre o consumo não compensado
    total_rs: float = 0.0
    bandeira: str = ""
    endereco: str = ""
    arquivo: str = ""
    origem: str = "manual"
    campos_faltando: list[str] = field(default_factory=list)

    # Datas (ISO AAAA-MM-DD) usadas para prever o próximo vencimento
    vencimento: str = ""
    emissao: str = ""
    proxima_leitura: str = ""

    # Composição da conta em R$ (None = a fatura não trouxe a linha)
    consumo_rs: float | None = None      # energia cobrada + custo de disponibilidade
    fio_b_rs: float | None = None        # "Parc. Inj. s/ Desc. - GD2": Fio B da energia compensada
    beneficio_rs: float | None = None    # Benefício Tarifário Bruto + Líquido SCEE (já somados)
    bandeira_rs: float | None = None
    cip_rs: float | None = None
    multa_rs: float | None = None
    juros_rs: float | None = None        # juros + correção monetária
    outros_rs: float | None = None       # o que sobra para fechar no total da fatura

    # Percentual desta UC no rateio de cada geradora: {id da geradora (só dígitos): %}
    rateio: dict[str, float] = field(default_factory=dict)

    @property
    def tem_geracao(self) -> bool:
        return self.injetado_kwh > 0
