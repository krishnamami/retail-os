/**
 * In-page section links.
 *
 * WHY THESE ARE NOT href="#challenge"
 *   The app routes on the URL hash, so a fragment link does not scroll -- it
 *   REPLACES the route. Clicking "The Challenge" navigated to a route called
 *   "challenge", which does not exist, and the reader landed on Not Found.
 *
 *   So a section link scrolls the element into view itself and leaves the hash
 *   alone. The section ids stay exactly as they were; only the mechanism
 *   changed.
 */
export const SECTIONS = {
  challenge: "The Challenge",
  approach: "SKU Proliferation",
  outcomes: "Trusted Decisions",
  security: "Governance",
  architecture: "Architecture",
} as const;

export type SectionId = keyof typeof SECTIONS;

export function scrollToSection(id: string) {
  const target = document.getElementById(id);
  if (!target) return;
  const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  target.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
}
