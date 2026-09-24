<template>
  <ModulePageShell
    :title="pageMeta.title"
    :subtitle="pageMeta.subtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton v-if="tab === 'dashboard'" variant="ghost" @click="openExport">导出质量报告</AppButton>
      <AppButton v-else-if="isRecordTab" variant="primary" :disabled="writeLocked" @click="openRecCreate">{{ recMeta.primaryLabel }}</AppButton>
      <AppButton v-else-if="tab === 'rectify'" variant="primary" :disabled="writeLocked" @click="openRectCreate">从问题生成整改</AppButton>
      <AppButton v-else-if="tab === 'followUp' && rectCurrent && ['PENDING','IN_PROGRESS'].includes(rectCurrent.status)" variant="primary" :disabled="writeLocked" @click="openProgress(rectCurrent)">追加整改进度</AppButton>
      <AppButton v-else-if="tab === 'archive'" variant="ghost" :disabled="archiveExporting" @click="doArchiveExport('rectifications')">导出质量档案</AppButton>
    </template>

    <div class="aaql-tabs">
      <button v-for="t in tabs" :key="t.key" :class="['aaql-tab', { 'is-active': tab === t.key }]" @click="switchTab(t.key)">{{ t.label }}</button>
    </div>

    <section v-if="actionNotice" :class="['aaql-receipt', { 'is-warning': !actionReceipt?.verified }]" role="status">
      <div><strong>{{ actionReceipt?.verified ? '已核对正式业务状态' : '操作结果待核实' }}</strong><p>{{ actionNotice }}</p></div>
      <div v-if="actionReceipt"><small>业务对象</small><b>{{ actionReceipt.objectLabel }}</b></div>
      <div v-if="actionReceipt"><small>下一责任</small><b>{{ actionReceipt.next }}</b></div>
      <AppButton v-if="pendingWrite" variant="ghost" :disabled="recSaving || rectSaving" @click="verifyPendingWrite">只读核对原操作</AppButton>
    </section>

    <!-- AA-226：运行质量看板。指标与责任队列分别取真实接口，任一读侧失败均单独说明。 -->
    <div v-if="tab === 'dashboard'" class="mp-stack">
      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <template v-else>
        <AppInlineAlert v-if="dashboardNotice" type="warning" :description="dashboardNotice" />
        <div class="aaql-grid aaql-grid--summary">
          <article v-for="item in overviewMetrics" :key="item.key" :class="['aaql-card', { 'is-due': item.key === 'due' && item.value > 0 }]">
            <div class="aaql-label">{{ item.label }}</div>
            <div class="aaql-value">{{ item.value }}</div>
            <div class="aaql-sub">{{ item.note }}</div>
          </article>
        </div>
        <div class="aaql-overview-layout">
          <section class="aaql-panel">
            <header><h3>待我办理</h3><span>来自正式质量记录与整改任务</span></header>
            <EmptyState v-if="!overviewRows.length" title="当前没有待办质量事项" description="已按当前身份与数据范围读取" />
            <DataTable v-else :columns="overviewColumns" :rows="overviewRows" row-key="objectKey">
              <template #cell-sourceType="{ row }">{{ row.sourceTypeLabel }}</template>
              <template #cell-deadline="{ row }">{{ row.deadline ? fmt(row.deadline) : '未设置' }}</template>
              <template #cell-status="{ row }"><StatusTag :type="row.statusType" :label="row.statusLabel" /></template>
              <template #cell-ops="{ row }"><button class="mp-link" @click="openOverviewItem(row)">继续办理</button></template>
            </DataTable>
          </section>
          <aside class="aaql-panel aaql-indicators">
            <header><h3>授权范围质量指标</h3><span>每项指标保留服务端筛选口径</span></header>
            <div v-for="i in indicators" :key="i.key" class="aaql-indicator-row"><span>{{ i.label }}</span><b>{{ i.value }}{{ i.unit }}</b><small v-if="i.numerator != null">{{ i.numerator }} / {{ i.denominator }}</small></div>
          </aside>
        </div>
        <details class="aaql-history"><summary>质量报告导出历史（{{ reports.length }}）</summary><EmptyState v-if="!reports.length" title="暂无导出记录" description="导出质量报告后在此保留审计记录" /><DataTable v-else :columns="reportColumns" :rows="reports" row-key="exportId"><template #cell-occurredAt="{ row }">{{ fmt(row.occurredAt) }}</template></DataTable></details>
      </template>
    </div>

    <!-- AA-227～AA-230：按业务字段呈现的质量记录表单；历史对象仍可继续办理。 -->
    <div v-else-if="isRecordTab" class="mp-stack">
      <AppInlineAlert v-if="tab === 'incident'" type="warning"
        description="教学事故等级与处理由学校现行制度认定。本页登记事实与处置意见，不自动生成处罚结论。" />
      <ol class="aaql-stage-rail" aria-label="质量闭环阶段"><li v-for="(step,index) in qualityStages" :key="step" :class="{ 'is-done': index < recordStage, 'is-current': index === recordStage }"><span>{{ index < recordStage ? '✓' : index + 1 }}</span><div><strong>{{ step }}</strong><small>{{ index === recordStage ? '当前环节' : index < recordStage ? '已有正式事实' : '等待前序完成' }}</small></div></li></ol>
      <ErrorState v-if="panelError" :description="panelError" @retry="loadRecords" />
      <LoadingState v-else-if="recLoading" />
      <section v-else class="aaql-record-layout">
        <main class="aaql-panel aaql-form-card">
          <header><h3>{{ recMeta.label }}记录 · 完整表单</h3><StatusTag :type="recCreateVisible ? 'warning' : 'default'" :label="recCreateVisible ? '尚未提交' : '已收起'" /></header>
          <div v-if="recCreateVisible" class="aaql-form aaql-form--record">
            <AppFormItem v-if="recMeta.showCourse" :label="recMeta.courseLabel" required><AppCoursePicker v-model="recForm.courseId" :disabled="writeLocked" @change="onCoursePicked" /></AppFormItem>
            <AppFormItem v-if="recMeta.showTeacher" :label="recMeta.teacherLabel" :required="tab === 'supervision'"><AppTeacherPicker v-model="recForm.teacherKey" :disabled="writeLocked" @change="onTeacherPicked" /></AppFormItem>
            <AppFormItem v-if="recMeta.showCollege" label="责任单位"><AppCollegePicker v-model="recForm.collegeId" :disabled="writeLocked" /></AppFormItem>
            <AppFormItem :label="recMeta.occurredLabel" required><AppDateTimePicker v-model="recForm.occurredAt" :disabled="writeLocked" /></AppFormItem>
            <AppFormItem :label="recMeta.titleLabel" required><AppTextInput v-model="recForm.title" :placeholder="recMeta.titlePlaceholder" :disabled="writeLocked" /></AppFormItem>
            <AppFormItem v-if="recMeta.showLocation" label="地点/教室"><AppTextInput v-model="recForm.location" placeholder="填写实际地点" :disabled="writeLocked" /></AppFormItem>
            <AppFormItem v-if="recMeta.showCategory" :label="recMeta.categoryLabel"><AppTextInput v-model="recForm.category" :placeholder="recMeta.categoryPlaceholder" :disabled="writeLocked" /></AppFormItem>
            <AppFormItem class="aaql-field--full" :label="recMeta.descriptionLabel" required><AppTextarea v-model="recForm.description" :rows="3" :placeholder="recMeta.descriptionPlaceholder" :disabled="writeLocked" /></AppFormItem>
            <AppFormItem class="aaql-field--full" :label="recMeta.conclusionLabel"><AppTextarea v-model="recForm.conclusion" :rows="2" :placeholder="recMeta.conclusionPlaceholder" :disabled="writeLocked" /></AppFormItem>
            <AppFormItem v-if="tab === 'incident'" class="aaql-field--full" label="处理意见"><AppTextarea v-model="recForm.handlingNote" :rows="2" placeholder="如实记录现有处理意见" :disabled="writeLocked" /></AppFormItem>
            <AppFormItem class="aaql-field--full" label="需要转入整改"><AppRadioGroup v-model="recForm.needRectify" :disabled="writeLocked" :options="[{ label: '是', value: true }, { label: '否', value: false }]" /></AppFormItem>
            <AppInlineAlert v-if="recFormError" class="aaql-field--full" type="danger" :description="recFormError" />
            <footer class="aaql-form-actions aaql-field--full"><span>来源对象和当前身份确认后，提交正式质量记录。</span><AppButton variant="ghost" :disabled="writeLocked" @click="resetRecForm">清空</AppButton><AppButton variant="primary" :loading="recSaving" :disabled="writeLocked" @click="submitRecCreate">{{ recMeta.primaryLabel }}</AppButton></footer>
          </div>
        </main>
        <aside class="aaql-side-stack">
          <section class="aaql-panel aaql-conditions"><header><h3>启动条件</h3></header><ul><li><span>正式来源对象已选定</span><b>{{ recordSourceReady ? '已确认' : '需确认' }}</b></li><li><span>当前身份和范围有明确依据</span><b>{{ ctx?.dataScope?.scopeName ? '已确认' : '需确认' }}</b></li><li><span>提交后由服务器复核状态</span><b>提交时复验</b></li></ul><p>创建责任：质量责任岗</p><p>交给：整改责任人 → 质量复核岗</p></section>
          <section class="aaql-panel"><header><h3>历史记录</h3><AppSelect v-model="recStatusFilter" :options="recStatusOptions" placeholder="全部状态" @change="searchRecords" /></header><p>{{ recRows.length }} 条当前页记录；选择对象可继续确认、关闭或发起整改。</p></section>
        </aside>
      </section>
      <details v-if="recRows.length" class="aaql-history" open><summary>历史{{ recMeta.label }}记录（{{ recRows.length }}）</summary><DataTable :columns="recColumns" :rows="recRows" row-key="recordId" row-clickable @row-click="viewRecDetail"><template #cell-status="{ row }"><StatusTag :type="recStatusType(row.status)" :label="recStatusLabel(row.status)" dot /></template><template #cell-needRectify="{ row }"><span v-if="row.needRectify" class="aaql-flag">需整改</span></template><template #cell-ops="{ row }"><button class="mp-link" @click.stop="viewRecDetail(row)">详情</button><button v-if="row.status === 'SUBMITTED'" class="mp-link" :disabled="writeLocked" @click.stop="askRecTransition('confirm', row)">确认</button><button v-if="row.status === 'CONFIRMED'" class="mp-link" :disabled="writeLocked" @click.stop="askRecTransition('close', row)">关闭</button><button v-if="row.status === 'SUBMITTED'" class="mp-link is-danger" :disabled="writeLocked" @click.stop="askRecTransition('cancel', row)">撤销</button><button v-if="row.status === 'CONFIRMED'" class="mp-link" :disabled="writeLocked" @click.stop="openRectifyFromRecord(row)">发起整改</button></template></DataTable></details>
    </div>

    <!-- AA-231：必须从正式问题生成的整改看板。 -->
    <div v-else-if="tab === 'rectify'" class="mp-stack">
      <div class="aaql-bar"><AppSelect v-model="rectStatusFilter" :options="rectStatusOptions" placeholder="全部状态" @change="searchRectifications" /></div>
      <AppInlineAlert v-if="rectPartial" type="warning" :description="rectPartial" />
      <ErrorState v-if="panelError" :description="panelError" @retry="loadRectifications" />
      <LoadingState v-else-if="rectLoading" />
      <EmptyState v-else-if="!displayRectRows.length" title="暂无整改任务" description="从已确认的问题记录发起，或点击上方「从问题生成整改」" />
      <div v-else class="aaql-kanban"><section v-for="lane in rectLanes" :key="lane.key" class="aaql-lane"><header><h3>{{ lane.label }}</h3><span>{{ lane.rows.length }}</span></header><div class="aaql-lane-list"><article v-for="row in lane.rows" :key="row.rectId" class="aaql-rect-card"><h4>{{ row.title }}</h4><p>来源：{{ row.sourceTitle || '来源问题待核对' }}</p><p>责任：{{ row.responsibleName || '责任人待指定' }}</p><p>期限：{{ fmt(row.deadline) || '未设置' }}</p><footer><StatusTag :type="rectStatusType(row)" :label="rectStatusLabel(row)" /><button class="mp-link" @click="viewRectDetail(row)">{{ row.status === 'CLOSED' ? '查看复核证据' : '进入处理' }}</button></footer></article><EmptyState v-if="!lane.rows.length" title="当前列暂无任务" description="状态变化后自动进入对应列" /></div></section></div>
    </div>

    <!-- AA-232：责任队列、当前对象、来源证据与跟进动作。 -->
    <div v-else-if="tab === 'followUp'" class="mp-stack">
      <AppInlineAlert type="info" description="提交复核只代表整改责任人完成本阶段；复核通过后才会关闭归档。" />
      <AppInlineAlert v-if="rectPartial" type="warning" :description="rectPartial" />
      <div class="aaql-bar"><AppSelect v-model="rectStatusFilter" :options="rectStatusOptions" placeholder="未关闭任务" @change="searchRectifications" /></div>
      <ErrorState v-if="panelError" :description="panelError" @retry="loadRectifications" /><LoadingState v-else-if="rectLoading" /><EmptyState v-else-if="!displayRectRows.length" title="本页暂无待跟进整改任务" description="可翻页继续查找，或指定状态筛选待整改、整改中和待复核任务" />
      <section v-else class="aaql-follow-layout"><aside class="aaql-panel aaql-follow-queue"><header><h3>责任队列</h3><span>{{ displayRectRows.length }} 项</span></header><button v-for="row in displayRectRows" :key="row.rectId" :class="['aaql-follow-item',{ 'is-active': String(rectCurrent?.rectId) === String(row.rectId) }]" @click="selectRect(row)"><strong>{{ row.title }}</strong><span>{{ row.sourceTitle || '来源问题待核对' }} · #{{ row.rectId }}</span><StatusTag :type="rectStatusType(row)" :label="rectStatusLabel(row)" /></button></aside><main class="aaql-follow-main"><LoadingState v-if="detailLoading" /><ErrorState v-else-if="detailError" :description="detailError" @retry="reloadRectCurrent" /><EmptyState v-else-if="!rectCurrent" title="选择一项整改任务" description="核对来源证据后追加当前对象的整改进度" /><template v-else><section class="aaql-object-context"><div><span>当前整改对象</span><h3>{{ rectCurrent.title }}</h3><p>来源：{{ rectCurrent.sourceTitle || '来源问题待核对' }} · 任务 #{{ rectCurrent.rectId }}</p></div><div><small>当前责任</small><strong>{{ rectCurrent.responsibleName || '整改责任人待明确' }}</strong></div><div><small>下一责任</small><strong>{{ rectCurrent.status === 'SUBMITTED' ? '质量复核岗' : '整改责任人 → 质量复核岗' }}</strong></div></section><section class="aaql-panel"><header><h3>来源证据与最近跟进</h3><StatusTag :type="rectStatusType(rectCurrent)" :label="rectStatusLabel(rectCurrent)" /></header><AppTimeline :items="rectTimelineItems" /><footer class="aaql-detail-actions"><AppButton variant="ghost" @click="returnToRectify(rectCurrent)">返回整改看板</AppButton><AppButton v-if="['PENDING','IN_PROGRESS'].includes(rectCurrent.status)" :disabled="writeLocked" @click="openProgress(rectCurrent)">追加进度</AppButton><AppButton v-if="['PENDING','IN_PROGRESS'].includes(rectCurrent.status)" variant="primary" :disabled="writeLocked" @click="openSubmitRect(rectCurrent)">提交复核</AppButton><AppButton v-if="rectCurrent.status === 'SUBMITTED'" variant="primary" :disabled="writeLocked" @click="openReview(rectCurrent,'APPROVE')">复核通过并关闭</AppButton><AppButton v-if="rectCurrent.status === 'SUBMITTED'" variant="danger" :disabled="writeLocked" @click="openReview(rectCurrent,'REJECT')">驳回整改</AppButton></footer></section></template></main></section>
    </div>

    <!-- AA-233：真实闭环记录与聚合统计。 -->
    <div v-else-if="tab === 'archive'" class="mp-stack">
      <div class="aaql-bar">
        <AppTermEntityPicker v-model="archiveTermId" placeholder="全部学期" style="max-width:220px" @change="loadArchive" />
        <AppButton size="small" variant="ghost" :loading="archiveExporting" @click="doArchiveExport('records')">导出问题记录 xlsx</AppButton>
        <AppButton size="small" variant="ghost" :loading="archiveExporting" @click="doArchiveExport('rectifications')">导出整改任务 xlsx</AppButton>
      </div>
      <ErrorState v-if="panelError" :description="panelError" @retry="loadArchive" />
      <LoadingState v-else-if="archiveLoading" />
      <template v-else>
        <AppInlineAlert type="info" description="质量档案来自已关闭问题与整改闭环；原记录只读，后续纠错通过新版本或正式业务流程办理。" /><AppInlineAlert v-if="archivePartial" type="warning" :description="archivePartial" />
        <div class="aaql-grid aaql-grid--archive"><article class="aaql-card"><div class="aaql-value">{{ archiveData.total ?? '待核对' }}</div><div class="aaql-label">质量问题总数</div></article><article class="aaql-card"><div class="aaql-value">{{ archiveData.rectification?.total ?? '待核对' }}</div><div class="aaql-label">整改任务总数</div></article><article class="aaql-card"><div class="aaql-value">{{ archiveData.rectification?.closed ?? '待核对' }}</div><div class="aaql-label">闭环归档</div></article><article class="aaql-card"><div class="aaql-value aaql-danger">{{ archiveData.rectification?.overdue ?? '待核对' }}</div><div class="aaql-label">逾期未关闭</div></article></div>
        <section class="aaql-panel"><header><h3>质量档案 · 原记录与正式凭证</h3><span>{{ archiveRows.length }} 条当前读取结果</span></header><EmptyState v-if="!archiveRows.length" title="当前范围暂无闭环档案" description="已关闭记录或整改任务会进入此处" /><DataTable v-else :columns="archiveColumns" :rows="archiveRows" row-key="archiveKey"><template #cell-source="{ row }">{{ row.sourceTitle }}<small class="aaql-cell-note">{{ row.sourceTypeLabel }}</small></template><template #cell-rectification="{ row }">{{ row.rectTitle || '未形成整改任务' }}</template><template #cell-conclusion="{ row }">{{ row.conclusion || '复核结论待核对' }}</template><template #cell-closedAt="{ row }">{{ fmt(row.closedAt) || '关闭时间未提供' }}</template><template #cell-archiveStatus><StatusTag type="success" label="已归档" /></template><template #cell-ops="{ row }"><button class="mp-link" @click="openArchiveEvidence(row)">查看封存证据</button></template></DataTable></section>
      </template>
    </div>

    <!-- 报告导出 -->
    <template v-if="isRecordTab || isRectTab">
      <p v-if="tab === 'followUp' && !rectStatusFilter" class="mp-note">分页总数包含已关闭任务；当前页仅展示未关闭任务，页内优先显示逾期项。</p>
      <AppPagination v-if="!panelError" :total="queuePagination.total" :page="queuePagination.page" :page-size="queuePagination.pageSize" :show-size-changer="false" @change="onQueuePageChange" />
    </template>

    <AppDrawer :visible="exportVisible" title="导出教务运行质量报告" mode="modal" size="small" @close="exportVisible = false">
      <div class="aaql-form">
        <AppFormItem label="导出用途" required>
          <AppTextInput ref="purposeInput" v-model="exportPurpose" placeholder="如 期末教学质量分析（≥5字，写审计）" :disabled="exporting" />
          <AppQuickPhrases scene-key="common.exportPurpose" @pick="onPickPurpose" />
        </AppFormItem>
        <AppInlineAlert type="info" description="报告含挂科率/预警/发布率/毕业通过率等质量指标，导出带水印+审计。" />
        <AppInlineAlert v-if="exportError" type="danger" :description="exportError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="exporting" @click="exportVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="exporting" @click="doExport">导出 xlsx</AppButton>
      </template>
    </AppDrawer>

    <!-- 问题记录：详情 -->
    <AppDrawer :visible="recDetailVisible" title="记录详情" mode="modal" size="medium" @close="closeRecDetail">
      <AppDescriptionList v-if="recCurrent" :items="recDescItems" :columns="2">
        <template #status><StatusTag :type="recStatusType(recCurrent.status)" :label="recStatusLabel(recCurrent.status)" dot /></template>
      </AppDescriptionList>
    </AppDrawer>

    <!-- 整改任务：发起（含来源问题记录一键发起） -->
    <AppDrawer :visible="rectCreateVisible" :title="rectSourceRecord ? `从「${rectSourceRecord.title}」发起整改` : '发起质量整改任务'" mode="modal" size="medium" @close="rectCreateVisible = false">
      <div class="aaql-form">
        <AppFormItem v-if="!rectSourceRecord" label="来源问题" required><AppSelect v-model="rectSourceRecordId" :options="rectSourceOptions" placeholder="选择已确认的质量问题" :disabled="rectSaving" /></AppFormItem>
        <AppFormItem label="整改标题" required><AppTextInput v-model="rectForm.title" placeholder="如 XX课程教学检查整改" :disabled="rectSaving" /></AppFormItem>
        <AppFormItem label="整改要求" required><AppTextarea v-model="rectForm.requirement" :rows="3" placeholder="≥5字，写审计" :disabled="rectSaving" /></AppFormItem>
        <AppFormItem label="责任人"><AppTeacherPicker v-model="rectForm.responsibleKey" placeholder="选择整改责任人" :disabled="rectSaving" @change="onResponsiblePicked" /></AppFormItem>
        <AppFormItem label="整改期限"><AppDateTimePicker v-model="rectForm.deadline" :disabled="rectSaving" /></AppFormItem>
        <AppInlineAlert v-if="rectFormError" type="danger" :description="rectFormError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="rectSaving" @click="rectCreateVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="rectSaving" @click="submitRectCreate">发起</AppButton>
      </template>
    </AppDrawer>

    <!-- 整改任务：详情 + 跟进时间线 -->
    <AppDrawer :visible="rectDetailVisible" title="整改任务详情" mode="modal" size="large" @close="closeRectDetail">
      <div v-if="rectCurrent" class="aaql-detail">
        <AppDescriptionList :items="rectDescItems" :columns="2">
          <template #status><StatusTag :type="rectStatusType(rectCurrent)" :label="rectStatusLabel(rectCurrent)" dot /></template>
          <template #deadline><b :class="{ 'aaql-danger': rectCurrent.overdue }">{{ fmt(rectCurrent.deadline) || '—' }}<span v-if="rectCurrent.overdue">（已逾期）</span></b></template>
        </AppDescriptionList>
        <div class="aaql-section-title">跟进时间线</div>
        <AppTimeline :items="rectTimelineItems" />
      </div>
      <template v-if="rectCurrent" #footer><AppButton variant="ghost" @click="closeRectDetail">返回整改看板</AppButton><AppButton v-if="rectCurrent.status !== 'CLOSED'" variant="primary" @click="continueRect(rectCurrent)">进入整改跟进</AppButton></template>
    </AppDrawer>

    <!-- 跟进说明 / 提交复核 -->
    <AppDrawer :visible="rectNoteVisible" :title="rectNoteMode === 'progress' ? '记录整改跟进' : '提交整改说明待复核'" mode="modal" size="small" @close="rectNoteVisible = false">
      <div class="aaql-form">
        <AppFormItem :label="rectNoteMode === 'progress' ? '跟进说明' : '整改说明'" required>
          <AppTextarea v-model="rectNoteText" :rows="4" placeholder="请填写具体进展或整改结果说明" :disabled="rectSaving" />
        </AppFormItem>
        <AppInlineAlert v-if="rectFormError" type="danger" :description="rectFormError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="rectSaving" @click="rectNoteVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="rectSaving" @click="submitRectNote">提交</AppButton>
      </template>
    </AppDrawer>

    <!-- 复核（通过/驳回） -->
    <AppDrawer :visible="reviewVisible" :title="reviewAction === 'APPROVE' ? '复核通过并关闭' : '驳回整改'" mode="modal" size="small" @close="reviewVisible = false">
      <div class="aaql-form">
        <AppFormItem :label="reviewAction === 'APPROVE' ? '复核结论（选填）' : '驳回原因'" :required="reviewAction === 'REJECT'">
          <AppTextarea v-model="reviewReason" :rows="3" :placeholder="reviewAction === 'REJECT' ? '≥5字，写审计' : '选填'" :disabled="rectSaving" />
        </AppFormItem>
        <AppInlineAlert v-if="rectFormError" type="danger" :description="rectFormError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="rectSaving" @click="reviewVisible = false">取消</AppButton>
        <AppButton :variant="reviewAction === 'APPROVE' ? 'primary' : 'danger'" :loading="rectSaving" @click="submitReview">确定</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="recConfirmVisible" :title="recConfirmTitle" :message="recConfirmMessage" :type="recConfirmKind === 'cancel' ? 'danger' : 'warning'" :submitting="recSaving" :confirm-disabled="!!pendingWrite" @confirm="onConfirmRecTransition" />

    <AppDrawer :visible="archiveEvidenceVisible" title="质量闭环证据" mode="modal" size="large" @close="archiveEvidenceVisible = false">
      <div v-if="archiveEvidence" class="aaql-detail">
        <section class="aaql-object-context"><div><span>原问题</span><h3>{{ archiveEvidence.sourceTitle }}</h3><p>{{ archiveEvidence.sourceTypeLabel }}</p></div><div><small>整改任务</small><strong>{{ archiveEvidence.rectTitle || '未形成整改任务' }}</strong></div><div><small>复核结论</small><strong>{{ archiveEvidence.conclusion || '待核对' }}</strong></div></section>
        <AppTimeline v-if="archiveEvidence.timeline?.length" :items="archiveEvidence.timeline" />
        <AppInlineAlert v-else type="info" description="当前闭环记录没有可展示的整改时间线；原问题状态与关闭时间仍来自正式记录。" />
      </div>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
