<template>
  <view class="internship-surface mobile-page mobile-student page-wrap sc">
    <MobileNavBar variant="brand" title="实习变更申请" show-back :fallback-url="'/pages/student-internship/index' + (context?.batchId ? '?batchId=' + encodeURIComponent(context.batchId) : '')" />
    <MobileGlobalState :state="pageState" @retry="load">
      <view v-if="context" class="page-pad stack">
        <view v-if="receipt" class="card sc__receipt">
          <view class="row-between"><text class="t-bold">✓ {{ receipt.actionLabel }}</text><text>第 {{ receipt.version }} 版</text></view>
          <text>申请 #{{ receipt.id }} · {{ receipt.statusLabel }}</text>
          <text>{{ receipt.nextStep }}</text>
        </view>

        <view class="card sc__current">
          <view class="row-between"><text class="sc__eyebrow">当前实习</text><MobileStatusTag :label="recordStatusLabel" /></view>
          <text class="sc__company">{{ context.company || '未落实单位' }}</text>
          <text class="sc__position">{{ context.post || '未落实岗位' }}</text>
          <button class="mobile-control sc__details-toggle" :aria-expanded="relationshipDetailsExpanded" @click="expandedRelationshipScope = relationshipDetailsExpanded ? '' : relationshipScope">{{ relationshipDetailsExpanded ? '收起实习详情' : '实习详情' }} <text>{{ relationshipDetailsExpanded ? '▴' : '▾' }}</text></button>
          <view v-if="relationshipDetailsExpanded"><text class="sc__position">{{ context.batch }}</text><text class="sc__version">批次编号 {{ context.batchId }} · 实习记录编号 {{ context.recordId }}</text></view>
        </view>

        <MobileInlineAlert v-if="!writable" type="info" description="历史实习仅可查看变更记录。" />
        <view v-if="writable" class="card stack">
          <view v-if="editing" class="sc__impact"><text class="t-bold">补正原申请 #{{ editing.id }} · 第 {{ editing.version }} 版</text><text>教师意见：{{ editing.reviewComment || '请补充变更说明' }}</text><text v-if="needCatalog">请重新核对并选择当前可申请岗位。</text><button class="mobile-control" :disabled="!writable || submitting || !!withdrawing" @click="cancelEdit">取消补正</button></view>
          <text v-if="formError" role="alert">{{ formError }}</text>
          <view class="sc__field">
            <text class="sc__label">变更类型</text>
            <picker class="mobile-picker" :disabled="!writable || !!editing || submitting" mode="selector" :range="typeLabels" :value="typeIndex" @change="onTypePick">
              <view class="sc__picker">{{ typeLabels[typeIndex] || '请选择' }} <text>▾</text></view>
            </picker>
          </view>

          <template v-if="needCatalog">
            <view class="sc__field">
              <text class="sc__label">目标岗位 <text class="sc__req">*</text></text>
              <view class="sc__search"><input class="mobile-input" v-model="keyword" :disabled="!writable || submitting || !!withdrawing" placeholder="搜索企业、岗位或地点" @confirm="searchTargets" /><button class="mobile-control" :disabled="targetLoading" @click="searchTargets">搜索</button></view>
            </view>
            <view v-if="selectedTarget" class="sc__selected">
              <text class="sc__eyebrow">已选目标关系</text>
              <view class="sc__compare"><text>{{ context.company || '当前单位' }} / {{ context.post || '当前岗位' }}</text><text class="sc__compare-arrow">→</text><text>{{ selectedTarget.companyName }} / {{ selectedTarget.title }}</text></view>
              <text>{{ selectedTarget.workLocation || '地点待企业完善' }} · 剩余 {{ selectedTarget.remaining }} 个名额</text>
            </view>
            <view v-if="targetLoading" class="sc__target-state">正在核验本批次可申请岗位…</view>
            <view v-else-if="targetError" role="alert">{{ targetError }}<button class="mobile-control" @click="loadTargets(targetPage)">重试岗位查询</button></view>
            <view v-else-if="!targets.length" class="sc__target-state">{{ targetPage > 1 || targetHasMore ? '本页暂无目标岗位，可调整搜索或翻页' : '暂无可申请岗位，请调整搜索' }}</view>
            <view v-else class="sc__targets">
              <button v-for="item in targets" :key="item.id" type="button" class="mobile-control sc__target" :disabled="item.canSelect !== true || submitting" :class="{ 'is-selected': selectedTarget?.id === item.id }" @click="selectTarget(item)">
                <view class="row-between"><text class="t-bold">{{ item.title }}</text><text>余 {{ item.remaining }}</text></view>
                <text>{{ item.companyName }}</text><text>{{ item.workLocation || '地点待完善' }}</text><text v-if="item.canSelect !== true">暂不可选：{{ item.selectionReason || '岗位条件待核验' }}</text>
              </button>
            </view>
            <view v-if="targetPage > 1 || targetHasMore" class="row-between"><button class="mobile-control" :disabled="targetLoading || targetPage <= 1" @click="loadTargets(targetPage-1)">上一页岗位</button><text>第 {{ targetPage }} 页</text><button class="mobile-control" :disabled="targetLoading || !targetHasMore" @click="loadTargets(targetPage+1)">下一页岗位</button></view>
          </template>

          <template v-if="needSelfNames">
            <view class="sc__field"><text class="sc__label">自主联系企业 <text class="sc__req">*</text></text><input v-model="form.targetEnterpriseName" :disabled="!writable || submitting || !!withdrawing" class="mobile-input sc__input" placeholder="填写真实企业全称" /></view>
            <view class="sc__field"><text class="sc__label">自主实习岗位 <text class="sc__req">*</text></text><input v-model="form.targetPositionName" :disabled="!writable || submitting || !!withdrawing" class="mobile-input sc__input" placeholder="填写真实岗位名称" /></view>
          </template>

          <view class="sc__field"><text class="sc__label">变更原因 <text class="sc__req">*</text></text><textarea v-model="form.reason" :disabled="!writable || submitting || !!withdrawing" class="mobile-textarea sc__textarea" maxlength="500" placeholder="说明为什么变更，以及已完成哪些沟通（不少于 5 字）" /></view>

          <view class="sc__impact">
            <text class="t-bold">审批通过后会发生什么</text>
            <text>1. 原岗位关系与原企业导师权限停止，原名额释放。</text>
            <text>2. 原知情确认与协议失效，按新去向重新办理。</text>
            <text>3. 状态回退为待上岗/准备中，重新合规前不能打卡。</text>
          </view>
        </view>

        <view class="card sc__history">
          <text class="card-title">申请与处理记录</text>
          <text v-if="historyError" role="alert">{{ historyError }}<button class="mobile-control" @click="loadHistory(historyPage)">重试处理记录</button></text><text v-else-if="!history.length" class="sc__empty">暂无变更申请</text>
          <view v-for="item in history" :key="item.id" class="sc__hist">
            <view><text class="t-bold">{{ typeLabel(item.changeType) }} · {{ statusLabel(item.status) }}</text><text>#{{ item.id }} · 第 {{ item.version }} 版 · {{ formatTime(item.createdAt) }}</text><button v-if="item.status === 'APPROVED'" class="mobile-control btn btn-ghost" :aria-expanded="expandedHistoryId === item.id" @click="expandedHistoryId = expandedHistoryId === item.id ? '' : item.id">{{ expandedHistoryId === item.id ? '收起办理详情' : '查看办理详情' }}</button><template v-if="item.status !== 'APPROVED' || expandedHistoryId === item.id"><text v-if="item.reason">申请原因：{{ item.reason }}</text><text v-if="item.reviewComment">审核意见：{{ item.reviewComment }}</text></template></view>
            <button class="mobile-control" v-if="item.status === 'PENDING'" :disabled="!writable || !!withdrawing || submitting" @click="withdraw(item)">{{ withdrawing === item.id ? '撤回中…' : '撤回申请' }}</button>
            <button class="mobile-control" v-if="item.status === 'REJECTED'" :disabled="!writable || submitting || !!withdrawing" @click="edit(item)">原单补正重交</button>
          </view>
          <view v-if="historyPage > 1 || historyHasMore" class="row-between"><button class="mobile-control" :disabled="historyLoading || historyPage <= 1" @click="loadHistory(historyPage-1)">上一页记录</button><text>第 {{ historyPage }} 页</text><button class="mobile-control" :disabled="historyLoading || !historyHasMore" @click="loadHistory(historyPage+1)">下一页记录</button></view>
        </view>
      </view>
    </MobileGlobalState>
    <MobileSafeAreaBar v-if="writable && context">
      <button class="mobile-control btn btn-primary flex-1" :disabled="!writable || submitting || !!withdrawing" @click="submit">{{ submitting ? '提交中…' : editing ? '补正后重交原申请' : '提交变更申请' }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { studentInternshipChanges, studentInternshipChangeTargets, studentInternshipChangeApply,
  studentInternshipChangeResubmit, studentInternshipChangeWithdraw } from '@/services/internshipApi'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'
import { formatDateTime } from '@/utils/format'
const TYPES = [
  { value: 'CHANGE_POSITION', label: '换岗' }, { value: 'CHANGE_ENTERPRISE', label: '换实习单位' },
  { value: 'SELF_ARRANGED', label: '转自主实习' }, { value: 'WITHDRAW_POST', label: '退岗' }
]
const emptyForm = () => ({ targetEnterpriseName: '', targetPositionName: '', reason: '' })
export default {
  data() { return {
    pageState: 'loading', submitting: false, withdrawing: '', requestedBatchId: '', context: null,
    expandedHistoryId: '', typeIndex: 0, typeLabels: TYPES.map(item => item.label), keyword: '', targets: [],
    targetLoading: false, targetError: '', targetPage: 1, targetHasMore: false, selectedTarget: null,
    form: emptyForm(), editing: null, formError: '', history: [], historyPage: 1, expandedRelationshipScope: '',
    historyHasMore: false, historyLoading: false, historyError: '', receipt: null,
    hidden: false, generation: currentSessionGeneration(), epoch: 0,
    sequence: 0, targetSequence: 0, historySequence: 0
  } },
  computed: {
    formatTime() { return formatDateTime },
    relationshipScope() { return [this.generation,this.context?.batchId,this.context?.recordId].join(':') },
    relationshipDetailsExpanded() { return this.expandedRelationshipScope === this.relationshipScope },
    writable() { return !!this.context && !this.context.historyMode && ['PREPARING', 'READY', 'ONBOARD', 'ASSESSING'].includes(this.context.statusText) },
    recordStatusLabel() { return ({ PREPARING: '准备中', READY: '待上岗', ONBOARD: '在岗实习', ASSESSING: '考核中', ARCHIVED: '已归档', ENDED: '已结束' })[this.context?.statusText] || '实习状态待核对' },
    currentType() { return TYPES[this.typeIndex].value },
    needCatalog() { return ['CHANGE_POSITION', 'CHANGE_ENTERPRISE'].includes(this.currentType) },
    needSelfNames() { return this.currentType === 'SELF_ARRANGED' }
  },
  onLoad(options) { this.requestedBatchId = String(options?.batchId || ''); this.load() },
  onShow() { const hidden = this.hidden; this.hidden = false; if (hidden || this.generation !== currentSessionGeneration()) this.load() },
  onHide() { this.pause() }, onUnload() { this.pause(); this.form = emptyForm(); this.context = null },
  onPullDownRefresh() { this.load(() => uni.stopPullDownRefresh()) },
  methods: {
    pause() { this.expandedHistoryId = ''; this.hidden = true; this.epoch++; this.sequence++; this.targetSequence++; this.historySequence++; this.submitting = false; this.withdrawing = ''; this.targetLoading = false; this.historyLoading = false },
    current(epoch, generation, batch, record) { return !this.hidden && epoch === this.epoch && generation === currentSessionGeneration() && String(this.context?.batchId) === batch && String(this.context?.recordId) === record },
    resetDraft() { this.editing = null; this.form = emptyForm(); this.selectedTarget = null; this.formError = ''; this.receipt = null },
    cancelEdit() { if (!this.submitting && !this.withdrawing) this.resetDraft() },
    statusLabel(status) { return ({ PENDING: '待教师审核', APPROVED: '已通过', REJECTED: '已退回，请补正', WITHDRAWN: '已撤回' })[status] || '状态待核对' },
    typeLabel(type) { return TYPES.find(item => item.value === type)?.label || '变更类型待核对' },
    errorText(e) { return e?.bizCode === 'DATA_CONFLICT' ? '申请或岗位已变化，请重新读取后核对' : normalizeError(e).text },
    async load(done) {
      if (this.generation !== currentSessionGeneration()) { this.pause(); this.hidden = false; this.generation = currentSessionGeneration(); this.context = null; this.history = []; this.targets = []; this.requestedBatchId = ''; this.resetDraft() }
      const seq = ++this.sequence, generation = currentSessionGeneration();
      const current = () => !this.hidden && seq === this.sequence && generation === currentSessionGeneration();
      this.pageState = 'loading';
      try {
        const dashboard = await studentApi.getInternship(this.requestedBatchId); if (!current()) return;
        if (!dashboard?.hasBatch || !dashboard.recordId || !dashboard.batchId) { this.epoch++; this.resetDraft(); this.context = null; this.history = []; this.targets = []; this.pageState = 'empty'; return }
        if (String(this.context?.batchId) !== String(dashboard.batchId) || String(this.context?.recordId) !== String(dashboard.recordId)) { this.epoch++; this.resetDraft(); this.targets = []; this.history = [] }
        this.context = dashboard; this.pageState = 'ready';
        await Promise.all([this.loadHistory(1), this.needCatalog ? this.loadTargets(1) : Promise.resolve()]);
      } catch (e) { if (current()) this.pageState = normalizeError(e).pageState || 'error' }
      finally { if (done) done() }
    },
    async onTypePick(e) {
      if (this.editing || this.submitting || this.withdrawing) return;
      this.typeIndex = Number(e.detail.value) || 0; this.targetSequence++;
      this.selectedTarget = null; this.targets = []; this.keyword = ''; this.targetError = '';
      this.form.targetEnterpriseName = ''; this.form.targetPositionName = '';
      if (this.needCatalog) await this.loadTargets(1);
    },
    searchTargets() { if (!this.submitting) return this.loadTargets(1) },
    async loadTargets(page = 1) {
      if (!this.context || !this.needCatalog || this.hidden) return;
      const epoch = this.epoch, generation = currentSessionGeneration(), batch = String(this.context.batchId), record = String(this.context.recordId);
      const type = this.currentType, keyword = this.keyword, seq = ++this.targetSequence;
      const current = () => this.current(epoch, generation, batch, record) && seq === this.targetSequence && type === this.currentType;
      this.targetLoading = true; this.targetError = '';
      try { const data = await studentInternshipChangeTargets(batch, record, type, keyword, page, 20); if (!current()) return; this.targets = data?.items || []; this.targetPage = page; this.targetHasMore = !!data?.hasMore }
      catch (e) { if (current()) this.targetError = this.errorText(e) }
      finally { if (current()) this.targetLoading = false }
    },
    async loadHistory(page = 1) {
      if (!this.context || this.hidden) return;
      const epoch = this.epoch, generation = currentSessionGeneration(), batch = String(this.context.batchId), record = String(this.context.recordId), seq = ++this.historySequence;
      const current = () => this.current(epoch, generation, batch, record) && seq === this.historySequence;
      this.historyLoading = true; this.historyError = '';
      try { const data = await studentInternshipChanges(batch, record, page, 20); if (!current()) return; this.history = data?.items || []; this.historyPage = page; this.historyHasMore = !!data?.hasMore }
      catch (e) { if (current()) this.historyError = this.errorText(e) }
      finally { if (current()) this.historyLoading = false }
    },
    selectTarget(item) { if (this.submitting || this.withdrawing || item.canSelect !== true) return; this.selectedTarget = item; this.form.targetEnterpriseName = item.companyName; this.form.targetPositionName = item.title },
    edit(item) {
      if (!this.writable || this.submitting || this.withdrawing || item.status !== 'REJECTED') return;
      this.resetDraft(); this.editing = { id: String(item.id), version: item.version, reviewComment: item.reviewComment || '' };
      this.typeIndex = TYPES.findIndex(type => type.value === item.changeType);
      if (this.typeIndex < 0) { this.resetDraft(); this.typeIndex = 0; return toast('变更类型待学校核对，暂不能补正') }
      this.form = { targetEnterpriseName: item.targetEnterpriseName || '', targetPositionName: item.targetPositionName || '', reason: item.reason || '' };
      this.keyword = ''; this.targets = []; if (this.needCatalog) this.loadTargets(1);
    },
    async submit() {
      if (!this.writable || this.submitting || this.withdrawing || this.hidden) return;
      const reason = this.form.reason.trim();
      if (reason.length < 5) return toast('变更原因不少于 5 字');
      if (this.needCatalog && (!this.selectedTarget || this.selectedTarget.canSelect !== true)) return toast('请从真实岗位列表选择可申请的目标岗位');
      if (this.needSelfNames && (this.form.targetEnterpriseName.trim().length < 2 || this.form.targetPositionName.trim().length < 2)) return toast('请填写完整的自主实习企业和岗位');
      const epoch = this.epoch, generation = currentSessionGeneration(), batch = String(this.context.batchId), record = String(this.context.recordId);
      const current = () => this.current(epoch, generation, batch, record);
      const editing = this.editing;
      const body = { batchId: batch, internshipId: record, expectedVersion: editing ? editing.version : 0, changeType: this.currentType, reason };
      if (this.needCatalog) body.targetPositionId = String(this.selectedTarget.positionId);
      if (this.needSelfNames) Object.assign(body, { targetEnterpriseName: this.form.targetEnterpriseName, targetPositionName: this.form.targetPositionName });
      this.submitting = true; this.formError = '';
      try {
        const result = editing ? await studentInternshipChangeResubmit(editing.id, body) : await studentInternshipChangeApply(body); if (!current()) return;
        this.resetDraft(); this.receipt = { actionLabel: editing ? '原变更单已补正重交' : '变更申请已提交', id: result.id, version: result.version, statusLabel: this.statusLabel(result.status), nextStep: '等待指导教师审核；审核前可在本页撤回' };
        await this.loadHistory(1);
      } catch (e) { if (current()) this.formError = this.errorText(e) + '；填写内容和原版本已保留，请核对后重试' }
      finally { if (current()) this.submitting = false }
    },
    async withdraw(item) {
      if (!this.writable || this.submitting || this.withdrawing || this.hidden) return;
      const epoch = this.epoch, generation = currentSessionGeneration(), batch = String(this.context.batchId), record = String(this.context.recordId);
      const current = () => this.current(epoch, generation, batch, record);
      this.withdrawing = String(item.id); this.formError = '';
      try { const result = await studentInternshipChangeWithdraw(String(item.id), { batchId: batch, internshipId: record, expectedVersion: item.version }); if (!current()) return; this.receipt = { actionLabel: '变更申请已撤回', id: result.id, version: result.version, statusLabel: this.statusLabel(result.status), nextStep: '如仍需变更，可基于当前关系重新申请' }; await this.loadHistory(1) }
      catch (e) { if (current()) this.formError = this.errorText(e) }
      finally { if (current()) this.withdrawing = '' }
    }
  }
}
</script>

<style scoped>
.sc__hist .btn-ghost{color:var(--text-link);border-color:var(--border-light)}
.sc__compare-arrow{color:var(--student-600);font-weight:700}
.sc__receipt{display:flex;flex-direction:column;gap:6px;padding:var(--space-3);border-color:var(--success-300,#86efac);background:var(--success-50,#f0fdf4);font-size:var(--font-size-base);line-height:1.55}.sc__current{display:flex;flex-direction:column;gap:5px;padding:var(--space-3);background:linear-gradient(135deg,var(--student-50,#eff6ff),var(--bg-card,#fff))}.sc__eyebrow{font-size:var(--font-size-base);font-weight:700;letter-spacing:.08em;color:var(--student-700)}.sc__company{font-size:var(--font-size-lg);font-weight:700}.sc__position{font-size:var(--font-size-base);color:var(--text-secondary)}.sc__version{font-size:var(--font-size-base);color:var(--text-tertiary)}.sc__field{display:flex;flex-direction:column;gap:6px;margin-bottom:var(--space-3)}.sc__label{font-size:var(--font-size-base);color:var(--text-secondary)}.sc__req{color:var(--danger-500)}.sc__input,.sc__picker,.sc__search{border:1px solid var(--border-base);border-radius:var(--radius-md);background:var(--bg-card)}.sc__input,.sc__picker{padding:10px 12px;font-size:var(--font-size-base)}.sc__picker{display:flex;justify-content:space-between}.sc__search{display:flex;overflow:hidden}.sc__search input{flex:1;min-width:0;padding:9px 11px;font-size:var(--font-size-base)}.sc__search button{width:72px;border:0;border-left:1px solid var(--border-light);border-radius:0;background:var(--brand-primary);color:#fff;font-size:var(--font-size-base)}.sc__search button::after{border:none}.sc__textarea{box-sizing:border-box;width:100%;min-height:110px;padding:10px 12px;border:1px solid var(--border-base);border-radius:var(--radius-md);font-size:var(--font-size-base)}.sc__selected{display:flex;flex-direction:column;gap:7px;margin-bottom:var(--space-3);padding:10px 11px;border:1px solid var(--student-300,#93c5fd);border-radius:var(--radius-md);background:var(--student-50,#eff6ff);font-size:var(--font-size-base);color:var(--text-secondary)}.sc__compare{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:7px;color:var(--text-primary)}.sc__compare b{color:var(--student-600)}.sc__target-state{padding:var(--space-3);border:1px dashed var(--border-base);border-radius:var(--radius-md);text-align:center;font-size:var(--font-size-base);line-height:1.5;color:var(--text-tertiary)}.sc__targets{display:flex;flex-direction:column;gap:8px;margin-bottom:var(--space-3);max-height:360px;overflow:auto}.sc__target{display:flex;flex-direction:column;gap:5px;margin:0;padding:10px 11px;border:1px solid var(--border-light);border-radius:var(--radius-md);background:var(--bg-card);text-align:left;font-size:var(--font-size-base);line-height:1.45}.sc__target.is-selected{border-color:var(--student-500);background:var(--student-50,#eff6ff)}.sc__target text{color:var(--text-secondary)}.sc__target::after{border:none}.sc__impact{display:flex;flex-direction:column;gap:6px;padding:10px 11px;border-radius:var(--radius-md);background:var(--warning-50,#fffbeb);font-size:var(--font-size-base);line-height:1.55;color:var(--text-secondary)}.sc__history{padding:var(--space-3)}.sc__hist{display:flex;align-items:center;justify-content:space-between;gap:var(--space-2);padding:10px 0;border-bottom:1px solid var(--border-light)}.sc__hist>view{display:flex;min-width:0;flex-direction:column;gap:4px}.sc__hist b{font-size:var(--font-size-base)}.sc__hist text{font-size:var(--font-size-base);color:var(--text-tertiary)}.sc__hist button{flex-shrink:0;margin:0;padding:4px 10px;border:1px solid var(--danger-300);border-radius:var(--radius-md);background:var(--bg-card);color:var(--danger-600);font-size:var(--font-size-base);line-height:1.8}.sc__hist button::after{border:none}@media(max-width:360px){.sc__compare{grid-template-columns:1fr}.sc__compare b{justify-self:center;transform:rotate(90deg)}}
.sc__details-toggle{display:flex;align-items:center;justify-content:space-between;width:100%;min-height:44px;margin:8px 0 0;padding:0;background:transparent;border:0;color:var(--text-link);font-size:var(--font-size-base)}.sc__details-toggle::after{border:0}.sc__history>.card-title,.sc__empty{display:block}.sc__empty{margin-top:12px;font-size:var(--font-size-base);color:var(--text-secondary)}.sc__input,.sc__search input{height:44px;min-height:44px;box-sizing:border-box;padding-top:0;padding-bottom:0}.sc__picker{min-height:44px;box-sizing:border-box}.sc__impact{font-size:var(--font-size-base);line-height:1.65}</style>
