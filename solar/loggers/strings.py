"""Detecção de string fora do ar: tensão ~0 enquanto o inversor gera, numa string que já funcionou."""

from datetime import datetime

from solar.loggers import repositorio

POTENCIA_MINIMA_W = 500
TENSAO_FALHA_V = 50
TENSAO_EM_USO_V = 100
JANELA_DIAS = 7
MINUTOS_LEITURA_VALIDA = 15


def indices_em_falha(tensoes_atuais: list[float], maiores_tensoes: list[float], potencia_w: float) -> list[int]:
    """Posições (0-based) das strings sem tensão que tiveram tensão normal na janela recente.
    Uma entrada de MPPT que nunca teve painel não alerta, porque nunca esteve em uso."""
    if potencia_w < POTENCIA_MINIMA_W:
        return []
    return [i for i, v in enumerate(tensoes_atuais)
            if v < TENSAO_FALHA_V and i < len(maiores_tensoes) and maiores_tensoes[i] >= TENSAO_EM_USO_V]


def strings_em_falha(sn: str, leitura: dict) -> list[int]:
    """Só avalia leituras recentes: uma leitura velha (inversor desligado) não indica falha de string."""
    minutos = (datetime.now() - datetime.fromisoformat(leitura["lida_em"])).total_seconds() / 60
    if minutos > MINUTOS_LEITURA_VALIDA:
        return []
    return indices_em_falha(leitura["tensoes_pv_v"], repositorio.maior_tensao_por_string(sn, JANELA_DIAS),
                            leitura["potencia_w"])
