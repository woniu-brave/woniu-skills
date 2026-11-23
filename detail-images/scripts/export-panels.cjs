const { access, mkdir, readFile, rename, rm, writeFile } = require('node:fs/promises');
const { existsSync } = require('node:fs');
const { randomUUID } = require('node:crypto');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

function loadChromium() {
  const bundled = path.resolve(path.dirname(process.execPath), '..', 'node_modules', 'playwright');
  for (const candidate of ['playwright', bundled]) {
    let resolved;
    try {
      resolved = require.resolve(candidate);
    } catch (error) {
      if (error.code === 'MODULE_NOT_FOUND') continue;
      throw error;
    }
    return require(resolved).chromium;
  }
  throw new Error('Playwright is required. Run npm install in the skill folder or use Node.js with Playwright available.');
}

function browserPath(chromium) {
  if (process.env.ECO_VISUAL_BROWSER) return process.env.ECO_VISUAL_BROWSER;

  const candidates = [
    chromium.executablePath(),
    ...[process.env.ProgramFiles, process.env['ProgramFiles(x86)'], process.env.LOCALAPPDATA]
      .filter(Boolean)
      .flatMap((base) => [
        path.join(base, 'Google', 'Chrome', 'Application', 'chrome.exe'),
        path.join(base, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
      ]),
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    '/usr/bin/chromium',
    '/usr/bin/google-chrome',
  ];
  const executablePath = candidates.find((candidate) => existsSync(candidate));
  if (!executablePath) {
    throw new Error('No Chromium browser found. Set ECO_VISUAL_BROWSER to the browser executable.');
  }
  return executablePath;
}

async function capturePanels(html, width, selectedId) {
  const chromium = loadChromium();
  const browser = await chromium.launch({ executablePath: browserPath(chromium), headless: true });
  try {
    const page = await browser.newPage({
      viewport: { width, height: 1000 },
      deviceScaleFactor: 1,
      reducedMotion: 'reduce',
      serviceWorkers: 'block',
    });
    await page.route(/^https?:\/\//, (route) => route.abort());
    await page.goto(pathToFileURL(html).href, { waitUntil: 'load' });

    const panels = page.locator('[data-export-id]');
    const ids = await panels.evaluateAll((elements) => elements.map((element) => {
      const id = element.dataset.exportId;
      if (element.parentElement?.closest('[data-export-id]')) {
        throw new Error(`Export panel "${id}" is nested inside another panel.`);
      }
      return id;
    }));
    if (!ids.length) throw new Error('No elements with data-export-id were found.');
    if (ids.some((id) => !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(id)) || new Set(ids).size !== ids.length) {
      throw new Error('Each export panel must have a unique lower-case ID such as product-hero.');
    }
    if (selectedId && !ids.includes(selectedId)) throw new Error(`Unknown export panel: ${selectedId}`);

    await page.evaluate(async (selected) => {
      if (document.body.hasAttribute('data-panel-gallery')) {
        document.body.classList.add('export-pages');
      }
      const sections = Array.from(document.querySelectorAll('[data-export-id]'));
      const images = sections.filter((section) => !selected || section.dataset.exportId === selected)
        .flatMap((section) => Array.from(section.querySelectorAll('img')));
      await Promise.all(images.map(async (image) => {
        image.loading = 'eager';
        try {
          await image.decode();
        } catch {
          const panel = image.closest('[data-export-id]').dataset.exportId;
          throw new Error(`Image failed to load in "${panel}": ${image.getAttribute('src') ?? '(no src)'}`);
        }
      }));
      await document.fonts.ready;
    }, selectedId);

    const captures = [];
    for (const [index, id] of ids.entries()) {
      if (selectedId && id !== selectedId) continue;
      const panel = panels.nth(index);
      const bounds = await panel.boundingBox();
      if (!bounds || bounds.height < 1 || Math.abs(bounds.width - width) > 0.01 || Math.abs(bounds.x) > 0.01) {
        throw new Error(`Panel "${id}" must have visible content and fill the ${width}px viewport horizontally.`);
      }

      await panel.scrollIntoViewIfNeeded();
      // Give Chromium time to paint tiles brought into view before capture.
      await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const png = await panel.screenshot({ type: 'png', animations: 'disabled' });
      const imageWidth = png.readUInt32BE(16);
      const imageHeight = png.readUInt32BE(20);
      if (imageWidth !== width || imageHeight < 1) throw new Error(`Unexpected image size for "${id}".`);

      const file = `${String(index + 1).padStart(2, '0')}-${id}.png`;
      captures.push({ png, info: { id, file, width: imageWidth, height: imageHeight } });
    }
    return { ids, captures };
  } finally {
    await browser.close();
  }
}

async function atomicWrite(target, contents) {
  const temp = `${target}.${randomUUID()}.tmp`;
  try {
    await writeFile(temp, contents);
    await rename(temp, target);
  } finally {
    await rm(temp, { force: true });
  }
}

async function main() {
  const [html, output, widthArg, flag, selectedId, ...extra] = process.argv.slice(2);
  const width = Number(widthArg);
  if (!html || !output || !Number.isSafeInteger(width) || width < 1 || extra.length ||
      (flag !== undefined && (flag !== '--panel' || !selectedId))) {
    throw new Error('Usage: node export-panels.cjs <local-html> <output-directory> <width-px> [--panel <id>]');
  }

  const inputPath = path.resolve(html);
  await access(inputPath);
  const manifestPath = path.join(output, 'manifest.json');
  const previous = selectedId ? JSON.parse(await readFile(manifestPath, 'utf8').catch((error) => {
    if (error.code !== 'ENOENT') throw error;
    throw new Error('Export the full page to this directory before exporting an individual panel.');
  })) : undefined;
  const { ids, captures } = await capturePanels(inputPath, width, selectedId);
  if (previous && (previous.width !== width || !Array.isArray(previous.panels) ||
      JSON.stringify(previous.panels.map(({ id }) => id)) !== JSON.stringify(ids))) {
    throw new Error('Panel order, IDs or width changed. Export the full page to a new directory.');
  }
  await mkdir(output, { recursive: true });
  const newPanels = captures.map(({ info }) => info);
  if (previous) {
    const updated = captures[0].info;
    updated.file = updated.file.replace(/\.png$/, `-${randomUUID().slice(0, 8)}.png`);
  }
  for (const { png, info } of captures) await atomicWrite(path.join(output, info.file), png);
  const panels = previous ? previous.panels.map((panel) => panel.id === selectedId ? newPanels[0] : panel) : newPanels;
  await atomicWrite(manifestPath, `${JSON.stringify({ width, panels }, null, 2)}\n`);
  process.stdout.write(`Exported ${captures.length} PNG file(s) to ${path.resolve(output)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.message}\n`);
  process.exitCode = 1;
});
