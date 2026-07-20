<template>
  <ModulePageShell :title="page.title" :subtitle="page.subtitle"
    :role-name="ctx.currentRole.roleName" :data-scope-name="ctx.dataScope.scopeName">
    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <ModuleHero :title="project ? project.projectName : '尚未创建实施项目'"
          :subtitle="project ? project.projectNo + ' · ' + project.profileCode : '选择方案后自动生成12类推荐预设'"
          :stats="heroStats" />

        <section v-if="!project" class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">创建学校实施项目</span></header>
          <div class="mp-card__body impl-actions">
            <input v-model.trim="createForm.projectName" maxlength="100" placeholder="项目名称" />
            <select v-model="createForm.profileCode"><option v-for="p in catalog.profiles" :key="p.code" :value="p.code">{{ p.name }} · {{ p.version }}</option></select>
            <button class="mp-btn mp-btn--primary" :disabled="saving" @click="createProject">创建并加载推荐预设</button>
          </div>
        </section>

        <template v-else>
          <section v-if="pageKey === 'overview'" class="mp-card">
            <header class="mp-card__head"><span class="mp-card__title">12类实施进度</span><span class="mp-note">{{ project.progress }}%</span></header>
            <div class="mp-card__body impl-grid">
              <div v-for="s in catalog.sections" :key="s.code" class="impl-tile"><b>{{ s.name }}</b><StatusTag type="success" :label="sectionMap[s.code]?.status || '待配置'" /></div>
            </div>
          </section>

          <section v-if="pageKey === 'wizard'" class="mp-card">
            <header class="mp-card__head"><span class="mp-card__title">12类引导式问答</span><span class="mp-note">推荐值已经填好，学校只需确认或选择；保存后仍可修改</span></header>
            <div class="mp-card__body">
              <div v-for="s in catalog.sections" :key="s.code" class="impl-section">
                <div><b>{{ s.name }}</b><small>{{ s.code }}</small></div>
                <div class="impl-questions">
                  <label v-for="q in s.questions" :key="q.key" class="impl-question">
                    <span>{{ q.label }}<em v-if="q.required">*</em></span>
                    <select v-if="q.type === 'select'" v-model="sectionDrafts[s.code][q.key]">
                      <option v-for="option in q.options" :key="option[0]" :value="option[0]">{{ option[1] }}</option>
                    </select>
                    <select v-else-if="q.type === 'boolean'" v-model="sectionDrafts[s.code][q.key]">
                      <option :value="true">是</option><option :value="false">否</option>
                    </select>
                    <input v-else-if="q.type === 'number'" v-model.number="sectionDrafts[s.code][q.key]"
                      type="number" :min="q.min" :max="q.max" />
                    <span v-else-if="q.type === 'multiselect'" class="impl-checks">
                      <label v-for="option in q.options" :key="option[0]"><input v-model="sectionDrafts[s.code][q.key]" type="checkbox" :value="option[0]" />{{ option[1] }}</label>
                    </span>
                  </label>
                </div>
                <button class="mp-btn" :disabled="saving" @click="saveSection(s.code)">保存</button>
              </div>
              <button class="mp-btn mp-btn--primary" :disabled="saving" @click="preview">生成安装预览</button>
            </div>
          </section>

          <section v-if="pageKey === 'presets'" class="mp-card">
            <header class="mp-card__head"><span class="mp-card__title">版本化学校开局包</span><span class="mp-note">均包含专业目录与专业教学标准入口</span></header>
            <div class="mp-card__body impl-grid">
              <article v-for="p in catalog.profiles" :key="p.code" :class="['impl-preset', { active: project.profileCode === p.code }]">
                <b>{{ p.name }}</b><small>{{ p.version }} · 建议 {{ p.deliveryDays }} 天</small><p>{{ p.description }}</p>
              </article>
            </div>
          </section>

          <section v-if="pageKey === 'mapping'" class="mp-card">
            <header class="mp-card__head"><span class="mp-card__title">第一步：上传师生标准模板</span><span class="mp-note">预检不会写入账号或组织</span></header>
            <div class="mp-card__body impl-actions">
              <input type="file" accept=".xlsx" @change="selectFile" />
              <button class="mp-btn mp-btn--primary" :disabled="saving || !identityFile" @click="validateFile">上传并预检</button>
              <span v-if="identityPreview" class="mp-note">批次 {{ identityPreview.batchNo }} · {{ identityPreview.total }}行 · 错误{{ identityPreview.invalid }}行</span>
              <button v-if="identityPreview" class="mp-btn" :disabled="saving" @click="discoverMapping">生成组织与角色候选</button>
            </div>
          </section>

          <section v-if="pageKey === 'mapping' && mapping" class="mp-card">
            <header class="mp-card__head"><span class="mp-card__title">第二步：确认组织树候选</span><span class="mp-note">编码、规范化名称和完整父级路径才能自动匹配</span></header>
            <div class="mp-card__body">
              <div v-for="item in mapping.candidates" :key="item.candidateId" class="impl-candidate">
                <div><b>{{ typeLabel(item.entityType) }} · {{ item.name }}</b><small>{{ item.parentName ? '上级：' + item.parentName : '顶级组织' }} · 来源行 {{ item.sourceRows.join('、') }}</small></div>
                <select v-model="item.uiAction"><option value="MATCH">匹配已有</option><option value="CREATE">新建</option><option value="IGNORE">忽略</option><option value="REVIEW" disabled>需人工处理</option></select>
                <select v-if="item.uiAction === 'MATCH'" v-model="item.uiTargetId"><option value="">请选择目标</option><option v-for="m in item.matches" :key="m.id" :value="m.id">{{ m.name }}</option></select>
                <StatusTag :type="item.recommendation.confidence === 1 ? 'success' : 'warning'" :label="item.recommendation.confidence === 1 ? '确定性推荐' : '存在歧义'" />
              </div>
              <div v-for="teacher in mapping.roleSuggestions" :key="teacher.loginName" class="impl-candidate">
                <div><b>教师角色 · {{ teacher.name }}（{{ teacher.loginName }}）</b><small>{{ teacher.positionName || '未填岗位' }}</small></div>
                <input v-model.trim="teacher.uiRoleCodes" placeholder="多个角色用逗号分隔" />
              </div>
              <div v-if="mapping.conflicts.length" class="impl-warning">仍有 {{ mapping.conflicts.length }} 个阻断项，必须逐项选择或填写角色后才能确认。</div>
              <button class="mp-btn mp-btn--primary" :disabled="saving" @click="confirmMapping">确认以上匹配</button>
            </div>
          </section>

          <section v-if="pageKey === 'mapping' && mapping?.status === 'CONFIRMED'" class="mp-card">
            <header class="mp-card__head"><span class="mp-card__title">第三步：安装组织与角色</span><span class="mp-note">同一事务，发生冲突整批回滚</span></header>
            <div class="mp-card__body impl-actions">
              <input v-model.trim="mappingApply.reason" placeholder="安装原因" maxlength="500" />
              <input v-model.trim="mappingApply.confirmText" placeholder="输入：确认安装组织与角色" />
              <button class="mp-btn mp-btn--danger" :disabled="saving" @click="applyMapping">安装并重新校验原文件</button>
            </div>
          </section>

          <section v-if="pageKey === 'mapping' && refreshedPreview" class="mp-card">
            <header class="mp-card__head"><span class="mp-card__title">第四步：创建师生账号</span><span class="mp-note">组织和角色安装后自动重检，无需再次上传</span></header>
            <div class="mp-card__body impl-actions">
              <StatusTag :type="refreshedPreview.invalid === 0 ? 'success' : 'danger'" :label="refreshedPreview.invalid === 0 ? '全部校验通过' : refreshedPreview.invalid + '行仍有错误'" />
              <button class="mp-btn mp-btn--danger" :disabled="saving || refreshedPreview.invalid > 0" @click="confirmAccounts">确认创建师生账号</button>
            </div>
          </section>

          <section v-if="pageKey === 'mapping' && relationBatch" class="mp-card">
            <header class="mp-card__head"><span class="mp-card__title">第五步：确认业务关系候选</span><span class="mp-note">只安装真实业务对象；冲突项必须选择覆盖或忽略</span></header>
            <div class="mp-card__body">
              <div class="impl-actions">
                <StatusTag type="success" :label="`可安装 ${relationBatch.summary.ready || 0}`" />
                <StatusTag type="info" :label="`已存在 ${relationBatch.summary.already || 0}`" />
                <StatusTag type="warning" :label="`冲突 ${relationBatch.summary.conflicts || 0}`" />
                <StatusTag type="danger" :label="`阻断 ${relationBatch.summary.blocked || 0}`" />
              </div>
              <div v-for="item in relationBatch.candidates" :key="item.candidateId" class="impl-candidate">
                <div><b>{{ item.relationName }} · {{ item.subjectName || item.subjectRef }} → {{ item.objectName || item.objectRef }}</b><small>{{ item.contextRef ? '业务批次：' + item.contextRef + ' · ' : '' }}来源行 {{ item.sourceRows.join('、') }} · {{ item.recommendation.reason }}</small></div>
                <select v-if="relationBatch.status === 'DISCOVERED'" v-model="item.uiAction">
                  <option value="" disabled>请选择</option>
                  <option v-if="item.status === 'READY'" value="INSTALL">安装</option>
                  <option v-if="item.status === 'ALREADY'" value="KEEP">保持现状</option>
                  <option v-if="item.status === 'CONFLICT'" value="REPLACE">明确覆盖</option>
                  <option value="IGNORE">忽略</option>
                </select>
                <StatusTag :type="relationTone(item.status)" :label="item.status" />
              </div>
              <button v-if="relationBatch.status === 'DISCOVERED'" class="mp-btn mp-btn--primary" :disabled="saving" @click="confirmRelations">确认关系决定</button>
              <div v-if="relationBatch.status === 'CONFIRMED'" class="impl-actions">
                <input v-model.trim="relationApply.reason" placeholder="安装原因" maxlength="500" />
                <input v-model.trim="relationApply.confirmText" placeholder="输入：确认安装业务关系" />
                <button class="mp-btn mp-btn--danger" :disabled="saving" @click="applyRelations">写入真实业务主表</button>
              </div>
              <div v-if="relationBatch.status === 'APPLIED'" class="impl-actions">
                <StatusTag type="success" label="业务关系已安装" />
                <input v-model.trim="relationRollback.reason" placeholder="回滚原因" maxlength="500" />
                <input v-model.trim="relationRollback.confirmText" placeholder="输入：确认回滚业务关系" />
                <button class="mp-btn mp-btn--danger" :disabled="saving" @click="rollbackRelations">安全回滚</button>
              </div>
              <StatusTag v-if="relationBatch.status === 'ROLLED_BACK'" type="warning" label="业务关系已回滚" />
            </div>
          </section>

          <section v-if="pageKey === 'installed' || pageKey === 'changes'" class="mp-card">
            <header class="mp-card__head"><span class="mp-card__title">安装版本链</span></header>
              <div class="mp-card__body"><p v-if="!installations.length" class="mp-note">尚未应用配置快照。</p><div v-for="i in installations" :key="i.id" class="impl-candidate"><div><b>{{ i.installationNo }}</b><small>{{ i.profileCode }} · {{ i.appliedAt }} · {{ i.snapshotHash }}</small></div><StatusTag :label="i.status" :type="i.status === 'APPLIED' ? 'success' : 'info'" /><button v-if="pageKey === 'changes' && i.status === 'APPLIED'" class="mp-btn mp-btn--danger" :disabled="saving" @click="createChange(i)">从此版本开始变更</button></div><div v-if="pageKey === 'changes' && project?.changeSourceInstallationId" class="impl-actions"><button class="mp-btn" :disabled="saving" @click="analyzeChange">运行影响分析</button><small v-if="changeAnalysis">风险 {{ changeAnalysis.riskLevel }} · 变更段 {{ changeAnalysis.changedSections?.length || 0 }} · 受影响配置 {{ JSON.stringify(changeAnalysis.affectedTableCounts) }}</small></div></div>
          </section>

          <section v-if="pageKey === 'acceptance'" class="mp-card">
            <div v-if="project.status === 'ACCEPTED' && project.acceptanceDigest" class="mp-note">验收摘要已冻结：{{ project.acceptanceDigest }}（{{ project.acceptanceSummary?.checks?.length || 0 }} 项检查）</div>
            <header class="mp-card__head"><span class="mp-card__title">12类上线检查</span></header>
            <div class="mp-card__body"><div class="impl-actions"><button class="mp-btn mp-btn--primary" :disabled="saving" @click="runChecks">运行全部检查</button><input v-model.trim="acceptForm.comment" placeholder="验收意见" /><input v-model.trim="acceptForm.confirmText" placeholder="输入：确认验收" /><button class="mp-btn mp-btn--danger" :disabled="saving || project.status !== 'READY_FOR_ACCEPTANCE'" @click="accept">验收封板</button></div><div v-for="c in project.checks" :key="c.code" class="impl-candidate"><StatusTag :type="c.result === 'PASS' ? 'success' : 'danger'" :label="c.result" /><b>{{ c.name }}</b><small>{{ c.severity }} · {{ JSON.stringify(c.evidence) }}</small><button v-if="c.result !== 'PASS' && c.severity !== 'BLOCKER'" class="mp-btn" :disabled="saving" @click="confirmCheck(c)">责任确认</button></div></div>
          </section>

          <section v-if="project.status === 'PREVIEW_READY'" class="mp-card">
            <header class="mp-card__head"><span class="mp-card__title">应用配置快照</span></header>
            <div class="mp-card__body impl-actions"><input v-model.trim="applyForm.reason" placeholder="应用原因" /><input v-model.trim="applyForm.confirmText" placeholder="输入：确认应用" /><button class="mp-btn mp-btn--danger" :disabled="saving" @click="applyPreset">应用</button></div>
          </section>

          <section v-if="pageKey === 'wizard' && runtimePresets" class="mp-card">
            <header class="mp-card__head"><span class="mp-card__title">运行预设主表</span><span class="mp-note">流程默认待确认；工作台与站内通知模板已安装</span></header>
            <div class="mp-card__body">
              <div class="impl-actions">
                <StatusTag type="info" :label="`流程 ${runtimePresets.counts.workflows}`" />
                <StatusTag type="success" :label="`工作台 ${runtimePresets.counts.workbenches}`" />
                <StatusTag type="success" :label="`通知模板 ${runtimePresets.counts.notifications}`" />
              </div>
              <div v-for="flow in runtimePresets.workflows" :key="flow.code" class="impl-flow">
                <input v-model="policyForm.workflowCodes" type="checkbox" :value="flow.code" :disabled="flow.policyConfirmed" />
                <span><b>{{ flow.name }}</b><small>{{ flow.code }} · {{ flow.timeoutHours }}小时 · {{ flow.status }}</small></span>
                <input v-model.number="flow.timeoutHours" type="number" min="1" max="720" aria-label="流程时限（小时）" />
                <button class="mp-btn" :disabled="saving" @click.prevent="saveWorkflow(flow)">保存时限</button>
              </div>
              <div v-if="runtimePresets.workflows.some((x) => !x.policyConfirmed)" class="impl-actions">
                <input v-model.trim="policyForm.reason" placeholder="学校流程政策确认说明" maxlength="500" />
                <input v-model.trim="policyForm.confirmText" placeholder="输入：确认启用学校流程政策" />
                <button class="mp-btn mp-btn--danger" :disabled="saving || !policyForm.workflowCodes.length" @click="confirmWorkflowPolicy">确认并启用选中流程</button>
              </div>
              <div class="impl-runtime-group">
                <h4>角色工作台（可后续修改）</h4>
                <div v-for="workbench in runtimePresets.workbenches" :key="workbench.roleCode" class="impl-runtime-row">
                  <div><b>{{ workbench.roleCode }}</b><small>{{ workbench.title }}</small></div>
                  <input v-model.trim="workbench.title" aria-label="工作台标题" placeholder="工作台标题" />
                  <input v-model.trim="workbench.subtitle" aria-label="工作台副标题" placeholder="工作台副标题" />
                  <select v-model="workbench.status" aria-label="工作台状态"><option value="ENABLED">启用</option><option value="DISABLED">停用</option></select>
                  <button class="mp-btn" :disabled="saving" @click="saveWorkbench(workbench)">保存</button>
                </div>
              </div>
              <div class="impl-runtime-group">
                <h4>消息与通知（学校可修改显示文案）</h4>
                <div v-for="notice in runtimePresets.notifications" :key="`${notice.templateCode}-${notice.channel}`" class="impl-notice-row">
                  <div><b>{{ notice.templateCode }}</b><small>变量：{{ notice.variables.join('、') || '无' }}</small></div>
                  <input v-model.trim="notice.title" aria-label="通知标题" placeholder="通知标题" />
                  <textarea v-model.trim="notice.content" aria-label="通知正文" rows="2" placeholder="通知正文" />
                  <input v-model.trim="notice.deepLink" aria-label="通知跳转地址" placeholder="跳转地址（可选）" />
                  <label class="impl-inline-check"><input v-model="notice.enabled" type="checkbox" />启用</label>
                  <button class="mp-btn" :disabled="saving" @click="saveNotification(notice)">保存</button>
                </div>
              </div>
            </div>
          </section>
        </template>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleHero, StatusTag, LoadingState, ErrorState } from '@/components/business'
