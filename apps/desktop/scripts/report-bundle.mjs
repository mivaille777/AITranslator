import { existsSync, readFileSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { gzipSync } from "node:zlib"

const desktopRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..")
const distRoot = resolve(desktopRoot, "dist")
const manifestPath = resolve(distRoot, ".vite", "manifest.json")

if (!existsSync(manifestPath)) {
  throw new Error(`Vite manifest not found: ${manifestPath}`)
}

const manifest = JSON.parse(readFileSync(manifestPath, "utf8"))

function findEntry(source) {
  const match = Object.entries(manifest).find(([key, value]) =>
    key === source || value?.src === source,
  )
  if (!match) {
    throw new Error(`Unable to locate Vite entry for ${source}`)
  }
  return match[0]
}

function collectStatic(entryKey, files = new Set(), visited = new Set()) {
  if (!entryKey || visited.has(entryKey)) return files
  visited.add(entryKey)
  const chunk = manifest[entryKey]
  if (!chunk) return files

  if (chunk.file) files.add(chunk.file)
  for (const cssFile of chunk.css ?? []) files.add(cssFile)
  for (const imported of chunk.imports ?? []) {
    collectStatic(imported, files, visited)
  }
  return files
}

function collectLazy(entryKey, initialFiles) {
  const files = new Set()
  const visited = new Set()

  function visit(key) {
    if (!key || visited.has(key)) return
    visited.add(key)
    const chunk = manifest[key]
    if (!chunk) return

    for (const imported of chunk.imports ?? []) visit(imported)
    for (const dynamicKey of chunk.dynamicImports ?? []) {
      collectStatic(dynamicKey, files)
      visit(dynamicKey)
    }
  }

  visit(entryKey)
  for (const file of initialFiles) files.delete(file)
  return files
}

function metric(file) {
  const absolute = resolve(distRoot, file)
  const bytes = readFileSync(absolute)
  return {
    file,
    raw: bytes.length,
    gzip: gzipSync(bytes).length,
  }
}

function summarize(files) {
  const metrics = [...files].map(metric)
  return metrics.reduce(
    (summary, item) => {
      const bucket = item.file.endsWith(".css") ? summary.css : summary.js
      bucket.raw += item.raw
      bucket.gzip += item.gzip
      return summary
    },
    {
      js: { raw: 0, gzip: 0 },
      css: { raw: 0, gzip: 0 },
    },
  )
}

function kb(bytes) {
  return `${(bytes / 1024).toFixed(1)} kB`
}

function printEntry(label, source) {
  const entryKey = findEntry(source)
  const initialFiles = collectStatic(entryKey)
  const lazyFiles = collectLazy(entryKey, initialFiles)
  const initial = summarize(initialFiles)
  const lazy = summarize(lazyFiles)

  console.log(`\n${label}`)
  console.log(`  initial JS  : ${kb(initial.js.raw)} raw / ${kb(initial.js.gzip)} gzip`)
  console.log(`  initial CSS : ${kb(initial.css.raw)} raw / ${kb(initial.css.gzip)} gzip`)
  console.log(`  lazy JS     : ${kb(lazy.js.raw)} raw / ${kb(lazy.js.gzip)} gzip`)
  console.log(`  lazy CSS    : ${kb(lazy.css.raw)} raw / ${kb(lazy.css.gzip)} gzip`)

  return { initialFiles, lazyFiles }
}

console.log("\n==============================================")
console.log(" AITranslator frontend bundle report")
console.log("==============================================")

const main = printEntry("Main initial route", "index.html")
const overlay = printEntry("Overlay initial surface", "overlay.html")

const emittedJs = [...new Set(
  Object.values(manifest)
    .map((chunk) => chunk?.file)
    .filter((file) => typeof file === "string" && file.endsWith(".js")),
)]
  .map(metric)
  .sort((left, right) => right.raw - left.raw)
  .slice(0, 8)

console.log("\nLargest emitted JS chunks")
for (const item of emittedJs) {
  console.log(`  ${item.file}  ${kb(item.raw)} raw / ${kb(item.gzip)} gzip`)
}

const sharedInitial = [...main.initialFiles].filter((file) => overlay.initialFiles.has(file))
const sharedMetrics = summarize(new Set(sharedInitial))
console.log("\nShared initial payload")
console.log(`  JS  : ${kb(sharedMetrics.js.raw)} raw / ${kb(sharedMetrics.js.gzip)} gzip`)
console.log(`  CSS : ${kb(sharedMetrics.css.raw)} raw / ${kb(sharedMetrics.css.gzip)} gzip`)
console.log("")
