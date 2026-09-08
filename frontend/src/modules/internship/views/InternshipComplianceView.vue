<template>
  <ModulePageShell
    :title="activeTab === 'overview' ? '上岗核验' : (tabs.find(item => item.key === activeTab)?.label || '上岗核验')"
    :subtitle="activeTab === 'incidents' ? '跟进事故处置，维护当前批次的应急预案。' : '核对学生上岗条件，查看缺项并继续办理。'"
  >
    <template #actions>
      <template v-if="!reviewRequested && !consentEditor && !safetyEditor && !filingEditor && !incidentEditor && !exemptionEditor && batchStore.selectedBatchId">
        <span class="compliance-updated">最近核验 {{ fmt(workbench.generatedAt || stats.evaluatedAt) }}</span>
        <AppButton variant="ghost" :disabled="loading || acting" @click="load">刷新核验</AppButton>
      </template>
      <AppButton v-if="reviewRequested" variant="ghost" @click="closeReview">返回审核台账</AppButton>
      <template v-else>
      <AppButton v-if="activeTab === 'exemptions' && !exemptionEditor && can('internship.compliance.exempt.request')" variant="primary" @click="openExemptionEditor">申请合规豁免</AppButton>
      <AppButton v-if="exemptionEditor" variant="ghost" @click="closeExemptionEditor">返回豁免台账</AppButton>
      <template v-if="activeTab === 'incidents'">
        <AppButton v-if="incidentEditor" variant="ghost" :disabled="acting" @click="closeIncidentEditor">返回事故与应急</AppButton>
        <template v-else>
          <AppButton v-if="can('internship.incident.handle')" variant="secondary" @click="openIncidentEditor('emergency')">新建应急预案</AppButton>
          <AppButton v-if="can('internship.incident.report')" variant="primary" @click="openIncidentEditor('incident')">上报事故</AppButton>
        </template>
      </template>
      <AppButton v-if="activeTab === 'filings' && !filingEditor && can('internship.filing.review')" variant="primary" @click="openFilingEditor">申请特殊备案</AppButton>
      <AppButton v-if="filingEditor" variant="ghost" @click="closeFilingEditor">返回备案台账</AppButton>
      <AppButton v-if="activeTab === 'safety' && !safetyEditor && can('internship.safety.manage')" variant="primary" @click="openSafetyEditor">配置安全课程</AppButton>
      <AppButton v-if="safetyEditor" variant="ghost" @click="closeSafetyEditor">返回安全教育</AppButton>
      <AppButton v-if="activeTab === 'consents' && !consentEditor && can('internship.consent.manage')" variant="primary" @click="openConsentEditor">下发确认任务</AppButton>
      <AppButton v-if="consentEditor" variant="ghost" @click="closeConsentEditor">返回知情台账</AppButton>
      </template>
    </template>
    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else-if="reviewRequested && (reviewError || groupError || !dialog.open)" class="review-state">
      <LoadingState v-if="groupLoading || !loadedGroups.has(activeTab) && !groupError" />
      <AppInlineAlert v-else type="warning" title="当前记录无法审核" :description="reviewError || groupError || '记录不存在或已不在当前可见范围，请返回台账重新选择。'" />
    </div>
    <div v-else-if="!reviewRequested" class="mp-stack compliance-content">
      <ActionReceipt :receipt="lastReceipt" @close="lastReceipt = null" />
      <AppInlineAlert
        v-if="!batchStore.selectedBatchId"
        type="warning"
        title="请先选择实习批次"
        description="所有统计、台账、审核和证据包都严格使用当前批次。"
      />
      <template v-else>
        <AppInlineAlert
          v-if="auditNotice"
          :type="auditNotice.type"
          :title="auditNotice.title"
          :description="auditNotice.description"
        >
          <template #actions>
            <AppButton size="sm" :disabled="auditHealthLoading" @click="loadAuditHealth">
              {{ auditHealthLoading ? '正在检查' : '重新检查' }}
            </AppButton>
          </template>
        </AppInlineAlert>

        <nav v-if="!consentEditor && !safetyEditor && !filingEditor && !incidentEditor && !exemptionEditor" class="work-tabs" aria-label="合规办理工作区">
          <div v-for="group in tabGroups" :key="group.key" class="work-tabs__group" :aria-label="group.label">

            <div class="work-tabs__buttons">
              <button
                v-for="tabItem in group.items"
                :key="tabItem.key"
                type="button"
                class="work-tab"
                :class="{ 'is-active': activeTab === tabItem.key }"
                :aria-pressed="activeTab === tabItem.key"
                @click="goTab(tabItem.key)"
              >
                {{ tabItem.label }}
                <span v-if="tabItem.count != null" class="tab-count">{{ tabItem.count }}</span>
              </button>
            </div>
          </div>
        </nav>

        <AppInlineAlert
          v-if="groupLoading && activeTab !== 'overview'"
          type="info" title="正在加载明细"
          description="统计数字已是最新，明细列表加载中…"
        />
        <AppInlineAlert
          v-else-if="groupError && activeTab !== 'overview'"
          type="danger" title="明细加载失败"
          :description="groupError"
        >
          <template #actions>
            <AppButton size="sm" :disabled="groupLoading" @click="reloadActiveGroup">重试</AppButton>
          </template>
        </AppInlineAlert>
        <AppInlineAlert
          v-if="statsError && activeTab !== 'overview'"
          type="warning"
          title="学生选择暂不可用"
          description="合规总览统计加载失败，依赖学生选择的新建操作已暂停；现有台账仍可查看和审核。请重试刷新。"
        >
          <template #actions>
            <AppButton size="sm" :disabled="loading" @click="load">重试</AppButton>
          </template>
        </AppInlineAlert>

        <template v-if="activeTab === 'overview'">
          <AppInlineAlert
            v-if="statsError"
            type="danger" title="合规总览统计加载失败"
            :description="statsError"
          >
            <template #actions>
              <AppButton size="sm" :disabled="loading" @click="load">重试</AppButton>
            </template>
          </AppInlineAlert>
          <div v-else class="compliance-metrics">
            <button
              v-for="metric in overviewMetrics"
              :key="metric.metricCode"
              type="button"
                class="metric-card"
                :class="{ 'is-active': selectedFilter === metric.drilldownFilter }"
                :aria-pressed="selectedFilter === metric.drilldownFilter"
              @click="selectFilter(metric.drilldownFilter)"
            >
              <span class="mp-note">{{ metric.metricLabel }}</span>
              <strong>{{ metric.count }}</strong>
            </button>
          </div>
          <section v-if="!statsError" class="mp-card">
            <div class="mp-card__head roster-heading">
              <div>
                <strong>学生核验清单</strong>
                <p class="mp-note">{{ drilldownRows.length }} 名学生 · 展开缺项查看完整原因</p>
              </div>
              <div class="compliance-filters"><label>核验分类 <select :value="selectedFilter" @change="selectFilter($event.target.value)"><option v-for="metric in metrics" :key="metric.metricCode" :value="metric.drilldownFilter">{{ metric.metricLabel }}（{{ metric.count }}）</option></select></label></div>
            </div>
            <div class="table-wrap">
              <table class="mp-table compliance-roster">
                <thead><tr><th>学生</th><th>指导教师</th><th>上岗条件</th><th>归档条件</th><th>操作</th></tr></thead>
                <tbody>
                  <tr v-for="row in drilldownRows" :key="row.internshipId">
                    <td><strong>{{ row.studentName }}</strong><div class="cell-sub">{{ row.studentNo }}</div></td>
                    <td>{{ row.advisorName || '待分配' }}</td>
                    <td><details v-if="row.blockers?.length"><summary>{{ row.blockers.length }} 项待补齐</summary><ul><li v-for="(item, index) in row.blockers" :key="index"><strong>{{ item.label }}</strong>：{{ item.reason }}</li></ul></details><span v-else>条件已满足</span></td>
                    <td><details v-if="row.archiveBlockers?.length"><summary>{{ row.archiveBlockers.length }} 项待补齐</summary><ul><li v-for="(item, index) in row.archiveBlockers" :key="index"><strong>{{ item.label }}</strong>：{{ item.reason }}</li></ul></details><span v-else>条件已满足</span></td>
                    <td><AppButton variant="ghost" @click="openStudent(row)">查看学生</AppButton><AppButton v-if="needsIdentityCorrection(row) && can('academicAffairs.roster.correction.view') && can('academicAffairs.roster.correction.apply')" variant="ghost" @click="openIdentityCorrection(row)">核实身份资料</AppButton></td>
                  </tr>
                  <tr v-if="!drilldownRows.length"><td colspan="5" class="empty-cell">当前口径下暂无学生</td></tr>
                </tbody>
              </table>
            </div>
          </section>
        </template>

        <template v-else-if="activeTab === 'consents'">
          <section v-if="consentEditor && can('internship.consent.manage')" class="mp-card consent-editor">
            <div class="mp-card__head">
              <div><strong>下发知情确认任务</strong><p class="mp-note">教师只能下发、催办、作废，不能代学生或监护人确认。</p></div>
            </div>
            <div class="form-grid consent-fields">
              <label>学生 *
                <select v-model="forms.consent.internshipId" :disabled="!!statsError">
                  <option value="">请选择学生</option>
                  <option v-for="student in students" :key="student.internshipId" :value="student.internshipId">{{ student.studentNo }} · {{ student.studentName }}</option>
                </select>
              </label>
              <label>确认人 *
                <select v-model="forms.consent.consentType">
                  <option value="STUDENT">学生本人</option>
                  <option value="GUARDIAN">已绑定监护人</option>
                </select>
              </label>
              <label>正文版本 *
                <input v-model.trim="forms.consent.contentVersion" maxlength="64" required minlength="2" placeholder="例如 2026-秋-v1" />
              </label>
              <label class="span-3">知情正文 *
                <textarea v-model.trim="forms.consent.contentSnapshot" rows="12" maxlength="20000" placeholder="粘贴本次下发的完整正文快照；正文变化必须升级版本" />
                <span class="field-help">{{ forms.consent.contentSnapshot.length }}/20000</span>
              </label>
            </div>
            <p class="consent-destination">{{ forms.consent.consentType === 'GUARDIAN' ? '发送至该学生已绑定监护人，送达结果在台账查看。' : '下发后由学生本人在学生端阅读并确认。' }}</p>
            <p v-if="consentError" role="alert" class="cell-error">{{ consentError }}</p>
            <div class="consent-actions"><AppButton variant="secondary" :disabled="acting" @click="closeConsentEditor">返回台账</AppButton><AppButton variant="primary" :loading="acting" :disabled="!consentFormValid" @click="createConsent">下发确认任务</AppButton></div>
            <p v-if="!consentFormValid" class="cell-sub">请选择学生，填写至少 2 字的正文版本和至少 20 字的完整正文。</p>
          </section>

          <section v-if="!consentEditor" class="mp-card consent-ledger">
            <div class="mp-card__head"><strong>知情确认台账</strong><span class="mp-note">{{ workbench.consents?.length || 0 }} 条</span></div>
            <p v-if="consentDelivery.message" :role="consentDelivery.error ? 'alert' : 'status'" :class="consentDelivery.error ? 'cell-error' : 'cell-sub'">{{ consentDelivery.message }}</p>
            <div class="table-wrap">
              <table class="mp-table consent-table">
                <thead><tr><th>学生/确认人</th><th>任务状态</th><th>送达情况</th><th>阅读与确认</th><th>正文版本</th><th>操作</th></tr></thead>
                <tbody>
                  <tr v-for="row in workbench.consents || []" :key="row.id">
                    <td>
                      <strong>{{ row.studentNo }} · {{ row.studentName }}</strong>
                      <div class="cell-sub">{{ row.consentType === 'GUARDIAN' ? `${row.participantName || '监护人'} · ${row.contactMasked || '手机号未显示'}` : '学生本人' }}</div>
                    </td>
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
                    <td>{{ row.contentVersion || '-' }}<div v-if="row.consentType === 'GUARDIAN'" class="cell-sub">链接到期 {{ fmt(row.guardianTokenExpiresAt) }}</div></td>
                    <td class="action-cell">
                      <button
                        v-if="row.consentType === 'GUARDIAN' && row.status === 'PENDING' && can('internship.consent.manage')"
                        type="button" class="mp-link" :disabled="acting" @click="redeliverConsent(row)"
                      >{{ acting && consentDelivery.id === String(row.id) ? '正在发送…' : '重新发送' }}</button>
                      <button
                        v-if="['PENDING','VALID'].includes(row.status) && can('internship.consent.manage')"
                        type="button" class="danger-link" :disabled="acting" @click="openAction('revoke-consent', row)"
                      >作废</button>
                    </td>
                  </tr>
                  <tr v-if="showEmpty(workbench.consents)"><td colspan="6" class="empty-cell">暂无知情任务，可从右上角下发确认任务</td></tr>
                </tbody>
              </table>
            </div>
          </section>
        </template>

        <template v-else-if="activeTab === 'safety'">
          <section v-if="safetyEditor && can('internship.safety.manage')" class="mp-card safety-editor">
            <div class="mp-card__head"><div><strong>配置安全教育课程</strong><p class="mp-note">课程升级后旧版本完成记录不能满足新版本。</p></div></div>
            <div class="form-grid">
              <label>课程名称 *<input v-model.trim="forms.safety.title" maxlength="200" placeholder="例如 岗前安全教育必修课" /></label>
              <label>课程版本 *<input v-model.trim="forms.safety.courseVersion" maxlength="40" placeholder="例如 2026-v1" /></label>
              <label>学习时长（分钟） *<input v-model.number="forms.safety.requiredMinutes" type="number" min="1" max="1440" /></label>
              <label>及格分数 *<input v-model.number="forms.safety.passingScore" type="number" min="1" max="100" /></label>
              <label>最多考核次数 *<input v-model.number="forms.safety.maxAttempts" type="number" min="1" max="20" /></label>
              <label class="checkbox-label"><input v-model="forms.safety.requireCommitment" type="checkbox" />要求学生安全承诺</label>
              <label class="span-3">课程正文 *<textarea v-model.trim="forms.safety.contentSnapshot" rows="7" maxlength="30000" placeholder="完整课程正文、注意事项和考核要求" /></label>
            </div>
            <p v-if="safetyError" role="alert" class="cell-error">{{ safetyError }}</p>
            <p v-if="!safetyFormValid" class="cell-sub">课程名称至少 2 字，版本必填，正文至少 20 字；请填写有效的时长、分数与次数。</p>
            <div class="consent-actions"><AppButton :disabled="acting" variant="secondary" @click="closeSafetyEditor">返回台账</AppButton><AppButton :disabled="!safetyFormValid" :loading="acting" variant="primary" @click="createSafetyCourse">保存并启用课程</AppButton></div>
          </section>
          <section v-if="!safetyEditor" class="mp-card safety-ledger">
            <div class="mp-card__head"><strong>当前课程</strong><span class="mp-note">{{ workbench.safetyCourses?.length || 0 }} 门</span></div>
            <div class="table-wrap"><table class="mp-table"><thead><tr><th>课程与版本</th><th>状态</th><th>学习要求</th><th>考核要求</th><th>安全承诺</th></tr></thead><tbody>
              <tr v-for="row in workbench.safetyCourses || []" :key="row.id"><td><strong>{{ row.title }}</strong><div class="cell-sub">{{ row.courseVersion }}</div></td><td>{{ complianceStatusText(row.status) }}</td><td>{{ row.requiredMinutes }} 分钟</td><td>{{ row.passingScore }} 分及格<div class="cell-sub">最多 {{ row.maxAttempts }} 次</div></td><td>{{ row.requireCommitment ? '必需' : '否' }}</td></tr>
              <tr v-if="showEmpty(workbench.safetyCourses)"><td colspan="5" class="empty-cell">当前批次未配置课程。请先配置课程，再办理学生安全教育核验</td></tr>
            </tbody></table></div>
          </section>
          <section v-if="!safetyEditor" class="mp-card safety-ledger">
            <div class="mp-card__head"><strong>学生学习与审核</strong></div>
            <div class="table-wrap"><table class="mp-table"><thead><tr><th>学生</th><th>课程与版本</th><th>状态</th><th>学习与考核</th><th>审核</th></tr></thead><tbody>
              <tr v-for="row in workbench.safetyCompletions || []" :key="row.id">
                <td><strong>{{ row.studentName }}</strong><div class="cell-sub">{{ row.studentNo }}</div></td><td>{{ row.courseTitle }}<div class="cell-sub">学习版本 {{ row.courseVersion }} · 当前 {{ row.currentCourseVersion }}</div></td><td>{{ complianceStatusText(row.status) }}</td><td>{{ row.studiedMinutes }} 分钟 · {{ row.score ?? '未评分' }}<div class="cell-sub">已考核 {{ row.attemptCount }} 次</div></td>
                <td class="action-cell"><template v-if="row.status === 'PENDING_REVIEW' && can('internship.safety.manage')"><button type="button" class="mp-link" @click="openAction('safety-review', row, 'APPROVE')">通过</button><button type="button" class="danger-link" @click="openAction('safety-review', row, 'REJECT')">退回</button></template></td>
              </tr><tr v-if="showEmpty(workbench.safetyCompletions)"><td colspan="5" class="empty-cell">暂无学生学习记录</td></tr>
            </tbody></table></div>
          </section>
        </template>

        <template v-else-if="activeTab === 'filings'">
          <section v-if="filingEditor && can('internship.filing.review')" class="mp-card filing-editor">
            <div class="mp-card__head"><div><strong>新建特殊备案</strong><p class="mp-note">经办人创建并提交，申请人与审核人必须分离。</p></div></div>
            <fieldset class="form-grid filing-fields" :disabled="acting || !!filingDraft">
              <label>学生 *<select v-model="forms.filing.internshipId" :disabled="!!statsError"><option value="">请选择学生</option><option v-for="student in students" :key="student.internshipId" :value="student.internshipId">{{ student.studentNo }} · {{ student.studentName }}</option></select></label>
              <label>备案类型 *<select v-model="forms.filing.filingType"><option v-for="item in filingTypes" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
              <label>目的地区<input v-model.trim="forms.filing.destinationRegion" maxlength="200" placeholder="跨区域/境外时填写" /></label>
              <label class="span-3">备案原因 *<textarea v-model.trim="forms.filing.triggerReason" rows="3" maxlength="500" placeholder="不少于5字" /></label>
              <label class="span-3">风险说明<textarea v-model.trim="forms.filing.riskDescription" rows="3" maxlength="2000" placeholder="高风险、夜班、境外、未成年类型必填" /></label>
              <label>依据附件 *<input type="file" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png" @change="uploadToForm($event, 'filing', 'fileIds', 'INTERNSHIP_FILING')" /></label>
              <span class="file-note">{{ fileText(forms.filing.fileIds) }}</span>
            </fieldset>
            <AppInlineAlert v-if="filingDraft" type="warning" title="备案草稿已保存，尚未提交学院" description="请重试提交原草稿，或返回台账核对；无需重新创建。" />
            <p v-if="filingError" role="alert" class="cell-error">{{ filingError }}</p>
            <p v-if="!filingFormValid && !filingDraft" class="cell-sub">请选择学生，填写至少 5 字的备案原因并上传依据材料；指定类型还需填写风险说明。</p>
            <div class="consent-actions"><AppButton variant="secondary" :disabled="acting" @click="closeFilingEditor">返回台账</AppButton><AppButton variant="primary" :disabled="!filingFormValid && !filingDraft" :loading="acting" @click="createFiling">{{ filingDraft ? '重试提交学院审核' : '提交学院审核' }}</AppButton></div>
          </section>
          <section v-if="!filingEditor" class="mp-card filing-ledger"><div class="mp-card__head"><strong>特殊备案台账</strong></div><div class="table-wrap"><table class="mp-table"><thead><tr><th>学生</th><th>类型</th><th>状态</th><th>申请与材料</th><th>审核意见</th><th>操作</th></tr></thead><tbody>
            <tr v-for="row in workbench.filings || []" :key="row.id"><td><strong>{{ row.studentName }}</strong><div class="cell-sub">{{ row.studentNo }}</div></td><td>{{ filingTypeText(row.filingType) }}</td><td>{{ complianceStatusText(row.status) }}</td><td>{{ row.triggerReason }}<div class="cell-sub">依据材料 {{ row.fileIds?.length || 0 }} 份</div></td><td><div>学院：{{ row.collegeComment || '暂无意见' }}</div><div class="cell-sub">学校：{{ row.schoolComment || '暂无意见' }}</div></td><td class="action-cell">
              <button v-if="row.status === 'DRAFT' && can('internship.filing.review')" type="button" class="mp-link" @click="filingAction(row, 'COLLEGE', 'submit')">提交</button>
              <template v-if="row.status === 'PENDING_COLLEGE' && can('internship.filing.review')"><button type="button" class="mp-link" @click="openAction('filing-review', row, 'APPROVE', 'COLLEGE')">学院通过</button><button type="button" class="danger-link" @click="openAction('filing-review', row, 'REJECT', 'COLLEGE')">学院退回</button></template>
              <template v-if="row.status === 'PENDING_SCHOOL' && can('internship.filing.review')"><button type="button" class="mp-link" @click="openAction('filing-review', row, 'APPROVE', 'SCHOOL')">学校通过</button><button type="button" class="danger-link" @click="openAction('filing-review', row, 'REJECT', 'SCHOOL')">学校退回</button></template>
            </td></tr><tr v-if="showEmpty(workbench.filings)"><td colspan="6" class="empty-cell">暂无特殊备案</td></tr>
          </tbody></table></div></section>
        </template>

        <template v-else-if="activeTab === 'incidents'">
          <section v-if="incidentEditor === 'incident' && can('internship.incident.report')" class="mp-card incident-editor">
            <div class="mp-card__head"><div><strong>上报事故</strong><p class="mp-note">填写事故情况与已采取措施，提交后在台账继续跟进。</p></div></div>
            <fieldset class="form-grid incident-fields" :disabled="acting">
              <label>学生<select v-model="forms.incident.internshipId" :disabled="!!statsError"><option value="">请选择学生</option><option v-for="student in students" :key="student.internshipId" :value="student.internshipId">{{ student.studentNo }} · {{ student.studentName }}</option></select></label>
              <label>严重程度<select v-model="forms.incident.severity"><option value="LOW">一般</option><option value="MEDIUM">较大</option><option value="HIGH">重大</option><option value="CRITICAL">特别重大</option></select></label>
              <label>事故类型<input v-model.trim="forms.incident.incidentType" maxlength="50" placeholder="例如 人身伤害/交通/设备" /></label>
              <label>发生时间<input v-model="forms.incident.occurredAt" type="datetime-local" :max="nowLocal" /></label>
              <label class="span-2">地点<input v-model.trim="forms.incident.location" maxlength="300" placeholder="具体到企业、车间或道路" /></label>
              <label class="span-3">情况摘要<textarea v-model.trim="forms.incident.summary" rows="3" maxlength="2000" placeholder="不少于5字，说明人员、时间、经过和当前状态" /></label>
              <label class="span-3">已采取应急措施<textarea v-model.trim="forms.incident.emergencyAction" rows="3" maxlength="2000" placeholder="说明送医、报警、停工、家校联系等措施" /></label>
              <label>现场材料<input type="file" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.mp4" @change="uploadToForm($event, 'incident', 'fileIds', 'INTERNSHIP_INCIDENT')" /></label>
              <span class="file-note">{{ fileText(forms.incident.fileIds) }}</span>
            </fieldset>
            <p v-if="incidentError" role="alert" class="dialog-error">{{ incidentError }}</p>
            <p v-if="!incidentFormValid" class="field-help">请选择学生，填写事故类型、发生时间、地点及至少 5 字的情况和应急措施。</p>
            <div class="consent-actions"><AppButton variant="secondary" :disabled="acting" @click="closeIncidentEditor">返回台账</AppButton><AppButton variant="primary" :loading="acting" :disabled="!incidentFormValid" @click="reportIncident">提交事故报告</AppButton></div>
          </section>
          <section v-if="!incidentEditor" class="mp-card incident-ledger"><div class="mp-card__head"><strong>事故处置台账</strong></div><div class="table-wrap"><table class="mp-table incident-table"><thead><tr><th>事故 / 学生</th><th>状态与程度</th><th>最近进展</th><th>当前待办</th><th>操作</th></tr></thead><tbody>
            <tr v-for="row in incidentRows" :key="row.id" :class="{ 'is-focus': String($route.query.id || '') === String(row.id) }">
              <td><strong>{{ row.incidentNo }}</strong><div>{{ row.studentName || '—' }}</div><div class="cell-sub">{{ row.studentNo }}</div><div v-if="row.riskId" class="cell-sub">关联风险 #{{ row.riskId }}</div></td>
              <td><span class="state-tag">{{ complianceStatusText(row.status) }}</span><div class="cell-sub">{{ severityText(row.severity) }}</div></td>
              <td><span>{{ row.latestEvent }}</span><div class="cell-sub">证据 {{ row.fileIds?.length || 0 }} 份</div></td>
              <td><strong>{{ row.currentAction }}</strong><div v-if="row.closeBlockers?.length" class="incident-blockers">{{ row.closeBlockers.join('；') }}</div></td>
              <td class="action-cell">
                <button v-for="target in incidentTargets(row)" :key="target" type="button" class="mp-link"
                  :disabled="target === 'CLOSED' && !row.closeAllowed"
                  :title="target === 'CLOSED' && row.closeBlockers?.length ? row.closeBlockers.join('；') : ''"
                  @click="openAction('incident-transition', row, target)">{{ incidentTargetText(target) }}</button>
                <button v-if="row.status === 'CLOSED' && row.evidenceTarget?.targetId && can('internship.evidence.export')" type="button" class="mp-link" @click="generateIncidentEvidence(row)">生成监管证据包</button>
              </td>
            </tr>
            <tr v-if="showEmpty(workbench.incidents)"><td colspan="5" class="empty-cell">暂无事故记录</td></tr>
          </tbody></table></div></section>

          <section v-if="incidentEditor === 'emergency' && can('internship.incident.handle')" class="mp-card incident-editor">
            <div class="mp-card__head"><strong>新建批次应急预案</strong></div>
            <fieldset class="form-grid incident-fields" :disabled="acting || !!emergencyDraft">
              <label>预案名称<input v-model.trim="forms.emergency.planName" maxlength="200" /></label>
              <label>责任人<input v-model.trim="forms.emergency.responsiblePerson" maxlength="100" /></label>
              <label>应急电话<input v-model.trim="forms.emergency.emergencyContact" type="tel" maxlength="30" placeholder="手机号或座机" /></label>
              <label>备用电话<input v-model.trim="forms.emergency.backupContact" type="tel" maxlength="30" /></label>
              <label class="span-2">医院/支援单位<input v-model.trim="forms.emergency.hospitalOrSupport" maxlength="300" /></label>
              <label class="span-3">处置步骤<textarea v-model.trim="forms.emergency.responseSteps" rows="5" maxlength="5000" placeholder="不少于10字，明确报告、救援、转运、家校沟通和复盘步骤" /></label>
              <label>预案附件<input type="file" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png" @change="uploadToForm($event, 'emergency', 'fileIds', 'INTERNSHIP_EMERGENCY')" /></label><span class="file-note">{{ fileText(forms.emergency.fileIds) }}</span>
            </fieldset>
            <AppInlineAlert v-if="emergencyDraft" type="warning" title="预案草稿已保存，尚未确认提交审核" description="请重试提交原草稿，或返回台账核对当前状态，无需重新创建。" />
            <p v-if="emergencyError" role="alert" class="dialog-error">{{ emergencyError }}</p>
            <p v-if="!emergencyFormValid && !emergencyDraft" class="field-help">请填写预案名称、责任人、有效联系电话、至少 10 字的处置步骤并上传预案附件。</p>
            <div class="consent-actions"><AppButton variant="secondary" :disabled="acting" @click="closeIncidentEditor">返回台账</AppButton><AppButton variant="primary" :loading="acting" :disabled="!emergencyFormValid && !emergencyDraft" @click="createEmergency">{{ emergencyDraft ? '重试提交预案审核' : '提交预案审核' }}</AppButton></div>
          </section>
          <section v-if="!incidentEditor" class="mp-card incident-ledger"><div class="mp-card__head"><strong>应急预案</strong></div><div class="table-wrap"><table class="mp-table"><thead><tr><th>预案名称</th><th>应急联系人</th><th>状态</th><th>材料</th><th>操作</th></tr></thead><tbody>
            <tr v-for="row in workbench.emergencyPlans || []" :key="row.id"><td>{{ row.planName }}</td><td>{{ row.responsiblePerson }}<div class="cell-sub">{{ row.emergencyContact }}</div></td><td>{{ complianceStatusText(row.status) }}</td><td>{{ row.fileIds?.length || 0 }} 份</td><td class="action-cell"><button v-if="row.status === 'DRAFT' && can('internship.incident.handle')" type="button" class="mp-link" @click="emergencyAction(row, 'SUBMIT')">提交审核</button><template v-if="row.status === 'PENDING_REVIEW' && can('internship.incident.handle')"><button type="button" class="mp-link" @click="openAction('emergency-review', row, 'APPROVE')">通过</button><button type="button" class="danger-link" @click="openAction('emergency-review', row, 'REJECT')">退回</button></template></td></tr>
            <tr v-if="showEmpty(workbench.emergencyPlans)"><td colspan="5" class="empty-cell">暂无应急预案</td></tr>
          </tbody></table></div></section>
        </template>

        <template v-else-if="activeTab === 'exemptions'">
          <section v-if="exemptionEditor && can('internship.compliance.exempt.request')" class="mp-card incident-editor">
            <div class="mp-card__head"><div><strong>申请合规豁免</strong><p class="mp-note">说明特殊情况、替代措施和有效期，提交学校审核。</p></div></div>
            <fieldset class="form-grid incident-fields" :disabled="acting">
              <label>学生<select v-model="forms.exemption.internshipId" :disabled="!!statsError"><option value="">请选择学生</option><option v-for="student in students" :key="student.internshipId" :value="student.internshipId">{{ student.studentNo }} · {{ student.studentName }}</option></select></label>
              <label>检查项<select v-model="forms.exemption.checkCode"><option value="">请选择检查项</option><option v-for="item in exemptionChecks" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
              <label>有效期至<input v-model="forms.exemption.validUntil" type="datetime-local" :min="nowLocal" /></label>
              <label class="span-3">申请原因<textarea v-model.trim="forms.exemption.reason" rows="4" maxlength="1000" placeholder="不少于10字，说明特殊事实、替代控制和责任人" /></label>
              <label>依据附件<input type="file" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png" @change="uploadToForm($event, 'exemption', 'evidenceFileIds', 'COMPLIANCE_EVIDENCE')" /></label><span class="file-note">{{ fileText(forms.exemption.evidenceFileIds) }}</span>
            </fieldset>
            <p v-if="exemptionError" role="alert" class="dialog-error">{{ exemptionError }}</p>
            <p v-if="!exemptionFormValid" class="field-help">请选择学生和检查项，填写至少 10 字原因、未来有效期，并上传依据附件。</p>
            <div class="consent-actions"><AppButton variant="secondary" :disabled="acting" @click="closeExemptionEditor">返回台账</AppButton><AppButton variant="primary" :loading="acting" :disabled="!exemptionFormValid" @click="requestExemption">提交学校审核</AppButton></div>
          </section>
          <section v-if="!exemptionEditor" class="mp-card incident-ledger"><div class="mp-card__head"><strong>豁免台账</strong></div><div class="table-wrap"><table class="mp-table"><thead><tr><th>学生 / 检查项</th><th>申请原因</th><th>有效期与状态</th><th>经办人员</th><th>操作</th></tr></thead><tbody>
            <tr v-for="row in workbench.exemptions || []" :key="row.id"><td><strong>{{ row.studentName }}</strong><div class="cell-sub">{{ row.studentNo }}</div><div>{{ exemptionCheckText(row.checkCode) }}</div></td><td>{{ row.reason }}</td><td><span class="state-tag">{{ complianceStatusText(row.status) }}</span><div class="cell-sub">截至 {{ fmt(row.validUntil) }}</div></td><td>申请：{{ row.requestedByName || '—' }}<div class="cell-sub">审核：{{ row.reviewedByName || '待审核' }}</div></td><td class="action-cell"><template v-if="row.status === 'PENDING_REVIEW' && can('internship.compliance.exempt.approve')"><button type="button" class="mp-link" @click="openAction('exemption-review', row, 'APPROVE')">批准</button><button type="button" class="danger-link" @click="openAction('exemption-review', row, 'REJECT')">拒绝</button></template></td></tr>
            <tr v-if="showEmpty(workbench.exemptions)"><td colspan="5" class="empty-cell">暂无豁免记录</td></tr>
          </tbody></table></div></section>
        </template>

        <template v-else-if="activeTab === 'evidence'">
          <section class="mp-card evidence-generator">
            <div class="mp-card__head"><div><strong>生成监管证据包</strong><p class="mp-note">按当前批次或单个学生汇集材料；生成后在历史记录查看缺项并下载。</p></div></div>
            <fieldset class="form-grid evidence-fields" :disabled="acting">
              <label>包类型<select v-model="forms.package.packageType"><option value="BATCH">批次包</option><option value="STUDENT">学生包</option></select></label>
              <label v-if="forms.package.packageType === 'STUDENT'">学生<select v-model="forms.package.targetId" :disabled="!!statsError"><option value="">请选择学生</option><option v-for="student in students" :key="student.internshipId" :value="student.internshipId">{{ student.studentNo }} · {{ student.studentName }}</option></select></label>
            </fieldset>
            <p v-if="packageError" role="alert" class="dialog-error">{{ packageError }}</p>
            <AppButton v-if="can('internship.evidence.export')" variant="primary" :loading="acting" :disabled="!packageFormValid" @click="generatePackage">生成证据包</AppButton>
          </section>
          <section class="mp-card incident-ledger"><div class="mp-card__head"><strong>证据包历史</strong></div><div class="table-wrap"><table class="mp-table"><thead><tr><th>对象与版本</th><th>生成结果</th><th>材料完整性</th><th>生成记录</th><th>操作</th></tr></thead><tbody>
            <tr v-for="row in workbench.evidencePackages || []" :key="row.id"><td><strong>{{ packageTypeText(row.packageType) }} · v{{ row.packageVersion }}</strong><div class="cell-sub">对象 #{{ row.targetId }}</div></td><td><span class="state-tag">{{ complianceStatusText(row.status) }}</span></td><td>{{ row.fileCount }} 份文件<div :class="row.missingCount ? 'incident-blockers' : 'cell-sub'">{{ row.missingCount ? `缺少 ${row.missingCount} 项，请核对包内缺项清单` : '无缺失项' }}</div></td><td>{{ row.generatedByName || '—' }}<div class="cell-sub">{{ fmt(row.generatedAt) }}</div><details v-if="row.packageSha256" class="evidence-hash"><summary>文件校验码</summary><code>{{ row.packageSha256 }}</code></details></td><td><button v-if="['READY','READY_WITH_MISSING'].includes(row.status) && can('internship.evidence.export')" type="button" class="mp-link" @click="downloadPackage(row)">下载ZIP</button></td></tr>
            <tr v-if="showEmpty(workbench.evidencePackages)"><td colspan="5" class="empty-cell">暂无证据包</td></tr>
          </tbody></table></div></section>
        </template>
      </template>
    </div>

    <div v-if="dialog.open && (!reviewRequested || !loading && !groupLoading && !reviewError && !groupError)" :class="reviewRequested ? 'review-workspace' : 'dialog-mask'" @click.self="reviewRequested ? null : closeDialog()">
      <section class="action-dialog" :role="reviewRequested ? 'region' : 'dialog'" :aria-modal="reviewRequested ? undefined : true" :aria-label="dialog.title">
        <div class="dialog-head"><strong>{{ dialog.title }}</strong><button v-if="!reviewRequested" type="button" class="dialog-close" @click="closeDialog">×</button></div>
        <p v-if="dialog.description" class="mp-note">{{ dialog.description }}</p>
        <section v-if="dialog.row" class="review-context" aria-label="审核对象">
          <strong>{{ dialog.row.studentName || dialog.row.planName || '当前记录' }}</strong>
          <span class="cell-sub">{{ dialog.row.studentNo || '' }} · {{ complianceStatusText(dialog.row.status) }}</span>
          <p v-if="dialog.row.courseTitle">{{ dialog.row.courseTitle }} · 学习版本 {{ dialog.row.courseVersion }}<br />已学习 {{ dialog.row.studiedMinutes }} 分钟 · 成绩 {{ dialog.row.score ?? '未评分' }} · 考核 {{ dialog.row.attemptCount }} 次</p>
          <template v-if="dialog.kind === 'incident-transition'">
            <p><strong>{{ dialog.row.incidentNo }}</strong><br />{{ dialog.row.incidentType }} · {{ severityText(dialog.row.severity) }}</p>
            <p>{{ fmt(dialog.row.occurredAt) }}<br />{{ dialog.row.location }}</p>
            <p><strong>事故情况</strong><br />{{ dialog.row.summary || '未填写' }}</p>
            <p><strong>当前待办</strong><br />{{ dialog.row.currentAction }}</p>
            <p v-if="dialog.row.closeBlockers?.length" class="incident-blockers">{{ dialog.row.closeBlockers.join('；') }}</p>
          </template>
          <template v-if="dialog.kind === 'emergency-review'">
            <p><strong>应急联系人</strong><br />{{ dialog.row.responsiblePerson }} · {{ dialog.row.emergencyContact }}</p>
            <p v-if="dialog.row.backupContact">备用电话：{{ dialog.row.backupContact }}</p>
            <p v-if="dialog.row.hospitalOrSupport">支援单位：{{ dialog.row.hospitalOrSupport }}</p>
          </template>
          <template v-if="dialog.kind === 'exemption-review'">
            <p><strong>{{ exemptionCheckText(dialog.row.checkCode) }}</strong><br />{{ dialog.row.reason }}</p>
            <p>有效期至 {{ fmt(dialog.row.validUntil) }}</p>
            <p>申请人：{{ dialog.row.requestedByName || '—' }}</p>
          </template>
          <p v-if="dialog.row.triggerReason"><strong>备案原因</strong><br />{{ dialog.row.triggerReason }}</p>
          <p v-if="dialog.row.destinationRegion">目的地区：{{ dialog.row.destinationRegion }}</p>
          <p v-if="dialog.row.collegeComment">学院意见：{{ dialog.row.collegeComment }}</p>
          <div v-if="dialog.row.fileIds?.length" class="review-files"><AppButton v-for="(fileId, index) in dialog.row.fileIds" :key="fileId" variant="ghost" @click="previewReviewFile(fileId)">查看材料 {{ index + 1 }}</AppButton></div>
        </section>
        <AppInlineAlert v-if="conflict.active" type="warning" title="记录已更新，请重新打开审核" description="原审核已停止提交。填写的意见仍保留，可复制后返回台账，重新核对最新记录。">
          <dl class="review-latest"><div v-for="item in conflict.latest" :key="item.label"><dt>{{ item.label }}</dt><dd>{{ item.value }}</dd></div></dl>
          <p v-if="conflict.stale">最新数据加载失败，请返回台账刷新。</p>
        </AppInlineAlert>
        <label v-if="dialog.showScore">审核分数（0-100）<input v-model.number="dialog.score" type="number" min="0" max="100" /></label>
        <label v-if="dialog.showInvestigation">调查结论<textarea v-model.trim="dialog.investigationConclusion" rows="3" maxlength="2000" /></label>
        <label v-if="dialog.showInvestigation">整改方案<textarea v-model.trim="dialog.rectificationPlan" rows="3" maxlength="2000" /></label>
        <label v-if="dialog.showInvestigation">责任/复核结论<textarea v-model.trim="dialog.responsibilityConclusion" rows="3" maxlength="2000" /></label>
        <label v-if="dialog.showEvidenceUpload">事故证据附件<input type="file" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.mp4" @change="uploadDialogEvidence" /><span class="file-note">{{ fileText(dialog.fileIds) }}</span></label>
        <label>{{ dialog.commentLabel }}<textarea v-model.trim="dialog.comment" rows="4" maxlength="1000" :placeholder="dialog.commentPlaceholder" /></label>
        <div v-if="dialogError" class="dialog-error">{{ dialogError }}</div>
        <div class="dialog-actions"><AppButton variant="ghost" :disabled="acting" @click="closeDialog">取消</AppButton><AppButton variant="primary" :disabled="acting || conflict.active" @click="confirmDialog">{{ acting ? '处理中…' : dialog.confirmText }}</AppButton></div>
      </section>
    </div>
  </ModulePageShell>
