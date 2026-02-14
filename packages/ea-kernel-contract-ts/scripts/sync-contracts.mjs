import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const packageRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(packageRoot, "../..");
const sourceDir = path.join(
  repoRoot,
  "packages",
  "ea-kernel",
  "docs",
  "reference",
  "contracts",
);
const targetDir = path.join(packageRoot, "contracts");

const files = [
  "kernel_schema.snapshot.json",
  "kernel_rules.snapshot.json",
  "kernel_judgment_vectors.snapshot.json",
];
const checkOnly = process.argv.includes("--check");

if (!fs.existsSync(sourceDir)) {
  throw new Error(`source contract directory not found: ${sourceDir}`);
}

fs.mkdirSync(targetDir, { recursive: true });
const outOfSync = [];
for (const file of files) {
  const source = path.join(sourceDir, file);
  const target = path.join(targetDir, file);
  if (!fs.existsSync(source)) {
    throw new Error(`source contract file not found: ${source}`);
  }
  if (checkOnly) {
    if (!fs.existsSync(target)) {
      outOfSync.push(file);
      continue;
    }

    const sourceRaw = fs.readFileSync(source, "utf8");
    const targetRaw = fs.readFileSync(target, "utf8");
    if (sourceRaw !== targetRaw) outOfSync.push(file);
    continue;
  }

  fs.copyFileSync(source, target);
}

if (checkOnly) {
  if (outOfSync.length > 0) {
    throw new Error(
      `[ea-kernel-contract-ts] out-of-sync contracts: ${outOfSync.join(", ")}`,
    );
  }
  console.log("[ea-kernel-contract-ts] contracts are in sync");
} else {
  console.log(`[ea-kernel-contract-ts] synced contracts from ${sourceDir}`);
}
