"use client";
import { Suspense, useEffect, useState } from "react";
import Nav from "@/components/Nav";
import { cap, getReport, pct, type Report } from "@/lib/data";
import { useIndex } from "@/lib/useData";

function SelfView() {
  const { index, error } = useIndex();
  const [reports, setReports] = useState<Report[]>([]);
  const self = index?.self?.[0];
  useEffect(() => {
    if (!self) return;
    Promise.all(self.maps.map((m) => getReport(self.id, m).catch(() => null))).then((r) =>
      setReports(r.filter((x): x is Report => x !== null)));
  }, [self]);
  if (error) return <p className="error">{error}</p>;
  if (!index) return <p className="muted">Loading…</p>;
  if (!self) return <p className="muted">No rounds for {index.target} in the data.</p>;

  return (
    <>
      <section className="card">
        <h2>How readable is {self.name}?</h2>
        <p className="muted">
          The same in-round read, pointed at our own attacks: how often it names our site, against the league average on that map.
          Higher than the league means opponents can read us more easily.
        </p>
        <table className="mix">
          <thead>
            <tr><th>Map</th><th>Our rounds</th><th>Read at 15 s</th><th>League</th><th>Read at first contact</th><th>League</th></tr>
          </thead>
          <tbody>
            {reports.map((r) => {
              const avg = index.map_detail?.[r.map]?.read_avg;
              const hot = (a: number | null, b?: number) => (a != null && b != null && a > b + 0.03 ? "leak" : "");
              return (
                <tr key={r.map}>
                  <td>{cap(r.map)}</td>
                  <td className="muted">{r.read_accuracy.contact.n}</td>
                  <td className={hot(r.read_accuracy.early.acc, avg?.early)}>{pct(r.read_accuracy.early.acc)}</td>
                  <td className="muted">{pct(avg?.early)}</td>
                  <td className={hot(r.read_accuracy.contact.acc, avg?.contact)}>{pct(r.read_accuracy.contact.acc)}</td>
                  <td className="muted">{pct(avg?.contact)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="muted small">Maps with fewer than about 30 rounds are too small to act on.</p>
      </section>

      <div className="grid">
        {reports.map((r) => (
          <section className="card" key={r.map}>
            <h3>{cap(r.map)}: what gives our site away</h3>
            {(r.leaks ?? []).length === 0 ? (
              <p className="muted">No signal where we are easier to read than the league.</p>
            ) : (
              <ul className="tells">
                {r.leaks!.map((l, i) => (
                  <li key={i}>
                    <strong>{l.signal}</strong>
                    <div className="muted">
                      → we go {l.site} {pct(l.rate)} of the time, the league {pct(l.league_rate)} · {l.n} rounds
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        ))}
      </div>
    </>
  );
}

export default function SelfPage() {
  return (
    <Suspense>
      <Nav />
      <main className="page">
        <SelfView />
      </main>
    </Suspense>
  );
}
