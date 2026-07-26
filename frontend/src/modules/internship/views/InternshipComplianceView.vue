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
            <p class="mp-note">规则 {{ stats.ruleVersion || '-' }} · 数据生成于 {{ fmt(workbench.generatedAt || stats.evaluatedAt) }}</p>
          </div>
          <div class="head-actions">
            <span class="status-pill">{{ workbench.batch?.status || '-' }}</span>
            <AppButton variant="ghost" size="sm" :disabled="loading || acting" @click="load">刷新</AppButton>
          </div>
        </div>

        <nav class="work-tabs" aria-label="合规办理工作区">
          <button
            v-for="tabItem in tabs"
            :key="tabItem.key"
            type="button"
            class="work-tab"
            :class="{ 'is-active': activeTab === tabItem.key }"
            @click="activeTab = tabItem.key"
          >
            {{ tabItem.label }}
            <span v-if="tabItem.count != null" class="tab-count">{{ tabItem.count }}</span>
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
                    <td>{{ blockerText(row.blockers) }}</td><td>{{ blockerText(row.archiveBlockers) }}</td>
                    <td><button type="button" class="mp-link" @click="openStudent(row)">学生详情</button></td>
                  </tr>
                  <tr v-if="!drilldownRows.length"><td colspan="7" class="empty-cell">当前口径下暂无学生</td></tr>
                </tbody>
              </table>
            </div>
          </section>
        </template>

        <template v-else-if="activeTab === 'consents'">
          <section v-if="can('internship.consent.manage')" class="mp-card action-panel">
            <div class="mp-card__head">
              <div><strong>下发知情确认任务</strong><p class="mp-note">教师只能下发、催办、作废，不能代学生或监护人确认。</p></div>
            </div>
            <div class="form-grid">
              <label>学生
                <select v-model="forms.consent.internshipId">
                  <option value="">请选择学生</option>
                  <option v-for="student in students" :key="student.internshipId" :value="student.internshipId">{{ student.studentNo }} · {{ student.studentName }}</option>
                </select>
              </label>
              <label>确认人
                <select v-model="forms.consent.consentType">
                  <option value="STUDENT">学生本人</option>
                  <option value="GUARDIAN">已绑定监护人</option>
                </select>
              </label>
              <label>正文版本
                <input v-model.trim="forms.consent.contentVersion" maxlength="64" placeholder="例如 2026-秋-v1" />
              </label>
              <label class="span-3">知情正文
                <textarea v-model.trim="forms.consent.contentSnapshot" rows="7" maxlength="20000" placeholder="粘贴本次下发的完整正文快照；正文变化必须升级版本" />
                <span class="field-help">{{ forms.consent.contentSnapshot.length }}/20000</span>
              </label>
            </div>
            <AppButton :disabled="acting || !consentFormValid" @click="createConsent">创建并下发</AppButton>
          </section>

          <section class="mp-card">
            <div class="mp-card__head"><strong>知情确认台账</strong><span class="mp-note">{{ workbench.consents?.length || 0 }} 条</span></div>
            <div class="table-wrap">
              <table class="mp-table consent-table">
                <thead><tr><th>学生/确认人</th><th>正文</th><th>任务状态</th><th>短信送达</th><th>阅读/确认</th><th>链接有效期</th><th>版本</th><th>操作</th></tr></thead>
                <tbody>
                  <tr v-for="row in workbench.consents || []" :key="row.id">
                    <td>
                      <strong>{{ row.studentNo }} · {{ row.studentName }}</strong>
                      <div class="cell-sub">{{ row.consentType === 'GUARDIAN' ? `${row.participantName || '监护人'} · ${row.contactMasked || '手机号未显示'}` : '学生本人' }}</div>
                    </td>
                    <td>{{ row.contentVersion || '-' }}</td>
                    <td><span :class="['state-tag', stateTone(row.status)]">{{ consentStatusText(row.status) }}</span></td>
                    <td>
                      <span v-if="row.consentType === 'STUDENT'" class="cell-sub">站内任务</span>
                      <template v-else>
                        <span :class="['state-tag', deliveryTone(row.deliveryStatus)]">{{ deliveryStatusText(row.deliveryStatus) }}</span>
                        <div v-if="row.deliveryReason" class="cell-error" :title="row.deliveryReason">{{ row.deliveryReason }}</div>
                        <div v-if="row.deliveredAt" class="cell-sub">{{ fmt(row.deliveredAt) }}</div>
                      </template>
                    </td>
                    <td><div>{{ row.viewedAt ? `已读 ${fmt(row.viewedAt)}` : '未读' }}</div><div class="cell-sub">{{ row.confirmedAt ? `确认 ${fmt(row.confirmedAt)}` : '未确认' }}</div></td>
                    <td>{{ row.consentType === 'GUARDIAN' ? fmt(row.guardianTokenExpiresAt) : '-' }}</td>
                    <td>{{ row.version }}</td>
                    <td class="action-cell">
                      <button
                        v-if="row.consentType === 'GUARDIAN' && row.status === 'PENDING' && can('internship.consent.manage')"
                        type="button" class="mp-link" :disabled="acting" @click="redeliverConsent(row)"
                      >重新发送</button>
                      <button
                        v-if="['PENDING','VALID'].includes(row.status) && can('internship.consent.manage')"
                        type="button" class="danger-link" :disabled="acting" @click="openAction('revoke-consent', row)"
                      >作废</button>
                    </td>
                  </tr>
                  <tr v-if="!(workbench.consents || []).length"><td colspan="8" class="empty-cell">暂无知情任务</td></tr>
                </tbody>
              </table>
            </div>
          </section>
        </template>

        <template v-else-if="activeTab === 'safety'">
          <section v-if="can('internship.safety.manage')" class="mp-card action-panel">
            <div class="mp-card__head"><div><strong>配置安全教育课程</strong><p class="mp-note">课程升级后旧版本完成记录不能满足新版本。</p></div></div>
            <div class="form-grid">
              <label>课程名称<input v-model.trim="forms.safety.title" maxlength="200" placeholder="例如 岗前安全教育必修课" /></label>
              <label>课程版本<input v-model.trim="forms.safety.courseVersion" maxlength="40" placeholder="例如 2026-v1" /></label>
              <label>要求分钟<input v-model.number="forms.safety.requiredMinutes" type="number" min="1" max="1440" /></label>
              <label>及格分<input v-model.number="forms.safety.passingScore" type="number" min="1" max="100" /></label>
              <label>最大尝试次数<input v-model.number="forms.safety.maxAttempts" type="number" min="1" max="20" /></label>
              <label class="checkbox-label"><input v-model="forms.safety.requireCommitment" type="checkbox" />要求学生安全承诺</label>
              <label class="span-3">课程正文<textarea v-model.trim="forms.safety.contentSnapshot" rows="7" maxlength="30000" placeholder="完整课程正文、注意事项和考核要求" /></label>
            </div>
            <AppButton :disabled="acting || !safetyFormValid" @click="createSafetyCourse">保存有效课程</AppButton>
          </section>
          <section class="mp-card">
            <div class="mp-card__head"><strong>课程配置</strong><span class="mp-note">{{ workbench.safetyCourses?.length || 0 }} 门</span></div>
            <div class="table-wrap"><table class="mp-table"><thead><tr><th>课程</th><th>版本</th><th>状态</th><th>时长</th><th>及格线</th><th>最大次数</th><th>承诺</th></tr></thead><tbody>
              <tr v-for="row in workbench.safetyCourses || []" :key="row.id"><td>{{ row.title }}</td><td>{{ row.courseVersion }}</td><td>{{ row.status }}</td><td>{{ row.requiredMinutes }}分钟</td><td>{{ row.passingScore }}</td><td>{{ row.maxAttempts }}</td><td>{{ row.requireCommitment ? '必需' : '否' }}</td></tr>
              <tr v-if="!(workbench.safetyCourses || []).length"><td colspan="7" class="empty-cell">当前批次未配置课程；启用安全门禁时将被判为配置错误</td></tr>
            </tbody></table></div>
          </section>
          <section class="mp-card">
            <div class="mp-card__head"><strong>学生学习与审核</strong></div>
            <div class="table-wrap"><table class="mp-table"><thead><tr><th>学生</th><th>课程</th><th>记录/当前版本</th><th>状态</th><th>时长</th><th>分数</th><th>尝试</th><th>版本</th><th>审核</th></tr></thead><tbody>
              <tr v-for="row in workbench.safetyCompletions || []" :key="row.id">
                <td>{{ row.studentNo }} · {{ row.studentName }}</td><td>{{ row.courseTitle }}</td><td>{{ row.courseVersion }} / {{ row.currentCourseVersion }}</td><td>{{ row.status }}</td><td>{{ row.studiedMinutes }}分钟</td><td>{{ row.score ?? '-' }}</td><td>{{ row.attemptCount }}</td><td>{{ row.version }}</td>
                <td class="action-cell"><template v-if="row.status === 'PENDING_REVIEW' && can('internship.safety.manage')"><button type="button" class="mp-link" @click="openAction('safety-review', row, 'APPROVE')">通过</button><button type="button" class="danger-link" @click="openAction('safety-review', row, 'REJECT')">退回</button></template></td>
              </tr><tr v-if="!(workbench.safetyCompletions || []).length"><td colspan="9" class="empty-cell">暂无学生学习记录</td></tr>
            </tbody></table></div>
          </section>
        </template>

        <template v-else-if="activeTab === 'filings'">
          <section v-if="can('internship.filing.review')" class="mp-card action-panel">
            <div class="mp-card__head"><div><strong>新建特殊备案</strong><p class="mp-note">经办人创建并提交，申请人与审核人必须分离。</p></div></div>
            <div class="form-grid">
              <label>学生<select v-model="forms.filing.internshipId"><option value="">请选择学生</option><option v-for="student in students" :key="student.internshipId" :value="student.internshipId">{{ student.studentNo }} · {{ student.studentName }}</option></select></label>
              <label>备案类型<select v-model="forms.filing.filingType"><option v-for="item in filingTypes" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
              <label>目的地区<input v-model.trim="forms.filing.destinationRegion" maxlength="200" placeholder="跨区域/境外时填写" /></label>
              <label class="span-3">触发原因<textarea v-model.trim="forms.filing.triggerReason" rows="3" maxlength="500" placeholder="不少于5字" /></label>
              <label class="span-3">风险说明<textarea v-model.trim="forms.filing.riskDescription" rows="3" maxlength="2000" placeholder="高风险、夜班、境外、未成年类型必填" /></label>
              <label>依据附件<input type="file" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png" @change="uploadToForm($event, 'filing', 'fileIds', 'INTERNSHIP_FILING')" /></label>
              <span class="file-note">{{ fileText(forms.filing.fileIds) }}</span>
            </div>
            <AppButton :disabled="acting || !filingFormValid" @click="createFiling">创建并提交学院审核</AppButton>
          </section>
          <section class="mp-card"><div class="mp-card__head"><strong>特殊备案台账</strong></div><div class="table-wrap"><table class="mp-table"><thead><tr><th>学生</th><th>类型</th><th>状态</th><th>原因</th><th>学院/学校意见</th><th>附件</th><th>版本</th><th>操作</th></tr></thead><tbody>
            <tr v-for="row in workbench.filings || []" :key="row.id"><td>{{ row.studentNo }} · {{ row.studentName }}</td><td>{{ filingTypeText(row.filingType) }}</td><td>{{ row.status }}</td><td>{{ row.triggerReason }}</td><td>{{ row.collegeComment || '-' }} / {{ row.schoolComment || '-' }}</td><td>{{ row.fileIds?.length || 0 }}</td><td>{{ row.version }}</td><td class="action-cell">
              <button v-if="row.status === 'DRAFT' && can('internship.filing.review')" type="button" class="mp-link" @click="filingAction(row, 'COLLEGE', 'submit')">提交</button>
              <template v-if="row.status === 'PENDING_COLLEGE' && can('internship.filing.review')"><button type="button" class="mp-link" @click="openAction('filing-review', row, 'APPROVE', 'COLLEGE')">学院通过</button><button type="button" class="danger-link" @click="openAction('filing-review', row, 'REJECT', 'COLLEGE')">学院退回</button></template>
              <template v-if="row.status === 'PENDING_SCHOOL' && can('internship.filing.review')"><button type="button" class="mp-link" @click="openAction('filing-review', row, 'APPROVE', 'SCHOOL')">学校通过</button><button type="button" class="danger-link" @click="openAction('filing-review', row, 'REJECT', 'SCHOOL')">学校退回</button></template>
            </td></tr><tr v-if="!(workbench.filings || []).length"><td colspan="8" class="empty-cell">暂无特殊备案</td></tr>
          </tbody></table></div></section>
        </template>

        <template v-else-if="activeTab === 'incidents'">
          <section v-if="can('internship.incident.report')" class="mp-card action-panel">
            <div class="mp-card__head"><div><strong>上报事故</strong><p class="mp-note">HIGH/CRITICAL 自动联动高风险单；事故编号由服务端生成。</p></div></div>
            <div class="form-grid">
              <label>学生<select v-model="forms.incident.internshipId"><option value="">请选择学生</option><option v-for="student in students" :key="student.internshipId" :value="student.internshipId">{{ student.studentNo }} · {{ student.studentName }}</option></select></label>
              <label>严重程度<select v-model="forms.incident.severity"><option value="LOW">一般</option><option value="MEDIUM">较大</option><option value="HIGH">重大</option><option value="CRITICAL">特别重大</option></select></label>
              <label>事故类型<input v-model.trim="forms.incident.incidentType" maxlength="50" placeholder="例如 人身伤害/交通/设备" /></label>
              <label>发生时间<input v-model="forms.incident.occurredAt" type="datetime-local" :max="nowLocal" /></label>
              <label class="span-2">地点<input v-model.trim="forms.incident.location" maxlength="300" placeholder="具体到企业、车间或道路" /></label>
              <label class="span-3">情况摘要<textarea v-model.trim="forms.incident.summary" rows="3" maxlength="2000" placeholder="不少于5字，说明人员、时间、经过和当前状态" /></label>
              <label class="span-3">已采取应急措施<textarea v-model.trim="forms.incident.emergencyAction" rows="3" maxlength="2000" placeholder="说明送医、报警、停工、家校联系等措施" /></label>
              <label>现场材料<input type="file" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.mp4" @change="uploadToForm($event, 'incident', 'fileIds', 'INTERNSHIP_INCIDENT')" /></label>
              <span class="file-note">{{ fileText(forms.incident.fileIds) }}</span>
            </div>
            <AppButton :disabled="acting || !incidentFormValid" @click="reportIncident">提交事故报告</AppButton>
          </section>
          <section class="mp-card"><div class="mp-card__head"><strong>事故处置台账</strong></div><div class="table-wrap"><table class="mp-table"><thead><tr><th>编号</th><th>学生</th><th>等级</th><th>状态</th><th>摘要</th><th>附件</th><th>版本</th><th>合法下一步</th></tr></thead><tbody>
            <tr v-for="row in workbench.incidents || []" :key="row.id"><td>{{ row.incidentNo }}</td><td>{{ row.studentNo }} · {{ row.studentName }}</td><td>{{ row.severity }}</td><td>{{ row.status }}</td><td>{{ row.summary }}</td><td>{{ row.fileIds?.length || 0 }}</td><td>{{ row.version }}</td><td class="action-cell"><button v-for="target in incidentTargets(row)" :key="target" type="button" class="mp-link" @click="openAction('incident-transition', row, target)">{{ incidentTargetText(target) }}</button></td></tr>
            <tr v-if="!(workbench.incidents || []).length"><td colspan="8" class="empty-cell">暂无事故记录</td></tr>
          </tbody></table></div></section>

          <section v-if="can('internship.incident.handle')" class="mp-card action-panel">
            <div class="mp-card__head"><strong>新建批次应急预案</strong></div>
            <div class="form-grid">
              <label>预案名称<input v-model.trim="forms.emergency.planName" maxlength="200" /></label>
              <label>责任人<input v-model.trim="forms.emergency.responsiblePerson" maxlength="100" /></label>
              <label>应急电话<input v-model.trim="forms.emergency.emergencyContact" type="tel" maxlength="30" placeholder="手机号或座机" /></label>
              <label>备用电话<input v-model.trim="forms.emergency.backupContact" type="tel" maxlength="30" /></label>
              <label class="span-2">医院/支援单位<input v-model.trim="forms.emergency.hospitalOrSupport" maxlength="300" /></label>
              <label class="span-3">处置步骤<textarea v-model.trim="forms.emergency.responseSteps" rows="5" maxlength="5000" placeholder="不少于10字，明确报告、救援、转运、家校沟通和复盘步骤" /></label>
              <label>预案附件<input type="file" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png" @change="uploadToForm($event, 'emergency', 'fileIds', 'INTERNSHIP_EMERGENCY')" /></label><span class="file-note">{{ fileText(forms.emergency.fileIds) }}</span>
            </div>
            <AppButton :disabled="acting || !emergencyFormValid" @click="createEmergency">创建并提交审核</AppButton>
          </section>
          <section class="mp-card"><div class="mp-card__head"><strong>应急预案</strong></div><div class="table-wrap"><table class="mp-table"><thead><tr><th>名称</th><th>责任人</th><th>联系电话</th><th>状态</th><th>附件</th><th>版本</th><th>操作</th></tr></thead><tbody>
            <tr v-for="row in workbench.emergencyPlans || []" :key="row.id"><td>{{ row.planName }}</td><td>{{ row.responsiblePerson }}</td><td>{{ row.emergencyContact }}</td><td>{{ row.status }}</td><td>{{ row.fileIds?.length || 0 }}</td><td>{{ row.version }}</td><td class="action-cell"><button v-if="row.status === 'DRAFT' && can('internship.incident.handle')" type="button" class="mp-link" @click="emergencyAction(row, 'SUBMIT')">提交审核</button><template v-if="row.status === 'PENDING_REVIEW' && can('internship.incident.handle')"><button type="button" class="mp-link" @click="openAction('emergency-review', row, 'APPROVE')">通过</button><button type="button" class="danger-link" @click="openAction('emergency-review', row, 'REJECT')">退回</button></template></td></tr>
            <tr v-if="!(workbench.emergencyPlans || []).length"><td colspan="7" class="empty-cell">暂无应急预案</td></tr>
          </tbody></table></div></section>
        </template>

        <template v-else-if="activeTab === 'exemptions'">
          <section v-if="can('internship.compliance.exempt.request')" class="mp-card action-panel">
            <div class="mp-card__head"><div><strong>申请合规豁免</strong><p class="mp-note">只允许有期限、有依据的个案申请；不能豁免基础身份、租户隔离或数据权限。</p></div></div>
            <div class="form-grid">
              <label>学生<select v-model="forms.exemption.internshipId"><option value="">请选择学生</option><option v-for="student in students" :key="student.internshipId" :value="student.internshipId">{{ student.studentNo }} · {{ student.studentName }}</option></select></label>
              <label>检查项<select v-model="forms.exemption.checkCode"><option value="">请选择检查项</option><option v-for="item in exemptionChecks" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
              <label>有效期至<input v-model="forms.exemption.validUntil" type="datetime-local" :min="nowLocal" /></label>
              <label class="span-3">申请原因<textarea v-model.trim="forms.exemption.reason" rows="4" maxlength="1000" placeholder="不少于10字，说明特殊事实、替代控制和责任人" /></label>
              <label>依据附件<input type="file" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png" @change="uploadToForm($event, 'exemption', 'evidenceFileIds', 'COMPLIANCE_EVIDENCE')" /></label><span class="file-note">{{ fileText(forms.exemption.evidenceFileIds) }}</span>
            </div>
            <AppButton :disabled="acting || !exemptionFormValid" @click="requestExemption">提交豁免申请</AppButton>
          </section>
          <section class="mp-card"><div class="mp-card__head"><strong>豁免台账</strong></div><div class="table-wrap"><table class="mp-table"><thead><tr><th>学生</th><th>检查项</th><th>原因</th><th>有效期</th><th>状态</th><th>申请/审批人</th><th>版本</th><th>操作</th></tr></thead><tbody>
            <tr v-for="row in workbench.exemptions || []" :key="row.id"><td>{{ row.studentNo }} · {{ row.studentName }}</td><td>{{ exemptionCheckText(row.checkCode) }}</td><td>{{ row.reason }}</td><td>{{ fmt(row.validUntil) }}</td><td>{{ row.status }}</td><td>{{ row.requestedByName || '-' }} / {{ row.reviewedByName || '-' }}</td><td>{{ row.version }}</td><td class="action-cell"><template v-if="row.status === 'PENDING_REVIEW' && can('internship.compliance.exempt.approve')"><button type="button" class="mp-link" @click="openAction('exemption-review', row, 'APPROVE')">批准</button><button type="button" class="danger-link" @click="openAction('exemption-review', row, 'REJECT')">拒绝</button></template></td></tr>
            <tr v-if="!(workbench.exemptions || []).length"><td colspan="8" class="empty-cell">暂无豁免记录</td></tr>
          </tbody></table></div></section>
        </template>

        <template v-else-if="activeTab === 'evidence'">
          <section class="mp-card action-panel">
            <div class="mp-card__head"><div><strong>生成监管证据包</strong><p class="mp-note">包含真实附件、对象版本、逐文件SHA-256、缺失项和审计。</p></div></div>
            <div class="form-grid">
              <label>包类型<select v-model="forms.package.packageType"><option value="BATCH">批次包</option><option value="STUDENT">学生包</option></select></label>
              <label v-if="forms.package.packageType === 'STUDENT'">学生<select v-model="forms.package.targetId"><option value="">请选择学生</option><option v-for="student in students" :key="student.internshipId" :value="student.internshipId">{{ student.studentNo }} · {{ student.studentName }}</option></select></label>
            </div>
            <AppButton v-if="can('internship.evidence.export')" :disabled="acting || !packageFormValid" @click="generatePackage">生成版本化证据包</AppButton>
          </section>
          <section class="mp-card"><div class="mp-card__head"><strong>证据包历史</strong></div><div class="table-wrap"><table class="mp-table"><thead><tr><th>类型</th><th>目标</th><th>版本</th><th>状态</th><th>文件/缺失</th><th>SHA-256</th><th>生成人</th><th>时间</th><th>下载</th></tr></thead><tbody>
            <tr v-for="row in workbench.evidencePackages || []" :key="row.id"><td>{{ row.packageType }}</td><td>{{ row.targetId }}</td><td>v{{ row.packageVersion }}</td><td>{{ row.status }}</td><td>{{ row.fileCount }} / {{ row.missingCount }}</td><td class="hash-cell">{{ row.packageSha256 || '-' }}</td><td>{{ row.generatedByName }}</td><td>{{ fmt(row.generatedAt) }}</td><td><button v-if="['READY','READY_WITH_MISSING'].includes(row.status) && can('internship.evidence.export')" type="button" class="mp-link" @click="downloadPackage(row)">下载ZIP</button></td></tr>
            <tr v-if="!(workbench.evidencePackages || []).length"><td colspan="9" class="empty-cell">暂无证据包</td></tr>
          </tbody></table></div></section>
        </template>
      </template>
    </div>

    <div v-if="dialog.open" class="dialog-mask" @click.self="closeDialog">
      <section class="action-dialog" role="dialog" aria-modal="true" :aria-label="dialog.title">
        <div class="dialog-head"><strong>{{ dialog.title }}</strong><button type="button" class="dialog-close" @click="closeDialog">×</button></div>
        <p v-if="dialog.description" class="mp-note">{{ dialog.description }}</p>
        <label v-if="dialog.showScore">审核分数（0-100）<input v-model.number="dialog.score" type="number" min="0" max="100" /></label>
        <label v-if="dialog.showInvestigation">调查结论<textarea v-model.trim="dialog.investigationConclusion" rows="3" maxlength="2000" /></label>
        <label v-if="dialog.showInvestigation">整改方案<textarea v-model.trim="dialog.rectificationPlan" rows="3" maxlength="2000" /></label>
        <label v-if="dialog.showInvestigation">责任/复核结论<textarea v-model.trim="dialog.responsibilityConclusion" rows="3" maxlength="2000" /></label>
        <label>{{ dialog.commentLabel }}<textarea v-model.trim="dialog.comment" rows="4" maxlength="1000" :placeholder="dialog.commentPlaceholder" /></label>
        <div v-if="dialogError" class="dialog-error">{{ dialogError }}</div>
        <div class="dialog-actions"><AppButton variant="ghost" :disabled="acting" @click="closeDialog">取消</AppButton><AppButton :disabled="acting" @click="confirmDialog">{{ acting ? '处理中…' : dialog.confirmText }}</AppButton></div>
      </section>
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

