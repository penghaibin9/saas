<template>
  <ModulePageShell
    :title="isEdit ? '编辑岗位' : '新增岗位'"
    :subtitle="pageSubtitle"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="岗位库维护"
  >
    <template #actions>
      <AppButton variant="ghost" @click="goBack">← 返回岗位库</AppButton>
    </template>

    <ErrorState v-if="error" :description="error" @retry="init" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-stack">
      <AppInlineAlert
        v-if="readonly"
        type="warning"
        title="已归档岗位不可编辑"
        :description="`岗位当前状态为「${detail.statusLabel}」，已归档岗位后端拒绝修改；本页为只读预览，提交已禁用。`"
      />

      <AppForm
        ref="posForm"
        :model="form"
        :rules="formRules"
        layout="horizontal"
        label-width="112px"
        @submit="onSubmit"
      >
        <!-- 基本信息 -->
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">基本信息</span>
            <span class="pf-aside">批次：按当前实习批次自动关联（预留）</span>
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
                  :disabled="isEdit || readonly"
                  disabled-reason="编辑岗位时不可更换所属企业"
                  placeholder="输入企业名称搜索"
                  search-placeholder="按企业名称搜索"
                  data-scope-hint="仅合作企业 · 黑名单/非合作中企业上架时由后端拦截"
                  @update:model-value="onCompanyChange"
                />
              </AppFormItem>
              <AppFormItem label="岗位名称" prop="title" required>
                <AppTextInput v-model="form.title" :disabled="readonly" placeholder="如：Java开发实习生 / 市场营销实习生 / 化工工艺实习生" />
              </AppFormItem>
              <AppFormItem label="容量" prop="headcount" required :hint="isEdit && detail ? `已分配 ${detail.allocatedCount} 人，容量不能低于已分配数` : ''">
                <AppNumberInput v-model="form.headcount" :min="1" :disabled="readonly" @clamp="onHeadcountClamp" />
              </AppFormItem>
            </div>
          </div>
        </section>

        <!-- 岗位要求 -->
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">岗位要求</span></div>
          <div class="mp-card__body">
            <div class="pf-grid">
              <AppFormItem label="专业要求" prop="majorRequirement">
                <AppTextInput v-model="form.majorRequirement" :disabled="readonly" placeholder="不填=不限" />
              </AppFormItem>
              <AppFormItem label="年级要求" prop="gradeRequirement">
                <AppTextInput v-model="form.gradeRequirement" :disabled="readonly" placeholder="如 2024级" />
              </AppFormItem>
            </div>
          </div>
        </section>

        <!-- 待遇信息 -->
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">工作内容与地址</span></div>
          <div class="mp-card__body pf-grid">
            <AppFormItem class="pf-grid__full" label="工作内容" prop="workContent" required>
              <AppTextarea v-model="form.workContent" :rows="4" :disabled="readonly" />
            </AppFormItem>
            <AppFormItem class="pf-grid__full" label="工作地址"><AppTextInput v-model="form.workAddress" :disabled="readonly" /></AppFormItem>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">工时与班次</span></div>
          <div class="mp-card__body pf-grid">
            <AppFormItem label="每日工时"><AppNumberInput v-model="form.dailyHours" :min="0" :max="24" :disabled="readonly" /></AppFormItem>
            <AppFormItem label="每周工时"><AppNumberInput v-model="form.weeklyHours" :min="0" :max="168" :disabled="readonly" /></AppFormItem>
            <AppFormItem label="班次"><AppTextInput v-model="form.shiftType" :disabled="readonly" /></AppFormItem>
            <AppFormItem label="每周休息"><AppNumberInput v-model="form.restDaysPerWeek" :min="0" :max="7" :disabled="readonly" /></AppFormItem>
            <AppFormItem label="是否夜班"><AppRadioGroup v-model="form.nightShift" :options="triStateOptions" :disabled="readonly" /></AppFormItem>
            <AppFormItem label="允许加班"><AppRadioGroup v-model="form.overtimeAllowed" :options="triStateOptions" :disabled="readonly" /></AppFormItem>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">报酬与食宿条件</span></div>
          <div class="mp-card__body">
            <div class="pf-grid">
              <AppFormItem label="报酬类型"><AppSelect v-model="form.remunerationType" :options="remunerationOptions" :disabled="readonly" /></AppFormItem>
              <AppFormItem label="报酬金额"><AppNumberInput v-model="form.remunerationAmount" :min="0" :disabled="readonly" /></AppFormItem>
              <AppFormItem label="发放周期"><AppSelect v-model="form.remunerationCycle" :options="cycleOptions" :disabled="readonly" /></AppFormItem>
              <AppFormItem label="提供住宿"><AppRadioGroup v-model="form.accommodationProvided" :options="triStateOptions" :disabled="readonly" /></AppFormItem>
              <AppFormItem label="提供餐食"><AppRadioGroup v-model="form.mealProvided" :options="triStateOptions" :disabled="readonly" /></AppFormItem>
              <AppFormItem label="工作地点" prop="workLocation">
                <AppTextInput v-model="form.workLocation" :disabled="readonly" placeholder="如：深圳市南山区科技园" />
              </AppFormItem>
              <AppFormItem label="薪资" prop="salaryRange">
                <AppTextInput v-model="form.salaryRange" :disabled="readonly" placeholder="如 3k-4k" />
              </AppFormItem>
              <AppFormItem class="pf-grid__full" label="补贴" prop="subsidy" hint="点击下方标签追加，或手动输入">
                <AppTextInput v-model="form.subsidy" :disabled="readonly" placeholder="如：五险一金、包吃住、交通补贴" />
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
            <AppFormItem label="危险岗位"><AppRadioGroup v-model="form.hazardousFlag" :options="triStateOptions" :disabled="readonly" /></AppFormItem>
            <AppFormItem label="特殊设备"><AppTextInput v-model="form.specialEquipment" :disabled="readonly" /></AppFormItem>
            <AppFormItem class="pf-grid__full" label="禁止安排说明"><AppTextarea v-model="form.prohibitedReason" :rows="2" :disabled="readonly" /></AppFormItem>
          </div>
        </section>

        <AppInlineAlert
          v-if="detail?.compliance"
          :type="detail.publishable ? 'success' : 'warning'"
          :title="detail.publishable ? '当前岗位可发布' : '当前岗位不可发布'"
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
            <AppFormItem label="备注" prop="remark">
              <AppTextarea v-model="form.remark" :rows="3" :disabled="readonly" placeholder="岗位补充说明（可选）" />
            </AppFormItem>
          </div>
        </section>

        <AppSubmitBar
          :loading="submitting"
          :disabled="readonly"
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
  AppSelect, AppRadioGroup
} from '@/components/common'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { positionApi } from '@/modules/internship/api/position.api'
import { toast } from '@/utils/toast'
import { useInternshipBatchStore } from '@/stores/internshipBatch'

