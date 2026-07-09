<template>
  <ModulePageShell
    :title="detail ? detail.name + ' · 毕设详情' : '毕设详情'"
    :subtitle="detail ? (detail.className + (detail.batchName ? ' · ' + detail.batchName : '')) : ''"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" @back="$router.back()" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-grid-2">
      <div class="mp-stack">
        <AppSectionCard title="课题信息">
          <template #header-extra>
            <StatusTag :type="detail.stageTone || 'processing'" :label="detail.stageLabel" dot />
          </template>
          <AppDescriptionList :items="topicInfoItems" :columns="1">
            <template #studentNo>
              <AppSensitiveText :value="detail.studentNo" type="generic" />
            </template>
            <template #phone>
              <AppSensitiveText :value="detail.phone" type="phone" />
            </template>
          </AppDescriptionList>
        </AppSectionCard>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">主状态进度</span></div>
          <div class="mp-card__body">
            <ul class="mp-timeline">
              <li v-for="s in detail.stateFlow" :key="s.title" class="mp-timeline__item" :class="'is-' + (s.tone === 'processing' ? 'warning' : s.tone)">
                <div class="mp-timeline__title">{{ s.title }}</div>
                <div class="mp-timeline__time">{{ s.time }}</div>
              </li>
            </ul>
          </div>
        </section>
      </div>

      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-tabs" style="padding: 0 var(--space-4)">
            <button v-for="t in tabs" :key="t.key" class="mp-tab" :class="{ 'is-active': tab === t.key }" @click="tab = t.key">
              {{ t.label }}
            </button>
          </div>
          <div class="mp-card__body">
            <table v-if="tab === 'proposals'" class="mp-audit">
              <thead><tr><th>材料</th><th>版本</th><th>提交时间</th><th>状态</th><th>批阅人</th></tr></thead>
              <tbody>
                <tr v-if="!detail.proposals.length"><td colspan="5" class="mp-note">暂无开题记录</td></tr>
                <tr v-for="p in detail.proposals" :key="p.id">
                  <td class="is-who">{{ p.type }}</td>
                  <td>{{ p.version }}</td>
                  <td>{{ p.submitAt }}</td>
                  <td><StatusTag :status="p.status" dot /></td>
                  <td>{{ p.reviewer }}</td>
                </tr>
              </tbody>
            </table>
            <table v-else-if="tab === 'finals'" class="mp-audit">
              <thead><tr><th>成果</th><th>版本</th><th>提交时间</th><th>状态</th><th>查重</th></tr></thead>
              <tbody>
                <tr v-if="!detail.finals.length"><td colspan="5" class="mp-note">暂无成果提交</td></tr>
                <tr v-for="f in detail.finals" :key="f.id">
                  <td class="is-who">{{ f.type }}</td>
                  <td>{{ f.version }}</td>
                  <td>{{ f.submitAt }}</td>
                  <td><StatusTag :status="f.status" dot /></td>
                  <td>{{ f.plagiarism }}</td>
                </tr>
              </tbody>
            </table>
            <table v-else class="mp-audit">
              <thead><tr><th>检测对象</th><th>查重率</th><th>状态</th><th>时间</th></tr></thead>
              <tbody>
                <tr v-if="!detail.plagiarisms.length"><td colspan="4" class="mp-note">暂无查重记录</td></tr>
                <tr v-for="p in detail.plagiarisms" :key="p.id">
                  <td class="is-who">{{ p.version }}</td>
                  <td>{{ p.rate }}</td>
                  <td>{{ p.status }}</td>
                  <td>{{ p.time }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <AppSectionCard title="审计日志（本学生毕设档案）">
          <AppAuditTrail :records="auditRecords" empty-text="暂无审计记录" compact :show-ip="false" />
        </AppSectionCard>
      </div>
    </div>

    <AppDrawer v-model:visible="assignVisible" title="分配选题">
      <div class="ie-form">
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">选题</span>
          <select v-model="assignTopicId" class="ie-in">
            <option value="">请选择</option>
            <option v-for="t in topicOpts" :key="t.id" :value="t.id" :disabled="t.remaining <= 0">{{ t.title }}（余 {{ t.remaining }}）</option>
          </select>
        </label>
        <p v-if="actionError" class="ie-err">{{ actionError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="assignVisible = false">取消</button>
          <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting" @click="submitAssign">确认</button>
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
/** 毕设学生详情（/admin/graduation/students/:id）：批次/选题/节点 + 材料/成果/查重 + 状态机操作 + 审计。 */
import { ModulePageShell, ModuleToolbar, StatusTag, LoadingState, ErrorState } from '@/components/business'
import { AppDrawer } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppSensitiveText, AppAuditTrail, AppSectionCard, AppDescriptionList } from '@/components/common'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { toast } from '@/utils/toast'

export default {
  name: 'GraduationStudentDetailView',
  components: { ModulePageShell, ModuleToolbar, StatusTag, LoadingState, ErrorState, AppDrawer, AppConfirmDialog, AppSensitiveText, AppAuditTrail, AppSectionCard, AppDescriptionList },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', submitting: false, detail: null,
      tab: 'proposals',
      tabs: [
        { key: 'proposals', label: '开题记录' },
        { key: 'finals', label: '成果提交' },
        { key: 'plagiarisms', label: '查重记录' }
      ],
      assignVisible: false, assignTopicId: '', topicOpts: [], actionError: '',
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null }
    }
  },
  computed: {
    topicInfoItems() {
      if (!this.detail) return []
      const d = this.detail
      return [
        { key: 'studentNo', label: '学号', value: d.studentNo },
        { key: 'batchName', label: '毕设批次', value: d.batchName || '未关联' },
        { key: 'topicTitle', label: '课题名称', value: d.topicTitle },
        { key: 'topicSource', label: '课题来源', value: d.topicSource || '—' },
        { key: 'advisorName', label: '指导教师', value: d.advisorName || '未分配' },
        { key: 'taskbook', label: '任务书', value: d.taskbook },
        { key: 'phone', label: '联系电话', value: d.phone },
        { key: 'midterm', label: '中期检查', value: d.midterm?.conclusion },
        { key: 'defense', label: '答辩安排', value: d.defense?.group },
        { key: 'risk', label: '风险等级', value: d.riskLabel }
      ]
    },
    auditRecords() {
      return (this.detail?.auditTrail || []).map((a, i) => ({
        id: i,
        action: a.action,
        actor: a.who,
        at: a.time,
        target: a.affected
      }))
    },
    toolbarActions() {
      if (!this.detail || this.detail.stage === 'ARCHIVED') {
        return [{ key: 'back', label: '返回列表' }]
      }
      const actions = []
      if (!this.detail.topicId) actions.push({ key: 'assignTopic', label: '分配选题' })
      if (!this.detail.advisorName) actions.push({ key: 'assignAdvisor', label: '分配导师' })
      if (this.detail.stage !== 'DEFENSE' && this.detail.stage !== 'ARCHIVED') {
        actions.push({ key: 'advance', label: '推进节点', variant: 'primary' })
      }
      if (this.detail.stage === 'DEFENSE') actions.push({ key: 'archive', label: '归档' })
      actions.push({ key: 'risk', label: '标记风险' })
      return actions
    }
  },
  created() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.error = ''
      const res = await gdStudentApi.getStudentDetail(this.$route.params.id)
      if (res.code === 0) this.detail = res.data
      else this.error = res.message
      this.loading = false
    },
    async onToolbar(key) {
      if (key === 'back') { this.$router.push('/admin/graduation/students'); return }
      if (key === 'assignTopic') {
        const t = await gdStudentApi.getConfirmedTopics()
        if (t.code === 0) { this.topicOpts = t.data; this.assignTopicId = ''; this.actionError = ''; this.assignVisible = true }
        else toast.error(t.message)
      }
      if (key === 'assignAdvisor') {
        this.confirm = { visible: true, title: '分配指导教师', message: '填写指导教师姓名', type: 'primary', confirmText: '确认', requireReason: true, reasonLabel: '指导教师', action: 'ADVISOR' }
      }
      if (key === 'advance') {
        this.confirm = { visible: true, title: '推进节点', message: `确认将「${this.detail.name}」推进到下一节点？`, type: 'primary', confirmText: '推进', requireReason: false, reasonLabel: '备注', action: 'ADVANCE' }
      }
      if (key === 'archive') {
        this.confirm = { visible: true, title: '归档毕设档案', message: '归档后记录只读', type: 'warning', confirmText: '确认归档', requireReason: true, reasonLabel: '归档原因', action: 'ARCHIVE' }
      }
      if (key === 'risk') {
        this.confirm = { visible: true, title: '标记高风险', message: '将学生标记为高风险并留痕', type: 'warning', confirmText: '标记', requireReason: true, reasonLabel: '风险原因', action: 'RISK_HIGH' }
      }
    },
    async submitAssign() {
      this.actionError = ''; this.submitting = true
      try {
        const res = await gdStudentApi.assignTopic(this.detail.id, { topicId: this.assignTopicId })
        if (res.code === 0) { toast.success('已分配选题'); this.assignVisible = false; this.load() } else this.actionError = res.message
      } finally { this.submitting = false }
    },
    async onConfirm({ reason } = {}) {
      this.submitting = true
      try {
        let res
        const id = this.detail.id
        if (this.confirm.action === 'ADVISOR') res = await gdStudentApi.assignAdvisor(id, { advisorName: (reason || '').trim() })
        if (this.confirm.action === 'ADVANCE') res = await gdStudentApi.setStage(id, { action: 'ADVANCE', reason: reason || '' })
        if (this.confirm.action === 'ARCHIVE') res = await gdStudentApi.setStage(id, { action: 'ARCHIVE', reason: reason || '' })
        if (this.confirm.action === 'RISK_HIGH') res = await gdStudentApi.setRisk(id, { riskLevel: 'HIGH', reason: reason || '' })
        if (res && res.code === 0) { toast.success('已更新'); this.confirm.visible = false; this.load() } else if (res) toast.error(res.message)
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ie-form { padding: var(--space-4); display: flex; flex-direction: column; gap: var(--space-3); }
.ie-fld { display: flex; flex-direction: column; gap: var(--space-1); }
.ie-lbl { font-size: var(--font-size-sm); }
.ie-in { padding: var(--space-2); border: 1px solid var(--border-default); border-radius: var(--radius-sm); }
.ie-err { color: var(--danger-600); font-size: var(--font-size-sm); }
.ie-actions { display: flex; gap: var(--space-2); justify-content: flex-end; }
</style>
