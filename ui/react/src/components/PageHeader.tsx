/** Consistent page heading, with the decision horizon always in view. */
import type { ReactNode } from "react";

export default function PageHeader({ title, sub, right, horizon }: {
  title: string; sub?: ReactNode; right?: ReactNode; horizon?: string;
}) {
  return (
    <div className="border-b border-slate-200 bg-white px-5 py-5 lg:px-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-[21px] font-semibold tracking-[-0.02em] text-claris-900">
            {title}
          </h1>
          {sub && (
            <p className="mt-1 max-w-[760px] text-[13px] leading-relaxed text-slate-500">
              {sub}
            </p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">{right}</div>
      </div>
      {horizon && (
        <p className="mt-3 text-[11.5px] text-slate-400">
          Decision horizon {horizon} — every state on this page is as known at
          that instant, not as of now.
        </p>
      )}
    </div>
  );
}
