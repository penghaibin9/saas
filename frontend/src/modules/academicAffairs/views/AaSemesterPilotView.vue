<template>
  <ModulePageShell
    title="真实学期验收"
    subtitle="R11 只读取真实学校正式事实并冻结六阶段证据；不会生成学生、课程、考勤、考试或成绩数据"
  >
    <template #actions>
      <AppButton variant="primary" :disabled="busy" @click="createVisible = true">新建真实学期验收</AppButton>
    </template>

    <div class="sp-stack">
      <AppInlineAlert
        type="danger"
        title="生产验收专用"
        description="仅用于真实学校上线/阶段验收。禁止在 mock、测试租户或未确认真实数据时勾选“真实数据已确认”；后端会再次校验生产部署、DB 与 mock-login 状态。"
      />

      <section class="sp-filter">
        <label>状态
          <select v-model="filters.status" :disabled="loading" @change="search">
            <option value="">全部状态</option>
            <option value="PREPARING">准备中</option>
            <option value="RUNNING">检查中</option>
            <option value="BLOCKED">有阻断</option>
            <option value="READY_TO_COMPLETE">可确认完成</option>
            <option value="COMPLETED">已完成</option>
            <option value="CANCELLED">已取消</option>
          </select>
        </label>
        <AppButton variant="ghost" :disabled="loading" @click="load">刷新</AppButton>
      </section>

      <ErrorState v-if="error" title="真实学期验收加载失败" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无真实学期验收" description="只在真实学校正式学期进入上线验收时创建" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="pilotId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-pilot="{ row }">
          <div class="sp-main">{{ row.pilotName }}</div>
          <div class="sp-sub">#{{ row.pilotId }} · {{ row.termCode || `学期 ${row.termId}` }}</div>
        </template>
        <template #cell-status="{ row }"><StatusTag :type="statusType(row.status)" :label="statusLabel(row.status)" dot /></template>
        <template #cell-stages="{ row }">
          <strong>{{ row.passedStageCount || 0 }}/{{ row.stageCount || 6 }}</strong>
          <span v-if="row.blockerCount" class="sp-danger"> · 阻断 {{ row.blockerCount }}</span>
        </template>
        <template #cell-checked="{ row }">{{ formatTime(row.latestCheckedAt) }}</template>
        <template #cell-actions="{ row }">
          <div class="sp-actions">
            <AppButton size="small" variant="ghost" :disabled="busy" @click="openDetail(row)">详情</AppButton>
            <AppButton v-if="!['COMPLETED','CANCELLED'].includes(row.status)" size="small" :disabled="busy" @click="runCheck(row)">重新检查</AppButton>
          </div>
        </template>
      </DataTable>

      <section v-if="detail" class="sp-detail">
        <header>
          <div>
            <h3>{{ detail.pilotName }}</h3>
            <p>{{ detail.purpose }}</p>
          </div>
          <div class="sp-actions">
            <AppButton v-if="!['COMPLETED','CANCELLED'].includes(detail.status)" :disabled="busy" @click="runCheck(detail)">执行六阶段检查</AppButton>
            <AppButton v-if="detail.status === 'READY_TO_COMPLETE'" variant="primary" :disabled="busy" @click="openComplete">确认真实学期完成</AppButton>
            <AppButton v-if="!['COMPLETED','CANCELLED'].includes(detail.status)" variant="ghost" :disabled="busy" @click="openCancel">取消验收</AppButton>
          </div>
        </header>

        <div class="sp-facts">
          <div><span>状态</span><strong>{{ statusLabel(detail.status) }}</strong></div>
          <div><span>六阶段</span><strong>{{ detail.passedStageCount || 0 }}/{{ detail.stageCount || 6 }}</strong></div>
          <div><span>阻断</span><strong>{{ detail.blockerCount || 0 }}</strong></div>
          <div><span>检查轮次</span><strong>{{ detail.checkRunNo || 0 }}</strong></div>
          <div><span>最新检查</span><strong>{{ formatTime(detail.latestCheckedAt) }}</strong></div>
          <div><span>真实数据确认</span><strong>{{ detail.realDataConfirmed ? '已确认' : '未确认' }}</strong></div>
        </div>

        <AppInlineAlert
          v-if="detail.environment"
          :type="detail.environment.eligibleForRealCompletion ? 'success' : 'warning'"
          :description="environmentText(detail.environment)"
        />

        <div class="sp-stages">
          <article v-for="stage in detail.stages || []" :key="stage.stageCode" class="sp-stage">
            <header>
              <div><strong>{{ stage.stageName }}</strong><span>{{ stage.stageCode }}</span></div>
              <StatusTag :type="stage.passed ? 'success' : 'danger'" :label="stage.passed ? '通过' : '阻断'" dot />
            </header>
            <p>{{ stage.conclusion }}</p>
            <ul v-if="stage.blockers?.length" class="sp-blockers"><li v-for="item in stage.blockers" :key="item">{{ item }}</li></ul>
            <ul v-if="stage.warnings?.length" class="sp-warnings"><li v-for="item in stage.warnings" :key="item">{{ item }}</li></ul>
            <details>
              <summary>查看冻结证据摘要</summary>
              <pre>{{ pretty(stage.evidence) }}</pre>
              <div class="sp-hash">evidenceHash: {{ stage.evidenceHash }}</div>
            </details>
          </article>
          <EmptyState v-if="!(detail.stages || []).length" title="尚未检查" description="执行六阶段检查后，这里会显示服务器冻结的真实证据与阻断项" />
        </div>
      </section>
    </div>

    <AppDrawer :visible="createVisible" title="新建真实学期验收" mode="modal" size="large" @close="createVisible = false">
      <div class="sp-form">
        <AppInlineAlert type="warning" description="创建动作不会生成业务数据，只建立只读验收容器。真实数据确认必须由学校上线负责人明确勾选。" />
        <label>正式学期<AppTermEntityPicker v-model="createForm.termId" placeholder="选择真实学校正式学期" :disabled="busy" /></label>
        <label>验收名称<input v-model.trim="createForm.pilotName" maxlength="160" placeholder="如：2026秋季学期上线验收" /></label>
        <label>验收用途<textarea v-model.trim="createForm.purpose" rows="3" maxlength="500" placeholder="说明本次真实学期验收用途（至少5字）" /></label>
        <label class="sp-check"><input v-model="createForm.realDataConfirmed" type="checkbox" /><span>我确认当前租户使用真实学校正式数据，不是 mock / 演示 / 测试数据。</span></label>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="busy" @click="createVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="busy" :disabled="!canCreate" @click="createPilot">创建验收</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="completeVisible" title="确认真实学校完整学期完成" mode="modal" size="large" @close="completeVisible = false">
      <div class="sp-form">
        <AppInlineAlert type="danger" description="这是生产验收终态。只有最新六阶段全部通过、零阻断且后端证据哈希一致时才能完成。" />
        <label>确认口令<input v-model.trim="completeForm.confirmText" autocomplete="off" placeholder="CONFIRM_REAL_SEMESTER_COMPLETED" /></label>
        <label>完成说明<textarea v-model.trim="completeForm.completionNote" rows="4" maxlength="500" placeholder="记录学校、学期与验收结论（至少5字）" /></label>
        <AppInlineAlert v-if="actionError" type="danger" :description="actionError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="busy" @click="completeVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="busy" :disabled="completeForm.confirmText !== confirmPhrase || completeForm.completionNote.length < 5" @click="completePilot">确认完成</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="cancelVisible" title="取消真实学期验收" mode="modal" size="small" @close="cancelVisible = false">
      <div class="sp-form">
        <label>取消原因<textarea v-model.trim="cancelReason" rows="4" maxlength="500" placeholder="至少5字" /></label>
        <AppInlineAlert v-if="actionError" type="danger" :description="actionError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="busy" @click="cancelVisible = false">返回</AppButton>
        <AppButton :loading="busy" :disabled="cancelReason.length < 5" @click="cancelPilot">确认取消</AppButton>
      </template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, StatusTag } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppInlineAlert, AppTermEntityPicker } from '@/components/common'
