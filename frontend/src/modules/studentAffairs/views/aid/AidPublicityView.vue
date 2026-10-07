<template>
  <AppPageShell
    title="困难认定公示待办"
    subtitle="学校终审通过、进入公示期的认定申请。公示期满可扫描批量转通过，或逐条人工确认。"
    :role-name="ctx?.currentRole?.roleName || ''"
    :data-scope-name="ctx?.dataScope?.scopeName || ''"
    watermark-purpose="困难认定公示确认"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载公示名单..." @retry="load"
                    @back="$router.push('/admin/student-affairs/aid')">
      <div class="sa-toolbar">
        <div class="sa-grid sa-grid--metrics">
          <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
        </div>
        <button type="button" class="ap-refresh" :disabled="loading || scanning || !!actingId" @click="load">刷新进度</button>
        <AppPermissionButton :allowed="canBtn('studentAffairs.aid.approve')" code="studentAffairs.aid.approve" :loading="scanning" @click="scan">
          公示期满扫描
        </AppPermissionButton>
      </div>

      <AppSectionCard title="公示中的认定申请">
        <p class="ap-note">公示信息仅展示允许字段（姓名 / 学号 / 拟认定等级）；家庭经济明细在公示页不呈现。</p>
        <p v-if="scanResult" class="ap-note" role="status">{{ scanResult }}</p>
        <DataTable v-if="items.length" :columns="publicityColumns" :rows="items" row-key="applyId">
          <template #cell-student="{ row }"><span class="mp-cell-main">{{ row.realName || ('学生#' + row.studentId) }}</span></template>
          <template #cell-studentNo="{ row }">{{ row.studentNo || '—' }}</template>
          <template #cell-level="{ row }"><StatusTag type="processing" :label="levelLabel(row.finalLevel || row.applyLevel)" dot /></template>
          <template #cell-deadline="{ row }"><span>{{ displayTime(row.publicityEnd) }}</span><small class="ap-deadline-note">{{ row.hasPendingObjection ? '异议复核完成后再确认' : row.publicityHint }}</small></template>
          <template #cell-objection="{ row }">
            <StatusTag v-if="row.hasPendingObjection" type="warning" label="异议待复核" dot />
            <span v-else>—</span>
          </template>
          <template #cell-actions="{ row }">
            <AppPermissionButton :allowed="canBtn('studentAffairs.aid.approve')" v-if="row.publicityReady && !row.hasPendingObjection" code="studentAffairs.aid.approve" size="sm" variant="secondary"
                                 :loading="actingId === row.applyId" @click="confirm(row)">
              确认公示期满 → 通过
            </AppPermissionButton>
            <span v-else class="ap-blocked">{{ row.hasPendingObjection ? '请先完成异议复核' : '暂不可确认' }}</span>
          </template>
        </DataTable>
        <p v-else class="sa-empty">当前无公示中的认定申请</p>
        <AppPagination v-model:page="pagination.page" v-model:pageSize="pagination.pageSize"
                       :total="pagination.total" @change="load" />
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppMetricCard, AppPageShell, AppPagination, AppPermissionButton, AppSectionCard, AppStatusTag } from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'
import { canCode } from '@/modules/studentAffairs/composables/permission'


const LEVELS = { SPECIAL: '特别困难', DIFFICULT: '困难', GENERAL: '一般困难' }
const PUBLICITY_COLUMNS = [
  { key: 'student', title: '学生' },
  { key: 'studentNo', title: '学号' },
  { key: 'level', title: '拟认定等级' },
  { key: 'deadline', title: '公示截止与进度' },
  { key: 'objection', title: '异议' },
  { key: 'actions', title: '操作', align: 'right', width: '200px' }
]

