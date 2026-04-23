import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def _make_db(home: Path):
    db = home / "state.db"
    con = sqlite3.connect(db)
    con.execute("""CREATE TABLE sessions (
        id TEXT PRIMARY KEY, source TEXT, user_id TEXT, model TEXT, model_config TEXT,
        system_prompt TEXT, parent_session_id TEXT, started_at REAL, ended_at REAL,
        end_reason TEXT, message_count INTEGER, tool_call_count INTEGER
    )""")
    con.execute("""CREATE TABLE messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT,
        tool_call_id TEXT, tool_calls TEXT, tool_name TEXT, timestamp REAL,
        token_count INTEGER, finish_reason TEXT, reasoning TEXT, reasoning_details TEXT,
        codex_reasoning_items TEXT, reasoning_content TEXT
    )""")
    return con


def test_counts_current_hermes_tool_results_without_tool_name(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    import importlib, monitor
    importlib.reload(monitor)
    con = _make_db(tmp_path)
    sid = "s1"
    now = time.time()
    con.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (sid, "telegram", None, "gpt", "{}", "", None, now, None, None, 4, 2))
    calls = [
        {"id": "call_1", "type": "function", "function": {"name": "terminal", "arguments": "{}"}},
        {"id": "call_2", "type": "function", "function": {"name": "read_file", "arguments": "{}"}},
    ]
    con.execute("INSERT INTO messages (session_id, role, content, tool_calls, timestamp) VALUES (?,?,?,?,?)", (sid, "assistant", "", json.dumps(calls), now+1))
    con.execute("INSERT INTO messages (session_id, role, content, tool_call_id, timestamp) VALUES (?,?,?,?,?)", (sid, "tool", '{"output":"ok"}', "call_1", now+2))
    con.execute("INSERT INTO messages (session_id, role, content, tool_call_id, timestamp) VALUES (?,?,?,?,?)", (sid, "tool", '{"error":"no such file"}', "call_2", now+3))
    con.commit(); con.close()

    data = monitor.analyze_sessions(days=1)
    assert data["total_tool_calls"] == 2
    assert data["total_errors"] == 1
    assert data["overall_success_rate"] == 50.0
    assert data["tool_stats"]["terminal"]["total"] == 1
    assert data["tool_stats"]["read_file"]["errors"] == 1


def test_counts_tool_calls_from_assistant_when_results_lack_ids(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    import importlib, monitor
    importlib.reload(monitor)
    con = _make_db(tmp_path)
    sid = "s2"
    now = time.time()
    con.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (sid, "telegram", None, "gpt", "{}", "", None, now, None, None, 3, 1))
    calls = [{"id": "call_1", "function": {"name": "search_files", "arguments": "{}"}}]
    con.execute("INSERT INTO messages (session_id, role, content, tool_calls, timestamp) VALUES (?,?,?,?,?)", (sid, "assistant", "", json.dumps(calls), now+1))
    con.execute("INSERT INTO messages (session_id, role, content, timestamp) VALUES (?,?,?,?)", (sid, "tool", '{"total_count": 0}', now+2))
    con.commit(); con.close()
    data = monitor.analyze_sessions(days=1)
    assert data["total_tool_calls"] == 1
    assert data["tool_stats"]["search_files"]["total"] == 1
