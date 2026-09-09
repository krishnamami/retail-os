/**
 * Business language over governed state.
 *
 * THE LINE THIS FILE DOES NOT CROSS
 *   Nothing here decides anything. Every function takes a governed outcome
 *   that the backend already produced and says it in the words a Product
 *   Manager, a Finance lead or an IS&T reviewer actually uses. The ontology
 *   term always survives underneath -- Decision Record and Evidence still show
 *   TECHNICAL_READINESS, MANUFACTURED_EVIDENCE and READINESS-v1.0.0-PROTOTYPE
 *   verbatim, because the audit surface must not be translated.
 *
 *   Rename a label here and no verdict changes. That is the test.
 */
import { PERSONA_FOR_PROPERTY, PERSONA_FOR_ROLE } from "./model";
import type { Lane, Persona, PortfolioCase, Tone } from "./model";
import type { AgentCase, BlockerKind, GovernedDecision, ReadinessView }
  from "../types/claris";

/* ── properties ───────────────────────────────────────────────────────────
   The closed set of properties that readiness policy actually references.
   A property with no entry falls back to its own name rather than a guess. */
export const PROPERTY_LABEL: Record<string, string> = {
  technical_review_result: "Technical approval",
  pricing_status: "Pricing status",
  pricing_value_usd: "Pricing amount",
  pricing_approval: "Pricing approval",
  go_live_approval_status: "Go-live approval",
  product_reference: "Product",
  geography: "Geography",
  term_months: "Term",
  customer_segment: "Customer segment",
};

export function propertyLabel(name: string | null | undefined): string {
  if (!name) return "A required fact";
  return PROPERTY_LABEL[name] ?? name.replace(/_/g, " ");
}

/* ── decision areas ───────────────────────────────────────────────────────
   Three governed decision types, three business areas, fixed order. */
const AREA_LABEL: Record<string, string> = {
  TECHNICAL_READINESS: "Technical",
  PRICING_READINESS: "Pricing",
  LAUNCH_READINESS: "Launch",
};
const AREA_ORDER = ["TECHNICAL_READINESS", "PRICING_READINESS", "LAUNCH_READINESS"];

export interface AreaRow {
  area: string;
  decisionType: string;
  status: string;
  tone: Tone;
  why: string;
}

function list(names: string[]): string {
  const labels = names.map(propertyLabel);
  if (labels.length <= 1) return labels[0] ?? "";
  return `${labels.slice(0, -1).join(", ")} and ${labels[labels.length - 1]}`;
}

/** "has" for one fact, "have" for several -- the why column is a sentence. */
function verb(count: number): string {
  return count === 1 ? "has" : "have";
}

/**
 * One business row per governed readiness decision.
 *
 * The status word is chosen by the OUTCOME plus which list the backend put
 * the evidence in -- never by re-testing the evidence.
 */
export function decisionAreas(agent: AgentCase): AreaRow[] {
  /* A decision with no missing input of its own is waiting on other
     decisions. Naming them beats "an earlier decision has not been reached",
     and the dependency comes from the governed subordinate findings. */
  const deps = new Map(
    decisionDependencies(agent).map((d) => [d.decisionType, d.dependsOn.map((x) => x.area)]),
  );
  const rows = agent.case.readiness.map((r) => ({
    area: AREA_LABEL[r.decision_type] ?? r.decision_type,
    decisionType: r.decision_type,
    ...businessStatus(r, deps.get(r.decision_type) ?? []),
  }));
  return rows.sort(
    (a, b) => AREA_ORDER.indexOf(a.decisionType) - AREA_ORDER.indexOf(b.decisionType),
  );
}

