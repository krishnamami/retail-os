/**
 * Configuration Request — canonical identity, and what it means for SKU
 * proliferation.
 *
 * THE ONE IDEA THIS SCREEN EXISTS TO LAND
 *   A new SKU does not automatically mean a new business configuration. The
 *   platform first asks what the canonical business identity is. If that
 *   identity exists, the configuration is reused, and any further identifier
 *   a legacy system demands is a PROJECTION of that same configuration rather
 *   than another business configuration.
 *
 * WHAT THIS COMPONENT WILL NOT DO
 *   It does not compare a request to a configuration, and it does not name a
 *   matched configuration or a legacy identifier. The deployed prototype
 *   stores neither relationship (see the governed-relationship check in the
 *   report). Where the link is absent the screen draws the architecture and
 *   says the relationship is not established — a fabricated CFG- or SKU- id
 *   would demo better and teach the wrong thing.
 */
import {
  ArrowDown, ArrowRight, Check, CircleDashed, Database, FileText, Info, Link2,
  Minus, Plus, Search, ShieldCheck,
} from "lucide-react";
import { Link } from "react-router-dom";

import { ProvenanceChip } from "./Badges";
import {
  IDENTITY_DIMENSIONS, consequenceLabel, fullIdentity, identityFacts,
  identityFlow, missingDimensions, relatedRequests, variantExamples,
} from "../data/language";
import type { IdentityFact } from "../data/language";
import { shortDate } from "../data/model";
import type { PortfolioCase, Tone } from "../data/model";
import type { GovernedDecision, WorkbenchData } from "../types/claris";

/* The systems the architecture projects into. Named as CONCEPTS only: no
   identifier is shown for any of them, because governed state records none. */
const TARGET_SYSTEMS = ["all_skus", "SAP", "ww_pricing", "Salesforce"];

const TONE_BOX: Record<Tone, string> = {
  ready: "border-ready-br bg-ready-bg text-ready-fg",
  attention: "border-attention-br bg-attention-bg text-attention-fg",
  blocked: "border-blocked-br bg-blocked-bg text-blocked-fg",
  quiet: "border-slate-200 bg-white text-slate-600",
};

