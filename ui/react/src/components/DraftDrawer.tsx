/**
 * The suggested message, in a panel of its own.
 *
 * Drafts used to append to the page and, before that, to sit in the audit
 * record. Neither is where a person composing a message looks. This opens,
 * shows one message, and closes — and it says on its face that nothing was
 * sent, because a draft that looks sent is worse than no draft.
 */
import { useState } from "react";
import { Check, Copy, Mail, X } from "lucide-react";

import type { DraftMessage } from "../data/language";

export default function DraftDrawer({ draft, kind, onClose }: {
  draft: DraftMessage; kind: "message" | "note"; onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);

  const text = kind === "note"
    ? `Note on ${draft.regarding}\n\n${draft.body}`
    : `To: ${draft.toTeam}\nRegarding: ${draft.regarding}\n\n${draft.body}`;

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);   // a blocked clipboard is not an error worth shouting
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button type="button" aria-label="Close" onClick={onClose}
              className="absolute inset-0 bg-claris-900/25" />
      <aside className="relative flex h-full w-full max-w-[480px] flex-col bg-white shadow-2xl">
        <header className="flex items-center justify-between border-b border-slate-200 px-5 py-3.5">
          <div className="flex items-center gap-2">
            <Mail className="h-4 w-4 text-claris-500" />
            <h2 className="text-[14px] font-semibold text-claris-900">
              {kind === "note" ? "Suggested note" : "Suggested message"}
            </h2>
          </div>
          <button type="button" onClick={onClose}
                  className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600">
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {kind === "message" && (
            <div className="mb-4 space-y-1.5 border-b border-slate-100 pb-4 text-[13px]">
              <div className="flex gap-2">
                <span className="w-[76px] shrink-0 text-slate-400">To</span>
                <span className="font-medium text-claris-900">{draft.toTeam}</span>
              </div>
              <div className="flex gap-2">
                <span className="w-[76px] shrink-0 text-slate-400">Regarding</span>
                <span className="font-medium text-claris-900">{draft.regarding}</span>
              </div>
              <div className="flex gap-2">
                <span className="w-[76px] shrink-0 text-slate-400">Routed to</span>
                <span className="text-slate-600">
                  the <b className="font-medium text-claris-900">{draft.toRole}</b> role
                  — no individual is named
                </span>
              </div>
            </div>
          )}

          <p className="whitespace-pre-wrap text-[13.5px] leading-relaxed text-slate-700">
            {draft.body}
          </p>

          <p className="mt-5 rounded-lg border border-attention-br bg-attention-bg px-3 py-2 text-[12px] font-semibold uppercase tracking-[0.06em] text-attention-fg">
            Draft only — not sent
          </p>
          <p className="mt-2 text-[11.5px] leading-relaxed text-slate-500">
            Nothing here sends mail or writes to SAP, FileMaker, Salesforce or
            ww_pricing. Copy it if you want to send it yourself.
          </p>
        </div>

        <footer className="flex items-center gap-2 border-t border-slate-200 px-5 py-3.5">
          <button type="button" onClick={copy}
            className="inline-flex items-center gap-1.5 rounded-lg bg-claris-700 px-4 py-2 text-[13px] font-semibold text-white transition hover:bg-claris-600">
            {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? "Copied" : "Copy"}
          </button>
          <button type="button" onClick={onClose}
            className="rounded-lg border border-slate-200 px-4 py-2 text-[13px] font-medium text-slate-600 transition hover:border-slate-300">
            Close
          </button>
        </footer>
      </aside>
    </div>
  );
}
