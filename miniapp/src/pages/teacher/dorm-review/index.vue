<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="宿舍现场工作台" subtitle="调宿 / 巡检 / 整改复查" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad">
        <view class="provider-card">
          <view><small>门禁 Provider</small><text>{{ presenceSummary.provider?.providerLabel || '未配置' }}</text></view>
          <view><small>最后同步</small><text>{{ presenceSummary.provider?.lastSyncAt ? fmt(presenceSummary.provider.lastSyncAt) : '—' }}</text></view>
          <view><small>健康状态</small><text>{{ presenceSummary.provider?.healthStatus || 'DISABLED' }}</text></view>
          <text class="provider-note">{{ presenceSummary.provider?.notice || '未接入归寝数据' }}；未知 {{ presenceSummary.unknown || 0 }} 人不计入未归。</text>
        </view>
        <view class="presence-summary">
          <view><text>{{ presenceSummary.tonightNotReturned || 0 }}</text><small>今晚确认未归</small></view>
          <view><text>{{ presenceSummary.lateReturn || 0 }}</text><small>晚归</small></view>
          <view><text>{{ presenceSummary.onLeave || 0 }}</text><small>已请假</small></view>
          <view><text>{{ presenceSummary.unknown || 0 }}</text><small>未知</small></view>
        </view>
        <view class="allocation-summary">
          <view><text>{{ allocationSummary.activeBatchCount || 0 }}</text><small>当前开放批次</small></view>
          <view><text>{{ allocationSummary.pendingSelectionCount || 0 }}</text><small>待学生选床</small></view>
          <view><text>{{ allocationSummary.reservedCount || 0 }}</text><small>已预留床位</small></view>
          <view><text>{{ allocationSummary.conflictCount || 0 }}</text><small>Dry Run 异常</small></view>
        </view>
        <view class="seg">
          <button class="seg__btn" :class="{ on: tab === 'transfer' }" @click="tab = 'transfer'">调宿待审 ({{ transfers.length }})</button>
          <button class="seg__btn" :class="{ on: tab === 'exception' }" @click="tab = 'exception'">异常待处置 ({{ exceptions.length }})</button>
          <button class="seg__btn" :class="{ on: tab === 'inspection' }" @click="tab = 'inspection'">现场巡检 ({{ tasks.length }})</button>
          <button class="seg__btn" :class="{ on: tab === 'recheck' }" @click="tab = 'recheck'">待复检 ({{ rectifications.length }})</button>
        </view>

        <MobileGlobalState v-if="tab === 'transfer' && !transfers.length" state="empty" title="暂无调宿待审" description="有学生调宿进入辅导员/宿管节点时会出现在这里。" />
        <view class="stack" v-else-if="tab === 'transfer'">
          <view v-for="x in transfers" :key="x.transferId" class="card ar">
            <view class="row-between">
              <view class="flex-1"><text class="t-md t-bold">{{ x.realName || '—' }}</text><text class="ar__sub">{{ x.studentNo || '' }} · {{ nodeLabel(x.currentNode || x.status) }}</text></view>
              <MobileStatusTag :label="x.statusLabel || nodeLabel(x.status)" type="warning" />
            </view>
            <view class="ar__route">
              <text class="ar__route-k">原床</text><text class="ar__route-v">{{ x.fromBedLabel || fallbackBed(x, 'from') }}</text>
              <text class="ar__arrow">↓</text>
              <text class="ar__route-k">目标</text><text class="ar__route-v ar__route-target">{{ x.toBedLabel || fallbackBed(x, 'to') }}</text>
            </view>
            <text class="ar__sub" v-if="x.reason">调宿事由：{{ x.reason }}</text>
            <MobileInlineAlert v-if="!x.fromBedLabel || !x.toBedLabel" type="warning" title="床位信息不完整" description="请刷新或联系宿管核对，确认原床和目标床后再审批。" />
            <view class="ar__actions" v-if="can(x, 'REJECT') || can(x, 'APPROVE')">
              <button v-if="can(x, 'REJECT')" class="ar__no flex-1" :disabled="acting" @click="reviewTransfer(x, 'REJECT')">驳回</button>
              <button v-if="can(x, 'APPROVE')" class="ar__ok flex-1" :disabled="acting || !x.fromBedLabel || !x.toBedLabel" @click="reviewTransfer(x, 'APPROVE')">核对后通过</button>
            </view>
            <text v-else class="ar__sub">当前节点暂无可执行动作</text>
          </view>
        </view>

        <MobileGlobalState v-if="tab === 'exception' && !exceptions.length" state="empty" title="暂无宿舍异常" description="查寝异常、夜不归宿等待处置记录会显示在这里。" />
        <view class="stack" v-else-if="tab === 'exception'">
          <view v-for="x in exceptions" :key="x.exceptionId" class="card ar">
            <view class="row-between"><view class="flex-1"><text class="t-md t-bold">{{ x.realName || '房间级异常' }}</text><text class="ar__sub">{{ x.studentNo || '' }} · {{ x.excTypeLabel || x.excType || '异常' }}</text></view><MobileStatusTag :label="x.statusLabel || x.status || '待处置'" type="warning" /></view>
            <text class="ar__sub" v-if="x.buildingName || x.roomNo">位置：{{ [x.buildingName, x.roomNo && (x.roomNo + '室')].filter(Boolean).join(' / ') }}</text>
            <text class="ar__sub" v-if="x.occurredAt || x.createdAt">发生时间：{{ fmt(x.occurredAt || x.createdAt) }}</text>
            <text class="ar__detail" v-if="x.detail">{{ x.detail }}</text>
            <button class="ar__ok" style="margin-top:10px" :disabled="acting" @click="handleException(x)">登记处置</button>
          </view>
        </view>

        <MobileGlobalState v-if="tab === 'inspection' && !tasks.length" state="empty" title="暂无现场检查任务" description="请先在 PC 端选择楼栋、楼层和模板发布任务。" />
        <view v-else-if="tab === 'inspection'" class="stack">
          <view class="card ar"><text class="t-md t-bold">选择检查任务</text><view class="task-chips"><button v-for="task in tasks" :key="task.taskId" class="task-chip" :class="{ on: inspection.task && inspection.task.taskId === task.taskId }" @click="selectTask(task)">{{ task.taskName }} · {{ task.buildingName }}</button></view></view>
          <view v-if="inspection.task" class="card ar">
            <text class="t-md t-bold">{{ inspection.task.templateName }}</text><text class="ar__sub">{{ inspection.task.buildingName }} · {{ inspection.task.floorScope && inspection.task.floorScope.length ? inspection.task.floorScope.join('、') + '层' : '整栋' }}</text>
            <text class="ar__sub">选择房间</text><view class="task-chips"><button v-for="room in rooms" :key="room.roomId" class="task-chip" :class="{ on: String(inspection.roomId) === String(room.roomId) }" @click="selectRoom(room)">{{ room.roomNo }}室</button></view>
            <view v-if="inspection.roomId" class="inspection-items"><view v-for="item in inspection.items" :key="item.itemCode" class="inspection-item"><view><text class="t-bold">{{ item.itemName }}</text><text class="ar__sub">{{ severityLabel(item.severity) }} · {{ item.maxScore }}分</text></view><view class="item-actions"><button :class="{ on: item.status === 'PASS' }" @click="setItem(item, 'PASS')">正常</button><button class="fail" :class="{ on: item.status === 'FAIL' }" @click="setItem(item, 'FAIL')">异常</button></view></view></view>
            <textarea v-if="inspectionAbnormal" v-model="inspection.detail" class="inspection-note" maxlength="1000" placeholder="异常说明与整改要求（至少5字）" />
            <view v-if="occupants.length"><text class="ar__sub">关联学生（可空）</text><view class="task-chips"><button v-for="student in occupants" :key="student.studentId" class="task-chip" :class="{ on: String(inspection.studentId) === String(student.studentId) }" @click="inspection.studentId = String(inspection.studentId) === String(student.studentId) ? '' : student.studentId">{{ student.realName || student.studentNo }}</button></view></view>
            <button class="task-chip upload" :disabled="acting" @click="uploadInspectionPhoto">{{ inspection.file ? '重新拍照/选图' : '拍照或上传现场证据' }}</button><text v-if="inspection.file" class="ar__sub uploaded">已上传：{{ inspection.file.fileName }}</text>
            <button class="ar__ok inspection-submit" :disabled="acting || !inspection.roomId || (inspectionAbnormal && inspection.detail.trim().length < 5)" @click="submitInspection">提交本房检查</button>
          </view>
        </view>

        <MobileGlobalState v-if="tab === 'recheck' && !rectifications.length" state="empty" title="暂无待复检整改" description="学生或宿管提交整改证据后会出现在这里。" />
        <view v-else-if="tab === 'recheck'" class="stack"><view v-for="x in rectifications" :key="x.rectificationId" class="card ar"><view class="row-between"><view><text class="t-md t-bold">{{ x.buildingName }} · {{ x.roomNo }}室</text><text class="ar__sub">{{ severityLabel(x.severity) }} · {{ x.studentName || '房间级整改' }}</text></view><MobileStatusTag :label="'待复检'" type="warning" /></view><text class="ar__detail">{{ x.requirement }}</text><textarea v-model="recheckNotes[x.rectificationId]" class="inspection-note" maxlength="1000" placeholder="复检意见（至少5字）" /><button class="task-chip upload" :disabled="acting" @click="uploadRecheckPhoto(x)">{{ recheckFiles[x.rectificationId] ? '重新上传复检照片' : '上传复检照片' }}</button><view class="ar__actions"><button class="ar__no flex-1" :disabled="acting || (recheckNotes[x.rectificationId] || '').trim().length < 5" @click="submitRecheck(x, 'RETURN')">退回整改</button><button class="ar__ok flex-1" :disabled="acting || (recheckNotes[x.rectificationId] || '').trim().length < 5 || (['HIGH','CRITICAL'].includes(x.severity) && !recheckFiles[x.rectificationId])" @click="submitRecheck(x, 'PASS')">通过并关闭</button></view></view></view>
      </view>
    </MobileGlobalState>
    <view v-if="actionDlg.visible" class="dialog-mask" @click.self="closeActionDlg">
      <view class="action-dialog">
        <text class="action-dialog__title">{{ actionDlg.title }}</text>
        <text v-if="actionDlg.description" class="action-dialog__description">{{ actionDlg.description }}</text>
        <textarea v-if="actionDlg.mode === 'TEXT'" v-model="actionDlg.value" class="action-dialog__input" maxlength="1000" :placeholder="actionDlg.placeholder" />
        <text v-if="actionDlg.error" class="action-dialog__error">{{ actionDlg.error }}</text>
        <view class="action-dialog__actions"><button class="action-dialog__cancel" @click="closeActionDlg">取消</button><button class="action-dialog__ok" @click="submitActionDlg">确认</button></view>
      </view>
    </view>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { affairsContractApi } from '@/services/affairsContractApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'
