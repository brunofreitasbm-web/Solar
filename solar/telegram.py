"""Aviso por Telegram quando uma fatura entra no histórico: valor, Pix e linha digitável da unidade."""

import html
import os
from dataclasses import dataclass
from datetime import date, datetime

import requests

from solar import unidades
from solar.db import conexao
from solar.faturas.modelo import Fatura

API_URL = "https://api.telegram.org/bot{token}/{metodo}"
TIMEOUT_SEGUNDOS = 15
CHAVE_TOKEN, CHAVE_CHAT, CHAVE_ATIVO = "telegram_bot_token", "telegram_chat_id", "telegram_ativo"


class FalhaTelegram(Exception):
    """Erro de envio já traduzido para uma mensagem que o usuário entende."""


@dataclass
class ConfigTelegram:
    token: str = ""
    chat_id: str = ""
    ativo: bool = False

    @property
    def pronto(self) -> bool:
        return bool(self.token and self.chat_id)


def _ler(chave: str) -> str:
    with conexao() as con:
        linha = con.execute("SELECT valor FROM config WHERE chave = ?", (chave,)).fetchone()
    return linha["valor"].strip() if linha else ""


def carregar() -> ConfigTelegram:
    return ConfigTelegram(
        token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or _ler(CHAVE_TOKEN),
        chat_id=_ler(CHAVE_CHAT),
        ativo=_ler(CHAVE_ATIVO) == "1",
    )


def salvar(cfg: ConfigTelegram) -> None:
    with conexao() as con:
        con.executemany(
            "INSERT OR REPLACE INTO config (chave, valor) VALUES (?, ?)",
            [(CHAVE_TOKEN, cfg.token.strip()), (CHAVE_CHAT, cfg.chat_id.strip()), (CHAVE_ATIVO, "1" if cfg.ativo else "0")],
        )


def _brl(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _data_br(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%d/%m/%Y") if iso else "não informado"


def montar_mensagem(fatura: Fatura, nome_unidade: str, endereco: str = "") -> str:
    ano, mes = fatura.mes_ref.split("-")
    linhas = [
        "<b>Fatura Equatorial fechada</b>",
        f"<b>{html.escape(nome_unidade)}</b> · UC {html.escape(fatura.uc)}",
    ]
    if endereco:
        linhas.append(html.escape(endereco))
    linhas += [
        f"Referência {mes}/{ano} · vence {_data_br(fatura.vencimento)}",
        f"Valor: <b>{_brl(fatura.total_rs)}</b>",
    ]
    if fatura.pix_copia_cola:
        linhas += ["", "Pix copia e cola (toque para copiar):", f"<code>{html.escape(fatura.pix_copia_cola)}</code>"]
    if fatura.codigo_barras:
        linhas += ["", "Código de barras (linha digitável):", f"<code>{html.escape(fatura.codigo_barras)}</code>"]
    if not (fatura.pix_copia_cola or fatura.codigo_barras):
        linhas += ["", "A fatura não trouxe Pix nem código de barras legíveis. Pegue na Agência Virtual."]
    return "\n".join(linhas)


def _chamar(token: str, metodo: str, dados: dict) -> dict:
    try:
        resposta = requests.post(API_URL.format(token=token, metodo=metodo), json=dados, timeout=TIMEOUT_SEGUNDOS)
        corpo = resposta.json()
    except requests.RequestException as erro:
        raise FalhaTelegram("Sem conexão com o Telegram. Confira a internet e tente de novo.") from erro
    except ValueError as erro:
        raise FalhaTelegram("O Telegram respondeu algo inesperado. Tente de novo em instantes.") from erro
    if not corpo.get("ok"):
        if resposta.status_code in (401, 404):
            raise FalhaTelegram("Token do bot inválido. Copie de novo o token que o @BotFather enviou.")
        raise FalhaTelegram(f"O Telegram recusou o envio: {corpo.get('description', 'motivo não informado')}. "
                            "Se for 'chat not found', abra o bot e envie /start antes.")
    return corpo


def enviar(texto: str, cfg: ConfigTelegram | None = None) -> None:
    cfg = cfg or carregar()
    if not cfg.pronto:
        raise FalhaTelegram("Informe o token do bot e o ID do chat para enviar mensagens.")
    _chamar(cfg.token, "sendMessage", {"chat_id": cfg.chat_id, "text": texto, "parse_mode": "HTML",
                                       "disable_web_page_preview": True})


def descobrir_chat_id(token: str) -> str:
    """Pega o chat da última mensagem recebida pelo bot — evita o usuário procurar o ID na mão."""
    atualizacoes = _chamar(token, "getUpdates", {"limit": 20}).get("result", [])
    for item in reversed(atualizacoes):
        chat = (item.get("message") or item.get("channel_post") or {}).get("chat")
        if chat:
            return str(chat["id"])
    raise FalhaTelegram("Nenhuma conversa encontrada. Abra o bot no Telegram, envie /start e tente de novo.")


def _ja_enviada(uc: str, mes: str) -> bool:
    with conexao() as con:
        return con.execute("SELECT 1 FROM telegram_enviados WHERE uc = ? AND mes_ref = ?", (uc, mes)).fetchone() is not None


def _registrar_envio(uc: str, mes: str) -> None:
    with conexao() as con:
        con.execute("INSERT OR REPLACE INTO telegram_enviados (uc, mes_ref, enviado_em) VALUES (?, ?, ?)",
                    (uc, mes, datetime.now().isoformat(timespec="seconds")))


def notificar_fatura(fatura: Fatura) -> bool:
    """Envia a fatura uma única vez por UC/mês. Nunca levanta erro: falha no Telegram não pode
    impedir a importação. Devolve True só quando a mensagem foi enviada agora."""
    try:
        cfg = carregar()
        if not (cfg.ativo and cfg.pronto) or _ja_enviada(fatura.uc, fatura.mes_ref):
            return False
        unidade = next((u for u in unidades.listar() if u.uc == fatura.uc), None)
        nome = unidade.nome if unidade else f"UC {fatura.uc}"
        enviar(montar_mensagem(fatura, nome, (unidade.endereco if unidade else "") or fatura.endereco), cfg)
        _registrar_envio(fatura.uc, fatura.mes_ref)
        return True
    except Exception:
        return False
