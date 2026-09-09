/** Wordmark. A ring with a resolved centre -- scattered inputs, one state. */
export function ClarisMark({ className = "", light = false }: {
  className?: string; light?: boolean;
}) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <svg viewBox="0 0 24 24" aria-hidden className="h-[22px] w-[22px]">
        <circle cx="12" cy="12" r="9.5" fill="none" strokeWidth="1.6"
                stroke={light ? "#B4CBE8" : "#275389"} />
        <circle cx="12" cy="12" r="3.4" fill={light ? "#FFFFFF" : "#0F2137"} />
      </svg>
      <span className={`text-[15px] font-semibold tracking-[-0.01em] ${
        light ? "text-white" : "text-claris-900"}`}>Claris</span>
    </span>
  );
}
