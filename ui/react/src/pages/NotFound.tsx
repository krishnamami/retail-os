import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="px-5 py-16 lg:px-8">
      <h1 className="text-[21px] font-semibold text-claris-900">Nothing here</h1>
      <p className="mt-2 max-w-[520px] text-[13px] leading-relaxed text-slate-500">
        This prototype has a landing page, a launch command center, a decision
        workbench, configuration decisions and an evidence explorer. Nothing
        else is implemented.
      </p>
      <Link to="/launches"
            className="mt-4 inline-block text-[13px] text-claris-600 hover:underline">
        Go to the command center
      </Link>
    </div>
  );
}
