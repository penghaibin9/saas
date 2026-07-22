<template>
  <div class="aa-print">
    <div class="aa-print__bar">
      <span>{{ printTime }}</span>
      <AppPrintButton variant="primary" :handler="doPrint" />
    </div>
    <LoadingState v-if="loading" />
    <div v-else class="aa-print__sheet">
      <h1 class="aa-print__title">{{ schoolName }}</h1>
      <h2 class="aa-print__subtitle">{{ typeLabel }}课表{{ keyText ? ('（' + keyText + '）') : '' }}</h2>
      <AaScheduleGrid :items="items" :slots="slots" :editable="false" />
    </div>
  </div>
</template>

<script>
/** 课表打印页（/admin/academic-affairs/print/schedule/:batchId?type=class|teacher&key=）：D7 独立打印路由。 */
import { LoadingState } from '@/components/business'
import { AppPrintButton } from '@/components/common'
import AaScheduleGrid from '@/modules/academicAffairs/components/AaScheduleGrid.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'

export default {
  name: 'AaPrintScheduleView',
  components: { LoadingState, AppPrintButton, AaScheduleGrid },
  data() {
    return { loading: true, schoolName: '职业院校', slots: [], items: [], printTime: '' }
  },
  computed: {
    type() { return this.$route.query.type || 'class' },
    keyText() { return this.$route.query.key || '' },
    typeLabel() { return this.type === 'teacher' ? '教师' : '班级' }
  },
  created() {
    const d = new Date()
    this.printTime = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    this.load()
  },
  methods: {
    doPrint() { window.print() },
    async load() {
      const batchId = this.$route.params.batchId
      const [ctxRes, slotRes, viewRes] = await Promise.all([
        academicAffairsApi.getContext(),
        academicAffairsApi.getTimeSlots(),
        this.type === 'teacher'
          ? academicAffairsApi.getScheduleTeacherView(batchId, this.keyText)
          : academicAffairsApi.getScheduleClassView(batchId, this.keyText)
      ])
      if (ctxRes.code === 0) this.schoolName = ctxRes.data.tenantBrandConfig.schoolName || '职业院校'
      if (slotRes.code === 0) this.slots = slotRes.data
      if (viewRes.code === 0) this.items = (viewRes.data && viewRes.data.items) || []
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
.aa-print__subtitle { text-align: center; font-size: 16px; font-weight: 500; margin: 0 0 16px; }
@media print {
  .aa-print__bar { display: none; }
  .aa-print { padding: 0; }
  @page { size: A4 landscape; margin: 1cm; }
}
</style>
