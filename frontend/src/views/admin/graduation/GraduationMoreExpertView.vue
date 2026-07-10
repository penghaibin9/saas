<template>
  <GraduationFormPageShell
    :ctx="ctx"
    title="新增答辩专家"
    subtitle="评委库 + 回避规则"
    back-to="/admin/graduation/more?panel=experts"
  >
    <form class="ie-form" @submit.prevent="submit">
      <label class="ie-fld"><span class="ie-lbl">专家姓名 <i>*</i></span><input v-model.trim="form.expertName" class="ie-in" /></label>
      <label class="ie-fld"><span class="ie-lbl">职称</span><input v-model.trim="form.title" class="ie-in" placeholder="如 教授/副教授" /></label>
      <label class="ie-fld"><span class="ie-lbl">所属学院</span><input v-model.trim="form.collegeName" class="ie-in" /></label>
      <label class="ie-fld"><span class="ie-lbl">是否校外</span>
        <select v-model="form.isExternal" class="ie-in"><option :value="false">校内</option><option :value="true">校外</option></select>
      </label>
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">回避说明</span><input v-model.trim="form.avoidNote" class="ie-in" placeholder="如 不评本院学生 / 回避亲属" /></label>
      <p v-if="formError" class="ie-err">{{ formError }}</p>
    </form>
    <template #footer>
      <button type="button" class="mp-btn" @click="$router.push('/admin/graduation/more?panel=experts')">取消</button>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting" @click="submit">保存</button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { graduationMoreApi } from '@/modules/graduation/api/graduation-more.api'
import { toast } from '@/utils/toast'

export default {
  name: 'GraduationMoreExpertView',
  components: { GraduationFormPageShell },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      form: { expertName: '', title: '', collegeName: '', isExternal: false, avoidNote: '' },
      formError: '', submitting: false
    }
  },
  methods: {
    async submit() {
      this.formError = ''
      if (!this.form.expertName) { this.formError = '专家姓名必填'; return }
      this.submitting = true
      const res = await graduationMoreApi.createExpert(this.form)
      this.submitting = false
      if (res.code === 0) { toast.success('已新增专家'); this.$router.push('/admin/graduation/more?panel=experts') }
      else this.formError = res.message
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
