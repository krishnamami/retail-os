/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system",
               "Segoe UI", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas",
               "monospace"],
      },
      colors: {
        /* Claris identity: a cool navy-blue, deliberately not AccordDental's
           green. The green there carries "approved / covered"; borrowing it
           would import a meaning this product does not have. */
        claris: {
          50:  "#EFF4FA", 100: "#DAE6F4", 200: "#B4CBE8", 300: "#84A9D6",
          400: "#5585BF", 500: "#3667A4", 600: "#275389", 700: "#1D416D",
          800: "#163152", 900: "#0F2137",
        },

        /* ── Governed outcome tones ───────────────────────────────────────
           Carried over from AccordDental as a PRINCIPLE, not a palette:
           a governed negative outcome is an answer, not an application error.

           ready      settled green   — evidenced and satisfied
           attention  amber           — a human is needed. CANNOT_DECIDE lives
                                        here, NOT in a red: the system is not
                                        failing, it is declining to guess
           blocked    muted clay      — an observed failure. Legible and
                                        serious, but visibly not the red a
                                        browser uses for a crash
           quiet      slate           — nothing has been reported. Absence is
                                        not a warning                       */
        ready:     { fg: "#0E6B4F", bg: "#E4F3EC", br: "#B7DECB" },
        attention: { fg: "#8A5A08", bg: "#FCF2DE", br: "#EFD9A8" },
        blocked:   { fg: "#98423A", bg: "#FBEDEB", br: "#EFCCC7" },
        quiet:     { fg: "#5A6472", bg: "#F1F3F6", br: "#DDE2E9" },
      },
      boxShadow: {
        card: "0 1px 2px rgba(15,33,55,.05), 0 1px 3px rgba(15,33,55,.06)",
        lift: "0 8px 24px -12px rgba(15,33,55,.28)",
      },
      keyframes: {
        "fade-in": { from: { opacity: "0", transform: "translateY(4px)" },
                     to:   { opacity: "1", transform: "translateY(0)" } },
      },
      animation: { "fade-in": "fade-in .22s ease" },
    },
  },
  plugins: [],
};
