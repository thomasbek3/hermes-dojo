import json
import os
from pathlib import Path

import scripts.analyzer as analyzer


def test_low_confidence_skill_gap_is_investigate_not_create(monkeypatch, tmp_path):
    monkeypatch.setattr(analyzer, "SKILLS_DIR", tmp_path)
    data = {"weakest_tools": [], "retry_patterns": [], "skill_gaps": [
        {"capability": "docker-management", "requests": 2, "sessions": 2, "confidence": "low"}
    ]}
    recs = analyzer.generate_recommendations(data)
    assert recs[0]["action"] == "investigate"
    assert recs[0]["target"] == "docker-management"


def test_high_confidence_skill_gap_can_create(monkeypatch, tmp_path):
    monkeypatch.setattr(analyzer, "SKILLS_DIR", tmp_path)
    data = {"weakest_tools": [], "retry_patterns": [], "skill_gaps": [
        {"capability": "csv-parsing", "requests": 5, "sessions": 3, "confidence": "high"}
    ]}
    recs = analyzer.generate_recommendations(data)
    assert recs[0]["action"] == "create"


def test_data_quality_blocks_autofix(monkeypatch, tmp_path):
    monkeypatch.setattr(analyzer, "SKILLS_DIR", tmp_path)
    data = {"weakest_tools": [{"tool":"terminal","total":10,"errors":3,"success_rate":70,"top_error":"bad"}],
            "retry_patterns": [], "skill_gaps": [], "data_quality": {"safe_to_autofix": False}}
    recs = analyzer.generate_recommendations(data)
    assert all(not r.get("autofix_allowed") for r in recs)


def test_recovered_tool_failure_becomes_verification_not_patch(monkeypatch, tmp_path):
    skill_dir = tmp_path / "browser-click"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: browser-click\nmetadata:\n  owner: user\n---\n")
    monkeypatch.setattr(analyzer, "SKILLS_DIR", tmp_path)
    data = {"weakest_tools": [{
        "tool": "browser_click",
        "total": 3,
        "errors": 2,
        "success_rate": 33.3,
        "top_error": "SyntaxError: f-string: invalid syntax",
        "status": "recovered",
        "last_success_after_error": True,
    }], "retry_patterns": [], "skill_gaps": [], "data_quality": {"safe_to_autofix": True}}
    recs = analyzer.generate_recommendations(data)
    assert recs[0]["action"] == "investigate"
    assert recs[0]["target"] == "browser-click"
    assert "recovered" in recs[0]["reason"].lower()
    assert recs[0]["autofix_allowed"] is False


def test_stale_tool_failure_becomes_verification_not_patch(monkeypatch, tmp_path):
    skill_dir = tmp_path / "browser-click"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: browser-click\nmetadata:\n  owner: user\n---\n")
    monkeypatch.setattr(analyzer, "SKILLS_DIR", tmp_path)
    data = {"weakest_tools": [{
        "tool": "browser_click",
        "total": 2,
        "errors": 2,
        "success_rate": 0.0,
        "top_error": "SyntaxError: f-string: invalid syntax",
        "status": "stale_failure",
        "last_success_after_error": False,
    }], "retry_patterns": [], "skill_gaps": [], "data_quality": {"safe_to_autofix": True}}
    recs = analyzer.generate_recommendations(data)
    assert recs[0]["action"] == "investigate"
    assert recs[0]["target"] == "browser-click"
    assert "verify current behavior" in recs[0]["reason"]
    assert recs[0]["status"] == "stale_failure"
    assert recs[0]["autofix_allowed"] is False
