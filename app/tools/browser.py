"""Browser tools — web search, reading, and interactive navigation."""

import asyncio
import re
import httpx
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import html2text
from ddgs import DDGS
from app.tools import registry

_stealth = Stealth()
_session = {"pw": None, "browser": None, "context": None, "page": None}
_browser_lock = asyncio.Lock()

# Reusable HTTP client for web_read (connection pooling)
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10),
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
        )
    return _http_client


# --- Browser lifecycle ---

async def _ensure_browser():
    """Launch or reuse a persistent stealth browser."""
    if _session["page"] and not _session["page"].is_closed():
        return _session["page"]

    await close_browser()

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage", "--no-sandbox"],
    )
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
        locale="fr-FR",
        timezone_id="Europe/Paris",
    )
    await _stealth.use_async(context)
    page = await context.new_page()

    _session.update(pw=pw, browser=browser, context=context, page=page)
    return page


async def close_browser():
    """Shut down the browser and free all resources."""
    # Close page first, then context, then browser
    for key in ("page", "context", "browser"):
        try:
            if _session[key]:
                await _session[key].close()
        except Exception:
            pass
    try:
        if _session["pw"]:
            await _session["pw"].stop()
    except Exception:
        pass
    _session.update(pw=None, browser=None, context=None, page=None)

    # Close shared HTTP client
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


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


async def _get_elements(page) -> str:
    elements = await page.evaluate("""() => {
        function esc(s) { return s.replace(/\\\\/g, '\\\\\\\\').replace(/"/g, '\\\\"'); }
        const out = [];
        document.querySelectorAll('a[href], button, input, select, textarea, [role="button"]')
            .forEach((el, i) => {
                if (!(el.offsetParent || el.offsetWidth > 0)) return;
                const tag = el.tagName.toLowerCase();
                const id = el.id, name = el.name || '', type = el.type || '';
                const text = (el.innerText || '').trim().substring(0, 60);
                const ph = el.placeholder || '', aria = el.getAttribute('aria-label') || '';
                const href = el.href || '';

                let sel = id ? '#'+CSS.escape(id) : name ? `${tag}[name="${esc(name)}"]`
                    : ph ? `${tag}[placeholder="${esc(ph)}"]` : aria ? `[aria-label="${esc(aria)}"]`
                    : text && tag !== 'input' ? `${tag}:has-text("${esc(text.substring(0,40))}")`
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


async def _retry(fn, retries=2, delay=2):
    last_err = None
    for i in range(retries + 1):
        try:
            return await fn()
        except Exception as e:
            last_err = e
            if i < retries:
                await asyncio.sleep(delay)
    return f"ERROR after {retries + 1} attempts: {last_err}"


# --- Tool functions ---

async def web_search(query: str, max_results: int = 5) -> str:
    def _do():
        results = DDGS().text(query, max_results=max_results)
        if not results:
            return "No results found."
        return "\n\n".join(
            f"{i}. {r['title']}\n   {r['href']}\n   {r['body']}"
            for i, r in enumerate(results, 1)
        )
    return await asyncio.to_thread(_do)


async def web_read(url: str) -> str:
    async def _do():
        # Try plain HTTP first
        try:
            client = _get_http_client()
            res = await client.get(url)
            if res.status_code == 200 and len(res.text) > 500:
                html = res.text
                # Extract <main> or <article> content for cleaner output
                m = re.search(r"(<(?:main|article)\b[^>]*>.*?</(?:main|article)>)", html, re.DOTALL | re.IGNORECASE)
                if m:
                    html = m.group(1)
                md = _to_markdown(html)
                if len(md) > 200:
                    return md[:4000] + "\n\n[... truncated ...]" if len(md) > 4000 else md
        except Exception:
            pass

        # Fallback to browser (serialized access)
        async with _browser_lock:
            page = await _ensure_browser()
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2000)
            await page.evaluate("""
                ['nav','footer','header','.cookie-banner','#cookie-consent','.ad','.ads',
                 '.sidebar','.menu','script','style','noscript','iframe']
                .forEach(s => document.querySelectorAll(s).forEach(el => el.remove()));
            """)
            md = _to_markdown(await page.content())
            return md[:4000] + "\n\n[... truncated ...]" if len(md) > 4000 else md

    return await _retry(_do)


async def web_go(url: str) -> str:
    async def _do():
        async with _browser_lock:
            page = await _ensure_browser()
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2000)
            elements = await _get_elements(page)
            title = await page.title()
            return f"Page: {title}\nURL: {page.url}\n\nElements:\n{elements}"
    return await _retry(_do)


async def web_click(selector: str) -> str:
    async def _do():
        async with _browser_lock:
            page = await _ensure_browser()
            await page.click(selector, timeout=5000)
            await page.wait_for_timeout(1500)
            elements = await _get_elements(page)
            title = await page.title()
            return f"Clicked. Page: {title}\nURL: {page.url}\n\nElements:\n{elements}"
    return await _retry(_do)


async def web_type(selector: str, text: str) -> str:
    async def _do():
        async with _browser_lock:
            page = await _ensure_browser()
            await page.fill(selector, text, timeout=5000)
            return f"Typed '{text}' into {selector}."
    return await _retry(_do)


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
