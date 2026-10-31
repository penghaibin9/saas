<template>
  <!-- Trusted repository-authored markup. Never replace with API/user-provided HTML. -->
  <div id="ykw-site" ref="host"><main id="main"><div v-html="heroMarkup" /><ProductDirectory compact /><div v-html="bodyMarkup" /></main><div v-html="dialogMarkup" /></div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import sourceMarkup from '../../components/official-site/showcase/approved-home.html?raw'
import { portalMarkup, PORTAL_LINKS } from '../../services/portalMarkup.js'
import ProductDirectory from '../../components/official-site/ProductDirectory.vue'
import { mountShowcase } from '../../components/official-site/showcase/runtime.js'
import { OFFICIAL_SITE_CONTACT, OFFICIAL_SEO_ROUTES } from '../../config/officialSalesPages.js'

import '../../components/official-site/showcase/showcase.css'
import { refreshOfficialHomeShare } from '../../services/officialWechatRuntime.js'

const markup = portalMarkup(sourceMarkup)
const host = ref(null)
const router = useRouter()
const route = useRoute()
let instance = null
let previousBodyMarker
let previousTitle
const ownedHead = []
const title = OFFICIAL_SEO_ROUTES[0].title
const description = OFFICIAL_SEO_ROUTES[0].description
// Preserve the approved hero, product introductions and dialogs verbatim.
const contentStart = markup.indexOf('<section class="hero"')
const directoryPosition = markup.indexOf('<section class="section suites"')
const mainEnd = markup.indexOf('</main>')
const heroMarkup = markup.slice(contentStart, directoryPosition)
const bodyMarkup = markup.slice(directoryPosition, mainEnd)
const dialogMarkup = markup.slice(mainEnd + '</main>'.length, markup.lastIndexOf('</div>'))
function metadata(selector, attributes, value) {
  let node = document.head.querySelector(selector)
  const previous = node?.getAttribute('content')
  const created = !node
  if (!node) { node = document.createElement('meta'); Object.entries(attributes).forEach(([key, content]) => node.setAttribute(key, content)); document.head.appendChild(node) }
  node.setAttribute('content', value)
  ownedHead.push(() => { if (node.getAttribute('content') !== value) return; if (created) node.remove(); else if (previous === null) node.removeAttribute('content'); else node.setAttribute('content', previous) })
}
onMounted(() => {
  previousTitle = document.title
  document.title = title
  previousBodyMarker = document.body.getAttribute('data-yueke-showcase')
  document.body.setAttribute('data-yueke-showcase', 'active')
  metadata('meta[name="description"]', { name: 'description' }, description)
  metadata('meta[property="og:title"]', { property: 'og:title' }, title)
  metadata('meta[property="og:description"]', { property: 'og:description' }, description)
  metadata('meta[property="og:image"]', { property: 'og:image' }, `${OFFICIAL_SITE_CONTACT.canonicalOrigin}/official-site/showcase-20260909/scenes/overview.webp`)
  void refreshOfficialHomeShare()
  instance = mountShowcase(host.value, {
    contact: { ...OFFICIAL_SITE_CONTACT, tel: OFFICIAL_SITE_CONTACT.phoneHref.replace(/^tel:/, '') },
    links: PORTAL_LINKS,
    navigate: to => router.push(to)
  })
})
watch(() => route.hash, hash => instance?.navigateHash(hash))
onBeforeUnmount(() => {
  instance?.destroy()
  instance = null
  if (document.body.getAttribute('data-yueke-showcase') === 'active') {
    if (previousBodyMarker === null) document.body.removeAttribute('data-yueke-showcase')
    else document.body.setAttribute('data-yueke-showcase', previousBodyMarker)
  }
  if (document.title === title) document.title = previousTitle
  ownedHead.splice(0).forEach(restore => restore())
})
</script>
