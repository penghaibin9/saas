<template>
  <view class="page-wrap">
    <MobileNavBar v-if="recordId" title="风险处置" :subtitle="risk ? risk.statusLabel : ''" back />
    <MobileGlobalState :state="state" :description="loadError" @retry="load">
      <view v-if="recordId && risk" class="page-pad stack-sm">
        <text class="risk-title">{{ risk.title }}</text>
        <text>{{ risk.realName }} · {{ risk.studentNo }}</text>
        <text>责任人：{{ risk.ownerName || risk.ownerLoginName || '未分派' }}</text>
        <text>{{ risk.detail }}</text>
        <text v-if="risk.sla?.dueAt">办理期限：{{ risk.sla.dueAt }}</text>
        <view v-for="entry in risk.handles || []" :key="entry.handleId" class="risk-history">
          <text>{{ actionLabel(entry.action) }} · {{ entry.operator }}</text><text>{{ entry.content }}</text>
        </view>
        <view v-if="can('PROCESS') || can('CLOSE')" class="stack-sm">
          <textarea v-model="note" maxlength="1000" placeholder="记录处置经过或关闭结论（至少5字）" />
          <button v-if="can('PROCESS')" :disabled="acting || note.trim().length < 5" @click="saveRisk('PROCESS')">记录处置</button>
          <button v-if="can('CLOSE')" :disabled="acting || note.trim().length < 5" @click="confirmClose">关闭风险</button>
        </view>
        <text v-if="loadError">{{ loadError }}</text>
        <text v-if="receipt">{{ receipt }}</text>
        <text v-if="!can('PROCESS') && !can('CLOSE') && risk.status !== 'CLOSED'">当前节点需按责任分工继续办理；转办、升级与接管请在PC风险工作区操作。</text>
        <button @click="returnToQueue">返回风险学生</button>
      </view>
      <view class="page-pad" v-if="!recordId && list">
        <!-- 风险概览 -->
        <view class="rk__summary card">
          <view class="rk__sum-item"><text class="rk__sum-val is-high">{{ counts.HIGH }}</text><text class="rk__sum-label">高风险</text></view>
          <view class="rk__sum-item"><text class="rk__sum-val is-mid">{{ counts.MEDIUM }}</text><text class="rk__sum-label">中风险</text></view>
          <view class="rk__sum-item"><text class="rk__sum-val">{{ total }}</text><text class="rk__sum-label">需关注</text></view>
        </view>

        <view class="rk__filters">
          <text class="rk__filter" :class="{ 'is-active': level === 'all' }" @click="level = 'all'">全部</text>
          <text class="rk__filter" :class="{ 'is-active': level === 'HIGH' }" @click="level = 'HIGH'">高风险</text>
          <text class="rk__filter" :class="{ 'is-active': level === 'MEDIUM' }" @click="level = 'MEDIUM'">中风险</text>
        </view>

        <view class="stack-sm">
          <MobileStudentCard
            v-for="s in list"
            :key="s.id"
            :name="s.name"
            :class-name="s.className"
            :major="s.major"
            :stage="s.stage"
            :current-task="s.task"
            :risk-level="s.risk"
            :pending-count="s.pending"
            :last-activity="s.last"
            @view="openStudent(s)"
          >
            <template #actions>
              <text class="rk__btn" @click.stop="contact(s)">联系</text>
              <text class="rk__btn is-primary" @click.stop="openStudent(s)">处理</text>
            </template>
          </MobileStudentCard>
          <view v-if="hasMore" class="rk__paging" @click="loadMore">
            {{ loadingMore ? '加载中…' : '上拉加载更多' }}
          </view>
          <view v-else class="rk__paging is-end">没有更多了</view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { realRequest } from '@/services/request'
import { affairsContractApi } from '@/services/affairsContractApi'
import { teacherApi } from '@/services/teacherApi'
import { ensureTeacherPerformanceApi } from '@/services/mobilePerformanceInstaller.teacher'
import { go } from '@/utils/nav'
const PAGE_SIZE = 20
ensureTeacherPerformanceApi()

