<template>
  <AppPageShell
    title="谈心谈话台账"
    subtitle="全量谈话记录只读台账，按类型 / 状态筛选。心理类谈话原文由后端按角色脱敏。"
    role-name="学工处 / 学院 / 辅导员"
    data-scope-name="按数据范围（辅导员限绑定学生）"
    watermark-purpose="谈话台账查看"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载谈话台账..." @retry="load"
                    @back="$router.push('/admin/student-affairs/talk')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>

      <AppSectionCard title="谈话记录">
        <div class="tl-filters">
          <div class="tl-fgroup">
            <button v-for="f in typeFilters" :key="f.key" type="button" class="tl-chip"
                    :class="{ 'is-on': activeType === f.key }" @click="setType(f.key)">{{ f.label }}</button>
          </div>
          <div class="tl-fgroup">
            <button v-for="f in statusFilters" :key="f.key" type="button" class="tl-chip tl-chip--st"
                    :class="{ 'is-on': activeStatus === f.key }" @click="setStatus(f.key)">{{ f.label }}</button>
          </div>
        </div>
        <DataTable v-if="items.length" :columns="talkColumns" :rows="items" row-key="talkId">
          <template #cell-student="{ row }"><span class="mp-cell-main">{{ row.realName || ('学生#' + row.studentId) }}</span></template>
          <template #cell-studentNo="{ row }">{{ row.studentNo || '—' }}</template>
          <template #cell-type="{ row }">
            {{ typeLabel(row.talkType) }}
            <span v-if="row.psyMasked" class="tl-psy" title="心理谈话原文受限">🔒</span>
          </template>
          <template #cell-topic="{ row }"><span class="tl-topic">{{ row.topic || '—' }}</span></template>
          <template #cell-talkAt="{ row }"><AppDateDisplay :value="row.talkAt" mode="datetime" empty-text="—" /></template>
          <template #cell-needFollow="{ row }">{{ row.needFollow ? '是' : '—' }}</template>
          <template #cell-status="{ row }"><StatusTag :type="statusType(row.status)" :label="row.statusLabel || row.status" dot /></template>
        </DataTable>
        <p v-else class="sa-empty">当前范围与筛选下暂无谈话记录</p>
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppDateDisplay, AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard, AppStatusTag } from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'

const TALK_COLUMNS = [
  { key: 'student', title: '学生' },
  { key: 'studentNo', title: '学号' },
  { key: 'type', title: '类型' },
  { key: 'topic', title: '主题' },
  { key: 'talkAt', title: '谈话时间' },
  { key: 'needFollow', title: '需跟进' },
  { key: 'status', title: '状态' }
]
// 与真实发起入口 TalkWorkbenchView.vue 的 talkType 枚举保持一致（此前这里是一套完全不同的
// 旧枚举 LIFE/CAREER/ECONOMIC/IDEOLOGY/SAFETY/ROUTINE/OTHER，一个都不匹配真实数据，
// 导致台账列表"类型"列对新记录原样显示英文枚举码，见 CC-真实交互业务巡检）。
const TYPE_LABELS = {
  DAILY: '日常谈话', ACADEMIC: '学业帮扶', PSYCHOLOGY: '心理疏导', DISCIPLINE: '违纪教育',
  EMPLOYMENT: '就业指导', INTERNSHIP: '实习指导', AID: '资助谈话', DORM: '宿舍问题'
}
const TYPE_FILTERS = [
  { key: '', label: '全部类型' }, { key: 'DAILY', label: '日常谈话' }, { key: 'ACADEMIC', label: '学业帮扶' },
  { key: 'PSYCHOLOGY', label: '心理疏导' }, { key: 'DISCIPLINE', label: '违纪教育' },
  { key: 'EMPLOYMENT', label: '就业指导' }, { key: 'INTERNSHIP', label: '实习指导' },
  { key: 'AID', label: '资助谈话' }, { key: 'DORM', label: '宿舍问题' }
]
const STATUS_FILTERS = [
  { key: '', label: '全部状态' },
  { key: 'PLANNED', label: '计划中' },
  { key: 'COMPLETED', label: '已完成' },
  { key: 'FOLLOW_UP', label: '跟进中' },
  { key: 'CLOSED', label: '已关闭' }
]

export default {
  name: 'TalkLedgerView',
  components: { AppDateDisplay, AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard, StatusTag: AppStatusTag, DataTable },
  data() {
    return { talkColumns: TALK_COLUMNS, loading: true, errorMessage: '', items: [], statusCounts: null, activeType: '', activeStatus: '', typeFilters: TYPE_FILTERS, statusFilters: STATUS_FILTERS }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      return [
        { key: 't', label: '谈话总数', value: this.statusCounts === null ? '—' : (this.statusCounts.ALL || 0), accent: 'primary' },
        { key: 'p', label: '计划中', value: this.statusCounts === null ? '—' : (this.statusCounts.PLANNED || 0), accent: 'warning' },
        { key: 'n', label: '需跟进', value: '—', accent: 'risk' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      const params = { pageSize: 200 }
      if (this.activeType) params.talkType = this.activeType
      if (this.activeStatus) params.status = this.activeStatus
      const res = await studentAffairsApi.getTalks(params)
      if (res.code === 0 && res.data) {
        this.items = res.data.items || []
        this.statusCounts = res.data.statusCounts || null
      } else {
        this.errorMessage = res.message || '谈话台账加载失败'
      }
      this.loading = false
    },
    setType(k) { if (this.activeType === k) return; this.activeType = k; this.load() },
    setStatus(k) { if (this.activeStatus === k) return; this.activeStatus = k; this.load() },
    typeLabel(t) { return TYPE_LABELS[t] || t || '—' },
    statusType(s) {
      if (s === 'COMPLETED' || s === 'CLOSED') return 'success'
      if (s === 'FOLLOW_UP') return 'processing'
      if (s === 'PLANNED') return 'warning'
      return 'default'
    }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.tl-filters { display: flex; flex-direction: column; gap: var(--space-2); margin-bottom: var(--space-3); }
.tl-fgroup { display: flex; gap: var(--space-2); flex-wrap: wrap; }
.tl-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 4px 14px; font-size: var(--font-size-sm); cursor: pointer; }
.tl-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.tl-topic { color: var(--text-secondary); max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tl-psy { font-size: var(--font-size-xs); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } }
@import '@/styles/module-page.css';
</style>
