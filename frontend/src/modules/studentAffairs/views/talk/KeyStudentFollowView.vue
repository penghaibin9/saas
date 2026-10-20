<template>
  <AppPageShell title="重点学生跟进"
    role-name="辅导员 / 学院" data-scope-name="本人带班 / 授权范围" watermark-purpose="重点学生跟进">
    <template #actions><AppButton variant="secondary" :loading="loading" @click="load">刷新</AppButton></template>
    <div class="ks-queues" aria-label="跟进事项类型">
      <button type="button" :aria-pressed="activeQueue === 'talk'" @click="setQueue('talk')">待跟进谈话</button>
      <button type="button" :aria-pressed="activeQueue === 'risk'" @click="setQueue('risk')">高风险事项</button>
    </div>
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="加载中..." @retry="load"
                    @back="$router.push('/admin/student-affairs/talk')">
      <section v-if="activeQueue === 'talk'" aria-label="待跟进谈话清单">
        <DataTable :columns="talkColumns" :rows="items" row-key="talkId" :pagination="pagination.total ? pagination : null" @page-change="onPageChange">
          <template #cell-student="{ row }"><span class="mp-cell-main">{{ row.realName || row.studentName || ('#'+row.studentId) }}</span></template>
          <template #cell-topic="{ row }"><span class="ks-topic">{{ row.topic || row.topicType || '—' }}</span></template>
          <template #cell-status="{ row }"><StatusTag type="warning" :label="row.statusLabel || row.status" dot /></template>
          <template #cell-actions="{ row }">
            <button type="button" class="ks-link" @click="openTalk(row)">办理谈话</button>
          </template>
        </DataTable>
        <p v-if="!items.length" class="sa-empty">暂无待跟进谈话</p>
      </section>
      <section v-else aria-label="高风险事项清单">
        <DataTable :columns="riskColumns" :rows="items" row-key="riskId" :pagination="pagination.total ? pagination : null" @page-change="onPageChange">
          <template #cell-student="{ row }"><span class="mp-cell-main">{{ row.realName || ('#'+row.studentId) }}</span></template>
          <template #cell-source="{ row }">{{ sourceLabel(row.source) }}</template>
          <template #cell-level="{ row }"><StatusTag :type="row.riskLevel==='CRITICAL'?'danger':'warning'" :label="levelLabel(row.riskLevel)" dot /></template>
          <template #cell-actions="{ row }">
            <button type="button" class="ks-link" @click="$router.push('/admin/student-affairs/risk/' + row.riskId)">处置</button>
          </template>
        </DataTable>
        <p v-if="!items.length" class="sa-empty">暂无在办高风险事项</p>
      </section>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppPageShell, AppStatusTag } from '@/components/common'
import { AppButton } from '@/components/ui'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'

const SRC = { LEAVE_OVERDUE: '请假逾期', ACADEMIC_WARNING: '学业预警', DORM: '宿舍', MENTAL: '心理', DISCIPLINE: '违纪', INTERNSHIP: '实习' }
const LEVEL = { LOW: '低', MEDIUM: '中', HIGH: '高', CRITICAL: '紧急' }
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
  components: { AppButton, AppGlobalState, AppPageShell, StatusTag: AppStatusTag, DataTable },
  data() { return { talkColumns: TALK_COLUMNS, riskColumns: RISK_COLUMNS, activeQueue: 'talk', loading: true, errorMessage: '', items: [], requestId: 0, pagination: { page: 1, pageSize: 20, total: 0 } } },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') }
  },
  mounted() { this.readRoute() },
  watch: { '$route.query'() { this.readRoute() } },
  beforeUnmount() { this.requestId++ },
  methods: {
    readRoute() {
      this.activeQueue = this.$route.query.queue === 'risk' ? 'risk' : 'talk'
      const page = Number(this.$route.query.page)
      this.pagination.page = Number.isSafeInteger(page) && page > 0 ? page : 1
      this.load()
    },
    setQueue(queue) { if (queue !== this.activeQueue) this.$router.replace({ query: { ...this.$route.query, queue, page: '1' } }) },
    onPageChange(page) { this.$router.replace({ query: { ...this.$route.query, page: String(page) } }) },
    openTalk(row) {
      this.$router.push({ path: '/admin/student-affairs/talk', query: { studentId: String(row.studentId), talkId: String(row.talkId) } })
    },
    async load() {
      const requestId = ++this.requestId
      this.loading = true; this.errorMessage = ''
      this.items = []; this.pagination.total = 0
      const params = { page: this.pagination.page, pageSize: this.pagination.pageSize }
      try {
        const res = this.activeQueue === 'talk'
          ? await studentAffairsApi.getTalks({ ...params, status: 'PLANNED,SCHEDULED,FOLLOW_UP' })
          : await studentAffairsApi.getRisks({ ...params, status: 'OPEN', priority: 'HIGH_CRITICAL' })
        if (requestId !== this.requestId) return
        if (res.code !== 0 || !res.data) throw new Error(res.message || '加载失败')
        this.items = res.data.items || []
        this.pagination.total = res.data.total ?? 0
      } catch (e) {
        if (requestId === this.requestId) this.errorMessage = e.message || '加载失败，请重试'
      } finally { if (requestId === this.requestId) this.loading = false }
    },
    sourceLabel(s) { return SRC[s] || (s ? '状态待确认' : '—') },
    levelLabel(l) { return LEVEL[l] || l || '—' }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ks-queues { display: flex; gap: 24px; border-bottom: 1px solid var(--line, var(--border-light)); }
.ks-queues button { border: 0; border-bottom: 2px solid transparent; padding: 10px 0; background: transparent; color: var(--text-secondary); font: inherit; cursor: pointer; }
.ks-queues button[aria-pressed="true"] { color: var(--color-primary); border-bottom-color: var(--color-primary); font-weight: 600; }
.ks-queues button:focus-visible, .ks-link:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 3px; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-3); text-align: center; }
.ks-topic { color: var(--text-secondary); font-size: var(--font-size-sm); }
.ks-link { border: none; background: none; color: var(--color-primary); cursor: pointer; font-size: var(--font-size-sm); }
</style>
