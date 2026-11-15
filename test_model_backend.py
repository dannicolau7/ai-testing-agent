"""Which model the tool talks to, and model-proposed requirement links. No network: a fake
model server runs inside the test."""

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

import app_audit
import model_backend
import requirement_links
import traceability

DEMO = Path(__file__).resolve().parent / "examples" / "audit-demo"


class _Server:
    """A stand-in for an OpenAI-compatible model server."""

    def __init__(self, reply, refuse_json_mode=False):
        seen = self.seen = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                seen.append((self.path, self.headers.get("Authorization"), body))
                if refuse_json_mode and "response_format" in body:
                    self.send_response(400)
                    self.end_headers()
                    return
                text = reply(body["messages"][0]["content"]) if callable(reply) else reply
                payload = json.dumps(text if isinstance(text, dict) else
                                     {"choices": [{"message": {"content": text}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def server():
    made = []

    def make(reply, **kwargs):
        made.append(_Server(reply, **kwargs))
        return made[-1]

    yield make
    for s in made:
        s.close()


def test_a_local_model_wins_and_no_setting_means_no_model():
    assert model_backend.resolve(env={}) is None
    local = model_backend.resolve("sk-key", env={"ATA_MODEL_URL": "http://localhost:11434", "ATA_MODEL_NAME": "llama3.2"})
    assert local.kind == "local" and local.base_url == "http://localhost:11434/v1"
    assert local.describe() == "model `llama3.2` on this machine"
    assert model_backend.resolve(env={"ANTHROPIC_API_KEY": "sk-key"}).kind == "anthropic"
    assert model_backend.resolve("sk-key", env={}).kind == "anthropic"
    remote = model_backend.LocalBackend("https://models.example.com/v1", "big")
    assert remote.describe() == "model `big` at models.example.com", "a report must say when prompts leave the machine"


def test_local_backend_speaks_the_chat_protocol(server):
    s = server("  four  ")
    backend = model_backend.LocalBackend(s.url, "tiny", key="secret")
    assert backend.complete("2+2?", max_tokens=5) == "  four  "
    path, auth, body = s.seen[0]
    assert path == "/v1/chat/completions" and auth == "Bearer secret"
    assert body["model"] == "tiny" and body["max_tokens"] == 5 and body["temperature"] == 0
    assert body["messages"] == [{"role": "user", "content": "2+2?"}]


def test_local_backend_retries_without_json_mode_and_reports_failures(server):
    s = server("{}", refuse_json_mode=True)
    assert model_backend.LocalBackend(s.url).complete("x", json_only=True) == "{}"
    assert len(s.seen) == 2 and "response_format" not in s.seen[1][2]
    for bad in ("", {"unexpected": True}):
        with pytest.raises(model_backend.ModelError):
            model_backend.LocalBackend(server(bad).url).complete("x")
    with pytest.raises(model_backend.ModelError, match="Could not reach"):
        model_backend.LocalBackend("http://127.0.0.1:9", timeout=2).complete("x")


class _Fake:
    def __init__(self, answers):
        self.answers, self.prompts = list(answers), []

    def describe(self):
        return "a fake model"

    def complete(self, prompt, max_tokens=0, json_only=False):
        self.prompts.append(prompt)
        return self.answers.pop(0)


def test_the_model_can_only_pick_from_the_list():
    model = app_audit.build_model(str(DEMO))
    reqs = traceability.extract_requirements(
        "REQ-1 List orders.\nREQ-2 Export orders.\nREQ-3 Fly.\nREQ-4 Sing.\nREQ-5 Delete an order.\n")
    fake = _Fake(["1", "0", "99", "POST /api/everything", "Route 4."])
    links = requirement_links.propose(reqs, model, fake)
    assert [(link.id, link.routes) for link in links] == [
        ("REQ-1", ["GET /api/orders"]), ("REQ-2", []), ("REQ-3", []), ("REQ-4", []),
        ("REQ-5", ["DELETE /api/orders/{order_id}"])]
    assert links[2].discarded == ["answer '99'"] and links[3].discarded == ["answer 'POST /api/everything'"]
    assert all(not link.confirmed for link in links), "a model's proposal is never confirmed by the tool"
    # The model is shown names, never source code.
    assert "0. none of these" in fake.prompts[0] and "(function list_orders)" in fake.prompts[0]
    assert "SELECT" not in fake.prompts[0] and "db.execute" not in fake.prompts[0]


def test_only_confirmed_links_are_used_by_the_audit(tmp_path):
    model = app_audit.build_model(str(DEMO))
    reqs = traceability.extract_requirements(
        "REQ-2 A signed-in customer can view an order, but only one of their own.\n"
        "REQ-3 Only a signed-in customer may delete an order.\n"
        "REQ-5 The search index can be rebuilt.\n")
    links = requirement_links.propose(reqs, model, _Fake(["2", "4", "5"]))
    text = requirement_links.dump(links, "a fake model")
    assert "confirmed: false" in text and text.startswith("# Links between requirements and code")

    loaded, problems = requirement_links.load(text)
    assert problems == [] and requirement_links.as_overrides(loaded) == {}
    unconfirmed = app_audit.audit(model, reqs, requirement_links.as_overrides(loaded))
    assert not [f for f in unconfirmed.findings if f.title.startswith("REQ-")]

    # A person confirms two, and adds a check by hand to the third.
    edited = text.replace("confirmed: false", "confirmed: true")
    edited = edited.replace("  - POST /api/admin/reindex\n  checks: []", "  - POST /api/admin/reindex\n  checks: [admin_only, bogus]")
    loaded, problems = requirement_links.load(edited)
    assert problems == ["REQ-5: unknown check(s) bogus ignored"]
    report = app_audit.audit(model, reqs, requirement_links.as_overrides(loaded), problems)
    titles = [f.title for f in report.findings if f.title.startswith("REQ-")]
    assert titles == [
        "REQ-2 limits GET /api/orders/{order_id} to the owner, but the code does not check who owns the row",
        "REQ-3 requires sign-in, but DELETE /api/orders/{order_id} shows no access check",
        "REQ-5 limits POST /api/admin/reindex to administrators, but no role check is visible",
    ]
    assert any("unknown check(s) bogus ignored" in n for n in report.not_examined)


def test_a_broken_links_file_is_reported_not_trusted():
    assert requirement_links.load("links: [")[1][0].startswith("the links file is not valid YAML")
    assert requirement_links.load("nothing: 1")[1] == ["the links file has no `links` list"]
    links, problems = requirement_links.load(
        "links:\n- {routes: [GET /x], confirmed: true}\n- {id: REQ-1, routes: [GET /x], confirmed: 'yes'}\n")
    assert problems == ["an entry without an id was skipped"]
    assert [(link.id, link.confirmed) for link in links] == [("REQ-1", False)], "only a real `true` confirms"


def test_a_confirmed_link_to_a_route_that_is_gone_is_flagged():
    model = app_audit.build_model(str(DEMO))
    reqs = traceability.extract_requirements("REQ-1 Something.\n")
    link = requirement_links.Link("REQ-1", routes=["GET /api/gone"], confirmed=True)
    report = app_audit.audit(model, reqs, {"REQ-1": link})
    assert "The confirmed link for REQ-1 names GET /api/gone, which the backend no longer defines" in [
        f.title for f in report.of("unclear")]


def test_link_command_end_to_end(server, tmp_path):
    s = server(lambda prompt: "2" if "view an order" in prompt else "0")
    out = tmp_path / "links.yaml"
    env = {"PATH": "/usr/bin:/bin", "ATA_MODEL_URL": s.url, "ATA_MODEL_NAME": "tiny", "NO_ANALYTICS": "1"}
    proc = subprocess.run(
        [sys.executable, "cli.py", "link", str(DEMO), "-r", str(DEMO / "requirements-plain.md"), "-o", str(out)],
        capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "model `tiny` on this machine" in proc.stdout and "Proposed links for 1 of 9" in proc.stdout
    out.write_text(out.read_text().replace("confirmed: false", "confirmed: true"))
    audit = subprocess.run(
        [sys.executable, "cli.py", "audit", str(DEMO), "-r", str(DEMO / "requirements-plain.md"), "--links", str(out)],
        capture_output=True, text=True, env=env)
    assert audit.returncode == 1
    assert "REQ-2 limits GET /api/orders/{order_id} to the owner" in audit.stdout

    no_model = subprocess.run(
        [sys.executable, "cli.py", "link", str(DEMO), "-r", str(DEMO / "requirements-plain.md")],
        capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"}, cwd=str(Path(__file__).resolve().parent))
    assert no_model.returncode == 2 and "No model is configured" in no_model.stdout
    assert not (Path(__file__).resolve().parent / "requirement-links.yaml").exists()


def test_the_agent_uses_a_local_model_when_one_is_set(server, monkeypatch):
    s = server("hello from the local model")
    monkeypatch.setenv("ATA_MODEL_URL", s.url)
    monkeypatch.setenv("NO_ANALYTICS", "1")
    from ai_testing_agent import AITestingAgent

    agent = AITestingAgent(verbose=False)
    assert agent._call_ai("anything") == "hello from the local model"
    assert len(s.seen) == 1
