"""Ferramentas matemáticas e consultas locais ao SQLite para subsidiar a IA."""

from datetime import date
from typing import Any

import pandas as pd

from solar import configuracoes, economia, expansao, financiamento, rateio, unidades
from solar.faturas import repositorio
from solar.tarifa import aneel


def _obter_tarifa_rapida(cfg) -> tuple[float, float]:
    """Retorna (tusd, tarifa_com_tributos) usando cache local ou padrão sem travar a rede."""
    try:
        from solar.db import ler_cache
        cache = ler_cache("tarifa_aneel_b1")
        if cache:
            dados, _ = cache
            te = float(dados.get("te_kwh", 0.45))
            tusd = float(dados.get("tusd_kwh", 0.35))
            padrao = (te + tusd) / (1 - cfg.icms - cfg.pis_cofins)
            return (tusd, padrao)
    except Exception:
        pass
    return (0.35, 0.95)


def obter_resumo_sistema() -> dict[str, Any]:
    """Coleta o panorama consolidado do parque solar atual."""
    lista_ucs = unidades.listar()
    df = repositorio.tabela()
    cfg = configuracoes.carregar()

    if df.empty:
        return {
            "status": "sem_dados",
            "mensagem": "Nenhuma fatura cadastrada no sistema ainda.",
        }

    tusd, tarifa_media = _obter_tarifa_rapida(cfg)

    df_eco = economia.tabela_economia(df, tusd, tarifa_media)
    resumo_mes = economia.resumo_mensal(df_eco)

    geradoras = [u for u in lista_ucs if u.geradora]
    beneficiarias = [u for u in lista_ucs if not u.geradora]
    kwp_total = sum(u.kwp or 0.0 for u in geradoras)

    # Últimas faturas de cada UC
    ultimas = df.sort_values("mes_ref").groupby("uc").last()
    saldo_creditos_total = float(ultimas["saldo_creditos_kwh"].sum()) if not ultimas.empty else 0.0
    consumo_mensal_recente = float(ultimas["consumo_kwh"].sum()) if not ultimas.empty else 0.0
    injetado_mensal_recente = float(ultimas["injetado_kwh"].sum()) if not ultimas.empty else 0.0

    economia_total_rs = float(resumo_mes["economia_rs"].sum()) if not resumo_mes.empty else 0.0
    faturas_total_rs = float(resumo_mes["total_fatura_rs"].sum()) if not resumo_mes.empty else 0.0

    # Financiamento
    fin = {}
    if cfg.valor_financiado > 0 and cfg.parcela_mensal > 0:
        hoje = date.today()
        pagas = financiamento.parcelas_pagas(cfg, hoje)
        restantes = max(cfg.qtd_parcelas - pagas, 0)
        saldo_dev = financiamento.saldo_devedor(cfg, pagas)
        taxa_mes = financiamento.taxa_mensal(cfg) or 0.0
        fin = {
            "valor_financiado": cfg.valor_financiado,
            "parcela_mensal": cfg.parcela_mensal,
            "parcelas_pagas": pagas,
            "parcelas_restantes": restantes,
            "saldo_devedor": round(saldo_dev, 2),
            "taxa_juros_mensal_pct": round(taxa_mes * 100, 2),
            "taxa_juros_anual_pct": round(((1 + taxa_mes) ** 12 - 1) * 100, 2) if taxa_mes else 0.0,
        }

    return {
        "status": "ok",
        "ucs_totais": len(lista_ucs),
        "ucs_geradoras": len(geradoras),
        "ucs_beneficiarias": len(beneficiarias),
        "potencia_instalada_kwp": round(kwp_total, 2),
        "saldo_creditos_kwh": round(saldo_creditos_total, 0),
        "consumo_mensal_atual_kwh": round(consumo_mensal_recente, 0),
        "injetado_mensal_atual_kwh": round(injetado_mensal_recente, 0),
        "economia_acumulada_rs": round(economia_total_rs, 2),
        "gasto_faturas_acumulado_rs": round(faturas_total_rs, 2),
        "tarifa_media_kwh": round(tarifa_media, 4),
        "financiamento": fin,
    }


