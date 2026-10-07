<template>
  <ModulePageShell
    :title="pageTitle"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="aaev-tabs" aria-label="教学评价业务入口">
      <button
        v-for="item in tabs"
        :key="item.key"
        :class="['aaev-tab', { 'is-active': queryTab === item.key }]"
        @click="switchTab(item.key)"
      >{{ item.label }}</button>
    </div>

    <div class="aaev-page-head">
      <div>
        <div class="aaev-breadcrumb">教务中心 / 教学质量 / {{ pageTitle }}</div>
        <div class="aaev-page-purpose">{{ pagePurpose }}</div>
      </div>
      <AppButton v-if="hasObjectSelection" variant="ghost" size="small" @click="returnToQueue">返回原队列</AppButton>
    </div>

    <div v-if="showLifecycle" class="aaev-stage-rail" aria-label="评价业务流程">
      <div v-for="(stage, index) in lifecycleStages" :key="stage" :class="['aaev-stage', stageClass(index)]">
        <span class="aaev-stage-dot">{{ index < lifecycleIndex ? '✓' : index + 1 }}</span>
        <span><strong>{{ stage }}</strong><small>{{ lifecycleHints[index] }}</small></span>
      </div>
    </div>

    <AppInlineAlert v-if="readError" type="danger" :description="readError" />
    <div v-if="readError" class="aaev-retry">
      <AppButton :loading="loading" @click="reloadView">重新加载当前视图</AppButton>
    </div>

    <template v-else>
      <!-- AA-234 评价批次 -->
      <div v-if="queryTab === 'batches'" class="mp-stack">
        <div class="aaev-toolbar">
          <span>应评任务只从正式教学任务生成；生命周期动作以服务端复查结果为准。</span>
          <AppButton v-if="canManage" variant="primary" size="small" @click="openCreate">创建评价批次</AppButton>
        </div>
        <div class="aaev-metrics">
          <Metric label="当前页批次" :value="rows.length" :hint="'服务端第 ' + batchPagination.page + ' 页'" />
          <Metric label="待启动" :value="batchStatusCount('DRAFT')" hint="需先生成正式应评任务" />
          <Metric label="评价进行中" :value="batchStatusCount('OPEN')" hint="当前页处于开放窗口" />
          <Metric label="待核算或归档" :value="batchStatusCount('RESULT_READY')" hint="需完成发布或申诉核验" warning />
        </div>
        <div class="aaev-layout">
          <section class="aaev-list-pane aaev-card">
            <div class="aaev-card-title">教学评价批次</div>
            <AppTextInput v-model="batchKeyword" placeholder="搜索本页批次名称" />
            <EmptyState v-if="!filteredBatches.length" title="暂无评价批次" description="当前数据范围内没有符合条件的批次" />
            <ul v-else class="aaev-list">
              <BatchItem v-for="batch in filteredBatches" :key="batch.batchId" :batch="batch" :active="current?.batchId === batch.batchId" @select="select(batch)" />
            </ul>
            <AppPagination :total="batchPagination.total" :page="batchPagination.page" :page-size="batchPagination.pageSize" :show-size-changer="false" @change="onBatchPaginationChange" />
          </section>
          <section class="aaev-detail">
            <EmptyState v-if="!current" title="选择评价批次" description="查看来源、当前责任、业务阻断和正式办理动作" />
            <template v-else>
              <ObjectCard
                :title="current.batchName"
                :meta="`评价批次 #${current.batchId} · 学期 ${current.termId || '未绑定'} · ${current.anonymous ? '学生匿名' : '非匿名配置'}`"
                :status="bLabel(current.status)"
                :status-type="bType(current.status)"
                :current-role="currentResponsibility"
                :next-role="nextResponsibility"
              />
              <div class="aaev-context-grid">
                <InfoCell label="对象来源" :value="`正式教学任务 / 批次 #${current.batchId}`" />
                <InfoCell label="为什么轮到我" :value="whyMine" />
                <InfoCell label="当前阻断" :value="currentBlocker" />
                <InfoCell label="已评回执" :value="`${submittedTaskCount} 次提交 / ${tasks.length} 个任务槽`" />
              </div>
              <div v-if="canManage" class="aaev-actions aaev-primary-actions">
                <AppButton v-if="current.status === 'DRAFT'" size="small" variant="ghost" @click="openGenTasks">生成应评任务</AppButton>
                <AppButton v-if="current.status === 'DRAFT'" size="small" variant="primary" :disabled="!tasks.length" @click="lc('publish', '发布批次')">发布批次</AppButton>
                <AppButton v-if="current.status === 'PUBLISHED'" size="small" variant="primary" @click="lc('open', '开放评教')">开放评教</AppButton>
                <AppButton v-if="current.status === 'OPEN'" size="small" variant="warning" @click="lc('closeScore', '关闭并核算')">关闭并核算</AppButton>
                <AppButton v-if="current.status === 'RESULT_READY'" size="small" variant="primary" @click="lc('publishResults', '发布结果')">发布结果</AppButton>
                <AppButton v-if="current.status === 'RESULT_READY'" size="small" variant="ghost" @click="lc('archive', '归档批次')">归档批次</AppButton>
              </div>
              <section class="aaev-card">
                <div class="aaev-card-title"><span>应评任务</span><small>提交数取自正式答卷事实</small></div>
                <EmptyState v-if="!tasks.length" title="未生成应评任务" description="草稿阶段从正式教学任务生成；非学生评价须指定真实评价人" />
                <DataTable v-else :columns="taskColumns" :rows="visibleTasks" row-key="taskId" :pagination="taskPagination" @page-change="onTaskPageChange">
                  <template #cell-evaluatorType="{ row }">{{ evaluatorLabel(row.evaluatorType) }}</template>
                  <template #cell-status="{ row }"><StatusTag :type="row.status === 'SUBMITTED' ? 'success' : 'primary'" :label="academicStatusLabel(row.status)" dot /></template>
                </DataTable>
              </section>
              <ResultTable v-if="results.length" :rows="results" :columns="resultColumns" :pagination="resultPagination" @page-change="onResultPageChange" />
            </template>
          </section>
        </div>
      </div>

      <!-- AA-235 申诉审核 -->
      <div v-else-if="queryTab === 'appeals'" class="mp-stack">
        <AppInlineAlert type="info" description="申诉按当前账号数据范围收敛：学院只做本学院初审，教务处完成终审；审核意见与正式结果分开留痕。" />
        <div class="aaev-layout aaev-appeal-layout">
          <section class="aaev-list-pane aaev-card">
            <div class="aaev-card-title"><span>责任队列</span><small>{{ appeals.length }} 条 / 总计 {{ appealPagination.total }} 条</small></div>
            <EmptyState v-if="!appeals.length" title="暂无申诉" description="当前岗位范围内没有待处理或已处理的评价申诉" />
            <DataTable
              v-else
              :columns="appealColumns"
              :rows="appeals"
              row-key="appealId"
              row-clickable
              :pagination="appealPagination"
              @row-click="selectAppeal"
              @page-change="onAppealPageChange"
            >
              <template #cell-object="{ row }"><strong>申诉 #{{ row.appealId }}</strong><small class="aaev-cell-meta">结果 #{{ row.resultId }} · {{ row.teacherKey || '教师标识缺失' }}</small></template>
              <template #cell-status="{ row }"><StatusTag :type="appealType(row.status)" :label="appealLabel(row.status)" dot /></template>
            </DataTable>
          </section>
          <section class="aaev-detail">
            <EmptyState v-if="!selectedAppeal" title="选择评价申诉" description="先核验对象、结果标识和申诉理由，再办理当前节点" />
            <template v-else>
              <ObjectCard
                :title="`评价申诉 #${selectedAppeal.appealId}`"
                :meta="`正式结果 #${selectedAppeal.resultId} · 教师 ${selectedAppeal.teacherKey || '—'}`"
                :status="appealLabel(selectedAppeal.status)"
                :status-type="appealType(selectedAppeal.status)"
                :current-role="appealCurrentRole"
                :next-role="appealNextRole"
              />
              <div class="aaev-evidence-grid">
                <Evidence title="来源对象与身份" status="服务端范围已核验" type="success">
                  申诉 #{{ selectedAppeal.appealId }} 关联结果 #{{ selectedAppeal.resultId }}，教师标识 {{ selectedAppeal.teacherKey || '接口未返回' }}。
                </Evidence>
                <Evidence title="当前结果版本" status="以 resultId 锁定" type="warning">
                  当前接口未提供展示版本号；审核命令严格锁定结果 #{{ selectedAppeal.resultId }}，不以列表位置代替对象。
                </Evidence>
                <Evidence title="材料与事实依据" status="申诉原文" type="success" wide>{{ selectedAppeal.reason || '申诉人未提供理由' }}</Evidence>
                <Evidence title="既有审核意见" :status="selectedAppeal.reviewReason ? '已有留痕' : '暂无留痕'" :type="selectedAppeal.reviewReason ? 'success' : 'default'" wide>
                  {{ selectedAppeal.reviewReason || '当前节点尚未形成正式审核意见。' }}
                </Evidence>
              </div>
              <div v-if="canReviewAppeal && ['SUBMITTED','COLLEGE_REVIEW'].includes(selectedAppeal.status)" class="aaev-actions aaev-primary-actions">
                <AppButton variant="primary" :disabled="confirmSubmitting" @click="approveAppeal(selectedAppeal)">{{ appealApproveLabel(selectedAppeal) }}</AppButton>
                <AppButton variant="danger" :disabled="confirmSubmitting" @click="rejectAppeal(selectedAppeal)">驳回申诉</AppButton>
              </div>
              <AppInlineAlert v-else-if="['SUBMITTED','COLLEGE_REVIEW'].includes(selectedAppeal.status)" type="warning" description="当前账号可查看本对象，但没有申诉审核权限；请交由当前责任岗位办理。" />
            </template>
          </section>
        </div>
      </div>

      <!-- AA-236 学生评教：教师 PC 管理视角 -->
      <div v-else-if="queryTab === 'studentEval'" class="mp-stack">
        <AppInlineAlert type="info" description="学生评教在教师 PC 仅展示匿名任务完成情况。本人匿名问卷由学生端按正式教学班名单核验后提交，教师端不读取或暴露评价人身份。" />
        <div class="aaev-layout">
          <section class="aaev-list-pane aaev-card">
            <div class="aaev-card-title">评价批次</div>
            <ul class="aaev-list">
              <BatchItem v-for="batch in rows" :key="batch.batchId" :batch="batch" :active="current?.batchId === batch.batchId" @select="selectTyped(batch)" />
            </ul>
            <AppPagination :total="batchPagination.total" :page="batchPagination.page" :page-size="batchPagination.pageSize" :show-size-changer="false" @change="onBatchPaginationChange" />
          </section>
          <section class="aaev-detail">
            <EmptyState v-if="!current" title="选择评教批次" description="查看学生匿名评教任务与实际提交数量" />
            <template v-else>
              <ObjectCard :title="current.batchName + ' · 学生评教'" :meta="`批次 #${current.batchId} · 匿名身份不在本页展示`" :status="bLabel(current.status)" :status-type="bType(current.status)" current-role="学生本人" next-role="评价核算岗" />
              <section class="aaev-card">
                <div class="aaev-card-title"><span>匿名任务完成情况</span><small>{{ submittedTaskCount }} 次正式提交</small></div>
                <EmptyState v-if="!tasks.length" title="暂无学生评教任务" description="请在评价批次草稿阶段从正式教学任务生成" />
                <DataTable v-else :columns="studentTaskColumns" :rows="visibleTasks" row-key="taskId" :pagination="taskPagination" @page-change="onTaskPageChange">
                  <template #cell-status="{ row }"><StatusTag :type="row.status === 'SUBMITTED' ? 'success' : 'primary'" :label="academicStatusLabel(row.status)" dot /></template>
                </DataTable>
              </section>
            </template>
          </section>
        </div>
      </div>

      <!-- AA-237~239 教师本人评价任务 -->
      <div v-else-if="viewMode === 'byType'" class="mp-stack">
        <AppInlineAlert type="info" :description="rolePrivacyNotice" />
        <div class="aaev-layout">
          <section class="aaev-list-pane aaev-card">
            <div class="aaev-card-title"><span>我的{{ typeViewLabel }}任务</span><small>{{ roleTasks.length }} 条</small></div>
            <EmptyState v-if="!roleTasks.length" :title="'暂无' + typeViewLabel + '任务'" description="任务由评价批次按正式教学任务及指定评价人生成" />
            <ul v-else class="aaev-list">
              <li
                v-for="task in roleTasks"
                :key="task.taskId"
                :class="['aaev-item', { 'is-active': selectedTask?.taskId === task.taskId }]"
                role="button"
                tabindex="0"
                :aria-current="selectedTask?.taskId === task.taskId ? 'true' : undefined"
                @click="selectRoleTask(task)"
                @keydown.enter.prevent="selectRoleTask(task)"
                @keydown.space.prevent="selectRoleTask(task)"
              >
                <span><strong>{{ task.courseName || '课程未命名' }}</strong><small>任务 #{{ task.taskId }} · {{ task.teacherName || '授课教师未返回' }}</small></span>
                <StatusTag :type="task.status === 'SUBMITTED' ? 'success' : 'primary'" :label="academicStatusLabel(task.status)" dot />
              </li>
            </ul>
          </section>
          <section class="aaev-detail">
            <EmptyState v-if="!selectedTask" :title="'选择' + typeViewLabel + '任务'" description="每次提交只锁定当前 taskId，提交后重新读取本人任务状态" />
            <template v-else>
              <ObjectCard
                :title="selectedTask.courseName + ' · ' + typeViewLabel"
                :meta="`任务 #${selectedTask.taskId} · 批次 #${selectedTask.batchId} · 被评教师 ${selectedTask.teacherName || '—'}`"
                :status="selectedTask.status === 'SUBMITTED' ? '已提交' : bLabel(selectedTask.batchStatus)"
                :status-type="selectedTask.status === 'SUBMITTED' ? 'success' : bType(selectedTask.batchStatus)"
                :current-role="ctx.currentRole.roleName || '任务指定评价人'"
                next-role="评价核算岗 → 结果发布"
              />
              <div class="aaev-notice"><strong>评价身份与结果权限分开</strong><span>{{ rolePrivacyDetail }}</span></div>
              <section class="aaev-card aaev-questionnaire">
                <div class="aaev-card-title"><span>{{ typeViewLabel }}问卷</span><small>提交当前任务，不直接产生发布结果</small></div>
                <div v-for="(question, index) in questionnaireItems" :key="question.key" class="aaev-question">
                  <div><strong>{{ index + 1 }}. {{ question.label }}</strong><small>{{ question.hint }}</small></div>
                  <AppRadioGroup v-model="answers[question.key]" :options="ratingOptions" size="compact" :disabled="!canSubmitRoleTask || saving" />
                </div>
                <AppFormItem :label="roleEvidenceLabel" required>
                  <AppTextarea v-model="evaluationEvidence" :rows="3" :maxlength="500" show-count :disabled="!canSubmitRoleTask || saving" :placeholder="roleEvidencePlaceholder" />
                </AppFormItem>
                <AppFormItem :label="roleCommentLabel">
                  <AppTextarea v-model="evaluationComment" :rows="3" :maxlength="1000" show-count :disabled="!canSubmitRoleTask || saving" :placeholder="roleCommentPlaceholder" />
                </AppFormItem>
                <AppInlineAlert v-if="roleFormError" type="danger" :description="roleFormError" />
                <div class="aaev-form-footer">
                  <span>客观分按五项等权换算：{{ evaluationScore === null ? '尚未完成' : evaluationScore + ' 分' }}</span>
                  <AppButton variant="primary" :disabled="!canSubmitRoleTask" :loading="saving" @click="openRoleSubmit">提交{{ typeViewLabel }}</AppButton>
                </div>
              </section>
            </template>
          </section>
        </div>
      </div>

      <!-- AA-240 评价统计 -->
      <div v-else-if="queryTab === 'evalStats'" class="mp-stack">
        <AppInlineAlert type="info" description="统计结果按当前账号数据范围由服务端裁定；学生匿名小样本保护及结果可见性不由前端推断。" />
        <div class="aaev-layout">
          <section class="aaev-list-pane aaev-card">
            <div class="aaev-card-title">统计批次</div>
            <ul class="aaev-list">
              <BatchItem v-for="batch in rows" :key="batch.batchId" :batch="batch" :active="current?.batchId === batch.batchId" @select="selectStats(batch)" />
            </ul>
            <AppPagination :total="batchPagination.total" :page="batchPagination.page" :page-size="batchPagination.pageSize" :show-size-changer="false" @change="onBatchPaginationChange" />
          </section>
          <section class="aaev-detail">
            <EmptyState v-if="!current" title="选择统计批次" description="查看等级分布、参评率和同口径结果明细" />
            <template v-else-if="stats">
              <ObjectCard :title="current.batchName + ' · 评价统计'" :meta="`批次 #${current.batchId} · 当前授权范围`" :status="bLabel(current.status)" :status-type="bType(current.status)" current-role="评价统计岗" next-role="结果发布 / 质量整改" />
              <div class="aaev-metrics is-three">
                <Metric label="范围内结果" :value="stats.resultCount ?? 0" hint="与下钻结果同一服务端范围" />
                <Metric label="学生均分均值" :value="stats.overallAvg ?? '—'" hint="无可见结果时不显示伪百分比" />
                <Metric label="待完成任务" :value="statsPendingCount" hint="各来源应评减已评" warning />
              </div>
              <div class="aaev-analytics-grid">
                <section class="aaev-card">
                  <div class="aaev-card-title">评价等级分布</div>
                  <div v-if="statsLevelRows.length" class="aaev-bars">
                    <div v-for="row in statsLevelRows" :key="row.level"><span>{{ row.level }}</span><i><b :style="{ width: row.percent + '%' }" /></i><strong>{{ row.count }}</strong></div>
                  </div>
                  <EmptyState v-else title="暂无等级结果" description="完成核算后由正式结果生成" />
                </section>
                <section class="aaev-card"><div class="aaev-card-title">各来源参评率</div><DataTable :columns="statsPartColumns" :rows="statsPartRows" row-key="type" /></section>
              </div>
              <ResultTable :rows="results" :columns="resultColumns" :pagination="resultPagination" title="同口径结果下钻" empty-title="暂无可见结果" @page-change="onResultPageChange" />
            </template>
          </section>
        </div>
      </div>

      <!-- AA-241 评价归档 -->
      <div v-else-if="queryTab === 'archive'" class="mp-stack">
        <AppInlineAlert type="info" description="归档批次与评价结果只读。归档前由服务端确认结果就绪且没有在途申诉；未发布草稿不会下发为档案。" />
        <EmptyState v-if="!archivedRows.length" title="暂无已归档批次" description="结果就绪且申诉已完成的批次归档后会出现在此" />
        <div v-else class="aaev-layout">
          <section class="aaev-list-pane aaev-card">
            <div class="aaev-card-title">评价档案</div>
            <ul class="aaev-list">
              <BatchItem v-for="batch in archivedRows" :key="batch.batchId" :batch="batch" :active="current?.batchId === batch.batchId" archive @select="select(batch)" />
            </ul>
            <AppPagination :total="archivePagination.total" :page="archivePagination.page" :page-size="archivePagination.pageSize" :show-size-changer="false" @change="onArchivePaginationChange" />
          </section>
          <section class="aaev-detail">
            <EmptyState v-if="!current" title="选择评价档案" description="查看批次原记录、正式结果和发布时间" />
            <template v-else>
              <ObjectCard :title="current.batchName" :meta="`档案批次 #${current.batchId} · 学期 ${current.termId || '未绑定'}`" status="已归档" status-type="default" current-role="档案查阅岗" :next-role="'结果发布时间：' + formatDateTime(current.resultPublishedAt)" />
              <div class="aaev-notice"><strong>只读封存</strong><span>当前接口未返回独立 Manifest 版本号；本页使用批次 ID 与结果 ID 作为正式对象标识，任何纠错必须另走受控流程。</span></div>
              <ResultTable :rows="results" :columns="archiveResultColumns" :pagination="resultPagination" title="评价档案 · 原记录与正式凭证" empty-title="无可见归档结果" archive @page-change="onResultPageChange" />
            </template>
          </section>
        </div>
      </div>
    </template>

    <AppDrawer :visible="createVisible" title="新建评教批次" mode="modal" size="medium" @close="createVisible = false">
      <div class="aaev-form">
        <AppFormItem label="批次名称" required><AppTextInput v-model="form.batchName" placeholder="如 2026秋第1批教学评价" :disabled="saving" /></AppFormItem>
        <AppFormItem label="正式学期" required><AppTermEntityPicker v-model="form.termId" placeholder="选择正式学期" :disabled="saving" /></AppFormItem>
        <AppInlineAlert type="info" description="学生评教强制匿名；问卷模板与学期在服务端再次校验。创建成功仅形成草稿，不代表已经发布。" />
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer><AppButton variant="ghost" :disabled="saving" @click="createVisible = false">取消</AppButton><AppButton variant="primary" :loading="saving" @click="submitCreate">创建批次</AppButton></template>
    </AppDrawer>

    <AppDrawer :visible="genVisible" title="生成应评任务" mode="modal" size="medium" @close="genVisible = false">
      <div class="aaev-form">
        <AppFormItem label="评价来源"><AppSelect v-model="genType" :options="genTypeOptions" :disabled="saving" /></AppFormItem>
        <AppFormItem label="正式教学任务" required><AppTeachingTaskPicker v-model="genTaskIds" multiple :query="{ termId: current?.termId || undefined }" :disabled="saving" /></AppFormItem>
        <AppFormItem v-if="['PEER','SUPERVISOR'].includes(genType)" label="指定评价人工号 / 用户标识" required><AppTextInput v-model="genEvaluatorKey" placeholder="必须与评价人登录身份匹配" :disabled="saving" /></AppFormItem>
        <AppInlineAlert type="info" :description="genTaskHint" />
        <AppInlineAlert v-if="genError" type="danger" :description="genError" />
      </div>
      <template #footer><AppButton variant="ghost" :disabled="saving" @click="genVisible = false">取消</AppButton><AppButton variant="primary" :loading="saving" @click="submitGen">生成任务</AppButton></template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirmVisible"
      :title="confirmTitle"
      :message="confirmMessage"
      :confirm-text="confirmText"
      :require-reason="confirmRequireReason"
      :reason-label="confirmReasonLabel"
      :submitting="confirmSubmitting"
      @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** AA-234~AA-241 教学评价：批次、本人任务、核算统计、申诉审核和只读归档。 */
