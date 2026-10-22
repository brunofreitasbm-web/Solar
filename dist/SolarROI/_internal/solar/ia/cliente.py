"""Cliente agnóstico de IA (DeepSeek, Google Gemini e Anthropic Claude) com fallback local."""

import json
import os
from typing import Generator

import requests

from solar.db import conexao
from solar.ia import ferramentas

PROMPT_SISTEMA = """Você é o Consultor Sênior de Inteligência Artificial do sistema Solar ROI.
Sua especialidade é o setor elétrico brasileiro (Marco Legal da Geração Distribuída - Lei 14.300/2022, Resoluções da ANEEL e faturas da Equatorial Energia Pará).
Seu objetivo é apoiar o gestor em decisões financeiras, operacionais e de expansão das usinas solares.

Diretrizes:
- Seja analítico, direto e objetivo. Entregue conclusões claras e números fundamentados.
- Ao responder sobre expansão, avalie a data de ruptura de demanda, payback, VPL e TIR.
- Ao responder sobre financiamento, avalie o custo de oportunidade (taxa de juros do contrato vs rendimento no CDI).
- Ao responder sobre compensação e faturas, considere a regra de transição do Fio B (GD1 vs GD2/GD3) e a franquia mínima (custo de disponibilidade trifásico = 100 kWh).
- Se faltarem dados específicos, informe o que é preciso cadastrar no sistema.
"""


def _buscar_chave_banco(chave_nome: str) -> str:
    try:
        with conexao() as con:
            linha = con.execute("SELECT valor FROM config WHERE chave = ?", (chave_nome,)).fetchone()
            return linha["valor"].strip() if linha and linha["valor"] else ""
    except Exception:
        return ""


def obter_chave_configurada() -> tuple[str, str]:
    """Retorna (provedor, chave). Provedores possíveis: 'deepseek', 'gemini', 'anthropic' ou ('', '')."""
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "").strip() or _buscar_chave_banco("deepseek_api_key")
    if deepseek_key:
        return ("deepseek", deepseek_key)

    gemini_key = os.getenv("GEMINI_API_KEY", "").strip() or _buscar_chave_banco("gemini_api_key")
    if gemini_key:
        return ("gemini", gemini_key)

    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip() or _buscar_chave_banco("anthropic_api_key")
    if anthropic_key:
        return ("anthropic", anthropic_key)

    return ("", "")


def salvar_chave(provedor: str, chave: str) -> None:
    chave_coluna = f"{provedor.lower()}_api_key"
    with conexao() as con:
        con.execute(
            "INSERT OR REPLACE INTO config (chave, valor) VALUES (?, ?)",
            (chave_coluna, chave.strip()),
        )


def _montar_contexto_dados() -> str:
    resumo = ferramentas.obter_resumo_sistema()
    exp = ferramentas.analisar_expansao_demanda()
    quit = ferramentas.analisar_decisao_quitacao()
    anom = ferramentas.auditar_anomalias_faturas()

    return f"""
DADOS REAIS DO SISTEMA SOLAR:
- Resumo Operacional: {json.dumps(resumo, ensure_ascii=False)}
- Projeção de Demanda e Expansão: {json.dumps(exp, ensure_ascii=False)}
- Financiamento e Quitação: {json.dumps(quit, ensure_ascii=False)}
- Auditoria e Anomalias: {json.dumps(anom, ensure_ascii=False)}
"""


def responder_pergunta(pergunta: str, historico: list[dict[str, str]] | None = None) -> Generator[str, None, None]:
    """Responde à dúvida do usuário via API externa ou pelo motor heurístico local."""
    provedor, chave = obter_chave_configurada()
    contexto = _montar_contexto_dados()

    if provedor == "deepseek":
        yield from _chamar_deepseek(pergunta, chave, contexto, historico)
    elif provedor == "gemini":
        yield from _chamar_gemini(pergunta, chave, contexto, historico)
    elif provedor == "anthropic":
        yield from _chamar_anthropic(pergunta, chave, contexto, historico)
    else:
        yield from _resposta_local_heuristica(pergunta)


def _chamar_deepseek(
    pergunta: str, chave: str, contexto: str, historico: list[dict[str, str]] | None
) -> Generator[str, None, None]:
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {chave}",
        "Content-Type": "application/json",
    }

    mensagens = [{"role": "system", "content": PROMPT_SISTEMA}]
    if historico:
        for msg in historico[-6:]:
            if msg.get("role") in ("user", "assistant"):
                mensagens.append({"role": msg["role"], "content": msg["content"]})

    prompt_final = f"{contexto}\n\nPERGUNTA DO USUÁRIO:\n{pergunta}"
    mensagens.append({"role": "user", "content": prompt_final})

    payload = {
        "model": "deepseek-chat",
        "messages": mensagens,
        "temperature": 0.2,
        "stream": True,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, stream=True, timeout=30)
        if resp.status_code != 200:
            yield f"⚠️ Erro ao consultar a API do DeepSeek ({resp.status_code}): {resp.text}\n\n"
            yield from _resposta_local_heuristica(pergunta)
            return

        for linha in resp.iter_lines():
            if not linha:
                continue
            linha_texto = linha.decode("utf-8")
            if linha_texto.startswith("data: "):
                dados_raw = linha_texto[6:].strip()
                if dados_raw == "[DONE]":
                    break
                try:
                    chunk = json.loads(dados_raw)
                    delta = chunk["choices"][0].get("delta", {})
                    conteudo = delta.get("content", "")
                    if conteudo:
                        yield conteudo
                except Exception:
                    continue
    except Exception as erro:
        yield f"⚠️ Falha de conexão com a API DeepSeek ({erro}). Alternando para análise local:\n\n"
        yield from _resposta_local_heuristica(pergunta)