</template>

<script>
import { formatDateTime } from '@/utils/dateUtils'
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppInlineAlert } from '@/components/common'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { fileSdk } from '@/services/file/fileSdk'
import ActionReceipt from './components/ActionReceipt.vue'
import { isConflict, captureConflict, emptyConflict } from '@/modules/internship/composables/conflictGuard'
import { complianceApi } from '@/modules/internship/api/compliance.api'
import { getPermissionPatterns } from '@/security/permissionGate'

// Tab key → 懒加载分组 key；'overview' 不对应任何分组（用 batchStats 的 drilldowns）。
const TAB_GROUP = {
  consents: 'consents', safety: 'safety', filings: 'filings',
  incidents: 'incidents', exemptions: 'exemptions', evidence: 'evidence'
}

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
const COMPLIANCE_STATUS_LABELS = {
  DRAFT: '草稿', ACTIVE: '已启用', RETIRED: '已停用', PENDING: '待完成', PASSED: '已通过', FAILED: '未通过',
  EXPIRED: '已过期', NOT_REQUIRED: '无需备案', PENDING_COLLEGE: '待学院审核', PENDING_SCHOOL: '待学校审核',
  APPROVED: '已通过', REJECTED: '已驳回', WITHDRAWN: '已撤回', SUPERSEDED: '已被新版本替代',
  REPORTED: '已上报', EMERGENCY_HANDLING: '应急处置中', INVESTIGATING: '调查中', RECTIFYING: '整改中',
  PENDING_REVIEW: '待复核', CLOSED: '已关闭', REVOKED: '已撤销', READY: '可导出',
  READY_WITH_MISSING: '可导出（有缺项）', INVALIDATED: '已失效', LEGACY_SUMMARY: '历史汇总'
}

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
    showScore: false, score: 100, showInvestigation: false, showEvidenceUpload: false,
    investigationConclusion: '', rectificationPlan: '', responsibilityConclusion: '', fileIds: []
  }
}

