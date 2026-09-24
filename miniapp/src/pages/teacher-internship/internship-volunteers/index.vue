<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" :title="scope.groupId ? '学生志愿详情' : '岗位确认'" show-back />
    <view class="page-pad vg-wrap">
      <MobileGlobalState :state="state" :description="error" @retry="load">
        <template v-if="state === 'ready'">
          <view v-if="!scope.groupId" class="card vg-filters">
            <picker :range="context.batches.map(item => item.name)" :value="batchIndex" @change="changeBatch"><view class="vg-picker">{{ context.batches[batchIndex]?.name || '选择实习批次' }} · 切换</view></picker>
            <picker v-if="campaigns.length" :range="campaigns.map(item => item.name)" :value="campaignIndex" @change="changeCampaign"><view class="vg-picker">{{ campaign?.name }} · 招聘季</view></picker>
            <view class="vg-search"><input v-model="keyword" placeholder="学生姓名或学号" confirm-type="search" @confirm="search" /><button size="mini" @click="search">搜索</button></view>
            <view class="vg-tabs"><button v-for="item in filters" :key="item.value" :class="{active: scope.status === item.value}" @click="changeStatus(item.value)">{{ item.label }}</button></view>
          </view>
          <template v-if="!scope.groupId">
            <view v-if="!campaigns.length" class="card vg-empty">本指导批次暂无招聘季。</view>
            <template v-else><text class="vg-meta">{{ total }} 组志愿 · 拟接收及申请改志愿优先显示</text>
              <view v-if="!rows.length" class="card vg-empty">当前筛选下没有志愿记录。</view>
              <button v-for="row in rows" :key="row.id" class="card vg-row" @click="openGroup(row.id)">
                <view class="vg-heading"><text class="vg-name">{{ row.studentName }}</text><MobileStatusTag :label="label(row.status)" /></view>
                <text class="vg-meta">{{ row.studentNo }} · 第 {{ row.submissionVersion }} 次投递</text>
                <text v-if="row.unlockRequestedAt" class="vg-attention">学生申请调整志愿，请核对原因</text>
                <text v-else-if="row.lockExpired" class="vg-attention">学校确认已超时，请核对处置</text>
                <text v-else-if="row.teacherConfirmDeadline" class="vg-meta">确认截止 {{ fmt(row.teacherConfirmDeadline) }}</text>
                <text class="vg-link">核对志愿与材料</text>
              </button>
              <view v-if="total > 20" class="vg-paging"><button :disabled="scope.page <= 1" @click="turn(-1)">上一页</button><text>{{ scope.page }} / {{ Math.ceil(total / 20) }}</text><button :disabled="scope.page * 20 >= total" @click="turn(1)">下一页</button></view>
            </template>
          </template>
          <template v-else-if="detail">
            <button class="vg-return" :disabled="busy" @click="returnToList">返回原队列</button>
            <view class="card"><text class="vg-meta">{{ campaign?.name }}</text><view class="vg-heading"><text class="vg-name">{{ detail.studentName }}</text><MobileStatusTag :label="label(detail.status)" /></view><text class="vg-meta">{{ detail.studentNo }} · 第 {{ detail.submissionVersion }} 次投递</text><text class="vg-meta">指导教师：{{ detail.advisorName || '待分配' }}</text>
              <MobileInlineAlert v-if="detail.revisionReason && detail.status === 'NEEDS_REVISION'" type="warning" title="已退回补正" :description="detail.revisionReason" />
              <MobileInlineAlert v-if="detail.unlockRequestedAt" type="warning" title="学生申请调整志愿" :description="detail.unlockRequestReason || '请核对学生诉求'" />
            </view>
            <view class="card"><text class="vg-title">岗位志愿与企业意见</text>
              <view v-for="item in detail.volunteers" :key="item.id" class="vg-choice">
                <text class="vg-meta">第 {{ item.volunteerNo }} 志愿 · {{ item.currentSubmission ? '当前投递' : '非当前材料' }}</text>
                <text class="vg-title">{{ item.positionName }}</text><text class="vg-meta">{{ item.companyName }}</text><text class="vg-copy">{{ item.applicationStatement || '未填写岗位申请说明' }}</text>
                <text class="vg-meta">企业意见：{{ decisionLabel(item.enterpriseDecision?.status) }} · {{ effectLabel(item.enterpriseDecision?.effectStatus) }}</text>
                <text v-if="item.enterpriseDecision?.reason" class="vg-copy">{{ item.enterpriseDecision.reason }}</text>
              </view>
            </view>
            <view class="card"><text class="vg-title">本次冻结材料</text>
              <text v-if="!detail.material" class="vg-attention">缺少当前投递材料，不能确认岗位。</text>
              <template v-else><text class="vg-meta">第 {{ detail.material.submissionVersion }} 次投递 · {{ fmt(detail.material.createdAt) }}</text><text class="vg-copy">{{ materialProfile.selfIntro || '未填写自我介绍' }}</text><text v-if="materialProfile.strengths" class="vg-copy">{{ materialProfile.strengths }}</text>
                <view v-for="(item, index) in materialItems" :key="item.id || index" class="vg-choice"><text class="vg-title">{{ item.title || '材料条目' }}</text><text class="vg-copy">{{ item.description || '无补充说明' }}</text></view>
                <button v-for="(id, index) in detail.material.attachmentFileIds || []" :key="id" class="vg-file" @click="openFile(id)">查看投递附件 {{ index + 1 }}</button>
              </template>
            </view>
            <view class="card"><text class="vg-title">企业处理历史</text><text v-if="!detail.decisionHistory?.length" class="vg-meta">暂无企业处理记录。</text><view v-for="item in detail.decisionHistory || []" :key="item.id" class="vg-choice"><text class="vg-title">{{ historyPosition(item.applicationId) }}</text><text class="vg-meta">第 {{ item.submissionVersion }} 次投递 · {{ fmt(item.decidedAt) }}</text><text class="vg-copy">{{ decisionLabel(item.status) }} · {{ effectLabel(item.effectStatus) }}</text><text v-if="item.reason" class="vg-copy">{{ item.reason }}</text></view></view>
            <view v-if="canHandle" class="card vg-actions"><text class="vg-title">学校办理</text>
              <picker :range="choices.map(item => `${item.companyName} · ${item.positionName}`)" :value="selectedIndex" :disabled="busy" @change="selectedId = choices[Number($event.detail.value)]?.id || ''"><view class="vg-picker">{{ selected?.positionName || '选择要确认的岗位' }}</view></picker>
              <text v-if="confirmBlock" class="vg-attention">{{ confirmBlock }}</text>
              <button :disabled="busy || !!confirmBlock" class="vg-primary" @click="handle('confirm')">确认此岗位</button>
              <textarea v-model="reason" :disabled="busy" maxlength="500" placeholder="退回补正意见，写清需要补充什么（2–500字）" />
              <button :disabled="busy || reason.trim().length < 2" @click="handle('return')">退回学生补正</button>
              <text class="vg-meta">确认仅落实岗位，协议、保险及上岗核验仍需继续办理。</text>
            </view>
            <MobileInlineAlert v-else-if="!actionError" type="info" :description="context.can('internship.application.review') ? '当前状态无需办理，保留记录供核对。' : '当前身份仅可查看，无岗位确认或退回权限。'" />
            <MobileInlineAlert v-if="actionError" type="warning" :description="actionError" />
            <button class="vg-return" :disabled="busy" @click="load">重新读取最新记录</button>
          </template>
        </template>
      </MobileGlobalState>
    </view>
  </view>
