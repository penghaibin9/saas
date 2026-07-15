<template>
  <ModulePageShell
    title="课程库 · 控制台"
    subtitle="课程分类 · 课程性质 · 学分学时 · 课程负责人 · 课程停用"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn" @click="$router.push('/admin/academic-affairs/courses')">课程列表</button>
      <button class="mp-btn mp-btn--primary" @click="$router.push('/admin/academic-affairs/courses/new')">＋ 新建课程</button>
    </template>

    <div class="aacc-tabs">
      <button v-for="t in tabs" :key="t.key" :class="['aacc-tab', { 'is-active': tab === t.key }]" @click="switchTab(t.key)">{{ t.label }}</button>
    </div>

    <!-- 分类/性质：快捷筛选芯片（带计数） -->
    <div v-if="tab === 'category' || tab === 'nature'" class="aacc-chips">
      <button class="aacc-chip" :class="{ 'is-active': !dimFilter }" @click="dimFilter = ''">全部（{{ rows.length }}）</button>
      <button v-for="opt in dimOptions" :key="opt.value" class="aacc-chip" :class="{ 'is-active': dimFilter === opt.value }" @click="dimFilter = opt.value">
        {{ opt.label }}（{{ dimCount(opt.value) }}）
      </button>
    </div>
    <!-- 课程负责人：未指定筛选 -->
    <div v-if="tab === 'owner'" class="aacc-chips">
      <button class="aacc-chip" :class="{ 'is-active': !ownerFilter }" @click="ownerFilter = ''">全部（{{ rows.length }}）</button>
      <button class="aacc-chip" :class="{ 'is-active': ownerFilter === 'UNSET' }" @click="ownerFilter = 'UNSET'">未指定负责人（{{ unsetOwnerCount }}）</button>
      <button class="aacc-chip" :class="{ 'is-active': ownerFilter === 'SET' }" @click="ownerFilter = 'SET'">已指定（{{ rows.length - unsetOwnerCount }}）</button>
    </div>
    <!-- 课程停用：状态筛选 -->
    <div v-if="tab === 'disable'" class="aacc-chips">
      <button class="aacc-chip" :class="{ 'is-active': !statusFilter }" @click="statusFilter = ''">全部可停用/启用（{{ togglableRows.length }}）</button>
      <button class="aacc-chip" :class="{ 'is-active': statusFilter === 'ENABLED' }" @click="statusFilter = 'ENABLED'">已启用（{{ enabledCount }}）</button>
      <button class="aacc-chip" :class="{ 'is-active': statusFilter === 'DISABLED' }" @click="statusFilter = 'DISABLED'">已停用（{{ disabledCount }}）</button>
    </div>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <template v-else>
      <EmptyState v-if="!displayRows.length" title="暂无数据" description="课程库为空，先在「新建课程」录入课程" />
      <DataTable v-else :columns="columns" :rows="displayRows" row-key="courseId">
        <template #cell-course="{ row }">
          <div class="mp-cell-main">{{ row.courseName }}</div>
          <div class="mp-cell-sub">{{ row.courseCode }}</div>
        </template>
        <template #cell-status="{ row }"><AppStatusTag :type="reviewStatusColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag></template>
        <template #cell-category="{ row }">{{ row.categoryLabel }}</template>
        <template #cell-nature="{ row }">{{ row.natureLabel }}</template>
        <template #cell-creditHours="{ row }">
          <div class="mp-cell-main">{{ row.credit }} 学分</div>
          <div class="mp-cell-sub">总{{ row.hoursTotal ?? '—' }}（理{{ row.hoursTheory ?? 0 }}/实{{ row.hoursPractice ?? 0 }}）</div>
        </template>
        <template #cell-owner="{ row }">{{ row.ownerTeacherId ? ('教师 #' + row.ownerTeacherId) : '未指定' }}</template>
        <template #cell-ops="{ row }">
          <template v-if="tab === 'category'"><button class="mp-link" @click="openDimForm(row, 'category')">调整类别</button></template>
          <template v-if="tab === 'nature'"><button class="mp-link" @click="openDimForm(row, 'nature')">调整性质</button></template>
          <template v-if="tab === 'credit'"><button class="mp-link" @click="openCreditForm(row)">编辑学分学时</button></template>
          <template v-if="tab === 'owner'"><button class="mp-link" @click="openOwnerForm(row)">{{ row.ownerTeacherId ? '更换负责人' : '指定负责人' }}</button></template>
          <template v-if="tab === 'disable'">
            <button v-if="row.status === 'ENABLED'" class="mp-link" @click="doDisable(row)">停用</button>
            <button v-else-if="row.status === 'DISABLED'" class="mp-link" @click="doEnable(row)">启用</button>
            <span v-else class="mp-note">审核中不可操作</span>
          </template>
          <button class="mp-link" @click="$router.push(`/admin/academic-affairs/courses/${row.courseId}`)">详情</button>
        </template>
      </DataTable>
    </template>

    <!-- 调整类别/性质 -->
    <AppDrawer :visible="dimForm.visible" :title="dimForm.dim === 'category' ? '调整课程类别' : '调整课程性质'" @update:visible="dimForm.visible = $event">
      <div class="aacc-form" v-if="dimForm.row">
        <AppFormItem :label="dimForm.row.courseName"><span class="mp-note">{{ dimForm.row.courseCode }}</span></AppFormItem>
        <AppFormItem v-if="dimForm.dim === 'category'" label="课程类别" required>
          <AppSelect v-model="dimForm.value" :options="categoryOptions" />
        </AppFormItem>
        <AppFormItem v-else label="课程性质" required>
          <AppSelect v-model="dimForm.value" :options="natureOptions" />
        </AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" @click="dimForm.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitDimForm">保存</AppButton>
      </template>
    </AppDrawer>

    <!-- 编辑学分学时 -->
    <AppDrawer :visible="creditForm.visible" title="编辑学分学时" @update:visible="creditForm.visible = $event">
      <div class="aacc-form" v-if="creditForm.row">
        <AppFormItem :label="creditForm.row.courseName"><span class="mp-note">{{ creditForm.row.courseCode }}</span></AppFormItem>
        <AppFormItem label="学分" required><AppNumberInput v-model="creditForm.credit" :min="0" :step="0.5" /></AppFormItem>
        <AppFormItem label="总学时" hint="留空或与下方分项之和一致"><AppNumberInput v-model="creditForm.hoursTotal" :min="0" /></AppFormItem>
        <AppFormItem label="理论学时"><AppNumberInput v-model="creditForm.hoursTheory" :min="0" /></AppFormItem>
        <AppFormItem label="实践学时"><AppNumberInput v-model="creditForm.hoursPractice" :min="0" /></AppFormItem>
        <AppFormItem label="实验学时"><AppNumberInput v-model="creditForm.hoursExperiment" :min="0" /></AppFormItem>
        <AppFormItem label="上机学时"><AppNumberInput v-model="creditForm.hoursComputer" :min="0" /></AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" @click="creditForm.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitCreditForm">保存</AppButton>
      </template>
    </AppDrawer>

    <!-- 指定/更换课程负责人 -->
    <AppDrawer :visible="ownerForm.visible" title="指定课程负责人" @update:visible="ownerForm.visible = $event">
      <div class="aacc-form" v-if="ownerForm.row">
        <AppFormItem :label="ownerForm.row.courseName"><span class="mp-note">{{ ownerForm.row.courseCode }}</span></AppFormItem>
        <AppFormItem label="课程负责人" required hint="须为本校在职教师">
          <AppTeacherPicker v-model="ownerForm.ownerTeacherId" :remote-search="searchTeachers" clearable />
        </AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" @click="ownerForm.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitOwnerForm">保存</AppButton>
      </template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
