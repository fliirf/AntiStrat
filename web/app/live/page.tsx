"use client";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import Nav from "@/components/Nav";
import MiniMap from "@/components/MiniMap";
import { cap, liveLookup, pct } from "@/lib/data";
import { useIndex } from "@/lib/useData";

// Same thresholds as the call sheet (engine/antistrat/callsheet.py).
const ROTATE = 0.75;
const LEAN = 0.6;

function LiveView() {
  const { index, error } = useIndex();
  const qs = useSearchParams();
  const [mapSel, setMap] = useState<string | null>(null);
  const [util, setUtil] = useState("none");
  const [fk, setFk] = useState("none");
  if (error) return <p className="error">{error}</p>;
  if (!index) return <p className="muted">Loading…</p>;
  const maps = Object.keys(index.live_read ?? {});
  if (!maps.length) return <p className="muted">No live-read table yet. Run the pipeline report step.</p>;
  const map = mapSel ?? (maps.includes(qs.get("map") ?? "") ? qs.get("map")! : maps[0]);
  const lr = index.live_read![map];
  const { key, probs, n } = liveLookup(lr, util, fk);
  const top = lr.sites.reduce((a, b) => (probs[a] >= probs[b] ? a : b));
  const p = probs[top];
  const call = p >= ROTATE ? `Rotate to ${top}.` : p >= LEAN ? `Lean one player toward ${top}, keep the rest.` : "Hold the default setup.";
  const v = lr.validation;
  const backedOff = key !== `${util}|${fk}`;

  return (
    <div className="grid">
      <section className="card">
        <h2>Live read</h2>
        <p className="muted">Enter what you see on defence. Works for any opponent: the data showed the in-round read is what predicts the site, not the team.</p>
        <div className="picker col">
          <label>
            Map
            <select value={map} onChange={(e) => { setMap(e.target.value); setUtil("none"); setFk("none"); }}>
              {maps.map((m) => <option key={m} value={m}>{cap(m)}</option>)}
            </select>
          </label>
          <label>
            0–15 s: attacker utility leads to
            <select value={util} onChange={(e) => setUtil(e.target.value)}>
              <option value="none">No clear lead / not seen</option>
              {lr.sites.flatMap((s) => [
                <option key={`${s}1`} value={`${s}1`}>{s}: one piece</option>,
                <option key={`${s}2`} value={`${s}2`}>{s}: two or more</option>,
              ])}
            </select>
          </label>
          <label>
            First kill (before the plant)
            <select value={fk} onChange={(e) => setFk(e.target.value)}>
              <option value="none">No contact yet</option>
              {lr.sites.flatMap((s) => [
                <option key={`${s}a`} value={`${s}a`}>Near {s}, attackers got it</option>,
                <option key={`${s}d`} value={`${s}d`}>Near {s}, we got it</option>,
              ])}
            </select>
          </label>
        </div>
      </section>

      <section className="card">
        <h2>Call: {call}</h2>
        <div className="split">
          <MiniMap centers={index.sites?.[map]?.centers} mix={probs} highlight={p >= LEAN ? top : null} />
          <table className="mix">
            <tbody>
              {lr.sites.map((s) => (
                <tr key={s}>
                  <td>{s}</td>
                  <td>
                    <div className="bar"><span style={{ width: pct(probs[s]) }} /></div>
                    {pct(probs[s])}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted small">
          Based on {n.toLocaleString()} planted rounds{backedOff ? " (too few rounds for this exact combination, so some of the input is ignored)" : ""}.
        </p>
        <p className="muted small">
          On the newest 20% of matches this table named the right site {pct(v.table_acc)} of the time (full model {pct(v.gbm_acc)},
          guessing the usual site {pct(v.baseline_acc)}). When it is at least 70% sure ({pct(v.table_confident.coverage)} of rounds)
          it is right {pct(v.table_confident.acc)}.
        </p>
      </section>
    </div>
  );
}

export default function LivePage() {
  return (
    <Suspense>
      <Nav />
      <main className="page">
        <LiveView />
      </main>
    </Suspense>
  );
}
