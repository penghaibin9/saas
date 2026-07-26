<template>
  <ModulePageShell
    title="岗位实习合规办理工作台"
    subtitle="上岗、过程、归档、事故、豁免与监管证据统一办理"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-stack">
      <AppInlineAlert
        v-if="!batchStore.selectedBatchId"
        type="warning"
        title="请先选择实习批次"
        description="所有统计、台账、审核和证据包都严格使用当前批次。"
      />
      <template v-else>
        <AppInlineAlert
          v-if="auditHealth && auditHealth.healthy === false"
          type="error"
          title="审计持久化异常"
          :description="auditHealth.message || '审计积压或消费异常，请先处理后再执行高风险操作。'"
        />
        <div class="workbench-head mp-card">
          <div>
            <strong>{{ workbench.batch?.name || '当前批次' }}</strong>
            <p class="mp-note">规则 {{ stats.ruleVersion || '-' }} · 数据生成于 {{ workbench.generatedAt || stats.evaluatedAt || '-' }}</p>
          </div>
          <div class="head-actions">
            <span class="status-pill">{{ workbench.batch?.status || '-' }}</span>
            <AppButton variant="ghost" size="sm" @click="load">刷新</AppButton>
          </div>
        </div>

        <nav class="work-tabs" aria-label="合规办理工作区">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            type="button"
            class="work-tab"
            :class="{ 'is-active': activeTab === tab.key }"
            @click="activeTab = tab.key"
          >
            {{ tab.label }}
            <span v-if="tab.count != null" class="tab-count">{{ tab.count }}</span>
          </button>
        </nav>

        <template v-if="activeTab === 'overview'">
          <div class="sa-grid sa-grid--metrics">
            <button
              v-for="metric in metrics"
              :key="metric.metricCode"
              type="button"
              class="mp-card metric-card"
              :class="{ 'is-active': selectedFilter === metric.drilldownFilter }"
              @click="selectedFilter = metric.drilldownFilter"
            >
              <span class="mp-note">{{ metric.metricLabel }}</span>
              <strong>{{ metric.count }}</strong>
            </button>
          </div>
          <section class="mp-card">
            <div class="mp-card__head">
              <div>
                <strong>{{ selectedMetric?.metricLabel || '批次学生' }}</strong>
                <p class="mp-note">列表、指标、上岗与归档动作共用同一权威规则。</p>
              </div>
            </div>
            <div class="table-wrap">
              <table class="mp-table">
                <thead><tr><th>学号</th><th>姓名</th><th>指导教师</th><th>状态</th><th>上岗阻断</th><th>归档阻断</th><th>操作</th></tr></thead>
                <tbody>
                  <tr v-for="row in drilldownRows" :key="row.internshipId">
                    <td>{{ row.studentNo }}</td><td>{{ row.studentName }}</td>
                    <td>{{ row.advisorName || '-' }}</td><td>{{ row.recordStatus }}</td>
                    <td>{{ blockerText(row.blockers) }}</td>
                    <td>{{ blockerText(row.archiveBlockers) }}</td>
                    <td><button class="mp-link" @click="openStudent(row)">学生详情</button></td>
                  </tr>
                  <tr v-if="!drilldownRows.length"><td colspan="7" class="empty-cell">当前口径下暂无学生</td></tr>
                </tbody>
              </table>
            </div>
          </section>
        </template>

        <template v-else-if="activeTab === 'consents'">
          <section v-if="can('internship.consent.manage')" class="mp-card action-panel">
            <div class="mp-card__head"><strong>下发知情确认任务</strong><span class="mp-note">教师只能下发、催办、作废，不能代学生或监护人确认。</span></div>
            <div class="form-grid">
              <label>学生<select v-model="forms.consent.internshipId"><option value="">请选择</option><option v-for="s in students" :key="s.internshipId" :value="s.internshipId">{{ s.studentNo }} · {{ s.studentName }}</option></select></label>
              <label>确认人<select v-model="forms.consent.consentType"><option value="STUDENT">学生本人</option><option value="GUARDIAN">已绑定监护人</option></select></label>
              <label>正文版本<input v-model.trim="forms.consent.contentVersion" placeholder="例如 2026-v1" /></label>
              <label class="span-2">知情正文<textarea v-model.trim="forms.consent.contentSnapshot" rows="5" placeholder="必须是本次下发的完整正文快照" /></label>
            </div>
            <AppButton :disabled="acting" @click="createConsent">创建并下发</AppButton>
          </section>
          <section class="mp-card">
            <div class="mp-card__head"><strong>知情确认台账</strong><span class="mp-note">{{ workbench.consents?.length || 0 }} 条</span></div>
            <div class="table-wrap"><table class="mp-table"><thead><tr><th>学生</th><th>类型</th><th>正文版本</th><th>状态</th><th>阅读</th><th>确认</th><th>版本</th><th>操作</th></tr></thead><tbody>
              <tr v-for="row in workbench.consents || []" :key="row.id">
                <td>{{ row.studentNo }} · {{ row.studentName }}</td><td>{{ row.consentType === 'GUARDIAN' ? '监护人' : '学生' }}</td>
                <td>{{ row.contentVersion }}</td><td>{{ row.status }}</td><td>{{ fmt(row.viewedAt) }}</td><td>{{ fmt(row.confirmedAt) }}</td><td>{{ row.version }}</td>
                <td><button v-if="row.status === 'PENDING' && can('internship.consent.manage')" class="danger-link" @click="revokeConsent(row)">作废</button></td>
              </tr><tr v-if="!(workbench.consents || []).length"><td colspan="8" class="empty-cell">暂无知情任务</td></tr>
            </tbody></table></div>
          </section>
        </template>

        <template v-else-if="activeTab === 'safety'">
          <section v-if="can('internship.safety.manage')" class="mp-card action-panel">
            <div class="mp-card__head"><strong>配置安全教育课程</strong><span class="mp-note">课程升级后旧版本完成记录不能满足新版本。</span></div>
            <div class="form-grid">
              <label>课程名称<input v-model.trim="forms.safety.title" /></label>
              <label>课程版本<input v-model.trim="forms.safety.courseVersion" /></label>
              <label>要求分钟<input v-model.number="forms.safety.requiredMinutes" type="number" min="0" /></label>
              <label>及格分<input v-model.number="forms.safety.passingScore" type="number" min="0" max="100" /></label>
              <label>最大次数<input v-model.number="forms.safety.maxAttempts" type="number" min="1" /></label>
              <label class="checkbox-label"><input v-model="forms.safety.requireCommitment" type="checkbox" />要求安全承诺</label>
              <label class="span-2">课程正文<textarea v-model.trim="forms.safety.contentSnapshot" rows="5" /></label>
            </div>
            <AppButton :disabled="acting" @click="createSafetyCourse">保存有效课程</AppButton>
          </section>
          <section class="mp-card">
            <div class="mp-card__head"><strong>课程配置</strong><span class="mp-note">{{ workbench.safetyCourses?.length || 0 }} 门</span></div>
            <div class="table-wrap"><table class="mp-table"><thead><tr><th>课程</th><th>版本</th><th>状态</th><th>时长</th><th>及格线</th><th>承诺</th></tr></thead><tbody>
              <tr v-for="row in workbench.safetyCourses || []" :key="row.id"><td>{{ row.title }}</td><td>{{ row.courseVersion }}</td><td>{{ row.status }}</td><td>{{ row.requiredMinutes }}分钟</td><td>{{ row.passingScore }}</td><td>{{ row.requireCommitment ? '必需' : '否' }}</td></tr>
              <tr v-if="!(workbench.safetyCourses || []).length"><td colspan="6" class="empty-cell">当前批次未配置课程；启用安全门禁时将被判为配置错误</td></tr>
            </tbody></table></div>
          </section>
          <section class="mp-card">
            <div class="mp-card__head"><strong>学生学习与审核</strong></div>
            <div class="table-wrap"><table class="mp-table"><thead><tr><th>学生</th><th>课程</th><th>记录/当前版本</th><th>状态</th><th>时长</th><th>分数</th><th>版本</th><th>审核</th></tr></thead><tbody>
              <tr v-for="row in workbench.safetyCompletions || []" :key="row.id">
                <td>{{ row.studentNo }} · {{ row.studentName }}</td><td>{{ row.courseTitle }}</td><td>{{ row.courseVersion }} / {{ row.currentCourseVersion }}</td><td>{{ row.status }}</td><td>{{ row.studiedMinutes }}分钟</td><td>{{ row.score ?? '-' }}</td><td>{{ row.version }}</td>
                <td><template v-if="row.status === 'PENDING_REVIEW' && can('internship.safety.manage')"><button class="mp-link" @click="reviewSafety(row, 'APPROVE')">通过</button><button class="danger-link" @click="reviewSafety(row, 'REJECT')">退回</button></template></td>
              </tr><tr v-if="!(workbench.safetyCompletions || []).length"><td colspan="8" class="empty-cell">暂无学生学习记录</td></tr>
            </tbody></table></div>
          </section>
        </template>

        <template v-else-if="activeTab === 'filings'">
          <section v-if="can('internship.filing.review')" class="mp-card action-panel">
            <div class="mp-card__head"><strong>新建特殊备案</strong><span class="mp-note">经办人创建并提交，学院审核后进入学校终审。</span></div>
            <div class="form-grid">
              <label>学生<select v-model="forms.filing.internshipId"><option value="">请选择</option><option v-for="s in students" :key="s.internshipId" :value="s.internshipId">{{ s.studentNo }} · {{ s.studentName }}</option></select></label>
              <label>备案类型<select v-model="forms.filing.filingType"><option value="MINOR">未成年</option><option value="CROSS_REGION">跨区域</option><option value="HIGH_RISK">高风险岗位</option><option value="NIGHT_SHIFT">夜班</option><option value="OTHER">其他</option></select></label>
              <label class="span-2">触发原因<textarea v-model.trim="forms.filing.triggerReason" rows="3" /></label>
              <label class="span-2">风险说明<textarea v-model.trim="forms.filing.riskDescription" rows="3" /></label>
              <label>依据附件<input type="file" @change="uploadToForm($event, 'filing', 'fileIds', 'INTERNSHIP_FILING')" /></label>
              <span class="file-note">{{ fileText(forms.filing.fileIds) }}</span>
            </div>
            <AppButton :disabled="acting" @click="createFiling">创建并提交学院审核</AppButton>
          </section>
          <section class="mp-card"><div class="mp-card__head"><strong>特殊备案台账</strong></div><div class="table-wrap"><table class="mp-table"><thead><tr><th>学生</th><th>类型</th><th>状态</th><th>原因</th><th>学院/学校意见</th><th>版本</th><th>操作</th></tr></thead><tbody>
            <tr v-for="row in workbench.filings || []" :key="row.id"><td>{{ row.studentNo }} · {{ row.studentName }}</td><td>{{ row.filingType }}</td><td>{{ row.status }}</td><td>{{ row.triggerReason }}</td><td>{{ row.collegeComment || '-' }} / {{ row.schoolComment || '-' }}</td><td>{{ row.version }}</td><td>
              <button v-if="row.status === 'DRAFT' && can('internship.filing.review')" class="mp-link" @click="filingAction(row, 'COLLEGE', 'submit')">提交</button>
              <template v-if="row.status === 'PENDING_COLLEGE' && can('internship.filing.review')"><button class="mp-link" @click="filingAction(row, 'COLLEGE', 'approve')">学院通过</button><button class="danger-link" @click="filingAction(row, 'COLLEGE', 'reject')">学院退回</button></template>
              <template v-if="row.status === 'PENDING_SCHOOL' && can('internship.filing.review')"><button class="mp-link" @click="filingAction(row, 'SCHOOL', 'approve')">学校通过</button><button class="danger-link" @click="filingAction(row, 'SCHOOL', 'reject')">学校退回</button></template>
            </td></tr><tr v-if="!(workbench.filings || []).length"><td colspan="7" class="empty-cell">暂无特殊备案</td></tr>
          </tbody></table></div></section>
        </template>

        <template v-else-if="activeTab === 'incidents'">
          <section v-if="can('internship.incident.report')" class="mp-card action-panel">
            <div class="mp-card__head"><strong>上报事故</strong><span class="mp-note">HIGH/CRITICAL 自动联动高风险单。</span></div>
            <div class="form-grid">
              <label>学生<select v-model="forms.incident.internshipId"><option value="">请选择</option><option v-for="s in students" :key="s.internshipId" :value="s.internshipId">{{ s.studentNo }} · {{ s.studentName }}</option></select></label>
              <label>严重程度<select v-model="forms.incident.severity"><option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>CRITICAL</option></select></label>
              <label>事故类型<input v-model.trim="forms.incident.incidentType" /></label>
              <label>发生时间<input v-model="forms.incident.occurredAt" type="datetime-local" /></label>
              <label>地点<input v-model.trim="forms.incident.location" /></label>
              <label class="span-2">情况摘要<textarea v-model.trim="forms.incident.summary" rows="3" /></label>
              <label class="span-2">已采取应急措施<textarea v-model.trim="forms.incident.emergencyAction" rows="3" /></label>
              <label>现场材料<input type="file" @change="uploadToForm($event, 'incident', 'fileIds', 'INTERNSHIP_INCIDENT')" /></label>
              <span class="file-note">{{ fileText(forms.incident.fileIds) }}</span>
            </div>
            <AppButton :disabled="acting" @click="reportIncident">提交事故报告</AppButton>
          </section>
          <section class="mp-card"><div class="mp-card__head"><strong>事故处置台账</strong></div><div class="table-wrap"><table class="mp-table"><thead><tr><th>编号</th><th>学生</th><th>等级</th><th>状态</th><th>摘要</th><th>版本</th><th>合法下一步</th></tr></thead><tbody>
            <tr v-for="row in workbench.incidents || []" :key="row.id"><td>{{ row.incidentNo }}</td><td>{{ row.studentNo }} · {{ row.studentName }}</td><td>{{ row.severity }}</td><td>{{ row.status }}</td><td>{{ row.summary }}</td><td>{{ row.version }}</td><td><button v-for="target in incidentTargets(row.status)" :key="target" class="mp-link" @click="transitionIncident(row, target)">{{ target }}</button></td></tr>
            <tr v-if="!(workbench.incidents || []).length"><td colspan="7" class="empty-cell">暂无事故记录</td></tr>
          </tbody></table></div></section>
          <section v-if="can('internship.incident.handle')" class="mp-card action-panel">
            <div class="mp-card__head"><strong>新建批次应急预案</strong></div>
            <div class="form-grid">
              <label>预案名称<input v-model.trim="forms.emergency.planName" /></label><label>责任人<input v-model.trim="forms.emergency.responsiblePerson" /></label>
              <label>应急电话<input v-model.trim="forms.emergency.emergencyContact" /></label><label>备用电话<input v-model.trim="forms.emergency.backupContact" /></label>
              <label>医院/支援单位<input v-model.trim="forms.emergency.hospitalOrSupport" /></label>
              <label class="span-2">处置步骤<textarea v-model.trim="forms.emergency.responseSteps" rows="4" /></label>
              <label>预案附件<input type="file" @change="uploadToForm($event, 'emergency', 'fileIds', 'INTERNSHIP_EMERGENCY')" /></label><span class="file-note">{{ fileText(forms.emergency.fileIds) }}</span>
            </div>
            <AppButton :disabled="acting" @click="createEmergency">创建并提交审核</AppButton>
          </section>
          <section class="mp-card"><div class="mp-card__head"><strong>应急预案</strong></div><div class="table-wrap"><table class="mp-table"><thead><tr><th>名称</th><th>责任人</th><th>联系电话</th><th>状态</th><th>版本</th><th>操作</th></tr></thead><tbody>
            <tr v-for="row in workbench.emergencyPlans || []" :key="row.id"><td>{{ row.planName }}</td><td>{{ row.responsiblePerson }}</td><td>{{ row.emergencyContact }}</td><td>{{ row.status }}</td><td>{{ row.version }}</td><td><button v-if="row.status === 'DRAFT'" class="mp-link" @click="emergencyAction(row, 'SUBMIT')">提交审核</button><template v-if="row.status === 'PENDING_REVIEW'"><button class="mp-link" @click="emergencyAction(row, 'APPROVE')">通过</button><button class="danger-link" @click="emergencyAction(row, 'REJECT')">退回</button></template></td></tr>
            <tr v-if="!(workbench.emergencyPlans || []).length"><td colspan="6" class="empty-cell">暂无应急预案</td></tr>
          </tbody></table></div></section>
        </template>

        <template v-else-if="activeTab === 'exemptions'">
          <section v-if="can('internship.compliance.exempt.request')" class="mp-card action-panel">
            <div class="mp-card__head"><strong>申请合规豁免</strong><span class="mp-note">只允许有期限、有依据的个案申请，不会自动永久放行。</span></div>
            <div class="form-grid">
              <label>学生<select v-model="forms.exemption.internshipId"><option value="">请选择</option><option v-for="s in students" :key="s.internshipId" :value="s.internshipId">{{ s.studentNo }} · {{ s.studentName }}</option></select></label>
              <label>检查项代码<input v-model.trim="forms.exemption.checkCode" placeholder="例如 specialFiling" /></label>
              <label>有效期至<input v-model="forms.exemption.validUntil" type="datetime-local" /></label>
              <label class="span-2">申请原因<textarea v-model.trim="forms.exemption.reason" rows="3" /></label>
              <label>依据附件<input type="file" @change="uploadToForm($event, 'exemption', 'evidenceFileIds', 'COMPLIANCE_EVIDENCE')" /></label><span class="file-note">{{ fileText(forms.exemption.evidenceFileIds) }}</span>
            </div>
            <AppButton :disabled="acting" @click="requestExemption">提交豁免申请</AppButton>
          </section>
          <section class="mp-card"><div class="mp-card__head"><strong>豁免台账</strong></div><div class="table-wrap"><table class="mp-table"><thead><tr><th>学生</th><th>检查项</th><th>原因</th><th>有效期</th><th>状态</th><th>申请/审批人</th><th>版本</th><th>操作</th></tr></thead><tbody>
            <tr v-for="row in workbench.exemptions || []" :key="row.id"><td>{{ row.studentNo }} · {{ row.studentName }}</td><td>{{ row.checkCode }}</td><td>{{ row.reason }}</td><td>{{ fmt(row.validUntil) }}</td><td>{{ row.status }}</td><td>{{ row.requestedByName || '-' }} / {{ row.reviewedByName || '-' }}</td><td>{{ row.version }}</td><td><template v-if="row.status === 'PENDING_REVIEW' && can('internship.compliance.exempt.approve')"><button class="mp-link" @click="reviewExemption(row, 'APPROVE')">批准</button><button class="danger-link" @click="reviewExemption(row, 'REJECT')">拒绝</button></template></td></tr>
            <tr v-if="!(workbench.exemptions || []).length"><td colspan="8" class="empty-cell">暂无豁免记录</td></tr>
          </tbody></table></div></section>
        </template>

        <template v-else-if="activeTab === 'evidence'">
          <section class="mp-card action-panel">
            <div class="mp-card__head"><strong>生成监管证据包</strong><span class="mp-note">包含真实附件、对象版本、逐文件SHA-256、缺失项和审计。</span></div>
            <div class="form-grid">
              <label>包类型<select v-model="forms.package.packageType"><option value="BATCH">批次包</option><option value="STUDENT">学生包</option></select></label>
              <label v-if="forms.package.packageType === 'STUDENT'">学生<select v-model="forms.package.targetId"><option value="">请选择</option><option v-for="s in students" :key="s.internshipId" :value="s.internshipId">{{ s.studentNo }} · {{ s.studentName }}</option></select></label>
            </div>
            <AppButton v-if="can('internship.evidence.export')" :disabled="acting" @click="generatePackage">生成版本化证据包</AppButton>
          </section>
          <section class="mp-card"><div class="mp-card__head"><strong>证据包历史</strong></div><div class="table-wrap"><table class="mp-table"><thead><tr><th>类型</th><th>目标</th><th>版本</th><th>状态</th><th>文件/缺失</th><th>SHA-256</th><th>生成人</th><th>时间</th><th>下载</th></tr></thead><tbody>
            <tr v-for="row in workbench.evidencePackages || []" :key="row.id"><td>{{ row.packageType }}</td><td>{{ row.targetId }}</td><td>v{{ row.packageVersion }}</td><td>{{ row.status }}</td><td>{{ row.fileCount }} / {{ row.missingCount }}</td><td class="hash-cell">{{ row.packageSha256 || '-' }}</td><td>{{ row.generatedByName }}</td><td>{{ fmt(row.generatedAt) }}</td><td><button v-if="['READY','READY_WITH_MISSING'].includes(row.status) && can('internship.evidence.export')" class="mp-link" @click="downloadPackage(row)">下载ZIP</button></td></tr>
            <tr v-if="!(workbench.evidencePackages || []).length"><td colspan="9" class="empty-cell">暂无证据包</td></tr>
          </tbody></table></div></section>
        </template>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppInlineAlert } from '@/components/common'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { complianceApi } from '@/modules/internship/api/compliance.api'
