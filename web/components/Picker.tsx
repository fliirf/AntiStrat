"use client";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import type { Index } from "@/lib/data";
import { cap } from "@/lib/data";

export default function Picker({ index }: { index: Index }) {
  const router = useRouter();
  const path = usePathname();
  const qs = useSearchParams();
  const team = qs.get("team") ?? index.opponents[0]?.id ?? "";
  const opp = index.opponents.find((o) => o.id === team) ?? index.opponents[0];
  const map = qs.get("map") ?? opp?.maps[0] ?? "";
  const go = (t: string, m: string) => router.push(`${path}?team=${encodeURIComponent(t)}&map=${encodeURIComponent(m)}`);
  if (!opp) return <p className="muted">No opponents of {index.target} in the data yet.</p>;
  return (
    <div className="picker">
      <label>
        Opponent
        <select value={opp.id} onChange={(e) => {
          const o = index.opponents.find((x) => x.id === e.target.value)!;
          go(o.id, o.maps.includes(map) ? map : o.maps[0]);
        }}>
          {index.opponents.map((o) => (
            <option key={o.id} value={o.id}>{o.name}</option>
          ))}
        </select>
      </label>
      <label>
        Map
        <select value={map} onChange={(e) => go(opp.id, e.target.value)}>
          {opp.maps.map((m) => (
            <option key={m} value={m}>{cap(m)}</option>
          ))}
        </select>
      </label>
    </div>
  );
}

export function useSelection(index: Index | null) {
  const qs = useSearchParams();
  if (!index) return { team: "", map: "" };
  const team = qs.get("team") ?? index.opponents[0]?.id ?? "";
  const opp = index.opponents.find((o) => o.id === team) ?? index.opponents[0];
  return { team: opp?.id ?? "", map: qs.get("map") ?? opp?.maps[0] ?? "" };
}
