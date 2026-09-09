/**
 * Copies the governed dataset into public/data so the app can fetch it.
 *
 * The dataset is produced by workbench/collect.py from governed state. This
 * script only MOVES it -- it never derives, reshapes or fills anything, so
 * there is no second place where a governed number could be invented.
 *
 * A missing dataset is a warning rather than a build failure: the app renders
 * an explicit "dataset not found" state, which is more useful during a demo
 * than a build that will not start.
 */
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const source = resolve(here, "../../../out/workbench_data.json");
const target = resolve(here, "../public/data/workbench_data.json");

if (!existsSync(source)) {
  console.warn(
    `\n  governed dataset not found at ${source}\n` +
    `  run:  .\\venv\\Scripts\\python.exe workbench\\collect.py\n` +
    `  the app will start and show an explicit empty state.\n`,
  );
  process.exit(0);
}
mkdirSync(dirname(target), { recursive: true });
copyFileSync(source, target);
console.log(`  governed dataset synced -> public/data/workbench_data.json`);
