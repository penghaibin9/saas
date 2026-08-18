<template>
  <ModulePageShell
    title="毕业资格审核 · 审核工作台"
    subtitle="十一项跨域供数三态判定 · 学分/课程/实践达成审核 · 毕设/实习/处分状态联动 · 教务终审 · 归档"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/graduation')">返回审核批次</AppButton>
    </template>

    <div class="mp-stack">
      <section class="agc-overview" aria-label="毕业审核批次健康概览">
        <div class="agc-overview__top">
          <div class="agc-overview__copy">
            <span class="agc-eyebrow">当前毕业审核批次</span>
            <h2>{{ currentBatch ? currentBatch.batchName : '选择一个审核批次' }}</h2>
            <p>
              {{ currentBatch
                ? batchHealthDescription
                : '选择批次后，这里会基于现有应审、系统通过、系统异常、已终审和已归档事实给出办理优先级。' }}
            </p>
            <div class="agc-batch-select">
              <AppGraduationBatchPicker
                v-model="batchId"
                :options="batchOptions"
                :disabled="loadingBatches"
                :placeholder="loadingBatches ? '批次加载中…' : '选择批次'"
                @change="onBatchChange"
              />
            </div>
          </div>

          <aside v-if="currentBatch" :class="['agc-decision', batchHealthTone]">
            <span>当前结论</span>
            <strong>{{ batchHealthLabel }}</strong>
            <div class="agc-progress-row">
              <small>终审覆盖度</small>
              <b>{{ finalProgressPct }}%</b>
            </div>
            <div class="agc-progress" aria-hidden="true">
              <i :style="{ width: `${finalProgressPct}%` }"></i>
            </div>
            <div class="agc-next">
              <small>建议下一动作</small>
              <b>{{ batchNextAction }}</b>
            </div>
          </aside>
        </div>

        <div v-if="currentBatch" class="agc-metrics">
          <article>
            <span>应审学生</span>
            <strong>{{ batchTotal }}</strong>
            <small>本批次纳入审核范围</small>
          </article>
          <article class="is-pass">
            <span>系统通过</span>
            <strong>{{ batchPassed }}</strong>
            <small>共享毕业核验器通过</small>
          </article>
          <article :class="{ 'is-risk': batchAbnormal > 0 }">
            <span>系统异常</span>
            <strong>{{ batchAbnormal }}</strong>
            <small>{{ batchAbnormal ? '优先核对责任模块证据' : '当前无系统异常' }}</small>
          </article>
          <article class="is-final">
            <span>已终审</span>
            <strong>{{ batchConcluded }}</strong>
            <small>已形成正式终审结论</small>
          </article>
          <article class="is-archive">
            <span>已归档</span>
            <strong>{{ batchArchived }}</strong>
            <small>按既有归档范围收敛</small>
          </article>
        </div>

        <EmptyState
          v-if="!loadingBatches && !batches.length"
          title="暂无审核批次"
          description="请先到「审核批次」页新建批次并执行预审"
        />
      </section>

      <div class="agc-tabs" aria-label="毕业审核工作区">
        <button
          v-for="t in tabs"
          :key="t.key"
          :class="['agc-tab', { 'is-active': tab === t.key }]"
          @click="switchTab(t.key)"
        >{{ t.label }}</button>
      </div>

      <template v-if="!batchId">
        <EmptyState title="请先选择批次" description="从上方选择一个审核批次后再进入具体审核工作区" />
      </template>

      <template v-else-if="['credit', 'practice', 'thesis', 'internship', 'discipline', 'fee'].includes(tab)">
        <AppInlineAlert
          v-if="tab === 'fee'"
          type="warning"
          description="费用结清默认 UNKNOWN（不阻断）。财务未对接前，可由教务处人工勾选 CLEARED/OWED 过渡，禁止假装已自动通过。"
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
              <button class="mp-link" :disabled="feeBusy" @click="markFee(row, 'CLEARED')">勾选已结清</button>
              <button class="mp-link" :disabled="feeBusy" @click="markFee(row, 'OWED')">勾选仍欠费</button>
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
          <AppButton variant="primary" :disabled="!batchId || archiving" :loading="archiving" @click="confirmArchive">执行归档</AppButton>
        </AppSectionCard>
        <ErrorState v-if="error" :description="error" @retry="loadTab" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="暂无已归档结果" description="执行归档后，已终审的毕业/结业名单会出现在此" />
        <DataTable v-else :columns="archiveColumns" :rows="rows" row-key="resultId" :pagination="pagination" @page-change="onPageChange">
          <template #cell-conclusion="{ row }"><span class="agc-conclusion">{{ conclusionLabel(row.conclusion) }}</span></template>
        </DataTable>
      </template>
    </div>

    <AppDrawer :visible="detail.visible" title="预审结果详情（十一项）" mode="modal" size="xlarge" @close="detail.visible = false">
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

