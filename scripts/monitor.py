#!/usr/bin/env python3
"""
Hermes Dojo — Performance Monitor

Reads ~/.hermes/state.db to analyze agent performance across recent sessions.
Identifies tool failures, user corrections, retry patterns, and skill gaps.

Usage:
    python3 monitor.py                    # Analyze last 7 days
    python3 monitor.py --days 30          # Analyze last 30 days
    python3 monitor.py --json             # Output as JSON
    python3 monitor.py --session-id X     # Analyze specific session
"""

import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HERMES_HOME = Path(os.getenv("HERMES_HOME", Path.home() / ".hermes"))
DB_PATH = HERMES_HOME / "state.db"

# Patterns that indicate a tool call failure in tool response content
ERROR_PATTERNS = [
    r"(?i)error[:\s]",
    r"(?i)traceback",
    r"(?i)exception[:\s]",
    r"(?i)failed to",
    r"(?i)command not found",
    r"(?i)permission denied",
    r"(?i)no such file",
    r"(?i)timeout",
    r"(?i)connection refused",
    r"(?i)404 not found",
    r"(?i)500 internal",
    r"(?i)rate limit",
    r"(?i)unauthorized",
    r"(?i)access denied",
    r"(?i)ENOENT",
    r"(?i)EACCES",
    r"(?i)ETIMEDOUT",
    r"(?i)could not",
    r"(?i)unable to",
    r"(?i)syntax error",
]

# Patterns in user messages that indicate corrections/dissatisfaction
CORRECTION_PATTERNS = [
    r"(?i)^no[,.\s]",
    r"(?i)wrong",
    r"(?i)not what I",
    r"(?i)I meant",
    r"(?i)that's not",
    r"(?i)please don't",
    r"(?i)stop",
    r"(?i)undo",
    r"(?i)revert",
    r"(?i)you misunderstood",
    r"(?i)incorrect",
    r"(?i)fix (this|that|it)",
    r"(?i)try again",
    r"(?i)that broke",
    r"(?i)doesn't work",
    r"(?i)not working",
    r"(?i)why did you",
]

# Patterns indicating user is repeatedly asking for something (skill gap signal)
REQUEST_PATTERNS = [
    (r"(?i)parse.*csv", "csv-parsing"),
    (r"(?i)format.*json", "json-formatting"),
    (r"(?i)convert.*pdf", "pdf-conversion"),
    (r"(?i)send.*email", "email-sending"),
    (r"(?i)create.*chart", "chart-creation"),
    (r"(?i)scrape.*web", "web-scraping"),
    (r"(?i)deploy", "deployment"),
    (r"(?i)docker", "docker-management"),
    (r"(?i)git.*commit", "git-operations"),
    (r"(?i)test.*unit|unit.*test", "unit-testing"),
    (r"(?i)database|sql|query", "database-operations"),
    (r"(?i)api.*call|fetch.*api|rest.*api", "api-integration"),
]


def classify_tool_result(content: str, tool_name: str = "") -> tuple[bool, str]:
    """Classify a tool result as success/failure with tool-aware JSON handling."""
    if not content:
        return False, ""

    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        payload = None

    if isinstance(payload, dict):
        if payload.get("success") is False or payload.get("status") in {"error", "failed", "failure"}:
            err = payload.get("error") or payload.get("message") or payload.get("output") or "reported failure"
            return True, str(err)[:160].replace("\n", " ")
        exit_code = payload.get("exit_code")
        if payload.get("error"):
            return True, str(payload.get("error"))[:160].replace("\n", " ")
        if isinstance(exit_code, int) and exit_code != 0:
            err = payload.get("error") or payload.get("stderr") or payload.get("output") or ""
            return True, f"exit_code={exit_code} {str(err)[:140]}".strip().replace("\n", " ")

        content_tools = {
            "read_file", "search_files", "skill_view", "skills_list",
            "browser_snapshot", "browser_console", "browser_vision",
            "session_search", "execute_code", "terminal", "write_file",
            "patch", "todo", "memory", "cronjob",
        }
        if tool_name in content_tools:
            return False, ""

        scan_parts = []
        for key in ("error", "stderr"):
            val = payload.get(key)
            if val:
                scan_parts.append(str(val))
        scan_text = "\n".join(scan_parts)
        if not scan_text:
            return False, ""
    else:
        scan_text = content

    for pattern in ERROR_PATTERNS:
        match = re.search(pattern, scan_text)
        if match:
            start = max(0, match.start() - 10)
            end = min(len(scan_text), match.end() + 80)
            snippet = scan_text[start:end].strip().replace("\n", " ")
            return True, snippet

    return False, ""


def _hash_args(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True, default=str)
    return hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest()[:12]


