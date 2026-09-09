import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { HashRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import App from "./App";
import "./index.css";

/* HashRouter, not BrowserRouter: the build uses a relative base so the demo
   can be served from any path or opened directly, and a deep link must not
   depend on a server rewriting unknown paths to index.html. */

/* One snapshot of governed state per session: it is a fold at a fixed horizon,
   so refetching on focus would only re-read the same file. */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: false, retry: false, staleTime: Infinity },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <HashRouter>
        <App />
      </HashRouter>
    </QueryClientProvider>
  </StrictMode>,
);
