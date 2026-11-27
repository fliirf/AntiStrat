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

export interface Trait {
  trait: "pace" | "force_after_pistol" | "retake";
  site?: string;
  confidence: "low" | "medium";
  n: number;
  value: number;
  map_value: number;
  text: string;
}

export interface ReadRule {
  min_prob: number;
  coverage: number;
  acc: number | null;
  n: number;
}

export interface CallRule {
  kind: "early_utility" | "contact";
  when: string;
  site: string;
  rate: number;
  rate_older: number;
  n_older: number;
  n_newer: number;
  rate_source: "newer" | "older";
  call: "rotate" | "lean";
  text: string;
}

export interface Timing {
  first_kill_s: number | null;
  plant_s: number | null;
  contact_to_plant_s: number | null;
  gap_10s_plus: number | null;
  fast_plant_share: number | null;
  n: number;
}

export interface CallSheet {
  map: string;
  rules: CallRule[];
  timing: Timing;
  fallback: string;
  confident_read?: ReadRule;
  n_older: number;
  n_newer: number;
}

export interface LiveCell {
  n: number;
  counts: Record<string, number>;
}

export interface LiveRead {
  sites: string[];
  min_cell: number;
  cells: Record<string, LiveCell>;
  validation: {
    n_test: number;
    table_acc: number;
    gbm_acc: number;
    baseline_acc: number;
    table_confident: { min_prob: number; coverage: number; acc: number | null };
  };
}

export interface Leak {
  signal: string;
  site: string;
  n: number;
  rate: number;
  league_rate: number;
  diff: number;
}

export interface SimCalibration {
  def_win_after_def_first_kill?: number;
  def_win_after_att_first_kill?: number;
  first_kill_swing?: number;
  n: number;
  extra_defender_value: number | null;
  rotation_share?: number;
  measured_presence?: { extra_defender: number; ci95: [number, number]; n: number; design: string };
}

export interface OpSide {
  rounds: number;
  op_open_rate: number;
  league_rate: number;
  win_after_op_open: number | null;
  n_op_open: number;
}

export interface OperatorProfile {
  sides: { defense: OpSide; attack: OpSide };
  def_open_zones: Record<string, number>;
  one_player_share: number | null;
  n_op_kills: number;
  confidence: "low" | "medium";
  text: string;
}

export interface UtilSide {
  casts: number;
  rounds: number;
  cells: Record<string, number>;
  top_abilities: Record<string, number>;
}

export interface UtilityMap {
  grid: number;
  bounds: [number, number, number, number];
  attack: UtilSide;
  defense: UtilSide;
}

export interface Impact {
  map_win: { default: number; read: number; habit_stack: number };
  habit_site: string;
  basis: string;
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
  traits?: Trait[];
  read_rule?: ReadRule;
  site_mix_note?: string;
  timing?: Timing;
  leaks?: Leak[];
  operator?: OperatorProfile | null;
  utility?: UtilityMap | null;
  impact?: Impact;
  is_sample?: boolean;
}

export interface Index {
  target: string;
  scope: string;
  generated_at: string;
  is_sample?: boolean;
  maps?: string[];
  opponents: { id: string; name: string; maps: string[] }[];
  metrics: Record<string, { baseline_acc: number; early: { acc: number }; contact: { acc: number }; n_test: number }>;
  sites?: Record<string, { centers: Record<string, [number, number]> }>;
  call_sheet?: Record<string, CallSheet>;
  live_read?: Record<string, LiveRead>;
  sim_calibration?: SimCalibration;
  self?: { id: string; name: string; maps: string[] }[];
  map_detail?: Record<string, { read_avg?: { early: number; contact: number } }>;
  op_validation?: Record<string, { teams: number; r: number | null; p: number | null; stable: boolean }>;
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

/** Accuracy and coverage of the read the coach acts on (confident rounds only, when known). */
export function readStats(report: Report): { acc: number; coverage: number } {
  const r = report.read_rule;
  if (r && r.acc != null && r.coverage) return { acc: r.acc, coverage: r.coverage };
  return { acc: report.read_accuracy.contact.acc ?? report.read_accuracy.baseline.acc, coverage: 1 };
}

export const pct = (x: number | null | undefined) => (x == null ? "–" : `${Math.round(x * 100)}%`);
export const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
/** "dark-cover" -> "Dark cover" */
export const pretty = (s: string) => cap(s.replace(/[-_]/g, " "));

export function planKey(team: string, map: string) {
  return `antistrat.plan.${team}.${map}`;
}

/** Shift sizes the match engine uses: calibrated from the data when available (see sim.py). */
export function assumptions(index: Index) {
  const v = index.sim_calibration?.extra_defender_value;
  if (!v) return { stackGain: 0.12, stackCost: 0.08, readGain: 0.1, readCost: 0.06, calibrated: false };
  const r = v * (index.sim_calibration?.rotation_share ?? 0.75);
  return { stackGain: v, stackCost: v, readGain: r, readCost: r, calibrated: true };
}

/** Live-read lookup with the same back-off as liveread.lookup in the engine. */
export function liveLookup(lr: LiveRead, util: string, fk: string): { key: string; probs: Record<string, number>; n: number } {
  const keys = [`${util}|${fk}`, `*|${fk}`, `${util}|*`, "*|*"];
  const key = keys.find((k) => (lr.cells[k]?.n ?? 0) >= lr.min_cell) ?? "*|*";
  const cell = lr.cells[key];
  const total = cell.n + lr.sites.length;
  const probs = Object.fromEntries(lr.sites.map((s) => [s, (cell.counts[s] + 1) / total]));
  return { key, probs, n: cell.n };
}
