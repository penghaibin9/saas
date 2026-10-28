<template>
  <section class="system-workspace">
    <header class="page-heading"><div><p class="eyebrow">学校配置与日常维护</p><h1>{{ route.meta.title }}</h1></div><el-button v-if="!special" :loading="loading" @click="load">刷新</el-button></header>
    <IdentityImportWorkspace v-if="resource === 'identity-import'"/>
    <RoleWorkspace v-else-if="resource === 'role'"/>
    <ConfigurationWorkspace v-else-if="['brand','dictionary','notification'].includes(resource)" :category="resource"/>
    <LeavePolicyWorkspace v-else-if="resource === 'leave-policy'"/>
    <template v-else>
      <el-alert v-if="error" type="error" :title="error" :closable="false" show-icon/>
      <el-alert v-if="receipt" type="success" :title="receipt" closable @close="receipt = ''"/>
      <template v-if="resource === 'overview' && data">
        <div class="overview-counts"><article><strong>{{ data.studentCount }}</strong><span>学生主档</span></article><article><strong>{{ data.staffCount }}</strong><span>教职工资料</span></article></div>
        <h2>学校准备与实习开局</h2><p>按顺序完成学校准备，再进入本平台的岗位实习中心。师生主档和账号沿用，无需重复导入。</p><ol class="setup-steps"><li v-for="step in data.steps" :key="step.path"><router-link v-if="pathAllowed(step.path)" :to="step.path">{{ step.name }}</router-link><span v-else>{{ step.name }}（由相应负责人办理）</span><p v-if="step.note">{{ step.note }}</p></li></ol>
        <h2>待处理问题</h2><div class="issue-list"><article v-for="item in data.issues" :key="item.name"><div><strong>{{ item.count }}</strong><span>{{ item.name }}</span></div><router-link v-if="pathAllowed(item.path)" :to="item.path">查看并处理</router-link></article></div><p>{{ data.note }}</p>
        <template v-if="data.backup"><h2>备份与恢复核验</h2><p>{{ data.backup.statusLabel }}</p><p>{{ data.backup.note }}</p><router-link v-if="pathAllowed(data.backup.path)" :to="data.backup.path">查看备份与恢复演练记录</router-link></template>
      </template>
      <template v-else>
        <p class="description">{{ descriptions[resource] }}</p>
        <p v-if="['integration','runtime'].includes(resource) && data?.checkedAt">{{ resource==='integration' ? '本次读取时间' : '本次检测时间' }}：{{ dateText(data.checkedAt) }}</p>
        <template v-if="resource==='delivery' && data?.version"><p>当前版本：{{ data.version.name }}</p><details><summary>实施人员使用：发布与数据库版本</summary><p>发布提交：<code>{{ data.version.commit || '未登记' }}</code></p><p>数据库结构：<code>{{ data.version.schemaRevision || '未登记' }}</code></p></details></template>
        <template v-if="resource==='migration' && data"><h2>迁移工具核对结果</h2><p>{{ data.evidenceNote }}</p><el-table :data="data.receipts" empty-text="尚无本校迁移脚本回执"><el-table-column prop="title" label="核对回执"/><el-table-column prop="statusLabel" label="核对结果"/><el-table-column label="脚本核验时间" min-width="180"><template #default="{row}">{{ dateText(row.checkedAt) }}</template></el-table-column><el-table-column prop="detail" label="数据与附件对账" min-width="280"/></el-table><h2>学校验收登记</h2></template>
        <template v-if="resource==='scope' && data?.blockedTasks && (data.blockedTasks.total || route.query.blocked==='1')">
          <h2>待交接异常：{{ data.blockedTasks.total }} 条</h2><p>{{ data.blockedTasks.note }}</p>
          <el-table :data="data.blockedTasks.items" empty-text="当前页没有需交接的异常待办"><el-table-column prop="title" label="待办事项"/><el-table-column prop="objectId" label="单据编号"/><el-table-column prop="assigneeId" label="原承办人编号"/><el-table-column prop="statusLabel" label="需要处理的原因"/><el-table-column label="继续办理" min-width="200"><template #default="{row}"><router-link v-if="row.path && pathAllowed(row.path)" :to="row.path">{{ row.actionLabel }}</router-link><span v-else>{{ row.actionNote || '由具备该业务权限的负责人办理' }}</span></template></el-table-column></el-table>
          <el-pagination v-if="data.blockedTasks.total>30" :current-page="blockedPage" :page-size="30" :total="data.blockedTasks.total" layout="total, prev, pager, next" aria-label="异常待办分页" @current-change="setBlockedPage"/>
          <el-button v-if="blockedPage>1 && !data.blockedTasks.items.length" @click="setBlockedPage(1)">当前页已无异常，返回第一页核对</el-button>
        </template>
        <ResponsibilityHandoff v-if="resource === 'scope'" :can-edit="canManage" @transferred="load" />
        <el-button v-if="resource==='scope' && route.query.blocked==='1'" @click="router.replace({query:{}})">查看全部责任关系</el-button>
        <details v-if="resource==='org' && allowed('system.org.manage')" :open="Boolean(route.query.jobId)"><summary>从电子表格导入组织架构</summary><IdentityImportWorkspace fixed-kind="organizations"/></details>
        <details v-if="resource==='scope' && data?.responsibilityCheck && route.query.blocked!=='1'" :open="!scopeRefId"><summary>责任关系核对：{{ data.responsibilityCheck.missing }} 个对象缺少负责人，{{ data.responsibilityCheck.duplicates }} 个对象有多名负责人</summary><p>{{ data.responsibilityCheck.note }}</p>
          <label>核对问题 <el-select v-model="issueType" aria-label="核对问题" @change="setIssuePage(1)"><el-option value="" label="全部责任问题"/><el-option value="MISSING" label="缺少负责人"/><el-option value="DUPLICATE" label="多名负责人"/></el-select></label>
          <el-table :data="data.responsibilityCheck.items" empty-text="当前条件下没有责任问题"><el-table-column prop="kind" label="责任岗位"/><el-table-column prop="name" label="组织"/><el-table-column prop="statusLabel" label="核对结果"/><el-table-column label="核对原关系"><template #default="{row}"><el-button text @click="focusResponsibility(row)">核对此对象责任</el-button></template></el-table-column></el-table>
          <el-button v-if="issuePage>1 && !data.responsibilityCheck.items.length" @click="setIssuePage(1)">当前页没有责任问题，返回第一页核对</el-button>
          <el-pagination v-if="data.responsibilityCheck.total>30" :current-page="issuePage" :page-size="30" :total="data.responsibilityCheck.total" layout="total, prev, pager, next" aria-label="责任问题分页" @current-change="setIssuePage"/>
        </details>
        <div v-if="resource==='scope' && data?.selectedObject" class="selected-responsibility">
          <h2>正在核对：{{ data.selectedObject.name }}</h2><p>下方仅列出此{{ scopeLabels[data.selectedObject.scopeType] }}的原责任关系。变更前核对原负责人在办事项；保存不会自动转派待办。</p>
          <el-button @click="focusResponsibility(null)">查看全部责任关系</el-button><el-button v-if="canManage" type="primary" @click="edit(data.selectedObject)">为此对象新增责任</el-button>
        </div>
        <div class="toolbar" v-if="!['integration','runtime'].includes(resource) && !(resource==='scope' && route.query.blocked==='1')">
          <el-checkbox v-if="resource==='scope'" v-model="scopeReviewOnly" @change="reset">仅看历史待核对关系</el-checkbox>
          <el-radio-group v-if="resource === 'org'" v-model="orgKind" @change="reset"><el-radio-button v-for="(label,key) in orgLabels" :key="key" :value="key">{{ label }}</el-radio-button></el-radio-group>
          <el-input v-if="['org','staff','student','account','audit','task','migration','delivery'].includes(resource)" v-model="keyword" clearable maxlength="100" :placeholder="searchLabel" :aria-label="searchLabel" @keyup.enter="reset" @clear="reset"/><el-button v-if="['org','staff','student','account','audit','task','migration','delivery'].includes(resource)" @click="reset">查询</el-button>
          <el-select v-if="['staff','student'].includes(resource)" v-model="accountStatus" placeholder="全部账号关联状态" aria-label="账号关联状态" @change="reset"><el-option value="" label="全部账号关联状态"/><el-option value="UNBOUND" :label="resource==='student' ? '尚未绑定账号' : '尚未开通账号'"/><el-option value="BOUND" :label="resource==='student' ? '已绑定账号' : '已开通账号'"/></el-select>
          <el-select v-if="resource==='task'" v-model="taskStatus" placeholder="全部任务状态" aria-label="任务状态" @change="reset"><el-option value="" label="全部任务状态"/><el-option v-for="(label,key) in taskStatuses" :key="key" :value="key" :label="label"/></el-select><template v-if="resource==='audit'"><label>开始时间 <input v-model="auditStart" type="datetime-local" aria-label="审计开始时间"/></label><label>结束时间 <input v-model="auditEnd" type="datetime-local" aria-label="审计结束时间"/></label></template><el-button v-if="canManage && ['org','scope','migration','delivery'].includes(resource) && !(resource==='scope' && data?.selectedObject)" type="primary" @click="edit(resource==='scope' ? data?.selectedObject : undefined)">{{ resource === 'org' ? '新增组织' : resource === 'scope' ? '新增责任关系' : '登记资料' }}</el-button>
          <router-link v-if="['student','staff','account'].includes(resource) && allowed('system.identity-import.view')" :to="`/admin/system/identity-import/${resource === 'staff' ? 'staff' : 'students'}`"><el-button type="primary">导入师生并开通账号</el-button></router-link>
          <el-button v-if="resource === 'audit' && allowed('system.audit.export')" @click="exportAudit">导出审计记录</el-button>
          <el-button v-if="['org','staff','student'].includes(resource) && allowed('system.person.export')" :loading="exporting" :disabled="loading" @click="exportPeople">导出当前筛选资料</el-button>
        </div>
        <el-table v-if="data && !(resource==='scope' && route.query.blocked==='1')" :data="data?.items || []" row-key="id" v-loading="loading" empty-text="当前条件下没有记录">
          <template v-if="resource === 'org'"><el-table-column prop="code" label="组织代码"/><el-table-column prop="name" label="组织名称" min-width="180"/><el-table-column v-if="orgKind === 'classes'" prop="grade" label="年级"/></template>
          <template v-else-if="['staff','student'].includes(resource)"><el-table-column prop="number" :label="resource === 'staff' ? '工号' : '学号'" min-width="130"/><el-table-column prop="name" label="姓名"/><el-table-column prop="organizationLabel" label="组织归属" min-width="220"/><el-table-column prop="accountLabel" label="账号绑定"/><el-table-column v-if="resource === 'staff'" prop="phone" label="联系电话"/><el-table-column v-else prop="grade" label="年级"/></template>
          <template v-else-if="resource === 'account'"><el-table-column prop="loginName" label="登录账号"/><el-table-column prop="name" label="姓名"/><el-table-column prop="typeLabel" label="身份类别"/><el-table-column label="有效角色" min-width="200"><template #default="{row}">{{ row.roles.map(r => r.name).join('、') || '未分配' }}</template></el-table-column><el-table-column label="首次改密"><template #default="{row}">{{ row.mustChangePassword ? '待修改临时密码' : '已设置' }}</template></el-table-column></template>
          <template v-else-if="resource === 'scope'"><el-table-column prop="name" label="负责人"/><el-table-column label="负责类型"><template #default="{row}">{{ scopeLabels[row.scopeType] || '待核对' }}</template></el-table-column><el-table-column prop="refName" label="负责对象"/><el-table-column label="关系检查"><template #default="{row}">{{ row.needsReview ? (row.status==='DISABLED' ? '历史关系已停用，原描述保留' : '历史关系待核对，暂不授权') : '已使用稳定对象关联' }}</template></el-table-column></template>
          <template v-else-if="resource === 'task'"><el-table-column prop="id" label="任务编号" width="100"/><el-table-column prop="typeName" label="任务类型" min-width="120"/><el-table-column prop="name" label="文件／任务" min-width="220"/><el-table-column label="生成时间" min-width="180"><template #default="{row}">{{ dateText(row.createdAt) }}</template></el-table-column><el-table-column prop="operator" label="操作人"/><el-table-column prop="total" label="总行数"/><el-table-column prop="succeeded" label="成功"/><el-table-column prop="failed" label="错误"/></template>
          <template v-else-if="resource === 'audit'"><el-table-column prop="operator" label="操作人"/><el-table-column label="操作"><template #default="{row}">{{ row.actionLabel || actionLabel(row.action) }}</template></el-table-column><el-table-column prop="objectId" label="对象编号"/><el-table-column prop="result" label="结果"/><el-table-column prop="roleLabel" label="当时身份"/><el-table-column prop="reason" label="原因" min-width="200"/><el-table-column label="变更明细" min-width="240"><template #default="{row}"><details v-if="row.changes?.length"><summary>查看 {{ row.changes.length }} 项变化</summary><div v-for="change in row.changes" :key="change.field"><strong>{{ change.label }}</strong><p>变更前：{{ change.before }}</p><p>变更后：{{ change.after }}</p></div></details><span v-else>{{ row.action==='CONFIG_SAVE' ? '此记录未记载字段差异' : '—' }}</span></template></el-table-column><el-table-column label="时间" min-width="180"><template #default="{row}">{{ dateText(row.createdAt) }}</template></el-table-column></template>
          <template v-else-if="resource==='integration'"><el-table-column prop="name" label="服务" min-width="130"/><el-table-column label="状态与启用情况" min-width="180"><template #default="{row}"><strong>{{ row.statusLabel }}</strong><p v-if="row.configurationLabel">当前配置：{{ row.configurationLabel }}</p></template></el-table-column><el-table-column label="最近实际检测／投递时间" min-width="175"><template #default="{row}">{{ dateText(row.lastCheckedAt) }}</template></el-table-column><el-table-column label="依据与失败原因" min-width="250"><template #default="{row}">{{ row.detail }}<p v-if="row.failureReason">失败原因：{{ row.failureReason }}</p></template></el-table-column><el-table-column prop="responsibleName" label="学校服务承办人" min-width="140"/></template>
          <template v-else-if="resource==='runtime'"><el-table-column prop="name" label="服务／检查项" min-width="180"/><el-table-column prop="detail" label="当前依据" min-width="250"/></template>
          <template v-else-if="['migration','delivery'].includes(resource)"><el-table-column prop="title" label="资料／批次名称" min-width="220"/><el-table-column prop="evidenceLabel" label="证据性质" min-width="240"/><el-table-column label="登记核验时间"><template #default="{row}">{{ dateText(row.checkedAt) }}</template></el-table-column></template>
          <el-table-column v-if="resource==='account'" label="有效期至" min-width="180"><template #default="{row}">{{ row.expiresAt ? dateText(row.expiresAt) : '长期有效' }}</template></el-table-column>
          <el-table-column v-if="!['audit','integration'].includes(resource)" prop="statusLabel" label="状态" min-width="130"/>
          <el-table-column v-if="!['audit','integration','runtime'].includes(resource)" label="操作" :fixed="['task','account'].includes(resource) ? 'right' : false" :min-width="resource === 'task' ? 150 : 200"><template #default="{row}">
            <template v-if="resource === 'account'"><el-button v-if="canManage && ['ACTIVE','LOCKED'].includes(row.status)" text @click="accountEdit(row, 'DISABLE')">停用</el-button><el-button v-if="canManage && row.status === 'DISABLED'" text @click="accountEdit(row, 'ENABLE')">启用</el-button><el-button v-if="canManage && row.status === 'LOCKED'" text @click="accountEdit(row, 'UNLOCK')">解锁</el-button><el-button v-if="allowed('system.account.reset')" text @click="accountEdit(row, 'RESET')">重置密码</el-button><el-button v-if="canManage" text @click="accountEdit(row, 'EXPIRY')">有效期</el-button></template>
            <el-button v-else-if="resource==='task' && row.canDownload" text @click="downloadResult(row)">下载受控结果</el-button><el-button v-else-if="resource==='task' && row.canRetry" text :disabled="exporting" @click="retryExport(row)">重试失败导出</el-button><el-button v-else-if="resource === 'task' && row.canOpen" text @click="router.push(row.path)">打开回执</el-button><p v-if="resource==='task' && row.message">{{ row.message }}</p>
            <el-button v-else-if="canManage" text @click="edit(row)">维护</el-button><el-button v-if="resource==='scope' && canManage && row.needsReview && row.status!=='DISABLED'" text @click="edit(row,false,true)">停用待核对关系</el-button><el-button v-if="['migration','delivery'].includes(resource)" text @click="edit(row,true)">查看登记</el-button><el-button v-if="resource==='student' && allowed('system.account.manage') && canManage" text @click="bindingStudent=row;bindingOpened=true">核对账号绑定</el-button><el-button v-if="['staff','student'].includes(resource) && allowed('system.person.sensitive')" text @click="contactRow=row;contactReason='';contactPhone='';contactError='';contactOpened=true">查看完整电话</el-button><el-button v-if="['migration','delivery'].includes(resource)" text @click="viewFiles=row.details?.fileIds || [];fileViewOpened=true">查看资料附件</el-button>
          </template></el-table-column>
        </el-table>
        <el-button v-if="resource==='scope' && route.query.blocked!=='1' && page>1 && data && !data.items.length" @click="setPage(1)">当前页已无记录，返回第一页</el-button>
        <el-pagination v-if="data?.total > 30 && !(resource==='scope' && route.query.blocked==='1')" v-model:current-page="page" :page-size="30" :total="data.total" layout="total, prev, pager, next" @current-change="setPage"/>

        <template v-if="resource === 'runtime' && data"><h2>备份与恢复演练</h2><p>{{ data.backupNote }}</p><el-table :data="data.backups" empty-text="尚无本校备份与恢复演练脚本回执"><el-table-column prop="title" label="记录名称"/><el-table-column prop="kindLabel" label="类型"/><el-table-column prop="statusLabel" label="验证状态"/><el-table-column label="脚本核验时间" min-width="180"><template #default="{row}">{{ dateText(row.checkedAt) }}</template></el-table-column><el-table-column prop="detail" label="核验依据" min-width="250"/></el-table><details><summary>实施人员使用：数据库版本</summary><code>{{ data.schemaRevision || '未读取' }}</code></details></template>
      </template>
    </template>
    <StudentBindingReview v-if="bindingStudent" v-model="bindingOpened" :student="bindingStudent" @saved="receipt=$event;load()"/><el-dialog v-model="contactOpened" title="按用途查看联系电话" @closed="contactPhone='';contactReason=''" width="min(540px,95vw)"><p>{{ contactRow?.name }}：完整查看将留下审计记录，关闭后清除明文。</p><el-input v-model="contactReason" type="textarea" placeholder="说明本次联系用途（至少5字）" aria-label="本次联系用途"/><el-button :loading="contactLoading" @click="revealContact">登记用途并查看</el-button><el-alert v-if="contactError" type="error" :title="contactError"/><p v-if="contactPhone">联系电话：{{ contactPhone }}</p></el-dialog>
    <el-dialog v-model="fileViewOpened" title="资料原始附件"><SystemAttachments :model-value="viewFiles" :purpose="resource==='migration' ? 'SYSTEM_MIGRATION' : 'SYSTEM_DOCUMENT'"/></el-dialog>
    <el-dialog v-model="opened" :title="dialogTitle" width="min(740px, 95vw)" :close-on-click-modal="false" @closed="formError = ''">
      <el-form label-position="top" :disabled="saving || readOnly" @submit.prevent="submit">
        <template v-if="resource === 'org'"><el-form-item label="组织名称" required><el-input v-model="form.name" maxlength="100"/></el-form-item><el-form-item label="组织代码" required><el-input v-model="form.code" maxlength="50"/></el-form-item><el-form-item v-if="['majors','classes'].includes(orgKind)" label="上级组织" required><SystemObjectSelect v-model="form.parentId" @update:model-value="form.confirmImpact=false" :path="`/organizations/${orgKind === 'majors' ? 'colleges' : 'majors'}`" label="选择上级组织"/></el-form-item><el-form-item v-if="orgKind === 'classes'" label="年级"><el-input v-model="form.grade" maxlength="20"/></el-form-item><div v-if="orgKind === 'majors'" class="form-grid"><el-form-item label="国家专业目录代码"><el-input v-model="form.nationalCode" maxlength="20"/></el-form-item><el-form-item label="学制（年）"><el-input-number v-model="form.educationYears" :min="1" :max="8"/></el-form-item><el-form-item label="培养层次"><el-select v-model="form.trainingLevel"><el-option value="SECONDARY" label="中职"/><el-option value="HIGHER" label="高职专科"/><el-option value="FIVE_YEAR" label="五年一贯制"/></el-select></el-form-item></div></template>
        <template v-else-if="['student','staff'].includes(resource)"><el-form-item label="姓名" required><el-input v-model="form.name" maxlength="100"/></el-form-item><el-form-item :label="resource === 'staff' ? '所属院系（与校内部门至少选一项）' : '所属院系'" :required="resource === 'student'"><SystemObjectSelect v-model="form.collegeId" path="/organizations/colleges" label="选择院系"/></el-form-item><el-form-item v-if="resource === 'student'" label="所属班级" required><SystemObjectSelect v-model="form.classId" path="/organizations/classes" label="选择班级"/></el-form-item><el-form-item v-if="resource === 'student'" label="年级"><el-input v-model="form.grade"/></el-form-item><template v-else><el-form-item label="校内部门"><SystemObjectSelect v-model="form.departmentId" path="/organizations/departments" label="选择校内部门"/></el-form-item><el-form-item label="新联系电话（留空保留原值）"><el-input v-model="form.phone" maxlength="30"/></el-form-item></template><el-alert v-if="impact" type="warning" :closable="false" :title="`关联实习 ${impact.internshipCount} 条、待办 ${impact.pendingCount} 条。${impact.note}`"/><p v-if="editLoading" role="status">正在核对关联批次和责任关系…</p>
          <template v-if="impact">
            <p v-if="impact.serviceResponsibilityCount">此人还承担学校服务承办职责。资料停用后不再作为有效承办人显示，请在“通知与服务设置”重新指定；原配置及变更记录保留。</p>
            <h3>关联批次（共{{ impact.batchCount }}个）</h3><el-table :data="impact.batches" empty-text="当前没有关联实习批次"><el-table-column prop="name" label="批次名称"/><el-table-column prop="id" label="批次编号" width="110"/></el-table>
            <h3>现有责任关系（共{{ impact.scopeCount }}条）</h3><el-table :data="impact.responsibilities" empty-text="当前没有相关责任关系"><el-table-column prop="name" label="负责人"/><el-table-column prop="kind" label="负责类型"/><el-table-column prop="refName" label="负责对象"/></el-table>
          </template>
          <el-checkbox v-model="form.confirmImpact" :disabled="editLoading || !impact">已核对组织调整影响，按原记录保留在办责任</el-checkbox></template>
        <template v-else-if="resource === 'account'"><p>{{ form.name }}（{{ form.loginName }}）</p><el-alert type="warning" :closable="false" title="操作后旧登录会话立即失效，历史记录保留；停用账号后仍需办理任务交接。"/><el-form-item v-if="form.action === 'EXPIRY'" label="账号有效期（留空表示长期）"><el-date-picker v-model="form.expiresAt" type="datetime"/></el-form-item></template>
        <template v-else-if="resource === 'scope' && !retiringScope"><el-form-item label="负责人账号" required><SystemObjectSelect v-model="form.userId" path="/accounts" label="选择负责人账号"/></el-form-item><el-form-item label="生效身份" required><el-select v-model="form.roleCode"><el-option v-for="role in roleOptions" :key="role.code" :value="role.code" :label="role.name"/></el-select></el-form-item><el-form-item label="负责类型"><el-select v-model="form.scopeType" @change="form.refId = ''"><el-option v-for="(label,key) in scopeLabels" :key="key" :value="key" :label="label"/></el-select></el-form-item><el-form-item label="负责对象" required><SystemObjectSelect v-model="form.refId" :path="`/organizations/${{COLLEGE:'colleges',MAJOR:'majors',CLASS:'classes'}[form.scopeType]}`" label="选择负责对象"/></el-form-item></template>
        <template v-else-if="['migration','delivery'].includes(resource)"><el-form-item label="资料名称／迁移批次名称" required><el-input v-model="form.title" maxlength="200"/></el-form-item><el-form-item label="来源及资料定位"><el-input v-model="form.source" maxlength="300"/></el-form-item><el-form-item label="责任人"><SystemObjectSelect v-model="form.ownerUserId" path="/accounts" label="选择资料责任人"/></el-form-item><el-form-item label="原始资料附件"><SystemAttachments v-model="form.fileIds" :purpose="resource==='migration' ? 'SYSTEM_MIGRATION' : 'SYSTEM_DOCUMENT'" :editable="!readOnly" @ready="filesReady=$event"/></el-form-item><el-form-item label="核对说明"><el-input v-model="form.notes" type="textarea" :rows="5" maxlength="5000"/></el-form-item><template v-if="resource === 'migration'"><el-form-item label="迁移映射规则"><el-input v-model="form.mappingRules" type="textarea" :rows="3" maxlength="5000"/></el-form-item><el-form-item label="组织与人员对应关系"><el-input v-model="form.identityMapping" type="textarea" :rows="3" maxlength="5000"/></el-form-item><p>对应清单使用组织代码、学号或工号；明细表可作为原始附件上传。请勿填写密码或证件号码。</p><el-form-item label="异常及处理结果"><el-input v-model="form.exceptionResolution" type="textarea" :rows="3" maxlength="5000"/></el-form-item><p>登记已核验前须补齐来源、映射和异常处理，核对人员、单据、附件数量，并完成正常师生接续办理；没有异常也须明确说明。</p><div class="form-grid" v-for="[key,label] in [['People','人员'],['Records','业务记录'],['Files','附件']]" :key="key"><el-form-item :label="`来源${label}数量`"><el-input-number v-model="form['expected'+key]" :min="0"/></el-form-item><el-form-item :label="`迁入${label}数量`"><el-input-number v-model="form['actual'+key]" :min="0"/></el-form-item></div><el-checkbox v-model="form.continuationChecked">已用正常师生账号核对查看及继续办理</el-checkbox></template></template>
        <el-alert v-if="retiringScope" type="warning" :closable="false" title="仅停用此条历史责任关系，保留原人员与对象描述。不会猜测归属、重新授权或自动转派待办；请先核对原责任资料。"/>
        <el-form-item v-if="resource !== 'account' && !retiringScope" label="状态"><el-select v-model="form.status"><template v-if="['migration','delivery'].includes(resource)"><el-option value="PENDING" label="待处理"/><el-option value="REVIEW" label="待核对"/><el-option value="VERIFIED" label="学校登记已核验"/></template><template v-else><el-option value="ACTIVE" label="启用"/><el-option value="DISABLED" label="停用"/></template></el-select></el-form-item>
        <el-form-item v-if="!readOnly" label="变更原因" required><el-input v-model="form.reason" type="textarea" maxlength="500"/></el-form-item>
        <template v-if="resource==='org' && form.id">
          <h3>组织引用核对</h3><p v-if="editLoading" role="status">正在核对组织引用…</p>
          <template v-if="impact"><p v-if="!organizationMoved">{{ impact.note }}</p><el-table :data="impact.items"><el-table-column prop="name" label="引用事项"/><el-table-column prop="count" label="数量"/></el-table>
            <p v-if="organizationMoved" role="alert">调整上级组织将同步所列学生的当前院系、专业归属，并按新归属裁定管理范围。组织和人员编号、账号绑定、历史实习及原待办责任保持；请另行核对在办事项交接。</p>
            <el-checkbox v-if="organizationMoved || (form.status==='DISABLED' && impact.hasReferences)" v-model="form.confirmImpact">{{ organizationMoved ? '已核对影响，确认调整归属并同步当前学生资料' : '已核对引用，确认仅停用组织并保留关联资料' }}</el-checkbox>
          </template>
        </template>
        <template v-if="resource==='scope' && form.id">
          <h3>原责任与在办事项核对</h3><p v-if="editLoading" role="status">正在核对原责任人的在办事项…</p>
          <template v-if="impact?.scopeId===form.id"><p>原责任：{{ impact.original.name }}，{{ impact.roleName }}；{{ impact.original.kind }}：{{ impact.original.refName }}；原状态：{{ impact.original.statusLabel }}。</p><p>{{ impact.note }}</p><RoleImpactSummary v-if="impact.roleImpact" :impact="impact.roleImpact"/></template>
        </template>
        <el-button v-if="form.id && ['org','student','staff','scope'].includes(resource)" :loading="editLoading" :disabled="saving" @click="refreshImpact">重新核对引用</el-button>
        <ConflictReview :conflict="conflict" :input="conflictInput" @reviewed="form.expectedVersion=$event;conflict=null;formError=''"/><el-alert v-if="formError" type="error" :title="formError" :closable="false"/>
        <el-button v-if="!readOnly" type="primary" native-type="submit" :loading="saving" :disabled="!filesReady || editLoading || (['student','staff'].includes(resource) && !impact) || (resource==='scope' && form.id && impact?.scopeId!==form.id) || (resource==='org' && form.id && (!impact || ((organizationMoved || (form.status==='DISABLED' && impact.hasReferences)) && !form.confirmImpact)))">确认并保存</el-button>
      </el-form>
    </el-dialog>
    <el-dialog v-model="passwordOpened" title="受控交付临时密码" width="560px" :close-on-click-modal="false" @closed="temporaryPassword = ''"><p>此密码仅用于本次交付，请单独告知本人；首次登录必须修改。</p><el-input :model-value="temporaryPassword" readonly show-password type="password" aria-label="本次重置的临时密码"/><p>关闭后不会再次显示。密码不进入普通人员导出和操作日志。</p></el-dialog>
  </section>
