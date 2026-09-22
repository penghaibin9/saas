<template>
  <ModulePageShell
    :title="pageTitle"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/grade-overview')">成绩总览</AppButton>
      <AppButton @click="closeTask">{{ isAdminRole ? '成绩任务' : '我的录入任务' }}</AppButton>
      <AppButton v-if="task && canSubmit" variant="primary" :disabled="writeBusy" @click="openSubmit">提交学院审核</AppButton>
    </template>

    <div class="mp-stack">
      <section v-if="dynamicCommand || dynamicRecoveryError" class="aa-action-receipt" role="status">
        <div><strong>原操作结果待核实</strong><span>{{ dynamicRecoveryError || '已保留原命令引用，请先只读核对；不会自动重发。' }}</span></div>
        <AppButton :disabled="!dynamicCommand || dynamicVerifying" @click="verifyDynamicCommand">核对原命令</AppButton>
      </section>
      <section v-if="submitReceipt && (!task || String(submitReceipt.taskId) === String(task.gradeTaskId))" class="aa-action-receipt" role="status">
        <div><strong>{{ submitReceipt.verified ? '已回读正式任务' : '结果待核实' }}</strong><span>{{ submitReceipt.courseName }} · 任务 {{ submitReceipt.taskId }}</span></div>
        <div><small>当前状态</small><b>{{ statusLabel(submitReceipt.status) }}</b></div>
        <div><small>下一责任</small><b>{{ submitReceipt.verified ? (['SUBMITTED', 'COLLEGE_REVIEW'].includes(submitReceipt.status) ? '学院成绩审核人' : submitReceipt.status === 'ACADEMIC_REVIEW' ? '教务成绩发布岗' : '查看正式成绩') : '请先核对正式状态' }}</b></div>
        <AppButton v-if="submitReceipt.verified" size="small" variant="ghost" @click="closeTask">继续下一门</AppButton><AppButton v-else :disabled="submitting" @click="verifySubmit">核对正式状态</AppButton>
      </section>
      <ErrorState v-if="taskError" :description="taskError" @retry="retryTask" />
      <LoadingState v-if="taskLoading" />
      <AppSectionCard v-if="!task" :title="importMode ? '选择成绩导入任务' : isAdminRole ? '成绩任务责任队列' : '我的录入任务'">
        <div class="aa-my-tasks">
          <ul>
            <li v-for="t in myTasks" :key="t.gradeTaskId" class="aa-my-task-item">
              <span>
                {{ t.courseName }}<small v-if="t.courseId"> · 课程ID {{ t.courseId }}</small>
                <small v-if="t.deadline"> · 截止 {{ formatDeadline(t.deadline) }}<strong v-if="t.isOverdue" class="aa-overdue-text"> · 已逾期</strong></small>
              </span>
              <AppStatusTag :type="statusColor(t.status)" dot>{{ statusLabel(t.status) }}</AppStatusTag>
              <AppButton size="small" variant="ghost" :disabled="writeBusy" @click="openTask(t)">进入</AppButton>
              <AppButton v-if="canRemind(t)" size="small" variant="ghost" class="aa-remind-link" @click.stop="openReminder(t)">催录</AppButton>
            </li>
          </ul>
        </div>
        <EmptyState v-if="!taskLoading && !myTasks.length" :title="importMode ? '当前没有可导入任务' : '当前没有成绩任务'" :description="importMode ? '先建立正式成绩任务，再按任务导入并预校验' : '选择正式教学任务后创建录入任务'" />
        <div class="aa-actions"><AppButton :disabled="taskPage <= 1" @click="changeTaskPage(taskPage - 1)">上一页</AppButton><span>第 {{ taskPage }} 页 · 共 {{ taskTotal }} 项</span><AppButton :disabled="taskPage * 20 >= taskTotal" @click="changeTaskPage(taskPage + 1)">下一页</AppButton><AppButton @click="showCreate = !showCreate">{{ showCreate ? '收起新建' : '新建录入任务' }}</AppButton></div>
      </AppSectionCard>
      <AppSectionCard v-if="!task && showCreate" title="新建成绩录入任务">
        <AppInlineAlert
          v-if="isAdminRole && !form.teachingTaskId"
          type="warning"
          title="管理员特殊补录"
          description="必须选择正式学期、课程库具体版本和明确行政班并填写原因；课程名、学分和课程版本均由课程库带出。"
        />
        <div class="aa-grid2">
          <label class="aa-field">
            <span :class="{ req: !isAdminRole }">教学任务</span>
            <AppTeachingTaskPicker
              v-model="form.teachingTaskId"
              :query="{ mine: !isAdminRole }"
              clearable
              @change="onTeachingTaskChange"
              placeholder="普通教师仅选择本人正式教学任务；管理员可留空做特殊补录"
            />
          </label>
          <label v-if="isAdminRole && !form.teachingTaskId" class="aa-field">
            <span class="req">课程具体版本</span>
            <AppCoursePicker v-model="form.courseId" @change="onCourseChange" placeholder="按课程代码/名称选择" />
          </label>
          <label class="aa-field"><span>课程</span><input :value="form.courseName" type="text" class="aa-input" disabled placeholder="由教学任务或课程版本带出" /></label>
          <label v-if="isAdminRole && !form.teachingTaskId" class="aa-field">
            <span class="req">正式学期</span>
            <AppTermEntityPicker v-model="form.termId" placeholder="选择正式学期" />
          </label>
          <label v-else class="aa-field"><span>学期</span><input :value="form.termCode" type="text" class="aa-input" disabled placeholder="由教学任务所属批次带出" /></label>
          <label class="aa-field"><span>学分</span><input v-model.number="form.credit" type="number" min="0" step="0.5" class="aa-input" disabled /></label>
          <label class="aa-field"><span :class="{ req: isAdminRole && !form.teachingTaskId }">班级</span><AppClassPicker v-model="form.classId" placeholder="由教学任务带出；特殊补录必选" :disabled="!!form.teachingTaskId" /></label>
          <label class="aa-field"><span>平时占比%</span><input v-model.number="form.usualRatio" type="number" min="0" max="100" class="aa-input" /></label>
          <label class="aa-field"><span>期中占比%</span><input v-model.number="form.midtermRatio" type="number" min="0" max="100" class="aa-input" placeholder="0=不启用期中" /></label>
          <label class="aa-field"><span>期末占比%</span><input v-model.number="form.finalRatio" type="number" min="0" max="100" class="aa-input" /></label>
          <label class="aa-field"><span>及格线</span><input v-model.number="form.passLine" type="number" min="0" max="100" class="aa-input" /></label>
          <label v-if="isAdminRole && !form.teachingTaskId" class="aa-field"><span class="req">补录原因</span><input v-model="form.adminSupplementReason" type="text" class="aa-input" placeholder="不少于5字" /></label>
        </div>
        <p class="mp-note">创建后可继续使用固定三段录入，也可在任务内切换为1—12项动态成绩方案；动态方案首次录分后锁定。</p>
        <div class="aa-actions"><AppButton variant="primary" :loading="creating" @click="createTask">创建任务</AppButton></div>

      </AppSectionCard>

      <template v-if="task">
        <section class="aa-task-context" aria-label="当前成绩任务">
          <div class="aa-task-context__identity">
            <div>
              <span class="aa-task-context__eyebrow">当前正式成绩任务</span>
              <h2>{{ task.courseName }}<span v-if="task.teachingClassName"> · {{ task.teachingClassName }}</span></h2>
              <p>{{ task.termCode || '学期待核对' }} · 任务 {{ task.gradeTaskId }} · 课程 {{ task.courseId || '待治理' }}</p>
              <p class="aa-task-source">来源：{{ task.teachingTaskId ? `正式教学任务 ${task.teachingTaskId}` : '历史任务或管理员特殊补录' }}</p>
            </div>
            <AppStatusTag :type="statusColor(task.status)" dot>{{ statusLabel(task.status) }}</AppStatusTag>
          </div>
          <div class="aa-task-context__responsibility">
            <div><small>当前责任</small><strong>{{ currentResponsibility }}</strong></div>
            <div><small>下一责任</small><strong>{{ nextResponsibility }}</strong></div>
          </div>
        </section>

        <ol class="aa-grade-steps" aria-label="成绩业务阶段">
          <li v-for="(step, index) in gradeSteps" :key="step" :class="{ 'is-done': index < taskStage, 'is-current': index === taskStage }">
            <span>{{ index < taskStage ? '✓' : index + 1 }}</span>
            <div><strong>{{ step }}</strong><small>{{ index === taskStage ? '当前环节' : index < taskStage ? '正式事实已形成' : '等待前序完成' }}</small></div>
          </li>
        </ol>

        <section class="aa-grade-metrics" aria-label="成绩任务关键事实">
          <article><small>正式名单</small><strong>{{ rosterMetric }}</strong><span>{{ dynamicMode ? '冻结名单版本人数' : `当前录入表 ${rows.length} 人，含待保存行` }}</span></article>
          <article><small>成绩项</small><strong>{{ gradeItemMetric }}</strong><span>{{ dynamicMode ? '动态方案正式分项' : '固定成绩分项' }}</span></article>
          <article><small>录入模式</small><strong>{{ formalSchemeMode === 'unknown' ? '待核对' : dynamicMode ? '动态分项' : hasMidterm ? '固定三段' : '固定两段' }}</strong><span>{{ formalSchemeMode === 'dynamic' ? '正式方案已锁定为动态' : '按当前任务方案办理' }}</span></article>
          <article><small>质量核验</small><strong>{{ qualityMetric }}</strong><span>提交前读取服务器完整性</span></article>
        </section>

        <AppInlineAlert type="info" title="正式名单与提交快照必须一致" description="空分不会自动变成 0；异常标记、名单版本和成绩方案由服务器复核。保存只代表当前行写入，提交学院后仍以正式任务回读为准。" />

        <AppSectionCard :title="`录入任务：${task.courseName}`">
          <template #header-extra><AppButton size="small" variant="ghost" @click="closeTask">返回</AppButton></template>
          <div class="aa-task-head">
            <span>课程ID {{ task.courseId || '待治理' }} · 及格线 {{ task.passLine }}</span>
            <span v-if="task.deadlineReady">截止 {{ formatDeadline(task.deadline) }}</span>
            <span v-else>未设置提交截止时间</span>
            <AppStatusTag :type="statusColor(task.status)" dot>{{ statusLabel(task.status) }}</AppStatusTag>
          </div>
          <div class="aa-mode-switch">
            <button :disabled="formalSchemeMode === 'dynamic'" :class="['aa-mode', { 'is-active': !dynamicMode }]" @click="switchMode(false)">固定三段</button>
            <button :class="['aa-mode', { 'is-active': dynamicMode }]" @click="switchMode(true)">动态成绩项</button>
          </div>
          <AppInlineAlert v-if="!task.courseId" type="warning" title="课程身份欠账" description="该历史任务尚未绑定课程库具体版本，不能发布正式成绩。" />
          <AppInlineAlert v-if="task.status === 'RETURNED' && task.returnReason" type="warning" :message="`已被退回：${task.returnReason}，请核对后重新提交`" />
          <AppInlineAlert
            v-if="task.isOverdue === true"
            type="warning"
            title="已超过成绩提交截止时间"
            description="可以继续完善成绩，但提交审核已锁定；请联系学院或教务管理员延长截止时间后再提交。"
          />
        </AppSectionCard>

        <details v-if="canExtendDeadline" class="aa-task-settings">
          <summary>成绩提交截止时间 <span>{{ task.deadlineReady ? formatDeadline(task.deadline) : '尚未设置，可在此设置' }}</span></summary>
        <AppSectionCard title="成绩提交截止时间">
          <div class="aa-grid2">
            <label class="aa-field">
              <span class="req">新截止时间</span>
              <input v-model="deadlineForm.deadlineLocal" type="datetime-local" class="aa-input" />
            </label>
            <label class="aa-field">
              <span class="req">设置 / 延期原因</span>
              <input v-model.trim="deadlineForm.reason" type="text" class="aa-input" maxlength="500" placeholder="不少于5字；延期只能向后调整" />
            </label>
          </div>
          <div class="aa-actions">
            <AppButton variant="primary" :loading="deadlineSaving" @click="saveDeadline">{{ task.deadlineReady ? '延长截止时间' : '设置截止时间' }}</AppButton>
            <span class="mp-note">截止时间以成绩录入任务中的持久化记录为准，不使用学期结束时间替代。逾期提交由应用预检与数据库原子门禁双重阻断。</span>
          </div>
        </AppSectionCard>
        </details>

        <template v-if="!dynamicMode">
          <AppSectionCard v-if="fixedEditable" :title="isAcademicTeacher ? '正式教学名单' : '添加学生'">
            <div class="aa-reg-search">
              <AppStudentPicker v-if="!isAcademicTeacher" v-model="candidateStudentId" class="aa-input--grow" placeholder="按姓名/学号检索并添加学生" @change="onStudentPicked" />
              <span v-else class="mp-note">任课教师只按正式教学班名单录入；不能手工添加名单外学生。</span>
              <AppButton :loading="loadingRoster" @click="loadRoster">{{ isAcademicTeacher ? '重新读取正式名单' : '按正式名单圈定' }}</AppButton>
              <AppButton @click="openImport">导入成绩（Excel）</AppButton>
            </div>
          </AppSectionCard>

          <AaAuthoritativeImportDrawer
            v-if="task && importActions"
            :key="taskSeq"
            v-model:visible="importVisible"
            title="成绩权威 XLSX 导入"
            template-name="成绩导入模板.xlsx"
            :preview-fields="['studentNo', 'studentName', 'usualScore', 'midtermScore', 'finalScore', 'exceptionFlag']"
            :download-template-fn="importActions.template"
            :upload-fn="importActions.upload"
            @imported="importActions.complete"
          />

          <AppSectionCard title="固定三段成绩录入表">
            <p class="mp-note">空分不会在页面上转成 0；缺考、缓考等使用异常标记。</p>
            <p class="mp-note">平时 {{ task.usualRatio }}%<template v-if="hasMidterm"> · 期中 {{ task.midtermRatio }}%</template> · 期末 {{ task.finalRatio }}%</p>
            <EmptyState v-if="!rows.length" title="录入表为空" description="从上方检索学生加入，或按正式教学班名单圈定" />
            <div class="aa-table-scroll" role="region" aria-label="数据表格，可横向滚动" tabindex="0" v-else>
