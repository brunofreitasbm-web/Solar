"""Leitura por regras do layout real de fatura da Equatorial Pará (nota fiscal + boleto).
Calibrado em 136 faturas reais do usuário, cobrindo as duas variantes do PDF: com resumo
"Nome do Cliente / C.C." no rodapé, e com ficha de compensação (boleto) no lugar dele."""

import io
import re
import unicodedata

import pdfplumber

try:
    import cv2
    import numpy as np
    TEM_CV2 = True
except ImportError:
    TEM_CV2 = False

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
    r"(\d{2})/(20\d{2})\s+(\d{2}/\d{2}/\d{4})\s+R\$\s*(" + NUMERO_BR + r")\s+\d{2}/\d{2}/\d{4}\s+AS"
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
RE_EMISSAO = re.compile(r"DATA DE EMISSAO:\s*(\d{2}/\d{2}/\d{4})")
RE_LEITURAS = re.compile(r"\d{2}/\d{2}/\d{4}\s+\d{2}/\d{2}/\d{4}\s+\d{1,2}\s+(\d{2}/\d{2}/\d{4})")


def _linha_6_colunas(nome: str) -> re.Pattern:
    """Linhas de item: 'DESCRIÇÃO qtd tarifa tarifa pis icms valor' — o que interessa é o último."""
    return re.compile(nome + r"\s+" + NUMERO_BR + r"(?:\s+" + NUMERO_BR + r"){4}\s+(" + NUMERO_BR + r")")


RE_CONSUMO_RS = _linha_6_colunas(r"\bCONSUMO \(KWH\)")
RE_DISPONIBILIDADE_RS = _linha_6_colunas(r"CUSTO DE DISPONIBILIDADE \(KWH\)")
RE_FIO_B_RS = _linha_6_colunas(r"PARC\. INJ\. S/ DESC\. - GD2 \(KWH\)")
RE_BENEFICIO_BRUTO = re.compile(r"BENEFICIO TARIFARIO BRUTO SCEE\s+" + NUMERO_BR + r"\s+" + NUMERO_BR + r"\s+(" + NUMERO_BR + r")")
RE_BANDEIRA_RS = re.compile(r"ADICIONAL BANDEIRA\s+" + NUMERO_BR + r"\s+" + NUMERO_BR + r"\s+(" + NUMERO_BR + r")")
RE_CIP = re.compile(r"CIP-ILUM PUB PREF MUNIC\s+(" + NUMERO_BR + r")")
RE_MULTA = re.compile(r"\bMULTA\s+(" + NUMERO_BR + r")")
RE_JUROS = re.compile(r"\bJUROS\s+(" + NUMERO_BR + r")")
RE_CORRECAO = re.compile(r"CORRECAO MONETARIA\s+(" + NUMERO_BR + r")")
RE_RATEIO = re.compile(r"DISTRIBUICAO PERCENTUAL DAS SEGUINTES UCS:\s*((?:[\d.\-]+\(\s*[\d,]+\s*%\)\s*,?\s*)+)")
RE_PAR_RATEIO = re.compile(r"([\d.\-]+)\(\s*([\d,]+)\s*%\)")
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


def _iso(data_br: str | None) -> str:
    """'26/06/2025' -> '2025-06-26'"""
    if not data_br:
        return ""
    dia, mes, ano = data_br.split("/")
    return f"{ano}-{mes}-{dia}"


def _mes_total_vencimento(texto: str) -> tuple[str | None, float | None, str]:
    m = RE_CABECALHO.search(texto)
    if not m:
        return None, None, ""
    mes, ano, vencimento, total = m.groups()
    return f"{ano}-{mes}", numero_br(total), _iso(vencimento)


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


def _valor(regex: re.Pattern, texto: str) -> float | None:
    m = regex.search(texto)
    return numero_br(m.group(1)) if m else None


def _valor_texto(regex: re.Pattern, texto: str) -> str | None:
    m = regex.search(texto)
    return m.group(1) if m else None


def _soma(regex: re.Pattern, texto: str) -> float | None:
    achados = regex.findall(texto)
    return sum(numero_br(a) for a in achados) if achados else None


def _soma_opcional(*valores: float | None) -> float | None:
    presentes = [v for v in valores if v is not None]
    return sum(presentes) if presentes else None


