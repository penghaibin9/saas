<template>
  <ModulePageShell
    :title="isEdit ? '编辑岗位' : '新增岗位'"
    :subtitle="pageSubtitle"
    watermark-purpose="岗位库维护"
  >
    <template #actions>
      <AppButton variant="ghost" @click="goBack">{{ isEdit ? '返回岗位详情' : '返回岗位库' }}</AppButton>
    </template>

    <ErrorState v-if="error" :description="error" @retry="init" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-stack">
      <AppInlineAlert
        v-if="readonly"
        type="warning"
        title="当前岗位只读"
        description="已归档岗位或当前身份没有维护权限，可查看已有资料。"
      />

      <AppForm
        ref="posForm"
        :model="form"
        :rules="formRules"
        layout="vertical"
        label-width="112px"
        @submit="onSubmit"
      >
        <!-- 基本信息 -->
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">基本信息</span>
            <span class="pf-aside">所属批次：{{ detail?.batchName || batchStore.selectedBatch?.batchName || '当前所选批次' }}</span>
          </div>
          <div class="mp-card__body">
            <div class="pf-grid">
              <!-- Picker 不包裸 label：label 激活会把点击转发给选择器内部按钮 -->
              <AppFormItem
                class="pf-grid__full"
                label="所属企业"
                prop="companyId"
                :required="!isEdit"
                :hint="isEdit ? '编辑岗位时不可更换所属企业' : ''"
              >
                <AppInternshipEnterprisePicker
                  v-model="form.companyId"
                  :options="companyPresetOpts"
                  :disabled="isEdit || readonly || submitting"
                  disabled-reason="编辑岗位时不可更换所属企业"
                  placeholder="输入企业名称搜索"
                  search-placeholder="按企业名称搜索"
                  data-scope-hint="仅合作企业 · 黑名单/非合作中企业上架时由后端拦截"
                  @update:model-value="onCompanyChange"
                />
              </AppFormItem>
              <AppFormItem label="岗位名称" prop="title" required v-slot="{ id }">
                <AppTextInput :id="id" v-model="form.title" :disabled="readonly || submitting" placeholder="如：Java开发实习生 / 市场营销实习生 / 化工工艺实习生" />
              </AppFormItem>
              <AppFormItem label="容量" prop="headcount" required :hint="isEdit && detail ? `已分配 ${detail.allocatedCount} 人，容量不能低于已分配数` : ''" v-slot="{ id }">
                <AppNumberInput :id="id" v-model="form.headcount" :min="1" :disabled="readonly || submitting" @clamp="onHeadcountClamp" />
              </AppFormItem>
            </div>
          </div>
        </section>

        <!-- 岗位要求 -->
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">岗位要求</span></div>
          <div class="mp-card__body">
            <div class="pf-grid">
              <AppFormItem label="专业要求" prop="majorRequirement" v-slot="{ id }">
                <AppTextInput :id="id" v-model="form.majorRequirement" :disabled="readonly || submitting" placeholder="不填=不限" />
              </AppFormItem>
              <AppFormItem label="年级要求" prop="gradeRequirement" v-slot="{ id }">
                <AppTextInput :id="id" v-model="form.gradeRequirement" :disabled="readonly || submitting" placeholder="如 2024级" />
              </AppFormItem>
            </div>
          </div>
        </section>

        <!-- 待遇信息 -->
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">工作内容与地址</span></div>
          <div class="mp-card__body pf-grid">
            <AppFormItem class="pf-grid__full" label="工作内容" prop="workContent" required v-slot="{ id }">
              <AppTextarea :id="id" v-model="form.workContent" :rows="4" :disabled="readonly || submitting" />
            </AppFormItem>
            <AppFormItem class="pf-grid__full" label="工作地址" v-slot="{ id }"><AppTextInput :id="id" v-model="form.workAddress" :disabled="readonly || submitting" /></AppFormItem>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">打卡地点与电子围栏</span>
            <span class="pf-aside">学生主动打卡时仅采集一次定位 · GCJ-02</span>
          </div>
          <div class="mp-card__body">
            <AppInlineAlert
              type="info"
              title="定位只作为核验线索"
              :description="`本批次建议半径 ${defaultFenceRadius} 米，最大可接受误差 ${maxAccuracyM} 米。低精度和围栏边界记录会转教师人工核验。`"
            />
            <div class="pf-grid pf-fence-fields">
              <AppFormItem label="启用岗位围栏">
                <AppRadioGroup v-model="form.geofenceEnabled" :options="boolOptions" :disabled="readonly || submitting" />
              </AppFormItem>
              <div class="pf-fence-actions">
                <AppButton v-if="form.geofenceEnabled" variant="ghost" size="small" :disabled="readonly || submitting" @click="applyDefaultFence">采用批次半径</AppButton>
                <span class="pf-aside">中心坐标从合规地图后台复制粘贴</span>
              </div>
              <AppFormItem label="中心纬度" prop="geofenceLat" :required="form.geofenceEnabled" v-slot="{ id }">
                <AppNumberInput :id="id" v-model="form.geofenceLat" :min="-90" :max="90" :step="0.000001" :disabled="readonly || submitting || !form.geofenceEnabled" />
              </AppFormItem>
              <AppFormItem label="中心经度" prop="geofenceLng" :required="form.geofenceEnabled" v-slot="{ id }">
                <AppNumberInput :id="id" v-model="form.geofenceLng" :min="-180" :max="180" :step="0.000001" :disabled="readonly || submitting || !form.geofenceEnabled" />
              </AppFormItem>
              <AppFormItem label="围栏半径（米）" prop="geofenceRadiusM" :required="form.geofenceEnabled" v-slot="{ id }">
                <AppNumberInput :id="id" v-model="form.geofenceRadiusM" :min="30" :max="5000" :step="10" :disabled="readonly || submitting || !form.geofenceEnabled" />
              </AppFormItem>
              <div class="pf-fence-preview" :class="{ 'is-enabled': form.geofenceEnabled }" aria-label="岗位围栏范围示意">
                <span class="pf-fence-preview__ring"><i /></span>
                <div><strong>{{ form.geofenceEnabled ? `${form.geofenceRadiusM || '—'} 米范围` : '未启用围栏' }}</strong><small>{{ form.geofenceEnabled ? '保存后，正式落岗会冻结本次围栏规则' : '学生打卡只留时间与定位证据' }}</small></div>
              </div>
            </div>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">工时与班次</span></div>
          <div class="mp-card__body pf-grid">
            <AppFormItem label="每日工时" v-slot="{ id }"><AppNumberInput :id="id" v-model="form.dailyHours" :min="0" :max="24" :disabled="readonly || submitting" /></AppFormItem>
            <AppFormItem label="每周工时" v-slot="{ id }"><AppNumberInput :id="id" v-model="form.weeklyHours" :min="0" :max="168" :disabled="readonly || submitting" /></AppFormItem>
            <AppFormItem label="班次" v-slot="{ id }"><AppTextInput :id="id" v-model="form.shiftType" :disabled="readonly || submitting" /></AppFormItem>
            <AppFormItem label="每周休息" v-slot="{ id }"><AppNumberInput :id="id" v-model="form.restDaysPerWeek" :min="0" :max="7" :disabled="readonly || submitting" /></AppFormItem>
            <AppFormItem label="是否夜班"><AppRadioGroup aria-label="是否夜班" v-model="form.nightShift" :options="triStateOptions" :disabled="readonly || submitting" /></AppFormItem>
            <AppFormItem label="允许加班"><AppRadioGroup aria-label="允许加班" v-model="form.overtimeAllowed" :options="triStateOptions" :disabled="readonly || submitting" /></AppFormItem>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">报酬与食宿条件</span></div>
          <div class="mp-card__body">
            <div class="pf-grid">
              <AppFormItem label="报酬类型" v-slot="{ id }"><AppSelect :id="id" v-model="form.remunerationType" :options="remunerationOptions" :disabled="readonly || submitting" /></AppFormItem>
              <AppFormItem label="报酬金额" v-slot="{ id }"><AppNumberInput :id="id" v-model="form.remunerationAmount" :min="0" :disabled="readonly || submitting" /></AppFormItem>
              <AppFormItem label="发放周期" v-slot="{ id }"><AppSelect :id="id" v-model="form.remunerationCycle" :options="cycleOptions" :disabled="readonly || submitting" /></AppFormItem>
              <AppFormItem label="提供住宿"><AppRadioGroup aria-label="提供住宿" v-model="form.accommodationProvided" :options="triStateOptions" :disabled="readonly || submitting" /></AppFormItem>
              <AppFormItem label="提供餐食"><AppRadioGroup aria-label="提供餐食" v-model="form.mealProvided" :options="triStateOptions" :disabled="readonly || submitting" /></AppFormItem>
              <AppFormItem class="pf-grid__full" label="工作地点" prop="workLocation">
                <AppChinaRegionPicker v-model="form.workLocation" :disabled="readonly || submitting" placeholder="请选择工作省 / 市 / 区县" />
              </AppFormItem>
              <AppFormItem label="薪资" prop="salaryRange" v-slot="{ id }">
                <AppTextInput :id="id" v-model="form.salaryRange" :disabled="readonly || submitting" placeholder="如 3k-4k" />
              </AppFormItem>
              <AppFormItem class="pf-grid__full" label="补贴" prop="subsidy" hint="点击下方标签追加，或手动输入" v-slot="{ id }">
                <AppTextInput :id="id" v-model="form.subsidy" :disabled="readonly || submitting" placeholder="如：五险一金、包吃住、交通补贴" />
                <AppTemplateChips
                  v-if="!readonly"
                  class="pf-welfare-chips"
                  :options="welfareChips"
                  size="compact"
                  @pick="onPickWelfare"
                />
              </AppFormItem>
            </div>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">风险与特殊设备</span></div>
          <div class="mp-card__body pf-grid">
            <AppFormItem label="危险岗位"><AppRadioGroup aria-label="危险岗位" v-model="form.hazardousFlag" :options="triStateOptions" :disabled="readonly || submitting" /></AppFormItem>
            <AppFormItem label="特殊设备" v-slot="{ id }"><AppTextInput :id="id" v-model="form.specialEquipment" :disabled="readonly || submitting" /></AppFormItem>
            <AppFormItem class="pf-grid__full" label="禁止安排说明" v-slot="{ id }"><AppTextarea :id="id" v-model="form.prohibitedReason" :rows="2" :disabled="readonly || submitting" /></AppFormItem>
          </div>
        </section>

        <AppInlineAlert
          v-if="detail?.compliance"
          :type="detail.publishable ? 'success' : 'warning'"
          :title="detail.publishable ? '已保存资料通过发布检查' : '已保存资料仍需补充'"
          :description="complianceDescription"
        />

        <!-- 企业导师（仅新建：沿用原抽屉口径，编辑态隐藏导师字段） -->
        <section v-if="!isEdit" class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">企业导师</span>
            <span class="pf-aside">先选择所属企业，再选择该企业的导师（可不指定）</span>
          </div>
          <div class="mp-card__body">
            <AppFormItem label="企业导师" prop="mentorContactId">
              <AppEnterpriseMentorPicker
                v-model="form.mentorContactId"
                :disabled="readonly || submitting"
                :query="{ companyId: form.companyId }"
                placeholder="选择企业导师（可不指定）"
                search-placeholder="按导师姓名过滤"
                data-scope-hint="先选择所属企业，再选择该企业的导师"
              />
            </AppFormItem>
          </div>
        </section>

        <!-- 备注 -->
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">备注</span></div>
          <div class="mp-card__body">
            <AppFormItem label="备注" prop="remark" v-slot="{ id }">
              <AppTextarea :id="id" v-model="form.remark" :rows="3" :disabled="readonly || submitting" placeholder="岗位补充说明（可选）" />
            </AppFormItem>
          </div>
        </section>

        <AppSubmitBar
          :loading="submitting"
          :disabled="readonly || submitting"
          :submit-text="isEdit ? '保存修改' : '创建岗位'"
          cancel-text="取消"
          @submit="onSubmit"
          @cancel="goBack"
        />
      </AppForm>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 岗位表单独立页（新建 + 编辑一体，替代岗位库列表页原「新增/编辑抽屉」）。
 * 路由（由主流程挂载，本文件不改 routes.js）：
 *   /admin/internship/positions/new       → 新建（草稿态，须先选合作企业）
 *   /admin/internship/positions/:id/edit  → 编辑（getPositionDetail 回填；ARCHIVED 只读预览）
 * 提交走真实 positionApi.createPosition / updatePosition。
 * 口径（沿用原抽屉）：编辑态所属企业只读展示不可换（:options 预置当前企业回显）、导师字段隐藏不提交；
 * 新建态企业与企业导师均由布局注入的业务 Picker 查询；企业导师以 companyId 为联动条件。
 */
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import {
  AppInlineAlert, AppForm, AppFormItem, AppTextInput, AppNumberInput, AppTextarea,
  AppSubmitBar, AppInternshipEnterprisePicker, AppEnterpriseMentorPicker, AppTemplateChips,
  AppSelect, AppRadioGroup, AppChinaRegionPicker
} from '@/components/common'
import { canCode } from '@/modules/internship/composables/permission'
import { positionApi } from '@/modules/internship/api/position.api'
import { REMUNERATION_TYPE, REMUNERATION_CYCLE } from '@/modules/internship/constants/position.constants'
import { toast } from '@/utils/toast'
import { useInternshipBatchStore } from '@/stores/internshipBatch'

