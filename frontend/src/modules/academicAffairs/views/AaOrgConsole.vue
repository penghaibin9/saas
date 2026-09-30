<template>
  <ModulePageShell
    class="aa-foundation-workspace"
    :title="pageMeta.title"
    :subtitle="pageMeta.subtitle"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
  >
    <template #actions>
      <AppButton v-if="canCreate" :disabled="busy || (tab !== 'college' && (optionsLoading || !!optionsError))"
              variant="primary" @click="openCreate">新建{{ tabLabel }}</AppButton>
    </template>

    <div class="mp-stack">
      <AppInlineAlert v-if="optionsError" type="danger" :description="optionsError" />
      <AppButton v-if="optionsError" variant="ghost" :disabled="busy" @click="loadOptions">重新加载组织选项</AppButton>

      <!-- 统计概览 -->
      <section v-if="tab === 'stats'" class="mp-card">
        <div class="mp-card__body">
          <ErrorState v-if="statsError" :description="statsError" @retry="loadStats" />
          <LoadingState v-else-if="statsLoading" />
          <div v-else class="mp-stack">
            <div class="aa-stat-grid">
              <div v-for="s in statCards" :key="s.key" class="aa-stat">
                <div class="aa-stat__num">{{ stats[s.key] ?? 0 }}</div>
                <div class="aa-stat__label">{{ s.label }}</div>
              </div>
            </div>
            <div class="aa-stat-ledger">
              <section class="aa-stat-panel">
                <h2>学院学生分布</h2>
                <div v-for="item in stats.collegeDistribution || []" :key="item.collegeId" class="aa-stat-bar-row">
                  <span>{{ item.collegeName }}</span>
                  <div><i :style="{ width: distributionWidth(item.studentCount) }"></i></div>
                  <strong>{{ item.studentCount }}</strong>
                </div>
              </section>
              <section class="aa-stat-panel">
                <h2>组织规模台账</h2>
                <table class="mp-audit"><thead><tr><th>学院</th><th>专业</th><th>行政班</th><th>学生</th></tr></thead>
                  <tbody><tr v-for="item in stats.collegeDistribution || []" :key="item.collegeId"><td>{{ item.collegeName }}</td><td>{{ item.majorCount }}</td><td>{{ item.classCount }}</td><td>{{ item.studentCount }}</td></tr></tbody>
                </table>
              </section>
            </div>
          </div>
        </div>
      </section>

      <!-- 组织树 -->
      <template v-else-if="tab === 'tree'">
      <AaOrgReferencePanel :college-options="collegeOptions" @view-organization="viewCheckedOrganization" />
      <section class="mp-card">
        <div class="mp-card__body">
          <h2>组织关系</h2>
          <ErrorState v-if="treeError" :description="treeError" @retry="loadTree" />
          <LoadingState v-else-if="treeLoading" />
          <EmptyState v-else-if="!tree.colleges || !tree.colleges.length" title="暂无组织数据" description="先在「学院」页签新建学院、专业与班级" />
          <ul v-else class="aa-tree">
            <li v-for="c in tree.colleges" :key="c.id">
              <strong>{{ c.collegeName }}</strong><span v-if="c.shortName" class="mp-note"> · {{ c.shortName }}</span>
              <ul>
                <li v-for="m in c.majors" :key="m.id">
                  {{ m.majorName }}
                  <StatusTag :type="m.enrollStatus === 'ENROLLING' ? 'success' : 'default'"
                             :label="m.enrollStatus === 'ENROLLING' ? '招生中' : '停招'" dot />
                  <ul>
                    <li v-for="k in m.classes" :key="k.id">
                      {{ k.className }} <span class="mp-note">（{{ classStatusLabel(k.classStatus) }}）</span>
                    </li>
                  </ul>
                </li>
              </ul>
            </li>
          </ul>
        </div>
      </section>

      </template>

      <!-- 专业方向（06号卡） -->
      <section v-else-if="tab === 'direction'" class="mp-card">
        <div class="mp-card__body">
          <div class="aa-filter">
            <span class="aa-note-inline">总开关：</span>
            <StatusTag v-if="directionToggle.loaded" :type="directionToggle.enabled ? 'success' : 'default'"
                       :label="directionToggle.enabled ? '已启用' : '未启用'" dot />
            <AppButton v-if="canManageSchool" :loading="directionToggle.loading" :disabled="busy || !directionToggle.loaded" @click="toggleMajorDirection">
              {{ directionToggle.enabled ? '停用总开关' : '启用总开关' }}
            </AppButton>
            <template v-if="directionToggle.loaded && directionToggle.enabled">
              <AppMajorPicker v-model="directionMajorId" placeholder="请选择专业" @change="changeDirectionMajor"
                              :options="majorOptions" :disabled="busy" />
              <AppButton v-if="directionMajorId && canManage" variant="primary" :disabled="busy" @click="openDirectionCreate">＋ 新建方向</AppButton>
            </template>
          </div>
          <ErrorState v-if="directionToggle.error" :description="directionToggle.error" @retry="loadDirectionToggle" />
          <LoadingState v-else-if="directionToggle.loading" />
          <EmptyState v-else-if="!directionToggle.enabled" title="专业方向总开关未启用"
                      description="本校尚未启用「专业方向」管理粒度；是否启用属学校业务政策，需教务处/校管确认后在此开启总开关。" />
          <EmptyState v-else-if="!directionMajorId" title="请选择专业" description="选择上方专业后查看/维护其下的方向" />
          <template v-else>
            <ErrorState v-if="directions.error" :description="directions.error" @retry="reloadDirections" />
            <LoadingState v-else-if="directions.loading" />
            <EmptyState v-else-if="!directions.rows.length" title="该专业暂无方向" description="点击「新建方向」新增" />
            <div class="aa-table-scroll" role="region" aria-label="数据表格，可横向滚动" tabindex="0" v-else>
<table  class="mp-audit">
              <thead><tr><th>方向名称</th><th>编码</th><th>所属专业</th><th>适用年级</th><th>责任岗位</th><th>状态</th><th>操作</th></tr></thead>
              <tbody>
                <tr v-for="d in directions.rows" :key="d.id">
                  <td>{{ d.directionName }}</td><td>{{ d.code || '—' }}</td><td>{{ selectedDirectionMajor?.label || '—' }}</td><td>专业下全部年级</td><td>教务组织管理岗</td>
                  <td><StatusTag :type="d.status === 'ACTIVE' ? 'success' : 'default'"
                                 :label="d.status === 'ACTIVE' ? '启用' : '停用'" dot /></td>
                  <td>
                    <button v-if="d.status === 'ACTIVE'" class="mp-link" :disabled="!canManage || busy" @click="openDirectionEdit(d)">编辑</button>
                    <button v-if="d.status === 'ACTIVE'" class="mp-link aa-danger" :disabled="!canManage || busy"
                            @click="disableDirection(d)">停用</button>
                    <span v-else class="aa-note-inline">历史记录</span>
                  </td>
                </tr>
              </tbody>
            </table>
</div>
            <AppPagination v-if="!directions.error && directions.total" :total="directions.total" :page="directions.page"
                           :page-size="directions.pageSize" :disabled="directions.loading || busy" @change="pageDirections" />
          </template>
        </div>
      </section>

      <!-- 班级学生（07号卡：只读增强，独立于「行政班」页签内既有名册弹窗） -->
      <section v-else-if="tab === 'students'" class="mp-card">
        <div class="mp-card__body">
          <div class="aa-filter">
            <AppClassPicker v-model="studentsFilterClassId" placeholder="请选择行政班" @change="searchStudents"
                            :options="classOptions" />
            <AppTextInput v-model="studentsKeyword" placeholder="学号或姓名" @keyup.enter="searchStudents" />
            <AppButton :disabled="!studentsFilterClassId" @click="searchStudents">查询</AppButton>
          </div>
          <EmptyState v-if="!studentsFilterClassId" title="请选择行政班" description="选择上方行政班查看该班学生名册" />
          <template v-else>
            <ErrorState v-if="studentsList.error" :description="studentsList.error" @retry="reloadStudentsList" />
            <LoadingState v-else-if="studentsList.loading" />
            <EmptyState v-else-if="!studentsList.rows.length" title="暂无符合条件的学生" description="可调整班级或搜索条件后重试。" />
            <div class="aa-table-scroll" role="region" aria-label="数据表格，可横向滚动" tabindex="0" v-else>
<table  class="mp-audit">
              <thead><tr><th>学号</th><th>姓名</th><th>当前班级</th><th>专业年级</th><th>学籍状态</th><th>手机号</th></tr></thead>
              <tbody>
                <tr v-for="s in studentsList.rows" :key="s.id">
                  <td>{{ s.studentNo }}</td><td>{{ s.realName }}</td><td>{{ s.className || '未分班' }}</td>
                  <td>{{ s.majorName || '—' }} · {{ s.grade || '年级待核' }}</td>
                  <td>{{ studentStatusLabel(s.studentStatus) }}</td><td>{{ s.phoneMasked || '—' }}</td>
                </tr>
              </tbody>
            </table>
</div>
            <AppPagination v-if="!studentsList.error && studentsList.total" :total="studentsList.total" :page="studentsList.page" :page-size="studentsList.pageSize" :disabled="studentsList.loading" @change="pageStudents" />
          </template>
          <p class="mp-note">本页仅只读查看，手机号脱敏展示；批量组织调整请使用「班级调整」页签。</p>
        </div>
      </section>

      <!-- 班级调整申请单（08号卡：行政班层面批量组织调整） -->
      <section v-else-if="tab === 'adjust'" class="mp-card">
        <div class="mp-card__body">
          <div class="aa-list-heading"><h2>班级调整</h2><span>发起申请 → 核对影响 → 确认执行</span></div>
          <div class="aa-transfer-steps" aria-label="学生转班流程">
            <span class="is-active"><b>1</b>确认学生</span><i></i><span><b>2</b>核对前后班级</span><i></i><span><b>3</b>执行并回执</span><i></i><span><b>4</b>返回原名册</span>
          </div>
          <section class="aa-transfer-launcher">
            <div>
              <strong>学生班级归属调整</strong>
              <p>先锁定原班级和学生，再进入正式影响核对。确认时使用当前对象 ID 与最新版本，避免锁错对象。</p>
            </div>
            <div class="aa-filter">
              <AppClassPicker v-model="studentsFilterClassId" placeholder="选择原班级" :options="classOptions" :disabled="busy" @change="searchAdjustStudents" />
              <AppSelect v-model="adjustStudentId" placeholder="选择学生" :options="adjustStudentOptions" :disabled="busy || studentsList.loading || !studentsFilterClassId" />
              <AppButton variant="primary" :disabled="busy || !adjustStudentId" @click="openSelectedStudentTransfer">进入转班核对</AppButton>
            </div>
            <AppInlineAlert v-if="studentsList.error" type="danger" :description="studentsList.error" />
            <p v-else-if="studentsFilterClassId" class="mp-note">已按原班级加载 {{ studentsList.total }} 名学生；办理结果会返回学生、原班级、目标班级、生效时间和原因。</p>
          </section>
          <div class="aa-adjust-divider"><span>班级层级批量调整申请</span></div>
          <div class="aa-filter">
            <AppSelect v-model="adjustments.filters.status" :placeholder="''" :disabled="busy" @change="searchAdjustments"
                       :options="[{ value: '', label: '全部状态' }, { value: 'DRAFT', label: '草稿' }, { value: 'CHECKED', label: '已核对' }, { value: 'EXECUTED', label: '已执行' }, { value: 'CANCELLED', label: '已撤销' }]" />
            <AppSelect v-model="adjustments.filters.adjustType" :placeholder="''" :disabled="busy" @change="searchAdjustments"
                       :options="[{ value: '', label: '全部类型' }, { value: 'MERGE', label: '合班登记' }, { value: 'SPLIT', label: '拆班登记' }, { value: 'DISBAND', label: '停用撤销' }, { value: 'GRADUATE_CLEAR', label: '毕业清班' }]" />
            <AppButton :disabled="busy" @click="searchAdjustments">查询</AppButton>
            <AppButton v-if="canManage" variant="primary" :disabled="busy || optionsLoading || !!optionsError" @click="openAdjustCreate">发起调整</AppButton>
          </div>
          <ErrorState v-if="adjustments.error" :description="adjustments.error" @retry="reloadAdjustments" />
          <LoadingState v-else-if="adjustments.loading" />
          <EmptyState v-else-if="!adjustments.rows.length" title="暂无符合条件的调整申请" :description="canManage ? '可调整筛选条件，或发起新的申请。' : '当前范围内暂无可查看的申请。'" />
          <div v-else class="aa-org-table">
          <div class="aa-table-scroll" role="region" aria-label="数据表格，可横向滚动" tabindex="0">
