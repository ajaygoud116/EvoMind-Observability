"""Failure injection validation script. Run with: python ops/_validate_failure.py"""
from __future__ import annotations

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["EVOMIND_OTEL_ENABLED"] = "false"

from fastapi.testclient import TestClient
from evomind.config.settings import Settings
from evomind.app import create_app


def _db() -> str:
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    return f.name


def _clean(db_path: str) -> None:
    """Safely remove a database file with retry."""
    import time
    for _ in range(3):
        try:
            os.unlink(db_path)
            return
        except PermissionError:
            time.sleep(0.1)
    print(f"    [WARN] Could not remove {db_path}")


def test_empty_prompt() -> None:
    db = _db()
    s = Settings(database_path=db, otel_enabled=False)
    app = create_app(s)
    c = TestClient(app)
    r = c.post("/api/query", json={"prompt": ""})
    assert r.status_code == 422
    print(f"  [PASS] Empty prompt = 422")
    app.state.lifecycle.shutdown()
    _clean(db)


def test_missing_prompt() -> None:
    db = _db()
    s = Settings(database_path=db, otel_enabled=False)
    app = create_app(s)
    c = TestClient(app)
    r = c.post("/api/query", json={})
    assert r.status_code == 422
    print(f"  [PASS] Missing prompt = 422")
    app.state.lifecycle.shutdown()
    _clean(db)


def test_whitespace_prompt() -> None:
    db = _db()
    s = Settings(database_path=db, otel_enabled=False)
    app = create_app(s)
    c = TestClient(app)
    r = c.post("/api/query", json={"prompt": "   "})
    assert r.status_code == 422
    print(f"  [PASS] Whitespace prompt = 422")
    app.state.lifecycle.shutdown()
    _clean(db)


def test_none_prompt() -> None:
    db = _db()
    s = Settings(database_path=db, otel_enabled=False)
    app = create_app(s)
    c = TestClient(app)
    r = c.post("/api/query", json={"prompt": None})
    assert r.status_code == 422
    print(f"  [PASS] None prompt = 422")
    app.state.lifecycle.shutdown()
    _clean(db)


def test_health() -> None:
    db = _db()
    s = Settings(database_path=db, otel_enabled=False)
    app = create_app(s)
    c = TestClient(app)
    r = c.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    print(f"  [PASS] Health = 200")
    app.state.lifecycle.shutdown()
    _clean(db)


def test_normal_request() -> None:
    db = _db()
    s = Settings(database_path=db, otel_enabled=False)
    app = create_app(s)
    c = TestClient(app)
    r = c.post("/api/query", json={"prompt": "show me users"})
    assert r.status_code == 200
    j = r.json()
    assert j["classification"] in ("safe", "unsafe", "ambiguous")
    assert isinstance(j["confidence"], float)
    print(f"  [PASS] Normal request = 200, class={j['classification']}, conf={j['confidence']:.2f}")
    app.state.lifecycle.shutdown()
    _clean(db)


def test_100_requests() -> None:
    db = _db()
    s = Settings(database_path=db, otel_enabled=False)
    app = create_app(s)
    c = TestClient(app)
    prompts = [
        "show me users", "delete user with id 1",
        "insert into orders values (1, 2)", "drop table users",
        "select * from products where price > 10",
    ]
    start = time.time()
    for i in range(100):
        r = c.post("/api/query", json={"prompt": prompts[i % len(prompts)]})
        assert r.status_code == 200
    elapsed = time.time() - start
    print(f"  [PASS] 100 requests in {elapsed:.2f}s ({elapsed/100*1000:.1f}ms/req)")
    app.state.lifecycle.shutdown()
    _clean(db)


def test_otel_unavailable() -> None:
    db = _db()
    s = Settings(database_path=db, otel_enabled=True,
                 otel_exporter_endpoint="http://localhost:1")
    app = create_app(s)
    c = TestClient(app)
    r = c.post("/api/query", json={"prompt": "show me users"})
    assert r.status_code == 200
    print(f"  [PASS] OTEL unreachable = still works")
    app.state.lifecycle.shutdown()
    _clean(db)


def test_startup_twice() -> None:
    db1, db2 = _db(), _db()
    app1 = create_app(Settings(database_path=db1, otel_enabled=False))
    app2 = create_app(Settings(database_path=db2, otel_enabled=False))
    r1 = TestClient(app1).post("/api/query", json={"prompt": "show me users"})
    r2 = TestClient(app2).post("/api/query", json={"prompt": "delete user with id 5"})
    assert r1.status_code == 200
    assert r2.status_code == 200
    print(f"  [PASS] Two independent apps work")
    app1.state.lifecycle.shutdown()
    app2.state.lifecycle.shutdown()
    _clean(db1)
    _clean(db2)


if __name__ == "__main__":
    tests = [
        ("Health endpoint", test_health),
        ("Empty prompt", test_empty_prompt),
        ("Missing prompt", test_missing_prompt),
        ("Whitespace prompt", test_whitespace_prompt),
        ("None prompt", test_none_prompt),
        ("Normal request", test_normal_request),
        ("100 sequential requests", test_100_requests),
        ("OTEL collector unavailable", test_otel_unavailable),
        ("Two independent apps", test_startup_twice),
    ]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    print(f"\nResults: {passed} passed, {failed} failed, {len(tests)} total")
    sys.exit(1 if failed else 0)
