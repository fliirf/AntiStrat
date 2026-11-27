import type { Report, SimCalibration } from "@/lib/data";
import { pct } from "@/lib/data";

/** What the plan is worth against this opponent: map win chance for three defence plans. */
export default function ImpactCard({ report, calibration }: { report: Report; calibration?: SimCalibration }) {
  const imp = report.impact;
  if (!imp) return null;
  const w = imp.map_win;
  const pts = (x: number) => `${x >= 0 ? "+" : ""}${Math.round(x * 1000) / 10} pts`;
  const rows: [string, number, string][] = [
    ["Default setup", w.default, "Balanced, no reads"],
    [`Stack ${imp.habit_site} (their habit)`, w.habit_stack, "Old-school scouting: guard their favourite site"],
    ["Default + rotate on read", w.read, "Call sheet and live read: move only on a confident read"],
  ];
  return (
    <section className="card impact noprint">
      <h2>Impact vs {report.team.name}</h2>
      <div className="stats big">
        {rows.map(([name, v, sub]) => (
          <div key={name}>
            <dt>{name}</dt>
            <dd>{pct(v)}</dd>
            <div className="muted small">{name === "Default setup" ? sub : `${pts(v - w.default)} vs default · ${sub}`}</div>
          </div>
        ))}
      </div>
      <p className="muted small">
        Map win chance over 2,000 simulated maps, starting on defence. {imp.basis}
      </p>
      {calibration?.measured_presence && (() => {
        const m = calibration.measured_presence!;
        const clear = m.ci95[0] > 0;
        return (
          <p className={clear ? "muted small" : "warn small"}>
            Measured check: one more defender near the contested site before the fight changed the defence win chance by{" "}
            {pts(m.extra_defender)} (95% interval {pts(m.ci95[0])} to {pts(m.ci95[1])}, {m.n.toLocaleString()} rounds).{" "}
            {clear
              ? "That supports the assumption above."
              : "No clear effect, so read the rotate-on-read gain as an upper estimate: the read itself is validated, the value of acting on it is not yet."}
          </p>
        );
      })()}
    </section>
  );
}
