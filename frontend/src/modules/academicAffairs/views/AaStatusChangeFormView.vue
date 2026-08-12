<template>
  <ModulePageShell
    title="发起学籍异动"
    subtitle="先看清当前与目标，再选择生效方式；终审仍只走教务正式异动链"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="goBack">返回列表</AppButton>
    </template>

    <AppSectionCard title="异动信息">
      <div class="aa-form">
        <div class="aa-form__row">
          <label class="aa-form__label required">学生</label>
          <div class="aa-form__field">
            <AppStudentPicker v-model="form.studentId" placeholder="选择发起异动的学生" @change="onStudentChange" />
            <div v-if="loadingStudent" class="aa-form__hint">正在读取当前学籍组织与状态…</div>
          </div>
        </div>

        <div class="aa-form__row">
          <label class="aa-form__label required">异动类型</label>
          <div class="aa-form__field">
            <AppSelect v-if="!lockedType" v-model="form.changeType" :options="changeTypeOptions" placeholder="" />
            <div v-else class="aa-picked">{{ TYPE_LABEL[form.changeType] || form.changeType }}</div>
            <div class="aa-form__hint">{{ typeHint }}</div>
          </div>
        </div>

        <div v-if="form.studentId" class="aa-transition" aria-label="学籍异动前后对照">
          <section class="aa-transition__card">
            <div class="aa-transition__eyebrow">当前</div>
            <strong class="aa-transition__title">{{ form.name || '已选学生' }}</strong>
            <dl class="aa-transition__grid">
              <div><dt>学院</dt><dd>{{ form.currentCollegeName || '—' }}</dd></div>
              <div><dt>专业</dt><dd>{{ form.studentMajorName || '—' }}</dd></div>
              <div><dt>班级</dt><dd>{{ form.currentClassName || '未编班' }}</dd></div>
              <div><dt>状态</dt><dd>{{ form.currentStatusLabel || '—' }}</dd></div>
            </dl>
          </section>
          <div class="aa-transition__arrow" aria-hidden="true">→</div>
          <section class="aa-transition__card aa-transition__card--target">
            <div class="aa-transition__eyebrow">目标</div>
            <strong class="aa-transition__title">{{ TYPE_LABEL[form.changeType] || form.changeType }}</strong>
            <dl class="aa-transition__grid">
              <div><dt>学院</dt><dd>{{ targetCollegeName }}</dd></div>
              <div><dt>专业</dt><dd>{{ targetMajorName }}</dd></div>
              <div><dt>班级</dt><dd>{{ targetClassName }}</dd></div>
              <div><dt>状态</dt><dd>{{ targetStatusLabel }}</dd></div>
            </dl>
          </section>
        </div>

        <template v-if="form.changeType === 'TRANSFER_MAJOR'">
          <div class="aa-form__row">
            <label class="aa-form__label required">目标组织</label>
            <div class="aa-form__field">
              <AppOrgCascader v-model="targetOrg" @change="onTargetOrgChange" />
              <div class="aa-form__hint">按学院 → 专业 → 班级逐级选择；专业必选，班级可由教务后续编排。</div>
            </div>
          </div>
        </template>

        <template v-if="form.changeType === 'TRANSFER_CLASS'">
          <div class="aa-form__row">
            <label class="aa-form__label required">转入班级</label>
            <div class="aa-form__field">
              <AppClassPicker
                v-model="form.toClassId"
                :options="targetClassPickerOptions"
                :placeholder="classSelectPlaceholder"
                :disabled="!form.studentId || loadingClasses"
              />
              <div class="aa-form__hint">仅同专业在读班级可选，跨专业请改用「转专业申请」；当前班级不会出现在候选内。</div>
            </div>
          </div>
        </template>

        <div class="aa-form__row">
          <label class="aa-form__label required">生效方式</label>
          <div class="aa-form__field">
            <div class="aa-radio-group">
              <label class="aa-radio">
                <input v-model="form.effectiveMode" type="radio" value="IMMEDIATE" />
                <span><strong>终审通过立即生效</strong><small>沿用现有正式异动入口</small></span>
              </label>
              <label class="aa-radio">
                <input v-model="form.effectiveMode" type="radio" value="SCHEDULED" />
                <span><strong>指定日期</strong><small>终审通过后等待计划时间，由 future-effective worker 生效</small></span>
              </label>
            </div>
            <div v-if="form.effectiveMode === 'SCHEDULED'" class="aa-effective-date">
              <input v-model="form.effectiveDate" class="aa-input" type="datetime-local" :min="minEffectiveDate" />
              <div class="aa-form__hint">必须晚于当前时间；到期前学生主档状态不会被提前改写。</div>
            </div>
          </div>
        </div>

        <div class="aa-form__row">
          <label class="aa-form__label">申请原因</label>
          <div class="aa-form__field">
            <textarea ref="reasonInput" v-model.trim="form.reason" class="aa-textarea" rows="3" maxlength="500" placeholder="选填，便于审批参考"></textarea>
            <AppQuickPhrases v-if="reasonPhraseScene" :scene-key="reasonPhraseScene" :group="form.changeType" @pick="onPickReason" />
          </div>
        </div>
      </div>

      <div class="aa-form__actions">
        <AppButton @click="goBack">取消</AppButton>
        <AppButton variant="primary" :disabled="!canSubmit" :loading="submitting" @click="submit">
          {{ form.effectiveMode === 'SCHEDULED' ? '提交计划生效异动' : '提交异动' }}
        </AppButton>
      </div>
    </AppSectionCard>
  </ModulePageShell>
