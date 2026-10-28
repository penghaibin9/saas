<template>
  <ModulePageShell class="atf-page"
    :title="isEdit ? '编辑协议模板' : '新建协议模板'"
    :subtitle="pageSubtitle"
    watermark-purpose="实习协议模板管理"
  >
    <template #actions>
      <AppButton variant="ghost" :disabled="submitting" @click="goBack">{{ isEdit ? '返回模板详情' : '返回模板库' }}</AppButton>
      <AppButton v-if="!loading && !error && !readonly" variant="primary" :disabled="!variablesReady" :loading="submitting" @click="onSubmit">{{ isEdit ? '保存修改' : '保存草稿' }}</AppButton>
    </template>

    <ErrorState v-if="error" :description="error" @retry="init" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-stack">
      <AppInlineAlert
        v-if="readonly"
        type="warning"
        title="当前模板不可编辑"
        :description="detail?.status === 'ARCHIVED' ? '模板已归档，仅可查看原有内容。' : '当前身份没有协议模板管理权限。'"
      />
      <p v-if="saveError" class="atf-error" role="alert">{{ saveError }}。本页输入已保留。</p>
      <p v-if="variablesError" class="atf-error" role="alert">{{ variablesError }} <AppButton variant="ghost" @click="loadVariables">重试</AppButton></p>
      <nav class="atf-sections" aria-label="模板编辑分区"><AppButton variant="ghost" @click="focusSection('info')">基本信息与范围</AppButton><AppButton variant="ghost" @click="focusSection('body')">协议正文与变量</AppButton></nav>

      <AppForm
        class="atf-form"
        ref="tplForm"
        :model="form"
        :rules="formRules"
        layout="vertical"
        label-width="112px"
        @submit="onSubmit"
      >
        <!-- 基本信息 -->
        <section ref="info" class="mp-card" tabindex="-1">
          <div class="mp-card__head"><span class="mp-card__title">基本信息</span></div>
          <div class="mp-card__body">
            <div class="atf-grid">
              <AppFormItem class="atf-grid__full" label="模板名称" prop="name" required>
                <AppTextInput v-model="form.name" :disabled="readonly || submitting" placeholder="如 顶岗实习三方协议" />
              </AppFormItem>
              <AppFormItem label="协议类型" prop="category">
                <AppSelect v-model="form.category" :options="categoryOptions" placeholder="" :disabled="readonly || submitting" />
              </AppFormItem>
              <AppFormItem label="版本号" prop="version">
                <AppTextInput v-model="form.version" :disabled="readonly || submitting" placeholder="v1.0" />
              </AppFormItem>
              <AppFormItem label="适用学院" prop="scopeCollegeIds">
                <AppCollegePicker v-model="form.scopeCollegeIds" multiple :disabled="readonly || submitting" placeholder="不限学院" @change="markDirty" />
              </AppFormItem>
              <AppFormItem label="适用专业" prop="scopeMajorIds">
                <AppMajorPicker v-model="form.scopeMajorIds" multiple :disabled="readonly || submitting" placeholder="不限专业" @change="markDirty" />
              </AppFormItem>
              <AppFormItem label="适用年级" prop="scopeGrades">
                <AppGradePicker v-model="form.scopeGrades" multiple :disabled="readonly || submitting" placeholder="不限年级" @change="markDirty" />
              </AppFormItem>
              <AppFormItem label="适用批次" prop="scopeBatchIds">
                <AppInternshipBatchPicker v-model="form.scopeBatchIds" multiple :disabled="readonly || submitting" placeholder="不限批次" @change="markDirty" />
              </AppFormItem>
              <AppFormItem class="atf-grid__full" label="备注" prop="remark">
                <AppTextInput v-model="form.remark" :disabled="readonly || submitting" placeholder="备注（可选）" />
              </AppFormItem>
            </div>
          </div>
        </section>

        <!-- 正文为主工作区；插入工具保留当前选区，不要求手打占位符。 -->
        <section ref="body" class="mp-card" tabindex="-1">
          <div class="mp-card__head">
            <span class="mp-card__title">模板正文</span>
            <span class="atf-aside">在光标处插入条款或变量</span>
          </div>
          <div class="mp-card__body">
            <AppFormItem class="atf-body-item" label="正文内容" prop="body">
              <details v-if="!readonly" class="atf-insert-group">
                <summary>常用条款<span>选择后插入正文</span></summary>
                <AppTemplateChips class="atf-body-chips" :options="AGREEMENT_CLAUSE" size="compact" @pick="onPickClause" />
              </details>
              <details v-if="!readonly && variableChipOptions.length" class="atf-insert-group" open>
                <summary>插入变量<span>生成协议时自动填入实际信息</span></summary>
                <AppTemplateChips class="atf-body-chips" :options="variableChipOptions" size="compact" @pick="onPickVariable" />
              </details>
              <AppTextarea
                ref="bodyInput"
                v-model="form.body"
                class="atf-body"
                :rows="16"
                :disabled="readonly || submitting"
                :placeholder="bodyPlaceholder"
                @click="rememberBodySelection"
                @keyup="rememberBodySelection"
                @select="rememberBodySelection"
                @blur="rememberBodySelection"
              />
              <p class="atf-editor-note">{{ (form.body || '').length }} 字<span>保存为草稿后，可在模板详情中核对并启用。</span></p>
            </AppFormItem>
          </div>
        </section>

        <AppSubmitBar
          class="atf-submit"
          :loading="submitting"
          :disabled="readonly || !variablesReady"
          :submit-text="isEdit ? '保存修改' : '保存草稿'"
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
import { canCode } from '@/modules/internship/composables/permission'
import { toast } from '@/utils/toast'
import { AGREEMENT_CLAUSE } from '@/modules/internship/constants/presetPrompts'
import { AppCollegePicker, AppMajorPicker, AppGradePicker, AppInternshipBatchPicker } from '@/components/common/picker'

