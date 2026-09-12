<template>
  <div class="wf-page">
    <AppSectionHeader title="流程模板管理" subtitle="学校管理员维护草稿；发布新版本只影响后续新提交的业务单据。" />
    <div class="wf-page__filters">
      <select v-model="filters.status" @change="load"><option value="">全部状态</option><option value="ENABLED">已发布</option><option value="DRAFT">草稿</option><option value="DISABLED">已停用</option></select>
      <input v-model.trim="filters.keyword" placeholder="搜索模板名称 / 编码" @keyup.enter="load" />
      <AppButton variant="secondary" @click="load">查询</AppButton>
      <AppButton v-if="isSchoolAdmin" variant="primary" @click="openCreate">新建流程模板</AppButton>
    </div>
    <p v-if="!isSchoolAdmin" class="wf-processes__readonly" role="note">仅学校管理员可以新建、编辑和发布流程模板。</p>
    <WorkflowStateBlock :loading="loading" :error="error" :empty="!list.length" view-state="NORMAL" @retry="load">
      <div class="wf-processes__list">
        <ProcessTemplateCard v-for="t in list" :key="t.templateId" :template="t" @view="openDetail">
          <template #actions>
            <AppButton v-if="isSchoolAdmin && t.status === 'ENABLED'" variant="primary" :loading="actionId === t.templateId" @click="createDraft(t)">创建新版本</AppButton>
            <AppButton v-if="isSchoolAdmin && t.status === 'DRAFT'" variant="primary" :loading="actionId === t.templateId" @click="openEdit(t)">编辑草稿</AppButton>
            <AppButton v-if="isSchoolAdmin && t.status === 'DRAFT'" variant="secondary" :loading="actionId === t.templateId" @click="publish(t)">发布</AppButton>
            <AppButton v-if="isSchoolAdmin && t.status === 'ENABLED'" variant="ghost" :loading="actionId === t.templateId" @click="openVoid(t)">停用</AppButton>
            <AppButton variant="ghost" @click="openDetail(t)">详情</AppButton>
          </template>
        </ProcessTemplateCard>
      </div>
    </WorkflowStateBlock>
    <AppDrawer :visible="detailVisible" :title="detail ? detail.templateName : '模板详情'" @update:visible="detailVisible = $event">
      <div v-if="detail" class="wf-processes__detail">
        <dl class="wf-processes__kv"><dt>适用业务</dt><dd>{{ businessLabel(detail.businessType) }}</dd><dt>版本</dt><dd>第 {{ detail.version }} 版</dd><dt>状态</dt><dd><AppBadge :type="statusType(detail.status)">{{ statusText(detail.status) }}</AppBadge></dd><dt>维护人</dt><dd>{{ detail.updatedBy || '—' }} · {{ detail.updatedAt || '—' }}</dd></dl>
        <h4 class="wf-processes__sub">节点定义（{{ detail.nodes.length }}）</h4>
        <div v-for="n in detail.nodes" :key="n.nodeId" class="wf-processes__node"><div class="wf-processes__node-head"><span class="wf-processes__node-name">{{ n.nodeName }}</span><AppBadge type="neutral">{{ nodeTypeLabel(n.nodeType) }}</AppBadge></div><div class="wf-processes__node-meta"><span>责任角色：{{ n.candidateRoles.map(roleLabel).join('、') || '—' }}</span><span>办理时限：{{ n.sla }} 小时</span></div></div>
      </div>
    </AppDrawer>
    <AppDrawer :visible="editorVisible" :title="editor.templateId ? '编辑流程草稿' : '新建流程模板'" @update:visible="editorVisible = $event">
      <form class="wf-editor" @submit.prevent="saveEditor">
        <label>模板名称<input v-model.trim="editor.name" maxlength="200" required /></label>
        <label>适用业务类型<select v-model="editor.bizType" required><option value="" disabled>请选择业务类型</option><option v-for="item in businessOptions" :key="item.code" :value="item.code">{{ item.label }}</option></select></label>
        <section class="wf-editor__nodes" aria-label="审批节点"><div class="wf-editor__nodes-head"><strong>审批节点</strong><AppButton type="button" variant="ghost" @click="addNode">添加节点</AppButton></div>
          <div v-for="(node, index) in editor.nodes" :key="node.localKey" class="wf-editor__node"><strong>第 {{ index + 1 }} 个节点</strong><label>节点名称<input v-model.trim="node.name" maxlength="150" required /></label><label>责任角色<select v-model="node.role" required><option v-for="role in roleOptions" :key="role" :value="role">{{ roleLabel(role) }}</option></select></label><label>时限（小时）<input v-model.number="node.sla" type="number" min="1" max="720" required /></label><AppButton v-if="editor.nodes.length > 1" type="button" variant="ghost" @click="removeNode(index)">删除节点</AppButton></div>
        </section>
        <p class="wf-editor__hint">草稿可以反复保存；发布后，已在办理的单据仍保留原版本。</p><div class="wf-editor__actions"><AppButton type="button" variant="ghost" @click="editorVisible = false">取消</AppButton><AppButton type="submit" variant="primary" :loading="saving">保存草稿</AppButton></div>
      </form>
    </AppDrawer>
    <AppConfirmDialog v-model:visible="voidVisible" title="停用流程模板" confirm-text="确认停用" require-reason reason-label="停用原因" :reason-min-length="5" @confirm="voidTemplate">停用后不能再发起新的业务单据；已在办理的单据仍保留原流程版本。</AppConfirmDialog>
  </div>
