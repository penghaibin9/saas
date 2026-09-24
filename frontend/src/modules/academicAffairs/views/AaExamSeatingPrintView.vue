<template>
  <div class="aa-print-preview aaesp">
    <div class="aaesp-page-head no-print">
      <div>
        <h1>考务打印</h1>
        <p>选择正式考场 → 核验冻结名单与座位全集 → 预览门贴 / 座位表 / 准考证 → 记录打印审计</p>
      </div>
      <button type="button" class="aaesp-back" @click="$router.push('/admin/academic-affairs/exam')">返回考务安排</button>
    </div>
    <AaExamObjectBar
      class="no-print"
      :title="document ? `${document.batchName || '考试批次'} · ${document.courseName || '考试课程'}` : '正式打印对象'"
      :object-id="document ? `EXAM-ROOM-${document.examRoomId}` : (roomId ? `EXAM-ROOM-${roomId}` : '等待输入考场 ID')"
      source="考务管理 / 考务打印"
      :status="document ? '正式发布可打印' : '等待核验正式证据'"
      owner="考务打印岗"
      :blocker="document ? '无已知阻断' : '尚未取得正式打印证据'"
      :blocked="!document"
      next-owner="监考执行岗 / 考场签到岗"
    />
    <AaExamStageRail class="no-print" :steps="stageSteps" :active-index="3" aria-label="考务打印办理阶段" />
    <div class="aaesp-toolbar no-print">
      <AppTextInput v-model="roomId" placeholder="考场 ID" style="max-width:160px" @keyup.enter="load" />
      <AppButton size="small" variant="primary" :disabled="loading || printRequest.submitting" @click="load">
        {{ loading ? '核验中…' : '载入正式打印数据' }}
      </AppButton>
      <AppButton v-if="canPrint" size="small" variant="ghost" @click="openPrint('DOOR_LIST')">打印门贴 / 座位表</AppButton>
      <AppButton v-if="canPrint" size="small" variant="ghost" @click="openPrint('TICKET')">批量打印准考证</AppButton>
      <span class="aaesp-hint">仅可打印已发布考务的正式座位表 / 门贴 / 准考证；重复打印必须留原因</span>
    </div>
    <AppInlineAlert v-if="printError" class="no-print" type="danger" :description="printError" />

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

    <LoadingState v-else-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
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
      :confirm-disabled="printUnconfirmed"
      @confirm="issueAndPrint"
    >
      <div class="aaesp-dialog">
        <AppInlineAlert v-if="printError" type="danger" :description="printError" />
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
import { EmptyState, ErrorState, LoadingState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppConfirmDialog, AppInlineAlert, AppTextInput } from '@/components/common'
import { academicAffairsExamPrintApi as api } from '@/modules/academicAffairs/api/academic-exam-formal-print.api'
import AaExamObjectBar from '@/modules/academicAffairs/components/exam/AaExamObjectBar.vue'
import AaExamStageRail from '@/modules/academicAffairs/components/exam/AaExamStageRail.vue'
import { currentUserFromToken } from '@/services/http/client'
import { toast } from '@/utils/toast'
import {
  clearUnconfirmedWrite,
  isDefiniteWriteRejection,
  markUnconfirmedWrite,
  readUnconfirmedWrite
} from '../components/parallel-b/unconfirmedWrite'

function emptyPrintRequest() {
  return { visible: false, submitting: false, documentKind: '', studentNo: '', studentName: '', reason: '' }
}

