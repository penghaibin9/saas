<template>
  <ModulePageShell
    :title="modeSpec.title"
    :subtitle="modeSpec.subtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="aamk-tabs">
      <button v-for="t in tabs" :key="t.key" :class="['aamk-tab', { 'is-active': tab === t.key }]" :disabled="saving || !!pendingWrite" @click="switchTab(t.key)">{{ t.label }}</button>
    </div>

    <section v-if="writeReceipt" class="aamk-receipt" role="status"><strong>{{ writeReceipt.verified ? '已回读正式记录' : '结果待核实' }}</strong><p>{{ writeReceipt.label }} · {{ writeReceipt.description }}</p><p v-if="writeReceipt.objectId">业务对象：#{{ writeReceipt.objectId }} · 操作时间：{{ formatMoment(writeReceipt.occurredAt) }}</p><p v-if="writeReceipt.status">实际状态：{{ writeReceipt.statusLabel || academicStatusLabel(writeReceipt.status) }}</p><p v-if="writeReceipt.next">下一步：{{ writeReceipt.next }}</p><AppButton v-if="pendingWrite" :disabled="saving" :loading="checkingWrite" @click="verifyWrite">只读核对结果</AppButton><p v-if="pendingWrite">请勿重复提交；如详情弹窗遮挡，可先关闭弹窗再核对。</p></section>
    <ErrorState v-if="error" :description="error" @retry="reload" />
    <LoadingState v-else-if="loading" />
    <template v-else>
      <section v-if="examFlowMode" class="aamk-process">
        <header>
          <div>
            <span>{{ modeSpec.objectType }}</span>
            <strong>{{ focusedProcessRow ? processObjectTitle(focusedProcessRow) : '当前范围暂无正式对象' }}</strong>
            <small>{{ focusedProcessRow ? processObjectIdentity(focusedProcessRow) : modeSpec.source }}</small>
          </div>
          <StatusTag v-if="focusedProcessRow" :type="mbType(focusedProcessRow.status)" :label="processStatusLabel" dot />
        </header>
        <ol v-if="focusedProcessRow" class="aamk-process__stages" aria-label="业务办理阶段">
          <li v-for="(step,index) in modeSpec.steps" :key="step" :class="{ done: index < processStage, current: index === processStage }">
            <span>{{ index < processStage ? '✓' : index + 1 }}</span><div><strong>{{ step }}</strong><small>{{ index === processStage ? '当前阶段' : index < processStage ? '已完成' : '等待前序完成' }}</small></div>
          </li>
        </ol>
        <dl class="aamk-process__facts">
          <div><dt>对象来源</dt><dd>{{ modeSpec.source }}</dd></div>
          <div><dt>当前责任</dt><dd>{{ modeSpec.owner }}</dd></div>
          <div><dt>为什么轮到我</dt><dd>{{ modeSpec.whyMe }}</dd></div>
          <div><dt>当前阻断</dt><dd>{{ processBlocker }}</dd></div>
          <div><dt>下一责任岗位</dt><dd>{{ processNextOwner }}</dd></div>
          <div><dt>返回位置</dt><dd>当前{{ modeSpec.title }}队列 · 第 {{ pagination.page }} 页</dd></div>
        </dl>
      </section>

      <!-- 补考批次 -->
      <div v-if="tab === 'makeup'" class="mp-stack">
        <div class="aamk-bar">
          <AppButton v-if="canManage" variant="primary" size="small" @click="openCreateBatch">新建补考批次</AppButton>
        </div>
        <EmptyState v-if="!rows.length" title="暂无补考批次" description="从不及格名单建批次" />
        <DataTable v-else :columns="batchColumns" :rows="rows" :pagination="pagination" @page-change="changePage" row-key="batchId">
          <template #cell-batchName="{ row }"><button class="aamk-focus" @click="focusProcess(row)">{{ row.batchName }}</button><small>#{{ row.batchId }} · {{ row.termCode || '学期待核对' }}</small></template>
          <template #cell-status="{ row }"><StatusTag :type="mbType(row.status)" :label="mbLabel(row.status)" dot /></template>
          <template #cell-ops="{ row }">
            <button class="mp-link" @click="openMakeupRecords(row)">名单/纳入</button>
            <button v-if="canManage && row.status === 'ARRANGED'" class="mp-link" @click="act('publishBatch', row.batchId, '发布')">发布</button>
            <button v-if="canManage && row.status === 'SCORING'" class="mp-link" @click="act('collegeReview', row.batchId, '学院审核')">学院审核</button>
            <button v-if="canManage && row.status === 'REVIEWED'" class="mp-link" @click="act('finishBatch', row.batchId, '教务发布回写')">教务发布回写</button>
            <button v-if="row.status !== 'DRAFT' && row.status !== 'ARRANGED'" class="mp-link" @click="printBatch(row.batchId)">打印安排表</button>
          </template>
        </DataTable>
      </div>

      <div v-else-if="['retake','exemption'].includes(tab)" class="aamk-review">
        <aside class="aamk-queue"><h3>责任队列</h3><EmptyState v-if="!rows.length" title="暂无申请" description="当前身份与范围内没有可显示的申请" />
          <button v-for="row in rows" :key="row.applyId || row.exemptionId" :class="['aamk-object',{selected:String(activeApplication?.applyId || activeApplication?.exemptionId)===String(row.applyId || row.exemptionId)}]" :disabled="saving || !!pendingWrite" @click="selectApplication(row)">
            <strong>{{ row.studentName }}</strong>
            <span>{{ row.courseName }} · {{ row.termCode || '学期待核对' }}</span>
            <small>#{{ row.applyId || row.exemptionId }} · {{ revisionText(row) }}</small>
            <StatusTag :type="rtType(row.status)" :label="applicationStatus(row)" />
          </button>
          <div class="aamk-paging"><AppButton :disabled="pagination.page <= 1 || saving || !!pendingWrite" @click="changePage(pagination.page-1)">上一页</AppButton><span>第{{ pagination.page }}页</span><AppButton :disabled="pagination.page * pagination.pageSize >= pagination.total || saving || !!pendingWrite" @click="changePage(pagination.page+1)">下一页</AppButton></div>
        </aside>
        <section class="aamk-evidence">
          <EmptyState v-if="!activeApplication" title="选择一份申请" description="先核对学生、课程、申请理由和当前节点" />
          <template v-else><header class="aamk-evidence__head"><div><h3>{{ activeApplication.studentName }} · {{ activeApplication.courseName }}</h3><p>{{ objectTitle(activeApplication) }} · {{ activeApplication.termCode || '学期待核对' }} · {{ revisionText(activeApplication) }}</p></div><StatusTag :type="rtType(activeApplication.status)" :label="applicationStatus(activeApplication)" /></header>
            <ol class="aamk-stage" aria-label="办理进度">
              <li v-for="(step,index) in applicationSteps" :key="step" :class="{done:index < applicationStage,current:index === applicationStage}"><span>{{ index < applicationStage ? '✓' : index + 1 }}</span><div><strong>{{ step }}</strong><small>{{ index === applicationStage ? '当前环节' : index < applicationStage ? '已完成或已越过' : '等待前序完成' }}</small></div></li>
            </ol>
            <AppInlineAlert v-if="!hasEvidenceContract(activeApplication)" type="warning" title="正式来源合同未返回" description="本页不会按学生姓名、课程名称或历史总评分数推断来源。共享服务返回精确成绩与证据版本后才能办理。" />
            <div class="aamk-facts">
              <article><div class="aamk-fact-title"><strong>来源对象与身份</strong><StatusTag type="success" label="精确申请" /></div><p>{{ objectTitle(activeApplication) }}</p><p>{{ courseIdentity(activeApplication) }}</p><p>提交：{{ formatMoment(activeApplication.appliedAt) }}</p><p class="aamk-muted">{{ activeApplication.reason || '未填写申请理由' }}</p></article>
              <article v-if="tab === 'retake'"><div class="aamk-fact-title"><strong>原正式成绩</strong><StatusTag :type="stateMeta(activeApplication.sourceGradeState).type" :label="stateMeta(activeApplication.sourceGradeState).label" /></div><p>{{ gradeIdentity(activeApplication.originGrade) }}</p><p>{{ gradeResult(activeApplication.originGrade) }}</p><p class="aamk-muted">{{ gradeSource(activeApplication.originGrade) }}</p><p class="aamk-muted">来源证据 {{ shortHash(activeApplication.sourceEvidenceHash) }}</p></article>
              <article v-if="tab === 'retake'"><div class="aamk-fact-title"><strong>当前成绩事实</strong><StatusTag :type="stateMeta(activeApplication.sourceGradeState).type" :label="activeApplication.currentGrade?.gradeId ? '当前版本已定位' : '当前版本待核对'" /></div><p>{{ gradeIdentity(activeApplication.currentGrade) }}</p><p>{{ gradeResult(activeApplication.currentGrade) }}</p><p class="aamk-muted">{{ gradeSource(activeApplication.currentGrade) }}</p></article>
              <article v-else><div class="aamk-fact-title"><strong>课程与认定依据</strong><StatusTag :type="stateMeta(activeApplication.evidenceState,'evidence').type" :label="stateMeta(activeApplication.evidenceState,'evidence').label" /></div><p>{{ courseIdentity(activeApplication) }}</p><p>证据 {{ activeApplication.evidenceCount == null ? '数量待核对' : `${activeApplication.evidenceCount} 份` }} · 清单 {{ shortHash(activeApplication.evidenceManifestHash) }}</p><p v-if="evidenceProblems(activeApplication).length" class="aamk-danger">{{ evidenceProblems(activeApplication).join('；') }}</p><p v-else class="aamk-muted">证据有效不等于当前文件访问已授权，打开前仍由文件中心复核。</p></article>
              <article v-if="tab === 'exemption'"><div class="aamk-fact-title"><strong>终审成绩结果</strong><StatusTag :type="stateMeta(activeApplication.resultGradeState).type" :label="stateMeta(activeApplication.resultGradeState).label" /></div><p>{{ gradeIdentity(activeApplication.resultGrade) }}</p><p>{{ gradeResult(activeApplication.resultGrade) }}</p><p class="aamk-muted">{{ gradeSource(activeApplication.resultGrade) }}</p><p class="aamk-muted">当前有效：{{ gradeIdentity(activeApplication.currentGrade) }} · {{ gradeResult(activeApplication.currentGrade) }}</p></article>
              <article><div class="aamk-fact-title"><strong>当前节点与可办动作</strong><StatusTag :type="rtType(activeApplication.status)" :label="applicationStatus(activeApplication)" /></div><p>{{ tab === 'retake' ? '补重修责任岗' : nodeLabel(activeApplication.currentNode) }}</p><p>{{ actionText(activeApplication) }}</p><p v-if="blockers(activeApplication).length" class="aamk-danger">{{ blockers(activeApplication).join('；') }}</p><p v-else class="aamk-muted">{{ activeApplication.returnReason || activeApplication.reviewReason || '暂无办理意见' }}</p></article>
              <article><div class="aamk-fact-title"><strong>{{ tab === 'retake' ? '新修读安排' : '证据文件版本' }}</strong><StatusTag :type="tab === 'retake' && activeApplication.enrollment?.rosterCoverage === 'FROZEN_AT_ENROLLMENT' ? 'success' : 'default'" :label="tab === 'retake' ? enrollmentLabel(activeApplication) : `${formalEvidenceFiles(activeApplication).length}份已登记`" /></div>
                <template v-if="tab === 'retake'"><p>教学任务：{{ activeApplication.enrollment?.teachingTaskId || activeApplication.teachingTaskId || '尚未编入' }}</p><p>教学班：{{ activeApplication.enrollment?.teachingClassId || '待核对' }}</p><p class="aamk-muted">{{ rosterIdentity(activeApplication) }}</p></template>
                <ul v-else-if="formalEvidenceFiles(activeApplication).length" class="aamk-evidence-list"><li v-for="file in formalEvidenceFiles(activeApplication)" :key="file.frozenBindingId || file.fileId"><strong>{{ file.fileName || `文件 #${file.fileId}` }}</strong><span>{{ evidenceVersion(file) }}</span><small>SHA-256 {{ shortHash(file.sha256) }} · {{ file.bindingStatus || '绑定状态待核对' }}</small></li></ul>
                <p v-else class="aamk-muted">未返回冻结证据文件；不使用旧附件名称替代正式清单。</p>
              </article>
            </div>
            <footer class="aamk-bar">
              <template v-if="tab === 'retake' && canReviewRetake"><button v-if="applicationCan(activeApplication,'APPROVE')" class="mp-link" @click="review('retakeReview',activeApplication.applyId,'APPROVE')">确认审核重修申请</button><button v-if="applicationCan(activeApplication,'REJECT')" class="mp-link is-danger" @click="reject('retakeReview',activeApplication.applyId)">驳回</button><button v-if="applicationCan(activeApplication,'ENROLL')" class="mp-link" @click="enrollRetake(activeApplication.applyId)">选择教学任务并编班</button></template>
              <template v-if="tab === 'exemption' && canReviewExemption"><button v-if="applicationCan(activeApplication,'APPROVE')" class="mp-link" @click="review('exemptionReview',activeApplication.exemptionId,'APPROVE')">确认本节点审核</button><button v-if="applicationCan(activeApplication,'RETURN')" class="mp-link" @click="returnEx(activeApplication.exemptionId)">退回补充材料</button><button v-if="applicationCan(activeApplication,'REJECT')" class="mp-link is-danger" @click="reject('exemptionReview',activeApplication.exemptionId)">驳回</button></template>
              <span v-if="!formalActions(activeApplication).length" class="aamk-muted">服务端未授权当前动作，仅可核对。</span>
            </footer>
          </template>
        </section>
      </div>

      <!-- 毕业清考 -->
      <div v-else-if="tab === 'clearance'" class="mp-stack">
        <div class="aamk-bar">
          <AppButton v-if="canManage" variant="primary" size="small" @click="openCreateClearance">新建清考批次</AppButton>
        </div>
        <AppInlineAlert type="info" description="毕业清考=应届生对「补考/重修后最优成绩仍不及格」课程的最后考核机会；名单自动圈定，正式成绩按学校规则折算，回写成绩后可重跑毕业预审。" />
        <EmptyState v-if="!rows.length" title="暂无清考批次" description="为毕业年级新建清考批次并自动圈定名单" />
        <DataTable v-else :columns="clearanceColumns" :rows="rows" :pagination="pagination" @page-change="changePage" row-key="batchId">
          <template #cell-batchName="{ row }"><button class="aamk-focus" @click="focusProcess(row)">{{ row.batchName }}</button><small>#{{ row.batchId }} · {{ row.termCode || '学期待核对' }}</small></template>
          <template #cell-grades="{ row }">{{ (row.targetGrades || []).join('、') || '—' }}</template>
          <template #cell-status="{ row }"><StatusTag :type="mbType(row.status)" :label="mbLabel(row.status)" dot /></template>
          <template #cell-ops="{ row }">
            <button v-if="canManage && ['DRAFT','ARRANGED'].includes(row.status)" class="mp-link" @click="scanClearance(row, true)">预览名单</button>
            <button v-if="canManage && ['DRAFT','ARRANGED'].includes(row.status)" class="mp-link" @click="scanClearance(row, false)">圈定名单</button>
            <button class="mp-link" @click="openClearanceRecords(row)">名单/录分</button>
            <button v-if="canManage && row.status === 'ARRANGED'" class="mp-link" @click="act('publishBatch', row.batchId, '发布清考')">发布</button>
            <button v-if="canManage && row.status === 'SCORING'" class="mp-link" @click="act('collegeReview', row.batchId, '学院审核')">学院审核</button>
            <button v-if="canManage && row.status === 'REVIEWED'" class="mp-link" @click="act('finishBatch', row.batchId, '清考成绩正式回写')">教务发布回写</button>
          </template>
        </DataTable>
      </div>

      <!-- 缓考合流 -->
      <div v-else class="mp-stack">
        <EmptyState v-if="!rows.length" title="暂无已批准且待合流的缓考申请" description="考务包审批通过的缓考学生在此并入补考批次" />
        <DataTable v-else :columns="poolColumns" :rows="rows" :pagination="pagination" @page-change="changePage" row-key="deferId">
          <template #cell-student="{ row }"><button class="aamk-focus" @click="focusProcess(row)">{{ row.studentName }}</button><small>{{ row.studentNo || '学号待核对' }}</small></template>
          <template #cell-course="{ row }">{{ row.courseName || '课程待核对' }}<small>原考试/课程来源</small></template>
          <template #cell-approved="{ row }">#{{ row.deferId }}<small>已批准缓考申请</small></template>
          <template #cell-target="{ row }">{{ row.nextBatchRef || '待选择补考批次' }}</template>
          <template #cell-status="{ row }"><StatusTag :type="row.nextBatchRef ? 'success' : 'warning'" :label="row.nextBatchRef ? '已合流' : '待安排'" dot /></template>
          <template #cell-ops="{ row }"><button v-if="canManage && !row.nextBatchRef" class="mp-link" @click="openMerge(row)">并入补考批次</button><span v-else class="aamk-muted">只读核对</span></template>
        </DataTable>
      </div>
    </template>

    <AppDrawer :visible="batchVisible" title="新建补考批次" mode="modal" size="medium" @close="batchVisible = false">
      <div class="aamk-form">
        <AppFormItem label="批次名称" required><AppTextInput v-model="batchForm.batchName" placeholder="如 2024秋补考" :disabled="saving || !!pendingWrite" /></AppFormItem>
        <AppFormItem label="学期"><AppTermCodePicker v-model="batchForm.termCode" :disabled="saving || !!pendingWrite" /></AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving || !!pendingWrite" @click="batchVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitBatch">创建</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="mergeVisible" title="并入补考批次" mode="modal" size="small" @close="mergeVisible = false">
      <div class="aamk-form">
        <AppFormItem label="目标补考批次" required><AppMakeupBatchPicker v-model="mergeBatchId" :disabled="saving || !!pendingWrite" /></AppFormItem>
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving || !!pendingWrite" @click="mergeVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitMerge">并入</AppButton>
      </template>
    </AppDrawer>

    <!-- 建清考批次 -->
    <AppDrawer :visible="clearanceVisible" title="新建毕业清考批次" mode="modal" size="medium" @close="clearanceVisible = false">
      <div class="aamk-form">
        <AppFormItem label="批次名称" required><AppTextInput v-model="clearanceForm.batchName" placeholder="如 2022届毕业清考" :disabled="saving || !!pendingWrite" /></AppFormItem>
        <AppFormItem label="限定毕业年级" required><AppTextInput v-model="clearanceForm.grades" placeholder="逗号分隔，如 2022 或 2021,2022" :disabled="saving || !!pendingWrite" /></AppFormItem>
        <AppFormItem label="学期"><AppTermCodePicker v-model="clearanceForm.termCode" :disabled="saving || !!pendingWrite" /></AppFormItem>
        <AppInlineAlert v-if="clearanceError" type="danger" :description="clearanceError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving || !!pendingWrite" @click="clearanceVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitClearance">创建</AppButton>
      </template>
    </AppDrawer>

    <!-- 清考名单/录分 -->
    <AppDrawer :visible="crVisible" :title="'清考名单 · ' + (crBatch ? crBatch.batchName : '')" mode="modal" size="xlarge" @close="crVisible = false">
      <AppInlineAlert v-if="detailError" type="danger" :description="detailError" /><LoadingState v-if="crLoading" />
      <EmptyState v-if="!crLoading && !crRows.length" title="暂无名单" description="先执行「圈定名单」自动捞取未通过课程" />
      <DataTable v-else :columns="crColumns" :rows="crRows" :pagination="crPagination" @page-change="page => !saving && !pendingWrite && loadClearanceRecords(page)" row-key="makeupId">
        <template #cell-student="{ row }">{{ row.studentName }}（{{ row.studentNo }}）</template>
        <template #cell-course="{ row }">{{ row.courseName }}<span class="mp-cell-sub">（原 {{ row.originScore != null ? row.originScore : '—' }} 分）</span></template>
        <template #cell-score="{ row }">
          <span v-if="['SCORED','FINISHED'].includes(row.status)">{{ row.finalScore }}</span>
          <AppNumberInput
            v-else-if="canManage && crBatch && ['PUBLISHED','SCORING'].includes(crBatch.status)"
            v-model="crScores[row.makeupId]" :disabled="saving || !!pendingWrite"
            class="aamk-score-input"
            :min="0"
            :max="100"
            :controls="false"
            size="compact"
            placeholder="0-100"
          />
          <span v-else>—</span>
        </template>
        <template #cell-ops="{ row }">
          <button v-if="canManage && row.status !== 'SCORED' && row.status !== 'FINISHED' && crBatch && ['PUBLISHED','SCORING'].includes(crBatch.status)"
                  class="mp-link" @click="submitClearanceScore(row)">录分</button>
        </template>
      </DataTable>
    </AppDrawer>

    <!-- 补考名单/纳入：上半是已纳入名单与录分，下半是候选名单与纳入 -->
    <AppDrawer :visible="mkVisible" :title="'补考名单 · ' + (mkBatch ? mkBatch.batchName : '')" mode="modal" size="xlarge" @close="mkVisible = false">
      <AppInlineAlert
        type="info"
        description="纳入只认学生本人当前有效的不及格成绩：课程、课程版本、修读次数和原始分全部由服务器从该条成绩推导，不接受手工输入课程名称。"
      />

      <h4 class="aamk-sub">已纳入名单（{{ mkPagination.total }}）</h4>
      <AppInlineAlert v-if="detailError" type="danger" :description="detailError" /><LoadingState v-if="mkLoading" />
      <EmptyState v-if="!mkLoading && !mkRows.length" title="尚未纳入学生" description="从下方候选名单选择不及格成绩纳入本批次" />
      <DataTable v-else :columns="mkColumns" :rows="mkRows" :pagination="mkPagination" @page-change="page => !saving && !pendingWrite && loadMakeupRecords(page)" row-key="makeupId">
        <template #cell-student="{ row }">{{ row.studentName }}（{{ row.studentNo }}）</template>
        <template #cell-course="{ row }">{{ row.courseName }}<span class="mp-cell-sub">（原 {{ row.originScore != null ? row.originScore : '—' }} 分）</span></template>
        <template #cell-score="{ row }">
          <span v-if="row.status === 'SCORED' || row.status === 'FINISHED'">{{ row.finalScore }}</span>
          <AppNumberInput
            v-else-if="canScoreMakeup"
            v-model="mkScores[row.makeupId]" :disabled="saving || !!pendingWrite"
            class="aamk-score-input" :min="0" :max="100" :controls="false" size="compact" placeholder="0-100"
          />
          <span v-else>—</span>
        </template>
        <template #cell-ops="{ row }">
          <button v-if="row.status !== 'SCORED' && row.status !== 'FINISHED' && canScoreMakeup"
                  class="mp-link" @click="submitMakeupScore(row)">录分</button>
        </template>
      </DataTable>

      <template v-if="canEnroll">
        <h4 class="aamk-sub">候选名单 · 当前有效不及格成绩</h4>
        <AppInlineAlert
          v-if="mkDebtCount"
          type="warning"
          :title="`${mkDebtCount} 条候选暂不可纳入`"
          description="这些记录缺少完整的课程和修读信息，需先由教务处核对。"
        />
        <LoadingState v-if="candidateLoading" /><EmptyState v-if="!candidateLoading && !mkCandidates.length" title="暂无候选" description="成绩发布后不及格的学生会出现在这里" />
        <DataTable v-else :columns="mkCandColumns" :rows="mkCandidates" :pagination="candidatePagination" @page-change="page => !saving && !pendingWrite && loadMakeupCandidates(page)" row-key="gradeId">
          <template #cell-student="{ row }">{{ row.studentName }}（{{ row.studentNo }}）<span class="mp-cell-sub">{{ row.className || '' }}</span></template>
          <template #cell-course="{ row }">
            {{ row.courseName }}
            <span class="mp-cell-sub">{{ row.courseCode || '编码待核对' }} · {{ row.courseVersion == null ? '版本待核对' : `版本${row.courseVersion}` }} · {{ row.attemptNo == null ? '次数待核对' : `第${row.attemptNo}次修读` }} · {{ row.score != null ? row.score : '—' }} 分</span>
          </template>
          <template #cell-ops="{ row }">
            <button v-if="row.identityReady && !enrolledGradeIds.has(String(row.gradeId))"
                    class="mp-link" :disabled="saving || !!pendingWrite" @click="enrollCandidate(row)">纳入</button>
            <span v-else-if="enrolledGradeIds.has(String(row.gradeId))" class="mp-cell-sub">已纳入</span>
            <span v-else class="mp-cell-sub">课程信息待核对</span>
          </template>
        </DataTable>
      </template>
      <AppInlineAlert
        v-else
        type="info"
        :description="'批次当前为' + mbLabel(mkBatch ? mkBatch.status : '') + '，只有草稿/已编排阶段可以继续纳入学生。'"
      />
    </AppDrawer>

    <AppDrawer :visible="retakeVisible" title="重修编入跟班" mode="modal" size="medium" @close="retakeVisible = false">
      <div class="aamk-form"><p>{{ retakeRow?.studentName }} · {{ retakeRow?.courseName }} · {{ retakeRow?.termCode }}</p>
        <AppFormItem label="目标教学任务" required><AppTeachingTaskPicker v-model="teachingTaskRef" :disabled="saving || !!pendingWrite" /></AppFormItem>
        <AppInlineAlert type="info" description="确认所选教学任务后提交。服务器核对学期、课程和名单版本；办理后回读申请编班状态。目标任务与名单版本详情仍需学校核对。" />
      </div><template #footer><AppButton :disabled="!teachingTaskRef || saving || !!pendingWrite" :loading="saving" @click="submitRetake">确认编入所选教学任务</AppButton></template>
    </AppDrawer>
    <AppConfirmDialog v-model:visible="confirmVisible" :title="confirmTitle" :message="confirmMessage" :submitting="saving" :confirm-disabled="!!pendingWrite" @confirm="onConfirm" />
    <AppConfirmDialog
      v-model:visible="reasonDialog.visible" :title="reasonDialog.title" type="danger"
      :confirm-disabled="String(reasonDialog.reason || '').trim().length < 5 || !!pendingWrite"
      :submitting="reasonDialog.submitting" @confirm="onReasonConfirm"
    ><AppInlineAlert v-if="error" type="danger" :description="error" /><label class="aamk-form">原因（至少5字）<textarea v-model="reasonDialog.reason" rows="3" :disabled="saving || !!pendingWrite" /></label></AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/** 补考重修缓考免修 · 教务处控制台（/admin/academic-affairs/makeup）：四条线 tab 管理。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppNumberInput, AppFormItem, AppConfirmDialog, AppInlineAlert, AppTermCodePicker, AppMakeupBatchPicker, AppTeachingTaskPicker } from '@/components/common'
import { academicAffairsMakeupApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { academicStatusLabel } from '@/modules/academicAffairs/constants/academic-display.constants'
import { matchPermission } from '@/config/navPlan'
import { currentUserFromToken } from '@/services/http/client'
import { gradeError } from './parallel-c/grade-review'
import {
  evidenceFiles, evidenceVersion, formatMoment, gradeIdentity, gradeResult, gradeSource,
  hasFormalAction, rowRevision, shortHash, stateMeta
} from './parallel-c/makeup-evidence'

const _MBL = { DRAFT: '草稿', ARRANGED: '已编排', PUBLISHED: '已发布', SCORING: '录入中', REVIEWED: '学院已审', FINISHED: '已结束' }

export default {
  name: 'AaMakeupConsoleView',
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
      AppButton, AppDrawer, AppTextInput, AppNumberInput, AppFormItem, AppConfirmDialog, AppInlineAlert, AppTermCodePicker, AppMakeupBatchPicker, AppTeachingTaskPicker
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      activeApplication: null,
      retakeVisible: false, retakeRow: null, teachingTaskRef: '',
      mkLoading: false, crLoading: false, candidateLoading: false, detailError: '',
      mkPagination: {page:1,pageSize:20,total:0}, crPagination: {page:1,pageSize:20,total:0}, candidatePagination: {page:1,pageSize:20,total:0},
      pendingWrite: null, writeReceipt: null, checkingWrite: false,
      alive: true, scopeSeq: 0, readSeq: 0, mkSeq: 0, crSeq: 0, candidateSeq: 0,
      pagination: { page: 1, pageSize: 20, total: 0 },
      tab: 'makeup', loading: true, error: '', rows: [], activeProcessKey: '',
      tabs: [
        { key: 'makeup', label: '补考批次' }, { key: 'retake', label: '重修审批' },
        { key: 'exemption', label: '免修审批' }, { key: 'clearance', label: '毕业清考' },
        { key: 'deferred', label: '缓考合流' }
      ],
      batchColumns: [{ key: 'batchName', title: '批次' }, { key: 'termCode', title: '学期' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }],
      clearanceColumns: [{ key: 'batchName', title: '批次' }, { key: 'grades', title: '毕业年级' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }],
      crColumns: [{ key: 'student', title: '学生' }, { key: 'course', title: '课程' }, { key: 'score', title: '清考成绩' }, { key: 'ops', title: '操作' }],
      clearanceVisible: false, clearanceForm: { batchName: '', grades: '', termCode: '' }, clearanceError: '',
      crVisible: false, crBatch: null, crRows: [], crScores: {},
      // 补考名单/纳入
      mkVisible: false, mkBatch: null, mkRows: [], mkScores: {}, mkCandidates: [], mkDebtCount: 0,
      mkColumns: [{ key: 'student', title: '学生' }, { key: 'course', title: '课程' }, { key: 'score', title: '补考成绩' }, { key: 'ops', title: '操作' }],
      mkCandColumns: [{ key: 'student', title: '学生' }, { key: 'course', title: '不及格成绩' }, { key: 'ops', title: '操作' }],
      poolColumns: [{ key: 'student', title: '学生' }, { key: 'course', title: '原考试课程' }, { key: 'approved', title: '已批申请' }, { key: 'target', title: '目标批次' }, { key: 'status', title: '合流状态' }, { key: 'ops', title: '办理入口' }],
      batchVisible: false, batchForm: { batchName: '', termCode: '' }, formError: '',
      mergeVisible: false, mergeRow: null, mergeBatchId: '',
      saving: false, confirmVisible: false, confirmTitle: '', confirmMessage: '', pendingAction: null,
      reasonDialog: { visible: false, title: '', reason: '', sceneKey: '', submitting: false, action: null }
    }
  },
  computed: {
    canManage() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.makeup.manage') },
    canReviewRetake() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.retake.review') },
    canReviewExemption() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.exemption.review') },
    identityKey() { const u = currentUserFromToken() || {}; return JSON.stringify([u.tenantId, u.userId, u.activeContextId, u.currentRoleCode, this.ctx.currentRole, this.ctx.dataScope, this.ctx.permissionPatterns]) },
    examFlowMode() { return ['makeup', 'clearance', 'deferred'].includes(this.tab) },
    modeSpec() {
      const specs = {
        makeup: { title: '补考批次', subtitle: '从正式不及格成绩圈定，完成安排、录分审核和有效成绩归档', objectType: '补考批次', source: '当前有效的不及格正式成绩', owner: '补重修责任岗', whyMe: '正式不及格成绩需要进入补考安排', steps: ['选择正式不及格成绩', '创建补考批次', '考试安排', '补考录分审核', '有效成绩归档'] },
        clearance: { title: '毕业清考', subtitle: '按学校政策圈定毕业年级，成绩回写后重新核验毕业资格', objectType: '毕业清考批次', source: '毕业年级与当前有效未通过课程', owner: '补重修责任岗', whyMe: '毕业资格仍被未通过课程阻断', steps: ['按学校政策圈定', '核验清考资格', '考试安排', '成绩审核发布', '资格重新核验'] },
        deferred: { title: '缓考合流', subtitle: '只处理已批准缓考申请，并入精确补考批次后继续录分归档', objectType: '缓考合流安排', source: '原考试名单与已批准缓考申请', owner: '补重修责任岗', whyMe: '缓考申请已批准，等待安排后续考试', steps: ['学生申请缓考', '原节点审核', '批准后考试安排', '合流录分', '有效成绩归档'] }
      }
      return specs[this.tab] || { title: this.tabs.find(item => item.key === this.tab)?.label || '补考与修读', subtitle: '先核对来源对象，再办理当前责任节点' }
    },
    focusedProcessRow() { if (!this.examFlowMode) return null; const key = this.activeProcessKey; return this.rows.find(row => this.processKey(row) === key) || this.rows[0] || null },
    processStage() { const row = this.focusedProcessRow; if (!row) return 0; if (this.tab === 'deferred') return row.nextBatchRef ? 3 : 2; const status = String(row.status || '').toUpperCase(); if (this.tab === 'clearance') return ({ DRAFT: 0, ARRANGED: 1, PUBLISHED: 2, SCORING: 3, REVIEWED: 3, FINISHED: 4 })[status] ?? 0; return ({ DRAFT: 1, ARRANGED: 2, PUBLISHED: 3, SCORING: 3, REVIEWED: 3, FINISHED: 4 })[status] ?? 0 },
    processStatusLabel() { if (!this.focusedProcessRow) return '—'; return this.tab === 'deferred' ? (this.focusedProcessRow.nextBatchRef ? '已合流' : '待安排') : this.mbLabel(this.focusedProcessRow.status) },
    processBlocker() { const row = this.focusedProcessRow; if (!row) return '当前范围没有可办理对象'; if (this.tab === 'deferred') return row.nextBatchRef ? '已合流，等待目标批次录分' : '需选择仍可接收名单的目标补考批次'; const status = String(row.status || '').toUpperCase(); if (this.tab === 'clearance') return ({ DRAFT: '需按学校政策核验并正式圈定名单', ARRANGED: '名单已圈定，等待考试安排或发布', PUBLISHED: '等待清考录分', SCORING: '存在待录入或待审核成绩', REVIEWED: '等待教务发布回写', FINISHED: '已回写，等待毕业资格重新核验' })[status] || '按正式批次状态核对'; return ({ DRAFT: '需从正式不及格成绩纳入名单', ARRANGED: '名单已编排，等待发布考试安排', PUBLISHED: '等待补考录分', SCORING: '存在待录入或待审核成绩', REVIEWED: '等待教务发布回写', FINISHED: '已归档为有效成绩结果' })[status] || '按正式批次状态核对' },
    processNextOwner() { const row = this.focusedProcessRow; if (!row) return '待形成正式对象后确定'; if (this.tab === 'deferred') return row.nextBatchRef ? '补考录分岗' : '补考批次安排岗'; const status = String(row.status || '').toUpperCase(); if (status === 'FINISHED') return this.tab === 'clearance' ? '毕业资格审核岗' : '成绩与学业预警责任岗'; if (status === 'REVIEWED') return '教务成绩发布岗'; if (['PUBLISHED', 'SCORING'].includes(status)) return '补考 / 清考录分岗'; if (status === 'ARRANGED') return '考试安排发布岗'; return '补重修责任岗' },
    /** 只有草稿/已编排阶段能继续纳入；发布后名单已对学生成立，后端也会 409。 */
    canEnroll() { return this.canManage && !!this.mkBatch && ['DRAFT', 'ARRANGED'].includes(this.mkBatch.status) },
    canScoreMakeup() { return this.canManage && !!this.mkBatch && ['PUBLISHED', 'SCORING'].includes(this.mkBatch.status) },
    /** 已纳入的原始成绩ID集合，避免候选里重复点「纳入」（后端幂等，这里只是别误导人）。 */
    enrolledGradeIds() {
      return new Set(this.mkRows.map((r) => String(r.originGradeId || '')).filter(Boolean))
    },
    applicationSteps() {
      return this.tab === 'retake'
        ? ['学生申请重修', '核验原正式成绩', '节点审批', '新修读安排', '有效成绩归档']
        : ['学生免修申请', '佐证材料核验', '节点审批', '课程认定', '材料归档']
    },
    applicationStage() {
      const status = String(this.activeApplication?.status || '').toUpperCase()
      if (this.tab === 'retake') return ({ SUBMITTED: 1, ACADEMIC_REVIEW: 2, APPROVED: 3, ENROLLED: 4, FINISHED: 4, REJECTED: 2 })[status] ?? 0
      return ({ SUBMITTED: 0, TEACHER_REVIEW: 1, COLLEGE_REVIEW: 2, ACADEMIC_REVIEW: 2, APPROVED: 4, REJECTED: 2, CANCELLED: 2 })[status] ?? 0
    }
  },
  created() {
    const q = this.$route.query.tab
    if (q && this.tabs.some(t => t.key === q)) this.tab = q
    this.restoreWrite();this.reload()
  },
  watch: {
    identityKey() { this.resetScope(); this.pagination.page = 1; this.reload() },
    '$route.query.tab'(value) { if (value !== this.tab && this.tabs.some(t => t.key === value)) this.switchTab(value, false) }
  },
  beforeUnmount() { this.alive = false; this.resetScope() },
  methods: {
    stateMeta, formatMoment, shortHash, gradeIdentity, gradeResult, gradeSource, evidenceVersion,
    formalEvidenceFiles(row) { return evidenceFiles(row) },
    formalActions(row) { return Array.isArray(row?.allowedActions) ? row.allowedActions.map(value => String(value || '').toUpperCase()).filter(Boolean) : [] },
    applicationCan(row, action) { return hasFormalAction(row, action) },
    revisionText(row) { const value=rowRevision(row,this.tab);return value==null?'版本待核对':`申请版本 ${value}` },
    objectTitle(row) { return `${this.tab === 'retake' ? '重修申请' : '免修申请'} #${row?.applyId || row?.exemptionId || '待核对'}` },
    courseIdentity(row) {
      const course=row?.course||{},grade=row?.originGrade||row?.resultGrade||{}
      const id=course.id||row?.courseId||grade.courseId
      const code=course.code||grade.courseCode
      const version=course.version??grade.courseVersion
      return [row?.courseName||course.name||'课程待核对',id?`课程 #${id}`:'课程ID待核对',code||'课程代码待核对',version==null?'课程版本待核对':`课程V${version}`].join(' · ')
    },
    evidenceProblems(row) { return Array.isArray(row?.evidenceProblems) ? row.evidenceProblems.filter(Boolean) : [] },
    blockers(row) {
      const source=this.tab==='retake'?row?.sourceGradeBlockers:row?.evidenceProblems
      return Array.isArray(source)?source.filter(Boolean):[]
    },
    actionText(row) {
      const labels={APPROVE:'通过本节点',REJECT:'驳回',RETURN:'退回补充材料',ENROLL:'编入正式教学任务'}
      const actions=this.formalActions(row)
      return actions.length?`服务端允许：${actions.map(action=>labels[action]||action).join('、')}`:'服务端未授权当前动作'
    },
    enrollmentLabel(row) { return row?.enrollment?.rosterCoverage==='FROZEN_AT_ENROLLMENT'?'编班版本已冻结':row?.status==='ENROLLED'?'编班来源待治理':'尚未编班' },
    rosterIdentity(row) {
      const enrollment=row?.enrollment||{}
      if(enrollment.rosterVersionId)return `名单版本 #${enrollment.rosterVersionId}${enrollment.rosterVersionNo==null?'':` · V${enrollment.rosterVersionNo}`}`
      return enrollment.rosterCoverage==='UNRESOLVED'?'当时名单版本无法证明':'完成编班后由服务端返回当时冻结名单版本'
    },
    hasEvidenceContract(row) {
      if(!row)return false
      return this.tab==='retake'
        ? Object.prototype.hasOwnProperty.call(row,'sourceGradeState')&&rowRevision(row,'retake')!=null&&Array.isArray(row.allowedActions)&&(row.sourceGradeState!=='RESOLVED'||Boolean(row.sourceEvidenceHash))
        : Object.prototype.hasOwnProperty.call(row,'evidenceState')&&Object.prototype.hasOwnProperty.call(row,'resultGradeState')&&rowRevision(row,'exemption')!=null&&Array.isArray(row.allowedActions)
    },
    commandIdentity(tab,row,action) {
      const expectedVersion=rowRevision(row,tab)
      if(expectedVersion==null)return null
      if(tab==='retake'){
        const expectedSourceEvidenceHash=String(row?.sourceEvidenceHash||'').trim()
        if(action!=='REJECT'&&!expectedSourceEvidenceHash)return null
        return action==='REJECT'?{expectedVersion}:{expectedVersion,expectedSourceEvidenceHash}
      }
      return {expectedVersion,expectedStatus:row?.status,expectedEvidenceManifestHash:row?.evidenceManifestHash??null}
    },
    sameApplicationSnapshot(current,snapshot,tab) {
      const revision=rowRevision(snapshot,tab)
      if(revision==null||rowRevision(current,tab)!==revision)return false
      if(tab==='retake')return String(current?.originGrade?.gradeId||'')===String(snapshot?.originGrade?.gradeId||'')&&String(current?.currentGrade?.gradeId||'')===String(snapshot?.currentGrade?.gradeId||'')&&String(current?.sourceEvidenceHash||'')===String(snapshot?.sourceEvidenceHash||'')&&current?.sourceGradeState===snapshot?.sourceGradeState
      return String(current?.course?.id||'')===String(snapshot?.course?.id||'')&&String(current?.evidenceManifestHash||'')===String(snapshot?.evidenceManifestHash||'')&&current?.evidenceState===snapshot?.evidenceState
    },
    freezeApplication(row) {
      return {
        ...row,
        course:{...(row?.course||{})},originGrade:{...(row?.originGrade||{})},currentGrade:{...(row?.currentGrade||{})},resultGrade:{...(row?.resultGrade||{})},
        enrollment:{...(row?.enrollment||{})},allowedActions:[...(row?.allowedActions||[])],
        sourceGradeBlockers:[...(row?.sourceGradeBlockers||[])],evidenceProblems:[...(row?.evidenceProblems||[])],
        evidenceFiles:(row?.evidenceFiles||[]).map(file=>({...file}))
      }
    },
    nextStep(row) {
      if(this.tab==='retake')return row?.status==='APPROVED'?'选择正式教学任务并编班':row?.status==='ENROLLED'?'等待新修读与有效成绩归档':'返回责任队列继续办理'
      return row?.status==='APPROVED'?'核对生成的正式成绩并进入材料归档':row?.status==='REJECTED'?'保留审批结论与材料证据':'由下一审批节点继续办理'
    },
    syncFormal(formal) {
      if(!formal)return
      for(const key of ['makeupId','applyId','exemptionId','batchId','deferId']){
        if(formal[key]==null)continue
        for(const rows of [this.rows,this.mkRows,this.crRows]){const row=rows.find(r=>String(r[key])===String(formal[key]));if(row)Object.assign(row,formal)}
        for(const row of [this.activeApplication,this.mkBatch,this.crBatch])if(row&&String(row[key])===String(formal[key]))Object.assign(row,formal)
      }
      if(formal.makeupId && ['SCORED','FINISHED'].includes(formal.status)){delete this.mkScores[formal.makeupId];delete this.crScores[formal.makeupId]}
    },
    async findFormal(tab, key, id, page=this.pagination.page) {
      if(!/^[1-9]\d*$/.test(String(id)))throw {code:422}
      const params={page:1,pageSize:2}
      const res=tab==='retake'&&key==='applyId'?await api.retakeApplies({...params,applyId:String(id)})
        :tab==='exemption'&&key==='exemptionId'?await api.exemptionApplies({...params,exemptionId:String(id)})
          :await this.readTab(tab,page)
      if(res.code!==0)throw res
      return res.data?.list?.find(row=>String(row[key])===String(id)) || null
    },
    recoveryKey(c){return 'aa-makeup-command:'+c.identity+':'+c.tab},
    persistWrite(p){globalThis.sessionStorage.setItem(this.recoveryKey(p),JSON.stringify({tab:p.tab,commandKey:p.commandKey||null,reference:p.reference||null}))},
    forgetWrite(p){globalThis.sessionStorage.removeItem(this.recoveryKey(p))},
    restoreWrite(){
      if(!this.alive)return
      const c=this.captureScope()
      try{const raw=globalThis.sessionStorage.getItem(this.recoveryKey(c));if(!raw)return
        const saved=JSON.parse(raw),ref=saved.reference
        if(saved.tab!==c.tab||(ref&&(!['MAKEUP_RETAKE_REVIEW','MAKEUP_RETAKE_ENROLL','MAKEUP_EXEMPTION_REVIEW'].includes(ref.operation)||
          !/^[1-9]\d*$/.test(ref.id)||!Number.isSafeInteger(ref.version)||ref.version<0||!/^[A-Za-z0-9_-]{8,128}$/.test(saved.commandKey))))throw new Error('原命令恢复引用不完整')
        const key=c.tab==='retake'?'applyId':'exemptionId'
        this.pendingWrite={...c,...saved,readReady:true,acknowledged:false,recovered:true,label:'原业务命令',description:'正在核对原命令与当前正式记录',
          read:()=>ref?this.findFormal(c.tab,key,ref.id,1):null,
          accept:(row,reply)=>rowRevision(row,c.tab)>=rowRevision(reply,c.tab)}
        this.writeReceipt={label:'原业务命令',description:'存在未决命令，请先只读核对',verified:false}
      }catch(err){this.pendingWrite={...c,readReady:true,recovered:true};this.writeReceipt={label:'原业务命令',description:'恢复引用暂不可读取，已阻止新命令',verified:false};this.error=err.message}
    },
    receiptMatches(p,reply){
      const ref=p.reference;if(!ref)return false
      const key=ref.operation.startsWith('MAKEUP_RETAKE_')?'applyId':'exemptionId'
      const next=ref.action==='ENROLL'?'ENROLLED':ref.action==='REJECT'?'REJECTED':ref.action==='RETURN'?'SUBMITTED':
        key==='applyId'?'APPROVED':({SUBMITTED:'TEACHER_REVIEW',TEACHER_REVIEW:'COLLEGE_REVIEW',COLLEGE_REVIEW:'ACADEMIC_REVIEW',ACADEMIC_REVIEW:'APPROVED'})[ref.status]
      return String(reply?.[key]||'')===ref.id&&rowRevision(reply,p.tab)===ref.version+1&&reply.status===next&&
        (ref.action!=='ENROLL'||String(reply.teachingTaskRef||'')===ref.target)
    },
    async runWrite({label,description='',before,write,read,accept,reference=null}) {
      if(this.saving || this.pendingWrite)return null
      const c=this.captureScope(),packet={...c,label,description,read,accept,reference,reply:null,acknowledged:false,readReady:false}
      this.pendingWrite=packet;this.writeReceipt={label,description,verified:false};this.saving=true;this.error=''
      let sent=false
      try {
        if(before && !await before())throw {code:409}
        if(!this.currentScope(c))return null
        if(reference){if(!globalThis.crypto?.randomUUID)throw new Error('无法生成可靠命令标识，本次未发送');packet.commandKey=globalThis.crypto.randomUUID();this.pendingWrite.commandKey=packet.commandKey}
        this.persistWrite(this.pendingWrite)
        sent=true
        let res;try{res=await write(packet.commandKey)}catch(err){res=err}
        if(!this.currentScope(c))return null
        if(res?.code!==0 && /403|404|409|422|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN|CONFLICT|VALIDATION/.test(String(res?.bizCode||res?.code||'')))throw res
        this.pendingWrite.reply=res?.code===0?res.data:null;this.pendingWrite.acknowledged=res?.code===0;this.pendingWrite.readReady=true
        return await this.verifyWrite()
      } catch(err) {
        if(!this.currentScope(c))return null
        if(!sent || /403|404|409|422|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN|CONFLICT|VALIDATION/.test(String(err?.bizCode||err?.code||''))) {if(sent)this.forgetWrite(this.pendingWrite);this.pendingWrite=null;this.writeReceipt=null}
        this.readError(err,sent?'结果待核实，请只读核对，不要重复操作。':'对象已变化或无法核对，本次未提交。')
        return null
      } finally {if(this.currentScope(c))this.saving=false}
    },
    async verifyWrite() {
      const p=this.pendingWrite
      if(!p || !p.readReady || this.checkingWrite || !this.currentScope(p))return null
      this.checkingWrite=true
      try {
        if(!p.acknowledged&&p.commandKey&&p.reference){
          const res=await api.commandReceipt(p.commandKey,p.reference.operation);if(!this.currentScope(p))return null
          if(res?.code!==0)throw res
          if(res.data?.commandKey!==p.commandKey||res.data.operation!==p.reference.operation||!['SUCCESS','UNRESOLVED'].includes(res.data.state))throw new Error('原命令回执标识不一致')
          if(res.data.state==='SUCCESS'){
            if(!this.receiptMatches(p,res.data.result))throw new Error('原命令回执与冻结申请或节点不一致')
            p.reply=res.data.result;p.acknowledged=true
          }
        }
        if(!p.read){this.error='原命令恢复引用无法读取，不能继续发送';return null}
        const formal=await p.read(p.reply)
        if(!this.currentScope(p))return null
        if(!p.acknowledged){this.error='已回读当前正式记录，但尚未取得本次命令回执，不能据此认定本次办理成功；请勿重复提交。';return null}
        if(['batchId','applyId','exemptionId','makeupId','deferId'].some(key=>p.reply?.[key]!=null&&String(p.reply[key])!==String(formal?.[key]??''))){this.error='正式记录与命令回执对象不一致，请只读核对原对象。';return null}
        if(!p.accept(formal,p.reply)){this.error='结果待核实：正式记录尚未反映本次办理结果，请勿重复提交。';return null}
        this.forgetWrite(p)
        this.syncFormal(formal)
        const objectId=formal?.applyId||formal?.exemptionId||formal?.makeupId||formal?.batchId||formal?.deferId
        this.writeReceipt={label:p.label,description:p.description,objectId,occurredAt:formal?.updatedAt,status:formal?.status,statusLabel:this.applicationStatus(formal),next:['retake','exemption'].includes(this.tab)?this.nextStep(formal):'',verified:true};this.pendingWrite=null;this.error=''
        return formal
      } catch(err){if(this.currentScope(p))this.readError(err,'结果待核实，请稍后只读核对。');return null}
      finally{if(this.currentScope(p))this.checkingWrite=false}
    },

    selectApplication(row) { if(this.saving||this.pendingWrite)return;this.cancelConfirmation();this.activeApplication=this.freezeApplication(row) },
    nodeLabel(node) { return ({SUBMITTED:'待补充后重新办理',TEACHER:'任课教师审核',TEACHER_REVIEW:'任课教师审核',COLLEGE:'学院审核',COLLEGE_REVIEW:'学院审核',ACADEMIC:'教务审核',ACADEMIC_REVIEW:'教务审核'})[node] || '当前责任节点待核对' },
    applicationStatus(row){return row?.status==='SUBMITTED'&&row?.currentNode==='SUBMITTED'&&row?.returnReason?'已退回，待补充材料':academicStatusLabel(row?.status)},
    academicStatusLabel,
    mbLabel(s) { return _MBL[s] || academicStatusLabel(s) },
    mbType(s) { return s === 'PUBLISHED' ? 'success' : s === 'FINISHED' ? 'default' : 'primary' },
    rtType(s) { return ['APPROVED', 'ENROLLED', 'FINISHED'].includes(s) ? 'success' : s === 'REJECTED' ? 'danger' : 'primary' },
    processKey(row) { return String(row?.batchId || row?.deferId || '') },
    focusProcess(row) { if (this.saving || this.pendingWrite) return; this.activeProcessKey = this.processKey(row) },
    processObjectTitle(row) { return this.tab === 'deferred' ? `${row.studentName || '学生待核对'} · ${row.courseName || '课程待核对'}` : (row.batchName || `${this.modeSpec.objectType} #${row.batchId || '待核对'}`) },
    processObjectIdentity(row) { if (this.tab === 'deferred') return `缓考申请 #${row.deferId || '待核对'}${row.nextBatchRef ? ` · 目标批次 ${row.nextBatchRef}` : ''}`; return `批次 #${row.batchId || '待核对'} · ${row.termCode || '学期待核对'}` },
    captureScope() { return { identity: this.identityKey, seq: this.scopeSeq, tab: this.tab } },
    currentScope(c) { return this.alive && c.identity === this.identityKey && c.seq === this.scopeSeq && c.tab === this.tab },
    resetScope() {
      this.activeApplication=null;this.retakeVisible=false;this.retakeRow=null;this.teachingTaskRef='';this.mkLoading=false;this.crLoading=false;this.candidateLoading=false;this.detailError=''
      for(const key of ['mkPagination','crPagination','candidatePagination'])this[key]={page:1,pageSize:20,total:0}
      this.batchForm={batchName:'',termCode:''};this.clearanceForm={batchName:'',grades:'',termCode:''};this.formError='';this.clearanceError=''
      this.pendingWrite=null;this.writeReceipt=null;this.checkingWrite=false
      this.scopeSeq++; this.readSeq++; this.mkSeq++; this.crSeq++; this.candidateSeq++
      this.rows=[]; this.activeProcessKey=''; this.mkRows=[]; this.crRows=[]; this.mkCandidates=[]; this.mkScores={}; this.crScores={}; this.mkBatch=null; this.crBatch=null; this.mergeRow=null; this.mergeBatchId=''; this.mkDebtCount=0
      this.mkVisible=false; this.crVisible=false; this.mergeVisible=false; this.batchVisible=false; this.clearanceVisible=false; this.confirmVisible=false; this.pendingAction=null
      this.reasonDialog={visible:false,title:'',reason:'',sceneKey:'',submitting:false,action:null}; this.saving=false; this.loading=false; this.error=''; this.pagination.total=0
      this.restoreWrite()
    },
    readError(err, fallback='读取失败，请重试。') {
      if (/403|NO_PERMISSION|FORBIDDEN/.test(String(err?.bizCode || err?.code || ''))) this.resetScope()
      this.error=gradeError(err, fallback);this.detailError=this.error
    },
    switchTab(k, updateRoute=true) { if(this.saving || this.pendingWrite || this.tab===k)return; this.resetScope(); this.tab=k; this.restoreWrite(); this.pagination.page=1; if(updateRoute)this.$router.replace({path:this.$route.path,query:{...this.$route.query,tab:k}}); this.reload() },
    changePage(page) { if(this.saving || this.pendingWrite)return;this.pagination.page=page;this.reload() },
    async readTab(tab, page=this.pagination.page) {
      const params={page,pageSize:this.pagination.pageSize}
      if(tab==='makeup')return api.listBatches({...params,kind:'MAKEUP'})
      if(tab==='clearance')return api.listBatches({...params,kind:'CLEARANCE'})
      if(tab==='retake')return api.retakeApplies(params)
      if(tab==='exemption')return api.exemptionApplies(params)
      return api.deferredPool(params)
    },
    async reload() {
      const c=this.captureScope(),seq=++this.readSeq,selectedId=this.activeApplication?.applyId||this.activeApplication?.exemptionId,selectedProcessKey=this.activeProcessKey
      const valid=()=>this.currentScope(c)&&seq===this.readSeq
      this.loading=true;this.error='';this.rows=[];this.activeApplication=null;this.pagination.total=0
      try { const res=await this.readTab(c.tab);if(!valid())return;if(res.code!==0)throw res;this.rows=res.data?.list||[];this.pagination.total=res.data?.total??this.rows.length;const active=this.rows.find(row=>String(row.applyId||row.exemptionId)===String(selectedId));this.activeApplication=active?this.freezeApplication(active):null;this.activeProcessKey=this.rows.some(row=>this.processKey(row)===selectedProcessKey)?selectedProcessKey:this.processKey(this.rows[0]) }
      catch(err) { if(valid())this.readError(err) }
      finally { if(valid())this.loading=false }
    },
    openCreateBatch() { if(!this.canManage||this.saving||this.pendingWrite)return;this.batchForm = { batchName: '', termCode: '' }; this.formError = ''; this.batchVisible = true },
    async submitBatch() {
      if(!this.canManage||this.saving||this.pendingWrite)return
      if(!this.batchForm.batchName.trim()){this.formError='批次名称必填';return}
      const body={...this.batchForm},page=1
      const formal=await this.runWrite({label:'新建补考批次',description:body.batchName,write:()=>api.createBatch(body),read:reply=>reply?.batchId?this.findFormal('makeup','batchId',reply.batchId,page):null,accept:row=>!!row&&row.batchName===body.batchName})
      if(formal){this.batchVisible=false;this.pagination.page=1;this.reload()}
    },
    act(fn,id,label) {
      if(!this.canManage||this.saving||this.pendingWrite)return
      const expected={publishBatch:['PUBLISHED','SCORING','REVIEWED','FINISHED'],collegeReview:['REVIEWED','FINISHED'],finishBatch:['FINISHED']}[fn]
      const row=this.rows.find(r=>String(r.batchId)===String(id));if(!row||!expected)return
      const c=this.captureScope(),page=this.pagination.page,status=row.status
      this.confirmTitle=label;this.confirmMessage=`${row.batchName} · 当前${this.mbLabel(status)}。服务器将重新核对名单与成绩。`
      this.pendingAction=async()=>{
        if(!this.currentScope(c))return null
        const formal=await this.runWrite({label,description:row.batchName,before:async()=>{const before=await this.findFormal(c.tab,'batchId',id,page);return before?.status===status},write:()=>api[fn](id),read:()=>this.findFormal(c.tab,'batchId',id,page),accept:row=>!!row&&expected.includes(row.status)})
        if(formal)this.reload();return formal
      }
      this.confirmVisible=true
    },
    printBatch(batchId) {
      this.$router.push(`/admin/academic-affairs/makeup/batches/${batchId}/print`)
    },
    review(fn,id,action) {
      if(this.saving||this.pendingWrite)return
      const key=fn==='retakeReview'?'applyId':'exemptionId',row=this.rows.find(r=>String(r[key])===String(id));if(!row)return
      if(!this.applicationCan(row,action)){this.error='服务端未授权当前动作，请重新读取责任队列。';return}
      const c=this.captureScope(),snapshot=this.freezeApplication(row)
      this.confirmTitle=action==='APPROVE'?'确认本节点通过':'确认办理';this.confirmMessage=`${row.studentName} · ${row.courseName} · ${academicStatusLabel(row.status)}。本节点通过不等于全部流程完成。`
      this.pendingAction=()=>this.currentScope(c)?this.processReview(fn,id,action,'',snapshot):null;this.confirmVisible=true
    },
    reviewResultMatches(tab,action,beforeStatus,reason,row) {
      if(!row)return false
      if(tab==='retake')return action==='APPROVE'?row.status==='APPROVED':action==='REJECT'&&row.status==='REJECTED'&&String(row.reviewReason||'').trim()===reason.trim()
      if(action==='RETURN')return row.status==='SUBMITTED'&&row.currentNode==='SUBMITTED'&&String(row.returnReason||'').trim()===reason.trim()
      if(action==='REJECT')return row.status==='REJECTED'&&row.currentNode==null&&String(row.returnReason||'').trim()===reason.trim()
      if(action!=='APPROVE')return false
      const next={SUBMITTED:'TEACHER_REVIEW',TEACHER_REVIEW:'COLLEGE_REVIEW',COLLEGE_REVIEW:'ACADEMIC_REVIEW',ACADEMIC_REVIEW:'APPROVED'}[beforeStatus]
      return !!next&&row.status===next&&(next==='APPROVED'?row.currentNode==null&&row.resultGradeState==='RESOLVED'&&!!row.resultGrade?.gradeId:row.currentNode===next)
    },
    writeRevisionMatches(tab,snapshot,formal,reply) {
      const before=rowRevision(snapshot,tab),current=rowRevision(formal,tab),ack=rowRevision(reply,tab)
      return before!=null&&current===before+1&&ack===current
    },
    async processReview(fn,id,action,reason,snapshot) {
      if(fn==='retakeReview'?!this.canReviewRetake:!this.canReviewExemption)return null
      const tab=fn==='retakeReview'?'retake':'exemption',key=tab==='retake'?'applyId':'exemptionId',page=this.pagination.page
      if(!this.applicationCan(snapshot,action)){this.error='服务端未授权当前动作，请重新读取责任队列。';return null}
      const identity=this.commandIdentity(tab,snapshot,action)
      if(!identity){this.error=tab==='retake'?'来源成绩版本证据未返回，不能提交当前动作。':'申请版本未返回，不能提交当前动作。';return null}
      const beforeNode=snapshot.currentNode,beforeStatus=snapshot.status
      const formal=await this.runWrite({label:action==='APPROVE'?'本节点审核':action==='RETURN'?'退回补充材料':'驳回申请',description:`${snapshot.studentName} · ${snapshot.courseName}`,
        before:async()=>{const row=await this.findFormal(tab,key,id,page);return row?.status===beforeStatus&&row?.currentNode===beforeNode&&this.applicationCan(row,action)&&this.sameApplicationSnapshot(row,snapshot,tab)},
        reference:{operation:tab==='retake'?'MAKEUP_RETAKE_REVIEW':'MAKEUP_EXEMPTION_REVIEW',id:String(id),version:rowRevision(snapshot,tab),action,status:beforeStatus},
        write:commandKey=>api[fn](id,action,reason,identity,commandKey),read:()=>this.findFormal(tab,key,id,page),
        accept:(row,reply)=>this.reviewResultMatches(tab,action,beforeStatus,reason,row)&&this.writeRevisionMatches(tab,snapshot,row,reply)})
      if(formal)this.reload();return formal
    },
    reject(fn,id) {
      if(this.saving||this.pendingWrite)return
      const key=fn==='retakeReview'?'applyId':'exemptionId',row=this.rows.find(r=>String(r[key])===String(id));if(!row)return
      if(!this.applicationCan(row,'REJECT')){this.error='服务端未授权驳回，请重新读取责任队列。';return}
      const c=this.captureScope(),snapshot=this.freezeApplication(row)
      this.reasonDialog={visible:true,title:`驳回：${row.studentName} · ${row.courseName}`,reason:'',sceneKey:'aa.makeup.reject',submitting:false,action:reason=>this.currentScope(c)?this.processReview(fn,id,'REJECT',reason,snapshot):null}
    },
    returnEx(id) {
      if(this.saving||this.pendingWrite)return
      const row=this.rows.find(r=>String(r.exemptionId)===String(id));if(!row)return
      if(!this.applicationCan(row,'RETURN')){this.error='服务端未授权退回，请重新读取责任队列。';return}
      const c=this.captureScope(),snapshot=this.freezeApplication(row)
      this.reasonDialog={visible:true,title:`退回补材料：${row.studentName} · ${row.courseName}`,reason:'',sceneKey:'aa.makeup.supplement',submitting:false,action:reason=>this.currentScope(c)?this.processReview('exemptionReview',id,'RETURN',reason,snapshot):null}
    },
    async onReasonConfirm() {
      const dialog=this.reasonDialog,reason=String(dialog.reason||'').trim()
      if(this.saving||this.pendingWrite||!dialog.action||reason.length<5)return
      dialog.submitting=true
      try{const formal=await dialog.action(reason);if(this.reasonDialog===dialog&&formal)dialog.visible=false}
      finally{if(this.reasonDialog===dialog)dialog.submitting=false}
    },
    enrollRetake(id) {
      if(!this.canReviewRetake||this.saving||this.pendingWrite)return
      const row=this.rows.find(r=>String(r.applyId)===String(id));if(row?.status!=='APPROVED')return
      if(!this.applicationCan(row,'ENROLL')){this.error='服务端未授权编班，请重新读取责任队列。';return}
      this.retakeRow=this.freezeApplication(row);this.teachingTaskRef='';this.retakeVisible=true
    },
    async submitRetake() {
      if(!this.canReviewRetake||!this.retakeRow||!this.teachingTaskRef||this.saving||this.pendingWrite)return
      const row=this.freezeApplication(this.retakeRow),target=String(this.teachingTaskRef),page=this.pagination.page
      const identity=this.commandIdentity('retake',row,'ENROLL')
      if(!identity){this.error='来源成绩版本证据未返回，不能提交编班。';return}
      const formal=await this.runWrite({label:'重修编入跟班',description:`${row.studentName} · ${row.courseName}`,
        before:async()=>{const current=await this.findFormal('retake','applyId',row.applyId,page);return current?.status==='APPROVED'&&this.applicationCan(current,'ENROLL')&&this.sameApplicationSnapshot(current,row,'retake')},
        reference:{operation:'MAKEUP_RETAKE_ENROLL',id:String(row.applyId),version:rowRevision(row,'retake'),action:'ENROLL',status:row.status,target},
        write:commandKey=>api.retakeEnroll(row.applyId,target,identity,commandKey),read:()=>this.findFormal('retake','applyId',row.applyId,page),
        accept:(formal,reply)=>formal?.status==='ENROLLED'&&String(formal.enrollment?.teachingTaskId||'')===target&&formal.enrollment?.rosterCoverage==='FROZEN_AT_ENROLLMENT'&&this.writeRevisionMatches('retake',row,formal,reply)})
      if(formal){this.retakeVisible=false;this.reload()}
    },
    openMerge(row) { if(!this.canManage||this.saving||this.pendingWrite)return;this.mergeRow = {...row}; this.mergeBatchId = ''; this.mergeVisible = true },
    async submitMerge() {
      if(!this.canManage||!this.mergeRow||this.saving||this.pendingWrite)return
      if(!this.mergeBatchId){this.error='请选择目标补考批次。';return}
      const row={...this.mergeRow},target=String(this.mergeBatchId),page=this.pagination.page
      const formal=await this.runWrite({label:'缓考并入补考批次',description:`${row.studentName} · ${row.courseName}`,
        before:async()=>{const r=await this.findFormal('deferred','deferId',row.deferId,page);return !!r&&!r.nextBatchRef},
        write:()=>api.mergeDeferred(row.deferId,target),read:()=>this.findFormal('deferred','deferId',row.deferId,page),
        accept:r=>!!r&&String(r.nextBatchRef)===target})
      if(formal){this.mergeVisible=false;this.reload()}
    },
    openCreateClearance() { if(!this.canManage||this.saving||this.pendingWrite)return;this.clearanceForm = { batchName: '', grades: '', termCode: '' }; this.clearanceError = ''; this.clearanceVisible = true },
    async submitClearance() {
      if(!this.canManage||this.saving||this.pendingWrite)return
      const grades=this.clearanceForm.grades.split(/[,，、\s]+/).filter(Boolean)
      if(!this.clearanceForm.batchName.trim()){this.clearanceError='批次名称必填';return}if(!grades.length){this.clearanceError='必须限定毕业年级';return}
      const body={batchName:this.clearanceForm.batchName,targetGrades:grades,termCode:this.clearanceForm.termCode||undefined}
      const formal=await this.runWrite({label:'新建毕业清考批次',description:body.batchName,write:()=>api.createClearanceBatch(body),read:reply=>reply?.batchId?this.findFormal('clearance','batchId',reply.batchId,1):null,accept:row=>!!row&&row.batchName===body.batchName})
      if(formal){this.clearanceVisible=false;this.pagination.page=1;this.reload()}
    },
    async scanClearance(row, dryRun) {
      if(!this.canManage||this.saving||this.pendingWrite)return
      const c=this.captureScope(),batch={...row},page=this.pagination.page
      if(dryRun){
        this.saving=true
        try{const res=await api.clearanceScan(batch.batchId,true);if(!this.currentScope(c))return;if(res?.code!==0)throw res
          this.writeReceipt={label:'名单预览（尚未圈定）',description:`${batch.batchName} · ${res.data?.candidates ?? '待核对'}条候选`,verified:false}
        }catch(err){if(this.currentScope(c))this.readError(err)}finally{if(this.currentScope(c))this.saving=false}
        return
      }
      this.confirmTitle='确认圈定清考名单';this.confirmMessage=`${batch.batchName} · ${(batch.targetGrades||[]).join('、')}。服务器重新核对当前未通过课程；预览不是正式名单。`
      this.pendingAction=async()=>{
        if(!this.currentScope(c))return null
        const formal=await this.runWrite({label:'圈定清考名单',description:batch.batchName,
          before:async()=>{const r=await this.findFormal('clearance','batchId',batch.batchId,page);return !!r&&['DRAFT','ARRANGED'].includes(r.status)},
          write:()=>api.clearanceScan(batch.batchId,false),
          read:async()=>{const res=await api.clearanceRecords(batch.batchId,{page:1,pageSize:20});if(res?.code!==0)throw res;return res.data},
          accept:(data,reply)=>!!reply&&Array.isArray(reply.items)&&Array.isArray(data?.list)&&reply.items.every(item=>data.list.some(r=>String(r.originGradeId)===String(item.gradeId)&&String(r.acadStudentId)===String(item.acadStudentId)))})
        if(formal)this.reload();return formal
      };this.confirmVisible=true
    },
    async readRecord(kind,batchId,recordId,page) {
      const res=await (kind==='clearance'?api.clearanceRecords:api.batchRecords)(batchId,{page,pageSize:20})
      if(res?.code!==0)throw res
      return res.data?.list?.find(r=>String(r.makeupId)===String(recordId))||null
    },
    async openClearanceRecords(row) {
      if(this.saving||this.pendingWrite)return
      this.cancelConfirmation()
      this.crBatch={...row};this.crScores={};this.crRows=[];this.crPagination.page=1;this.crVisible=true
      await this.loadClearanceRecords()
    },
    async loadClearanceRecords(page=this.crPagination.page) {
      if(!this.crBatch)return
      const c=this.captureScope(),seq=++this.crSeq,bid=this.crBatch.batchId
      const valid=()=>this.currentScope(c)&&seq===this.crSeq&&String(this.crBatch?.batchId)===String(bid)
      this.crPagination.page=page;this.crLoading=true;this.detailError='';this.crRows=[]
      try{const res=await api.clearanceRecords(bid,{page,pageSize:20});if(!valid())return;if(res?.code!==0)throw res;this.crRows=res.data?.list||[];this.crPagination.total=res.data?.total??this.crRows.length}
      catch(err){if(valid()){this.detailError=gradeError(err);this.readError(err)}}finally{if(valid())this.crLoading=false}
    },
    async submitClearanceScore(row) { return this.submitScore('clearance',row) },
    async openMakeupRecords(row) {
      if(this.saving||this.pendingWrite)return
      this.cancelConfirmation()
      const c=this.captureScope()
      this.mkBatch={...row};this.mkScores={};this.mkCandidates=[];this.mkDebtCount=0;this.mkRows=[];this.mkPagination.page=1;this.candidatePagination.page=1;this.mkVisible=true
      await this.loadMakeupRecords()
      if(this.currentScope(c)&&String(this.mkBatch?.batchId)===String(row.batchId)&&this.canEnroll)await this.loadMakeupCandidates()
    },
    async loadMakeupRecords(page=this.mkPagination.page) {
      if(!this.mkBatch)return
      const c=this.captureScope(),seq=++this.mkSeq,bid=this.mkBatch.batchId
      const valid=()=>this.currentScope(c)&&seq===this.mkSeq&&String(this.mkBatch?.batchId)===String(bid)
      this.mkPagination.page=page;this.mkLoading=true;this.detailError='';this.mkRows=[]
      try{const res=await api.batchRecords(bid,{page,pageSize:20});if(!valid())return;if(res?.code!==0)throw res;this.mkRows=res.data?.list||[];this.mkPagination.total=res.data?.total??this.mkRows.length}
      catch(err){if(valid()){this.detailError=gradeError(err);this.readError(err)}}finally{if(valid())this.mkLoading=false}
    },
    async loadMakeupCandidates(page=this.candidatePagination.page) {
      if(!this.mkBatch)return
      const c=this.captureScope(),seq=++this.candidateSeq,bid=this.mkBatch.batchId
      const valid=()=>this.currentScope(c)&&seq===this.candidateSeq&&String(this.mkBatch?.batchId)===String(bid)
      this.candidatePagination.page=page;this.candidateLoading=true;this.mkCandidates=[];this.mkDebtCount=0
      try{const res=await api.makeupPending({termCode:this.mkBatch.termCode||undefined,page,pageSize:20});if(!valid())return;if(res?.code!==0)throw res;this.mkCandidates=res.data?.list||[];this.mkDebtCount=this.mkCandidates.filter(r=>!r.identityReady).length;this.candidatePagination.total=res.data?.total??this.mkCandidates.length}
      catch(err){if(valid()){this.detailError=gradeError(err);this.readError(err)}}finally{if(valid())this.candidateLoading=false}
    },
    enrollCandidate(row) {
      if(!this.canEnroll||!row.identityReady||!row.gradeId||!row.acadStudentId||this.enrolledGradeIds.has(String(row.gradeId))||this.saving||this.pendingWrite)return
      const c=this.captureScope(),batch={...this.mkBatch},candidate={...row},page=this.pagination.page
      this.confirmTitle='确认纳入补考名单';this.confirmMessage=`${candidate.studentName} · ${candidate.courseName} · ${batch.batchName}。服务器重新核对该条有效不及格成绩。`
      this.pendingAction=async()=>{
        if(!this.currentScope(c))return null
        const formal=await this.runWrite({label:'纳入补考名单',description:`${candidate.studentName} · ${candidate.courseName}`,
          before:async()=>{const r=await this.findFormal('makeup','batchId',batch.batchId,page);return !!r&&['DRAFT','ARRANGED'].includes(r.status)},
          write:()=>api.enroll(batch.batchId,{gradeId:String(candidate.gradeId),acadStudentId:String(candidate.acadStudentId)}),
          read:async()=>{const res=await api.batchRecords(batch.batchId,{page:1,pageSize:2,originGradeId:String(candidate.gradeId),acadStudentId:String(candidate.acadStudentId)});if(res?.code!==0)throw res;return res.data?.list?.find(r=>String(r.originGradeId)===String(candidate.gradeId)&&String(r.acadStudentId)===String(candidate.acadStudentId))||null},
          accept:r=>!!r})
        if(formal){await this.loadMakeupRecords();if(this.currentScope(c))this.reload()}return formal
      };this.confirmVisible=true
    },
    async submitMakeupScore(row) { return this.submitScore('makeup',row) },
    async submitScore(kind,row) {
      if(!this.canManage||this.saving||this.pendingWrite)return
      const isClearance=kind==='clearance',batch=isClearance?this.crBatch:this.mkBatch,scores=isClearance?this.crScores:this.mkScores
      if(!batch||!['PUBLISHED','SCORING'].includes(batch.status)||['SCORED','FINISHED'].includes(row.status))return
      const raw=scores[row.makeupId]
      if(raw==null||String(raw).trim()===''||!Number.isInteger(Number(raw))||Number(raw)<0||Number(raw)>100){this.detailError='请填写0至100的整数成绩；空白不代表0分。';return}
      const value=Number(raw),record={...row},bid=batch.batchId,page=(isClearance?this.crPagination:this.mkPagination).page,c=this.captureScope()
      const formal=await this.runWrite({label:isClearance?'清考录分':'补考录分',description:`${record.studentName} · ${record.courseName} · ${value}分`,
        before:async()=>{const r=await this.readRecord(kind,bid,record.makeupId,page);return !!r&&r.status===record.status&&r.finalScore===record.finalScore},
        write:()=>api.score(record.makeupId,value),read:()=>this.readRecord(kind,bid,record.makeupId,page),
        accept:r=>!!r&&['SCORED','FINISHED'].includes(r.status)&&r.finalScore!=null&&Number(r.finalScore)===value})
      if(formal&&this.currentScope(c)){
        const rows=isClearance?this.crRows:this.mkRows,target=rows.find(r=>String(r.makeupId)===String(record.makeupId))
        if(target)Object.assign(target,formal)
        delete scores[record.makeupId];this.detailError='';this.reload()
      }
      return formal
    },
    cancelConfirmation(){this.confirmVisible=false;this.pendingAction=null;this.reasonDialog.visible=false;this.reasonDialog.action=null},
    async onConfirm() { if(this.saving||this.pendingWrite)return;const a=this.pendingAction,c=this.captureScope();if(!a)return;const formal=await a();if(this.currentScope(c)&&formal){this.confirmVisible=false;this.pendingAction=null} }
  }
}
</script>

