<template>
  <ModulePageShell
    title="学院专业班级"
    :subtitle="'组织架构维护（学院 / 专业 / 行政班）· 教学秘书绑定 · 组织变更审计'"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
  >
    <template #actions>
      <AppButton v-if="canManage && ['college','major','class'].includes(tab)"
              variant="primary" @click="openCreate">＋ 新建{{ tabLabel }}</AppButton>
    </template>

    <div class="mp-stack">
      <!-- 页签 -->
      <nav class="aa-tabs">
        <button v-for="t in tabs" :key="t.key" class="aa-tab" :class="{ 'is-active': tab === t.key }"
                @click="switchTab(t.key)">{{ t.label }}</button>
      </nav>

      <!-- 统计概览 -->
      <section v-if="tab === 'stats'" class="mp-card">
        <div class="mp-card__body">
          <ErrorState v-if="statsError" :description="statsError" @retry="loadStats" />
          <LoadingState v-else-if="statsLoading" />
          <div v-else class="aa-stat-grid">
            <div v-for="s in statCards" :key="s.key" class="aa-stat">
              <div class="aa-stat__num">{{ stats[s.key] ?? 0 }}</div>
              <div class="aa-stat__label">{{ s.label }}</div>
            </div>
          </div>
        </div>
      </section>

      <!-- 组织树 -->
      <section v-else-if="tab === 'tree'" class="mp-card">
        <div class="mp-card__body">
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

      <!-- 专业方向（06号卡） -->
      <section v-else-if="tab === 'direction'" class="mp-card">
        <div class="mp-card__body">
          <div class="aa-filter">
            <span class="aa-note-inline">总开关：</span>
            <StatusTag :type="directionToggle.enabled ? 'success' : 'default'"
                       :label="directionToggle.enabled ? '已启用' : '未启用'" dot />
            <AppButton v-if="canManage" :loading="directionToggle.loading" @click="toggleMajorDirection">
              {{ directionToggle.enabled ? '停用总开关' : '启用总开关' }}
            </AppButton>
            <template v-if="directionToggle.enabled">
              <AppSelect v-model="directionMajorId" :placeholder="''" @change="reloadDirections"
                         :options="[{ value: '', label: '请选择专业' }, ...majorOptions]" />
              <AppButton v-if="directionMajorId && canManage" variant="primary" @click="openDirectionCreate">＋ 新建方向</AppButton>
            </template>
          </div>
          <EmptyState v-if="!directionToggle.enabled" title="专业方向总开关未启用"
                      description="本校尚未启用「专业方向」管理粒度；是否启用属学校业务政策，需教务处/校管确认后在此开启总开关。" />
          <EmptyState v-else-if="!directionMajorId" title="请选择专业" description="选择上方专业后查看/维护其下的方向" />
          <template v-else>
            <ErrorState v-if="directions.error" :description="directions.error" @retry="reloadDirections" />
            <LoadingState v-else-if="directions.loading" />
            <EmptyState v-else-if="!directions.rows.length" title="该专业暂无方向" description="点击「新建方向」新增" />
            <table v-else class="mp-audit">
              <thead><tr><th>方向名称</th><th>编码</th><th>状态</th><th>操作</th></tr></thead>
              <tbody>
                <tr v-for="d in directions.rows" :key="d.id">
                  <td>{{ d.directionName }}</td><td>{{ d.code || '—' }}</td>
                  <td><StatusTag :type="d.status === 'ACTIVE' ? 'success' : 'default'"
                                 :label="d.status === 'ACTIVE' ? '启用' : '停用'" dot /></td>
                  <td>
                    <button class="mp-link" :disabled="!canManage" @click="openDirectionEdit(d)">编辑</button>
                    <button v-if="d.status === 'ACTIVE'" class="mp-link aa-danger" :disabled="!canManage"
                            @click="disableDirection(d)">停用</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </template>
        </div>
      </section>

      <!-- 班级学生（07号卡：只读增强，独立于「行政班」页签内既有名册弹窗） -->
      <section v-else-if="tab === 'students'" class="mp-card">
        <div class="mp-card__body">
          <div class="aa-filter">
            <AppSelect v-model="studentsFilterClassId" :placeholder="''" @change="reloadStudentsList"
                       :options="[{ value: '', label: '请选择行政班' }, ...classOptions]" />
            <input v-model="studentsKeyword" class="aa-input" placeholder="学号/姓名关键字" @keyup.enter="reloadStudentsList" />
            <AppButton :disabled="!studentsFilterClassId" @click="reloadStudentsList">查询</AppButton>
          </div>
          <EmptyState v-if="!studentsFilterClassId" title="请选择行政班" description="选择上方行政班查看该班学生名册" />
          <template v-else>
            <ErrorState v-if="studentsList.error" :description="studentsList.error" @retry="reloadStudentsList" />
            <LoadingState v-else-if="studentsList.loading" />
            <EmptyState v-else-if="!studentsList.rows.length" title="该班暂无在册学生" />
            <table v-else class="mp-audit">
              <thead><tr><th>学号</th><th>姓名</th><th>性别</th><th>学籍状态</th><th>手机号</th></tr></thead>
              <tbody>
                <tr v-for="s in studentsList.rows" :key="s.id">
                  <td>{{ s.studentNo }}</td><td>{{ s.realName }}</td><td>{{ s.gender || '—' }}</td>
                  <td>{{ s.studentStatus || '—' }}</td><td>{{ s.phoneMasked || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </template>
          <p class="mp-note">本页仅只读查看，手机号脱敏展示；批量组织调整请使用「班级调整」页签。</p>
        </div>
      </section>

      <!-- 班级调整申请单（08号卡：行政班层面批量组织调整） -->
      <section v-else-if="tab === 'adjust'" class="mp-card">
        <div class="mp-card__body">
          <div class="aa-filter">
            <AppSelect v-model="adjustments.filters.status" :placeholder="''" @change="reloadAdjustments"
                       :options="[{ value: '', label: '全部状态' }, { value: 'DRAFT', label: '草稿' }, { value: 'CHECKED', label: '已核对' }, { value: 'EXECUTED', label: '已执行' }, { value: 'CANCELLED', label: '已撤销' }]" />
            <AppSelect v-model="adjustments.filters.adjustType" :placeholder="''" @change="reloadAdjustments"
                       :options="[{ value: '', label: '全部类型' }, { value: 'MERGE', label: '合班登记' }, { value: 'SPLIT', label: '拆班登记' }, { value: 'DISBAND', label: '停用撤销' }, { value: 'GRADUATE_CLEAR', label: '毕业清班' }]" />
            <AppButton @click="reloadAdjustments">查询</AppButton>
            <AppButton v-if="canManage" variant="primary" @click="openAdjustCreate">＋ 发起调整</AppButton>
          </div>
          <ErrorState v-if="adjustments.error" :description="adjustments.error" @retry="reloadAdjustments" />
          <LoadingState v-else-if="adjustments.loading" />
          <EmptyState v-else-if="!adjustments.rows.length" title="暂无调整申请" description="点击「发起调整」新建" />
          <table v-else class="mp-audit">
            <thead><tr><th>类型</th><th>来源班级</th><th>目标班级</th><th>理由</th><th>状态</th><th>发起时间</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="a in adjustments.rows" :key="a.id">
                <td>{{ adjustTypeLabel(a.adjustType) }}</td>
                <td>{{ a.fromClassNames || '—' }}</td>
                <td>{{ a.toClassName || '—' }}</td>
                <td>{{ a.reason }}</td>
                <td><StatusTag :type="adjustStatusType(a.status)" :label="adjustStatusLabel(a.status)" dot /></td>
                <td>{{ a.createdAt ? a.createdAt.slice(0, 16).replace('T', ' ') : '—' }}</td>
                <td>
                  <button v-if="a.status === 'DRAFT' && canManage" class="mp-link" @click="precheckAdjustment(a)">前置核对</button>
                  <button v-if="a.status === 'CHECKED' && canManage" class="mp-link" @click="precheckAdjustment(a)">重新核对</button>
                  <button v-if="a.checkResult" class="mp-link" @click="viewCheckResult(a)">核对结果</button>
                  <button v-if="a.status === 'CHECKED' && canManage" class="mp-link" :disabled="isAdjustBlocked(a)"
                          @click="confirmAdjustAction(a, 'execute')">确认执行</button>
                  <button v-if="['DRAFT','CHECKED'].includes(a.status) && canManage" class="mp-link aa-danger"
                          @click="confirmAdjustAction(a, 'cancel')">撤销</button>
                </td>
              </tr>
            </tbody>
          </table>
          <p class="mp-note">
            本组为行政班层面的批量组织调整（不改写学生所属行政班，个体学生转班请走「行政班」页签内既有的「学生 → 调整班级」）。
          </p>
        </div>
      </section>

      <!-- 列表类页签（学院/专业/行政班/年级/教学班/审计/班级学生）-->
      <template v-else>
        <div v-if="tab === 'major' || tab === 'class'" class="aa-filter">
          <AppSelect v-if="tab === 'major'" v-model="filters.collegeId" :placeholder="''" @change="reload"
                     :options="[{ value: '', label: '全部学院' }, ...collegeOptions]" />
          <AppSelect v-if="tab === 'class'" v-model="filters.majorId" :placeholder="''" @change="reload"
                     :options="[{ value: '', label: '全部专业' }, ...majorOptions]" />
          <input v-model="filters.keyword" class="aa-input" placeholder="关键词" @keyup.enter="reload" />
          <AppButton @click="reload">查询</AppButton>
        </div>

        <ErrorState v-if="error" :description="error" @retry="reload" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" :title="'暂无' + tabLabel + '数据'" description="可调整筛选条件或新建记录" />
        <DataTable
          v-else
          :columns="columns"
          :rows="rows"
          row-key="id"
          :pagination="pagination"
          @page-change="onPageChange"
        >
          <template #cell-enrollStatus="{ row }">
            <StatusTag :type="row.enrollStatus === 'ENROLLING' ? 'success' : 'default'"
                       :label="row.enrollStatus === 'ENROLLING' ? '招生中' : '停招'" dot />
          </template>
          <template #cell-classStatus="{ row }">
            <StatusTag :type="row.classStatus === 'NORMAL' ? 'success' : 'default'"
                       :label="classStatusLabel(row.classStatus)" dot />
          </template>
          <template #cell-actions="{ row }">
            <template v-if="tab === 'college'">
              <button class="mp-link" :disabled="!canManage" @click="openEdit(row)">编辑</button>
              <button class="mp-link" :disabled="!canManage" @click="openSecretary(row)">教学秘书</button>
              <button class="mp-link aa-danger" :disabled="!canManage" @click="openDelete(row)">删除</button>
            </template>
            <template v-else-if="tab === 'major'">
              <button class="mp-link" :disabled="!canManage" @click="openEdit(row)">编辑</button>
              <button class="mp-link aa-danger" :disabled="!canManage" @click="openDelete(row)">删除</button>
            </template>
            <template v-else-if="tab === 'class'">
              <button class="mp-link" :disabled="!canManage" @click="openEdit(row)">编辑</button>
              <button class="mp-link" @click="openStudents(row)">学生</button>
              <button class="mp-link aa-danger" :disabled="!canManage" @click="openDelete(row)">删除</button>
            </template>
          </template>
        </DataTable>
      </template>

      <p class="mp-note">
        组织三表复用冻结册 t_college / t_major / t_class；删除为软删且要求先清空下级/在册学生；
        全部写操作经后端 build_affairs_context 数据范围收敛并写组织变更审计（AA_ORG_*）。
      </p>
    </div>

    <!-- 新建 / 编辑 表单 -->
    <AppDrawer :visible="form.visible" :title="(form.mode === 'create' ? '新建' : '编辑') + tabLabel" @update:visible="form.visible = $event">
      <div class="aa-form">
        <AppFormItem v-for="f in formFields" :key="f.key" :label="f.label" :required="!!f.required">
          <AppSelect v-if="f.type === 'select'" v-model="form.model[f.key]" :options="f.options || []" />
          <AppNumberInput v-else-if="f.type === 'number'" v-model="form.model[f.key]" />
          <AppTextInput v-else v-model="form.model[f.key]" :placeholder="f.placeholder || ''" />
        </AppFormItem>
      </div>
      <template #footer>
        <AppButton @click="form.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="form.submitting" @click="submitForm">保存</AppButton>
      </template>
    </AppDrawer>

    <!-- 教学秘书绑定 -->
    <AppDrawer :visible="secretary.visible" :title="'教学秘书绑定 · ' + (secretary.row && secretary.row.collegeName)" @update:visible="secretary.visible = $event">
      <div class="aa-form">
        <AppFormItem label="教学秘书 user_id">
          <AppTextInput v-model="secretary.secretaryId" placeholder="留空为解绑" />
        </AppFormItem>
      </div>
      <template #footer>
        <AppButton @click="secretary.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="secretary.submitting" @click="submitSecretary">保存</AppButton>
      </template>
    </AppDrawer>

    <!-- 班级学生抽屉 -->
    <AppDrawer :visible="students.visible" :title="'班级学生 · ' + students.className" @update:visible="students.visible = $event">
      <LoadingState v-if="students.loading" />
      <EmptyState v-else-if="!students.rows.length" title="该班暂无在册学生" />
      <table v-else class="mp-audit">
        <thead><tr><th>学号</th><th>姓名</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="s in students.rows" :key="s.id">
            <td>{{ s.studentNo }}</td><td>{{ s.realName }}</td>
            <td><button class="mp-link" :disabled="!canManage" @click="openAdjust(s)">调整班级</button></td>
          </tr>
        </tbody>
      </table>
      <template #footer>
        <AppButton @click="students.visible = false">关闭</AppButton>
      </template>
    </AppDrawer>

    <!-- 班级调整 -->
    <AppDrawer :visible="adjust.visible" :title="'班级调整 · ' + (adjust.student && adjust.student.realName)" @update:visible="adjust.visible = $event">
      <div class="aa-form">
        <AppFormItem label="目标班级" required>
          <AppSelect v-model="adjust.targetClassId" placeholder="请选择目标班级" :options="classOptions" />
        </AppFormItem>
      </div>
      <template #footer>
        <AppButton @click="adjust.visible = false">取消</AppButton>
        <AppButton variant="primary" :disabled="!adjust.targetClassId" :loading="adjust.submitting"
                @click="submitAdjust">确认调整</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="del.visible"
      type="danger"
      :title="'删除' + tabLabel"
      :message="del.message"
      confirm-text="确认删除"
      :submitting="del.submitting"
      @confirm="submitDelete"
    />

    <!-- 专业方向 · 新建/编辑 -->
    <AppDrawer :visible="directionForm.visible" :title="(directionForm.mode === 'create' ? '新建' : '编辑') + '专业方向'" @update:visible="directionForm.visible = $event">
      <div class="aa-form">
        <AppFormItem label="方向名称" required>
          <AppTextInput v-model="directionForm.model.directionName" placeholder="如 Web开发方向" />
        </AppFormItem>
        <AppFormItem label="编码">
          <AppTextInput v-model="directionForm.model.code" placeholder="选填，专业内唯一" />
        </AppFormItem>
      </div>
      <template #footer>
        <AppButton @click="directionForm.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="directionForm.submitting" @click="submitDirectionForm">保存</AppButton>
      </template>
    </AppDrawer>

    <!-- 班级调整申请单 · 发起 -->
    <AppDrawer :visible="adjustCreateForm.visible" title="发起班级调整" @update:visible="adjustCreateForm.visible = $event">
      <div class="aa-form">
        <AppFormItem label="调整类型" required>
          <AppSelect v-model="adjustCreateForm.model.adjustType" :options="[
            { value: 'MERGE', label: '合班登记' }, { value: 'SPLIT', label: '拆班登记' },
            { value: 'DISBAND', label: '停用撤销' }, { value: 'GRADUATE_CLEAR', label: '毕业清班' }]" />
        </AppFormItem>
        <AppFormItem label="来源班级" required hint="按住 Ctrl/Cmd 可多选">
          <!-- 原生多选列表框：AppSelect 只支持单选，多选保留原生控件，不强行套壳 -->
          <select v-model="adjustCreateForm.model.fromClassIds" multiple size="5" class="aa-native-multiselect">
            <option v-for="c in classOptions" :key="c.value" :value="c.value">{{ c.label }}</option>
          </select>
        </AppFormItem>
        <AppFormItem v-if="adjustCreateForm.model.adjustType === 'MERGE'" label="目标班级" required>
          <AppSelect v-model="adjustCreateForm.model.toClassId" placeholder="请选择目标班级" :options="classOptions" />
        </AppFormItem>
        <AppFormItem label="调整理由" required>
          <AppTextInput v-model="adjustCreateForm.model.reason" placeholder="至少5个字符" />
        </AppFormItem>
      </div>
      <template #footer>
        <AppButton @click="adjustCreateForm.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="adjustCreateForm.submitting" @click="submitAdjustCreate">发起</AppButton>
      </template>
    </AppDrawer>

    <!-- 班级调整申请单 · 核对结果 -->
    <AppDrawer :visible="adjustCheckResult.visible" title="核对结果" @update:visible="adjustCheckResult.visible = $event">
      <template v-if="adjustCheckResult.row && adjustCheckResult.row.checkResult">
        <p>
          阻断状态：
          <StatusTag :type="adjustCheckResult.row.checkResult.blocked ? 'danger' : 'success'"
                     :label="adjustCheckResult.row.checkResult.blocked ? '存在阻断项' : '无阻断'" dot />
        </p>
        <table class="mp-audit">
          <thead><tr><th>班级</th><th>在读学生数</th></tr></thead>
          <tbody>
            <tr v-for="ref in adjustCheckResult.row.checkResult.refs" :key="ref.classId">
              <td>{{ ref.className }}</td><td>{{ ref.activeStudentCount }}</td>
            </tr>
          </tbody>
        </table>
      </template>
      <template #footer>
        <AppButton @click="adjustCheckResult.visible = false">关闭</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="adjustActionConfirm.visible"
      :type="adjustActionConfirm.action === 'cancel' ? 'danger' : 'warning'"
      :title="adjustActionConfirm.title"
      :message="adjustActionConfirm.message"
      :confirm-text="adjustActionConfirm.action === 'execute' ? '确认执行' : '确认撤销'"
      :submitting="adjustActionConfirm.submitting"
      @confirm="submitAdjustAction"
    />
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
import { AppSelect, AppFormItem, AppTextInput, AppNumberInput } from '@/components/common'
import { academicAffairsOrgApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { currentUserFromToken } from '@/services/http/client'
import { toast } from '@/utils/toast'

const CLASS_STATUS = { NORMAL: '在读', GRADUATED: '已毕业', DISBANDED: '已解散' }
const MANAGE_ROLES = ['SCHOOL_ADMIN', 'PLATFORM_SUPER_ADMIN', 'ACADEMIC_TEACHER', 'COLLEGE_ADMIN']

export default {
  name: 'AaOrgConsole',
  components: { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppButton, AppDrawer, AppConfirmDialog, AppSelect, AppFormItem, AppTextInput, AppNumberInput },
  data() {
    return {
      tab: 'college',
      tabs: [
        { key: 'college', label: '学院' }, { key: 'major', label: '专业' }, { key: 'class', label: '行政班' },
        { key: 'grade', label: '年级' }, { key: 'teaching', label: '教学班' },
        { key: 'direction', label: '专业方向' }, { key: 'students', label: '班级学生' }, { key: 'adjust', label: '班级调整' },
        { key: 'tree', label: '组织树' }, { key: 'stats', label: '统计' }, { key: 'audit', label: '变更审计' }
      ],
      loading: false, error: '', rows: [],
      pagination: { page: 1, pageSize: 10, total: 0 },
      filters: { collegeId: '', majorId: '', keyword: '' },
      collegeOptions: [], majorOptions: [], classOptions: [],
      stats: {}, statsLoading: false, statsError: '',
      tree: { colleges: [] }, treeLoading: false, treeError: '',
      form: { visible: false, mode: 'create', submitting: false, model: {} },
      secretary: { visible: false, submitting: false, row: null, secretaryId: '' },
      students: { visible: false, loading: false, rows: [], className: '', classId: null },
      adjust: { visible: false, submitting: false, student: null, targetClassId: '' },
      del: { visible: false, submitting: false, row: null, message: '' },
      // 专业方向（06号卡）
      directionToggle: { enabled: false, loading: false },
      directionMajorId: '',
      directions: { rows: [], loading: false, error: '' },
      directionForm: { visible: false, mode: 'create', submitting: false, model: {} },
      // 班级学生（07号卡：只读增强，独立于「行政班」页签内既有的名册弹窗）
      studentsFilterClassId: '',
      studentsKeyword: '',
      studentsList: { rows: [], loading: false, error: '' },
      // 班级调整申请单（08号卡：批量组织调整，区别于「行政班/学生」内既有的个体转班弹窗）
      adjustments: {
        rows: [], loading: false, error: '',
        filters: { status: '', adjustType: '' }
      },
      adjustCreateForm: {
        visible: false, submitting: false,
        model: { adjustType: 'MERGE', fromClassIds: [], toClassId: '', reason: '' }
      },
      adjustCheckResult: { visible: false, row: null },
      adjustActionConfirm: { visible: false, submitting: false, title: '', message: '', action: null, row: null }
    }
  },
  computed: {
    user() { return currentUserFromToken() || {} },
    roleName() { return this.user.roleName || this.user.currentRoleCode || '' },
    dataScopeName() { return this.user.scopeLabel || this.user.dataScope || '' },
    canManage() { return MANAGE_ROLES.includes((this.user.currentRoleCode || '').toUpperCase()) },
    tabLabel() { return (this.tabs.find((t) => t.key === this.tab) || {}).label || '' },
    statCards() {
      return [
        { key: 'collegeCount', label: '学院数' }, { key: 'majorCount', label: '专业数' },
        { key: 'classCount', label: '行政班数' }, { key: 'studentCount', label: '在校生数' },
        { key: 'enrollingMajorCount', label: '招生专业数' }, { key: 'graduatedClassCount', label: '已毕业班数' }
      ]
    },
    columns() {
      const map = {
        college: [{ key: 'collegeName', title: '学院名称' }, { key: 'shortName', title: '简称' },
          { key: 'code', title: '编码' }, { key: 'sortOrder', title: '排序' },
          { key: 'secretaryId', title: '教学秘书' }, { key: 'actions', title: '操作' }],
        major: [{ key: 'majorName', title: '专业名称' }, { key: 'collegeName', title: '所属学院' },
          { key: 'educationYears', title: '学制' }, { key: 'trainingLevel', title: '培养层次' },
          { key: 'direction', title: '专业方向' }, { key: 'enrollStatus', title: '招生状态' },
          { key: 'actions', title: '操作' }],
        class: [{ key: 'className', title: '班级名称' }, { key: 'classCode', title: '班级编号' },
          { key: 'majorName', title: '专业' }, { key: 'grade', title: '年级' },
          { key: 'capacity', title: '编制' }, { key: 'graduateYear', title: '应毕业' },
          { key: 'classStatus', title: '状态' }, { key: 'actions', title: '操作' }],
        grade: [{ key: 'grade', title: '年级' }, { key: 'classCount', title: '班级数' },
          { key: 'studentCount', title: '学生数' }],
        teaching: [{ key: 'teachingClassCode', title: '教学班代码' }, { key: 'teachingClassName', title: '教学班名' },
          { key: 'courseCount', title: '课程数' }, { key: 'expectedStudents', title: '预计人数' }],
        audit: [{ key: 'occurredAt', title: '时间' }, { key: 'bizType', title: '对象' },
          { key: 'action', title: '动作' }, { key: 'operator', title: '操作人' }, { key: 'detail', title: '说明' }]
      }
      return map[this.tab] || []
    },
    formFields() {
      if (this.tab === 'college') {
        return [
          { key: 'collegeName', label: '学院名称', required: true },
          { key: 'shortName', label: '简称' }, { key: 'code', label: '编码' },
          { key: 'sortOrder', label: '排序', type: 'number' }
        ]
      }
      if (this.tab === 'major') {
        return [
          { key: 'collegeId', label: '所属学院', type: 'select', required: true, options: this.collegeOptions },
          { key: 'majorName', label: '专业名称', required: true },
          { key: 'educationYears', label: '学制（年）', type: 'number' },
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
        { key: 'majorId', label: '所属专业', type: 'select', required: true, options: this.majorOptions },
        { key: 'className', label: '班级名称', required: true },
        { key: 'classCode', label: '班级编号' }, { key: 'grade', label: '年级', placeholder: '如 2026' },
        { key: 'capacity', label: '编制人数', type: 'number' },
        { key: 'graduateYear', label: '应毕业年份', placeholder: '如 2029' },
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
    '$route.query.tab'(v) {
      if (v && this.tabs.some((t) => t.key === v) && v !== this.tab) this.switchTab(v)
    }
  },
  methods: {
    classStatusLabel(v) { return CLASS_STATUS[v] || v || '' },
    switchTab(key) {
      this.tab = key
      this.pagination.page = 1
      if (key === 'stats') this.loadStats()
      else if (key === 'tree') this.loadTree()
      else if (key === 'direction') this.loadDirectionToggle()
      else if (key === 'adjust') this.reloadAdjustments()
      else if (key === 'students') { /* 需先选行政班，见 reloadStudentsList */ }
      else this.reload()
    },
    async loadOptions() {
      const c = await api.listColleges({ pageSize: 200 })
      if (c.code === 0) this.collegeOptions = c.data.list.map((x) => ({ value: x.id, label: x.collegeName }))
      const m = await api.listMajors({ pageSize: 500 })
      if (m.code === 0) this.majorOptions = m.data.list.map((x) => ({ value: x.id, label: x.majorName }))
      const k = await api.listClasses({ pageSize: 500 })
      if (k.code === 0) this.classOptions = k.data.list.map((x) => ({ value: x.id, label: x.className }))
    },
    onPageChange(p) { this.pagination.page = p; this.reload() },
    async reload() {
      if (['tree', 'stats', 'direction', 'students', 'adjust'].includes(this.tab)) return
      this.loading = true; this.error = ''
      const params = { page: this.pagination.page, pageSize: this.pagination.pageSize }
      let res
      if (this.tab === 'college') res = await api.listColleges({ ...params, keyword: this.filters.keyword })
      else if (this.tab === 'major') res = await api.listMajors({ ...params, collegeId: this.filters.collegeId, keyword: this.filters.keyword })
      else if (this.tab === 'class') res = await api.listClasses({ ...params, majorId: this.filters.majorId, keyword: this.filters.keyword })
      else if (this.tab === 'teaching') res = await api.listTeachingClasses(params)
      else if (this.tab === 'audit') res = await api.listAudit(params)
      else if (this.tab === 'grade') { const g = await api.listGrades(); if (g.code === 0) { this.rows = g.data.items || []; this.pagination.total = this.rows.length } else this.error = g.message; this.loading = false; return }
      if (res) {
        if (res.code === 0) { this.rows = res.data.list; this.pagination.total = res.data.total } else this.error = res.message
      }
      this.loading = false
    },
    async loadStats() {
      this.statsLoading = true; this.statsError = ''
      const res = await api.orgStats()
      if (res.code === 0) this.stats = res.data; else this.statsError = res.message
      this.statsLoading = false
    },
    async loadTree() {
      this.treeLoading = true; this.treeError = ''
      const res = await api.orgTree()
      if (res.code === 0) this.tree = res.data; else this.treeError = res.message
      this.treeLoading = false
    },
    defaultModel() {
      if (this.tab === 'college') return { sortOrder: 0 }
      if (this.tab === 'major') return { educationYears: 3, enrollStatus: 'ENROLLING', trainingLevel: '' }
      return { classStatus: 'NORMAL' }
    },
    openCreate() {
      if (!this.canManage) return toast.error('无操作权限')
      this.form = { visible: true, mode: 'create', submitting: false, model: this.defaultModel() }
    },
    openEdit(row) {
      this.form = { visible: true, mode: 'edit', submitting: false, model: { ...row } }
    },
    async submitForm() {
      const m = this.form.model
      this.form.submitting = true
      let res
      if (this.tab === 'college') {
        res = this.form.mode === 'create' ? await api.createCollege(m) : await api.updateCollege(m.id, m)
      } else if (this.tab === 'major') {
        res = this.form.mode === 'create' ? await api.createMajor(m) : await api.updateMajor(m.id, m)
      } else {
        res = this.form.mode === 'create' ? await api.createClass(m) : await api.updateClass(m.id, m)
      }
      this.form.submitting = false
      if (res.code === 0) { toast.success('已保存'); this.form.visible = false; this.loadOptions(); this.reload() }
      else toast.error(res.message)
    },
    openSecretary(row) {
      this.secretary = { visible: true, submitting: false, row, secretaryId: row.secretaryId || '' }
    },
    async submitSecretary() {
      this.secretary.submitting = true
      const res = await api.bindSecretary(this.secretary.row.id, this.secretary.secretaryId || null)
      this.secretary.submitting = false
      if (res.code === 0) { toast.success('已保存'); this.secretary.visible = false; this.reload() }
      else toast.error(res.message)
    },
    async openStudents(row) {
      this.students = { visible: true, loading: true, rows: [], className: row.className, classId: row.id }
      const res = await api.listClassStudents(row.id, { pageSize: 200 })
      this.students.loading = false
      if (res.code === 0) this.students.rows = res.data.list; else toast.error(res.message)
    },
    openAdjust(student) {
      this.adjust = { visible: true, submitting: false, student, targetClassId: '' }
    },
    async submitAdjust() {
      this.adjust.submitting = true
      const res = await api.adjustClass({ studentId: this.adjust.student.id, targetClassId: this.adjust.targetClassId })
      this.adjust.submitting = false
      if (res.code === 0) {
        toast.success('已调整')
        this.adjust.visible = false
        if (this.students.visible && this.students.classId) this.openStudents({ id: this.students.classId, className: this.students.className })
      } else toast.error(res.message)
    },
    openDelete(row) {
      const name = row.collegeName || row.majorName || row.className || ''
      this.del = { visible: true, submitting: false, row, message: `确认删除「${name}」？删除为逻辑软删，要求先清空下级/在册学生。` }
    },
    async submitDelete() {
      this.del.submitting = true
      const id = this.del.row.id
      let res
      if (this.tab === 'college') res = await api.deleteCollege(id)
      else if (this.tab === 'major') res = await api.deleteMajor(id)
      else res = await api.deleteClass(id)
      this.del.submitting = false
      if (res.code === 0) { toast.success('已删除'); this.del.visible = false; this.loadOptions(); this.reload() }
      else toast.error(res.message)
    },

    // ═══════════ 专业方向（06号卡） ═══════════
    async loadDirectionToggle() {
      const res = await api.getMajorDirectionToggle()
      if (res.code === 0) this.directionToggle.enabled = !!res.data.enabled
      else toast.error(res.message)
      if (this.directionToggle.enabled && this.directionMajorId) this.reloadDirections()
    },
    async toggleMajorDirection() {
      if (!this.canManage) return toast.error('无操作权限')
      this.directionToggle.loading = true
      const res = await api.setMajorDirectionToggle(!this.directionToggle.enabled)
      this.directionToggle.loading = false
      if (res.code === 0) {
        this.directionToggle.enabled = !!res.data.enabled
        toast.success('已保存')
        if (this.directionToggle.enabled && this.directionMajorId) this.reloadDirections()
      } else toast.error(res.message)
    },
    async reloadDirections() {
      if (!this.directionMajorId) { this.directions.rows = []; return }
      this.directions.loading = true; this.directions.error = ''
      const res = await api.listDirections(this.directionMajorId, { pageSize: 200 })
      this.directions.loading = false
      if (res.code === 0) this.directions.rows = res.data.list
      else this.directions.error = res.message
    },
    openDirectionCreate() {
      if (!this.canManage) return toast.error('无操作权限')
      this.directionForm = { visible: true, mode: 'create', submitting: false, model: { directionName: '', code: '' } }
    },
    openDirectionEdit(row) {
      this.directionForm = { visible: true, mode: 'edit', submitting: false, model: { ...row } }
    },
    async submitDirectionForm() {
      const m = this.directionForm.model
      if (!m.directionName || !m.directionName.trim()) return toast.error('方向名称必填')
      this.directionForm.submitting = true
      const res = this.directionForm.mode === 'create'
        ? await api.createDirection(this.directionMajorId, m)
        : await api.updateDirection(this.directionMajorId, m.id, m)
      this.directionForm.submitting = false
      if (res.code === 0) { toast.success('已保存'); this.directionForm.visible = false; this.reloadDirections() }
      else toast.error(res.message)
    },
    async disableDirection(row) {
      if (!this.canManage) return toast.error('无操作权限')
      const res = await api.disableDirection(this.directionMajorId, row.id)
      if (res.code === 0) { toast.success('已停用'); this.reloadDirections() } else toast.error(res.message)
    },

    // ═══════════ 班级学生（07号卡：只读增强） ═══════════
    async reloadStudentsList() {
      if (!this.studentsFilterClassId) { this.studentsList.rows = []; return }
      this.studentsList.loading = true; this.studentsList.error = ''
      const res = await api.listClassStudents(this.studentsFilterClassId,
        { pageSize: 200, keyword: this.studentsKeyword || undefined })
      this.studentsList.loading = false
      if (res.code === 0) this.studentsList.rows = res.data.list
      else this.studentsList.error = res.message
    },

    // ═══════════ 班级调整申请单（08号卡：批量组织调整） ═══════════
    adjustTypeLabel(v) {
      return { MERGE: '合班登记', SPLIT: '拆班登记', DISBAND: '停用撤销', GRADUATE_CLEAR: '毕业清班' }[v] || v
    },
    adjustStatusLabel(v) {
      return { DRAFT: '草稿', CHECKED: '已核对', EXECUTED: '已执行', CANCELLED: '已撤销' }[v] || v
    },
    adjustStatusType(v) {
      return { DRAFT: 'default', CHECKED: 'warning', EXECUTED: 'success', CANCELLED: 'default' }[v] || 'default'
    },
    isAdjustBlocked(row) { return !!(row.checkResult && row.checkResult.blocked) },
    async reloadAdjustments() {
      this.adjustments.loading = true; this.adjustments.error = ''
      const res = await api.listClassAdjustments({
        pageSize: 200, status: this.adjustments.filters.status || undefined,
        adjustType: this.adjustments.filters.adjustType || undefined
      })
      this.adjustments.loading = false
      if (res.code === 0) this.adjustments.rows = res.data.list
      else this.adjustments.error = res.message
    },
    openAdjustCreate() {
      if (!this.canManage) return toast.error('无操作权限')
      this.adjustCreateForm = {
        visible: true, submitting: false,
        model: { adjustType: 'MERGE', fromClassIds: [], toClassId: '', reason: '' }
      }
    },
    async submitAdjustCreate() {
      const m = this.adjustCreateForm.model
      if (!m.fromClassIds.length) return toast.error('请至少选择1个来源班级')
      if (m.adjustType === 'MERGE' && !m.toClassId) return toast.error('合班登记必须指定目标班级')
      if (!m.reason || m.reason.trim().length < 5) return toast.error('调整理由至少5个字符')
      this.adjustCreateForm.submitting = true
      const res = await api.createClassAdjustment({
        adjustType: m.adjustType, fromClassIds: m.fromClassIds,
        toClassId: m.adjustType === 'MERGE' ? m.toClassId : undefined, reason: m.reason
      })
      this.adjustCreateForm.submitting = false
      if (res.code === 0) { toast.success('已发起'); this.adjustCreateForm.visible = false; this.reloadAdjustments() }
      else toast.error(res.message)
    },
    async precheckAdjustment(row) {
      const res = await api.precheckClassAdjustment(row.id)
      if (res.code === 0) {
        toast.success(res.data.checkResult && res.data.checkResult.blocked ? '核对完成：存在阻断项' : '核对完成：无阻断项')
        this.reloadAdjustments()
      } else toast.error(res.message)
    },
    viewCheckResult(row) { this.adjustCheckResult = { visible: true, row } },
    confirmAdjustAction(row, action) {
      const map = {
        execute: { title: '确认执行', message: `确认执行「${this.adjustTypeLabel(row.adjustType)}」调整？该操作将变更相关行政班状态，不可撤销。` },
        cancel: { title: '撤销申请', message: '确认撤销该调整申请？' }
      }
      this.adjustActionConfirm = { visible: true, submitting: false, row, action, ...map[action] }
    },
    async submitAdjustAction() {
      const { row, action } = this.adjustActionConfirm
      this.adjustActionConfirm.submitting = true
      const res = action === 'execute'
        ? await api.executeClassAdjustment(row.id)
        : await api.cancelClassAdjustment(row.id)
      this.adjustActionConfirm.submitting = false
      if (res.code === 0) {
        toast.success(action === 'execute' ? '已执行' : '已撤销')
        this.adjustActionConfirm.visible = false
        this.reloadAdjustments()
      } else toast.error(res.message)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-tabs { display: flex; gap: var(--space-1); flex-wrap: wrap; border-bottom: 1px solid var(--border-200); margin-bottom: var(--space-3); }
.aa-tab { padding: var(--space-2) var(--space-3); border: none; background: transparent; cursor: pointer; color: var(--text-500); border-bottom: 2px solid transparent; }
.aa-tab.is-active { color: var(--primary-600); border-bottom-color: var(--primary-600); font-weight: var(--font-weight-semibold); }
.aa-filter { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; align-items: center; }
.aa-note-inline { color: var(--text-500); font-size: var(--font-size-sm); }
.aa-input, .aa-filter select { padding: var(--space-1) var(--space-2); border: 1px solid var(--border-300); border-radius: var(--radius-sm); }
.aa-danger { color: var(--danger-600); }
.aa-stat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: var(--space-3); }
.aa-stat { padding: var(--space-3); border: 1px solid var(--border-200); border-radius: var(--radius-md); text-align: center; }
.aa-stat__num { font-size: var(--font-size-2xl); font-weight: var(--font-weight-bold); color: var(--primary-600); }
.aa-stat__label { color: var(--text-500); font-size: var(--font-size-sm); }
.aa-tree { list-style: none; padding-left: var(--space-2); }
.aa-tree ul { list-style: none; padding-left: var(--space-4); }
.aa-native-multiselect { width: 100%; box-sizing: border-box; padding: var(--space-2); border: 1px solid var(--border-300); border-radius: var(--radius-sm); font-family: inherit; }
.mp-link + .mp-link { margin-left: var(--space-2); }
</style>
