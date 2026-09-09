/**
 * Product Launch Command Center — what needs attention, and who needs to act.
 *
 * Three numbers, one sentence, one table. Evidence counts, provenance chips
 * and last-activity stamps used to live in these rows; they were the
 * platform's bookkeeping rather than the reader's question, and they now live
 * one click deeper on the case.
 *
 * Every row reads its outcome from a governed decision. This page groups,
 * labels and orders, and nothing more.
 */
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowRight, ChevronDown, Info, Search } from "lucide-react";

import DataGate from "../components/DataGate";
import PageHeader from "../components/PageHeader";
import { OutcomeBadge } from "../components/Badges";
import {
  PERSONAS, ageInDays, buildKpis, buildPortfolio, typeCounts,
} from "../data/model";
import type { PortfolioCase } from "../data/model";
import { identityLabel, primaryBlocker } from "../data/language";
import type { WorkbenchData } from "../types/claris";

const KINDS = ["All", "Launch", "Change", "Configuration request"] as const;

/** English, not string concatenation: "Launch" does not pluralise to "Launchs". */
const PLURAL: Record<string, (n: number) => string> = {
  Launch: (n) => (n === 1 ? "Launch" : "Launches"),
  Change: (n) => (n === 1 ? "Change" : "Changes"),
  "Configuration request": (n) =>
    n === 1 ? "Configuration Request" : "Configuration Requests",
};

const KPI_TONE: Record<string, string> = {
  ready: "text-ready-fg", attention: "text-attention-fg",
  blocked: "text-blocked-fg", quiet: "text-claris-900",
};

function Board({ data }: { data: WorkbenchData }) {
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState("");
  const [why, setWhy] = useState(false);

  const cases = useMemo(() => buildPortfolio(data), [data]);
  const kpis = useMemo(() => buildKpis(cases), [cases]);
  const counts = useMemo(() => typeCounts(cases), [cases]);

  const kind = params.get("kind") ?? "All";
  const persona = params.get("persona") ?? "All";

  const rows = cases.filter((c) => {
    if (kind !== "All" && c.kind !== kind) return false;
    if (persona !== "All" && c.waitingOnPersona !== persona) return false;
    if (query && !`${c.id} ${c.product ?? ""}`.toLowerCase()
        .includes(query.toLowerCase())) return false;
    return true;
  });

  function setParam(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value === "All") next.delete(key); else next.set(key, value);
    setParams(next, { replace: true });
  }

  const ready = kpis.find((k) => k.label === "Ready")?.value ?? 0;

  return (
    <>
      <PageHeader
        title="Product Launch Command Center"
        sub="All launches, changes and configuration requests."
        horizon={data.horizon}
      />

      <div className="px-5 py-6 lg:px-8">
        <div className="grid gap-3 sm:grid-cols-3">
          {kpis.map((kpi) => (
            <div key={kpi.label} className="rounded-xl border border-slate-200 bg-white p-5">
              <div className={`text-[34px] font-semibold leading-none ${KPI_TONE[kpi.tone]}`}>
                {kpi.value}
              </div>
              <div className="mt-1.5 text-[13.5px] font-semibold text-claris-900">
                {kpi.label}
              </div>
              <div className="mt-0.5 text-[11.5px] leading-snug text-slate-400">
                {kpi.hint}
              </div>
            </div>
          ))}
        </div>

        <p className="mt-2.5 text-[12.5px] text-slate-500">
          {counts.map((c, i) => (
            <span key={c.kind}>
              {i > 0 && <span className="mx-1.5 text-slate-300">·</span>}
              <b className="font-semibold text-slate-700">{c.count}</b>{" "}
              {PLURAL[c.kind](c.count)}
            </span>
          ))}
        </p>

        {ready === 0 && (
          <div className="mt-4 rounded-xl border border-attention-br bg-attention-bg p-4">
            <div className="flex items-start gap-2.5">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-attention-fg" />
              <p className="min-w-0 flex-1 text-[13px] leading-relaxed text-attention-fg">
                <b>No cases currently satisfy launch-readiness requirements.</b>{" "}
                Required evidence is incomplete or not source-confirmed. The
                platform will not mark a launch ready until governed
                requirements are satisfied.
              </p>
              <button type="button" onClick={() => setWhy((v) => !v)}
                className="inline-flex shrink-0 items-center gap-1 text-[12.5px] font-medium text-attention-fg underline-offset-2 hover:underline">
                Why?
                <ChevronDown className={`h-3.5 w-3.5 transition ${why ? "rotate-180" : ""}`} />
              </button>
            </div>
            {why && (
              <p className="mt-3 border-t border-attention-br pt-3 text-[12.5px] leading-relaxed text-attention-fg/90">
                In this dataset the cases carrying pricing approval are not the
                same cases carrying technical and activation confirmation, so no
                single case has every required fact reported by a source.
                Readiness requirements were not relaxed to produce a ready
                case — a governed negative outcome is an answer, not an
                application error.
              </p>
            )}
          </div>
        )}

        <div className="mt-5 flex flex-wrap items-center gap-2">
          <div className="flex gap-1 rounded-lg border border-slate-200 bg-white p-1">
            {KINDS.map((k) => (
              <button key={k} type="button" onClick={() => setParam("kind", k)}
                className={`rounded-md px-2.5 py-1 text-[12.5px] font-medium transition ${
                  kind === k ? "bg-claris-700 text-white"
                             : "text-slate-600 hover:bg-slate-100"}`}>
                {k}
                {k !== "All" && (
                  <span className="ml-1 opacity-60">
                    {cases.filter((c) => c.kind === k).length}
                  </span>
                )}
              </button>
            ))}
          </div>

          <select value={persona}
            onChange={(e) => setParam("persona", e.target.value)}
            className="rounded-lg border border-slate-200 bg-white px-2.5 py-[7px] text-[12.5px] text-slate-700">
            <option value="All">All teams</option>
            {PERSONAS.map((p) => (
              <option key={p} value={p}>Needs action from: {p}</option>
            ))}
          </select>

          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-[14px] w-[14px] -translate-y-1/2 text-slate-400" />
            <input value={query} onChange={(e) => setQuery(e.target.value)}
              placeholder="Search cases, products…"
              className="w-[248px] rounded-lg border border-slate-200 bg-white py-[7px] pl-8 pr-3 text-[12.5px] text-slate-700 placeholder:text-slate-400" />
          </div>

          <span className="ml-auto text-[12px] text-slate-500">
            {rows.length} of {cases.length}
          </span>
        </div>

        <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full min-w-[820px] text-[13px]">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/70 text-left text-[12px] text-slate-500">
                <th className="px-4 py-2.5 font-medium">Case</th>
                <th className="px-4 py-2.5 font-medium">Type</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium">Needs action from</th>
                <th className="px-4 py-2.5 font-medium">Blocker</th>
                <th className="px-4 py-2.5 font-medium">Age</th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => <Row key={`${row.kind}-${row.id}`}
                                      row={row} horizon={data.horizon} />)}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-slate-500">
                    No cases match this filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <p className="mt-3 text-[12px] leading-relaxed text-slate-400">
          Launches and changes are listed side by side. The governed model does
          not record which launch a change belongs to, so this board does not
          assert one.
        </p>
      </div>
    </>
  );
}

