<template>
  <GraduationFormPageShell
    :ctx="ctx"
    :title="editing ? '编辑导师' : '申报导师'"
    subtitle="导师资格申报 · 容量 / 方向 / 联系方式"
    back-to="/admin/graduation/mentors"
  >
    <form class="ie-form" @submit.prevent="submit">
      <label class="ie-fld"><span class="ie-lbl">教师工号 <i>*</i></span><input v-model.trim="form.teacherNo" class="ie-in" :disabled="!!editing" /></label>
      <label class="ie-fld"><span class="ie-lbl">教师姓名 <i>*</i></span><input v-model.trim="form.teacherName" class="ie-in" /></label>
      <label class="ie-fld"><span class="ie-lbl">导师类型</span>
        <AppSelect v-model="form.mentorType" :options="MENTOR_TYPE" />
      </label>
      <label class="ie-fld"><span class="ie-lbl">职称</span><input v-model.trim="form.title" class="ie-in" /></label>
      <label class="ie-fld"><span class="ie-lbl">所属学院</span><input v-model.trim="form.collegeName" class="ie-in" /></label>
      <label class="ie-fld"><span class="ie-lbl">所属专业</span><input v-model.trim="form.majorName" class="ie-in" /></label>
      <label class="ie-fld"><span class="ie-lbl">最大指导人数</span><input v-model.number="form.maxCapacity" type="number" min="1" class="ie-in" /></label>
      <label class="ie-fld"><span class="ie-lbl">联系电话</span><input v-model.trim="form.phone" class="ie-in" /></label>
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">指导方向</span><input v-model.trim="form.researchDirection" class="ie-in" placeholder="如 Web 开发 / 嵌入式系统" /></label>
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">备注</span><textarea v-model.trim="form.remark" class="ie-in" rows="2" /></label>
      <p v-if="formError" class="ie-err">{{ formError }}</p>
    </form>
    <template #footer>
      <button type="button" class="mp-btn" @click="$router.push('/admin/graduation/mentors')">取消</button>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting" @click="submit">保存</button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { graduationMentorApi } from '@/modules/graduation/api/graduation-mentor.api'
import { MENTOR_TYPE } from '@/modules/graduation/constants/graduation-mentor.constants'
import { AppSelect } from '@/components/common'
import { toast } from '@/utils/toast'

const EMPTY_FORM = () => ({
  teacherNo: '', teacherName: '', mentorType: 'INTERNAL', title: '', collegeName: '',
  majorName: '', researchDirection: '', maxCapacity: 8, phone: '', remark: ''
})

export default {
  name: 'GraduationMentorFormView',
  components: { GraduationFormPageShell, AppSelect },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { MENTOR_TYPE, editing: null, form: EMPTY_FORM(), formError: '', submitting: false }
  },
  async created() {
    const id = this.$route.params.id
    if (id) {
      const res = await graduationMentorApi.getMentorDetail(id)
      if (res.code !== 0) { toast.error(res.message); return }
      this.editing = res.data
      const row = res.data
      this.form = {
        teacherNo: row.teacherNo, teacherName: row.teacherName, mentorType: row.mentorType,
        title: row.title, collegeName: row.collegeName, majorName: row.majorName,
        researchDirection: row.researchDirection, maxCapacity: row.maxCapacity,
        phone: row.phone || '', remark: row.remark || ''
      }
    }
  },
  methods: {
    async submit() {
      this.formError = ''
      if (!this.form.teacherNo || !this.form.teacherName) { this.formError = '教师工号与姓名必填'; return }
      this.submitting = true
      try {
        const res = this.editing
          ? await graduationMentorApi.updateMentor(this.editing.id, this.form)
          : await graduationMentorApi.createMentor(this.form)
        if (res.code === 0) { toast.success('已保存'); this.$router.push('/admin/graduation/mentors') }
        else this.formError = res.message
      } finally { this.submitting = false }
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
