import type { IndexRow, RunDetail, Verdict } from "./types";

const BASE = `${import.meta.env.BASE_URL}data`;

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}/${path}`);
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}. Run scripts/export_ui_data.py first.`);
  return res.json() as Promise<T>;
}

export const loadIndex = () => getJson<IndexRow[]>("index.json");
export const loadRun = (id: string) => getJson<RunDetail>(`runs/${encodeURIComponent(id)}.json`);

// Plain-language names, so a non-technical reader can follow the timeline.
export const TOOL_LABELS: Record<string, string> = {
  log_stats: "Counted log messages",
  search_logs: "Searched the logs",
  list_commits: "Listed recent code changes",
  show_commit: "Opened one code change",
  read_config: "Read a config file",
  get_db_schema: "Looked at the database structure",
  get_container_status: "Checked which services are running",
  submit_report: "Wrote the final report",
};

export const VERDICT: Record<Verdict, { icon: string; label: string; cls: string }> = {
  correct: { icon: "✅", label: "Found the real cause", cls: "bg-emerald-100 text-emerald-800" },
  wrong: { icon: "❌", label: "Wrong cause", cls: "bg-rose-100 text-rose-800" },
  unclear: { icon: "❓", label: "No cause named", cls: "bg-amber-100 text-amber-800" },
};