function businessStatus(
  r: ReadinessView, dependsOn: string[] = [],
): { status: string; tone: Tone; why: string } {
  if (r.outcome === "READY") {
    return { status: "Ready", tone: "ready", why: "All required evidence received and confirmed" };
  }
  if (r.outcome === "NOT_READY") {
    return {
      status: "Not ready",
      tone: "blocked",
      why: r.failed.length
        ? `${list(r.failed)} ${r.failed.length === 1 ? "was" : "were"} rejected by the source`
        : dependsOn.length
          ? `${joinAreas(dependsOn)} ${verb(dependsOn.length)} not been satisfied`
          : "An earlier decision is not ready",
    };
  }
  // CANNOT_DECIDE -- the platform declined to guess. Which kind of gap it is
  // decides the wording, and the backend already sorted the properties.
  if (r.insufficient_evidence.length) {
    return {
      status: "Needs confirmation",
      tone: "attention",
      why: `${list(r.insufficient_evidence)} ${r.insufficient_evidence.length === 1 ? "is" : "are"} not confirmed by a source`,
    };
  }
  if (r.missing_evidence.length) {
    return {
      status: "Cannot decide",
      tone: "attention",
      why: `${list(r.missing_evidence)} ${verb(r.missing_evidence.length)} not been received`,
    };
  }
  return {
    status: "Cannot decide",
    tone: "attention",
    why: dependsOn.length
      ? `${joinAreas(dependsOn)} requirements are unresolved`
      : "An earlier decision has not been reached",
  };
}

function joinAreas(areas: string[]): string {
  if (areas.length <= 1) return areas[0] ?? "";
  return `${areas.slice(0, -1).join(", ")} and ${areas[areas.length - 1]}`;
}

/* ── blockers ─────────────────────────────────────────────────────────────*/
const CONDITION_SHORT: Record<BlockerKind, (label: string) => string> = {
  OBSERVED_FAILURE: (l) => `${l} rejected`,
  MANUFACTURED_EVIDENCE: (l) => `${l} not confirmed`,
  ABSENT_EVIDENCE: (l) => `${l} not received`,
  CONTRADICTED_EVIDENCE: (l) => `${l}: sources disagree`,
  SUBORDINATE: () => "Waiting on an earlier decision",
};

const CONDITION_LONG: Record<BlockerKind, (label: string) => string> = {
  OBSERVED_FAILURE: (l) => `${l} was rejected by the source system.`,
  MANUFACTURED_EVIDENCE: (l) =>
    `${l} has not been confirmed by a source. A value is present, but it was ` +
    `supplied by projection logic rather than asserted by a system or a person.`,
  ABSENT_EVIDENCE: (l) => `${l} has not been received from any source.`,
  CONTRADICTED_EVIDENCE: (l) => `Sources disagree about ${l.toLowerCase()}.`,
  SUBORDINATE: () => "This decision depends on an earlier one that has not been reached.",
};

export interface BlockerView {
  short: string;
  long: string;
  propertyLabel: string;
  value: string | null;
  provenance: string | null;
  kind: BlockerKind;
}

/** The worst blocker, in business words. The backend ordered them; we read [0]. */
export function primaryBlocker(agent: AgentCase | undefined): BlockerView | null {
  const b = agent?.blockers?.find((x) => x.kind !== "SUBORDINATE") ?? agent?.blockers?.[0];
  if (!b) return null;
  const label = propertyLabel(b.property_name);
  return {
    short: CONDITION_SHORT[b.kind](label),
    long: CONDITION_LONG[b.kind](label),
    propertyLabel: label,
    value: b.evidence_value,
    provenance: b.provenance,
    kind: b.kind,
  };
}

/* ── who needs to act ─────────────────────────────────────────────────────
   The agent routes to a responsible ROLE. The board thinks in teams. Both are
   shown; neither is a person, because no individual is established. */
export interface ActionOwner { team: Persona | null; role: string }

export function needsActionFrom(agent: AgentCase | undefined): ActionOwner | null {
  const role = agent?.waiting_on?.role;
  if (!role) return null;
  return { team: PERSONA_FOR_ROLE[role] ?? null, role };
}

/* ── the recommendation ───────────────────────────────────────────────────*/
const ACTION_LABEL: Record<string, string> = {
  REQUEST_EVIDENCE: "Request update",
  REQUEST_DECISION: "Request confirmation",
  ESCALATE: "Escalate",
  NO_ACTION_REQUIRED: "No action required",
};

export interface NextAction {
  /** Button copy. */
  label: string;
  /** One business sentence. */
  statement: string;
  /** The agent's own words, kept for the reasoning drawer. */
  reasoning: string;
  code: string;
}

