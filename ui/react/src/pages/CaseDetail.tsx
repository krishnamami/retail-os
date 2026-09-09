/**
 * Case detail — a router between two decision domains.
 *
 * A SKU change is a readiness case: where does it stand, who acts next, why.
 * A configuration request is an identity case: does this already exist. They
 * need different screens, and forcing one into the other's shape is what made
 * a completed identity assessment look like a stalled launch.
 *
 * Evidence and Decision record are shared, because provenance and audit do
 * not change shape between domains.
 */
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  AlertCircle, ArrowLeft, ArrowRight, CheckCircle2, ChevronDown, CircleDashed,
  Database, FileText, Flag, Info, Sparkles,
} from "lucide-react";

import DataGate from "../components/DataGate";
import ChangeCase from "../components/ChangeCase";
import ConfigurationCase from "../components/ConfigurationCase";
import LaunchCase from "../components/LaunchCase";
import DecisionRecord from "../components/DecisionRecord";
import DraftDrawer from "../components/DraftDrawer";
import EvidenceTable from "../components/EvidenceTable";
import { Pill } from "../components/Badges";
import { ageInDays, buildLanes, buildPortfolio, shortDate } from "../data/model";
import type { PortfolioCase } from "../data/model";
import {
  REASON_LABEL, currentDecision, draftMessage, firstDecision, fullIdentity,
  identityDecision, identityFacts, missingDimensions, needsActionFrom,
  nextAction, primaryBlocker, propertyLabel, unresolvedCount,
} from "../data/language";
import type { WorkbenchData } from "../types/claris";

const TABS = ["Overview", "Evidence", "Decision record"] as const;
type Tab = (typeof TABS)[number];

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

function Tile({ icon: Icon, label, children }: {
  icon: typeof Info; label: string; children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3.5">
      <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.06em] text-slate-400">
        <Icon className="h-3.5 w-3.5" /> {label}
      </div>
      <div className="text-[13px] leading-snug text-claris-900">{children}</div>
    </div>
  );
}

