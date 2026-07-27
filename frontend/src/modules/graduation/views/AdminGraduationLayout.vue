<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="毕业设计中心"
    :ctx="layoutCtx"
    @menu-select="onMenuSelect"
  >
    <AppInlineAlert
      v-if="ctx && contextError"
      type="danger"
      title="权限上下文加载失败"
      :description="contextError"
      class="gd-scope-alert"
    />
    <AppInlineAlert
      v-else-if="ctx && !permissionReady"
      type="warning"
      title="权限尚未就绪"
      description="真实权限未加载成功前，写操作暂不可用。请检查网络后重试，或联系管理员确认角色授权。"
      class="gd-scope-alert"
    />
    <AppInlineAlert
      v-else-if="ctx && ctx.scopeHint"
      type="warning"
      title="数据范围未就绪"
      :description="ctx.scopeHint"
      class="gd-scope-alert"
    />
    <GraduationBatchStrip v-if="ctx" class="gd-batch-bar" />

    <section v-if="canRenderBusiness" class="gd-page-intro" aria-label="当前页面使用说明">
      <div class="gd-page-intro__main">
        <span class="gd-page-intro__eyebrow">当前工作区</span>
        <strong>{{ pageExperience.title }}</strong>
        <p>{{ pageExperience.purpose }}</p>
      </div>
      <div class="gd-page-intro__next">
        <span>当前重点</span>
        <strong>{{ pageExperience.focus }}</strong>
        <p>{{ pageExperience.next }}</p>
      </div>
      <div class="gd-page-intro__scope">
        <span>{{ ctx.currentRole?.roleName || '当前角色' }}</span>
        <span>{{ ctx.dataScope?.scopeName || '当前数据范围' }}</span>
      </div>
    </section>

    <div
      v-if="canRenderBusiness"
      class="gd-business-view"
      :class="{ 'gd-student-readonly': isStudentList && !canManageStudents }"
    >
      <AppInlineAlert
        v-if="isStudentList && !canManageStudents"
        type="info"
        title="当前为只读名单视图"
        description="你可以查看本数据范围内的毕设学生、进度和材料状态；建档、导师分配、选题、资格认定、分组、答辩组分配与归档仅对具有学生管理权限的角色开放。"
        class="gd-scope-alert"
      />
      <AppInlineAlert
        v-if="isReminderWorkspace"
        type="info"
        title="催交会发送真实站内消息"
        description="点击催交后，系统会向该学生创建真实站内消息并写入催办留痕；请勿因旧页面缓存而重复电话或微信催办。"
        class="gd-scope-alert"
      />
      <GraduationExtensionAdminPanel v-if="isExtensionWorkspace" :ctx="businessCtx" />
      <router-view v-else :key="businessViewKey" :ctx="businessCtx" />
    </div>
    <LoadingState v-else-if="loading" text="正在加载毕业设计中心…" />
    <EmptyState
      v-else-if="!scopeReady && ctx"
      title="数据范围未配置"
      description="当前角色需要学院/专业数据范围后才能查看业务列表。请先在系统管理完成组织范围配置，或切换到已授权角色。"
    />
    <EmptyState
      v-else
      title="无法进入毕业设计中心"
      description="权限上下文不可用。请刷新页面重试；若持续失败，请联系学校管理员。"
    />
  </BasePortalLayout>
</template>

<script>
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState, EmptyState } from '@/components/business'
import { AppInlineAlert } from '@/components/common'
import { matchPermission } from '@/config/navPlan'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { graduationPickerAdapters } from '@/modules/graduation/pickerAdapters'
import { useGraduationBatchStore } from '@/stores/graduationBatch'
import GraduationBatchStrip from './_shared/GraduationBatchStrip.vue'
import GraduationExtensionAdminPanel from './GraduationExtensionAdminPanel.vue'
import router from '@/router'

