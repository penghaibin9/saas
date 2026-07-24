<template>
  <ModulePageShell
    :title="detail ? `${detail.batchName} · 批次详情` : '实习批次详情'"
    :subtitle="detail ? [detail.batchNo, termText].filter(Boolean).join(' · ') : ''"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="实习批次管理"
  >
    <template #actions>
      <AppButton variant="ghost" @click="goBack">← 返回批次列表</AppButton>
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else-if="detail" class="mp-grid-2">
      <!-- 左：批次信息 + 阶段时间轴 + 规则配置 -->
      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">批次信息</span>
            <AppStatusTag :type="statusTagType[detail.status] || 'default'" dot>{{ detail.statusLabel }}</AppStatusTag>
          </div>
          <div class="mp-card__body">
            <AppDescriptionList :items="infoItems" :columns="2" />
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">阶段时间轴</span></div>
          <div class="mp-card__body">
            <AppTimeline v-if="stageTimelineItems.length" :items="stageTimelineItems" />
            <p v-else class="mp-note" style="margin: 0">该批次未配置阶段时间轴。</p>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">规则配置</span></div>
          <div class="mp-card__body">
            <ul v-if="rulesList.length" class="bdv-rules">
              <li v-for="(line, i) in rulesList" :key="i">{{ line }}</li>
            </ul>
            <p v-else class="mp-note" style="margin: 0">该批次未配置规则。</p>
          </div>
        </section>
      </div>

      <!-- 右：状态与操作 + 操作留痕 -->
      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">状态与操作</span></div>
          <div class="mp-card__body">
            <div class="bdv-status">
              <span class="bdv-status__lbl">当前状态</span>
              <AppStatusTag :type="statusTagType[detail.status] || 'default'" dot>{{ detail.statusLabel }}</AppStatusTag>
            </div>
            <AppDescriptionList v-if="transitionItems.length" :items="transitionItems" :columns="1" size="compact" />
            <p v-if="detail.transitionReason" class="bdv-reason">作废原因：{{ detail.transitionReason }}</p>
            <div class="bdv-actions">
              <AppButton v-if="detail.status === 'DRAFT'" variant="secondary" @click="goEdit">编辑</AppButton>
              <AppButton v-if="detail.status === 'DRAFT'" variant="primary" @click="openConfirm('activate')">启用</AppButton>
              <AppButton v-if="detail.status === 'RUNNING'" variant="danger" @click="openConfirm('close')">结束</AppButton>
              <AppButton v-if="detail.status === 'CLOSED'" variant="danger" @click="openConfirm('archive')">归档</AppButton>
              <AppButton v-if="detail.status === 'DRAFT'" variant="danger" @click="openConfirm('void')">作废</AppButton>
            </div>
            <p v-if="isFinal" class="mp-note" style="margin: var(--space-2) 0 0">
              批次已处于终态（{{ detail.statusLabel }}），仅可查看，不可再变更。
            </p>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">操作留痕</span></div>
          <div class="mp-card__body">
            <AppAuditTrail :records="auditRecords" :show-ip="false" empty-text="暂无操作记录" />
          </div>
        </section>
      </div>
    </div>

    <!-- 启用 / 结束 / 归档 / 作废 二次确认（沿用列表页文案与 reason 规则） -->
    <AppConfirmDialog
      v-model:visible="confirmVisible"
      :title="confirmConf.title"
      :message="confirmConf.message"
      :type="confirmConf.type"
      :confirm-text="confirmConf.confirmText"
      :require-reason="confirmConf.requireReason"
      reason-label="作废原因（≥5 字）"
      :submitting="confirmSubmitting"
      @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 实习批次独立详情页（/admin/internship/batches/:id，路由由主流程挂载）。
 * 原列表页详情抽屉收口至此：批次信息 + 阶段时间轴 + 规则配置 + 状态动作（启用/结束/归档/作废）
 * + 编辑入口（仅 DRAFT）+ 审计留痕。状态流转全部走真实 internshipApi，越权与非法状态由后端拦截。
 */
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog, AppTimeline, AppAuditTrail, AppDescriptionList } from '@/components/common'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { toast } from '@/utils/toast'
import { formatDate, formatDateTime } from '@/utils/dateUtils'

