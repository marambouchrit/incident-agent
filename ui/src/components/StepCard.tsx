import { useState } from "react";
import { TOOL_LABELS } from "../data";
import type { Step } from "../types";
import { highlight, type Mark } from "./Highlight";

const PREVIEW_LINES = 6;

function formatArgs(args: Record<string, unknown>): string {
  const parts = Object.entries(args).map(([k, v]) => `${k}=${typeof v === "string" ? JSON.stringify(v) : String(v)}`);
  return parts.length ? parts.join(", ") : "no arguments";
}

function ToolResult({ text, marks }: { text: string; marks: Mark[] }) {
  // Results that hold evidence start open: that is where the proof is.
  const [open, setOpen] = useState(marks.length > 0);
  const lines = text.split("\n");
  const long = lines.length > PREVIEW_LINES;
  const shown = open || !long ? text : lines.slice(0, PREVIEW_LINES).join("\n");
  const { node, unplaced } = highlight(shown, open || !long ? marks : []);

  return (
    <div className="mt-2">
      <pre className="max-h-[32rem] overflow-auto whitespace-pre-wrap break-words rounded bg-slate-900 p-3 font-mono text-xs leading-relaxed text-slate-100 [&_mark]:text-slate-900">
        {node}
      </pre>
      <div className="mt-1 flex flex-wrap gap-3 text-xs text-slate-500">
        {long && (
          <button onClick={() => setOpen(!open)} className="underline">
            {open ? "show less" : `show all ${lines.length} lines`}
          </button>
        )}
        {marks.length > 0 && (
          <span className="text-yellow-800">
            contains evidence {marks.map((m) => `#${m.n}`).join(", ")}
            {(open || !long) && unplaced.length > 0 && ` (#${unplaced.join(", #")} matched with whitespace or diff "+/-" changes)`}
          </span>
        )}
      </div>
    </div>
  );
}

export default function StepCard({ step, marksFor }: { step: Step; marksFor: (call: number) => Mark[] }) {
  const thought = step.hypothesis?.replace(/^Hypothesis:\s*/i, "");
  return (
    <li id={`step-${step.step}`} className="relative scroll-mt-4 pl-10">
      <span className="absolute left-0 top-0 flex h-7 w-7 items-center justify-center rounded-full bg-slate-800 text-sm font-semibold text-white">
        {step.step}
      </span>
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        {step.forced && (
          <p className="mb-2 text-xs font-semibold uppercase text-amber-700">step limit reached: report forced</p>
        )}
        {thought && (
          <p className="text-slate-800">
            <span className="mr-1 text-xs font-semibold uppercase tracking-wide text-indigo-600">Thinking</span>
            {thought}
          </p>
        )}
        {step.tool_calls.map((call, i) => (
          <div key={i} className="mt-3 border-t border-slate-100 pt-3">
            <p className="text-sm">
              <span className="mr-1 text-xs font-semibold uppercase tracking-wide text-teal-700">Action</span>
              <b>{TOOL_LABELS[call.tool] ?? call.tool}</b>
              <span className="ml-2 font-mono text-xs text-slate-500">
                {call.tool}({call.tool === "submit_report" ? "…" : formatArgs(call.args)})
              </span>
              {call.is_error && <span className="ml-2 rounded bg-rose-100 px-1 text-xs text-rose-700">error</span>}
              {call.duplicate && <span className="ml-2 rounded bg-amber-100 px-1 text-xs text-amber-700">repeated call</span>}
            </p>
            {call.tool !== "submit_report" && <ToolResult text={call.result} marks={marksFor(i)} />}
            {call.tool === "submit_report" && call.is_error && (
              <pre className="mt-2 whitespace-pre-wrap rounded bg-rose-50 p-2 text-xs text-rose-800">{call.result}</pre>
            )}
          </div>
        ))}
      </div>
    </li>
  );
}