export default {
  name: 'AaExamSeatingPrintView',
  props: { ctx: { type: Object, default: () => ({}) } },
  components: { EmptyState, ErrorState, LoadingState, AppButton, AppConfirmDialog, AppInlineAlert, AppTextInput, AaExamObjectBar, AaExamStageRail },
  data() {
    return {
      roomId: this.$route.query.roomId || '',
      loading: false,
      error: '',
      printError: '',
      printUnconfirmed: false,
      document: null,
      rows: [],
      printRequest: emptyPrintRequest(),
      printLayout: '',
      printStudentNo: '',
      loadSeq: 0,
      printSeq: 0,
      stageSteps: ['创建批次', '圈课冻结', '编排预检', '考试发布', '异常收口']
    }
  },
  computed: {
    canPrint() {
      return !!(!this.loading && !this.error && this.document?.documentStatus === 'OFFICIAL' && this.document.printIdentity
        && String(this.document.examRoomId) === String(this.roomId) && this.rows.length > 0)
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
    this.loadSeq++
    this.printSeq++
    window.removeEventListener('afterprint', this.resetPrintProjection)
  },
  watch: {
    '$route.query.roomId'(value) {
      const next = String(value || '')
      if (next === String(this.roomId || '')) return
      this.roomId = next
      this.invalidateDocument()
      if (next) this.load()
    }
  },
  methods: {
    currentIdentity() {
      return JSON.stringify([currentUserFromToken(), this.ctx])
    },
    printOperationKey(roomId = this.roomId) {
      const user = currentUserFromToken() || {}
      return JSON.stringify([user.tenantId, user.userId, user.activeContextId, user.currentRoleCode, roomId, 'exam.print'])
    },
    invalidateDocument() {
      this.loadSeq++
      this.printSeq++
      this.document = null
      this.rows = []
      this.loading = false
      this.error = ''
      this.printError = ''
      this.printUnconfirmed = false
      this.printRequest = emptyPrintRequest()
      this.resetPrintProjection()
    },
    formatPublishedAt(value) {
      if (!value) return '—'
      const text = String(value).replace('T', ' ')
      return text.length > 19 ? text.slice(0, 19) : text
    },
    async load() {
      const id = String(this.roomId || '').trim()
      if (!id) {
        this.error = '请填考场 ID'
        return
      }
      const seq = ++this.loadSeq
      const identity = this.currentIdentity()
      const current = () => seq === this.loadSeq && id === String(this.roomId || '').trim() && identity === this.currentIdentity()
      this.printSeq++
      this.printRequest = emptyPrintRequest()
      this.loading = true
      this.error = ''
      this.printError = ''
      this.printUnconfirmed = false
      this.document = null
      this.rows = []
      this.resetPrintProjection()
      try {
        const data = await api.formalRoomPrint(id)
        if (!current()) return
        if (!data || data.documentStatus !== 'OFFICIAL') {
          throw new Error('后端未返回正式打印证据，已阻止打印')
        }
        if (String(data.examRoomId) !== id || !data.printIdentity) {
          throw new Error('正式打印对象不一致或证据缺失，已阻止打印')
        }
        const seats = Array.isArray(data.seats) ? data.seats : []
        if (!seats.length) throw new Error('正式考场没有可打印座位数据')
        this.document = data
        this.rows = seats
      } catch (error) {
        if (!current()) return
        this.document = null
        this.rows = []
        this.error = error?.message || '正式打印数据核验失败'
      } finally {
        if (current()) this.loading = false
      }
    },
    openPrint(documentKind, row = null) {
      if (!this.canPrint) {
        toast.error('缺少正式打印证据，禁止打印')
        return
      }
      this.printUnconfirmed = false
      this.printError = ''
      const operationKey = this.printOperationKey()
      try {
        if (readUnconfirmedWrite(operationKey)) {
          this.printUnconfirmed = true
          this.printError = '该考场打印审计结果未确认，已暂停重复办理，请核对正式审计记录'
          return
        }
      } catch {
        this.printError = '无法读取打印核对记录，暂不能办理'
        return
      }
      this.printRequest = {
        visible: true,
        submitting: false,
        documentKind,
        studentNo: row?.studentNo || '',
        studentName: row?.studentName || '',
        reason: '',
        roomId: String(this.roomId),
        identity: this.currentIdentity(),
        printIdentity: this.document.printIdentity
      }
    },
    async issueAndPrint() {
      const form = this.printRequest
      if (!form.visible || form.submitting || !this.canPrint || form.roomId !== String(this.roomId)
        || form.identity !== this.currentIdentity() || form.printIdentity !== this.document?.printIdentity) return
      const operationKey = this.printOperationKey(form.roomId)
      try {
        if (readUnconfirmedWrite(operationKey)) {
          this.printUnconfirmed = true
          this.printError = '打印审计结果未确认，不能重复办理'
          return
        }
      } catch {
        this.printError = '无法读取打印核对记录，暂不能办理'
        return
      }
      if (form.studentNo && form.reason.trim().length < 5) {
        toast.error('单个补打原因不少于5字')
        return
      }
      form.submitting = true
      const seq = ++this.printSeq
      const current = () => seq === this.printSeq && form === this.printRequest
        && form.roomId === String(this.roomId) && form.identity === this.currentIdentity()
        && form.printIdentity === this.document?.printIdentity
      try {
        try {
          markUnconfirmedWrite(operationKey, { roomId: form.roomId, startedAt: Date.now() })
        } catch {
          this.printError = '无法保存打印核对记录，本次未发送'
          return
        }
        const issued = await api.issueFormalPrint(form.roomId, {
          documentKind: form.documentKind,
          studentNo: form.studentNo || undefined,
          reason: form.reason.trim() || undefined
        })
        if (!issued?.auditRecorded || issued.printIdentity !== form.printIdentity) {
          throw new Error('打印审计未绑定当前正式证据，已阻止打印')
        }
        clearUnconfirmedWrite(operationKey)
        if (!current()) return
        form.visible = false
        this.printLayout = form.documentKind
        this.printStudentNo = form.studentNo || ''
        toast.success(issued.reprint ? `补打审计已记录（第${issued.printSequence}次）` : '打印审计已记录')
        this.$nextTick(() => { if (current()) window.print() })
      } catch (error) {
        const rejected = isDefiniteWriteRejection(error)
        if (rejected) clearUnconfirmedWrite(operationKey)
        if (current()) {
          this.printUnconfirmed = !rejected
          this.printError = rejected
            ? (error?.message || '打印审计被拒绝')
            : '打印审计结果未确认，已暂停重复办理，请核对正式审计记录'
        }
      } finally {
        if (current()) form.submitting = false
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
.aaesp-page-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 14px; }
.aaesp-page-head h1 { margin: 0; color: #17365f; font-size: 26px; }
.aaesp-page-head p { margin: 6px 0 0; color: #71839f; font-size: 13px; }
.aaesp-back { padding: 8px 12px; border: 1px solid #cdd9e9; border-radius: 8px; background: #fff; color: #2f66c5; cursor: pointer; }
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

<style src="../styles/print-preview.css"></style>

<style>
/* 仅考务打印使用工作区布局，纸张输出不包含导航或滚动容器。 */
@media print {
  body:has(.aaesp) :is(.bpl-topbar, .tw-centers, .tw-rails, .tw-tabbar, .tw-dock-wrap) { display: none !important; }
  body:has(.aaesp), body:has(.aaesp) :is(#app, .base-portal-layout, .tw-frame, .tw-body, .tw-working, .tw-main, .aa-business-area) {
    display: block !important;
    height: auto !important;
    min-height: 0 !important;
    overflow: visible !important;
    margin: 0 !important;
    padding: 0 !important;
  }
}
</style>
