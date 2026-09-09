/**
 * Recommended next action, on Overview.
 *
 * The agent used to have a tab of its own, which put a recommendation on the
 * same footing as the governed decision. It is not on that footing: it reads
 * the decision and proposes a next step. So it sits inside the case, below the
 * decision that produced it, and says so in one line.
 *
 * Everything here was READ from a governed decision. The agent explains,
 * routes to a role and drafts; it never determines an outcome. The action
 * codes, the open question and the agent's own wording live in the reasoning
 * drawer, not on the primary surface.
 */
import { useState } from "react";
import { ChevronDown, Mail, Sparkles, StickyNote } from "lucide-react";

import { Pill } from "./Badges";
import { nextAction } from "../data/language";
import type { AgentCase, Draft } from "../types/claris";

export default function AgentPanel({ agent, drafts, onAction }: {
  agent: AgentCase;
  drafts: Draft[];
  onAction: (action: string) => void;
}) {
  const [reasoning, setReasoning] = useState(false);
  const action = nextAction(agent);
  const role = agent.waiting_on?.role ?? null;

  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-claris-200 bg-claris-50 p-4">
        <div className="mb-1.5 flex items-center gap-2 text-[12px] font-semibold text-claris-600">
          <Sparkles className="h-3.5 w-3.5" /> Recommended next action
        </div>
        <p className="text-[14.5px] font-medium leading-relaxed text-claris-900">
          {action?.statement ?? "No action is required."}
        </p>
        <p className="mt-1.5 text-[12px] leading-relaxed text-slate-500">
          The Agent recommends the next action based on the governed decision.
          It does not make the business decision.
        </p>

        <div className="mt-3.5 flex flex-wrap items-center gap-3">
          <button type="button" onClick={() => onAction("Draft Message")}
            className="inline-flex items-center gap-1.5 rounded-lg bg-claris-700 px-3.5 py-2 text-[12.5px] font-semibold text-white transition hover:bg-claris-600">
            <Mail className="h-3.5 w-3.5" /> Draft Message
          </button>
          <button type="button" onClick={() => onAction("Add Note")}
            className="rounded-lg border border-claris-200 bg-white px-3 py-2 text-[12.5px] font-medium text-claris-700 transition hover:border-claris-400">
            Add Note
          </button>
          <button type="button" onClick={() => setReasoning((v) => !v)}
            className="inline-flex items-center gap-1 text-[12.5px] text-claris-600 hover:text-claris-800">
            View reasoning
            <ChevronDown className={`h-3.5 w-3.5 transition ${reasoning ? "rotate-180" : ""}`} />
          </button>
        </div>

        {reasoning && (
          <div className="mt-3.5 space-y-2 border-t border-claris-200 pt-3.5 text-[12.5px] leading-relaxed text-slate-600">
            <p>{agent.recommendation?.statement ?? "No recommendation was produced."}</p>
            <div className="flex flex-wrap items-center gap-2 text-[11.5px]">
              <Pill tone="quiet">{action?.code ?? "NO_ACTION_REQUIRED"}</Pill>
              {role && <span>responsible role: <b className="text-claris-900">{role}</b></span>}
            </div>
            <p className="text-[11.5px] text-slate-500">
              Addressed to a role, never a person —{" "}
              {agent.waiting_on?.open_question ?? "ownership is not established"}.
              Every actor identifier in this dataset is a simulation artefact.
            </p>
          </div>
        )}
      </div>

      {drafts.length > 0 && (
        <div className="space-y-2.5">
          <div className="text-[12px] font-semibold uppercase tracking-[0.08em] text-slate-400">
            Drafts · not delivered anywhere
          </div>
          {drafts.map((draft) => (
            <div key={draft.communication_id}
                 className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="mb-1.5 flex flex-wrap items-center gap-2 text-[12px]">
                {draft.channel === "WORKBENCH_NOTE"
                  ? <StickyNote className="h-3.5 w-3.5 text-slate-400" />
                  : <Mail className="h-3.5 w-3.5 text-slate-400" />}
                <Pill tone="quiet">{draft.status}</Pill>
                {draft.to_role
                  ? <span className="text-slate-600">to <b>{draft.to_role}</b></span>
                  : <span className="text-slate-400">internal note</span>}
              </div>
              <div className="text-[13px] font-semibold text-claris-900">{draft.subject}</div>
              <pre className="mt-2 whitespace-pre-wrap font-mono text-[11.5px] leading-relaxed text-slate-600">
                {draft.body}
              </pre>
            </div>
          ))}
          <p className="text-[11.5px] text-slate-400">
            Nothing sends mail or writes to SAP, FileMaker, Salesforce or
            ww_pricing.
          </p>
        </div>
      )}
    </div>
  );
}
