<template>
  <GraduationFormPageShell
    :ctx="ctx"
    :title="editing ? '编辑毕业设计批次' : '新建毕业设计批次'"
    :subtitle="editing ? '核对批次身份、周期和范围。' : '建立本届毕业设计的工作边界。'"
    eyebrow="批次与实施"
    purpose="保存后继续维护规则、阶段、学生和导师；本页不会自动启动批次。"
    :status-text="statusText"
    :status-tone="statusTone"
    back-label="返回批次列表"
    back-to="/admin/graduation/batches?panel=list"
    :busy="submitting"
  >
    <template #context>
      <div class="batch-context"><span>模式</span><strong>{{ editing ? '编辑批次' : '创建批次' }}</strong></div>
      <div class="batch-context"><span>适用范围</span><strong>{{ scopeSummary }}</strong></div>
      <div class="batch-context"><span>关键条件</span><strong>{{ completionCount }}/3</strong></div>
    </template>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="loadError" :description="loadError" @retry="load" />
    <form v-else class="ie-form" @submit.prevent="submit">
      <section class="gd-form-section">
        <header class="gd-form-section__head">
          <div><span>01 · 批次身份</span><strong>名称、编号和实施规模</strong></div>
        </header>

        <div class="ie-fld ie-fld--full">
          <label class="ie-lbl" for="gd-batch-name">批次名称 <i>*</i></label>
          <input id="gd-batch-name" v-model.trim="form.batchName" class="ie-in" aria-describedby="gd-batch-name-hint" placeholder="如 2026届毕业设计" autocomplete="off" />
          <small id="gd-batch-name-hint" class="ie-hint">使用届次和业务名称，方便教师与学生识别。</small>
        </div>
        <div class="ie-fld">
          <label class="ie-lbl" for="gd-batch-no">批次编号 <i>*</i></label>
          <input id="gd-batch-no" v-model.trim="form.batchNo" class="ie-in" :disabled="Boolean(editing)" aria-describedby="gd-batch-no-hint" placeholder="如 GD-2026" autocomplete="off" />
          <small id="gd-batch-no-hint" class="ie-hint">租户内唯一，创建后保持稳定。</small>
        </div>
        <div class="ie-fld">
          <label class="ie-lbl" for="gd-grade-year">毕业届次</label>
          <input id="gd-grade-year" v-model.trim="form.gradeYear" class="ie-in" placeholder="如 2026届" autocomplete="off" />
        </div>
        <div class="ie-fld">
          <label class="ie-lbl" for="gd-academic-year">所属学年</label>
          <input id="gd-academic-year" v-model.trim="form.academicYear" class="ie-in" placeholder="如 2025-2026" autocomplete="off" />
        </div>
        <div class="ie-fld">
          <label class="ie-lbl" for="gd-planned-count">计划学生数</label>
          <input id="gd-planned-count" v-model.number="form.plannedCount" type="number" min="0" class="ie-in" inputmode="numeric" aria-describedby="gd-planned-count-hint" />
          <small id="gd-planned-count-hint" class="ie-hint">仅用于规模判断，不代替真实学生名单。</small>
        </div>
      </section>

      <section class="gd-form-section">
        <header class="gd-form-section__head">
          <div><span>02 · 实施边界</span><strong>总周期和适用范围</strong></div>
        </header>

        <AppDatePicker v-model="form.startDate" class="ie-fld" label="开始日期" role="start" :end-value="form.endDate" hint="批次启动日" />
        <AppDatePicker v-model="form.endDate" class="ie-fld" label="结束日期" role="end" :start-value="form.startDate" hint="批次收口日" />
        <div class="ie-fld ie-fld--full">
          <label class="ie-lbl" for="gd-college-scope">适用范围</label>
          <input id="gd-college-scope" v-model.trim="form.collegeScope" class="ie-in" aria-describedby="gd-college-scope-hint" placeholder="学院 / 专业范围；留空表示全校" autocomplete="off" />
          <small id="gd-college-scope-hint" class="ie-hint">正式可见数据仍由后端数据范围裁决。</small>
        </div>
        <div class="ie-fld ie-fld--full">
          <label class="ie-lbl" for="gd-batch-remark">实施备注</label>
          <textarea id="gd-batch-remark" v-model.trim="form.remark" class="ie-in" rows="3" placeholder="记录特殊口径或交接事项"></textarea>
        </div>
      </section>

      <p v-if="formError" class="ie-err" role="alert">{{ formError }}</p>
    </form>

    <template #aside>
      <section class="gd-form-aside-card">
        <span>保存前检查</span>
        <strong>{{ completionCount === 3 ? '关键条件已齐全' : `还差 ${3 - completionCount} 项` }}</strong>
        <ul class="gd-form-checklist">
          <li :class="{ 'is-ready': identityReady }">名称与唯一编号</li>
          <li :class="{ 'is-ready': datesReady }">日期顺序正确</li>
          <li :class="{ 'is-ready': scaleReady }">计划人数有效</li>
        </ul>
      </section>
      <details class="batch-next">
        <summary>保存后的下一步</summary>
        <ol><li>维护规则与阶段</li><li>导入学生并配置导师</li><li>检查完成后启动批次</li></ol>
      </details>
    </template>

    <template #footer>
      <button type="button" class="mp-btn" :disabled="submitting" @click="cancel">取消</button>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting || loading" @click="submit">
        {{ submitting ? '保存中…' : editing ? '保存批次' : '创建批次' }}
      </button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { ErrorState, LoadingState } from '@/components/business'
