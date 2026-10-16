"""Previsão de vencimentos, calendário (.ics) para lembretes e custo dos atrasos pagos."""

import re
import urllib.parse
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from solar.config import EMAIL_ISABELA
from solar.datas import mes_ref, somar_meses

PRAZO_PADRAO_DIAS = 7  # emissão → vencimento quando não há fatura anterior para medir
DIAS_PARA_CONSIDERAR_FATURA_ATRASADA = 5


def _data(iso: str | None) -> date | None:
    return date.fromisoformat(iso) if isinstance(iso, str) and iso else None


def proximos_vencimentos(df: pd.DataFrame, nomes: dict[str, str], hoje: date | None = None) -> pd.DataFrame:
    """Prevê o próximo vencimento de cada unidade pela leitura seguinte e pelo prazo
    emissão→vencimento da última fatura. `aguardando_fatura` indica que a fatura do ciclo
    já deveria ter saído e ainda não foi carregada."""
    hoje = hoje or date.today()
    linhas = []
    for uc, grupo in df.sort_values("mes_ref").groupby("uc"):
        ultima = grupo.iloc[-1]
        vencimento, emissao, proxima_leitura = _data(ultima["vencimento"]), _data(ultima["emissao"]), _data(ultima["proxima_leitura"])
        if vencimento is None:
            continue
        prazo = (vencimento - emissao).days if emissao else PRAZO_PADRAO_DIAS
        if proxima_leitura:
            emissao_prevista = proxima_leitura + timedelta(days=1)
            previsto = emissao_prevista + timedelta(days=prazo)
        else:
            emissao_prevista, previsto = None, somar_meses(vencimento, 1)

        aguardando = bool(emissao_prevista and emissao_prevista + timedelta(days=DIAS_PARA_CONSIDERAR_FATURA_ATRASADA) <= hoje)
        while previsto + timedelta(days=30) < hoje:  # histórico antigo: rola para o ciclo atual
            previsto = somar_meses(previsto, 1)

        total_rs = float(ultima.get("total_rs", 0.0)) if pd.notna(ultima.get("total_rs")) else 0.0
        pix = str(ultima.get("pix_copia_cola", "")) if pd.notna(ultima.get("pix_copia_cola")) else ""
        codigo_barras = str(ultima.get("codigo_barras", "")) if pd.notna(ultima.get("codigo_barras")) else ""
        endereco = str(ultima.get("endereco", "")) if pd.notna(ultima.get("endereco")) else ""

        linhas.append({
            "uc": uc, "unidade": nomes.get(uc, uc), "ultima_fatura": ultima["mes_ref"],
            "ultimo_vencimento": vencimento, "vencimento_previsto": previsto,
            "dias": (previsto - hoje).days, "aguardando_fatura": aguardando,
            "total_rs": total_rs, "pix_copia_cola": pix, "codigo_barras": codigo_barras,
            "endereco": endereco,
        })
    return pd.DataFrame(linhas).sort_values("vencimento_previsto").reset_index(drop=True)


def extrair_chave_pix_simples(pix_copia_cola: str) -> str:
    """Extrai a chave PIX limpa (UUID ou chave curta) de dentro do código EMV do Pix."""
    if not pix_copia_cola:
        return ""
    m_uuid = re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", pix_copia_cola)
    if m_uuid:
        return m_uuid.group(0)
    return pix_copia_cola[:36] if len(pix_copia_cola) > 36 else pix_copia_cola


def link_google_agenda(p: dict | pd.Series) -> str:
    """Gera link direto para criar evento no Google Agenda já com Isabela convidada, valor e chave Pix no status."""
    data = p.get("vencimento_previsto")
    if isinstance(data, str):
        data = date.fromisoformat(data)
    elif not isinstance(data, date):
        data = date.today()

    data_str = data.strftime("%Y%m%d")
    data_fim = (data + timedelta(days=1)).strftime("%Y%m%d")
    unidade = p.get("unidade", "Energia")
    total_rs = p.get("total_rs", 0.0)
    endereco = p.get("endereco", "")
    pix = p.get("pix_copia_cola", "")
    codigo_barras = p.get("codigo_barras", "")

    chave_pix = extrair_chave_pix_simples(pix)
    status_pix = f"[PIX: {chave_pix}]" if chave_pix else (f"[Boleto: {codigo_barras[:15]}...]" if codigo_barras else "[Aguardando Fatura/PIX]")
    titulo = f"{status_pix} Energia R$ {total_rs:.2f} - {unidade}"

    detalhes_linhas = [
        f"STATUS: AGUARDANDO PAGAMENTO {status_pix}",
        f"Fatura de Energia Equatorial - {unidade}",
        f"Endereço / De onde é: {endereco}" if endereco else "",
        f"Vencimento: {data.strftime('%d/%m/%Y')}",
        f"Valor da energia: R$ {total_rs:.2f}",
        f"Convidada (notificada): {EMAIL_ISABELA}",
        "",
        f"CHAVE PIX: {chave_pix}" if chave_pix else "",
        "CÓDIGO PIX COPIA E COLA:" if pix else "",
        pix if pix else "",
        "",
        f"LINHA DIGITÁVEL / BOLETO: {codigo_barras}" if codigo_barras else "",
    ]
    detalhes = "\n".join(l for l in detalhes_linhas if l is not None).strip()

    params = {
        "action": "TEMPLATE",
        "text": titulo,
        "dates": f"{data_str}/{data_fim}",
        "details": detalhes,
        "location": endereco or "Equatorial Energia",
        "add": EMAIL_ISABELA,
    }
    return "https://calendar.google.com/calendar/render?" + urllib.parse.urlencode(params)


