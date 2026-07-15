<template>
  <ModulePageShell
    title="课程库 · 控制台"
    subtitle="课程分类 · 课程性质 · 学分学时 · 课程大纲 · 考核方式 · 课程负责人 · 课程材料 · 课程停用 · 课程归档"
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

    <!-- 分类/性质/考核方式：快捷筛选芯片（带计数） -->
    <div v-if="tab === 'category' || tab === 'nature' || tab === 'assessment'" class="aacc-chips">
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
    <!-- 课程归档：已停用 / 历史版本（被新版本取代）筛选 -->
    <div v-if="tab === 'archive'" class="aacc-chips">
      <button class="aacc-chip" :class="{ 'is-active': !archiveFilter }" @click="archiveFilter = ''">全部（{{ archiveRows.length }}）</button>
      <button class="aacc-chip" :class="{ 'is-active': archiveFilter === 'DISABLED' }" @click="archiveFilter = 'DISABLED'">已停用（{{ archiveDisabledCount }}）</button>
      <button class="aacc-chip" :class="{ 'is-active': archiveFilter === 'SUPERSEDED' }" @click="archiveFilter = 'SUPERSEDED'">历史版本（{{ archiveSupersededCount }}）</button>
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
        <template #cell-assessment="{ row }">{{ examModeLabel(row.examMode) }}</template>
        <template #cell-creditHours="{ row }">
          <div class="mp-cell-main">{{ row.credit }} 学分</div>
          <div class="mp-cell-sub">总{{ row.hoursTotal ?? '—' }}（理{{ row.hoursTheory ?? 0 }}/实{{ row.hoursPractice ?? 0 }}）</div>
        </template>
        <template #cell-owner="{ row }">{{ row.ownerTeacherId ? ('教师 #' + row.ownerTeacherId) : '未指定' }}</template>
        <template #cell-archiveReason="{ row }"><span class="mp-note">{{ row.archiveReason }}</span></template>
        <template #cell-ops="{ row }">
          <template v-if="tab === 'category'"><button class="mp-link" @click="openDimForm(row, 'category')">调整类别</button></template>
          <template v-if="tab === 'nature'"><button class="mp-link" @click="openDimForm(row, 'nature')">调整性质</button></template>
          <template v-if="tab === 'credit'"><button class="mp-link" @click="openCreditForm(row)">编辑学分学时</button></template>
          <template v-if="tab === 'outline'"><button class="mp-link" @click="openMaterialPanel(row, 'SYLLABUS')">管理大纲</button></template>
          <template v-if="tab === 'assessment'"><button class="mp-link" @click="openDimForm(row, 'assessment')">调整考核方式</button></template>
          <template v-if="tab === 'owner'"><button class="mp-link" @click="openOwnerForm(row)">{{ row.ownerTeacherId ? '更换负责人' : '指定负责人' }}</button></template>
          <template v-if="tab === 'material'"><button class="mp-link" @click="openMaterialPanel(row, '')">管理材料</button></template>
          <template v-if="tab === 'disable'">
            <button v-if="row.status === 'ENABLED'" class="mp-link" @click="doDisable(row)">停用</button>
            <button v-else-if="row.status === 'DISABLED'" class="mp-link" @click="doEnable(row)">启用</button>
            <span v-else class="mp-note">审核中不可操作</span>
          </template>
          <button class="mp-link" @click="$router.push(`/admin/academic-affairs/courses/${row.courseId}`)">详情</button>
        </template>
      </DataTable>
    </template>

    <!-- 调整类别/性质/考核方式 -->
    <AppDrawer :visible="dimForm.visible" :title="dimFormTitle" @update:visible="dimForm.visible = $event">
      <div class="aacc-form" v-if="dimForm.row">
        <AppFormItem :label="dimForm.row.courseName"><span class="mp-note">{{ dimForm.row.courseCode }}</span></AppFormItem>
        <AppFormItem v-if="dimForm.dim === 'category'" label="课程类别" required>
          <AppSelect v-model="dimForm.value" :options="categoryOptions" />
        </AppFormItem>
        <AppFormItem v-else-if="dimForm.dim === 'nature'" label="课程性质" required>
          <AppSelect v-model="dimForm.value" :options="natureOptions" />
        </AppFormItem>
        <AppFormItem v-else label="考核方式" required hint="将影响该课程期中期末考试组织方式（考试/考查）">
          <AppSelect v-model="dimForm.value" :options="assessmentOptions" />
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

    <!-- 课程大纲 / 课程材料：文件清单 + 新增（附件走文件中心，POST /api/v1/files/upload） -->
    <AppDrawer :visible="materialPanel.visible" :title="materialPanelTitle" @update:visible="materialPanel.visible = $event">
      <div class="aacc-form" v-if="materialPanel.course">
        <AppFormItem :label="materialPanel.course.courseName"><span class="mp-note">{{ materialPanel.course.courseCode }}</span></AppFormItem>

        <AppFileList
          :files="materialFiles"
          :loading="materialPanel.loading"
          :empty-text="materialPanel.lockedType === 'SYLLABUS' ? '暂无大纲文档' : '暂无课程材料'"
          :previewable="false"
          downloadable
          removable
          @download="downloadMaterial"
          @remove="confirmVoidMaterial"
        />

        <div class="aacc-material-add">
          <div class="aacc-material-add__title">{{ materialPanel.lockedType === 'SYLLABUS' ? '＋ 上传大纲文档' : '＋ 新增材料' }}</div>
          <AppFormItem v-if="!materialPanel.lockedType" label="材料类型" required>
            <AppSelect v-model="materialForm.materialType" :options="materialTypeOptions" />
          </AppFormItem>
          <AppFormItem label="标题" required>
            <AppTextInput v-model="materialForm.title" placeholder="如：数据结构教学大纲（2026版）" :maxlength="200" />
          </AppFormItem>
          <AppFormItem label="附件" hint="选填，支持 pdf/doc/docx/ppt/pptx/xls/xlsx 等，≤50MB">
            <input type="file" @change="onMaterialFilePick" />
            <span v-if="materialForm.uploading" class="mp-note">上传中…</span>
            <span v-else-if="materialForm.fileName" class="mp-note">已上传：{{ materialForm.fileName }}</span>
          </AppFormItem>
          <AppFormItem label="备注">
            <AppTextarea v-model="materialForm.remark" placeholder="选填" :rows="2" :maxlength="500" show-count />
          </AppFormItem>
          <AppInlineAlert v-if="materialForm.err" type="danger" :description="materialForm.err" />
          <div class="aacc-material-add__actions">
            <AppButton variant="primary" size="sm" :loading="materialForm.submitting" :disabled="materialForm.uploading" @click="submitMaterialForm">保存</AppButton>
          </div>
        </div>
      </div>

      <template #footer>
        <AppButton variant="ghost" @click="materialPanel.visible = false">关闭</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="materialVoidConfirm.visible" title="作废材料"
      :content="`确认作废「${materialVoidConfirm.title}」？作废后不可恢复（逻辑删除，留审计）。`"
      danger confirm-text="确认作废" :submitting="materialVoidConfirm.submitting" @confirm="doVoidMaterial" />
  </ModulePageShell>
