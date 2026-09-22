<template>
  <ModulePageShell
    title="调停课申请"
    subtitle="教师从本人正式课位发起，不直接修改课表"
    :role-name="roleName"
    :data-scope-name="scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/schedule-change')">返回调停课台账</AppButton>
      <AppButton variant="primary" :disabled="submitting || Boolean(unconfirmed)" @click="origin ? onSubmit() : openMySchedule()">{{ origin ? '预检后提交申请' : '从正式课位选择' }}</AppButton>
    </template>
    <div class="mp-stack">
      <section v-if="unconfirmed && !submitting" class="sc-unconfirmed" role="alert">
        <strong>提交结果未确认，已暂停此课位的重复提交</strong>
        <p>原课位 {{ unconfirmed.originItemId }} · 提交时间 {{ new Date(unconfirmed.startedAt).toLocaleString() }}。请到调停课台账核对；列表暂未查到也不能证明提交失败。</p>
        <p v-if="unconfirmedDraft">本次提交原因：{{ unconfirmedDraft.reason }}</p>
        <AppButton variant="ghost" @click="$router.push('/admin/academic-affairs/schedule-change')">查看调停课台账</AppButton>
      </section>
      <section v-if="receipt" class="sc-receipt" role="status">
        <div><strong>✓ 调停课申请已提交</strong><span>{{ receipt.courseName }} · 单据 {{ receipt.changeId }}</span></div>
        <div><small>当前结果</small><b>{{ receipt.statusLabel }}</b></div>
        <div><small>下一责任</small><b>学院教务审核人</b></div>
        <div class="sc-receipt__actions">
          <AppButton size="small" variant="ghost" @click="$router.push('/admin/academic-affairs/teacher/today')">返回今日教学</AppButton>
          <AppButton size="small" variant="ghost" @click="goReceipt">查看申请详情</AppButton>
          <AppButton size="small" @click="openMySchedule">继续从课表选择</AppButton>
        </div>
      </section>
      <section v-if="origin" class="sc-object-context" aria-label="当前调停课对象">
        <div><strong>{{ origin.courseName || '课程待确认' }} · {{ origin.className || '教学班待确认' }}</strong><p>调停课申请 · {{ origin.batchName || '正式课表' }} · 原课表项 {{ origin.itemId || form.originItemId }}</p><p>来源：从本人正式课表选择 · 当前状态：{{ receipt ? receipt.statusLabel : '申请编辑中' }}</p></div>
        <dl><div><dt>当前责任</dt><dd>{{ receipt ? '学院教务审核人' : '任课教师 / 当前审核岗' }}</dd></div><div><dt>下一责任</dt><dd>{{ receipt ? '教务审核岗 → 课表生效 → 师生通知' : '学院教务审核人' }}</dd></div></dl>
      </section>
      <ol class="sc-flow-rail" aria-label="调停课申请流程">
        <li v-for="(stage, index) in stages" :key="stage" :class="flowClass(index + 1)"><b>{{ index + 1 }}</b><span>{{ stage }}</span><small>{{ flowNote(index + 1) }}</small></li>
      </ol>
      <div class="sc-compare">
      <AppSectionCard title="原正式课位" class="sc-origin-card">
        <LoadingState v-if="originLoading" />
        <ErrorState v-else-if="originError" :description="originError" @retry="loadOrigin" />
        <EmptyState
          v-else-if="!form.originItemId"
          title="请先从本人课表选择一个课位"
          description="系统会自动带入正式课位，不需要复制或填写任何内部 ID。"
        >
          <template #actions>
            <AppButton variant="primary" @click="openMySchedule">打开本人课表</AppButton>
          </template>
        </EmptyState>
        <div v-else-if="origin" class="sc-origin">
          <div>
            <strong>{{ origin.courseName || '课程' }}</strong>
            <p>{{ origin.className || '教学班' }} · {{ origin.teacherName || '任课教师' }}</p>
          </div>
          <dl>
            <div><dt>原时间</dt><dd>{{ weekdayLabel(origin.weekday) }} 第{{ origin.slotNo }}节</dd></div>
            <div><dt>原周次</dt><dd>{{ origin.startWeek }}–{{ origin.endWeek }}周（{{ parityLabel(origin.weekParity) }}）</dd></div>
            <div><dt>原教室</dt><dd>{{ origin.classroom || '待定' }}</dd></div>
            <div><dt>正式批次</dt><dd>{{ origin.batchName || '已发布课表' }}</dd></div>
          </dl>
        </div>
      </AppSectionCard>

      <form v-if="origin" class="sc-form" @submit.prevent="onSubmit">
        <h2 class="sc-form__title">拟调整课位</h2>
        <div class="sc-fld sc-fld--full">
          <label class="sc-lbl">变更类型 <i>*</i></label>
          <div class="sc-radio">
            <label v-for="t in CHANGE_TYPES" :key="t.value">
              <input type="radio" :value="t.value" v-model="form.changeType" /> {{ t.label }}
            </label>
          </div>
        </div>

        <div class="sc-fld sc-fld--full">
          <label class="sc-lbl">原因 <i>*</i>（≥5 字）</label>
          <textarea ref="reasonInput" class="sc-in" v-model.trim="form.reason" rows="3" placeholder="请说明本次调整原因" />
          <AppQuickPhrases scene-key="aa.schedchg.reason" @pick="onPickReason" />
        </div>

        <div v-if="form.changeType === 'STOP'" class="sc-fld sc-fld--full">
          <label class="sc-lbl">停课教学周 <i>*</i></label>
          <input class="sc-in" type="number" min="1" v-model.number="form.targetStartWeek" placeholder="请选择只停哪一周" />
          <small>只停这一周的该课次；其余周次仍保留在正式课表。</small>
        </div>

        <template v-if="form.changeType !== 'STOP'">
          <div v-if="form.changeType === 'ADJUST'" class="sc-fld sc-fld--full">
            <label class="sc-lbl">调整范围 <i>*</i></label>
            <div v-if="lockedOccurrenceWeek" class="sc-occurrence-lock">
              本次从具体课次发起，仅调整第 {{ lockedOccurrenceWeek }} 教学周；如需调整连续周次，请返回个人课表重新选择。
            </div>
            <div v-else class="sc-radio">
              <label><input type="radio" value="OCCURRENCE" v-model="adjustScope" /> 只调整一次课</label>
              <label><input type="radio" value="RANGE" v-model="adjustScope" /> 调整周期课表</label>
            </div>
          </div>
          <div class="sc-fld">
            <label class="sc-lbl">目标星期 <i>*</i></label>
            <AppSelect v-model="form.targetWeekday" :options="weekdayOptions" />
          </div>
          <div class="sc-fld">
            <label class="sc-lbl">目标节次 <i>*</i></label>
            <input class="sc-in" type="number" min="1" v-model.number="form.targetSlotNo" />
          </div>
          <div v-if="form.changeType === 'MAKEUP'" class="sc-fld sc-fld--full">
            <label class="sc-lbl">补课教学周 <i>*</i></label>
            <input class="sc-in" type="number" min="1" v-model.number="form.targetStartWeek" placeholder="补课只新增这一周的一次课" />
          </div>
          <template v-else>
            <div v-if="adjustScope === 'OCCURRENCE' || lockedOccurrenceWeek" class="sc-fld sc-fld--full">
              <label class="sc-lbl">调整教学周 <i>*</i></label>
              <input class="sc-in" type="number" min="1" v-model.number="form.targetStartWeek" :disabled="Boolean(lockedOccurrenceWeek)" placeholder="请选择只调整哪一周" />
              <small>本次只调整这一周的该课次，其余周次保持原课表不变。</small>
            </div>
            <template v-else-if="adjustScope === 'RANGE'">
              <div class="sc-fld">
                <label class="sc-lbl">起始周 <i>*</i></label>
                <input class="sc-in" type="number" min="1" v-model.number="form.targetStartWeek" />
              </div>
              <div class="sc-fld">
                <label class="sc-lbl">结束周 <i>*</i></label>
                <input class="sc-in" type="number" min="1" v-model.number="form.targetEndWeek" />
              </div>
              <div class="sc-fld">
                <label class="sc-lbl">单双周</label>
                <AppSelect v-model="form.targetWeekParity" :options="weekParityOptions" placeholder="沿用原课位" />
              </div>
            </template>
          </template>
          <div class="sc-fld">
            <label class="sc-lbl">目标教室</label>
            <input class="sc-in" v-model.trim="form.targetClassroom" placeholder="默认沿用原教室" />
          </div>

          <div class="sc-fld sc-fld--full sc-conflict">
            <AppButton :disabled="!canCheckConflict" :loading="checkingConflict" @click="checkConflict">
              检测冲突
            </AppButton>
            <p v-if="conflictError" class="sc-conflict__bad" role="alert">{{ conflictError }}</p>
            <p v-else-if="conflictResult === undefined" class="sc-conflict__hint">
              检测教师、班级和教室冲突；提交时仍由服务端复核。
            </p>
            <p v-else-if="conflictResult === null" class="sc-conflict__ok">✓ 目标课位暂无冲突</p>
            <p v-else-if="conflictResult" class="sc-conflict__bad">
              ✗ 冲突（{{ conflictTypeLabel(conflictResult.type) }}）：{{ conflictResult.detail }}
            </p>
          </div>
        </template>

        <div class="sc-fld sc-fld--full">
          <label class="sc-lbl">{{ form.changeType === 'STOP' ? '停课后续安排' : '补课/备注说明' }}
            <i v-if="form.changeType === 'STOP'">*</i></label>
          <input ref="makeupInput" class="sc-in" v-model.trim="form.makeupPlan" placeholder="停课须填写补课/后续安排" />
          <AppQuickPhrases scene-key="aa.schedchg.makeup" @pick="onPickMakeup" />
        </div>

        <p v-if="err" class="sc-err">{{ err }}</p>
        <div class="sc-btns">
          <AppButton @click="$router.back()">取消</AppButton>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting || !!unconfirmed">{{ unconfirmed ? '结果待核对' : '提交申请' }}</button>
        </div>
      </form>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