const PAGE_EXPERIENCE = {
  'graduation-dashboard': {
    title: '毕业设计运营总览',
    purpose: '查看当前批次整体进度、今日待办和滞后风险。',
    focus: '先处理待办与高风险',
    next: '点击待办卡进入对应队列，处理完成后返回总览复核风险变化。'
  },
  'graduation-students': {
    title: '毕设学生与进度',
    purpose: '按批次查询学生当前阶段、课题导师、材料缺口和风险。',
    focus: '先筛选异常和缺口',
    next: '先用页签与筛选缩小范围，再进入学生详情或执行当前允许的操作。'
  },
  'graduation-batches': {
    title: '批次与实施规则',
    purpose: '维护毕业设计批次、阶段期限和批次规则。',
    focus: '确认批次状态与阶段期限',
    next: '修改前先核对当前批次，发布或关闭前再次检查阶段时间轴。'
  },
  'graduation-topic-lib': {
    title: '题目申报与审核',
    purpose: '维护题目、审核申报并检查容量和题目要求。',
    focus: '优先处理待审核题目',
    next: '审核时同时核对导师资格、容量、附件和课题要求。'
  },
  'graduation-topic-rounds': {
    title: '选题轮次与志愿',
    purpose: '管理选题轮次、学生志愿、导师确认和匹配结果。',
    focus: '先处理待确认与容量冲突',
    next: '确认录取前核对志愿顺序、题目容量和学生当前状态。'
  },
  'graduation-topics': {
    title: '学生选题结果',
    purpose: '查看已匹配课题、导师关系和后续变更状态。',
    focus: '关注未匹配和变更申请',
    next: '优先处理没有形成稳定指导关系的学生。'
  },
  'graduation-process': {
    title: '过程指导工作区',
    purpose: '围绕同一学生连续查看任务书、指导记录、计划、评价和中期检查。',
    focus: '先选学生，再处理当前节点',
    next: '按当前阶段进入对应页签，完成后继续处理下一名学生。'
  },
  'graduation-proposals': {
    title: '开题连续批阅',
    purpose: '集中处理待审、驳回重交和逾期未交的开题材料。',
    focus: '优先待审与逾期未交',
    next: '从左侧队列选择材料，批阅后使用自动下一条连续处理。'
  },
  'graduation-finals': {
    title: '成果连续检查',
    purpose: '核对初稿、定稿、查重摘要、附件和批阅意见。',
    focus: '先处理待审与查重异常',
    next: '核对版本和查重状态后通过或退回，处理完成自动进入下一条。'
  },
  'graduation-defense': {
    title: '答辩编排与发布',
    purpose: '管理答辩分组、时间地点、评委秘书、回避冲突和通知。',
    focus: '先消除冲突和待定信息',
    next: '发布前确保人员、时间、地点和回避校验全部完整。'
  },
  'graduation-plagiarism-ledger': {
    title: '查重处理台账',
    purpose: '查看查重任务、检测结果、超标记录和复查申请。',
    focus: '优先超标与待复查',
    next: '选择学生后核对正式成果版本，再执行当前允许的动作。'
  },
  'graduation-review-tasks': {
    title: '论文评阅任务',
    purpose: '分配并处理正式定稿评阅，查看评分和退回重评状态。',
    focus: '优先待评阅和被退回任务',
    next: '确认评阅人回避关系和正式定稿版本后再提交评阅。'
  },
  'graduation-defense-scoring': {
    title: '答辩评分',
    purpose: '按学生查看评委评分、缺席和本轮确认状态。',
    focus: '补齐未评分与未确认记录',
    next: '完成本轮所有评分后再由授权角色确认成绩。'
  },
  'graduation-defense-confirmation': {
    title: '答辩秘书确认',
    purpose: '核对本轮评委评分完整性并确认答辩成绩。',
    focus: '先检查缺项和异常评分',
    next: '确认前逐项核对评委记录、缺席说明和答辩轮次。'
  },
  'graduation-grade-ledger': {
    title: '成绩核算与发布',
    purpose: '核对导师分、评阅分、答辩分和综合成绩状态。',
    focus: '优先处理缺项和待复核成绩',
    next: '按核算、复核、发布顺序办理，不跳过前置状态。'
  },
  'graduation-risk-archive': {
    title: '风险处置与材料归档',
    purpose: '集中查看风险、材料完整性、归档候选和备案结果。',
    focus: '先补材料和关闭高风险',
    next: '归档前完成完整性预检，确认无阻断后再执行归档。'
  },
  'graduation-stats-report': {
    title: '毕业设计统计报表',
    purpose: '查看当前批次进度、质量、风险和完成情况。',
    focus: '关注异常趋势而非单一数字',
    next: '从异常指标下钻到学生名单或对应业务队列。'
  },
  'graduation-audit-logs': {
    title: '毕业设计操作日志',
    purpose: '按操作者、对象和时间追溯关键业务动作。',
    focus: '先定位业务对象和时间范围',
    next: '结合学生档案和业务状态复核操作前后变化。'
  }
}

