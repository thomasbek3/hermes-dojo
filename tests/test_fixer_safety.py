from pathlib import Path

import scripts.fixer as fixer


def _skill(path: Path, name="owned", meta="owner: user"):
    d = path / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\nmetadata:\n  hermes:\n    {meta}\n---\n# Skill\n")
    return d


def test_run_evolution_uses_codex_oauth_dry_run():
    r = fixer.run_evolution("hermes-dojo", iterations=1, dry_run=True)
    assert "openai-codex/gpt-5.4" in r["command"]
    assert "OPENROUTER" not in r["command"]
    assert "openrouter" not in r["command"]


def test_apply_skips_unowned_skill_patch(monkeypatch, tmp_path):
    monkeypatch.setattr(fixer, "SKILLS_DIR", tmp_path)
    d = _skill(tmp_path, "not-owned", "tags: [x]")
    plan = {"patches": [{"target":"not-owned", "skill_path": str(d), "skill_addition":"## Unsafe", "patch_description":"x", "error_type":"generic"}], "creations": [], "evolutions": []}
    applied = fixer.apply_fixes(plan)
    assert applied[0]["action"] == "skip"
    assert "Unsafe" not in (d / "SKILL.md").read_text()


def test_apply_patches_owned_skill_with_backup(monkeypatch, tmp_path):
    monkeypatch.setattr(fixer, "SKILLS_DIR", tmp_path)
    d = _skill(tmp_path, "owned", "owner: user")
    plan = {"patches": [{"target":"owned", "skill_path": str(d), "skill_addition":"## Safe", "patch_description":"x", "error_type":"generic", "autofix_allowed": True}], "creations": [], "evolutions": []}
    applied = fixer.apply_fixes(plan)
    assert applied
    assert "## Safe" in (d / "SKILL.md").read_text()
    assert list(d.glob("SKILL.md.bak.*"))
