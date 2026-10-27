import sys
import os
sys.path.insert(0, os.path.abspath("."))
from playwright.sync_api import sync_playwright
from solar.equatorial import _obter_contexto, URL_AGENCIA, URL_SEGUNDA_VIA, esta_autenticado_na_pagina

with sync_playwright() as p:
    ctx = _obter_contexto(p, headless=False)
    # Purga cookies do Incapsula manchados
    cookies = ctx.cookies()
    novos_cookies = [c for c in cookies if not any(c['name'].lower().startswith(pfx) for pfx in ['incap', 'visid_incap', 'nlbi', '_incap'])]
    ctx.clear_cookies()
    if novos_cookies:
        ctx.add_cookies(novos_cookies)
        
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(URL_AGENCIA, timeout=45000)
    page.wait_for_timeout(4000)
    print("Passo 1 OK. Indo para Segunda Via...")
    
    page.goto(URL_SEGUNDA_VIA, timeout=45000)
    page.wait_for_timeout(5000)
    print("Segunda Via URL:", page.url)
    print("Segunda Via Title:", page.title())
    
    botoes_baixar = page.locator("button:has-text('Baixar'), a:has-text('Baixar'), button:has-text('PDF'), a:has-text('PDF'), .btn-download, [title*='fatura'], [title*='Fatura']").all()
    print("Botões de fatura encontrados:", len(botoes_baixar))
    
    page.screenshot(path="scratch/segundavia_autenticado.png")
    print("Screenshot salvo em scratch/segundavia_autenticado.png")
    ctx.close()
