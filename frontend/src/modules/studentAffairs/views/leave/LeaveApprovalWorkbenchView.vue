<template>
  <ModulePageShell title="请假初审" subtitle="请假初审工作台 · 通过 / 驳回 / 退回重提（连续处理双栏）"
    :role-name="roleName" :data-scope-name="scopeHint">
    <div class="mp-stack">
      <div class="bar">
        <AppSearchBox v-model="keyword" placeholder="按学生姓名 / 学号搜索" @search="reload" />
      </div>

      <DualPaneWorkspace aside-title="待初审队列" :aside-count="total">
        <template #aside>
          <AppGlobalState :state="asideState" :description="asideDescription" loading-text="加载中…" @retry="load">
            <ul class="lv-list">
              <li v-for="r in filteredRows" :key="r.id">
                <button type="button" class="lv-item" :class="{ 'is-active': String(r.id) === selectedId }" @click="select(r.id)">
                  <div class="lv-item__row">
                    <span class="lv-item__name">{{ r.studentName }}</span>
                    <AppStatusTag :status="r.affairsStatus" :label="r.affairsStatusLabel" />
                  </div>
                  <div class="lv-item__sub">{{ r.studentNo }} · {{ r.className }}</div>
                  <div class="lv-item__sub">{{ fmt(r.startTime) }} ~ {{ fmt(r.endTime) }} · {{ r.leaveTypeLabel }} · {{ r.days }}天</div>
                </button>
              </li>
            </ul>
          </AppGlobalState>
        </template>

        <section class="mp-card lv-main">
          <template v-if="!selectedId">
            <EmptyState v-if="doneHint" title="本页待初审请假已全部处理"
              description="可翻页或切换筛选条件，继续处理其他请假" />
            <EmptyState v-else title="从左侧选择一条请假开始初审"
              description="通过后自动流转到下一审批节点；驳回为终态；退回后学生可修改重提" />
          </template>
          <AppGlobalState v-else :state="detailState" :description="detail.error" loading-text="详情加载中…" @retry="loadDetail(selectedId)">
            <div class="lv-main__body">
              <div class="lv-head">
                <span class="lv-head__name">{{ detail.data.studentName }}</span>
                <span class="mp-note">{{ detail.data.studentNo }} · {{ detail.data.className }}</span>
                <AppStatusTag :status="detail.data.affairsStatus" :label="detail.data.affairsStatusLabel" />
              </div>

              <div class="sec-t">请假信息</div>
              <AppDescriptionList :items="leaveItems" :columns="2" />

              <div class="sec-t">审批留痕</div>
              <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无处理记录" />
            </div>

            <div v-if="canAct" class="lv-foot">
              <AppPermissionButton :allowed="canBtn('studentAffairs.leave.approve')" code="studentAffairs.leave.approve" variant="ghost" danger @click="openReturn">退回重提</AppPermissionButton>
              <AppPermissionButton :allowed="canBtn('studentAffairs.leave.approve')" code="studentAffairs.leave.approve" variant="ghost" danger @click="openReject">驳回</AppPermissionButton>
              <AppPermissionButton :allowed="canBtn('studentAffairs.leave.approve')" code="studentAffairs.leave.approve" variant="primary" @click="openApprove">通过</AppPermissionButton>
            </div>
          </AppGlobalState>
        </section>
      </DualPaneWorkspace>
    </div>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      reason-label="意见" :reason-placeholder="cd.reasonPlaceholder"
      :submitting="cd.submitting" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
/**
 * 请假初审工作台（/admin/student-affairs/leave-approval）。
 * 覆盖 13A-05 状态机 §1 请假初审三节点：COUNSELOR_REVIEW/COLLEGE_REVIEW/STUDENT_AFFAIRS_REVIEW，
 * 真实对接 /student-affairs/leave/pending + /approve + /reject + /return。
 * 分角色浏览器测试发现：此前"请假审批"菜单项落地的是旧版 campus-service 接口，无法处理
 * 走新版工作流(affairs_status 非空)提交的请假，本页补齐初审这一步的真实页面。
 */
import { ModulePageShell, EmptyState } from '@/components/business'
import {
  AppStatusTag, AppConfirmDialog, AppPermissionButton, AppDescriptionList, AppAuditTrail,
  AppSearchBox, AppGlobalState
} from '@/components/common'
import DualPaneWorkspace from './components/DualPaneWorkspace.vue'
import { leaveApi } from '@/modules/studentAffairs/api/leave.api'
import { toast } from '@/utils/toast'
import { formatDateTime } from '@/utils/dateUtils'
import { canCode } from '@/modules/studentAffairs/composables/permission'


