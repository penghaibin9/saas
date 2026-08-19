<template>
  <div class="aaesp">
    <div class="aaesp-toolbar no-print">
      <AppTextInput v-model="roomId" placeholder="考场 ID" style="max-width:160px" @keyup.enter="load" />
      <AppButton size="small" variant="primary" :disabled="loading" @click="load">
        {{ loading ? '核验中…' : '载入正式打印数据' }}
      </AppButton>
      <AppButton v-if="canPrint" size="small" variant="ghost" @click="openPrint('DOOR_LIST')">打印门贴 / 座位表</AppButton>
      <AppButton v-if="canPrint" size="small" variant="ghost" @click="openPrint('TICKET')">批量打印准考证</AppButton>
      <span class="aaesp-hint">仅可打印已发布考务的正式座位表 / 门贴 / 准考证；重复打印必须留原因</span>
    </div>

    <div v-if="canPrint" :class="['aaesp-sheet', printLayout ? `is-${printLayout.toLowerCase()}` : '']">
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

      <div class="aaesp-door-section">
        <table class="aaesp-table">
          <thead><tr><th>座位号</th><th>准考证号</th><th>学号</th><th>姓名</th><th class="no-print">操作</th></tr></thead>
          <tbody>
            <tr v-for="s in rows" :key="s.seatNo">
              <td>{{ s.seatNo }}</td>
              <td>{{ s.admissionNo }}</td>
              <td>{{ s.studentNo }}</td>
              <td>{{ s.studentName }}</td>
              <td class="no-print"><button class="aaesp-link" @click="openPrint('TICKET', s)">单个补打</button></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="aaesp-tickets">
        <div v-for="s in printRows" :key="'t' + s.seatNo" class="aaesp-ticket">
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

    <AppConfirmDialog
      v-model:visible="printRequest.visible"
      :title="printDialogTitle"
      type="primary"
      confirm-text="记录审计并打印"
      :submitting="printRequest.submitting"
      @confirm="issueAndPrint"
    >
      <div class="aaesp-dialog">
        <AppInlineAlert
          type="info"
          title="正式打印会写入考务审计"
          :description="printRequest.studentNo ? `本次仅补打 ${printRequest.studentName || printRequest.studentNo} 的准考证。` : '首次打印原因可留空；同一正式证据重复打印时，后端会强制要求不少于5字的补打原因。'"
        />
        <label>打印 / 补打原因
          <textarea
            v-model.trim="printRequest.reason"
            class="aaesp-textarea"
            maxlength="500"
            :placeholder="printRequest.studentNo ? '单个补打必须填写不少于5字原因' : '首次打印可不填；再次打印必须填写不少于5字原因'"
          />
        </label>
      </div>
    </AppConfirmDialog>
  </div>
</template>

<script>
/** C-W3 考务正式打印：只消费 formal-print provider；真正打印必须先写 append-only 审计。 */
import { EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppConfirmDialog, AppInlineAlert, AppTextInput } from '@/components/common'
import { academicAffairsExamPrintApi as api } from '@/modules/academicAffairs/api/academic-exam-formal-print.api'
import { toast } from '@/utils/toast'

function emptyPrintRequest() {
  return { visible: false, submitting: false, documentKind: '', studentNo: '', studentName: '', reason: '' }
}

export default {
  name: 'AaExamSeatingPrintView',
  components: { EmptyState, AppButton, AppConfirmDialog, AppInlineAlert, AppTextInput },
  data() {
    return {
      roomId: this.$route.query.roomId || '',
      loading: false,
      document: null,
      rows: [],
      printRequest: emptyPrintRequest(),
      printLayout: '',
      printStudentNo: ''
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
    },
    printRows() {
      if (!this.printStudentNo) return this.rows
      return this.rows.filter(row => String(row.studentNo || '') === this.printStudentNo)
    },
    printDialogTitle() {
      if (this.printRequest.studentNo) return `单个补打 · ${this.printRequest.studentName || this.printRequest.studentNo}`
      return this.printRequest.documentKind === 'DOOR_LIST' ? '打印门贴 / 座位表' : '批量打印准考证'
    }
  },
  created() {
    if (this.roomId) this.load()
    window.addEventListener('afterprint', this.resetPrintProjection)
  },
  beforeUnmount() {
    window.removeEventListener('afterprint', this.resetPrintProjection)
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
      this.resetPrintProjection()
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
    openPrint(documentKind, row = null) {
      if (!this.canPrint) {
        toast.error('缺少正式打印证据，禁止打印')
        return
      }
      this.printRequest = {
        visible: true,
        submitting: false,
        documentKind,
        studentNo: row?.studentNo || '',
        studentName: row?.studentName || '',
        reason: ''
      }
    },
    async issueAndPrint() {
      const form = this.printRequest
      if (form.studentNo && form.reason.trim().length < 5) {
        toast.error('单个补打原因不少于5字')
        return
      }
      form.submitting = true
      try {
        const issued = await api.issueFormalPrint(this.roomId, {
          documentKind: form.documentKind,
          studentNo: form.studentNo || undefined,
          reason: form.reason.trim() || undefined
        })
        if (!issued?.auditRecorded || issued.printIdentity !== this.document?.printIdentity) {
          throw new Error('打印审计未绑定当前正式证据，已阻止打印')
        }
        form.visible = false
        this.printLayout = form.documentKind
        this.printStudentNo = form.studentNo || ''
        toast.success(issued.reprint ? `补打审计已记录（第${issued.printSequence}次）` : '打印审计已记录')
        this.$nextTick(() => window.print())
      } catch (error) {
        toast.error(error?.message || '打印审计记录失败')
      } finally {
        form.submitting = false
      }
    },
    resetPrintProjection() {
      this.printLayout = ''
      this.printStudentNo = ''
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
.aaesp-link { padding: 0; border: 0; background: transparent; color: var(--primary-600, #2563eb); cursor: pointer; }
.aaesp-tickets { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-top: 20px; }
.aaesp-ticket { border: 1px dashed #999; border-radius: 6px; padding: 12px; font-size: 13px; line-height: 1.7; }
.aaesp-ticket-title { font-weight: 700; text-align: center; margin-bottom: 6px; }
.aaesp-ticket-proof { margin-top: 6px; color: #64748b; font-size: 10px; word-break: break-all; }
.aaesp-dialog { display: grid; gap: 12px; }
.aaesp-dialog label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aaesp-textarea { min-height: 84px; resize: vertical; padding: 9px 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; font: inherit; }
@media print {
  .no-print { display: none !important; }
  .aaesp { padding: 0; }
  .aaesp-proof { break-inside: avoid; }
  .aaesp-ticket { page-break-inside: avoid; }
  .aaesp-sheet.is-ticket .aaesp-door-section { display: none !important; }
  .aaesp-sheet.is-door_list .aaesp-tickets { display: none !important; }
}
</style>