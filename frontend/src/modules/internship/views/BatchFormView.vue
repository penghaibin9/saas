<template>
  <ModulePageShell
    class="ix-batch-form"
    :title="isEdit ? '编辑实习批次' : '新建实习批次'"
    :subtitle="pageSubtitle"
    watermark-purpose="实习批次管理"
  >
    <template #actions>
      <AppButton variant="ghost" @click="goBack">{{ isEdit ? '返回批次详情' : '返回批次列表' }}</AppButton>
    </template>

    <ErrorState v-if="contextError" :description="contextError" @retry="loadContext" />
    <ErrorState v-else-if="error" :description="error" @retry="init" />
    <LoadingState v-else-if="loading || contextLoading" />
    <div v-else class="mp-stack">
      <AppInlineAlert
        v-if="readonly"
        type="warning"
        title="当前批次不可编辑"
        :description="detail?.status !== 'DRAFT' && detail ? `当前为${detail.statusLabel}，可查看原有配置。` : '当前身份没有批次管理权限，可查看原有配置。'"
      />

      <div v-if="saveError" class="bf-save-error" role="alert">
        <strong>{{ saveError }}</strong>
        <p v-if="versionConflict">你的输入仍保留在本页。请先查看最新批次，再决定是否重新编辑；不会直接覆盖他人的修改。</p>
        <AppButton v-if="versionConflict" variant="secondary" @click="openLatest">查看最新批次</AppButton>
      </div>
      <div class="bf-layout">
      <aside class="bf-guide">
        <span class="bf-guide__label">填写批次安排</span>
        <nav aria-label="批次表单分区">
          <button v-for="section in formSections" :key="section.key" type="button"
            :aria-current="activeSection === section.key ? 'step' : undefined" @click="focusSection(section.key)">
            <span>{{ section.order }}</span>{{ section.label }}
          </button>
        </nav>
        <p>保存为草稿后，继续选择参与班级与学生。名单预览确认后，再启用批次。</p>
      </aside>
      <AppForm
        ref="batchForm"
        :model="form"
        :rules="formRules"
        class="bf-content"
        layout="vertical"
        @submit="onSubmit"
      >
        <!-- 基本信息 -->
        <section id="batch-basic" ref="basic" class="mp-card" tabindex="-1">
          <div class="mp-card__head"><h2 class="mp-card__title">基本信息</h2></div>
          <div class="mp-card__body">
            <div class="bf-grid">
              <AppFormItem label="批次名称" prop="batchName">
                <AppTextInput v-model="form.batchName" :disabled="readonly" placeholder="如：2026 届春季岗位实习" />
              </AppFormItem>
              <AppFormItem label="批次编号" prop="batchNo" :hint="isEdit ? '批次编号创建后不可修改' : '本校不重复的编号，如：INT-2026S'">
                <AppTextInput v-model="form.batchNo" :disabled="isEdit || readonly" placeholder="如：INT-2026S" />
              </AppFormItem>
              <AppFormItem label="学年" prop="academicYear">
                <AppTextInput v-model="form.academicYear" :disabled="readonly" placeholder="如：2025-2026" />
              </AppFormItem>
              <AppFormItem label="学期" prop="term">
                <AppTextInput v-model="form.term" :disabled="readonly" placeholder="如：第二学期" />
              </AppFormItem>
              <AppFormItem label="实习开始" prop="startDate">
                <AppDatePicker v-model="form.startDate" role="start" :end-value="form.endDate" :disabled="readonly" />
              </AppFormItem>
              <AppFormItem label="实习结束" prop="endDate">
                <AppDatePicker v-model="form.endDate" role="end" :start-value="form.startDate" :disabled="readonly" />
              </AppFormItem>
              <AppFormItem label="报名开始" prop="signupStartDate">
                <AppDatePicker v-model="form.signupStartDate" role="start" :end-value="form.signupEndDate" :disabled="readonly" />
              </AppFormItem>
              <AppFormItem label="报名结束" prop="signupEndDate">
                <AppDatePicker v-model="form.signupEndDate" role="end" :start-value="form.signupStartDate" :disabled="readonly" />
              </AppFormItem>
              <AppFormItem label="计划人数" prop="plannedCount">
                <AppNumberInput v-model="form.plannedCount" :min="0" :disabled="readonly" placeholder="0" />
              </AppFormItem>
              <AppFormItem class="bf-grid__full" label="备注" prop="remark">
                <AppTextarea v-model="form.remark" :rows="3" :disabled="readonly" placeholder="批次说明（可选）" />
              </AppFormItem>
            </div>
          </div>
        </section>

        <!-- 阶段配置：表单化（BUG-007），高级模式保留原 JSON 通道 -->
        <section id="batch-stages" ref="stages" class="mp-card" tabindex="-1">
          <div class="mp-card__head">
            <h2 class="mp-card__title">阶段安排</h2>
            <button type="button" class="bf-mode" @click="toggleAdvanced">
              {{ advancedJson ? '使用分组表单' : '高级配置' }}
            </button>
          </div>
          <div class="mp-card__body bf-json">
            <template v-if="!advancedJson">
              <div class="bf-rows">
                <div v-for="(s, i) in stageRows" :key="i" class="bf-row">
                  <AppFormItem :label="`阶段 ${i + 1}`"><AppTextInput v-model="s.name" :disabled="readonly" placeholder="如：岗前准备" /></AppFormItem>
                  <AppFormItem label="开始日期"><AppDatePicker v-model="s.startDate" :disabled="readonly" /></AppFormItem>
                  <AppFormItem label="结束日期"><AppDatePicker v-model="s.endDate" :disabled="readonly" /></AppFormItem>
                  <AppButton variant="text" :disabled="readonly" @click="removeStage(i)">删除</AppButton>
                </div>
                <p v-if="!stageRows.length" class="bf-preview__note">使用系统现有三个阶段：岗前准备、在岗实习、总结考核。可按本轮安排添加具体日期。</p>
                <AppButton variant="secondary" size="sm" :disabled="readonly" @click="addStage">＋ 添加阶段</AppButton>
                <p v-if="stageFormError" class="bf-preview__err">{{ stageFormError }}</p>
              </div>
            </template>
            <AppFormItem
              v-else
              label="阶段时间轴"
              prop="stagesJson"
              :error="stagesError"
              hint='JSON 数组，形如 [{"code":"PREP","name":"岗前准备","startDate":"","endDate":""}]'
            >
              <AppTextarea
                v-model="form.stagesJson"
                class="bf-code"
                :rows="10"
                :disabled="readonly"
                :status="stagesError ? 'error' : 'default'"
                placeholder='[{"code":"PREP","name":"岗前准备","startDate":"","endDate":""}]'
              />
            </AppFormItem>
            <div v-if="advancedJson" class="bf-preview">
              <div class="bf-preview__title">解析预览</div>
              <p v-if="advancedJson && stagesParsed.empty" class="bf-preview__note">留空提交时将使用默认三阶段：岗前准备 / 在岗实习 / 总结考核</p>
              <p v-else-if="advancedJson && stagesError" class="bf-preview__err">{{ stagesError }}</p>
              <AppTimeline v-else :items="stagePreviewItems" />
            </div>
          </div>
        </section>

        <!-- 规则配置：表单化（BUG-007），6 个规则菜单在此有真正可用的配置界面 -->
        <section id="batch-rules" ref="rules" class="mp-card" tabindex="-1">
          <div class="mp-card__head">
            <h2 class="mp-card__title">业务规则</h2>
            <span class="bf-aside">采用现有配置，请按学校本轮要求核对</span>
          </div>
          <div class="mp-card__body bf-json">
            <div v-if="!advancedJson" class="bf-rules">
              <div class="bf-rules__grp">
                <div class="bf-rules__t">打卡规则</div>
                <AppFormItem label="每日必打卡">
                  <AppRadioGroup v-model="rulesForm.checkin.requireDaily" :options="boolOptions" :disabled="readonly" />
                </AppFormItem>
                <AppFormItem label="电子围栏半径（米）">
                  <AppNumberInput v-model="rulesForm.checkin.geofenceRadiusM" :min="50" :max="5000" :step="50" :disabled="readonly" />
                </AppFormItem>
                <AppFormItem label="最大定位误差（米）" hint="超过该误差时转教师核验，不直接判定正常或超范围">
                  <AppNumberInput v-model="rulesForm.checkin.maxAccuracyM" :min="20" :max="2000" :step="10" :disabled="readonly" />
                </AppFormItem>
              </div>

              <div class="bf-rules__grp">
                <div class="bf-rules__t">周报规则</div>
                <AppFormItem label="提交频率">
                  <AppSelect v-model="rulesForm.weeklyReport.frequency" :options="frequencyOptions" :disabled="readonly" />
                </AppFormItem>
                <AppFormItem label="正文最少字数">
                  <AppNumberInput v-model="rulesForm.weeklyReport.minWordCount" :min="0" :max="5000" :step="100" :disabled="readonly" />
                </AppFormItem>
                <AppFormItem label="截止（周几前）">
                  <AppSelect v-model="rulesForm.weeklyReport.deadlineWeekday" :options="weekdayOptions" :disabled="readonly" />
                </AppFormItem>
              </div>

              <div class="bf-rules__grp">
                <div class="bf-rules__t">指导规则</div>
                <AppFormItem label="每学期最少巡访次数">
                  <AppNumberInput v-model="rulesForm.guidance.minVisitsPerTerm" :min="0" :max="50" :disabled="readonly" />
                </AppFormItem>
                <AppFormItem label="每月最少沟通次数">
                  <AppNumberInput v-model="rulesForm.guidance.minCommunicationsPerMonth" :min="0" :max="50" :disabled="readonly" />
                </AppFormItem>
              </div>

              <div class="bf-rules__grp">
                <div class="bf-rules__t">评价权重（合计须为 100%）</div>
                <AppFormItem label="企业评价 %">
                  <AppNumberInput v-model="rulesForm.evaluation.enterpriseWeight" :min="0" :max="100" :disabled="readonly" />
                </AppFormItem>
                <AppFormItem label="教师评价 %">
                  <AppNumberInput v-model="rulesForm.evaluation.teacherWeight" :min="0" :max="100" :disabled="readonly" />
                </AppFormItem>
                <AppFormItem label="学生自评 %">
                  <AppNumberInput v-model="rulesForm.evaluation.selfWeight" :min="0" :max="100" :disabled="readonly" />
                </AppFormItem>
                <p :class="evalWeightSum === 100 ? 'bf-preview__note' : 'bf-preview__err'">
                  当前合计 {{ evalWeightSum }}%
                </p>
              </div>

              <div class="bf-rules__grp">
                <div class="bf-rules__t">成绩规则</div>
                <AppFormItem label="及格线">
                  <AppNumberInput v-model="rulesForm.score.passThreshold" :min="0" :max="100" :disabled="readonly" />
                </AppFormItem>
                <div class="bf-rows">
                  <div v-for="(c, i) in rulesForm.score.components" :key="i" class="bf-row bf-row--score">
                    <AppTextInput v-model="c.name" :disabled="readonly" placeholder="构成项名称" />
                    <AppNumberInput v-model="c.weight" :min="0" :max="100" :disabled="readonly" placeholder="权重 %" />
                    <AppButton variant="text" :disabled="readonly" @click="removeComponent(i)">删除</AppButton>
                  </div>
                  <AppButton variant="secondary" size="sm" :disabled="readonly" @click="addComponent">＋ 添加成绩构成项</AppButton>
                  <p :class="componentWeightSum === 100 ? 'bf-preview__note' : 'bf-preview__err'">
                    成绩构成合计 {{ componentWeightSum }}%（须为 100%）
                  </p>
                </div>
              </div>

              <div class="bf-rules__grp">
                <div class="bf-rules__t">上岗前置（未满足则不允许「上岗」）</div>
                <AppFormItem label="须三方协议生效">
                  <AppRadioGroup v-model="rulesForm.onboard.requireAgreement" :options="boolOptions" :disabled="readonly" />
                </AppFormItem>
                <AppFormItem label="须实习保险核验">
                  <AppRadioGroup v-model="rulesForm.onboard.requireInsurance" :options="boolOptions" :disabled="readonly" />
                </AppFormItem>
                <AppFormItem label="须分配校内指导教师">
                  <AppRadioGroup v-model="rulesForm.onboard.requireAdvisor" :options="boolOptions" :disabled="readonly" />
                </AppFormItem>
              </div>
            </div>
            <AppFormItem
              v-else
              label="规则 JSON"
              prop="rulesJson"
              :error="rulesError"
              hint='JSON 对象，形如 {"checkin":{"geofenceRadiusM":500}}，未填写的分组沿用原有/默认规则'
            >
              <AppTextarea
                v-model="form.rulesJson"
                class="bf-code"
                :rows="10"
                :disabled="readonly"
                :status="rulesError ? 'error' : 'default'"
                placeholder='{"checkin":{"requireDaily":true,"geofenceRadiusM":500}}'
              />
            </AppFormItem>
            <div v-if="advancedJson" class="bf-preview">
              <div class="bf-preview__title">解析预览</div>
              <p v-if="rulesParsed.empty" class="bf-preview__note">留空提交时将沿用原有/默认规则（打卡、周报、指导、评价、成绩）</p>
              <p v-else-if="rulesError" class="bf-preview__err">{{ rulesError }}</p>
              <AppDescriptionList v-else :items="rulesPreviewItems" :columns="1" size="compact" label-width="150px" />
            </div>
          </div>
        </section>

        <AppSubmitBar
          :loading="submitting"
          :disabled="readonly || versionConflict"
          :submit-text="isEdit ? '保存修改' : '保存并配置名单'"
          cancel-text="取消"
          @submit="onSubmit"
          @cancel="goBack"
        />
      </AppForm>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 实习批次表单独立页（新建 + 编辑一体）。
 * 路由（由主流程挂载，本文件不改 routes.js）：
 *   /admin/internship/batches/new       → 新建（草稿态）
 *   /admin/internship/batches/:id/edit  → 编辑（仅 DRAFT 可编辑，其余状态只读预览，后端最终拦截）
 * 提交走真实 internshipApi.createBatch / updateBatch；stagesJson / rulesJson 为带 JSON 校验的
 * 文本字段 + 真实解析预览（阶段→只读时间轴，规则→键值列表），不做假结构编辑器。
 */
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import {
  AppInlineAlert, AppForm, AppFormItem, AppTextInput, AppNumberInput, AppTextarea,
  AppSubmitBar, AppDatePicker, AppTimeline, AppDescriptionList, AppSelect, AppRadioGroup
} from '@/components/common'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { toast } from '@/utils/toast'
import { formatDate } from '@/utils/dateUtils'
import { withInternshipBatch, internshipBatchListReturn } from '../navigation.js'

