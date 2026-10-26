import sys, os
sys.path.insert(0, os.path.abspath("."))
from playwright.sync_api import sync_playwright
from solar.equatorial import _obter_contexto, esta_autenticado_na_pagina

with sync_playwright() as p:
    ctx = _obter_contexto(p, headless=False)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto('https://agenciavirtual.equatorialenergia.com.br/SegundaVia/', timeout=45000)
    page.wait_for_timeout(4000)
    
    print("Page URL:", page.url)
    print("Page Title:", page.title())
    print("esta_autenticado_na_pagina:", esta_autenticado_na_pagina(page))
    
    # Check buttons and links
    elements = page.locator("button, a, input, [role='button']").all()
    print(f"Total interactive elements: {len(elements)}")
    for el in elements:
        try:
            if el.is_visible():
                text = el.inner_text().strip().replace("\n", " ")
                cls = el.get_attribute("class") or ""
                id_ = el.get_attribute("id") or ""
                href = el.get_attribute("href") or ""
                if text or href:
                    print(f"[{el.evaluate('e => e.tagName')}] id='{id_}' class='{cls}' text='{text[:40]}' href='{href[:40]}'")
        except:
            pass
    ctx.close()
