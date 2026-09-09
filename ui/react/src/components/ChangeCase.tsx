/**
 * SKU / Change workbench — actionable decision space for cross-persona teams.
 *
 * FIVE IMMEDIATE ANSWERS
 *   1. Can this launch/change proceed?
 *   2. If not, why not?
 *   3. What exactly is missing?
 *   4. Which persona/role needs to provide it?
 *   5. What can the Product Manager do about it?
 *
 * This is not a status dashboard. It is a workbench: every section enables
 * a decision or action. The ontology remains one tab away in Decision Record;
 * every property's provenance one tab away in Evidence. A Product Manager
 * should never need either; an auditor should never be denied either.
 */
import {
  AlertCircle, ArrowRight, Database, Sparkles, Users,
} from "lucide-react";

import JourneyRail from "./JourneyRail";
import { Pill } from "./Badges";
import {
  decisionAreas, decisionDependencies, missingEvidenceLabels, nextAction,
  openItems, primaryBlocker, decisionAreaLabel,
} from "../data/language";
import type { Lane, PortfolioCase, Tone } from "../data/model";
import type { AgentCase } from "../types/claris";
import { shortDate } from "../data/model";

const AREA_TONE: Record<Tone, string> = {
  ready: "bg-ready-bg text-ready-fg border-ready-br",
  attention: "bg-attention-bg text-attention-fg border-attention-br",
  blocked: "bg-blocked-bg text-blocked-fg border-blocked-br",
  quiet: "bg-quiet-bg text-quiet-fg border-quiet-br",
};

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

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="text-[11px] font-medium uppercase tracking-[0.06em] text-slate-400">
        {label}
      </div>
      <div className="mt-1 text-[13px] leading-snug text-claris-900">{children}</div>
    </div>
  );
}

/**
 * Action & Dependencies table — the most important new workbench section.
 *
 * Shows what is blocking the case, who needs to provide it, and whether a
 * communication action exists (subordinate dependencies like Launch Readiness
 * cannot be requested directly — they re-evaluate when their prerequisites
 * are satisfied).
 */