import { h } from 'vue'
import { ModulePageShell, DataTable, StatusTag, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppTextarea, AppFormItem, AppSelect, AppRadioGroup, AppConfirmDialog, AppInlineAlert, AppTermEntityPicker, AppTeachingTaskPicker, AppPagination } from '@/components/common'
import { academicAffairsApi, academicAffairsEvaluationApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { academicStatusLabel } from '@/modules/academicAffairs/constants/academic-display.constants'
import { matchPermission } from '@/config/navPlan'
import { toast } from '@/utils/toast'
import { currentUserFromToken } from '@/services/http/client'

const _BL = { DRAFT: '草稿', PUBLISHED: '已发布批次', OPEN: '评价进行中', CLOSED: '已关闭', RESULT_READY: '结果就绪', ARCHIVED: '已归档' }
const _LV = { EXCELLENT: '优秀', GOOD: '良好', PASS: '合格', NEED_IMPROVE: '需整改' }
const _EL = { STUDENT: '学生评教', SELF: '教师自评', PEER: '同行评价', SUPERVISOR: '督导评价' }
const _AL = { SUBMITTED: '待学院初审', COLLEGE_REVIEW: '待教务终审', RESOLVED: '已通过', REJECTED: '已驳回' }
const freshPagination = (pageSize) => ({ page: 1, pageSize, total: 0 })
const freshAnswers = () => ({ preparation: '', objective: '', organization: '', feedback: '', alignment: '' })

const Metric = {
  props: { label: String, value: [String, Number], hint: String, warning: Boolean },
  render() { return h('div', { class: ['aaev-metric', { 'is-warn': this.warning }] }, [h('span', this.label), h('strong', String(this.value)), h('small', this.hint)]) }
}
const InfoCell = {
  props: { label: String, value: String },
  render() { return h('div', [h('span', this.label), h('strong', this.value)]) }
}
const ObjectCard = {
  props: { title: String, meta: String, status: String, statusType: String, currentRole: String, nextRole: String },
  render() {
    return h('div', { class: 'aaev-object-card' }, [
      h('div', [h('div', { class: 'aaev-title' }, this.title), h('div', { class: 'aaev-object-meta' }, this.meta)]),
      h(StatusTag, { type: this.statusType, label: this.status, dot: true }),
      h('div', { class: 'aaev-responsibility' }, [
        h('span', ['当前责任', h('strong', this.currentRole)]),
        h('span', ['下一责任', h('strong', this.nextRole)])
      ])
    ])
  }
}
const BatchItem = {
  props: { batch: Object, active: Boolean, archive: Boolean },
  emits: ['select'],
  methods: { activate() { this.$emit('select') } },
  render() {
    return h('li', {
      class: ['aaev-item', { 'is-active': this.active }],
      role: 'button', tabindex: 0, 'aria-current': this.active ? 'true' : undefined,
      onClick: this.activate, onKeydown: (event) => { if (['Enter', ' '].includes(event.key)) { event.preventDefault(); this.activate() } }
    }, [
      h('span', [h('strong', this.batch.batchName), h('small', `批次 #${this.batch.batchId} · 学期 ${this.batch.termId || '未绑定'}`)]),
      h(StatusTag, {
        type: this.archive || ['ARCHIVED', 'CLOSED'].includes(this.batch.status)
          ? 'default'
          : (this.batch.status === 'OPEN' ? 'success' : this.batch.status === 'RESULT_READY' ? 'warning' : 'primary'),
        label: this.archive ? '已归档' : (_BL[this.batch.status] || this.batch.status),
        dot: true
      })
    ])
  }
}
const Evidence = {
  props: { title: String, status: String, type: String, wide: Boolean },
  render() { return h('article', { class: { 'is-wide': this.wide } }, [h('div', [h('strong', this.title), h(StatusTag, { type: this.type, label: this.status })]), h('p', this.$slots.default?.())]) }
}
const ResultTable = {
  props: { rows: Array, columns: Array, pagination: Object, title: { type: String, default: '评价结果' }, emptyTitle: { type: String, default: '暂无评价结果' }, archive: Boolean },
  emits: ['page-change'],
  render() {
    const slots = {
      'cell-level': ({ row }) => h(StatusTag, { type: row.level === 'EXCELLENT' ? 'success' : row.level === 'NEED_IMPROVE' ? 'danger' : 'primary', label: _LV[row.level] || '等级待确认', dot: true }),
      'cell-published': ({ row }) => row.published ? '已发布' : '未发布'
    }
    if (this.archive) slots['cell-proof'] = ({ row }) => `结果 #${row.resultId}`
    return h('section', { class: 'aaev-card' }, [
      h('div', { class: 'aaev-card-title' }, this.title),
      !this.rows?.length ? h(EmptyState, { title: this.emptyTitle, description: '服务端未返回当前数据范围内的结果' }) : h(DataTable, { columns: this.columns, rows: this.rows, rowKey: 'resultId', pagination: this.pagination, onPageChange: (page) => this.$emit('page-change', page) }, slots)
    ])
  }
}

export default {
  name: 'AaEvaluationConsoleView',
  components: {
    ModulePageShell, DataTable, StatusTag, EmptyState, AppButton, AppDrawer, AppTextInput, AppTextarea,
    AppFormItem, AppSelect, AppRadioGroup, AppConfirmDialog, AppInlineAlert, AppTermEntityPicker,
    AppTeachingTaskPicker, AppPagination, Metric, InfoCell, ObjectCard, BatchItem, Evidence, ResultTable
  },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' }, permissionPatterns: [] },
      tabs: [
        { key: 'batches', label: '评价批次' }, { key: 'appeals', label: '申诉审核' },
        { key: 'studentEval', label: '学生评教' }, { key: 'selfEval', label: '教师自评' },
        { key: 'peerEval', label: '同行评价' }, { key: 'supervisorEval', label: '督导评价' },
        { key: 'evalStats', label: '评价统计' }, { key: 'archive', label: '评价归档' }
      ],
      typeViewMap: {
        selfEval: { type: 'SELF', label: '教师自评' },
        peerEval: { type: 'PEER', label: '同行评价' },
        supervisorEval: { type: 'SUPERVISOR', label: '督导评价' }
      },
      pageMeta: {
        batches: ['评价批次', '应评任务从正式教学任务产生', '创建批次、生成任务、开放窗口、核算发布并交接申诉归档。'],
        appeals: ['申诉审核', '结果发布、申诉与复核版本分开', '先核验来源结果和当前节点，再由学院初审、教务终审形成正式意见。'],
        studentEval: ['学生评教', '匿名任务完成情况', '教师 PC 查看匿名任务完成事实；学生本人在学生端按正式名单提交。'],
        selfEval: ['教师自评', '自评任务来自本人正式教学任务', '本人只办理分配给当前账号的自评任务，提交后交评价核算岗。'],
        peerEval: ['同行评价', '同行范围与自评范围分开', '指定同行依据听课事实评价当前教学任务，不替代教师自评。'],
        supervisorEval: ['督导评价', '评价与质量整改分开办理', '督导记录观察事实并提交评价；需要整改时由质量整改流程承接。'],
        evalStats: ['评价统计', '授权结果与参评口径', '按服务端数据范围查看等级、参评率与同口径结果下钻。'],
        archive: ['评价归档', '未发布草稿不形成档案', '只读查看已归档批次和正式结果标识，受控纠错另走流程。']
      },
      lifecycleStages: ['创建批次', '生成任务', '评价提交', '核算发布', '申诉归档'],
      lifecycleHints: ['上游任务可回查', '绑定任务和评价人', '按任务身份提交', '按真实答卷核算', '申诉完成后封存'],
      queryTab: 'batches',
      rows: [], archivedRows: [], current: null, tasks: [], results: [], appeals: [], selectedAppeal: null, stats: null,
      roleTasks: [], selectedTask: null, answers: freshAnswers(), evaluationEvidence: '', evaluationComment: '', roleFormError: '',
      resultSeq: 0, selectionSeq: 0, roleSeq: 0, queueSeq: 0, viewSeq: 0, readError: '', loading: false, batchKeyword: '',
      batchPagination: freshPagination(30), archivePagination: freshPagination(30),
      taskPagination: freshPagination(20), resultPagination: freshPagination(50), appealPagination: freshPagination(50),
      taskColumns: [
        { key: 'courseName', title: '课程' }, { key: 'teacherName', title: '教师' },
        { key: 'evaluatorType', title: '评价来源' }, { key: 'submittedCount', title: '正式提交数' },
        { key: 'status', title: '任务状态' }
      ],
      studentTaskColumns: [
        { key: 'courseName', title: '课程' }, { key: 'teacherName', title: '被评教师' },
        { key: 'submittedCount', title: '匿名已评数' }, { key: 'status', title: '任务状态' }
      ],
      resultColumns: [
        { key: 'teacherName', title: '教师' }, { key: 'courseName', title: '课程' },
        { key: 'studentAvg', title: '学生均分' }, { key: 'supervisorAvg', title: '督导' },
        { key: 'peerAvg', title: '同行' }, { key: 'selfScore', title: '自评' },
        { key: 'compositeScore', title: '综合分' }, { key: 'level', title: '等级' },
        { key: 'published', title: '发布状态' }
      ],
      archiveResultColumns: [
        { key: 'courseName', title: '课程' }, { key: 'teacherName', title: '教师' },
        { key: 'compositeScore', title: '综合分' }, { key: 'level', title: '等级' },
        { key: 'published', title: '发布状态' }, { key: 'proof', title: '正式凭证' }
      ],
      statsPartColumns: [
        { key: 'type', title: '来源' }, { key: 'total', title: '应评' },
        { key: 'submitted', title: '已评' }, { key: 'rate', title: '参评率' }
      ],
      appealColumns: [{ key: 'object', title: '申诉对象' }, { key: 'status', title: '当前节点' }],
      createVisible: false, form: { batchName: '', termId: '' }, formError: '',
      genVisible: false, genTaskIds: [], genType: 'STUDENT', genEvaluatorKey: '', genError: '',
      genTypeOptions: [
        { label: '学生评教', value: 'STUDENT' }, { label: '教师自评', value: 'SELF' },
        { label: '同行评价', value: 'PEER' }, { label: '督导评价', value: 'SUPERVISOR' }
      ],
      ratingOptions: [
        { label: '很好', value: 4 }, { label: '较好', value: 3 },
        { label: '一般', value: 2 }, { label: '需改进', value: 1 }
      ],
      questionnaireItems: [
        { key: 'preparation', label: '教学准备充分', hint: '备课、资源与课堂准备事实' },
        { key: 'objective', label: '教学目标清晰', hint: '目标与正式课程任务的一致性' },
        { key: 'organization', label: '课堂组织有序', hint: '教学组织与课堂节奏' },
        { key: 'feedback', label: '反馈及时有效', hint: '指导、答疑与学习反馈' },
        { key: 'alignment', label: '实践与课程目标一致', hint: '实践任务与培养目标对应关系' }
      ],
      saving: false, confirmVisible: false, confirmTitle: '', confirmMessage: '',
      confirmText: '确认操作', pendingAction: null, confirmRequireReason: false,
      confirmReasonLabel: '', confirmSubmitting: false
    }
  },
  computed: {
    identityKey() {
      const user = currentUserFromToken() || {}
      return JSON.stringify([user.tenantId, user.userId, user.activeContextId, user.currentRoleCode, this.ctx.currentRole, this.ctx.dataScope, this.ctx.permissionPatterns])
    },
    pageTitle() { return (this.pageMeta[this.queryTab] || this.pageMeta.batches)[0] },
    pageSubtitle() { return (this.pageMeta[this.queryTab] || this.pageMeta.batches)[1] },
    pagePurpose() { return (this.pageMeta[this.queryTab] || this.pageMeta.batches)[2] },
    viewMode() { return this.typeViewMap[this.queryTab] ? 'byType' : this.queryTab },
    typeViewLabel() { return (this.typeViewMap[this.queryTab] || {}).label || '' },
    typeFilter() { return (this.typeViewMap[this.queryTab] || {}).type || '' },
    showLifecycle() { return ['batches', 'appeals', 'archive'].includes(this.queryTab) },
    lifecycleIndex() {
      if (this.queryTab === 'appeals' || this.queryTab === 'archive') return 4
      const indexes = { DRAFT: this.tasks.length ? 1 : 0, PUBLISHED: 2, OPEN: 2, RESULT_READY: 3, ARCHIVED: 4 }
      return this.current ? (indexes[this.current.status] ?? 0) : 2
    },
    hasObjectSelection() { return Boolean(this.current || this.selectedAppeal || this.selectedTask) },
    canManage() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.evaluation.batch.manage') },
    canReviewAppeal() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.evaluation.appeal.review') },
    filteredBatches() {
      const keyword = this.batchKeyword.trim().toLowerCase()
      return keyword ? this.rows.filter((batch) => String(batch.batchName || '').toLowerCase().includes(keyword)) : this.rows
    },
    visibleTasks() {
      const start = (this.taskPagination.page - 1) * this.taskPagination.pageSize
      return this.tasks.slice(start, start + this.taskPagination.pageSize)
    },
    submittedTaskCount() { return this.tasks.reduce((sum, task) => sum + Number(task.submittedCount || 0), 0) },
    currentResponsibility() {
      return ({ DRAFT: '评价责任岗', PUBLISHED: '窗口开放岗', OPEN: '评价人 / 核算岗', RESULT_READY: '结果发布与申诉复核岗', ARCHIVED: '档案查阅岗' })[this.current?.status] || '评价责任岗'
    },
    nextResponsibility() {
      return ({ DRAFT: '评价人', PUBLISHED: '评价人', OPEN: '评价核算岗', RESULT_READY: '申诉复核岗 / 档案岗', ARCHIVED: '受控纠错流程' })[this.current?.status] || '评价核算岗'
    },
    whyMine() { return this.canManage ? '当前账号具备批次管理权限，且对象在当前数据范围内' : '对象在当前账号可查看的数据范围内' },
    currentBlocker() {
      if (!this.current) return '未选择对象'
      if (this.current.status === 'DRAFT' && !this.current.termId) return '未绑定正式学期，服务端将拒绝后续写入'
      if (this.current.status === 'DRAFT' && !this.tasks.length) return '尚未生成正式应评任务'
      if (this.current.status === 'RESULT_READY') return '归档前必须完成在途申诉'
      return '服务端未返回当前阻断'
    },
    appealCurrentRole() {
      return this.selectedAppeal?.status === 'SUBMITTED' ? '所属学院评价复核岗'
        : this.selectedAppeal?.status === 'COLLEGE_REVIEW' ? '教务处评价终审岗' : '已完成处理'
    },
    appealNextRole() {
      return this.selectedAppeal?.status === 'SUBMITTED' ? '教务处评价终审岗'
        : this.selectedAppeal?.status === 'COLLEGE_REVIEW' ? '结果发布 / 归档岗' : '返回原申诉队列'
    },
    statsLevelRows() {
      const byLevel = this.stats?.byLevel || {}
      const total = Object.values(byLevel).reduce((sum, value) => sum + Number(value || 0), 0)
      return Object.keys(byLevel).map((key) => ({
        level: this.lvLabel(key), count: Number(byLevel[key] || 0),
        percent: total ? Math.round(Number(byLevel[key] || 0) / total * 100) : 0
      }))
    },
    statsPartRows() {
      const participation = this.stats?.participation || {}
      return Object.keys(participation).map((key) => ({
        type: this.evaluatorLabel(key), total: participation[key].total,
        submitted: participation[key].submitted, rate: `${participation[key].rate}%`
      }))
    },
    statsPendingCount() {
      return this.statsPartRows.reduce((sum, row) => sum + Math.max(0, Number(row.total || 0) - Number(row.submitted || 0)), 0)
    },
    evaluationScore() {
      const values = Object.values(this.answers).map(Number)
      if (values.some((value) => !value)) return null
      const points = { 4: 100, 3: 85, 2: 70, 1: 55 }
      return Math.round(values.reduce((sum, value) => sum + points[value], 0) / values.length)
    },
    canSubmitRoleTask() {
      return Boolean(this.selectedTask && this.selectedTask.status !== 'SUBMITTED' && this.selectedTask.batchStatus === 'OPEN' && !this.saving && !this.confirmSubmitting)
    },
    roleEvidenceLabel() { return this.typeFilter === 'PEER' ? '听课证据' : this.typeFilter === 'SUPERVISOR' ? '观察事实' : '自评依据' },
    roleEvidencePlaceholder() {
      return this.typeFilter === 'PEER' ? '填写听课时间、课堂与可核验事实'
        : this.typeFilter === 'SUPERVISOR' ? '填写课堂观察事实，避免只写结论' : '填写本学期教学任务、材料或改进依据'
    },
    roleCommentLabel() { return this.typeFilter === 'SUPERVISOR' ? '整改建议（选填）' : '评价说明（选填）' },
    roleCommentPlaceholder() { return this.typeFilter === 'SUPERVISOR' ? '写明问题和建议；正式整改仍需另建质量整改任务' : '补充与评分有关的具体说明' },
    rolePrivacyNotice() { return `当前只读取登录账号的${this.typeViewLabel}任务；任务身份来自服务端 evaluatorKey 校验，列表不会混入其他评价人的任务。` },
    rolePrivacyDetail() {
      return this.typeFilter === 'SELF' ? '本人身份仅用于核验自评任务归属；结果由核算岗按既定权重处理。'
        : '评价人身份用于任务归属和审计，被评教师只在结果正式发布后按授权范围查看结果。'
    },
    genTaskHint() {
      if (this.genType === 'STUDENT') return '学生任务强制匿名，提交资格由正式教学班名单版本裁定。'
      if (this.genType === 'SELF') return '自评任务自动使用教学任务中的授课教师标识作为评价人。'
      return '同行或督导任务必须指定真实评价人标识，提交时服务端会核验登录身份。'
    }
  },
  watch: {
    '$route.query.tab'(value) {
      this.resetSelection()
      this.queryTab = this.validTab(value)
      this.reloadView()
    },
    identityKey() {
      this.resetSelection()
      this.confirmVisible = false
      this.pendingAction = null
      this.reloadView()
    }
  },
  beforeUnmount() { this.resultSeq++; this.selectionSeq++; this.roleSeq++; this.queueSeq++; this.viewSeq++ },
  async created() {
    const response = await academicAffairsApi.getContext()
    if (response.code === 0) this.ctx = response.data
    this.queryTab = this.validTab(this.$route?.query?.tab)
    await this.reloadView()
  },
  methods: {
    academicStatusLabel,
    validTab(value) { return this.tabs.some((item) => item.key === value) ? value : 'batches' },
    resetSelection() {
      this.resultSeq++; this.selectionSeq++; this.roleSeq++
      this.queueSeq++; this.viewSeq++
      this.rows = []; this.archivedRows = []; this.appeals = []
      this.batchPagination.total = 0; this.archivePagination.total = 0; this.appealPagination.total = 0
      this.current = null; this.tasks = []; this.results = []; this.stats = null
      this.taskPagination.page = 1; this.taskPagination.total = 0
      this.selectedAppeal = null; this.roleTasks = []; this.selectedTask = null
      this.readError = ''; this.resetQuestionnaire()
    },
    async reloadView() {
      const seq = ++this.viewSeq
      this.loading = true
      this.readError = ''
      try {
        if (this.queryTab === 'appeals') await this.loadAppeals()
        else if (this.queryTab === 'archive') await this.loadArchived()
        else if (this.viewMode === 'byType') await this.loadRoleTasks()
        else await this.loadBatches()
      } finally { if (seq === this.viewSeq) this.loading = false }
    },
    bLabel(status) { return _BL[status] || academicStatusLabel(status) },
    bType(status) { return status === 'OPEN' ? 'success' : ['ARCHIVED', 'CLOSED'].includes(status) ? 'default' : status === 'RESULT_READY' ? 'warning' : 'primary' },
    lvLabel(level) { return _LV[level] || '等级待确认' },
    evaluatorLabel(type) { return _EL[type] || '评价人类型待确认' },
    appealLabel(status) { return _AL[status] || academicStatusLabel(status) },
    appealApproveLabel(row) { return row.status === 'SUBMITTED' ? '学院初审通过' : '教务终审通过' },
    appealType(status) { return status === 'RESOLVED' ? 'success' : status === 'REJECTED' ? 'danger' : status === 'COLLEGE_REVIEW' ? 'warning' : 'primary' },
    batchStatusCount(status) { return this.rows.filter((row) => row.status === status).length },
    stageClass(index) { return index < this.lifecycleIndex ? 'is-done' : index === this.lifecycleIndex ? 'is-current' : '' },
    formatDateTime(value) {
      if (!value) return '接口未返回'
      const date = new Date(value)
      return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('zh-CN', { hour12: false })
    },
    switchTab(key) {
      if (this.confirmSubmitting || key === this.queryTab) return
      this.$router.replace({ query: { tab: key } })
    },
    syncObjectQuery(values) {
      this.$router.replace({ query: { ...this.$route.query, batchId: undefined, taskId: undefined, appealId: undefined, ...values } })
    },
    returnToQueue() { this.resetSelection(); this.syncObjectQuery({}) },
    async loadBatches() {
      const seq = ++this.queueSeq, identity = this.identityKey, tab = this.queryTab, page = this.batchPagination.page
      const current = () => seq === this.queueSeq && identity === this.identityKey && tab === this.queryTab && page === this.batchPagination.page
      this.rows = []; this.batchPagination.total = 0; this.readError = ''
      try {
        const res = await api.listBatches({ page: this.batchPagination.page, pageSize: this.batchPagination.pageSize })
        if (!current()) return
        if (res.code !== 0) { this.readError = res.message || '评价批次加载失败'; return }
        this.rows = res.data.list
        this.batchPagination.total = res.data.total
        const requested = String(this.$route?.query?.batchId || '')
        const target = this.rows.find((row) => String(row.batchId) === requested)
        if (target) {
          if (this.queryTab === 'studentEval') await this.selectTyped(target, false)
          else if (this.queryTab === 'evalStats') await this.selectStats(target, false)
          else await this.select(target, false)
        }
      } catch (error) { if (current()) this.readError = error?.message || '评价批次加载失败' }
    },
    async loadArchived() {
      const seq = ++this.queueSeq, identity = this.identityKey, tab = this.queryTab, page = this.archivePagination.page
      const current = () => seq === this.queueSeq && identity === this.identityKey && tab === this.queryTab && page === this.archivePagination.page
      this.archivedRows = []; this.archivePagination.total = 0; this.readError = ''
      try {
        const res = await api.archivedBatches({ page: this.archivePagination.page, pageSize: this.archivePagination.pageSize })
        if (!current()) return
        if (res.code !== 0) { this.readError = res.message || '评价归档批次加载失败'; return }
        this.archivedRows = res.data.list
        this.archivePagination.total = res.data.total
        const target = this.archivedRows.find((row) => String(row.batchId) === String(this.$route?.query?.batchId || ''))
        if (target) await this.select(target, false)
      } catch (error) { if (current()) this.readError = error?.message || '评价归档批次加载失败' }
    },
    onBatchPaginationChange({ page }) {
      if (!page || page === this.batchPagination.page) return
      this.batchPagination.page = page
      this.current = null; this.tasks = []; this.results = []; this.stats = null
      this.taskPagination.page = 1; this.taskPagination.total = 0
      this.syncObjectQuery({})
      this.loadBatches()
    },
    onArchivePaginationChange({ page }) {
      if (!page || page === this.archivePagination.page) return
      this.archivePagination.page = page
      this.current = null; this.tasks = []; this.results = []
      this.taskPagination.page = 1; this.taskPagination.total = 0
      this.syncObjectQuery({})
      this.loadArchived()
    },
    async loadCurrentResults() {
      if (!this.current) { this.results = []; this.resultPagination.total = 0; return }
      const seq = ++this.resultSeq
      const id = this.current.batchId
      const identity = this.identityKey
      const page = this.resultPagination.page
      const current = () => seq === this.resultSeq && id === this.current?.batchId && identity === this.identityKey && page === this.resultPagination.page
      try {
        const res = await api.results(id, { page: this.resultPagination.page, pageSize: this.resultPagination.pageSize })
        if (!current()) return
        if (res.code === 0) {
          this.results = res.data.list
          this.resultPagination.total = res.data.total
        } else this.readError = res.message || '评价结果加载失败'
      } catch (error) {
        if (current()) this.readError = error?.message || '评价结果加载失败'
      }
    },
    async select(batch, sync = true) {
      if (this.confirmSubmitting) return
      this.current = { ...batch }; this.tasks = []; this.results = []; this.readError = ''
      this.taskPagination.page = 1; this.taskPagination.total = 0
      this.resultPagination.page = 1
      if (sync) this.syncObjectQuery({ batchId: batch.batchId })
      const seq = ++this.selectionSeq
      const identity = this.identityKey
      const id = batch.batchId
      const current = () => seq === this.selectionSeq && identity === this.identityKey && id === this.current?.batchId
      try {
        const response = await api.listTasks(id)
        if (!current()) return
        if (response.code !== 0) { this.readError = response.message || '应评任务加载失败'; return }
        this.tasks = response.data.items || []
        this.taskPagination.total = this.tasks.length
      } catch (error) {
        if (current()) this.readError = error?.message || '应评任务加载失败'
        return
      }
      if (current()) await this.loadCurrentResults()
    },
    async selectTyped(batch, sync = true) {
      if (this.confirmSubmitting) return
      this.current = { ...batch }; this.tasks = []; this.results = []; this.readError = ''
      this.taskPagination.page = 1; this.taskPagination.total = 0
      if (sync) this.syncObjectQuery({ batchId: batch.batchId })
      const seq = ++this.selectionSeq
      const identity = this.identityKey
      const id = batch.batchId
      const current = () => seq === this.selectionSeq && identity === this.identityKey && id === this.current?.batchId
      try {
        const response = await api.listTasks(id, { evaluatorType: 'STUDENT' })
        if (!current()) return
        if (response.code === 0) {
          this.tasks = response.data.items || response.data.list || []
          this.taskPagination.total = this.tasks.length
        }
        else this.readError = response.message || '学生评教任务加载失败'
      } catch (error) {
        if (current()) this.readError = error?.message || '学生评教任务加载失败'
      }
    },
    async selectStats(batch, sync = true) {
      if (this.confirmSubmitting) return
      this.current = { ...batch }; this.stats = null; this.results = []; this.readError = ''
      this.resultPagination.page = 1
      if (sync) this.syncObjectQuery({ batchId: batch.batchId })
      const seq = ++this.selectionSeq
      const identity = this.identityKey
      const id = batch.batchId
      const current = () => seq === this.selectionSeq && identity === this.identityKey && id === this.current?.batchId
      try {
        const response = await api.stats(id)
        if (!current()) return
        if (response.code === 0) this.stats = response.data
        else { this.readError = response.message || '评价统计加载失败'; return }
      } catch (error) {
        if (current()) this.readError = error?.message || '评价统计加载失败'
        return
      }
      if (current()) await this.loadCurrentResults()
    },
    onResultPageChange(page) {
      if (!page || page === this.resultPagination.page) return
      this.resultPagination.page = page
      this.loadCurrentResults()
    },
    onTaskPageChange(page) {
      if (!page || page === this.taskPagination.page) return
      this.taskPagination.page = page
    },
    async loadAppeals() {
      const seq = ++this.queueSeq, identity = this.identityKey, tab = this.queryTab, page = this.appealPagination.page
      const current = () => seq === this.queueSeq && identity === this.identityKey && tab === this.queryTab && page === this.appealPagination.page
      this.appeals = []; this.appealPagination.total = 0; this.readError = ''
      try {
        const res = await api.listAppeals({ page: this.appealPagination.page, pageSize: this.appealPagination.pageSize })
        if (!current()) return
        if (res.code !== 0) { this.readError = res.message || '申诉列表加载失败'; return }
        this.appeals = res.data.list
        this.appealPagination.total = res.data.total
        const target = this.appeals.find((row) => String(row.appealId) === String(this.$route?.query?.appealId || ''))
        if (target) this.selectAppeal(target, false)
      } catch (error) { if (current()) this.readError = error?.message || '申诉列表加载失败' }
    },
    selectAppeal(row, sync = true) {
      this.selectedAppeal = { ...row }
      if (sync) this.syncObjectQuery({ appealId: row.appealId })
    },
    onAppealPageChange(page) {
      if (!page || page === this.appealPagination.page) return
      this.appealPagination.page = page
      this.selectedAppeal = null
      this.syncObjectQuery({})
      this.loadAppeals()
    },
    async loadRoleTasks() {
      const seq = ++this.roleSeq
      const identity = this.identityKey
      const type = this.typeFilter
      try {
        const response = await api.myRoleTasks(type)
        if (seq !== this.roleSeq || identity !== this.identityKey || type !== this.typeFilter) return
        if (response.code !== 0) { this.readError = response.message || `${this.typeViewLabel}任务加载失败`; return }
        this.roleTasks = response.data.items || []
        const target = this.roleTasks.find((task) => String(task.taskId) === String(this.$route?.query?.taskId || ''))
        if (target) this.selectRoleTask(target, false)
      } catch (error) {
        if (seq === this.roleSeq) this.readError = error?.message || `${this.typeViewLabel}任务加载失败`
      }
    },
    selectRoleTask(task, sync = true) {
      if (this.confirmSubmitting) return
      this.selectedTask = { ...task }
      this.resetQuestionnaire()
      if (sync) this.syncObjectQuery({ taskId: task.taskId, batchId: task.batchId })
    },
    resetQuestionnaire() {
      this.answers = freshAnswers()
      this.evaluationEvidence = ''
      this.evaluationComment = ''
      this.roleFormError = ''
    },
    openRoleSubmit() {
      if (!this.canSubmitRoleTask) return
      if (this.evaluationScore === null) { this.roleFormError = '请完成全部五项评价'; return }
      if (this.evaluationEvidence.trim().length < 5) { this.roleFormError = `${this.roleEvidenceLabel}至少填写5字`; return }
      this.roleFormError = ''
      const taskId = this.selectedTask.taskId
      const taskName = `${this.selectedTask.courseName} / ${this.selectedTask.teacherName || '被评教师'}`
      const type = this.typeFilter
      const payload = {
        taskId,
        answers: { ...this.answers, evidence: this.evaluationEvidence.trim(), evaluatorType: type },
        objectiveScore: this.evaluationScore,
        comment: this.evaluationComment.trim() || undefined
      }
      this.confirmRequireReason = false
      this.confirmReasonLabel = ''
      this.confirmTitle = `提交${this.typeViewLabel}`
      this.confirmText = `确认提交${this.typeViewLabel}`
      this.confirmMessage = `确认提交任务 #${taskId}「${taskName}」？提交后不可重复提交，下一责任岗位为评价核算岗。`
      this.pendingAction = async () => {
        const response = await api.submit(payload)
        if (response.code !== 0) { toast.error(response.message || `${this.typeViewLabel}提交失败`); return false }
        toast.success(`${this.typeViewLabel}已提交，等待评价核算`)
        await this.loadRoleTasks()
        const fresh = this.roleTasks.find((task) => String(task.taskId) === String(taskId))
        if (fresh) this.selectRoleTask(fresh, false)
        return true
      }
      this.confirmVisible = true
    },
    openCreate() {
      this.form = { batchName: '', termId: '' }
      this.formError = ''
      this.createVisible = true
    },
    async submitCreate() {
      if (!this.form.batchName.trim()) { this.formError = '批次名称必填'; return }
      if (!this.form.termId) { this.formError = '请选择正式学期'; return }
      if (this.saving) return
      this.saving = true
      this.formError = ''
      try {
        const response = await api.createBatch({
          batchName: this.form.batchName.trim(),
          termId: this.form.termId,
          anonymous: true,
          template: { items: this.questionnaireItems.map((item) => ({ key: item.key, q: item.label, type: 'scale4' })) }
        })
        if (response.code === 0) {
          toast.success('评价批次草稿已创建')
          this.createVisible = false
          this.batchPagination.page = 1
          await this.loadBatches()
          const created = this.rows.find((row) => String(row.batchId) === String(response.data?.batchId))
          if (created) await this.select(created)
        } else this.formError = response.message || '评价批次创建失败'
      } catch (error) { this.formError = error?.message || '评价批次创建失败' } finally { this.saving = false }
    },
    openGenTasks() {
      this.genTaskIds = []
      this.genType = 'STUDENT'
      this.genEvaluatorKey = ''
      this.genError = ''
      this.genVisible = true
    },
    async submitGen() {
      const ids = this.genTaskIds
      if (!ids.length) { this.genError = '请选择正式教学任务'; return }
      if (['PEER', 'SUPERVISOR'].includes(this.genType) && !this.genEvaluatorKey.trim()) {
        this.genError = '同行或督导评价必须指定真实评价人标识'
        return
      }
      if (this.saving || !this.current) return
      const batchId = this.current.batchId
      const type = this.genType
      this.saving = true
      this.genError = ''
      try {
        const response = type === 'STUDENT'
          ? await api.genTasks(batchId, ids, 'STUDENT')
          : await api.genRoleTasks(batchId, type, ids.map((teachingTaskId) => ({
              teachingTaskId,
              evaluatorKey: type === 'SELF' ? undefined : this.genEvaluatorKey.trim()
            })))
        if (response.code === 0) {
          toast.success(`已生成 ${response.data.taskCount} 条${this.evaluatorLabel(type)}任务`)
          this.genVisible = false
          await this.select({ ...this.current }, false)
        } else this.genError = response.message || '生成应评任务失败'
      } catch (error) { this.genError = error?.message || '生成应评任务失败' } finally { this.saving = false }
    },
    lc(fn, label) {
      if (!this.current || this.confirmSubmitting || !this.canManage) return
      const batchId = this.current.batchId
      const batchName = this.current.batchName
      const expectedStatus = this.current.status
      this.confirmRequireReason = false
      this.confirmReasonLabel = ''
      this.confirmTitle = label
      this.confirmText = `确认${label}`
      this.confirmMessage = `确认对批次 #${batchId}「${batchName}」执行“${label}”？当前状态 ${this.bLabel(expectedStatus)}，服务端将重新校验对象状态与权限。`
      this.pendingAction = async () => {
        const response = await api[fn](batchId)
        if (response.code !== 0) { toast.error(response.message || `${label}失败`); return false }
        toast.success(`${label}成功`)
        await this.loadBatches()
        const batch = this.rows.find((row) => String(row.batchId) === String(batchId))
        if (batch) await this.select(batch, false)
        else {
          const fresh = await api.getBatch(batchId)
          if (fresh.code === 0) await this.select(fresh.data, false)
        }
        return true
      }
      this.confirmVisible = true
    },
    approveAppeal(row) {
      if (this.confirmSubmitting || !this.canReviewAppeal) return
      const isCollegeStage = row.status === 'SUBMITTED'
      const stageLabel = isCollegeStage ? '学院初审' : '教务终审'
      this.confirmRequireReason = true
      this.confirmReasonLabel = `${stageLabel}意见（≥5 字）`
      this.confirmTitle = `${stageLabel}通过`
      this.confirmText = `确认${stageLabel}通过`
      this.confirmMessage = `确认对申诉 #${row.appealId}、结果 #${row.resultId} 执行${stageLabel}通过？服务端将按当前账号数据范围复核本级权限。`
      this.pendingAction = async (reason) => {
        const note = String(reason || '').trim()
        const res = await api.reviewAppeal(row.appealId, 'RESOLVE', note)
        if (res.code !== 0) { toast.error(res.message); return false }
        toast.success(`${stageLabel}已通过`)
        await this.loadAppeals()
        const fresh = this.appeals.find((item) => item.appealId === row.appealId)
        if (fresh) this.selectAppeal(fresh, false)
        return true
      }
      this.confirmVisible = true
    },
    rejectAppeal(row) {
      if (this.confirmSubmitting || !this.canReviewAppeal) return
      const id = row.appealId
      this.confirmRequireReason = true
      this.confirmReasonLabel = '驳回原因（≥5 字）'
      this.confirmTitle = '驳回申诉'
      this.confirmText = '确认驳回申诉'
      this.confirmMessage = `确认驳回申诉 #${row.appealId}（结果 #${row.resultId}）？原因将写入审计并通知申诉人。`
      this.pendingAction = async (reason) => {
        const res = await api.reviewAppeal(id, 'REJECT', String(reason || '').trim())
        if (res.code !== 0) { toast.error(res.message); return false }
        toast.success('申诉已驳回')
        await this.loadAppeals()
        const fresh = this.appeals.find((item) => item.appealId === id)
        if (fresh) this.selectAppeal(fresh, false)
        return true
      }
      this.confirmVisible = true
    },
    async onConfirm(payload = {}) {
      if (this.confirmSubmitting || !this.pendingAction) return
      const action = this.pendingAction
      this.confirmSubmitting = true
      try {
        const ok = await action(payload && payload.reason)
        if (ok) {
          this.confirmVisible = false
          this.pendingAction = null
          this.confirmRequireReason = false
          this.confirmReasonLabel = ''
        }
      } catch (error) {
        toast.error(error?.message || '操作失败')
      } finally {
        this.confirmSubmitting = false
      }
    }
  }
}
</script>

