<template>
  <ModulePageShell
    :title="pageSpec.title"
    :subtitle="pageSpec.subtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    show-subtitle-in-concise
  >
    <template #actions>
      <AppButton variant="ghost" size="small" @click="showSource = !showSource">来源与还原说明</AppButton>
      <AppButton
        v-if="pageSpec.primary"
        variant="primary"
        size="small"
        :disabled="primaryDisabled"
        :loading="saving"
        @click="runPrimaryAction"
      >{{ pageSpec.primary }}</AppButton>
    </template>

    <AppInlineAlert v-if="showSource" type="info" :description="pageSpec.sourceNote" />
    <AppInlineAlert
      v-if="!currentTermId"
      type="warning"
      title="尚未设置当前学期"
      description="教材目录和库存仍可查看；审核、征订、发放和费用写操作必须先在学年学期中设置当前学期。"
    />

    <AaTextbookObjectBar
      v-if="showObjectBar && selectedObject"
      :title="selectedObject.primary"
      :object-type="pageSpec.object"
      :object-id="selectedObject.objectId"
      :term-name="currentTermName"
      :source="pageSpec.source"
      :status-label="statusLabel(selectedObject.status)"
      :current-owner="pageSpec.role"
      :next-owner="pageSpec.nextRole"
    />
    <AaTextbookStageRail v-if="showStageRail" :current="pageSpec.stage" />

    <section v-if="showObjectBar" class="aatb-guidance">
      <div><span>为什么轮到我</span><strong>{{ pageSpec.whyMe }}</strong></div>
      <div><span>当前阻断</span><strong>{{ blockerText }}</strong></div>
      <div><span>办理后交接</span><strong>{{ pageSpec.nextRole }}</strong></div>
    </section>

    <ErrorState v-if="error" :description="error" @retry="reload" />
    <LoadingState v-else-if="loading" />
    <template v-else>
      <AppInlineAlert v-if="tab === 'stock' && rows.some(row => row.dataConflict)" type="danger" title="库存记录存在冲突" description="已签收与待签收占用超过到货数量。请核对到货、发放及退领原记录；负数按实际差额展示，不视为可继续发放。" />
      <section class="aatb-metrics" aria-label="教材业务指标">
        <article v-for="metric in metricCards" :key="metric.label" :class="{ 'is-warning': metric.warning }">
          <span>{{ metric.label }}</span><strong>{{ metric.value }}</strong><small>{{ metric.note }}</small>
        </article>
      </section>

      <template v-if="tab === 'stats'">
        <section class="aatb-analytics">
          <article class="aatb-panel">
            <header><h2>教材闭环 · 当前正式数量</h2><span>数据来自教材统计接口</span></header>
            <div class="aatb-bars">
              <div v-for="item in statsBars" :key="item.label">
                <span>{{ item.label }}</span><i><b :style="{ width: `${item.percent}%` }" /></i><strong>{{ item.value }}</strong>
              </div>
            </div>
          </article>
          <article class="aatb-panel">
            <header><h2>本校汇总口径</h2><span>全部学期</span></header>
            <dl class="aatb-facts">
              <div><dt>选用与备案</dt><dd>{{ stats.selectionApproved || 0 }} / {{ stats.selectionTotal || 0 }}</dd></div>
              <div><dt>征订与到货</dt><dd>{{ stats.arrivedQty || 0 }} / {{ stats.orderQty || 0 }}</dd></div>
              <div><dt>未结费用</dt><dd>¥{{ money(stats.unpaidAmount) }}</dd></div>
              <div><dt>周期趋势</dt><dd>服务端未提供按周序列</dd></div>
            </dl>
          </article>
        </section>
        <section class="aatb-table-card">
          <header><div><h2>同口径明细下钻</h2><p>到货、发放、签收和费用分别按正式业务记录核对</p></div></header>
          <DataTable :columns="statsColumns" :rows="statsRows" row-key="key" />
        </section>
      </template>

      <section v-else class="aatb-table-card">
        <header>
          <div><h2>{{ pageSpec.tableTitle }}</h2><p>{{ pageSpec.tableNote }}</p></div>
          <span>共 {{ total }} 条 · 正式数据接入服务端分页</span>
        </header>
        <div class="aatb-toolbar">
          <AppTextInput v-model="keyword" :placeholder="`搜索${pageSpec.title}`" :disabled="saving" @keyup.enter="search" />
          <AppButton size="small" :disabled="saving" @click="search">查询</AppButton>
          <button class="aatb-clear" :disabled="saving" @click="clearSearch">清空</button>
          <small v-if="tab !== 'catalog' && keyword">当前接口未提供关键词参数，仅筛选本页已读取记录</small>
        </div>
        <EmptyState v-if="!filteredRows.length" title="暂无数据" :description="emptyHint" />
        <DataTable
          v-else
          :columns="columns"
          :rows="filteredRows"
          :row-key="rowKey"
          :pagination="{ page, pageSize, total }"
          @page-change="turnPage"
        >
          <template #cell-primary="{ row }"><button class="aatb-object-link" @click="selectRow(row)">{{ row.primary }}</button><small>{{ row.secondary }}</small></template>
          <template #cell-status="{ row }"><StatusTag :type="statusType(row.status)" :label="statusLabel(row.status)" dot /></template>
          <template #cell-price="{ row }">{{ row.unitPrice == null ? '—' : `¥${money(row.unitPrice)}` }}</template>
          <template #cell-amount="{ row }">¥{{ money(row.amount) }}</template>
          <template #cell-paid="{ row }">¥{{ money(row.paidAmount) }} / ¥{{ money(row.amount) }}</template>
          <template #cell-progress="{ row }"><strong>待签收 {{ row.pendingCount || 0 }} · 已签收 {{ row.receivedCount || 0 }}</strong><small>退领 {{ row.returnedCount || 0 }} · 未结费用 {{ row.unsettledFeeCount || 0 }}</small></template>
          <template #cell-ops="{ row }">
            <button v-if="tab === 'catalog'" class="mp-link" @click="openTextbook(row)">打开</button>
            <template v-else-if="tab === 'selection'">
              <button class="mp-link" @click="selectRow(row)">查看来源</button>
              <button v-if="row.status === 'DRAFT'" class="mp-link" @click="confirmSelectionSubmit(row)">提交</button>
              <button v-if="row.status === 'DRAFT'" class="mp-link is-danger" @click="confirmSelectionWithdraw(row)">撤回</button>
            </template>
            <template v-else-if="tab === 'review'">
              <button class="mp-link" @click="selectRow(row)">查看证据</button>
              <button v-if="canAdvance(row.status)" class="mp-link" @click="confirmAdvance(row)">推进</button>
              <button v-if="canAdvance(row.status)" class="mp-link is-danger" @click="advanceReturn(row.reviewBatchId)">退回</button>
            </template>
            <template v-else-if="tab === 'order'">
              <button class="mp-link" @click="selectRow(row)">打开</button>
              <button v-if="row.status === 'DRAFT'" class="mp-link" @click="confirmOrderSubmit(row)">提交征订</button>
              <button v-if="['DRAFT','ORDERED'].includes(row.status)" class="mp-link is-danger" @click="cancelOrder(row)">取消</button>
              <button v-if="['ORDERED','PARTIALLY_ARRIVED'].includes(row.status)" class="mp-link" @click="openArrival(row)">到货登记</button>
              <button v-if="['PARTIALLY_ARRIVED','ARRIVED','ARCHIVED'].includes(row.status)" class="mp-link" @click="openDistributionGenerate(row)">生成发放名单</button>
              <button v-if="row.status === 'ARRIVED'" class="mp-link" @click="confirmOrderArchive(row)">归档</button>
            </template>
            <button v-else-if="tab === 'distribution'" class="mp-link" @click="openDistribution(row)">发放明细</button>
            <template v-else-if="tab === 'fee'">
              <button class="mp-link" @click="selectRow(row)">打开</button>
              <button v-if="['UNPAID','PARTIAL'].includes(row.status)" class="mp-link" @click="confirmFeePaid(row)">全额收款</button>
              <button v-if="['UNPAID','PARTIAL'].includes(row.status)" class="mp-link" @click="openPartial(row)">部分收款</button>
              <button v-if="row.status === 'UNPAID'" class="mp-link is-danger" @click="waiveFee(row.feeId)">减免</button>
            </template>
            <button v-else class="mp-link" @click="selectRow(row)">打开</button>
          </template>
        </DataTable>
      </section>
    </template>

    <AppDrawer :visible="tbVisible" :title="editingTextbookId ? '编辑教材目录' : '新建教材'" mode="modal" size="medium" @close="tbVisible = false">
      <div class="aatb-form-grid">
        <AppFormItem label="教材名称" required><AppTextInput v-model="tbForm.name" :disabled="saving" /></AppFormItem>
        <AppFormItem label="ISBN"><AppTextInput v-model="tbForm.isbn" :disabled="saving || !!editingTextbookId" /></AppFormItem>
        <AppFormItem label="版本"><AppTextInput v-model="tbForm.edition" :disabled="saving" /></AppFormItem>
        <AppFormItem label="出版社"><AppTextInput v-model="tbForm.publisher" :disabled="saving" /></AppFormItem>
        <AppFormItem label="适用课程/学科"><AppTextInput v-model="tbForm.subject" :disabled="saving" /></AppFormItem>
        <AppFormItem label="定价"><AppNumberInput v-model="tbForm.unitPrice" :min="0" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="formError" class="aatb-form-wide" type="danger" :description="formError" />
      </div>
      <template #footer><AppButton variant="ghost" :disabled="saving" @click="tbVisible = false">取消</AppButton><AppButton variant="primary" :loading="saving" @click="submitTextbook">保存目录</AppButton></template>
    </AppDrawer>

    <AppDrawer :visible="selectionVisible" title="教材选用正式申报" mode="modal" size="large" @close="selectionVisible = false">
      <AppInlineAlert type="info" title="第四级对象视角" description="从正式教学任务开始，教材版本和需求人数提交后进入教材选用审核岗。" />
      <div class="aatb-form-grid">
        <AppFormItem label="教学任务" required><AppTeachingTaskPicker v-model="selectionForm.taskId" :query="{ termId: currentTermId || undefined }" :disabled="saving" /></AppFormItem>
        <AppFormItem label="教材版本" required><AppSelect v-model="selectionForm.textbookId" :options="textbookOptions" placeholder="选择正式教材目录" :disabled="saving || selectionCatalogLoading" /></AppFormItem>
        <AppFormItem label="需求人数" required><AppNumberInput v-model="selectionForm.expectedQty" :min="1" :disabled="saving" /></AppFormItem>
        <AppFormItem class="aatb-form-wide" label="选用原因" required><AppTextarea v-model="selectionForm.remark" :disabled="saving" placeholder="说明课程、版本和实际需求依据" /></AppFormItem>
        <AppInlineAlert v-if="selectionError" class="aatb-form-wide" type="danger" :description="selectionError" />
      </div>
      <template #footer><AppButton variant="ghost" :disabled="saving" @click="selectionVisible = false">返回来源工作区</AppButton><AppButton variant="primary" :loading="saving" :disabled="!selectionCanSubmit" @click="submitSelection">提交教材选用申报</AppButton></template>
    </AppDrawer>

    <AppDrawer :visible="arrivalVisible" title="登记到货验收" mode="modal" size="medium" @close="arrivalVisible = false">
      <div class="aatb-form-stack">
        <AppInlineAlert type="info" description="到货数量是累计值，只能增加且不能超过征订数量；登记后重新读取正式明细。" />
        <p v-if="arrivalRow">征订批次：{{ arrivalRow.batchName || arrivalRow.orderBatchId }}</p>
        <LoadingState v-if="arrivalLoading" />
        <ErrorState v-else-if="arrivalError" :description="arrivalError" @retry="openArrival(arrivalRow)" />
        <EmptyState v-else-if="!arrivalItems.length" title="无征订明细" description="当前正式批次没有可登记的教材明细。" />
        <ul v-else class="aatb-items"><li v-for="item in arrivalItems" :key="item.itemId"><span>{{ item.textbookName }}（订 {{ item.orderQty }} / 到 {{ item.arrivedQty }}）</span><span class="aatb-arr"><AppNumberInput v-model="arrivalQty[item.itemId]" :min="item.arrivedQty || 0" :max="item.orderQty" /><AppButton size="small" variant="ghost" @click="submitArrival(item.itemId)">登记</AppButton></span></li></ul>
      </div>
    </AppDrawer>

    <AppDrawer :visible="partialVisible" title="部分收款" mode="modal" size="medium" @close="partialVisible = false">
      <div v-if="partialRow" class="aatb-form-stack"><AppFormItem label="教材"><span>{{ partialRow.textbookName }}</span></AppFormItem><AppFormItem label="应收 / 已收"><span>¥{{ money(partialRow.amount) }} / ¥{{ money(partialRow.paidAmount) }}</span></AppFormItem><AppFormItem label="本次收款" required><AppNumberInput v-model="partialAmount" :min="0" /></AppFormItem></div>
      <AppInlineAlert type="info" description="仅登记已实际收到的款项。若提示结果未确认，请先刷新费用台账核对已收金额；系统会阻止旧记录重复累计。" />
      <template #footer><AppButton variant="ghost" :disabled="saving" @click="partialVisible = false">取消</AppButton><AppButton variant="primary" :loading="saving" :disabled="saving" @click="submitPartial">确认收款</AppButton></template>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="confirmVisible" :title="confirmTitle" :message="confirmMessage" @confirm="onConfirm" />
    <AppConfirmDialog v-model:visible="reasonDialog.visible" :title="reasonDialog.title" type="danger" require-reason :phrase-scene-key="reasonDialog.sceneKey" reason-label="原因（≥5字）" :submitting="reasonDialog.submitting" @confirm="onReasonConfirm" />
  </ModulePageShell>
