<template>
  <GraduationFormPageShell
    :ctx="ctx"
    :title="student ? `过程分组 · ${student.name}` : '批量设置分组'"
    :subtitle="batchMode ? `已选 ${recordIds.length} 人，将统一写入过程分组名称` : '设置学生过程分组'"
    :back-to="backTo"
  >
    <form class="ie-form" @submit.prevent="submit">
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">分组名称 <i>*</i></span>
        <input v-model.trim="groupName" class="ie-in" list="gd-group-suggest" placeholder="如：第1组 / A组答辩预备" />
        <datalist id="gd-group-suggest">
          <option v-for="g in groupOpts" :key="g" :value="g" />
        </datalist>
      </label>
      <p v-if="formError" class="ie-err">{{ formError }}</p>
    </form>
    <template #footer>
      <button type="button" class="mp-btn" @click="$router.push(backTo)">取消</button>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting || !groupName" @click="submit">确认</button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { toast } from '@/utils/toast'

export default {
  name: 'GraduationStudentGroupView',
  components: { GraduationFormPageShell },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      student: null, groupName: '', groupOpts: [], recordIds: [],
      formError: '', submitting: false
    }
  },
  computed: {
    backTo() {
      const panel = this.$route.query.returnPanel || 'grouping'
      return `/admin/graduation/students?panel=${panel}`
    },
    batchMode() {
      return !this.$route.params.id && this.recordIds.length > 0
    }
  },
  async created() {
    const g = await gdStudentApi.getStudentGroups()
    if (g.code === 0) this.groupOpts = g.data || []
    const ids = this.$route.query.ids
    if (ids) this.recordIds = String(ids).split(',').filter(Boolean)
    const id = this.$route.params.id
    if (id) {
      const s = await gdStudentApi.getStudentDetail(id)
      if (s.code === 0) {
        this.student = s.data
        this.groupName = s.data.studentGroup || ''
      }
    }
  },
  methods: {
    async submit() {
      this.formError = ''
      if (!this.groupName) { this.formError = '请填写分组名称'; return }
      this.submitting = true
      try {
        let res
        if (this.student) {
          res = await gdStudentApi.setStudentGroup(this.student.id, { groupName: this.groupName, reason: '' })
        } else {
          res = await gdStudentApi.batchSetStudentGroup({ recordIds: this.recordIds, groupName: this.groupName, reason: '批量分组' })
        }
        if (res.code === 0) {
          toast.success(this.student ? '已更新分组' : `已更新 ${res.data.updated} 人`)
          this.$router.push(this.backTo)
        } else this.formError = res.message
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
