import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import {
  OFFICIAL_SEO_ROUTES,
  OFFICIAL_SITE_CONTACT,
  officialCanonicalUrl
} from '../src/config/officialSalesPages.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const prerenderSource = fs.readFileSync(path.join(root, 'scripts/prerender-official-site.mjs'), 'utf8')

test('all official SEO routes resolve to the canonical production origin', () => {
  assert.ok(OFFICIAL_SEO_ROUTES.length >= 6)
  for (const route of OFFICIAL_SEO_ROUTES) {
    assert.ok(officialCanonicalUrl(route.path).startsWith(`${OFFICIAL_SITE_CONTACT.canonicalOrigin}/`))
    assert.ok(route.title)
    assert.ok(route.description)
  }
})

test('official prerender emits share-card metadata for search and social previews', () => {
  for (const marker of [
    'og:site_name',
    'og:locale',
    'og:image',
    'og:image:alt',
    'twitter:card',
    'twitter:title',
    'twitter:description',
    'twitter:image',
    'primaryImageOfPage',
    "contactType: 'sales'"
  ]) {
    assert.ok(prerenderSource.includes(marker), `missing prerender marker: ${marker}`)
  }
})

test('social preview images use absolute hnyueke.com URLs', () => {
  assert.match(prerenderSource, /absoluteAssetUrl/)
  assert.match(prerenderSource, /OFFICIAL_SITE_CONTACT\.canonicalOrigin/)
  assert.match(prerenderSource, /page\?\.screenshots\?\.\[0\].*workbench\.webp/)
})
