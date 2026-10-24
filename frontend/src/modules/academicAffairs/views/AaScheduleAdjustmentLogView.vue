<template>
  <ModulePageShell
    class="aa-schedule-workspace"
    title="课表调整记录"
    subtitle="查询排课、改排、发布及作废的操作记录。"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/schedule')">课表批次</AppButton>
    </template>

    <div class="mp-stack">
      <AaScheduleObjectBar
        name="查询范围"
        :identity="activeFilterLabel"
        source="调停课申请及审批结果请到调停课台账查看。"
        status="仅供查看"
        :owner="ctx.currentRole.roleName || '教务排课岗'"
        next-owner="返回对应批次或调停课台账"
      />

      <div class="aa-adjust-metrics" aria-label="调整记录概览">
        <article><span>符合条件的记录</span><strong>{{ loading || error ? '—' : total }}</strong></article>
        <article><span>本页课程安排变更</span><strong>{{ loading || error ? '—' : pageTypeCount('AA_SCHEDULE') }}</strong></article>
        <article><span>本页批次变更</span><strong>{{ loading || error ? '—' : pageTypeCount('AA_SCHEDULE_BATCH') }}</strong></article>
      </div>

      <AppSectionCard compact title="调整记录">
        <div class="aa-filter">
          <label class="aa-filter__item">
            记录类型
            <AppSelect v-model="bizType" :options="bizTypeOptions" @change="reload" />
          </label>
          <label class="aa-filter__item">
            动作
            <AppSelect v-model="action" :options="actionSelectOptions" @change="reload" />
          </label>
          <AppButton @click="reload">查询</AppButton>
        </div>
        <ErrorState v-if="error" :description="error" @retry="reload" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="暂无匹配记录" description="可调整记录类型或操作筛选" />
        <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
          <template #cell-bizType="{ row }">
            <AppStatusTag :type="row.bizType === 'AA_SCHEDULE' ? 'info' : 'default'" dot>
              {{ typeLabel(row.bizType) }}
            </AppStatusTag>
          </template>
          <template #cell-action="{ row }">{{ actionLabel(row.action) }}</template>
          <template #cell-occurredAt="{ row }">{{ formatDateTime(row.occurredAt) }}</template>
          <template #cell-roleName="{ row }">{{ roleLabel(row.roleName) }}</template>
          <template #cell-bizId="{ row }">
            <details class="aa-detail"><summary>实施人员使用</summary>
              <p>关联编号：{{ row.bizId || '—' }}；记录编号：{{ row.id }}</p>
              <p v-if="technicalDetail(row)">{{ row.detail }}</p>
            </details>
          </template>
          <template #cell-detail="{ row }">
            <span class="aa-detail">{{ businessDetail(row) || '—' }}</span>
          </template>
        </DataTable>
      </AppSectionCard>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 课表调整记录（/admin/academic-affairs/schedule/adjustments）：13B 课表管理续工第三轮新增。
 * GET /academic-affairs/schedule/adjustments?bizType=&action=&page=&pageSize=，与
 * 「学院专业班级 · 变更审计」（list_org_audit）同一「审计留痕直读」模式，只读，不落新表。
 * bizType 精确枚举 AA_SCHEDULE（条目级）/ AA_SCHEDULE_BATCH（批次级），与调停课台账
 * （AA_SCHEDULE_CHANGE，独立二级模块）、课表导出审计（AA_SCHEDULE_EXPORT，见「课表导出」页）
 * 互不混入。
 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppStatusTag, AppSelect } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import AaScheduleObjectBar from '@/modules/academicAffairs/components/AaScheduleObjectBar.vue'
import { ROLE_LABELS } from '@/modules/workflow/constants/workflow.constants.js'
import { safeLocalizedText } from '@/utils/presentationSafety.js'
import { formatDateTime } from '@/utils/dateUtils.js'

const ACTION_LABELS = {
  CREATE: '新建批次', ADD_ITEM: '手工排课', IMPORT: '导入课表', ADJUST_ITEM: '改排条目',
  TEACHER_OBJECT: '教师提出异议', PRE_PUBLISH: '预发布', PUBLISH: '发布', VOID_REISSUE: '作废重发',
  ARCHIVE: '归档', OPEN_CORRECTION_DRAFT: '发起课表纠错', START_CORRECTION_DRAFT: '创建纠错草稿', MOVE_ITEM: '移动课程安排'
}
const ITEM_ACTIONS = ['ADD_ITEM', 'ADJUST_ITEM', 'TEACHER_OBJECT']
const BATCH_ACTIONS = ['CREATE', 'IMPORT', 'PRE_PUBLISH', 'PUBLISH', 'VOID_REISSUE', 'ARCHIVE']

