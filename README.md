# /plan

Standalone home for the OpenCode `/plan` skill.

## What this repository contains
- `SKILL.md` — canonical skill definition
- `BEST_PRACTICES.md` — planning and operating guidelines
- `templates/` — reusable plan templates
- `scripts/` — validation, DAG, and Monte Carlo tooling

## Current version
- Skill: `/plan`
- Version: `2.0`
- Modes: `plan-only`, `plan-and-execute`, `resume-approved-plan`, `continuous-planning`

## Install
```bash
mkdir -p ~/.config/opencode/skills
rm -rf ~/.config/opencode/skills/plan
git clone https://github.com/SIN-Skills/plan ~/.config/opencode/skills/plan
```

## Goal
One skill, one repo. No more mixed storage across unrelated repositories.
