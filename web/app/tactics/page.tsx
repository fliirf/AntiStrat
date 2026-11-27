"use client";
import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import Nav from "@/components/Nav";
import Picker, { useSelection } from "@/components/Picker";
import SampleBanner from "@/components/SampleBanner";
import CallSheetCard from "@/components/CallSheetCard";
import ImpactCard from "@/components/ImpactCard";
import { assumptions, cap, pct, planKey, readStats } from "@/lib/data";
import { useIndex, useReport } from "@/lib/useData";

const ROUNDS = 24;

function TacticsView() {
  const { index, error } = useIndex();
  const { team, map } = useSelection(index);
  const { report } = useReport(team, map);
  const [startSide, setStartSide] = useState<"defense" | "attack">("defense");
  const [plan, setPlan] = useState<string[]>(Array(ROUNDS).fill("default"));

  useEffect(() => {
    if (!team || !map) return;
    try {
      const saved = JSON.parse(localStorage.getItem(planKey(team, map)) ?? "null");
      if (saved?.plan) {
        setPlan(saved.plan);
        setStartSide(saved.startSide ?? "defense");
        return;
      }
    } catch {}
    setPlan(Array(ROUNDS).fill("default"));
  }, [team, map]);

  useEffect(() => {
    if (!team || !map) return;
    try {
      localStorage.setItem(planKey(team, map), JSON.stringify({ plan, startSide }));
    } catch {}
  }, [plan, startSide, team, map]);

  if (error) return <p className="error">{error}</p>;
  if (!index || !report) return <p className="muted">Loading…</p>;
  const sites = Object.keys(report.site_mix_smoothed);
  const options = ["default", "read", ...sites.map((s) => `stack:${s}`)];
  const label = (o: string) => (o === "default" ? "Default" : o === "read" ? "Default + rotate on read" : `Stack ${o.slice(6)}`);
  const defending = (i: number) => (startSide === "defense") === i < 12;
  const { acc, coverage } = readStats(report);
  const a = assumptions(index);
  const value = (o: string) => {
    if (o.startsWith("stack:")) {
      const p = report.site_mix_smoothed[o.slice(6)] ?? 0;
      return p * a.stackGain - (1 - p) * a.stackCost;
    }
    return o === "read" ? coverage * (acc * a.readGain - (1 - acc) * a.readCost) : 0;
  };
  const retakes = (report.traits ?? []).filter((t) => t.trait === "retake");
  const best = options.reduce((a, b) => (value(a) >= value(b) ? a : b));

  return (
    <>
      <SampleBanner show={index.is_sample} />
      <Picker index={index} />
      <ImpactCard report={report} index={index} />
      <CallSheetCard sheet={index.call_sheet?.[map]} report={report} />
      <section className="card noprint">
        <div className="row between">
          <h2>Game plan vs {report.team.name} on {cap(map)}</h2>
          <div className="row">
            <label className="inline">
              We start on
              <select value={startSide} onChange={(e) => setStartSide(e.target.value as "defense" | "attack")}>
                <option value="defense">Defense</option>
                <option value="attack">Attack</option>
              </select>
            </label>
            <button onClick={() => setPlan(plan.map((p, i) => (defending(i) ? best : p)))}>Fill with best call ({label(best)})</button>
            <button className="ghost" onClick={() => setPlan(Array(ROUNDS).fill("default"))}>Reset</button>
          </div>
        </div>
        <p className="muted">
          They hit {sites.map((s) => `${s} ${pct(report.site_mix_smoothed[s])}`).join(" · ")} (close to the map average).
          The read is confident in {pct(coverage)} of rounds and then right {pct(acc)} of the time. Pick a call for each
          defense round.
        </p>
        <div className="rounds">
          {plan.map((p, i) => (
            <div key={i} className={`round ${defending(i) ? "def" : "att"} ${i === 12 ? "half" : ""}`}>
              <div className="rn">R{i + 1}{i === 0 || i === 12 ? " · pistol" : ""}</div>
              {defending(i) ? (
                <select value={p} onChange={(e) => setPlan(plan.map((x, j) => (j === i ? e.target.value : x)))}>
                  {options.map((o) => (
                    <option key={o} value={o}>{label(o)}</option>
                  ))}
                </select>
              ) : (
                <div className="muted small">We attack</div>
              )}
              {defending(i) && value(p) < 0 && <div className="leak small">Risky vs their habits</div>}
            </div>
          ))}
        </div>
        <h3>When we attack</h3>
        {retakes.length ? (
          <ul className="tells">
            {retakes.map((t, i) => (
              <li key={i}>
                <span className={`chip conf-${t.confidence}`}>{t.confidence} confidence · {t.n} rounds</span>
                <div>{t.text}</div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">
            No defensive weakness of theirs held steady over time in the data (retakes, early aggression), so there is no
            opponent-specific attack call. Play your own default.
          </p>
        )}
        <p className="muted small">
          {a.calibrated
            ? `Call values use the data: a first kill swings a defence round by ${pct(index.sim_calibration?.first_kill_swing)}; an extra defender at the fight is credited a quarter of that (${pct(a.stackGain)}).`
            : "Call values use default assumptions (no calibration in the data yet)."}
        </p>
        <div className="row end">
          <Link className="button" href={`/simulation?team=${team}&map=${map}`}>Simulate this plan →</Link>
        </div>
      </section>
    </>
  );
}

export default function TacticsPage() {
  return (
    <Suspense>
      <Nav />
      <main className="page">
        <TacticsView />
      </main>
    </Suspense>
  );
}
