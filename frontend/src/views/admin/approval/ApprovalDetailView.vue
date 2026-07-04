<template>
  <ModulePageShell
    :title="task ? task.title : '审批详情'"
    :subtitle="task ? task.taskId + ' · ' + task.bizTypeLabel + ' · 当前节点：' + task.currentNode : ''"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <ErrorState v-if="error" :description="error" @retry="load" @back="$router.back()" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-grid-2">
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
                {{ task.applicant.name }} · {{ maskNo(task.applicant.studentNo) }} · {{ task.applicant.className }}
              </span>
            </div>
            <div class="mp-kv">
              <span class="mp-kv__k">提交时间</span>
              <span class="mp-kv__v">{{ task.submitTime }}（截止 {{ task.deadline }}）</span>
            </div>
            <div v-for="(f, i) in detail.fields" :key="i" class="mp-kv">
              <span class="mp-kv__k">{{ f.label }}</span>
              <span class="mp-kv__v">
                {{ f.value }}
                <span v-if="f.masked" class="dv-masked">已脱敏</span>
              </span>
            </div>
          </div>
        </section>

        <section v-if="detail.applyNote" class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">申请说明</span></div>
          <div class="mp-card__body">
            <p class="dv-note-text">{{ detail.applyNote }}</p>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">附件材料</span>
            <span class="mp-note">共 {{ detail.attachments.length }} 份</span>
          </div>
          <div class="mp-card__body">
            <p v-if="!detail.attachments.length" class="mp-note">申请人未上传附件</p>
            <div v-else style="display: flex; gap: var(--space-2); flex-wrap: wrap">
              <StatusTag v-for="a in detail.attachments" :key="a" type="info" :label="'📎 ' + a" />
            </div>
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

        <section v-if="suggestions.length" class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">加签建议</span>
            <span class="mp-note">仅供决策参考，不改变流转节点</span>
          </div>
          <div class="mp-card__body">
            <div v-for="(s, i) in suggestions" :key="i" class="dv-suggestion">
              <div class="mp-cell-main">{{ s.who }}</div>
              <div class="dv-suggestion__content">{{ s.content }}</div>
              <div class="mp-cell-sub">{{ s.time }}</div>
            </div>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">办理操作</span></div>
          <div class="mp-card__body">
            <template v-if="canHandle">
              <label class="mp-note" style="display: block; margin-bottom: var(--space-1)">审批意见（选填）</label>
              <textarea
                v-model="comment"
                class="mp-textarea"
                placeholder="例如：材料齐全，同意办理；意见将写入时间线并同步申请人…"
              ></textarea>
              <p v-if="formError" class="mp-form-err">{{ formError }}</p>
              <div style="display: flex; gap: var(--space-2); margin-top: var(--space-3)">
                <AppButton
                  variant="primary"
                  style="flex: 1"
                  :loading="submitting"
                  :disabled="!can('approveTask')"
                  :title="reason('approveTask')"
                  @click="submitApprove"
                >
                  ✓ 审批通过
                </AppButton>
                <AppButton
                  variant="danger"
                  style="flex: 1"
                  :disabled="!can('returnTask') || submitting"
                  :title="reason('returnTask')"
                  @click="returnDialog = true"
                >
                  ↩ 退回申请
                </AppButton>
                <AppButton
                  variant="secondary"
                  style="flex: 1"
                  :disabled="!can('transferTask') || submitting"
                  :title="reason('transferTask')"
                  @click="openTransfer"
                >
                  ⇄ 转交
                </AppButton>
              </div>
              <p class="mp-note" style="text-align: center; margin-top: var(--space-2)">
                办理动作实时写入审批时间线与审计留痕，结果同步申请人
              </p>
            </template>
            <EmptyState
              v-else
              :title="readonlyTitle"
              :description="readonlyDesc"
            />
          </div>
        </section>
      </div>
    </div>

    <AppConfirmDialog
      v-model:visible="returnDialog"
      title="退回申请确认"
      :message="task ? '退回后「' + task.title + '」将返回申请人整改，退回原因原样同步对方。' : ''"
      type="danger"
      confirm-text="确认退回"
      require-reason
      reason-label="退回原因"
      reason-placeholder="请写明退回原因与整改要求（不少于 5 个字）"
      :submitting="submitting"
      @confirm="submitReturn"
    />

    <AppDrawer v-model:visible="transferDrawer" title="转交任务">
      <p class="mp-note" style="margin: 0 0 var(--space-3)">
        任务状态保持待审批，办理人转移给所选对象并全程留痕。
      </p>
      <div
        v-for="t in ctx.transferTargets"
        :key="t.userId"
        class="mp-radio"
        :class="{ 'is-active': transferForm.targetUserId === t.userId }"
        @click="transferForm.targetUserId = t.userId"
      >
        <input type="radio" :checked="transferForm.targetUserId === t.userId" style="margin-top: 3px" />
        <div>
          <div class="mp-radio__title">{{ t.userName }} · {{ t.roleName }}</div>
          <div class="mp-radio__desc">{{ t.orgName }} · 当前在办 {{ t.pendingCount }} 条</div>
        </div>
      </div>
      <label class="mp-note" style="display: block; margin: var(--space-3) 0 var(--space-1)">转交说明（选填）</label>
      <textarea
        v-model="transferForm.note"
        class="mp-textarea"
        placeholder="例如：该件涉及学籍口径，请协助复核后办理…"
      ></textarea>
      <p v-if="transferError" class="mp-form-err">{{ transferError }}</p>
      <template #footer>
        <AppButton variant="ghost" @click="transferDrawer = false">取消</AppButton>
        <AppButton variant="primary" :loading="submitting" @click="submitTransfer">确认转交</AppButton>
      </template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
