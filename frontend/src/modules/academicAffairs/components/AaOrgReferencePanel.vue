<template>
  <section class="mp-card aa-reference-panel">
    <div class="mp-card__body">
      <div class="aa-reference-heading">
        <div><h2>组织变更前核对</h2><p class="mp-note">查看学生、教学任务和培养方案引用，先处理影响，再办理停用或结班。</p></div>
        <AppButton variant="primary" :loading="loading" @click="runCheck">重新核对</AppButton>
      </div>
      <div class="aa-reference-filters">
        <AppFormItem label="核对对象"><AppSelect v-model="criteria.targetType" :options="typeOptions" placeholder="全部组织" /></AppFormItem>
        <AppFormItem label="所属学院"><AppCollegePicker v-model="criteria.collegeId" :options="collegeOptions" placeholder="全部可见学院" /></AppFormItem>
        <AppFormItem label="组织名称"><AppTextInput v-model="criteria.keyword" :maxlength="100" placeholder="输入学院、专业或班级名称" @keyup.enter="runCheck" /></AppFormItem>
      </div>
      <p v-if="appliedCriteria" class="mp-note">当前结果：{{ typeLabel(appliedCriteria.targetType) }} · {{ collegeLabel(appliedCriteria.collegeId) }}<span v-if="appliedCriteria.keyword"> · {{ appliedCriteria.keyword }}</span>。筛选修改后点击「重新核对」。</p>
      <ErrorState v-if="error" :description="error" @retry="runCheck" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="当前范围内没有符合条件的组织" description="可以调整对象类型或所属学院后重新核对。" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="key" :pagination="pagination" @page-change="changePage">
        <template #cell-targetName="{ row }"><strong>{{ row.targetName }}</strong><div class="mp-note">{{ typeLabel(row.targetType) }}</div></template>
        <template #cell-students="{ row }">{{ refCount(row, 'STUDENT') }}</template>
        <template #cell-tasks="{ row }">{{ refCount(row, 'TEACHING_TASK') }}</template>
        <template #cell-programs="{ row }">{{ row.targetType === 'CLASS' ? '—' : refCount(row, 'PROGRAM') }}</template>
        <template #cell-blocked="{ row }"><StatusTag :type="row.blocked ? 'warning' : 'success'" :label="row.blocked ? '需先处理引用' : '未发现引用阻断'" /></template>
        <template #cell-actions="{ row }"><AppButton variant="ghost" @click="openDetail(row)">查看核对</AppButton></template>
      </DataTable>
      <p class="mp-note aa-reference-footnote">核对反映查询时的情况，不会更改组织或学生资料，也不代表停用、结班或删除已获批准；历史引用仍需保留。</p>
    </div>
    <AppDrawer :visible="detail.visible" title="组织引用核对" mode="modal" size="large" @update:visible="closeDetail">
      <ErrorState v-if="detail.error" :description="detail.error" @retry="retryDetail" />
      <LoadingState v-else-if="detail.loading" />
      <template v-else-if="detail.report">
        <h2>{{ detail.report.targetName }}</h2>
        <p class="mp-note">{{ typeLabel(detail.report.targetType) }} · 核对时间 {{ displayTime(detail.report.checkedAt) }}</p>
        <AppInlineAlert :type="detail.report.blocked ? 'warning' : 'success'" :description="detail.report.blocked ? '存在需要先处理的关联，请逐项查看下方建议。' : '本次未发现当前引用阻断；仍需按相应业务规则办理组织变更。'" />
        <div class="aa-reference-items">
          <div v-for="ref in detail.report.refs" :key="ref.refType" class="aa-reference-item">
            <div class="aa-reference-item-title"><strong>{{ ref.label }}</strong><StatusTag :type="ref.blocked ? 'warning' : 'default'" :label="String(ref.refCount)" /></div>
            <p class="mp-note">{{ ref.guidance }}</p>
          </div>
        </div>
        <AppInlineAlert v-for="warning in detail.report.warnings" :key="warning" type="info" :description="warning" />
      </template>
      <template #footer>
        <AppButton @click="closeDetail">关闭</AppButton>
        <AppButton v-if="detail.report" variant="primary" @click="viewOrganization">查看组织资料</AppButton>
      </template>
    </AppDrawer>
  </section>
</template>

