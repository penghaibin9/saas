<template>
  <ModulePageShell
    :title="isEdit ? '编辑实习批次' : '新建实习批次'"
    :subtitle="pageSubtitle"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="实习批次管理"
  >
    <template #actions>
      <AppButton variant="ghost" @click="goBack">← 返回批次列表</AppButton>
    </template>

    <ErrorState v-if="error" :description="error" @retry="init" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-stack">
      <AppInlineAlert
        v-if="readonly"
        type="warning"
        title="当前批次不可编辑"
        :description="`批次当前状态为「${detail.statusLabel}」，仅草稿（DRAFT）批次可在此编辑；本页为只读预览，提交已禁用。`"
      />

      <AppForm
        ref="batchForm"
        :model="form"
        :rules="formRules"
        layout="horizontal"
        label-width="112px"
        @submit="onSubmit"
      >
        <!-- 基本信息 -->
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">基本信息</span></div>
          <div class="mp-card__body">
            <div class="bf-grid">
              <AppFormItem label="批次名称" prop="batchName">
                <AppTextInput v-model="form.batchName" :disabled="readonly" placeholder="如：2026 届春季岗位实习" />
              </AppFormItem>
              <AppFormItem label="批次编号" prop="batchNo" :hint="isEdit ? '批次编号创建后不可修改' : '租户内唯一，如：INT-2026S'">
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

        <!-- 阶段配置（stagesJson） -->
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">阶段配置</span>
            <span class="bf-aside">stagesJson · 留空使用默认三阶段：岗前准备 / 在岗实习 / 总结考核</span>
          </div>
          <div class="mp-card__body bf-json">
            <AppFormItem
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
            <div class="bf-preview">
              <div class="bf-preview__title">解析预览</div>
              <p v-if="stagesParsed.empty" class="bf-preview__note">留空提交时将使用默认三阶段：岗前准备 / 在岗实习 / 总结考核</p>
              <p v-else-if="stagesError" class="bf-preview__err">{{ stagesError }}</p>
              <AppTimeline v-else :items="stagePreviewItems" />
            </div>
          </div>
        </section>

        <!-- 规则配置（rulesJson：打卡 / 周报 / 指导 / 评价 / 成绩） -->
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">规则配置</span>
            <span class="bf-aside">rulesJson · 打卡 / 周报 / 指导 / 评价 / 成绩 · 仅填需覆盖的字段即可局部提交</span>
          </div>
          <div class="mp-card__body bf-json">
            <AppFormItem
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
            <div class="bf-preview">
              <div class="bf-preview__title">解析预览</div>
              <p v-if="rulesParsed.empty" class="bf-preview__note">留空提交时将沿用原有/默认规则（打卡、周报、指导、评价、成绩）</p>
              <p v-else-if="rulesError" class="bf-preview__err">{{ rulesError }}</p>
              <AppDescriptionList v-else :items="rulesPreviewItems" :columns="1" size="compact" label-width="150px" />
            </div>
          </div>
        </section>

        <AppSubmitBar
          :loading="submitting"
          :disabled="readonly"
          :submit-text="isEdit ? '保存修改' : '创建批次'"
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
  AppSubmitBar, AppDatePicker, AppTimeline, AppDescriptionList
} from '@/components/common'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { toast } from '@/utils/toast'

const RULE_LABELS = {
  checkin: '打卡', weeklyReport: '周报', guidance: '指导', evaluation: '评价', score: '成绩',
  requireDaily: '每日必打卡', geofenceRadiusM: '电子围栏半径（米）', frequency: '提交频率',
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

export default {
  name: 'BatchFormView',
  components: {
    ModulePageShell, LoadingState, ErrorState, AppButton,
    AppInlineAlert, AppForm, AppFormItem, AppTextInput, AppNumberInput, AppTextarea,
    AppSubmitBar, AppDatePicker, AppTimeline, AppDescriptionList
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
      return this.ctx?.dataScope?.name || ''
    },
    readonly() {
      return this.isEdit && !!this.detail && this.detail.status !== 'DRAFT'
    },
    pageSubtitle() {
      if (this.isEdit) {
        return this.detail ? `${this.detail.batchName}（${this.detail.batchNo}）` : ''
      }
      return '创建后为草稿态，可配置阶段时间轴与打卡 / 周报 / 指导 / 评价 / 成绩规则，启用后实习流程正式开放'
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
      const stages = this.stagesParsed.data || []
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
    internshipApi.getContext().then((res) => {
      if (res.code === 0) this.ctx = res.data
    })
    this.init()
  },
  methods: {
    dateShort(v) {
      return v ? String(v).slice(0, 10) : ''
    },
    pct(v) {
      return `${Math.round((v || 0) * 100)}%`
    },
    goBack() {
      const back = this.$router.options.history.state && this.$router.options.history.state.back
      if (typeof back === 'string' && back.startsWith('/admin/internship/batches')) this.$router.back()
      else this.$router.push('/admin/internship/batches')
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
      if (this.readonly || this.submitting) return
      const { valid } = await this.$refs.batchForm.validate()
      if (!valid) return
      if (this.stagesError) return toast.error('阶段时间轴 JSON 配置有误，请先修正')
      if (this.rulesError) return toast.error('规则配置 JSON 配置有误，请先修正')
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
      if (!this.stagesParsed.empty) body.stages = this.stagesParsed.data
      if (!this.rulesParsed.empty) body.rules = this.rulesParsed.data
      this.submitting = true
      try {
        const res = this.isEdit
          ? await internshipApi.updateBatch(this.$route.params.id, body)
          : await internshipApi.createBatch(body)
        if (res.code === 0) {
          toast.success(this.isEdit ? '已保存修改' : '已新建批次（草稿态）')
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
@media (max-width: 960px) {
  .bf-grid,
  .bf-json {
    grid-template-columns: 1fr;
  }
}
</style>
