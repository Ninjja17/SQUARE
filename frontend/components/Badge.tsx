import { clsx } from "clsx";

type Props = {
  variant?: "passed" | "warning" | "critical" | "new" | "reused" | "go" | "pilot" | "changes" | "default";
  children: React.ReactNode;
  className?: string;
};

const variantMap: Record<string, string> = {
  passed: "badge-passed",
  warning: "badge-warning",
  critical: "badge-critical",
  new: "badge-new",
  reused: "badge-reused",
  go: "badge-go",
  pilot: "badge-pilot",
  changes: "badge-changes",
  default: "border-[#333] text-[#aaa] bg-[#111]",
};

export function Badge({ variant = "default", children, className }: Props) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium border",
        variantMap[variant],
        className
      )}
    >
      {children}
    </span>
  );
}