export default {
  name: 'AidPublicityView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppPagination, AppPermissionButton, AppSectionCard, StatusTag: AppStatusTag, DataTable },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      publicityColumns: PUBLICITY_COLUMNS,
      loading: true, scanning: false, actingId: '', errorMessage: '', items: [], scanResult: '', loadSeq: 0, levelTotals: { SPECIAL: null, DIFFICULT: null },
      pagination: { page: 1, pageSize: 20, total: 0 }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      return [
        { key: 'all', label: '公示中', value: this.pagination.total, accent: 'primary' },
        { key: 'sp', label: '特别困难', value: this.levelTotals.SPECIAL ?? '—', accent: 'risk' },
        { key: 'df', label: '困难', value: this.levelTotals.DIFFICULT ?? '—', accent: 'warning' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    async load() {
      const seq = ++this.loadSeq
      this.loading = true; this.errorMessage = ''
      try {
      const [pageRes, specialRes, difficultRes] = await Promise.all([
        studentAffairsApi.getAidApplications({ status: 'PUBLICITY', page: this.pagination.page, pageSize: this.pagination.pageSize }),
        studentAffairsApi.getAidApplications({ status: 'PUBLICITY', level: 'SPECIAL', pageSize: 1 }),
        studentAffairsApi.getAidApplications({ status: 'PUBLICITY', level: 'DIFFICULT', pageSize: 1 })
      ])
      if (seq !== this.loadSeq) return
      if (pageRes.code === 0 && pageRes.data) {
        this.items = pageRes.data.items || []
        this.pagination.total = pageRes.data.total != null ? pageRes.data.total : this.items.length
      } else {
        this.errorMessage = pageRes.message || '公示名单加载失败'
      }
      this.levelTotals = {
        SPECIAL: specialRes.code === 0 ? specialRes.data?.total ?? null : null,
        DIFFICULT: difficultRes.code === 0 ? difficultRes.data?.total ?? null : null
      }
      } catch {
        if (seq === this.loadSeq) this.errorMessage = '公示名单暂未加载，请重试'
      } finally { if (seq === this.loadSeq) this.loading = false }
    },
    async scan() {
      if (this.scanning || this.actingId) return
      this.scanning = true
      try {
      const res = await studentAffairsApi.scanAidPublicity()
      if (res.code === 0) {
        const n = (res.data && res.data.count) || 0
        this.scanResult = `本次确认 ${n} 条；有异议待复核 ${res.data?.skippedObjection || 0} 条；批次异常 ${res.data?.invalidBatch || 0} 条。每次最多确认200条，剩余到期事项可继续扫描。`
        toast.success(n ? `公示期满 ${n} 条已转通过` : '暂无到期公示')
        this.pagination.page = 1
        await this.load()
      } else {
        toast.error(res.message || '扫描失败')
      }
      } catch { toast.error('扫描结果暂未获取，请刷新核对后再办理') }
      finally { this.scanning = false }
    },
    async confirm(it) {
      if (this.actingId || this.scanning) return
      if (!it.publicityReady || it.hasPendingObjection) { toast.error(it.hasPendingObjection ? '请先完成异议复核' : '公示期尚未结束或期限信息缺失，请刷新核对'); return }
      this.actingId = it.applyId
      try {
        const res = await studentAffairsApi.confirmAidPublicity(it.applyId, it.version)
        if (res.code === 0) {
          toast.success('已确认通过，进入困难库')
          this.pagination.page = 1
          await this.load()
        } else {
          toast.error(res.message || '确认失败，请刷新后核对当前状态')
        }
      } catch {
        toast.error('确认结果暂未获取，请刷新核对后再办理')
      } finally {
        this.actingId = ''
      }
    },
    levelLabel(l) { return LEVELS[l] || '等级待确认' },
    displayTime(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '期限待核对' }
  }
}
</script>

<style scoped>
.sa-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); margin-bottom: var(--space-4); flex-wrap: wrap; }
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-4); flex: 1; min-width: 320px; }
.ap-note { color: var(--text-tertiary); font-size: var(--font-size-sm); margin-bottom: var(--space-3); }
.ap-blocked { color: var(--text-secondary); font-size: var(--font-size-sm); }
.ap-deadline-note { display: block; margin-top: 4px; color: var(--text-tertiary); line-height: 1.5; }
.ap-refresh { padding: 7px 12px; border: 1px solid var(--border-color); border-radius: 6px; background: var(--surface); color: var(--text-primary); cursor: pointer; }
.ap-refresh:disabled { opacity: .55; cursor: default; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } }
@import '@/styles/module-page.css';
</style>
