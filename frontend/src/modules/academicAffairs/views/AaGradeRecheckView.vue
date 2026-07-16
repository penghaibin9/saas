<template>
  <ModulePageShell
    title="成绩复查复审"
    subtitle="学生对已发布成绩发起复查，教务处复审：维持原成绩 / 调整成绩（回写成绩单并通知学生）/ 不予受理"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="aa-filter">
        <label class="aa-filter__item">状态
          <select v-model="status" class="aa-input aa-input--sm" @change="load">
            <option value="">全部</option>
            <option value="SUBMITTED">待复审</option>
            <option value="UPHELD">已维持</option>
            <option value="ADJUSTED">已调整</option>
            <option value="REJECTED">不予受理</option>
          </select>
        </label>
        <button class="mp-btn" @click="load">查询</button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <AppSectionCard title="复查申请台账">
          <EmptyState v-if="!rows.length" title="暂无复查申请" description="学生在小程序对已发布成绩发起复查后，这里出现待复审记录" />
          <div v-else class="aa-table-wrap">
            <table class="aa-table">
              <thead>
                <tr><th>学生</th><th>学号</th><th>课程</th><th>学期</th><th>原成绩</th><th>调整后</th><th>理由</th><th>状态</th><th>操作</th></tr>
              </thead>
              <tbody>
                <tr v-for="r in rows" :key="r.recheckId">
                  <td>{{ r.studentName }}</td>
                  <td>{{ r.studentNo }}</td>
                  <td class="aa-td-name">{{ r.courseName }}</td>
                  <td>{{ r.term }}</td>
                  <td>{{ r.originalScore }}</td>
                  <td>{{ r.newScore ?? '—' }}</td>
                  <td class="aa-td-reason" :title="r.reason">{{ r.reason }}</td>
                  <td><AppStatusTag :type="statusColor(r.status)" dot>{{ statusLabel(r.status) }}</AppStatusTag></td>
                  <td>
                    <button v-if="r.status === 'SUBMITTED'" class="mp-link" @click="openReview(r)">复审</button>
                    <span v-else class="aa-note-sm">{{ r.reviewNote || '—' }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </AppSectionCard>

        <AppSectionCard v-if="active" :title="`复审：${active.studentName} · ${active.courseName}（原 ${active.originalScore} 分）`">
          <div class="aa-review">
            <label class="aa-radio"><input type="radio" value="UPHOLD" v-model="form.action" /> 维持原成绩</label>
            <label class="aa-radio"><input type="radio" value="ADJUST" v-model="form.action" /> 调整成绩</label>
            <label class="aa-radio"><input type="radio" value="REJECT" v-model="form.action" /> 不予受理</label>
          </div>
          <div v-if="form.action === 'ADJUST'" class="aa-review-row">
            <label class="aa-field-inline">调整后成绩<input v-model.number="form.newScore" type="number" min="0" max="100" class="aa-input aa-input--xs" /></label>
          </div>
          <textarea v-model.trim="form.note" class="aa-textarea" rows="2"
                    :placeholder="form.action === 'REJECT' ? '不予受理原因（必填，≥5字）' : '复审意见（选填）'"></textarea>
          <div class="aa-actions">
            <button class="mp-btn mp-btn--primary" :disabled="submitting" @click="doReview">{{ submitting ? '提交中…' : '提交复审结果' }}</button>
            <button class="mp-btn" @click="active = null">取消</button>
          </div>
        </AppSectionCard>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/** 成绩复查复审（/admin/academic-affairs/grade-recheck）：GET /grade-rechecks + POST /grade-rechecks/{id}/review。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSectionCard, AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const STATUS = { SUBMITTED: '待复审', UPHELD: '已维持原成绩', ADJUSTED: '已调整成绩', REJECTED: '不予受理' }

export default {
  name: 'AaGradeRecheckView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppSectionCard, AppStatusTag },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', status: '', rows: [], active: null, submitting: false,
      form: { action: 'UPHOLD', newScore: null, note: '' }
    }
  },
  created() { this.load() },
  methods: {
    statusLabel(s) { return STATUS[s] || s },
    statusColor(s) {
      if (s === 'ADJUSTED') return 'success'
      if (s === 'REJECTED') return 'danger'
      if (s === 'SUBMITTED') return 'primary'
      return 'default'
    },
    async load() {
      this.loading = true
      this.error = ''
      this.active = null
      const res = await academicAffairsApi.getGradeRechecks({ status: this.status || undefined, page: 1, pageSize: 100 })
      if (res.code === 0) this.rows = res.data.list
      else this.error = res.message
      this.loading = false
    },
    openReview(r) {
      this.active = r
      this.form = { action: 'UPHOLD', newScore: r.originalScore, note: '' }
    },
    async doReview() {
      if (this.submitting) return
      if (this.form.action === 'ADJUST' && (this.form.newScore == null || this.form.newScore < 0 || this.form.newScore > 100)) {
        toast.error('调整后成绩须为 0-100')
        return
      }
      if (this.form.action === 'REJECT' && (!this.form.note || this.form.note.length < 5)) {
        toast.error('不予受理原因必填且不少于 5 字')
        return
      }
      this.submitting = true
      const res = await academicAffairsApi.reviewGradeRecheck(this.active.recheckId, {
        action: this.form.action,
        note: this.form.note || undefined,
        newScore: this.form.action === 'ADJUST' ? this.form.newScore : undefined
      })
      this.submitting = false
      if (res.code === 0) {
        toast.success('复审结果已提交')
        this.active = null
        this.load()
      } else toast.error(res.message || '提交失败')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.aa-filter__item { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-input { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; }
.aa-input--sm { width: 160px; }
.aa-input--xs { width: 90px; }
.aa-table-wrap { overflow-x: auto; }
.aa-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.aa-table th, .aa-table td { padding: 8px 10px; text-align: center; border-bottom: 1px solid var(--border-200, #e5e6eb); white-space: nowrap; }
.aa-table th { color: var(--text-700, #4e5969); font-weight: 600; background: var(--fill-100, #f7f8fa); }
.aa-td-name { text-align: left; min-width: 120px; }
.aa-td-reason { max-width: 220px; overflow: hidden; text-overflow: ellipsis; text-align: left; }
.aa-note-sm { color: var(--text-500, #646a73); font-size: 12px; }
.aa-review { display: flex; gap: 20px; margin-bottom: 12px; }
.aa-radio { display: inline-flex; align-items: center; gap: 6px; font-size: 14px; color: var(--text-800, #333); cursor: pointer; }
.aa-review-row { margin-bottom: 12px; }
.aa-field-inline { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-textarea { width: 100%; box-sizing: border-box; padding: 8px 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; font-size: 13px; resize: vertical; }
.aa-actions { margin-top: 12px; display: flex; gap: 12px; }
</style>
