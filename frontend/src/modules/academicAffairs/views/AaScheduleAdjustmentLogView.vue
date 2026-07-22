<template>
  <ModulePageShell
    title="课表调整记录"
    subtitle="课表条目/批次变更留痕只读查询（手工排课、导入、改排、教师异议、发布、作废重发等）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/schedule')">课表批次</AppButton>
    </template>

    <div class="mp-stack">
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

      <AppSectionCard title="调整记录">
        <ErrorState v-if="error" :description="error" @retry="reload" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="暂无匹配记录" description="课表批次发生手工排课/导入/改排/发布/作废重发等操作后会在此留痕" />
        <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
          <template #cell-bizType="{ row }">
            <AppStatusTag :type="row.bizType === 'AA_SCHEDULE' ? 'info' : 'default'" dot>
              {{ row.bizType === 'AA_SCHEDULE' ? '条目' : '批次' }}
            </AppStatusTag>
          </template>
          <template #cell-action="{ row }">{{ actionLabel(row.action) }}</template>
        </DataTable>
        <p class="mp-note">
          本页只读，读取排课服务操作留痕（t_affairs_audit_trail）；正式「调课/停课/补课」审批流程见
          「调停课」二级模块自有台账，不在本页重复展示。
        </p>
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

const ACTION_LABELS = {
  CREATE: '新建批次', ADD_ITEM: '手工排课', IMPORT: '导入课表', ADJUST_ITEM: '改排条目',
  TEACHER_OBJECT: '教师提出异议', PRE_PUBLISH: '预发布', PUBLISH: '发布', VOID_REISSUE: '作废重发',
  ARCHIVE: '归档'
}
const ITEM_ACTIONS = ['ADD_ITEM', 'ADJUST_ITEM', 'TEACHER_OBJECT']
const BATCH_ACTIONS = ['CREATE', 'IMPORT', 'PRE_PUBLISH', 'PUBLISH', 'VOID_REISSUE', 'ARCHIVE']

export default {
  name: 'AaScheduleAdjustmentLogView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppStatusTag, AppSelect },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      bizType: '', action: '', rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',
      columns: [
        { key: 'occurredAt', title: '时间' },
        { key: 'bizType', title: '类型' },
        { key: 'action', title: '动作' },
        { key: 'bizId', title: '对象ID' },
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
        { value: '', label: '全部（条目 + 批次）' },
        { value: 'AA_SCHEDULE', label: '条目变更（手工排课/导入/改排/教师异议）' },
        { value: 'AA_SCHEDULE_BATCH', label: '批次变更（新建/整批导入/预发布/发布/作废重发/归档）' }
      ]
    },
    actionOptions() {
      if (this.bizType === 'AA_SCHEDULE') return ITEM_ACTIONS
      if (this.bizType === 'AA_SCHEDULE_BATCH') return BATCH_ACTIONS
      return [...ITEM_ACTIONS, ...BATCH_ACTIONS]
    },
    actionSelectOptions() {
      return [{ value: '', label: '全部动作' }, ...this.actionOptions.map((value) => ({ value, label: this.actionLabel(value) }))]
    }
  },
  created() { this.load() },
  methods: {
    actionLabel(a) { return ACTION_LABELS[a] || a || '—' },
    reload() { this.page = 1; this.load() },
    onPageChange(p) { this.page = p; this.load() },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getScheduleAdjustments({
        bizType: this.bizType || undefined, action: this.action || undefined,
        page: this.page, pageSize: this.pageSize
      })
      this.loading = false
      if (res.code === 0) {
        this.rows = res.data.list
        this.total = res.data.total
      } else {
        this.error = res.message
        this.rows = []
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
.aa-filter__item { display: inline-flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); min-width: 220px; }
.aa-select { height: 34px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; box-sizing: border-box; }
</style>
