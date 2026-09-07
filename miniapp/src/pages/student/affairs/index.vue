<template>
  <view class="page-wrap">
    <MobilePrivacyGate />
    <view class="af__hero hero-band is-brand">
      <view class="hero-band__orb" />
      <view class="mnav__status" :style="{ height: statusBarHeight + 'px' }" />
      <view class="af__navbar"><text class="af__navbar-back" @click="back">‹</text><text class="af__navbar-title">{{ materialReturnContext.bizType ? '材料补交' : '学工中心' }}</text></view>
      <view class="stat-strip" v-if="data && !materialReturnContext.bizType">
        <view class="stat-strip__item"><text class="stat-strip__val">{{ data.leaveCount }}</text><text class="stat-strip__label">请假</text></view>
        <view class="stat-strip__item"><text class="stat-strip__val">{{ data.aidApproved }}</text><text class="stat-strip__label">困难认定</text></view>
        <view class="stat-strip__item"><text class="stat-strip__val">{{ data.fundingGranted }}</text><text class="stat-strip__label">获资助</text></view>
        <view class="stat-strip__item"><text class="stat-strip__val">{{ openMaterials.length }}</text><text class="stat-strip__label">待补材料</text></view>
      </view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="data" style="padding-top: var(--space-3);">
        <view v-if="!materialReturnContext.bizType" class="card">
          <view class="icon-grid">
            <view v-for="(it, i) in entries" :key="it.key" class="icon-grid__item" @click="go(it.route)">
              <view class="icon-grid__badge" :class="gradClass(i)">{{ it.icon }}</view>
              <text class="icon-grid__label">{{ it.label }}</text>
            </view>
          </view>
          <view class="af__work-study" @click="go('/pages/student/affairs/work-study')">
            <view><text class="card-title">勤工助学</text><text class="t-xs t-tertiary">查开放岗位、提交申请、看上岗进度与月度补贴</text></view>
            <text class="link">进入</text>
          </view>
          <view class="af__work-study" @click="go('/pages/student/affairs/loan')">
            <view><text class="card-title">助学贷款</text><text class="t-xs t-tertiary">提交电子回执、查看核验进度</text></view>
            <text class="link">进入</text>
          </view>
          <view class="af__work-study" @click="go('/pages/student/affairs/reduction')">
            <view><text class="card-title">减免与临时补助</text><text class="t-xs t-tertiary">申请、补正与结果查询</text></view>
            <text class="link">进入</text>
          </view>
        </view>

        <view id="affairs-material-section" class="section-head"><text class="section-head__title">材料补交</text><text class="af__refresh" @click="loadMaterials">刷新</text></view>
        <view v-if="materialReturnContext.bizType" class="card af__context"><text>仅显示{{ bizLabel(materialReturnContext.bizType) }}材料</text><button class="btn" @click="returnToApplication">{{ materialReturnContext.bizType === 'PROFILE' ? '返回学生档案' : '返回原申请' }}</button></view>
        <MobileInlineAlert v-if="materialError" type="warning" title="材料列表暂不可用" :description="materialError" />
        <view v-else-if="!materials.length" class="card af__empty"><text>暂无材料缺项</text></view>
        <view v-else class="stack">
          <view
            v-for="item in materials"
            :key="item.requirementId"
            :id="'material-' + item.requirementId"
            class="card af__material"
            :class="{ 'is-focus': String(item.requirementId) === focusMaterialId }"
          >
            <view class="row-between af__mat-head">
              <view class="flex-1">
                <text class="card-title">{{ item.itemName }}</text>
                <text class="t-xs t-tertiary">{{ bizLine(item) }} · 第{{ item.returnRound || 1 }}轮</text>
              </view>
              <MobileStatusTag :status="item.status" :label="item.statusLabel || '状态待确认'" />
            </view>
            <text v-if="item.requirementReason" class="af__reason">缺项说明：{{ item.requirementReason }}</text>
            <text v-if="item.dueAt" class="af__due" :class="{ overdue: item.overdue }">截止 {{ formatTime(item.dueAt) }}{{ item.overdue ? '（已逾期）' : '' }}</text>
            <text class="t-xs t-tertiary">审核责任人：{{ item.reviewOwner || '待分配' }}</text>

            <view v-if="canSubmitMaterial(item)" class="af__submit">
              <button class="btn btn-secondary" :disabled="!!materialBusy" @click="chooseMaterial(item)">
                {{ selectedFiles[item.requirementId] ? selectedFiles[item.requirementId].name : '选择补交文件' }}
              </button>
              <input v-model.trim="materialNotes[item.requirementId]" :disabled="!!materialBusy" class="input" maxlength="500" placeholder="补充说明（选填）" />
              <button class="btn btn-primary" :disabled="!!materialBusy || !selectedFiles[item.requirementId]" @click="submitMaterial(item)">
                {{ materialBusy === item.requirementId ? '处理中…' : uploadedMaterials[item.requirementId] ? '检查并提交审核' : '上传并提交审核' }}
              </button>
            </view>
            <view v-else-if="item.status === 'PENDING_REVIEW'" class="af__pending"><text>最新版本已提交，等待老师审核。</text></view>
            <view v-if="uploadedMaterials[item.requirementId] && canSubmitMaterial(item)" class="af__pending"><text>{{ materialFileHint(uploadedMaterials[item.requirementId]) }}</text></view>
            <view v-if="materialNotices[item.requirementId]" class="af__pending"><text>{{ materialNotices[item.requirementId] }}</text></view>

            <view class="af__versions" v-if="(item.versions || []).length">
              <text class="af__versions-title">版本记录（{{ item.versionCount || item.versions.length }}）</text>
              <view v-for="version in item.versions" :key="version.submissionId" class="af__version row-between">
                <view class="flex-1">
                  <text class="t-sm t-primary">V{{ version.versionNo }} · {{ version.fileName }}</text>
                  <text class="t-xs t-tertiary">{{ version.statusLabel || '状态待确认' }} · {{ formatTime(version.submittedAt) }}</text>
                  <text v-if="version.reviewNote" class="af__review">审核意见：{{ version.reviewNote }}</text>
                </view>
                <view class="af__version-actions">
                  <text v-if="version.current" class="af__current">当前</text>
                  <text v-if="version.downloadable" class="af__link" @click="downloadMaterial(version)">查看</text>
                </view>
              </view>
            </view>
          </view>
          <button v-if="!focusMaterialId && materials.length < materialTotal" class="btn btn-secondary af__more" :disabled="materialLoadingMore" @click="loadMoreMaterials">
            {{ materialLoadingMore ? '加载中…' : '加载更多（' + materials.length + '/' + materialTotal + '）' }}
          </button>
        </view>

        <view v-if="!materialReturnContext.bizType" class="section-head"><text class="section-head__title">我的处分</text></view>
        <view v-if="!materialReturnContext.bizType" class="card" @click="go('/pages/student/affairs/discipline')">
          <text class="t-sm t-secondary">{{ discNote }}</text>
          <text class="t-sm link">进入申诉 ›</text>
        </view>
      </view>
    </MobileGlobalState>
    <MobileTabBar side="student" active="" :before-navigate="mayLeaveMaterials" />
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import fileSdk from '@/services/fileSdk'
import { affairsContractApi } from '@/services/affairsContractApi'
import { normalizeError } from '@/services/request'
import { go, toast } from '@/utils/nav'
import { getStatusBarHeight } from '@/utils/deviceInfo'

