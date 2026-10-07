<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="在校服务待处理" subtitle="请假审批与学生服务申请" show-back />
    <view>
      <view class="page-pad">
        <view class="tabs" role="tablist">
          <button class="tab" :class="{ active: activeTab === 'leave' }" @click="activeTab = 'leave'">请假待审</button>
          <button class="tab" :class="{ active: activeTab === 'workorder' }" @click="switchWorkOrders">服务工单<text v-if="workTotal" class="tab__count">{{ workTotal }}</text></button>
        </view>

        <template v-if="activeTab === 'leave'">
          <MobileGlobalState :state="state" @retry="load">
          <MobileGlobalState v-if="!leaveList.length" state="empty" title="暂无待审批请假" description="学生提交的请假申请会在这里出现。" />
          <template v-else>
            <view class="cs__hint">请假审批、退回、销假和续假均在统一审批中心按正式状态机办理。</view>
            <view class="stack">
              <view v-for="x in leaveList" :key="x.id" class="card cs">
                <view class="row-between"><view class="flex-1"><view class="row" style="gap:6px;"><text class="t-md t-bold">{{ x.name || '—' }}</text><text class="cs__type">{{ x.typeLabel || x.type }}</text></view><text class="cs__sub">{{ x.className || '' }}<text v-if="x.code"> · {{ x.code }}</text></text></view><MobileStatusTag :label="x.statusLabel || x.status" type="warning" /></view>
                <view class="cs__period" v-if="x.startTime"><text class="cs__period-k">起止</text><text class="flex-1 t-sm">{{ (x.startTime || '').slice(5, 16) }} ~ {{ (x.endTime || '').slice(5, 16) }}</text></view>
                <view class="cs__reason" v-if="x.reason"><text class="cs__reason-k">事由</text><text class="flex-1 t-sm">{{ x.reason }}</text></view>
              </view>
            </view>
            <view class="cs__foot"><button class="btn btn-primary" @click="goApproval">前往审批中心处理</button></view>
          </template>
          </MobileGlobalState>
        </template>

        <template v-else>
          <view v-if="!selected" class="work-search"><input v-model.trim="keyword" placeholder="搜索学生姓名或申请事项" confirm-type="search" @confirm="searchWorkOrders" /><button class="work-search__button" @click="searchWorkOrders">搜索</button></view>
          <view v-if="!selected && !detailLoading">
          <MobileGlobalState v-if="workState === 'loading' && !workList.length" state="loading" />
          <MobileGlobalState v-else-if="!['ready', 'loading'].includes(workState)" :state="workState === 'idle' ? 'loading' : workState" title="服务工单暂时无法加载" :description="workError" @retry="searchWorkOrders" />
          <MobileGlobalState v-else-if="!workList.length" state="empty" title="暂无服务工单" description="学生的服务申请会在这里进入处理队列。" />
          <template v-else>
            <view class="cs__hint">工单只展示你当前数据范围内的学生；处理说明会写入正式审计轨迹。</view>
            <view class="stack"><view v-for="x in workList" :key="x.id" class="card cs cs--tap" @click="openWorkOrder(x)"><view class="row-between"><view class="flex-1"><text class="t-md t-bold">{{ x.title || '服务申请' }}</text><text class="cs__sub">{{ x.name || '学生' }}{{ x.className ? ' · ' + x.className : '' }}</text></view><MobileStatusTag :label="x.statusLabel || x.status" :type="workStatusType(x.status)" /></view><text class="cs__reason-text">{{ x.detail || '未填写补充说明' }}</text><text class="cs__apply">提交于 {{ formatTime(x.createTime) }} · 点击查看并处理</text></view></view>
            <button v-if="workList.length < workTotal" class="btn btn-secondary cs__more" :loading="workState === 'loading'" @click="loadMoreWorkOrders">加载更多</button>
          </template>
          </view>
          <MobileGlobalState v-if="detailLoading" state="loading" />

          <view v-if="selected && selected.order" class="card work-detail">
            <button class="btn btn-secondary" :disabled="submitting" @click="selected = null">返回工单列表</button>
            <view class="row-between"><text class="t-lg t-bold">处理服务申请</text><MobileStatusTag :label="selected.order.statusLabel || selected.order.status" :type="workStatusType(selected.order.status)" /></view>
            <view class="work-detail__line"><text>学生</text><text>{{ selected.order.name || selected.student?.name || '—' }}{{ selected.order.className ? ' · ' + selected.order.className : '' }}</text></view>
            <view class="work-detail__line"><text>申请事项</text><text>{{ selected.order.title || '—' }}</text></view>
            <view class="work-detail__body"><text>学生说明</text><text>{{ selected.order.detail || '未填写补充说明' }}</text></view>
            <view v-if="selected.order.allowedActions && selected.order.allowedActions.includes('handle')" class="work-detail__form"><textarea v-model.trim="actionNote" :disabled="submitting" maxlength="300" placeholder="填写处理说明（至少5字），学生可在“我的办理”查看" auto-height /><view class="work-detail__actions"><button class="btn btn-secondary" :disabled="submitting" @click="submitWorkOrder(false)">更新进度</button><button class="btn btn-primary" :loading="submitting" :disabled="submitting" @click="submitWorkOrder(true)">办结并通知学生</button></view></view>
            <view v-else class="cs__hint">{{ selected.order.actionHint || '当前工单仅可查看' }}</view>
            <view v-if="selected.order.trail && selected.order.trail.length" class="work-trail"><view v-for="(entry, index) in selected.order.trail" :key="index" class="work-trail__item"><text class="work-trail__title">{{ entry.title || '处理记录' }}</text><text>{{ entry.desc || '' }}</text><text class="work-trail__time">{{ formatTime(entry.time) }}</text></view></view>
          </view>
        </template>
      </view>
    </view>
  </view>
