<template>
  <AppPageShell title="重点学生跟进" subtitle="需跟进的谈话与中高风险学生汇总，形成重点关注跟进清单。按数据范围裁剪。"
    role-name="辅导员 / 学院" data-scope-name="本人带班 / 授权范围" watermark-purpose="重点学生跟进">
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="加载中..." @retry="load"
                    @back="$router.push('/admin/student-affairs/talk')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>
      <AppSectionCard title="待跟进谈话">
        <DataTable v-if="followTalks.length" :columns="talkColumns" :rows="followTalks" row-key="talkId">
          <template #cell-student="{ row }"><span class="mp-cell-main">{{ row.realName || row.studentName || ('#'+row.studentId) }}</span></template>
          <template #cell-topic="{ row }"><span class="ks-topic">{{ row.topic || row.topicType || '—' }}</span></template>
          <template #cell-status="{ row }"><StatusTag type="warning" :label="row.statusLabel || row.status" dot /></template>
          <template #cell-actions="{ row }">
            <button type="button" class="ks-link" @click="$router.push('/admin/student-affairs/talk')">去处理</button>
          </template>
        </DataTable>
        <p v-else class="sa-empty">暂无待跟进谈话</p>
      </AppSectionCard>
      <AppSectionCard title="中高风险学生">
        <DataTable v-if="keyRisks.length" :columns="riskColumns" :rows="keyRisks" row-key="riskId">
          <template #cell-student="{ row }"><span class="mp-cell-main">{{ row.realName || ('#'+row.studentId) }}</span></template>
          <template #cell-source="{ row }">{{ sourceLabel(row.source) }}</template>
          <template #cell-level="{ row }"><StatusTag :type="row.riskLevel==='CRITICAL'?'danger':'warning'" :label="levelLabel(row.riskLevel)" dot /></template>
          <template #cell-actions="{ row }">
            <button type="button" class="ks-link" @click="$router.push('/admin/student-affairs/risk/' + row.riskId)">处置</button>
          </template>
        </DataTable>
        <p v-else class="sa-empty">暂无中高风险学生</p>
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
const KEY_LEVEL = ['HIGH', 'CRITICAL']
const ACTIVE_RISK = ['NEW', 'ASSIGNED', 'PROCESSING', 'FOLLOWING', 'REOPENED']
const TALK_COLUMNS = [
  { key: 'student', title: '学生' },
  { key: 'topic', title: '主题' },
  { key: 'status', title: '状态' },
  { key: 'actions', title: '', align: 'right', width: '80px' }
]
const RISK_COLUMNS = [
  { key: 'student', title: '学生' },
  { key: 'source', title: '来源' },
  { key: 'level', title: '等级' },
  { key: 'actions', title: '', align: 'right', width: '80px' }
]

export default {
  name: 'KeyStudentFollowView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard, StatusTag: AppStatusTag, DataTable },
  data() { return { talkColumns: TALK_COLUMNS, riskColumns: RISK_COLUMNS, loading: true, errorMessage: '', talks: [], risks: [] } },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    followTalks() { return this.talks.filter((t) => ['PLANNED', 'FOLLOW_UP'].includes(t.status)) },
    keyRisks() { return this.risks.filter((r) => ACTIVE_RISK.includes(r.status) && KEY_LEVEL.includes(r.riskLevel)) },
    metricCards() {
      return [
        { key: 't', label: '待跟进谈话', value: this.followTalks.length, accent: this.followTalks.length ? 'warning' : 'success' },
        { key: 'r', label: '中高风险学生', value: this.keyRisks.length, accent: this.keyRisks.length ? 'risk' : 'success' },
        { key: 's', label: '重点学生合计', value: new Set([...this.followTalks.map((t) => t.studentId), ...this.keyRisks.map((r) => r.studentId)]).size, accent: 'primary' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      // 待服务端全量统计：重点名单聚合仅加载各接口单页上限。
      const [tk, rk] = await Promise.all([studentAffairsApi.getTalks({ pageSize: 200 }), studentAffairsApi.getRisks({ pageSize: 200 })])
      this.talks = (tk.code === 0 && tk.data) ? (tk.data.items || tk.data.list || []) : []
      if (rk.code === 0 && rk.data) this.risks = rk.data.items || []
      else this.errorMessage = rk.message || '加载失败'
      this.loading = false
    },
    sourceLabel(s) { return SRC[s] || s || '—' },
    levelLabel(l) { return LEVEL[l] || l || '—' }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.sa-empty { color: var(--text-tertiary); padding: var(--space-3); text-align: center; }
.ks-topic { color: var(--text-secondary); font-size: var(--font-size-sm); }
.ks-link { border: none; background: none; color: var(--color-primary); cursor: pointer; font-size: var(--font-size-sm); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } }
@import '@/styles/module-page.css';
</style>
