/**
 * The only place the app learns where governed data comes from.
 *
 * Today that is a static JSON file produced by workbench/collect.py. When an
 * API replaces it, this file changes and nothing else does: pages consume
 * useWorkbenchData(), which returns the same shape either way. That is the
 * whole reason the fetch is not written inline in a component.
 */
import { useQuery } from "@tanstack/react-query";

import type { WorkbenchData } from "../types/claris";

export const DATA_URL = `${import.meta.env.BASE_URL}data/workbench_data.json`;

export class DatasetMissing extends Error {}

async function fetchWorkbenchData(): Promise<WorkbenchData> {
  const response = await fetch(DATA_URL, { cache: "no-store" });
  if (!response.ok) {
    throw new DatasetMissing(
      "The governed dataset has not been generated yet. Run " +
      "workbench/collect.py, then npm run sync-data.",
    );
  }
  return (await response.json()) as WorkbenchData;
}

export function useWorkbenchData() {
  return useQuery({
    queryKey: ["workbench-data"],
    queryFn: fetchWorkbenchData,
    staleTime: Infinity,   // a snapshot of governed state; it does not drift
    retry: false,          // a missing file is a state to show, not to retry
  });
}
