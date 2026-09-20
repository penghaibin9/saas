<template>
  <view class="page-wrap">
    <MobilePrivacyGate />
    <MobileNavBar variant="teacher" :title="tab === 'checkout' ? '退宿办理' : tab === 'recheck' ? '整改复检' : recordId ? '调宿办理' : '宿舍现场工作台'" :subtitle="recordId ? `申请 #${recordId}` : '调宿 / 退宿 / 巡检 / 整改复查'" show-back />
    <view v-if="loadError" class="page-pad">{{ loadError }}</view>
    <button v-if="needsLogin && recordId && tab === 'recheck'" size="mini" @click="loginForRectification">登录后继续整改</button>
    <button v-if="recordId" size="mini" @click="clearFocus">返回{{ tab === 'checkout' ? '退宿' : tab === 'recheck' ? '整改' : '调宿' }}队列</button>
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad">
        <view v-if="!recordId && ['transfer', 'exception'].includes(tab)" class="provider-card">
          <view><small>门禁数据来源</small><text>{{ presenceSummary.provider?.providerLabel || '未配置' }}</text></view>
          <view><small>最后同步</small><text>{{ presenceSummary.provider?.lastSyncAt ? fmt(presenceSummary.provider.lastSyncAt) : '—' }}</text></view>
          <view><small>连接状态</small><text>{{ providerHealthLabel(presenceSummary.provider?.healthStatus) }}</text></view>
          <text class="provider-note">{{ presenceSummary.provider?.notice || '未接入归寝数据' }}；未知 {{ presenceSummary.unknown || 0 }} 人不计入未归。</text>
        </view>
        <view v-if="!recordId && ['transfer', 'exception'].includes(tab)" class="presence-summary">
          <view><text>{{ presenceSummary.tonightNotReturned || 0 }}</text><small>今晚确认未归</small></view>
          <view><text>{{ presenceSummary.lateReturn || 0 }}</text><small>晚归</small></view>
          <view><text>{{ presenceSummary.onLeave || 0 }}</text><small>已请假</small></view>
          <view><text>{{ presenceSummary.unknown || 0 }}</text><small>未知</small></view>
        </view>
        <view v-if="!recordId && ['transfer', 'exception'].includes(tab)" class="allocation-summary">
          <view><text>{{ allocationSummary.activeBatchCount || 0 }}</text><small>当前开放批次</small></view>
          <view><text>{{ allocationSummary.pendingSelectionCount || 0 }}</text><small>待学生选床</small></view>
          <view><text>{{ allocationSummary.reservedCount || 0 }}</text><small>已预留床位</small></view>
          <view><text>{{ allocationSummary.conflictCount || 0 }}</text><small>预分配异常</small></view>
        </view>
        <view v-if="!recordId" class="seg">
          <button class="seg__btn" :class="{ on: tab === 'transfer' }" @click="tab = 'transfer'; pendingPage = 1; load()">调宿待审</button>
          <button class="seg__btn" :class="{ on: tab === 'exception' }" @click="tab = 'exception'; pendingPage = 1; load()">异常待处置</button>
          <button class="seg__btn" :class="{ on: tab === 'inspection' }" @click="tab = 'inspection'; load()">现场巡检</button>
          <button class="seg__btn" :class="{ on: tab === 'recheck' }" @click="tab = 'recheck'; load()">整改复检</button>
          <button class="seg__btn" :class="{ on: tab === 'checkout' }" @click="openCheckouts">退宿办理</button>
        </view>
        <view v-if="tab === 'checkout'" class="stack">
          <text>核对学生与床位后确认退宿，确认后释放床位。</text>
          <view class="row-between"><button v-if="!recordId" size="mini" @click="checkoutStatus = checkoutStatus === 'PENDING' ? 'CONFIRMED' : 'PENDING'; checkoutPage = 1; load()">{{ checkoutStatus === 'PENDING' ? '查看已退宿' : '返回待确认' }}</button><button size="mini" @click="load">刷新</button></view>
          <text v-if="checkoutReceipt">{{ checkoutReceipt }}</text>
          <text v-if="!checkouts.length">当前范围暂无{{ checkoutStatus === 'PENDING' ? '待确认退宿单' : '已退宿记录' }}</text>
          <view v-for="x in checkouts" :key="x.requestId" class="checkout-row">
            <view class="row-between"><text class="t-bold">{{ x.studentName }} · {{ x.studentNo }}</text><text>{{ checkoutLabel(x.status) }}</text></view>
            <text class="ar__sub">{{ x.bedLabel }} · 退宿单 #{{ x.requestId }}</text>
            <text class="ar__sub">{{ x.reason }}</text>
            <text v-for="b in x.blockers" :key="b.code" class="ar__sub">需先处理：{{ b.message }}</text>
            <button v-if="can(x, 'CONFIRM')" class="ar__ok" :disabled="acting || !!x.blockers?.length || !x.bedLabel" @click="confirmCheckout(x)">核对并确认退宿</button>
          </view>
          <view class="row-between"><button size="mini" :disabled="checkoutPage <= 1" @click="checkoutPage--; load()">上一页</button><text>第 {{ checkoutPage }} 页 · 共 {{ checkoutTotal }} 条</text><button size="mini" :disabled="checkoutPage * 20 >= checkoutTotal" @click="checkoutPage++; load()">下一页</button></view>
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
            <text class="ar__sub" v-if="x.returnReason">未通过原因：{{ x.returnReason }}</text>
            <MobileInlineAlert v-if="!x.fromBedLabel || !x.toBedLabel" type="warning" title="床位信息不完整" description="请刷新或联系宿管核对，确认原床和目标床后再审批。" />
            <view class="ar__actions" v-if="can(x, 'REJECT') || can(x, 'APPROVE')">
              <button v-if="can(x, 'REJECT')" class="ar__no flex-1" :disabled="acting" @click="reviewTransfer(x, 'REJECT')">驳回</button>
              <button v-if="can(x, 'APPROVE')" class="ar__ok flex-1" :disabled="acting || !x.fromBedLabel || !x.toBedLabel" @click="reviewTransfer(x, 'APPROVE')">核对后通过</button>
            </view>
            <text v-else class="ar__sub">{{ x.status === 'EXECUTED' ? '调宿已完成，原床已释放。' : x.status === 'REJECTED' ? '本次申请已结束，原床保持不变；学生可重新申请。' : '当前节点暂无可执行动作' }}</text>
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

        <view v-if="!recordId && ['transfer', 'exception'].includes(tab)" class="row-between"><button size="mini" :disabled="pendingPage <= 1 || acting" @click="pendingPage--; load()">上一页</button><text>第 {{ pendingPage }} 页 · 共 {{ tab === 'transfer' ? transferTotal : exceptionTotal }} 条</text><button size="mini" :disabled="pendingPage * 20 >= (tab === 'transfer' ? transferTotal : exceptionTotal) || acting" @click="pendingPage++; load()">下一页</button></view>
        <view v-if="tab === 'inspection'" class="row-between"><button size="mini" :disabled="taskPage <= 1 || acting" @click="taskPage--; load()">上一页</button><text>第 {{ taskPage }} 页 · 共 {{ taskTotal }} 项</text><button size="mini" :disabled="taskPage * 20 >= taskTotal || acting" @click="taskPage++; load()">下一页</button></view>
        <MobileGlobalState v-if="tab === 'inspection' && !tasks.length" state="empty" title="当前页暂无现场检查任务" description="可返回上一页；新任务由 PC 端选择楼栋、楼层和模板发布。" />
        <view v-else-if="tab === 'inspection'" class="stack">
          <view class="card ar"><text class="t-md t-bold">选择检查任务</text><view class="task-chips"><button v-for="task in tasks" :key="task.taskId" class="task-chip" :class="{ on: inspection.task && inspection.task.taskId === task.taskId }" @click="selectTask(task)">{{ task.taskName }} · {{ task.buildingName }}</button></view></view>
          <view v-if="inspection.task" class="card ar">
            <text class="t-md t-bold">{{ inspection.task.templateName }}</text><text class="ar__sub">{{ inspection.task.buildingName }} · {{ inspection.task.floorScope && inspection.task.floorScope.length ? inspection.task.floorScope.join('、') + '层' : '整栋' }}</text>
            <view v-if="inspection.task.floorScope?.length" class="task-chips"><button v-for="floor in inspection.task.floorScope" :key="floor" class="task-chip" :disabled="acting" :class="{ on: roomFloor === floor }" @click="roomFloor = floor; roomPage = 1; loadInspectionRooms()">{{ floor }}层</button></view>
            <text v-if="roomError" class="ar__sub">{{ roomError }}</text><button v-if="roomError" size="mini" @click="loadInspectionRooms">重新加载房间</button>
            <text v-if="roomLoading" class="ar__sub">房间加载中…</text>
            <text class="ar__sub">选择房间</text><view class="task-chips"><button v-for="room in rooms" :key="room.roomId" class="task-chip" :class="{ on: String(inspection.roomId) === String(room.roomId) }" @click="selectRoom(room)">{{ room.roomNo }}室</button></view>
            <view class="row-between"><button size="mini" :disabled="roomPage <= 1 || roomLoading || acting" @click="roomPage--; loadInspectionRooms()">上一页</button><text>第 {{ roomPage }} 页 · 共 {{ roomTotal }} 间</text><button size="mini" :disabled="roomPage * 20 >= roomTotal || roomLoading || acting" @click="roomPage++; loadInspectionRooms()">下一页</button></view>
            <view v-if="inspection.roomId" class="inspection-items"><view v-for="item in inspection.items" :key="item.itemCode" class="inspection-item"><view><text class="t-bold">{{ item.itemName }}</text><text class="ar__sub">{{ severityLabel(item.severity) }} · {{ item.maxScore }}分</text></view><view class="item-actions"><button :class="{ on: item.status === 'PASS' }" @click="setItem(item, 'PASS')">正常</button><button class="fail" :class="{ on: item.status === 'FAIL' }" @click="setItem(item, 'FAIL')">异常</button></view></view></view>
            <textarea v-if="inspectionAbnormal" v-model="inspection.detail" class="inspection-note" maxlength="1000" placeholder="异常说明与整改要求（至少5字）" />
            <view v-if="occupants.length"><text class="ar__sub">关联学生（可空）</text><view class="task-chips"><button v-for="student in occupants" :key="student.studentId" class="task-chip" :class="{ on: String(inspection.studentId) === String(student.studentId) }" @click="inspection.studentId = String(inspection.studentId) === String(student.studentId) ? '' : student.studentId">{{ student.realName || student.studentNo }}</button></view></view>
            <button class="task-chip upload" :disabled="acting" @click="uploadInspectionPhoto">{{ inspection.file ? '重新拍照/选图' : '拍照或上传现场证据' }}</button><text v-if="inspection.file" class="ar__sub uploaded">已上传：{{ inspection.file.fileName }}</text>
            <button class="ar__ok inspection-submit" :disabled="acting || !inspection.roomId || (inspectionAbnormal && inspection.detail.trim().length < 5)" @click="submitInspection">提交本房检查</button>
          </view>
        </view>

        <view v-if="tab === 'recheck' && !recordId" class="row-between"><button size="mini" @click="recheckStatus = recheckStatus === 'CLOSED' ? 'WAITING_RECHECK' : 'CLOSED'; recheckPage = 1; load()">{{ recheckStatus === 'CLOSED' ? '返回待复检' : '查看已关闭' }}</button><button size="mini" @click="recheckStatus = 'PENDING'; recheckPage = 1; load()">查看未完成</button><text>共 {{ recheckTotal }} 条</text></view>
        <MobileGlobalState v-if="tab === 'recheck' && !rectifications.length" state="empty" :title="recheckStatus === 'CLOSED' ? '暂无已关闭整改' : '暂无待复检整改'" description="按当前负责范围查询。" />
        <view v-else-if="tab === 'recheck'" class="stack"><view v-for="x in rectifications" :key="x.rectificationId" class="card ar"><view class="row-between"><view><text class="t-md t-bold">{{ x.buildingName }} · {{ x.roomNo }}室</text><text class="ar__sub">{{ severityLabel(x.severity) }} · {{ x.studentName || '房间级整改' }}</text></view><MobileStatusTag :label="rectificationLabel(x.status)" :type="x.status === 'CLOSED' ? 'success' : 'warning'" /></view><text class="ar__detail">{{ x.requirement }}</text>
            <view class="review-evidence"><text class="t-bold">原检查</text><text class="ar__sub">{{ x.inspectionDetail || '未填写检查说明' }}</text><button v-for="file in x.inspectionFiles || []" :key="file.fileId" class="task-chip" @click="openEvidence(file)">{{ file.fileName || '查看检查照片' }}</button>
            <text class="t-bold">整改反馈</text><text class="ar__sub">{{ x.rectifyNote || '尚未提交整改说明' }}</text><button v-for="file in x.rectificationFiles || []" :key="file.fileId" class="task-chip" @click="openEvidence(file)">{{ file.fileName || '查看整改照片' }}</button><text v-if="x.recheckNote" class="ar__sub">上次复检：{{ x.recheckNote }}</text><button v-for="file in x.recheckFiles || []" :key="file.fileId" class="task-chip" @click="openEvidence(file)">{{ file.fileName || '查看复检照片' }}</button></view>
            <button v-if="can(x, 'START')" :disabled="acting" @click="startRoomRectification(x)">开始整改</button>
            <view v-if="can(x, 'SUBMIT')" class="review-evidence">
              <textarea v-model="roomRectNotes[x.rectificationId]" class="inspection-note" maxlength="1000" placeholder="整改说明（5-1000字）" />
              <button class="task-chip upload" :disabled="acting" @click="uploadRoomRectification(x)">{{ roomRectFiles[x.rectificationId] ? '重新上传整改照片' : '上传整改照片' }}</button>
              <text v-if="roomRectFiles[x.rectificationId]">{{ roomRectFiles[x.rectificationId].fileName }}</text>
              <button :disabled="acting || (roomRectNotes[x.rectificationId] || '').trim().length < 5 || !roomRectFiles[x.rectificationId]" @click="submitRoomRectification(x)">提交复检</button>
            </view>
            <template v-if="can(x, 'PASS') || can(x, 'RETURN')"><textarea v-model="recheckNotes[x.rectificationId]" class="inspection-note" maxlength="1000" placeholder="复检意见（至少5字）" /><button class="task-chip upload" :disabled="acting" @click="uploadRecheckPhoto(x)">{{ recheckFiles[x.rectificationId] ? '重新上传复检照片' : '上传复检照片' }}</button><view class="ar__actions"><button class="ar__no flex-1" :disabled="acting || (recheckNotes[x.rectificationId] || '').trim().length < 5" v-if="can(x, 'RETURN')" @click="submitRecheck(x, 'RETURN')">退回整改</button><button class="ar__ok flex-1" :disabled="acting || (recheckNotes[x.rectificationId] || '').trim().length < 5 || (['HIGH','CRITICAL'].includes(x.severity) && !recheckFiles[x.rectificationId])" v-if="can(x, 'PASS')" @click="submitRecheck(x, 'PASS')">通过并关闭</button></view></template></view><view v-if="!recordId" class="row-between"><button size="mini" :disabled="recheckPage <= 1" @click="recheckPage--; load()">上一页</button><text>第 {{ recheckPage }} 页</text><button size="mini" :disabled="recheckPage * 20 >= recheckTotal" @click="recheckPage++; load()">下一页</button></view></view>
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
import { normalizeError, realRequest } from '@/services/request'
import { toast } from '@/utils/nav'
import { createClientRequestId } from '@/utils/clientRequestId'
import fileSdk from '@/services/fileSdk'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'

