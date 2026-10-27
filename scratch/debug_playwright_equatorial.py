import sys
import os
sys.path.insert(0, os.path.abspath("."))
import time
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from solar.equatorial import (
    _obter_contexto,
    URL_AGENCIA,
    URL_SEGUNDA_VIA,
    PASTA_PERFIL,
    esta_autenticado_na_pagina,
    esta_autenticado_no_contexto,
)

scratch_dir = Path("scratch")
scratch_dir.mkdir(exist_ok=True)

print("--- INICIANDO DEBUG PLAYWRIGHT EQUATORIAL ---")

with sync_playwright() as p:
    ctx = _obter_contexto(p, headless=False)
    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        
        # Monitora respostas
        def on_response(response):
            if "incapsula" in response.url.lower() or response.status >= 400:
                print(f"[HTTP {response.status}] {response.url[:90]}")
        page.on("response", on_response)
        
        # 1. Passo: Agência Virtual Raiz
        print(f"\n[PASSO 1] Acessando {URL_AGENCIA}...")
        page.goto(URL_AGENCIA, timeout=45000)
        page.wait_for_timeout(4000)
        page.screenshot(path="scratch/debug_step1_agencia.png")
        print(f"URL: {page.url}")
        print(f"Title: {page.title()}")
        print(f"Autenticado na página: {esta_autenticado_na_pagina(page)}")
        print(f"Autenticado no contexto: {esta_autenticado_no_contexto(ctx)}")
        
        # Checa cookies
        cookies = ctx.cookies()
        incap_cookies = [c['name'] for c in cookies if 'incap' in c['name'].lower() or 'visid' in c['name'].lower()]
        print(f"Cookies de segurança detectados: {incap_cookies}")
        
        # Checa iframes
        for i, frame in enumerate(page.frames):
            print(f"Frame {i}: URL={frame.url[:80]} Title='{frame.title()}'")
            if "incapsula" in frame.url.lower():
                print(f"  --> Frame Incapsula detectado! Texto: {frame.inner_text('body')[:150]}")
                
        # 2. Passo: Segunda Via
        print(f"\n[PASSO 2] Acessando {URL_SEGUNDA_VIA}...")
        page.goto(URL_SEGUNDA_VIA, timeout=45000)
        page.wait_for_timeout(5000)
        page.screenshot(path="scratch/debug_step2_segundavia.png")
        print(f"URL atual: {page.url}")
        print(f"Title atual: {page.title()}")
        print(f"Autenticado: {esta_autenticado_na_pagina(page)}")
        
        # Checa elementos de login ou de download
        botoes = page.locator("button, a, input").all()
        print(f"Total de elementos interativos: {len(botoes)}")
        textos = []
        for b in botoes[:30]:
            try:
                t = b.inner_text().strip().replace('\n', ' ')
                if t and len(t) < 40 and t not in textos:
                    textos.append(t)
            except Exception:
                pass
        print(f"Amostra de botões/links: {textos[:15]}")
        
        # Procura botões de fatura
        faturas = page.locator("button:has-text('Baixar'), a:has-text('Baixar'), button:has-text('PDF'), a:has-text('PDF'), .btn-download")
        print(f"Botões de download encontrados: {faturas.count()}")

    finally:
        ctx.close()
        print("\n--- FIM DO DIAGNÓSTICO ---")
