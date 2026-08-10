// 设计令牌必须最先引入，所有组件样式依赖其中的 CSS 变量
import './styles/tokens.css'
// Element Plus 主题变量对齐（仅日期选择器使用 el 组件）
import './styles/element-theme.css'
// PC 管理端高对比视觉皮肤：只覆盖外观，不改变菜单、路由与业务结构。
import './styles/high-contrast-skin.css'
// Golden 页面二次精修：仅学生主档与选课控制台的唯一 DOM 锚点生效。
import './styles/golden-refinement.css'
// Screenshot F 微调：收紧学生筛选区并修正选课长标题断行。
import './styles/golden-refinement-final.css'
// Golden 业务页 rollout：学工 / 岗位实习 / 毕业设计代表性看板，页面唯一锚点生效。
import './styles/golden-business-rollout.css'
// Screenshot C 最终收口：平衡学工指标区并去除毕设重复上下文层。
import './styles/golden-business-rollout-final.css'
// Golden 高频操作页 rollout：请假连续审批 / 实习学生台账 / 毕设学生台账。
import './styles/golden-business-ops-rollout.css'
// Stage B / B3：窄屏管理端仍保留可操作的一/二级导航，不再要求用户拉宽窗口。
import './styles/stage-b-responsive-nav.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { installDirtyFormGuard } from './router/dirtyFormGuard'
import { toast } from './utils/toast'

// Stage B 高频工作流：给“某个实习学生的材料”一个稳定真实深链。
// 页面直接读取 /internship/material-center/{internshipId} 的真实版本链，不造第二份材料数据。
if (!router.hasRoute('internship-student-materials')) {
  router.addRoute({
    path: '/admin/internship/students/:id/materials',
    component: () => import('@/modules/internship/views/AdminInternshipLayout.vue'),
    meta: { moduleCode: 'INTERNSHIP' },
    children: [{
      path: '',
      name: 'internship-student-materials',
      component: () => import('@/modules/internship/views/InternshipStudentMaterialEntryView.vue'),
      meta: {
        moduleCode: 'INTERNSHIP',
        title: '学生实习材料',
        requiresAuth: true,
        permissionKey: 'internship.archive.view'
      }
    }]
  })
}

// P0 演示页阻断：受保护后台会话里，任何误入 /demo 都立即回主站工作台。
router.beforeEach((to) => {
  if (!String(to.path || '').startsWith('/demo')) return true
  let hasSession = false
  try {
    hasSession = Boolean(
      window.localStorage.getItem('accessToken') ||
      window.localStorage.getItem('token') ||
      window.sessionStorage.getItem('accessToken') ||
      window.sessionStorage.getItem('token')
    )
  } catch {
    hasSession = false
  }
  if (!hasSession) return true
  return { path: '/workbench', replace: true }
})

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(router)
installDirtyFormGuard(router)

// 全局兜底：UI 事件处理器若抛出异常（包括业务页面尚未 await 的 Promise），
// 统一收敛为 toast，避免一次点击把整个管理端打回登录页或空白页。
app.config.errorHandler = (err, instance, info) => {
  const message = err && err.message ? err.message : '页面操作失败，请稍后重试'
  console.error('[vue-error]', info, err)
  toast.error(message)
}

window.addEventListener('unhandledrejection', (event) => {
  const reason = event && event.reason
  // AbortError 通常来自路由切换/组件卸载时主动取消请求，不应骚扰用户。
  if (reason && reason.name === 'AbortError') return
  console.error('[unhandled-rejection]', reason)
})

app.mount('#app')
