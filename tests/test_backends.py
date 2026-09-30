import json
import socket
import sys
import threading
import time
import types
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import pytest

from wagtail_laya import backends
from wagtail_laya.backends import LocalBackend, ServiceBackend
from wagtail_laya.errors import LayaError, LayaUnavailable

QUESTIONS = {"q": {"type": "noul", "instructions": "about 'a'?"}}
PAYLOAD = {"model": "english", "answers": {"q": {"type": "noul", "noul": 0.5, "answer_confidence": 0.9}}}


class FakeRouter:
    def __init__(self, fail=None):
        self.calls = []
        self.fail = fail

    def predict(self, state, questions, model=None):
        self.calls.append((state, questions, model))
        if self.fail:
            raise self.fail
        return PAYLOAD


@pytest.fixture
def fake_laya(monkeypatch):
    """A stand-in ``laya`` module whose Router() records every instance it builds."""
    created = []
    module = types.ModuleType("laya")

    def Router():
        time.sleep(0.05)  # widen the race window for the concurrency test
        router = FakeRouter()
        created.append(router)
        return router

    module.Router = Router
    monkeypatch.setitem(sys.modules, "laya", module)
    monkeypatch.setattr(backends, "_router", None)
    return created


def test_local_backend_passes_state_questions_and_model_through(fake_laya):
    assert LocalBackend().predict({"x": 1}, QUESTIONS, model="multilingual") == PAYLOAD
    assert fake_laya[0].calls == [({"x": 1}, QUESTIONS, "multilingual")]


def test_local_backend_loads_the_model_once_per_process(fake_laya):
    LocalBackend().predict({}, QUESTIONS)
    LocalBackend().predict({}, QUESTIONS)
    assert len(fake_laya) == 1
    assert len(fake_laya[0].calls) == 2


def test_concurrent_first_requests_load_the_model_once(fake_laya):
    threads = [threading.Thread(target=LocalBackend().predict, args=({}, QUESTIONS)) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(fake_laya) == 1
    assert len(fake_laya[0].calls) == 8


def test_missing_laya_names_the_local_extra(monkeypatch):
    monkeypatch.setitem(sys.modules, "laya", None)  # makes `import laya` raise ImportError
    monkeypatch.setattr(backends, "_router", None)
    with pytest.raises(LayaError, match=r'wagtail-laya\[local\]'):
        LocalBackend().predict({}, QUESTIONS)


def test_prediction_errors_become_laya_errors(fake_laya, monkeypatch):
    monkeypatch.setattr(backends, "_router", FakeRouter(fail=ValueError("question 'q' has no criteria")))
    with pytest.raises(LayaError, match="question 'q' has no criteria"):
        LocalBackend().predict({}, QUESTIONS)


@pytest.fixture
def laya_server():
    """A real HTTP server on localhost that records requests and sends a configurable reply."""
    received = []
    reply = {"status": 200, "body": PAYLOAD}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers["Content-Length"])
            received.append(
                {
                    "path": self.path,
                    "auth": self.headers.get("Authorization"),
                    "body": json.loads(self.rfile.read(length)),
                }
            )
            body = reply["body"]
            raw = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(reply["status"])
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield SimpleNamespace(url=f"http://127.0.0.1:{server.server_port}", received=received, reply=reply)
    server.shutdown()
    server.server_close()


def test_service_posts_state_questions_model_and_key(laya_server):
    backend = ServiceBackend(laya_server.url + "/", api_key="secret", timeout=5)

    assert backend.url == laya_server.url + "/v1/systemone"
    assert backend.predict({"x": 1}, QUESTIONS, model="multilingual") == PAYLOAD
    assert laya_server.received == [
        {
            "path": "/v1/systemone",
            "auth": "Bearer secret",
            "body": {"state": {"x": 1}, "questions": QUESTIONS, "model": "multilingual"},
        }
    ]


def test_service_omits_model_and_key_when_unset(laya_server):
    ServiceBackend(laya_server.url, timeout=5).predict("text", QUESTIONS)
    assert laya_server.received[0]["auth"] is None
    assert laya_server.received[0]["body"] == {"state": "text", "questions": QUESTIONS}


def test_service_http_errors_carry_the_servers_detail(laya_server):
    laya_server.reply.update(status=413, body={"detail": "too many questions (65 > 64)"})
    with pytest.raises(LayaError, match=r"413.*too many questions \(65 > 64\)"):
        ServiceBackend(laya_server.url, timeout=5).predict({}, QUESTIONS)


def test_service_invalid_json_is_a_laya_error(laya_server):
    laya_server.reply.update(body=b"<html>proxy error</html>")
    with pytest.raises(LayaError, match="invalid JSON"):
        ServiceBackend(laya_server.url, timeout=5).predict({}, QUESTIONS)


def test_unreachable_service_is_a_laya_error():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]  # closed on exit: nothing listens here
    with pytest.raises(LayaError, match="Could not reach Laya"):
        ServiceBackend(f"http://127.0.0.1:{port}", timeout=2).predict({}, QUESTIONS)


def test_a_non_http_answer_is_a_laya_error():
    # e.g. WAGTAIL_LAYA_URL pointing at Redis or SSH: urllib raises http.client errors, not OSError.
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        port = server.getsockname()[1]

        def answer_garbage():
            conn, _ = server.accept()
            conn.recv(65536)
            conn.sendall(b"NOT HTTP AT ALL\r\n\r\n")
            conn.close()

        thread = threading.Thread(target=answer_garbage, daemon=True)
        thread.start()
        with pytest.raises(LayaError, match="invalid response"):
            ServiceBackend(f"http://127.0.0.1:{port}", timeout=5).predict({}, QUESTIONS)
        thread.join(timeout=5)


def test_laya_failing_to_start_is_a_laya_error(monkeypatch):
    module = types.ModuleType("laya")

    def Router():
        raise ValueError("LAYA_DEVICE 'tpu' is not a torch device")

    module.Router = Router
    monkeypatch.setitem(sys.modules, "laya", module)
    monkeypatch.setattr(backends, "_router", None)
    with pytest.raises(LayaUnavailable, match="could not start.*tpu"):
        LocalBackend().predict({}, QUESTIONS)


def test_a_broken_laya_install_is_a_laya_error(monkeypatch):
    # e.g. a libtorch dylib that fails to load raises OSError, not ImportError.
    import builtins

    real_import = builtins.__import__

    def broken_import(name, *args, **kwargs):
        if name == "laya":
            raise OSError("dlopen(libtorch_cpu.dylib): image not found")
        return real_import(name, *args, **kwargs)

    monkeypatch.delitem(sys.modules, "laya", raising=False)
    monkeypatch.setattr(builtins, "__import__", broken_import)
    monkeypatch.setattr(backends, "_router", None)
    with pytest.raises(LayaUnavailable, match="could not start.*libtorch"):
        LocalBackend().predict({}, QUESTIONS)


def test_missing_laya_and_unreachable_servers_mean_laya_is_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "laya", None)
    monkeypatch.setattr(backends, "_router", None)
    with pytest.raises(LayaUnavailable):
        LocalBackend().predict({}, QUESTIONS)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    with pytest.raises(LayaUnavailable):
        ServiceBackend(f"http://127.0.0.1:{port}", timeout=2).predict({}, QUESTIONS)
