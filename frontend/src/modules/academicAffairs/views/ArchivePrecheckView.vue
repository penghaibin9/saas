<template>
  <ModulePageShell class="aapc-page"
    title="归档缺失提醒"
    :subtitle="isCollegeScope ? '只核对本院实时缺项；学校正式封存由校教务统筹' : '十三个数据域逐项核对；待处理与已阻断均不能封存，不适用项必须有正式依据'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="ghost" :loading="loading" @click="load">重新检查</AppButton>
      <AppButton variant="primary" @click="goBatch">{{ isCollegeScope ? '查看学校归档进度' : '进入归档批次' }}</AppButton>
    </template>

    <div class="aapc-toolbar">
      <AppFormItem label="学期"><AppTermEntityPicker v-model="termId" placeholder="默认当前学期" /></AppFormItem>
      <span>检查范围：{{ ctx.dataScope.scopeName || (isCollegeScope ? '本学院' : '当前授权范围') }}</span>
      <span v-if="termCode">当前学期：{{ termCode }}</span>
    </div>
    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="`${error}；${precheckDecision}`" @retry="load" />
    <EmptyState v-else-if="!domains.length" title="暂无可检查内容" description="请选择学期后重新检查" />
    <template v-else>
      <section class="aapc-decision" :class="{ 'is-pass': overallResult === 'PASS' }" aria-live="polite">
        <div><h2>{{ precheckTitle }}</h2><p>{{ overallDescription }}</p></div>
        <AppButton v-if="firstBlockingDomain && !schoolCheckPending(firstBlockingDomain)" size="small" variant="ghost" @click="jump(firstBlockingDomain)">去处理首要阻断</AppButton>
      </section>
      <p v-if="scopeNote" class="aapc-note">{{ flowText(scopeNote, '检查范围待核对') }}</p>
      <p v-if="isCollegeScope" class="aapc-note">{{ precheckDecision }}</p>
      <div class="aapc-counts">
        <span>{{ domains.length }} 类检查</span><span>{{ passedDomains }} 类已通过</span>
        <span>{{ domains.filter(d => d.result === 'NOT_APPLICABLE').length }} 类不适用</span>
      </div>
      <section v-if="blockedDomainRows.length" class="aapc-section">
        <header><h3>优先处理（{{ blockedDomainRows.length }} 类）</h3><span>已阻断与待核验资料均不可封存</span></header>
        <DataTable :columns="issueColumns" :rows="blockedDomainRows" row-key="domain">
          <template #cell-domain="{ row }"><strong>{{ row.domainLabel }}</strong><small>{{ row.recordCount || 0 }} 条业务记录</small></template>
          <template #cell-summary="{ row }">
            <p class="aapc-problem">{{ flowText(row.summary || row.note, '未返回检查摘要') }}</p>
            <details v-if="Array.isArray(row.evidence) && row.evidence.length" class="aapc-evidence">
              <summary>查看检查依据（{{ row.evidence.length }}）</summary>
              <ul><li v-for="(item,index) in evidencePreview(row.evidence)" :key="index">{{ item }}</li></ul>
            </details>
            <details v-if="row.ruleCode" class="aapc-evidence"><summary>实施人员使用：技术依据</summary><code>{{ row.ruleCode }}</code></details>
          </template>
          <template #cell-result="{ row }"><StatusTag :type="tagType(row)" :label="tagLabel(row)" dot /></template>
          <template #cell-action="{ row }">
            <span v-if="schoolCheckPending(row)" class="aapc-note">等待校教务核验学校统筹项</span>
            <AppButton v-else size="small" variant="ghost" @click="jump(row)">去处理</AppButton>
          </template>
        </DataTable>
      </section>
      <details v-if="passedDomainRows.length" class="aapc-passed">
        <summary>已通过与不适用（{{ passedDomainRows.length }} 类）<span>不适用项保留正式依据</span></summary>
        <div v-for="d in passedDomainRows" :key="d.domain" class="aapc-result-row" :class="{ 'is-na': d.result === 'NOT_APPLICABLE' }">
          <strong>{{ d.domainLabel }}</strong><StatusTag :type="tagType(d)" :label="tagLabel(d)" dot />
          <p>{{ flowText(d.summary || d.note, '未返回检查摘要') }}</p>
          <details v-if="Array.isArray(d.evidence) && d.evidence.length" class="aapc-evidence"><summary>查看检查依据（{{ d.evidence.length }}）</summary><ul><li v-for="(item,index) in evidencePreview(d.evidence)" :key="index">{{ item }}</li></ul></details>
          <details v-if="d.ruleCode" class="aapc-evidence"><summary>实施人员使用：技术依据</summary><code>{{ d.ruleCode }}</code></details>
        </div>
      </details>
      <p class="aapc-footnote">预检结果用于查缺；正式封存以归档批次中的最新检查结论为准。</p>
    </template>
  </ModulePageShell>
