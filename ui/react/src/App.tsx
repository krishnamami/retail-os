/**
 * Routes.
 *
 * The landing page stands outside the app shell -- it is a public story, not a
 * screen inside the product. Everything under /launches shares the shell.
 */
import { Route, Routes } from "react-router-dom";

import AppShell from "./components/AppShell";
import LandingPage from "./pages/LandingPage";
import CommandCenter from "./pages/CommandCenter";
import CaseDetail from "./pages/CaseDetail";
import Configurations from "./pages/Configurations";
import EvidenceExplorer from "./pages/EvidenceExplorer";
import About from "./pages/About";
import NotFound from "./pages/NotFound";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route element={<AppShell />}>
        <Route path="/launches" element={<CommandCenter />} />
        <Route path="/launches/:caseId" element={<CaseDetail />} />
        <Route path="/configurations" element={<Configurations />} />
        <Route path="/evidence" element={<EvidenceExplorer />} />
        <Route path="/about" element={<About />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