const GRAD_CLASSES = ['g1', 'g4', 'g3', 'g5', 'g2', 'g7']
const ENTRIES = [
  { key: 'leave', label: '我的请假', icon: '📝', route: '/pages/student/affairs/leave' },
  { key: 'dorm', label: '我的宿舍', icon: '🏠', route: '/pages/student/affairs/dorm' },
  { key: 'aid', label: '困难认定', icon: '🤝', route: '/pages/student/affairs/aid' },
  { key: 'funding', label: '奖助申请', icon: '💰', route: '/pages/student/affairs/funding' },
  { key: 'discipline', label: '违纪申诉', icon: '⚖️', route: '/pages/student/affairs/discipline' },
  { key: 'talk', label: '谈心谈话', icon: '💬', route: '/pages/student/affairs/talk' },
  { key: 'activity', label: '活动与二课', icon: '🎉', route: '/pages/student/affairs/activity' },
  { key: 'service', label: '在校服务', icon: '🏫', route: '/pages/student/campus-service/index' }
]

export default {
  data() {
    return {
      data: null,
      disc: null,
      state: 'loading',
      statusBarHeight: 20,
      entries: ENTRIES,
      materials: [],
      materialError: '',
      materialBusy: '',
      pageVisible: false,
      selectedFiles: {},
      uploadedMaterials: {}, materialNotices: {},
      materialNotes: {},
      leaveContext: {}, focusMaterialId: '',
      materialPage: 1,
      materialPageSize: 20,
      materialTotal: 0,
      materialLoadingMore: false
    }
  },
  onLoad(query) {
    this.leaveContext = query && ['PROFILE', 'LEAVE', 'AID', 'FUNDING'].includes(query.bizType) && /^\d+$/.test(String(query.bizId || '')) ? { bizType: query.bizType, bizId: query.bizId } : {}
    this.statusBarHeight = getStatusBarHeight()
    this.focusMaterialId = String((query && (query.materialRequirementId || query.requirementId)) || '')
    this.load()
    // #ifdef H5
    this._beforeUnload = (event) => {
      if (!this.materialBusy && !this.hasMaterialDraft()) return
      event.preventDefault(); event.returnValue = ''
    }
    window.addEventListener('beforeunload', this._beforeUnload)
    // #endif
  },
  onShow() { this.pageVisible = true; this.syncMaterialLeaveAlert() },
  onHide() { this.pageVisible = false; this.syncMaterialLeaveAlert() },
  onUnload() {
    this.pageVisible = false; this.syncMaterialLeaveAlert()
    // #ifdef H5
    window.removeEventListener('beforeunload', this._beforeUnload)
    // #endif
  },
  onBackPress() {
    if (this._allowMaterialBack || (!this.materialBusy && !this.hasMaterialDraft())) return false
    this.back()
    return true
  },
  watch: {
    materialGuardActive() { this.syncMaterialLeaveAlert() }
  },
  computed: {
    materialReturnContext() {
      if (this.leaveContext.bizType) return this.leaveContext
      const row = this.materials.find(item => String(item.requirementId) === this.focusMaterialId)
      return row && ['PROFILE', 'LEAVE', 'AID', 'FUNDING'].includes(row.bizType) && /^\d+$/.test(String(row.bizId || '')) ? { bizType: row.bizType, bizId: String(row.bizId) } : {}
    },
    materialGuardActive() { return !!this.materialBusy || this.hasMaterialDraft() },
    discNote() {
      if (!this.disc) return '生效中处分数量'
      return this.disc.activeCount > 0 ? `生效中 ${this.disc.activeCount} 条（${this.disc.detailNote || '明细请联系辅导员'}）` : '暂无生效处分'
    },
    openMaterials() { return this.materials.filter((x) => ['MISSING', 'RETURNED', 'PENDING_REVIEW'].includes(x.status)) }
  },
  methods: {
    hasMaterialDraft() { return Object.values(this.selectedFiles).some(Boolean) || Object.values(this.materialNotes).some(note => String(note || '').trim()) },
    syncMaterialLeaveAlert() {
      // #ifdef MP-WEIXIN
      if (typeof uni.enableAlertBeforeUnload !== 'function') return
      if (this.pageVisible && (this.materialBusy || this.hasMaterialDraft())) {
        uni.enableAlertBeforeUnload({ message: this.materialBusy ? '材料正在提交，请稍候再离开。' : '材料尚未提交，离开后需要重新选择文件。' })
      } else if (typeof uni.disableAlertBeforeUnload === 'function') uni.disableAlertBeforeUnload()
      // #endif
    },
    async mayLeaveMaterials() {
      if (this.materialBusy) { toast('材料正在提交，请稍候再离开'); return false }
      if (!this.hasMaterialDraft()) return true
      if (this._materialLeavePrompt) return false
      this._materialLeavePrompt = true
      try {
        const allowed = await new Promise(resolve => uni.showModal({
          title: '材料尚未提交', content: '离开将放弃本页选择的文件和补充说明。已提交的材料不受影响。',
          cancelText: '继续填写', confirmText: '放弃离开',
          success: result => resolve(!!result.confirm), fail: () => resolve(false)
        }))
        if (!allowed || this.materialBusy) return false
        this.selectedFiles = {}; this.materialNotes = {}; this.uploadedMaterials = {}; this.materialNotices = {}
        this.syncMaterialLeaveAlert()
        return true
      } finally { this._materialLeavePrompt = false }
    },
    async returnToApplication() { const context = this.materialReturnContext || this.leaveContext; if (!context.bizType) return; if (context.bizType === 'PROFILE') return this.go('/pages/student/profile/index'); await this.go('/pages/student/affairs/' + (context.bizType === 'FUNDING' ? 'funding' : context.bizType === 'AID' ? 'aid' : 'leave') + '?recordId=' + encodeURIComponent(context.bizId)) },
    async go(url) { if (await this.mayLeaveMaterials()) go(url) },
    async back() {
      if (!await this.mayLeaveMaterials()) return
      this._allowMaterialBack = true
      uni.navigateBack({ delta: 1, fail: () => go('/pages/student/home/index'), complete: () => { this._allowMaterialBack = false } })
    },
    gradClass(i) { return GRAD_CLASSES[i % GRAD_CLASSES.length] },
    formatTime(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '' },
    // 学生不该靠主键认业务：后端下发 businessContext 时用业务语言，否则退回原文案。
    bizLine(item) {
      const c = (item && item.businessContext) || {}
      const parts = [c.bizPeriod, c.bizDisplayTitle || this.bizLabel(item.bizType), c.bizDisplaySubtitle].filter(Boolean)
      return parts.length ? parts.join(' · ') : `${this.bizLabel(item.bizType)} #${item.bizId}`
    },
    bizLabel(value) {
      return ({ PROFILE: '个人档案', LEAVE: '请假', AID: '困难认定', FUNDING: '奖助申请', DISCIPLINE: '违纪处分', DISCIPLINE_APPEAL: '处分申诉', DORM_TRANSFER: '调宿申请', CREDIT_APPEAL: '第二课堂申诉', SECOND_CLASS_APPEAL: '第二课堂申诉' }[value] || '学工申请')
    },
    canSubmitMaterial(item) { return (item.allowedActions || []).includes('SUBMIT_MATERIAL') },
    load() {
      this.state = 'loading'
      Promise.all([
        studentApi.getAffairsOverview(),
        studentApi.getMyDiscipline().catch(() => null),
        this.loadMaterials(false)
      ]).then(([ov, d]) => {
        this.data = ov
        this.disc = d
        this.state = 'ready'
        this.scrollToMaterial()
      }).catch(() => { this.state = 'error' })
    },
    loadMaterials(showToast = true, reset = true) {
      this.materialError = ''
      if (reset) this.materialPage = 1
      return affairsContractApi.getMyMaterialRequirements({
        ...this.leaveContext, page: this.materialPage,
        pageSize: this.materialPageSize,
        requirementId: this.focusMaterialId || undefined
      }).then((d) => {
        this.materials = (d && d.items) || []
        this.materialTotal = Number((d && d.total) || 0)
        this.scrollToMaterial()
        return this.materials
      }).catch((e) => {
        this.materialError = normalizeError(e).text || '材料列表加载失败'
        if (showToast) toast(this.materialError)
        return []
      })
    },
    loadMoreMaterials() {
      if (this.materialLoadingMore || this.materials.length >= this.materialTotal) return
      this.materialLoadingMore = true
      const nextPage = this.materialPage + 1
      affairsContractApi.getMyMaterialRequirements({ ...this.leaveContext, requirementId: this.focusMaterialId || undefined, page: nextPage, pageSize: this.materialPageSize })
        .then((d) => {
          this.materials = this.materials.concat((d && d.items) || [])
          this.materialTotal = Number((d && d.total) || this.materialTotal)
          this.materialPage = nextPage
        })
        .catch((e) => toast(normalizeError(e).text || '更多材料加载失败'))
        .finally(() => { this.materialLoadingMore = false })
    },
    scrollToMaterial() {
      if (!this.focusMaterialId && !this.leaveContext.bizId) return
      this.$nextTick(() => {
        setTimeout(() => {
          try { uni.pageScrollTo({ selector: this.focusMaterialId ? '#material-' + this.focusMaterialId : '#affairs-material-section', duration: 250 }) } catch (e) {}
        }, 80)
      })
    },
    chooseMaterial(item) {
      if (this.materialBusy) return
      const done = (res) => {
        if (this.materialBusy) return
        const file = (res && res.tempFiles && res.tempFiles[0]) || null
        if (!file) return
        this.selectedFiles = { ...this.selectedFiles, [item.requirementId]: {
          path: file.path || file.tempFilePath,
          name: file.name || `补交材料-${Date.now()}`
        } }
        delete this.uploadedMaterials[item.requirementId]
        delete this.materialNotices[item.requirementId]
      }
      if (typeof uni.chooseMessageFile === 'function') {
        uni.chooseMessageFile({ count: 1, type: 'file', success: done, fail: () => {} })
      } else if (typeof uni.chooseFile === 'function') {
        uni.chooseFile({ count: 1, success: done, fail: () => {} })
      } else {
        uni.chooseImage({ count: 1, success: done, fail: () => {} })
      }
    },
    materialFileHint(file) {
      if (file.readyForBusiness === true) return '文件已上传且安全可用，确认后提交老师审核。'
      if (file.scanStatus === 'ERROR') return '安全扫描失败，请稍后检查；持续失败可更换文件或联系学校管理员。'
      if (['PENDING', 'RUNNING'].includes(file.scanStatus)) return '文件已上传，正在等待安全扫描；稍后点击“检查并提交审核”，无需重复上传。'
      if (['INFECTED', 'QUARANTINED'].includes(file.scanStatus) || file.status === 'QUARANTINED') return '文件存在安全风险，请更换文件后重新提交。'
      return '文件尚不可提交，请检查最新状态或更换文件。'
    },
    async submitMaterial(item) {
      const chosen = this.selectedFiles[item.requirementId]
      if (!chosen || !chosen.path || this.materialBusy) return
      this.materialBusy = item.requirementId
      delete this.materialNotices[item.requirementId]
      try {
        if (!this.uploadedMaterials[item.requirementId]) this.uploadedMaterials[item.requirementId] = await affairsContractApi.uploadMaterialFile(chosen.path)
        const uploaded = this.uploadedMaterials[item.requirementId]
        const metadata = await fileSdk.metadata(uploaded.fileId)
        this.uploadedMaterials[item.requirementId] = metadata
        if (metadata.readyForBusiness !== true) return
        await affairsContractApi.submitMaterialVersion(item.requirementId, uploaded.fileId, this.materialNotes[item.requirementId] || '', item.version)
        toast('材料已补交，等待老师审核')
        delete this.selectedFiles[item.requirementId]
        delete this.uploadedMaterials[item.requirementId]
        this.materialNotes[item.requirementId] = ''
        await this.loadMaterials(false)
      } catch (e) {
        this.materialNotices[item.requirementId] = normalizeError(e).text || '材料补交失败，文件与说明已保留，请重试'
      } finally { this.materialBusy = '' }
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
.af__hero { padding: 0 var(--page-padding-mobile) var(--space-4); }
.af__navbar { position: relative; height: 40px; display: flex; align-items: center; justify-content: center; }
.af__navbar-back { position: absolute; left: 0; color: #fff; font-size: 22px; padding: 4px 8px; }
.af__navbar-title { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: #fff; }
.link,.af__link,.af__refresh { color: #2563eb; }
.link { display: block; margin-top: 8px; }
.af__refresh { font-size: 12px; }
.af__empty { text-align: center; color: var(--text-tertiary); }
.af__material.is-focus { border: 2px solid var(--brand-primary); }
.af__mat-head { align-items: flex-start; gap: 10px; }
.af__reason,.af__due,.af__review { display: block; margin-top: 8px; font-size: 12px; color: var(--text-secondary); line-height: 1.6; }
.af__due.overdue,.af__review { color: var(--warning-700); }
.af__submit { margin-top: 12px; padding: 12px; border-radius: 10px; background: var(--bg-page); display: flex; flex-direction: column; gap: 9px; }
.af__pending { margin-top: 12px; padding: 10px; border-radius: 8px; background: #eff6ff; color: #1d4ed8; font-size: 12px; }
.af__versions { margin-top: 14px; }
.af__versions-title { display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; }
.af__more { width: 100%; margin-top: 10px; }
.af__version { padding: 10px 0; border-top: 1px solid var(--border-light); align-items: flex-start; gap: 8px; }
.af__version-actions { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.af__current { color: var(--brand-primary); background: #eff6ff; padding: 2px 6px; border-radius: 5px; }
.af__work-study { display:flex; justify-content:space-between; align-items:center; gap:12px; margin-top:12px; padding:12px 2px 2px; border-top:1px solid var(--border-light); }
</style>
