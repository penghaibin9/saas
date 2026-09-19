<template>
  <ModulePageShell
    :title="currentTabLabel"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/graduation')">返回审核批次</AppButton>
    </template>

    <div class="mp-stack">
      <section v-if="actionReceipt" class="agc-receipt" role="status">
        <div><strong>{{ actionReceipt.verified ? '✓' : '…' }} {{ actionReceipt.title }}</strong><span>{{ actionReceipt.subject }} · {{ actionReceipt.businessId }}</span></div>
        <div><small>处理结果</small><b>{{ actionReceipt.result }}</b></div>
        <div><small>下一步</small><b>{{ actionReceipt.next }}</b></div>
      </section>
      <section class="agc-context" aria-label="毕业审核批次健康概览">
        <div class="agc-context__object">
          <span class="agc-eyebrow">当前毕业审核批次</span>
          <strong>{{ currentBatch ? currentBatch.batchName : '选择一个审核批次' }}</strong>
          <small>{{ currentBatch ? `来源：毕业审核批次 #${currentBatch.batchId} · 年级 ${currentBatch.gradeYear || '未指定'}` : '请先选择正式审核批次' }}</small>
          <AppGraduationBatchPicker
            v-model="batchId"
            :options="batchOptions"
            :disabled="loadingBatches || !!pendingWrite"
            :placeholder="loadingBatches ? '批次加载中…' : '选择批次'"
            @change="onBatchChange"
          />
        </div>
        <div><span>当前结论</span><strong>{{ batchHealthLabel || '等待选择' }}</strong><small>{{ currentBatch ? `系统通过 ${batchPassed} · 异常 ${batchAbnormal} · 已形成正式终审结论 ${batchConcluded}` : '选择批次后读取正式状态' }}</small></div>
        <div><span>当前责任</span><strong>{{ currentOwner }}</strong><small>{{ responsibilityReason }}</small></div>
        <div><span>当前阻断</span><strong :class="{ 'is-risk-text': batchAbnormal > 0 }">{{ currentBlocker }}</strong><small>建议下一动作：{{ batchNextAction }}</small></div>
        <div><span>下一岗位</span><strong>{{ nextOwner }}</strong><small>完成当前主动作后回到本批次原队列</small></div>
      </section>

      <GraduationStageRail :active="stageIndex" />
      <div v-if="currentBatch" class="agc-coverage"><span>终审覆盖度</span><b>{{ finalProgressPct }}%</b><i><em :style="{ width: `${finalProgressPct}%` }"></em></i></div>

      <EmptyState v-if="!loadingBatches && !batches.length" title="暂无审核批次" description="请先到「审核批次」页新建批次并执行预审" />

      <div class="agc-tabs" aria-label="毕业审核工作区">
        <button
          v-for="t in tabs"
          :key="t.key"
          :class="['agc-tab', { 'is-active': tab === t.key }]"
          @click="switchTab(t.key)"
        >{{ t.label }}</button>
      </div>

      <section v-if="showEvidenceBoard && queueRows.length" class="agc-evidence-board" aria-label="毕业资格证据办理工作区">
        <aside class="agc-queue">
          <header><strong>责任队列</strong><span>{{ pagination.total || queueRows.length }} 人</span></header>
          <button v-for="row in queueRows.slice(0, 8)" :key="row.resultId" :class="{ 'is-active': focusedRow && row.resultId === focusedRow.resultId }" @click="focusResult(row)">
            <span>{{ row.realName || row.studentName || `学生 ${row.studentId}` }}</span>
            <small>{{ row.studentNo || row.studentId }} · {{ statusLabel(row.status) }}</small>
          </button>
        </aside>
        <article v-if="focusedRow" class="agc-focus">
          <header>
            <div><span class="agc-eyebrow">当前学生对象</span><h2>{{ focusedRow.realName || focusedRow.studentName || `学生 ${focusedRow.studentId}` }}</h2><small>正式审核结果 #{{ focusedRow.resultId }} · 来源批次 #{{ focusedRow.batchId }}</small></div>
            <AppStatusTag :type="overallColor(focusedRow.overall)" dot>{{ overallLabel(focusedRow.overall) }}</AppStatusTag>
          </header>
          <div class="agc-focus__items">
            <div v-for="item in focusedItems" :key="item.item" class="agc-focus__item">
              <span>{{ itemLabel(item.item) }}</span>
              <AppStatusTag :type="gradItemColor(item.result)" dot>{{ itemResultLabel(item.result) }}</AppStatusTag>
              <p>{{ item.evidence || '当前正式证据未提供' }}</p>
              <small>证据责任：{{ ownerLabel(item.owner) }}<template v-if="item.refId"> · 来源对象 #{{ item.refId }}</template></small>
            </div>
          </div>
          <footer>
            <span>{{ currentBlocker }}</span>
            <AppButton variant="primary" @click="openDetail(focusedRow)">{{ tab === 'final' ? '核对十一项并终审' : '查看十一项完整证据' }}</AppButton>
          </footer>
        </article>
      </section>

      <template v-if="!batchId">
        <EmptyState title="请先选择批次" description="从上方选择一个审核批次后再进入具体审核工作区" />
      </template>

      <template v-else-if="['credit', 'practice', 'thesis', 'internship', 'discipline', 'fee'].includes(tab)">
        <AppInlineAlert
          v-if="tab === 'fee'"
          type="warning"
          description="费用结清默认显示“待治理”（不阻断）。财务未对接前，可由教务处人工标记为“已结清”或“欠费”，不得显示为已自动通过。"
        />
        <ErrorState v-if="error" :description="error" @retry="loadTab" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" :title="`暂无${currentTabLabel}数据`" description="批次尚未执行预审，或该项供数为空" />
        <DataTable
          v-else
          :columns="itemColumns"
          :rows="rows"
          row-key="resultId"
          :pagination="pagination"
          @page-change="onPageChange"
        >
          <template #cell-result="{ row }">
            <AppStatusTag :type="gradItemColor(itemOf(row).result)" dot>{{ itemResultLabel(itemOf(row).result) }}</AppStatusTag>
          </template>
          <template #cell-evidence="{ row }">
            <span class="agc-evidence">{{ itemOf(row).evidence || '—' }}</span>
          </template>
          <template #cell-ops="{ row }">
            <template v-if="tab === 'fee'">
              <button class="mp-link" :disabled="feeBusy || !canManagePermission || !!pendingWrite" @click="markFee(row, 'CLEARED')">勾选已结清</button>
              <button class="mp-link" :disabled="feeBusy || !canManagePermission || !!pendingWrite" @click="markFee(row, 'OWED')">勾选仍欠费</button>
            </template>
            <router-link v-else-if="linkFor(row)" class="mp-link" :to="linkFor(row)">跳转责任模块</router-link>
            <button class="mp-link" @click="openDetail(row)">十一项详情</button>
          </template>
        </DataTable>
      </template>

      <template v-else-if="tab === 'course'">
        <ErrorState v-if="error" :description="error" @retry="loadCourseTab" />
        <LoadingState v-else-if="loading" />
        <template v-else>
          <AppSectionCard title="必修全通过">
            <EmptyState v-if="!courseRequiredRows.length" title="暂无必修数据" description="批次尚未执行预审" />
            <DataTable
              v-else
              :columns="itemColumns"
              :rows="courseRequiredRows"
              row-key="resultId"
              :pagination="courseRequiredPagination"
              @page-change="onCourseRequiredPageChange"
            >
              <template #cell-result="{ row }">
                <AppStatusTag :type="gradItemColor(itemOf(row, 'COURSE_REQUIRED').result)" dot>{{ itemResultLabel(itemOf(row, 'COURSE_REQUIRED').result) }}</AppStatusTag>
              </template>
              <template #cell-evidence="{ row }">
                <span class="agc-evidence">{{ itemOf(row, 'COURSE_REQUIRED').evidence || '—' }}</span>
              </template>
              <template #cell-ops="{ row }"><button class="mp-link" @click="openDetail(row)">十一项详情</button></template>
            </DataTable>
          </AppSectionCard>
          <AppSectionCard title="选修学分达标">
            <EmptyState v-if="!courseElectiveRows.length" title="暂无选修数据" description="批次尚未执行预审" />
            <DataTable
              v-else
              :columns="itemColumns"
              :rows="courseElectiveRows"
              row-key="resultId"
              :pagination="courseElectivePagination"
              @page-change="onCourseElectivePageChange"
            >
              <template #cell-result="{ row }">
                <AppStatusTag :type="gradItemColor(itemOf(row, 'COURSE_ELECTIVE').result)" dot>{{ itemResultLabel(itemOf(row, 'COURSE_ELECTIVE').result) }}</AppStatusTag>
              </template>
              <template #cell-evidence="{ row }">
                <span class="agc-evidence">{{ itemOf(row, 'COURSE_ELECTIVE').evidence || '—' }}</span>
              </template>
              <template #cell-ops="{ row }"><button class="mp-link" @click="openDetail(row)">十一项详情</button></template>
            </DataTable>
          </AppSectionCard>
        </template>
      </template>

      <template v-else-if="tab === 'final'">
        <AppInlineAlert
          type="warning"
          description="教务终审会写入毕业/结业/延毕学籍终态，属于不可逆业务动作；请在十一项证据和学院初审均核对完成后操作。"
        />
        <ErrorState v-if="error" :description="error" @retry="loadTab" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="暂无待终审名单" description="需学院初审通过（ACADEMIC_REVIEW）后才进入本队列" />
        <DataTable v-else :columns="finalColumns" :rows="rows" row-key="resultId" :pagination="pagination" @page-change="onPageChange">
          <template #cell-overall="{ row }"><AppStatusTag :type="overallColor(row.overall)" dot>{{ overallLabel(row.overall) }}</AppStatusTag></template>
          <template #cell-ops="{ row }">
            <button v-if="canNormalFinal(row)" class="mp-btn mp-btn--primary" @click="openFinal(row)">教务终审</button>
            <template v-else>
              <span class="agc-final-blocked">系统异常 · 先治理阻断项</span>
              <button class="mp-link" @click="openDetail(row)">查看阻断证据</button>
            </template>
          </template>
        </DataTable>
      </template>

      <template v-else-if="tab === 'roster'">
        <ErrorState v-if="error" :description="error" @retry="loadRosterTab" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rosterData" title="暂无名单" description="批次尚未终审，终审后写入毕业/结业/延毕结论的学生会出现在此" />
        <template v-else>
          <div class="agc-roster-toolbar">
            <input v-model.trim="rosterKeyword" class="aa-select agc-roster-search" placeholder="按学号/姓名筛选" />
          </div>
          <AppSectionCard v-for="g in rosterGroups" :key="g.key" :title="`${g.title}（${g.rows.length}）`">
            <EmptyState v-if="!g.rows.length" :title="`暂无${g.title}学生`" description="终审写入该结论后会出现在此" />
            <DataTable v-else :columns="rosterColumns" :rows="g.rows" row-key="studentId" />
          </AppSectionCard>
        </template>
      </template>

      <template v-else-if="tab === 'reason'">
        <ErrorState v-if="error" :description="error" @retry="loadReasonTab" />
        <LoadingState v-else-if="loading" />
        <template v-else>
          <AppSectionCard v-for="g in reasonGroups" :key="g.status" :title="`${g.title}（${g.total}）`">
            <p class="mp-note">{{ g.hint }}</p>
            <EmptyState v-if="!g.rows.length" :title="`暂无${g.title}学生`" description="批次内暂无该分类学生" />
            <DataTable
              v-else
              :columns="reasonColumns"
              :rows="g.rows"
              row-key="resultId"
              :pagination="g.pagination"
              @page-change="(p) => onReasonPageChange(g.status, p)"
            >
              <template #cell-reason="{ row }"><span class="agc-evidence">{{ reasonText(row) }}</span></template>
              <template #cell-ops="{ row }"><button class="mp-link" @click="openDetail(row)">十一项详情</button></template>
            </DataTable>
          </AppSectionCard>
        </template>
      </template>

      <template v-else-if="tab === 'results'">
        <ErrorState v-if="error" :description="error" @retry="loadTab" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="暂无预审结果" description="请先在「审核批次」页执行预审" />
        <DataTable v-else :columns="resultColumns" :rows="rows" row-key="resultId" :pagination="pagination" @page-change="onPageChange">
          <template #cell-overall="{ row }"><AppStatusTag :type="overallColor(row.overall)" dot>{{ overallLabel(row.overall) }}</AppStatusTag></template>
          <template #cell-status="{ row }"><AppStatusTag :type="row.status === 'ARCHIVED' ? 'default' : 'primary'" dot>{{ statusLabel(row.status) }}</AppStatusTag></template>
          <template #cell-conclusion="{ row }"><span v-if="row.conclusion" class="agc-conclusion">{{ conclusionLabel(row.conclusion) }}</span><span v-else>—</span></template>
          <template #cell-ops="{ row }"><button class="mp-link" @click="openDetail(row)">详情 / 处理</button></template>
        </DataTable>
      </template>

      <template v-else-if="tab === 'archive'">
        <AppSectionCard title="归档操作">
          <p class="mp-note">收敛该批次已终审的「毕业/结业」结果为已归档（ARCHIVED）；延毕滚入下一批次、退回待重初审的结果不在本次归档范围内，需重新走完流程后再归档。</p>
          <AppButton variant="primary" :disabled="!canManagePermission || !batchId || archiving || !!pendingWrite" :loading="archiving" @click="confirmArchive">执行归档</AppButton>
        </AppSectionCard>
        <ErrorState v-if="error" :description="error" @retry="loadTab" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="暂无已归档结果" description="执行归档后，已终审的毕业/结业名单会出现在此" />
        <DataTable v-else :columns="archiveColumns" :rows="rows" row-key="resultId" :pagination="pagination" @page-change="onPageChange">
          <template #cell-conclusion="{ row }"><span class="agc-conclusion">{{ conclusionLabel(row.conclusion) }}</span></template>
        </DataTable>
      </template>
    </div>

    <AppDrawer :visible="detail.visible" title="预审结果详情（十一项）" mode="modal" size="xlarge" @close="closeDetail">
      <template v-if="detail.row">
        <div class="agc-detail-head">
          <div>
            <span class="agc-eyebrow">学生审核事实</span>
            <div class="agc-detail-name">{{ detail.row.realName || ('学生 ' + detail.row.studentId) }}</div>
          </div>
          <div class="agc-detail-tags">
            <AppStatusTag :type="overallColor(detail.row.overall)" dot>{{ overallLabel(detail.row.overall) }}</AppStatusTag>
            <AppStatusTag :type="detail.row.status === 'ARCHIVED' ? 'default' : 'primary'" dot>{{ statusLabel(detail.row.status) }}</AppStatusTag>
          </div>
        </div>
        <div class="agc-items">
          <div v-for="it in detail.row.items" :key="it.item" class="agc-item">
            <span class="agc-item__label">{{ itemLabel(it.item) }}</span>
            <AppStatusTag :type="gradItemColor(it.result)" dot>{{ itemResultLabel(it.result) }}</AppStatusTag>
            <span class="agc-item__ev">{{ it.evidence }}</span>
          </div>
        </div>
        <AppInlineAlert v-if="detail.row.reviewNote" type="info" :description="`最近处理意见：${detail.row.reviewNote}`" />

        <div v-if="canCollegeReview(detail.row)" class="agc-actions">
          <div class="agc-actions__title">学院初审</div>
          <AppButton v-if="canCollegeApprove(detail.row)" variant="primary" :loading="detailBusy" @click="doCollegeReview('APPROVE')">通过</AppButton>
          <AppButton v-if="canCollegeReject(detail.row)" :loading="detailBusy" @click="openCollegeReject">退回学院（需≥5字原因）</AppButton>
        </div>
        <AppInlineAlert
          v-if="detail.row.status === 'SYSTEM_ABNORMAL'"
          type="warning"
          description="系统预审异常：学院通过已锁定；请先治理阻断项并重新预审，或退回学院重新核对。"
        />

        <div v-if="canNormalFinal(detail.row)" class="agc-actions">
          <div class="agc-actions__title">毕业资格终审</div>
          <AppRadioGroup v-model="finalConclusion" :options="conclusionOptions" variant="button" />
          <AppButton variant="primary" :loading="detailBusy || finalDlg.submitting" @click="confirmFinal">确认终审并写学籍</AppButton>
        </div>
        <AppInlineAlert
          v-else-if="detail.row.status === 'ACADEMIC_REVIEW' && detail.row.overall === 'SYSTEM_ABNORMAL'"
          type="warning"
          description="系统预审仍为异常：普通教务终审不可用审核备注覆盖评估结论。请先下钻阻断证据、完成治理并重新预审；正式例外必须走独立 Override 流程。"
        />
        <p v-if="detail.row.conclusion" class="mp-note">终审结论：{{ conclusionLabel(detail.row.conclusion) }}（涉学籍终态，不可在本页撤销）</p>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="finalDlg.visible"
      title="确认毕业资格终审"
      type="danger"
      :message="`将对该生写入学籍终态「${CONCLUSION_LABEL[finalConclusion]}」，是否确认？`"
      :submitting="finalDlg.submitting"
      @confirm="doFinal"
    />
    <AppConfirmDialog
      v-model:visible="archiveDlg.visible"
      title="确认审核归档"
      type="warning"
      :message="'将该批次已终审的毕业/结业结果标记为已归档，归档后不可在本页撤销，是否确认？'"
      :submitting="archiving"
      @confirm="doArchive"
    />
    <AppConfirmDialog
      v-model:visible="collegeRejectDlg.visible"
      title="退回学院重新核对"
      type="danger"
      require-reason
      reason-label="退回原因（≥5字）"
      :submitting="detailBusy"
      @confirm="doCollegeReject"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 毕业资格审核 · 审核工作台（/admin/academic-affairs/graduation/audit-console?tab=）。
 * 十一项跨域供数三态判定的下游叶子共享同一批次选择与详情抽屉。
 * Stage D 只提升信息架构，不在前端重新计算毕业资格，也不制造 DecisionTrace。
 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSectionCard, AppConfirmDialog, AppInlineAlert, AppGraduationBatchPicker, AppRadioGroup } from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import AppStatusTag from '@/components/common/AppStatusTag.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import {
  GRAD_ITEM_LABEL, GRAD_ITEM_RESULT, gradItemColor, OVERALL_LABEL, overallColor,
  CONCLUSION_LABEL, GRAD_STATUS_LABEL, GRAD_FAIL_GROUPS
} from '@/modules/academicAffairs/constants/grade-graduation'
import { toast } from '@/utils/toast'
import { currentUserFromToken } from '@/services/http/client'
import { gradeError } from './parallel-c/grade-review'
import { matchPermission } from '@/config/navPlan'
import { systemConfirm } from '@/services/systemDialog'
import GraduationStageRail from '@/modules/academicAffairs/components/graduation/GraduationStageRail.vue'