const blankForm = () => ({
  companyId: '', title: '', majorRequirement: '', gradeRequirement: '',
  workLocation: '', salaryRange: '', subsidy: '', headcount: 1, mentorContactId: '', remark: '',
  workContent: '', workAddress: '', dailyHours: null, weeklyHours: null, shiftType: '',
  nightShift: null, overtimeAllowed: null, restDaysPerWeek: null,
  remunerationType: '', remunerationAmount: null, remunerationCycle: '',
  accommodationProvided: null, mealProvided: null, hazardousFlag: null,
  specialEquipment: '', prohibitedReason: '', geofenceEnabled: false,
  geofenceLat: null, geofenceLng: null, geofenceRadiusM: null
})

// 岗位福利快捷标签（20-岗位实习预设便捷字段与提示词.md §5），点击追加进「补贴」字段
const WELFARE_CHIPS = [
  '餐补', '交通补贴', '住宿补贴', '五险', '节日福利', '带薪年假',
  '团队活动', '转正机会', '弹性工时', '免费零食', '员工培训'
]

export default {
  name: 'PositionFormView',
  props: { ctx: { type: Object, required: true } },
  components: {
    ModulePageShell, LoadingState, ErrorState, AppButton,
    AppInlineAlert, AppForm, AppFormItem, AppTextInput, AppNumberInput, AppTextarea,
    AppSubmitBar, AppInternshipEnterprisePicker, AppEnterpriseMentorPicker, AppTemplateChips,
    AppSelect, AppRadioGroup, AppChinaRegionPicker
  },
  data() {
    return {
      loadSequence: 0,
      loading: false,
      error: '',
      submitting: false,
      detail: null,
      form: blankForm()
    }
  },
  computed: {
    isEdit() {
      return !!this.$route.params.id
    },
    isFormRoute() {
      const p = this.$route.path
      return p.endsWith('/new') || p.endsWith('/edit')
    },
    readonly() {
      return !Array.isArray(this.ctx.permissionPatterns) || !canCode(this.ctx, 'internship.position.manage') || (this.isEdit && this.detail?.status === 'ARCHIVED')
    },
    batchStore() { return useInternshipBatchStore() },
    triStateOptions() {
      return [{ label: '未知', value: null }, { label: '是', value: true }, { label: '否', value: false }]
    },
    boolOptions() {
      return [{ label: '启用', value: true }, { label: '暂不启用', value: false }]
    },
    defaultFenceRadius() {
      return Number(this.detail?.checkinRule?.defaultRadiusM || this.batchStore.selectedBatch?.rules?.checkin?.geofenceRadiusM || 500)
    },
    maxAccuracyM() {
      return Number(this.detail?.checkinRule?.maxAccuracyM || this.batchStore.selectedBatch?.rules?.checkin?.maxAccuracyM || 200)
    },
    remunerationOptions() {
      return REMUNERATION_TYPE
    },
    cycleOptions() {
      return REMUNERATION_CYCLE
    },
    complianceDescription() {
      const c = this.detail?.compliance || {}
      return `需处理 ${c.blockers?.length || 0} 项，待补充 ${c.unknowns?.length || 0} 项，提醒 ${c.warnings?.length || 0} 项。这里显示已保存资料的检查结果，本次修改保存后重新检查。`
    },
    companyPresetOpts() {
      // 编辑态回显：把当前岗位所属企业预置进选择器本地选项缓存（合法本地预置，不是一次性全量加载）
      if (!this.isEdit || !this.detail || !this.detail.companyId) return []
      return [{ label: this.detail.companyName, value: this.detail.companyId }]
    },
    pageSubtitle() {
      if (this.isEdit) {
        return this.detail ? `${this.detail.title} · ${this.detail.companyName}（${this.detail.statusLabel}）` : ''
      }
      return '先填写岗位资料与实习条件，保存后在岗位详情核对并提交审核。'
    },
    welfareChips() {
      return WELFARE_CHIPS
    },
    formRules() {
      const rules = {
        title: [{ required: true, message: '岗位名称必填' }],
        workContent: [{ required: true, message: '工作内容必填' }],
        headcount: [
          { required: true, message: '容量至少 1' },
          { validator: (v) => (Number(v) >= 1 ? true : '容量至少 1') }
        ]
      }
      if (!this.isEdit) rules.companyId = [{ required: true, message: '请选择所属企业' }]
      const requiredFence = (value, _model) => !this.form.geofenceEnabled || value !== null && value !== '' || '启用围栏后必须填写完整'
      rules.geofenceLat = [{ validator: requiredFence }]
      rules.geofenceLng = [{ validator: requiredFence }]
      rules.geofenceRadiusM = [{ validator: requiredFence }]
      return rules
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
    this.init()
  },
  beforeUnmount() { this.loadSequence++ },
  methods: {
    onHeadcountClamp({ from, to }) {
      // BUG-003：容量填 -5 原来被静默改成 1，用户毫无感知
      toast.warning(`容量最少 ${to} 人，已把输入的 ${from} 修正为 ${to}`)
    },
    onPickWelfare(text) {
      if (!text || this.submitting) return
      const cur = (this.form.subsidy || '').split(/[、,，]/).map((s) => s.trim()).filter(Boolean)
      if (cur.includes(text)) return
      cur.push(text)
      this.form.subsidy = cur.join('、')
    },
    applyDefaultFence() {
      this.form.geofenceRadiusM = this.defaultFenceRadius
    },
    goBack() {
      const query = { ...this.$route.query }
      if (!this.isEdit) delete query.section
      this.$router.push({ path: this.isEdit ? '/admin/internship/positions/' + this.$route.params.id : '/admin/internship/positions', query })
    },
    async init() {
      const sequence = ++this.loadSequence
      this.submitting = false
      this.error = ''
      if (!this.isEdit) {
        this.detail = null
        this.form = blankForm()
        this.loading = false
        return
      }
      this.loading = true
      const id = this.$route.params.id
      const res = await positionApi.getPositionDetail(id)
      if (sequence !== this.loadSequence || id !== this.$route.params.id) return
      this.loading = false
      if (res.code !== 0) {
        this.error = res.message || '岗位不存在或无权查看'
        return
      }
      const d = res.data
      this.detail = d
      this.form = {
        companyId: d.companyId || '',
        title: d.title || '',
        majorRequirement: d.majorRequirement || '',
        gradeRequirement: d.gradeRequirement || '',
        workLocation: d.workLocation || '',
        salaryRange: d.salaryRange || '',
        subsidy: d.subsidy || '',
        headcount: d.headcount || 1,
        mentorContactId: '', // 编辑态隐藏导师字段（口径同原抽屉），不回填不提交
        remark: d.remark || ''
        ,workContent: d.workContent || '', workAddress: d.workAddress || '',
        dailyHours: d.dailyHours, weeklyHours: d.weeklyHours, shiftType: d.shiftType || '',
        nightShift: d.nightShift, overtimeAllowed: d.overtimeAllowed,
        restDaysPerWeek: d.restDaysPerWeek, remunerationType: d.remunerationType || '',
        remunerationAmount: d.remunerationAmount, remunerationCycle: d.remunerationCycle || '',
        accommodationProvided: d.accommodationProvided, mealProvided: d.mealProvided,
        hazardousFlag: d.hazardousFlag, specialEquipment: d.specialEquipment || '',
        prohibitedReason: d.prohibitedReason || '',
        geofenceEnabled: !!d.checkinRule?.configured,
        geofenceLat: d.geofenceLat, geofenceLng: d.geofenceLng,
        geofenceRadiusM: d.geofenceRadiusM
      }
    },
    async onCompanyChange() {
      // 企业变更后清空导师；企业导师由统一 Picker 按 companyId 查询。
      if (this.isEdit) return
      this.form.mentorContactId = ''
    },
    async onSubmit() {
      if (this.readonly || this.submitting) return
      const sequence = this.loadSequence, id = this.$route.params.id, query = { ...this.$route.query }, isEdit = this.isEdit
      const { valid } = await this.$refs.posForm.validate()
      if (!valid || sequence !== this.loadSequence || id !== this.$route.params.id) return
      const f = this.form
      const body = {
        title: (f.title || '').trim(),
        majorRequirement: (f.majorRequirement || '').trim(),
        gradeRequirement: (f.gradeRequirement || '').trim(),
        workLocation: (f.workLocation || '').trim(),
        salaryRange: (f.salaryRange || '').trim(),
        subsidy: (f.subsidy || '').trim(),
        headcount: Number(f.headcount || 1),
        remark: (f.remark || '').trim()
        ,workContent: (f.workContent || '').trim(), workAddress: (f.workAddress || '').trim() || null,
        dailyHours: f.dailyHours, weeklyHours: f.weeklyHours, shiftType: (f.shiftType || '').trim() || null,
        nightShift: f.nightShift, overtimeAllowed: f.overtimeAllowed,
        restDaysPerWeek: f.restDaysPerWeek, remunerationType: f.remunerationType || null,
        remunerationAmount: f.remunerationAmount, remunerationCycle: f.remunerationCycle || null,
        accommodationProvided: f.accommodationProvided, mealProvided: f.mealProvided,
        hazardousFlag: f.hazardousFlag, specialEquipment: (f.specialEquipment || '').trim() || null,
        prohibitedReason: (f.prohibitedReason || '').trim() || null,
        geofenceLat: f.geofenceEnabled ? Number(f.geofenceLat) : null,
        geofenceLng: f.geofenceEnabled ? Number(f.geofenceLng) : null,
        geofenceRadiusM: f.geofenceEnabled ? Number(f.geofenceRadiusM) : null
      }
      body.batchId = this.detail?.batchId || this.batchStore.selectedBatchId || null
      if (this.isEdit) body.expectedVersion = this.detail.version
      if (!this.isEdit) {
        body.companyId = f.companyId
        body.mentorContactId = f.mentorContactId || null
      }
      this.submitting = true
      try {
        const res = this.isEdit
          ? await positionApi.updatePosition(id, body)
          : await positionApi.createPosition(body)
        if (sequence !== this.loadSequence || id !== this.$route.params.id) return
        if (res.code === 0) {
          if (typeof window !== 'undefined') window.__SAAS_DIRTY_FORM_GUARD__?.markSaved?.()
          toast.success(isEdit ? '已保存，发布前请核对检查结果' : '已创建岗位草稿')
          this.$router.push({ path: '/admin/internship/positions/' + res.data.id, query: { ...query, section: query.section || 'publish' } })
        } else {
          toast.error(res.message || '保存失败')
        }
      } finally {
        if (sequence === this.loadSequence) this.submitting = false
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.pf-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-1) var(--space-6);
}
.pf-grid__full {
  grid-column: 1 / -1;
}
.pf-aside {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.pf-welfare-chips {
  margin-top: var(--space-2);
}
.pf-fence-fields { margin-top: var(--space-4); align-items: end; }
.pf-fence-actions { display: flex; align-items: center; gap: var(--space-3); min-height: 40px; }
.pf-fence-preview { min-height: 86px; border: 1px dashed var(--border-color); border-radius: var(--radius-lg); display: flex; align-items: center; gap: var(--space-4); padding: var(--space-3); color: var(--text-tertiary); }
.pf-fence-preview.is-enabled { border-color: var(--primary-300); background: var(--primary-50); color: var(--text-primary); }
.pf-fence-preview__ring { width: 52px; height: 52px; border-radius: 50%; border: 2px solid currentColor; display: grid; place-items: center; flex: 0 0 auto; }
.pf-fence-preview__ring i { width: 10px; height: 10px; border-radius: 50%; background: currentColor; }
.pf-fence-preview strong, .pf-fence-preview small { display: block; }
.pf-fence-preview small { margin-top: 4px; color: var(--text-secondary); }
@media (max-width: 960px) {
  .pf-grid {
    grid-template-columns: 1fr;
  }
}
</style>