/**
 * 审批详情（/admin/approval/todos/:taskId）。
 * 闭环：业务信息（脱敏）/附件/申请说明 → 通过（意见选填）/ 退回（原因必填）/ 转交（选人）
 * → 时间线与审计留痕即时刷新；已办结或已转交任务操作区只读；taskId 不存在展示 ErrorState。
 */
import {
  ModulePageShell,
  StatusTag,
  LoadingState,
  ErrorState,
  EmptyState
} from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { approvalApi } from '@/modules/approval/api/approval.api'
import { toast } from '@/utils/toast'

export default {
  name: 'ApprovalDetailView',
  components: {
    ModulePageShell,
    StatusTag,
    LoadingState,
    ErrorState,
    EmptyState,
    AppConfirmDialog,
    AppButton,
    AppDrawer
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      task: null,
      detail: null,
      timeline: [],
      suggestions: [],
      comment: '',
      formError: '',
      submitting: false,
      returnDialog: false,
      transferDrawer: false,
      transferForm: { targetUserId: '', note: '' },
      transferError: ''
    }
  },
  computed: {
    canHandle() {
      return !!(this.task && this.task.status === 'PENDING_REVIEW' && !this.task.transferred)
    },
    readonlyTitle() {
      if (!this.task) return '任务不可操作'
      if (this.task.transferred) return '该任务已转交'
      return this.task.status === 'APPROVED' ? '该任务已办结（通过）' : '该任务已办结（退回）'
    },
    readonlyDesc() {
      if (!this.task) return ''
      if (this.task.transferred) return (this.task.transferHint || '已转交他人办理') + '，本页仅可查看流转记录'
      return '办理结果已同步申请人，操作区仅可查看，完整留痕见审批时间线'
    }
  },
  created() {
    this.load()
  },
  methods: {
    can(key) {
      const pa = this.ctx.permissionActions[key]
      return !!(pa && pa.visible && pa.allowed)
    },
    reason(key) {
      const pa = this.ctx.permissionActions[key]
      return pa && !pa.allowed ? pa.reason : ''
    },
    urgencyTone(urgency) {
      if (urgency === 'OVERDUE') return 'danger'
      if (urgency === 'URGENT') return 'warning'
      return 'default'
    },
    toneClass(tone) {
      const t = tone === 'processing' ? 'warning' : tone
      return 'is-' + (['success', 'warning', 'danger', 'default'].includes(t) ? t : 'default')
    },
    maskNo(v) {
      return v ? v.slice(0, -4) + '**' + v.slice(-2) : ''
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await approvalApi.getApprovalDetail(this.$route.params.taskId)
      if (res.code === 0) {
        this.task = res.data.task
        this.detail = res.data.detail
        this.timeline = res.data.timeline
        this.suggestions = res.data.suggestions
      } else {
        this.error = res.message
      }
      this.loading = false
    },
    async submitApprove() {
      if (!this.can('approveTask')) return
      this.formError = ''
      this.submitting = true
      const res = await approvalApi.approveTask(this.task.taskId, { comment: this.comment })
      this.submitting = false
      if (res.code === 0) {
        toast.success('审批通过：已留痕并同步申请人，待办统计已联动更新')
        this.comment = ''
        this.load()
      } else {
        this.formError = res.message
      }
    },
    async submitReturn({ reason }) {
      this.submitting = true
      const res = await approvalApi.returnTask(this.task.taskId, { reason })
      this.submitting = false
      this.returnDialog = false
      if (res.code === 0) {
        toast.success('已退回：原因已同步申请人，并写入退回记录与审计留痕')
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    openTransfer() {
      if (!this.can('transferTask')) return
      this.transferForm = { targetUserId: '', note: '' }
      this.transferError = ''
      this.transferDrawer = true
    },
    async submitTransfer() {
      this.transferError = ''
      if (!this.transferForm.targetUserId) {
        this.transferError = '请选择转交对象'
        return
      }
      this.submitting = true
      const res = await approvalApi.transferTask(this.task.taskId, {
        targetUserId: this.transferForm.targetUserId,
        note: this.transferForm.note
      })
      this.submitting = false
      if (res.code === 0) {
        this.transferDrawer = false
        toast.success('已转交给 ' + res.data.transferredTo + '：任务状态不变，流转留痕已更新')
        this.load()
      } else {
        this.transferError = res.message
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.dv-masked {
  margin-left: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--info-600);
  background: var(--info-50);
  border: 1px solid var(--info-100);
  border-radius: var(--radius-full);
  padding: 0 var(--space-1);
  white-space: nowrap;
}
.dv-note-text {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: 1.8;
}
.dv-suggestion {
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-left: 3px solid var(--warning-500);
  border-radius: var(--radius-base);
  background: var(--bg-section-warm);
  margin-bottom: var(--space-2);
}
.dv-suggestion:last-child {
  margin-bottom: 0;
}
.dv-suggestion__content {
  margin: var(--space-1) 0;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: 1.7;
}
</style>
