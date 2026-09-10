<template>
  <ModulePageShell
    :title="pageMeta.title"
    :subtitle="pageMeta.subtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/schedule')">返回课表批次</AppButton>
      <AppButton v-if="tab === 'rules' && canManageRules" variant="primary" :disabled="!canWriteRules" @click="openRuleEditor">维护规则版本</AppButton>
      <AppButton v-else-if="tab === 'auto'" variant="primary" :disabled="!autoBatchId || autoLoading" @click="runAuto(true)">运行试排</AppButton>
      <AppButton v-else-if="tab === 'conflict'" variant="primary" :disabled="!conflictBatchId" @click="loadConflict">处理当前冲突</AppButton>
      <AppButton v-else-if="tab === 'import'" variant="primary" :disabled="!canImportBatch" @click="importVisible = true">上传并预校验</AppButton>
      <AppButton v-else-if="tab === 'result'" variant="primary" :disabled="!workbench" @click="openPublishedSchedule">查看正式版本</AppButton>
      <AppButton v-else-if="tab === 'adjust' && workbench?.batchStatus === 'PUBLISHED'" variant="primary" :disabled="!hasPublishedGap || !canCorrectSchedule" @click="openCorrectionDraft()">创建纠错草稿</AppButton>
    </template>

    <div v-if="tab !== 'room'" class="mp-stack aasg-page-context">
      <AaScheduleObjectBar
        :name="contextObject.name"
        :identity="contextObject.identity"
        :source="contextObject.source"
        :status="contextObject.status"
        :owner="ctx.currentRole.roleName || '教务排课岗'"
        next-owner="冲突核对岗 → 课表预发布 / 发布岗"
      />
      <AaScheduleStageRail mode="scheduling" :active-index="pageMeta.stage" />
    </div>

    <ErrorState v-if="routeError" :description="routeError" />
    <div v-else-if="tab === 'room'" class="mp-stack">
      <AppInlineAlert type="info" title="核对教室占用时段" description="按日期查看已批准预约和正式课表占用；未列出占用不代表保证空闲，安排课位仍须通过正式冲突检查。" />
      <AaResourceOccupancyView v-if="canReadOccupancy" />
      <ErrorState v-else description="当前身份没有资源占用查看权限，请由教学资源负责人核对教室时段。" />
    </div>
    <div v-else-if="['import', 'result', 'adjust'].includes(tab)" class="mp-stack">
      <AppSectionCard :title="pageMeta.sectionTitle">
        <AppScheduleBatchPicker v-model="workbenchBatchId" @change="loadWorkbench" />
        <p class="mp-note">请选择要查看或办理的课表批次。</p>
        <ErrorState v-if="workbenchError" :description="workbenchError" @retry="loadWorkbench" />
        <LoadingState v-else-if="workbenchLoading" />
        <template v-else-if="workbench">
          <p>{{ workbench.batchName }} · {{ batchStatusLabel(workbench.batchStatus) }}</p>
          <template v-if="tab === 'import'">
            <p>下载当前模板，上传排课结果后先预检，再明确确认导入；不会直接执行自动排课。</p>
            <AppButton :disabled="!canImportBatch" @click="importVisible = true">导入当前批次排课结果</AppButton>
            <p v-if="!canImportBatch" class="mp-note">仅具有导入权限的可编辑草稿允许导入。</p>
          </template>
          <template v-else-if="tab === 'result'">
            <p>应排 {{ workbench.expectedHours }} 节，已排 {{ workbench.scheduledHours }} 节；此批次状态以服务端结果为准。</p>
            <AppButton @click="openPublishedSchedule">查看本批次课表</AppButton>
          </template>
          <template v-else>
            <AppButton v-if="workbench.batchStatus === 'DRAFT'" :disabled="!canCorrectSchedule" @click="openBatchEditor">进入本批次编排</AppButton>
            <AppButton v-else-if="hasPublishedGap" :disabled="!canCorrectSchedule" @click="openCorrectionDraft()">创建纠错草稿后补排</AppButton>
            <p v-else class="mp-note">当前批次不允许直接编辑。请返回排课工作台核对状态和正式可用动作。</p>
          </template>
        </template>
      </AppSectionCard>
    </div>
    <div v-else-if="tab === 'workbench'" class="mp-stack">
      <AppSectionCard title="排课批次与当前进度">
        <div class="aasg-workbench-filter">
          <label class="aasg-field">
            <span>课表批次</span>
            <AppScheduleBatchPicker v-model="workbenchBatchId" @change="loadWorkbench" />
          </label>
          <AppButton size="small" :loading="workbenchLoading" :disabled="!workbenchBatchId" @click="loadWorkbench">刷新进度</AppButton>
        </div>
      </AppSectionCard>

      <ErrorState v-if="workbenchError" :description="workbenchError" @retry="loadWorkbench" />
      <LoadingState v-else-if="workbenchLoading" />
      <template v-else-if="workbench">
        <AppSectionCard :title="`${workbench.batchName || '排课批次'} · ${batchStatusLabel(workbench.batchStatus)}`">
          <div class="aasg-flow" aria-label="排课业务流程">
            <div v-for="(step, index) in workbench.workflow.steps" :key="step.key" :class="['aasg-flow-step', `is-${step.state}`]">
              <span class="aasg-flow-index">{{ index + 1 }}</span>
              <strong>{{ step.label }}</strong>
            </div>
          </div>
          <div class="aasg-current-action">
            <div>
              <span>当前状态</span>
              <strong>{{ currentStageLabel }}</strong>
              <small>{{ workbench.workflow.nextAction.description }}</small>
            </div>
            <AppButton
              variant="primary"
              size="small"
              :disabled="workbench.workflow.nextAction.code === 'BATCH_REISSUE' && !canCorrectSchedule"
              :title="workbench.workflow.nextAction.code === 'BATCH_REISSUE' && !canCorrectSchedule ? '当前身份没有课表编辑权限' : ''"
              @click="runWorkbenchAction(workbench.workflow.nextAction.code)"
            >
              下一步：{{ workbench.workflow.nextAction.label }}
            </AppButton>
          </div>
          <AppInlineAlert
            v-if="workbench.workflow.blockers.length"
            type="warning"
            title="当前阻断原因"
            :description="workbench.workflow.blockers.join('；')"
          />
          <AppInlineAlert v-else type="success" title="当前步骤无阻断" description="可以按右侧“下一步”继续推进。" />
        </AppSectionCard>

        <div class="aasg-metric-grid">
          <div v-for="card in workbenchCards" :key="card.label" :class="['aasg-metric', { 'is-alert': card.alert }]">
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
            <small>{{ card.note }}</small>
          </div>
        </div>

        <AppInlineAlert
          v-if="hasPublishedGap && !canCorrectSchedule"
          type="warning"
          title="当前身份只能查看漏排"
          description="请切换到拥有课表编辑权限的教务身份后创建纠错草稿；当前正式课表不会下线。"
        />

        <AppSectionCard v-if="hasPublishedGap && canCorrectSchedule" title="漏排任务处理中心">
          <div class="aasg-repair-center">
            <div class="aasg-repair-copy">
              <span class="aasg-repair-kicker">当前正式课表不下线</span>
              <strong>保留已排 {{ workbench.scheduledHours }} 节，只补剩余 {{ repairRemaining }} 节</strong>
              <p>创建纠错草稿会复制当前全部有效课位。老师学生 PC 和老师学生小程序继续使用现在的正式课表；待纠错草稿补齐并通过发布门禁后，系统再一次性切换四端正式版本。</p>
            </div>
            <div class="aasg-repair-facts" aria-label="纠错草稿影响范围">
              <div><span>应排</span><strong>{{ workbench.expectedHours }}</strong><small>节</small></div>
              <div><span>直接保留</span><strong>{{ workbench.scheduledHours }}</strong><small>节</small></div>
              <div class="is-gap"><span>继续补排</span><strong>{{ repairRemaining }}</strong><small>节</small></div>
            </div>
            <AppButton variant="primary" @click="openCorrectionDraft()">
              创建纠错草稿（保留已排 {{ workbench.scheduledHours }} 节）
            </AppButton>
          </div>
        </AppSectionCard>

        <AppSectionCard title="排课任务队列">
          <p v-if="hasPublishedGap && canCorrectSchedule" class="mp-note aasg-queue-note">当前是四端正在使用的正式版本，不能直接写入。点击“创建草稿后补排”，系统会先保留现有课位，再把你带到对应班级和教学任务。<template v-if="workbench.taskQueueTotal > workbench.taskQueue.length"> 当前显示优先级最高的 {{ workbench.taskQueue.length }} / {{ workbench.taskQueueTotal }} 项。</template></p>
          <p v-else class="mp-note aasg-queue-note">默认把未排、部分漏排放在前面。教务员不需要记班级 ID 或教学任务 ID，点击“去排课”即可带入对应批次、班级和任务。<template v-if="workbench.taskQueueTotal > workbench.taskQueue.length"> 当前显示优先级最高的 {{ workbench.taskQueue.length }} / {{ workbench.taskQueueTotal }} 项。</template></p>
          <EmptyState v-if="!workbench.taskQueue.length" title="当前没有待处理任务" description="教学任务已排齐；请继续检查冲突并进入预发布。" />
          <DataTable v-else :columns="taskQueueColumns" :rows="workbench.taskQueue" row-key="taskId">
            <template #cell-course="{ row }">
              <div class="mp-cell-main">{{ row.courseName || row.courseCode || '未命名课程' }}</div>
              <div class="mp-cell-sub">{{ row.className || '教学班待确认' }} · {{ row.teacherName || '教师待确认' }}</div>
            </template>
            <template #cell-progress="{ row }">
              <div class="mp-cell-main">{{ row.scheduledSessions }} / {{ row.expectedSessions }} 节</div>
              <div class="mp-cell-sub">剩余 {{ row.remainingSessions }} 节 · 总学时 {{ row.totalHours || '—' }}</div>
            </template>
            <template #cell-requirement="{ row }">
              <div class="mp-cell-main">{{ weekRangeText(row) }}</div>
              <div class="mp-cell-sub">{{ roomRequirementText(row.requiredRoomType) }}</div>
            </template>
            <template #cell-status="{ row }">
              <StatusTag :type="row.issueType === 'NOT_READY' ? 'warning' : 'danger'" :label="row.issueLabel" dot />
            </template>
            <template #cell-ops="{ row }">
              <button v-if="row.canSchedule && row.classId" class="mp-link" @click="openTask(row)">去排课</button>
              <button v-else-if="hasPublishedGap && canCorrectSchedule && row.classId" class="mp-link" @click="openCorrectionDraft(row)">创建草稿后补排</button>
              <button v-else-if="workbench.batchStatus === 'PUBLISHED'" class="mp-link" @click="openPublishedSchedule">查看正式课表</button>
              <button v-else class="mp-link" @click="openTeachingTasks">完善任务</button>
            </template>
          </DataTable>
        </AppSectionCard>
      </template>
      <EmptyState v-else title="请选择课表批次" description="选择批次后，系统会汇总教学任务、漏排、冲突、教师异议并给出下一步。" />
    </div>

    <!-- V2-03 第一施工卡：排课规则中心 -->
    <div v-else-if="tab === 'rules'" class="mp-stack">
      <AppInlineAlert
        type="info"
        title="规则只影响自动排课"
        description="手工排课和导入结果不会被规则自动改写；批次级规则覆盖学期默认规则，已发布课表不允许再修改参数。"
      />

      <AppInlineAlert
        v-if="!canManageRules"
        type="warning"
        title="当前角色为只读查看"
        description="学院和任课教师可以查看学校排课口径，但只有教务处或学校管理员可以修改。"
      />
      <AppInlineAlert
        v-if="termArchived"
        type="warning"
        title="该学期已经归档"
        description="归档学期的排课规则已冻结，只能查看，不能新增、修改或删除。"
      />
      <AppInlineAlert
        v-if="slotLoadWarning"
        type="warning"
        title="作息节次读取失败"
        :description="slotLoadWarning"
      />

      <AppSectionCard title="规则范围">
        <div class="aasg-bar">
          <label class="aasg-field is-term">
            <span>学期</span>
            <AppTermEntityPicker v-model="termId" placeholder="请选择学期" @change="onTermChange" />
          </label>
          <div class="aasg-grow" />
          <AppButton
            v-if="canManageRules"
            variant="primary"
            size="small"
            :disabled="!canWriteRules || catalogLoading"
            @click="openRuleEditor"
          >
            新增规则
          </AppButton>
        </div>
        <div v-if="termInfo" class="aasg-term-facts">
          <span>{{ termInfo.termName || `${termInfo.yearCode || ''} 第${termInfo.termNo || '—'}学期` }}</span>
          <span>教学周 {{ termInfo.teachingWeeks || '未配置' }} 周</span>
          <StatusTag :type="termArchived ? 'warning' : 'success'" :label="termStatusLabel(termInfo.status)" dot />
        </div>
      </AppSectionCard>

      <ErrorState v-if="catalogError" :description="catalogError" @retry="loadCatalog" />
      <ErrorState v-else-if="termError" :description="termError" @retry="onTermChange" />

      <AppSectionCard v-if="editorVisible && !catalogError && !termError" :title="editingRuleId ? '修改排课规则' : '新增排课规则'">
        <div class="aasg-editor">
          <label class="aasg-field">
            <span>业务参数</span>
            <select v-model="ruleForm.ruleKey" class="aasg-input" :disabled="saving || Boolean(editingRuleId)" @change="onRuleKeyChange">
              <option value="">请选择参数</option>
              <option v-for="meta in catalog" :key="meta.ruleKey" :value="meta.ruleKey">{{ meta.group }} · {{ meta.label }}</option>
            </select>
          </label>

          <label class="aasg-field">
            <span>生效范围</span>
            <select v-model="ruleForm.scopeType" class="aasg-input" :disabled="saving || Boolean(editingRuleId)" @change="onScopeChange">
              <option value="TERM">本学期默认</option>
              <option value="BATCH">指定课表批次</option>
            </select>
          </label>

          <label v-if="ruleForm.scopeType === 'BATCH'" class="aasg-field">
            <span>课表批次</span>
            <AppScheduleBatchPicker v-model="ruleForm.batchId" :disabled="saving || Boolean(editingRuleId)" />
          </label>

          <div v-if="selectedMeta" class="aasg-meta">
            <strong>{{ selectedMeta.label }}</strong>
            <span>{{ selectedMeta.description }}</span>
          </div>

          <div v-if="selectedMeta?.control === 'WEEK_RANGE'" class="aasg-control-grid is-two">
            <label class="aasg-field"><span>起始周</span><input v-model.number="ruleForm.value.startWeek" class="aasg-input" type="number" min="1" max="30" /></label>
            <label class="aasg-field"><span>结束周</span><input v-model.number="ruleForm.value.endWeek" class="aasg-input" type="number" min="1" :max="termInfo?.teachingWeeks || 30" /></label>
          </div>

          <div v-else-if="selectedMeta?.control === 'WEEKDAY_MULTI'" class="aasg-choice-panel">
            <div class="aasg-choice-title">选择允许自动排课的星期</div>
            <label v-for="day in weekdayOptions" :key="day.value" class="aasg-check">
              <input v-model="ruleForm.value" type="checkbox" :value="day.value" />{{ day.label }}
            </label>
          </div>

          <div v-else-if="selectedMeta?.control === 'SLOT_MULTI'" class="aasg-choice-panel">
            <div class="aasg-choice-title">选择允许自动排课的节次</div>
            <label v-for="slot in availableSlots" :key="slot.slotNo" class="aasg-check">
              <input v-model="ruleForm.value" type="checkbox" :value="slot.slotNo" />{{ slotLabel(slot) }}
            </label>
          </div>

          <div v-else-if="selectedMeta?.control === 'FORBIDDEN_GRID'" class="aasg-forbidden">
            <div class="aasg-choice-title">勾选全校统一禁排时段</div>
            <div v-for="day in weekdayOptions" :key="day.value" class="aasg-forbidden-row">
              <strong>{{ day.label }}</strong>
              <label class="aasg-check is-whole-day">
                <input type="checkbox" :checked="isForbidden(day.value, null)" @change="toggleForbidden(day.value, null)" />整天
              </label>
              <label v-for="slot in availableSlots" :key="`${day.value}-${slot.slotNo}`" class="aasg-check">
                <input
                  type="checkbox"
                  :disabled="isForbidden(day.value, null)"
                  :checked="isForbidden(day.value, slot.slotNo)"
                  @change="toggleForbidden(day.value, slot.slotNo)"
                />第{{ slot.slotNo }}节
              </label>
            </div>
          </div>

          <label v-else-if="selectedMeta?.control === 'INTEGER'" class="aasg-field is-number">
            <span>{{ selectedMeta.label }}</span>
            <div class="aasg-number-wrap">
              <input v-model.number="ruleForm.value" class="aasg-input" type="number" :min="selectedMeta.min" :max="selectedMeta.max" />
              <em>{{ selectedMeta.unit || '' }}</em>
            </div>
          </label>

          <div v-else-if="selectedMeta?.control === 'BOOLEAN'" class="aasg-choice-panel">
            <div class="aasg-choice-title">{{ selectedMeta.label }}</div>
            <label class="aasg-radio"><input v-model="ruleForm.value" type="radio" :value="true" />开启</label>
            <label class="aasg-radio"><input v-model="ruleForm.value" type="radio" :value="false" />关闭</label>
          </div>

          <label class="aasg-field">
            <span>备注</span>
            <textarea v-model.trim="ruleForm.remark" class="aasg-textarea" maxlength="500" placeholder="说明本校采用该参数的原因或使用边界（选填）" />
          </label>

          <AppInlineAlert v-if="formError" type="danger" title="无法保存" :description="formError" />
          <div class="aasg-editor-actions">
            <AppButton :disabled="saving" @click="closeRuleEditor">取消</AppButton>
            <AppButton variant="primary" :loading="saving" :disabled="!canWriteRules" @click="saveRule">保存规则</AppButton>
          </div>
        </div>
      </AppSectionCard>

      <ErrorState v-if="ruleError" :description="ruleError" @retry="loadRules" />
      <LoadingState v-else-if="ruleLoading || catalogLoading" />
      <template v-else-if="!catalogError && !termError">
        <EmptyState
          v-if="!rules.length"
          title="该学期尚未配置排课规则"
          description="系统会使用安全默认值运行自动排课；建议教务处结合本校教学周、作息节次和教师管理制度逐项确认。"
        />
        <DataTable v-else :columns="ruleColumns" :rows="rules" row-key="ruleId">
          <template #cell-rule="{ row }">
            <div class="mp-cell-main">{{ row.ruleLabel }}</div>
            <div class="mp-cell-sub">{{ row.ruleGroup }}</div>
          </template>
          <template #cell-scope="{ row }">
            <div class="mp-cell-main">{{ scopeLabel(row) }}</div>
            <div class="mp-cell-sub">{{ row.batchId ? '应用于所选课表批次' : '作为该学期默认参数' }}</div>
          </template>
          <template #cell-value="{ row }">
            <div :class="['mp-cell-main', { 'is-danger-text': row.invalidValue }]">{{ row.valueSummary || '未设置' }}</div>
            <div v-if="row.remark" class="mp-cell-sub">{{ row.remark }}</div>
            <div v-if="row.validationMessage" class="mp-cell-sub is-danger-text">{{ row.validationMessage }}</div>
          </template>
          <template #cell-status="{ row }">
            <StatusTag :type="row.invalidValue ? 'danger' : 'success'" :label="row.invalidValue ? '配置异常' : '已启用'" dot />
          </template>
          <template #cell-ops="{ row }">
            <template v-if="canWriteRules">
              <button v-if="catalogByKey[row.ruleKey]" class="mp-link" @click="editRule(row)">修改</button>
              <button class="mp-link is-danger" @click="confirmDeleteRule(row)">删除</button>
            </template>
            <span v-else class="mp-cell-sub">只读</span>
          </template>
        </DataTable>
      </template>

      <AppSectionCard v-if="catalog.length && !catalogError" title="学校未配置时采用的安全默认值">
        <div class="aasg-default-grid">
          <div v-for="meta in catalog" :key="meta.ruleKey">
            <strong>{{ meta.label }}</strong>
            <span>{{ formatValue(meta, meta.defaultValue) }}</span>
          </div>
        </div>
      </AppSectionCard>
    </div>

    <!-- 教师可用时间：本轮保持既有流程 -->
    <div v-else-if="tab === 'availability'" class="mp-stack">
      <EmptyState v-if="!avails.length" title="暂无教师不可排时间提交" description="教师提交不可排课时段后在此采纳" />
      <DataTable v-else :columns="availColumns" :rows="avails" row-key="availabilityId">
        <template #cell-slot="{ row }">周{{ row.weekday }} 第{{ row.slotNo }}节</template>
        <template #cell-status="{ row }"><StatusTag :type="row.status === 'ADOPTED' ? 'success' : row.status === 'REJECTED' ? 'danger' : 'primary'" :label="availabilityStatusLabel(row.status)" dot /></template>
        <template #cell-ops="{ row }">
          <button v-if="row.status === 'PENDING'" class="mp-link" @click="reviewAvail(row.availabilityId, 'ADOPT')">采纳</button>
          <button v-if="row.status === 'PENDING'" class="mp-link is-danger" @click="rejectAvail(row.availabilityId)">驳回</button>
        </template>
      </DataTable>
    </div>

    <!-- 自动排课：本轮不改算法 -->
    <div v-else-if="tab === 'auto'" class="mp-stack">
      <div class="aasg-bar">
        <AppScheduleBatchPicker v-model="autoBatchId" style="max-width:260px" @change="syncBatchQuery(autoBatchId)" />
        <AppButton variant="ghost" size="small" :loading="autoLoading" @click="runAuto(true)">试排预览</AppButton>
        <AppButton variant="primary" size="small" :loading="autoLoading" @click="doAuto">一键自动排课</AppButton>
        <AppButton variant="ghost" size="small" @click="doClearAuto">清除自动排课结果</AppButton>
      </div>
      <AppInlineAlert type="info" description="自动排课只处理已确认、已设周学时且未标记不排课的教学任务；手工排课不会被覆盖，排不下的任务会返回明确原因。" />
      <template v-if="autoResult">
        <div class="aasg-summary">
          <span class="is-ok">已排入 {{ autoResult.placedSessions }} 节 / {{ autoResult.placedTasks }} 个任务</span>
          <span :class="{ 'is-bad': autoResult.missedTasks }">漏排 {{ autoResult.missedTasks }} 个任务</span>
          <span>可用教室 {{ autoResult.roomPoolSize }} 间</span>
          <span v-if="autoResult.dryRun" class="is-warn">试排结果（未落库）</span>
        </div>
        <div v-if="autoMissSummary.length" class="aasg-section">
          <div class="aasg-section-title">漏排原因分布</div>
          <div class="aasg-reasons"><span v-for="item in autoMissSummary" :key="item.reason" class="aasg-reason-chip">{{ item.reasonLabel }} × {{ item.count }}</span></div>
        </div>
        <DataTable v-if="autoMisses.length" :columns="missColumns" :rows="autoMisses" row-key="taskId">
          <template #cell-course="{ row }">{{ row.courseName }}<span v-if="row.className" class="aasg-sub">（{{ row.className }}）</span></template>
          <template #cell-progress="{ row }">{{ row.placedSessions }} / {{ row.needSessions }} 节</template>
          <template #cell-reason="{ row }"><span class="aasg-tag is-hard">{{ row.reasonLabel }}</span></template>
          <template #cell-detail="{ row }"><span class="aasg-advice">{{ row.detail }}</span></template>
        </DataTable>
        <EmptyState v-else-if="!autoResult.missedTasks" title="全部排课成功" description="所有待排任务均已排入，无漏排" />
      </template>
      <EmptyState v-else title="尚未执行自动排课" description="选择课表批次后先试排预览，确认结果再正式落库" />
    </div>

    <!-- 冲突报告：本轮保持既有能力 -->
    <div v-else class="mp-stack">
      <div class="aasg-bar">
        <AppScheduleBatchPicker v-model="conflictBatchId" style="max-width:260px" @change="syncBatchQuery(conflictBatchId)" />
        <AppButton variant="primary" size="small" @click="loadConflict">生成冲突报告</AppButton>
      </div>
      <template v-if="conflict">
        <div class="aasg-summary">
          <span :class="{ 'is-bad': conflict.hardCount }">HARD 物理冲突 {{ conflict.hardCount }}</span>
          <span :class="{ 'is-warn': conflict.softCount }">SOFT 软冲突 {{ conflict.softCount }}</span>
          <span :class="conflict.canPrePublish ? 'is-ok' : 'is-bad'">{{ conflict.canPrePublish ? '可预发布' : '存在HARD冲突，禁止预发布' }}</span>
        </div>
        <div v-if="conflict.hardConflicts.length" class="aasg-section">
          <div class="aasg-section-title">HARD 冲突（必须清零）</div>
          <ul class="aasg-conflicts">
            <li v-for="(item, index) in conflict.hardConflicts" :key="`hard-${index}`">
              <span class="aasg-tag is-hard">{{ dimLabel(item.dimension) }}</span>
              周{{ item.weekday }}第{{ item.slotNo }}节：{{ item.itemA.courseName }}（{{ item.itemA.className }}） ⨯ {{ item.itemB.courseName }}（{{ item.itemB.className }}）
            </li>
          </ul>
        </div>
        <div v-if="conflict.softConflicts.length" class="aasg-section">
          <div class="aasg-section-title">SOFT 冲突（教师不可排时间）</div>
          <ul class="aasg-conflicts">
            <li v-for="(item, index) in conflict.softConflicts" :key="`soft-${index}`">
              <span class="aasg-tag is-soft">{{ item.item.teacherName }}</span>
              周{{ item.weekday }}第{{ item.slotNo }}节：{{ item.item.courseName }}（教师已登记不可排）
            </li>
          </ul>
        </div>
        <EmptyState v-if="!conflict.hardCount && !conflict.softCount" title="无冲突" description="该批次课表无 HARD/SOFT 冲突，可预发布" />
      </template>
    </div>

    <AaAuthoritativeImportDrawer v-if="importVisible && canImportBatch" v-model:visible="importVisible" title="导入当前批次排课结果" template-name="排课结果导入模板.xlsx"
      show-import-mode :download-template-fn="() => academicAffairsApi.downloadScheduleImportTemplate()"
      :upload-fn="(file, mode) => academicFileExchangeApi.uploadScheduleImport(workbenchBatchId, file, mode)"
      @imported="loadWorkbench" />
    <AppConfirmDialog
      v-model:visible="confirmVisible"
      :title="confirmTitle"
      :message="confirmMessage"
      :require-reason="confirmRequireReason"
      :reason-label="confirmReasonLabel"
      @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppInlineAlert, AppConfirmDialog, AppTermEntityPicker, AppScheduleBatchPicker, AppSectionCard } from '@/components/common'
