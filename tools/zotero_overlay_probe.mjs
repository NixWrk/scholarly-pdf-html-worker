#!/usr/bin/env node

/* globals process */

import { access, mkdir, readFile, writeFile } from "fs/promises";
import { basename, dirname, extname, join, resolve, sep } from "path";
import { pathToFileURL } from "url";

const SCRIPT_DIR = import.meta.dirname;
const DEFAULT_PDFJS_DIR = resolve(
  SCRIPT_DIR,
  "..",
  ".tmp_local2",
  "vendor",
  "zotero-pdfjs"
);

function usage() {
  console.error(
    [
      "Usage:",
      "  node tools/zotero_overlay_probe.mjs <input.pdf> [--out <overlays.json>] [--pdfjs-dir <zotero-pdfjs>] [--build generic-legacy]",
      "",
      "The Zotero/pdf.js generic-legacy build must exist in <zotero-pdfjs>:",
      "  npx.cmd gulp generic-legacy",
    ].join("\n")
  );
}

function parseArgs(argv) {
  let input = null;
  let out = null;
  let buildName = "generic-legacy";
  let pdfjsDir = process.env.Z2M_ZOTERO_PDFJS_DIR || DEFAULT_PDFJS_DIR;

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "--out") {
      out = argv[++i];
    } else if (arg === "--build") {
      buildName = argv[++i];
    } else if (arg === "--pdfjs-dir") {
      pdfjsDir = argv[++i];
    } else if (arg === "--pretty" || arg === "--no-futyma-check") {
      // Accepted for compatibility with the temporary research probe.
    } else if (arg === "--help" || arg === "-h") {
      usage();
      process.exit(0);
    } else if (!input) {
      input = arg;
    } else {
      throw new Error(`Unexpected argument: ${arg}`);
    }
  }

  if (!input) {
    usage();
    process.exit(2);
  }

  return { input, out, buildName, pdfjsDir: resolve(pdfjsDir) };
}

function toPdfjsResourceDir(pdfjsDir, ...parts) {
  return `${resolve(pdfjsDir, ...parts).replaceAll(sep, "/")}/`;
}

async function loadPdfjs(pdfjsDir, buildName) {
  const buildDir = join(pdfjsDir, "build", buildName);
  const pdfPath = join(buildDir, "build", "pdf.mjs");
  await access(pdfPath).catch(() => {
    throw new Error(
      `Missing ${pdfPath}. Run in ${pdfjsDir}: npx.cmd gulp ${buildName}`
    );
  });
  const pdfjs = await import(pathToFileURL(pdfPath).href);
  return { buildDir, pdfjs };
}

function textFromChars(chars = []) {
  return chars.map(char => char.c).join("");
}

function getOverlayContext(overlay, page) {
  const firstChar = overlay.word?.[0];
  const pageChars = page?.chars || [];
  if (!firstChar || !pageChars.length) {
    return "";
  }
  const from = Math.max(0, firstChar.offset - 80);
  const to = Math.min(
    pageChars.length,
    firstChar.offset + overlay.word.length + 80
  );
  return textFromChars(pageChars.slice(from, to)).replaceAll(/\s+/g, " ").trim();
}

function summarizeProcessedData(processedData) {
  const pageEntries = Object.entries(processedData.pages || {}).sort(
    ([a], [b]) => Number(a) - Number(b)
  );
  const overlays = pageEntries.flatMap(([pageIndex, page]) =>
    (page.overlays || []).map(overlay => ({
      pageIndex: Number(pageIndex),
      overlay,
    }))
  );

  const counts = {};
  for (const { overlay } of overlays) {
    counts[overlay.type] = (counts[overlay.type] || 0) + 1;
  }

  const citations = overlays
    .filter(({ overlay }) => overlay.type === "citation")
    .map(({ pageIndex, overlay }) => {
      const page = processedData.pages[pageIndex];
      return {
        pageIndex,
        text: textFromChars(overlay.word),
        context: getOverlayContext(overlay, page),
        references: (overlay.references || []).map(reference => ({
          index: reference.index ?? null,
          pageIndex: reference.position?.pageIndex ?? null,
          text: textFromChars(reference.chars)
            .replaceAll(/\s+/g, " ")
            .trim()
            .slice(0, 160),
        })),
      };
    });

  return { counts, citations };
}

async function main() {
  const { input, out, buildName, pdfjsDir } = parseArgs(process.argv.slice(2));
  const {
    buildDir,
    pdfjs: { getDocument, GlobalWorkerOptions, VerbosityLevel },
  } = await loadPdfjs(pdfjsDir, buildName);
  const inputPath = resolve(input);
  const outputPath = resolve(
    out ||
      join(
        process.cwd(),
        `${basename(inputPath, extname(inputPath))}.overlays.json`
      )
  );

  GlobalWorkerOptions.workerSrc = pathToFileURL(
    join(buildDir, "build", "pdf.worker.mjs")
  ).href;

  const data = new Uint8Array(await readFile(inputPath));
  const loadingTask = getDocument({
    data,
    cMapPacked: true,
    cMapUrl: toPdfjsResourceDir(pdfjsDir, "build", buildName, "web", "cmaps"),
    standardFontDataUrl: toPdfjsResourceDir(
      pdfjsDir,
      "build",
      buildName,
      "web",
      "standard_fonts"
    ),
    wasmUrl: toPdfjsResourceDir(pdfjsDir, "build", buildName, "web", "wasm"),
    verbosity: VerbosityLevel.ERRORS,
  });

  let pdfDocument = null;
  try {
    pdfDocument = await loadingTask.promise;
    const processedData = await pdfDocument.getProcessedData({});
    const summary = summarizeProcessedData(processedData);

    await mkdir(dirname(outputPath), { recursive: true });
    await writeFile(
      outputPath,
      JSON.stringify({ inputPath, processedData, summary })
    );

    console.log(`Wrote ${outputPath}`);
    console.log(
      `Pages with overlays: ${Object.keys(processedData.pages || {}).length}`
    );
    console.log(`Overlay counts: ${JSON.stringify(summary.counts)}`);
  } finally {
    await pdfDocument?.destroy();
  }
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
