<template>
  <ModulePageShell class="isd" :title="detail ? detail.name + ' · 实习档案' : '实习档案'" :subtitle="pageSubtitle">
    <template #actions><button class="mp-btn" @click="goBack">{{ volunteerReturnTo ? '返回岗位确认' : /^\/admin\/internship\/insurance(?:\/\d+)?(?:\?|$)/.test(String($route.query.returnTo || '')) ? '返回保险材料' : /^\/admin\/internship\/assignment-logs(?:\?|$)/.test(String($route.query.returnTo || '')) ? '返回分配记录' : /^\/admin\/internship\/compliance(?:\?|$)/.test(String($route.query.returnTo || '')) ? '返回上岗核验' : '返回名单' }}</button></template>
    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <template v-else-if="detail">
      <div class="isd-identity"><AppStatusTag :type="detail.statusTone" dot>{{ detail.statusLabel }}</AppStatusTag><span>{{ detail.batchName || '批次信息待补充' }}</span><span>校内指导教师 · {{ detail.advisorName || '待分配' }}</span></div>
      <nav class="isd-sections" aria-label="学生实习档案分区">
        <RouterLink v-for="item in sections" :key="item.key" :to="sectionLocation(item.key)" :class="{ 'is-active': activeSection === item.key }" :aria-current="activeSection === item.key ? 'page' : undefined">{{ item.label }}</RouterLink>
      </nav>
      <div v-show="activeSection === 'profile'" class="isd-layout">
        <section class="mp-card">
          <div class="mp-card__head"><h2 class="isd-title">学生与实习信息</h2></div>
          <dl class="isd-facts">
            <div><dt>姓名</dt><dd>{{ detail.name }}</dd></div>
            <div><dt>学号</dt><dd><AppSensitiveText :value="detail.studentNo" type="generic" /></dd></div>
            <div><dt>班级</dt><dd>{{ detail.className || '待补充' }}</dd></div>
            <div><dt>联系电话</dt><dd>{{ detail.phone || '未登记' }}</dd></div>
            <div><dt>实习批次</dt><dd>{{ detail.batchName || '待补充' }}</dd></div>
            <div><dt>实习时间</dt><dd>{{ detail.internRange || '待安排' }}</dd></div>
            <div><dt>校内指导教师</dt><dd>{{ detail.advisorName || '待分配' }}</dd></div>
            <div><dt>实习去向</dt><dd>{{ detail.destinationLabel }}</dd></div>
            <div class="isd-facts__wide"><dt>备注</dt><dd>{{ detail.remark || '暂无备注' }}</dd></div>
          </dl>
        </section>
        <aside class="mp-card isd-next">
          <span class="isd-kicker">当前进度</span><h2>{{ currentConclusion }}</h2><p>{{ nextStepDescription }}</p>
          <RouterLink v-if="detail.eligibilityStatus !== 'QUALIFIED'" class="mp-btn mp-btn--primary" :to="sectionLocation('eligibility')">{{ canReview ? '办理资格审核' : '查看资格结果' }}</RouterLink>
          <button v-else-if="statusAction && canManage" class="mp-btn mp-btn--primary" :disabled="submitting || onboardLoading" @click="askStatus(statusAction.action)">{{ statusAction.label }}</button>
          <button v-if="detail.status === 'ASSESSING' && canArchive" class="mp-btn" @click="goArchive">前往归档中心</button>
          <RouterLink class="mp-link" :to="sectionLocation('placement')">查看岗位与去向 →</RouterLink>
        </aside>
      </div>
      <div v-show="activeSection === 'eligibility'" class="isd-layout">
        <section class="mp-card isd-review">
          <div class="mp-card__head"><div><h2 class="isd-title">资格审核</h2><p class="sd-card-note">依据学校要求核对学生资格，保存认定结果及后续安排。</p></div></div>
          <form v-if="canReview" class="isd-review__form" @submit.prevent="askEligibility">
            <fieldset :disabled="submitting || reviewConflict"><legend>本次认定结果</legend>
              <label v-for="item in eligibilityOptions" :key="item.value" class="isd-choice" :class="{ 'is-selected': reviewForm.status === item.value }">
                <input v-model="reviewForm.status" type="radio" name="eligibility-result" :value="item.value" /><span><strong>{{ item.label }}</strong><small>{{ item.hint }}</small></span>
              </label>
            </fieldset>
            <label class="isd-field">认定说明 <span>选填 · 保存后向该学生展示</span>
              <textarea v-model="reviewForm.reason" rows="3" :disabled="submitting || reviewConflict" placeholder="说明核对结果；需要补充时，写清补充事项和后续安排。" />
            </label>
            <div v-if="reviewError" role="alert" class="isd-error">{{ reviewError }}<button v-if="reviewConflict" type="button" class="mp-link" @click="refreshReview">核对最新记录并保留草稿</button></div>
            <div class="isd-review__footer"><span>结果会记录到此学生的处理记录</span><button class="mp-btn mp-btn--primary" type="submit" :disabled="submitting || !reviewForm.status || reviewConflict">保存认定</button></div>
          </form>
          <div v-else class="isd-readonly"><h3>{{ isReadonly ? '当前档案仅可查看' : '当前身份可查看资格结果' }}</h3><p>{{ isReadonly ? '已结束、归档或作废的实习不能在此修改资格。' : '资格认定由具备审核权限的经办人办理。' }}</p></div>
        </section>
        <aside class="mp-card isd-result">
          <span class="isd-kicker">已保存的认定结果</span><AppStatusTag :type="eligTone(detail.eligibilityStatus)">{{ detail.eligibilityLabel }}</AppStatusTag>
          <p class="isd-result__reason">{{ detail.eligibilityReview?.reason || '暂无认定说明' }}</p>
          <p v-if="detail.eligibilityReview?.reviewedAt" class="sd-card-note">认定时间 · {{ formatDateTime(detail.eligibilityReview.reviewedAt) }}</p>
          <p v-if="detail.eligibilityReview?.reason" class="sd-card-note">{{ detail.eligibilityReview.studentVisible ? '该说明已向学生展示' : '历史内部说明，仅教师可见' }}</p>
          <div class="isd-note">资格合格后，继续落实实习岗位，并按本批次要求完成上岗手续。</div>
          <RouterLink class="mp-link" :to="sectionLocation('history')">查看历次处理记录 →</RouterLink>
        </aside>
      </div>
      <div v-show="activeSection === 'placement'" class="isd-placement-actions">
        <button v-if="canManage && ['PREPARING', 'READY'].includes(detail.status)" class="mp-btn" :disabled="onboardLoading || submitting" @click="checkOnboard()">{{ onboardLoading ? '正在核对…' : '核对上岗条件' }}</button>
        <button v-if="canManage" class="mp-btn mp-btn--primary" @click="openAssign">{{ detail.positionId ? '调整岗位' : '分配岗位' }}</button>
        <button v-if="canManage && detail.positionId" class="mp-btn mp-btn--danger-ghost" @click="askUnassign">退岗</button>
      </div>
      <section v-if="(onboardLoading || onboardError || onboardChecklist) && ['profile', 'placement'].includes(activeSection)" class="mp-card isd-check" aria-label="上岗条件核对" aria-live="polite" :aria-busy="onboardLoading">
        <div class="mp-card__head"><h2 class="isd-title">上岗条件核对</h2><button v-if="!onboardLoading" class="mp-btn" :disabled="submitting" @click="checkOnboard()">重新核对</button></div>
        <div class="mp-card__body">
          <p v-if="onboardLoading">正在读取该学生的最新上岗条件…</p>
          <p v-else-if="onboardError" role="alert" class="isd-error">{{ onboardError }}</p>
          <template v-else-if="onboardChecklist">
            <strong>{{ onboardChecklist.canOnboard ? '上岗条件已满足' : '上岗前仍有事项待完成' }}</strong>
            <p v-if="!onboardChecklist.statusReady">当前尚未处于待上岗状态，请先核对准备情况。</p>
            <ul v-if="onboardChecklist.blockers?.length"><li v-for="(item, index) in onboardChecklist.blockers" :key="index">{{ item }}</li></ul>
            <div v-if="agreementFollowUp"><RouterLink class="mp-btn" :to="agreementFollowUp">查找该生协议并补齐 →</RouterLink><p class="mp-note">按当前批次和姓名查询，进入协议前请核对学号。</p></div>
            <p v-else-if="!onboardChecklist.canOnboard && onboardChecklist.statusReady">当前条件尚未满足，请重新核对最新记录。</p>
            <button v-if="onboardChecklist.canOnboard && canManage" class="mp-btn mp-btn--primary" :disabled="submitting" @click="askStatus('ONBOARD')">办理上岗</button>
          </template>
        </div>
      </section>
        <section v-show="activeSection === 'placement'" class="mp-card">
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
                <span class="sd-v sd-v--wrap"><a class="mp-link" @click="openEnterprise">{{ detail.enterpriseName }}</a>
                  <span v-if="detail.company && detail.company.blacklist" class="sd-warn"> · 黑名单</span></span>
              </div>
              <div class="sd-kv"><span class="sd-k">实习岗位</span>
                <span class="sd-v sd-v--wrap"><a class="mp-link" @click="openPosition">{{ detail.positionName }}</a></span>
              </div>
              <div class="sd-kv"><span class="sd-k">企业导师</span><span class="sd-v">{{ detail.mentorName || '未指定' }}</span></div>
              <div class="sd-kv"><span class="sd-k">岗位容量</span><span class="sd-v">{{ detail.position ? detail.position.capacity : '—' }}</span></div>
              <div class="sd-kv sd-kv--full"><span class="sd-k">工作地点</span><span class="sd-v sd-v--wrap">{{ detail.position ? detail.position.workLocation : '—' }}</span></div>
            </div>
            <div v-if="!detail.positionId && canManage" class="sd-dest-actions">
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

      <section v-show="activeSection === 'history'" class="mp-card">
        <div class="mp-card__head"><h2 class="isd-title">处理记录</h2><span class="sd-card-note">最近 20 条</span></div>
        <div v-if="!detail.auditTrail?.length" class="isd-readonly">暂无处理记录</div>
        <ol v-else class="isd-history">
          <li v-for="(entry, index) in detail.auditTrail" :key="index"><span class="isd-history__dot" /><div>
            <h3>{{ auditLabel(entry.action) }}<span>{{ entry.operator || '系统' }}</span></h3>
            <p v-if="entry.action === 'ELIGIBILITY'">{{ eligibilityLabel(entry.detail?.status) }}</p>
            <p v-if="entry.detail?.reason" class="isd-history__reason">{{ entry.detail.reason }}</p><time>{{ formatDateTime(entry.occurredAt) }}</time>
          </div></li>
        </ol>
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
import { AppSensitiveText, AppStatusTag, AppInternshipPositionPicker } from '@/components/common'
import { AppDrawer } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { internStudentApi } from '@/modules/internship/api/internship-student.api'
import { canCode } from '@/modules/internship/composables/permission'
import { toast } from '@/utils/toast'
import { formatDateTime } from '@/utils/dateUtils'