</template>

<script>
import { DataTable, EmptyState, ErrorState, LoadingState, ModulePageShell, StatusTag } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppConfirmDialog, AppFormItem, AppInlineAlert, AppNumberInput, AppSelect, AppTeachingTaskPicker, AppTextarea, AppTextInput } from '@/components/common'
import AaTextbookObjectBar from '@/modules/academicAffairs/components/textbooks/AaTextbookObjectBar.vue'
import AaTextbookStageRail from '@/modules/academicAffairs/components/textbooks/AaTextbookStageRail.vue'
import { academicAffairsApi, academicAffairsTextbookApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { textbookP0Api } from '@/modules/academicAffairs/api/textbook-p0.api'
import { currentUserFromToken } from '@/services/http/client'
import { toast } from '@/utils/toast'
import { textbookQueuePage, textbookQueueReturnPath } from '../components/textbooks/textbookNavigation.js'

const LABELS = {
  ENABLED: '在用', DISABLED: '停用', DRAFT: '草稿', SUBMITTED: '已提交', REVIEWING: '审核中',
  COLLEGE_REVIEWING: '学院审核中', COLLEGE_APPROVED: '学院已通过', ACADEMIC_APPROVED: '教务已通过', PUBLISHED: '已备案',
  APPROVED: '已备案', RETURNED: '已退回', ORDERED: '已征订', PARTIALLY_ARRIVED: '部分到货', ARRIVED: '已到货',
  ARCHIVED: '已归档', CANCELLED: '已取消', DISTRIBUTING: '发放中', COMPLETED: '已完成', UNPAID: '未收款',
  PARTIAL: '部分收款', PAID: '已结清', WAIVED: '已减免'
}

const PAGE_SPEC = {
  catalog: { title: '教材目录', subtitle: '教材版本与课程选用分开维护', object: '教材目录', primary: '新建教材', role: '教材目录管理岗', nextRole: '任课教师 / 课程负责人选用', source: '教材目录管理岗正式建立', sourceNote: '目录只维护教材版本事实；选用、征订、发放和费用继续使用各自正式业务记录。', whyMe: '维护可供正式选用的教材版本', stage: 0, tableTitle: '教材目录 · 数量与来源', tableNote: 'ISBN、版本、出版社和适用课程来自正式教材目录' },
  selection: { title: '教材选用', subtitle: '使用教学任务和名单测算，不手工造学生名单', object: '教材选用申报', primary: '从教学任务申报', role: '任课教师 / 课程负责人', nextRole: '教材选用审核岗', source: '正式教学任务', sourceNote: '选用必须绑定正式教学任务和教材目录；需求人数由课程负责人申报，提交后进入审核。', whyMe: '当前教学任务需要确定教材版本和需求数量', stage: 0, tableTitle: '教材选用申报 · 候选与正式结果', tableNote: '教学任务、教材、需求人数、申报人和审核状态同屏核对' },
  review: { title: '审核备案', subtitle: '审核后才能进入征订流程', object: '教材审核批次', primary: '审核选用申报', role: '教材选用审核岗', nextRole: '征订管理岗', source: '已提交教材选用', sourceNote: '审核批次只纳入当前学期已提交选用；推进前显示批次编号和当前正式状态。', whyMe: '选用申报已提交并进入本岗位审核队列', stage: 1, tableTitle: '责任队列', tableNote: '打开批次查看来源，确认对象后推进或退回' },
  order: { title: '征订到货', subtitle: '到货后继续进入发放和签收，不止于采购', object: '教材征订批次', primary: '生成征订 / 补订', role: '教材征订 / 到货岗', nextRole: '教材发放签收岗', source: '已备案教材选用', sourceNote: '征订批次汇总已备案选用；到货按教材明细累计登记，不能超过征订量。', whyMe: '教材选用已备案并等待征订或到货验收', stage: 2, tableTitle: '征订与到货 · 数量与来源', tableNote: '批次状态、到货明细和发放入口按正式记录衔接' },
  distribution: { title: '发放签收', subtitle: '按班级名单逐条登记签收并形成费用', object: '教材发放批次', primary: '', role: '教材发放签收岗', nextRole: '教材费用核对岗', source: '已到货教材征订批次', sourceNote: '发放名单来自正式班级和学生；签收后按征订价格快照生成费用。', whyMe: '教材已到货并已生成班级发放名单', stage: 3, tableTitle: '发放签收批次', tableNote: '待签收、已签收、退领和未结费用分别显示' },
  fee: { title: '费用台账', subtitle: '费用来源于发放事实，不直接覆盖库存', object: '教材费用', primary: '核对费用流水', role: '教材费用核对岗', nextRole: '费用复核与授权查阅', source: '教材发放签收记录', sourceNote: '费用按发放记录与征订价格快照形成；收款和减免不会直接改写库存事实。', whyMe: '签收已形成应收或存在未结费用', stage: 4, tableTitle: '教材费用', tableNote: '学生标识、教材、应收、实收和费用状态同口径核对' },
  stock: { title: '教材库存', subtitle: '库存不足和历史保留分别处理', object: '教材库存', primary: '刷新库存流水', role: '教材库存管理岗', nextRole: '发放 / 退补换责任岗', source: '到货、发放占用与正式签收数量', sourceNote: '可用库存为到货量减已签收及待签收占用量；历史记录不因目录变更被覆盖。', whyMe: '需要核对到货、发放与当前可用库存', stage: 4, tableTitle: '教材库存 · 数量与来源', tableNote: '到货、待签收占用、已签收和可用库存分别呈现' },
  stats: { title: '教材统计', subtitle: '到货、发放、签收不是同一个数量', object: '教材统计', primary: '查看关联办理', role: '教材管理岗', nextRole: '教材选用审核 → 征订到货 → 发放签收岗', source: '教材闭环统计投影', sourceNote: '统计只消费正式业务事实；服务端未提供的周期趋势不使用演示值补齐。', whyMe: '需要从闭环统计定位待处理环节', stage: 4, tableTitle: '同口径明细下钻', tableNote: '从统计返回选用、征订、到货和费用办理' }
}

export default {
  name: 'AaTextbookConsoleView',
  components: { AaTextbookObjectBar, AaTextbookStageRail, AppButton, AppConfirmDialog, AppDrawer, AppFormItem, AppInlineAlert, AppNumberInput, AppSelect, AppTeachingTaskPicker, AppTextarea, AppTextInput, DataTable, EmptyState, ErrorState, LoadingState, ModulePageShell, StatusTag },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } }, currentTermId: '', currentTermName: '',
      tab: 'catalog', loading: true, error: '', rows: [], stats: {}, page: 1, pageSize: 20, total: 0, keyword: '', appliedKeyword: '',
      loadSeq: 0, arrivalSeq: 0, actionSeq: 0, initialized: false, saving: false, showSource: false, activeRowKey: '',
      tbVisible: false, editingTextbookId: '', tbForm: { name: '', isbn: '', edition: '', publisher: '', subject: '', unitPrice: 0 }, formError: '',
      selectionVisible: false, selectionCatalogLoading: false, selectionCatalog: [], selectionError: '', selectionForm: { taskId: '', textbookId: '', expectedQty: 1, remark: '' },
      arrivalVisible: false, arrivalRow: null, arrivalItems: [], arrivalQty: {}, arrivalError: '', arrivalLoading: false,
      partialVisible: false, partialRow: null, partialAmount: 0,
      confirmVisible: false, confirmTitle: '', confirmMessage: '', pendingAction: null,
      reasonDialog: { visible: false, title: '', sceneKey: '', submitting: false, action: null }
    }
  },
  computed: {
    pageSpec() { return PAGE_SPEC[this.tab] || PAGE_SPEC.catalog },
    identityKey() { return JSON.stringify([currentUserFromToken(), this.ctx]) },
    showObjectBar() { return ['selection', 'review'].includes(this.tab) },
    showStageRail() { return ['selection', 'review'].includes(this.tab) },
    primaryDisabled() { return this.saving || (['review', 'order'].includes(this.tab) && !this.currentTermId) },
    visibleRows() { return this.tab === 'stock' ? this.rows.slice((this.page - 1) * this.pageSize, this.page * this.pageSize) : this.rows },
    normalizedRows() {
      return this.visibleRows.map(row => {
        if (this.tab === 'catalog') return { ...row, primary: row.name || '未命名教材', secondary: `${row.isbn || 'ISBN 未维护'} · 目录 ${row.textbookId || '—'}`, objectId: row.textbookId }
        if (this.tab === 'selection') return { ...row, primary: row.courseName || '课程待核对', secondary: `教学任务 ${row.taskId || '未关联'} · 申报 ${row.selectionId || '—'}`, objectId: row.selectionId }
        if (this.tab === 'review') return { ...row, primary: row.batchName || '未命名审核批次', secondary: `审核批次 ${row.reviewBatchId || '—'}`, objectId: row.reviewBatchId }
        if (this.tab === 'order') return { ...row, primary: row.batchName || '未命名征订批次', secondary: `征订批次 ${row.orderBatchId || '—'}`, objectId: row.orderBatchId, detailHint: '打开后读取征订与到货明细' }
        if (this.tab === 'distribution') return { ...row, primary: row.orderBatchName || '教材发放批次', secondary: `${row.className || '班级待核对'} · 发放批次 ${row.distributionBatchId || '—'}`, objectId: row.distributionBatchId }
        if (this.tab === 'fee') return { ...row, primary: row.textbookName || '教材费用', secondary: `学生 ${row.studentName || row.studentId || '待核对'} · 台账 ${row.feeId || '—'}`, objectId: row.feeId }
        return { ...row, primary: row.textbookName || '教材库存', secondary: `教材 ${row.textbookId || '—'} · 以库存流水为准`, objectId: row.textbookId, status: row.stockQty > 0 ? 'ENABLED' : 'DRAFT' }
      })
    },
    filteredRows() { if (!this.appliedKeyword || this.tab === 'catalog') return this.normalizedRows; const keyword = this.appliedKeyword.toLowerCase(); return this.normalizedRows.filter(row => Object.values(row).some(value => String(value ?? '').toLowerCase().includes(keyword))) },
    selectedObject() { return this.normalizedRows.find(row => this.rowKey(row) === this.activeRowKey) || this.normalizedRows[0] || null },
    blockerText() { if (!this.selectedObject) return '当前范围没有可办理对象'; if (this.tab === 'selection') return ({ DRAFT: '待提交审核', SUBMITTED: '等待教材选用审核岗处理', REVIEWING: '等待教材选用审核岗处理', APPROVED: '审核已通过，等待征订岗位建单', ORDERED: '已进入征订批次，可返回征订到货核对', RETURNED: '已退回，等待申报人修订' }[this.selectedObject.status] || '按当前正式状态核对'); if (this.tab === 'review') return this.canAdvance(this.selectedObject.status) ? '需核对来源选用和当前审批节点' : '当前状态无可执行审核动作'; return '按当前正式状态核对' },
    textbookOptions() { return this.selectionCatalog.map(row => ({ label: `${row.name}${row.edition ? ` · ${row.edition}` : ''}`, value: String(row.textbookId) })) },
    selectionCanSubmit() { return Boolean(this.selectionForm.taskId && this.selectionForm.textbookId && Number(this.selectionForm.expectedQty) > 0 && this.selectionForm.remark.trim()) },
    columns() {
      const map = {
        catalog: [{ key: 'primary', title: '教材名称 / ISBN' }, { key: 'edition', title: '版本' }, { key: 'publisher', title: '出版社' }, { key: 'subject', title: '适用课程' }, { key: 'price', title: '定价' }, { key: 'status', title: '状态' }, { key: 'ops', title: '办理入口' }],
        selection: [{ key: 'primary', title: '教学任务' }, { key: 'textbookName', title: '选用教材' }, { key: 'expectedQty', title: '需求人数' }, { key: 'officerKey', title: '申报人' }, { key: 'status', title: '审核状态' }, { key: 'ops', title: '办理入口' }],
        review: [{ key: 'primary', title: '审核批次' }, { key: 'status', title: '备案状态' }, { key: 'rejectReason', title: '审核依据 / 退回原因' }, { key: 'ops', title: '办理入口' }],
        order: [{ key: 'primary', title: '征订单' }, { key: 'status', title: '当前状态' }, { key: 'detailHint', title: '征订 / 到货数量' }, { key: 'ops', title: '办理入口', width: '300px' }],
        distribution: [{ key: 'primary', title: '发放批次' }, { key: 'progress', title: '发放 / 费用' }, { key: 'status', title: '状态' }, { key: 'nextAction', title: '下一责任' }, { key: 'ops', title: '办理入口' }],
        fee: [{ key: 'primary', title: '学生 / 发放来源' }, { key: 'amount', title: '原始应收' }, { key: 'paid', title: '实收 / 原始应收' }, { key: 'status', title: '费用状态' }, { key: 'ops', title: '办理入口' }],
        stock: [{ key: 'primary', title: '教材' }, { key: 'arrivedQty', title: '到货量' }, { key: 'reservedQty', title: '待签收占用' }, { key: 'distributedQty', title: '已签收' }, { key: 'stockQty', title: '可用库存' }, { key: 'ops', title: '办理入口' }]
      }
      return map[this.tab] || []
    },
    metricCards() {
      const count = status => this.rows.filter(row => row.status === status).length
      const sum = field => this.rows.reduce((total, row) => total + Number(row[field] || 0), 0)
      if (this.tab === 'catalog') return [{ label: '目录总数', value: this.total, note: '正式教材目录' }, { label: '本页在用', value: count('ENABLED'), note: '当前页真实状态' }, { label: '本页有定价', value: this.rows.filter(row => row.unitPrice != null).length, note: '目录定价已维护' }, { label: '本页待核验', value: this.rows.filter(row => !row.isbn || !row.publisher).length, note: 'ISBN 或出版社缺失', warning: true }]
      if (this.tab === 'selection') return [{ label: '选用总数', value: this.total, note: '当前数据范围' }, { label: '本页草稿', value: count('DRAFT'), note: '待申报人提交' }, { label: '本页审核中', value: count('SUBMITTED') + count('REVIEWING'), note: '等待审核岗位' }, { label: '本页已备案', value: count('APPROVED') + count('ORDERED'), note: '可进入征订' }]
      if (this.tab === 'review') return [{ label: '审核批次', value: this.total, note: '正式批次总数' }, { label: '本页待办', value: this.rows.filter(row => this.canAdvance(row.status)).length, note: '当前节点可推进', warning: true }, { label: '本页已备案', value: count('PUBLISHED'), note: '可进入征订' }, { label: '本页已退回', value: count('RETURNED'), note: '返回申报人修订' }]
      if (this.tab === 'order') return [{ label: '征订批次', value: this.total, note: '正式批次总数' }, { label: '本页待提交', value: count('DRAFT'), note: '需提交征订' }, { label: '本页到货中', value: count('ORDERED') + count('PARTIALLY_ARRIVED'), note: '等待到货验收', warning: true }, { label: '本页已到货', value: count('ARRIVED') + count('ARCHIVED'), note: '可进入发放' }]
      if (this.tab === 'distribution') return [{ label: '发放批次', value: this.total, note: '正式批次总数' }, { label: '本页待签收', value: sum('pendingCount'), note: '学生发放记录', warning: true }, { label: '本页已签收', value: sum('receivedCount'), note: '已形成发放事实' }, { label: '本页未结费用', value: sum('unsettledFeeCount'), note: '转费用岗位处理' }]
      if (this.tab === 'fee') return [{ label: '费用记录', value: this.total, note: '当前数据范围' }, { label: '本页应收', value: `¥${this.money(this.rows.filter(row => row.status !== 'WAIVED').reduce((total, row) => total + Number(row.amount || 0), 0))}`, note: '已减免金额不计入' }, { label: '本页已收', value: `¥${this.money(sum('paidAmount'))}`, note: '正式收款记录' }, { label: '本页待核对', value: count('UNPAID') + count('PARTIAL'), note: '未收或部分收款', warning: true }]
      if (this.tab === 'stock') return [{ label: '库存品种', value: this.total, note: '有到货或发放记录的教材' }, { label: '账面到货', value: sum('arrivedQty'), note: '以到货流水为准' }, { label: '已签收', value: sum('distributedQty'), note: '正式签收数量' }, { label: '可用库存', value: sum('stockQty'), note: '到货减已签收及待签收占用' }]
      return [{ label: '统计范围', value: '本校全部学期', note: '包含历史记录' }, { label: '选用总数', value: this.stats.selectionTotal || 0, note: '正式选用记录' }, { label: '待处理费用', value: `¥${this.money(this.stats.unpaidAmount)}`, note: '未结不等于欠费结论', warning: true }, { label: '到货率', value: `${Math.round(Number(this.stats.arrivalRate || 0) * 100)}%`, note: `${this.stats.arrivedQty || 0} / ${this.stats.orderQty || 0}` }]
    },
    statsBars() { const values = [{ label: '选用', value: Number(this.stats.selectionTotal || 0) }, { label: '备案', value: Number(this.stats.selectionApproved || 0) }, { label: '征订', value: Number(this.stats.orderQty || 0) }, { label: '到货', value: Number(this.stats.arrivedQty || 0) }]; const max = Math.max(1, ...values.map(item => item.value)); return values.map(item => ({ ...item, percent: Math.max(item.value ? 4 : 0, Math.round(item.value / max * 100)) })) },
    statsColumns() { return [{ key: 'label', title: '业务口径' }, { key: 'value', title: '正式数量' }, { key: 'owner', title: '责任岗位' }, { key: 'note', title: '下钻说明' }] },
    statsRows() { return [{ key: 'selection', label: '教材选用 / 已备案', value: `${this.stats.selectionTotal || 0} / ${this.stats.selectionApproved || 0}`, owner: '教材选用审核岗', note: '进入选用或审核备案核对' }, { key: 'order', label: '征订 / 到货', value: `${this.stats.orderQty || 0} / ${this.stats.arrivedQty || 0}`, owner: '征订到货岗', note: '进入征订到货核对批次明细' }, { key: 'fee', label: '未结费用金额', value: `¥${this.money(this.stats.unpaidAmount)}`, owner: '教材费用核对岗', note: '进入费用台账核对学生记录' }] },
    emptyHint() { return { catalog: '可由教材目录管理岗新建正式目录', selection: '请从正式教学任务发起教材选用', review: '当前学期没有已提交选用可建审核批次', order: '当前学期没有已备案选用可生成征订', distribution: '请从已到货征订批次生成班级发放名单', fee: '学生签收后按征订价格快照生成费用', stock: '征订到货并签收后形成库存口径' }[this.tab] || '' }
  },
  watch: {
    '$route.query.tab'(value) { const next = PAGE_SPEC[value] ? value : 'catalog'; if (this.tab !== next) { this.tab = next; this.resetView(); if (this.initialized) this.reload() } },
    identityKey() { if (this.initialized) { this.loadSeq++; this.actionSeq++; this.saving = false; this.resetView(); this.page = textbookQueuePage(this.$route.query.page); this.rows = []; this.stats = {}; this.total = 0; this.reload() } }
  },
  async created() { const [contextRes, termRes] = await Promise.all([academicAffairsApi.getContext(), academicAffairsApi.getCurrentTerm()]); if (contextRes.code === 0) this.ctx = contextRes.data; if (termRes.code === 0 && termRes.data) { this.currentTermId = String(termRes.data.termId || termRes.data.id || ''); this.currentTermName = termRes.data.termName || termRes.data.name || termRes.data.termCode || '' } const queryTab = this.$route?.query?.tab; this.tab = PAGE_SPEC[queryTab] ? queryTab : 'catalog'; this.page = textbookQueuePage(this.$route.query.page); this.initialized = true; this.reload() },
  beforeUnmount() { this.loadSeq++; this.arrivalSeq++; this.actionSeq++ },
  beforeRouteLeave() { return !this.saving },
  beforeRouteUpdate() { return !this.saving },
  methods: {
    money(value) { return Number(value || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) },
    statusLabel(status) { return LABELS[status] || (status ? '状态待确认' : '—') },
    statusType(status) { if (['ENABLED', 'PAID', 'APPROVED', 'PUBLISHED', 'ARRIVED', 'ARCHIVED', 'COMPLETED'].includes(status)) return 'success'; if (['CANCELLED', 'RETURNED', 'WAIVED', 'DISABLED'].includes(status)) return 'info'; if (['DRAFT', 'PARTIAL', 'PARTIALLY_ARRIVED', 'REVIEWING', 'COLLEGE_REVIEWING', 'COLLEGE_APPROVED', 'ACADEMIC_APPROVED', 'DISTRIBUTING'].includes(status)) return 'warning'; return 'primary' },
    rowKey(row) { return String(row.textbookId || row.selectionId || row.reviewBatchId || row.orderBatchId || row.distributionBatchId || row.feeId || '') },
    selectRow(row) { this.activeRowKey = this.rowKey(row) },
    resetView() { this.page = 1; this.keyword = ''; this.appliedKeyword = ''; this.activeRowKey = ''; this.showSource = false; this.clearDialogs() },
    clearDialogs() { this.arrivalSeq++; this.arrivalVisible = false; this.partialVisible = false; this.tbVisible = false; this.selectionVisible = false; this.reasonDialog.visible = false; this.arrivalItems = []; this.arrivalQty = {}; this.partialRow = null },
    search() { this.page = 1; this.appliedKeyword = this.keyword.trim(); if (this.tab === 'catalog') this.reload() },
    clearSearch() { this.keyword = ''; this.appliedKeyword = ''; this.page = 1; if (this.tab === 'catalog') this.reload() },
    turnPage(value) { this.page = value; this.activeRowKey = ''; this.reload() },
    runPrimaryAction() { if (this.tab === 'catalog') this.openTextbook(); else if (this.tab === 'selection') this.openSelection(); else if (this.tab === 'review') this.createReview(); else if (this.tab === 'order') this.createOrder(); else if (['fee', 'stock'].includes(this.tab)) this.reload(); else if (this.tab === 'stats') this.switchTab('order') },
    switchTab(key) { if (this.saving || key === this.tab) return; this.$router.replace({ query: { ...this.$route.query, tab: key } }) },
    async reload() { const seq = ++this.loadSeq, identity = this.identityKey, tab = this.tab, page = this.page; const current = () => seq === this.loadSeq && identity === this.identityKey && tab === this.tab && page === this.page; this.loading = true; this.error = ''; try { const params = { page, pageSize: this.pageSize, ...(tab === 'catalog' && this.appliedKeyword ? { keyword: this.appliedKeyword } : {}) }; let result; if (tab === 'stats') result = await api.stats(); else if (tab === 'stock') result = await api.stock(); else if (tab === 'catalog') result = await api.listTextbooks(params); else if (tab === 'selection') result = await api.listSelections(params); else if (tab === 'review') result = await api.listReviewBatches(params); else if (tab === 'order') result = await api.listOrderBatches(params); else if (tab === 'distribution') result = await textbookP0Api.listDistributionBatches({ termId: this.currentTermId || undefined, ...params }); else result = await api.feeLedger(params); if (!current()) return; if (result.code !== 0) { this.error = result.message || '教材数据加载失败'; return } if (tab === 'stats') this.stats = result.data || {}; else if (tab === 'stock') { this.rows = result.data?.items || []; this.total = this.rows.length } else { this.rows = result.data?.list || []; this.total = Number(result.data?.total || 0) } } catch (exception) { if (current()) this.error = exception?.message || '教材数据加载失败' } finally { if (current()) this.loading = false } },
    async write(call, success) { if (this.saving) return null; const seq = ++this.actionSeq, identity = this.identityKey, tab = this.tab; const current = () => seq === this.actionSeq && identity === this.identityKey && tab === this.tab; this.saving = true; try { const result = await call(); if (!current()) return null; if (result.code !== 0) { toast.error(result.message || '办理结果未确认，请核对正式记录'); return null } if (success) await success(result); return result } catch (exception) { if (current()) toast.error(exception?.message || '办理结果未确认，请核对正式记录'); return null } finally { if (current()) this.saving = false } },
    prepareConfirm(title, message, action) { this.confirmTitle = title; this.confirmMessage = message; this.pendingAction = { identity: this.identityKey, tab: this.tab, action }; this.confirmVisible = true },
    onConfirm() { const pending = this.pendingAction; this.pendingAction = null; this.confirmVisible = false; if (!pending) return; if (typeof pending === 'function') return pending(); if (pending.identity === this.identityKey && pending.tab === this.tab) pending.action() },
    openTextbook(row) { this.editingTextbookId = row?.textbookId || ''; this.tbForm = { name: row?.name || '', isbn: row?.isbn || '', edition: row?.edition || '', publisher: row?.publisher || '', subject: row?.subject || '', unitPrice: Number(row?.unitPrice || 0) }; this.formError = ''; this.tbVisible = true },
    async submitTextbook() { if (!this.tbForm.name.trim()) { this.formError = '教材名称必填'; return } const body = { ...this.tbForm, name: this.tbForm.name.trim() }; await this.write(() => this.editingTextbookId ? api.updateTextbook(this.editingTextbookId, body) : api.createTextbook(body), () => { toast.success(this.editingTextbookId ? '教材目录已保存' : '教材目录已创建'); this.tbVisible = false; this.reload() }) },
    async openSelection() { this.selectionForm = { taskId: '', textbookId: '', expectedQty: 1, remark: '' }; this.selectionError = ''; this.selectionVisible = true; this.selectionCatalogLoading = true; const identity = this.identityKey; try { const result = await api.listTextbooks({ status: 'ENABLED', page: 1, pageSize: 200 }); if (identity !== this.identityKey || !this.selectionVisible) return; if (result.code !== 0) { this.selectionError = result.message || '教材目录加载失败'; return } this.selectionCatalog = result.data?.list || [] } catch (exception) { if (identity === this.identityKey && this.selectionVisible) this.selectionError = exception?.message || '教材目录加载失败' } finally { if (identity === this.identityKey) this.selectionCatalogLoading = false } },
    async submitSelection() { if (!this.selectionCanSubmit) { this.selectionError = '请完整选择教学任务、教材版本、需求人数并填写选用原因'; return } const body = { taskId: String(this.selectionForm.taskId), textbookId: String(this.selectionForm.textbookId), expectedQty: Number(this.selectionForm.expectedQty), remark: this.selectionForm.remark.trim() }; await this.write(() => api.createSelection(body), () => { toast.success('教材选用申报已建立，请在列表确认后提交审核'); this.selectionVisible = false; this.reload() }) },
    confirmSelectionSubmit(row) { const frozen = { id: row.selectionId, name: row.courseName || row.selectionId }; this.prepareConfirm('提交教材选用申报', `确认提交“${frozen.name}”（申报 ${frozen.id}）？提交后由教材选用审核岗处理。`, () => this.write(() => api.submitSelection(frozen.id), () => { toast.success('已提交审核'); this.reload() })) },
    confirmSelectionWithdraw(row) { const frozen = { id: row.selectionId, name: row.courseName || row.selectionId }; this.prepareConfirm('撤回教材选用草稿', `确认撤回“${frozen.name}”（申报 ${frozen.id}）？`, () => this.write(() => api.withdrawSelection(frozen.id), () => { toast.success('草稿已撤回'); this.reload() })) },
    canAdvance(status) { return ['DRAFT', 'COLLEGE_REVIEWING', 'COLLEGE_APPROVED', 'ACADEMIC_APPROVED'].includes(status) },
    confirmAdvance(row) { const frozen = { id: row.reviewBatchId, name: row.batchName || row.reviewBatchId, status: row.status }; this.prepareConfirm('推进教材审核', `批次“${frozen.name}”（${frozen.id}）当前状态为“${this.statusLabel(frozen.status)}”。确认按正式审核链推进？`, () => this.write(() => api.reviewAdvance(frozen.id, 'APPROVE'), () => { toast.success('审核节点已推进，请核对正式状态'); this.reload() })) },
    advanceReturn(id) { this.reasonDialog = { visible: true, title: '退回教材审核', sceneKey: '', submitting: false, identity: this.identityKey, action: reason => api.reviewAdvance(id, 'RETURN', reason) } },
    async createReview() { if (!this.currentTermId) { toast.error('请先设置当前学期'); return } const termId = this.currentTermId, identity = this.identityKey, termName = this.currentTermName; await this.write(async () => { const candidates = await textbookP0Api.reviewCandidates(termId); if (identity !== this.identityKey || termId !== this.currentTermId) return { code: 1, message: '当前学期或身份已变化' }; if (candidates.code !== 0) return candidates; const ids = (candidates.data?.items || []).map(item => item.selectionId); if (!ids.length) return { code: 1, message: '当前学期无已提交的教材选用' }; return api.createReviewBatch({ batchName: `${termName || '当前学期'}教材审核批次`, termId, selectionIds: ids }) }, () => { toast.success('当前学期审核批次已创建'); this.reload() }) },
    async createOrder() { if (!this.currentTermId) { toast.error('请先设置当前学期'); return } const termId = this.currentTermId; await this.write(() => api.createOrderBatch({ termId }), result => { toast.success(result.data?.supplemental ? '教材补订批次已生成' : '教材征订批次已生成'); this.reload() }) },
    confirmOrderSubmit(row) { const frozen = { id: row.orderBatchId, name: row.batchName || row.orderBatchId }; this.prepareConfirm('提交教材征订', `确认提交征订批次“${frozen.name}”（${frozen.id}）？`, () => this.write(() => api.submitOrder(frozen.id), () => { toast.success('征订批次已提交'); this.reload() })) },
    confirmOrderArchive(row) { const frozen = { id: row.orderBatchId, name: row.batchName || row.orderBatchId }; this.prepareConfirm('归档教材征订', `确认归档已到货批次“${frozen.name}”（${frozen.id}）？`, () => this.write(() => api.archiveOrder(frozen.id), () => { toast.success('征订批次已归档'); this.reload() })) },
    cancelOrder(row) { const id = row.orderBatchId; this.reasonDialog = { visible: true, title: '取消教材征订批次', sceneKey: '', submitting: false, identity: this.identityKey, action: reason => textbookP0Api.cancelOrder(id, reason) } },
    queueReturnPath() { return textbookQueueReturnPath(this.$route.fullPath, this.tab, this.page) },
    openDistributionGenerate(row) { this.$router.push({ name: 'aa-textbook-distribution-new', query: { orderBatchId: row.orderBatchId, returnTo: this.queueReturnPath() } }) },
    openDistribution(row) { this.$router.push({ name: 'aa-textbook-distribution-detail', params: { batchId: row.distributionBatchId }, query: { returnTo: this.queueReturnPath() } }) },
    async openArrival(row) { const seq = ++this.arrivalSeq, identity = this.identityKey, id = row.orderBatchId; const current = () => seq === this.arrivalSeq && identity === this.identityKey && this.arrivalVisible && id === this.arrivalRow?.orderBatchId; this.arrivalRow = { ...row }; this.arrivalVisible = true; this.arrivalQty = {}; this.arrivalItems = []; this.arrivalError = ''; this.arrivalLoading = true; try { const result = await api.orderItems(id); if (!current()) return; if (result.code !== 0) { this.arrivalError = result.message || '征订明细加载失败'; return } this.arrivalItems = result.data?.items || []; this.arrivalItems.forEach(item => { this.arrivalQty[item.itemId] = item.arrivedQty }) } catch (exception) { if (current()) this.arrivalError = exception?.message || '征订明细加载失败' } finally { if (current()) this.arrivalLoading = false } },
    async submitArrival(itemId) { const row = { ...this.arrivalRow }, quantity = this.arrivalQty[itemId], identity = this.identityKey, seq = this.arrivalSeq; if (!this.arrivalItems.some(item => item.itemId === itemId)) return; await this.write(() => api.recordArrival(itemId, quantity ?? 0), async () => { toast.success('到货累计量已登记'); const result = await api.orderItems(row.orderBatchId); if (identity !== this.identityKey || seq !== this.arrivalSeq) return; if (result.code === 0) this.arrivalItems = result.data?.items || []; else this.arrivalError = result.message || '已登记，明细刷新失败，请重新查询'; this.reload() }) },
    openPartial(row) { if (this.saving) return; this.partialRow = { ...row, identity: this.identityKey }; this.partialAmount = 0; this.partialVisible = true },
    async submitPartial() {
      if (this.saving || !this.partialVisible || this.partialRow?.identity !== this.identityKey || this.tab !== 'fee') return
      const amount = Number(this.partialAmount), row = { ...this.partialRow }, paid = Number(row.paidAmount)
      if (!Number.isFinite(amount) || amount <= 0 || Math.abs(amount * 100 - Math.round(amount * 100)) > 0.000001) { toast.error('收款金额须大于0，且最多两位小数'); return }
      if (!row.feeId || !Number.isFinite(paid) || amount > Number(row.amount) - paid) { toast.error('请核对正式已收金额，本次不能超过待收金额'); return }
      await this.write(() => api.markFee(row.feeId, 'PARTIAL', amount, '', paid), () => { toast.success('部分收款已登记'); this.partialVisible = false; this.reload() })
    },
    confirmFeePaid(row) { const frozen = { id: row.feeId, name: row.textbookName || row.feeId, amount: row.amount, paid: row.paidAmount }; this.prepareConfirm('登记教材费全额收款', `确认将“${frozen.name}”台账 ${frozen.id} 登记为全额收款？应收 ¥${this.money(frozen.amount)}，当前已收 ¥${this.money(frozen.paid)}。`, () => this.write(() => api.markFee(frozen.id, 'PAID', undefined, '', frozen.paid), result => { toast.success(result.data?.idempotent ? '费用已处于终态' : '费用已结清'); this.reload() })) },
    waiveFee(id) { this.reasonDialog = { visible: true, title: '减免教材费', sceneKey: 'aa.textbook.reduce', submitting: false, identity: this.identityKey, action: reason => api.markFee(id, 'WAIVE', undefined, reason) } },
    async onReasonConfirm({ reason }) { const dialog = this.reasonDialog; if (!dialog.visible || !dialog.action || dialog.identity !== this.identityKey || this.saving) return; dialog.submitting = true; try { await this.write(() => dialog.action(reason), () => { if (this.reasonDialog === dialog) dialog.visible = false; toast.success('办理成功，请核对更新后的正式记录'); this.reload() }) } finally { if (this.reasonDialog === dialog && dialog.identity === this.identityKey) dialog.submitting = false } }
  }
}
</script>

