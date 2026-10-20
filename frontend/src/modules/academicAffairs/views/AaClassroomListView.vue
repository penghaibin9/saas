<template>
  <div class="cr-root">
  <ClassroomBatchWorkspace v-if="batchMode" :key="contextRevision" ref="batchWorkspace" :building="selectedBuilding" :mode="batchMode" :initial-batch-id="typeof $route.query.batchNo === 'string' ? $route.query.batchNo : ''" @batch="rememberBatch" @close="closeBatch" @complete="finishBatch" />
  <ModulePageShell v-else class="classroom-workspace" :title="formVisible ? (editingId ? '编辑教室' : '新建教室') : '教室资源'" :role-name="ctx.currentRole?.roleName" :data-scope-name="ctx.dataScope?.scopeName">
    <template #actions>
      <AppButton v-if="formVisible" :disabled="saving" @click="closeForm">返回教室列表</AppButton>
      <template v-else-if="can('create')"><AppButton @click="openBatch('import')">导入台账</AppButton><AppButton @click="openCreate(selectedBuilding)">单间新增</AppButton><AppButton variant="primary" @click="openBuilding()">新建教学楼</AppButton></template>
    </template>
    <p class="cr-intro">{{ formVisible ? '先确定所在楼栋，再填写教室信息。' : '先建教学楼，再按楼层整批生成或导入台账；日常只维护例外教室。' }}</p>
    <div v-if="receipt" class="cr-receipt" role="status"><div><strong>{{ receipt.roomName }} · {{ receipt.action }}</strong><p>{{ formVisible ? '已保留楼栋、类型和容量，可以继续填写下一间教室。' : '可继续维护教室资料，或查看相关课程安排。' }}</p></div><AppButton v-if="receipt.classroomId && !formVisible" variant="ghost" @click="goSchedule(receipt)">查看课表</AppButton><button class="cr-link" aria-label="关闭操作回执" @click="receipt = null">关闭</button></div>

    <template v-if="!formVisible">
      <form v-if="buildingForm" class="cr-panel cr-building-form" @submit.prevent="saveBuilding">
        <div class="cr-section-head"><h2>{{ buildingEditingId ? '维护教学楼层数' : '新建教学楼' }}</h2><AppButton :disabled="buildingSaving" @click="buildingForm = null">取消</AppButton></div>
        <AppInlineAlert v-if="buildingError" type="danger" :description="buildingError" />
        <div class="cr-grid"><label>楼栋名称 *<input v-model="buildingForm.buildingName" required maxlength="100" :disabled="!!buildingEditingId || buildingSaving" placeholder="如 第一教学楼"></label><label>楼栋编码 *<input v-model="buildingForm.buildingCode" required maxlength="50" :disabled="!!buildingEditingId || buildingSaving" placeholder="全校唯一，如 JX01"></label><label>校区<input v-model="buildingForm.campusCode" maxlength="50" :disabled="!!buildingEditingId || buildingSaving" placeholder="如 主校区"></label><label>楼层数 *<input v-model.number="buildingForm.floorCount" required type="number" min="1" max="100" :disabled="buildingSaving"></label></div>
        <p class="cr-footnote">楼栋编码全校唯一。名称、编码、校区完全一致的已有教室会归入本楼，教室编号和历史关联保留；楼层待您核对。</p><AppButton variant="primary" :disabled="buildingSaving" @click="saveBuilding">{{ buildingSaving ? '正在保存…' : buildingEditingId ? '保存楼层数' : '创建教学楼并继续建教室' }}</AppButton>
      </form>
      <div v-else class="cr-catalog">
      <aside class="cr-panel cr-buildings" aria-label="教学楼目录"><form @submit.prevent="loadBuildings(1)"><label for="cr-building-search">教学楼</label><div><input id="cr-building-search" v-model="buildingKeyword" placeholder="楼名 / 编码 / 校区"><button class="cr-link" type="submit">查找</button></div></form><ErrorState v-if="buildingsError" :description="buildingsError" @retry="loadBuildings(buildingPage)" /><LoadingState v-else-if="buildingsLoading" /><template v-else><button class="cr-building-item" :class="{ active: !filters.buildingId }" @click="selectBuilding(null)"><OfficeBuilding /><span><strong>全部教室</strong><small>包含尚未建楼的历史教室</small></span></button><button v-for="building in buildings" :key="building.buildingId" class="cr-building-item" :class="{ active: filters.buildingId === building.buildingId }" @click="selectBuilding(building)"><OfficeBuilding /><span><strong>{{ building.buildingName }}</strong><small>{{ building.campusCode || '校区未填写' }} · {{ building.roomCount }} 间</small></span></button><p v-if="!buildings.length" class="cr-footnote">{{ buildingKeyword ? '未找到教学楼，请调整搜索。' : '先建立教学楼，即可整栋批量建教室。' }}</p><div v-if="buildingTotal > 50" class="cr-building-pager"><AppButton :disabled="buildingPage <= 1" @click="loadBuildings(buildingPage - 1)">上一页</AppButton><AppButton :disabled="buildingPage * 50 >= buildingTotal" @click="loadBuildings(buildingPage + 1)">下一页</AppButton></div></template></aside>
      <section class="cr-panel" aria-label="教室列表">
        <header class="cr-building-head"><div><h2>{{ selectedBuilding?.buildingName || '全校教室资源' }}</h2><p>{{ selectedBuilding ? `${selectedBuilding.floorCount} 层 · ${selectedBuilding.roomCount || 0} 间教室 · ${selectedBuilding.capacity || 0} 个教学座位` : '选择左侧教学楼，按楼层管理教室' }}</p></div><div v-if="selectedBuilding"><AppButton v-if="can('update')" @click="openBuilding(selectedBuilding)">楼栋资料</AppButton><AppButton v-if="can('create')" variant="primary" @click="openBatch('generate')">批量建教室</AppButton></div></header>
        <nav v-if="selectedBuilding" class="cr-floor-nav" aria-label="楼层"><button :class="{ active: filters.floorNo === '' }" @click="selectFloor('')">全部楼层</button><button v-for="floor in Math.min(selectedBuilding.floorCount, 6)" :key="floor" :class="{ active: filters.floorNo === String(floor) }" @click="selectFloor(String(floor))">{{ floor }} 层</button><select v-if="selectedBuilding.floorCount > 6" :value="Number(filters.floorNo) > 6 ? filters.floorNo : ''" aria-label="更多楼层" @change="selectFloor($event.target.value)"><option value="" disabled>更多楼层</option><option v-for="floor in selectedBuilding.floorCount - 6" :key="floor + 6" :value="String(floor + 6)">{{ floor + 6 }} 层</option></select><button :class="{ active: filters.floorNo === '0' }" @click="selectFloor('0')">楼层待核对</button></nav>
        <nav class="cr-status-tabs" aria-label="教室状态"><button v-for="option in statusOptions" :key="option.value" :aria-pressed="filters.status === option.value" :class="{ active: filters.status === option.value }" @click="selectStatus(option.value)">{{ option.label }}</button></nav>
        <form class="cr-filters" @submit.prevent="search">
          <div class="cr-filter cr-filter--grow"><label for="cr-keyword">查找教室</label><AppTextInput id="cr-keyword" v-model="filters.keyword" placeholder="输入楼栋、教室编号或名称" clearable /></div>
          <div class="cr-filter"><label for="cr-type">教室类型</label><AppSelect id="cr-type" v-model="filters.roomType" :options="typeOptions" placeholder="" @change="search" /></div>
          <AppButton variant="primary" @click="search">查询</AppButton><AppButton variant="ghost" @click="reset">重置</AppButton>
        </form>
        <div class="cr-view-tools"><p class="cr-status-hint">“可用”表示可以选入排课，不代表当前时段空闲。</p><div><button :aria-pressed="viewMode === 'grid'" @click="viewMode = 'grid'">教室视图</button><button :aria-pressed="viewMode === 'table'" @click="viewMode = 'table'">台账视图</button></div></div>
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <div v-else-if="!rows.length" class="cr-empty"><OfficeBuilding aria-hidden="true" /><h2>{{ hasFilters ? '没有符合条件的教室' : '建立学校的教室资源目录' }}</h2><p>{{ hasFilters ? '调整关键词、类型或状态后再试。' : '从整栋批量生成或导入学校已有台账开始。' }}</p><AppButton v-if="hasFilters" @click="reset">清空筛选</AppButton><AppButton v-else-if="can('create')" variant="primary" @click="selectedBuilding ? openBatch('generate') : openBuilding()">{{ selectedBuilding ? '批量建教室' : '新建教学楼' }}</AppButton><p v-else>请联系有教室维护权限的管理员录入。</p></div>
        <template v-else-if="viewMode === 'grid'"><div class="cr-room-grid"><button v-for="row in rows" :key="row.classroomId" class="cr-room-card" @click="openDetail(row)"><div><OfficeBuilding /><StatusTag :type="statusType(row.status)" :label="row.statusLabel" dot /></div><strong>{{ row.roomCode }}</strong><span>{{ row.roomName }}</span><small>{{ row.buildingName }} · {{ row.floorNo ? `${row.floorNo} 层` : '楼层待核对' }} · {{ row.roomTypeLabel }}</small><footer><span><b>{{ row.capacity }}</b> 教学座位</span><span>{{ examSeatText(row.examSeats) }}</span></footer><div class="cr-rule-summary"><span>{{ ruleShort(row.allowSchedule, '排课') }}</span><span>{{ ruleShort(row.allowExam, '排考') }}</span><span>{{ ruleShort(row.allowBorrow, '借用') }}</span></div></button></div><div class="cr-grid-pager"><span>共 {{ pagination.total }} 间 · 第 {{ pagination.page }} 页</span><AppButton :disabled="pagination.page <= 1" @click="onPageChange(pagination.page - 1)">上一页</AppButton><AppButton :disabled="pagination.page * pagination.pageSize >= pagination.total" @click="onPageChange(pagination.page + 1)">下一页</AppButton></div></template>
        <DataTable v-else :columns="columns" :rows="rows" row-key="classroomId" :pagination="pagination" @page-change="onPageChange">
          <template #cell-room="{ row }"><button class="cr-room-name" @click="openDetail(row)">{{ row.roomName }}</button><small class="cr-sub">{{ row.floorNo ? `${row.floorNo} 层 · ` : '楼层待核对 · ' }}{{ row.roomCode }}</small></template>
          <template #cell-building="{ row }"><span>{{ row.buildingName }}</span><small v-if="row.campusCode" class="cr-sub">校区编码 {{ row.campusCode }}</small></template>
          <template #cell-roomType="{ row }">{{ row.roomTypeLabel }}</template>
          <template #cell-capacity="{ row }"><strong>{{ row.capacity }}</strong><small class="cr-unit">教学座位</small></template>
          <template #cell-examSeats="{ row }"><strong>{{ row.examSeats ?? '未设置' }}</strong><small class="cr-unit">{{ row.examSeats === null || row.examSeats === undefined ? '沿用教学座位' : '考试座位' }}</small></template>
          <template #cell-usageRules="{ row }"><div class="cr-rule-summary cr-rule-summary--table"><span>{{ ruleShort(row.allowSchedule, '排课') }}</span><span>{{ ruleShort(row.allowExam, '排考') }}</span><span>{{ ruleShort(row.allowBorrow, '借用') }}</span></div></template>
          <template #cell-status="{ row }"><StatusTag :type="statusType(row.status)" :label="row.statusLabel" dot /></template>
          <template #cell-actions="{ row }"><div class="cr-row-actions"><button v-if="can('update')" class="cr-link" @click="openEdit(row)">编辑</button><button class="cr-link" @click="goSchedule(row)">课表</button><button class="cr-link" :aria-label="`查看${row.roomName}资料与操作`" @click="openDetail(row)">资料与操作</button></div></template>
        </DataTable>
      </section>
      </div>
      <p class="cr-footnote">停用或维修中的教室不出现在可用教室选项中；已有课程安排需到课表中核对。</p>
    </template>

    <form v-else ref="editor" class="cr-editor-form" @submit.prevent="submitForm(false)">
      <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      <div class="cr-editor">
        <div class="cr-panel">
          <section class="cr-section"><div class="cr-section-head"><h2>所在楼栋</h2><small>必填项标记 *</small></div><div class="cr-grid">
            <AppFormItem v-slot="{ id }" data-field="cr-building-code" label="楼栋编码" required :error="fieldErrors.buildingCode"><AppTextInput :id="id" v-model="form.buildingCode" :maxlength="50" placeholder="如 A / 教1" :disabled="saving || !!form.buildingId" :status="fieldErrors.buildingCode ? 'error' : 'default'" /></AppFormItem>
            <AppFormItem v-slot="{ id }" data-field="cr-building-name" label="楼栋名称" required :error="fieldErrors.buildingName"><AppTextInput :id="id" v-model="form.buildingName" :maxlength="100" placeholder="如 教学A楼" :disabled="saving || !!form.buildingId" :status="fieldErrors.buildingName ? 'error' : 'default'" /></AppFormItem>
          </div><div v-if="buildingChoices.length && !editingId" class="cr-reuse"><small>复用当前列表楼栋</small><button v-for="building in buildingChoices" :key="building.buildingCode + building.buildingName" type="button" :disabled="saving" @click="reuseBuilding(building)">{{ building.buildingName }} · {{ building.buildingCode }}</button></div></section>
          <section class="cr-section"><div class="cr-section-head"><h2>教室信息</h2><small>同一楼栋内编号唯一</small></div><div class="cr-grid">
            <AppFormItem v-if="form.buildingId" v-slot="{ id }" label="所在楼层" hint="旧教室楼层不从编号猜测，请核对后填写。"><AppNumberInput :id="id" v-model="form.floorNo" :min="1" :max="100" :precision="0" :disabled="saving" /></AppFormItem>
            <AppFormItem v-slot="{ id }" data-field="cr-room-code" label="教室编号" required :error="fieldErrors.roomCode"><AppTextInput :id="id" v-model="form.roomCode" :maxlength="50" placeholder="如 101" :disabled="saving" :status="fieldErrors.roomCode ? 'error' : 'default'" /></AppFormItem>
            <AppFormItem v-slot="{ id }" data-field="cr-room-name" label="教室名称" :hint="`留空将使用：${form.buildingName.trim() + form.roomCode.trim() || '楼栋名称 + 教室编号'}`"><AppTextInput :id="id" v-model="form.roomName" :maxlength="100" placeholder="可选，留空自动组合名称" :disabled="saving" /></AppFormItem>
            <AppFormItem v-slot="{ id }" data-field="cr-room-type" label="教室类型"><AppSelect :id="id" v-model="form.roomType" :options="typeOptions.slice(1)" placeholder="" :disabled="saving" /></AppFormItem>
            <AppFormItem v-slot="{ id }" data-field="cr-capacity" label="容量（座位）" hint="填写实际可用座位数，范围 0–1000。" :error="fieldErrors.capacity"><AppNumberInput :id="id" v-model="form.capacity" :min="0" :max="1000" :precision="0" :disabled="saving" :status="fieldErrors.capacity ? 'error' : 'default'" /></AppFormItem>
            <AppFormItem v-slot="{ id }" data-field="cr-exam-seats" label="考试座位" hint="按实际考位填写；0 表示没有考位。留空保持未设置，排考时按正式合同沿用教学座位，不做折半。" :error="fieldErrors.examSeats"><AppNumberInput :id="id" v-model="form.examSeats" :min="0" :max="1000" :precision="0" :disabled="saving" :status="fieldErrors.examSeats ? 'error' : 'default'" /></AppFormItem><label class="cr-exclusive"><input v-model="form.isExclusive" type="checkbox" :disabled="saving">专用教室（自动排课跳过）</label>
            <AppFormItem data-field="cr-allow-schedule" label="允许排课" required hint="决定该教室能否进入排课候选；仍须通过时段、容量和状态门禁。" :error="fieldErrors.allowSchedule"><AppSelect :model-value="ruleValue(form.allowSchedule)" @update:model-value="form.allowSchedule = $event === 'true'" :options="booleanOptions" placeholder="服务端未提供" :disabled="saving" :status="fieldErrors.allowSchedule ? 'error' : 'default'" /></AppFormItem>
            <AppFormItem data-field="cr-allow-exam" label="允许排考" required hint="与考试座位数分别维护；允许排考不代表当前时段可用。" :error="fieldErrors.allowExam"><AppSelect :model-value="ruleValue(form.allowExam)" @update:model-value="form.allowExam = $event === 'true'" :options="booleanOptions" placeholder="服务端未提供" :disabled="saving" :status="fieldErrors.allowExam ? 'error' : 'default'" /></AppFormItem>
            <AppFormItem data-field="cr-allow-borrow" label="开放借用" required hint="只控制借用入口，审批时仍核对占用、维修和停用状态。" :error="fieldErrors.allowBorrow"><AppSelect :model-value="ruleValue(form.allowBorrow)" @update:model-value="form.allowBorrow = $event === 'true'" :options="booleanOptions" placeholder="服务端未提供" :disabled="saving" :status="fieldErrors.allowBorrow ? 'error' : 'default'" /></AppFormItem>
            <AppFormItem v-slot="{ id }" data-field="cr-remark" label="备注" class="cr-wide"><AppTextarea :id="id" ref="remarkInput" v-model="form.remark" :maxlength="500" :rows="3" placeholder="例如：投影仪使用说明、教室管理注意事项" :disabled="saving" /><AppQuickPhrases v-if="!saving" scene-key="aa.remark" @pick="onPickRemark" /></AppFormItem>
          </div><details class="cr-extra" :open="!!form.campusCode"><summary>补充校区信息（选填）</summary><AppFormItem v-slot="{ id }" data-field="cr-campus-code" label="校区编码"><AppTextInput :id="id" v-model="form.campusCode" :maxlength="50" placeholder="学校已有校区编码" :disabled="saving || !!form.buildingId" /></AppFormItem></details></section>
        </div>
        <aside class="cr-panel cr-preview" aria-label="教室信息预览"><small>教室信息预览</small><OfficeBuilding class="cr-preview-icon" aria-hidden="true" /><h2>{{ previewName }}</h2><p>{{ form.buildingName || '填写楼栋与编号后自动组合名称' }}</p><dl><div><dt>教室类型</dt><dd>{{ typeOptions.find(item => item.value === form.roomType)?.label }}</dd></div><div><dt>教学座位</dt><dd>{{ form.capacity ?? '待填写' }} 座</dd></div><div><dt>考试座位</dt><dd>{{ examSeatText(form.examSeats) }}</dd></div><div><dt>允许排课</dt><dd>{{ ruleText(form.allowSchedule) }}</dd></div><div><dt>允许排考</dt><dd>{{ ruleText(form.allowExam) }}</dd></div><div><dt>开放借用</dt><dd>{{ ruleText(form.allowBorrow) }}</dd></div></dl><StatusTag :type="statusType(editingStatus || 'AVAILABLE')" :label="editingId ? statusOptions.find(item => item.value === editingStatus)?.label : '新建后默认可用'" /><p class="cr-preview-note">三项用途开关彼此独立；专用教室规则仍单独生效。实际办理还会核对资源状态与占用。</p></aside>
      </div>
      <footer class="cr-editor-footer"><span>保存后可在教室列表继续维护。</span><div><AppButton variant="ghost" :disabled="saving" @click="closeForm">取消</AppButton><AppButton v-if="!editingId" :disabled="saving" @click="submitForm(true)">保存并新增同楼教室</AppButton><AppButton variant="primary" :loading="saving" @click="submitForm(false)">保存教室</AppButton></div></footer>
    </form>

    <AppDrawer :visible="detailVisible" title="教室资料与操作" mode="modal" size="medium" @close="closeDetail">
      <LoadingState v-if="detailLoading" /><ErrorState v-else-if="detailError" :description="detailError" @retry="loadDetail" />
      <div v-else-if="detail" class="cr-detail"><div class="cr-detail-head"><div><h2>{{ detail.roomName }}</h2><p>{{ detail.buildingName }} · {{ detail.roomCode }}</p></div><StatusTag :type="statusType(detail.status)" :label="detail.statusLabel" dot /></div><dl><div><dt>楼栋编码</dt><dd>{{ detail.buildingCode }}</dd></div><div><dt>教室类型</dt><dd>{{ detail.roomTypeLabel }}</dd></div><div><dt>所在楼层</dt><dd>{{ detail.floorNo ? `${detail.floorNo} 层` : '待核对' }}</dd></div><div><dt>教学座位</dt><dd>{{ detail.capacity }} 座</dd></div><div><dt>考试座位</dt><dd>{{ examSeatText(detail.examSeats) }}</dd></div><div><dt>允许排课</dt><dd>{{ ruleText(detail.allowSchedule) }}</dd></div><div><dt>允许排考</dt><dd>{{ ruleText(detail.allowExam) }}</dd></div><div><dt>开放借用</dt><dd>{{ ruleText(detail.allowBorrow) }}</dd></div><div><dt>专用教室</dt><dd>{{ detail.isExclusive ? '是，自动排课跳过' : '否' }}</dd></div><div><dt>校区编码</dt><dd>{{ detail.campusCode || '未填写' }}</dd></div><div class="cr-wide"><dt>备注</dt><dd>{{ detail.remark || '未填写' }}</dd></div></dl><div class="cr-detail-section"><h3>继续办理</h3><div class="cr-detail-actions"><AppButton @click="goSchedule(detail)">查看教室课表</AppButton><AppButton v-if="can('create')" @click="openCreate(detail)">同楼新增教室</AppButton><AppButton v-if="can('update')" @click="openEdit(detail)">编辑资料</AppButton></div></div><div v-if="can('update')" class="cr-detail-section"><h3>调整可用状态</h3><p>更改可用教室选项；已有课程安排需另外核对。</p><div class="cr-detail-actions"><AppButton v-for="option in statusOptions.filter(item => item.value && item.value !== detail.status)" :key="option.value" @click="askStatus(detail, option.value)">{{ option.value === 'AVAILABLE' ? '恢复可用' : option.value === 'MAINTENANCE' ? '标记维修中' : '停用教室' }}</AppButton></div></div><div v-if="can('delete')" class="cr-detail-section"><button class="cr-link cr-danger" @click="askDelete(detail)">删除教室</button><p>从资源目录移除，保留历史课表中的教室名称记录。</p></div></div>
    </AppDrawer>
    <AppConfirmDialog :visible="confirmVisible" :title="confirmTitle" :message="confirmMessage" :type="confirmType" :confirm-text="confirmText" :submitting="acting" @update:visible="value => { if (!acting) confirmVisible = value }" @confirm="onConfirm"><AppInlineAlert v-if="actionError" type="danger" :description="actionError" /></AppConfirmDialog>
  </ModulePageShell>
  </div>