export function nextAction(agent: AgentCase | undefined): NextAction | null {
  const rec = agent?.recommendation;
  if (!rec) return null;
  const owner = needsActionFrom(agent);
  const team = owner?.team ?? owner?.role ?? "the responsible team";
  const label = ACTION_LABEL[rec.action] ?? "Take action";
  const property = propertyLabel(rec.property_name);
  const statement =
    rec.action === "REQUEST_DECISION"
      ? `Request ${property.toLowerCase()} confirmation from ${team}.`
      : rec.action === "REQUEST_EVIDENCE"
        ? `Ask ${team} for ${property.toLowerCase()}.`
        : rec.action === "ESCALATE"
          ? `Escalate to ${team}.`
          : "No action is required.";
  return { label, statement, reasoning: rec.statement, code: rec.action };
}

/* ── configuration decisions ──────────────────────────────────────────────
   Two governed decisions per request matter to a business reader: the FIRST
   one, which says what the request caused, and the CURRENT one, which says
   what the same request would conclude now that those configurations exist.
   Both are stored. Neither is computed here.  */
export const IDENTITY_OUTCOME_LABEL: Record<string, string> = {
  CREATE_PRODUCT: "Created product",
  CREATE_CONFIGURATION: "Created configuration",
  CREATE_BUSINESS_IDENTITY: "Created business identity",
  NEW_VERSION: "New version",
  NO_BUSINESS_CHANGE: "Reuse existing",
  CANNOT_DECIDE: "Cannot decide",
};

export function identityLabel(code: string | undefined): string {
  return code ? IDENTITY_OUTCOME_LABEL[code] ?? code : "—";
}

export function firstDecision(decisions: GovernedDecision[]): GovernedDecision | undefined {
  return [...decisions].sort((a, b) => a.decided_at.localeCompare(b.decided_at))[0];
}

export function currentDecision(decisions: GovernedDecision[]): GovernedDecision | undefined {
  return decisions.find((d) => d.state === "current") ?? firstDecision(decisions);
}

/** Segments are stored lower-case; two of them are acronyms, not words. */
const SEGMENT_LABEL: Record<string, string> = {
  enterprise: "Enterprise",
  smb: "SMB",
  smb_plus: "SMB+",
};

/** "NAMER · 36 · Enterprise" -- readable, and never the serialized identity. */
export function businessIdentity(
  properties: Record<string, { fold_state: string; value: string | null }>,
): string | null {
  const parts = ["geography", "term_months", "customer_segment"].map((name) => {
    const p = properties[name];
    return p?.fold_state === "ESTABLISHED" ? p.value : null;
  });
  if (parts.some((p) => p === null)) return null;
  const [geography, term, segment] = parts as string[];
  return `${geography} · ${formatTerm(term)} · ${SEGMENT_LABEL[segment.toLowerCase()] ?? segment}`;
}

/* ══════════════════════════════════════════════════════════════════════════
   IDENTITY DECISIONS
   ══════════════════════════════════════════════════════════════════════════
   A configuration request is not a launch. It asks one question -- does this
   describe something that already exists? -- and the platform answers it from
   four facts. Everything below reads that answer; none of it re-derives one.

   In particular: nothing here compares a request to a configuration. The
   platform performs that comparison and stores its verdict; a frontend that
   repeated it would produce the same answer even after the backend changed
   its mind, which is the definition of deriving an outcome.
   ══════════════════════════════════════════════════════════════════════════*/

export function formatTerm(months: string): string {
  const n = Number(months);
  return Number.isFinite(n) ? `${n} month${n === 1 ? "" : "s"}` : months;
}

/** The four facts that form a business identity, in the order they are read. */
export const IDENTITY_DIMENSIONS = [
  { property: "product_reference", label: "Product" },
  { property: "geography", label: "Geography" },
  { property: "term_months", label: "Term" },
  { property: "customer_segment", label: "Customer segment" },
] as const;

export interface IdentityFact {
  property: string;
  label: string;
  /** Business-formatted, or null when no source reported it. */
  value: string | null;
  provenance: string | null;
  reported: boolean;
}