<style scoped>
.aamk-process { display:grid;gap:0;margin-bottom:16px;overflow:hidden;border:1px solid #d9e3f0;border-radius:10px;background:#fff; }
.aamk-process>header { display:flex;align-items:center;justify-content:space-between;gap:16px;padding:14px 16px;border-bottom:1px solid #e4ebf3;background:#f8fbff; }
.aamk-process>header>div { display:grid;gap:4px; }.aamk-process>header span,.aamk-process>header small { color:#74849a;font-size:11px; }.aamk-process>header strong { color:#263e5c;font-size:14px; }
.aamk-process__stages { display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:0;margin:0;padding:14px 16px;list-style:none;border-bottom:1px solid #e4ebf3; }
.aamk-process__stages li { position:relative;display:flex;align-items:flex-start;gap:8px;color:#75849a; }.aamk-process__stages li:not(:last-child)::after { position:absolute;top:11px;left:29px;right:8px;height:1px;background:#dbe4ee;content:''; }
.aamk-process__stages li>span { z-index:1;display:grid;place-items:center;flex:0 0 23px;width:23px;height:23px;border:1px solid #d4deea;border-radius:50%;background:#fff;font-size:11px; }.aamk-process__stages li.done>span { border-color:#acd8bd;background:#ebf7ef;color:#16834a; }.aamk-process__stages li.current>span { border-color:#2f67ba;background:#2f67ba;color:#fff; }
.aamk-process__stages strong,.aamk-process__stages small { display:block;font-size:11px;line-height:1.4; }.aamk-process__stages small { margin-top:3px;color:#95a1b1;font-weight:400; }
.aamk-process__facts { display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;margin:0;background:#e3eaf2; }.aamk-process__facts>div { min-height:58px;padding:10px 13px;background:#fff; }.aamk-process__facts dt { color:#7b899b;font-size:10px; }.aamk-process__facts dd { margin:5px 0 0;color:#344a67;font-size:12px;font-weight:600;line-height:1.45; }
.aamk-focus { padding:0;border:0;background:transparent;color:#245aa5;font:inherit;font-weight:650;cursor:pointer; }.aamk-focus+small { display:block;margin-top:3px;color:#8190a3;font-size:10px; }
.aamk-review { display:grid;grid-template-columns:260px minmax(0,1fr);gap:16px; }
.aamk-queue,.aamk-evidence { border:1px solid var(--border-200, #e1e7ef);border-radius:10px;background:var(--bg-white, #fff);overflow:hidden; }
.aamk-queue h3,.aamk-evidence__head { margin:0;padding:16px;border-bottom:1px solid var(--border-200, #e1e7ef); }
.aamk-evidence__head { display:flex;align-items:flex-start;justify-content:space-between;gap:16px; }
.aamk-evidence__head h3,.aamk-evidence__head p { margin:0; }
.aamk-evidence__head p { margin-top:6px;font-size:12px;color:var(--text-secondary,#64748b); }
.aamk-object { width:100%;display:flex;flex-direction:column;align-items:flex-start;gap:8px;padding:16px;text-align:left;background:transparent;border:0;border-bottom:1px solid var(--border-200, #e1e7ef);cursor:pointer; }
.aamk-object.selected { background:var(--primary-50,#eaf0ff);box-shadow:inset 3px 0 var(--primary-color,#2563eb); }
.aamk-object span,.aamk-object small,.aamk-muted { font-size:12px;color:var(--text-secondary,#64748b); }
.aamk-stage { display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:0;margin:0;padding:16px;list-style:none;border-bottom:1px solid var(--border-200,#e1e7ef); }
.aamk-stage li { display:flex;align-items:flex-start;gap:8px;position:relative;color:var(--text-secondary,#64748b); }
.aamk-stage li:not(:last-child)::after { content:'';position:absolute;left:30px;right:8px;top:12px;height:1px;background:var(--border-200,#e1e7ef); }
.aamk-stage li>span { width:24px;height:24px;display:grid;place-items:center;flex:0 0 24px;border:1px solid var(--border-200,#e1e7ef);border-radius:50%;background:#fff;font-size:12px;z-index:1; }
.aamk-stage li.done>span { border-color:#b7dfc7;background:#edf8f1;color:#16834a; }
.aamk-stage li.current>span { border-color:var(--primary-color,#2563eb);background:var(--primary-color,#2563eb);color:#fff; }
.aamk-stage strong,.aamk-stage small { display:block;font-size:12px;line-height:1.45; }
.aamk-stage small { margin-top:3px;font-weight:400;color:var(--text-tertiary,#94a3b8); }
.aamk-facts { display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;padding:16px; }
.aamk-facts article { padding:16px;border:1px solid var(--border-200, #e1e7ef);border-radius:8px; }
.aamk-fact-title { display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px; }
.aamk-facts p { margin:5px 0;line-height:1.6;font-size:13px;overflow-wrap:anywhere; }
.aamk-danger { color:var(--danger-color,#c2413a); }
.aamk-evidence-list { display:grid;gap:8px;margin:8px 0 0;padding:0;list-style:none; }
.aamk-evidence-list li { display:grid;gap:3px;padding-top:8px;border-top:1px solid var(--border-100,#eef2f6);font-size:12px; }
.aamk-evidence-list span,.aamk-evidence-list small { color:var(--text-secondary,#64748b);overflow-wrap:anywhere; }
.aamk-evidence footer,.aamk-paging { display:flex;gap:12px;align-items:center;padding:16px; }
@media(max-width:1180px){.aamk-stage{grid-template-columns:1fr;gap:8px}.aamk-stage li:not(:last-child)::after{display:none}.aamk-process__facts{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:1000px){.aamk-review{grid-template-columns:220px minmax(0,1fr)}.aamk-facts{grid-template-columns:1fr}.aamk-process__stages{grid-template-columns:1fr;gap:8px}.aamk-process__stages li:not(:last-child)::after{display:none}}

.aamk-receipt { margin-bottom:16px;padding:16px;border:1px solid var(--border-200, #e1e7ef);border-radius:10px;background:var(--bg-white, #fff); }
.aamk-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-color, #e5e7eb); margin-bottom: 16px; }
.aamk-tab { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; }
.aamk-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 600; }
.aamk-bar { margin-bottom: 8px; }
.aamk-form { display: flex; flex-direction: column; gap: 12px; }
.aamk-score-input { width: 82px; padding: 4px 8px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 6px; font-size: 13px; }
.aamk-sub { margin: 16px 0 8px; font-size: 14px; font-weight: 600; color: var(--text-primary, #1f2937); }
</style>
