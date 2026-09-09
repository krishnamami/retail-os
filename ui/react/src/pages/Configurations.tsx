/**
 * Configuration Decisions — the SKU proliferation story, told in four numbers
 * and one table.
 *
 * Two governed decisions per request matter to a business reader: the FIRST,
 * which says what the request caused when it arrived, and the CURRENT, which
 * says what the same request concludes now that those configurations exist.
 * Showing only the current one made every request read "Reuse existing",
 * which erases the creations that produced the configurations in the first
 * place. Both are stored; both are shown; neither is computed here.
 *
 * The canonical identity string is real and it matters, but it is not how an
 * executive understands proliferation. It lives one disclosure deeper.
 */
import { useMemo, useState } from "react";
import { ChevronDown, Layers } from "lucide-react";
import { Link } from "react-router-dom";

import DataGate from "../components/DataGate";
import PageHeader from "../components/PageHeader";
import { OutcomeBadge, Pill } from "../components/Badges";
import { buildPortfolio, shortDate } from "../data/model";
import {
  businessIdentity, currentDecision, firstDecision, identityLabel,
} from "../data/language";
import type { WorkbenchData } from "../types/claris";

const IDENTITY_FACTS = [
  "product_reference", "geography", "term_months", "customer_segment",
];

function Metric({ value, label, hint, tone = "quiet" }: {
  value: number; label: string; hint: string; tone?: string;
}) {
  const colour: Record<string, string> = {
    quiet: "text-claris-900", ready: "text-ready-fg", attention: "text-attention-fg",
  };
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className={`text-[32px] font-semibold leading-none ${colour[tone]}`}>{value}</div>
      <div className="mt-1.5 text-[13px] font-semibold text-claris-900">{label}</div>
      <div className="mt-0.5 text-[11.5px] leading-snug text-slate-400">{hint}</div>
    </div>
  );
}

