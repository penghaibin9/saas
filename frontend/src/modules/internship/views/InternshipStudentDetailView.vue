<template>
  <ModulePageShell
    :title="detail ? detail.name + ' · 实习详情' : '实习详情'"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn" @click="goBack">← 返回实习学生</button>
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <template v-else-if="detail">
      <div class="sd-head">
        <AppStatusTag :type="detail.statusTone" dot>{{ detail.statusLabel }}</AppStatusTag>
        <AppStatusTag :type="eligTone(detail.eligibilityStatus)">{{ detail.eligibilityLabel }}</AppStatusTag>
        <span class="sd-dest">去向：{{ detail.destinationLabel }}</span>
        <div class="sd-head__spacer" />
        <button v-if="detail.eligibilityStatus !== 'QUALIFIED' && detail.status !== 'ARCHIVED'" class="mp-btn" @click="askEligibility">认定资格合格</button>
        <button v-if="detail.status !== 'ARCHIVED'" class="mp-btn mp-btn--primary" @click="openAssign">{{ detail.positionId ? '调岗' : '分配岗位' }}</button>
        <button v-if="detail.positionId && detail.status !== 'ARCHIVED'" class="mp-btn" @click="askUnassign">退岗</button>
        <button v-if="statusAction" class="mp-btn mp-btn--primary" @click="askStatus(statusAction.action)">{{ statusAction.label }}</button>
      </div>

      <div class="mp-grid-2">
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">实习信息</span></div>
          <div class="mp-card__body sd-grid">
            <div class="sd-kv"><span class="sd-k">姓名</span><span class="sd-v">{{ detail.name }}</span></div>
            <div class="sd-kv"><span class="sd-k">学号</span><span class="sd-v"><AppSensitiveText :value="detail.studentNo" type="generic" /></span></div>
            <div class="sd-kv"><span class="sd-k">班级</span><span class="sd-v">{{ detail.className }}</span></div>
            <div class="sd-kv"><span class="sd-k">联系电话</span><span class="sd-v">{{ detail.phone || '未登记' }}</span></div>
            <div class="sd-kv"><span class="sd-k">校内指导教师</span><span class="sd-v">{{ detail.advisorName || '未指定' }}</span></div>
            <div class="sd-kv"><span class="sd-k">实习起止</span><span class="sd-v">{{ detail.internRange || '—' }}</span></div>
            <div class="sd-kv"><span class="sd-k">实习保险</span><span class="sd-v">{{ detail.insurance || '—' }}</span></div>
            <div class="sd-kv"><span class="sd-k">三方协议</span><span class="sd-v">{{ detail.agreement || '—' }}</span></div>
            <div class="sd-kv sd-kv--full"><span class="sd-k">备注</span><span class="sd-v">{{ detail.remark || '—' }}</span></div>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">企业 / 岗位 / 导师（来自企业库·岗位库）</span></div>
          <div class="mp-card__body">
            <EmptyState v-if="!detail.positionId" title="未分配岗位" description="点右上「分配岗位」从岗位库选择已上架岗位" />
            <div v-else class="sd-grid">
              <div class="sd-kv"><span class="sd-k">实习企业</span>
                <span class="sd-v"><a class="mp-link" @click="detail.enterpriseId && $router.push('/admin/internship/enterprises/' + detail.enterpriseId)">{{ detail.enterpriseName }}</a>
                  <span v-if="detail.company && detail.company.blacklist" class="sd-warn"> · 黑名单</span></span>
              </div>
              <div class="sd-kv"><span class="sd-k">实习岗位</span>
                <span class="sd-v"><a class="mp-link" @click="$router.push('/admin/internship/positions/' + detail.positionId)">{{ detail.positionName }}</a></span>
              </div>
              <div class="sd-kv"><span class="sd-k">企业导师</span><span class="sd-v">{{ detail.mentorName || '未指定' }}</span></div>
              <div class="sd-kv"><span class="sd-k">岗位容量</span><span class="sd-v">{{ detail.position ? detail.position.capacity : '—' }}</span></div>
              <div class="sd-kv"><span class="sd-k">工作地点</span><span class="sd-v">{{ detail.position ? detail.position.workLocation : '—' }}</span></div>
            </div>
            <div v-if="!detail.positionId && detail.status !== 'ARCHIVED'" class="sd-dest-actions">
              <span class="sd-k">未分配可标记去向：</span>
              <button class="mp-link" @click="askDestination('SELF_ARRANGED')">自主实习</button>
              <button class="mp-link" @click="askDestination('EXEMPTED')">免实习</button>
            </div>
          </div>
        </section>
      </div>

      <section class="mp-card">
        <div class="mp-card__head"><span class="mp-card__title">操作留痕</span></div>
        <div class="mp-card__body">
          <AppAuditTrail :records="auditRecords" empty-text="暂无操作记录" />
        </div>
      </section>
    </template>

    <!-- 分配岗位 -->
    <AppDrawer v-model:visible="assignVisible" title="分配岗位">
      <div class="ie-form">
        <p class="ie-hint">仅「已上架」且企业非黑名单、未满员的岗位可选。</p>
        <!-- Picker 不能包在 <label> 里：label 激活会把点击转发给选择器内部按钮 -->
        <div class="ie-fld ie-fld--full"><span class="ie-lbl">岗位 <i>*</i></span>
          <AppInternshipPositionPicker
            v-model="assignPositionId"
            placeholder="输入岗位或企业名称搜索"
            search-placeholder="按岗位名称 / 企业搜索"
            data-scope-hint="仅已上架、未满员岗位可选"
          />
        </div>
        <p v-if="assignError" class="ie-err">{{ assignError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="assignVisible = false">取消</button>
          <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting || !assignPositionId" @click="submitAssign">确认分配</button>
        </div>
      </div>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message"
      :type="confirm.type" :confirm-text="confirm.confirmText" :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel" :submitting="submitting" @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 实习学生详情（/admin/internship/students/:id）：生产级；企业/岗位/导师真实关联 + 分配/退岗/状态机/资格/去向 + 审计。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSensitiveText, AppStatusTag, AppAuditTrail, AppInternshipPositionPicker } from '@/components/common'
import { AppDrawer } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { internStudentApi } from '@/modules/internship/api/internship-student.api'
import { toast } from '@/utils/toast'

const STATUS_NEXT = {
  PREPARING: { action: 'READY', label: '置为待上岗' },
  READY: { action: 'ONBOARD', label: '上岗' },
  ONBOARD: { action: 'ASSESS', label: '进入考核' },
  ASSESSING: { action: 'ARCHIVE', label: '归档' }
}

export default {
  name: 'InternshipStudentDetailView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppSensitiveText, AppStatusTag, AppAuditTrail, AppDrawer, AppConfirmDialog, AppInternshipPositionPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', submitting: false, detail: null,
      assignVisible: false, assignPositionId: '', assignError: '',
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, extra: null }
    }
  },
  computed: {
    statusAction() { return this.detail && this.detail.status !== 'ARCHIVED' ? STATUS_NEXT[this.detail.status] : null },
    pageSubtitle() {
      if (!this.detail) return '加载中'
      const no = this.detail.studentNo
      const masked = no ? `${String(no).slice(0, -4)}**${String(no).slice(-2)}` : '—'
      return `${this.detail.className} · ${masked}`
    },
    auditRecords() {
      return (this.detail?.auditTrail || []).map((a, i) => ({
        id: i,
        action: a.action,
        actor: a.operator,
        at: a.occurredAt
      }))
    }
  },
  created() { this.load() },
  methods: {
    goBack() {
      const q = {}
      if (this.$route.query.batchId) q.batchId = this.$route.query.batchId
      else if (this.detail?.batchId) q.batchId = this.detail.batchId
      this.$router.push({ path: '/admin/internship/students', query: q })
    },
    eligTone(s) { return s === 'QUALIFIED' ? 'success' : (s === 'UNQUALIFIED' ? 'danger' : 'warning') },
    async load() {
      this.loading = true; this.error = ''
      const res = await internStudentApi.getStudentDetail(this.$route.params.id)
      if (res.code === 0) this.detail = res.data; else this.error = res.message
      this.loading = false
    },
    // 选择器远程搜索（岗位实习模块适配层，后端裁定关键字与数据范围）
    openAssign() {
      // 岗位候选改为选择器内按关键字远程搜索，不再一次性预载
      this.assignPositionId = ''; this.assignError = ''
      this.assignVisible = true
    },
    async submitAssign() {
      this.assignError = ''; this.submitting = true
      try {
        const res = await internStudentApi.assignPosition(this.detail.id, {
          positionId: this.assignPositionId,
          expectedVersion: this.detail.version
        })
        if (res.code === 0) { toast.success('已分配岗位'); this.assignVisible = false; this.load() } else this.assignError = res.message
      } finally { this.submitting = false }
    },
    askEligibility() {
      this.confirm = { visible: true, title: '实习资格认定', message: '确认该生实习资格合格？', type: 'primary', confirmText: '认定合格', requireReason: false, action: 'ELIG', extra: null }
    },
    askUnassign() {
      this.confirm = { visible: true, title: '退岗', message: '确认退岗？将释放该岗位名额。', type: 'warning', confirmText: '确认退岗', requireReason: true, reasonLabel: '退岗原因', action: 'UNASSIGN', extra: null }
    },
    async askStatus(action) {
      const m = STATUS_NEXT[this.detail.status]
      // BUG-010：上岗前先取前置清单，缺项直接列出来，别让教师点完才吃 409
      if (action === 'ONBOARD') {
        const res = await internStudentApi.getOnboardChecklist(this.detail.id)
        if (res.code === 0 && res.data && !res.data.canOnboard) {
          const miss = (res.data.blockers || []).join('；')
          return toast.error(miss ? `不能上岗，前置未完成：${miss}` : '不能上岗，前置条件未满足')
        }
      }
      this.confirm = { visible: true, title: m.label, message: `确认执行「${m.label}」？`, type: 'primary', confirmText: '确认', requireReason: false, action: 'STATUS', extra: action }
    },
    askDestination(dest) {
      const label = dest === 'SELF_ARRANGED' ? '自主实习' : '免实习'
      this.confirm = { visible: true, title: '标记去向 · ' + label, message: `确认将去向标记为「${label}」？`, type: 'primary', confirmText: '确认', requireReason: false, action: 'DEST', extra: dest }
    },
    async onConfirm({ reason } = {}) {
      const { action, extra } = this.confirm
      this.submitting = true
      try {
        let res
        if (action === 'ELIG') res = await internStudentApi.setEligibility(this.detail.id, { status: 'QUALIFIED', reason: reason || '' })
        else if (action === 'UNASSIGN') res = await internStudentApi.unassignPosition(this.detail.id, {
          reason: reason || '', expectedVersion: this.detail.version
        })
        else if (action === 'STATUS') res = await internStudentApi.setStatus(this.detail.id, { action: extra, reason: reason || '' })
        else if (action === 'DEST') res = await internStudentApi.setDestination(this.detail.id, { destination: extra, reason: reason || '' })
        if (res && res.code === 0) { toast.success('已更新并写入留痕'); this.confirm.visible = false; this.load() } else if (res) toast.error(res.message)
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.sd-head { display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.sd-head__spacer { flex: 1; }
.sd-dest { font-size: 12px; color: var(--t2, #475569); }
.sd-warn { color: var(--danger, #dc2626); }
.sd-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-3); }
.sd-kv { display: flex; flex-direction: column; gap: 2px; }
.sd-kv--full { grid-column: 1 / -1; }
.sd-k { font-size: 12px; color: var(--t3, #64748b); }
.sd-v { font-size: 13px; color: var(--t1, #0f1e3d); }
.sd-dest-actions { margin-top: var(--space-3); display: flex; align-items: center; gap: var(--space-2); font-size: 12px; }
.sd-trail__item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px dashed var(--line, #eef1f6); font-size: 13px; }
.sd-trail__meta { color: var(--t3, #64748b); font-size: 12px; }
.mp-btn { padding: 7px 14px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.ie-form { display: grid; grid-template-columns: 1fr; gap: var(--space-3); }
.ie-fld { display: flex; flex-direction: column; gap: 4px; }
.ie-fld--full { grid-column: 1 / -1; }
.ie-lbl { font-size: 12px; color: var(--t2, #475569); }
.ie-lbl i { color: var(--danger, #dc2626); font-style: normal; }
.ie-in { width: 100%; padding: 7px 10px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; font-size: 13px; box-sizing: border-box; }
.ie-err { color: var(--danger, #dc2626); font-size: 12px; margin: 0; }
.ie-hint { font-size: 12px; color: var(--t3, #64748b); margin: 0; }
.ie-actions { display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-2); }
</style>
