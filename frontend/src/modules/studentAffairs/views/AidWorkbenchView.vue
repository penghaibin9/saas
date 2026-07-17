<template>
  <ModulePageShell
    title="困难认定工作台"
    subtitle="批次 · 班级评议 / 辅导员初审 / 学院复审 / 学校终审 · 公示与困难库"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="困难认定（含家庭经济敏感信息）"
  >
    <!-- 批次上下文 -->
    <div class="ad-batchbar">
      <label class="ad-batchsel">
        <span>认定批次</span>
        <AppSelect v-model="batchId" class="ad-batchpick" :options="batchOptions" placeholder="（请选择批次）" @change="onBatchChange" />
      </label>
      <div class="ad-batchtools">
        <AppPermissionButton code="studentAffairs.aid.batch.manage" variant="secondary" size="sm" @click="openBatch">建批次</AppPermissionButton>
        <AppPermissionButton code="studentAffairs.aid.approve" variant="secondary" size="sm" :loading="scanning" @click="onScanPublicity">公示扫描</AppPermissionButton>
        <AppPermissionButton code="studentAffairs.aid.create" variant="primary" size="sm" :disabled="!currentBatchOpen" @click="openApply">受理申请</AppPermissionButton>
      </div>
    </div>

    <div class="ad-toolbar">
      <div class="ad-filters">
        <button
          v-for="f in statusFilters"
          :key="f.key"
          type="button"
          class="ad-chip"
          :class="{ 'is-on': activeStatus === f.key }"
          @click="activeStatus = f.key"
        >
          {{ f.label }}<em>{{ f.count }}</em>
        </button>
      </div>
    </div>

    <div class="ad-workspace">
      <div class="ad-list">
        <LoadingState v-if="loading" text="正在加载认定申请…" />
        <ErrorState v-else-if="listError" :description="listError" @retry="loadApplications" />
        <EmptyState v-else-if="!batchId" title="请先选择认定批次" description="从上方选择一个批次，或点「建批次」新建" />
        <EmptyState v-else-if="!filteredList.length" title="该批次暂无申请" description="可点「受理申请」为学生受理，或调整筛选条件" />
        <ul v-else class="ad-queue">
          <li
            v-for="it in filteredList"
            :key="it.applyId"
            class="ad-qitem"
            :class="{ 'is-active': selected && selected.applyId === it.applyId }"
            @click="select(it)"
          >
            <div class="ad-qitem__top">
              <span class="ad-qitem__name">{{ it.realName || ('学生#' + it.studentId) }}</span>
              <StatusTag :type="statusType(it.status)" :label="it.statusLabel" dot />
            </div>
            <div class="ad-qitem__meta">
              申请：{{ levelLabel(it.applyLevel) }}
              <span v-if="it.finalLevel"> · 核定：{{ levelLabel(it.finalLevel) }}</span>
              <span class="ad-qitem__income">家庭年收入：{{ (it.familyEconomy && it.familyEconomy.annualIncomeRange) || '—' }}</span>
            </div>
          </li>
        </ul>
      </div>

      <div class="ad-detail">
        <EmptyState v-if="!selected" title="请从左侧选择一条申请" description="查看详情、评审、公示确认、查看完整家庭经济（敏感）" />
        <template v-else>
          <div class="ad-dhead">
            <div>
              <h3 class="ad-dname">{{ selected.realName || ('学生#' + selected.studentId) }}</h3>
              <StatusTag :type="statusType(selected.status)" :label="selected.statusLabel" dot />
            </div>
            <button type="button" class="ad-refresh" title="刷新详情" @click="reloadDetail">↻</button>
          </div>

          <dl class="ad-kv">
            <div><dt>申请等级</dt><dd>{{ levelLabel(selected.applyLevel) }}</dd></div>
            <div><dt>建议等级</dt><dd>{{ levelLabel(selected.suggestLevel) || '—' }}</dd></div>
            <div><dt>核定等级</dt><dd>{{ levelLabel(selected.finalLevel) || '—' }}</dd></div>
            <div><dt>学号</dt><dd>{{ selected.studentNo || '—' }}</dd></div>
          </dl>

          <!-- 家庭经济（强敏感，默认脱敏） -->
          <section class="ad-family">
            <div class="ad-family__head">
              <span class="ad-family__title">家庭经济（强敏感）</span>
              <button type="button" class="ad-reveal" :disabled="revealing" @click="openReveal">
                {{ revealed ? '已展开完整' : '🔒 查看完整（留审计）' }}
              </button>
            </div>
            <template v-if="!revealed">
              <div class="ad-family__row">年收入区间：{{ fam.annualIncomeRange || '—' }}</div>
              <div class="ad-family__row">家庭人数：{{ fam.memberCount || '—' }}</div>
              <div class="ad-family__row">特殊标记：{{ (fam.specialTags && fam.specialTags.join('、')) || '无' }}</div>
              <div class="ad-family__mask">明细已脱敏，查看完整需填写原因并留审计</div>
            </template>
            <template v-else>
              <div class="ad-family__row ad-family__row--full">年收入：<b>{{ revealedFam.annualIncome || '未填写' }}</b></div>
              <div class="ad-family__row">负债：{{ revealedFam.debt || '—' }}</div>
              <div class="ad-family__row">家庭人数：{{ revealedFam.memberCount || '—' }}</div>
              <div class="ad-family__row">特殊标记：{{ (revealedFam.specialTags && revealedFam.specialTags.join('、')) || '无' }}</div>
            </template>
          </section>

          <div v-if="detailActions.length" class="ad-actions">
            <AppPermissionButton
              v-for="a in detailActions"
              :key="a.key"
              :code="a.code"
              :variant="a.tone === 'primary' ? 'primary' : (a.tone === 'danger' ? 'danger' : 'secondary')"
              size="sm"
              :loading="acting"
              @click="onAction(a.key)"
            >{{ a.label }}</AppPermissionButton>
          </div>
          <p v-else class="ad-terminal">该申请已处于终态（{{ selected.statusLabel }}），仅可查看。</p>
        </template>
      </div>
    </div>

    <!-- 通用确认（评审通过/退回/驳回/重提/公示确认/调整审批） -->
    <AppConfirmDialog
      v-model:visible="dialog.visible"
      :title="dialog.title"
      :message="dialog.message"
      :type="dialog.type"
      :confirm-text="dialog.confirmText"
      :require-reason="dialog.requireReason"
      :reason-label="dialog.reasonLabel"
      :reason-placeholder="dialog.reasonPlaceholder"
      :submitting="acting"
      @confirm="onDialogConfirm"
    />

    <!-- 查看完整家庭经济 modal（原因必填，落 SENSITIVE 审计） -->
    <div v-if="revealModal.visible" class="ad-mask" @click.self="revealModal.visible = false">
      <div class="ad-modal">
        <h3 class="ad-modal__title">查看完整家庭经济</h3>
        <p class="ad-modal__hint">该操作将记录敏感查看审计（谁、何时、查看谁、原因）。仅授权角色可见明文，无权限返回 403。</p>
        <label class="ad-field"><span>查看原因 <i>*</i></span>
          <AppTextarea v-model="revealModal.reason" :rows="3" placeholder="如：核对家庭经济，办理助学金前置校验" />
        </label>
        <p v-if="revealModal.error" class="ad-err">{{ revealModal.error }}</p>
        <div class="ad-modal__foot">
          <button type="button" class="ad-btn" @click="revealModal.visible = false">取消</button>
          <button type="button" class="ad-btn ad-btn--primary" :disabled="revealing" @click="submitReveal">确认查看</button>
        </div>
      </div>
    </div>

    <!-- 动态调整 modal -->
    <div v-if="adjustModal.visible" class="ad-mask" @click.self="adjustModal.visible = false">
      <div class="ad-modal">
        <h3 class="ad-modal__title">困难等级动态调整</h3>
        <label class="ad-field"><span>目标等级 <i>*</i></span>
          <AppSelect v-model="adjustModal.targetLevel" :options="levelOptions" placeholder="" />
        </label>
        <label class="ad-field"><span>调整原因（≥5字） <i>*</i></span>
          <AppTextarea v-model="adjustModal.reason" :rows="3" placeholder="说明调整原因，不少于 5 字" />
        </label>
        <p v-if="adjustModal.error" class="ad-err">{{ adjustModal.error }}</p>
        <div class="ad-modal__foot">
          <button type="button" class="ad-btn" @click="adjustModal.visible = false">取消</button>
          <button type="button" class="ad-btn ad-btn--primary" :disabled="acting" @click="submitAdjust">提交调整</button>
        </div>
      </div>
    </div>

    <!-- 建批次 modal -->
    <div v-if="batchModal.visible" class="ad-mask" @click.self="batchModal.visible = false">
      <div class="ad-modal">
        <h3 class="ad-modal__title">新建认定批次</h3>
        <label class="ad-field"><span>批次名称 <i>*</i></span>
          <AppTextInput v-model="batchModal.batchName" placeholder="如：2026 春季家庭经济困难认定" />
        </label>
        <label class="ad-field"><span>学年 <i>*</i></span>
          <AppTextInput v-model="batchModal.schoolYear" placeholder="如：2025-2026" />
        </label>
        <label class="ad-field"><span>公示天数</span>
          <AppNumberInput v-model="batchModal.publicityDays" :min="0" placeholder="默认 5，快测可填 0" />
        </label>
        <label class="ad-check"><input v-model="batchModal.publish" type="checkbox" /> 立即发布（开放受理）</label>
        <p v-if="batchModal.error" class="ad-err">{{ batchModal.error }}</p>
        <div class="ad-modal__foot">
          <button type="button" class="ad-btn" @click="batchModal.visible = false">取消</button>
          <button type="button" class="ad-btn ad-btn--primary" :disabled="acting" @click="submitBatch">保存</button>
        </div>
      </div>
    </div>

    <!-- 受理申请 modal -->
    <div v-if="applyModal.visible" class="ad-mask" @click.self="applyModal.visible = false">
      <div class="ad-modal">
        <h3 class="ad-modal__title">受理困难认定申请</h3>
        <div class="ad-field"><span>学生 <i>*</i></span>
          <AppStudentPicker v-model="applyModal.studentId" :remote-search="searchStudents" placeholder="按姓名 / 学号搜索学生" />
        </div>
        <label class="ad-field"><span>申请等级 <i>*</i></span>
          <AppSelect v-model="applyModal.applyLevel" :options="levelOptions" placeholder="" />
        </label>
        <label class="ad-field"><span>困难情况说明（10-500字） <i>*</i></span>
          <AppTextarea v-model="applyModal.statement" :rows="3" placeholder="客观描述家庭困难情况，10-500 字" />
        </label>
        <div class="ad-grid2">
          <label class="ad-field"><span>家庭人数</span>
            <AppNumberInput v-model="applyModal.memberCount" :min="0" />
          </label>
          <label class="ad-field"><span>家庭年收入（元）</span>
            <AppTextInput v-model="applyModal.annualIncome" placeholder="强敏感，隔离存储" />
          </label>
        </div>
        <label class="ad-field"><span>负债（元）</span>
          <AppTextInput v-model="applyModal.debt" placeholder="选填" />
        </label>
        <p v-if="applyModal.error" class="ad-err">{{ applyModal.error }}</p>
        <div class="ad-modal__foot">
          <button type="button" class="ad-btn" @click="applyModal.visible = false">取消</button>
          <button type="button" class="ad-btn ad-btn--primary" :disabled="acting" @click="submitApply">受理</button>
        </div>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 困难认定工作台（/admin/student-affairs/aid）—— 13A P4 困难认定 + 强敏感家庭经济管线。
 * 真实对接 /api/v1/student-affairs/aid/*：批次 → 受理 → 班级评议/辅导员初审/学院复审/学校终审 → 公示 → 通过（进困难库+360）→ 动态调整。
 * 家庭经济默认脱敏（年收入区间）；查看完整走 reveal（sensitiveView 鉴权 + SENSITIVE 审计，非授权 403）。
 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import {
  AppConfirmDialog, AppNumberInput, AppPermissionButton, AppSelect, AppStatusTag,
  AppStudentPicker, AppTextInput, AppTextarea
} from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

const AID_NODES = ['CLASS_REVIEW', 'COUNSELOR_REVIEW', 'COLLEGE_REVIEW', 'SCHOOL_REVIEW']
const STATUS_TYPE = {
  DRAFT: 'default', SUBMITTED: 'processing', CLASS_REVIEW: 'warning', COUNSELOR_REVIEW: 'warning',
  COLLEGE_REVIEW: 'warning', SCHOOL_REVIEW: 'warning', PUBLICITY: 'processing', APPROVED: 'success',
  REJECTED: 'danger', ADJUST_REVIEW: 'processing', ARCHIVED: 'default'
}
const LEVEL = { SPECIAL: '特别困难', DIFFICULT: '困难', GENERAL: '一般困难' }
const BATCH_STATUS = { DRAFT: '草稿', OPEN: '开放中', CLOSED: '已截止' }

export default {
  name: 'AidWorkbenchView',
  components: {
    ModulePageShell, LoadingState, ErrorState, EmptyState, AppConfirmDialog, AppNumberInput,
    AppPermissionButton, AppSelect, StatusTag: AppStatusTag, AppStudentPicker, AppTextInput, AppTextarea
  },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      loading: false, listError: '', batches: [], batchId: '', list: [],
      selected: null, acting: false, scanning: false,
      revealed: false, revealedFam: {}, revealing: false,
      activeStatus: 'ALL',
      dialog: { visible: false, action: '', title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '', reasonPlaceholder: '' },
      revealModal: { visible: false, reason: '', error: '' },
      adjustModal: { visible: false, targetLevel: 'DIFFICULT', reason: '', error: '' },
      batchModal: { visible: false, batchName: '', schoolYear: '', publicityDays: 0, publish: true, error: '' },
      applyModal: { visible: false, studentId: '', applyLevel: 'DIFFICULT', statement: '', memberCount: null, annualIncome: '', debt: '', error: '' },
      levelOptions: Object.entries(LEVEL).map(([value, label]) => ({ value, label }))
    }
  },
  computed: {
    roleName() {
      return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || ''
    },
    dataScopeName() {
      return (this.ctx && this.ctx.dataScope && this.ctx.dataScope.scopeName) || ''
    },
    batchOptions() {
      return this.batches.map((b) => ({
        value: b.batchId,
        label: `${b.batchName}（${b.schoolYear} · ${this.batchStatusLabel(b.status)}）`
      }))
    },
    currentBatchOpen() {
      const b = this.batches.find((x) => x.batchId === this.batchId)
      return !!b && b.status === 'OPEN'
    },
    fam() {
      return (this.selected && this.selected.familyEconomy) || {}
    },
    statusFilters() {
      const c = (arr) => this.list.filter((x) => arr.includes(x.status)).length
      return [
        { key: 'ALL', label: '全部', count: this.list.length },
        { key: 'REVIEW', label: '评审中', count: c(AID_NODES) },
        { key: 'PUBLICITY', label: '公示中', count: c(['PUBLICITY']) },
        { key: 'APPROVED', label: '已通过', count: c(['APPROVED']) },
        { key: 'ADJUST_REVIEW', label: '调整审批', count: c(['ADJUST_REVIEW']) },
        { key: 'REJECTED', label: '已驳回', count: c(['REJECTED']) }
      ]
    },
    filteredList() {
      let arr = this.list
      if (this.activeStatus === 'REVIEW') arr = arr.filter((x) => AID_NODES.includes(x.status))
      else if (this.activeStatus !== 'ALL') arr = arr.filter((x) => x.status === this.activeStatus)
      return arr
    },
    detailActions() {
      const s = this.selected && this.selected.status
      if (!s) return []
      if (AID_NODES.includes(s)) {
        const label = { CLASS_REVIEW: '评议通过', COUNSELOR_REVIEW: '初审通过', COLLEGE_REVIEW: '复审通过', SCHOOL_REVIEW: '终审通过' }[s]
        return [
          { key: 'approve', label, tone: 'primary', code: 'studentAffairs.aid.approve' },
          { key: 'return', label: '退回', tone: 'default', code: 'studentAffairs.aid.approve' },
          { key: 'reject', label: '驳回', tone: 'danger', code: 'studentAffairs.aid.approve' }
        ]
      }
      if (s === 'DRAFT') return [{ key: 'resubmit', label: '重新提交', tone: 'primary', code: 'studentAffairs.aid.create' }]
      if (s === 'PUBLICITY') return [{ key: 'publicityConfirm', label: '确认公示通过', tone: 'primary', code: 'studentAffairs.aid.approve' }]
      if (s === 'APPROVED') return [{ key: 'adjust', label: '动态调整', tone: 'default', code: 'studentAffairs.aid.adjust' }]
      if (s === 'ADJUST_REVIEW') {
        return [
          { key: 'adjustApprove', label: '调整通过', tone: 'primary', code: 'studentAffairs.aid.adjust' },
          { key: 'adjustReject', label: '调整驳回', tone: 'danger', code: 'studentAffairs.aid.adjust' }
        ]
      }
      return []
    }
  },
  created() {
    this.loadBatches()
  },
  methods: {
    levelLabel(l) {
      return LEVEL[l] || ''
    },
    statusType(s) {
      return STATUS_TYPE[s] || 'default'
    },
    batchStatusLabel(s) {
      return BATCH_STATUS[s] || s
    },
    async loadBatches() {
      const res = await studentAffairsApi.getAidBatches({ page: 1, pageSize: 100 })
      if (res.code === 0 && res.data) {
        this.batches = res.data.items || []
        if (!this.batchId && this.batches.length) {
          this.batchId = this.batches[0].batchId
          this.loadApplications()
        }
      } else {
        this.listError = res.message || '批次加载失败'
      }
    },
    onBatchChange() {
      this.selected = null
      this.revealed = false
      if (this.batchId) this.loadApplications()
      else this.list = []
    },
    async loadApplications() {
      if (!this.batchId) return
      this.loading = true
      this.listError = ''
      const res = await studentAffairsApi.getAidApplications({ batchId: this.batchId, page: 1, pageSize: 200 })
      this.loading = false
      if (res.code === 0 && res.data) {
        this.list = res.data.items || []
        if (this.selected) {
          const hit = this.list.find((x) => x.applyId === this.selected.applyId)
          if (hit) this.selected = hit
        }
      } else {
        this.listError = res.message || '申请加载失败'
      }
    },
    select(it) {
      this.selected = it
      this.revealed = false
      this.revealedFam = {}
    },
    async reloadDetail() {
      if (!this.selected) return
      const res = await studentAffairsApi.getAidDetail(this.selected.applyId)
      if (res.code === 0 && res.data) this.selected = res.data
      else toast.error(res.message || '刷新详情失败')
    },
    onAction(key) {
      if (key === 'adjust') { this.openAdjust(); return }
      const map = {
        approve: { action: 'approve', title: '评审通过', message: '通过后推进到下一评审节点，终审通过将进入公示。', type: 'primary', confirmText: '评审通过', requireReason: false },
        return: { action: 'return', title: '退回申请', message: '退回后回到草稿，可修改后重新提交。', type: 'warning', confirmText: '退回', requireReason: true, reasonLabel: '退回原因（≥5字）', reasonPlaceholder: '请说明退回原因，不少于 5 字' },
        reject: { action: 'reject', title: '驳回申请', message: '驳回为终态，本次认定不予通过。', type: 'danger', confirmText: '驳回', requireReason: true, reasonLabel: '驳回原因（≥5字）', reasonPlaceholder: '请说明驳回原因，不少于 5 字' },
        resubmit: { action: 'resubmit', title: '重新提交', message: '将退回的申请重新提交，回到班级评议。', type: 'primary', confirmText: '重新提交', requireReason: false },
        publicityConfirm: { action: 'publicityConfirm', title: '确认公示通过', message: '确认公示期满无异议，认定通过并写入困难库、学生 360。', type: 'primary', confirmText: '确认通过', requireReason: false },
        adjustApprove: { action: 'adjustApprove', title: '调整审批通过', message: '通过后困难等级按目标等级调整，写入等级变更历史。', type: 'primary', confirmText: '调整通过', requireReason: false },
        adjustReject: { action: 'adjustReject', title: '调整审批驳回', message: '驳回后等级维持不变。', type: 'danger', confirmText: '调整驳回', requireReason: false }
      }
      const d = map[key]
      if (!d) return
      this.dialog = { visible: true, reasonLabel: '原因', reasonPlaceholder: '', ...d }
    },
    async onDialogConfirm(payload) {
      const reason = (payload && payload.reason) || ''
      const id = this.selected.applyId
      const a = this.dialog.action
      const call = {
        approve: () => studentAffairsApi.reviewAid(id, 'APPROVE'),
        return: () => studentAffairsApi.reviewAid(id, 'RETURN', null, reason),
        reject: () => studentAffairsApi.reviewAid(id, 'REJECT', null, reason),
        resubmit: () => studentAffairsApi.resubmitAid(id),
        publicityConfirm: () => studentAffairsApi.confirmAidPublicity(id),
        adjustApprove: () => studentAffairsApi.approveAidAdjust(id, 'APPROVE'),
        adjustReject: () => studentAffairsApi.approveAidAdjust(id, 'REJECT')
      }[a]
      if (!call) return
      await this.runAction(call, {
        approve: '已评审通过', return: '已退回', reject: '已驳回', resubmit: '已重新提交',
        publicityConfirm: '认定已通过', adjustApprove: '调整已通过', adjustReject: '调整已驳回'
      }[a])
      this.dialog.visible = false
    },
    // ── 敏感查看 ──
    openReveal() {
      if (this.revealed) return
      this.revealModal = { visible: true, reason: '', error: '' }
    },
    async submitReveal() {
      const reason = (this.revealModal.reason || '').trim()
      if (!reason || reason.length < 5) { this.revealModal.error = '查看原因不少于 5 字'; return }
      this.revealing = true
      const res = await studentAffairsApi.revealAidFamily(this.selected.applyId, reason)
      this.revealing = false
      if (res.code === 0 && res.data) {
        this.revealed = true
        this.revealedFam = res.data.familyEconomy || {}
        this.revealModal.visible = false
        toast.success('已查看完整家庭经济（已记审计）')
      } else {
        this.revealModal.error = res.message || '无权限查看'
        toast.error(res.message || '无权限查看完整家庭经济')
      }
    },
    // ── 动态调整 ──
    openAdjust() {
      this.adjustModal = { visible: true, targetLevel: this.selected.finalLevel || 'DIFFICULT', reason: '', error: '' }
    },
    async submitAdjust() {
      const reason = (this.adjustModal.reason || '').trim()
      if (!reason || reason.length < 5) { this.adjustModal.error = '调整原因不少于 5 字'; return }
      const ok = await this.runAction(
        () => studentAffairsApi.adjustAid(this.selected.applyId, this.adjustModal.targetLevel, reason),
        '调整已提交'
      )
      if (ok) this.adjustModal.visible = false
      else this.adjustModal.error = this._lastErr || '提交失败'
    },
    // ── 批次 ──
    openBatch() {
      this.batchModal = { visible: true, batchName: '', schoolYear: '', publicityDays: 0, publish: true, error: '' }
    },
    async submitBatch() {
      const m = this.batchModal
      const batchName = (m.batchName || '').trim()
      const schoolYear = (m.schoolYear || '').trim()
      if (!batchName || !schoolYear) { m.error = '批次名称与学年必填'; return }
      const body = { batchName, schoolYear, publicityDays: Number(m.publicityDays) || 0, publish: !!m.publish }
      const res = await studentAffairsApi.createAidBatch(body)
      if (res.code === 0) {
        toast.success('批次已保存')
        this.batchModal.visible = false
        await this.loadBatches()
        if (res.data && res.data.batchId) { this.batchId = res.data.batchId; this.loadApplications() }
      } else {
        this.batchModal.error = res.message || '保存失败'
      }
    },
    // ── 受理 ──
    openApply() {
      this.applyModal = { visible: true, studentId: '', applyLevel: 'DIFFICULT', statement: '', memberCount: null, annualIncome: '', debt: '', error: '' }
    },
    searchStudents(keyword) {
      return studentAffairsApi.searchStudents(keyword)
    },
    async submitApply() {
      const m = this.applyModal
      if (!m.studentId) { m.error = '请选择学生'; return }
      const statement = (m.statement || '').trim()
      if (!statement || statement.length < 10 || statement.length > 500) { m.error = '困难情况说明需 10-500 字'; return }
      const body = {
        batchId: String(this.batchId), studentId: String(m.studentId), applyLevel: m.applyLevel,
        statement, memberCount: m.memberCount || null,
        annualIncome: (m.annualIncome || '').trim(), debt: (m.debt || '').trim(), familyMembers: [], specialTags: []
      }
      const ok = await this.runAction(() => studentAffairsApi.applyAid(body), '申请已受理')
      if (ok) this.applyModal.visible = false
      else this.applyModal.error = this._lastErr || '受理失败'
    },
    async onScanPublicity() {
      this.scanning = true
      const res = await studentAffairsApi.scanAidPublicity()
      this.scanning = false
      if (res.code === 0) {
        toast.info(`公示扫描完成：${res.data.count} 条转为已通过`)
        this.loadApplications()
      } else {
        toast.error(res.message || '扫描失败')
      }
    },
    async runAction(call, okMsg) {
      this.acting = true
      this._lastErr = ''
      const res = await call()
      if (res.code === 0) {
        toast.success(okMsg)
        if (res.data && res.data.applyId) { this.selected = res.data; this.revealed = false }
        else await this.reloadDetail()
        await this.loadApplications()
        this.acting = false
        return true
      }
      this._lastErr = res.message || '操作失败'
      toast.error(this._lastErr)
      this.acting = false
      return false
    }
  }
}
</script>

<style scoped>
.ad-batchbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
  padding: var(--space-3);
  margin-bottom: var(--space-3);
  background: var(--primary-50);
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-lg);
}
.ad-batchpick {
  width: 320px;
}
.ad-batchsel {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.ad-batchtools {
  display: flex;
  gap: var(--space-2);
}
.ad-toolbar {
  margin-bottom: var(--space-3);
}
.ad-filters {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.ad-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  height: 30px;
  padding: 0 var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-full);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.ad-chip.is-on {
  border-color: var(--primary-400);
  color: var(--primary-700);
  background: var(--primary-50);
}
.ad-chip em {
  font-style: normal;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.ad-btn {
  height: 30px;
  padding: 0 var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.ad-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.ad-btn--primary {
  background: var(--primary-600);
  border-color: var(--primary-600);
  color: #fff;
}
.ad-btn--danger {
  background: var(--danger-600, #dc2626);
  border-color: var(--danger-600, #dc2626);
  color: #fff;
}
.ad-workspace {
  display: grid;
  grid-template-columns: minmax(300px, 400px) 1fr;
  gap: var(--space-4);
  align-items: start;
}
.ad-list {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  min-height: 320px;
  padding: var(--space-2);
}
.ad-queue {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.ad-qitem {
  padding: var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  cursor: pointer;
}
.ad-qitem:hover {
  border-color: var(--primary-300);
}
.ad-qitem.is-active {
  border-color: var(--primary-500);
  background: var(--primary-50);
}
.ad-qitem__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}
.ad-qitem__name {
  font-weight: 600;
  color: var(--text-primary);
}
.ad-qitem__meta {
  margin-top: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.ad-qitem__income {
  color: var(--text-secondary);
}
.ad-detail {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  min-height: 320px;
  padding: var(--space-4);
}
.ad-dhead {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.ad-dname {
  margin: 0 0 var(--space-2);
  font-size: var(--font-size-lg);
  color: var(--text-primary);
}
.ad-refresh {
  border: 1px solid var(--border-base);
  background: var(--bg-card);
  border-radius: var(--radius-base);
  width: 28px;
  height: 28px;
  cursor: pointer;
  color: var(--text-secondary);
}
.ad-kv {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2) var(--space-4);
  margin: 0 0 var(--space-4);
}
.ad-kv > div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.ad-kv dt {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.ad-kv dd {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--text-primary);
}
.ad-family {
  border: 1px dashed var(--warning-300, #fbbf24);
  border-radius: var(--radius-base);
  background: var(--warning-50, #fffbeb);
  padding: var(--space-3);
  margin-bottom: var(--space-4);
}
.ad-family__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}
.ad-family__title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--warning-700, #b45309);
}
.ad-reveal {
  height: 26px;
  padding: 0 var(--space-2);
  border: 1px solid var(--warning-300, #fbbf24);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--warning-700, #b45309);
  font-size: var(--font-size-xs);
  cursor: pointer;
}
.ad-reveal:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.ad-family__row {
  font-size: var(--font-size-sm);
  color: var(--text-primary);
  margin-bottom: 2px;
}
.ad-family__row--full b {
  color: var(--danger-600, #dc2626);
}
.ad-family__mask {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin-top: var(--space-1);
}
.ad-actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-base);
}
.ad-terminal {
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-base);
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
}
.ad-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.ad-modal {
  width: 480px;
  max-width: calc(100vw - 32px);
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  box-shadow: var(--shadow-lg, 0 10px 40px rgba(0, 0, 0, 0.2));
}
.ad-modal__title {
  margin: 0 0 var(--space-3);
  font-size: var(--font-size-lg);
  color: var(--text-primary);
}
.ad-modal__hint {
  margin: 0 0 var(--space-3);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.ad-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin-bottom: var(--space-3);
}
.ad-field > span {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.ad-field i {
  color: var(--danger-600, #dc2626);
  font-style: normal;
}
.ad-grid2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
}
.ad-check {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-bottom: var(--space-3);
}
.ad-input,
.ad-textarea {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  padding: var(--space-2);
  outline: none;
}
.ad-textarea {
  resize: vertical;
}
.ad-err {
  margin: 0 0 var(--space-2);
  color: var(--danger-600, #dc2626);
  font-size: var(--font-size-xs);
}
.ad-modal__foot {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-2);
}
</style>