import { AppDatePicker } from '@/components/common/date'
import { graduationBatchApi } from '@/modules/graduation/api/graduation-batch.api'
import { toast } from '@/utils/toast'
import { todayDate, formatDate, addDays, validateRange } from '@/utils/dateUtils'

const EMPTY_FORM = () => ({
  batchName: '', batchNo: '', gradeYear: '', academicYear: '', plannedCount: 0,
  startDate: todayDate(), endDate: formatDate(addDays(new Date(), 180)),
  collegeScope: '', remark: ''
})
const SAFE_PREFIX = '/admin/graduation/'
const freezeSnapshot = (value) => Object.freeze({ ...value })

export default {
  name: 'GraduationBatchFormView',
  components: { GraduationFormPageShell, AppDatePicker, ErrorState, LoadingState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { editing: null, form: EMPTY_FORM(), formError: '', loading: false, loadError: '', submitting: false, commandSnapshot: null }
  },
  computed: {
    identityReady() { return Boolean(this.form.batchName && this.form.batchNo) },
    datesReady() { return Boolean(this.form.startDate && this.form.endDate && validateRange(this.form.startDate, this.form.endDate).ok) },
    scaleReady() { const value = Number(this.form.plannedCount); return Number.isFinite(value) && value >= 0 },
    completionCount() { return [this.identityReady, this.datesReady, this.scaleReady].filter(Boolean).length },
    scopeSummary() { return this.form.collegeScope || '全校' },
    statusText() { return this.editing ? (this.editing.statusLabel || this.editing.status || '编辑主档') : '新建主档' },
    statusTone() {
      const status = String(this.editing?.status || '').toUpperCase()
      if (status === 'RUNNING') return 'success'
      if (status === 'ARCHIVED' || status === 'VOIDED') return 'danger'
      if (status === 'CLOSED') return 'warning'
      return 'info'
    },
    listTarget() {
      const raw = Array.isArray(this.$route.query.returnTo) ? this.$route.query.returnTo[0] : this.$route.query.returnTo
      const safe = String(raw || '').trim()
      if (safe.startsWith(SAFE_PREFIX)) return safe
      return this.$router.resolve({ name: 'graduation-batches', query: { panel: 'list', batchId: this.editing?.id || this.$route.query.batchId || undefined } }).fullPath
    }
  },
  created() { this.load() },
  beforeRouteLeave(_to, _from, next) {
    if (this.submitting) { toast.info('批次正在保存，请等待服务器回执后再离开'); next(false); return }
    next()
  },
  methods: {
    async load() {
      const id = this.$route.params.id
      if (!id) return
      this.loading = true
      this.loadError = ''
      try {
        const res = await graduationBatchApi.getBatchDetail(id)
        if (res.code !== 0) { this.loadError = res.message || '批次详情加载失败'; return }
        this.editing = res.data
        const row = res.data || {}
        this.form = {
          batchName: row.batchName || '', batchNo: row.batchNo || '', gradeYear: row.gradeYear || '', academicYear: row.academicYear || '',
          plannedCount: Number(row.plannedCount || 0), startDate: (row.startDate || '').slice(0, 10), endDate: (row.endDate || '').slice(0, 10),
          collegeScope: row.collegeScope || '', remark: row.remark || ''
        }
      } catch (error) { this.loadError = error?.message || '批次详情加载失败' }
      finally { this.loading = false }
    },
    cancel() { if (!this.submitting) this.$router.push(this.listTarget) },
    validate() {
      if (!this.form.batchName || !this.form.batchNo) return '批次名称与编号必填'
      const range = validateRange(this.form.startDate, this.form.endDate)
      if (!range.ok) return range.message
      if (!this.scaleReady) return '计划人数必须是大于或等于 0 的数字'
      return ''
    },
    async submit() {
      if (this.submitting) return
      this.formError = this.validate()
      if (this.formError) return
      const snapshot = freezeSnapshot({ editing: Boolean(this.editing), id: this.editing?.id || null, body: freezeSnapshot({ ...this.form }), returnTo: this.listTarget })
      this.commandSnapshot = snapshot
      this.submitting = true
      let saved = false
      try {
        const res = snapshot.editing ? await graduationBatchApi.updateBatch(snapshot.id, snapshot.body) : await graduationBatchApi.createBatch(snapshot.body)
        if (res.code !== 0) { this.formError = res.message || '批次保存失败'; return }
        saved = true
        toast.success(snapshot.editing ? '批次已保存' : '批次主档已创建')
      } catch (error) { this.formError = error?.message || '批次保存失败' }
      finally { this.submitting = false; this.commandSnapshot = null }
      if (saved) await this.$router.push(snapshot.returnTo)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.batch-context{display:grid;flex:0 0 auto;min-width:112px;gap:1px;padding:6px 8px;border:1px solid var(--border-light);border-radius:8px;background:#fff}.batch-context span{color:var(--text-tertiary);font-size:9px}.batch-context strong{overflow:hidden;color:var(--text-primary);font-size:11px;text-overflow:ellipsis;white-space:nowrap}.batch-next{padding:10px;border:1px solid var(--border-light);border-radius:9px;background:#fff}.batch-next summary{cursor:pointer;font-size:10px;font-weight:700}.batch-next ol{display:grid;gap:5px;margin:7px 0 0;padding-left:18px;color:var(--text-secondary);font-size:9px}.mp-btn{min-height:34px;padding:0 15px;border:1px solid var(--border-base);border-radius:8px;background:#fff;color:var(--text-primary);cursor:pointer;font-size:12px}.mp-btn--primary{border-color:var(--primary-600);background:var(--primary-600);color:#fff}.mp-btn:disabled{cursor:not-allowed;opacity:.5}
</style>
