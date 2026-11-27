const screens = [
  { name: "Opponent report", desc: "Site habits and early-round tells" },
  { name: "Tactics", desc: "Plan your setup round by round" },
  { name: "Simulation timeline", desc: "Where your setup leaks, round by round" },
];

export default function Home() {
  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: "48px 16px" }}>
      <h1 style={{ margin: 0 }}>
        Anti<span style={{ color: "var(--accent)" }}>Strat</span>
      </h1>
      <p style={{ color: "var(--muted)" }}>VALORANT Tactical Manager · Haven &amp; Lotus</p>
      <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", marginTop: 32 }}>
        {screens.map((s) => (
          <section key={s.name} style={{ background: "var(--panel)", borderRadius: 8, padding: 20 }}>
            <h2 style={{ margin: "0 0 8px", fontSize: 18 }}>{s.name}</h2>
            <p style={{ margin: 0, color: "var(--muted)" }}>{s.desc}</p>
          </section>
        ))}
      </div>
    </main>
  );
}