<script>
import { DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppInlineAlert, AppSelect, AppFormItem, AppTextInput, AppCollegePicker } from '@/components/common'
import { academicAffairsOrgApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { formatDateTime } from '@/utils/dateUtils'

export default {
  name: 'AaOrgReferencePanel',
  components: { DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppButton, AppDrawer, AppInlineAlert, AppSelect, AppFormItem, AppTextInput, AppCollegePicker },
  props: { collegeOptions: { type: Array, default: () => [] } },
  emits: ['view-organization'],
  data() {
    return {
      criteria: { targetType: '', collegeId: '', keyword: '' }, appliedCriteria: null,
      rows: [], loading: false, error: '', sequence: 0, detailSequence: 0,
      pagination: { page: 1, pageSize: 20, total: 0 },
      detail: { visible: false, loading: false, error: '', target: null, report: null },
      typeOptions: [{ value: '', label: '全部组织' }, { value: 'COLLEGE', label: '学院' }, { value: 'MAJOR', label: '专业' }, { value: 'CLASS', label: '行政班' }],
      columns: [{ key: 'targetName', title: '核对对象' }, { key: 'students', title: '在籍学生' },
        { key: 'tasks', title: '未归档任务' }, { key: 'programs', title: '生效方案' },
        { key: 'blocked', title: '核对结果' }, { key: 'actions', title: '操作' }],
    }
  },
  mounted() { this.runCheck() },
  beforeUnmount() { this.sequence++; this.detailSequence++ },
  methods: {
    typeLabel(kind) { return { COLLEGE: '学院', MAJOR: '专业', CLASS: '行政班' }[kind] || '全部组织' },
    collegeLabel(id) { return this.collegeOptions.find(row => row.value === id)?.label || '全部可见学院' },
    refCount(row, kind) { return row.refs.find(ref => ref.refType === kind)?.refCount ?? 0 },
    displayTime(value) { return formatDateTime(value, '—') },
    runCheck() { return this.load(1, { ...this.criteria, keyword: this.criteria.keyword.trim() }) },
    changePage(page) { return this.load(page, this.appliedCriteria || this.criteria) },
    async load(page, criteria) {
      const sequence = ++this.sequence
      const selected = { ...criteria }
      this.loading = true; this.error = ''; this.rows = []
      try {
        const res = await api.listOrgReferenceChecks({ ...selected, page, pageSize: this.pagination.pageSize })
        if (sequence !== this.sequence) return
        if (res.code !== 0) { this.error = res.message || '组织引用核对失败，请重试'; return }
        this.rows = res.data.list.map(row => ({ ...row, key: `${row.targetType}:${row.targetId}` }))
        this.pagination.page = page; this.pagination.total = res.data.total
        this.appliedCriteria = selected
      } catch (error) {
        if (sequence === this.sequence) this.error = error.message || '核对请求未完成，请重试'
      } finally {
        if (sequence === this.sequence) this.loading = false
      }
    },
    async openDetail(row) {
      const sequence = ++this.detailSequence
      const target = { targetType: row.targetType, targetId: row.targetId }
      this.detail = { visible: true, loading: true, error: '', target, report: null }
      try {
        const res = await api.getOrgReferenceCheck(target.targetType, target.targetId)
        if (sequence !== this.detailSequence || !this.detail.visible) return
        if (res.code === 0) this.detail.report = res.data
        else this.detail.error = res.message || '读取核对详情失败，请重试'
      } catch (error) {
        if (sequence === this.detailSequence) this.detail.error = error.message || '读取核对详情失败，请重试'
      } finally {
        if (sequence === this.detailSequence) this.detail.loading = false
      }
    },
    retryDetail() { if (this.detail.target) return this.openDetail(this.detail.target) },
    closeDetail() { this.detailSequence++; this.detail.visible = false; this.detail.loading = false },
    viewOrganization() {
      if (!this.detail.report) return
      const report = this.detail.report
      this.closeDetail(); this.$emit('view-organization', report)
    },
  },
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-reference-heading { display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:16px }
.aa-reference-heading h2 { margin:0;font-size:18px }
.aa-reference-filters { display:grid;grid-template-columns:1fr 1fr 1.4fr;gap:16px }
.aa-reference-footnote { margin:16px 0 0 }
.aa-reference-items { display:grid;gap:12px;margin:20px 0 }
.aa-reference-item { padding:14px 16px;border:1px solid var(--border-color, #e2e8f0);border-radius:10px }
.aa-reference-item-title { display:flex;justify-content:space-between;align-items:center;gap:12px }
.aa-reference-item p { margin:8px 0 0 }
@media (max-width:800px) { .aa-reference-filters { grid-template-columns:1fr }.aa-reference-heading { flex-wrap:wrap } }
</style>