<table class="mp-audit">
            <thead><tr><th>类型</th><th>来源班级</th><th>目标班级</th><th>理由</th><th>状态</th><th>发起时间</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="a in adjustments.rows" :key="a.id">
                <td>{{ adjustTypeLabel(a.adjustType) }}</td>
                <td>{{ a.fromClassNames || '—' }}</td>
                <td>{{ a.toClassName || '—' }}</td>
                <td>{{ a.reason }}</td>
                <td><StatusTag :type="adjustStatusType(a.status)" :label="adjustStatusLabel(a.status)" dot /></td>
                <td>{{ displayTime(a.createdAt) }}</td>
                <td><div class="aa-org-actions">
                  <button v-if="a.status === 'DRAFT' && canManage" class="mp-link" :disabled="busy" @click="precheckAdjustment(a)">前置核对</button>
                  <button v-if="a.status === 'CHECKED' && canManage" class="mp-link" :disabled="busy" @click="precheckAdjustment(a)">重新核对</button>
                  <button v-if="a.checkResult" class="mp-link" :disabled="busy" @click="viewCheckResult(a)">{{ a.status === 'EXECUTED' ? '执行结果' : a.status === 'CANCELLED' ? '历史核对' : a.checkResult.blocked ? '查看待处理项' : '核对结果' }}</button>
                  <button v-if="a.status === 'CHECKED' && canManage" class="mp-link" :disabled="busy || isAdjustBlocked(a)"
                          @click="confirmAdjustAction(a, 'execute')">确认执行</button>
                  <button v-if="['DRAFT','CHECKED'].includes(a.status) && canManage" class="mp-link aa-danger"
                          :disabled="busy" @click="confirmAdjustAction(a, 'cancel')">撤销</button>
                </div></td>
              </tr>
            </tbody>
          </table>
</div>
          </div>
          <AppPagination v-if="!adjustments.error && adjustments.total" :total="adjustments.total" :page="adjustments.page" :page-size="adjustments.pageSize" :disabled="adjustments.loading || busy" @change="pageAdjustments" />
          <p class="mp-note">
            合班、停用和毕业清班前，先处理来源班级中的在籍学生与未归档学期的教学任务。学生转班可从「行政班 → 学生 → 调整班级」办理。
          </p>
        </div>
      </section>

      <!-- 列表类页签（学院/专业/行政班/年级/教学班/审计/班级学生）-->
      <template v-else>
        <div :class="{ 'aa-org-ledger-layout': masterDetailTabs.includes(tab) }">
        <aside v-if="masterDetailTabs.includes(tab)" class="aa-org-master">
          <div class="aa-org-master__head"><strong>组织与引用</strong><span>{{ treeNodeCount }} 个组织节点</span></div>
          <LoadingState v-if="optionsLoading" />
          <ul v-else class="aa-org-master__tree">
            <li v-for="college in tree.colleges || []" :key="college.id">
              <strong>{{ college.collegeName }}</strong>
              <ul><li v-for="major in college.majors || []" :key="major.id"><span>{{ major.majorName }}</span><small>{{ (major.classes || []).length }} 个班</small></li></ul>
            </li>
          </ul>
        </aside>
        <section class="mp-card aa-org-list">
        <AppInlineAlert v-if="masterDetailTabs.includes(tab)" type="info" :description="pageMeta.notice" />
        <div class="aa-list-heading"><h2>{{ tabLabel }}列表</h2><span v-if="!loading && !error">共 {{ pagination.total }} 条</span></div>
        <div v-if="['college','major','class','grade','teaching'].includes(tab)" class="aa-filter">
          <AppCollegePicker v-if="tab === 'major'" v-model="filters.collegeId" placeholder="全部学院" @change="search"
                            :options="collegeOptions" clearable />
          <AppMajorPicker v-if="['class','grade'].includes(tab)" v-model="filters.majorId" placeholder="全部专业" @change="search"
                          :options="majorOptions" clearable />
          <AppTermEntityPicker v-if="tab === 'teaching' && canViewTerms" v-model="filters.termId" placeholder="全部学期" @change="search" />
          <AppTextInput v-if="tab !== 'grade'" v-model="filters.keyword" :placeholder="tab === 'class' ? '班级名称或编号' : tab === 'teaching' ? '教学班或课程名称' : '名称或编码'" @keyup.enter="search" />
          <AppButton :disabled="busy" @click="search">查询</AppButton>
          <AppButton variant="ghost" :disabled="busy" @click="resetFilters">重置</AppButton>
        </div>

        <ErrorState v-if="error" :description="error" @retry="reload" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" :title="'暂无符合条件的' + tabLabel" :description="canCreate ? '可调整筛选条件，或新建记录。' : '当前范围内暂无可查看的数据。'" />
        <DataTable
          v-else
          :columns="columns"
          :rows="rows"
          :row-key="tab === 'grade' ? 'grade' : 'id'"
          :pagination="tab === 'grade' ? undefined : pagination"
          @page-change="onPageChange"
        >
          <template #cell-trainingLevel="{ row }">{{ trainingLevelLabel(row.trainingLevel) }}</template>
          <template #cell-referenceStatus="{ row }"><StatusTag :type="row.referenceStatus === 'IN_USE' ? 'warning' : 'success'" :label="row.referenceStatus === 'IN_USE' ? '已有正式引用' : '暂无正式引用'" dot /></template>
          <template #cell-majorNames="{ row }">{{ (row.majorNames || []).join('、') || '—' }}</template>
          <template #cell-teacherNames="{ row }">{{ (row.teacherNames || []).join('、') || '待配置' }}</template>
          <template #cell-rosterStatus="{ row }"><StatusTag :type="row.rosterStatus === 'LOCKED' ? 'success' : 'warning'" :label="row.rosterStatus === 'LOCKED' ? `正式名单 V${row.rosterVersion}` : '名单待正式化'" dot /></template>
          <template #cell-secretaryId="{ row }">
            <span>{{ row.secretaryId ? (row.secretaryName || '绑定账号已不可用') : '未绑定' }}</span>
            <StatusTag v-if="row.secretaryId && row.secretaryStatus !== 'ACTIVE'" type="warning" :label="secretaryStatusLabel(row.secretaryStatus)" />
          </template>
          <template #cell-bizType="{ row }">{{ auditObjectLabel(row.bizType) }}</template>
          <template #cell-action="{ row }">{{ auditActionLabel(row.action) }}</template>
          <template #cell-occurredAt="{ row }">{{ displayTime(row.occurredAt) }}</template>
          <template #cell-courses="{ row }">{{ (row.courses || []).join('、') || '—' }}</template>
          <template #cell-isMerged="{ row }">{{ row.isMerged ? '合班' : '普通教学班' }}</template>
          <template #cell-expectedStudents="{ row }">{{ row.expectedStudents ?? '—' }} <span class="mp-note">{{ row.teachingClassId ? '班额' : '预计' }}</span></template>
          <template #cell-enrollStatus="{ row }">
            <StatusTag :type="row.enrollStatus === 'ENROLLING' ? 'success' : 'default'"
                       :label="row.enrollStatus === 'ENROLLING' ? '招生中' : '停招'" dot />
          </template>
          <template #cell-classStatus="{ row }">
            <StatusTag :type="row.classStatus === 'NORMAL' ? 'success' : 'default'"
                       :label="classStatusLabel(row.classStatus)" dot />
          </template>
          <template #cell-actions="{ row }">
            <div class="aa-org-actions">
            <template v-if="tab === 'college' && canManage">
              <button class="mp-link" :disabled="busy" @click="openEdit(row)">编辑</button>
              <button class="mp-link" :disabled="busy" @click="openSecretary(row)">教学秘书</button>
              <button class="mp-link aa-danger" :disabled="busy" @click="openDelete(row)">删除</button>
            </template>
            <template v-else-if="tab === 'major' && canManage">
              <button v-if="canManage" class="mp-link" :disabled="busy" @click="openEdit(row)">编辑</button>
              <button v-if="canManage" class="mp-link aa-danger" :disabled="busy" @click="openDelete(row)">删除</button>
            </template>
            <template v-else-if="tab === 'class'">
              <button v-if="canManage" class="mp-link" :disabled="busy" @click="openEdit(row)">编辑</button>
              <button class="mp-link" :disabled="busy" @click="openStudents(row)">学生</button>
              <button v-if="canManage" class="mp-link aa-danger" :disabled="busy" @click="openDelete(row)">删除</button>
            </template>
            <template v-else-if="tab === 'teaching'">
              <button v-if="canViewTeachingTasks" class="mp-link" @click="openTeachingBatch(row)">查看教学任务</button>
              <span v-else class="mp-note">只读</span>
            </template>
            <span v-else-if="!canManage" class="mp-note">只读</span>
            </div>
          </template>
        </DataTable>
        </section>
        </div>
      </template>

      <p v-if="['college','major','class'].includes(tab)" class="mp-note">
        按学院、专业、行政班的顺序建立组织。删除前需处理下级组织、关联学生与未归档教学任务，变更可在「变更审计」中查看。
      </p>
      <p v-if="tab === 'teaching'" class="mp-note">按学期查看教学班，教学安排请从对应的教学任务中维护。</p>
    </div>

    <!-- 新建 / 编辑 表单 -->
    <AppDrawer :visible="form.visible" :title="(form.mode === 'create' ? '新建' : '编辑') + formLabel" mode="modal" size="medium" @update:visible="closeForm">
      <AppInlineAlert v-if="form.error" type="danger" :description="form.error" />
      <fieldset class="aa-form aa-org-form" :disabled="form.submitting">
        <AppFormItem v-for="f in formFields" :key="f.key" :label="f.label" :required="!!f.required">
          <AppCollegePicker v-if="f.picker === 'college'" v-model="form.model[f.key]" :options="f.options || []" :disabled="form.submitting" />
          <AppMajorPicker v-else-if="f.picker === 'major'" v-model="form.model[f.key]" :options="f.options || []" :disabled="form.submitting" />
          <AppTeacherPicker v-else-if="f.picker === 'teacher'" v-model="form.model[f.key]" placeholder="选填，选择教师" :disabled="form.submitting" />
          <AppSelect v-else-if="f.type === 'select'" v-model="form.model[f.key]" :options="f.options || []" />
          <AppNumberInput v-else-if="f.type === 'number'" v-model="form.model[f.key]" :min="f.min" :max="f.max" :step="1" />
          <AppTextInput v-else v-model="form.model[f.key]" :placeholder="f.placeholder || ''" :maxlength="f.maxlength || 200" />
        </AppFormItem>
        <AppFormItem v-if="parentChanged || classStateChanged" label="调整原因" required>
          <AppTextInput v-model="form.model.reason" placeholder="说明调整原因，至少 5 个字" :maxlength="500" />
        </AppFormItem>
        <section v-if="classStateChanged" class="aa-class-state-check">
          <strong>{{ classStatusLabel(form.originalClassStatus) }} → {{ classStatusLabel(form.model.classStatus) }}</strong>
          <p class="mp-note">班级状态影响后续教学安排；学生学籍和历史名单保持原值。</p>
          <template v-if="form.statePreview">
            <p>在籍学生 {{ form.statePreview.activeStudentCount }} 人 · 未归档教学任务 {{ form.statePreview.openTaskCount }} 条</p>
            <AppInlineAlert v-for="message in form.statePreview.blockers" :key="message" type="warning" :description="message" />
            <AppInlineAlert v-if="!form.statePreview.blocked" type="success" description="核对通过，可以保存本次变更。保存时会再次核验当前引用。" />
          </template>
          <p v-else class="mp-note">先核对班级成员、教学任务及组织状态，再确认保存。</p>
        </section>
      </fieldset>
      <template #footer>
        <AppButton :disabled="form.submitting" @click="closeForm">取消</AppButton>
        <AppButton v-if="classStateChanged" :loading="form.statePreviewing" :disabled="form.submitting" @click="previewClassState">核对状态影响</AppButton>
        <AppButton variant="primary" :loading="form.submitting" :disabled="!canManage || form.needsReload || (classStateChanged && !classStateReady)" @click="submitForm">{{ classStateChanged ? '确认并保存' : '保存' }}</AppButton>
      </template>
    </AppDrawer>

    <!-- 教学秘书绑定 -->
    <AppDrawer :visible="secretary.visible" :title="'教学秘书绑定 · ' + (secretary.row && secretary.row.collegeName)" mode="modal" size="medium" @update:visible="closeSecretary">
      <div class="aa-form">
        <template v-if="secretary.receipt">
          <AppInlineAlert type="success" :description="secretary.receipt.secretaryId ? '教学秘书绑定已更新' : '学院教学秘书绑定已解除'" />
          <p class="mp-note">{{ secretary.receipt.collegeName }} · {{ secretary.receipt.secretaryName || '未绑定教学秘书' }}</p>
        </template>
        <template v-else>
          <p class="mp-note">当前绑定：{{ secretary.row?.secretaryId ? (secretary.row.secretaryName || '账号已不可用') : '未绑定' }}</p>
          <AppInlineAlert v-if="secretary.row?.secretaryId && secretary.row.secretaryStatus !== 'ACTIVE'" type="warning"
                          :description="secretaryStatusLabel(secretary.row.secretaryStatus) + '，请更换人员或解除学院绑定。'" />
          <AppInlineAlert v-if="secretary.error" type="danger" :description="secretary.error" />
          <AppFormItem v-if="!secretary.review" label="新的教学秘书">
            <AppTeacherPicker :key="secretary.row?.id" v-model="secretary.secretaryId" placeholder="按姓名或账号选择；留空解除绑定"
                              :remote-search="searchSecretaryCandidates" :resolve-by-value="resolveSecretaryCandidate" :disabled="secretary.submitting || secretary.reviewing"
                              data-scope-hint="本校启用的教职工账号；审核权限由学校岗位配置决定" />
          </AppFormItem>
          <AppInlineAlert v-else type="info" :description="secretary.review.message" />
        </template>
        <p class="mp-note">后续审批按学院绑定与现有岗位配置选择受理人；已生成的待办保留原受理人。解除学院绑定后，仍有效的任职继续适用。</p>
      </div>
      <template #footer>
        <AppButton v-if="secretary.receipt" variant="primary" @click="closeSecretary">完成</AppButton>
        <template v-else>
          <AppButton :disabled="secretary.submitting" @click="closeSecretary">取消</AppButton>
          <AppButton v-if="secretary.review" :disabled="secretary.submitting" @click="invalidateSecretaryReview">返回修改</AppButton>
          <AppButton v-if="secretary.review" variant="primary" :loading="secretary.submitting" :disabled="!canManage || secretary.needsReload" @click="submitSecretary">{{ secretary.review.secretaryId ? '确认绑定' : '确认解除绑定' }}</AppButton>
          <AppButton v-else variant="primary" :loading="secretary.reviewing" :disabled="!canManage || !secretaryChanged || secretary.needsReload" @click="reviewSecretary">核对变更</AppButton>
        </template>
      </template>
    </AppDrawer>

    <!-- 班级学生抽屉 -->
    <AppDrawer :visible="students.visible" :title="'班级学生 · ' + students.className" mode="modal" size="xlarge" @update:visible="students.visible = $event">
      <ErrorState v-if="students.error" :description="students.error" @retry="reloadStudentDrawer" />
      <LoadingState v-else-if="students.loading" />
      <EmptyState v-else-if="!students.rows.length" title="该班暂无在册学生" />
      <div class="aa-table-scroll" role="region" aria-label="数据表格，可横向滚动" tabindex="0" v-else>
