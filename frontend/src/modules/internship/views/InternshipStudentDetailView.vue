<template>
  <ModulePageShell
    :title="detail ? detail.name + ' · 实习详情' : '实习详情'"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn" @click="goBack">← 返回实习学生</button>
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <template v-else-if="detail">
      <section class="sd-summary mp-card">
        <div class="sd-summary__main">
          <div class="sd-summary__identity">
            <div>
              <span class="sd-summary__eyebrow">当前业务结论</span>
              <strong>{{ currentConclusion }}</strong>
              <p>{{ nextStepDescription }}</p>
            </div>
            <div class="sd-summary__tags">
              <AppStatusTag :type="detail.statusTone" dot>{{ detail.statusLabel }}</AppStatusTag>
              <AppStatusTag :type="eligTone(detail.eligibilityStatus)">{{ detail.eligibilityLabel }}</AppStatusTag>
              <span class="sd-dest">去向：{{ detail.destinationLabel }}</span>
            </div>
          </div>

          <div class="sd-summary__facts">
            <div><span>当前企业</span><strong>{{ detail.enterpriseName || '未落实' }}</strong></div>
            <div><span>当前岗位</span><strong>{{ detail.positionName || '未分配' }}</strong></div>
            <div><span>校内导师</span><strong>{{ detail.advisorName || '未指定' }}</strong></div>
            <div><span>实习时间</span><strong>{{ detail.internRange || '未设置' }}</strong></div>
          </div>
        </div>

        <div v-if="detail.status !== 'ARCHIVED' || detail.status === 'ASSESSING'" class="sd-actions">
          <div class="sd-actions__primary">
            <button v-if="statusAction" class="mp-btn mp-btn--primary" @click="askStatus(statusAction.action)">{{ statusAction.label }}</button>
            <button v-if="detail.status === 'ASSESSING'" class="mp-btn mp-btn--primary" @click="goArchive">前往归档中心</button>
            <button v-if="detail.status !== 'ARCHIVED'" class="mp-btn" @click="openAssign">{{ detail.positionId ? '调整岗位' : '分配岗位' }}</button>
          </div>
          <div class="sd-actions__secondary">
            <button v-if="detail.eligibilityStatus !== 'QUALIFIED' && detail.status !== 'ARCHIVED'" class="mp-btn" @click="askEligibility">认定资格合格</button>
            <button v-if="detail.positionId && detail.status !== 'ARCHIVED'" class="mp-btn mp-btn--danger-ghost" @click="askUnassign">退岗</button>
          </div>
        </div>
      </section>

      <div class="mp-grid-2 sd-panels">
        <section class="mp-card">
          <div class="mp-card__head">
            <div>
              <span class="mp-card__title">学生与实习信息</span>
              <p class="sd-card-note">用于核对身份、指导关系、实习周期和基础材料状态。</p>
            </div>
          </div>
          <div class="mp-card__body sd-grid">
            <div class="sd-kv"><span class="sd-k">姓名</span><span class="sd-v">{{ detail.name }}</span></div>
            <div class="sd-kv"><span class="sd-k">学号</span><span class="sd-v"><AppSensitiveText :value="detail.studentNo" type="generic" /></span></div>
            <div class="sd-kv"><span class="sd-k">班级</span><span class="sd-v">{{ detail.className }}</span></div>
            <div class="sd-kv"><span class="sd-k">联系电话</span><span class="sd-v">{{ detail.phone || '未登记' }}</span></div>
            <div class="sd-kv"><span class="sd-k">校内指导教师</span><span class="sd-v">{{ detail.advisorName || '未指定' }}</span></div>
            <div class="sd-kv"><span class="sd-k">实习起止</span><span class="sd-v">{{ detail.internRange || '—' }}</span></div>
            <div class="sd-kv"><span class="sd-k">实习保险</span><span class="sd-v" :class="{ 'sd-v--muted': !detail.insurance }">{{ detail.insurance || '未登记' }}</span></div>
            <div class="sd-kv"><span class="sd-k">三方协议</span><span class="sd-v" :class="{ 'sd-v--muted': !detail.agreement }">{{ detail.agreement || '未登记' }}</span></div>
            <div class="sd-kv sd-kv--full"><span class="sd-k">备注</span><span class="sd-v sd-v--wrap">{{ detail.remark || '—' }}</span></div>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head">
            <div>
              <span class="mp-card__title">企业、岗位与企业导师</span>
              <p class="sd-card-note">信息来自企业库和岗位库，调整岗位时不会在此页手工改写。</p>
            </div>
          </div>
          <div class="mp-card__body">
            <EmptyState v-if="!detail.positionId" title="尚未分配岗位" description="使用页面上方“分配岗位”，从已上架且未满员的岗位中选择。" />
            <div v-else class="sd-grid">
              <div class="sd-kv"><span class="sd-k">实习企业</span>
                <span class="sd-v sd-v--wrap"><a class="mp-link" @click="detail.enterpriseId && $router.push('/admin/internship/enterprises/' + detail.enterpriseId)">{{ detail.enterpriseName }}</a>
                  <span v-if="detail.company && detail.company.blacklist" class="sd-warn"> · 黑名单</span></span>
              </div>
              <div class="sd-kv"><span class="sd-k">实习岗位</span>
                <span class="sd-v sd-v--wrap"><a class="mp-link" @click="$router.push('/admin/internship/positions/' + detail.positionId)">{{ detail.positionName }}</a></span>
              </div>
              <div class="sd-kv"><span class="sd-k">企业导师</span><span class="sd-v">{{ detail.mentorName || '未指定' }}</span></div>
              <div class="sd-kv"><span class="sd-k">岗位容量</span><span class="sd-v">{{ detail.position ? detail.position.capacity : '—' }}</span></div>
              <div class="sd-kv sd-kv--full"><span class="sd-k">工作地点</span><span class="sd-v sd-v--wrap">{{ detail.position ? detail.position.workLocation : '—' }}</span></div>
            </div>
            <div v-if="!detail.positionId && detail.status !== 'ARCHIVED'" class="sd-dest-actions">
              <div>
                <strong>不走学校岗位库？</strong>
                <span>可按实际情况标记去向，但请先核对申请和证明材料。</span>
              </div>
              <div class="sd-dest-actions__buttons">
                <button class="mp-btn" @click="askDestination('SELF_ARRANGED')">标记自主实习</button>
                <button class="mp-btn" @click="askDestination('EXEMPTED')">标记免实习</button>
              </div>
            </div>
          </div>
        </section>
      </div>

      <section class="mp-card sd-audit">
        <div class="mp-card__head">
          <div>
            <span class="mp-card__title">操作留痕</span>
            <p class="sd-card-note">展示本学生岗位实习关键操作的时间、动作和经办人。</p>
          </div>
        </div>
        <div class="mp-card__body">
          <AppAuditTrail :records="auditRecords" empty-text="暂无操作记录" />
        </div>
      </section>
    </template>

    <AppDrawer v-model:visible="assignVisible" title="分配岗位" mode="modal" size="medium">
      <div class="ie-form">
        <div class="ie-intro">
          <strong>{{ detail?.name || '当前学生' }}</strong>
          <p>仅可选择已上架、企业非黑名单且尚未满员的岗位。提交后会更新学生去向与岗位占用。</p>
        </div>
        <div class="ie-fld ie-fld--full"><span class="ie-lbl">岗位 <i>*</i></span>
          <AppInternshipPositionPicker
            v-model="assignPositionId"
            placeholder="输入岗位或企业名称搜索"
            search-placeholder="按岗位名称 / 企业搜索"
            data-scope-hint="仅已上架、未满员岗位可选"
          />
        </div>
        <p v-if="assignError" class="ie-err">{{ assignError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="assignVisible = false">取消</button>
          <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting || !assignPositionId" @click="submitAssign">确认分配</button>
        </div>
      </div>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message"
      :type="confirm.type" :confirm-text="confirm.confirmText" :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel" :submitting="submitting" @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 实习学生详情：普通状态流只负责 READY/ONBOARD/ASSESS；归档统一进入正式归档中心。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSensitiveText, AppStatusTag, AppAuditTrail, AppInternshipPositionPicker } from '@/components/common'
import { AppDrawer } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { internStudentApi } from '@/modules/internship/api/internship-student.api'
import { toast } from '@/utils/toast'

const STATUS_NEXT = {
  PREPARING: { action: 'READY', label: '置为待上岗' },
  READY: { action: 'ONBOARD', label: '上岗' },
  ONBOARD: { action: 'ASSESS', label: '进入考核' }
}

export default {
  name: 'InternshipStudentDetailView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppSensitiveText, AppStatusTag, AppAuditTrail, AppDrawer, AppConfirmDialog, AppInternshipPositionPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', submitting: false, detail: null,
      assignVisible: false, assignPositionId: '', assignError: '',
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, extra: null }
    }
  },
  computed: {
    statusAction() { return this.detail && this.detail.status !== 'ARCHIVED' ? STATUS_NEXT[this.detail.status] : null },
    pageSubtitle() {
      if (!this.detail) return '加载中'
      const no = this.detail.studentNo
      const masked = no ? `${String(no).slice(0, -4)}**${String(no).slice(-2)}` : '—'
      return `${this.detail.className} · ${masked}`
    },
    currentConclusion() {
      if (!this.detail) return ''
      if (this.detail.status === 'ARCHIVED') return '该生实习已归档，当前以查看和追溯为主'
      if (this.detail.eligibilityStatus !== 'QUALIFIED') return '实习资格尚未认定合格，不能直接推进上岗'
      if (!this.detail.positionId && this.detail.destinationType === 'NONE') return '尚未落实实习岗位或其他去向'
      if (this.detail.status === 'PREPARING') return '前期信息已建立，下一步确认是否达到待上岗条件'
      if (this.detail.status === 'READY') return '学生处于待上岗阶段，下一步核对前置条件并办理上岗'
      if (this.detail.status === 'ONBOARD') return '学生正在岗实习，持续关注过程材料与风险'
      if (this.detail.status === 'ASSESSING') return '学生进入考核阶段，可核对成绩与归档材料'
      return `当前状态：${this.detail.statusLabel || this.detail.status}`
    },
    nextStepDescription() {
      if (!this.detail) return ''
      if (this.detail.status === 'ARCHIVED') return '查看企业、岗位和操作留痕；如需更正，请走对应业务流程。'
      if (this.detail.eligibilityStatus !== 'QUALIFIED') return '先完成实习资格认定，再分配岗位或标记真实去向。'
      if (!this.detail.positionId && this.detail.destinationType === 'NONE') return '分配已上架岗位，或根据真实情况标记自主实习/免实习。'
      if (this.detail.status === 'ASSESSING') return '进入归档中心核对材料、风险、报告和最终成绩。'
      if (this.statusAction) return `按业务进度执行“${this.statusAction.label}”，系统会继续校验对应前置条件。`
      return '查看下方基础信息与操作留痕，确认是否还有未闭环事项。'
    },
    auditRecords() {
      return (this.detail?.auditTrail || []).map((a, i) => ({
        id: i,
        action: a.action,
        actor: a.operator,
        at: a.occurredAt
      }))
    }
  },
  created() { this.load() },
  methods: {
    goBack() {
      const q = {}
      if (this.$route.query.batchId) q.batchId = this.$route.query.batchId
      else if (this.detail?.batchId) q.batchId = this.detail.batchId
      this.$router.push({ path: '/admin/internship/students', query: q })
    },
    goArchive() {
      this.$router.push({
        path: '/admin/internship/archive',
        query: {
          batchId: this.detail?.batchId || this.$route.query.batchId || '',
          internshipId: this.detail?.id || this.$route.params.id
        }
      })
    },
    eligTone(s) { return s === 'QUALIFIED' ? 'success' : (s === 'UNQUALIFIED' ? 'danger' : 'warning') },
    async load() {
      this.loading = true; this.error = ''
      const res = await internStudentApi.getStudentDetail(this.$route.params.id)
      if (res.code === 0) this.detail = res.data; else this.error = res.message
      this.loading = false
    },
    openAssign() {
      this.assignPositionId = ''; this.assignError = ''
      this.assignVisible = true
    },
    async submitAssign() {
      this.assignError = ''; this.submitting = true
      try {
        const res = await internStudentApi.assignPosition(this.detail.id, {
          positionId: this.assignPositionId,
          expectedVersion: this.detail.version
        })
        if (res.code === 0) { toast.success('已分配岗位'); this.assignVisible = false; this.load() } else this.assignError = res.message
      } finally { this.submitting = false }
    },
    askEligibility() {
      this.confirm = { visible: true, title: '实习资格认定', message: '确认该生实习资格合格？', type: 'primary', confirmText: '认定合格', requireReason: false, action: 'ELIG', extra: null }
    },
    askUnassign() {
      this.confirm = { visible: true, title: '退岗', message: '确认退岗？将释放该岗位名额。', type: 'warning', confirmText: '确认退岗', requireReason: true, reasonLabel: '退岗原因', action: 'UNASSIGN', extra: null }
    },
    async askStatus(action) {
      const m = STATUS_NEXT[this.detail.status]
      if (action === 'ONBOARD') {
        const res = await internStudentApi.getOnboardChecklist(this.detail.id)
        if (res.code === 0 && res.data && !res.data.canOnboard) {
          const miss = (res.data.blockers || []).join('；')
          return toast.error(miss ? `不能上岗，前置未完成：${miss}` : '不能上岗，前置条件未满足')
        }
      }
      this.confirm = { visible: true, title: m.label, message: `确认执行「${m.label}」？`, type: 'primary', confirmText: '确认', requireReason: false, action: 'STATUS', extra: action }
    },
    askDestination(dest) {
      const label = dest === 'SELF_ARRANGED' ? '自主实习' : '免实习'
      this.confirm = { visible: true, title: '标记去向 · ' + label, message: `确认将去向标记为「${label}」？`, type: 'primary', confirmText: '确认', requireReason: false, action: 'DEST', extra: dest }
    },
    async onConfirm({ reason } = {}) {
      const { action, extra } = this.confirm
      this.submitting = true
      try {
        let res
        if (action === 'ELIG') res = await internStudentApi.setEligibility(this.detail.id, { status: 'QUALIFIED', reason: reason || '' })
        else if (action === 'UNASSIGN') res = await internStudentApi.unassignPosition(this.detail.id, {
          reason: reason || '', expectedVersion: this.detail.version
        })
        else if (action === 'STATUS') res = await internStudentApi.setStatus(this.detail.id, { action: extra, reason: reason || '', expectedVersion: this.detail.version })
        else if (action === 'DEST') res = await internStudentApi.setDestination(this.detail.id, { destinationType: extra, expectedVersion: this.detail.version })
        if (res && res.code === 0) { toast.success('已更新并写入留痕'); this.confirm.visible = false; this.load() } else if (res) toast.error(res.message)
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.sd-summary{display:flex;flex-direction:column;gap:18px;padding:20px;margin-bottom:16px;border-color:var(--pri-200,#bfdbfe);background:var(--pri-50,#f8fbff)}.sd-summary__identity{display:flex;align-items:flex-start;justify-content:space-between;gap:20px}.sd-summary__identity>div:first-child{min-width:0}.sd-summary__eyebrow{display:block;font-size:12px;color:var(--t3,#64748b);margin-bottom:5px}.sd-summary__identity strong{display:block;font-size:18px;line-height:1.45;color:var(--t1,#0f1e3d)}.sd-summary__identity p{margin:7px 0 0;font-size:13px;line-height:1.6;color:var(--t2,#475569)}.sd-summary__tags{display:flex;align-items:center;justify-content:flex-end;flex-wrap:wrap;gap:8px;flex-shrink:0}.sd-dest{font-size:12px;color:var(--t2,#475569);padding:4px 9px;border-radius:999px;background:#fff;border:1px solid var(--line,#d9dee8)}.sd-summary__facts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:16px}.sd-summary__facts>div{min-width:0;padding:11px 12px;border-radius:8px;background:#fff;border:1px solid var(--line,#e5e9f0);display:flex;flex-direction:column;gap:4px}.sd-summary__facts span{font-size:11px;color:var(--t3,#64748b)}.sd-summary__facts strong{font-size:13px;color:var(--t1,#0f1e3d);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.sd-actions{display:flex;align-items:center;justify-content:space-between;gap:12px;padding-top:16px;border-top:1px solid var(--line,#d9dee8)}.sd-actions__primary,.sd-actions__secondary{display:flex;align-items:center;flex-wrap:wrap;gap:8px}.sd-actions__secondary{justify-content:flex-end}.sd-panels{align-items:stretch}.sd-card-note{margin:4px 0 0;font-size:12px;line-height:1.5;color:var(--t3,#64748b)}.sd-warn{color:var(--danger,#dc2626)}.sd-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px 22px}.sd-kv{display:flex;flex-direction:column;gap:4px;min-width:0}.sd-kv--full{grid-column:1/-1}.sd-k{font-size:12px;color:var(--t3,#64748b)}.sd-v{font-size:13px;line-height:1.55;color:var(--t1,#0f1e3d);min-width:0}.sd-v--muted{color:var(--t3,#64748b)}.sd-v--wrap{word-break:break-word;white-space:normal}.sd-dest-actions{margin-top:16px;padding:14px;border-radius:9px;background:var(--warning-50,#fff7ed);display:flex;align-items:center;justify-content:space-between;gap:16px}.sd-dest-actions>div:first-child{display:flex;flex-direction:column;gap:4px}.sd-dest-actions strong{font-size:13px;color:var(--t1,#0f1e3d)}.sd-dest-actions span{font-size:12px;line-height:1.5;color:var(--t2,#475569)}.sd-dest-actions__buttons{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:8px;flex-shrink:0}.sd-audit{margin-top:16px}.mp-btn{padding:8px 14px;border:1px solid var(--line,#d9dee8);border-radius:8px;background:#fff;cursor:pointer;font-size:13px;line-height:1.4;white-space:nowrap}.mp-btn:hover{border-color:var(--pri,#2563eb);color:var(--pri,#2563eb)}.mp-btn--primary{background:var(--pri,#2563eb);color:#fff;border-color:var(--pri,#2563eb)}.mp-btn--primary:hover{color:#fff}.mp-btn--danger-ghost{border-color:var(--danger-300,#fca5a5);color:var(--danger,#dc2626)}.mp-btn:disabled{opacity:.5;cursor:not-allowed}.ie-form{display:grid;grid-template-columns:1fr;gap:16px}.ie-intro{padding:12px 14px;border-radius:8px;background:var(--pri-50,#eff6ff)}.ie-intro strong{font-size:14px;color:var(--t1,#0f1e3d)}.ie-intro p{margin:5px 0 0;font-size:12px;line-height:1.55;color:var(--t2,#475569)}.ie-fld{display:flex;flex-direction:column;gap:6px}.ie-fld--full{grid-column:1/-1}.ie-lbl{font-size:12px;color:var(--t2,#475569)}.ie-lbl i{color:var(--danger,#dc2626);font-style:normal}.ie-err{color:var(--danger,#dc2626);font-size:12px;margin:0;padding:9px 11px;border-radius:7px;background:var(--danger-50,#fef2f2)}.ie-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:4px}@media(max-width:1100px){.sd-summary__facts{grid-template-columns:1fr 1fr}.sd-summary__identity{flex-direction:column}.sd-summary__tags{justify-content:flex-start}.sd-actions{align-items:flex-start;flex-direction:column}.sd-actions__secondary{justify-content:flex-start}}@media(max-width:720px){.sd-summary{padding:16px}.sd-summary__facts,.sd-grid{grid-template-columns:1fr}.sd-dest-actions{align-items:flex-start;flex-direction:column}.sd-dest-actions__buttons{justify-content:flex-start}.sd-actions__primary,.sd-actions__secondary{width:100%}.mp-btn{max-width:100%;white-space:normal}.sd-summary__facts strong{white-space:normal;word-break:break-word}}
</style>
