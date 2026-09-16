// The network table as the application shows it, written out for Mike.
//
//   deno run --allow-net --allow-read --allow-write Contents/tools/export-network-table.ts
//
// Asks the running haversack server (127.0.0.1:8790) about every task, derives the body region
// the way the network browser does (Contents/src/SlicerLive/logic/anatomy/regions.ts), and writes
// Contents/docs/networks-<date>.json and .csv. The region is Albula's inference, not haversack's fact;
// the file says so per row. Ron, 2026-09-11: "prepare a file for mike with the information that
// we assembled into the network browser."
import { regionsOfStructures, regionsOfTaskName } from "../src/SlicerLive/logic/anatomy/regions.ts";
import { paperFor } from "../src/SlicerLive/logic/anatomy/model-papers.ts";

const BASE = "http://127.0.0.1:8790/v1";
const health = await fetch(`${BASE}/health`).then((r) => r.json());
const tasks: string[] = (await fetch(`${BASE}/tasks`).then((r) => r.json())).tasks;

const rows = [];
for (const name of tasks) {
  const d = await fetch(`${BASE}/tasks/${encodeURIComponent(name)}`).then((r) => r.ok ? r.json() : null);
  const structures: string[] = d?.structures ?? [];
  const derived = structures.length ? regionsOfStructures(structures) : null;
  const regions = derived ? derived.regions : regionsOfTaskName(name);
  const eco = name.split(":")[0];
  const paper = paperFor(name);
  rows.push({
    name,
    family: paper?.name ?? eco,
    modality: d?.modality ?? null,
    regions,
    region_source: derived ? "derived from the structure names" : regions.length ? "derived from the task name (no structure list)" : "unknown",
    structures_unplaced_by_region_table: derived?.unknown ?? null,
    n_structures: d?.n_structures ?? (structures.length || null),
    structures,
    networks_run: Array.isArray(d?.weights) ? d.weights.length : null,
    engine: d?.engine ?? null,
    weights_installed_here: Array.isArray(d?.weights_installed) && d.weights_installed.length ? d.weights_installed.every((w: { installed?: boolean }) => w.installed === true) : null,
    paper: paper ? { title: paper.title, doi: paper.doi, url: paper.url } : null,
  });
}
const date = new Date().toLocaleDateString("sv");   // YYYY-MM-DD, local day, not UTC
const out = {
  written: new Date().toISOString(),
  from: `haversack ${health.version} on this machine, ${tasks.length} tasks`,
  note: "regions is Albula's inference (Head, Neck, Thorax, Abdomen, Pelvis, Spine, Limbs, Whole body) from the structure names, or from the task name when a task lists no structures; region_source says which. Not a haversack field. See Contents/docs/for-mike-2026-09-11.md.",
  tasks: rows,
};
await Deno.writeTextFile(`Contents/docs/networks-${date}.json`, JSON.stringify(out, null, 2) + "\n");
const esc = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
const csv = ["name,family,modality,regions,region_source,n_structures,networks_run,engine,weights_installed_here,paper_doi,structures"]
  .concat(rows.map((r) => [r.name, r.family, r.modality, r.regions.join("; "), r.region_source, r.n_structures, r.networks_run, r.engine, r.weights_installed_here, r.paper?.doi, r.structures.join("; ")].map(esc).join(",")))
  .join("\n") + "\n";
await Deno.writeTextFile(`Contents/docs/networks-${date}.csv`, csv);
console.log(`${rows.length} tasks → Contents/docs/networks-${date}.json and .csv`);