/** 发起调停课（/admin/academic-affairs/schedule-change/apply）：提交即冲突预检，冲突后端 409 → 单据不落库。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppQuickPhrases, AppSelect, AppSectionCard } from '@/components/common'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { scheduleChangeApi, CHANGE_TYPES } from '@/modules/academicAffairs/api/academic-schedule-change.api'
import { toast } from '@/utils/toast'
import { currentUserFromToken } from '@/services/http/client'
import { systemConfirm } from '@/services/systemDialog'
import { readUnconfirmedWrite, markUnconfirmedWrite, clearUnconfirmedWrite, isDefiniteWriteRejection } from '../components/parallel-b/unconfirmedWrite'

const EMPTY = () => ({
  changeType: 'ADJUST', originItemId: '', reason: '',
  targetWeekday: null, targetSlotNo: null, targetStartWeek: null, targetEndWeek: null,
  targetWeekParity: '', targetClassroom: '', makeupPlan: ''
})

export default {
  name: 'AaScheduleChangeApplyView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppButton, AppQuickPhrases, AppSelect, AppSectionCard },
  props: { ctx: { type: Object, default: () => ({}) } },
  data() {
    return {
      CHANGE_TYPES, form: EMPTY(), adjustScope: '', submitting: false, err: '',
      checkingConflict: false, origin: null, originLoading: false, originError: '',
      receipt: null, unconfirmed: null, unconfirmedDraft: null,
      originSeq: 0, conflictSeq: 0, submitSeq: 0, conflictError: '',
      // undefined=未检测；null=检测通过无冲突；对象={type,conflictWith,detail}=有冲突
      conflictResult: undefined
    }
  },
  created() {
    const query = this.$route?.query || {}
    this.form.originItemId = String(query.originItemId || '').trim()
    const requestedType = String(query.changeType || '').toUpperCase()
    if (CHANGE_TYPES.some((item) => item.value === requestedType)) this.form.changeType = requestedType
    this.restoreUnconfirmed()
    if (this.form.originItemId) this.loadOrigin()
  },
  beforeUnmount() { this.originSeq++; this.conflictSeq++; this.submitSeq++ },
  async beforeRouteLeave() {
    if (this.submitting) return false
    return !this.form.reason && !this.form.makeupPlan || await systemConfirm({ title:'确认离开调课申请', message:'当前调整内容尚未提交，离开后填写内容会丢失。', confirmText:'放弃并离开', type:'danger' })
  },
  async beforeRouteUpdate(to, from) {
    if (to.query.originItemId === from.query.originItemId) return true
    if (this.submitting) return false
    return !this.form.reason && !this.form.makeupPlan || await systemConfirm({ title:'确认切换课位', message:'切换课位将放弃尚未提交的调整内容。', confirmText:'放弃并切换', type:'danger' })
  },
  computed: {
    submissionKey() {
      const user = currentUserFromToken() || {}
      return JSON.stringify([user.tenantId, user.userId, user.activeContextId, user.currentRoleCode || this.ctx?.currentRole?.roleCode, this.form.originItemId, 'schedule-change.submit'])
    },
    identityKey() { return JSON.stringify([currentUserFromToken(), this.ctx?.currentRole, this.ctx?.dataScope]) },
    conflictKey() {
      const f = this.form
      return JSON.stringify([this.identityKey, f.originItemId, f.changeType, f.targetWeekday, f.targetSlotNo, f.targetStartWeek, f.targetEndWeek, f.targetWeekParity, f.targetClassroom])
    },
    weekdayOptions() { return Array.from({ length: 7 }, (_, i) => ({ value: i + 1, label: `周${i + 1}` })) },
    weekParityOptions() {
      return [
        { value: 'ALL', label: '全周' },
        { value: 'ODD', label: '单周' },
        { value: 'EVEN', label: '双周' }
      ]
    },
    roleName() { return this.ctx?.currentRole?.roleName || '任课教师' },
    lockedOccurrenceWeek() {
      if (this.form.changeType !== 'ADJUST' || !this.origin) return null
      const week = Number(this.$route?.query?.occurrenceWeek || 0)
      return week >= Number(this.origin.startWeek || 0) && week <= Number(this.origin.endWeek || 0) ? week : null
    },
    scopeName() { return this.ctx?.dataScope?.scopeName || '本人课位' },
    stages() { return ['正式课位', '发起申请', '冲突预检', '审批生效', '通知回执'] },
    flowIndex() {
      if (this.receipt) return 4
      if (this.origin && this.conflictResult !== undefined) return 3
      if (this.origin) return 2
      return 1
    },
    canCheckConflict() {
      if (!this.form.originItemId || !this.form.targetWeekday || !this.form.targetSlotNo) return false
      const startWeek = Number(this.form.targetStartWeek || 0)
      const endWeek = Number(this.form.targetEndWeek || 0)
      if (this.form.changeType === 'MAKEUP') return startWeek > 0 && endWeek === startWeek
      if (this.form.changeType !== 'ADJUST') return false
      if (!this.adjustScope && !this.lockedOccurrenceWeek) return false
      return startWeek > 0 && endWeek >= startWeek
    }
  },
  watch: {
    '$route.query.originItemId'(value) {
      this.originSeq++; this.conflictSeq++
      this.form = EMPTY(); this.origin = null; this.originError = ''; this.err = ''; this.receipt = null
      this.form.originItemId = String(value || '').trim()
      this.originLoading = false
      this.restoreUnconfirmed()
      if (this.form.originItemId) this.loadOrigin()
    },
    identityKey() {
      this.originSeq++; this.conflictSeq++; this.submitSeq++
      this.form = EMPTY(); this.adjustScope = ''; this.origin = null; this.receipt = null
      this.unconfirmed = null; this.unconfirmedDraft = null
      this.originLoading = false; this.checkingConflict = false; this.submitting = false
      this.originError = ''; this.err = ''; this.conflictError = ''; this.conflictResult = undefined
    },
    conflictKey() { this.conflictSeq++; this.checkingConflict = false; this.conflictError = ''; this.conflictResult = undefined },
    // 目标字段变化后旧的预检结果失效，避免用户误以为仍然有效
    'form.changeType'(value) {
      this.conflictResult = undefined
      if (!this.origin) return
      if (value === 'ADJUST') {
        const requestedWeek = Number(this.$route?.query?.occurrenceWeek || 0)
        const inside = requestedWeek >= Number(this.origin.startWeek || 0) && requestedWeek <= Number(this.origin.endWeek || 0)
        if (inside || Number(this.origin.startWeek) === Number(this.origin.endWeek)) {
          const single = inside ? requestedWeek : Number(this.origin.startWeek)
          this.adjustScope = 'OCCURRENCE'
          this.form.targetStartWeek = single
          this.form.targetEndWeek = single
        } else {
          this.adjustScope = ''
          this.form.targetStartWeek = null
          this.form.targetEndWeek = null
        }
        this.form.targetWeekParity = this.origin.weekParity || 'ALL'
        return
      }
      const requestedWeek = Number(this.$route?.query?.occurrenceWeek || 0)
      const inside = requestedWeek >= Number(this.origin.startWeek || 0) && requestedWeek <= Number(this.origin.endWeek || 0)
      const single = inside ? requestedWeek : (Number(this.origin.startWeek) === Number(this.origin.endWeek) ? Number(this.origin.startWeek) : null)
      this.form.targetStartWeek = single
      this.form.targetEndWeek = single
      this.form.targetWeekParity = value === 'MAKEUP' ? 'ALL' : (this.origin.weekParity || 'ALL')
    },
    'form.originItemId'() { this.conflictResult = undefined },
    'form.targetWeekday'() { this.conflictResult = undefined },
    'form.targetSlotNo'() { this.conflictResult = undefined },
    'form.targetStartWeek'() { this.conflictResult = undefined },
    'form.targetEndWeek'() { this.conflictResult = undefined },
    'form.targetWeekParity'() { this.conflictResult = undefined },
    'form.targetClassroom'() { this.conflictResult = undefined },
    adjustScope(value) {
      this.conflictResult = undefined
      if (!this.origin || this.form.changeType !== 'ADJUST' || this.lockedOccurrenceWeek) return
      if (value === 'OCCURRENCE') {
        this.form.targetStartWeek = null
        this.form.targetEndWeek = null
        this.form.targetWeekParity = this.origin.weekParity || 'ALL'
      } else if (value === 'RANGE') {
        this.form.targetStartWeek = this.origin.startWeek || null
        this.form.targetEndWeek = this.origin.endWeek || null
        this.form.targetWeekParity = this.origin.weekParity || 'ALL'
      }
    }
  },
  methods: {
    restoreUnconfirmed() {
      this.unconfirmedDraft = null
      try { this.unconfirmed = readUnconfirmedWrite(this.submissionKey) }
      catch { this.err = '无法读取提交核对记录，暂不能提交，请恢复浏览器存储后重试' }
    },
    conflictTypeLabel(t) { return { TEACHER: '教师冲突', CLASS: '班级冲突', CLASSROOM: '教室冲突' }[t] || (t ? '类型待确认' : '—') },
    weekdayLabel(value) { return `周${'一二三四五六日'[Number(value) - 1] || (value ? '待确认' : '')}` },
    parityLabel(value) { return { ALL: '全周', ODD: '单周', EVEN: '双周' }[value] || '全周' },
    flowClass(index) { return { 'is-done': index < this.flowIndex, 'is-active': index === this.flowIndex } },
    flowNote(index) {
      if (index < this.flowIndex) return '已核对'
      if (index > this.flowIndex) return '等待前序完成'
      return ['请从本人课表选择', '当前设计与填写', '按真实课位校验', '等待当前岗位审核', '按真实状态解锁'][index - 1]
    },
    openMySchedule() { this.$router.push('/admin/academic-affairs/schedule/teacher') },
    async loadOrigin() {
      if (!this.form.originItemId) return
      const seq = ++this.originSeq
      const id = this.form.originItemId
      const identity = this.identityKey
      const current = () => seq === this.originSeq && id === this.form.originItemId && identity === this.identityKey
      this.originLoading = true
      this.originError = ''
      this.origin = null
      try {
      const res = await scheduleChangeApi.originItem(this.form.originItemId)
      if (!current()) return
      if (res.code !== 0) {
        this.origin = null
        this.originError = res.message || '原课位已发生变化，请返回本人课表重新选择'
        return
      }
      this.origin = res.data
      const requestedWeek = Number(this.$route?.query?.occurrenceWeek || 0)
      const singleWeek = requestedWeek >= Number(res.data.startWeek || 0) && requestedWeek <= Number(res.data.endWeek || 0)
        ? requestedWeek
        : (Number(res.data.startWeek) === Number(res.data.endWeek) ? Number(res.data.startWeek) : null)
      if (this.form.changeType === 'ADJUST') {
        if (singleWeek != null) {
          this.adjustScope = 'OCCURRENCE'
          this.form.targetStartWeek = singleWeek
          this.form.targetEndWeek = singleWeek
        } else {
          this.adjustScope = ''
          this.form.targetStartWeek = null
          this.form.targetEndWeek = null
        }
        this.form.targetWeekParity = res.data.weekParity || 'ALL'
      } else {
        this.form.targetStartWeek = singleWeek
        this.form.targetEndWeek = singleWeek
        this.form.targetWeekParity = this.form.changeType === 'MAKEUP' ? 'ALL' : (res.data.weekParity || 'ALL')
      }
      this.form.targetClassroom = res.data.classroom || ''
      } catch (e) {
        if (current()) this.originError = e?.message || '原课位加载失败，请重试'
      } finally { if (current()) this.originLoading = false }
    },
    onPickReason(text) {
      const el = this.$refs.reasonInput
      const { value, selStart, selEnd } = insertAtCursor(el, this.form.reason, text)
      this.form.reason = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    onPickMakeup(text) {
      const el = this.$refs.makeupInput
      const { value, selStart, selEnd } = insertAtCursor(el, this.form.makeupPlan, text)
      this.form.makeupPlan = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    normalizeOccurrenceFields() {
      if (!['STOP', 'MAKEUP'].includes(this.form.changeType)) return
      const week = Number(this.form.targetStartWeek || 0)
      this.form.targetEndWeek = week > 0 ? week : null
      this.form.targetWeekParity = this.form.changeType === 'MAKEUP' ? 'ALL' : (this.origin?.weekParity || 'ALL')
    },
    async checkConflict() {
      this.normalizeOccurrenceFields()
      if (!this.canCheckConflict) return
      const seq = ++this.conflictSeq
      const key = this.conflictKey
      const current = () => seq === this.conflictSeq && key === this.conflictKey
      this.checkingConflict = true
      this.conflictError = ''
      this.conflictResult = undefined
      try {
        const res = await scheduleChangeApi.conflictCheck({
          originItemId: this.form.originItemId,
          changeType: this.form.changeType,
          targetWeekday: this.form.targetWeekday,
          targetSlotNo: this.form.targetSlotNo,
          targetStartWeek: this.form.targetStartWeek || undefined,
          targetEndWeek: this.form.targetEndWeek || undefined,
          targetWeekParity: this.form.targetWeekParity || undefined,
          targetClassroom: this.form.targetClassroom || undefined
        })
        if (!current()) return
        this.conflictResult = res.code === 0 ? (res.data.conflict || null) : undefined
        if (res.code !== 0) this.conflictError = res.message || '冲突检测失败，请重试'
      } catch (e) {
        if (current()) this.conflictError = e?.message || '冲突检测失败，请重试'
      } finally { if (seq === this.conflictSeq) this.checkingConflict = false }
    },
    validate() {
      this.normalizeOccurrenceFields()
      if (!this.form.originItemId || !this.origin) return '请从本人课表重新选择要变更的课位'
      if (!this.form.reason || this.form.reason.length < 5) return '原因必填且不少于 5 字'
      if (this.form.changeType !== 'STOP' && (!this.form.targetWeekday || !this.form.targetSlotNo)) return '调课/补课须填写目标星期与节次'
      if (this.form.changeType === 'ADJUST' && !this.adjustScope && !this.lockedOccurrenceWeek) return '请选择“只调整一次课”或“调整周期课表”'
      if (this.form.changeType === 'ADJUST' && this.adjustScope === 'OCCURRENCE' && !Number(this.form.targetStartWeek || 0)) return '请选择具体调整教学周'
      if (['STOP', 'MAKEUP'].includes(this.form.changeType) && !Number(this.form.targetStartWeek || 0)) return this.form.changeType === 'STOP' ? '请选择具体停课教学周' : '请选择具体补课教学周'
      if (this.form.changeType === 'STOP' && !this.form.makeupPlan) return '停课须填写补课/后续安排'
      return ''
    },
    async onSubmit() {
      if (this.submitting) return
      try { this.unconfirmed = readUnconfirmedWrite(this.submissionKey) || this.unconfirmed }
      catch { this.err = '无法读取提交核对记录，暂不能提交，请恢复浏览器存储后重试'; return }
      if (this.unconfirmed) { this.err = '提交结果未确认，请先核对原申请，不能重复提交'; return }
      this.err = this.validate()
      if (this.err) return
      const seq = ++this.submitSeq
      const identity = this.identityKey
      const submittedForm = JSON.stringify(this.form)
      const courseName = this.origin.courseName
      const originId = this.form.originItemId
      const operationKey = this.submissionKey
      const marker = { originItemId: originId, startedAt: Date.now() }
      const current = () => seq === this.submitSeq && identity === this.identityKey && originId === this.form.originItemId
      this.submitting = true
      try {
        // Persist before sending so reload/back navigation cannot silently enable another POST.
        try { markUnconfirmedWrite(operationKey, marker) }
        catch { this.err = '无法保存提交核对记录，本次尚未发送，请恢复浏览器存储后重试'; return }
        this.normalizeOccurrenceFields()
        const body = { ...this.form }
        if (body.changeType === 'STOP') {
          delete body.targetWeekday; delete body.targetSlotNo; delete body.targetClassroom
        }
        if (!body.targetWeekParity) delete body.targetWeekParity
        const res = await scheduleChangeApi.submit(body)
        const confirmed = res?.code === 0 && !!res.data?.changeId
        const rejected = isDefiniteWriteRejection(res)
        if (confirmed || rejected) clearUnconfirmedWrite(operationKey)
        if (!current()) return
        if (confirmed) {
          this.receipt = {
            changeId: res.data.changeId,
            status: res.data.status,
            courseName: res.data.courseName || courseName || '课程',
            statusLabel: '待学院审核'
          }
          toast.success('调停课已提交，进入学院审核')
          if (JSON.stringify(this.form) === submittedForm) {
            this.form = EMPTY()
            this.origin = null
            this.conflictResult = undefined
          }
        } else if (rejected) {
          this.err = res.message || '提交失败'
          toast.error(this.err)
        } else {
          this.unconfirmed = marker
          this.unconfirmedDraft = JSON.parse(submittedForm)
          this.err = '提交结果未确认，请到台账核对原申请，不能重复提交'
        }
      } catch {
        if (current()) {
          this.unconfirmed = marker
          this.unconfirmedDraft = JSON.parse(submittedForm)
          this.err = '提交结果未确认，请先到台账核对，不能重复提交'
        }
      } finally { if (seq === this.submitSeq) this.submitting = false }
    },
    goReceipt() {
      if (!this.receipt?.changeId) return
      this.$router.push(this.receipt.status === 'APPLIED'
        ? `/admin/academic-affairs/print/schedule-change/${this.receipt.changeId}/notice`
        : `/admin/academic-affairs/schedule-change?changeId=${encodeURIComponent(this.receipt.changeId)}`)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.sc-compare { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 16px; align-items: start; }
.sc-object-context { display: grid; grid-template-columns: minmax(0, 1fr) minmax(360px, .7fr); gap: 24px; align-items: center; padding: 15px 18px; border: 1px solid var(--line, #d9dee8); border-left: 3px solid var(--pri, #2563eb); border-radius: 12px; background: var(--bg-card, #fff); }.sc-object-context strong { font-size: 16px; }.sc-object-context p { margin: 5px 0 0; color: var(--t2, #52647a); font-size: 12px; }.sc-object-context dl { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; margin: 0; }.sc-object-context dt { color: var(--t3, #94a3b8); font-size: 12px; }.sc-object-context dd { margin: 5px 0 0; font-size: 13px; font-weight: 600; }
.sc-flow-rail { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); list-style: none; margin: 0; padding: 15px 10px; background: var(--bg-card, #fff); border: 1px solid var(--line, #d9dee8); border-radius: 12px; }.sc-flow-rail li { position: relative; display: grid; justify-items: center; gap: 4px; text-align: center; color: var(--t2, #52647a); font-size: 12px; }.sc-flow-rail li::after { content: ''; position: absolute; top: 12px; left: calc(50% + 18px); width: calc(100% - 36px); height: 1px; background: var(--line, #d9dee8); }.sc-flow-rail li:last-child::after { display: none; }.sc-flow-rail b { position: relative; z-index: 1; display: grid; place-items: center; width: 24px; height: 24px; border-radius: 50%; border: 1px solid var(--line, #d9dee8); background: #f7f9fc; }.sc-flow-rail .is-done b { color: #16803c; border-color: #b7dfc2; background: #f0f9f2; }.sc-flow-rail .is-active b { color: #fff; border-color: var(--pri, #2563eb); background: var(--pri, #2563eb); }.sc-flow-rail small { color: var(--t3, #94a3b8); }
.sc-unconfirmed { padding: 16px; border: 1px solid #e7b95d; border-radius: 12px; background: #fffbeb; }
.sc-unconfirmed p { margin: 8px 0; font-size: 13px; }
.sc-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; padding: 18px; border: 1px solid var(--line, #d9dee8); border-radius: 12px; background: var(--bg-card, #fff); }
.sc-form__title { grid-column: 1 / -1; font-size: 16px; margin: 0; padding-bottom: 12px; border-bottom: 1px solid var(--line, #d9dee8); }
.sc-in { min-height: 36px; }
.sc-fld { display: flex; flex-direction: column; gap: 4px; }
.sc-fld--full { grid-column: 1 / -1; }
.sc-lbl { font-size: 12px; color: var(--t2, #475569); }
.sc-lbl i { color: var(--danger, #dc2626); font-style: normal; }
.sc-in { width: 100%; padding: 7px 10px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; font-size: 13px; box-sizing: border-box; }
.sc-hint { font-size: 11px; color: var(--t3, #94a3b8); margin: 2px 0 0; }
.sc-occurrence-lock { padding: 10px 12px; border: 1px solid var(--pri, #2563eb); border-radius: 8px; background: var(--pri-bg, #eef5ff); color: var(--t2, #52647a); font-size: 12px; line-height: 1.6; }
.sc-radio { display: flex; gap: var(--space-4); font-size: 13px; padding-top: 4px; }
.sc-conflict { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.sc-conflict__hint { margin: 0; font-size: 12px; color: var(--t3, #94a3b8); }
.sc-conflict__ok { margin: 0; font-size: 13px; color: var(--success, #16a34a); font-weight: 600; }
.sc-conflict__bad { margin: 0; font-size: 13px; color: var(--danger, #dc2626); font-weight: 600; }
.sc-err { grid-column: 1 / -1; color: var(--danger, #dc2626); font-size: 12px; margin: 0; }
.sc-btns { grid-column: 1 / -1; display: flex; justify-content: flex-end; gap: var(--space-2); }
.sc-origin-card { max-width: 900px; }
.sc-origin { display: grid; grid-template-columns: 1fr; gap: 20px; align-items: start; }
.sc-origin strong { font-size: 17px; color: var(--text-900, #1f2329); }
.sc-origin p { margin: 5px 0 0; color: var(--text-500, #86909c); font-size: 13px; }
.sc-origin dl { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 18px; margin: 0; }
.sc-origin dl div { min-width: 0; }
.sc-origin dt { color: var(--text-500, #86909c); font-size: 11px; }
.sc-origin dd { margin: 3px 0 0; color: var(--text-800, #272e3b); font-size: 13px; }
.sc-receipt { display: grid; grid-template-columns: minmax(0,1fr) auto auto auto; align-items: center; gap: 18px; max-width: 900px; padding: 13px 15px; border: 1px solid #a7d7b4; border-radius: 11px; background: #f3fbf5; }
.sc-receipt strong, .sc-receipt span, .sc-receipt small, .sc-receipt b { display: block; }.sc-receipt strong { color: #15803d; }.sc-receipt span, .sc-receipt small { margin-top: 3px; color: #64748b; font-size: 11px; }.sc-receipt b { margin-top: 3px; font-size: 12px; }.sc-receipt__actions { display: flex; gap: 8px; }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
@media (max-width: 760px) {
  .sc-object-context { grid-template-columns: 1fr; }.sc-object-context dl { grid-template-columns: 1fr; }.sc-flow-rail { grid-template-columns: 1fr; gap: 10px; }.sc-flow-rail li { justify-items: start; grid-template-columns: 26px auto; text-align: left; }.sc-flow-rail li::after { display: none; }.sc-flow-rail li small { grid-column: 2; }
  .sc-compare { grid-template-columns: 1fr; }
  .sc-form { grid-template-columns: 1fr; }
  .sc-fld--full, .sc-err, .sc-btns { grid-column: 1; }
  .sc-origin { grid-template-columns: 1fr; }
  .sc-origin dl { grid-template-columns: 1fr; }
  .sc-receipt { grid-template-columns: 1fr; gap: 10px; }
  .sc-receipt__actions { align-items: stretch; flex-direction: column; }
}
</style>
