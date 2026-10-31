import { createApp, createSSRApp } from 'vue'
import { createRouter, createMemoryHistory, createWebHistory } from 'vue-router'
import App from './App.vue'
import { OFFICIAL_SALES_PAGES } from './config/officialSalesPages.js'
export function createSiteApp({ server = false, hydrate = false } = {}) {
  const router = createRouter({
    history: server ? createMemoryHistory() : createWebHistory(),
    scrollBehavior(to, from, savedPosition) {
      if (savedPosition) return savedPosition
      if (!to.hash) return { top: 0 }
      const target = typeof document === 'undefined' ? null : document.getElementById(to.hash.slice(1))
      return { el: to.hash, top: target ? parseFloat(getComputedStyle(target).scrollMarginTop) || 90 : 90 }
    },
    routes: [
      { path: '/', component: () => import('./views/official-site/ApprovedShowcaseView.vue') },
      ...OFFICIAL_SALES_PAGES.map(page => ({ path: page.path, component:
        ['/products', '/solutions', '/about', '/services/delivery'].includes(page.path) ? () => import('./views/official-site/CompanyView.vue') :
        page.type === 'local-product' ? () => import('./views/official-site/OfficialLocalProductView.vue') :
        page.type === 'product' ? () => import('./views/official-site/OfficialProductView.vue') :
        page.path === '/platform' ? () => import('./views/official-site/OfficialPlatformCapabilityView.vue') :
        page.type === 'legal' ? () => import('./views/official-site/OfficialPolicyView.vue') :
        () => import('./views/official-site/OfficialSalesPageView.vue'), props: page.type === 'product' ? { slug: page.path.split('/').at(-1) } : undefined })),
      { path: '/manage/:section?', component: () => import('./views/manage/ManageView.vue'), meta: { noindex: true } },
      { path: '/:pathMatch(.*)*', component: () => import('./views/NotFoundView.vue'), meta: { noindex: true } }
    ]
  })
  // Static servers may append a slash for generated index.html directories.
  router.beforeEach(to => {
    if (to.path.length > 1 && to.path.endsWith('/')) return { path: to.path.replace(/\/+$/, ''), query: to.query, hash: to.hash, replace: true }
  })
  const app = (server || hydrate ? createSSRApp : createApp)(App)
  app.use(router)
  return { app, router }
}
