/**
 * Decision Record — the governance and audit surface.
 *
 * It had become a dumping ground: full agent email drafts, workbench notes,
 * repeated blocker lists and a table of every stored field, all at the same
 * weight. An auditor's first question is narrower than that — what was
 * decided, why, and under which policy — so that is what opens.
 *
 * Nothing is removed. The raw records, the internal codes, the untranslated
 * blockers and the agent's own communications are all still here, one
 * disclosure deeper, exactly as stored.
 */
import { useState } from "react";
import { ChevronDown, GitMerge, Mail, ShieldCheck, StickyNote } from "lucide-react";

import { OutcomeBadge, Pill } from "./Badges";
import {
  decisionAreaLabel, decisionAreas, decisionDependencies, shortPolicy,
} from "../data/language";
import { shortDate } from "../data/model";
import type { PortfolioCase } from "../data/model";
import type { AgentCase } from "../types/claris";

function Panel({ title, sub, children }: {
  title: string; sub?: string; children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-[14px] font-semibold text-claris-900">{title}</h2>
      {sub && <p className="mt-0.5 text-[12px] leading-relaxed text-slate-500">{sub}</p>}
      <div className="mt-3.5">{children}</div>
    </section>
  );
}

function Disclosure({ label, count, children }: {
  label: string; count?: number; children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <section className="rounded-xl border border-slate-200 bg-white">
      <button type="button" onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left">
        <span className="text-[13.5px] font-semibold text-claris-900">
          {label}
          {count !== undefined && (
            <span className="ml-2 font-normal text-slate-400">{count}</span>
          )}
        </span>
        <ChevronDown className={`h-4 w-4 shrink-0 text-slate-400 transition ${open ? "rotate-180" : ""}`} />
      </button>
      {open && <div className="border-t border-slate-200 px-5 py-4">{children}</div>}
    </section>
  );
}