</template>

<script>
import { normalizeError, safeToast, toastError } from '@/services/request'
import { teacherApi } from '@/services/teacherApi'
import { go } from '@/utils/nav'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'

export default {
  data() { return { state: 'loading', leaveList: [], activeTab: 'leave', keyword: '', workList: [], workTotal: 0, workPage: 1, workState: 'idle', workError: '', selected: null, actionNote: '', submitting: false, pageDisposed: false, loadSeq: 0, workSeq: 0, detailSeq: 0, detailLoading: false } },
  onLoad() { this.session = currentSessionGeneration(); this.load() },
  onShow() {
    if (this.session !== undefined && this.session !== currentSessionGeneration()) {
      this.session = currentSessionGeneration(); this.workSeq++; this.detailSeq++
      this.leaveList = []; this.workList = []; this.workTotal = 0; this.selected = null; this.actionNote = ''; this.submitting = false; this.detailLoading = false; this.workState = 'idle'
      this.load()
    }
  },
  onUnload() { this.pageDisposed = true; this.loadSeq++; this.workSeq++; this.detailSeq++ },
  onPullDownRefresh() { this.load(() => uni.stopPullDownRefresh()) },
  methods: {
    isCurrent(session) { return !this.pageDisposed && session === currentSessionGeneration() },
    async load(done) {
      const session = currentSessionGeneration(), seq = ++this.loadSeq
      if (this.activeTab === 'workorder') { await this.loadWorkOrders(); if (done) done(); return }
      this.state = 'loading'
      try { const d = await teacherApi.getCampusServicePending(); if (this.isCurrent(session) && seq === this.loadSeq) { this.leaveList = (d && d.list) || []; this.state = 'ready' } }
      catch (error) { if (this.isCurrent(session) && seq === this.loadSeq) this.state = normalizeError(error).pageState || 'error' }
      finally { if (done) done() }
    },
    goApproval() { go('/pages/teacher/approval/index') },
    switchWorkOrders() { this.activeTab = 'workorder'; if (this.workState === 'idle') return this.loadWorkOrders() },
    searchWorkOrders() { this.selected = null; this.detailSeq++; this.detailLoading = false; return this.loadWorkOrders(1, true) },
    loadMoreWorkOrders() { if (this.workState !== 'loading') return this.loadWorkOrders(this.workPage + 1, false) },
    async loadWorkOrders(page = 1, replace = true) {
      const session = currentSessionGeneration(), seq = ++this.workSeq
      this.workState = 'loading'; this.workError = ''
      try {
        const d = await teacherApi.getCampusWorkOrders({ page, pageSize: 20, keyword: this.keyword || undefined })
        if (!this.isCurrent(session) || seq !== this.workSeq) return
        if (!Array.isArray(d?.list)) throw new Error('工单列表未完整加载，请重试')
        this.workList = replace ? d.list : [...this.workList, ...d.list]; this.workTotal = Number(d.total) || 0; this.workPage = page; this.workState = 'ready'
      } catch (error) { if (this.isCurrent(session) && seq === this.workSeq) { const normalized = normalizeError(error); this.workError = normalized.text; this.workState = normalized.pageState || 'error' } }
    },
    async openWorkOrder(row) {
      const session = currentSessionGeneration(), seq = ++this.detailSeq
      this.selected = null; this.detailLoading = true
      try {
        const detail = await teacherApi.getCampusWorkOrderDetail(row.id)
        if (!this.isCurrent(session) || seq !== this.detailSeq) return
        if (!detail?.order) throw new Error('工单详情未完整加载，请重试')
        this.selected = detail; this.actionNote = ''
      } catch (e) { if (this.isCurrent(session) && seq === this.detailSeq) toastError(e) }
      finally { if (this.isCurrent(session) && seq === this.detailSeq) this.detailLoading = false }
    },
    async submitWorkOrder(close) {
      if (this.submitting) return
      const note = (this.actionNote || '').trim(); if (note.length < 5) { safeToast('处理说明至少填写5个字'); return }
      const order = this.selected && this.selected.order; if (!order || order.version === undefined || order.version === null) { safeToast('记录已变化，请重新打开后处理'); return }
      if (!order.allowedActions?.includes(close ? 'complete' : 'handle')) { safeToast(order.actionHint || '当前身份不能处理此工单'); return }
      const session = currentSessionGeneration(), seq = this.detailSeq
      this.submitting = true
      try {
        await teacherApi.handleCampusWorkOrder(order.id, { note, close, version: order.version })
        if (!this.isCurrent(session)) return
        // 写入已经成功；回读失败也不能继续使用旧版本提交。
        if (seq !== this.detailSeq) return
        this.selected = null; this.detailLoading = true; this.actionNote = ''
        safeToast(close ? '工单已办结，学生可查看处理结果' : '处理进度已更新')
        try {
          const detail = await teacherApi.getCampusWorkOrderDetail(order.id)
          if (!this.isCurrent(session) || seq !== this.detailSeq) return
          if (!detail?.order) throw new Error('处理已保存，详情未完整加载，请重新打开工单查看')
          this.selected = detail
        } catch (e) { if (this.isCurrent(session) && seq === this.detailSeq) toastError(e) }
        if (this.isCurrent(session) && seq === this.detailSeq) await this.loadWorkOrders(1, true)
      } catch (e) { if (this.isCurrent(session)) toastError(e) }
      finally { if (this.isCurrent(session)) { this.submitting = false; if (seq === this.detailSeq) this.detailLoading = false } }
    },
    workStatusType(status) { return status === 'COMPLETED' ? 'success' : status === 'CLOSED' ? 'default' : status === 'PROCESSING' ? 'primary' : 'warning' },
    formatTime(value) { return value ? String(value).replace('T', ' ').slice(0, 16) : '—' }
  }
}
</script>

