import fs from "node:fs/promises";
import path from "node:path";
import { ImageResponse } from "next/og";

export const alt = "Adam Little builds agents";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const GROUND = "#0b0c0f";
const TEXT = "#ececf1";
const TEXT_MUTED = "#7b8194";
const TITLE = "Adam Little builds agents";
const SITE = "adambuilds.ai";
/**
 * Resolve the font through the package rather than `process.cwd()`, so it
 * holds wherever `geist` is hoisted. `package.json` is not in geist's exports
 * map, so resolve the exported `font/sans` entry (`dist/sans.js`) and walk to
 * `dist/fonts` from there. Turbopack rewrites any statically visible
 * `require.resolve` into a module id, so fetch Node's resolver through
 * `process.getBuiltinModule`, which the bundler leaves alone.
 */
function resolveGeistDist(): string {
  const { createRequire } = process.getBuiltinModule("node:module");
  return path.dirname(createRequire(import.meta.url).resolve("geist/font/sans"));
}

const FONT_FILE = path.join(resolveGeistDist(), "fonts/geist-sans/Geist-Medium.ttf");

export default async function OpenGraphImage() {
  const geist = await fs.readFile(FONT_FILE);
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: 80,
          background: GROUND,
          color: TEXT,
          fontFamily: "Geist",
        }}
      >
        <div style={{ fontSize: 96, lineHeight: 1.1, letterSpacing: "-0.02em" }}>{TITLE}</div>
        <div style={{ fontSize: 32, color: TEXT_MUTED }}>{SITE}</div>
      </div>
    ),
    {
      ...size,
      fonts: [{ name: "Geist", data: geist, weight: 500, style: "normal" }],
    },
  );
}
