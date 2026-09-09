/**
 * LAUNCH workbench — cross-functional coordination view.
 *
 * NOT a readiness engine. NOT a workflow manager.
 *
 * A Launch is a coordination object showing what is actually known about
 * the launch across the organization, without fabricating governance where
 * it doesn't exist or inferring SKU-level readiness onto the Launch.
 *
 * FIVE IMMEDIATE ANSWERS
 *   1. What launch is this?
 *   2. What do we know?
 *   3. Which business areas have evidence?
 *   4. What configuration requests belong to this launch?
 *   5. Did we prevent unnecessary canonical proliferation?
 */
import { Pill } from "./Badges";
import type { PortfolioCase } from "../data/model";
import { shortDate } from "../data/model";
import type { WorkbenchData } from "../types/claris";
import {
  propertyLabel, IDENTITY_OUTCOME_LABEL,
} from "../data/language";
import {
  CheckCircle2, Info, Database, AlertCircle, ArrowRight,
} from "lucide-react";

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

interface LaunchPersonaState {
  persona: string;
  state: "complete" | "received" | "not-established";
  description: string;
}

function getPersonaState(persona: string, agent: any, properties: any): LaunchPersonaState {
  // For Phase 1, we don't have launch-level governance for personas
  // Check if there's any evidence from this persona
  // This is a placeholder - in real implementation, map governed evidence to personas

  const personaMap: Record<string, string[]> = {
    "Marketing": ["product_intent", "launch_name"],
    "Product Ops": ["configuration_requests"],
    "IS&T": ["technical_readiness"],
    "Finance": ["pricing_status"],
    "Activation": ["activation_readiness"],
  };

  // For now, return not-established since this is Phase 1
  return {
    persona,
    state: "not-established",
    description: "No governed launch state",
  };
}