const FILING_TYPES = [
  { value: 'CROSS_PROVINCE', label: '跨省实习' }, { value: 'CROSS_CITY', label: '跨市实习' },
  { value: 'OVERSEAS', label: '境外实习' }, { value: 'HIGH_RISK', label: '高风险岗位' },
  { value: 'NIGHT_SHIFT', label: '夜班岗位' }, { value: 'SPECIAL_TRADE', label: '特殊工种' },
  { value: 'MINOR', label: '未成年学生' }, { value: 'REMOTE', label: '远程实习' },
  { value: 'OTHER', label: '其他特殊情形' }
]
const EXEMPTION_CHECKS = [
  { value: 'enterpriseAccess', label: '企业准入' }, { value: 'studentConsent', label: '学生知情确认' },
  { value: 'guardianConsent', label: '监护人知情确认' }, { value: 'safetyEducation', label: '安全教育' },
  { value: 'insurance', label: '实习保险' }, { value: 'agreement', label: '三方协议' },
  { value: 'specialFiling', label: '特殊备案' }, { value: 'positionRights', label: '岗位权益' },
  { value: 'emergencyPlan', label: '应急预案' }
]

function freshForms() {
  return {
    consent: { internshipId: '', consentType: 'STUDENT', contentVersion: '', contentSnapshot: '' },
    safety: { title: '', courseVersion: '', requiredMinutes: 60, passingScore: 80, maxAttempts: 3, requireCommitment: true, contentSnapshot: '' },
    filing: { internshipId: '', filingType: 'OTHER', destinationRegion: '', triggerReason: '', riskDescription: '', fileIds: [] },
    incident: { internshipId: '', severity: 'MEDIUM', incidentType: '', occurredAt: '', location: '', summary: '', emergencyAction: '', fileIds: [] },
    emergency: { planName: '', responsiblePerson: '', emergencyContact: '', backupContact: '', hospitalOrSupport: '', responseSteps: '', fileIds: [] },
    exemption: { internshipId: '', checkCode: '', reason: '', validUntil: '', evidenceFileIds: [] },
    package: { packageType: 'BATCH', targetId: '' }
  }
}

