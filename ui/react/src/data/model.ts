/**
 * Presentation model over governed state.
 *
 * THE LINE THIS FILE DOES NOT CROSS
 *   No governed outcome is computed here. Every READY / NOT_READY /
 *   CANNOT_DECIDE / NO_BUSINESS_CHANGE / CREATE_CONFIGURATION shown in the UI
 *   is read from a field the backend already decided. What this file does is
 *   group, label and order -- work that belongs to a screen, not to policy.
 *
 *   The test for whether something belongs here: if the backend changed its
 *   mind, would this code still produce the same verdict? If yes, it is
 *   deriving an outcome and it does not belong.
 */
import type {
  AgentCase, BlockerKind, GovernedDecision, PropertyBag, WorkbenchData,
} from "../types/claris";

/* ── personas ──────────────────────────────────────────────────────────────
   The five lanes the business recognises. This is a VIEW over governed
   properties, not a workflow: evidence arrives late and out of order, and a
   lane being "complete" says only that its evidence is in, never that the
   case reached it by travelling through the lane before it. */
export const PERSONAS = [
  "Marketing", "Product Operations", "IS&T", "Finance", "Activation",
] as const;
export type Persona = (typeof PERSONAS)[number];

/** Which lane owns a governed property. Presentation grouping only. */
export const PERSONA_FOR_PROPERTY: Record<string, Persona> = {
  change_requested_by: "Marketing",
  change_requester_role: "Marketing",
  intent_classification: "Marketing",
  product_reference: "Marketing",
  geography: "Marketing",
  term_months: "Marketing",
  customer_segment: "Marketing",
  launch_reference: "Marketing",
  product_name: "Marketing",

  sku_status: "Product Operations",
  sku_activation_status: "Product Operations",
  hierarchy_approval_code: "Product Operations",
  hierarchy_approval_authority: "Product Operations",
  sap_con_load_status: "Product Operations",
  sap_con_hierarchy_code: "Product Operations",
  sap_con_load_actor: "Product Operations",
  sap_prd_load_status: "Product Operations",
  sap_prd_hierarchy_code: "Product Operations",
  sap_prd_promotion_hierarchy_code: "Product Operations",
  sap_prd_promotion_actor: "Product Operations",

  technical_review_result: "IS&T",
  con_verification_status: "IS&T",
  sap_con_test_status: "IS&T",
  sap_con_test_actor: "IS&T",

  pricing_status: "Finance",
  pricing_value_usd: "Finance",
  pricing_confirmed: "Finance",
  final_pricing_approval_status: "Finance",
  pricing_upload_status: "Finance",
  pricing_uploaded_price_usd: "Finance",
  pricing_publication_status: "Finance",
  pricing_list_price: "Finance",
  pricing_currency: "Finance",
  pricing_published_by: "Finance",
  zupdm_approval_status: "Finance",
  all_gates_cleared: "Finance",
  overnight_push_status: "Finance",
  overnight_push_run_date: "Finance",

  go_live_approval_requested: "Activation",
  go_live_approval_level: "Activation",
  go_live_requested_by: "Activation",
  go_live_approval_status: "Activation",
  go_live_approved_by: "Activation",
  material_activation_status: "Activation",
  material_activated_by: "Activation",
  material_status: "Activation",
  supply_chain_notification_status: "Activation",
  supply_chain_notification_type: "Activation",
  supply_chain_notified_by: "Activation",
};

/** The agent routes to a responsible ROLE; the board thinks in personas. */
export const PERSONA_FOR_ROLE: Record<string, Persona> = {
  "Technical Review": "IS&T",
  "SAP Operations": "Product Operations",
  "Master Data": "Product Operations",
  Pricing: "Finance",
  Finance: "Finance",
  "Pricing Operations": "Finance",
  "Launch Governance": "Activation",
  "Supply Chain": "Activation",
  "Requesting role": "Marketing",
};

/* ── plain language ───────────────────────────────────────────────────────
   Internal codes stay in the details; the surface reads like a person wrote
   it. The mapping is one-way and lossless -- the code travels alongside so a
   reader can always get back to it. */
export const BLOCKER_LABEL: Record<BlockerKind, string> = {
  OBSERVED_FAILURE: "Reported as failed by the source",
  MANUFACTURED_EVIDENCE: "Not confirmed by source",
  ABSENT_EVIDENCE: "Required evidence not received",
  CONTRADICTED_EVIDENCE: "Sources disagree",
  SUBORDINATE: "Waiting on an earlier decision",
};

