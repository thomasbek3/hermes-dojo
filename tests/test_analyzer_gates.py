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
