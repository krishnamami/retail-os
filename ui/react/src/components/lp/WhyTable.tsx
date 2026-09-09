import { Container, Eyebrow, H2, Section, Sub } from "../primitives";
import { OutcomeBadge, ProvenanceChip } from "../Badges";

/**
 * The single most important idea on the page, shown as one worked row: a field
 * reads PASS and the platform still declines to call it approved. Everything
 * else here is context for that.
 */
export default function WhyTable() {
  return (
    <Section id="outcomes" className="border-b border-slate-200 bg-white">
      <Container>
        <Eyebrow>Outcomes</Eyebrow>
        <H2>Every decision can answer “why”.</H2>
        <Sub className="mt-3 max-w-[62ch]">
          Not a score, not a confidence percentage. The evidence it rested on,
          how that evidence came to exist, the policy applied, and what happens
          next.
        </Sub>

        <div className="mt-8 overflow-x-auto rounded-xl border border-slate-200">
          <table className="w-full min-w-[820px] text-[13px]">
            <thead className="bg-slate-50 text-left text-[12px] text-slate-500">
              <tr>
                <th className="px-4 py-2.5 font-medium">Source evidence</th>
                <th className="px-4 py-2.5 font-medium">Provenance</th>
                <th className="px-4 py-2.5 font-medium">Policy</th>
                <th className="px-4 py-2.5 font-medium">Governed decision</th>
                <th className="px-4 py-2.5 font-medium">Next action</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-t border-slate-200">
                <td className="px-4 py-4 align-top">
                  <div className="font-mono text-[12px] text-slate-500">
                    technical_approval_status
                  </div>
                  <div className="mt-1 text-[15px] font-semibold text-claris-900">PASS</div>
                </td>
                <td className="px-4 py-4 align-top">
                  <ProvenanceChip provenance="DEFAULTED" />
                  <div className="mt-1.5 text-[12px] leading-snug text-slate-500">
                    The source was silent. Projection logic supplied the value.
                  </div>
                </td>
                <td className="px-4 py-4 align-top text-slate-600">
                  Technical approval must be observed, not defaulted.
                </td>
                <td className="px-4 py-4 align-top">
                  <OutcomeBadge outcome="CANNOT_DECIDE" />
                  <div className="mt-1.5 text-[12px] leading-snug text-slate-500">
                    Not a failure. The platform declined to guess.
                  </div>
                </td>
                <td className="px-4 py-4 align-top text-slate-600">
                  Ask IS&amp;T to confirm the technical review explicitly.
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <p className="mt-4 max-w-[74ch] text-[13.5px] leading-relaxed text-slate-600">
          A field can display <b>PASS</b> and still be insufficient evidence that
          approval actually happened. Keeping those two apart is the difference
          between a dashboard and a decision.
        </p>
      </Container>
    </Section>
  );
}