export default {
  name: 'AdminGraduationLayout',
  components: {
    BasePortalLayout, LoadingState, EmptyState, AppInlineAlert,
    GraduationBatchStrip, GraduationExtensionAdminPanel
  },
  provide() { return { appPickerAdapters: graduationPickerAdapters } },
  data() {
    return { loading: true, ctx: null, contextError: '', permissionReady: false, scopeReady: false }
  },
  computed: {
    brandTitle() {
      if (!this.ctx) return '管理端'
      return (this.ctx.tenantBrandConfig?.schoolName || '管理端') + ' · 管理端'
    },
    layoutCtx() { return this.ctx },
    canRenderBusiness() { return !!(this.ctx && this.permissionReady && this.scopeReady) },
    isStudentList() { return this.$route.name === 'graduation-students' },
    isReminderWorkspace() { return ['graduation-proposals', 'graduation-finals'].includes(this.$route.name) },
    isExtensionWorkspace() {
      return this.$route.name === 'graduation-dashboard' && ['excellent', 'delay'].includes(String(this.$route.query.extension || ''))
    },
    pageExperience() {
      const extension = String(this.$route.query.extension || '')
      if (this.isExtensionWorkspace && extension === 'excellent') {
        return {
          title: '优秀成果认定',
          purpose: '处理候选提名、专业复核和学院终审。',
          focus: '先核对正式定稿与已发布成绩',
          next: '仅对当前行允许的动作办理，完成后继续处理下一条待办。'
        }
      }
      if (this.isExtensionWorkspace && extension === 'delay') {
        return {
          title: '延期答辩审核',
          purpose: '处理学生申请、导师意见、专业复核、学院审批和重新排期。',
          focus: '优先临近原答辩日期的申请',
          next: '按角色顺序办理，学院批准后再安排新的答辩组和日期。'
        }
      }
      return PAGE_EXPERIENCE[this.$route.name] || {
        title: this.$route.meta?.title || '毕业设计业务页面',
        purpose: '查看当前批次的业务数据并完成本角色允许的操作。',
        focus: '先确认批次、状态和待办',
        next: '使用筛选缩小范围，处理完成后检查页面状态是否已刷新。'
      }
    },
    canManageStudents() {
      const patterns = this.ctx?.permissionPatterns
      return Array.isArray(patterns) && matchPermission(patterns, 'graduationDesign.student.manage')
    },
    businessViewKey() {
      return `${this.$route.name || this.$route.path}|${this.$route.meta?.defaultPanel || ''}`
    },
    businessCtx() {
      if (!this.ctx) return null
      const studentListWrite = !this.isStudentList || this.canManageStudents
      return {
        ...this.ctx,
        permissionReady: this.permissionReady,
        scopeReady: this.scopeReady,
        writeEnabled: this.permissionReady && !this.ctx.readonlyTenant && studentListWrite,
        contextError: this.contextError
      }
    }
  },
  watch: {
    '$route.query.batchId': {
      immediate: true,
      handler(id) {
        const store = useGraduationBatchStore()
        store.ensureLoaded({ batchIdFromUrl: id || '', force: !store.initialized })
      }
    },
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        if (panel === 'grad-qual') {
          router.replace({ query: { ...this.$route.query, panel: 'roster' } }).catch(() => {})
        }
      }
    }
  },
  async created() { await this.loadContext() },
  mounted() { this.normalizeReminderCopy() },
  updated() { this.normalizeReminderCopy() },
  methods: {
    normalizeReminderCopy() {
      if (!this.isReminderWorkspace || typeof document === 'undefined') return
      this.$nextTick(() => {
        document.querySelectorAll('.gd-business-view .mp-note').forEach((node) => {
          const text = String(node.textContent || '')
          if (text.includes('当前仅记录线下催办留痕') || text.includes('不代表站内消息已送达')) {
            node.textContent = '本操作会创建真实站内消息并写入催办留痕；学生提交后将进入对应待审队列。'
          }
        })
      })
    },
    async loadContext() {
      this.loading = true
      this.contextError = ''
      const res = await graduationApi.getContext()
      this.loading = false
      if (res.code !== 0 || !res.data) {
        this.ctx = {
          tenantBrandConfig: { schoolName: '管理端' },
          currentRole: { roleName: '未识别' },
          dataScope: { scopeName: '未知' },
          permissionActions: {}, permissionPatterns: null
        }
        this.permissionReady = false
        this.scopeReady = false
        this.contextError = res.message || '权限上下文加载失败'
        return
      }
      this.ctx = res.data
      this.permissionReady = !!res.data.permissionReady
      const needsScope = !!res.data.roleNeedsOrgScope
      const configured = res.data.scopeConfigured !== false
      this.scopeReady = !(needsScope && !configured)
      if (!this.permissionReady) this.contextError = res.data.permissionError || '真实权限未加载成功，写操作已禁用'
      const store = useGraduationBatchStore()
      await store.ensureLoaded({ batchIdFromUrl: this.$route.query.batchId || '', force: true })
      this.syncBatchToUrl()
    },
    syncBatchToUrl() {
      const store = useGraduationBatchStore()
      const cur = this.$route.query.batchId ? String(this.$route.query.batchId) : ''
      const next = store.selectedBatchId || ''
      if (next && next !== cur) router.replace({ query: { ...this.$route.query, batchId: next } }).catch(() => {})
    },
    onMenuSelect(item) {
      if (item?.path && item.path !== this.$route.fullPath.split('#')[0]) {
        const store = useGraduationBatchStore()
        const path = item.path
        const batchQ = store.selectedBatchId ? `batchId=${encodeURIComponent(store.selectedBatchId)}` : ''
        let target = path
        if (batchQ && !/[?&]batchId=/.test(path)) target = path.includes('?') ? `${path}&${batchQ}` : `${path}?${batchQ}`
        router.push(target).catch(() => {})
      }
    }
  }
}
</script>