function formatIdentityValue(property: string, value: string): string {
  if (property === "term_months") return formatTerm(value);
  if (property === "customer_segment") {
    return SEGMENT_LABEL[value.toLowerCase()] ?? value;
  }
  return value;
}

export function identityFacts(
  properties: Record<string, { fold_state: string; value: string | null;
                              provenance?: string | null }>,
): IdentityFact[] {
  return IDENTITY_DIMENSIONS.map(({ property, label }) => {
    const p = properties[property];
    const reported = p?.fold_state === "ESTABLISHED" && p.value !== null;
    return {
      property,
      label,
      value: reported ? formatIdentityValue(property, p.value as string) : null,
      provenance: p?.provenance ?? null,
      reported,
    };
  });
}

export function missingDimensions(facts: IdentityFact[]): IdentityFact[] {
  return facts.filter((f) => !f.reported);
}

/* ── the governed identity decision, in business words ────────────────────
   Outcome and reason are both stored. The wording below is chosen by that
   pair; it never inspects the facts to reach a different conclusion. */
export const REASON_LABEL: Record<string, string> = {
  EXACT_IDENTITY_MATCH: "Exact identity match",
  NEW_IDENTITY_TUPLE: "New identity",
  NEW_PRODUCT_FAMILY: "New product family",
  MISSING_REQUIRED_INPUT: "Required input missing",
};

export interface IdentityDecisionView {
  code: string;
  /** "No business change" -- the decision, said plainly. */
  headline: string;
  explanation: string;
  /** What should happen next. */
  result: string;
  tone: Tone;
}

const IDENTITY_DECISION: Record<string, Omit<IdentityDecisionView, "code">> = {
  NO_BUSINESS_CHANGE: {
    headline: "No business change",
    explanation:
      "The requested commercial identity already exists. Reuse the canonical " +
      "configuration rather than creating another business configuration.",
    result: "Reuse the existing configuration.",
    tone: "ready",
  },
  CREATE_CONFIGURATION: {
    headline: "Create configuration",
    explanation:
      "The request describes a complete business identity that does not " +
      "currently exist.",
    result: "Create a canonical configuration.",
    tone: "ready",
  },
  CREATE_PRODUCT: {
    headline: "Create product",
    explanation:
      "The requested product family does not yet exist in the canonical model.",
    result:
      "Create the product and its initial configuration, as governed by the " +
      "existing decision semantics.",
    tone: "ready",
  },
  CANNOT_DECIDE: {
    headline: "Cannot decide",
    explanation: "A required identity dimension has not been reported.",
    result: "No configuration is created until the identity is complete.",
    tone: "attention",
  },
};

export function identityDecision(
  decision: GovernedDecision | undefined,
  missing: IdentityFact[] = [],
): IdentityDecisionView | null {
  if (!decision) return null;
  const base = IDENTITY_DECISION[decision.outcome_code];
  if (!base) {
    return {
      code: decision.outcome_code,
      headline: decision.outcome_code.replace(/_/g, " ").toLowerCase(),
      explanation: "",
      result: "",
      tone: "quiet",
    };
  }
  const explanation =
    decision.outcome_code === "CANNOT_DECIDE" && missing.length
      ? `${list(missing.map((m) => m.property))} has not been reported, so no ` +
        `canonical identity can be formed.`
      : base.explanation;
  /* "No configuration is created" states the consequence; a next action has to
     say what would move it. The missing dimension is the answer, and it is
     read from governed state rather than assumed. */
  const result =
    decision.outcome_code === "CANNOT_DECIDE" && missing.length
      ? `Request the missing ${list(missing.map((m) => m.property)).toLowerCase()}.`
      : base.result;
  return { code: decision.outcome_code, ...base, explanation, result };
}

/* ── the decision flow ────────────────────────────────────────────────────
   A VISUALISATION of one governed decision, drawn from the identity facts and
   the stored outcome. These are not persisted workflow states, and the panel
   says so on screen. */
export interface FlowStep {
  label: string;
  detail?: string;
  tone: Tone;
  terminal?: boolean;
}

