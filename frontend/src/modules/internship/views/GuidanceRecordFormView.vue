<template>
  <ModulePageShell :title="`新增${typeMeta.label}`"
    subtitle="记录本次沟通与处理建议，保存后查看详情并继续跟进。"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppButton variant="ghost" :disabled="submitting" @click="backToList">返回指导巡访</AppButton>
    </template>

    <section class="mp-card grf">
      <div v-if="submitError" class="grf__error" role="alert">{{ submitError }}</div>
      <div class="grf__type">
        <span class="grf__type-lbl">记录类型</span>
        <AppQuickFilterChips :model-value="type" :options="typeOptions" @change="switchType" />
      </div>

      <AppForm ref="formRef" :model="form" :rules="rules" layout="horizontal" label-width="110px" @submit="doSubmit">
        <fieldset class="grf__fields" :disabled="submitting || !!pendingGuidance" :inert="submitting || !!pendingGuidance">
        <AppFormSection title="学生与指导方式">
          <AppFormItem v-if="type === 'guidance'" label="指导学生" prop="internshipIds" required>
            <AppInternshipStudentPicker v-model="form.internshipIds" multiple @change="onGuidanceStudents"
              :key="batchStore.selectedBatchId" :query="{ batchId: batchStore.selectedBatchId }"
              placeholder="按姓名或学号选择本人学生，可批量选择"
              data-scope-hint="逐学生保存独立记录；最多100名。附件逐学生独立上传并绑定。" />
          </AppFormItem>
          <AppFormItem v-else label="实习学生" prop="internshipId" required>
            <AppInternshipStudentPicker
              v-model="form.internshipId"
              :key="batchStore.selectedBatchId" :query="{ batchId: batchStore.selectedBatchId }"
              placeholder="输入姓名或学号搜索实习学生"
              search-placeholder="按姓名 / 学号搜索"
              data-scope-hint="指导教师仅本人指导学生；管理员全校"
            />
          </AppFormItem>
          <AppFormItem label="方式" prop="method">
            <AppSelect v-model="form.method" :options="methodOptions" />
          </AppFormItem>
        </AppFormSection>

        <template v-if="type === 'guidance'">
          <AppFormSection title="指导内容">
            <AppFormItem label="指导日期" prop="guidanceDate" required><AppDatePicker v-model="form.guidanceDate" placeholder="选择实际指导日期" /></AppFormItem>
            <AppFormItem label="主题"><AppTextInput v-model="form.topic" placeholder="如：岗位适应 / 安全教育" /></AppFormItem>
            <AppFormItem label="指导内容" prop="content" required>
              <AppTextarea v-model="form.content" :rows="4" placeholder="记录本次指导的具体内容" />
            </AppFormItem>
            <AppFormItem label="问题类型"><AppTextInput v-model="form.problemType" placeholder="如：岗位不符 / 考勤异常 / 安全隐患" /></AppFormItem>
            <AppFormItem label="处理建议"><AppTextInput v-model="form.suggestion" placeholder="给学生/企业的处理建议" /></AppFormItem>
            <AppFormItem label="下次跟进日期"><AppDatePicker v-model="form.nextFollowDate" /></AppFormItem>
          </AppFormSection>
          <AppFormSection title="后续跟进" description="有风险需持续处理时标记线索，需协同时通知辅导员。">
            <AppFormItem label="联动动作">
              <AppCheckboxGroup v-model="form.guidanceFlags" :options="flagOptions" />
            </AppFormItem>
          </AppFormSection>
        </template>

        <template v-else>
          <AppFormSection title="巡访反馈">
            <AppFormItem label="巡访标题" prop="title" required><AppTextInput v-model="form.title" placeholder="填写本次巡访主题，2至200字" maxlength="200" /></AppFormItem>
            <AppFormItem label="企业反馈">
              <AppTextInput v-model="form.enterpriseFeedback" placeholder="企业对学生的反馈" />
              <AppTemplateChips class="grf__chips" :options="VISIT_GUIDANCE" size="compact" @pick="(v) => pickInto('enterpriseFeedback', v)" />
            </AppFormItem>
            <AppFormItem label="学生反馈">
              <AppTextInput v-model="form.studentFeedback" placeholder="学生对岗位/实习的反馈" />
              <AppTemplateChips class="grf__chips" :options="VISIT_STATUS" size="compact" @pick="(v) => pickInto('studentFeedback', v)" />
            </AppFormItem>
          </AppFormSection>
          <AppFormSection title="安全隐患与整改" description="填写安全隐患或整改要求后，该巡访自动进入「整改中」">
            <AppFormItem label="安全隐患">
              <AppTextInput v-model="form.safetyIssue" placeholder="仅填写实际发现的问题；未发现隐患请留空" />
            </AppFormItem>
            <AppFormItem label="整改要求"><AppTextInput v-model="form.rectifyRequire" placeholder="填写后自动进入「整改中」" /></AppFormItem>
            <AppFormItem label="整改截止"><AppDatePicker v-model="form.rectifyDeadline" /></AppFormItem>
          </AppFormSection>
          <AppFormSection title="巡访内容">
            <AppFormItem label="巡访内容"><AppTextarea v-model="form.monthlyReport" :rows="3" placeholder="填写本次巡访的实际过程与事实" /></AppFormItem>
          </AppFormSection>
        </template>

        <AppFormSection title="相关材料" :description="type === 'guidance' ? '选填：图片、压缩包、文字文档、便携文档或电子表格；每名学生独立上传并完成安全检查后保存。' : '选填，可上传沟通或巡访佐证材料。'">
          <AppFormItem label="附件">
            <div class="grf__file-row">
              <input type="file" aria-label="上传相关材料" :accept="type === 'guidance' ? '.jpg,.jpeg,.png,.rar,.zip,.doc,.docx,.pdf,.xls,.xlsx' : undefined" :disabled="uploadingFile || submitting" class="grf__file" @change="onFilePick" />
              <span v-if="uploadingFile" class="grf__att">上传中，请稍候…</span>
              <span v-else-if="form.fileId" class="grf__att">已上传：{{ attachName }}</span>
              <span v-else-if="selectedGuidanceFile" class="grf__att">已选：{{ attachName }}，保存时逐学生上传</span>

            </div>
          </AppFormItem>
        </AppFormSection>

        </fieldset>
        <AppSubmitBar sticky :loading="submitting" :disabled="uploadingFile || !batchStore.selectedBatchId || (pendingGuidance && guidanceResults.length && guidanceResults.every(row => row.success))" :submit-text="pendingGuidance ? '重试未确认或失败项' : `保存${typeMeta.label}`" cancel-text="取消并返回"
          @submit="onSubmitClick" @cancel="backToList">
          <template #info>{{ uploadingFile ? '附件上传中，完成后即可保存' : '保存后查看记录详情，继续跟进或登记下一条' }}</template>
        </AppSubmitBar>
      </AppForm>
      <p v-if="pendingGuidance">原提交内容已保留，重试使用相同内容核对；成功项不会再次创建。</p>
      <AppButton v-if="pendingGuidance && !guidanceUnconfirmed && (!guidanceResults.length || guidanceResults.some(row => !row.success))" variant="ghost" :disabled="submitting" @click="editFailedGuidances">修改未完成内容</AppButton>
      <section v-if="guidanceResults.length" class="grf__results" aria-label="逐学生保存结果">
        <strong>已保存 {{ guidanceResults.filter(row => row.success).length }} 条，未完成 {{ guidanceResults.filter(row => !row.success).length }} 条</strong>
        <p>成功项已保留，重试只处理未完成项。学校可按原指导编号读取。</p>
        <ul>
          <li v-for="row in guidanceResults" :key="row.internshipId">
            <span>{{ row.studentName || '所选学生' }}{{ row.studentNo ? '（' + row.studentNo + '）' : '' }}：{{ row.success ? '已保存，指导编号 ' + row.id : (row.unconfirmed ? '保存结果待确认；' : '未保存；') + row.message }}</span>
            <AppButton v-if="row.success" variant="ghost" @click="viewGuidance(row)">查看原记录</AppButton>
          </li>
        </ul>
      </section>
    </section>
  </ModulePageShell>
