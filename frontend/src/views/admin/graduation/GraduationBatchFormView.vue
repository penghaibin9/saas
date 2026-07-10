<template>
  <GraduationFormPageShell
    :ctx="ctx"
    :title="editing ? '编辑批次' : '新建毕设批次'"
    :subtitle="editing ? '修改批次基础信息' : '创建一届毕业设计批次'"
    back-to="/admin/graduation/batches"
  >
    <form class="ie-form" @submit.prevent="submit">
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">批次名称 <i>*</i></span><input v-model.trim="form.batchName" class="ie-in" placeholder="如 2026届毕业设计" /></label>
      <label class="ie-fld"><span class="ie-lbl">批次编号 <i>*</i></span><input v-model.trim="form.batchNo" class="ie-in" :disabled="!!editing" placeholder="租户内唯一" /></label>
      <label class="ie-fld"><span class="ie-lbl">届</span><input v-model.trim="form.gradeYear" class="ie-in" placeholder="如 2026届" /></label>
      <label class="ie-fld"><span class="ie-lbl">学年</span><input v-model.trim="form.academicYear" class="ie-in" placeholder="如 2025-2026" /></label>
      <label class="ie-fld"><span class="ie-lbl">计划人数</span><input v-model.number="form.plannedCount" type="number" min="0" class="ie-in" /></label>
      <AppDatePicker v-model="form.startDate" class="ie-fld" label="开始日期" role="start" :end-value="form.endDate" hint="批次启动日" />
      <AppDatePicker v-model="form.endDate" class="ie-fld" label="结束日期" role="end" :start-value="form.startDate" hint="批次收口日" />
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">适用范围</span><input v-model.trim="form.collegeScope" class="ie-in" placeholder="学院/专业范围，留空=全校" /></label>
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">备注</span><textarea v-model.trim="form.remark" class="ie-in" rows="2" /></label>
      <p v-if="formError" class="ie-err">{{ formError }}</p>
    </form>
    <template #footer>
      <button type="button" class="mp-btn" @click="$router.push('/admin/graduation/batches')">取消</button>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting" @click="submit">保存</button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { AppDatePicker } from '@/components/common/date'
import { graduationBatchApi } from '@/modules/graduation/api/graduation-batch.api'
import { toast } from '@/utils/toast'
import { todayDate, formatDate, addDays, validateRange } from '@/utils/dateUtils'

const EMPTY_FORM = () => ({
  batchName: '', batchNo: '', gradeYear: '', academicYear: '', plannedCount: 0,
  startDate: todayDate(),
  endDate: formatDate(addDays(new Date(), 180)),
  collegeScope: '', remark: ''
})

export default {
  name: 'GraduationBatchFormView',
  components: { GraduationFormPageShell, AppDatePicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { editing: null, form: EMPTY_FORM(), formError: '', submitting: false }
  },
  async created() {
    const id = this.$route.params.id
    if (id) {
      const res = await graduationBatchApi.getBatchDetail(id)
      if (res.code !== 0) { toast.error(res.message); return }
      this.editing = res.data
      const row = res.data
      this.form = {
        batchName: row.batchName, batchNo: row.batchNo, gradeYear: row.gradeYear,
        academicYear: row.academicYear, plannedCount: row.plannedCount,
        startDate: (row.startDate || '').slice(0, 10), endDate: (row.endDate || '').slice(0, 10),
        collegeScope: row.collegeScope, remark: row.remark
      }
    }
  },
  methods: {
    async submit() {
      this.formError = ''
      if (!this.form.batchName || !this.form.batchNo) { this.formError = '批次名称与编号必填'; return }
      const range = validateRange(this.form.startDate, this.form.endDate)
      if (!range.ok) { this.formError = range.message; return }
      this.submitting = true
      try {
        const res = this.editing
          ? await graduationBatchApi.updateBatch(this.editing.id, this.form)
          : await graduationBatchApi.createBatch(this.form)
        if (res.code === 0) { toast.success('已保存'); this.$router.push('/admin/graduation/batches') }
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
