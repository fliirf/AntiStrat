import Link from "next/link";

const screens = [
  { href: "/report", name: "Opponent report", desc: "Site habits and the early-round tells that give away the hit." },
  { href: "/tactics", name: "Tactics", desc: "Make a call for every defense round: default, play the read, or stack a site." },
  { href: "/simulation", name: "Simulation", desc: "5,000 simulated maps show where your setup leaks." },
];

export default function Home() {
  return (
    <main className="page">
      <h1 className="hero">
        Anti<span>Strat</span>
      </h1>
      <p className="muted lead">VALORANT Tactical Manager · prepare for Cloud9's opponents on Haven and Lotus</p>
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
