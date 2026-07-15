<template>
  <ModulePageShell
    title="学生成绩单"
    subtitle="教务视角查看学生已发布课程成绩（读侧）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="aa-reg-search">
        <input v-model.trim="kw" class="aa-input aa-input--grow" placeholder="按姓名/学号检索学生" @keyup.enter="searchStudents" />
        <button class="mp-btn" :disabled="searching" @click="searchStudents">检索</button>
      </div>
      <ul v-if="candidates.length" class="aa-cand-list">
        <li v-for="s in candidates" :key="s.studentId" class="aa-cand-item">
          <span>{{ s.realName }} · 学号 {{ s.studentNo }}</span>
          <button class="mp-link" @click="pick(s)">查看成绩单</button>
        </li>
      </ul>

      <template v-if="studentId">
        <LoadingState v-if="loading" />
        <template v-else-if="data">
          <div class="aa-metric-grid">
            <AppMetricCard title="已获学分" :value="data.earnedCredits ?? data.totalCredits ?? 0" />
            <AppMetricCard title="挂科门次" :value="data.failCount ?? 0" />
          </div>
          <AppSectionCard :title="`${name || '学生'} 的成绩单`">
            <template #header-extra>
              <button class="mp-btn" :disabled="!data.items.length" @click="exportPanel = !exportPanel">导出成绩单</button>
            </template>
            <div v-if="exportPanel" class="aa-export-bar">
              <input v-model.trim="exportPurpose" class="aa-input aa-input--grow" placeholder="导出用途（必填，≥5字，如：学院例会核对，将写入审计）" />
              <button class="mp-btn mp-btn--primary" :disabled="exporting" @click="doExport">{{ exporting ? '导出中…' : '确认导出 xlsx' }}</button>
            </div>
            <p v-if="data.note" class="mp-note">{{ data.note }}</p>
            <EmptyState v-if="!data.items.length && !data.note" title="暂无成绩记录" description="学生还没有已发布的课程成绩" />
            <table v-else-if="data.items.length" class="aa-course-table">
              <thead><tr><th>课程</th><th>学期</th><th>学分</th><th>成绩</th><th>结果</th></tr></thead>
              <tbody>
                <tr v-for="(g, i) in data.items" :key="i">
                  <td>{{ g.courseName }}</td>
                  <td>{{ g.term || '—' }}</td>
                  <td>{{ g.credit }}</td>
                  <td>{{ g.score ?? '—' }}</td>
                  <td><AppStatusTag :type="g.passStatus === 'PASSED' ? 'success' : 'danger'">{{ g.passStatus === 'PASSED' ? '及格' : '不及格' }}</AppStatusTag></td>
                </tr>
              </tbody>
            </table>
          </AppSectionCard>
        </template>
      </template>
      <EmptyState v-else-if="!candidates.length" title="选择学生查看成绩单" description="用上方检索找到学生" />
    </div>
  </ModulePageShell>
</template>

<script>
/** 学生成绩单（/admin/academic-affairs/transcript）：GET /students/:id/transcript。 */
import { ModulePageShell, LoadingState, EmptyState } from '@/components/business'
import { AppMetricCard, AppSectionCard, AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaTranscriptView',
  components: { ModulePageShell, LoadingState, EmptyState, AppMetricCard, AppSectionCard, AppStatusTag },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      kw: '', searching: false, candidates: [],
      studentId: this.$route.query.studentId || '', name: this.$route.query.name || '',
      loading: false, data: null,
      exportPanel: this.$route.query.action === 'export', exportPurpose: '', exporting: false
    }
  },
  created() {
    if (this.studentId) this.load()
  },
  methods: {
    async searchStudents() {
      if (this.searching) return
      this.searching = true
      const res = await academicAffairsApi.getRoster({ keyword: this.kw || undefined, page: 1, pageSize: 20 })
      this.candidates = res.code === 0 ? res.data.list : []
      this.searching = false
    },
    pick(s) {
      this.studentId = s.studentId
      this.name = s.realName
      this.candidates = []
      this.load()
    },
    async load() {
      this.loading = true
      const res = await academicAffairsApi.getTranscript(this.studentId)
      if (res.code === 0) this.data = res.data
      else toast.error(res.message || '加载失败')
      this.loading = false
    },
    async doExport() {
      if (!this.exportPurpose || this.exportPurpose.trim().length < 5) {
        toast.error('导出用途必填且不少于 5 个字')
        return
      }
      this.exporting = true
      const res = await academicAffairsApi.exportTranscript(this.studentId, this.exportPurpose.trim())
      this.exporting = false
      if (res.code !== 0) {
        toast.error(res.message || '导出失败')
        return
      }
      const href = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = href
      a.download = `${this.name || '学生'}-成绩单-${Date.now()}.xlsx`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(href)
      toast.success('导出成功，已写入审计')
      this.exportPanel = false
      this.exportPurpose = ''
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-reg-search { display: flex; gap: 12px; align-items: center; }
.aa-input { height: 34px; padding: 0 12px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 14px; box-sizing: border-box; }
.aa-input--grow { flex: 1; }
.aa-cand-list { list-style: none; margin: 0; padding: 0; border: 1px solid var(--border-100, #f0f1f2); border-radius: 6px; }
.aa-cand-item { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; border-bottom: 1px solid var(--border-100, #f0f1f2); font-size: 13px; }
.aa-cand-item:last-child { border-bottom: none; }
.aa-metric-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
.aa-export-bar { display: flex; gap: 12px; align-items: center; margin-bottom: 14px; padding: 10px 12px; background: var(--fill-50, #f7f8fa); border-radius: 6px; }
.aa-course-table { width: 100%; border-collapse: collapse; }
.aa-course-table th, .aa-course-table td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border-100, #f0f1f2); font-size: 14px; }
.aa-course-table th { color: var(--text-500, #646a73); font-weight: 500; font-size: 13px; }
</style>