</template>

<script>
/** D3-U 学籍异动便利性工作台。
 *  当前学籍事实只读 GET /roster/{id}；立即写入仍 POST /status-changes；
 *  指定日期只切换到既有 POST /status-changes/scheduled，不复制状态机与事实链。 */
import { ModulePageShell } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppQuickPhrases, AppSelect, AppStudentPicker, AppClassPicker, AppOrgCascader } from '@/components/common'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { hasGroupPhrases } from '@/utils/quickPhrases'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { statusChangeConvenienceApi } from '@/modules/academicAffairs/api/status-change-convenience.api'
import { TYPE_LABEL, TYPE_PATH_SEGMENT } from '@/modules/academicAffairs/constants/status-change'
import { toast } from '@/utils/toast'

const TYPE_HINT = {
  SUSPEND: '仅在籍学生可休学；到期日按规则中心最长年限自动计算。休学≠保留学籍。',
  PRESERVE: '保留学籍：人离校、学籍保留（如应征入伍/联合培养），复学走 RESUME。',
  WITHDRAW: '退学为终态，终审生效后不可再发起其它异动。',
  RESUME: '仅休学中或保留学籍中的学生可复学；休学超最长年限不可复学。',
  RETAIN: '留级：降级继续修读，与「保留学籍」不是同一业务。',
  TRANSFER_MAJOR: '转专业：必须选择目标专业，终审生效后同步迁移主档院系班。',
  TRANSFER_CLASS: '转班：仅限同专业换班，学院/专业不变；终审生效后同步迁移主档班级。'
}

const TARGET_STATUS = {
  SUSPEND: ['SUSPENDED', '休学'],
  PRESERVE: ['PRESERVED', '保留学籍'],
  WITHDRAW: ['WITHDRAWN', '退学'],
  RESUME: ['REGISTERED', '在籍'],
  RETAIN: ['RETAINED', '留级'],
  TRANSFER_MAJOR: ['REGISTERED', '在籍'],
  TRANSFER_CLASS: ['REGISTERED', '在籍']
}