export default {
  data() {
    return {
      recordId: '', risk: null, note: '', acting: false, receipt: '', loadError: '', focusEpoch: 0, list: [], state: 'loading', level: 'all', page: 1, hasMore: false,
      loadingMore: false, total: 0, counts: { HIGH: 0, MEDIUM: 0 }
    }
  },
  onLoad(q) {
    this.recordId = String(q?.recordId || ''); this._pageActive = true
    // #ifdef H5
    this._focusHashChange = () => this.syncFocusHash(window.location.hash)
    window.addEventListener('hashchange', this._focusHashChange)
    // #endif
    this.load({ reset: true })
  },
  onShow() { this._pageActive = true; if (this.recordId) this.loadRisk() },
  onHide() { this._pageActive = false; this._loadEpoch = (this._loadEpoch || 0) + 1 },
  onUnload() {
    this._pageActive = false; this._loadEpoch = (this._loadEpoch || 0) + 1; this.focusEpoch++
    // #ifdef H5
    if (this._focusHashChange) window.removeEventListener('hashchange', this._focusHashChange)
    // #endif
  },
  onReachBottom() { this.loadMore() },
  watch: {
    level() { this.load({ reset: true }) }
  },
  onPullDownRefresh() {
    this.load({ reset: true, done: () => uni.stopPullDownRefresh() })
  },
  methods: {
    can(action) { return Array.isArray(this.risk?.allowedActions) && this.risk.allowedActions.includes(action) },
    actionLabel(action) { return ({ ASSIGN: '分派', PROCESS: '处置', FOLLOW: '跟进', TRANSFER: '转办', ESCALATE: '升级', TAKEOVER: '接管', CLOSE: '关闭', REOPEN: '重开' })[action] || '办理记录' },
    returnToQueue() { uni.redirectTo({ url: '/pages/teacher/risk-students/index' }) },
    syncFocusHash(hash) {
      const [path, query = ''] = String(hash || '').replace(/^#/, '').split('?')
      if (path !== '/pages/teacher/risk-students/index') return
      const id = new URLSearchParams(query).get('recordId') || ''
      if (id === this.recordId) return
      this.recordId = id; this.risk = null; this.note = ''; this.receipt = ''; this.focusEpoch++
      return this.load()
    },
    async loadRisk() {
      const epoch = ++this.focusEpoch; this.state = 'loading'; this.loadError = ''
      try {
        if (!/^[1-9]\d*$/.test(this.recordId)) throw new Error('风险编号无效，请从待办重新进入')
        const row = await realRequest(`/mobile/teacher/affairs/risk/${this.recordId}`)
        if (epoch !== this.focusEpoch || !this._pageActive) return
        if (!row || String(row.riskId) !== this.recordId) throw new Error('风险记录不存在或不在当前权限范围内')
        this.risk = row; this.state = 'ready'
      } catch (e) { if (epoch !== this.focusEpoch) return; this.risk = null; this.state = 'error'; this.loadError = e.message || '风险记录加载失败' }
    },
    confirmClose() {
      if (this.acting || !this.can('CLOSE')) return
      const id = this.recordId, version = this.risk.version
      uni.showModal({ title: '确认关闭风险', content: '请确认处置已完成。关闭后将结束当前待办并通知学生。', success: result => {
        if (result.confirm && this.recordId === id && this.risk?.version === version) this.saveRisk('CLOSE')
      } })
    },
    async saveRisk(action) {
      if (this.acting || !['PROCESS', 'CLOSE'].includes(action) || !this.can(action) || this.note.trim().length < 5) return
      if (this.risk.version === undefined || this.risk.version === null) { this.loadError = '缺少记录版本，请刷新核对'; return }
      const id = this.recordId; this.acting = true; this.receipt = ''; this.loadError = ''
      try {
        if (action === 'CLOSE') await affairsContractApi.closeRisk(id, this.note.trim(), this.risk.version)
        else await affairsContractApi.processRisk(id, this.note.trim(), this.risk.version)
        if (this.recordId !== id) return
        this.note = ''; this.receipt = action === 'CLOSE' ? '风险已关闭，请核对下方办理记录。' : '处置已记录，可继续跟进。'; await this.loadRisk()
      } catch (e) { if (this.recordId === id) this.loadError = e.message || '保存失败，已保留填写内容；请核对最新状态后重试' }
      finally { this.acting = false }
    },
    loadMore() {
      if (!this.hasMore || this.loadingMore) return
      this.load({ reset: false })
    },
    load({ reset = true, done = null } = {}) {
      if (this.recordId) return this.loadRisk().finally(() => { if (done) done() })
      if (this._riskPromise) return this._riskPromise.finally(() => { if (done) done() })
      const requestedLevel = this.level
      const requestedPage = reset ? 1 : this.page + 1
      const epoch = (this._loadEpoch || 0) + 1
      this._loadEpoch = epoch
      if (reset) this.state = 'loading'
      else this.loadingMore = true
      const pending = teacherApi.getRiskStudentsPage(requestedLevel, requestedPage, PAGE_SIZE)
        .then((result) => {
          if (!this._pageActive || this._loadEpoch !== epoch || this.level !== requestedLevel) return result
          this.list = reset ? (result.list || []) : [...this.list, ...(result.list || [])]
          this.page = Number(result.page) || requestedPage
          this.hasMore = !!result.hasMore
          this.total = Number(result.total) || 0
          this.counts = result.counts || { HIGH: 0, MEDIUM: 0 }
          this.state = 'ready'
          return result
        })
        .catch((error) => {
          if (this._pageActive && this._loadEpoch === epoch && reset) this.state = 'error'
          throw error
        })
        .finally(() => {
          if (this._riskPromise === pending) this._riskPromise = null
          this.loadingMore = false
          if (done) done()
        })
      this._riskPromise = pending
      return pending
    },
    openStudent(student) { go('/pages/teacher/student-detail/index?id=' + student.id) },
    contact(student) { this.openStudent(student) }
  }
}
</script>

<style scoped>
.risk-title { font-weight: 600; font-size: 18px; }
.risk-history { display: flex; flex-direction: column; gap: 8px; border-top: 1px solid var(--border-base); padding: 12px 0; }
textarea { width: 100%; box-sizing: border-box; padding: 12px; background: var(--bg-card); border: 1px solid var(--border-base); border-radius: 8px; }
.rk__summary { display: flex; margin-bottom: var(--space-4); }
.rk__sum-item { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 3px; }
.rk__sum-val { font-size: var(--font-size-metric-sm); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.rk__sum-val.is-high { color: var(--danger-600); }
.rk__sum-val.is-mid { color: var(--warning-600); }
.rk__sum-label { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.rk__filters { display: flex; gap: var(--space-2); margin-bottom: var(--space-4); }
.rk__filter { padding: 5px 14px; border-radius: var(--radius-full); background: var(--bg-card); font-size: var(--font-size-sm); color: var(--text-secondary); border: 1px solid var(--border-base); }
.rk__filter.is-active { background: var(--teacher-600); color: #fff; border-color: var(--teacher-600); }
.rk__btn { font-size: var(--font-size-sm); color: var(--text-secondary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 5px 12px; }
.rk__btn.is-primary { color: #fff; background: var(--teacher-600); border-color: var(--teacher-600); }
.rk__paging { text-align: center; padding: var(--space-3) 0; font-size: var(--font-size-sm); color: var(--teacher-700); }
.rk__paging.is-end { color: var(--text-tertiary); }
</style>
