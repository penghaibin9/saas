<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="学工待办" subtitle="逐条待办、权限、数据范围与 PC 同源" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="data">
        <view class="ta__total">
          <text class="ta__total-n">{{ data.total }}</text>
          <text class="ta__total-l">项学工待办</text>
        </view>

        <view class="section-head"><text class="section-head__title">待我处理</text></view>
        <view class="ta__empty" v-if="!todoItems.length"><text>暂无待办</text></view>
        <view class="stack" v-else>
          <view v-for="item in todoItems" :key="item.todoId" class="ta__todo" @click="openTodo(item)">
            <view class="flex-1">
              <view class="ta__todo-head">
                <text class="ta__label">{{ item.label || item.todoType }}</text>
                <text v-if="item.overdue" class="ta__overdue">已逾期</text>
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

        <view class="section-head ta__section">
          <text class="section-head__title">材料补交审核</text>
          <text class="ta__refresh" @click="loadMaterials">刷新</text>
        </view>
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
                <text class="ta__sub">{{ bizLabel(item.bizType) }} #{{ item.bizId }} · 学生 #{{ item.studentId }}</text>
              </view>
              <MobileStatusTag :status="item.status" :label="item.statusLabel || item.status" />
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
        <button v-if="selectedMaterialIds.length" class="btn btn-primary ta__batch-btn" :disabled="batchBusy" @click="createReminderBatch">
          {{ batchBusy ? '逐条校验中…' : `批量提醒已选 ${selectedMaterialIds.length} 项` }}
        </button>

        <view class="section-head ta__section"><text class="section-head__title">安全批次结果</text></view>
        <MobileInlineAlert type="info" title="仅开放低风险材料提醒" description="审批、发放、处分和风险关闭必须继续逐条办理。" />
        <view v-if="!batchJobs.length" class="ta__empty card"><text>暂无批次记录</text></view>
        <view v-else class="stack">
          <view v-for="job in batchJobs" :key="job.batchJobId" class="ta__card" @click="openBatch(job)">
            <view class="flex-1"><text class="ta__label">{{ job.batchNo }}</text><text class="ta__sub">{{ job.statusLabel || job.status }} · 成功 {{ job.successCount }} / 失败 {{ job.failureCount }}</text></view>
            <button v-if="(job.allowedActions || []).includes('RETRY_FAILED')" class="btn btn-secondary ta__small" :disabled="batchBusy" @click.stop="retryBatch(job)">重试失败项</button>
            <text v-else class="ta__go">›</text>
          </view>
        </view>
        <view v-if="activeBatch" class="card ta__batch-detail">
          <text class="ta__label">{{ activeBatch.batchNo }} · {{ activeBatch.statusLabel || activeBatch.status }}</text>
          <view v-for="detail in (activeBatch.items || [])" :key="detail.itemId" class="ta__batch-item">
            <view class="flex-1"><text class="ta__title">{{ detail.itemKey }}</text><text class="ta__sub">{{ detail.status }} · 尝试 {{ detail.attemptCount }} 次</text><text v-if="detail.errorMessage" class="ta__error">{{ detail.errorMessage }}</text></view>
          </view>
        </view>

        <view class="section-head ta__section"><text class="section-head__title">按业务分类</text></view>
        <view class="stack">
          <view v-for="c in data.cards" :key="c.todoType" class="ta__card" @click="openCard(c)">
            <text class="ta__label">{{ c.label }}</text>
            <view class="ta__right"><text class="ta__count">{{ c.count }}</text><text class="ta__go">›</text></view>
          </view>
        </view>

        <template v-if="activityVisible">
          <view class="section-head ta__section"><text class="section-head__title">现场活动签到</text></view>
          <MobileInlineAlert v-if="activityError" type="warning" title="活动签到暂不可用" :description="activityError" />
          <MobileGlobalState v-else-if="!activities.length" state="empty" title="暂无进行中活动" description="活动开始后可在此生成5分钟动态签到码。" />
          <view v-else class="stack">
            <view v-for="a in activities" :key="a.activityId" class="ta__card ta__activity">
              <view class="flex-1">
                <text class="ta__label">{{ a.activityName }}</text>
                <text class="ta__sub">{{ a.location || '未填写地点' }} · 已报名 {{ a.signupCount || 0 }} 人</text>
              </view>
              <button class="btn btn-primary ta__code-btn" :disabled="codeLoading === a.activityId" @click="showCode(a)">
                {{ codeLoading === a.activityId ? '生成中…' : '生成签到码' }}
              </button>
            </view>
          </view>
        </template>
      </view>
    </MobileGlobalState>

    <view v-if="codeData" class="ta__mask" @click.self="codeData = null">
      <view class="card ta__code-card">
        <text class="card-title">{{ codeData.activityName }}</text>
        <text class="ta__code">{{ codeData.checkinCode }}</text>
        <text class="ta__code-tip">请学生在活动页输入此码。动态码最多5分钟有效，过期后重新生成。</text>
        <button class="btn btn-primary" @click="codeData = null">完成</button>
      </view>
    </view>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { affairsContractApi } from '@/services/affairsContractApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const ROUTES = {
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
      activities: [],
      activityVisible: true,
      activityError: '',
      codeData: null,
      codeLoading: '',
      materials: [],
      materialError: '',
      materialBusy: '',
      selectedMaterialIds: [],
      returningId: '',
      returnReason: '',
      batchJobs: [],
      activeBatch: null,
      batchBusy: false,
      focusMaterialId: ''
    }
  },
  computed: { todoItems() { return (this.data && Array.isArray(this.data.items)) ? this.data.items : [] } },
  onLoad(query) {
    this.focusMaterialId = String((query && (query.materialRequirementId || query.recordId)) || '')
    this.load()
  },
  onShow() { if (this.state === 'ready') this.load() },
  methods: {
    formatTime(value) { return value ? String(value).replace('T', ' ').slice(0, 16) : '' },
    bizLabel(value) { return ({ LEAVE: '请假', AID: '困难认定', FUNDING: '奖助申请', DISCIPLINE: '违纪处分', DISCIPLINE_APPEAL: '处分申诉', DORM_TRANSFER: '调宿申请', CREDIT_APPEAL: '第二课堂申诉' }[value] || value) },
    allows(item, action) { return (item.allowedActions || []).includes(action) },
    canRemind(item) { return ['MISSING', 'RETURNED'].includes(item.status) && item.version !== undefined && item.version !== null },
    load() {
      this.state = 'loading'; this.activityError = ''
      Promise.all([
        teacherApi.getAffairs(),
        this.loadMaterials(false),
        this.loadBatches(false)
      ]).then(([d]) => {
        this.data = d
        this.state = 'ready'
        this.scrollToMaterial()
      }).catch((e) => { this.state = 'error'; toast(normalizeError(e).text || '学工待办加载失败') })
      affairsContractApi.getOngoingActivities().then((d) => { this.activities = (d && d.items) || []; this.activityVisible = true })
        .catch((e) => {
          const n = normalizeError(e)
          if (n.kind === 'forbidden') { this.activityVisible = false; this.activities = [] }
          else { this.activityVisible = true; this.activityError = n.text || '活动数据加载失败，请稍后重试' }
        })
    },
    loadMaterials(showToast = true) {
      this.materialError = ''
      return affairsContractApi.getMaterialRequirements().then((d) => {
        this.materials = (d && d.items) || []
        const visible = new Set(this.materials.map((x) => String(x.requirementId)))
        this.selectedMaterialIds = this.selectedMaterialIds.filter((id) => visible.has(String(id)))
        this.scrollToMaterial()
        return this.materials
      }).catch((e) => {
        const n = normalizeError(e)
        if (n.kind === 'forbidden') { this.materials = []; return [] }
        this.materialError = n.text || '材料队列加载失败'
        if (showToast) toast(this.materialError)
        return []
      })
    },
    loadBatches(showToast = true) {
      return affairsContractApi.getMaterialBatchJobs().then((d) => { this.batchJobs = (d && d.items) || []; return this.batchJobs })
        .catch((e) => { if (showToast && normalizeError(e).kind !== 'forbidden') toast(normalizeError(e).text || '批次列表加载失败'); this.batchJobs = []; return [] })
    },
    scrollToMaterial() {
      if (!this.focusMaterialId) return
      this.$nextTick(() => setTimeout(() => {
        try { uni.pageScrollTo({ selector: '#teacher-material-' + this.focusMaterialId, duration: 250 }) } catch (e) {}
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
          .then(() => { toast(action === 'ACCEPT' ? '材料已验收' : (action === 'RETURN' ? '已退回学生重补' : '材料已免交')); this.cancelReturn(); return this.loadMaterials(false) })
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
    },
    showCode(a) {
      if (this.codeLoading) return
      this.codeLoading = a.activityId
      affairsContractApi.getActivityCheckinToken(a.activityId).then((d) => { this.codeData = d })
        .catch((e) => toast(normalizeError(e).text || '签到码生成失败'))
        .finally(() => { this.codeLoading = '' })
    }
  }
}
</script>

<style scoped>
.ta__total { background: var(--brand-primary); color: #fff; border-radius: var(--radius-lg); padding: var(--space-4); margin-bottom: var(--space-4); display: flex; align-items: baseline; gap: var(--space-2); }
.ta__total-n { font-size: 28px; font-weight: 700; }
.ta__empty { text-align: center; color: var(--text-tertiary); padding: var(--space-5); }
.ta__card,.ta__todo { display: flex; justify-content: space-between; align-items: center; background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-4); box-shadow: var(--shadow-card); }
.ta__todo { align-items: flex-start; gap: 12px; }
.ta__todo-head { display: flex; align-items: flex-start; gap: 8px; }
.ta__overdue { font-size: 11px; color: var(--danger-600); background: var(--danger-50, #fef2f2); padding: 2px 6px; border-radius: 6px; }
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
.ta__batch-btn { position: sticky; bottom: 12px; z-index: 20; width: 100%; margin-top: 12px; }
.ta__batch-detail { margin-top: 12px; }
.ta__batch-item { display: flex; padding: 10px 0; border-top: 1px solid var(--border-light); }
.ta__error { display: block; margin-top: 4px; font-size: 12px; }
.ta__activity { gap: 10px; }
.ta__code-btn { flex-shrink: 0; font-size: 12px; padding: 0 10px; }
.ta__mask { position: fixed; inset: 0; z-index: 1000; background: rgba(15,23,42,.5); display: flex; align-items: center; justify-content: center; padding: 24px; }
.ta__code-card { width: 100%; text-align: center; padding: 24px; }
.ta__code { display: block; font-size: 44px; letter-spacing: 10px; font-weight: 800; color: var(--brand-primary); margin: 22px 0 12px; }
.ta__code-tip { display: block; font-size: 13px; color: var(--text-secondary); line-height: 1.6; margin-bottom: 18px; }
</style>