/** 课程库控制台（/admin/academic-affairs/courses/console?tab=xxx）：
 * 课程分类 / 课程性质 / 学分学时 / 课程负责人 / 课程停用 5 个三级模块共用同一台账不同 ?tab= 视角，
 * 对齐既有「培养方案」「学院专业班级」控制台模式。深编辑/两级审核仍走 /courses/:id 详情页与 /courses/:id/edit 表单。
 * 写操作一律取当前完整课程记录 merge 目标字段后整体 PUT（后端 update_course 按整表字段覆盖，不支持局部 PATCH）。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import {
  AppSelect, AppNumberInput, AppFormItem, AppStatusTag, AppTeacherPicker, AppInlineAlert
} from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { COURSE_CATEGORY, COURSE_NATURE, REVIEW_STATUS, reviewStatusColor } from '@/modules/academicAffairs/constants/course-program'
import { toast } from '@/utils/toast'

export default {
  name: 'AaCourseConsoleView',
  components: {
    ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppDrawer,
    AppSelect, AppNumberInput, AppFormItem, AppStatusTag, AppTeacherPicker, AppInlineAlert
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      tab: 'category', loading: true, error: '', rows: [], saving: false, formError: '',
      dimFilter: '', ownerFilter: '', statusFilter: '',
      tabs: [
        { key: 'category', label: '课程分类' },
        { key: 'nature', label: '课程性质' },
        { key: 'credit', label: '学分学时' },
        { key: 'owner', label: '课程负责人' },
        { key: 'disable', label: '课程停用' }
      ],
      dimForm: { visible: false, dim: 'category', row: null, value: '' },
      creditForm: { visible: false, row: null, credit: 0, hoursTotal: null, hoursTheory: null, hoursPractice: null, hoursExperiment: null, hoursComputer: null },
      ownerForm: { visible: false, row: null, ownerTeacherId: '' }
    }
  },
  computed: {
    categoryOptions() { return Object.keys(COURSE_CATEGORY).map((k) => ({ label: COURSE_CATEGORY[k], value: k })) },
    natureOptions() { return Object.keys(COURSE_NATURE).map((k) => ({ label: COURSE_NATURE[k], value: k })) },
    dimOptions() { return this.tab === 'category' ? this.categoryOptions : this.natureOptions },
    unsetOwnerCount() { return this.rows.filter((r) => !r.ownerTeacherId).length },
    togglableRows() { return this.rows.filter((r) => r.status === 'ENABLED' || r.status === 'DISABLED') },
    enabledCount() { return this.rows.filter((r) => r.status === 'ENABLED').length },
    disabledCount() { return this.rows.filter((r) => r.status === 'DISABLED').length },
    columns() {
      const map = {
        category: [{ key: 'course', title: '课程' }, { key: 'category', title: '类别' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作', width: '160px' }],
        nature: [{ key: 'course', title: '课程' }, { key: 'nature', title: '性质' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作', width: '160px' }],
        credit: [{ key: 'course', title: '课程' }, { key: 'creditHours', title: '学分 / 学时' }, { key: 'ops', title: '操作', width: '160px' }],
        owner: [{ key: 'course', title: '课程' }, { key: 'owner', title: '课程负责人' }, { key: 'ops', title: '操作', width: '160px' }],
        disable: [{ key: 'course', title: '课程' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作', width: '160px' }]
      }
      return map[this.tab] || []
    },
    displayRows() {
      let list = this.rows
      if ((this.tab === 'category' || this.tab === 'nature') && this.dimFilter) {
        list = list.filter((r) => r[this.tab] === this.dimFilter)
      }
      if (this.tab === 'owner' && this.ownerFilter) {
        list = list.filter((r) => (this.ownerFilter === 'UNSET' ? !r.ownerTeacherId : !!r.ownerTeacherId))
      }
      if (this.tab === 'disable') {
        list = this.statusFilter ? this.rows.filter((r) => r.status === this.statusFilter) : this.togglableRows
      }
      return list
    }
  },
  created() {
    const q = this.$route && this.$route.query && this.$route.query.tab
    if (q && this.tabs.some((t) => t.key === q)) this.tab = q
    this.load()
  },
  methods: {
    reviewStatusColor,
    statusLabel(s) { return REVIEW_STATUS[s] || s || '' },
    dimCount(v) { return this.rows.filter((r) => r[this.tab] === v).length },
    switchTab(k) {
      this.tab = k
      this.dimFilter = ''; this.ownerFilter = ''; this.statusFilter = ''
      this.$router.replace({ query: { ...this.$route.query, tab: k } }).catch(() => {})
    },
    async searchTeachers(keyword) {
      const res = await academicAffairsApi.searchCourseTeachers(keyword)
      return res.code === 0 ? (res.data.items || []) : []
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getCourses({ page: 1, pageSize: 500 })
      if (res.code === 0) this.rows = res.data.list
      else this.error = res.message
      this.loading = false
    },
    // ── 通用：整表 merge 后 PUT ──
    async putCourse(row, patch) {
      const body = {
        courseCode: row.courseCode, courseName: row.courseName, courseNameEn: row.courseNameEn,
        category: row.category, nature: row.nature, credit: row.credit, hoursTotal: row.hoursTotal,
        hoursTheory: row.hoursTheory, hoursPractice: row.hoursPractice, hoursExperiment: row.hoursExperiment,
        hoursComputer: row.hoursComputer, examMode: row.examMode, ownerCollegeId: row.ownerCollegeId || undefined,
        ownerTeacherId: row.ownerTeacherId || undefined, isCore: row.isCore, description: row.description,
        isAllMajor: row.isAllMajor, applicableMajors: row.applicableMajors, prerequisiteCodes: row.prerequisiteCodes,
        ...patch
      }
      return academicAffairsApi.updateCourse(row.courseId, body)
    },
    // ── 课程分类/性质 ──
    openDimForm(row, dim) {
      this.formError = ''
      this.dimForm = { visible: true, dim, row, value: row[dim] }
    },
    async submitDimForm() {
      this.saving = true
      const res = await this.putCourse(this.dimForm.row, { [this.dimForm.dim]: this.dimForm.value })
      this.saving = false
      if (res.code === 0) { toast.success('已保存'); this.dimForm.visible = false; this.load() } else this.formError = res.message
    },
    // ── 学分学时 ──
    openCreditForm(row) {
      this.formError = ''
      this.creditForm = {
        visible: true, row, credit: row.credit, hoursTotal: row.hoursTotal, hoursTheory: row.hoursTheory,
        hoursPractice: row.hoursPractice, hoursExperiment: row.hoursExperiment, hoursComputer: row.hoursComputer
      }
    },
    async submitCreditForm() {
      this.saving = true
      const f = this.creditForm
      const res = await this.putCourse(f.row, {
        credit: f.credit, hoursTotal: f.hoursTotal, hoursTheory: f.hoursTheory,
        hoursPractice: f.hoursPractice, hoursExperiment: f.hoursExperiment, hoursComputer: f.hoursComputer
      })
      this.saving = false
      if (res.code === 0) { toast.success('已保存'); this.creditForm.visible = false; this.load() } else this.formError = res.message
    },
    // ── 课程负责人 ──
    openOwnerForm(row) {
      this.formError = ''
      this.ownerForm = { visible: true, row, ownerTeacherId: row.ownerTeacherId || '' }
    },
    async submitOwnerForm() {
      if (!this.ownerForm.ownerTeacherId) { this.formError = '请选择课程负责人'; return }
      this.saving = true
      const res = await this.putCourse(this.ownerForm.row, { ownerTeacherId: this.ownerForm.ownerTeacherId })
      this.saving = false
      if (res.code === 0) { toast.success('已保存'); this.ownerForm.visible = false; this.load() } else this.formError = res.message
    },
    // ── 课程停用 ──
    async doDisable(row) {
      const res = await academicAffairsApi.disableCourse(row.courseId)
      if (res.code === 0) { toast.success('已停用'); this.load() }
      else toast.error(res.message || '停用失败（可能仍被培养方案引用，可到课程详情页「查看引用情况」核实）')
    },
    async doEnable(row) {
      const res = await academicAffairsApi.enableCourse(row.courseId)
      if (res.code === 0) { toast.success('已启用'); this.load() }
      else toast.error(res.message || '启用失败')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aacc-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-color, #e5e7eb); margin-bottom: 16px; flex-wrap: wrap; }
.aacc-tab { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; }
.aacc-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 600; }
.aacc-chips { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
.aacc-chip { padding: 4px 12px; border-radius: 999px; border: 1px solid var(--border-300, #d0d3d9); background: var(--bg-white, #fff); color: var(--text-700, #4e5969); font-size: 12px; cursor: pointer; }
.aacc-chip.is-active { background: var(--primary-50, #eff6ff); border-color: var(--primary-500, #3b82f6); color: var(--primary-600, #2563eb); font-weight: 600; }
.aacc-form { display: flex; flex-direction: column; gap: 12px; }
</style>