export default {
  name: 'InternshipComplianceView',
  components: { ModulePageShell, LoadingState, ErrorState, AppButton, AppInlineAlert, ActionReceipt },
  props: { ctx: { type: Object, required: true } },
  data: () => ({
    loading: false, acting: false, error: '', activeTab: 'overview', consentError: '', safetyError: '', filingError: '', incidentError: '', emergencyError: '', exemptionError: '', packageError: '', emergencyDraft: null, filingDraft: null, reviewError: '',
    stats: {}, workbench: {}, auditHealth: null, auditHealthError: '', auditHealthLoading: false, auditHealthSeq: 0, selectedFilter: 'ALL', forms: freshForms(),
    filingTypes: FILING_TYPES, exemptionChecks: EXEMPTION_CHECKS,
    dialog: emptyDialog(), dialogError: '', conflict: emptyConflict(), lastReceipt: null,
    consentDelivery: { id: '', message: '', error: false, blockedVersion: null },
    // 首屏只拉 summary + 6 个统计数字；哪个 Tab 打开过、明细分组才会被拉过一次并缓存在这里。
    loadedGroups: new Set(), groupLoading: false, groupError: '',
    // 只允许当前 Tab 发起的最新分组请求控制 loading/error；旧 Tab 的请求可以回填缓存，但不能污染当前 UI。
    groupRequestSeq: 0, activeGroupRequest: '',
    // batchStats 还提供跨业务 Tab 共用的学生选择项；失败时台账仍可读，但依赖学生选择的新建动作必须显式停用。
    statsError: '',
    // 每次 load()（含切批次）自增；分组请求回来时比对，丢弃属于上一轮的响应，
    // 否则切批次时在途的旧请求会把上一个批次的台账并进当前视图。
    loadSeq: 0
  }),
  computed: {
    auditNotice() {
      if (this.auditHealthError) return {
        type: 'warning', title: '暂未取得审计状态',
        description: `${this.auditHealthError}。当前无法确认审计是否正常，可重新检查；学生条件与台账仍可查看。`
      }
      if (this.auditHealth?.healthy === false) {
        const details = []
        if (this.auditHealth.stalled) details.push(`待处理 ${this.auditHealth.backlog} 条，已有记录等待超过 1 小时`)
        if (this.auditHealth.dead > 0) details.push(`处理失败 ${this.auditHealth.dead} 条`)
        return {
          type: 'danger', title: '审计处理异常',
          description: `${details.join('；') || '审计队列未恢复正常'}。请联系系统管理员处理，恢复后重新检查；高风险办理仍由系统校验。`
        }
      }
      if (this.auditHealthLoading) return {
        type: 'info', title: '正在检查审计状态', description: '学生条件与台账可继续查看。'
      }
      return null
    },
    reviewRequested() { return ['safety', 'filings', 'incidents', 'exemptions'].includes(this.$route.query.tab) && this.$route.query.reviewId != null },
    exemptionEditor() { return this.activeTab === 'exemptions' && this.$route.query.form === 'exemption' },
    incidentEditor() { return this.activeTab === 'incidents' && ['incident', 'emergency'].includes(this.$route.query.form) ? this.$route.query.form : '' },
    filingEditor() { return this.activeTab === 'filings' && this.$route.query.form === 'filing' },
    safetyEditor() { return this.activeTab === 'safety' && this.$route.query.form === 'safety' },
    consentEditor() { return this.activeTab === 'consents' && this.$route.query.form === 'consent' },
    batchStore() { return useInternshipBatchStore() },
    metrics() { return this.stats.metrics || [] },
    students() { return this.stats.drilldowns?.ALL || [] },
    overviewMetrics() { return this.metrics.filter(item => ['TOTAL', 'ONBOARD_READY', 'BLOCKED', 'ARCHIVE_READY', 'ARCHIVE_BLOCKED'].includes(item.metricCode)) },
    incidentRows() {
      const rows = [...(this.workbench.incidents || [])]
      const focusId = String(this.$route.query.id || '')
      return focusId ? rows.sort((a, b) => Number(String(b.id) === focusId) - Number(String(a.id) === focusId)) : rows
    },
    selectedMetric() { return this.metrics.find((item) => item.drilldownFilter === this.selectedFilter) },
    drilldownRows() { return this.stats.drilldowns?.[this.selectedFilter] || [] },
    nowLocal() {
      const date = new Date(Date.now() - new Date().getTimezoneOffset() * 60000)
      return date.toISOString().slice(0, 16)
    },
    consentFormValid() {
      const form = this.forms.consent
      return !this.statsError && !!form.internshipId && form.contentVersion.trim().length >= 2 && form.contentSnapshot.trim().length >= 20
    },
    safetyFormValid() {
      const form = this.forms.safety
      return form.title.trim().length >= 2 && form.courseVersion.trim().length >= 1 && form.contentSnapshot.trim().length >= 20 && Number(form.requiredMinutes) >= 1 && Number(form.requiredMinutes) <= 1440 && Number(form.passingScore) >= 1 && Number(form.passingScore) <= 100 && Number(form.maxAttempts) >= 1 && Number(form.maxAttempts) <= 20
    },
    filingFormValid() {
      const form = this.forms.filing
      const riskRequired = ['HIGH_RISK', 'NIGHT_SHIFT', 'OVERSEAS', 'MINOR'].includes(form.filingType)
      return !this.statsError && !!form.internshipId && form.triggerReason.trim().length >= 5 && (!riskRequired || form.riskDescription.trim().length >= 5) && form.fileIds.length > 0
    },
    incidentFormValid() {
      const form = this.forms.incident
      return !this.statsError && !!form.internshipId && !!form.occurredAt && form.occurredAt <= this.nowLocal && form.incidentType.trim().length >= 2 && form.location.trim().length >= 2 && form.summary.trim().length >= 5 && form.emergencyAction.trim().length >= 5
    },
    emergencyFormValid() {
      const form = this.forms.emergency
      return form.planName.trim().length >= 2 && form.responsiblePerson.trim().length >= 2 && /^[0-9+\-()\s]{7,30}$/.test(form.emergencyContact) && form.responseSteps.trim().length >= 10 && form.fileIds.length > 0
    },
    exemptionFormValid() {
      const form = this.forms.exemption
      return !this.statsError && !!form.internshipId && !!form.checkCode && form.reason.trim().length >= 10 && !!form.validUntil && form.validUntil > this.nowLocal && form.evidenceFileIds.length > 0
    },
    packageFormValid() {
      return this.forms.package.packageType === 'BATCH' || (!this.statsError && !!this.forms.package.targetId)
    },
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
    },
    tabGroups() {
      const tabs = Object.fromEntries(this.tabs.map((item) => [item.key, item]))
      return [
        { key: 'onboard', label: '上岗门禁', items: [tabs.overview, tabs.consents, tabs.safety, tabs.filings] },
        { key: 'incident', label: '事故处置', items: [tabs.incidents] },
        { key: 'exception', label: '例外审批', items: [tabs.exemptions] },
        { key: 'evidence', label: '监管留痕', items: [tabs.evidence] }
      ]
    }
  },
  watch: {
    '$route.fullPath': { immediate: true, handler() { this.restoreReview() } },
    '$route.query.tab': {
      immediate: true,
      handler(value) {
        const next = value && Object.prototype.hasOwnProperty.call(TAB_GROUP, value) ? value : 'overview'
        if (this.activeTab !== next) this.activeTab = next
      }
    },
    '$route.query.filter': { immediate: true, handler(value) { this.selectedFilter = typeof value === 'string' ? value : 'ALL' } },
    'batchStore.selectedBatchId': { immediate: true, handler() { this.consentDelivery = { id: '', message: '', error: false, blockedVersion: null }; this.forms = freshForms(); this.consentError = ''; this.safetyError = ''; this.filingError = ''; this.incidentError = ''; this.emergencyError = ''; this.exemptionError = ''; this.packageError = ''; this.emergencyDraft = null; this.filingDraft = null; this.dialog = emptyDialog(); this.reviewError = ''; this.load() } },
    async activeTab(tab) { await this.ensureGroupLoaded(tab); this.restoreReview() }
  },
  beforeUnmount() { this.loadSeq++; this.auditHealthSeq++; this.groupRequestSeq++ },
  methods: {
    async loadAuditHealth() {
      if (this.auditHealthLoading || !this.batchStore.selectedBatchId) return
      const seq = ++this.auditHealthSeq
      const loadSeq = this.loadSeq
      const batchId = this.batchStore.selectedBatchId
      const current = () => seq === this.auditHealthSeq && loadSeq === this.loadSeq && batchId === this.batchStore.selectedBatchId
      this.auditHealthLoading = true
      this.auditHealthError = ''
      try {
        const result = await complianceApi.auditHealth()
        if (!current()) return
        if (result?.code !== 0 || typeof result.data?.healthy !== 'boolean') {
          throw new Error(result?.message && result.code !== 0 ? result.message : '审计状态返回不完整')
        }
        this.auditHealth = result.data
      } catch (error) {
        if (!current()) return
        this.auditHealth = null
        this.auditHealthError = error?.message || '审计状态读取失败'
      } finally { if (current()) this.auditHealthLoading = false }
    },
    closeReview() {
      if (this.acting) return
      this.dialog = emptyDialog(); this.dialogError = ''; this.conflict = emptyConflict(); this.reviewError = ''
      const query = { ...this.$route.query }; delete query.reviewId; delete query.reviewAction; delete query.reviewLevel; delete query.reviewKind
      this.$router.push({ path: this.$route.path, query })
    },
    restoreReview() {
      this.reviewError = ''
      if (!this.reviewRequested) {
        if (['safety-review', 'filing-review', 'incident-transition', 'emergency-review', 'exemption-review'].includes(this.dialog.kind)) this.dialog = emptyDialog()
        return
      }
      const tab = this.$route.query.tab
      if (!this.loadedGroups.has(tab) || this.loading || this.groupLoading) return
      const id = String(this.$route.query.reviewId)
      const action = this.$route.query.reviewAction
      const level = tab === 'filings' ? this.$route.query.reviewLevel : ''
      const kind = tab === 'exemptions' ? 'exemption-review' : tab === 'incidents' ? this.$route.query.reviewKind : tab === 'safety' ? 'safety-review' : 'filing-review'
      if (this.dialog.open && this.dialog.kind === kind && String(this.dialog.row?.id) === id && this.dialog.action === action && this.dialog.level === level) return
      this.dialog = emptyDialog()
      if (tab === 'exemptions') {
        const row = (this.workbench.exemptions || []).find(item => String(item.id) === id)
        if (!row) { this.reviewError = '记录不存在或不在当前批次的可见范围。'; return }
        if (!this.can('internship.compliance.exempt.approve')) { this.reviewError = '当前身份没有豁免审核权限。'; return }
        if (row.status !== 'PENDING_REVIEW' || !['APPROVE', 'REJECT'].includes(action)) { this.reviewError = '申请状态或审核动作已变化，请返回台账核对。'; return }
        this.openAction(kind, row, action, '', true)
        return
      }
      if (tab === 'incidents') {
        if (!['incident-transition', 'emergency-review'].includes(kind)) { this.reviewError = '办理链接参数不完整，请从台账重新打开。'; return }
        const row = (this.workbench[this.conflictCollection(kind)] || []).find(item => String(item.id) === id)
        if (!row) { this.reviewError = '记录不存在或不在当前批次的可见范围。'; return }
        if (!this.can('internship.incident.handle') || action === 'CLOSED' && !this.can('internship.incident.close')) { this.reviewError = '当前身份没有此操作的办理权限。'; return }
        const allowed = kind === 'incident-transition' ? this.incidentTargets(row).includes(action) && (action !== 'CLOSED' || row.closeAllowed) : row.status === 'PENDING_REVIEW' && ['APPROVE', 'REJECT'].includes(action)
        if (!allowed) { this.reviewError = '记录状态或办理条件已变化，请返回台账核对下一步。'; return }
        this.openAction(kind, row, action, '', true)
        return
      }
      if (!['APPROVE', 'REJECT'].includes(action) || tab === 'filings' && !['COLLEGE', 'SCHOOL'].includes(level)) { this.reviewError = '审核链接参数不完整，请从台账重新打开。'; return }
      const row = (this.workbench[this.conflictCollection(kind)] || []).find(item => String(item.id) === id)
      if (!row) { this.reviewError = '记录不存在或不在当前批次的可见范围。'; return }
      if (!this.can(tab === 'safety' ? 'internship.safety.manage' : 'internship.filing.review')) { this.reviewError = '当前身份没有此记录的审核权限。'; return }
      const expectedStatus = tab === 'safety' ? 'PENDING_REVIEW' : level === 'COLLEGE' ? 'PENDING_COLLEGE' : 'PENDING_SCHOOL'
      if (row.status !== expectedStatus) { this.reviewError = `记录已变为“${this.complianceStatusText(row.status)}”，请返回台账查看下一步。`; return }
      this.openAction(kind, row, action, level, true)
    },
    async previewReviewFile(fileId) {
      try { await fileSdk.preview(String(fileId)) } catch (error) { this.dialogError = error.message || '材料暂时无法预览，请重试' }
    },
    openExemptionEditor() { this.$router.push({ path: this.$route.path, query: { ...this.$route.query, tab: 'exemptions', form: 'exemption' } }) },
    closeExemptionEditor() { if (this.acting) return; const query = { ...this.$route.query }; delete query.form; this.$router.push({ path: this.$route.path, query }) },
    openIncidentEditor(form) { this.$router.push({ path: this.$route.path, query: { ...this.$route.query, tab: 'incidents', form } }) },
    closeIncidentEditor() { if (this.acting) return; const query = { ...this.$route.query }; delete query.form; this.$router.push({ path: this.$route.path, query }) },
    openFilingEditor() { this.$router.push({ path: this.$route.path, query: { ...this.$route.query, tab: 'filings', form: 'filing' } }) },
    closeFilingEditor() { const query = { ...this.$route.query }; delete query.form; this.$router.push({ path: this.$route.path, query }) },
    openSafetyEditor() { this.$router.push({ path: this.$route.path, query: { ...this.$route.query, tab: 'safety', form: 'safety' } }) },
    closeSafetyEditor() { const query = { ...this.$route.query }; delete query.form; this.$router.push({ path: this.$route.path, query }) },
    openConsentEditor() { this.$router.push({ path: this.$route.path, query: { ...this.$route.query, tab: 'consents', form: 'consent' } }) },
    closeConsentEditor() { const query = { ...this.$route.query }; delete query.form; this.$router.push({ path: this.$route.path, query }) },
    goTab(tab) { const query = { ...this.$route.query, tab }; delete query.id; delete query.form; this.$router.push({ path: this.$route.path, query }) },
    selectFilter(filter) { this.selectedFilter = filter; this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, filter } }) },
    can(permission) {
      const patterns = getPermissionPatterns() || []
      return patterns.includes('*') || patterns.some((pattern) => pattern === permission || (pattern.endsWith('.*') && permission.startsWith(pattern.slice(0, -1))))
    },
    fmt: formatDateTime,
    fileText(ids) { return ids?.length ? `已上传 ${ids.length} 个文件` : '尚未上传' },
    blockerText(items) { return items?.length ? items.map((item) => `${item.label}：${item.reason}`).join('；') : '无' },
    blockerOwner(codes) {
      const owners = {
        enterpriseAccess: '企业准入经办人', studentConsent: '学生本人', guardianConsent: '已绑定监护人',
        safetyEducation: '学生与安全教育审核人', insurance: '保险核验经办人', agreement: '协议当前确认方',
        specialFiling: '学院 / 学校备案审核人', workRights: '岗位审核经办人', emergency: '应急预案责任人'
      }
      return (codes || []).map((code) => owners[code] || '合规经办人').filter((value, index, all) => all.indexOf(value) === index).join('、') || '合规经办人'
    },
    filingTypeText(value) { return FILING_TYPES.find((item) => item.value === value)?.label || (value ? '其他备案类型' : '-') },
    exemptionCheckText(value) { return EXEMPTION_CHECKS.find((item) => item.value === value)?.label || (value ? '其他检查项' : '-') },
    complianceStatusText(value) { return COMPLIANCE_STATUS_LABELS[value] || (value ? '状态待确认' : '-') },
    severityText(value) { return ({ LOW: '一般', MEDIUM: '较大', HIGH: '重大', CRITICAL: '特别重大' })[value] || '程度待确认' },
    packageTypeText(value) { return ({ BATCH: '批次包', STUDENT: '学生包' })[value] || '其他证据包' },
    consentStatusText(value) { return ({ PENDING: '待确认', VALID: '已确认', REJECTED: '已拒绝', EXPIRED: '已过期', SUPERSEDED: '已被新版本替代', REVOKED: '已作废', NOT_APPLICABLE: '无需确认' })[value] || (value ? '确认状态待核实' : '-') },
    deliveryStatusText(value) { return ({ SENT: '已发送', SKIPPED: '未发送', FAILED: '发送失败', NOT_SENT: '尚未发送', NOT_REQUIRED: '无需发送' })[String(value || '').toUpperCase()] || (value ? '发送状态待确认' : '尚未发送') },
    deliveryTone(value) { const status = String(value || '').toUpperCase(); return status === 'SENT' ? 'is-success' : ['SKIPPED', 'FAILED'].includes(status) ? 'is-danger' : 'is-muted' },
    stateTone(value) { return value === 'VALID' || value === 'APPROVED' ? 'is-success' : ['REJECTED', 'REVOKED', 'EXPIRED'].includes(value) ? 'is-danger' : value === 'PENDING' ? 'is-warn' : 'is-muted' },
    incidentTargetText(value) { return ({ EMERGENCY_HANDLING: '进入应急处置', INVESTIGATING: '进入调查', RECTIFYING: '进入整改', PENDING_REVIEW: '提交复核', CLOSED: '关闭事故' })[value] || '更新事故状态' },
    /** 首屏：只拉批次统计 + 工作台 summary（6 项数字走 SQL COUNT），不拉任何分组明细。
     * 明细列表改为按 Tab 懒加载，见 ensureGroupLoaded。
     *
     * 三个并发请求不是同一个故障域：summary 负责各业务 Tab 的计数，分组接口负责台账明细；
     * `batchStats` 负责总览指标/下钻，并提供知情、备案、事故、豁免、学生证据包共用的学生选择项。
     * 因此 stats 失败时不能把整页判死，也不能让其他 Tab 假装可正常新建：现有台账和审批继续可用，
     * 依赖学生选择的新建动作会显示告警并停用，直到 stats 重试成功。 */
    async load() {
      // 先自增，让所有在途的分组请求立即作废（含"没选批次"这条早退路径）。
      const seq = ++this.loadSeq
      this.auditHealthSeq++; this.auditHealth = null; this.auditHealthError = ''; this.auditHealthLoading = false
      this.activeGroupRequest = ''; this.groupError = ''; this.groupLoading = false
      const batchId = this.batchStore.selectedBatchId
      if (!batchId) {
        this.stats = {}; this.workbench = {}; this.loadedGroups = new Set()
        this.statsError = ''; this.error = ''; this.loading = false
        return
      }
      this.loading = true; this.error = ''; this.statsError = ''
      this.loadAuditHealth()
      try {
        const [statsRes, summary] = await Promise.all([
          complianceApi.batchStats(batchId), complianceApi.workbenchSummary(batchId)
        ])
        if (seq !== this.loadSeq || batchId !== this.batchStore.selectedBatchId) return
        if (summary.code !== 0) throw new Error(summary.message || '合规工作台加载失败')
        if (statsRes.code !== 0) {
          this.stats = {}
          this.statsError = statsRes.message || '合规总览统计加载失败'
        } else {
          this.stats = statsRes.data || {}
        }
        // 旧分组明细一律作废重拉：批次切换或动作后台账可能已变，缓存的分组不可信。
        this.workbench = summary.data || {}
        this.loadedGroups = new Set()
        if (!this.stats.drilldowns?.[this.selectedFilter]) this.selectedFilter = 'ALL'
        await this.ensureGroupLoaded(this.activeTab)
        this.restoreReview()
      } catch (loadError) {
        if (seq !== this.loadSeq) return
        this.error = loadError.message || '合规工作台加载失败'
      } finally { if (seq === this.loadSeq) { this.loading = false; this.restoreReview() } }
    },
    /** 明细尚未到达（加载中）或加载失败时，不能显示「暂无 XX」——那等于告诉老师
     * "这里没有数据"，而系统其实还不知道、或者根本没取到。合规台账尤其不能这样骗人。 */
    showEmpty(list) {
      return !this.groupLoading && !this.groupError && !(list || []).length
    },
    /** 点开哪个 Tab 才请求哪组明细；已加载过（且未被 load() 作废）的分组不重复请求。 */
    async ensureGroupLoaded(tab) {
      const group = TAB_GROUP[tab]
      const batchId = this.batchStore.selectedBatchId
      // 切到总览、无批次、或已加载分组时，当前 Tab 没有在途请求；立即释放共享 UI 状态。
      // 旧 Tab 的请求即使随后返回，也因为失去 activeGroupRequest 所有权，不能再改当前 loading/error。
      if (!group || !batchId || this.loadedGroups.has(group)) {
        this.activeGroupRequest = ''; this.groupError = ''; this.groupLoading = false
        return
      }
      const seq = this.loadSeq
      const requestId = ++this.groupRequestSeq
      const requestKey = `${seq}:${batchId}:${group}:${requestId}`
      this.activeGroupRequest = requestKey
      const staleData = () => seq !== this.loadSeq || batchId !== this.batchStore.selectedBatchId
      const ownsUi = () => !staleData() && this.activeGroupRequest === requestKey && TAB_GROUP[this.activeTab] === group
      this.groupLoading = true; this.groupError = ''
      try {
        const res = await complianceApi.workbenchGroup(batchId, group)
        // 切批次/刷新后的响应属于上一轮，数据也必须丢弃；同批次旧 Tab 的响应可以回填该分组缓存，
        // 但 loading/error 只允许当前 Tab 的最新请求通过 ownsUi() 控制。
        if (staleData()) return
        if (res.code !== 0) throw new Error(res.message || '分组明细加载失败')
        this.workbench = { ...this.workbench, ...(res.data || {}) }
        this.loadedGroups.add(group)
      } catch (groupErrorObj) {
        if (staleData()) return
        if (ownsUi()) this.groupError = groupErrorObj.message || '分组明细加载失败'
      } finally {
        if (ownsUi()) this.groupLoading = false
      }
    },
    /** 错误横幅上的「重试」：重新拉当前 Tab 的明细。 */
    reloadActiveGroup() {
      this.groupError = ''
      this.loadedGroups.delete(TAB_GROUP[this.activeTab])
      return this.ensureGroupLoaded(this.activeTab)
    },
    openStudent(row) { this.$router.push({ path: `/admin/internship/students/${row.internshipId}`, query: { batchId: String(this.batchStore.selectedBatchId), returnTo: this.$route.fullPath } }) },
    needsIdentityCorrection(row) {
      return !!row.studentId && row.blockers?.some(item => item.code === 'guardianConsent' && item.reason?.startsWith('出生日期待核实'))
    },
    openIdentityCorrection(row) {
      if (!this.needsIdentityCorrection(row) || !this.can('academicAffairs.roster.correction.view') || !this.can('academicAffairs.roster.correction.apply')) return
      this.$router.push({ path: '/admin/academic-affairs/roster/corrections', query: {
        studentId: String(row.studentId), fieldKey: 'ID_CARD', returnTo: this.$route.fullPath
      } })
    },
    async run(resultPromise, successMessage, { resetForm = '', onConflict = null, onError = null } = {}) {
      if (this.acting) return false
      this.acting = true
      try {
        const result = await resultPromise
        // 撞车（409）单独走 onConflict：弹窗要留着、老师填的长文本要留着，
        // 所以不能把它降级成一个一闪而过的错误 toast。
        if (onConflict && isConflict(result)) { await onConflict(result); return false }
        if (result.code !== 0) throw new Error(result.message || '操作失败')
        const data = result.data || {}
        this.lastReceipt = data.id ? {
          id: data.id, version: data.version, actionLabel: successMessage,
          objectLabel: `合规对象 ${data.id}`, status: data.status,
          statusLabel: this.complianceStatusText(data.status),
          auditText: '业务事实与审计 outbox 已在同一事务提交',
          nextStep: data.nextStep || (data.status === 'CLOSED' ? '生成监管证据包' : '继续当前责任链')
        } : this.lastReceipt
        this.$message?.success?.(successMessage)
        if (resetForm) this.forms[resetForm] = freshForms()[resetForm]
        await this.load()
        return true
      } catch (runError) {
        if (onError) onError(runError)
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
    async uploadDialogEvidence(event) {
      const file = event.target.files?.[0]
      if (!file) return
      if (file.size > 20 * 1024 * 1024) { event.target.value = ''; this.$message?.warning?.('单个文件不能超过20MB'); return }
      const result = await complianceApi.uploadEvidence(file, 'INTERNSHIP_INCIDENT')
      event.target.value = ''
      if (result.code !== 0) { this.$message?.error?.(result.message || '事故证据上传失败'); return }
      const fileId = result.data?.fileId || result.data?.id
      if (fileId) this.dialog.fileIds = [...new Set([...(this.dialog.fileIds || []), String(fileId)])]
    },
    async createConsent() {
      if (this.acting || !this.can('internship.consent.manage')) return
      this.consentError = ''
      if (!this.consentFormValid) { this.consentError = '请选择学生，正文版本不少于2字，完整正文不少于20字'; return }
      const form = { ...this.forms.consent, deliveryChannel: this.forms.consent.consentType === 'GUARDIAN' ? 'SMS' : 'PORTAL' }
      const succeeded = await this.run(complianceApi.createConsent(form), form.consentType === 'GUARDIAN' ? '监护人任务已创建，请查看送达结果' : '学生知情确认任务已下发', { resetForm: 'consent', onError: error => { this.consentError = error.message || '下发失败，请重试' } })
      if (succeeded) this.closeConsentEditor()
      else if (!this.consentError) this.consentError = '下发未完成，请核对提示后重试；已填写内容保留。'
    },
    async redeliverConsent(row) {
      if (this.acting || !this.can('internship.consent.manage') || row?.consentType !== 'GUARDIAN' || row.status !== 'PENDING' || !row.id) return
      const id = String(row.id)
      if (this.consentDelivery.id === id && this.consentDelivery.blockedVersion != null && this.consentDelivery.blockedVersion === row.version) return
      this.consentDelivery = { id, message: '', error: false, blockedVersion: null }
      if (row.version == null) {
        this.consentDelivery = { id, message: '任务版本缺失，请刷新核验后重试。', error: true, blockedVersion: null }
        return
      }
      const batchId = this.batchStore.selectedBatchId
      const seq = this.loadSeq
      const current = () => batchId === this.batchStore.selectedBatchId && seq === this.loadSeq
      this.acting = true
      try {
        const result = await complianceApi.redeliverConsent(id, row.version)
        if (!current()) return
        if (isConflict(result)) {
          this.consentDelivery = { id, message: '任务已变化，本次未重新发送。请刷新核验并核对最新任务后再办理。', error: true, blockedVersion: row.version }
          return
        }
        if (result.code !== 0) throw new Error(result.message || '重新发送失败，请重试。')
        const sent = result.data?.deliveryStatus === 'SENT'
        this.consentDelivery = {
          id, error: !sent, blockedVersion: null,
          message: sent
            ? `任务 ${id}：新链接已发送，旧链接已失效；请监护人使用最新短信，由本人完成确认。`
            : `任务 ${id}：链接已更新，但短信未确认送达。${result.data?.deliveryReason || '请核对台账中的送达情况后重试。'}`
        }
        await this.load()
      } catch (error) {
        if (current()) this.consentDelivery = { id, message: `${error.message || '重新发送失败'} 请先刷新核对送达结果，再决定是否重试。`, error: true, blockedVersion: null }
      } finally { this.acting = false }
    },
    async createSafetyCourse() {
      if (this.acting || !this.can('internship.safety.manage')) return
      this.safetyError = ''
      if (!this.safetyFormValid) { this.safetyError = '请检查课程名称、版本、正文、时长、分数和尝试次数'; return }
      const succeeded = await this.run(complianceApi.createSafetyCourse({ ...this.forms.safety, batchId: this.batchStore.selectedBatchId, status: 'ACTIVE' }), '安全课程已创建', { resetForm: 'safety', onError: error => { this.safetyError = error.message || '课程保存失败，请重试' } })
      if (succeeded) this.closeSafetyEditor()
    },
    async createFiling() {
      if (this.acting || !this.can('internship.filing.review')) return
      this.filingError = ''
      if (!this.filingDraft && !this.filingFormValid) { this.filingError = '请完整填写备案原因、必要风险说明并上传依据附件'; return }
      const batchId = this.batchStore.selectedBatchId
      this.acting = true
      try {
        if (!this.filingDraft) {
          const created = await complianceApi.createFiling({ ...this.forms.filing, fileIds: [...this.forms.filing.fileIds] })
          if (batchId !== this.batchStore.selectedBatchId) return
          if (created.code !== 0) throw new Error(created.message || '特殊备案创建失败')
          this.filingDraft = { id: String(created.data.id), version: created.data.version }
        }
        const submitted = await complianceApi.reviewFiling(this.filingDraft.id, 'COLLEGE', 'submit', { expectedVersion: this.filingDraft.version })
        if (batchId !== this.batchStore.selectedBatchId) return
        if (submitted.code !== 0) throw new Error(submitted.message || '特殊备案提交失败')
        this.$message?.success?.('特殊备案已提交学院审核')
        this.forms.filing = freshForms().filing
        this.filingDraft = null
        await this.load()
        this.closeFilingEditor()
      } catch (createError) {
        if (batchId === this.batchStore.selectedBatchId) this.filingError = createError.message || '特殊备案办理失败'
      } finally { this.acting = false }
    },
    filingAction(row, level, action) { this.run(complianceApi.reviewFiling(row.id, level, action, { expectedVersion: row.version }), '备案状态已更新') },
    async reportIncident() {
      if (this.acting || !this.can('internship.incident.report')) return
      this.incidentError = ''
      if (!this.incidentFormValid) { this.incidentError = this.statsError ? '学生选择暂不可用，请先重试合规统计' : '请完整填写事故情况与应急措施'; return }
      const succeeded = await this.run(complianceApi.reportIncident({ ...this.forms.incident, idempotencyKey: `pc-${Date.now()}-${Math.random().toString(36).slice(2)}` }), '事故已上报', { resetForm: 'incident', onError: error => { this.incidentError = error.message || '事故上报失败，请核对后重试' } })
      if (succeeded) this.closeIncidentEditor()
    },
    incidentTargets(row) {
      const targets = ({ REPORTED: ['EMERGENCY_HANDLING', 'INVESTIGATING'], EMERGENCY_HANDLING: ['INVESTIGATING'], INVESTIGATING: ['RECTIFYING', 'PENDING_REVIEW'], RECTIFYING: ['PENDING_REVIEW'], PENDING_REVIEW: ['CLOSED'] })[row.status] || []
      return targets
    },
    generateIncidentEvidence(row) {
      const target = row.evidenceTarget || {}
      return this.run(complianceApi.generateEvidencePackage(target.packageType, target.targetId), '事故监管证据包已生成')
    },
    async createEmergency() {
      if (this.acting || !this.can('internship.incident.handle')) return
      this.emergencyError = ''
      if (!this.emergencyDraft && !this.emergencyFormValid) { this.emergencyError = '请检查预案名称、责任人、联系电话、处置步骤和附件'; return }
      const batchId = this.batchStore.selectedBatchId
      this.acting = true
      let succeeded = false
      try {
        if (!this.emergencyDraft) {
          const created = await complianceApi.createEmergencyPlan({ ...this.forms.emergency, fileIds: [...this.forms.emergency.fileIds], batchId })
          if (batchId !== this.batchStore.selectedBatchId) return
          if (created.code !== 0) throw new Error(created.message || '应急预案创建失败')
          this.emergencyDraft = { id: String(created.data.id), version: created.data.version }
        }
        const submitted = await complianceApi.reviewEmergencyPlan(this.emergencyDraft.id, 'SUBMIT', { expectedVersion: this.emergencyDraft.version })
        if (batchId !== this.batchStore.selectedBatchId) return
        if (submitted.code !== 0) throw new Error(submitted.message || '应急预案提交失败，请返回台账核对后重试')
        this.$message?.success?.('应急预案已提交审核')
        this.forms.emergency = freshForms().emergency
        this.emergencyDraft = null
        succeeded = true
        await this.load()
      } catch (createError) {
        if (batchId === this.batchStore.selectedBatchId) this.emergencyError = createError.message || '应急预案办理失败'
      } finally { this.acting = false }
      if (succeeded && batchId === this.batchStore.selectedBatchId) this.closeIncidentEditor()
    },
    emergencyAction(row, action) { this.run(complianceApi.reviewEmergencyPlan(row.id, action, { expectedVersion: row.version }), '应急预案状态已更新') },
    async requestExemption() {
      if (this.acting || !this.can('internship.compliance.exempt.request')) return
      this.exemptionError = ''
      if (!this.exemptionFormValid) { this.exemptionError = this.statsError ? '学生选择暂不可用，请先重试合规统计' : '请补齐检查项、申请原因、有效期及依据附件'; return }
      const ok = await this.run(complianceApi.grantExemption({ ...this.forms.exemption, evidenceFileIds: [...this.forms.exemption.evidenceFileIds] }), '豁免申请已提交学校审批', { resetForm: 'exemption', onError: error => { this.exemptionError = error.message || '申请未完成，请核对后重试' } })
      if (ok) this.closeExemptionEditor()
    },
    async generatePackage() {
      if (this.acting || !this.can('internship.evidence.export')) return
      this.packageError = ''
      if (!this.packageFormValid) { this.packageError = this.forms.package.packageType === 'STUDENT' && this.statsError ? '学生选择暂不可用，请先重试合规统计' : '请选择证据包目标'; return }
      const targetId = this.forms.package.packageType === 'BATCH' ? this.batchStore.selectedBatchId : this.forms.package.targetId
      return this.run(complianceApi.generateEvidencePackage(this.forms.package.packageType, targetId), '证据包生成请求已完成，请核对历史记录中的状态和缺项', { onError: error => { this.packageError = error.message || '生成失败，请重试' } })
    },
    async downloadPackage(row) {
      try { await complianceApi.downloadEvidencePackage(row.id, `岗位实习_${row.packageType}_v${row.packageVersion}.zip`) }
      catch (downloadError) { this.$message?.error?.(downloadError.message || '下载失败') }
    },
    openAction(kind, row, action = '', level = '', fromRoute = false) {
      const dialog = emptyDialog()
      dialog.open = true; dialog.kind = kind; dialog.row = { ...row, fileIds: [...(kind === 'exemption-review' ? row.evidenceFileIds || [] : row.fileIds || [])] }; dialog.action = action; dialog.level = level
      if (kind === 'revoke-consent') { dialog.title = '作废知情确认任务'; dialog.description = '作废后学生或监护人无法再确认，必须重新下发新任务。'; dialog.commentLabel = '作废原因（至少5字）'; dialog.commentPlaceholder = '说明作废原因'; dialog.confirmText = '确认作废' }
      if (kind === 'safety-review') { dialog.title = action === 'APPROVE' ? '通过安全教育审核' : '退回安全教育记录'; dialog.showScore = action === 'APPROVE'; dialog.commentLabel = action === 'APPROVE' ? '审核备注（可选）' : '退回原因（至少5字）'; dialog.confirmText = action === 'APPROVE' ? '确认通过' : '确认退回' }
      if (kind === 'filing-review') { dialog.title = `${level === 'SCHOOL' ? '学校' : '学院'}${action === 'APPROVE' ? '通过' : '退回'}特殊备案`; dialog.commentLabel = action === 'APPROVE' ? '审核意见（可选）' : '退回原因（至少5字）'; dialog.confirmText = action === 'APPROVE' ? '确认通过' : '确认退回' }
      if (kind === 'incident-transition') { dialog.title = this.incidentTargetText(action); dialog.showInvestigation = ['PENDING_REVIEW', 'CLOSED'].includes(action); dialog.showEvidenceUpload = action === 'CLOSED'; dialog.investigationConclusion = row.investigationConclusion || ''; dialog.rectificationPlan = row.rectificationPlan || ''; dialog.responsibilityConclusion = row.responsibilityConclusion || ''; dialog.fileIds = [...(row.fileIds || [])]; dialog.commentLabel = '流转说明（可选）'; dialog.confirmText = '确认流转' }
      if (kind === 'emergency-review') { dialog.title = action === 'APPROVE' ? '通过应急预案' : '退回应急预案'; dialog.commentLabel = action === 'APPROVE' ? '审核意见（可选）' : '退回原因（至少5字）'; dialog.confirmText = action === 'APPROVE' ? '确认通过' : '确认退回' }
      if (kind === 'exemption-review') { dialog.title = action === 'APPROVE' ? '批准合规豁免' : '拒绝合规豁免'; dialog.commentLabel = action === 'APPROVE' ? '批准意见（建议说明替代控制）' : '拒绝原因（至少5字）'; dialog.confirmText = action === 'APPROVE' ? '确认批准' : '确认拒绝' }
      this.dialog = dialog; this.dialogError = ''; this.conflict = emptyConflict()
      if (!fromRoute && ['safety-review', 'filing-review', 'incident-transition', 'emergency-review', 'exemption-review'].includes(kind)) {
        const query = { ...this.$route.query, tab: kind === 'safety-review' ? 'safety' : kind === 'filing-review' ? 'filings' : kind === 'exemption-review' ? 'exemptions' : 'incidents', reviewId: String(row.id), reviewAction: action }; delete query.form
        if (['incident-transition', 'emergency-review'].includes(kind)) query.reviewKind = kind; else delete query.reviewKind
        if (level) query.reviewLevel = level; else delete query.reviewLevel
        this.$router.push({ path: this.$route.path, query })
      }
    },
    closeDialog() { if (this.reviewRequested) return this.closeReview(); if (!this.acting) { this.dialog = emptyDialog(); this.dialogError = ''; this.conflict = emptyConflict() } },
    /** dialog.kind → workbench 台账集合，冲突后按 id 重新捞同一条的真值 */
    conflictCollection(kind) {
      return ({
        'revoke-consent': 'consents', 'safety-review': 'safetyCompletions', 'filing-review': 'filings',
        'incident-transition': 'incidents', 'emergency-review': 'emergencyPlans', 'exemption-review': 'exemptions'
      })[kind] || ''
    },
    /**
     * 撞车善后：重新拉台账，把这条记录的最新状态和版本摆出来。
     * 三段调查结论最长各 2000 字，绝不能因为一次 409 就让老师重敲——弹窗和输入全部留着。
     * 原审核快照不换版；当前操作禁用，重新打开最新台账记录后才能再次审核。
     */
    async onDialogConflict(res) {
      const dialog = this.dialog
      this.conflict = { ...emptyConflict(), active: true }
      const captured = await captureConflict({
        res,
        refresh: async () => { await this.load(); if (this.error || this.groupError) throw new Error(this.error || this.groupError) },
        latest: () => {
          const key = this.conflictCollection(this.dialog.kind)
          const rows = (key && this.workbench[key]) || []
          const fresh = rows.find((r) => String(r.id) === String(this.dialog.row?.id))
          if (!fresh) throw new Error('这条记录已不在当前台账里')
          return [
            { label: '最新状态', value: this.complianceStatusText(fresh.status) },
            { label: '最新版本', value: fresh.version }
          ]
        }
      })
      if (this.dialog === dialog) this.conflict = captured
    },
    async confirmDialog() {
      if (this.acting || !this.dialog.open || this.conflict.active) return
      const dialog = this.dialog
      const comment = dialog.comment.trim()
      if ((dialog.kind === 'revoke-consent' || dialog.action === 'REJECT') && comment.length < 5) { this.dialogError = '原因必须不少于5字'; return }
      if (dialog.showScore && (!Number.isFinite(Number(dialog.score)) || Number(dialog.score) < 0 || Number(dialog.score) > 100)) { this.dialogError = '审核分数必须为0至100'; return }
      if (dialog.showInvestigation && [dialog.investigationConclusion, dialog.rectificationPlan, dialog.responsibilityConclusion].some((value) => value.trim().length < 5)) { this.dialogError = '调查结论、整改方案、责任/复核结论均不少于5字'; return }
      let promise; let successMessage = '操作成功'
      if (dialog.kind === 'revoke-consent') { promise = complianceApi.revokeConsent(dialog.row.id, { expectedVersion: dialog.row.version, reason: comment }); successMessage = '知情任务已作废' }
      if (dialog.kind === 'safety-review') { promise = complianceApi.reviewSafetyCompletion(dialog.row.id, { action: dialog.action, score: dialog.showScore ? Number(dialog.score) : null, comment, expectedVersion: dialog.row.version }); successMessage = '安全教育审核完成' }
      if (dialog.kind === 'filing-review') { promise = complianceApi.reviewFiling(dialog.row.id, dialog.level, dialog.action.toLowerCase(), { expectedVersion: dialog.row.version, comment }); successMessage = '备案状态已更新' }
      if (dialog.kind === 'incident-transition') { promise = complianceApi.transitionIncident(dialog.row.id, { status: dialog.action, expectedVersion: dialog.row.version, comment, investigationConclusion: dialog.investigationConclusion, rectificationPlan: dialog.rectificationPlan, responsibilityConclusion: dialog.responsibilityConclusion, fileIds: dialog.fileIds }); successMessage = `事故已流转至${this.incidentTargetText(dialog.action)}` }
      if (dialog.kind === 'emergency-review') { promise = complianceApi.reviewEmergencyPlan(dialog.row.id, dialog.action, { expectedVersion: dialog.row.version, comment }); successMessage = '应急预案状态已更新' }
      if (dialog.kind === 'exemption-review') { promise = complianceApi.reviewExemption(dialog.row.id, { action: dialog.action, comment, expectedVersion: dialog.row.version }); successMessage = '豁免审批完成' }
      if (!promise) { this.dialogError = '未知操作，已阻止提交'; return }
      const ok = await this.run(promise, successMessage, { onConflict: (res) => this.onDialogConflict(res), onError: error => { this.dialogError = error.message || '审核未完成，请重试' } })
      if (ok) this.closeDialog()
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.evidence-generator { padding:20px 24px; }
.evidence-generator > .mp-card__head { padding:0 !important; }
.evidence-fields { padding:0; border:0; min-width:0; }
.evidence-hash { margin-top:8px; font-size:12px; }
.evidence-hash summary { cursor:pointer; color:var(--color-primary); }
.evidence-hash code { display:block; margin-top:8px; overflow-wrap:anywhere; line-height:1.6; }

.incident-editor { padding:24px; border:1px solid var(--card-b, #e5e7eb); border-radius:12px; }
.incident-editor > .mp-card__head { padding:0 !important; }
.incident-fields { min-width:0; border:0; padding:0; gap:20px; }
.incident-fields textarea { line-height:1.7; resize:vertical; }
.incident-ledger .mp-table { min-width:0; width:100%; table-layout:fixed; }
.incident-ledger th,.incident-ledger td { padding:14px 16px; overflow-wrap:anywhere; }
.incident-ledger .action-cell { white-space:normal; }
.incident-ledger .empty-cell { padding:42px 16px !important; }
.incident-blockers { color:var(--color-danger, #b42318); font-size:12px; line-height:1.6; margin-top:6px; }

.review-workspace { width:100%; }
.review-workspace .action-dialog { width:100%;max-height:none;box-sizing:border-box;box-shadow:none;border:1px solid var(--card-b, #e5e7eb);padding:24px;display:grid;grid-template-columns:minmax(0,1fr) minmax(280px, .85fr);gap:18px 28px; }
.review-workspace .dialog-head { grid-column:1/-1;font-size:18px;padding-bottom:16px;border-bottom:1px solid var(--card-b, #e5e7eb); }
.review-workspace .review-context { grid-column:1;grid-row:2/7;margin:0;align-content:start; }
.review-workspace .action-dialog > label,.review-workspace .action-dialog > .dialog-error { grid-column:2; }
.review-workspace .dialog-actions { grid-column:1/-1;border-top:1px solid var(--card-b, #e5e7eb);padding-top:18px; }
.review-state { padding:24px 0; }
@media(max-width:1000px){.review-workspace .action-dialog{display:flex;}}

.review-context { display:grid;gap:6px;padding:16px;background:var(--bg, #f5f7fb);border:1px solid var(--card-b, #e5e7eb);border-radius:8px;margin:16px 0; }
.review-context p { margin:6px 0;font-size:13px;line-height:1.7;white-space:pre-wrap; }
.review-files { display:flex;gap:8px;flex-wrap:wrap; }
.review-latest { font-size:13px;display:flex;gap:20px; }.review-latest dd { margin:4px 0; }

.filing-editor { padding:24px;border:1px solid var(--card-b, #e5e7eb);border-radius:12px;background:var(--card, white); }
.filing-editor > .mp-card__head { padding:0 !important; }
.filing-fields { border:0;padding:0;min-width:0; }
.filing-ledger .mp-table { width:100%;min-width:0;table-layout:fixed; }
.filing-ledger th,.filing-ledger td { padding:14px 12px;vertical-align:top;overflow-wrap:anywhere; }
.filing-ledger .empty-cell { padding:60px 16px; }

.safety-editor { padding:24px; border:1px solid var(--card-b, #e5e7eb); border-radius:12px; background:var(--card, white); }
.safety-editor > .mp-card__head { padding:0 !important; }
.safety-ledger .mp-table { min-width:0; width:100%; table-layout:fixed; }
.safety-ledger th, .safety-ledger td { padding:14px 16px; vertical-align:top; overflow-wrap:anywhere; }
.safety-ledger th:first-child { width:23%; }
.safety-ledger .empty-cell { padding:40px 16px; }

.consent-editor { padding: 24px; border: 1px solid var(--card-b, #e5e7eb); border-radius: 12px; background: var(--card, white); }
.consent-editor > .mp-card__head { padding: 0 !important; }
.consent-fields { grid-template-columns: minmax(220px, 1.2fr) 1fr 1fr; gap: 20px; }
.consent-editor .consent-fields textarea { line-height: 1.8; padding: 16px; resize: vertical; }
.consent-actions { display: flex; justify-content: flex-end; gap: 10px; border-top: 1px solid var(--card-b, #e5e7eb); padding-top: 18px; }
.consent-destination { color: var(--t2, #475569); font-size: 13px; }
.consent-ledger .consent-table th, .consent-ledger .consent-table td { padding: 14px 16px; vertical-align: top; }
.consent-ledger .consent-table { min-width: 0; width: 100%; table-layout: fixed; } .consent-ledger .consent-table td { overflow-wrap: anywhere; } .consent-ledger .consent-table th:first-child { width: 21%; } .consent-ledger .empty-cell { padding: 70px 16px !important; }

.compliance-content { display:flex;flex-direction:column;gap:16px; }
.compliance-content > section > .mp-card__head { padding:16px 16px 0; }

.compliance-metrics { display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:1px;border:1px solid var(--card-b, #e5e7eb);border-radius:8px;background:var(--card-b, #e5e7eb);overflow:hidden; }
.compliance-metrics .metric-card { padding:12px 16px;border:0;border-bottom:2px solid transparent;background:white;display:flex;align-items:center;justify-content:space-between;gap:8px;min-width:0; }
.compliance-metrics .metric-card.is-active { outline:0;background:var(--color-primary-light,#eef4ff);border-bottom-color:var(--color-primary); }
.compliance-metrics .metric-card:focus-visible { outline:2px solid var(--color-primary);outline-offset:-3px; }
.compliance-metrics strong { font-size:22px;font-variant-numeric:tabular-nums; }
.compliance-updated { color:var(--t2, #475569);font-size:12px; }
.compliance-content > section > .roster-heading { padding:14px 16px;flex-wrap:wrap;border-bottom:1px solid var(--card-b, #e5e7eb); }
.roster-heading p { margin:4px 0 0; }
.compliance-filters { padding:0; }
.compliance-filters label { display: flex; align-items: center; gap: 12px; font-size: 13px; }
.compliance-filters select { min-width: 210px; padding: 8px; border: 1px solid var(--card-b, #e5e7eb); border-radius: 6px; color: inherit; background: white; }
.compliance-roster th, .compliance-roster td { padding: 14px 16px; vertical-align: top; text-align: left; }
.compliance-roster td:first-child { min-width: 150px; }
.compliance-roster td:last-child { width: 115px; }
.compliance-roster summary { cursor: pointer; color: var(--pri, #2563eb); }
.compliance-roster ul { padding-left: 18px; margin: 10px 0 0; max-width: 310px; font-size: 12px; line-height: 1.7; }

.workbench-head,.head-actions,.mp-card__head,.dialog-head,.dialog-actions{display:flex;align-items:center;justify-content:space-between;gap:16px}.workbench-head p{margin:5px 0 0}.status-pill,.tab-count{display:inline-flex;align-items:center;justify-content:center;border-radius:999px;background:var(--color-primary-light,#eef4ff);color:var(--color-primary);padding:3px 9px;font-size:12px}.work-tabs{display:flex;flex-wrap:wrap;gap:8px;padding:2px}.work-tab{border:1px solid var(--border-color);background:#fff;border-radius:8px;padding:9px 13px;cursor:pointer;white-space:nowrap}.work-tab.is-active{border-color:var(--color-primary);color:var(--color-primary);background:var(--color-primary-light,#eef4ff)}.tab-count{margin-left:5px;padding:1px 6px}.metric-card{text-align:left;cursor:pointer}.metric-card.is-active{outline:2px solid var(--color-primary)}.action-panel{border-left:4px solid var(--color-primary)}.form-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:14px 0}.form-grid label,.action-dialog label{display:flex;flex-direction:column;gap:6px;font-size:13px;color:var(--text-secondary)}.form-grid input,.form-grid select,.form-grid textarea,.action-dialog input,.action-dialog textarea{box-sizing:border-box;width:100%;border:1px solid var(--border-color);border-radius:7px;padding:9px 10px;background:#fff;color:var(--text-primary)}.form-grid .span-2{grid-column:span 2}.form-grid .span-3{grid-column:1/-1}.checkbox-label{flex-direction:row!important;align-items:center}.checkbox-label input{width:auto}.field-help,.file-note,.cell-sub{color:var(--text-tertiary);font-size:12px}.file-note{align-self:end;padding-bottom:10px}.table-wrap{overflow-x:auto}.mp-table{width:100%;border-collapse:collapse;min-width:900px}.consent-table{min-width:1180px}.mp-table th,.mp-table td{padding:10px;border-bottom:1px solid var(--border-color);text-align:left;vertical-align:top;font-size:13px}.mp-table th{color:var(--text-secondary);font-weight:600;background:#fafbfc}.empty-cell{text-align:center!important;color:var(--text-tertiary);padding:24px!important}.mp-link,.danger-link{border:0;background:transparent;padding:3px 5px;cursor:pointer;color:var(--color-primary);white-space:nowrap}.danger-link{color:var(--color-danger,#d92d20)}.mp-link:disabled,.danger-link:disabled{opacity:.5;cursor:not-allowed}.action-cell{white-space:nowrap}.state-tag{display:inline-flex;border-radius:999px;padding:3px 8px;font-size:12px;background:#f2f4f7;color:#475467}.state-tag.is-success{background:#ecfdf3;color:#067647}.state-tag.is-danger{background:#fff1f0;color:#b42318}.state-tag.is-warn{background:#fff7e6;color:#8b5c00}.state-tag.is-muted{background:#f2f4f7;color:#667085}.cell-error{max-width:220px;color:#b42318;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-top:4px}.hash-cell{max-width:230px;word-break:break-all;font-family:monospace;font-size:12px}.dialog-mask{position:fixed;inset:0;z-index:3000;background:rgba(16,24,40,.45);display:flex;align-items:center;justify-content:center;padding:20px}.action-dialog{width:min(560px,94vw);max-height:88vh;overflow:auto;background:#fff;border-radius:12px;padding:20px;box-shadow:0 24px 70px rgba(16,24,40,.25);display:flex;flex-direction:column;gap:14px}.dialog-close{border:0;background:transparent;font-size:24px;cursor:pointer;color:#667085}.dialog-actions{justify-content:flex-end;margin-top:4px}.dialog-error{padding:9px 11px;border-radius:7px;background:#fff1f0;color:#b42318;font-size:13px}
.compliance-now{overflow:hidden;border-color:color-mix(in srgb,var(--color-primary) 24%,var(--border-color));box-shadow:0 14px 38px rgba(30,64,175,.08)}
.compliance-now__head{align-items:flex-end;background:linear-gradient(120deg,var(--color-primary-light,#eef4ff),#fff 70%)}
.compliance-now__head>div{display:grid;gap:4px}.compliance-now__eyebrow{color:var(--color-primary);font-size:10px;font-weight:800;letter-spacing:.12em}
.compliance-now__list{display:grid;gap:10px;padding:14px}.compliance-now__item{display:grid;grid-template-columns:minmax(155px,.8fr) minmax(0,2fr) auto;align-items:center;gap:14px;padding:13px;border:1px solid var(--border-color);border-left:4px solid var(--color-warning,#f59e0b);border-radius:10px;background:#fff}
.compliance-now__identity{display:grid;gap:3px}.compliance-now__identity>span{color:var(--color-warning,#b45309);font-size:10px;font-weight:800}.compliance-now__identity small{color:var(--text-tertiary)}
.compliance-now__item dl{display:grid;grid-template-columns:1.5fr 1fr 1fr;gap:9px;margin:0}.compliance-now__item dl div{min-width:0;padding:8px 10px;border-radius:8px;background:#f8fafc}.compliance-now__item dt{margin-bottom:3px;color:var(--text-tertiary);font-size:10px;font-weight:700}.compliance-now__item dd{margin:0;color:var(--text-secondary);font-size:12px;line-height:1.45}
.compliance-now__empty{display:grid;gap:4px;padding:24px;text-align:center;color:var(--text-secondary)}.compliance-now__empty span{font-size:12px}
.work-tabs{gap:4px 12px;padding:0 0 8px;border-bottom:1px solid var(--border-color)}.work-tabs__group{display:flex;align-items:center;flex:0 0 auto}.work-tabs__buttons{display:flex;flex-wrap:wrap;gap:4px}.work-tabs__group .work-tab{border-color:transparent;background:transparent;padding:8px 10px;border-radius:6px}.work-tabs__group .work-tab.is-active{background:var(--color-primary-light,#eef4ff);color:var(--color-primary);font-weight:600}.work-tab:focus-visible{outline:2px solid var(--color-primary);outline-offset:2px}
@media(max-width:1100px){.compliance-metrics .metric-card{flex-direction:column;align-items:flex-start;gap:4px}}
.incident-table{min-width:1280px}.incident-table td{max-width:260px}.incident-table strong{display:block;line-height:1.45}.incident-table tr.is-focus td{background:var(--color-primary-light,#eef4ff)}
@media(max-width:900px){.form-grid{grid-template-columns:1fr 1fr}.form-grid .span-3{grid-column:1/-1}}
@media(max-width:900px){.compliance-now__item{grid-template-columns:1fr}.compliance-now__item dl{grid-template-columns:1fr}}
@media(max-width:640px){.form-grid{grid-template-columns:1fr}.form-grid .span-2,.form-grid .span-3{grid-column:auto}.workbench-head{align-items:flex-start;flex-direction:column}.head-actions{width:100%}.action-dialog{padding:16px}.compliance-now__head{align-items:flex-start}}
</style>