const TAB_CONFIG = {
  credit: { label: '学分达成审核', item: 'CREDIT' },
  course: { label: '课程达成审核' },
  practice: { label: '实践环节审核', item: 'PRACTICE' },
  thesis: { label: '毕设状态联动', item: 'GRADUATION_DESIGN' },
  internship: { label: '实习状态联动', item: 'INTERNSHIP' },
  discipline: { label: '处分状态联动', item: 'DISCIPLINE' },
  fee: { label: '费用结清', item: 'FEE' },
  final: { label: '毕业资格终审', status: 'ACADEMIC_REVIEW' },
  roster: { label: '毕业学生名单' },
  reason: { label: '不通过原因' },
  results: { label: '审核结果' },
  archive: { label: '审核归档', status: 'ARCHIVED' }
}

const LINK_ITEM = {
  GRADUATION_DESIGN: (refId) => `/admin/graduation/students/${refId}`,
  INTERNSHIP: (refId) => `/admin/internship/students/${refId}`
}

const freshPagination = () => ({ page: 1, pageSize: 20, total: 0 })
const exactId = value => typeof value === 'string' && value.trim() ? value : (typeof value === 'number' && Number.isSafeInteger(value) ? String(value) : '')

// 后端事实语义：费用结清默认 UNKNOWN（不阻断）；用户界面展示为“待治理”。
export default {
  name: 'AaGraduationAuditConsoleView',
  components: {
    ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton,
    AppSectionCard, AppConfirmDialog, AppInlineAlert, AppDrawer, AppStatusTag,
    AppGraduationBatchPicker, AppRadioGroup, GraduationStageRail
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      alive: true, scope: 0, readSeq: {}, pendingWrite: null,
      CONCLUSION_LABEL,
      conclusionOptions: Object.entries(CONCLUSION_LABEL).map(([value, label]) => ({ value, label })),
      tabs: Object.keys(TAB_CONFIG).map((key) => ({ key, label: TAB_CONFIG[key].label })),
      tab: 'credit',
      batches: [], loadingBatches: true, batchId: '',
      rows: [], courseRequiredRows: [], courseElectiveRows: [],
      courseRequiredPagination: freshPagination(),
      courseElectivePagination: freshPagination(),
      rosterData: null, rosterKeyword: '',
      reasonRows: { SYSTEM_ABNORMAL: [], REJECTED: [], DELAYED: [] },
      reasonPagination: {
        SYSTEM_ABNORMAL: freshPagination(),
        REJECTED: freshPagination(),
        DELAYED: freshPagination()
      },
      loading: false, error: '',
      pagination: freshPagination(),
      detail: { visible: false, row: null }, detailBusy: false,
      actionReceipt: null,
      finalConclusion: 'GRADUATED',
      finalDlg: { visible: false, submitting: false },
      archiveDlg: { visible: false },
      collegeRejectDlg: { visible: false },
      archiving: false,
      feeBusy: false,
      itemColumns: [
        { key: 'studentId', title: '学号' }, { key: 'realName', title: '姓名' },
        { key: 'result', title: '结果' }, { key: 'evidence', title: '证据' }, { key: 'ops', title: '操作', width: '160px' }
      ],
      finalColumns: [
        { key: 'studentId', title: '学号' }, { key: 'realName', title: '姓名' },
        { key: 'overall', title: '系统预审' }, { key: 'ops', title: '操作', width: '120px' }
      ],
      resultColumns: [
        { key: 'studentId', title: '学号' }, { key: 'realName', title: '姓名' },
        { key: 'overall', title: '系统预审' }, { key: 'status', title: '当前状态' },
        { key: 'conclusion', title: '终审结论' }, { key: 'ops', title: '操作', width: '120px' }
      ],
      archiveColumns: [
        { key: 'studentId', title: '学号' }, { key: 'realName', title: '姓名' }, { key: 'conclusion', title: '终审结论' }
      ],
      rosterColumns: [
        { key: 'studentNo', title: '学号' }, { key: 'realName', title: '姓名' },
        { key: 'collegeName', title: '学院' }, { key: 'majorName', title: '专业' }, { key: 'className', title: '班级' }
      ],
      reasonColumns: [
        { key: 'studentNo', title: '学号' }, { key: 'realName', title: '姓名' },
        { key: 'reason', title: '不通过原因' }, { key: 'ops', title: '操作', width: '100px' }
      ],
      focusedResultId: ''
    }
  },
  computed: {
    identity() { const u=currentUserFromToken()||{};return JSON.stringify([u.tenantId,u.userId,u.activeContextId,u.currentRoleCode,this.ctx.currentRole,this.ctx.dataScope,this.ctx.permissionPatterns]) },
    canCollegePermission(){return matchPermission(this.ctx.permissionPatterns||[],'academicAffairs.graduation.collegeReview')},
    canFinalPermission(){return matchPermission(this.ctx.permissionPatterns||[],'academicAffairs.graduation.final')},
    canManagePermission(){return matchPermission(this.ctx.permissionPatterns||[],'academicAffairs.graduation.manage')},
    currentTabLabel() { return TAB_CONFIG[this.tab] ? TAB_CONFIG[this.tab].label : '' },
    pageSubtitle() {
      const copy = {
        roster: '确认批次正式学生范围，查看毕业、结业与延毕名单',
        credit: '核对学分达成证据，异常返回培养与成绩责任模块治理',
        course: '分别核对必修课程与选修学分，保留两类正式证据',
        practice: '核对培养方案要求的实践环节完成证据',
        thesis: '读取毕业设计正式状态，缺失或未通过时返回责任模块',
        internship: '读取岗位实习正式状态，缺失或未通过时返回责任模块',
        fee: '财务未供数时保持 UNKNOWN；人工标记必须回读正式结果',
        discipline: '核对未解除处分等正式阻断证据',
        final: '逐项查看十一项正式证据，锁定学生与审核结果后执行终审',
        reason: '按系统异常、学院退回和延毕分类返回责任岗位治理',
        results: '查看正式预审、学院审核与教务终审结论',
        archive: '封存已终审结果；UNKNOWN 与未闭环对象继续留在责任队列'
      }
      return copy[this.tab] || '毕业资格审核工作区'
    },
    stageIndex(){return ['roster'].includes(this.tab)?1:['credit','course','practice','thesis','internship','fee','discipline','reason'].includes(this.tab)?2:this.tab==='final'?4:['results','archive'].includes(this.tab)?5:0},
    queueRows(){return this.tab==='course'?[...this.courseRequiredRows,...this.courseElectiveRows].filter((row,index,all)=>all.findIndex(item=>String(item.resultId)===String(row.resultId))===index):this.rows},
    focusedRow(){return this.queueRows.find(row=>String(row.resultId)===String(this.focusedResultId))||this.queueRows[0]||null},
    focusedItems(){if(!this.focusedRow)return[];if(this.tab==='final')return this.focusedRow.items||[];if(this.tab==='course')return (this.focusedRow.items||[]).filter(item=>['COURSE_REQUIRED','COURSE_ELECTIVE'].includes(item.item));const item=this.itemOf(this.focusedRow);return item?.item?[item]:[]},
    showEvidenceBoard(){return ['credit','course','practice','thesis','internship','discipline','fee','final'].includes(this.tab)},
    currentOwner(){if(this.tab==='final')return '教务终审岗';if(this.tab==='archive')return '教务归档岗';if(this.tab==='results')return '教务复核岗';if(this.tab==='roster')return '学院名单核对岗';const item=this.focusedItems.find(entry=>entry.result!=='PASS')||this.focusedItems[0];return this.ownerLabel(item?.owner)},
    responsibilityReason(){if(!this.currentBatch)return'选择批次后确定';if(this.tab==='final')return'学院初审通过且系统预审通过，轮到教务终审';if(this.batchAbnormal)return`有 ${this.batchAbnormal} 名学生存在阻断证据`;return'当前阶段需要核对正式证据与责任来源'},
    currentBlocker(){if(!this.currentBatch)return'尚未选择批次';const item=this.focusedItems.find(entry=>entry.result!=='PASS');if(item)return`${this.itemLabel(item.item)}：${this.itemResultLabel(item.result)}`;if(this.batchAbnormal)return`${this.batchAbnormal} 名系统异常`;return'当前无已知阻断'},
    nextOwner(){if(this.tab==='final')return'证书管理岗';if(this.tab==='archive')return'受控纠错岗';if(this.batchAbnormal)return'学院审核岗';return'教务终审岗'},
    currentBatch() { return this.batches.find((b) => String(b.batchId) === String(this.batchId)) || null },
    batchTotal() { return Number(this.currentBatch?.total || 0) },
    batchPassed() { return Number(this.currentBatch?.passed || 0) },
    batchAbnormal() { return Number(this.currentBatch?.abnormal || 0) },
    batchConcluded() { return Number(this.currentBatch?.concluded || 0) },
    batchArchived() { return Number(this.currentBatch?.archived || 0) },
    unconcludedCount() { return Math.max(this.batchTotal - this.batchConcluded, 0) },
    finalProgressPct() {
      if (!this.batchTotal) return 0
      return Math.max(0, Math.min(100, Math.round(this.batchConcluded / this.batchTotal * 100)))
    },
    batchHealthLabel() {
      if (!this.currentBatch) return ''
      if (!this.batchTotal) return '等待预审结果'
      if (this.batchAbnormal > 0) return '存在系统异常'
      if (this.unconcludedCount > 0) return '审核进行中'
      return '终审结论已形成'
    },
    batchHealthTone() {
      if (!this.batchTotal) return 'is-neutral'
      if (this.batchAbnormal > 0) return 'is-warning'
      if (this.unconcludedCount > 0) return 'is-info'
      return 'is-success'
    },
    batchHealthDescription() {
      if (!this.currentBatch) return ''
      if (!this.batchTotal) return '当前批次尚无可核验结果；先回到审核批次执行预审。'
      if (this.batchAbnormal > 0) {
        return `当前有 ${this.batchAbnormal} 名系统异常，另有 ${this.unconcludedCount} 名尚未形成终审结论；应先核对异常证据和责任模块。`
      }
      if (this.unconcludedCount > 0) {
        return `已终审 ${this.batchConcluded}/${this.batchTotal} 人，尚有 ${this.unconcludedCount} 人未形成终审结论；继续按学院初审 → 教务终审推进。`
      }
      return `本批次 ${this.batchTotal} 名学生均已形成终审结论；已归档 ${this.batchArchived} 人。延毕等结论按既有规则不强制进入本次归档。`
    },
    batchNextAction() {
      if (!this.currentBatch || !this.batchTotal) return '返回审核批次执行预审'
      if (this.batchAbnormal > 0) return '先处理系统异常与责任模块证据'
      if (this.unconcludedCount > 0) return '继续学院初审与教务终审'
      return '复核结论名单与归档范围'
    },
    batchOptions() {
      return this.batches.map((b) => ({
        value: String(b.batchId),
        label: `${b.batchName}（${b.status}，应审 ${b.total}）`
      }))
    },
    rosterGroups() {
      if (!this.rosterData) return []
      const kw = (this.rosterKeyword || '').trim()
      const filterFn = (rows) => (!kw ? rows : rows.filter((r) =>
        (r.studentNo || '').includes(kw) || (r.realName || '').includes(kw)))
      return [
        { key: 'GRADUATED', title: '毕业', rows: filterFn(this.rosterData.graduated || []) },
        { key: 'COMPLETED', title: '结业', rows: filterFn(this.rosterData.completed || []) },
        { key: 'DELAYED', title: '延毕', rows: filterFn(this.rosterData.delayed || []) }
      ]
    },
    reasonGroups() {
      return GRAD_FAIL_GROUPS.map((g) => ({
        ...g,
        rows: this.reasonRows[g.status] || [],
        pagination: this.reasonPagination[g.status] || freshPagination(),
        total: Number(this.reasonPagination[g.status]?.total || 0)
      }))
    }
  },
  watch:{identity(){this.reloadForIdentity()},'$route.query':{deep:true,handler(q){if(this.loading||this.detailBusy||this.finalDlg.submitting||this.archiving)return;const tab=q?.tab&&TAB_CONFIG[q.tab]?q.tab:this.tab;const batch=q?.batchId?String(q.batchId):this.batchId;if(tab!==this.tab||batch!==this.batchId){this.scope++;this.tab=tab;this.batchId=batch;this.detail={visible:false,row:null};this.actionReceipt=null;this.pagination.page=1;this.resetSpecialPagination();this.loadTab()}}}},
  async created() {
    const q = this.$route && this.$route.query
    if (q && q.tab && TAB_CONFIG[q.tab]) this.tab = q.tab
    await this.loadBatches()
    if (q && q.batchId && this.batches.some((b) => String(b.batchId) === String(q.batchId))) this.batchId = String(q.batchId)
    else if (this.batches.length) this.batchId = (this.batches.find((b) => b.status !== 'ARCHIVED') || this.batches[0]).batchId
    await this.loadTab()
    if (q && q.resultId) {
      const requested=exactId(q.resultId);if(!requested){toast.error('指定毕业审核结果标识无效');return}
      const res = await academicAffairsApi.getGradResult(requested)
      if (res.code === 0&&exactId(res.data?.resultId)===requested&&String(res.data?.batchId)===String(this.batchId)) this.openDetail(res.data)
      else toast.error('指定毕业审核结果与当前批次不一致，已阻止办理')
    }
  },
  beforeUnmount(){this.alive=false;this.invalidatePrivate()},
  methods: {
    token(kind){const seq=(this.readSeq[kind]||0)+1;this.readSeq[kind]=seq;return {kind,seq,scope:this.scope,identity:this.identity,route:this.$route.fullPath,batchId:String(this.batchId),tab:this.tab}},
    current(c){return this.alive&&c.scope===this.scope&&c.identity===this.identity&&c.route===this.$route.fullPath&&this.readSeq[c.kind]===c.seq},
    denied(err){return /403|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN/.test([err?.code,err?.bizCode].join(' '))},
    invalidatePrivate(){this.scope++;this.readSeq={};this.batches=[];this.batchId='';this.rows=[];this.courseRequiredRows=[];this.courseElectiveRows=[];this.rosterData=null;this.reasonRows={SYSTEM_ABNORMAL:[],REJECTED:[],DELAYED:[]};this.detail={visible:false,row:null};this.focusedResultId='';this.actionReceipt=null;this.pendingWrite=null;this.loading=false;this.loadingBatches=false;this.detailBusy=false;this.archiving=false;this.feeBusy=false;this.finalDlg={visible:false,submitting:false};this.archiveDlg={visible:false};this.collegeRejectDlg={visible:false}},
    async reloadForIdentity(){this.invalidatePrivate();await this.loadBatches();if(!this.alive)return;this.batchId=String((this.batches.find((b)=>b.status!=='ARCHIVED')||this.batches[0])?.batchId||'');await this.loadTab()},
    fail(err,fallback){if(this.denied(err))this.invalidatePrivate();return gradeError(err,fallback)},
    gradItemColor, overallColor,
    itemLabel(i) { return GRAD_ITEM_LABEL[i] || i },
    itemResultLabel(r) { return GRAD_ITEM_RESULT[r] || r },
    overallLabel(o) { return OVERALL_LABEL[o] || o || '—' },
    statusLabel(s) { return GRAD_STATUS_LABEL[s] || (s ? '状态待确认' : '') },
    conclusionLabel(c) { return CONCLUSION_LABEL[c] || c },
    ownerLabel(owner){return {AA_STAFF:'教务审核岗',COLLEGE_STAFF:'学院审核岗',COUNSELOR:'辅导员/学工责任岗',GD_MENTOR:'毕业设计责任岗',INTERNSHIP_MENTOR:'岗位实习责任岗',FINANCE:'财务供数岗'}[owner]||'证据责任岗'},
    focusResult(row){if(!row||this.pendingWrite)return;this.focusedResultId=String(row.resultId||'')},
    itemOf(row, key) {
      const target = key || (TAB_CONFIG[this.tab] && TAB_CONFIG[this.tab].item)
      return (row.items || []).find((it) => it.item === target) || row.itemDetail || {}
    },
    linkFor(row) {
      const cfg = TAB_CONFIG[this.tab]
      if (!cfg || !cfg.item || !LINK_ITEM[cfg.item]) return null
      const it = this.itemOf(row)
      if (!it.refId) return null
      return LINK_ITEM[cfg.item](it.refId)
    },
    canCollegeApprove(r) {
      return Boolean(this.canCollegePermission&&!this.pendingWrite&&r && r.overall === 'SYSTEM_PASSED' && ['SYSTEM_PASSED', 'COLLEGE_REVIEW'].includes(r.status))
    },
    canCollegeReject(r) { return Boolean(this.canCollegePermission&&!this.pendingWrite&&r && ['SYSTEM_PASSED', 'SYSTEM_ABNORMAL', 'COLLEGE_REVIEW'].includes(r.status)) },
    canCollegeReview(r) { return this.canCollegeApprove(r) || this.canCollegeReject(r) },
    canNormalFinal(r) { return Boolean(this.canFinalPermission&&!this.pendingWrite&&r && r.status === 'ACADEMIC_REVIEW' && r.overall === 'SYSTEM_PASSED') },
    resetSpecialPagination() {
      this.courseRequiredPagination = freshPagination()
      this.courseElectivePagination = freshPagination()
      this.reasonPagination = {
        SYSTEM_ABNORMAL: freshPagination(),
        REJECTED: freshPagination(),
        DELAYED: freshPagination()
      }
    },
    async markFee(row, status) {
      if (!this.canManagePermission || !this.batchId || this.feeBusy || this.pendingWrite) return
      const label = status === 'CLEARED' ? '已结清' : '仍欠费'
      if (!await systemConfirm({ title:'确认费用状态', message:`确认将 ${row.realName || row.studentNo || row.studentId} 费用状态勾选为「${label}」？`, confirmText:`确认${label}` })) return
      const batchId=String(this.batchId),payload={studentNo:row.studentNo,studentId:row.studentId,status,evidence:`人工勾选过渡（${label}）`},expected=status==='CLEARED'?'PASS':'FAIL';this.feeBusy=true
      const ok=await this.performResultWrite('fee',row,()=>academicAffairsApi.markFeeClearance(batchId,payload),fresh=>(fresh.items||[]).some(item=>item.item==='FEE'&&item.result===expected),{title:'已核对正式费用证据',result:`费用状态：${label}`,next:'费用证据变化后应重新执行完整十一项预审'})
      this.feeBusy=false;if(ok){toast.success('已回读费用证据');await this.loadTab()}
    },
    switchTab(k) {
      if (this.loading || this.detailBusy || this.finalDlg.submitting || this.archiving || this.pendingWrite) return
      this.scope++;this.detail={visible:false,row:null};this.actionReceipt=null;this.focusedResultId=''
      this.tab = k
      this.$router.replace({ query: { ...this.$route.query, tab: k } }).catch(() => {})
      this.pagination.page = 1
      this.resetSpecialPagination()
      this.loadTab()
    },
    onBatchChange() {
      if(this.pendingWrite)return
      this.scope++;this.detail={visible:false,row:null};this.actionReceipt=null;this.focusedResultId='';this.rows=[];this.courseRequiredRows=[];this.courseElectiveRows=[];this.rosterData=null
      this.$router.replace({ query: { ...this.$route.query, batchId: this.batchId } }).catch(() => {})
      this.pagination.page = 1
      this.resetSpecialPagination()
      this.loadTab()
    },
    onPageChange(p) { this.pagination.page = p; this.loadTab() },
    onCourseRequiredPageChange(p) { this.courseRequiredPagination.page = p; this.loadCourseTab() },
    onCourseElectivePageChange(p) { this.courseElectivePagination.page = p; this.loadCourseTab() },
    onReasonPageChange(status, p) {
      if (!this.reasonPagination[status]) return
      this.reasonPagination[status].page = p
      this.loadReasonTab()
    },
    async loadBatches() {
      const c=this.token('batches');this.loadingBatches = true
      try {
        const pageSize = 100
        const all = []
        let page = 1
        let total = 0
        do {
          const res = await academicAffairsApi.listGradBatches({ page, pageSize })
          if(!this.current(c))return
          if (res.code !== 0) throw res
          const list = Array.isArray(res.data?.list) ? res.data.list : []
          all.push(...list)
          total = Number(res.data?.total || all.length)
          if (!list.length) break
          page += 1
        } while (all.length < total)
        if(this.current(c))this.batches = all
      } catch (e) {
        if(this.current(c))toast.error(this.fail(e,'毕业审核批次加载失败'))
      } finally {
        if(this.current(c))this.loadingBatches=false
      }
    },
    async readGradBatch(batchId){
      let page=1
      while(page<=3){const res=await academicAffairsApi.listGradBatches({page,pageSize:20});if(res?.code!==0)throw res;if(!Array.isArray(res.data?.list))throw {code:503};const found=res.data.list.find(row=>String(row.batchId)===String(batchId));if(found)return found;if(res.data.list.length<20||page*20>=Number(res.data.total))break;page++}
      return null
    },
    async loadTab() {
      if (this.tab === 'course') { await this.loadCourseTab(); return }
      if (this.tab === 'roster') { await this.loadRosterTab(); return }
      if (this.tab === 'reason') { await this.loadReasonTab(); return }
      if (!this.batchId) { this.rows = []; this.pagination.total = 0; return }
      const c=this.token('tab');this.loading = true
      this.error = ''
      try {
        const cfg = TAB_CONFIG[this.tab] || {}
        const params = { page: this.pagination.page, pageSize: this.pagination.pageSize }
        if (cfg.item) params.item = cfg.item
        if (cfg.status) params.status = cfg.status
        const res = await academicAffairsApi.getGradResults(c.batchId, params)
        if(!this.current(c)||c.batchId!==String(this.batchId)||c.tab!==this.tab)return
        if(res.code!==0)throw res;if(!Array.isArray(res.data?.list)||res.data.list.some(row=>String(row.batchId)!==c.batchId))throw {code:503}
        this.rows=res.data.list;this.pagination.total=Number.isFinite(res.data.total)?res.data.total:res.data.list.length
      } catch (e) {
        if(this.current(c))this.error=this.fail(e,'毕业审核数据加载失败')
      } finally {
        if(this.current(c))this.loading=false
      }
    },
    async loadCourseTab() {
      if (!this.batchId) {
        this.courseRequiredRows = []
        this.courseElectiveRows = []
        this.courseRequiredPagination.total = 0
        this.courseElectivePagination.total = 0
        return
      }
      const c=this.token('course');this.loading = true
      this.error = ''
      try {
        const [req, ele] = await Promise.all([
          academicAffairsApi.getGradResults(c.batchId, {
            item: 'COURSE_REQUIRED',
            page: this.courseRequiredPagination.page,
            pageSize: this.courseRequiredPagination.pageSize
          }),
          academicAffairsApi.getGradResults(c.batchId, {
            item: 'COURSE_ELECTIVE',
            page: this.courseElectivePagination.page,
            pageSize: this.courseElectivePagination.pageSize
          })
        ])
        if(!this.current(c)||c.batchId!==String(this.batchId)||this.tab!=='course')return
        if(this.denied(req)||this.denied(ele))throw (this.denied(req)?req:ele)
        if(req.code===0&&Array.isArray(req.data?.list)&&req.data.list.every(row=>String(row.batchId)===c.batchId)) {
          this.courseRequiredRows = req.data.list
          this.courseRequiredPagination.total = req.data.total
        } else this.error = req.message || '必修课程审核加载失败'
        if (ele.code===0&&Array.isArray(ele.data?.list)&&ele.data.list.every(row=>String(row.batchId)===c.batchId)) {
          this.courseElectiveRows = ele.data.list
          this.courseElectivePagination.total = ele.data.total
        } else this.error = this.error || ele.message || '选修课程审核加载失败'
      } catch (e) {
        if(this.current(c))this.error=this.fail(e,'课程达成审核加载失败')
      } finally {
        if(this.current(c))this.loading=false
      }
    },
    async loadRosterTab() {
      if (!this.batchId) { this.rosterData = null; return }
      const c=this.token('roster');this.loading = true
      this.error = ''
      try {
        const res = await academicAffairsApi.getGradRosters(c.batchId);if(!this.current(c)||c.batchId!==String(this.batchId)||this.tab!=='roster')return
        if(res.code!==0)throw res;if(!['graduated','completed','delayed'].every(key=>Array.isArray(res.data?.[key])))throw {code:503};this.rosterData=res.data
      } catch (e) {
        if(this.current(c))this.error=this.fail(e,'毕业名单加载失败')
      } finally {
        if(this.current(c))this.loading=false
      }
    },
    async loadReasonTab() {
      if (!this.batchId) {
        this.reasonRows = { SYSTEM_ABNORMAL: [], REJECTED: [], DELAYED: [] }
        Object.values(this.reasonPagination).forEach((p) => { p.total = 0 })
        return
      }
      const c=this.token('reason');this.loading = true
      this.error = ''
      try {
        const results = await Promise.all(GRAD_FAIL_GROUPS.map((g) => {
          const pg = this.reasonPagination[g.status] || freshPagination()
          return academicAffairsApi.getGradResults(c.batchId, {
            status: g.status,
            page: pg.page,
            pageSize: pg.pageSize
          })
        }))
        if(!this.current(c)||c.batchId!==String(this.batchId)||this.tab!=='reason')return
        const forbidden=results.find(r=>this.denied(r));if(forbidden)throw forbidden
        const next = {}
        let firstErr = ''
        GRAD_FAIL_GROUPS.forEach((g, idx) => {
          const r = results[idx]
          const pg = this.reasonPagination[g.status]
          if (r.code===0&&Array.isArray(r.data?.list)&&r.data.list.every(row=>String(row.batchId)===c.batchId)) {
            next[g.status] = r.data.list
            if (pg) pg.total = r.data.total
          } else {
            next[g.status] = []
            if (pg) pg.total = 0
            firstErr = firstErr || r.message || '不通过原因加载失败'
          }
        })
        this.reasonRows = next
        this.error = firstErr
      } catch (e) {
        if(this.current(c))this.error=this.fail(e,'不通过原因加载失败')
      } finally {
        if(this.current(c))this.loading=false
      }
    },
    reasonText(row) {
      const parts = []
      if (row.reviewNote) parts.push(`学院意见：${row.reviewNote}`)
      const fails = (row.items || []).filter((it) => it.result === 'FAIL')
        .map((it) => `${this.itemLabel(it.item)}：${it.evidence || '未通过'}`)
      if (fails.length) parts.push(fails.join('；'))
      return parts.join('；') || '暂无明细，请点右侧「十一项详情」核对'
    },
    resultSignature(row){return JSON.stringify([String(row?.resultId||''),String(row?.batchId||''),row?.status||'',row?.overall||'',row?.version??null,(row?.items||[]).map(item=>[item.item,item.result,item.evidence??null,item.refId??null,item.evidenceHash||'',item.checkedAt||''])])},
    freezeDecision(row){return {scope:this.scope,identity:this.identity,route:this.$route.fullPath,row:JSON.parse(JSON.stringify(row)),conclusion:this.finalConclusion}},
    sameDecision(c){return !!c&&c.scope===this.scope&&c.identity===this.identity&&c.route===this.$route.fullPath&&String(c.row?.batchId)===String(this.batchId)&&String(c.row?.resultId)===String(this.detail.row?.resultId)&&this.resultSignature(c.row)===this.resultSignature(this.detail.row)},
    openDetail(row) {
      if(this.pendingWrite||this.detailBusy||this.finalDlg.visible||this.collegeRejectDlg.visible)return
      if(!row||exactId(row.resultId)!==String(row.resultId)||String(row.batchId)!==String(this.batchId)){toast.error('毕业审核结果与当前批次不一致，已阻止办理');return}
      this.detail = { visible: true, row }
      this.finalConclusion = 'GRADUATED'
    },
    closeDetail(){this.detail={visible:false,row:null};if(this.$route.query.resultId){const query={...this.$route.query};delete query.resultId;this.$router.replace({query}).catch(()=>{})}},
    openFinal(row) {
      if (!this.canNormalFinal(row)) {
        toast.error('系统预审仍为异常，普通教务终审不可用；请先治理阻断项并重新预审')
        this.openDetail(row)
        return
      }
      this.openDetail(row)
    },
    openCollegeReject() {
      if (this.detailBusy || !this.canCollegeReject(this.detail.row)) return
      this.collegeRejectDlg.command=this.freezeDecision(this.detail.row)
      this.collegeRejectDlg.visible = true
    },
    recordActionReceipt(row, title, result, next, verified=true) {
      this.actionReceipt = {
        title, result, next, verified,
        subject: row?.realName || row?.studentName || '毕业审核对象',
        businessId: row?.resultId ? '正式毕业审核结果' : '正式审核批次'
      }
    },
    async performResultWrite(kind,row,send,verify,receipt){
      if(this.pendingWrite||!row)return false
      const resultId=exactId(row.resultId),batchId=String(this.batchId);if(!resultId||String(row.batchId)!==batchId)return false
      const c=this.token('write'),shown=this.resultSignature(row);this.detailBusy=true
      try{const before=await academicAffairsApi.getGradResult(resultId);if(!this.current(c))return false;if(before?.code!==0)throw before;if(exactId(before.data?.resultId)!==resultId||String(before.data?.batchId)!==batchId)throw {code:409};if(this.resultSignature(before.data)!==shown){this.detail.row=before.data;throw {code:409,message:'正式结果已变化'} }
        this.pendingWrite={kind,resultId,batchId};let res;try{res=await send(before.data)}catch(err){res=err}if(!this.current(c))return false
        if(res?.code!==0&&/403|404|409|422|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN|CONFLICT|VALIDATION/.test([res?.code,res?.bizCode].join(' '))){this.pendingWrite=null;throw res}
        const after=await academicAffairsApi.getGradResult(resultId);if(!this.current(c))return false;if(after?.code!==0)throw after
        if(res?.code===0&&after?.code===0&&exactId(after.data?.resultId)===resultId&&String(after.data?.batchId)===batchId&&verify(after.data,res)){this.detail.row=after.data;this.pendingWrite=null;this.recordActionReceipt(after.data,receipt.title,receipt.result,receipt.next,true);return true}
        this.recordActionReceipt(row,'结果待核实','已读取当前正式结果，但不能证明本次操作完成','请勿重复操作，由有权限人员核对评估与决定记录',false);return false
      }catch(err){if(this.current(c))toast.error(this.fail(err,'操作前核对未完成，请重新读取。'));return false}finally{if(this.current(c))this.detailBusy=false}
    },
    async doCollegeReject({ reason } = {}) {
      if (this.detailBusy || !this.detail.row) return
      const note = String(reason || '').trim()
      if (note.length < 5) { toast.error('退回原因不少于 5 字'); return }
      const command=this.collegeRejectDlg.command
      if(!this.sameDecision(command)||!this.canCollegeReject(command.row)){this.collegeRejectDlg.visible=false;toast.error('审核对象已变化，请重新核对');return}
      const row=command.row
      const ok=await this.performResultWrite('college-reject',row,()=>academicAffairsApi.collegeReviewGrad(row.resultId,'REJECT',note),fresh=>fresh.status==='REJECTED'&&String(fresh.reviewNote||'')===note,{title:'学院审核已退回',result:'正式退回原因已回读',next:'本批次不支持再次提交；需要时并入下一批次'})
      if(ok){toast.success('已回读学院退回结果');this.collegeRejectDlg.visible=false;this.detail.visible=false;await this.loadTab()}
    },
    async doCollegeReview(action) {
      if (this.detailBusy || action !== 'APPROVE' || !this.canCollegeApprove(this.detail.row)) return
      const row=this.detail.row
      const ok=await this.performResultWrite('college-approve',row,()=>academicAffairsApi.collegeReviewGrad(row.resultId,'APPROVE',''),fresh=>fresh.status==='ACADEMIC_REVIEW'&&fresh.overall==='SYSTEM_PASSED',{title:'学院审核已通过',result:'当前进入教务终审队列',next:'教务处继续核对十一项正式证据'})
      if(ok){toast.success('已回读学院通过结果');this.detail.visible=false;await this.loadTab()}
    },
    confirmFinal() {
      if (this.finalDlg.submitting || !this.canNormalFinal(this.detail.row)) {
        toast.error('系统预审仍为异常，禁止打开普通终审确认')
        return
      }
      this.finalDlg.command=this.freezeDecision(this.detail.row)
      this.finalDlg.visible = true
    },
    async doFinal() {
      if (this.finalDlg.submitting || !this.detail.row) return
      if (!this.canNormalFinal(this.detail.row)) {
        this.finalDlg.visible = false
        toast.error('系统预审已变化或仍为异常，请重新加载并治理阻断项')
        return
      }
      const command=this.finalDlg.command
      if(!this.sameDecision(command)||command.conclusion!==this.finalConclusion){this.finalDlg.visible=false;toast.error('终审对象或结论已变化，请重新确认');return}
      const row=command.row
      const resultId = this.detail.row.resultId
      const batchId=String(this.batchId),c=this.token('write'),shown=this.resultSignature(row)
      this.finalDlg.submitting=true;this.detailBusy=true
      try {
        const fresh = await academicAffairsApi.getGradResult(resultId)
        if(!this.current(c))return
        if(fresh?.code!==0||exactId(fresh.data?.resultId)!==exactId(resultId)||String(fresh.data?.batchId)!==batchId||this.resultSignature(fresh.data)!==shown)throw fresh
        this.detail.row = fresh.data
        if (!this.canNormalFinal(fresh.data)) throw {code:409}
        this.pendingWrite={kind:'final',resultId:exactId(resultId),batchId}
        let res;try{res=await academicAffairsApi.finalGrad(resultId, this.finalConclusion, true)}catch(err){res=err}
        if(!this.current(c))return
        if(res?.code!==0&&/403|404|409|422|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN|CONFLICT|VALIDATION/.test([res?.code,res?.bizCode].join(' '))){this.pendingWrite=null;throw res}
        const after=await academicAffairsApi.getGradResult(resultId)
        if(!this.current(c))return
        if(after?.code!==0)throw after
        if(res?.code===0&&after?.code===0&&exactId(after.data?.resultId)===exactId(resultId)&&String(after.data?.batchId)===batchId&&after.data.status===this.finalConclusion&&after.data.conclusion===this.finalConclusion){this.pendingWrite=null;this.detail.row=after.data;this.recordActionReceipt(after.data,'毕业资格终审完成',CONCLUSION_LABEL[this.finalConclusion]||this.finalConclusion,'终审结论已写入学籍；可继续证书与批次归档',true);toast.success('已回读正式终审结论');this.finalDlg.visible=false;this.detail.visible=false;await this.loadBatches();await this.loadTab()}
        else this.recordActionReceipt(row,'结果待核实','已读取当前正式结果，但不能证明本次终审完成','请勿重复终审，由有权限人员核对正式决定记录',false)
      }catch(err){if(this.current(c))toast.error(this.fail(err,'终审前核对未完成，请重新读取。'))}
      finally{if(this.current(c)){this.finalDlg.submitting=false;this.detailBusy=false}}
    },
    confirmArchive() {
      if (!this.canManagePermission || !this.batchId || this.archiving || this.pendingWrite) return
      this.archiveDlg.command={batchId:String(this.batchId),scope:this.scope,identity:this.identity,route:this.$route.fullPath}
      this.archiveDlg.visible = true
    },
    async doArchive() {
      if (!this.batchId || this.archiving) return
      if (!this.canManagePermission || this.pendingWrite) return
      const command=this.archiveDlg.command
      if(!command||command.batchId!==String(this.batchId)||command.scope!==this.scope||command.identity!==this.identity||command.route!==this.$route.fullPath){this.archiveDlg.visible=false;toast.error('归档批次已变化，请重新确认');return}
      const batchId = this.batchId
      const batch=this.currentBatch,c=this.token('archiveWrite');this.archiving=true
      try {
        const before=await this.readGradBatch(batchId);if(!this.current(c))return;if(!before||String(before.batchId)!==batchId)throw {code:409}
        this.pendingWrite={kind:'archive',batchId}
        let res;try{res=await academicAffairsApi.archiveGradBatch(batchId)}catch(err){res=err}if(!this.current(c))return
        if(res?.code!==0&&/403|404|409|422|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN|CONFLICT|VALIDATION/.test([res?.code,res?.bizCode].join(' '))){this.pendingWrite=null;throw res}
        const after=await this.readGradBatch(batchId);if(!this.current(c))return
        if(res?.code===0&&Number.isFinite(res.data?.archived)&&after?.status==='ARCHIVED'){
          this.pendingWrite=null;this.recordActionReceipt({realName:batch?.batchName},'毕业审核批次已归档',`正式回执归档 ${res.data.archived} 条结果`,'后续变更必须走正式纠错链；此处不代表十三域学期归档完成',true);toast.success('已回读批次归档状态');this.archiveDlg.visible=false;await this.loadBatches();await this.loadTab()
        } else this.recordActionReceipt({realName:batch?.batchName},'归档结果待核实','已读取当前批次，但不能确认本次命令完成','请勿重复归档，由有权限人员核对正式批次',false)
      } catch (e) {
        if(this.current(c))toast.error(this.fail(e,'归档前核对未完成'))
      } finally {
        if(this.current(c))this.archiving=false
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.agc-context { display: grid; grid-template-columns: minmax(280px, 1.5fr) repeat(4, minmax(150px, 1fr)); overflow: hidden; border: 1px solid #dbe5f2; border-radius: 12px; background: #fff; }
.agc-context > div { display: grid; align-content: center; gap: 5px; min-width: 0; padding: 14px 16px; border-right: 1px solid #e8eef6; }
.agc-context > div:last-child { border-right: 0; }
.agc-context span, .agc-context small { color: #728198; font-size: 12px; line-height: 1.45; }
.agc-context strong { overflow: hidden; color: #18365f; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.agc-context__object strong { font-size: 16px; }
.agc-context__object :deep(.app-select), .agc-context__object :deep(select) { margin-top: 5px; }
.is-risk-text { color: #b45f0b !important; }
.agc-coverage { display: grid; grid-template-columns: auto auto minmax(120px, 1fr); align-items: center; gap: 10px; margin-top: -8px; color: #75849a; font-size: 12px; }
.agc-coverage b { color: #1f5fbf; font-variant-numeric: tabular-nums; }
.agc-coverage i { height: 5px; overflow: hidden; border-radius: 999px; background: #e7edf6; }
.agc-coverage em { display: block; height: 100%; border-radius: inherit; background: #3978d2; }

.agc-evidence-board { display: grid; grid-template-columns: minmax(220px, .72fr) minmax(0, 1.8fr); overflow: hidden; min-height: 310px; border: 1px solid #dbe5f2; border-radius: 12px; background: #fff; }
.agc-queue { padding: 14px; border-right: 1px solid #e6edf6; background: #f8faff; }
.agc-queue header { display: flex; justify-content: space-between; gap: 12px; margin: 0 3px 10px; color: #18365f; }
.agc-queue header span { color: #75849a; font-size: 12px; }
.agc-queue button { display: grid; width: 100%; gap: 4px; margin: 0 0 7px; padding: 10px 11px; border: 1px solid transparent; border-radius: 8px; background: transparent; color: #314866; text-align: left; cursor: pointer; }
.agc-queue button:hover, .agc-queue button.is-active { border-color: #c9dcf6; background: #eaf2ff; color: #1d5fb8; }
.agc-queue button span { font-weight: 650; }
.agc-queue button small { color: #7b899c; }
.agc-focus { display: grid; grid-template-rows: auto 1fr auto; min-width: 0; padding: 19px 21px; }
.agc-focus > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; padding-bottom: 14px; border-bottom: 1px solid #edf1f6; }
.agc-focus h2 { margin: 5px 0 4px; color: #17345c; font-size: 20px; }
.agc-focus header small { color: #78869a; }
.agc-focus__items { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); align-content: start; gap: 9px; padding: 15px 0; }
.agc-focus__item { display: grid; grid-template-columns: minmax(92px, auto) auto; align-items: center; gap: 6px 10px; min-width: 0; padding: 11px 12px; border: 1px solid #e1e9f4; border-radius: 9px; background: #fbfcfe; }
.agc-focus__item > span { color: #314866; font-weight: 650; }
.agc-focus__item p, .agc-focus__item small { grid-column: 1 / -1; margin: 0; color: #6f7e92; font-size: 12px; line-height: 1.55; }
.agc-focus__item small { color: #8a96a7; }
.agc-focus > footer { display: flex; align-items: center; justify-content: space-between; gap: 15px; padding-top: 13px; border-top: 1px solid #edf1f6; color: #7b5d20; font-size: 12px; }

.agc-overview {
  overflow: hidden;
  border: 1px solid #dbe6f6;
  border-radius: 20px;
  background:
    radial-gradient(circle at 91% 10%, rgba(59, 130, 246, .13), transparent 30%),
    linear-gradient(135deg, #fff 0%, #f9fbff 60%, #f1f6ff 100%);
  box-shadow: 0 20px 48px -40px rgba(37, 99, 235, .55);
}
.agc-receipt { display: grid; grid-template-columns: minmax(0,1fr) auto minmax(220px,auto); align-items: center; gap: 18px; padding: 13px 15px; border: 1px solid #a7d7b4; border-radius: 11px; background: #f3fbf5; }
.agc-receipt strong, .agc-receipt span, .agc-receipt small, .agc-receipt b { display: block; }.agc-receipt strong { color: #15803d; }.agc-receipt span, .agc-receipt small { margin-top: 3px; color: #64748b; font-size: 11px; }.agc-receipt b { margin-top: 3px; font-size: 12px; }
.agc-overview__top {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 24px;
  padding: 24px 26px 20px;
}
.agc-overview__copy h2 {
  margin: 7px 0 6px;
  color: #17233a;
  font-size: 24px;
  letter-spacing: -.02em;
}
.agc-overview__copy > p {
  max-width: 760px;
  margin: 0;
  color: #64748b;
  font-size: 12.5px;
  line-height: 1.75;
}
.agc-eyebrow {
  color: #2468d8;
  font-size: 10.5px;
  font-weight: 750;
  letter-spacing: .08em;
}
.agc-batch-select { width: min(420px, 100%); margin-top: 15px; }

.agc-decision {
  display: grid;
  align-content: center;
  gap: 7px;
  padding: 18px;
  border: 1px solid #dbe8fb;
  border-radius: 15px;
  background: rgba(255,255,255,.80);
}
.agc-decision > span,
.agc-progress-row small,
.agc-next small { color: #8793a5; font-size: 10px; }
.agc-decision > strong { color: #235ea8; font-size: 18px; }
.agc-decision.is-warning { border-color: #f0d7ad; }
.agc-decision.is-warning > strong { color: #a85b0b; }
.agc-decision.is-success { border-color: #c7ead3; }
.agc-decision.is-success > strong { color: #18794e; }
.agc-decision.is-neutral { border-color: #dde3ea; }
.agc-decision.is-neutral > strong { color: #536174; }
.agc-progress-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-top: 3px; }
.agc-progress-row b { color: #334155; font-size: 11px; font-variant-numeric: tabular-nums; }
.agc-progress { height: 6px; overflow: hidden; border-radius: 999px; background: #e9eef6; }
.agc-progress i { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #72a7ee, #2f6fd2); }
.agc-decision.is-warning .agc-progress i { background: linear-gradient(90deg, #f7c66c, #d97706); }
.agc-decision.is-success .agc-progress i { background: linear-gradient(90deg, #68d391, #16a34a); }
.agc-next { display: grid; gap: 3px; margin-top: 5px; padding-top: 9px; border-top: 1px solid #e8edf4; }
.agc-next b { color: #27364c; font-size: 11px; line-height: 1.5; }

.agc-metrics {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0;
  border-top: 1px solid rgba(201, 216, 238, .75);
  background: rgba(255,255,255,.72);
}
.agc-metrics article {
  min-width: 0;
  padding: 16px 18px;
  border-right: 1px solid #e8eef7;
}
.agc-metrics article:last-child { border-right: 0; }
.agc-metrics span,
.agc-metrics strong,
.agc-metrics small { display: block; }
.agc-metrics span { color: #7a8798; font-size: 10.5px; }
.agc-metrics strong { margin-top: 5px; color: #172033; font-size: 23px; font-variant-numeric: tabular-nums; }
.agc-metrics small { margin-top: 4px; color: #98a3b3; font-size: 9.8px; line-height: 1.45; }
.agc-metrics article.is-pass strong { color: #18794e; }
.agc-metrics article.is-final strong { color: #2468d8; }
.agc-metrics article.is-archive strong { color: #64748b; }
.agc-metrics article.is-risk { background: #fffbf2; }
.agc-metrics article.is-risk strong { color: #b45f0b; }

.aa-select {
  height: 34px;
  padding: 0 10px;
  border: 1px solid var(--border-300, #d0d3d9);
  border-radius: 8px;
  background: var(--bg-white, #fff);
  color: var(--text-900, #1f2329);
  font-size: 13px;
  min-width: 260px;
}
.agc-roster-toolbar { display: flex; margin-bottom: 4px; }
.agc-roster-search { min-width: 220px; }

.agc-tabs {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  padding: 5px;
  border: 1px solid #e3eaf3;
  border-radius: 13px;
  background: #f7f9fc;
}
.agc-tab {
  padding: 8px 12px;
  border: 1px solid transparent;
  border-radius: 9px;
  background: transparent;
  cursor: pointer;
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
}
.agc-tab:hover { color: #2f5f9f; background: #fff; }
.agc-tab.is-active {
  color: #205fb4;
  border-color: #dbe7f7;
  background: #fff;
  box-shadow: 0 5px 14px -12px rgba(30, 64, 175, .55);
  font-weight: 650;
}

.agc-evidence { color: var(--text-500, #6b7789); font-size: 12px; line-height: 1.6; }
.agc-conclusion { color: var(--success-600, #16a34a); font-weight: 600; }
.agc-final-blocked {
  display: inline-block;
  margin-right: 8px;
  color: #a85b0b;
  font-size: 11px;
  font-weight: 650;
  line-height: 1.45;
}
.agc-detail-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e9edf3;
}
.agc-detail-tags { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.agc-detail-name { margin-top: 4px; font-size: 17px; font-weight: 650; color: #172033; }
.agc-items {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 14px;
}
.agc-item {
  display: grid;
  grid-template-columns: minmax(80px, auto) auto minmax(0, 1fr);
  align-items: center;
  gap: 9px;
  min-height: 54px;
  padding: 10px 12px;
  border: 1px solid #e7edf5;
  border-radius: 11px;
  background: #fbfcfe;
  font-size: 12px;
}
.agc-item__label { color: #3f4d61; font-weight: 600; }
.agc-item__ev { min-width: 0; color: #788497; font-size: 11px; line-height: 1.5; word-break: break-word; }
.agc-actions {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--border-color, #e5e7eb);
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.agc-actions__title { width: 100%; font-weight: 650; font-size: 13px; margin-bottom: 4px; }
.agc-radio { display: flex; align-items: center; gap: 6px; font-size: 13px; }

@media (max-width: 1080px) {
  .agc-context { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .agc-context > div { border-bottom: 1px solid #e8eef6; }
  .agc-overview__top { grid-template-columns: 1fr; }
  .agc-metrics { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .agc-metrics article { border-bottom: 1px solid #e8eef7; }
}
@media (max-width: 760px) {
  .agc-evidence-board { grid-template-columns: 1fr; }
  .agc-queue { border-right: 0; border-bottom: 1px solid #e6edf6; }
  .agc-focus__items { grid-template-columns: 1fr; }
  .agc-receipt { grid-template-columns: 1fr; gap: 10px; }
  .agc-overview__top { padding: 20px; }
  .agc-overview__copy h2 { font-size: 21px; }
  .agc-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .agc-items { grid-template-columns: 1fr; }
  .agc-detail-head { align-items: flex-start; flex-direction: column; }
}
@media (max-width: 520px) {
  .agc-context { grid-template-columns: 1fr; }
  .agc-metrics { grid-template-columns: 1fr; }
  .agc-metrics article { border-right: 0; }
  .agc-tab { width: 100%; text-align: left; }
}
</style>