export function identityFlow(
  facts: IdentityFact[],
  decision: GovernedDecision | undefined,
): FlowStep[] {
  const missing = missingDimensions(facts);
  const complete = missing.length === 0;
  const outcome = decision?.outcome_code;

  const steps: FlowStep[] = [
    { label: "Request received", tone: "quiet" },
  ];

  if (!complete) {
    steps.push({ label: "Identity incomplete", tone: "attention" });
    steps.push({
      label: `${list(missing.map((m) => m.property))} missing`,
      tone: "attention",
    });
    steps.push({
      label: "Cannot decide", tone: "attention", terminal: true,
      detail: "Nothing is created until the required identity is complete.",
    });
    return steps;
  }

  steps.push({ label: "Identity complete", tone: "ready" });
  steps.push({ label: "Canonical identity evaluated", tone: "quiet" });

  if (outcome === "NO_BUSINESS_CHANGE") {
    steps.push({ label: "Existing identity found", tone: "ready" });
    steps.push({ label: "Reuse existing", tone: "ready", terminal: true });
  } else if (outcome === "CREATE_CONFIGURATION") {
    steps.push({ label: "No existing identity found", tone: "quiet" });
    steps.push({ label: "Create configuration", tone: "ready", terminal: true });
  } else if (outcome === "CREATE_PRODUCT") {
    steps.push({ label: "Product family not found", tone: "quiet" });
    steps.push({ label: "Create product", tone: "ready", terminal: true });
  } else {
    steps.push({
      label: identityLabel(outcome), tone: "quiet", terminal: true,
    });
  }
  return steps;
}

/* ── canonical identity, read aloud with the product ──────────────────────*/
export function fullIdentity(
  properties: Record<string, { fold_state: string; value: string | null }>,
): string | null {
  const facts = identityFacts(properties);
  if (facts.some((f) => !f.reported)) return null;
  return facts.map((f) => f.value).join(" · ");
}

/* ── legitimate variation examples ────────────────────────────────────────
   The four cards at the foot of a configuration case are built from OTHER
   requests in governed state, each carrying its own stored decision. Nothing
   is authored: if the corpus holds no request that differs only in term, no
   term card is rendered.

   This compares two sets of DISPLAYED governed facts to decide which card to
   show. It does not decide any request's outcome -- every card reads the
   outcome the backend already stored for the request it names. */
export interface VariantExample {
  requestId: string;
  /** "Same identity (this request)" | "Different geography" | ... */
  heading: string;
  identity: string;
  outcome: string;
  outcomeCode: string | undefined;
  isSame: boolean;
}

const VARIANT_HEADING: Record<string, string> = {
  geography: "Different geography",
  term_months: "Different term",
  customer_segment: "Different customer segment",
};

export function variantExamples(
  subjectId: string,
  properties: Record<string, { fold_state: string; value: string | null }>,
  all: Record<string, Record<string, { fold_state: string; value: string | null }>>,
  decisions: GovernedDecision[],
): VariantExample[] {
  const mine = identityFacts(properties);
  if (mine.some((f) => !f.reported)) return [];

  const codeOf = (id: string) =>
    firstDecision(decisions.filter((d) => d.subject_id === id))?.outcome_code;
  const outcomeOf = (id: string) => identityLabel(codeOf(id));

  const examples: VariantExample[] = [{
    requestId: subjectId,
    heading: "Same identity (this request)",
    identity: mine.map((f) => f.value).join(" · "),
    outcome: outcomeOf(subjectId),
    outcomeCode: codeOf(subjectId),
    isSame: true,
  }];

  for (const dimension of ["geography", "term_months", "customer_segment"]) {
    const match = Object.entries(all).find(([id, other]) => {
      if (id === subjectId) return false;
      const facts = identityFacts(other);
      if (facts.some((f) => !f.reported)) return false;
      // differs in exactly this dimension and nothing else
      return facts.every((f, i) =>
        f.property === dimension ? f.value !== mine[i].value : f.value === mine[i].value);
    });
    if (!match) continue;
    const [id, other] = match;
    examples.push({
      requestId: id,
      heading: VARIANT_HEADING[dimension] ?? dimension,
      identity: identityFacts(other).map((f) => f.value).join(" · "),
      outcome: outcomeOf(id),
      outcomeCode: codeOf(id),
      isSame: false,
    });
  }
  return examples;
}

