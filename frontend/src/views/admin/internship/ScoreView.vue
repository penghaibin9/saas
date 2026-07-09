<template>
  <ModulePageShell title="评价与成绩" subtitle="实习成绩 · 五项权重核算 · 复核发布 · 缺项不可发布"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppButton variant="primary" @click="openCompute">＋ 核算成绩</AppButton>
      <AppButton variant="secondary" :loading="exporting" @click="doExport">⬇ 导出 Excel 台账</AppButton>
    </template>

    <!-- 权重配置 -->
    <div class="cfg">
      <span class="cfg__t">五项权重配置</span>
      <label v-for="w in weightDefs" :key="w.key" class="cfg__item">
        <span>{{ w.label }}</span>
        <input v-model.number="cfg[w.key]" type="number" min="0" max="100" class="cfg__in" />
      </label>
      <label class="cfg__item"><span>及格线</span><input v-model.number="cfg.passLine" type="number" min="0" max="100" class="cfg__in" /></label>
      <span class="cfg__sum" :class="{ 'is-bad': weightSum !== 100 }">合计 {{ weightSum }}/100</span>
      <button class="cfg__save" :disabled="savingCfg" @click="saveConfig">{{ savingCfg ? '保存中…' : '保存配置' }}</button>
    </div>

    <div class="bar">
      <input v-model="keyword" class="bar__kw" placeholder="按学生姓名搜索" @keyup.enter="load" />
      <select v-model="statusFilter" class="bar__sel" @change="load">
        <option value="">全部状态</option>
        <option v-for="(l, k) in statusMap" :key="k" :value="k">{{ l }}</option>
      </select>
      <button class="bar__go" @click="load">查询</button>
      <span class="bar__hint">共 {{ total }} 条 · 数据范围内可见</span>
    </div>

    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="error" class="state is-err">{{ error }} <button @click="load">重试</button></div>
    <div v-else-if="!rows.length" class="state">暂无成绩</div>

    <table v-else class="tbl">
      <thead>
        <tr><th>学号</th><th>姓名</th><th>打卡</th><th>周报</th><th>月报</th><th>企业</th><th>学校</th><th>总分</th><th>及格</th><th>状态</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id">
          <td>{{ r.studentNo }}</td><td>{{ r.studentName }}</td>
          <td>{{ n(r.checkinScore) }}</td><td>{{ n(r.weeklyScore) }}</td><td>{{ n(r.monthlyScore) }}</td>
          <td>{{ n(r.enterpriseScore) }}</td><td>{{ n(r.schoolScore) }}</td>
          <td><b>{{ r.incomplete ? '—' : r.totalScore }}</b><span v-if="r.incomplete" class="miss">缺项</span></td>
          <td>{{ r.incomplete ? '—' : (r.isPass ? '及格' : '不及格') }}</td>
          <td><AppStatusTag :status="r.status">{{ r.statusLabel }}</AppStatusTag></td>
          <td class="tbl__ops">
            <button class="op" @click="openDetail(r)">详情</button>
            <button v-if="['PENDING_REVIEW','PENDING_CALC'].includes(r.status)" class="op" @click="openCompute(r)">重算</button>
            <button v-if="r.status === 'PENDING_REVIEW'" class="op op--ok" :disabled="r.incomplete" @click="confirmAct(r, 'publish')">发布</button>
            <button v-if="r.status === 'PENDING_REVIEW'" class="op" @click="confirmAct(r, 'return')">退回</button>
            <button v-if="r.status === 'PUBLISHED'" class="op op--danger" @click="confirmAct(r, 'withdraw')">撤回</button>
            <button v-if="r.status === 'PUBLISHED'" class="op" @click="confirmAct(r, 'archive')">归档</button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- 核算 -->
    <div v-if="computeDlg.visible" class="modal" @click.self="computeDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">核算实习成绩</div>
        <div class="modal__body">
          <label class="fld"><span class="fld__lb">实习学生 *</span>
            <select v-model="cForm.internshipId" :disabled="cForm.locked" class="fld__ct">
              <option value="">请选择本人指导学生</option>
              <option v-for="s in studentOptions" :key="s.id" :value="s.id">{{ s.name }}（{{ s.studentNo }}）</option>
            </select>
          </label>
          <div class="scores">
            <label v-for="s in scoreInputs" :key="s.key" class="score">
              <span class="score__lb">{{ s.label }}</span>
              <input v-model.number="cForm[s.key]" type="number" min="0" max="100" class="score__in" :placeholder="s.ph || ''" />
            </label>
          </div>
          <p class="modal__hint">各项 0-100。企业评价分留空时自动取「已通过企业评价」均分；缺项将标记且不可发布。权重取上方配置。</p>
        </div>
        <div class="modal__foot">
          <button class="mbtn" @click="computeDlg.visible = false">取消</button>
          <button class="mbtn mbtn--primary" :disabled="computeDlg.submitting" @click="submitCompute">{{ computeDlg.submitting ? '核算中…' : '核算' }}</button>
        </div>
      </div>
    </div>

    <!-- 详情 -->
    <div v-if="detailDlg.visible" class="modal" @click.self="detailDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">成绩详情</div>
        <div class="modal__body">
          <div v-if="detailDlg.loading" class="state">加载中…</div>
          <template v-else-if="detailDlg.data">
            <div class="dline"><span class="dline__lb">学生</span><span class="dline__ct">{{ detailDlg.data.studentName }}（{{ detailDlg.data.studentNo }}）</span></div>
            <div class="dline"><span class="dline__lb">总分/及格线</span><span class="dline__ct">{{ detailDlg.data.incomplete ? '缺项' : detailDlg.data.totalScore }} / {{ detailDlg.data.passLine }}</span></div>
            <div class="dline"><span class="dline__lb">缺项</span><span class="dline__ct">{{ detailDlg.data.incompleteReason || '无' }}</span></div>
            <div class="dline"><span class="dline__lb">权重(打/周/月/企/校)</span>
              <span class="dline__ct">{{ wtext(detailDlg.data.weights) }}</span></div>
            <div class="dtrail">
              <div class="dtrail__t">核算/发布留痕</div>
              <div v-for="(t, i) in (detailDlg.data.auditTrail || [])" :key="i" class="dtrail__i"><b>{{ t.action }}</b> · {{ t.operator }} · {{ t.occurredAt }}</div>
            </div>
          </template>
        </div>
        <div class="modal__foot"><button class="mbtn" @click="detailDlg.visible = false">关闭</button></div>
      </div>
    </div>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      reason-label="原因" :submitting="cd.submitting" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog } from '@/components/common'