def analisar_expansao_demanda(
    kwp_adicional: float | None = None,
    capex_por_kwp: float = 3200.0,
    financiado: bool = False,
    juros_mensal: float = 0.015,
    parcelas: int = 48,
) -> dict[str, Any]:
    """Avalia o crescimento do consumo, data de ruptura e viabilidade de ampliação."""
    df = repositorio.tabela()
    if df.empty:
        return {"status": "sem_dados", "erro": "Faturas insuficientes para análise."}

    cfg = configuracoes.carregar()
    demanda = expansao.analisar_demanda(df, cfg.degradacao_anual)

    if not demanda:
        return {
            "status": "inconclusivo",
            "mensagem": "São necessários ao menos 6 meses de faturas para estimar tendência de expansão.",
        }

    # Se kwp_adicional não foi especificado, calcula o tamanho ideal para cobrir a tendência em 5 anos
    lacuna_5_anos = demanda.lacuna_em(60, cfg.degradacao_anual)
    rendimento_medio = 125.0  # kWh gerados por kWp/mês no Pará
    kwp_sugerido = kwp_adicional or max(round(lacuna_5_anos / rendimento_medio, 1), 5.0)

    sim = expansao.simular_expansao(
        kwp=kwp_sugerido,
        custo_por_kwp=capex_por_kwp,
        rendimento_kwh_kwp_mes=rendimento_medio,
        valor_kwh=0.95,
        reajuste_anual=cfg.reajuste_tarifa_anual,
        degradacao_anual=cfg.degradacao_anual,
        taxa_desconto_anual=0.10,
        juros_mensal=juros_mensal if financiado else None,
        parcelas=parcelas,
        entrada_pct=0.10 if financiado else 0.0,
    )

    return {
        "status": "ok",
        "producao_atual_kwh_mes": round(demanda.producao_kwh_mes, 0),
        "demanda_atual_kwh_mes": round(demanda.demanda_kwh_mes, 0),
        "crescimento_anual_kwh": round(demanda.crescimento_kwh_mes_por_ano, 0),
        "sobra_atual_kwh_mes": round(demanda.sobra_kwh_mes, 0),
        "meses_ate_faltar_energia": demanda.meses_ate_faltar,
        "diagnostico_ruptura": (
            "Capacidade atual já é deficitária." if demanda.meses_ate_faltar == 0 else
            f"Previsão de faltar geração em {demanda.meses_ate_faltar} meses." if demanda.meses_ate_faltar else
            "Geração atual atende a projeção para mais de 10 anos."
        ),
        "simulacao_ampliacao": {
            "kwp_adicionado": kwp_sugerido,
            "capex_estimado_rs": round(sim.capex, 2),
            "geracao_nova_kwh_mes": round(sim.kwh_mes, 0),
            "economia_primeiro_mes_rs": round(sim.economia_mes_inicial, 2),
            "payback_meses": sim.payback_meses,
            "payback_anos": round(sim.payback_meses / 12, 1) if sim.payback_meses else None,
            "vpl_25_anos_rs": round(sim.vpl, 2),
            "tir_anual_pct": round(sim.tir_anual * 100, 2) if sim.tir_anual else None,
            "financiado": financiado,
            "parcela_mensal_rs": round(sim.parcela_mensal, 2) if sim.parcela_mensal else None,
        },
    }


def analisar_decisao_quitacao(taxa_cdi_anual: float = 0.105) -> dict[str, Any]:
    """Compara amortizar o financiamento vs aplicar o capital no CDI."""
    cfg = configuracoes.carregar()
    if not (cfg.valor_financiado and cfg.parcela_mensal and cfg.qtd_parcelas):
        return {
            "status": "sem_financiamento",
            "mensagem": "Nenhum financiamento configurado no sistema.",
        }

    hoje = date.today()
    pagas = financiamento.parcelas_pagas(cfg, hoje)
    saldo_dev = financiamento.saldo_devedor(cfg, pagas)
    taxa_contrato_mes = financiamento.taxa_mensal(cfg) or 0.0
    taxa_contrato_ano = (1 + taxa_contrato_mes) ** 12 - 1

    sim_quitacao = financiamento.simular_amortizacao(cfg, saldo_dev, modo="prazo", hoje=hoje)

    # Rendimento do mesmo capital no CDI líquido (estimando 15% IR)
    cdi_liquido_ano = taxa_cdi_anual * 0.85
    spread_anual_pct = (taxa_contrato_ano - cdi_liquido_ano) * 100

    recomendacao = (
        "Recomenda-se quitar antecipadamente: o custo do financiamento é maior que o ganho no CDI."
        if taxa_contrato_ano > cdi_liquido_ano
        else "Vale a pena manter o financiamento e aplicar no CDI: o rendimento líquido supera os juros do contrato."
    )

    return {
        "status": "ok",
        "saldo_devedor_rs": round(saldo_dev, 2),
        "parcelas_restantes": cfg.qtd_parcelas - pagas,
        "parcela_atual_rs": cfg.parcela_mensal,
        "juros_economizados_quitando_rs": round(sim_quitacao.juros_economizados, 2),
        "taxa_contrato_anual_pct": round(taxa_contrato_ano * 100, 2),
        "cdi_liquido_anual_pct": round(cdi_liquido_ano * 100, 2),
        "spread_anual_pct": round(spread_anual_pct, 2),
        "recomendacao": recomendacao,
    }


