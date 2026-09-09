/**
 * The shape of the governed dataset, exactly as workbench/collect.py emits it.
 *
 * These types describe DATA, not decisions. Nothing here computes an outcome:
 * every governed verdict in the UI is read from a field that the backend
 * already decided. If a value is not in this file, the frontend does not know
 * it and must say so rather than derive it.
 */

export type Provenance = "OBSERVED" | "DEFAULTED" | "DERIVED";
export type FoldState =
  | "ESTABLISHED" | "UNREPORTED" | "EXPLICITLY_UNDEFINED"
  | "CONTRADICTED" | "INVALID";
export type ReadinessOutcome = "READY" | "NOT_READY" | "CANNOT_DECIDE";
export type BlockerKind =
  | "OBSERVED_FAILURE" | "MANUFACTURED_EVIDENCE" | "ABSENT_EVIDENCE"
  | "CONTRADICTED_EVIDENCE" | "SUBORDINATE";

export interface PropertyState {
  fold_state: FoldState | string;
  value: string | null;
  provenance: Provenance | null;
  basis_count?: number;
  defaulted_count?: number;
  effective_at?: string | null;
  arrival_at?: string | null;
  is_actor_reference?: boolean;
  simulated_actor?: boolean;
}

export type PropertyBag = Record<string, PropertyState>;

export interface ReadinessView {
  decision_type: string;
  outcome: ReadinessOutcome;
  why: string;
  intent: string;
  policy_version: string;
  missing_evidence: string[];
  insufficient_evidence: string[];
  failed: string[];
}

export interface Blocker {
  kind: BlockerKind;
  decision_type: string;
  property_name: string | null;
  statement: string;
  evidence_value: string | null;
  provenance: Provenance | null;
}

export interface WaitingOn {
  role: string | null;
  actor: string | null;          // always null: roles, never people
  basis: string;
  governance_basis: string;
  open_question: string | null;
}

export interface Recommendation {
  action: string;
  statement: string;
  target_role: string | null;
  property_name: string | null;
  authorized: boolean;
}

export interface Draft {
  communication_id: string;
  channel: "WORKBENCH_NOTE" | "EMAIL_DRAFT" | string;
  status: "DRAFT" | "SUPERSEDED" | string;
  to_role: string | null;
  to_actor: string | null;
  subject: string;
  body: string;
}

export interface JourneyStep {
  stage: string;
  statement: string;
  action?: string;
  kind?: string;
  policy_version?: string;
}

export interface AgentCase {
  case: {
    subject_type: string;
    subject_id: string;
    decision_horizon: string;
    readiness: ReadinessView[];
    evidence_counts: { established: number; defaulted: number; unreported: number };
    first_activity: string | null;
    last_activity: string | null;
    properties: PropertyBag;
  };
  headline: string;
  blockers: Blocker[];
  waiting_on: WaitingOn | null;
  recommendation: Recommendation | null;
  communications: Draft[];
  journey: JourneyStep[];
}

export interface GovernedDecision {
  decision_id: string;
  decision_type: string;
  subject_type: string;
  subject_id: string;
  outcome_code: string;
  reason_code: string | null;
  matched_rule_id: string | null;
  state: string;
  governance_basis: string;
  execution_mode: string;
  kb_version: string;
  policy_version: string;
  decided_at: string;
  superseded_by: string | null;
  input_digest: string | null;
}

export interface ConfigurationRow {
  configuration_id: string;
  product_id: string;
  canonical_identity: string;
  status: string;
  created_at: string;
  versions: number;
}

export interface EvidenceRow {
  subject_type: string;
  subject_id: string;
  mapping_id: string;
  property_name: string;
  asserted_value: string | null;
  value_provenance: Provenance;
  source_system: string;
  source_actor_id: string | null;
  source_actor_role: string | null;
  occurred_at: string;
  arrival_at: string;
  event_type: string | null;
  source_path: string | null;
}

export interface WorkbenchData {
  horizon: string;
  generated_from: string;
  totals: {
    evidence: number; observed: number; defaulted: number;
    mappings: number; subjects: number; property_states: number;
  };
  cases: AgentCase[];
  properties: Record<string, Record<string, PropertyBag>>;
  decisions: GovernedDecision[];
  configurations: ConfigurationRow[];
  evidence: EvidenceRow[];
}
