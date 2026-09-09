import { Check, HelpCircle, Plus } from "lucide-react";

import { Container, Eyebrow, H2, Section, Sub } from "../primitives";

const TODAY = [
  ["PROD-001 / NAMER / 36 / Enterprise", "SKU-001"],
  ["PROD-001 / NAMER / 48 / Enterprise", "SKU-002"],
  ["PROD-001 / APAC / 36 / Enterprise", "SKU-003"],
  ["PROD-001 / NAMER / 36 / SMB", "SKU-004"],
];

export default function Proliferation() {
  return (
    <Section id="approach" className="border-b border-slate-200 bg-slate-50">
      <Container>
        <Eyebrow>The SKU proliferation problem</Eyebrow>
        <H2>Same product. Different requests. Too many SKUs.</H2>
        <Sub className="mt-3 max-w-[62ch]">
          Every request that looks new gets treated as new. Some genuinely are.
          Telling those apart is a decision, and until now nothing made it.
        </Sub>

        <div className="mt-8 grid gap-4 lg:grid-cols-2">
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="text-[13px] font-semibold text-slate-600">Today</div>
            <div className="mt-3 space-y-2">
              {TODAY.map(([identity, sku]) => (
                <div key={sku}
                  className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 px-3 py-2 text-[12.5px]">
                  <span className="font-mono text-slate-600">{identity}</span>
                  <span className="text-slate-400">→</span>
                  <span className="font-semibold text-claris-900">{sku}</span>
                </div>
              ))}
              <div className="flex items-center justify-between gap-3 rounded-lg border border-blocked-br bg-blocked-bg px-3 py-2 text-[12.5px]">
                <span className="font-mono text-slate-600">
                  another NAMER / 36 / Enterprise request
                </span>
                <span className="text-slate-400">→</span>
                <span className="font-semibold text-blocked-fg">another SKU</span>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="text-[13px] font-semibold text-slate-600">
              With governed identity
            </div>
            <div className="mt-3 space-y-3">
              <div className="rounded-lg border border-ready-br bg-ready-bg p-3">
                <div className="flex items-center gap-2 text-[12.5px] font-semibold text-ready-fg">
                  <Check className="h-3.5 w-3.5" /> Duplicate business identity
                </div>
                <div className="mt-1 text-[12px] font-semibold text-slate-700">
                  Reuse existing
                </div>
                <div className="mt-1 text-[12.5px] text-slate-600">
                  Reuse the existing configuration.
                </div>
              </div>
              <div className="rounded-lg border border-claris-200 bg-claris-50 p-3">
                <div className="flex items-center gap-2 text-[12.5px] font-semibold text-claris-700">
                  <Plus className="h-3.5 w-3.5" /> Legitimate change · NAMER → APAC
                </div>
                <div className="mt-1 text-[12px] font-semibold text-slate-700">
                  Create configuration
                </div>
                <div className="mt-1 text-[12.5px] text-slate-600">
                  An identity-bearing dimension changed.
                </div>
              </div>
              <div className="rounded-lg border border-attention-br bg-attention-bg p-3">
                <div className="flex items-center gap-2 text-[12.5px] font-semibold text-attention-fg">
                  <HelpCircle className="h-3.5 w-3.5" /> Incomplete identity
                </div>
                <div className="mt-1 text-[12px] font-semibold text-slate-700">
                  Cannot decide
                </div>
                <div className="mt-1 text-[12.5px] text-slate-600">
                  A required input is missing. Nothing is created.
                </div>
              </div>
            </div>
          </div>
        </div>

        <p className="mt-5 max-w-[74ch] text-[13px] leading-relaxed text-slate-500">
          <b className="text-claris-900">What phase 1 claims.</b> It prevents
          unnecessary proliferation in the canonical business model, and makes
          legacy-driven proliferation visible and measurable. It does not remove
          physical SKU or material rows that already exist in legacy systems.
        </p>
      </Container>
    </Section>
  );
}
