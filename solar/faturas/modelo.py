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
    credito_rs: float | None = None  # valor em R$ abatido pela energia compensada, quando a fatura informa
    tarifa_kwh: float | None = None  # R$/kWh com tributos
    total_rs: float = 0.0
    bandeira: str = ""
    endereco: str = ""
    arquivo: str = ""
    origem: str = "manual"
    campos_faltando: list[str] = field(default_factory=list)

    @property
    def tem_geracao(self) -> bool:
        return self.injetado_kwh > 0
