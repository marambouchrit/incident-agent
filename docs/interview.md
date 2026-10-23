# Interview prep — Incident Investigation Agent

Short answers (3–6 lines), with real numbers from the project. Read the question, answer out
loud first, then compare. Sources: `results/2026-10-22_v1.0.md`, `docs/concepts.md`, `PROGRESS.md`.

---

## 0. The pitch (30 seconds)

> I built an autonomous AI agent that finds the root cause of a production incident. It gets an
> incident report, chooses its own tools (logs, commits, config, DB schema, container status),
> and ends with a structured report: the cause, verbatim evidence, a confidence and a suggested
> fix. It is read-only: it proposes fixes, never applies them. I evaluated it on 11 incidents I
> recorded from a real FastAPI + Postgres app: with a small free model it finds the right cause
> in 29 of 33 runs, and 15/15 on scenarios it never saw during tuning.

**Numbers to know by heart:** 11 scenarios (6 dev / 5 holdout) × 3 runs = 33 runs ·
cause 29/33 · category 28/33 · evidence 93/103 (0.90) · blind holdout (v2) cause 15/15,
category 11/15 · confidence 0.96 vs. accuracy 0.78 on dev · ~44K tokens/run · $0 ·
max 15 steps · 7 tools + `submit_report` · 188 tests.

---

## 1. Agent design

**Q1. Why is this an agent and not a workflow? Show where the decision is made.**
> In a workflow, my code decides the steps. Here my code only gives the model 7 tools and a
> 15-step budget; the model picks the next tool from what the last result showed. The decision
> is in the model's tool call, not in `agent/loop.py`: the loop just executes whatever it asks.
> Proof in the trajectories: all runs start with `log_stats`, then s01 checks the DB schema (the
> diff added a column), s04 reads the pool config (pool timeouts), s03 checks containers
> (restarts). No line of code says "if pool timeout, read config".