import { getPermissionPatterns } from '@/security/permissionGate'

function freshForms() {
  return {
    consent: { internshipId: '', consentType: 'STUDENT', contentVersion: '2026-v1', contentSnapshot: '' },
    safety: { title: '', courseVersion: 'v1', requiredMinutes: 60, passingScore: 80, maxAttempts: 3, requireCommitment: true, contentSnapshot: '' },
    filing: { internshipId: '', filingType: 'OTHER', triggerReason: '', riskDescription: '', fileIds: [] },
    incident: { internshipId: '', severity: 'MEDIUM', incidentType: 'OTHER', occurredAt: '', location: '', summary: '', emergencyAction: '', fileIds: [] },
    emergency: { planName: '', responsiblePerson: '', emergencyContact: '', backupContact: '', hospitalOrSupport: '', responseSteps: '', fileIds: [] },
    exemption: { internshipId: '', checkCode: '', reason: '', validUntil: '', evidenceFileIds: [] },
    package: { packageType: 'BATCH', targetId: '' }
  }
}

export default {
  name: 'InternshipComplianceView',
  components: { ModulePageShell, LoadingState, ErrorState, AppButton, AppInlineAlert },
  props: { ctx: { type: Object, required: true } },
  data: () => ({
    loading: false, acting: false, error: '', activeTab: 'overview',
    stats: {}, workbench: {}, auditHealth: null, selectedFilter: 'ALL', forms: freshForms()
  }),
  computed: {
    batchStore() { return useInternshipBatchStore() },
    metrics() { return this.stats.metrics || [] },
    students() { return this.stats.drilldowns?.ALL || [] },
    selectedMetric() { return this.metrics.find((item) => item.drilldownFilter === this.selectedFilter) },
    drilldownRows() { return this.stats.drilldowns?.[this.selectedFilter] || [] },
    tabs() {
      const counts = this.workbench.counts || {}
      return [
        { key: 'overview', label: '合规总览', count: this.stats.blocked || 0 },
        { key: 'consents', label: '知情确认', count: counts.consentPending || 0 },
        { key: 'safety', label: '安全教育', count: counts.safetyPending || 0 },
        { key: 'filings', label: '特殊备案', count: counts.filingPending || 0 },
        { key: 'incidents', label: '事故与应急', count: counts.incidentOpen || 0 },
        { key: 'exemptions', label: '豁免审批', count: counts.exemptionPending || 0 },
        { key: 'evidence', label: '监管证据包', count: counts.packageReady || 0 }
      ]
    }
  },
  watch: {
    'batchStore.selectedBatchId': { immediate: true, handler() { this.load() } }
  },
  methods: {
    can(permission) {
      const patterns = getPermissionPatterns() || []
      return patterns.includes('*') || patterns.some((pattern) =>
        pattern === permission || (pattern.endsWith('.*') && permission.startsWith(pattern.slice(0, -1))))
    },
    fmt(value) { return value ? String(value).replace('T', ' ').slice(0, 16) : '-' },
    fileText(ids) { return ids?.length ? `已上传 ${ids.length} 个文件` : '尚未上传' },
    blockerText(items) { return items?.length ? items.map((item) => `${item.label}：${item.reason}`).join('；') : '无' },
    async load() {
      const batchId = this.batchStore.selectedBatchId
      if (!batchId) { this.stats = {}; this.workbench = {}; return }
      this.loading = true; this.error = ''
      const [stats, workbench, health] = await Promise.all([
        complianceApi.batchStats(batchId), complianceApi.workbench(batchId), complianceApi.auditHealth()
      ])
      this.loading = false
      if (stats.code !== 0) { this.error = stats.message || '合规统计加载失败'; return }
      if (workbench.code !== 0) { this.error = workbench.message || '合规办理台账加载失败'; return }
      this.stats = stats.data || {}; this.workbench = workbench.data || {}
      this.auditHealth = health.code === 0 ? health.data : { healthy: false, message: health.message }
      if (!this.stats.drilldowns?.[this.selectedFilter]) this.selectedFilter = 'ALL'
    },
    openStudent(row) { this.$router.push(row.route || `/admin/internship/students/${row.internshipId}`) },
    async run(resultPromise, successMessage) {
      if (this.acting) return false
      this.acting = true
      try {
        const result = await resultPromise
        if (result.code !== 0) throw new Error(result.message || '操作失败')
        this.$message?.success?.(successMessage)
        await this.load()
        return true
      } catch (error) {
        this.$message?.error?.(error.message || '操作失败')
        return false
      } finally { this.acting = false }
    },
    async uploadToForm(event, formKey, field, bizType) {
      const file = event.target.files?.[0]
      if (!file) return
      const result = await complianceApi.uploadEvidence(file, bizType)
      event.target.value = ''
      if (result.code !== 0) { this.$message?.error?.(result.message); return }
      const fileId = result.data?.fileId
      if (fileId) this.forms[formKey][field] = [...(this.forms[formKey][field] || []), fileId]
    },
    createConsent() {
      const form = this.forms.consent
      if (!form.internshipId || !form.contentVersion || !form.contentSnapshot) return this.$message?.warning?.('请选择学生并填写正文版本和完整正文')
      this.run(complianceApi.createConsent({ ...form, deliveryChannel: 'SYSTEM_MESSAGE' }), '知情确认任务已下发')
    },
    revokeConsent(row) {
      const reason = window.prompt('请输入作废原因（至少5字）') || ''
      if (reason.trim().length < 5) return
      this.run(complianceApi.revokeConsent(row.id, { expectedVersion: row.version, reason }), '知情任务已作废')
    },
    createSafetyCourse() {
      const form = this.forms.safety
      if (!form.title || !form.courseVersion || !form.contentSnapshot) return this.$message?.warning?.('课程名称、版本和正文必填')
      this.run(complianceApi.createSafetyCourse({ ...form, batchId: this.batchStore.selectedBatchId, status: 'ACTIVE' }), '安全课程已创建')
    },
    reviewSafety(row, action) {
      const score = action === 'APPROVE' ? Number(window.prompt('请输入审核分数（0-100）', '100')) : null
      if (action === 'APPROVE' && (!Number.isFinite(score) || score < 0 || score > 100)) return
      const comment = window.prompt(action === 'APPROVE' ? '审核备注（可选）' : '退回原因', '') || ''
      this.run(complianceApi.reviewSafetyCompletion(row.id, { action, score, comment, expectedVersion: row.version }), '安全教育审核完成')
    },
    async createFiling() {
      const form = this.forms.filing
      if (!form.internshipId || form.triggerReason.trim().length < 5 || form.riskDescription.trim().length < 5 || !form.fileIds.length) return this.$message?.warning?.('学生、原因、风险说明和附件均必填')
      const created = await complianceApi.createFiling(form)
      if (created.code !== 0) return this.$message?.error?.(created.message)
      await this.run(complianceApi.reviewFiling(created.data.id, 'COLLEGE', 'submit', { expectedVersion: created.data.version }), '特殊备案已提交学院审核')
    },
    filingAction(row, level, action) {
      const comment = action === 'submit' ? '' : (window.prompt(action === 'approve' ? '审核意见（可选）' : '退回原因（至少5字）', '') || '')
      if (action === 'reject' && comment.trim().length < 5) return
      this.run(complianceApi.reviewFiling(row.id, level, action, { expectedVersion: row.version, comment }), '备案状态已更新')
    },
    reportIncident() {
      const form = this.forms.incident
      if (!form.internshipId || !form.occurredAt || form.summary.trim().length < 5) return this.$message?.warning?.('学生、发生时间和情况摘要必填')
      this.run(complianceApi.reportIncident({ ...form, idempotencyKey: `pc-${Date.now()}-${Math.random().toString(36).slice(2)}` }), '事故已上报')
    },
    incidentTargets(status) {
      return ({ REPORTED: ['EMERGENCY_HANDLING', 'INVESTIGATING'], EMERGENCY_HANDLING: ['INVESTIGATING'], INVESTIGATING: ['RECTIFYING', 'PENDING_REVIEW'], RECTIFYING: ['PENDING_REVIEW'], PENDING_REVIEW: ['CLOSED'] })[status] || []
    },
    async transitionIncident(row, target) {
      const body = { status: target, expectedVersion: row.version }
      if (['PENDING_REVIEW', 'CLOSED'].includes(target)) {
        body.investigationConclusion = window.prompt('调查结论', row.investigationConclusion || '') || ''
        body.rectificationPlan = window.prompt('整改方案', row.rectificationPlan || '') || ''
        body.responsibilityConclusion = window.prompt('责任/复核结论', row.responsibilityConclusion || '') || ''
      }
      if (target === 'CLOSED') {
        this.$message?.warning?.('关闭事故必须已有附件；如缺少，请先在事故详情补充材料')
      }
      await this.run(complianceApi.transitionIncident(row.id, body), `事故已流转至 ${target}`)
    },
    async createEmergency() {
      const form = this.forms.emergency
      if (!form.planName || !form.responsiblePerson || !form.emergencyContact || !form.responseSteps || !form.fileIds.length) return this.$message?.warning?.('预案名称、责任人、联系电话、处置步骤和附件必填')
      const created = await complianceApi.createEmergencyPlan({ ...form, batchId: this.batchStore.selectedBatchId })
      if (created.code !== 0) return this.$message?.error?.(created.message)
      await this.run(complianceApi.reviewEmergencyPlan(created.data.id, 'SUBMIT', { expectedVersion: created.data.version }), '应急预案已提交审核')
    },
    emergencyAction(row, action) {
      const comment = action === 'REJECT' ? (window.prompt('驳回原因（至少5字）') || '') : ''
      if (action === 'REJECT' && comment.trim().length < 5) return
      this.run(complianceApi.reviewEmergencyPlan(row.id, action, { expectedVersion: row.version, comment }), '应急预案状态已更新')
    },
    requestExemption() {
      const form = this.forms.exemption
      if (!form.internshipId || !form.checkCode || form.reason.trim().length < 10 || !form.validUntil || !form.evidenceFileIds.length) return this.$message?.warning?.('学生、检查项、10字以上原因、有效期和依据附件均必填')
      this.run(complianceApi.grantExemption(form), '豁免申请已提交学校审批')
    },
    reviewExemption(row, action) {
      const comment = window.prompt(action === 'APPROVE' ? '批准意见（可选）' : '拒绝原因', '') || ''
      this.run(complianceApi.reviewExemption(row.id, { action, comment, expectedVersion: row.version }), '豁免审批完成')
    },
    generatePackage() {
      const form = this.forms.package
      const targetId = form.packageType === 'BATCH' ? this.batchStore.selectedBatchId : form.targetId
      if (!targetId) return this.$message?.warning?.('请选择证据包目标')
      this.run(complianceApi.generateEvidencePackage(form.packageType, targetId), '证据包已生成')
    },
    async downloadPackage(row) {
      try { await complianceApi.downloadEvidencePackage(row.id, `岗位实习_${row.packageType}_v${row.packageVersion}.zip`) }
      catch (error) { this.$message?.error?.(error.message || '下载失败') }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.workbench-head,.head-actions,.mp-card__head{display:flex;align-items:center;justify-content:space-between;gap:16px}.workbench-head p{margin:5px 0 0}.status-pill,.tab-count{display:inline-flex;align-items:center;justify-content:center;border-radius:999px;background:var(--color-primary-light,#eef4ff);color:var(--color-primary);padding:3px 9px;font-size:12px}.work-tabs{display:flex;gap:8px;overflow-x:auto;padding:2px}.work-tab{border:1px solid var(--border-color);background:#fff;border-radius:8px;padding:9px 13px;cursor:pointer;white-space:nowrap}.work-tab.is-active{border-color:var(--color-primary);color:var(--color-primary);background:var(--color-primary-light,#eef4ff)}.tab-count{margin-left:5px;padding:1px 6px}.metric-card{text-align:left;cursor:pointer}.metric-card.is-active{outline:2px solid var(--color-primary)}.action-panel{border-left:4px solid var(--color-primary)}.form-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:14px 0}.form-grid label{display:flex;flex-direction:column;gap:6px;font-size:13px;color:var(--text-secondary)}.form-grid input,.form-grid select,.form-grid textarea{box-sizing:border-box;width:100%;border:1px solid var(--border-color);border-radius:7px;padding:9px 10px;background:#fff;color:var(--text-primary)}.form-grid .span-2{grid-column:span 2}.checkbox-label{flex-direction:row!important;align-items:center}.checkbox-label input{width:auto}.file-note{align-self:end;padding-bottom:10px;color:var(--text-tertiary);font-size:12px}.table-wrap{overflow-x:auto}.mp-table{width:100%;border-collapse:collapse;min-width:900px}.mp-table th,.mp-table td{padding:10px;border-bottom:1px solid var(--border-color);text-align:left;vertical-align:top;font-size:13px}.mp-link,.danger-link{border:0;background:transparent;cursor:pointer;padding:3px 6px;color:var(--color-primary)}.danger-link{color:var(--color-danger,#d93025)}.empty-cell{text-align:center!important;color:var(--text-tertiary)}.hash-cell{max-width:190px;word-break:break-all;font-family:monospace;font-size:11px}@media(max-width:1100px){.form-grid{grid-template-columns:1fr 1fr}}@media(max-width:760px){.form-grid{grid-template-columns:1fr}.form-grid .span-2{grid-column:span 1}}
</style>