export const OUTCOME_LABEL: Record<string, string> = {
  READY: "Ready",
  NOT_READY: "Not ready",
  CANNOT_DECIDE: "Cannot decide",
  NO_BUSINESS_CHANGE: "No business change",
  CREATE_CONFIGURATION: "Create configuration",
  CREATE_BUSINESS_IDENTITY: "Create business identity",
  NEW_VERSION: "New version",
  NO_GOVERNED_DECISION: "Not governed at this level",
};

export type Tone = "ready" | "attention" | "blocked" | "quiet";

/** Tone is a property of the OUTCOME, never chosen at a call site. */
export function toneForOutcome(outcome: string): Tone {
  switch (outcome) {
    case "READY":
    case "NO_BUSINESS_CHANGE":
    case "CREATE_CONFIGURATION":
    case "CREATE_BUSINESS_IDENTITY":
    case "NEW_VERSION":
      return "ready";
    case "NOT_READY":
      return "blocked";
    case "CANNOT_DECIDE":
      return "attention";
    default:
      return "quiet";
  }
}

export function toneForProvenance(p: string | null | undefined): Tone {
  if (p === "OBSERVED") return "ready";
  if (p === "DEFAULTED") return "attention";
  if (p === "DERIVED") return "attention";
  return "quiet";
}

/* ── the portfolio ────────────────────────────────────────────────────────
   Three kinds of case, because governed state supports three and no more.

   A Launch is NOT the parent of a Change here. SKU_MINTED carries a launch id
   in the RAW event, but no governed property records it, so the two are shown
   side by side and the boundary is stated on screen. Manufacturing the join
   would be the one thing this product exists to stop. */
export type CaseKind = "Launch" | "Change" | "Configuration request";

export interface PortfolioCase {
  id: string;
  kind: CaseKind;
  subjectType: string;
  product: string | null;
  outcome: string;
  outcomeLabel: string;
  tone: Tone;
  waitingOnRole: string | null;
  waitingOnPersona: Persona | null;
  blockerLabel: string | null;
  blockerKind: BlockerKind | null;
  firstActivity: string | null;
  lastActivity: string | null;
  established: number;
  defaulted: number;
  unreported: number;
  agent?: AgentCase;
  properties: PropertyBag;
  decisions: GovernedDecision[];
  /** True when the governed model cannot relate this case to a launch. */
  launchLinkUnavailable: boolean;
}

function stamps(properties: PropertyBag, field: "effective_at" | "arrival_at") {
  return Object.values(properties)
    .map((p) => p[field])
    .filter((value): value is string => Boolean(value))
    .sort();
}

function productOf(properties: PropertyBag): string | null {
  return (
    properties.product_reference?.value ??
    properties.launch_reference?.value ??
    null
  );
}