</template>

<script>
import { AppButton, AppBadge, AppDrawer, AppSectionHeader } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import WorkflowStateBlock from '@/modules/workflow/components/WorkflowStateBlock.vue'
import ProcessTemplateCard from '@/modules/workflow/components/ProcessTemplateCard.vue'
import { workflowProvider, getProcessStatusText, getProcessStatusType, getNodeTypeLabel, ROLE_LABELS } from '@/modules/workflow'
import { fetchLayoutContext } from '@/modules/workbench/api/workbench.api'
import { toast } from '@/utils/toast'

const ROLE_OPTIONS = ['SCHOOL_ADMIN', 'ACADEMIC_ADMIN', 'COLLEGE_ADMIN', 'COUNSELOR', 'STUDENT_AFFAIRS_ADMIN', 'INTERN_MENTOR', 'GRADUATION_ADMIN']
const BUSINESS_LABELS = { CsLeave: '学生请假', LEAVE: '请假审批', AID: '家庭经济困难认定', FUNDING: '奖助学金审批', DISCIPLINE: '违纪处分', DISCIPLINE_REMOVE: '处分解除', GRADE_REVIEW: '成绩审核发布', GRADE_CHANGE: '成绩更正', SCHEDULE_CHANGE: '调停课', STATUS_CHANGE: '学籍异动', PROGRAM: '培养方案', INTERNSHIP_APPLICATION: '实习申请', INTERNSHIP_CHANGE: '实习岗位变更', GD_TOPIC: '毕业设计选题', GD_PROPOSAL: '毕业设计开题', GD_FINAL: '毕业设计成果审核', EMPLOYMENT_DESTINATION: '就业去向登记' }
const makeNode = () => ({ localKey: crypto.randomUUID(), nodeCode: '', name: '', role: 'SCHOOL_ADMIN', sla: 48 })
const emptyEditor = () => ({ templateId: '', version: 0, name: '', bizType: '', nodes: [makeNode()] })

