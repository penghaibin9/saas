<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" :title="materialReturnContext.bizType ? '材料审核' : '学工待办'" :subtitle="materialReturnContext.bizType ? '核对业务材料与当前版本' : '查看待办、材料与办理进度'" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="data">
        <template v-if="!materialReturnContext.bizType">
        <view class="ta__work-study" @click="uni.navigateTo({ url: '/pages/teacher/affairs/work-study/index' })">
          <view><text class="ta__label">勤工助学工作区</text><text class="ta__sub">审核申请、核验协议、确认上岗与登记月度考核</text></view><text class="ta__go">›</text>
        </view>
        <view class="ta__work-study" @click="uni.navigateTo({ url: '/pages/teacher/affairs/loan/index' })">
          <view><text class="ta__label">贷款回执核验</text><text class="ta__sub">核验、退回与确认台账</text></view><text class="ta__go">›</text>
        </view>
        <view class="ta__work-study" @click="uni.navigateTo({ url: '/pages/teacher/affairs/reduction/index' })">
          <view><text class="ta__label">减免与临补</text><text class="ta__sub">待审、退回与结果落实</text></view><text class="ta__go">›</text>
        </view>
        <view class="ta__work-study" @click="uni.navigateTo({ url: '/pages/teacher/affairs/activity/index' })">
          <view><text class="ta__label">活动现场与名单确认</text><text class="ta__sub">报名截止、现场签到、结束活动并生成积分</text></view><text class="ta__go">›</text>
        </view>
        <view class="ta__total">
          <view><text class="ta__eyebrow">今日先做</text><view><text class="ta__total-n">{{ data.total }}</text><text class="ta__total-l">项学工待办</text></view></view>
          <view class="ta__priority-stats">
            <view class="ta__priority-stat is-overdue"><text>{{ prioritySummary.overdue }}</text><text>已逾期</text></view>
            <view class="ta__priority-stat is-near"><text>{{ prioritySummary.dueWithin24h }}</text><text>24h内</text></view>
            <view class="ta__priority-stat"><text>{{ prioritySummary.ordinary }}</text><text>普通</text></view>
          </view>
        </view>

        <view class="section-head"><text class="section-head__title">待我处理</text></view>
        <view class="ta__empty" v-if="!todoItems.length"><text>暂无待办</text></view>
        <view class="stack" v-else>
          <view v-for="item in todoItems" :key="item.todoId" class="ta__todo" :class="priorityClass(item)" @click="openTodo(item)">
            <view class="flex-1">
              <view class="ta__todo-head">
                <text class="ta__label">{{ item.label || item.todoType }}</text>
                <text v-if="item.overdue" class="ta__overdue">已逾期</text>
                <text v-else-if="item.dueWithin24h" class="ta__near">24h 内</text>
              </view>
              <text class="ta__title">{{ item.title || '学工待办' }}</text>
              <text v-if="item.studentName || item.studentNo" class="ta__sub">
                {{ item.studentName || '学生' }}{{ item.studentNo ? ` · ${item.studentNo}` : '' }}{{ item.className ? ` · ${item.className}` : '' }}
              </text>
              <text v-if="item.dueAt" class="ta__due">截止 {{ formatTime(item.dueAt) }}</text>
            </view>
            <text class="ta__go">›</text>
          </view>
        </view>
        <button v-if="todoHasMore" class="btn btn-secondary ta__load-more" :disabled="todoLoading" @click="loadMoreTodos">{{ todoLoading ? '加载中…' : '继续加载待办' }}</button>

        </template>

        <view id="leave-material-section" class="section-head ta__section">
          <text class="section-head__title">材料补交审核</text>
          <text class="ta__refresh" @click="loadMaterials">刷新</text>
        </view>
        <view v-if="materialReturnContext.bizType" class="ta__context card"><text>仅显示{{ bizLabel(materialReturnContext.bizType) }}材料</text><button class="btn btn-secondary" @click="returnToApplication">{{ materialReturnContext.bizType === 'PROFILE' ? '返回学生档案' : '返回原申请' }}</button></view>
        <MobileInlineAlert v-if="materialError" type="warning" title="材料队列暂不可用" :description="materialError" />
        <view v-else-if="!materials.length" class="ta__empty card"><text>暂无材料缺项</text></view>
        <view v-else class="stack">
          <view
            v-for="item in materials"
            :key="item.requirementId"
            :id="'teacher-material-' + item.requirementId"
            class="card ta__material"
            :class="{ 'is-focus': String(item.requirementId) === focusMaterialId }"
          >
            <view class="row-between ta__todo-head">
              <view class="flex-1">
                <text class="ta__label">{{ item.itemName }}</text>
                <text class="ta__sub">{{ materialStudentLine(item) }}</text>
                <text class="ta__sub">{{ materialBizLine(item) }}</text>
              </view>
              <MobileStatusTag :status="item.status" :label="item.statusLabel || '状态待确认'" />
            </view>
            <text v-if="item.requirementReason" class="ta__title">缺项说明：{{ item.requirementReason }}</text>
            <text v-if="item.dueAt" class="ta__due" :class="{ 'is-danger': item.overdue }">截止 {{ formatTime(item.dueAt) }}{{ item.overdue ? '（已逾期）' : '' }}</text>
            <text class="ta__sub">审核责任人：{{ item.reviewOwner || '未识别' }}</text>

            <view v-if="item.currentSubmission" class="ta__submission">
              <view class="flex-1">
                <text class="ta__label">V{{ item.currentSubmission.versionNo }} · {{ item.currentSubmission.fileName }}</text>
                <text class="ta__sub">{{ item.currentSubmission.statusLabel || item.currentSubmission.status }} · {{ formatTime(item.currentSubmission.submittedAt) }}</text>
              </view>
              <text class="ta__link" @click="downloadMaterial(item.currentSubmission)">查看材料</text>
            </view>

            <view class="ta__actions">
              <label v-if="canRemind(item)" class="ta__check" @click.stop="toggleMaterial(item)">
                <view class="ta__box" :class="{ checked: selectedMaterialIds.includes(item.requirementId) }">{{ selectedMaterialIds.includes(item.requirementId) ? '✓' : '' }}</view>
                <text>加入批量提醒</text>
              </label>
              <button v-if="allows(item, 'ACCEPT_MATERIAL')" class="btn btn-primary ta__small" :disabled="materialBusy === item.requirementId" @click="reviewMaterial(item, 'ACCEPT')">验收</button>
              <button v-if="allows(item, 'RETURN_MATERIAL')" class="btn btn-danger ta__small" :disabled="materialBusy === item.requirementId" @click="startReturn(item)">退回</button>
              <button v-if="allows(item, 'WAIVE_MATERIAL')" class="btn btn-secondary ta__small" :disabled="materialBusy === item.requirementId" @click="reviewMaterial(item, 'WAIVE')">免交</button>
            </view>
            <view v-if="returningId === item.requirementId" class="ta__return-box">
              <textarea v-model.trim="returnReason" maxlength="500" placeholder="填写5-500字退回原因" />
              <view class="ta__return-actions"><button class="btn btn-secondary ta__small" @click="cancelReturn">取消</button><button class="btn btn-danger ta__small" :disabled="returnReason.length < 5" @click="reviewMaterial(item, 'RETURN')">确认退回</button></view>
            </view>
          </view>
        </view>
        <button v-if="materialHasMore" class="btn btn-secondary ta__load-more" :disabled="materialLoading" @click="loadMoreMaterials">{{ materialLoading ? '加载中…' : '继续加载材料' }}</button>
        <button v-if="selectedMaterialIds.length" class="btn btn-primary ta__batch-btn" :disabled="batchBusy" @click="createReminderBatch">
          {{ batchBusy ? '逐条校验中…' : `批量提醒已选 ${selectedMaterialIds.length} 项` }}
        </button>

        <template v-if="!materialReturnContext.bizType || batchJobs.length">
        <view class="section-head ta__section"><text class="section-head__title">批量提醒记录</text></view>
        <MobileInlineAlert type="info" title="仅开放低风险材料提醒" description="审批、发放、处分和风险关闭必须继续逐条办理。" />
        <view v-if="!batchJobs.length" class="ta__empty card"><text>暂无批次记录</text></view>
        <view v-else class="stack">
          <view v-for="job in batchJobs" :key="job.batchJobId" class="ta__card" @click="openBatch(job)">
            <view class="flex-1"><text class="ta__label">{{ job.batchNo }}</text><text class="ta__sub">{{ job.statusLabel || job.status }} · 成功 {{ job.successCount }} / 失败 {{ job.failureCount }}</text></view>
            <button v-if="(job.allowedActions || []).includes('RETRY_FAILED')" class="btn btn-secondary ta__small" :disabled="batchBusy" @click.stop="retryBatch(job)">重试失败项</button>
            <text v-else class="ta__go">›</text>
          </view>
        </view>
        <button v-if="batchHasMore" class="btn btn-secondary ta__load-more" :disabled="batchLoading" @click="loadMoreBatches">{{ batchLoading ? '加载中…' : '继续加载批次' }}</button>
        <view v-if="activeBatch" class="card ta__batch-detail">
          <text class="ta__label">{{ activeBatch.batchNo }} · {{ activeBatch.statusLabel || activeBatch.status }}</text>
          <view v-for="detail in (activeBatch.items || [])" :key="detail.itemId" class="ta__batch-item">
            <view class="flex-1"><text class="ta__title">任务项编号 {{ detail.itemKey }}</text><text class="ta__sub">{{ batchItemStatusLabel(detail.status) }} · 尝试 {{ detail.attemptCount }} 次</text><text v-if="detail.errorMessage" class="ta__error">{{ detail.errorMessage }}</text></view>
          </view>
        </view>

        </template>
        <template v-if="!materialReturnContext.bizType">
        <view class="section-head ta__section"><text class="section-head__title">按业务分类</text></view>
        <view class="stack">
          <view v-for="c in data.cards" :key="c.todoType" class="ta__card" @click="openCard(c)">
            <text class="ta__label">{{ c.label }}</text>
            <view class="ta__right"><text class="ta__count">{{ c.count }}</text><text class="ta__go">›</text></view>
          </view>
        </view>

        </template>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { affairsContractApi } from '@/services/affairsContractApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const ROUTES = {
  WORK_STUDY_REVIEW: '/pages/teacher/affairs/work-study/index', WORK_STUDY_ONBOARD: '/pages/teacher/affairs/work-study/index',
  STUDENT_LOAN_REVIEW: '/pages/teacher/affairs/loan/index', STUDENT_LOAN_CONFIRM: '/pages/teacher/affairs/loan/index', FEE_REDUCTION_REVIEW: '/pages/teacher/affairs/reduction/index',
  FEE_REDUCTION_FULFILL: '/pages/teacher/affairs/reduction/index',
  LEAVE_APPROVAL: '/pages/teacher/affairs-leave/index', LEAVE_CANCEL: '/pages/teacher/affairs-leave/index',
  LEAVE_OVERDUE: '/pages/teacher/affairs-leave/index', LEAVE_EXTENSION: '/pages/teacher/affairs-leave/index',
  AID_APPROVAL: '/pages/teacher/affairs-review/index?type=AID_APPROVAL',
  AID_ADJUST: '/pages/teacher/affairs-review/index?type=AID_ADJUST',
  FUNDING_APPROVAL: '/pages/teacher/affairs-review/index?type=FUNDING_APPROVAL',
  DISCIPLINE_APPROVAL: '/pages/teacher/affairs-review/index?type=DISCIPLINE_APPROVAL',
  DISCIPLINE_REMOVE: '/pages/teacher/affairs-review/index?type=DISCIPLINE_REMOVE',
  RISK_HANDLE: '/pages/teacher/affairs-review/index?type=RISK_HANDLE',
  DORM_TRANSFER: '/pages/teacher/dorm-review/index?tab=transfer',
  DORM_EXCEPTION: '/pages/teacher/dorm-review/index?tab=exception',
  AID_OBJECTION_REVIEW: '/pages/teacher/affairs-review/index?type=AID_OBJECTION_REVIEW',
  FUNDING_APPEAL_REVIEW: '/pages/teacher/affairs-review/index?type=FUNDING_APPEAL_REVIEW',
  DISCIPLINE_APPEAL_REVIEW: '/pages/teacher/affairs-review/index?type=DISCIPLINE_APPEAL_REVIEW',
  SECOND_CLASS_APPEAL_REVIEW: '/pages/teacher/affairs-review/index?type=SECOND_CLASS_APPEAL_REVIEW'
}

