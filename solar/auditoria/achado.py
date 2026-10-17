from dataclasses import dataclass


@dataclass(frozen=True)
class Achado:
    uc: str
    mes_ref: str
    gravidade: str  # "erro" | "aviso"
    titulo: str
    explicacao: str
    acao: str


def reais(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
