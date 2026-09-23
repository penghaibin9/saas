<template>
  <ModulePageShell
    :title="pageMeta.title"
    :subtitle="pageMeta.subtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton v-if="viewMode === 'exam' && schoolExamScope" variant="primary" @click="openCreate">创建考试批次</AppButton>
      <AppButton v-else size="small" variant="ghost" :disabled="loading" @click="load">刷新正式数据</AppButton>
    </template>

    <section v-if="teacherExamView" aria-label="本人正式监考安排">
      <h2>我的监考安排</h2>
      <p>按本人当前正式监考指派展示。考试时间、教室或监考人调整后，请刷新核对。</p>
      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!myInvigilations.length" title="暂无正式监考安排" description="这里只展示本人已发布且尚未过期的安排。" />
      <DataTable v-else :columns="invigilationColumns" :rows="myInvigilations" row-key="invigilatorId">
        <template #cell-course="{ row }"><strong>{{ row.courseName }}</strong><p>{{ row.batchName }}</p></template>
        <template #cell-when="{ row }">{{ row.examDate }} {{ row.startTime }}—{{ row.endTime }}</template>
        <template #cell-duty="{ row }">{{ row.role === 'CHIEF' ? '主监考' : row.role === 'ASSISTANT' ? '监考' : '监考职责待核对' }}</template>
        <template #cell-state="{ row }">{{ row.workStatus === 'FINISHED' ? '考试已结束' : '待监考' }}</template>
        <template #cell-actions="{ row }"><AppButton size="small" variant="ghost" @click="myExamBatch = { batchId: row.batchId, batchName: row.batchName, status: row.batchStatus }">查看考场异常</AppButton></template>
      </DataTable>
      <AaExamIncidentWorkbench v-if="myExamBatch" :key="myExamBatch.batchId" :batch="myExamBatch" />
    </section>
    <AaExamObjectBar v-else v-bind="objectBar" />
    <AaExamStageRail v-if="!teacherExamView && (current || selectedDefer || selectedArchive)" :steps="stageSteps" :active-index="stageIndex" :aria-label="pageMeta.title + '办理阶段'" />

    <div v-if="viewMode === 'exam' && !teacherExamView" class="aaexam-layout">
      <div class="aaexam-list">
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="暂无考试批次" description="点击右上角新建" />
        <ul v-else class="aaexam-batches">
          <li v-for="b in rows" :key="b.batchId"
              :class="['aaexam-batch', { 'is-active': current && current.batchId === b.batchId }]"
              @click="select(b)">
            <div class="aaexam-batch-name">{{ b.batchName }}</div>
            <StatusTag :type="statusType(b.status)" :label="statusLabel(b.status)" dot />
          </li>
        </ul>
      </div>

      <div class="aaexam-detail">
        <EmptyState v-if="!current" title="选择一个批次" description="从左侧选择批次以圈定课程、编排考场与监考" />
        <template v-else>
          <div class="aaexam-head">
            <div>
              <div class="aaexam-title">{{ current.batchName }}</div>
              <StatusTag :type="statusType(current.status)" :label="statusLabel(current.status)" dot />
            </div>
            <div v-if="schoolExamScope" class="aaexam-actions">
              <AppButton v-if="current.status === 'DRAFT'" size="small" variant="ghost" @click="openAddCourse">+ 批量圈课</AppButton>
              <AppButton v-if="current.status === 'DRAFT'" size="small" variant="primary" @click="lc('confirmBatchCourses', '推进(课程确认完成)')">推进</AppButton>
              <AppButton v-if="['COURSE_CONFIRMED','PUBLISHED'].includes(current.status)" size="small" variant="ghost" @click="openPatrol">巡考安排</AppButton>
              <AppButton v-if="current.status === 'COURSE_CONFIRMED'" size="small" variant="ghost" :loading="autoArranging" @click="openAutoPlan">自动排考</AppButton>
              <AppButton
                v-if="current.status === 'COURSE_CONFIRMED'"
                size="small"
                variant="primary"
                @click="lc('publishBatch', '发布')"
              >发布</AppButton>
              <AppButton v-if="current.status === 'PUBLISHED'" size="small" variant="warning" @click="lc('finishBatch', '结束考试')">结束</AppButton>
              <AppButton v-if="current.status === 'FINISHED'" size="small" variant="ghost" @click="lc('archiveBatch', '归档')">归档</AppButton>
            </div>
          </div>

          <AppInlineAlert
            v-if="readinessError"
            type="danger"
            :description="'考务数据核对失败：' + readinessError + '；请重新读取后核对'"
          />
          <AppInlineAlert v-if="!schoolExamScope" type="info" description="当前办理本学院课程确认与考场编排；批次推进、发布及全校就绪检查由教务处办理。" />
          <div v-if="readiness" class="aaexam-readiness" aria-label="考务发布就绪摘要">
            <div class="aaexam-readiness__item">
              <span>应考课程</span>
              <strong>{{ readiness.eligibleCourseCount }}</strong>
              <small>本批次已圈定 {{ readiness.circledCourseCount }} 门 · 同学期另有 {{ readiness.pendingCandidateCount }} 门候选</small>
            </div>
            <div class="aaexam-readiness__item">
              <span>已排</span>
              <strong>{{ readiness.arrangedCourseCount }}</strong>
              <small>已确认 {{ readiness.confirmedCourseCount }}</small>
            </div>
            <div class="aaexam-readiness__item" :class="{ 'is-risk': readiness.missedCourseCount }">
              <span>漏排</span>
              <strong>{{ readiness.missedCourseCount }}</strong>
              <small>只需继续处理异常课程</small>
            </div>
            <div class="aaexam-readiness__item" :class="{ 'is-risk': readiness.invigilatorGapCount }">
              <span>监考缺口</span>
              <strong>{{ readiness.invigilatorGapCount }}</strong>
              <small>缺口考场数</small>
            </div>
            <div class="aaexam-readiness__item" :class="{ 'is-risk': readiness.roomShortageCount }">
              <span>教室不足</span>
              <strong>{{ readiness.roomShortageCount }}</strong>
              <small>容量不足或尚无考场</small>
            </div>
            <div class="aaexam-readiness__item is-conclusion" :class="readiness.canPublish ? 'is-ready' : 'is-risk'">
              <span>就绪提示</span>
              <strong>{{ readiness.canPublish ? '就绪检查通过' : '存在待处理提示' }}</strong>
              <small>{{ readiness.canPublish ? '仍以正式发布校验为准' : '仍可尝试发布，由正式门禁最终判定' }}</small>
            </div>
          </div>

          <AppInlineAlert
            v-if="readiness && !readiness.canPublish && readiness.blockingReasons && readiness.blockingReasons.length"
            type="warning"
            :description="'就绪检查提示：' + readiness.blockingReasons.join('；')"
          />

          <div v-if="stats" class="aaexam-stats">
            <span>已圈课程 {{ stats.courseCount }}</span>
            <span>已确认 {{ stats.confirmedCount }}</span>
            <span :class="{ 'is-warn': stats.absentCount }">缺考 {{ stats.absentCount }}</span>
            <span :class="{ 'is-warn': stats.violationCount }">违纪 {{ stats.violationCount }}</span>
          </div>

          <template v-if="autoResult && autoResult.batchId === String(current.batchId)">
            <AppInlineAlert
              v-if="autoResult.timePlan && autoResult.timePlan.misses && autoResult.timePlan.misses.length"
              type="warning"
              :description="'自动定时未放下 ' + autoResult.timePlan.misses.length + ' 门：' + autoResult.timePlan.misses.map(m => `${m.courseName}（${m.reasonLabel}）`).join('；')"
            />
            <AppInlineAlert
              v-if="autoResult.misses && autoResult.misses.length"
              type="warning"
              :description="'自动排考漏排 ' + autoResult.misses.length + ' 门：' + autoResult.misses.map(m => `${m.courseName}（${m.reasonLabel}——${m.detail}）`).join('；')"
            />
            <AppInlineAlert
              v-if="autoResult.invigilatorGaps && autoResult.invigilatorGaps.length"
              type="warning"
              :description="'监考缺口 ' + autoResult.invigilatorGaps.length + ' 处：' + autoResult.invigilatorGaps.map(g => `${g.courseName} 考场${g.roomSeq}（需 ${g.needed} 实配 ${g.assigned}）`).join('；') + '，请在考场编排中手工补指'"
            />
            <AppInlineAlert
              v-if="autoArrangeComplete"
              type="success"
              :description="'自动排考完成：自动定时 ' + (autoResult.timePlan ? autoResult.timePlan.assigned : 0) + ' 门，编排 ' + autoResult.arrangedCourses + ' 门，无漏排、无监考缺口'"
            />
            <AppInlineAlert v-else type="warning" :description="readinessError || !readiness ? '本次编排已返回，完整就绪结果尚未确认，请重新读取。' : `完整批次仍有待处理项：漏排 ${readiness.missedCourseCount ?? '待确认'} 门、监考缺口 ${readiness.invigilatorGapCount ?? '待确认'} 处、教室不足 ${readiness.roomShortageCount ?? '待确认'} 处。`" />
          </template>

          <div class="aaexam-section-title">考试课程</div>
          <EmptyState v-if="!courses.length" title="未圈定课程" description="从已终审教学任务批量圈定应考课程" />
          <DataTable v-else :columns="courseColumns" :rows="courses" row-key="examCourseId" :pagination="coursePagination" @page-change="onCoursePageChange">
            <template #cell-course="{ row }">
              <div class="mp-cell-main">{{ row.courseName }}</div>
              <div class="mp-cell-sub">{{ row.className }} · {{ row.teacherName || '未派课' }}</div>
            </template>
            <template #cell-schedule="{ row }">{{ row.examDate || '—' }} {{ row.startTime || '' }}</template>
            <template #cell-status="{ row }">
              <StatusTag :type="row.status === 'CONFIRMED' ? 'success' : 'primary'"
                         :label="row.status === 'CONFIRMED' ? '已确认' : '待确认'" dot />
            </template>
            <template #cell-ops="{ row }">
              <button v-if="row.status === 'PENDING_CONFIRM'" class="mp-link" @click="confirm(row, 'CONFIRM')">确认</button>
              <button class="mp-link" @click="openSchedule(row)">设时间</button>
              <button class="mp-link" @click="openArrange(row)">考场</button>
            </template>
          </DataTable>

          <AaExamIncidentWorkbench :batch="current" />
        </template>
      </div>
    </div>

    <section v-else-if="viewMode === 'defer'" class="aaexam-mode-grid">
      <div class="aaexam-mode-main">
        <div class="aaexam-panel-head">
          <div>
            <h2>当前责任队列</h2>
            <p>只有命中真实班级、授课或学院关系的申请才会进入列表；教务处按全校范围查看。</p>
          </div>
          <span>共 {{ modePagination.total }} 条</span>
        </div>
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!deferRows.length" title="当前没有缓考申请" description="新的申请会从辅导员节点开始进入四级审核链" />
        <DataTable
          v-else
          :columns="deferColumns"
          :rows="deferRows"
          row-key="deferId"
          :pagination="modePagination"
          @page-change="onModePageChange"
        >
          <template #cell-student="{ row }">
            <div class="mp-cell-main">{{ row.studentName || '—' }}</div>
            <div class="mp-cell-sub">学生对象 {{ row.studentId || '—' }}</div>
          </template>
          <template #cell-course="{ row }">
            <div class="mp-cell-main">{{ row.courseName || '—' }}</div>
            <div class="mp-cell-sub">考试课程 {{ row.examCourseId || '—' }}</div>
          </template>
          <template #cell-reason="{ row }">
            <div>{{ row.reason || '未填写说明' }}</div>
            <div class="mp-cell-sub">{{ row.reasonType || '未标原因类型' }}</div>
          </template>
          <template #cell-status="{ row }"><StatusTag :type="deferStatusType(row.status)" :label="deferStatusLabel(row.status)" dot /></template>
          <template #cell-actions="{ row }">
            <button class="mp-link" @click="selectDefer(row)">查看证据</button>
            <template v-if="canReviewDefer(row)">
              <button class="mp-link" @click="openDeferDecision(row, 'APPROVE')">通过</button>
              <button class="mp-link" @click="openDeferDecision(row, 'RETURN')">退回</button>
              <button class="mp-link is-danger" @click="openDeferDecision(row, 'REJECT')">驳回</button>
            </template>
          </template>
        </DataTable>
      </div>
      <aside class="aaexam-mode-aside">
        <h2>审核证据与流转</h2>
        <EmptyState v-if="!selectedDefer" title="选择一条申请" description="查看申请原因、当前节点与下一责任岗位" />
        <template v-else>
          <dl class="aaexam-evidence">
            <div><dt>申请人</dt><dd>{{ selectedDefer.studentName || '—' }}</dd></div>
            <div><dt>考试课程</dt><dd>{{ selectedDefer.courseName || '—' }}</dd></div>
            <div><dt>提交时间</dt><dd>{{ formatTime(selectedDefer.applyAt) }}</dd></div>
            <div><dt>当前节点</dt><dd>{{ deferStatusLabel(selectedDefer.status) }}</dd></div>
            <div><dt>为什么轮到我</dt><dd>{{ deferWhyMine(selectedDefer) }}</dd></div>
            <div><dt>退回记录</dt><dd>{{ selectedDefer.returnReason || '无' }}</dd></div>
          </dl>
          <AppInlineAlert type="info" :description="'通过后流向：' + deferNextOwner(selectedDefer.status) + '。真实权限与数据范围由服务端再次校验。'" />
        </template>
      </aside>
    </section>

    <section v-else-if="viewMode === 'archive'" class="aaexam-mode-grid">
      <div class="aaexam-mode-main">
        <div class="aaexam-panel-head">
          <div>
            <h2>已封存考试批次</h2>
            <p>仅列出正式进入 ARCHIVED 状态的批次，课程与异常摘要来自归档事实。</p>
          </div>
          <span>共 {{ modePagination.total }} 个</span>
        </div>
        <AppInlineAlert type="info" description="归档页保持只读。课程确认数、缺考与违纪数用于核验封存完整性，不提供绕过状态机的补写入口。" />
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!archiveRows.length" title="暂无考务归档" description="考试结束并通过正式归档命令后显示在此" />
        <DataTable
          v-else
          :columns="archiveColumns"
          :rows="archiveRows"
          row-key="batchId"
          :pagination="modePagination"
          @page-change="onModePageChange"
        >
          <template #cell-batch="{ row }">
            <div class="mp-cell-main">{{ row.batchName || '未命名批次' }}</div>
            <div class="mp-cell-sub">批次 {{ row.batchId }} · 学期 {{ row.termId || '—' }}</div>
          </template>
          <template #cell-status><StatusTag type="default" label="已归档" dot /></template>
          <template #cell-completeness="{ row }">
            <div>课程 {{ row.completenessSummary?.courseCount ?? 0 }} · 已确认 {{ row.completenessSummary?.confirmedCount ?? 0 }}</div>
            <div class="mp-cell-sub">缺考 {{ row.completenessSummary?.absentCount ?? 0 }} · 违纪 {{ row.completenessSummary?.violationCount ?? 0 }}</div>
          </template>
          <template #cell-actions="{ row }"><button class="mp-link" @click="selectArchive(row)">查看封存证据</button></template>
        </DataTable>
      </div>
      <aside class="aaexam-mode-aside">
        <h2>封存证据</h2>
        <EmptyState v-if="!selectedArchive" title="选择一个批次" description="查看归档时间与完整性摘要" />
        <template v-else>
          <dl class="aaexam-evidence">
            <div><dt>考试批次</dt><dd>{{ selectedArchive.batchName || '—' }}</dd></div>
            <div><dt>正式状态</dt><dd>已归档（ARCHIVED）</dd></div>
            <div><dt>归档时间</dt><dd>{{ formatTime(selectedArchive.archivedAt) }}</dd></div>
            <div><dt>课程确认</dt><dd>{{ selectedArchive.completenessSummary?.confirmedCount ?? 0 }} / {{ selectedArchive.completenessSummary?.courseCount ?? 0 }}</dd></div>
            <div><dt>异常摘要</dt><dd>缺考 {{ selectedArchive.completenessSummary?.absentCount ?? 0 }}，违纪 {{ selectedArchive.completenessSummary?.violationCount ?? 0 }}</dd></div>
            <div><dt>返回位置</dt><dd>考务管理 / 考务归档</dd></div>
          </dl>
          <AppInlineAlert :type="archiveHasRisk(selectedArchive) ? 'warning' : 'success'" :description="archiveHasRisk(selectedArchive) ? '封存记录仍含异常计数，请按审计事实核查；本页不会改写归档数据。' : '封存摘要未发现异常计数，归档事实保持只读。'" />
        </template>
      </aside>
    </section>

    <AppDrawer :visible="createVisible" title="新建考试批次" mode="modal" size="small" @close="createVisible = false">
      <div class="aaexam-form">
        <AppFormItem label="学期" required><AppTermEntityPicker v-model="form.termId" placeholder="请选择正式学期" :disabled="saving" /></AppFormItem>
        <AppFormItem label="批次名称" required><AppTextInput v-model="form.batchName" placeholder="如 2024秋期末考试" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="createVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitCreate">创建</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="courseVisible" title="批量圈定应考课程" mode="modal" size="large" @close="closeCourseDrawer">
      <div class="aaexam-form">
        <div class="aaexam-candidate-toolbar">
          <AppTextInput v-model="candidateKeyword" placeholder="搜索课程、教学班或教师" :disabled="candidateLoading || saving" />
          <AppButton size="small" variant="ghost" :loading="candidateLoading" @click="loadCourseCandidates">搜索</AppButton>
        </div>
        <AppInlineAlert
          type="info"
          :description="'系统只列出当前考试批次同学期、已终审且尚未圈定的教学任务；单次最多 100 门。已选 ' + selectedTaskIds.length + ' 门。'"
        />
        <LoadingState v-if="candidateLoading" />
        <EmptyState v-else-if="!courseCandidates.length" title="暂无可圈定课程" description="当前批次没有尚未圈定的已终审教学任务" />
        <div v-else class="aaexam-candidate-list">
          <AppCheckboxGroup v-model="selectedTaskIds" :options="candidateOptions" :max="100" block :disabled="saving" />
        </div>
        <div v-if="coursePreview" class="aaexam-preview">
          <div class="aaexam-preview__summary">
            <strong>预览结果：可圈 {{ coursePreview.ready }} 门</strong>
            <span v-if="coursePreview.blocked">· 阻断 {{ coursePreview.blocked }} 门</span>
          </div>
          <ul v-if="previewBlockedItems.length" class="aaexam-preview__blocked">
            <li v-for="item in previewBlockedItems" :key="item.teachingTaskId">
              {{ item.courseName || ('教学任务 ' + item.teachingTaskId) }}：{{ item.message }}
            </li>
          </ul>
          <AppInlineAlert
            v-if="coursePreview.previewToken"
            type="success"
            description="预览为零写入；确认时系统会重新校验名单与任务状态，再逐门进入正式圈课写链。"
          />
        </div>
        <AppInlineAlert v-if="courseError" type="danger" :description="courseError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="closeCourseDrawer">取消</AppButton>
        <AppButton variant="ghost" :loading="saving" :disabled="!selectedTaskIds.length" @click="previewCourses">预览圈课</AppButton>
        <AppButton
          variant="primary"
          :loading="saving"
          :disabled="!coursePreview || !coursePreview.previewToken || !coursePreview.ready"
          @click="confirmCourses"
        >确认圈定 {{ coursePreview ? coursePreview.ready : 0 }} 门</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="autoPlanVisible" title="自动排考 · 日期与场次" mode="modal" size="large" @close="closeAutoPlan">
      <div class="aaexam-form">
        <AppInlineAlert type="info" description="系统先用所选日期×场次自动安排考试时间，再增量切考场、铺座位、配监考；已定时间和已有考场不会被覆盖。" />

        <div class="aaexam-auto-block">
          <div class="aaexam-auto-head">
            <strong>考试日期</strong>
            <AppButton size="small" variant="ghost" :disabled="autoArranging" @click="addAutoDate">+ 添加日期</AppButton>
          </div>
          <div v-for="(date, index) in autoPlan.dates" :key="'date-' + index" class="aaexam-auto-row">
            <AppDatePicker v-model="autoPlan.dates[index]" :disabled="autoArranging" />
            <AppButton v-if="autoPlan.dates.length > 1" size="small" variant="ghost" :disabled="autoArranging" @click="removeAutoDate(index)">移除</AppButton>
          </div>
        </div>

        <div class="aaexam-auto-block">
          <div class="aaexam-auto-head">
            <strong>每日场次</strong>
            <AppButton size="small" variant="ghost" :disabled="autoArranging" @click="addAutoSession">+ 添加场次</AppButton>
          </div>
          <div v-for="(session, index) in autoPlan.sessions" :key="'session-' + index" class="aaexam-auto-row is-session">
            <AppTimePicker v-model="session.start" :disabled="autoArranging" />
            <span class="aaexam-auto-sep">至</span>
            <AppTimePicker v-model="session.end" :disabled="autoArranging" />
            <AppButton v-if="autoPlan.sessions.length > 1" size="small" variant="ghost" :disabled="autoArranging" @click="removeAutoSession(index)">移除</AppButton>
          </div>
        </div>

        <AppFormItem label="同班每日最多考试场次">
          <AppNumberInput v-model="autoPlan.maxPerDayPerClass" :min="1" :max="4" :disabled="autoArranging" />
        </AppFormItem>
        <AppInlineAlert v-if="autoPlanError" type="danger" :description="autoPlanError" />
        <AppInlineAlert v-if="autoTimeReceipt && autoTimeReceipt.batchId === current?.batchId" type="info" :description="`考试批次 ${autoTimeReceipt.batchId} 的时间安排已保存；相同方案再次办理将继续考场编排。`" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="autoArranging" @click="closeAutoPlan">取消</AppButton>
        <AppButton variant="primary" :loading="autoArranging" @click="runAutoArrange">开始自动排考</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="schedVisible" title="设置考试时间" mode="modal" size="medium" @close="schedVisible = false">
      <div class="aaexam-form">
        <AppFormItem label="考试日期"><AppDatePicker v-model="sched.examDate" :disabled="saving" /></AppFormItem>
        <AppFormItem label="开始时间"><AppTimePicker v-model="sched.startTime" :disabled="saving" /></AppFormItem>
        <AppFormItem label="结束时间"><AppTimePicker v-model="sched.endTime" :disabled="saving" /></AppFormItem>
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="schedVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitSchedule">保存</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="arrangeVisible" :title="'考场编排 · ' + (arrangeCourse ? arrangeCourse.courseName : '')" mode="modal" size="large" @close="arrangeVisible = false">
      <div class="aaexam-form">
        <div class="aaexam-section-title">已有考场</div>
        <AppInlineAlert v-if="!canArrangeRooms" type="info" description="请等待教务处推进至课程确认完成后，再编排考场和监考。发布后本页仅供查阅。" />
        <AppInlineAlert v-if="arrangeError" type="danger" :description="arrangeError" />
        <EmptyState v-if="!arrangeRooms.length" title="暂无考场" description="添加考场后可指定监考" />
        <ul v-else class="aaexam-rooms">
          <li v-for="r in arrangeRooms" :key="r.examRoomId">
            <span>考场{{ r.roomSeq }} · {{ r.classroomText }}（{{ r.plannedCount }}/{{ r.capacity }}）</span>
            <button class="mp-link" @click="printSeating(r.examRoomId)">座位表/准考证/门贴</button>
            <div v-if="canArrangeRooms" class="aaexam-room-actions">
              <AppButton v-if="arrangeRooms.length === 1 && !r.plannedCount" size="small" :disabled="!arrangeCourse?.rosterIdentity?.studentIds?.length || saving" @click="assignFrozenSeats(r)">按冻结名单铺位</AppButton>
              <p>监考：{{ (r.invigilators || []).map(item => item.teacherName || '教师姓名待核对').join('、') || '尚未指定' }}</p>
              <AppTeacherPicker v-model="invigilatorForm.teacherKey" :query="teacherKeyQuery" :disabled="saving" placeholder="选择监考教师" @change="onInvigilatorPicked" />
              <AppButton size="small" :disabled="!invigilatorForm.teacherKey || saving" @click="assignRoomInvigilator(r)">指定监考</AppButton>
            </div>
          </li>
        </ul>
        <AppFormItem label="新增考场"><AppClassroomPicker v-model="roomForm.classroomId" :query="{ purpose: 'EXAM' }" :disabled="saving || !canArrangeRooms" @change="onExamRoomPicked" /></AppFormItem>
        <AppFormItem label="容量"><AppNumberInput v-model="roomForm.capacity" :min="1" :max="500" :disabled="saving || !canArrangeRooms" /></AppFormItem>
        <AppButton size="small" variant="ghost" :loading="saving" :disabled="!canArrangeRooms" @click="submitRoom">添加考场</AppButton>
      </div>
    </AppDrawer>

    <AppDrawer :visible="patrolVisible" title="巡考安排" mode="modal" size="large" @close="patrolVisible = false">
      <div class="aaexam-form">
        <div class="aaexam-section-title">已排巡考</div>
        <EmptyState v-if="!patrols.length" title="暂无巡考" description="填写下方表单排巡考（同一人同时段/与监考冲突会拦截）" />
        <ul v-else class="aaexam-rooms">
          <li v-for="p in patrols" :key="p.patrolId">
            <span>{{ p.teacherName || p.teacherKey }} · {{ p.patrolDate || '—' }} {{ p.startTime || '' }}-{{ p.endTime || '' }} · {{ p.areaScope || '全场' }}</span>
          </li>
        </ul>
        <AppFormItem label="巡考教师" required><AppTeacherPicker v-model="patrolForm.teacherKey" :query="teacherKeyQuery" :disabled="saving" @change="onPatrolTeacherPicked" /></AppFormItem>
        <AppFormItem label="巡考日期"><AppDatePicker v-model="patrolForm.patrolDate" :disabled="saving" /></AppFormItem>
        <AppFormItem label="开始时间"><AppTimePicker v-model="patrolForm.startTime" :disabled="saving" /></AppFormItem>
        <AppFormItem label="结束时间"><AppTimePicker v-model="patrolForm.endTime" :disabled="saving" /></AppFormItem>
        <AppFormItem label="巡考区域"><AppTextInput v-model="patrolForm.areaScope" placeholder="如 教学楼A/全场" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="patrolError" type="danger" :description="patrolError" />
        <AppButton size="small" variant="primary" :loading="saving" @click="submitPatrol">排巡考</AppButton>
      </div>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="confirmVisible" :title="confirmTitle" :message="confirmMessage" @confirm="onConfirm" />
    <AppConfirmDialog
      v-model:visible="deferConfirmVisible"
      :title="deferDecisionTitle"
      :message="deferDecisionMessage"
      :type="deferDecisionAction === 'REJECT' ? 'danger' : deferDecisionAction === 'RETURN' ? 'warning' : 'primary'"
      :confirm-text="deferDecisionAction === 'APPROVE' ? '确认通过' : deferDecisionAction === 'RETURN' ? '确认退回' : '确认驳回'"
      :require-reason="deferDecisionAction !== 'APPROVE'"
      reason-label="审核意见"
      reason-placeholder="退回或驳回请填写至少 5 个字的依据"
      :reason-min-length="5"
      :submitting="saving"
      @confirm="submitDeferDecision"
    />
  </ModulePageShell>