export default {
  data() {
    return {
      data: null,
      state: 'loading',
      materials: [],
      materialError: '',
      materialBusy: '',
      selectedMaterialIds: [],
      returningId: '',
      returnReason: '',
      batchJobs: [],
      activeBatch: null,
      batchBusy: false,
      leaveContext: {}, focusMaterialId: '',
      todoPage: 1,
      todoHasMore: false,
      todoLoading: false,
      materialPage: 1,
      materialHasMore: false,
      materialLoading: false,
      batchPage: 1,
      batchHasMore: false,
      batchLoading: false
    }
  },
  computed: {
    materialReturnContext() {
      if (this.leaveContext.bizType) return this.leaveContext
      const row = this.materials.find(item => String(item.requirementId) === this.focusMaterialId)
      return row && ['PROFILE', 'LEAVE', 'AID', 'FUNDING'].includes(row.bizType) && /^\d+$/.test(String(row.bizId || '')) ? { bizType: row.bizType, bizId: String(row.bizId) } : {}
    },
    todoItems() { return (this.data && Array.isArray(this.data.items)) ? this.data.items : [] },
    prioritySummary() {
      return (this.data && this.data.prioritySummary) || { overdue: 0, dueWithin24h: 0, ordinary: 0 }
    }
  },
  onLoad(query) {
    this.leaveContext = query && ['PROFILE', 'LEAVE', 'AID', 'FUNDING'].includes(query.bizType) && /^\d+$/.test(String(query.bizId || '')) ? { bizType: query.bizType, bizId: query.bizId } : {}
    this.focusMaterialId = String((query && (query.materialRequirementId || query.recordId)) || '')
    this.load()
  },
  onShow() { if (this.state === 'ready') this.load() },
  methods: {
    batchItemStatusLabel(value) { return ({ PENDING: '待处理', RUNNING: '处理中', SUCCEEDED: '处理成功', SUCCESS: '处理成功', FAILED: '处理失败', RETRY: '等待重试', RETRYING: '正在重试', DEAD: '重试失败', SKIPPED: '已跳过', CANCELLED: '已取消' }[value] || (value ? `状态待确认（${value}）` : '状态未知')) },
    returnToApplication() { const context = this.materialReturnContext || this.leaveContext; if (!context.bizType) return; if (context.bizType === 'PROFILE') return uni.navigateTo({ url: '/pages/teacher/student-detail/index?id=' + encodeURIComponent(context.bizId) }); uni.navigateTo({ url: context.bizType === 'FUNDING' ? '/pages/teacher/affairs-review/index?type=FUNDING_APPROVAL&recordId=' + encodeURIComponent(context.bizId) : context.bizType === 'AID' ? '/pages/teacher/affairs-review/index?type=AID_APPROVAL&recordId=' + encodeURIComponent(context.bizId) : '/pages/teacher/affairs-leave/index?recordId=' + encodeURIComponent(context.bizId) }) },
    formatTime(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '' },
    priorityClass(item) {
      return { 'is-overdue': !!item.overdue, 'is-near': !item.overdue && !!item.dueWithin24h }
    },
    bizLabel(value) { return ({ PROFILE: '学生个人档案', LEAVE: '请假', AID: '困难认定', FUNDING: '奖助申请', DISCIPLINE: '违纪处分', DISCIPLINE_APPEAL: '处分申诉', DORM_TRANSFER: '调宿申请', CREDIT_APPEAL: '第二课堂申诉' }[value] || '学工申请') },
    // 老师在手机上尤其不该靠主键认学生。后端下发 businessContext 时显示
    // 姓名/学号/班级与业务标题，未下发时退回原有 ID 文案，不留空白。
    materialStudentLine(item) {
      const c = (item && item.businessContext) || {}
      const parts = [c.studentName, c.studentNo, c.className].filter(Boolean)
      return parts.length ? parts.join(' · ') : `学生 #${item.studentId}`
    },
    materialBizLine(item) {
      const c = (item && item.businessContext) || {}
      const parts = [c.bizPeriod, c.bizDisplayTitle || this.bizLabel(item.bizType), c.bizDisplaySubtitle].filter(Boolean)
      return parts.length ? parts.join(' · ') : `${this.bizLabel(item.bizType)} #${item.bizId}`
    },
    allows(item, action) { return (item.allowedActions || []).includes(action) },
    canRemind(item) { return ['MISSING', 'RETURNED'].includes(item.status) && item.version !== undefined && item.version !== null },
    load() {
      this.state = 'loading'; this.todoPage = 1
      const task = Promise.all([
        teacherApi.getAffairs(1, 20),
        this.loadMaterials(false, true),
        this.loadBatches(false, true)
      ]).then(([d]) => {
        this.data = d
        this.todoHasMore = Boolean(d && d.hasMore)
        this.state = 'ready'
        this.scrollToMaterial()
      }).catch((e) => { this.state = 'error'; toast(normalizeError(e).text || '学工待办加载失败') })
      return task
    },
    loadMaterials(showToast = true, reset = true) {
      this.materialError = ''
      if (reset) this.materialPage = 1
      return affairsContractApi.getMaterialRequirements('', this.materialPage, 20, { ...this.leaveContext, requirementId: this.focusMaterialId || undefined }).then((d) => {
        const rows = (d && d.items) || []
        this.materials = reset ? rows : [...this.materials, ...rows]
        this.materialHasMore = this.materialPage * 20 < Number((d && d.total) || 0)
        const visible = new Set(this.materials.map((x) => String(x.requirementId)))
        this.selectedMaterialIds = this.selectedMaterialIds.filter((id) => visible.has(String(id)))
        this.scrollToMaterial()
        return this.materials
      }).catch((e) => {
        const n = normalizeError(e)
        if (n.kind === 'forbidden') { this.materials = []; return [] }
        this.materialError = n.text || '材料队列加载失败'
        if (showToast) toast(this.materialError)
        return null
      })
    },
    loadBatches(showToast = true, reset = true) {
      if (reset) this.batchPage = 1
      return affairsContractApi.getMaterialBatchJobs(this.batchPage, 20).then((d) => {
        const rows = (d && d.items) || []
        this.batchJobs = reset ? rows : [...this.batchJobs, ...rows]
        this.batchHasMore = this.batchPage * 20 < Number((d && d.total) || 0)
        return this.batchJobs
      }).catch((e) => { if (showToast && normalizeError(e).kind !== 'forbidden') toast(normalizeError(e).text || '批次列表加载失败'); if (reset) this.batchJobs = []; return null })
    },
    loadMoreTodos() {
      if (this.todoLoading || !this.todoHasMore) return
      this.todoLoading = true
      const next = this.todoPage + 1
      teacherApi.getAffairs(next, 20).then((d) => {
        this.todoPage = next
        this.data = { ...this.data, ...d, items: [...this.todoItems, ...((d && d.items) || [])] }
        this.todoHasMore = Boolean(d && d.hasMore)
      }).catch((e) => toast(normalizeError(e).text || '待办加载失败')).finally(() => { this.todoLoading = false })
    },
    loadMoreMaterials() {
      if (this.materialLoading || !this.materialHasMore) return
      const previous = this.materialPage
      this.materialLoading = true; this.materialPage = previous + 1
      this.loadMaterials(true, false).then((result) => { if (result === null) this.materialPage = previous })
        .finally(() => { this.materialLoading = false })
    },
    loadMoreBatches() {
      if (this.batchLoading || !this.batchHasMore) return
      const previous = this.batchPage
      this.batchLoading = true; this.batchPage = previous + 1
      this.loadBatches(true, false).then((result) => { if (result === null) this.batchPage = previous })
        .finally(() => { this.batchLoading = false })
    },
    scrollToMaterial() {
      if (!this.focusMaterialId && !this.leaveContext.bizId) return
      this.$nextTick(() => setTimeout(() => {
        try { uni.pageScrollTo({ selector: this.focusMaterialId ? '#teacher-material-' + this.focusMaterialId : '#leave-material-section', duration: 250 }) } catch (e) {}
      }, 80))
    },
    routeFor(todoType, params = {}) {
      const base = ROUTES[todoType]
      if (!base) return ''
      const query = []
      if (params.recordId) query.push(`recordId=${encodeURIComponent(params.recordId)}`)
      if (params.todoId) query.push(`todoId=${encodeURIComponent(params.todoId)}`)
      if (!query.length) return base
      return base + (base.includes('?') ? '&' : '?') + query.join('&')
    },
    openTodo(item) {
      const params = {
        ...(item.actionParams || {}),
        recordId: item.recordId || (item.actionParams && item.actionParams.recordId) || '',
        todoId: item.todoId || (item.actionParams && item.actionParams.todoId) || ''
      }
      if (item.todoType === 'MATERIAL_REVIEW') {
        this.focusMaterialId = String(params.recordId || '')
        this.scrollToMaterial()
        return
      }
      const url = this.routeFor(item.todoType, params)
      if (!url) { toast('该待办类型尚未配置移动端处理入口'); return }
      uni.navigateTo({ url })
    },
    openCard(c) {
      if (c.todoType === 'MATERIAL_REVIEW') { this.scrollToMaterial(); return }
      const url = this.routeFor(c.todoType)
      if (!url) { toast('该待办类型尚未配置移动端处理入口'); return }
      uni.navigateTo({ url })
    },
    toggleMaterial(item) {
      const id = String(item.requirementId)
      this.selectedMaterialIds = this.selectedMaterialIds.includes(id)
        ? this.selectedMaterialIds.filter((x) => x !== id)
        : [...this.selectedMaterialIds, id]
    },
    startReturn(item) { this.returningId = item.requirementId; this.returnReason = '' },
    cancelReturn() { this.returningId = ''; this.returnReason = '' },
    reviewMaterial(item, action) {
      if (this.materialBusy) return
      const reason = action === 'RETURN' ? this.returnReason : ''
      if (action === 'RETURN' && reason.trim().length < 5) { toast('退回原因至少5字'); return }
      const run = () => {
        this.materialBusy = item.requirementId
        affairsContractApi.reviewMaterialRequirement(item.requirementId, action, reason, item.version)
          .then(() => { toast(action === 'ACCEPT' ? '材料已验收' : (action === 'RETURN' ? '已退回学生重补' : '材料已免交')); this.cancelReturn(); return this.load() })
          .catch((e) => toast(normalizeError(e).text || '材料审核失败'))
          .finally(() => { this.materialBusy = '' })
      }
      if (action === 'RETURN') { run(); return }
      uni.showModal({
        title: action === 'ACCEPT' ? '确认验收' : '确认免交',
        content: action === 'ACCEPT' ? `确认验收“${item.itemName}”当前版本？` : `确认将“${item.itemName}”标记为免交？`,
        success: (res) => { if (res.confirm) run() }
      })
    },
    createReminderBatch() {
      if (this.batchBusy || !this.selectedMaterialIds.length) return
      const rows = this.materials.filter((x) => this.selectedMaterialIds.includes(String(x.requirementId)) && this.canRemind(x))
      if (!rows.length) { toast('已选材料状态已变化，请刷新'); return }
      uni.showModal({
        title: '批量提醒',
        content: `确认提醒 ${rows.length} 项材料？系统会逐条校验权限、范围、状态和版本。`,
        success: (res) => {
          if (!res.confirm) return
          this.batchBusy = true
          affairsContractApi.createMaterialReminderBatch(
            rows.map((x) => ({ requirementId: Number(x.requirementId), version: Number(x.version) })),
            `material-remind:${Date.now()}`
          ).then((result) => {
            toast(`完成：成功${result.successCount}，失败${result.failureCount}`)
            this.activeBatch = result
            this.selectedMaterialIds = []
            return this.loadBatches(false)
          }).catch((e) => toast(normalizeError(e).text || '批量提醒失败'))
            .finally(() => { this.batchBusy = false })
        }
      })
    },
    openBatch(job) {
      affairsContractApi.getMaterialBatchJob(job.batchJobId).then((d) => { this.activeBatch = d })
        .catch((e) => toast(normalizeError(e).text || '批次详情加载失败'))
    },
    retryBatch(job) {
      if (this.batchBusy) return
      this.batchBusy = true
      affairsContractApi.retryMaterialBatchFailed(job.batchJobId).then((d) => {
        this.activeBatch = d
        toast(`重试完成：成功${d.successCount}，失败${d.failureCount}`)
        return this.loadBatches(false)
      }).catch((e) => toast(normalizeError(e).text || '失败项重试失败'))
        .finally(() => { this.batchBusy = false })
    },
    downloadMaterial(version) {
      affairsContractApi.downloadMaterialFile(version.fileId).then((d) => {
        const path = d && d.tempFilePath
        if (!path) throw new Error('下载文件路径为空')
        uni.openDocument({
          filePath: path,
          showMenu: true,
          fail: () => uni.saveFile({ tempFilePath: path, success: () => toast('文件已保存'), fail: () => toast('文件暂无法打开') })
        })
      }).catch((e) => toast(normalizeError(e).text || '材料下载失败'))
    }
  }
}
</script>