export default {
  name: 'LeaveApprovalWorkbenchView',
  components: {
    ModulePageShell, EmptyState, DualPaneWorkspace, AppStatusTag, AppConfirmDialog, AppPermissionButton,
    AppDescriptionList, AppAuditTrail, AppSearchBox, AppGlobalState
  },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      rows: [], total: 0, loading: false, error: '',
      keyword: '',
      selectedId: '', doneHint: false,
      detail: { loading: false, error: '', data: null },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false, reasonPlaceholder: '', submitting: false, submit: null }
    }
  },
  computed: {
    roleName() { return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || '辅导员 / 学院学工 / 学工处' },
    scopeHint() { return (this.ctx && this.ctx.dataScope && this.ctx.dataScope.name) || '按数据范围：仅轮到本人身份审批的节点' },
    filteredRows() {
      const k = (this.keyword || '').trim()
      if (!k) return this.rows
      return this.rows.filter((r) => (r.studentName || '').includes(k) || (r.studentNo || '').includes(k))
    },
    asideState() {
      if (this.loading) return 'loading'
      if (this.error) return 'error'
      return this.rows.length ? 'ready' : 'empty'
    },
    asideDescription() {
      if (this.error) return this.error
      if (!this.loading && !this.rows.length) return '当前暂无待你初审的请假'
      return ''
    },
    detailState() {
      if (this.detail.loading) return 'loading'
      if (this.detail.error) return 'error'
      return this.detail.data ? 'ready' : 'empty'
    },
    canAct() {
      const s = this.detail.data && this.detail.data.affairsStatus
      return ['COUNSELOR_REVIEW', 'COLLEGE_REVIEW', 'STUDENT_AFFAIRS_REVIEW'].includes(s)
    },
    leaveItems() {
      const d = this.detail.data || {}
      return [
        { label: '请假类型', value: d.leaveTypeLabel },
        { label: '天数', value: d.days },
        { label: '开始时间', value: this.fmt(d.startTime) },
        { label: '结束时间', value: this.fmt(d.endTime) },
        { label: '应返校时间', value: this.fmt(d.expectedReturnAt) },
        { label: '请假事由', value: d.reason || '—' },
        ...(d.returnReason ? [{ label: '退回意见', value: d.returnReason }] : [])
      ]
    },
    auditRecords() {
      return (this.detail.data && this.detail.data.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actor: t.operator, reason: t.detail, at: t.occurredAt
      }))
    }
  },
  created() { this.load() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    fmt(v) { return v ? formatDateTime(v) : '' },
    reload() { this.load() },
    async load() {
      this.loading = true; this.error = ''
      const res = await leaveApi.pending({ page: 1, pageSize: 100 })
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
    },
    select(id) {
      const sid = String(id)
      this.doneHint = false
      if (this.selectedId === sid) return
      this.selectedId = sid
      this.loadDetail(sid)
    },
    async loadDetail(id) {
      this.detail = { loading: true, error: '', data: null }
      const res = await leaveApi.detail(id)
      if (String(this.selectedId) !== String(id)) return
      this.detail.loading = false
      if (res.code !== 0) { this.detail.error = res.message || '详情加载失败'; return }
      this.detail.data = res.data
    },
    openApprove() {
      const id = this.detail.data.id
      this.cd = { visible: true, title: '请假通过', content: '通过后将流转到下一审批节点，或终审通过并通知学生。', danger: false, confirmText: '通过', requireReason: false, reasonPlaceholder: '', submitting: false, submit: (r) => leaveApi.approve(id, { comment: r || '' }) }
    },
    openReject() {
      const id = this.detail.data.id
      this.cd = { visible: true, title: '请假驳回', content: '驳回为终态，学生需重新发起申请。', danger: true, confirmText: '驳回', requireReason: true, reasonPlaceholder: '请填写驳回原因（不少于 5 字）', submitting: false, submit: (r) => leaveApi.reject(id, { reason: r }) }
    },
    openReturn() {
      const id = this.detail.data.id
      this.cd = { visible: true, title: '退回重提', content: '退回后学生可修改申请内容重新提交，重新进入首个审批节点。', danger: true, confirmText: '退回', requireReason: true, reasonPlaceholder: '请填写退回原因（不少于 5 字）', submitting: false, submit: (r) => leaveApi.returnForResubmit(id, { reason: r }) }
    },
    async onConfirm({ reason }) {
      this.cd.submitting = true
      const res = await this.cd.submit(reason || '')
      this.cd.submitting = false
      if (res.code !== 0) return toast.error(res.message || '操作失败')
      this.cd.visible = false
      toast.success('处理完成，已写审批留痕')
      await this.advance()
    },
    async advance() {
      const oldId = this.selectedId
      await this.load()
      const still = this.rows.find((r) => String(r.id) === String(oldId))
      if (still) { this.loadDetail(oldId); return }
      const next = this.rows[0]
      if (next) { this.select(next.id); return }
      this.selectedId = ''
      this.detail = { loading: false, error: '', data: null }
      this.doneHint = true
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.bar { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.sec-t { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); margin: var(--space-4) 0 var(--space-2); }

.lv-list { list-style: none; margin: 0; padding: var(--space-2); display: flex; flex-direction: column; gap: var(--space-1); }
.lv-item { display: block; width: 100%; text-align: left; font: inherit; cursor: pointer; background: transparent; border: 1px solid transparent; border-radius: var(--radius-md, 8px); padding: var(--space-2) var(--space-3); transition: background 0.12s ease, border-color 0.12s ease; }
.lv-item:hover { background: var(--primary-50, #eff6ff); }
.lv-item.is-active { background: var(--primary-50, #eff6ff); border-color: var(--primary-600, #2563eb); }
.lv-item__row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
.lv-item__name { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary); }
.lv-item__sub { margin-top: 2px; font-size: var(--font-size-xs); color: var(--text-tertiary); }

.lv-main { display: flex; flex-direction: column; min-height: 320px; }
.lv-main__body { flex: 1; padding: var(--space-4); min-width: 0; }
.lv-head { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.lv-head__name { font-size: var(--font-size-md, 15px); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.lv-foot { position: sticky; bottom: 0; display: flex; justify-content: flex-end; gap: var(--space-2); padding: var(--space-3) var(--space-4); border-top: 1px solid var(--border-light); background: var(--bg-card, #fff); }
</style>
