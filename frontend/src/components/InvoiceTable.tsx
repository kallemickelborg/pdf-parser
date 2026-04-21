import type { ParseResult } from "../types/api";
import { InvoiceRow } from "./InvoiceRow";

interface InvoiceTableProps {
  results: ParseResult[];
}

const COLUMNS = [
  { key: "expand", label: "" },
  { key: "status", label: "Status" },
  { key: "file", label: "File" },
  { key: "invoice_no", label: "Invoice_no" },
  { key: "vendor", label: "Vendor" },
  { key: "customer", label: "Customer" },
  { key: "due_date", label: "Due_Date" },
  { key: "amount", label: "Gross_Total_Amount", align: "right" as const },
  { key: "currency", label: "Currency" },
  { key: "billing_type", label: "Billing_Type" },
  { key: "adapter", label: "Adapter" },
];

export function InvoiceTable({ results }: InvoiceTableProps) {
  if (results.length === 0) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white py-12 text-center text-slate-500">
        No invoices in this view.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <table className="w-full text-sm">
        <thead className="border-b border-slate-200 bg-slate-50">
          <tr>
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                className={`px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-600 ${
                  col.align === "right" ? "text-right" : "text-left"
                }`}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {results.map((r) => (
            <InvoiceRow key={r.id} result={r} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
