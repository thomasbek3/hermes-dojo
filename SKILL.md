---
name: hermes-dojo
description: >
  Continuous self-improvement system for Hermes Agent. Analyzes your past sessions
  to find recurring failures and skill gaps, then automatically creates or patches
  skills and runs self-evolution to fix them. Set it to run overnight and wake up
  to a better agent. Use /dojo to start.
version: 1.0.0
license: MIT
metadata:
  author: yonko
  hermes:
    tags: [self-improvement, self-evolution, analytics, meta-agent]
    category: agent-improvement
    requires_toolsets: [terminal]
allowed-tools: Bash(python3:*) Read Write skill_manage delegate_task session_search memory
---

## Overview

Hermes Dojo is your agent's training gym. It reads your past sessions, finds where
the agent struggles, creates or improves skills to fix those weaknesses, and tracks
improvement over time.

The core loop: **measure → identify weakness → fix → evolve → verify → report**

## Commands

- `/dojo` or `/dojo analyze` — Analyze recent sessions for failure patterns
- `/dojo improve` — Fix the top weaknesses (patch skills + run self-evolution)
- `/dojo report` — Show current performance metrics and improvement history
- `/dojo history` — Show learning curve over time
- `/dojo auto` — Set up overnight cron: analyze + improve + report at 6am
- `/dojo status` — Quick summary of agent health

## Workflow

### Step 1: Analyze

Run `python3 ~/.hermes/skills/hermes-dojo/scripts/monitor.py` to scan recent sessions.

This reads `~/.hermes/state.db` and produces a JSON report with:
- Per-tool success/failure rates
- Error patterns (grouped by tool and error type)
- User correction signals (messages containing "no,", "wrong", "I meant", "not what I")
- Skill gap detection (repeated manual tasks with no skill)
- Session-level metrics (tool calls per session, retry patterns)

Present the results as a clear dashboard:

```
=== Hermes Dojo Analysis ===
Sessions analyzed: 23 (last 7 days)
Total tool calls: 156
Overall success rate: 78%

Top Weaknesses:
1. terminal_run: 73% success (12 failures) — common error: "command not found"
2. web_extract: 81% success (4 failures) — common error: "timeout"
3. No skill for: CSV parsing (requested 4 times)

User Corrections Detected: 7
- 3x wrong file path
- 2x wrong command syntax
- 2x misunderstood request
```

### Step 2: Improve

For each identified weakness, decide the fix:

**A) Existing skill fails → patch it:**
1. Read the current skill's SKILL.md
2. Analyze the failure patterns from Step 1
3. Use `skill_manage` with action "patch" to add error handling, better instructions, or edge case coverage
4. Log the change

**B) No skill exists for a recurring need → create one:**
1. Analyze the session patterns where this capability was needed
2. Use `skill_manage` with action "create" to make a new skill
3. Include specific instructions based on what worked in past sessions
4. Log the creation

**C) Skill exists but needs deeper improvement → run self-evolution:**
1. Run: `cd ~/.hermes/hermes-agent-self-evolution && .venv/bin/python3 -m evolution.skills.evolve_skill --skill <name> --hermes-repo ~/.hermes --iterations 5 --eval-source synthetic`
2. This uses GEPA to analyze execution traces and propose targeted improvements
3. Review the evolution output — accept if score improved
4. Log before/after scores

### Step 3: Verify

After improvements:
1. Re-run `monitor.py` to compute new metrics
2. Compare before/after success rates
3. If improvement < 5%, flag for manual review
4. Store results in metrics history

### Step 4: Report

Run `python3 ~/.hermes/skills/hermes-dojo/scripts/reporter.py` to generate a report.

Format for Telegram delivery:
```
🥋 Hermes Dojo — Overnight Report

📊 Analyzed: 23 sessions, 156 tool calls
📈 Overall: 78% → 85% (+7%)

✅ Improved:
  • terminal_run: 73% → 96% (added PATH check)
  • web_extract: 81% → 95% (added retry + timeout)

🆕 New skill created:
  • csv-handler: for CSV parsing you keep asking about

⚠️ Still working on:
  • File path resolution (need more examples)

📉 Learning curve: 71% → 78% → 85% (3 days)
```

### Step 5: Track

