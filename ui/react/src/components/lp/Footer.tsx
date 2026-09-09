import { ClarisMark } from "../ClarisMark";
import { Container } from "../primitives";

export default function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-white py-8">
      <Container className="flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
        <ClarisMark />
        <p className="text-[12px] text-slate-500">
          Prototype. Governed state only — no sign-in, no outbound mail, no
          writes to any source system.
        </p>
      </Container>
    </footer>
  );
}