<style scoped>
.tabs { display:flex; gap:var(--space-2); margin-bottom:var(--space-3); }.tab { flex:1; border:0; background:var(--fill-light); color:var(--text-secondary); padding:10px 8px; border-radius:var(--radius-md); font-size:var(--font-size-sm); }.tab.active { background:var(--teacher-50); color:var(--teacher-700); font-weight:600; }.tab__count { margin-left:4px; color:inherit; }
.cs__hint { font-size:var(--font-size-xs); color:var(--text-tertiary); padding:0 var(--space-1) var(--space-2); }.cs { display:flex; flex-direction:column; gap:var(--space-2); }.cs--tap { cursor:pointer; }.cs__type { font-size:10px; color:var(--teacher-700); background:var(--teacher-50); padding:1px 6px; border-radius:var(--radius-sm); }.cs__sub,.cs__apply { display:block; font-size:var(--font-size-xs); color:var(--text-tertiary); margin-top:2px; }.cs__period,.cs__reason { display:flex; gap:var(--space-3); }.cs__period-k,.cs__reason-k { font-size:var(--font-size-sm); color:var(--text-tertiary); width:40px; flex-shrink:0; }.cs__reason-text { font-size:var(--font-size-sm); color:var(--text-secondary); line-height:1.6; }.cs__foot,.cs__more { margin-top:var(--space-4); }
.work-search { display:flex; gap:var(--space-2); margin-bottom:var(--space-3); background:var(--fill-light); padding:8px 10px; border-radius:var(--radius-md); }.work-search input { flex:1; min-width:0; font-size:var(--font-size-sm); }.work-search__button { border:0; background:transparent; color:var(--teacher-700); font-size:var(--font-size-sm); }.work-detail { margin-top:var(--space-4); display:flex; flex-direction:column; gap:var(--space-3); }.work-detail__line { display:flex; justify-content:space-between; gap:var(--space-3); font-size:var(--font-size-sm); }.work-detail__line text:first-child,.work-detail__body text:first-child { color:var(--text-tertiary); flex-shrink:0; }.work-detail__body { display:flex; flex-direction:column; gap:4px; font-size:var(--font-size-sm); line-height:1.6; }.work-detail__form textarea { width:100%; min-height:84px; box-sizing:border-box; background:var(--fill-light); border-radius:var(--radius-md); padding:10px; font-size:var(--font-size-sm); }.work-detail__actions { display:flex; gap:var(--space-2); margin-top:var(--space-2); }.work-detail__actions button { flex:1; font-size:var(--font-size-sm); }.work-trail { border-top:1px solid var(--border-light); padding-top:var(--space-2); }.work-trail__item { display:flex; flex-direction:column; gap:3px; padding:var(--space-2) 0; font-size:var(--font-size-xs); color:var(--text-secondary); }.work-trail__title { color:var(--text-primary); font-weight:600; }.work-trail__time { color:var(--text-tertiary); }
</style>
