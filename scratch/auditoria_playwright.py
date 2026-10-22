"""Auditoria em tempo real com Playwright no app Streamlit Solar ROI."""

import sys
import time
from playwright.sync_api import sync_playwright

URL_BASE = "http://localhost:8501"


def auditar():
    erros_console = []
    erros_pagina = []
    falhas_streamlit = []

    print(f"[*] Iniciando Playwright para auditar {URL_BASE}...", flush=True)
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=True)
            print("[*] Usando Microsoft Edge do sistema.", flush=True)
        except Exception:
            try:
                browser = p.chromium.launch(channel="chrome", headless=True)
                print("[*] Usando Google Chrome do sistema.", flush=True)
            except Exception:
                browser = p.chromium.launch(headless=True)
                print("[*] Usando Chromium padrão.", flush=True)

        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        def on_console(msg):
            if msg.type == "error":
                erros_console.append(f"[{msg.type.upper()}] {msg.text}")
                print(f"  [CONSOLE ERROR] {msg.text}", flush=True)

        def on_page_error(exc):
            erros_pagina.append(str(exc))
            print(f"  [PAGE ERROR] {exc}", flush=True)

        page.on("console", on_console)
        page.on("pageerror", on_page_error)

        # 1. Carrega a página inicial
        print("[*] Carregando página inicial...", flush=True)
        page.goto(URL_BASE, timeout=60000)
        page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=30000)
        time.sleep(2)
        page.screenshot(path="scratch/screenshot_inicio.png")
        print("  [OK] Página inicial carregada. Screenshot salvo em scratch/screenshot_inicio.png", flush=True)

        # Verifica se há exceção na tela inicial
        exceptions = page.locator('[data-testid="stException"]').all_text_contents()
        if exceptions:
            for exc in exceptions:
                falhas_streamlit.append(f"Tela Inicial: {exc}")
                print(f"  [FALHA INICIAL] {exc}", flush=True)
        else:
            print("  [OK] Tela inicial sem falhas.", flush=True)

        # 2. Navega para o Consultor IA
        print("[*] Acessando 'Consultor IA' (via rota /consultor-ia)...", flush=True)
        page.goto(f"{URL_BASE}/consultor-ia", timeout=30000)
        page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=15000)
        try:
            page.wait_for_selector('button:has-text("Diagnóstico Completo")', timeout=60000)
        except Exception:
            print("  [AVISO] Conteúdo do Consultor IA não renderizou em 60s.", flush=True)
        time.sleep(1)
        page.screenshot(path="scratch/screenshot_consultor_ia.png")
        print("  [OK] Página Consultor IA aberta. Screenshot em scratch/screenshot_consultor_ia.png", flush=True)

        # Verifica status de API e exceções
        exceptions_ia = page.locator('[data-testid="stException"]').all_text_contents()
        if exceptions_ia:
            for exc in exceptions_ia:
                falhas_streamlit.append(f"Consultor IA: {exc}")
                print(f"  [FALHA Consultor IA] {exc}", flush=True)
        else:
            print("  [OK] Consultor IA renderizou sem exceções.", flush=True)

        # Verifica texto de status
        status_text = page.locator('text="API Conectada"').all_text_contents()
        if status_text:
            print(f"  [STATUS DETECTADO] {status_text[0]}", flush=True)

        # Testa clicar na ação rápida "📊 Diagnóstico Completo"
        btn_diag = page.locator('button:has-text("Diagnóstico Completo")')
        if btn_diag.count() > 0:
            print("[*] Clicando em '📊 Diagnóstico Completo'...", flush=True)
            btn_diag.first.click()
            time.sleep(4)
            page.screenshot(path="scratch/screenshot_diagnostico.png")
            exceptions_diag = page.locator('[data-testid="stException"]').all_text_contents()
            if exceptions_diag:
                for exc in exceptions_diag:
                    falhas_streamlit.append(f"Diagnóstico Completo: {exc}")
                    print(f"  [FALHA NO DIAGNÓSTICO] {exc}", flush=True)
            else:
                print("  [OK] Diagnóstico Completo gerado com sucesso!", flush=True)

        # Pergunta livre no chat
        chat = page.locator('[data-testid="stChatInputTextArea"]')
        if chat.count() > 0:
            print("[*] Enviando pergunta no chat...", flush=True)
            chat.first.fill("Qual a potencia total instalada?")
            chat.first.press("Enter")
            time.sleep(15)
            page.screenshot(path="scratch/screenshot_chat.png")
            excs = page.locator('[data-testid="stException"]').all_text_contents()
            for e in excs:
                falhas_streamlit.append(f"Chat: {e}")
                print(f"  [FALHA NO CHAT] {e}", flush=True)
            if not excs:
                print("  [OK] Chat respondeu sem excecoes.", flush=True)

        # 3. Testa navegação nas principais abas
        rotas_principais = ["Dashboard", "Simulador", "Configurações", "Unidades"]
        for rota in rotas_principais:
            print(f"[*] Navegando para '{rota}'...", flush=True)
            link = page.locator(f'text="{rota}"')
            if link.count() > 0:
                try:
                    link.first.click()
                    time.sleep(2)
                    excs = page.locator('[data-testid="stException"]').all_text_contents()
                    if excs:
                        for e in excs:
                            msg = f"Rota '{rota}': {e}"
                            falhas_streamlit.append(msg)
                            print(f"  [FALHA NA ROTA] {msg}", flush=True)
                    else:
                        print(f"  [OK] Rota '{rota}' sem erros.", flush=True)
                except Exception as e:
                    print(f"  [ERRO AO CLICAR] {rota}: {e}", flush=True)

        browser.close()

    print("\n" + "=" * 55, flush=True)
    print("RESUMO DA AUDITORIA PLAYWRIGHT EM TEMPO REAL:", flush=True)
    print(f"- Exceções do Streamlit (stException): {len(falhas_streamlit)}", flush=True)
    print(f"- Erros não tratados de JS (Page Error): {len(erros_pagina)}", flush=True)
    print(f"- Erros de console do navegador: {len(erros_console)}", flush=True)
    if falhas_streamlit:
        print("\nFalhas detectadas no Streamlit:", flush=True)
        for f in falhas_streamlit:
            print(f"  [FALHA] {f}", flush=True)
    else:
        print("[SUCESSO] Nenhuma excecao ou quebra de renderizacao detectada no Streamlit!", flush=True)
    print("=" * 55, flush=True)


if __name__ == "__main__":
    auditar()