/* ══════════════════════════════════════════════════════════════════════════
   SKU / CHANGE READINESS — the words
   ══════════════════════════════════════════════════════════════════════════*/

/** One line under a lane: what that team is actually waiting on. */
export function laneSubtext(lane: Lane, subject: PortfolioCase): string {
  if (lane.status === "not-established") {
    return subject.kind === "Change" && lane.persona === "Marketing"
      ? "Launch relationship not established"
      : "No governed property for this team";
  }
  const label = propertyLabel(lane.blockerProperty);
  switch (lane.blockerKind) {
    case "OBSERVED_FAILURE": return `${label} rejected by the source`;
    case "CONTRADICTED_EVIDENCE": return `Sources disagree about ${label.toLowerCase()}`;
    case "MANUFACTURED_EVIDENCE": return `${label} not confirmed by a source`;
    case "ABSENT_EVIDENCE": return `${label} required`;
    default: break;
  }
  if (lane.status === "complete") return "All required evidence received";
  if (lane.status === "in-progress") return "Some evidence still outstanding";
  return "No evidence reported";
}

/** How many governed readiness decisions have not reached READY. */
export function unresolvedCount(agent: AgentCase | undefined): number {
  return (agent?.case.readiness ?? []).filter((r) => r.outcome !== "READY").length;
}

/** Every property a readiness decision is still waiting on, in business words. */
export function missingEvidenceLabels(agent: AgentCase | undefined): string[] {
  const names = new Set<string>();
  for (const r of agent?.case.readiness ?? []) {
    for (const n of [...r.missing_evidence, ...r.insufficient_evidence, ...r.failed]) {
      names.add(n);
    }
  }
  return [...names].map(propertyLabel).sort();
}

/* ── open items by team ───────────────────────────────────────────────────
   The journey rail, reshaped into a table. It adds no claim: the grouping is
   the same presentation grouping the lanes use, and the only GOVERNED owner
   in this data is the single role the platform routes the next action to,
   which is marked as such. */
export interface OpenItem {
  team: Persona;
  status: "Action required" | "In progress" | "Not started";
  needed: string;
  isNextAction: boolean;
}

export function openItems(lanes: Lane[], subject: PortfolioCase): OpenItem[] {
  const owner = needsActionFrom(subject.agent);
  return lanes
    .filter((lane) => lane.status === "needs-confirmation"
      || lane.status === "rejected"
      || lane.status === "in-progress"
      || lane.status === "not-started")
    .map((lane) => ({
      team: lane.persona,
      status: (lane.blockerKind ? "Action required"
        : lane.status === "in-progress" ? "In progress"
        : "Not started") as OpenItem["status"],
      needed: laneSubtext(lane, subject),
      isNextAction: owner?.team === lane.persona,
    }));
}

/* ── the draft ────────────────────────────────────────────────────────────
   Composed from governed facts in business language. The agent's own draft
   quotes property names and internal codes; correct for an audit trail, wrong
   for a message a person is about to send. Neither is ever delivered. */
export interface DraftMessage {
  toRole: string;
  toTeam: string;
  regarding: string;
  body: string;
}

export function draftMessage(
  subject: PortfolioCase, agent: AgentCase | undefined,
): DraftMessage | null {
  const owner = needsActionFrom(agent);
  if (!owner) return null;
  const wanted = (agent?.case.readiness ?? [])
    .filter((r) => r.outcome !== "READY")
    .flatMap((r) => [...r.missing_evidence, ...r.insufficient_evidence])
    .filter((n) => PERSONA_FOR_PROPERTY[n] === owner.team)
    .map(propertyLabel);
  const unique = [...new Set(wanted)];
  const team = owner.team ?? owner.role;
  return {
    toRole: owner.role,
    toTeam: team,
    regarding: subject.id,
    body:
      `Hi ${team} team,\n\n` +
      (unique.length
        ? `We are missing ${list2(unique)} for ${subject.id}. Could you ` +
          `confirm the current status, or let us know if anything else is ` +
          `needed from us?`
        : `We are waiting on your confirmation for ${subject.id}. Could you ` +
          `let us know the current status?`) +
      `\n\nThanks,\nClaris Common Decision Platform`,
  };
}

