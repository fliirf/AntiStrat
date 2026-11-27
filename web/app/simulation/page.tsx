"use client";
import { Suspense, useEffect, useState } from "react";
import Nav from "@/components/Nav";
import Picker, { useSelection } from "@/components/Picker";
import SampleBanner from "@/components/SampleBanner";
import { cap, pct, planKey, simulate, type SimResult } from "@/lib/data";
import { useIndex } from "@/lib/useData";

function SimView() {
  const { index, error } = useIndex();
  const { team, map } = useSelection(index);
  const [result, setResult] = useState<SimResult | null>(null);
  const [simError, setSimError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const run = () => {
    if (!team || !map) return;
    let saved: { plan?: string[]; startSide?: string } = {};
    try {
      saved = JSON.parse(localStorage.getItem(planKey(team, map)) ?? "{}");
    } catch {}
    setRunning(true);
    setSimError(null);
    simulate({ team, map, plan: saved.plan ?? [], start_side: saved.startSide ?? "defense", n: 5000 })
      .then(setResult)
      .catch((e) => setSimError(String(e.message ?? e)))
      .finally(() => setRunning(false));
  };
  useEffect(run, [team, map]); // eslint-disable-line react-hooks/exhaustive-deps

  if (error) return <p className="error">{error}</p>;
  if (!index) return <p className="muted">Loading…</p>;
  const opp = index.opponents.find((o) => o.id === team);
  const leaks = result?.timeline.filter((t) => t.leak) ?? [];
  return (
    <>
      <SampleBanner show={index.is_sample} />
      <Picker index={index} />
      <section className="card">
        <div className="row between">
          <h2>5,000 simulated maps vs {opp?.name} on {cap(map)}</h2>
          <button onClick={run} disabled={running}>{running ? "Simulating…" : "Run again"}</button>
        </div>
        {simError && <p className="error">{simError}</p>}
        {result && (
          <>
            <dl className="stats big">
              <div><dt>Map win chance</dt><dd>{pct(result.map_win)}</dd></div>
              <div><dt>Most likely score</dt><dd>{Object.keys(result.score_dist)[0]}</dd></div>
              <div><dt>Rounds where the plan leaks</dt><dd>{leaks.length}</dd></div>
            </dl>
            <div className="timeline" role="img" aria-label="Win chance per round">
              {result.timeline.map((t) => (
                <div key={t.round} className="tcol" title={`R${t.round}: ${pct(t.p_win)}${t.note ? " · " + t.note : ""}`}>
                  <div className="tbar-wrap">
                    <div className={`tbar ${t.side} ${t.leak ? "leak" : ""}`} style={{ height: `${t.p_win * 100}%` }} />
                  </div>
                  <div className="small muted">{t.round}</div>
                </div>
              ))}
            </div>
            <p className="small muted">Bar = our chance to win the round. Blue: we defend. Grey: we attack. Red: the call costs us win chance.</p>
            {leaks.length > 0 && (
              <>
                <h3>Where the setup leaks</h3>
                <ul className="leaks">
                  {leaks.map((t) => (
                    <li key={t.round}>
                      <strong>R{t.round}</strong> · {t.plan} · {t.note} · {Math.round((t.delta_vs_default ?? 0) * 100)} pts vs default
                      {t.likely_site ? ` · watch ${t.likely_site}` : ""}
                    </li>
                  ))}
                </ul>
              </>
            )}
            <details>
              <summary>Assumptions</summary>
              <pre className="small">{JSON.stringify(result.assumptions, null, 2)}</pre>
            </details>
          </>
        )}
      </section>
    </>
  );
}

export default function SimulationPage() {
  return (
    <Suspense>
      <Nav />
      <main className="page">
        <SimView />
      </main>
    </Suspense>
  );
}
