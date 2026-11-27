export type SiteMix = Record<string, number>;

export interface Tell {
  kind: "utility" | "first_contact";
  site: string;
  signal: string;
  hit_rate: number;
  n: number;
  base_rate: number;
  lift: number;
}

export interface Report {
  team: { id: string; name: string };
  map: string;
  target: string;
  sample: { attack_rounds: number; plants: number; games: number };
  site_mix: SiteMix;
  site_mix_smoothed: SiteMix;
  map_site_mix: SiteMix;
  site_counts: Record<string, number>;
  tells: Tell[];
  read_accuracy: {
    early: { acc: number | null; n: number };
    contact: { acc: number | null; n: number };
    baseline: { acc: number };
  };
  adaptation:
    | { shown: false; reason: string }
    | { shown: true; repeat_after_loss: number; repeat_after_win: number; n: number; q: number };
  economy: { attack_win_rate: number; plant_rate: number };
  is_sample?: boolean;
}

export interface Index {
  target: string;
  scope: string;
  generated_at: string;
  is_sample?: boolean;
  opponents: { id: string; name: string; maps: string[] }[];
  metrics: Record<string, { baseline_acc: number; early: { acc: number }; contact: { acc: number }; n_test: number }>;
  sites?: Record<string, { centers: Record<string, [number, number]> }>;
}

export interface TimelineEntry {
  round: number;
  side: "defense" | "attack";
  plan: string | null;
  p_win: number;
  p_reached: number;
  likely_site?: string;
  delta_vs_default?: number;
  leak?: boolean;
  note?: string;
}

export interface SimResult {
  map_win: number;
  score_dist: Record<string, number>;
  timeline: TimelineEntry[];
  assumptions: Record<string, number | number[]>;
}

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function getIndex(): Promise<Index> {
  const r = await fetch("/aggregates/index.json", { cache: "no-store" });
  if (!r.ok) throw new Error("No aggregates yet. Run the pipeline report step.");
  return r.json();
}

export async function getReport(team: string, map: string): Promise<Report> {
  const r = await fetch(`/aggregates/${encodeURIComponent(team)}_${encodeURIComponent(map)}.json`, { cache: "no-store" });
  if (!r.ok) throw new Error(`No report for ${team} on ${map}`);
  return r.json();
}

export async function simulate(body: { team: string; map: string; plan: string[]; start_side: string; n?: number }): Promise<SimResult> {
  const r = await fetch(`${API_URL}/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`Simulation failed (${r.status}). Is the API running at ${API_URL}?`);
  return r.json();
}

export const pct = (x: number | null | undefined) => (x == null ? "–" : `${Math.round(x * 100)}%`);
export const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export function planKey(team: string, map: string) {
  return `antistrat.plan.${team}.${map}`;
}