def gerar_ics(previsoes: pd.DataFrame, meses: int = 6, agora: datetime | None = None) -> str:
    """Calendário para importar no Google Agenda/Outlook, com lembrete 3 dias e 1 dia antes,
    com chave Pix no status, valor, local e cópia para Isabela."""
    agora = agora or datetime.now(timezone.utc)
    carimbo = agora.strftime("%Y%m%dT%H%M%SZ")
    linhas = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Solar ROI//Vencimentos//PT-BR", "CALSCALE:GREGORIAN"]
    for _, p in previsoes.iterrows():
        total_rs = p.get("total_rs", 0.0)
        pix = p.get("pix_copia_cola", "")
        codigo_barras = p.get("codigo_barras", "")
        endereco = p.get("endereco", "")
        unidade = p.get("unidade", "")
        chave_pix = extrair_chave_pix_simples(pix)
        status_pix = f"[PIX: {chave_pix}]" if chave_pix else (f"[Boleto: {codigo_barras[:15]}...]" if codigo_barras else "[Aguardando Fatura/PIX]")

        for k in range(meses):
            data = somar_meses(p["vencimento_previsto"], k)
            desc = (
                f"STATUS: AGUARDANDO PAGAMENTO {status_pix}\\n"
                f"Fatura de Energia - {unidade}\\n"
                f"Endereço / De onde é: {endereco}\\n"
                f"Vencimento: {data:%d/%m/%Y}\\n"
                f"Valor da energia: R$ {total_rs:.2f}\\n"
                f"Chave Pix: {chave_pix}\\n\\n"
                f"Chave Pix (Copia e Cola):\\n{pix}\\n\\n"
                f"Linha Digitavel: {codigo_barras}"
            )
            linhas += [
                "BEGIN:VEVENT",
                f"UID:{p['uc']}-{mes_ref(data)}@solar-roi",
                f"DTSTAMP:{carimbo}",
                f"DTSTART;VALUE=DATE:{data:%Y%m%d}",
                f"SUMMARY:{status_pix} Vence fatura R$ {total_rs:.2f} - {unidade}",
                f"DESCRIPTION:{desc}",
                f"LOCATION:{endereco}",
                "STATUS:CONFIRMED",
                f"ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE;CN=Isabela:mailto:{EMAIL_ISABELA}",
                "BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Fatura vence em 3 dias", "TRIGGER:-P3D", "END:VALARM",
                "BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Fatura vence amanhã", "TRIGGER:-P1D", "END:VALARM",
                "END:VEVENT",
            ]
    linhas.append("END:VCALENDAR")
    return "\r\n".join(linhas) + "\r\n"


def encargos_por_atraso(df: pd.DataFrame, nomes: dict[str, str]) -> pd.DataFrame:
    """Multa, juros e correção cobrados nas faturas — sinal de pagamento após o vencimento."""
    d = df.copy()
    d["multa_rs"] = d["multa_rs"].fillna(0.0)
    d["juros_rs"] = d["juros_rs"].fillna(0.0)
    d["com_encargo"] = (d["multa_rs"] + d["juros_rs"]) > 0
    tabela = d.groupby("uc").agg(
        faturas=("mes_ref", "count"), com_encargo=("com_encargo", "sum"),
        multa_rs=("multa_rs", "sum"), juros_rs=("juros_rs", "sum"),
    ).reset_index()
    tabela["unidade"] = tabela["uc"].map(lambda uc: nomes.get(uc, uc))
    tabela["encargos_rs"] = tabela["multa_rs"] + tabela["juros_rs"]
    tabela["pct_faturas"] = 100 * tabela["com_encargo"] / tabela["faturas"]
    return tabela.sort_values("encargos_rs", ascending=False).reset_index(drop=True)