export default {
  name: 'WorkflowProcessesView', components: { AppButton, AppBadge, AppDrawer, AppSectionHeader, AppConfirmDialog, WorkflowStateBlock, ProcessTemplateCard },
  data() { return { loading: false, error: '', list: [], filters: { status: '', keyword: '' }, detailVisible: false, detail: null, editorVisible: false, editor: emptyEditor(), saving: false, actionId: '', voidVisible: false, voidTarget: null, roleCode: '' } },
  computed: {
    isSchoolAdmin() { return this.roleCode === 'SCHOOL_ADMIN' },
    roleOptions() { return [...new Set([...ROLE_OPTIONS, ...this.editor.nodes.map(node => node.role).filter(Boolean)])] },
    businessOptions() {
      const options = Object.entries(BUSINESS_LABELS).map(([code, label]) => ({ code, label }))
      if (this.editor.bizType && !BUSINESS_LABELS[this.editor.bizType]) options.push({ code: this.editor.bizType, label: '当前配置的业务（保留原值）' })
      return options
    }
  },
  async created() { await Promise.all([this.load(), this.loadRole()]) },
  methods: {
    statusText: getProcessStatusText, statusType: getProcessStatusType, nodeTypeLabel: getNodeTypeLabel,
    roleLabel(code) { return ROLE_LABELS[code] || '其他已配置角色' },
    businessLabel(code) { return BUSINESS_LABELS[code] || '其他已配置业务' },
    async loadRole() { try { this.roleCode = String((await fetchLayoutContext()).currentRole?.roleCode || '').toUpperCase() } catch { this.roleCode = '' } },
    async load() { this.loading = true; this.error = ''; try { this.list = (await workflowProvider.getProcessTemplates(this.filters)).data.list } catch (e) { this.error = e.message || '加载失败' } finally { this.loading = false } },
    async openDetail(t) { try { this.detail = (await workflowProvider.getProcessTemplateDetail(t.templateId)).data; this.detailVisible = true } catch (e) { toast.warning(e.message || '加载详情失败') } },
    openCreate() { this.editor = emptyEditor(); this.editorVisible = true },
    openEdit(t) { this.editor = { templateId: t.templateId, version: t.rowVersion, name: t.templateName, bizType: t.businessType, nodes: t.nodes.map((n) => ({ localKey: crypto.randomUUID(), nodeCode: n.nodeCode, name: n.nodeName, role: n.candidateRoles[0] || 'SCHOOL_ADMIN', sla: n.sla || 48 })) }; this.editorVisible = true },
    addNode() { this.editor.nodes.push(makeNode()) }, removeNode(index) { this.editor.nodes.splice(index, 1) },
    async saveEditor() { this.saving = true; const payload = { name: this.editor.name, bizType: this.editor.bizType, nodes: this.editor.nodes.map((n, index) => ({ name: n.name, role: n.role, sla: n.sla, nodeCode: n.nodeCode || `NODE_${String(index + 1).padStart(2, '0')}` })) }; try { if (this.editor.templateId) await workflowProvider.updateProcessTemplate(this.editor.templateId, { ...payload, version: this.editor.version }); else await workflowProvider.createProcessTemplate(payload); toast.success(this.editor.templateId ? '草稿已保存' : '草稿已创建'); this.editorVisible = false; await this.load() } catch (e) { toast.warning(e.message || '保存失败') } finally { this.saving = false } },
    async createDraft(t) { this.actionId = t.templateId; try { const res = await workflowProvider.createProcessTemplateDraft(t.templateId, t.rowVersion); toast.success(`已创建「${res.data.templateName}」的新版本草稿`); await this.load(); this.openEdit(res.data) } catch (e) { toast.warning(e.message || '创建草稿失败') } finally { this.actionId = '' } },
    async publish(t) { this.actionId = t.templateId; try { await workflowProvider.publishProcessTemplateDraft(t.templateId, t.rowVersion); toast.success('新版本已发布，后续新单据将使用新流程'); await this.load() } catch (e) { toast.warning(e.message || '发布失败') } finally { this.actionId = '' } },
    openVoid(t) { this.voidTarget = t; this.voidVisible = true },
    async voidTemplate(reason) { const target = this.voidTarget; if (!target) return; this.actionId = target.templateId; try { await workflowProvider.updateProcessTemplateStatus(target.templateId, 'DISABLED', target.rowVersion, reason); toast.success('流程模板已停用'); this.voidVisible = false; await this.load() } catch (e) { toast.warning(e.message || '停用失败') } finally { this.actionId = '' } }
  }
}
</script>

<style scoped>
@import './workflow-page.css';
.wf-processes__list{display:flex;flex-direction:column;gap:var(--space-4)}.wf-processes__readonly{margin:0 0 var(--space-3);padding:10px 12px;border-radius:var(--radius-base);background:var(--gray-50);color:var(--text-secondary)}.wf-processes__detail{display:flex;flex-direction:column;gap:var(--space-3)}.wf-processes__kv{display:grid;grid-template-columns:auto 1fr;gap:var(--space-2) var(--space-4);margin:0;font-size:var(--font-size-sm)}.wf-processes__kv dt{color:var(--text-tertiary)}.wf-processes__kv dd{margin:0;color:var(--text-primary)}.wf-processes__sub{margin:var(--space-2) 0 0;font-size:var(--font-size-base)}.wf-processes__node{border:1px solid var(--border-light);border-radius:var(--radius-base);padding:var(--space-2) var(--space-3)}.wf-processes__node-head,.wf-editor__nodes-head{display:flex;align-items:center;justify-content:space-between;gap:var(--space-2)}.wf-processes__node-name{font-weight:var(--font-weight-medium)}.wf-processes__node-meta{display:flex;flex-wrap:wrap;gap:var(--space-3);margin-top:var(--space-1);font-size:var(--font-size-xs);color:var(--text-secondary)}.wf-editor{display:flex;flex-direction:column;gap:16px}.wf-editor>label,.wf-editor__node label{display:grid;gap:6px;font-size:13px;color:var(--text-secondary)}.wf-editor input,.wf-editor select{min-height:36px;border:1px solid var(--border-light);border-radius:6px;padding:0 10px;color:var(--text-primary);background:var(--bg-card)}.wf-editor__nodes{display:grid;gap:12px}.wf-editor__node{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:12px;border:1px solid var(--border-light);border-radius:8px}.wf-editor__node>strong{grid-column:1/-1}.wf-editor__hint{margin:0;color:var(--text-secondary);font-size:13px;line-height:1.6}.wf-editor__actions{display:flex;justify-content:flex-end;gap:8px}@media(max-width:640px){.wf-editor__node{grid-template-columns:1fr}.wf-editor__node>strong{grid-column:auto}}
</style>