const RULE_LABELS = {
  checkin: '打卡', weeklyReport: '周报', guidance: '指导', evaluation: '评价', score: '成绩',
  requireDaily: '每日必打卡', geofenceRadiusM: '电子围栏半径（米）', maxAccuracyM: '最大定位误差（米）', frequency: '提交频率',
  minWordCount: '正文最少字数', deadlineWeekday: '截止（周几前）',
  minVisitsPerTerm: '每学期最少巡访次数', minCommunicationsPerMonth: '每月最少沟通次数',
  enterpriseWeight: '企业评价权重', teacherWeight: '教师评价权重', selfWeight: '学生自评权重',
  passThreshold: '及格线', components: '成绩构成'
}
const FREQUENCY_LABEL = { WEEKLY: '每周 1 次', BIWEEKLY: '每两周 1 次' }

const blankForm = () => ({
  batchName: '', batchNo: '', academicYear: '', term: '',
  startDate: '', endDate: '', signupStartDate: '', signupEndDate: '',
  plannedCount: 0, remark: '', stagesJson: '', rulesJson: ''
})

/** 规则表单默认值（与后端 internship_service.DEFAULT_RULES 对齐；权重以百分数呈现）。 */
const blankRulesForm = () => ({
  checkin: { requireDaily: true, geofenceRadiusM: 500, maxAccuracyM: 200 },
  weeklyReport: { frequency: 'WEEKLY', minWordCount: 800, deadlineWeekday: 7 },
  guidance: { minVisitsPerTerm: 2, minCommunicationsPerMonth: 2 },
  evaluation: { enterpriseWeight: 40, teacherWeight: 40, selfWeight: 20 },
  score: {
    passThreshold: 60,
    components: [
      { name: '企业评价', weight: 40 },
      { name: '教师评价', weight: 40 },
      { name: '考核成绩', weight: 20 }
    ]
  },
  onboard: { requireAgreement: true, requireInsurance: true, requireAdvisor: true }
})

