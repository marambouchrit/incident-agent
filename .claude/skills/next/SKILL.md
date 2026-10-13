---
name: next
description: Tell me where I am in the 2-week roadmap and the single next concrete step; at the start of a day, give the day briefing (concepts, plan) first. Use whenever I ask "what's next", "next step", "where am I", "what should I do now", "let's start Day N", or say I just finished something.
argument-hint: "[optional: what I just finished]"
---

Guide me to my next step. What I just finished (may be empty): $ARGUMENTS

## 1. Find where I am
- Read `PROGRESS.md`: current day, latest daily entry, checkpoint table.
- Read that day's section in `ROADMAP.md` §4 (and §0.1 if it's Day 0).
- Check the repo, not just the log: do the day's files exist? Does `pytest -q` pass? Are there open `TODO(human)` markers (`grep -rn "TODO(human)" agent baseline eval`)?
- If I said I finished something, verify it (file exists, test passes, command runs). If it doesn't check out, the next step is to fix that. Say what's missing.

## 1b. Start of a new day? → day briefing first
If nothing of the current day has been done yet (no daily entry for it, none of its files exist), start with a **day briefing** before the next step:
- **Today's goal** and deliverable, in one line, plus the checkpoint it serves.
- **Key concepts (2–4):** for each, the why in 2–3 sentences tied to this project, plus one interview-style question I should be able to answer by tonight.
- **Plan:** the day's steps in order, each marked *scaffolded* or *TODO(human)*.
Then continue with the normal answer below for the first step. The briefing can go up to ~40 lines; the normal answer stays ≤ 20.

## 2. Pick ONE next step
- The first unfinished item of the current day, in roadmap order.
- If there are open `TODO(human)` gaps, the next step is usually to fill them. Don't scaffold more on top.
- If the day is done → say so, suggest `/log-day`, and preview tomorrow in one line.
- If I'm behind the next checkpoint → propose what to cut (Stretch items first, never evaluation).

## 3. Answer in this format (≤ 20 lines)
**Where you are:** Day N · next checkpoint CPx (Day M) · on track / behind by ~X

**Concept first:** *(only if this step introduces a new concept)* 2–4 sentences on the why, plus one interview-style question I should be able to answer afterwards.

**Next step:** one concrete action, one sentence.

**Who does what:**
- I (Claude Code) scaffold: …
- You fill `TODO(human)`: … (the decisions, named)

**Done when:** a checkable condition (test, command, output).

Then ask: "Shall I scaffold it?" and **stop**. Write no code and no files in this answer.
