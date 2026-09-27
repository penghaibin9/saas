<template>
  <section class="exam-attendance" aria-label="本场到考登记">
    <div class="exam-attendance__head">
      <div>
        <h3>本场到考登记</h3>
        <p>按正式考场座位逐人登记；办理后重新读取同一考场确认结果。</p>
      </div>
      <AppButton size="small" variant="ghost" :disabled="loading || !!pendingStudentId" @click="load">刷新名单</AppButton>
    </div>
    <AppInlineAlert v-if="actionError" type="warning" :description="actionError" />
    <AppInlineAlert v-if="receipt" type="success" :description="receipt" />
    <LoadingState v-if="loading && !items.length" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <template v-else>
      <EmptyState v-if="!items.length" title="暂无正式座位名单" description="请先核对该考场是否已铺位。" />
      <DataTable v-else :columns="columns" :rows="items" row-key="studentId">
        <template #cell-student="{ row }"><strong>{{ row.studentName || '姓名待核对' }}</strong><p>{{ row.studentNo || '学号待核对' }}</p></template>
        <template #cell-seat="{ row }">{{ row.seatNo ?? '待核对' }}</template>
        <template #cell-status="{ row }">{{ statusText(row.attendanceStatus) }}</template>
        <template #cell-action="{ row }">
          <AppButton v-if="row.attendanceStatus === 'NOT_STARTED' && row.markPresentAction?.allowed === true" size="small" variant="primary" :loading="pendingStudentId === row.studentId" :disabled="!!pendingStudentId || loading" @click="markPresent(row)">登记到考</AppButton>
          <span v-else>{{ row.markPresentAction?.reason || (row.attendanceStatus === 'PRESENT' ? '已登记到考' : '当前不可登记到考') }}</span>
        </template>
      </DataTable>
    </template>
  </section>
</template>

<script>
import { DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppInlineAlert } from '@/components/common'
import { academicAffairsExamApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'

export default {
  name: 'AaExamAttendanceWorkbench',
  components: { DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppInlineAlert },
  props: { roomId: { type: String, required: true } },
  data() {
    return {
      columns: [{ key: 'student', title: '考生' }, { key: 'seat', title: '座位号' }, { key: 'status', title: '到考状态' }, { key: 'action', title: '办理' }],
      items: [], batchId: '', batchStatus: '', loading: false, error: '', actionError: '', receipt: '', pendingStudentId: '', readSeq: 0, alive: true
    }
  },
  watch: { roomId() { this.items = []; this.actionError = ''; this.receipt = ''; this.load() } },
  mounted() { this.load() },
  beforeUnmount() { this.alive = false; this.readSeq++ },
  methods: {
    statusText(status) {
      return ({ NOT_STARTED: '待登记', PRESENT: '已到考', ABSENT: '缺考', DISCIPLINE_VIOLATION: '违纪' })[status] || '状态待核对'
    },
    async load() {
      const seq = ++this.readSeq, roomId = this.roomId
      const current = () => this.alive && seq === this.readSeq && roomId === this.roomId
      this.loading = true; this.error = ''; this.actionError = ''; this.receipt = ''; this.items = []; this.batchId = ''; this.batchStatus = ''
      try {
        const res = await api.roomAttendance(roomId)
        if (!current()) return false
        if (res.code !== 0) { this.error = res.message || '到考名单读取失败'; return false }
        if (String(res.data?.examRoomId) !== roomId || !Array.isArray(res.data?.items)) { this.error = '考场名单与当前考场不一致，请刷新重试'; return false }
        this.items = res.data.items; this.batchId = String(res.data.batchId || ''); this.batchStatus = res.data.batchStatus || ''
        return true
      } catch (error) { if (current()) this.error = error?.message || '到考名单读取失败'; return false }
      finally { if (current()) this.loading = false }
    },
    async markPresent(row) {
      if (this.pendingStudentId || this.loading || !row || this.items.find(item => item.studentId === row.studentId) !== row || row.attendanceStatus !== 'NOT_STARTED' || row.markPresentAction?.allowed !== true || !Number.isInteger(row.version)) return
      const roomId = this.roomId, studentId = row.studentId, version = row.version
      if (!studentId || !this.batchId) return
      this.pendingStudentId = studentId; this.actionError = ''; this.receipt = ''
      try {
        const res = await api.markRoomPresent(roomId, studentId, version)
        if (!this.alive || this.roomId !== roomId) return
        if (res.code !== 0) {
          await this.load()
          this.actionError = res.message || '登记未完成，请核对最新到考状态'
          return
        }
        const loaded = await this.load()
        if (!this.alive || this.roomId !== roomId) return
        if (loaded && this.items.find(item => item.studentId === studentId)?.attendanceStatus === 'PRESENT') this.receipt = `${row.studentName || row.studentNo || '该考生'}已登记到考，考场名单已重新核对。`
        else this.actionError = '登记命令已返回，但同一考场尚未回读到到考结果，请再次刷新核对。'
      } catch (error) {
        if (this.alive && this.roomId === roomId) { await this.load(); this.actionError = error?.message || '登记结果待核对，请刷新考场名单' }
      } finally { if (this.alive && this.roomId === roomId) this.pendingStudentId = '' }
    }
  }
}
</script>

<style scoped>
.exam-attendance { min-width: 0; margin-top: 12px; padding: 12px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 8px; background: #fff; }
.exam-attendance__head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.exam-attendance h3 { margin: 0 0 4px; font-size: 16px; }
.exam-attendance p { margin: 0 0 12px; color: var(--text-secondary, #64748b); font-size: 13px; }
@media (max-width: 600px) { .exam-attendance__head { flex-direction: column; } }
</style>