</template>

<script>
/**
 * 指导 / 巡访记录独立录入页（/admin/internship/guidance/new?type=guidance|visit）。
 * 由 GuidanceVisitView 的「＋ 新增记录」进入；原新增窄弹窗收口至此。
 * query.type 决定表单形态，顶部 chips 可切换并联动字段；提交走真实 createGuidance / createVisit。
 */
import { ModulePageShell } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppForm, AppFormSection, AppFormItem, AppSubmitBar, AppSelect, AppTextInput, AppTextarea,
  AppDatePicker, AppInternshipStudentPicker, AppCheckboxGroup, AppQuickFilterChips, AppTemplateChips } from '@/components/common'
import { guidanceVisitApi } from '@/modules/internship/api/guidance-visit.api'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { toast } from '@/utils/toast'
import { VISIT_STATUS, VISIT_GUIDANCE } from '@/modules/internship/constants/presetPrompts'
import { currentSessionGeneration } from '@/services/http/client'
import { normalizeUiError } from '@/utils/presentationSafety'

const TYPE_META = { guidance: { label: '指导记录' }, visit: { label: '巡访记录' } }
const METHODS = {
  guidance: [
    { value: 'ONSITE', label: '现场' }, { value: 'ONLINE', label: '微信或QQ（即时聊天）指导' }, { value: 'PHONE', label: '电话' },
    { value: 'VIDEO', label: '视频' }, { value: 'ENTERPRISE_FEEDBACK', label: '企业导师反馈' }
  ],
  visit: [{ value: 'ONSITE', label: '现场' }, { value: 'ONLINE', label: '线上' }, { value: 'PHONE', label: '电话' }]
}
const LIST_PATH = '/admin/internship/guidance'

