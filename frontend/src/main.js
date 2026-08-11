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
// Screenshot C：仅收紧毕设学生台账的页面上下文条。
import './styles/golden-business-ops-rollout-final.css'
// Golden 风险工作区 rollout：学工风险 / 实习风险 / 毕设风险与归档。
import './styles/golden-risk-workspaces-rollout.css'
// Screenshot C：仅恢复学工风险指标区的五列桌面节奏；实习与毕设 B 保持冻结。
import './styles/golden-risk-workspaces-rollout-final.css'
// Golden 材料 / 归档 / 证据工作区 rollout：学工归档 / 实习学生材料 / 毕设材料中心。
import './styles/golden-material-evidence-rollout.css'
// Golden 实施 / 规则配置 rollout：辅导员责任台账 / 实习批次 / 毕设批次。
import './styles/golden-implementation-config-rollout.css'
// Golden 评价 / 成绩 / 结果分析 rollout：辅导员考评 / 实习综合成绩 / 毕设统计报表。
import './styles/golden-evaluation-results-rollout.css'
// Batch 6 B 修正：按毕设统计页真实 DOM 收敛九个统计域为桌面双列驾驶舱。
import './styles/golden-evaluation-results-rollout-final.css'
// Golden 主数据 / 核心对象 rollout：班级管理 / 企业岗位库 / 毕设题目库。
import './styles/golden-master-data-rollout.css'
// Golden 审核 / 流转队列 rollout：困难认定公示 / 实习变更 / 毕设开题连续批阅。
import './styles/golden-review-queues-rollout.css'
// Golden 过程指导 / 跟踪台账 rollout：谈话台账 / 实习指导 / 毕设导师分配。
import './styles/golden-process-guidance-rollout.css'
// Golden 学生个体 360° 详情 rollout：学工画像 / 实习详情 / 毕设详情。
import './styles/golden-student-360-rollout.css'
// Golden 异常 / 延期 / 补偿流程 rollout：学工延期销假 / 毕设延期答辩；实习簇待业务合同修复后再收编。
import './styles/golden-exception-recovery-rollout.css'
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
