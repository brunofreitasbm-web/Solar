"""Fallback com Claude para faturas que o parser por regras não conseguiu ler por completo."""

import base64
import json

import anthropic

from solar.config import MODELO_IA
from solar.faturas.modelo import Fatura

INSTRUCOES = """Você recebe uma fatura de energia elétrica brasileira (Equatorial). Extraia os campos.
- uc: número da unidade consumidora / conta contrato, só dígitos.
- mes_ref: mês de referência no formato AAAA-MM.
- consumo_kwh: consumo ativo do mês em kWh.
- injetado_kwh: energia injetada na rede no mês (geração própria enviada), 0 se não houver.
- compensado_kwh: energia compensada/abatida nesta fatura via créditos (SCEE), 0 se não houver.
- saldo_creditos_kwh: saldo de créditos acumulados em kWh após esta fatura, 0 se não houver.
- credito_rs: valor total em R$ (positivo) abatido pela energia compensada; null se a fatura não mostrar.
- tarifa_kwh: tarifa de consumo em R$/kWh com tributos; null se não houver.
- total_rs: valor total a pagar em R$.
- bandeira: bandeira tarifária do mês (Verde, Amarela, Vermelha P1, Vermelha P2) ou "".
- endereco: endereço da unidade consumidora ou "".
Use null só onde indicado; nunca invente valores."""

ESQUEMA = {
    "type": "object",
    "properties": {
        "uc": {"type": "string"},
        "mes_ref": {"type": "string"},
        "consumo_kwh": {"type": "number"},
        "injetado_kwh": {"type": "number"},
        "compensado_kwh": {"type": "number"},
        "saldo_creditos_kwh": {"type": "number"},
        "credito_rs": {"type": ["number", "null"]},
        "tarifa_kwh": {"type": ["number", "null"]},
        "total_rs": {"type": "number"},
        "bandeira": {"type": "string"},
        "endereco": {"type": "string"},
    },
    "required": [
        "uc", "mes_ref", "consumo_kwh", "injetado_kwh", "compensado_kwh", "saldo_creditos_kwh",
        "credito_rs", "tarifa_kwh", "total_rs", "bandeira", "endereco",
    ],
    "additionalProperties": False,
}


class FalhaLeituraIA(Exception):
    pass


def interpretar(pdf: bytes) -> Fatura:
    cliente = anthropic.Anthropic()
    try:
        resposta = cliente.beta.messages.create(
            model=MODELO_IA,
            max_tokens=4000,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": ESQUEMA}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "document", "source": {
                        "type": "base64", "media_type": "application/pdf",
                        "data": base64.standard_b64encode(pdf).decode(),
                    }},
                    {"type": "text", "text": INSTRUCOES},
                ],
            }],
        )
    except anthropic.AuthenticationError as erro:
        raise FalhaLeituraIA("Chave da Anthropic inválida. Confira ANTHROPIC_API_KEY no arquivo .env.") from erro
    except anthropic.RateLimitError as erro:
        raise FalhaLeituraIA("Limite de uso da IA atingido. Tente de novo em alguns minutos.") from erro
    except anthropic.APIConnectionError as erro:
        raise FalhaLeituraIA("Sem conexão com a IA. Verifique a internet.") from erro
    except anthropic.APIStatusError as erro:
        raise FalhaLeituraIA(f"A IA recusou o arquivo ({erro.status_code}). Preencha os campos manualmente.") from erro

    if resposta.stop_reason in ("refusal", "max_tokens"):
        raise FalhaLeituraIA("A IA não conseguiu ler esta fatura. Preencha os campos manualmente.")
    texto = next(b.text for b in resposta.content if b.type == "text")
    return Fatura(**json.loads(texto), origem="ia")
