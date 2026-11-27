import type { CallSheet, Report } from "@/lib/data";
import { cap, pct, pretty } from "@/lib/data";

const secs = (x: number | null | undefined) => (x == null ? "–" : `${Math.round(x)} s`);

export default function CallSheetCard({ sheet, report }: { sheet?: CallSheet; report: Report }) {
  if (!sheet) return <p className="muted">No call sheet for this map yet. Run the pipeline report step.</p>;
  const early = sheet.rules.filter((r) => r.kind === "early_utility");
  const contact = sheet.rules.filter((r) => r.kind === "contact");
  const cr = sheet.confident_read;
  const t = sheet.timing;
  return (
    <section className="card callsheet">
      <div className="row between">
        <h2>Call sheet: {report.team.name} on {cap(sheet.map)}</h2>
        <button className="ghost noprint" onClick={() => window.print()}>Print</button>
      </div>
      <p className="muted">
        Rules learned from every team on {cap(sheet.map)}, checked on the newest 20% of matches ({sheet.n_newer} rounds).
        The percentages are from those newer matches.
      </p>

      <div className="cs-grid">
        <div>
          <h3>Before the round</h3>
          <ul className="rules">
            <li>{sheet.fallback}</li>
            {(report.traits ?? []).map((tr, i) => (
              <li key={i}>
                <span className={`chip conf-${tr.confidence}`}>{tr.confidence} confidence · {tr.n} rounds</span> {tr.text}
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h3>0–15 s: early utility</h3>
          {early.length === 0 && !(sheet.utility_leaks ?? []).length && (
            <p className="muted">No utility pattern strong enough on this map.</p>
          )}
          <ul className="rules">
            {early.map((r, i) => (
              <li key={i}>
                <span className={`chip call-${r.call}`}>{r.call === "rotate" ? "Rotate" : "Lean"} {r.site}</span> {r.when}:{" "}
                <strong>{r.site} {pct(r.rate)}</strong> <span className="muted small">
                  ({r.rate_source === "newer" ? `${r.n_newer} newer rounds` : `${r.n_older} older rounds, too few newer to check`})
                </span>
              </li>
            ))}
          </ul>

          {(sheet.utility_leaks ?? []).length > 0 && (
            <>
              <h3>Utility that gives the site away</h3>
              <ul className="rules">
                {sheet.utility_leaks!.map((l, i) => (
                  <li key={i}>
                    <span className="chip">{l.agent ? `${l.agent} · ` : ""}{pretty(l.ability)} → {l.site}</span>{" "}
                    <strong>{l.site} {pct(l.rate_newer)}</strong> vs {pct(l.base_newer)} usually{" "}
                    <span className="muted small">({l.n_newer} newer rounds)</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>

        <div>
          <h3>First contact</h3>
          <p className="muted small">
            First kill at {secs(t.first_kill_s)}, plant at {secs(t.plant_s)}: about {secs(t.contact_to_plant_s)} to react
            {t.gap_10s_plus != null && ` (10 s or more in ${pct(t.gap_10s_plus)} of rounds)`}.
          </p>
          {contact.length === 0 && <p className="muted">No contact pattern strong enough on this map.</p>}
          <ul className="rules">
            {contact.map((r, i) => (
              <li key={i}>
                <span className={`chip call-${r.call}`}>{r.call === "rotate" ? "Rotate" : "Lean"} {r.site}</span> {r.when}:{" "}
                <strong>{r.site} {pct(r.rate)}</strong> <span className="muted small">
                  ({r.rate_source === "newer" ? `${r.n_newer} newer rounds` : `${r.n_older} older rounds, too few newer to check`})
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {cr && cr.acc != null && (
        <p className="callout">
          Live read: in {pct(cr.coverage)} of rounds the model is confident (70%+) by first contact, and then it is right{" "}
          {pct(cr.acc)} of the time. In the other rounds, stay on the default.
        </p>
      )}
    </section>
  );
}