<style scoped>
.aatb-guidance { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1px; overflow: hidden; border: 1px solid #dbe4ef; border-radius: 10px; background: #dbe4ef; }
.aatb-guidance div { display: grid; gap: 4px; padding: 11px 14px; background: #f8fbff; }.aatb-guidance span { color: #7a889d; font-size: 11px; }.aatb-guidance strong { color: #28405e; font-size: 12px; }
.aatb-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }.aatb-metrics article { display: grid; gap: 5px; min-height: 82px; padding: 14px 16px; border: 1px solid #d8e2ef; border-radius: 10px; background: #fff; }.aatb-metrics article.is-warning { border-color: #ecd09c; background: #fff8ea; }.aatb-metrics span { color: #64758b; font-size: 12px; }.aatb-metrics strong { color: #243b59; font-size: 25px; line-height: 1; }.aatb-metrics small { color: #8794a7; font-size: 11px; }
.aatb-table-card, .aatb-panel { overflow: hidden; border: 1px solid #d8e2ee; border-radius: 10px; background: #fff; }.aatb-table-card > header, .aatb-panel > header { display: flex; align-items: center; justify-content: space-between; gap: 16px; min-height: 48px; padding: 10px 16px; border-bottom: 1px solid #e3eaf2; }.aatb-table-card h2, .aatb-panel h2 { margin: 0; color: #24374f; font-size: 14px; }.aatb-table-card header p { margin: 3px 0 0; color: #7b899b; font-size: 11px; }.aatb-table-card header > span, .aatb-panel header > span { color: #7c899a; font-size: 11px; }
.aatb-toolbar { display: flex; align-items: center; gap: 10px; padding: 10px 16px; border-bottom: 1px solid #e3eaf2; }.aatb-toolbar :deep(.app-text-input) { max-width: 280px; }.aatb-toolbar small { margin-left: auto; color: #966317; }.aatb-clear { border: 0; background: transparent; color: #5d6d82; cursor: pointer; }
.aatb-object-link { padding: 0; border: 0; background: transparent; color: #245aa5; font: inherit; font-weight: 650; cursor: pointer; }.aatb-object-link + small, :deep(td small) { display: block; margin-top: 3px; color: #8190a3; font-size: 10px; }
.aatb-analytics { display: grid; grid-template-columns: 1.05fr .95fr; gap: 14px; }.aatb-bars { display: grid; gap: 18px; padding: 22px 18px; }.aatb-bars > div { display: grid; grid-template-columns: 64px 1fr 54px; align-items: center; gap: 10px; color: #52647c; font-size: 12px; }.aatb-bars i { overflow: hidden; height: 9px; border-radius: 99px; background: #edf2f8; }.aatb-bars b { display: block; height: 100%; border-radius: inherit; background: #3e72c4; }.aatb-bars strong { text-align: right; color: #294d7c; }
.aatb-facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin: 0; padding: 18px; }.aatb-facts div { min-height: 58px; padding: 11px 12px; border-radius: 8px; background: #f5f8fc; }.aatb-facts dt { color: #7b899b; font-size: 11px; }.aatb-facts dd { margin: 7px 0 0; color: #2d435e; font-size: 15px; font-weight: 650; }
.aatb-form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px 16px; }.aatb-form-wide { grid-column: 1 / -1; }.aatb-form-stack { display: flex; flex-direction: column; gap: 12px; }.aatb-items { display: flex; flex-direction: column; gap: 8px; margin: 0; padding: 0; list-style: none; }.aatb-items li { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 9px 0; border-bottom: 1px solid #edf1f5; }.aatb-arr { display: flex; align-items: center; gap: 8px; }
@media (max-width: 900px) { .aatb-metrics, .aatb-guidance, .aatb-analytics { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 640px) { .aatb-metrics, .aatb-guidance, .aatb-analytics, .aatb-form-grid { grid-template-columns: 1fr; }.aatb-form-wide { grid-column: auto; }.aatb-toolbar { align-items: stretch; flex-direction: column; }.aatb-toolbar small { margin-left: 0; } }
</style>
