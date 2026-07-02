import { createRouter, createWebHistory } from 'vue-router'

/**
 * UI-P1.5 临时路由：只有组件预览页。
 * 正式业务路由（/admin、/student、/enterprise、/dashboard，见总册 V3.0 §5.2 路由隔离）
 * 在后续阶段建立，本文件届时整体替换。
 */
const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'ui-preview',
      component: () => import('../views/UiPreview.vue')
    },
    {
      path: '/dev/components',
      name: 'component-dev',
      component: () => import('../views/ComponentDevPreview.vue')
    }
  ]
})

export default router
