import type { ReactNode } from "react";

export interface Mark {
  n: number; // evidence number shown to the reader (1-based)
  quote: string;
}

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

// A quote may differ from the tool output in whitespace and may use "..." to skip text
// (same leniency as eval.metrics.quote_found). Each piece becomes a regex: spaces match any
// whitespace, and a line break may be followed by a diff "+"/"-" the agent left out.
// Display only: the score itself comes from Python.
const GAP = "\\s+(?:[+-](?![+-]))?\\s*";

function pieceRegexes(quote: string): RegExp[] {
  return quote
    .replace(/…/g, "...")
    .split("...")
    .map((p) => p.trim())
    .filter(Boolean)
    .map((p) => new RegExp(p.split(/\s+/).map(escape).join(GAP), "g"));
}

/** Tool output with the report's evidence quotes highlighted. Returns the quote numbers it could not place. */
export function highlight(text: string, marks: Mark[]): { node: ReactNode; unplaced: number[] } {
  const ranges: { start: number; end: number; n: number }[] = [];
  const unplaced: number[] = [];
  for (const m of marks) {
    let placed = false;
    for (const re of pieceRegexes(m.quote)) {
      for (const hit of text.matchAll(re)) {
        ranges.push({ start: hit.index!, end: hit.index! + hit[0].length, n: m.n });
        placed = true;
      }
    }
    if (!placed) unplaced.push(m.n);
  }
  ranges.sort((a, b) => a.start - b.start);

  const out: ReactNode[] = [];
  let pos = 0;
  for (const r of ranges) {
    if (r.start < pos) continue; // overlapping quotes: keep the first
    out.push(text.slice(pos, r.start));
    out.push(
      <mark key={`${r.start}-${r.n}`} className="rounded bg-yellow-200 px-0.5" title={`evidence #${r.n}`}>
        {text.slice(r.start, r.end)}
        <sup className="ml-0.5 font-sans font-semibold text-yellow-900">{r.n}</sup>
      </mark>,
    );
    pos = r.end;
  }
  out.push(text.slice(pos));
  return { node: out, unplaced };
}
