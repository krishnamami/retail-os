/**
 * Every governed property on one subject, with how it came to exist.
 *
 * OBSERVED, DEFAULTED and UNREPORTED are never collapsed into a single
 * "present / missing" column. That collapse is exactly what let eight SKUs
 * read PASS on a value no source ever asserted.
 *
 * This is the trust surface, so it stays technical: real property names, real
 * vocabulary, no translation. The business words live on Overview.
 */
import { useMemo, useState } from "react";

import { ProvenanceChip } from "./Badges";
import { shortDate } from "../data/model";
import type { PropertyBag } from "../types/claris";

type Filter = "All" | "Reported" | "Defaulted" | "Not reported";

export default function EvidenceTable({ properties }: { properties: PropertyBag }) {
  const [filter, setFilter] = useState<Filter>("All");
  const names = useMemo(() => Object.keys(properties).sort(), [properties]);

  const counts = useMemo(() => {
    const established = names.filter(
      (n) => properties[n].fold_state === "ESTABLISHED");
    return {
      All: names.length,
      Reported: established.length,
      Defaulted: established.filter((n) => properties[n].provenance === "DEFAULTED").length,
      "Not reported": names.length - established.length,
    } satisfies Record<Filter, number>;
  }, [names, properties]);

  const shown = names.filter((name) => {
    const p = properties[name];
    const established = p.fold_state === "ESTABLISHED";
    if (filter === "Reported") return established;
    if (filter === "Defaulted") return established && p.provenance === "DEFAULTED";
    if (filter === "Not reported") return !established;
    return true;
  });

  if (names.length === 0) {
    return <p className="text-[13px] text-slate-500">No governed properties for this subject.</p>;
  }

  const FILTERS: Filter[] = ["All", "Reported", "Defaulted", "Not reported"];

  return (
    <div>
      <div className="mb-3.5 flex flex-wrap items-center gap-1 rounded-lg border border-slate-200 bg-white p-1">
        {FILTERS.map((name) => (
          <button key={name} type="button" onClick={() => setFilter(name)}
            className={`rounded-md px-2.5 py-1 text-[12.5px] font-medium transition ${
              filter === name ? "bg-claris-700 text-white"
                              : "text-slate-600 hover:bg-slate-100"}`}>
            {counts[name]} {name === "All" ? "properties" : name.toLowerCase()}
          </button>
        ))}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-[12.5px]">
          <thead>
            <tr className="border-b border-slate-200 text-left text-slate-500">
              <th className="py-2 pr-3 font-medium">Property</th>
              <th className="py-2 pr-3 font-medium">Value</th>
              <th className="py-2 pr-3 font-medium">Provenance</th>
              <th className="py-2 pr-3 font-medium">Basis</th>
              <th className="py-2 pr-3 font-medium">Occurred</th>
              <th className="py-2 font-medium">Received</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((name) => {
              const p = properties[name];
              const established = p.fold_state === "ESTABLISHED";
              return (
                <tr key={name} className="border-b border-slate-100 last:border-0">
                  <td className="py-2 pr-3 align-top">
                    <span className="font-mono text-[11.5px] font-medium text-claris-900">
                      {name}
                    </span>
                    {p.simulated_actor && (
                      <span className="ml-2 rounded bg-quiet-bg px-1.5 py-0.5 text-[10.5px] text-quiet-fg">
                        simulated actor
                      </span>
                    )}
                  </td>
                  <td className="py-2 pr-3 align-top text-slate-700">
                    {established ? p.value ?? "—" : <span className="text-slate-400">—</span>}
                  </td>
                  <td className="py-2 pr-3 align-top">
                    <ProvenanceChip provenance={p.provenance} foldState={p.fold_state} />
                  </td>
                  <td className="py-2 pr-3 align-top text-slate-500">
                    {p.basis_count ?? 0}
                    {p.defaulted_count ? ` (${p.defaulted_count} defaulted)` : ""}
                  </td>
                  <td className="py-2 pr-3 align-top text-slate-500">{shortDate(p.effective_at)}</td>
                  <td className="py-2 align-top text-slate-500">{shortDate(p.arrival_at)}</td>
                </tr>
              );
            })}
            {shown.length === 0 && (
              <tr>
                <td colSpan={6} className="py-8 text-center text-slate-500">
                  No properties in this category.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-[12px] leading-relaxed text-slate-500">
        Provenance is recorded per row. A value marked DEFAULTED exists because
        projection logic supplied it, not because a source asserted it — which
        is why readiness policy accepts only OBSERVED evidence.
      </p>
    </div>
  );
}