function emptyForm() {
  return { internshipId: '', internshipIds: [], guidanceDate: '', method: 'ONSITE', title: '', topic: '', content: '', problemType: '', suggestion: '',
    nextFollowDate: '', guidanceFlags: [], enterpriseFeedback: '', studentFeedback: '',
    safetyIssue: '', rectifyRequire: '', rectifyDeadline: '', monthlyReport: '', fileId: '' }
}

export default {
  name: 'GuidanceRecordFormView',
  components: { ModulePageShell, AppButton, AppForm, AppFormSection, AppFormItem, AppSubmitBar,
    AppSelect, AppTextInput, AppTextarea, AppDatePicker, AppInternshipStudentPicker, AppCheckboxGroup, AppQuickFilterChips, AppTemplateChips },
  data() {
    return {
      VISIT_STATUS, VISIT_GUIDANCE,
      type: 'guidance',
      typeOptions: [{ label: '指导记录', value: 'guidance' }, { label: '巡访记录', value: 'visit' }],
      flagOptions: [{ label: '标记为风险线索', value: 'toRisk' }, { label: '通知辅导员', value: 'notifyCounselor' }],
      form: emptyForm(),
      attachName: '', uploadingFile: false, submitting: false, submitError: '', uploadSequence: 0,
      selectedGuidanceFile: null, pendingGuidance: null, guidanceTargets: [], guidanceResults: [], guidanceStudents: {}, guidanceUnconfirmed: false,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    typeMeta() { return TYPE_META[this.type] },
    methodOptions() { return METHODS[this.type] },
    rules() {
      const r = {}
      if (this.type === 'guidance') {
        r.internshipIds = [{ validator: value => Array.isArray(value) && value.length > 0 && value.length <= 100 ? true : '请选择1至100名指导学生' }]
        r.guidanceDate = [{ required: true, message: '请选择实际指导日期' }]
        r.content = [
          { required: true, message: '指导内容必填' },
          { validator: (v) => (String(v).trim() ? true : '指导内容必填') }
        ]
      } else {
        r.internshipId = [{ required: true, message: '请选择实习学生' }]
        r.title = [{ required: true, message: '请填写巡访标题' }, { validator: v => String(v || '').trim().length >= 2 && String(v || '').trim().length <= 200 ? true : '巡访标题须为2至200字' }]
      }
      return r
    }
  },
  beforeUnmount() { this.uploadSequence++; this.form = emptyForm(); this.pendingGuidance = null; this.guidanceTargets = []; this.selectedGuidanceFile = null },
  watch: {
    'batchStore.selectedBatchId'() {
      this.uploadSequence++; this.form = emptyForm(); this.attachName = ''
      this.uploadingFile = false; this.submitting = false; this.submitError = ''
      this.pendingGuidance = null; this.guidanceTargets = []; this.guidanceResults = []; this.selectedGuidanceFile = null; this.guidanceStudents = {}; this.guidanceUnconfirmed = false
    },
    '$route.query.type': {
      immediate: true,
      handler(t) { this.applyType((t || 'guidance').toString()) }
    }
  },
  methods: {
    // 选择器远程搜索（岗位实习模块适配层，关键字与数据范围由后端裁定）
    pickInto(field, text) {
      if (!text || this.submitting || this.pendingGuidance) return
      const cur = (this.form[field] || '').trim()
      this.form[field] = cur ? cur + '；' + text : text
    },
    applyType(t) {
      if (this.pendingGuidance) return
      this.uploadSequence++; this.uploadingFile = false; this.form.fileId = ''; this.attachName = ''; this.selectedGuidanceFile = null
      this.type = TYPE_META[t] ? t : 'guidance'
      // 方式选项随类型联动：当前值不在新选项内时回退到第一项
      if (!this.methodOptions.some((o) => o.value === this.form.method)) {
        this.form.method = this.methodOptions[0].value
      }
      if (this.$refs.formRef) this.$refs.formRef.clearValidate()
    },
    switchType(k) {
      if (k === this.type || this.submitting || this.uploadingFile || this.pendingGuidance) return
      this.$router.replace({ query: { ...this.$route.query, type: k } })
    },
    onGuidanceStudents(ids, items) {
      if (this.submitting || this.pendingGuidance) return
      this.guidanceStudents = Object.fromEntries((Array.isArray(items) ? items : []).map(item => [String(item.value), {
        studentName: item.raw?.name || item.raw?.studentName || item.label || '所选学生', studentNo: item.raw?.studentNo || ''
      }]))
    },
    backToList() {
      if (this.submitting) return
      // 从列表进入时走历史返回（保留 tab/筛选/页码/选中）；深链直入时兜底到对应 tab 列表
      const back = this.$router.options.history.state && this.$router.options.history.state.back
      if (typeof back === 'string' && (back === LIST_PATH || back.startsWith(LIST_PATH + '?'))) this.$router.back()
      else this.$router.push({ path: LIST_PATH, query: this.batchStore.withBatchQuery({ panel: this.type, keyword: this.$route.query.keyword, returnTo: this.$route.query.returnTo }) })
    },
    async onFilePick(e) {
      const file = e.target.files && e.target.files[0]
      if (!file || this.uploadingFile || this.submitting || this.pendingGuidance) return
      if (this.type === 'guidance') { this.selectedGuidanceFile = file; this.attachName = file.name; e.target.value = ''; return }
      const sequence = ++this.uploadSequence
      const form = this.form
      this.submitError = ''
      this.uploadingFile = true
      const res = await guidanceVisitApi.uploadAttachment(file)
      if (sequence !== this.uploadSequence || form !== this.form) return
      this.uploadingFile = false
      e.target.value = ''
      if (res.code !== 0) { this.submitError = res.message || '附件上传失败，请重新选择文件'; return }
      this.form.fileId = res.data.fileId; this.attachName = res.data.fileName || file.name
      toast.success('附件已上传')
    },
    onSubmitClick() {
      if (this.type === 'guidance' && this.pendingGuidance) { this.submitGuidances(); return }
      // 统一走 AppForm 校验管道（校验通过后触发 @submit → doSubmit）
      if (this.$refs.formRef) this.$refs.formRef.onSubmit()
    },
    async doSubmit() {
      if (this.submitting || this.uploadingFile) return
      this.submitError = ''
      if (!this.batchStore.selectedBatchId) { this.submitError = '请先选择实习批次'; return }
      const f = this.form
      if (this.type === 'guidance') { await this.submitGuidances(); return }
      if (!f.internshipId) { this.submitError = '请选择实习学生'; return }
      const type = this.type
      const queryBefore = this.batchStore.withBatchQuery({ ...this.$route.query })
      const payload = { internshipId: f.internshipId, method: f.method, title: f.title.trim(), enterpriseFeedback: f.enterpriseFeedback,
            studentFeedback: f.studentFeedback, safetyIssue: f.safetyIssue, rectifyRequire: f.rectifyRequire,
            rectifyDeadline: f.rectifyDeadline, monthlyReport: f.monthlyReport, fileId: f.fileId }
      this.submitting = true
      const res = await guidanceVisitApi.createVisit(payload)
      if (this.form !== f) return
      this.submitting = false
      if (res.code !== 0) { this.submitError = res.message || '保存失败，已保留填写内容'; return }
      window.__SAAS_DIRTY_FORM_GUARD__?.markSaved()
      this.form = emptyForm(); this.attachName = ''
      await this.$nextTick()
      toast.success('记录已保存')
      const query = { ...queryBefore, panel: type, id: String(res.data.id), receipt: 'created' }
      delete query.type
      this.$router.push({
        path: LIST_PATH,
        query
      })
    },
    async submitGuidances() {
      if (this.submitting || this.uploadingFile) return
      const form = this.form, batchId = String(this.batchStore.selectedBatchId || ''), generation = currentSessionGeneration(), sequence = this.uploadSequence
      const current = () => this.form === form && String(this.batchStore.selectedBatchId || '') === batchId && generation === currentSessionGeneration() && sequence === this.uploadSequence
      if (!batchId || !Array.isArray(form.internshipIds) || !form.internshipIds.length || form.internshipIds.length > 100) { this.submitError = '请选择当前批次的1至100名指导学生'; return }
      if (!form.guidanceDate || form.content.trim().length < 2) { this.submitError = '请选择实际日期并填写至少2字指导内容'; return }
      if (!this.pendingGuidance) {
        this.pendingGuidance = { batchId, guidanceDate: form.guidanceDate, method: form.method,
          topic: form.topic.trim(), content: form.content.trim(), problemType: form.problemType.trim(), suggestion: form.suggestion.trim(),
          nextFollowDate: form.nextFollowDate, toRisk: form.guidanceFlags.includes('toRisk'), notifyCounselor: form.guidanceFlags.includes('notifyCounselor') }
        this.guidanceTargets = form.internshipIds.map(id => ({ internshipId: String(id), requestKey: `guide-${Date.now()}-${Math.random().toString(36).slice(2)}`, fileId: null }))
        this.guidanceUnconfirmed = false
      }
      this.submitting = true; this.submitError = ''
      let sent = [], previousUnconfirmed = new Map()
      const updateResult = (target, row) => {
        this.guidanceResults = [...this.guidanceResults.filter(item => item.internshipId !== target.internshipId),
          { ...this.guidanceStudents[target.internshipId], ...row, internshipId: target.internshipId, unconfirmed: !!target.unconfirmed }]
      }
      try {
        const pending = this.guidanceTargets.filter(target => !this.guidanceResults.some(row => row.success && row.internshipId === target.internshipId))
        if (!pending.length) return
        const prepared = []
        for (const target of pending) {
          try {
            if (this.selectedGuidanceFile && !target.fileId) {
              const result = await guidanceVisitApi.uploadAttachment(this.selectedGuidanceFile)
              if (!current()) return
              if (result.code !== 0 || !result.data?.fileId) throw { ...result, message: result.message || '附件接收未完成，请重试原提交' }
              target.fileId = String(result.data.fileId)
            }
            if (target.fileId) {
              const result = await guidanceVisitApi.getAttachmentMetadata(target.fileId)
              if (!current()) return
              if (result.code !== 0 || String(result.data?.fileId) !== target.fileId || result.data?.readyForBusiness !== true) throw { message: '附件安全检查尚未完成，请稍后重试原提交' }
            }
            prepared.push(target)
          } catch (error) {
            if (!current()) return
            updateResult(target, { success: false, message: normalizeUiError(error, { fallback: '附件准备未完成，请重试原提交' }).userMessage })
          }
        }
        if (!prepared.length) return
        sent = prepared; previousUnconfirmed = new Map(sent.map(target => [target.internshipId, !!target.unconfirmed]))
        for (const target of sent) target.unconfirmed = true
        this.guidanceUnconfirmed = true
        const result = await guidanceVisitApi.createGuidancesBatch({ ...this.pendingGuidance,
          items: sent.map(({ internshipId, requestKey, fileId }) => ({ internshipId, requestKey, fileId })) })
        if (!current()) return
        if (result.code !== 0) throw { ...result, message: result.message || '批量保存未确认，请重试原提交' }
        const rows = result.data?.items
        if (!Array.isArray(rows) || rows.length !== sent.length || String(result.data.batchId) !== batchId ||
            new Set(rows.map(row => row?.internshipId)).size !== sent.length || rows.some(row => !row || !sent.some(target => target.internshipId === row.internshipId && row.requestKey === target.requestKey) || typeof row.success !== 'boolean' || (row.success && !row.id))) throw { message: '逐学生回执不完整，请重试原提交核对' }
        for (const row of rows) {
          const target = sent.find(target => target.internshipId === row.internshipId)
          target.unconfirmed = !row.success && (previousUnconfirmed.get(target.internshipId) || row.code === 'SAVE_FAILED' || row.saveUnconfirmed === true)
          updateResult(target, row)
        }
        if (this.guidanceTargets.every(target => this.guidanceResults.some(row => row.internshipId === target.internshipId && row.success))) window.__SAAS_DIRTY_FORM_GUARD__?.markSaved()
      } catch (error) {
        if (!current()) return
        this.submitError = normalizeUiError(error, { fallback: '办理未确认，请保留原输入并重试' }).userMessage
        for (const target of sent) {
          if (!previousUnconfirmed.get(target.internshipId) && error.biz && [400, 401, 403, 404, 422].includes(Number(error.httpStatus))) target.unconfirmed = false
          updateResult(target, { success: false, message: this.submitError })
        }
      }
      finally { if (current()) { this.submitting = false; this.guidanceUnconfirmed = this.guidanceTargets.some(target => target.unconfirmed) } }
    },
    editFailedGuidances() {
      if (this.submitting || this.guidanceUnconfirmed) return
      this.form.internshipIds = this.guidanceTargets.filter(target => !this.guidanceResults.some(row => row.success && row.internshipId === target.internshipId)).map(target => target.internshipId)
      this.guidanceResults = this.guidanceResults.filter(row => row.success)
      this.pendingGuidance = null; this.guidanceTargets = []; this.submitError = ''
    },
    viewGuidance(row) { this.$router.push({ path: LIST_PATH, query: this.batchStore.withBatchQuery({ panel: 'guidance', id: String(row.id) }) }) }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.grf { padding: var(--space-5); max-width: 980px; }
.grf__fields { border: 0; padding: 0; margin: 0; min-width: 0; }
.grf__error { padding: 12px 16px; margin-bottom: 16px; border: 1px solid var(--danger-200, #fecdca); border-radius: 8px; background: var(--danger-50, #fff4f2); color: var(--danger-700, #b42318); }
.grf__type { display: flex; align-items: center; gap: var(--space-3); padding-bottom: var(--space-4); margin-bottom: var(--space-4); border-bottom: 1px solid var(--border-light); }
.grf__type-lbl { font-size: var(--font-size-sm); color: var(--text-secondary); }
.grf__file-row { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; min-height: 32px; }
.grf__file { font-size: var(--font-size-xs); }
.grf__att { font-size: var(--font-size-xs); color: var(--success-700); }
.grf__chips { margin-top: var(--space-2); }
</style>