</template>

<script>
/** 考务管理 · 教务处控制台：批次生命周期 + 批量圈课 + 两段式自动排考 + 发布就绪。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppNumberInput, AppFormItem, AppConfirmDialog, AppInlineAlert, AppCheckboxGroup, AppTermEntityPicker, AppClassroomPicker, AppTeacherPicker, AppDatePicker, AppTimePicker } from '@/components/common'
import { academicAffairsApi, academicAffairsExamApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { academicAffairsExamConvenienceApi as convenienceApi } from '@/modules/academicAffairs/api/exam-convenience.api'
import AaExamIncidentWorkbench from '@/modules/academicAffairs/components/AaExamIncidentWorkbench.vue'
import AaExamObjectBar from '@/modules/academicAffairs/components/exam/AaExamObjectBar.vue'
import AaExamStageRail from '@/modules/academicAffairs/components/exam/AaExamStageRail.vue'
import { toast } from '@/utils/toast'
import { currentUserFromToken } from '@/services/http/client'

const _L = { DRAFT: '草稿', COURSE_CONFIRMED: '课程已确认', ARRANGED: '已编排', PUBLISHED: '已发布', FINISHED: '已结束', ARCHIVED: '已归档' }
const EXAM_STEPS = ['创建批次', '圈课冻结', '编排预检', '考试发布', '异常收口']
const DEFER_STEPS = ['学生发起缓考', '当前节点审核', '后续节点审核', '缓考安排', '结果归档']
const DEFER_LABEL = {
  COUNSELOR_REVIEW: '辅导员审核', TEACHER_CONFIRM: '任课教师确认', COLLEGE_REVIEW: '学院审核',
  ACADEMIC_FINAL: '教务处终审', APPROVED: '已通过', RETURNED: '已退回补材料', REJECTED: '已驳回'
}
const DEFER_ACTIVE = new Set(['COUNSELOR_REVIEW', 'TEACHER_CONFIRM', 'COLLEGE_REVIEW', 'ACADEMIC_FINAL'])

export default {
  name: 'AaExamConsoleView',
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AaExamIncidentWorkbench, AaExamObjectBar, AaExamStageRail,
    AppButton, AppDrawer, AppTextInput, AppNumberInput, AppFormItem, AppConfirmDialog, AppInlineAlert,
    AppCheckboxGroup, AppTermEntityPicker, AppClassroomPicker, AppTeacherPicker, AppDatePicker, AppTimePicker
  },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      loading: true, error: '', rows: [], pagination: { page: 1, pageSize: 50, total: 0 },
      myInvigilations: [], myExamBatch: null,
      invigilationColumns: [{ key: 'course', title: '课程与批次' }, { key: 'when', title: '考试时间' }, { key: 'classroom', title: '考场' }, { key: 'duty', title: '本人职责' }, { key: 'state', title: '当前状态' }, { key: 'actions', title: '办理' }],
      modePagination: { page: 1, pageSize: 20, total: 0 },
      deferRows: [], archiveRows: [], selectedDefer: null, selectedArchive: null,
      current: null, courses: [], coursePagination: { page: 1, pageSize: 20, total: 0 }, stats: null, readiness: null, readinessError: '',
      createVisible: false, form: { batchName: '', termId: '' }, formError: '',
      courseVisible: false, candidateLoading: false, candidateKeyword: '', courseCandidates: [], selectedTaskIds: [], coursePreview: null, courseError: '',
      autoPlanVisible: false, autoPlanError: '', autoPlan: { dates: [''], sessions: [{ start: '', end: '' }], maxPerDayPerClass: 1 },
      schedVisible: false, schedCourse: null, sched: { examDate: '', startTime: '', endTime: '' },
      arrangeVisible: false, arrangeCourse: null, arrangeRooms: [], arrangeError: '', invigilatorForm: { teacherKey: '', teacherName: '' }, roomForm: { classroomId: '', classroomText: '', capacity: 50 },
      patrolVisible: false, patrols: [], patrolForm: { teacherKey: '', teacherName: '', patrolDate: '', startTime: '', endTime: '', areaScope: '' }, patrolError: '', teacherKeyQuery: { valueField: 'loginName' },
      saving: false, confirmVisible: false, confirmTitle: '', confirmMessage: '', pendingAction: null,
      deferConfirmVisible: false, deferDecisionAction: '', deferDecisionRow: null,
      autoArranging: false, autoResult: null, autoTimeReceipt: null, autoSeq: 0, loadSeq: 0, detailSeq: 0, initialized: false,
      courseColumns: [
        { key: 'course', title: '课程/班级' }, { key: 'schedule', title: '考试时间' },
        { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }
      ],
      deferColumns: [
        { key: 'student', title: '申请学生' }, { key: 'course', title: '考试课程' },
        { key: 'reason', title: '申请依据' }, { key: 'status', title: '当前责任节点' }, { key: 'actions', title: '办理' }
      ],
      archiveColumns: [
        { key: 'batch', title: '考试批次' }, { key: 'status', title: '封存状态' },
        { key: 'completeness', title: '完整性摘要' }, { key: 'archivedAt', title: '归档时间' }, { key: 'actions', title: '操作' }
      ]
    }
  },
  computed: {
    viewMode() {
      const tab = String(this.$route.query.tab || '').toLowerCase()
      return tab === 'defer' ? 'defer' : tab === 'archive' ? 'archive' : 'exam'
    },
    pageMeta() {
      if (this.teacherExamView) return { title: '我的监考安排', subtitle: '本人正式指派 → 核对时间与教室 → 监考及异常处置' }
      if (this.viewMode === 'defer') return { title: '缓考审批', subtitle: `学生申请 → 四级审核 → 缓考安排 → 结果归档 · 共 ${this.modePagination.total} 条申请` }
      if (this.viewMode === 'archive') return { title: '考务归档', subtitle: `只读核验已封存考试批次与异常摘要 · 共 ${this.modePagination.total} 个批次` }
      return { title: '考务安排', subtitle: `批次 → 圈课冻结 → 编排预检 → 发布 → 异常收口 · 共 ${this.pagination.total} 个批次` }
    },
    stageSteps() { return this.viewMode === 'defer' ? DEFER_STEPS : EXAM_STEPS },
    stageIndex() {
      if (this.viewMode === 'archive') return 4
      if (this.viewMode === 'defer') {
        const status = this.selectedDefer?.status
        if (status === 'COUNSELOR_REVIEW') return 1
        if (['TEACHER_CONFIRM', 'COLLEGE_REVIEW', 'ACADEMIC_FINAL'].includes(status)) return 2
        if (status === 'APPROVED') return 3
        if (['RETURNED', 'REJECTED'].includes(status)) return 4
        return 1
      }
      const status = this.current?.status
      return ({ DRAFT: 0, COURSE_CONFIRMED: 1, ARRANGED: 2, PUBLISHED: 3, FINISHED: 4, ARCHIVED: 4 })[status] ?? 0
    },
    objectBar() {
      if (this.viewMode === 'defer') {
        const row = this.selectedDefer
        return {
          title: row ? `${row.studentName || '学生'} · ${row.courseName || '考试课程'}` : '缓考审核责任队列',
          objectId: row ? `DEFER-${row.deferId}` : `${this.modePagination.total} 条正式申请`,
          source: '考务管理 / 缓考审批', status: row ? this.deferStatusLabel(row.status) : '等待选择申请',
          owner: row ? this.deferOwner(row.status) : (this.ctx.currentRole.roleName || '当前受理岗位'),
          blocker: row?.returnReason || (row?.status === 'APPROVED' ? '审核链已完成' : '无已知阻断'),
          blocked: !!row?.returnReason || row?.status === 'REJECTED', nextOwner: row ? this.deferNextOwner(row.status) : '按当前审核节点流转'
        }
      }
      if (this.viewMode === 'archive') {
        const row = this.selectedArchive
        return {
          title: row?.batchName || '考务归档清单', objectId: row ? `EXAM-BATCH-${row.batchId}` : `${this.modePagination.total} 个封存批次`,
          source: '考务管理 / 考务归档', status: row ? '已归档' : '只读核验', owner: '考务档案管理岗',
          blocker: row && this.archiveHasRisk(row) ? '封存摘要含异常计数' : '无已知阻断', blocked: !!(row && this.archiveHasRisk(row)), nextOwner: '档案查阅与受控审计'
        }
      }
      const status = this.current?.status
      const publishStage = status === 'COURSE_CONFIRMED'
      const blocker = publishStage ? (this.readinessError || (this.readiness && !this.readiness.canPublish ? (this.readiness.blockingReasons || []).join('；') : '')) : ''
      return {
        title: this.current?.batchName || '考试批次责任队列', objectId: this.current ? `EXAM-BATCH-${this.current.batchId}` : `${this.pagination.total} 个批次`,
        source: '考务管理 / 考务安排', status: this.current ? this.statusLabel(status) : '等待选择批次',
        owner: this.examOwner(status), blocker: blocker || (publishStage && this.readiness?.canPublish ? '本次就绪检查通过，发布时再次校验' : (this.current ? '按当前阶段核验，尚无本次就绪结论' : '选择批次后核验')), blocked: !!blocker, nextOwner: this.examNextOwner(status)
      }
    },
    deferDecisionTitle() {
      if (this.deferDecisionAction === 'APPROVE') return '确认通过当前缓考节点'
      if (this.deferDecisionAction === 'RETURN') return '退回学生补充材料'
      return '驳回缓考申请'
    },
    deferDecisionMessage() {
      const row = this.deferDecisionRow
      const name = row ? `${row.studentName || '学生'} · ${row.courseName || '考试课程'}` : '当前申请'
      if (this.deferDecisionAction === 'APPROVE') return `${name} 将按正式状态机流向 ${row ? this.deferNextOwner(row.status) : '下一责任岗位'}。`
      if (this.deferDecisionAction === 'RETURN') return `${name} 将退回学生补充材料，审核意见会写入正式记录。`
      return `${name} 将进入驳回终态，审核意见会写入正式记录。`
    },
    autoArrangeComplete() {
      return !!this.autoResult && String(this.autoResult.batchId) === String(this.current?.batchId) && !this.readinessError &&
        this.readiness?.canPublish === true && ['missedCourseCount', 'invigilatorGapCount', 'roomShortageCount'].every(key => this.readiness[key] === 0)
    },
    canArrangeRooms() { return ['COURSE_CONFIRMED', 'ARRANGED'].includes(this.current?.status) },
    schoolExamScope() { return ['SCHOOL', 'TENANT_ALL'].includes(this.ctx.dataScope?.scope) },
    teacherExamView() { return this.viewMode === 'exam' && (this.ctx.currentRole?.roleCode || currentUserFromToken()?.currentRoleCode) === 'ACADEMIC_TEACHER' },
    identityKey() { return JSON.stringify([currentUserFromToken(), this.ctx]) },
    candidateOptions() {
      return this.courseCandidates.map((row) => ({
        value: String(row.teachingTaskId),
        label: `${row.courseName || '未命名课程'} · ${row.teachingClassName || '未分教学班'} · ${row.teacherName || '未派课'}`
      }))
    },
    previewBlockedItems() {
      return (this.coursePreview?.items || []).filter((item) => item.status !== 'READY')
    }
  },
  watch: {
    'current.batchId'() { this.autoSeq++; this.autoArranging = false; this.coursePreview = null; this.autoTimeReceipt = null; this.confirmVisible = false; this.pendingAction = null; this.coursePagination.page = 1 },
    '$route.fullPath'() { if (this.initialized) this.resetModeAndLoad() },
    identityKey() { if (!this.initialized) return; this.resetModeAndLoad() }
  },
  beforeUnmount() { this.autoSeq++; this.detailSeq++; this.loadSeq++ },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    await this.$nextTick()
    this.initialized = true
    this.load()
  },
  methods: {
    onExamRoomPicked(value, items) {
      this.roomForm.classroomId = value || ''
      this.roomForm.classroomText = items?.[0]?.label || ''
      const room = items?.[0]?.raw
      this.roomForm.capacity = room?.examSeats ?? room?.capacity ?? 0
    },
    onPatrolTeacherPicked(value, items) {
      this.patrolForm.teacherKey = value || ''
      this.patrolForm.teacherName = items?.[0]?.raw?.teacherName || items?.[0]?.label || ''
    },
    statusLabel(s) { return _L[s] || '状态待确认' },
    statusType(s) {
      if (s === 'PUBLISHED') return 'success'
      if (s === 'FINISHED') return 'warning'
      if (s === 'ARCHIVED') return 'default'
      return 'primary'
    },
    examOwner(status) {
      if (status === 'DRAFT') return '考务批次管理岗'
      if (['COURSE_CONFIRMED', 'ARRANGED'].includes(status)) return '考务编排岗'
      if (status === 'PUBLISHED') return '考务运行岗'
      if (status === 'FINISHED') return '考务归档岗'
      if (status === 'ARCHIVED') return '考务档案管理岗'
      return this.ctx.currentRole.roleName || '考务批次管理岗'
    },
    examNextOwner(status) {
      if (status === 'DRAFT') return '学院课程确认岗 → 考务编排岗'
      if (['COURSE_CONFIRMED', 'ARRANGED'].includes(status)) return '考务发布岗'
      if (status === 'PUBLISHED') return '监考与异常处置岗'
      if (status === 'FINISHED') return '考务归档岗'
      if (status === 'ARCHIVED') return '档案查阅岗'
      return '学院课程确认岗 → 考务编排岗'
    },
    deferStatusLabel(status) { return DEFER_LABEL[status] || '状态待确认' },
    deferStatusType(status) {
      if (status === 'APPROVED') return 'success'
      if (status === 'REJECTED') return 'danger'
      if (status === 'RETURNED') return 'warning'
      return 'primary'
    },
    deferOwner(status) {
      return ({ COUNSELOR_REVIEW: '辅导员', TEACHER_CONFIRM: '任课教师', COLLEGE_REVIEW: '学院教务', ACADEMIC_FINAL: '教务处终审岗' })[status] || '流程已结束'
    },
    deferNextOwner(status) {
      return ({ COUNSELOR_REVIEW: '任课教师', TEACHER_CONFIRM: '学院教务', COLLEGE_REVIEW: '教务处终审岗', ACADEMIC_FINAL: '缓考安排岗', APPROVED: '缓考安排岗', RETURNED: '申请学生', REJECTED: '流程结束' })[status] || '按正式状态机判定'
    },
    deferWhyMine(row) {
      const role = this.ctx.currentRole.roleName || '当前身份'
      return `${role}在当前数据范围内可查看该申请；能否办理仍由服务端按 ${this.deferOwner(row.status)} 节点校验。`
    },
    canReviewDefer(row) { return DEFER_ACTIVE.has(String(row?.status || '')) },
    archiveHasRisk(row) {
      const summary = row?.completenessSummary || {}
      return Number(summary.absentCount || 0) + Number(summary.violationCount || 0) > 0
    },
    formatTime(value) {
      if (!value) return '—'
      const date = new Date(value)
      return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('zh-CN', { hour12: false })
    },
    resetModeAndLoad() {
      this.autoSeq++; this.detailSeq++; this.loadSeq++
      this.current = null; this.courses = []; this.coursePagination.page = 1; this.coursePagination.total = 0; this.stats = null; this.readiness = null; this.readinessError = ''
      this.autoTimeReceipt = null; this.autoArranging = false; this.rows = []; this.deferRows = []; this.archiveRows = []
      this.selectedDefer = null; this.selectedArchive = null; this.modePagination.page = 1
      this.deferConfirmVisible = false; this.deferDecisionAction = ''; this.deferDecisionRow = null
      this.load()
    },
    async load() {
      const seq = ++this.loadSeq, identity = this.identityKey
      const current = () => seq === this.loadSeq && identity === this.identityKey
      this.loading = true; this.error = ''
      this.myInvigilations = []; this.myExamBatch = null
      try {
      if (this.teacherExamView) {
        const res = await api.getMyInvigilation()
        if (!current()) return
        if (res.code !== 0) this.error = res.message || '本人监考安排读取失败'
        else this.myInvigilations = Array.isArray(res.data?.items) ? res.data.items : []
        return
      }
      const res = this.viewMode === 'defer'
        ? await api.deferList({ page: this.modePagination.page, pageSize: this.modePagination.pageSize })
        : this.viewMode === 'archive'
          ? await api.listArchived({ page: this.modePagination.page, pageSize: this.modePagination.pageSize })
          : await api.listBatches({ page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (!current()) return
      if (res.code === 0) {
        const list = Array.isArray(res.data?.list) ? res.data.list : []
        if (this.viewMode === 'defer') {
          this.deferRows = list; this.modePagination.total = Number(res.data?.total || 0)
          this.selectedDefer = list.find(row => row.deferId === this.selectedDefer?.deferId) || list[0] || null
        } else if (this.viewMode === 'archive') {
          this.archiveRows = list; this.modePagination.total = Number(res.data?.total || 0)
          this.selectedArchive = list.find(row => row.batchId === this.selectedArchive?.batchId) || list[0] || null
        } else { this.rows = list; this.pagination.total = Number(res.data?.total || 0) }
      } else this.error = res.message
      } catch (error) { if (current()) this.error = error?.message || '考试批次加载失败' }
      finally { if (current()) this.loading = false }
    },
    onModePageChange(page) { this.modePagination.page = Number(page || 1); this.load() },
    selectDefer(row) { this.selectedDefer = row },
    selectArchive(row) { this.selectedArchive = row },
    openDeferDecision(row, action) {
      if (!this.canReviewDefer(row) || this.saving) return
      this.selectedDefer = row
      this.deferDecisionRow = { ...row }
      this.deferDecisionAction = action
      this.deferConfirmVisible = true
    },
    async submitDeferDecision({ reason = '' } = {}) {
      const row = this.deferDecisionRow, action = this.deferDecisionAction, identity = this.identityKey
      if (!row || !action || this.saving) return
      this.saving = true
      try {
        const res = await api.deferReview(row.deferId, action, String(reason || '').trim())
        if (identity !== this.identityKey || this.viewMode !== 'defer') return
        if (res.code !== 0) { toast.error(res.message || '缓考审核失败'); return }
        toast.success(action === 'APPROVE' ? `已通过，下一岗位：${this.deferNextOwner(row.status)}` : action === 'RETURN' ? '已退回学生补充材料' : '已驳回缓考申请')
        this.deferConfirmVisible = false; this.deferDecisionRow = null; this.deferDecisionAction = ''
        await this.load()
      } catch (error) { if (identity === this.identityKey) toast.error(error?.message || '办理结果未确认，请刷新正式记录') }
      finally { if (identity === this.identityKey) this.saving = false }
    },
    async select(b) { this.coursePagination.page = 1; this.current = b; this.autoResult = null; await this.refresh() },
    async refresh() {
      if (!this.current) return
      const seq = ++this.detailSeq, id = this.current.batchId, identity = this.identityKey
      const current = () => seq === this.detailSeq && id === this.current?.batchId && identity === this.identityKey
      this.courses = []; this.stats = null; this.readiness = null; this.readinessError = ''
      try {
      const [cs, st, ready] = await Promise.all([
        api.listCourses(id, { page: this.coursePagination.page, pageSize: this.coursePagination.pageSize }),
        api.batchStats(id),
        this.schoolExamScope ? convenienceApi.getReadiness(id) : Promise.resolve({ code: 0, data: null })
      ])
      if (!current()) return
      this.courses = cs.code === 0 ? cs.data.list : []
      this.coursePagination.total = cs.code === 0 ? Number(cs.data?.total || 0) : 0
      this.stats = st.code === 0 ? st.data : null
      this.readiness = ready.code === 0 ? ready.data : null
      this.readinessError = cs.code !== 0 ? cs.message : st.code !== 0 ? st.message : ready.code !== 0 ? ready.message : ''
      } catch (error) { if (current()) this.readinessError = error?.message || '考试详情加载失败' }
    },
    onCoursePageChange(page) { this.coursePagination.page = Number(page || 1); this.refresh() },
    openCreate() { this.form = { batchName: '', termId: '' }; this.formError = ''; this.createVisible = true },
    async submitCreate() {
      if (this.saving) return
      const identity = this.identityKey
      if (!this.form.termId) { this.formError = '请选择正式学期'; return }
      if (!this.form.batchName) { this.formError = '批次名称必填'; return }
      this.saving = true
      try {
        const res = await api.createBatch({ batchName: this.form.batchName, termId: this.form.termId })
        if (identity !== this.identityKey) return
        if (res.code === 0) { toast.success('已创建'); this.createVisible = false; await this.select(res.data); await this.load() }
        else this.formError = res.message
      } catch (error) {
        if (identity === this.identityKey) this.formError = error?.message || '创建结果待核对，请先刷新批次列表'
      } finally { if (identity === this.identityKey) this.saving = false }
    },
    lc(fn, label) {
      if (!this.current || this.saving) return
      const batch = { ...this.current }, identity = this.identityKey
      this.confirmTitle = label
      this.confirmMessage = `确认对批次「${this.current.batchName}」执行「${label}」？`
      this.pendingAction = async () => {
        const current = () => batch.batchId === this.current?.batchId && identity === this.identityKey
        if (!current() || this.saving) return
        this.saving = true
        try {
          const res = await api[fn](batch.batchId)
          if (!current()) return
          if (res.code === 0) { toast.success(label + '成功'); this.current = res.data; await this.load(); await this.refresh() }
          else toast.error(res.message)
        } catch (error) { if (current()) toast.error(error?.message || '办理结果未确认，请核对批次') }
        finally { if (current()) this.saving = false }
      }
      this.confirmVisible = true
    },
    async openAddCourse() {
      this.courseVisible = true
      this.candidateKeyword = ''
      this.courseCandidates = []
      this.selectedTaskIds = []
      this.coursePreview = null
      this.courseError = ''
      await this.loadCourseCandidates()
    },
    closeCourseDrawer() {
      if (this.saving) return
      this.courseVisible = false
      this.coursePreview = null
      this.courseError = ''
    },
    async loadCourseCandidates() {
      if (!this.current) return
      this.candidateLoading = true
      this.courseError = ''
      const res = await convenienceApi.listCourseCandidates(this.current.batchId, {
        keyword: this.candidateKeyword || undefined,
        page: 1,
        pageSize: 100
      })
      this.candidateLoading = false
      if (res.code === 0) {
        this.courseCandidates = res.data.list || []
        this.selectedTaskIds = []
        this.coursePreview = null
      } else {
        this.courseCandidates = []
        this.courseError = res.message
      }
    },
    async previewCourses() {
      if (!this.selectedTaskIds.length) { this.courseError = '请至少选择 1 门应考课程'; return }
      this.saving = true; this.courseError = ''
      const res = await convenienceApi.previewCourses(this.current.batchId, this.selectedTaskIds)
      this.saving = false
      if (res.code === 0) this.coursePreview = res.data
      else { this.coursePreview = null; this.courseError = res.message }
    },
    async confirmCourses() {
      const previewToken = this.coursePreview?.previewToken
      if (!previewToken) { this.courseError = '预览已失效，请重新预览'; return }
      this.saving = true; this.courseError = ''
      const res = await convenienceApi.confirmCourses(this.current.batchId, previewToken)
      this.saving = false
      if (res.code !== 0) { this.courseError = res.message; return }
      const { succeeded = 0, failed = 0, items = [] } = res.data || {}
      await this.refresh()
      if (failed) {
        const message = `已圈定 ${succeeded} 门，另有 ${failed} 门状态已变化：${items.filter(item => !item.ok).map(item => item.message).join('；')}`
        await this.loadCourseCandidates()
        this.courseError = message
        return
      }
      toast.success(`已批量圈定 ${succeeded} 门课程`)
      this.courseVisible = false
      this.coursePreview = null
    },
    openAutoPlan() {
      this.autoPlan = { dates: [''], sessions: [{ start: '', end: '' }], maxPerDayPerClass: 1 }
      this.autoPlanError = ''
      this.autoPlanVisible = true
    },
    closeAutoPlan() {
      if (this.autoArranging) return
      this.autoPlanVisible = false
      this.autoPlanError = ''
    },
    addAutoDate() { this.autoPlan.dates.push('') },
    removeAutoDate(index) { if (this.autoPlan.dates.length > 1) this.autoPlan.dates.splice(index, 1) },
    addAutoSession() { this.autoPlan.sessions.push({ start: '', end: '' }) },
    removeAutoSession(index) { if (this.autoPlan.sessions.length > 1) this.autoPlan.sessions.splice(index, 1) },
    async runAutoArrange() {
      if (!this.current || this.autoArranging) return
      const batchId = this.current.batchId, identity = this.identityKey, seq = ++this.autoSeq
      const current = () => seq === this.autoSeq && batchId === this.current?.batchId && identity === this.identityKey
      const dates = [...new Set(this.autoPlan.dates.map((value) => String(value || '').trim()).filter(Boolean))]
      const sessions = []
      const seenSessions = new Set()
      for (const row of this.autoPlan.sessions) {
        const start = String(row.start || '').trim()
        const end = String(row.end || '').trim()
        if (!start && !end) continue
        if (!start || !end) { this.autoPlanError = '每个考试场次都必须同时填写开始与结束时间'; return }
        if (start >= end) { this.autoPlanError = `场次 ${start}-${end} 的结束时间必须晚于开始时间`; return }
        const key = `${start}-${end}`
        if (!seenSessions.has(key)) {
          seenSessions.add(key)
          sessions.push({ start, end })
        }
      }
      if (!dates.length) { this.autoPlanError = '请至少选择 1 个考试日期'; return }
      if (!sessions.length) { this.autoPlanError = '请至少配置 1 个每日考试场次'; return }

      this.autoPlanError = ''
      this.autoArranging = true
      const body = { dates, sessions, maxPerDayPerClass: Number(this.autoPlan.maxPerDayPerClass || 1) }
      const key = JSON.stringify([identity, batchId, body])
      try {
        let timePlan = this.autoTimeReceipt?.key === key ? this.autoTimeReceipt.data : null
        if (!timePlan) {
          const timeRes = await convenienceApi.autoTimes(batchId, body)
          if (!current()) return
          if (timeRes.code !== 0) { this.autoPlanError = timeRes.message || '时间安排结果未确认，请先核对正式考试时间'; return }
          timePlan = timeRes.data
          this.autoTimeReceipt = { key, batchId, data: timePlan }
        }
        if (!current()) return
        const arrangeRes = await api.autoArrange(batchId)
        if (!current()) return
        if (arrangeRes.code !== 0) {
          this.autoPlanError = `时间安排已保存；考场编排未完成：${arrangeRes.message || '请核对后继续编排'}`
          await this.refresh()
          return
        }
        this.autoResult = { ...arrangeRes.data, batchId: String(batchId), timePlan }
        this.autoPlanVisible = false
        await this.refresh()
        if (current() && this.autoArrangeComplete) toast.success('本批次完整就绪检查通过，仍以正式发布校验为准')
      } catch (error) { if (current()) this.autoPlanError = (this.autoTimeReceipt ? '时间安排已保存；' : '') + (error?.message || '办理结果未确认，请核对正式记录') }
      finally { if (current()) this.autoArranging = false }
    },
    async confirm(row, action) {
      const res = await api.confirmCourse(row.examCourseId, action)
      if (res.code === 0) { toast.success('已处理'); await this.refresh() } else toast.error(res.message)
    },
    openSchedule(row) { this.schedCourse = row; this.sched = { examDate: row.examDate || '', startTime: row.startTime || '', endTime: row.endTime || '' }; this.schedVisible = true },
    async submitSchedule() {
      this.saving = true
      const res = await api.setSchedule(this.schedCourse.examCourseId, this.sched)
      this.saving = false
      if (res.code === 0) { toast.success('已保存'); this.schedVisible = false; await this.refresh() } else toast.error(res.message)
    },
    async openArrange(row) {
      this.arrangeCourse = row; this.roomForm = { classroomId: '', classroomText: '', capacity: 50 }; this.arrangeVisible = true
      this.arrangeError = ''; this.invigilatorForm = { teacherKey: '', teacherName: '' }
      await this.readArrangeRooms()
    },
    async readArrangeRooms() {
      const id = this.arrangeCourse?.examCourseId, identity = this.identityKey
      const current = () => id === this.arrangeCourse?.examCourseId && identity === this.identityKey && this.arrangeVisible
      this.arrangeRooms = []
      try {
        const res = await api.listRooms(id)
        if (!current()) return
        if (res.code !== 0) { this.arrangeError = res.message; return }
        const rooms = await Promise.all((res.data.items || []).map(async room => {
          const inv = await api.listInvigilators(room.examRoomId)
          if (inv.code !== 0) throw Error(inv.message || '监考名单读取失败')
          return { ...room, invigilators: inv.data.items || [] }
        }))
        if (current()) this.arrangeRooms = rooms
      } catch (error) { if (current()) this.arrangeError = error?.message || '考场读取失败' }
    },
    onInvigilatorPicked(value, items) {
      this.invigilatorForm = { teacherKey: value || '', teacherName: items?.[0]?.raw?.teacherName || items?.[0]?.label || '' }
    },
    async arrangeCommand(command) {
      if (this.saving || !this.canArrangeRooms) return
      const id = this.arrangeCourse?.examCourseId, identity = this.identityKey
      const current = () => id === this.arrangeCourse?.examCourseId && identity === this.identityKey && this.arrangeVisible
      this.saving = true; this.arrangeError = ''
      try {
        const res = await command()
        if (!current()) return
        if (res.code !== 0) { this.arrangeError = res.message; return }
        await this.readArrangeRooms()
        if (current()) await this.refresh()
      } catch (error) { if (current()) this.arrangeError = error?.message || '办理结果待核对，请重新打开考场确认' }
      finally { if (identity === this.identityKey) this.saving = false }
    },
    async assignFrozenSeats(room) {
      const ids = this.arrangeCourse?.rosterIdentity?.studentIds || []
      if (this.arrangeRooms.length !== 1 || room.plannedCount || !ids.length) return
      if (ids.length > Number(room.capacity || 0)) { this.arrangeError = '冻结名单人数超过考场容量，请先核对考场安排'; return }
      await this.arrangeCommand(() => api.assignSeats(room.examRoomId, ids.map(String)))
    },
    async assignRoomInvigilator(room) {
      if (!this.invigilatorForm.teacherKey) return
      const body = { ...this.invigilatorForm, role: 'ASSISTANT' }
      await this.arrangeCommand(() => api.addInvigilator(room.examRoomId, body))
    },
    async submitRoom() {
      if (this.saving || !this.canArrangeRooms) return
      if (!this.roomForm.classroomText) { toast.error('考场名必填'); return }
      const id = this.arrangeCourse.examCourseId, body = { ...this.roomForm }
      await this.arrangeCommand(() => api.addRoom(id, body))
    },
    printSeating(roomId) {
      this.$router.push({ path: '/admin/academic-affairs/exam/print/seating', query: { roomId } })
    },
    async openPatrol() {
      this.patrolForm = { teacherKey: '', teacherName: '', patrolDate: '', startTime: '', endTime: '', areaScope: '' }
      this.patrolError = ''; this.patrolVisible = true
      const res = await api.listPatrols(this.current.batchId)
      this.patrols = res.code === 0 ? (res.data.items || []) : []
    },
    async submitPatrol() {
      if (!this.patrolForm.teacherKey) { this.patrolError = '巡考教师工号必填'; return }
      this.saving = true
      const res = await api.addPatrol(this.current.batchId, this.patrolForm)
      this.saving = false
      if (res.code === 0) {
        toast.success('已排巡考')
        this.patrolForm = { teacherKey: '', teacherName: '', patrolDate: '', startTime: '', endTime: '', areaScope: '' }
        const r = await api.listPatrols(this.current.batchId)
        this.patrols = r.code === 0 ? (r.data.items || []) : []
        await this.refresh()
      } else this.patrolError = res.message
    },
    async onConfirm() { const a = this.pendingAction; this.pendingAction = null; this.confirmVisible = false; if (a) await a() }
  }
}
</script>

<style scoped>
.aaexam-layout { display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: 16px; }
.aaexam-detail { min-width: 0; }
.aaexam-batches { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.aaexam-batch { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 10px 12px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 8px; cursor: pointer; }
.aaexam-batch.is-active { border-color: var(--primary-color, #2563eb); background: var(--primary-bg, #eff6ff); }
.aaexam-batch-name { min-width: 0; font-weight: 500; overflow-wrap: anywhere; }
.aaexam-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; margin-bottom: 12px; }
.aaexam-title { font-size: 16px; font-weight: 600; margin-bottom: 4px; }
.aaexam-actions { display: flex; justify-content: flex-end; gap: 8px; flex-wrap: wrap; }
.aaexam-readiness { display: grid; grid-template-columns: repeat(6, minmax(110px, 1fr)); gap: 10px; margin-bottom: 12px; }
.aaexam-readiness__item { min-width: 0; padding: 12px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 10px; background: var(--fill-light, #f8fafc); display: flex; flex-direction: column; gap: 3px; }
.aaexam-readiness__item span { font-size: 12px; color: var(--text-secondary, #64748b); }
.aaexam-readiness__item strong { font-size: 20px; line-height: 1.2; }
.aaexam-readiness__item small { color: var(--text-secondary, #64748b); overflow-wrap: anywhere; }
.aaexam-readiness__item.is-risk { border-color: var(--warning-color, #d97706); background: #fffbeb; }
.aaexam-readiness__item.is-ready { border-color: var(--success-color, #16a34a); background: #f0fdf4; }
.aaexam-readiness__item.is-conclusion strong { font-size: 16px; }
.aaexam-stats { display: flex; gap: 16px; flex-wrap: wrap; padding: 10px 12px; background: var(--fill-light, #f8fafc); border-radius: 8px; margin: 12px 0; font-size: 13px; }
.aaexam-stats .is-warn { color: var(--warning-color, #d97706); font-weight: 600; }
.aaexam-section-title { font-weight: 500; margin: 14px 0 8px; }
.aaexam-form { display: flex; flex-direction: column; gap: 12px; }
.aaexam-candidate-toolbar { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; align-items: center; }
.aaexam-candidate-list { max-height: 420px; overflow: auto; padding: 10px 12px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 8px; }
.aaexam-preview { display: flex; flex-direction: column; gap: 8px; padding: 10px 12px; border-radius: 8px; background: var(--fill-light, #f8fafc); }
.aaexam-preview__summary { display: flex; gap: 6px; flex-wrap: wrap; }
.aaexam-preview__blocked { margin: 0; padding-left: 20px; color: var(--warning-color, #d97706); }
.aaexam-auto-block { display: flex; flex-direction: column; gap: 8px; padding: 10px 12px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 8px; }
.aaexam-auto-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.aaexam-auto-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; align-items: center; }
.aaexam-auto-row.is-session { grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr) auto; }
.aaexam-auto-sep { color: var(--text-secondary, #64748b); }
.aaexam-rooms, .aaexam-incidents { list-style: none; margin: 0 0 8px; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.aaexam-rooms li, .aaexam-incidents li { display: flex; justify-content: space-between; gap: 12px; padding: 8px 12px; background: var(--fill-light, #f8fafc); border-radius: 6px; }
.aaexam-rooms li { flex-wrap: wrap; }
.aaexam-room-actions { flex: 1 0 100%; display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.aaexam-room-actions p { flex-basis: 100%; margin: 0; }
.aaexam-mode-grid { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 16px; align-items: start; }
.aaexam-mode-main, .aaexam-mode-aside { min-width: 0; padding: 16px; border: 1px solid #dce5f2; border-radius: 12px; background: #fff; }
.aaexam-mode-aside { position: sticky; top: 8px; }
.aaexam-mode-main > .app-inline-alert { margin-bottom: 12px; }
.aaexam-panel-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 14px; }
.aaexam-panel-head h2, .aaexam-mode-aside h2 { margin: 0; color: #17365f; font-size: 17px; }
.aaexam-panel-head p { margin: 5px 0 0; color: #71839f; font-size: 12px; line-height: 1.55; }
.aaexam-panel-head > span { flex: 0 0 auto; padding: 4px 9px; border-radius: 999px; background: #edf4ff; color: #2f66c5; font-size: 12px; }
.aaexam-evidence { display: grid; gap: 0; margin: 12px 0; }
.aaexam-evidence > div { padding: 10px 0; border-bottom: 1px solid #edf1f7; }
.aaexam-evidence dt { margin-bottom: 4px; color: #71839f; font-size: 11px; }
.aaexam-evidence dd { margin: 0; color: #17365f; font-size: 13px; line-height: 1.55; overflow-wrap: anywhere; }
.mp-link.is-danger { color: #c2410c; }

@media (max-width: 1080px) {
  .aaexam-layout { grid-template-columns: 240px minmax(0, 1fr); }
  .aaexam-readiness { grid-template-columns: repeat(3, minmax(120px, 1fr)); }
  .aaexam-mode-grid { grid-template-columns: minmax(0, 1fr) 280px; }
}

@media (max-width: 760px) {
  .aaexam-layout, .aaexam-mode-grid { grid-template-columns: 1fr; }
  .aaexam-mode-aside { position: static; }
  .aaexam-list { max-height: 220px; overflow: auto; }
  .aaexam-head { flex-direction: column; }
  .aaexam-actions { justify-content: flex-start; width: 100%; }
  .aaexam-readiness { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .aaexam-candidate-toolbar, .aaexam-auto-row, .aaexam-auto-row.is-session { grid-template-columns: 1fr; }
  .aaexam-auto-sep { display: none; }
  .aaexam-rooms li, .aaexam-incidents li { flex-direction: column; }
}
</style>