function Detail({ subject, data }: { subject: PortfolioCase; data: WorkbenchData }) {
  const [tab, setTab] = useState<Tab>("Overview");
  const [draftKind, setDraftKind] = useState<"message" | "note" | null>(null);
  const [showOthers, setShowOthers] = useState(false);

  const lanes = useMemo(() => buildLanes(subject), [subject]);
  const agent = subject.agent;
  const owner = needsActionFrom(agent);
  const blocker = primaryBlocker(agent);
  const action = nextAction(agent);
  const age = ageInDays(subject.firstActivity, data.horizon);
  const draft = draftMessage(subject, agent);

  /* Two domains, two summary strips. */
  const isConfiguration = subject.kind === "Configuration request";
  const currentIdentity = currentDecision(subject.decisions);
  const originalIdentity = firstDecision(subject.decisions);
  const identityMissing = missingDimensions(identityFacts(subject.properties));
  const identityView = identityDecision(currentIdentity, identityMissing);
  const identity = fullIdentity(subject.properties);

  /* The hero names ONE next handoff. Saying so without saying how much else
     is open would read as "Finance is all that is left", which is false. */
  const unresolved = unresolvedCount(agent);
  const otherAreas = (agent?.case.readiness ?? []).filter((r) => r.outcome !== "READY");

  return (
    <>
      <div className="border-b border-slate-200 bg-white px-5 pt-4 lg:px-8">
        <div className="flex items-center justify-between gap-3">
          <Link to="/launches"
                className="inline-flex items-center gap-1 text-[12.5px] text-slate-500 hover:text-claris-700">
            <ArrowLeft className="h-3.5 w-3.5" /> Back to Command Center
          </Link>
          <span className="text-[11.5px] text-slate-400">
            {subject.firstActivity && (
              <>Created {shortDate(subject.firstActivity)}
                <span className="mx-1.5 text-slate-300">•</span></>
            )}
            Decision horizon {shortDate(data.horizon)}
          </span>
        </div>

        <div className="mt-2 flex flex-wrap items-center gap-2.5">
          <h1 className="text-[24px] font-semibold tracking-[-0.02em] text-claris-900">
            {subject.id}
          </h1>
          <Pill tone="quiet">{subject.kind}</Pill>
          {subject.product && <Pill tone="quiet">{subject.product}</Pill>}
        </div>

        {isConfiguration ? (
          /* ── identity hero ──────────────────────────────────────────── */
          <div className="mt-4 space-y-3">
            <div className={`rounded-xl border p-5 ${
              identityView?.tone === "attention"
                ? "border-attention-br bg-attention-bg"
                : "border-ready-br bg-ready-bg"}`}>
              <div className="grid gap-5 lg:grid-cols-[1.55fr_.95fr]">
                <div className="flex gap-3.5">
                  <span className={`mt-0.5 inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${
                    identityView?.tone === "attention"
                      ? "bg-attention-br/50 text-attention-fg"
                      : "bg-ready-br/50 text-ready-fg"}`}>
                    {identityView?.tone === "attention"
                      ? <CircleDashed className="h-5 w-5" />
                      : <CheckCircle2 className="h-5 w-5" />}
                  </span>
                  <div className="min-w-0">
                    <h2 className={`text-[24px] font-semibold tracking-[-0.02em] ${
                      identityView?.tone === "attention"
                        ? "text-attention-fg" : "text-ready-fg"}`}>
                      {identityView?.headline ?? "No decision recorded"}
                    </h2>
                    <p className="mt-1.5 max-w-[64ch] text-[13.5px] leading-relaxed text-slate-700">
                      {identityView?.explanation}
                    </p>
                  </div>
                </div>

                <div className="flex gap-3.5 lg:border-l lg:border-current/15 lg:pl-5">
                  <span className="mt-0.5 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white/70 text-claris-600">
                    <Sparkles className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <div className="text-[11px] font-bold uppercase tracking-[0.12em] text-slate-500">
                      Next action
                    </div>
                    <div className="mt-1 text-[14px] font-semibold text-claris-900">
                      {identityView?.result ?? "—"}
                    </div>
                    {identityMissing.length === 0 && (
                      <p className="mt-1.5 text-[11.5px] leading-relaxed text-slate-600">
                        If a target system requires another SKU or material
                        identifier, a legacy projection may be created where
                        required — it does not become another business
                        configuration.
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Tile icon={FileText} label="Requested identity">
                {identity
                  ? <b className="font-semibold">{identity}</b>
                  : <span className="text-attention-fg">Identity incomplete</span>}
              </Tile>
              <Tile icon={Database} label="Existing configuration">
                <span className="font-normal text-slate-500">
                  Relationship not established
                </span>
                {currentIdentity?.outcome_code === "NO_BUSINESS_CHANGE" && (
                  <div className="mt-1 text-[11px] leading-snug text-slate-400">
                    The matching configuration exists, but the relationship is
                    not yet established in governed state.
                  </div>
                )}
              </Tile>
              <Tile icon={Info} label="Decision reason">
                {currentIdentity?.reason_code
                  ? REASON_LABEL[currentIdentity.reason_code] ?? currentIdentity.reason_code
                  : "—"}
                {currentIdentity?.reason_code === "EXACT_IDENTITY_MATCH" && (
                  <div className="mt-1 text-[11px] leading-snug text-slate-400">
                    on all four identity dimensions
                  </div>
                )}
              </Tile>
              <Tile icon={Flag} label="Primary blocker">
                {identityMissing.length === 0
                  ? <span className="font-normal text-slate-500">None</span>
                  : `${propertyLabel(identityMissing[0].property)} not reported`}
              </Tile>
            </div>
          </div>
        ) : (
          /* ── readiness hero ─────────────────────────────────────────── */
          <div className={`mt-4 rounded-xl border p-5 ${
            subject.tone === "blocked" ? "border-blocked-br bg-blocked-bg"
            : subject.tone === "attention" ? "border-attention-br bg-attention-bg"
            : subject.tone === "ready" ? "border-ready-br bg-ready-bg"
            : "border-slate-200 bg-slate-50/60"}`}>
            <div className="flex flex-wrap items-start gap-5">
              <div className="flex min-w-[300px] flex-1 gap-3.5">
                <span className={`mt-0.5 inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${
                  subject.tone === "blocked" ? "bg-blocked-br/50 text-blocked-fg"
                  : subject.tone === "attention" ? "bg-attention-br/50 text-attention-fg"
                  : "bg-white/70 text-slate-500"}`}>
                  {subject.tone === "ready"
                    ? <CheckCircle2 className="h-5 w-5" />
                    : <AlertCircle className="h-5 w-5" />}
                </span>
                <div className="min-w-0">
                  <h2 className={`text-[24px] font-semibold tracking-[-0.02em] ${
                    subject.tone === "blocked" ? "text-blocked-fg"
                    : subject.tone === "attention" ? "text-attention-fg"
                    : "text-claris-900"}`}>
                    {subject.outcomeLabel}
                  </h2>
                  <p className="mt-1.5 max-w-[46ch] text-[13.5px] leading-relaxed text-slate-700">
                    {subject.outcome === "NO_GOVERNED_DECISION"
                      ? "No readiness decision is defined for this subject type. " +
                        "Governed facts are recorded; no verdict is claimed."
                      : subject.outcome === "NOT_READY"
                        ? "Launch readiness is not satisfied: a required input " +
                          "was reported as failed by its source."
                        : "Launch readiness cannot yet be determined because " +
                          "required evidence is missing."}
                  </p>
                </div>
              </div>

              <div className="grid flex-1 gap-4 sm:grid-cols-3 lg:border-l lg:border-current/15 lg:pl-5">
                <Fact label="Next action from">
                  {owner
                    ? <b className="font-semibold">{owner.team ?? owner.role}</b>
                    : <span className="text-slate-400">—</span>}
                </Fact>
                <Fact label="Primary blocker">
                  {blocker ? blocker.short : <span className="text-slate-400">None</span>}
                </Fact>
                <Fact label="Age">
                  {age === null ? "—" : `${age} days`}
                  <div className="text-[11.5px] text-slate-400">
                    first seen {shortDate(subject.firstActivity)}
                  </div>
                </Fact>
              </div>

              {action && action.code !== "NO_ACTION_REQUIRED" && (
                <button type="button" onClick={() => setDraftKind("message")}
                  className="inline-flex shrink-0 items-center gap-1.5 self-center rounded-lg bg-claris-700 px-4 py-2.5 text-[13px] font-semibold text-white transition hover:bg-claris-600">
                  {action.label} <ArrowRight className="h-3.5 w-3.5" />
                </button>
              )}
            </div>

            {unresolved > 1 && (
              <div className="mt-3.5 border-t border-current/15 pt-3">
                <button type="button" onClick={() => setShowOthers((v) => !v)}
                  className="inline-flex items-center gap-1 text-[12.5px] font-medium text-claris-700 underline-offset-2 hover:underline">
                  {unresolved - 1} other readiness requirement
                  {unresolved - 1 === 1 ? "" : "s"} unresolved
                  <ChevronDown className={`h-3.5 w-3.5 transition ${showOthers ? "rotate-180" : ""}`} />
                </button>
                {showOthers && (
                  <ul className="mt-2 space-y-1">
                    {otherAreas.map((r) => (
                      <li key={r.decision_type} className="text-[12.5px] text-slate-600">
                        • {r.why}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        )}

        <div className="mt-4 flex gap-1">
          {TABS.map((name) => (
            <button key={name} type="button" onClick={() => setTab(name)}
              className={`-mb-px border-b-2 px-3 py-2.5 text-[13px] font-medium transition ${
                tab === name
                  ? "border-claris-700 text-claris-900"
                  : "border-transparent text-slate-500 hover:text-slate-700"}`}>
              {name}
            </button>
          ))}
        </div>
      </div>

      {tab === "Overview" && (
        subject.kind === "Configuration request"
          ? <ConfigurationCase subject={subject} data={data}
                               current={currentIdentity} original={originalIdentity}
                               onTab={setTab} />
          : subject.kind === "Launch"
            ? <LaunchCase subject={subject} data={data} onTab={setTab} />
            : <ChangeCase subject={subject} lanes={lanes} horizon={data.horizon}
                          onTab={setTab} onDraft={setDraftKind} />)}

      {tab === "Evidence" && (
        <div className="px-5 py-6 lg:px-8">
          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-[14px] font-semibold text-claris-900">
              Evidence for {subject.id}
            </h2>
            <p className="mt-0.5 text-[12px] text-slate-500">
              All governed evidence used to determine the current state.
            </p>
            <div className="mt-3.5">
              <EvidenceTable properties={subject.properties} />
            </div>
          </section>
        </div>
      )}

      {tab === "Decision record" && (
        <div className="px-5 py-6 lg:px-8">
          <DecisionRecord subject={subject} />
        </div>
      )}

      {draftKind && draft && (
        <DraftDrawer kind={draftKind} onClose={() => setDraftKind(null)}
          draft={draftKind === "note"
            ? { ...draft, body:
                `${subject.outcomeLabel} at horizon ${shortDate(data.horizon)}.\n\n` +
                `${blocker?.long ?? ""}\n\n` +
                `Recommended: ${action?.statement ?? "no action required"}\n\n` +
                `This note records governed decisions. The Agent did not make ` +
                `them and has changed no business fact.` }
            : draft} />
      )}
    </>
  );
}

export default function CaseDetail() {
  const { caseId = "" } = useParams();
  return (
    <DataGate>
      {(data) => {
        const subject = buildPortfolio(data)
          .find((c) => c.id === decodeURIComponent(caseId));
        if (!subject) {
          return (
            <div className="px-5 py-14 lg:px-8">
              <h1 className="text-[19px] font-semibold text-claris-900">
                No governed case named {decodeURIComponent(caseId)}
              </h1>
              <p className="mt-2 text-[13px] text-slate-500">
                This board only shows cases that exist in governed state.
              </p>
              <Link to="/launches" className="mt-4 inline-block text-[13px] text-claris-600 hover:underline">
                Back to the Command Center
              </Link>
            </div>
          );
        }
        /* keyed by case id: a hash-route change does not remount, so without
           this, opening a related request from Decision record would land on
           Decision record instead of that case's Overview. */
        return <Detail key={subject.id} subject={subject} data={data} />;
      }}
    </DataGate>
  );
}
