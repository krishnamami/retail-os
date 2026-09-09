/**
 * Decision & Handoff Journey.
 *
 * NOT a workflow. The five lanes are the teams a launch touches, and a lane's
 * state is read from the evidence and governed findings that exist for this
 * subject right now. Evidence arrives late and out of order — a lane can be
 * complete while the one before it is silent, and the rail draws that rather
 * than hiding it behind a sequence.
 *
 * One business state and one line of context per lane. The counts this used
 * to carry ("1 of 2 reported") were the platform's bookkeeping, not the
 * reader's question, and they live in Evidence.
 */
import { AlertTriangle, Check, CircleDashed, Clock, HelpCircle, Info, Minus }
  from "lucide-react";

import { LANE_TONE } from "../data/model";
import type { Lane, LaneStatus, PortfolioCase } from "../data/model";
import { laneSubtext } from "../data/language";
import { Pill } from "./Badges";

const ICON: Record<LaneStatus, typeof Check> = {
  complete: Check,
  "needs-confirmation": HelpCircle,
  "in-progress": Clock,
  "not-started": CircleDashed,
  rejected: AlertTriangle,
  "not-established": Minus,
};

const RING: Record<LaneStatus, string> = {
  complete: "border-ready-br bg-ready-bg text-ready-fg",
  "needs-confirmation": "border-attention-br bg-attention-bg text-attention-fg",
  "in-progress": "border-claris-200 bg-claris-50 text-claris-600",
  "not-started": "border-quiet-br bg-quiet-bg text-quiet-fg",
  rejected: "border-blocked-br bg-blocked-bg text-blocked-fg",
  "not-established": "border-dashed border-slate-300 bg-white text-slate-400",
};

export default function JourneyRail({ lanes, subject }: {
  lanes: Lane[]; subject: PortfolioCase;
}) {
  return (
    <div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
        {lanes.map((lane) => {
          const Icon = ICON[lane.status];
          return (
            <div key={lane.persona}
                 className="flex flex-col rounded-xl border border-slate-200 bg-white p-3 text-center">
              <div className={`mx-auto mb-2 inline-flex h-8 w-8 items-center justify-center rounded-full border ${RING[lane.status]}`}>
                <Icon className="h-4 w-4" />
              </div>
              <div className="text-[12.5px] font-semibold leading-tight text-claris-900">
                {lane.persona}
              </div>
              <Pill tone={LANE_TONE[lane.status]} className="mx-auto mt-1.5 !text-[10.5px]">
                {lane.label}
              </Pill>
              <div className="mt-1.5 text-[10.5px] leading-snug text-slate-500">
                {laneSubtext(lane, subject)}
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-3 flex items-start gap-2 rounded-lg bg-claris-50 px-3 py-2.5">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-claris-500" />
        <p className="text-[11.5px] leading-relaxed text-slate-600">
          Reconstructed decision state, not a sequential workflow. Evidence may
          arrive asynchronously and out of order, so a lane can be complete
          while an earlier one has reported nothing.
        </p>
      </div>
    </div>
  );
}