function emptyDialog() {
  return {
    open: false, kind: '', row: null, action: '', level: '', title: '', description: '',
    comment: '', commentLabel: '办理意见', commentPlaceholder: '', confirmText: '确认办理',
    showScore: false, score: 100, showInvestigation: false,
    investigationConclusion: '', rectificationPlan: '', responsibilityConclusion: ''
  }
}

export default {
  name: 'InternshipComplianceView',
  components: { ModulePageShell, LoadingState, ErrorState, AppButton, AppInlineAlert },
  props: { ctx: { type: Object, required: true } },
  data: () => ({
    loading: false, acting: false, error: '', activeTab: 'overview',
    stats: {}, workbench: {}, auditHealth: null, selectedFilter: 'ALL', forms: freshForms(),
    filingTypes: FILING_TYPES, exemptionChecks: EXEMPTION_CHECKS,
    dialog: emptyDialog(), dialogError: ''
  }),
  computed: {
    batchStore() { return useInternshipBatchStore() },
    metrics() { return this.stats.metrics || [] },
    students() { return this.stats.drilldowns?.ALL || [] },
    selectedMetric() { return this.metrics.find((item) => item.drilldownFilter === this.selectedFilter) },
    drilldownRows() { return this.stats.drilldowns?.[this.selectedFilter] || [] },
    nowLocal() {
      const date = new Date(Date.now() - new Date().getTimezoneOffset() * 60000)
      return date.toISOString().slice(0, 16)
    },
    consentFormValid() {
      const form = this.forms.consent
      return !!form.internshipId && form.contentVersion.trim().length >= 2 && form.contentSnapshot.trim().length >= 20
    },
    safetyFormValid() {
      const form = this.forms.safety
      return form.title.trim().length >= 2 && form.courseVersion.trim().length >= 1 && form.contentSnapshot.trim().length >= 20 && Number(form.requiredMinutes) >= 1 && Number(form.requiredMinutes) <= 1440 && Number(form.passingScore) >= 1 && Number(form.passingScore) <= 100 && Number(form.maxAttempts) >= 1 && Number(form.maxAttempts) <= 20
    },
    filingFormValid() {
      const form = this.forms.filing
      const riskRequired = ['HIGH_RISK', 'NIGHT_SHIFT', 'OVERSEAS', 'MINOR'].includes(form.filingType)
      return !!form.internshipId && form.triggerReason.trim().length >= 5 && (!riskRequired || form.riskDescription.trim().length >= 5) && form.fileIds.length > 0
    },
    incidentFormValid() {
      const form = this.forms.incident
      return !!form.internshipId && !!form.occurredAt && form.occurredAt <= this.nowLocal && form.incidentType.trim().length >= 2 && form.location.trim().length >= 2 && form.summary.trim().length >= 5 && form.emergencyAction.trim().length >= 5
    },
    emergencyFormValid() {
      const form = this.forms.emergency
      return form.planName.trim().length >= 2 && form.responsiblePerson.trim().length >= 2 && /^[0-9+\-()\s]{7,30}$/.test(form.emergencyContact) && form.responseSteps.trim().length >= 10 && form.fileIds.length > 0
    },
    exemptionFormValid() {
      const form = this.forms.exemption
      return !!form.internshipId && !!form.checkCode && form.reason.trim().length >= 10 && !!form.validUntil && form.validUntil > this.nowLocal && form.evidenceFileIds.length > 0
    },
    packageFormValid() { return this.forms.package.packageType === 'BATCH' || !!this.forms.package.targetId },
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
      return patterns.includes('*') || patterns.some((pattern) => pattern === permission || (pattern.endsWith('.*') && permission.startsWith(pattern.slice(0, -1))))
    },
    fmt(value) { return value ? String(value).replace('T', ' ').replace('Z', '').slice(0, 16) : '-' },
    fileText(ids) { return ids?.length ? `已上传 ${ids.length} 个文件` : '尚未上传' },
    blockerText(items) { return items?.length ? items.map((item) => `${item.label}：${item.reason}`).join('；') : '无' },
    filingTypeText(value) { return FILING_TYPES.find((item) => item.value === value)?.label || value || '-' },
    exemptionCheckText(value) { return EXEMPTION_CHECKS.find((item) => item.value === value)?.label || value || '-' },
    consentStatusText(value) { return ({ PENDING: '待确认', VALID: '已确认', REJECTED: '已拒绝', EXPIRED: '已过期', SUPERSEDED: '已被新版本替代', REVOKED: '已作废', NOT_APPLICABLE: '无需确认' })[value] || value || '-' },
    deliveryStatusText(value) { return ({ SENT: '已发送', SKIPPED: '未发送', FAILED: '发送失败', NOT_SENT: '尚未发送', NOT_REQUIRED: '无需发送' })[String(value || '').toUpperCase()] || value || '尚未发送' },
    deliveryTone(value) { const status = String(value || '').toUpperCase(); return status === 'SENT' ? 'is-success' : ['SKIPPED', 'FAILED'].includes(status) ? 'is-danger' : 'is-muted' },
    stateTone(value) { return value === 'VALID' || value === 'APPROVED' ? 'is-success' : ['REJECTED', 'REVOKED', 'EXPIRED'].includes(value) ? 'is-danger' : value === 'PENDING' ? 'is-warn' : 'is-muted' },
    incidentTargetText(value) { return ({ EMERGENCY_HANDLING: '进入应急处置', INVESTIGATING: '进入调查', RECTIFYING: '进入整改', PENDING_REVIEW: '提交复核', CLOSED: '关闭事故' })[value] || value },
    async load() {
      const batchId = this.batchStore.selectedBatchId
      if (!batchId) { this.stats = {}; this.workbench = {}; return }
      this.loading = true; this.error = ''
      try {
        const [stats, workbench, health] = await Promise.all([
          complianceApi.batchStats(batchId), complianceApi.workbench(batchId), complianceApi.auditHealth()
        ])
        if (stats.code !== 0) throw new Error(stats.message || '合规统计加载失败')
        if (workbench.code !== 0) throw new Error(workbench.message || '合规办理台账加载失败')
        this.stats = stats.data || {}; this.workbench = workbench.data || {}
        this.auditHealth = health.code === 0 ? health.data : { healthy: false, message: health.message }
        if (!this.stats.drilldowns?.[this.selectedFilter]) this.selectedFilter = 'ALL'
      } catch (loadError) {
        this.error = loadError.message || '合规工作台加载失败'
      } finally { this.loading = false }
    },
    openStudent(row) { this.$router.push(row.route || `/admin/internship/students/${row.internshipId}`) },
    async run(resultPromise, successMessage, { resetForm = '' } = {}) {
      if (this.acting) return false
      this.acting = true
      try {
        const result = await resultPromise
        if (result.code !== 0) throw new Error(result.message || '操作失败')
        this.$message?.success?.(successMessage)
        if (resetForm) this.forms[resetForm] = freshForms()[resetForm]
        await this.load()
        return true
      } catch (runError) {
        this.$message?.error?.(runError.message || '操作失败')
        return false
      } finally { this.acting = false }
    },
    async uploadToForm(event, formKey, field, bizType) {
      const file = event.target.files?.[0]
      if (!file) return
      if (file.size > 20 * 1024 * 1024) { event.target.value = ''; this.$message?.warning?.('单个文件不能超过20MB'); return }
      const result = await complianceApi.uploadEvidence(file, bizType)
      event.target.value = ''
      if (result.code !== 0) { this.$message?.error?.(result.message || '材料上传失败'); return }
      const fileId = result.data?.fileId || result.data?.id
      if (fileId) this.forms[formKey][field] = [...new Set([...(this.forms[formKey][field] || []), String(fileId)])]
    },
    createConsent() {
      if (!this.consentFormValid) return this.$message?.warning?.('请选择学生，正文版本不少于2字，完整正文不少于20字')
      const form = { ...this.forms.consent, deliveryChannel: this.forms.consent.consentType === 'GUARDIAN' ? 'SMS' : 'PORTAL' }
      this.run(complianceApi.createConsent(form), form.consentType === 'GUARDIAN' ? '监护人任务已创建，送达结果已写入台账' : '学生知情确认任务已下发', { resetForm: 'consent' })
    },
    redeliverConsent(row) { this.run(complianceApi.redeliverConsent(row.id, row.version), '监护人确认链接已轮换，送达结果已更新') },
    createSafetyCourse() {
      if (!this.safetyFormValid) return this.$message?.warning?.('请检查课程名称、版本、正文、时长、分数和尝试次数')
      this.run(complianceApi.createSafetyCourse({ ...this.forms.safety, batchId: this.batchStore.selectedBatchId, status: 'ACTIVE' }), '安全课程已创建', { resetForm: 'safety' })
    },
    async createFiling() {
      if (!this.filingFormValid) return this.$message?.warning?.('请完整填写备案原因、必要风险说明并上传依据附件')
      if (this.acting) return
      this.acting = true
      try {
        const created = await complianceApi.createFiling(this.forms.filing)
        if (created.code !== 0) throw new Error(created.message || '特殊备案创建失败')
        const submitted = await complianceApi.reviewFiling(created.data.id, 'COLLEGE', 'submit', { expectedVersion: created.data.version })
        if (submitted.code !== 0) throw new Error(submitted.message || '特殊备案提交失败')
        this.$message?.success?.('特殊备案已提交学院审核')
        this.forms.filing = freshForms().filing
        await this.load()
      } catch (createError) { this.$message?.error?.(createError.message || '特殊备案办理失败') }
      finally { this.acting = false }
    },
    filingAction(row, level, action) { this.run(complianceApi.reviewFiling(row.id, level, action, { expectedVersion: row.version }), '备案状态已更新') },
    reportIncident() {
      if (!this.incidentFormValid) return this.$message?.warning?.('请填写学生、事故类型、非未来发生时间、地点、摘要和应急措施')
      this.run(complianceApi.reportIncident({ ...this.forms.incident, idempotencyKey: `pc-${Date.now()}-${Math.random().toString(36).slice(2)}` }), '事故已上报', { resetForm: 'incident' })
    },
    incidentTargets(row) {
      const targets = ({ REPORTED: ['EMERGENCY_HANDLING', 'INVESTIGATING'], EMERGENCY_HANDLING: ['INVESTIGATING'], INVESTIGATING: ['RECTIFYING', 'PENDING_REVIEW'], RECTIFYING: ['PENDING_REVIEW'], PENDING_REVIEW: ['CLOSED'] })[row.status] || []
      return targets.filter((target) => target !== 'CLOSED' || (row.fileIds || []).length > 0)
    },
    async createEmergency() {
      if (!this.emergencyFormValid) return this.$message?.warning?.('请检查预案名称、责任人、联系电话、处置步骤和附件')
      if (this.acting) return
      this.acting = true
      try {
        const created = await complianceApi.createEmergencyPlan({ ...this.forms.emergency, batchId: this.batchStore.selectedBatchId })
        if (created.code !== 0) throw new Error(created.message || '应急预案创建失败')
        const submitted = await complianceApi.reviewEmergencyPlan(created.data.id, 'SUBMIT', { expectedVersion: created.data.version })
        if (submitted.code !== 0) throw new Error(submitted.message || '应急预案提交失败')
        this.$message?.success?.('应急预案已提交审核')
        this.forms.emergency = freshForms().emergency
        await this.load()
      } catch (createError) { this.$message?.error?.(createError.message || '应急预案办理失败') }
      finally { this.acting = false }
    },
    emergencyAction(row, action) { this.run(complianceApi.reviewEmergencyPlan(row.id, action, { expectedVersion: row.version }), '应急预案状态已更新') },
    requestExemption() {
      if (!this.exemptionFormValid) return this.$message?.warning?.('请选择真实检查项，填写10字以上原因、未来有效期并上传依据附件')
      this.run(complianceApi.grantExemption(this.forms.exemption), '豁免申请已提交学校审批', { resetForm: 'exemption' })
    },
    generatePackage() {
      if (!this.packageFormValid) return this.$message?.warning?.('请选择证据包目标')
      const targetId = this.forms.package.packageType === 'BATCH' ? this.batchStore.selectedBatchId : this.forms.package.targetId
      this.run(complianceApi.generateEvidencePackage(this.forms.package.packageType, targetId), '证据包已生成')
    },
    async downloadPackage(row) {
      try { await complianceApi.downloadEvidencePackage(row.id, `岗位实习_${row.packageType}_v${row.packageVersion}.zip`) }
      catch (downloadError) { this.$message?.error?.(downloadError.message || '下载失败') }
    },
    openAction(kind, row, action = '', level = '') {
      const dialog = emptyDialog()
      dialog.open = true; dialog.kind = kind; dialog.row = row; dialog.action = action; dialog.level = level
      if (kind === 'revoke-consent') { dialog.title = '作废知情确认任务'; dialog.description = '作废后学生或监护人无法再确认，必须重新下发新任务。'; dialog.commentLabel = '作废原因（至少5字）'; dialog.commentPlaceholder = '说明作废原因'; dialog.confirmText = '确认作废' }
      if (kind === 'safety-review') { dialog.title = action === 'APPROVE' ? '通过安全教育审核' : '退回安全教育记录'; dialog.showScore = action === 'APPROVE'; dialog.commentLabel = action === 'APPROVE' ? '审核备注（可选）' : '退回原因（至少5字）'; dialog.confirmText = action === 'APPROVE' ? '确认通过' : '确认退回' }
      if (kind === 'filing-review') { dialog.title = `${level === 'SCHOOL' ? '学校' : '学院'}${action === 'APPROVE' ? '通过' : '退回'}特殊备案`; dialog.commentLabel = action === 'APPROVE' ? '审核意见（可选）' : '退回原因（至少5字）'; dialog.confirmText = action === 'APPROVE' ? '确认通过' : '确认退回' }
      if (kind === 'incident-transition') { dialog.title = this.incidentTargetText(action); dialog.showInvestigation = ['PENDING_REVIEW', 'CLOSED'].includes(action); dialog.investigationConclusion = row.investigationConclusion || ''; dialog.rectificationPlan = row.rectificationPlan || ''; dialog.responsibilityConclusion = row.responsibilityConclusion || ''; dialog.commentLabel = '流转说明（可选）'; dialog.confirmText = '确认流转' }
      if (kind === 'emergency-review') { dialog.title = action === 'APPROVE' ? '通过应急预案' : '退回应急预案'; dialog.commentLabel = action === 'APPROVE' ? '审核意见（可选）' : '退回原因（至少5字）'; dialog.confirmText = action === 'APPROVE' ? '确认通过' : '确认退回' }
      if (kind === 'exemption-review') { dialog.title = action === 'APPROVE' ? '批准合规豁免' : '拒绝合规豁免'; dialog.commentLabel = action === 'APPROVE' ? '批准意见（建议说明替代控制）' : '拒绝原因（至少5字）'; dialog.confirmText = action === 'APPROVE' ? '确认批准' : '确认拒绝' }
      this.dialog = dialog; this.dialogError = ''
    },
    closeDialog() { if (!this.acting) { this.dialog = emptyDialog(); this.dialogError = '' } },
    async confirmDialog() {
      const dialog = this.dialog
      const comment = dialog.comment.trim()
      if ((dialog.kind === 'revoke-consent' || dialog.action === 'REJECT') && comment.length < 5) { this.dialogError = '原因必须不少于5字'; return }
      if (dialog.showScore && (!Number.isFinite(Number(dialog.score)) || Number(dialog.score) < 0 || Number(dialog.score) > 100)) { this.dialogError = '审核分数必须为0至100'; return }
      if (dialog.showInvestigation && [dialog.investigationConclusion, dialog.rectificationPlan, dialog.responsibilityConclusion].some((value) => value.trim().length < 5)) { this.dialogError = '调查结论、整改方案、责任/复核结论均不少于5字'; return }
      let promise; let successMessage = '操作成功'
      if (dialog.kind === 'revoke-consent') { promise = complianceApi.revokeConsent(dialog.row.id, { expectedVersion: dialog.row.version, reason: comment }); successMessage = '知情任务已作废' }
      if (dialog.kind === 'safety-review') { promise = complianceApi.reviewSafetyCompletion(dialog.row.id, { action: dialog.action, score: dialog.showScore ? Number(dialog.score) : null, comment, expectedVersion: dialog.row.version }); successMessage = '安全教育审核完成' }
      if (dialog.kind === 'filing-review') { promise = complianceApi.reviewFiling(dialog.row.id, dialog.level, dialog.action.toLowerCase(), { expectedVersion: dialog.row.version, comment }); successMessage = '备案状态已更新' }
      if (dialog.kind === 'incident-transition') { promise = complianceApi.transitionIncident(dialog.row.id, { status: dialog.action, expectedVersion: dialog.row.version, comment, investigationConclusion: dialog.investigationConclusion, rectificationPlan: dialog.rectificationPlan, responsibilityConclusion: dialog.responsibilityConclusion }); successMessage = `事故已流转至${this.incidentTargetText(dialog.action)}` }
      if (dialog.kind === 'emergency-review') { promise = complianceApi.reviewEmergencyPlan(dialog.row.id, dialog.action, { expectedVersion: dialog.row.version, comment }); successMessage = '应急预案状态已更新' }
      if (dialog.kind === 'exemption-review') { promise = complianceApi.reviewExemption(dialog.row.id, { action: dialog.action, comment, expectedVersion: dialog.row.version }); successMessage = '豁免审批完成' }
      if (!promise) { this.dialogError = '未知操作，已阻止提交'; return }
      const ok = await this.run(promise, successMessage)
      if (ok) this.closeDialog()
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.workbench-head,.head-actions,.mp-card__head,.dialog-head,.dialog-actions{display:flex;align-items:center;justify-content:space-between;gap:16px}.workbench-head p{margin:5px 0 0}.status-pill,.tab-count{display:inline-flex;align-items:center;justify-content:center;border-radius:999px;background:var(--color-primary-light,#eef4ff);color:var(--color-primary);padding:3px 9px;font-size:12px}.work-tabs{display:flex;gap:8px;overflow-x:auto;padding:2px}.work-tab{border:1px solid var(--border-color);background:#fff;border-radius:8px;padding:9px 13px;cursor:pointer;white-space:nowrap}.work-tab.is-active{border-color:var(--color-primary);color:var(--color-primary);background:var(--color-primary-light,#eef4ff)}.tab-count{margin-left:5px;padding:1px 6px}.metric-card{text-align:left;cursor:pointer}.metric-card.is-active{outline:2px solid var(--color-primary)}.action-panel{border-left:4px solid var(--color-primary)}.form-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:14px 0}.form-grid label,.action-dialog label{display:flex;flex-direction:column;gap:6px;font-size:13px;color:var(--text-secondary)}.form-grid input,.form-grid select,.form-grid textarea,.action-dialog input,.action-dialog textarea{box-sizing:border-box;width:100%;border:1px solid var(--border-color);border-radius:7px;padding:9px 10px;background:#fff;color:var(--text-primary)}.form-grid .span-2{grid-column:span 2}.form-grid .span-3{grid-column:1/-1}.checkbox-label{flex-direction:row!important;align-items:center}.checkbox-label input{width:auto}.field-help,.file-note,.cell-sub{color:var(--text-tertiary);font-size:12px}.file-note{align-self:end;padding-bottom:10px}.table-wrap{overflow-x:auto}.mp-table{width:100%;border-collapse:collapse;min-width:900px}.consent-table{min-width:1180px}.mp-table th,.mp-table td{padding:10px;border-bottom:1px solid var(--border-color);text-align:left;vertical-align:top;font-size:13px}.mp-table th{color:var(--text-secondary);font-weight:600;background:#fafbfc}.empty-cell{text-align:center!important;color:var(--text-tertiary);padding:24px!important}.mp-link,.danger-link{border:0;background:transparent;padding:3px 5px;cursor:pointer;color:var(--color-primary);white-space:nowrap}.danger-link{color:var(--color-danger,#d92d20)}.mp-link:disabled,.danger-link:disabled{opacity:.5;cursor:not-allowed}.action-cell{white-space:nowrap}.state-tag{display:inline-flex;border-radius:999px;padding:3px 8px;font-size:12px;background:#f2f4f7;color:#475467}.state-tag.is-success{background:#ecfdf3;color:#067647}.state-tag.is-danger{background:#fff1f0;color:#b42318}.state-tag.is-warn{background:#fff7e6;color:#8b5c00}.state-tag.is-muted{background:#f2f4f7;color:#667085}.cell-error{max-width:220px;color:#b42318;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-top:4px}.hash-cell{max-width:230px;word-break:break-all;font-family:monospace;font-size:12px}.dialog-mask{position:fixed;inset:0;z-index:3000;background:rgba(16,24,40,.45);display:flex;align-items:center;justify-content:center;padding:20px}.action-dialog{width:min(560px,94vw);max-height:88vh;overflow:auto;background:#fff;border-radius:12px;padding:20px;box-shadow:0 24px 70px rgba(16,24,40,.25);display:flex;flex-direction:column;gap:14px}.dialog-close{border:0;background:transparent;font-size:24px;cursor:pointer;color:#667085}.dialog-actions{justify-content:flex-end;margin-top:4px}.dialog-error{padding:9px 11px;border-radius:7px;background:#fff1f0;color:#b42318;font-size:13px}
@media(max-width:900px){.form-grid{grid-template-columns:1fr 1fr}.form-grid .span-3{grid-column:1/-1}}
@media(max-width:640px){.form-grid{grid-template-columns:1fr}.form-grid .span-2,.form-grid .span-3{grid-column:auto}.workbench-head{align-items:flex-start;flex-direction:column}.head-actions{width:100%}.action-dialog{padding:16px}}
</style>
