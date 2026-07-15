<template>
  <div class="aa-print">
    <div class="aa-print__bar">
      <span>{{ printTime }}</span>
      <button v-if="!loading && !error" class="mp-btn mp-btn--primary" @click="doPrint">打印</button>
    </div>
    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" />
    <div v-else class="aa-print__sheet">
      <h1 class="aa-print__title">{{ schoolName }}</h1>
      <h2 class="aa-print__subtitle">补考安排表{{ data.termCode ? '（' + data.termCode + '）' : '' }}</h2>
      <p class="aa-print__meta">批次：{{ data.batchName }}　打印时间：{{ printTime }}</p>
      <table class="aa-print__table">
        <thead>
          <tr>
            <th>序号</th><th>学号</th><th>姓名</th><th>课程</th><th>考试日期</th><th>时间</th><th>状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(s, i) in data.students" :key="i">
            <td>{{ i + 1 }}</td>
            <td>{{ s.studentNo }}</td>
            <td>{{ s.studentName }}</td>
            <td>{{ s.courseName }}</td>
            <td>{{ s.examDate || '待补充' }}</td>
            <td>{{ s.startTime ? `${s.startTime}-${s.endTime || ''}` : '待补充' }}</td>
            <td>{{ s.status }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="!data.students.length" class="aa-print__empty">该批次暂无补考学生名单</p>
    </div>
  </div>
</template>

<script>
/** 补考安排表打印页（三级施工卡 11-材料归档 D7）：/admin/academic-affairs/makeup/batches/:id/print，独立打印路由。 */
import { LoadingState, ErrorState } from '@/components/business'
import { academicAffairsApi, academicAffairsMakeupApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'

export default {
  name: 'AaMakeupPrintView',
  components: { LoadingState, ErrorState },
  data() {
    return { loading: true, error: '', schoolName: '职业院校', printTime: '', data: { students: [] } }
  },
  created() {
    const d = new Date()
    this.printTime = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    this.load()
  },
  methods: {
    doPrint() { window.print() },
    async load() {
      const batchId = this.$route.params.id
      const [ctxRes, dataRes] = await Promise.all([academicAffairsApi.getContext(), api.printData(batchId)])
      if (ctxRes.code === 0) this.schoolName = ctxRes.data.tenantBrandConfig.schoolName || '职业院校'
      if (dataRes.code === 0) this.data = { ...dataRes.data, students: dataRes.data.students || [] }
      else this.error = dataRes.message || '加载失败'
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-print { padding: 24px; background: #fff; color: #000; }
.aa-print__bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; font-size: 12px; color: #666; }
.aa-print__title { text-align: center; font-size: 22px; margin: 0 0 4px; }
.aa-print__subtitle { text-align: center; font-size: 16px; font-weight: 500; margin: 0 0 8px; }
.aa-print__meta { text-align: center; font-size: 12px; color: #555; margin: 0 0 16px; }
.aa-print__table { width: 100%; border-collapse: collapse; font-size: 13px; }
.aa-print__table th, .aa-print__table td { border: 1px solid #999; padding: 6px 8px; text-align: center; }
.aa-print__table th { background: #f2f2f2; }
.aa-print__empty { text-align: center; color: #888; margin-top: 24px; }
@media print {
  .aa-print__bar { display: none; }
  .aa-print { padding: 0; }
  @page { size: A4 portrait; margin: 1.5cm; }
}
</style>
