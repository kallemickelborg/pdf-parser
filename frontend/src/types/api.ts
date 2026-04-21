export type ParseStatus = "parsed" | "partial" | "failed";

export interface CanonicalInvoice {
  invoice_no: string | null;
  vendor: string | null;
  customer: string | null;
  due_date: string | null;
  gross_total_amount: string | null;
  billing_type: string | null;
  currency: string | null;
}

export interface ParseResult {
  id: string;
  source_file: string;
  status: ParseStatus;
  invoice: CanonicalInvoice;
  adapter_used: string | null;
  adapters_tried: string[];
  missing_fields: string[];
  warnings: string[];
  error: string | null;
  text_preview: string;
}

export interface Summary {
  total: number;
  parsed: number;
  partial: number;
  failed: number;
  pdf_input_dir: string;
  run_id: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface InvoicesResponse {
  summary: Summary;
  results: ParseResult[];
}

export type StatusFilter = "all" | ParseStatus;
