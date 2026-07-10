<template>
  <GraduationFormPageShell
    :ctx="ctx"
    :title="editing ? '编辑' + typeLabel : '新建' + typeLabel"
    :subtitle="'毕设' + typeLabel + ' · 草稿→启用→停用→归档'"
    :back-to="backTo"
  >
    <form class="ie-form" @submit.prevent="save">
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">模板名称 <i>*</i></span>
        <input v-model.trim="form.name" class="ie-in" :placeholder="'如 2026届' + typeLabel" />
      </label>
      <label class="ie-fld"><span class="ie-lbl">版本号</span><input v-model.trim="form.version" class="ie-in" placeholder="v1" /></label>
      <label class="ie-fld"><span class="ie-lbl">适用范围说明</span><input v-model.trim="form.applicableNote" class="ie-in" placeholder="如 软件学院/全校" /></label>
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">模板正文</span>
        <textarea v-model="form.content" class="ie-in" rows="6" :placeholder="'可用占位变量：' + varHint"></textarea>
      </label>
      <div v-if="variables.length" class="ie-fld ie-fld--full">
        <span class="ie-lbl">可用占位变量</span>
        <div class="tpl-vars">
          <button type="button" v-for="v in variables" :key="v" class="tpl-var" @click="insertVar(v)">{{ '{' + v + '}' }}</button>
        </div>
      </div>
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">备注</span><input v-model.trim="form.remark" class="ie-in" /></label>
      <p v-if="formError" class="ie-err">{{ formError }}</p>
    </form>
    <template #footer>
      <button type="button" class="mp-btn" @click="$router.push(backTo)">取消</button>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting" @click="save">{{ editing ? '保存' : '创建' }}</button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { graduationTemplateApi } from '@/modules/graduation/api/graduation-template.api'
import { toast } from '@/utils/toast'

const TYPE_LABEL = { MATERIAL: '材料模板', TASKBOOK: '任务书模板', PROPOSAL: '开题模板' }

export default {
  name: 'GraduationTemplateFormView',
  components: { GraduationFormPageShell },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      editing: null,
      form: { name: '', version: 'v1', applicableNote: '', content: '', remark: '' },
      formError: '', submitting: false, variables: []
    }
  },
  computed: {
    templateType() { return this.$route.query.type || 'MATERIAL' },
    typeLabel() { return TYPE_LABEL[this.templateType] || '材料模板' },
    varHint() { return this.variables.map((v) => '{' + v + '}').join(' ') },
    backTo() { return `/admin/graduation/templates?type=${this.templateType}` }
  },
  async created() {
    const res = await graduationTemplateApi.getVariables()
    if (res.code === 0) this.variables = res.data[this.templateType] || []
    const id = this.$route.params.id
    if (id) {
      const d = await graduationTemplateApi.getTemplate(id)
      if (d.code !== 0) { toast.error(d.message); return }
      this.editing = d.data
      this.form = {
        name: d.data.name, version: d.data.version, applicableNote: d.data.applicableNote,
        content: d.data.content, remark: d.data.remark
      }
    }
  },
  methods: {
    insertVar(v) { this.form.content = (this.form.content || '') + '{' + v + '}' },
    async save() {
      this.formError = ''
      if (!this.form.name) { this.formError = '模板名称必填'; return }
      this.submitting = true
      const body = { templateType: this.templateType, ...this.form }
      const res = this.editing
        ? await graduationTemplateApi.updateTemplate(this.editing.id, body)
        : await graduationTemplateApi.createTemplate(body)
      this.submitting = false
      if (res.code === 0) { toast.success(this.editing ? '已保存' : '已创建'); this.$router.push(this.backTo) }
      else this.formError = res.message || '保存失败'
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.tpl-vars { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-1); }
.tpl-var { font-size: var(--font-size-xs); color: var(--brand-primary); background: var(--primary-50); border: 1px solid var(--primary-100); padding: 3px 8px; border-radius: var(--radius-sm); cursor: pointer; }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