import { implementationApi } from '@/modules/system/api/implementation.api'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

const PAGES = { overview: ['实施总览', '查看12类进度、阻断项和下一步'], wizard: ['首次开局向导', '通过可恢复配置完成学校开局'], presets: ['预设方案', '选择版本化学校开局包'], mapping: ['数据导入与智能匹配', '一份师生文件生成组织、岗位角色和账号'], installed: ['已安装配置', '追溯配置来源与版本'], changes: ['变更与升级', '从已安装版本发起受控变更'], acceptance: ['上线检查与验收', '阻断项全部通过后封板'] }

export default {
  name: 'SystemImplementationView', components: { ModulePageShell, ModuleHero, StatusTag, LoadingState, ErrorState },
  props: { ctx: { type: Object, required: true } },
  data() { return { loading: true, saving: false, error: '', catalog: { profiles: [], sections: [] }, project: null, installations: [], changeAnalysis: null, mapping: null, identityFile: null, identityPreview: null, refreshedPreview: null, relationBatch: null, runtimePresets: null, sectionDrafts: {}, createForm: { projectName: '学校首次实施', profileCode: 'HIGHER_VOCATIONAL' }, applyForm: { reason: '', confirmText: '' }, mappingApply: { reason: '', confirmText: '' }, relationApply: { reason: '', confirmText: '' }, relationRollback: { reason: '', confirmText: '' }, policyForm: { workflowCodes: [], reason: '', confirmText: '' }, acceptForm: { comment: '', confirmText: '' } } },
  computed: { pageKey() { return this.$route.meta.implementationPageKey || 'overview' }, page() { const p = PAGES[this.pageKey]; return { title: p[0], subtitle: p[1] } }, sectionMap() { return Object.fromEntries((this.project?.sections || []).map((x) => [x.code, x])) }, heroStats() { return [{ label: '状态', value: this.project?.status || '未创建', tone: 'primary' }, { label: '完成度', value: `${this.project?.progress || 0}%`, tone: 'success' }, { label: '安装版本', value: String(this.installations.length), tone: 'info' }] } },
  watch: { '$route.meta.implementationPageKey': 'load' }, created() { this.load() },
  methods: {
    typeLabel(type) { return ({ COLLEGE: '学院/部门', MAJOR: '专业', CLASS: '班级' })[type] || type },
    relationTone(status) { return ({ READY: 'success', ALREADY: 'info', CONFLICT: 'warning', BLOCKED: 'danger' })[status] || 'info' },
    hydrateMapping(raw) { if (!raw?.candidates) return null; raw.candidates.forEach((x) => { x.uiAction = x.recommendation.action; x.uiTargetId = x.recommendation.targetId || '' }); raw.roleSuggestions.forEach((x) => { x.uiRoleCodes = x.currentRoleCodes || x.suggestedRoleCodes.join(',') }); return raw },
    hydrateRelation(raw) { if (!raw?.candidates) return null; raw.candidates.forEach((x) => { x.uiAction = x.recommendation.action === 'REVIEW' ? '' : x.recommendation.action }); return raw },
    async load() { this.loading = true; this.error = ''; try { const [catalog, project] = await Promise.all([implementationApi.catalog(), implementationApi.current()]); this.catalog = catalog; this.project = project; this.sectionDrafts = Object.fromEntries(catalog.sections.map((s) => [s.code, JSON.parse(JSON.stringify(this.sectionMap[s.code]?.config || s.defaultConfig))])); this.mapping = this.hydrateMapping(this.sectionMap.identity_import?.config?.mapping); this.installations = ['installed', 'changes'].includes(this.pageKey) ? await implementationApi.installations() : []; if (project && this.pageKey === 'mapping') { const batches = await implementationApi.relationBatches(project.id); this.relationBatch = this.hydrateRelation(batches[0]) } if (project && this.pageKey === 'wizard' && ['APPLIED', 'VERIFYING', 'READY_FOR_ACCEPTANCE', 'ACCEPTED'].includes(project.status)) { const runtime = await implementationApi.runtimePresets(project.id); this.runtimePresets = { ...runtime, workflows: runtime.workflows || [], workbenches: runtime.workbenches || [], notifications: runtime.notifications || [] }; this.policyForm.workflowCodes = this.runtimePresets.workflows.filter((x) => !x.policyConfirmed).map((x) => x.code) } } catch (e) { this.error = e.message || '加载失败' } finally { this.loading = false } },
    async action(fn, message) { this.saving = true; try { await fn(); toast.success(message); await this.load() } catch (e) { toast.error(e.message || '操作失败') } finally { this.saving = false } },
    createProject() { this.action(() => implementationApi.create(this.createForm), '实施项目已创建') },
    createChange(installation) { const name = window.prompt('请输入变更项目名称', `${installation.profileCode} 变更项目`); if (name === null) return; this.action(async () => { this.project = await implementationApi.createChange(installation.id, { projectName: name.trim() }); this.changeAnalysis = null }, '变更项目已创建') },
    analyzeChange() { this.action(async () => { this.changeAnalysis = await implementationApi.analyzeChange(this.project.id); this.project.version = this.changeAnalysis.projectVersion }, '影响分析已完成') },
    saveSection(code) { this.action(() => implementationApi.saveSection(this.project.id, code, { config: this.sectionDrafts[code], projectVersion: this.project.version }), '配置已保存') },
    preview() { this.action(() => implementationApi.preview(this.project.id), '预览已生成') }, applyPreset() { this.action(() => implementationApi.apply(this.project.id, this.applyForm), '配置快照已应用') },
    selectFile(e) { this.identityFile = e.target.files?.[0] || null; this.identityPreview = null },
    async validateFile() { this.saving = true; try { this.identityPreview = await implementationApi.validateIdentityFile(this.identityFile); toast.success('文件预检完成') } catch (e) { toast.error(e.message || '预检失败') } finally { this.saving = false } },
    async discoverMapping() { this.saving = true; try { this.mapping = this.hydrateMapping(await implementationApi.discoverMapping(this.project.id, this.identityPreview.batchNo)); this.project.version = this.mapping.projectVersion; toast.success('候选已生成') } catch (e) { toast.error(e.message || '生成候选失败') } finally { this.saving = false } },
    confirmMapping() { const organizationDecisions = this.mapping.candidates.map((x) => ({ candidateId: x.candidateId, action: x.uiAction, targetId: x.uiTargetId })); const roleDecisions = this.mapping.roleSuggestions.map((x) => ({ loginName: x.loginName, roleCodes: x.uiRoleCodes })); this.action(async () => { const result = await implementationApi.confirmMapping(this.project.id, { projectVersion: this.project.version, organizationDecisions, roleDecisions }); this.mapping = this.hydrateMapping(result) }, '匹配已确认') },
    async applyMapping() { this.saving = true; try { const result = await implementationApi.applyMapping(this.project.id, { ...this.mappingApply, projectVersion: this.project.version }); this.refreshedPreview = result.refreshedPreview; this.mapping.status = 'APPLIED'; toast.success('组织与角色已安装，原文件已重检') } catch (e) { toast.error(e.message || '安装失败') } finally { this.saving = false } },
    async confirmAccounts() { this.saving = true; try { const batchNo = this.refreshedPreview.batchNo; const res = await systemApi.confirmIdentityImportBatch(batchNo); if (res.code !== 0) throw new Error(res.message); toast.success(res.data.receipt); if ((this.identityPreview?.relations?.suggested || 0) > 0) { this.relationBatch = this.hydrateRelation(await implementationApi.discoverRelations(this.project.id, batchNo)); this.project.version = this.relationBatch.projectVersion; toast.success('师生账号已创建，业务关系候选已生成') } else { await this.load() } } catch (e) { toast.error(e.message || '创建账号失败') } finally { this.saving = false } },
    confirmRelations() { const decisions = this.relationBatch.candidates.map((x) => ({ candidateId: x.candidateId, action: x.uiAction })); this.action(async () => { this.relationBatch = this.hydrateRelation(await implementationApi.confirmRelations(this.project.id, { batchNo: this.relationBatch.batchNo, projectVersion: this.project.version, decisions })); this.project.version = this.relationBatch.projectVersion }, '业务关系决定已确认') },
    applyRelations() { this.action(async () => { this.relationBatch = this.hydrateRelation(await implementationApi.applyRelations(this.project.id, { batchNo: this.relationBatch.batchNo, projectVersion: this.project.version, ...this.relationApply })); this.project.version = this.relationBatch.projectVersion }, '业务关系已写入真实业务主表') },
    rollbackRelations() { this.action(async () => { this.relationBatch = this.hydrateRelation(await implementationApi.rollbackRelations(this.project.id, this.relationBatch.batchNo, { projectVersion: this.project.version, ...this.relationRollback })); this.project.version = this.relationBatch.projectVersion }, '业务关系已安全回滚') },
    confirmWorkflowPolicy() { this.action(() => implementationApi.confirmWorkflowPolicy(this.project.id, this.policyForm), '学校流程政策已确认并启用') },
    saveWorkflow(flow) { this.action(() => implementationApi.updateWorkflow(this.project.id, flow.code, { projectVersion: this.project.version, timeoutHours: flow.timeoutHours }), '流程时限已保存，需重新确认政策') },
    saveWorkbench(workbench) { this.action(() => implementationApi.updateWorkbench(this.project.id, workbench.roleCode, { projectVersion: this.project.version, title: workbench.title, subtitle: workbench.subtitle, status: workbench.status }), '角色工作台已保存') },
    saveNotification(notice) { this.action(() => implementationApi.updateNotification(this.project.id, notice.templateCode, notice.channel, { projectVersion: this.project.version, title: notice.title, content: notice.content, deepLink: notice.deepLink, enabled: notice.enabled }), '通知模板已保存') },
    runChecks() { this.action(() => implementationApi.runChecks(this.project.id), '上线检查完成') },
    confirmCheck(check) { const comment = window.prompt('请输入责任确认说明', '已核实并接受该项风险'); if (comment === null) return; this.action(() => implementationApi.confirmCheck(this.project.id, check.code, { projectVersion: this.project.version, comment, confirmText: '确认责任' }), '责任确认已记录') },
    accept() { this.action(() => implementationApi.accept(this.project.id, this.acceptForm), '实施已验收') }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.impl-actions{display:flex;align-items:center;gap:var(--space-3);flex-wrap:wrap}.impl-actions input,.impl-actions select,.impl-question input[type="number"],.impl-question select,.impl-candidate input,.impl-candidate select{border:1px solid var(--border-light);border-radius:var(--radius-md);padding:9px 11px;background:var(--bg-card);color:var(--text-primary)}.impl-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:var(--space-3)}.impl-tile,.impl-preset{border:1px solid var(--border-light);border-radius:var(--radius-md);padding:var(--space-3)}.impl-tile{display:flex;justify-content:space-between;align-items:center}.impl-preset.active{border-color:var(--primary-500);background:var(--bg-section-blue)}.impl-preset small,.impl-section small,.impl-candidate small{display:block;color:var(--text-tertiary);margin-top:4px}.impl-preset p{color:var(--text-secondary);font-size:var(--font-size-sm);line-height:1.6}.impl-section{display:grid;grid-template-columns:180px minmax(0,1fr) 80px;gap:var(--space-3);align-items:start;padding:var(--space-3) 0;border-bottom:1px dashed var(--border-light)}.impl-questions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--space-3)}.impl-question{display:flex;flex-direction:column;gap:6px;color:var(--text-secondary);font-size:var(--font-size-sm)}.impl-question em{color:var(--danger-500);font-style:normal;margin-left:3px}.impl-checks{display:flex;gap:10px;flex-wrap:wrap}.impl-checks label{display:flex;align-items:center;gap:4px}.impl-candidate{display:flex;align-items:center;gap:var(--space-3);padding:var(--space-3) 0;border-bottom:1px dashed var(--border-light)}.impl-candidate>div{flex:1}.impl-warning{margin:var(--space-3) 0;padding:var(--space-3);background:var(--warning-50);color:var(--warning-700);border-radius:var(--radius-md)}@media(max-width:900px){.impl-grid,.impl-questions{grid-template-columns:1fr}.impl-section{grid-template-columns:1fr}.impl-candidate{align-items:flex-start;flex-direction:column}}
