<template>
  <GraduationFormPageShell
    :ctx="ctx"
    :title="student ? `答辩组 · ${student.name}` : '分配答辩组'"
    subtitle="答辩组来自「答辩安排」模块真实数据"
    :back-to="backTo"
  >
    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <form v-else class="ie-form" @submit.prevent="submit">
      <p class="ie-hint">答辩组来自「答辩安排」模块真实数据；分配后自动更新组内人数。</p>
      <div class="ie-fld ie-fld--full"><span class="ie-lbl">答辩组 <i>*</i></span>
        <AppRemoteSelect v-model="defenseGroupId" :options="groupOptions" placeholder="按组名 / 日期 / 地点搜索答辩组" />
      </div>
      <p v-if="formError" class="ie-err">{{ formError }}</p>
    </form>
    <template v-if="student" #footer>
      <button type="button" class="mp-btn" @click="$router.push(backTo)">取消</button>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting || !defenseGroupId" @click="submit">确认分配</button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { LoadingState, ErrorState } from '@/components/business'
import { AppRemoteSelect } from '@/components/common'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { toast } from '@/utils/toast'

export default {
  name: 'GraduationStudentDefenseView',
  components: { GraduationFormPageShell, LoadingState, ErrorState, AppRemoteSelect },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', student: null,
      defenseGroupId: '', defenseOpts: [], formError: '', submitting: false
    }
  },
  computed: {
    groupOptions() {
      return this.defenseOpts.map((g) => ({ label: `${g.groupName} · ${g.defenseDate || '日期待定'} · ${g.location || '地点待定'}（${g.studentCount}人）`, value: g.id }))
    },
    backTo() {
      const panel = this.$route.query.returnPanel || 'defense'
      return `/admin/graduation/students?panel=${panel}`
    }
  },
  created() { this.load() },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const id = this.$route.params.id
      const s = await gdStudentApi.getStudentDetail(id)
      if (s.code !== 0) { this.error = s.message; this.loading = false; return }
      this.student = s.data
      this.defenseGroupId = s.data.defenseGroupId || ''
      const d = await gdStudentApi.getDefenseGroups()
      if (d.code === 0) this.defenseOpts = d.data
      else this.defenseOpts = []
      this.loading = false
    },
    async submit() {
      this.formError = ''
      this.submitting = true
      try {
        const res = await gdStudentApi.assignDefenseGroup(this.student.id, { defenseGroupId: this.defenseGroupId, reason: '' })
        if (res.code === 0) { toast.success('已分配答辩组'); this.$router.push(this.backTo) }
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