const CATEGORY_OPTS = ['三方协议', '顶岗实习协议', '安全责任书', '实习承诺书', '保密协议']
const blankForm = () => ({
  name: '', category: '', version: 'v1.0', scopeCollegeIds: [], scopeMajorIds: [],
  scopeGrades: [], scopeBatchIds: [], body: '', remark: ''
})

export default {
  name: 'AgreementTemplateFormView',
  props: { ctx: { type: Object, default: () => ({}) } },
  components: {
    ModulePageShell, LoadingState, ErrorState, AppButton,
    AppCollegePicker, AppMajorPicker, AppGradePicker, AppInternshipBatchPicker,
    AppInlineAlert, AppForm, AppFormItem, AppTextInput, AppSelect, AppTextarea, AppSubmitBar, AppTemplateChips
  },
  data() {
    return {
      AGREEMENT_CLAUSE,
      loadTicket: 0, variableTicket: 0, saveError: '', variablesReady: false, variablesError: '', bodySelection: null,
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
      return !Array.isArray(this.ctx?.permissionPatterns) || !canCode(this.ctx, 'internship.agreement.template.manage') || (this.isEdit && !!this.detail && this.detail.status === 'ARCHIVED')
    },
    pageSubtitle() {
      if (this.isEdit) {
        return this.detail ? `${this.detail.name}（${this.detail.category || '未分类'} · ${this.detail.version}）` : ''
      }
      return '设置模板信息与适用范围，编写可复用的协议正文。'
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
    this.loadVariables()
    this.init()
  },
  beforeUnmount() { this.loadTicket++; this.variableTicket++ },
  methods: {
    focusSection(key) { this.$refs[key]?.scrollIntoView({ block: 'start', behavior: 'smooth' }); this.$refs[key]?.focus({ preventScroll: true }) },
    async loadVariables() {
      const ticket = ++this.variableTicket
      this.variablesReady = false; this.variablesError = ''
      try {
        const res = await agreementTemplateApi.getVariablePresets()
        if (ticket !== this.variableTicket) return
        if (res.code !== 0) throw new Error(res.message || '变量列表加载失败，请重试')
        this.variablePresets = res.data || []; this.variablesReady = true
      } catch (error) { if (ticket === this.variableTicket) this.variablesError = error.message || '变量列表加载失败，请重试' }
    },
    markDirty() { window.__SAAS_DIRTY_FORM_GUARD__?.markDirty() },
    braced(key) {
      return '{' + '{' + key + '}' + '}'
    },
    rememberBodySelection(event) {
      const input = event.target
      if (input?.tagName !== 'TEXTAREA') return
      this.bodySelection = { start: input.selectionStart, end: input.selectionEnd }
    },
    insertBodyText(text, clause = false) {
      if (!text || this.readonly || this.submitting) return
      window.__SAAS_DIRTY_FORM_GUARD__?.markDirty()
      const body = this.form.body || ''
      const start = Math.min(this.bodySelection?.start ?? body.length, body.length)
      const end = Math.min(this.bodySelection?.end ?? body.length, body.length)
      const before = body.slice(0, start), after = body.slice(end)
      const inserted = clause ? `${before && !before.endsWith('\n') ? '\n' : ''}${text}${after && !after.startsWith('\n') ? '\n' : ''}` : text
      this.form.body = before + inserted + after
      const caret = start + inserted.length
      this.bodySelection = { start: caret, end: caret }
      this.$nextTick(() => {
        const input = this.$refs.bodyInput?.$el?.querySelector('textarea')
        input?.focus({ preventScroll: true }); input?.setSelectionRange(caret, caret)
      })
    },
    onPickClause(text) { this.insertBodyText(text, true) },
    onPickVariable(text) { this.insertBodyText(text) },
    goBack() { if (!this.submitting) this.$router.push({ path: this.isEdit ? `/admin/internship/agreement-templates/${this.$route.params.id}` : '/admin/internship/agreement-templates', query: { ...this.$route.query } }) },
    async init() {
      const ticket = ++this.loadTicket
      this.error = ''; this.saveError = ''
      this.bodySelection = null
      if (!this.isEdit) {
        this.detail = null
        this.form = blankForm()
        this.loading = false
        return
      }
      this.loading = true
      const id = this.$route.params.id
      try {
      const res = await agreementTemplateApi.getTemplateDetail(id)
      if (ticket !== this.loadTicket || id !== this.$route.params.id) return
      if (res.code !== 0 || !res.data) throw new Error(res.message || '模板不存在或无权查看')
      const d = res.data
      this.detail = d
      this.form = {
        name: d.name || '',
        category: d.category || '',
        version: d.version || 'v1.0',
        scopeCollegeIds: (d.scopeCollegeIds || []).map(String),
        scopeMajorIds: (d.scopeMajorIds || []).map(String),
        scopeGrades: (d.scopeGrades || []).map(String),
        scopeBatchIds: (d.scopeBatchIds || []).map(String),
        body: d.body || '',
        remark: d.remark || ''
      }
      } catch (error) { if (ticket === this.loadTicket) this.error = error.message || '模板加载失败，请重试' }
      finally { if (ticket === this.loadTicket) this.loading = false }
    },
    _buildBody() {
      // 变量清单不再靠人工勾选：直接扫正文里实际用到了哪些 {{key}}，保证清单与正文永远一致
      const body = this.form.body || ''
      const variables = this.variablePresets
        .filter((v) => body.includes(this.braced(v.key)))
        .map((v) => ({ key: v.key, label: v.label, example: v.example }))
      return {
        name: this.form.name, category: this.form.category || null, version: this.form.version || 'v1.0',
        scopeCollegeIds: this.form.scopeCollegeIds, scopeMajorIds: this.form.scopeMajorIds,
        scopeGrades: this.form.scopeGrades, scopeBatchIds: this.form.scopeBatchIds,
        body: this.form.body, variables, remark: this.form.remark
      }
    },
    async onSubmit() {
      if (this.readonly || this.submitting || !this.variablesReady || this.loading || this.error) return
      const ticket = this.loadTicket, id = this.$route.params.id, scope = this.ctx?.ctxKey
      this.submitting = true
      this.saveError = ''
      try {
        const { valid } = await this.$refs.tplForm.validate()
        if (!valid || ticket !== this.loadTicket || scope !== this.ctx?.ctxKey || this.readonly) return
        const payload = this._buildBody()
        const res = this.isEdit
          ? await agreementTemplateApi.updateTemplate(this.$route.params.id, payload)
          : await agreementTemplateApi.createTemplate(payload)
        if (ticket !== this.loadTicket || id !== this.$route.params.id || scope !== this.ctx?.ctxKey) return
        if (res.code === 0 && res.data?.id) {
          window.__SAAS_DIRTY_FORM_GUARD__?.markSaved()
          toast.success(this.isEdit ? '模板修改已保存' : '模板草稿已保存，核对后可启用')
          this.$router.push({ path: `/admin/internship/agreement-templates/${res.data.id}`, query: { ...this.$route.query } })
        } else {
          this.saveError = res.message || '未能确认保存结果，请到模板库核对'
        }
      } catch (error) {
        if (ticket === this.loadTicket) this.saveError = error.message || '保存失败，请重试'
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
.atf-insert-group { border-bottom: 1px solid var(--card-b); padding: 0 0 10px; margin-bottom: 12px; }
.atf-insert-group summary { cursor: pointer; font-size: 13px; font-weight: 600; color: var(--text-primary); padding: 4px 0; }
.atf-insert-group summary span { margin-left: 12px; font-weight: 400; font-size: 12px; color: var(--text-secondary); }
.atf-insert-group[open] summary { margin-bottom: 8px; }
.atf-insert-group summary:focus-visible { outline: 2px solid var(--primary-500); outline-offset: 3px; }
.atf-insert-group .atf-body-chips { margin-bottom: 0; }
.atf-editor-note { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px; margin: 8px 0 0; color: var(--text-secondary); font-size: 12px; line-height: 1.6; }
@media (max-width: 960px) {
  .atf-grid {
    grid-template-columns: 1fr;
  }
}
.atf-page .mp-card { border-radius: 8px; box-shadow: none; margin-bottom: 20px; }.atf-page .mp-card__head { padding: 16px 20px; flex-wrap: wrap; gap: 8px; }.atf-page .mp-card__body { padding: 20px; }.atf-grid { gap: 8px 24px; }.atf-body :deep(textarea) { font-size: 14px; line-height: 1.9; min-height: 380px; }.atf-page :deep(.app-submit-bar) { border-radius: 8px; }
.atf-form { display: grid; grid-template-columns: 320px minmax(0, 1fr); align-items: start; gap: 20px; }
.atf-form section { scroll-margin-top: 16px; }
.atf-sections { display: flex; flex-wrap: wrap; gap: 8px; border-bottom: 1px solid var(--card-b); padding-bottom: 8px; }
.atf-error { margin: 0; color: var(--danger-700, #b91c1c); background: var(--danger-50, #fef2f2); padding: 12px 16px; border-radius: 6px; font-size: 13px; line-height: 1.8; }
.atf-form > .mp-card { min-width: 0; margin-bottom: 0; }.atf-form .atf-grid { grid-template-columns: 1fr; }.atf-form > .atf-submit { grid-column: 1 / -1; margin: 0; width: 100%; box-sizing: border-box; bottom: 0; }
@media (max-width: 1100px) { .atf-form { grid-template-columns: 1fr; } }
</style>