<style scoped>
.gd-scope-alert { margin: 0 0 var(--space-3); }
.gd-batch-bar { margin: 0 0 var(--space-3); }
.gd-student-readonly :deep(.mp-link + .mp-link) { display: none !important; }
.gd-business-view :deep(.mp-tabs .mp-tab:nth-child(8)) { display: none !important; }

.gd-page-intro {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(260px, .9fr) auto;
  gap: var(--space-4);
  align-items: center;
  margin: 0 0 var(--space-3);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: var(--radius-lg, 12px);
  background: var(--card, #fff);
}
.gd-page-intro__main,
.gd-page-intro__next { min-width: 0; }
.gd-page-intro__eyebrow,
.gd-page-intro__next > span {
  display: block;
  margin-bottom: 3px;
  color: var(--text-tertiary, #64748b);
  font-size: var(--font-size-xs, 12px);
}
.gd-page-intro strong {
  display: block;
  color: var(--text-primary, #0f172a);
  font-size: var(--font-size-base, 14px);
  line-height: 1.45;
}
.gd-page-intro p {
  margin: 3px 0 0;
  color: var(--text-secondary, #475569);
  font-size: var(--font-size-sm, 13px);
  line-height: 1.55;
}
.gd-page-intro__next {
  padding-left: var(--space-4);
  border-left: 1px solid var(--border-light, #e2e8f0);
}
.gd-page-intro__scope {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  color: var(--text-secondary, #475569);
  font-size: var(--font-size-xs, 12px);
  white-space: nowrap;
}
.gd-page-intro__scope span {
  max-width: 210px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.gd-business-view { min-width: 0; }
.gd-business-view :deep(.mp-stack) { gap: var(--space-3); }
.gd-business-view :deep(.mp-card) {
  border-color: var(--border-light, #e2e8f0);
  box-shadow: none;
}
.gd-business-view :deep(.mp-card__head) {
  min-height: 46px;
  padding: var(--space-3) var(--space-4);
}
.gd-business-view :deep(.mp-card__body) { padding: var(--space-4); }
.gd-business-view :deep(.mp-tabs) {
  display: flex;
  align-items: center;
  gap: 4px;
  max-width: 100%;
  padding: 4px;
  overflow-x: auto;
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: var(--radius-md, 8px);
  background: var(--gray-50, #f8fafc);
  scrollbar-width: thin;
}
.gd-business-view :deep(.mp-tab) {
  flex: 0 0 auto;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 6px;
  white-space: nowrap;
}
.gd-business-view :deep(.mp-tab.is-active) {
  background: var(--card, #fff);
  box-shadow: 0 1px 2px rgba(15, 23, 42, .08);
}
.gd-business-view :deep(.gd-actions),
.gd-business-view :deep(.ie-actions),
.gd-business-view :deep(.mp-toolbar) {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.gd-business-view :deep(.mp-note) {
  max-width: 100%;
  color: var(--text-tertiary, #64748b);
  line-height: 1.55;
}
.gd-business-view :deep(.mp-cell-main),
.gd-business-view :deep(.mp-cell-sub) {
  overflow-wrap: anywhere;
}
.gd-business-view :deep(table) {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
}
.gd-business-view :deep(th) {
  position: sticky;
  top: 0;
  z-index: 2;
  background: var(--gray-50, #f8fafc);
  color: var(--text-secondary, #475569);
  font-weight: 600;
  white-space: nowrap;
}
.gd-business-view :deep(th),
.gd-business-view :deep(td) {
  padding-top: 10px;
  padding-bottom: 10px;
  vertical-align: top;
}
.gd-business-view :deep(.mp-link),
.gd-business-view :deep(.mp-btn) { white-space: nowrap; }
.gd-business-view :deep(textarea),
.gd-business-view :deep(input),
.gd-business-view :deep(select) { max-width: 100%; }
.gd-business-view :deep(.mp-pagination),
.gd-business-view :deep(.pagination) {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--space-2);
}

@media (max-width: 1180px) {
  .gd-page-intro { grid-template-columns: minmax(0, 1fr) minmax(240px, .8fr); }
  .gd-page-intro__scope {
    grid-column: 1 / -1;
    flex-direction: row;
    justify-content: flex-end;
    border-top: 1px solid var(--border-light, #e2e8f0);
    padding-top: var(--space-2);
  }
}

@media (max-width: 900px) {
  .gd-page-intro { grid-template-columns: 1fr; gap: var(--space-3); }
  .gd-page-intro__next {
    padding: var(--space-3) 0 0;
    border-left: 0;
    border-top: 1px solid var(--border-light, #e2e8f0);
  }
  .gd-page-intro__scope { justify-content: flex-start; }
  .gd-business-view :deep(.mp-card__head),
  .gd-business-view :deep(.mp-card__body) { padding-left: var(--space-3); padding-right: var(--space-3); }
  .gd-business-view :deep(.mp-grid-2) { grid-template-columns: 1fr; }
}
</style>