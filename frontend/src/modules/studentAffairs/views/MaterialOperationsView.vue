<template>
  <AppPageShell
    title="材料与档案中心"
    subtitle="统一登记缺项、审核学生补交版本，并查看公共文件版本与真实档案 Manifest。"
    role-name="辅导员 / 学院学工 / 学工处 / 心理专项授权角色"
    data-scope-name="后端先按业务权限、班级/学院范围与强敏感逐生授权过滤"
    watermark-purpose="学工材料与档案"
  >
    <template #actions>
      <button class="secondary" :disabled="loading" @click="load">刷新</button>
      <button class="secondary" :disabled="acting === 'backfill'" @click="backfillLegacy">
        {{ acting === 'backfill' ? '正在回填…' : '回填旧材料' }}
      </button>
    </template>

    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在读取材料版本…" @retry="load">
      <div class="metrics">
        <div class="metric"><span>授权范围材料</span><strong>{{ summary.total }}</strong></div>
        <div class="metric"><span>待学生补交</span><strong>{{ summary.missing }}</strong></div>
        <div class="metric"><span>待老师审核</span><strong>{{ summary.pendingReview }}</strong></div>
        <div class="metric"><span>强敏感材料</span><strong>{{ summary.highlySensitive }}</strong></div>
      </div>

      <AppInlineAlert
        type="warning"
        description="心理与困难认定材料不会先拉全量再前端隐藏；无专项权限或学生范围时，后端列表、总数、文件和 Manifest 均不可枚举。"
      />

      <AppSectionCard title="登记材料缺项">
        <div class="form-grid">
          <label><span>业务类型</span><select v-model="form.bizType"><option v-for="item in bizTypes" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
          <label><span>业务记录 ID</span><input v-model.trim="form.bizId" inputmode="numeric" placeholder="从申请详情复制记录ID" /></label>
          <label><span>材料项编码</span><input v-model.trim="form.itemCode" maxlength="100" placeholder="如 FAMILY_PROOF" /></label>
          <label><span>材料项名称</span><input v-model.trim="form.itemName" maxlength="200" placeholder="如 家庭经济情况证明" /></label>
          <label><span>补交截止日期</span><input v-model="form.dueDate" type="date" /></label>
          <label class="wide"><span>缺项说明</span><textarea v-model.trim="form.requirementReason" maxlength="500" placeholder="说明缺失内容和补交要求（5-500字）" /></label>
        </div>
        <div class="toolbar"><button class="primary" :disabled="acting === 'create' || !createValid" @click="createRequirement">{{ acting === 'create' ? '正在登记…' : '登记缺项并通知学生' }}</button></div>
      </AppSectionCard>

      <AppSectionCard title="材料总览与真实版本">
        <div class="toolbar filters">
          <select v-model="statusFilter" @change="loadRequirements"><option value="">全部状态</option><option value="MISSING">待补交</option><option value="RETURNED">退回重补</option><option value="PENDING_REVIEW">待审核</option><option value="ACCEPTED">已验收</option><option value="WAIVED">已免交</option></select>
          <select v-model="sensitivityFilter" @change="loadRequirements"><option value="">全部敏感级别</option><option value="PERSONAL">个人</option><option value="SENSITIVE">敏感</option><option value="HIGHLY_SENSITIVE">强敏感</option></select>
          <button class="secondary" :disabled="loading" @click="loadRequirements">刷新队列</button>
          <button class="primary" :disabled="!selectedRows.length || acting === 'batch'" @click="createReminderBatch">批量提醒已选 {{ selectedRows.length }} 项</button>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th class="check-col"></th><th>业务与学生</th><th>缺项/敏感级别</th><th>状态/期限</th><th>当前公共版本</th><th>责任人</th><th class="ops-col">操作</th></tr></thead>
            <tbody>
              <tr v-for="row in requirements" :key="row.requirementId" :class="{ selectedRow: activeRequirement?.requirementId === row.requirementId }" @click="openRequirement(row)">
                <td @click.stop><input type="checkbox" :disabled="!canRemind(row)" :checked="selected.has(row.requirementId)" @change="toggle(row)" /></td>
                <td><strong>{{ bizLabel(row.bizType) }} #{{ row.bizId }}</strong><small>学生 #{{ row.studentId }} · asset {{ row.assetId || '待回填' }}</small></td>
                <td><strong>{{ row.itemName }}</strong><small>{{ row.requirementReason || row.itemCode }}</small><span class="sensitivity" :class="sensitivityClass(row.sensitivityLevel)">{{ sensitivityText(row.sensitivityLevel) }}</span></td>
                <td><span class="status" :class="statusClass(row.status)">{{ row.statusLabel || row.status }}</span><small :class="{ overdue: row.overdue }">{{ row.dueAt ? `截止 ${fmt(row.dueAt)}` : '未设截止时间' }}</small></td>
                <td>
                  <template v-if="row.currentSubmission">
                    <strong>v{{ row.currentSubmission.versionNo }} · {{ row.currentSubmission.fileName }}</strong>
                    <small>versionId {{ row.currentSubmission.fileVersionId || '待回填' }} · {{ row.currentSubmission.statusLabel }}</small>
                    <div class="inline-actions"><button class="text-btn" @click.stop="preview(row.currentSubmission)">预览</button><button class="text-btn" @click.stop="download(row.currentSubmission)">下载</button></div>
                  </template>
                  <span v-else>尚未提交</span>
                </td>
                <td>{{ row.reviewOwner || '未识别' }}</td>
                <td @click.stop><div class="row-actions"><button v-if="allows(row, 'ACCEPT_MATERIAL')" class="primary small" :disabled="acting === row.requirementId" @click="review(row, 'ACCEPT')">验收</button><button v-if="allows(row, 'RETURN_MATERIAL')" class="danger small" :disabled="acting === row.requirementId" @click="review(row, 'RETURN')">退回</button><button v-if="allows(row, 'WAIVE_MATERIAL')" class="secondary small" :disabled="acting === row.requirementId" @click="review(row, 'WAIVE')">免交</button><span v-if="!(row.allowedActions || []).length">—</span></div></td>
              </tr>
              <tr v-if="!requirements.length"><td colspan="7" class="empty">当前授权与筛选条件下暂无材料；强敏感材料不会出现在无权角色的空壳列表中</td></tr>
            </tbody>
          </table>
        </div>
      </AppSectionCard>

      <div v-if="activeRequirement" class="detail-grid">
        <AppSectionCard title="历史版本（不可覆盖）">
          <div v-if="!activeRequirement.versions?.length" class="empty">暂无提交版本</div>
          <article v-for="version in activeRequirement.versions || []" :key="version.submissionId" class="version-card">
            <div><strong>v{{ version.versionNo }} · {{ version.fileName }}</strong><small>submission {{ version.submissionId }} · fileVersion {{ version.fileVersionId || '待回填' }}</small></div>
            <div><span class="status" :class="statusClass(version.status)">{{ version.statusLabel }}</span><small>{{ fmt(version.submittedAt) }}</small></div>
            <div class="inline-actions"><button class="text-btn" @click="preview(version)">预览</button><button class="text-btn" @click="download(version)">下载</button></div>
          </article>
        </AppSectionCard>

        <AppSectionCard title="最新真实档案 Manifest">
          <div v-if="manifestLoading" class="empty">正在读取档案清单…</div>
          <div v-else-if="manifestError" class="empty">{{ manifestError }}</div>
          <div v-else-if="!manifest" class="empty">该学生尚未完成档案冻结，或当前角色无档案查看权限</div>
          <template v-else>
            <dl class="manifest-meta"><div><dt>Manifest ID</dt><dd>{{ manifest.manifestId }}</dd></div><div><dt>Revision</dt><dd>{{ manifest.revision }}</dd></div><div><dt>状态</dt><dd>{{ manifest.status }}</dd></div><div><dt>SHA-256</dt><dd class="mono">{{ manifest.manifestSha256 }}</dd></div></dl>
            <div class="table-wrap"><table><thead><tr><th>材料</th><th>versionId</th><th>文件</th><th>扫描</th><th>审核</th><th>SHA-256</th></tr></thead><tbody><tr v-for="item in manifest.items || []" :key="`${item.materialCode}-${item.versionId}`"><td>{{ item.materialCode }}</td><td class="mono">{{ item.versionId }}</td><td>{{ item.fileName }}</td><td>{{ item.scanResult }}</td><td>{{ item.reviewStatus }}</td><td class="mono">{{ shortHash(item.sha256) }}</td></tr></tbody></table></div>
          </template>
        </AppSectionCard>
      </div>

      <AppSectionCard title="安全批次与逐条结果">
        <div class="batch-grid">
          <article v-for="job in batchJobs" :key="job.batchJobId" class="batch-card" :class="{ active: activeBatch?.batchJobId === job.batchJobId }" @click="openBatch(job)"><div><strong>{{ job.batchNo }}</strong><small>{{ job.statusLabel || job.status }} · 成功 {{ job.successCount }} / 失败 {{ job.failureCount }}</small></div><button v-if="(job.allowedActions || []).includes('RETRY_FAILED')" class="secondary small" :disabled="acting === `retry-${job.batchJobId}`" @click.stop="retry(job)">重试失败项</button></article>
          <p v-if="!batchJobs.length" class="empty">暂无批次记录</p>
        </div>
        <div v-if="activeBatch" class="batch-detail"><h4>{{ activeBatch.batchNo }} · {{ activeBatch.statusLabel }}</h4><table><thead><tr><th>记录</th><th>动作</th><th>结果</th><th>尝试次数</th><th>失败原因</th></tr></thead><tbody><tr v-for="item in activeBatch.items || []" :key="item.itemId"><td>{{ item.itemKey }}</td><td>{{ item.action }}</td><td><span class="status" :class="statusClass(item.status)">{{ item.status }}</span></td><td>{{ item.attemptCount }}</td><td>{{ item.errorMessage || '—' }}</td></tr></tbody></table></div>
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppInlineAlert, AppPageShell, AppSectionCard } from '@/components/common'
import { affairsOperationsApi } from '@/modules/studentAffairs/api/operations.api'
import { toast } from '@/utils/toast'