const ACTION_LABEL = { CREATE: '新建批次', UPDATE: '编辑批次', ACTIVATE: '启用批次', CLOSE: '结束批次', ARCHIVE: '归档批次', VOID: '作废批次' }

export default {
  name: 'BatchDetailView',
  components: {
    ModulePageShell, LoadingState, ErrorState, AppButton,
    AppStatusTag, AppConfirmDialog, AppTimeline, AppAuditTrail, AppDescriptionList
  },
  data() {
    return {
      ctx: null,
      loading: true,
      error: '',
      detail: null,
      confirmVisible: false,
      confirmMode: '',
      confirmSubmitting: false,
      statusTagType: { DRAFT: 'default', RUNNING: 'success', CLOSED: 'info', ARCHIVED: 'default', VOIDED: 'danger' }
    }
  },
  computed: {
    roleName() {
      return this.ctx?.currentRole?.roleName || ''
    },
    dataScopeName() {
      return this.ctx?.dataScope?.name || ''
    },
    termText() {
      const d = this.detail
      if (!d) return ''
      return [d.academicYear, d.term].filter(Boolean).join(' · ')
    },
    infoItems() {
      const d = this.detail
      if (!d) return []
      return [
        { label: '批次编号', value: d.batchNo || '—' },
        { label: '学年学期', value: this.termText || '—' },
        { label: '实习起止', value: `${this.dateShort(d.startDate) || '—'} ~ ${this.dateShort(d.endDate) || '—'}` },
        { label: '报名窗口', value: `${this.dateShort(d.signupStartDate) || '—'} ~ ${this.dateShort(d.signupEndDate) || '—'}` },
        { label: '计划 / 实际人数', value: `${d.plannedCount} / ${d.actualCount}` },
        { label: '备注', value: d.remark || '—' },
        { label: '创建时间', value: this.dateTime(d.createTime) },
        { label: '更新时间', value: this.dateTime(d.updateTime) }
      ]
    },
    stageTimelineItems() {
      const stages = (this.detail && this.detail.stages) || []
      return stages.map((s) => ({
        id: s.code,
        title: s.name,
        type: 'primary',
        time: (s.startDate || s.endDate)
          ? `${this.dateShort(s.startDate) || '—'} ~ ${this.dateShort(s.endDate) || '—'}`
          : '未设置具体日期'
      }))
    },
    rulesList() {
      const r = this.detail && this.detail.rules
      if (!r) return []
      const out = []
      if (r.checkin) out.push(`打卡：${r.checkin.requireDaily ? '每日必打卡' : '不强制每日'}，电子围栏 ${r.checkin.geofenceRadiusM} 米`)
      if (r.weeklyReport) out.push(`周报：${r.weeklyReport.frequency === 'WEEKLY' ? '每周 1 次' : '每两周 1 次'}，正文 ≥ ${r.weeklyReport.minWordCount} 字，周${r.weeklyReport.deadlineWeekday}前提交`)
      if (r.guidance) out.push(`指导：每学期现场巡访 ≥ ${r.guidance.minVisitsPerTerm} 次，每月沟通 ≥ ${r.guidance.minCommunicationsPerMonth} 次`)
      if (r.evaluation) out.push(`评价权重：企业 ${this.pct(r.evaluation.enterpriseWeight)} / 教师 ${this.pct(r.evaluation.teacherWeight)} / 自评 ${this.pct(r.evaluation.selfWeight)}`)
      if (r.score) out.push(`成绩：及格线 ${r.score.passThreshold} 分，构成 ${(r.score.components || []).map((c) => `${c.name} ${this.pct(c.weight)}`).join(' + ')}`)
      return out
    },
    transitionItems() {
      const d = this.detail
      if (!d) return []
      const items = []
      if (d.lastTransitionAt || d.lastTransitionBy) {
        items.push({ label: '最近流转', value: `${d.lastTransitionBy || '—'} · ${this.dateTime(d.lastTransitionAt)}` })
      }
      if (d.archiveBatchNo) {
        items.push({ label: '归档批次号', value: `${d.archiveBatchNo}（${d.archivedBy || '—'} · ${this.dateTime(d.archivedAt)}）` })
      }
      return items
    },
    auditRecords() {
      const trail = (this.detail && this.detail.auditTrail) || []
      return trail.map((t) => ({
        id: t.id,
        action: ACTION_LABEL[t.action] || t.action,
        actor: t.operator,
        at: t.time,
        reason: t.detail
      }))
    },
    isFinal() {
      return ['ARCHIVED', 'VOIDED'].includes(this.detail?.status)
    },
    confirmConf() {
      const name = this.detail ? this.detail.batchName : ''
      if (this.confirmMode === 'activate') {
        return { title: '启用批次', message: `将「${name}」置为「进行中」，实习流程正式开放。`, type: 'primary', confirmText: '确认启用', requireReason: false }
      }
      if (this.confirmMode === 'close') {
        return { title: '结束批次', message: `将「${name}」置为「已结束」，结束后才可归档。`, type: 'danger', confirmText: '确认结束', requireReason: false }
      }
      if (this.confirmMode === 'archive') {
        return { title: '归档批次', message: `归档「${name}」后进入只读台账，不可再变更。`, type: 'danger', confirmText: '确认归档', requireReason: false }
      }
      if (this.confirmMode === 'void') {
        return { title: '作废批次', message: `作废「${name}」（仅草稿态可作废，可审计）。`, type: 'danger', confirmText: '确认作废', requireReason: true }
      }
      return { title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false }
    }
  },
  watch: {
    '$route.params.id'(id, oldId) {
      if (!id || id === oldId) return
      this.detail = null
      this.load()
    }
  },
  created() {
    internshipApi.getContext().then((res) => {
      if (res.code === 0) this.ctx = res.data
    })
    this.load()
  },
  methods: {
    dateShort(v) {
      return formatDate(v, '')
    },
    dateTime(v) {
      return formatDateTime(v)
    },
    pct(v) {
      return `${Math.round((v || 0) * 100)}%`
    },
    goBack() {
      // 从列表进入时走历史返回（保留筛选/页码/panel）；深链直入时兜底到列表
      const back = this.$router.options.history.state && this.$router.options.history.state.back
      if (typeof back === 'string' && back.startsWith('/admin/internship/batches')) this.$router.back()
      else this.$router.push('/admin/internship/batches')
    },
    goEdit() {
      this.$router.push(`/admin/internship/batches/${this.detail.id}/edit`)
    },
    async load() {
      this.loading = true
      this.error = ''
      const id = this.$route.params.id
      const res = await internshipApi.getBatchDetail(id)
      if (id !== this.$route.params.id) return
      this.loading = false
      if (res.code !== 0) {
        this.error = res.message || '批次不存在或无权查看'
        return
      }
      this.detail = res.data
    },
    openConfirm(mode) {
      this.confirmMode = mode
      this.confirmVisible = true
    },
    async onConfirm(payload) {
      const d = this.detail
      if (!d) return
      const reason = (payload && payload.reason) || ''
      this.confirmSubmitting = true
      let res
      if (this.confirmMode === 'activate') res = await internshipApi.activateBatch(d.id, { expectedVersion: d.version })
      else if (this.confirmMode === 'close') res = await internshipApi.closeBatch(d.id, { expectedVersion: d.version })
      else if (this.confirmMode === 'archive') res = await internshipApi.archiveBatch(d.id, { expectedVersion: d.version })
      else if (this.confirmMode === 'void') res = await internshipApi.voidBatch(d.id, reason)
      this.confirmSubmitting = false
      if (res && res.code === 0) {
        toast.success('操作成功')
        this.confirmVisible = false
        await this.load()
      } else {
        toast.error((res && res.message) || '操作失败')
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.bdv-rules {
  margin: 0;
  padding-left: var(--space-5);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.bdv-status {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: var(--space-3);
  margin-bottom: var(--space-3);
  border-bottom: 1px dashed var(--border-light);
}
.bdv-status__lbl {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.bdv-reason {
  margin: var(--space-3) 0 0;
  padding: var(--space-2) var(--space-3);
  background: var(--danger-50, #fef2f2);
  color: var(--danger-700, #b91c1c);
  border-radius: 8px;
  font-size: var(--font-size-sm);
}
.bdv-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-3);
}
</style>
