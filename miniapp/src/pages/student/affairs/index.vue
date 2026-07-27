<template>
  <view class="page-wrap">
    <view class="af__hero hero-band is-brand">
      <view class="hero-band__orb" />
      <view class="mnav__status" :style="{ height: statusBarHeight + 'px' }" />
      <view class="af__navbar"><text class="af__navbar-back" @click="back">‹</text><text class="af__navbar-title">学工中心</text></view>
      <view class="stat-strip" v-if="data">
        <view class="stat-strip__item"><text class="stat-strip__val">{{ data.leaveCount }}</text><text class="stat-strip__label">请假</text></view>
        <view class="stat-strip__item"><text class="stat-strip__val">{{ data.aidApproved }}</text><text class="stat-strip__label">困难认定</text></view>
        <view class="stat-strip__item"><text class="stat-strip__val">{{ data.fundingGranted }}</text><text class="stat-strip__label">获资助</text></view>
        <view class="stat-strip__item"><text class="stat-strip__val">{{ openMaterials.length }}</text><text class="stat-strip__label">待补材料</text></view>
      </view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="data" style="padding-top: var(--space-3);">
        <view class="card">
          <view class="icon-grid">
            <view v-for="(it, i) in entries" :key="it.key" class="icon-grid__item" @click="go(it.route)">
              <view class="icon-grid__badge" :class="gradClass(i)">{{ it.icon }}</view>
              <text class="icon-grid__label">{{ it.label }}</text>
            </view>
          </view>
        </view>

        <view class="section-head"><text class="section-head__title">材料补交</text><text class="af__refresh" @click="loadMaterials">刷新</text></view>
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
                <text class="t-xs t-tertiary">{{ bizLabel(item.bizType) }} #{{ item.bizId }} · 第{{ item.returnRound || 1 }}轮</text>
              </view>
              <MobileStatusTag :status="item.status" :label="item.statusLabel || item.status" />
            </view>
            <text v-if="item.requirementReason" class="af__reason">缺项说明：{{ item.requirementReason }}</text>
            <text v-if="item.dueAt" class="af__due" :class="{ overdue: item.overdue }">截止 {{ formatTime(item.dueAt) }}{{ item.overdue ? '（已逾期）' : '' }}</text>
            <text class="t-xs t-tertiary">审核责任人：{{ item.reviewOwner || '待分配' }}</text>

            <view v-if="canSubmitMaterial(item)" class="af__submit">
              <button class="btn btn-secondary" :disabled="materialBusy === item.requirementId" @click="chooseMaterial(item)">
                {{ selectedFiles[item.requirementId] ? selectedFiles[item.requirementId].name : '选择补交文件' }}
              </button>
              <input v-model.trim="materialNotes[item.requirementId]" class="input" maxlength="500" placeholder="补充说明（选填）" />
              <button class="btn btn-primary" :disabled="materialBusy === item.requirementId || !selectedFiles[item.requirementId]" @click="submitMaterial(item)">
                {{ materialBusy === item.requirementId ? '提交中…' : '上传并提交审核' }}
              </button>
            </view>
            <view v-else-if="item.status === 'PENDING_REVIEW'" class="af__pending"><text>最新版本已提交，等待老师审核。</text></view>

            <view class="af__versions" v-if="(item.versions || []).length">
              <text class="af__versions-title">版本记录（{{ item.versionCount || item.versions.length }}）</text>
              <view v-for="version in item.versions" :key="version.submissionId" class="af__version row-between">
                <view class="flex-1">
                  <text class="t-sm t-primary">V{{ version.versionNo }} · {{ version.fileName }}</text>
                  <text class="t-xs t-tertiary">{{ version.statusLabel || version.status }} · {{ formatTime(version.submittedAt) }}</text>
                  <text v-if="version.reviewNote" class="af__review">审核意见：{{ version.reviewNote }}</text>
                </view>
                <view class="af__version-actions">
                  <text v-if="version.current" class="af__current">当前</text>
                  <text v-if="version.downloadable" class="af__link" @click="downloadMaterial(version)">查看</text>
                </view>
              </view>
            </view>
          </view>
        </view>

        <view class="section-head"><text class="section-head__title">我的处分</text></view>
        <view class="card" @click="go('/pages/student/affairs/discipline')">
          <text class="t-sm t-secondary">{{ discNote }}</text>
          <text class="t-sm link">进入申诉 ›</text>
        </view>
      </view>
    </MobileGlobalState>
    <MobileTabBar side="student" active="home" />
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { affairsContractApi } from '@/services/affairsContractApi'
import { normalizeError } from '@/services/request'
import { go, toast } from '@/utils/nav'

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
      selectedFiles: {},
      materialNotes: {},
      focusMaterialId: ''
    }
  },
  onLoad(query) {
    try { this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20 } catch (e) {}
    this.focusMaterialId = String((query && (query.materialRequirementId || query.requirementId)) || '')
    this.load()
  },
  computed: {
    discNote() {
      if (!this.disc) return '生效中处分数量'
      return this.disc.activeCount > 0 ? `生效中 ${this.disc.activeCount} 条（${this.disc.detailNote || '明细请联系辅导员'}）` : '暂无生效处分'
    },
    openMaterials() { return this.materials.filter((x) => ['MISSING', 'RETURNED', 'PENDING_REVIEW'].includes(x.status)) }
  },
  methods: {
    go,
    back() { uni.navigateBack({ delta: 1, fail: () => go('/pages/student/home/index') }) },
    gradClass(i) { return GRAD_CLASSES[i % GRAD_CLASSES.length] },
    formatTime(value) { return value ? String(value).replace('T', ' ').slice(0, 16) : '' },
    bizLabel(value) {
      return ({ LEAVE: '请假', AID: '困难认定', FUNDING: '奖助申请', DISCIPLINE: '违纪处分', DISCIPLINE_APPEAL: '处分申诉', DORM_TRANSFER: '调宿申请', CREDIT_APPEAL: '第二课堂申诉', SECOND_CLASS_APPEAL: '第二课堂申诉' }[value] || value || '学工申请')
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
    loadMaterials(showToast = true) {
      this.materialError = ''
      return affairsContractApi.getMyMaterialRequirements().then((d) => {
        this.materials = (d && d.items) || []
        this.scrollToMaterial()
        return this.materials
      }).catch((e) => {
        this.materialError = normalizeError(e).text || '材料列表加载失败'
        if (showToast) toast(this.materialError)
        return []
      })
    },
    scrollToMaterial() {
      if (!this.focusMaterialId) return
      this.$nextTick(() => {
        setTimeout(() => {
          try { uni.pageScrollTo({ selector: '#material-' + this.focusMaterialId, duration: 250 }) } catch (e) {}
        }, 80)
      })
    },
    chooseMaterial(item) {
      const done = (res) => {
        const file = (res && res.tempFiles && res.tempFiles[0]) || null
        if (!file) return
        this.$set(this.selectedFiles, item.requirementId, {
          path: file.path || file.tempFilePath,
          name: file.name || `补交材料-${Date.now()}`
        })
      }
      if (typeof uni.chooseMessageFile === 'function') {
        uni.chooseMessageFile({ count: 1, type: 'file', success: done, fail: () => {} })
      } else if (typeof uni.chooseFile === 'function') {
        uni.chooseFile({ count: 1, success: done, fail: () => {} })
      } else {
        uni.chooseImage({ count: 1, success: done, fail: () => {} })
      }
    },
    submitMaterial(item) {
      const chosen = this.selectedFiles[item.requirementId]
      if (!chosen || !chosen.path || this.materialBusy) return
      this.materialBusy = item.requirementId
      affairsContractApi.uploadMaterialFile(chosen.path)
        .then((uploaded) => affairsContractApi.submitMaterialVersion(
          item.requirementId,
          uploaded.fileId,
          this.materialNotes[item.requirementId] || '',
          item.version
        ))
        .then(() => {
          toast('材料已补交，等待老师审核')
          this.$delete(this.selectedFiles, item.requirementId)
          this.$set(this.materialNotes, item.requirementId, '')
          return this.loadMaterials(false)
        })
        .catch((e) => toast(normalizeError(e).text || '材料补交失败'))
        .finally(() => { this.materialBusy = '' })
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
.af__version { padding: 10px 0; border-top: 1px solid var(--border-light); align-items: flex-start; gap: 8px; }
.af__version-actions { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.af__current { color: var(--brand-primary); background: #eff6ff; padding: 2px 6px; border-radius: 5px; }
</style>
