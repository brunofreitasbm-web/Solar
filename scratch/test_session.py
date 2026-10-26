import sys, os
sys.path.insert(0, os.path.abspath("."))
from playwright.sync_api import sync_playwright
from solar.equatorial import _obter_contexto, esta_autenticado_na_pagina

with sync_playwright() as p:
    ctx = _obter_contexto(p, headless=False)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto('https://agenciavirtual.equatorialenergia.com.br/', timeout=45000)
    page.wait_for_timeout(5000)
    print('Current URL:', page.url)
    print('Title:', page.title())
    print('esta_autenticado:', esta_autenticado_na_pagina(page))
    btn_login = page.locator(".btn-login, button:has-text('Entrar')")
    print('btn_login count:', btn_login.count())
    for i in range(btn_login.count()):
        print(f'btn {i} visible:', btn_login.nth(i).is_visible())
    ctx.close()
