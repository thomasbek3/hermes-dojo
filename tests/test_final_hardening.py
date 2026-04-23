
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import scripts.fixer as fixer


def test_monitor_returns_json_error_when_db_locked(tmp_path):
    db = tmp_path / "state.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, started_at REAL)")
    con.execute("CREATE TABLE messages (session_id TEXT, role TEXT, content TEXT, tool_calls TEXT, tool_name TEXT, tool_call_id TEXT, timestamp REAL)")
    con.commit()
    con.execute("BEGIN EXCLUSIVE")
    env = os.environ.copy()
    env["HERMES_HOME"] = str(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "monitor.py"), "--json"],
        env=env,
        capture_output=True,
        text=True,
        timeout=3,
    )
    con.rollback(); con.close()
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert "database" in data["error"].lower()
    assert data["data_quality"]["safe_to_autofix"] is False


def test_fix_plan_preserves_investigations():
    recs = [{"action": "investigate", "target": "terminal", "reason": "core tool failure", "priority": 10}]
    plan = fixer.generate_fix_plan(recs)
    assert plan["investigations"][0]["target"] == "terminal"
    assert plan["summary"]["investigations"] == 1


def test_evolution_apply_is_gated_by_owned_skill(monkeypatch, tmp_path):
    monkeypatch.setattr(fixer, "SKILLS_DIR", tmp_path)
    called = []
    monkeypatch.setattr(fixer, "run_evolution", lambda *a, **k: called.append((a, k)) or {"status":"completed","skill":a[0],"iterations":1})
    d = tmp_path / "not-owned"
    d.mkdir()
    (d / "SKILL.md").write_text("---\nname: not-owned\n---\n# x\n")
    plan = {
        "patches": [], "creations": [],
        "evolutions": [{"skill": "not-owned", "target": "not-owned", "skill_path": str(d), "autofix_allowed": True, "iterations": 1}],
        "investigations": [],
    }
    applied = fixer.apply_fixes(plan)
    assert not called
    assert applied[0]["action"] == "skip"
