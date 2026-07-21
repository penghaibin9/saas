<template>
  <div class="aa-print">
    <div class="aa-print__bar">
      <span>{{ printTime }}</span>
      <AppPrintButton variant="primary" :handler="doPrint" />
    </div>

    <LoadingState v-if="loading" />
    <div v-else-if="error" class="aa-print__err">{{ error }}</div>
    <div v-else class="aa-print__sheet">
      <h1 class="aa-print__title">{{ schoolName }}</h1>
      <h2 class="aa-print__subtitle">学生成绩单</h2>
      <div class="aa-print__meta">
        <span>学生ID：{{ studentId }}</span>
        <span>GPA：{{ data.gpa ?? '—' }}</span>
        <span>已获学分：{{ data.earnedCredits ?? 0 }}</span>
      </div>
      <table class="aa-print__table">
        <thead><tr><th>课程</th><th>学期</th><th>学分</th><th>成绩</th><th>结果</th></tr></thead>
        <tbody>
          <tr v-for="(g, i) in data.items" :key="i">
            <td>{{ g.courseName }}</td>
            <td>{{ g.term || '—' }}</td>
            <td>{{ g.credit }}</td>
            <td>{{ g.score ?? '—' }}</td>
            <td>{{ g.passStatus === 'PASSED' ? '及格' : '不及格' }}</td>
          </tr>
        </tbody>
      </table>
      <div class="aa-print__seal">教务处（盖章）：____________  日期：__________</div>
    </div>
  </div>
</template>

<script>
/** 成绩单打印页（/admin/academic-affairs/print/transcript/:studentId）：D7 独立打印路由，无导航布局。 */
import { LoadingState } from '@/components/business'
import { AppPrintButton } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'

export default {
  name: 'AaTranscriptPrintView',
  components: { LoadingState, AppPrintButton },
  data() {
    return { loading: true, error: '', schoolName: '职业院校', data: { items: [], gpa: null, earnedCredits: 0 }, printTime: '' }
  },
  computed: {
    studentId() { return this.$route.params.studentId }
  },
  created() {
    const d = new Date()
    this.printTime = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    this.load()
  },
  methods: {
    doPrint() { window.print() },
    async load() {
      const [ctxRes, trRes] = await Promise.all([
        academicAffairsApi.getContext(),
        academicAffairsApi.getTranscript(this.studentId)
      ])
      if (ctxRes.code === 0) this.schoolName = ctxRes.data.tenantBrandConfig.schoolName || '职业院校'
      if (trRes.code === 0) this.data = trRes.data
      else this.error = trRes.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-print { padding: 24px; max-width: 800px; margin: 0 auto; color: #000; background: #fff; }
.aa-print__bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; font-size: 12px; color: #666; }
.aa-print__err { color: var(--danger-600, #f53f3f); }
.aa-print__title { text-align: center; font-size: 22px; margin: 0 0 4px; }
.aa-print__subtitle { text-align: center; font-size: 16px; font-weight: 500; margin: 0 0 12px; }
.aa-print__meta { display: flex; justify-content: center; gap: 24px; margin-bottom: 16px; font-size: 14px; }
.aa-print__table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
.aa-print__table th, .aa-print__table td { border: 1px solid #333; padding: 8px 12px; font-size: 14px; text-align: left; }
.aa-print__table th { background: #f5f5f5; font-weight: 500; }
.aa-print__seal { margin-top: 32px; text-align: right; font-size: 14px; }
@media print {
  .aa-print__bar { display: none; }
  .aa-print { padding: 0; }
  @page { size: A4; margin: 1.5cm; }
}
</style>