</template>

<script>
/** 课程库控制台（/admin/academic-affairs/courses/console?tab=xxx）：
 * 课程分类 / 课程性质 / 学分学时 / 课程大纲 / 考核方式 / 课程负责人 / 课程材料 / 课程停用 / 课程归档
 * 9 个三级模块共用同一台账不同 ?tab= 视角，对齐既有「培养方案」「学院专业班级」控制台模式。
 * 深编辑/两级审核仍走 /courses/:id 详情页与 /courses/:id/edit 表单。
 * 维度类写操作（分类/性质/学分学时/考核方式/负责人）一律取当前完整课程记录 merge 目标字段后整体 PUT
 * （后端 update_course 按整表字段覆盖，不支持局部 PATCH）。
 *
 * Tier1 R3 续工新增（施工记录 2026-07-16）：
 * - 课程大纲 / 课程材料：新增 t_aa_course_material 挂课程级教学资源，附件走既有文件中心
 *   （POST /api/v1/files/upload），materialType=SYLLABUS 即「课程大纲」子集，两个三级菜单共用同一套
 *   Drawer 组件（materialPanel/materialForm），仅 lockedType 不同；
 * - 考核方式：字段（exam_mode）与读写端点此前已存在（Tier1 R2 铺底），本轮只补齐控制台 Tab 入口；
 * - 课程归档：不新增状态机状态（SM-05 冻结 6 态无 ARCHIVED），改为纯前端只读视图——按 courseCode 分组取
 *   最大 version 为当前版本，DISABLED 或非最大版本视为「已归档」（已停用 / 历史版本），数据完全来自既有
 *   version/status 字段，不需要新后端接口。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import {
  AppSelect, AppNumberInput, AppFormItem, AppStatusTag, AppTeacherPicker, AppInlineAlert,
  AppFileList, AppTextInput, AppTextarea, AppConfirmDialog
} from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { COURSE_CATEGORY, COURSE_NATURE, EXAM_MODE, MATERIAL_TYPE, REVIEW_STATUS, reviewStatusColor } from '@/modules/academicAffairs/constants/course-program'
import { toast } from '@/utils/toast'

export default {
  name: 'AaCourseConsoleView',
  components: {
    ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppDrawer,
    AppSelect, AppNumberInput, AppFormItem, AppStatusTag, AppTeacherPicker, AppInlineAlert,
    AppFileList, AppTextInput, AppTextarea, AppConfirmDialog
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      tab: 'category', loading: true, error: '', rows: [], saving: false, formError: '',
      dimFilter: '', ownerFilter: '', statusFilter: '', archiveFilter: '',
      tabs: [
        { key: 'category', label: '课程分类' },
        { key: 'nature', label: '课程性质' },
        { key: 'credit', label: '学分学时' },
        { key: 'outline', label: '课程大纲' },
        { key: 'assessment', label: '考核方式' },
        { key: 'owner', label: '课程负责人' },
        { key: 'material', label: '课程材料' },
        { key: 'disable', label: '课程停用' },
        { key: 'archive', label: '课程归档' }
      ],
      dimForm: { visible: false, dim: 'category', row: null, value: '' },
      creditForm: { visible: false, row: null, credit: 0, hoursTotal: null, hoursTheory: null, hoursPractice: null, hoursExperiment: null, hoursComputer: null },
      ownerForm: { visible: false, row: null, ownerTeacherId: '' },
      materialPanel: { visible: false, course: null, lockedType: '', loading: false, items: [] },
      materialForm: { materialType: 'COURSEWARE', title: '', fileId: '', fileName: '', remark: '', uploading: false, submitting: false, err: '' },
      materialVoidConfirm: { visible: false, id: '', title: '', submitting: false }
    }
  },
  computed: {
    categoryOptions() { return Object.keys(COURSE_CATEGORY).map((k) => ({ label: COURSE_CATEGORY[k], value: k })) },
    natureOptions() { return Object.keys(COURSE_NATURE).map((k) => ({ label: COURSE_NATURE[k], value: k })) },
    assessmentOptions() { return Object.keys(EXAM_MODE).map((k) => ({ label: EXAM_MODE[k], value: k })) },
    materialTypeOptions() { return Object.keys(MATERIAL_TYPE).map((k) => ({ label: MATERIAL_TYPE[k], value: k })) },
    dimOptions() {
      if (this.tab === 'category') return this.categoryOptions
      if (this.tab === 'assessment') return this.assessmentOptions
      return this.natureOptions
    },
    dimFormTitle() {
      if (this.dimForm.dim === 'category') return '调整课程类别'
      if (this.dimForm.dim === 'nature') return '调整课程性质'
      return '调整考核方式'
    },
    unsetOwnerCount() { return this.rows.filter((r) => !r.ownerTeacherId).length },
    togglableRows() { return this.rows.filter((r) => r.status === 'ENABLED' || r.status === 'DISABLED') },
    enabledCount() { return this.rows.filter((r) => r.status === 'ENABLED').length },
    disabledCount() { return this.rows.filter((r) => r.status === 'DISABLED').length },
    /** 课程归档（纯前端派生，不建新状态）：按 courseCode 分组取最大 version 视为当前版本；
     * DISABLED 或非最大版本一律计入归档视图（历史版本仍可能是 ENABLED——旧版本供历史培养方案引用，
     * 见 SM-05 冻结规则，不代表已停用，archiveReason 分别标注区分）。 */
    archiveRows() {
      const maxVerByCode = {}
      this.rows.forEach((r) => {
        const v = Number(r.version) || 1
        if (!maxVerByCode[r.courseCode] || v > maxVerByCode[r.courseCode]) maxVerByCode[r.courseCode] = v
      })
      return this.rows
        .filter((r) => r.status === 'DISABLED' || Number(r.version) < (maxVerByCode[r.courseCode] || 1))
        .map((r) => ({
          ...r,
          archiveVersionLabel: `v${r.version}`,
          archiveReason: r.status === 'DISABLED' ? '已停用' : `已有新版本 v${maxVerByCode[r.courseCode]}（历史版本供既有培养方案引用）`
        }))
    },
    archiveDisabledCount() { return this.archiveRows.filter((r) => r.status === 'DISABLED').length },
    archiveSupersededCount() { return this.archiveRows.filter((r) => r.status !== 'DISABLED').length },
    archiveFilteredRows() {
      if (this.archiveFilter === 'DISABLED') return this.archiveRows.filter((r) => r.status === 'DISABLED')
      if (this.archiveFilter === 'SUPERSEDED') return this.archiveRows.filter((r) => r.status !== 'DISABLED')
      return this.archiveRows
    },
    materialPanelTitle() { return this.materialPanel.lockedType === 'SYLLABUS' ? '课程大纲' : '课程材料' },
    materialFiles() {
      return this.materialPanel.items.map((m) => ({
        id: m.id, fileId: m.fileId, name: m.title + (m.fileName ? `（${m.fileName}）` : '（无附件，仅登记）'),
        uploadedAt: m.createdAt, uploader: m.uploader, status: 'done'
      }))
    },
    columns() {
      const map = {
        category: [{ key: 'course', title: '课程' }, { key: 'category', title: '类别' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作', width: '160px' }],
        nature: [{ key: 'course', title: '课程' }, { key: 'nature', title: '性质' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作', width: '160px' }],
        credit: [{ key: 'course', title: '课程' }, { key: 'creditHours', title: '学分 / 学时' }, { key: 'ops', title: '操作', width: '160px' }],
        outline: [{ key: 'course', title: '课程' }, { key: 'ops', title: '操作', width: '140px' }],
        assessment: [{ key: 'course', title: '课程' }, { key: 'assessment', title: '考核方式' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作', width: '160px' }],
        owner: [{ key: 'course', title: '课程' }, { key: 'owner', title: '课程负责人' }, { key: 'ops', title: '操作', width: '160px' }],
        material: [{ key: 'course', title: '课程' }, { key: 'ops', title: '操作', width: '140px' }],
        disable: [{ key: 'course', title: '课程' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作', width: '160px' }],
        archive: [{ key: 'course', title: '课程' }, { key: 'archiveVersionLabel', title: '版本' }, { key: 'status', title: '状态' }, { key: 'archiveReason', title: '归档说明' }, { key: 'ops', title: '操作', width: '100px' }]
      }
      return map[this.tab] || []
    },
    displayRows() {
      if (this.tab === 'archive') return this.archiveFilteredRows
      let list = this.rows
      if ((this.tab === 'category' || this.tab === 'nature' || this.tab === 'assessment') && this.dimFilter) {
        list = list.filter((r) => r[this.dimFieldName(this.tab)] === this.dimFilter)
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
    examModeLabel(v) { return EXAM_MODE[v] || v || '' },
    /** 维度 Tab 对应的真实课程字段名（assessment Tab 展示名与后端字段名 examMode 不同名）。 */
    dimFieldName(dim) { return dim === 'assessment' ? 'examMode' : dim },
    dimCount(v) { return this.rows.filter((r) => r[this.dimFieldName(this.tab)] === v).length },
    switchTab(k) {
      this.tab = k
      this.dimFilter = ''; this.ownerFilter = ''; this.statusFilter = ''; this.archiveFilter = ''
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
    // ── 课程分类/性质/考核方式 ──
    openDimForm(row, dim) {
      this.formError = ''
      this.dimForm = { visible: true, dim, row, value: row[this.dimFieldName(dim)] }
    },
    async submitDimForm() {
      this.saving = true
      const field = this.dimFieldName(this.dimForm.dim)
      const res = await this.putCourse(this.dimForm.row, { [field]: this.dimForm.value })
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
    },
    // ── 课程大纲 / 课程材料（共用同一 Drawer，lockedType='SYLLABUS' 时即「课程大纲」）──
    openMaterialPanel(row, lockedType) {
      this.materialPanel = { visible: true, course: row, lockedType: lockedType || '', loading: true, items: [] }
      this.resetMaterialForm()
      this.loadMaterials()
    },
    resetMaterialForm() {
      this.materialForm = {
        materialType: this.materialPanel.lockedType || 'COURSEWARE', title: '', fileId: '', fileName: '',
        remark: '', uploading: false, submitting: false, err: ''
      }
    },
    async loadMaterials() {
      this.materialPanel.loading = true
      const res = await academicAffairsApi.getCourseMaterials(this.materialPanel.course.courseId, this.materialPanel.lockedType)
      this.materialPanel.loading = false
      if (res.code === 0) this.materialPanel.items = res.data.list
      else toast.error(res.message || '材料加载失败')
    },
    async onMaterialFilePick(e) {
      const file = e.target.files && e.target.files[0]
      if (!file) return
      this.materialForm.uploading = true; this.materialForm.err = ''
      const res = await academicAffairsApi.uploadCourseMaterialFile(file)
      this.materialForm.uploading = false
      if (res.code === 0) { this.materialForm.fileId = res.data.fileId; this.materialForm.fileName = res.data.fileName || file.name }
      else this.materialForm.err = '附件上传失败：' + (res.message || '')
    },
    async submitMaterialForm() {
      this.materialForm.err = ''
      const f = this.materialForm
      if (!f.title || !f.title.trim()) { f.err = '请填写标题'; return }
      const materialType = this.materialPanel.lockedType || f.materialType
      f.submitting = true
      const res = await academicAffairsApi.addCourseMaterial(this.materialPanel.course.courseId, {
        materialType, title: f.title.trim(), fileId: f.fileId || null, fileName: f.fileName || null, remark: f.remark || null
      })
      f.submitting = false
      if (res.code !== 0) { f.err = res.message || '新增失败'; return }
      toast.success('已新增'); this.resetMaterialForm(); this.loadMaterials()
    },
    async downloadMaterial(f) {
      if (!f.fileId) { toast.error('该材料未上传附件'); return }
      try {
        const blob = await academicAffairsApi.downloadCourseMaterial(f.fileId)
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url; a.download = f.name || '附件'
        document.body.appendChild(a); a.click(); a.remove()
        URL.revokeObjectURL(url)
      } catch (e) { toast.error('下载失败：' + (e.message || '')) }
    },
    confirmVoidMaterial(f) {
      this.materialVoidConfirm = { visible: true, id: f.id, title: f.name, submitting: false }
    },
    async doVoidMaterial() {
      this.materialVoidConfirm.submitting = true
      const res = await academicAffairsApi.voidCourseMaterial(this.materialVoidConfirm.id)
      this.materialVoidConfirm.submitting = false
      if (res.code !== 0) { toast.error(res.message || '作废失败'); return }
      toast.success('已作废'); this.materialVoidConfirm.visible = false; this.loadMaterials()
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
.aacc-material-add { margin-top: 16px; padding-top: 16px; border-top: 1px dashed var(--border-300, #d0d3d9); display: flex; flex-direction: column; gap: 10px; }
.aacc-material-add__title { font-size: 13px; font-weight: 600; color: var(--text-700, #4e5969); }
.aacc-material-add__actions { display: flex; justify-content: flex-end; }
</style>
