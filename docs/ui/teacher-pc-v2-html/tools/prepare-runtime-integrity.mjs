#!/usr/bin/env node

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const toolDir = path.dirname(fileURLToPath(import.meta.url))
const runtimePath = path.resolve(toolDir, '../shared/v2-prototype.js')
let source = fs.readFileSync(runtimePath, 'utf8').replace(/\r\n/g, '\n')

if (!source.includes('function repairExactDuplicateOverlays()')) {
  const anchor = '  window.V2Prototype = {'
  const integrity = `  function repairExactDuplicateOverlays() {
    const groups = new Map();
    $$('[id]').forEach(element => {
      if (!element.id) return;
      if (!groups.has(element.id)) groups.set(element.id, []);
      groups.get(element.id).push(element);
    });

    const repaired = [];
    groups.forEach((nodes, id) => {
      if (nodes.length < 2) return;
      if (!nodes.every(node => node.matches('.v2-modal-backdrop,.v2-drawer-backdrop'))) return;
      const signature = nodes[0].outerHTML;
      if (!nodes.every(node => node.outerHTML === signature)) return;
      nodes.slice(1).forEach(node => node.remove());
      repaired.push({ id, removed: nodes.length - 1 });
    });

    if (repaired.length) {
      const history = Array.isArray(window.__V2_DUPLICATE_OVERLAY_REPAIRS__)
        ? window.__V2_DUPLICATE_OVERLAY_REPAIRS__
        : [];
      window.__V2_DUPLICATE_OVERLAY_REPAIRS__ = history.concat(repaired);
    }
    return repaired;
  }

  let overlayIntegrityQueued = false;
  function scheduleOverlayIntegrityRepair() {
    if (overlayIntegrityQueued) return;
    overlayIntegrityQueued = true;
    queueMicrotask(() => {
      overlayIntegrityQueued = false;
      repairExactDuplicateOverlays();
    });
  }

  const overlayIntegrityObserver = new MutationObserver(scheduleOverlayIntegrityRepair);
  overlayIntegrityObserver.observe(document.documentElement, { childList: true, subtree: true });
  scheduleOverlayIntegrityRepair();
  window.addEventListener('load', scheduleOverlayIntegrityRepair);
  window.addEventListener('v2:page-ready', scheduleOverlayIntegrityRepair);

`
  if (!source.includes(anchor)) throw new Error('V2Prototype anchor missing')
  source = source.replace(anchor, `${integrity}${anchor}`)
}

if (!source.includes('repairExactDuplicateOverlays();\n    document.body.dataset.theme')) {
  source = source.replace(
    '  function initEnhancements() {\n    document.body.dataset.theme',
    '  function initEnhancements() {\n    repairExactDuplicateOverlays();\n    document.body.dataset.theme'
  )
}

const required = [
  'function repairExactDuplicateOverlays()',
  "node.matches('.v2-modal-backdrop,.v2-drawer-backdrop')",
  'nodes.every(node => node.outerHTML === signature)',
  'overlayIntegrityObserver.observe',
  'window.__V2_DUPLICATE_OVERLAY_REPAIRS__'
]
for (const marker of required) {
  if (!source.includes(marker)) throw new Error(`runtime integrity marker missing: ${marker}`)
}

fs.writeFileSync(runtimePath, source, 'utf8')
console.log('strict duplicate overlay runtime integrity prepared')
