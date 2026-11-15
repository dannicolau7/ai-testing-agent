"""
browser_audit.py — open the running application in a browser and watch what happens.

Stage 7 of docs/ROADMAP.md, first version. Everything else in the audit reads source. This
part observes: it opens the application in a real browser, follows the links it finds, and
records what each page actually does.

    python cli.py browse http://localhost:3000 --source path/to/app

It reports:

- wrong now   a page that fails to load or throws an error; a request from a page to the
              API that is answered "not found", "method not allowed" or with a server
              error; a link that leads nowhere
- likely      errors a page writes to the browser console
- unclear     API requests refused for lack of sign-in (the crawl may simply not be signed in)

With --source it also compares what it saw with the backend routes read from the code, and
lists the routes it saw the frontend call. That settles what reading source cannot: calls
made through a helper the source reader did not follow.

Safety. By default it only opens pages and follows links, which are GET requests. It never
fills in forms. It clicks buttons only with --click, and then skips any button whose label
looks destructive. Even so, use it against a test environment, never production.

Needs the `playwright` package and a Chromium browser (pip install playwright; playwright
install chromium). Set ATA_BROWSER_PATH to use a Chromium that is already installed.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from urllib.parse import urldefrag, urljoin, urlparse

import app_audit

DESTRUCTIVE = re.compile(
    r"delete|remove|destroy|drop|erase|purge|cancel|pay|buy|purchase|order|checkout|send|submit|"
    r"sign ?out|log ?out|reset|revoke|disable|deactivate|unsubscribe|confirm|transfer|publish",
    re.IGNORECASE,
)
_STATIC = re.compile(r"\.(js|mjs|css|png|jpe?g|gif|svg|ico|woff2?|ttf|map|webp|avif|json)$", re.IGNORECASE)


class BrowserUnavailable(RuntimeError):
    """Playwright or a browser is not installed."""


@dataclass
class ApiSeen:
    method: str
    path: str
    status: int          # 0 when the request got no answer
    page: str


@dataclass
class PageSeen:
    url: str
    status: int = 0
    errors: List[str] = field(default_factory=list)          # uncaught exceptions
    console_errors: List[str] = field(default_factory=list)
    buttons_clicked: List[str] = field(default_factory=list)
    buttons_skipped: List[str] = field(default_factory=list)


@dataclass
class Observation:
    start: str
    pages: List[PageSeen] = field(default_factory=list)
    api: List[ApiSeen] = field(default_factory=list)
    broken_links: List[Tuple[str, str, int]] = field(default_factory=list)   # (from page, link, status)
    not_visited: int = 0          # links left over when the page limit was reached
    clicked: bool = False


def _path(url: str) -> str:
    parsed = urlparse(url)
    return parsed.path or "/"


def browse(start: str, max_pages: int = 25, click: bool = False, headers: Optional[Dict[str, str]] = None,
           timeout_ms: int = 15000) -> Observation:
    """Open `start`, follow same-site links up to max_pages, and record what each page does."""
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrowserUnavailable(
            "The browser check needs Playwright: pip install playwright && playwright install chromium") from exc

    origin = "{0.scheme}://{0.netloc}".format(urlparse(start))
    seen = Observation(start=start, clicked=click)
    queue: List[Tuple[str, str]] = [(start, "")]
    visited: set = set()

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(executable_path=os.environ.get("ATA_BROWSER_PATH") or None)
        except PlaywrightError as exc:
            raise BrowserUnavailable(
                "No browser could be started. Run `playwright install chromium`, or set ATA_BROWSER_PATH "
                f"to an installed Chromium. ({str(exc).splitlines()[0][:120]})") from exc
        context = browser.new_context(extra_http_headers=headers or {})
        try:
            while queue and len(seen.pages) < max_pages:
                url, came_from = queue.pop(0)
                url = urldefrag(url)[0]
                if url in visited:
                    continue
                visited.add(url)
                page = context.new_page()
                record = PageSeen(url=url)
                current = {"url": url}

                def on_response(response, record=record, current=current):
                    request = response.request
                    if request.resource_type in ("fetch", "xhr") and response.url.startswith(origin):
                        seen.api.append(ApiSeen(request.method, _path(response.url), response.status, _path(current["url"])))

                def on_failed(request, current=current):
                    if request.resource_type in ("fetch", "xhr") and request.url.startswith(origin):
                        seen.api.append(ApiSeen(request.method, _path(request.url), 0, _path(current["url"])))

                page.on("response", on_response)
                page.on("requestfailed", on_failed)
                page.on("pageerror", lambda error, record=record: record.errors.append(str(error)[:200]))
                page.on("console", lambda message, record=record: record.console_errors.append(message.text[:200])
                        if message.type == "error" else None)
                try:
                    response = page.goto(url, wait_until="networkidle", timeout=timeout_ms)
                    record.status = response.status if response else 0
                except PlaywrightError as exc:
                    record.errors.append("the page did not finish loading: " + str(exc).splitlines()[0][:150])
                if record.status >= 400 and came_from:
                    # A link that leads nowhere is a fault of the page that links to it.
                    seen.broken_links.append((_path(came_from), _path(url), record.status))
                    page.close()
                    continue
                seen.pages.append(record)
                try:
                    links = page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))")
                except PlaywrightError:
                    links = []
                for href in links:
                    if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
                        continue
                    target = urldefrag(urljoin(url, href))[0]
                    if target.startswith(origin) and target not in visited and not _STATIC.search(_path(target)):
                        queue.append((target, url))
                if click:
                    _click_buttons(page, record, PlaywrightError)
                page.close()
            seen.not_visited = len({u for u, _ in queue if u not in visited})
        finally:
            context.close()
            browser.close()
    return seen


def _click_buttons(page, record: PageSeen, error_type) -> None:
    """Click buttons that are outside forms and do not look destructive, one at a time."""
    # Number the candidate buttons in the page, so the one clicked is the one whose label was read.
    try:
        labels = page.eval_on_selector_all(
            "button:not([type=submit]):not([disabled])",
            """els => els.filter(e => !e.closest('form')).map((e, i) => {
                   e.setAttribute('data-ata-button', String(i));
                   return (e.innerText || e.getAttribute('aria-label') || '').trim();
               })""")
    except error_type:
        return
    for index, label in enumerate(labels[:20]):
        if not label or DESTRUCTIVE.search(label):
            record.buttons_skipped.append(label or "(no label)")
            continue
        try:
            before = page.url
            page.locator(f'[data-ata-button="{index}"]').click(timeout=3000)
            # Give the click's own requests time to start, then wait for them to finish.
            page.wait_for_timeout(400)
            page.wait_for_load_state("networkidle", timeout=5000)
            record.buttons_clicked.append(label)
            if page.url != before:
                break   # the click left the page; the numbering no longer holds
        except error_type:
            record.buttons_skipped.append(label + " (could not be clicked)")


# ── Findings ──────────────────────────────────────────────────────────────────


@dataclass
class BrowserReport:
    seen: Observation
    findings: List[app_audit.Finding] = field(default_factory=list)
    routes_seen_called: List[str] = field(default_factory=list)   # backend routes the browser saw called
    routes_never_seen: List[str] = field(default_factory=list)
    compared_with_source: bool = False

    def of(self, group: str) -> List[app_audit.Finding]:
        return [f for f in self.findings if f.group == group]

    @property
    def ok(self) -> bool:
        return not self.of("wrong_now")


def report(seen: Observation, model: Optional[app_audit.AppModel] = None) -> BrowserReport:
    out = BrowserReport(seen=seen)
    add = lambda group, title, detail, where: out.findings.append(app_audit.Finding(group, title, detail, where))  # noqa: E731

    for page in seen.pages:
        where = _path(page.url)
        if page.status >= 400 or page.status == 0:
            add("wrong_now", f"The page {where} did not load",
                f"The server answered {page.status}." if page.status else "; ".join(page.errors) or "No answer.", where)
            continue
        for error in dict.fromkeys(page.errors):
            add("wrong_now", f"The page {where} throws an error", error, where)
        for error in list(dict.fromkeys(page.console_errors))[:5]:
            # The browser logs every failed request to the console too; those are reported below.
            if not error.startswith("Failed to load resource"):
                add("likely", f"The page {where} writes an error to the console", error, where)

    for source, link, status in dict.fromkeys(seen.broken_links):
        add("wrong_now", f"A link on {source} leads to {link}, which answers {status}",
            "A user who follows it reaches an error page.", source)

    reported = set()
    # Requests a page sends together are answered in no fixed order; the report's order must not depend on it.
    for call in sorted(seen.api, key=lambda c: (c.page, c.path, c.method, c.status)):
        key = (call.method, app_audit.normalize_path(call.path), call.status)
        if key in reported:
            continue
        reported.add(key)
        name = f"{call.method} {call.path}"
        if call.status in (404, 405):
            reason = "not found" if call.status == 404 else "method not allowed"
            add("wrong_now", f"The page {call.page} calls {name}, and the server answers {call.status}",
                f"Seen in the browser: the request was answered \"{reason}\". The frontend relies on "
                "something the backend does not provide.", call.page)
        elif call.status >= 500:
            add("wrong_now", f"The page {call.page} calls {name}, and the server fails with {call.status}",
                "Seen in the browser on a plain visit to the page.", call.page)
        elif call.status == 0:
            add("wrong_now", f"The page {call.page} calls {name}, and gets no answer",
                "The request failed before any response arrived.", call.page)
        elif call.status in (401, 403):
            add("unclear", f"The page {call.page} calls {name}, and is refused with {call.status}",
                "This is expected if the page needs sign-in and the browser check was not signed in. Pass "
                "--header to sign it in.", call.page)

    if model is not None and model.routes:
        out.compared_with_source = True
        called = set()
        for call in seen.api:
            for route in model.routes:
                if app_audit._match((call.method, app_audit.normalize_path(_api_path(call.path))), {route.key}):
                    called.add(f"{route.method} {route.path}")
        out.routes_seen_called = sorted(called)
        out.routes_never_seen = sorted(
            {f"{r.method} {r.path}" for r in model.routes
             if not app_audit.OPERATIONAL.match(app_audit.normalize_path(r.path))} - called)
    order = {"wrong_now": 0, "likely": 1, "unclear": 2}
    out.findings.sort(key=lambda f: order.get(f.group, 3))
    return out


def _api_path(path: str) -> str:
    """Numbers and long ids in a real URL stand where the route has a parameter."""
    return re.sub(r"/(\d+|[0-9a-fA-F-]{16,})(?=/|$)", "/{id}", path)


def render_markdown(result: BrowserReport) -> str:
    seen = result.seen
    lines = [
        "# Browser check",
        "",
        f"Opened `{seen.start}` in a browser and followed its links.",
        "",
        "| What | Count |",
        "|---|---|",
        f"| Pages opened | {len(seen.pages)} |",
        f"| Requests to the API seen | {len(seen.api)} |",
        f"| Links that lead nowhere | {len(set(seen.broken_links))} |",
    ]
    if result.compared_with_source:
        total = len(result.routes_seen_called) + len(result.routes_never_seen)
        lines.append(f"| Backend routes seen being called | {len(result.routes_seen_called)} of {total} |")
    lines.append("")
    for key, title, _ in app_audit._GROUPS:
        items = result.of(key)
        lines += [f"## {title} ({len(items)})", ""]
        for f in items:
            lines += [f"- **{f.title}**", f"  {f.detail} `{f.where}`"]
        if not items:
            lines.append("- None seen.")
        lines.append("")
    if result.compared_with_source:
        lines += ["## Backend routes", ""]
        if result.routes_seen_called:
            lines.append("Seen being called from a page: " + ", ".join(f"`{r}`" for r in result.routes_seen_called) + ".")
        if result.routes_never_seen:
            lines += ["", "Never seen being called: " + ", ".join(f"`{r}`" for r in result.routes_never_seen) + ". "
                      "They may be reached by a form, a button or a signed-in page this check did not use."]
        lines.append("")
    lines += ["## Not examined", ""]
    if seen.not_visited:
        lines.append(f"- {seen.not_visited} more link(s) were found and not opened: the page limit was reached.")
    skipped = sorted({b for p in seen.pages for b in p.buttons_skipped})
    if seen.clicked:
        clicked = sum(len(p.buttons_clicked) for p in seen.pages)
        lines.append(f"- Buttons: {clicked} clicked. Skipped because the label looks destructive or could not be "
                     f"clicked: {', '.join(skipped) or 'none'}.")
    else:
        lines.append("- Buttons were not clicked. Pass --click to click the ones that do not look destructive.")
    lines += [
        "- Forms were not filled in or submitted.",
        "- Pages that need sign-in, unless --header gave the browser a way in.",
        "- Whether what a page shows is right: this check sees requests and errors, not meaning.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"
