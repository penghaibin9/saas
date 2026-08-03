<template>
  <ModulePageShell
    title="访问治理"
    subtitle="解释为什么能/不能访问、职责分离、紧急访问与权限复核"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="mp-tabs">
        <button class="mp-tab" :class="{ 'is-active': tab === 'explain' }" @click="tab = 'explain'">访问解释</button>
        <button class="mp-tab" :class="{ 'is-active': tab === 'sod' }" @click="switchTo('sod')">职责分离</button>
        <button class="mp-tab" :class="{ 'is-active': tab === 'emergency' }" @click="switchTo('emergency')">紧急访问</button>
        <button class="mp-tab" :class="{ 'is-active': tab === 'review' }" @click="switchTo('review')">权限复核</button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="reload" />

      <!-- 访问解释 -->
      <template v-else-if="tab === 'explain'">
        <section class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">解释一次访问</span>
            <span class="mp-note">结论来自真实鉴权核心，页面不自行推断</span>
          </header>
          <div class="mp-card__body">
            <div class="ag-form">
              <div>
                <label class="ag-label">动作权限码<span class="ag-required">*</span></label>
                <input v-model="explain.actionCode" class="mp-input" placeholder="如 systemAdmin.role.view" />
              </div>
              <div>
                <label class="ag-label">组织类型（可选）</label>
                <select v-model="explain.scopeTargetType" class="mp-input">
                  <option value="">不判数据范围</option>
                  <option value="COLLEGE">学院</option>
                  <option value="MAJOR">专业</option>
                  <option value="CLASS">班级</option>
                </select>
              </div>
              <div>
                <label class="ag-label">组织 id（可选）</label>
                <input v-model="explain.scopeTargetId" class="mp-input" />
              </div>
            </div>
            <AppButton
              variant="primary"
              style="margin-top: var(--space-3)"
              :loading="explain.submitting"
              @click="doExplain"
            >解释</AppButton>
            <p v-if="explain.error" class="mp-form-err">{{ explain.error }}</p>

            <template v-if="explain.result">
              <div class="ag-verdict" :class="explain.result.decision === 'ALLOW' ? 'is-allow' : 'is-deny'">
                {{ explain.result.decision === 'ALLOW' ? '允许' : '拒绝' }}
                <span class="ag-verdict__reason">{{ reasonLabel(explain.result.reasonCode) }}</span>
              </div>
              <p class="mp-note">追踪号 {{ explain.result.traceId }}（真实 403 也会带上它，可据此复现）</p>
              <table class="mp-audit" style="margin-top: var(--space-2)">
                <thead><tr><th style="width: 200px">判定层</th><th style="width: 90px">结果</th><th>说明</th></tr></thead>
                <tbody>
                  <tr v-for="(c, i) in explain.result.chain" :key="i">
                    <td class="is-who">{{ stepLabel(c.step) }}</td>
                    <td>
                      <StatusTag :type="c.pass ? 'success' : 'danger'" :label="c.pass ? '通过' : '未通过'" />
                    </td>
                    <td class="mp-cell-sub">{{ stepDetail(c) }}</td>
                  </tr>
                </tbody>
              </table>
            </template>
          </div>
        </section>

        <section class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">最近的拒绝</span></header>
          <div class="mp-card__body" style="padding-top: 0">
            <table class="mp-audit">
              <thead><tr><th>动作</th><th style="width: 180px">原因</th><th style="width: 130px">角色</th><th style="width: 160px">时间</th></tr></thead>
              <tbody>
                <tr v-for="d in denials" :key="d.traceId">
                  <td class="is-who">{{ d.actionCode }}</td>
                  <td>{{ reasonLabel(d.reasonCode) }}</td>
                  <td>{{ d.activeRole || '—' }}</td>
                  <td class="mp-cell-sub">{{ fmt(d.occurredAt) }}</td>
                </tr>
              </tbody>
            </table>
            <EmptyState v-if="!denials.length" title="暂无拒绝记录" description="" />
          </div>
        </section>
      </template>

      <!-- 职责分离 -->
      <template v-else-if="tab === 'sod'">
        <section class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">职责分离规则</span>
            <AppButton variant="primary" size="small" @click="sodForm.open = true">新增规则</AppButton>
          </header>
          <div class="mp-card__body" style="padding-top: 0">
            <table class="mp-audit">
              <thead><tr><th style="width: 140px">规则</th><th>不得兼任的两个角色</th><th style="width: 90px">严重度</th><th>理由</th></tr></thead>
              <tbody>
                <tr v-for="r in sod.rules" :key="r.ruleCode">
                  <td class="is-who">{{ r.ruleCode }}</td>
                  <td>{{ r.roleA }} ✕ {{ r.roleB }}</td>
                  <td>{{ r.severity }}</td>
                  <td class="mp-cell-sub">{{ r.reason }}</td>
                </tr>
              </tbody>
            </table>
            <EmptyState v-if="!sod.rules.length" title="尚未配置职责分离规则" description="例如资助发放与安全审计不得由同一人兼任" />
          </div>
        </section>

        <section v-if="sod.violations.length" class="mp-card ag-danger-card">
          <header class="mp-card__head"><span class="mp-card__title">已检出的冲突</span></header>
          <div class="mp-card__body" style="padding-top: 0">
            <table class="mp-audit">
              <thead><tr><th style="width: 140px">规则</th><th style="width: 120px">人员</th><th>持有角色</th><th style="width: 90px">状态</th></tr></thead>
              <tbody>
                <tr v-for="v in sod.violations" :key="v.ruleCode + v.subjectUserId">
                  <td class="is-who">{{ v.ruleCode }}</td>
                  <td>{{ v.subjectUserId }}</td>
                  <td class="mp-cell-sub">{{ (v.roles || []).join('、') }}</td>
                  <td><StatusTag type="danger" :label="v.status" /></td>
                </tr>
              </tbody>
            </table>
            <p class="mp-note">检出的冲突在后端会被真实拦截（403），不是只在这里提示。</p>
          </div>
        </section>
      </template>

      <!-- 紧急访问 -->
      <template v-else-if="tab === 'emergency'">
        <section class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">紧急访问</span>
            <AppButton variant="primary" size="small" @click="emergencyForm.open = true">开通紧急访问</AppButton>
          </header>
          <div class="mp-card__body" style="padding-top: 0">
            <table class="mp-audit">
              <thead>
                <tr>
                  <th style="width: 110px">人员</th><th style="width: 130px">临时角色</th>
                  <th style="width: 140px">工单号</th><th style="width: 165px">有效期</th>
                  <th style="width: 90px">状态</th><th style="width: 80px">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="e in emergency" :key="e.sessionCode">
                  <td class="is-who">{{ e.subjectUserId }}</td>
                  <td>{{ e.grantedRole }}</td>
                  <td class="mp-cell-sub">{{ e.ticketRef }}</td>
                  <td class="mp-cell-sub">{{ fmt(e.startedAt) }} ~ {{ fmt(e.expiresAt) }}</td>
                  <td>
                    <StatusTag :type="e.activeNow ? 'warning' : 'default'" :label="e.activeNow ? '生效中' : e.status" />
                  </td>
                  <td>
                    <button v-if="e.activeNow" class="mp-link" @click="revokeEmergency(e)">收回</button>
                    <span v-else class="mp-note">—</span>
                  </td>
                </tr>
              </tbody>
            </table>
            <EmptyState v-if="!emergency.length" title="当前没有紧急访问" description="默认无人长期持有超级权限；紧急访问必须有工单号且最长 8 小时" />
          </div>
        </section>
      </template>

      <!-- 权限复核 -->
      <template v-else>
        <section class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">权限复核</span>
            <AppButton variant="primary" size="small" @click="reviewForm.open = true">发起复核</AppButton>
          </header>
          <div class="mp-card__body" style="padding-top: 0">
            <table class="mp-audit">
              <thead><tr><th>标题</th><th style="width: 100px">状态</th><th style="width: 150px">截止</th><th style="width: 90px">操作</th></tr></thead>
              <tbody>
                <tr v-for="c in reviews" :key="c.campaignId">
                  <td class="is-who">{{ c.title }}<span class="mp-cell-sub">{{ c.campaignCode }}</span></td>
                  <td><StatusTag :type="c.status === 'CLOSED' ? 'success' : 'processing'" :label="reviewStatusLabel(c.status)" /></td>
                  <td class="mp-cell-sub">{{ fmt(c.dueAt) }}</td>
                  <td><button class="mp-link" @click="openReview(c)">详情</button></td>
                </tr>
              </tbody>
            </table>
            <EmptyState v-if="!reviews.length" title="暂无复核活动" description="高权角色建议按季度复核，普通角色按半年" />
          </div>
        </section>
      </template>
    </div>

    <AppDrawer v-model:visible="sodForm.open" title="新增职责分离规则">
      <label class="ag-label">规则编码<span class="ag-required">*</span></label>
      <input v-model="sodForm.ruleCode" class="mp-input" placeholder="如 SOD-FUND-AUDIT" />
      <label class="ag-label">角色 A<span class="ag-required">*</span></label>
      <input v-model="sodForm.roleA" class="mp-input" placeholder="如 FUNDING_ADMIN" />
      <label class="ag-label">角色 B<span class="ag-required">*</span></label>
      <input v-model="sodForm.roleB" class="mp-input" placeholder="如 SECURITY_AUDITOR" />
      <label class="ag-label">为什么不能兼任<span class="ag-required">*</span></label>
      <textarea v-model="sodForm.reason" class="mp-textarea" rows="2" placeholder="至少 5 个字" />
      <div v-if="sodForm.error" class="mp-form-err">{{ sodForm.error }}</div>
      <template #footer>
        <AppButton variant="ghost" @click="sodForm.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="sodForm.submitting" @click="submitSod">创建</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer v-model:visible="emergencyForm.open" title="开通紧急访问">
      <p class="ag-tip">紧急访问必须关联工单或事件号，且最长 8 小时——不存在无限期的紧急权限。</p>
      <label class="ag-label">人员 userId<span class="ag-required">*</span></label>
      <input v-model="emergencyForm.subjectUserId" class="mp-input" />
      <label class="ag-label">临时角色<span class="ag-required">*</span></label>
      <input v-model="emergencyForm.grantedRole" class="mp-input" placeholder="如 SYS_ADMIN" />
      <label class="ag-label">工单/事件号<span class="ag-required">*</span></label>
      <input v-model="emergencyForm.ticketRef" class="mp-input" placeholder="如 INC-2026-001" />
      <label class="ag-label">时长（分钟，最长 480）<span class="ag-required">*</span></label>
      <input v-model="emergencyForm.minutes" type="number" class="mp-input" />
      <label class="ag-label">开通理由<span class="ag-required">*</span></label>
      <textarea v-model="emergencyForm.reason" class="mp-textarea" rows="2" placeholder="至少 5 个字" />
      <div v-if="emergencyForm.error" class="mp-form-err">{{ emergencyForm.error }}</div>
      <template #footer>
        <AppButton variant="ghost" @click="emergencyForm.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="emergencyForm.submitting" @click="submitEmergency">开通</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer v-model:visible="reviewForm.open" title="发起权限复核">
      <label class="ag-label">标题<span class="ag-required">*</span></label>
      <input v-model="reviewForm.title" class="mp-input" placeholder="如 2026 春季高权角色复核" />
      <label class="ag-label">截止时间</label>
      <input v-model="reviewForm.dueAt" type="datetime-local" class="mp-input" />
      <div v-if="reviewForm.error" class="mp-form-err">{{ reviewForm.error }}</div>
      <template #footer>
        <AppButton variant="ghost" @click="reviewForm.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="reviewForm.submitting" @click="submitReview">创建</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer v-model:visible="reviewDetail.open" :title="reviewDetail.title">
      <LoadingState v-if="reviewDetail.loading" />
      <template v-else-if="reviewDetail.data">
        <p class="mp-note">
          待处理 {{ reviewDetail.data.pendingCount }} 条。还有未给结论的条目时不能关闭复核——
          复核不能"到期自动算过"。
        </p>
        <table v-if="reviewDetail.data.items.length" class="mp-audit" style="margin-top: var(--space-2)">
          <thead><tr><th style="width: 110px">人员</th><th style="width: 140px">角色</th><th style="width: 110px">结论</th><th>备注</th></tr></thead>
          <tbody>
            <tr v-for="i in reviewDetail.data.items" :key="i.itemId">
              <td class="is-who">{{ i.subjectUserId }}</td>
              <td>{{ i.roleCode }}</td>
              <td>{{ i.decision ? reviewDecisionLabel(i.decision) : '待处理' }}</td>
              <td class="mp-cell-sub">{{ i.note || '—' }}</td>
            </tr>
          </tbody>
        </table>
        <EmptyState v-else title="暂无复核条目" description="" />
      </template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
