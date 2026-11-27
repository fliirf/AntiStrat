import Link from "next/link";

const screens = [
  { href: "/tactics", name: "Call sheet & tactics", desc: "When to rotate: early utility and first-contact rules per map, checked on the newest matches." },
  { href: "/report", name: "Opponent report", desc: "What stays true about them: pace, round 2 after pistol, retakes, with confidence." },
  { href: "/simulation", name: "Simulation", desc: "5,000 simulated maps show where your plan costs win chance." },
];

export default function Home() {
  return (
    <main className="page">
      <h1 className="hero">
        Anti<span>Strat</span>
      </h1>
      <p className="muted lead">VALORANT Tactical Manager · prepare for Cloud9's VCT opponents, map by map</p>
      <div className="cards">
        {screens.map((s) => (
          <Link key={s.href} href={s.href} className="card link">
            <h2>{s.name}</h2>
            <p className="muted">{s.desc}</p>
          </Link>
        ))}
      </div>
    </main>
  );
}
