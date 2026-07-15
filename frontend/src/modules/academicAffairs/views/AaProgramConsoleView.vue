<template>
  <ModulePageShell
    title="培养方案 · 控制台"
    subtitle="方案制定 · 版本 · 课程模块 · 学分要求 · 毕业要求 · 审核 · 发布"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn" @click="$router.push('/admin/academic-affairs/programs')">方案列表</button>
    </template>

    <div class="aapc-tabs">
      <button v-for="t in tabs" :key="t.key" :class="['aapc-tab', { 'is-active': tab === t.key }]" @click="switchTab(t.key)">{{ t.label }}</button>
    </div>

    <!-- 方案选择器：课程模块 / 学分要求 / 毕业要求 需先选定一个方案 -->
    <div v-if="needsProgramPicker" class="aapc-picker">
      <span class="aapc-picker__label">当前方案</span>
      <AppSelect v-model="selectedProgramId" :options="programOptions" placeholder="选择要维护的培养方案…" @change="onProgramPicked" />
      <span v-if="selectedProgram" class="aapc-picker__hint">
        状态：<AppStatusTag :type="reviewStatusColor(selectedProgram.status)" dot>{{ statusLabel(selectedProgram.status) }}</AppStatusTag>
        <template v-if="!isEditable">（非编制态，仅可查看）</template>
      </span>
    </div>

    <div v-if="!needsProgramPicker" class="aapc-bar">
      <AppButton v-if="tab === 'authoring'" variant="primary" size="small" @click="openCreate">＋ 新建方案</AppButton>
    </div>
    <div v-else-if="selectedProgramId" class="aapc-bar">
      <AppButton v-if="tab === 'courseModules' && isEditable" variant="primary" size="small" @click="openCourseForm(null)">＋ 添加课程</AppButton>
      <AppButton v-if="tab === 'practicePlan' && isEditable" variant="primary" size="small" @click="openCourseForm(null, '实践环节')">＋ 添加实践课程</AppButton>
      <AppButton v-if="tab === 'creditRequirements' && isEditable" variant="primary" size="small" @click="openCreditForm(null)">＋ 添加模块学分</AppButton>
      <AppButton v-if="tab === 'creditRequirements' && isEditable" variant="secondary" size="small" :loading="savingCredit" @click="saveCredit">保存学分结构</AppButton>
      <AppButton v-if="tab === 'graduationRequirements' && isEditable" variant="primary" size="small" @click="openGradForm(null)">＋ 添加毕业要求</AppButton>
    </div>
    <div v-if="tab === 'practicePlan' && selectedProgramId && practiceCreditTarget !== null" class="aapc-picker__hint" style="margin-bottom:12px;">
      学分要求中「实践环节」目标学分：<strong>{{ practiceCreditTarget }}</strong>
      <button class="mp-link" @click="switchTab('creditRequirements')">去学分要求维护</button>
    </div>

    <ErrorState v-if="error" :description="error" @retry="reload" />
    <LoadingState v-else-if="loading" />
    <template v-else>
      <EmptyState v-if="needsProgramPicker && !selectedProgramId" title="请先选择方案" :description="emptyHint" />
      <EmptyState v-else-if="!rows.length" title="暂无数据" :description="emptyHint" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-status="{ row }"><AppStatusTag :type="reviewStatusColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag></template>
        <template #cell-program="{ row }">
          <div class="mp-cell-main">{{ row.programName }}</div>
          <div class="mp-cell-sub">{{ row.gradeYear ? ('年级 ' + row.gradeYear) : '未设年级' }} · v{{ row.version }}</div>
        </template>
        <template #cell-category="{ row }">{{ gradCategoryLabel(row.category) }}</template>
        <template #cell-creditTarget="{ row }">{{ row.creditTarget }}</template>
        <template #cell-ops="{ row }">
          <!-- 方案制定 -->
          <template v-if="tab === 'authoring'">
            <button class="mp-link" @click="$router.push(`/admin/academic-affairs/programs/${row.programId}`)">继续编制</button>
          </template>
          <!-- 方案版本 -->
          <template v-if="tab === 'versions'">
            <button class="mp-link" @click="$router.push(`/admin/academic-affairs/programs/${row.programId}`)">查看</button>
            <button v-if="canNewVersion(row.status)" class="mp-link" @click="doNewVersion(row)">新建版本</button>
          </template>
          <!-- 计划变更（收编入口：已发布/启用计划的变更须带原因，走同一版本链机制） -->
          <template v-if="tab === 'planChange'">
            <button class="mp-link" @click="$router.push(`/admin/academic-affairs/programs/${row.programId}`)">查看</button>
            <button v-if="canNewVersion(row.status)" class="mp-link" @click="openChange(row)">发起变更</button>
          </template>
          <!-- 课程模块 -->
          <template v-if="tab === 'courseModules'">
            <template v-if="isEditable">
              <button class="mp-link" @click="openCourseForm(row)">编辑</button>
              <button class="mp-link is-danger" @click="confirmDeleteCourse(row)">删除</button>
            </template>
          </template>
          <!-- 实践教学计划（课程模块的实践环节筛选切面，复用同一套课程明细读写） -->
          <template v-if="tab === 'practicePlan'">
            <template v-if="isEditable">
              <button class="mp-link" @click="openCourseForm(row)">编辑</button>
              <button class="mp-link is-danger" @click="confirmDeleteCourse(row)">删除</button>
            </template>
          </template>
          <!-- 学分要求 -->
          <template v-if="tab === 'creditRequirements'">
            <template v-if="isEditable">
              <button class="mp-link" @click="openCreditForm(row)">编辑</button>
              <button class="mp-link is-danger" @click="removeCreditRow(row)">删除</button>
            </template>
          </template>
          <!-- 毕业要求 -->
          <template v-if="tab === 'graduationRequirements'">
            <template v-if="isEditable">
              <button class="mp-link" @click="openGradForm(row)">编辑</button>
              <button class="mp-link is-danger" @click="confirmDeleteGrad(row)">删除</button>
            </template>
          </template>
          <!-- 方案审核 -->
          <template v-if="tab === 'review'">
            <button class="mp-link" @click="openReview(row, 'APPROVE')">{{ row.status === 'COLLEGE_REVIEW' ? '学院审核通过' : '教务审核通过' }}</button>
            <button class="mp-link is-danger" @click="openReview(row, 'RETURN')">退回</button>
          </template>
          <!-- 方案发布 -->
          <template v-if="tab === 'publish'">
            <button class="mp-link" @click="openBind(row)">绑定年级</button>
            <button class="mp-link" @click="viewBindings(row)">查看绑定</button>
          </template>
        </template>
      </DataTable>
    </template>

    <!-- 新建方案 -->
    <AppDrawer :visible="createVisible" title="新建培养方案" @update:visible="createVisible = $event">
      <div class="aapc-form">
        <AppFormItem label="方案名称" required><AppTextInput v-model="createForm.programName" :disabled="saving" placeholder="如 软件技术2026级培养方案" /></AppFormItem>
        <AppFormItem label="专业ID"><AppTextInput v-model="createForm.majorId" :disabled="saving" placeholder="选填" /></AppFormItem>
        <AppFormItem label="年级"><AppTextInput v-model="createForm.gradeYear" :disabled="saving" placeholder="如 2026" /></AppFormItem>
        <AppFormItem label="毕业总学分"><AppNumberInput v-model="createForm.totalCredits" :min="0" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="createVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitCreate">创建</AppButton>
      </template>
    </AppDrawer>

    <!-- 课程模块：新增/编辑 -->
    <AppDrawer :visible="courseVisible" :title="courseForm.programCourseId ? '编辑课程' : '添加课程'" @update:visible="courseVisible = $event">
      <div class="aapc-form">
        <AppFormItem label="课程名称" required><AppTextInput v-model="courseForm.courseName" :disabled="saving" /></AppFormItem>
        <AppFormItem label="课程模块"><AppTextInput v-model="courseForm.module" :disabled="saving" placeholder="如 专业核心/实践环节" /></AppFormItem>
        <AppFormItem label="开课学期"><AppNumberInput v-model="courseForm.openTermNo" :min="1" :max="12" :disabled="saving" /></AppFormItem>
        <AppFormItem label="学分"><AppNumberInput v-model="courseForm.credit" :min="0" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="courseVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitCourse">保存</AppButton>
      </template>
    </AppDrawer>

    <!-- 学分要求：新增/编辑模块学分行 -->
    <AppDrawer :visible="creditVisible" :title="creditForm._editing ? '编辑模块学分' : '添加模块学分'" @update:visible="creditVisible = $event">
      <div class="aapc-form">
        <AppFormItem label="课程模块" required><AppTextInput v-model="creditForm.module" :disabled="creditForm._editing" placeholder="如 公共基础/专业核心/顶岗实习" /></AppFormItem>
        <AppFormItem label="学分目标" required><AppNumberInput v-model="creditForm.creditTarget" :min="0" /></AppFormItem>
        <AppFormItem label="备注"><AppTextInput v-model="creditForm.note" /></AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" @click="creditVisible = false">取消</AppButton>
        <AppButton variant="primary" @click="submitCreditRow">确定</AppButton>
      </template>
    </AppDrawer>

    <!-- 毕业要求：新增/编辑 -->
    <AppDrawer :visible="gradVisible" :title="gradForm.requirementId ? '编辑毕业要求' : '添加毕业要求'" @update:visible="gradVisible = $event">
      <div class="aapc-form">
        <AppFormItem label="分类" required>
          <AppSelect v-model="gradForm.category" :options="gradCategoryOptions" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="要求内容" required><AppTextarea v-model="gradForm.content" :maxlength="1000" :disabled="saving" placeholder="如：具备较强的软件系统分析与设计能力" /></AppFormItem>
        <AppFormItem label="排序"><AppNumberInput v-model="gradForm.sortOrder" :min="0" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="gradVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitGrad">保存</AppButton>
      </template>
    </AppDrawer>

    <!-- 方案发布：绑定年级 -->
    <AppDrawer :visible="bindVisible" title="绑定年级" @update:visible="bindVisible = $event">
      <div class="aapc-form" v-if="bindRow">
        <AppFormItem label="方案"><span>{{ bindRow.programName }}</span></AppFormItem>
        <AppFormItem label="绑定年级" required><AppTextInput v-model="bindForm.gradeYear" placeholder="如 2026" /></AppFormItem>
        <AppFormItem label="行政班ID"><AppTextInput v-model="bindForm.classId" placeholder="选填，留空=全专业该年级" /></AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" @click="bindVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitBind">确认绑定</AppButton>
      </template>
    </AppDrawer>

    <!-- 方案发布：绑定记录只读 -->
    <AppDrawer :visible="bindingsVisible" title="绑定记录" @update:visible="bindingsVisible = $event">
      <EmptyState v-if="!bindingRows.length" title="暂无绑定记录" description="" />
      <ul v-else class="aapc-bindings">
        <li v-for="b in bindingRows" :key="b.bindingId">
          <span>{{ b.gradeYear }} 级{{ b.classId ? ('· 班级#' + b.classId) : '（全专业）' }}</span>
          <AppStatusTag :type="b.status === 'ACTIVE' ? 'success' : 'default'" dot>{{ b.status === 'ACTIVE' ? '生效中' : '已被替代' }}</AppStatusTag>
        </li>
      </ul>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="reviewDlg.visible"
      :title="reviewDlg.title"
      :type="reviewDlg.type"
      :confirm-text="reviewDlg.confirmText"
      :require-reason="reviewDlg.requireReason"
      reason-label="审核意见"
      :submitting="reviewDlg.submitting"
      @confirm="doReview"
    />
    <!-- 计划变更：已发布/启用计划须填写变更原因（≥5字），生成新版本并留痕 -->
    <AppConfirmDialog
      v-model:visible="changeDlg.visible"
      :title="changeDlg.row ? `发起变更「${changeDlg.row.programName}」` : '发起变更'"
      type="warning"
      confirm-text="确认变更"
      require-reason
      reason-label="变更原因"
      reason-placeholder="请说明本次教学计划变更的原因，如调整课程/学时/开课学院等"
      :submitting="changeDlg.submitting"
      @confirm="doChange"
    />
    <AppConfirmDialog
      v-model:visible="confirmDlg.visible"
      :title="confirmDlg.title"
      type="danger"
      confirm-text="确认删除"
      :submitting="confirmDlg.submitting"
      @confirm="onConfirmDelete"
    />
  </ModulePageShell>