def auditar_anomalias_faturas() -> dict[str, Any]:
    """Identifica cobranças suspeitas, multas e quedas atípicas de geração."""
    df = repositorio.tabela()
    if df.empty:
        return {"status": "sem_dados", "anomalias": []}

    anomalias = []
    # Multas e juros pagos
    if "multa_rs" in df.columns:
        multas = df[df["multa_rs"].fillna(0) > 0]
        if not multas.empty:
            total_multas = multas["multa_rs"].sum()
            anomalias.append({
                "tipo": "custo_atraso",
                "descricao": f"Foram pagos R$ {total_multas:.2f} em multas e juros por atraso em faturas.",
                "faturas_afetadas": len(multas),
            })

    # UCs geradoras com geração zero ou muito abaixo
    geradoras = [u.uc for u in unidades.listar() if u.geradora]
    if geradoras:
        df_ger = df[df["uc"].isin(geradoras)].sort_values("mes_ref")
        ultimas_ger = df_ger.groupby("uc").last()
        for uc, row in ultimas_ger.iterrows():
            if row.get("injetado_kwh", 0) <= 0:
                anomalias.append({
                    "tipo": "geracao_zerada",
                    "descricao": f"A UC geradora {uc} teve injeção zerada no último mês registrado ({row.get('mes_ref')}).",
                    "uc": str(uc),
                })

    return {
        "status": "ok",
        "total_anomalias": len(anomalias),
        "anomalias": anomalias,
    }


def gerar_relatorio_executivo_markdown() -> str:
    """Gera um parecer consolidado em Markdown com base nos dados e modelos locais."""
    resumo = obter_resumo_sistema()
    if resumo.get("status") == "sem_dados":
        return "### ⚠️ Dados Insuficientes\nNenhuma fatura cadastrada no sistema. Envie faturas para habilitar o consultor."

    exp = analisar_expansao_demanda()
    quit = analisar_decisao_quitacao()
    anom = auditar_anomalias_faturas()

    texto = []
    texto.append("## 📊 Diagnóstico Executivo de Energia Solar\n")
    texto.append(f"**Panorama Geral:** {resumo['ucs_totais']} Unidades ({resumo['ucs_geradoras']} Geradora(s), {resumo['ucs_beneficiarias']} Beneficiária(s)) com potência de **{resumo['potencia_instalada_kwp']} kWp**.")
    texto.append(f"- **Economia acumulada:** R$ {resumo['economia_acumulada_rs']:,.2f}")
    texto.append(f"- **Saldo atual de créditos:** {resumo['saldo_creditos_kwh']:,.0f} kWh")
    texto.append(f"- **Consumo mensal recente:** {resumo['consumo_mensal_atual_kwh']:,.0f} kWh | Injetado: {resumo['injetado_mensal_atual_kwh']:,.0f} kWh\n")

    texto.append("### 🚀 1. Expansão e Capacidade Futura")
    if exp.get("status") == "ok":
        texto.append(f"- **Status de Ruptura:** {exp['diagnostico_ruptura']}")
        texto.append(f"- **Consumo vs Geração:** Consumo médio de {exp['demanda_atual_kwh_mes']:,.0f} kWh/mês para geração de {exp['producao_atual_kwh_mes']:,.0f} kWh/mês.")
        sim = exp["simulacao_ampliacao"]
        texto.append(f"- **Simulação de Ampliação (+{sim['kwp_adicionado']} kWp):**")
        texto.append(f"  - Investimento estimado: R$ {sim['capex_estimado_rs']:,.2f}")
        texto.append(f"  - Payback estimado: **{sim['payback_anos']} anos** ({sim['payback_meses']} meses)")
        texto.append(f"  - Retorno em 25 anos (VPL): **R$ {sim['vpl_25_anos_rs']:,.2f}** (TIR de {sim['tir_anual_pct']}%)")
    else:
        texto.append("- Faturas históricas ainda insuficientes para estimar com precisão a tendência de expansão.")

    texto.append("\n### 🏦 2. Decisão de Quitação vs CDI")
    if quit.get("status") == "ok":
        texto.append(f"- **Saldo devedor:** R$ {quit['saldo_devedor_rs']:,.2f} em {quit['parcelas_restantes']} parcelas de R$ {quit['parcela_atual_rs']:,.2f}.")
        texto.append(f"- **Custo do financiamento:** {quit['taxa_contrato_anual_pct']}% a.a. vs **CDI Líquido:** {quit['cdi_liquido_anual_pct']}% a.a.")
        texto.append(f"- **Economia de juros se quitar hoje:** R$ {quit['juros_economizados_quitando_rs']:,.2f}")
        texto.append(f"- **Conclusão:** {quit['recomendacao']}")
    else:
        texto.append("- Nenhum financiamento em aberto cadastrado em Configurações.")

    texto.append("\n### 🔍 3. Auditoria de Custos e Anomalias")
    if anom.get("total_anomalias", 0) > 0:
        for a in anom["anomalias"]:
            texto.append(f"- ⚠️ **{a['tipo']}:** {a['descricao']}")
    else:
        texto.append("- Nenhuma anomalia grave detectada nas últimas faturas auditadas.")

    return "\n".join(texto)
