"""A small made-up shop site with planted problems, for `python cli.py browse`.

    python examples/browser-demo/server.py 8765
    python cli.py browse http://127.0.0.1:8765

Standard library only. Every "dangerous" action here only counts how often it was called.
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAGES = {
    "/": """<h1>Shop</h1>
        <a href="/orders">Orders</a> <a href="/reports">Reports</a> <a href="/help">Help</a>
        <a href="/account">Account</a> <a href="/old-page">Old page</a> <a href="/orders#top">Orders again</a>
        <a href="mailto:x@example.com">Mail</a>""",
    # Works: loads its data from an API route that exists.
    "/orders": """<h1>Orders</h1><ul id="list"></ul>
        <button id="refresh">Refresh</button> <button id="delete">Delete all orders</button>
        <form><button type="submit">Save</button></form>
        <script>
        const load = () => fetch('/api/orders').then(r => r.json()).then(d => { list.innerHTML = d.map(o => '<li>' + o.id).join('') });
        load();
        refresh.onclick = () => fetch('/api/orders/7');
        document.getElementById('delete').onclick = () => fetch('/api/orders', {method: 'DELETE'});
        </script>""",
    # Planted: calls a route the backend does not have, and one that fails.
    "/reports": """<h1>Reports</h1>
        <script>fetch('/api/reports/summary'); fetch('/api/reports/slow');</script>""",
    # Planted: an uncaught error and a console error.
    "/help": """<h1>Help</h1><script>console.error('help text failed to load'); notDefined.call();</script>""",
    # Needs sign-in.
    "/account": """<h1>Account</h1><script>fetch('/api/me');</script>""",
    # For `python cli.py journey`. Not linked from the home page, so `browse` does not reach it.
    # Saving works. Renaming is planted: the page shows the new title but the server keeps the old one.
    # Archiving is planted: the page says "Archived" although the server has no such route.
    "/notes": """<h1>Notes</h1>
        <label>Title <input id="title"></label> <button id="save">Save</button>
        <label>New title <input id="newtitle"></label> <button id="rename">Rename first note</button>
        <button id="archive">Archive all</button>
        <p id="msg"></p><ul id="list"></ul>
        <script>
        const show = (notes) => { list.innerHTML = notes.map(n => '<li>' + n).join('') };
        const load = () => fetch('/api/notes').then(r => r.json()).then(show);
        const post = (url, body) => fetch(url, {method: 'POST', body: JSON.stringify(body)});
        save.onclick = () => post('/api/notes', {title: title.value}).then(load);
        rename.onclick = () => post('/api/notes/rename', {title: newtitle.value})
            .then(() => { list.firstChild.textContent = newtitle.value; msg.textContent = 'Renamed'; });
        archive.onclick = () => post('/api/notes/archive', {}).then(() => { msg.textContent = 'Archived'; });
        load();
        </script>""",
}
calls = {"delete_all": 0}
notes = ["First note"]


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, kind="application/json"):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        path = self.path.split("?")[0]
        if path in PAGES:
            self._send(200, "<!doctype html><title>Shop</title>" + PAGES[path], "text/html")
        elif path == "/api/orders":
            self._send(200, json.dumps([{"id": 7}, {"id": 8}]))
        elif path.startswith("/api/orders/"):
            self._send(200, json.dumps({"id": 7}))
        elif path == "/api/reports/slow":
            self._send(500, json.dumps({"error": "boom"}))
        elif path == "/api/me":
            signed_in = self.headers.get("Authorization") == "Bearer demo-token"
            self._send(200 if signed_in else 401, json.dumps({"name": "demo"} if signed_in else {"error": "sign in"}))
        elif path == "/api/notes":
            self._send(200, json.dumps(notes))
        elif path == "/api/_calls":
            self._send(200, json.dumps(calls))
        else:
            self._send(404, "<h1>Not found</h1>", "text/html")

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/api/notes":
            notes.append(str(body.get("title", "")))
            self._send(201, json.dumps({"ok": True}))
        elif self.path == "/api/notes/rename":
            self._send(200, json.dumps({"ok": True}))      # planted: answers "ok" and stores nothing
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_DELETE(self):  # noqa: N802
        calls["delete_all"] += 1
        self._send(204, "")

    def log_message(self, *args):
        pass


def make_server(port=0):
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    server = make_server(int(sys.argv[1]) if len(sys.argv) > 1 else 8765)
    print(f"http://127.0.0.1:{server.server_port}")
    server.serve_forever()
