<template>
  <ModulePageShell
    :title="tabs.find(item => item.key === tab)?.label || '业务工作区'"
    subtitle="核对当前对象和版本，按权限办理；切换对象后重新读取正式记录"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/courses')">课程列表</AppButton>
      <AppButton v-if="hasPermission('academicAffairs.course.manage')" variant="primary" @click="$router.push('/admin/academic-affairs/courses/new')">＋ 新建课程</AppButton>
    </template>

    <details class="aacc-workspace-directory"><summary>切换相关工作区</summary><div class="aacc-tabs">
      <button v-for="t in tabs" :key="t.key" :class="['aacc-tab', { 'is-active': tab === t.key }]" @click="switchTab(t.key)">{{ t.label }}</button>
    </div></details>

    <!-- 分类/性质/考核方式：快捷筛选芯片（带计数） -->
    <div v-if="tab === 'category' || tab === 'nature' || tab === 'assessment'" class="aacc-chips">
      <button class="aacc-chip" :class="{ 'is-active': !dimFilter }" @click="dimFilter = ''">全部</button>
      <button v-for="opt in dimOptions" :key="opt.value" class="aacc-chip" :class="{ 'is-active': dimFilter === opt.value }" @click="dimFilter = opt.value">
        {{ opt.label }}
      </button>
    </div>
    <!-- 课程负责人：未指定筛选 -->
    <div v-if="tab === 'owner'" class="aacc-chips">
      <button class="aacc-chip" :class="{ 'is-active': !ownerFilter }" @click="ownerFilter = ''">全部</button>
      <button class="aacc-chip" :class="{ 'is-active': ownerFilter === 'UNSET' }" @click="ownerFilter = 'UNSET'">未指定负责人</button>
      <button class="aacc-chip" :class="{ 'is-active': ownerFilter === 'SET' }" @click="ownerFilter = 'SET'">已指定</button>
    </div>
    <!-- 课程停用：状态筛选 -->
    <div v-if="tab === 'disable'" class="aacc-chips">
      <button class="aacc-chip" :class="{ 'is-active': !statusFilter }" @click="statusFilter = ''">全部可停用/启用</button>
      <button class="aacc-chip" :class="{ 'is-active': statusFilter === 'ENABLED' }" @click="statusFilter = 'ENABLED'">已启用</button>
      <button class="aacc-chip" :class="{ 'is-active': statusFilter === 'DISABLED' }" @click="statusFilter = 'DISABLED'">已停用</button>
    </div>
    <!-- 历史课程：已停用 / 旧版本（被新版本取代）筛选 -->
    <div v-if="tab === 'archive'" class="aacc-chips">
      <button class="aacc-chip" :class="{ 'is-active': !archiveFilter }" @click="archiveFilter = ''">全部</button>
      <button class="aacc-chip" :class="{ 'is-active': archiveFilter === 'DISABLED' }" @click="archiveFilter = 'DISABLED'">已停用</button>
      <button class="aacc-chip" :class="{ 'is-active': archiveFilter === 'SUPERSEDED' }" @click="archiveFilter = 'SUPERSEDED'">历史版本</button>
    </div>

    <AppInlineAlert v-if="savedCourse" type="success" :description="savedCourse.message" />
    <AppButton v-if="savedCourse?.courseId" @click="$router.push({ path: '/admin/academic-affairs/courses/' + savedCourse.courseId, query: { returnTo: $route.fullPath } })">打开已保存课程</AppButton>
    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <template v-else>
      <EmptyState v-if="!displayRows.length" v-bind="emptyStateCopy" />
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
        <template #cell-owner="{ row }">{{ row.ownerTeacherId ? (row.ownerTeacherName || '负责人姓名未取得') : '未指定' }}</template>
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
      <nav v-if="serverTotal > viewPageSize || viewPage > 1" class="aacc-pagination" aria-label="课程工作区分页">
        <span>共 {{ serverTotal }} 条 · 第 {{ viewPage }} / {{ totalPages }} 页</span>
        <div>
          <AppButton size="sm" :disabled="viewPage <= 1" @click="viewPage -= 1">上一页</AppButton>
          <AppButton size="sm" :disabled="viewPage >= totalPages" @click="viewPage += 1">下一页</AppButton>
        </div>
      </nav>
    </template>

    <!-- 调整类别/性质/考核方式 -->
    <AppDrawer :visible="dimForm.visible" :title="dimFormTitle" mode="modal" size="medium" @update:visible="!saving && (dimForm.visible = $event)">
      <div class="aacc-form" v-if="dimForm.row">
        <AppFormItem :label="dimForm.row.courseName"><span class="mp-note">{{ dimForm.row.courseCode }}</span></AppFormItem>
        <AppFormItem v-if="dimForm.dim === 'category'" label="课程类别" required>
          <AppSelect :disabled="saving" v-model="dimForm.value" :options="categoryOptions" />
        </AppFormItem>
        <AppFormItem v-else-if="dimForm.dim === 'nature'" label="课程性质" required>
          <AppSelect :disabled="saving" v-model="dimForm.value" :options="natureOptions" />
        </AppFormItem>
        <AppFormItem v-else label="考核方式" required hint="将影响该课程期中期末考试组织方式（考试/考查）">
          <AppSelect :disabled="saving" v-model="dimForm.value" :options="assessmentOptions" />
        </AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="dimForm.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitDimForm">保存</AppButton>
      </template>
    </AppDrawer>

    <!-- 编辑学分学时 -->
    <AppDrawer :visible="creditForm.visible" title="编辑学分学时" mode="modal" size="large" @update:visible="!saving && (creditForm.visible = $event)">
      <div class="aacc-form" v-if="creditForm.row">
        <AppFormItem :label="creditForm.row.courseName"><span class="mp-note">{{ creditForm.row.courseCode }}</span></AppFormItem>
        <AppFormItem label="学分" required><AppNumberInput :disabled="saving" v-model="creditForm.credit" :min="0" :step="0.5" /></AppFormItem>
        <AppFormItem label="总学时" hint="留空或与下方分项之和一致"><AppNumberInput :disabled="saving" v-model="creditForm.hoursTotal" :min="0" /></AppFormItem>
        <AppFormItem label="理论学时"><AppNumberInput :disabled="saving" v-model="creditForm.hoursTheory" :min="0" /></AppFormItem>
        <AppFormItem label="实践学时"><AppNumberInput :disabled="saving" v-model="creditForm.hoursPractice" :min="0" /></AppFormItem>
        <AppFormItem label="实验学时"><AppNumberInput :disabled="saving" v-model="creditForm.hoursExperiment" :min="0" /></AppFormItem>
        <AppFormItem label="上机学时"><AppNumberInput :disabled="saving" v-model="creditForm.hoursComputer" :min="0" /></AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="creditForm.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitCreditForm">保存</AppButton>
      </template>
    </AppDrawer>

    <!-- 指定/更换课程负责人 -->
    <AppDrawer :visible="ownerForm.visible" title="指定课程负责人" mode="modal" size="medium" @update:visible="!saving && (ownerForm.visible = $event)">
      <div class="aacc-form" v-if="ownerForm.row">
        <AppFormItem :label="ownerForm.row.courseName"><span class="mp-note">{{ ownerForm.row.courseCode }}</span></AppFormItem>
        <AppFormItem label="课程负责人" required hint="须为本校在职教师">
          <AppTeacherPicker :disabled="saving" v-model="ownerForm.ownerTeacherId" clearable />
        </AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="ownerForm.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitOwnerForm">保存</AppButton>
      </template>
    </AppDrawer>

    <!-- 课程大纲 / 课程材料：文件清单 + 新增（附件走文件中心，POST /api/v1/files） -->
    <AppDrawer :visible="materialPanel.visible" :title="materialPanelTitle" mode="modal" size="large" @update:visible="materialPanel.visible = $event">
      <div class="aacc-form" v-if="materialPanel.course">
        <AppFormItem :label="materialPanel.course.courseName"><span class="mp-note">{{ materialPanel.course.courseCode }}</span></AppFormItem>

        <ErrorState v-if="materialPanel.error" :description="materialPanel.error" @retry="loadMaterials" />
        <AppFileList v-else
          :files="materialFiles"
          :loading="materialPanel.loading"
          :empty-text="materialPanel.lockedType === 'SYLLABUS' ? '暂无大纲文档' : '暂无课程材料'"
          :previewable="false"
          downloadable
          :removable="canVoidMaterial"
          @download="downloadMaterial"
          @remove="confirmVoidMaterial"
        />

        <div v-if="hasPermission('academicAffairs.course.manage')" class="aacc-material-add">
          <div class="aacc-material-add__title">{{ materialPanel.lockedType === 'SYLLABUS' ? '＋ 上传大纲文档' : '＋ 新增材料' }}</div>
          <AppFormItem v-if="!materialPanel.lockedType" label="材料类型" required>
            <AppSelect v-model="materialForm.materialType" :options="materialTypeOptions" />
          </AppFormItem>
          <AppFormItem label="标题" required>
            <AppTextInput v-model="materialForm.title" placeholder="如：数据结构教学大纲（2026版）" :maxlength="200" />
          </AppFormItem>
          <AppFormItem label="附件" hint="选填，支持 pdf/doc/docx/ppt/pptx/xls/xlsx 等，≤50MB">
            <input type="file" :disabled="materialForm.uploading || materialForm.submitting" @change="onMaterialFilePick" />
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
 * 课程分类 / 课程性质 / 学分学时 / 课程大纲 / 考核方式 / 课程负责人 / 课程材料 / 课程停用 / 历史课程
 * 9 个三级模块共用同一台账不同 ?tab= 视角，对齐既有「培养方案」「学院专业班级」控制台模式。
 * 深编辑/两级审核仍走 /courses/:id 详情页与 /courses/:id/edit 表单。
 * 维度类写操作（分类/性质/学分学时/考核方式/负责人）一律取当前完整课程记录 merge 目标字段后整体 PUT
 * （后端 update_course 按整表字段覆盖，不支持局部 PATCH）。
 *
 * Tier1 R3 续工新增（施工记录 2026-07-16）：
 * - 课程大纲 / 课程材料：新增 t_aa_course_material 挂课程级教学资源，附件走既有文件中心
 *   （POST /api/v1/files），materialType=SYLLABUS 即「课程大纲」子集，两个三级菜单共用同一套
 *   Drawer 组件（materialPanel/materialForm），仅 lockedType 不同；
 * - 考核方式：字段（exam_mode）与读写端点此前已存在（Tier1 R2 铺底），本轮只补齐控制台 Tab 入口；
 * - 历史课程（R3 外部核验后由 navPlan 模板占位名「课程归档」改名）：真实教务系统的课程库没有"归档"
 *   概念——条目终态是停用/禁用（强智"禁用"、南开课程库清理"沉淀处理"、正方课程库表单无状态字段、
 *   北理工官方定义课程库维护只有增/删/改）；"归档"在教务语境专指教学档案移交档案馆，且本项目该词已被
 *   「教务归档」模块（按学期批次归档9域）占用，同词不同义会误导教务处用户。本 tab 展示的实际内容就是
 *   "已停用 + 被新版本取代的旧版本"，故按实命名。不新增状态机状态（SM-05 冻结 6 态无 ARCHIVED，
 *   DISABLED 即终态），纯前端只读派生，数据完全来自既有 version/status 字段，不需要新后端接口。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import {
  AppSelect, AppNumberInput, AppFormItem, AppStatusTag, AppTeacherPicker, AppInlineAlert,
  AppFileList, AppTextInput, AppTextarea, AppConfirmDialog
} from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { COURSE_CATEGORY, COURSE_NATURE, EXAM_MODE, MATERIAL_TYPE, REVIEW_STATUS, reviewStatusColor } from '@/modules/academicAffairs/constants/course-program'
import { matchPermission } from '@/config/navPlan'
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
      tab: 'category', loading: true, error: '', rows: [], saving: false, formError: '', disposed: false, listReadRevision: 0, serverTotal: 0, materialReadRevision: 0, savedCourse: null,
      dimFilter: '', ownerFilter: '', statusFilter: '', archiveFilter: '', viewPage: 1, viewPageSize: 20,
      tabs: [
        { key: 'category', label: '课程分类' },
        { key: 'nature', label: '课程性质' },
        { key: 'credit', label: '学分学时' },
        { key: 'outline', label: '课程大纲' },
        { key: 'assessment', label: '考核方式' },
        { key: 'owner', label: '课程负责人' },
        { key: 'material', label: '课程材料' },
        { key: 'disable', label: '课程停用' },
        { key: 'archive', label: '历史课程' }
      ],
      dimForm: { visible: false, dim: 'category', row: null, value: '' },
      creditForm: { visible: false, row: null, credit: 0, hoursTotal: null, hoursTheory: null, hoursPractice: null, hoursExperiment: null, hoursComputer: null },
      ownerForm: { visible: false, row: null, ownerTeacherId: '' },
      materialPanel: { visible: false, course: null, lockedType: '', loading: false, items: [], error: '' },
      materialForm: { materialType: 'COURSEWARE', title: '', fileId: '', fileName: '', remark: '', uploading: false, submitting: false, err: '' },
      materialVoidConfirm: { visible: false, id: '', title: '', submitting: false }
    }
  },
  computed: {
    contextIdentity() { return JSON.stringify([this.ctx.ctxKey, this.ctx.currentRole, this.ctx.dataScope, this.ctx.permissionPatterns, this.ctx.permissionVersion, this.ctx.dataScopeVersion]) },
    canVoidMaterial() {
      return this.hasPermission('academicAffairs.course.manage') && String(this.ctx.currentRole?.roleCode || this.ctx.currentRole?.roleType || '').toUpperCase() !== 'COLLEGE_ACADEMIC'
    },
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
    emptyStateCopy() { return { title: '当前条件下没有课程', description: '请调整筛选条件后重试。历史课程只包含已停用或已有更高正式版本的记录。' } },
    totalPages() { return Math.max(1, Math.ceil(this.serverTotal / this.viewPageSize)) },
    displayRows() { return this.rows }
  },
  watch: {
    contextIdentity() { this.materialPanel.visible = false; this.materialVoidConfirm.visible = false; this.dimForm.visible = false; this.creditForm.visible = false; this.ownerForm.visible = false; this.savedCourse = null; this.rows = []; this.load() },
    '$route.query.tab': function (nextTab) {
      if (!nextTab || nextTab === this.tab || !this.tabs.some((item) => item.key === nextTab)) return
      this.tab = nextTab
      this.dimFilter = ''
      this.ownerFilter = ''
      this.statusFilter = ''
      this.archiveFilter = ''
      this.searchPage()
    },
    dimFilter() { this.searchPage() },
    ownerFilter() { this.searchPage() },
    statusFilter() { this.searchPage() },
    archiveFilter() { this.searchPage() },
    viewPage() { this.load() }
  },
  created() {
    const q = this.$route && this.$route.query && this.$route.query.tab
    if (q && this.tabs.some((t) => t.key === q)) this.tab = q
    this.load()
  },
  beforeUnmount() { this.disposed = true; this.materialReadRevision++; this.listReadRevision++ },
  methods: {
    hasPermission(key) { return matchPermission(this.ctx.permissionPatterns || [], key) },
    reviewStatusColor,
    statusLabel(s) { return REVIEW_STATUS[s] || (s ? '状态待确认' : '') },
    examModeLabel(v) { return EXAM_MODE[v] || (v ? '考核方式待确认' : '') },
    /** 维度 Tab 对应的真实课程字段名（assessment Tab 展示名与后端字段名 examMode 不同名）。 */
    dimFieldName(dim) { return dim === 'assessment' ? 'examMode' : dim },
    switchTab(k) {
      return this.$router.replace({ query: { ...this.$route.query, tab: k } })
    },
    searchPage() { if (this.viewPage === 1) return this.load(); this.viewPage = 1 },
    async load() {
      const revision = ++this.listReadRevision, identity = this.contextIdentity
      const current = () => !this.disposed && revision === this.listReadRevision && identity === this.contextIdentity
      const params = { page: this.viewPage, pageSize: this.viewPageSize }
      if (['category', 'nature'].includes(this.tab) && this.dimFilter) params[this.tab] = this.dimFilter
      if (this.tab === 'assessment' && this.dimFilter) params.examMode = this.dimFilter
      if (this.tab === 'owner' && this.ownerFilter) params.ownerAssigned = this.ownerFilter === 'SET'
      if (this.tab === 'disable') { params.togglable = true; if (this.statusFilter) params.status = this.statusFilter }
      if (this.tab === 'archive') params.history = this.archiveFilter || 'ALL'
      this.loading = true; this.error = ''; this.rows = []
      try {
        const res = await academicAffairsApi.getCourses(params)
        if (!current()) return
        if (res.code !== 0) { this.error = res.message || '课程读取失败，请重试'; return }
        this.rows = res.data.list; this.serverTotal = res.data.total
      } catch { if (current()) this.error = '课程读取失败，请重试' }
      finally { if (current()) this.loading = false }
    },
    // ── 通用：整表 merge 后 PUT ──
    async putCourse(row, patch) {
      const identity = this.contextIdentity
      const detail = await academicAffairsApi.getCourse(row.courseId)
      if (this.disposed || identity !== this.contextIdentity || !this.hasPermission('academicAffairs.course.manage')) return { code: -1, message: '当前身份已变化，请重新打开课程' }
      if (detail.code !== 0) return detail
      if (String(detail.data?.courseId) !== String(row.courseId)) return { code: -1, message: '课程信息不一致，请重新打开课程' }
      row = detail.data
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
    async saveCoursePatch(form, patch) {
      if (this.saving || !form.visible || !form.row || !this.hasPermission('academicAffairs.course.manage')) return
      const identity = this.contextIdentity
      this.saving = true; this.formError = ''; this.savedCourse = null
      try {
        const res = await this.putCourse(form.row, patch)
        if (this.disposed || identity !== this.contextIdentity || !form.visible) return
        if (res.code !== 0) { this.formError = res.message || '保存失败，已保留输入'; return }
        form.visible = false
        const id = res.data?.courseId
        this.savedCourse = { courseId: id, message: id ? String(id) !== String(form.row.courseId) ? '已建立新的课程草稿，请打开新版本继续办理审核。原版本及已有引用保持不变。' : '课程已保存，可打开课程核对结果。' : '保存已确认，但未取得课程编号，请从课程列表核对，勿重复提交。' }
        await this.load()
      } catch { if (!this.disposed && identity === this.contextIdentity) this.formError = '保存失败，已保留输入，请重试' }
      finally { this.saving = false }
    },
    // ── 课程分类/性质/考核方式 ──
    openDimForm(row, dim) {
      if (this.saving || !this.hasPermission('academicAffairs.course.manage')) return
      this.formError = ''
      this.dimForm = { visible: true, dim, row, value: row[this.dimFieldName(dim)] }
    },
    async submitDimForm() {
      const field = this.dimFieldName(this.dimForm.dim)
      return this.saveCoursePatch(this.dimForm, { [field]: this.dimForm.value })
    },
    // ── 学分学时 ──
    openCreditForm(row) {
      if (this.saving || !this.hasPermission('academicAffairs.course.manage')) return
      this.formError = ''
      this.creditForm = {
        visible: true, row, credit: row.credit, hoursTotal: row.hoursTotal, hoursTheory: row.hoursTheory,
        hoursPractice: row.hoursPractice, hoursExperiment: row.hoursExperiment, hoursComputer: row.hoursComputer
      }
    },
    async submitCreditForm() {
      const f = this.creditForm
      return this.saveCoursePatch(f, {
        credit: f.credit, hoursTotal: f.hoursTotal, hoursTheory: f.hoursTheory,
        hoursPractice: f.hoursPractice, hoursExperiment: f.hoursExperiment, hoursComputer: f.hoursComputer
      })
    },
    // ── 课程负责人 ──
    openOwnerForm(row) {
      if (this.saving || !this.hasPermission('academicAffairs.course.manage')) return
      this.formError = ''
      this.ownerForm = { visible: true, row, ownerTeacherId: row.ownerTeacherId || '' }
    },
    async submitOwnerForm() {
      if (!this.ownerForm.ownerTeacherId) { this.formError = '请选择课程负责人'; return }
      return this.saveCoursePatch(this.ownerForm, { ownerTeacherId: this.ownerForm.ownerTeacherId })
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
      this.materialVoidConfirm.visible = false
      this.materialPanel = { visible: true, course: row, lockedType: lockedType || '', loading: true, items: [], error: '' }
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
      const panel = this.materialPanel, identity = this.contextIdentity, revision = ++this.materialReadRevision
      if (!panel.visible || !panel.course) return
      const current = () => !this.disposed && panel === this.materialPanel && panel.visible && revision === this.materialReadRevision && identity === this.contextIdentity
      panel.loading = true; panel.error = ''; panel.items = []
      try {
        const res = await academicAffairsApi.getCourseMaterials(panel.course.courseId, panel.lockedType)
        if (!current()) return
        if (res.code === 0) panel.items = res.data.list
        else panel.error = res.message || '材料读取失败，请重试'
      } catch { if (current()) panel.error = '材料读取失败，请重试' }
      finally { if (current()) panel.loading = false }
    },
    async onMaterialFilePick(e) {
      const file = e.target.files && e.target.files[0]
      const f = this.materialForm, panel = this.materialPanel, identity = this.contextIdentity
      if (!file || f.uploading || f.submitting || !panel.visible || !this.hasPermission('academicAffairs.course.manage')) return
      const current = () => !this.disposed && f === this.materialForm && panel === this.materialPanel && panel.visible && identity === this.contextIdentity
      f.uploading = true; f.err = ''
      try {
        const res = await academicAffairsApi.uploadCourseMaterialFile(file)
        if (!current()) return
        if (res.code === 0) { f.fileId = res.data.fileId; f.fileName = res.data.fileName || file.name }
        else f.err = '附件上传失败：' + (res.message || '')
      } catch { if (current()) f.err = '附件上传失败，请重试' }
      finally { f.uploading = false }
    },
    async submitMaterialForm() {
      const f = this.materialForm, panel = this.materialPanel, identity = this.contextIdentity
      if (f.submitting || f.uploading || !panel.visible || !panel.course || !this.hasPermission('academicAffairs.course.manage')) return
      const current = () => !this.disposed && f === this.materialForm && panel === this.materialPanel && panel.visible && identity === this.contextIdentity
      f.err = ''
      if (!f.title || !f.title.trim()) { f.err = '请填写标题'; return }
      const materialType = panel.lockedType || f.materialType
      f.submitting = true
      try {
      const res = await academicAffairsApi.addCourseMaterial(panel.course.courseId, {
        materialType, title: f.title.trim(), fileId: f.fileId || null, fileName: f.fileName || null, remark: f.remark || null
      })
      if (!current()) return
      if (res.code !== 0) { f.err = res.message || '新增失败'; return }
      toast.success('已新增'); this.resetMaterialForm(); this.loadMaterials()
      } catch { if (current()) f.err = '材料保存失败，已保留输入，请重试' }
      finally { f.submitting = false }
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
      if (!this.canVoidMaterial || !this.materialPanel.visible || !this.materialPanel.items.some(item => String(item.id) === String(f.id))) return
      this.materialVoidConfirm = { visible: true, id: f.id, title: f.name, submitting: false, courseId: this.materialPanel.course.courseId }
    },
    async doVoidMaterial() {
      const dlg = this.materialVoidConfirm, panel = this.materialPanel, identity = this.contextIdentity
      if (!this.canVoidMaterial || !dlg.visible || dlg.submitting || !panel.visible || dlg.courseId !== panel.course?.courseId) return
      const current = () => !this.disposed && panel === this.materialPanel && dlg === this.materialVoidConfirm && identity === this.contextIdentity
      dlg.submitting = true
      try {
        const res = await academicAffairsApi.voidCourseMaterial(dlg.id)
        if (!current()) return
        if (res.code !== 0) { toast.error(res.message || '作废失败'); return }
        toast.success('已作废'); dlg.visible = false; this.loadMaterials()
      } catch { if (current()) toast.error('作废失败，请重试') }
      finally { dlg.submitting = false }
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
.aacc-workspace-directory{margin-bottom:14px}.aacc-workspace-directory summary{cursor:pointer;color:var(--primary-600,#2d5cad);font-size:13px;padding:8px 0}
.aacc-pagination { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 12px 4px 0; color: var(--text-500, #86909c); font-size: 13px; }
.aacc-pagination div { display: flex; gap: 8px; }
</style>
