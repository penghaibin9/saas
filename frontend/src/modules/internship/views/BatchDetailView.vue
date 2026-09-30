<template>
  <ModulePageShell class="ix-batch-detail" :title="detail?.batchName || '批次详情'"
    :subtitle="detail ? [detail.batchNo, termText].filter(Boolean).join(' · ') : ''" watermark-purpose="实习批次管理">
    <template #actions>
      <AppButton variant="ghost" @click="goBack">返回批次列表</AppButton>
      <AppButton v-if="detail?.status === 'DRAFT' && canManage" variant="secondary" @click="goEdit">编辑批次</AppButton>
      <AppButton v-if="detail?.status === 'DRAFT' && canManage" variant="primary" @click="focusParticipants">配置名单并启用</AppButton>
    </template>
    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <template v-else-if="detail">
      <div class="bdv-identity">
        <AppStatusTag :type="statusTagType[detail.status] || 'default'" dot>{{ detail.statusLabel }}</AppStatusTag>
        <span>{{ dateShort(detail.startDate) }} 至 {{ dateShort(detail.endDate) }}</span>
        <span>实习档案 <strong>{{ detail.actualCount ?? '—' }}</strong> 人</span>
      </div>
      <nav class="bdv-tabs" aria-label="批次详情分区">
        <RouterLink v-for="tab in detailTabs" :key="tab.key" :to="sectionLocation(tab.key)"
          :class="{ 'is-active': activeSection === tab.key }"
          :aria-current="activeSection === tab.key ? 'page' : undefined">{{ tab.label }}</RouterLink>
      </nav>
      <div v-if="activeSection === 'overview'" class="bdv-overview">
        <section class="mp-card">
          <div class="mp-card__head"><h2 class="mp-card__title">本轮实习安排</h2></div>
          <div class="mp-card__body"><AppDescriptionList :items="infoItems" :columns="2" /></div>
        </section>
        <aside class="mp-card bdv-next">
          <div class="mp-card__head"><h2 class="mp-card__title">当前进度与下一步</h2></div>
          <div class="mp-card__body">
            <p class="bdv-next__text">{{ nextStep }}</p>
            <AppButton v-if="detail.status === 'DRAFT' && canManage" variant="primary" @click="focusParticipants">选择参与学生</AppButton>
            <AppButton v-else variant="secondary" @click="goStudents">查看学生与资格</AppButton>
            <AppDescriptionList v-if="transitionItems.length" :items="transitionItems" :columns="1" size="compact" />
            <p v-if="detail.transitionReason" class="bdv-reason">{{ detail.status === 'VOIDED' ? '作废原因' : '流转原因' }}：{{ detail.transitionReason }}</p>
            <div v-if="canManage && !isFinal" class="bdv-lifecycle">
              <span>批次管理</span>
              <AppButton v-if="detail.status === 'RUNNING'" variant="ghost" @click="openConfirm('close')">结束批次</AppButton>
              <AppButton v-if="detail.status === 'CLOSED'" variant="ghost" @click="openConfirm('archive')">归档批次</AppButton>
              <AppButton v-if="detail.status === 'DRAFT'" variant="ghost" @click="openConfirm('void')">作废草稿</AppButton>
            </div>
          </div>
        </aside>
      </div>
      <BatchParticipantScope v-show="activeSection === 'participants'" :key="detail.id" ref="participantScope"
        :batch-id="detail.id" :batch-status="detail.status" :readonly="!canManage" @frozen="load" />
      <div v-if="activeSection === 'rules'" class="bdv-overview">
        <section class="mp-card">
          <div class="mp-card__head"><h2 class="mp-card__title">业务规则</h2><AppButton v-if="detail.status === 'DRAFT' && canManage" variant="ghost" @click="goEdit">编辑规则</AppButton></div>
          <div class="mp-card__body">
            <dl v-if="rulesList.length" class="bdv-rule-list">
              <div v-for="rule in rulesList" :key="rule.label"><dt>{{ rule.label }}</dt><dd>{{ rule.value }}</dd></div>
            </dl>
            <p v-else class="mp-note">该批次未配置规则。</p>
            <p class="bdv-footnote">启用后的规则按原有生效范围执行，已形成的历史结果保留。</p>
          </div>
        </section>
        <section class="mp-card">
          <div class="mp-card__head"><h2 class="mp-card__title">阶段安排</h2></div>
          <div class="mp-card__body">
            <AppTimeline v-if="stageTimelineItems.length" :items="stageTimelineItems" />
            <p v-else class="mp-note">该批次未配置阶段时间轴。</p>
          </div>
        </section>
      </div>
      <section v-if="activeSection === 'history'" class="mp-card">
        <div class="mp-card__head"><h2 class="mp-card__title">操作记录</h2></div>
        <div class="mp-card__body"><AppAuditTrail :records="auditRecords" :show-ip="false" empty-text="暂无操作记录" /></div>
      </section>
    </template>
    <AppConfirmDialog v-model:visible="confirmVisible" :title="confirmConf.title" :message="confirmConf.message"
      :type="confirmConf.type" :confirm-text="confirmConf.confirmText" :require-reason="confirmConf.requireReason"
      :reason-label="confirmConf.reasonLabel || '操作原因（≥5 字）'" :submitting="confirmSubmitting" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