</template>
<script>
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppNumberInput, AppTextarea, AppSelect, AppFormItem, AppConfirmDialog, AppInlineAlert, AppQuickPhrases } from '@/components/common'
import { OfficeBuilding } from '@element-plus/icons-vue'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import ClassroomBatchWorkspace from '../components/ClassroomBatchWorkspace.vue'
import { classroomCatalogApi } from '../api/academic-classroom-catalog.api'
import { matchPermission } from '@/config/navPlan'
import { isDeniedResult, isConflictResult } from '../components/parallel-a/resultState'
import { systemConfirm } from '@/services/systemDialog'

const EMPTY_FILTERS = () => ({ keyword: '', roomType: '', status: '', buildingId: '', floorNo: '' })
const EMPTY_FORM = () => ({ buildingId: null, floorNo: null, examSeats: null, isExclusive: false, allowSchedule: true, allowExam: true, allowBorrow: false, expectedVersion: null, buildingCode: '', buildingName: '', roomCode: '', roomName: '', capacity: 0, roomType: 'LECTURE', campusCode: '', remark: '' })
const errorMessage = (error, fallback) => error?.message || fallback
export default {
  name: 'AaClassroomListView',
  components: { ClassroomBatchWorkspace, ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, AppButton, AppDrawer, AppTextInput, AppNumberInput, AppTextarea, AppSelect, AppFormItem, AppConfirmDialog, AppInlineAlert, AppQuickPhrases, OfficeBuilding },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      viewMode: 'grid', batchMode: '', buildings: [], buildingsLoading: false, buildingsError: '', buildingKeyword: '', buildingPage: 1, buildingTotal: 0, buildingRevision: 0, selectedBuilding: null, buildingForm: null, buildingEditingId: '', buildingError: '', buildingSaving: false,
      loading: false, error: '', rows: [], filters: EMPTY_FILTERS(), pagination: { page: 1, pageSize: 12, total: 0 }, loadRevision: 0, detailRevision: 0, contextRevision: 0,
      columns: [{ key: 'room', title: '教室 / 编号' }, { key: 'building', title: '所在楼栋' }, { key: 'roomType', title: '类型' }, { key: 'capacity', title: '教学座位' }, { key: 'examSeats', title: '考试座位' }, { key: 'usageRules', title: '用途规则' }, { key: 'status', title: '状态' }, { key: 'actions', title: '操作' }],
      typeOptions: [{ label: '全部类型', value: '' }, { label: '普通教室', value: 'LECTURE' }, { label: '多媒体教室', value: 'MULTIMEDIA' }, { label: '机房', value: 'COMPUTER' }, { label: '实验室', value: 'LAB' }, { label: '其他', value: 'OTHER' }],
      booleanOptions: [{ label: '允许', value: 'true' }, { label: '禁止', value: 'false' }],
      statusOptions: [{ label: '全部教室', value: '' }, { label: '可用', value: 'AVAILABLE' }, { label: '维修中', value: 'MAINTENANCE' }, { label: '停用', value: 'DISABLED' }],
      formVisible: false, editingId: '', editingStatus: '', form: EMPTY_FORM(), originalForm: '', saving: false, formError: '', fieldErrors: {}, receipt: null,
      detailVisible: false, detail: null, detailId: '', detailLoading: false, detailError: '',
      confirmVisible: false, confirmTitle: '', confirmMessage: '', confirmType: 'primary', confirmText: '', pendingAction: null, acting: false, actionError: ''
    }
  },
  computed: {
    hasFilters() { return !!(this.filters.keyword || this.filters.roomType || this.filters.status || this.filters.floorNo) },
    previewName() { return this.form.roomName.trim() || this.form.buildingName.trim() + this.form.roomCode.trim() || '待填写教室' },
    buildingChoices() { return [...new Map(this.rows.map(row => [row.buildingCode + ':' + row.buildingName, { buildingCode: row.buildingCode, buildingName: row.buildingName }])).values()] },
    dirty() { return this.formVisible && JSON.stringify(this.form) !== this.originalForm }
  },
  watch: {
    '$route.query': { immediate: true, handler() { this.restoreFilters(); if (typeof this.$route.query.batchNo === 'string' && !this.batchMode && this.can('create')) this.batchMode = 'resume'; this.load() } },
    ctx() { this.batchMode = ''; this.buildings = []; this.selectedBuilding = null; this.buildingForm = null; this.buildingSaving = false; this.loadBuildings(); this.contextRevision++; this.detailRevision++; this.formVisible = false; this.form = EMPTY_FORM(); this.detailVisible = false; this.detail = null; this.receipt = null; this.pendingAction = null; this.confirmVisible = false; this.saving = false; this.acting = false; this.load() }
  },
  mounted() { this.loadBuildings() },
  beforeUnmount() { this.buildingRevision++; this.loadRevision++; this.detailRevision++; this.contextRevision++ },
  async beforeRouteLeave() { return !this.$refs.batchWorkspace?.busy && !this.buildingSaving && !this.saving && (!(this.dirty || this.$refs.batchWorkspace?.dirty || this.buildingForm) || await systemConfirm({ title:'确认离开教室资源', message:'当前教室资料尚未保存，离开后填写内容会丢失。', confirmText:'放弃修改并离开', type:'danger' })) },
  methods: {
    handleFailure(error, field, fallback) {
      if (isDeniedResult(error)) {
        this.contextRevision++; this.loadRevision++; this.detailRevision++; this.buildingRevision++
        this.rows = []; this.buildings = []; this.selectedBuilding = null; this.buildingForm = null; this.batchMode = ''; this.form = EMPTY_FORM(); this.formVisible = false; this.detail = null; this.detailVisible = false; this.pendingAction = null; this.confirmVisible = false; this.receipt = null
        this.loading = false; this.buildingsLoading = false; this.saving = false; this.acting = false; this.buildingSaving = false; this.detailLoading = false; this.pagination.total = 0; this.buildingTotal = 0
        this.error = `${errorMessage(error, fallback)}；已清除先前教室与楼栋内容。`
      } else this[field] = (isConflictResult(error) ? '事实已变化，保留输入，请重新核对。' : '') + errorMessage(error, fallback)
    },
    async loadBuildings(page = 1) {
      const rev = ++this.buildingRevision; this.buildingsLoading = true; this.buildingsError = ''
      try { const data = await classroomCatalogApi.buildings({ keyword: this.buildingKeyword, page }); if (rev !== this.buildingRevision) return; this.buildings = data.items; this.buildingPage = page; this.buildingTotal = data.total; this.selectedBuilding = this.buildings.find(b => b.buildingId === this.filters.buildingId) || null }
      catch (e) { if (rev === this.buildingRevision) { this.buildings = []; this.selectedBuilding = null; this.handleFailure(e, 'buildingsError', '教学楼加载失败') } }
      finally { if (rev === this.buildingRevision) this.buildingsLoading = false }
    },
    selectBuilding(building) { this.selectedBuilding = building; this.filters.buildingId = building?.buildingId || ''; this.filters.floorNo = ''; this.search() },
    selectFloor(floor) { this.filters.floorNo = floor; this.search() },
    openBuilding(building) { this.buildingEditingId = building?.buildingId || ''; this.buildingError = ''; this.buildingForm = building ? { ...building, expectedVersion: building.version } : { buildingCode: '', buildingName: '', campusCode: '', floorCount: 5 } },
    async saveBuilding() {
      if (this.buildingSaving || !this.can(this.buildingEditingId ? 'update' : 'create')) return
      if (!this.$el.querySelector('.cr-building-form')?.reportValidity()) return
      const rev = this.contextRevision; this.buildingSaving = true; this.buildingError = ''
      try { const b = await classroomCatalogApi.saveBuilding(this.buildingForm, this.buildingEditingId); if (rev !== this.contextRevision) return; const isNew = !this.buildingEditingId; this.buildingForm = null; this.buildingKeyword = b.buildingCode; await this.loadBuildings(); this.selectBuilding(b); if (isNew) this.openBatch('generate') }
      catch (e) { if (rev === this.contextRevision) this.handleFailure(e, 'buildingError', '教学楼未保存，请重试') }
      finally { if (rev === this.contextRevision) this.buildingSaving = false }
    },
    openBatch(mode) { if (!this.can('create') || (mode === 'generate' && !this.selectedBuilding)) return; this.batchMode = mode },
    rememberBatch(batchNo) { if (this.$route.query.batchNo !== batchNo) this.$router.replace({ query: { ...this.$route.query, batchNo } }) },
    async closeBatch() { if (this.$refs.batchWorkspace?.busy || (this.$refs.batchWorkspace?.dirty && !await systemConfirm({ title:'确认返回教室清单', message:'清单修改尚未重新预检，返回后本次修改会丢失。', confirmText:'放弃修改并返回', type:'danger' }))) return; const query = { ...this.$route.query }; delete query.batchNo; await this.$router.replace({ query }); this.batchMode = ''; this.loadBuildings(); this.load() },
    async finishBatch() { const query = { ...this.$route.query }; delete query.batchNo; await this.$router.replace({ query }); this.batchMode = ''; this.loadBuildings(); this.load() },
    can(action) { return matchPermission(this.ctx.permissionPatterns || [], `academicAffairs.classroom.${action}`) },
    restoreFilters() {
      const query = this.$route.query
      this.filters = { keyword: typeof query.keyword === 'string' ? query.keyword : '', roomType: this.typeOptions.some(item => item.value === query.roomType) ? query.roomType : '', status: this.statusOptions.some(item => item.value === query.status) ? query.status : '', buildingId: typeof query.buildingId === 'string' && /^\d+$/.test(query.buildingId) ? query.buildingId : '', floorNo: typeof query.floorNo === 'string' && /^\d+$/.test(query.floorNo) ? query.floorNo : '' }; this.selectedBuilding = this.buildings.find(b => b.buildingId === this.filters.buildingId) || null
      const page = Number(query.page)
      this.pagination.page = Number.isSafeInteger(page) && page > 0 ? page : 1
    },
    async updateQuery(page = 1) {
      this.pagination.page = page
      const query = { ...this.$route.query }
      for (const key of ['keyword', 'roomType', 'status', 'buildingId', 'floorNo']) { if (this.filters[key] !== '' && this.filters[key] != null) query[key] = String(this.filters[key]).trim(); else delete query[key] }
      if (page > 1) query.page = String(page); else delete query.page
      if (JSON.stringify(query) === JSON.stringify(this.$route.query)) return this.load()
      await this.$router.replace({ query })
    },
    search() { return this.updateQuery(1) },
    selectStatus(status) { this.filters.status = status; return this.search() },
    reset() { this.filters = { ...EMPTY_FILTERS(), buildingId: this.filters.buildingId }; return this.search() },
    onPageChange(page) { return this.updateQuery(page) },
    async load() {
      const revision = ++this.loadRevision
      this.loading = true; this.error = ''; this.rows = []; this.pagination.total = 0
      try {
        const res = await academicAffairsApi.listClassrooms({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
        if (revision !== this.loadRevision) return
        if (res.code !== 0) throw res
        this.rows = res.data.items; this.pagination.total = res.data.total
        if (!this.rows.length && this.pagination.page > 1 && this.pagination.total <= (this.pagination.page - 1) * this.pagination.pageSize) return this.updateQuery(Math.max(1, Math.ceil(this.pagination.total / this.pagination.pageSize)))
      } catch (error) { if (revision === this.loadRevision) this.handleFailure(error, 'error', '教室列表加载失败，请重试。') }
      finally { if (revision === this.loadRevision) this.loading = false }
    },
    statusType(status) { return status === 'AVAILABLE' ? 'success' : status === 'MAINTENANCE' ? 'warning' : 'default' },
    examSeatText(value) { return value === null || value === undefined || value === '' ? '考试座位未设置（沿用教学座位）' : `${value} 考试座位` },
    ruleText(value) { return typeof value === 'boolean' ? (value ? '允许' : '禁止') : '服务端未提供' },
    ruleValue(value) { return typeof value === 'boolean' ? String(value) : '' },
    ruleShort(value, label) { return typeof value === 'boolean' ? `${label}${value ? '允许' : '禁止'}` : `${label}未提供` },
    focusField(id) { this.$nextTick(() => this.$el.querySelector(`[data-field="${id}"] input, [data-field="${id}"] textarea, [data-field="${id}"] select`)?.focus()) },
    openCreate(source) {
      if (!this.can('create') || this.saving) return
      this.editingId = ''; this.editingStatus = ''; this.form = EMPTY_FORM()
      if (source) for (const key of ['buildingId', 'floorNo', 'buildingCode', 'buildingName', 'roomType', 'campusCode']) this.form[key] = source[key] ?? this.form[key]
      if (source?.buildingId && this.filters.floorNo && this.filters.floorNo !== '0') this.form.floorNo = Number(this.filters.floorNo)
      this.beginForm(source ? 'cr-room-code' : 'cr-building-code')
    },
    async openEdit(row) {
      if (!this.can('update') || this.saving) return
      const revision = this.contextRevision
      this.saving = true; this.formError = ''
      try {
        const exact = await academicAffairsApi.getClassroom(row.classroomId)
        if (revision !== this.contextRevision) return
        if (exact.code !== 0) throw exact
        const formal = exact.data || {}, defaults = EMPTY_FORM()
        if (!/^[1-9]\d*$/.test(String(formal.classroomId ?? '')) || String(formal.classroomId) !== String(row.classroomId) || !Number.isSafeInteger(formal.version) || formal.version < 0) throw new Error('教室正式资料与当前对象不一致，资料待核对。')
        this.editingId = formal.classroomId; this.editingStatus = formal.status
        this.form = Object.fromEntries(Object.keys(defaults).map(key => [key, formal[key] ?? defaults[key]]))
        for (const key of ['allowSchedule', 'allowExam', 'allowBorrow']) this.form[key] = typeof formal[key] === 'boolean' ? formal[key] : null
        this.form.examSeats = formal.examSeats === null || formal.examSeats === undefined ? null : formal.examSeats
        this.form.expectedVersion = formal.version
        this.beginForm('cr-building-code')
      } catch (error) { if (revision === this.contextRevision) this.handleFailure(error, 'error', '教室正式资料读取失败，无法编辑。') }
      finally { if (revision === this.contextRevision) this.saving = false }
    },
    beginForm(focus) { this.closeDetail(); this.formError = ''; this.fieldErrors = {}; this.originalForm = JSON.stringify(this.form); this.formVisible = true; this.focusField(focus) },
    async closeForm() { if (this.saving || (this.dirty && !await systemConfirm({ title:'确认放弃教室修改', message:'当前教室资料尚未保存。', confirmText:'放弃修改', type:'danger' }))) return; this.formVisible = false; this.form = EMPTY_FORM(); this.formError = ''; this.fieldErrors = {} },
    reuseBuilding(building) { if (this.saving) return; this.form.buildingCode = building.buildingCode; this.form.buildingName = building.buildingName; this.focusField('cr-room-code') },
    onPickRemark(text) { const el = this.$refs.remarkInput?.$refs.el; const { value, selStart, selEnd } = insertAtCursor(el, this.form.remark, text); this.form.remark = value; this.$nextTick(() => applyInsertion(el, selStart, selEnd)) },
    validateForm() {
      const errors = {}, ids = { buildingCode: 'cr-building-code', buildingName: 'cr-building-name', roomCode: 'cr-room-code', capacity: 'cr-capacity', examSeats: 'cr-exam-seats', allowSchedule: 'cr-allow-schedule', allowExam: 'cr-allow-exam', allowBorrow: 'cr-allow-borrow' }
      for (const [key, label] of [['buildingCode', '楼栋编码'], ['buildingName', '楼栋名称'], ['roomCode', '教室编号']]) if (!this.form[key].trim()) errors[key] = `请填写${label}`
      if (this.form.capacity === null || this.form.capacity === '' || !Number.isInteger(Number(this.form.capacity)) || Number(this.form.capacity) < 0 || Number(this.form.capacity) > 1000) errors.capacity = '请填写 0–1000 之间的整数座位数'
      if (this.form.examSeats !== null && this.form.examSeats !== '' && (!Number.isInteger(Number(this.form.examSeats)) || Number(this.form.examSeats) < 0 || Number(this.form.examSeats) > 1000)) errors.examSeats = '考试座位须为 0–1000 之间的整数；0 会按零考位保存'
      for (const key of ['allowSchedule', 'allowExam', 'allowBorrow']) if (typeof this.form[key] !== 'boolean') errors[key] = '请选择允许或禁止，不能根据专用教室属性推断'
      this.fieldErrors = errors
      const first = Object.keys(errors)[0]
      if (first) this.focusField(ids[first])
      return !first
    },
    async submitForm(keepBuilding = false) {
      if (this.saving || !this.can(this.editingId ? 'update' : 'create') || !this.validateForm()) return
      const revision = this.contextRevision, editingId = this.editingId
      const body = Object.fromEntries(Object.entries(this.form).map(([key, value]) => [key, typeof value === 'string' ? value.trim() : value]))
      body.examSeats = body.examSeats === '' || body.examSeats === null ? null : Number(body.examSeats)
      this.saving = true; this.formError = ''
      try {
        const res = editingId ? await academicAffairsApi.updateClassroom(editingId, body) : await academicAffairsApi.createClassroom(body)
        if (revision !== this.contextRevision) return
        if (res.code !== 0) throw res
        const id = res.data?.classroomId || editingId
        const formal = id ? await academicAffairsApi.getClassroom(id) : null
        if (revision !== this.contextRevision) return
        if (formal && isDeniedResult(formal)) throw formal
        const confirmed = formal?.code === 0 && String(formal.data?.classroomId) === String(id) && this.rulesMatch(formal.data, body)
        this.receipt = confirmed ? { ...formal.data, action: editingId ? '资料已更新，已读取正式对象' : '教室已创建，已读取正式对象' } : { classroomId: id, roomName: res.data?.roomName || body.roomName || body.buildingName + body.roomCode, action: '保存结果待确认，请重新读取教室资料' }
        if (keepBuilding && !editingId) {
          this.form = { ...EMPTY_FORM(), ...Object.fromEntries(['buildingCode', 'buildingName', 'roomType', 'capacity', 'examSeats', 'isExclusive', 'allowSchedule', 'allowExam', 'allowBorrow', 'campusCode'].map(key => [key, body[key]])) }
          this.originalForm = JSON.stringify(this.form); this.focusField('cr-room-code')
        } else { this.formVisible = false; this.form = EMPTY_FORM() }
        await this.load()
        await this.loadBuildings(this.buildingPage)
      } catch (error) { if (revision === this.contextRevision) this.handleFailure(error, 'formError', '保存失败，已保留填写内容，请核对后重试。') }
      finally { if (revision === this.contextRevision) this.saving = false }
    },
    rulesMatch(formal, requested) {
      const formalExamSeats = formal?.examSeats === null || formal?.examSeats === undefined ? null : Number(formal.examSeats)
      return formalExamSeats === requested.examSeats && ['allowSchedule', 'allowExam', 'allowBorrow'].every(key => typeof formal?.[key] === 'boolean' && formal[key] === requested[key])
    },
    async openDetail(row) { this.detailId = row.classroomId; this.detailVisible = true; await this.loadDetail() },
    async loadDetail() {
      const revision = ++this.detailRevision
      this.detailLoading = true; this.detailError = ''; this.detail = null
      try {
        const res = await academicAffairsApi.getClassroom(this.detailId)
        if (revision !== this.detailRevision) return
        if (res.code !== 0) throw res
        this.detail = res.data
      } catch (error) { if (revision === this.detailRevision) this.handleFailure(error, 'detailError', '教室资料加载失败，请重试。') }
      finally { if (revision === this.detailRevision) this.detailLoading = false }
    },
    closeDetail() { this.detailRevision++; this.detailVisible = false; this.detail = null },
    goSchedule(row) { if (!this.can('view')) return; this.closeDetail(); this.$router.push(`/admin/academic-affairs/schedule/room/${encodeURIComponent(row.classroomId)}`) },
    askStatus(row, target) {
      if (!this.can('update') || this.acting) return
      const label = { AVAILABLE: '恢复可用', DISABLED: '停用教室', MAINTENANCE: '标记维修中' }[target]
      this.confirmTitle = label; this.confirmText = label; this.confirmType = target === 'AVAILABLE' ? 'primary' : 'warning'
      this.confirmMessage = `将「${row.roomName}」${label}。${target === 'AVAILABLE' ? '恢复后可在排课时选择。' : '调整后将不再出现在可用教室选项中，请同时核对已有课程安排。'}`
      this.pendingAction = { kind: 'status', id: row.classroomId, roomName: row.roomName, target }; this.actionError = ''; this.confirmVisible = true
    },
    askDelete(row) {
      if (!this.can('delete') || this.acting) return
      this.confirmTitle = '删除教室'; this.confirmText = '删除教室'; this.confirmType = 'danger'; this.confirmMessage = `确认将「${row.roomName}」从教室资源目录移除？历史课表中的教室名称记录将保留。`
      this.pendingAction = { kind: 'delete', id: row.classroomId, roomName: row.roomName }; this.actionError = ''; this.confirmVisible = true
    },
    async onConfirm() {
      const action = this.pendingAction
      if (!action || this.acting || !this.can(action.kind === 'delete' ? 'delete' : 'update')) return
      const revision = this.contextRevision
      this.acting = true; this.actionError = ''
      try {
        const res = action.kind === 'status' ? await academicAffairsApi.setClassroomStatus(action.id, action.target) : await academicAffairsApi.deleteClassroom(action.id)
        if (revision !== this.contextRevision) return
        if (res.code !== 0) throw res
        this.confirmVisible = false; this.pendingAction = null; this.closeDetail()
        this.receipt = { classroomId: action.kind === 'delete' ? '' : action.id, roomName: action.roomName, action: action.kind === 'delete' ? '已从目录移除' : `已${this.statusOptions.find(item => item.value === action.target)?.label}` }
        await this.load()
        await this.loadBuildings(this.buildingPage)
      } catch (error) { if (revision === this.contextRevision) this.handleFailure(error, 'actionError', '操作失败，请重试。') }
      finally { if (revision === this.contextRevision) this.acting = false }
    }
  }
}
</script>
<style scoped>
.cr-view-tools{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 20px 16px}.cr-view-tools .cr-status-hint{margin:0}.cr-view-tools>div{display:flex;flex:none}.cr-view-tools button{font:inherit;font-size:12px;border:1px solid var(--border-base);background:var(--bg-card);color:var(--text-secondary);padding:7px 10px;cursor:pointer}.cr-view-tools button:first-child{border-radius:6px 0 0 6px}.cr-view-tools button:last-child{border-radius:0 6px 6px 0}.cr-view-tools button[aria-pressed=true]{color:var(--pri);background:var(--pri-bg)}.cr-room-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px;padding:4px 20px 20px}.cr-room-card{padding:16px;border:1px solid var(--border-base);border-radius:10px;text-align:left;background:var(--bg-card);font:inherit;color:var(--text-primary);cursor:pointer;min-width:0;transition:border-color .15s}.cr-room-card:hover{border-color:var(--pri);box-shadow:0 3px 12px #245cc013}.cr-room-card>div{display:flex;align-items:center;justify-content:space-between;gap:8px}.cr-room-card svg{height:24px;width:24px;color:var(--pri)}.cr-room-card>strong{display:block;font-size:22px;margin:14px 0 4px;overflow-wrap:anywhere}.cr-room-card>span{display:block;font-size:13px;overflow-wrap:anywhere}.cr-room-card>small{display:block;color:var(--text-secondary);font-size:11px;line-height:1.7;margin:8px 0 16px;overflow-wrap:anywhere}.cr-room-card footer{display:flex;justify-content:space-between;gap:6px;padding-top:12px;border-top:1px solid var(--border-base);color:var(--text-secondary);font-size:11px}.cr-room-card footer b{color:var(--text-primary);font-size:16px}.cr-room-card .cr-rule-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;margin-top:10px}.cr-rule-summary span{padding:4px 3px;border-radius:4px;background:var(--bg-page,#f5f8fe);color:var(--text-secondary);font-size:10px;text-align:center}.cr-rule-summary--table{display:grid;grid-template-columns:repeat(3,minmax(42px,1fr));gap:4px;min-width:150px}.cr-grid-pager{padding:0 20px 20px;display:flex;align-items:center;justify-content:flex-end;gap:10px}.cr-grid-pager span{font-size:12px;color:var(--text-secondary)}

.cr-root{min-width:0}.cr-root>:first-child:not(.classroom-workspace){padding:24px}.cr-catalog{display:grid;grid-template-columns:215px minmax(0,1fr);gap:18px;align-items:start}.cr-buildings{padding:14px 10px}.cr-buildings form{padding:0 4px 14px}.cr-buildings form label{display:block;font-weight:600;margin:4px 0 12px}.cr-buildings form>div{display:flex;gap:8px}.cr-buildings input,.cr-building-form input{width:100%;min-width:0;box-sizing:border-box;height:38px;border:1px solid var(--border-base);border-radius:6px;padding:0 10px;background:var(--bg-card);color:var(--text-primary);font:inherit}.cr-buildings form button{flex:none}.cr-building-item{display:flex;align-items:center;gap:10px;width:100%;padding:13px 10px;margin:4px 0;border:0;border-radius:8px;background:none;text-align:left;color:var(--text-primary);cursor:pointer}.cr-building-item.active{background:var(--pri-bg);color:var(--pri);box-shadow:inset 3px 0 var(--pri)}.cr-building-item svg{width:23px;height:23px;flex:none;color:var(--pri)}.cr-building-item span{min-width:0}.cr-building-item strong{font-size:13px;display:block;overflow-wrap:anywhere}.cr-building-item small{display:block;color:var(--text-secondary);font-size:11px;line-height:1.6;margin-top:5px}.cr-building-head{display:flex;justify-content:space-between;align-items:center;gap:14px;padding:20px}.cr-building-head h2{font-size:19px;margin:0 0 8px}.cr-building-head p{font-size:12px;color:var(--text-secondary);margin:0}.cr-building-head>div:last-child{display:flex;gap:8px;flex-wrap:wrap}.cr-floor-nav{display:flex;gap:8px;padding:0 20px 18px;overflow:auto}.cr-floor-nav button{flex:none;border:1px solid var(--border-base);border-radius:6px;background:var(--bg-card);color:var(--text-secondary);padding:7px 12px;cursor:pointer;font:inherit;font-size:12px}.cr-floor-nav button.active{background:var(--pri);border-color:var(--pri);color:white}.cr-building-form{padding:24px;max-width:800px;margin:auto}.cr-building-form label{display:grid;gap:8px;font-size:13px}.cr-building-form>.app-button{margin-top:22px}.cr-exclusive{display:flex;align-items:center;gap:8px;font-size:13px}.cr-exclusive input{accent-color:var(--pri)}.cr-building-pager{display:flex;gap:8px;margin-top:16px}
@media(max-width:1100px){.cr-catalog{grid-template-columns:1fr}.cr-buildings{display:flex;flex-wrap:wrap;gap:8px}.cr-buildings form{width:100%}.cr-building-item{width:auto}.cr-building-head{flex-wrap:wrap}}

.classroom-workspace{container-type:inline-size}.cr-intro{margin:0 0 20px;color:var(--text-secondary);font-size:13px;line-height:1.7}.cr-panel{min-width:0;border:1px solid var(--border-base);border-radius:12px;background:var(--bg-card);overflow:hidden}.cr-status-tabs{display:flex;gap:24px;padding:0 20px;border-bottom:1px solid var(--border-base);overflow-x:auto}.cr-status-tabs button{flex:none;min-height:48px;padding:12px 2px;border:0;border-bottom:3px solid transparent;background:none;color:var(--text-secondary);font:inherit;cursor:pointer}.cr-status-tabs button.active{border-bottom-color:var(--pri);color:var(--pri);font-weight:650}.cr-filters{display:flex;align-items:end;gap:12px;flex-wrap:wrap;padding:18px 20px}.cr-filter{display:grid;gap:6px;flex:0 1 175px;min-width:0;font-size:12px;color:var(--text-secondary)}.cr-filter--grow{flex:1 1 240px}.cr-filter :deep(.app-text-input),.cr-filter :deep(.app-select){box-sizing:border-box;width:100%;height:38px}.cr-status-hint{margin:0 20px 16px;font-size:12px;color:var(--text-secondary)}.cr-footnote{margin:16px 0 0;color:var(--text-secondary);font-size:12px;line-height:1.7}.cr-room-name{display:block;padding:4px 0;border:0;background:none;color:var(--text-primary);font:inherit;font-weight:650;text-align:left;cursor:pointer}.cr-room-name:hover{color:var(--pri)}.cr-sub{display:block;color:var(--text-secondary);font-size:12px;line-height:1.7}.cr-unit{margin-left:5px;color:var(--text-secondary)}.cr-row-actions{display:flex;align-items:center;gap:12px;white-space:nowrap}.cr-link{font:inherit;font-size:13px;min-height:34px;padding:4px 0;border:0;background:transparent;color:var(--pri);cursor:pointer}.cr-danger{color:var(--danger-500)}.cr-empty{display:grid;justify-items:center;gap:12px;padding:52px 24px;text-align:center}.cr-empty svg{width:36px;height:36px;padding:12px;box-sizing:content-box;border-radius:16px;background:var(--pri-bg);color:var(--pri)}.cr-empty h2{margin:4px 0 0;font-size:18px}.cr-empty p{max-width:420px;color:var(--text-secondary);font-size:13px;line-height:1.8}.cr-empty :deep(.app-button){margin-top:6px}.cr-receipt{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:18px;padding:14px 18px;border:1px solid var(--border-base);border-left:3px solid var(--success-500,#27845a);border-radius:8px;background:var(--bg-card)}.cr-receipt>div{flex:1}.cr-receipt p{margin:4px 0 0;color:var(--text-secondary);font-size:12px}.cr-editor{display:grid;grid-template-columns:minmax(0,1fr) 250px;gap:20px;align-items:start}.cr-section{padding:22px 24px;border-bottom:1px solid var(--border-base)}.cr-section:last-child{border:0}.cr-section-head{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin-bottom:18px}.cr-section-head h2{font-size:16px;margin:0}.cr-section-head small{font-size:12px;color:var(--text-secondary)}.cr-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px 22px}.cr-grid :deep(.app-form-item){min-width:0;margin-bottom:0}.cr-grid :deep(.app-text-input),.cr-grid :deep(.app-select),.cr-grid :deep(.app-number-input){width:100%;height:38px;box-sizing:border-box}.cr-grid :deep(.app-textarea){box-sizing:border-box;width:100%}.cr-wide{grid-column:1/-1}.cr-reuse{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:14px}.cr-reuse small{color:var(--text-secondary);font-size:12px}.cr-reuse button{border:1px solid var(--border-base);background:var(--pri-bg);color:var(--pri);border-radius:6px;padding:5px 9px;font-size:12px;cursor:pointer}.cr-preview{padding:22px}.cr-preview>small{font-size:12px;color:var(--text-secondary)}.cr-preview-icon{display:block;width:28px;height:28px;color:var(--pri);margin-top:20px}.cr-preview h2{margin:12px 0 6px;font-size:23px;line-height:1.4;overflow-wrap:anywhere}.cr-preview>p{font-size:13px;color:var(--text-secondary);line-height:1.7}.cr-preview dl{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:22px 0}.cr-preview dt{font-size:12px;color:var(--text-secondary)}.cr-preview dd{margin:4px 0 0;font-weight:600}.cr-preview-note{border-top:1px solid var(--border-base);padding-top:16px;margin-top:20px}.cr-editor-footer{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:14px;background:var(--bg-card);border:1px solid var(--border-base);border-radius:10px;margin-top:18px;padding:16px 20px}.cr-editor-footer>span{font-size:12px;color:var(--text-secondary)}.cr-editor-footer>div{display:flex;gap:8px;flex-wrap:wrap}.cr-extra{margin-top:18px;color:var(--text-secondary);font-size:12px}.cr-extra summary{cursor:pointer;padding:4px 0}.cr-extra :deep(.app-form-item){margin-top:14px;margin-bottom:0;max-width:300px}.cr-detail{padding:4px;line-height:1.7}.cr-detail-head{display:flex;align-items:center;justify-content:space-between;gap:12px}.cr-detail h2{font-size:21px;overflow-wrap:anywhere}.cr-detail p{color:var(--text-secondary);font-size:13px}.cr-detail dl{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:22px 0}.cr-detail dt{color:var(--text-secondary);font-size:12px}.cr-detail dd{margin:4px 0 0;white-space:pre-wrap;overflow-wrap:anywhere}.cr-detail-section{padding:18px 0;border-top:1px solid var(--border-base)}.cr-detail-section h3{font-size:14px;margin:0 0 8px}.cr-detail-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
@container(max-width:900px){.cr-editor{grid-template-columns:1fr}.cr-preview{display:none}}
@container(max-width:560px){.cr-grid{grid-template-columns:1fr}.cr-wide{grid-column:auto}.cr-section{padding:18px}.cr-filters{padding:16px}.cr-filter{flex:1 1 160px}.cr-filter--grow{flex-basis:100%}.cr-status-tabs{gap:20px;padding:0 16px}.cr-editor-footer{padding:14px}.cr-editor-footer>div{width:100%}.cr-editor-footer :deep(.app-button){white-space:normal;height:auto;min-height:38px}.cr-section-head{flex-wrap:wrap;gap:4px}.cr-intro{margin-bottom:16px}}
.classroom-workspace{gap:12px}.cr-intro{margin:0}.cr-building-head{padding:14px 20px}.cr-building-head h2{font-size:17px}.cr-floor-nav{flex-wrap:wrap;padding-bottom:10px;gap:6px;overflow:visible}.cr-floor-nav button,.cr-floor-nav select{height:32px;box-sizing:border-box;padding:5px 10px;font:inherit;font-size:12px}.cr-floor-nav select{max-width:110px;border:1px solid var(--border-base);border-radius:6px;background:var(--bg-card);color:var(--text-secondary)}.cr-status-tabs button{min-height:40px;padding:8px 2px}.cr-filters{padding:12px 20px}.cr-room-card{padding:14px}.cr-room-card>span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.cr-room-card>small{margin:7px 0 12px}.cr-room-card>strong{margin-top:10px}
</style>
