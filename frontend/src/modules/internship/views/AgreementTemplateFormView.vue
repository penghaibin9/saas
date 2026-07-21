<template>
  <ModulePageShell
    :title="isEdit ? '编辑协议模板' : '新建协议模板'"
    :subtitle="pageSubtitle"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="实习协议模板管理"
  >
    <template #actions>
      <AppButton variant="ghost" @click="goBack">← 返回模板库</AppButton>
    </template>

    <ErrorState v-if="error" :description="error" @retry="init" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-stack">
      <AppInlineAlert
        v-if="readonly"
        type="warning"
        title="当前模板不可编辑"
        :description="`模板当前状态为「${detail.statusLabel}」，已归档模板仅可查看，不可再编辑；本页为只读预览，提交已禁用。`"
      />

      <AppForm
        ref="tplForm"
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
            <div class="atf-grid">
              <AppFormItem class="atf-grid__full" label="模板名称" prop="name" required>
                <AppTextInput v-model="form.name" :disabled="readonly" placeholder="如 顶岗实习三方协议" />
              </AppFormItem>
              <AppFormItem label="协议类型" prop="category">
                <AppSelect v-model="form.category" :options="categoryOptions" placeholder="" :disabled="readonly" />
              </AppFormItem>
              <AppFormItem label="版本号" prop="version">
                <AppTextInput v-model="form.version" :disabled="readonly" placeholder="v1.0" />
              </AppFormItem>
              <AppFormItem label="适用学院ID" prop="scopeCollegeIds">
                <AppTextInput v-model="form.scopeCollegeIds" :disabled="readonly" placeholder="逗号分隔，留空=全校" />
              </AppFormItem>
              <AppFormItem label="适用专业ID" prop="scopeMajorIds">
                <AppTextInput v-model="form.scopeMajorIds" :disabled="readonly" placeholder="逗号分隔，留空=全校" />
              </AppFormItem>
              <AppFormItem label="适用年级" prop="scopeGrades">
                <AppTextInput v-model="form.scopeGrades" :disabled="readonly" placeholder="如 2024级,2023级" />
              </AppFormItem>
              <AppFormItem label="适用批次ID" prop="scopeBatchIds">
                <AppTextInput v-model="form.scopeBatchIds" :disabled="readonly" placeholder="逗号分隔，留空=不限" />
              </AppFormItem>
              <AppFormItem class="atf-grid__full" label="备注" prop="remark">
                <AppTextInput v-model="form.remark" :disabled="readonly" placeholder="备注（可选）" />
              </AppFormItem>
            </div>
          </div>
        </section>

        <!-- 模板正文（核心内容，占满宽度）：条款/变量都是点击插入，不用手打双花括号 -->
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">模板正文</span>
            <span class="atf-aside">点下方按钮把条款或变量插入正文，光标停在哪就插在哪</span>
          </div>
          <div class="mp-card__body">
            <AppFormItem class="atf-body-item" label="正文内容" prop="body">
              <div v-if="!readonly" class="atf-chip-row">
                <span class="atf-chip-row__label">常用条款</span>
                <AppTemplateChips class="atf-body-chips" :options="AGREEMENT_CLAUSE" size="compact" @pick="onPickClause" />
              </div>
              <div v-if="!readonly && variableChipOptions.length" class="atf-chip-row">
                <span class="atf-chip-row__label">插入变量</span>
                <AppTemplateChips class="atf-body-chips" :options="variableChipOptions" size="compact" @pick="onPickVariable" />
              </div>
              <AppTextarea
                v-model="form.body"
                class="atf-body"
                :rows="16"
                :disabled="readonly"
                :placeholder="bodyPlaceholder"
              />
            </AppFormItem>
          </div>
        </section>

        <AppSubmitBar
          :loading="submitting"
          :disabled="readonly"
          :submit-text="isEdit ? '保存修改' : '创建模板'"
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
 * 实习协议模板表单独立页（新建 + 编辑一体，原列表页编辑抽屉收口至此）。
 * 路由（由主流程挂载，本文件不改 routes.js）：
 *   /admin/internship/agreement-templates/new       → 新建
 *   /admin/internship/agreement-templates/:id/edit  → 编辑（已归档 ARCHIVED 只读预览，后端最终拦截）
 * 字段与原抽屉一致（名称/类型/版本/适用范围×4/正文/备注，不增不减）；
 * 变量占位改点击插入（不再靠手动勾选记账），提交时从正文实际内容反推 variables 清单。
 * 编辑态 getTemplateDetail(:id) 回填，提交走真实 createTemplate / updateTemplate。
 */
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import {
  AppInlineAlert, AppForm, AppFormItem, AppTextInput, AppSelect, AppTextarea, AppSubmitBar, AppTemplateChips
} from '@/components/common'
import { agreementTemplateApi } from '@/modules/internship/api/agreement-template.api'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { toast } from '@/utils/toast'
import { AGREEMENT_CLAUSE } from '@/modules/internship/constants/presetPrompts'

const CATEGORY_OPTS = ['三方协议', '顶岗实习协议', '安全责任书', '实习承诺书', '保密协议']
const blankForm = () => ({
  name: '', category: '', version: 'v1.0', scopeCollegeIds: '', scopeMajorIds: '',
  scopeGrades: '', scopeBatchIds: '', body: '', remark: ''
})
const toArr = (s) => (s || '').split(/[,，]/).map((x) => x.trim()).filter(Boolean)

