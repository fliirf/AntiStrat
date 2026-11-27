export default function SampleBanner({ show }: { show?: boolean }) {
  if (!show) return null;
  return (
    <div className="banner">
      Sample data: these numbers come from a synthetic dataset. Run the pipeline on the GRID data to see real reports.
    </div>
  );
}
