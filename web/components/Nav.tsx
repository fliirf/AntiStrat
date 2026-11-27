"use client";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

const tabs = [
  { href: "/report", label: "Opponent report" },
  { href: "/tactics", label: "Tactics" },
  { href: "/simulation", label: "Simulation" },
];

export default function Nav() {
  const path = usePathname();
  const qs = useSearchParams().toString();
  return (
    <header className="nav">
      <Link href="/" className="brand">
        Anti<span>Strat</span>
      </Link>
      <nav>
        {tabs.map((t) => (
          <Link key={t.href} href={qs ? `${t.href}?${qs}` : t.href} className={path === t.href ? "tab active" : "tab"}>
            {t.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