function list2(items: string[]): string {
  const lower = items.map((i) => i.toLowerCase());
  if (lower.length <= 1) return lower[0] ?? "";
  return `${lower.slice(0, -1).join(", ")} and ${lower[lower.length - 1]}`;
}

/* ── decision dependencies ────────────────────────────────────────────────
   A subordinate blocker names the decision it depends on inside its own
   statement. Rather than print that sentence, the dependency is read out of
   it by matching the KNOWN decision-type vocabulary -- and if no known type
   appears, nothing is drawn rather than something guessed. */
export function decisionDependencies(
  agent: AgentCase | undefined,
): { decisionType: string; area: string; dependsOn: { type: string; area: string }[] }[] {
  const known = (agent?.case.readiness ?? []).map((r) => r.decision_type);
  const byDecision = new Map<string, Set<string>>();

  for (const blocker of agent?.blockers ?? []) {
    if (blocker.kind !== "SUBORDINATE") continue;
    const dependent = blocker.decision_type;
    for (const candidate of known) {
      if (candidate === dependent) continue;
      if (blocker.statement.includes(candidate)) {
        if (!byDecision.has(dependent)) byDecision.set(dependent, new Set());
        byDecision.get(dependent)!.add(candidate);
      }
    }
  }

  return [...byDecision.entries()].map(([decisionType, deps]) => ({
    decisionType,
    area: AREA_LABEL[decisionType] ?? decisionType,
    dependsOn: [...deps].map((type) => ({ type, area: AREA_LABEL[type] ?? type })),
  }));
}

/** "Technical Readiness" -- the decision type, said in business words. */
export function decisionAreaLabel(decisionType: string): string {
  const area = AREA_LABEL[decisionType];
  return area ? `${area} readiness` : decisionType;
}

/** "v1.0" from "READINESS-v1.0.0-PROTOTYPE" -- the rest lives in the details. */
export function shortPolicy(policyVersion: string | null | undefined): string {
  if (!policyVersion) return "—";
  const match = policyVersion.match(/v(\d+\.\d+)/);
  return match ? `v${match[1]}` : policyVersion;
}

/* ── related requests ─────────────────────────────────────────────────────
   Several requests, fewer canonical identities. The Decision column reads
   the decision each request RECEIVED WHEN IT ARRIVED, because that is what
   the request caused; a replay of every one of them today would read "reuse"
   and erase the creations that made the configurations exist. */
export interface RelatedRequest {
  id: string;
  facts: IdentityFact[];
  decision: string;
  outcomeCode: string | undefined;
  isSelf: boolean;
}

export function relatedRequests(
  subjectId: string,
  all: Record<string, Record<string, { fold_state: string; value: string | null;
                                       provenance?: string | null }>>,
  decisions: GovernedDecision[],
): RelatedRequest[] {
  return Object.entries(all)
    .map(([id, properties]) => {
      const original = firstDecision(decisions.filter((d) => d.subject_id === id));
      return {
        id,
        facts: identityFacts(properties),
        decision: identityLabel(original?.outcome_code),
        outcomeCode: original?.outcome_code,
        isSelf: id === subjectId,
      };
    })
    .sort((a, b) => a.id.localeCompare(b.id));
}

/** The consequence, in the words the teaching cards use. */
export const CONSEQUENCE_LABEL: Record<string, string> = {
  NO_BUSINESS_CHANGE: "Reuse existing configuration",
  CREATE_CONFIGURATION: "Create new configuration",
  CREATE_PRODUCT: "Create product and configuration",
  CREATE_BUSINESS_IDENTITY: "Create business identity",
  NEW_VERSION: "Create new version",
  CANNOT_DECIDE: "Create nothing",
};

export function consequenceLabel(code: string | undefined): string {
  return code ? CONSEQUENCE_LABEL[code] ?? identityLabel(code) : "—";
}
