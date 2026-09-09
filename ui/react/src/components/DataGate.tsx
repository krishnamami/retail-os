/**
 * One place that answers "what if the governed dataset is not there?".
 *
 * A missing snapshot is a state to explain, not an error boundary to trip.
 * The message names the two commands that produce it, because the person
 * looking at this screen in a demo is the person who can run them.
 */
import type { ReactNode } from "react";
import { Loader2, DatabaseZap } from "lucide-react";

import { useWorkbenchData } from "../data/source";
import type { WorkbenchData } from "../types/claris";

export default function DataGate(
  { children }: { children: (data: WorkbenchData) => ReactNode },
) {
  const { data, isLoading, error } = useWorkbenchData();

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 px-6 py-16 text-[13px] text-slate-500">
        <Loader2 className="h-4 w-4 animate-spin" /> Reading governed state…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="px-5 py-14 lg:px-8">
        <div className="max-w-[620px] rounded-xl border border-attention-br bg-attention-bg p-5">
          <div className="mb-2 flex items-center gap-2 text-[13px] font-semibold text-attention-fg">
            <DatabaseZap className="h-4 w-4" /> No governed snapshot loaded
          </div>
          <p className="text-[13px] leading-relaxed text-attention-fg/90">
            {error instanceof Error
              ? error.message
              : "The governed dataset could not be read."}
          </p>
          <pre className="mt-3 rounded-lg bg-white/70 p-3 font-mono text-[11.5px] text-slate-700">
{`python workbench/collect.py     # reads the database at the horizon
npm run sync-data               # copies out/workbench_data.json here`}
          </pre>
          <p className="mt-3 text-[12px] text-attention-fg/80">
            This screen shows nothing rather than showing placeholder launches.
            An empty board is honest; a fabricated one is not.
          </p>
        </div>
      </div>
    );
  }

  return <>{children(data)}</>;
}