export function buildPortfolio(data: WorkbenchData): PortfolioCase[] {
  const cases: PortfolioCase[] = [];

  /* Changes -- one per sku subject, carrying the agent's analysis. */
  for (const agent of data.cases) {
    const launch = agent.case.readiness.find(
      (r) => r.decision_type === "LAUNCH_READINESS",
    );
    const worst = agent.blockers[0] ?? null;
    const role = agent.waiting_on?.role ?? null;
    cases.push({
      id: agent.case.subject_id,
      kind: "Change",
      subjectType: agent.case.subject_type,
      product: null,
      outcome: launch?.outcome ?? "NO_GOVERNED_DECISION",
      outcomeLabel: OUTCOME_LABEL[launch?.outcome ?? "NO_GOVERNED_DECISION"],
      tone: toneForOutcome(launch?.outcome ?? "NO_GOVERNED_DECISION"),
      waitingOnRole: role,
      waitingOnPersona: role ? PERSONA_FOR_ROLE[role] ?? null : null,
      blockerLabel: worst ? BLOCKER_LABEL[worst.kind] : null,
      blockerKind: worst ? worst.kind : null,
      firstActivity: agent.case.first_activity,
      lastActivity: agent.case.last_activity,
      established: agent.case.evidence_counts.established,
      defaulted: agent.case.evidence_counts.defaulted,
      unreported: agent.case.evidence_counts.unreported,
      agent,
      properties: agent.case.properties,
      decisions: data.decisions.filter((d) => d.subject_id === agent.case.subject_id),
      launchLinkUnavailable: true,
    });
  }

  /* Launches -- real governed subjects, but no readiness decision is defined
     for them, so the state column says exactly that rather than guessing. */
  for (const [id, properties] of Object.entries(data.properties.launch ?? {})) {
    const arrivals = stamps(properties, "arrival_at");
    const established = Object.values(properties)
      .filter((p) => p.fold_state === "ESTABLISHED").length;
    cases.push({
      id, kind: "Launch", subjectType: "launch",
      product: productOf(properties),
      outcome: "NO_GOVERNED_DECISION",
      outcomeLabel: OUTCOME_LABEL.NO_GOVERNED_DECISION,
      tone: "quiet",
      waitingOnRole: null, waitingOnPersona: null,
      blockerLabel: null, blockerKind: null,
      firstActivity: stamps(properties, "effective_at")[0] ?? null,
      lastActivity: arrivals[arrivals.length - 1] ?? null,
      established,
      defaulted: Object.values(properties)
        .filter((p) => p.provenance === "DEFAULTED").length,
      unreported: Object.values(properties).length - established,
      properties,
      decisions: data.decisions.filter((d) => d.subject_id === id),
      launchLinkUnavailable: false,
    });
  }

  /* Configuration requests -- the identity decisions. */
  for (const [id, properties] of Object.entries(
    data.properties.configuration_request ?? {},
  )) {
    const decisions = data.decisions.filter((d) => d.subject_id === id);
    const current = decisions.find((d) => d.state === "current") ?? decisions[0];
    const outcome = current?.outcome_code ?? "NO_GOVERNED_DECISION";
    const missing = ["product_reference", "geography", "term_months",
                     "customer_segment"]
      .filter((n) => properties[n]?.fold_state !== "ESTABLISHED");
    const arrivals = stamps(properties, "arrival_at");
    const established = Object.values(properties)
      .filter((p) => p.fold_state === "ESTABLISHED").length;
    cases.push({
      id, kind: "Configuration request", subjectType: "configuration_request",
      product: productOf(properties),
      outcome,
      outcomeLabel: OUTCOME_LABEL[outcome] ?? outcome,
      tone: toneForOutcome(outcome),
      waitingOnRole: missing.length ? "Requesting role" : null,
      waitingOnPersona: missing.length ? "Marketing" : null,
      blockerLabel: missing.length ? BLOCKER_LABEL.ABSENT_EVIDENCE : null,
      blockerKind: missing.length ? "ABSENT_EVIDENCE" : null,
      firstActivity: stamps(properties, "effective_at")[0] ?? null,
      lastActivity: arrivals[arrivals.length - 1] ?? null,
      established,
      defaulted: Object.values(properties)
        .filter((p) => p.provenance === "DEFAULTED").length,
      unreported: Object.values(properties).length - established,
      properties,
      decisions,
      launchLinkUnavailable: false,
    });
  }

  return cases.sort(
    (a, b) => a.kind.localeCompare(b.kind) || a.id.localeCompare(b.id),
  );
}

/* ── headline counters ────────────────────────────────────────────────────
   Three numbers, because an executive board that needs a legend is not a
   board. Every one is a count of governed rows; none is a target, and none is
   adjusted to make the page look better. "Ready" reads 0 because no case has
   complete observed evidence, and that is the finding, not an empty state. */
export interface Kpi {
  label: string; value: number; hint: string; tone: Tone;
}

export function buildKpis(cases: PortfolioCase[]): Kpi[] {
  return [
    { label: "Cases", tone: "quiet", value: cases.length,
      hint: "launches, changes and configuration requests" },
    { label: "Need attention", tone: "attention",
      value: cases.filter((c) => c.blockerKind !== null).length,
      hint: "a governed decision is blocked or cannot be reached" },
    { label: "Ready", tone: "ready",
      value: cases.filter((c) => c.outcome === "READY").length,
      hint: "all required evidence received and confirmed" },
  ];
}