<table  class="aa-course-table">
              <thead><tr><th>学生</th><th>学号</th><th>平时 {{ task.usualRatio }}%</th><th v-if="hasMidterm">期中 {{ task.midtermRatio }}%</th><th>期末 {{ task.finalRatio }}%</th><th>已存总评</th><th>异常标记</th><th>结果 / 保存</th></tr></thead>
              <tbody>
                <tr v-for="r in rows" :key="r.studentId">
                  <td><strong>{{ r.realName }}</strong></td>
                  <td>{{ r.studentNo || '学号未提供' }}</td>
                  <td><input v-model.number="r.usual" type="number" min="0" max="100" class="aa-input aa-input--xs" :disabled="writeBusy || !fixedEditable || r.exceptionFlag !== 'NORMAL'" /></td>
                  <td v-if="hasMidterm"><input v-model.number="r.midterm" type="number" min="0" max="100" class="aa-input aa-input--xs" :disabled="writeBusy || !fixedEditable || r.exceptionFlag !== 'NORMAL'" /></td>
                  <td><input v-model.number="r.final" type="number" min="0" max="100" class="aa-input aa-input--xs" :disabled="writeBusy || !fixedEditable || r.exceptionFlag !== 'NORMAL'" /></td>
                  <td class="aa-total-score">{{ r.total ?? '—' }}</td>
                  <td><AppSelect v-model="r.exceptionFlag" :options="exceptionOptions" :disabled="writeBusy || !fixedEditable" placeholder="" size="compact" /></td>
                  <td><AppStatusTag v-if="r.passStatus" :type="resultColor(r.passStatus)">{{ resultLabel(r.passStatus) }}</AppStatusTag> <button v-if="fixedEditable" class="mp-link" :disabled="writeBusy" @click="saveRow(r)">保存</button></td>
                </tr>
              </tbody>
            </table>
