import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The governed dataset is served as a static file from public/data rather
// than bundled: it is half a megabyte, it changes whenever collect.py runs,
// and rebuilding the app to refresh data would be the wrong dependency.
//
// base is relative so the built app also opens from the filesystem, which is
// how the demo is most likely to be shown.
export default defineConfig({
  base: "./",
  plugins: [react()],
  server: { port: 5174, open: true },
  build: { outDir: "dist", cssTarget: ["chrome87", "safari14", "firefox78"] },
});