Run `python3 ~/.hermes/skills/hermes-dojo/scripts/tracker.py save` to persist metrics.
Run `python3 ~/.hermes/skills/hermes-dojo/scripts/tracker.py history` to show the learning curve.

## Setting Up Overnight Cron

When the user says `/dojo auto`:

Set up a cron job that runs at 6:00 AM daily:
"Run /dojo analyze, then /dojo improve on the top 3 weaknesses, then send the report to my home channel."

This makes the agent literally improve while you sleep.

## Safe Proposal Mode

When the task explicitly says SAFE PROPOSAL MODE:

- Run analysis and reporting normally, but do not create, patch, or evolve skills unless the target skill is explicitly marked `metadata.hermes.generated_by: hermes-dojo` or `metadata.hermes.owner: user` and the change is low-risk, idempotent, backed up, and verified.
- In cron/autonomous runs, never call `clarify`. That tool is unavailable in cron execution contexts, so choose a reasonable default and report assumptions/skips instead of trying to ask the user.
- Fail closed on improvements if Dojo reports database unavailable/locked, zero tool calls, contradictory metrics, parser errors, weak evidence, or fewer than 5 independent requests across 3 sessions for a claimed skill gap.
- Treat likely parser false positives as investigations, not fix candidates. In practice this includes `read_file` / `search_files` outputs whose file contents merely contain words like `error`, `exception`, or `unauthorized`.
- If `skill_view` failures come from category-qualified names like `category:skill`, report that as a routing/documentation issue first. Confirm whether the skill loads unqualified before proposing any patch.
- After analysis, persist the snapshot with `python3 ~/.hermes/skills/hermes-dojo/scripts/tracker.py save` so the next run has a comparison baseline.
- Only run Hermes Agent Self-Evolution with Hermes OpenAI Codex OAuth models (`openai-codex/gpt-5.5`) unless `HERMES_SELF_EVOLUTION_ALLOW_PAID_API=1` is explicitly set.

## Daily Safe Proposal Audit Add-ons

For Thomas's 6am Dojo SAFE PROPOSAL MODE run, the useful workflow is broader than the basic monitor/report loop:

1. Run the normal Dojo commands:
   - `python3 ~/.hermes/skills/hermes-dojo/scripts/monitor.py`
   - `python3 ~/.hermes/skills/hermes-dojo/scripts/monitor.py --json` when exact fields are needed
   - `python3 ~/.hermes/skills/hermes-dojo/scripts/reporter.py`
   - `python3 ~/.hermes/skills/hermes-dojo/scripts/tracker.py save`
   - `python3 ~/.hermes/skills/hermes-dojo/scripts/tracker.py history`
2. Run Skill Doctor as a parallel library-health pass:
   - `python3 ~/.hermes/skills/autonomous-ai-agents/skill-doctor/scripts/skill_doctor.py`
3. Add focused investigations for Thomas's recurring quality concerns:
   - duplicate or overlapping meta-skills, especially self-improvement / skill-promotion / audit skills
   - unverified operational claims; cross-check against the `verify-before-claim` skill before proposing changes
   - todo source-of-truth drift; distinguish real todo-tool misuse from context-compaction/report mentions
   - stale model/version references such as GPT/Codex/Claude model strings; propose the model-upgrade workflow rather than opportunistic patching
   - skill-promotion quality: promoted skills should be discoverable, non-duplicative, have triggers/procedure/pitfalls/verification, and be audited after creation
4. Fail closed on weak evidence:
   - Do not promote a skill gap unless it has at least 5 independent requests across 3 sessions.
   - Treat `read_file` / `search_files` "errors" caused by file prose containing words like `error`, `exception`, or `unauthorized` as parser false positives unless explicit tool failure metadata confirms failure.
   - If a skill gap already has a relevant skill, report it as routing/reuse drift rather than creating another skill.
5. Report concise actions, not a raw dump:
   - metrics and trend
   - any safe changes actually made
   - highest-confidence proposed fixes
   - rejected false positives and why
   - next audit targets

## Important Notes

- Never modify bundled skills (in hermes-agent/skills/). Only modify user skills in ~/.hermes/skills/
- Self-evolution requires ~/.hermes/hermes-agent-self-evolution to be cloned
- Metrics are stored in ~/.hermes/skills/hermes-dojo/data/metrics.json
- Each analysis run is timestamped so you can track improvement over days/weeks
