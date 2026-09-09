/**
 * Evidence Explorer -- the row-level truth the rest of the product rests on.
 *
 * One row per (raw event, mapping). Provenance is a stored column, not a
 * rendering choice: a value can read PASS and still be DEFAULTED, and the
 * only place a reader can check that is here.
 */
import { useMemo, useState } from "react";
import { Search } from "lucide-react";

import DataGate from "../components/DataGate";
import PageHeader from "../components/PageHeader";
import { Pill, ProvenanceChip } from "../components/Badges";
import { shortDate } from "../data/model";
import type { WorkbenchData } from "../types/claris";

const PROVENANCES = ["All", "OBSERVED", "DEFAULTED", "DERIVED"] as const;
const PAGE = 60;

function Body({ data }: { data: WorkbenchData }) {
  const [provenance, setProvenance] = useState<string>("All");
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(PAGE);

  const rows = useMemo(() => data.evidence.filter((e) => {
    if (provenance !== "All" && e.value_provenance !== provenance) return false;
    if (!query) return true;
    const hay = `${e.subject_id} ${e.property_name} ${e.mapping_id} ${e.event_type ?? ""} ${e.asserted_value ?? ""}`;
    return hay.toLowerCase().includes(query.toLowerCase());
  }), [data.evidence, provenance, query]);

  return (
    <>
      <PageHeader
        title="Evidence Explorer"
        horizon={data.horizon}
        sub={`${data.totals.evidence} rows across ${data.totals.mappings} mappings — ${data.totals.observed} asserted by a source, ${data.totals.defaulted} supplied by projection logic.`}
      />

      <div className="px-5 py-6 lg:px-8">
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex gap-1 rounded-lg border border-slate-200 bg-white p-1">
            {PROVENANCES.map((p) => (
              <button key={p} type="button"
                onClick={() => { setProvenance(p); setLimit(PAGE); }}
                className={`rounded-md px-2.5 py-1 text-[12.5px] font-medium transition ${
                  provenance === p ? "bg-claris-700 text-white"
                                   : "text-slate-600 hover:bg-slate-100"}`}>
                {p}
              </button>
            ))}
          </div>
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-[14px] w-[14px] -translate-y-1/2 text-slate-400" />
            <input value={query}
              onChange={(e) => { setQuery(e.target.value); setLimit(PAGE); }}
              placeholder="Subject, property, mapping or event type"
              className="w-[300px] rounded-lg border border-slate-200 bg-white py-[7px] pl-8 pr-3 text-[12.5px] text-slate-700 placeholder:text-slate-400" />
          </div>
          <span className="ml-auto text-[12px] text-slate-500">
            {rows.length} row{rows.length === 1 ? "" : "s"}
          </span>
        </div>

        <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full min-w-[1040px] text-[12px]">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/70 text-left text-slate-500">
                <th className="px-4 py-2.5 font-medium">Subject</th>
                <th className="px-4 py-2.5 font-medium">Property</th>
                <th className="px-4 py-2.5 font-medium">Value</th>
                <th className="px-4 py-2.5 font-medium">Provenance</th>
                <th className="px-4 py-2.5 font-medium">Mapping</th>
                <th className="px-4 py-2.5 font-medium">Source</th>
                <th className="px-4 py-2.5 font-medium">Occurred</th>
                <th className="px-4 py-2.5 font-medium">Received</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, limit).map((e, i) => (
                <tr key={`${e.mapping_id}-${e.subject_id}-${e.property_name}-${i}`}
                    className="border-b border-slate-100 last:border-0">
                  <td className="px-4 py-2 align-top">
                    <div className="font-medium text-claris-900">{e.subject_id}</div>
                    <div className="text-[11px] text-slate-400">{e.subject_type}</div>
                  </td>
                  <td className="px-4 py-2 align-top text-slate-700">{e.property_name}</td>
                  <td className="px-4 py-2 align-top text-slate-700">{e.asserted_value ?? "—"}</td>
                  <td className="px-4 py-2 align-top">
                    <ProvenanceChip provenance={e.value_provenance} />
                  </td>
                  <td className="px-4 py-2 align-top font-mono text-[11px] text-slate-500">
                    {e.mapping_id}
                  </td>
                  <td className="px-4 py-2 align-top text-slate-600">
                    {e.source_system}
                    {e.source_actor_role && (
                      <div className="text-[11px] text-slate-400">{e.source_actor_role}</div>
                    )}
                  </td>
                  <td className="px-4 py-2 align-top text-slate-500">{shortDate(e.occurred_at)}</td>
                  <td className="px-4 py-2 align-top text-slate-500">{shortDate(e.arrival_at)}</td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-slate-500">
                    No evidence matches this filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {rows.length > limit && (
          <button type="button" onClick={() => setLimit((n) => n + PAGE)}
            className="mt-3 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[12.5px] text-slate-600 hover:border-slate-300">
            Show {Math.min(PAGE, rows.length - limit)} more
          </button>
        )}

        <p className="mt-4 flex flex-wrap items-center gap-2 text-[12px] text-slate-500">
          <Pill tone="ready">OBSERVED</Pill> a source asserted this value.
          <Pill tone="attention">DEFAULTED</Pill> projection logic supplied it
          because the source was silent about it. Readiness policy accepts only
          the first.
        </p>
      </div>
    </>
  );
}

export default function EvidenceExplorer() {
  return <DataGate>{(data) => <Body data={data} />}</DataGate>;
}
