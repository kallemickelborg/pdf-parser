import { useState } from "react";
import { InvoiceTable } from "./components/InvoiceTable";
import { SummaryCards } from "./components/SummaryCards";
import { useInvoices } from "./hooks/useInvoices";
import type { StatusFilter } from "./types/api";

export default function App() {
  const [filter, setFilter] = useState<StatusFilter>("all");
  const { data, loading, error, reparse, reparsing } = useInvoices(filter);

  if (loading && !data) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <div className="text-center">
          <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-slate-800" />
          <p className="text-slate-600">Parsing PDFs...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <div className="max-w-md rounded-lg border border-red-200 bg-red-50 p-6 text-center">
          <p className="mb-2 text-lg font-semibold text-red-800">
            Failed to load data
          </p>
          <p className="text-sm text-red-600">{error}</p>
          <p className="mt-3 text-xs text-red-500">
            Make sure the backend is running on port 8000.
          </p>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const partialWithoutInvoiceNo = data.results.filter(
    (r) => r.status !== "parsed" && !r.invoice.invoice_no
  ).length;

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white shadow-sm">
        <div className="mx-auto max-w-[1400px] px-6 py-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-xl font-bold text-slate-900">
                PDF Invoice Parser
              </h1>
              <p className="text-sm text-slate-500">
                Canonical invoice extraction — input:{" "}
                <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700">
                  {data.summary.pdf_input_dir}
                </code>
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => void reparse()}
                disabled={reparsing}
                className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50"
              >
                {reparsing ? "Re-parsing..." : "Re-parse folder"}
              </button>
              <a
                href="/api/export.xlsx"
                download
                className="rounded-md border border-slate-900 bg-slate-900 px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-slate-800"
              >
                Export validated (XLSX)
              </a>
              <a
                href="/api/export.xlsx?include_partial=true"
                download
                className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50"
                title="Includes partially-parsed rows"
              >
                Export all (XLSX)
              </a>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1400px] space-y-6 px-6 py-6">
        <SummaryCards
          summary={data.summary}
          activeFilter={filter}
          onFilterChange={setFilter}
        />

        {partialWithoutInvoiceNo > 0 && filter !== "failed" && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <strong>{partialWithoutInvoiceNo}</strong> PDF(s) could not extract
            an invoice number. These likely use a template/language the current
            adapters don&apos;t recognize — review them below, or add a new
            adapter for that template.
          </div>
        )}

        <InvoiceTable results={data.results} />
      </main>
    </div>
  );
}
