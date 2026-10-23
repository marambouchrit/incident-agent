import type { Score, Truth } from "../types";

export default function TruthCard({ truth, score }: { truth: Truth; score: Score }) {
  const commitMark = score.commit_match === null ? "" : score.commit_match ? " ✅" : " ❌";
  return (
    <div className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-emerald-700">
        Ground truth (hidden from the agent)
      </h3>

      <p className="mt-2 text-slate-800">{truth.key_detail}</p>

      <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
        <dt className="text-slate-500">Category</dt>
        <dd className="font-mono">{truth.category}</dd>
        <dt className="text-slate-500">Culprit commit</dt>
        <dd className="font-mono">
          {truth.culprit_commit || "none (external)"}
          {commitMark}
        </dd>
        <dt className="text-slate-500">Key detail named</dt>
        <dd>{score.alias_hits.length ? `✅ ${score.alias_hits.join(", ")}` : "❌"}</dd>
      </dl>

      <h4 className="mt-4 text-sm font-semibold">Expected fix</h4>
      <p className="mt-1 text-sm text-slate-800">{truth.expected_fix}</p>

      {truth.red_herrings.length > 0 && (
        <>
          <h4 className="mt-4 text-sm font-semibold">Red herrings (traps placed in the data)</h4>
          <ul className="mt-1 list-disc pl-5 text-sm text-slate-700">
            {truth.red_herrings.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </>
      )}

      {truth.notes && <p className="mt-4 text-sm text-slate-600">{truth.notes}</p>}
    </div>
  );
}