<table  class="mp-audit">
        <thead><tr><th>学号</th><th>姓名</th><th>学籍状态</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="s in students.rows" :key="s.id">
            <td>{{ s.studentNo }}</td><td>{{ s.realName }}</td><td>{{ studentStatusLabel(s.studentStatus) }}</td>
            <td><button v-if="canManage" class="mp-link" :disabled="busy" @click="openAdjust(s)">调整班级</button><span v-else class="mp-note">只读</span></td>
          </tr>
        </tbody>
      </table>
</div>
      <AppPagination v-if="!students.error && students.total" :total="students.total" :page="students.page" :page-size="students.pageSize" :disabled="students.loading || busy" @change="pageStudentDrawer" />
      <template #footer>
        <AppButton @click="students.visible = false">关闭</AppButton>
      </template>
    </AppDrawer>

    <!-- 班级调整 -->
    <AppDrawer :visible="adjust.visible" :title="(adjust.receipt ? '转班结果 · ' : '学生转班 · ') + (adjust.student?.realName || '')" mode="modal" size="large" @update:visible="closeAdjust">
      <template v-if="adjust.receipt">
        <AppInlineAlert type="success" :description="`${adjust.receipt.studentName} 已从${adjust.receipt.fromClassName || '未分班'}转入${adjust.receipt.toClassName}。班级名册与学籍归属已更新。`" />
        <p class="mp-note">{{ displayTime(adjust.receipt.effectiveAt) }} 生效 · {{ adjust.receipt.reason || '教务班级归属调整' }}</p>
        <p class="mp-note">学生学籍状态与年级保持原值。课程与教学班名单沿各自正式业务办理。</p>
      </template>
      <fieldset v-else class="aa-form aa-org-form" :disabled="adjust.submitting">
        <p class="mp-note">{{ adjust.student?.studentNo }} · 当前班级：{{ adjust.origin?.className || '未分班' }} · {{ studentStatusLabel(adjust.student?.studentStatus) }}</p>
        <AppFormItem label="目标班级" required>
          <AppClassPicker v-model="adjust.targetClassId" placeholder="请选择目标班级" :options="classOptions.filter(option => option.value !== String(adjust.student?.classId || ''))" :disabled="adjust.submitting" @change="invalidateTransferPreview" />
        </AppFormItem>
        <AppFormItem label="调整原因" required>
          <AppTextInput v-model="adjust.reason" placeholder="说明转班原因，至少 5 个字" :maxlength="500" />
        </AppFormItem>
        <LoadingState v-if="adjust.previewing" />
        <template v-else-if="adjust.preview">
          <div class="aa-transfer-summary">
            <strong>{{ adjust.preview.target.className }}</strong>
            <span>{{ adjust.preview.target.collegeName }} · {{ adjust.preview.target.majorName }}</span>
            <span>在籍人数 {{ adjust.preview.target.studentCount }} → {{ adjust.preview.target.afterStudentCount }} · 编制 {{ adjust.preview.target.capacity ?? '未设置' }}</span>
          </div>
          <AppInlineAlert v-for="message in adjust.preview.warnings" :key="message" type="warning" :description="message" />
          <AppInlineAlert type="info" description="确认后立即更新学生的班级、专业和学院归属，保留学籍变更记录；学生学籍状态与年级保持原值。" />
        </template>
        <AppInlineAlert v-if="adjust.error" type="danger" :description="adjust.error" />
      </fieldset>
      <template #footer>
        <AppButton :disabled="adjust.submitting" @click="closeAdjust">{{ adjust.receipt ? '关闭' : '返回名册' }}</AppButton>
        <AppButton v-if="adjust.receipt" variant="primary" @click="viewTransferredClass">查看目标班名册</AppButton>
        <AppButton v-else-if="!adjust.preview" variant="primary" :disabled="!adjust.targetClassId || adjust.previewing || adjust.submitting" :loading="adjust.previewing" @click="previewTransfer">核对转班</AppButton>
        <AppButton v-else variant="primary" :loading="adjust.submitting" @click="submitAdjust">确认转班</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="del.visible"
      type="danger"
      :title="'删除' + tabLabel"
      :message="del.message + (del.error ? ' 当前无法删除：' + del.error : '')"
      confirm-text="确认删除"
      :submitting="del.submitting"
      @confirm="submitDelete"
    />

    <!-- 专业方向 · 新建/编辑 -->
    <AppDrawer :visible="directionForm.visible" :title="(directionForm.mode === 'create' ? '新建' : '编辑') + '专业方向'" mode="modal" size="medium" @update:visible="closeDirectionForm">
      <div class="aa-form">
        <p class="mp-note">所属专业：{{ directionForm.majorName }}</p>
        <AppInlineAlert v-if="directionForm.error" type="danger" :description="directionForm.error" />
        <AppFormItem label="方向名称" required>
          <AppTextInput v-model="directionForm.model.directionName" :maxlength="200" :disabled="directionForm.submitting" placeholder="如 Web开发方向" />
        </AppFormItem>
        <AppFormItem label="编码">
          <AppTextInput v-model="directionForm.model.code" :maxlength="50" :disabled="directionForm.submitting" placeholder="选填，专业内唯一，最多50字" />
        </AppFormItem>
      </div>
      <template #footer>
        <AppButton :disabled="directionForm.submitting" @click="closeDirectionForm">取消</AppButton>
        <AppButton variant="primary" :loading="directionForm.submitting" :disabled="!canManage || !directionToggle.loaded || !directionToggle.enabled || directionForm.needsReload" @click="submitDirectionForm">保存</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog :visible="directionConfirm.visible" @update:visible="closeDirectionAction"
                      type="warning" :title="directionConfirm.title" :message="directionConfirm.message"
                      :confirm-text="directionConfirm.enabled ? '确认启用' : '确认停用'"
                      :submitting="directionConfirm.submitting" :confirm-disabled="directionConfirm.needsReload" @confirm="submitDirectionAction">
      <AppInlineAlert v-if="directionConfirm.error" type="danger" :description="directionConfirm.error" />
    </AppConfirmDialog>

    <!-- 班级调整申请单 · 发起 -->
    <AppDrawer :visible="adjustCreateForm.visible" title="发起班级调整" mode="modal" size="large" @update:visible="closeAdjustCreate">
      <fieldset class="aa-form aa-org-form" :disabled="adjustCreateForm.submitting">
        <AppFormItem label="调整类型" required>
          <AppSelect v-model="adjustCreateForm.model.adjustType" :options="[
            { value: 'MERGE', label: '合班登记' }, { value: 'SPLIT', label: '拆班登记' },
            { value: 'DISBAND', label: '停用撤销' }, { value: 'GRADUATE_CLEAR', label: '毕业清班' }]" />
        </AppFormItem>
        <AppInlineAlert type="info" :description="adjustEffect(adjustCreateForm.model.adjustType)" />
        <AppFormItem label="来源班级" required hint="可搜索并选择多个班级">
          <AppClassPicker v-model="adjustCreateForm.model.fromClassIds" :options="classOptions" multiple placeholder="请选择来源班级" :disabled="adjustCreateForm.submitting" />
        </AppFormItem>
        <AppFormItem v-if="adjustCreateForm.model.adjustType === 'MERGE'" label="目标班级" required>
          <AppClassPicker v-model="adjustCreateForm.model.toClassId" placeholder="请选择目标班级" :options="classOptions" :disabled="adjustCreateForm.submitting" />
        </AppFormItem>
        <AppFormItem label="调整理由" required>
          <AppTextInput v-model="adjustCreateForm.model.reason" placeholder="说明调整原因，至少 5 个字" :maxlength="1000" />
        </AppFormItem>
        <AppInlineAlert v-if="adjustCreateForm.error" type="danger" :description="adjustCreateForm.error" />
      </fieldset>
      <template #footer>
        <AppButton :disabled="adjustCreateForm.submitting" @click="closeAdjustCreate">取消</AppButton>
        <AppButton variant="primary" :loading="adjustCreateForm.submitting" @click="submitAdjustCreate">发起并核对</AppButton>
      </template>
    </AppDrawer>

    <!-- 班级调整申请单 · 核对结果 -->
    <AppDrawer :visible="adjustCheckResult.visible" :title="adjustCheckResult.row?.status === 'EXECUTED' ? '班级调整结果' : adjustCheckResult.row?.status === 'CANCELLED' ? '已撤销申请 · 历史核对' : '班级调整核对'" mode="modal" size="xlarge" @update:visible="closeAdjustResult">
      <template v-if="adjustCheckResult.row && adjustCheckResult.row.checkResult">
        <AppInlineAlert :type="adjustCheckResult.row.status === 'EXECUTED' ? 'success' : 'info'" :description="adjustResultMessage(adjustCheckResult.row)" />
        <p class="mp-note">{{ adjustTypeLabel(adjustCheckResult.row.adjustType) }} · {{ adjustCheckResult.row.fromClassNames }}<span v-if="adjustCheckResult.row.toClassName"> → {{ adjustCheckResult.row.toClassName }}</span></p>
        <p v-if="adjustCheckResult.row.status === 'CHECKED'">
          <StatusTag :type="adjustCheckResult.row.checkResult.blocked ? 'danger' : 'success'"
                     :label="adjustCheckResult.row.checkResult.blocked ? '存在待处理事项' : '核对通过'" dot />
          <span class="mp-note">核对于 {{ displayTime(adjustCheckResult.row.checkedAt) }}，24 小时内有效；执行时会重新核验。</span>
        </p>
        <p v-else-if="adjustCheckResult.row.checkResult.execution" class="mp-note">已于 {{ displayTime(adjustCheckResult.row.checkResult.execution.executedAt) }} 完成，变更 {{ adjustCheckResult.row.checkResult.execution.changedClassCount }} 个班级的状态。</p>
        <p v-else class="mp-note">核对时间：{{ displayTime(adjustCheckResult.row.checkedAt) }}。以下为当时的核对记录。</p>
        <div class="aa-table-scroll" role="region" aria-label="数据表格，可横向滚动" tabindex="0">
