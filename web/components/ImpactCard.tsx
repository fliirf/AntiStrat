import type { Est, Index, Report } from "@/lib/data";
import { pct } from "@/lib/data";

const pts = (x: number) => `${x >= 0 ? "+" : ""}${Math.round(x * 1000) / 10} pts`;
const sec = (x: number) => `${Math.round(x * 10) / 10} s`;
const ci = (e: Est, f: (x: number) => string) => `${f(e.lo)} to ${f(e.hi)}`;

/** Measured impact first (from real rounds), then the match engine's estimate for this opponent. */
export default function ImpactCard({ report, index }: { report: Report; index: Index }) {
  const m = index.measured;
  const imp = report.impact;
  const lead = m?.lead_time;
  return (
    <section className="card impact noprint">
      <h2>Impact</h2>
      {m && lead && (
        <>
          <h3>Measured on real pro rounds</h3>
          <div className="stats big">
            <div>
              <dt>Read right, defence still elsewhere at the plant</dt>
              <dd>{pct(m.headroom.misaligned_share.est)}</dd>
              <div className="muted small">
                defence won {pct(m.headroom.def_win_misaligned.est)} of those vs {pct(m.headroom.def_win_aligned.est)} when aligned
              </div>
            </div>
            <div>
              <dt>Defence never stacks the site before the plant</dt>
              <dd>{pct(lead.majority.never_committed_before_plant.est)}</dd>
              <div className="muted small">
                of those rounds · median head start counting them at the plant: {sec(lead.majority.median_lead_s.est)}
              </div>
            </div>
            {lead.majority.committed_median_lead_s && (
              <div>
                <dt>When the defence does commit</dt>
                <dd>{sec(lead.majority.committed_median_lead_s.est)}</dd>
                <div className="muted small">
                  median head start for the read · read first in {pct(lead.majority.committed_read_first_share?.est)} ·
                  95% {ci(lead.majority.committed_median_lead_s, sec)}
                </div>
              </div>
            )}
          </div>
          <p className="muted small">
            {lead.rounds.toLocaleString()} planted rounds. A read counts when it names the right site with {pct(m.definitions.confident)}+
            confidence (out-of-fold), at {m.definitions.early_read_ready_s} s for early utility or at the first kill. The defence
            commits when at least half its alive players (and two or more) are within {m.definitions.near_site_m} m of the site,
            from positions every 2 s. Rounds where it never commits count as committing at the plant. Intervals: 95%, resampling
            whole series. {m.headroom.note}
          </p>
          <p className="muted small">
            One more defender on the site at the plant: {pts(m.plant_position.extra_defender_near_site.est)} defence win chance
            (95% {ci(m.plant_position.extra_defender_near_site, pts)}), with alive counts and loadouts held fixed.
          </p>
        </>
      )}
      {imp && (
        <>
          <h3>Model estimate vs {report.team.name}</h3>
          <div className="stats">
            <div><dt>Default setup</dt><dd>{pct(imp.map_win.default)}</dd></div>
            <div>
              <dt>Stack {imp.habit_site} (their habit)</dt><dd>{pct(imp.map_win.habit_stack)}</dd>
              <div className="muted small">{pts(imp.map_win.habit_stack - imp.map_win.default)} vs default</div>
            </div>
            <div>
              <dt>Default + rotate on read</dt><dd>{pct(imp.map_win.read)}</dd>
              <div className="muted small">{pts(imp.map_win.read - imp.map_win.default)} vs default</div>
            </div>
          </div>
          <p className="muted small">Map win chance over 2,000 simulated maps, starting on defence. {imp.basis}</p>
        </>
      )}
    </section>
  );
}