export default {
  data() { return { pendingPage: 1, transferTotal: 0, exceptionTotal: 0, disposed: false, sessionGeneration: null, taskPage: 1, taskTotal: 0, roomPage: 1, roomTotal: 0, roomFloor: undefined, roomLoading: false, roomError: '', roomSerial: 0, occupantSerial: 0, roomRectNotes: {}, roomRectFiles: {}, roomRectRequests: {}, needsLogin: false, recheckStatus: 'WAITING_RECHECK', recheckPage: 1, recheckTotal: 0, checkouts: [], checkoutPage: 1, checkoutTotal: 0, checkoutStatus: 'PENDING', checkoutReceipt: '', recordId: '', loadSerial: 0, loadError: '', state: 'loading', acting: false, tab: 'transfer', transfers: [], exceptions: [], tasks: [], rectifications: [], rooms: [], occupants: [], allocationSummary: {}, presenceSummary: {}, actionDlg: { visible: false, mode: 'CONFIRM', title: '', description: '', placeholder: '', value: '', min: 0, invalid: '', error: '', submit: null }, inspection: { task: null, roomId: '', items: [], detail: '', studentId: '', file: null, clientRequestId: '' }, recheckNotes: {}, recheckFiles: {} } },
  computed: { inspectionAbnormal() { return this.inspection.items.some((item) => item.status === 'FAIL') } },
  onLoad(q) {
    this.recordId = String(q?.recordId || ''); if (q && ['exception', 'inspection', 'recheck', 'checkout'].includes(q.tab)) this.tab = q.tab
    // H5 changing only the hash query reuses this page; onLoad does not run again.
    // #ifdef H5
    this._onDormHashChange = () => this.syncFocusHash(window.location.hash)
    window.addEventListener('hashchange', this._onDormHashChange)
    // #endif
    this.load()
  },
  onShow() { if (this.state === 'ready' && !this.acting) this.load() },
  onUnload() { this.disposeFocus() },
  beforeUnmount() { this.disposeFocus() },
  methods: {
    rectificationLabel(status) { return ({ OPEN: '待整改', RECTIFYING: '整改中', WAITING_RECHECK: '待复检', CLOSED: '已关闭', ESCALATED: '已升级风险' })[status] || '状态待核对' },
    async runDormCommand(command, success, fallback) {
      if (this.acting) return false
      const generation = currentSessionGeneration(), serial = this.loadSerial
      const current = () => !this.disposed && generation === currentSessionGeneration() && serial === this.loadSerial
      this.acting = true
      try {
        const result = await command()
        if (!current()) return false
        await success(result)
        return true
      } catch (e) { if (current()) this.showError(e, fallback); return false }
      finally { if (!this.disposed && generation === currentSessionGeneration()) this.acting = false }
    },
    async startRoomRectification(row) {
      if (this.acting || !this.can(row, 'START')) return
      const version = this.versionOf(row); if (version === null) return
      return this.runDormCommand(() => realRequest(`/mobile/teacher/affairs/dorm/rectifications/${row.rectificationId}/start`, { method: 'POST', data: { expectedVersion: version } }), () => this.load(), '开始整改失败')
    },
    async uploadRoomRectification(row) {
      if (this.acting || !this.can(row, 'SUBMIT')) return
      return this.uploadDormPhoto(file => { this.roomRectFiles[row.rectificationId] = file }, '整改照片上传失败')
    },
    async submitRoomRectification(row) {
      if (this.acting || !this.can(row, 'SUBMIT')) return
      const id = row.rectificationId, note = String(this.roomRectNotes[id] || '').trim(), file = this.roomRectFiles[id]
      if (note.length < 5 || note.length > 1000 || !file) return
      const version = this.versionOf(row); if (version === null) return
      const payload = JSON.stringify({ version, note, fileId: file.fileId })
      if (this.roomRectRequests[id]?.payload !== payload) this.roomRectRequests[id] = { payload, key: createClientRequestId('dorm-rectify') }
      return this.runDormCommand(() => realRequest(`/mobile/teacher/affairs/dorm/rectifications/${id}/submit`, { method: 'POST', data: { expectedVersion: version, note, fileIds: [file.fileId], clientRequestId: this.roomRectRequests[id].key } }), async () => {
        delete this.roomRectNotes[id]; delete this.roomRectFiles[id]; delete this.roomRectRequests[id]
        toast('整改已提交，等待复检'); await this.load()
      }, '整改提交失败')
    },
    loginForRectification() { uni.redirectTo({ url: `/pages/login/teacher/index?dormRectificationId=${encodeURIComponent(this.recordId)}` }) },
    openCheckouts() { this.tab = 'checkout'; this.checkoutPage = 1; this.load() },
    checkoutLabel(status) { return ({ PENDING_CONFIRMATION: '待确认', BLOCKED: '存在阻断', CONFIRMED: '已退宿', CANCELLED: '已取消' })[status] || '待核对' },
    confirmCheckout(row) {
      if (this.acting || !this.can(row, 'CONFIRM') || row.blockers?.length || !row.bedLabel) return
      const version = this.versionOf(row); if (version === null) return
      const generation = currentSessionGeneration(), serial = this.loadSerial
      this.actionDlg = {
        visible: true, mode: 'CONFIRM', title: '确认退宿并释放床位', value: '', min: 0,
        description: `${row.studentName} · ${row.studentNo}\n${row.bedLabel}\n${row.reason}\n确认后住宿关系结束，原床位可重新分配。`,
        submit: async () => {
          if (this.acting || this.disposed || generation !== currentSessionGeneration() || serial !== this.loadSerial) return
          this.checkoutReceipt = ''
          return this.runDormCommand(() => realRequest(`/student-affairs/dorm/checkout-requests/${row.requestId}/confirm`, { method: 'POST', data: { version } }), async result => {
            this.checkoutReceipt = `${result.studentName || row.studentName}：${this.checkoutLabel(result.status)} · ${result.bedLabel || row.bedLabel}`
            await this.load()
          }, '退宿确认失败，床位结果请刷新核对')
        }
      }
    },
    disposeFocus() {
      // #ifdef H5
      if (this._onDormHashChange) window.removeEventListener('hashchange', this._onDormHashChange)
      this._onDormHashChange = null
      // #endif
      this.loadSerial++
      this.disposed = true
    },
    syncFocusHash(hash) {
      const [path, query = ''] = String(hash || '').replace(/^#/, '').split('?')
      if (path !== '/pages/teacher/dorm-review/index') return
      const params = new URLSearchParams(query)
      const id = params.get('recordId') || ''
      const requestedTab = params.get('tab')
      const tab = ['exception', 'inspection', 'recheck', 'checkout'].includes(requestedTab) ? requestedTab : 'transfer'
      if (id === this.recordId && tab === this.tab) return
      this.recordId = id
      this.tab = tab; this.checkoutPage = 1; this.checkouts = []; this.checkoutReceipt = ''
      this.transfers = []; this.rectifications = []; this.recheckNotes = {}; this.recheckFiles = {}; this.roomRectNotes = {}; this.roomRectFiles = {}; this.roomRectRequests = {}
      this.closeActionDlg()
      return this.load()
    },
    clearFocus() { uni.redirectTo({ url: '/pages/teacher/dorm-review/index' + (['checkout', 'recheck'].includes(this.tab) ? '?tab=' + this.tab : '') }) },
    async openEvidence(file) { try { await fileSdk.open(file.fileId) } catch (e) { this.showError(e, '照片暂不可查看') } },
    fmt(v) { return (v || '').slice(0, 16).replace('T', ' ') },
    severityLabel(v) { return ({ LOW: '低风险', MEDIUM: '中风险', HIGH: '高风险', CRITICAL: '重大风险' })[v] || '风险待确认' },
    nodeLabel(v) { return ({ COUNSELOR_REVIEW: '辅导员审核', DORM_MANAGER_REVIEW: '宿管审核', EXECUTED: '已执行', REJECTED: '已驳回' })[v] || '状态待确认' },
    providerHealthLabel(v) { return ({ HEALTHY: '连接正常', OK: '连接正常', DEGRADED: '连接不稳定', ERROR: '连接异常', DISABLED: '未启用' })[v] || '待确认' },
    fallbackBed(x, side) {
      const prefix = side === 'from' ? 'from' : 'to'
      const parts = [x[prefix + 'BuildingName'], x[prefix + 'RoomNo'] && (x[prefix + 'RoomNo'] + '室'), x[prefix + 'BedNo'] && (x[prefix + 'BedNo'] + '床')].filter(Boolean)
      return parts.join(' / ') || (x[prefix + 'BedId'] ? `床位 #${x[prefix + 'BedId']}` : '未记录')
    },
    can(x, action) {
      return Array.isArray(x.allowedActions) && x.allowedActions.includes(action)
    },
    async load() {
      const serial = ++this.loadSerial
      const generation = currentSessionGeneration()
      const current = () => !this.disposed && serial === this.loadSerial && generation === currentSessionGeneration()
      if (this.sessionGeneration !== generation) {
        this.sessionGeneration = generation; this.transfers = []; this.exceptions = []; this.tasks = []; this.rectifications = []; this.checkouts = []
        this.rooms = []; this.occupants = []; this.inspection = { task: null, roomId: '', items: [], detail: '', studentId: '', file: null, clientRequestId: '' }
        this.roomRectNotes = {}; this.roomRectFiles = {}; this.roomRectRequests = {}; this.recheckNotes = {}; this.recheckFiles = {}
        this.allocationSummary = {}; this.presenceSummary = {}; this.checkoutReceipt = ''; this.closeActionDlg()
        this.taskPage = 1; this.recheckPage = 1; this.checkoutPage = 1; this.pendingPage = 1; this.transferTotal = 0; this.exceptionTotal = 0; this.acting = false
      }
      this.state = 'loading'; this.loadError = ''; this.needsLogin = false
      try {
        if (!this.recordId && this.tab === 'recheck') {
          const data = await realRequest('/mobile/teacher/affairs/dorm/rectifications', { data: { status: this.recheckStatus, page: this.recheckPage, pageSize: 20 } })
          if (!current()) return
          this.rectifications = data.items || []; this.recheckTotal = data.total || 0; this.state = 'ready'; return
        }
        if (this.recordId && !/^[1-9]\d*$/.test(this.recordId)) throw new Error('申请编号无效，请从办理入口重新进入')
        if (this.recordId && this.tab === 'recheck') {
          const row = await realRequest(`/mobile/teacher/affairs/dorm/rectifications/${this.recordId}`)
          if (!current()) return
          if (!row || String(row.rectificationId) !== this.recordId) throw new Error('该整改单不存在或不在当前权限范围内')
          this.rectifications = [row]; this.recheckTotal = 1; this.state = 'ready'; return
        }
        if (this.tab === 'checkout') {
          const query = this.recordId ? { recordId: this.recordId, page: 1, pageSize: 1 } : { status: this.checkoutStatus, page: this.checkoutPage, pageSize: 20 }
          const data = await realRequest('/student-affairs/dorm/checkout-requests', { data: query })
          if (!current()) return
          if (this.recordId && !data.items?.length) throw new Error('该退宿单不存在或不在当前权限范围内')
          this.checkouts = data.items || []; this.checkoutTotal = data.total || 0; this.state = 'ready'; return
        }
        if (this.recordId) {
          if (!/^[1-9]\d*$/.test(this.recordId)) throw new Error('调宿申请编号无效，请从待办重新进入')
          const data = await realRequest('/student-affairs/dorm/transfers', { data: { recordId: this.recordId, page: 1, pageSize: 1 } })
          if (!current()) return
          if (!data?.items?.length) throw new Error('该调宿申请不存在或不在当前权限范围内')
          this.transfers = data.items; this.state = 'ready'; return
        }
        if (this.tab === 'inspection') {
          const data = await affairsContractApi.getDormInspectionTasks('RUNNING', { page: this.taskPage, pageSize: 20 })
          if (!current()) return
          if (!Array.isArray(data?.items)) throw new Error('巡检任务未完整加载，请重试')
          this.tasks = data.items; this.taskTotal = Number(data.total) || 0; this.state = 'ready'; return
        }
        const pending = await teacherApi.getAffairsDormPending({ page: this.pendingPage, pageSize: 20 })
        if (!current()) return
        if (!Array.isArray(pending?.transfers) || !Array.isArray(pending?.exceptions)) throw new Error('宿舍待办未完整加载，请重试')
        this.transfers = pending.transfers; this.exceptions = pending.exceptions; this.transferTotal = Number(pending.transferTotal) || 0; this.exceptionTotal = Number(pending.exceptionTotal) || 0; this.allocationSummary = pending.allocationSummary || {}; this.presenceSummary = pending.presenceSummary || {}; this.state = 'ready'
      } catch (e) { if (!current()) return; this.needsLogin = normalizeError(e).kind === 'auth'; this.state = normalizeError(e).pageState || 'error'; this.loadError = normalizeError(e).text || '宿舍现场工作台加载失败'; this.showError(e, this.loadError) }
    },
    showError(e, fallback) { const n = normalizeError(e); toast(n.text || (e && e.message) || fallback); if (n.kind === 'conflict') this.load(); return n },
    versionOf(x) { if (x.version === undefined || x.version === null || x.version === '') { toast('记录缺少版本号，请刷新后重试'); this.load(); return null }; return x.version },
    async selectTask(task) {
      if (this.acting) return
      this.inspection = { task, roomId: '', items: (task.templateItems || []).map((item) => ({ itemCode: item.code, itemName: item.name, maxScore: item.maxScore, severity: item.severity, status: 'PASS', score: item.maxScore })), detail: '', studentId: '', file: null, clientRequestId: '' }; this.rooms = []; this.occupants = []
      this.roomFloor = task.floorScope?.[0]; this.roomPage = 1
      return this.loadInspectionRooms()
    },
    async loadInspectionRooms() {
      const task = this.inspection.task
      if (!task || this.acting) return
      const serial = ++this.roomSerial, loadSerial = this.loadSerial, generation = currentSessionGeneration()
      const current = () => !this.disposed && serial === this.roomSerial && loadSerial === this.loadSerial && generation === currentSessionGeneration() && task === this.inspection.task
      this.roomLoading = true; this.roomError = ''; this.rooms = []; this.roomTotal = 0; this.occupants = []; this.inspection.roomId = ''; this.inspection.studentId = ''; this.occupantSerial++
      try {
        const data = await affairsContractApi.getDormInspectionRooms(task.buildingId, { floor: this.roomFloor, page: this.roomPage, pageSize: 20 })
        if (!current()) return
        if (!Array.isArray(data?.items)) throw new Error('房间未完整加载，请重试')
        this.rooms = data.items; this.roomTotal = Number(data.total) || 0
      } catch (e) { if (current()) this.roomError = normalizeError(e).text || '检查房间加载失败' }
      finally { if (current()) this.roomLoading = false }
    },
    async selectRoom(room) {
      if (this.acting || this.roomLoading) return
      const serial = ++this.occupantSerial, generation = currentSessionGeneration(), loadSerial = this.loadSerial, inspection = this.inspection
      const current = () => !this.disposed && generation === currentSessionGeneration() && loadSerial === this.loadSerial && serial === this.occupantSerial && inspection === this.inspection
      inspection.roomId = room.roomId; inspection.studentId = ''; inspection.file = null; inspection.detail = ''; inspection.clientRequestId = createClientRequestId('dorm-record'); this.occupants = []
      inspection.requestPayload = ''; inspection.items.forEach(item => { item.status = 'PASS'; item.score = item.maxScore })
      try {
        const data = await affairsContractApi.getDormInspectionBeds(room.roomId)
        if (!current()) return
        if (!Array.isArray(data?.items)) throw new Error('房间住宿学生未完整加载')
        const seen = new Set()
        this.occupants = data.items.filter((bed) => bed.studentId && !seen.has(String(bed.studentId)) && seen.add(String(bed.studentId))).map((bed) => ({ studentId: bed.studentId, realName: bed.studentName || bed.occupantName || bed.realName, studentNo: bed.studentNo }))
      } catch (e) { if (current()) { inspection.roomId = ''; this.showError(e, '房间住宿学生加载失败') } }
    },
    setItem(item, status) { item.status = status; item.score = status === 'PASS' ? item.maxScore : 0 },
    async uploadDormPhoto(assign, fallback) {
      if (this.acting) return
      const generation = currentSessionGeneration(), serial = this.loadSerial
      const current = () => !this.disposed && generation === currentSessionGeneration() && serial === this.loadSerial
      this.acting = true
      try {
        const selected = await fileSdk.choose(); if (!selected || !current()) return
        const uploaded = await fileSdk.upload(selected, { bizType: 'TEMP_PRIVATE' }); if (!current()) return
        if (!uploaded?.fileId && !uploaded?.id) throw new Error('上传结果缺少文件编号，请重试')
        assign({ fileId: String(uploaded.fileId || uploaded.id), fileName: uploaded.fileName || selected.name || '现场照片' })
      } catch (e) { if (current()) this.showError(e, fallback) }
      finally { if (!this.disposed && generation === currentSessionGeneration()) this.acting = false }
    },
    uploadInspectionPhoto() { const inspection = this.inspection; return this.uploadDormPhoto(file => { if (inspection === this.inspection) inspection.file = file }, '现场照片上传失败') },
    async submitInspection() {
      if (this.acting || this.roomLoading || !this.inspection.task || !this.inspection.roomId || (this.inspectionAbnormal && this.inspection.detail.trim().length < 5)) return
      const inspection = this.inspection, generation = currentSessionGeneration(), serial = this.loadSerial
      const current = () => !this.disposed && generation === currentSessionGeneration() && serial === this.loadSerial && inspection === this.inspection
      const failedSeverity = inspection.items.some(item => item.status === 'FAIL' && ['HIGH', 'CRITICAL'].includes(item.severity))
      if (failedSeverity && !inspection.file) return toast('高风险异常必须上传现场照片')
      const data = { roomId: inspection.roomId, result: this.inspectionAbnormal ? 'ABNORMAL' : 'NORMAL', issueType: inspection.task.checkType, itemResults: inspection.items.map(({ itemCode, status, score }) => ({ itemCode, status, score })), detail: this.inspectionAbnormal ? inspection.detail.trim() : '', studentId: inspection.studentId || undefined, fileIds: inspection.file ? [inspection.file.fileId] : [] }
      const payload = JSON.stringify(data)
      if (inspection.requestPayload && inspection.requestPayload !== payload) return toast('上次提交结果尚待核对，请先刷新任务确认，勿重复登记')
      if (!inspection.clientRequestId) inspection.clientRequestId = createClientRequestId('dorm-record')
      inspection.requestPayload = payload
      this.acting = true
      try {
        await affairsContractApi.submitDormInspectionRecord(inspection.task.taskId, { ...data, clientRequestId: inspection.clientRequestId })
        if (!current()) return
        toast('本房检查已提交'); inspection.roomId = ''; inspection.file = null; inspection.studentId = ''; this.occupants = []
        await this.load()
      } catch (e) { if (current()) this.showError(e, '检查提交失败') }
      finally { if (!this.disposed && generation === currentSessionGeneration()) this.acting = false }
    },
    uploadRecheckPhoto(x) { return this.uploadDormPhoto(file => { this.recheckFiles[x.rectificationId] = file }, '复检照片上传失败') },
    async submitRecheck(x, action) {
      if (this.acting || !this.can(x, action)) return
      const note = String(this.recheckNotes[x.rectificationId] || '').trim(), file = this.recheckFiles[x.rectificationId]
      if (note.length < 5) return
      if (action === 'PASS' && ['HIGH', 'CRITICAL'].includes(x.severity) && !file) return toast('高风险复检通过必须上传照片')
      const version = this.versionOf(x); if (version === null) return
      return this.runDormCommand(() => affairsContractApi.recheckDormRectification(x.rectificationId, { expectedVersion: version, action, note, fileIds: file ? [file.fileId] : [] }), async () => {
        delete this.recheckNotes[x.rectificationId]; delete this.recheckFiles[x.rectificationId]
        toast(action === 'PASS' ? '复检已通过并关闭' : '已退回继续整改'); await this.load()
      }, '复检提交失败')
    },
    promptText({ title, placeholder, initial = '', min = 5, invalid, submit }) {
      this.actionDlg = { visible: true, mode: 'TEXT', title, description: '', placeholder, value: initial, min, invalid, error: '', submit }
    },
    closeActionDlg() { this.actionDlg.visible = false; this.actionDlg.submit = null },
    submitActionDlg() {
      if (this.acting) return
      const value = String(this.actionDlg.value || '').trim()
      if (this.actionDlg.mode === 'TEXT' && value.length < this.actionDlg.min) { this.actionDlg.error = this.actionDlg.invalid; return }
      const run = this.actionDlg.submit
      this.closeActionDlg()
      if (run) return run(value)
    },
    reviewTransfer(x, action, previous = '') {
      if (this.acting || !this.can(x, action)) return
      const generation = currentSessionGeneration(), serial = this.loadSerial
      const current = () => !this.disposed && generation === currentSessionGeneration() && serial === this.loadSerial
      const run = async (reason) => {
        if (this.acting || !current()) return
        const version = this.versionOf(x); if (version === null) return
        const ok = await this.runDormCommand(() => affairsContractApi.reviewDormTransfer(x.transferId, action, reason, version), () => { toast(action === 'APPROVE' ? '已通过' : '已驳回'); return this.load() }, '调宿处理失败')
        if (!ok && current() && action === 'REJECT') this.reviewTransfer(x, action, reason)
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
      const generation = currentSessionGeneration(), serial = this.loadSerial
      const current = () => !this.disposed && generation === currentSessionGeneration() && serial === this.loadSerial
      this.promptText({
        title: '处置说明', placeholder: '处置说明不少于5字', initial: previous, invalid: '处置说明至少5字',
        submit: async (note) => {
          if (this.acting || !current()) return
          const version = this.versionOf(x); if (version === null) return
          const ok = await this.runDormCommand(() => affairsContractApi.handleDormException(x.exceptionId, note, version), () => { toast('已处置'); return this.load() }, '异常处置失败')
          if (!ok && current()) this.handleException(x, note)
        }
      })
    }
  }
}
</script>

<style scoped>
.review-evidence{display:flex;flex-direction:column;gap:8px;margin:12px 0;padding:12px 0;border-block:1px solid var(--border-light,#e4e9f0)}

.allocation-summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-bottom: 12px; }
.provider-card { display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:12px;margin-bottom:10px;border:1px solid #cbd5e1;border-radius:10px;background:#f8fafc }.provider-card small,.provider-card text { display:block }.provider-card small { color:#64748b;font-size:10px }.provider-card view>text { margin-top:3px;color:#0f172a;font-size:13px;font-weight:700 }.provider-note { grid-column:1/-1;color:#475569!important;font-size:11px!important;line-height:1.5 }.presence-summary { display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:10px }.presence-summary view { padding:8px 3px;border-radius:8px;background:#fff7ed;text-align:center }.presence-summary text,.presence-summary small { display:block }.presence-summary text { color:#c2410c;font-size:17px;font-weight:700 }.presence-summary small { margin-top:2px;color:#64748b;font-size:9px }
.allocation-summary view { padding: 9px 4px; border-radius: 9px; background: #eff6ff; text-align: center; }
.allocation-summary text { display: block; color: #1d4ed8; font-size: 18px; font-weight: 700; }
.allocation-summary small { display: block; color: #64748b; font-size: 10px; margin-top: 3px; }
.seg { display: grid; grid-template-columns:1fr 1fr; gap: 8px; margin-bottom: 12px; }
.seg__btn { font-size: 13px; background: #f1f5f9; color: #334155; border: none; border-radius: 8px; padding: 8px; }
.seg__btn.on { background: #2563eb; color: #fff; }
.ar { margin-bottom: 10px; }
.checkout-row { padding: 16px 0; border-bottom: 1px solid #e2e8f0; }
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
