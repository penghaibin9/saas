<template>
  <ModulePageShell
    :title="task ? task.title : '审批详情'"
    :subtitle="task ? task.taskId + ' · ' + task.bizTypeLabel + ' · 当前节点：' + task.currentNode : ''"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-link" @click="goBackToList">← 返回列表</button>
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" @back="goBackToList" />
    <LoadingState v-else-if="loading" />
    <div v-else-if="task" class="mp-grid-2">
      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">业务信息</span>
            <span>
              <StatusTag :status="task.status" :label="task.statusLabel" dot />
              <StatusTag
                v-if="task.status === 'PENDING_REVIEW'"
                :type="urgencyTone(task.urgency)"
                :label="task.urgencyLabel"
                style="margin-left: var(--space-2)"
              />
            </span>
          </div>
          <div class="mp-card__body">
            <div class="mp-kv">
              <span class="mp-kv__k">申请人</span>
              <span class="mp-kv__v">
                {{ task.applicant.name }}
                <template v-if="task.applicant.studentNo"> · {{ maskNo(task.applicant.studentNo) }}</template>
                <template v-if="task.applicant.className"> · {{ task.applicant.className }}</template>
              </span>
            </div>
            <div class="mp-kv"><span class="mp-kv__k">提交时间</span><span class="mp-kv__v">{{ task.submitTime || '—' }}</span></div>
            <div v-if="task.deadline" class="mp-kv"><span class="mp-kv__k">办理期限</span><span class="mp-kv__v">{{ task.deadline }}</span></div>
            <div v-for="(f, i) in detail.fields" :key="i" class="mp-kv"><span class="mp-kv__k">{{ f.label }}</span><span class="mp-kv__v">{{ f.value }}</span></div>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">附件材料</span><span class="mp-note">共 {{ detail.attachments.length }} 份</span></div>
          <div class="mp-card__body">
            <p v-if="!detail.attachments.length" class="mp-note">申请人未上传附件</p>
            <div v-else class="dv-attachments"><StatusTag v-for="a in detail.attachments" :key="a" type="info" :label="'📎 ' + a" /></div>
          </div>
        </section>
      </div>

      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">审批时间线</span></div>
          <div class="mp-card__body">
            <p v-if="!timeline.length" class="mp-note">暂无流转记录</p>
            <ul v-else class="mp-timeline">
              <li v-for="(t, i) in timeline" :key="i" class="mp-timeline__item" :class="toneClass(t.tone)">
                <div class="mp-timeline__title">{{ t.who }} · {{ t.action }}</div>
                <div v-if="t.comment" class="mp-timeline__desc">{{ t.comment }}</div>
                <div class="mp-timeline__time">{{ t.time }}</div>
              </li>
            </ul>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">办理操作</span></div>
          <div class="mp-card__body">
            <template v-if="canHandle">
              <label class="mp-note dv-label">审批意见（选填）</label>
              <textarea v-model="comment" class="mp-textarea" placeholder="审批意见会写入真实流转记录"></textarea>
              <p v-if="formError" class="mp-form-err">{{ formError }}</p>
              <div class="dv-actions">
                <AppButton variant="primary" :loading="submitting" :disabled="!canAction('approveTask', 'APPROVE')" @click="submitApprove">✓ 审批通过</AppButton>
                <AppButton variant="secondary" :disabled="!canAction('returnTask', 'RETURN') || submitting" @click="returnDialog = true">↩ 退回修改</AppButton>
                <AppButton variant="danger" :disabled="!canAction('rejectTask', 'REJECT') || submitting" @click="rejectDialog = true">✕ 驳回终止</AppButton>
                <AppButton variant="secondary" :disabled="!canAction('transferTask', 'TRANSFER') || submitting" @click="openTransfer">⇄ 转办</AppButton>
              </div>
              <p class="mp-note dv-hint">退回修改会生成申请人重提待办；驳回终止结束原流程，两者不会互换。</p>
            </template>
            <EmptyState v-else :title="readonlyTitle" :description="readonlyDesc" />
          </div>
        </section>
      </div>
    </div>

    <AppConfirmDialog
      v-model:visible="returnDialog"
      title="退回修改确认"
      :message="task ? '退回后「' + task.title + '」仍保持流程运行，并给申请人生成修改重提待办。' : ''"
      type="primary"
      confirm-text="确认退回修改"
      require-reason
      reason-label="退回原因 / 修改要求"
      reason-placeholder="请写明退回原因与需要修改的内容"
      :submitting="submitting"
      @confirm="submitReturn"
    />

    <AppConfirmDialog
      v-model:visible="rejectDialog"
      title="驳回终止确认"
      :message="task ? '驳回后「' + task.title + '」的原审批流程将终止，不生成原流程重提入口。' : ''"
      type="danger"
      confirm-text="确认驳回终止"
      require-reason
      reason-label="驳回原因"
      reason-placeholder="请写明终止原流程的原因"
      :submitting="submitting"
      @confirm="submitReject"
    />

    <AppDrawer v-model:visible="transferDrawer" title="转办任务">
      <p class="mp-note">原任务保留 TRANSFERRED 留痕；仅展示同时满足当前节点责任角色与数据范围的目标办理人。</p>
      <p v-if="transferTargetsLoading" class="mp-note">正在核验当前任务的可转办人员…</p>
      <template v-else>
        <div v-for="t in transferTargets" :key="t.userId" class="mp-radio" :class="{ 'is-active': transferForm.targetUserId === t.userId }" @click="transferForm.targetUserId = t.userId">
          <input type="radio" :checked="transferForm.targetUserId === t.userId" />
          <div><div class="mp-radio__title">{{ t.userName }} · {{ t.roleName }}</div><div class="mp-radio__desc">{{ t.orgName || '当前数据范围' }} · 当前在办 {{ t.pendingCount }} 条</div></div>
        </div>
        <p v-if="!transferTargets.length && !transferError" class="mp-note">当前任务没有满足节点角色与数据范围的可转办人员。</p>
      </template>
      <label class="mp-note dv-label">转办说明（选填）</label>
      <textarea v-model="transferForm.note" class="mp-textarea" placeholder="请说明转办原因或办理重点"></textarea>
      <p v-if="transferError" class="mp-form-err">{{ transferError }}</p>
      <template #footer><AppButton variant="ghost" @click="transferDrawer = false">取消</AppButton><AppButton variant="primary" :loading="submitting" :disabled="transferTargetsLoading" @click="submitTransfer">确认转办</AppButton></template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { approvalApi } from '@/modules/approval/api/approval.api'