export default {
  name: 'AaGraduationAuditConsoleView',
  components: {
    ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton,
    AppSectionCard, AppConfirmDialog, AppInlineAlert, AppDrawer, AppStatusTag,
    AppGraduationBatchPicker, AppRadioGroup
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
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
      ]
    }
  },
  computed: {
    currentTabLabel() { return TAB_CONFIG[this.tab] ? TAB_CONFIG[this.tab].label : '' },
    currentBatch() { return this.batches.find((b) => b.batchId === this.batchId) || null },
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
        value: b.batchId,
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
  async created() {
    const q = this.$route && this.$route.query
    if (q && q.tab && TAB_CONFIG[q.tab]) this.tab = q.tab
    await this.loadBatches()
    if (q && q.batchId && this.batches.some((b) => b.batchId === q.batchId)) this.batchId = q.batchId
    else if (this.batches.length) this.batchId = (this.batches.find((b) => b.status !== 'ARCHIVED') || this.batches[0]).batchId
    await this.loadTab()
  },
  methods: {
    gradItemColor, overallColor,
    itemLabel(i) { return GRAD_ITEM_LABEL[i] || i },
    itemResultLabel(r) { return GRAD_ITEM_RESULT[r] || r },
    overallLabel(o) { return OVERALL_LABEL[o] || o || '—' },
    statusLabel(s) { return GRAD_STATUS_LABEL[s] || s || '' },
    conclusionLabel(c) { return CONCLUSION_LABEL[c] || c },
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
      return Boolean(r && r.overall === 'SYSTEM_PASSED' && ['SYSTEM_PASSED', 'COLLEGE_REVIEW'].includes(r.status))
    },
    canCollegeReject(r) { return Boolean(r && ['SYSTEM_PASSED', 'SYSTEM_ABNORMAL', 'COLLEGE_REVIEW'].includes(r.status)) },
    canCollegeReview(r) { return this.canCollegeApprove(r) || this.canCollegeReject(r) },
    canNormalFinal(r) { return Boolean(r && r.status === 'ACADEMIC_REVIEW' && r.overall === 'SYSTEM_PASSED') },
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
      if (!this.batchId || this.feeBusy) return
      const label = status === 'CLEARED' ? '已结清' : '仍欠费'
      if (!window.confirm(`确认将 ${row.realName || row.studentNo || row.studentId} 费用状态勾选为「${label}」？`)) return
      this.feeBusy = true
      try {
        const res = await academicAffairsApi.markFeeClearance(this.batchId, {
          studentNo: row.studentNo,
          studentId: row.studentId,
          status,
          evidence: `人工勾选过渡（${label}）`
        })
        if (res.code === 0) {
          toast.success('费用结清已勾选')
          await this.loadTab()
        } else toast.error(res.message || '勾选失败')
      } catch (e) {
        toast.error((e && e.message) || '勾选失败')
      } finally {
        this.feeBusy = false
      }
    },
    switchTab(k) {
      if (this.loading || this.detailBusy || this.finalDlg.submitting || this.archiving) return
      this.tab = k
      this.$router.replace({ query: { ...this.$route.query, tab: k } }).catch(() => {})
      this.pagination.page = 1
      this.resetSpecialPagination()
      this.loadTab()
    },
    onBatchChange() {
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
      this.loadingBatches = true
      try {
        const res = await academicAffairsApi.listGradBatches({ pageSize: 100 })
        if (res.code === 0) this.batches = res.data.list
        else toast.error(res.message || '毕业审核批次加载失败')
      } catch (e) {
        toast.error((e && e.message) || '毕业审核批次加载失败')
      } finally {
        this.loadingBatches = false
      }
    },
    async loadTab() {
      if (this.tab === 'course') { await this.loadCourseTab(); return }
      if (this.tab === 'roster') { await this.loadRosterTab(); return }
      if (this.tab === 'reason') { await this.loadReasonTab(); return }
      if (!this.batchId) { this.rows = []; this.pagination.total = 0; return }
      this.loading = true
      this.error = ''
      try {
        const cfg = TAB_CONFIG[this.tab] || {}
        const params = { page: this.pagination.page, pageSize: this.pagination.pageSize }
        if (cfg.item) params.item = cfg.item
        if (cfg.status) params.status = cfg.status
        const res = await academicAffairsApi.getGradResults(this.batchId, params)
        if (res.code === 0) {
          this.rows = res.data.list
          this.pagination.total = res.data.total
        } else this.error = res.message || '毕业审核数据加载失败'
      } catch (e) {
        this.error = (e && e.message) || '毕业审核数据加载失败'
      } finally {
        this.loading = false
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
      this.loading = true
      this.error = ''
      try {
        const [req, ele] = await Promise.all([
          academicAffairsApi.getGradResults(this.batchId, {
            item: 'COURSE_REQUIRED',
            page: this.courseRequiredPagination.page,
            pageSize: this.courseRequiredPagination.pageSize
          }),
          academicAffairsApi.getGradResults(this.batchId, {
            item: 'COURSE_ELECTIVE',
            page: this.courseElectivePagination.page,
            pageSize: this.courseElectivePagination.pageSize
          })
        ])
        if (req.code === 0) {
          this.courseRequiredRows = req.data.list
          this.courseRequiredPagination.total = req.data.total
        } else this.error = req.message || '必修课程审核加载失败'
        if (ele.code === 0) {
          this.courseElectiveRows = ele.data.list
          this.courseElectivePagination.total = ele.data.total
        } else this.error = this.error || ele.message || '选修课程审核加载失败'
      } catch (e) {
        this.error = (e && e.message) || '课程达成审核加载失败'
      } finally {
        this.loading = false
      }
    },
    async loadRosterTab() {
      if (!this.batchId) { this.rosterData = null; return }
      this.loading = true
      this.error = ''
      try {
        const res = await academicAffairsApi.getGradRosters(this.batchId)
        if (res.code === 0) this.rosterData = res.data
        else this.error = res.message || '毕业名单加载失败'
      } catch (e) {
        this.error = (e && e.message) || '毕业名单加载失败'
      } finally {
        this.loading = false
      }
    },
    async loadReasonTab() {
      if (!this.batchId) {
        this.reasonRows = { SYSTEM_ABNORMAL: [], REJECTED: [], DELAYED: [] }
        Object.values(this.reasonPagination).forEach((p) => { p.total = 0 })
        return
      }
      this.loading = true
      this.error = ''
      try {
        const results = await Promise.all(GRAD_FAIL_GROUPS.map((g) => {
          const pg = this.reasonPagination[g.status] || freshPagination()
          return academicAffairsApi.getGradResults(this.batchId, {
            status: g.status,
            page: pg.page,
            pageSize: pg.pageSize
          })
        }))
        const next = {}
        let firstErr = ''
        GRAD_FAIL_GROUPS.forEach((g, idx) => {
          const r = results[idx]
          const pg = this.reasonPagination[g.status]
          if (r.code === 0) {
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
        this.error = (e && e.message) || '不通过原因加载失败'
      } finally {
        this.loading = false
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
    openDetail(row) {
      this.detail = { visible: true, row }
      this.finalConclusion = 'GRADUATED'
    },
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
      this.collegeRejectDlg.visible = true
    },
    async doCollegeReject({ reason } = {}) {
      if (this.detailBusy || !this.detail.row) return
      const note = String(reason || '').trim()
      if (note.length < 5) { toast.error('退回原因不少于 5 字'); return }
      this.detailBusy = true
      try {
        const res = await academicAffairsApi.collegeReviewGrad(this.detail.row.resultId, 'REJECT', note)
        if (res.code === 0) {
          toast.success('已处理')
          this.collegeRejectDlg.visible = false
          this.detail.visible = false
          await this.loadTab()
        } else toast.error(res.message || '处理失败')
      } catch (e) {
        toast.error((e && e.message) || '处理失败')
      } finally {
        this.detailBusy = false
      }
    },
    async doCollegeReview(action) {
      if (this.detailBusy || action !== 'APPROVE' || !this.canCollegeApprove(this.detail.row)) return
      this.detailBusy = true
      try {
        const res = await academicAffairsApi.collegeReviewGrad(this.detail.row.resultId, 'APPROVE', '')
        if (res.code === 0) {
          toast.success('已处理')
          this.detail.visible = false
          await this.loadTab()
        } else toast.error(res.message || '处理失败')
      } catch (e) {
        toast.error((e && e.message) || '处理失败')
      } finally {
        this.detailBusy = false
      }
    },
    confirmFinal() {
      if (this.finalDlg.submitting || !this.canNormalFinal(this.detail.row)) {
        toast.error('系统预审仍为异常，禁止打开普通终审确认')
        return
      }
      this.finalDlg.visible = true
    },
    async doFinal() {
      if (this.finalDlg.submitting || !this.detail.row) return
      if (!this.canNormalFinal(this.detail.row)) {
        this.finalDlg.visible = false
        toast.error('系统预审已变化或仍为异常，请重新加载并治理阻断项')
        return
      }
      const resultId = this.detail.row.resultId
      this.finalDlg.submitting = true
      try {
        const fresh = await academicAffairsApi.getGradResult(resultId)
        if (fresh.code !== 0) { toast.error(fresh.message || '终审前状态重读失败'); return }
        this.detail.row = fresh.data
        if (!this.canNormalFinal(fresh.data)) {
          this.finalDlg.visible = false
          toast.error('终审前状态已变化，请重新核对最新预审结果')
          await this.loadTab()
          return
        }
        const res = await academicAffairsApi.finalGrad(resultId, this.finalConclusion, true)
        if (res.code === 0) {
          toast.success('终审完成，已写学籍')
          this.finalDlg.visible = false
          this.detail.visible = false
          await this.loadBatches()
          await this.loadTab()
        } else toast.error(res.message || '终审失败')
      } catch (e) {
        toast.error((e && e.message) || '终审失败')
      } finally {
        this.finalDlg.submitting = false
      }
    },
    confirmArchive() {
      if (!this.batchId || this.archiving) return
      this.archiveDlg.visible = true
    },
    async doArchive() {
      if (!this.batchId || this.archiving) return
      const batchId = this.batchId
      this.archiving = true
      try {
        const res = await academicAffairsApi.archiveGradBatch(batchId)
        if (res.code === 0) {
          toast.success(`已归档 ${res.data.archived} 条`)
          this.archiveDlg.visible = false
          await this.loadBatches()
          await this.loadTab()
        } else toast.error(res.message || '归档失败')
      } catch (e) {
        toast.error((e && e.message) || '归档失败')
      } finally {
        this.archiving = false
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.agc-overview {
  overflow: hidden;
  border: 1px solid #dbe6f6;
  border-radius: 20px;
  background:
    radial-gradient(circle at 91% 10%, rgba(59, 130, 246, .13), transparent 30%),
    linear-gradient(135deg, #fff 0%, #f9fbff 60%, #f1f6ff 100%);
  box-shadow: 0 20px 48px -40px rgba(37, 99, 235, .55);
}
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
  .agc-overview__top { grid-template-columns: 1fr; }
  .agc-metrics { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .agc-metrics article { border-bottom: 1px solid #e8eef7; }
}
@media (max-width: 760px) {
  .agc-overview__top { padding: 20px; }
  .agc-overview__copy h2 { font-size: 21px; }
  .agc-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .agc-items { grid-template-columns: 1fr; }
  .agc-detail-head { align-items: flex-start; flex-direction: column; }
}
@media (max-width: 520px) {
  .agc-metrics { grid-template-columns: 1fr; }
  .agc-metrics article { border-right: 0; }
  .agc-tab { width: 100%; text-align: left; }
}
</style>
