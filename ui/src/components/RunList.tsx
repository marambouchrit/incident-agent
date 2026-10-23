import { useEffect, useMemo, useState } from "react";
import { loadIndex, VERDICT } from "../data";
import type { IndexRow } from "../types";

export default function RunList() {
  const [rows, setRows] = useState<IndexRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [split, setSplit] = useState<"all" | "dev" | "holdout">("all");

  useEffect(() => {
    loadIndex().then(setRows).catch((e: Error) => setError(e.message));
  }, []);

  const groups = useMemo(() => {
    const byScenario = new Map<string, IndexRow[]>();
    for (const r of rows ?? []) {
      if (split !== "all" && r.split !== split) continue;
      byScenario.set(r.scenario, [...(byScenario.get(r.scenario) ?? []), r]);
    }
    return [...byScenario.entries()];
  }, [rows, split]);

  if (error) return <p className="text-rose-700">{error}</p>;
  if (!rows) return <p className="text-slate-500">Loading…</p>;

  const shown = groups.flatMap(([, rs]) => rs);
  const correct = shown.filter((r) => r.verdict === "correct").length;
  const catOk = shown.filter((r) => r.category_match).length;

  return (
    <div>
      <p className="mb-4 max-w-3xl text-slate-700">
        Each row is one investigation. The agent got an incident report, chose which logs, code changes
        and configs to look at, and wrote a report. Click a run to replay it step by step.
      </p>

      <div className="mb-4 flex flex-wrap items-center gap-3 text-sm">
        {(["all", "dev", "holdout"] as const).map((s) => (
          <button
            key={s}
            onClick={() => setSplit(s)}
            className={`rounded-full border px-3 py-1 ${split === s ? "border-slate-800 bg-slate-800 text-white" : "border-slate-300 bg-white"}`}
          >
            {s}
          </button>
        ))}
        <span className="text-slate-600">
          cause <b>{correct}/{shown.length}</b> · category <b>{catOk}/{shown.length}</b>
        </span>
      </div>

      <div className="space-y-3">
        {groups.map(([scenario, rs]) => (
          <div key={scenario} className="rounded-lg border border-slate-200 bg-white p-3">
            <div className="mb-2 flex items-center gap-2 text-sm">
              <span className="font-mono font-semibold">{scenario}</span>
              <span className="rounded bg-slate-100 px-1.5 text-slate-600">{rs[0].split}</span>
              <span className="rounded bg-slate-100 px-1.5 text-slate-600">{rs[0].difficulty}</span>
            </div>
            <div className="grid gap-2 sm:grid-cols-3">
              {rs.map((r) => (
                <a
                  key={r.id}
                  href={`#/run/${encodeURIComponent(r.id)}`}
                  className="rounded border border-slate-200 p-2 text-sm hover:border-slate-400 hover:bg-slate-50"
                >
                  <div className="flex items-center justify-between">
                    <span>
                      {VERDICT[r.verdict].icon} run {r.run_index}
                    </span>
                    <span className="text-slate-500">{r.steps} steps</span>
                  </div>
                  <div className="mt-1 truncate font-mono text-xs text-slate-600">
                    {r.category_match ? "" : "≠ "}
                    {r.category ?? "—"}
                    {r.needs_judge && <span title="half-specific report: category broke the tie"> · tie</span>}
                  </div>
                  <div className="text-xs text-slate-500">
                    conf {r.confidence?.toFixed(2) ?? "—"} · evidence {r.evidence_found}/{r.evidence_total}
                  </div>
                </a>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
