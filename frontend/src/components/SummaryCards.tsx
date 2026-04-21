import type { StatusFilter, Summary } from "../types/api";

interface SummaryCardsProps {
  summary: Summary;
  activeFilter: StatusFilter;
  onFilterChange: (filter: StatusFilter) => void;
}

interface CardConfig {
  label: string;
  filter: StatusFilter;
  getValue: (s: Summary) => number;
  accent: string;
}

const CARDS: CardConfig[] = [
  {
    label: "Total PDFs",
    filter: "all",
    getValue: (s) => s.total,
    accent: "border-slate-400 bg-slate-50",
  },
  {
    label: "Fully Parsed",
    filter: "parsed",
    getValue: (s) => s.parsed,
    accent: "border-emerald-400 bg-emerald-50",
  },
  {
    label: "Partial",
    filter: "partial",
    getValue: (s) => s.partial,
    accent: "border-amber-400 bg-amber-50",
  },
  {
    label: "Failed",
    filter: "failed",
    getValue: (s) => s.failed,
    accent: "border-red-400 bg-red-50",
  },
];

export function SummaryCards({
  summary,
  activeFilter,
  onFilterChange,
}: SummaryCardsProps) {
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {CARDS.map((card) => {
        const isActive = activeFilter === card.filter;
        return (
          <button
            key={card.filter}
            type="button"
            onClick={() => onFilterChange(card.filter)}
            className={`rounded-lg border-l-4 p-4 text-left shadow-sm transition ${card.accent} ${
              isActive
                ? "ring-2 ring-slate-900 ring-offset-2"
                : "hover:shadow-md"
            }`}
          >
            <p className="text-sm font-medium text-gray-600">{card.label}</p>
            <p className="mt-1 text-3xl font-bold text-gray-900">
              {card.getValue(summary)}
            </p>
          </button>
        );
      })}
    </div>
  );
}
