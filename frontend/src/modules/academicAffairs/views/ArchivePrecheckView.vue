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
        <strong>{{ overallResult === 'PASS' ? '可以进入归档批次' : '必须先处理阻断项' }}</strong>
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
          <small>后端返回的业务语义域</small>
        </article>
        <article class="is-pass">
          <span>已通过域</span>
          <strong>{{ passedDomains }}</strong>
          <small>当前无需处理</small>
        </article>
        <article :class="{ 'is-risk': blockedDomains > 0 }">
          <span>阻断域</span>
          <strong>{{ blockedDomains }}</strong>
          <small>{{ blockedDomains ? '按阻断数量优先处理' : '当前无阻断域' }}</small>
        </article>
        <article :class="{ 'is-risk': blockingCount > 0 }">
          <span>阻断项</span>
          <strong>{{ blockingCount }}</strong>
          <small>来自十三域实时语义检查</small>
        </article>
      </section>

      <section v-if="blockedDomainRows.length" class="aapc-section is-blocker">
        <header class="aapc-section-head">
          <div>
            <span class="aapc-eyebrow">优先处理</span>
            <h3>归档阻断域</h3>
            <p>按阻断项数量从高到低排列；先处理最影响归档闭环的业务域，再重新检查。</p>
          </div>
          <span class="aapc-count is-danger">{{ blockedDomainRows.length }} 个阻断域</span>
        </header>
        <div class="aapc-grid">
          <article v-for="d in blockedDomainRows" :key="d.domain" class="aapc-card is-missing">
            <header class="aapc-card-head">
              <div>
                <span class="aapc-card-title">{{ d.domainLabel }}</span>
                <code>{{ d.ruleCode || `${d.domain}_SEMANTIC_GATE` }}</code>
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
              <pre>{{ evidencePreview(d.evidence) }}</pre>
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
            <span class="aapc-eyebrow">完成证据</span>
            <h3>已通过业务域</h3>
            <p>这些域已满足当前归档语义门禁，保留规则编号与证据供复核，不与阻断项混排。</p>
          </div>
          <span class="aapc-count">{{ passedDomainRows.length }} 个通过域</span>
        </header>
        <div class="aapc-grid">
          <article v-for="d in passedDomainRows" :key="d.domain" class="aapc-card is-ok">
            <header class="aapc-card-head">
              <div>
                <span class="aapc-card-title">{{ d.domainLabel }}</span>
                <code>{{ d.ruleCode || `${d.domain}_SEMANTIC_GATE` }}</code>
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
              <pre>{{ evidencePreview(d.evidence) }}</pre>
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
      return Math.max(this.domains.length - this.blockedDomains, 0)
    },
    blockedDomainRows() {
      return this.domains
        .filter((domain) => domain.result !== 'PASS')
        .slice()
        .sort((a, b) => Number(b.blockingCount || 0) - Number(a.blockingCount || 0))
    },
    passedDomainRows() {
      return this.domains.filter((domain) => domain.result === 'PASS')
    },
    firstBlockingDomain() {
      return this.blockedDomainRows[0] || null
    },
    overallDescription() {
      if (this.overallResult === 'PASS') {
        return `共检查 ${this.domains.length} 个业务域，当前全部满足归档语义门禁。进入归档批次后仍按正式归档状态机执行。`
      }
      return `仍有 ${this.blockedDomains} 个业务域、${this.blockingCount} 个阻断项需要处理；本页只解释后端实时预检结果，不写入归档事实。`
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
  box-shadow: 0 20px 48px -40px rgba(22, 163, 74, .4);
}
.aapc-eyebrow { color: #2b69c9; font-size: 10.5px; font-weight: 750; letter-spacing: .08em; }
.aapc-hero__main h2 { margin: 8px 0 7px; color: #17233a; font-size: 24px; letter-spacing: -.02em; }
.aapc-hero__main > p { max-width: 760px; margin: 0; color: #64748b; font-size: 12.5px; line-height: 1.75; }
.aapc-toolbar { display: flex; align-items: center; gap: 16px; margin-top: 15px; }
.aapc-scope-note { margin-top: 10px; color: #6f7e91; font-size: 10.8px; line-height: 1.6; }
.aapc-decision {
  display: grid;
  align-content: center;
  gap: 8px;
  padding: 18px;
  border: 1px solid rgba(225, 166, 166, .65);
  border-radius: 15px;
  background: rgba(255,255,255,.82);
}
.aapc-hero.is-pass .aapc-decision { border-color: #cae8d2; }
.aapc-decision > span, .aapc-next small { color: #8793a5; font-size: 10px; }
.aapc-decision > strong { color: #ad3838; font-size: 17px; }
.aapc-hero.is-pass .aapc-decision > strong { color: #18794e; }
.aapc-next { display: grid; gap: 3px; padding-top: 9px; border-top: 1px solid #e8edf4; }
.aapc-next b { color: #27364c; font-size: 11px; line-height: 1.55; }

.aapc-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0,1fr));
  gap: 10px;
  margin-bottom: 14px;
}
.aapc-metrics article {
  padding: 15px 16px;
  border: 1px solid #e3eaf3;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 12px 26px -26px rgba(15,23,42,.55);
}
.aapc-metrics span, .aapc-metrics strong, .aapc-metrics small { display: block; }
.aapc-metrics span { color: #78879a; font-size: 10.5px; }
.aapc-metrics strong { margin-top: 5px; color: #172033; font-size: 22px; font-variant-numeric: tabular-nums; }
.aapc-metrics small { margin-top: 4px; color: #97a2b2; font-size: 9.8px; line-height: 1.4; }
.aapc-metrics article.is-pass strong { color: #18794e; }
.aapc-metrics article.is-risk { border-color: #efc7c7; background: #fffafa; }
.aapc-metrics article.is-risk strong { color: #b33b3b; }

.aapc-section {
  margin-top: 14px;
  overflow: hidden;
  border: 1px solid #e3eaf4;
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 14px 34px -30px rgba(15,23,42,.38);
}
.aapc-section.is-blocker { border-color: #efc7c7; }
.aapc-section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 20px;
  border-bottom: 1px solid #edf1f7;
  background: linear-gradient(180deg,#fff,#fcfdff);
}
.aapc-section-head h3 { margin: 4px 0 0; color: #172033; font-size: 16px; }
.aapc-section-head p { margin: 5px 0 0; color: #718096; font-size: 11px; line-height: 1.6; }
.aapc-count { flex-shrink: 0; padding: 5px 9px; border-radius: 999px; background: #eef5ff; color: #2468d8; font-size: 10.5px; font-weight: 700; }
.aapc-count.is-danger { background: #fff0f0; color: #b53d3d; }

.aapc-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 12px; padding: 14px; }
.aapc-card { display: flex; flex-direction: column; min-height: 245px; padding: 16px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 12px; background: #fff; }
.aapc-card.is-missing { border-color: #efb0b0; background: #fffdfd; }
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

@media (max-width: 900px) {
  .aapc-hero { grid-template-columns: 1fr; }
  .aapc-metrics { grid-template-columns: repeat(2, minmax(0,1fr)); }
}
@media (max-width: 600px) {
  .aapc-hero { padding: 20px; }
  .aapc-metrics { grid-template-columns: 1fr; }
  .aapc-section-head { flex-direction: column; }
}
</style>
