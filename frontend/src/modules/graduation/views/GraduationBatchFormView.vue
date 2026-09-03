<template>
  <GraduationFormPageShell
    :ctx="ctx"
    :title="editing ? '编辑毕业设计批次' : '新建毕业设计批次'"
    :subtitle="editing ? '核对批次身份、实施周期与适用范围，保存后继续维护规则。' : '先建立一届毕业设计的工作边界，再进入规则、学生与导师实施。'"
    eyebrow="批次与实施"
    purpose="批次是学生、导师、题目、材料和成绩的共同业务边界；保存前先确认编号、周期与适用范围。"
    :status-text="statusText"
    :status-tone="statusTone"
    back-label="返回批次列表"
    back-to="/admin/graduation/batches?panel=list"
    :busy="submitting"
  >
    <template #context>
      <div class="batch-context">
        <span>办理模式</span>
        <strong>{{ editing ? '修改现有批次' : '创建新批次' }}</strong>
      </div>
      <div class="batch-context">
        <span>当前范围</span>
        <strong>{{ scopeSummary }}</strong>
      </div>
      <div class="batch-context">
        <span>计划规模</span>
        <strong>{{ Number(form.plannedCount || 0) }} 人</strong>
      </div>
      <div class="batch-context">
        <span>已完成条件</span>
        <strong>{{ completionCount }}/3</strong>
      </div>
    </template>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="loadError" :description="loadError" @retry="load" />
    <form v-else class="ie-form" @submit.prevent="submit">
      <section class="gd-form-section">
        <header class="gd-form-section__head">
          <div>
            <span>01 · 批次身份</span>
            <strong>老师和学生看到的批次名称与唯一编号</strong>
            <small>批次编号创建后保持稳定，用于跨端查询、导入、审计和历史追溯。</small>
          </div>
        </header>

        <label class="ie-fld ie-fld--full">
          <span class="ie-lbl">批次名称 <i>*</i></span>
          <input v-model.trim="form.batchName" class="ie-in" placeholder="如 2026届毕业设计" autocomplete="off" />
          <small class="ie-hint">建议使用“届次 + 毕业设计”，让教师和学生一眼确认当前工作批次。</small>
        </label>
        <label class="ie-fld">
          <span class="ie-lbl">批次编号 <i>*</i></span>
          <input v-model.trim="form.batchNo" class="ie-in" :disabled="Boolean(editing)" placeholder="如 GD-2026" autocomplete="off" />
          <small class="ie-hint">租户内唯一；创建后不允许通过本页修改。</small>
        </label>
        <label class="ie-fld">
          <span class="ie-lbl">毕业届次</span>
          <input v-model.trim="form.gradeYear" class="ie-in" placeholder="如 2026届" autocomplete="off" />
        </label>
        <label class="ie-fld">
          <span class="ie-lbl">所属学年</span>
          <input v-model.trim="form.academicYear" class="ie-in" placeholder="如 2025-2026" autocomplete="off" />
        </label>
        <label class="ie-fld">
          <span class="ie-lbl">计划学生数</span>
          <input v-model.number="form.plannedCount" type="number" min="0" class="ie-in" inputmode="numeric" />
          <small class="ie-hint">用于实施规模判断，不代替后续真实学生名单。</small>
        </label>
      </section>

      <section class="gd-form-section">
        <header class="gd-form-section__head">
          <div>
            <span>02 · 实施边界</span>
            <strong>确定批次运行周期和适用组织范围</strong>
            <small>阶段日历会在批次保存后单独维护；本页只冻结批次总周期。</small>
          </div>
        </header>

        <AppDatePicker v-model="form.startDate" class="ie-fld" label="开始日期" role="start" :end-value="form.endDate" hint="批次启动日" />
        <AppDatePicker v-model="form.endDate" class="ie-fld" label="结束日期" role="end" :start-value="form.startDate" hint="批次收口日" />
        <label class="ie-fld ie-fld--full">
          <span class="ie-lbl">适用范围</span>
          <input v-model.trim="form.collegeScope" class="ie-in" placeholder="学院 / 专业范围；留空表示全校" autocomplete="off" />
          <small class="ie-hint">这里记录业务范围说明；正式可见数据仍由后端数据范围裁决。</small>
        </label>
        <label class="ie-fld ie-fld--full">
          <span class="ie-lbl">实施备注</span>
          <textarea v-model.trim="form.remark" class="ie-in" rows="3" placeholder="记录本届实施口径、特殊说明或交接事项" />
        </label>
      </section>

      <p v-if="formError" class="ie-err" role="alert">{{ formError }}</p>
    </form>

    <template #aside>
      <section class="gd-form-aside-card">
        <span>保存前检查</span>
        <strong>{{ completionCount === 3 ? '关键条件已齐全' : `还差 ${3 - completionCount} 项关键条件` }}</strong>
        <ul class="gd-form-checklist">
          <li :class="{ 'is-ready': identityReady }">批次名称与唯一编号已填写</li>
          <li :class="{ 'is-ready': datesReady }">开始、结束日期顺序正确</li>
          <li :class="{ 'is-ready': scaleReady }">计划人数为有效非负数</li>
        </ul>
      </section>
      <section class="gd-form-aside-card">
        <span>保存后的真实流程</span>
        <strong>{{ nextActionText }}</strong>
        <p>保存只建立批次主档，不会自动发布。随后依次维护规则和阶段、导入学生、配置导师，再由授权角色启动批次。</p>
      </section>
      <section class="gd-form-aside-card">
        <span>跨端影响</span>
        <strong>启动后才进入教师与学生工作区</strong>
        <p>教师 PC、学生 PC 和微信端都按同一 batchId 读取状态；本页不会在浏览器端伪造阶段或人数。</p>
      </section>
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
  startDate: todayDate(),
  endDate: formatDate(addDays(new Date(), 180)),
  collegeScope: '', remark: ''
})