**Q2. Your prompt suggests starting with `log_stats`. Isn't that a workflow?**
> No. The prompt *advises* a method, like a senior engineer would ("first find when it
> started"), but no code enforces any order. My test: if my code says "at step 2, call tool X",
> it's a workflow. Mine never does.

**Q3. How does your loop work, and how does it stop?**
> The agent's state is the list of messages: rules, the incident, then each tool call with its
> result. Each turn, the model reads the whole history and picks a tool; my code validates it,
> runs it read-only and sends back the result, even if it's an error. It stops when the model
> calls `submit_report` with a valid report. After 15 steps I force one last call that can only
> be `submit_report` (with `not_identified` allowed), so every run ends with a report.

**Q4. Why a raw loop and not LangChain / LangGraph? What would make you switch?**
> I wanted to understand the loop, not hide it: about 100 lines where I see every message, limit
> and error. Every safety rule (step limit, duplicate detection, report retry) is plain code I
> can test and explain. I'd switch for things a framework does well and I didn't need: resuming
> after a crash, human-in-the-loop approval, or several agents working together.

**Q5. Why is the final report a tool (`submit_report`) and not JSON in the text?**
> The API enforces the tool's argument schema, and Pydantic validates it. If the model writes
> `confidence: 1.5`, it gets a precise error back and fixes it. With free JSON in the text I'd
> have to guess where it starts and repair it myself. Calling the tool is also a clean stop signal.

**Q6. Why only one retry for an invalid report?**
> A format mistake is fixed in one try when you show the exact error. If the second try fails
> too, it's not a typo, the agent is lost, and more retries just burn steps and tokens. The
> counter covers the whole run, so the forced final call doesn't give a hidden extra chance.

**Q7. What if the model answers without calling a tool?**
> I send back "continue with a tool or submit your report". It costs one step, and it also
> catches Gemini's occasional empty answers. The 15-step limit guarantees it can't loop forever.

**Q8. How do you change LLM provider?**
> Everything goes through one function, `llm_call(messages, tools) -> (message, usage)`, with my
> own neutral message format. I add the translation for the new provider in `agent/llm.py` and
> change one line in `.env`. The loop, trajectories and evaluation don't change.

**Q9. Can your agent correct itself?**
> Yes, in two ways. A tool error comes back as a result ("unknown service, valid ones are…") and
> it retries. And it chooses each tool from the previous result, so it can drop a hypothesis.
> But it never corrects the application: it's read-only and only proposes a fix.

---

## 2. Tools

**Q10. How did you design the tools?**
> Each tool answers one question an engineer would ask (when did it start, what changed, what
> does the config say…). Each has typed arguments (Pydantic generates the JSON schema the model
> reads and validates what it sends), a "use this when…" hint, a capped output, and error
> messages written for the model. Seven tools is enough to cover every scenario; more would just
> make choosing harder.

**Q11. Why two log tools, `log_stats` and `search_logs`?**
> Different questions. `log_stats` says *when* and *what* in ~40 lines instead of 9,000 raw
> lines; `search_logs` gives the exact lines to quote as evidence. The agent looks at the map,
> then zooms in. With one tool it would drown in raw lines or have no exact quotes.

**Q12. How did you decide what `log_stats` shows?**
> I tested it on the first 5 scenarios. With errors only, s03 (out of memory) and s05 (dropped
> index) were invisible: they have no error lines. So I added p95 latency and restarts with the
> deployed version. Now every failure type has a visible signal.

**Q13. Give an example of a tool description you rewrote, and why.**
> `get_container_status` said "exit 137 = out of memory". That's wrong: 137 only means killed by
> a signal; `oom_killed` tells you if it was memory. The model followed my documentation and
> mislabelled s06. I fixed the description, not the prompt: fixing the source is more general
> than adding a prompt rule that competes with a wrong description. After that, s06 runs read
> `oom_killed=False` correctly.

**Q14. What happens if the important line is line 200 and you cap at 100?**
> Three protections. Filters run *before* the cap (level, keyword, time window). `log_stats`
> gives the overview first. And the footer says "340 lines NOT shown, narrow your query".
> Without that footer, the model would think it had seen everything.

**Q15. Why such detailed tool error messages?**
> Because the model reads them, not a human. `No logs for service 'chekout'. Available: api, db,
> worker` lets it fix itself on the next turn, with no extra code from me.

**Q16. Tell me about a bug you found.**
> To group identical log messages, I replaced every number with `N`. In s04 that turned "pool
> size 2" into "size N": the evidence disappeared. Tests passed because they checked the output
> *size*, not its *content*. Lesson: summarising is choosing what to throw away, so test the
> content on real scenarios.

---

## 3. Safety and limits

**Q17. How do you stop the agent from looping, hallucinating or doing something dangerous?**
> Looping: max 15 steps, then a forced report; identical calls are not re-run (the agent gets a
> 5-line reminder of the earlier result and a nudge to try another angle). Hallucination: every
> evidence quote must appear verbatim in a tool result from that run. Danger: all tools are
> read-only, confined to the scenario folder, with a 10 s timeout and a 100-line output cap.

**Q18. Does the LLM run the tools itself?**
> No. It writes a request (tool name + JSON arguments). My code validates it, runs it and returns
> the result as text. The model never touches files, so all the security is in my code.

**Q19. How do you stop the agent from reading the answer?**
> Every path goes through `safe_path`: it rejects absolute paths and `..`, resolves symlinks, then
> checks the result is still inside `scenarios/<id>/`. Ground truth lives outside that folder.
> Scenario IDs are neutral (`s01`…), and a test fails if the prompt contains giveaway words.

**Q20. Can a tool output be dangerous?**
> Yes: a log line can contain text like "ignore your instructions". Tool outputs are *data*, not
> instructions; the system prompt says so. And since every tool is read-only, even a fooled
> agent can't break anything. That's why "read-only" matters more than any prompt rule.

**Q21. How do you detect that the agent is going in circles?**
> I keep a fingerprint of each call: tool name + sorted arguments, without empty values. If the
> same fingerprint comes back, I don't run the tool again; I answer "already done at step N" with
> a short preview. It still counts as a step, so the 15-step limit stays true.

---

## 4. Evaluation

**Q22. How do you evaluate an agent?**
> Each scenario runs 3 times, because the model isn't deterministic, so I report rates, not
> anecdotes. For each run I score separately: did it name the precise cause (guilty commit + key
> detail from the ground truth), and did it pick the right category. I check every quote against
> what the tools really returned. And I compare confidence with accuracy.

**Q23. Why 3 runs per scenario?**
> The same prompt and model give different investigations from run to run. One run can be lucky
> or unlucky. 3 runs show if a result is stable (3/3) or fragile (1/3). With 11 scenarios, it's
> still a trend, not a statistical proof, and I say so.

**Q24. How do you know the evidence is real?**
> Every tool result is saved in full in the trajectory. I check that each quote in the report
> appears word for word in at least one of those results; if not, the model never saw it. That
> caught s01 run 1: right answer, but an invented schema line saying the column exists, when the
> tool had shown it doesn't. 93/103 quotes (0.90) pass in v1.0.

**Q25. Why a strict match for quotes, not a fuzzy one?**
> Fuzzy matching would let through a fake quote that looks like a real line. Strict sometimes
> gives a false alarm (a copy mistake), but it never lets an invention through. For an
> anti-hallucination check, that's the right side to be wrong on.

**Q26. Why not an LLM judge for everything?**
> A judge costs money, adds randomness and can be wrong too. The category compares exactly, the
> key detail is found by keywords. A judge would only be needed for half-right cases; I flag
> those (`needs_judge`) and break the tie with the category.

**Q27. Right commit, wrong category: is it a failure?**
> It depends on the rule, which is why I score both. In s04 the agent said `bad_config` (the
> starting change) while the truth says `resource_exhaustion` (what breaks). Both are defensible,
> so the category set was ambiguous. Two scores showed the investigation worked and only the
> labelling needed work, which I then fixed with a clear rule.

**Q28. Why no baseline?**
> I chose to spend 2 weeks on the agent and a solid evaluation (dev/holdout split, verbatim
> evidence check, failure taxonomy). A baseline (all data in one prompt) would answer "is the
> loop worth its cost?". I present it as a known limit and future work, not something I forgot.

**Q29. Why only 11 scenarios?**
> Each one is a real incident recorded on a running app, not invented text: about 50 minutes
> each. 11 cover 3 difficulty levels and 7 categories, with 5 held out. I dropped one (s09)
> because it depended on a race between two services: a test that isn't reproducible measures luck.

**Q30. Why recorded incidents instead of generated logs?**
> Error messages come from real libraries (psycopg, SQLAlchemy, httpx), with real timing and real
> noise. Hand-written logs tend to contain accidental hints ("ERROR: pool too small") that make
> the investigation too easy.

**Q31. How did you build the hard scenarios?**
> Three recipes: the cause is hidden in an innocently named commit ("Tune HTTP client defaults"
> lowers a timeout to 0.07 s); look-alikes of earlier scenarios (a full pool while the pool
> config didn't change); and a decoy at ERROR level that only the *timing* rules out.

**Q32. Can I trust your 29/33?**
> It re-computes exactly from the saved trajectories. A fresh run gives close but not identical
> numbers, which is why each scenario runs 3 times. But 29/33 includes scenarios I read while
> tuning. The most honest number is the blind holdout (v2): cause 15/15, category 11/15. And 11
> scenarios is a trend, not a statistical proof.

**Q33. Why a small free model and not a big one?**
> Budget: free only. Stronger free models allow ~20 requests a day; a full eval needs ~240. It
> became an argument: 15/15 causes on unseen scenarios with a "Flash-Lite" model, so most of the
> performance comes from the design (tools, loop, evidence rules), not model size.

---

## 5. Failures and tuning

**Q34. What is your agent's worst failure mode? Show a trajectory.**
> Anchoring: it grabs the suspicious commit just before the incident and never checks timing. In
> s08 it blames a commit that made search slow, but search only broke 11 minutes later, 4 seconds
> after a commit lowered the Postgres `statement_timeout` (30 s → 250 ms). In v1.0 it even
> *quotes* the timeout change and still blames the slow query: it sees the evidence but doesn't
> weigh it. Run 1 of s08 used all 15 steps and got a forced report.

**Q35. How do you fight anchoring without turning the agent into a workflow?**
> I require proof before concluding (timing aligned, state checked, one alternative ruled out),
> but I don't fix any tool order. A workflow says "do A then B"; I say "don't conclude without
> proving X". Measured effect on s08: the agent opens the timeout commit 2/3 times instead of 0/3.

**Q36. How did you find what was wrong with your agent?**
> I read all 18 dev trajectories with a small script showing each step's hypothesis, tool and
> result. I named each failure and counted them: anchoring 6/18, then wrong category (often a
> misread signal like exit code 137). Then I fixed one thing at a time with a before/after number.

**Q37. How did you avoid overfitting your prompt to your scenarios?**
> Dev/holdout split fixed at creation; I tuned only on dev. One tuning round with 2 changes, each
> justified by dev failures, then froze the version with a git tag `v1.0`. And when I did read
> the holdout, I said so: the v3 holdout 15/15 is labelled "not blind", and I report the v2
> number instead.

**Q38. Did you find test leaks in your prompt?**
> Yes: the evidence example in prompt v1 cited `git/45b232b`, the real guilty commit of s01. I
> replaced it with `git/<hash>` and added a test that scans the prompt for ground-truth commits.
> The giveaway test also rejected the word "de**fault**" once; I rephrased the prompt, not the test.

**Q39. Did a change ever break something?**
> Yes. The rule "label the change that started the problem" dropped s03 from 3/3 to 1/3 (a
> heavier code change vs. a process killed). I added a clear priority ("process killed →
> `infra_crash`") and re-ran: 3/3. That's why the whole dev set is re-run after every change.

**Q40. A scenario stays at 0/3. Do you keep tuning?**
> No. In s06 the agent finds the right story (the `payments` container is down) but labels it
> `infra_crash`, not `dependency_failure`. Nothing in the snapshot shows `payments` is external:
> it's a container in the same compose file. The label is ambiguous; tuning for it would overfit.

**Q41. Is your agent well calibrated?**
> No. Average confidence 0.96 for 78 % accuracy on dev, and the wrong runs are all at 0.9–1.0.
> A written confidence scale in the prompt only moved it from 1.00 to 0.96. Next step: compute
> confidence in code from the checks actually done, instead of asking the model.

**Q42. What did your changes cost?**
> Every rule is sent on every call: v3 costs 18 % more tokens per run than v2 (45K vs. 38K) for
> +2 correct categories out of 18. With a paid model, that trade-off would need justifying.

---

## 6. Observability

**Q43. Why build a trajectory viewer?**
> You can't debug an agent from its final answer: the code is the same every run, the behaviour
> lives in the trace. On s08 the report just says "wrong"; the trace shows the agent read the
> lowered timeout and still blamed the slow query. The viewer also lets a non-technical person
> follow an investigation step by step.

**Q44. Why doesn't the UI compute the score itself?**
> The scoring rules live in one place, in Python (`eval/metrics.py`). A second copy in
> TypeScript would drift: I'd change a rule on one side and forget the other. It almost
> happened: the viewer first showed 27/33 instead of 29/33.

---

## 7. What's next

**Q45. What would you build next, and what new risks would it bring?**
> First, confidence computed from the checks the agent did, and a fresh blind holdout or a public
> benchmark (RCAEval) to measure generalisation. A one-shot baseline to measure what the loop adds.
> Then a live environment: real-time data means rate limits, secrets and huge logs. And a
> fixer/verifier pair of agents: the moment an agent can *apply* a fix, read-only safety is gone,
> so I'd need human approval, a sandbox and rollback.

**Q46. Does your agent work on any project?**
> Not live: it reads frozen snapshots of incidents in a fixed folder format. That was a choice,
> so I could *measure* it against a known answer. For another system, you'd export logs,
> commits and config into that format; connecting it live is future work.
