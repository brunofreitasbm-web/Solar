"""Tarifa B1 residencial vigente hoje, direto da base oficial da ANEEL (Dados Abertos)."""

from dataclasses import asdict, dataclass
from datetime import date

import requests

from solar.config import ANEEL_RECURSO_TARIFAS, ANEEL_URL, DISTRIBUIDORA_ANEEL
from solar.db import gravar_cache, ler_cache

CHAVE_CACHE = "tarifa_aneel_b1"
TIMEOUT_S = 30


@dataclass
class TarifaVigente:
    te_kwh: float
    tusd_kwh: float
    inicio_vigencia: str
    fim_vigencia: str
    resolucao: str
    consultado_em: str

    @property
    def sem_tributos(self) -> float:
        return self.te_kwh + self.tusd_kwh

    def com_tributos(self, icms: float, pis_cofins: float) -> float:
        # ICMS e PIS/COFINS são calculados "por dentro": incidem sobre o próprio valor final
        return self.sem_tributos / (1 - icms - pis_cofins)


class FalhaTarifa(Exception):
    pass


def _mwh(valor: str) -> float:
    return float(valor.replace(".", "").replace(",", ".") or 0)


def _buscar_registros() -> list[dict]:
    parametros = {
        "resource_id": ANEEL_RECURSO_TARIFAS,
        "filters": f'{{"SigAgente":"{DISTRIBUIDORA_ANEEL}","DscSubGrupo":"B1"}}',
        "sort": "DatInicioVigencia desc",
        "limit": 500,
    }
    resposta = requests.get(ANEEL_URL, params=parametros, timeout=TIMEOUT_S)
    resposta.raise_for_status()
    import json as _json
    return _json.loads(resposta.content.decode("utf-8"))["result"]["records"]


def _eh_residencial_convencional(r: dict) -> bool:
    return (
        r["DscBaseTarifaria"].startswith("Tarifa de Aplica")
        and r["DscModalidadeTarifaria"] == "Convencional"
        and r["DscSubClasse"] == "Residencial"
        and r["DscDetalhe"].startswith("N")  # "Não se aplica" — exclui linhas SCEE/APE
        and r["DscUnidadeTerciaria"] == "MWh"
    )


def selecionar_vigente(registros: list[dict], hoje: date) -> TarifaVigente:
    candidatos = [
        r for r in registros
        if _eh_residencial_convencional(r) and r["DatInicioVigencia"] <= hoje.isoformat() <= r["DatFimVigencia"]
    ]
    if not candidatos:
        raise FalhaTarifa("A ANEEL não retornou tarifa vigente para hoje.")
    atual = max(candidatos, key=lambda r: r["DatInicioVigencia"])
    return TarifaVigente(
        te_kwh=_mwh(atual["VlrTE"]) / 1000,
        tusd_kwh=_mwh(atual["VlrTUSD"]) / 1000,
        inicio_vigencia=atual["DatInicioVigencia"],
        fim_vigencia=atual["DatFimVigencia"],
        resolucao=atual["DscREH"],
        consultado_em=hoje.isoformat(),
    )


def tarifa_de_hoje(forcar: bool = False) -> TarifaVigente:
    hoje = date.today()
    cache = ler_cache(CHAVE_CACHE)
    if cache and not forcar and cache[0]["consultado_em"] == hoje.isoformat():
        return TarifaVigente(**cache[0])
    try:
        tarifa = selecionar_vigente(_buscar_registros(), hoje)
    except (requests.RequestException, KeyError, ValueError, FalhaTarifa) as erro:
        if cache:
            return TarifaVigente(**cache[0])
        raise FalhaTarifa("Não foi possível consultar a ANEEL agora. Verifique a internet e tente de novo.") from erro
    gravar_cache(CHAVE_CACHE, asdict(tarifa))
    return tarifa
