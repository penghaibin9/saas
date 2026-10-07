<template>
  <ModulePageShell
    class="aarw-registration"
    :title="tabs.find(item => item.key === tab)?.label || '注册工作台'"
    subtitle="注册资格核验 · 未注册学生处理 · 暂缓注册审批 · 注册异常处理 · 注册归档"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    show-subtitle-in-concise
  >
    <template #actions>
      <AppButton v-if="$route.query.returnToken" variant="ghost" @click="returnToOrigin">返回原位置</AppButton>
    </template>
    <div class="aarw-tabs">
      <button v-for="t in tabs" :key="t.key" :class="['aarw-tab', { 'is-active': tab === t.key }]" @click="switchTab(t.key)">{{ t.label }}</button>
    </div>

    <AppSectionCard v-if="tab !== 'archive'" class="aarw-batch-bar" compact>
      <div class="aarw-batch-row">
        <label class="aarw-batch-label">批次</label>
        <AppRegistrationBatchPicker v-model="batchId" :options="batchOptions" placeholder="选择注册批次" style="max-width:280px" @change="onBatchChange" />
        <template v-if="tab === 'eligibility'">
          <AppTextInput v-model="elig.keyword" class="aarw-filter-keyword" placeholder="按学号 / 姓名检索" clearable @change="loadEligibility" />
          <AppSelect v-model="elig.status" class="aarw-filter-status" :options="eligStatusOptions" placeholder="全部核验结果" @change="loadEligibility" />
          <AppButton variant="ghost" @click="loadEligibility">查询</AppButton>
        </template>
        <span v-else class="mp-note aarw-batch-hint">{{ batchHint }}</span>
      </div>
    </AppSectionCard>

    <div v-if="tab === 'deferral' || tab === 'exception'" class="mp-stack">
      <AppInlineAlert v-if="registrationWrite.error && registrationActionVisible(registrationWrite.context)" type="danger" :description="registrationWrite.error" />
      <AppInlineAlert v-if="registrationWrite.pending && !registrationWrite.busy" type="warning">
        <template v-if="exceptionCreateIdentity() === registrationWrite.pending.identityKey && !registrationWrite.pending.denied">
          {{ registrationWrite.pending.label }}：原批次 {{ registrationWrite.pending.batchId }}，学生 {{ registrationWrite.pending.studentId }}。
          {{ registrationWrite.pending.message }}
          <span v-if="registrationWrite.pending.objectId">正式对象 ID：{{ registrationWrite.pending.objectId }}。</span>
          <span v-else>尚未获得正式对象 ID，不能判断未提交。</span>
        </template>
        <template v-else>此前的注册办理请求仍待核对，请使用原身份及有效查看权限处理。</template>
        已暂停这三类动作的重复提交；单次最多核对原批次前 5 页，每页 100 条。
        <AppButton v-if="registrationWrite.pending.objectId" variant="ghost" size="small"
                   :disabled="registrationWrite.checking || !canReadRegistrationAction(registrationWrite.pending)" @click="verifyRegistrationAction">
          {{ registrationWrite.checking ? '正在核对…' : '重新查询正式对象 ID' }}
        </AppButton>
      </AppInlineAlert>
      <AppInlineAlert v-if="registrationWrite.receipt && registrationActionVisible(registrationWrite.receipt)"
                      :type="registrationWrite.receipt.commandConfirmed ? 'success' : 'warning'">
        {{ registrationWrite.receipt.commandConfirmed ? '已收到办理回执并核对正式记录' : '已核对当前记录，本次请求回执仍待确认' }}。
        {{ registrationWrite.receipt.label }}，对象 {{ registrationWrite.receipt.objectId }}，学生 {{ registrationWrite.receipt.studentId }}；
        回读状态：{{ registrationActionStatus(registrationWrite.receipt.domain, registrationWrite.receipt.status) }}。后续状态以正式队列为准。
      </AppInlineAlert>
    </div>

    <!-- 注册资格核验 -->
    <div v-if="tab === 'eligibility'" class="mp-stack">
      <ErrorState v-if="elig.error" :description="elig.error" @retry="loadEligibility" />
      <LoadingState v-else-if="elig.loading" />
      <EmptyState v-else-if="!batchId" title="请先选择批次" description="核验候选名单按批次圈定（入学=待注册在籍生 / 学年=在籍待续生）" />
      <EmptyState v-else-if="!elig.rows.length" title="暂无候选学生" description="该批次下暂无需要核验的学生" />
      <div v-else class="aarw-review-workspace">
        <section class="aarw-object-summary" aria-label="当前注册对象">
          <div v-if="selectedEligRow" class="aarw-object-summary__identity">
            <h2>{{ selectedEligRow.realName || '未命名学生' }}</h2>
            <p>{{ selectedEligRow.studentNo || '学号待核实' }} · {{ selectedBatchLabel }}</p>
            <div class="aarw-object-summary__status">
              <span>来源：本批次资格候选名单</span>
              <StatusTag :type="eligStatusType(selectedEligRow.eligibilityStatus)" :label="objectStatusText(selectedEligRow)" />
            </div>
          </div>
          <p v-else class="aarw-object-empty">请从候选队列选择学生后办理。</p>
          <dl class="aarw-object-summary__responsibility">
            <div><dt>当前操作身份</dt><dd>{{ currentRoleName }}</dd></div>
            <div><dt>下一责任岗位</dt><dd>{{ nextRoleText(selectedEligRow) }}</dd></div>
          </dl>
        </section>

        <ol class="aarw-progress" aria-label="注册办理流程">
          <li v-for="(step, index) in registrationSteps" :key="step.title" :class="{ 'is-current': index === 2, 'is-complete': step.complete }" :aria-current="index === 2 ? 'step' : undefined">
            <span class="aarw-progress__number" aria-hidden="true">{{ step.complete ? '✓' : index + 1 }}</span>
            <div><strong>{{ step.title }}</strong><small>{{ step.detail }}</small></div>
          </li>
        </ol>

        <div class="aarw-elig-layout">
        <aside class="aarw-elig-queue" aria-label="注册资格核验候选队列">
          <div class="aarw-elig-queue__head">
            <strong>资格核验候选队列</strong>
            <span class="mp-note">当前批次共 {{ elig.pagination.total }} 人；每页 {{ elig.pagination.pageSize }}</span>
          </div>
          <div class="aarw-elig-queue__items">
            <button
              v-for="row in elig.rows"
              :key="row.studentId"
              class="aarw-elig-item"
              :class="{ 'is-active': isEligSelected(row) }"
              :disabled="row.registrationStatus === 'REGISTERED'"
              type="button"
              @click="selectEligibilityRow(row)"
            >
              <div class="aarw-elig-item__main">
                <strong>{{ row.realName || '未命名学生' }}</strong>
                <small>{{ row.studentNo || '—' }}</small>
              </div>
              <div class="aarw-elig-item__meta">
                <StatusTag :type="eligStatusType(row.eligibilityStatus)" :label="eligStatusLabel(row.eligibilityStatus)" dot />
                <small>{{ row.className || '班级待确认' }}</small>
              </div>
              <small class="mp-note">{{ row.eligibilityNote || '核验说明待补齐' }}</small>
            </button>
          </div>
          <div class="aarw-elig-queue__pager">
            <button class="mp-link" :disabled="elig.pagination.page <= 1" @click="onEligPage(elig.pagination.page - 1)">上一页</button>
            <span>第 {{ elig.pagination.page }} / {{ Math.max(1, Math.ceil(elig.pagination.total / elig.pagination.pageSize)) }} 页</span>
            <button class="mp-link" :disabled="elig.pagination.page >= Math.max(1, Math.ceil(elig.pagination.total / elig.pagination.pageSize))"
                    @click="onEligPage(elig.pagination.page + 1)">下一页</button>
          </div>
        </aside>

        <div class="aarw-elig-workspace">
          <AppSectionCard class="aarw-object-card" title="当前对象 · 核验证据">
            <div v-if="selectedEligRow" class="aarw-evidence-grid">
              <section v-for="evidence in registrationEvidence" :key="evidence.title" class="aarw-evidence-item">
                <div class="aarw-evidence-item__head">
                  <h3>{{ evidence.title }}</h3>
                  <StatusTag :type="evidence.type" :label="evidence.label" />
                </div>
                <p>{{ evidence.fact }}</p>
                <p class="aarw-evidence-item__note">{{ evidence.note }}</p>
                <button v-if="evidence.source && canViewRegistrationList" type="button" class="mp-link" :disabled="eligSubmitting" @click="goRegistrationList">查看本批次注册名单</button>
              </section>
            </div>
            <p v-else class="aarw-object-empty">请从左侧候选队列选一个对象后办理。</p>
          </AppSectionCard>

          <AppSectionCard title="对象办理操作">
            <AppInlineAlert v-if="eligCommandError" type="danger">{{ eligCommandError }}</AppInlineAlert>
            <AppInlineAlert v-if="eligUnknown" type="warning">批次 {{ eligUnknown.batchId }}、学生 {{ eligUnknown.studentId }} 的核验请求结果待确认，已暂停重复提交。请先查询正式核验记录和注册异常。</AppInlineAlert>
            <AppInlineAlert v-if="eligReceipt && String(eligReceipt.studentId) === String(selectedEligId)" type="success">学生 {{ eligReceipt.studentId }}：{{ eligStatusLabel(eligReceipt.eligibilityStatus) }}。核验记录 {{ eligReceipt.registrationId }}<template v-if="eligReceipt.exceptionId">，已生成注册异常 {{ eligReceipt.exceptionId }}</template>。资格核验不会代替正式注册。</AppInlineAlert>
            <div v-if="selectedEligRow" class="aarw-action-grid">
              <button
                v-if="selectedEligRow.registrationStatus !== 'REGISTERED' && selectedEligRow.eligibilityStatus !== 'ELIGIBLE'"
                class="mp-link"
                :disabled="!canVerifyEligibility || !knownEligibilityState(selectedEligRow) || eligSubmitting || !!eligUnknown"
                @click="askEligible(selectedEligRow)"
              >
                核验通过
              </button>
              <button
                v-if="selectedEligRow.registrationStatus !== 'REGISTERED'"
                class="mp-link is-danger"
                :disabled="!canVerifyEligibility || !knownEligibilityState(selectedEligRow) || eligSubmitting || !!eligUnknown"
                @click="openIneligible(selectedEligRow)"
              >
                标记不合格
              </button>
              <p v-if="selectedEligRow.registrationStatus === 'REGISTERED'" class="mp-note">该学生已完成注册，当前岗位仅展示结果。</p>
              <p v-else-if="selectedEligRow.eligibilityStatus === 'ELIGIBLE'" class="mp-note">该学生已核验通过，建议回到“注册名单”继续办理。</p>
              <AppButton v-if="selectedEligRow.eligibilityStatus === 'ELIGIBLE' && canViewRegistrationList" :disabled="eligSubmitting" @click="goRegistrationList">进入本批次注册名单</AppButton>
              <p v-else-if="selectedEligRow.eligibilityStatus === 'INELIGIBLE'" class="mp-note">该学生不合格，请查看核验说明与注册异常，按实际原因处理。</p>
              <p v-if="!knownEligibilityState(selectedEligRow)" class="mp-note">资格状态待确认，暂不能提交核验。</p>
              <p v-if="!canVerifyEligibility" class="mp-note">核验需具有注册资格核验权限，且批次处于开放状态。</p>
            </div>
            <p v-else class="mp-note">先选中左侧队列中的对象，或返回该批次“注册名单”核查队列范围。</p>
          </AppSectionCard>
        </div>
        </div>
      </div>
    </div>

    <!-- 未注册学生 -->
    <div v-else-if="tab === 'unregistered'" class="mp-stack">
      <AppInlineAlert type="info">先核对所属批次、注册记录与暂缓申请。有效暂缓应按正式期限判断，未注册记录本身不能证明材料不合格或学生已被退学。</AppInlineAlert>
      <div class="aarw-toolbar">
        <AppButton variant="ghost" size="small" :disabled="!canScanUnregistered" @click="askScan">
          {{ scanning ? '扫描中…' : '扫描本批次逾期未注册' }}
        </AppButton>
        <AppButton variant="ghost" size="small" @click="openExport">导出名单</AppButton>
      </div>
      <p class="mp-note">扫描范围为本批次全校候选，包含当前页外学生；跳过有效暂缓批准。入学注册可改变学籍主档，学年/学期注册只标记本批次记录。</p>
      <AppInlineAlert v-if="scanOperation.pending && !scanning" type="warning">存在结果尚未核对的到期扫描请求，已暂停重复扫描。请在原身份、原批次核查正式队列；查询队列不会自动解除未知结果。</AppInlineAlert>
      <AppInlineAlert v-if="scanTargetCurrent(scanOperation.target) && scanOperation.error" type="danger">{{ scanOperation.error }}</AppInlineAlert>
      <AppInlineAlert v-if="scanTargetCurrent(scanOperation.target) && scanOperation.receipt" type="success">
        批次 {{ scanOperation.receipt.batchId }}：标记未注册记录 {{ scanOperation.receipt.marked }} 条；因有效暂缓跳过 {{ scanOperation.receipt.skipped }} 人；新增辅导员待办 {{ scanOperation.receipt.notified }} 条。待办数不代表通知送达或不同辅导员人数。
        <template v-if="scanOperation.target.registerType === 'ENROLL'">入学注册扫描按正式状态入口处理符合条件的学籍主档；本回执未单列主档变更数。</template>
        <template v-else>学年/学期扫描只标记本批次注册记录，不将学籍主档倒退为未注册。</template>
      </AppInlineAlert>
      <AppConfirmDialog v-model:visible="scanConfirm.visible" title="确认扫描逾期未注册" type="warning"
        :message="scanConfirm.message" :submitting="scanning" :confirm-disabled="!canScanUnregistered || !scanTargetCurrent(scanConfirm.target)"
        confirm-text="确认扫描本批次全校候选" @confirm="doScan" />
      <AppSectionCard title="未注册学生 · 责任队列">
      <div class="aarw-toolbar">
        <AppTextInput v-model="unreg.keyword" placeholder="检索本页学生姓名 / 学号" clearable />
        <AppButton variant="ghost" :disabled="unreg.loading" @click="loadUnregistered">刷新本页</AppButton>
        <span class="mp-note">正式队列共 {{ unreg.pagination.total }} 条；姓名检索仅筛选已读取的本页。</span>
      </div>
      <ErrorState v-if="unreg.error" :description="unreg.error" @retry="loadUnregistered" />
      <LoadingState v-else-if="unreg.loading" />
      <EmptyState v-else-if="!unreg.rows.length" title="暂无未注册学生" description="选择批次后可执行「扫描本批次逾期未注册」，或查看全部批次汇总" />
      <DataTable v-else :columns="unregColumns" :rows="unregisteredRows" row-key="queueKey" :pagination="unreg.pagination" @page-change="onUnregPage">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.realName }}</div>
          <div class="mp-cell-sub">{{ row.studentNo }}</div>
        </template>
        <template #cell-registerType="{ row }">{{ regTypeLabel(row.registerType) }}</template>
        <template #cell-batchName="{ row }">
          <div class="mp-cell-main">{{ row.batchName || '批次名称待核对' }}</div>
          <div class="mp-cell-sub">{{ regTypeLabel(row.registerType) }} · 截止 {{ registrationTime(row.windowEnd) }}（本地时间）</div>
        </template>
        <template #cell-eligibility><span class="mp-cell-sub">未提供资格结论</span></template>
        <template #cell-deferral><span class="mp-cell-sub">进入原因核对暂缓</span></template>
        <template #cell-owner><span class="mp-cell-sub">责任老师待核对</span></template>
        <template #cell-kind="{ row }">
          <StatusTag :type="row.kind === 'UNREGISTERED' ? 'danger' : 'warning'" :label="row.kind === 'UNREGISTERED' ? '未注册' : '逾期待扫描'" dot />
        </template>
        <template #cell-actions="{ row }"><AppButton variant="ghost" size="small" @click="openUnregisteredReason(row)">查看原因</AppButton></template>
      </DataTable>
      <p v-if="unreg.rows.length && !unregisteredRows.length" class="mp-note">本页没有匹配学生；这不代表其它页没有记录。</p>
      </AppSectionCard>
      <p class="mp-note">
        「未注册」表示本批次记录已标记 UNREGISTERED；学年/学期记录不代表学籍主档退回未注册。「逾期待扫描」表示本批次已截止且尚未完成注册，仍须由正式扫描判定。
      </p>
    </div>

    <!-- 暂缓注册 -->
    <div v-else-if="tab === 'deferral'" class="mp-stack">
      <div class="aarw-toolbar">
        <AppSelect v-model="defer.status" :options="deferStatusOptions" placeholder="全部状态" @change="loadDeferrals" />
        <AppButton variant="ghost" size="small" @click="loadDeferrals">查询</AppButton>
        <AppButton variant="primary" size="small" :disabled="!batchId || !canRunRegistrationAction('deferral.apply')" @click="openDeferralApply">申请暂缓注册</AppButton>
      </div>
      <ErrorState v-if="defer.error" :description="defer.error" @retry="loadDeferrals" />
      <LoadingState v-else-if="defer.loading" />
      <EmptyState v-else-if="!defer.rows.length" title="暂无暂缓注册申请" description="学生材料未齐/特殊原因时可代其提交暂缓注册申请" />
      <DataTable v-else :columns="deferColumns" :rows="defer.rows" row-key="deferralId" :pagination="defer.pagination" @page-change="onDeferPage">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.realName }}</div>
          <div class="mp-cell-sub">{{ row.studentNo }}</div>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="deferStatusType(row.status)" :label="deferStatusLabel(row.status)" dot />
        </template>
        <template #cell-actions="{ row }">
          <template v-if="row.status === 'PENDING'">
            <button class="mp-link" :disabled="!canRunRegistrationAction('deferral.approve')" @click="askDeferralReview(row, 'APPROVE')">通过</button>
            <button class="mp-link is-danger" :disabled="!canRunRegistrationAction('deferral.approve')" @click="askDeferralReview(row, 'REJECT')">驳回</button>
          </template>
          <span v-else class="mp-cell-sub">{{ row.reviewNote || '—' }}</span>
        </template>
      </DataTable>
    </div>

    <!-- 注册异常 -->
    <div v-else-if="tab === 'exception'" class="mp-stack">
      <div class="aarw-toolbar">
        <AppSelect v-model="exc.status" :options="excStatusOptions" placeholder="全部状态" @change="loadExceptions" />
        <AppButton variant="ghost" size="small" @click="loadExceptions">查询</AppButton>
        <AppButton variant="primary" size="small" :disabled="!canCreateRegistrationException()" @click="openExceptionCreate">标记注册异常</AppButton>
      </div>
      <AppInlineAlert v-if="excCreateError" type="danger" :description="excCreateError" />
      <AppInlineAlert v-if="excPendingCreate" type="warning">
        <template v-if="exceptionCreateIdentity() === excPendingCreate.identityKey && !excPendingCreate.denied">
          批次 {{ excPendingCreate.batchId }}、学生 {{ excPendingCreate.studentId }} 的异常新增结果待核对。
          {{ excPendingCreate.message }}
          <span v-if="excPendingCreate.exceptionId">正式回执 ID：{{ excPendingCreate.exceptionId }}。</span>
          <span v-else>尚未取得可核对的正式异常 ID，不能据此判断未创建。</span>
        </template>
        <template v-else>此前的异常新增请求尚未完成正式记录核对；请使用原身份及有效查看权限核对。</template>
        已暂停重复新增。每次最多核对原批次前 5 页，每页 100 条；未找到不能证明未创建。
        <AppButton v-if="excPendingCreate.exceptionId" variant="ghost" size="small"
                   :disabled="excCreating || excReceiptChecking || !canReadExceptionCreate()" @click="checkExceptionCreateReceipt">
          {{ excReceiptChecking ? '正在核对正式记录…' : '重新查询正式异常 ID' }}
        </AppButton>
      </AppInlineAlert>
      <AppInlineAlert v-if="excCreateReceipt && exceptionCreateIdentity() === excCreateReceipt.identityKey && String(batchId) === excCreateReceipt.batchId" type="success">
        已创建注册异常 {{ excCreateReceipt.exceptionId }}，学生 {{ excCreateReceipt.studentId }}。
        创建后核对状态：{{ excCreateReceipt.status === 'OPEN' ? '待处理（OPEN）' : '已处理（RESOLVED）' }}。后续状态以异常列表为准。
      </AppInlineAlert>
      <ErrorState v-if="exc.error" :description="exc.error" @retry="loadExceptions" />
      <LoadingState v-else-if="exc.loading" />
      <EmptyState v-else-if="!exc.rows.length" title="暂无注册异常" description="核验不合格会自动转入本清单；也可直接标记" />
      <DataTable v-else :columns="excColumns" :rows="exc.rows" row-key="exceptionId" :pagination="exc.pagination" @page-change="onExcPage">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.realName }}</div>
          <div class="mp-cell-sub">{{ row.studentNo }}</div>
        </template>
        <template #cell-exceptionType="{ row }">{{ excTypeLabel(row.exceptionType) }}</template>
        <template #cell-status="{ row }">
          <StatusTag :type="row.status === 'OPEN' ? 'warning' : row.status === 'RESOLVED' ? 'success' : 'default'"
                     :label="row.status === 'OPEN' ? '待处理' : row.status === 'RESOLVED' ? '已处理' : '状态待核对'" dot />
        </template>
        <template #cell-actions="{ row }">
          <button v-if="row.status === 'OPEN'" class="mp-link" :disabled="!canRunRegistrationAction('exception.resolve')" @click="askResolveException(row)">处理</button>
          <span v-else class="mp-cell-sub">{{ row.resolutionNote || '—' }}</span>
        </template>
      </DataTable>
    </div>

    <!-- 注册归档：OPEN→CLOSED→ARCHIVED（关闭/归档动作在「注册批次」列表操作列执行），本页只读查阅+导出 -->
    <div v-else class="mp-stack">
      <ErrorState v-if="archive.error" :description="archive.error" @retry="loadArchive" />
      <LoadingState v-else-if="archive.loading" />
      <EmptyState v-else-if="!archive.rows.length" title="暂无已归档批次" description="批次在「注册批次」列表关闭后再归档，在此核对正式归档标记并查阅名单" />
      <DataTable v-else :columns="archiveColumns" :rows="archive.rows" row-key="batchId" :pagination="archive.pagination" @page-change="onArchivePage">
        <template #cell-registerType="{ row }">{{ regTypeLabel(row.registerType) }}</template>
        <template #cell-completion="{ row }">{{ row.detailError || (row.registered === null ? '—' : `${row.registered} / ${row.total}`) }}</template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="goArchiveDetail(row)">查看名单</button>
          <button class="mp-link" @click="openArchiveExport(row)">导出</button>
        </template>
      </DataTable>
    </div>

    <AppDrawer :visible="unregReason.visible" title="未注册原因核对" mode="modal" size="medium" @close="closeUnregisteredReason">
      <template v-if="unregReason.row">
        <h3>{{ unregReason.row.realName || '学生姓名待核对' }} · {{ unregReason.row.studentNo }}</h3>
        <p>{{ unregReason.row.batchName }} · 学生 {{ unregReason.row.studentId }} · 批次 {{ unregReason.row.batchId }}</p>
        <p>{{ unregReason.row.kind === 'OVERDUE_PENDING_SCAN' ? '注册窗口已截止，尚未完成本批次注册，等待正式扫描判定。' : '本批次已登记为未注册，具体原因须核对资格与暂缓记录；不能据此判断退学。' }}</p>
        <p class="mp-note">资格结论、材料证据及责任老师未在本条队列中提供。以下仅显示同一学生、同一批次的正式暂缓申请。</p>
        <LoadingState v-if="unregReason.loading" />
        <ErrorState v-else-if="unregReason.error" :description="unregReason.error" @retry="readUnregisteredReason" />
        <template v-else>
          <p v-if="!unregReason.deferrals.length">{{ unregReason.exhausted ? '当前正式队列未查到该生在本批次的暂缓申请。' : '已读取的前五页未查到该生；不能据此判断没有申请。' }}</p>
          <div v-for="item in unregReason.deferrals" :key="item.deferralId" class="aarw-reason-record">
            <strong>{{ deferStatusLabel(item.status) }} · 申请 {{ item.deferralId }}</strong>
            <p>{{ item.reason }}</p>
            <p>申请延后至：{{ item.requestedUntil ? registrationTime(item.requestedUntil) : '未设期限，按正式审批结果处理' }}</p>
            <p v-if="item.reviewNote">审批意见：{{ item.reviewNote }}</p>
          </div>
        </template>
      </template>
      <template #footer><AppButton variant="ghost" @click="closeUnregisteredReason">返回原队列</AppButton></template>
    </AppDrawer>

    <!-- 标记核验不合格 / 转注册异常 -->
    <AppDrawer :visible="eligDrawer.visible" title="核验不合格" mode="modal" size="medium" @close="eligDrawer.visible = false">
      <div class="aarw-form">
        <p class="mp-note">学生：{{ eligDrawer.studentName }}</p>
        <AppFormItem label="异常类型" required>
          <AppSelect v-model="eligDrawer.exceptionType" :options="excTypeOptions" :disabled="eligDrawer.saving" />
        </AppFormItem>
        <AppFormItem label="核验意见" required>
          <AppTextarea ref="eligNoteInput" v-model="eligDrawer.note" placeholder="不合格原因（将转入注册异常并通知辅导员）" :disabled="eligDrawer.saving" />
          <AppQuickPhrases scene-key="aa.reg.fail" @pick="onPickEligNote" />
        </AppFormItem>
        <AppInlineAlert v-if="eligDrawer.formError" type="danger" :description="eligDrawer.formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="eligDrawer.saving" @click="eligDrawer.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="eligDrawer.saving" @click="submitIneligible">提交</AppButton>
      </template>
    </AppDrawer>

    <!-- 申请暂缓注册 -->
    <AppDrawer :visible="deferDrawer.visible" title="申请暂缓注册" mode="modal" size="medium" @close="closeDeferralApply">
      <div class="aarw-form">
        <AppFormItem label="学生" required>
          <AppStudentPicker v-model="deferDrawer.studentId" :disabled="deferDrawer.saving || !!registrationWrite.pending" />
        </AppFormItem>
        <AppFormItem label="暂缓原因" required>
          <AppTextarea ref="deferReasonInput" v-model="deferDrawer.reason" placeholder="如材料未齐 / 特殊原因说明" :disabled="deferDrawer.saving || !!registrationWrite.pending" />
          <AppQuickPhrases scene-key="aa.reg.defer" @pick="onPickDeferReason" />
        </AppFormItem>
        <AppFormItem label="申请延后至">
          <AppDatePicker v-model="deferDrawer.requestedUntil" placeholder="留空=不限期，由教务处后续处理" :disabled="deferDrawer.saving || !!registrationWrite.pending" />
        </AppFormItem>
        <AppInlineAlert v-if="deferDrawer.formError" type="danger" :description="deferDrawer.formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="registrationWrite.busy || registrationWrite.checking" @click="closeDeferralApply">取消</AppButton>
        <AppButton variant="primary" :loading="deferDrawer.saving" :disabled="!!registrationWrite.pending" @click="submitDeferralApply">提交申请</AppButton>
      </template>
    </AppDrawer>

    <!-- 标记注册异常 -->
    <AppDrawer :visible="excDrawer.visible" title="标记注册异常" mode="modal" size="medium" @close="closeExceptionCreate">
      <div class="aarw-form">
        <AppFormItem label="学生" required>
          <AppStudentPicker v-model="excDrawer.studentId" :disabled="excDrawer.saving || !!excPendingCreate" />
        </AppFormItem>
        <AppFormItem label="异常类型" required>
          <AppSelect v-model="excDrawer.exceptionType" :options="excTypeOptions" :disabled="excDrawer.saving || !!excPendingCreate" />
        </AppFormItem>
        <AppFormItem label="说明" :required="excDrawer.exceptionType === 'OTHER'">
          <AppTextarea v-model="excDrawer.description" placeholder="异常类型为「其他」时必填" :disabled="excDrawer.saving || !!excPendingCreate" />
        </AppFormItem>
        <AppInlineAlert v-if="excDrawer.formError" type="danger" :description="excDrawer.formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="excCreating || excReceiptChecking" @click="closeExceptionCreate">取消</AppButton>
        <AppButton variant="primary" :loading="excCreating || excReceiptChecking" :disabled="!!excPendingCreate" @click="submitExceptionCreate">提交</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirm.visible"
      :title="confirm.title"
      :message="confirm.message"
      :type="confirm.type"
      :submitting="eligSubmitting"
      @confirm="onConfirm"
    />

    <!-- 导出用途（未注册名单 / 注册归档共用；用途写入审计与文件水印） -->
    <AppConfirmDialog
      v-model:visible="exportDialog.visible" :title="exportDialog.title" type="warning"
      message="导出文件带水印，用途将写入审计留痕。"
      confirm-text="确认导出" require-reason phrase-scene-key="common.exportPurpose"
      reason-label="导出用途（≥5 字）" :submitting="exportDialog.submitting" @confirm="onExportConfirm"
    />

    <!-- 暂缓注册驳回 / 注册异常处理说明：配置方案未给这两个场景词条，只做对话框化不挂快捷用语。
         reason-min-length=1 保持原口径「非空即可」，不擅自收紧为 ≥5 字（原实现只校验 !note.trim()） -->
    <AppConfirmDialog
      v-model:visible="deferRejectDialog.visible" title="驳回暂缓注册申请" type="danger"
      :message="deferRejectDialog.message"
      confirm-text="确认驳回" require-reason :reason-min-length="1" reason-label="驳回理由"
      :submitting="deferRejectDialog.submitting" :confirm-disabled="!!registrationWrite.pending" @confirm="onDeferRejectConfirm"
    >
      <AppInlineAlert v-if="registrationWrite.error && registrationActionVisible(registrationWrite.context)" type="danger" :description="registrationWrite.error" />
      <p v-if="registrationWrite.pending" class="mp-note">结果仍待核对，已暂停重复提交；关闭此框后可重新查询正式对象 ID。</p>
    </AppConfirmDialog>
    <AppConfirmDialog
      v-model:visible="resolveDialog.visible" title="处理注册异常" type="primary"
      :message="resolveDialog.message"
      confirm-text="确认处理" require-reason :reason-min-length="1" reason-label="处理说明"
      :submitting="resolveDialog.submitting" :confirm-disabled="!!registrationWrite.pending" @confirm="onResolveConfirm"
    >
      <AppInlineAlert v-if="registrationWrite.error && registrationActionVisible(registrationWrite.context)" type="danger" :description="registrationWrite.error" />
      <p v-if="registrationWrite.pending" class="mp-note">结果仍待核对，已暂停重复提交；关闭此框后可重新查询正式对象 ID。</p>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/**
 * 注册工作台（/admin/academic-affairs/registration/workbench）：
 * 注册资格核验 / 未注册学生 / 暂缓注册 / 注册异常 —— 四叶共用同一批次选择器，Tab 走 ?tab= 深链接。
 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import {
  AppTextInput, AppTextarea, AppSelect, AppFormItem, AppInlineAlert, AppConfirmDialog,
  AppSectionCard, AppStudentPicker, AppDatePicker, AppQuickPhrases, AppRegistrationBatchPicker
} from '@/components/common'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'
import { matchPermission } from '@/config/navPlan'
import { academicRouteState } from '@/modules/academicAffairs/academicFlowContext'
import { formatDateTime } from '@/utils/dateUtils'

const ELIG_STATUS_LABEL = { PENDING: '待核验', ELIGIBLE: '合格', INELIGIBLE: '不合格' }
const EXC_TYPE_LABEL = { IDENTITY_MISMATCH: '身份不符', UNPAID: '未缴费', MATERIAL_MISSING: '材料缺失', OTHER: '其他' }
const DEFER_STATUS_LABEL = { PENDING: '待审', APPROVED: '已通过', REJECTED: '已驳回' }
const REG_TYPE_LABEL = { ENROLL: '入学注册', ANNUAL: '学年注册', SEMESTER: '学期注册' }
const REG_TYPE_SHORT = { ENROLL: '入学', ANNUAL: '学年', SEMESTER: '学期' }

function emptyPage() {
  return { page: 1, pageSize: 20, total: 0 }
}

export default {
  name: 'AaRegistrationWorkbenchView',
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppTextInput, AppTextarea, AppSelect, AppFormItem, AppInlineAlert,
    AppConfirmDialog, AppSectionCard, AppStudentPicker, AppDatePicker, AppQuickPhrases, AppRegistrationBatchPicker
  },
  inject: {
    academicFlow: { default: null }
  },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      tab: 'eligibility',
      tabs: [
        { key: 'eligibility', label: '注册资格核验' },
        { key: 'unregistered', label: '未注册学生' },
        { key: 'deferral', label: '暂缓注册' },
        { key: 'exception', label: '注册异常' },
        { key: 'archive', label: '注册归档' }
      ],
      batches: [],
      batchId: '',
      scanning: false,
      scanConfirm: { visible: false, target: null, message: '' },
      scanOperation: { target: null, pending: null, receipt: null, error: '', deniedIdentity: '' },
      excTypeOptions: Object.entries(EXC_TYPE_LABEL).map(([value, label]) => ({ label, value })),
      eligStatusOptions: [
        { label: '全部核验结果', value: '' },
        { label: '待核验', value: 'PENDING' },
        { label: '合格', value: 'ELIGIBLE' },
        { label: '不合格', value: 'INELIGIBLE' }
      ],
      deferStatusOptions: [
        { label: '全部状态', value: '' },
        { label: '待审', value: 'PENDING' },
        { label: '已通过', value: 'APPROVED' },
        { label: '已驳回', value: 'REJECTED' }
      ],
      excStatusOptions: [
        { label: '全部状态', value: '' },
        { label: '待处理', value: 'OPEN' },
        { label: '已处理', value: 'RESOLVED' }
      ],
      eligColumns: [
        { key: 'student', title: '学生' },
        { key: 'className', title: '班级' },
        { key: 'eligibilityStatus', title: '核验结果' },
        { key: 'eligibilityNote', title: '核验意见' },
        { key: 'actions', title: '操作', width: '160px' }
      ],
      unregColumns: [
        { key: 'student', title: '学生' },
        { key: 'batchName', title: '批次' },
        { key: 'eligibility', title: '资格结论' },
        { key: 'deferral', title: '暂缓状态' },
        { key: 'owner', title: '责任老师' },
        { key: 'kind', title: '注册记录' },
        { key: 'actions', title: '办理入口' }
      ],
      deferColumns: [
        { key: 'student', title: '学生' },
        { key: 'reason', title: '原因' },
        { key: 'requestedUntil', title: '申请延后至' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作/意见' }
      ],
      excColumns: [
        { key: 'student', title: '学生' },
        { key: 'exceptionType', title: '异常类型' },
        { key: 'description', title: '说明' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作/结果' }
      ],
      archiveColumns: [
        { key: 'batchName', title: '批次名称' },
        { key: 'registerType', title: '类型' },
        { key: 'completion', title: '注册完成' },
        { key: 'archivedAt', title: '归档时间' },
        { key: 'actions', title: '操作', width: '140px' }
      ],
      elig: { keyword: '', status: '', rows: [], loading: false, error: '', pagination: emptyPage() },
      unreg: { rows: [], loading: false, error: '', keyword: '', pagination: emptyPage() },
      unregReason: { visible: false, row: null, loading: false, error: '', deferrals: [], exhausted: false, version: 0 },
      defer: { status: '', rows: [], loading: false, error: '', pagination: emptyPage() },
      exc: { status: '', rows: [], loading: false, error: '', pagination: emptyPage() },
      archive: { rows: [], loading: false, error: '', pagination: emptyPage() },
      queueVersions: { unreg: 0, defer: 0, exc: 0, archive: 0 },
      selectedEligId: '',
      selectedEligRow: null,
      eligRequestVersion: 0,
      eligScopeVersion: 0,
      eligFilterKey: null,
      eligDisposed: false,
      eligSubmitting: false,
      eligReceipt: null,
      eligUnknown: null,
      eligCommandError: '',
      eligDrawer: { visible: false, studentId: '', studentName: '', exceptionType: 'OTHER', note: '', saving: false, formError: '' },
      deferDrawer: { visible: false, studentId: '', reason: '', requestedUntil: '', saving: false, formError: '' },
      excDrawer: { visible: false, studentId: '', exceptionType: 'OTHER', description: '', saving: false, formError: '' },
      excCreating: false,
      excReceiptChecking: false,
      excPendingCreate: null,
      excCreateReceipt: null,
      excCreateError: '',
      excCreateDeniedIdentity: '',
      registrationWrite: { busy: false, checking: false, pending: null, receipt: null, error: '', context: null, deniedIdentity: '' },
      confirm: { visible: false, title: '', message: '', type: 'primary' },
      pendingAction: null,
      exportDialog: { visible: false, title: '', submitting: false, action: null },
      deferRejectDialog: { visible: false, deferralId: '', submitting: false },
      resolveDialog: { visible: false, exceptionId: '', submitting: false }
    }
  },
  computed: {
    unregisteredRows() {
      const keyword = this.unreg.keyword.trim().toLocaleLowerCase()
      return this.unreg.rows.filter(row => !keyword || `${row.realName || ''} ${row.studentNo || ''}`.toLocaleLowerCase().includes(keyword))
        .map(row => ({ ...row, queueKey: `${row.batchId}:${row.studentId}` }))
    },
    batchOptions() {
      return this.batches.map((b) => ({
        label: `${b.batchName}（${REG_TYPE_SHORT[b.registerType] || b.registerType}·${this.batchStatusCn(b.status)}）`, value: b.batchId
      }))
    },
    batchHint() {
      if (this.tab === 'eligibility') return '资格核验、暂缓注册、标记异常均需先选择具体批次'
      return '未注册/异常/暂缓列表默认显示全部批次；选择批次可收窄'
    },
    selectedBatchLabel() {
      const batch = this.batches.find((b) => String(b.batchId) === String(this.batchId))
      if (!batch) return '未选择批次'
      return `${batch.batchName || '未命名批次'}（${REG_TYPE_SHORT[batch.registerType] || batch.registerType || '未知类型'}）`
    },
    currentRoleName() {
      return this.ctx?.currentRole?.roleName || '当前岗位'
    },
    canViewRegistrationList() {
      return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.registration.view')
    },
    registrationSteps() {
      const batch = this.batches.find(b => String(b.batchId) === String(this.batchId))
      const row = this.selectedEligRow
      return [
        { title: '创建批次', detail: batch ? this.batchStatusCn(batch.status) : '批次待核实', complete: !!batch },
        { title: '圈定候选', detail: '候选已读取；名单版本待核实', complete: false },
        { title: '资格核验', detail: row ? this.eligStatusLabel(row.eligibilityStatus) : '请选择学生', complete: false },
        { title: '正式注册', detail: row?.registrationStatus === 'REGISTERED' ? '已完成注册' : '以正式注册结果为准', complete: row?.registrationStatus === 'REGISTERED' },
        { title: '关闭归档', detail: '在归档环节核对', complete: false }
      ]
    },
    registrationEvidence() {
      const row = this.selectedEligRow
      if (!row) return []
      return [
        { title: '来源对象与身份', type: 'default', label: '正式候选', source: true,
          fact: `${row.realName || '姓名待核实'} · ${row.studentNo || '学号待核实'} · ${row.className || '班级待核实'}`,
          note: `学生 ID：${row.studentId}；批次 ID：${this.batchId}` },
        { title: '当前名单版本', type: 'warning', label: '待核实',
          fact: `当前筛选共 ${this.elig.pagination.total} 人，第 ${this.elig.pagination.page} 页。`,
          note: '当前名单未提供版本信息，候选人数不能证明名单已冻结。' },
        { title: '材料与事实依据', type: 'warning', label: '材料待核实',
          fact: row.eligibilityNote ? `核验说明：${row.eligibilityNote}` : '尚无核验说明。',
          note: '本页尚无可核对的材料清单；核验说明不能代替材料原件。' },
        { title: '当前办理节点', type: 'default', label: '资格核验',
          fact: this.objectReasonText(row),
          note: `操作身份：${this.currentRoleName}；具体受理人尚待确认。` },
        { title: '状态与可用动作', type: this.eligStatusType(row.eligibilityStatus), label: this.eligStatusLabel(row.eligibilityStatus),
          fact: this.objectBlockText(row),
          note: `${this.objectOutcomeText(row)}；${this.canVerifyEligibility ? this.objectActionText(row) : '当前身份或批次不允许核验。'}` },
        { title: '证据新鲜度', type: 'warning', label: '待核实',
          fact: row.eligibilityCheckedAt ? `最近核验时间：${formatDateTime(row.eligibilityCheckedAt, '时间待核实')}（本地时间）` : '尚无核验记录。',
          note: '最近核验时间不代表材料、名单在本次提交前未发生变化。' }
      ]
    },
    eligibilityContextKey() {
      return JSON.stringify([String(this.batchId || ''), this.tab, this.eligScopeVersion, this.ctx])
    },
    canScanUnregistered() {
      const batch = this.batches.find(b => String(b.batchId) === String(this.batchId))
      return this.tab === 'unregistered' && !this.eligDisposed && !this.scanning && !this.scanOperation.pending &&
        this.scanOperation.deniedIdentity !== this.exceptionCreateIdentity() &&
        matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.registration.unregistered.scan') &&
        batch?.status === 'OPEN' && ['ENROLL', 'ANNUAL', 'SEMESTER'].includes(batch.registerType)
    },
    canVerifyEligibility() {
      return this.batches.some(b => String(b.batchId) === String(this.batchId) && b.status === 'OPEN') &&
        matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.registration.eligibility.verify')
    }
  },
  beforeUnmount() { this.eligDisposed = true; this.eligRequestVersion++ },
  watch: {
    ctx: { deep: true, handler() { this.invalidateEligibilityContext() } }
  },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    const route = academicRouteState(this.$route, { tabs: this.tabs.map(t => t.key), defaultTab: 'eligibility' })
    if (route.error) { this.elig.error = route.error; return }
    this.tab = route.tab
    this.batchId = route.batchId
    await this.loadBatches()
    this.selectedEligId = route.studentId
    this.elig.pagination.page = route.page
    this.elig.pagination.pageSize = route.pageSize
    if (typeof this.$route.query.status === 'string') this.elig.status = this.$route.query.status
    if (typeof this.$route.query.keyword === 'string') this.elig.keyword = this.$route.query.keyword
    this.loadCurrentTab()
  },
  methods: {
    eligibilityRouteQuery() {
      return { ...this.$route?.query, tab: this.tab, batchId: String(this.batchId || '') || undefined,
        studentId: String(this.selectedEligId || '') || undefined,
        keyword: this.elig.keyword || undefined, status: this.elig.status || undefined,
        page: String(this.elig.pagination.page), pageSize: String(this.elig.pagination.pageSize) }
    },
    async syncEligibilityRoute() {
      if (!this.$router || this.eligDisposed) return false
      const query = this.eligibilityRouteQuery()
      if (Object.keys(query).every(key => query[key] === this.$route?.query?.[key])) return true
      try { return !(await this.$router.replace({ query })) } catch { return false }
    },
    async goRegistrationList() {
      if (!this.batchId || this.eligSubmitting || !this.canViewRegistrationList) return
      const batchId = String(this.batchId)
      const target = JSON.stringify(this.eligibilityRouteQuery())
      if (!await this.syncEligibilityRoute() || target !== JSON.stringify(this.eligibilityRouteQuery()) ||
        this.eligDisposed || !this.canViewRegistrationList) return
      this.$router.push({ path: `/admin/academic-affairs/registration/${batchId}`,
        query: { returnToken: this.academicFlow?.captureReturn() } })
    },
    returnToOrigin() {
      this.academicFlow?.back(this.$route.query.returnToken, '/admin/academic-affairs/registration')
    },
    async onExportConfirm({ reason }) {
      const action = this.exportDialog.action
      this.exportDialog.submitting = true
      const ok = action ? await action(reason) : false
      this.exportDialog.submitting = false
      if (ok) this.exportDialog.visible = false
    },
    async onDeferRejectConfirm({ reason }) {
      const dialog = this.deferRejectDialog
      if (dialog.submitting) return
      dialog.submitting = true
      try {
        const ok = await this.reviewDeferral(dialog.deferralId, 'REJECT', reason, dialog.target)
        if (ok && dialog === this.deferRejectDialog && this.registrationActionCurrent(dialog.target)) dialog.visible = false
      } finally { dialog.submitting = false }
    },
    async onResolveConfirm({ reason }) {
      const dialog = this.resolveDialog
      if (dialog.submitting) return
      dialog.submitting = true
      try {
        const ok = await this.resolveException(dialog.exceptionId, reason, dialog.target)
        if (ok && dialog === this.resolveDialog && this.registrationActionCurrent(dialog.target)) dialog.visible = false
      } finally { dialog.submitting = false }
    },
    onPickEligNote(text) {
      const el = this.$refs.eligNoteInput && this.$refs.eligNoteInput.$refs.el
      const { value, selStart, selEnd } = insertAtCursor(el, this.eligDrawer.note, text)
      this.eligDrawer.note = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    onPickDeferReason(text) {
      if (this.deferDrawer.saving || this.registrationWrite.pending) return
      const el = this.$refs.deferReasonInput && this.$refs.deferReasonInput.$refs.el
      const { value, selStart, selEnd } = insertAtCursor(el, this.deferDrawer.reason, text)
      this.deferDrawer.reason = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    batchStatusCn(s) {
      return { DRAFT: '草稿', OPEN: '开放中', CLOSED: '已关闭', ARCHIVED: '已归档' }[s] || (s ? '状态待确认' : '—')
    },
    regTypeLabel(t) {
      return REG_TYPE_LABEL[t] || (t ? '类型待确认' : '—')
    },
    switchTab(key) {
      if (key === this.tab) return
      const selectedId = this.selectedEligId
      this.invalidateEligibilityContext()
      this.selectedEligId = selectedId
      this.tab = key
      this.syncEligibilityRoute()
      this.loadCurrentTab()
    },
    loadCurrentTab() {
      if (this.tab === 'eligibility') this.loadEligibility()
      else if (this.tab === 'unregistered') this.loadUnregistered()
      else if (this.tab === 'deferral') this.loadDeferrals()
      else if (this.tab === 'exception') this.loadExceptions()
      else this.loadArchive()
    },
    onBatchChange() {
      this.invalidateEligibilityContext()
      this.elig.pagination.page = 1
      for (const key of Object.keys(this.queueVersions)) this[key].pagination.page = 1
      this.selectedEligId = ''
      this.selectedEligRow = null
      this.syncEligibilityRoute()
      this.loadCurrentTab()
    },
    async loadBatches() {
      const res = await academicAffairsApi.getRegistrationBatches({ page: 1, pageSize: 100 })
      const list = res.code === 0 ? (res.data.list || []) : []
      // 已归档批次只读，不进本工作台（资格核验/未注册/暂缓/异常）批次选择器；查阅走「注册归档」Tab。
      this.batches = list.filter((b) => b.status !== 'ARCHIVED')
      if (!this.batchId) {
        const open = this.batches.find((b) => b.status === 'OPEN')
        if (open) this.batchId = open.batchId
      }
    },
    /* ── 资格核验 ── */
    invalidateEligibilityContext() {
      this.closeUnregisteredReason()
      this.eligScopeVersion++
      this.eligRequestVersion++
      this.elig.rows = []; this.elig.pagination.total = 0; this.elig.loading = false
      this.selectedEligId = ''; this.selectedEligRow = null; this.eligReceipt = null; this.eligCommandError = ''
      this.pendingAction = null; this.confirm.visible = false
      this.eligDrawer.visible = false
      for (const key of Object.keys(this.queueVersions)) {
        this.queueVersions[key]++
        this[key].rows = []; this[key].pagination.total = 0; this[key].loading = false; this[key].error = ''
      }
      this.deferDrawer.visible = false; this.excDrawer.visible = false
      this.deferRejectDialog.visible = false; this.resolveDialog.visible = false
      this.exportDialog.visible = false; this.exportDialog.action = null
    },
    captureEligibilityTarget(row) {
      return { batchId: String(this.batchId), studentId: String(row.studentId),
        contextKey: this.eligibilityContextKey, checkedAt: row.eligibilityCheckedAt || null,
        status: row.eligibilityStatus, registrationStatus: row.registrationStatus }
    },
    eligibilityTargetCurrent(target) {
      const row = target && this.findEligibilityRow(target.studentId)
      return !!row && !this.eligDisposed && !this.elig.loading && this.canVerifyEligibility &&
        target.contextKey === this.eligibilityContextKey && String(this.selectedEligId) === target.studentId &&
        this.knownEligibilityState(row) && row.registrationStatus !== 'REGISTERED' && row.registrationStatus === target.registrationStatus &&
        row.eligibilityStatus === target.status && (row.eligibilityCheckedAt || null) === target.checkedAt
    },
    isEligSelected(row) { return !!row && String(row.studentId) === String(this.selectedEligId) },
    selectEligibilityRow(row) {
      if (!row || !row.studentId) return
      if (String(this.selectedEligId) !== String(row.studentId)) {
        this.eligReceipt = null; this.eligCommandError = ''
        if (this.pendingAction?.kind === 'eligible') { this.pendingAction = null; this.confirm.visible = false }
        this.eligDrawer.visible = false
      }
      this.selectedEligId = row.studentId
      this.selectedEligRow = row
      this.syncEligibilityRoute()
    },
    findEligibilityRow(studentId) {
      return this.elig.rows.find((row) => String(row.studentId) === String(studentId))
    },
    reconcileSelectedEligibility() {
      const rows = this.elig.rows || []
      const keep = this.selectedEligId ? this.findEligibilityRow(this.selectedEligId) : null
      if (this.selectedEligId && !keep) {
        this.selectedEligRow = null
        this.elig.error = '原学生已不在当前候选页，请调整筛选或返回注册名单核对，未切换到其他学生'
        return
      }
      if (!rows.length) {
        this.selectedEligId = ''
        this.selectedEligRow = null
        return
      }
      const next = keep || rows.find((row) => row.registrationStatus !== 'REGISTERED') || rows[0]
      this.selectedEligId = next?.studentId || ''
      this.selectedEligRow = next || null
    },
    eligStatusLabel(s) { return ELIG_STATUS_LABEL[s] || (s ? '状态待确认' : '—') },
    knownEligibilityState(row) { return ['PENDING', 'ELIGIBLE', 'INELIGIBLE'].includes(row?.eligibilityStatus) },
    eligStatusType(s) { return s === 'ELIGIBLE' ? 'success' : s === 'INELIGIBLE' ? 'danger' : 'default' },
    onEligPage(page) {
      this.invalidateEligibilityContext()
      this.elig.pagination.page = page
      return this.loadEligibility()
    },
    async loadEligibility() {
      const filterKey = JSON.stringify([String(this.batchId || ''), this.elig.keyword, this.elig.status, this.elig.pagination.pageSize])
      if (this.eligFilterKey !== null && this.eligFilterKey !== filterKey) {
        this.invalidateEligibilityContext()
        this.elig.pagination.page = 1
      }
      this.eligFilterKey = filterKey
      if (this.elig.keyword.length > 200) { this.elig.error = '检索词不能超过 200 个字符，请缩短后重试'; return }
      this.syncEligibilityRoute()
      const version = ++this.eligRequestVersion
      const contextKey = this.eligibilityContextKey
      const queryKey = JSON.stringify([this.elig.keyword, this.elig.status, this.elig.pagination.page, this.elig.pagination.pageSize])
      const current = () => !this.eligDisposed && version === this.eligRequestVersion && contextKey === this.eligibilityContextKey &&
        queryKey === JSON.stringify([this.elig.keyword, this.elig.status, this.elig.pagination.page, this.elig.pagination.pageSize])
      if (!this.batchId) { this.elig.rows = []; this.elig.pagination.total = 0; this.elig.loading = false; this.reconcileSelectedEligibility(); return }
      this.elig.loading = true
      this.elig.error = ''
      try {
        const res = await academicAffairsApi.getRegistrationEligibility(this.batchId, {
          status: this.elig.status || undefined, keyword: this.elig.keyword || undefined,
          page: this.elig.pagination.page, pageSize: this.elig.pagination.pageSize
        })
        if (!current()) return
        if (res.code === 0) {
          this.elig.rows = res.data.list
          this.elig.pagination.total = res.data.total
          this.reconcileSelectedEligibility()
          await this.syncEligibilityRoute()
        } else {
          this.elig.rows = []
          this.selectedEligRow = null
          this.elig.pagination.total = 0
          this.elig.error = res.message || '资格名单读取失败，请重试'
        }
      } catch (error) {
        if (!current()) return
        this.elig.rows = []; this.elig.pagination.total = 0; this.selectedEligRow = null
        this.elig.error = error?.message || '资格名单读取失败，请重试'
      } finally {
        if (current()) { this.elig.loading = false; this.academicFlow?.restorePosition?.() }
      }
    },
    objectStatusText(row) {
      if (!row) return '—'
      if (row.registrationStatus === 'REGISTERED') return '已完成注册'
      if (!this.knownEligibilityState(row)) return '资格状态待确认'
      if (row.eligibilityStatus === 'ELIGIBLE') return '核验合格（待进入注册名单）'
      if (row.eligibilityStatus === 'INELIGIBLE') return '核验不合格（已回流异常）'
      return '待核验'
    },
    objectReasonText(row) {
      if (!row) return '—'
      if (row.registrationStatus === 'REGISTERED') return '学生已完成注册，当前岗位仅收口核验结果'
      if (!this.knownEligibilityState(row)) return '资格状态尚未确认，请重新核对正式记录'
      if (row.eligibilityStatus === 'INELIGIBLE') return '核验不通过，需查看核验说明与注册异常，按实际原因处理'
      if (row.eligibilityStatus === 'ELIGIBLE') return '核验已完成，进入名单办理后续'
      return `当前批次[${this.selectedBatchLabel}]待教务处岗位完成核验`
    },
    objectBlockText(row) {
      if (!row) return '—'
      if (row.registrationStatus === 'REGISTERED') return '已读到正式注册结果；归档条件仍需在归档环节核对'
      if (!this.knownEligibilityState(row)) return '资格状态待确认，已暂停核验提交'
      if (row.eligibilityStatus === 'INELIGIBLE') return '核验不合格；是否已修复需查注册异常'
      if (row.eligibilityStatus === 'ELIGIBLE') return '资格已通过；正式注册仍需核对暂缓、异常及批次条件'
      return '尚未完成资格核验'
    },
    objectActionText(row) {
      if (!row) return '—'
      if (row.registrationStatus === 'REGISTERED') return '仅支持查看'
      if (!this.knownEligibilityState(row)) return '重新查询资格状态'
      if (row.eligibilityStatus === 'INELIGIBLE') return '提交异常说明并转异常列表'
      if (row.eligibilityStatus === 'ELIGIBLE') return '建议返回注册名单继续下一步'
      return '核验通过 / 标记不合格'
    },
    objectOutcomeText(row) {
      if (!row) return '—'
      if (row.registrationStatus === 'REGISTERED') return '注册结果：已完成'
      if (row.eligibilityStatus === 'INELIGIBLE') return '结果：待修正'
      if (row.eligibilityStatus === 'ELIGIBLE') return '结果：核验通过'
      return '结果：尚未确认'
    },
    nextRoleText(row) {
      if (!row) return '—'
      if (row.registrationStatus === 'REGISTERED') return '已完成正式注册'
      if (!this.knownEligibilityState(row)) return '待核实办理岗位'
      if (row.eligibilityStatus === 'INELIGIBLE') return '注册异常处理岗；具体受理人以异常记录为准'
      if (row.eligibilityStatus === 'ELIGIBLE') return '正式注册办理岗'
      return '注册资格核验岗'
    },
    toastMissingTarget() { toast.error('该对象已不在当前列表，请重新选择') },
    askEligible(row) {
      if (!this.canVerifyEligibility || this.eligSubmitting || this.eligUnknown || this.elig.loading) return
      const target = this.findEligibilityRow(row?.studentId)
      if (!target) return this.toastMissingTarget()
      if (!this.knownEligibilityState(target)) return toast.error('资格状态待确认，请先重新查询')
      if (target.registrationStatus === 'REGISTERED') return toast.error('该对象已完成注册')
      if (target.eligibilityStatus === 'ELIGIBLE') return toast.error('该对象已核验通过')
      this.confirm = { visible: true, title: '核验通过', message: `确认「${target.realName}」注册资格核验通过？`, type: 'primary' }
      this.pendingAction = { kind: 'eligible', target: this.captureEligibilityTarget(target) }
    },
    openIneligible(row) {
      if (!this.canVerifyEligibility || this.eligSubmitting || this.eligUnknown || this.elig.loading) return
      const target = this.findEligibilityRow(row?.studentId)
      if (!target || target.registrationStatus === 'REGISTERED') return this.toastMissingTarget()
      if (!this.knownEligibilityState(target)) return toast.error('资格状态待确认，请先重新查询')
      this.eligDrawer = {
        visible: true,
        studentId: target.studentId,
        target: this.captureEligibilityTarget(target),
        studentName: `${target.realName || '未命名学生'} · ${target.studentNo || '—'}`,
        exceptionType: 'OTHER',
        note: '',
        saving: false,
        formError: ''
      }
    },
    async submitIneligible() {
      if (this.eligSubmitting || this.eligUnknown) return
      const drawer = this.eligDrawer
      const target = drawer.target
      if (!this.eligDrawer.note.trim()) { this.eligDrawer.formError = '核验意见必填'; return }
      if (!this.eligibilityTargetCurrent(target)) { drawer.formError = '批次、身份或学生已变化，请重新核对'; return }
      this.eligDrawer.saving = true
      this.eligDrawer.formError = ''
      const ok = await this.verifyEligibilityTarget(target, {
        result: 'INELIGIBLE', note: drawer.note.trim(), exceptionType: drawer.exceptionType
      })
      drawer.saving = false
      if (ok) drawer.visible = false
      else drawer.formError = this.eligCommandError || '结果待确认，请查询正式记录'
    },
    async verifyEligibilityTarget(target, body) {
      if (this.eligSubmitting || this.eligUnknown || !this.eligibilityTargetCurrent(target)) return false
      this.eligSubmitting = true; this.eligCommandError = ''; this.eligReceipt = null
      const sameContext = () => !this.eligDisposed && target.contextKey === this.eligibilityContextKey && String(this.selectedEligId) === target.studentId
      try {
        const res = await academicAffairsApi.verifyRegistrationEligibility(target.batchId, target.studentId, body)
        const receipt = res.data
        if (res.code === 0 && receipt?.registrationId && String(receipt.studentId) === target.studentId &&
          receipt.eligibilityStatus === body.result && (body.result !== 'INELIGIBLE' || receipt.exceptionId)) {
          if (sameContext()) { this.eligReceipt = { ...receipt }; await this.loadEligibility() }
          return true
        }
        if (res.code === 0 || Number(res.code) >= 500000 || ['REQUEST_TIMEOUT', 'NETWORK_ERROR'].includes(res.bizCode)) {
          this.eligUnknown = target
          if (sameContext()) await this.loadEligibility()
        } else if (sameContext()) {
          this.eligCommandError = res.message || '核验未完成，请重新核对'
          if (String(res.code).startsWith('403')) {
            this.elig.rows = []; this.reconcileSelectedEligibility(); this.elig.pagination.total = 0
            this.elig.error = this.eligCommandError
          }
        }
        return false
      } catch {
        this.eligUnknown = target
        if (sameContext()) await this.loadEligibility()
        return false
      } finally { this.eligSubmitting = false }
    },

    /* ── 未注册学生 ── */
    registrationTime(value) { return formatDateTime(value, '未提供') },
    closeUnregisteredReason() {
      this.unregReason = { visible: false, row: null, loading: false, error: '', deferrals: [], exhausted: false, version: (this.unregReason?.version || 0) + 1 }
    },
    openUnregisteredReason(row) {
      if (!row || !this.unreg.rows.some(item => String(item.studentId) === String(row.studentId) && String(item.batchId) === String(row.batchId))) return
      if (!/^\d+$/.test(String(row.studentId)) || !/^\d+$/.test(String(row.batchId))) return
      this.closeUnregisteredReason()
      this.unregReason.visible = true
      this.unregReason.row = { ...row }
      return this.readUnregisteredReason()
    },
    async readUnregisteredReason() {
      const drawer = this.unregReason, row = drawer.row, context = this.eligibilityContextKey
      if (!drawer.visible || !row) return
      const version = ++drawer.version
      const current = () => !this.eligDisposed && this.unregReason === drawer && drawer.visible && drawer.version === version && context === this.eligibilityContextKey
      drawer.loading = true; drawer.error = ''; drawer.deferrals = []; drawer.exhausted = false
      try {
        const found = []
        for (let page = 1; page <= 5; page++) {
          const response = await academicAffairsApi.getRegistrationDeferrals({ batchId: String(row.batchId), page, pageSize: 100 })
          if (!current()) return
          if (response?.code !== 0) throw response
          const rows = response.data?.list
          if (!Array.isArray(rows)) throw new Error('暂缓申请回执不完整，请重新核对')
          found.push(...rows.filter(item => String(item.batchId) === String(row.batchId) && String(item.studentId) === String(row.studentId)))
          if (rows.length < 100 || (Number.isFinite(response.data.total) && page * 100 >= response.data.total)) { drawer.exhausted = true; break }
        }
        if (current()) drawer.deferrals = found
      } catch (error) {
        if (!current()) return
        drawer.deferrals = []
        const forbidden = [error?.bizCode, error?.code].some(code => ['NO_PERMISSION', 'NO_DATA_SCOPE'].includes(code) || [403, 403001, 403002].includes(Number(code)))
        if (forbidden) { drawer.row = null; drawer.visible = false; this.unreg.rows = []; this.unreg.pagination.total = 0; this.unreg.error = '无权核对原学生暂缓记录，请刷新当前范围。' }
        else drawer.error = error?.message || '暂缓申请读取失败，不能据此判断没有申请。'
      } finally { if (current()) drawer.loading = false }
    },
    async loadRegistrationQueue(key, read) {
      if (key === 'unreg') this.closeUnregisteredReason()
      const queue = this[key]
      const version = ++this.queueVersions[key]
      const contextKey = this.eligibilityContextKey
      const queryKey = () => JSON.stringify([queue.status, queue.pagination.page, queue.pagination.pageSize])
      const requestedQuery = queryKey()
      const current = () => !this.eligDisposed && version === this.queueVersions[key] &&
        contextKey === this.eligibilityContextKey && requestedQuery === queryKey()
      queue.rows = []; queue.pagination.total = 0; queue.loading = true; queue.error = ''
      try {
        const res = await read(current)
        if (!current()) return
        if (res?.code !== 0) throw new Error(res?.message || '队列读取失败，请重新查询')
        queue.rows = res.data.list || []
        queue.pagination.total = res.data.total ?? 0
      } catch (error) {
        if (current()) { queue.rows = []; queue.pagination.total = 0; queue.error = error?.message || '队列读取失败，请重新查询' }
      } finally {
        if (current()) queue.loading = false
      }
    },
    onUnregPage(page) { this.unreg.pagination.page = page; this.loadUnregistered() },
    async loadUnregistered() {
      return this.loadRegistrationQueue('unreg', () => academicAffairsApi.getUnregisteredStudents({
        batchId: this.batchId || undefined, page: this.unreg.pagination.page, pageSize: this.unreg.pagination.pageSize
      }))
    },
    scanTargetCurrent(target) {
      return !!target && !this.eligDisposed && target.identity === this.exceptionCreateIdentity() &&
        target.epoch === this.eligScopeVersion && target.batchId === String(this.batchId) && this.tab === 'unregistered'
    },
    askScan() {
      if (!this.canScanUnregistered) return
      const batch = this.batches.find(b => String(b.batchId) === String(this.batchId))
      const target = { batchId: String(batch.batchId), registerType: batch.registerType,
        identity: this.exceptionCreateIdentity(), epoch: this.eligScopeVersion }
      this.scanConfirm = { visible: true, target,
        message: `确认扫描批次 ${target.batchId}「${batch.batchName || '未命名批次'}」的全校逾期候选（包含本页外学生）？有效暂缓批准会跳过。${target.registerType === 'ENROLL' ? '符合条件的入学注册学生将经正式入口标记学籍主档未注册。' : '本次只标记本批次注册记录，不倒退学籍主档状态。'}` }
    },
    async doScan() {
      const target = this.scanConfirm.target
      if (!this.canScanUnregistered || !this.scanTargetCurrent(target)) return
      this.scanning = true
      this.scanConfirm.visible = false
      this.scanConfirm.target = null
      this.scanOperation.target = target; this.scanOperation.pending = target
      this.scanOperation.receipt = null; this.scanOperation.error = ''
      try {
        const res = await academicAffairsApi.scanUnregistered(target.batchId)
        const data = res?.data
        const valid = res?.code === 0 && String(data?.batchId) === target.batchId &&
          ['marked', 'skipped', 'notified'].every(key => Number.isSafeInteger(data?.[key]) && data[key] >= 0) && data.notified <= data.marked
        if (valid) {
          this.scanOperation.pending = null
          if (this.scanTargetCurrent(target)) { this.scanOperation.receipt = { ...data }; await this.loadUnregistered() }
          return
        }
        const code = Number(res?.code)
        const denied = String(code).startsWith('403') || ['NO_PERMISSION', 'NO_DATA_SCOPE'].includes(res?.bizCode)
        const conflict = String(code).startsWith('409') || res?.bizCode === 'DATA_CONFLICT'
        const rejected = denied || conflict || ['DATA_NOT_FOUND', 'VALIDATION_ERROR'].includes(res?.bizCode) ||
          (code >= 400 && code < 500) || (code >= 400000 && code < 500000)
        if (rejected) {
          this.scanOperation.pending = null
          if (denied) this.scanOperation.deniedIdentity = target.identity
          if (this.scanTargetCurrent(target)) {
            this.scanOperation.error = res?.message || (conflict ? '批次状态已变化，请重新核对' : '扫描未执行，请核对权限和批次')
            if (denied) {
              this.queueVersions.unreg++; this.unreg.rows = []; this.unreg.pagination.total = 0
              this.unreg.loading = false; this.unreg.error = this.scanOperation.error
            } else if (conflict) await this.loadUnregistered()
          }
        } else if (this.scanTargetCurrent(target)) this.scanOperation.error = '未取得可核对的正式扫描回执，结果未知；请先核查原批次，禁止重复扫描。'
      } catch {
        if (this.scanTargetCurrent(target)) this.scanOperation.error = '未取得可核对的正式扫描回执，结果未知；请先核查原批次，禁止重复扫描。'
      } finally { this.scanning = false }
    },
    openExport() {
      this.exportDialog = {
        visible: true, title: '导出未注册学生名单', submitting: false,
        action: async (purpose) => {
          const res = await academicAffairsApi.exportUnregistered({ batchId: this.batchId || undefined, purpose })
          if (res.code !== 0) { toast.error(res.message || '导出失败'); return false }
          this.downloadBlob(res.data, `未注册学生名单-${Date.now()}.xlsx`)
          toast.success('导出成功')
          return true
        }
      }
    },
    /** 统一 blob 下载（未注册名单 / 注册归档共用，避免每处重复一份 createObjectURL 样板） */
    downloadBlob(blob, filename) {
      const href = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = href
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(href)
    },

    /* 暂缓申请/审核与异常处理共享本页的单次写锁，不改变其他动作。 */
    canRunRegistrationAction(permission) {
      return !this.eligDisposed && !this.registrationWrite.busy && !this.registrationWrite.checking && !this.registrationWrite.pending &&
        this.registrationWrite.deniedIdentity !== this.exceptionCreateIdentity() &&
        matchPermission(this.ctx.permissionPatterns || [], `academicAffairs.registration.${permission}`)
    },
    registrationActionCurrent(target) {
      return !!target && !this.eligDisposed && target.identityKey === this.exceptionCreateIdentity() && target.contextKey === this.eligibilityContextKey
    },
    registrationActionVisible(target) {
      return !!target && target.identityKey === this.exceptionCreateIdentity() && (!this.batchId || target.batchId === String(this.batchId))
    },
    registrationActionStatus(domain, status) {
      return domain === 'deferral' ? this.deferStatusLabel(status) : ({ OPEN: '待处理', RESOLVED: '已处理' }[status] || '状态待核对')
    },
    registrationEvidenceKey(domain, row) {
      return JSON.stringify(domain === 'deferral'
        ? [row.deferralId, row.batchId, row.studentId, row.status, row.reason, row.requestedUntil, row.reviewNote, row.reviewedAt]
        : [row.exceptionId, row.batchId, row.studentId, row.status, row.exceptionType, row.description, row.resolutionNote, row.resolvedAt])
    },
    captureRegistrationAction(domain, row) {
      const key = domain === 'deferral' ? 'defer' : 'exc', id = domain === 'deferral' ? row?.deferralId : row?.exceptionId
      if (!id || !row.batchId || !row.studentId) return null
      return { domain, objectId: String(id), batchId: String(row.batchId), studentId: String(row.studentId),
        identityKey: this.exceptionCreateIdentity(), contextKey: this.eligibilityContextKey,
        queueVersion: this.queueVersions[key], evidence: this.registrationEvidenceKey(domain, row) }
    },
    registrationTargetCurrent(target) {
      if (!this.registrationActionCurrent(target)) return false
      const key = target.domain === 'deferral' ? 'defer' : 'exc', idKey = target.domain === 'deferral' ? 'deferralId' : 'exceptionId'
      const row = this[key].rows.find(item => String(item[idKey]) === target.objectId)
      return !this[key].loading && this.queueVersions[key] === target.queueVersion && !!row &&
        row.status === (target.domain === 'deferral' ? 'PENDING' : 'OPEN') && this.registrationEvidenceKey(target.domain, row) === target.evidence
    },
    canReadRegistrationAction(target) {
      return !!target && !this.eligDisposed && target.identityKey === this.exceptionCreateIdentity() &&
        matchPermission(this.ctx.permissionPatterns || [], `academicAffairs.registration.${target.domain}.view`)
    },
    denyRegistrationAction(target) {
      if (this.registrationWrite.pending) this.registrationWrite.pending.denied = true
      if (!this.registrationActionCurrent(target)) return
      const key = target.domain === 'deferral' ? 'defer' : 'exc'
      this.queueVersions[key]++; this[key].rows = []; this[key].pagination.total = 0; this[key].loading = false
      this.registrationWrite.receipt = null; this.registrationWrite.deniedIdentity = target.identityKey
      this.registrationWrite.error = '当前身份无权办理或核对该对象，已清除原队列和输入内容。'
      if (key === 'defer') {
        this.deferDrawer = { visible: false, studentId: '', reason: '', requestedUntil: '', saving: false, formError: '' }
        this.deferRejectDialog = { visible: false, deferralId: '', submitting: false }
        if (this.pendingAction?.kind === 'deferralApprove') { this.pendingAction = null; this.confirm.visible = false }
      } else this.resolveDialog = { visible: false, exceptionId: '', submitting: false }
    },
    async runRegistrationAction(command, write) {
      if (!this.canRunRegistrationAction(command.permission) || !this.registrationActionCurrent(command)) return false
      const state = this.registrationWrite
      state.busy = true; state.error = ''; state.receipt = null
      state.pending = { ...command, postConfirmed: false, message: '本次请求回执尚待核对。' }
      const target = state.pending
      state.context = target
      try {
        const res = await write()
        if (this.eligDisposed) return false
        if (String(res.code).startsWith('403')) { this.denyRegistrationAction(target); state.pending = null; return false }
        const code = Number(res.code)
        const uncertain = code >= 500000 || (code >= 500 && code < 600) || Number(res.status) >= 500 || ['REQUEST_TIMEOUT', 'NETWORK_ERROR'].includes(res.bizCode)
        if (code > 0 && !uncertain) {
          state.pending = null
          if (this.registrationActionCurrent(target)) {
            state.error = res.message || '业务命令未完成，请重新核对。'
            if (String(res.code).startsWith('409') && target.kind !== 'apply') {
              if (target.domain === 'deferral') await this.loadDeferrals(); else await this.loadExceptions()
            }
          }
          return false
        }
        const idKey = target.domain === 'deferral' ? 'deferralId' : 'exceptionId', receipt = res.data
        const valid = res.code === 0 && typeof receipt?.[idKey] === 'string' && receipt[idKey] &&
          (!target.objectId || receipt[idKey] === target.objectId) && String(receipt.batchId) === target.batchId &&
          String(receipt.studentId) === target.studentId && receipt.status === target.expectedStatus
        if (valid) { target.objectId = receipt[idKey]; target.postConfirmed = true; target.message = '已收到办理回执，正在核对正式记录。' }
        return target.objectId ? await this.verifyRegistrationAction() : false
      } catch {
        if (!this.eligDisposed && state.pending === target) target.message = '请求中断，结果仍待核对，禁止直接重发。'
        if (target.objectId && !this.eligDisposed) return await this.verifyRegistrationAction()
        return false
      } finally { state.busy = false }
    },
    async verifyRegistrationAction() {
      const state = this.registrationWrite, target = state.pending
      if (!target?.objectId || state.checking || !this.canReadRegistrationAction(target)) return false
      const current = () => !this.eligDisposed && state.pending === target && target.identityKey === this.exceptionCreateIdentity()
      state.checking = true
      try {
        const pageSize = 100
        for (let page = 1; page <= 5; page++) {
          const query = { batchId: target.batchId, page, pageSize }
          const res = target.domain === 'deferral' ? await academicAffairsApi.getRegistrationDeferrals(query) : await academicAffairsApi.getRegistrationExceptions(query)
          if (!current()) return false
          if (String(res.code).startsWith('403')) { this.denyRegistrationAction(target); return false }
          if (res.code !== 0 || !Array.isArray(res.data?.list)) { target.message = res.message || '正式记录读取失败，结果仍待核对。'; return false }
          const idKey = target.domain === 'deferral' ? 'deferralId' : 'exceptionId'
          const row = res.data.list.find(item => String(item[idKey]) === target.objectId)
          if (row) {
            const statuses = target.domain === 'deferral' ? ['PENDING', 'APPROVED', 'REJECTED'] : ['OPEN', 'RESOLVED']
            if (String(row.batchId) !== target.batchId || String(row.studentId) !== target.studentId || !statuses.includes(row.status)) {
              target.message = '正式记录对象或状态不一致，结果仍待核对。'; return false
            }
            const confirmed = target.postConfirmed && (target.kind === 'apply' || row.status === target.expectedStatus)
            state.receipt = { ...target, status: row.status, commandConfirmed: confirmed }
            if (!confirmed) { target.message = '已读到当前状态，但不能证明本次请求完成；继续暂停重复提交。'; return false }
            state.pending = null
            if (state.deniedIdentity === target.identityKey) state.deniedIdentity = ''
            return true
          }
          if (res.data.list.length < pageSize || page * pageSize >= Number(res.data.total)) break
        }
        target.message = '本次有限范围内未找到正式 ID，不能判断未提交；可重新查询。'
        return false
      } catch {
        if (current()) target.message = '正式记录查询中断，结果仍待核对。'
        return false
      } finally { state.checking = false }
    },

    /* ── 暂缓注册 ── */
    deferStatusLabel(s) { return DEFER_STATUS_LABEL[s] || (s ? '状态待确认' : '—') },
    deferStatusType(s) { return s === 'APPROVED' ? 'success' : s === 'REJECTED' ? 'danger' : 'warning' },
    onDeferPage(page) { this.defer.pagination.page = page; this.loadDeferrals() },
    async loadDeferrals() {
      return this.loadRegistrationQueue('defer', () => academicAffairsApi.getRegistrationDeferrals({
        batchId: this.batchId || undefined, status: this.defer.status || undefined,
        page: this.defer.pagination.page, pageSize: this.defer.pagination.pageSize
      }))
    },
    openDeferralApply() {
      if (!this.batchId || !this.canRunRegistrationAction('deferral.apply')) return
      this.registrationWrite.error = ''
      this.deferDrawer = { visible: true, studentId: '', reason: '', requestedUntil: '', saving: false, formError: '',
        batchId: String(this.batchId), identityKey: this.exceptionCreateIdentity(), contextKey: this.eligibilityContextKey }
    },
    closeDeferralApply() {
      if (!this.registrationWrite.busy && !this.registrationWrite.checking) this.deferDrawer.visible = false
    },
    async submitDeferralApply() {
      if (!this.canRunRegistrationAction('deferral.apply')) return
      const drawer = this.deferDrawer
      if (!drawer.visible || !this.registrationActionCurrent(drawer)) { drawer.formError = '身份或批次已变化，请重新填写'; return }
      if (!drawer.studentId) { drawer.formError = '请选择学生'; return }
      if (drawer.reason.trim().length < 2) { drawer.formError = '暂缓原因至少填写 2 个字符'; return }
      const command = { kind: 'apply', domain: 'deferral', permission: 'deferral.apply', label: '暂缓注册申请',
        batchId: drawer.batchId, studentId: String(drawer.studentId), objectId: '', expectedStatus: 'PENDING',
        identityKey: drawer.identityKey, contextKey: drawer.contextKey,
        reason: drawer.reason.trim(), requestedUntil: drawer.requestedUntil || undefined }
      drawer.saving = true; drawer.formError = ''
      try {
        const ok = await this.runRegistrationAction(command, () => academicAffairsApi.applyRegistrationDeferral(command.batchId, {
          studentId: command.studentId, reason: command.reason, requestedUntil: command.requestedUntil
        }))
        if (drawer === this.deferDrawer && this.registrationActionCurrent(command)) {
          if (ok) { drawer.visible = false; this.loadDeferrals() }
          else drawer.formError = this.registrationWrite.error || '结果待核对，请关闭窗口后查询正式记录，勿重复提交。'
        }
      } finally { drawer.saving = false }
    },
    askDeferralReview(row, action) {
      if (!['APPROVE', 'REJECT'].includes(action) || !this.canRunRegistrationAction('deferral.approve')) return
      const target = this.captureRegistrationAction('deferral', row)
      if (!this.registrationTargetCurrent(target)) return
      this.registrationWrite.error = ''
      const message = `学生 ${target.studentId}，批次 ${target.batchId}，暂缓申请 ${target.objectId}；当前待审核。`
      if (action === 'REJECT') {
        this.deferRejectDialog = { visible: true, deferralId: target.objectId, target, message, submitting: false }
        return
      }
      this.confirm = { visible: true, title: '通过暂缓注册申请', message: `${message} 确认通过？`, type: 'primary' }
      this.pendingAction = { kind: 'deferralApprove', target }
    },
    /** @returns {boolean} 是否成功（调用方据此决定关不关弹窗，失败时保留用户已填内容） */
    async reviewDeferral(deferralId, action, note, target) {
      if (!this.canRunRegistrationAction('deferral.approve') || !this.registrationTargetCurrent(target) ||
        String(deferralId) !== target.objectId || !['APPROVE', 'REJECT'].includes(action)) return false
      if (action === 'REJECT' && !String(note || '').trim()) return false
      const command = { ...target, kind: 'review', permission: 'deferral.approve', label: action === 'APPROVE' ? '通过暂缓申请' : '驳回暂缓申请',
        action, note: String(note || '').trim(), expectedStatus: action === 'APPROVE' ? 'APPROVED' : 'REJECTED' }
      const ok = await this.runRegistrationAction(command, () => academicAffairsApi.reviewRegistrationDeferral(command.objectId, { action, note: command.note }))
      if (ok && this.registrationActionCurrent(command)) this.loadDeferrals()
      return ok
    },

    /* ── 注册异常 ── */
    excTypeLabel(t) { return EXC_TYPE_LABEL[t] || (t ? '类型待确认' : '—') },
    onExcPage(page) { this.exc.pagination.page = page; this.loadExceptions() },
    async loadExceptions() {
      return this.loadRegistrationQueue('exc', () => academicAffairsApi.getRegistrationExceptions({
        batchId: this.batchId || undefined, status: this.exc.status || undefined,
        page: this.exc.pagination.page, pageSize: this.exc.pagination.pageSize
      }))
    },
    exceptionCreateIdentity() {
      return this.academicFlow?.identity?.() || JSON.stringify(this.ctx)
    },
    canCreateRegistrationException() {
      return !!this.batchId && !this.eligDisposed && !this.excCreating && !this.excReceiptChecking && !this.excPendingCreate &&
        this.excCreateDeniedIdentity !== this.exceptionCreateIdentity() &&
        matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.registration.exception.create')
    },
    canReadExceptionCreate() {
      return !!this.excPendingCreate && !this.eligDisposed &&
        this.excPendingCreate.identityKey === this.exceptionCreateIdentity() &&
        matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.registration.exception.view')
    },
    closeExceptionCreate() {
      if (!this.excCreating && !this.excReceiptChecking) this.excDrawer.visible = false
    },
    openExceptionCreate() {
      if (!this.canCreateRegistrationException()) return
      this.excCreateError = ''; this.excCreateReceipt = null
      this.excDrawer = { visible: true, studentId: '', exceptionType: 'OTHER', description: '', saving: false, formError: '',
        batchId: String(this.batchId), identityKey: this.exceptionCreateIdentity(), contextKey: this.eligibilityContextKey }
    },
    exceptionDraftCurrent(drawer) {
      return !this.eligDisposed && drawer === this.excDrawer && drawer.visible &&
        drawer.identityKey === this.exceptionCreateIdentity() && drawer.contextKey === this.eligibilityContextKey &&
        drawer.batchId === String(this.batchId)
    },
    denyExceptionCreate(target) {
      if (this.eligDisposed || target.identityKey !== this.exceptionCreateIdentity()) return
      if (target.contextKey !== this.eligibilityContextKey) {
        if (this.excPendingCreate) this.excPendingCreate.denied = true
        return
      }
      this.excCreateDeniedIdentity = target.identityKey
      this.excCreateReceipt = null
      this.exc.rows = []; this.exc.pagination.total = 0; this.queueVersions.exc++
      this.exc.loading = false
      this.excDrawer = { visible: false, studentId: '', exceptionType: 'OTHER', description: '', saving: false, formError: '' }
      this.excCreateError = '当前身份无权完成本次异常操作或正式记录核对，已清除原对象内容。'
      if (this.excPendingCreate) this.excPendingCreate.denied = true
    },
    async submitExceptionCreate() {
      if (!this.canCreateRegistrationException()) return
      const drawer = this.excDrawer
      if (!this.exceptionDraftCurrent(drawer)) { drawer.formError = '身份或批次已变化，请重新选择后填写'; return }
      if (!drawer.studentId) { drawer.formError = '请选择学生'; return }
      if (drawer.exceptionType === 'OTHER' && !drawer.description.trim()) {
        drawer.formError = '异常类型为「其他」时说明必填'; return
      }
      const target = { batchId: drawer.batchId, studentId: String(drawer.studentId), exceptionType: drawer.exceptionType,
        description: drawer.description.trim(), identityKey: drawer.identityKey, contextKey: drawer.contextKey,
        exceptionId: '', message: '请求结果待确认。' }
      this.excCreating = true; drawer.saving = true; drawer.formError = ''; this.excCreateReceipt = null
      try {
        const res = await academicAffairsApi.createRegistrationException(target.batchId, {
          studentId: target.studentId, exceptionType: target.exceptionType, description: target.description || undefined
        })
        if (this.eligDisposed) return
        if (String(res.code).startsWith('403')) { this.denyExceptionCreate(target); return }
        const receipt = res.data
        const valid = res.code === 0 && typeof receipt?.exceptionId === 'string' && receipt.exceptionId &&
          String(receipt.batchId) === target.batchId && String(receipt.studentId) === target.studentId && receipt.status === 'OPEN'
        if (valid) {
          this.excPendingCreate = { ...target, exceptionId: receipt.exceptionId, message: '已收到创建回执，正在核对正式记录。' }
          const confirmed = await this.checkExceptionCreateReceipt()
          if (confirmed && this.exceptionDraftCurrent(drawer)) { drawer.visible = false; this.loadExceptions() }
          else if (this.exceptionDraftCurrent(drawer)) drawer.formError = '创建回执已收到，正式记录仍待核对；关闭窗口后可重新查询正式异常 ID。'
        } else if (res.code === 0 || Number(res.code) >= 500000 || ['REQUEST_TIMEOUT', 'NETWORK_ERROR'].includes(res.bizCode)) {
          this.excPendingCreate = target
          if (this.exceptionDraftCurrent(drawer)) drawer.formError = '结果待确认，已暂停重复提交，请核对正式异常记录。'
        } else if (this.exceptionDraftCurrent(drawer)) drawer.formError = res.message || '异常新增未完成，请核对原说明后重试'
      } catch {
        if (!this.eligDisposed) {
          this.excPendingCreate = target
          if (this.exceptionDraftCurrent(drawer)) drawer.formError = '结果待确认，已暂停重复提交，请核对正式异常记录。'
        }
      } finally { drawer.saving = false; this.excCreating = false }
    },
    async checkExceptionCreateReceipt() {
      const target = this.excPendingCreate
      if (!target?.exceptionId || this.excReceiptChecking) return false
      if (!this.canReadExceptionCreate()) {
        if (target.identityKey === this.exceptionCreateIdentity()) target.message = '当前身份尚无正式异常查看权限，结果仍待核对。'
        return false
      }
      const current = () => !this.eligDisposed && target === this.excPendingCreate &&
        target.identityKey === this.exceptionCreateIdentity()
      this.excReceiptChecking = true
      try {
        const pageSize = 100, maxPages = 5
        for (let page = 1; page <= maxPages; page++) {
          const res = await academicAffairsApi.getRegistrationExceptions({ batchId: target.batchId, page, pageSize })
          if (!current()) return false
          if (String(res.code).startsWith('403')) { this.denyExceptionCreate(target); return false }
          if (res.code !== 0 || !Array.isArray(res.data?.list)) {
            target.message = res.message || '正式记录读取失败，结果仍待核对。'; return false
          }
          const row = res.data.list.find(item => String(item.exceptionId) === target.exceptionId)
          if (row) {
            if (String(row.batchId) !== target.batchId || String(row.studentId) !== target.studentId ||
              row.exceptionType !== target.exceptionType || !['OPEN', 'RESOLVED'].includes(row.status)) {
              target.message = '正式记录的对象或状态与创建回执不一致，结果仍待核对。'; return false
            }
            this.excCreateReceipt = { exceptionId: target.exceptionId, batchId: target.batchId,
              studentId: target.studentId, status: row.status, identityKey: target.identityKey }
            if (this.excCreateDeniedIdentity === target.identityKey) this.excCreateDeniedIdentity = ''
            this.excPendingCreate = null
            return true
          }
          if (res.data.list.length < pageSize || page * pageSize >= Number(res.data.total)) break
        }
        target.message = '本次有限范围内未找到该 ID，不能判断未创建；可再次查询正式 ID。'
        return false
      } catch {
        if (current()) target.message = '正式记录读取中断，结果仍待核对；可再次查询正式 ID。'
        return false
      } finally { this.excReceiptChecking = false }
    },
    askResolveException(row) {
      if (!this.canRunRegistrationAction('exception.resolve')) return
      const target = this.captureRegistrationAction('exception', row)
      if (!this.registrationTargetCurrent(target)) return
      this.registrationWrite.error = ''
      this.resolveDialog = { visible: true, exceptionId: target.objectId, target, submitting: false,
        message: `学生 ${target.studentId}，批次 ${target.batchId}，异常 ${target.objectId}；确认处理后只解除该异常，注册资格及正式注册仍需另行核对。` }
    },
    /** @returns {boolean} 是否成功（同 reviewDeferral，失败不关弹窗） */
    async resolveException(exceptionId, note, target) {
      if (!this.canRunRegistrationAction('exception.resolve') || !this.registrationTargetCurrent(target) ||
        String(exceptionId) !== target.objectId || !String(note || '').trim()) return false
      const command = { ...target, kind: 'resolve', permission: 'exception.resolve', label: '处理注册异常',
        note: String(note).trim(), expectedStatus: 'RESOLVED' }
      const ok = await this.runRegistrationAction(command, () => academicAffairsApi.resolveRegistrationException(command.objectId, command.note))
      if (ok && this.registrationActionCurrent(command)) this.loadExceptions()
      return ok
    },

    /* ── 注册归档：批次在「注册批次」列表关闭→归档后进入本清单，只读+导出 ── */
    onArchivePage(page) { this.archive.pagination.page = page; this.loadArchive() },
    async loadArchive() {
      return this.loadRegistrationQueue('archive', async (current) => {
        const res = await academicAffairsApi.getArchivedRegistrationBatches({
          page: this.archive.pagination.page, pageSize: this.archive.pagination.pageSize
        })
        if (!current() || res.code !== 0) return res
        const list = res.data.list || []
        const details = await Promise.allSettled(list.map((b) => academicAffairsApi.getRegistrationArchiveDetail(b.batchId)))
        const denied = details.find(d => d.status === 'fulfilled' && String(d.value?.code).startsWith('403'))
        if (denied) return denied.value
        return { code: 0, data: { total: res.data.total, list: list.map((b, i) => {
          const d = details[i].status === 'fulfilled' ? details[i].value : null
          const ok = d?.code === 0 && d.data?.stats
          return { ...b, registered: ok ? d.data.stats.registered : null, total: ok ? d.data.stats.total : null,
            archivedAt: (ok && d.data.archivedAt) || '', detailError: ok ? '' : '归档统计读取失败，请重新查询' }
        }) } }
      })
    },
    goArchiveDetail(row) {
      this.$router.push(`/admin/academic-affairs/registration/${row.batchId}`)
    },
    openArchiveExport(row) {
      this.exportDialog = {
        visible: true, title: `导出注册归档 · ${row.batchName}`, submitting: false,
        action: async (purpose) => {
          const res = await academicAffairsApi.exportRegistrationArchive(row.batchId, purpose)
          if (res.code !== 0) { toast.error(res.message || '导出失败'); return false }
          this.downloadBlob(res.data, `注册归档-${row.batchName}-${Date.now()}.xlsx`)
          toast.success('导出成功')
          return true
        }
      }
    },

    /* ── 通用确认弹窗回调 ── */
    async onConfirm() {
      const a = this.pendingAction
      this.confirm.visible = false
      this.pendingAction = null
      if (!a) return
      if (a.kind === 'eligible') {
        if (!this.eligibilityTargetCurrent(a.target)) { toast.error('批次、身份或学生已变化，请重新核对'); return }
        await this.verifyEligibilityTarget(a.target, { result: 'ELIGIBLE' })
      } else if (a.kind === 'deferralApprove') {
        await this.reviewDeferral(a.target?.objectId, 'APPROVE', '', a.target)
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aarw-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-color, #e5e7eb); margin-bottom: 16px; }
.aarw-tab { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; }
.aarw-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 600; }
.aarw-registration { padding-bottom: 72px; }
.aarw-registration .aarw-tabs { margin-bottom: 0; }
.aarw-batch-bar { margin-bottom: 0; }
.aarw-batch-row { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.aarw-filter-keyword { flex: 1 1 180px; max-width: 280px; }
.aarw-filter-status { flex: 0 1 180px; }
.aarw-batch-label { font-size: 13px; color: var(--text-secondary, #64748b); }
.aarw-batch-hint { margin: 0; }
.aarw-toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 12px; }
.aarw-toolbar > :first-child { max-width: 360px; }
.aarw-toolbar > :nth-child(2) { max-width: 220px; }
.aarw-form { display: flex; flex-direction: column; gap: 12px; }
.aarw-review-workspace { display: flex; flex-direction: column; gap: 12px; }
.aarw-object-summary { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px; padding: 16px; border: 1px solid var(--border-color, #e2e8f0); border-left: 3px solid var(--primary-color, #2563eb); border-radius: 10px; background: var(--surface-color, #fff); }
.aarw-object-summary__identity { min-width: 0; }
.aarw-object-summary h2 { margin: 0 0 6px; font-size: 16px; line-height: 1.5; }
.aarw-object-summary p { margin: 0 0 6px; color: var(--text-secondary, #64748b); font-size: 12px; overflow-wrap: anywhere; }
.aarw-object-summary__status { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; color: var(--text-secondary, #64748b); font-size: 12px; }
.aarw-object-summary__responsibility { display: flex; flex-wrap: wrap; gap: 16px; margin: 0; font-size: 12px; }
.aarw-object-summary dt { margin-bottom: 4px; color: var(--text-secondary, #64748b); }
.aarw-object-summary dd { margin: 0; font-weight: 600; }
.aarw-progress { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; list-style: none; padding: 14px 16px; margin: 0; border: 1px solid var(--border-color, #e2e8f0); border-radius: 10px; background: var(--surface-color, #fff); }
.aarw-progress li { display: flex; align-items: flex-start; gap: 8px; color: var(--text-secondary, #64748b); font-size: 12px; }
.aarw-progress__number { display: grid; place-items: center; flex: 0 0 24px; height: 24px; border: 1px solid var(--border-color, #e2e8f0); border-radius: 50%; }
.aarw-progress strong { display: block; padding-top: 4px; font-weight: 500; }
.aarw-progress small { display: block; margin-top: 8px; line-height: 1.6; }
.aarw-progress .is-complete .aarw-progress__number { color: var(--success-color, #167647); background: var(--success-bg, #edf8f1); border-color: var(--success-border, #c7e6d3); }
.aarw-progress .is-current { color: var(--primary-color, #2563eb); }
.aarw-progress .is-current .aarw-progress__number { color: #fff; background: var(--primary-color, #2563eb); border-color: var(--primary-color, #2563eb); }
.aarw-elig-layout { display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 16px; align-items: start; }
.aarw-elig-queue { min-width: 0; background: var(--surface-color, #fff); border: 1px solid var(--border-color, #e5e7eb); border-radius: 10px; padding: 10px; }
.aarw-elig-queue__head { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; margin-bottom: 12px; }
.aarw-elig-queue__items { display: flex; flex-direction: column; gap: 8px; }
.aarw-elig-item { text-align: left; border: 1px solid var(--border-color, #e2e8f0); background: var(--surface-color, #fff); border-radius: 8px; padding: 10px 12px; }
.aarw-elig-item.is-active { border-color: var(--primary-color, #2563eb); background: var(--primary-soft, #eef3ff); }
.aarw-elig-item:disabled { opacity: 0.55; cursor: not-allowed; }
.aarw-elig-item__main { display: flex; justify-content: space-between; gap: 8px; }
.aarw-elig-item__meta { display: flex; justify-content: space-between; align-items: center; margin-top: 4px; }
.aarw-elig-queue__pager { display: flex; justify-content: space-between; align-items: center; margin-top: 10px; }
.aarw-elig-workspace { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.aarw-evidence-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.aarw-evidence-item { min-width: 0; padding: 12px; border: 1px solid var(--border-color, #e2e8f0); border-radius: 8px; }
.aarw-evidence-item__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.aarw-evidence-item h3 { margin: 2px 0 0; font-size: 13px; line-height: 1.5; }
.aarw-evidence-item p { margin: 10px 0 0; color: var(--text-secondary, #64748b); font-size: 12px; line-height: 1.7; overflow-wrap: anywhere; }
.aarw-evidence-item .mp-link { margin-top: 10px; }
.aarw-action-grid { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; }
.aarw-object-empty { margin: 0; color: var(--text-secondary, #64748b); }
@media (max-width: 1100px) {
  .aarw-elig-layout { grid-template-columns: minmax(220px, 30%) minmax(0, 1fr); }
  .aarw-evidence-grid { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 720px) {
  .aarw-elig-layout { grid-template-columns: minmax(0, 1fr); }
  .aarw-progress { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .aarw-batch-row { flex-wrap: wrap; }
  .aarw-tabs { overflow-x: auto; }
  .aarw-tab { flex-shrink: 0; }
}
</style>
