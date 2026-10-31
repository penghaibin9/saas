import { createSiteApp } from './app.js'
import { installOfficialSeoRuntime } from './services/officialSeoRuntime.js'
import { installOfficialWechatRuntime } from './services/officialWechatRuntime.js'
const { app, router } = createSiteApp({ hydrate: document.body.hasAttribute('data-prerendered') })
// Do not use top-level await: lazy route chunks also import shared exports from
// this entry chunk; waiting for them here creates a circular module deadlock.
router.isReady().then(() => {
  app.mount('#app')
  installOfficialSeoRuntime(router)
  installOfficialWechatRuntime(router)
  syncRobots(router.currentRoute.value)
})
function syncRobots(to) {
  let robots = document.head.querySelector('meta[name="robots"]')
  if (!robots) { robots = document.createElement('meta'); robots.name = 'robots'; document.head.appendChild(robots) }
  robots.content = to.meta.noindex ? 'noindex, nofollow' : 'index, follow, max-image-preview:large'
}
router.afterEach(syncRobots)
