<template>
  <ModulePageShell
    title="教务归档 · 语义预检"
    subtitle="按业务完成状态判断能否归档；阻断域优先处理，通过域作为完成证据保留"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="ghost" :loading="loading" @click="load">重新检查</AppButton>
      <AppButton variant="primary" @click="goBatch">进入归档批次</AppButton>
    </template>

    <section class="aapc-hero" :class="overallResult === 'PASS' ? 'is-pass' : 'is-blocked'">
      <div class="aapc-hero__main">
        <span class="aapc-eyebrow">{{ termCode || '当前学期' }} · 归档前置门禁</span>
        <h2>{{ overallResult === 'PASS' ? '当前满足归档语义门禁' : '当前仍有业务阻断，暂不可归档' }}</h2>
        <p>{{ overallDescription }}</p>

        <div class="aapc-toolbar">
          <AppFormItem label="学期">
            <AppTermEntityPicker v-model="termId" placeholder="默认当前学期" @change="load" />
          </AppFormItem>
        </div>

        <div v-if="scopeNote" class="aapc-scope-note">{{ scopeNote }}</div>
      </div>

      <aside class="aapc-decision">
        <span>当前结论</span>
        <strong>{{ overallResult === 'PASS' ? '可以进入归档批次' : '必须先处理阻断 / 待治理项' }}</strong>
        <div class="aapc-next">
          <small>建议下一动作</small>
          <b>{{ nextActionText }}</b>
        </div>
        <AppButton
          v-if="firstBlockingDomain"
          size="small"
          variant="ghost"
          @click="jump(firstBlockingDomain)"
        >去处理首要阻断</AppButton>
      </aside>
    </section>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <EmptyState v-else-if="!domains.length" title="暂无可检查内容" description="请选择学期后重新检查" />
    <template v-else>
      <section class="aapc-metrics" aria-label="归档预检关键指标">
        <article>
          <span>检查域</span>
          <strong>{{ domains.length }}</strong>
          <small>系统已完成业务语义检查</small>
        </article>
        <article class="is-pass">
          <span>已通过域</span>
          <strong>{{ passedDomains }}</strong>
          <small>当前无需处理</small>
        </article>
        <article :class="{ 'is-risk': blockedDomains > 0 }">
          <span>阻断 / 待治理域</span>
          <strong>{{ blockedDomains }}</strong>
          <small>{{ blockedDomains ? 'BLOCKED 与 UNKNOWN 均不得进入正式归档' : '当前无阻断或待治理域' }}</small>
        </article>
        <article :class="{ 'is-risk': blockingCount > 0 }">
          <span>阻断项</span>
          <strong>{{ blockingCount }}</strong>
          <small>来自十三域当前语义检查</small>
        </article>
      </section>

      <section v-if="blockedDomainRows.length" class="aapc-section is-blocker">
        <header class="aapc-section-head">
          <div>
            <span class="aapc-eyebrow">优先处理</span>
            <h3>归档阻断 / 待治理域</h3>
            <p>BLOCKED 是已知业务阻断，UNKNOWN 是证据不足待治理；两者都不得绿色放行，处理后再重新检查。</p>
          </div>
          <span class="aapc-count is-danger">{{ blockedDomainRows.length }} 个阻断 / 待治理域</span>
        </header>
        <div class="aapc-grid">
          <article v-for="d in blockedDomainRows" :key="d.domain" class="aapc-card is-missing">
            <header class="aapc-card-head">
              <div>
                <span class="aapc-card-title">{{ d.domainLabel }}</span>
                <small>归档校验规则</small>
              </div>
              <StatusTag :type="tagType(d)" :label="tagLabel(d)" dot />
            </header>

            <div class="aapc-card-metrics">
              <div><b>{{ d.recordCount || 0 }}</b><span>业务记录</span></div>
              <div class="danger"><b>{{ d.blockingCount || 0 }}</b><span>阻断项</span></div>
            </div>

            <p class="aapc-card-note">{{ d.summary || d.note || '未返回检查摘要' }}</p>

            <details v-if="Array.isArray(d.evidence) && d.evidence.length" class="aapc-evidence">
              <summary>查看证据（{{ d.evidence.length }}）</summary>
              <ul>
                <li v-for="(item, index) in evidencePreview(d.evidence)" :key="index">{{ item }}</li>
              </ul>
            </details>
            <details v-if="d.ruleCode" class="aapc-evidence">
              <summary>技术依据</summary>
              <code>{{ d.ruleCode }}</code>
            </details>

            <footer class="aapc-card-actions">
              <span>修复后重新执行语义预检</span>
              <AppButton size="small" variant="ghost" @click="jump(d)">去处理</AppButton>
            </footer>
          </article>
        </div>
      </section>

      <section v-if="passedDomainRows.length" class="aapc-section">
        <header class="aapc-section-head">
          <div>
            <span class="aapc-eyebrow">非阻断证据</span>
            <h3>已满足门禁的业务域</h3>
            <p>PASS 表示已证明完成；NOT_APPLICABLE 表示本学期明确不适用。两者均非阻断，但不得混成同一个“通过”。</p>
          </div>
          <span class="aapc-count">{{ passedDomainRows.length }} 个非阻断域</span>
        </header>
        <div class="aapc-grid">
          <article v-for="d in passedDomainRows" :key="d.domain" :class="['aapc-card', d.result === 'NOT_APPLICABLE' ? 'is-na' : 'is-ok']">
            <header class="aapc-card-head">
              <div>
                <span class="aapc-card-title">{{ d.domainLabel }}</span>
                <small>归档校验规则</small>
              </div>
              <StatusTag :type="tagType(d)" :label="tagLabel(d)" dot />
            </header>

            <div class="aapc-card-metrics">
              <div><b>{{ d.recordCount || 0 }}</b><span>业务记录</span></div>
              <div><b>{{ d.blockingCount || 0 }}</b><span>阻断项</span></div>
            </div>

            <p class="aapc-card-note">{{ d.summary || d.note || '未返回检查摘要' }}</p>

            <details v-if="Array.isArray(d.evidence) && d.evidence.length" class="aapc-evidence">
              <summary>查看证据（{{ d.evidence.length }}）</summary>
              <ul>
                <li v-for="(item, index) in evidencePreview(d.evidence)" :key="index">{{ item }}</li>
              </ul>
            </details>
            <details v-if="d.ruleCode" class="aapc-evidence">
              <summary>技术依据</summary>
              <code>{{ d.ruleCode }}</code>
            </details>

            <footer class="aapc-card-actions">
              <span>当前无需处理</span>
            </footer>
          </article>
        </div>
      </section>
    </template>
  </ModulePageShell>
