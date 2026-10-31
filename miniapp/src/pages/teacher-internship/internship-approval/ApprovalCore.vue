<template>
  <view class="internship-surface page-wrap teacher-approval">
    <MobileNavBar variant="teacher" title="实习审批" show-back />
    <view class="tabs">
      <view v-for="item in tabOptions" :key="item.key" class="tab" :class="{ on: tab === item.key }" @click="selectTab(item.key)">
        {{ item.label }}<text v-if="item.count" class="badge">{{ item.count }}</text><text v-if="tab === item.key" class="underline" />
      </view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack">
        <view v-if="batches.length" class="batch-card">
          <text class="muted">实习批次</text>
          <picker class="mobile-picker" mode="selector" :range="batchLabels" :value="batchIndex" :disabled="hasActiveOperation" @change="onBatch">
            <view class="picker-value">{{ batchLabels[batchIndex] || '请选择批次' }} <text>▾</text></view>
          </picker>
        </view>

        <MobileInlineAlert v-if="(tab === 'makeup' && makeups.length) || (tab === 'leave' && leaves.length)" type="info" description="请先查看证明材料；缺少必需证明不能通过。" />
        <view v-if="receipt && tab === receipt.kind" class="card result-card">
          <view class="row-between">
            <view class="flex-1">
              <text class="result-title">{{ receipt.actionLabel }} · {{ receipt.studentName }}</text>
              <text class="result-meta">{{ receipt.statusLabel }} · 记录 {{ receipt.id }} · 第{{ receipt.version }}版</text>
            </view>
            <text class="result-close" @click="receipt = null">关闭</text>
          </view>
          <text class="result-next">{{ receipt.pendingNext ? '已交下一责任人继续审批；全部必需节点通过前，请假和考勤不会提前生效。' : receipt.kind === 'overdue' ? '本次请假已办结，关联超期风险已同步；可继续处理下一条返岗记录。' : '下一步：学生端可回看结果；可继续办理当前批次下一份待办。' }}</text>
        </view>
        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次" description="当前身份的数据范围内没有可办理批次。" />

        <template v-else-if="tab === 'makeup'">
          <MobileInlineAlert v-if="!canReviewMakeup && !sourceErrors.makeup" type="warning" description="当前身份可查看补卡申请，不能审批。" />
          <MobileInlineAlert v-if="sourceErrors.makeup" type="warning" :description="sourceErrors.makeup" />
          <MobileGlobalState v-else-if="!makeups.length" state="empty" title="暂无待审补卡" description="仅显示本人指导范围。" />
          <InternshipApprovalCard
            v-for="item in makeups"
            :key="item.id"
            :item="item"
            kind="makeup"
            :acting="isActing('makeup', item.id)"
            :viewing="isViewing('makeup', item.id)"
            :can-review="canReviewMakeup"
            :evidence-viewed="isEvidenceViewed('makeup', item)"
            @review="review"
            @view-evidence="viewEvidence"
          />
          <view v-if="reviewDraft.visible && reviewDraft.kind === 'makeup'" class="card review-editor">
            <text class="review-title">{{ reviewDraft.action === 'REJECT' ? '驳回补卡' : '通过并补写打卡' }}</text>
            <text class="review-object">{{ reviewDraft.item?.studentName }} · {{ reviewDraft.item?.checkinDate }} · 第{{ reviewDraft.item?.version }}版</text>
            <MobileInlineAlert v-if="reviewDraft.error" type="warning" :description="reviewDraft.error" />
            <text class="review-label">处理意见{{ reviewDraft.action === 'REJECT' ? '（必填，不少于5字）' : '（选填）' }}</text>
            <textarea v-model="reviewDraft.comment" class="mobile-textarea review-textarea" maxlength="500" :disabled="reviewSubmitting" placeholder="写清核验结论；驳回时说明学生需要补充或修改什么" />
            <text class="review-count">{{ reviewDraft.comment.length }}/500</text>
            <view class="review-actions">
              <button class="mobile-control review-cancel flex-1" :disabled="reviewSubmitting" plain @click="closeReview">取消</button>
              <button class="mobile-control review-submit flex-1" :class="{ danger: reviewDraft.action === 'REJECT' }" :disabled="reviewSubmitting || reviewDraft.conflicted" plain @click="submitReview">{{ reviewSubmitting ? '提交中…' : '确认提交' }}</button>
            </view>
            <button v-if="reviewDraft.conflicted && reviewDraft.latest?.status === 'PENDING'" class="mobile-control review-cancel" @click="adoptReview">已核对当前记录，继续办理</button>
          </view>
        </template>

        <template v-else-if="tab === 'leave'">
          <MobileInlineAlert v-if="!canReviewLeave" type="warning" description="当前身份可查看请假申请，不能审批。" />
          <MobileInlineAlert v-if="sourceErrors.leave" type="warning" :description="sourceErrors.leave" />
          <MobileGlobalState v-else-if="!leaves.length" state="empty" title="暂无待审请假" description="仅显示本人指导范围。" />
          <InternshipApprovalCard
            v-for="item in leaves"
            :key="item.id"
            :item="item"
            kind="leave"
            :acting="isActing('leave', item.id)"
            :viewing="isViewing('leave', item.id)"
            :can-review="canReviewLeave && item.approvalProgress?.canReview !== false"
            :evidence-viewed="isEvidenceViewed('leave', item)"
            @review="review"
            @view-evidence="viewEvidence"
          />
          <view v-if="reviewDraft.visible && reviewDraft.kind === 'leave'" class="card review-editor">
            <text class="review-title">{{ reviewDraft.action === 'REJECT' ? '驳回请假' : reviewDraft.action === 'REQUEST_CHANGES' ? '退回补正，重交后从首级审批' : '通过本级审批' }}</text>
            <text class="review-object">{{ reviewDraft.item?.studentName }} · {{ reviewDraft.item?.startDate }}~{{ reviewDraft.item?.endDate }} · 第{{ reviewDraft.item?.version }}版</text>
            <MobileInlineAlert v-if="reviewDraft.error" type="warning" :description="reviewDraft.error" />
            <text class="review-label">审批意见{{ reviewDraft.action !== 'APPROVE' ? '（必填，不少于5字）' : '（选填）' }}</text>
            <textarea v-model="reviewDraft.comment" class="mobile-textarea review-textarea" maxlength="500" :disabled="reviewSubmitting" placeholder="写清审批结论；驳回时说明学生需要补充或修改什么" />
            <text class="review-count">{{ reviewDraft.comment.length }}/500</text>
            <view class="review-actions">
              <button class="mobile-control review-cancel flex-1" :disabled="reviewSubmitting" plain @click="closeReview">取消</button>
              <button class="mobile-control review-submit flex-1" :class="{ danger: reviewDraft.action === 'REJECT' }" :disabled="reviewSubmitting || reviewDraft.conflicted" plain @click="submitReview">{{ reviewSubmitting ? '提交中…' : '确认提交' }}</button>
            </view>
            <view v-if="reviewDraft.conflicted && reviewDraft.latest" class="detail"><text>最新申请：第{{ reviewDraft.latest.version }}版 · {{ reviewDraft.latest.statusLabel || '状态待核对' }}；{{ reviewDraft.latest.startDate }} ~ {{ reviewDraft.latest.endDate }}；{{ reviewDraft.latest.reason || '事由未填写' }}</text></view>
            <button v-if="reviewDraft.conflicted" class="mobile-control review-cancel" :disabled="reviewDraft.reading" @click="rereadConflict('review')">{{ reviewDraft.reading ? '读取中…' : '重新读取当前原单' }}</button>
            <button v-if="reviewDraft.conflicted && reviewDraft.latest?.status === 'PENDING'" class="mobile-control review-cancel" :disabled="reviewDraft.reading" @click="adoptReview">已核对当前记录，继续办理</button>
          </view>
        </template>

        <template v-else>
          <MobileInlineAlert v-if="!canReviewLeave" type="warning" description="当前身份仅可查看，不能办结销假。" />
          <MobileInlineAlert v-if="sourceErrors.overdue" type="warning" :description="sourceErrors.overdue" />
          <MobileGlobalState v-else-if="!overdues.length" state="empty" title="暂无待办结销假" description="当前批次没有超期未归或已销假待关闭风险的记录。" />
          <view v-if="returnDraft.visible" class="card review-editor">
            <text class="review-title">确认返岗并办结</text>
            <text class="review-object">{{ returnDraft.item?.studentName }} · {{ returnDraft.item?.startDate }}~{{ returnDraft.item?.endDate }} · 第{{ returnDraft.item?.version }}版</text>
            <MobileInlineAlert v-if="returnDraft.error" type="warning" :description="returnDraft.error" />
            <text class="review-label">返岗核实说明（必填，不少于2字）</text>
            <textarea v-model="returnDraft.note" class="mobile-textarea review-textarea" maxlength="500" :disabled="returnSubmitting" placeholder="如：已联系学生和企业，确认已返岗" />
            <text class="review-count">{{ returnDraft.note.length }}/500</text>
            <view class="review-actions">
              <button class="mobile-control review-cancel flex-1" :disabled="returnSubmitting" plain @click="closeReturn">取消</button>
              <button class="mobile-control review-submit flex-1" :disabled="returnSubmitting || returnDraft.conflicted || returnDraft.note.trim().length < 2" plain @click="submitReturn">{{ returnSubmitting ? '办结中…' : '确认返岗并办结' }}</button>
            </view>
            <view v-if="returnDraft.conflicted && returnDraft.latest" class="detail"><text>最新原单：第{{ returnDraft.latest.version }}版 · {{ returnDraft.latest.statusLabel || '状态待核对' }}；{{ returnDraft.latest.returnNote || '未填写销假说明' }}</text></view>
            <button v-if="returnDraft.conflicted" class="mobile-control review-cancel" :disabled="returnDraft.reading" @click="rereadConflict('return')">{{ returnDraft.reading ? '读取中…' : '重新读取当前原单' }}</button>
            <button v-if="returnDraft.conflicted && returnDraft.latest && !returnDraft.latest.returnAcknowledged && ['RETURNED', 'OVERDUE'].includes(returnDraft.latest.status)" class="mobile-control review-cancel" :disabled="returnDraft.reading" @click="adoptReturn">已核对当前记录，继续办理</button>
          </view>
          <view v-for="item in overdues" :key="item.id" class="card item-card">
            <view class="row-between">
              <view class="flex-1">
                <text class="title">{{ item.studentName || '—' }}</text>
                <text class="sub">{{ item.studentNo || '' }} · {{ item.leaveTypeLabel || '类型待核对' }}</text>
              </view>
              <MobileStatusTag :label="item.statusLabel || '状态待核对'" :type="item.status === 'OVERDUE' ? 'danger' : 'success'" />
            </view>
            <view class="detail"><text class="key">请假起止</text><text>{{ item.startDate || '—' }} ~ {{ item.endDate || '—' }}</text></view>
            <view v-if="item.returnNote" class="detail"><text class="key">销假说明</text><text class="flex-1">{{ item.returnNote }}</text></view>
            <view class="detail"><text class="key">提交时间</text><text>{{ formatTime(item.submittedAt || item.createdAt) }}</text></view>
            <view class="detail"><text class="key">数据版本</text><text>第{{ item.version }}版</text></view>
            <button
              class="mobile-control approve"
              :class="{ 'is-disabled': isActing('return', item.id) || !canReviewLeave }"
              :disabled="isActing('return', item.id) || !canReviewLeave"
              plain
              @click="openReturn(item)"
            >{{ isActing('return', item.id) ? '办结中…' : (canReviewLeave ? '确认返岗并同步风险' : '无办结权限') }}</button>
          </view>
          <button class="mobile-control" v-if="overdueHasMore && !sourceErrors.overdue" plain :disabled="loadingMore" @click="loadMore">{{ loadingMore ? '加载中…' : '加载更多待办结销假' }}</button>
        </template>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import InternshipApprovalCard from './ApprovalCard.vue'