/** 教学质量（/admin/academic-affairs/quality）：运行质量看板+报告导出 +
 *  01督导听课/02巡课记录/03教学检查/04教学事故（共用问题记录）+
 *  AA-231质量整改/AA-232整改跟进（共用整改任务，发起/跟进两视角）+
 *  AA-233质量归档（正式问题、整改过程、复核结论的只读证据链）。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppTextarea, AppSelect, AppRadioGroup, AppFormItem, AppInlineAlert, AppTimeline, AppDateTimePicker, AppQuickPhrases, AppDescriptionList, AppConfirmDialog, AppTermEntityPicker, AppCoursePicker, AppTeacherPicker, AppCollegePicker, AppPagination } from '@/components/common'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { academicAffairsApi, academicAffairsQualityApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'
import { currentUserFromToken } from '@/services/http/client'

const _REC_TYPE_META = {
  supervision: { type: 'SUPERVISION', label: '督导听课', primaryLabel: '新增听课记录', titleLabel: '课次', titlePlaceholder: '填写正式课次', teacherLabel: '教师', courseLabel: '课程', occurredLabel: '听课时间', descriptionLabel: '观察事实', descriptionPlaceholder: '如实记录课堂观察事实', conclusionLabel: '改进意见', conclusionPlaceholder: '填写具体改进意见', showTeacher: true, showCourse: true, showCollege: false, showLocation: true, showCategory: false },
  patrol: { type: 'PATROL', label: '巡课记录', primaryLabel: '新增巡课记录', titleLabel: '课次', titlePlaceholder: '填写巡查课次', teacherLabel: '巡查人', occurredLabel: '巡课日期', descriptionLabel: '问题事实', descriptionPlaceholder: '如实记录巡查发现', conclusionLabel: '处置建议', conclusionPlaceholder: '填写处置建议', showTeacher: true, showCourse: false, showCollege: false, showLocation: true, showCategory: false },
  inspection: { type: 'INSPECTION', label: '教学检查', primaryLabel: '发起检查记录', titleLabel: '检查范围', titlePlaceholder: '填写检查范围', teacherLabel: '涉及教师', courseLabel: '涉及课程', occurredLabel: '检查时间', categoryLabel: '检查项目', categoryPlaceholder: '填写检查项目', descriptionLabel: '发现事实', descriptionPlaceholder: '填写检查证据与发现事实', conclusionLabel: '结论', conclusionPlaceholder: '填写检查结论', showTeacher: false, showCourse: false, showCollege: true, showLocation: false, showCategory: true },
  incident: { type: 'INCIDENT', label: '教学事故', primaryLabel: '登记事故事实', titleLabel: '事故事实摘要', titlePlaceholder: '填写事故摘要', teacherLabel: '涉及教师', courseLabel: '课程', occurredLabel: '发生时间', categoryLabel: '事故类型 / 等级', categoryPlaceholder: '按学校现行制度填写，不由系统推定', descriptionLabel: '事实材料说明', descriptionPlaceholder: '如实说明事实与材料来源', conclusionLabel: '当前处理状态', conclusionPlaceholder: '填写当前处理状态', showTeacher: true, showCourse: true, showCollege: false, showLocation: true, showCategory: true }
}
const _REC_TYPE_KEYS = Object.keys(_REC_TYPE_META)
const _REC_STATUS_LABEL = { SUBMITTED: '待确认', CONFIRMED: '已确认', CLOSED: '已关闭' }
const _REC_STATUS_TYPE = { SUBMITTED: 'primary', CONFIRMED: 'warning', CLOSED: 'default' }
const _RECT_STATUS_LABEL = { PENDING: '待整改', IN_PROGRESS: '整改中', SUBMITTED: '待复核', CLOSED: '已关闭' }
const _RECT_STATUS_TYPE = { PENDING: 'primary', IN_PROGRESS: 'warning', SUBMITTED: 'processing', CLOSED: 'default' }
const _QUALITY_STAGES = ['记录问题', '指派整改', '执行跟进', '提交复核', '关闭归档']
const _PAGE_META = {
  dashboard: { title: '质量看板', subtitle: '从发现问题接续整改闭环' },
  supervision: { title: '督导听课', subtitle: '从真实课次记录，不用评价分替代事实' },
  patrol: { title: '巡课记录', subtitle: '问题可进入整改，但登记不等于已整改' },
  inspection: { title: '教学检查', subtitle: '检查证据与后续责任明确' },
  incident: { title: '教学事故', subtitle: '等级与处理由现行制度决定，不由页面硬编码处罚' },
  rectify: { title: '质量整改', subtitle: '任务必须有来源问题和责任人' },
  followUp: { title: '整改跟进', subtitle: '提交复核与复核通过分开' },
  archive: { title: '质量归档', subtitle: '可追溯原问题、过程与复核人' }
}

export default {
  name: 'AaQualityDashboardView',
  components: { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppButton, AppDrawer,
               AppTextInput, AppTextarea, AppSelect, AppRadioGroup, AppFormItem, AppInlineAlert,
               AppTimeline, AppDateTimePicker, AppQuickPhrases, AppDescriptionList, AppConfirmDialog, AppTermEntityPicker,
               AppCoursePicker, AppTeacherPicker, AppCollegePicker, AppPagination },
  data() {
    return {
      alive: true,
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      tab: 'dashboard', panelSeq: 0, detailSeq: 0, writeSeq: 0, panelError: '',
      actionNotice: '', actionReceipt: null, pendingWrite: null,
      tabs: [
        { key: 'dashboard', label: '运行质量看板' },
        { key: 'supervision', label: '督导听课' },
        { key: 'patrol', label: '巡课记录' },
        { key: 'inspection', label: '教学检查' },
        { key: 'incident', label: '教学事故' },
        { key: 'rectify', label: '质量整改' },
        { key: 'followUp', label: '整改跟进' },
        { key: 'archive', label: '质量归档' }
      ],
      // dashboard
      loading: true, error: '', dashboardNotice: '', indicators: [], reports: [], overviewRecordRows: [], overviewRectRows: [],
      overviewColumns: [{ key: 'title', title: '问题' }, { key: 'sourceType', title: '来源类型' }, { key: 'responsible', title: '责任部门 / 人' }, { key: 'deadline', title: '整改期限' }, { key: 'status', title: '状态' }, { key: 'ops', title: '办理入口', width: '100px' }],
      reportColumns: [{ key: 'operator', title: '导出人' }, { key: 'roleName', title: '角色' }, { key: 'detail', title: '用途' }, { key: 'occurredAt', title: '时间' }],
      exportVisible: false, exportPurpose: '', exportError: '', exporting: false,
      // 问题记录（01/02/03/04）
      recLoading: false, recRows: [], recStatusFilter: '', recPagination: { page: 1, pageSize: 20, total: 0 },
      recStatusOptions: [{ label: '全部状态', value: '' }, { label: '待确认', value: 'SUBMITTED' }, { label: '已确认', value: 'CONFIRMED' }, { label: '已关闭', value: 'CLOSED' }],
      recColumns: [{ key: 'title', title: '标题' }, { key: 'teacherName', title: '教师' }, { key: 'courseName', title: '课程' },
                  { key: 'conclusion', title: '结论' }, { key: 'status', title: '状态' }, { key: 'needRectify', title: '' }, { key: 'ops', title: '操作' }],
      recCreateVisible: false, recForm: {}, recFormError: '', recSaving: false,
      recDetailVisible: false, recCurrent: null, recConfirmVisible: false, recConfirmKind: '', recConfirmTarget: null, recConfirmTitle: '', recConfirmMessage: '',
      // 整改任务（05/06）
      rectLoading: false, rectRows: [], rectStatusFilter: '', rectPartial: '', rectPagination: { page: 1, pageSize: 20, total: 0 },
      rectStatusOptions: [{ label: '全部状态', value: '' }, { label: '待整改', value: 'PENDING' }, { label: '整改中', value: 'IN_PROGRESS' }, { label: '待复核', value: 'SUBMITTED' }, { label: '已关闭', value: 'CLOSED' }],
      rectColumns: [{ key: 'title', title: '标题' }, { key: 'sourceTitle', title: '来源' }, { key: 'responsibleName', title: '责任人' },
                   { key: 'deadline', title: '期限' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }],
      rectCreateVisible: false, rectForm: {}, rectFormError: '', rectSaving: false, rectSourceRecord: null, rectSourceRecordId: '', rectSourceRecords: [],
      rectDetailVisible: false, rectCurrent: null, detailLoading: false, detailError: '',
      rectNoteVisible: false, rectNoteMode: '', rectNoteText: '', rectNoteTargetId: '', rectNoteTargetSnapshot: null,
      reviewVisible: false, reviewAction: '', reviewReason: '', reviewTargetId: '', reviewTargetSnapshot: null,
      // 归档
      archiveLoading: false, archiveData: {}, archiveTermId: '', archiveExporting: false, archivePartial: '', archiveRows: [],
      archiveColumns: [{ key: 'source', title: '问题来源' }, { key: 'rectification', title: '整改任务' }, { key: 'conclusion', title: '复核结论' }, { key: 'closedAt', title: '关闭时间' }, { key: 'archiveStatus', title: '归档记录' }, { key: 'ops', title: '办理入口', width: '110px' }],
      archiveEvidenceVisible: false, archiveEvidence: null
    }
  },
  computed: {
    identityKey() { return JSON.stringify([currentUserFromToken(), this.ctx]) },
    pageMeta() { return _PAGE_META[this.tab] || _PAGE_META.dashboard },
    qualityStages() { return _QUALITY_STAGES },
    isRecordTab() { return _REC_TYPE_KEYS.includes(this.tab) },
    isRectTab() { return this.tab === 'rectify' || this.tab === 'followUp' },
    queuePagination() { return this.isRecordTab ? this.recPagination : this.rectPagination },
    recMeta() { return _REC_TYPE_META[this.tab] || {} },
    recordTypeKeys() { return _REC_TYPE_KEYS.map((k) => _REC_TYPE_META[k].type) },
    writeLocked() { return this.recSaving || this.rectSaving || this.exporting || this.archiveExporting || !!this.pendingWrite },
    recordSourceReady() {
      if (this.tab === 'supervision') return !!this.recForm.courseId && !!this.recForm.teacherKey
      if (this.tab === 'incident') return !!this.recForm.courseId
      if (this.tab === 'inspection') return !!this.recForm.collegeId
      return !!this.recForm.occurredAt && !!this.recForm.teacherKey
    },
    recordStage() { return ({ SUBMITTED: 1, CONFIRMED: 2, CLOSED: 4 })[this.recCurrent?.status] ?? 0 },
    overviewRows() {
      const records = this.overviewRecordRows.filter(row => row.status !== 'CLOSED').map(row => ({ ...row, objectKey: `record:${row.recordId}`, objectType: 'record', title: row.title, sourceTypeLabel: this.recTypeLabel(row.recordType), responsible: row.teacherName || row.recorderName || '质量责任岗', deadline: null, statusLabel: this.recStatusLabel(row.status), statusType: this.recStatusType(row.status), targetTab: Object.keys(_REC_TYPE_META).find(key => _REC_TYPE_META[key].type === row.recordType) || 'inspection' }))
      const rects = this.overviewRectRows.filter(row => row.status !== 'CLOSED').map(row => ({ ...row, objectKey: `rect:${row.rectId}`, objectType: 'rect', title: row.title, sourceTypeLabel: row.sourceTitle ? this.recTypeLabel(row.sourceType) : '质量整改', responsible: row.responsibleName || '整改责任人待明确', statusLabel: this.rectStatusLabel(row), statusType: this.rectStatusType(row), targetTab: row.status === 'PENDING' ? 'rectify' : 'followUp' }))
      return [...rects, ...records].slice(0, 20)
    },
    overviewMetrics() {
      const user = currentUserFromToken() || {}, keys = new Set([user.userId, user.loginName, user.realName].filter(Boolean).map(String))
      const records = this.overviewRecordRows, rects = this.overviewRectRows
      return [
        { key: 'start', label: '待我启动', value: records.filter(row => row.status === 'SUBMITTED').length, note: '待确认问题记录' },
        { key: 'todo', label: '待我办理', value: rects.filter(row => ['PENDING','IN_PROGRESS','SUBMITTED'].includes(row.status)).length, note: '真实受理职责演练' },
        { key: 'mine', label: '我发起的', value: [...records.filter(row => keys.has(String(row.recorderKey))), ...rects.filter(row => keys.has(String(row.initiatorKey)))].length, note: '已交下一岗位' },
        { key: 'due', label: '即将到期', value: rects.filter(row => row.overdue && row.status !== 'CLOSED').length, note: '仍有明确处理责任' }
      ]
    },
    rectLanes() {
      return [
        { key: 'pending', label: '待领取 / 待整改', rows: this.displayRectRows.filter(row => row.status === 'PENDING') },
        { key: 'working', label: '处理中 / 待复核', rows: this.displayRectRows.filter(row => ['IN_PROGRESS','SUBMITTED'].includes(row.status)) },
        { key: 'closed', label: '已关闭', rows: this.displayRectRows.filter(row => row.status === 'CLOSED') }
      ]
    },
    rectSourceOptions() { return this.rectSourceRecords.map(row => ({ value: String(row.recordId), label: `${this.recTypeLabel(row.recordType)} · ${row.title}` })) },
    /** 跟进视角（06）未显式选状态时默认隐藏已关闭，并把逾期任务排到最前；发起视角（05）显示全部。 */
    displayRectRows() {
      let rows = this.rectRows
      if (this.tab === 'followUp' && !this.rectStatusFilter) {
        rows = rows.filter((r) => r.status !== 'CLOSED')
      }
      if (this.tab === 'followUp') {
        rows = [...rows].sort((a, b) => (b.overdue === a.overdue ? 0 : b.overdue ? 1 : -1))
      }
      return rows
    },
    /** 记录详情键值 → AppDescriptionList items（仅展示层映射，数据取自 recCurrent，不改数据流）。 */
    recDescItems() {
      const r = this.recCurrent
      if (!r) return []
      const items = [
        { label: '类型', value: this.recTypeLabel(r.recordType) },
        { label: '标题', value: r.title },
        { key: 'status', label: '状态', value: '' },
        { label: '教师', value: r.teacherName || '—' },
        { label: '课程', value: r.courseName || '—' },
        { label: '发生时间', value: this.fmt(r.occurredAt) || '—' },
        { label: '地点', value: r.location || '—' },
        { label: '分类/等级', value: r.category || '—' }
      ]
      if (r.score != null) items.push({ label: '评分', value: r.score })
      items.push({ label: '结论', value: r.conclusion || '—' })
      items.push({ label: '详细描述', value: r.description || '—', span: 2 })
      if (r.handlingNote) items.push({ label: '处理意见', value: r.handlingNote, span: 2 })
      items.push({ label: '记录人', value: r.recorderName || '—' })
      if (r.confirmedByName) items.push({ label: '确认人', value: `${r.confirmedByName}（${this.fmt(r.confirmedAt)}）` })
      return items
    },
    /** 整改任务详情键值 → AppDescriptionList items（status/deadline 用具名插槽保留标签与逾期红色）。 */
    rectDescItems() {
      const r = this.rectCurrent
      if (!r) return []
      const items = [
        { label: '标题', value: r.title },
        { key: 'status', label: '状态', value: '' }
      ]
      if (r.sourceTitle) items.push({ label: '来源记录', value: `${r.sourceTitle}（${this.recTypeLabel(r.sourceType)}）` })
      items.push({ label: '整改要求', value: r.requirement, span: 2 })
      items.push({ label: '责任人', value: r.responsibleName || '—' })
      items.push({ key: 'deadline', label: '期限', value: '' })
      if (r.resultNote) items.push({ label: '复核结论', value: r.resultNote, span: 2 })
      return items
    },
    /** 整改详情跟进时间线：progressLog[{time,operator,action,note}] → AppTimeline items。 */
    rectTimelineItems() {
      return this.timelineFromLog((this.rectCurrent && this.rectCurrent.progressLog) || [])
    }
  },
  watch: { identityKey() { this.resetScope(); this.afterTabLoad() } },
  beforeUnmount() { this.alive = false; this.panelSeq++; this.detailSeq++; this.writeSeq++ },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    else { this.loading = false; this.error = this.failureText(c, '当前教务身份与数据范围读取失败。'); return }
    this.$watch(
      () => this.$route?.fullPath,
      () => {
        const value = this.$route?.query?.tab
        const next = value && this.tabs.some((item) => item.key === value) ? value : 'dashboard'
        const changed = next !== this.tab
        this.tab = next
        this.afterTabLoad(changed)
      },
      { immediate: true }
    )
  },
  methods: {
    failureText(result, fallback = '操作失败，请重试。') {
      const code = [result?.status, result?.statusCode, result?.code, result?.bizCode].join(' ')
      if (/403|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN/.test(code)) return '当前身份无权读取或办理此质量对象。'
      if (/409|CONFLICT/.test(code)) return '对象状态已经变化，请重新读取后办理。'
      if (/422|VALIDATION/.test(code)) return result?.message || '提交内容不符合当前业务规则。'
      return result?.message || fallback
    },
    denied(result) { return /403|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN/.test([result?.status, result?.statusCode, result?.code, result?.bizCode].join(' ')) },
    explicitFailure(result) { return /403|404|409|422|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN|NOT_FOUND|CONFLICT|VALIDATION/.test([result?.status, result?.statusCode, result?.code, result?.bizCode].join(' ')) },
    safeId(value) { const id = String(value ?? '').trim(); return /^[1-9]\d*$/.test(id) ? id : '' },
    resetScope() {
      this.recPagination.total = 0; this.rectPagination.total = 0
      this.panelSeq++; this.detailSeq++; this.writeSeq++; this.recRows = []; this.rectRows = []; this.rectPartial = ''; this.overviewRecordRows = []; this.overviewRectRows = []
      this.recCurrent = null; this.rectCurrent = null; this.archiveRows = []; this.archiveEvidence = null
      this.recDetailVisible = false; this.recConfirmVisible = false; this.recConfirmTarget = null; this.rectDetailVisible = false; this.archiveEvidenceVisible = false
      this.rectNoteVisible = false; this.reviewVisible = false; this.pendingWrite = null; this.actionNotice = ''; this.actionReceipt = null
      this.recSaving = false; this.rectSaving = false; this.exporting = false; this.archiveExporting = false
    },
    resetRecForm() { this.recForm = { needRectify: false }; this.recFormError = ''; this.recCreateVisible = true },
    pickedEntity(value, items) { const item = items?.[0], raw = item?.raw || item || {}; return { id: String(value || ''), label: String(raw.courseName || raw.name || raw.realName || raw.teacherName || item?.label || '') } },
    onCoursePicked(value, items) { const picked = this.pickedEntity(value, items); this.recForm.courseId = picked.id; this.recForm.courseName = picked.label },
    onTeacherPicked(value, items) { const picked = this.pickedEntity(value, items); this.recForm.teacherKey = picked.id; this.recForm.teacherName = picked.label },
    onResponsiblePicked(value, items) { const picked = this.pickedEntity(value, items); this.rectForm.responsibleKey = picked.id; this.rectForm.responsibleName = picked.label },
    onPickPurpose(text) {
      const el = this.$refs.purposeInput && this.$refs.purposeInput.$refs.input
      const { value, selStart, selEnd } = insertAtCursor(el, this.exportPurpose, text)
      this.exportPurpose = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    fmt(s) { return s ? String(s).replace('T', ' ').slice(0, 16) : '' },
    recTypeLabel(rt) { const m = Object.values(_REC_TYPE_META).find((x) => x.type === rt); return m ? m.label : rt },
    recStatusLabel(s) { return _REC_STATUS_LABEL[s] || (s ? '状态待确认' : '—') },
    recStatusType(s) { return _REC_STATUS_TYPE[s] || 'default' },
    rectStatusLabel(r) { return r.overdue && r.status !== 'CLOSED' ? '已逾期' : (_RECT_STATUS_LABEL[r.status] || r.status) },
    rectStatusType(r) { return r.overdue && r.status !== 'CLOSED' ? 'danger' : (_RECT_STATUS_TYPE[r.status] || 'default') },
    timelineFromLog(log = []) {
      const actionLabel = { CREATE: '发起整改', PROGRESS: '记录跟进', SUBMIT: '提交复核', APPROVE: '复核通过', REJECT: '复核驳回' }
      const actionType = { CREATE: 'primary', PROGRESS: 'processing', SUBMIT: 'warning', APPROVE: 'success', REJECT: 'danger' }
      return (Array.isArray(log) ? log : []).map((item) => ({
        time: item.time ? String(item.time).replace('T', ' ').slice(0, 19) : '',
        title: actionLabel[item.action] || item.action || '过程记录',
        operator: item.operator || '操作人待核对',
        description: item.note || '未提供说明',
        type: actionType[item.action] || 'default'
      }))
    },
    updateRecColumns() {
      this.recColumns = [{ key: 'title', title: this.recMeta.titleLabel || '对象' }, { key: 'teacherName', title: this.recMeta.teacherLabel || '责任人' }, { key: 'courseName', title: this.recMeta.courseLabel || '课程' }, { key: 'conclusion', title: this.recMeta.conclusionLabel || '结论' }, { key: 'status', title: '状态' }, { key: 'needRectify', title: '' }, { key: 'ops', title: '操作' }]
    },
    routeQuery(patch = {}, remove = []) { const query = { ...this.$route.query, ...patch }; remove.forEach(key => delete query[key]); return query },
    switchTab(k) {
      if (k === this.tab) return
      const query = this.$route?.query?.returnToken ? { returnToken: this.$route.query.returnToken } : {}
      if (k !== 'dashboard') query.tab = k
      this.$router.push({ path: this.$route.path, query })
    },
    afterTabLoad(tabChanged = false) {
      const page = Number(this.$route?.query?.page || 1)
      this.recPagination.page = this.rectPagination.page = Number.isSafeInteger(page) && page > 0 ? page : 1
      this.panelSeq++; this.detailSeq++; this.panelError = ''; this.detailError = ''; this.recDetailVisible = false; this.rectDetailVisible = false
      if (tabChanged) { this.pendingWrite = null; this.actionNotice = ''; this.actionReceipt = null; this.recConfirmVisible = false; this.recConfirmTarget = null; this.rectCurrent = null; this.recCurrent = null }
      if (this.tab === 'dashboard') this.load()
      else if (this.isRecordTab) { this.updateRecColumns(); if (tabChanged || !Object.keys(this.recForm).length) this.resetRecForm(); this.loadRecords() }
      else if (this.isRectTab) this.loadRectifications()
      else if (this.tab === 'archive') this.loadArchive()
    },
    openOverviewItem(row) {
      const query = { tab: row.targetTab }
      if (row.objectType === 'record') query.recordId = String(row.recordId)
      else query.rectId = String(row.rectId)
      if (this.$route?.query?.returnToken) query.returnToken = this.$route.query.returnToken
      this.$router.push({ path: this.$route.path, query })
    },
    // ── 看板 ──
    async load() {
      const seq = ++this.panelSeq, identity = this.identityKey, tab = this.tab
      const current = () => this.alive && seq === this.panelSeq && identity === this.identityKey && tab === this.tab
      this.loading = true; this.error = ''; this.dashboardNotice = ''; this.indicators = []; this.reports = []; this.overviewRecordRows = []; this.overviewRectRows = []
      try {
        const settled = await Promise.allSettled([api.dashboard(), api.reports({ pageSize: 50 }), api.listRecords({ page: 1, pageSize: 20 }), api.listRectifications({ page: 1, pageSize: 20 })])
        if (!current()) return
        const results = settled.map(item => item.status === 'fulfilled' ? item.value : item.reason)
        const denied = results.find(result => this.denied(result))
        if (denied) { this.resetScope(); this.error = this.failureText(denied); return }
        const [dashboard, reports, records, rects] = results
        if (dashboard?.code === 0 && Array.isArray(dashboard.data?.indicators)) this.indicators = dashboard.data.indicators
        if (reports?.code === 0 && Array.isArray(reports.data?.list)) this.reports = reports.data.list
        if (records?.code === 0 && Array.isArray(records.data?.list)) this.overviewRecordRows = records.data.list
        if (rects?.code === 0 && Array.isArray(rects.data?.list)) this.overviewRectRows = rects.data.list
        const failed = [
          ['质量指标', dashboard?.code === 0 && Array.isArray(dashboard.data?.indicators) ? null : (dashboard?.code === 0 ? { code: 503001, message: '质量指标回执不完整' } : dashboard)],
          ['导出历史', reports?.code === 0 && Array.isArray(reports.data?.list) ? null : (reports?.code === 0 ? { code: 503001, message: '导出历史回执不完整' } : reports)],
          ['问题队列', records?.code === 0 && Array.isArray(records.data?.list) ? null : (records?.code === 0 ? { code: 503001, message: '问题队列回执不完整' } : records)],
          ['整改队列', rects?.code === 0 && Array.isArray(rects.data?.list) ? null : (rects?.code === 0 ? { code: 503001, message: '整改队列回执不完整' } : rects)]
        ].filter(([, result]) => result)
        if (failed.length === 4) this.error = failed.map(([label, result]) => `${label}：${this.failureText(result, '读取失败')}`).join('；')
        else if (failed.length) this.dashboardNotice = `部分数据暂不可用：${failed.map(([label, result]) => `${label}（${this.failureText(result, '读取失败')}）`).join('、')}。其余区域仍为正式接口结果。`
      } catch (result) { if (current()) this.error = this.failureText(result, '质量看板读取失败，请重试。') }
      finally { if (current()) this.loading = false }
    },
    openExport() { this.exportPurpose = ''; this.exportError = ''; this.exportVisible = true },
    async doExport() {
      if (!this.exportPurpose || this.exportPurpose.trim().length < 5) { this.exportError = '用途至少5字'; return }
      const identity = this.identityKey, purpose = this.exportPurpose.trim()
      this.exporting = true; this.exportError = ''
      try {
        const res = await api.exportReport({ purpose })
        if (!this.alive || identity !== this.identityKey) return
        if (res.code !== 0 || !(res.data instanceof Blob)) throw res
        this._download(res.data, 'academic_quality_report.xlsx')
        toast.success('已生成带审计水印的质量报告'); this.exportVisible = false; await this.load()
      } catch (result) { if (this.alive && identity === this.identityKey) this.exportError = this.failureText(result, '导出结果待核实，请检查下载记录后再试。') }
      finally { if (this.alive && identity === this.identityKey) this.exporting = false }
    },
    _download(blob, filename) {
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a'); a.href = url; a.download = filename; a.click()
      URL.revokeObjectURL(url)
    },
    // ── 01/02/03/04 问题记录 ──
    searchRecords() { this.onQueuePageChange({ page: 1 }) },
    searchRectifications() { this.onQueuePageChange({ page: 1 }) },
    onQueuePageChange({ page }) {
      if (this.writeLocked || !Number.isSafeInteger(page) || page < 1) return
      const query = this.routeQuery({ page: String(page) }, ['recordId', 'rectId'])
      if (String(this.$route.query.page || 1) === String(page) && !this.$route.query.recordId && !this.$route.query.rectId) this.afterTabLoad()
      else this.$router.replace({ query })
    },
    async loadRecords() {
      const seq = ++this.panelSeq, identity = this.identityKey, tab = this.tab, status = this.recStatusFilter, page = this.recPagination.page
      const current = () => this.alive && seq === this.panelSeq && identity === this.identityKey && tab === this.tab && status === this.recStatusFilter && page === this.recPagination.page
      this.recLoading = true; this.panelError = ''; this.recRows = []
      try {
        const res = await api.listRecords({ recordType: this.recMeta.type, status: status || undefined, page, pageSize: this.recPagination.pageSize })
        if (!current()) return
        if (res.code !== 0) throw res
        if (!Array.isArray(res.data?.list) || !Number.isSafeInteger(res.data.total) || res.data.total < 0) throw { code: 503001, message: '质量记录分页回执不完整，不能按空列表办理。' }
        this.recRows = res.data.list
        this.recPagination.total = res.data.total
        const routeId = this.safeId(this.$route?.query?.recordId)
        if (this.$route?.query?.recordId && !routeId) throw { code: 422, message: '质量记录参数无效，请从当前列表重新选择。' }
        if (routeId) {
          const target = this.recRows.find(row => String(row.recordId) === routeId)
          if (!target) throw { code: 404, message: '指定质量记录不在当前范围或当前页，请返回来源队列。' }
          await this.loadRecDetail(target, true)
        }
      } catch (error) { if (current()) { if (this.denied(error)) this.recRows = []; this.panelError = this.failureText(error, '问题记录加载失败，请重试。') } }
      finally { if (current()) this.recLoading = false }
    },
    openRecCreate() { this.resetRecForm() },
    async submitRecCreate() {
      if (this.pendingWrite || this.recSaving) return
      if (!this.recordSourceReady) { this.recFormError = '请先选择或填写当前页面要求的正式来源对象。'; return }
      if (!String(this.recForm.title || '').trim()) { this.recFormError = `${this.recMeta.titleLabel}必填`; return }
      if (!String(this.recForm.description || '').trim()) { this.recFormError = `${this.recMeta.descriptionLabel}必填`; return }
      const body = Object.freeze({ recordType: this.recMeta.type, ...this.recForm, title: this.recForm.title.trim(), description: this.recForm.description.trim() })
      const command = { kind: 'record-create', identity: this.identityKey, tab: this.tab, body, objectId: '', sent: false }
      this.recSaving = true; this.recFormError = ''; this.pendingWrite = command; this.actionReceipt = null; this.actionNotice = `正在提交${this.recMeta.label}记录；未核对前请勿重复提交。`
      try {
        let res
        try { command.sent = true; res = await api.createRecord(body) } catch (error) { res = error }
        if (!this.currentWrite(command)) return
        if (res?.code !== 0 && this.explicitFailure(res)) { this.pendingWrite = null; this.actionNotice = ''; throw res }
        command.objectId = this.safeId(res?.data?.recordId)
        if (res?.code === 0 && command.objectId) {
          const fresh = await api.getRecord(command.objectId)
          if (!this.currentWrite(command)) return
          if (fresh?.code === 0 && String(fresh.data?.recordId) === command.objectId && fresh.data?.recordType === body.recordType && fresh.data?.title === body.title) {
            this.pendingWrite = null; this.actionReceipt = { verified: true, objectLabel: `${this.recMeta.label} #${command.objectId}`, next: body.needRectify ? '质量责任岗确认后指派整改' : '质量责任岗确认记录' }; this.actionNotice = `正式记录状态：${this.recStatusLabel(fresh.data.status)}。`; toast.success('已回读正式质量记录'); this.resetRecForm(); await this.loadRecords(); return
          }
        }
        this.actionNotice = '提交结果待核实，当前回读不足以证明正式记录已经建立；请勿重复提交。'
      } catch (error) { if (this.currentWrite(command) || !this.pendingWrite) this.recFormError = this.failureText(error, '记录尚未确认，请保留表单并重试读取。') }
      finally { if (this.alive && command.identity === this.identityKey) this.recSaving = false }
    },
    async viewRecDetail(row) {
      const id = this.safeId(row?.recordId)
      if (!id) return
      if (String(this.$route?.query?.recordId || '') !== id) return this.$router.push({ path: this.$route.path, query: this.routeQuery({ recordId: id }, ['rectId']) })
      return this.loadRecDetail(row, true)
    },
    async loadRecDetail(row, openDrawer = true) {
      const seq = ++this.detailSeq, identity = this.identityKey, id = this.safeId(row?.recordId)
      this.recCurrent = null; this.recDetailVisible = false
      try {
        const res = await api.getRecord(id)
        if (!this.alive || seq !== this.detailSeq || identity !== this.identityKey) return
        if (res.code !== 0 || String(res.data?.recordId) !== id || res.data?.recordType !== this.recMeta.type) throw res?.code !== 0 ? res : { code: 409 }
        this.recCurrent = res.data; this.recDetailVisible = openDrawer
      } catch (error) { if (this.alive && seq === this.detailSeq && identity === this.identityKey) toast.error(this.failureText(error, '记录详情读取失败。')) }
    },
    closeRecDetail() {
      this.recDetailVisible = false; this.recCurrent = null
      if (this.$route?.query?.recordId) this.$router.replace({ path: this.$route.path, query: this.routeQuery({}, ['recordId']) })
    },
    recordSignature(row) { return JSON.stringify([String(row?.recordId || ''), row?.recordType, row?.status, row?.title, row?.createdAt]) },
    askRecTransition(kind, row) {
      if (this.writeLocked) return
      const snapshot = Object.freeze({ ...row }), id = this.safeId(snapshot.recordId)
      if (!id) return
      const meta = {
        confirm: ['确认质量记录', `确认对象「${snapshot.title}」#${id}？确认后由质量责任岗继续关闭或指派整改。`],
        close: ['关闭质量记录', `确认关闭对象「${snapshot.title}」#${id}？关闭后进入质量归档。`],
        cancel: ['撤销质量记录', `确认撤销对象「${snapshot.title}」#${id}？请先核对当前对象编号和标题。`]
      }[kind]
      if (!meta) return
      this.recConfirmKind = kind; this.recConfirmTarget = snapshot; this.recConfirmTitle = meta[0]; this.recConfirmMessage = meta[1]; this.recConfirmVisible = true
    },
    async onConfirmRecTransition() {
      const kind = this.recConfirmKind, target = this.recConfirmTarget
      if (!target || this.pendingWrite) return
      const completed = kind === 'confirm' ? await this.confirmRec(target) : kind === 'close' ? await this.closeRec(target) : await this.cancelRec(target)
      if (completed) { this.recConfirmVisible = false; this.recConfirmTarget = null }
    },
    currentWrite(command) { return this.alive && this.pendingWrite === command && command.identity === this.identityKey && command.tab === this.tab },
    async runRecordTransition(kind, row, beforeStatus, afterStatus, send) {
      if (this.pendingWrite || this.recSaving) return false
      const snapshot = Object.freeze({ ...row }), id = this.safeId(snapshot.recordId)
      const command = { kind, identity: this.identityKey, tab: this.tab, objectId: id, snapshot, expectedAfter: afterStatus, sent: false }
      this.recSaving = true; this.actionReceipt = null; this.actionNotice = '正在核对并提交当前质量记录，请勿切换对象或重复操作。'
      try {
        const before = await api.getRecord(id)
        if (!this.alive || command.identity !== this.identityKey || command.tab !== this.tab) return false
        if (before?.code !== 0 || before.data?.status !== beforeStatus || this.recordSignature(before.data) !== this.recordSignature(snapshot)) throw before?.code !== 0 ? before : { code: 409 }
        this.pendingWrite = command
        let result
        try { command.sent = true; result = await send(id) } catch (error) { result = error }
        if (!this.currentWrite(command)) return false
        if (result?.code !== 0 && this.explicitFailure(result)) { this.pendingWrite = null; this.actionNotice = ''; throw result }
        if (kind === 'record-cancel' && result?.code === 0 && result.data?.cancelled === true && String(result.data?.recordId) === id) {
          this.pendingWrite = null; this.actionReceipt = { verified: true, objectLabel: `${snapshot.title} · #${id}`, next: '返回原质量记录队列' }; this.actionNotice = '正式回执确认记录已撤销。'; toast.success('记录已撤销'); await this.loadRecords(); return true
        }
        const after = await api.getRecord(id)
        if (!this.currentWrite(command)) return false
        if (result?.code === 0 && after?.code === 0 && String(after.data?.recordId) === id && after.data?.status === afterStatus) {
          this.pendingWrite = null; this.actionReceipt = { verified: true, objectLabel: `${snapshot.title} · #${id}`, next: afterStatus === 'CONFIRMED' ? (snapshot.needRectify ? '指派整改责任人' : '质量责任岗关闭记录') : '质量归档' }; this.actionNotice = `正式状态：${this.recStatusLabel(afterStatus)}。`; toast.success('已回读正式质量记录'); await this.loadRecords(); return true
        }
        this.actionNotice = '操作结果待核实，当前读取不足以证明本次命令完成；请勿重复操作。'; return false
      } catch (error) { if (this.alive && command.identity === this.identityKey) { if (!command.sent) this.actionNotice = ''; if (this.denied(error)) this.recRows = []; toast.error(this.failureText(error, '本次操作未确认。')) } return false }
      finally { if (this.alive && command.identity === this.identityKey) this.recSaving = false }
    },
    confirmRec(row) { return this.runRecordTransition('record-confirm', row, 'SUBMITTED', 'CONFIRMED', id => api.confirmRecord(id)) },
    closeRec(row) { return this.runRecordTransition('record-close', row, 'CONFIRMED', 'CLOSED', id => api.closeRecord(id)) },
    cancelRec(row) { return this.runRecordTransition('record-cancel', row, 'SUBMITTED', null, id => api.cancelRecord(id)) },
    async verifyPendingWrite() {
      const command = this.pendingWrite
      if (!command || this.recSaving || this.rectSaving) return
      if (!command.objectId) {
        this.actionNotice = '服务端未返回可核对的业务对象编号，当前不能证明命令完成，也不会自动重放。请保留来源对象并由业务审计记录核对。'
        return
      }
      const isRecord = command.kind.startsWith('record-')
      if (command.kind === 'record-cancel') {
        this.actionNotice = '撤销命令没有可安全区分“已撤销”和“当前不可读”的只读回执，系统不会自动重放；请从原队列或审计记录核对。'
        return
      }
      this.recSaving = isRecord; this.rectSaving = !isRecord
      try {
        const res = isRecord ? await api.getRecord(command.objectId) : await api.getRectification(command.objectId)
        if (!this.currentWrite(command)) return
        let verified = false, next = '返回原质量队列'
        if (command.kind === 'record-create') verified = res?.code === 0 && String(res.data?.recordId) === command.objectId && res.data?.recordType === command.body?.recordType && res.data?.title === command.body?.title
        else if (command.kind.startsWith('record-')) { verified = res?.code === 0 && String(res.data?.recordId) === command.objectId && res.data?.status === command.expectedAfter; next = command.expectedAfter === 'CONFIRMED' ? '质量责任岗继续关闭或指派整改' : '质量归档岗' }
        else if (command.kind === 'rect-create') { verified = res?.code === 0 && String(res.data?.rectId) === command.objectId && String(res.data?.sourceRecordId) === command.sourceId && res.data?.title === command.body?.title; next = res?.data?.responsibleName || '整改责任人' }
        else {
          verified = res?.code === 0 && String(res.data?.rectId) === command.objectId && res.data?.status === command.expectedAfter
          if (command.kind === 'rect-progress' || command.kind === 'rect-submit') {
            const action = command.kind === 'rect-progress' ? 'PROGRESS' : 'SUBMIT'
            verified = verified && Array.isArray(res.data?.progressLog) && res.data.progressLog.some(item => item.action === action && String(item.note || '').trim() === command.note)
          }
          next = command.expectedAfter === 'CLOSED' ? '质量归档岗' : command.expectedAfter === 'SUBMITTED' ? '质量复核岗' : (res?.data?.responsibleName || '整改责任人')
        }
        if (!verified) { this.actionNotice = res?.code === 0 ? '只读核对仍未找到与原命令一致的正式状态；请勿重复提交。' : this.failureText(res, '只读核对失败，请稍后再次核对。'); return }
        this.pendingWrite = null; this.actionReceipt = { verified: true, objectLabel: `${res.data?.title || command.snapshot?.title || '质量对象'} · #${command.objectId}`, next }; this.actionNotice = `已只读核对正式状态：${isRecord ? this.recStatusLabel(res.data.status) : this.rectStatusLabel(res.data)}。`; toast.success('已核对原操作，无重复提交')
        if (this.isRecordTab) await this.loadRecords()
        else if (this.isRectTab) await this.loadRectifications()
      } catch (error) { if (this.currentWrite(command)) this.actionNotice = this.failureText(error, '只读核对失败，原命令不会自动重放。') }
      finally { if (this.alive && command.identity === this.identityKey) { this.recSaving = false; this.rectSaving = false } }
    },
    // ── AA-231/AA-232 质量整改与跟进 ──
    async loadRectifications() {
      const seq = ++this.panelSeq, identity = this.identityKey, tab = this.tab, status = this.rectStatusFilter, page = this.rectPagination.page
      const current = () => this.alive && seq === this.panelSeq && identity === this.identityKey && tab === this.tab && status === this.rectStatusFilter && page === this.rectPagination.page
      this.rectLoading = true; this.panelError = ''; this.rectPartial = ''; this.rectRows = []; this.rectSourceRecords = []
      try {
        const settled = await Promise.allSettled([
          api.listRectifications({ status: status || undefined, page, pageSize: this.rectPagination.pageSize }),
          api.listRecords({ status: 'CONFIRMED', page: 1, pageSize: 100 })
        ])
        if (!current()) return
        const [rectResult, sourceResult] = settled.map(item => item.status === 'fulfilled' ? item.value : item.reason)
        const denied = [rectResult, sourceResult].find(result => this.denied(result))
        if (denied) { this.rectRows = []; this.rectSourceRecords = []; throw denied }
        if (rectResult?.code !== 0 || !Array.isArray(rectResult.data?.list) || !Number.isSafeInteger(rectResult.data.total) || rectResult.data.total < 0) throw rectResult?.code !== 0 ? rectResult : { code: 503001, message: '整改任务分页回执不完整，不能按空列表办理。' }
        this.rectRows = rectResult.data.list
        this.rectPagination.total = rectResult.data.total
        if (sourceResult?.code === 0 && Array.isArray(sourceResult.data?.list)) this.rectSourceRecords = sourceResult.data.list
        else if (tab === 'rectify') this.rectPartial = `整改任务已读取，但来源问题暂不可选：${this.failureText(sourceResult, '来源问题读取失败')}。`
        const routeId = this.safeId(this.$route?.query?.rectId)
        if (this.$route?.query?.rectId && !routeId) throw { code: 422, message: '整改任务参数无效，请从当前队列重新选择。' }
        const target = routeId ? this.rectRows.find(row => String(row.rectId) === routeId) : (tab === 'followUp' ? this.displayRectRows[0] : null)
        if (routeId && !target) throw { code: 404, message: '指定整改任务不在当前范围或当前页，请返回来源队列。' }
        if (target) await this.loadRectDetail(target, tab === 'rectify')
      } catch (error) { if (current()) { if (this.denied(error)) { this.rectRows = []; this.rectSourceRecords = [] }; this.panelError = this.failureText(error, '整改记录加载失败，请重试。') } }
      finally { if (current()) this.rectLoading = false }
    },
    openRectCreate() {
      this.rectSourceRecord = null; this.rectSourceRecordId = ''
      this.rectForm = {}
      this.rectFormError = ''
      this.rectCreateVisible = true
    },
    openRectifyFromRecord(row) {
      const snapshot = Object.freeze({ ...row })
      this.rectSourceRecord = snapshot; this.rectSourceRecordId = String(snapshot.recordId || '')
      this.rectForm = { title: `${snapshot.title} · 整改`, responsibleKey: snapshot.teacherKey || '', responsibleName: snapshot.teacherName || '' }
      this.rectFormError = ''
      this.rectCreateVisible = true
    },
    async submitRectCreate() {
      if (this.pendingWrite || this.rectSaving) return
      if (!this.rectForm.title || !this.rectForm.title.trim()) { this.rectFormError = '标题必填'; return }
      if (!this.rectForm.requirement || this.rectForm.requirement.trim().length < 5) { this.rectFormError = '整改要求必填且不少于5字'; return }
      const source = this.rectSourceRecord || this.rectSourceRecords.find(row => String(row.recordId) === String(this.rectSourceRecordId))
      const sourceId = this.safeId(source?.recordId)
      if (!sourceId) { this.rectFormError = '必须选择一条已确认的正式质量问题作为整改来源。'; return }
      const snapshot = Object.freeze({ ...source })
      const body = Object.freeze({
        title: this.rectForm.title.trim(), requirement: this.rectForm.requirement.trim(),
        responsibleKey: this.rectForm.responsibleKey || undefined,
        responsibleName: this.rectForm.responsibleName || undefined,
        deadline: this.rectForm.deadline || undefined
      })
      const command = { kind: 'rect-create', identity: this.identityKey, tab: this.tab, objectId: '', sourceId, snapshot, body, sent: false }
      this.rectSaving = true; this.rectFormError = ''; this.actionReceipt = null; this.actionNotice = '正在核对来源问题并发起整改；未核对前请勿重复提交。'
      try {
        const before = await api.getRecord(sourceId)
        if (!this.alive || command.identity !== this.identityKey || command.tab !== this.tab) return
        if (before?.code !== 0 || before.data?.status !== 'CONFIRMED' || this.recordSignature(before.data) !== this.recordSignature(snapshot)) throw before?.code !== 0 ? before : { code: 409 }
        this.pendingWrite = command
        let res
        try { command.sent = true; res = await api.rectifyFromRecord(sourceId, body) } catch (error) { res = error }
        if (!this.currentWrite(command)) return
        if (res?.code !== 0 && this.explicitFailure(res)) { this.pendingWrite = null; this.actionNotice = ''; throw res }
        command.objectId = this.safeId(res?.data?.rectId)
        if (res?.code === 0 && command.objectId) {
          const fresh = await api.getRectification(command.objectId)
          if (!this.currentWrite(command)) return
          if (fresh?.code === 0 && String(fresh.data?.rectId) === command.objectId && String(fresh.data?.sourceRecordId) === sourceId && fresh.data?.title === body.title) {
            this.pendingWrite = null; this.actionReceipt = { verified: true, objectLabel: `${body.title} · #${command.objectId}`, next: fresh.data?.responsibleName || '整改责任人' }; this.actionNotice = `正式整改状态：${this.rectStatusLabel(fresh.data)}。`; toast.success('已回读正式整改任务'); this.rectCreateVisible = false; await this.loadRectifications(); return
          }
        }
        this.actionNotice = '发起结果待核实，当前回读不足以证明整改任务已经建立；请勿重复提交。'
      } catch (error) { if (this.alive && command.identity === this.identityKey) { if (!command.sent) this.actionNotice = ''; this.rectFormError = this.failureText(error, '整改任务尚未确认，请保留表单并只读核对。') } }
      finally { if (this.alive && command.identity === this.identityKey) this.rectSaving = false }
    },
    async viewRectDetail(row) {
      const id = this.safeId(row?.rectId)
      if (!id) return
      if (String(this.$route?.query?.rectId || '') !== id) return this.$router.push({ path: this.$route.path, query: this.routeQuery({ rectId: id }, ['recordId']) })
      return this.loadRectDetail(row, true)
    },
    selectRect(row) {
      const id = this.safeId(row?.rectId)
      if (!id) return
      if (String(this.$route?.query?.rectId || '') === id) return this.loadRectDetail(row, false)
      return this.$router.push({ path: this.$route.path, query: this.routeQuery({ rectId: id }, ['recordId']) })
    },
    reloadRectCurrent() { const row = this.rectRows.find(item => String(item.rectId) === String(this.$route?.query?.rectId || this.rectCurrent?.rectId)); if (row) return this.loadRectDetail(row, this.tab === 'rectify') },
    async loadRectDetail(row, openDrawer = false) {
      const seq = ++this.detailSeq, identity = this.identityKey, id = this.safeId(row?.rectId), tab = this.tab
      this.detailLoading = true; this.detailError = ''; this.rectCurrent = null; this.rectDetailVisible = false
      try {
        const res = await api.getRectification(id)
        if (!this.alive || seq !== this.detailSeq || identity !== this.identityKey || tab !== this.tab) return
        if (res?.code !== 0 || String(res.data?.rectId) !== id) throw res?.code !== 0 ? res : { code: 409 }
        this.rectCurrent = res.data; this.rectDetailVisible = openDrawer
      } catch (error) { if (this.alive && seq === this.detailSeq && identity === this.identityKey) { this.detailError = this.failureText(error, '整改详情读取失败。'); if (openDrawer) toast.error(this.detailError) } }
      finally { if (this.alive && seq === this.detailSeq && identity === this.identityKey) this.detailLoading = false }
    },
    closeRectDetail() {
      this.rectDetailVisible = false
      if (this.tab !== 'followUp') this.rectCurrent = null
      if (this.$route?.query?.rectId && this.tab !== 'followUp') this.$router.replace({ path: this.$route.path, query: this.routeQuery({}, ['rectId']) })
    },
    continueRect(row) {
      const id = this.safeId(row?.rectId)
      if (!id) return
      const query = { tab: 'followUp', rectId: id }
      if (this.$route?.query?.returnToken) query.returnToken = this.$route.query.returnToken
      this.rectDetailVisible = false
      return this.$router.push({ path: this.$route.path, query })
    },
    returnToRectify(row) {
      const query = { tab: 'rectify', rectId: String(row?.rectId || '') }
      if (this.$route?.query?.returnToken) query.returnToken = this.$route.query.returnToken
      return this.$router.push({ path: this.$route.path, query })
    },
    rectSignature(row) { return JSON.stringify([String(row?.rectId || ''), String(row?.sourceRecordId || ''), row?.status, row?.title, row?.deadline, row?.responsibleKey, row?.updatedAt || row?.createdAt]) },
    openProgress(row) { const snapshot = Object.freeze({ ...row }); this.rectNoteMode = 'progress'; this.rectNoteTargetId = String(snapshot.rectId || ''); this.rectNoteTargetSnapshot = snapshot; this.rectNoteText = ''; this.rectFormError = ''; this.rectNoteVisible = true },
    openSubmitRect(row) { const snapshot = Object.freeze({ ...row }); this.rectNoteMode = 'submit'; this.rectNoteTargetId = String(snapshot.rectId || ''); this.rectNoteTargetSnapshot = snapshot; this.rectNoteText = ''; this.rectFormError = ''; this.rectNoteVisible = true },
    async submitRectNote() {
      if (this.pendingWrite || this.rectSaving) return
      if (!this.rectNoteText || this.rectNoteText.trim().length < 2) { this.rectFormError = '说明必填'; return }
      const snapshot = this.rectNoteTargetSnapshot, id = this.safeId(snapshot?.rectId), note = this.rectNoteText.trim(), mode = this.rectNoteMode
      if (!id || String(id) !== String(this.rectNoteTargetId)) { this.rectFormError = '当前整改对象已变化，请关闭弹窗后重新选择。'; return }
      const beforeStatus = snapshot.status, expectedAfter = mode === 'submit' ? 'SUBMITTED' : 'IN_PROGRESS'
      const command = { kind: mode === 'submit' ? 'rect-submit' : 'rect-progress', identity: this.identityKey, tab: this.tab, objectId: id, snapshot, note, expectedAfter, sent: false }
      this.rectSaving = true; this.rectFormError = ''; this.actionReceipt = null; this.actionNotice = '正在核对并提交当前整改对象；未核对前请勿重复提交。'
      try {
        const before = await api.getRectification(id)
        if (!this.alive || command.identity !== this.identityKey || command.tab !== this.tab) return
        if (before?.code !== 0 || before.data?.status !== beforeStatus || this.rectSignature(before.data) !== this.rectSignature(snapshot)) throw before?.code !== 0 ? before : { code: 409 }
        this.pendingWrite = command
        let res
        try { command.sent = true; res = mode === 'progress' ? await api.addProgress(id, note) : await api.submitRectification(id, note) } catch (error) { res = error }
        if (!this.currentWrite(command)) return
        if (res?.code !== 0 && this.explicitFailure(res)) { this.pendingWrite = null; this.actionNotice = ''; throw res }
        const after = await api.getRectification(id)
        if (!this.currentWrite(command)) return
        const log = Array.isArray(after?.data?.progressLog) ? after.data.progressLog : []
        const action = mode === 'progress' ? 'PROGRESS' : 'SUBMIT'
        const matchedLog = log.some(item => item.action === action && String(item.note || '').trim() === note)
        if (res?.code === 0 && after?.code === 0 && String(after.data?.rectId) === id && after.data?.status === expectedAfter && matchedLog) {
          this.pendingWrite = null; this.actionReceipt = { verified: true, objectLabel: `${snapshot.title} · #${id}`, next: mode === 'submit' ? '质量复核岗' : (after.data?.responsibleName || '整改责任人') }; this.actionNotice = `正式整改状态：${this.rectStatusLabel(after.data)}。`; toast.success(mode === 'submit' ? '已提交复核并回读状态' : '已记录进度并回读状态'); this.rectNoteVisible = false; await this.loadRectifications(); return
        }
        this.actionNotice = '操作结果待核实，当前读取不足以证明进度或提交复核已经入库；请勿重复提交。'
      } catch (error) { if (this.alive && command.identity === this.identityKey) { if (!command.sent) this.actionNotice = ''; this.rectFormError = this.failureText(error, '整改操作尚未确认，请保留说明并只读核对。') } }
      finally { if (this.alive && command.identity === this.identityKey) this.rectSaving = false }
    },
    openReview(row, action) { const snapshot = Object.freeze({ ...row }); this.reviewAction = action; this.reviewTargetId = String(snapshot.rectId || ''); this.reviewTargetSnapshot = snapshot; this.reviewReason = ''; this.rectFormError = ''; this.reviewVisible = true },
    async submitReview() {
      if (this.pendingWrite || this.rectSaving) return
      if (this.reviewAction === 'REJECT' && (!this.reviewReason || this.reviewReason.trim().length < 5)) { this.rectFormError = '驳回原因必填且不少于5字'; return }
      const snapshot = this.reviewTargetSnapshot, id = this.safeId(snapshot?.rectId), action = this.reviewAction, reason = this.reviewReason.trim()
      if (!id || String(id) !== String(this.reviewTargetId) || snapshot.status !== 'SUBMITTED') { this.rectFormError = '当前复核对象或状态已变化，请关闭弹窗后重新选择。'; return }
      const expectedAfter = action === 'APPROVE' ? 'CLOSED' : 'IN_PROGRESS'
      const command = { kind: action === 'APPROVE' ? 'rect-approve' : 'rect-reject', identity: this.identityKey, tab: this.tab, objectId: id, snapshot, reason, action, expectedAfter, sent: false }
      this.rectSaving = true; this.rectFormError = ''; this.actionReceipt = null; this.actionNotice = '正在核对并复核当前整改对象；未核对前请勿重复提交。'
      try {
        const before = await api.getRectification(id)
        if (!this.alive || command.identity !== this.identityKey || command.tab !== this.tab) return
        if (before?.code !== 0 || before.data?.status !== 'SUBMITTED' || this.rectSignature(before.data) !== this.rectSignature(snapshot)) throw before?.code !== 0 ? before : { code: 409 }
        this.pendingWrite = command
        let res
        try { command.sent = true; res = await api.reviewRectification(id, action, reason) } catch (error) { res = error }
        if (!this.currentWrite(command)) return
        if (res?.code !== 0 && this.explicitFailure(res)) { this.pendingWrite = null; this.actionNotice = ''; throw res }
        const after = await api.getRectification(id)
        if (!this.currentWrite(command)) return
        if (res?.code === 0 && after?.code === 0 && String(after.data?.rectId) === id && after.data?.status === expectedAfter) {
          this.pendingWrite = null; this.actionReceipt = { verified: true, objectLabel: `${snapshot.title} · #${id}`, next: action === 'APPROVE' ? '质量归档岗' : (after.data?.responsibleName || '整改责任人') }; this.actionNotice = `正式整改状态：${this.rectStatusLabel(after.data)}。`; toast.success(action === 'APPROVE' ? '复核通过并已关闭' : '已驳回至整改责任人'); this.reviewVisible = false; await this.loadRectifications(); return
        }
        this.actionNotice = '复核结果待核实，当前读取不足以证明状态已经迁移；请勿重复提交。'
      } catch (error) { if (this.alive && command.identity === this.identityKey) { if (!command.sent) this.actionNotice = ''; this.rectFormError = this.failureText(error, '整改复核尚未确认，请保留结论并只读核对。') } }
      finally { if (this.alive && command.identity === this.identityKey) this.rectSaving = false }
    },
    // ── AA-233 质量归档 ──
    async loadArchive() {
      const seq = ++this.panelSeq, identity = this.identityKey, termId = this.archiveTermId
      const current = () => this.alive && seq === this.panelSeq && identity === this.identityKey && termId === this.archiveTermId
      this.archiveLoading = true; this.panelError = ''; this.archivePartial = ''; this.archiveData = {}; this.archiveRows = []
      try {
        const params = { termId: termId || undefined, page: 1, pageSize: 100 }
        const settled = await Promise.allSettled([
          api.archiveOverview({ termId: termId || undefined }),
          api.listRecords({ ...params, status: 'CLOSED' }),
          api.listRectifications({ ...params, status: 'CLOSED' })
        ])
        if (!current()) return
        const [overview, recordResult, rectResult] = settled.map(item => item.status === 'fulfilled' ? item.value : item.reason)
        const denied = [overview, recordResult, rectResult].find(result => this.denied(result))
        if (denied) throw denied
        const overviewValid = overview?.code === 0 && overview.data && typeof overview.data === 'object'
        const recordsValid = recordResult?.code === 0 && Array.isArray(recordResult.data?.list)
        const rectsValid = rectResult?.code === 0 && Array.isArray(rectResult.data?.list)
        if (overviewValid) this.archiveData = overview.data
        const records = recordsValid ? recordResult.data.list : []
        const rects = rectsValid ? rectResult.data.list : []
        const failed = [
          ['汇总指标', overviewValid ? null : (overview?.code === 0 ? { code: 503001, message: '汇总指标回执不完整' } : overview)],
          ['已关闭问题', recordsValid ? null : (recordResult?.code === 0 ? { code: 503001, message: '已关闭问题回执不完整' } : recordResult)],
          ['已关闭整改', rectsValid ? null : (rectResult?.code === 0 ? { code: 503001, message: '已关闭整改回执不完整' } : rectResult)]
        ].filter(([, result]) => result)
        if (failed.length === 3) throw { code: 503001, message: failed.map(([label, result]) => `${label}：${this.failureText(result, '读取失败')}`).join('；') }
        if (failed.length) this.archivePartial = `部分档案数据暂不可用：${failed.map(([label, result]) => `${label}（${this.failureText(result, '读取失败')}）`).join('、')}。表格只展示已核实的正式接口结果。`
        const recordsById = new Map(records.map(row => [String(row.recordId), row]))
        const usedRecords = new Set()
        const rows = rects.map(rect => {
          const source = recordsById.get(String(rect.sourceRecordId))
          if (source) usedRecords.add(String(source.recordId))
          return {
            archiveKey: `rect:${rect.rectId}`,
            sourceTitle: source?.title || rect.sourceTitle || (rect.sourceRecordId ? `问题记录 #${rect.sourceRecordId}` : '来源问题待核对'),
            sourceTypeLabel: this.recTypeLabel(source?.recordType || rect.sourceType) || '质量问题',
            rectTitle: rect.title,
            conclusion: rect.resultNote || source?.conclusion || '',
            closedAt: rect.closedAt || source?.confirmedAt || source?.createdAt,
            timeline: this.timelineFromLog(rect.progressLog),
            sourceRecord: source || null,
            rectification: rect
          }
        })
        records.filter(record => !usedRecords.has(String(record.recordId))).forEach(record => rows.push({
          archiveKey: `record:${record.recordId}`, sourceTitle: record.title, sourceTypeLabel: this.recTypeLabel(record.recordType), rectTitle: '',
          conclusion: record.conclusion || record.handlingNote || '', closedAt: record.confirmedAt || record.createdAt,
          timeline: [], sourceRecord: record, rectification: null
        }))
        this.archiveRows = rows.sort((a, b) => String(b.closedAt || '').localeCompare(String(a.closedAt || '')))
      } catch (error) { if (current()) { if (this.denied(error)) { this.archiveData = {}; this.archiveRows = [] }; this.panelError = this.failureText(error, '质量归档加载失败，请重试。') } }
      finally { if (current()) this.archiveLoading = false }
    },
    openArchiveEvidence(row) { this.archiveEvidence = Object.freeze({ ...row }); this.archiveEvidenceVisible = true },
    async doArchiveExport(domain) {
      if (this.archiveExporting) return
      const identity = this.identityKey, termId = this.archiveTermId
      this.archiveExporting = true
      try {
        const res = await api.archiveExport(domain, { termId: termId || undefined, purpose: `质量归档导出-${domain}` })
        if (!this.alive || identity !== this.identityKey || termId !== this.archiveTermId) return
        if (res?.code !== 0 || !(res.data instanceof Blob)) throw res
        this._download(res.data, `quality_archive_${domain}.xlsx`); toast.success('已生成质量归档文件')
      } catch (error) { if (this.alive && identity === this.identityKey) toast.error(this.failureText(error, '归档导出结果待核实，请检查下载记录后再试。')) }
      finally { if (this.alive && identity === this.identityKey) this.archiveExporting = false }
    }
  }
}
</script>