def parse_tool_calls(raw: Any) -> list[dict]:
    """Parse Hermes assistant.tool_calls across OpenAI/Codex storage shapes."""
    if not raw:
        return []
    try:
        calls = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return []
    if isinstance(calls, dict):
        calls = [calls]
    if not isinstance(calls, list):
        return []

    parsed = []
    for call in calls:
        if not isinstance(call, dict):
            continue
        fn = call.get("function") if isinstance(call.get("function"), dict) else {}
        name = call.get("name") or fn.get("name")
        if not name:
            continue
        args = call.get("arguments") or fn.get("arguments") or ""
        parsed.append({
            "id": call.get("id") or call.get("call_id") or call.get("tool_call_id"),
            "name": str(name),
            "args_hash": _hash_args(args),
        })
    return parsed


def iter_tool_results(messages: list[dict]) -> list[dict]:
    """Return tool result records with names resolved from current Hermes schema."""
    pending_by_id: dict[str, dict] = {}
    pending_fifo: dict[str, list[dict]] = defaultdict(list)
    results = []

    for msg in messages:
        role = msg.get("role")
        sid = msg.get("session_id")
        if role == "assistant":
            for call in parse_tool_calls(msg.get("tool_calls")):
                if call.get("id"):
                    pending_by_id[str(call["id"])] = call
                pending_fifo[sid].append(call)
        elif role == "tool":
            tool_name = msg.get("tool_name")
            method = "explicit" if tool_name else "unknown"
            args_hash = ""
            call_id = msg.get("tool_call_id")
            if not tool_name and call_id and str(call_id) in pending_by_id:
                call = pending_by_id[str(call_id)]
                tool_name = call["name"]
                args_hash = call.get("args_hash", "")
                method = "id"
            if not tool_name and pending_fifo.get(sid):
                call = pending_fifo[sid].pop(0)
                tool_name = call["name"]
                args_hash = call.get("args_hash", "")
                method = "fifo"
            if not tool_name:
                tool_name = "unknown"
            row = dict(msg)
            row["resolved_tool_name"] = tool_name
            row["resolution_method"] = method
            row["args_hash"] = args_hash
            results.append(row)
    return results


def detect_retry_patterns(messages: list[dict]) -> list[dict]:
    """Detect likely retry loops: same session + same tool + same args in quick succession."""
    retries = []
    by_session: dict[str, list[dict]] = defaultdict(list)
    for msg in messages:
        by_session[msg.get("session_id")].append(msg)

    for sid, session_messages in by_session.items():
        prev_key = None
        prev_time = 0
        consecutive_count = 0
        for msg in session_messages:
            if msg.get("role") != "assistant":
                continue
            for call in parse_tool_calls(msg.get("tool_calls")):
                key = (call["name"], call.get("args_hash"))
                ts = msg["timestamp"]
                if key == prev_key and (ts - prev_time) < 30:
                    consecutive_count += 1
                else:
                    if consecutive_count >= 2 and prev_key:
                        retries.append({"tool": prev_key[0], "count": consecutive_count + 1, "session_id": sid})
                    consecutive_count = 0
                prev_key = key
                prev_time = ts
        if consecutive_count >= 2 and prev_key:
            retries.append({"tool": prev_key[0], "count": consecutive_count + 1, "session_id": sid})

    return retries


def _is_real_user_task(content: str) -> bool:
    """Filter out cron/system wrappers, pasted transcripts, and huge blobs."""
    if not content:
        return False
    stripped = content.strip()
    if stripped.startswith("[SYSTEM:") or stripped.startswith("[System note:"):
        return False
    if "<memory-context>" in stripped or "Conversation started:" in stripped:
        return False
    if len(stripped) > 1800:
        return False
    return True