/* ── dependencies, instead of subordinate rows ───────────────────────────*/
function Dependencies({ agent }: { agent: AgentCase }) {
  const groups = decisionDependencies(agent);
  if (groups.length === 0) return null;
  return (
    <Panel title="Decision dependencies"
           sub="Read from the governed subordinate findings. One decision cannot be reached until the decisions it rests on are.">
      <div className="space-y-3">
        {groups.map((group) => (
          <div key={group.decisionType}
               className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-slate-50/60 p-3.5">
            <div className="flex flex-col gap-1.5">
              {group.dependsOn.map((dep) => (
                <span key={dep.type}
                      className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[12.5px] font-medium text-claris-900">
                  {decisionAreaLabel(dep.type)}
                </span>
              ))}
            </div>
            <GitMerge className="h-4 w-4 rotate-90 text-slate-400" />
            <span className="rounded-lg border border-claris-200 bg-claris-50 px-3 py-1.5 text-[12.5px] font-semibold text-claris-800">
              {decisionAreaLabel(group.decisionType)}
            </span>
            <span className="text-[12px] text-slate-500">
              {decisionAreaLabel(group.decisionType)} depends on{" "}
              {group.dependsOn.map((d) => decisionAreaLabel(d.type).toLowerCase()).join(" and ")}.
            </span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

export default function DecisionRecord({ subject }: { subject: PortfolioCase }) {
  const agent = subject.agent;
  const readiness = agent?.case.readiness ?? [];
  const areas = agent ? decisionAreas(agent) : [];
  const whyFor = new Map(areas.map((a) => [a.decisionType, a.why]));
  const current = subject.decisions.find((d) => d.state === "current");
  const history = subject.decisions;

  return (
    <div className="space-y-4">
      {readiness.length > 0 && (
        <Panel title="Governed decisions"
               sub="One row per governed decision, with the policy that produced it.">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] text-[13px]">
              <thead>
                <tr className="border-b border-slate-200 text-left text-[11.5px] text-slate-500">
                  <th className="pb-2 pr-3 font-medium">Decision</th>
                  <th className="pb-2 pr-3 font-medium">Outcome</th>
                  <th className="pb-2 pr-3 font-medium">Why</th>
                  <th className="pb-2 font-medium">Policy</th>
                </tr>
              </thead>
              <tbody>
                {readiness.map((r) => (
                  <tr key={r.decision_type} className="border-b border-slate-100 last:border-0">
                    <td className="py-2.5 pr-3 align-top font-medium text-claris-900">
                      {decisionAreaLabel(r.decision_type)}
                    </td>
                    <td className="py-2.5 pr-3 align-top">
                      <OutcomeBadge outcome={r.outcome} />
                    </td>
                    <td className="py-2.5 pr-3 align-top text-slate-600">
                      {whyFor.get(r.decision_type) ?? r.why}
                    </td>
                    <td className="py-2.5 align-top text-slate-500">
                      {shortPolicy(r.policy_version)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      {agent && <Dependencies agent={agent} />}

      {history.length > 0 && (
        <Panel title="Identity assessment"
               sub="The decision in force, and every decision it replaced. Nothing here is translated.">
          {current && (
            <div className="rounded-xl border border-claris-200 bg-claris-50 p-4">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-claris-700 px-2 py-0.5 text-[10.5px] font-bold uppercase tracking-[0.08em] text-white">
                  Current
                </span>
                <b className="font-mono text-[14px] text-claris-900">
                  {current.outcome_code}
                </b>
                <Pill tone={current.governance_basis === "AUTHORITATIVE" ? "ready" : "attention"}>
                  {current.governance_basis}
                </Pill>
              </div>
              <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
                {[
                  ["Decision", current.decision_type],
                  ["Reason", current.reason_code ?? "—"],
                  ["Matched rule", current.matched_rule_id ?? "—"],
                  ["State", current.state],
                  ["Version", `${current.kb_version} / ${current.policy_version ?? "—"}`],
                  ["Decided", shortDate(current.decided_at)],
                ].map(([label, value]) => (
                  <div key={label}>
                    <dt className="text-[10.5px] font-medium uppercase tracking-[0.06em] text-slate-400">
                      {label}
                    </dt>
                    <dd className="mt-0.5 font-mono text-[12px] text-claris-900">{value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}

          {history.filter((d) => d.decision_id !== current?.decision_id).length > 0 && (
            <div className="mt-4">
              <div className="mb-2 text-[11px] font-bold uppercase tracking-[0.1em] text-slate-400">
                Previous decisions
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[820px] text-[12px]">
                  <thead>
                    <tr className="border-b border-slate-200 text-left text-slate-500">
                      <th className="py-2 pr-3 font-medium">Decided</th>
                      <th className="py-2 pr-3 font-medium">Outcome</th>
                      <th className="py-2 pr-3 font-medium">Reason</th>
                      <th className="py-2 pr-3 font-medium">Rule</th>
                      <th className="py-2 pr-3 font-medium">State</th>
                      <th className="py-2 font-medium">Basis</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history
                      .filter((d) => d.decision_id !== current?.decision_id)
                      .sort((a, b) => a.decided_at.localeCompare(b.decided_at))
                      .map((d) => (
                        <tr key={d.decision_id} className="border-b border-slate-100 last:border-0">
                          <td className="py-2 pr-3 align-top text-slate-500">
                            {shortDate(d.decided_at)}
                          </td>
                          <td className="py-2 pr-3 align-top font-mono text-slate-700">
                            {d.outcome_code}
                          </td>
                          <td className="py-2 pr-3 align-top font-mono text-slate-600">
                            {d.reason_code ?? "—"}
                          </td>
                          <td className="py-2 pr-3 align-top font-mono text-[11px] text-slate-500">
                            {d.matched_rule_id ?? "—"}
                          </td>
                          <td className="py-2 pr-3 align-top text-slate-600">{d.state}</td>
                          <td className="py-2 align-top">
                            <Pill tone={d.governance_basis === "AUTHORITATIVE" ? "ready" : "attention"}>
                              {d.governance_basis}
                            </Pill>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-3 text-[12px] leading-relaxed text-slate-500">
                The earliest decision is what the request caused when it
                arrived. Later decisions are replays against a model that has
                since changed — which is why a request that created a
                configuration now reads as reusing one. No stored record was
                altered.
              </p>
            </div>
          )}
        </Panel>
      )}

      {/* ── everything below is the raw surface, untranslated ───────────── */}
      <Disclosure label="Technical details — policy and blockers">
        {readiness.length > 0 && (
          <div>
            <div className="mb-2 text-[11px] font-bold uppercase tracking-[0.1em] text-slate-400">
              Readiness policy detail
            </div>
            <div className="space-y-2">
              {readiness.map((r) => (
                <div key={r.decision_type} className="rounded-lg border border-slate-200 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <b className="font-mono text-[12px] text-claris-900">{r.decision_type}</b>
                    <span className="font-mono text-[11.5px] text-slate-600">{r.outcome}</span>
                    <span className="text-[11px] text-slate-400">{r.policy_version}</span>
                  </div>
                  <p className="mt-1 font-mono text-[11px] leading-relaxed text-slate-600">
                    {r.why}
                  </p>
                  {r.missing_evidence.length > 0 && (
                    <p className="mt-1 font-mono text-[11px] text-slate-500">
                      missing: {r.missing_evidence.join(", ")}
                    </p>
                  )}
                  {r.insufficient_evidence.length > 0 && (
                    <p className="mt-1 font-mono text-[11px] text-slate-500">
                      insufficient: {r.insufficient_evidence.join(", ")}
                    </p>
                  )}
                  {r.failed.length > 0 && (
                    <p className="mt-1 font-mono text-[11px] text-blocked-fg">
                      failed: {r.failed.join(", ")}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {agent && agent.blockers.length > 0 && (
          <div className="mt-4 border-t border-slate-200 pt-4">
            <div className="mb-2 text-[11px] font-bold uppercase tracking-[0.1em] text-slate-400">
              Blockers, as recorded
            </div>
            <div className="space-y-2">
              {agent.blockers.map((b, i) => (
                <div key={`${b.decision_type}-${b.property_name}-${i}`}
                     className="flex flex-wrap items-start gap-2 rounded-lg border border-slate-200 p-2.5">
                  <Pill tone={b.kind === "OBSERVED_FAILURE" ||
                              b.kind === "CONTRADICTED_EVIDENCE" ? "blocked" : "attention"}>
                    <span className="font-mono">{b.kind}</span>
                  </Pill>
                  <span className="min-w-0 flex-1 text-[12px] leading-relaxed text-slate-700">
                    {b.statement}
                  </span>
                  {b.provenance && <Pill tone="quiet">{b.provenance}</Pill>}
                </div>
              ))}
            </div>
          </div>
        )}

        <p className="mt-4 flex items-start gap-1.5 border-t border-slate-200 pt-4 text-[12px] leading-relaxed text-slate-500">
          <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-claris-500" />
          Decisions marked PROTOTYPE_ASSUMPTION rest on policy this project
          wrote, not on policy Claris confirmed. The distinction is stored, not
          styled away.
        </p>
      </Disclosure>

      {agent && agent.communications.length > 0 && (
        <Disclosure label="Communication history" count={agent.communications.length}>
          <div className="space-y-3">
            {agent.communications.map((c) => (
              <div key={c.communication_id} className="rounded-lg border border-slate-200 p-3.5">
                <div className="mb-1.5 flex flex-wrap items-center gap-2 text-[12px]">
                  {c.channel === "WORKBENCH_NOTE"
                    ? <StickyNote className="h-3.5 w-3.5 text-slate-400" />
                    : <Mail className="h-3.5 w-3.5 text-slate-400" />}
                  <b className="font-mono text-claris-900">{c.channel}</b>
                  <Pill tone="quiet">{c.status}</Pill>
                  {c.to_role
                    ? <span className="text-slate-600">to role <b>{c.to_role}</b></span>
                    : <span className="text-slate-400">no recipient</span>}
                </div>
                <div className="text-[13px] font-semibold text-claris-900">{c.subject}</div>
                <pre className="mt-2 whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-slate-600">
                  {c.body}
                </pre>
              </div>
            ))}
          </div>
          <p className="mt-3 text-[11.5px] text-slate-500">
            Drafted by the Launch Coordination Agent against governed state.
            None was sent.
          </p>
        </Disclosure>
      )}
    </div>
  );
}