def _chamar_gemini(
    pergunta: str, chave: str, contexto: str, historico: list[dict[str, str]] | None
) -> Generator[str, None, None]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={chave}"

    contents = []
    if historico:
        for msg in historico[-6:]:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    prompt_final = f"{contexto}\n\nPERGUNTA DO USUÁRIO:\n{pergunta}"
    contents.append({"role": "user", "parts": [{"text": prompt_final}]})

    payload = {
        "systemInstruction": {"parts": [{"text": PROMPT_SISTEMA}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048},
    }

    try:
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code != 200:
            yield f"⚠️ Erro ao consultar a API do Gemini ({resp.status_code}): {resp.text}\n\n"
            yield from _resposta_local_heuristica(pergunta)
            return

        dados = resp.json()
        texto = dados["candidates"][0]["content"]["parts"][0]["text"]
        yield texto
    except Exception as erro:
        yield f"⚠️ Falha de conexão com a API ({erro}). Alternando para análise local:\n\n"
        yield from _resposta_local_heuristica(pergunta)


def _chamar_anthropic(
    pergunta: str, chave: str, contexto: str, historico: list[dict[str, str]] | None
) -> Generator[str, None, None]:
    try:
        import anthropic

        cliente = anthropic.Anthropic(api_key=chave)
        mensagens = []
        if historico:
            for msg in historico[-6:]:
                mensagens.append({"role": msg["role"], "content": msg["content"]})

        prompt_final = f"{contexto}\n\nPERGUNTA DO USUÁRIO:\n{pergunta}"
        mensagens.append({"role": "user", "content": prompt_final})

        with cliente.messages.stream(
            model="claude-3-5-haiku-20241022",
            max_tokens=2048,
            system=PROMPT_SISTEMA,
            messages=mensagens,
        ) as stream:
            for chunk in stream.text_stream:
                yield chunk
    except Exception as erro:
        yield f"⚠️ Falha de chamada à Anthropic ({erro}). Alternando para análise local:\n\n"
        yield from _resposta_local_heuristica(pergunta)


def _resposta_local_heuristica(pergunta: str) -> Generator[str, None, None]:
    p = pergunta.lower()
    if any(termo in p for termo in ["expans", "ampli", "crescimento", "ruptura", "faltar", "kwp"]):
        exp = ferramentas.analisar_expansao_demanda()
        if exp.get("status") == "ok":
            sim = exp["simulacao_ampliacao"]
            texto = (
                f"### 📈 Parecer de Expansão e Demanda\n\n"
                f"- **Diagnóstico:** {exp['diagnostico_ruptura']}\n"
                f"- **Consumo Médio:** {exp['demanda_atual_kwh_mes']:,.0f} kWh/mês para geração de {exp['producao_atual_kwh_mes']:,.0f} kWh/mês.\n"
                f"- **Tendência de Crescimento:** {exp['crescimento_anual_kwh']:,.0f} kWh/mês a cada ano.\n\n"
                f"**Recomendação de Dimensionamento:**\n"
                f"- Ampliação sugerida: **+{sim['kwp_adicionado']} kWp**\n"
                f"- Investimento estimado (CAPEX): **R$ {sim['capex_estimado_rs']:,.2f}**\n"
                f"- Payback estimado: **{sim['payback_anos']} anos** ({sim['payback_meses']} meses)\n"
                f"- VPL em 25 anos: **R$ {sim['vpl_25_anos_rs']:,.2f}** (TIR de {sim['tir_anual_pct']}% a.a.)\n"
            )
            yield texto
        else:
            yield "Dados de faturas insuficientes para projetar a curva de expansão."

    elif any(termo in p for termo in ["quit", "financi", "amortiz", "cdi", "parcel"]):
        quit = ferramentas.analisar_decisao_quitacao()
        if quit.get("status") == "ok":
            texto = (
                f"### 🏦 Análise de Quitação vs CDI\n\n"
                f"- **Saldo Devedor Atual:** R$ {quit['saldo_devedor_rs']:,.2f}\n"
                f"- **Parcelas Restantes:** {quit['parcelas_restantes']}x de R$ {quit['parcela_atual_rs']:,.2f}\n"
                f"- **Taxa de Juros do Contrato:** {quit['taxa_contrato_anual_pct']}% ao ano\n"
                f"- **Rendimento Líquido no CDI:** {quit['cdi_liquido_anual_pct']}% ao ano\n"
                f"- **Economia Bruta de Juros se quitar hoje:** R$ {quit['juros_economizados_quitando_rs']:,.2f}\n\n"
                f"💡 **Recomendação:** {quit['recomendacao']}\n"
            )
            yield texto
        else:
            yield "Não há financiamento ativo configurado no sistema em Configurações."

    elif any(termo in p for termo in ["anomalia", "atraso", "multa", "problema", "auditoria"]):
        anom = ferramentas.auditar_anomalias_faturas()
        if anom.get("total_anomalias", 0) > 0:
            yield "### ⚠️ Anomalias Detectadas nas Faturas\n\n"
            for a in anom["anomalias"]:
                yield f"- **{a['tipo']}:** {a['descricao']}\n"
        else:
            yield "✅ Nenhuma cobrança indevida ou queda anômala detectada nas faturas registradas."

    else:
        yield ferramentas.gerar_relatorio_executivo_markdown()
