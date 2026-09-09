/**
 * Hero — why should I care, answered in under sixty seconds.
 *
 * The architecture stack used to sit here, five boxes deep, before a reader
 * had any reason to care how it is built. It now lives further down the page,
 * where someone who has already understood the problem can ask how it works.
 */
import { Link } from "react-router-dom";
import { ArrowRight, Clock, Layers, ShieldCheck } from "lucide-react";

import { Container } from "../primitives";

const VALUE = [
  { icon: Clock, title: "Reduce launch delays",
    detail: "Find what is blocking progress and which team needs to act." },
  { icon: Layers, title: "Prevent SKU proliferation",
    detail: "Reuse existing business identities instead of creating unnecessary configurations." },
  { icon: ShieldCheck, title: "Govern every decision",
    detail: "Every outcome can explain why it happened." },
];

export default function Hero() {
  return (
    <section className="border-b border-slate-200 bg-gradient-to-b from-claris-50 to-white">
      <Container className="grid gap-10 py-16 lg:grid-cols-[1.1fr_.9fr] lg:items-center lg:py-20">
        <div>
          <div className="mb-4 text-[11px] font-bold uppercase tracking-[0.16em] text-claris-500">
            From fragmented launches to governed decisions
          </div>
          <h1 className="max-w-[19ch] text-[36px] font-semibold leading-[1.1] tracking-[-0.03em] text-claris-900 sm:text-[44px]">
            Know where every product launch stands, what's blocking it, and
            what decision is needed next.
          </h1>
          <p className="mt-5 max-w-[54ch] text-[16px] leading-relaxed text-slate-600">
            Claris gives teams a shared, governed view of product launches and
            changes so everyone is working from the same facts rather than
            reconstructing status from spreadsheets, meetings and systems.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <Link to="/launches"
              className="inline-flex items-center gap-2 rounded-lg bg-claris-700 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-claris-600">
              Explore Prototype <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>

        <div className="rounded-2xl border border-claris-200 bg-claris-900 p-8 text-right shadow-card">
          <p className="text-[26px] font-semibold leading-[1.25] tracking-[-0.02em] text-white sm:text-[30px]">
            Same product.<br />Fewer delays.<br />Clearer decisions.
          </p>
          <p className="mt-4 text-[13px] leading-relaxed text-claris-200">
            One shared decision state across the systems Claris already runs.
          </p>
        </div>
      </Container>

      <Container className="grid gap-3 pb-16 sm:grid-cols-3">
        {VALUE.map(({ icon: Icon, title, detail }) => (
          <div key={title} className="rounded-xl border border-slate-200 bg-white p-5 shadow-card">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-claris-50 text-claris-600">
              <Icon className="h-[18px] w-[18px]" />
            </span>
            <div className="mt-3 text-[15px] font-semibold leading-snug text-claris-900">
              {title}
            </div>
            <div className="mt-1.5 text-[13px] leading-relaxed text-slate-500">
              {detail}
            </div>
          </div>
        ))}
      </Container>
    </section>
  );
}
