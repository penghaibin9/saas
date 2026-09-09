<template>
  <div class="aa-print aa-print-preview">
    <div class="aa-print__bar">
      <span>{{ printTime }}</span>
      <AppPrintButton variant="primary" :disabled="loading || !!error" :handler="doPrint" />
    </div>
    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else class="aa-print__sheet">
      <h1 class="aa-print__title">{{ schoolName }}</h1>
      <h2 class="aa-print__subtitle">{{ typeLabel }}课表{{ keyText ? ('（' + keyText + '）') : '' }}</h2>
      <AaScheduleGrid :items="items" :slots="slots" :editable="false" />
    </div>
  </div>
</template>

<script>
/** 课表打印页（/admin/academic-affairs/print/schedule/:batchId?type=class|teacher|student&key=）：D7 独立打印路由。 */
import { LoadingState, ErrorState } from '@/components/business'
import { AppPrintButton } from '@/components/common'
import AaScheduleGrid from '@/modules/academicAffairs/components/AaScheduleGrid.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'

export default {
  name: 'AaPrintScheduleView',
  components: { LoadingState, ErrorState, AppPrintButton, AaScheduleGrid },
  data() {
    return { loading: true, error: '', schoolName: '职业院校', slots: [], items: [], printTime: '' }
  },
  computed: {
    type() { return this.$route.query.type || 'class' },
    keyText() { return this.$route.query.key || '' },
    typeLabel() { return { teacher: '教师', student: '学生', class: '班级' }[this.type] || '班级' }
  },
  created() {
    const d = new Date()
    this.printTime = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    this.load()
  },
  methods: {
    doPrint() { if (!this.loading && !this.error) window.print() },
    async load() {
      this.loading = true
      this.error = ''
      const batchId = this.$route.params.batchId
      try {
        const [ctxRes, slotRes, viewRes] = await Promise.all([
          academicAffairsApi.getContext(),
          academicAffairsApi.getTimeSlots(),
          this.type === 'teacher'
            ? academicAffairsApi.getScheduleTeacherView(batchId, this.keyText)
            : this.type === 'student'
              ? academicAffairsApi.getScheduleStudentView(batchId, this.keyText)
              : academicAffairsApi.getScheduleClassView(batchId, this.keyText)
        ])
        if (ctxRes.code === 0) this.schoolName = ctxRes.data.tenantBrandConfig.schoolName || '职业院校'
        if (slotRes.code === 0) this.slots = slotRes.data
        if (slotRes.code !== 0 || viewRes.code !== 0) this.error = slotRes.code !== 0 ? (slotRes.message || '节次读取失败') : (viewRes.message || '课表读取失败')
        else this.items = viewRes.data?.items || []
      } catch (exception) {
        this.error = exception?.message || '打印课表读取失败，请重试'
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-print { padding: 24px; background: var(--bg-card); color: #000; }
.aa-print__bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; font-size: 12px; color: #666; }
.aa-print__title { text-align: center; font-size: 22px; margin: 0 0 4px; }
.aa-print__subtitle { text-align: center; font-size: 16px; font-weight: 500; margin: 0 0 16px; }
@media print {
  .aa-print__bar { display: none; }
  .aa-print { padding: 0; }
  @page { size: A4 landscape; margin: 1cm; }
}
</style>

<style src="../styles/print-preview.css"></style>
