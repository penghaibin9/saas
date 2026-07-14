<template>
  <ModulePageShell
    title="发起调停课"
    subtitle="教师就本人已发布课位发起调课/停课/补课；提交即做目标课位三重冲突预检（冲突则不予受理）"
    :role-name="roleName"
    :data-scope-name="scopeName"
  >
    <div class="mp-stack">
      <form class="sc-form" @submit.prevent="onSubmit">
        <div class="sc-fld sc-fld--full">
          <label class="sc-lbl">变更类型 <i>*</i></label>
          <div class="sc-radio">
            <label v-for="t in CHANGE_TYPES" :key="t.value">
              <input type="radio" :value="t.value" v-model="form.changeType" /> {{ t.label }}
            </label>
          </div>
        </div>

        <div class="sc-fld">
          <label class="sc-lbl">原课表项 ID <i>*</i></label>
          <input class="sc-in" v-model.trim="form.originItemId" placeholder="已发布课表中的本人课位 itemId" />
          <p class="sc-hint">从「课表·教师视图」复制原课位 itemId</p>
        </div>

        <div class="sc-fld sc-fld--full">
          <label class="sc-lbl">原因 <i>*</i>（≥5 字）</label>
          <input class="sc-in" v-model.trim="form.reason" placeholder="如：教师因公出差需调整" />
        </div>

        <template v-if="form.changeType !== 'STOP'">
          <div class="sc-fld">
            <label class="sc-lbl">目标星期 <i>*</i></label>
            <select class="sc-in" v-model.number="form.targetWeekday">
              <option v-for="d in 7" :key="d" :value="d">周{{ d }}</option>
            </select>
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
            <select class="sc-in" v-model="form.targetWeekParity">
              <option value="">沿用原课位</option>
              <option value="ALL">全周</option>
              <option value="ODD">单周</option>
              <option value="EVEN">双周</option>
            </select>
          </div>
          <div class="sc-fld">
            <label class="sc-lbl">目标教室</label>
            <input class="sc-in" v-model.trim="form.targetClassroom" placeholder="默认沿用原教室" />
          </div>
        </template>

        <div class="sc-fld sc-fld--full">
          <label class="sc-lbl">{{ form.changeType === 'STOP' ? '停课后续安排' : '补课/备注说明' }}
            <i v-if="form.changeType === 'STOP'">*</i></label>
          <input class="sc-in" v-model.trim="form.makeupPlan" placeholder="停课须填写补课/后续安排" />
        </div>

        <p v-if="err" class="sc-err">{{ err }}</p>
        <div class="sc-btns">
          <button type="button" class="mp-btn" @click="$router.back()">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">提交申请</button>
        </div>
      </form>
    </div>
  </ModulePageShell>
</template>

<script>
/** 发起调停课（/admin/academic-affairs/schedule-change/apply）：提交即冲突预检，冲突后端 409 → 单据不落库。 */
import { ModulePageShell } from '@/components/business'
import { scheduleChangeApi, CHANGE_TYPES } from '@/modules/academicAffairs/api/academic-schedule-change.api'
import { toast } from '@/utils/toast'

const EMPTY = () => ({
  changeType: 'ADJUST', originItemId: '', reason: '',
  targetWeekday: 1, targetSlotNo: null, targetStartWeek: null, targetEndWeek: null,
  targetWeekParity: '', targetClassroom: '', makeupPlan: ''
})

export default {
  name: 'AaScheduleChangeApplyView',
  components: { ModulePageShell },
  props: { ctx: { type: Object, default: () => ({}) } },
  data() { return { CHANGE_TYPES, form: EMPTY(), submitting: false, err: '' } },
  computed: {
    roleName() { return this.ctx?.currentRole?.roleName || '任课教师' },
    scopeName() { return this.ctx?.dataScope?.scopeName || '本人课位' }
  },
  methods: {
    validate() {
      if (!this.form.originItemId) return '请填写原课表项 ID'
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
          toast.success('调停课已提交，进入学院审核')
          this.$router.push('/admin/academic-affairs/schedule-change')
        } else {
          this.err = res.message || '提交失败'
          toast.error(this.err)
        }
      } finally { this.submitting = false }
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
.sc-err { grid-column: 1 / -1; color: var(--danger, #dc2626); font-size: 12px; margin: 0; }
.sc-btns { grid-column: 1 / -1; display: flex; justify-content: flex-end; gap: var(--space-2); }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
