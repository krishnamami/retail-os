/**
 * The prototype chrome: dark rail, light content.
 *
 * Two primary destinations. Evidence is where a reader goes from a case when
 * they ask "why", not somewhere they navigate to cold, so it sits below the
 * divider with How it works rather than competing for attention at the top.
 *
 * No login, no role switch that changes permissions. "Viewing as Product
 * Manager" is a label describing whose questions the board answers -- it is
 * not authentication, and the header says so rather than implying a session.
 */
import { NavLink, Outlet } from "react-router-dom";
import { GitBranch, LayoutGrid, FileText, Database, UserRound }
  from "lucide-react";

import { ClarisMark } from "./ClarisMark";

const PRIMARY = [
  { to: "/launches", label: "Launches", icon: LayoutGrid, end: true },
  { to: "/configurations", label: "Configurations", icon: GitBranch },
];

const SECONDARY = [
  { to: "/about", label: "How it works", icon: FileText },
  { to: "/evidence", label: "Evidence explorer", icon: Database },
];

const LINK =
  "flex items-center gap-2.5 rounded-lg px-3 py-2 transition";

export default function AppShell() {
  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className="hidden w-[224px] shrink-0 flex-col bg-claris-900 px-4 py-5 lg:flex">
        <NavLink to="/" className="mb-7 px-2">
          <ClarisMark light />
        </NavLink>

        <nav className="flex flex-col gap-0.5">
          {PRIMARY.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={label} to={to} end={end}
              className={({ isActive }) =>
                `${LINK} text-[13.5px] ${
                  isActive
                    ? "bg-claris-700/70 font-semibold text-white"
                    : "text-claris-200 hover:bg-claris-800 hover:text-white"}`}>
              <Icon className="h-[15px] w-[15px]" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto">
          <div className="mb-2 border-t border-claris-800" />
          <nav className="flex flex-col gap-0.5">
            {SECONDARY.map(({ to, label, icon: Icon }) => (
              <NavLink key={label} to={to}
                className={({ isActive }) =>
                  `${LINK} text-[12.5px] ${
                    isActive
                      ? "bg-claris-800 font-medium text-white"
                      : "text-claris-300 hover:bg-claris-800 hover:text-claris-100"}`}>
                <Icon className="h-[14px] w-[14px]" />
                {label}
              </NavLink>
            ))}
          </nav>
          <p className="mt-3 px-3 text-[11px] leading-relaxed text-claris-400">
            Prototype. Governed state only — nothing here sends mail or writes
            to a source system.
          </p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-5 py-3 lg:px-8">
          <NavLink to="/" className="lg:hidden"><ClarisMark /></NavLink>
          <div className="hidden lg:block" />
          <span className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-1.5 text-[12.5px] text-slate-600">
            <UserRound className="h-[14px] w-[14px] text-claris-500" />
            Viewing as: <b className="font-semibold text-claris-900">Product Manager</b>
            <span className="text-slate-400">· no sign-in in this prototype</span>
          </span>
        </header>
        <main className="min-w-0 flex-1"><Outlet /></main>
      </div>
    </div>
  );
}