def analyze_sessions(days: int = 7, session_id: str = None) -> dict[str, Any]:
    """Analyze recent sessions for performance metrics."""
    if not DB_PATH.exists():
        return {"error": f"Database not found at {DB_PATH}"}

    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=0.25)
        conn.row_factory = sqlite3.Row

        cutoff = time.time() - (days * 86400)

        # Get sessions
        if session_id:
            sessions = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchall()
        else:
            sessions = conn.execute(
                "SELECT * FROM sessions WHERE started_at > ? ORDER BY started_at DESC",
                (cutoff,),
            ).fetchall()

        if not sessions:
            conn.close()
            return {
                "sessions_analyzed": 0,
                "message": "No sessions found in the specified time range.",
                "data_quality": {"safe_to_autofix": False},
            }

        session_ids = [s["id"] for s in sessions]
        placeholders = ",".join("?" for _ in session_ids)

        # Get all messages for these sessions
        messages = conn.execute(
            f"SELECT * FROM messages WHERE session_id IN ({placeholders}) ORDER BY timestamp",
            session_ids,
        ).fetchall()
        messages = [dict(m) for m in messages]
        conn.close()
    except sqlite3.OperationalError as exc:
        return {
            "error": f"Database unavailable: {exc}",
            "sessions_analyzed": 0,
            "total_tool_calls": 0,
            "total_errors": 0,
            "overall_success_rate": 0.0,
            "weakest_tools": [],
            "tool_stats": {},
            "user_corrections": 0,
            "correction_samples": [],
            "retry_patterns": [],
            "skill_gaps": [],
            "total_messages": 0,
            "data_quality": {"safe_to_autofix": False, "error": str(exc)},
        }

    # === Analyze tool calls ===
    tool_stats = defaultdict(lambda: {
        "total": 0,
        "errors": 0,
        "error_types": Counter(),
        "first_error_at": None,
        "last_error_at": None,
        "last_success_at": None,
    })
    all_errors = []
    tool_results = iter_tool_results(messages)

    for msg in tool_results:
        tool_name = msg["resolved_tool_name"]
        stats = tool_stats[tool_name]
        stats["total"] += 1
        timestamp = msg.get("timestamp") or 0

        is_error, error_type = classify_tool_result(msg.get("content", ""), tool_name)
        if is_error:
            stats["errors"] += 1
            stats["error_types"][error_type] += 1
            stats["first_error_at"] = timestamp if stats["first_error_at"] is None else min(stats["first_error_at"], timestamp)
            stats["last_error_at"] = timestamp if stats["last_error_at"] is None else max(stats["last_error_at"], timestamp)
            all_errors.append({
                "tool": tool_name,
                "error": error_type,
                "session_id": msg["session_id"],
                "timestamp": timestamp,
            })
        else:
            stats["last_success_at"] = timestamp if stats["last_success_at"] is None else max(stats["last_success_at"], timestamp)

    # === Analyze user corrections ===
    corrections = []
    for msg in messages:
        if msg["role"] == "user" and msg.get("content") and _is_real_user_task(msg["content"]):
            content = msg["content"]
            for pattern in CORRECTION_PATTERNS:
                if re.search(pattern, content):
                    corrections.append({
                        "content": content[:100],
                        "pattern": pattern,
                        "session_id": msg["session_id"],
                        "timestamp": msg["timestamp"],
                    })
                    break

    # === Detect skill gaps ===
    skill_gaps = defaultdict(lambda: {"count": 0, "sessions": set(), "samples": []})
    for msg in messages:
        if msg["role"] == "user" and msg.get("content") and _is_real_user_task(msg["content"]):
            for pattern, gap_name in REQUEST_PATTERNS:
                if re.search(pattern, msg["content"]):
                    entry = skill_gaps[gap_name]
                    entry["count"] += 1
                    entry["sessions"].add(msg["session_id"])
                    if len(entry["samples"]) < 3:
                        entry["samples"].append(msg["content"][:120])

    # === Detect retry patterns ===
    retries = detect_retry_patterns(messages)

    # === Compute summary ===
    total_tool_calls = sum(s["total"] for s in tool_stats.values())
    total_errors = sum(s["errors"] for s in tool_stats.values())
    overall_success = (
        round((1 - total_errors / total_tool_calls) * 100, 1)
        if total_tool_calls > 0
        else 100.0
    )

    # Rank tools by failure rate
    weakest_tools = []
    for tool_name, stats in sorted(
        tool_stats.items(),
        key=lambda x: x[1]["errors"] / max(x[1]["total"], 1),
        reverse=True,
    ):
        if stats["errors"] > 0:
            success_rate = round((1 - stats["errors"] / stats["total"]) * 100, 1)
            top_error = stats["error_types"].most_common(1)
            last_error_at = stats.get("last_error_at")
            last_success_at = stats.get("last_success_at")
            last_success_after_error = (
                last_error_at is not None
                and last_success_at is not None
                and last_success_at > last_error_at
            )
            stale_failure = (
                not last_success_after_error
                and last_error_at is not None
                and time.time() - last_error_at > 24 * 3600
            )
            status = "recovered" if last_success_after_error else "stale_failure" if stale_failure else "active_failure"
            weakest_tools.append({
                "tool": tool_name,
                "total": stats["total"],
                "errors": stats["errors"],
                "success_rate": success_rate,
                "top_error": top_error[0][0] if top_error else "",
                "first_error_at": stats.get("first_error_at"),
                "last_error_at": last_error_at,
                "last_success_at": last_success_at,
                "last_success_after_error": last_success_after_error,
                "status": status,
            })

    # Skill gaps require stronger evidence than a keyword appearing twice.
    recurring_gaps = [
        {
            "capability": name,
            "requests": data["count"],
            "sessions": len(data["sessions"]),
            "samples": data["samples"],
            "confidence": "high" if data["count"] >= 5 and len(data["sessions"]) >= 3 else "low",
        }
        for name, data in sorted(skill_gaps.items(), key=lambda item: item[1]["count"], reverse=True)
        if data["count"] >= 2
    ][:10]

    declared_tool_calls = sum(int(s["tool_call_count"] or 0) for s in sessions)
    resolution_counts = Counter(r.get("resolution_method", "unknown") for r in tool_results)
    low_confidence_resolutions = resolution_counts.get("fifo", 0) + resolution_counts.get("unknown", 0)
    session_tool_mismatches = []
    actual_by_session = Counter(r["session_id"] for r in tool_results)
    for s in sessions:
        declared = int(s["tool_call_count"] or 0)
        actual = actual_by_session.get(s["id"], 0)
        if declared != actual:
            session_tool_mismatches.append({"session_id": s["id"], "declared": declared, "actual": actual})

    result = {
        "timestamp": time.time(),
        "days_analyzed": days,
        "sessions_analyzed": len(sessions),
        "total_tool_calls": total_tool_calls,
        "total_errors": total_errors,
        "overall_success_rate": overall_success,
        "weakest_tools": weakest_tools[:10],
        "tool_stats": {
            name: {
                "total": stats["total"],
                "errors": stats["errors"],
                "success_rate": round((1 - stats["errors"] / max(stats["total"], 1)) * 100, 1),
            }
            for name, stats in sorted(tool_stats.items())
        },
        "user_corrections": len(corrections),
        "correction_samples": corrections[:5],
        "retry_patterns": retries,
        "skill_gaps": recurring_gaps,
        "total_messages": len(messages),
        "data_quality": {
            "declared_tool_calls": declared_tool_calls,
            "actual_tool_result_rows": len(tool_results),
            "tool_call_count_delta": len(tool_results) - declared_tool_calls,
            "resolution_counts": dict(resolution_counts),
            "low_confidence_resolutions": low_confidence_resolutions,
            "low_confidence_resolution_rate": round(low_confidence_resolutions / max(len(tool_results), 1), 4),
            "session_tool_mismatches": session_tool_mismatches[:20],
            "safe_to_autofix": (
                total_tool_calls > 0
                and len(sessions) >= 5
                and len(tool_results) >= 50
                and low_confidence_resolutions / max(len(tool_results), 1) <= 0.02
            ),
        },
        "sessions": [
            {
                "id": s["id"],
                "source": s["source"],
                "model": s["model"],
                "tool_calls": s["tool_call_count"],
                "messages": s["message_count"],
                "started_at": s["started_at"],
            }
            for s in sessions[:20]
        ],
    }

    return result


