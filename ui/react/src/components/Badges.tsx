/**
 * Every coloured token in the product.
 *
 * Tone is derived from the VALUE, never passed in at a call site -- the same
 * discipline AccordDental applies to its signals. A call site that could
 * choose its own colour is a call site that will eventually paint
 * CANNOT_DECIDE red.
 *
 * WHY CANNOT_DECIDE IS AMBER AND NOT_READY IS CLAY
 *   A governed negative outcome is an answer, not an application error.
 *   CANNOT_DECIDE means the platform declined to guess -- that is the product
 *   working, so it reads as "needs a human", not as a fault. NOT_READY is a
 *   real negative and is legible as one, in a muted clay rather than the red
 *   a browser uses for a crash.
 */
import type { ReactNode } from "react";

import { OUTCOME_LABEL, toneForOutcome, toneForProvenance } from "../data/model";
import type { Tone } from "../data/model";

const TONE: Record<Tone, string> = {
  ready: "bg-ready-bg text-ready-fg border-ready-br",
  attention: "bg-attention-bg text-attention-fg border-attention-br",
  blocked: "bg-blocked-bg text-blocked-fg border-blocked-br",
  quiet: "bg-quiet-bg text-quiet-fg border-quiet-br",
};

export function Pill({ tone, children, className = "", title }: {
  tone: Tone; children: ReactNode; className?: string; title?: string;
}) {
  return (
    <span title={title}
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11.5px] font-semibold ${TONE[tone]} ${className}`}>
      {children}
    </span>
  );
}

/** A governed outcome, in business words with the code kept for reference. */
export function OutcomeBadge({ outcome, label, className = "" }: {
  outcome: string; label?: string; className?: string;
}) {
  return (
    <Pill tone={toneForOutcome(outcome)} title={outcome} className={className}>
      {label ?? OUTCOME_LABEL[outcome] ?? outcome}
    </Pill>
  );
}

/**
 * How a value came to exist. The distinction the whole platform rests on:
 * a field can read PASS and still be insufficient evidence that approval
 * happened, and these three tokens are where a reader sees that.
 */
export function ProvenanceChip({ provenance, foldState, className = "" }: {
  provenance?: string | null; foldState?: string | null; className?: string;
}) {
  if (foldState && foldState !== "ESTABLISHED") {
    return (
      <Pill tone="quiet" className={className}
        title="No source has reported a value for this property">
        UNREPORTED
      </Pill>
    );
  }
  const title = provenance === "DEFAULTED"
    ? "Projection logic supplied this value because the source was silent"
    : provenance === "OBSERVED"
      ? "A source explicitly asserted this value"
      : "Calculated from other governed facts";
  return (
    <Pill tone={toneForProvenance(provenance)} className={className} title={title}>
      {provenance ?? "UNREPORTED"}
    </Pill>
  );
}
