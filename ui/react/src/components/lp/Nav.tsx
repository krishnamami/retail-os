import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

import { ClarisMark } from "../ClarisMark";
import { Container } from "../primitives";
import { SECTIONS, scrollToSection } from "./anchors";
import type { SectionId } from "./anchors";

export default function Nav() {
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200/70 bg-white/85 backdrop-blur">
      <Container className="flex h-16 items-center justify-between">
        <ClarisMark />
        <nav className="hidden items-center gap-7 md:flex">
          {(Object.keys(SECTIONS) as SectionId[]).map((id) => (
            <button key={id} type="button" onClick={() => scrollToSection(id)}
              className="text-[13.5px] text-slate-600 transition hover:text-claris-700">
              {SECTIONS[id]}
            </button>
          ))}
        </nav>
        <Link to="/launches"
          className="inline-flex items-center gap-1.5 rounded-lg bg-claris-700 px-4 py-2 text-[13px] font-semibold text-white transition hover:bg-claris-600">
          Explore Prototype <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </Container>
    </header>
  );
}
