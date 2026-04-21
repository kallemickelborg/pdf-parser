import type { ParseStatus } from "../types/api";

interface StatusBadgeProps {
  status: ParseStatus;
}

const STYLES: Record<ParseStatus, string> = {
  parsed: "bg-emerald-100 text-emerald-800 ring-emerald-200",
  partial: "bg-amber-100 text-amber-800 ring-amber-200",
  failed: "bg-red-100 text-red-800 ring-red-200",
};

const LABELS: Record<ParseStatus, string> = {
  parsed: "Parsed",
  partial: "Partial",
  failed: "Failed",
};

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${STYLES[status]}`}
    >
      {LABELS[status]}
    </span>
  );
}
