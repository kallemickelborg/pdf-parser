import { useCallback, useEffect, useState } from "react";
import type { InvoicesResponse, StatusFilter } from "../types/api";

interface UseInvoicesResult {
  data: InvoicesResponse | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
  reparse: () => Promise<void>;
  reparsing: boolean;
}

export function useInvoices(filter: StatusFilter): UseInvoicesResult {
  const [data, setData] = useState<InvoicesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reparsing, setReparsing] = useState(false);

  const fetchData = useCallback(async (): Promise<void> => {
    try {
      setError(null);
      const response = await fetch(`/api/invoices?status=${filter}`);
      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }
      const json = (await response.json()) as InvoicesResponse;
      setData(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [filter]);

  const reparse = useCallback(async (): Promise<void> => {
    setReparsing(true);
    try {
      const response = await fetch("/api/reparse", { method: "POST" });
      if (!response.ok) {
        throw new Error(`Reparse failed with status ${response.status}`);
      }
      await fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setReparsing(false);
    }
  }, [fetchData]);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  return {
    data,
    loading,
    error,
    refetch: fetchData,
    reparse,
    reparsing,
  };
}