const BOOL_OPTIONS = [{ label: '是', value: true }, { label: '否', value: false }]
const FREQUENCY_OPTIONS = [
  { label: '每周 1 次', value: 'WEEKLY' },
  { label: '每两周 1 次', value: 'BIWEEKLY' }
]
const WEEKDAY_OPTIONS = [1, 2, 3, 4, 5, 6, 7].map((d) => ({
  label: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][d - 1], value: d
}))

/** 0~1 的小数权重转百分数；已是百分数（>1）则原样保留。 */
function toPercent(v, fallback) {
  const n = Number(v)
  if (!Number.isFinite(n)) return fallback
  return n <= 1 ? Math.round(n * 100) : Math.round(n)
}

export default {
  name: 'BatchFormView',
  components: {
    ModulePageShell, LoadingState, ErrorState, AppButton,
    AppInlineAlert, AppForm, AppFormItem, AppTextInput, AppNumberInput, AppTextarea,
    AppSubmitBar, AppDatePicker, AppTimeline, AppDescriptionList, AppSelect, AppRadioGroup
  },
  data() {
    return {
      ctx: null,
      contextLoading: true,
      contextError: '',
      loading: false,
      error: '',
      saveError: '',
      versionConflict: false,
      activeSection: 'basic',
      submitting: false,
      detail: null,
      form: blankForm(),
      // BUG-007：阶段/规则改为真实表单，advancedJson 保留原 JSON 通道（不删能力）
      advancedJson: false,
      stageRows: [],
      rulesForm: blankRulesForm(),
      boolOptions: BOOL_OPTIONS,
      frequencyOptions: FREQUENCY_OPTIONS,
      weekdayOptions: WEEKDAY_OPTIONS
    }
  },
  computed: {
    formSections() { return [
      { key: 'basic', label: '基本信息', order: '01' },
      { key: 'stages', label: '阶段安排', order: '02' },
      { key: 'rules', label: '业务规则', order: '03' }
    ] },
    evalWeightSum() {
      const e = this.rulesForm.evaluation
      return Number(e.enterpriseWeight || 0) + Number(e.teacherWeight || 0) + Number(e.selfWeight || 0)
    },
    componentWeightSum() {
      return (this.rulesForm.score.components || []).reduce((s, c) => s + Number(c.weight || 0), 0)
    },
    stageFormError() {
      const rows = this.stageRows.filter((s) => (s.name || '').trim() || (s.code || '').trim())
      if (rows.some((s) => !(s.name || '').trim())) return '每个阶段都必须填写阶段名称'
      if (rows.some((s) => s.startDate && s.endDate && s.startDate > s.endDate)) {
        return '阶段的开始日期不能晚于结束日期'
      }
      return ''
    },
    isEdit() {
      return !!this.$route.params.id
    },
    isFormRoute() {
      const p = this.$route.path
      return p.endsWith('/new') || p.endsWith('/edit')
    },
    roleName() {
      return this.ctx?.currentRole?.roleName || ''
    },
    dataScopeName() {
      return this.ctx?.dataScope?.name || ''
    },
    readonly() {
      return this.ctx?.permissionActions?.createBatch?.allowed !== true || (this.isEdit && !!this.detail && this.detail.status !== 'DRAFT')
    },
    pageSubtitle() {
      if (this.isEdit) {
        return this.detail ? `${this.detail.batchName}（${this.detail.batchNo}）` : ''
      }
      return '填写周期和本轮规则，保存为草稿后继续配置参与名单。'
    },
    formRules() {
      const rules = {
        batchName: [{ required: true, message: '批次名称为必填项' }],
        startDate: [{ required: true, message: '请选择实习开始日期' }],
        endDate: [{ required: true, message: '请选择实习结束日期' }]
      }
      if (!this.isEdit) rules.batchNo = [{ required: true, message: '批次编号为必填项' }]
      return rules
    },
    stagesParsed() {
      const text = (this.form.stagesJson || '').trim()
      if (!text) return { empty: true, data: null, error: '' }
      let data
      try {
        data = JSON.parse(text)
      } catch (e) {
        return { empty: false, data: null, error: `JSON 解析失败：${e.message}` }
      }
      if (!Array.isArray(data)) return { empty: false, data: null, error: '阶段时间轴需为 JSON 数组（[ ... ]）' }
      if (!data.every((s) => s && typeof s === 'object' && !Array.isArray(s))) {
        return { empty: false, data: null, error: '数组每一项需为阶段对象（含 code / name / startDate / endDate）' }
      }
      return { empty: false, data, error: '' }
    },
    stagesError() {
      return this.stagesParsed.error
    },
    stagePreviewItems() {
      const stages = this.advancedJson
        ? (this.stagesParsed.data || [])
        : this.stageRows.filter((s) => (s.name || '').trim())
      return stages.map((s, i) => ({
        id: s.code || `stage-${i}`,
        title: s.name || s.code || `阶段 ${i + 1}`,
        type: 'primary',
        time: (s.startDate || s.endDate)
          ? `${this.dateShort(s.startDate) || '—'} ~ ${this.dateShort(s.endDate) || '—'}`
          : '未设置具体日期'
      }))
    },
    rulesParsed() {
      const text = (this.form.rulesJson || '').trim()
      if (!text) return { empty: true, data: null, error: '' }
      let data
      try {
        data = JSON.parse(text)
      } catch (e) {
        return { empty: false, data: null, error: `JSON 解析失败：${e.message}` }
      }
      if (!data || typeof data !== 'object' || Array.isArray(data)) {
        return { empty: false, data: null, error: '规则配置需为 JSON 对象（{ ... }）' }
      }
      return { empty: false, data, error: '' }
    },
    rulesError() {
      return this.rulesParsed.error
    },
    rulesPreviewItems() {
      return this.flattenRules(this.rulesParsed.data || {})
    }
  },
  watch: {
    '$route.params.id'() {
      // 同组件在 /new 与 /:id/edit 间切换时重新初始化；离开表单路由时跳过
      if (!this.isFormRoute) return
      this.detail = null
      this.init()
    }
  },
  created() {
    this.loadContext()
    this.init()
  },
  methods: {
    async loadContext() {
      this.contextLoading = true; this.contextError = ''; this.ctx = null
      try {
        const res = await internshipApi.getContext()
        if (res.code !== 0) throw new Error(res.message || '批次权限加载失败，请重试')
        this.ctx = res.data
      } catch (error) {
        this.contextError = error.message || '批次权限加载失败，请重试'
      } finally { this.contextLoading = false }
    },
    focusSection(section) {
      this.activeSection = section
      this.$refs[section]?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      this.$refs[section]?.focus({ preventScroll: true })
    },
    toggleAdvanced() {
      if (!this.advancedJson) {
        this.form.stagesJson = JSON.stringify(this.stageRows, null, 2)
        this.form.rulesJson = JSON.stringify(this.buildRulesFromForm(), null, 2)
        this.advancedJson = true
      } else {
        if (this.stagesError || this.rulesError) return toast.error('请先修正高级配置中的格式错误')
        this.fillStructured({ stages: this.stagesParsed.data || [], rules: this.rulesParsed.data || {} })
        this.advancedJson = false
      }
    },
    detailLocation(id, section = this.$route.query?.setup) {
      const location = withInternshipBatch(`/admin/internship/batches/${id}`, id)
      if (this.$route.query?.returnTo) location.query.returnTo = this.$route.query.returnTo
      if (section) location.query.setup = section
      return location
    },
    openLatest() { this.$router.push(this.detailLocation(this.detail.id)) },
    dateShort(v) {
      return formatDate(v, '')
    },
    addStage() {
      window.__SAAS_DIRTY_FORM_GUARD__?.markDirty()
      this.stageRows.push({ code: '', name: '', startDate: '', endDate: '' })
    },
    removeStage(i) {
      window.__SAAS_DIRTY_FORM_GUARD__?.markDirty()
      this.stageRows.splice(i, 1)
    },
    addComponent() {
      window.__SAAS_DIRTY_FORM_GUARD__?.markDirty()
      this.rulesForm.score.components.push({ name: '', weight: 0 })
    },
    removeComponent(i) {
      window.__SAAS_DIRTY_FORM_GUARD__?.markDirty()
      this.rulesForm.score.components.splice(i, 1)
    },
    /** 把后端返回的 stages / rules 回填到结构化表单（权重统一转百分数）。 */
    fillStructured(d) {
      this.stageRows = Array.isArray(d.stages)
        ? d.stages.map((s) => ({
          code: s.code || '', name: s.name || '',
          startDate: this.dateShort(s.startDate), endDate: this.dateShort(s.endDate)
        }))
        : []
      const base = blankRulesForm()
      const r = d.rules || {}
      this.rulesForm = {
        checkin: { ...base.checkin, ...(r.checkin || {}) },
        weeklyReport: { ...base.weeklyReport, ...(r.weeklyReport || {}) },
        guidance: { ...base.guidance, ...(r.guidance || {}) },
        evaluation: {
          enterpriseWeight: toPercent(r.evaluation?.enterpriseWeight, base.evaluation.enterpriseWeight),
          teacherWeight: toPercent(r.evaluation?.teacherWeight, base.evaluation.teacherWeight),
          selfWeight: toPercent(r.evaluation?.selfWeight, base.evaluation.selfWeight)
        },
        score: {
          passThreshold: Number(r.score?.passThreshold ?? base.score.passThreshold),
          components: Array.isArray(r.score?.components) && r.score.components.length
            ? r.score.components.map((c) => ({ name: c.name || '', weight: toPercent(c.weight, 0) }))
            : base.score.components
        },
        onboard: { ...base.onboard, ...(r.onboard || {}) }
      }
    },
    /** 结构化表单 → 后端 rules 结构（百分数还原为 0~1 小数）。 */
    buildRulesFromForm() {
      const f = this.rulesForm
      return {
        checkin: {
          requireDaily: !!f.checkin.requireDaily,
          geofenceRadiusM: Number(f.checkin.geofenceRadiusM || 0),
          maxAccuracyM: Number(f.checkin.maxAccuracyM || 200)
        },
        weeklyReport: {
          frequency: f.weeklyReport.frequency,
          minWordCount: Number(f.weeklyReport.minWordCount || 0),
          deadlineWeekday: Number(f.weeklyReport.deadlineWeekday || 7)
        },
        guidance: {
          minVisitsPerTerm: Number(f.guidance.minVisitsPerTerm || 0),
          minCommunicationsPerMonth: Number(f.guidance.minCommunicationsPerMonth || 0)
        },
        evaluation: {
          enterpriseWeight: Number(f.evaluation.enterpriseWeight || 0) / 100,
          teacherWeight: Number(f.evaluation.teacherWeight || 0) / 100,
          selfWeight: Number(f.evaluation.selfWeight || 0) / 100
        },
        score: {
          passThreshold: Number(f.score.passThreshold || 0),
          components: (f.score.components || [])
            .filter((c) => (c.name || '').trim())
            .map((c) => ({ name: c.name.trim(), weight: Number(c.weight || 0) / 100 }))
        },
        onboard: {
          requireAgreement: !!f.onboard.requireAgreement,
          requireInsurance: !!f.onboard.requireInsurance,
          requireAdvisor: !!f.onboard.requireAdvisor
        }
      }
    },
    pct(v) {
      return `${Math.round((v || 0) * 100)}%`
    },
    goBack() {
      this.$router.push(this.isEdit
        ? this.detailLocation(this.$route.params.id)
        : internshipBatchListReturn(this.$route.query, this.$route.query?.batchId))
    },
    async init() {
      this.error = ''
      this.saveError = ''
      this.versionConflict = false
      if (!this.isEdit) {
        this.detail = null
        this.form = blankForm()
        this.stageRows = []
        this.rulesForm = blankRulesForm()
        this.advancedJson = false
        this.loading = false
        return
      }
      this.loading = true
      const id = this.$route.params.id
      const res = await internshipApi.getBatchDetail(id)
      if (id !== this.$route.params.id) return
      this.loading = false
      if (res.code !== 0) {
        this.error = res.message || '批次不存在或无权查看'
        return
      }
      const d = res.data
      this.detail = d
      this.form = {
        batchName: d.batchName || '',
        batchNo: d.batchNo || '',
        academicYear: d.academicYear || '',
        term: d.term || '',
        startDate: this.dateShort(d.startDate),
        endDate: this.dateShort(d.endDate),
        signupStartDate: this.dateShort(d.signupStartDate),
        signupEndDate: this.dateShort(d.signupEndDate),
        plannedCount: d.plannedCount || 0,
        remark: d.remark || '',
        stagesJson: Array.isArray(d.stages) && d.stages.length ? JSON.stringify(d.stages, null, 2) : '',
        rulesJson: d.rules ? JSON.stringify(d.rules, null, 2) : ''
      }
      this.fillStructured(d)
      await this.$nextTick()
      if (this.formSections.some((section) => section.key === this.$route.query.section)) this.focusSection(this.$route.query.section)
    },
    flattenRules(obj, path = []) {
      const rows = []
      Object.keys(obj || {}).forEach((k) => {
        const v = obj[k]
        if (v && typeof v === 'object' && !Array.isArray(v)) {
          rows.push(...this.flattenRules(v, [...path, k]))
        } else {
          rows.push({
            label: [...path, k].map((seg) => RULE_LABELS[seg] || seg).join(' · '),
            value: this.formatRuleValue(k, v)
          })
        }
      })
      return rows
    },
    formatRuleValue(key, v) {
      if (typeof v === 'boolean') return v ? '是' : '否'
      if (Array.isArray(v)) {
        if (v.length && v.every((it) => it && typeof it === 'object' && it.name)) {
          return v
            .map((it) => (typeof it.weight === 'number' ? `${it.name} ${this.pct(it.weight)}` : String(it.name)))
            .join(' + ')
        }
        return JSON.stringify(v)
      }
      if (v === null || v === undefined || v === '') return '未设置'
      if (key === 'frequency') return FREQUENCY_LABEL[v] || String(v)
      if (/Weight$/.test(key) && typeof v === 'number' && v <= 1) return this.pct(v)
      return String(v)
    },
    async onSubmit() {
      if (this.readonly || this.submitting || this.versionConflict) return
      this.saveError = ''
      const { valid } = await this.$refs.batchForm.validate()
      if (!valid) { this.focusSection('basic'); return }
      if (this.advancedJson) {
        if (this.stagesError) return toast.error('阶段时间轴 JSON 配置有误，请先修正')
        if (this.rulesError) return toast.error('规则配置 JSON 配置有误，请先修正')
      } else {
        if (this.stageFormError) { this.focusSection('stages'); return toast.error(this.stageFormError) }
        if (this.evalWeightSum !== 100) { this.focusSection('rules'); return toast.error(`评价权重合计须为 100%，当前 ${this.evalWeightSum}%`) }
        if (this.componentWeightSum !== 100) { this.focusSection('rules'); return toast.error(`成绩构成权重合计须为 100%，当前 ${this.componentWeightSum}%`) }
      }
      const f = this.form
      const body = {
        batchName: (f.batchName || '').trim(),
        academicYear: f.academicYear || '',
        term: f.term || '',
        startDate: f.startDate || '',
        endDate: f.endDate || '',
        signupStartDate: f.signupStartDate || '',
        signupEndDate: f.signupEndDate || '',
        plannedCount: Number(f.plannedCount || 0),
        remark: f.remark || ''
      }
      if (!this.isEdit) body.batchNo = (f.batchNo || '').trim()
      else {
        // 后端 update_batch 强制乐观锁；版本来自进入编辑页时的详情
        const ver = this.detail?.version
        if (ver === undefined || ver === null || ver === '') {
          toast.error('缺少批次版本号，请刷新后重试')
          return
        }
        body.expectedVersion = Number(ver)
      }
      if (this.advancedJson) {
        if (!this.stagesParsed.empty) body.stages = this.stagesParsed.data
        if (!this.rulesParsed.empty) body.rules = this.rulesParsed.data
      } else {
        const stages = this.stageRows
          .filter((s) => (s.name || '').trim())
          .map((s, i) => ({
            code: (s.code || '').trim() || `STAGE${i + 1}`,
            name: s.name.trim(),
            startDate: s.startDate || '',
            endDate: s.endDate || ''
          }))
        if (stages.length) body.stages = stages
        body.rules = this.buildRulesFromForm()
      }
      this.submitting = true
      try {
        const res = this.isEdit
          ? await internshipApi.updateBatch(this.$route.params.id, body)
          : await internshipApi.createBatch(body)
        if (res.code === 0) {
          window.__SAAS_DIRTY_FORM_GUARD__?.markSaved()
          if (this.isEdit) {
            toast.success('已保存修改')
            this.goBack()
          } else {
            toast.success('批次已创建，请继续选择参与班级与学生')
            this.$router.push(this.detailLocation(res.data.id, 'participants'))
          }
        } else {
          this.saveError = res.message || '保存失败，请重试，已填写内容仍保留。'
          this.versionConflict = this.isEdit && (Number(res.code) === 409001 || /已被其他用户修改|DATA_CONFLICT/.test(String(res.message || '')))
        }
      } catch (e) {
        this.saveError = e.message || '保存失败，请重试，已填写内容仍保留。'
      } finally {
        this.submitting = false
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.bf-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-1) var(--space-6);
}
.bf-grid__full {
  grid-column: 1 / -1;
}
.bf-json {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr);
  gap: var(--space-5);
  align-items: start;
}
.bf-aside {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.bf-code :deep(textarea) {
  font-family: 'JetBrains Mono', Consolas, Menlo, monospace;
  font-size: 12.5px;
  line-height: 1.7;
}
.bf-preview {
  border: 1px solid var(--border-light);
  border-radius: 10px;
  background: var(--bg-subtle, #f8fafc);
  padding: var(--space-3) var(--space-4);
}
.bf-preview__title {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}
.bf-preview__note {
  margin: 0;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.bf-preview__err {
  margin: 0;
  font-size: var(--font-size-xs);
  color: var(--danger-600);
  word-break: break-all;
}
/* 阶段/规则表单化（BUG-007） */
.bf-mode {
  margin-left: auto;
  border: 0;
  background: none;
  padding: 0;
  color: var(--primary-600);
  cursor: pointer;
  font-size: var(--font-size-xs);
}
.bf-rows {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  align-items: flex-start;
}
.bf-row {
  display: grid;
  grid-template-columns: 1.4fr 0.8fr 1fr 1fr auto;
  gap: var(--space-2);
  width: 100%;
  align-items: center;
}
.bf-row--score {
  grid-template-columns: 1.4fr 0.8fr auto;
}
.bf-rules {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
}
.bf-rules__grp {
  border: 1px solid var(--border-light);
  border-radius: 10px;
  padding: var(--space-3) var(--space-4);
}
.bf-rules__t {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}
@media (max-width: 960px) {
  .bf-grid,
  .bf-json,
  .bf-rules {
    grid-template-columns: 1fr;
  }
  .bf-row,
  .bf-row--score {
    grid-template-columns: 1fr;
  }
}

.bf-layout { display: grid; grid-template-columns: 156px minmax(0, 1fr); gap: 22px; align-items: start; }
.bf-guide { position: sticky; top: 170px; padding-top: 8px; }
.bf-guide__label { font-size: 12px; color: var(--t3); display: block; margin: 0 0 12px 10px; }
.bf-guide nav { display: grid; gap: 4px; }
.bf-guide button { display: flex; align-items: center; gap: 12px; background: transparent; border: 0; border-radius: 5px; padding: 12px 10px; text-align: left; font: inherit; font-size: 13px; color: var(--t2); cursor: pointer; }
.bf-guide button span { color: var(--t3); font-size: 11px; }
.bf-guide button[aria-current] { color: var(--pri); background: var(--pri-bg); font-weight: 600; }
.bf-guide p { color: var(--t3); margin: 18px 10px; font-size: 12px; line-height: 1.8; }
.bf-content { display: grid; gap: 18px; min-width: 0; }
.bf-content section { scroll-margin-top: 170px; }
.bf-content h2 { margin: 0; font-size: 15px; }
.bf-content .bf-json { grid-template-columns: 1fr; }
.bf-content .bf-grid { gap: 12px 24px; }
.bf-content .bf-row { grid-template-columns: minmax(100px, 1.2fr) repeat(2, minmax(110px, 1fr)) auto; align-items: end; }
.bf-content .bf-row--score { grid-template-columns: 1.4fr 0.8fr auto; align-items: center; }
.bf-content .bf-rules__grp { border: 0; border-top: 1px solid var(--card-b); border-radius: 0; padding: 16px 0 0; }
.bf-content .bf-rules { gap: 24px; }
.bf-rules__t { font-size: 14px; color: var(--t1); }
.bf-save-error { padding: 14px 18px; border: 1px solid var(--danger-200); background: var(--danger-50); color: var(--danger-700); font-size: 13px; line-height: 1.7; border-radius: 6px; }
@media (max-width: 1080px) { .bf-layout { grid-template-columns: 1fr; } .bf-guide { position: static; padding: 0; } .bf-guide nav { display: flex; } .bf-guide p, .bf-guide__label { display: none; } }
@media (max-width: 800px) { .bf-content .bf-row { grid-template-columns: 1fr; } }

</style>
