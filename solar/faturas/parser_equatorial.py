"""Leitura por regras do layout de fatura da Equatorial. Trabalha sobre texto normalizado
(maiúsculo, sem acento) para tolerar variações de OCR/encoding entre versões do PDF."""

import io
import re
import unicodedata

import pdfplumber

from solar.faturas.modelo import CAMPOS_OBRIGATORIOS, Fatura

MESES = {"JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
         "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12}
NUMERO_BR = r"-?\d{1,3}(?:\.\d{3})*(?:,\d+)?|-?\d+(?:,\d+)?"

RE_UC = re.compile(r"(?:UNIDADE CONSUMIDORA|CONTA CONTRATO|INSTALACAO|CODIGO DO CLIENTE|\bUC\b)\D{0,40}?(\d{6,12})")
RE_MES_TEXTO = re.compile(r"\b(" + "|".join(MESES) + r")\s*/\s*(20\d{2})\b")
RE_MES_NUMERO = re.compile(r"REFERENCIA\D{0,30}?(\d{2})\s*/\s*(20\d{2})")
RE_TOTAL = re.compile(r"(?:TOTAL A PAGAR|VALOR A PAGAR|VALOR TOTAL)\D{0,20}?(\d{1,3}(?:\.\d{3})*,\d{2})")
RE_SALDO = re.compile(r"SALDO\s*(?:ATUAL|ACUMULADO|DE CREDITOS?|DISPONIVEL|A COMPENSAR)?\D{0,30}?(" + NUMERO_BR + r")\s*KWH")
RE_INJETADO_MES = re.compile(r"(?:ENERGIA\s+)?(?:INJETADA|GERACAO)\s+(?:NO|DO)\s+(?:MES|CICLO)\D{0,20}?(" + NUMERO_BR + r")\s*KWH")
RE_BANDEIRA = re.compile(r"BANDEIRA\s*(VERDE|AMARELA|VERMELHA(?:\s*P(?:ATAMAR)?\s*\d)?|ESCASSEZ HIDRICA)")
RE_ENDERECO = re.compile(r"(?:ENDERECO|LOCAL DE CONSUMO)\s*:?\s*(.{10,90})")


def numero_br(texto: str) -> float:
    return float(texto.replace(".", "").replace(",", "."))


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.upper()


def extrair_texto(pdf: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        return "\n".join(p.extract_text() or "" for p in doc.pages)


def _linhas_com(texto: str, padrao: str, excluir: str | None = None) -> list[list[float]]:
    """Números de cada linha que casa com `padrao` — itens da fatura vêm como 'DESCRIÇÃO qtd tarifa valor'."""
    resultado = []
    for linha in texto.splitlines():
        if re.search(padrao, linha) and not (excluir and re.search(excluir, linha)):
            numeros = [numero_br(n) for n in re.findall(NUMERO_BR, linha)]
            if numeros:
                resultado.append(numeros)
    return resultado


def _mes_ref(texto: str) -> str:
    if m := RE_MES_NUMERO.search(texto):
        return f"{m.group(2)}-{m.group(1)}"
    if m := RE_MES_TEXTO.search(texto):
        return f"{m.group(2)}-{MESES[m.group(1)]:02d}"
    return ""


def _consumo_e_tarifa(texto: str) -> tuple[float, float | None]:
    linhas = _linhas_com(texto, r"CONSUMO.*KWH|^CONSUMO\b", excluir=r"INJETAD|MEDIA|HISTORICO")
    if not linhas:
        return 0.0, None
    numeros = linhas[0]
    tarifa = next((n for n in numeros[1:] if 0.2 < n < 3), None)
    return numeros[0], tarifa


def _compensacao(texto: str) -> tuple[float, float | None]:
    """Energia injetada costuma aparecer em duas linhas (TUSD e TE) com a mesma quantidade:
    quantidade = maior kWh, crédito = soma dos valores das linhas."""
    linhas = _linhas_com(texto, r"INJETAD|COMPENSAD|SCEE", excluir=r"NO MES|DO MES|SALDO")
    if not linhas:
        return 0.0, None
    quantidade = max(abs(l[0]) for l in linhas)
    credito = sum(abs(l[-1]) for l in linhas if len(l) > 1)
    return quantidade, credito or None


def _primeiro(regex: re.Pattern, texto: str, conversor=str):
    m = regex.search(texto)
    return conversor(m.group(1).strip()) if m else None


def interpretar(texto_bruto: str) -> Fatura:
    texto = normalizar(texto_bruto)
    consumo, tarifa = _consumo_e_tarifa(texto)
    compensado, credito = _compensacao(texto)
    injetado = _primeiro(RE_INJETADO_MES, texto, numero_br) or 0.0

    fatura = Fatura(
        uc=_primeiro(RE_UC, texto) or "",
        mes_ref=_mes_ref(texto),
        consumo_kwh=consumo,
        injetado_kwh=injetado,
        compensado_kwh=compensado,
        saldo_creditos_kwh=_primeiro(RE_SALDO, texto, numero_br) or 0.0,
        credito_rs=credito,
        tarifa_kwh=tarifa,
        total_rs=_primeiro(RE_TOTAL, texto, numero_br) or 0.0,
        bandeira=(_primeiro(RE_BANDEIRA, texto) or "").title(),
        endereco=(_primeiro(RE_ENDERECO, texto) or "").title(),
        origem="parser",
    )
    fatura.campos_faltando = [c for c in CAMPOS_OBRIGATORIOS if not getattr(fatura, c)]
    return fatura