import fileSdk from '@/services/fileSdk'

export default {
  data() { return { state: 'loading', acting: false, tab: 'transfer', transfers: [], exceptions: [], tasks: [], rectifications: [], rooms: [], occupants: [], allocationSummary: {}, presenceSummary: {}, actionDlg: { visible: false, mode: 'CONFIRM', title: '', description: '', placeholder: '', value: '', min: 0, invalid: '', error: '', submit: null }, inspection: { task: null, roomId: '', items: [], detail: '', studentId: '', file: null }, recheckNotes: {}, recheckFiles: {} } },
  computed: { inspectionAbnormal() { return this.inspection.items.some((item) => item.status === 'FAIL') } },
  onLoad(q) { if (q && ['exception', 'inspection', 'recheck'].includes(q.tab)) this.tab = q.tab; this.load() },
  onShow() { if (this.state === 'ready') this.load() },
  methods: {
    fmt(v) { return (v || '').slice(0, 16).replace('T', ' ') },
    severityLabel(v) { return ({ LOW: '低风险', MEDIUM: '中风险', HIGH: '高风险', CRITICAL: '重大风险' })[v] || v },
    nodeLabel(v) { return ({ COUNSELOR_REVIEW: '辅导员审核', DORM_MANAGER_REVIEW: '宿管审核', EXECUTED: '已执行', REJECTED: '已驳回' })[v] || v || '待审' },
    fallbackBed(x, side) {
      const prefix = side === 'from' ? 'from' : 'to'
      const parts = [x[prefix + 'BuildingName'], x[prefix + 'RoomNo'] && (x[prefix + 'RoomNo'] + '室'), x[prefix + 'BedNo'] && (x[prefix + 'BedNo'] + '床')].filter(Boolean)
      return parts.join(' / ') || (x[prefix + 'BedId'] ? `床位 #${x[prefix + 'BedId']}` : '未记录')
    },
    can(x, action) {
      return Array.isArray(x.allowedActions) ? x.allowedActions.includes(action) : ['COUNSELOR_REVIEW', 'DORM_MANAGER_REVIEW', 'SUBMITTED'].includes(x.status)
    },
    async load() {
      this.state = 'loading'
      try {
        const [pending, taskData, rectData] = await Promise.all([teacherApi.getAffairsDormPending(), affairsContractApi.getDormInspectionTasks('RUNNING'), affairsContractApi.getDormRectifications('WAITING_RECHECK')])
        this.transfers = pending?.transfers || []; this.exceptions = pending?.exceptions || []; this.allocationSummary = pending?.allocationSummary || {}; this.presenceSummary = pending?.presenceSummary || {}; this.tasks = taskData?.items || []; this.rectifications = rectData?.items || []; this.state = 'ready'
      } catch (e) { this.state = 'error'; this.showError(e, '宿舍现场工作台加载失败') }
    },
    showError(e, fallback) { const n = normalizeError(e); toast(n.text || (e && e.message) || fallback); if (n.kind === 'conflict') this.load(); return n },
    versionOf(x) { if (x.version === undefined || x.version === null || x.version === '') { toast('记录缺少版本号，请刷新后重试'); this.load(); return null }; return x.version },
    async selectTask(task) {
      this.inspection = { task, roomId: '', items: (task.templateItems || []).map((item) => ({ itemCode: item.code, itemName: item.name, maxScore: item.maxScore, severity: item.severity, status: 'PASS', score: item.maxScore })), detail: '', studentId: '', file: null }; this.rooms = []; this.occupants = []
      try { const data = await affairsContractApi.getDormInspectionRooms(task.buildingId); const floors = task.floorScope || []; this.rooms = (data.items || []).filter((room) => !floors.length || floors.includes(Number(room.floorNo))) } catch (e) { this.showError(e, '检查房间加载失败') }
    },
    async selectRoom(room) { this.inspection.roomId = room.roomId; this.inspection.studentId = ''; this.occupants = []; try { const data = await affairsContractApi.getDormInspectionBeds(room.roomId); const seen = new Set(); this.occupants = (data.items || []).filter((bed) => bed.studentId && !seen.has(String(bed.studentId)) && seen.add(String(bed.studentId))).map((bed) => ({ studentId: bed.studentId, realName: bed.studentName || bed.realName, studentNo: bed.studentNo })) } catch (e) { this.showError(e, '房间住宿学生加载失败') } },
    setItem(item, status) { item.status = status; item.score = status === 'PASS' ? item.maxScore : 0 },
    async uploadInspectionPhoto() { try { const selected = await fileSdk.choose(); if (!selected) return; this.acting = true; const uploaded = await fileSdk.upload(selected, { bizType: 'TEMP_PRIVATE' }); this.inspection.file = { fileId: String(uploaded.fileId || uploaded.id), fileName: uploaded.fileName || selected.name || '现场照片' } } catch (e) { this.showError(e, '现场照片上传失败') } finally { this.acting = false } },
    async submitInspection() { if (!this.inspection.task || !this.inspection.roomId || (this.inspectionAbnormal && this.inspection.detail.trim().length < 5)) return; const failedSeverity = this.inspection.items.filter((item) => item.status === 'FAIL').some((item) => ['HIGH', 'CRITICAL'].includes(item.severity)); if (failedSeverity && !this.inspection.file) return toast('高风险异常必须上传现场照片'); this.acting = true; try { await affairsContractApi.submitDormInspectionRecord(this.inspection.task.taskId, { roomId: this.inspection.roomId, result: this.inspectionAbnormal ? 'ABNORMAL' : 'NORMAL', issueType: this.inspection.task.checkType, itemResults: this.inspection.items.map(({ itemCode, status, score }) => ({ itemCode, status, score })), detail: this.inspectionAbnormal ? this.inspection.detail.trim() : '', studentId: this.inspection.studentId || undefined, fileIds: this.inspection.file ? [this.inspection.file.fileId] : [], clientRequestId: `dorm-record-${Date.now()}-${Math.random().toString(16).slice(2)}`.slice(0, 100) }); toast('本房检查已提交'); const task = this.inspection.task; await this.load(); const latest = this.tasks.find((item) => item.taskId === task.taskId) || task; await this.selectTask(latest) } catch (e) { this.showError(e, '检查提交失败') } finally { this.acting = false } },
    async uploadRecheckPhoto(x) { try { const selected = await fileSdk.choose(); if (!selected) return; this.acting = true; const uploaded = await fileSdk.upload(selected, { bizType: 'TEMP_PRIVATE' }); this.recheckFiles[x.rectificationId] = { fileId: String(uploaded.fileId || uploaded.id), fileName: uploaded.fileName || selected.name || '复检照片' } } catch (e) { this.showError(e, '复检照片上传失败') } finally { this.acting = false } },
    async submitRecheck(x, action) { const note = String(this.recheckNotes[x.rectificationId] || '').trim(); if (note.length < 5) return; const file = this.recheckFiles[x.rectificationId]; if (action === 'PASS' && ['HIGH', 'CRITICAL'].includes(x.severity) && !file) return toast('高风险复检通过必须上传照片'); this.acting = true; try { await affairsContractApi.recheckDormRectification(x.rectificationId, { expectedVersion: x.version, action, note, fileIds: file ? [file.fileId] : [] }); toast(action === 'PASS' ? '复检已通过并关闭' : '已退回继续整改'); await this.load() } catch (e) { this.showError(e, '复检提交失败') } finally { this.acting = false } },
    promptText({ title, placeholder, initial = '', min = 5, invalid, submit }) {
      this.actionDlg = { visible: true, mode: 'TEXT', title, description: '', placeholder, value: initial, min, invalid, error: '', submit }
    },
    closeActionDlg() { this.actionDlg.visible = false; this.actionDlg.submit = null },
    submitActionDlg() {
      const value = String(this.actionDlg.value || '').trim()
      if (this.actionDlg.mode === 'TEXT' && value.length < this.actionDlg.min) { this.actionDlg.error = this.actionDlg.invalid; return }
      const run = this.actionDlg.submit
      this.closeActionDlg()
      if (run) run(value)
    },
    reviewTransfer(x, action, previous = '') {
      if (this.acting || !this.can(x, action)) return
      const run = (reason) => {
        const version = this.versionOf(x); if (version === null) return
        this.acting = true
        affairsContractApi.reviewDormTransfer(x.transferId, action, reason, version).then(() => { toast(action === 'APPROVE' ? '已通过' : '已驳回'); this.load() })
          .catch((e) => { const n = this.showError(e, '调宿处理失败'); if (n.kind !== 'conflict' && action === 'REJECT') setTimeout(() => this.reviewTransfer(x, action, reason), 0) })
          .finally(() => { this.acting = false })
      }
      if (action === 'REJECT') {
        this.promptText({ title: '驳回调宿', placeholder: '驳回原因不少于5字', initial: previous, invalid: '驳回原因至少5字', submit: run })
        return
      }
      this.actionDlg = {
        visible: true, mode: 'CONFIRM', title: '确认通过调宿', value: '', min: 0, invalid: '', error: '',
        description: `${x.realName || '该学生'}\n${x.fromBedLabel || this.fallbackBed(x, 'from')}\n→ ${x.toBedLabel || this.fallbackBed(x, 'to')}\n\n确认床位、学生和审批节点无误后再通过。`,
        submit: () => run('')
      }
    },
    handleException(x, previous = '') {
      if (this.acting) return
      this.promptText({
        title: '处置说明', placeholder: '处置说明不少于5字', initial: previous, invalid: '处置说明至少5字',
        submit: (note) => {
          const version = this.versionOf(x); if (version === null) return
          this.acting = true
          affairsContractApi.handleDormException(x.exceptionId, note, version).then(() => { toast('已处置'); this.load() })
            .catch((e) => { const n = this.showError(e, '异常处置失败'); if (n.kind !== 'conflict') setTimeout(() => this.handleException(x, note), 0) })
            .finally(() => { this.acting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
.allocation-summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-bottom: 12px; }
.provider-card { display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:12px;margin-bottom:10px;border:1px solid #cbd5e1;border-radius:10px;background:#f8fafc }.provider-card small,.provider-card text { display:block }.provider-card small { color:#64748b;font-size:10px }.provider-card view>text { margin-top:3px;color:#0f172a;font-size:13px;font-weight:700 }.provider-note { grid-column:1/-1;color:#475569!important;font-size:11px!important;line-height:1.5 }.presence-summary { display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:10px }.presence-summary view { padding:8px 3px;border-radius:8px;background:#fff7ed;text-align:center }.presence-summary text,.presence-summary small { display:block }.presence-summary text { color:#c2410c;font-size:17px;font-weight:700 }.presence-summary small { margin-top:2px;color:#64748b;font-size:9px }
.allocation-summary view { padding: 9px 4px; border-radius: 9px; background: #eff6ff; text-align: center; }
.allocation-summary text { display: block; color: #1d4ed8; font-size: 18px; font-weight: 700; }
.allocation-summary small { display: block; color: #64748b; font-size: 10px; margin-top: 3px; }
.seg { display: grid; grid-template-columns:1fr 1fr; gap: 8px; margin-bottom: 12px; }
.seg__btn { font-size: 13px; background: #f1f5f9; color: #334155; border: none; border-radius: 8px; padding: 8px; }
.seg__btn.on { background: #2563eb; color: #fff; }
.ar { margin-bottom: 10px; }
.row-between { display: flex; justify-content: space-between; gap: 8px; }
.ar__sub { display: block; font-size: 12px; color: #64748b; margin-top: 4px; }
.ar__detail { display: block; margin-top: 8px; padding: 8px; background: #f8fafc; border-radius: 8px; font-size: 13px; line-height: 1.6; }
.ar__route { margin-top: 10px; padding: 10px; background: #f8fafc; border-radius: 8px; display: grid; grid-template-columns: 44px 1fr; gap: 5px 8px; }
.ar__route-k { font-size: 12px; color: #64748b; }
.ar__route-v { font-size: 13px; color: #334155; font-weight: 600; }
.ar__route-target { color: #166534; }
.ar__arrow { grid-column: 2; color: #94a3b8; }
.ar__actions { display: flex; gap: 8px; margin-top: 10px; }
.ar__ok { background: #16a34a; color: #fff; border: none; border-radius: 8px; padding: 8px; font-size: 13px; }
.ar__no { background: #fee2e2; color: #b91c1c; border: none; border-radius: 8px; padding: 8px; font-size: 13px; }
.task-chips { display:flex;gap:7px;flex-wrap:wrap;margin-top:9px }.task-chip { border:1px solid #dbeafe;background:#eff6ff;color:#1d4ed8;border-radius:8px;padding:7px 10px;font-size:12px }.task-chip.on { background:#2563eb;color:#fff }.task-chip.upload { margin-top:10px }.inspection-items { display:grid;gap:8px;margin-top:12px }.inspection-item { display:flex;align-items:center;justify-content:space-between;gap:8px;padding:9px;border:1px solid #e2e8f0;border-radius:8px }.item-actions { display:flex;gap:6px }.item-actions button { border:1px solid #bbf7d0;background:#f0fdf4;color:#166534;border-radius:7px;padding:6px 9px }.item-actions button.fail { border-color:#fecaca;background:#fef2f2;color:#b91c1c }.item-actions button.on { box-shadow:inset 0 0 0 2px currentColor;font-weight:700 }.inspection-note { width:100%;min-height:84px;box-sizing:border-box;margin-top:10px;padding:9px;border:1px solid #cbd5e1;border-radius:8px;background:#fff }.inspection-submit { width:100%;margin-top:12px }.uploaded { color:#166534 }
.dialog-mask { position:fixed;inset:0;z-index:2000;display:flex;align-items:center;justify-content:center;padding:24px;background:rgba(15,23,42,.45) }.action-dialog { width:100%;max-width:360px;box-sizing:border-box;padding:20px;border-radius:16px;background:#fff;box-shadow:0 20px 60px rgba(15,23,42,.25) }.action-dialog__title,.action-dialog__description,.action-dialog__error { display:block }.action-dialog__title { font-size:18px;font-weight:700;color:#0f172a }.action-dialog__description { margin-top:12px;white-space:pre-line;color:#475569;font-size:13px;line-height:1.65 }.action-dialog__input { width:100%;min-height:100px;box-sizing:border-box;margin-top:14px;padding:10px;border:1px solid #cbd5e1;border-radius:10px;background:#fff }.action-dialog__error { margin-top:7px;color:#dc2626;font-size:12px }.action-dialog__actions { display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:18px }.action-dialog__cancel,.action-dialog__ok { border-radius:10px;font-size:14px }.action-dialog__cancel { background:#f1f5f9;color:#334155 }.action-dialog__ok { background:#2563eb;color:#fff }
</style>
