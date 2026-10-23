import type { MouseEvent } from "react";
import type { QuoteLocation, Report, Score } from "../types";

export default function ReportCard({
  report,
  score,
  locations,
}: {
  report: Report | null;
  score: Score;
  locations: QuoteLocation[][];
}) {
  if (!report) {
    return (
      <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-amber-900">
        The agent never submitted a valid report.
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-indigo-600">Agent's report</h3>

      <p className="mt-2 text-slate-800">{report.summary}</p>

      <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
        <dt className="text-slate-500">Category</dt>
        <dd className="font-mono">
          {report.root_cause_category} {score.category_match ? "✅" : "❌"}
        </dd>
        <dt className="text-slate-500">Confidence</dt>
        <dd>
          <div className="flex items-center gap-2">
            <div className="h-2 w-32 rounded bg-slate-200">
              <div className="h-2 rounded bg-indigo-500" style={{ width: `${report.confidence * 100}%` }} />
            </div>
            {report.confidence.toFixed(2)}
          </div>
        </dd>
        <dt className="text-slate-500">Status</dt>
        <dd className="font-mono">{report.status}</dd>
      </dl>

      <h4 className="mt-4 text-sm font-semibold">Evidence (quoted from what the agent saw)</h4>
      <ol className="mt-1 space-y-2">
        {report.evidence.map((e, i) => {
          const locs = locations[i] ?? [];
          return (
            <li key={i} className="text-sm">
              <div className="flex items-baseline gap-2">
                <span className="rounded bg-yellow-200 px-1 text-xs font-semibold text-yellow-900">#{i + 1}</span>
                <span className="font-mono text-xs text-slate-500">{e.source}</span>
                {locs.length ? (
                  <a href={`#step-${locs[0].step}`} onClick={jump(locs[0].step)} className="text-xs text-emerald-700 underline">
                    seen at step {locs.map((l) => l.step).join(", ")}
                  </a>
                ) : (
                  <span className="text-xs font-semibold text-rose-700">not found in any tool output</span>
                )}
              </div>
              <pre className="mt-1 whitespace-pre-wrap break-words rounded bg-slate-50 p-2 font-mono text-xs">{e.quote}</pre>
            </li>
          );
        })}
      </ol>

      <h4 className="mt-4 text-sm font-semibold">Suggested fix (proposed, never applied)</h4>
      <p className="mt-1 text-sm text-slate-800">{report.suggested_fix}</p>
    </div>
  );
}

// The page uses "#/run/<id>" for routing, so a plain "#step-3" link would change the route.
const jump = (step: number) => (ev: MouseEvent) => {
  ev.preventDefault();
  document.getElementById(`step-${step}`)?.scrollIntoView({ behavior: "smooth" });
};