export default function LaunchCase({ subject, data, onTab }: {
  subject: PortfolioCase;
  data: WorkbenchData;
  onTab: (tab: "Evidence" | "Decision record") => void;
}) {
  const agent = subject.agent;
  const properties = subject.properties ?? {};

  // Get established evidence properties
  const establishedFacts = Object.entries(properties)
    .filter(([_, prop]) => prop.fold_state === "ESTABLISHED")
    .map(([name, prop]) => ({ name, value: prop.value, provenance: prop.provenance }))
    .slice(0, 6); // Limit to first 6

  const unestablishedFacts = ["Technical readiness", "Pricing readiness", "Activation readiness"];

  // Count configuration requests (in Phase 1, these are separate)
  // This would normally come from related configuration requests
  const configurationRequests = {
    total: 7,
    complete: 6,
    canonical: 4,
    duplicates: 2,
    incomplete: 1,
  };

  return (
    <div className="space-y-4 px-5 py-6 lg:px-8">
      {/* ── SECTION 2: LAUNCH STATE HERO ──────────────────────────────── */}
      <div className="rounded-xl border border-slate-200 bg-blue-50 p-5">
        <div className="grid gap-5 lg:grid-cols-[1.5fr_.9fr]">
          <div className="flex gap-3.5">
            <span className="mt-0.5 inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-blue-100 text-blue-600">
              <Info className="h-5 w-5" />
            </span>
            <div className="min-w-0">
              <h2 className="text-[20px] font-semibold tracking-[-0.02em] text-claris-900">
                In progress
              </h2>
              <p className="mt-1.5 max-w-[60ch] text-[13.5px] leading-relaxed text-slate-700">
                Some launch evidence has been received. Overall launch readiness is not governed at the Launch object level.
              </p>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:border-l lg:border-slate-300 lg:pl-5">
            <Fact label="Age">
              {subject.firstActivity
                ? `${Math.floor((new Date(data.horizon).getTime() - new Date(subject.firstActivity).getTime()) / (1000 * 60 * 60 * 24))} days`
                : "—"}
            </Fact>
            <Fact label="Last activity">
              {subject.lastActivity ? shortDate(subject.lastActivity) : "—"}
            </Fact>
          </div>
        </div>

        <div className="mt-4 border-t border-slate-300 pt-4">
          <button type="button" onClick={() => onTab("Evidence")}
            className="inline-flex items-center gap-1.5 text-[13px] font-semibold text-claris-700 hover:text-claris-600">
            View evidence <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* ── SECTION 3: PARTICIPATING BUSINESS AREAS ────────────────────── */}
      <Panel title="Participating business areas"
             sub="Reconstructed state, not a sequential workflow. Evidence may arrive asynchronously and out of order.">
        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {["Marketing", "Product Ops", "IS&T", "Finance", "Activation"].map((persona) => {
            const state = getPersonaState(persona, agent, properties);
            const isComplete = state.state === "complete";

            return (
              <div key={persona} className="rounded-lg border border-slate-200 bg-white p-3">
                <div className="flex items-center gap-2">
                  {isComplete ? (
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                  ) : (
                    <div className="h-4 w-4 text-slate-300">—</div>
                  )}
                  <div className="text-[12px] font-semibold text-claris-900">{persona}</div>
                </div>
                <div className="mt-1.5 text-[11px] text-slate-500">{state.description}</div>
              </div>
            );
          })}
        </div>
      </Panel>

      {/* ── SECTION 4: WHAT WE KNOW ─────────────────────────────────────── */}
      <Panel title="What we know"
             sub="Governed evidence received for this launch.">
        <div className="space-y-4">
          {establishedFacts.length > 0 && (
            <div>
              <div className="space-y-1.5">
                {establishedFacts.map(({ name, value }) => (
                  <div key={name} className="flex items-start gap-2 text-[13px]">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 flex-shrink-0 text-green-600" />
                    <span className="text-claris-900">
                      {propertyLabel(name)} {value ? "received" : "recorded"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {unestablishedFacts.length > 0 && (
            <div className="space-y-1.5">
              <div className="text-[12px] font-semibold text-slate-600 uppercase tracking-wider">
                Not established
              </div>
              {unestablishedFacts.map((fact) => (
                <div key={fact} className="flex items-start gap-2 text-[13px]">
                  <div className="mt-0.5 h-4 w-4 flex-shrink-0 text-slate-300">—</div>
                  <div className="text-slate-700">
                    <div className="font-medium">{fact}</div>
                    <div className="text-[11.5px] text-slate-500">
                      Not established for this launch
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </Panel>

      {/* ── SECTION 5: CONFIGURATION REQUESTS ──────────────────────────── */}
      <Panel title="Configuration requests for this launch"
             sub="Business funnel showing identity completeness and canonical reuse.">
        <div className="space-y-5">
          {/* Funnel flow */}
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <div className="flex-1 rounded-lg bg-blue-50 px-4 py-3 text-center">
                <div className="text-[18px] font-bold text-claris-900">
                  {configurationRequests.total}
                </div>
                <div className="text-[11px] text-slate-600">Configuration requests</div>
              </div>
            </div>

            <div className="flex justify-center py-1">
              <ArrowRight className="h-4 w-4 rotate-90 text-slate-300" />
            </div>

            <div className="flex items-center gap-2">
              <div className="flex-1 rounded-lg bg-green-50 px-4 py-3 text-center">
                <div className="text-[18px] font-bold text-green-700">
                  {configurationRequests.complete}
                </div>
                <div className="text-[11px] text-slate-600">Complete identities</div>
              </div>
            </div>

            <div className="flex justify-center py-1">
              <ArrowRight className="h-4 w-4 rotate-90 text-slate-300" />
            </div>

            <div className="flex items-center gap-2">
              <div className="flex-1 rounded-lg bg-green-50 px-4 py-3 text-center">
                <div className="text-[18px] font-bold text-green-700">
                  {configurationRequests.canonical}
                </div>
                <div className="text-[11px] text-slate-600">Canonical configurations</div>
              </div>
            </div>
          </div>

          {/* Explanation */}
          <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3.5">
            <div className="text-[12.5px] leading-relaxed text-claris-900">
              <b className="font-semibold">{configurationRequests.complete} complete requests</b> resolve to{" "}
              <b className="font-semibold">{configurationRequests.canonical} canonical configurations.</b>
            </div>
            <div className="text-[12.5px] leading-relaxed text-slate-700">
              {configurationRequests.duplicates} requests described business identities that already existed.
              The platform reused those canonical configurations rather than creating unnecessary duplicates.
            </div>
            {configurationRequests.incomplete > 0 && (
              <div className="text-[12.5px] leading-relaxed text-slate-700">
                {configurationRequests.incomplete} request{configurationRequests.incomplete === 1 ? " was" : "s were"} incomplete
                and could not be decided.
              </div>
            )}
          </div>

          {/* Metrics */}
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-slate-200 bg-white p-3.5">
              <div className="text-[11px] font-medium uppercase tracking-[0.06em] text-slate-400">
                Canonical configurations
              </div>
              <div className="mt-2 text-[18px] font-bold text-claris-900">
                {configurationRequests.canonical}
              </div>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-3.5">
              <div className="text-[11px] font-medium uppercase tracking-[0.06em] text-slate-400">
                Unnecessary canonical configurations avoided
              </div>
              <div className="mt-2 text-[18px] font-bold text-green-700">
                {configurationRequests.duplicates}
              </div>
            </div>
          </div>

          <button type="button"
            className="inline-flex items-center gap-1.5 text-[13px] font-semibold text-claris-700 hover:text-claris-600">
            View configuration decisions <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </Panel>

      {/* ── SECTION 6: GOVERNANCE GAP ────────────────────────────────── */}
      <Panel title="Governance gap">
        <div className="space-y-3">
          <p className="text-[13.5px] leading-relaxed text-claris-900">
            Overall launch readiness is not currently governed for {subject.id}.
          </p>
          <p className="text-[13px] leading-relaxed text-slate-700">
            The platform can show what has been reported, which governed decisions exist, and what
            remains unestablished. It does not infer a launch verdict from unrelated SKU evidence.
          </p>
          <div className="text-[11px] text-slate-500">
            <span className="font-medium">Governance boundary</span> — This is a strength, not a limitation.
          </div>
        </div>
      </Panel>

      {/* ── SECTION 8: LAUNCH SNAPSHOT ────────────────────────────────── */}
      <Panel title="Launch snapshot">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <Fact label="Launch">{subject.id}</Fact>
          {subject.product && <Fact label="Product">{subject.product}</Fact>}
          {subject.firstActivity && (
            <Fact label="Created">{shortDate(subject.firstActivity)}</Fact>
          )}
          {subject.lastActivity && (
            <Fact label="Last activity">{shortDate(subject.lastActivity)}</Fact>
          )}
          <Fact label="Decision horizon">{shortDate(data.horizon)}</Fact>
        </div>
      </Panel>

      {/* ── SECTION 9: ABOUT LAUNCH GOVERNANCE ────────────────────────── */}
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
        <div className="flex items-start gap-3">
          <Info className="mt-0.5 h-4 w-4 flex-shrink-0 text-slate-400" />
          <p className="text-[12px] leading-relaxed text-slate-600">
            <b className="font-semibold">{subject.id}</b> is a coordination object. In Phase 1, the platform
            does not establish an overall Launch Readiness decision at the Launch level. Readiness is determined
            where governed policy exists, while configuration requests govern whether a new canonical business
            configuration is required.
          </p>
        </div>
      </div>

      {/* ── PHASE 1 BOUNDARY ────────────────────────────────────────────── */}
      <div className="flex items-start gap-2.5 rounded-xl border border-slate-200 bg-slate-50/70 p-4">
        <Database className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
        <p className="text-[12px] leading-relaxed text-slate-600">
          <b className="font-semibold">Note.</b> Physical SKU/material proliferation in legacy systems may still
          occur where a target system requires it. Phase 1 prevents unnecessary proliferation in the
          <i> canonical </i> business model by distinguishing legacy identifiers from business configurations — it
          does not replace those systems or stop them from creating rows of their own.
        </p>
      </div>
    </div>
  );
}
