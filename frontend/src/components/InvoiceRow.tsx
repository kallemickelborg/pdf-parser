import { useState } from "react";
import type { ParseResult } from "../types/api";
import { StatusBadge } from "./StatusBadge";

interface InvoiceRowProps {
  result: ParseResult;
}

function formatValue(value: string | null): string {
  if (value === null || value === "") return "—";
  return value;
}

export function InvoiceRow({ result }: InvoiceRowProps) {
  const [expanded, setExpanded] = useState(false);
  const inv = result.invoice;
  const canExpand =
    result.missing_fields.length > 0 ||
    result.warnings.length > 0 ||
    result.error !== null ||
    result.text_preview !== "";

  return (
    <>
      <tr className="border-b border-slate-100 hover:bg-slate-50">
        <td className="px-3 py-2">
          <button
            type="button"
            onClick={() => setExpanded((e) => !e)}
            disabled={!canExpand}
            className="text-slate-500 hover:text-slate-800 disabled:text-slate-300"
            aria-label={expanded ? "Collapse" : "Expand"}
          >
            {expanded ? "▾" : "▸"}
          </button>
        </td>
        <td className="px-3 py-2">
          <StatusBadge status={result.status} />
        </td>
        <td className="px-3 py-2 font-mono text-xs text-slate-700">
          {result.source_file}
        </td>
        <td className="px-3 py-2 font-medium">{formatValue(inv.invoice_no)}</td>
        <td className="px-3 py-2">{formatValue(inv.vendor)}</td>
        <td className="px-3 py-2">{formatValue(inv.customer)}</td>
        <td className="px-3 py-2">{formatValue(inv.due_date)}</td>
        <td className="px-3 py-2 text-right tabular-nums">
          {formatValue(inv.gross_total_amount)}
        </td>
        <td className="px-3 py-2">{formatValue(inv.currency)}</td>
        <td className="px-3 py-2">{formatValue(inv.billing_type)}</td>
        <td className="px-3 py-2 text-xs text-slate-500">
          {result.adapter_used ?? "—"}
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-slate-100 bg-slate-50/50">
          <td colSpan={11} className="px-6 py-3">
            <DetailsPanel result={result} />
          </td>
        </tr>
      )}
    </>
  );
}

function DetailsPanel({ result }: { result: ParseResult }) {
  return (
    <div className="space-y-3 text-sm">
      {result.missing_fields.length > 0 && (
        <div>
          <span className="font-semibold text-slate-700">Missing fields: </span>
          <span className="text-amber-700">
            {result.missing_fields.join(", ")}
          </span>
        </div>
      )}
      {result.adapters_tried.length > 0 && (
        <div>
          <span className="font-semibold text-slate-700">Adapters tried: </span>
          <span className="text-slate-600">
            {result.adapters_tried.join(" → ")}
          </span>
        </div>
      )}
      {result.warnings.length > 0 && (
        <div>
          <span className="font-semibold text-slate-700">Warnings:</span>
          <ul className="ml-6 list-disc text-slate-600">
            {result.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      )}
      {result.error && (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-red-800">
          <span className="font-semibold">Error: </span>
          {result.error}
        </div>
      )}
      {result.text_preview && (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs font-medium text-slate-500">
            Text preview
          </summary>
          <pre className="mt-2 max-h-56 overflow-auto whitespace-pre-wrap rounded bg-white p-2 font-mono text-xs text-slate-700">
            {result.text_preview}
          </pre>
        </details>
      )}
    </div>
  );
}