import { academicSemesterPilotApi as api } from '@/modules/academicAffairs/api/academic-semester-pilot.api'
import { toast } from '@/utils/toast'

const CONFIRM_PHRASE = 'CONFIRM_REAL_SEMESTER_COMPLETED'

export default {
  name: 'AaSemesterPilotView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, StatusTag, AppButton, AppDrawer, AppInlineAlert, AppTermEntityPicker },
  data() {
    return {
      confirmPhrase: CONFIRM_PHRASE,
      loading: false, busy: false, error: '', rows: [], detail: null,
      filters: { status: '' }, pagination: { page: 1, pageSize: 50, total: 0 },
      columns: [
        { key: 'pilot', title: '验收 / 学期' }, { key: 'status', title: '状态' },
        { key: 'stages', title: '六阶段' }, { key: 'checked', title: '最新检查' },
        { key: 'actions', title: '操作', align: 'right', width: '190px' }
      ],
      createVisible: false,
      createForm: { termId: '', pilotName: '', purpose: '', realDataConfirmed: false }, formError: '',
      completeVisible: false, completeForm: { confirmText: '', completionNote: '' },
      cancelVisible: false, cancelReason: '', actionError: ''
    }
  },
  computed: {
    canCreate() {
      return Boolean(this.createForm.termId && this.createForm.pilotName.length >= 3 && this.createForm.purpose.length >= 5 && this.createForm.realDataConfirmed)
    }
  },
  created() { this.load() },
  methods: {
    statusLabel(status) {
      return { PREPARING: '准备中', RUNNING: '检查中', BLOCKED: '有阻断', READY_TO_COMPLETE: '可确认完成', COMPLETED: '已完成', CANCELLED: '已取消' }[status] || status || '未知'
    },
    statusType(status) {
      if (status === 'COMPLETED') return 'success'
      if (status === 'READY_TO_COMPLETE') return 'primary'
      if (status === 'BLOCKED') return 'danger'
      if (status === 'CANCELLED') return 'default'
      return 'warning'
    },
    formatTime(value) { return value ? String(value).replace('T', ' ').slice(0, 19) : '—' },
    pretty(value) { try { return JSON.stringify(value || {}, null, 2) } catch { return '{}' } },
    environmentText(env) {
      return `环境：${env.appEnv || '—'} / ${env.deploymentMode || '—'}；DB ${env.dbEnabled ? '已启用' : '未启用'}；mock-login ${env.mockLoginEnabled ? '仍开启' : '已关闭'}；${env.eligibleForRealCompletion ? '允许真实完成确认' : '当前禁止真实完成确认'}`
    },
    search() { this.pagination.page = 1; this.load() },
    onPageChange(page) { this.pagination.page = page; this.load() },
    async load() {
      this.loading = true; this.error = ''
      const res = await api.list({ status: this.filters.status || undefined, page: this.pagination.page, pageSize: this.pagination.pageSize })
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '真实学期验收加载失败'; this.rows = []; return }
      this.rows = res.data?.list || []
      this.pagination.total = Number(res.data?.total || 0)
      if (this.detail?.pilotId) {
        const current = this.rows.find((row) => row.pilotId === this.detail.pilotId)
        if (!current && this.detail.status !== 'COMPLETED') this.detail = null
      }
    },
    async openDetail(row) {
      this.busy = true
      const res = await api.detail(row.pilotId)
      this.busy = false
      if (res.code !== 0) { toast.error(res.message || '验收详情加载失败'); return }
      this.detail = res.data
    },
    async createPilot() {
      if (!this.canCreate || this.busy) return
      this.busy = true; this.formError = ''
      const res = await api.create({ ...this.createForm, termId: Number(this.createForm.termId) })
      this.busy = false
      if (res.code !== 0) { this.formError = res.message || '创建失败'; return }
      this.createVisible = false
      this.createForm = { termId: '', pilotName: '', purpose: '', realDataConfirmed: false }
      toast.success('真实学期验收已创建；尚未执行六阶段检查')
      await this.load(); await this.openDetail(res.data)
    },
    async runCheck(row) {
      if (this.busy) return
      this.busy = true; this.actionError = ''
      const res = await api.check(row.pilotId)
      this.busy = false
      if (res.code !== 0) { toast.error(res.message || '六阶段检查失败'); return }
      this.detail = res.data
      toast.success(`六阶段检查完成：${res.data.passedStageCount || 0}/${res.data.stageCount || 6} 通过，阻断 ${res.data.blockerCount || 0}`)
      await this.load()
    },
    openComplete() {
      this.actionError = ''; this.completeForm = { confirmText: '', completionNote: '' }; this.completeVisible = true
    },
    async completePilot() {
      if (!this.detail || this.completeForm.confirmText !== CONFIRM_PHRASE || this.completeForm.completionNote.length < 5 || this.busy) return
      this.busy = true; this.actionError = ''
      const res = await api.complete(this.detail.pilotId, this.completeForm.confirmText, this.completeForm.completionNote)
      this.busy = false
      if (res.code !== 0) { this.actionError = res.message || '确认完成失败'; return }
      this.completeVisible = false; this.detail = res.data; toast.success('真实学校完整学期验收已确认完成'); await this.load()
    },
    openCancel() { this.cancelReason = ''; this.actionError = ''; this.cancelVisible = true },
    async cancelPilot() {
      if (!this.detail || this.cancelReason.length < 5 || this.busy) return
      this.busy = true; this.actionError = ''
      const res = await api.cancel(this.detail.pilotId, this.cancelReason)
      this.busy = false
      if (res.code !== 0) { this.actionError = res.message || '取消失败'; return }
      this.cancelVisible = false; this.detail = res.data; toast.success('真实学期验收已取消'); await this.load()
    }
  }
}
</script>

