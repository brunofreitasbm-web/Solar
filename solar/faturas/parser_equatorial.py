"""Leitura por regras do layout real de fatura da Equatorial Pará (nota fiscal + boleto).
Calibrado em 136 faturas reais do usuário, cobrindo as duas variantes do PDF: com resumo
"Nome do Cliente / C.C." no rodapé, e com ficha de compensação (boleto) no lugar dele."""

import io
import re
import unicodedata

import pdfplumber

from solar.faturas.modelo import CAMPOS_OBRIGATORIOS, Fatura

MESES_ABREV = {"JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
               "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12}
NUMERO_BR = r"(?:-?\d{1,3}(?:\.\d{3})*(?:,\d+)?|-?\d+(?:,\d+)?)"

# Identificador estável da unidade: aparece em TODA fatura, logo antes do link da chave de
# acesso. Mais confiável que o "C.C." do rodapé, que só existe em uma das duas variantes.
RE_UC = re.compile(r"(\d)\.(\d{3})\.(\d{3})\.(\d{3})-(\d{2})\s*\n?\s*HTTPS")

# "<mês>/<ano> <vencimento> R$ <total> <emissão> AS <hora>" — aparece em toda fatura, logo
# após o protocolo de autorização, nas duas variantes de layout.
RE_CABECALHO = re.compile(
    r"(\d{2})/(20\d{2})\s+\d{2}/\d{2}/\d{4}\s+R\$\s*(" + NUMERO_BR + r")\s+\d{2}/\d{2}/\d{4}\s+AS"
)

RE_CONSUMO_LINHA = re.compile(
    r"\bCONSUMO \(KWH\)\s+(" + NUMERO_BR + r")(?:\s+" + NUMERO_BR + r"){4}\s+(" + NUMERO_BR + r")"
)
RE_CONSUMO_TOTAL = re.compile(
    r"CONSUMO ATIVO TOTAL\s+" + NUMERO_BR + r"\s+" + NUMERO_BR + r"\s+" + NUMERO_BR + r"\s+(" + NUMERO_BR + r")\s*KWH"
)
RE_INJETADO_TOTAL = re.compile(
    r"ENERGIA INJETADA ATIVO TOTAL\s+" + NUMERO_BR + r"\s+" + NUMERO_BR + r"\s+" + NUMERO_BR + r"\s+(" + NUMERO_BR + r")\s*KWH"
)
RE_COMPENSADO = re.compile(r"CONSUMO COMPENSADO\s*\(KWH\)\s+(" + NUMERO_BR + r")")
RE_CREDITO_LIQUIDO = re.compile(r"BENEFICIO TARIFARIO LIQUIDO SCEE\s+(" + NUMERO_BR + r")")
RE_SALDO_ACUMULADO = re.compile(r"SALDO ACUMULADO GERAL TOTAL:?\s*(" + NUMERO_BR + r")")
RE_GERADORA = re.compile(r"ENERGIA INJETADA ATIVO TOTAL|ENERGIA ATIVA INJETADA \(KWH\)")
RE_BANDEIRA = re.compile(r"\b(VERDE|AMARELA|VERMELHA(?:\s+PATAMAR\s*\d)?|ESCASSEZ HIDRICA)\s*:")
RE_ENDERECO = re.compile(r"CPF:.{0,20}\n(.{10,90})\nCEP:\s*(\d{5}-?\d{3})\s*-\s*([A-Z\s]+?)\s*-\s*([A-Z\s]+?)\s*-\s*PA")


def numero_br(texto: str) -> float:
    return float(texto.replace(".", "").replace(",", "."))


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.upper()


def extrair_texto(pdf: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        return "\n".join(p.extract_text() or "" for p in doc.pages)


def _uc(texto: str) -> str | None:
    m = RE_UC.search(texto)
    return "".join(m.groups()) if m else None


def _mes_e_total(texto: str) -> tuple[str | None, float | None]:
    m = RE_CABECALHO.search(texto)
    if not m:
        return None, None
    mes, ano, total = m.groups()
    return f"{ano}-{mes}", numero_br(total)


def _consumo_kwh(texto: str) -> float | None:
    """Prioriza a leitura do medidor (base de faturamento); usa a linha "Consumo (kWh)"
    só quando não há bandeira dividindo o ciclo em mais de um segmento de tarifa."""
    if m := RE_CONSUMO_TOTAL.search(texto):
        return numero_br(m.group(1))
    if m := RE_CONSUMO_LINHA.search(texto):
        return numero_br(m.group(1))
    return None


def _tarifa_kwh(texto: str) -> float | None:
    m = RE_CONSUMO_LINHA.search(texto)
    if not m:
        return None
    quantidade, valor_total = numero_br(m.group(1)), numero_br(m.group(2))
    return valor_total / quantidade if quantidade else None


def _compensacao(texto: str) -> tuple[float, float | None]:
    compensado = numero_br(RE_COMPENSADO.search(texto).group(1)) if RE_COMPENSADO.search(texto) else 0.0
    credito = abs(numero_br(RE_CREDITO_LIQUIDO.search(texto).group(1))) if RE_CREDITO_LIQUIDO.search(texto) else None
    return compensado, credito


def _endereco(texto: str) -> str:
    m = RE_ENDERECO.search(texto)
    if not m:
        return ""
    rua, bairro, cidade = m.group(1).strip().title(), m.group(3).strip().title(), m.group(4).strip().title()
    return f"{rua} — {bairro}, {cidade}"


def interpretar(texto_bruto: str) -> Fatura:
    texto = normalizar(texto_bruto)
    mes_ref, total_rs = _mes_e_total(texto)
    compensado, credito = _compensacao(texto)
    injetado = numero_br(m.group(1)) if (m := RE_INJETADO_TOTAL.search(texto)) else 0.0
    saldo = numero_br(m.group(1)) if (m := RE_SALDO_ACUMULADO.search(texto)) else 0.0
    bandeiras = RE_BANDEIRA.findall(texto)

    uc = _uc(texto)
    consumo = _consumo_kwh(texto)

    fatura = Fatura(
        uc=uc or "",
        mes_ref=mes_ref or "",
        consumo_kwh=consumo if consumo is not None else 0.0,
        injetado_kwh=injetado,
        compensado_kwh=compensado,
        saldo_creditos_kwh=saldo,
        credito_rs=credito,
        tarifa_kwh=_tarifa_kwh(texto),
        total_rs=total_rs if total_rs is not None else 0.0,
        bandeira="/".join(dict.fromkeys(b.title() for b in bandeiras)),
        endereco=_endereco(texto),
        origem="parser",
    )
    campos_presentes = {"uc": uc, "mes_ref": mes_ref, "consumo_kwh": consumo, "total_rs": total_rs}
    fatura.campos_faltando = [c for c in CAMPOS_OBRIGATORIOS if campos_presentes[c] is None]
    return fatura