const STATUS_NEXT = {
  PREPARING: { action: 'READY', label: '置为待上岗' },
  READY: { action: 'ONBOARD', label: '上岗' },
  ONBOARD: { action: 'ASSESS', label: '进入考核' }
}

export default {
  name: 'InternshipStudentDetailView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppSensitiveText, AppStatusTag, AppDrawer, AppConfirmDialog, AppInternshipPositionPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', submitting: false, detail: null, loadSequence: 0,
      reviewForm: { status: '', reason: '' }, reviewError: '', reviewConflict: false,
      onboardLoading: false, onboardError: '', onboardChecklist: null, onboardSequence: 0,
      sections: [{ key: 'profile', label: '基本资料' }, { key: 'eligibility', label: '资格审核' }, { key: 'placement', label: '岗位去向' }, { key: 'history', label: '处理记录' }],
      eligibilityOptions: [{ value: 'QUALIFIED', label: '合格', hint: '已按学校要求核对，可以继续实习准备' }, { value: 'UNQUALIFIED', label: '不合格', hint: '本次未通过，请在说明中写清后续安排' }, { value: 'PENDING', label: '待认定', hint: '暂未形成结论，继续核对或补充材料' }],
      assignVisible: false, assignPositionId: '', assignError: '',
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, extra: null }
    }
  },
  computed: {
    agreementFollowUp() {
      if (this.onboardLoading || this.onboardError || !this.detail?.name || !this.detail?.batchId || !canCode(this.ctx, 'internship.agreement.view')) return null
      if (!(this.onboardChecklist?.evaluation?.blockers || []).some(item => item.code === 'agreement')) return null
      return { path: '/admin/internship/agreements', query: { batchId: String(this.detail.batchId), panel: 'confirm', status: '', keyword: this.detail.name, returnTo: this.$route.fullPath } }
    },
    volunteerReturnTo() {
      const ref = this.$route.query.returnTo
      if (typeof ref !== 'string' || !/^\/admin\/internship\/volunteer-review\/\d+(?:\?|$)/.test(ref)) return ''
      const batchId = this.detail?.batchId || this.$route.query.batchId
      return batchId && new URL(ref, 'https://local.invalid').searchParams.get('batchId') === String(batchId) ? ref : ''
    },
    activeSection() { return this.sections.some((s) => s.key === this.$route.query.section) ? this.$route.query.section : 'profile' },
    isReadonly() { return !this.detail || this.detail.status === 'ARCHIVED' || ['CLOSED', 'ARCHIVED', 'VOIDED'].includes(this.detail.batchStatus) },
    canManage() { return !this.isReadonly && canCode(this.ctx, 'internship.student.manage') },
    canReview() { return !this.isReadonly && canCode(this.ctx, 'internship.student.eligibility.review') },
    canArchive() { return canCode(this.ctx, 'internship.archive.view') },
    statusAction() { return this.detail && this.detail.status !== 'ARCHIVED' ? STATUS_NEXT[this.detail.status] : null },
    pageSubtitle() {
      if (!this.detail) return this.loading ? '加载中' : '核对本批次学生实习档案'
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
  },
  watch: {
    '$route.params.id': { immediate: true, handler() {
      this.assignVisible = false; this.confirm.visible = false
      this.reviewForm = { status: '', reason: '' }; this.reviewError = ''; this.reviewConflict = false
      this.load()
      this.focusHeading()
    } },
    '$route.query.batchId'() {
      this.confirm.visible = false; this.assignVisible = false
      this.reviewForm = { status: '', reason: '' }; this.reviewError = ''; this.reviewConflict = false
      this.load()
    }
  },
  mounted() { this.focusHeading() },
  beforeUnmount() { this.loadSequence++; this.onboardSequence++ },
  methods: {
    focusHeading() {
      this.$nextTick(() => {
        const heading = this.$el?.querySelector('h1')
        if (!heading) return
        heading.setAttribute('tabindex', '-1')
        heading.style.scrollMarginTop = '16px'
        heading.focus({ preventScroll: true })
        heading.scrollIntoView({ block: 'start', behavior: 'instant' })
      })
    },
    formatDateTime,
    sectionLocation(section) { return { path: this.$route.path, query: { ...this.$route.query, section } } },
    eligibilityLabel(status) { return this.eligibilityOptions.find((x) => x.value === status)?.label || '待认定' },
    auditLabel(action) {
      return ({ ELIGIBILITY: '资格认定', CREATE: '建立实习档案', ASSIGN: '分配岗位', UNASSIGN: '退岗', ADVISOR: '调整指导教师', DESTINATION: '更新去向', STATUS_READY: '确认待上岗', STATUS_ONBOARD: '确认上岗', STATUS_ASSESS: '进入考核' })[action] || action
    },
    openEnterprise() {
      if (!this.detail?.enterpriseId) return
      this.$router.push({
        path: `/admin/internship/enterprises/${this.detail.enterpriseId}`,
        query: { batchId: String(this.detail.batchId || this.$route.query.batchId || ''), returnTo: this.$route.fullPath }
      })
    },
    openPosition() {
      if (!this.detail?.positionId) return
      this.$router.push({
        path: `/admin/internship/positions/${this.detail.positionId}`,
        query: { batchId: String(this.detail.batchId || this.$route.query.batchId || ''), returnTo: this.$route.fullPath }
      })
    },
    goBack() {
      if (this.volunteerReturnTo) return this.$router.push(this.volunteerReturnTo)
      const target = String(this.$route.query.returnTo || '')
      if (/^\/admin\/internship\/(?:students|assignment-logs|compliance|insurance(?:\/\d+)?)(?:\?|$)/.test(target)) return this.$router.push(target)
      this.$router.push({ path: '/admin/internship/students', query: { batchId: this.detail?.batchId || this.$route.query.batchId } })
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
      const seq = ++this.loadSequence
      this.onboardSequence++; this.onboardLoading = false; this.onboardError = ''; this.onboardChecklist = null
      this.loading = true; this.error = ''
      const res = await internStudentApi.getStudentDetail(this.$route.params.id)
      if (seq !== this.loadSequence) return
      if (res.code === 0 && this.$route.query.batchId && String(res.data.batchId) !== String(this.$route.query.batchId)) {
        this.detail = null; this.error = '此档案不属于当前批次，请返回名单重新进入'
      } else if (res.code === 0) this.detail = res.data
      else { this.detail = null; this.error = res.message || '实习档案加载失败，请重试' }
      this.loading = false
    },
    async refreshReview() {
      await this.load()
      if (!this.error) { this.reviewConflict = false; this.reviewError = '' }
    },
    openAssign() {
      if (!this.canManage || this.submitting) return
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
      if (!this.canReview || !this.reviewForm.status || this.submitting || this.reviewConflict) return
      this.confirm = { visible: true, title: '保存资格认定', message: '将「' + this.detail.name + '」的资格认定为「' + this.eligibilityLabel(this.reviewForm.status) + '」。本次填写的说明将向该学生展示。', type: 'primary', confirmText: '确认保存', requireReason: false, action: 'ELIG', extra: { ...this.reviewForm } }
    },
    askUnassign() {
      this.confirm = { visible: true, title: '退岗', message: '确认退岗？将释放该岗位名额。', type: 'warning', confirmText: '确认退岗', requireReason: true, reasonLabel: '退岗原因', action: 'UNASSIGN', extra: null }
    },
    async askStatus(action) {
      if (!this.canManage || this.submitting || this.onboardLoading) return
      const m = STATUS_NEXT[this.detail.status]
      if (!m || m.action !== action) return
      if (action === 'ONBOARD' && !await this.checkOnboard()) return
      this.confirm = { visible: true, title: m.label, message: `确认执行「${m.label}」？`, type: 'primary', confirmText: '确认', requireReason: false, action: 'STATUS', extra: action }
    },
    async checkOnboard() {
      if (!this.canManage || this.submitting || this.onboardLoading) return false
      const id = this.detail.id, batchId = this.$route.query.batchId, seq = ++this.onboardSequence
      const current = () => seq === this.onboardSequence && this.detail?.id === id && this.$route.query.batchId === batchId && this.canManage
      this.onboardLoading = true; this.onboardError = ''; this.onboardChecklist = null
      try {
        const res = await internStudentApi.getOnboardChecklist(id)
        if (!current()) return false
        if (res.code !== 0 || !res.data) throw new Error(res.message || '上岗条件核对失败，请重试')
        this.onboardChecklist = res.data
        return res.data.canOnboard === true && this.detail.status === 'READY'
      } catch (err) {
        if (current()) this.onboardError = err.message || '上岗条件核对失败，请重试'
        return false
      } finally {
        if (seq === this.onboardSequence) this.onboardLoading = false
      }
    },
    askDestination(dest) {
      const label = dest === 'SELF_ARRANGED' ? '自主实习' : '免实习'
      this.confirm = { visible: true, title: '标记去向 · ' + label, message: `确认将去向标记为「${label}」？`, type: 'primary', confirmText: '确认', requireReason: false, action: 'DEST', extra: dest }
    },
    async onConfirm({ reason } = {}) {
      const { action, extra } = this.confirm
      if (this.submitting || (action === 'ELIG' ? !this.canReview : !this.canManage)) return
      const recordId = this.detail.id
      this.submitting = true
      try {
        let res
        if (action === 'ELIG') res = await internStudentApi.setEligibility(this.detail.id, {
          status: extra.status, reason: extra.reason.trim(), publishReason: true, expectedVersion: this.detail.version
        })
        else if (action === 'UNASSIGN') res = await internStudentApi.unassignPosition(this.detail.id, {
          reason: reason || '', expectedVersion: this.detail.version
        })
        else if (action === 'STATUS') res = await internStudentApi.setStatus(this.detail.id, { action: extra, reason: reason || '', expectedVersion: this.detail.version })
        else if (action === 'DEST') res = await internStudentApi.setDestination(this.detail.id, {
          destination: extra, reason: reason || '', expectedVersion: this.detail.version
        })
        if (recordId !== this.detail?.id) return
        if (res && res.code === 0) {
          toast.success('已保存并写入处理记录'); this.confirm.visible = false
          if (action === 'ELIG') {
            this.reviewForm = { status: '', reason: '' }; this.reviewError = ''
            window.__SAAS_DIRTY_FORM_GUARD__?.markSaved()
          }
          this.load()
        } else if (res && action === 'ELIG') {
          this.confirm.visible = false; this.reviewError = res.message || '保存失败，填写内容已保留'
          this.reviewConflict = res.code === 409001 || res.code === 'DATA_CONFLICT'
        } else if (res) toast.error(res.message)
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.sd-card-note{margin:4px 0 0;font-size:12px;line-height:1.5;color:var(--t3,#64748b)}.sd-warn{color:var(--danger,#dc2626)}.sd-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px 22px}.sd-kv{display:flex;flex-direction:column;gap:4px;min-width:0}.sd-kv--full{grid-column:1/-1}.sd-k{font-size:12px;color:var(--t3,#64748b)}.sd-v{font-size:13px;line-height:1.55;color:var(--t1,#0f1e3d);min-width:0}.sd-v--wrap{word-break:break-word;white-space:normal}.sd-dest-actions{margin-top:16px;padding:14px;border-radius:9px;background:var(--warning-50,#fff7ed);display:flex;align-items:center;justify-content:space-between;gap:16px}.sd-dest-actions>div:first-child{display:flex;flex-direction:column;gap:4px}.sd-dest-actions strong{font-size:13px;color:var(--t1,#0f1e3d)}.sd-dest-actions span{font-size:12px;line-height:1.5;color:var(--t2,#475569)}.sd-dest-actions__buttons{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:8px;flex-shrink:0}.mp-btn{padding:8px 14px;border:1px solid var(--line,#d9dee8);border-radius:8px;background:#fff;cursor:pointer;font-size:13px;line-height:1.4;white-space:nowrap}.mp-btn:hover{border-color:var(--pri,#2563eb);color:var(--pri,#2563eb)}.mp-btn--primary{background:var(--pri,#2563eb);color:#fff;border-color:var(--pri,#2563eb)}.mp-btn--primary:hover{color:#fff}.mp-btn--danger-ghost{border-color:var(--danger-300,#fca5a5);color:var(--danger,#dc2626)}.mp-btn:disabled{opacity:.5;cursor:not-allowed}.ie-form{display:grid;grid-template-columns:1fr;gap:16px}.ie-intro{padding:12px 14px;border-radius:8px;background:var(--pri-50,#eff6ff)}.ie-intro strong{font-size:14px;color:var(--t1,#0f1e3d)}.ie-intro p{margin:5px 0 0;font-size:12px;line-height:1.55;color:var(--t2,#475569)}.ie-fld{display:flex;flex-direction:column;gap:6px}.ie-fld--full{grid-column:1/-1}.ie-lbl{font-size:12px;color:var(--t2,#475569)}.ie-lbl i{color:var(--danger,#dc2626);font-style:normal}.ie-err{color:var(--danger,#dc2626);font-size:12px;margin:0;padding:9px 11px;border-radius:7px;background:var(--danger-50,#fef2f2)}.ie-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:4px}@media(max-width:720px){.sd-grid{grid-template-columns:1fr}.sd-dest-actions{align-items:flex-start;flex-direction:column}.sd-dest-actions__buttons{justify-content:flex-start}.mp-btn{max-width:100%;white-space:normal}}

.isd.mps{gap:12px}
.isd-identity{display:flex;align-items:center;flex-wrap:wrap;gap:10px 20px;color:var(--t2);font-size:13px;margin:0}
.isd-sections{display:flex;gap:26px;border-bottom:1px solid var(--card-b);margin-bottom:4px;overflow:auto}
.isd-sections a{padding:0 2px 12px;color:var(--t2);font-size:14px;text-decoration:none;white-space:nowrap;border-bottom:2px solid transparent}
.isd-sections a.is-active{border-color:var(--pri);color:var(--pri);font-weight:600}
.isd-layout{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(250px,1fr);gap:22px;align-items:start}
.isd-title{font-size:16px;margin:0;font-weight:600}.isd-facts{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin:0;padding:24px}
.isd-facts dt{font-size:12px;color:var(--t3);margin-bottom:7px}.isd-facts dd{font-size:14px;margin:0;line-height:1.6;overflow-wrap:anywhere}.isd-facts__wide{grid-column:1/-1}
.isd-next,.isd-result{padding:24px}.isd-kicker{display:block;font-size:12px;color:var(--t3);margin-bottom:14px}
.isd-next h2{font-size:18px;line-height:1.6;margin:0 0 10px}.isd-next p,.isd-note{color:var(--t2);font-size:13px;line-height:1.8}
.isd-next .mp-btn{display:block;text-align:center;margin:20px 0}.isd-next .mp-link,.isd-result .mp-link{display:block;margin-top:18px;font-size:13px}
.isd-review__form{padding:18px}.isd-review fieldset{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;padding:0;border:0;margin:0 0 16px}.isd-review legend{font-size:13px;margin-bottom:12px}
.isd-choice{display:flex;align-items:center;gap:8px;border:1px solid var(--card-b);border-radius:8px;padding:12px 10px;margin:0;align-items:flex-start;cursor:pointer}
.isd-choice.is-selected{border-color:var(--pri);background:var(--pri-bg)}.isd-choice input{accent-color:var(--pri);width:16px;height:16px;flex:none}
.isd-choice strong{display:block;font-size:14px;font-weight:500}.isd-choice small{display:block;font-size:12px;color:var(--t2);line-height:1.6;margin-top:3px}
.isd-field{display:block;font-size:13px}.isd-field span{font-size:12px;color:var(--t3);margin-left:8px}.isd-field textarea{box-sizing:border-box;display:block;width:100%;resize:vertical;border:1px solid var(--card-b);border-radius:8px;padding:10px;margin-top:8px;font:inherit;line-height:1.7;background:var(--card);color:var(--t1)}
.isd-field textarea:focus{outline:2px solid var(--pri);outline-offset:2px}.isd-review__footer{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-top:22px}.isd-review__footer span{font-size:12px;color:var(--t3)}
.isd-result__reason{white-space:pre-wrap;overflow-wrap:anywhere;font-size:14px;line-height:1.8;margin:20px 0}.isd-note{padding-top:20px;margin-top:22px;border-top:1px solid var(--line)}
.isd-error{color:var(--danger);background:var(--danger-50,#fff2f0);font-size:13px;line-height:1.7;padding:12px;margin-top:15px}.isd-error button{display:block;margin-top:8px}
.isd-readonly{padding:24px;font-size:14px;color:var(--t2)}.isd-readonly h3{font-size:15px;color:var(--t1);margin-top:0}.isd-readonly p{line-height:1.7}
.isd-placement-actions{display:flex;gap:10px;margin-bottom:16px}.isd-history{list-style:none;margin:0;padding:24px}.isd-history li{display:flex;gap:18px;padding-bottom:24px}.isd-history__dot{width:9px;height:9px;border:3px solid var(--pri-bg);background:var(--pri);border-radius:50%;margin-top:3px;flex:none}.isd-history h3{font-size:14px;font-weight:600;margin:0 0 8px}.isd-history h3 span{font-size:12px;color:var(--t3);font-weight:400;margin-left:18px}.isd-history p{font-size:13px;margin:6px 0;line-height:1.7}.isd-history__reason{white-space:pre-wrap;overflow-wrap:anywhere}.isd-history time{color:var(--t3);font-size:12px}
.isd-check{margin-top:16px}.isd-check .mp-card__head{display:flex;align-items:center;justify-content:space-between;gap:12px}.isd-check .mp-card__body{font-size:13px;line-height:1.7}.isd-check p{margin:8px 0}.isd-check ul{padding-left:20px;margin:12px 0}.isd-check li{padding:4px 0;overflow-wrap:anywhere}.isd-placement-actions{flex-wrap:wrap}
@media(max-width:900px){.isd-layout{grid-template-columns:1fr}.isd-facts{gap:18px;padding:18px}.isd-sections{gap:20px}.isd-review__footer{flex-wrap:wrap}}
@media(max-width:600px){.isd-review fieldset{grid-template-columns:1fr}.isd-choice{align-items:center}.isd-field span{display:block;margin:4px 0 0}}
</style>
