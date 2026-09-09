import { Container, Eyebrow, H2, Section, Sub } from "../primitives";

const LAYERS = [
  { title: "Sources", lines: ["SAP", "FileMaker / all_skus", "ww_pricing", "Salesforce", "Files & APIs"] },
  { title: "Evidence", lines: ["Governed facts", "with provenance"] },
  { title: "Business context", lines: ["Objects", "Relationships", "Assertions", "Resolved state"] },
  { title: "Governed decisions", lines: ["Identity", "Technical readiness", "Pricing readiness", "Launch readiness"] },
  { title: "Agent coordination", lines: ["Explain", "Coordinate", "Recommend", "Draft"] },
  { title: "Experience", lines: ["Common Decision", "Workbench"] },
];

export default function Architecture() {
  return (
    <Section id="architecture" className="border-b border-slate-200 bg-white">
      <Container>
        <Eyebrow>Architecture</Eyebrow>
        <H2>Works with the systems Claris already runs.</H2>
        <Sub className="mt-3 max-w-[62ch]">
          Nothing here replaces a source system. Evidence flows in; decisions
          and coordination flow out.
        </Sub>

        <div className="mt-8 overflow-x-auto">
          <div className="flex min-w-[900px] items-stretch gap-2">
            {LAYERS.map((layer, index) => (
              <div key={layer.title} className="flex flex-1 items-center gap-2">
                <div className="h-full flex-1 rounded-xl border border-slate-200 bg-white p-4">
                  <div className="text-[13px] font-semibold text-claris-900">
                    {layer.title}
                  </div>
                  <ul className="mt-2 space-y-1">
                    {layer.lines.map((line) => (
                      <li key={line} className="text-[12px] leading-snug text-slate-500">
                        {line}
                      </li>
                    ))}
                  </ul>
                </div>
                {index < LAYERS.length - 1 && (
                  <span className="text-slate-300">→</span>
                )}
              </div>
            ))}
          </div>
          <div className="mt-2 min-w-[900px] rounded-xl border border-claris-200 bg-claris-50 px-4 py-2.5 text-center text-[12.5px] font-medium text-claris-700">
            Governance · Authorization · Provenance · Audit · Versioning —
            across every layer
          </div>
        </div>
      </Container>
    </Section>
  );
}
