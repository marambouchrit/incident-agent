import { useEffect, useState } from "react";
import { loadRun, VERDICT } from "../data";
import type { RunDetail } from "../types";
import type { Mark } from "./Highlight";
import ReportCard from "./ReportCard";
import StepCard from "./StepCard";
import TruthCard from "./TruthCard";

export default function RunView({ id }: { id: string }) {
  const [run, setRun] = useState<RunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setRun(null);
    loadRun(id).then(setRun).catch((e: Error) => setError(e.message));
  }, [id]);

  if (error) return <p className="text-rose-700">{error}</p>;
  if (!run) return <p className="text-slate-500">Loading…</p>;

  const t = run.trajectory;
  const v = VERDICT[run.verdict];
  const quotes = t.report?.evidence ?? [];
  const marksFor = (step: number) => (call: number): Mark[] =>
    run.quote_locations.flatMap((locs, i) =>
      locs.some((l) => l.step === step && l.call === call) ? [{ n: i + 1, quote: quotes[i].quote }] : [],
    );

  return (
    <div>
      <a href="#/" className="text-sm text-slate-500 hover:underline">
        ← all runs
      </a>

      <section className="mt-3 rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="font-mono font-semibold">{t.scenario}</span>
          <span className="rounded bg-slate-100 px-1.5 text-slate-600">{run.truth.split}</span>
          <span className="rounded bg-slate-100 px-1.5 text-slate-600">{run.truth.difficulty}</span>
          <span className={`rounded px-2 py-0.5 font-medium ${v.cls}`}>
            {v.icon} {v.label}
          </span>
          {run.score.needs_judge && (
            <span className="rounded bg-slate-100 px-1.5 text-slate-600" title="Only one of commit / key detail named; the category broke the tie">
              tie broken by category
            </span>
          )}
          <span className="ml-auto text-slate-500">
            {t.model} · agent {t.agent_version} · {t.totals.steps} steps · {(t.totals.latency_ms / 1000).toFixed(0)} s ·{" "}
            {Math.round(t.totals.input_tokens / 1000)}K tokens in
          </span>
        </div>
        <h2 className="mt-3 text-xs font-semibold uppercase tracking-wide text-slate-500">The incident report the agent received</h2>
        <p className="mt-1 text-slate-800">{t.incident}</p>
      </section>

      <h2 className="mb-3 mt-6 text-lg font-semibold">How the agent investigated</h2>
      <ol className="space-y-4">
        {t.steps.map((s) => (
          <StepCard key={s.step} step={s} marksFor={marksFor(s.step)} />
        ))}
      </ol>
      <p className="mt-3 text-sm text-slate-500">
        Stopped because: <span className="font-mono">{t.stop_reason}</span>
      </p>

      <h2 className="mb-3 mt-8 text-lg font-semibold">What the agent concluded vs. what really happened</h2>
      <div className="grid gap-4 md:grid-cols-2">
        <ReportCard report={t.report} score={run.score} locations={run.quote_locations} />
        <TruthCard truth={run.truth} score={run.score} />
      </div>
    </div>
  );
}