import { scoreApi } from '@/modules/internship/api/score.api'
import { internStudentApi } from '@/modules/internship/api/internship-student.api'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import { toast } from '@/utils/toast'

const WEIGHTS = [
  { key: 'checkinWeight', label: '打卡' }, { key: 'weeklyWeight', label: '周报' },
  { key: 'monthlyWeight', label: '月报' }, { key: 'enterpriseWeight', label: '企业' }, { key: 'schoolWeight', label: '学校' }
]
const SCORE_INPUTS = [
  { key: 'checkinScore', label: '打卡' }, { key: 'weeklyScore', label: '周报' },
  { key: 'monthlyScore', label: '月报总结' }, { key: 'enterpriseScore', label: '企业评价', ph: '留空自动取' },
  { key: 'schoolScore', label: '学校评价' }
]
const STATUS_MAP = { PENDING_CALC: '待核算', PENDING_REVIEW: '待复核', PUBLISHED: '已发布', WITHDRAWN: '已撤回', ARCHIVED: '已归档' }

export default {
  name: 'ScoreView',
  components: { ModulePageShell, AppButton, AppStatusTag, AppConfirmDialog },
  data() {
    return {
      rows: [], total: 0, loading: false, error: '', exporting: false,
      keyword: '', statusFilter: '', statusMap: STATUS_MAP, weightDefs: WEIGHTS, scoreInputs: SCORE_INPUTS,
      cfg: { checkinWeight: 20, weeklyWeight: 20, monthlyWeight: 10, enterpriseWeight: 30, schoolWeight: 20, passLine: 60 },
      savingCfg: false,
      studentOptions: [],
      cForm: { internshipId: '', locked: false, checkinScore: null, weeklyScore: null, monthlyScore: null, enterpriseScore: null, schoolScore: null },
      computeDlg: { visible: false, submitting: false },
      detailDlg: { visible: false, loading: false, data: null },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false, submitting: false },
      pending: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    weightSum() { return WEIGHTS.reduce((a, w) => a + (Number(this.cfg[w.key]) || 0), 0) }
  },
  created() { this.loadConfig(); this.load() },
  methods: {
    n(v) { return v === 0 ? 0 : (v || '—') },
    wtext(w) { return w ? `${w.checkin}/${w.weekly}/${w.monthly}/${w.enterprise}/${w.school}` : '—' },
    async loadConfig() {
      const res = await scoreApi.getConfig()
      if (res.code === 0) this.cfg = { ...this.cfg, ...res.data }
    },
    async saveConfig() {
      if (this.weightSum !== 100) return toast.error(`五项权重之和须为 100，当前 ${this.weightSum}`)
      this.savingCfg = true
      const res = await scoreApi.saveConfig(this.cfg)
      this.savingCfg = false
      if (res.code !== 0) return toast.error(res.message || '保存失败')
      toast.success('权重配置已保存')
    },
    async load() {
      this.loading = true; this.error = ''
      const params = { page: 1, pageSize: 50, keyword: this.keyword }
      if (this.statusFilter) params.status = this.statusFilter
      const res = await scoreApi.getScores(params)
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
    },
    async openCompute(row) {
      this.cForm = { internshipId: '', locked: false, checkinScore: null, weeklyScore: null, monthlyScore: null, enterpriseScore: null, schoolScore: null }
      if (row && row.internId) {
        this.cForm.internshipId = row.internId; this.cForm.locked = true
        this.cForm.checkinScore = row.checkinScore; this.cForm.weeklyScore = row.weeklyScore
        this.cForm.monthlyScore = row.monthlyScore; this.cForm.enterpriseScore = row.enterpriseScore
        this.cForm.schoolScore = row.schoolScore
      }
      this.computeDlg.visible = true
      if (!this.studentOptions.length) {
        const res = await internStudentApi.getStudents({ page: 1, pageSize: 200 })
        if (res.code === 0) this.studentOptions = res.data.list.map((s) => ({ id: s.id, name: s.name, studentNo: s.studentNo }))
      }
    },
    async submitCompute() {
      if (!this.cForm.internshipId) return toast.error('请选择实习学生')
      this.computeDlg.submitting = true
      const body = { internshipId: this.cForm.internshipId }
      for (const s of SCORE_INPUTS) if (this.cForm[s.key] !== null && this.cForm[s.key] !== '') body[s.key] = this.cForm[s.key]
      const res = await scoreApi.compute(body)
      this.computeDlg.submitting = false
      if (res.code !== 0) return toast.error(res.message || '核算失败')
      this.computeDlg.visible = false
      toast.success(res.data.incomplete ? `已核算（缺项：${res.data.incompleteReason}）` : `已核算，总分 ${res.data.total}`)
      this.load()
    },
    async openDetail(r) {
      this.detailDlg = { visible: true, loading: true, data: null }
      const res = await scoreApi.getDetail(r.id)
      this.detailDlg.loading = false
      if (res.code !== 0) { toast.error(res.message); this.detailDlg.visible = false; return }
      this.detailDlg.data = res.data
    },
    confirmAct(r, kind) {
      const map = {
        publish: { title: '发布成绩', content: `发布「${r.studentName}」的实习成绩（总分 ${r.totalScore}）？发布后学生可见。`, danger: false, confirmText: '发布', requireReason: false },
        return: { title: '退回重算', content: `退回「${r.studentName}」的成绩到待核算？`, danger: false, confirmText: '退回', requireReason: false },
        withdraw: { title: '撤回成绩', content: `撤回「${r.studentName}」的已发布成绩，原因将写审计。`, danger: true, confirmText: '撤回', requireReason: true },
        archive: { title: '归档成绩', content: `归档「${r.studentName}」的已发布成绩？`, danger: false, confirmText: '归档', requireReason: false }
      }[kind]
      this.pending = { id: r.id, kind }
      this.cd = { visible: true, ...map, submitting: false }
    },
    async onConfirm({ reason }) {
      const p = this.pending
      this.cd.submitting = true
      let res
      if (p.kind === 'publish') res = await scoreApi.publish(p.id)
      else if (p.kind === 'return') res = await scoreApi.returnRecalc(p.id, { reason })
      else if (p.kind === 'withdraw') res = await scoreApi.withdraw(p.id, { reason })
      else res = await scoreApi.archive(p.id)
      this.cd.submitting = false
      if (res.code !== 0) return toast.error(res.message || '操作失败')
      this.cd.visible = false; toast.success('操作成功，已写审计'); this.load()
    },
    async doExport() {
      this.exporting = true
      const res = await scoreApi.exportScores({ keyword: this.keyword, status: this.statusFilter })
      this.exporting = false
      if (res.code !== 0) return toast.error(res.message)
      downloadXlsxFromApi(res.data, '实习成绩台账.xlsx')
      toast.success(`已导出 ${res.data.rowCount} 条（水印 + 导出留痕）`)
    }
  }
}
</script>

