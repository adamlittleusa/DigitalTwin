#!/usr/bin/env node
// Verifies every internal href in the built HTML maps to a page that was built.
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

const APP_DIR = path.join(process.cwd(), ".next/server/app");

async function listHtmlFiles(dir) {
  const entries = await readdir(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await listHtmlFiles(full)));
    } else if (entry.name.endsWith(".html")) {
      files.push(full);
    }
  }
  return files;
}

function fileToRoute(file) {
  let rel = path.relative(APP_DIR, file).replace(/\\/g, "/");
  rel = rel.replace(/\.html$/, "");
  if (rel === "index") return "/";
  if (rel.endsWith("/index")) rel = rel.slice(0, -"/index".length);
  return "/" + rel;
}

const htmlFiles = (await listHtmlFiles(APP_DIR)).filter(
  (f) => !path.basename(f).startsWith("_") && !f.includes("[")
);

const builtRoutes = new Set(htmlFiles.map(fileToRoute));

const hrefPattern = /href="(\/[^"]*)"/g;
const missing = [];
let checked = 0;

for (const file of htmlFiles) {
  const html = await readFile(file, "utf8");
  for (const match of html.matchAll(hrefPattern)) {
    let href = match[1];
    if (href.startsWith("/_next/") || href.startsWith("/opengraph-image")) continue;
    href = href.split("#")[0].split("?")[0];
    if (href === "" || href === "/favicon.ico") continue;
    checked += 1;
    if (!builtRoutes.has(href)) missing.push({ from: fileToRoute(file), href });
  }
}

if (missing.length > 0) {
  console.error(`Link check failed: ${missing.length} broken internal link(s):`);
  for (const { from, href } of missing) console.error(`  ${from} -> ${href}`);
  process.exit(1);
}

console.log(`Link check passed: ${checked} internal link(s) checked across ${htmlFiles.length} page(s).`);
