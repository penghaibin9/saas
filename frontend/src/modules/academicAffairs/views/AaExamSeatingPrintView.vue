<template>
  <div class="aaesp">
    <div class="aaesp-toolbar no-print">
      <AppTextInput v-model="roomId" placeholder="考场 ID" style="max-width:160px" @keyup.enter="load" />
      <AppButton size="small" variant="primary" :disabled="loading" @click="load">
        {{ loading ? '核验中…' : '载入正式打印数据' }}
      </AppButton>
      <AppButton v-if="canPrint" size="small" variant="ghost" @click="print">打印</AppButton>
      <span class="aaesp-hint">仅可打印已发布考务的正式座位表 / 门贴 / 准考证</span>
    </div>

    <div v-if="canPrint" class="aaesp-sheet">
      <div class="aaesp-official">正式发布 · {{ document.batchStatus }}</div>
      <h2 class="aaesp-title">正式考场座位表 / 门贴</h2>
      <p class="aaesp-sub">{{ document.batchName || '考试批次' }} · {{ document.courseName || '考试课程' }}</p>
      <p class="aaesp-sub">
        {{ document.examDate || '日期待定' }} {{ document.startTime || '' }}-{{ document.endTime || '' }}
        · {{ document.classroom || `考场 ${document.examRoomId}` }}
        · 共 {{ document.seatCount }} 人
      </p>
      <div class="aaesp-proof">
        <span>正式发布时间：{{ formatPublishedAt(document.publishedAt) }}</span>
        <span>打印证据：{{ shortIdentity }}</span>
      </div>

      <table class="aaesp-table">
        <thead><tr><th>座位号</th><th>准考证号</th><th>学号</th><th>姓名</th></tr></thead>
        <tbody>
          <tr v-for="s in rows" :key="s.seatNo">
            <td>{{ s.seatNo }}</td>
            <td>{{ s.admissionNo }}</td>
            <td>{{ s.studentNo }}</td>
            <td>{{ s.studentName }}</td>
          </tr>
        </tbody>
      </table>

      <div class="aaesp-tickets">
        <div v-for="s in rows" :key="'t' + s.seatNo" class="aaesp-ticket">
          <div class="aaesp-ticket-title">准考证</div>
          <div>姓名：{{ s.studentName }}</div>
          <div>学号：{{ s.studentNo }}</div>
          <div>准考证号：{{ s.admissionNo }}</div>
          <div>考试：{{ document.courseName || '—' }}</div>
          <div>时间：{{ document.examDate || '—' }} {{ document.startTime || '' }}-{{ document.endTime || '' }}</div>
          <div>考场：{{ document.classroom || document.examRoomId }} · 座位：{{ s.seatNo }}</div>
          <div class="aaesp-ticket-proof">正式打印证据：{{ shortIdentity }}</div>
        </div>
      </div>
    </div>

    <EmptyState
      v-else
      title="输入考场 ID 载入正式打印数据"
      description="系统会先核验考试已发布、课程已确认、考场有效、冻结名单与座位全集一致；任一条件不满足都不会降级打印草稿数据。"
    />
  </div>
</template>

<script>
/** C-W3 考务正式打印：只消费 formal-print provider，禁止回退普通 roomSeats 编排数据。 */
import { EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppTextInput } from '@/components/common'
import { academicAffairsExamPrintApi as api } from '@/modules/academicAffairs/api/academic-exam-formal-print.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaExamSeatingPrintView',
  components: { EmptyState, AppButton, AppTextInput },
  data() {
    return {
      roomId: this.$route.query.roomId || '',
      loading: false,
      document: null,
      rows: []
    }
  },
  computed: {
    canPrint() {
      return this.document?.documentStatus === 'OFFICIAL' && this.rows.length > 0
    },
    shortIdentity() {
      const value = String(this.document?.printIdentity || '')
      if (!value) return '—'
      return value.length > 46 ? `${value.slice(0, 24)}…${value.slice(-16)}` : value
    }
  },
  created() {
    if (this.roomId) this.load()
  },
  methods: {
    formatPublishedAt(value) {
      if (!value) return '—'
      const text = String(value).replace('T', ' ')
      return text.length > 19 ? text.slice(0, 19) : text
    },
    async load() {
      const id = String(this.roomId || '').trim()
      if (!id) {
        toast.error('请填考场 ID')
        return
      }
      this.loading = true
      this.document = null
      this.rows = []
      try {
        const data = await api.formalRoomPrint(id)
        if (!data || data.documentStatus !== 'OFFICIAL') {
          throw new Error('后端未返回正式打印证据，已阻止打印')
        }
        const seats = Array.isArray(data.seats) ? data.seats : []
        if (!seats.length) throw new Error('正式考场没有可打印座位数据')
        this.document = data
        this.rows = seats
      } catch (error) {
        this.document = null
        this.rows = []
        toast.error(error?.message || '正式打印数据核验失败')
      } finally {
        this.loading = false
      }
    },
    print() {
      if (!this.canPrint) {
        toast.error('缺少正式打印证据，禁止打印')
        return
      }
      window.print()
    }
  }
}
</script>

<style scoped>
.aaesp { padding: 16px; }
.aaesp-toolbar { display: flex; gap: 8px; align-items: center; margin-bottom: 16px; flex-wrap: wrap; }
.aaesp-hint { color: var(--text-secondary, #64748b); font-size: 13px; }
.aaesp-sheet { position: relative; }
.aaesp-official { width: fit-content; margin: 0 auto 8px; padding: 3px 10px; border: 1px solid #475569; border-radius: 999px; font-size: 12px; font-weight: 700; letter-spacing: .04em; }
.aaesp-title { text-align: center; margin: 0 0 4px; }
.aaesp-sub { text-align: center; color: var(--text-secondary, #64748b); margin: 3px 0; }
.aaesp-proof { display: flex; justify-content: space-between; gap: 16px; margin: 12px 0; padding: 8px 10px; border: 1px solid #cbd5e1; border-radius: 6px; color: #475569; font-size: 11px; }
.aaesp-table { width: 100%; border-collapse: collapse; }
.aaesp-table th, .aaesp-table td { border: 1px solid #999; padding: 6px 8px; text-align: center; font-size: 13px; }
.aaesp-tickets { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-top: 20px; }
.aaesp-ticket { border: 1px dashed #999; border-radius: 6px; padding: 12px; font-size: 13px; line-height: 1.7; }
.aaesp-ticket-title { font-weight: 700; text-align: center; margin-bottom: 6px; }
.aaesp-ticket-proof { margin-top: 6px; color: #64748b; font-size: 10px; word-break: break-all; }
@media print {
  .no-print { display: none !important; }
  .aaesp { padding: 0; }
  .aaesp-proof { break-inside: avoid; }
  .aaesp-ticket { page-break-inside: avoid; }
}
</style>
