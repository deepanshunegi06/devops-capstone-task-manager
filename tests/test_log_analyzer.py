import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "log_analyzer", Path(__file__).parents[1] / "scripts" / "log_analyzer.py")
log_analyzer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(log_analyzer)


def _records():
    recs = []
    for minute in range(10):                      # quiet baseline: 0-1 errors per minute
        for i in range(20):
            recs.append({"timestamp": f"2026-11-24T10:{minute:02d}:00", "level": "INFO",
                         "message": "request", "status": 200, "duration_ms": 12})
        if minute % 3 == 0:
            recs.append({"timestamp": f"2026-11-24T10:{minute:02d}:30", "level": "ERROR",
                         "message": "unhandled exception", "status": 500})
    for i in range(15):                           # spike at 10:10
        recs.append({"timestamp": "2026-11-24T10:10:05", "level": "ERROR",
                     "message": f"db timeout after {i * 100} ms", "status": 500})
    for _ in range(6):
        recs.append({"timestamp": "2026-11-24T10:11:00", "level": "WARNING",
                     "message": "failed login", "user": "admin"})
    recs.append({"timestamp": "2026-11-24T10:11:00", "level": "INFO", "message": "request",
                 "method": "GET", "path": "/api/tasks", "duration_ms": 900})
    return recs


def test_detects_error_spike_and_patterns():
    report = log_analyzer.analyse(_records())
    assert [a["minute"] for a in report["error_spikes"]] == ["2026-11-24T10:10"]
    patterns = {p["pattern"]: p["count"] for p in report["top_patterns"]}
    assert patterns["db timeout after <NUM> ms"] == 15     # 15 lines -> one template
    assert report["possible_brute_force"] == {"admin": 6}
    assert report["slow_endpoints"] == {"GET /api/tasks": 1}


def test_template_masking():
    assert log_analyzer.template("user 42 hit /api/tasks/7 id=abcdef0123456789abcd") == \
        "user <NUM> hit <PATH> id=<HEX>"


def test_cli_reads_file(tmp_path, capsys):
    import json
    f = tmp_path / "app.log"
    f.write_text("\n".join(json.dumps(r) for r in _records()) + "\nnot json\n")
    assert log_analyzer.main([str(f)]) == 1           # non-zero exit when spikes exist
    assert "Error-rate anomalies" in capsys.readouterr().out
