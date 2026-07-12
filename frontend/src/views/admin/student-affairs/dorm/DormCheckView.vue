<template>
  <AppPageShell
    title="宿舍检查"
    subtitle="卫生/安全/违禁/夜不归宿检查任务与记录；异常须绑真实涉事学生（夜不归宿必填），自动进入风险处置。"
    role-name="宿管 / 辅导员 / 学工处"
    data-scope-name="宿管限负责楼栋"
    watermark-purpose="宿舍检查登记"
  >
    <template #actions>
      <AppPermissionButton code="studentAffairs.dorm.inspection.manage" :loading="actioning" @click="createTask">
        新建检查任务
      </AppPermissionButton>
    </template>

    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载检查任务..." @retry="load"
                    @back="$router.push('/admin/student-affairs/dashboard')">
      <AppSectionCard title="检查任务">
        <table class="sa-table">
          <thead><tr><th>任务</th><th>类型</th><th>楼栋</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="t in tasks" :key="t.taskId" :class="{ 'sa-sel': t.taskId === curTask }">
              <td><strong>{{ t.taskName }}</strong></td>
              <td>{{ typeLabel(t.checkType) }}</td>
              <td>{{ t.buildingName || '—' }}</td>
              <td>{{ t.status }}</td>
              <td class="sa-actions">
                <AppPermissionButton code="studentAffairs.dorm.view" size="sm" variant="secondary" @click="openTask(t)">记录</AppPermissionButton>
                <AppPermissionButton code="studentAffairs.dorm.inspection.manage" size="sm" :loading="actioning" @click="addRecord(t)">录结果</AppPermissionButton>
              </td>
            </tr>
            <tr v-if="!tasks.length"><td colspan="5" class="sa-empty">暂无检查任务</td></tr>
          </tbody>
        </table>
      </AppSectionCard>

      <AppSectionCard v-if="curTask" :title="`检查记录 · ${curTaskName}`">
        <table class="sa-table">
          <thead><tr><th>房间</th><th>结果</th><th>问题</th><th>说明</th><th>关联风险</th></tr></thead>
          <tbody>
            <tr v-for="r in records" :key="r.recordId">
              <td>{{ r.roomNo || r.roomId || '—' }}</td>
              <td><AppStatusTag :type="r.result === 'ABNORMAL' ? 'danger' : 'success'" :label="r.result === 'ABNORMAL' ? '异常' : '正常'" /></td>
              <td>{{ r.issueType || '—' }}</td>
              <td>{{ r.detail || '—' }}</td>
              <td><a v-if="r.relatedRiskId" class="sa-link" @click="$router.push(`/admin/student-affairs/risk/${r.relatedRiskId}`)">风险 #{{ r.relatedRiskId }} →</a><span v-else class="sa-muted">—</span></td>
            </tr>
            <tr v-if="!records.length"><td colspan="5" class="sa-empty">暂无检查记录</td></tr>
          </tbody>
        </table>
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppPageShell, AppPermissionButton, AppSectionCard, AppStatusTag } from '@/components/common'
import { studentAffairsApi } from '@/modules/student-affairs/api/studentAffairs.api'

export default {
  name: 'DormCheckView',
  components: { AppGlobalState, AppPageShell, AppPermissionButton, AppSectionCard, AppStatusTag },
  data() { return { loading: true, actioning: false, errorMessage: '', tasks: [], curTask: '', curTaskName: '', curTaskType: '', records: [] } },
  computed: { pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') } },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      try { this.tasks = (await studentAffairsApi.listDormCheckTasks({ pageSize: 100 })).data.items || [] }
      catch (e) { this.errorMessage = e.message || '检查任务加载失败' } finally { this.loading = false }
    },
    async openTask(t) {
      this.curTask = t.taskId; this.curTaskName = t.taskName; this.curTaskType = t.checkType
      try { this.records = (await studentAffairsApi.listDormCheckRecords(t.taskId)).data.items || [] }
      catch (e) { this.errorMessage = e.message }
    },
    async createTask() {
      const name = window.prompt('任务名称', '月度卫生检查')
      if (!name) return
      const checkType = (window.prompt('类型 HYGIENE/SAFETY/CONTRABAND/NIGHT_ABSENCE', 'HYGIENE') || 'HYGIENE').toUpperCase()
      const buildingId = window.prompt('楼栋 ID（可空）', '') || null
      await this.runAction(() => studentAffairsApi.createDormCheckTask({ taskName: name.trim(), checkType, buildingId }))
    },
    async addRecord(t) {
      const roomId = window.prompt('房间 ID（可空）', '') || null
      const result = (window.prompt('结果 NORMAL/ABNORMAL', 'ABNORMAL') || 'ABNORMAL').toUpperCase()
      const body = { roomId, result, issueType: t.checkType }
      if (result === 'ABNORMAL') {
        const detail = window.prompt('异常说明（不少于 5 字）', '')
        if (!detail || detail.trim().length < 5) { if (detail !== null) window.alert('说明不少于 5 字'); return }
        body.detail = detail.trim()
        const needStu = t.checkType === 'NIGHT_ABSENCE'
        const sid = window.prompt(needStu ? '涉事学生 ID（夜不归宿必填）' : '涉事学生 ID（可空；填则绑风险）', '')
        if (needStu && !sid) { window.alert('夜不归宿须指定学生'); return }
        if (sid) body.studentId = sid.trim()
      }
      await this.runAction(async () => { await studentAffairsApi.submitDormCheckRecord(t.taskId, body); this.curTask && await this.openTask(t) })
    },
    async runAction(fn) {
      this.actioning = true
      try { await fn(); await this.load() } catch (e) { this.errorMessage = e.message || '操作失败' } finally { this.actioning = false }
    },
    typeLabel(t) { return ({ HYGIENE: '卫生', SAFETY: '安全', CONTRABAND: '违禁品', NIGHT_ABSENCE: '夜不归宿' })[t] || t }
  }
}
</script>

<style scoped>
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-3); text-align: left; }
.sa-actions { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.sa-sel { background: var(--primary-50, var(--bg-subtle)); }
.sa-link { color: var(--primary-600); cursor: pointer; }
.sa-muted { color: var(--text-tertiary); }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
</style>