<style scoped>
.cfg { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; padding: var(--space-3); margin-bottom: var(--space-3); background: var(--bg-subtle); border-radius: var(--radius-base); }
.cfg__t { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); }
.cfg__item { display: flex; align-items: center; gap: var(--space-1); font-size: var(--font-size-xs); color: var(--text-secondary); }
.cfg__in { width: 56px; height: 30px; border: 1px solid var(--border-base); border-radius: var(--radius-base); padding: 0 var(--space-1); font-size: var(--font-size-sm); }
.cfg__sum { font-size: var(--font-size-sm); color: var(--success-700); }
.cfg__sum.is-bad { color: var(--danger-600); }
.cfg__save { height: 30px; padding: 0 var(--space-3); border: 1px solid var(--primary-600); background: var(--primary-600); color: #fff; border-radius: var(--radius-base); cursor: pointer; font-size: var(--font-size-sm); }
.cfg__save:disabled { opacity: 0.6; }
.bar { display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.bar__kw, .bar__sel { height: 32px; border: 1px solid var(--border-base); border-radius: var(--radius-base); padding: 0 var(--space-2); font-size: var(--font-size-sm); }
.bar__go { height: 32px; padding: 0 var(--space-3); border: 1px solid var(--primary-600); background: var(--primary-600); color: #fff; border-radius: var(--radius-base); cursor: pointer; font-size: var(--font-size-sm); }
.bar__hint { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-left: auto; }
.state { padding: var(--space-6); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); border: 1px dashed var(--border-base); border-radius: var(--radius-base); }
.state.is-err { color: var(--danger-600); }
.tbl { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
.tbl th, .tbl td { text-align: left; padding: var(--space-2) var(--space-2); border-bottom: 1px solid var(--border-light); }
.tbl th { color: var(--text-tertiary); font-weight: var(--font-weight-medium); background: var(--bg-subtle); }
.miss { color: var(--danger-600); font-size: var(--font-size-xs); margin-left: 4px; }
.tbl__ops { display: flex; gap: var(--space-1); flex-wrap: wrap; }
.op { border: 1px solid var(--border-base); background: var(--bg-card); border-radius: var(--radius-sm); padding: 2px var(--space-2); font-size: var(--font-size-xs); cursor: pointer; color: var(--text-secondary); }
.op:hover { border-color: var(--primary-500); color: var(--primary-600); }
.op:disabled { opacity: 0.45; cursor: not-allowed; }
.op--ok { border-color: var(--success-100); color: var(--success-700); }
.op--danger { border-color: var(--danger-100); color: var(--danger-600); }
.modal { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center; justify-content: center; z-index: var(--z-modal, 1000); padding: var(--space-4); }
.modal__card { background: var(--bg-card); border-radius: var(--radius-lg); width: min(560px, 100%); max-height: 88vh; display: flex; flex-direction: column; box-shadow: var(--shadow-lg); }
.modal__head { padding: var(--space-4); font-weight: var(--font-weight-semibold); border-bottom: 1px solid var(--border-light); }
.modal__body { padding: var(--space-4); overflow-y: auto; }
.modal__foot { padding: var(--space-3) var(--space-4); border-top: 1px solid var(--border-light); display: flex; justify-content: flex-end; gap: var(--space-2); }
.modal__hint { margin: var(--space-2) 0 0; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.mbtn { height: 34px; padding: 0 var(--space-4); border: 1px solid var(--border-base); background: var(--bg-card); border-radius: var(--radius-base); cursor: pointer; font-size: var(--font-size-sm); }
.mbtn--primary { background: var(--primary-600); border-color: var(--primary-600); color: #fff; }
.mbtn--primary:disabled { opacity: 0.6; cursor: not-allowed; }
.fld { display: flex; flex-direction: column; gap: var(--space-1); margin-bottom: var(--space-3); }
.fld__lb { font-size: var(--font-size-xs); color: var(--text-secondary); }
.fld__ct { height: 34px; border: 1px solid var(--border-base); border-radius: var(--radius-base); padding: 0 var(--space-2); font-size: var(--font-size-sm); }
.scores { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-bottom: var(--space-2); }
.score { display: flex; flex-direction: column; gap: 2px; width: calc(20% - var(--space-2)); min-width: 78px; }
.score__lb { font-size: var(--font-size-xs); color: var(--text-secondary); }
.score__in { height: 32px; border: 1px solid var(--border-base); border-radius: var(--radius-base); padding: 0 var(--space-1); font-size: var(--font-size-sm); width: 100%; }
.dline { display: flex; gap: var(--space-3); padding: var(--space-1) 0; font-size: var(--font-size-sm); }
.dline__lb { width: 120px; flex-shrink: 0; color: var(--text-tertiary); }
.dline__ct { color: var(--text-primary); word-break: break-all; }
.dtrail { margin-top: var(--space-3); padding-top: var(--space-3); border-top: 1px dashed var(--border-light); }
.dtrail__t { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-bottom: var(--space-2); }
.dtrail__i { font-size: var(--font-size-xs); color: var(--text-secondary); padding: 2px 0; }
</style>