</template>

<script>
/** 培养方案 · 控制台（/admin/academic-affairs/programs/console?tab=xxx）：
 * 方案制定 / 方案版本 / 课程模块 / 学分要求 / 毕业要求 / 方案审核 / 方案发布 7 个三级模块共用一个工作台，
 * 深链接对齐既有「学院专业班级」「教材管理」控制台模式（navPlan `?tab=` 叶子）。
 * 深编辑（基本信息/两级审提交/绑定操作历史）仍复用既有 /programs/:id 编制器，本页只做「跨方案工作队列 + 结构化子表 CRUD」。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import {
  AppTextInput, AppNumberInput, AppTextarea, AppSelect, AppFormItem,
  AppStatusTag, AppConfirmDialog, AppInlineAlert
} from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import {
  REVIEW_STATUS, reviewStatusColor, canSubmit, canNewVersion, canPublishBind,
  GRADUATION_REQUIREMENT_CATEGORY, isPracticeModule
} from '@/modules/academicAffairs/constants/course-program'
import { toast } from '@/utils/toast'

export default {
  name: 'AaProgramConsoleView',
  components: {
    ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppTextInput, AppNumberInput, AppTextarea, AppSelect, AppFormItem,
    AppStatusTag, AppConfirmDialog, AppInlineAlert
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      tab: 'authoring', loading: true, error: '', rows: [],
      pagination: null,
      tabs: [
        { key: 'authoring', label: '方案制定' },
        { key: 'versions', label: '方案版本' },
        { key: 'planChange', label: '计划变更' },
        { key: 'courseModules', label: '课程模块' },
        { key: 'practicePlan', label: '实践教学计划' },
        { key: 'creditRequirements', label: '学分要求' },
        { key: 'graduationRequirements', label: '毕业要求' },
        { key: 'review', label: '方案审核' },
        { key: 'publish', label: '方案发布' }
      ],
      allPrograms: [], selectedProgramId: '', selectedProgram: null,
      creditItems: [], savingCredit: false, practiceCreditTarget: null,
      saving: false, formError: '',
      createVisible: false, createForm: { programName: '', majorId: '', gradeYear: '', totalCredits: null },
      courseVisible: false, courseForm: { programCourseId: '', courseName: '', module: '', openTermNo: null, credit: null },
      creditVisible: false, creditForm: { module: '', creditTarget: 0, note: '', _editing: false, _origModule: '' },
      gradVisible: false, gradForm: { requirementId: '', category: 'ABILITY', content: '', sortOrder: 0 },
      bindVisible: false, bindRow: null, bindForm: { gradeYear: '', classId: '' },
      bindingsVisible: false, bindingRows: [],
      reviewDlg: { visible: false, title: '', type: 'primary', confirmText: '确认', requireReason: false, submitting: false, row: null, action: '' },
      changeDlg: { visible: false, submitting: false, row: null },
      confirmDlg: { visible: false, title: '', submitting: false, action: null }
    }
  },
  computed: {
    needsProgramPicker() { return ['courseModules', 'creditRequirements', 'graduationRequirements', 'practicePlan'].includes(this.tab) },
    isEditable() { return this.selectedProgram && canSubmit(this.selectedProgram.status) },
    programOptions() {
      return this.allPrograms.map((p) => ({ label: `${p.programName}（${p.gradeYear || '未设年级'} · v${p.version} · ${this.statusLabel(p.status)}）`, value: p.programId }))
    },
    gradCategoryOptions() {
      return Object.keys(GRADUATION_REQUIREMENT_CATEGORY).map((k) => ({ label: GRADUATION_REQUIREMENT_CATEGORY[k], value: k }))
    },
    columns() {
      const map = {
        authoring: [{ key: 'program', title: '方案' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作', width: '110px' }],
        versions: [{ key: 'program', title: '方案' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作', width: '160px' }],
        planChange: [{ key: 'program', title: '教学计划（方案）' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作', width: '140px' }],
        courseModules: [{ key: 'openTermNo', title: '开课学期' }, { key: 'module', title: '课程模块' }, { key: 'courseName', title: '课程名称' }, { key: 'credit', title: '学分' }, { key: 'ops', title: '操作', width: '110px' }],
        practicePlan: [{ key: 'openTermNo', title: '开课学期' }, { key: 'module', title: '实践环节' }, { key: 'courseName', title: '实践课程/项目' }, { key: 'credit', title: '学分' }, { key: 'ops', title: '操作', width: '110px' }],
        creditRequirements: [{ key: 'module', title: '课程模块' }, { key: 'creditTarget', title: '学分目标' }, { key: 'note', title: '备注' }, { key: 'ops', title: '操作', width: '110px' }],
        graduationRequirements: [{ key: 'category', title: '分类' }, { key: 'content', title: '要求内容' }, { key: 'sortOrder', title: '排序' }, { key: 'ops', title: '操作', width: '110px' }],
        review: [{ key: 'program', title: '方案' }, { key: 'status', title: '审核节点' }, { key: 'ops', title: '操作', width: '180px' }],
        publish: [{ key: 'program', title: '方案' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作', width: '160px' }]
      }
      return map[this.tab] || []
    },
    emptyHint() {
      return {
        authoring: '点击「新建方案」开始编制课程结构',
        versions: '暂无方案',
        planChange: '暂无已发布/启用的教学计划可发起变更',
        courseModules: this.selectedProgramId ? '点击「添加课程」构建方案课程结构' : '请选择一个方案',
        practicePlan: this.selectedProgramId ? '点击「添加实践课程」录入集中实践/实训/实习环节' : '请选择一个方案',
        creditRequirements: this.selectedProgramId ? '点击「添加模块学分」构建学分结构' : '请选择一个方案',
        graduationRequirements: this.selectedProgramId ? '点击「添加毕业要求」录入结构化条目' : '请选择一个方案',
        review: '暂无待审核方案',
        publish: '暂无待发布/已发布方案'
      }[this.tab] || ''
    }
  },
  async created() {
    const q = this.$route && this.$route.query && this.$route.query.tab
    if (q && this.tabs.some((t) => t.key === q)) this.tab = q
    await this.loadAllPrograms()
    this.reload()
  },
  methods: {
    reviewStatusColor, canNewVersion,
    statusLabel(s) { return REVIEW_STATUS[s] || s || '' },
    gradCategoryLabel(c) { return GRADUATION_REQUIREMENT_CATEGORY[c] || c || '' },
    switchTab(k) {
      this.tab = k
      this.$router.replace({ query: { ...this.$route.query, tab: k } }).catch(() => {})
      this.reload()
    },
    async loadAllPrograms() {
      const res = await academicAffairsApi.getPrograms({ page: 1, pageSize: 200 })
      if (res.code === 0) this.allPrograms = res.data.list
    },
    onProgramPicked() {
      this.selectedProgram = this.allPrograms.find((p) => p.programId === this.selectedProgramId) || null
      this.reload()
    },
    onPageChange(p) { if (this.pagination) { this.pagination.page = p; this.reload() } },

    async reload() {
      this.loading = true
      this.error = ''
      this.pagination = null
      try {
        if (this.tab === 'authoring') return await this.loadAuthoring()
        if (this.tab === 'versions') return await this.loadVersions()
        if (this.tab === 'planChange') return await this.loadPlanChange()
        if (this.tab === 'courseModules') return await this.loadCourseModules()
        if (this.tab === 'practicePlan') return await this.loadPracticePlan()
        if (this.tab === 'creditRequirements') return await this.loadCreditRequirements()
        if (this.tab === 'graduationRequirements') return await this.loadGraduationRequirements()
        if (this.tab === 'review') return await this.loadReview()
        if (this.tab === 'publish') return await this.loadPublish()
      } finally {
        this.loading = false
      }
    },
    async loadAuthoring() {
      const res = await academicAffairsApi.getPrograms({ statusIn: 'DRAFT,RETURNED', page: 1, pageSize: 100 })
      if (res.code === 0) this.rows = res.data.list.map((p) => ({ ...p, id: p.programId }))
      else this.error = res.message
    },
    async loadVersions() {
      const res = await academicAffairsApi.getPrograms({ page: 1, pageSize: 200 })
      if (res.code === 0) this.rows = res.data.list.map((p) => ({ ...p, id: p.programId }))
      else this.error = res.message
    },
    async loadPlanChange() {
      // 计划变更：仅已发布/启用/冻结/停用（canNewVersion 态）教学计划可发起变更
      const res = await academicAffairsApi.getPrograms({ statusIn: 'PUBLISHED,ENABLED,FROZEN,DISABLED', page: 1, pageSize: 200 })
      if (res.code === 0) this.rows = res.data.list.map((p) => ({ ...p, id: p.programId }))
      else this.error = res.message
    },
    async loadCourseModules() {
      if (!this.selectedProgramId) { this.rows = []; return }
      const res = await academicAffairsApi.getProgram(this.selectedProgramId)
      if (res.code === 0) {
        this.selectedProgram = res.data
        this.rows = (res.data.courses || []).map((c) => ({ ...c, id: c.programCourseId }))
      } else this.error = res.message
    },
    async loadPracticePlan() {
      // 实践教学计划：课程模块的「实践环节」筛选切面（module 命中集中实践/实训/实习关键词），
      // 交叉展示学分要求里「实践环节」模块的目标学分（同一 requirement_json，见施工记录 U-03 折中）。
      this.practiceCreditTarget = null
      if (!this.selectedProgramId) { this.rows = []; return }
      const res = await academicAffairsApi.getProgram(this.selectedProgramId)
      if (res.code === 0) {
        this.selectedProgram = res.data
        this.rows = (res.data.courses || [])
          .filter((c) => isPracticeModule(c.module))
          .map((c) => ({ ...c, id: c.programCourseId }))
      } else { this.error = res.message; return }
      const creditRes = await academicAffairsApi.getCreditRequirements(this.selectedProgramId)
      if (creditRes.code === 0) {
        const item = (creditRes.data.items || []).find((i) => isPracticeModule(i.module))
        this.practiceCreditTarget = item ? item.creditTarget : null
      }
    },
    async loadCreditRequirements() {
      if (!this.selectedProgramId) { this.rows = []; return }
      const res = await academicAffairsApi.getCreditRequirements(this.selectedProgramId)
      if (res.code === 0) {
        this.creditItems = res.data.items || []
        this.rows = this.creditItems.map((it, idx) => ({ ...it, id: 'cr-' + idx }))
      } else this.error = res.message
    },
    async loadGraduationRequirements() {
      if (!this.selectedProgramId) { this.rows = []; return }
      const res = await academicAffairsApi.getGraduationRequirements(this.selectedProgramId)
      if (res.code === 0) this.rows = (res.data.items || []).map((r) => ({ ...r, id: r.requirementId }))
      else this.error = res.message
    },
    async loadReview() {
      const res = await academicAffairsApi.getPrograms({ statusIn: 'COLLEGE_REVIEW,ACADEMIC_REVIEW', page: 1, pageSize: 100 })
      if (res.code === 0) this.rows = res.data.list.map((p) => ({ ...p, id: p.programId }))
      else this.error = res.message
    },
    async loadPublish() {
      const res = await academicAffairsApi.getPrograms({ statusIn: 'PUBLISHED,ENABLED', page: 1, pageSize: 100 })
      if (res.code === 0) this.rows = res.data.list.map((p) => ({ ...p, id: p.programId }))
      else this.error = res.message
    },

    // ── 新建方案 ──
    openCreate() {
      this.createForm = { programName: '', majorId: '', gradeYear: '', totalCredits: null }
      this.formError = ''
      this.createVisible = true
    },
    async submitCreate() {
      if (!this.createForm.programName) { this.formError = '方案名称必填'; return }
      this.saving = true
      const res = await academicAffairsApi.createProgram({
        programName: this.createForm.programName,
        majorId: this.createForm.majorId || undefined,
        gradeYear: this.createForm.gradeYear || undefined,
        totalCredits: this.createForm.totalCredits || undefined,
        requirement: {}
      })
      this.saving = false
      if (res.code === 0) {
        toast.success('方案已创建')
        this.createVisible = false
        await this.loadAllPrograms()
        this.reload()
      } else this.formError = res.message
    },

    // ── 方案版本 ──
    async doNewVersion(row) {
      const res = await academicAffairsApi.createProgramNewVersion(row.programId)
      if (res.code === 0) { toast.success('已新建版本 v' + res.data.version); await this.loadAllPrograms(); this.reload() }
      else toast.error(res.message || '新建版本失败')
    },

    // ── 计划变更（收编入口：同一版本链机制 + 强制变更原因留痕） ──
    openChange(row) {
      this.changeDlg = { visible: true, submitting: false, row }
    },
    async doChange(payload) {
      const reason = (payload && payload.reason) || ''
      this.changeDlg.submitting = true
      const res = await academicAffairsApi.changeProgram(this.changeDlg.row.programId, reason)
      this.changeDlg.submitting = false
      if (res.code === 0) {
        this.changeDlg.visible = false
        toast.success('变更已生效，已生成新版本 v' + res.data.version)
        await this.loadAllPrograms()
        this.reload()
      } else toast.error(res.message || '变更失败')
    },

    // ── 课程模块（practicePlan 复用同一套读写，presetModule 供「＋ 添加实践课程」预填模块名） ──
    openCourseForm(row, presetModule) {
      this.courseForm = row
        ? { programCourseId: row.programCourseId, courseName: row.courseName, module: row.module, openTermNo: row.openTermNo, credit: row.credit }
        : { programCourseId: '', courseName: '', module: presetModule || '', openTermNo: null, credit: null }
      this.formError = ''
      this.courseVisible = true
    },
    async submitCourse() {
      if (!this.courseForm.courseName) { this.formError = '课程名称必填'; return }
      this.saving = true
      const body = { courseName: this.courseForm.courseName, module: this.courseForm.module || undefined,
        openTermNo: this.courseForm.openTermNo || undefined, credit: this.courseForm.credit != null ? Math.round(this.courseForm.credit) : undefined }
      const res = this.courseForm.programCourseId
        ? await academicAffairsApi.updateProgramCourse(this.courseForm.programCourseId, body)
        : await academicAffairsApi.addProgramCourse(this.selectedProgramId, body)
      this.saving = false
      if (res.code === 0) { toast.success('已保存'); this.courseVisible = false; this.reload() } else this.formError = res.message
    },
    confirmDeleteCourse(row) {
      this.confirmDlg = { visible: true, title: `删除课程「${row.courseName}」？`, submitting: false, action: async () => {
        const res = await academicAffairsApi.deleteProgramCourse(row.programCourseId)
        if (res.code === 0) { toast.success('已删除'); this.reload() } else toast.error(res.message)
      } }
    },

    // ── 学分要求（本地数组，点「保存学分结构」统一持久化） ──
    openCreditForm(row) {
      this.creditForm = row
        ? { module: row.module, creditTarget: row.creditTarget, note: row.note || '', _editing: true, _origModule: row.module }
        : { module: '', creditTarget: 0, note: '', _editing: false, _origModule: '' }
      this.formError = ''
      this.creditVisible = true
    },
    submitCreditRow() {
      if (!this.creditForm.module) { this.formError = '课程模块必填'; return }
      if (this.creditForm._editing) {
        const idx = this.creditItems.findIndex((i) => i.module === this.creditForm._origModule)
        if (idx >= 0) this.creditItems.splice(idx, 1, { module: this.creditForm.module, creditTarget: Number(this.creditForm.creditTarget) || 0, note: this.creditForm.note })
      } else {
        if (this.creditItems.some((i) => i.module === this.creditForm.module)) { this.formError = '该模块已存在'; return }
        this.creditItems.push({ module: this.creditForm.module, creditTarget: Number(this.creditForm.creditTarget) || 0, note: this.creditForm.note })
      }
      this.rows = this.creditItems.map((it, idx) => ({ ...it, id: 'cr-' + idx }))
      this.creditVisible = false
    },
    removeCreditRow(row) {
      this.creditItems = this.creditItems.filter((i) => i.module !== row.module)
      this.rows = this.creditItems.map((it, idx) => ({ ...it, id: 'cr-' + idx }))
    },
    async saveCredit() {
      this.savingCredit = true
      const res = await academicAffairsApi.saveCreditRequirements(this.selectedProgramId, this.creditItems)
      this.savingCredit = false
      if (res.code === 0) toast.success('学分结构已保存（目标合计 ' + res.data.targetSum + '）')
      else toast.error(res.message || '保存失败')
    },

    // ── 毕业要求 ──
    openGradForm(row) {
      this.gradForm = row
        ? { requirementId: row.requirementId, category: row.category, content: row.content, sortOrder: row.sortOrder }
        : { requirementId: '', category: 'ABILITY', content: '', sortOrder: 0 }
      this.formError = ''
      this.gradVisible = true
    },
    async submitGrad() {
      if (!this.gradForm.content) { this.formError = '要求内容必填'; return }
      this.saving = true
      const body = { category: this.gradForm.category, content: this.gradForm.content, sortOrder: this.gradForm.sortOrder || 0 }
      const res = this.gradForm.requirementId
        ? await academicAffairsApi.updateGraduationRequirement(this.gradForm.requirementId, body)
        : await academicAffairsApi.createGraduationRequirement(this.selectedProgramId, body)
      this.saving = false
      if (res.code === 0) { toast.success('已保存'); this.gradVisible = false; this.reload() } else this.formError = res.message
    },
    confirmDeleteGrad(row) {
      this.confirmDlg = { visible: true, title: '删除该条毕业要求？', submitting: false, action: async () => {
        const res = await academicAffairsApi.deleteGraduationRequirement(row.requirementId)
        if (res.code === 0) { toast.success('已删除'); this.reload() } else toast.error(res.message)
      } }
    },

    // ── 方案审核 ──
    openReview(row, action) {
      this.reviewDlg = {
        visible: true, action, row,
        title: action === 'APPROVE' ? `审核通过「${row.programName}」` : `退回「${row.programName}」`,
        type: action === 'APPROVE' ? 'primary' : 'warning',
        confirmText: action === 'APPROVE' ? '确认通过' : '确认退回',
        requireReason: action === 'RETURN', submitting: false
      }
    },
    async doReview(payload) {
      const reason = (payload && payload.reason) || ''
      this.reviewDlg.submitting = true
      const res = await academicAffairsApi.reviewProgram(this.reviewDlg.row.programId, this.reviewDlg.action, reason)
      this.reviewDlg.submitting = false
      if (res.code === 0) { this.reviewDlg.visible = false; toast.success('已处理'); this.reload() }
      else toast.error(res.message || '处理失败')
    },

    // ── 方案发布 ──
    openBind(row) {
      this.bindRow = row
      this.bindForm = { gradeYear: '', classId: '' }
      this.formError = ''
      this.bindVisible = true
    },
    async submitBind() {
      if (!this.bindForm.gradeYear) { this.formError = '绑定年级必填'; return }
      this.saving = true
      const res = await academicAffairsApi.bindProgramGrade(this.bindRow.programId, this.bindForm.gradeYear, this.bindForm.classId || undefined)
      this.saving = false
      if (res.code === 0) { toast.success('已绑定'); this.bindVisible = false; this.reload() } else this.formError = res.message
    },
    async viewBindings(row) {
      this.bindingsVisible = true
      this.bindingRows = []
      const res = await academicAffairsApi.getProgramBindings(row.programId)
      if (res.code === 0) this.bindingRows = res.data.items || []
      else toast.error(res.message)
    },

    async onConfirmDelete() {
      this.confirmDlg.submitting = true
      const action = this.confirmDlg.action
      if (action) await action()
      this.confirmDlg.submitting = false
      this.confirmDlg.visible = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aapc-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-color, #e5e7eb); margin-bottom: 16px; flex-wrap: wrap; }
.aapc-tab { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; }
.aapc-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 600; }
.aapc-picker { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; flex-wrap: wrap; }
.aapc-picker__label { font-size: 13px; color: var(--text-500, #646a73); }
.aapc-picker__hint { font-size: 13px; color: var(--text-500, #646a73); display: inline-flex; align-items: center; gap: 6px; }
.aapc-bar { margin-bottom: 12px; display: flex; gap: 8px; flex-wrap: wrap; }
.aapc-form { display: flex; flex-direction: column; gap: 12px; }
.aapc-bindings { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
.aapc-bindings li { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--border-100, #f0f1f2); }
.mp-link.is-danger { color: var(--danger-600, #f53f3f); }
</style>