function Row({ row, horizon }: { row: PortfolioCase; horizon: string }) {
  const age = ageInDays(row.firstActivity, horizon);
  const blocker = primaryBlocker(row.agent);
  const label = blocker?.short
    ?? (row.blockerKind === "ABSENT_EVIDENCE" ? "Identity incomplete" : null);

  return (
    <tr className="border-b border-slate-100 last:border-0 hover:bg-slate-50/60">
      <td className="px-4 py-3 align-middle">
        <Link to={`/launches/${encodeURIComponent(row.id)}`}
              className="font-semibold text-claris-800 hover:underline">
          {row.id}
        </Link>
      </td>
      <td className="px-4 py-3 align-middle text-slate-600">{row.kind}</td>
      <td className="px-4 py-3 align-middle">
        <OutcomeBadge
          outcome={row.outcome}
          label={row.kind === "Configuration request"
            ? identityLabel(row.outcome) : undefined} />
      </td>
      <td className="px-4 py-3 align-middle text-slate-700">
        {row.waitingOnPersona ?? row.waitingOnRole ?? <span className="text-slate-300">—</span>}
      </td>
      <td className="px-4 py-3 align-middle text-slate-600">
        {label ?? <span className="text-slate-300">—</span>}
      </td>
      <td className="whitespace-nowrap px-4 py-3 align-middle text-slate-500">
        {age === null ? "—" : `${age}d`}
      </td>
      <td className="px-4 py-3 text-right align-middle">
        <Link to={`/launches/${encodeURIComponent(row.id)}`}
              className="inline-flex items-center gap-1 text-[12.5px] text-claris-600 hover:text-claris-800">
          Open <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </td>
    </tr>
  );
}

export default function CommandCenter() {
  return <DataGate>{(data) => <Board data={data} />}</DataGate>;
}
