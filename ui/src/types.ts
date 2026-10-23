// Shapes written by scripts/export_ui_data.py (trajectory format: agent/ trajectory writer).

export type Verdict = "correct" | "wrong" | "unclear";

export interface IndexRow {
  id: string;
  scenario: string;
  run_index: number | null;
  split: "dev" | "holdout" | null;
  difficulty: string | null;
  agent_version: string | null;
  model: string | null;
  verdict: Verdict;
  needs_judge: boolean;
  category_match: boolean;
  category: string | null;
  confidence: number | null;
  steps: number;
  stop_reason: string | null;
  evidence_found: number;
  evidence_total: number;
}

export interface ToolCall {
  tool: string;
  args: Record<string, unknown>;
  result: string;
  is_error: boolean;
  duplicate: boolean;
}

export interface Step {
  step: number;
  forced: boolean;
  hypothesis: string | null;
  tool_calls: ToolCall[];
  tokens?: { input_tokens: number; output_tokens: number };
  latency_ms?: number;
}

export interface Evidence {
  source: string;
  quote: string;
}

export interface Report {
  root_cause_category: string;
  evidence: Evidence[];
  confidence: number;
  suggested_fix: string;
  status: string;
  summary: string;
}

export interface Trajectory {
  scenario: string;
  agent_version: string;
  model: string;
  started_at: string;
  incident: string;
  steps: Step[];
  report: Report | null;
  stop_reason: string;
  totals: { steps: number; tool_calls: number; input_tokens: number; output_tokens: number; latency_ms: number };
}

export interface Truth {
  id: string;
  category: string;
  key_detail: string;
  culprit_commit: string;
  culprit_file?: string;
  difficulty: string;
  red_herrings: string[];
  split: string;
  expected_fix: string;
  notes?: string;
}

export interface Score {
  correct: boolean;
  needs_judge: boolean;
  category_match: boolean;
  commit_match: boolean | null;
  alias_hits: string[];
  evidence: { precision: number | null; total: number; found: number; missing: string[] };
}

export interface QuoteLocation {
  step: number;
  call: number;
}

export interface RunDetail {
  id: string;
  trajectory: Trajectory;
  score: Score;
  verdict: Verdict;
  truth: Truth;
  quote_locations: QuoteLocation[][];
}