export default {
  name: 'AgreementTemplateFormView',
  components: {
    ModulePageShell, LoadingState, ErrorState, AppButton,
    AppInlineAlert, AppForm, AppFormItem, AppTextInput, AppSelect, AppTextarea, AppSubmitBar, AppTemplateChips
  },
  data() {
    return {
      AGREEMENT_CLAUSE,
      ctx: null,
      loading: false,
      error: '',
      submitting: false,
      detail: null,
      variablePresets: [],
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
      return this.isEdit && !!this.detail && this.detail.status === 'ARCHIVED'
    },
    pageSubtitle() {
      if (this.isEdit) {
        return this.detail ? `${this.detail.name}（${this.detail.category || '未分类'} · ${this.detail.version}）` : ''
      }
      return '创建实习三方协议 / 安全责任书等模板，支持适用范围 / 版本 / 变量占位'
    },
    formRules() {
      return {
        name: [
          { required: true, message: '模板名称为必填项' },
          { min: 2, message: '模板名称至少 2 个字' }
        ]
      }
    },
    categoryOptions() {
      return [{ value: '', label: '未分类' }, ...CATEGORY_OPTS.map((c) => ({ value: c, label: c }))]
    },
    bodyPlaceholder() {
      // 用 braced() 拼占位符，避免在模板里直接写双花括号（Vue 会当插值解析）
      return `甲方：${this.braced('schoolName')}  乙方：${this.braced('companyName')}  实习学生：${this.braced('studentName')} ……`
    },
    // 变量清单点击即插入正文（不再靠勾选记账）；label 直接标好人话名字，点哪个插哪个
    variableChipOptions() {
      return this.variablePresets.map((v) => ({ label: v.label, value: this.braced(v.key) }))
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
    agreementTemplateApi.getVariablePresets().then((res) => {
      if (res.code === 0) this.variablePresets = res.data || []
    })
    this.init()
  },
  methods: {
    braced(key) {
      return '{' + '{' + key + '}' + '}'
    },
    onPickClause(text) {
      if (!text) return
      const cur = (this.form.body || '').replace(/\n+$/, '')
      this.form.body = cur ? cur + '\n' + text : text
    },
    onPickVariable(text) {
      if (!text) return
      // 变量占位符直接接在末尾，中间留个空格，方便连续点插多个变量拼一行（如 甲方：{{schoolName}} 乙方：{{companyName}}）
      const cur = this.form.body || ''
      this.form.body = cur && !/\s$/.test(cur) ? cur + ' ' + text : cur + text
    },
    goBack() {
      // 从列表/详情进入时走历史返回（保留筛选/页码）；深链直入时兜底到模板库列表
      const back = this.$router.options.history.state && this.$router.options.history.state.back
      if (typeof back === 'string' && back.startsWith('/admin/internship/agreement-templates')) this.$router.back()
      else this.$router.push('/admin/internship/agreement-templates')
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
      const res = await agreementTemplateApi.getTemplateDetail(id)
      if (id !== this.$route.params.id) return
      this.loading = false
      if (res.code !== 0) {
        this.error = res.message || '模板不存在或无权查看'
        return
      }
      const d = res.data
      this.detail = d
      this.form = {
        name: d.name || '',
        category: d.category || '',
        version: d.version || 'v1.0',
        scopeCollegeIds: (d.scopeCollegeIds || []).join(','),
        scopeMajorIds: (d.scopeMajorIds || []).join(','),
        scopeGrades: (d.scopeGrades || []).join(','),
        scopeBatchIds: (d.scopeBatchIds || []).join(','),
        body: d.body || '',
        remark: d.remark || ''
      }
    },
    _buildBody() {
      // 变量清单不再靠人工勾选：直接扫正文里实际用到了哪些 {{key}}，保证清单与正文永远一致
      const body = this.form.body || ''
      const variables = this.variablePresets
        .filter((v) => body.includes(this.braced(v.key)))
        .map((v) => ({ key: v.key, label: v.label, example: v.example }))
      return {
        name: this.form.name, category: this.form.category || null, version: this.form.version || 'v1.0',
        scopeCollegeIds: toArr(this.form.scopeCollegeIds), scopeMajorIds: toArr(this.form.scopeMajorIds),
        scopeGrades: toArr(this.form.scopeGrades), scopeBatchIds: toArr(this.form.scopeBatchIds),
        body: this.form.body, variables, remark: this.form.remark
      }
    },
    async onSubmit() {
      if (this.readonly || this.submitting) return
      const { valid } = await this.$refs.tplForm.validate()
      if (!valid) return
      this.submitting = true
      try {
        const payload = this._buildBody()
        const res = this.isEdit
          ? await agreementTemplateApi.updateTemplate(this.$route.params.id, payload)
          : await agreementTemplateApi.createTemplate(payload)
        if (res.code === 0) {
          toast.success('已保存并写入留痕')
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
.atf-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-1) var(--space-6);
}
.atf-grid__full {
  grid-column: 1 / -1;
}
.atf-aside {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.atf-aside code {
  background: var(--bg-subtle, #f1f5f9);
  padding: 0 4px;
  border-radius: 4px;
}
.atf-body-item {
  width: 100%;
}
.atf-body :deep(textarea) {
  font-size: 13px;
  line-height: 1.8;
}
.atf-chip-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}
.atf-chip-row__label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  white-space: nowrap;
}
.atf-chip-row .atf-body-chips {
  margin-bottom: 0;
}
@media (max-width: 960px) {
  .atf-grid {
    grid-template-columns: 1fr;
  }
}
</style>