export default {
  name: 'MaterialOperationsView',
  components: { AppGlobalState, AppInlineAlert, AppPageShell, AppSectionCard },
  data() {
    return {
      loading: true, acting: '', errorMessage: '', requirements: [], batchJobs: [], activeBatch: null,
      activeRequirement: null, manifest: null, manifestLoading: false, manifestError: '', selected: new Set(),
      statusFilter: '', sensitivityFilter: '',
      summary: { total: 0, missing: 0, pendingReview: 0, accepted: 0, highlySensitive: 0 },
      bizTypes: [
        { value: 'LEAVE', label: '请假' }, { value: 'AID', label: '困难认定（强敏感）' },
        { value: 'MENTAL', label: '心理专项材料（强敏感）' }, { value: 'FUNDING', label: '奖助申请' },
        { value: 'DISCIPLINE', label: '违纪处分' }, { value: 'DISCIPLINE_APPEAL', label: '处分申诉' },
        { value: 'DORM_TRANSFER', label: '调宿申请' }, { value: 'CREDIT_APPEAL', label: '第二课堂申诉' }
      ],
      form: { bizType: 'LEAVE', bizId: '', itemCode: '', itemName: '', requirementReason: '', dueDate: '' }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    createValid() { return /^\d+$/.test(this.form.bizId) && /^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(this.form.itemCode) && this.form.itemName.trim().length >= 2 && (!this.form.requirementReason || this.form.requirementReason.length >= 5) },
    selectedRows() { return this.requirements.filter((row) => this.selected.has(row.requirementId) && this.canRemind(row)) }
  },
  mounted() { this.load() },
  methods: {
    fmt(value) { return value ? String(value).replace('T', ' ').slice(0, 16) : '' },
    shortHash(value) { const text = String(value || ''); return text ? `${text.slice(0, 10)}…${text.slice(-8)}` : '-' },
    bizLabel(value) { return this.bizTypes.find((x) => x.value === value)?.label || value },
    allows(row, action) { return (row.allowedActions || []).includes(action) },
    canRemind(row) { return ['MISSING', 'RETURNED'].includes(row.status) && row.version !== undefined && row.version !== null },
    statusClass(status) { return { ACCEPTED: 'ok', SUCCESS: 'ok', WAIVED: 'ok', APPROVED: 'ok', PENDING_REVIEW: 'wait', SUBMITTED: 'wait', MISSING: 'warn', RETURNED: 'warn', REJECTED: 'bad', FAILED: 'bad', PARTIAL_SUCCESS: 'warn', SUPERSEDED: 'muted' }[status] || '' },
    sensitivityText(value) { return { PERSONAL: '个人', SENSITIVE: '敏感', HIGHLY_SENSITIVE: '强敏感' }[value] || value || '敏感' },
    sensitivityClass(value) { return value === 'HIGHLY_SENSITIVE' ? 'high' : (value === 'SENSITIVE' ? 'sensitive' : '') },
    async load() { this.loading = true; this.errorMessage = ''; try { await Promise.all([this.loadRequirements(), this.loadBatches()]) } catch (e) { this.errorMessage = e?.message || '材料工作台加载失败' } finally { this.loading = false } },
    async loadRequirements() {
      const data = await affairsOperationsApi.listCenter({ status: this.statusFilter || undefined, sensitivityLevel: this.sensitivityFilter || undefined, page: 1, pageSize: 100 })
      this.requirements = data?.items || []; this.summary = { ...this.summary, ...(data?.summary || {}), total: Number(data?.total || 0) }
      const visible = new Set(this.requirements.map((x) => x.requirementId)); this.selected = new Set([...this.selected].filter((id) => visible.has(id)))
      if (this.activeRequirement) this.activeRequirement = this.requirements.find((x) => x.requirementId === this.activeRequirement.requirementId) || null
    },
    async loadBatches() { const data = await affairsOperationsApi.listBatchJobs({ page: 1, pageSize: 50 }); this.batchJobs = data?.items || [] },
    toggle(row) { const next = new Set(this.selected); next.has(row.requirementId) ? next.delete(row.requirementId) : next.add(row.requirementId); this.selected = next },
    async openRequirement(row) { this.activeRequirement = row; this.manifest = null; this.manifestError = ''; this.manifestLoading = true; try { const data = await affairsOperationsApi.getLatestManifest(row.studentId); this.manifest = data?.manifest || null } catch (e) { this.manifestError = e?.message || '档案清单不可见' } finally { this.manifestLoading = false } },
    async createRequirement() {
      if (!this.createValid) return toast.warning('请填写有效业务记录、材料编码、名称和缺项说明')
      this.acting = 'create'
      try { await affairsOperationsApi.createRequirement({ bizType: this.form.bizType, bizId: Number(this.form.bizId), itemCode: this.form.itemCode.toUpperCase(), itemName: this.form.itemName, requirementReason: this.form.requirementReason || undefined, dueAt: this.form.dueDate ? `${this.form.dueDate}T23:59:59` : undefined }); toast.success('材料缺项已登记并通知学生'); Object.assign(this.form, { bizId: '', itemCode: '', itemName: '', requirementReason: '', dueDate: '' }); await this.loadRequirements() } catch (e) { toast.error(e?.message || '登记失败') } finally { this.acting = '' }
    },
    async review(row, action) {
      let reason = ''; if (action === 'RETURN') { reason = window.prompt('请输入5-500字退回原因') || ''; if (reason.trim().length < 5) return toast.warning('退回原因至少5字') }
      if (action === 'WAIVE') reason = window.prompt('填写免交说明（选填）') || ''; if (action === 'ACCEPT' && !window.confirm(`确认验收 ${row.itemName} 的当前版本？`)) return
      this.acting = row.requirementId
      try { await affairsOperationsApi.reviewRequirement(row.requirementId, action, reason, row.version); toast.success('材料状态已更新'); await this.loadRequirements(); if (this.activeRequirement?.requirementId === row.requirementId) this.activeRequirement = this.requirements.find((x) => x.requirementId === row.requirementId) || null } catch (e) { toast.error(e?.message || '材料审核失败') } finally { this.acting = '' }
    },
    async backfillLegacy() { if (!window.confirm('确认幂等回填当前学校尚未接入公共版本链的旧材料？')) return; this.acting = 'backfill'; try { const result = await affairsOperationsApi.backfill(500); toast.success(`回填完成：补交版本 ${result.convertedSubmissions}，旧附件 ${result.convertedAttachments}`); await this.loadRequirements() } catch (e) { toast.error(e?.message || '旧材料回填失败') } finally { this.acting = '' } },
    async createReminderBatch() {
      if (!this.selectedRows.length || !window.confirm(`确认向 ${this.selectedRows.length} 项缺失材料发送提醒？`)) return
      this.acting = 'batch'; try { const result = await affairsOperationsApi.createBatchJob({ jobType: 'MATERIAL_REMIND', idempotencyKey: `material-remind:${Date.now()}`, items: this.selectedRows.map((row) => ({ requirementId: Number(row.requirementId), version: Number(row.version) })) }); toast.success(`批次完成：成功 ${result.successCount}，失败 ${result.failureCount}`); this.selected = new Set(); await Promise.all([this.loadRequirements(), this.loadBatches()]) } catch (e) { toast.error(e?.message || '批量提醒失败') } finally { this.acting = '' }
    },
    async openBatch(job) { try { this.activeBatch = await affairsOperationsApi.getBatchJob(job.batchJobId) } catch (e) { toast.error(e?.message || '批次详情加载失败') } },
    async retry(job) { this.acting = `retry-${job.batchJobId}`; try { const result = await affairsOperationsApi.retryFailed(job.batchJobId); toast.success(`重试完成：成功 ${result.successCount}，失败 ${result.failureCount}`); this.activeBatch = result; await this.loadBatches() } catch (e) { toast.error(e?.message || '失败项重试失败') } finally { this.acting = '' } },
    async preview(version) { try { await affairsOperationsApi.previewMaterial(version.fileId) } catch (e) { toast.error(e?.message || '材料预览失败') } },
    async download(version) { try { await affairsOperationsApi.downloadMaterial(version.fileId, version.fileName) } catch (e) { toast.error(e?.message || '材料下载失败') } }
  }
}
</script>

<style scoped>
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}.metric{padding:16px;border:1px solid #e7ebf1;border-radius:12px;background:#fff}.metric span,.metric strong{display:block}.metric span{font-size:12px;color:#667085}.metric strong{font-size:26px;margin-top:5px}.form-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.form-grid label span{display:block;font-size:12px;color:#667085;margin-bottom:5px}.form-grid input,.form-grid select,.form-grid textarea,.filters select{box-sizing:border-box;width:100%;min-height:38px;border:1px solid #d9dee7;border-radius:8px;padding:8px 10px;background:#fff}.form-grid textarea{min-height:82px}.wide{grid-column:1/-1}.toolbar{display:flex;gap:10px;align-items:center;justify-content:flex-end;margin-top:14px}.filters{justify-content:flex-start}.filters select{width:190px}.primary,.secondary,.danger{border:0;border-radius:8px;padding:9px 14px;cursor:pointer}.primary{background:#315efb;color:#fff}.secondary{background:#eef2f7;color:#344054}.danger{background:#fee4e2;color:#b42318}.small{padding:6px 9px;font-size:12px}.primary:disabled,.secondary:disabled,.danger:disabled{opacity:.5;cursor:not-allowed}.table-wrap{overflow:auto;margin-top:12px}table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:11px 9px;border-bottom:1px solid #edf0f4;vertical-align:top}td strong,td small{display:block}td small{color:#667085;margin-top:4px}.check-col{width:34px}.ops-col{min-width:185px}.row-actions,.inline-actions{display:flex;gap:7px;flex-wrap:wrap}.status,.sensitivity{display:inline-block;padding:3px 7px;border-radius:6px;background:#eef2f7;margin-top:5px}.status.ok{background:#dcfae6;color:#067647}.status.wait{background:#eaf0ff;color:#1d4ed8}.status.warn{background:#fff3d6;color:#b54708}.status.bad,.sensitivity.high{background:#fee4e2;color:#b42318}.status.muted{color:#667085}.sensitivity.sensitive{background:#fff3d6;color:#b54708}.overdue{color:#b42318}.text-btn{all:unset;color:#315efb;cursor:pointer}.empty{text-align:center;color:#98a2b3;padding:24px}.selectedRow{background:#f7f9ff}.detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.version-card{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:14px;align-items:center;padding:12px;border-bottom:1px solid #edf0f4}.version-card strong,.version-card small{display:block}.version-card small{color:#667085;margin-top:4px}.manifest-meta{display:grid;grid-template-columns:1fr 1fr;gap:10px}.manifest-meta div{padding:10px;border:1px solid #edf0f4;border-radius:8px}.manifest-meta dt{font-size:12px;color:#667085}.manifest-meta dd{margin:5px 0 0;word-break:break-all}.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}.batch-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.batch-card{display:flex;justify-content:space-between;gap:10px;align-items:center;padding:12px;border:1px solid #e7ebf1;border-radius:10px;cursor:pointer}.batch-card.active{border-color:#315efb;background:#f5f7ff}.batch-card strong,.batch-card small{display:block}.batch-card small{margin-top:4px;color:#667085}.batch-detail{margin-top:16px;overflow:auto}
@media(max-width:1000px){.metrics,.form-grid,.batch-grid,.detail-grid{grid-template-columns:1fr 1fr}}@media(max-width:680px){.metrics,.form-grid,.batch-grid,.detail-grid{grid-template-columns:1fr}.wide{grid-column:auto}.filters{align-items:stretch;flex-direction:column}.filters select{width:100%}.version-card{grid-template-columns:1fr}}
</style>