/**
 * 访问治理（/admin/system/access-governance）。
 * 解释结论由后端真实鉴权核心给出；页面只展示判定链，绝不自行推断——
 * 前端重算一遍必然与后端漂移，那样的"解释"会骗人。
 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState, StatusTag } from '@/components/business'
import { AppButton } from '@/components/ui'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

const STEP_LABEL = {
  SUPER_ADMIN: '超级管理员直通',
  ACTIVE_ROLE: '当前激活角色',
  PERMISSION_PATTERNS: '生效的权限范围',
  ROLE_DENY: '角色级显式禁止',
  PERMISSION_CHECK: '权限判定（权威）',
  DATA_SCOPE: '数据范围',
  EMERGENCY_ACCESS: '紧急访问',
  SELF_CHECK: '解释器自检'
}

const REASON_LABEL = {
  SUPER_ADMIN_BYPASS: '超级管理员',
  PERMISSION_GRANTED: '已授权',
  PERMISSION_NOT_GRANTED: '未授予该权限',
  ROLE_EXPLICIT_DENY: '该角色被显式禁止',
  DATA_SCOPE_DENIED: '数据范围拒绝',
  EXPLAINER_DRIFT: '解释器与鉴权核心不一致（需修复）'
}

export default {
  name: 'SystemAccessGovernanceView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, StatusTag, AppButton, AppDrawer },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      tab: 'explain',
      error: '',
      denials: [],
      sod: { rules: [], violations: [] },
      emergency: [],
      reviews: [],
      explain: {
        actionCode: '', scopeTargetType: '', scopeTargetId: '',
        result: null, error: '', submitting: false
      },
      sodForm: { open: false, ruleCode: '', roleA: '', roleB: '', reason: '', error: '', submitting: false },
      emergencyForm: {
        open: false, subjectUserId: '', grantedRole: '', ticketRef: '',
        minutes: 60, reason: '', error: '', submitting: false
      },
      reviewForm: { open: false, title: '', dueAt: '', error: '', submitting: false },
      reviewDetail: { open: false, loading: false, title: '', data: null }
    }
  },
  created() { this.loadDenials() },
  methods: {
    fmt(v) { return v ? String(v).replace('T', ' ').slice(0, 16) : '—' },
    stepLabel(s) { return STEP_LABEL[s] || s },
    reasonLabel(r) { return REASON_LABEL[r] || r },
    reviewStatusLabel(s) { return ({ DRAFT: '草稿', RUNNING: '进行中', CLOSED: '已关闭' })[s] || s },
    reviewDecisionLabel(d) {
      return ({ KEEP: '保留', ADJUST: '调整', REVOKE: '回收', EXCEPTION: '例外' })[d] || d
    },
    stepDetail(c) {
      if (c.roleCode) return `角色 ${c.roleCode}`
      if (c.patternCount !== undefined) return `共 ${c.patternCount} 条权限范围`
      if (c.actionCode) return c.actionCode
      if (c.reasonCode) return this.reasonLabel(c.reasonCode)
      if (c.expiresAt) return `有效至 ${this.fmt(c.expiresAt)}`
      if (c.note) return c.note
      return '—'
    },

    async switchTo(tab) {
      this.tab = tab
      if (tab === 'sod') await this.loadSod()
      if (tab === 'emergency') await this.loadEmergency()
      if (tab === 'review') await this.loadReviews()
    },
    reload() {
      this.error = ''
      this.switchTo(this.tab)
    },

    async loadDenials() {
      const res = await systemApi.getAccessDenials()
      if (res.code === 0) this.denials = (res.data || {}).items || []
    },
    async loadSod() {
      const res = await systemApi.getSodRules()
      if (res.code === 0) this.sod = res.data || { rules: [], violations: [] }
      else this.error = res.message
    },
    async loadEmergency() {
      const res = await systemApi.getEmergencySessions()
      if (res.code === 0) this.emergency = (res.data || {}).items || []
      else this.error = res.message
    },
    async loadReviews() {
      const res = await systemApi.getAccessReviews()
      if (res.code === 0) this.reviews = (res.data || {}).items || []
      else this.error = res.message
    },

    async doExplain() {
      if (!this.explain.actionCode.trim()) { this.explain.error = '请填写动作权限码'; return }
      this.explain.submitting = true
      this.explain.error = ''
      const res = await systemApi.explainAccess({
        actionCode: this.explain.actionCode.trim(),
        scopeTargetType: this.explain.scopeTargetType || null,
        scopeTargetId: this.explain.scopeTargetId || null
      })
      this.explain.submitting = false
      if (res.code === 0) {
        this.explain.result = res.data
        this.loadDenials()
      } else {
        this.explain.error = res.message
      }
    },

    async submitSod() {
      if (!this.sodForm.ruleCode || !this.sodForm.roleA || !this.sodForm.roleB) {
        this.sodForm.error = '规则编码与两个角色都必填'
        return
      }
      if (this.sodForm.reason.trim().length < 5) { this.sodForm.error = '理由不少于 5 个字'; return }
      this.sodForm.submitting = true
      const res = await systemApi.createSodRule({
        ruleCode: this.sodForm.ruleCode.trim(),
        roleA: this.sodForm.roleA.trim(),
        roleB: this.sodForm.roleB.trim(),
        reason: this.sodForm.reason.trim()
      })
      this.sodForm.submitting = false
      if (res.code === 0) {
        toast.success('规则已创建')
        this.sodForm.open = false
        this.loadSod()
      } else {
        this.sodForm.error = res.message
      }
    },

    async submitEmergency() {
      const f = this.emergencyForm
      if (!f.subjectUserId || !f.grantedRole || !f.ticketRef) {
        f.error = '人员、角色、工单号都必填'
        return
      }
      if (f.reason.trim().length < 5) { f.error = '开通理由不少于 5 个字'; return }
      f.submitting = true
      const res = await systemApi.grantEmergencySession({
        subjectUserId: Number(f.subjectUserId),
        grantedRole: f.grantedRole.trim(),
        ticketRef: f.ticketRef.trim(),
        minutes: Number(f.minutes) || 60,
        reason: f.reason.trim()
      })
      f.submitting = false
      if (res.code === 0) {
        toast.success('紧急访问已开通，到期自动失效')
        f.open = false
        this.loadEmergency()
      } else {
        f.error = res.message
      }
    },

    async revokeEmergency(row) {
      const res = await systemApi.revokeEmergencySession(row.sessionCode, { reason: '管理员提前收回' })
      if (res.code === 0) {
        toast.success('已收回')
        this.loadEmergency()
      } else {
        toast.error(res.message)
      }
    },

    async submitReview() {
      if (!this.reviewForm.title.trim()) { this.reviewForm.error = '请填写标题'; return }
      this.reviewForm.submitting = true
      const res = await systemApi.createAccessReview({
        title: this.reviewForm.title.trim(),
        dueAt: this.reviewForm.dueAt ? new Date(this.reviewForm.dueAt).toISOString() : null
      })
      this.reviewForm.submitting = false
      if (res.code === 0) {
        toast.success('复核活动已创建')
        this.reviewForm.open = false
        this.loadReviews()
      } else {
        this.reviewForm.error = res.message
      }
    },

    async openReview(c) {
      this.reviewDetail = { open: true, loading: true, title: `${c.title} · 明细`, data: null }
      const res = await systemApi.getAccessReviewDetail(c.campaignId)
      this.reviewDetail.loading = false
      if (res.code === 0) this.reviewDetail.data = res.data
      else toast.error(res.message)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ag-form { display: flex; gap: var(--space-3); flex-wrap: wrap; }
.ag-form > div { flex: 1; min-width: 200px; }
.ag-label { display: block; margin-top: var(--space-3); margin-bottom: var(--space-1); font-size: var(--font-size-sm); }
.ag-required { color: var(--danger-600); }
.ag-tip { margin: 0; font-size: var(--font-size-sm); color: var(--text-secondary); }
.ag-verdict {
  margin-top: var(--space-4); padding: var(--space-3);
  border-radius: var(--radius-md); font-size: var(--font-size-lg); font-weight: 600;
}
.ag-verdict.is-allow { background: var(--fill-secondary); color: var(--success-600, var(--text-primary)); }
.ag-verdict.is-deny { background: var(--fill-secondary); color: var(--danger-600); }
.ag-verdict__reason { margin-left: var(--space-2); font-size: var(--font-size-sm); font-weight: normal; color: var(--text-secondary); }
.ag-danger-card { border-left: 3px solid var(--danger-600); }
</style>