const blankForm = () => ({
  companyId: '', title: '', majorRequirement: '', gradeRequirement: '',
  workLocation: '', salaryRange: '', subsidy: '', headcount: 1, mentorContactId: '', remark: '',
  workContent: '', workAddress: '', dailyHours: null, weeklyHours: null, shiftType: '',
  nightShift: null, overtimeAllowed: null, restDaysPerWeek: null,
  remunerationType: '', remunerationAmount: null, remunerationCycle: '',
  accommodationProvided: null, mealProvided: null, hazardousFlag: null,
  specialEquipment: '', prohibitedReason: ''
})

// 岗位福利快捷标签（20-岗位实习预设便捷字段与提示词.md §5），点击追加进「补贴」字段
const WELFARE_CHIPS = [
  '餐补', '交通补贴', '住宿补贴', '五险', '节日福利', '带薪年假',
  '团队活动', '转正机会', '弹性工时', '免费零食', '员工培训'
]

export default {
  name: 'PositionFormView',
  components: {
    ModulePageShell, LoadingState, ErrorState, AppButton,
    AppInlineAlert, AppForm, AppFormItem, AppTextInput, AppNumberInput, AppTextarea,
    AppSubmitBar, AppInternshipEnterprisePicker, AppEnterpriseMentorPicker, AppTemplateChips,
    AppSelect, AppRadioGroup
  },
  data() {
    return {
      ctx: null,
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
    roleName() {
      return this.ctx?.currentRole?.roleName || ''
    },
    dataScopeName() {
      return this.ctx?.dataScope?.scopeName || ''
    },
    readonly() {
      return this.isEdit && !!this.detail && this.detail.status === 'ARCHIVED'
    },
    batchStore() { return useInternshipBatchStore() },
    triStateOptions() {
      return [{ label: '未知', value: null }, { label: '是', value: true }, { label: '否', value: false }]
    },
    remunerationOptions() {
      return ['HOURLY', 'MONTHLY', 'DAILY', 'ALLOWANCE', 'UNPAID', 'OTHER'].map((value) => ({ label: value, value }))
    },
    cycleOptions() {
      return ['MONTHLY', 'WEEKLY', 'DAILY', 'ON_COMPLETION', 'OTHER'].map((value) => ({ label: value, value }))
    },
    complianceDescription() {
      const c = this.detail?.compliance || {}
      return `阻断 ${c.blockers?.length || 0} 项，未知 ${c.unknowns?.length || 0} 项，警告 ${c.warnings?.length || 0} 项；规则 ${c.ruleVersion || '-'}。保存成功不代表已合规。`
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
      return '新增岗位为草稿态，须先关联合作企业；提交审核、上架/下架、风险标记在岗位库列表操作'
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
    internshipApi.getContext().then((res) => {
      if (res.code === 0) this.ctx = res.data
    })
    this.init()
  },
  methods: {
    onHeadcountClamp({ from, to }) {
      // BUG-003：容量填 -5 原来被静默改成 1，用户毫无感知
      toast.warning(`容量最少 ${to} 人，已把输入的 ${from} 修正为 ${to}`)
    },
    onPickWelfare(text) {
      if (!text) return
      const cur = (this.form.subsidy || '').split(/[、,，]/).map((s) => s.trim()).filter(Boolean)
      if (cur.includes(text)) return
      cur.push(text)
      this.form.subsidy = cur.join('、')
    },
    goBack() {
      const back = this.$router.options.history.state && this.$router.options.history.state.back
      if (typeof back === 'string' && back.startsWith('/admin/internship/positions')) this.$router.back()
      else this.$router.push('/admin/internship/positions')
    },
    async init() {
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
      if (id !== this.$route.params.id) return
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
        prohibitedReason: d.prohibitedReason || ''
      }
    },
    async onCompanyChange() {
      // 企业变更后清空导师；企业导师由统一 Picker 按 companyId 查询。
      if (this.isEdit) return
      this.form.mentorContactId = ''
    },
    async onSubmit() {
      if (this.readonly || this.submitting) return
      const { valid } = await this.$refs.posForm.validate()
      if (!valid) return
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
        prohibitedReason: (f.prohibitedReason || '').trim() || null
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
          ? await positionApi.updatePosition(this.$route.params.id, body)
          : await positionApi.createPosition(body)
        if (res.code === 0) {
          toast.success(this.isEdit ? '已保存；权益字段将重新评估，保存不代表已合规' : '已新增岗位草稿；保存不代表可发布')
          this.goBack()
        } else {
          toast.error(res.message || '保存失败')
        }
      } finally {
        this.submitting = false
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
@media (max-width: 960px) {
  .pf-grid {
    grid-template-columns: 1fr;
  }
}
</style>
