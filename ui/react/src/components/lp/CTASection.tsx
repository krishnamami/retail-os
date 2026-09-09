import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

import { Container, Section } from "../primitives";

export default function CTASection() {
  return (
    <Section className="bg-claris-900">
      <Container className="text-center">
        <h2 className="text-[26px] font-semibold tracking-[-0.02em] text-white sm:text-[30px]">
          The complete story in one experience.
        </h2>
        <p className="mx-auto mt-3 max-w-[58ch] text-[15px] leading-relaxed text-claris-200">
          From business problem to governed decision — with real evidence, real
          outcomes, and a clear path forward.
        </p>
        <Link to="/launches"
          className="mt-7 inline-flex items-center gap-2 rounded-lg bg-white px-5 py-2.5 text-sm font-semibold text-claris-900 transition hover:bg-claris-50">
          Explore Prototype <ArrowRight className="h-4 w-4" />
        </Link>
        <p className="mt-8 text-[13px] italic text-claris-300">
          “Not just more data. Better decisions.”
        </p>
      </Container>
    </Section>
  );
}
