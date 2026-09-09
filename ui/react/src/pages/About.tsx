/**
 * How this works — the Q&A surface.
 *
 * Not part of the normal product flow. A business user should never need this
 * page; an architecture, security, governance or audit reviewer should never
 * be sent away from it. Collapsed by default so it reads as a list of
 * questions rather than a wall of policy.
 */
import { useState } from "react";
import { ChevronDown } from "lucide-react";

import DataGate from "../components/DataGate";
import PageHeader from "../components/PageHeader";
import { Pill } from "../components/Badges";
import type { WorkbenchData } from "../types/claris";

function Question({ q, children, open, onToggle }: {
  q: string; children: React.ReactNode; open: boolean; onToggle: () => void;
}) {
  return (
    <div className="border-b border-slate-200 last:border-0">
      <button type="button" onClick={onToggle}
        className="flex w-full items-center justify-between gap-3 py-4 text-left">
        <span className="text-[14px] font-semibold text-claris-900">{q}</span>
        <ChevronDown className={`h-4 w-4 shrink-0 text-slate-400 transition ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="space-y-2.5 pb-5 text-[13px] leading-relaxed text-slate-600">
          {children}
        </div>
      )}
    </div>
  );
}

function Body({ data }: { data: WorkbenchData }) {
  const [open, setOpen] = useState<string | null>("How decisions are governed");
  const toggle = (q: string) => setOpen((current) => (current === q ? null : q));
  const ask = (q: string) => ({ open: open === q, onToggle: () => toggle(q) });

  return (
    <>
      <PageHeader
        title="How this works"
        sub="The platform turns real-world events into governed decisions. These are the questions architecture, security, governance and audit ask before trusting one."
        horizon={data.horizon}
      />

      <div className="px-5 py-6 lg:px-8">
        <div className="max-w-[860px] rounded-xl border border-slate-200 bg-white px-5">
          <Question q="How decisions are governed" {...ask("How decisions are governed")}>
            <p>
              Policy reads governed state and produces an outcome. It never
              guesses: a required fact that is missing, or present but not
              asserted by a source, produces <b>Cannot decide</b> rather than a
              pass or a failure.
            </p>
            <p>
              Two classes of rule are stored and labelled.{" "}
              <Pill tone="ready">AUTHORITATIVE</Pill> is a rule Claris
              confirmed. <Pill tone="attention">PROTOTYPE_ASSUMPTION</Pill> is a
              rule this project wrote to make the demonstration coherent. The
              readiness policy used throughout is{" "}
              <code className="text-claris-700">READINESS-v1.0.0-PROTOTYPE</code>,
              stored as a prototype assumption and labelled as one on every
              decision it produces.
            </p>
          </Question>

          <Question q="Where evidence comes from" {...ask("Where evidence comes from")}>
            <p>
              Raw events from source systems project to evidence, evidence
              promotes to assertions, assertions fold to property state at a
              decision horizon, and policy reads that state. Nothing is entered
              by hand.
            </p>
            <p>
              Every value carries how it came to exist. <b>OBSERVED</b> — a
              source explicitly asserted it. <b>DEFAULTED</b> — projection logic
              supplied it because the source was silent about that fact.{" "}
              <b>DERIVED</b> — calculated from other governed facts. A folded
              property resting on any defaulted basis reports DEFAULTED: the
              weakest link wins.
            </p>
            <p>
              This snapshot: {data.totals.evidence} evidence rows across{" "}
              {data.totals.mappings} mappings — {data.totals.observed} observed,{" "}
              {data.totals.defaulted} defaulted — over {data.totals.subjects}{" "}
              subjects and {data.totals.property_states} property states, folded
              at <code className="text-claris-700">{data.horizon}</code> from{" "}
              <code className="text-claris-700">{data.generated_from}</code>.
            </p>
          </Question>

          <Question q="Security & authorization" {...ask("Security & authorization")}>
            <p>
              Production deployment integrates with Claris enterprise
              authentication and authorization. Authorization depends on the
              governed decision, its outcome and its subject — not on role
              alone.
            </p>
            <p>
              This prototype has <b>no sign-in and no identity management</b>.
              "Viewing as: Product Manager" is a label describing whose
              questions the board answers, not a session. Persona differences
              belong to authorization, which is why every team uses the same
              case screen rather than a dashboard of its own.
            </p>
          </Question>

          <Question q="What the Agent can do" {...ask("What the Agent can do")}>
            <p>
              The Launch Coordination Agent explains a governed outcome, routes
              to a responsible <em>role</em>, and drafts communications. It does
              not determine readiness, write evidence, or name an individual.
            </p>
            <p>
              Every actor identifier in this dataset is a simulation artefact,
              so no draft is addressed to a person. Ownership beyond role is an
              open question, and the agent says so rather than inventing an
              owner. Every action produces a draft; nothing is sent.
            </p>
          </Question>

          <Question q="Architecture" {...ask("Architecture")}>
            <p>
              Sources (SAP, FileMaker, ww_pricing, Salesforce, files and
              approvals) → evidence with provenance → business context (objects,
              relationships, resolved state) → governed decisions (identity,
              technical, pricing, launch readiness) → agent coordination →
              this experience. Governance, authorization, provenance, audit and
              versioning apply across every layer.
            </p>
            <p>
              Nothing replaces a source system. Evidence flows in; decisions and
              coordination flow out.
            </p>
          </Question>

          <Question q="Prototype boundaries" {...ask("Prototype boundaries")}>
            <ul className="ml-4 list-disc space-y-1">
              <li>No sign-in and no identity management.</li>
              <li>No launch creation. Nothing here mints a SKU or a configuration.</li>
              <li>No mail is sent. Every communication stays a draft.</li>
              <li>No write to SAP, FileMaker, Salesforce or ww_pricing.</li>
              <li>No evidence is entered by hand; it is reproduced from raw events.</li>
              <li>
                No case is launch-ready. The cases carrying pricing approval are
                not the cases carrying technical and activation confirmation, so
                readiness cannot be satisfied by any of them.
              </li>
              <li>
                Launches and changes are not related to each other. The raw
                events carry a launch identifier; no governed property records
                it, so the association is not asserted.
              </li>
              <li>
                The dataset is a snapshot. It does not refresh until the
                collector is run again.
              </li>
            </ul>
          </Question>
        </div>
      </div>
    </>
  );
}

export default function About() {
  return <DataGate>{(data) => <Body data={data} />}</DataGate>;
}
