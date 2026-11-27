/** Utility cast density on a coarse grid, drawn in the same coordinates as the site centres. */
export default function HeatMap({
  cells,
  grid,
  bounds,
  centers,
  color,
  label,
}: {
  cells: Record<string, number>;
  grid: number;
  bounds: [number, number, number, number];
  centers?: Record<string, [number, number]>;
  color: string;
  label: string;
}) {
  const S = 260;
  const [x0, y0, x1, y1] = bounds;
  const cw = S / grid;
  const max = Math.max(1, ...Object.values(cells));
  const sx = (x: number) => ((x - x0) / (x1 - x0)) * S;
  const sy = (y: number) => S - ((y - y0) / (y1 - y0)) * S;
  return (
    <svg viewBox={`0 0 ${S} ${S}`} className="heatmap" role="img" aria-label={label}>
      <rect width={S} height={S} rx="8" className="minimap-bg" />
      {Object.entries(cells).map(([k, v]) => {
        const [i, j] = k.split(",").map(Number);
        return (
          <rect key={k} x={i * cw} y={S - (j + 1) * cw} width={cw} height={cw} fill={color}
            opacity={0.15 + 0.85 * (v / max)} />
        );
      })}
      {centers &&
        Object.entries(centers).map(([s, [x, y]]) => (
          <text key={s} x={sx(x)} y={sy(y) + 6} textAnchor="middle" className="site-label heat-label">{s}</text>
        ))}
    </svg>
  );
}
