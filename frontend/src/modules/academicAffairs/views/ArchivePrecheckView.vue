<template>
  <ModulePageShell
    title="教务归档 · 语义预检"
    subtitle="按业务完成状态判断能否归档，不再用“有记录”代替“已完成”"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="primary" @click="goBatch">进入归档批次</AppButton>
    </template>

    <div class="aapc-toolbar">
      <AppFormItem label="学期">
        <AppTermEntityPicker v-model="termId" placeholder="默认当前学期" @change="load" />
      </AppFormItem>
      <AppButton size="small" variant="ghost" :loading="loading" @click="load">重新检查</AppButton>
    </div>

    <AppInlineAlert v-if="scopeNote" type="info" :description="scopeNote" />

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <EmptyState v-else-if="!domains.length" title="暂无可检查内容" description="请选择学期后重新检查" />
    <template v-else>
      <section class="aapc-summary" :class="overallResult === 'PASS' ? 'is-pass' : 'is-blocked'">
        <div>
          <span class="aapc-summary-eyebrow">{{ termCode || '当前学期' }}</span>
          <h2>{{ overallResult === 'PASS' ? '当前满足归档语义门禁' : '当前不可归档' }}</h2>
          <p>{{ overallResult === 'PASS' ? '所有已启用业务域均已完成语义检查。' : `仍有 ${blockedDomains} 个业务域、${blockingCount} 个阻断项需要处理。` }}</p>
        </div>
        <div class="aapc-summary-metrics">
          <div><b>{{ domains.length }}</b><span>检查域</span></div>
          <div><b>{{ blockedDomains }}</b><span>阻断域</span></div>
          <div><b>{{ blockingCount }}</b><span>阻断项</span></div>
        </div>
      </section>

      <div class="aapc-grid">
        <article v-for="d in domains" :key="d.domain" class="aapc-card" :class="cardClass(d)">
          <header class="aapc-card-head">
            <div>
              <span class="aapc-card-title">{{ d.domainLabel }}</span>
              <code>{{ d.ruleCode || `${d.domain}_SEMANTIC_GATE` }}</code>
            </div>
            <StatusTag :type="tagType(d)" :label="tagLabel(d)" dot />
          </header>

          <div class="aapc-card-metrics">
            <div><b>{{ d.recordCount || 0 }}</b><span>业务记录</span></div>
            <div :class="{ danger: Number(d.blockingCount || 0) > 0 }"><b>{{ d.blockingCount || 0 }}</b><span>阻断项</span></div>
          </div>

          <p class="aapc-card-note">{{ d.summary || d.note || '未返回检查摘要' }}</p>

          <details v-if="Array.isArray(d.evidence) && d.evidence.length" class="aapc-evidence">
            <summary>查看证据（{{ d.evidence.length }}）</summary>
            <pre>{{ evidencePreview(d.evidence) }}</pre>
          </details>

          <footer class="aapc-card-actions">
            <span>{{ d.result === 'PASS' ? '无需处理' : '请先修复阻断后重新检查' }}</span>
            <AppButton v-if="d.result !== 'PASS'" size="small" variant="ghost" @click="jump(d)">去处理</AppButton>
          </footer>
        </article>
      </div>
    </template>
  </ModulePageShell>
</template>