function Panel({ title, sub, children, className = "" }: {
  title: string; sub?: string; children: React.ReactNode; className?: string;
}) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-white p-5 ${className}`}>
      <h2 className="text-[14px] font-semibold text-claris-900">{title}</h2>
      {sub && <p className="mt-0.5 text-[12px] leading-relaxed text-slate-500">{sub}</p>}
      <div className="mt-3.5">{children}</div>
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-slate-100 py-2 last:border-0">
      <span className="text-[12.5px] text-slate-500">{label}</span>
      <span className="text-right text-[13px] font-medium text-claris-900">{children}</span>
    </div>
  );
}

/* ── 1. identity resolution ──────────────────────────────────────────────
   Four stages: what arrived, what the platform concluded, what that means
   for the canonical model, and what it means for legacy systems. The fourth
   is where the prototype's boundary lives, and it says so. */
function Stage({ n, title, note, children, tone = "quiet" }: {
  n: number; title: string; note?: string; children: React.ReactNode; tone?: Tone;
}) {
  return (
    <div className={`flex-1 rounded-xl border p-3.5 ${
      tone === "ready" ? "border-ready-br bg-ready-bg/40"
      : tone === "attention" ? "border-attention-br bg-attention-bg/40"
      : "border-slate-200 bg-white"}`}>
      <div className="mb-2.5 flex items-center gap-2">
        <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-claris-700 text-[11px] font-bold text-white">
          {n}
        </span>
        <span className="text-[12.5px] font-semibold text-claris-900">{title}</span>
      </div>
      {children}
      {note && <p className="mt-2 text-[10.5px] leading-snug text-slate-400">{note}</p>}
    </div>
  );
}

function IdentityResolution({ facts, decision, original, identity }: {
  facts: IdentityFact[]; decision: GovernedDecision | undefined;
  original: GovernedDecision | undefined; identity: string | null;
}) {
  const complete = missingDimensions(facts).length === 0;
  const outcome = decision?.outcome_code;
  const reuse = outcome === "NO_BUSINESS_CHANGE";
  const creates = outcome === "CREATE_CONFIGURATION" || outcome === "CREATE_PRODUCT";
  const originallyCreated =
    original && outcome !== original.outcome_code
    && (original.outcome_code === "CREATE_CONFIGURATION"
        || original.outcome_code === "CREATE_PRODUCT");

  return (
    <div>
      <div className="flex flex-col gap-2 lg:flex-row lg:items-stretch">
        <Stage n={1} title="Incoming request">
          <div className="space-y-0.5 text-[12.5px]">
            {facts.map((f) => (
              <div key={f.property} className={f.reported ? "text-claris-900" : "text-attention-fg"}>
                {f.reported ? f.value : `${f.label}: not reported`}
              </div>
            ))}
          </div>
        </Stage>

        <Arrow />

        <Stage n={2} title="Identity assessment"
               tone={complete ? "quiet" : "attention"}>
          <div>
            <span className="mb-2 inline-flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500">
              {complete ? <Search className="h-4 w-4" /> : <Minus className="h-4 w-4" />}
            </span>
            <div className="text-[12.5px] leading-snug">
              <div className="font-semibold text-claris-900">
                {!complete ? "Cannot evaluate"
                  : reuse ? "Match found"
                  : creates ? "No match found"
                  : "Assessed"}
              </div>
              <div className="text-slate-500">
                {!complete ? "Required identity incomplete"
                  : reuse ? "Same canonical business identity"
                  : creates ? "Identity-bearing dimension differs"
                  : "See decision record"}
              </div>
            </div>
          </div>
        </Stage>

        <Arrow />

        <Stage n={3} title="Canonical configuration"
               tone={complete ? (reuse ? "ready" : "quiet") : "attention"}
               note="Configuration identifier not established in governed state.">
          {complete ? (
            <>
              <div>
                <Database className="mb-1.5 h-4 w-4 text-claris-500" />
                <div className="text-[12.5px] font-medium leading-snug text-claris-900">
                  {identity}
                </div>
              </div>
              <span className={`mt-2 inline-flex rounded-full border px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-[0.06em] ${
                reuse ? TONE_BOX.ready : "border-claris-200 bg-claris-50 text-claris-700"}`}>
                {reuse ? "Reuse" : creates ? "Create" : "—"}
              </span>
              {originallyCreated && (
                <p className="mt-2 text-[10.5px] leading-snug text-claris-600">
                  This request originally created it —{" "}
                  {original.outcome_code === "CREATE_PRODUCT"
                    ? "the product family did not exist"
                    : "the identity did not exist"} at the time.
                </p>
              )}
            </>
          ) : (
            <p className="text-[12.5px] leading-snug text-attention-fg">
              No canonical identity established. Nothing created.
            </p>
          )}
        </Stage>

        <Arrow />

        <Stage n={4} title="Legacy representations" tone="quiet">
          <div className="space-y-1">
            {TARGET_SYSTEMS.map((system) => (
              <div key={system}
                   className="flex items-center justify-between gap-2 rounded-md border border-dashed border-slate-300 bg-slate-50/60 px-2 py-1">
                <span className="font-mono text-[10.5px] text-slate-600">{system}</span>
                <span className="text-[10px] text-slate-400">Not established</span>
              </div>
            ))}
          </div>
          <p className="mt-2 text-[10.5px] leading-snug text-slate-400">
            {complete
              ? "Legacy mapping may be established where a target system " +
                "requires it. Those identifiers represent this configuration; " +
                "they are not business identities of their own."
              : "Not attempted — no canonical identity exists to project."}
          </p>
        </Stage>
      </div>
    </div>
  );
}

function Arrow() {
  return (
    <div className="flex items-center justify-center lg:w-8">
      <ArrowRight className="hidden h-5 w-5 text-claris-500 lg:block" />
      <ArrowDown className="h-5 w-5 text-claris-500 lg:hidden" />
    </div>
  );
}

/* ── 2. why this prevents proliferation ──────────────────────────────────*/
function ProliferationCard({ configurationsForProduct, avoided, complete }: {
  configurationsForProduct: number; avoided: number | null; complete: boolean;
}) {
  const claims = [
    "A new SKU does not automatically create a new business configuration.",
    "Requests are matched on governed business identity — product, geography, term and customer segment.",
    "Multiple legacy identifiers can represent the same canonical configuration.",
  ];
  return (
    <div className="rounded-xl border border-claris-200 bg-claris-50 p-5">
      <div className="mb-3 flex items-center gap-2">
        <ShieldCheck className="h-4 w-4 text-claris-600" />
        <h2 className="text-[14px] font-semibold text-claris-900">
          Why this prevents proliferation
        </h2>
      </div>
      <ul className="space-y-2.5">
        {claims.map((claim) => (
          <li key={claim} className="flex gap-2 text-[12.5px] leading-relaxed text-claris-900">
            <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ready-fg" />
            {claim}
          </li>
        ))}
      </ul>

      <div className="mt-4 space-y-2 border-t border-claris-200 pt-3.5">
        <div className="flex items-baseline justify-between gap-3">
          <span className="text-[12.5px] text-slate-600">
            Canonical configurations for this product
          </span>
          <b className="text-[18px] font-semibold text-claris-900">
            {configurationsForProduct}
          </b>
        </div>
        {complete && avoided !== null && (
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-[12.5px] text-slate-600">
              Unnecessary canonical configurations avoided
            </span>
            <b className="text-[18px] font-semibold text-ready-fg">{avoided}</b>
          </div>
        )}
        <p className="pt-1 text-[11px] leading-relaxed text-slate-500">
          A legacy-representation count is not shown: the deployed prototype
          does not record which legacy identifiers project from a
          configuration.
        </p>
      </div>
    </div>
  );
}

/* ── 3. canonical identity, and its legacy projections ───────────────────*/
function CanonicalIdentityCard({ facts }: { facts: IdentityFact[] }) {
  return (
    <Panel title="Canonical business identity"
           sub="The dimensions that decide whether two requests are the same commercial offering.">
      <div>
        {facts.map((fact) => (
          <Field key={fact.property} label={fact.label}>
            {fact.reported ? (
              <span className="inline-flex items-center gap-2">
                {fact.value}
                <ProvenanceChip provenance={fact.provenance} foldState="ESTABLISHED" />
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 text-attention-fg">
                <Minus className="h-3.5 w-3.5" /> Not reported
              </span>
            )}
          </Field>
        ))}
        <Field label="Configuration">
          <span className="font-normal text-slate-500">Relationship not established</span>
        </Field>
      </div>
    </Panel>
  );
}

function LegacyProjectionsCard({ complete }: { complete: boolean }) {
  const COLUMNS = ["Target system", "Identifier", "Status", "Reason"];
  return (
    <Panel title="Legacy system projections"
           sub="Identifiers a target system holds for this canonical configuration.">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[420px] text-[12.5px]">
          <thead>
            <tr className="border-b border-slate-200 text-left text-[11.5px] text-slate-500">
              {COLUMNS.map((c) => <th key={c} className="pb-2 pr-3 font-medium">{c}</th>)}
            </tr>
          </thead>
          <tbody>
            {complete ? TARGET_SYSTEMS.map((system) => (
              <tr key={system} className="border-b border-slate-100 last:border-0">
                <td className="py-2 pr-3 align-middle font-mono text-[11.5px] text-slate-700">
                  {system}
                </td>
                <td className="py-2 pr-3 align-middle text-slate-400">Not established</td>
                <td className="py-2 pr-3 align-middle">
                  <span className="rounded-full border border-dashed border-slate-300 px-2 py-0.5 text-[11px] text-slate-500">
                    Not established
                  </span>
                </td>
                <td className="py-2 align-middle text-[11.5px] text-slate-500">
                  Governed relationship not recorded
                </td>
              </tr>
            )) : (
              <tr>
                <td colSpan={COLUMNS.length} className="py-6 text-center text-[12.5px] text-slate-500">
                  No canonical identity exists, so no projection is attempted.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        <p className="mt-3 rounded-lg border border-dashed border-slate-300 bg-slate-50/60 p-3 text-[12px] leading-relaxed text-slate-600">
          <b className="font-semibold">Legacy mapping not established in governed state.</b>{" "}
          The canonical decision is established, but this prototype does not yet
          record the governed relationship to specific legacy identifiers.
        </p>
      </div>
      <div className="mt-3 flex items-start gap-2 rounded-lg bg-slate-50 p-3">
        <Link2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
        <p className="text-[11.5px] leading-relaxed text-slate-500">
          A target-model record is a projection per target system, target
          object type and target key. Whether it creates a new target identity
          is a separate question from whether the business configuration is
          new — which is the distinction this platform exists to keep.
        </p>
      </div>
    </Panel>
  );
}

/* ── 4. related requests ─────────────────────────────────────────────────
   The proliferation argument in one table: read down the identity columns and
   the duplicates are visible without anyone asserting them. */
function RelatedRequests({ subject, data }: {
  subject: PortfolioCase; data: WorkbenchData;
}) {
  const rows = relatedRequests(
    subject.id, data.properties.configuration_request ?? {}, data.decisions,
  );
  if (rows.length <= 1) return null;

  return (
    <Panel title="Related requests"
           sub="Several requests can resolve to fewer canonical business identities. The decision shown is the one each request received when it arrived.">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[680px] text-[12.5px]">
          <thead>
            <tr className="border-b border-slate-200 text-left text-[11.5px] text-slate-500">
              <th className="py-2 pr-3 font-medium">Request</th>
              {IDENTITY_DIMENSIONS.map((d) => (
                <th key={d.property} className="py-2 pr-3 font-medium">{d.label}</th>
              ))}
              <th className="py-2 font-medium">Decision</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}
                  className={`border-b border-slate-100 last:border-0 ${
                    row.isSelf ? "bg-claris-50/70" : ""}`}>
                <td className="py-2 pr-3 align-middle">
                  {row.isSelf
                    ? <b className="text-claris-900">{row.id}</b>
                    : <Link to={`/launches/${encodeURIComponent(row.id)}`}
                            className="text-claris-700 hover:underline">{row.id}</Link>}
                </td>
                {row.facts.map((fact) => (
                  <td key={fact.property} className="py-2 pr-3 align-middle">
                    {fact.reported
                      ? <span className="text-slate-700">{fact.value}</span>
                      : <span className="text-attention-fg">not reported</span>}
                  </td>
                ))}
                <td className="py-2 align-middle">
                  <span className={`inline-flex whitespace-nowrap rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${
                    row.outcomeCode === "NO_BUSINESS_CHANGE"
                      ? "border-ready-br bg-ready-bg text-ready-fg"
                      : row.outcomeCode === "CANNOT_DECIDE"
                        ? "border-attention-br bg-attention-bg text-attention-fg"
                        : "border-claris-200 bg-claris-50 text-claris-700"}`}>
                    {row.decision}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-[11.5px] leading-relaxed text-slate-400">
        Every requested identity in governed state. The platform's own
        comparison is the decision recorded against each request — this table
        lists them, it does not perform one.
      </p>
    </Panel>
  );
}

/* ── 5. when does a request become a new configuration? ──────────────────*/
function VariationExamples({ subject, data }: {
  subject: PortfolioCase; data: WorkbenchData;
}) {
  const examples = variantExamples(
    subject.id, subject.properties,
    data.properties.configuration_request ?? {}, data.decisions,
  );
  if (examples.length <= 1) return null;

  return (
    <Panel title="When does a request become a new configuration?"
           sub="Each card is a real request in governed state, with the decision it received. Change one identity-bearing dimension and the answer changes.">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {examples.map((example) => (
          <div key={example.requestId}
               className={`rounded-xl border p-4 ${
                 example.isSame ? "border-ready-br/50 bg-ready-bg/40"
                                : "border-attention-br/40 bg-attention-bg/30"}`}>
            <div className="mb-2.5 flex items-center gap-2">
              <span className={`inline-flex h-7 w-7 items-center justify-center rounded-full ${
                example.isSame ? "bg-ready-br/30 text-ready-fg" : "bg-attention-br/30 text-attention-fg"}`}>
                {example.isSame ? <Check className="h-4 w-4 font-bold" />
                                : <Plus className="h-4 w-4 font-bold" />}
              </span>
              <span className={`text-[12.5px] font-semibold ${
                example.isSame ? "text-ready-fg" : "text-attention-fg"}`}>
                {example.heading}
              </span>
            </div>
            <div className="text-[12px] leading-snug text-slate-700 font-medium">{example.identity}</div>
            <div className={`mt-3 inline-flex rounded-full border px-3 py-1.5 text-[10.5px] font-bold uppercase tracking-[0.05em] ${
              example.isSame ? "border-ready-br/50 bg-ready-bg/60 text-ready-fg"
                             : "border-attention-br/50 bg-attention-bg/60 text-attention-fg"}`}>
              {consequenceLabel(example.outcomeCode)}
            </div>
            <div className="mt-2.5 text-[10px] text-slate-500">
              {example.isSame
                ? "this request"
                : <Link to={`/launches/${encodeURIComponent(example.requestId)}`}
                        className="text-claris-600 hover:underline">{example.requestId}</Link>}
            </div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-[11.5px] leading-relaxed text-slate-400">
        Not every new configuration is proliferation. A different
        identity-bearing dimension represents a different commercial offering.
      </p>
    </Panel>
  );
}

/* ── 5. the boundary, stated once ────────────────────────────────────────*/
function BoundaryNote() {
  return (
    <div className="flex items-start gap-2.5 rounded-xl border border-slate-200 bg-slate-50/70 p-4">
      <Info className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
      <p className="text-[12px] leading-relaxed text-slate-600">
        <b className="font-semibold text-slate-700">Note.</b> Physical
        SKU/material proliferation in legacy systems may still occur where a
        target system requires it. Phase 1 prevents unnecessary proliferation
        in the <i>canonical</i> business model by distinguishing legacy
        identifiers from business configurations — it does not replace those
        systems or stop them creating rows of their own.
      </p>
    </div>
  );
}

/* ── the overview ────────────────────────────────────────────────────────*/
export default function ConfigurationCase({ subject, data, current, original, onTab }: {
  subject: PortfolioCase;
  data: WorkbenchData;
  current: GovernedDecision | undefined;
  original: GovernedDecision | undefined;
  onTab: (tab: "Evidence" | "Decision record") => void;
}) {
  const facts = identityFacts(subject.properties);
  const missing = missingDimensions(facts);
  const complete = missing.length === 0;
  const identity = fullIdentity(subject.properties);
  const launch = subject.properties.launch_reference;

  const product = subject.product;
  const configurationsForProduct = data.configurations
    .filter((c) => !product || c.product_id === product).length;
  const avoided = original?.outcome_code === "NO_BUSINESS_CHANGE" ? 1 : 0;

  return (
    <div className="space-y-4 px-5 py-6 lg:px-8">
      {/* identity resolution + why it prevents proliferation */}
      <div className="grid gap-4 lg:grid-cols-[1.9fr_.85fr]">
        <Panel title="Identity resolution"
               sub="How this request was evaluated, and what it maps to.">
          <IdentityResolution facts={facts} decision={current} original={original}
                              identity={identity} />
          {!complete && (
            <div className="mt-4">
              <ol className="flex flex-wrap items-center gap-2">
                {identityFlow(facts, current).map((step) => (
                  <li key={step.label}
                      className={`rounded-lg border px-3 py-1.5 text-[11.5px] ${TONE_BOX[step.tone]} ${
                        step.terminal ? "font-bold uppercase tracking-[0.05em]" : ""}`}>
                    {step.label}
                  </li>
                ))}
              </ol>
            </div>
          )}
          <p className="mt-3 text-[11px] leading-relaxed text-slate-400">
            A view of one governed decision, drawn from the identity facts and
            the stored outcome. These are not persisted workflow states, and no
            step here was executed as a task.
          </p>
        </Panel>

        <ProliferationCard configurationsForProduct={configurationsForProduct}
                           avoided={complete ? avoided : null} complete={complete} />
      </div>

      {!complete && (
        <div className="rounded-xl border border-attention-br bg-attention-bg p-4">
          <div className="flex items-center gap-2 text-[12px] font-bold uppercase tracking-[0.1em] text-attention-fg">
            <CircleDashed className="h-3.5 w-3.5" /> Nothing created
          </div>
          <p className="mt-2 text-[13px] leading-relaxed text-slate-700">
            No canonical identity was established, no configuration was
            created, no legacy projection was attempted, and no duplicate
            comparison was performed. The platform does not guess a missing
            identity dimension.
          </p>
        </div>
      )}

      {/* canonical identity + legacy projections */}
      <div className="grid gap-4 lg:grid-cols-2">
        <CanonicalIdentityCard facts={facts} />
        <LegacyProjectionsCard complete={complete} />
      </div>

      {/* the proliferation argument, and the teaching that follows it */}
      <RelatedRequests subject={subject} data={data} />
      {complete && <VariationExamples subject={subject} data={data} />}

      {/* relationships and the boundary */}
      <div className="grid gap-4 lg:grid-cols-[1.6fr_.9fr]">
        <BoundaryNote />
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="space-y-2">
            <Field label="Launch">
              {launch?.fold_state === "ESTABLISHED" && launch.value
                ? <Link to={`/launches/${encodeURIComponent(launch.value)}`}
                        className="text-claris-700 hover:underline">{launch.value}</Link>
                : <span className="font-normal text-slate-400">not recorded</span>}
            </Field>
            <Field label="Requested">{shortDate(subject.firstActivity)}</Field>
          </div>
          <div className="mt-3 flex flex-wrap gap-2 border-t border-slate-200 pt-3">
            <button type="button" onClick={() => onTab("Evidence")}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-[12.5px] font-medium text-slate-600 transition hover:border-slate-300">
              <Database className="h-3.5 w-3.5" /> View evidence
            </button>
            <button type="button" onClick={() => onTab("Decision record")}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-[12.5px] font-medium text-slate-600 transition hover:border-slate-300">
              <FileText className="h-3.5 w-3.5" /> View decision record
            </button>
          </div>
        </div>
      </div>

    </div>
  );
}
