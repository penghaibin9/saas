<template>
  <view class="page-wrap sc">
    <MobileNavBar variant="student" title="实习变更申请" subtitle="从真实岗位库选择目标，审批后重新合规上岗" show-back />
    <MobileGlobalState :state="pageState" @retry="load">
      <view v-if="context" class="page-pad stack">
        <view v-if="receipt" class="card sc__receipt">
          <view class="row-between"><text class="t-bold">✓ {{ receipt.actionLabel }}</text><text>v{{ receipt.version }}</text></view>
          <text>申请 #{{ receipt.id }} · {{ receipt.statusLabel }}</text>
          <text>{{ receipt.nextStep }}</text>
        </view>

        <view class="card sc__current">
          <text class="sc__eyebrow">当前实习关系</text>
          <text class="sc__company">{{ context.company || '未落实单位' }}</text>
          <text class="sc__position">{{ context.post || '未落实岗位' }} · {{ context.batch }}</text>
          <text class="sc__version">批次 #{{ context.batchId }} · 实习记录 #{{ context.recordId }} · {{ context.statusText }}</text>
        </view>

        <view class="card stack">
          <view class="sc__field">
            <text class="sc__label">变更类型</text>
            <picker mode="selector" :range="typeLabels" :value="typeIndex" @change="onTypePick">
              <view class="sc__picker">{{ typeLabels[typeIndex] || '请选择' }} <text>▾</text></view>
            </picker>
          </view>

          <template v-if="needCatalog">
            <view class="sc__field">
              <text class="sc__label">选择真实目标岗位 <text class="sc__req">*</text></text>
              <view class="sc__search"><input v-model="keyword" placeholder="搜索企业、岗位或地点" @confirm="searchTargets" /><button :disabled="targetLoading" @click="searchTargets">搜索</button></view>
            </view>
            <view v-if="selectedTarget" class="sc__selected">
              <text class="sc__eyebrow">已选目标关系</text>
              <view class="sc__compare"><text>{{ context.company || '当前单位' }} / {{ context.post || '当前岗位' }}</text><text class="sc__compare-arrow">→</text><text>{{ selectedTarget.companyName }} / {{ selectedTarget.title }}</text></view>
              <text>{{ selectedTarget.workLocation || '地点待企业完善' }} · 剩余 {{ selectedTarget.remaining }} 个名额</text>
            </view>
            <view v-if="targetLoading" class="sc__target-state">正在核验本批次可申请岗位…</view>
            <view v-else-if="!targets.length" class="sc__target-state">暂无符合批次、企业准入、劳动权益与容量要求的岗位</view>
            <view v-else class="sc__targets">
              <button v-for="item in targets" :key="item.id" type="button" class="sc__target" :class="{ 'is-selected': selectedTarget?.id === item.id }" @click="selectTarget(item)">
                <view class="row-between"><text class="t-bold">{{ item.title }}</text><text>余 {{ item.remaining }}</text></view>
                <text>{{ item.companyName }}</text><text>{{ item.workLocation || '地点待完善' }} · {{ item.ruleVersion }}</text>
              </button>
            </view>
          </template>

          <template v-if="needSelfNames">
            <view class="sc__field"><text class="sc__label">自主联系企业 <text class="sc__req">*</text></text><input v-model="form.targetEnterpriseName" class="sc__input" placeholder="填写真实企业全称" /></view>
            <view class="sc__field"><text class="sc__label">自主实习岗位 <text class="sc__req">*</text></text><input v-model="form.targetPositionName" class="sc__input" placeholder="填写真实岗位名称" /></view>
          </template>

          <view class="sc__field"><text class="sc__label">变更原因 <text class="sc__req">*</text></text><textarea v-model="form.reason" class="sc__textarea" maxlength="500" placeholder="说明为什么变更，以及已完成哪些沟通（不少于 5 字）" /></view>

          <view class="sc__impact">
            <text class="t-bold">审批通过后会发生什么</text>
            <text>1. 原岗位关系与原企业导师权限停止，原名额释放。</text>
            <text>2. 原知情确认与协议失效，按新去向重新办理。</text>
            <text>3. 状态回退为待上岗/准备中，重新合规前不能打卡。</text>
          </view>
        </view>

        <view v-if="history.length" class="card sc__history">
          <text class="card-title">申请与处理记录</text>
          <view v-for="item in history" :key="item.id" class="sc__hist">
            <view><text class="t-bold">{{ item.changeTypeLabel }} · {{ item.statusLabel }}</text><text>#{{ item.id }} · v{{ item.version }} · {{ item.createdAt }}</text></view>
            <button v-if="item.status === 'PENDING'" :disabled="withdrawing === item.id" @click="withdraw(item)">{{ withdrawing === item.id ? '撤回中…' : '撤回申请' }}</button>
          </view>
        </view>
      </view>
    </MobileGlobalState>
    <MobileSafeAreaBar v-if="context">
      <button class="btn btn-primary flex-1" :disabled="submitting" @click="submit">{{ submitting ? '提交中…' : '提交变更申请' }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import {
  studentInternshipChanges, studentInternshipChangeTargets,
  studentInternshipChangeApply, studentInternshipChangeWithdraw
} from '@/services/internshipApi'
import { toast } from '@/utils/nav'

const TYPES = [
  { value: 'CHANGE_POSITION', label: '换岗' },
  { value: 'CHANGE_ENTERPRISE', label: '换实习单位' },
  { value: 'SELF_ARRANGED', label: '转自主实习' },
  { value: 'WITHDRAW_POST', label: '退岗' }
]

export default {
  data() {
    return {
      pageState: 'loading', submitting: false, withdrawing: '', requestedBatchId: '', context: null,
      typeIndex: 0, typeLabels: TYPES.map((item) => item.label), keyword: '', targets: [],
      targetLoading: false, selectedTarget: null,
      form: { targetEnterpriseName: '', targetPositionName: '', reason: '' },
      history: [], receipt: null
    }
  },
  computed: {
    currentType() { return TYPES[this.typeIndex].value },
    needCatalog() { return ['CHANGE_POSITION', 'CHANGE_ENTERPRISE'].includes(this.currentType) },
    needSelfNames() { return this.currentType === 'SELF_ARRANGED' }
  },
  onLoad(options) { this.requestedBatchId = options?.batchId || ''; this.load() },
  onPullDownRefresh() { this.load(() => uni.stopPullDownRefresh()) },
  methods: {
    async load(done) {
      this.pageState = 'loading'
      try {
        const dashboard = await studentApi.getInternship(this.requestedBatchId)
        if (!dashboard?.hasBatch || !dashboard.recordId || !dashboard.batchId) {
          this.context = null; this.history = []; this.pageState = 'empty'; return
        }
        this.context = dashboard
        const data = await studentInternshipChanges(dashboard.batchId, dashboard.recordId)
        this.history = data?.items || []
        this.pageState = 'ready'
        if (this.needCatalog) await this.loadTargets()
      } catch (e) {
        this.pageState = 'error'
      } finally { if (done) done() }
    },
    async onTypePick(e) {
      this.typeIndex = Number(e.detail.value) || 0
      this.selectedTarget = null; this.targets = []; this.keyword = ''
      this.form.targetEnterpriseName = ''; this.form.targetPositionName = ''
      if (this.needCatalog) await this.loadTargets()
    },
    searchTargets() { this.selectedTarget = null; this.loadTargets() },
    async loadTargets() {
      if (!this.context || !this.needCatalog) return
      this.targetLoading = true
      try {
        const data = await studentInternshipChangeTargets(
          this.context.batchId, this.context.recordId, this.currentType, this.keyword, 1, 20)
        this.targets = data?.items || []
      } catch (e) {
        this.targets = []; toast((e && e.message) || '目标岗位加载失败')
      } finally { this.targetLoading = false }
    },
    selectTarget(item) {
      this.selectedTarget = item
      this.form.targetEnterpriseName = item.companyName
      this.form.targetPositionName = item.title
    },
    async submit() {
      if (this.submitting || !this.context) return
      const reason = (this.form.reason || '').trim()
      if (reason.length < 5) return toast('变更原因不少于 5 字')
      if (this.needCatalog && !this.selectedTarget) return toast('请从真实岗位列表选择目标岗位')
      if (this.needSelfNames && ((this.form.targetEnterpriseName || '').trim().length < 2 || (this.form.targetPositionName || '').trim().length < 2)) return toast('请填写完整的自主实习企业和岗位')
      const body = {
        batchId: this.context.batchId, internshipId: this.context.recordId,
        expectedVersion: 0, changeType: this.currentType, reason,
        targetEnterpriseName: this.form.targetEnterpriseName,
        targetPositionName: this.form.targetPositionName
      }
      if (this.selectedTarget) {
        body.targetPositionId = this.selectedTarget.positionId
        body.targetEnterpriseId = this.selectedTarget.companyId
      }
      this.submitting = true
      try {
        const result = await studentInternshipChangeApply(body)
        this.receipt = {
          actionLabel: '变更申请已提交', id: result.id, version: result.version,
          statusLabel: result.statusLabel || result.status, nextStep: '等待指导教师审核；审核前可在本页撤回'
        }
        this.form.reason = ''; this.selectedTarget = null
        toast('申请已提交并留下回执')
        const data = await studentInternshipChanges(this.context.batchId, this.context.recordId)
        this.history = data?.items || []
      } catch (e) {
        toast((e && e.message) || '提交失败，填写内容已保留')
      } finally { this.submitting = false }
    },
    async withdraw(item) {
      if (this.withdrawing) return
      this.withdrawing = item.id
      try {
        const result = await studentInternshipChangeWithdraw(item.id, {
          batchId: this.context.batchId, internshipId: this.context.recordId,
          expectedVersion: item.version
        })
        this.receipt = {
          actionLabel: '变更申请已撤回', id: result.id, version: result.version,
          statusLabel: result.statusLabel || result.status, nextStep: '如仍需变更，可基于当前真实关系重新提交'
        }
        const data = await studentInternshipChanges(this.context.batchId, this.context.recordId)
        this.history = data?.items || []
        toast('申请已撤回')
      } catch (e) {
        toast((e && e.message) || '撤回失败，正在刷新')
        const data = await studentInternshipChanges(this.context.batchId, this.context.recordId)
        this.history = data?.items || []
      } finally { this.withdrawing = '' }
    }
  }
}
</script>

<style scoped>
.sc__compare-arrow{color:var(--student-600);font-weight:700}
.sc__receipt{display:flex;flex-direction:column;gap:6px;padding:var(--space-3);border-color:var(--success-300,#86efac);background:var(--success-50,#f0fdf4);font-size:var(--font-size-xs);line-height:1.55}.sc__current{display:flex;flex-direction:column;gap:5px;padding:var(--space-3);background:linear-gradient(135deg,var(--student-50,#eff6ff),var(--bg-card,#fff))}.sc__eyebrow{font-size:10px;font-weight:700;letter-spacing:.08em;color:var(--student-700)}.sc__company{font-size:var(--font-size-lg);font-weight:700}.sc__position{font-size:var(--font-size-sm);color:var(--text-secondary)}.sc__version{font-size:var(--font-size-xs);color:var(--text-tertiary)}.sc__field{display:flex;flex-direction:column;gap:6px;margin-bottom:var(--space-3)}.sc__label{font-size:var(--font-size-sm);color:var(--text-secondary)}.sc__req{color:var(--danger-500)}.sc__input,.sc__picker,.sc__search{border:1px solid var(--border-base);border-radius:var(--radius-md);background:var(--bg-card)}.sc__input,.sc__picker{padding:10px 12px;font-size:var(--font-size-sm)}.sc__picker{display:flex;justify-content:space-between}.sc__search{display:flex;overflow:hidden}.sc__search input{flex:1;min-width:0;padding:9px 11px;font-size:var(--font-size-sm)}.sc__search button{width:72px;border:0;border-left:1px solid var(--border-light);border-radius:0;background:var(--student-600);color:#fff;font-size:var(--font-size-sm)}.sc__search button::after{border:none}.sc__textarea{box-sizing:border-box;width:100%;min-height:110px;padding:10px 12px;border:1px solid var(--border-base);border-radius:var(--radius-md);font-size:var(--font-size-sm)}.sc__selected{display:flex;flex-direction:column;gap:7px;margin-bottom:var(--space-3);padding:10px 11px;border:1px solid var(--student-300,#93c5fd);border-radius:var(--radius-md);background:var(--student-50,#eff6ff);font-size:var(--font-size-xs);color:var(--text-secondary)}.sc__compare{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:7px;color:var(--text-primary)}.sc__compare b{color:var(--student-600)}.sc__target-state{padding:var(--space-3);border:1px dashed var(--border-base);border-radius:var(--radius-md);text-align:center;font-size:var(--font-size-xs);line-height:1.5;color:var(--text-tertiary)}.sc__targets{display:flex;flex-direction:column;gap:8px;margin-bottom:var(--space-3);max-height:360px;overflow:auto}.sc__target{display:flex;flex-direction:column;gap:5px;margin:0;padding:10px 11px;border:1px solid var(--border-light);border-radius:var(--radius-md);background:var(--bg-card);text-align:left;font-size:var(--font-size-xs);line-height:1.45}.sc__target.is-selected{border-color:var(--student-500);background:var(--student-50,#eff6ff)}.sc__target text{color:var(--text-secondary)}.sc__target::after{border:none}.sc__impact{display:flex;flex-direction:column;gap:6px;padding:10px 11px;border-radius:var(--radius-md);background:var(--warning-50,#fffbeb);font-size:var(--font-size-xs);line-height:1.55;color:var(--text-secondary)}.sc__history{padding:var(--space-3)}.sc__hist{display:flex;align-items:center;justify-content:space-between;gap:var(--space-2);padding:10px 0;border-bottom:1px solid var(--border-light)}.sc__hist>view{display:flex;min-width:0;flex-direction:column;gap:4px}.sc__hist b{font-size:var(--font-size-sm)}.sc__hist text{font-size:var(--font-size-xs);color:var(--text-tertiary)}.sc__hist button{flex-shrink:0;margin:0;padding:4px 10px;border:1px solid var(--danger-300);border-radius:var(--radius-md);background:var(--bg-card);color:var(--danger-600);font-size:var(--font-size-xs);line-height:1.8}.sc__hist button::after{border:none}@media(max-width:360px){.sc__compare{grid-template-columns:1fr}.sc__compare b{justify-self:center;transform:rotate(90deg)}}
</style>
