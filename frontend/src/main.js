// 设计令牌必须最先引入，所有组件样式依赖其中的 CSS 变量
import './styles/tokens.css'
// Element Plus 主题变量对齐（仅日期选择器使用 el 组件）
import './styles/element-theme.css'
// PC 管理端高对比视觉皮肤：只覆盖外观，不改变菜单、路由与业务结构。
import './styles/high-contrast-skin.css'
// Stage B / B3：窄屏管理端仍保留可操作的一/二级导航，不再要求用户拉宽窗口。
import './styles/stage-b-responsive-nav.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './config/helpCenterRuntime'
import { installGraduationW76Workbench } from './modules/workbench/config/graduationW76Workbench'
import { installDirtyFormGuard } from './router/dirtyFormGuard'
import { toast } from './utils/toast'

// W7.6：只扩展既有 T9 评阅人工作台配方，复用 UnifiedTodo 与统一评阅中心，不新增工作台状态。
installGraduationW76Workbench()

// 小程序 WebView / 售后二维码共用的公开只读帮助页。
// 与 /admin/help 分离：不暴露管理端导航，不要求管理端 token，也没有业务写入口。
if (!router.hasRoute('public-help')) {
  router.addRoute({
    path: '/help',
    name: 'public-help',
    component: () => import('./views/help/PublicHelpView.vue'),
    meta: { public: true, title: '帮助中心' }
  })
}

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

// 任何失效书签、旧链接或未知 URL 都回到工作台，避免生产环境出现空白路由页。
if (!router.hasRoute('unknown-route-fallback')) {
  router.addRoute({
    path: '/:pathMatch(.*)*',
    name: 'unknown-route-fallback',
    redirect: '/workbench'
  })
}

// Stage B / B4：统一未保存表单保护。第一批覆盖实习批次/企业，同域长表单由 guard 单一维护。
installDirtyFormGuard(router)

const app = createApp(App)
// 统一轻提示兼容门面：业务页可使用 this.$message.success/error/warning/info，
// 实际仍由全局 AppToast 渲染，不引入第二套通知组件。
app.config.globalProperties.$message = toast
app.use(createPinia())
app.use(router)
app.mount('#app')
