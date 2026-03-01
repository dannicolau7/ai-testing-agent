#!/usr/bin/env python3
"""
Request Runner - Postman Replacement
=====================================
Send HTTP requests from the command line and optionally save them as pytest tests.

USAGE EXAMPLES:

    # Simple GET request
    python cli.py request GET /api/users

    # POST request with body
    python cli.py request POST /api/login \\
      --body '{"email":"test@test.com","password":"pass"}'

    # With Bearer auth
    python cli.py request GET /api/profile \\
      --auth bearer \\
      --token "eyJ..."

    # Save as test
    python cli.py request POST /api/login \\
      --body '{"email":"test@test.com","password":"pass"}' \\
      --save-as-test \\
      --test-name login_test

    # With custom headers
    python cli.py request GET /api/data \\
      --headers '{"X-Custom":"value"}' \\
      --auth apikey \\
      --token "abc123"

    # Different environment
    python cli.py request GET /api/users \\
      --base-url https://staging.api.com \\
      --env staging
"""

import requests
import json
import os
from typing import Dict, Optional, Any, List
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

console = Console()


class RequestRunner:
    """
    Send HTTP requests and optionally save as pytest tests.
    Replaces Postman for API testing workflows.

    Integrates with:
    - env_manager.py  → loads base URLs from named environments
    - auth_handler.py → all supported auth schemes
    - test_output/    → generated tests match existing test structure
    """

    def __init__(self, base_url: str = None, env: str = "dev"):
        """
        Initialise the runner.

        Args:
            base_url: Override base URL (falls back to env_manager → BASE_URL env var → localhost)
            env:      Named environment to load via env_manager (dev / staging / prod …)
        """
        self.env = env
        self.base_url = base_url or self._resolve_base_url(env)
        self.session = requests.Session()
        self.history: List[Dict] = []
        self.last_response: Optional[requests.Response] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send(
        self,
        method: str,
        path: str,
        headers: Dict = None,
        body: Dict = None,
        params: Dict = None,
        auth: Dict = None,
        timeout: int = 30,
    ) -> requests.Response:
        """
        Send an HTTP request.

        Args:
            method:  HTTP method (GET, POST, PUT, DELETE, PATCH …)
            path:    API path, e.g. /api/login
            headers: Extra request headers
            body:    JSON request body (dict)
            params:  Query-string parameters (dict)
            auth:    Authentication config dict, e.g.
                        {'type': 'bearer', 'token': 'eyJ...'}
                        {'type': 'apikey', 'header_name': 'X-API-Key', 'key': 'abc'}
                        {'type': 'basic',  'username': 'u', 'password': 'p'}
            timeout: Request timeout in seconds (default 30)

        Returns:
            requests.Response object

        Raises:
            requests.exceptions.ConnectionError: host unreachable
            requests.exceptions.Timeout:         request timed out
            requests.exceptions.RequestException: any other network error
        """
        url = self._build_url(path)
        headers = dict(headers or {})

        # Resolve auth
        basic_auth_tuple = None
        if auth and auth.get("type", "none").lower() != "none":
            headers, basic_auth_tuple = self._apply_auth(headers, auth)

        try:
            response = self.session.request(
                method=method.upper(),
                url=url,
                headers=headers if headers else None,
                json=body,
                params=params,
                auth=basic_auth_tuple,
                timeout=timeout,
            )

            self.last_response = response
            self.history.append(
                {
                    "timestamp": datetime.now(),
                    "method": method.upper(),
                    "url": url,
                    "status": response.status_code,
                    "duration": response.elapsed.total_seconds(),
                }
            )

            return response

        except requests.exceptions.ConnectionError as e:
            console.print(f"[red]❌ Connection error – is the server running at {self.base_url}?[/red]")
            console.print(f"[dim]{e}[/dim]")
            raise
        except requests.exceptions.Timeout:
            console.print(f"[red]❌ Request timed out after {timeout}s[/red]")
            raise
        except requests.exceptions.RequestException as e:
            console.print(f"[red]❌ Request failed: {e}[/red]")
            raise

    def display_response(self, response: requests.Response) -> None:
        """Render the response in a rich, Postman-style format."""
        # ── Status line ────────────────────────────────────────────────
        status_color = "green" if response.status_code < 400 else "red"
        elapsed = response.elapsed.total_seconds()

        console.print()
        console.print(
            Panel(
                Text.from_markup(
                    f"[{status_color} bold]{response.status_code} {response.reason}[/{status_color} bold]"
                    f"   [blue]{elapsed:.3f}s[/blue]"
                    f"   [dim]{len(response.content)} bytes[/dim]"
                ),
                title="[bold]Response[/bold]",
                border_style=status_color,
            )
        )

        # ── Response headers (first 15) ────────────────────────────────
        if response.headers:
            console.print("[yellow]Response Headers:[/yellow]")
            tbl = Table(show_header=False, box=None, padding=(0, 2))
            tbl.add_column("Key", style="cyan", no_wrap=True)
            tbl.add_column("Value", style="white")
            for key, value in list(response.headers.items())[:15]:
                tbl.add_row(key, value)
            console.print(tbl)
            console.print()

        # ── Body ───────────────────────────────────────────────────────
        console.print("[yellow]Response Body:[/yellow]")
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type or self._looks_like_json(response.text):
            try:
                json_data = response.json()
                syntax = Syntax(
                    json.dumps(json_data, indent=2, ensure_ascii=False),
                    "json",
                    theme="monokai",
                    line_numbers=True,
                    word_wrap=True,
                )
                console.print(syntax)
            except Exception:
                console.print(response.text[:2000])
        elif "text/html" in content_type:
            # Show a short snippet rather than the whole HTML blob
            console.print(f"[dim]{response.text[:500]}…[/dim]")
        else:
            console.print(response.text[:2000])

    def save_as_test(
        self,
        response: requests.Response,
        test_name: str,
        output_path: str = "./test_output",
        method: str = "GET",
        path: str = "/",
        body: Dict = None,
        headers: Dict = None,
        params: Dict = None,
    ) -> str:
        """
        Save this request/response pair as a runnable pytest file.

        Args:
            response:    Response received from send()
            test_name:   Snake-case name for the test function (e.g. login_test)
            output_path: Directory where the file will be written
            method:      HTTP method used
            path:        API path used
            body:        Request body dict (or None)
            headers:     Request headers dict (or None)
            params:      Query params dict (or None)

        Returns:
            Absolute path of the saved file
        """
        os.makedirs(output_path, exist_ok=True)

        # Attempt to parse JSON body from response
        expected_body: Optional[Dict] = None
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                expected_body = response.json()
            except Exception:
                pass

        test_code = self._generate_test_code(
            test_name=test_name,
            method=method,
            path=path,
            body=body,
            headers=headers,
            params=params,
            expected_status=response.status_code,
            expected_body=expected_body,
        )

        # Sanitise test name for use as a filename
        safe_name = "".join(c if c.isalnum() or c == "_" else "_" for c in test_name)
        filename = os.path.join(output_path, f"test_{safe_name}.py")

        with open(filename, "w", encoding="utf-8") as f:
            f.write(test_code)

        console.print(f"\n[green]✅ Test saved to: {filename}[/green]")
        console.print(f"[blue]Run with: pytest {filename} -v[/blue]")

        return filename

    def show_history(self) -> None:
        """Print a summary table of all requests made this session."""
        if not self.history:
            console.print("[dim]No requests in history yet.[/dim]")
            return

        tbl = Table(title="Request History", show_lines=True)
        tbl.add_column("#", style="dim", width=4)
        tbl.add_column("Method", style="cyan", width=8)
        tbl.add_column("URL", style="white")
        tbl.add_column("Status", width=8)
        tbl.add_column("Time (s)", width=10)

        for idx, entry in enumerate(self.history, 1):
            color = "green" if entry["status"] < 400 else "red"
            tbl.add_row(
                str(idx),
                entry["method"],
                entry["url"],
                f"[{color}]{entry['status']}[/{color}]",
                f"{entry['duration']:.3f}",
            )

        console.print(tbl)

    def display_request(
        self,
        method: str,
        path: str,
        headers: Dict = None,
        body: Dict = None,
        params: Dict = None,
        auth: Dict = None,
    ) -> None:
        """Show a Postman-style panel of what is about to be sent."""
        url = self._build_url(path)

        console.print()
        console.print(
            Panel(
                Text.from_markup(f"[cyan bold]{method.upper()}[/cyan bold]  [white]{url}[/white]"),
                title="[bold]Request[/bold]",
                border_style="cyan",
            )
        )

        if params:
            console.print("[yellow]Query Params:[/yellow]")
            tbl = Table(show_header=False, box=None, padding=(0, 2))
            tbl.add_column("Key", style="cyan")
            tbl.add_column("Value", style="white")
            for k, v in params.items():
                tbl.add_row(k, str(v))
            console.print(tbl)
            console.print()

        if headers:
            console.print("[yellow]Request Headers:[/yellow]")
            tbl = Table(show_header=False, box=None, padding=(0, 2))
            tbl.add_column("Key", style="cyan")
            tbl.add_column("Value", style="white")
            for k, v in headers.items():
                tbl.add_row(k, str(v))
            console.print(tbl)
            console.print()

        if auth and auth.get("type", "none") != "none":
            console.print(f"[yellow]Auth:[/yellow] [dim]{auth.get('type', '').upper()}[/dim]")
            console.print()

        if body:
            console.print("[yellow]Request Body:[/yellow]")
            syntax = Syntax(
                json.dumps(body, indent=2, ensure_ascii=False),
                "json",
                theme="monokai",
                line_numbers=False,
            )
            console.print(syntax)
            console.print()

    def to_curl(
        self,
        method: str,
        path: str,
        headers: Dict = None,
        body: Dict = None,
        params: Dict = None,
        auth: Dict = None,
    ) -> str:
        """
        Generate the equivalent curl command for this request.

        Example output:
            curl -X POST 'https://api.example.com/api/login' \\
              -H 'Content-Type: application/json' \\
              -H 'Authorization: Bearer eyJ...' \\
              -d '{"email":"x@x.com"}'
        """
        url = self._build_url(path)

        # Add query params to URL
        if params:
            from urllib.parse import urlencode
            url = f"{url}?{urlencode(params)}"

        parts = [f"curl -X {method.upper()} '{url}'"]

        # Auth headers (simulate what _apply_auth does)
        effective_headers = dict(headers or {})
        if auth and auth.get("type", "none") != "none":
            auth_type = auth.get("type", "").lower()
            if auth_type in ("bearer", "oauth2"):
                token = auth.get("token") or ""
                effective_headers["Authorization"] = f"Bearer {token}"
            elif auth_type == "apikey":
                key_name = auth.get("header_name", "X-API-Key")
                effective_headers[key_name] = auth.get("token") or ""
            elif auth_type == "basic":
                raw = auth.get("token") or ""
                parts.append(f"  -u '{raw}'")

        for k, v in effective_headers.items():
            parts.append(f"  -H '{k}: {v}'")

        if body:
            body_str = json.dumps(body, separators=(",", ":"))
            if "Content-Type" not in effective_headers:
                parts.append("  -H 'Content-Type: application/json'")
            parts.append(f"  -d '{body_str}'")

        curl_cmd = " \\\n".join(parts)
        return curl_cmd

    def run_benchmark(
        self,
        method: str,
        path: str,
        n: int = 10,
        headers: Dict = None,
        body: Dict = None,
        params: Dict = None,
        auth: Dict = None,
        timeout: int = 30,
    ) -> Dict:
        """
        Send the request N times and show a latency stats table.

        Args:
            n: Number of repetitions (default 10)

        Returns:
            Dict with keys: min, max, avg, p95, success_count, error_count
        """
        import statistics

        console.print(f"\n[cyan]⏱  Benchmarking {method.upper()} {self._build_url(path)} × {n}…[/cyan]\n")

        times: List[float] = []
        statuses: List[int] = []
        errors = 0

        for i in range(1, n + 1):
            try:
                resp = self.send(
                    method=method,
                    path=path,
                    headers=headers,
                    body=body,
                    params=params,
                    auth=auth,
                    timeout=timeout,
                )
                elapsed = resp.elapsed.total_seconds() * 1000  # ms
                times.append(elapsed)
                statuses.append(resp.status_code)
                status_color = "green" if resp.status_code < 400 else "red"
                console.print(
                    f"  [{status_color}]#{i:>3}  {resp.status_code}  {elapsed:>7.1f} ms[/{status_color}]"
                )
            except Exception:
                errors += 1
                console.print(f"  [red]#{i:>3}  ERROR[/red]")

        if not times:
            console.print("[red]All requests failed.[/red]")
            return {"min": 0, "max": 0, "avg": 0, "p95": 0, "success_count": 0, "error_count": errors}

        times_sorted = sorted(times)
        p95_idx = max(0, int(len(times_sorted) * 0.95) - 1)
        stats = {
            "min": min(times),
            "max": max(times),
            "avg": statistics.mean(times),
            "p95": times_sorted[p95_idx],
            "success_count": len(times),
            "error_count": errors,
        }

        # Status distribution
        from collections import Counter
        status_dist = Counter(statuses)

        console.print()
        tbl = Table(title=f"Benchmark Results  ({n} requests)", show_lines=True)
        tbl.add_column("Metric", style="yellow")
        tbl.add_column("Value", style="cyan")
        tbl.add_row("Min latency", f"{stats['min']:.1f} ms")
        tbl.add_row("Max latency", f"{stats['max']:.1f} ms")
        tbl.add_row("Avg latency", f"{stats['avg']:.1f} ms")
        tbl.add_row("p95 latency", f"{stats['p95']:.1f} ms")
        tbl.add_row("Successes", str(stats["success_count"]))
        tbl.add_row("Errors", str(stats["error_count"]))
        for code, count in sorted(status_dist.items()):
            tbl.add_row(f"HTTP {code}", f"{count}×")
        console.print(tbl)

        return stats

    def retry_send(
        self,
        method: str,
        path: str,
        headers: Dict = None,
        body: Dict = None,
        params: Dict = None,
        auth: Dict = None,
        timeout: int = 30,
        retries: int = 3,
        retry_on: tuple = (500, 502, 503, 504),
    ) -> requests.Response:
        """
        Send with automatic retry on network errors or specified status codes.

        Args:
            retries:   Maximum number of retry attempts (default 3)
            retry_on:  HTTP status codes that trigger a retry (default 5xx)

        Returns:
            Final requests.Response
        """
        import time

        last_exc = None
        for attempt in range(1, retries + 2):  # +1 for the initial attempt
            try:
                resp = self.send(
                    method=method,
                    path=path,
                    headers=headers,
                    body=body,
                    params=params,
                    auth=auth,
                    timeout=timeout,
                )
                if resp.status_code in retry_on and attempt <= retries:
                    wait = 2 ** (attempt - 1)  # exponential back-off: 1s, 2s, 4s …
                    console.print(
                        f"[yellow]⚠  HTTP {resp.status_code} – retrying in {wait}s "
                        f"(attempt {attempt}/{retries})[/yellow]"
                    )
                    time.sleep(wait)
                    continue
                return resp
            except requests.exceptions.RequestException as exc:
                last_exc = exc
                if attempt <= retries:
                    wait = 2 ** (attempt - 1)
                    console.print(
                        f"[yellow]⚠  Network error – retrying in {wait}s "
                        f"(attempt {attempt}/{retries})[/yellow]"
                    )
                    time.sleep(wait)

        if last_exc:
            raise last_exc
        raise requests.exceptions.RequestException("All retry attempts exhausted")

    # ── Collections ────────────────────────────────────────────────────────

    def save_collection(
        self,
        name: str,
        method: str,
        path: str,
        headers: Dict = None,
        body: Dict = None,
        params: Dict = None,
        auth: Dict = None,
        collection_file: str = "./requests_collection.json",
    ) -> None:
        """
        Save a named request to a collection JSON file (like Postman collections).

        Args:
            name:            Human-readable name, e.g. 'login' or 'get_users'
            collection_file: Path to the collection JSON file
        """
        import time as _time

        collection = self._load_collection_file(collection_file)

        collection[name] = {
            "method": method.upper(),
            "path": path,
            "headers": headers or {},
            "body": body,
            "params": params or {},
            "auth": auth or {"type": "none"},
            "saved_at": datetime.now().isoformat(),
        }

        with open(collection_file, "w", encoding="utf-8") as f:
            json.dump(collection, f, indent=2)

        console.print(f"[green]✅ Saved '{name}' to collection: {collection_file}[/green]")

    def list_collection(self, collection_file: str = "./requests_collection.json") -> None:
        """Print all saved requests in a collection."""
        collection = self._load_collection_file(collection_file)

        if not collection:
            console.print(f"[dim]Collection is empty: {collection_file}[/dim]")
            return

        tbl = Table(title=f"Collection: {collection_file}", show_lines=True)
        tbl.add_column("Name", style="cyan")
        tbl.add_column("Method", style="yellow", width=8)
        tbl.add_column("Path / URL", style="white")
        tbl.add_column("Auth", style="dim")
        tbl.add_column("Saved", style="dim")

        for name, req in collection.items():
            tbl.add_row(
                name,
                req.get("method", "GET"),
                req.get("path", "/"),
                req.get("auth", {}).get("type", "none"),
                req.get("saved_at", "")[:19],
            )

        console.print(tbl)

    def run_collection_request(
        self,
        name: str,
        collection_file: str = "./requests_collection.json",
        timeout: int = 30,
    ) -> Optional[requests.Response]:
        """
        Replay a named request from the collection.

        Args:
            name: The name used when saving (e.g. 'login')

        Returns:
            Response object, or None if name not found
        """
        collection = self._load_collection_file(collection_file)

        if name not in collection:
            console.print(f"[red]❌ '{name}' not found in {collection_file}[/red]")
            console.print(f"[dim]Available: {', '.join(collection.keys()) or 'none'}[/dim]")
            return None

        req = collection[name]
        console.print(f"\n[cyan]▶  Running collection request: '{name}'[/cyan]")

        auth = req.get("auth") or {"type": "none"}
        if auth.get("type") == "none":
            auth = None

        return self.send(
            method=req["method"],
            path=req["path"],
            headers=req.get("headers") or None,
            body=req.get("body"),
            params=req.get("params") or None,
            auth=auth,
            timeout=timeout,
        )

    def _load_collection_file(self, path: str) -> Dict:
        """Load collection JSON, returning empty dict if file doesn't exist."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError as e:
            console.print(f"[red]❌ Corrupt collection file ({path}): {e}[/red]")
            return {}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_base_url(self, env: str) -> str:
        """
        Resolve base URL with priority:
          1. env_manager active environment
          2. BASE_URL environment variable
          3. http://localhost:8000 default
        """
        try:
            from env_manager import EnvManager

            mgr = EnvManager()
            env_data = mgr.get_env(env) or mgr.get_active_env()
            if env_data and env_data.get("base_url"):
                return env_data["base_url"].rstrip("/")
        except Exception:
            pass  # env_manager unavailable – fall through

        return os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")

    def _build_url(self, path: str) -> str:
        """
        Build the final request URL.

        If ``path`` is already a full URL (starts with http:// or https://)
        it is used verbatim so the caller can do:

            python cli.py request GET https://jsonplaceholder.typicode.com/posts/1

        Otherwise it is appended to ``self.base_url``.
        """
        if path.startswith("http://") or path.startswith("https://"):
            return path
        base = self.base_url.rstrip("/")
        path = path if path.startswith("/") else f"/{path}"
        return f"{base}{path}"

    def _apply_auth(
        self, headers: Dict, auth: Dict
    ):
        """
        Apply authentication to the request.

        Supports all auth types that auth_handler.py knows about:
          bearer  – Authorization: Bearer <token>
          apikey  – <header_name>: <key>
          basic   – returns an HTTPBasicAuth tuple for requests
          oauth2  – treated as bearer (token already obtained)

        Returns:
            (updated_headers, basic_auth_tuple_or_None)
        """
        auth_type = auth.get("type", "bearer").lower()

        if auth_type in ("bearer", "oauth2"):
            token = auth.get("token") or auth.get("key")
            if not token:
                console.print("[yellow]⚠️  Bearer auth selected but no --token provided.[/yellow]")
            else:
                headers["Authorization"] = f"Bearer {token}"

        elif auth_type == "apikey":
            header_name = auth.get("header_name", "X-API-Key")
            key_value = auth.get("token") or auth.get("key")
            if not key_value:
                console.print("[yellow]⚠️  API-key auth selected but no --token provided.[/yellow]")
            else:
                headers[header_name] = key_value

        elif auth_type == "basic":
            username = auth.get("username") or auth.get("token", "").split(":")[0]
            password = auth.get("password") or (
                auth.get("token", "").split(":", 1)[1]
                if ":" in (auth.get("token") or "")
                else ""
            )
            if not username:
                console.print(
                    "[yellow]⚠️  Basic auth: supply --token as 'username:password'.[/yellow]"
                )
            else:
                return headers, (username, password)

        return headers, None

    def _looks_like_json(self, text: str) -> bool:
        """Quick heuristic – does the body look like JSON?"""
        stripped = text.strip()
        return stripped.startswith(("{", "[")) if stripped else False

    def _generate_test_code(
        self,
        test_name: str,
        method: str,
        path: str,
        body: Optional[Dict],
        headers: Optional[Dict],
        params: Optional[Dict],
        expected_status: int,
        expected_body: Optional[Dict],
    ) -> str:
        """
        Produce a complete, runnable pytest file from a captured request/response.

        The generated test:
          • Uses BASE_URL from environment (compatible with existing conftest.py)
          • Makes the identical request that was captured
          • Asserts status code
          • Asserts that the top-level keys of the response body are present
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        method_lower = method.lower()

        # ── Header block ───────────────────────────────────────────────
        code = f'''"""
Auto-generated test from RequestRunner (Postman replacement)
Generated : {now}
Method    : {method.upper()}
Path      : {path}
Status    : {expected_status}
"""

import pytest
import requests
import os

BASE_URL = os.getenv("BASE_URL", "{self.base_url}")


'''

        # ── Test function ──────────────────────────────────────────────
        code += f'def test_{test_name}():\n'
        code += f'    """\n'
        code += f'    Verify {method.upper()} {path} returns {expected_status}.\n'
        code += f'\n'
        code += f'    Auto-generated by RequestRunner on {now}.\n'
        code += f'    Edit assertions below to tighten coverage.\n'
        code += f'    """\n'
        code += f'    url = f"{{BASE_URL}}{path}"\n\n'

        # Headers
        if headers:
            formatted_headers = json.dumps(headers, indent=8)
            code += f"    headers = {formatted_headers}\n"
        else:
            code += "    headers = {}\n"

        # Query params
        if params:
            formatted_params = json.dumps(params, indent=8)
            code += f"    params = {formatted_params}\n"

        # Body
        if body:
            formatted_body = json.dumps(body, indent=8)
            code += f"    body = {formatted_body}\n"

        code += "\n"

        # Build the requests call
        call_args = ["url"]
        if body:
            call_args.append("json=body")
        if headers:
            call_args.append("headers=headers")
        if params:
            call_args.append("params=params")

        args_str = ",\n        ".join(call_args)
        code += f"    response = requests.{method_lower}(\n"
        code += f"        {args_str}\n"
        code += f"    )\n\n"

        # ── Assertions ─────────────────────────────────────────────────
        code += "    # ── Status assertion ──────────────────────────────────────\n"
        code += f'    assert response.status_code == {expected_status}, (\n'
        code += f'        f"Expected HTTP {expected_status}, got {{response.status_code}}. "\n'
        code += f'        f"Body: {{response.text[:200]}}"\n'
        code += f'    )\n'

        if expected_body and isinstance(expected_body, dict):
            top_keys = list(expected_body.keys())[:5]
            code += "\n    # ── Body assertions (top-level keys) ─────────────────────\n"
            code += "    data = response.json()\n"
            for key in top_keys:
                safe_key = key.replace('"', '\\"')
                code += (
                    f'    assert "{safe_key}" in data, '
                    f'"Response JSON is missing expected field: {safe_key}"\n'
                )

        elif expected_body and isinstance(expected_body, list):
            code += "\n    # ── Body assertion (list response) ────────────────────────\n"
            code += "    data = response.json()\n"
            code += "    assert isinstance(data, list), \"Expected a JSON array response\"\n"

        code += "\n\n"

        # ── Parametrised edge-case block ───────────────────────────────
        if body:
            code += "# ── Optional: parametrised edge-case tests ────────────────────\n"
            code += "# Uncomment and customise as needed\n"
            code += "#\n"
            code += "# @pytest.mark.parametrize(\"payload,expected_status\", [\n"
            code += "#     ({}, 422),         # empty body\n"
            code += "#     (None, 422),        # missing body\n"
            code += "# ])\n"
            code += f"# def test_{test_name}_edge_cases(payload, expected_status):\n"
            code += f'#     url = f"{{BASE_URL}}{path}"\n'
            code += f"#     response = requests.{method_lower}(url, json=payload)\n"
            code += "#     assert response.status_code == expected_status\n"

        return code

    def analyze_response(self, response: requests.Response, method: str = "GET", path: str = "/") -> Dict:
        """
        Analyze a response and return findings + suggested pytest assertions.

        No external API key required — analysis is pattern-based.

        Returns a dict with:
            status_summary  : human-readable status description
            performance     : latency assessment (fast / acceptable / slow / very slow)
            issues          : list of detected issues
            suggestions     : list of suggested assertions to add to the test
            score           : overall health score 0-100
        """
        status = response.status_code
        elapsed_ms = response.elapsed.total_seconds() * 1000
        content_type = response.headers.get("content-type", "")

        issues: List[str] = []
        suggestions: List[str] = []

        # ── Status assessment ──────────────────────────────────────────
        if 200 <= status < 300:
            status_summary = f"✅ {status} — Success"
        elif status in (301, 302, 307, 308):
            status_summary = f"↪️  {status} — Redirect"
            issues.append(f"Response is a redirect to: {response.headers.get('Location', '?')}")
        elif status == 400:
            status_summary = "❌ 400 — Bad Request (malformed input)"
            issues.append("Server rejected the request body — check field names and types")
        elif status == 401:
            status_summary = "🔒 401 — Unauthorized (missing or invalid credentials)"
            issues.append("Authentication failed — check token / API key")
        elif status == 403:
            status_summary = "🚫 403 — Forbidden (insufficient permissions)"
            issues.append("Authenticated but not authorized for this resource")
        elif status == 404:
            status_summary = "🔍 404 — Not Found"
            issues.append(f"Endpoint {method.upper()} {path} does not exist")
        elif status == 405:
            status_summary = "⛔ 405 — Method Not Allowed"
            allowed = response.headers.get("Allow", "?")
            issues.append(f"HTTP {method.upper()} is not allowed — server accepts: {allowed}")
        elif status == 409:
            status_summary = "⚡ 409 — Conflict (duplicate resource)"
            issues.append("Resource already exists — consider testing idempotency")
        elif status == 422:
            status_summary = "❌ 422 — Unprocessable Entity (validation error)"
            issues.append("Validation error — review required fields and data types")
        elif status == 429:
            status_summary = "🐢 429 — Rate Limited"
            retry_after = response.headers.get("Retry-After", "?")
            issues.append(f"Rate limit hit — Retry-After: {retry_after}s")
        elif status >= 500:
            status_summary = f"🔥 {status} — Server Error"
            issues.append("Server-side error — inspect API logs")
        else:
            status_summary = f"ℹ️  {status}"

        # ── Performance assessment ─────────────────────────────────────
        if elapsed_ms < 200:
            performance = "🟢 fast"
        elif elapsed_ms < 800:
            performance = "🟡 acceptable"
        elif elapsed_ms < 2000:
            performance = "🟠 slow"
        else:
            performance = "🔴 very slow"
        performance += f" ({elapsed_ms:.0f} ms)"

        if elapsed_ms > 2000:
            issues.append(f"High latency: {elapsed_ms:.0f} ms — consider caching or query optimisation")

        # ── Body analysis ──────────────────────────────────────────────
        body = None
        if "application/json" in content_type:
            try:
                body = response.json()
            except Exception:
                issues.append("Content-Type is application/json but body is not valid JSON")

        if body is not None:
            if isinstance(body, dict):
                keys = list(body.keys())
                suggestions.append(f"assert response.status_code == {status}")
                suggestions.append("data = response.json()")
                for key in keys[:6]:
                    suggestions.append(f'assert "{key}" in data')
                # Look for common error patterns even in 2xx
                if status < 300:
                    if "error" in body or "errors" in body:
                        issues.append("Success status but response body contains an 'error' field — verify this is intentional")
                    if "token" in body or "access_token" in body:
                        token_key = "access_token" if "access_token" in body else "token"
                        suggestions.append(f'assert len(data["{token_key}"]) > 0, "Token should not be empty"')
                    if "id" in body:
                        suggestions.append('assert data["id"] is not None, "Resource ID should be present"')
            elif isinstance(body, list):
                suggestions.append(f"assert response.status_code == {status}")
                suggestions.append("data = response.json()")
                suggestions.append("assert isinstance(data, list)")
                if body:
                    first = body[0]
                    if isinstance(first, dict):
                        for key in list(first.keys())[:4]:
                            suggestions.append(f'assert "{key}" in data[0]')
            # Warn on empty body for 200/201
            if not body and status in (200, 201):
                issues.append("Response body is empty for a 200/201 — check if this is expected")

        elif status < 300 and not body:
            suggestions.append(f"assert response.status_code == {status}")

        # Check for missing security headers (informational)
        security_headers = ["x-content-type-options", "x-frame-options", "strict-transport-security"]
        missing_security = [h for h in security_headers if h not in {k.lower() for k in response.headers}]
        if missing_security:
            issues.append(f"Missing security headers: {', '.join(missing_security)}")

        # ── Score ──────────────────────────────────────────────────────
        score = 100
        score -= len(issues) * 10
        if elapsed_ms > 2000:
            score -= 20
        elif elapsed_ms > 800:
            score -= 10
        if status >= 500:
            score -= 30
        elif status >= 400:
            score -= 20
        score = max(0, min(100, score))

        result = {
            "status_summary": status_summary,
            "performance": performance,
            "issues": issues,
            "suggestions": suggestions,
            "score": score,
        }

        # ── Rich display ───────────────────────────────────────────────
        console.print()
        score_color = "green" if score >= 80 else ("yellow" if score >= 50 else "red")
        console.print(
            Panel(
                f"[bold]{status_summary}[/bold]\n"
                f"Performance: {performance}\n"
                f"Health score: [{score_color}]{score}/100[/{score_color}]",
                title="[bold]Response Analysis[/bold]",
                border_style=score_color,
            )
        )

        if issues:
            console.print("[yellow]⚠️  Issues found:[/yellow]")
            for issue in issues:
                console.print(f"   • {issue}")
            console.print()

        if suggestions:
            console.print("[cyan]💡 Suggested assertions:[/cyan]")
            for s in suggestions:
                console.print(f"   [dim]{s}[/dim]")
            console.print()

        return result

    def interactive_mode(self, output_path: str = "./test_output") -> None:
        """
        REPL-style interactive request builder — like Postman's UI in the terminal.

        Type 'exit' or press Ctrl-C to quit.
        """
        console.print()
        console.print(
            Panel(
                "[bold cyan]AI Testing Agent — Interactive Request Mode[/bold cyan]\n"
                "[dim]Type 'exit' to quit · Press Enter to accept defaults[/dim]",
                border_style="cyan",
            )
        )

        while True:
            try:
                console.print("\n[bold cyan]── New Request ─────────────────────────────[/bold cyan]")

                method = input("Method [GET]: ").strip().upper() or "GET"
                if method.lower() == "exit":
                    break

                path = input("Path: ").strip()
                if not path or path.lower() == "exit":
                    break
                if not path.startswith("/") and not path.startswith("http"):
                    path = "/" + path

                # Optional body
                body_raw = input("Body JSON (or Enter to skip): ").strip()
                body = None
                if body_raw:
                    try:
                        body = json.loads(body_raw)
                    except json.JSONDecodeError:
                        console.print("[yellow]⚠️  Invalid JSON — body ignored[/yellow]")

                # Optional query params
                params_raw = input("Query params JSON (or Enter to skip): ").strip()
                params = None
                if params_raw:
                    try:
                        params = json.loads(params_raw)
                    except json.JSONDecodeError:
                        console.print("[yellow]⚠️  Invalid JSON — params ignored[/yellow]")

                # Auth
                auth_type = input("Auth (bearer/apikey/basic/none) [none]: ").strip().lower() or "none"
                auth = None
                if auth_type != "none":
                    token = input(f"  Token/key (for {auth_type}): ").strip()
                    auth = {"type": auth_type, "token": token}
                    if auth_type == "apikey":
                        header_name = input("  Header name [X-API-Key]: ").strip() or "X-API-Key"
                        auth["header_name"] = header_name

                # Confirm and send
                console.print()
                self.display_request(method, path, body=body, params=params, auth=auth)
                confirm = input("Send? [Y/n]: ").strip().lower()
                if confirm in ("n", "no"):
                    console.print("[dim]Skipped.[/dim]")
                    continue

                response = self.send(method, path, body=body, params=params, auth=auth)
                self.display_response(response)

                # Analyze?
                do_analyze = input("\nAnalyze response? [y/N]: ").strip().lower()
                if do_analyze in ("y", "yes"):
                    self.analyze_response(response, method=method, path=path)

                # Save as test?
                do_save = input("Save as pytest test? [y/N]: ").strip().lower()
                if do_save in ("y", "yes"):
                    test_name = input("Test name [captured_test]: ").strip() or "captured_test"
                    self.save_as_test(
                        response=response,
                        test_name=test_name,
                        output_path=output_path,
                        method=method,
                        path=path,
                        body=body,
                        params=params,
                    )

                # Save to collection?
                do_collect = input("Save to collection? [y/N]: ").strip().lower()
                if do_collect in ("y", "yes"):
                    name = input("Request name: ").strip() or f"{method.lower()}_{path.split('/')[-1]}"
                    self.save_collection(name=name, method=method, path=path, body=body, params=params, auth=auth)

                # Show curl?
                do_curl = input("Show curl command? [y/N]: ").strip().lower()
                if do_curl in ("y", "yes"):
                    console.print()
                    console.print(self.to_curl(method, path, body=body, params=params, auth=auth))

            except KeyboardInterrupt:
                console.print("\n[dim]Interrupted — exiting interactive mode.[/dim]")
                break

        console.print("\n[cyan]👋 Goodbye![/cyan]\n")