<style scoped>
.ta__work-study { display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:var(--space-4); padding:14px; border:1px solid rgba(37,99,235,.18); border-radius:14px; background:rgba(37,99,235,.06); }
.ta__total { background: linear-gradient(135deg, #174a78, var(--brand-primary) 58%, #2f8ea3); color: #fff; border-radius: 20px; padding: 18px; margin-bottom: var(--space-4); display: flex; align-items: center; justify-content: space-between; gap: 14px; box-shadow: 0 18px 38px -25px rgba(15,59,95,.72); }
.ta__eyebrow { display: block; margin-bottom: 5px; font-size: 11px; font-weight: 700; letter-spacing: 2px; opacity: .82; }
.ta__total-n { font-size: 28px; font-weight: 700; }
.ta__total-l { margin-left: 6px; font-size: 12px; opacity: .84; }
.ta__priority-stats { display: flex; gap: 6px; }
.ta__priority-stat { min-width: 44px; padding: 7px 6px; border: 1px solid rgba(255,255,255,.16); border-radius: 11px; background: rgba(255,255,255,.1); text-align: center; }
.ta__priority-stat text { display: block; font-size: 10px; opacity: .82; }
.ta__priority-stat text:first-child { margin-bottom: 2px; font-size: 17px; font-weight: 750; opacity: 1; }
.ta__priority-stat.is-overdue { background: rgba(190,24,24,.28); }
.ta__priority-stat.is-near { background: rgba(217,119,6,.3); }
.ta__empty { text-align: center; color: var(--text-tertiary); padding: var(--space-5); }
.ta__card,.ta__todo { display: flex; justify-content: space-between; align-items: center; background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-4); box-shadow: var(--shadow-card); }
.ta__todo { align-items: flex-start; gap: 12px; }
.ta__todo.is-overdue { border-left: 4px solid var(--danger-500, #dc2626); background: linear-gradient(90deg, var(--danger-50, #fef2f2), #fff 34%); }
.ta__todo.is-near { border-left: 4px solid var(--warning-500, #f59e0b); background: linear-gradient(90deg, #fff8eb, #fff 34%); }
.ta__todo-head { display: flex; align-items: flex-start; gap: 8px; }
.ta__overdue { font-size: 11px; color: var(--danger-600); background: var(--danger-50, #fef2f2); padding: 2px 6px; border-radius: 6px; }
.ta__near { font-size: 11px; color: #a15c00; background: #fff2d6; padding: 2px 6px; border-radius: 6px; }
.ta__title { display: block; margin-top: 5px; color: var(--text-primary); font-size: 14px; line-height: 1.5; }
.ta__label { display: block; font-weight: 600; color: var(--text-primary); }
.ta__sub,.ta__due { display: block; margin-top: 4px; font-size: 12px; color: var(--text-tertiary); }
.ta__due { color: var(--warning-700); }
.ta__due.is-danger,.ta__error { color: var(--danger-600); }
.ta__right { display: flex; align-items: center; gap: 8px; }
.ta__count { font-size: 20px; font-weight: 700; color: var(--brand-primary); }
.ta__go { color: var(--text-tertiary); font-size: 20px; }
.ta__section { margin-top: 22px; }
.ta__refresh,.ta__link { color: var(--brand-primary); font-size: 12px; }
.ta__material.is-focus { border: 2px solid var(--brand-primary); }
.ta__submission { display: flex; align-items: center; gap: 10px; margin-top: 12px; padding: 10px; background: var(--bg-page); border-radius: 8px; }
.ta__actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
.ta__small { min-width: 64px; padding: 0 10px; font-size: 12px; }
.ta__check { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-secondary); }
.ta__box { width: 18px; height: 18px; border: 1px solid var(--border-default); border-radius: 4px; text-align: center; line-height: 18px; }
.ta__box.checked { background: var(--brand-primary); border-color: var(--brand-primary); color: #fff; }
.ta__return-box { margin-top: 10px; padding: 10px; background: var(--bg-page); border-radius: 8px; }
.ta__return-box textarea { width: 100%; min-height: 72px; padding: 8px; box-sizing: border-box; background: #fff; border-radius: 7px; }
.ta__return-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }
.ta__load-more { width: 100%; margin-top: 12px; }
.ta__batch-btn { position: sticky; bottom: 12px; z-index: 20; width: 100%; margin-top: 12px; }
.ta__batch-detail { margin-top: 12px; }
.ta__batch-item { display: flex; padding: 10px 0; border-top: 1px solid var(--border-light); }
.ta__error { display: block; margin-top: 4px; font-size: 12px; }
</style>
