<template>
  <ModulePageShell
    title="发起调停课"
    subtitle="教师就本人已发布课位发起调课/停课/补课；提交即做目标课位三重冲突预检（冲突则不予受理）"
    :role-name="roleName"
    :data-scope-name="scopeName"
  >
    <div class="mp-stack">
      <section v-if="receipt" class="sc-receipt" role="status">
        <div><strong>✓ 调停课申请已提交</strong><span>{{ receipt.courseName }} · 单据 {{ receipt.changeId }}</span></div>
        <div><small>当前结果</small><b>{{ receipt.statusLabel }}</b></div>
        <div><small>下一责任</small><b>学院教务审核人</b></div>
        <div class="sc-receipt__actions">
          <AppButton size="small" variant="ghost" @click="goReceipt">查看申请详情</AppButton>
          <AppButton size="small" @click="openMySchedule">继续从课表选择</AppButton>
        </div>
      </section>
      <AppSectionCard title="原安排" class="sc-origin-card">
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
          <input ref="reasonInput" class="sc-in" v-model.trim="form.reason" placeholder="如：教师因公出差需调整" />
          <AppQuickPhrases scene-key="aa.schedchg.reason" @pick="onPickReason" />
        </div>

        <template v-if="form.changeType !== 'STOP'">
          <div class="sc-fld">
            <label class="sc-lbl">目标星期 <i>*</i></label>
            <AppSelect v-model="form.targetWeekday" :options="weekdayOptions" />
          </div>
          <div class="sc-fld">
            <label class="sc-lbl">目标节次 <i>*</i></label>
            <input class="sc-in" type="number" min="1" v-model.number="form.targetSlotNo" />
          </div>
          <div class="sc-fld">
            <label class="sc-lbl">起始周</label>
            <input class="sc-in" type="number" min="1" v-model.number="form.targetStartWeek" placeholder="默认沿用原课位" />
          </div>
          <div class="sc-fld">
            <label class="sc-lbl">结束周</label>
            <input class="sc-in" type="number" min="1" v-model.number="form.targetEndWeek" placeholder="默认沿用原课位" />
          </div>
          <div class="sc-fld">
            <label class="sc-lbl">单双周</label>
            <AppSelect v-model="form.targetWeekParity" :options="weekParityOptions" placeholder="沿用原课位" />
          </div>
          <div class="sc-fld">
            <label class="sc-lbl">目标教室</label>
            <input class="sc-in" v-model.trim="form.targetClassroom" placeholder="默认沿用原教室" />
          </div>

          <div class="sc-fld sc-fld--full sc-conflict">
            <AppButton :disabled="!canCheckConflict" :loading="checkingConflict" @click="checkConflict">
              检测冲突
            </AppButton>
            <p v-if="conflictResult === undefined" class="sc-conflict__hint">
              先检测目标课位是否冲突，提交时仍会做同一算法的强制校验（预检失败不阻止提交）
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
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">提交申请</button>
        </div>
      </form>
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
      CHANGE_TYPES, form: EMPTY(), submitting: false, err: '',
      checkingConflict: false, origin: null, originLoading: false, originError: '',
      receipt: null,
      // undefined=未检测；null=检测通过无冲突；对象={type,conflictWith,detail}=有冲突
      conflictResult: undefined
    }
  },
  created() {
    const query = this.$route?.query || {}
    this.form.originItemId = String(query.originItemId || '').trim()
    const requestedType = String(query.changeType || '').toUpperCase()
    if (CHANGE_TYPES.some((item) => item.value === requestedType)) this.form.changeType = requestedType
    if (this.form.originItemId) this.loadOrigin()
  },
  computed: {
    weekdayOptions() { return Array.from({ length: 7 }, (_, i) => ({ value: i + 1, label: `周${i + 1}` })) },
    weekParityOptions() {
      return [
        { value: 'ALL', label: '全周' },
        { value: 'ODD', label: '单周' },
        { value: 'EVEN', label: '双周' }
      ]
    },
    roleName() { return this.ctx?.currentRole?.roleName || '任课教师' },
    scopeName() { return this.ctx?.dataScope?.scopeName || '本人课位' },
    canCheckConflict() {
      return !!(this.form.originItemId && this.form.targetWeekday && this.form.targetSlotNo)
    }
  },
  watch: {
    // 目标字段变化后旧的预检结果失效，避免用户误以为仍然有效
    'form.originItemId'() { this.conflictResult = undefined },
    'form.targetWeekday'() { this.conflictResult = undefined },
    'form.targetSlotNo'() { this.conflictResult = undefined },
    'form.targetStartWeek'() { this.conflictResult = undefined },
    'form.targetEndWeek'() { this.conflictResult = undefined },
    'form.targetWeekParity'() { this.conflictResult = undefined },
    'form.targetClassroom'() { this.conflictResult = undefined }
  },
  methods: {
    conflictTypeLabel(t) { return { TEACHER: '教师冲突', CLASS: '班级冲突', CLASSROOM: '教室冲突' }[t] || t },
    weekdayLabel(value) { return `周${'一二三四五六日'[Number(value) - 1] || value || ''}` },
    parityLabel(value) { return { ALL: '全周', ODD: '单周', EVEN: '双周' }[value] || '全周' },
    openMySchedule() { this.$router.push('/admin/academic-affairs/schedule/teacher') },
    async loadOrigin() {
      if (!this.form.originItemId) return
      this.originLoading = true
      this.originError = ''
      const res = await scheduleChangeApi.originItem(this.form.originItemId)
      this.originLoading = false
      if (res.code !== 0) {
        this.origin = null
        this.originError = res.message || '原课位已发生变化，请返回本人课表重新选择'
        return
      }
      this.origin = res.data
      this.form.targetStartWeek = res.data.startWeek || null
      this.form.targetEndWeek = res.data.endWeek || null
      this.form.targetWeekParity = res.data.weekParity || 'ALL'
      this.form.targetClassroom = res.data.classroom || ''
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
    async checkConflict() {
      if (!this.canCheckConflict) return
      this.checkingConflict = true
      try {
        const res = await scheduleChangeApi.conflictCheck({
          originItemId: this.form.originItemId,
          targetWeekday: this.form.targetWeekday,
          targetSlotNo: this.form.targetSlotNo,
          targetStartWeek: this.form.targetStartWeek || undefined,
          targetEndWeek: this.form.targetEndWeek || undefined,
          targetWeekParity: this.form.targetWeekParity || undefined,
          targetClassroom: this.form.targetClassroom || undefined
        })
        // 预检失败（含越权/网络异常）不阻断表单：静默保持"未检测"，仍可正常提交由后端把关（卡07 §5.2）
        this.conflictResult = res.code === 0 ? (res.data.conflict || null) : undefined
      } finally { this.checkingConflict = false }
    },
    validate() {
      if (!this.form.originItemId || !this.origin) return '请从本人课表重新选择要变更的课位'
      if (!this.form.reason || this.form.reason.length < 5) return '原因必填且不少于 5 字'
      if (this.form.changeType !== 'STOP' && (!this.form.targetWeekday || !this.form.targetSlotNo)) return '调课/补课须填写目标星期与节次'
      if (this.form.changeType === 'STOP' && !this.form.makeupPlan) return '停课须填写补课/后续安排'
      return ''
    },
    async onSubmit() {
      this.err = this.validate()
      if (this.err) return
      this.submitting = true
      try {
        const body = { ...this.form }
        if (body.changeType === 'STOP') {
          delete body.targetWeekday; delete body.targetSlotNo; delete body.targetStartWeek
          delete body.targetEndWeek; delete body.targetWeekParity; delete body.targetClassroom
        }
        if (!body.targetWeekParity) delete body.targetWeekParity
        const res = await scheduleChangeApi.submit(body)
        if (res.code === 0) {
          this.receipt = {
            changeId: res.data.changeId,
            courseName: res.data.courseName || this.origin.courseName || '课程',
            statusLabel: '待学院审核'
          }
          toast.success('调停课已提交，进入学院审核')
          this.form = EMPTY()
          this.origin = null
          this.conflictResult = undefined
        } else {
          this.err = res.message || '提交失败'
          toast.error(this.err)
        }
      } finally { this.submitting = false }
    },
    goReceipt() {
      if (!this.receipt?.changeId) return
      this.$router.push(`/admin/academic-affairs/print/schedule-change/${this.receipt.changeId}/notice`)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.sc-form { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: var(--space-3); max-width: 900px; }
.sc-fld { display: flex; flex-direction: column; gap: 4px; }
.sc-fld--full { grid-column: 1 / -1; }
.sc-lbl { font-size: 12px; color: var(--t2, #475569); }
.sc-lbl i { color: var(--danger, #dc2626); font-style: normal; }
.sc-in { width: 100%; padding: 7px 10px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; font-size: 13px; box-sizing: border-box; }
.sc-hint { font-size: 11px; color: var(--t3, #94a3b8); margin: 2px 0 0; }
.sc-radio { display: flex; gap: var(--space-4); font-size: 13px; padding-top: 4px; }
.sc-conflict { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.sc-conflict__hint { margin: 0; font-size: 12px; color: var(--t3, #94a3b8); }
.sc-conflict__ok { margin: 0; font-size: 13px; color: var(--success, #16a34a); font-weight: 600; }
.sc-conflict__bad { margin: 0; font-size: 13px; color: var(--danger, #dc2626); font-weight: 600; }
.sc-err { grid-column: 1 / -1; color: var(--danger, #dc2626); font-size: 12px; margin: 0; }
.sc-btns { grid-column: 1 / -1; display: flex; justify-content: flex-end; gap: var(--space-2); }
.sc-origin-card { max-width: 900px; }
.sc-origin { display: grid; grid-template-columns: minmax(180px, 1fr) minmax(0, 2fr); gap: 24px; align-items: start; }
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
  .sc-form { grid-template-columns: 1fr; }
  .sc-fld--full, .sc-err, .sc-btns { grid-column: 1; }
  .sc-origin { grid-template-columns: 1fr; }
  .sc-origin dl { grid-template-columns: 1fr; }
  .sc-receipt { grid-template-columns: 1fr; gap: 10px; }
  .sc-receipt__actions { align-items: stretch; flex-direction: column; }
}
</style>