export default {
  name: 'AaScheduleAdjustmentLogView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppStatusTag, AppSelect, AaScheduleObjectBar },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      bizType: '', action: '', rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',
      columns: [
        { key: 'occurredAt', title: '时间' },
        { key: 'bizType', title: '类型' },
        { key: 'action', title: '动作' },
        { key: 'bizId', title: '实施信息' },
        { key: 'operator', title: '操作人' },
        { key: 'roleName', title: '角色' },
        { key: 'detail', title: '详情' }
      ]
    }
  },
  computed: {
    pagination() { return { page: this.page, pageSize: this.pageSize, total: this.total } },
    bizTypeOptions() {
      return [
        { value: '', label: '全部类型' },
        { value: 'AA_SCHEDULE', label: '课程安排变更' },
        { value: 'AA_SCHEDULE_BATCH', label: '批次变更' }
      ]
    },
    actionOptions() {
      if (this.bizType === 'AA_SCHEDULE') return ITEM_ACTIONS
      if (this.bizType === 'AA_SCHEDULE_BATCH') return BATCH_ACTIONS
      return [...ITEM_ACTIONS, ...BATCH_ACTIONS]
    },
    actionSelectOptions() {
      return [{ value: '', label: '全部动作' }, ...this.actionOptions.map((value) => ({ value, label: this.actionLabel(value) }))]
    },
    activeFilterLabel() {
      const type = this.bizTypeOptions.find((item) => item.value === this.bizType)?.label || '全部类型'
      const action = this.actionSelectOptions.find((item) => item.value === this.action)?.label || '全部动作'
      return `${type} / ${action}`
    }
  },
  created() { this.load() },
  methods: {
    actionLabel(a) { return ACTION_LABELS[a] || (a ? '其他操作' : '—') },
    typeLabel(value) { return { AA_SCHEDULE: '课程安排', AA_SCHEDULE_BATCH: '批次' }[value] || '其他事项' },
    roleLabel(value) { return safeLocalizedText({ value, dictionary: { ...ROLE_LABELS, TEACHER: '教师', ACADEMIC_TEACHER: '任课教师' }, unknownLabel: value ? '其他业务角色' : '—' }) },
    formatDateTime,
    technicalDetail(row) {
      if (['TEACHER_OBJECT', 'VOID_REISSUE'].includes(row.action)) return false
      return /(?:^|[;,])\s*[A-Za-z][A-Za-z0-9_]*=/.test(row.detail || '')
    },
    businessDetail(row) {
      if (!this.technicalDetail(row)) return row.detail || ''
      if (row.action === 'OPEN_CORRECTION_DRAFT') return String(row.detail).match(/^draftBatchId=\d+;reason=([\s\S]*)$/)?.[1] || ''
      if (row.action === 'START_CORRECTION_DRAFT') return String(row.detail).match(/^sourceBatchId=\d+;clonedItems=\d+;reason=([\s\S]*)$/)?.[1] || ''
      return String(row.detail).match(/(?:^|;)(周\d+第\d+节)(?:;|$)/)?.[1] || ''
    },
    pageTypeCount(type) { return this.rows.filter((row) => row.bizType === type).length },
    reload() { this.page = 1; this.load() },
    onPageChange(p) { this.page = p; this.load() },
    async load() {
      this.loading = true
      this.error = ''
      try {
        const res = await academicAffairsApi.getScheduleAdjustments({
          bizType: this.bizType || undefined, action: this.action || undefined,
          page: this.page, pageSize: this.pageSize
        })
        if (res.code === 0) {
          this.rows = res.data?.list || []
          this.total = res.data?.total || 0
        } else {
          this.error = res.message || '调整记录读取失败'
          this.rows = []
          this.total = 0
        }
      } catch (error) {
        this.error = error?.message || '网络连接中断，未能读取调整记录'
        this.rows = []
        this.total = 0
      } finally { this.loading = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
@import '../styles/schedule-workspace.css';
.aa-filter { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
.aa-filter__item { display: inline-flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); min-width: 220px; }
.aa-select { height: 34px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; box-sizing: border-box; }
.aa-adjust-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.aa-adjust-metrics article { display: grid; gap: 6px; padding: 15px 17px; border: 1px solid var(--border-200, #dbe3ed); border-radius: 10px; background: var(--bg-white, #fff); }
.aa-adjust-metrics span { color: var(--text-500, #68788c); font-size: 12px; }
.aa-adjust-metrics strong { color: var(--text-900, #193252); font-size: 24px; }
.aa-adjust-metrics small, .aa-detail { color: var(--text-500, #68788c); font-size: 11px; line-height: 1.55; }
.aa-detail { white-space: normal; overflow-wrap: anywhere; }
@media (max-width: 760px) { .aa-adjust-metrics { grid-template-columns: 1fr; } }
</style>