function toLocalInputMin() {
  const d = new Date(Date.now() + 60 * 1000)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export default {
  name: 'AaStatusChangeFormView',
  components: { ModulePageShell, AppButton, AppSectionCard, AppQuickPhrases, AppSelect, AppStudentPicker, AppClassPicker, AppOrgCascader },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      TYPE_LABEL,
      submitting: false,
      loadingStudent: false,
      loadingClasses: false,
      targetClassOptions: [],
      targetOrg: [],
      targetOrgItems: [],
      form: {
        studentId: this.$route.query.studentId || '',
        name: this.$route.query.name || '',
        changeType: (this.$route.query.type && TYPE_LABEL[this.$route.query.type]) ? this.$route.query.type : 'SUSPEND',
        reason: '',
        effectiveMode: 'IMMEDIATE',
        effectiveDate: '',
        toCollegeId: '',
        toMajorId: '',
        toClassId: '',
        currentCollegeId: '',
        currentCollegeName: '',
        studentMajorId: '',
        studentMajorName: '',
        currentClassId: '',
        currentClassName: '',
        currentStatus: '',
        currentStatusLabel: ''
      }
    }
  },
  computed: {
    lockedType() {
      return !!(this.$route.query.type && TYPE_LABEL[this.$route.query.type])
    },
    typeHint() {
      return TYPE_HINT[this.form.changeType] || ''
    },
    changeTypeOptions() {
      return Object.entries(TYPE_LABEL).map(([value, label]) => ({ value, label }))
    },
    reasonPhraseScene() {
      return hasGroupPhrases('aa.statuschg.reason', this.form.changeType) ? 'aa.statuschg.reason' : ''
    },
    classSelectPlaceholder() {
      if (!this.form.studentId) return '请先选择学生'
      if (this.loadingClasses) return '加载班级中…'
      if (!this.targetClassOptions.length) return '该专业下暂无其它可选班级'
      return '请选择目标班级'
    },
    targetClassPickerOptions() {
      return this.targetClassOptions.map((c) => ({ value: c.id, label: `${c.className}（${c.grade || '—'}）`, raw: c }))
    },
    targetStatusLabel() {
      return TARGET_STATUS[this.form.changeType]?.[1] || '—'
    },
    targetCollegeName() {
      if (this.form.changeType === 'TRANSFER_MAJOR') return this.targetOrgItems[0]?.label || '请选择目标学院'
      return this.form.currentCollegeName || '—'
    },
    targetMajorName() {
      if (this.form.changeType === 'TRANSFER_MAJOR') return this.targetOrgItems[1]?.label || '请选择目标专业'
      return this.form.studentMajorName || '—'
    },
    targetClassName() {
      if (this.form.changeType === 'TRANSFER_MAJOR') return this.targetOrgItems[2]?.label || '待教务编班'
      if (this.form.changeType === 'TRANSFER_CLASS') {
        const found = this.targetClassOptions.find((c) => String(c.id) === String(this.form.toClassId))
        return found?.className || '请选择目标班级'
      }
      return this.form.currentClassName || '未编班'
    },
    minEffectiveDate() {
      return toLocalInputMin()
    },
    canSubmit() {
      if (!this.form.studentId || this.loadingStudent) return false
      if (this.form.changeType === 'TRANSFER_CLASS' && !this.form.toClassId) return false
      if (this.form.changeType === 'TRANSFER_MAJOR' && !this.form.toMajorId) return false
      if (this.form.effectiveMode === 'SCHEDULED' && !this.form.effectiveDate) return false
      return true
    }
  },
  watch: {
    'form.changeType'(val) {
      this.form.toCollegeId = ''
      this.form.toMajorId = ''
      this.form.toClassId = ''
      this.targetOrg = []
      this.targetOrgItems = []
      this.targetClassOptions = []
      if (val === 'TRANSFER_CLASS' && this.form.studentId && this.form.studentMajorId) this.loadTargetClasses()
    }
  },
  created() {
    if (this.form.studentId) this.loadStudentOrgInfo()
  },
  methods: {
    onStudentChange(_value, items) {
      const selected = items?.[0]
      this.form.name = selected?.raw?.realName || selected?.label || ''
      this.resetCurrentStudentFacts()
      if (this.form.studentId) this.loadStudentOrgInfo()
    },
    resetCurrentStudentFacts() {
      this.form.currentCollegeId = ''
      this.form.currentCollegeName = ''
      this.form.studentMajorId = ''
      this.form.studentMajorName = ''
      this.form.currentClassId = ''
      this.form.currentClassName = ''
      this.form.currentStatus = ''
      this.form.currentStatusLabel = ''
      this.form.toClassId = ''
      this.targetClassOptions = []
    },
    onTargetOrgChange(values, items) {
      this.targetOrgItems = items || []
      this.form.toCollegeId = values?.[0] || ''
      this.form.toMajorId = values?.[1] || ''
      this.form.toClassId = values?.[2] || ''
    },
    onPickReason(text) {
      const el = this.$refs.reasonInput
      const { value, selStart, selEnd } = insertAtCursor(el, this.form.reason, text)
      this.form.reason = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    goBack() {
      const seg = this.lockedType && TYPE_PATH_SEGMENT[this.form.changeType]
      this.$router.push(seg ? `/admin/academic-affairs/status-changes/${seg}` : '/admin/academic-affairs/status-changes')
    },
    async loadStudentOrgInfo() {
      if (!this.form.studentId) return
      this.loadingStudent = true
      const res = await academicAffairsApi.getRosterDetail(this.form.studentId)
      this.loadingStudent = false
      if (res.code !== 0) {
        toast.error(res.message || '读取学生当前学籍信息失败')
        return
      }
      this.form.name = res.data.realName || this.form.name
      this.form.currentCollegeId = res.data.collegeId || ''
      this.form.currentCollegeName = res.data.collegeName || '（未编学院）'
      this.form.studentMajorId = res.data.majorId || ''
      this.form.studentMajorName = res.data.majorName || '（未编专业）'
      this.form.currentClassId = res.data.classId || ''
      this.form.currentClassName = res.data.className || '未编班'
      this.form.currentStatus = res.data.studentStatus || ''
      this.form.currentStatusLabel = res.data.statusLabel || res.data.studentStatus || '—'
      if (this.form.changeType === 'TRANSFER_CLASS') await this.loadTargetClasses()
    },
    async loadTargetClasses() {
      this.form.toClassId = ''
      this.targetClassOptions = []
      if (!this.form.studentMajorId) return
      this.loadingClasses = true
      const res = await academicAffairsApi.listClasses({ majorId: this.form.studentMajorId, classStatus: 'NORMAL', pageSize: 100 })
      this.targetClassOptions = res.code === 0
        ? res.data.list.filter((c) => String(c.id) !== String(this.form.currentClassId))
        : []
      this.loadingClasses = false
    },
    buildBody() {
      return {
        studentId: this.form.studentId,
        changeType: this.form.changeType,
        reason: this.form.reason || '',
        toCollegeId: this.form.changeType === 'TRANSFER_MAJOR' ? (this.form.toCollegeId || undefined) : undefined,
        toMajorId: this.form.changeType === 'TRANSFER_MAJOR' ? (this.form.toMajorId || undefined) : undefined,
        toClassId: (this.form.changeType === 'TRANSFER_MAJOR' || this.form.changeType === 'TRANSFER_CLASS') ? (this.form.toClassId || undefined) : undefined
      }
    },
    async submit() {
      if (this.submitting || !this.canSubmit) return
      if (this.form.effectiveMode === 'SCHEDULED') {
        const selected = new Date(this.form.effectiveDate)
        if (!Number.isFinite(selected.getTime()) || selected.getTime() <= Date.now()) {
          toast.error('计划生效时间必须晚于当前时间')
          return
        }
      }
      this.submitting = true
      const body = this.buildBody()
      let res
      if (this.form.effectiveMode === 'SCHEDULED') {
        res = await statusChangeConvenienceApi.submitScheduled({ ...body, effectiveDate: new Date(this.form.effectiveDate).toISOString() })
      } else {
        res = await academicAffairsApi.submitStatusChange(body)
      }
      this.submitting = false
      if (res.code === 0) {
        toast.success(this.form.effectiveMode === 'SCHEDULED' ? '异动已提交，终审后按指定日期生效' : '异动已提交，进入审批流程')
        this.$router.push(`/admin/academic-affairs/status-changes/${res.data.changeId}`)
      } else {
        toast.error(res.message || '提交失败')
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-form { display: flex; flex-direction: column; gap: 18px; max-width: 920px; }
.aa-form__row { display: flex; align-items: flex-start; gap: 16px; }
.aa-form__label { width: 96px; flex-shrink: 0; padding-top: 8px; font-size: 13px; color: var(--text-700, #4e5969); text-align: right; }
.aa-form__label.required::before { content: '*'; color: var(--danger-600, #f53f3f); margin-right: 4px; }
.aa-form__field { flex: 1; min-width: 0; }
.aa-input, .aa-textarea { width: 100%; padding: 8px 12px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 14px; box-sizing: border-box; }
.aa-input { height: 36px; }
.aa-picked { display: flex; align-items: center; gap: 12px; font-size: 14px; color: var(--text-900, #1f2329); }
.aa-form__hint { margin-top: 5px; font-size: 12px; line-height: 1.5; color: var(--text-400, #8a9099); }
.aa-transition { margin-left: 112px; display: grid; grid-template-columns: minmax(0, 1fr) 36px minmax(0, 1fr); gap: 12px; align-items: stretch; }
.aa-transition__card { padding: 16px; border: 1px solid var(--border-200, #e5e6eb); border-radius: 10px; background: var(--bg-white, #fff); }
.aa-transition__card--target { background: var(--fill-50, #f7f8fa); }
.aa-transition__eyebrow { margin-bottom: 4px; font-size: 12px; color: var(--text-400, #8a9099); }
.aa-transition__title { display: block; margin-bottom: 14px; font-size: 15px; color: var(--text-900, #1f2329); }
.aa-transition__grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin: 0; }
.aa-transition__grid div { min-width: 0; }
.aa-transition__grid dt { margin-bottom: 3px; font-size: 11px; color: var(--text-400, #8a9099); }
.aa-transition__grid dd { margin: 0; overflow-wrap: anywhere; font-size: 13px; color: var(--text-800, #31343a); }
.aa-transition__arrow { align-self: center; justify-self: center; font-size: 22px; color: var(--text-400, #8a9099); }
.aa-radio-group { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.aa-radio { display: flex; gap: 9px; align-items: flex-start; padding: 12px; border: 1px solid var(--border-200, #e5e6eb); border-radius: 8px; cursor: pointer; }
.aa-radio input { margin-top: 3px; }
.aa-radio span { display: flex; flex-direction: column; gap: 3px; }
.aa-radio strong { font-size: 13px; font-weight: 600; color: var(--text-900, #1f2329); }
.aa-radio small { font-size: 11px; line-height: 1.4; color: var(--text-400, #8a9099); }
.aa-effective-date { margin-top: 10px; max-width: 360px; }
.aa-form__actions { margin-top: 24px; display: flex; gap: 12px; padding-left: 112px; }
@media (max-width: 820px) {
  .aa-form__row { display: block; }
  .aa-form__label { display: block; width: auto; padding: 0 0 6px; text-align: left; }
  .aa-transition { margin-left: 0; grid-template-columns: 1fr; }
  .aa-transition__arrow { transform: rotate(90deg); }
  .aa-radio-group { grid-template-columns: 1fr; }
  .aa-form__actions { padding-left: 0; }
}
</style>