<style scoped>
.aaql-tabs { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 16px; border-bottom: 1px solid var(--border-color, #e5e7eb); }
.aaql-tab { padding: 8px 14px; border: none; background: none; cursor: pointer; font-size: 13px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; }
.aaql-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 500; }
.aaql-receipt { display: grid; grid-template-columns: minmax(240px, 1fr) minmax(150px, auto) minmax(150px, auto) auto; gap: 20px; align-items: center; margin-bottom: 16px; padding: 14px 18px; border: 1px solid #b7dfc9; border-radius: 10px; background: #f0fbf5; color: #174c32; }
.aaql-receipt.is-warning { border-color: #f0c980; background: #fff8e8; color: #784b0c; }
.aaql-receipt p { margin: 3px 0 0; font-size: 13px; }
.aaql-receipt div:not(:first-child) { display: flex; flex-direction: column; gap: 3px; }
.aaql-receipt small { color: currentColor; opacity: .72; }
.aaql-bar { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.aaql-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; margin-bottom: 20px; }
.aaql-grid--summary, .aaql-grid--archive { grid-template-columns: repeat(4, minmax(150px, 1fr)); }
.aaql-card { padding: 18px; border: 1px solid var(--border-base, #dbe4f0); background: var(--bg-card, #fff); border-radius: 10px; box-shadow: 0 2px 7px rgba(23, 50, 85, .04); }
.aaql-card.is-due { border-color: #ebc780; background: #fff9ed; }
.aaql-value { font-size: 26px; font-weight: 700; color: var(--primary-color, #2563eb); }
.aaql-value.aaql-danger { color: var(--danger-color, #dc2626); }
.aaql-unit { font-size: 14px; margin-left: 2px; color: var(--text-secondary, #64748b); }
.aaql-label { margin-top: 4px; font-size: 13px; color: var(--text-secondary, #64748b); }
.aaql-sub { margin-top: 2px; font-size: 12px; color: var(--text-tertiary, #94a3b8); }
.aaql-overview-layout { display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 16px; align-items: start; }
.aaql-panel { min-width: 0; overflow: hidden; border: 1px solid var(--border-base, #dbe4f0); border-radius: 10px; background: var(--bg-card, #fff); box-shadow: 0 2px 7px rgba(23, 50, 85, .04); }
.aaql-panel > header { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 52px; padding: 0 18px; border-bottom: 1px solid var(--border-base, #e5ebf3); }
.aaql-panel > header h3 { margin: 0; color: var(--text-primary, #122b4e); font-size: 16px; }
.aaql-panel > header span, .aaql-panel > header p { color: var(--text-secondary, #64748b); font-size: 12px; }
.aaql-indicators { padding-bottom: 8px; }
.aaql-indicator-row { display: grid; grid-template-columns: 1fr auto; gap: 2px 12px; padding: 13px 18px; border-bottom: 1px solid var(--border-light, #edf1f7); }
.aaql-indicator-row:last-child { border-bottom: 0; }
.aaql-indicator-row span { color: var(--text-secondary, #536a88); font-size: 13px; }
.aaql-indicator-row b { color: var(--text-primary, #122b4e); }
.aaql-indicator-row small { grid-column: 1 / -1; color: var(--text-tertiary, #8291a7); }
.aaql-history { margin-top: 16px; border: 1px solid var(--border-base, #dbe4f0); border-radius: 10px; background: var(--bg-card, #fff); overflow: hidden; }
.aaql-history summary { padding: 14px 18px; color: var(--text-primary, #122b4e); font-weight: 600; cursor: pointer; }
.aaql-stage-rail { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 0; margin: 0 0 16px; padding: 0; list-style: none; border: 1px solid var(--border-base, #dbe4f0); border-radius: 10px; background: #fff; overflow: hidden; }
.aaql-stage-rail li { position: relative; display: flex; gap: 10px; align-items: center; min-width: 0; padding: 13px 14px; border-right: 1px solid var(--border-light, #edf1f7); }
.aaql-stage-rail li:last-child { border-right: 0; }
.aaql-stage-rail li > span { display: inline-grid; place-items: center; width: 26px; height: 26px; flex: 0 0 auto; border-radius: 50%; background: #eef3fa; color: #5d7391; font-size: 12px; font-weight: 700; }
.aaql-stage-rail li div { min-width: 0; display: flex; flex-direction: column; }
.aaql-stage-rail li strong { overflow: hidden; color: #304967; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.aaql-stage-rail li small { color: #8a9aaf; font-size: 11px; }
.aaql-stage-rail li.is-current { background: #edf4ff; }
.aaql-stage-rail li.is-current > span, .aaql-stage-rail li.is-done > span { background: var(--primary-color, #2563eb); color: #fff; }
.aaql-stage-rail li.is-current strong { color: var(--primary-color, #235dbc); }
.aaql-record-layout { display: grid; grid-template-columns: minmax(0, 1fr) 290px; gap: 16px; align-items: start; }
.aaql-form-card { overflow: visible; }
.aaql-side-stack { display: flex; flex-direction: column; gap: 16px; }
.aaql-side-stack .aaql-panel { padding-bottom: 14px; }
.aaql-side-stack .aaql-panel > p { margin: 12px 16px 0; color: var(--text-secondary, #63758e); font-size: 12px; line-height: 1.55; }
.aaql-conditions ul { margin: 0; padding: 0 16px; list-style: none; }
.aaql-conditions li { display: flex; justify-content: space-between; gap: 12px; padding: 12px 0; border-bottom: 1px solid var(--border-light, #edf1f7); color: #506782; font-size: 12px; }
.aaql-conditions li b { color: var(--primary-color, #235dbc); }
.aaql-section-title { font-weight: 500; margin: 8px 0 12px; }
.aaql-form { display: flex; flex-direction: column; gap: 12px; }
.aaql-form--record { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 2px 20px; padding: 20px; background: var(--bg-card, #fff); }
.aaql-form--record .aaql-field--full { grid-column: 1 / -1; }
.aaql-form-actions { display: flex; align-items: center; justify-content: flex-end; gap: 10px; padding-top: 14px; border-top: 1px solid var(--border-light, #edf1f7); }
.aaql-form-actions > span { margin-right: auto; color: var(--text-secondary, #64748b); font-size: 12px; }
.aaql-form-section { display: flex; align-items: baseline; gap: 10px; padding-bottom: 10px; margin: 2px 0 8px; border-bottom: 1px solid var(--border-base, #e2e8f0); }
.aaql-form-section:not(:first-child) { margin-top: 8px; }
.aaql-form-section strong { color: var(--text-primary, #0f172a); font-size: 15px; }
.aaql-form-section span { color: var(--text-tertiary, #94a3b8); font-size: 12px; }
.aaql-flag { font-size: 12px; padding: 1px 6px; border-radius: 4px; background: var(--warning-bg, #fef3c7); color: var(--warning-color, #b45309); }
.aaql-kanban { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.aaql-lane { min-width: 0; padding: 12px; border: 1px solid var(--border-base, #dbe4f0); border-radius: 10px; background: #f6f8fc; }
.aaql-lane > header { display: flex; justify-content: space-between; align-items: center; padding: 2px 2px 12px; }
.aaql-lane > header h3 { margin: 0; color: #233f62; font-size: 15px; }
.aaql-lane > header span { display: inline-grid; place-items: center; min-width: 24px; height: 24px; border-radius: 12px; background: #e5ecf7; color: #536b89; font-size: 12px; }
.aaql-lane-list { display: flex; flex-direction: column; gap: 10px; }
.aaql-rect-card { padding: 14px; border: 1px solid #e1e8f1; border-radius: 9px; background: #fff; box-shadow: 0 2px 6px rgba(31, 61, 99, .04); }
.aaql-rect-card h4 { margin: 0 0 10px; color: #173557; font-size: 14px; }
.aaql-rect-card p { margin: 5px 0; overflow: hidden; color: #637791; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.aaql-rect-card footer { display: flex; justify-content: space-between; align-items: center; margin-top: 12px; padding-top: 10px; border-top: 1px solid #edf1f6; }
.aaql-follow-layout { display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: 16px; align-items: start; }
.aaql-follow-queue { display: flex; flex-direction: column; max-height: 680px; overflow: auto; }
.aaql-follow-item { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 5px 10px; padding: 13px 16px; border: 0; border-bottom: 1px solid #edf1f6; background: #fff; text-align: left; cursor: pointer; }
.aaql-follow-item:hover, .aaql-follow-item.is-active { background: #edf4ff; }
.aaql-follow-item strong { overflow: hidden; color: #173557; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.aaql-follow-item > span { grid-column: 1 / -1; overflow: hidden; color: #73849a; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.aaql-follow-main { display: flex; min-width: 0; flex-direction: column; gap: 14px; }
.aaql-object-context { display: grid; grid-template-columns: minmax(0, 1fr) minmax(140px, auto) minmax(160px, auto); gap: 18px; align-items: center; padding: 16px 18px; border: 1px solid #c9dbf4; border-radius: 10px; background: #f3f7fd; }
.aaql-object-context div { min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.aaql-object-context span, .aaql-object-context small { color: #6a7f9b; font-size: 11px; }
.aaql-object-context h3 { margin: 0; overflow: hidden; color: #15365e; font-size: 17px; text-overflow: ellipsis; white-space: nowrap; }
.aaql-object-context p { margin: 0; color: #647a96; font-size: 12px; }
.aaql-object-context strong { color: #244d7d; font-size: 13px; }
.aaql-detail-actions { display: flex; justify-content: flex-end; gap: 8px; padding: 14px 18px; border-top: 1px solid #edf1f6; }
.aaql-cell-note { display: block; margin-top: 3px; color: #8190a4; font-size: 11px; }
.aaql-detail { display: flex; flex-direction: column; gap: 10px; }
.aaql-detail-row { display: flex; flex-direction: column; gap: 2px; font-size: 13px; }
.aaql-detail-row span { color: var(--text-tertiary, #94a3b8); font-size: 12px; }
.aaql-detail-row b.aaql-danger { color: var(--danger-color, #dc2626); }
.aaql-detail-row p { margin: 0; white-space: pre-wrap; word-break: break-word; }
@media (max-width: 1100px) {
  .aaql-overview-layout, .aaql-record-layout { grid-template-columns: 1fr; }
  .aaql-side-stack { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .aaql-kanban { grid-template-columns: 1fr; }
  .aaql-lane-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 720px) {
  .aaql-grid--summary, .aaql-grid--archive, .aaql-side-stack, .aaql-lane-list { grid-template-columns: 1fr; }
  .aaql-receipt, .aaql-follow-layout, .aaql-object-context { grid-template-columns: 1fr; }
  .aaql-stage-rail { grid-template-columns: 1fr; }
  .aaql-stage-rail li { border-right: 0; border-bottom: 1px solid var(--border-light, #edf1f7); }
  .aaql-form--record { grid-template-columns: 1fr; }
  .aaql-form--record .aaql-field--full { grid-column: auto; }
  .aaql-form-section { align-items: flex-start; flex-direction: column; gap: 3px; }
  .aaql-form-actions { align-items: stretch; flex-direction: column; }
}
</style>
