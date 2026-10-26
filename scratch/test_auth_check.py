import sys, os
sys.path.insert(0, os.path.abspath("."))
from playwright.sync_api import sync_playwright
from solar.equatorial import _obter_contexto, esta_autenticado_na_pagina

with sync_playwright() as p:
    ctx = _obter_contexto(p, headless=False)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto('https://agenciavirtual.equatorialenergia.com.br/SegundaVia/', timeout=45000)
    page.wait_for_timeout(5000)
    print("Page URL:", page.url)
    print("Page Title:", page.title())
    print("esta_autenticado_na_pagina:", esta_autenticado_na_pagina(page))
    
    btn_login = page.locator(".btn-login, button:has-text('Entrar')")
    print("btn_login count:", btn_login.count())
    for i in range(btn_login.count()):
        print(f"  btn {i}: visible={btn_login.nth(i).is_visible()}, text={btn_login.nth(i).inner_text().strip()}")
    
    # Check for Sair or other logged-in indicators
    sair = page.locator("text='Sair', text='Olá', [title*='Sair']").all()
    print("Sair/Ola elements:", len(sair))
    
    # Check localStorage cognito
    is_cognito = page.evaluate("() => Object.keys(localStorage).some(k => k.includes('CognitoIdentityServiceProvider') && k.endsWith('.refreshToken'))")
    print("Cognito refreshToken in localStorage:", is_cognito)
    
    ctx.close()