<table class="mp-audit">
          <thead><tr><th>班级</th><th>在籍学生</th><th>未归档教学任务</th><th>核对说明</th></tr></thead>
          <tbody>
            <tr v-for="ref in adjustCheckResult.row.checkResult.refs" :key="ref.classId">
              <td>{{ ref.className || '班级已不可用' }}<span v-if="ref.isTarget" class="mp-note"> · 目标班级</span></td><td>{{ ref.activeStudentCount }}</td><td>{{ ref.openTaskCount ?? '待重新核对' }}</td>
              <td><ul v-if="ref.blockers?.length" class="aa-org-blockers"><li v-for="message in ref.blockers" :key="message">{{ message }}</li></ul><span v-else>无待处理事项</span></td>
            </tr>
          </tbody>
        </table>
</div>
      </template>
      <template #footer>
        <AppButton :disabled="busy" @click="closeAdjustResult">关闭</AppButton>
        <AppButton v-if="canManage && adjustCheckResult.row?.status === 'CHECKED'" :disabled="busy" @click="precheckAdjustment(adjustCheckResult.row)">重新核对</AppButton>
        <AppButton v-if="canManage && adjustCheckResult.row?.status === 'CHECKED'" variant="primary" :disabled="busy || isAdjustBlocked(adjustCheckResult.row)" @click="confirmAdjustAction(adjustCheckResult.row, 'execute')">确认执行</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      :visible="adjustActionConfirm.visible"
      @update:visible="closeAdjustAction"
      :type="adjustActionConfirm.action === 'cancel' ? 'danger' : 'warning'"
      :title="adjustActionConfirm.title"
      :message="adjustActionConfirm.message"
      :confirm-text="adjustActionConfirm.action === 'execute' ? '确认执行' : '确认撤销'"
      :submitting="adjustActionConfirm.submitting"
      :confirm-disabled="adjustActionConfirm.needsRecheck"
      @confirm="submitAdjustAction"
    >
      <AppInlineAlert v-if="adjustActionConfirm.error" type="danger" :description="adjustActionConfirm.error" />
      <p v-if="adjustActionConfirm.needsRecheck" class="mp-note">请关闭此窗口，在列表中重新核对最新结果。</p>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/**
 * 学院专业班级管理控制台（/admin/academic-affairs/orgs）。
 * 生产级：数据全部来自真实后端 /academic-affairs/orgs/*，无 mock；页面三态 + 二次确认 + 越权由后端裁决。
 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import AaOrgReferencePanel from '@/modules/academicAffairs/components/AaOrgReferencePanel.vue'
import { AppInlineAlert, AppSelect, AppFormItem, AppTextInput, AppNumberInput, AppTeacherPicker, AppCollegePicker, AppMajorPicker, AppClassPicker, AppTermEntityPicker, AppPagination } from '@/components/common'
import { academicAffairsOrgApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { matchPermission } from '@/config/navPlan'
import { ACADEMIC_STUDENT_STATUS_LABELS } from '@/modules/academicAffairs/config/academicStudentLabels'
import { toast } from '@/utils/toast'
import { formatDateTime } from '@/utils/dateUtils'

const CLASS_STATUS = { NORMAL: '在读', GRADUATED: '已毕业', DISBANDED: '已解散' }

export default {
  name: 'AaOrgConsole',
  components: { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppButton, AppDrawer, AppConfirmDialog, AaOrgReferencePanel, AppInlineAlert, AppSelect, AppFormItem, AppTextInput, AppNumberInput, AppTeacherPicker, AppCollegePicker, AppMajorPicker, AppClassPicker, AppTermEntityPicker, AppPagination },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      tab: 'college',
      tabs: [
        { key: 'college', label: '学院' }, { key: 'major', label: '专业' }, { key: 'class', label: '行政班' },
        { key: 'grade', label: '年级' }, { key: 'teaching', label: '教学班' },
        { key: 'direction', label: '专业方向' }, { key: 'students', label: '班级学生' }, { key: 'adjust', label: '班级调整' },
        { key: 'tree', label: '组织核对' }, { key: 'stats', label: '统计' }, { key: 'audit', label: '变更审计' }
      ],
      loading: false, error: '', rows: [],
      optionsLoading: false, optionsError: '', requestVersions: { list: 0, options: 0, students: 0, studentDrawer: 0, tree: 0, stats: 0, adjustments: 0, transfer: 0, classState: 0, directionToggle: 0, directions: 0, secretary: 0 }, actionBusy: false,
      pagination: { page: 1, pageSize: 10, total: 0 },
      filters: { collegeId: '', majorId: '', keyword: '', termId: '' },
      collegeOptions: [], majorOptions: [], classOptions: [],
      stats: {}, statsLoading: false, statsError: '',
      tree: { colleges: [] }, treeLoading: false, treeError: '',
      form: { visible: false, mode: 'create', kind: 'college', submitting: false, model: {}, originalParentId: '', error: '' },
      secretary: { visible: false, submitting: false, row: null, secretaryId: '', reviewing: false, review: null, receipt: null, error: '', needsReload: false },
      students: { visible: false, loading: false, error: '', rows: [], className: '', classId: null, page: 1, pageSize: 20, total: 0 },
      adjust: { visible: false, submitting: false, student: null, targetClassId: '', reason: '', previewing: false, preview: null, receipt: null, error: '', origin: null },
      del: { visible: false, submitting: false, row: null, message: '' },
      // 专业方向（06号卡）
      directionToggle: { enabled: false, version: 0, loading: false, loaded: false, error: '' },
      directionMajorId: '',
      directions: { rows: [], loading: false, error: '', page: 1, pageSize: 20, total: 0 },
      directionForm: { visible: false, mode: 'create', submitting: false, model: {}, majorId: '', majorName: '', error: '', needsReload: false },
      directionConfirm: { visible: false, submitting: false, kind: '', title: '', message: '', error: '', needsReload: false },
      // 班级学生（07号卡：只读增强，独立于「行政班」页签内既有的名册弹窗）
      studentsFilterClassId: '',
      studentsKeyword: '',
      studentsList: { rows: [], loading: false, error: '', page: 1, pageSize: 20, total: 0 },
      adjustStudentId: '',
      // 班级调整申请单（08号卡：批量组织调整，区别于「行政班/学生」内既有的个体转班弹窗）
      adjustments: {
        rows: [], loading: false, error: '', page: 1, pageSize: 20, total: 0,
        filters: { status: '', adjustType: '' }
      },
      adjustCreateForm: {
        visible: false, submitting: false, error: '',
        model: { adjustType: 'MERGE', fromClassIds: [], toClassId: '', reason: '' }
      },
      adjustCheckResult: { visible: false, row: null },
      adjustActionConfirm: { visible: false, submitting: false, title: '', message: '', action: null, row: null, error: '', needsRecheck: false }
    }
  },
  computed: {
    pageMeta() {
      return {
        college: { title: '学院管理', subtitle: '维护学院稳定身份、负责人和下游引用。', notice: '学院代码作为稳定身份参与专业、权限和统计关联；调整名称不会改变既有对象 ID。' },
        major: { title: '专业管理', subtitle: '按学院维护专业主档、学制和招生状态。', notice: '专业主档被培养方案、班级和招生业务引用；停招保留历史关系，不删除正式记录。' },
        grade: { title: '年级管理', subtitle: '按入学年度查看专业、班级与学生规模。', notice: '' },
        class: { title: '行政班管理', subtitle: '维护专业年级下的行政班、班主任和在班人数。', notice: '行政班连接学籍归属与教学任务；变更状态前必须核对在籍学生和未归档任务。' },
        teaching: { title: '教学班管理', subtitle: '按学期查看课程教学班、任课关系和正式名单版本。', notice: '教学班由教学任务形成；名单版本锁定后用于课表、成绩和考勤，维护入口回到对应教学任务。' },
        tree: { title: '组织核对', subtitle: '核对学院、专业、行政班的主档关系与正式引用。', notice: '' },
        stats: { title: '组织统计', subtitle: '按真实数据范围汇总学院、专业、班级与学生分布。', notice: '' },
        direction: { title: '专业方向', subtitle: '在学校启用方向粒度后维护专业下的培养方向。', notice: '' },
        students: { title: '班级学生', subtitle: '按行政班查询真实学籍名册与当前状态。', notice: '' },
        adjust: { title: '班级调整', subtitle: '围绕明确班级对象完成核对、确认、执行和结果回执。', notice: '' },
        audit: { title: '组织变更审计', subtitle: '查看组织对象的正式变更留痕。', notice: '' }
      }[this.tab] || { title: '学院专业班级', subtitle: '维护教务组织主档。', notice: '' }
    },
    masterDetailTabs() { return ['college', 'major', 'class', 'teaching'] },
    treeNodeCount() {
      return (this.tree.colleges || []).reduce((total, college) => total + 1 + (college.majors || []).reduce(
        (count, major) => count + 1 + (major.classes || []).length, 0), 0)
    },
    adjustStudentOptions() {
      return (this.studentsList.rows || []).map(student => ({
        value: String(student.id), label: `${student.studentNo} · ${student.realName}`
      }))
    },
    selectedDirectionMajor() { return this.majorOptions.find(option => String(option.value) === String(this.directionMajorId)) || null },
    roleName() { return this.ctx.currentRole?.roleName || '' },
    dataScopeName() { return this.ctx.dataScope?.scopeName || '' },
    canManage() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.org.manage') && ['SCHOOL', 'TENANT_ALL', 'COLLEGE'].includes(this.ctx.dataScope?.scope) },
    canViewTeachingTasks() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.teachingTask.view') },
    canViewTerms() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.term.view') },
    canManageSchool() { return this.canManage && ['SCHOOL', 'TENANT_ALL'].includes(this.ctx.dataScope?.scope) },
    canCreate() { return this.canManage && ['college', 'major', 'class'].includes(this.tab) && (this.tab !== 'college' || this.canManageSchool) },
    busy() { return this.actionBusy || this.form.submitting || this.secretary.submitting || this.adjust.submitting || this.del.submitting || this.directionForm.submitting || this.directionConfirm.submitting || this.adjustCreateForm.submitting || this.adjustActionConfirm.submitting },
    canWriteDirections() { return this.canManage && this.directionToggle.loaded && this.directionToggle.enabled && !!this.directionMajorId && !this.busy },
    secretaryChanged() { return String(this.secretary.secretaryId || '') !== String(this.secretary.row?.secretaryId || '') },
    tabLabel() { return (this.tabs.find((t) => t.key === this.tab) || {}).label || '' },
    formLabel() { return this.tabs.find(t => t.key === this.form.kind)?.label || '' },
    parentChanged() {
      const key = this.form.kind === 'major' ? 'collegeId' : this.form.kind === 'class' ? 'majorId' : ''
      return this.form.mode === 'edit' && !!key && String(this.form.model[key] || '') !== String(this.form.originalParentId || '')
    },
    classStateChanged() {
      return this.form.kind === 'class' && this.form.mode === 'edit' &&
        (this.form.model.classStatus || 'NORMAL') !== (this.form.originalClassStatus || 'NORMAL')
    },
    classStateReady() {
      const p = this.form.statePreview
      return !!p && !p.blocked && p.classId === String(this.form.model.id) && p.targetStatus === this.form.model.classStatus
    },
    statCards() {
      return [
        { key: 'collegeCount', label: '学院数' }, { key: 'majorCount', label: '专业数' },
        { key: 'classCount', label: '行政班数' }, { key: 'studentCount', label: '学生档案数' },
        { key: 'enrollingMajorCount', label: '招生专业数' }, { key: 'graduatedClassCount', label: '已毕业班数' }
      ]
    },
    columns() {
      const map = {
        college: [{ key: 'collegeName', title: '学院名称' }, { key: 'code', title: '学院代码' },
          { key: 'secretaryId', title: '负责人' }, { key: 'majorCount', title: '专业数' },
          { key: 'referenceStatus', title: '引用状态' }, { key: 'actions', title: '操作' }],
        major: [{ key: 'majorName', title: '专业名称' }, { key: 'collegeName', title: '所属学院' },
          { key: 'code', title: '专业代码' }, { key: 'educationYears', title: '学制' },
          { key: 'classCount', title: '行政班' }, { key: 'referenceStatus', title: '引用状态' },
          { key: 'actions', title: '操作' }],
        class: [{ key: 'className', title: '班级名称' }, { key: 'classCode', title: '班级编号' },
          { key: 'majorName', title: '专业' }, { key: 'grade', title: '年级' },
          { key: 'headTeacherName', title: '班主任' }, { key: 'studentCount', title: '在班人数' },
          { key: 'classStatus', title: '状态' }, { key: 'actions', title: '操作' }],
        grade: [{ key: 'grade', title: '年级' }, { key: 'admissionYear', title: '入学年度' },
          { key: 'expectedGraduationYear', title: '预计毕业年度' }, { key: 'majorNames', title: '关联专业' },
          { key: 'classCount', title: '班级数' }, { key: 'studentCount', title: '学生数' }],
        teaching: [{ key: 'teachingClassName', title: '教学班' }, { key: 'teachingClassCode', title: '代码' },
          { key: 'termName', title: '学期' }, { key: 'courses', title: '课程' },
          { key: 'teacherNames', title: '任课关系' }, { key: 'rosterStatus', title: '名单版本' }, { key: 'actions', title: '操作' }],
        audit: [{ key: 'occurredAt', title: '时间' }, { key: 'bizType', title: '对象' },
          { key: 'action', title: '动作' }, { key: 'operator', title: '操作人' }, { key: 'detail', title: '说明' }]
      }
      return map[this.tab] || []
    },
    formFields() {
      if (this.form.kind === 'college') {
        return [
          { key: 'collegeName', label: '学院名称', required: true, maxlength: 200 },
          { key: 'shortName', label: '简称', maxlength: 100 }, { key: 'code', label: '编码', maxlength: 50 },
          { key: 'sortOrder', label: '排序', type: 'number', min: -2147483648, max: 2147483647 }
        ]
      }
      if (this.form.kind === 'major') {
        return [
          { key: 'collegeId', label: '所属学院', picker: 'college', required: true, options: this.collegeOptions },
          { key: 'majorName', label: '专业名称', required: true },
          { key: 'code', label: '专业编码', maxlength: 50 },
          { key: 'educationYears', label: '学制（年）', type: 'number', min: 1, max: 10 },
          { key: 'trainingLevel', label: '培养层次', type: 'select', options: [
            { value: '', label: '未设置' }, { value: 'SECONDARY', label: '中职' },
            { value: 'HIGHER', label: '高职' }, { value: 'FIVE_YEAR', label: '五年制' }] },
          { key: 'direction', label: '专业方向' },
          { key: 'enrollStatus', label: '招生状态', type: 'select', options: [
            { value: 'ENROLLING', label: '招生中' }, { value: 'STOPPED', label: '停招' }] }
        ]
      }
      // class
      return [
        { key: 'majorId', label: '所属专业', picker: 'major', required: true, options: this.majorOptions },
        { key: 'className', label: '班级名称', required: true },
        { key: 'classCode', label: '班级编号' }, { key: 'grade', label: '年级', placeholder: '如 2026' },
        { key: 'capacity', label: '编制人数', type: 'number', min: 0 },
        { key: 'graduateYear', label: '应毕业年份', placeholder: '如 2029' },
        { key: 'counselorId', label: '辅导员', picker: 'teacher' },
        { key: 'headTeacherId', label: '班主任', picker: 'teacher' },
        { key: 'classStatus', label: '班级状态', type: 'select', options: [
          { value: 'NORMAL', label: '在读' }, { value: 'GRADUATED', label: '已毕业' },
          { value: 'DISBANDED', label: '已解散' }] }
      ]
    }
  },
  created() {
    const q = this.$route && this.$route.query && this.$route.query.tab
    if (q && this.tabs.some((t) => t.key === q)) this.tab = q
    this.loadOptions()
    if (this.tab === 'stats') this.loadStats()
    else if (this.tab === 'tree') this.loadTree()
    else if (this.tab === 'direction') this.loadDirectionToggle()
    else if (this.tab === 'adjust') this.reloadAdjustments()
    else if (this.tab === 'students') { /* 需先选行政班，见 reloadStudentsList */ }
    else this.reload()
  },
  watch: {
    'form.model.classStatus'() { this.invalidateClassStatePreview() },
    'secretary.secretaryId'() { this.invalidateSecretaryReview() },
    '$route.query.tab'(v) {
      this.switchTab(this.tabs.some(t => t.key === v) ? v : 'college')
    }
  },
  beforeUnmount() { this.invalidateReads(true) },
  beforeRouteUpdate(to, from, next) { if (this.busy) { toast.warning('正在保存组织信息，请稍候再切换'); next(false) } else next() },
  beforeRouteLeave(to, from, next) { if (this.busy) { toast.warning('正在保存组织信息，请稍候再离开'); next(false) } else next() },
  methods: {
    viewCheckedOrganization(report) {
      const tab = { COLLEGE: 'college', MAJOR: 'major', CLASS: 'class' }[report.targetType]
      if (!tab || this.busy) return
      this.switchTab(tab); this.filters.keyword = report.targetName; this.search()
    },
    invalidateReads(includeOptions = false) { for (const key of Object.keys(this.requestVersions)) if (includeOptions || key !== 'options') this.requestVersions[key]++ },
    displayTime(value) {
      if (!value) return '—'
      // Organization audit/created_at are stored as UTC; legacy DTOs omit the offset.
      const time = String(value)
      return formatDateTime(/(?:Z|[+-]\d{2}:\d{2})$/i.test(time) ? time : `${time}Z`, '—')
    },
    auditObjectLabel(value) { return { AA_ORG_COLLEGE: '学院', AA_ORG_MAJOR: '专业', AA_ORG_CLASS: '行政班', AA_ORG_MAJOR_DIRECTION: '专业方向', AA_ORG_CLASS_ADJUST: '学生班级调整', AA_ORG_CLASS_ADJUST_REQUEST: '班级调整申请' }[value] || '组织记录' },
    auditActionLabel(value) { return { CREATE: '新建', UPDATE: '修改', DELETE: '删除', BIND_SECRETARY: '教学秘书绑定', ADJUST_CLASS: '调整学生班级', TOGGLE: '设置总开关', DIRECTION_CREATE: '新建方向', DIRECTION_UPDATE: '修改方向', DIRECTION_DISABLE: '停用方向', ADJUST_CREATE: '发起调整', SYNC_CHECK: '前置核对', ADJUST_EXECUTE: '执行调整', ADJUST_CANCEL: '撤销调整' }[value] || '组织变更' },
    openTeachingBatch(row) { if (this.canViewTeachingTasks && row.batchId) this.$router.push({ name: 'aa-task-detail', params: { batchId: row.batchId } }) },
    studentStatusLabel(value) { return ACADEMIC_STUDENT_STATUS_LABELS[value] || '待确认' },
    trainingLevelLabel(value) { return { SECONDARY: '中职', HIGHER: '高职', FIVE_YEAR: '五年制' }[value] || '未设置' },
    closeForm() { if (!this.form.submitting) { this.form.visible = false; this.invalidateClassStatePreview() } },
    classStatusLabel(v) { return CLASS_STATUS[v] || (v ? '待确认' : '') },
    switchTab(key) {
      if (this.busy || key === this.tab || !this.tabs.some(t => t.key === key)) return
      this.tab = key
      this.invalidateReads()
      this.rows = []; this.error = ''; this.loading = false
      for (const state of [this.form, this.secretary, this.students, this.adjust, this.del, this.directionForm, this.directionConfirm, this.adjustCreateForm, this.adjustCheckResult, this.adjustActionConfirm]) state.visible = false
      this.filters = { collegeId: '', majorId: '', keyword: '', termId: '' }
      this.pagination.page = 1
      this.pagination.total = 0
      if (this.$route.query.tab !== key) this.$router.replace({ query: { ...this.$route.query, tab: key } })
      if (key === 'stats') this.loadStats()
      else if (key === 'tree') this.loadTree()
      else if (key === 'direction') this.loadDirectionToggle()
      else if (key === 'adjust') this.reloadAdjustments()
      else if (key === 'students') this.reloadStudentsList()
      else this.reload()
    },
    async loadOptions() {
      const version = ++this.requestVersions.options
      this.optionsLoading = true; this.optionsError = ''
      const res = await api.orgTree()
      if (version !== this.requestVersions.options) return
      this.optionsLoading = false
      if (res.code !== 0) {
        this.collegeOptions = []; this.majorOptions = []; this.classOptions = []
        this.optionsError = res.message || '组织选项加载失败，请重试'
        return
      }
      const colleges = res.data?.colleges || []
      this.tree = { colleges }
      this.collegeOptions = colleges.map(c => ({ value: String(c.id), label: c.collegeName }))
      this.majorOptions = colleges.flatMap(c => (c.majors || []).map(m => ({ value: String(m.id), label: m.majorName, collegeId: String(c.id) })))
      this.classOptions = colleges.flatMap(c => (c.majors || []).flatMap(m => (m.classes || []).map(k => ({ value: String(k.id), label: k.className, majorId: String(m.id) }))))
    },
    search() { this.pagination.page = 1; this.reload() },
    resetFilters() { this.filters = { collegeId: '', majorId: '', keyword: '', termId: '' }; this.search() },
    onPageChange(p) { this.pagination.page = p; this.reload() },
    async reload() {
      if (['tree', 'stats', 'direction', 'students', 'adjust'].includes(this.tab)) return
      const version = ++this.requestVersions.list
      const tab = this.tab
      this.loading = true; this.error = ''
      const params = { page: this.pagination.page, pageSize: this.pagination.pageSize }
      let res
      if (this.tab === 'college') res = await api.listColleges({ ...params, keyword: this.filters.keyword })
      else if (this.tab === 'major') res = await api.listMajors({ ...params, collegeId: this.filters.collegeId, keyword: this.filters.keyword })
      else if (this.tab === 'class') res = await api.listClasses({ ...params, majorId: this.filters.majorId, keyword: this.filters.keyword })
      else if (this.tab === 'teaching') res = await api.listTeachingClasses({ ...params, termId: this.filters.termId || undefined, keyword: this.filters.keyword || undefined })
      else if (this.tab === 'audit') res = await api.listAudit(params)
      else if (this.tab === 'grade') res = await api.listGrades({ majorId: this.filters.majorId || undefined })
      if (version !== this.requestVersions.list || tab !== this.tab) return
      if (res) {
        if (res.code === 0) {
          this.rows = tab === 'grade' ? (res.data.items || []) : (res.data.list || [])
          this.pagination.total = tab === 'grade' ? this.rows.length : (res.data.total || 0)
        } else { this.rows = []; this.error = res.message || '列表加载失败，请重试' }
      }
      this.loading = false
    },
    async loadStats() {
      const version = ++this.requestVersions.stats
      this.statsLoading = true; this.statsError = ''
      const res = await api.orgStats()
      if (version !== this.requestVersions.stats) return
      if (res.code === 0) this.stats = res.data; else this.statsError = res.message
      this.statsLoading = false
    },
    distributionWidth(value) {
      const max = Math.max(1, ...(this.stats.collegeDistribution || []).map(item => Number(item.studentCount) || 0))
      return `${Math.max(4, Math.round((Number(value) || 0) / max * 100))}%`
    },
    async loadTree() {
      const version = ++this.requestVersions.tree
      this.treeLoading = true; this.treeError = ''
      const res = await api.orgTree()
      if (version !== this.requestVersions.tree) return
      if (res.code === 0) this.tree = res.data; else this.treeError = res.message
      this.treeLoading = false
    },
    defaultModel() {
      if (this.tab === 'college') return { sortOrder: 0 }
      if (this.tab === 'major') return { collegeId: this.filters.collegeId, educationYears: 3, enrollStatus: 'ENROLLING', trainingLevel: '' }
      return { majorId: this.filters.majorId, classStatus: 'NORMAL' }
    },
    openCreate() {
      if (!this.canCreate || this.busy || (this.tab !== 'college' && (this.optionsLoading || this.optionsError))) return
      this.form = { visible: true, mode: 'create', kind: this.tab, submitting: false, model: this.defaultModel(), originalParentId: '', error: '', needsReload: false }
    },
    openEdit(row) {
      if (!this.canManage || this.busy) return
      this.requestVersions.classState++
      this.form = { visible: true, mode: 'edit', kind: this.tab, submitting: false, model: { ...row }, originalParentId: row.collegeId || row.majorId || '', originalClassStatus: row.classStatus || 'NORMAL', statePreview: null, statePreviewing: false, error: '', needsReload: false }
    },
    invalidateClassStatePreview() {
      this.requestVersions.classState++
      this.form.statePreview = null
      this.form.statePreviewing = false
    },
    async previewClassState() {
      if (!this.canManage || this.busy || !this.form.visible || !this.classStateChanged) return
      if (String(this.form.model.reason || '').trim().length < 5) { this.form.error = '调整原因至少 5 个字'; return }
      const form = this.form, target = form.model.classStatus
      const version = ++this.requestVersions.classState
      form.statePreview = null; form.statePreviewing = true; form.error = ''
      const res = await api.previewClassState(form.model.id, { classStatus: target, expectedVersion: form.model.version })
      if (version !== this.requestVersions.classState || this.form !== form || !form.visible || form.model.classStatus !== target) return
      form.statePreviewing = false
      if (res.code === 0) form.statePreview = res.data
      else form.error = res.message || '核对失败，请重试'
    },
    async submitForm() {
      const form = this.form
      if (!this.canManage || this.busy || !form.visible || form.needsReload) return
      const m = form.model
      const kind = form.kind
      for (const f of this.formFields) {
        if (f.required && !String(m[f.key] ?? '').trim()) { this.form.error = '请填写' + f.label; return }
        if (f.type === 'number' && m[f.key] !== undefined && m[f.key] !== null && m[f.key] !== '') {
          const value = Number(m[f.key])
          if (!Number.isInteger(value) || (f.min !== undefined && value < f.min) || (f.max !== undefined && value > f.max)) {
            this.form.error = f.label + '须为有效整数'; return
          }
        }
      }
      if ((this.parentChanged || this.classStateChanged) && String(m.reason || '').trim().length < 5) { this.form.error = '调整原因至少 5 个字'; return }
      if (this.classStateChanged && !this.classStateReady) { this.form.error = '请先核对并处理状态变更的影响'; return }
      const body = Object.fromEntries(this.formFields.map(f => [f.key, f.type === 'number'
        ? (m[f.key] === '' || m[f.key] === undefined || m[f.key] === null ? null : Number(m[f.key]))
        : (typeof m[f.key] === 'string' ? m[f.key].trim() : (m[f.key] ?? null))]))
      if (this.form.mode === 'edit') {
        body.expectedVersion = m.version
        if (!this.parentChanged) { delete body.collegeId; delete body.majorId }
        if (this.parentChanged || this.classStateChanged) body.reason = m.reason.trim()
        if (this.classStateChanged) body.expectedStateSnapshotHash = this.form.statePreview.snapshotHash
      }
      form.error = ''
      form.submitting = true
      try {
        let res
        if (kind === 'college') {
          res = form.mode === 'create' ? await api.createCollege(body) : await api.updateCollege(m.id, body)
        } else if (kind === 'major') {
          res = form.mode === 'create' ? await api.createMajor(body) : await api.updateMajor(m.id, body)
        } else {
          res = form.mode === 'create' ? await api.createClass(body) : await api.updateClass(m.id, body)
        }
        if (this.form !== form || !form.visible) return
        if (res.code === 0) {
          toast.success('已保存'); form.visible = false; this.loadOptions(); this.reload()
        } else {
          form.error = res.message || '保存失败，请重试'; this.invalidateClassStatePreview()
          if (res.bizCode === 'DATA_CONFLICT' && res.details?.reason === 'VERSION_CONFLICT') {
            form.needsReload = true
            form.error += '。本次输入仍保留；请关闭后从刷新后的列表重新打开，核对最新资料再修改。'
            this.reload()
          }
        }
      } catch (error) {
        if (this.form === form && form.visible) {
          form.error = error.message || '请求未完成，请核对列表中的保存结果后重试'
          this.invalidateClassStatePreview()
        }
      } finally {
        form.submitting = false
      }
    },
    openSecretary(row) {
      if (!this.canManage || this.busy) return
      ++this.requestVersions.secretary
      this.secretary = { visible: true, submitting: false, row: { ...row }, secretaryId: row.secretaryId || '',
        reviewing: false, review: null, receipt: null, error: '', needsReload: false }
    },
    secretaryStatusLabel(status) { return { DISABLED: '账号已停用', LOCKED: '账号已锁定', DELETED: '账号已删除', INVALID_TYPE: '非校内职工账号' }[status] || '账号已不可用' },
    closeSecretary() {
      if (this.secretary.submitting) return
      this.secretary.visible = false; this.invalidateSecretaryReview()
    },
    invalidateSecretaryReview() {
      ++this.requestVersions.secretary
      this.secretary.review = null; this.secretary.reviewing = false
    },
    async fetchSecretaryOptions(params) {
      const form = this.secretary
      if (!form.visible || !this.canManage || !form.row) return []
      const res = await api.listSecretaryCandidates(form.row.id, params)
      if (form !== this.secretary || !form.visible) return []
      if (res.code !== 0) throw new Error(res.message || '教职工读取失败，请重试')
      return res.data.list.map(u => ({ ...u, desc: u.loginName || '' }))
    },
    searchSecretaryCandidates(keyword) { return this.fetchSecretaryOptions({ keyword, pageSize: 50 }) },
    resolveSecretaryCandidate(value) {
      const row = this.secretary.row
      if (row?.secretaryId && String(row.secretaryId) === String(value)) {
        return Promise.resolve({ value: String(value), label: row.secretaryName || '绑定账号已不可用',
          desc: row.secretaryLoginName || '', disabled: row.secretaryStatus !== 'ACTIVE' })
      }
      return this.fetchSecretaryOptions({ userId: value }).then(rows => rows[0])
    },
    async reviewSecretary() {
      const form = this.secretary
      if (!form.visible || this.busy || form.reviewing || !this.canManage || !this.secretaryChanged || form.needsReload || form.receipt) return
      const version = ++this.requestVersions.secretary
      const sid = String(form.secretaryId || '')
      form.reviewing = true; form.error = ''; form.review = null
      try {
        const target = sid ? (await this.fetchSecretaryOptions({ userId: sid }))[0] : null
        if (version !== this.requestVersions.secretary || form !== this.secretary || !form.visible || sid !== String(form.secretaryId || '')) return
        if (sid && (!target || String(target.value) !== sid)) { form.error = '该账号已不可用，请重新选择本校启用的教职工'; return }
        const previous = form.row.secretaryName || (form.row.secretaryId ? '原绑定账号' : '未绑定')
        form.review = { secretaryId: sid || null, targetName: target?.label || '',
          message: `${form.row.collegeName}：${previous} → ${target?.label || '解除学院绑定'}。请核对后确认。` }
      } catch (error) {
        if (version === this.requestVersions.secretary && form === this.secretary) form.error = error.message
      } finally {
        if (version === this.requestVersions.secretary && form === this.secretary) form.reviewing = false
      }
    },
    async submitSecretary() {
      const form = this.secretary
      if (!this.canManage || this.busy || !form.visible || !form.row || !form.review || form.needsReload || form.receipt) return
      if (String(form.review.secretaryId || '') !== String(form.secretaryId || '')) return
      form.submitting = true; form.error = ''
      const res = await api.bindSecretary(form.row.id, form.review.secretaryId, form.row.version)
      form.submitting = false
      if (res.code === 0) { form.receipt = res.data; toast.success('已保存'); this.reload() }
      else {
        form.error = res.message || '绑定失败，请重试'; this.invalidateSecretaryReview()
        if (res.bizCode === 'DATA_CONFLICT') { form.needsReload = true; form.error += '。请关闭后重新打开最新学院记录。'; this.reload() }
      }
    },
    async openStudents(row) {
      if (this.busy) return
      this.students = { visible: true, loading: false, error: '', rows: [], className: row.className, classId: row.id, page: 1, pageSize: 20, total: 0 }
      await this.reloadStudentDrawer()
    },
    pageStudentDrawer({ page, pageSize }) { this.students.page = page; this.students.pageSize = pageSize; this.reloadStudentDrawer() },
    async reloadStudentDrawer() {
      const version = ++this.requestVersions.studentDrawer
      const classId = this.students.classId
      this.students.loading = true; this.students.error = ''; this.students.rows = []
      const res = await api.listClassStudents(classId, { page: this.students.page, pageSize: this.students.pageSize })
      if (version !== this.requestVersions.studentDrawer || classId !== this.students.classId || !this.students.visible) return
      this.students.loading = false
      if (res.code === 0) { this.students.rows = res.data.list; this.students.total = res.data.total || 0 }
      else { this.students.error = res.message || '班级学生加载失败，请重试'; this.students.total = 0 }
    },
    openAdjust(student) {
      if (!this.canManage || this.busy || this.optionsLoading || this.optionsError) return
      ++this.requestVersions.transfer
      this.adjust = { visible: true, submitting: false, student: { ...student }, targetClassId: '', reason: '', previewing: false, preview: null, receipt: null, error: '',
        origin: { classId: this.students.classId, className: this.students.className } }
      this.students.visible = false
    },
    closeAdjust() {
      if (this.adjust.submitting) return
      ++this.requestVersions.transfer
      this.adjust.visible = false
      if (this.tab !== 'adjust' && !this.adjust.receipt && this.adjust.origin?.classId) {
        this.students.visible = true
        this.reloadStudentDrawer()
      }
    },
    invalidateTransferPreview() {
      ++this.requestVersions.transfer
      this.adjust.preview = null; this.adjust.previewing = false; this.adjust.error = ''
    },
    async previewTransfer() {
      if (!this.canManage || this.busy || !this.adjust.visible || !this.adjust.targetClassId || this.adjust.previewing) return
      if ((this.adjust.reason || '').trim().length < 5) { this.adjust.error = '请填写至少 5 个字的调整原因'; return }
      const version = ++this.requestVersions.transfer
      const target = this.adjust.targetClassId
      this.adjust.previewing = true; this.adjust.error = ''; this.adjust.preview = null
      try {
        const res = await api.previewClassTransfer({ studentId: this.adjust.student.id, targetClassId: target })
        if (version !== this.requestVersions.transfer || !this.adjust.visible || target !== this.adjust.targetClassId) return
        if (res.code === 0) {
          this.adjust.preview = res.data
          this.adjust.origin = { classId: res.data.fromClassId, className: res.data.fromClassName }
        } else this.adjust.error = res.message || '转班核对失败，请重试'
      } catch {
        if (version === this.requestVersions.transfer) this.adjust.error = '暂时无法核对，请重试'
      } finally { if (version === this.requestVersions.transfer) this.adjust.previewing = false }
    },
    viewTransferredClass() {
      if (this.busy || !this.adjust.receipt) return
      const row = this.adjust.receipt
      this.adjust.visible = false
      return this.openStudents({ id: row.toClassId, className: row.toClassName })
    },
    async submitAdjust() {
      if (!this.canManage || this.busy || !this.adjust.visible || !this.adjust.preview || !this.adjust.targetClassId) return
      const preview = this.adjust.preview
      if (String(preview.target.id) !== String(this.adjust.targetClassId)) { this.invalidateTransferPreview(); return }
      const reason = (this.adjust.reason || '').trim()
      if (reason.length < 5 || reason.length > 500) { this.adjust.error = '调整原因需为 5 至 500 个字符'; return }
      this.adjust.submitting = true
      this.adjust.error = ''
      try {
        const res = await api.adjustClass({ studentId: this.adjust.student.id, targetClassId: preview.target.id,
          expectedVersion: preview.student.version, expectedTargetVersion: preview.target.version, expectedSnapshotHash: preview.snapshotHash, reason })
        if (res.code === 0) {
          this.adjust.receipt = res.data
          toast.success('转班已完成')
          this.reload()
        } else {
          this.adjust.error = res.message || '转班失败，请重新核对'
          this.adjust.preview = null
        }
      } catch { this.adjust.error = '暂未取得办理结果，请先刷新名册确认学生归属'; this.adjust.preview = null }
      finally { this.adjust.submitting = false }
    },
    openDelete(row) {
      if (!this.canManage || this.busy) return
      const nameKey = { college: 'collegeName', major: 'majorName', class: 'className' }[this.tab]
      if (!nameKey) return
      const name = row[nameKey] || ''
      const note = this.tab === 'class' ? '关联学生或未归档教学任务尚未处理时无法删除。' : '存在下级组织或学生时无法删除。'
      this.del = { visible: true, submitting: false, row: { ...row }, kind: this.tab, error: '', message: `确认删除「${name}」？${note}` }
    },
    async submitDelete() {
      if (!this.canManage || this.busy || !this.del.visible || !this.del.row) return
      this.del.submitting = true
      this.del.error = ''
      const id = this.del.row.id
      let res
      if (this.del.kind === 'college') res = await api.deleteCollege(id)
      else if (this.del.kind === 'major') res = await api.deleteMajor(id)
      else res = await api.deleteClass(id)
      this.del.submitting = false
      if (res.code === 0) { toast.success('已删除'); this.del.visible = false; this.loadOptions(); this.reload() }
      else this.del.error = res.message || '删除失败，请重试'
    },

    // ═══════════ 专业方向（06号卡） ═══════════
    async loadDirectionToggle() {
      const version = ++this.requestVersions.directionToggle
      this.directionToggle.loading = true; this.directionToggle.loaded = false; this.directionToggle.error = ''
      const res = await api.getMajorDirectionToggle()
      if (version !== this.requestVersions.directionToggle) return
      this.directionToggle.loading = false
      if (res.code === 0) {
        Object.assign(this.directionToggle, res.data, { loaded: true })
        this.reloadDirections()
      } else this.directionToggle.error = res.message || '总开关状态读取失败，请重试'
    },
    toggleMajorDirection() {
      if (!this.canManageSchool || this.busy || !this.directionToggle.loaded) return
      const enabled = !this.directionToggle.enabled
      this.directionConfirm = { visible: true, submitting: false, kind: 'toggle', enabled,
        version: this.directionToggle.version, error: '', needsReload: false,
        title: enabled ? '启用专业方向' : '停用专业方向总开关',
        message: enabled ? '启用后，可按专业维护本校的方向清单。确认本校需要按方向管理？' : '停用后，暂停专业方向的查看与维护。已有方向记录将保留，重新启用后可继续查看。' }
    },
    changeDirectionMajor() {
      if (this.busy) return
      this.closeDirectionForm(); this.closeDirectionAction()
      this.directions.page = 1
      this.reloadDirections()
    },
    pageDirections({ page, pageSize }) {
      if (this.busy) return
      this.directions.page = page; this.directions.pageSize = pageSize
      this.reloadDirections()
    },
    async reloadDirections() {
      const version = ++this.requestVersions.directions
      const majorId = this.directionMajorId
      this.directions.rows = []; this.directions.total = 0; this.directions.loading = false
      if (!majorId || !this.directionToggle.loaded || !this.directionToggle.enabled) return
      this.directions.loading = true; this.directions.error = ''
      const res = await api.listDirections(majorId, { page: this.directions.page, pageSize: this.directions.pageSize })
      if (version !== this.requestVersions.directions || majorId !== this.directionMajorId) return
      this.directions.loading = false
      if (res.code === 0) {
        this.directions.rows = res.data.list; this.directions.total = res.data.total
        if (!res.data.list.length && res.data.total && this.directions.page > 1) {
          this.directions.page = Math.ceil(res.data.total / this.directions.pageSize)
          return this.reloadDirections()
        }
      }
      else this.directions.error = res.message
    },
    openDirectionCreate() {
      if (!this.canWriteDirections) return
      this.directionForm = { visible: true, mode: 'create', submitting: false, model: { directionName: '', code: '' },
        majorId: this.directionMajorId, majorName: this.majorOptions.find(m => m.value === this.directionMajorId)?.label || '当前专业', error: '', needsReload: false }
    },
    openDirectionEdit(row) {
      if (!this.canWriteDirections || row.status !== 'ACTIVE' || String(row.majorId) !== this.directionMajorId) return
      this.openDirectionCreate()
      this.directionForm.mode = 'edit'; this.directionForm.model = { ...row }
    },
    closeDirectionForm() { if (!this.directionForm.submitting) this.directionForm.visible = false },
    closeDirectionAction() {
      if (this.directionConfirm.submitting) return
      const refresh = this.directionConfirm.needsReload
      this.directionConfirm.visible = false
      if (refresh) this.loadDirectionToggle()
    },
    async submitDirectionForm() {
      const form = this.directionForm
      if (!form.visible || !this.canWriteDirections || form.needsReload) return
      const m = form.model
      const body = { directionName: (m.directionName || '').trim(), code: (m.code || '').trim() || null }
      if (!body.directionName) { form.error = '方向名称必填'; return }
      if (body.directionName.length > 200 || (body.code || '').length > 50) { form.error = '方向名称最多200字，编码最多50字'; return }
      if (form.mode === 'edit') body.expectedVersion = m.version
      form.submitting = true; form.error = ''
      const res = form.mode === 'create'
        ? await api.createDirection(form.majorId, body)
        : await api.updateDirection(form.majorId, m.id, body)
      form.submitting = false
      if (res.code === 0) { toast.success('已保存'); form.visible = false; this.reloadDirections() }
      else {
        form.error = res.message || '保存失败，请重试'
        if (['VERSION_CONFLICT', 'INVALID_STATE'].includes(res.details?.reason)) {
          form.needsReload = true; form.error += '。请关闭后刷新列表，重新打开记录。'; this.reloadDirections()
        }
        if (res.bizCode === 'FEATURE_DISABLED') this.loadDirectionToggle()
      }
    },
    disableDirection(row) {
      if (!this.canWriteDirections || row.status !== 'ACTIVE' || String(row.majorId) !== this.directionMajorId) return
      this.directionConfirm = { visible: true, submitting: false, kind: 'disable', enabled: false,
        row: { ...row }, majorId: this.directionMajorId, error: '', needsReload: false,
        title: '停用专业方向', message: `确认停用「${row.directionName}」？停用后作为历史记录保留，不再允许编辑。` }
    },
    async submitDirectionAction() {
      const action = this.directionConfirm
      if (!action.visible || this.busy || action.needsReload || !this.directionToggle.loaded) return
      if (action.kind === 'toggle' ? !this.canManageSchool : !this.canWriteDirections) return
      action.submitting = true; action.error = ''
      ++this.requestVersions.directionToggle
      const res = action.kind === 'toggle'
        ? await api.setMajorDirectionToggle(action.enabled, action.version)
        : await api.disableDirection(action.majorId, action.row.id, { expectedVersion: action.row.version })
      action.submitting = false
      if (res.code === 0) {
        if (action.kind === 'toggle') Object.assign(this.directionToggle, res.data, { loaded: true, loading: false, error: '' })
        action.visible = false; this.closeDirectionForm(); toast.success('已保存'); this.reloadDirections()
      } else {
        action.error = res.message || '操作失败，请重试'
        if (res.bizCode === 'DATA_CONFLICT' || res.bizCode === 'FEATURE_DISABLED') {
          action.needsReload = true; action.error += '。请关闭此窗口后重新核对。'
        }
      }
    },

    // ═══════════ 班级学生（07号卡：只读增强） ═══════════
    searchStudents() { this.studentsList.page = 1; this.reloadStudentsList() },
    pageStudents({ page, pageSize }) { this.studentsList.page = page; this.studentsList.pageSize = pageSize; this.reloadStudentsList() },
    async reloadStudentsList() {
      const version = ++this.requestVersions.students
      const classId = this.studentsFilterClassId
      this.studentsList.rows = []; this.studentsList.total = 0
      if (!classId) { this.studentsList.loading = false; this.studentsList.error = ''; return }
      this.studentsList.loading = true; this.studentsList.error = ''
      const res = await api.listClassStudents(classId,
        { page: this.studentsList.page, pageSize: this.studentsList.pageSize, keyword: this.studentsKeyword || undefined })
      if (version !== this.requestVersions.students || classId !== this.studentsFilterClassId) return
      this.studentsList.loading = false
      if (res.code === 0) { this.studentsList.rows = res.data.list; this.studentsList.total = res.data.total || 0 }
      else this.studentsList.error = res.message || '班级学生加载失败，请重试'
    },
    searchAdjustStudents() {
      this.adjustStudentId = ''
      this.studentsKeyword = ''
      this.studentsList.page = 1
      this.studentsList.pageSize = 100
      this.reloadStudentsList()
    },
    openSelectedStudentTransfer() {
      const student = this.studentsList.rows.find(row => String(row.id) === String(this.adjustStudentId))
      const origin = this.classOptions.find(row => String(row.value) === String(this.studentsFilterClassId))
      if (!student || !origin || !this.canManage || this.busy) return
      ++this.requestVersions.transfer
      this.adjust = { visible: true, submitting: false, student: { ...student }, targetClassId: '', reason: '', previewing: false, preview: null, receipt: null, error: '',
        origin: { classId: this.studentsFilterClassId, className: origin.label } }
    },

    // ═══════════ 班级调整申请单（08号卡：批量组织调整） ═══════════
    adjustTypeLabel(v) {
      return { MERGE: '合班登记', SPLIT: '拆班登记', DISBAND: '停用撤销', GRADUATE_CLEAR: '毕业清班' }[v] || (v ? '待确认' : '—')
    },
    adjustStatusLabel(v) {
      return { DRAFT: '草稿', CHECKED: '已核对', EXECUTED: '已执行', CANCELLED: '已撤销' }[v] || (v ? '待确认' : '—')
    },
    adjustStatusType(v) {
      return { DRAFT: 'default', CHECKED: 'warning', EXECUTED: 'success', CANCELLED: 'default' }[v] || 'default'
    },
    adjustEffect(type) {
      return {
        MERGE: '登记合班去向并停用来源班级。请先完成学生转班、归档教学任务；本操作不会迁移学生。',
        SPLIT: '仅记录拆班安排，保留班级当前状态。新建班级和学生转班需分别办理。',
        DISBAND: '将来源班级设为已解散。请先处理在籍学生并归档教学任务，执行后保留历史记录。',
        GRADUATE_CLEAR: '将来源班级设为已毕业。请先完成学生毕业处理并归档教学任务，执行后保留历史记录。'
      }[type] || '请选择调整类型，查看执行后的结果。'
    },
    adjustResultMessage(row) {
      if (row.status === 'CANCELLED') return '此申请已撤销，未执行班级变更。历史核对记录仅供查阅。'
      if (row.status !== 'EXECUTED') return this.adjustEffect(row.adjustType)
      if (row.adjustType === 'SPLIT') return '拆班安排已登记。本次未变更班级状态或学生归属；新建班级与学生转班请分别办理。'
      const result = row.checkResult?.execution
      return result ? `已将 ${result.changedClassCount} 个来源班级设为${this.classStatusLabel(result.classStatus)}，历史记录已保留。本次未迁移学生。` : '调整已执行，以下为执行前的核对记录。'
    },
    isAdjustBlocked(row) {
      if (row?.status !== 'CHECKED' || row.checkResult?.blocked !== false || !row.checkResult?.snapshotHash) return true
      const expires = row.checkExpiresAt
      const timestamp = expires && Date.parse(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(expires) ? expires : `${expires}Z`)
      return !Number.isFinite(timestamp) || timestamp <= Date.now()
    },
    closeAdjustCreate() { if (!this.busy) this.adjustCreateForm.visible = false },
    closeAdjustResult() { if (!this.busy) this.adjustCheckResult.visible = false },
    closeAdjustAction() { if (!this.busy) this.adjustActionConfirm.visible = false },
    searchAdjustments() { if (!this.busy) { this.adjustments.page = 1; return this.reloadAdjustments() } },
    pageAdjustments({ page, pageSize }) {
      if (this.busy) return
      this.adjustments.page = page; this.adjustments.pageSize = pageSize
      return this.reloadAdjustments()
    },
    async reloadAdjustments() {
      const version = ++this.requestVersions.adjustments
      this.adjustments.rows = []; this.adjustments.total = 0
      this.adjustments.loading = true; this.adjustments.error = ''
      const res = await api.listClassAdjustments({
        page: this.adjustments.page, pageSize: this.adjustments.pageSize,
        status: this.adjustments.filters.status || undefined,
        adjustType: this.adjustments.filters.adjustType || undefined
      })
      if (version !== this.requestVersions.adjustments) return
      this.adjustments.loading = false
      if (res.code === 0) { this.adjustments.rows = res.data.list; this.adjustments.total = res.data.total || 0 }
      else this.adjustments.error = res.message || '班级调整加载失败，请重试'
    },
    openAdjustCreate() {
      if (!this.canManage || this.busy || this.optionsLoading || this.optionsError) return
      this.adjustCreateForm = {
        visible: true, submitting: false, error: '',
        model: { adjustType: 'MERGE', fromClassIds: [], toClassId: '', reason: '' }
      }
    },
    async submitAdjustCreate() {
      if (!this.canManage || this.busy || !this.adjustCreateForm.visible) return
      const m = this.adjustCreateForm.model
      const sourceIds = [...new Set(m.fromClassIds.map(String))]
      const fail = message => { this.adjustCreateForm.error = message }
      if (!sourceIds.length || sourceIds.length > 500) return fail('请选择 1 至 500 个来源班级')
      if (m.adjustType === 'MERGE' && !m.toClassId) return fail('合班登记必须指定目标班级')
      if (m.adjustType === 'MERGE' && sourceIds.includes(String(m.toClassId))) return fail('目标班级不能同时作为来源班级')
      const reason = (m.reason || '').trim()
      if (reason.length < 5 || reason.length > 1000) return fail('调整理由需为 5 至 1000 个字符')
      this.adjustCreateForm.submitting = true
      this.adjustCreateForm.error = ''
      let created
      try {
        const res = await api.createClassAdjustment({
          adjustType: m.adjustType, fromClassIds: sourceIds,
          toClassId: m.adjustType === 'MERGE' ? m.toClassId : undefined, reason
        })
        if (res.code !== 0) return fail(res.message || '发起失败，请重试')
        created = res.data
        this.adjustCreateForm.visible = false
        this.adjustments.page = 1
      } catch { fail('暂时无法发起，请稍后重试') }
      finally { this.adjustCreateForm.submitting = false }
      if (created) await this.precheckAdjustment(created)
    },
    async precheckAdjustment(row) {
      if (!this.canManage || this.busy || !['DRAFT', 'CHECKED'].includes(row?.status)) return
      this.actionBusy = true
      try {
        const res = await api.precheckClassAdjustment(row.id, row.version)
        if (res.code === 0) {
          this.adjustCheckResult = { visible: true, row: res.data }
          toast.success(res.data.checkResult?.blocked ? '核对完成，请先处理待办事项' : '核对通过，请确认后执行')
        } else toast.error(res.message || '核对失败，请刷新后重试')
        await this.reloadAdjustments()
      } catch { toast.error('核对未完成，请刷新申请后重试') }
      finally { this.actionBusy = false }
    },
    viewCheckResult(row) { if (!this.busy) this.adjustCheckResult = { visible: true, row } },
    confirmAdjustAction(row, action) {
      if (!this.canManage || this.busy || !['execute', 'cancel'].includes(action)) return
      if (action === 'execute' ? this.isAdjustBlocked(row) : !['DRAFT', 'CHECKED'].includes(row?.status)) return
      const map = {
        execute: { title: '确认执行' + this.adjustTypeLabel(row.adjustType), message: `${row.fromClassNames || '已选来源班级'}${row.toClassName ? ' → ' + row.toClassName : ''}。${this.adjustEffect(row.adjustType)}` },
        cancel: { title: '撤销申请', message: `确认撤销「${this.adjustTypeLabel(row.adjustType)}」申请？班级和学生保持当前状态，申请记录仍可查看。` }
      }
      this.adjustCheckResult.visible = false
      this.adjustActionConfirm = { visible: true, submitting: false, row: { ...row }, action, error: '', needsRecheck: false, ...map[action] }
    },
    async submitAdjustAction() {
      if (!this.canManage || this.busy || !this.adjustActionConfirm.visible || this.adjustActionConfirm.needsRecheck) return
      const { row, action } = this.adjustActionConfirm
      if (!row || !['execute', 'cancel'].includes(action)) return
      this.adjustActionConfirm.submitting = true
      this.adjustActionConfirm.error = ''
      try {
        const res = action === 'execute'
          ? await api.executeClassAdjustment(row.id, row.version)
          : await api.cancelClassAdjustment(row.id, row.version)
        if (res.code === 0) {
          toast.success(action === 'execute' ? '班级调整已执行' : '申请已撤销')
          this.adjustActionConfirm.visible = false
          if (action === 'execute') this.adjustCheckResult = { visible: true, row: res.data }
          await this.loadOptions()
        } else {
          this.adjustActionConfirm.error = res.message || '办理失败，请刷新后重试'
          this.adjustActionConfirm.needsRecheck = true
        }
        await this.reloadAdjustments()
      } catch {
        this.adjustActionConfirm.error = '暂未取得办理结果，请刷新申请确认最新状态'
        this.adjustActionConfirm.needsRecheck = true
      } finally { this.adjustActionConfirm.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
@import '../styles/foundation-workspace.css';
.aa-org-list { padding: 20px; }
.aa-list-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 16px; }
.aa-list-heading h2 { margin: 0; font-size: 16px; font-weight: 600; }
.aa-list-heading span { font-size: 12px; color: var(--text-secondary); }
.aa-org-form { margin: 0; padding: 0; border: 0; min-width: 0; display: grid; gap: 16px; }
.aa-org-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; }
.aa-org-actions .mp-link { margin: 0; white-space: nowrap; }
.aa-org-table { overflow-x: auto; }
.aa-org-table table { min-width: 820px; }
.aa-org-table th, .aa-org-table td { vertical-align: top; }
.aa-org-table th, .aa-org-table td:first-child { white-space: nowrap; }
.aa-org-table td:nth-child(2) { min-width: 140px; }
.aa-org-table td:nth-child(4) { min-width: 170px; }
.aa-org-table td:nth-child(6) { min-width: 110px; }
.aa-org-table td:last-child { min-width: 175px; }
.aa-org-blockers { margin: 0; padding-left: 16px; }
.aa-transfer-summary { display: grid; gap: 8px; padding: 16px; border: 1px solid var(--border-200); border-radius: var(--radius-md); }
.aa-transfer-summary span { color: var(--text-secondary); }
.aa-class-state-check { padding: 16px; border: 1px solid var(--border-200); border-radius: var(--radius-md); display: grid; gap: 10px; }
.aa-class-state-check p { margin: 0; }
.aa-transfer-steps { display: flex; align-items: center; gap: 10px; margin: 4px 0 18px; color: var(--text-500); font-size: 13px; }
.aa-transfer-steps span { display: inline-flex; align-items: center; gap: 7px; white-space: nowrap; }
.aa-transfer-steps b { display: grid; place-items: center; width: 24px; height: 24px; border-radius: 50%; background: var(--bg-page); color: var(--text-500); }
.aa-transfer-steps .is-active { color: var(--primary-600); font-weight: 600; }
.aa-transfer-steps .is-active b { color: #fff; background: var(--primary-600); }
.aa-transfer-steps i { flex: 1; height: 1px; min-width: 18px; background: var(--border-200); }
.aa-transfer-launcher { padding: 18px; border: 1px solid var(--border-200); border-left: 3px solid var(--primary-600); border-radius: var(--radius-md); background: var(--bg-card); }
.aa-transfer-launcher > div:first-child { margin-bottom: 14px; }
.aa-transfer-launcher p { margin: 6px 0 0; color: var(--text-500); font-size: 13px; line-height: 1.65; }
.aa-transfer-launcher .aa-filter { margin: 0; padding: 0; border: 0; }
.aa-adjust-divider { display: flex; align-items: center; gap: 12px; margin: 22px 0 14px; color: var(--text-500); font-size: 12px; }
.aa-adjust-divider::before, .aa-adjust-divider::after { content: ''; height: 1px; flex: 1; background: var(--border-200); }
.aa-tabs { display: flex; gap: var(--space-1); flex-wrap: wrap; border-bottom: 1px solid var(--border-200); margin-bottom: var(--space-3); }
.aa-tab { padding: var(--space-2) var(--space-3); border: none; background: transparent; cursor: pointer; color: var(--text-500); border-bottom: 2px solid transparent; }
.aa-tab.is-active { color: var(--primary-600); border-bottom-color: var(--primary-600); font-weight: var(--font-weight-semibold); }
.aa-filter { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; align-items: center; }
.aa-filter > :deep(.app-remote-select), .aa-filter > :deep(.app-select), .aa-filter > :deep(.app-text-input) { flex: 1 1 200px; width: auto; min-width: 180px; max-width: 320px; }
.aa-note-inline { color: var(--text-500); font-size: var(--font-size-sm); }
.aa-input, .aa-filter select { padding: var(--space-1) var(--space-2); border: 1px solid var(--border-300); border-radius: var(--radius-sm); }
.aa-danger { color: var(--danger-600); }
.aa-stat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: var(--space-3); }
.aa-stat { padding: var(--space-3); border: 1px solid var(--border-200); border-radius: var(--radius-md); text-align: center; }
.aa-stat__num { font-size: var(--font-size-2xl); font-weight: var(--font-weight-bold); color: var(--primary-600); }
.aa-stat__label { color: var(--text-500); font-size: var(--font-size-sm); }
.aa-stat-ledger { display: grid; grid-template-columns: minmax(0, .9fr) minmax(420px, 1.1fr); gap: 16px; }
.aa-stat-panel { padding: 18px; border: 1px solid var(--border-200); border-radius: var(--radius-md); background: var(--bg-card); overflow: auto; }
.aa-stat-panel h2 { margin: 0 0 16px; font-size: 16px; }
.aa-stat-bar-row { display: grid; grid-template-columns: 120px minmax(100px, 1fr) 58px; gap: 12px; align-items: center; margin: 12px 0; font-size: 13px; }
.aa-stat-bar-row > div { height: 8px; overflow: hidden; border-radius: 999px; background: var(--bg-page); }
.aa-stat-bar-row i { display: block; height: 100%; border-radius: inherit; background: var(--primary-500, #356fd1); }
.aa-stat-bar-row strong { text-align: right; }
.aa-org-ledger-layout { display: grid; grid-template-columns: 230px minmax(0, 1fr); gap: 16px; align-items: start; }
.aa-org-master { position: sticky; top: 12px; max-height: 650px; overflow: auto; border: 1px solid var(--border-200); border-radius: var(--radius-md); background: var(--bg-card); }
.aa-org-master__head { display: flex; justify-content: space-between; gap: 8px; padding: 15px 16px; border-bottom: 1px solid var(--border-200); }
.aa-org-master__head span, .aa-org-master__tree small { font-size: 12px; color: var(--text-500); }
.aa-org-master__tree, .aa-org-master__tree ul { list-style: none; margin: 0; padding: 0; }
.aa-org-master__tree > li { padding: 13px 15px; border-bottom: 1px solid var(--border-100); }
.aa-org-master__tree li:last-child { border-bottom: 0; }
.aa-org-master__tree ul { margin-top: 9px; display: grid; gap: 7px; }
.aa-org-master__tree ul li { display: flex; justify-content: space-between; gap: 8px; color: var(--text-500); font-size: 13px; }
.aa-tree { list-style: none; padding-left: var(--space-2); }
.aa-tree ul { list-style: none; padding-left: var(--space-4); }
.mp-link + .mp-link { margin-left: var(--space-2); }
@media (max-width: 1180px) {
  .aa-org-ledger-layout, .aa-stat-ledger { grid-template-columns: minmax(0, 1fr); }
  .aa-org-master { position: static; max-height: 260px; }
}
@media (max-width: 900px) { .aa-transfer-steps i { display: none; } .aa-transfer-steps { flex-wrap: wrap; } }
</style>