def print_dashboard(data: dict):
    """Print a human-readable dashboard."""
    if "error" in data:
        print(f"Error: {data['error']}")
        return

    if data["sessions_analyzed"] == 0:
        print(data.get("message", "No sessions found."))
        return

    print("=" * 60)
    print("  HERMES DOJO — PERFORMANCE ANALYSIS")
    print("=" * 60)
    print(f"  Sessions analyzed:  {data['sessions_analyzed']} (last {data['days_analyzed']} days)")
    print(f"  Total tool calls:   {data['total_tool_calls']}")
    print(f"  Total messages:     {data['total_messages']}")
    print(f"  Overall success:    {data['overall_success_rate']}%")
    print()

    if data["weakest_tools"]:
        print("  TOP WEAKNESSES:")
        print("  " + "-" * 56)
        for i, tool in enumerate(data["weakest_tools"][:5], 1):
            print(f"  {i}. {tool['tool']}: {tool['success_rate']}% success "
                  f"({tool['errors']}/{tool['total']} failures)")
            if tool["top_error"]:
                print(f"     → {tool['top_error'][:60]}")
        print()

    if data["user_corrections"] > 0:
        print(f"  USER CORRECTIONS: {data['user_corrections']}")
        for c in data["correction_samples"][:3]:
            print(f"     • \"{c['content'][:50]}...\"")
        print()

    if data["skill_gaps"]:
        print("  SKILL GAPS DETECTED:")
        for gap in data["skill_gaps"]:
            print(f"     • {gap['capability']}: requested {gap['requests']}x, no skill exists")
        print()

    if data["retry_patterns"]:
        print(f"  RETRY LOOPS: {len(data['retry_patterns'])}")
        for r in data["retry_patterns"][:3]:
            print(f"     • {r['tool']}: called {r['count']}x in rapid succession")
        print()

    print("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Hermes Dojo Performance Monitor")
    parser.add_argument("--days", type=int, default=7, help="Days to analyze (default: 7)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--session-id", type=str, help="Analyze specific session")
    args = parser.parse_args()

    data = analyze_sessions(days=args.days, session_id=args.session_id)

    if args.json:
        # Make Counter objects serializable
        print(json.dumps(data, indent=2, default=str))
    else:
        print_dashboard(data)
