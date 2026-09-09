import { Eye, FileSearch, KeyRound, ShieldCheck, UserCheck, HelpCircle }
  from "lucide-react";

import { Container, Eyebrow, H2, Section, Sub } from "../primitives";

const ITEMS = [
  { icon: KeyRound, title: "Role-based access",
    body: "Production deployment integrates with Claris enterprise " +
          "authentication and authorization. This prototype has no sign-in." },
  { icon: ShieldCheck, title: "Decision authorization",
    body: "Authorization depends on the governed decision, its outcome and its " +
          "subject — not on role alone." },
  { icon: Eye, title: "Evidence provenance",
    body: "Observed, defaulted and unreported stay distinguishable everywhere " +
          "they are shown." },
  { icon: UserCheck, title: "Human control",
    body: "Agents explain, coordinate and draft. Governed decision services " +
          "determine business outcomes." },
  { icon: FileSearch, title: "Audit and replay",
    body: "Evidence, policy version, decision and action history can be " +
          "reconstructed for any point in time." },
  { icon: HelpCircle, title: "Cannot decide",
    body: "Insufficient context stops progression safely instead of " +
          "fabricating certainty." },
];

export default function Governance() {
  return (
    <Section id="security" className="border-b border-slate-200 bg-slate-50">
      <Container>
        <Eyebrow>Governance &amp; security</Eyebrow>
        <H2>Built to be questioned.</H2>
        <Sub className="mt-3 max-w-[62ch]">
          The questions an enterprise asks before it trusts a decision layer,
          answered in the design rather than in a policy document.
        </Sub>
        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {ITEMS.map(({ icon: Icon, title, body }) => (
            <div key={title} className="rounded-xl border border-slate-200 bg-white p-4">
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-claris-50 text-claris-600">
                <Icon className="h-4 w-4" />
              </span>
              <div className="mt-2.5 text-[13.5px] font-semibold text-claris-900">{title}</div>
              <p className="mt-1 text-[12.5px] leading-relaxed text-slate-500">{body}</p>
            </div>
          ))}
        </div>
      </Container>
    </Section>
  );
}
