/**
 * Shared building blocks.
 *
 * One file so a dozen sections cannot drift apart on container width, type
 * scale or button shape -- the pattern AccordDental uses, and the reason its
 * landing page reads as one document rather than twelve.
 */
import type { ReactNode } from "react";

export function Container({ children, className = "" }: {
  children: ReactNode; className?: string;
}) {
  return (
    <div className={`mx-auto w-full max-w-[1200px] px-5 sm:px-8 ${className}`}>
      {children}
    </div>
  );
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <div className="mb-3 text-[11px] font-bold uppercase tracking-[0.16em] text-claris-500">
      {children}
    </div>
  );
}

export function H2({ children, className = "" }: {
  children: ReactNode; className?: string;
}) {
  return (
    <h2 className={`text-[26px] font-semibold leading-[1.18] tracking-[-0.02em] text-claris-900 sm:text-[31px] ${className}`}>
      {children}
    </h2>
  );
}

export function Sub({ children, className = "" }: {
  children: ReactNode; className?: string;
}) {
  return (
    <p className={`text-[15px] leading-relaxed text-slate-500 ${className}`}>
      {children}
    </p>
  );
}

export function Section({ id, children, className = "" }: {
  id?: string; children: ReactNode; className?: string;
}) {
  return (
    <section id={id} className={`py-16 sm:py-20 ${className}`}>{children}</section>
  );
}

export function Card({ children, className = "" }: {
  children: ReactNode; className?: string;
}) {
  return (
    <div className={`rounded-xl border border-slate-200 bg-white shadow-card ${className}`}>
      {children}
    </div>
  );
}

const BTN =
  "inline-flex items-center justify-center gap-2 rounded-lg px-5 py-2.5 " +
  "text-sm font-semibold transition";

export function PrimaryButton({ children, onClick, href, className = "" }: {
  children: ReactNode; onClick?: () => void; href?: string; className?: string;
}) {
  const cls = `${BTN} bg-claris-700 text-white hover:bg-claris-600 ${className}`;
  return href
    ? <a href={href} className={cls}>{children}</a>
    : <button type="button" onClick={onClick} className={cls}>{children}</button>;
}

export function GhostButton({ children, onClick, href, className = "" }: {
  children: ReactNode; onClick?: () => void; href?: string; className?: string;
}) {
  const cls = `${BTN} border border-claris-200 bg-white text-claris-700 hover:border-claris-400 ${className}`;
  return href
    ? <a href={href} className={cls}>{children}</a>
    : <button type="button" onClick={onClick} className={cls}>{children}</button>;
}
