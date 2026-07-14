<template>
  <div class="aaesp">
    <div class="aaesp-toolbar no-print">
      <AppTextInput v-model="roomId" placeholder="考场 ID" style="max-width:160px" />
      <AppButton size="small" variant="primary" @click="load">载入座位表</AppButton>
      <AppButton v-if="rows.length" size="small" variant="ghost" @click="print">打印</AppButton>
      <span class="aaesp-hint">座位表专页 + 门贴/准考证（A4 打印）</span>
    </div>

    <div v-if="rows.length" class="aaesp-sheet">
      <h2 class="aaesp-title">考场座位表 / 门贴</h2>
      <p class="aaesp-sub">考场 {{ roomId }} · 共 {{ rows.length }} 人</p>
      <table class="aaesp-table">
        <thead><tr><th>座位号</th><th>准考证号</th><th>学号</th><th>姓名</th><th>考勤</th></tr></thead>
        <tbody>
          <tr v-for="s in rows" :key="s.seatNo">
            <td>{{ s.seatNo }}</td><td>{{ s.admissionNo }}</td><td>{{ s.studentNo }}</td>
            <td>{{ s.studentName }}</td><td>{{ attLabel(s.attendanceStatus) }}</td>
          </tr>
        </tbody>
      </table>
      <div class="aaesp-tickets">
        <div v-for="s in rows" :key="'t' + s.seatNo" class="aaesp-ticket">
          <div class="aaesp-ticket-title">准考证</div>
          <div>姓名：{{ s.studentName }}</div>
          <div>学号：{{ s.studentNo }}</div>
          <div>准考证号：{{ s.admissionNo }}</div>
          <div>考场：{{ roomId }} · 座位：{{ s.seatNo }}</div>
        </div>
      </div>
    </div>
    <EmptyState v-else title="输入考场 ID 载入" description="座位表/准考证数据来自考场铺位结果" />
  </div>
</template>

<script>
/** 考务座位表/准考证打印（/admin/academic-affairs/exam/print/seating）：座位表专页 + 门贴/准考证 A4 打印。 */
import { EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppTextInput } from '@/components/common'
import { academicAffairsExamApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaExamSeatingPrintView',
  components: { EmptyState, AppButton, AppTextInput },
  data() { return { roomId: this.$route.query.roomId || '', rows: [] } },
  created() { if (this.roomId) this.load() },
  methods: {
    attLabel(s) { return { NOT_STARTED: '—', PRESENT: '出席', ABSENT: '缺考', DISCIPLINE_VIOLATION: '违纪' }[s] || s },
    async load() {
      if (!this.roomId) { toast.error('请填考场 ID'); return }
      const res = await api.roomSeats(this.roomId)
      if (res.code === 0) this.rows = res.data.items || []
      else toast.error(res.message)
    },
    print() { window.print() }
  }
}
</script>

<style scoped>
.aaesp { padding: 16px; }
.aaesp-toolbar { display: flex; gap: 8px; align-items: center; margin-bottom: 16px; }
.aaesp-hint { color: var(--text-secondary, #64748b); font-size: 13px; }
.aaesp-title { text-align: center; margin: 0 0 4px; }
.aaesp-sub { text-align: center; color: var(--text-secondary, #64748b); margin: 0 0 12px; }
.aaesp-table { width: 100%; border-collapse: collapse; }
.aaesp-table th, .aaesp-table td { border: 1px solid #999; padding: 6px 8px; text-align: center; font-size: 13px; }
.aaesp-tickets { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-top: 20px; }
.aaesp-ticket { border: 1px dashed #999; border-radius: 6px; padding: 12px; font-size: 13px; }
.aaesp-ticket-title { font-weight: 700; text-align: center; margin-bottom: 6px; }
@media print { .no-print { display: none !important; } .aaesp-ticket { page-break-inside: avoid; } }
</style>
