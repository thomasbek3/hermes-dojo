# Hermes Dojo Demo Script

## Recording Setup
- Terminal: full screen, dark theme, large font (16pt+)
- Resolution: 1920x1080 or 1280x720
- Record with: QuickTime (Cmd+Shift+5) or OBS

## Script (aim for ~2 minutes)

### [0:00-0:10] Hook
"Your AI agent makes the same mistakes every day. You correct it, it forgets next session. What if it could fix itself?"

### [0:10-0:25] Show the Problem
In terminal, run:
```bash
cd ~/.hermes/skills/hermes-dojo/scripts
python3 monitor.py
```

Point out: "55% success rate. web_extract fails 100% of the time. The agent keeps timing out on web scraping and users keep correcting wrong git branches. 13 times users had to say 'no, I meant...'"

### [0:25-0:45] Dojo Analyzes
```bash
python3 analyzer.py
```

"Dojo found 9 improvement opportunities. It ranked them by impact — web_extract is the worst at 0% success, terminal_run has 20 errors. It also detected skill gaps: users asked for CSV parsing 5 times but no skill exists."

### [0:45-1:10] Dojo Fixes
```bash
python3 fixer.py --apply
```

"Dojo automatically creates targeted skills. Not boilerplate — real instructions with bash commands, error recovery tables, and safety checks."

Show a created skill:
```bash
cat ~/.hermes/skills/terminal-run/SKILL.md
```

"Look at this — it checks the git branch before commits, validates paths exist before operations, has a recovery table for every common error. This is a real skill that changes agent behavior."

### [1:10-1:30] The Report
```bash
python3 reporter.py --format telegram
```

"This gets delivered to your Telegram every morning. Success rates, what was fixed, what still needs work. Set it up as a cron job and your agent improves while you sleep."

### [1:30-1:45] Learning Curve
```bash
python3 tracker.py save
python3 tracker.py history
```

"Over time, you see your agent getting better. The sparkline shows the trend. This is proof, not promises."

### [1:45-1:55] Self-Evolution Integration
```bash
cd ~/.hermes/hermes-agent-self-evolution
.venv/bin/python3 -m evolution.skills.evolve_skill --skill hermes-dojo --hermes-repo ~/.hermes --dry-run
```

"For skills that need deeper optimization, Dojo hooks into Hermes self-evolution — the GEPA framework from the ICLR paper. It runs DSPy optimization on your weakest skills."

### [1:55-2:00] Close
"Hermes Dojo. Your agent, getting better while you sleep. Built on Hermes Agent by Nous Research."

## Cleanup After Demo
```bash
rm -rf ~/.hermes/skills/{web-extract,terminal-run,execute-code,deployment,csv-parsing,json-formatting,docker-management,api-integration,database-operations}
rm -f ~/.hermes/skills/hermes-dojo/data/metrics.json
python3 ~/.hermes/skills/hermes-dojo/scripts/seed_demo_data.py --clear
```
