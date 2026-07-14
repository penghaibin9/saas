<template>
  <ModulePageShell
    title="学院专业班级"
    :subtitle="'组织架构维护（学院 / 专业 / 行政班）· 教学秘书绑定 · 组织变更审计'"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
  >
    <template #actions>
      <button v-if="canManage && ['college','major','class'].includes(tab)"
              class="mp-btn mp-btn--primary" @click="openCreate">＋ 新建{{ tabLabel }}</button>
    </template>

    <div class="mp-stack">
      <!-- 页签 -->
      <nav class="aa-tabs">
        <button v-for="t in tabs" :key="t.key" class="aa-tab" :class="{ 'is-active': tab === t.key }"
                @click="switchTab(t.key)">{{ t.label }}</button>
      </nav>

      <!-- 统计概览 -->
      <section v-if="tab === 'stats'" class="mp-card">
        <div class="mp-card__body">
          <ErrorState v-if="statsError" :description="statsError" @retry="loadStats" />
          <LoadingState v-else-if="statsLoading" />
          <div v-else class="aa-stat-grid">
            <div v-for="s in statCards" :key="s.key" class="aa-stat">
              <div class="aa-stat__num">{{ stats[s.key] ?? 0 }}</div>
              <div class="aa-stat__label">{{ s.label }}</div>
            </div>
          </div>
        </div>
      </section>

      <!-- 组织树 -->
      <section v-else-if="tab === 'tree'" class="mp-card">
        <div class="mp-card__body">
          <ErrorState v-if="treeError" :description="treeError" @retry="loadTree" />
          <LoadingState v-else-if="treeLoading" />
          <EmptyState v-else-if="!tree.colleges || !tree.colleges.length" title="暂无组织数据" description="先在「学院」页签新建学院、专业与班级" />
          <ul v-else class="aa-tree">
            <li v-for="c in tree.colleges" :key="c.id">
              <strong>{{ c.collegeName }}</strong><span v-if="c.shortName" class="mp-note"> · {{ c.shortName }}</span>
              <ul>
                <li v-for="m in c.majors" :key="m.id">
                  {{ m.majorName }}
                  <StatusTag :type="m.enrollStatus === 'ENROLLING' ? 'success' : 'default'"
                             :label="m.enrollStatus === 'ENROLLING' ? '招生中' : '停招'" dot />
                  <ul>
                    <li v-for="k in m.classes" :key="k.id">
                      {{ k.className }} <span class="mp-note">（{{ classStatusLabel(k.classStatus) }}）</span>
                    </li>
                  </ul>
                </li>
              </ul>
            </li>
          </ul>
        </div>
      </section>

      <!-- 列表类页签（学院/专业/行政班/年级/教学班/审计/班级学生）-->
      <template v-else>
        <div v-if="tab === 'major' || tab === 'class'" class="aa-filter">
          <select v-if="tab === 'major'" v-model="filters.collegeId" @change="reload">
            <option value="">全部学院</option>
            <option v-for="c in collegeOptions" :key="c.value" :value="c.value">{{ c.label }}</option>
          </select>
          <select v-if="tab === 'class'" v-model="filters.majorId" @change="reload">
            <option value="">全部专业</option>
            <option v-for="m in majorOptions" :key="m.value" :value="m.value">{{ m.label }}</option>
          </select>
          <input v-model="filters.keyword" class="aa-input" placeholder="关键词" @keyup.enter="reload" />
          <button class="mp-btn" @click="reload">查询</button>
        </div>

        <ErrorState v-if="error" :description="error" @retry="reload" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" :title="'暂无' + tabLabel + '数据'" description="可调整筛选条件或新建记录" />
        <DataTable
          v-else
          :columns="columns"
          :rows="rows"
          row-key="id"
          :pagination="pagination"
          @page-change="onPageChange"
        >
          <template #cell-enrollStatus="{ row }">
            <StatusTag :type="row.enrollStatus === 'ENROLLING' ? 'success' : 'default'"
                       :label="row.enrollStatus === 'ENROLLING' ? '招生中' : '停招'" dot />
          </template>
          <template #cell-classStatus="{ row }">
            <StatusTag :type="row.classStatus === 'NORMAL' ? 'success' : 'default'"
                       :label="classStatusLabel(row.classStatus)" dot />
          </template>
          <template #cell-actions="{ row }">
            <template v-if="tab === 'college'">
              <button class="mp-link" :disabled="!canManage" @click="openEdit(row)">编辑</button>
              <button class="mp-link" :disabled="!canManage" @click="openSecretary(row)">教学秘书</button>
              <button class="mp-link aa-danger" :disabled="!canManage" @click="openDelete(row)">删除</button>
            </template>
            <template v-else-if="tab === 'major'">
              <button class="mp-link" :disabled="!canManage" @click="openEdit(row)">编辑</button>
              <button class="mp-link aa-danger" :disabled="!canManage" @click="openDelete(row)">删除</button>
            </template>
            <template v-else-if="tab === 'class'">
              <button class="mp-link" :disabled="!canManage" @click="openEdit(row)">编辑</button>
              <button class="mp-link" @click="openStudents(row)">学生</button>
              <button class="mp-link aa-danger" :disabled="!canManage" @click="openDelete(row)">删除</button>
            </template>
          </template>
        </DataTable>
      </template>

      <p class="mp-note">
        组织三表复用冻结册 t_college / t_major / t_class；删除为软删且要求先清空下级/在册学生；
        全部写操作经后端 build_affairs_context 数据范围收敛并写组织变更审计（AA_ORG_*）。
      </p>
    </div>

    <!-- 新建 / 编辑 表单 -->
    <div v-if="form.visible" class="aa-modal" @click.self="form.visible = false">
      <div class="aa-modal__panel">
        <h3 class="aa-modal__title">{{ form.mode === 'create' ? '新建' : '编辑' }}{{ tabLabel }}</h3>
        <div class="aa-form">
          <label v-for="f in formFields" :key="f.key" class="aa-form__row">
            <span class="aa-form__label">{{ f.label }}<i v-if="f.required" class="aa-req">*</i></span>
            <select v-if="f.type === 'select'" v-model="form.model[f.key]">
              <option v-for="o in f.options" :key="o.value" :value="o.value">{{ o.label }}</option>
            </select>
            <input v-else v-model="form.model[f.key]" :type="f.type === 'number' ? 'number' : 'text'"
                   :placeholder="f.placeholder || ''" />
          </label>
        </div>
        <div class="aa-modal__foot">
          <button class="mp-btn" @click="form.visible = false">取消</button>
          <button class="mp-btn mp-btn--primary" :disabled="form.submitting" @click="submitForm">保存</button>
        </div>
      </div>
    </div>

    <!-- 教学秘书绑定 -->
    <div v-if="secretary.visible" class="aa-modal" @click.self="secretary.visible = false">
      <div class="aa-modal__panel">
        <h3 class="aa-modal__title">教学秘书绑定 · {{ secretary.row && secretary.row.collegeName }}</h3>
        <div class="aa-form">
          <label class="aa-form__row">
            <span class="aa-form__label">教学秘书 user_id</span>
            <input v-model="secretary.secretaryId" placeholder="留空为解绑" />
          </label>
        </div>
        <div class="aa-modal__foot">
          <button class="mp-btn" @click="secretary.visible = false">取消</button>
          <button class="mp-btn mp-btn--primary" :disabled="secretary.submitting" @click="submitSecretary">保存</button>
        </div>
      </div>
    </div>

    <!-- 班级学生抽屉 -->
    <div v-if="students.visible" class="aa-modal" @click.self="students.visible = false">
      <div class="aa-modal__panel aa-modal__panel--wide">
        <h3 class="aa-modal__title">班级学生 · {{ students.className }}</h3>
        <LoadingState v-if="students.loading" />
        <EmptyState v-else-if="!students.rows.length" title="该班暂无在册学生" />
        <table v-else class="mp-audit">
          <thead><tr><th>学号</th><th>姓名</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="s in students.rows" :key="s.id">
              <td>{{ s.studentNo }}</td><td>{{ s.realName }}</td>
              <td><button class="mp-link" :disabled="!canManage" @click="openAdjust(s)">调整班级</button></td>
            </tr>
          </tbody>
        </table>
        <div class="aa-modal__foot"><button class="mp-btn" @click="students.visible = false">关闭</button></div>
      </div>
    </div>

    <!-- 班级调整 -->
    <div v-if="adjust.visible" class="aa-modal" @click.self="adjust.visible = false">
      <div class="aa-modal__panel">
        <h3 class="aa-modal__title">班级调整 · {{ adjust.student && adjust.student.realName }}</h3>
        <div class="aa-form">
          <label class="aa-form__row">
            <span class="aa-form__label">目标班级<i class="aa-req">*</i></span>
            <select v-model="adjust.targetClassId">
              <option value="">请选择目标班级</option>
              <option v-for="c in classOptions" :key="c.value" :value="c.value">{{ c.label }}</option>
            </select>
          </label>
        </div>
        <div class="aa-modal__foot">
          <button class="mp-btn" @click="adjust.visible = false">取消</button>
          <button class="mp-btn mp-btn--primary" :disabled="adjust.submitting || !adjust.targetClassId"
                  @click="submitAdjust">确认调整</button>
        </div>
      </div>
    </div>

    <AppConfirmDialog
      v-model:visible="del.visible"
      type="danger"
      :title="'删除' + tabLabel"
      :message="del.message"
      confirm-text="确认删除"
      :submitting="del.submitting"
      @confirm="submitDelete"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 学院专业班级管理控制台（/admin/academic-affairs/orgs）。
 * 生产级：数据全部来自真实后端 /academic-affairs/orgs/*，无 mock；页面三态 + 二次确认 + 越权由后端裁决。
 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { academicAffairsOrgApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { currentUserFromToken } from '@/services/http/client'
import { toast } from '@/utils/toast'

const CLASS_STATUS = { NORMAL: '在读', GRADUATED: '已毕业', DISBANDED: '已解散' }
const MANAGE_ROLES = ['SCHOOL_ADMIN', 'PLATFORM_SUPER_ADMIN', 'ACADEMIC_TEACHER', 'COLLEGE_ADMIN']

export default {
  name: 'AaOrgConsole',
  components: { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppConfirmDialog },
  data() {
    return {
      tab: 'college',
      tabs: [
        { key: 'college', label: '学院' }, { key: 'major', label: '专业' }, { key: 'class', label: '行政班' },
        { key: 'grade', label: '年级' }, { key: 'teaching', label: '教学班' },
        { key: 'tree', label: '组织树' }, { key: 'stats', label: '统计' }, { key: 'audit', label: '变更审计' }
      ],
      loading: false, error: '', rows: [],
      pagination: { page: 1, pageSize: 10, total: 0 },
      filters: { collegeId: '', majorId: '', keyword: '' },
      collegeOptions: [], majorOptions: [], classOptions: [],
      stats: {}, statsLoading: false, statsError: '',
      tree: { colleges: [] }, treeLoading: false, treeError: '',
      form: { visible: false, mode: 'create', submitting: false, model: {} },
      secretary: { visible: false, submitting: false, row: null, secretaryId: '' },
      students: { visible: false, loading: false, rows: [], className: '', classId: null },
      adjust: { visible: false, submitting: false, student: null, targetClassId: '' },
      del: { visible: false, submitting: false, row: null, message: '' }
    }
  },
  computed: {
    user() { return currentUserFromToken() || {} },
    roleName() { return this.user.roleName || this.user.currentRoleCode || '' },
    dataScopeName() { return this.user.scopeLabel || this.user.dataScope || '' },
    canManage() { return MANAGE_ROLES.includes((this.user.currentRoleCode || '').toUpperCase()) },
    tabLabel() { return (this.tabs.find((t) => t.key === this.tab) || {}).label || '' },
    statCards() {
      return [
        { key: 'collegeCount', label: '学院数' }, { key: 'majorCount', label: '专业数' },
        { key: 'classCount', label: '行政班数' }, { key: 'studentCount', label: '在校生数' },
        { key: 'enrollingMajorCount', label: '招生专业数' }, { key: 'graduatedClassCount', label: '已毕业班数' }
      ]
    },
    columns() {
      const map = {
        college: [{ key: 'collegeName', title: '学院名称' }, { key: 'shortName', title: '简称' },
          { key: 'code', title: '编码' }, { key: 'sortOrder', title: '排序' },
          { key: 'secretaryId', title: '教学秘书' }, { key: 'actions', title: '操作' }],
        major: [{ key: 'majorName', title: '专业名称' }, { key: 'collegeName', title: '所属学院' },
          { key: 'educationYears', title: '学制' }, { key: 'trainingLevel', title: '培养层次' },
          { key: 'direction', title: '专业方向' }, { key: 'enrollStatus', title: '招生状态' },
          { key: 'actions', title: '操作' }],
        class: [{ key: 'className', title: '班级名称' }, { key: 'classCode', title: '班级编号' },
          { key: 'majorName', title: '专业' }, { key: 'grade', title: '年级' },
          { key: 'capacity', title: '编制' }, { key: 'graduateYear', title: '应毕业' },
          { key: 'classStatus', title: '状态' }, { key: 'actions', title: '操作' }],
        grade: [{ key: 'grade', title: '年级' }, { key: 'classCount', title: '班级数' },
          { key: 'studentCount', title: '学生数' }],
        teaching: [{ key: 'teachingClassCode', title: '教学班代码' }, { key: 'teachingClassName', title: '教学班名' },
          { key: 'courseCount', title: '课程数' }, { key: 'expectedStudents', title: '预计人数' }],
        audit: [{ key: 'occurredAt', title: '时间' }, { key: 'bizType', title: '对象' },
          { key: 'action', title: '动作' }, { key: 'operator', title: '操作人' }, { key: 'detail', title: '说明' }]
      }
      return map[this.tab] || []
    },
    formFields() {
      if (this.tab === 'college') {
        return [
          { key: 'collegeName', label: '学院名称', required: true },
          { key: 'shortName', label: '简称' }, { key: 'code', label: '编码' },
          { key: 'sortOrder', label: '排序', type: 'number' }
        ]
      }
      if (this.tab === 'major') {
        return [
          { key: 'collegeId', label: '所属学院', type: 'select', required: true, options: this.collegeOptions },
          { key: 'majorName', label: '专业名称', required: true },
          { key: 'educationYears', label: '学制（年）', type: 'number' },
          { key: 'trainingLevel', label: '培养层次', type: 'select', options: [
            { value: '', label: '未设置' }, { value: 'SECONDARY', label: '中职' },
            { value: 'HIGHER', label: '高职' }, { value: 'FIVE_YEAR', label: '五年制' }] },
          { key: 'direction', label: '专业方向' },
          { key: 'enrollStatus', label: '招生状态', type: 'select', options: [
            { value: 'ENROLLING', label: '招生中' }, { value: 'STOPPED', label: '停招' }] }
        ]
      }
      // class
      return [
        { key: 'majorId', label: '所属专业', type: 'select', required: true, options: this.majorOptions },
        { key: 'className', label: '班级名称', required: true },
        { key: 'classCode', label: '班级编号' }, { key: 'grade', label: '年级', placeholder: '如 2026' },
        { key: 'capacity', label: '编制人数', type: 'number' },
        { key: 'graduateYear', label: '应毕业年份', placeholder: '如 2029' },
        { key: 'classStatus', label: '班级状态', type: 'select', options: [
          { value: 'NORMAL', label: '在读' }, { value: 'GRADUATED', label: '已毕业' },
          { value: 'DISBANDED', label: '已解散' }] }
      ]
    }
  },
  created() {
    const q = this.$route && this.$route.query && this.$route.query.tab
    if (q && this.tabs.some((t) => t.key === q)) this.tab = q
    this.loadOptions()
    if (this.tab === 'stats') this.loadStats()
    else if (this.tab === 'tree') this.loadTree()
    else this.reload()
  },
  watch: {
    '$route.query.tab'(v) {
      if (v && this.tabs.some((t) => t.key === v) && v !== this.tab) this.switchTab(v)
    }
  },
  methods: {
    classStatusLabel(v) { return CLASS_STATUS[v] || v || '' },
    switchTab(key) {
      this.tab = key
      this.pagination.page = 1
      if (key === 'stats') this.loadStats()
      else if (key === 'tree') this.loadTree()
      else this.reload()
    },
    async loadOptions() {
      const c = await api.listColleges({ pageSize: 200 })
      if (c.code === 0) this.collegeOptions = c.data.list.map((x) => ({ value: x.id, label: x.collegeName }))
      const m = await api.listMajors({ pageSize: 500 })
      if (m.code === 0) this.majorOptions = m.data.list.map((x) => ({ value: x.id, label: x.majorName }))
      const k = await api.listClasses({ pageSize: 500 })
      if (k.code === 0) this.classOptions = k.data.list.map((x) => ({ value: x.id, label: x.className }))
    },
    onPageChange(p) { this.pagination.page = p; this.reload() },
    async reload() {
      if (['tree', 'stats'].includes(this.tab)) return
      this.loading = true; this.error = ''
      const params = { page: this.pagination.page, pageSize: this.pagination.pageSize }
      let res
      if (this.tab === 'college') res = await api.listColleges({ ...params, keyword: this.filters.keyword })
      else if (this.tab === 'major') res = await api.listMajors({ ...params, collegeId: this.filters.collegeId, keyword: this.filters.keyword })
      else if (this.tab === 'class') res = await api.listClasses({ ...params, majorId: this.filters.majorId, keyword: this.filters.keyword })
      else if (this.tab === 'teaching') res = await api.listTeachingClasses(params)
      else if (this.tab === 'audit') res = await api.listAudit(params)
      else if (this.tab === 'grade') { const g = await api.listGrades(); if (g.code === 0) { this.rows = g.data.items || []; this.pagination.total = this.rows.length } else this.error = g.message; this.loading = false; return }
      if (res) {
        if (res.code === 0) { this.rows = res.data.list; this.pagination.total = res.data.total } else this.error = res.message
      }
      this.loading = false
    },
    async loadStats() {
      this.statsLoading = true; this.statsError = ''
      const res = await api.orgStats()
      if (res.code === 0) this.stats = res.data; else this.statsError = res.message
      this.statsLoading = false
    },
    async loadTree() {
      this.treeLoading = true; this.treeError = ''
      const res = await api.orgTree()
      if (res.code === 0) this.tree = res.data; else this.treeError = res.message
      this.treeLoading = false
    },
    defaultModel() {
      if (this.tab === 'college') return { sortOrder: 0 }
      if (this.tab === 'major') return { educationYears: 3, enrollStatus: 'ENROLLING', trainingLevel: '' }
      return { classStatus: 'NORMAL' }
    },
    openCreate() {
      if (!this.canManage) return toast.error('无操作权限')
      this.form = { visible: true, mode: 'create', submitting: false, model: this.defaultModel() }
    },
    openEdit(row) {
      this.form = { visible: true, mode: 'edit', submitting: false, model: { ...row } }
    },
    async submitForm() {
      const m = this.form.model
      this.form.submitting = true
      let res
      if (this.tab === 'college') {
        res = this.form.mode === 'create' ? await api.createCollege(m) : await api.updateCollege(m.id, m)
      } else if (this.tab === 'major') {
        res = this.form.mode === 'create' ? await api.createMajor(m) : await api.updateMajor(m.id, m)
      } else {
        res = this.form.mode === 'create' ? await api.createClass(m) : await api.updateClass(m.id, m)
      }
      this.form.submitting = false
      if (res.code === 0) { toast.success('已保存'); this.form.visible = false; this.loadOptions(); this.reload() }
      else toast.error(res.message)
    },
    openSecretary(row) {
      this.secretary = { visible: true, submitting: false, row, secretaryId: row.secretaryId || '' }
    },
    async submitSecretary() {
      this.secretary.submitting = true
      const res = await api.bindSecretary(this.secretary.row.id, this.secretary.secretaryId || null)
      this.secretary.submitting = false
      if (res.code === 0) { toast.success('已保存'); this.secretary.visible = false; this.reload() }
      else toast.error(res.message)
    },
    async openStudents(row) {
      this.students = { visible: true, loading: true, rows: [], className: row.className, classId: row.id }
      const res = await api.listClassStudents(row.id, { pageSize: 200 })
      this.students.loading = false
      if (res.code === 0) this.students.rows = res.data.list; else toast.error(res.message)
    },
    openAdjust(student) {
      this.adjust = { visible: true, submitting: false, student, targetClassId: '' }
    },
    async submitAdjust() {
      this.adjust.submitting = true
      const res = await api.adjustClass({ studentId: this.adjust.student.id, targetClassId: this.adjust.targetClassId })
      this.adjust.submitting = false
      if (res.code === 0) {
        toast.success('已调整')
        this.adjust.visible = false
        if (this.students.visible && this.students.classId) this.openStudents({ id: this.students.classId, className: this.students.className })
      } else toast.error(res.message)
    },
    openDelete(row) {
      const name = row.collegeName || row.majorName || row.className || ''
      this.del = { visible: true, submitting: false, row, message: `确认删除「${name}」？删除为逻辑软删，要求先清空下级/在册学生。` }
    },
    async submitDelete() {
      this.del.submitting = true
      const id = this.del.row.id
      let res
      if (this.tab === 'college') res = await api.deleteCollege(id)
      else if (this.tab === 'major') res = await api.deleteMajor(id)
      else res = await api.deleteClass(id)
      this.del.submitting = false
      if (res.code === 0) { toast.success('已删除'); this.del.visible = false; this.loadOptions(); this.reload() }
      else toast.error(res.message)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-tabs { display: flex; gap: var(--space-1); flex-wrap: wrap; border-bottom: 1px solid var(--border-200); margin-bottom: var(--space-3); }
.aa-tab { padding: var(--space-2) var(--space-3); border: none; background: transparent; cursor: pointer; color: var(--text-500); border-bottom: 2px solid transparent; }
.aa-tab.is-active { color: var(--primary-600); border-bottom-color: var(--primary-600); font-weight: var(--font-weight-semibold); }
.aa-filter { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.aa-input, .aa-filter select { padding: var(--space-1) var(--space-2); border: 1px solid var(--border-300); border-radius: var(--radius-sm); }
.aa-danger { color: var(--danger-600); }
.aa-stat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: var(--space-3); }
.aa-stat { padding: var(--space-3); border: 1px solid var(--border-200); border-radius: var(--radius-md); text-align: center; }
.aa-stat__num { font-size: var(--font-size-2xl); font-weight: var(--font-weight-bold); color: var(--primary-600); }
.aa-stat__label { color: var(--text-500); font-size: var(--font-size-sm); }
.aa-tree { list-style: none; padding-left: var(--space-2); }
.aa-tree ul { list-style: none; padding-left: var(--space-4); }
.aa-modal { position: fixed; inset: 0; background: rgba(0,0,0,.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.aa-modal__panel { background: var(--surface-100, #fff); border-radius: var(--radius-lg); padding: var(--space-4); width: 420px; max-width: 92vw; max-height: 88vh; overflow: auto; }
.aa-modal__panel--wide { width: 640px; }
.aa-modal__title { margin: 0 0 var(--space-3); font-size: var(--font-size-lg); }
.aa-form__row { display: flex; flex-direction: column; gap: var(--space-1); margin-bottom: var(--space-2); }
.aa-form__label { font-size: var(--font-size-sm); color: var(--text-500); }
.aa-form input, .aa-form select { padding: var(--space-1) var(--space-2); border: 1px solid var(--border-300); border-radius: var(--radius-sm); }
.aa-req { color: var(--danger-600); margin-left: 2px; }
.aa-modal__foot { display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-3); }
.mp-btn { padding: var(--space-1) var(--space-3); border: 1px solid var(--border-300); background: transparent; border-radius: var(--radius-sm); cursor: pointer; }
.mp-btn--primary { background: var(--primary-600); color: #fff; border-color: var(--primary-600); }
.mp-link + .mp-link { margin-left: var(--space-2); }
</style>