</template>

<script>
/** PageId AA-ARCHIVE-PRECHECK-01：结构化语义预检，不落库。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState, StatusTag } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppTermEntityPicker, AppFormItem } from '@/components/common'
import { academicAffairsApi, academicAffairsArchiveApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { safeBusinessMessage, safeEnumLabel } from '@/utils/presentationSafety'

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

export default {
  name: 'ArchivePrecheckView',
  components: {
    ModulePageShell, LoadingState, ErrorState, EmptyState,
    StatusTag, AppButton, AppTermEntityPicker, AppFormItem
  },
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
  computed: {
    passedDomains() {
      return this.domains.filter((domain) => domain.result === 'PASS').length
    },
    blockedDomainRows() {
      return this.domains
        .filter((domain) => ['BLOCKED', 'UNKNOWN'].includes(domain.result))
        .slice()
        .sort((a, b) => Number(b.blockingCount || 0) - Number(a.blockingCount || 0))
    },
    passedDomainRows() {
      return this.domains.filter((domain) => ['PASS', 'NOT_APPLICABLE'].includes(domain.result))
    },
    firstBlockingDomain() {
      return this.blockedDomainRows[0] || null
    },
    overallDescription() {
      if (this.overallResult === 'PASS') {
        return `共检查 ${this.domains.length} 个业务域，当前全部满足归档语义门禁。进入归档批次后仍按正式归档状态机执行。`
      }
      return `仍有 ${this.blockedDomains} 个阻断 / 待治理业务域、${this.blockingCount} 个阻断项需要处理；UNKNOWN 不会被当成 PASS，本页不写入归档事实。`
    },
    nextActionText() {
      if (!this.firstBlockingDomain) return '进入归档批次继续正式归档流程'
      return `先处理「${this.firstBlockingDomain.domainLabel}」的 ${Number(this.firstBlockingDomain.blockingCount || 0)} 个阻断项`
    }
  },
  async created() {
    try {
      const context = await academicAffairsApi.getContext()
      if (context.code === 0 && context.data) this.ctx = context.data
    } catch {
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
        const states = new Set(this.domains.map((d) => d.result))
        this.overallResult = data.result || (states.has('BLOCKED') ? 'BLOCKED' : states.has('UNKNOWN') ? 'UNKNOWN' : 'PASS')
        this.blockingCount = Number(data.blockingCount ?? 0)
        const fallbackBlockedDomains = this.domains.filter((d) => ['BLOCKED', 'UNKNOWN'].includes(d.result)).length
        this.blockedDomains = Number(data.blockedDomains ?? fallbackBlockedDomains)
        if (!this.termId && data.termId) this.termId = data.termId
      } catch (err) {
        this.domains = []
        this.error = err?.message || '归档预检失败，请稍后重试'
      } finally {
        this.loading = false
      }
    },
    tagType(domain) {
      return { PASS: 'success', BLOCKED: 'danger', UNKNOWN: 'warning', NOT_APPLICABLE: 'info' }[domain.result] || 'warning'
    },
    tagLabel(domain) {
      return { PASS: '通过', BLOCKED: '阻断', UNKNOWN: '待治理', NOT_APPLICABLE: '不适用' }[domain.result] || '待确认'
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
    jump(domain) {
      const path = domain.route || FALLBACK_ROUTE[domain.domain]
      if (path) this.$router.push(path)
    },
    goBatch() { this.$router.push('/admin/academic-affairs/archive') }
  }
}
</script>

<style scoped>
.aapc-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 285px;
  gap: 24px;
  margin-bottom: 14px;
  padding: 24px 26px;
  border: 1px solid #efc0c0;
  border-radius: 20px;
  background:
    radial-gradient(circle at 90% 12%, rgba(239, 68, 68, .10), transparent 30%),
    linear-gradient(135deg, #fff 0%, #fffafa 62%, #fff3f3 100%);
  box-shadow: 0 20px 48px -40px rgba(185, 28, 28, .46);
}
.aapc-hero.is-pass {
  border-color: #bfe2c8;
  background:
    radial-gradient(circle at 90% 12%, rgba(34, 197, 94, .11), transparent 30%),
    linear-gradient(135deg, #fff 0%, #fbfffc 62%, #f0fbf3 100%);
  box-shadow: 0 20px 48px -40px rgba(22, 101, 52, .36);
}
.aapc-hero__main h2 { margin: 8px 0 6px; color: #1f2937; font-size: 23px; }
.aapc-hero__main > p { max-width: 760px; margin: 0; color: #64748b; font-size: 12.5px; line-height: 1.7; }
.aapc-eyebrow { color: #b45309; font-size: 10.5px; font-weight: 700; letter-spacing: .06em; }
.aapc-hero.is-pass .aapc-eyebrow { color: #237a43; }
.aapc-toolbar { width: min(420px, 100%); margin-top: 16px; }
.aapc-scope-note { margin-top: 10px; color: #8b6a24; font-size: 10px; line-height: 1.5; }
.aapc-decision {
  display: grid;
  align-content: center;
  gap: 8px;
  padding: 18px;
  border: 1px solid #f1c7c7;
  border-radius: 15px;
  background: rgba(255,255,255,.84);
}
.aapc-hero.is-pass .aapc-decision { border-color: #c7e5ce; }
.aapc-decision > span,
.aapc-next small { color: #8b96a8; font-size: 10px; }
.aapc-decision > strong { color: #b42318; font-size: 16px; line-height: 1.45; }
.aapc-hero.is-pass .aapc-decision > strong { color: #237a43; }
.aapc-next { display: grid; gap: 4px; padding-top: 9px; border-top: 1px solid #edf0f4; }
.aapc-next b { color: #354154; font-size: 11px; line-height: 1.5; }

.aapc-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0,1fr));
  margin-bottom: 14px;
  overflow: hidden;
  border: 1px solid #e3e9f0;
  border-radius: 14px;
  background: #fff;
}
.aapc-metrics article { padding: 14px 18px; border-right: 1px solid #edf0f4; }
.aapc-metrics article:last-child { border-right: 0; }
.aapc-metrics span, .aapc-metrics strong, .aapc-metrics small { display: block; }
.aapc-metrics span { color: #7c8798; font-size: 10px; }
.aapc-metrics strong { margin-top: 4px; color: #253044; font-size: 22px; font-variant-numeric: tabular-nums; }
.aapc-metrics small { margin-top: 3px; color: #98a3b3; font-size: 9px; line-height: 1.4; }
.aapc-metrics article.is-pass strong { color: #237a43; }
.aapc-metrics article.is-risk { background: #fff9f5; }
.aapc-metrics article.is-risk strong { color: #b42318; }

.aapc-section {
  margin-bottom: 14px;
  padding: 18px;
  border: 1px solid #e5eaf0;
  border-radius: 15px;
  background: #fff;
}
.aapc-section.is-blocker { border-color: #efcece; background: #fffdfd; }
.aapc-section-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 18px; margin-bottom: 14px; }
.aapc-section-head h3 { margin: 4px 0 3px; color: #263349; font-size: 17px; }
.aapc-section-head p { margin: 0; color: #7a8698; font-size: 10.5px; line-height: 1.55; }
.aapc-count { flex: none; color: #557086; font-size: 11px; }
.aapc-count.is-danger { color: #b42318; }
.aapc-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 10px; }
.aapc-card {
  min-width: 0;
  padding: 14px;
  border: 1px solid #e4e9ef;
  border-radius: 12px;
  background: #fbfcfd;
}
.aapc-card.is-missing { border-color: #efcccc; background: #fffafa; }
.aapc-card.is-ok { border-color: #d7e7dc; background: #fbfefc; }
.aapc-card.is-na { border-color: #d8e2ef; background: #f8fbff; }
.aapc-card.is-na .aapc-card-title { color: #405a78; }
.aapc-card-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.aapc-card-title { display: block; color: #29364a; font-size: 13px; font-weight: 650; }
.aapc-card-head small { color: #9aa4b2; font-size: 9px; }
.aapc-card-metrics { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 8px; margin: 12px 0 10px; }
.aapc-card-metrics > div { padding: 8px 10px; border-radius: 8px; background: #f3f6f9; }
.aapc-card-metrics b, .aapc-card-metrics span { display: block; }
.aapc-card-metrics b { color: #334155; font-size: 15px; }
.aapc-card-metrics span { margin-top: 2px; color: #8a95a6; font-size: 9px; }
.aapc-card-metrics .danger b { color: #b42318; }
.aapc-card-note { min-height: 34px; margin: 0 0 9px; color: #667085; font-size: 10.5px; line-height: 1.6; }
.aapc-evidence { margin-top: 7px; color: #697586; font-size: 10px; }
.aapc-evidence summary { cursor: pointer; color: #475569; }
.aapc-evidence ul { margin: 6px 0 0; padding-left: 18px; }
.aapc-evidence li { margin: 3px 0; line-height: 1.55; }
.aapc-evidence code { display: block; margin-top: 5px; overflow-wrap: anywhere; color: #5c6675; font-size: 9px; }
.aapc-card-actions { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-top: 11px; padding-top: 10px; border-top: 1px solid #edf0f3; color: #9aa3af; font-size: 9.5px; }

@media (max-width: 900px) {
  .aapc-hero { grid-template-columns: 1fr; padding: 20px; }
  .aapc-metrics { grid-template-columns: repeat(2, minmax(0,1fr)); }
}
@media (max-width: 600px) {
  .aapc-hero { padding: 17px; }
  .aapc-hero__main h2 { font-size: 19px; }
  .aapc-metrics { grid-template-columns: 1fr; }
  .aapc-metrics article { border-right: 0; border-bottom: 1px solid #edf0f4; }
  .aapc-metrics article:last-child { border-bottom: 0; }
  .aapc-grid { grid-template-columns: 1fr; }
  .aapc-section { padding: 14px; }
  .aapc-section-head { align-items: flex-start; flex-direction: column; gap: 6px; }
}
</style>