</div>
          </AppSectionCard>
        </template>

        <template v-else>
          <AppSectionCard title="动态成绩项方案">
            <AppInlineAlert
              type="info"
              title="兼容现有成绩主账"
              description="分项成绩单独留痕，系统按权重生成总评后仍进入原学院审核、教务发布、预警和成绩单流程。首次录分后方案自动锁定。"
            />
            <LoadingState v-if="dynamicLoading" />
            <template v-else-if="dynamicData">
              <div class="aa-scheme-head">
                <span>名单版本：{{ dynamicData.rosterIdentity?.rosterVersionNo || '—' }} · {{ dynamicData.rosterIdentity?.memberCount ?? '—' }}人</span>
                <span>权重合计 {{ schemeTotal }}%</span>
              </div>
              <div class="aa-scheme-list">
                <div v-for="(component, index) in schemeDraft" :key="component.code + index" class="aa-scheme-row">
                  <input v-model.trim="component.code" class="aa-input aa-code" maxlength="40" :disabled="writeBusy || !schemeEditable" placeholder="代码" />
                  <input v-model.trim="component.name" class="aa-input aa-name" maxlength="80" :disabled="writeBusy || !schemeEditable" placeholder="名称" />
                  <input v-model.number="component.weight" type="number" min="0.01" max="100" step="0.01" class="aa-input aa-weight" :disabled="writeBusy || !schemeEditable" />
                  <label class="aa-required"><input v-model="component.required" type="checkbox" :disabled="writeBusy || !schemeEditable" /> 必填</label>
                  <button v-if="schemeEditable && schemeDraft.length > 1" class="mp-link is-danger" @click="removeComponent(index)">删除</button>
                </div>
              </div>
              <div v-if="schemeEditable" class="aa-actions">
                <AppButton :disabled="schemeDraft.length >= 12" @click="addComponent">新增成绩项</AppButton>
                <AppButton variant="primary" :loading="schemeSaving" @click="saveScheme">保存方案</AppButton>
              </div>
              <p v-else class="mp-note">方案状态：{{ schemeStatusLabel(dynamicData.scheme?.status) }}。已开始录分或任务状态已变化，当前只读。</p>
            </template>
          </AppSectionCard>

          <AppSectionCard title="动态分项录入表">
            <div class="aa-actions">
              <AppButton :disabled="!dynamicWritable || writeBusy || dynamicLoading" @click="saveDynamicRows()">整批保存当前页</AppButton>
              <span>第 {{ dynamicPage }} 页 · 共 {{ dynamicData?.total ?? '—' }} 人</span>
              <AppButton :disabled="dynamicPage <= 1 || writeBusy || dynamicLoading || !!dynamicCommand || dynamicDirty" @click="changeDynamicPage(dynamicPage - 1)">上一页</AppButton>
              <AppButton :disabled="!dynamicData?.hasMore || writeBusy || dynamicLoading || !!dynamicCommand || dynamicDirty" @click="changeDynamicPage(dynamicPage + 1)">下一页</AppButton>
              <span v-if="dynamicDirty">本页有未保存分项，请先保存再翻页。</span>
            </div>
            <p v-if="dynamicQuality" class="mp-note">{{ dynamicQuality.summary }} · 未录 {{ dynamicQuality.missingCount }} 人 · 分项待核 {{ dynamicQuality.incompleteCount }} 人 · 不及格 {{ dynamicQuality.failCount }} 人</p>
            <ErrorState v-if="dynamicError" :description="dynamicError" @retry="loadDynamic" />
            <LoadingState v-else-if="dynamicLoading" />
            <EmptyState v-else-if="!dynamicRows.length" title="正式名单为空" description="请先完成教学班和名单版本治理" />
            <div v-else class="aa-table-scroll">
              <table class="aa-course-table aa-dynamic-table">
                <thead>
                  <tr>
                    <th>学生</th><th>异常标记</th>
                    <th v-for="component in dynamicComponents" :key="component.code">{{ component.name }}<small>{{ component.weight }}%</small></th>
                    <th>总评</th><th>结果</th><th></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in dynamicRows" :key="row.studentId">
                    <td><strong>{{ row.realName }}</strong><small>{{ row.studentNo }}</small></td>
                    <td><AppSelect v-model="row.exceptionFlag" :options="exceptionOptions" :disabled="writeBusy || !dynamicWritable" placeholder="" size="compact" /><small v-if="row.draftConflict">正式状态：{{ exceptionOptions.find(option => option.value === row.formalExceptionFlag)?.label || '待核对' }}</small></td>
                    <td v-for="component in dynamicComponents" :key="component.code">
                      <input v-model.number="row.scores[component.code]" type="number" min="0" max="100" step="0.01" class="aa-input aa-input--xs" :disabled="writeBusy || !dynamicWritable || row.exceptionFlag !== 'NORMAL'" />
                      <small v-if="row.formalScores && row.scores[component.code] !== row.formalScores[component.code]">正式值：{{ row.formalScores[component.code] ?? '未录' }}</small>
                    </td>
                    <td>{{ row.totalScore ?? '—' }}</td>
                    <td><AppStatusTag v-if="row.passStatus" :type="resultColor(row.passStatus)">{{ resultLabel(row.passStatus) }}</AppStatusTag></td>
                    <td>
                      <button v-if="row.draftConflict" class="mp-link" :disabled="writeBusy || !!dynamicCommand" @click="confirmDynamicDraft(row)">已核对正式值，保留我的草稿</button>
                      <button v-else-if="dynamicWritable" class="mp-link" :disabled="writeBusy" @click="saveDynamicRow(row)">{{ dynamicSavingId === row.studentId ? '保存中' : '保存' }}</button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </AppSectionCard>
        </template>

        <AppSectionCard v-if="canSubmit" title="提交审核">
          <div class="aa-actions">
            <AppButton variant="primary" :loading="submitting" @click="openSubmit">提交进入学院审核</AppButton>
            <span class="mp-note">提交时冻结正式名单版本；名单换版后必须退回重建，禁止静默替换。</span>
          </div>
        </AppSectionCard>
      </template>
    </div>

    <AppConfirmDialog v-model:visible="submitDialog" title="提交进入学院审核" confirm-text="确认提交学院" :submitting="submitting" @confirm="submit">
      <p>{{ submitCommand?.courseName }} · 任务 {{ submitCommand?.taskId }}</p><p>提交时由服务器重新校验并冻结正式名单；确认对象已固定。</p>
    </AppConfirmDialog>
    <AppConfirmDialog
      v-model:visible="reminderVisible"
      title="催录成绩"
      :message="reminderTask ? `将刷新《${reminderTask.courseName || '课程'}》当前正式任课教师的待录待办，并写入消息中心提醒。` : ''"
      type="warning"
      confirm-text="确认催录"
      require-reason
      reason-label="催录说明"
      reason-placeholder="例如：请于本周内完成成绩录入并提交学院审核"
      :reason-min-length="2"
      :loading="reminding"
      @confirm="confirmReminder"
    >
      <p class="mp-note">催录将提醒当前正式任课教师办理待录成绩。具体送达情况请在消息中心查看。</p>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import {
  AppSectionCard, AppStatusTag, AppInlineAlert, AppSelect, AppConfirmDialog,
  AppClassPicker, AppStudentPicker, AppTeachingTaskPicker,
  AppCoursePicker, AppTermEntityPicker
} from '@/components/common'
import AaAuthoritativeImportDrawer from '@/modules/academicAffairs/components/AaAuthoritativeImportDrawer.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { academicFileExchangeApi } from '@/modules/academicAffairs/api/academic-file-exchange.api'
import { gradeIdentityApi } from '@/modules/academicAffairs/api/grade-identity.api'
import { academicAffairsR10Api } from '@/modules/academicAffairs/api/academic-affairs-r10.api'
import { gradeReminderApi } from '@/modules/academicAffairs/api/grade-reminder.api'
import { toast } from '@/utils/toast'
import { currentUserFromToken } from '@/services/http/client'
import { gradeError } from './parallel-c/grade-review.js'
import { gradeCommandIdentityRef, findGradeCommandReference, createGradeCommandReference, removeGradeCommandReference } from './parallel-c/grade-command-recovery.js'

const TASK_STATUS = {
  NOT_STARTED: '未开始', INPUTTING: '录入中', SUBMITTED: '已提交',
  COLLEGE_REVIEW: '学院审核中', ACADEMIC_REVIEW: '教务终审中', PUBLISHED: '已发布',
  RETURNED: '已退回', ARCHIVED: '已归档'
}
const EDITABLE_STATUS = new Set(['NOT_STARTED', 'INPUTTING', 'RETURNED'])
const ADMIN_ROLES = new Set(['SCHOOL_ADMIN', 'ACADEMIC_ADMIN', 'JWC_ADMIN', 'PLATFORM_SUPER_ADMIN', 'COLLEGE_ADMIN'])
const SUBMITTABLE_STATUS = new Set(['INPUTTING', 'RETURNED'])

