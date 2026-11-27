import type { SiteMix } from "@/lib/data";

/** Schematic map: site positions from clustered plants, circle size = share of attacks. */
export default function MiniMap({
  centers,
  mix,
  highlight,
}: {
  centers?: Record<string, [number, number]>;
  mix: SiteMix;
  highlight?: string | null;
}) {
  if (!centers) return null;
  const pts = Object.entries(centers);
  const xs = pts.map(([, p]) => p[0]);
  const ys = pts.map(([, p]) => p[1]);
  const pad = 2000;
  const minX = Math.min(...xs) - pad, maxX = Math.max(...xs) + pad;
  const minY = Math.min(...ys) - pad, maxY = Math.max(...ys) + pad;
  const W = 320, H = 220;
  const sx = (x: number) => ((x - minX) / (maxX - minX)) * W;
  const sy = (y: number) => H - ((y - minY) / (maxY - minY)) * H;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="minimap" role="img" aria-label="Schematic minimap of bomb sites">
      <rect x="0" y="0" width={W} height={H} rx="8" className="minimap-bg" />
      {pts.map(([s, [x, y]]) => {
        const share = mix[s] ?? 0;
        const r = 14 + share * 46;
        const on = highlight === s;
        return (
          <g key={s}>
            <circle cx={sx(x)} cy={sy(y)} r={r} className={on ? "site site-on" : "site"} />
            <text x={sx(x)} y={sy(y) + 5} textAnchor="middle" className="site-label">
              {s} · {Math.round(share * 100)}%
            </text>
          </g>
        );
      })}
    </svg>
  );
}
