/**
 * The challenge — one process, five teams, no shared answer.
 *
 * The persona flow leads, because it is the picture every stakeholder
 * recognises immediately. The comparison below it is deliberately short: two
 * paragraphs, no system diagram.
 */
import { Building2, ClipboardCheck, Cpu, Megaphone, Rocket } from "lucide-react";

import { Container, Eyebrow, H2, Section, Sub } from "../primitives";

const LANES = [
  { icon: Megaphone, team: "Marketing", work: "Product intent" },
  { icon: ClipboardCheck, team: "Product Operations", work: "Configuration" },
  { icon: Cpu, team: "IS&T", work: "Technical review" },
  { icon: Building2, team: "Finance", work: "Pricing & approval" },
  { icon: Rocket, team: "Activation", work: "Go live" },
];

export default function Bottlenecks() {
  return (
    <Section id="challenge" className="border-b border-slate-200 bg-white">
      <Container>
        <Eyebrow>The challenge</Eyebrow>
        <H2>A launch crosses five teams. One shared view.</H2>
        <Sub className="mt-3 max-w-[62ch]">
          The work is real and the people are capable. What is missing is a
          common decision state — so the same question gets asked five times and
          answered differently.
        </Sub>

        <div className="mt-9 flex flex-wrap items-start justify-center gap-2 sm:gap-3">
          {LANES.map(({ icon: Icon, team, work }, index) => (
            <div key={team} className="flex items-center gap-2 sm:gap-3">
              <div className="w-[132px] text-center">
                <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl border border-claris-200 bg-claris-50 text-claris-600">
                  <Icon className="h-5 w-5" />
                </span>
                <div className="mt-2 text-[13.5px] font-semibold text-claris-900">{team}</div>
                <div className="text-[11.5px] text-slate-500">{work}</div>
              </div>
              {index < LANES.length - 1 && (
                <span className="mt-[-30px] text-slate-300">→</span>
              )}
            </div>
          ))}
        </div>

        <p className="mt-6 text-center text-[13px] text-slate-500">
          One shared decision state across existing Claris systems.
        </p>

        <div className="mt-10 grid gap-4 lg:grid-cols-2">
          <div className="rounded-xl border border-blocked-br bg-blocked-bg p-5">
            <div className="text-[13px] font-semibold text-blocked-fg">Today</div>
            <p className="mt-2 text-[13.5px] leading-relaxed text-slate-700">
              Status is reconstructed from emails, spreadsheets and meetings.
              Each system holds part of the answer; none holds the decision.
            </p>
            <p className="mt-3 text-[13.5px] font-medium text-blocked-fg">
              Result: waiting, rework, unclear ownership, delayed launches.
            </p>
          </div>
          <div className="rounded-xl border border-ready-br bg-ready-bg p-5">
            <div className="text-[13px] font-semibold text-ready-fg">
              With a common decision state
            </div>
            <p className="mt-2 text-[13.5px] leading-relaxed text-slate-700">
              One view of where each launch stands, what is blocking it, and
              which team needs to act next.
            </p>
            <p className="mt-3 text-[13.5px] font-medium text-ready-fg">
              Built for real-world complexity. Simple to use.
            </p>
          </div>
        </div>
      </Container>
    </Section>
  );
}