function asUtcDate(value) {
  const text = String(value || '').trim()
  if (!text) return null
  const normalized = /(?:Z|[+-]\d\d:\d\d)$/.test(text) ? text : `${text}Z`
  const parsed = new Date(normalized)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

export default {
  name: 'AaGradeEntryView',
  components: {
    ModulePageShell, EmptyState, LoadingState, ErrorState, AppButton, AppSectionCard,
    AppStatusTag, AppInlineAlert, AppSelect, AppConfirmDialog, AaAuthoritativeImportDrawer, AppClassPicker,
    AppStudentPicker, AppTeachingTaskPicker, AppCoursePicker, AppTermEntityPicker
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      academicFileExchangeApi, academicAffairsApi,
      form: {
        teachingTaskId: '', courseId: '', courseName: '', termId: '', termCode: '',
        credit: null, classId: '', usualRatio: 30, midtermRatio: 0, finalRatio: 70,
        passLine: 60, adminSupplementReason: ''
      },
      creating: false, task: null, myTasks: [], showCreate: false, taskLoading: false, taskError: '',
      taskSeq: 0, listSeq: 0, recordsSeq: 0, dynamicSeq: 0, alive: true, savingRowId: '',
      taskPage: 1, taskTotal: 0, rosterInfo: null, submitDialog: false, submitCommand: null, submitPending: false,
      candidateStudentId: '', loadingRoster: false, rows: [], submitting: false,
      submitReceipt: null,
      importVisible: false, importActions: null,
      reminderVisible: false, reminderTask: null, reminding: false,
      deadlineForm: { deadlineLocal: '', reason: '' }, deadlineSaving: false,
      formalSchemeMode: 'unknown', dynamicMode: false, dynamicLoading: false, dynamicError: '', dynamicData: null,
      schemePending: false, pendingSchemeComponents: null, schemeDraft: [], schemeSaving: false, dynamicSavingId: '',
      dynamicCommand: null, dynamicRecoveryError: '', dynamicVerifying: false, dynamicPage: 1, dynamicQuality: null
    }
  },
  computed: {
    importMode() { return this.$route?.query?.action === 'import' },
    pageTitle() { return this.importMode ? '成绩导入' : '成绩录入' },
    pageSubtitle() { return this.importMode ? '与正式名单和成绩方案匹配后才能确认' : '按正式教学名单连续录分，支持固定和动态成绩项' },
    identityKey() { const u = currentUserFromToken() || {}; return JSON.stringify([u.tenantId, u.userId, u.currentRoleCode, u.activeContextId, this.ctx.currentRole, this.ctx.dataScope]) },
    writeBusy() { return this.creating || this.submitting || this.schemePending || this.schemeSaving || !!this.dynamicSavingId || !!this.savingRowId || this.deadlineSaving || this.reminding },
    editable() { return !!this.task && EDITABLE_STATUS.has(this.task.status) && this.task.allowedActions?.includes('INPUT') && !this.submitPending && !this.schemePending && !this.dynamicCommand && !this.dynamicRecoveryError },
    dynamicWritable() { return this.editable && !this.dynamicLoading && !this.dynamicError && !this.dynamicRows.some(row => row.draftConflict) && this.dynamicData?.canWriteComponents === true && String(this.dynamicData.gradeTaskId) === String(this.task.gradeTaskId) },
    fixedEditable() { return this.editable && this.formalSchemeMode === 'fixed' },
    hasMidterm() { return this.task && Number(this.task.midtermRatio) > 0 },
    gradeSteps() { return ['正式教学任务', '建立成绩任务', '录入提交', '学院审核', '教务发布'] },
    taskStage() {
      const status = String(this.task?.status || '').toUpperCase()
      if (['SUBMITTED', 'COLLEGE_REVIEW'].includes(status)) return 3
      if (status === 'ACADEMIC_REVIEW') return 4
      if (['PUBLISHED', 'ARCHIVED'].includes(status)) return 5
      return 2
    },
    currentResponsibility() {
      const status = String(this.task?.status || '').toUpperCase()
      if (['SUBMITTED', 'COLLEGE_REVIEW'].includes(status)) return '学院成绩审核岗'
      if (status === 'ACADEMIC_REVIEW') return '教务成绩发布岗'
      if (['PUBLISHED', 'ARCHIVED'].includes(status)) return '成绩事实只读'
      return '任课教师 / 有权限的成绩管理岗'
    },
    nextResponsibility() {
      const status = String(this.task?.status || '').toUpperCase()
      if (['PUBLISHED', 'ARCHIVED'].includes(status)) return '预警扫描 / 更正留痕'
      if (status === 'ACADEMIC_REVIEW') return '正式发布与后置扫描'
      if (['SUBMITTED', 'COLLEGE_REVIEW'].includes(status)) return '教务成绩发布岗'
      return '学院成绩审核岗'
    },
    rosterMetric() {
      const dynamicCount = this.dynamicData?.rosterIdentity?.memberCount
      if (this.dynamicMode) return Number.isInteger(dynamicCount) && dynamicCount >= 0 ? `${dynamicCount} 人` : '待核对'
      if (this.rosterInfo?.ready === true && Number.isInteger(this.rosterInfo.memberCount)) return `${this.rosterInfo.memberCount} 人`
      return '待核对'
    },
    gradeItemMetric() { return `${this.dynamicMode ? this.dynamicComponents.length : (this.hasMidterm ? 3 : 2)} 项` },
    qualityMetric() {
      if (this.dynamicMode && this.dynamicQuality) return this.dynamicQuality.canSubmit === true ? '可提交' : '待完善'
      if (!this.dynamicMode) return this.rows.length ? '逐行核对' : '名单待载入'
      return '读取中'
    },
    isAcademicTeacher() {
      return String(this.ctx?.currentRole?.roleCode || this.ctx?.currentRoleCode || '').toUpperCase() === 'ACADEMIC_TEACHER'
    },
    isAdminRole() {
      const code = (this.ctx?.currentRole?.roleCode || this.ctx?.currentRoleCode || '').toUpperCase()
      return ADMIN_ROLES.has(code) || this.ctx?.userType === 'PLATFORM_SUPER_ADMIN'
    },
    canExtendDeadline() {
      return this.isAdminRole && Array.isArray(this.task?.allowedActions) && this.task.allowedActions.includes('EXTEND_DEADLINE')
    },
    canSubmit() {
      if (!this.task || this.isAdminRole || !SUBMITTABLE_STATUS.has(this.task.status)) return false
      if (this.task.isOverdue === true || this.task.teacherAuthorityReady === false) return false
      const actions = Array.isArray(this.task.allowedActions) ? this.task.allowedActions : []
      return actions.includes('SUBMIT') && !this.submitPending && !this.dynamicCommand && !this.dynamicRecoveryError && !(this.dynamicMode && this.dynamicRows.some(row => row.draftConflict))
    },
    exceptionOptions() {
      return [
        { value: 'NORMAL', label: '正常' }, { value: 'ABSENT', label: '缺考' },
        { value: 'DEFERRED', label: '缓考' }, { value: 'EXEMPT', label: '免修' },
        { value: 'CHEAT', label: '作弊' }
      ]
    },
    dynamicRows() { return this.dynamicData?.items || [] },
    dynamicDirty() { return this.dynamicRows.some(row => row.originalDraft !== JSON.stringify([row.scores, row.exceptionFlag])) },
    dynamicComponents() { return this.dynamicData?.scheme?.components || [] },
    schemeEditable() { return this.editable && !!this.dynamicData?.scheme?.editable },
    schemeTotal() { return Number(this.schemeDraft.reduce((sum, item) => sum + Number(item.weight || 0), 0).toFixed(4)) }
  },
  watch: {
    identityKey() { this.invalidateTask(); this.myTasks = []; this.submitReceipt = null; this.submitPending = false; this.loadTasks() },
    '$route.fullPath'() { this.invalidateTask(); this.loadTasks() }
  },
  created() { this.loadTasks() },
  beforeUnmount() { this.alive = false; this.invalidateTask() },
  methods: {
    denyTask(err) {
      if (!/403|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN/.test([err?.httpStatus, err?.bizCode, err?.code].join(' '))) return false
      this.invalidateTask(); this.myTasks = []; this.taskTotal = 0; this.taskPage = 1; this.submitReceipt = null; this.submitPending = false; this.showCreate = false
      this.form = { teachingTaskId: '', courseId: '', courseName: '', termId: '', termCode: '', credit: null, classId: '', usualRatio: 30, midtermRatio: 0, finalRatio: 70, passLine: 60, adminSupplementReason: '' }
      this.taskError = gradeError(err); return true
    },
    showTaskError(err, fallback) { if (!this.denyTask(err)) this.taskError = gradeError(err, fallback) },
    retryTask() { if (this.schemePending) return this.loadDynamic(); if (!this.task) return this.loadTasks(); if (this.formalSchemeMode === 'unknown' && this.task.allowedActions?.includes('INPUT')) return this.openTask({ gradeTaskId: this.task.gradeTaskId }); return this.dynamicMode ? this.loadDynamic() : this.refreshRecords() },
    resultLabel(value) { return value === 'PASSED' ? '及格' : ['FAIL', 'FAILED'].includes(value) ? '不及格' : '结果待确认' },
    resultColor(value) { return value === 'PASSED' ? 'success' : ['FAIL', 'FAILED'].includes(value) ? 'danger' : 'default' },
    captureTask() { return { taskId: this.task?.gradeTaskId, seq: this.taskSeq, identity: this.identityKey } },
    currentTask(context) { return this.alive && context.seq === this.taskSeq && context.identity === this.identityKey && String(context.taskId || '') === String(this.task?.gradeTaskId || '') },
    invalidateTask() {
      this.taskSeq++; this.listSeq++; this.recordsSeq++; this.dynamicSeq++;
      this.dynamicCommand = null; this.dynamicRecoveryError = ''; this.dynamicVerifying = false; this.dynamicPage = 1; this.dynamicQuality = null
      this.task = null; this.schemePending = false; this.pendingSchemeComponents = null; this.schemeDraft = []; this.candidateStudentId = ''; this.reminderTask = null; this.deadlineForm = { deadlineLocal: '', reason: '' }; this.formalSchemeMode = 'unknown'; this.rows = []; this.dynamicData = null; this.rosterInfo = null; this.taskError = ''; this.dynamicError = '';
      this.importVisible = false; this.importActions = null; this.reminderVisible = false; this.submitDialog = false; this.submitCommand = null;
      this.loadingRoster = false; this.dynamicLoading = false; this.taskLoading = false;
      this.creating = false; this.submitting = false; this.schemeSaving = false; this.dynamicSavingId = ''; this.savingRowId = ''; this.deadlineSaving = false; this.reminding = false
    },
    async readExactTask(taskId) {
      const res = await academicAffairsApi.getGradeTasks({ taskId, page: 1, pageSize: 1 })
      if (res?.code !== 0) throw res
      const row = res.data?.list?.find(item => String(item.gradeTaskId) === String(taskId))
      if (!row) throw { code: 404 }
      return row
    },
    async changeTaskPage(page) { if (this.writeBusy) return; this.taskPage = page; await this.loadTasks() },
    schemeStatusLabel(value) { return ({ DRAFT: '草稿', PUBLISHED: '已发布', ACTIVE: '生效中', LOCKED: '已锁定', ARCHIVED: '已归档' })[value] || (value ? '状态待确认' : '未设置') },
    statusLabel(status) { return TASK_STATUS[status] || (status ? '状态待确认' : '未知') },
    statusColor(status) {
      if (['PUBLISHED', 'ARCHIVED'].includes(status)) return 'success'
      if (['RETURNED'].includes(status)) return 'warning'
      if (['SUBMITTED', 'COLLEGE_REVIEW', 'ACADEMIC_REVIEW'].includes(status)) return 'primary'
      return 'default'
    },
    formatDeadline(value) {
      const parsed = asUtcDate(value)
      if (!parsed) return '—'
      return parsed.toLocaleString([], { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
    },
    deadlineLocalValue(value) {
      const parsed = asUtcDate(value)
      if (!parsed) return ''
      const shifted = new Date(parsed.getTime() - parsed.getTimezoneOffset() * 60000)
      return shifted.toISOString().slice(0, 16)
    },
    prepareDeadlineForm() {
      this.deadlineForm = {
        deadlineLocal: this.deadlineLocalValue(this.task?.deadline),
        reason: ''
      }
    },
    canRemind(row) {
      return this.isAdminRole && Array.isArray(row?.allowedActions) && row.allowedActions.includes('REMIND')
    },
    openReminder(row) {
      if (!this.canRemind(row)) return
      this.reminderTask = { ...row }
      this.reminderVisible = true
    },
    async confirmReminder({ reason }) {
      if (this.writeBusy || !this.reminderTask) return
      const context = this.captureTask()
      try {
      if (!this.reminderTask || this.reminding) return
      this.reminding = true
      const res = await gradeReminderApi.remind(this.reminderTask.gradeTaskId, reason)
      if (!this.currentTask(context)) return
      this.reminding = false
      if (res.code === 0) {
        const count = Number(res.data?.remindedCount || 0)
        toast.success(`已刷新 ${count} 位当前任课教师的待录待办并写入消息提醒`)
        this.reminderVisible = false
        this.reminderTask = null
        await this.loadTasks()
      if (!this.currentTask(context)) return
      } else toast.error(res.message || '催录失败')
      } catch (err) { if (this.currentTask(context)) this.showTaskError(err, '操作结果待核实，请先读取正式记录；不要重复操作。') }
      finally { if (this.alive && context.seq === this.taskSeq && context.identity === this.identityKey) this.reminding = false }
    },
    async saveDeadline() {
      if (this.writeBusy || !this.canExtendDeadline) return
      const context = this.captureTask()
      try {
      if (!this.canExtendDeadline || this.deadlineSaving) return
      if (!this.deadlineForm.deadlineLocal) { toast.error('请选择新的截止时间'); return }
      const reason = this.deadlineForm.reason.trim()
      if (reason.length < 5) { toast.error('设置 / 延期原因不少于5字'); return }
      const local = new Date(this.deadlineForm.deadlineLocal)
      if (Number.isNaN(local.getTime())) { toast.error('截止时间格式不合法'); return }
      this.deadlineSaving = true
      const res = await gradeReminderApi.extendDeadline(this.task.gradeTaskId, local.toISOString(), reason)
      if (!this.currentTask(context)) return
      this.deadlineSaving = false
      if (res.code !== 0) { toast.error(res.message || '截止时间更新失败'); return }
      const formal = await this.readExactTask(context.taskId)
      if (!this.currentTask(context)) return
      this.task = formal; this.prepareDeadlineForm()
      const listRow = this.myTasks.find(row => String(row.gradeTaskId) === String(formal.gradeTaskId))
      if (listRow) Object.assign(listRow, formal)
      toast.success(res.data?.isExtension ? '成绩提交截止时间已延长' : '成绩提交截止时间已设置')
      } catch (err) { if (this.currentTask(context)) this.showTaskError(err, '操作结果待核实，请先读取正式记录；不要重复操作。') }
      finally { if (this.alive && context.seq === this.taskSeq && context.identity === this.identityKey) this.deadlineSaving = false }
    },
    closeTask() {
      if (this.writeBusy || this.submitPending) return
      this.invalidateTask(); this.dynamicMode = false; this.showCreate = false
      this.deadlineForm = { deadlineLocal: '', reason: '' }
      if (this.$route.query.taskId) {
        const query = { ...this.$route.query }; delete query.taskId; delete query.action; delete query.mode
        this.$router.replace({ path: this.$route.path, query })
      } else this.loadTasks()
    },
    switchMode(value) {
      if (this.writeBusy || (!value && this.formalSchemeMode === 'dynamic')) return
      this.dynamicMode = value
      if (value) this.loadDynamic()
    },
    onTeachingTaskChange(value, items) {
      if (!value) {
        this.form.courseId = ''; this.form.courseName = ''; this.form.termCode = ''
        this.form.credit = null; this.form.classId = ''
        return
      }
      const item = items?.[0]
      const task = item?.raw || item || {}
      this.form.courseId = task.courseId || ''
      this.form.courseName = task.courseName || task.name || item?.label || ''
      if (task.credit != null) this.form.credit = task.credit
      if (task.classId != null) this.form.classId = String(task.classId)
      this.form.termCode = task.termCode || ''
    },
    onCourseChange(value, items) {
      const item = items?.[0]
      const course = item?.raw || item || {}
      this.form.courseId = value || course.courseId || course.id || ''
      this.form.courseName = course.courseName || course.name || item?.label || ''
      if (course.credit != null) this.form.credit = course.credit
    },
    onStudentPicked(value, items) {
      const item = items?.[0]
      if (!item) return
      this.addRow(item.raw || item)
      this.candidateStudentId = ''
    },
    async loadTasks() {
      const seq = ++this.listSeq, identity = this.identityKey
      const valid = () => this.alive && seq === this.listSeq && identity === this.identityKey
      this.taskLoading = true; this.taskError = ''
      try {
        const res = await academicAffairsApi.getGradeTasks({ page: this.taskPage, pageSize: 20 })
        if (!valid()) return
        if (res?.code !== 0) throw res
        this.myTasks = res.data?.list || []; this.taskTotal = res.data?.total || 0
        const taskId = this.$route.query.taskId
        if (taskId && !this.task) await this.openTask({ gradeTaskId: taskId })
      } catch (err) { if (valid()) this.showTaskError(err) }
      finally { if (valid()) this.taskLoading = false }
    },
    async openTask(row) {
      if (this.writeBusy || (this.submitPending && String(row.gradeTaskId) !== String(this.submitReceipt?.taskId))) return
      this.invalidateTask()
      const seq = this.taskSeq, identity = this.identityKey
      const valid = () => this.alive && seq === this.taskSeq && identity === this.identityKey
      this.taskLoading = true
      try {
        const task = await this.readExactTask(row.gradeTaskId)
        if (!valid()) return
        this.task = task; this.prepareDeadlineForm()
        this.restoreDynamicCommand()
        if (task.allowedActions?.includes('INPUT')) {
          const scheme = await academicAffairsR10Api.getGradeScheme(task.gradeTaskId)
          if (!valid()) return
          if (scheme?.code !== 0) throw scheme
          this.formalSchemeMode = scheme.data?.schemeId ? 'dynamic' : scheme.data?.status === 'DEFAULT' ? 'fixed' : 'unknown'
          if (this.formalSchemeMode === 'unknown') throw { code: 503 }
        }
        this.dynamicMode = this.formalSchemeMode === 'dynamic' || String(this.$route.query.mode || '') === 'dynamic'
        if (this.dynamicMode) await this.loadDynamic()
        else {
          await this.refreshRecords()
          if (valid() && this.fixedEditable && this.isAcademicTeacher) await this.loadRoster({ quiet: true })
        }
        if (valid() && this.$route.query.action === 'import' && this.fixedEditable) this.openImport()
      } catch (err) { if (valid()) this.showTaskError(err) }
      finally { if (valid()) this.taskLoading = false }
    },
    async refreshRecords() {
      if (!this.task) return
      const context = this.captureTask(), seq = ++this.recordsSeq
      try {
        const res = await academicAffairsApi.getGradeRecords(context.taskId)
        if (!this.currentTask(context) || seq !== this.recordsSeq) return
        if (res?.code !== 0) throw res
        this.rows = (res.data.items || []).map((item) => ({
          studentId: item.studentId, studentNo: item.studentNo, realName: item.realName, usual: item.usualScore,
          midterm: item.midtermScore, final: item.finalScore, total: item.totalScore,
          passStatus: item.passStatus, exceptionFlag: item.exceptionFlag || 'NORMAL'
        }))
      } catch (err) { if (this.currentTask(context) && seq === this.recordsSeq) this.showTaskError(err, '成绩记录读取失败，请重试。') }
    },
    schemeMatches(actual, expected) { return Array.isArray(actual) && Array.isArray(expected) && actual.length === expected.length && expected.every((item, i) => actual[i]?.code === item.code && actual[i].name === item.name && Number(actual[i].weight) === Number(item.weight) && (actual[i].required !== false) === (item.required !== false)) },
    async loadDynamic() {
      if (!this.task) return
      const context = this.captureTask(), seq = ++this.dynamicSeq
      const previousIdentity = this.dynamicData
      const drafts = new Map(this.dynamicRows.filter(row => row.originalDraft !== JSON.stringify([row.scores, row.exceptionFlag])).map(row => [String(row.studentId), row]))
      const valid = () => this.currentTask(context) && seq === this.dynamicSeq
      this.dynamicLoading = true; this.dynamicError = ''
      try {
        const res = await academicAffairsR10Api.getDynamicGradeRoster(context.taskId, { page: this.dynamicPage, pageSize: 30, ...(this.dynamicPage > 1 ? { expectedRosterVersionId: this.dynamicCommand?.rosterVersionId || this.dynamicData?.rosterIdentity?.rosterVersionId } : {}) })
        if (!valid()) return
        if (res?.code !== 0) throw res
        if (!res.data?.scheme || (!res.data.scheme.schemeId && res.data.scheme.status !== 'DEFAULT')) throw { code: 503 }
        if (String(res.data.gradeTaskId) !== String(context.taskId)) throw new Error('正式名单返回了其他成绩任务')
        if ([...drafts.keys()].some(id => !(res.data.items || []).some(row => String(row.studentId) === id))) throw new Error('名单已变化，原页草稿保留，请先核对学生名单。')
        this.dynamicData = res.data
        this.formalSchemeMode = res.data.scheme?.schemeId ? 'dynamic' : res.data.scheme?.status === 'DEFAULT' ? 'fixed' : this.formalSchemeMode
        this.schemeDraft = (res.data.scheme?.components || []).map((item, index) => ({ code: item.code, name: item.name, weight: Number(item.weight), required: item.required !== false, order: item.order || index + 1 }))
        this.dynamicData.items = (res.data.items || []).map(row => {
          const draft = drafts.get(String(row.studentId))
          const draftConflict = !!draft && (draft.draftConflict || draft.rowVersion !== row.rowVersion || String(draft.recordId || '') !== String(row.recordId || '') || previousIdentity?.scheme?.schemeVersion !== res.data.scheme.schemeVersion || previousIdentity?.rosterIdentity?.rosterVersionId !== res.data.rosterIdentity?.rosterVersionId)
          return { ...row, scores: { ...(draft?.scores || row.scores || {}) }, formalScores: { ...(row.scores || {}) },
            draftConflict, formalExceptionFlag: row.exceptionFlag || 'NORMAL', exceptionFlag: draft?.exceptionFlag || row.exceptionFlag || 'NORMAL', originalDraft: JSON.stringify([row.scores || {}, row.exceptionFlag || 'NORMAL']) }
        })
        if (res.data.status) this.task.status = res.data.status
        if (this.schemePending && res.data.scheme?.schemeId && this.schemeMatches(res.data.scheme.components, this.pendingSchemeComponents)) { this.schemePending = false; this.pendingSchemeComponents = null; this.taskError = '' }
        if (this.schemePending) this.dynamicError = '结果待核实：正式方案尚未反映本次内容，请继续只读核对。'
        return !this.schemePending
      } catch (err) { if (valid() && !this.denyTask(err)) this.dynamicError = gradeError(err, '动态成绩工作区加载失败。'); return false }
      finally { if (valid()) this.dynamicLoading = false }
    },
    addComponent() {
      const index = this.schemeDraft.length + 1
      this.schemeDraft.push({ code: `ITEM_${index}`, name: `成绩项${index}`, weight: 0, required: true, order: index })
    },
    removeComponent(index) { this.schemeDraft.splice(index, 1) },
    async saveScheme() {
      if (!this.task || !this.schemeEditable || this.writeBusy) return
      if (Math.abs(this.schemeTotal - 100) > 0.0001) { toast.error(`权重合计须为100%，当前为${this.schemeTotal}%`); return }
      const context = this.captureTask()
      const components = this.schemeDraft.map((item, index) => ({ ...item, code: String(item.code || '').toUpperCase(), order: index + 1 }))
      this.schemeSaving = true; this.schemePending = true; this.pendingSchemeComponents = components; this.formalSchemeMode = 'unknown'; this.dynamicSeq++
      try {
        const res = await academicAffairsR10Api.updateGradeScheme(context.taskId, components)
        if (!this.currentTask(context)) return
        if (res?.code !== 0) throw res
        const read = await this.loadDynamic()
        if (!this.currentTask(context)) return
        if (!read) { this.taskError = '方案保存结果待核实，请重新读取正式方案；固定录入和再次保存暂不可用。'; return }
        const actual = this.dynamicData?.scheme?.components || []
        const matched = this.schemeMatches(actual, components)
        if (this.formalSchemeMode === 'dynamic' && matched) toast.success('动态成绩项方案已保存并回读')
        else this.taskError = '当前正式方案已回读，但与本次提交内容不一致，请核对后办理。'
      } catch (err) { if (this.currentTask(context)) this.showTaskError(err, '方案保存结果待核实，请先读取正式方案；不要重复保存。') }
      finally { if (this.currentTask(context)) this.schemeSaving = false }
    },
    restoreDynamicCommand() {
      const identityRef = gradeCommandIdentityRef(currentUserFromToken() || {})
      const found = findGradeCommandReference(identityRef, ['GRADE_COMPONENT_BATCH_SAVE', 'GRADE_TASK_SUBMIT'], this.task?.gradeTaskId)
      this.dynamicRecoveryError = !identityRef ? '登录身份无法核对，请重新登录后读取原命令。' : found.ok ? '' : found.error
      this.dynamicCommand = found.entry || null
      if (this.dynamicCommand) this.dynamicPage = this.dynamicCommand.rosterVersionId ? this.dynamicCommand.page : 1
    },
    dynamicExpected() {
      const data = this.dynamicData
      if (!data || String(data.gradeTaskId) !== String(this.task?.gradeTaskId) || !Number.isInteger(data.taskVersion) || !data.rosterIdentity?.rosterHash) throw new Error('正式任务和名单版本尚未载入')
      return { expectedTaskVersion: data.taskVersion, expectedSchemeId: data.scheme.schemeId,
        expectedSchemeVersion: data.scheme.schemeVersion, rosterIdentity: { ...data.rosterIdentity } }
    },
    beginDynamicCommand(operation) {
      const saved = createGradeCommandReference({ identityRef: gradeCommandIdentityRef(currentUserFromToken() || {}), operation, objectId: this.task.gradeTaskId, page: this.dynamicPage, rosterVersionId: this.dynamicData?.rosterIdentity?.rosterVersionId })
      if (!saved.ok) { this.dynamicRecoveryError = saved.error; return null }
      this.dynamicCommand = saved.entry
      return saved.existing ? null : saved.entry
    },
    async verifyDynamicCommand() {
      const command = this.dynamicCommand, context = this.captureTask()
      if (!command || this.dynamicVerifying || command.identityRef !== gradeCommandIdentityRef(currentUserFromToken() || {}) || String(command.objectId) !== String(context.taskId)) return
      this.dynamicVerifying = true
      try {
        const receipt = await academicAffairsR10Api.getDynamicGradeReceipt(context.taskId, command.operation, command.commandKey)
        if (!this.currentTask(context)) return
        if (receipt?.code !== 0) throw receipt
        const ack = receipt.data?.result
        if (receipt.data?.state !== 'SUCCESS' || receipt.data.commandKey !== command.commandKey || receipt.data.operation !== command.operation || String(ack?.gradeTaskId) !== String(context.taskId)) {
          this.taskError = '尚未取得本次原命令的成功回执，请继续只读核对。'; return
        }
        const formalTask = await this.readExactTask(context.taskId)
        if (!this.currentTask(context)) return
        if (command.operation === 'GRADE_COMPONENT_BATCH_SAVE') {
          if (!Array.isArray(ack.items) || ack.savedCount !== ack.items.length || !ack.items.length || ack.items.some(item => !item.recordId || !Number.isInteger(item.rowVersion))) throw new Error('原保存回执不完整')
          const read = await academicAffairsR10Api.getDynamicGradeRoster(context.taskId, { page: command.page, pageSize: 30, ...(command.page > 1 ? { expectedRosterVersionId: ack.rosterIdentity?.rosterVersionId || command.rosterVersionId } : {}) })
          if (!this.currentTask(context)) return
          if (read?.code !== 0) throw read
          if (String(read.data?.gradeTaskId) !== String(context.taskId)) throw new Error('正式记录对象不一致')
          // Only saved rows are refreshed: another student's unsaved draft survives.
          for (const saved of ack.items) {
            const local = this.dynamicRows.find(row => String(row.studentId) === String(saved.studentId))
            const formal = read.data.items?.find(row => String(row.studentId) === String(saved.studentId))
            if (!formal || String(formal.recordId) !== String(saved.recordId) || formal.rowVersion < saved.rowVersion) throw new Error('正式行尚未反映原命令结果')
            if (local) Object.assign(local, formal, { scores: { ...formal.scores }, formalScores: { ...formal.scores }, formalExceptionFlag: formal.exceptionFlag || 'NORMAL', draftConflict: false, originalDraft: JSON.stringify([formal.scores || {}, formal.exceptionFlag || 'NORMAL']) })
          }
          if (this.dynamicData) { this.dynamicData.taskVersion = read.data.taskVersion; this.dynamicData.scheme = read.data.scheme; this.dynamicData.rosterIdentity = read.data.rosterIdentity; this.dynamicData.canWriteComponents = read.data.canWriteComponents }
          this.formalSchemeMode = 'dynamic'
          this.dynamicQuality = ack.qualityReport
        } else {
          if (ack.status !== 'SUBMITTED' || !ack.workflowInstanceId || ack.nextNode !== 'COLLEGE_REVIEW') throw new Error('原提交回执缺少正式审核流')
          this.submitReceipt = { taskId: context.taskId, courseName: formalTask.courseName, status: formalTask.status, verified: true }
          this.submitPending = false
        }
        this.task = formalTask
        const removed = removeGradeCommandReference(command.commandKey, command.identityRef)
        if (!removed.ok) { this.dynamicRecoveryError = removed.error; return }
        this.dynamicCommand = null; this.dynamicRecoveryError = ''; this.taskError = ''
        toast.success(command.operation === 'GRADE_TASK_SUBMIT' ? '原提交已确认，正式审核流程已建立' : '原保存已确认，当前正式记录已回读')
      } catch (err) { if (this.currentTask(context)) this.showTaskError(err, '原操作结果待核实，请保留草稿并继续只读核对。') }
      finally { if (this.currentTask(context)) this.dynamicVerifying = false }
    },
    handleDynamicRejection(result, command) {
      const status = Number(result?.httpStatus)
      // A 5xx response is always uncertain, even when its body contains 409.
      const explicit = status >= 400 && status < 500 && /^(400|401|403|404|409|422)$/.test(String(status))
      if (!explicit) return false
      const removed = removeGradeCommandReference(command.commandKey, command.identityRef)
      if (!removed.ok) { this.dynamicRecoveryError = removed.error; return false }
      this.dynamicCommand = null
      this.showTaskError(result, '本次原命令未受理，草稿保留；请核对最新任务版本。')
      return true
    },
    confirmDynamicDraft(row) {
      if (!this.dynamicRows.includes(row) || this.writeBusy || this.dynamicCommand) return
      row.draftConflict = false
    },
    async saveDynamicRow(row) { return this.saveDynamicRows([row]) },
    async saveDynamicRows(rows = this.dynamicRows) {
      if (this.writeBusy) return
      if (rows.some(row => (typeof row.studentId === 'number' && !Number.isSafeInteger(row.studentId)) || !/^[1-9]\d*$/.test(String(row.studentId)))) { this.taskError = '学生标识无法准确读取，请重新加载正式名单。'; return }
      if (!this.dynamicWritable) return
      const context = this.captureTask()
      let command
      try {
        const expected = this.dynamicExpected()
        const changes = rows.map(row => ({ studentId: String(row.studentId), expectedRecordId: row.recordId || '', expectedRowVersion: row.rowVersion ?? null,
          scores: Object.fromEntries(Object.entries(row.scores || {}).filter(([, value]) => value !== '' && value != null)), exceptionFlag: row.exceptionFlag || 'NORMAL' }))
        command = this.beginDynamicCommand('GRADE_COMPONENT_BATCH_SAVE')
        if (!command) return
        this.dynamicSavingId = rows.length === 1 ? rows[0].studentId : 'batch'
        const res = await academicAffairsR10Api.saveDynamicGradeBatch(context.taskId, { ...expected, rows: changes }, command.commandKey)
        // Persistent reference was written before POST; late replies never unlock another identity.
        if (!this.currentTask(context)) return
        if (res?.code !== 0 && this.handleDynamicRejection(res, command)) return
        await this.verifyDynamicCommand()
      } catch (err) { if (this.currentTask(context)) this.showTaskError(err, command ? '保存结果待核实，请只读核对原命令；草稿保留。' : '正式版本无法确认，本次未发送保存。') }
      finally { if (this.currentTask(context)) this.dynamicSavingId = '' }
    },
    openImport() {
      if (!this.fixedEditable || this.writeBusy) return
      const context = this.captureTask()
      this.importActions = {
        template: () => { if (!this.currentTask(context)) return Promise.reject(new Error('任务已切换，请重新打开导入')); return academicAffairsApi.downloadGradeImportTemplate(context.taskId) },
        upload: file => { if (!this.currentTask(context)) return Promise.reject(new Error('任务已切换，请重新打开导入')); return academicFileExchangeApi.uploadGradeImport(context.taskId, file) },
        complete: result => { if (this.currentTask(context)) return this.onImported(result) }
      }
      this.importVisible = true
    },
    async onImported(result) {
      if (!this.task || !this.importVisible) return
      const context = this.captureTask()
      await this.refreshRecords()
      if (!this.currentTask(context)) return
      try {
        const formal = await this.readExactTask(context.taskId)
        if (!this.currentTask(context)) return
        this.task = formal
        toast.success(`已回读导入结果：${result?.imported ?? result?.created ?? 0} 条`)
      } catch (err) { if (this.currentTask(context)) this.showTaskError(err, '导入结果待核实，请读取正式任务。') }
    },
    async createTask() {
      if (this.writeBusy) return
      const context = this.captureTask()
      try {
      if (this.creating) return
      if (!this.form.teachingTaskId && !this.isAdminRole) { toast.error('请选择教学任务'); return }
      if (!this.form.teachingTaskId) {
        if (!this.form.courseId) { toast.error('请选择课程库具体版本'); return }
        if (!this.form.termId) { toast.error('请选择正式学期'); return }
        if (!this.form.classId) { toast.error('请选择明确行政班'); return }
        if ((this.form.adminSupplementReason || '').trim().length < 5) { toast.error('管理员特殊补录原因不少于5字'); return }
      }
      if (Number(this.form.usualRatio) + Number(this.form.midtermRatio) + Number(this.form.finalRatio) !== 100) {
        toast.error('平时+期中+期末占比之和须=100'); return
      }
      this.creating = true
      const payload = {
        teachingTaskId: this.form.teachingTaskId || undefined,
        courseId: this.form.teachingTaskId ? undefined : Number(this.form.courseId),
        courseName: this.form.teachingTaskId ? undefined : this.form.courseName,
        termId: this.form.teachingTaskId ? undefined : Number(this.form.termId),
        classId: this.form.teachingTaskId ? undefined : Number(this.form.classId),
        credit: this.form.teachingTaskId ? undefined : this.form.credit,
        usualRatio: Number(this.form.usualRatio), midtermRatio: Number(this.form.midtermRatio),
        finalRatio: Number(this.form.finalRatio), passLine: Number(this.form.passLine),
        adminSupplementReason: this.form.teachingTaskId ? undefined : this.form.adminSupplementReason.trim()
      }
      const res = this.form.teachingTaskId
        ? await academicAffairsApi.createGradeTask(payload)
        : await gradeIdentityApi.createGradeTask(payload)
      if (!this.currentTask(context)) return
      this.creating = false
      if (res.code === 0) { this.task = res.data; this.prepareDeadlineForm(); toast.success('任务已创建，开始录入'); this.loadTasks() }
      else toast.error(res.message || '创建失败')
      } catch (err) { if (this.currentTask(context)) this.showTaskError(err, '操作结果待核实，请先读取正式记录；不要重复操作。') }
      finally { if (this.alive && context.seq === this.taskSeq && context.identity === this.identityKey) this.creating = false }
    },
    async loadRoster({ quiet = false } = {}) {
      if (!this.fixedEditable || this.loadingRoster || this.writeBusy) return
      const context = this.captureTask()
      try {
      if (this.loadingRoster) return
      this.loadingRoster = true
      const res = await academicAffairsApi.getGradeRoster(this.task.gradeTaskId)
      if (!this.currentTask(context)) return
      this.loadingRoster = false
      if (res.code === 0) {
        this.rosterInfo = res.data
        const items = res.data.items || []
        if (!items.length) { if (!quiet) toast.error(res.data.note || '未圈定到正式名单'); return }
        items.forEach((student) => this.addRow(student))
        if (!quiet) toast.success(`已读取正式名单 ${items.length} 人`)
      } else toast.error(res.message || '加载名单失败')
      } catch (err) { if (this.currentTask(context)) this.showTaskError(err, '操作结果待核实，请先读取正式记录；不要重复操作。') }
      finally { if (this.alive && context.seq === this.taskSeq && context.identity === this.identityKey) this.loadingRoster = false }
    },
    addRow(student) {
      if (this.rows.some((row) => row.studentId === student.studentId)) return
      this.rows.push({ studentId: student.studentId, studentNo: student.studentNo, realName: student.realName, usual: null, midterm: null, final: null, total: null, passStatus: null, exceptionFlag: 'NORMAL' })
    },
    async saveRow(row) {
      if (!this.fixedEditable || this.writeBusy) return
      const context = this.captureTask()
      const payload = { studentId: row.studentId,
        usualScore: row.exceptionFlag === 'NORMAL' && row.usual !== '' && row.usual != null ? row.usual : undefined,
        midtermScore: row.exceptionFlag === 'NORMAL' && row.midterm !== '' && row.midterm != null ? row.midterm : undefined,
        finalScore: row.exceptionFlag === 'NORMAL' && row.final !== '' && row.final != null ? row.final : undefined,
        clearUsual: row.exceptionFlag === 'NORMAL' && (row.usual === '' || row.usual == null),
        clearMidterm: row.exceptionFlag === 'NORMAL' && this.hasMidterm && (row.midterm === '' || row.midterm == null),
        clearFinal: row.exceptionFlag === 'NORMAL' && (row.final === '' || row.final == null),
        exceptionFlag: row.exceptionFlag }
      this.savingRowId = String(row.studentId)
      try {
        const res = await academicAffairsApi.enterScore(context.taskId, payload)
        if (!this.currentTask(context)) return
        if (res?.code !== 0) throw res
        const records = await academicAffairsApi.getGradeRecords(context.taskId)
        if (!this.currentTask(context)) return
        if (records?.code !== 0) throw records
        const formal = records.data?.items?.find(item => String(item.studentId) === String(row.studentId))
        if (!formal) throw { code: 503 }
        const changedFields = [['usualScore', 'clearUsual'], ['midtermScore', 'clearMidterm'], ['finalScore', 'clearFinal']]
        if (changedFields.some(([field, clear]) => payload[clear] ? formal[field] != null : payload[field] != null && Number(formal[field]) !== Number(payload[field]))) throw { code: 503 }
        row.usual = formal.usualScore ?? null; row.midterm = formal.midtermScore ?? null; row.final = formal.finalScore ?? null
        row.exceptionFlag = formal.exceptionFlag || row.exceptionFlag
        row.total = formal.totalScore; row.passStatus = formal.passStatus
        const task = await this.readExactTask(context.taskId)
        if (!this.currentTask(context)) return
        this.task = task
        toast.success(`${row.realName} 已保存并回读`)
      } catch (err) { if (this.currentTask(context)) this.showTaskError(err, '保存结果待核实，请核对正式记录；草稿保留，请勿重复录入。') }
      finally { if (this.currentTask(context)) this.savingRowId = '' }
    },
    async submitDynamicTask() {
      const context = this.submitCommand
      if (!context || !this.currentTask(context) || !this.canSubmit || this.writeBusy) return
      if (this.dynamicDirty) { this.taskError = '当前页有未保存分项，请先保存后检查。'; return }
      this.submitting = true
      let command
      try {
        const expected = this.dynamicExpected()
        const quality = await academicAffairsR10Api.getDynamicGradeQuality(context.taskId)
        if (!this.currentTask(context)) return
        if (quality?.code !== 0) throw quality
        this.dynamicQuality = quality.data
        if (String(quality.data?.gradeTaskId) !== String(context.taskId) || quality.data.taskVersion !== expected.expectedTaskVersion || quality.data.canSubmit !== true) {
          this.taskError = quality.data?.summary || '完整性或版本检查未通过，本次未提交。'; return
        }
        command = this.beginDynamicCommand('GRADE_TASK_SUBMIT')
        if (!command) return
        this.submitDialog = false
        const res = await academicAffairsR10Api.submitDynamicGrade(context.taskId, expected, command.commandKey)
        if (!this.currentTask(context)) return
        if (res?.code !== 0 && this.handleDynamicRejection(res, command)) return
        await this.verifyDynamicCommand()
      } catch (err) { if (this.currentTask(context)) this.showTaskError(err, command ? '提交结果待核实，请只读核对原命令。' : '未能核对正式成绩，本次未提交。') }
      finally { if (this.currentTask(context)) this.submitting = false }
    },
    async changeDynamicPage(page) {
      if (this.writeBusy || this.dynamicLoading || this.dynamicCommand || this.dynamicDirty || page < 1) return
      this.dynamicPage = page
      await this.loadDynamic()
    },
    openSubmit() {
      if (!this.canSubmit || this.writeBusy) return
      this.submitCommand = { ...this.captureTask(), courseName: this.task.courseName }
      this.submitDialog = true
    },
    async submit() {
      if (this.dynamicMode) return this.submitDynamicTask()
      const context = this.submitCommand
      if (!context || !this.currentTask(context) || !this.canSubmit || this.writeBusy) return
      this.submitting = true
      try {
        const before = await this.readExactTask(context.taskId)
        if (!this.currentTask(context)) return
        this.task = before
        if (!this.canSubmit) { this.submitDialog = false; this.taskError = '任务状态或办理权限已变化，请重新核对。'; return }
        this.submitPending = true
        this.submitReceipt = { taskId: this.task.gradeTaskId, courseName: this.task.courseName, status: null, verified: false }
        let res
        try { res = await academicAffairsApi.submitGradeTask(context.taskId) } catch { res = null }
        if (!this.currentTask(context)) return
        this.submitDialog = false
        if (res && res.code !== 0 && /403|404|409|NO_PERMISSION|CONFLICT|VALIDATION/.test(String(res.bizCode || res.code))) {
          this.submitPending = false; this.submitReceipt = null; this.showTaskError(res, '本次提交未受理，请核对任务。'); return
        }
        await this.verifySubmit()
      } catch (err) { if (this.currentTask(context)) this.showTaskError(err, '未能核对任务，本次未提交。') }
      finally { if (this.currentTask(context)) this.submitting = false }
    },
    async verifySubmit() {
      if (!this.task || !this.submitReceipt || this.submitReceipt.verified || String(this.task.gradeTaskId) !== String(this.submitReceipt.taskId)) return
      const context = this.captureTask()
      try {
        const task = await this.readExactTask(context.taskId)
        if (!this.currentTask(context)) return
        this.task = task
        const verified = ['SUBMITTED', 'COLLEGE_REVIEW', 'ACADEMIC_REVIEW', 'PUBLISHED', 'ARCHIVED'].includes(task.status)
        this.submitReceipt = { taskId: this.task.gradeTaskId, courseName: this.task.courseName, status: task.status, verified }
        if (verified) this.submitPending = false
      } catch { /* 保留待核实回执；不重放提交。 */ }
    }

  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-task-settings { border: 1px solid var(--border-base); border-radius: 10px; background: var(--bg-card); }
.aa-task-settings summary { padding: 12px 16px; cursor: pointer; font-size: 13px; font-weight: 600; color: var(--text-primary); }
.aa-task-settings summary span { margin-left: 12px; color: var(--text-secondary); font-size: 12px; font-weight: 400; }
.aa-task-settings[open] summary { border-bottom: 1px solid var(--border-base); }
.aa-task-context .aa-task-source { margin-top: 5px; }
.aa-table-scroll .aa-course-table { min-width: 780px; }
.aa-table-scroll .aa-course-table th { padding: 12px 14px; background: var(--pri-bg); }
.aa-table-scroll .aa-course-table td { padding: 14px; font-size: 12px; }
.aa-table-scroll .aa-course-table tr:hover td { background: var(--bg-hover, var(--pri-bg)); }
.aa-total-score { color: var(--pri); font-weight: 700; }
.aa-grid2 { display: grid; grid-template-columns: repeat(2, minmax(220px, 1fr)); gap: 14px 24px; }
.aa-field { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-field .req::before, .aa-field span.req::before { content: '*'; color: var(--danger-600, #f53f3f); margin-right: 4px; }
.aa-input { height: 34px; padding: 0 12px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 14px; box-sizing: border-box; }
.aa-input--grow { flex: 1; }.aa-input--xs { width: 82px; height: 30px; padding: 0 8px; }
.aa-actions { margin-top: 16px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }.aa-reg-search { display: flex; gap: 12px; }
.aa-task-head { display: flex; align-items: center; gap: 16px; font-size: 14px; color: var(--text-700, #4e5969); margin-bottom: 8px; flex-wrap: wrap; }
.aa-mode-switch { display: inline-flex; gap: 4px; margin: 8px 0 12px; padding: 4px; border-radius: 8px; background: var(--fill-100, #f2f3f5); }
.aa-mode { padding: 7px 14px; border: 0; border-radius: 6px; background: transparent; color: var(--text-600, #64748b); cursor: pointer; }
.aa-mode.is-active { background: var(--bg-card); color: var(--primary-600, #2563eb); box-shadow: 0 1px 3px rgba(15,23,42,.12); }
.aa-course-table { width: 100%; border-collapse: collapse; }.aa-course-table th, .aa-course-table td { text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--border-100, #f0f1f2); font-size: 14px; }
.aa-course-table th { color: var(--text-500, #646a73); font-weight: 500; font-size: 13px; white-space: nowrap; }.aa-course-table th small, .aa-course-table td small { display: block; margin-top: 3px; color: var(--text-400, #8a9099); font-size: 12px; }
.aa-table-scroll { overflow-x: auto; }.aa-dynamic-table { min-width: 860px; }
.aa-scheme-head { display: flex; justify-content: space-between; margin: 14px 0 10px; color: var(--text-600, #64748b); font-size: 13px; }
.aa-scheme-list { display: flex; flex-direction: column; gap: 8px; }.aa-scheme-row { display: flex; align-items: center; gap: 10px; }.aa-code { width: 150px; }.aa-name { flex: 1; }.aa-weight { width: 110px; }.aa-required { display: flex; align-items: center; gap: 5px; font-size: 13px; white-space: nowrap; }.is-danger { color: var(--danger-600, #dc2626); }
.aa-my-tasks { margin: 0; padding: 0; }.aa-my-tasks h4 { margin: 0 0 10px; font-size: 14px; }
.aa-my-tasks ul { list-style: none; margin: 0; padding: 0; }.aa-my-task-item { display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--border-100, #f0f1f2); font-size: 14px; }.aa-my-task-item small { color: var(--text-500, #64748b); }
.aa-remind-link { color: var(--warning-700, #b45309); }.aa-overdue-text { color: var(--danger-600, #dc2626); font-weight: 600; }
.aa-action-receipt { display: grid; grid-template-columns: minmax(0,1fr) auto auto auto; align-items: center; gap: 18px; padding: 13px 15px; border: 1px solid #a7d7b4; border-radius: 11px; background: var(--bg-card); }
.aa-action-receipt strong, .aa-action-receipt span, .aa-action-receipt small, .aa-action-receipt b { display: block; }
.aa-action-receipt strong { color: var(--text-primary); font-size: 14px; }.aa-action-receipt span { margin-top: 3px; color: var(--text-secondary); font-size: 12px; }.aa-action-receipt small { color: var(--text-tertiary); font-size: 12px; }.aa-action-receipt b { margin-top: 3px; color: var(--text-primary); font-size: 12px; }
.aa-task-context { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 24px; padding: 16px; border: 1px solid #dbe5f2; border-left: 3px solid var(--pri); border-radius: 11px; background: var(--bg-card); }
.aa-task-context__identity { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; min-width: 0; }
.aa-task-context__eyebrow { color: var(--text-secondary); font-size: 12px; }
.aa-task-context h2 { margin: 4px 0 5px; color: var(--text-primary); font-size: 17px; line-height: 1.35; }
.aa-task-context h2 span { font-weight: 600; }
.aa-task-context p { margin: 0; color: var(--text-secondary); font-size: 12px; }
.aa-task-context__responsibility { display: grid; grid-template-columns: repeat(2, minmax(135px, 1fr)); gap: 22px; align-content: center; }
.aa-task-context__responsibility small, .aa-task-context__responsibility strong { display: block; }
.aa-task-context__responsibility small { color: var(--text-tertiary); font-size: 11px; }
.aa-task-context__responsibility strong { margin-top: 4px; color: var(--text-primary); font-size: 12px; }
.aa-grade-steps { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 0; margin: 0; padding: 15px 16px; list-style: none; border: 1px solid #e4eaf2; border-radius: 11px; background: var(--bg-card); }
.aa-grade-steps li { position: relative; display: flex; align-items: flex-start; gap: 9px; min-width: 0; color: var(--text-tertiary); }
.aa-grade-steps li:not(:last-child)::after { content: ''; position: absolute; top: 12px; right: 10px; left: 42px; height: 1px; background: #e1e7ef; }
.aa-grade-steps li > span { position: relative; z-index: 1; display: grid; place-items: center; flex: 0 0 24px; height: 24px; border: 1px solid #dce3ec; border-radius: 50%; background: var(--bg-card); font-size: 11px; }
.aa-grade-steps li > div { position: relative; z-index: 1; min-width: 0; padding-right: 10px; background: var(--bg-card); }
.aa-grade-steps strong, .aa-grade-steps small { display: block; white-space: nowrap; }
.aa-grade-steps strong { color: var(--text-secondary); font-size: 12px; }
.aa-grade-steps small { margin-top: 3px; font-size: 10px; }
.aa-grade-steps li.is-done > span { color: #267a4b; border-color: #b9dfc8; background: #f0faf4; }
.aa-grade-steps li.is-current > span { color: #fff; border-color: var(--pri); background: var(--pri); }
.aa-grade-steps li.is-current strong { color: var(--pri); }
.aa-grade-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.aa-grade-metrics article { min-width: 0; padding: 14px 16px; border: 1px solid #e2e8f0; border-radius: 11px; background: var(--bg-card); }
.aa-grade-metrics small, .aa-grade-metrics strong, .aa-grade-metrics span { display: block; }
.aa-grade-metrics small { color: var(--text-secondary); font-size: 12px; }
.aa-grade-metrics strong { margin-top: 6px; color: var(--text-primary); font-size: 24px; }
.aa-grade-metrics span { margin-top: 5px; color: var(--text-tertiary); font-size: 11px; }
@media (max-width: 980px) { .aa-task-context { grid-template-columns: 1fr; }.aa-grade-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }.aa-grade-steps { overflow-x: auto; grid-template-columns: repeat(5, minmax(150px, 1fr)); } }
@media (max-width: 760px) { .aa-grid2, .aa-action-receipt, .aa-grade-metrics { grid-template-columns: 1fr; }.aa-task-context__identity { flex-direction: column; }.aa-task-context__responsibility { grid-template-columns: 1fr; gap: 10px; }.aa-action-receipt { align-items: stretch; gap: 10px; }.aa-scheme-row { align-items: stretch; flex-direction: column; }.aa-code, .aa-weight { width: 100%; } }
</style>
