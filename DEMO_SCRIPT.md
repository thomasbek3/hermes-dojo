# Hermes Dojo Demo Script

## Recording Setup
- Terminal: full screen, dark theme, large font (16pt+)
- Resolution: 1920x1080 or 1280x720
- Record with: QuickTime (Cmd+Shift+5) or OBS

## Before Recording (cleanup)
```bash
rm -rf ~/.hermes/skills/{web-extract,terminal-run,execute-code,deployment,csv-parsing,json-formatting,api-integration}
rm -f ~/.hermes/skills/hermes-dojo/data/metrics.json
python3 ~/.hermes/skills/hermes-dojo/scripts/seed_demo_data.py --clear
```

## One-Command Demo (recommended)

The fastest path: run one command that does everything.

```bash
cd ~/.hermes/skills/hermes-dojo/scripts
python3 demo.py --reset --multi-day
```

This seeds realistic failure data, pre-populates a 5-day learning curve, then runs the full Dojo pipeline. Output includes:
- Session analysis (57.1% success rate, 11 user corrections, 4 skill gaps)
- 7 new skills created with real bash commands and error recovery
- Sample skill preview (terminal-run with branch checks, path validation)
- Report with delta from previous day (+3.9%)
- Learning curve with sparkline: 34.2% -> 57.1% over 5 days

## Script (aim for ~2 minutes)

### [0:00-0:10] Hook
"Your AI agent makes the same mistakes every day. You correct it, it forgets next session. What if it could fix itself?"

### [0:10-0:30] Run Dojo
```bash
cd ~/.hermes/skills/hermes-dojo/scripts
python3 demo.py --reset --multi-day
```

Let it run. Point out the key numbers as they appear:
- "57% success rate. web_extract fails 100% of the time."
- "11 user corrections — that's 11 times someone said 'no, I meant...'"
- "4 skill gaps detected — things users keep asking for that the agent can't do"

### [0:30-0:50] Show Created Skill
Scroll up to the sample skill preview, or run:
```bash
cat ~/.hermes/skills/terminal-run/SKILL.md
```

"Look at this — not boilerplate. Real bash commands: `git branch --show-current` before every commit. Path validation before file ops. Error recovery table for every common failure. This is a skill that changes how the agent behaves."

### [0:50-1:10] Show the Report
Scroll to the report section in demo output. Or for Telegram format:
```bash
python3 reporter.py --format telegram
```

"This gets delivered to Telegram every morning. Success rates, what was fixed, what still needs work."

### [1:10-1:30] Show Learning Curve
Scroll to the learning curve section. Point out:
- "34.2% on Day 1 to 57.1% today — 23 point improvement"
- "The sparkline shows the trend. This is proof, not promises."
- "User corrections dropped from 12 to 5 over 4 days"

### [1:30-1:45] Self-Evolution Hook
```bash
cd ~/.hermes/hermes-agent-self-evolution
.venv/bin/python3 -m evolution.skills.evolve_skill --skill terminal-run --hermes-repo ~/.hermes --dry-run
```

"For skills that need deeper optimization, Dojo hooks into Hermes self-evolution — the GEPA framework. It runs DSPy optimization on your weakest skills."

### [1:45-2:00] Close
"Hermes Dojo. Your agent, getting better while you sleep. Built on Hermes Agent by Nous Research."

## After Recording (cleanup)
```bash
rm -rf ~/.hermes/skills/{web-extract,terminal-run,execute-code,deployment,csv-parsing,json-formatting,api-integration}
rm -f ~/.hermes/skills/hermes-dojo/data/metrics.json
python3 ~/.hermes/skills/hermes-dojo/scripts/seed_demo_data.py --clear
```