def _composicao(texto: str, total_rs: float | None) -> dict[str, float | None]:
    """Quebra a conta nas linhas que a compõem; `outros_rs` fecha a diferença até o total."""
    liquido = _valor(RE_CREDITO_LIQUIDO, texto)
    itens = {
        "consumo_rs": _soma_opcional(_valor(RE_CONSUMO_RS, texto), _valor(RE_DISPONIBILIDADE_RS, texto)),
        "fio_b_rs": _valor(RE_FIO_B_RS, texto),
        "beneficio_rs": _soma_opcional(_valor(RE_BENEFICIO_BRUTO, texto), liquido),
        "bandeira_rs": _soma(RE_BANDEIRA_RS, texto),
        "cip_rs": _valor(RE_CIP, texto),
        "multa_rs": _valor(RE_MULTA, texto),
        "juros_rs": _soma_opcional(_valor(RE_JUROS, texto), _valor(RE_CORRECAO, texto)),
    }
    itens = {k: round(v, 2) if v is not None else None for k, v in itens.items()}
    itens["outros_rs"] = round(total_rs - sum(v for v in itens.values() if v is not None), 2) if total_rs is not None else None
    return itens


def _rateio(texto: str) -> dict[str, float]:
    m = RE_RATEIO.search(texto)
    if not m:
        return {}
    return {re.sub(r"\D", "", uc): numero_br(pct) for uc, pct in RE_PAR_RATEIO.findall(m.group(1))}


RE_LINHA_DIGITAVEL = re.compile(r"(\d{5}\.\d{5}\s+\d{5}\.\d{6}\s+\d{5}\.\d{6}\s+\d\s+\d{14})")


def extrair_pix_e_codigo_barras(pdf_bytes: bytes = b"", texto_bruto: str = "") -> tuple[str, str]:
    """Extrai a linha digitável do boleto e o payload do PIX Copia e Cola."""
    linha_digitavel = ""
    pix_copia_cola = ""

    if m := RE_LINHA_DIGITAVEL.search(texto_bruto):
        linha_digitavel = m.group(1).strip()

    if pdf_bytes and TEM_CV2:
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                p0 = pdf.pages[0]
                if not linha_digitavel:
                    texto_p0 = p0.extract_text() or ""
                    if m := RE_LINHA_DIGITAVEL.search(texto_p0):
                        linha_digitavel = m.group(1).strip()

                cands = [i for i in p0.images if i.get("top", 0) > 650 and 50 < i.get("width", 0) < 120]
                if cands:
                    img_meta = cands[0]
                    crop_box = (img_meta["x0"] - 3, img_meta["top"] - 3, img_meta["x1"] + 3, img_meta["bottom"] + 3)
                    pil_img = p0.crop(crop_box).to_image(resolution=400).original
                    np_img = np.array(pil_img.convert("RGB"))
                    gray = cv2.cvtColor(np_img, cv2.COLOR_RGB2GRAY)
                    bordered = cv2.copyMakeBorder(gray, 25, 25, 25, 25, cv2.BORDER_CONSTANT, value=255)
                    detector = cv2.QRCodeDetector()
                    val, _, _ = detector.detectAndDecode(bordered)
                    if not val:
                        _, thresh = cv2.threshold(bordered, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                        val, _, _ = detector.detectAndDecode(thresh)
                    if val and "pix" in val.lower():
                        pix_copia_cola = val
        except Exception:
            pass

    return pix_copia_cola, linha_digitavel


def interpretar(texto_bruto: str, pdf_bytes: bytes = b"") -> Fatura:
    texto = normalizar(texto_bruto)
    mes_ref, total_rs, vencimento = _mes_total_vencimento(texto)
    compensado, credito = _compensacao(texto)
    injetado = numero_br(m.group(1)) if (m := RE_INJETADO_TOTAL.search(texto)) else 0.0
    saldo = numero_br(m.group(1)) if (m := RE_SALDO_ACUMULADO.search(texto)) else 0.0
    bandeiras = RE_BANDEIRA.findall(texto)

    uc = _uc(texto)
    consumo = _consumo_kwh(texto)
    pix_copia_cola, linha_digitavel = extrair_pix_e_codigo_barras(pdf_bytes, texto_bruto)

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
        vencimento=vencimento,
        emissao=_iso(_valor_texto(RE_EMISSAO, texto)),
        proxima_leitura=_iso(_valor_texto(RE_LEITURAS, texto)),
        rateio=_rateio(texto),
        pix_copia_cola=pix_copia_cola,
        codigo_barras=linha_digitavel,
        **_composicao(texto, total_rs),
    )
    campos_presentes = {"uc": uc, "mes_ref": mes_ref, "consumo_kwh": consumo, "total_rs": total_rs}
    fatura.campos_faltando = [c for c in CAMPOS_OBRIGATORIOS if campos_presentes[c] is None]
    return fatura