import { buildReturnQuery, returnPath } from '@/modules/approval/utils/queueContext'
import { toast } from '@/utils/toast'

export default {
  name: 'ApprovalDetailView',
  components: { ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState, AppConfirmDialog, AppButton, AppDrawer },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', task: null,
      detail: { fields: [], attachments: [], applyNote: '' }, timeline: [], suggestions: [],
      comment: '', formError: '', submitting: false,
      returnDialog: false, rejectDialog: false, transferDrawer: false,
      transferTargets: [], transferTargetsLoading: false,
      transferForm: { targetUserId: '', note: '' }, transferError: ''
    }
  },
  computed: {
    canHandle() { return !!(this.task && this.task.status === 'PENDING_REVIEW' && this.task.allowedActions?.length) },
    readonlyTitle() {
      if (!this.task) return '任务不可操作'
      if (this.task.status === 'APPROVED') return '该任务已办结（通过）'
      if (this.task.status === 'RETURNED') return '该任务已退回修改'
      if (this.task.status === 'REJECTED') return '该任务已驳回终止'
      if (this.task.status === 'TRANSFERRED') return '该任务已转办'
      return '该任务当前不可办理'
    },
    readonlyDesc() {
      if (!this.task) return ''
      if (this.task.status === 'RETURNED') return '流程仍在运行，申请人可按退回要求修改并重新提交。'
      if (this.task.status === 'REJECTED') return '原流程已经终止；如需再次申请，应重新发起新流程。'
      return '本页仅展示服务端已持久化的处理结果与流转记录。'
    }
  },
  created() { this.load() },
  methods: {
    canAction(key, action) {
      const pa = this.ctx.permissionActions[key]
      return !!(pa && pa.visible && pa.allowed && this.task?.allowedActions?.includes(action))
    },
    urgencyTone(v) { return v === 'OVERDUE' ? 'danger' : (v === 'NEAR_DEADLINE' || v === 'URGENT') ? 'warning' : 'default' },
    toneClass(tone) { const t = tone === 'processing' ? 'warning' : tone; return 'is-' + (['success', 'warning', 'danger', 'default'].includes(t) ? t : 'default') },
    maskNo(v) { return v ? v.slice(0, -4) + '**' + v.slice(-2) : '' },
    async load() {
      this.loading = true; this.error = ''
      const res = await approvalApi.getApprovalDetail(this.$route.params.taskId)
      if (res.code === 0) {
        this.task = res.data.task; this.detail = res.data.detail; this.timeline = res.data.timeline; this.suggestions = res.data.suggestions
      } else this.error = res.message
      this.loading = false
    },
    async actionFailed(res, field = 'form') {
      const conflict = String(res.bizCode || '').includes('CONFLICT') || /已被处理|发生变化|刷新后重试|版本/.test(res.message || '')
      if (conflict) { toast.info('该审批事实已经变化，已为你刷新最新状态'); await this.load(); return }
      if (field === 'transfer') this.transferError = res.message; else this.formError = res.message
    },
    async goNext() {
      // TP-A03/A04：真实服务端 seek，按当前进入详情页时携带的完整筛选（业务类型/
      // 紧急度/关键词/提交日期）取队列里锚点任务之后的下一条，不再用 pageSize=1
      // 重新查第一页去猜"下一条=队首"，也不再只保留 bizType 一个筛选维度。
      const q = this.$route.query || {}
      const res = await approvalApi.getNextTodo(this.task?.taskId, {
        keyword: q.keyword || '',
        bizType: q.bizType || '',
        urgency: q.urgency || '',
        submitDate: q.submitDate || ''
      })
      if (res.code === 0 && res.data) {
        await this.$router.replace({ path: '/admin/approval/todos/' + res.data.taskId, query: { ...q } }); await this.load(); return
      }
      // 同队列已经处理完：回到来源列表，保留原筛选/分页（PcQueueContext v1），
      // 不再无条件推到无筛选的待办首页。
      this.goBackToList()
    },
    goBackToList() {
      const q = this.$route.query || {}
      this.$router.push({ path: returnPath(q), query: buildReturnQuery(q) })
    },
    async finishAction(res, message) {
      if (res.code !== 0) { await this.actionFailed(res); return false }
      toast.success(message); await this.load(); await this.goNext(); return true
    },
    async submitApprove() {
      if (!this.canAction('approveTask', 'APPROVE')) return
      this.formError = ''; this.submitting = true
      const res = await approvalApi.approveTask(this.task.taskId, { comment: this.comment, version: this.task.version })
      this.submitting = false
      if (await this.finishAction(res, '审批通过：服务端已持久化，正在进入下一条待办')) this.comment = ''
    },
    async submitReturn({ reason }) {
      this.submitting = true
      const res = await approvalApi.returnTask(this.task.taskId, { reason, version: this.task.version })
      this.submitting = false; this.returnDialog = false
      await this.finishAction(res, '已退回修改：申请人修改重提待办已生成，正在进入下一条待办')
    },
    async submitReject({ reason }) {
      this.submitting = true
      const res = await approvalApi.rejectTask(this.task.taskId, { reason, version: this.task.version })
      this.submitting = false; this.rejectDialog = false
      await this.finishAction(res, '已驳回终止：原流程已结束，正在进入下一条待办')
    },
    async openTransfer() {
      if (!this.canAction('transferTask', 'TRANSFER')) return
      this.transferForm = { targetUserId: '', note: '' }
      this.transferError = ''
      this.transferTargets = []
      this.transferDrawer = true
      this.transferTargetsLoading = true
      const res = await approvalApi.getTransferTargets([this.task.taskId])
      this.transferTargetsLoading = false
      if (res.code === 0) this.transferTargets = res.data
      else this.transferError = res.message
    },
    async submitTransfer() {
      this.transferError = ''
      if (!this.transferForm.targetUserId) { this.transferError = '请选择转办对象'; return }
      if (!this.transferTargets.some((x) => String(x.userId) === String(this.transferForm.targetUserId))) {
        this.transferError = '该人员已不在当前任务可转办范围，请重新打开转办列表'
        return
      }
      this.submitting = true
      const res = await approvalApi.transferTask(this.task.taskId, { targetUserId: this.transferForm.targetUserId, note: this.transferForm.note, version: this.task.version })
      this.submitting = false
      if (res.code === 0) { this.transferDrawer = false; toast.success('已转办：原任务已留痕，新办理人已获得真实待办'); await this.load(); await this.goNext() }
      else await this.actionFailed(res, 'transfer')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.dv-attachments { display: flex; gap: var(--space-2); flex-wrap: wrap; }
.dv-label { display: block; margin: var(--space-3) 0 var(--space-1); }
.dv-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-2); margin-top: var(--space-3); }
.dv-hint { margin: var(--space-2) 0 0; text-align: center; line-height: 1.6; }
@media (max-width: 900px) { .dv-actions { grid-template-columns: 1fr; } }
</style>
