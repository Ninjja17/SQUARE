import { clsx } from "clsx";

type Props = {
  label: string;
  value: string | number;
  sub?: string;
  highlight?: boolean;
};

export function MetricCard({ label, value, sub, highlight }: Props) {
  return (
    <div className={clsx("card text-center", highlight && "border-white/30")}>
      <p className="text-[11px] uppercase tracking-widest text-[#666] mb-1">{label}</p>
      <p className="text-3xl font-bold text-white">{value}</p>
      {sub && <p className="text-xs text-[#555] mt-1">{sub}</p>}
    </div>
  );
}