import { academicAffairsApi, academicAffairsSchedulingApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { matchPermission } from '@/config/navPlan'
import { toast } from '@/utils/toast'
import { academicRouteState, academicIdentity, createAcademicRequestGate } from '../academicFlowContext.js'
import { currentUserFromToken } from '@/services/http/client'
import { academicFileExchangeApi } from '../api/academic-file-exchange.api'
import AaAuthoritativeImportDrawer from '../components/AaAuthoritativeImportDrawer.vue'
import AaResourceOccupancyView from './AaResourceOccupancyView.vue'
import AaScheduleObjectBar from '../components/AaScheduleObjectBar.vue'
import AaScheduleStageRail from '../components/AaScheduleStageRail.vue'

const MANAGE_ROLES = new Set(['PLATFORM_SUPER_ADMIN', 'SCHOOL_ADMIN', 'ACADEMIC_ADMIN'])
const DEFAULT_DAYS = [
  { value: 1, label: '周一' }, { value: 2, label: '周二' }, { value: 3, label: '周三' },
  { value: 4, label: '周四' }, { value: 5, label: '周五' }, { value: 6, label: '周六' },
  { value: 7, label: '周日' }
]

export default {
  name: 'AaSchedulingConsoleView',
  components: { ModulePageShell, DataTable, StatusTag, EmptyState, LoadingState, ErrorState, AppButton, AppInlineAlert, AppConfirmDialog, AppTermEntityPicker, AppScheduleBatchPicker, AppSectionCard, AaAuthoritativeImportDrawer, AaResourceOccupancyView, AaScheduleObjectBar, AaScheduleStageRail },
  props: { ctx: { type: Object, required: true } },
  inject: { academicFlow: { default: null } },
  data() {
    return {
      academicAffairsApi, academicFileExchangeApi, routeError: '', importVisible: false, routeSyncing: false, disposed: false,
      tab: 'workbench',
      tabs: [{ key: 'workbench', label: '排课工作台' }, { key: 'rules', label: '排课规则' }, { key: 'availability', label: '教师不可排时间' }, { key: 'auto', label: '自动排课' }, { key: 'conflict', label: '冲突报告' }, { key: 'room', label: '教室可用时间' }, { key: 'import', label: '导入排课结果' }, { key: 'result', label: '排课结果' }, { key: 'adjust', label: '排课调整' }],
      termId: '', termInfo: null,
      workbenchBatchId: '', workbench: null, workbenchLoading: false, workbenchError: '',
      rules: [], catalog: [], timeSlots: [],
      ruleLoading: false, catalogLoading: false, ruleError: '', catalogError: '', termError: '', slotLoadWarning: '',
      editorVisible: false, editingRuleId: '', saving: false, formError: '',
      ruleForm: { ruleKey: '', scopeType: 'TERM', batchId: '', value: null, remark: '' },
      avails: [], conflictBatchId: '', conflict: null,
      autoBatchId: '', autoResult: null, autoLoading: false,
      confirmVisible: false, confirmTitle: '', confirmMessage: '', pendingAction: null, pendingContextKey: '',
      confirmRequireReason: false, confirmReasonLabel: '',
      correctionTargetTask: null,
      ruleColumns: [
        { key: 'rule', title: '业务参数' }, { key: 'scope', title: '生效范围', width: '190px' },
        { key: 'value', title: '当前配置' }, { key: 'status', title: '状态', width: '110px' },
        { key: 'ops', title: '操作', width: '130px' }
      ],
      missColumns: [{ key: 'course', title: '课程' }, { key: 'teacherName', title: '教师' }, { key: 'progress', title: '已排/需排' }, { key: 'reason', title: '漏排原因' }, { key: 'detail', title: '处置建议' }],
      availColumns: [{ key: 'teacherName', title: '教师' }, { key: 'slot', title: '时段' }, { key: 'reason', title: '原因' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }],
      taskQueueColumns: [
        { key: 'course', title: '课程 / 教师 / 教学班' },
        { key: 'progress', title: '已排 / 应排', width: '170px' },
        { key: 'requirement', title: '周次 / 教室要求', width: '180px' },
        { key: 'status', title: '问题', width: '130px' },
        { key: 'ops', title: '下一步', width: '100px' }
      ]
    }
  },
  computed: {
    pageMeta() {
      const pages = {
        workbench: { title: '排课工作台', subtitle: '从就绪教学任务进入编排，按真实阻断推进到正式发布。', sectionTitle: '当前批次排课进度', stage: 2 },
        rules: { title: this.$route?.query?.tab === 'constraint' ? '排课约束' : '排课规则', subtitle: '规则与排课引擎同源，保留版本、作用范围和优先级。', sectionTitle: '规则与适用范围', stage: 1 },
        availability: { title: '教师可用时间', subtitle: '教师时间偏好作为排课约束输入，不直接改写正式课表。', sectionTitle: '教师可用时段', stage: 1 },
        auto: { title: '自动排课', subtitle: '保留已有课位，先试排并处理冲突，再进入发布门禁。', sectionTitle: '自动排课工作区', stage: 2 },
        conflict: { title: '冲突报告', subtitle: '硬冲突直达具体任务与课位，软提醒保留规则依据。', sectionTitle: '冲突与可解决路径', stage: 3 },
        room: { title: '教室可用时间', subtitle: '区分正式课表、预约和维修占用，排课仍由服务端最终校验。', sectionTitle: '资源占用', stage: 1 },
        import: { title: '导入排课结果', subtitle: '上传后先预校验，再按原始行号确认正式导入结果。', sectionTitle: '准备与预校验', stage: 2 },
        result: { title: '排课结果', subtitle: '读取指定批次和正式版本，不按列表顺序猜测当前课表。', sectionTitle: '指定批次排课结果', stage: 3 },
        adjust: { title: '排课调整', subtitle: '已发布结果不原地编辑；纠错草稿保留当前正式课表在线。', sectionTitle: '课表调整与纠错', stage: 3 }
      }
      return pages[this.tab] || pages.workbench
    },
    contextObject() {
      if (this.workbench) return {
        name: this.workbench.batchName || '当前课表批次',
        identity: `批次 #${this.workbench.batchId} · 学期 #${this.workbench.termId}`,
        source: '来源：正式教学任务、排课规则、教师时间与资源可用性',
        status: this.batchStatusLabel(this.workbench.batchStatus)
      }
      if (this.termInfo) return {
        name: this.termInfo.termName || `${this.termInfo.yearCode || ''} 第${this.termInfo.termNo || '—'}学期`,
        identity: `学期 #${this.termId} · ${this.pageMeta.title}`,
        source: '来源：当前正式学期与排课规则目录',
        status: this.termStatusLabel(this.termInfo.status)
      }
      return { name: this.pageMeta.sectionTitle, identity: '选择学期或课表批次后读取正式对象', source: '来源：教务排课服务', status: '对象待选择' }
    },
    canReadOccupancy() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.resourceOccupancy.view') },
    canImportBatch() { return this.workbench?.batchStatus === 'DRAFT' && matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.schedule.import') },
    canManageRules() { return MANAGE_ROLES.has(String(this.ctx.currentRole.roleCode || '').toUpperCase()) },
    canCorrectSchedule() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.schedule.edit') },
    repairRemaining() { return Math.max(0, Number(this.workbench?.expectedHours || 0) - Number(this.workbench?.scheduledHours || 0)) },
    hasPublishedGap() { return this.workbench?.batchStatus === 'PUBLISHED' && this.repairRemaining > 0 },
    termArchived() { return String(this.termInfo?.status || '').toUpperCase() === 'ARCHIVED' },
    canWriteRules() {
      return Boolean(
        this.canManageRules && this.termId && this.termInfo
        && !this.termArchived && !this.catalogError && !this.termError
      )
    },
    catalogByKey() { return Object.fromEntries(this.catalog.map(item => [item.ruleKey, item])) },
    selectedMeta() { return this.catalogByKey[this.ruleForm.ruleKey] || null },
    weekdayOptions() { return this.selectedMeta?.options?.length ? this.selectedMeta.options : DEFAULT_DAYS },
    availableSlots() {
      if (this.timeSlots.length) return this.timeSlots
      return Array.from({ length: 8 }, (_, index) => ({ slotNo: index + 1, slotName: `第${index + 1}节` }))
    },
    autoMisses() { return this.autoResult?.misses || [] },
    autoMissSummary() {
      const rows = this.autoResult?.misses || []
      const grouped = {}
      rows.forEach((row) => {
        grouped[row.reason] = grouped[row.reason] || { reason: row.reason, reasonLabel: row.reasonLabel, count: 0 }
        grouped[row.reason].count += 1
      })
      return Object.values(grouped).sort((a, b) => b.count - a.count)
    },
    currentStageLabel() {
      const current = this.workbench?.workflow?.steps?.find(row => row.state === 'current')
      return current?.label || '状态待确认'
    },
    workbenchCards() {
      if (!this.workbench) return []
      const row = this.workbench
      return [
        { label: '教学任务', value: row.totalTasks, note: `已确认 ${row.confirmedTaskCount} · 已就绪 ${row.readyTaskCount}`, alert: row.notReadyTaskCount > 0 },
        { label: '已排任务', value: row.scheduledTasks, note: `任务触达率 ${row.completionRate}%` },
        { label: '未排 / 漏排', value: `${row.unplacedTaskCount} / ${row.partiallyScheduledTaskCount}`, note: `共 ${row.missingTaskCount} 个待补齐`, alert: row.missingTaskCount > 0 },
        { label: '应排 / 已排节次', value: `${row.expectedHours} / ${row.scheduledHours}`, note: `剩余 ${Math.max(0, row.expectedHours - row.scheduledHours)} 节`, alert: row.expectedHours !== row.scheduledHours },
        { label: '硬 / 软冲突', value: `${row.hardConflicts} / ${row.softConflicts}`, note: '硬冲突必须清零', alert: row.hardConflicts > 0 },
        { label: '教师异议', value: row.teacherObjectionCount, note: `待处理偏好 ${row.pendingAvailabilityCount}`, alert: row.teacherObjectionCount > 0 }
      ]
    }
  },
  watch: {
    confirmVisible(value) { if (value) this.pendingContextKey = this.commandContextKey() },
    '$route.fullPath'() { this.syncRoute() },
    ctx() { this.syncRoute() },
    tab(value) {
      if (this.routeSyncing) return
      const requested = this.$route.query.tab === 'constraint' ? 'rules' : (this.$route.query.tab || 'workbench')
      if (requested !== value) { this.$router.push({ path: this.$route.path, query: { ...this.$route.query, tab: value } }); return }
      if (value === 'availability') this.loadAvails()
      if (value === 'workbench' && this.workbenchBatchId) this.loadWorkbench()
    }
  },
  async created() {
    this.routeGate = createAcademicRequestGate(() => this.routeContextKey())
    this.workbenchGate = createAcademicRequestGate(() => JSON.stringify([this.routeContextKey(), this.workbenchBatchId]))
    this.ruleGate = createAcademicRequestGate(() => JSON.stringify([this.routeContextKey(), this.termId]))
    await Promise.all([this.loadCatalog(), this.loadTimeSlots()])
    await this.syncRoute()
  },
  beforeUnmount() { this.disposed = true; this.routeGate.invalidate(); this.workbenchGate.invalidate(); this.ruleGate.invalidate(); this.pendingAction = null },
  methods: {
    switchTab(tab) { return this.$router.push({ path: this.$route.path, query: { ...this.$route.query, tab } }) },
    routeContextKey() { return JSON.stringify([this.academicFlow?.identity() || academicIdentity(currentUserFromToken(), this.ctx), this.$route?.fullPath]) },
    commandContextKey() { return JSON.stringify([this.disposed, this.routeContextKey(), this.termId, this.workbenchBatchId, this.autoBatchId, this.conflictBatchId]) },
    async syncRoute() {
      if (!this.routeGate || this.disposed) return
      const current = this.routeGate.begin()
      this.workbenchGate.invalidate(); this.ruleGate.invalidate()
      this.confirmVisible = false; this.pendingAction = null; this.importVisible = false; this.closeRuleEditor()
      this.workbench = null; this.workbenchLoading = false; this.workbenchError = ''; this.conflict = null; this.autoResult = null; this.autoLoading = false; this.avails = []
      this.rules = []; this.termInfo = null; this.ruleLoading = false; this.saving = false
      const state = academicRouteState(this.$route, { tabs: [...this.tabs.map(item => item.key), 'constraint'], defaultTab: 'workbench' })
      this.routeError = state.error
      this.routeSyncing = true; this.tab = state.tab === 'constraint' ? 'rules' : state.tab
      this.termId = state.termId; this.workbenchBatchId = state.batchId; this.autoBatchId = state.batchId; this.conflictBatchId = state.batchId
      await this.$nextTick(); this.routeSyncing = false
      if (!current() || state.error) return
      if (['rules', 'availability'].includes(this.tab) && !state.termId) {
        const currentTerm = await academicAffairsApi.getCurrentTerm()
        if (!current()) return
        if (currentTerm.code !== 0 || !currentTerm.data?.termId) {
          this.termError = currentTerm.message || '当前学期尚未配置，请先到教务基础确认正式学期'
          return
        }
        await this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, termId: String(currentTerm.data.termId) } })
        return
      }
      if (['rules', 'availability'].includes(this.tab)) await this.onTermChange()
      if (!current()) return
      if (this.tab === 'availability' && this.termId) await this.loadAvails()
      if (state.batchId && ['workbench', 'import', 'result', 'adjust'].includes(this.tab)) await this.loadWorkbench()
      if (state.batchId && this.tab === 'conflict') await this.loadConflict()
    },
    cloneValue(value) {
      if (value == null) return value
      return JSON.parse(JSON.stringify(value))
    },
    async loadWorkbench(value) {
      if (typeof value === 'string' || typeof value === 'number') this.workbenchBatchId = String(value)
      const batchId = this.workbenchBatchId
      const current = this.workbenchGate.begin()
      this.workbench = null; this.workbenchError = ''; this.workbenchLoading = false
      if (String(this.$route.query.batchId || '') !== batchId) {
        await this.syncBatchQuery(batchId); return
      }
      if (!batchId) return
      this.workbenchLoading = true
      const response = await academicAffairsApi.getScheduleSummary(batchId)
      if (!current()) return
      this.workbenchLoading = false
      if (response.code === 0 && String(response.data?.batchId) === batchId) this.workbench = response.data
      else this.workbenchError = response.code === 0 ? '返回的课表批次与当前入口不一致，请返回原队列核对' : (response.message || '指定排课批次读取失败，请返回原队列核对')
      this.academicFlow?.restorePosition()
    },
    syncBatchQuery(batchId) {
      const query = { ...this.$route.query }
      if (batchId) query.batchId = String(batchId); else delete query.batchId
      return this.$router.replace({ path: this.$route.path, query })
    },
    returnQuery() { const returnToken = this.academicFlow?.captureReturn(); return returnToken ? { returnToken } : {} },
    openBatchEditor() { this.$router.push({ path: `/admin/academic-affairs/schedule/${this.workbenchBatchId}/edit`, query: this.returnQuery() }) },
    batchStatusLabel(status) {
      return ({ DRAFT: '编排中', PRE_PUBLISHED: '预发布', PUBLISHED: '已正式发布', SUPERSEDED: '已被新版本替代', ARCHIVED: '已归档' })[status] || (status ? '状态待确认' : '状态待确认')
    },
    weekRangeText(row) { return row.startWeek && row.endWeek ? `第 ${row.startWeek}-${row.endWeek} 周` : '周次待确认' },
    roomRequirementText(value) { return value ? `教室要求：${value}` : '教室类型不限' },
    openTeachingTasks() { this.$router.push('/admin/academic-affairs/teaching-tasks') },
    openPublishedSchedule() { this.$router.push({ path: `/admin/academic-affairs/schedule/${this.workbenchBatchId}/views`, query: this.returnQuery() }) },
    openTask(row) {
      this.$router.push({
        path: `/admin/academic-affairs/schedule/${this.workbenchBatchId}/edit`,
        query: { classId: row.classId, className: row.className || '', taskId: row.taskId, ...this.returnQuery() }
      })
    },
    openCorrectionDraft(row = null) {
      if (!this.hasPublishedGap || !this.canCorrectSchedule) return
      this.correctionTargetTask = row
      this.confirmRequireReason = true
      this.confirmReasonLabel = '纠错原因（至少 5 个字）'
      this.confirmTitle = '创建漏排纠错草稿'
      this.confirmMessage = `系统会保留已排 ${this.workbench.scheduledHours} 节，只补剩余 ${this.repairRemaining} 节。创建期间老师学生 PC 和老师学生小程序继续使用当前正式课表，不会下线。`
      this.pendingAction = (reason) => this.createCorrectionDraft(reason)
      this.confirmVisible = true
    },
    async createCorrectionDraft(reason) {
      const context = this.commandContextKey()
      const sourceBatchId = this.workbenchBatchId
      const targetTask = this.correctionTargetTask
      this.correctionTargetTask = null
      const response = await academicAffairsApi.startScheduleCorrection(sourceBatchId, String(reason || '').trim())
      if (context !== this.commandContextKey()) return
      if (response.code !== 0) {
        toast.error(response.message || '创建纠错草稿失败')
        return
      }
      this.workbenchBatchId = String(response.data.batchId)
      await this.loadWorkbench()
      toast.success(`已保留 ${response.data.scheduledSessions} 节现有课位，可继续补排剩余 ${response.data.remainingSessions} 节`)
      if (targetTask?.classId) this.openTask(targetTask)
    },
    runWorkbenchAction(code) {
      if (code === 'TEACHING_TASKS') return this.openTeachingTasks()
      if (code === 'AVAILABILITY') return this.switchTab('availability')
      if (code === 'AUTO_DRY_RUN') return this.switchTab('auto')
      if (code === 'TASK_QUEUE') { document.querySelector('.aasg-queue-note')?.scrollIntoView({ behavior: 'smooth', block: 'start' }); return }
      if (code === 'CONFLICTS') return this.switchTab('conflict')
      if (code === 'HANDLE_OBJECTIONS') return this.$router.push(`/admin/academic-affairs/schedule/${this.workbenchBatchId}/edit`)
      if (['PRE_PUBLISH', 'PUBLISH'].includes(code)) return this.$router.push({ path: '/admin/academic-affairs/schedule/publish', query: { batchId: this.workbenchBatchId } })
      if (code === 'BATCH_REISSUE') return this.openCorrectionDraft()
      if (code === 'CHANGE_LEDGER') return this.$router.push('/admin/academic-affairs/schedule-change')
      this.$router.push(`/admin/academic-affairs/schedule/${this.workbenchBatchId}/views`)
    },
    async loadCatalog() {
      this.catalogLoading = true; this.catalogError = ''
      const response = await api.ruleCatalog()
      this.catalogLoading = false
      if (response.code === 0) this.catalog = response.data.items || []
      else { this.catalog = []; this.catalogError = response.message || '排课规则目录加载失败' }
    },
    async loadTimeSlots() {
      const response = await academicAffairsApi.getTimeSlots(false)
      if (response.code === 0) {
        this.timeSlots = (response.data || []).map(row => ({
          slotNo: Number(row.slotNo), slotName: row.slotName || `第${row.slotNo}节`,
          startTime: row.startTime || '', endTime: row.endTime || ''
        })).filter(row => Number.isInteger(row.slotNo) && row.slotNo > 0)
      } else {
        this.slotLoadWarning = '暂时无法读取学校作息，将显示第1—8节作为只读参考；保存时系统仍会按学校启用节次校验。'
      }
    },
    async onTermChange(value) {
      if (value !== undefined && value !== null) this.termId = value ? String(value) : ''
      const termId = this.termId
      const current = this.ruleGate.begin()
      this.closeRuleEditor(); this.termInfo = null; this.termError = ''; this.ruleError = ''; this.rules = []; this.ruleLoading = false
      if (String(this.$route.query.termId || '') !== termId) {
        const query = { ...this.$route.query }; if (termId) query.termId = termId; else delete query.termId
        await this.$router.replace({ path: this.$route.path, query }); return
      }
      if (!this.termId) { this.rules = []; this.termError = '请选择学期后查看排课规则'; return }
      const detail = await academicAffairsApi.getTermDetail(termId)
      if (!current()) return
      if (detail.code !== 0) {
        this.rules = []
        this.termError = detail.message || '学期状态加载失败，已禁止修改排课规则'
        return
      }
      this.termInfo = detail.data
      await this.loadRules()
    },
    async loadRules() {
      if (!this.termId || this.termError) return
      const current = this.ruleGate.begin()
      this.ruleLoading = true; this.ruleError = ''
      const response = await api.listRules({ termId: this.termId })
      if (!current()) return
      this.ruleLoading = false
      if (response.code === 0) this.rules = response.data.items || []
      else { this.rules = []; this.ruleError = response.message || '排课规则加载失败' }
    },
    openRuleEditor() {
      if (!this.canWriteRules) return
      this.editingRuleId = ''
      this.ruleForm = { ruleKey: '', scopeType: 'TERM', batchId: '', value: null, remark: '' }
      this.formError = ''; this.editorVisible = true
    },
    closeRuleEditor() {
      this.editorVisible = false; this.editingRuleId = ''; this.formError = ''
    },
    onRuleKeyChange() {
      const meta = this.selectedMeta
      this.ruleForm.value = meta ? this.cloneValue(meta.defaultValue) : null
      this.formError = ''
    },
    onScopeChange() {
      if (this.ruleForm.scopeType !== 'BATCH') this.ruleForm.batchId = ''
      this.formError = ''
    },
    editRule(row) {
      if (!this.canWriteRules || !this.catalogByKey[row.ruleKey]) return
      this.editingRuleId = row.ruleId
      this.ruleForm = {
        ruleKey: row.ruleKey,
        scopeType: row.batchId ? 'BATCH' : 'TERM',
        batchId: row.batchId || '',
        value: this.cloneValue(row.ruleValue ?? this.catalogByKey[row.ruleKey].defaultValue),
        remark: row.remark || ''
      }
      this.formError = ''; this.editorVisible = true
      this.$nextTick(() => document.querySelector('.aasg-editor')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
    },
    localRuleError() {
      const meta = this.selectedMeta
      if (!this.termId || !this.termInfo) return '学期状态尚未确认，不能保存规则'
      if (!meta) return '请选择业务参数'
      if (this.ruleForm.scopeType === 'BATCH' && !this.ruleForm.batchId) return '请选择课表批次'
      const value = this.ruleForm.value
      if (meta.control === 'WEEK_RANGE') {
        const start = Number(value?.startWeek); const end = Number(value?.endWeek)
        if (!Number.isInteger(start) || !Number.isInteger(end) || start < 1 || end < 1) return '起始周和结束周必须是正整数'
        if (start > end) return '起始周不能晚于结束周'
        if (this.termInfo?.teachingWeeks && end > Number(this.termInfo.teachingWeeks)) return `结束周不能超过该学期教学周数 ${this.termInfo.teachingWeeks}`
      }
      if (['WEEKDAY_MULTI', 'SLOT_MULTI'].includes(meta.control) && (!Array.isArray(value) || !value.length)) return `${meta.label}至少选择一项`
      if (meta.control === 'INTEGER') {
        const number = Number(value)
        if (!Number.isInteger(number) || number < meta.min || number > meta.max) return `${meta.label}必须在 ${meta.min}—${meta.max} 之间`
      }
      if (meta.control === 'BOOLEAN' && typeof value !== 'boolean') return `${meta.label}必须选择开启或关闭`
      return ''
    },
    async saveRule() {
      if (this.saving || !this.canWriteRules) return
      const error = this.localRuleError()
      if (error) { this.formError = error; return }
      this.saving = true; this.formError = ''
      const context = this.commandContextKey(), form = this.ruleForm
      const response = await api.saveRule({
        ruleKey: this.ruleForm.ruleKey,
        termId: this.termId,
        batchId: this.ruleForm.scopeType === 'BATCH' ? this.ruleForm.batchId : undefined,
        ruleValue: this.cloneValue(this.ruleForm.value),
        remark: this.ruleForm.remark || undefined
      })
      if (context !== this.commandContextKey() || form !== this.ruleForm) return
      this.saving = false
      if (response.code === 0) {
        toast.success(`${response.data.ruleLabel || '排课规则'}已保存`)
        this.closeRuleEditor(); await this.loadRules()
      } else this.formError = response.message || '保存排课规则失败'
    },
    confirmDeleteRule(row) {
      this.confirmRequireReason = false
      this.confirmTitle = `删除“${row.ruleLabel}”`
      this.confirmMessage = '删除后自动排课将恢复该参数的安全默认值。历史审计记录仍会保留。'
      this.pendingAction = async () => {
        const context = this.commandContextKey()
        const response = await api.deleteRule(row.ruleId)
        if (context !== this.commandContextKey()) return
        if (response.code === 0) { toast.success('规则已删除'); await this.loadRules() }
        else toast.error(response.message || '删除规则失败')
      }
      this.confirmVisible = true
    },
    isForbidden(weekday, slotNo) {
      return Array.isArray(this.ruleForm.value) && this.ruleForm.value.some(row => Number(row.weekday) === Number(weekday) && (row.slotNo == null ? slotNo == null : Number(row.slotNo) === Number(slotNo)))
    },
    toggleForbidden(weekday, slotNo) {
      const rows = Array.isArray(this.ruleForm.value) ? [...this.ruleForm.value] : []
      if (slotNo == null) {
        const active = this.isForbidden(weekday, null)
        this.ruleForm.value = active ? rows.filter(row => Number(row.weekday) !== Number(weekday)) : [...rows.filter(row => Number(row.weekday) !== Number(weekday)), { weekday }]
        return
      }
      const signature = row => Number(row.weekday) === Number(weekday) && Number(row.slotNo) === Number(slotNo)
      const active = rows.some(signature)
      this.ruleForm.value = active
        ? rows.filter(row => !signature(row))
        : [...rows.filter(row => !(Number(row.weekday) === Number(weekday) && row.slotNo == null)), { weekday, slotNo }]
    },
    scopeLabel(row) { return row.batchId ? '指定课表批次' : '本学期默认' },
    termStatusLabel(status) { return ({ DRAFT: '编制中', PUBLISHED: '已发布', FROZEN: '已冻结', ARCHIVED: '已归档' })[status] || '状态待确认' },
    availabilityStatusLabel(status) { return ({ PENDING: '待处理', ADOPTED: '已采纳', REJECTED: '已驳回' })[status] || '状态待确认' },
    slotLabel(slot) { return `${slot.slotName || `第${slot.slotNo}节`}${slot.startTime ? ` · ${slot.startTime}-${slot.endTime || ''}` : ''}` },
    formatValue(meta, value) {
      if (meta.control === 'WEEK_RANGE') return `第${value.startWeek}—${value.endWeek}周`
      if (meta.control === 'WEEKDAY_MULTI') return value.map(number => DEFAULT_DAYS.find(day => day.value === number)?.label || number).join('、')
      if (meta.control === 'SLOT_MULTI') return value.map(number => `第${number}节`).join('、')
      if (meta.control === 'FORBIDDEN_GRID') return value.length ? `${value.length}个禁排设置` : '不设统一禁排'
      if (meta.control === 'INTEGER') return `${value}${meta.unit || ''}`
      if (meta.control === 'BOOLEAN') return value ? '开启' : '关闭'
      return '—'
    },
    dimLabel(value) { return ({ TEACHER: '教师冲突', CLASS: '班级冲突', CLASSROOM: '教室冲突' })[value] || (value ? '待确认' : '—') },
    async loadAvails() {
      const context = this.commandContextKey()
      if (!this.termId) { this.avails = []; return }
      const response = await api.listAvailability({ termId: this.termId || undefined })
      if (context !== this.commandContextKey()) return
      this.avails = response.code === 0 ? (response.data.items || []) : []
      if (response.code !== 0) toast.error(response.message || '教师不可排时间加载失败')
    },
    async reviewAvail(id, action) {
      const context = this.commandContextKey()
      const response = await api.reviewAvailability(id, action)
      if (context !== this.commandContextKey()) return
      if (response.code === 0) { toast.success('已采纳'); await this.loadAvails() }
      else toast.error(response.message || '处理失败')
    },
    rejectAvail(id) {
      this.confirmRequireReason = true; this.confirmReasonLabel = '驳回原因（≥5字）'
      this.confirmTitle = '驳回教师不可排时间'; this.confirmMessage = '原因将写入处理记录并供申请教师查看。'
      this.pendingAction = async (reason) => {
        const context = this.commandContextKey()
        const response = await api.reviewAvailability(id, 'REJECT', String(reason || '').trim())
        if (context !== this.commandContextKey()) return
        if (response.code === 0) { toast.success('已驳回'); await this.loadAvails() }
        else toast.error(response.message || '驳回失败')
      }
      this.confirmVisible = true
    },
    async loadConflict() {
      if (!this.conflictBatchId) { toast.error('请选择课表批次'); return }
      const context = this.commandContextKey(), batchId = this.conflictBatchId
      this.conflict = null
      const response = await api.conflictReport(batchId)
      if (context !== this.commandContextKey()) return
      if (response.code === 0) this.conflict = response.data
      else toast.error(response.message || '冲突报告生成失败')
    },
    async runAuto(dryRun) {
      if (!this.autoBatchId) { toast.error('请选择课表批次'); return }
      const context = this.commandContextKey(), batchId = this.autoBatchId
      this.autoLoading = true
      const response = await api.autoSchedule(batchId, dryRun)
      if (context !== this.commandContextKey()) return
      this.autoLoading = false
      if (response.code === 0) { this.autoResult = response.data; toast.success(dryRun ? '试排完成（未落库）' : `已排入 ${response.data.placedSessions} 节`) }
      else toast.error(response.message || '自动排课失败')
    },
    doAuto() {
      if (!this.autoBatchId) { toast.error('请选择课表批次'); return }
      this.confirmRequireReason = false; this.confirmTitle = '执行自动排课'
      this.confirmMessage = '仅新增自动排课结果，手工和导入课位不会被覆盖。'
      this.pendingAction = () => this.runAuto(false); this.confirmVisible = true
    },
    doClearAuto() {
      if (!this.autoBatchId) { toast.error('请选择课表批次'); return }
      this.confirmRequireReason = false; this.confirmTitle = '清除自动排课结果'
      this.confirmMessage = '只清除该批次由系统自动生成的课位，手工和导入课位继续保留。'
      this.pendingAction = async () => {
        const context = this.commandContextKey()
        const response = await api.clearAuto(this.autoBatchId)
        if (context !== this.commandContextKey()) return
        if (response.code === 0) { toast.success(`已清除 ${response.data.cleared} 节`); this.autoResult = null }
        else toast.error(response.message || '清除失败')
      }
      this.confirmVisible = true
    },
    async onConfirm(payload = {}) {
      const action = this.pendingAction
      const valid = this.pendingContextKey === this.commandContextKey()
      this.pendingAction = null; this.confirmVisible = false; this.confirmRequireReason = false
      if (action && valid) await action(payload.reason || '')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aasg-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-color, #e5e7eb); margin-bottom: 16px; }
.aasg-tab { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; }
.aasg-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 600; }
.aasg-workbench-filter { display: flex; flex-wrap: wrap; align-items: end; gap: 12px; }
.aasg-flow { display: grid; grid-template-columns: repeat(7, minmax(95px, 1fr)); gap: 8px; margin-bottom: 16px; }
.aasg-flow-step { min-width: 0; padding: 10px 8px; border: 1px solid var(--border-200, #e5e7eb); border-radius: 8px; color: var(--text-secondary, #64748b); background: var(--fill-light, #f8fafc); text-align: center; }
.aasg-flow-step strong { display: block; margin-top: 5px; font-size: 12px; }
.aasg-flow-index { display: inline-flex; width: 22px; height: 22px; align-items: center; justify-content: center; border-radius: 50%; background: var(--border-200, #e5e7eb); font-size: 12px; }
.aasg-flow-step.is-completed { color: var(--success-color, #16a34a); border-color: #bbf7d0; background: #f0fdf4; }
.aasg-flow-step.is-current { color: var(--primary-color, #2563eb); border-color: #93c5fd; background: #eff6ff; box-shadow: 0 0 0 2px rgb(37 99 235 / 8%); }
.aasg-flow-step.is-current .aasg-flow-index { color: #fff; background: var(--primary-color, #2563eb); }
.aasg-flow-step.is-completed .aasg-flow-index { color: #fff; background: var(--success-color, #16a34a); }
.aasg-current-action { display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 14px; margin-bottom: 12px; border-radius: 8px; background: var(--fill-light, #f8fafc); }
.aasg-current-action > div { display: flex; flex-direction: column; gap: 3px; }
.aasg-current-action span, .aasg-current-action small { color: var(--text-secondary, #64748b); font-size: 12px; }
.aasg-metric-grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 10px; }
.aasg-metric { min-width: 0; padding: 13px; border: 1px solid var(--border-200, #e5e7eb); border-radius: 8px; background: var(--bg-white, #fff); }
.aasg-metric span, .aasg-metric small { display: block; color: var(--text-secondary, #64748b); font-size: 12px; }
.aasg-metric strong { display: block; margin: 5px 0 3px; color: var(--text-900, #1f2329); font-size: 22px; line-height: 1.1; }
.aasg-metric.is-alert { border-color: #fed7aa; background: #fff7ed; }
.aasg-metric.is-alert strong { color: #c2410c; }
.aasg-repair-center { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 18px 24px; align-items: center; padding: 18px; border: 1px solid #fdba74; border-radius: 10px; background: linear-gradient(135deg, #fff7ed 0%, #fff 72%); }
.aasg-repair-copy { min-width: 0; }
.aasg-repair-copy > strong { display: block; margin: 5px 0 7px; color: var(--text-900, #1f2329); font-size: 18px; }
.aasg-repair-copy p { max-width: 760px; margin: 0; color: var(--text-secondary, #64748b); font-size: 13px; line-height: 1.7; }
.aasg-repair-kicker { color: #c2410c; font-size: 12px; font-weight: 600; }
.aasg-repair-facts { display: grid; grid-template-columns: repeat(3, minmax(88px, 1fr)); gap: 8px; }
.aasg-repair-facts > div { min-width: 88px; padding: 10px 12px; border: 1px solid #fed7aa; border-radius: 8px; background: rgb(255 255 255 / 82%); text-align: center; }
.aasg-repair-facts span, .aasg-repair-facts small { display: block; color: var(--text-secondary, #64748b); font-size: 11px; }
.aasg-repair-facts strong { display: block; margin: 2px 0; color: var(--text-900, #1f2329); font-size: 20px; }
.aasg-repair-facts .is-gap strong { color: #c2410c; }
.aasg-repair-center > :last-child { grid-column: 1 / -1; justify-self: end; }
.aasg-queue-note { margin: 0 0 12px; }
.aasg-bar { display: flex; flex-wrap: wrap; gap: 10px; align-items: end; }
.aasg-grow { flex: 1; }.aasg-field { display: flex; flex-direction: column; gap: 6px; min-width: 220px; color: var(--text-700, #4e5969); font-size: 13px; }
.aasg-field.is-term { width: 280px; }.aasg-input { min-height: 36px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); }
.aasg-textarea { min-height: 78px; padding: 9px 10px; resize: vertical; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; font: inherit; }
.aasg-term-facts { display: flex; flex-wrap: wrap; gap: 14px; align-items: center; margin-top: 12px; color: var(--text-600, #475569); font-size: 13px; }
.aasg-editor { display: flex; flex-direction: column; gap: 15px; }.aasg-meta { display: flex; flex-direction: column; gap: 4px; padding: 12px 14px; border-radius: 8px; background: var(--fill-light, #f8fafc); }
.aasg-meta span { color: var(--text-secondary, #64748b); font-size: 13px; }.aasg-control-grid { display: grid; gap: 12px; }.aasg-control-grid.is-two { grid-template-columns: repeat(2, minmax(0, 220px)); }
.aasg-choice-panel, .aasg-forbidden { padding: 13px 14px; border: 1px solid var(--border-200, #e5e7eb); border-radius: 8px; }.aasg-choice-title { margin-bottom: 10px; font-weight: 600; }
.aasg-check, .aasg-radio { display: inline-flex; align-items: center; gap: 5px; margin: 3px 14px 3px 0; font-size: 13px; }.aasg-forbidden-row { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; padding: 8px 0; border-top: 1px solid var(--border-100, #f1f5f9); }
.aasg-forbidden-row:first-of-type { border-top: 0; }.aasg-forbidden-row strong { width: 48px; }.aasg-check.is-whole-day { padding-right: 10px; border-right: 1px solid var(--border-200, #e5e7eb); }
.aasg-number-wrap { display: flex; align-items: center; gap: 8px; }.aasg-number-wrap .aasg-input { width: 140px; }.aasg-number-wrap em { font-style: normal; color: var(--text-secondary, #64748b); }
.aasg-editor-actions { display: flex; justify-content: flex-end; gap: 8px; }.aasg-default-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.aasg-default-grid > div { padding: 12px; border: 1px solid var(--border-200, #e5e7eb); border-radius: 7px; }.aasg-default-grid strong, .aasg-default-grid span { display: block; }.aasg-default-grid span { margin-top: 5px; color: var(--text-secondary, #64748b); font-size: 12px; }
.is-danger-text { color: var(--danger-color, #dc2626); }.aasg-summary { display: flex; flex-wrap: wrap; gap: 16px; padding: 10px 12px; background: var(--fill-light, #f8fafc); border-radius: 8px; margin-bottom: 12px; font-size: 13px; }
.aasg-summary .is-bad { color: var(--danger-color, #dc2626); font-weight: 600; }.aasg-summary .is-warn { color: var(--warning-color, #d97706); font-weight: 600; }.aasg-summary .is-ok { color: var(--success-color, #16a34a); font-weight: 600; }
.aasg-section-title { font-weight: 500; margin: 12px 0 8px; }.aasg-conflicts { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }.aasg-conflicts li { padding: 8px 12px; background: var(--fill-light, #f8fafc); border-radius: 6px; font-size: 13px; }
.aasg-tag { display: inline-block; padding: 1px 8px; border-radius: 4px; margin-right: 8px; font-size: 12px; }.aasg-tag.is-hard { background: #fee2e2; color: #dc2626; }.aasg-tag.is-soft { background: #fef3c7; color: #d97706; }
.aasg-reasons { display: flex; flex-wrap: wrap; gap: 8px; }.aasg-reason-chip { padding: 3px 10px; border-radius: 12px; background: #fef3c7; color: #b45309; font-size: 12px; }.aasg-advice, .aasg-sub { color: var(--text-secondary, #64748b); font-size: 12px; }
@media (max-width: 1100px) { .aasg-flow { grid-template-columns: repeat(4, minmax(110px, 1fr)); }.aasg-metric-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 900px) { .aasg-default-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.aasg-control-grid.is-two { grid-template-columns: 1fr; }.aasg-repair-center { grid-template-columns: 1fr; }.aasg-repair-center > :last-child { grid-column: auto; } }
@media (max-width: 620px) { .aasg-default-grid { grid-template-columns: 1fr; }.aasg-field, .aasg-field.is-term { width: 100%; min-width: 0; }.aasg-flow { grid-template-columns: repeat(2, minmax(0, 1fr)); }.aasg-metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.aasg-current-action { align-items: stretch; flex-direction: column; }.aasg-repair-facts { grid-template-columns: 1fr; }.aasg-repair-center > :last-child { width: 100%; justify-content: center; } }
</style>
