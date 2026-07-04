<template>
  <ModulePageShell
    :title="detail ? detail.warning.code + ' · 预警跟进' : '预警跟进'"
    :subtitle="detail ? detail.warning.name + '（' + detail.warning.className + '）· ' + detail.warning.sourceRule : ''"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.name"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" @back="$router.back()" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-grid-2">
      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">预警信息</span>
            <span>
              <RiskTag :level="detail.warning.level" />
              <StatusTag :status="detail.warning.status" :label="statusLabel(detail.warning.status)" dot style="margin-left: var(--space-2)" />
            </span>
          </div>
          <div class="mp-card__body">
            <div class="mp-kv"><span class="mp-kv__k">预警类型</span><span class="mp-kv__v">{{ typeLabel(detail.warning.type) }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">触发原因</span><span class="mp-kv__v">{{ detail.warning.reason }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">触发时间</span><span class="mp-kv__v">{{ detail.warning.triggerTime }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">处理期限</span><span class="mp-kv__v">{{ detail.warning.deadline || '未设置' }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">跟进人</span><span class="mp-kv__v">{{ detail.warning.owner || '未分配' }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">已提醒</span><span class="mp-kv__v">{{ detail.warning.remindCount }} 次</span></div>
            <div v-if="detail.warning.closeResult" class="mp-kv"><span class="mp-kv__k">关闭说明</span><span class="mp-kv__v">{{ detail.warning.closeResult }}</span></div>
            <div v-if="detail.warning.recordStatus === 'VOIDED'" class="mp-kv"><span class="mp-kv__k">误报说明</span><span class="mp-kv__v">{{ detail.warning.voidReason }}</span></div>
          </div>
        </section>

        <section v-if="detail.student" class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">学生信息</span>
            <button class="mp-link" @click="$router.push('/admin/academic/students/' + detail.student.id)">学业详情 →</button>
          </div>
          <div class="mp-card__body">
            <div class="mp-kv"><span class="mp-kv__k">学生</span><span class="mp-kv__v">{{ detail.student.name }} · {{ maskNo(detail.student.studentNo) }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">班级</span><span class="mp-kv__v">{{ detail.student.className }}（{{ detail.student.collegeName }}）</span></div>
            <div class="mp-kv"><span class="mp-kv__k">GPA / 挂科</span><span class="mp-kv__v">{{ detail.student.gpa.toFixed(1) }} / {{ detail.student.failedCount }} 门</span></div>
            <div class="mp-kv"><span class="mp-kv__k">学分进度</span><span class="mp-kv__v">{{ detail.student.obtainedCredits }} / {{ detail.student.requiredCredits }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">辅导员</span><span class="mp-kv__v">{{ detail.student.counselor }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">联系电话</span><span class="mp-kv__v">{{ detail.student.phone || '未登记' }}</span></div>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">关联学业数据</span></div>
          <div class="mp-card__body">
            <div class="awd-block">
              <div class="awd-block__title">关联成绩</div>
              <ul class="awd-list">
                <li v-for="g in detail.extras.relatedGrades" :key="g">{{ g }}</li>
                <li v-if="!detail.extras.relatedGrades.length" class="mp-note">无关联成绩数据</li>
              </ul>
            </div>
            <div class="awd-block">
              <div class="awd-block__title">学分情况</div>
              <p class="awd-text">{{ detail.extras.relatedCredits || '—' }}</p>
            </div>
            <div class="awd-block">
              <div class="awd-block__title">历史预警</div>
              <ul class="awd-list">
                <li v-for="h in detail.extras.historyWarnings" :key="h">{{ h }}</li>
                <li v-if="!detail.extras.historyWarnings.length" class="mp-note">无历史预警</li>
              </ul>
            </div>
            <div v-if="detail.extras.suggestion" class="awd-suggestion">处理建议：{{ detail.extras.suggestion }}</div>
          </div>
        </section>
      </div>

      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">跟进记录（{{ detail.interventions.length }}）</span>
            <button
              v-if="visible('academic.warning.followup')"
              class="mp-link"
              :class="{ 'is-disabled': !can('academic.warning.followup') || closedOrVoided }"
              :title="reason('academic.warning.followup')"
              @click="openFollowup"
            >
              ＋ 新增跟进
            </button>
          </div>
          <div class="mp-card__body">
            <ul v-if="detail.interventions.length" class="mp-timeline">
              <li v-for="i in detail.interventions" :key="i.id" class="mp-timeline__item is-warning">
                <div class="mp-timeline__title">{{ i.wayLabel }} · {{ i.operator }}</div>
                <div class="mp-timeline__desc">
                  {{ i.content }}
                  <div v-if="i.result" class="mp-cell-sub">结果：{{ i.result }}</div>
                  <div v-if="i.nextPlan" class="mp-cell-sub">下一步：{{ i.nextPlan }}</div>
                </div>
                <div class="mp-timeline__time">{{ i.time }}</div>
              </li>
            </ul>
            <EmptyState v-else title="暂无跟进记录" description="领取预警后请及时记录谈话、家校联系或帮扶计划" />
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">操作审计</span></div>
          <div class="mp-card__body">
            <table class="mp-audit">
              <thead><tr><th>操作人</th><th>时间</th><th>动作</th><th>明细</th></tr></thead>
              <tbody>
                <tr v-for="a in detail.auditLogs" :key="a.id">
                  <td class="is-who">{{ a.operator }}<div class="mp-cell-sub">{{ a.roleName }}</div></td>
                  <td>{{ a.time }}</td>
                  <td>{{ a.action }}</td>
                  <td>{{ a.detail }}</td>
                </tr>
                <tr v-if="!detail.auditLogs.length"><td colspan="4" class="mp-note">暂无审计记录</td></tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>

    <FormDrawer
      v-model:visible="followForm.visible"
      v-model="followForm.model"
      title="新增跟进记录"
      :fields="followFields"
      :submitting="followForm.submitting"
      note="跟进记录将同步进入学生360的学业过程页签，并写入审计日志。"
      submit-text="提交跟进"
      @submit="submitFollowup"
    />

    <AppConfirmDialog
      v-model:visible="closeDialog.visible"
      type="primary"
      title="关闭预警"
      message="确认关闭该预警？关闭后学生学业状态将按剩余预警重新计算，关闭结果会同步学生端。"
      confirm-text="确认关闭"
      require-reason
      reason-label="关闭说明"
      reason-placeholder="请说明关闭依据（如成绩回升、学分补齐、补考通过），不少于 5 个字"
      :submitting="closeDialog.submitting"
      @confirm="submitClose"
    />

    <AppConfirmDialog
      v-model:visible="escalateDialog.visible"
      type="warning"
      title="升级预警"
      message="确认升级该预警？升级后等级将调整为高风险，并转交学院学业帮扶专班跟进。"
      confirm-text="确认升级"
      require-reason
      reason-label="升级说明"
      reason-placeholder="请说明升级依据（如跟进无效、风险加剧），不少于 5 个字"
      :submitting="escalateDialog.submitting"
      @confirm="submitEscalate"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 学业预警跟进详情（/admin/academic/warnings/:id）。
 * 闭环：预警信息 + 学生信息 + 关联学业数据 → 新增跟进 → 关闭（说明留痕）/ 升级（转专班留痕）→ 操作审计。
 */
import { ModulePageShell, ModuleToolbar, StatusTag, RiskTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { FormDrawer } from '@/modules/academic/components'
import { getWarningDetail, createIntervention, closeWarning, escalateWarning, remindWarnings } from '@/modules/academic/api/academic.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AcademicWarningDetailView',
  components: { ModulePageShell, ModuleToolbar, StatusTag, RiskTag, LoadingState, ErrorState, EmptyState, AppConfirmDialog, FormDrawer },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      detail: null,
      followForm: { visible: false, submitting: false, model: {} },
      closeDialog: { visible: false, submitting: false },
      escalateDialog: { visible: false, submitting: false }
    }
  },
  computed: {
    closedOrVoided() {
      return !this.detail || ['CLOSED'].includes(this.detail.warning.status) || this.detail.warning.recordStatus === 'VOIDED'
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'remind', permission: 'academic.warning.batchRemind', label: '发送提醒' },
        { key: 'escalate', permission: 'academic.warning.escalate', label: '升级预警', variant: 'warning' },
        { key: 'close', permission: 'academic.warning.close', label: '关闭预警', variant: 'primary' }
      ]
        .filter((a) => pa[a.permission] && pa[a.permission].visible)
        .map((a) => ({
          ...a,
          disabled: !pa[a.permission].allowed || this.closedOrVoided,
          disabledReason: !pa[a.permission].allowed ? pa[a.permission].reason : '预警已关闭或已作废'
        }))
    },
    followFields() {
      return [
        {
          key: 'way',
          label: '跟进方式',
          type: 'select',
          required: true,
          options: [
            { value: 'TALK', label: '当面谈话' },
            { value: 'PHONE', label: '电话联系' },
            { value: 'FAMILY', label: '家校联系' },
            { value: 'PLAN', label: '帮扶计划' }
          ]
        },
        { key: 'content', label: '跟进内容', type: 'textarea', required: true, placeholder: '记录本次跟进的过程与学生情况（不少于 5 个字）' },
        { key: 'result', label: '跟进结果', type: 'text' },
        { key: 'nextPlan', label: '下一步计划', type: 'text' }
      ]
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
    visible(key) {
      const pa = this.ctx.permissionActions[key]
      return !!(pa && pa.visible)
    },
    reason(key) {
      const pa = this.ctx.permissionActions[key]
      return pa && !pa.allowed ? pa.reason : ''
    },
    maskNo(v) {
      return v ? v.slice(0, -4) + '**' + v.slice(-2) : ''
    },
    typeLabel(v) {
      return (this.ctx.statusOptions.warningType.find((o) => o.value === v) || {}).label || v
    },
    statusLabel(v) {
      return (this.ctx.statusOptions.warningStatus.find((o) => o.value === v) || {}).label || v
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await getWarningDetail(this.$route.params.id)
      if (res.code === 0) this.detail = res.data
      else this.error = res.message
      this.loading = false
    },
    async onToolbar(key) {
      if (key === 'remind') {
        const res = await remindWarnings([this.detail.warning.id])
        if (res.code === 0) {
          toast.success('提醒已发送给学生与跟进人，已留痕')
          this.load()
        } else {
          toast.error(res.message)
        }
      } else if (key === 'close') {
        this.closeDialog = { visible: true, submitting: false }
      } else if (key === 'escalate') {
        this.escalateDialog = { visible: true, submitting: false }
      }
    },
    openFollowup() {
      if (!this.can('academic.warning.followup') || this.closedOrVoided) return
      this.followForm = { visible: true, submitting: false, model: { way: 'TALK' } }
    },
    async submitFollowup() {
      this.followForm.submitting = true
      const res = await createIntervention(this.detail.warning.id, this.followForm.model)
      this.followForm.submitting = false
      if (res.code === 0) {
        toast.success('跟进记录已提交，已同步学生360并留痕')
        this.followForm.visible = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async submitClose({ reason }) {
      this.closeDialog.submitting = true
      const res = await closeWarning(this.detail.warning.id, { result: reason })
      this.closeDialog.submitting = false
      if (res.code === 0) {
        toast.success('预警已关闭，结果已同步学生端并留痕')
        this.closeDialog.visible = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async submitEscalate({ reason }) {
      this.escalateDialog.submitting = true
      const res = await escalateWarning(this.detail.warning.id, { reason })
      this.escalateDialog.submitting = false
      if (res.code === 0) {
        toast.success('预警已升级为高风险，并转交学院学业帮扶专班（已留痕）')
        this.escalateDialog.visible = false
        this.load()
      } else {
        toast.error(res.message)
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.awd-block {
  margin-bottom: var(--space-3);
}
.awd-block__title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  margin-bottom: var(--space-1);
}
.awd-list {
  margin: 0;
  padding-left: var(--space-5);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.awd-list li {
  padding: 2px 0;
}
.awd-text {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.awd-suggestion {
  margin-top: var(--space-3);
  font-size: var(--font-size-sm);
  color: var(--primary-700);
  background: var(--primary-50);
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
  line-height: var(--line-height-base);
}
</style>