</template>

<script>
import { useInternshipContextStore } from '@/stores/internshipContext'
import { teacherVolunteerApi } from '@/services/teacherVolunteerApi'
import { openBusinessFile } from '@/services/fileApi'

const base = '/pages/teacher-internship/internship-volunteers/index'
const filters = [{ value: 'PENDING', label: '待处理' }, { value: 'NEEDS_REVISION', label: '待补正' }, { value: 'APPROVED', label: '已确认' }, { value: 'ALL', label: '全部' }]
export default {
  data: () => ({ scope: { batchId: '', campaignId: '', groupId: '', status: 'PENDING', keyword: '', page: 1 }, state: 'loading', error: '', actionError: '', campaigns: [], rows: [], total: 0, detail: null, keyword: '', selectedId: '', reason: '', busy: false, sequence: 0, filters }),
  computed: {
    context() { return useInternshipContextStore() },
    batchIndex() { return Math.max(0, this.context.batches.findIndex(item => String(item.id) === this.scope.batchId)) },
    campaignIndex() { return Math.max(0, this.campaigns.findIndex(item => String(item.id) === this.scope.campaignId)) },
    campaign() { return this.campaigns.find(item => String(item.id) === this.scope.campaignId) },
    materialProfile() { return this.detail?.material?.profileSnapshot?.profile || {} },
    materialItems() { return this.detail?.material?.profileSnapshot?.items || [] },
    choices() { return (this.detail?.volunteers || []).filter(item => item.currentSubmission && item.positionAvailable && item.status === 'PENDING_REVIEW') },
    selected() { return this.choices.find(item => String(item.id) === String(this.selectedId)) },
    selectedIndex() { return Math.max(0, this.choices.findIndex(item => item.id === this.selectedId)) },
    canHandle() { return this.state === 'ready' && !this.actionError && this.context.can('internship.application.review') && ['SUBMITTED', 'LOCKED'].includes(this.detail?.status) && ['PREPARING', 'READY'].includes(this.detail?.recordStatus) && !this.detail?.positionId },
    confirmBlock() {
      const row = this.detail
      if (!this.canHandle) return '当前不可办理'
      if (!row.material) return '缺少当前投递材料'
      if (row.eligibilityStatus !== 'QUALIFIED') return '请先完成学生实习资格核验'
      if (!row.advisorUserId) return '请先分配校内指导教师'
      if (row.lockExpired) return '拟接收锁已超时，请先核对并退回修订'
      if (!this.selected) return '请选择当前有效的岗位志愿'
      if (row.status === 'LOCKED' && String(row.lockedApplicationId) !== this.selectedId) return '只能确认当前拟接收锁定的岗位'
      const decision = this.selected.enterpriseDecision
      if (row.enterpriseConfirmRequired && !(decision?.status === 'ACCEPT_INTENT' && decision.effectStatus === 'ACTIVE')) return '需要企业当前有效的拟接收意见'
      if (!this.campaign?.schoolConfirmStartAt || !this.campaign?.schoolConfirmEndAt) return '学校尚未配置确认窗口'
      const now = Date.now()
      if (!Number.isFinite(this.timestamp(this.campaign.schoolConfirmStartAt)) || !Number.isFinite(this.timestamp(this.campaign.schoolConfirmEndAt))) return '学校确认时间需要核对'
      if (this.campaign.status !== 'OPEN' || now < this.timestamp(this.campaign.schoolConfirmStartAt) || now > this.timestamp(this.campaign.schoolConfirmEndAt)) return '当前不在学校确认窗口'
      return ''
    }
  },
  onLoad(query) { this.applyQuery(query || {}) },
  onUnload() { this.sequence++ },
  watch: { '$route.fullPath'() { if (this.$route?.path === base) this.applyQuery(this.$route.query || {}) } },
  methods: {
    applyQuery(query) {
      const scope = { batchId: '', campaignId: '', groupId: '', status: 'PENDING', keyword: '', page: 1 }
      for (const key of ['batchId', 'campaignId', 'groupId']) {
        if (query[key] != null && query[key] !== '' && (typeof query[key] !== 'string' || !/^[1-9]\d*$/.test(query[key]))) { this.sequence++; this.detail = null; this.state = 'error'; this.error = '入口定位不完整，请返回工作台重新进入'; return }
        scope[key] = query[key] || ''
      }
      if (scope.groupId && (!scope.batchId || !scope.campaignId)) { this.sequence++; this.detail = null; this.state = 'error'; this.error = '学生详情必须包含原批次和招聘季'; return }
      scope.status = filters.some(item => item.value === query.status) ? query.status : 'PENDING'
      scope.keyword = typeof query.keyword === 'string' ? query.keyword.slice(0, 100) : ''
      scope.page = /^[1-9]\d*$/.test(String(query.page || '')) && Number.isSafeInteger(Number(query.page)) ? Number(query.page) : 1
      this.scope = scope; this.keyword = scope.keyword; this.load()
    },
    async load() {
      const sequence = ++this.sequence; this.state = 'loading'; this.error = ''; this.detail = null; this.rows = []; this.total = 0; this.actionError = ''; this.reason = ''; this.selectedId = ''
      try {
        await this.context.load(true)
        if (sequence !== this.sequence) return
        if (!this.context.can('internship.application.view')) { this.state = 'forbidden'; this.error = '当前身份没有正式志愿查看权限'; return }
        const batchId = String(this.scope.batchId || this.context.selectedBatchId || '')
        if (!batchId) { this.campaigns = []; this.state = 'ready'; return }
        if (!this.context.batches.some(item => String(item.id) === batchId)) throw new Error('该批次不在当前指导范围内')
        this.scope.batchId = batchId
        const data = await teacherVolunteerApi.campaigns(batchId)
        if (sequence !== this.sequence) return
        this.campaigns = data.items || []
        if (this.scope.campaignId && !this.campaigns.some(item => String(item.id) === this.scope.campaignId)) throw new Error('原招聘季不可访问，请返回队列核对')
        if (!this.scope.campaignId) this.scope.campaignId = String(this.campaigns[0]?.id || '')
        if (!this.scope.campaignId) { this.state = 'ready'; return }
        const scope = { ...this.scope }
        const result = scope.groupId ? await teacherVolunteerApi.detail(scope) : await teacherVolunteerApi.list(scope)
        if (sequence !== this.sequence) return
        if (scope.groupId) {
          if (String(result.id) !== scope.groupId || String(result.batchId) !== scope.batchId || String(result.campaignId) !== scope.campaignId) throw new Error('学生志愿与入口定位不一致')
          this.detail = result; this.selectedId = String(result.lockedApplicationId || '')
        } else { if (String(result.batchId) !== scope.batchId) throw new Error('队列批次不一致'); this.rows = result.items || []; this.total = result.total || 0 }
        this.state = 'ready'
      } catch (e) { if (sequence === this.sequence) { this.error = e.message || '暂时无法读取志愿'; this.state = 'error' } }
    },
    navigate(change) { const scope = { ...this.scope, ...change }; const query = Object.entries(scope).filter(([, value]) => value !== '').map(([key, value]) => `${key}=${encodeURIComponent(value)}`).join('&'); uni.redirectTo({ url: `${base}?${query}` }) },
    changeBatch(event) { this.navigate({ batchId: String(this.context.batches[Number(event.detail.value)]?.id || ''), campaignId: '', page: 1, groupId: '' }) },
    changeCampaign(event) { this.navigate({ campaignId: String(this.campaigns[Number(event.detail.value)]?.id || ''), page: 1, groupId: '' }) },
    changeStatus(status) { this.navigate({ status, page: 1 }) },
    search() { this.navigate({ keyword: this.keyword.trim(), page: 1 }) },
    turn(delta) { this.navigate({ page: this.scope.page + delta }) },
    openGroup(groupId) { this.navigate({ groupId: String(groupId) }) },
    returnToList() { this.navigate({ groupId: '' }) },
    timestamp(value) { return new Date(/(?:Z|[+-]\d\d:\d\d)$/.test(value || '') ? value : `${value}Z`).getTime() },
    fmt(value) { return value && Number.isFinite(this.timestamp(value)) ? new Date(this.timestamp(value)).toLocaleString('zh-CN', { hour12: false }) : '尚无记录' },
    label(value) { return ({ DRAFT: '草稿', SUBMITTED: '已投递', LOCKED: '企业拟接收', NEEDS_REVISION: '待学生补正', APPROVED: '学校已确认', CLOSED: '已关闭' })[value] || '状态待核对' },
    decisionLabel(value) { return ({ INTERESTED: '有意向', INTERVIEW: '邀请面试', ACCEPT_INTENT: '拟接收', REJECTED: '不接收', WITHDRAWN: '已撤回' })[value] || '暂无意见' },
    effectLabel(value) { if (!value) return '待处理'; if (value === 'ACTIVE' && this.detail?.status === 'NEEDS_REVISION') return '退回前意见'; return ({ ACTIVE: '当前有效', SUPERSEDED: '历史意见', EXPIRED: '已失效', CONSUMED: '已用于确认' })[value] || '历史记录' },
    historyPosition(id) { const item = this.detail?.volunteers?.find(row => String(row.id) === String(id)); return item ? `${item.companyName} · ${item.positionName}` : '历史岗位申请' },
    async openFile(id) { try { await openBusinessFile(id) } catch (e) { this.actionError = e.message || '材料暂时无法打开' } },
    async handle(action) {
      if (this.busy || !this.canHandle || (action === 'confirm' && this.confirmBlock) || (action === 'return' && this.reason.trim().length < 2)) return
      const sequence = this.sequence; const scope = { ...this.scope }; const row = this.detail
      const data = { expectedGroupVersion: row.version, expectedRecordVersion: row.recordVersion }
      if (action === 'confirm') Object.assign(data, { applicationId: this.selected.id, expectedApplicationVersion: this.selected.version })
      else data.reason = this.reason.trim()
      const content = action === 'confirm' ? `确认 ${row.studentName} 的岗位：${this.selected.companyName} · ${this.selected.positionName}？` : `将 ${row.studentName} 的本组志愿退回补正：${data.reason}`
      this.busy = true; this.actionError = ''
      try {
        const confirmed = await new Promise(resolve => uni.showModal({ title: action === 'confirm' ? '学校确认岗位' : '退回学生补正', content, success: result => resolve(result.confirm), fail: () => resolve(false) }))
        if (!confirmed || sequence !== this.sequence) return
        await teacherVolunteerApi[action](scope, data)
        if (sequence !== this.sequence) return
        await this.load()
      } catch (e) { if (sequence === this.sequence) this.actionError = `${e.message || '办理失败'}；请重新读取最新记录后核对。` }
      finally { this.busy = false }
    }
  }
}
</script>

