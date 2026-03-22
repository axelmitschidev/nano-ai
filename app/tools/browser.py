"""Browser tools — web search, reading, and interactive navigation."""

import time
import httpx
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
import html2text
from ddgs import DDGS
from app.tools import registry

_stealth = Stealth()
_session = {"pw": None, "browser": None, "context": None, "page": None}


# --- Browser lifecycle ---

def _ensure_browser():
    """Launch or reuse a persistent stealth browser."""
    if _session["page"] and not _session["page"].is_closed():
        return _session["page"]

    close_browser()

    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage", "--no-sandbox"],
    )
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
        locale="fr-FR",
        timezone_id="Europe/Paris",
    )
    _stealth.use_sync(context)
    page = context.new_page()

    _session.update(pw=pw, browser=browser, context=context, page=page)
    return page


def close_browser():
    """Shut down the browser and free all resources."""
    for key in ("context", "browser"):
        try:
            if _session[key]:
                _session[key].close()
        except Exception:
            pass
    try:
        if _session["pw"]:
            _session["pw"].stop()
    except Exception:
        pass
    _session.update(pw=None, browser=None, context=None, page=None)


# --- Helpers ---

def _to_markdown(html: str) -> str:
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = True
    converter.body_width = 0
    converter.skip_internal_links = True
    text = converter.handle(html)

    cleaned, empty = [], 0
    for line in text.split("\n"):
        if not line.strip():
            empty += 1
            if empty <= 2:
                cleaned.append("")
        else:
            empty = 0
            cleaned.append(line)
    return "\n".join(cleaned).strip()


def _get_elements(page) -> str:
    elements = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('a[href], button, input, select, textarea, [role="button"]')
            .forEach((el, i) => {
                if (!(el.offsetParent || el.offsetWidth > 0)) return;
                const tag = el.tagName.toLowerCase();
                const id = el.id, name = el.name || '', type = el.type || '';
                const text = (el.innerText || '').trim().substring(0, 60);
                const ph = el.placeholder || '', aria = el.getAttribute('aria-label') || '';
                const href = el.href || '';

                let sel = id ? '#'+id : name ? `${tag}[name="${name}"]`
                    : ph ? `${tag}[placeholder="${ph}"]` : aria ? `[aria-label="${aria}"]`
                    : text && tag !== 'input' ? `${tag}:has-text("${text.substring(0,40)}")`
                    : `${tag}:nth-of-type(${i+1})`;

                let desc = tag === 'input' || tag === 'textarea'
                    ? `[${tag}${type?' type='+type:''}] ${ph||name||id}`
                    : tag === 'a' ? `[link] ${text||aria} -> ${href.substring(0,50)}`
                    : `[${tag}] ${text||aria}`;

                out.push({sel, desc});
            });
        return out.slice(0, 50);
    }""")
    if not elements:
        return "No interactive elements found."
    return "\n".join(f"  {e['sel']}  →  {e['desc']}" for e in elements)


def _retry(fn, retries=2, delay=2):
    last_err = None
    for i in range(retries + 1):
        try:
            return fn()
        except Exception as e:
            last_err = e
            if i < retries:
                time.sleep(delay)
    return f"ERROR after {retries + 1} attempts: {last_err}"


# --- Tool functions ---

def web_search(query: str, max_results: int = 5) -> str:
    def _do():
        results = DDGS().text(query, max_results=max_results)
        if not results:
            return "No results found."
        return "\n\n".join(
            f"{i}. {r['title']}\n   {r['href']}\n   {r['body']}"
            for i, r in enumerate(results, 1)
        )
    return _retry(_do)


def web_read(url: str) -> str:
    def _do():
        try:
            res = httpx.get(url, timeout=10, follow_redirects=True, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            })
            if res.status_code == 200 and len(res.text) > 500:
                md = _to_markdown(res.text)
                if len(md) > 200:
                    return md[:4000] + "\n\n[... truncated ...]" if len(md) > 4000 else md
        except Exception:
            pass

        page = _ensure_browser()
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2000)
        page.evaluate("""
            ['nav','footer','header','.cookie-banner','#cookie-consent','.ad','.ads',
             '.sidebar','.menu','script','style','noscript','iframe']
            .forEach(s => document.querySelectorAll(s).forEach(el => el.remove()));
        """)
        md = _to_markdown(page.content())
        return md[:4000] + "\n\n[... truncated ...]" if len(md) > 4000 else md

    return _retry(_do)


def web_go(url: str) -> str:
    def _do():
        page = _ensure_browser()
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2000)
        return f"Page: {page.title()}\nURL: {page.url}\n\nElements:\n{_get_elements(page)}"
    return _retry(_do)


def web_click(selector: str) -> str:
    def _do():
        page = _ensure_browser()
        page.click(selector, timeout=5000)
        page.wait_for_timeout(1500)
        return f"Clicked. Page: {page.title()}\nURL: {page.url}\n\nElements:\n{_get_elements(page)}"
    return _retry(_do)


def web_type(selector: str, text: str) -> str:
    def _do():
        page = _ensure_browser()
        page.fill(selector, text, timeout=5000)
        return f"Typed '{text}' into {selector}."
    return _retry(_do)


# --- Registration ---

def register_tools():
    registry.register("web_search", web_search,
        "Search the internet. Returns titles, URLs, and snippets.",
        {"type": "object", "properties": {
            "query": {"type": "string", "description": "Search query"},
        }, "required": ["query"]})

    registry.register("web_read", web_read,
        "Read a web page and return its content as clean markdown.",
        {"type": "object", "properties": {
            "url": {"type": "string", "description": "URL to read"},
        }, "required": ["url"]})

    registry.register("web_go", web_go,
        "Navigate to a URL and list interactive elements. Use this to interact with websites.",
        {"type": "object", "properties": {
            "url": {"type": "string", "description": "URL to navigate to"},
        }, "required": ["url"]})

    registry.register("web_click", web_click,
        "Click an element on the current page.",
        {"type": "object", "properties": {
            "selector": {"type": "string", "description": "CSS selector of element to click"},
        }, "required": ["selector"]})

    registry.register("web_type", web_type,
        "Type text into a form field on the current page.",
        {"type": "object", "properties": {
            "selector": {"type": "string", "description": "CSS selector of the input field"},
            "text": {"type": "string", "description": "Text to type"},
        }, "required": ["selector", "text"]})