.impl-flow{display:flex;align-items:flex-start;gap:10px;padding:10px 0;border-bottom:1px dashed var(--border-light)}.impl-flow span{flex:1}.impl-flow small{display:block;color:var(--text-tertiary);margin-top:3px}.impl-flow input[type="number"]{width:100px;border:1px solid var(--border-light);border-radius:var(--radius-md);padding:8px;background:var(--bg-card);color:var(--text-primary)}
.impl-runtime-group{margin-top:var(--space-4);padding-top:var(--space-3);border-top:1px solid var(--border-light)}.impl-runtime-group h4{margin:0 0 var(--space-2);color:var(--text-primary)}.impl-runtime-row,.impl-notice-row{display:grid;grid-template-columns:150px minmax(140px,1fr) minmax(180px,1fr) 100px 70px;gap:var(--space-2);align-items:center;padding:var(--space-2) 0;border-bottom:1px dashed var(--border-light)}.impl-notice-row{grid-template-columns:150px 180px minmax(260px,1fr) 180px 60px 70px}.impl-runtime-row small,.impl-notice-row small{display:block;color:var(--text-tertiary);margin-top:3px;font-size:var(--font-size-xs)}.impl-runtime-row input,.impl-runtime-row select,.impl-notice-row input,.impl-notice-row textarea{width:100%;border:1px solid var(--border-light);border-radius:var(--radius-md);padding:8px;background:var(--bg-card);color:var(--text-primary);font:inherit}.impl-inline-check{display:flex;align-items:center;gap:4px;font-size:var(--font-size-xs);white-space:nowrap}@media(max-width:1100px){.impl-runtime-row,.impl-notice-row{grid-template-columns:1fr 1fr}.impl-runtime-row>div,.impl-notice-row>div{grid-column:1/-1}}
</style>
