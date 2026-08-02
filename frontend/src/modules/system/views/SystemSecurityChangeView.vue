<template>
  <ModulePageShell
    title="安全变更"
    subtitle="草稿、审核、排期期间不会改变任何人的权限；只有激活才生效，且可回滚"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />

      <template v-else>
        <section class="mp-card sc-hero">
          <div>
            <span class="sc-hero__label">当前安全版本号</span>
            <strong class="sc-hero__value">{{ currentRevision }}</strong>
            <p class="sc-hero__hint">
              每次激活或回滚都会让它 +1。版本号只进不退——回滚也产生新版本，
              这样任何时刻都能解释清楚"当时到底是什么状态"。
            </p>
          </div>
          <AppButton variant="primary" @click="openCreate">新建安全变更</AppButton>
        </section>

        <section class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">变更列表</span>
            <span class="mp-note">草稿与排期不影响真实权限</span>
          </header>
          <div class="mp-card__body" style="padding-top: 0">
            <table class="mp-audit">
              <thead>
                <tr>
                  <th>标题</th>
                  <th style="width: 110px">状态</th>
                  <th style="width: 90px">风险</th>
                  <th style="width: 150px">计划生效</th>
                  <th style="width: 90px">生效版本</th>
                  <th style="width: 240px">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="c in changes" :key="c.changeSetId">
                  <td class="is-who">
                    {{ c.title }}
                    <span class="mp-cell-sub">{{ c.changeCode }}</span>
                  </td>
                  <td><StatusTag :type="statusType(c.status)" :label="statusLabel(c.status)" /></td>
                  <td>{{ riskLabel(c.riskLevel) }}</td>
                  <td class="mp-cell-sub">{{ fmt(c.scheduledAt) }}</td>
                  <td class="mp-cell-sub">{{ c.activatedRevision ?? '—' }}</td>
                  <td>
                    <button class="mp-link" @click="openDetail(c)">详情</button>
                    <button
                      v-for="t in c.allowedTransitions"
                      :key="t"
                      class="mp-link"
                      :class="{ 'sc-danger': t === 'ROLLED_BACK' || t === 'REJECTED' }"
                      @click="openTransition(c, t)"
                    >{{ actionLabel(t) }}</button>
                  </td>
                </tr>
              </tbody>
            </table>
            <EmptyState
              v-if="!changes.length"
              title="暂无安全变更"
              description="调整自定义角色权限或数据范围策略时，通过安全变更走审核与激活流程"
            />
          </div>
        </section>

        <section class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">激活历史</span></header>
          <div class="mp-card__body" style="padding-top: 0">
            <table class="mp-audit">
              <thead>
                <tr>
                  <th style="width: 90px">版本</th>
                  <th style="width: 100px">动作</th>
                  <th style="width: 100px">改动条数</th>
                  <th style="width: 160px">时间</th>
                  <th>追踪号</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="a in activations" :key="a.revision">
                  <td class="is-who">{{ a.revision }}</td>
                  <td>
                    <StatusTag :type="a.action === 'ROLLBACK' ? 'warning' : 'success'"
                               :label="a.action === 'ROLLBACK' ? '回滚' : '激活'" />
                  </td>
                  <td>{{ a.itemCount }}</td>
                  <td class="mp-cell-sub">{{ fmt(a.occurredAt) }}</td>
                  <td class="mp-cell-sub">{{ a.traceId }}</td>
                </tr>
              </tbody>
            </table>
            <EmptyState v-if="!activations.length" title="尚无激活记录" description="" />
          </div>
        </section>
      </template>
    </div>

    <AppDrawer v-model:visible="form.open" title="新建安全变更">
      <label class="sc-label">标题<span class="sc-required">*</span></label>
      <input v-model="form.title" class="mp-input" placeholder="如：收回教务管理员的成绩发布权限" />
      <label class="sc-label">风险等级</label>
      <select v-model="form.riskLevel" class="mp-input">
        <option value="NORMAL">一般</option>
        <option value="HIGH">高</option>
        <option value="CRITICAL">极高</option>
      </select>
      <label class="sc-label">变更原因<span class="sc-required">*</span></label>
      <textarea v-model="form.reason" class="mp-textarea" rows="2" placeholder="至少 5 个字" />
      <div v-if="form.error" class="mp-form-err">{{ form.error }}</div>
      <template #footer>
        <AppButton variant="ghost" @click="form.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="form.submitting" @click="submitCreate">创建草稿</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer v-model:visible="detail.open" :title="detail.title">
      <LoadingState v-if="detail.loading" />
      <template v-else-if="detail.data">
        <h4 class="sc-section">改动内容</h4>
        <table v-if="detail.data.items.length" class="mp-audit">
          <thead><tr><th style="width: 130px">对象类型</th><th>对象</th><th>改成什么</th></tr></thead>
          <tbody>
            <tr v-for="i in detail.data.items" :key="i.itemId">
              <td>{{ targetLabel(i.targetType) }}</td>
              <td class="is-who">{{ i.targetId }}</td>
              <td class="mp-cell-sub">{{ describeAfter(i) }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="mp-note">还没有改动内容。</p>

        <template v-if="detail.data.impact && detail.data.impact.items">
          <h4 class="sc-section">影响面（提交审核时算出）</h4>
          <p v-for="(im, idx) in detail.data.impact.items" :key="idx" class="mp-note">
            {{ im.targetId }}：
            <template v-if="im.added && im.added.length">新增 {{ im.added.length }} 项权限；</template>
            <template v-if="im.removed && im.removed.length">收回 {{ im.removed.length }} 项权限；</template>
            <template v-if="!im.added && !im.removed">{{ JSON.stringify(im.change || {}) }}</template>
          </p>
        </template>

        <h4 class="sc-section">流程记录</h4>
        <div class="mp-kv"><span class="mp-kv__k">发起</span><span class="mp-kv__v">{{ fmt(detail.data.submittedAt) }}</span></div>
        <div class="mp-kv">
          <span class="mp-kv__k">复核</span>
          <span class="mp-kv__v">
            {{ fmt(detail.data.reviewedAt) }}
            <span v-if="detail.data.selfReviewed" class="sc-flag">发起人自复核</span>
          </span>
        </div>
        <div class="mp-kv"><span class="mp-kv__k">复核意见</span><span class="mp-kv__v">{{ detail.data.reviewNote || '—' }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">激活</span><span class="mp-kv__v">{{ fmt(detail.data.activatedAt) }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">回滚</span><span class="mp-kv__v">{{ fmt(detail.data.rolledBackAt) }}</span></div>
      </template>
    </AppDrawer>

    <AppDrawer v-model:visible="action.open" :title="action.title">
      <p class="sc-tip">{{ action.tip }}</p>

      <template v-if="action.target === 'SCHEDULED'">
        <label class="sc-label">计划生效时间<span class="sc-required">*</span></label>
        <input v-model="action.scheduledAt" type="datetime-local" class="mp-input" />
      </template>

      <template v-if="action.target === 'APPROVED'">
        <div class="sc-selfreview">
          <p class="sc-selfreview__title">发起人自行复核时，需逐字输入下面这句话</p>
          <p class="sc-selfreview__text">{{ selfReviewText }}</p>
          <input v-model="action.selfReviewAck" class="mp-input" placeholder="请逐字输入上面这句话" />
          <p class="mp-note">
            如果本次由他人复核，此项留空即可。系统在无法确认复核人身份时会按最严格方式处理。
          </p>
        </div>
      </template>

      <label class="sc-label">{{ action.target === 'APPROVED' ? '复核意见' : '原因' }}<span class="sc-required">*</span></label>
      <textarea v-model="action.reason" class="mp-textarea" rows="2" placeholder="至少 5 个字" />

      <div v-if="action.error" class="mp-form-err">{{ action.error }}</div>
      <template #footer>
        <AppButton variant="ghost" @click="action.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="action.submitting" @click="submitTransition">确认</AppButton>
      </template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
/**
 * 安全变更（/admin/system/security-changes）。
 * 后端保证：草稿/审核/排期期间不写任何权限表，激活是单事务，
 * 并发激活由数据库唯一约束兜底，回滚用 before 快照还原并产生新版本号。
 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState, StatusTag } from '@/components/business'
import { AppButton } from '@/components/ui'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

const SELF_REVIEW_TEXT = '我已确认本次安全变更的影响并愿意承担责任'

const STATUS_LABEL = {
  DRAFT: '草稿',
  PENDING_REVIEW: '待复核',
  APPROVED: '已批准',
  SCHEDULED: '已排期',
  ACTIVATED: '已生效',
  REJECTED: '已驳回',
  ROLLED_BACK: '已回滚'
}

const ACTION_LABEL = {
  PENDING_REVIEW: '提交复核',
  APPROVED: '复核通过',
  REJECTED: '驳回',
  SCHEDULED: '排期',
  ACTIVATED: '立即激活',
  ROLLED_BACK: '回滚',
  DRAFT: '退回草稿'
}

const ACTION_TIP = {
  PENDING_REVIEW: '提交只是进入待复核，权限不会有任何变化。',
  APPROVED: '批准同样不改变权限——只有激活才生效。',
  REJECTED: '驳回后可退回草稿继续修改。',
  SCHEDULED: '排期后到点自动激活；生效前权限保持原样。',
  ACTIVATED: '激活会在同一个事务里应用全部改动并产生新的安全版本号；失败则整体回滚，不会改一半。',
  ROLLED_BACK: '回滚按激活时保存的快照还原，并产生一个新的版本号（而不是把版本号退回去）。',
  DRAFT: '退回草稿以便继续调整改动内容。'
}

export default {
  name: 'SystemSecurityChangeView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, StatusTag, AppButton, AppDrawer },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      changes: [],
      activations: [],
      currentRevision: 0,
      selfReviewText: SELF_REVIEW_TEXT,
      form: { open: false, title: '', reason: '', riskLevel: 'NORMAL', error: '', submitting: false },
      detail: { open: false, loading: false, title: '', data: null },
      action: {
        open: false, changeSetId: '', target: '', title: '', tip: '',
        reason: '', scheduledAt: '', selfReviewAck: '', expectedVersion: 0,
        error: '', submitting: false
      }
    }
  },
  created() { this.load() },
  methods: {
    fmt(v) { return v ? String(v).replace('T', ' ').slice(0, 16) : '—' },
    statusLabel(s) { return STATUS_LABEL[s] || s },
    actionLabel(s) { return ACTION_LABEL[s] || s },
    riskLabel(r) { return ({ NORMAL: '一般', HIGH: '高', CRITICAL: '极高' })[r] || r },
    targetLabel(t) { return ({ CUSTOM_ROLE: '自定义角色', SCOPE_POLICY: '范围策略' })[t] || t },
    statusType(s) {
      if (s === 'ACTIVATED') return 'success'
      if (s === 'ROLLED_BACK' || s === 'REJECTED') return 'danger'
      if (s === 'SCHEDULED' || s === 'PENDING_REVIEW') return 'processing'
      return 'default'
    },
    describeAfter(item) {
      const after = item.after || {}
      if (Array.isArray(after.permissionCodes)) return `权限调整为 ${after.permissionCodes.length} 项`
      return JSON.stringify(after)
    },

    async load() {
      this.loading = true
      this.error = ''
      const [list, history] = await Promise.all([
        systemApi.getSecurityChanges(),
        systemApi.getSecurityActivations()
      ])
      if (list.code === 0) {
        const data = list.data || {}
        this.changes = data.items || []
        this.currentRevision = data.currentRevision ?? 0
      } else {
        this.error = list.message
      }
      if (history.code === 0) this.activations = (history.data || {}).items || []
      this.loading = false
    },

    openCreate() {
      this.form = { open: true, title: '', reason: '', riskLevel: 'NORMAL', error: '', submitting: false }
    },

    async submitCreate() {
      if (!this.form.title.trim()) { this.form.error = '请填写标题'; return }
      if (this.form.reason.trim().length < 5) { this.form.error = '变更原因不少于 5 个字'; return }
      this.form.submitting = true
      const res = await systemApi.createSecurityChange({
        title: this.form.title.trim(),
        reason: this.form.reason.trim(),
        riskLevel: this.form.riskLevel
      })
      this.form.submitting = false
      if (res.code === 0) {
        toast.success('草稿已创建（尚未影响任何权限）')
        this.form.open = false
        this.load()
      } else {
        this.form.error = res.message
      }
    },

    async openDetail(c) {
      this.detail = { open: true, loading: true, title: `${c.title} · 详情`, data: null }
      const res = await systemApi.getSecurityChangeDetail(c.changeSetId)
      this.detail.loading = false
      if (res.code === 0) this.detail.data = res.data
      else toast.error(res.message)
    },

    openTransition(c, target) {
      this.action = {
        open: true,
        changeSetId: c.changeSetId,
        target,
        title: `${ACTION_LABEL[target] || target} · ${c.title}`,
        tip: ACTION_TIP[target] || '',
        reason: '',
        scheduledAt: '',
        selfReviewAck: '',
        expectedVersion: c.version,
        error: '',
        submitting: false
      }
    },

    async submitTransition() {
      if (this.action.reason.trim().length < 5) { this.action.error = '请填写不少于 5 个字'; return }
      if (this.action.target === 'SCHEDULED' && !this.action.scheduledAt) {
        this.action.error = '请填写计划生效时间'
        return
      }
      this.action.submitting = true
      this.action.error = ''
      const res = await systemApi.transitionSecurityChange(this.action.changeSetId, {
        targetStatus: this.action.target,
        reason: this.action.reason.trim(),
        expectedVersion: this.action.expectedVersion,
        scheduledAt: this.action.scheduledAt ? new Date(this.action.scheduledAt).toISOString() : null,
        selfReviewAck: this.action.selfReviewAck || null
      })
      this.action.submitting = false
      if (res.code === 0) {
        toast.success('安全变更已更新')
        this.action.open = false
        this.load()
      } else {
        // 自复核确认文本不符、版本冲突等，后端会给明确原因，直接展示
        this.action.error = res.message
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.sc-hero { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); padding: var(--space-4); }
.sc-hero__label { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.sc-hero__value { display: block; font-size: var(--font-size-xl); margin-top: var(--space-1); }
.sc-hero__hint { margin: var(--space-2) 0 0; font-size: var(--font-size-sm); color: var(--text-secondary); max-width: 640px; }
.sc-label { display: block; margin-top: var(--space-3); margin-bottom: var(--space-1); font-size: var(--font-size-sm); }
.sc-required { color: var(--danger-600); }
.sc-tip { margin: 0 0 var(--space-2); font-size: var(--font-size-sm); color: var(--text-secondary); }
.sc-section { margin: var(--space-4) 0 var(--space-2); font-size: var(--font-size-sm); }
.sc-danger { color: var(--danger-600); }
.sc-flag {
  margin-left: var(--space-2); padding: 0 var(--space-1); border-radius: var(--radius-sm);
  background: var(--fill-secondary); font-size: var(--font-size-xs); color: var(--text-secondary);
}
.sc-selfreview {
  margin-top: var(--space-3); padding: var(--space-3);
  border-radius: var(--radius-md); background: var(--fill-secondary);
}
.sc-selfreview__title { margin: 0 0 var(--space-1); font-size: var(--font-size-sm); font-weight: 600; }
.sc-selfreview__text {
  margin: 0 0 var(--space-2); font-size: var(--font-size-sm);
  color: var(--danger-600); user-select: all;
}
</style>
