"use client";
import { Suspense } from "react";
import Nav from "@/components/Nav";
import Picker, { useSelection } from "@/components/Picker";
import MiniMap from "@/components/MiniMap";
import SampleBanner from "@/components/SampleBanner";
import { cap, pct } from "@/lib/data";
import { useIndex, useReport } from "@/lib/useData";

function ReportView() {
  const { index, error } = useIndex();
  const { team, map } = useSelection(index);
  const { report, error: rErr } = useReport(team, map);
  if (error) return <p className="error">{error}</p>;
  if (!index) return <p className="muted">Loading…</p>;
  const sites = report ? Object.keys(report.site_mix_smoothed) : [];
  const fav = report ? sites.reduce((a, b) => (report.site_mix_smoothed[a] >= report.site_mix_smoothed[b] ? a : b)) : null;
  return (
    <>
      <SampleBanner show={index.is_sample} />
      <Picker index={index} />
      {rErr && <p className="error">{rErr}</p>}
      {report && (
        <div className="grid">
          <section className="card span2">
            <h2>{report.team.name} on {cap(report.map)}: attack habits</h2>
            <p className="muted">
              {report.sample.attack_rounds} attack rounds · {report.sample.plants} plants · {report.sample.games} maps
            </p>
            <div className="split">
              <MiniMap centers={index.sites?.[report.map]?.centers} mix={report.site_mix_smoothed} highlight={fav} />
              <table className="mix">
                <thead>
                  <tr><th>Site</th><th>{report.team.name}</th><th>Map average</th><th>Plants</th></tr>
                </thead>
                <tbody>
                  {sites.map((s) => (
                    <tr key={s}>
                      <td>{s}</td>
                      <td>
                        <div className="bar"><span style={{ width: pct(report.site_mix_smoothed[s]) }} /></div>
                        {pct(report.site_mix_smoothed[s])}
                      </td>
                      <td className="muted">{pct(report.map_site_mix[s])}</td>
                      <td className="muted">{report.site_counts[s]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {report.site_mix_note && <p className="warn">{report.site_mix_note}</p>}
            {!report.site_mix_note && report.sample.plants < 20 && (
              <p className="warn">Small sample: shares are pulled toward the map average.</p>
            )}
          </section>

          <section className="card">
            <h2>What stays true about them</h2>
            <p className="muted">Traits that held steady between older and newer matches in the data.</p>
            {(report.traits ?? []).length === 0 && <p className="muted">Not enough rounds for a stable trait.</p>}
            <ul className="tells">
              {(report.traits ?? []).map((t, i) => (
                <li key={i}>
                  <span className={`chip conf-${t.confidence}`}>{t.confidence} confidence · {t.n} rounds</span>
                  <div>{t.text}</div>
                </li>
              ))}
            </ul>
          </section>

          <section className="card">
            <h2>Team-specific tells</h2>
            <p className="muted">
              Early-round signals followed by a plant on the same site for this team. In testing, these did not beat the
              map-wide rules on the call sheet, so treat them as hints.
            </p>
            {report.tells.length === 0 && <p className="muted">No reliable tells (each needs at least 5 rounds).</p>}
            <ul className="tells">
              {report.tells.map((t, i) => (
                <li key={i}>
                  <span className={`chip ${t.kind}`}>{t.kind === "utility" ? "0–15 s utility" : "First contact"}</span>
                  <strong>{t.signal}</strong>
                  <div className="muted">
                    → {t.site} {pct(t.hit_rate)} of the time (normally {pct(t.base_rate)}) · {t.n} rounds
                  </div>
                </li>
              ))}
            </ul>
          </section>

          <section className="card">
            <h2>How readable are they?</h2>
            <p className="muted">How often the round-read model names the right site on this team's rounds (out-of-fold).</p>
            <dl className="stats">
              <div><dt>Guess the usual site</dt><dd>{pct(report.read_accuracy.baseline.acc)}</dd></div>
              <div><dt>Read at 15 s (utility)</dt><dd>{pct(report.read_accuracy.early.acc)}</dd></div>
              <div><dt>Read at first contact</dt><dd>{pct(report.read_accuracy.contact.acc)}</dd></div>
            </dl>
            <h3>Adapting between rounds</h3>
            {report.adaptation.shown ? (
              <p>
                After a lost round they repeat the site {pct(report.adaptation.repeat_after_loss)} of the time, after a won
                round {pct(report.adaptation.repeat_after_win)} (q = {report.adaptation.q}).
              </p>
            ) : (
              <p className="muted">Not shown: {report.adaptation.reason}.</p>
            )}
          </section>
        </div>
      )}
    </>
  );
}

export default function ReportPage() {
  return (
    <Suspense>
      <Nav />
      <main className="page">
        <ReportView />
      </main>
    </Suspense>
  );
}