<style scoped>
.aaev-tabs { display: flex; gap: 4px; overflow-x: auto; border-bottom: 1px solid var(--border-color, #dbe4f0); margin-bottom: 14px; }
.aaev-tab { flex: 0 0 auto; white-space: nowrap; padding: 9px 14px; border: 0; border-bottom: 2px solid transparent; background: transparent; color: var(--text-secondary, #5e718d); cursor: pointer; }
.aaev-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); background: var(--primary-50, #eff6ff); font-weight: 600; }
.aaev-page-head, .aaev-toolbar, .aaev-card-title, .aaev-form-footer { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.aaev-page-head { margin-bottom: 14px; }
.aaev-breadcrumb { color: var(--text-tertiary, #789); font-size: 13px; margin-bottom: 5px; }
.aaev-page-purpose, .aaev-toolbar { color: var(--text-secondary, #526987); font-size: 14px; }
.aaev-stage-rail { display: grid; grid-template-columns: repeat(5, 1fr); gap: 0; padding: 16px; margin-bottom: 16px; border: 1px solid var(--border-color, #dbe4f0); border-radius: 10px; background: var(--bg-card, #fff); }
.aaev-stage { position: relative; display: flex; gap: 10px; align-items: flex-start; color: var(--text-tertiary, #8090a6); }
.aaev-stage::after { position: absolute; content: ''; height: 1px; background: var(--border-color, #dbe4f0); top: 14px; left: 36px; right: 8px; }
.aaev-stage:last-child::after { display: none; }
.aaev-stage-dot { position: relative; z-index: 1; display: grid; place-items: center; width: 28px; height: 28px; border: 1px solid var(--border-color, #dbe4f0); border-radius: 50%; background: #fff; font-size: 12px; flex: 0 0 auto; }
.aaev-stage strong, .aaev-stage small { display: block; }
.aaev-stage strong { font-size: 13px; }
.aaev-stage small { margin-top: 4px; font-size: 11px; }
.aaev-stage.is-done .aaev-stage-dot { color: #147d52; border-color: #b5e2ce; background: #eefaf4; }
.aaev-stage.is-current { color: var(--primary-700, #1d4fa3); }
.aaev-stage.is-current .aaev-stage-dot { color: #fff; border-color: var(--primary-600, #2563eb); background: var(--primary-600, #2563eb); }
.aaev-retry, .aaev-toolbar { margin-bottom: 12px; }
.aaev-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
.aaev-metrics.is-three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
:deep(.aaev-metric) { padding: 15px; border: 1px solid var(--border-color, #dbe4f0); border-radius: 10px; background: var(--bg-card, #fff); }
:deep(.aaev-metric.is-warn) { border-color: #f0ce96; background: #fff8e9; }
:deep(.aaev-metric span), :deep(.aaev-metric small) { display: block; color: var(--text-secondary, #60738e); }
:deep(.aaev-metric strong) { display: block; margin: 5px 0; color: var(--text-primary, #18314f); font-size: 26px; }
:deep(.aaev-metric small) { font-size: 12px; }
.aaev-layout { display: grid; grid-template-columns: 280px minmax(0, 1fr); gap: 16px; }
.aaev-appeal-layout { grid-template-columns: 320px minmax(0, 1fr); }
.aaev-list-pane, .aaev-detail { min-width: 0; }
.aaev-card { padding: 16px; border: 1px solid var(--border-color, #dbe4f0); border-radius: 10px; background: var(--bg-card, #fff); }
.aaev-card + .aaev-card { margin-top: 14px; }
.aaev-card-title { margin-bottom: 13px; color: var(--text-primary, #18314f); font-weight: 600; }
.aaev-card-title small { color: var(--text-tertiary, #789); font-weight: 400; }
.aaev-list { list-style: none; margin: 12px 0 0; padding: 0; display: flex; flex-direction: column; gap: 7px; max-height: 620px; overflow: auto; }
.aaev-list-pane :deep(.app-pagination) { margin-top: 12px; }
:deep(.aaev-item) { display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 11px 12px; border: 1px solid var(--border-color, #dbe4f0); border-radius: 8px; cursor: pointer; }
:deep(.aaev-item > span:first-child) { min-width: 0; }
:deep(.aaev-item strong), :deep(.aaev-item small) { display: block; }
:deep(.aaev-item strong) { overflow-wrap: anywhere; font-size: 13px; }
:deep(.aaev-item small) { margin-top: 4px; color: var(--text-tertiary, #789); font-size: 11px; }
:deep(.aaev-item.is-active) { border-color: var(--primary-color, #2563eb); background: var(--primary-50, #eff6ff); }
:deep(.aaev-item:focus-visible) { outline: 2px solid var(--primary-color, #2563eb); outline-offset: 2px; }
:deep(.aaev-object-card) { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px 16px; align-items: start; padding: 15px; margin-bottom: 14px; border: 1px solid var(--border-color, #dbe4f0); border-left: 3px solid var(--primary-600, #2563eb); border-radius: 10px; background: var(--bg-card, #fff); }
:deep(.aaev-title) { color: var(--text-primary, #18314f); font-size: 17px; font-weight: 700; }
:deep(.aaev-object-meta) { margin-top: 5px; color: var(--text-secondary, #60738e); font-size: 12px; }
:deep(.aaev-responsibility) { grid-column: 1 / -1; display: grid; grid-template-columns: 1fr 1fr; padding-top: 10px; border-top: 1px solid var(--border-color, #e4eaf2); }
:deep(.aaev-responsibility span) { color: var(--text-tertiary, #789); font-size: 12px; }
:deep(.aaev-responsibility strong) { display: block; margin-top: 3px; color: var(--text-primary, #18314f); }
.aaev-context-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-bottom: 14px; }
.aaev-context-grid > :deep(div) { padding: 12px; background: var(--bg-secondary, #f6f8fb); border-radius: 8px; }
.aaev-context-grid :deep(span), .aaev-context-grid :deep(strong) { display: block; }
.aaev-context-grid :deep(span) { color: var(--text-tertiary, #789); font-size: 12px; }
.aaev-context-grid :deep(strong) { margin-top: 5px; color: var(--text-primary, #18314f); font-size: 13px; }
.aaev-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.aaev-primary-actions { justify-content: flex-end; padding: 12px 0; }
.aaev-evidence-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.aaev-evidence-grid :deep(article) { padding: 14px; border: 1px solid var(--border-color, #dbe4f0); border-radius: 8px; background: var(--bg-card, #fff); }
.aaev-evidence-grid :deep(article.is-wide) { grid-column: 1 / -1; }
.aaev-evidence-grid :deep(article > div) { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
.aaev-evidence-grid :deep(p) { margin: 9px 0 0; color: var(--text-secondary, #526987); line-height: 1.65; white-space: pre-wrap; }
.aaev-notice { display: flex; gap: 10px; padding: 13px 15px; margin-bottom: 14px; border-radius: 9px; background: var(--primary-50, #edf4ff); color: var(--primary-800, #214b82); }
.aaev-notice span { line-height: 1.5; }
.aaev-question { display: grid; grid-template-columns: minmax(260px, 1fr) auto; gap: 16px; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--border-color, #e4eaf2); }
.aaev-question small { display: block; margin-top: 3px; color: var(--text-tertiary, #789); }
.aaev-questionnaire :deep(.app-form-item) { margin-top: 14px; }
.aaev-form-footer { margin-top: 14px; color: var(--text-secondary, #526987); }
.aaev-analytics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 14px; }
.aaev-analytics-grid .aaev-card + .aaev-card { margin-top: 0; }
.aaev-bars > div { display: grid; grid-template-columns: 64px minmax(0, 1fr) 34px; gap: 10px; align-items: center; margin: 14px 0; }
.aaev-bars i { height: 9px; overflow: hidden; border-radius: 999px; background: var(--bg-secondary, #edf2f8); }
.aaev-bars b { display: block; height: 100%; border-radius: inherit; background: var(--primary-600, #2563eb); }
.aaev-form { display: flex; flex-direction: column; gap: 12px; }
@media (max-width: 1080px) {
  .aaev-stage-rail { overflow-x: auto; grid-template-columns: repeat(5, 180px); }
  .aaev-metrics { grid-template-columns: repeat(2, 1fr); }
  .aaev-analytics-grid { grid-template-columns: 1fr; }
}
@media (max-width: 900px) {
  .aaev-layout { grid-template-columns: 1fr; }
  .aaev-list-pane { max-height: 380px; overflow: auto; padding: 12px; }
  .aaev-context-grid { grid-template-columns: 1fr; }
}
@media (max-width: 640px) {
  .aaev-tabs { overflow-x: auto; }
  .aaev-tab { flex: 0 0 auto; white-space: nowrap; }
  .aaev-page-head, .aaev-toolbar, .aaev-form-footer { align-items: stretch; flex-direction: column; }
  .aaev-metrics, .aaev-metrics.is-three { grid-template-columns: 1fr; }
  .aaev-question { grid-template-columns: 1fr; }
  .aaev-evidence-grid { grid-template-columns: 1fr; }
  .aaev-evidence-grid :deep(article.is-wide) { grid-column: auto; }
  :deep(.aaev-responsibility) { grid-template-columns: 1fr; gap: 10px; }
}
</style>