import { formatDateTime } from '@/utils/format'
import { useInternshipContextStore } from '@/stores/internshipContext'
import {
  teacherInternshipLeaveEvidenceViewed,
  teacherInternshipLeaves,
  teacherInternshipLeaveReview,
  teacherInternshipMakeupEvidenceViewed,
  teacherInternshipMakeups,
  teacherInternshipMakeupReview
} from '@/services/internshipApi'
import { openBusinessFile } from '@/services/fileApi'
import { realRequest, normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'

export default {
  components: { InternshipApprovalCard },
  data: () => ({
    tab: 'makeup', makeups: [], leaves: [], overdues: [], state: 'loading',
    batches: [], batchId: '', batchIndex: 0,
    actingKeys: {}, viewingKeys: {}, viewedEvidence: {},
    makeupPage: 1, leavePage: 1, overduePage: 1, makeupHasMore: false, leaveHasMore: false, overdueHasMore: false,
    loadingMore: false, loadSeq: 0, moreRequest: 0,
    hidden: false, epoch: 0, generation: currentSessionGeneration(), defaultTabPending:true,
    sourceErrors: { makeup: '', leave: '', overdue: '' }, focusId: '', requestedBatchId: '',
    reviewSubmitting: false,
    reviewDraft: { visible: false, kind: '', item: null, action: '', comment: '', error: '' },
    returnSubmitting: false,
    returnDraft: { visible: false, item: null, note: '', error: '' },
    receipt: null
  }),
  computed: {
    context() { return useInternshipContextStore() },
    batchLabels() { return this.batches.map((item) => item.name || '实习批次') },
    tabOptions() {
      return [
        { key: 'makeup', label: '补卡审批', count: this.sourceErrors.makeup ? '—' : this.makeups.length },
        { key: 'leave', label: '请假审批', count: this.sourceErrors.leave ? '—' : this.leaves.length },
        { key: 'overdue', label: '销假办结', count: this.sourceErrors.overdue ? '—' : this.overdues.length }
      ]
    },
    canReviewMakeup() { return this.context.can('internship.makeup.review') },
    canReviewLeave() { return this.context.can('internship.leave.review') },
    hasActiveOperation() {
      return this.reviewSubmitting || this.returnSubmitting || Object.values(this.actingKeys).some(Boolean) || Object.values(this.viewingKeys).some(Boolean)
    }
  },
  beforeUnmount() { this.pause() },
  watch: { tab() { this.moreRequest++; this.loadingMore = false } },
  methods: {
    open(options) {
      if (['makeup', 'leave', 'overdue'].includes(options?.tab)) {this.tab = options.tab;this.defaultTabPending=false}
      this.focusId = String(options?.leaveId || '')
      this.requestedBatchId = String(options?.batchId || '')
      this.hidden = false
      this.load()
    },
    pause() {
      this.hidden = true; this.epoch++; this.loadSeq++; this.viewedEvidence = {}; this.actingKeys = {}; this.viewingKeys = {}
      this.reviewSubmitting = false; this.returnSubmitting = false; this.loadingMore = false
      for (const draft of [this.reviewDraft, this.returnDraft]) {
        draft.reading = false
        if (draft.conflicted) { draft.latest = null; draft.error = '恢复页面后请重新读取当前原单，输入已保留。' }
      }
    },
    selectTab(key) { if(this.hasActiveOperation || !['makeup','leave','overdue'].includes(key))return;this.defaultTabPending=false;this.tab=key },
    resume() { if (this.hidden) { this.hidden = false; this.load() } },
    capture() { return { epoch: this.epoch, generation: currentSessionGeneration(), batchId: String(this.batchId) } },
    current(scope) { return !this.hidden && scope.epoch === this.epoch && scope.generation === currentSessionGeneration() && scope.batchId === String(this.batchId) && scope.batchId === String(this.context.selectedBatchId || '') },
    recordKey(kind, id) { return `${kind}:${id}` },
    isActing(kind, id) { return !!this.actingKeys[this.recordKey(kind, id)] },
    isViewing(kind, id) { return !!this.viewingKeys[this.recordKey(kind, id)] },
    isEvidenceViewed(kind, item) {
      return !!item.evidenceViewed || !!this.viewedEvidence[this.evidenceKey(kind, item)]
    },
    evidenceKey(kind, item) { return `${kind}:${item.id}:${item.version}:${item.evidenceFileId || ''}` },
    setKey(mapName, key, value) {
      this[mapName] = { ...this[mapName], [key]: value }
    },
    formatTime: formatDateTime,
    async load(done) {
      if (this.hidden) { done?.(); return }
      if (this.generation !== currentSessionGeneration()) {
        this.pause(); this.hidden = false; this.generation = currentSessionGeneration()
        this.focusId = ''; this.requestedBatchId = ''; this.batchId = ''
        this.reviewDraft = { visible: false }; this.returnDraft = { visible: false }; this.receipt = null
      }
      const seq = ++this.loadSeq
      this.moreRequest++; this.loadingMore = false
      const generation = currentSessionGeneration()
      this.state = 'loading'
      this.makeupPage = 1
      this.leavePage = 1
      this.overduePage = 1
      this.makeupHasMore = false
      this.leaveHasMore = false
      this.overdueHasMore = false
      try {
        this.context.restore()
        await this.context.load(true)
        if (this.hidden || seq !== this.loadSeq || generation !== currentSessionGeneration()) return
        if(!this.context.can('internship.makeup.view') && !this.context.can('internship.leave.view')){this.makeups=[];this.leaves=[];this.overdues=[];this.state='forbidden';return}
        if(this.defaultTabPending){if(this.tab==='makeup'&&!this.context.can('internship.makeup.view'))this.tab='leave';this.defaultTabPending=false}
        let focus = null
        if (this.focusId) {
          if (!/^[1-9]\d*$/.test(this.focusId)) throw new Error('请假待办编号无效')
          const query = this.requestedBatchId ? `?batchId=${encodeURIComponent(this.requestedBatchId)}` : ''
          focus = await realRequest(`/mobile/teacher/internship/context/leaves/${encodeURIComponent(this.focusId)}${query}`)
          if (this.hidden || seq !== this.loadSeq || generation !== currentSessionGeneration()) return
        }
        this.batches = this.context.batches || []
        const requested = String(focus?.batchId || this.requestedBatchId || '')
        if (requested) {
          if (!this.batches.some(item => String(item.id) === requested)) throw new Error('该待办所属批次不在当前身份范围内')
          this.context.selectBatch(requested)
        }
        if (this.batchId && String(this.batchId) !== String(this.context.selectedBatchId || '')) {
          this.epoch++; this.reviewDraft = { visible: false }; this.returnDraft = { visible: false }; this.receipt = null; this.viewedEvidence = {}
        }
        this.batchId = this.context.selectedBatchId || ''
        this.batchIndex = Math.max(0, this.batches.findIndex((item) => String(item.id) === String(this.batchId)))
        if (!this.batchId) {
          this.makeups = []; this.leaves = []; this.overdues = []; this.state = 'ready'; return
        }
        const query = `?batchId=${encodeURIComponent(this.batchId)}`
        const scope = this.capture()
        const sources = [
          ['makeup', 'internship.makeup.view', () => teacherInternshipMakeups(scope.batchId)],
          ['leave', 'internship.leave.view', () => teacherInternshipLeaves(scope.batchId)],
          ['overdue', 'internship.leave.view', () => realRequest(`/mobile/teacher/internship/context/leaves/overdue${query}`)]
        ]
        const results = await Promise.allSettled(sources.map(([, permission, read]) => this.context.can(permission) ? read() : Promise.reject(new Error('当前身份没有此类记录的查看权限'))))
        if (seq !== this.loadSeq || !this.current(scope)) return
        const data = {}
        results.forEach((result, index) => { const [key,permission] = sources[index]; data[key] = result.status === 'fulfilled' ? result.value : {}; this.sourceErrors[key] = result.status === 'fulfilled' ? '' : !this.context.can(permission) ? '当前身份无权查看此类记录，请切换有权身份或联系学校。' : '此类记录暂未读取，请核对权限或重试' })
        this.makeups = data.makeup?.items || data.makeup?.list || []
        this.leaves = data.leave?.items || data.leave?.list || []
        this.makeupHasMore = !!data.makeup?.hasMore
        this.leaveHasMore = !!data.leave?.hasMore
        this.overdues = data.overdue?.list || []
        this.overdueHasMore = !!data.overdue?.hasMore
        if (focus && String(focus.batchId) === scope.batchId) {
          const rows = focus.status === 'PENDING' ? this.leaves : this.overdues
          if (['PENDING', 'RETURNED', 'OVERDUE'].includes(focus.status) && !focus.returnAcknowledged && !rows.some(item => String(item.id) === String(focus.id))) rows.unshift(focus)
        }
        this.state = 'ready'
      } catch (error) {
        if (this.hidden || seq !== this.loadSeq || generation !== currentSessionGeneration()) return
        this.state = 'error'
        toast(error?.message || '实习审批数据加载失败')
      } finally { done?.() }
    },
    async onBatch(event) {
      if (this.hasActiveOperation) return
      this.focusId = ''; this.requestedBatchId = ''; this.epoch++; this.viewedEvidence = {}
      this.batchIndex = Number(event.detail.value)
      this.context.selectBatch(this.batches[this.batchIndex]?.id)
      this.makeups = []
      this.leaves = []
      this.overdues = []
      this.closeReview()
      this.closeReturn()
      this.receipt = null
      await this.load()
    },
    async loadMore() {
      if (!this.batchId || this.loadingMore || this.state !== 'ready') return
      const selectedBatch = this.batchId
      const scope = this.capture()
      const request = ++this.moreRequest, sequence = this.loadSeq, tab = this.tab
      const current = () => this.current(scope) && request === this.moreRequest && sequence === this.loadSeq && tab === this.tab
      this.loadingMore = true
      try {
        if (this.tab === 'makeup' && this.makeupHasMore) {
          const page = this.makeupPage + 1
          const data = await teacherInternshipMakeups(selectedBatch, page, 20)
          if (!current()) return
          const known = new Set(this.makeups.map(item => String(item.id)))
          this.makeups = [...this.makeups, ...(data?.items || []).filter(item => !known.has(String(item.id)))]
          this.makeupPage = page
          this.makeupHasMore = !!data?.hasMore
        } else if (this.tab === 'leave' && this.leaveHasMore) {
          const page = this.leavePage + 1
          const data = await teacherInternshipLeaves(selectedBatch, page, 20)
          if (!current()) return
          const known = new Set(this.leaves.map(item => String(item.id)))
          this.leaves = [...this.leaves, ...(data?.items || []).filter(item => !known.has(String(item.id)))]
          this.leavePage = page
          this.leaveHasMore = !!data?.hasMore
        } else if (this.tab === 'overdue' && this.overdueHasMore) {
          const page = this.overduePage + 1
          const data = await realRequest(`/mobile/teacher/internship/context/leaves/overdue?batchId=${encodeURIComponent(selectedBatch)}&page=${page}&pageSize=20`)
          if (!current()) return
          const known = new Set(this.overdues.map(item => String(item.id)))
          this.overdues = [...this.overdues, ...(data?.list || []).filter(item => !known.has(String(item.id)))]
          this.overduePage = page
          this.overdueHasMore = !!data?.hasMore
        }
      } catch (error) { if (current()) toast(error?.message || '后续记录读取失败，请重试')
      } finally { if (current()) this.loadingMore = false }
    },
    async viewEvidence({ kind, item }) {
      const key = this.recordKey(kind, item.id)
      const evidenceKey = this.evidenceKey(kind, item)
      const batchId = this.batchId
      const snapshot = { ...item }
      const scope = this.capture()
      if (!this.current(scope) || this.sourceErrors[kind] || this.isViewing(kind, item.id) || this.isActing(kind, item.id)) return
      if (!item.evidenceFileId) return toast('该申请没有可查看的证明材料')
      this.setKey('viewingKeys', key, true)
      try {
        await openBusinessFile(item.evidenceFileId)
        if (!this.current(scope) || this.evidenceKey(kind, item) !== evidenceKey) return
        if (kind === 'makeup') await teacherInternshipMakeupEvidenceViewed(item.id)
        else {
          const viewed = await teacherInternshipLeaveEvidenceViewed(snapshot.id, {
            batchId, expectedVersion: snapshot.version, evidenceFileId: snapshot.evidenceFileId
          })
          if (String(viewed?.id) !== String(snapshot.id) || viewed?.version !== snapshot.version || String(viewed?.evidenceFileId) !== String(snapshot.evidenceFileId)) return toast('材料版本已变化，请重新核对')
        }
        if (!this.current(scope) || this.evidenceKey(kind, item) !== evidenceKey) return
        this.setKey('viewedEvidence', evidenceKey, true)
        toast('材料已查看，审计留痕已写入')
      } catch (error) {
        if (this.current(scope)) toast(error?.message || '材料查看失败，未写入查看留痕')
      } finally { if (this.current(scope)) this.setKey('viewingKeys', key, false) }
    },
    review({ kind, item, action }) {
      const key = this.recordKey(kind, item.id)
      const canReview = kind === 'makeup' ? this.canReviewMakeup : this.canReviewLeave
      if (!canReview || this.hidden || this.sourceErrors[kind] || this.state !== 'ready') return toast('当前身份没有该类审批权限或批次正在切换')
      if (this.isActing(kind, item.id) || this.isViewing(kind, item.id)) return
      if (action === 'APPROVE') {
        if (item.evidenceRequired && !item.evidenceFileId) return toast('缺少规则要求的证明材料，不能通过')
        if (item.evidenceFileId && !this.isEvidenceViewed(kind, item)) return toast('请先查看证明材料，再执行通过')
      }
      this.reviewDraft = { visible: true, kind, item: { ...item }, action, comment: '', error: '', batchId: this.batchId, generation: currentSessionGeneration(), conflicted: false, latest: null }
    },
    closeReview() {
      if (this.reviewSubmitting) return
      this.reviewDraft = { visible: false, kind: '', item: null, action: '', comment: '', error: '' }
    },
    async submitReview() {
      const draft = this.reviewDraft
      const item = draft.item
      if (!draft.visible || !item || this.reviewSubmitting || draft.conflicted || draft.batchId !== this.batchId || draft.generation !== currentSessionGeneration() || this.hidden || this.sourceErrors[draft.kind]) return
      if (!(draft.kind === 'makeup' ? this.canReviewMakeup : this.canReviewLeave)) return
      if (draft.action === 'APPROVE' && (item.evidenceRequired && !item.evidenceFileId || item.evidenceFileId && !this.isEvidenceViewed(draft.kind, item))) { this.reviewDraft.error = '请先查看并核对当前版本证明材料'; return }
      const comment = String(draft.comment || '').trim()
      if (draft.action !== 'APPROVE' && comment.length < 5) {
        this.reviewDraft.error = '退回或驳回原因不少于5个字，并写清学生需要补充或修改什么。'
        return
      }
      const key = this.recordKey(draft.kind, item.id)
      const selectedBatch = this.batchId
      const scope = this.capture()
      this.reviewSubmitting = true
      this.reviewDraft.error = ''
      this.setKey('actingKeys', key, true)
      try {
        const body = { action: draft.action, comment, expectedVersion: item.version }
        const result = draft.kind === 'makeup'
          ? await teacherInternshipMakeupReview(item.id, selectedBatch, body)
          : await teacherInternshipLeaveReview(item.id, selectedBatch, body)
        if (!this.current(scope) || this.reviewDraft !== draft) return
        this.receipt = {
          kind: draft.kind, id: result?.id || item.id, version: result?.version ?? item.version,
          pendingNext: draft.kind === 'leave' && result?.status === 'PENDING',
          statusLabel: result?.statusLabel || (draft.action === 'REJECT' ? '已驳回' : draft.action === 'REQUEST_CHANGES' ? '已退回，请补正' : '已通过'),
          actionLabel: draft.action === 'REJECT' ? '已驳回' : draft.action === 'REQUEST_CHANGES' ? '已退回补正，等待学生修改重交' : (draft.kind === 'makeup' ? '已通过并补写打卡' : result?.status === 'PENDING' ? '本级通过，已交下一级' : '全部审批通过'),
          studentName: item.studentName || '学生'
        }
        this.reviewDraft = { visible: false, kind: '', item: null, action: '', comment: '', error: '' }
        toast(this.receipt.actionLabel)
        await this.load()
      } catch (error) {
        if (!this.current(scope) || this.reviewDraft !== draft) return
        if (normalizeError(error).kind === 'conflict') {
          const savedComment = draft.comment
          const savedId = item.id
          let latest = null, readError = ''
          try {
            if (draft.kind === 'leave') latest = await this.rereadLeave(item, scope)
            else { await this.load(); latest = this.makeups.find(row => String(row.id) === String(savedId)) }
          } catch (error) { readError = error?.message || '当前原单读取失败，请重试核对' }
          if (!this.current(scope) || this.reviewDraft !== draft) return
          this.reviewDraft = {
            ...draft, item, latest: latest ? { ...latest } : null, conflicted: true, comment: savedComment,
            error: readError || (latest?.status === 'PENDING' ? '记录已被更新。处理意见已保留，请核对最新版本后重新提交。' : '该待办已被处理，处理意见已保留供你核对。')
          }
        } else this.reviewDraft.error = error?.message || '审批失败，处理意见已保留。'
      } finally {
        if (this.current(scope)) { this.reviewSubmitting = false; this.setKey('actingKeys', key, false) }
      }
    },
    adoptReview() {
      const draft = this.reviewDraft, latest = draft.latest
      if (this.hidden || this.reviewSubmitting || draft.reading || !latest || draft.batchId !== this.batchId || draft.generation !== currentSessionGeneration() || this.sourceErrors[draft.kind] || String(latest.id) !== String(draft.item.id) || latest.status !== 'PENDING') return
      this.reviewDraft = { ...draft, item: { ...latest }, conflicted: false, latest: null, error: '' }
      if (draft.kind === 'leave') this.leaves = this.leaves.map(row => String(row.id) === String(latest.id) ? { ...latest } : row)
    },
    async rereadLeave(item, scope) {
      const row = await realRequest(`/mobile/teacher/internship/context/leaves/${encodeURIComponent(item.id)}?batchId=${encodeURIComponent(scope.batchId)}`)
      if (!this.current(scope)) return null
      if (String(row?.id) !== String(item.id) || String(row?.batchId) !== scope.batchId || !Number.isInteger(row?.version) || row.version < 0) throw { message: '当前原单或批次不一致，请重新核对' }
      return row
    },
    async rereadConflict(kind) {
      if (!['review', 'return'].includes(kind)) return
      const key = kind === 'return' ? 'returnDraft' : 'reviewDraft', draft = this[key]
      if (!draft.visible || !draft.item || !draft.conflicted || draft.reading || this.hidden || !this.canReviewLeave ||
          kind === 'review' && draft.kind !== 'leave' || draft.batchId !== this.batchId ||
          draft.generation !== currentSessionGeneration() || this.sourceErrors[kind === 'return' ? 'overdue' : 'leave']) return
      const scope = this.capture()
      draft.reading = true; draft.latest = null; draft.error = ''
      try {
        const latest = await this.rereadLeave(draft.item, scope)
        if (!this.current(scope) || this[key] !== draft) return
        draft.latest = latest ? { ...latest } : null
        draft.error = '当前原单已重新读取，请核对最新版本后再决定是否继续。'
      } catch (error) {
        if (this.current(scope) && this[key] === draft) draft.error = error?.message || '当前原单读取失败，输入已保留，请重试核对。'
      } finally {
        if (this.current(scope) && this[key] === draft) draft.reading = false
      }
    },
    openReturn(item) {
      if (!this.canReviewLeave || this.hidden || this.sourceErrors.overdue || this.state !== 'ready') return toast('当前记录未就绪或没有销假办结权限')
      if (this.isActing('return', item.id)) return
      this.returnDraft = { visible: true, item: { ...item }, note: '', error: '', batchId: this.batchId, generation: currentSessionGeneration(), conflicted: false, latest: null }
    },
    closeReturn() {
      if (this.returnSubmitting) return
      this.returnDraft = { visible: false, item: null, note: '', error: '' }
    },
    async submitReturn() {
      const draft = this.returnDraft
      const item = draft.item
      const note = String(draft.note || '').trim()
      if (!draft.visible || !item || this.returnSubmitting || note.length < 2 || draft.conflicted || draft.batchId !== this.batchId || draft.generation !== currentSessionGeneration() || this.hidden || this.sourceErrors.overdue) return
      if (!this.canReviewLeave) return
      const key = this.recordKey('return', item.id)
      const selectedBatch = this.batchId
      const scope = this.capture()
      this.returnSubmitting = true
      this.returnDraft.error = ''
      this.setKey('actingKeys', key, true)
      try {
        const result = await realRequest(`/mobile/teacher/internship/context/leaves/${encodeURIComponent(item.id)}/ack-return`, {
          method: 'POST', data: { note, expectedVersion: item.version, batchId: selectedBatch }
        })
        if (!this.current(scope) || this.returnDraft !== draft) return
        this.receipt = {
          kind: 'overdue', id: result?.id || item.id, version: result?.version ?? item.version,
          statusLabel: result?.statusLabel || '已销假', actionLabel: '返岗已确认',
          studentName: item.studentName || '学生'
        }
        this.returnDraft = { visible: false, item: null, note: '', error: '' }
        toast('返岗已确认，关联风险已同步处理')
        await this.load()
      } catch (error) {
        if (!this.current(scope) || this.returnDraft !== draft) return
        if (normalizeError(error).kind === 'conflict') {
          const savedNote = draft.note
          let latest = null, readError = ''
          try { latest = await this.rereadLeave(item, scope) }
          catch (error) { readError = error?.message || '当前原单读取失败，请重试核对' }
          if (!this.current(scope) || this.returnDraft !== draft) return
          this.returnDraft = {
            ...draft, item, latest: latest ? { ...latest } : null, conflicted: true, note: savedNote,
            error: readError || (latest && !latest.returnAcknowledged && ['RETURNED', 'OVERDUE'].includes(latest.status) ? '记录已更新。核实说明已保留，请确认最新版本后重新提交。' : '该记录已办结或状态已变化。核实说明已保留供你核对。')
          }
        } else this.returnDraft.error = error?.message || '销假办结失败，核实说明已保留。'
      } finally {
        if (this.current(scope)) { this.returnSubmitting = false; this.setKey('actingKeys', key, false) }
      }
    },
    adoptReturn() {
      const draft = this.returnDraft, latest = draft.latest
      if (this.hidden || this.returnSubmitting || draft.reading || !latest || latest.returnAcknowledged || draft.batchId !== this.batchId || draft.generation !== currentSessionGeneration() || this.sourceErrors.overdue || String(latest.id) !== String(draft.item.id) || !['RETURNED', 'OVERDUE'].includes(latest.status)) return
      this.returnDraft = { ...draft, item: { ...latest }, conflicted: false, latest: null, error: '' }
      this.overdues = this.overdues.map(row => String(row.id) === String(latest.id) ? { ...latest } : row)
    }
  }
}
</script>

<style scoped>
.tabs { display: flex; background: var(--bg-card); border-bottom: 1px solid var(--border-light); }
.tab { position: relative; flex: 1; padding: 14px 4px 12px; text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); }
.tab.on { color: var(--brand-primary); font-weight: var(--font-weight-semibold); }
.underline { position: absolute; left: 34%; right: 34%; bottom: 0; height: 2px; border-radius: 2px; background: var(--brand-primary); }
.badge { display: inline-flex; min-width: 16px; height: 16px; margin-left: 4px; padding: 0 4px; align-items: center; justify-content: center; border-radius: 8px; background: var(--error-500); color: #fff; font-size: 10px; box-sizing: border-box; }
.batch-card { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }
.muted { color: var(--text-tertiary); font-size: var(--font-size-sm); }
.picker-value { color: var(--brand-primary); font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); text-align: right; }
.item-card { display: flex; flex-direction: column; gap: 10px; }
.title { display: block; color: var(--text-primary); font-size: var(--font-size-md); font-weight: var(--font-weight-semibold); }
.sub { display: block; margin-top: 3px; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.detail { display: flex; gap: 12px; color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.55; }
.key { width: 68px; flex: 0 0 68px; color: var(--text-tertiary); }
.approve { margin: 4px 0 0; background: var(--brand-primary); color: #fff; border: 0; }
.approve.is-disabled { background: var(--gray-300); color: var(--text-tertiary); }
.result-card{border-color:var(--success-200,#bbf7d0);background:var(--success-50,#f0fdf4)}.result-title{display:block;color:var(--success-800,#166534);font-size:var(--font-size-md);font-weight:600}.result-meta,.result-next{display:block;margin-top:5px;color:var(--success-700,#15803d);font-size:var(--font-size-xs);line-height:1.5}.result-close{flex-shrink:0;color:var(--success-700,#15803d);font-size:var(--font-size-xs)}.review-editor{display:flex;flex-direction:column;gap:10px;border-color:var(--teacher-200,#bfdbfe);background:var(--teacher-50,#eff6ff)}.review-title{font-size:var(--font-size-md);font-weight:600;color:var(--text-primary)}.review-object{font-size:var(--font-size-xs);color:var(--text-secondary)}.review-label{margin-top:3px;font-size:var(--font-size-sm);font-weight:600;color:var(--text-secondary)}.review-textarea{box-sizing:border-box;width:100%;min-height:112px;padding:12px;border:1px solid var(--border-light);border-radius:var(--radius-md);background:var(--bg-card);font-size:var(--font-size-base);line-height:1.6}.review-count{align-self:flex-end;color:var(--text-tertiary);font-size:10px}.review-actions{display:flex;gap:10px}.review-cancel,.review-submit{min-height:44px;border-radius:var(--radius-md);font-size:var(--font-size-md)}.review-cancel{border:1px solid var(--border-base);background:var(--bg-card);color:var(--text-secondary)}.review-submit{border:0;background:var(--teacher-600);color:#fff}.review-submit.danger{background:var(--danger-600)}
.teacher-approval :deep(.page-pad){width:100%;max-width:760px;margin:0 auto;box-sizing:border-box}.teacher-approval .card{border-radius:8px;box-shadow:none}.teacher-approval .tabs{max-width:760px;margin:0 auto}.teacher-approval .tab,.teacher-approval button,.teacher-approval .picker-value{min-height:44px;font-size:15px;box-sizing:border-box}.teacher-approval .tab{display:flex;align-items:center;justify-content:center}.teacher-approval .batch-card{padding:4px 0 12px;border-bottom:1px solid var(--border-light)}.teacher-approval .muted,.teacher-approval .result-meta,.teacher-approval .result-next,.teacher-approval .review-object,.teacher-approval .review-label,.teacher-approval .detail{font-size:14px;line-height:22px}.teacher-approval .review-title,.teacher-approval .result-title{font-size:16px;line-height:24px}.teacher-approval .review-textarea{font-size:15px;line-height:22px}.teacher-approval .result-close{display:inline-flex;align-items:center;min-width:44px;min-height:44px;font-size:14px}
</style>