/** "13 Launches · 13 Changes · 7 Configuration Requests" -- context, not a KPI. */
export function typeCounts(cases: PortfolioCase[]): { kind: CaseKind; count: number }[] {
  return (["Launch", "Change", "Configuration request"] as CaseKind[])
    .map((kind) => ({ kind, count: cases.filter((c) => c.kind === kind).length }))
    .filter((row) => row.count > 0);
}

/** How long a case has been idle, and how many are waiting on each team. */
export function waitingOnCounts(cases: PortfolioCase[]): { persona: Persona; count: number }[] {
  return PERSONAS
    .map((persona) => ({
      persona,
      count: cases.filter((c) => c.waitingOnPersona === persona).length,
    }))
    .filter((row) => row.count > 0);
}

/* ── persona lanes for one case ───────────────────────────────────────────
   Five teams, one business state each. Counts used to sit here ("7 of 14
   reported"); they live in Evidence now, where a reader who wants them is
   already asking the deeper question. The lane answers one thing: does my
   team need to act?

   This file decides the STATE. The words that describe it are in
   language.ts -- a lane says what governed state holds, not how to phrase it. */
export type LaneStatus =
  | "complete" | "needs-confirmation" | "in-progress" | "not-started"
  | "rejected" | "not-established";

export interface Lane {
  persona: Persona;
  status: LaneStatus;
  label: string;
  /** The governed property this lane is stuck on, when there is one. */
  blockerKind: BlockerKind | null;
  blockerProperty: string | null;
  properties: string[];
  reported: number;
}

const LANE_LABEL: Record<LaneStatus, string> = {
  complete: "Complete",
  "needs-confirmation": "Needs confirmation",
  "in-progress": "In progress",
  "not-started": "Not started",
  rejected: "Rejected",
  "not-established": "Not established",
};

export function buildLanes(subject: PortfolioCase): Lane[] {
  const blockerFor = new Map<string, BlockerKind>();
  for (const blocker of subject.agent?.blockers ?? []) {
    if (blocker.property_name) blockerFor.set(blocker.property_name, blocker.kind);
  }

  return PERSONAS.map((persona) => {
    const names = Object.keys(subject.properties).filter(
      (name) => PERSONA_FOR_PROPERTY[name] === persona,
    );
    if (names.length === 0) {
      return {
        persona, status: "not-established" as LaneStatus,
        label: LANE_LABEL["not-established"],
        blockerKind: null, blockerProperty: null, properties: [], reported: 0,
      };
    }

    const blocked = names
      .map((name) => ({ name, kind: blockerFor.get(name) }))
      .filter((b): b is { name: string; kind: BlockerKind } => Boolean(b.kind));
    const reported = names.filter(
      (n) => subject.properties[n].fold_state === "ESTABLISHED",
    ).length;

    /* Worst blocker wins the lane, in the same order the agent ranks them. */
    const worst =
      blocked.find((b) => b.kind === "OBSERVED_FAILURE")
      ?? blocked.find((b) => b.kind === "CONTRADICTED_EVIDENCE")
      ?? blocked.find((b) => b.kind === "MANUFACTURED_EVIDENCE")
      ?? blocked.find((b) => b.kind === "ABSENT_EVIDENCE")
      ?? null;

    let status: LaneStatus;
    if (worst?.kind === "OBSERVED_FAILURE" || worst?.kind === "CONTRADICTED_EVIDENCE") {
      status = "rejected";
    } else if (worst) status = "needs-confirmation";
    else if (reported === names.length) status = "complete";
    else if (reported > 0) status = "in-progress";
    else status = "not-started";

    return {
      persona, status, label: LANE_LABEL[status],
      blockerKind: worst?.kind ?? null,
      blockerProperty: worst?.name ?? null,
      properties: names.sort(),
      reported,
    };
  });
}

export const LANE_TONE: Record<LaneStatus, Tone> = {
  complete: "ready",
  "needs-confirmation": "attention",
  "in-progress": "attention",
  "not-started": "quiet",
  rejected: "blocked",
  "not-established": "quiet",
};

/* ── small helpers ────────────────────────────────────────────────────────*/
export function ageInDays(from: string | null, horizon: string): number | null {
  if (!from) return null;
  const days = (Date.parse(horizon) - Date.parse(from)) / 86_400_000;
  return Number.isFinite(days) ? Math.max(0, Math.round(days)) : null;
}

export function shortDate(iso: string | null | undefined): string {
  return iso ? String(iso).slice(0, 10) : "—";
}