<style scoped>
.sp-stack { display: grid; gap: 16px; }
.sp-filter { display: flex; gap: 10px; align-items: end; flex-wrap: wrap; }
.sp-filter label, .sp-form label { display: grid; gap: 6px; font-size: 13px; color: var(--text-secondary, #475569); }
.sp-filter select, .sp-form input, .sp-form textarea { min-height: 36px; padding: 8px 10px; border: 1px solid var(--border-base, #dbe2ea); border-radius: 8px; background: var(--bg-card, #fff); color: var(--text-primary, #0f172a); }
.sp-main { font-weight: 600; color: var(--text-primary, #0f172a); }
.sp-sub, .sp-hash { margin-top: 3px; color: var(--text-tertiary, #64748b); font-size: 12px; overflow-wrap: anywhere; }
.sp-danger { color: var(--danger-600, #dc2626); }
.sp-actions { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.sp-detail { display: grid; gap: 14px; padding: 16px; border: 1px solid var(--border-light, #e5e7eb); border-radius: 12px; background: var(--bg-card, #fff); }
.sp-detail > header { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.sp-detail h3 { margin: 0; }
.sp-detail header p { margin: 5px 0 0; color: var(--text-tertiary, #64748b); }
.sp-facts { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 10px; }
.sp-facts > div { padding: 10px 12px; border-radius: 9px; background: var(--bg-section, #f8fafc); }
.sp-facts span { display: block; color: var(--text-tertiary, #64748b); font-size: 12px; }
.sp-facts strong { display: block; margin-top: 3px; }
.sp-stages { display: grid; gap: 10px; }
.sp-stage { padding: 12px; border: 1px solid var(--border-light, #e5e7eb); border-radius: 10px; }
.sp-stage > header { display: flex; justify-content: space-between; gap: 12px; align-items: center; }
.sp-stage header div { display: flex; gap: 8px; align-items: baseline; }
.sp-stage header span { color: var(--text-tertiary, #64748b); font-size: 11px; }
.sp-stage p { margin: 8px 0; }
.sp-blockers, .sp-warnings { margin: 6px 0; padding-left: 22px; font-size: 13px; }
.sp-blockers { color: var(--danger-700, #b91c1c); }
.sp-warnings { color: var(--warning-700, #a16207); }
.sp-stage details { margin-top: 8px; }
.sp-stage pre { max-height: 260px; overflow: auto; padding: 10px; border-radius: 8px; background: #0f172a; color: #e2e8f0; font-size: 11px; white-space: pre-wrap; overflow-wrap: anywhere; }
.sp-form { display: grid; gap: 14px; }
.sp-check { grid-template-columns: auto 1fr; align-items: flex-start; }
.sp-check input { min-height: 0; margin-top: 2px; }
@media (max-width: 760px) { .sp-detail > header { flex-direction: column; } .sp-actions { justify-content: flex-start; } .sp-facts { grid-template-columns: repeat(2,minmax(0,1fr)); } }
</style>