const SAFE_PREFIX = '/admin/graduation/'
const freezeSnapshot = (value) => Object.freeze({ ...value })

export default {
  name: 'GraduationBatchFormView',
  components: { GraduationFormPageShell, AppDatePicker, ErrorState, LoadingState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      editing: null,
      form: EMPTY_FORM(),
      formError: '',
      loading: false,
      loadError: '',
      submitting: false,
      commandSnapshot: null
    }
  },
  computed: {
    identityReady() {
      return Boolean(this.form.batchName && this.form.batchNo)
    },
    datesReady() {
      return Boolean(this.form.startDate && this.form.endDate && validateRange(this.form.startDate, this.form.endDate).ok)
    },
    scaleReady() {
      const value = Number(this.form.plannedCount)
      return Number.isFinite(value) && value >= 0
    },
    completionCount() {
      return [this.identityReady, this.datesReady, this.scaleReady].filter(Boolean).length
    },
    scopeSummary() {
      return this.form.collegeScope || '全校'
    },
    statusText() {
      if (!this.editing) return '新建主档'
      return this.editing.statusLabel || this.editing.status || '编辑主档'
    },
    statusTone() {
      const status = String(this.editing?.status || '').toUpperCase()
      if (status === 'RUNNING') return 'success'
      if (status === 'ARCHIVED' || status === 'VOIDED') return 'danger'
      if (status === 'CLOSED') return 'warning'
      return 'info'
    },
    nextActionText() {
      return this.editing ? '返回批次台账，继续维护规则或查看实施状态' : '创建主档后，先维护规则与阶段，再导入学生'
    },
    listTarget() {
      const raw = Array.isArray(this.$route.query.returnTo)
        ? this.$route.query.returnTo[0]
        : this.$route.query.returnTo
      const safe = String(raw || '').trim()
      if (safe.startsWith(SAFE_PREFIX)) return safe
      return this.$router.resolve({
        name: 'graduation-batches',
        query: { panel: 'list', batchId: this.editing?.id || this.$route.query.batchId || undefined }
      }).fullPath
    }
  },
  created() {
    this.load()
  },
  beforeRouteLeave(to, from, next) {
    if (this.submitting) {
      toast.info('批次正在保存，请等待服务器回执后再离开')
      next(false)
      return
    }
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
        if (res.code !== 0) {
          this.loadError = res.message || '批次详情加载失败'
          return
        }
        this.editing = res.data
        const row = res.data || {}
        this.form = {
          batchName: row.batchName || '',
          batchNo: row.batchNo || '',
          gradeYear: row.gradeYear || '',
          academicYear: row.academicYear || '',
          plannedCount: Number(row.plannedCount || 0),
          startDate: (row.startDate || '').slice(0, 10),
          endDate: (row.endDate || '').slice(0, 10),
          collegeScope: row.collegeScope || '',
          remark: row.remark || ''
        }
      } catch (error) {
        this.loadError = error?.message || '批次详情加载失败'
      } finally {
        this.loading = false
      }
    },
    cancel() {
      if (!this.submitting) this.$router.push(this.listTarget)
    },
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

      const snapshot = freezeSnapshot({
        editing: Boolean(this.editing),
        id: this.editing?.id || null,
        body: freezeSnapshot({ ...this.form }),
        returnTo: this.listTarget
      })
      this.commandSnapshot = snapshot
      this.submitting = true
      let saved = false
      try {
        const res = snapshot.editing
          ? await graduationBatchApi.updateBatch(snapshot.id, snapshot.body)
          : await graduationBatchApi.createBatch(snapshot.body)
        if (res.code !== 0) {
          this.formError = res.message || '批次保存失败'
          return
        }
        saved = true
        toast.success(snapshot.editing ? '批次已保存，服务器最新状态已回读' : '批次主档已创建，下一步维护规则与阶段')
      } catch (error) {
        this.formError = error?.message || '批次保存失败'
      } finally {
        this.submitting = false
        this.commandSnapshot = null
      }
      if (saved) await this.$router.push(snapshot.returnTo)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.batch-context {
  display: grid;
  flex: 0 0 auto;
  min-width: 130px;
  gap: 2px;
  padding: 7px 10px;
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 8px;
  background: var(--bg-card, #fff);
}

.batch-context span {
  color: var(--text-tertiary, #64748b);
  font-size: 10px;
}

.batch-context strong {
  overflow: hidden;
  color: var(--text-primary, #0f172a);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mp-btn {
  min-height: 36px;
  padding: 0 16px;
  border: 1px solid var(--border-base, #d9dee8);
  border-radius: 8px;
  background: var(--bg-card, #fff);
  color: var(--text-primary, #0f172a);
  cursor: pointer;
  font-size: 13px;
}

.mp-btn--primary {
  border-color: var(--primary-600, #2563eb);
  background: var(--primary-600, #2563eb);
  color: #fff;
}

.mp-btn:disabled {
  cursor: not-allowed;
  opacity: .5;
}
</style>