<script>
/** PageId AA-ARCHIVE-PRECHECK-01：结构化语义预检，不落库。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState, StatusTag } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppTermEntityPicker, AppFormItem, AppInlineAlert } from '@/components/common'
import { academicAffairsApi, academicAffairsArchiveApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'

const FALLBACK_ROUTE = {
  STUDENT_STATUS: '/admin/academic-affairs/roster',
  REGISTRATION: '/admin/academic-affairs/registration',
  STATUS_CHANGE: '/admin/academic-affairs/status-changes',
  PROGRAM: '/admin/academic-affairs/programs',
  TEACHING_TASK: '/admin/academic-affairs/teaching-tasks',
  SCHEDULE: '/admin/academic-affairs/scheduling',
  SELECTION: '/admin/academic-affairs/selection/archive',
  EXAM: '/admin/academic-affairs/exam',
  GRADE: '/admin/academic-affairs/grade-tasks',
  MAKEUP: '/admin/academic-affairs/makeup',
  EVALUATION: '/admin/academic-affairs/evaluation',
  TEXTBOOK: '/admin/academic-affairs/textbooks',
  GRADUATION: '/admin/academic-affairs/graduation-audit'
}

export default {
  name: 'ArchivePrecheckView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, StatusTag, AppButton, AppTermEntityPicker, AppFormItem, AppInlineAlert },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      loading: true,
      error: '',
      domains: [],
      scopeNote: '',
      termId: '',
      termCode: '',
      overallResult: 'BLOCKED',
      blockingCount: 0,
      blockedDomains: 0
    }
  },
  async created() {
    try {
      const context = await academicAffairsApi.getContext()
      if (context.code === 0 && context.data) this.ctx = context.data
    } catch (_) {
      // 页面数据请求仍会走后端权限；上下文失败由父布局统一拦截。
    }
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      try {
        const res = await api.precheck(this.termId || undefined)
        if (res.code !== 0) throw new Error(res.message || '归档预检失败')
        const data = res.data || {}
        this.domains = Array.isArray(data.domains) ? data.domains : []
        this.scopeNote = data.scopeNote || ''
        this.termCode = data.termCode || ''
        this.overallResult = data.result || (this.domains.every((d) => d.result === 'PASS') ? 'PASS' : 'BLOCKED')
        this.blockingCount = Number(data.blockingCount || 0)
        this.blockedDomains = Number(data.blockedDomains || this.domains.filter((d) => d.result !== 'PASS').length)
        if (!this.termId && data.termId) this.termId = data.termId
      } catch (err) {
        this.domains = []
        this.error = err?.message || '归档预检失败，请稍后重试'
      } finally {
        this.loading = false
      }
    },
    cardClass(domain) { return domain.result === 'PASS' ? 'is-ok' : 'is-missing' },
    tagType(domain) { return domain.result === 'PASS' ? 'success' : 'danger' },
    tagLabel(domain) { return domain.result === 'PASS' ? '通过' : '阻断' },
    evidencePreview(evidence) {
      return JSON.stringify((evidence || []).slice(0, 5), null, 2)
    },
    jump(domain) {
      const path = domain.route || FALLBACK_ROUTE[domain.domain]
      if (path) this.$router.push(path)
    },
    goBatch() { this.$router.push('/admin/academic-affairs/archive') }
  }
}
</script>

<style scoped>
.aapc-toolbar { display: flex; align-items: center; gap: 16px; margin-bottom: 12px; }
.aapc-summary { display: flex; justify-content: space-between; gap: 24px; padding: 20px 22px; margin: 14px 0; border: 1px solid; border-radius: 14px; background: #fff; }
.aapc-summary.is-pass { border-color: #86c99a; background: #f3fbf5; }
.aapc-summary.is-blocked { border-color: #efb0b0; background: #fff7f7; }
.aapc-summary-eyebrow { color: var(--text-tertiary, #64748b); font-size: 12px; }
.aapc-summary h2 { margin: 6px 0; font-size: 20px; }
.aapc-summary p { margin: 0; color: var(--text-secondary, #64748b); font-size: 13px; }
.aapc-summary-metrics { display: flex; gap: 12px; align-items: center; }
.aapc-summary-metrics div { min-width: 82px; padding: 10px 12px; border: 1px solid rgba(148,163,184,.35); border-radius: 10px; text-align: center; background: #fff; }
.aapc-summary-metrics b, .aapc-summary-metrics span { display: block; }
.aapc-summary-metrics b { font-size: 20px; }
.aapc-summary-metrics span { margin-top: 3px; color: #64748b; font-size: 11px; }
.aapc-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 14px; margin-top: 12px; }
.aapc-card { display: flex; flex-direction: column; min-height: 245px; padding: 16px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 12px; background: #fff; }
.aapc-card.is-missing { border-color: #efb0b0; }
.aapc-card.is-ok { border-color: #b9d9c1; }
.aapc-card-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.aapc-card-head > div { display: flex; flex-direction: column; gap: 5px; min-width: 0; }
.aapc-card-title { font-weight: 650; }
.aapc-card-head code { overflow: hidden; color: #64748b; font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.aapc-card-metrics { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin: 14px 0; }
.aapc-card-metrics div { padding: 9px 10px; border-radius: 8px; background: #f8fafc; }
.aapc-card-metrics b, .aapc-card-metrics span { display: block; }
.aapc-card-metrics b { font-size: 19px; }
.aapc-card-metrics span { color: #64748b; font-size: 11px; }
.aapc-card-metrics .danger b { color: #c24141; }
.aapc-card-note { min-height: 38px; margin: 0; color: #475569; font-size: 12px; line-height: 1.6; }
.aapc-evidence { margin-top: 12px; color: #475569; font-size: 11px; }
.aapc-evidence summary { cursor: pointer; }
.aapc-evidence pre { max-height: 170px; overflow: auto; padding: 9px; border-radius: 8px; background: #0f172a; color: #e2e8f0; white-space: pre-wrap; word-break: break-word; }
.aapc-card-actions { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-top: auto; padding-top: 14px; color: #64748b; font-size: 11px; }
@media (max-width: 900px) { .aapc-summary { flex-direction: column; } .aapc-summary-metrics { align-self: stretch; } .aapc-summary-metrics div { flex: 1; } }
</style>