function ActionDependencies({ agent, areas }: { agent: any; areas: any[] }) {
  if (!agent || areas.length === 0) return null;

  // Show all readiness areas, not just direct dependencies
  const deps = areas;

  // Map decision types to their required evidence and responsible teams
  const depDetails: Record<string, { needed: string[]; team: string }> = {
    TECHNICAL_READINESS: {
      needed: ["Technical approval"],
      team: "IS&T",
    },
    PRICING_READINESS: {
      needed: ["Pricing status", "Pricing amount"],
      team: "Finance",
    },
    LAUNCH_READINESS: {
      needed: ["Technical + Pricing must resolve"],
      team: "System dependency",
    },
  };

  // Helper to create descriptive status text
  const getDescriptiveStatus = (decisionType: string, baseStatus: string) => {
    if (decisionType === "LAUNCH_READINESS") {
      return "Blocked by unresolved Technical + Pricing";
    }
    if (decisionType === "TECHNICAL_READINESS") {
      return "Waiting for IS&T";
    }
    if (decisionType === "PRICING_READINESS") {
      return "Waiting for Finance";
    }
    return baseStatus;
  };

  return (
    <Panel title="Action & dependencies"
           sub="What is needed, from whom, and how to move this forward.">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[650px] text-[13px]">
          <thead>
            <tr className="border-b border-slate-200 text-left text-[12.5px] text-claris-700">
              <th className="pb-2 pr-4 font-semibold">Dependency</th>
              <th className="pb-2 pr-4 font-semibold">What is needed</th>
              <th className="pb-2 pr-4 font-semibold">From</th>
              <th className="pb-2 pr-4 font-semibold">State</th>
              <th className="pb-2 font-semibold">Action</th>
            </tr>
          </thead>
          <tbody>
            {deps.map((dep) => {
              const isSubordinate = dep.decisionType === "LAUNCH_READINESS";
              const details = depDetails[dep.decisionType] || {
                needed: ["Unknown"],
                team: "Unknown",
              };
              const descriptiveStatus = getDescriptiveStatus(dep.decisionType, dep.status);
              const statusTone = dep.tone;

              return (
                <tr key={dep.decisionType} className="border-b border-slate-100 last:border-0">
                  <td className="py-3 pr-4 align-top font-semibold text-claris-900">
                    {decisionAreaLabel(dep.decisionType)}
                  </td>
                  <td className="py-3 pr-4 align-top text-slate-700">
                    <ul className="space-y-0.5">
                      {details.needed.map((item) => (
                        <li key={item} className="flex items-start gap-2">
                          <span className="mt-1.5 inline-block h-1 w-1 rounded-full bg-claris-700 flex-shrink-0" />
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </td>
                  <td className="py-3 pr-4 align-top text-slate-700">
                    {details.team}
                  </td>
                  <td className="py-3 pr-4 align-top">
                    <Pill tone={statusTone}>
                      {descriptiveStatus}
                    </Pill>
                  </td>
                  <td className="py-3 align-top">
                    {isSubordinate
                      ? <span className="inline-flex rounded-full border border-slate-300 bg-white px-3 py-1 text-[12px] font-medium text-slate-500">
                          No action yet
                        </span>
                      : <button type="button"
                          className="inline-flex rounded-full border border-claris-300 bg-claris-50 px-3 py-1 text-[12px] font-semibold text-claris-700 hover:bg-claris-100">
                          Request from {details.team}
                        </button>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

/**
 * Readiness dependency diagram — shows which decisions must be satisfied
 * before others can proceed. NOT a process flow, NOT a workflow.
 */
function ReadinessDependencyDiagram({ agent }: { agent: any }) {
  if (!agent) return null;

  const areas = decisionAreas(agent);
  const technical = areas.find((a) => a.decisionType === "TECHNICAL_READINESS");
  const pricing = areas.find((a) => a.decisionType === "PRICING_READINESS");
  const launch = areas.find((a) => a.decisionType === "LAUNCH_READINESS");

  if (!technical || !pricing || !launch) return null;

  return (
    <Panel title="Readiness dependency diagram"
           sub="Launch readiness depends on Technical and Pricing readiness. Both must be satisfied.">
      <div className="space-y-4">
        {/* Horizontal dependency diagram - three boxes in a row */}
        <div className="flex items-center justify-center gap-4">
          {/* Technical Readiness */}
          <div className="flex-1 rounded-lg border border-slate-200 bg-slate-50 p-4 text-center">
            <div className="text-[13px] font-bold text-claris-900">
              Technical Readiness
            </div>
            <div className="mt-2 text-[12px] font-semibold text-attention-fg">
              {technical.status}
            </div>
            <div className="mt-1.5 text-[11px] text-slate-500">
              Waiting on IS&T
            </div>
          </div>

          {/* Arrow */}
          <div className="flex items-center justify-center shrink-0">
            <ArrowRight className="h-4 w-4 text-slate-400" />
          </div>

          {/* Launch Readiness */}
          <div className="flex-1 rounded-lg border border-slate-200 bg-slate-50 p-4 text-center">
            <div className="text-[13px] font-bold text-claris-900">
              Launch Readiness
            </div>
            <div className="mt-2 text-[12px] font-semibold text-attention-fg">
              {launch.status}
            </div>
            <div className="mt-1.5 text-[11px] text-slate-500">
              Dependent
            </div>
          </div>

          {/* Arrow */}
          <div className="flex items-center justify-center shrink-0">
            <ArrowRight className="h-4 w-4 text-slate-400" />
          </div>

          {/* Pricing Readiness */}
          <div className="flex-1 rounded-lg border border-slate-200 bg-slate-50 p-4 text-center">
            <div className="text-[13px] font-bold text-claris-900">
              Pricing Readiness
            </div>
            <div className="mt-2 text-[12px] font-semibold text-attention-fg">
              {pricing.status}
            </div>
            <div className="mt-1.5 text-[11px] text-slate-500">
              Waiting on Finance
            </div>
          </div>
        </div>

        <p className="text-[11px] leading-relaxed text-slate-500">
          This is a decision dependency diagram, not a process flow. Only readiness
          decisions that appear in governed state are shown. Marketing, Product
          Operations, and Activation are not readiness dependencies.
        </p>
      </div>
    </Panel>
  );
}

/**
 * What happens next — a simple explanatory card showing the sequence of
 * events after missing information arrives.
 */
function WhatHappensNext() {
  return (
    <Panel title="What happens next?">
      <div className="space-y-2">
        <div className="flex gap-3">
          <div className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-claris-100 text-[12px] font-semibold text-claris-700">
            1
          </div>
          <div className="text-[13px] leading-snug text-claris-900">
            Finance provides pricing status and amount
          </div>
        </div>
        <div className="flex gap-3">
          <div className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-claris-100 text-[12px] font-semibold text-claris-700">
            2
          </div>
          <div className="text-[13px] leading-snug text-claris-900">
            IS&T provides technical approval
          </div>
        </div>
        <div className="flex gap-3">
          <div className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-claris-100 text-[12px] font-semibold text-claris-700">
            3
          </div>
          <div className="text-[13px] leading-snug text-claris-900">
            Governed readiness is re-evaluated
          </div>
        </div>
        <div className="flex gap-3">
          <div className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-claris-100 text-[12px] font-semibold text-claris-700">
            4
          </div>
          <div className="text-[13px] leading-snug text-claris-900">
            Launch readiness can proceed when all required decisions are satisfied
          </div>
        </div>
      </div>
    </Panel>
  );
}

export default function ChangeCase({ subject, lanes, horizon, onTab, onDraft }: {
  subject: PortfolioCase;
  lanes: Lane[];
  horizon: string;
  onTab: (tab: "Evidence" | "Decision record") => void;
  onDraft: (kind: "message" | "note") => void;
}) {
  const agent = subject.agent;
  const areas = agent ? decisionAreas(agent) : [];
  const blocker = primaryBlocker(agent);
  const action = nextAction(agent);
  const missing = missingEvidenceLabels(agent);
  const items = openItems(lanes, subject);

  return (
    <div className="space-y-4 px-5 py-6 lg:px-8">
      {/* ── SECTION 1 & 2: Readiness summary + Decision & handoff journey ── */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Readiness summary"
               sub="One row per governed readiness decision, in business words.">
          {areas.length === 0 ? (
            <p className="text-[13px] leading-relaxed text-slate-500">
              {subject.kind === "Launch"
                ? "No readiness decision is defined for launches. Governed " +
                  "facts are recorded; no verdict is claimed."
                : "No readiness decision has been reached for this case."}
            </p>
          ) : (
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-slate-200 text-left text-[11.5px] text-slate-500">
                  <th className="pb-2 pr-3 font-medium">Decision area</th>
                  <th className="pb-2 pr-3 font-medium">Status</th>
                  <th className="pb-2 font-medium">Why</th>
                </tr>
              </thead>
              <tbody>
                {areas.map((row) => (
                  <tr key={row.decisionType} className="border-b border-slate-100 last:border-0">
                    <td className="py-2.5 pr-3 align-top font-medium text-claris-900">
                      {row.area}
                    </td>
                    <td className="py-2.5 pr-3 align-top">
                      <span className={`inline-flex items-center whitespace-nowrap rounded-full border px-2.5 py-0.5 text-[11.5px] font-semibold ${AREA_TONE[row.tone]}`}>
                        {row.status}
                      </span>
                    </td>
                    <td className="py-2.5 align-top text-slate-600">{row.why}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>

        <Panel title="Decision & handoff journey">
          <JourneyRail lanes={lanes} subject={subject} />
        </Panel>
      </div>

      {/* ── SECTION 3: Action & Dependencies (NEW — MOST IMPORTANT) ────────── */}
      <ActionDependencies agent={agent} areas={areas} />

      {/* ── SECTION 4 & 5: Why cannot proceed + Agent recommendation ──────── */}
      <div className="grid gap-4 lg:grid-cols-2">
        {blocker && (
          <Panel title="Why this case cannot proceed">
            <p className="text-[13.5px] leading-relaxed text-claris-900">
              {blocker.long}
            </p>
            {missing.length > 0 && (
              <div className="mt-3.5 rounded-lg border border-claris-200 bg-claris-50 p-3.5">
                <div className="mb-2 flex items-center gap-2 text-[12.5px] font-semibold text-claris-800">
                  <AlertCircle className="h-3.5 w-3.5" /> Missing required evidence
                </div>
                <ul className="space-y-1">
                  {missing.map((label) => (
                    <li key={label} className="text-[12.5px] text-slate-700">• {label}</li>
                  ))}
                </ul>
                <button type="button" onClick={() => onTab("Evidence")}
                  className="mt-3 inline-flex items-center gap-1 text-[12.5px] font-medium text-claris-600 hover:text-claris-800">
                  View evidence <ArrowRight className="h-3.5 w-3.5" />
                </button>
              </div>
            )}
          </Panel>
        )}

        {agent && (
          <Panel title="Agent recommendation">
            <div className="rounded-xl border border-claris-200 bg-claris-50 p-4">
              <div className="mb-1.5 flex items-center gap-2 text-[12px] font-semibold text-claris-600">
                <Sparkles className="h-3.5 w-3.5" /> Agent recommendation
              </div>
              <p className="text-[15px] font-semibold leading-snug text-claris-900">
                {action?.statement ?? "No action is required."}
              </p>
              <p className="mt-1.5 text-[12px] leading-relaxed text-slate-500">
                The Agent recommends this next action based on governed decision
                state. It does not make the business decision.
              </p>
              <div className="mt-3.5 flex flex-wrap items-center gap-2">
                <button type="button" onClick={() => onDraft("message")}
                  className="rounded-lg bg-claris-700 px-3.5 py-2 text-[12.5px] font-semibold text-white transition hover:bg-claris-600">
                  Draft message
                </button>
                <button type="button" onClick={() => onDraft("note")}
                  className="rounded-lg border border-claris-200 bg-white px-3 py-2 text-[12.5px] font-medium text-claris-700 transition hover:border-claris-400">
                  Add note
                </button>
                <button type="button" onClick={() => onTab("Decision record")}
                  className="text-[12.5px] text-claris-600 underline-offset-2 hover:underline">
                  View reasoning
                </button>
              </div>
            </div>
          </Panel>
        )}
      </div>

      {/* ── SECTION 6 & 7: Dependency diagram + What happens next ────────── */}
      <div className="grid gap-4 lg:grid-cols-2">
        <ReadinessDependencyDiagram agent={agent} />
        <WhatHappensNext />
      </div>

      {/* ── SECTION 8 & 9: Key facts + Open items ─────────────────────────── */}
      <div className="grid gap-4 lg:grid-cols-[.8fr_1.2fr]">
        <Panel title="Key facts">
          <div className="grid gap-4 sm:grid-cols-2">
            <Fact label="Case type">{subject.kind}</Fact>
            <Fact label="Product">
              {subject.product ?? <span className="text-slate-400">Not recorded</span>}
            </Fact>
            <Fact label="First seen">{shortDate(subject.firstActivity)}</Fact>
            <Fact label="Last activity">{shortDate(subject.lastActivity)}</Fact>
            <Fact label="Days open">
              {subject.firstActivity
                ? Math.floor((new Date(horizon).getTime() - new Date(subject.firstActivity).getTime())
                    / (1000 * 60 * 60 * 24))
                : "—"}
            </Fact>
          </div>
          {subject.launchLinkUnavailable && (
            <p className="mt-4 rounded-lg border border-quiet-br bg-quiet-bg px-3 py-2 text-[12px] text-quiet-fg">
              Launch relationship not established in governed state.
            </p>
          )}
          <p className="mt-3 text-[11px] text-slate-400">
            Decision horizon {shortDate(horizon)} — every state on this page is
            as known at that instant.
          </p>
        </Panel>

        {items.length > 0 && (
          <Panel title="Open items by team"
                 sub="The recommended next action targets one team; these are the requirements that remain open.">
            <div className="mb-3">
              <Pill tone="attention">
                {items.filter((i) => i.status === "Action required").length} team
                {items.filter((i) => i.status === "Action required").length === 1 ? "" : "s"} need to act
              </Pill>
            </div>
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-slate-200 text-left text-[11.5px] text-slate-500">
                  <th className="pb-2 pr-3 font-medium">Team</th>
                  <th className="pb-2 pr-3 font-medium">Status</th>
                  <th className="pb-2 font-medium">What's needed</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.team} className="border-b border-slate-100 last:border-0">
                    <td className="py-2.5 pr-3 align-top">
                      <span className="font-medium text-claris-900">{item.team}</span>
                      {item.isNextAction && (
                        <span className="ml-2 rounded bg-claris-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.05em] text-claris-700">
                          next
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 pr-3 align-top">
                      <Pill tone={item.status === "Action required" ? "attention" : "quiet"}>
                        {item.status}
                      </Pill>
                    </td>
                    <td className="py-2.5 align-top text-slate-600">{item.needed}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 flex items-start gap-1.5 text-[11.5px] leading-relaxed text-slate-400">
              <Users className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              Teams are grouped by the governed property each owns. Only the row
              marked NEXT is a role the platform routes to — ownership beyond
              that is not established in governed state.
            </p>
          </Panel>
        )}
      </div>

      {/* ── Footer note ────────────────────────────────────────────────────── */}
      <div className="flex items-start gap-2.5 rounded-xl border border-slate-200 bg-slate-50/70 p-4">
        <Database className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
        <p className="text-[12px] leading-relaxed text-slate-600">
          <b className="font-semibold">Note.</b> Physical SKU/material
          proliferation in legacy systems may still occur where a target system
          requires it. Phase 1 prevents unnecessary proliferation in the
          <i> canonical </i> business model by distinguishing legacy identifiers
          from business configurations — it does not replace those systems or
          stop them creating rows of their own.
        </p>
      </div>
    </div>
  );
}