</template>

<script>
/** PageId AA-ARCHIVE-PRECHECK-01：结构化语义预检，不落库。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, StatusTag } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppTermEntityPicker, AppFormItem } from '@/components/common'
import { academicAffairsArchiveApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { safeBusinessMessage, safeEnumLabel } from '@/utils/presentationSafety'
import { currentUserFromToken } from '@/services/http/client'
import { gradeError } from './parallel-c/grade-review'
import { academicFlowText } from '../config/academicFlowRegistry.js'

const ARCHIVE_DOMAINS = ['STUDENT_STATUS','REGISTRATION','STATUS_CHANGE','PROGRAM','TEACHING_TASK','SCHEDULE','SELECTION','EXAM','GRADE','MAKEUP','EVALUATION','TEXTBOOK','GRADUATION']
const DOMAIN_RESULTS = new Set(['PASS','BLOCKED','UNKNOWN','NOT_APPLICABLE'])

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
  GRADUATION: '/admin/academic-affairs/graduation/audit-console'
}

// 后端状态语义约束：UNKNOWN 不会被当成 PASS；页面只展示对应中文含义。
// 后端归档门禁：BLOCKED 与 UNKNOWN 均不得进入正式归档。
export default {
  name: 'ArchivePrecheckView',
  components: {
    ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState,
    StatusTag, AppButton, AppTermEntityPicker, AppFormItem
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      issueColumns: [{ key: 'domain', title: '归档资料', width: '18%' }, { key: 'summary', title: '当前问题', width: '50%' }, { key: 'result', title: '检查结论', width: '14%' }, { key: 'action', title: '处理入口' }],
      alive: true, scope: 0, seq: 0,
      loading: true,
      error: '',
      syncingResolvedTerm: false,
      domains: [],
      scopeType: '',
      scopeNote: '',
      termId: '',
      termCode: '',
      overallResult: 'BLOCKED',
      blockingCount: 0,
      blockedDomains: 0
    }
  },
  computed: {
    identity() {
      const user = currentUserFromToken() || {}
      return JSON.stringify([user.tenantId, user.userId, user.activeContextId, user.currentRoleCode, this.ctx.currentRole, this.ctx.dataScope])
    },
    isCollegeScope() { return this.scopeType === 'COLLEGE' || (this.ctx.dataScope?.scopeType || this.ctx.dataScope?.scope) === 'COLLEGE' },
    routeTermError() {
      const termId = this.$route.query?.termId
      return termId != null && (typeof termId !== 'string' || !/^\d+$/.test(termId)) ? '学期参数无效，请从归档批次重新进入' : ''
    },
    precheckTitle() {
      if (this.loading) return '正在读取所选学期的预检结果'
      if (this.error || !this.domains.length) return '预检结果待核对'
      if (this.isCollegeScope) return this.overallResult === 'PASS' ? '本学院当前没有阻断或待处理事项' : '本院预检仍有阻断或待核验事项'
      return this.overallResult === 'PASS' ? '当前满足归档检查要求' : '当前仍有业务阻断，暂不可归档'
    },
    precheckDecision() {
      if (this.loading) return '正在读取'
      if (this.error || !this.domains.length) return '尚未取得有效结论'
      if (this.overallResult !== 'PASS') return this.isCollegeScope ? '按各项实际责任核对，学校统筹项交校教务' : '必须先处理阻断 / 待处理事项'
      return this.isCollegeScope ? '本院已具备当前预检条件' : '可以进入归档批次'
    },
    passedDomains() {
      return this.domains.filter((domain) => domain.result === 'PASS').length
    },
    blockedDomainRows() {
      return this.domains
        .filter((domain) => ['BLOCKED', 'UNKNOWN'].includes(domain.result))
        .slice()
        .sort((a, b) => Number(this.schoolCheckPending(a)) - Number(this.schoolCheckPending(b)) || Number(b.blockingCount || 0) - Number(a.blockingCount || 0))
    },
    passedDomainRows() {
      return this.domains.filter((domain) => ['PASS', 'NOT_APPLICABLE'].includes(domain.result))
    },
    firstBlockingDomain() {
      return this.blockedDomainRows[0] || null
    },
    overallDescription() {
      if (this.loading) return '正在按当前身份、范围与学期读取正式业务数据。'
      if (this.error || !this.domains.length) return '请重新读取预检结果；未取得结论前，不认定数据完整或可归档。'
      if (this.overallResult === 'PASS') {
        if (this.isCollegeScope) return `共检查本学院 ${this.domains.length} 个业务域，本学院当前没有阻断或待处理事项；学校正式封存仍由校教务统一核对。`
        return `共检查 ${this.domains.length} 个业务域，当前全部满足归档检查要求。进入归档批次后仍按正式归档流程执行。`
      }
      return `仍有 ${this.blockedDomains} 个阻断 / 待处理业务域、${this.blockingCount} 个阻断项需要处理；${this.isCollegeScope ? '本院事项按责任处理，学校统筹项待校教务核验；' : ''}待处理状态不会被当作已通过，本页不写入归档事实。`
    },
    nextActionText() {
      if (this.loading || this.error || !this.domains.length) return '先取得当前学期的有效预检结果'
      if (!this.firstBlockingDomain && this.isCollegeScope) return '由校教务统一核对学校归档条件'
      if (!this.firstBlockingDomain) return '进入归档批次继续正式归档流程'
      if (this.schoolCheckPending(this.firstBlockingDomain)) return `请校教务核验「${this.firstBlockingDomain.domainLabel}」的学校统筹项`
      return `先处理「${this.firstBlockingDomain.domainLabel}」的 ${Number(this.firstBlockingDomain.blockingCount || 0)} 个阻断项`
    }
  },
  watch: {
    identity() { this.syncRoute() },
    '$route.query.termId'() { this.syncRoute() },
    termId() { if (!this.syncingResolvedTerm) this.onTermChange() }
  },
  created() { this.syncRoute() },
  beforeUnmount() { this.alive = false; this.clearPrivate() },
  methods: {
    flowText: academicFlowText,
    capture(termId) { return { scope: this.scope, identity: this.identity, termId: String(termId || ''), routeTerm: this.$route.query?.termId } },
    isCurrent(c) { return this.alive && c.scope === this.scope && c.identity === this.identity && c.termId === String(this.termId || '') && c.routeTerm === this.$route.query?.termId },
    denied(err) { return /403|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN/.test([err?.code, err?.bizCode].join(' ')) },
    clearPrivate() {
      this.scope += 1; this.seq += 1; this.loading = false; this.error = ''; this.domains = []
      this.scopeType = ''; this.scopeNote = ''; this.termCode = ''; this.overallResult = 'BLOCKED'; this.blockingCount = 0; this.blockedDomains = 0
    },
    syncRoute() {
      this.clearPrivate()
      const termId = this.$route.query?.termId
      if (this.routeTermError) {
        this.error = this.routeTermError
        return
      }
      this.syncingResolvedTerm = true
      this.termId = termId || ''
      this.$nextTick(() => { this.syncingResolvedTerm = false })
      return this.load()
    },
    onTermChange() {
      this.clearPrivate()
      const termId = String(this.termId || '')
      if (termId === String(this.$route.query?.termId || '')) return this.load()
      const query = { ...this.$route.query }
      if (termId) query.termId = termId
      else delete query.termId
      return this.$router.replace({ query })
    },
    fail(err, fallback) { if (this.denied(err)) this.clearPrivate(); return gradeError(err, fallback) },
    validDomains(domains) {
      if (!Array.isArray(domains) || domains.length !== ARCHIVE_DOMAINS.length) return false
      const seen = new Set()
      for (const row of domains) {
        if (!row || !ARCHIVE_DOMAINS.includes(row.domain) || seen.has(row.domain) || !DOMAIN_RESULTS.has(row.result)) return false
        seen.add(row.domain)
      }
      return ARCHIVE_DOMAINS.every((domain) => seen.has(domain))
    },
    async load() {
      this.clearPrivate()
      if (this.routeTermError) { this.error = this.routeTermError; return }
      const requestedTerm = String(this.termId || '')
      const c = this.capture(requestedTerm)
      const seq = ++this.seq
      this.loading = true
      this.error = ''
      try {
        const res = await api.precheck(this.termId || undefined)
        if (!this.isCurrent(c) || seq !== this.seq) return
        if (res.code !== 0) throw res
        const data = res.data || {}
        if (requestedTerm && String(data.termId) !== requestedTerm) throw { code: 503, message: '归档预检学期与当前选择不一致' }
        if (!this.validDomains(data.domains)) throw { code: 503, message: '十三域预检结果不完整' }
        const blockedRows = data.domains.filter((d) => ['BLOCKED', 'UNKNOWN'].includes(d.result))
        const derivedResult = blockedRows.some((row) => row.result === 'BLOCKED') ? 'BLOCKED' : blockedRows.length ? 'UNKNOWN' : 'PASS'
        if (!['PASS','BLOCKED','UNKNOWN'].includes(data.result) || data.result !== derivedResult) throw { code: 503, message: '归档预检结论与明细不一致' }
        const fallbackBlockedDomains = blockedRows.length
        const reportedBlockedDomains = Number(data.blockedDomains ?? fallbackBlockedDomains)
        if (!Number.isFinite(reportedBlockedDomains) || reportedBlockedDomains !== fallbackBlockedDomains) throw { code: 503, message: '归档阻断域数量与明细不一致' }
        this.domains = data.domains
        this.scopeType = data.scopeType || ''
        this.scopeNote = data.scopeNote || ''
        this.termCode = data.termCode || ''
        this.overallResult = derivedResult
        this.blockingCount = Number.isFinite(Number(data.blockingCount)) ? Number(data.blockingCount) : blockedRows.reduce((sum, row) => sum + Number(row.blockingCount || 0), 0)
        this.blockedDomains = reportedBlockedDomains
        if (!this.termId && data.termId) {
          // The default-term response resolves the picker value. Do not turn that
          // server-derived assignment into a second full 13-domain precheck.
          this.loading = false
          this.syncingResolvedTerm = true
          this.termId = String(data.termId)
          this.$nextTick(() => { this.syncingResolvedTerm = false })
        }
      } catch (err) {
        if (!this.isCurrent(c) || seq !== this.seq) return
        this.domains = []
        this.error = this.fail(err, '归档预检失败，请稍后重试')
      } finally {
        if (this.isCurrent(c) && seq === this.seq) this.loading = false
      }
    },
    tagType(domain) {
      return { PASS: 'success', BLOCKED: 'danger', UNKNOWN: 'warning', NOT_APPLICABLE: 'info' }[domain.result] || 'warning'
    },
    schoolCheckPending(domain) {
      return this.isCollegeScope && domain.result === 'UNKNOWN' && Array.isArray(domain.evidence) && domain.evidence.some(item => item?.type === 'COLLEGE_ARCHIVE_SCOPE' && item.schoolCheckPerformed === false && item.responsibleOrgType === 'SCHOOL')
    },
    tagLabel(domain) {
      if (this.schoolCheckPending(domain)) return '待学校核验'
      return { PASS: '通过', BLOCKED: '阻断', UNKNOWN: '待处理', NOT_APPLICABLE: '不适用' }[domain.result] || '待确认'
    },
    evidencePreview(evidence) {
      return (evidence || []).slice(0, 5).map((item) => {
        if (typeof item === 'string') return safeBusinessMessage(item, '已记录一条待复核证据')
        if (!item || typeof item !== 'object') return '已记录一条待复核证据'
        const subject = item.studentName || item.courseName || item.className || item.name || item.title
        const message = item.summary || item.message || item.description || item.reason
        const count = Number.isFinite(Number(item.count)) ? `${Number(item.count)} 项` : ''
        const status = item.status ? safeEnumLabel({ value: item.status, unknownLabel: '状态待确认' }) : ''
        const parts = [subject, message && safeBusinessMessage(message, ''), count, status].filter(Boolean)
        return parts.join(' · ') || '已记录一条待复核证据'
      })
    },
    handoffQuery() {
      const query = {}
      if (typeof this.termId === 'string' && /^[1-9]\d*$/.test(this.termId)) query.termId = this.termId
      return query
    },
    jump(domain) {
      const route = domain.route || FALLBACK_ROUTE[domain.domain]
      if (!route) return
      const target = this.$router.resolve(route)
      this.$router.push({ path: target.path, query: { ...this.handoffQuery(), ...target.query } })
    },
    goBatch() {
      const query = this.handoffQuery()
      if (this.$route.query.termId === query.termId && this.$route.query.batchId) query.batchId = this.$route.query.batchId
      this.$router.push({ path: '/admin/academic-affairs/archive', query })
    }
  }
}
</script>

<style scoped>
.aapc-page { gap:10px; }
.aapc-toolbar :deep(.app-form-item) { display:flex;align-items:center;gap:12px; }
.aapc-toolbar :deep(.app-form-item__label) { flex-shrink:0;margin:0; }
.aapc-toolbar :deep(.app-form-item__control) { min-width:0;flex:1; }

.aapc-toolbar { display:flex;align-items:center;flex-wrap:wrap;gap:16px;margin-bottom:4px; }
.aapc-toolbar .app-form-item { width:350px;max-width:100%;margin:0; }
.aapc-toolbar > span,.aapc-note { color:var(--text-secondary,#64748b);font-size:13px; }
.aapc-decision { display:flex;align-items:center;justify-content:space-between;gap:16px;padding:14px 18px;border:1px solid #f5d599;border-radius:8px;background:#fffbef; }
.aapc-decision.is-pass { background:#f0faf5;border-color:#b8dfca; }
.aapc-decision h2 { font-size:16px;margin:0 0 5px; }
.aapc-decision p { font-size:13px;line-height:1.6;margin:0; }
.aapc-counts { display:flex;flex-wrap:wrap;gap:20px;margin:4px 0;font-size:14px; }
.aapc-section,.aapc-passed { background:var(--bg-card,#fff);border:1px solid var(--border-color,#dbe3ee);border-radius:8px;overflow:hidden; }
.aapc-section header { display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;padding:14px 18px;background:var(--fill-light,#f4f7fc); }
.aapc-section h3 { margin:0;font-size:16px; }
.aapc-section header span { color:var(--text-secondary,#64748b);font-size:13px; }
.aapc-section small { display:block;margin-top:6px;color:var(--text-secondary,#64748b);font-size:12px; }
.aapc-section :deep(.dt__td) { vertical-align:top;padding:18px;white-space:normal;overflow-wrap:anywhere; }
.aapc-problem { margin:0;line-height:1.6; }
.aapc-evidence { margin-top:8px;font-size:13px;line-height:1.6; }
.aapc-evidence summary { color:var(--primary-color,#285cba);cursor:pointer; }
.aapc-evidence ul { padding-left:20px;margin:8px 0; }
.aapc-evidence code { overflow-wrap:anywhere; }
.aapc-passed { margin-top:16px; }
.aapc-passed > summary { padding:14px 18px;cursor:pointer;font-weight:600; }
.aapc-passed > summary span { font-size:13px;font-weight:400;color:var(--text-secondary,#64748b);margin-left:16px; }
.aapc-result-row { padding:16px 18px;border-top:1px solid var(--border-color,#dbe3ee); }
.aapc-result-row > strong { margin-right:20px; }
.aapc-result-row > p { font-size:14px;line-height:1.6;margin:8px 0; }
.aapc-result-row.is-na { background:var(--fill-light,#f8fafc); }
.aapc-footnote { color:var(--text-secondary,#64748b);font-size:13px;line-height:1.6;margin:16px 0 0; }
@media(max-width:600px) { .aapc-toolbar { align-items:stretch;flex-direction:column; }.aapc-toolbar .app-form-item { width:100%; }.aapc-decision { align-items:flex-start;flex-direction:column; }.aapc-section :deep(table) { min-width:650px; }.aapc-passed > summary span { display:block;margin:6px 0 0; } }
</style>