<style scoped>
.vg-wrap{padding-bottom:calc(24px + env(safe-area-inset-bottom))}.vg-wrap .card{margin-bottom:16px}.vg-filters{display:grid;gap:12px}.vg-picker{min-height:44px;display:flex;align-items:center;color:var(--text-primary);font-size:14px}.vg-search{display:flex;align-items:center;gap:12px}.vg-search input{flex:1;min-width:0;font-size:14px}.vg-search button{margin:0}.vg-tabs{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}.vg-tabs button{padding:0;font-size:12px;min-height:44px;line-height:44px;margin:0}.vg-tabs .active{color:var(--brand-primary);background:var(--brand-light,#edf8f6)}.vg-row{display:block;width:100%;text-align:left;line-height:1.5;padding:20px;background:var(--bg-card,#fff)}.vg-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:8px 0}.vg-name{font-size:20px;font-weight:600}.vg-title{display:block;font-size:16px;font-weight:600;line-height:1.6;color:var(--text-primary)}.vg-meta,.vg-copy,.vg-attention,.vg-link{display:block;margin-top:8px;line-height:1.7}.vg-meta{font-size:12px;color:var(--text-tertiary)}.vg-copy{font-size:14px;color:var(--text-secondary);white-space:pre-wrap;overflow-wrap:anywhere}.vg-attention{font-size:13px;color:var(--warning,#956316)}.vg-link{font-size:13px;color:var(--brand-primary)}.vg-choice{padding-top:16px;margin-top:16px;border-top:1px solid var(--border-light)}.vg-empty{font-size:14px;color:var(--text-secondary)}.vg-paging{display:flex;align-items:center;justify-content:space-between;font-size:12px;gap:12px}.vg-paging button,.vg-return,.vg-file,.vg-actions button{font-size:14px;min-height:44px}.vg-return{margin-bottom:16px}.vg-file{margin-top:12px}.vg-actions textarea{box-sizing:border-box;width:100%;padding:12px;margin:20px 0 12px;min-height:104px;border:1px solid var(--border-light);border-radius:8px;font-size:14px}.vg-actions .vg-primary{margin-top:12px;background:var(--brand-primary);color:#fff}.vg-actions button[disabled]{opacity:.5}
</style>