/**
 * 实习批次独立详情页（/admin/internship/batches/:id，路由由主流程挂载）。
 * 批次结束先读取真实 readiness；无阻断走普通结束，有阻断时只向校级管理员暴露后端已有的
 * force + forceReason 正式能力，原因与当时合规报告均由后端留痕，不绕过或放松 BATCH_CLOSE 闸门。
 */
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog, AppTimeline, AppAuditTrail, AppDescriptionList } from '@/components/common'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { batchLifecycleApi } from '@/modules/internship/api/batch-lifecycle.api'
import { toast } from '@/utils/toast'
import { formatDate, formatDateTime } from '@/utils/dateUtils'
import BatchParticipantScope from './components/BatchParticipantScope.vue'
import { withInternshipBatch, internshipBatchListReturn } from '../navigation.js'
import { useInternshipBatchStore } from '@/stores/internshipBatch'

const ACTION_LABEL = { CREATE: '新建批次', UPDATE: '编辑批次', ACTIVATE: '启用批次', CLOSE: '结束批次', ARCHIVE: '归档批次', VOID: '作废批次' }

export default {
  name: 'BatchDetailView',
  components: {
    ModulePageShell, LoadingState, ErrorState, AppButton,
    AppStatusTag, AppConfirmDialog, AppTimeline, AppAuditTrail, AppDescriptionList,
    BatchParticipantScope
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
      closeReadiness: null,
      loadSequence: 0,
      statusTagType: { DRAFT: 'default', RUNNING: 'success', CLOSED: 'info', ARCHIVED: 'default', VOIDED: 'danger' }
    }
  },
  computed: {
    detailTabs() { return [
      { key: 'overview', label: '批次概况' }, { key: 'participants', label: '参与名单' },
      { key: 'rules', label: '阶段与规则' }, { key: 'history', label: '操作记录' }
    ] },
    activeSection() {
      const value = this.$route.query.setup
      return this.detailTabs.some((tab) => tab.key === value) ? value : 'overview'
    },
    nextStep() {
      const messages = {
        DRAFT: '核对实习时间与规则后，选择参与班级或学生。预览名单无误，再冻结名单并启用批次。',
        RUNNING: '本批次已启用。请继续核对学生参与资格与待安置情况；学生满足各项上岗条件后再进入实习过程。',
        CLOSED: '本批次已结束。核对结项材料和学生结果，满足归档条件后完成归档。',
        ARCHIVED: '本批次已归档，历史名单、规则与处理记录可在授权范围内查看。',
        VOIDED: '本批次已作废，保留原有信息与操作记录供核对。'
      }
      return messages[this.detail?.status] || '请核对当前批次信息。'
    },
    canManage() { return this.ctx?.permissionActions?.createBatch?.allowed === true },
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
      if (r.checkin) out.push({ label: '考勤打卡', value: `${r.checkin.requireDaily ? '每日必打卡' : '不强制每日打卡'}；电子围栏 ${r.checkin.geofenceRadiusM ?? '—'} 米；最大定位误差 ${r.checkin.maxAccuracyM ?? 200} 米` })
      if (r.weeklyReport) {
        const day = ['', '周一', '周二', '周三', '周四', '周五', '周六', '周日'][r.weeklyReport.deadlineWeekday]
        out.push({ label: '实习周报', value: `${r.weeklyReport.frequency === 'WEEKLY' ? '每周 1 次' : '每两周 1 次'}；正文至少 ${r.weeklyReport.minWordCount ?? '—'} 字${day ? `；${day}前提交` : ''}` })
      }
      if (r.guidance) out.push({ label: '指导巡访', value: `每学期现场巡访至少 ${r.guidance.minVisitsPerTerm ?? '—'} 次；每月沟通至少 ${r.guidance.minCommunicationsPerMonth ?? '—'} 次` })
      if (r.evaluation) out.push({ label: '评价权重', value: `企业 ${this.pct(r.evaluation.enterpriseWeight)} / 教师 ${this.pct(r.evaluation.teacherWeight)} / 自评 ${this.pct(r.evaluation.selfWeight)}` })
      if (r.score) out.push({ label: '成绩评定', value: `及格线 ${r.score.passThreshold ?? '—'} 分；${(r.score.components || []).map((c) => `${c.name} ${this.pct(c.weight)}`).join(' + ')}` })
      if (r.onboard) {
        const checks = [['requireAgreement', '三方协议生效'], ['requireInsurance', '保险核验'], ['requireAdvisor', '分配校内指导教师']]
        out.push({ label: '上岗前置', value: checks.map(([key, label]) => `${label}：${r.onboard[key] === true ? '必需' : r.onboard[key] === false ? '不要求' : '未配置'}`).join('；') })
      }
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
        action: t.action,
        actionLabel: ACTION_LABEL[t.action] || (t.action ? '业务操作' : '—'),
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
      if (this.confirmMode === 'close') {
        return {
          title: '结束批次',
          message: `将「${name}」置为「已结束」，结束后才可归档。`,
          type: 'danger', confirmText: '确认结束', requireReason: false
        }
      }
      if (this.confirmMode === 'force-close') {
        const blocked = Number(this.closeReadiness?.blocked || 0)
        return {
          title: '强制结束批次',
          message: `当前有 ${blocked} 名学生存在结束阻断。确需结束请填写不少于 5 字原因；系统会保留本次就绪检查与强制结束事实。`,
          type: 'danger', confirmText: '确认强制结束', requireReason: true,
          reasonLabel: '强制结束原因（≥5 字）'
        }
      }
      if (this.confirmMode === 'archive') {
        return {
          title: '归档批次', message: `归档「${name}」后进入只读台账，不可再变更。`,
          type: 'danger', confirmText: '确认归档', requireReason: false
        }
      }
      if (this.confirmMode === 'void') {
        return {
          title: '作废批次', message: `作废「${name}」（仅草稿态可作废，可审计）。`,
          type: 'danger', confirmText: '确认作废', requireReason: true,
          reasonLabel: '作废原因（≥5 字）'
        }
      }
      return { title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false }
    }
  },
  watch: {
    '$route.params.id'(id, oldId) {
      if (!id || id === oldId) return
      this.detail = null
      this.closeReadiness = null
      this.confirmVisible = false
      this.load()
      this.focusHeading()
    }
  },
  created() {
    internshipApi.getContext().then((res) => {
      if (res.code === 0) this.ctx = res.data
    })
    this.load()
  },
  mounted() { this.focusHeading() },
  beforeUnmount() { this.loadSequence++ },
  methods: {
    focusHeading() {
      this.$nextTick(() => {
        const heading = this.$el?.querySelector('h1')
        if (!heading) return
        heading.setAttribute('tabindex', '-1')
        heading.style.scrollMarginTop = '170px'
        heading.focus({ preventScroll: true })
        heading.scrollIntoView({ block: 'start', behavior: 'instant' })
      })
    },
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
      this.$router.push(internshipBatchListReturn(this.$route.query, this.detail?.id || this.$route.query.batchId))
    },
    goEdit() {
      const location = withInternshipBatch(`/admin/internship/batches/${this.detail.id}/edit`, this.detail.id)
      location.query.returnTo = this.$route.query.returnTo
      location.query.setup = this.activeSection
      this.$router.push(location)
    },
    sectionLocation(section) {
      return { path: this.$route.path, query: { ...this.$route.query, batchId: this.detail.id, setup: section } }
    },
    goStudents() {
      this.$router.push(withInternshipBatch('/admin/internship/students', this.detail.id))
    },
    async focusParticipants() {
      await this.$router.replace(this.sectionLocation('participants'))
      await this.$nextTick()
      this.$refs.participantScope?.focus()
    },
    async load() {
      const sequence = ++this.loadSequence
      this.loading = true
      this.error = ''
      this.detail = null
      const id = this.$route.params.id
      try {
        const res = await internshipApi.getBatchDetail(id)
        if (sequence !== this.loadSequence || id !== this.$route.params.id) return
        if (res.code !== 0 || !res.data) throw new Error(res.message || '批次不存在或无权查看')
        this.detail = res.data
        const store = useInternshipBatchStore()
        const cached = store.availableBatches.find((batch) => String(batch.id) === String(this.detail.id))
        if (cached) {
          for (const key of ['status', 'batchName', 'batchNo', 'startDate', 'endDate']) cached[key] = this.detail[key]
          if (String(store.selectedBatchId) === String(this.detail.id)) store.applyBatch(cached)
        }
      } catch (error) {
        if (sequence === this.loadSequence) this.error = error.message || '批次加载失败，请重试'
      } finally {
        if (sequence === this.loadSequence) this.loading = false
      }
    },
    async openConfirm(mode) {
      if (!this.canManage) return
      if (mode === 'close') {
        const res = await batchLifecycleApi.getReadiness(this.detail.id)
        if (!res || res.code !== 0) {
          toast.error((res && res.message) || '无法读取批次结束就绪检查')
          return
        }
        this.closeReadiness = res.data || null
        this.confirmMode = Number(res.data?.blocked || 0) > 0 ? 'force-close' : 'close'
        this.confirmVisible = true
        return
      }
      this.confirmMode = mode
      this.confirmVisible = true
    },
    async onConfirm(payload) {
      if (!this.canManage) return
      const d = this.detail
      if (!d) return
      const reason = (payload && payload.reason) || ''
      this.confirmSubmitting = true
      let res
      if (this.confirmMode === 'close') {
        res = await batchLifecycleApi.close(d.id, { expectedVersion: d.version })
      } else if (this.confirmMode === 'force-close') {
        res = await batchLifecycleApi.close(d.id, {
          expectedVersion: d.version,
          force: true,
          forceReason: reason
        })
      } else if (this.confirmMode === 'archive') {
        res = await internshipApi.archiveBatch(d.id, { expectedVersion: d.version })
      } else if (this.confirmMode === 'void') {
        res = await internshipApi.voidBatch(d.id, { reason, expectedVersion: d.version })
      }
      this.confirmSubmitting = false
      if (res && res.code === 0) {
        toast.success('操作成功')
        this.confirmVisible = false
        this.closeReadiness = null
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

.bdv-identity { display: flex; align-items: center; flex-wrap: wrap; gap: 12px 22px; color: var(--t2); font-size: 13px; }
.bdv-identity strong { color: var(--t1); }
.bdv-tabs { display: flex; gap: 24px; border-bottom: 1px solid var(--card-b); overflow-x: auto; }
.bdv-tabs a { color: var(--t2); text-decoration: none; padding: 8px 2px; border-bottom: 2px solid transparent; white-space: nowrap; font-size: 13px; }
.bdv-tabs a.is-active { color: var(--pri); border-color: var(--pri); font-weight: 600; }
.bdv-overview { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(260px, 1fr); gap: 16px; align-items: start; }
.bdv-overview h2, .ix-batch-detail h2 { margin: 0; font-size: 14px; }
.bdv-next__text { margin: 0 0 16px; color: var(--t2); line-height: 1.85; font-size: 13px; }
.bdv-lifecycle { display: flex; align-items: center; gap: 12px; border-top: 1px solid var(--card-b); padding-top: 12px; margin-top: 20px; color: var(--t3); font-size: 12px; }
.bdv-footnote { color: var(--t3); line-height: 1.7; font-size: 12px; margin: 18px 0 0; }
.bdv-rules li { padding: 10px 0; line-height: 1.75; border-bottom: 1px solid var(--card-b); }
.bdv-rules li:last-child { border: 0; }
.bdv-rule-list { margin: 0; }
.bdv-rule-list > div { display: grid; grid-template-columns: 82px minmax(0, 1fr); gap: 16px; padding: 15px 0; border-bottom: 1px solid var(--card-b); font-size: 13px; line-height: 1.8; }
.bdv-rule-list > div:first-child { padding-top: 0; }
.bdv-rule-list > div:last-child { border-bottom: 0; padding-bottom: 0; }
.bdv-rule-list dt { color: var(--t2); font-weight: 600; }
.bdv-rule-list dd { margin: 0; color: var(--t2); overflow-wrap: anywhere; }
@media (max-width: 1120px) { .bdv-overview { grid-template-columns: 1fr; } }

</style>