</template>
<script setup>
import { ElAlert, ElButton, ElCheckbox, ElDatePicker, ElDialog, ElForm, ElFormItem, ElInput, ElInputNumber, ElOption, ElPagination, ElRadioButton, ElRadioGroup, ElSelect, ElTable, ElTableColumn, ElLoading } from 'element-plus'
import 'element-plus/es/components/alert/style/css'
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/checkbox/style/css'
import 'element-plus/es/components/date-picker/style/css'
import 'element-plus/es/components/dialog/style/css'
import 'element-plus/es/components/form/style/css'
import 'element-plus/es/components/form-item/style/css'
import 'element-plus/es/components/input/style/css'
import 'element-plus/es/components/input-number/style/css'
import 'element-plus/es/components/option/style/css'
import 'element-plus/es/components/pagination/style/css'
import 'element-plus/es/components/radio-button/style/css'
import 'element-plus/es/components/radio-group/style/css'
import 'element-plus/es/components/select/style/css'
import 'element-plus/es/components/table/style/css'
import 'element-plus/es/components/loading/style/css'
const vLoading = ElLoading.directive

import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { get, save, download } from './systemApi'
import { getPermissionPatterns } from '@/security/permissionGate'
import { getVisibleNavPlan, matchPermission } from '@/config/navPlan'
import IdentityImportWorkspace from './IdentityImportWorkspace.vue'
import RoleWorkspace from './RoleWorkspace.vue'
import RoleImpactSummary from './RoleImpactSummary.vue'
import ConfigurationWorkspace from './ConfigurationWorkspace.vue'
import LeavePolicyWorkspace from './LeavePolicyWorkspace.vue'
import SystemObjectSelect from './SystemObjectSelect.vue'
import ResponsibilityHandoff from './ResponsibilityHandoff.vue'
import SystemAttachments from './SystemAttachments.vue'
import ConflictReview from './ConflictReview.vue'
import StudentBindingReview from './StudentBindingReview.vue'
const bindingStudent=ref(null),bindingOpened=ref(false)
const conflict=ref(null)
const route = useRoute(), router = useRouter(), resource = computed(() => route.meta.resource)
const special = computed(() => ['identity-import','role','brand','dictionary','notification','leave-policy'].includes(resource.value))
const taskStatuses={UPLOADED:'已上传',VALIDATING:'正在预检',VALIDATED:'预检通过',QUEUED:'已排队或正在整批处理',CONFIRMING:'正在确认',IMPORTED:'导入完成',FAILED:'失败',CANCELLED:'已取消',SUCCESS:'导出完成'}
const taskStatus=ref('')
const accountStatus=ref('')
const issueType=ref(''),issuePage=ref(1),scopeType=ref(''),scopeRefId=ref(''),scopeReviewOnly=ref(false),blockedPage=ref(1)
const searchLabel=computed(()=>resource.value==='task'?'搜索任务编号、文件或操作人':['migration','delivery'].includes(resource.value)?'搜索资料名称或来源':'搜索名称、编号或账号')
const auditStart=ref(String(route.query.start || '')),auditEnd=ref(String(route.query.end || ''))
function filters(){return {keyword:keyword.value,...(resource.value==='scope'?{issueType:issueType.value,issuePage:issuePage.value,scopeType:scopeType.value,refId:scopeRefId.value,reviewOnly:scopeReviewOnly.value,blockedPage:blockedPage.value}:{}),...(['staff','student'].includes(resource.value)?{accountStatus:accountStatus.value}:{}),...(resource.value==='task'?{status:taskStatus.value}:{}),...(resource.value==='audit'?{startAt:auditStart.value?new Date(auditStart.value).toISOString():undefined,endAt:auditEnd.value?new Date(auditEnd.value).toISOString():undefined}:{})}}
const data = ref(null), error = ref(''), receipt = ref(''), loading = ref(false), page = ref(1), keyword = ref(''), orgKind = ref('colleges')
const exporting=ref(false)
const orgLabels = { colleges: '院系', majors: '专业', classes: '年级班级', departments: '校内部门' }, scopeLabels = { COLLEGE: '院系', MAJOR: '专业', CLASS: '班级' }
const descriptions = { org: '组织名称可调整，已有引用的组织保留历史关系并通过停用退出使用。', staff: '维护教职工基础资料。指导、签到和巡访记录仍在实习中心的教师工作台账中办理。', student: '实习批次名单引用这里的同一份学生主档；开户与绑定通过师生导入完成。', account: '登录身份与人员档案分别维护。停用、解锁、重置和有效期调整会撤销旧登录会话。', scope: '责任人和负责对象以稳定编号关联。历史匹配不唯一的关系须核对后才授权。', task: '查看导入导出进度，刷新可读取后台处理结果。结果仅限任务发起人在有效期内领取，领取时重新核对权限和范围。', audit: '查询本校操作证据；学校端不提供删除或修改审计记录。', migration: '记录来源、差异对账和继续办理检查。登记记录不能代替真实数据与附件核验。', integration: '配置存在、连接可用和外部接收成功分别取证。', runtime: '运行检测与备份恢复证据分别展示。恢复数据库由实施人员按受控流程办理。', delivery: '登记手册、培训、备案与验收资料；学校登记状态不能替代原始证明。' }
const allowed = code => matchPermission(getPermissionPatterns(), code)
const canManage = computed(() => allowed(`system.${resource.value}.manage`))
function pathAllowed(path) {
  return getVisibleNavPlan({ permissionPatterns: getPermissionPatterns() }).some(g => g.children.some(m => m.children.some(p =>
    [p.path, ...(p.workspacePaths || [])].some(candidate => candidate === path || (!candidate.includes('?') && candidate === path.split('?')[0])))))
}
const endpoint = computed(() => ({ org: `/organizations/${orgKind.value}`, staff:'/people/staff',student:'/people/student',account:'/accounts',scope:'/scopes',task:'/tasks',audit:'/audit',integration:'/integrations',runtime:'/runtime',migration:'/records/MIGRATION',delivery:'/records/DOCUMENT',overview:'/overview' }[resource.value]))
let sequence = 0
async function load() {
  if (special.value) return
  const run = ++sequence; loading.value = true; error.value = ''
  try { const result = await get(endpoint.value, { page: page.value, pageSize: 30, ...filters() }); if (run === sequence) data.value = result }
  catch (e) { if (run === sequence) { data.value = null; error.value = e.message || '加载失败，请重试' } }
  finally { if (run === sequence) loading.value = false }
}
async function setPage(nextPage = 1) {
  const previousPath = route.fullPath
  await router.replace({ query: { ...route.query, page:nextPage > 1 ? String(nextPage) : undefined, search:keyword.value || undefined,
    start:resource.value==='audit'?auditStart.value || undefined:undefined,end:resource.value==='audit'?auditEnd.value || undefined:undefined,
    kind:resource.value==='org'?orgKind.value:undefined,status:resource.value==='task'?taskStatus.value || undefined:undefined,
    binding:['staff','student'].includes(resource.value)?accountStatus.value || undefined:undefined,
    issue:resource.value==='scope'?issueType.value || undefined:undefined,issuePage:resource.value==='scope' && issuePage.value>1?String(issuePage.value):undefined,
    scopeType:resource.value==='scope'?scopeType.value || undefined:undefined,refId:resource.value==='scope'?scopeRefId.value || undefined:undefined,review:resource.value==='scope' && scopeReviewOnly.value?'1':undefined } })
  if (route.fullPath === previousPath) await load()
}
function reset() { return setPage(1) }
async function setBlockedPage(value=1){await router.replace({query:{...route.query,blocked:'1',blockedPage:value>1?String(value):undefined}})}
async function setIssuePage(value=1){issuePage.value=value;await setPage(page.value)}
async function focusResponsibility(item){scopeType.value=item?.scopeType || '';scopeRefId.value=item?.id || '';if(item)scopeReviewOnly.value=false;await setPage(1)}
const contactOpened=ref(false),contactRow=ref(null),contactReason=ref(''),contactPhone=ref(''),contactError=ref(''),contactLoading=ref(false)
async function revealContact(){const target=contactRow.value;const area=resource.value;contactLoading.value=true;contactError.value='';contactPhone.value='';try{const result=await save(`/people/${resource.value}/${contactRow.value.id}/contact`,{reason:contactReason.value});if(contactOpened.value && contactRow.value===target && resource.value===area)contactPhone.value=result.phone || '未登记联系电话'}catch(e){contactError.value=e.message}finally{contactLoading.value=false}}
const filesReady=ref(true),viewFiles=ref([]),fileViewOpened=ref(false)
const readOnly=ref(false),retiringScope=ref(false)
const opened = ref(false), saving = ref(false), form = ref({}), formError = ref(''), impact = ref(null), roleOptions = ref([]), passwordOpened = ref(false), temporaryPassword = ref('')
const organizationMoved=computed(()=>resource.value==='org' && form.value.id && ['majors','classes'].includes(orgKind.value) && impact.value && String(form.value.parentId)!==String(impact.value.parentId))
let editSequence=0
const editLoading=ref(false)
const conflictInput=computed(()=>{
  const values={...form.value}
  if(resource.value==='org'){
    if(orgKind.value!=='majors')for(const key of ['educationYears','trainingLevel','nationalCode'])delete values[key]
    if(orgKind.value!=='classes')delete values.grade
  }
  return values
})
const dialogTitle = computed(() => retiringScope.value ? '停用待核对责任关系' : readOnly.value ? `查看${route.meta.title}` : resource.value === 'account' ? { RESET:'重置登录密码',DISABLE:'停用用户账号',ENABLE:'启用用户账号',UNLOCK:'解锁用户账号',EXPIRY:'调整账号有效期' }[form.value.action] : `维护${route.meta.title}`)
async function refreshImpact(){
  if(saving.value || !form.value.id)return
  const ticket=++editSequence
  if(resource.value!=='scope')form.value.confirmImpact=false
  impact.value=null;editLoading.value=true;formError.value=''
  const path=resource.value==='org' ? `/organizations/${orgKind.value}/${form.value.id}/impact` : resource.value==='scope' ? `/scopes/${form.value.id}/impact` : `/people/${resource.value}/${form.value.id}/impact`
  try{const result=await get(path);if(ticket===editSequence)impact.value=result}
  catch(e){if(ticket===editSequence)formError.value=e.message}
  finally{if(ticket===editSequence)editLoading.value=false}
}
async function edit(row, viewing=false, retiring=false) {
  if(saving.value)return
  const ticket=++editSequence,area=resource.value
  readOnly.value=viewing;retiringScope.value=area==='scope' && retiring
  conflict.value=null; formError.value = ''; impact.value = null; filesReady.value=true
  opened.value=true;editLoading.value=false
  const common = { id: row?.id, expectedVersion: row?.version || 0, reason:'',status:row?.status || 'ACTIVE' }
  if (area === 'org') {
    form.value = { ...common, name:row?.name || '',code:row?.code || '',parentId:row?.parentId || '',grade:row?.grade || '',educationYears:row?.educationYears || 3,trainingLevel:row?.trainingLevel || '',nationalCode:row?.nationalCode || '',confirmImpact:false }
    if(row?.id)await refreshImpact()
  }
  else if (['student','staff'].includes(area)) {
    form.value = { ...common,name:row.name,collegeId:row.collegeId || '',classId:row.classId || '',departmentId:row.departmentId || '',grade:row.grade || '',phone:'',confirmImpact:false }
    await refreshImpact()
  }
  else if (area === 'scope') {
    form.value = { ...common,userId:row?.userId || '',roleCode:row?.roleCode || '',scopeType:row?.scopeType || 'COLLEGE',refId:row?.refId || '' }
    if(retiringScope.value){await refreshImpact();return}
    editLoading.value=true
    roleOptions.value=[]
    try {const result=await get('/roles');if(ticket===editSequence){roleOptions.value=result.items;if(row?.id)await refreshImpact()}}
    catch(e){if(ticket===editSequence)formError.value=e.message}
    finally{if(ticket===editSequence)editLoading.value=false}
  }
  else form.value = { ...common,status:row?.status || 'PENDING',title:row?.title || '',ownerUserId:row?.ownerUserId || '',source:'',notes:'',mappingRules:'',identityMapping:'',exceptionResolution:'',expectedPeople:0,actualPeople:0,expectedRecords:0,actualRecords:0,expectedFiles:0,actualFiles:0,continuationChecked:false,fileIds:[],...(row?.details || {}) }
}
function accountEdit(row, action) { if(saving.value)return; readOnly.value=false; ++editSequence;editLoading.value=false;conflict.value=null; formError.value = ''; form.value = { id:row.id,name:row.name,loginName:row.loginName,expectedVersion:row.version,action,expiresAt:row.expiresAt ? new Date(row.expiresAt) : null,reason:'' }; opened.value = true }
async function submit() {
  if (readOnly.value || saving.value || editLoading.value || conflict.value || !filesReady.value || (['student','staff'].includes(resource.value) && !impact.value)) return
  if(resource.value==='scope' && form.value.id && impact.value?.scopeId!==form.value.id)return
  if(resource.value==='org' && form.value.id && (!impact.value || ((organizationMoved.value || (form.value.status==='DISABLED' && impact.value.hasReferences)) && !form.value.confirmImpact)))return
  const ticket=editSequence
  saving.value = true; formError.value = ''
  try {
    const { id, name, loginName, ...rest } = form.value
    const body = retiringScope.value ? {expectedVersion:rest.expectedVersion,reason:rest.reason} : resource.value === 'account' ? rest : { ...rest, ...(name !== undefined ? { name } : {}) }
    if(resource.value==='org')body.impactFingerprint=impact.value?.fingerprint || ''
    if(resource.value === 'account' && body.expiresAt) body.expiresAt = new Date(body.expiresAt).toISOString()
    const path = retiringScope.value ? `/scopes/${id}/retire` : resource.value === 'account' ? `/accounts/${id}/actions` : `${endpoint.value}${id ? '/'+id : ''}`
    const result = await save(path, body, id && resource.value !== 'account' && !retiringScope.value ? 'PUT' : 'POST')
    if(ticket!==editSequence)return
    opened.value = false; receipt.value = result.message || '已保存。下次办理将按最新配置裁定，历史记录保留。'
    if (result.temporaryPassword) { temporaryPassword.value = result.temporaryPassword; passwordOpened.value = true }
    await load()
  } catch (e) { if(ticket===editSequence){formError.value = e.message || '保存失败，输入已保留，请核对后重试'; conflict.value=e.details?.current ? e.details : null} }
  finally { if(ticket===editSequence)saving.value = false }
}
async function downloadResult(row){try{await download(`/tasks/${row.id}/result`,`任务${row.id}导出结果.xlsx`)}catch(e){error.value=e.message}}
async function exportAudit() { try { await download('/audit/export','操作审计.xlsx',filters()) } catch(e) { error.value = e.message } }
async function exportPeople(){
  if(exporting.value)return
  exporting.value=true;const run=sequence
  try{
    const kind=resource.value==='org'?orgKind.value:resource.value
    if(data.value?.total>5000){
      const result=await save('/exports/'+kind,filters())
      if(run===sequence)await router.push({path:'/admin/system/tasks',query:{search:result.id}})
    }else{
      const label=resource.value==='org'?orgLabels[orgKind.value]:resource.value==='staff'?'教职工':'学生'
      await download('/exports/'+kind,`${label}资料导出.xlsx`,filters())
    }
  }catch(e){if(run===sequence)error.value=e.message}finally{exporting.value=false}
}
async function retryExport(row){if(exporting.value)return;exporting.value=true;const run=sequence;try{await save(`/tasks/${row.id}/retry-export`,{expectedVersion:row.version});if(run===sequence)await load()}catch(e){if(run===sequence)error.value=e.message}finally{exporting.value=false}}
const dateText = value => value ? new Date(/Z$|[+-]\d\d:\d\d$/.test(value) ? value : value+'Z').toLocaleString('zh-CN') : '—'
const actionLabel = value => ({ LOGIN:'登录',LOGOUT:'退出登录',ROLE_SWITCH:'切换身份',ORG_SAVE:'维护组织',PERSON_SAVE:'维护人员',ROLE_SAVE:'调整角色权限',ROLE_MEMBER:'调整角色成员',SCOPE_SAVE:'调整责任范围',IDENTITY_PREVIEW:'师生导入预检',IDENTITY_CONFIRM:'确认师生开户',IDENTITY_RECEIPT_DOWNLOAD:'领取开户回执',ACCOUNT_RESET:'重置账号密码',ACCOUNT_DISABLE:'停用账号',ACCOUNT_ENABLE:'启用账号',ACCOUNT_UNLOCK:'解锁账号',ACCOUNT_EXPIRY:'调整有效期',CONFIG_SAVE:'修改学校配置',DELIVERY_RECORD:'登记交付资料',AUDIT_EXPORT:'导出审计' }[value] || '业务操作（可凭对象编号追溯）')
watch(() => route.fullPath, () => {
  ++editSequence;readOnly.value=false;retiringScope.value=false;editLoading.value=false;impact.value=null;saving.value=false
  ++sequence; bindingOpened.value=false; contactOpened.value=false; contactPhone.value=''; data.value=null; error.value=''; receipt.value=''; opened.value=false; temporaryPassword.value=''
  const requestedPage=Number(route.query.page)
  page.value=Number.isSafeInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1
  keyword.value=String(route.query.search || '')
  taskStatus.value=resource.value==='task' && Object.hasOwn(taskStatuses,String(route.query.status)) ? String(route.query.status) : ''
  accountStatus.value=['staff','student'].includes(resource.value) && ['BOUND','UNBOUND'].includes(String(route.query.binding)) ? String(route.query.binding) : ''
  const requestedBlockedPage=Number(route.query.blockedPage)
  blockedPage.value=resource.value==='scope' && Number.isSafeInteger(requestedBlockedPage) && requestedBlockedPage>0?requestedBlockedPage:1
  scopeReviewOnly.value=resource.value==='scope' && route.query.review==='1'
  issueType.value=resource.value==='scope' && ['MISSING','DUPLICATE'].includes(String(route.query.issue)) ? String(route.query.issue) : ''
  const requestedIssuePage=Number(route.query.issuePage)
  issuePage.value=resource.value==='scope' && Number.isSafeInteger(requestedIssuePage) && requestedIssuePage>0 ? requestedIssuePage : 1
  const hasScope=resource.value==='scope' && Object.hasOwn(scopeLabels,String(route.query.scopeType)) && /^\d+$/.test(String(route.query.refId || ''))
  scopeType.value=hasScope ? String(route.query.scopeType) : '';scopeRefId.value=hasScope ? String(route.query.refId) : ''
  orgKind.value=Object.hasOwn(orgLabels,String(route.query.kind)) ? String(route.query.kind) : 'colleges'
  auditStart.value=resource.value==='audit' ? String(route.query.start || '') : ''
  auditEnd.value=resource.value==='audit' ? String(route.query.end || '') : ''
  load()
}, { immediate: true })
</script>
<style scoped>
.toolbar>.el-select{width:240px;max-width:100%}
.system-workspace{padding:24px;max-width:1500px;margin:auto;color:var(--t1)}.page-heading{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:24px}.eyebrow{font-size:12px;color:var(--t3);margin:0 0 8px}h1{font-size:24px;margin:0}h2{font-size:18px;margin-top:28px}.description{color:var(--t2);line-height:1.8}.toolbar{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:20px 0}.toolbar>.el-input{width:240px}.el-pagination{margin:22px 0}.el-alert{margin:14px 0}.overview-counts{display:flex;gap:20px}.overview-counts article{background:var(--surface);border:1px solid var(--line);padding:24px;min-width:180px;display:flex;gap:20px;align-items:center;border-radius:12px}.overview-counts strong{font-size:30px}.setup-steps{display:flex;flex-wrap:wrap;gap:20px;padding:20px 36px;background:var(--surface);border:1px solid var(--line);border-radius:12px}.setup-steps li{padding-right:20px}.issue-list{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}.issue-list article{padding:18px;display:flex;justify-content:space-between;align-items:center;border:1px solid var(--line);border-radius:10px}.issue-list article div{display:flex;gap:16px}.issue-list strong{font-size:22px}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.el-form .el-select{width:100%}details{margin:20px 0}.system-workspace a{color:var(--pri)}@media(max-width:800px){.system-workspace{padding:14px}.issue-list,.form-grid{grid-template-columns:1fr}.overview-counts{flex-wrap:wrap}h1{font-size:20px}}
</style>
