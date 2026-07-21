<template>
  <AppPageShell
    title="辅导员工作台"
    subtitle="按我的数据范围聚合：待处理风险、待跟进谈话与高频入口。复杂配置回各业务工作台处理。"
    role-name="辅导员"
    data-scope-name="本人带班 / 授权范围"
    watermark-purpose="辅导员工作台"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载工作台..." @retry="load"
                    @back="$router.push('/admin/student-affairs/dashboard')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>

      <div class="cw-cols">
        <AppSectionCard title="待处理风险学生">
          <DataTable v-if="activeRisks.length" :columns="riskColumns" :rows="activeRisks" row-key="riskId">
            <template #cell-student="{ row }">{{ row.realName || ('学生#' + row.studentId) }}</template>
            <template #cell-source="{ row }">{{ sourceLabel(row.source) }}</template>
            <template #cell-level="{ row }"><StatusTag :type="riskType(row.riskLevel)" :label="levelLabel(row.riskLevel)" dot /></template>
            <template #cell-actions="{ row }">
              <button type="button" class="cw-link" @click="$router.push('/admin/student-affairs/risk/' + row.riskId)">处置</button>
            </template>
          </DataTable>
          <p v-else class="sa-empty">暂无待处理风险</p>
        </AppSectionCard>

        <AppSectionCard title="待跟进 / 计划中谈话">
          <DataTable v-if="actionTalks.length" :columns="talkColumns" :rows="actionTalks" row-key="talkId">
            <template #cell-student="{ row }">{{ row.realName || row.studentName || ('学生#' + row.studentId) }}</template>
            <template #cell-topic="{ row }"><span class="cw-topic">{{ row.topic || row.topicType || '—' }}</span></template>
            <template #cell-status="{ row }"><StatusTag :type="talkType(row.status)" :label="row.statusLabel || row.status" dot /></template>
            <template #cell-actions>
              <button type="button" class="cw-link" @click="$router.push('/admin/student-affairs/talk')">处理</button>
            </template>
          </DataTable>
          <p v-else class="sa-empty">暂无待跟进谈话</p>
        </AppSectionCard>
      </div>

      <AppSectionCard title="高频入口">
        <div class="cw-quick">
          <button v-for="q in quickLinks" :key="q.route" type="button" class="cw-quickbtn" @click="$router.push(q.route)">{{ q.label }}</button>
        </div>
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard, AppStatusTag } from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'

const SRC = { LEAVE_OVERDUE: '请假逾期', ACADEMIC_WARNING: '学业预警', DORM: '宿舍', MENTAL: '心理', DISCIPLINE: '违纪', INTERNSHIP: '实习' }
const LEVEL = { LOW: '低', MEDIUM: '中', HIGH: '高', CRITICAL: '紧急' }
const ACTIVE_RISK = ['NEW', 'ASSIGNED', 'PROCESSING', 'FOLLOWING', 'REOPENED']
const ACTION_TALK = ['PLANNED', 'FOLLOW_UP']
const RISK_COLUMNS = [
  { key: 'student', title: '学生' },
  { key: 'source', title: '来源' },
  { key: 'level', title: '等级' },
  { key: 'actions', title: '', align: 'right', width: '80px' }
]
const TALK_COLUMNS = [
  { key: 'student', title: '学生' },
  { key: 'topic', title: '主题' },
  { key: 'status', title: '状态' },
  { key: 'actions', title: '', align: 'right', width: '80px' }
]

export default {
  name: 'CounselorWorkbenchView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard, StatusTag: AppStatusTag, DataTable },
  data() {
    return {
      riskColumns: RISK_COLUMNS,
      talkColumns: TALK_COLUMNS,
      loading: true, errorMessage: '', risks: [], talks: [],
      quickLinks: [
        { label: '请假审批', route: '/admin/student-affairs/leave' },
        { label: '风险预警', route: '/admin/student-affairs/risk' },
        { label: '谈心谈话', route: '/admin/student-affairs/talk' },
        { label: '班级管理', route: '/admin/student-affairs/profile' },
        { label: '困难认定', route: '/admin/student-affairs/aid' },
        { label: '违纪处分', route: '/admin/student-affairs/discipline' }
      ]
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    activeRisks() { return this.risks.filter((r) => ACTIVE_RISK.includes(r.status)) },
    actionTalks() { return this.talks.filter((t) => ACTION_TALK.includes(t.status)) },
    metricCards() {
      const critical = this.activeRisks.filter((r) => ['HIGH', 'CRITICAL'].includes(r.riskLevel)).length
      return [
        { key: 'r', label: '待处理风险', value: this.activeRisks.length, accent: this.activeRisks.length ? 'warning' : 'success' },
        { key: 'c', label: '高/紧急风险', value: critical, accent: critical ? 'risk' : 'success' },
        { key: 't', label: '待跟进谈话', value: this.actionTalks.length, accent: this.actionTalks.length ? 'warning' : 'success' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      const [rk, tk] = await Promise.all([
        studentAffairsApi.getRisks({ pageSize: 200 }),
        studentAffairsApi.getTalks({ pageSize: 200 })
      ])
      if (rk.code === 0 && rk.data) this.risks = rk.data.items || []
      else this.errorMessage = rk.message || '工作台加载失败'
      this.talks = (tk.code === 0 && tk.data) ? (tk.data.items || tk.data.list || []) : []
      this.loading = false
    },
    sourceLabel(s) { return SRC[s] || s || '—' },
    levelLabel(l) { return LEVEL[l] || l || '—' },
    riskType(l) { return ({ LOW: 'default', MEDIUM: 'warning', HIGH: 'danger', CRITICAL: 'danger' })[l] || 'default' },
    talkType(s) { return ({ PLANNED: 'warning', FOLLOW_UP: 'warning', COMPLETED: 'success', CLOSED: 'default' })[s] || 'processing' }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.cw-cols { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); margin-bottom: var(--space-4); }
.sa-empty { color: var(--text-tertiary); padding: var(--space-3); text-align: center; }
.cw-topic { color: var(--text-secondary); font-size: var(--font-size-sm); }
.cw-link { border: none; background: none; color: var(--color-primary); cursor: pointer; font-size: var(--font-size-sm); }
.cw-quick { display: flex; gap: var(--space-3); flex-wrap: wrap; }
.cw-quickbtn { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-md); padding: 10px 20px; cursor: pointer; font-size: var(--font-size-sm); }
.cw-quickbtn:hover { border-color: var(--color-primary); color: var(--color-primary); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } .cw-cols { grid-template-columns: 1fr; } }
@import '@/styles/module-page.css';
</style>