function Body({ data }: { data: WorkbenchData }) {
  const [technical, setTechnical] = useState(false);

  const rows = useMemo(() => {
    return buildPortfolio(data)
      .filter((c) => c.kind === "Configuration request")
      .map((request) => {
        const first = firstDecision(request.decisions);
        const current = currentDecision(request.decisions);
        const complete = IDENTITY_FACTS.every(
          (f) => request.properties[f]?.fold_state === "ESTABLISHED",
        );
        return {
          id: request.id,
          product: request.product,
          identity: businessIdentity(request.properties),
          complete,
          first,
          current,
          requestedAt: request.firstActivity,
        };
      });
  }, [data]);

  const complete = rows.filter((r) => r.complete).length;
  /* A request whose FIRST governed decision was "no business change" reused a
     configuration that already existed. That is a duplicate that did not get
     created -- read from the stored decision, not inferred from the name. */
  const duplicatesAvoided = rows.filter(
    (r) => r.complete && r.first?.outcome_code === "NO_BUSINESS_CHANGE",
  ).length;

  return (
    <>
      <PageHeader
        title="Configuration Decisions"
        sub="From requests to canonical identities. Whether a request describes something that already exists, or something new."
        horizon={data.horizon}
      />

      <div className="space-y-5 px-5 py-6 lg:px-8">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Metric value={rows.length} label="Requests received"
                  hint="configuration requests in governed state" />
          <Metric value={complete} label="Complete identities"
                  hint="all four identity facts reported" />
          <Metric value={data.configurations.length} label="Configurations"
                  hint="distinct configurations that exist" />
          <Metric value={duplicatesAvoided} label="Duplicates avoided" tone="ready"
                  hint="requests that reused an existing configuration" />
        </div>

        <div className="flex gap-2.5 rounded-xl border border-claris-200 bg-claris-50 p-4">
          <Layers className="mt-0.5 h-4 w-4 shrink-0 text-claris-600" />
          <p className="text-[13px] leading-relaxed text-claris-900">
            {complete} complete identities resolve to {data.configurations.length}{" "}
            configurations. The difference is proliferation that did not happen:
            requests worded differently reduced to an identity that already
            existed and reused it, rather than creating another configuration
            for the same commercial thing.
          </p>
        </div>

        <section className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-[14px] font-semibold text-claris-900">Requests</h2>
          <p className="mt-0.5 text-[12px] text-slate-500">
            What each request caused when it arrived, and what the same request
            concludes today. A missing identity fact does not produce a
            near-match — it produces no identity.
          </p>

          <div className="mt-3.5 overflow-x-auto">
            <table className="w-full min-w-[760px] text-[13px]">
              <thead>
                <tr className="border-b border-slate-200 text-left text-[11.5px] text-slate-500">
                  <th className="py-2 pr-3 font-medium">Request</th>
                  <th className="py-2 pr-3 font-medium">Product</th>
                  <th className="py-2 pr-3 font-medium">Business identity</th>
                  <th className="py-2 pr-3 font-medium">Original action</th>
                  <th className="py-2 pr-3 font-medium">Current result</th>
                  <th className="py-2 font-medium">Requested</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className="border-b border-slate-100 last:border-0">
                    <td className="py-2.5 pr-3 align-middle">
                      <Link to={`/launches/${encodeURIComponent(row.id)}`}
                            className="font-medium text-claris-800 hover:underline">
                        {row.id}
                      </Link>
                    </td>
                    <td className="py-2.5 pr-3 align-middle text-slate-600">
                      {row.product ?? "—"}
                    </td>
                    <td className="py-2.5 pr-3 align-middle">
                      {row.identity
                        ? <span className="text-slate-700">{row.identity}</span>
                        : <Pill tone="attention">Identity incomplete</Pill>}
                    </td>
                    <td className="py-2.5 pr-3 align-middle text-slate-700">
                      {identityLabel(row.first?.outcome_code)}
                    </td>
                    <td className="py-2.5 pr-3 align-middle">
                      {row.current
                        ? <OutcomeBadge outcome={row.current.outcome_code}
                                        label={identityLabel(row.current.outcome_code)} />
                        : <span className="text-slate-300">—</span>}
                    </td>
                    <td className="whitespace-nowrap py-2.5 align-middle text-slate-500">
                      {shortDate(row.requestedAt)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="mt-3 text-[12px] leading-relaxed text-slate-400">
            <b className="font-semibold text-slate-500">Original action</b> is the
            first governed decision recorded for the request.{" "}
            <b className="font-semibold text-slate-500">Current result</b> is what
            the platform concludes today, now that those configurations exist —
            which is why a request that created a configuration now reads as
            reusing one.
          </p>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-5">
          <button type="button" onClick={() => setTechnical((v) => !v)}
            className="flex w-full items-center justify-between gap-3 text-left">
            <span>
              <span className="text-[14px] font-semibold text-claris-900">
                Technical detail — canonical identities
              </span>
              <span className="mt-0.5 block text-[12px] text-slate-500">
                How the platform decides two requests are the same thing.
              </span>
            </span>
            <ChevronDown className={`h-4 w-4 shrink-0 text-slate-400 transition ${technical ? "rotate-180" : ""}`} />
          </button>

          {technical && (
            <div className="mt-4 overflow-x-auto border-t border-slate-200 pt-4">
              <table className="w-full min-w-[720px] text-[12.5px]">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-[11.5px] text-slate-500">
                    <th className="py-2 pr-3 font-medium">Configuration</th>
                    <th className="py-2 pr-3 font-medium">Product</th>
                    <th className="py-2 pr-3 font-medium">Canonical identity</th>
                    <th className="py-2 pr-3 font-medium">Status</th>
                    <th className="py-2 pr-3 font-medium">Versions</th>
                    <th className="py-2 font-medium">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {data.configurations.map((c) => (
                    <tr key={c.configuration_id} className="border-b border-slate-100 last:border-0">
                      <td className="py-2 pr-3 align-top font-medium text-claris-900">
                        {c.configuration_id}
                      </td>
                      <td className="py-2 pr-3 align-top text-slate-600">{c.product_id}</td>
                      <td className="py-2 pr-3 align-top font-mono text-[11px] text-slate-500">
                        {c.canonical_identity}
                      </td>
                      <td className="py-2 pr-3 align-top text-slate-600">{c.status}</td>
                      <td className="py-2 pr-3 align-top text-slate-600">{c.versions}</td>
                      <td className="py-2 align-top text-slate-500">{shortDate(c.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-3 text-[12px] leading-relaxed text-slate-500">
                Canonical identity is length-prefixed, so no two different
                tuples can ever collapse into the same string. This is the
                comparison the platform actually performs; the business
                identity above is the same tuple, read aloud.
              </p>
            </div>
          )}
        </section>
      </div>
    </>
  );
}

export default function Configurations() {
  return <DataGate>{(data) => <Body data={data} />}</DataGate>;
}
