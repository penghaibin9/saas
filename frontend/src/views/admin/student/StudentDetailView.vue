<template>
  <ModulePageShell
    :title="detail ? `${detail.name || '未命名学生'} · 学生360` : '学生360'"
    subtitle="围绕同一名学生查看主档、学工摘要、生命周期事实和正式业务入口；敏感字段继续按真实权限脱敏。"
    :role-name="roleName"
    :data-scope-name="scopeName"
    watermark-purpose="学生360查阅"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <AppGlobalState
      :state="pageState"
      :title="stateTitle"
      :description="stateDescription"
      :error-code="errorCode"
      loading-text="正在加载学生360真实数据…"
      @retry="load"
      @back="goBack"
    >
      <template #actions>
        <div class="s360-state-actions">
          <button v-if="pageState === 'error'" type="button" class="s360-btn is-primary" @click="load">重新加载</button>
          <button type="button" class="s360-btn" @click="goBack">返回学生列表</button>
        </div>
      </template>

      <div v-if="detail" class="s360-page">
        <section class="s360-hero" aria-labelledby="student360-conclusion">
          <div class="s360-hero__main">
            <span class="s360-hero__eyebrow">STUDENT 360 · 当前学生结论</span>
            <h2 id="student360-conclusion">{{ conclusion }}</h2>
            <p>{{ conclusionDetail }}</p>
            <div class="s360-hero__tags">
              <AppStatusTag :type="statusTone(detail.studentStatus)" :label="statusLabel(detail.studentStatus)" dot />
              <RiskTag v-if="riskTopLevel !== 'NONE'" :level="riskTopLevel" />
              <AppStatusTag :type="projectionMeta.type" :label="projectionMeta.label" />
            </div>
          </div>
          <dl class="s360-hero__metrics" aria-label="学生360关键真值">
            <div v-for="item in heroMetrics" :key="item.key">
              <dt>{{ item.label }}</dt>
              <dd :class="{ 'is-text': item.text, 'is-gap': item.gap }">{{ item.value }}</dd>
              <small>{{ item.hint }}</small>
            </div>
          </dl>
        </section>

        <div class="s360-truth" role="note">
          <span class="s360-truth__icon" aria-hidden="true">真</span>
          <div>
            <strong>数据真值边界</strong>
            <p>主档来自现有学生详情接口；请假、宿舍、困难、奖助、处分、风险、谈话、家校、心理必要摘要与成长时间线只读取现有学工画像接口。完整学业、实习、毕设、就业聚合尚未返回时统一标记 DATA GAP，不以 0 或空数组冒充正常。</p>
          </div>
          <div class="s360-truth__tags">
            <AppStatusTag type="warning" label="DATA GAP · nextFollowAt" />
            <AppStatusTag type="warning" label="DATA GAP · recommendedAction" />
          </div>
        </div>

        <div v-if="projectionStatus === 'degraded'" class="s360-banner is-warning" role="status">
          <strong>部分学工摘要暂不可用</strong>
          <span>{{ affairsError }}；主档仍可查阅，不可用域不会显示成 0。</span>
          <button type="button" @click="loadAffairsProjection(detail.studentId, loadSeq)">重试摘要</button>
        </div>
        <div v-else-if="projectionStatus === 'restricted'" class="s360-banner" role="note">
          <strong>当前身份仅获学生主档权限</strong>
          <span>未读取学工跨域摘要；这不会扩大当前权限或数据范围。</span>
        </div>
        <div v-if="detail.voided" class="s360-banner is-danger" role="status">
          <strong>该学生主档已作废，仅可查阅与导出</strong>
          <span>作废原因：{{ detail.voidReason || '未记录' }}</span>
        </div>

        <section class="s360-profile">
          <div class="s360-avatar" aria-hidden="true">{{ avatar }}</div>
          <div class="s360-profile__main">
            <strong>{{ detail.name || '未命名学生' }}</strong>
            <p>{{ detail.studentNo || '学号未登记' }} · {{ orgLine }}</p>
            <div>
              <span>身份核验：{{ identityLabel(detail.identityVerifyStatus) }}</span>
              <span>账号：{{ bindLabel(detail.accountBindStatus) }}</span>
              <span>入学：{{ detail.enrollDate || '未登记' }}</span>
              <span>辅导员：{{ detail.counselorName || '未配置' }}</span>
            </div>
          </div>
          <div class="s360-completeness">
            <b>{{ completeness }}%</b>
            <span>主档完整度</span>
            <i><em :style="{ width: `${completeness}%` }" /></i>
          </div>
        </section>

        <section v-if="quickActions.length" class="s360-quick">
          <div class="s360-quick__copy">
            <span>围绕当前学生办理</span>
            <strong>进入原业务工作台继续处理</strong>
            <small>这里只传递 studentId、学生显示上下文、intent 与站内 returnTo；状态和 allowedActions 仍由目标页面与服务端校验。</small>
          </div>
          <div class="s360-quick__grid">
            <button v-for="action in quickActions" :key="action.key" type="button" @click="startStudentAction(action)">
              <span aria-hidden="true">{{ action.icon }}</span><b>{{ action.label }}</b><em>去办理 →</em>
            </button>
          </div>
        </section>

        <nav class="s360-tabs" aria-label="学生360内容页签">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            type="button"
            :class="{ 'is-active': activeTab === tab.key }"
            :aria-current="activeTab === tab.key ? 'page' : undefined"
            @click="setTab(tab.key)"
          >{{ tab.label }}</button>
        </nav>

        <div v-show="activeTab === 'overview'" class="s360-overview">
          <section class="s360-card">
            <header><div><h3>当前关注事项</h3><p>按学生聚合跨域事实；具体写操作仍进入原工作台。</p></div><AppStatusTag :type="projectionMeta.type" :label="projectionMeta.label" /></header>
            <div v-if="affairsLoading" class="s360-loading">正在加载当前关注摘要…</div>
            <EmptyState v-else-if="projectionStatus === 'restricted'" title="当前身份无学工摘要权限" description="学生主档仍可正常查阅；请切换授权身份后再查看学工跨域摘要。" />
            <EmptyState v-else-if="!affairsProfile" title="学工摘要暂不可用" :description="affairsError || '服务端未返回该学生的学工画像摘要。'" />
            <div v-else class="s360-domain-grid">
              <button
                v-for="card in focusCards"
                :key="card.key"
                type="button"
                :class="[`is-${card.tone}`, { 'is-disabled': !card.path }]"
                :disabled="!card.path"
                @click="openFocus(card)"
              >
                <div><span class="s360-domain-icon">{{ card.icon }}</span><strong>{{ card.label }}</strong><AppStatusTag :type="card.tagType" :label="card.tag" /></div>
                <b>{{ card.value }}</b>
                <p>{{ card.description }}</p>
                <small v-if="card.path">进入正式业务 →</small>
              </button>
            </div>
          </section>

          <aside class="s360-card s360-timeline-card">
            <header><div><h3>近期成长时间线</h3><p>只展示已进入服务端阶段事件的正式记录。</p></div></header>
            <div v-if="affairsLoading && !timelineItems.length" class="s360-loading">正在加载时间线…</div>
            <EmptyState v-else-if="!timelineItems.length" title="暂无可展示的成长事件" description="这不表示没有其他业务记录；当前时间线只读取已形成正式阶段事件的数据。" />
            <ol v-else class="s360-timeline">
              <li v-for="item in timelineItems" :key="item.eventId">
                <span aria-hidden="true" />
                <div><strong>{{ item.title }}</strong><p v-if="item.detail">{{ item.detail }}</p><small>{{ item.occurredAt || '时间未记录' }} · {{ item.moduleLabel }}</small></div>
              </li>
            </ol>
          </aside>
        </div>

        <section v-show="activeTab === 'basic'" class="s360-card">
          <header><div><h3>基础信息</h3><p>{{ canSensitive ? '当前角色可见授权明文。' : '敏感字段已按权限脱敏。' }}</p></div></header>
          <div class="s360-kv-grid"><div v-for="item in basicKvs" :key="item.key"><span>{{ item.label }}</span><strong>{{ item.value }}</strong></div></div>
        </section>

        <section v-show="activeTab === 'status'" class="s360-card">
          <header><div><h3>学籍与状态</h3><p>此处只读；学籍写入继续进入教务学籍异动流程。</p></div><button type="button" class="s360-link" @click="$router.push('/admin/student/status')">进入学籍台账 →</button></header>
          <EmptyState v-if="!statusHistory.length" title="当前详情接口未返回学籍变更历史" description="这不表示学生没有历史异动；请进入正式学籍台账查询。" />
          <ol v-else class="s360-timeline"><li v-for="item in statusHistory" :key="item.id"><span aria-hidden="true" /><div><strong>{{ statusLabel(item.fromStatus) }} → {{ statusLabel(item.toStatus) }}</strong><p>{{ item.reason || '未填写原因' }}</p><small>{{ item.operatedAt || '时间未记录' }} · {{ item.operator || '系统' }}</small></div></li></ol>
        </section>

        <div v-show="activeTab === 'campus'" class="s360-two-col">
          <section class="s360-card"><header><div><h3>数字迎新</h3><p>只展示当前详情接口已经返回的真实步骤。</p></div></header><EmptyState v-if="!orientationSteps.length" title="迎新步骤未进入当前聚合合同" description="请进入数字迎新工作区查看报到资格、办理进度和异常闭环。" /><ol v-else class="s360-timeline"><li v-for="item in orientationSteps" :key="`${item.name}-${item.time}`"><span aria-hidden="true" /><div><strong>{{ item.name }}</strong><small>{{ item.time || '时间未记录' }}</small></div></li></ol></section>
          <section class="s360-card"><header><div><h3>在校服务摘要</h3><p>来自现有学工画像服务端聚合。</p></div></header><EmptyState v-if="!affairsProfile" title="在校服务摘要暂不可用" :description="affairsError || '当前身份未获学工摘要权限。'" /><div v-else class="s360-kv-grid"><div><span>累计请假</span><strong>{{ realNumber(affairsProfile.leaveSummary?.total) }} 次</strong></div><div><span>当前宿舍</span><strong>{{ dormText }}</strong></div><div><span>困难认定</span><strong>{{ aidText }}</strong></div><div><span>已获资助</span><strong>{{ realNumber(affairsProfile.fundingSummary?.grantedCount) }} 项</strong></div><div><span>生效处分</span><strong>{{ disciplineText }}</strong></div><div><span>心理必要摘要</span><strong>{{ affairsProfile.psyFlag || '未返回' }}</strong></div></div></section>
        </div>

        <section v-show="activeTab === 'academic'" class="s360-card">
          <header><div><h3>学业过程</h3><p>仅展示当前接口真实返回内容。</p></div><AppStatusTag v-if="isAcademicPartial" type="info" label="PARTIAL" /></header>
          <EmptyState v-if="!hasAcademicData" title="完整学业聚合仍是 DATA GAP" description="当前学生详情门面未返回可信课程、学分与预警聚合；页面不使用 0 冒充学业正常。" />
          <template v-else><div class="s360-kv-grid"><div><span>平均绩点</span><strong>{{ detail.academic.gpa || '未返回' }}</strong></div><div><span>已修学分</span><strong>{{ academicCreditText }}</strong></div><div><span>预警等级</span><strong>{{ warningLevelLabel(detail.academic.warningLevel) }}</strong></div></div><div class="s360-table-wrap"><table v-if="detail.academic.courses?.length" class="s360-table"><thead><tr><th>课程</th><th>学期</th><th>成绩</th><th>重修</th></tr></thead><tbody><tr v-for="course in detail.academic.courses" :key="`${course.name}-${course.term}`"><td><strong>{{ course.name }}</strong></td><td>{{ course.term }}</td><td>{{ course.score }}</td><td>{{ course.retake ? '是' : '—' }}</td></tr></tbody></table></div></template>
        </section>

        <div v-show="activeTab === 'career'" class="s360-three-col">
          <section v-for="card in careerCards" :key="card.key" class="s360-card"><header><div><h3>{{ card.title }}</h3><p>{{ card.subtitle }}</p></div></header><EmptyState v-if="!card.record" :title="`${card.title}聚合未返回`" :description="card.gap" /><div v-else class="s360-kv-list"><div v-for="item in card.items" :key="item.label"><span>{{ item.label }}</span><strong>{{ item.value }}</strong></div></div></section>
        </div>

        <section v-show="activeTab === 'risk'" class="s360-card">
          <header><div><h3>风险与跟进</h3><p>Student 360 不复制风险 allowedActions，也不提供“我来处理 / 关闭 / 升级”等写动作。</p></div><button v-if="canDomain('studentAffairs.risk.view')" type="button" class="s360-link" @click="openRiskWorkbench">进入风险工作台 →</button></header>
          <EmptyState v-if="!affairsProfile" title="风险摘要暂不可用" :description="affairsError || '当前身份未获学工风险摘要权限。'" />
          <template v-else><div class="s360-risk-summary"><div><span>未关闭风险</span><strong>{{ realNumber(affairsProfile.riskSummary?.openCount) }}</strong></div><div><span>最高等级</span><RiskTag v-if="riskTopLevel !== 'NONE'" :level="riskTopLevel" /><AppStatusTag v-else type="success" label="暂无未关闭风险" /></div><div><span>心理必要摘要</span><strong>{{ affairsProfile.psyFlag || '未返回' }}</strong></div></div><p class="s360-boundary">具体风险记录、责任人、版本和可执行动作请进入风险工作台；前端不得从摘要推断 recommendedAction。</p></template>
        </section>

        <div v-show="activeTab === 'audit'" class="s360-two-col">
          <section class="s360-card"><header><div><h3>信息更正申请</h3><p>证件类关键字段继续走正式更正审核。</p></div><button type="button" class="s360-link" @click="$router.push('/admin/student/corrections')">进入更正审核 →</button></header><EmptyState v-if="!corrections.length" title="当前详情接口未返回更正记录" description="这不表示没有申请；请进入信息更正审核工作区查询。" /><div v-else class="s360-kv-list"><div v-for="item in corrections" :key="item.id"><span>{{ item.fieldLabel }} · {{ item.submitTime }}</span><AppStatusTag :status="item.status" /></div></div></section>
          <section class="s360-card"><header><div><h3>学生主档审计记录</h3><p>只展示当前详情接口明确返回的单生审计投影。</p></div></header><EmptyState v-if="!auditTrail.length" title="暂无单生审计投影" description="编辑与导出仍继续写审计；此处不使用全局审计分页冒充当前学生完整审计。" /><div v-else class="s360-table-wrap"><table class="s360-table"><thead><tr><th>时间</th><th>操作人</th><th>动作</th><th>说明</th></tr></thead><tbody><tr v-for="item in auditTrail" :key="item.id"><td>{{ item.time }}</td><td><strong>{{ item.operator }}</strong></td><td>{{ auditActionLabel(item) }}</td><td>{{ item.detail }}</td></tr></tbody></table></div></section>
        </div>
      </div>
    </AppGlobalState>

    <AppDrawer :visible="editDrawer.visible" title="编辑基础信息" @update:visible="editDrawer.visible = $event">
      <div class="s360-form">
        <label><span>姓名</span><input v-model="editDrawer.form.name" /></label>
        <label><span>手机号</span><input v-model="editDrawer.form.phone" /></label>
        <label><span>辅导员</span><select v-model="editDrawer.form.counselorName"><option v-for="item in counselorOptions" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
        <p v-if="editDrawer.error" class="s360-form__error">{{ editDrawer.error }}</p>
        <div><AppButton variant="ghost" @click="editDrawer.visible = false">取消</AppButton><AppButton variant="primary" :disabled="editDrawer.submitting" @click="submitEdit">保存变更</AppButton></div>
        <small>变更继续携带 expectedVersion 并写字段级审计；证件类关键字段请走信息更正审核流程。</small>
      </div>
    </AppDrawer>

    <AppConfirmDialog
      :visible="exportDialog.visible"
      type="warning"
      title="导出学生档案"
      :message="detail ? `将导出 ${detail.name} 的学生档案：敏感字段自动脱敏，文件附水印，导出行为写入审计日志。` : ''"
      confirm-text="确认导出"
      require-reason
      reason-label="导出用途"
      reason-placeholder="如：学籍异动材料归档（不少于 5 个字）"
      :submitting="exportDialog.submitting"
      @update:visible="exportDialog.visible = $event"
      @confirm="submitExport"
    />
  </ModulePageShell>
</template>

<script>
import {
  ModulePageShell,
  ModuleToolbar,
  StatusTag as AppStatusTag,
  RiskTag,
  EmptyState
} from '@/components/business'
import { AppConfirmDialog, AppGlobalState } from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { studentApi } from '@/modules/student/api/student.api'
import studentAffairsApi from '@/modules/studentAffairs/api/studentAffairsB.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'
import { toast } from '@/utils/toast'
import { presentAuditRecord } from '@/utils/presentationSafety'

const FORBIDDEN_CODES = new Set(['FORBIDDEN', 'NO_PERMISSION', 'PERMISSION_DENIED', 'NO_DATA_SCOPE', 'UNAUTHORIZED'])
const EMPTY_CODES = new Set(['NOT_FOUND', 'STUDENT_NOT_FOUND'])
const VALID_TABS = new Set(['overview', 'basic', 'status', 'campus', 'academic', 'career', 'risk', 'audit'])
const MODULE_LABELS = { leave: '请假与返校', aid: '困难认定', funding: '奖助资助', discipline: '违纪处分', risk: '风险处置', talk: '谈心谈话', system: '系统事件' }

export default {
  name: 'StudentDetailView',
  components: { ModulePageShell, ModuleToolbar, AppStatusTag, RiskTag, EmptyState, AppConfirmDialog, AppGlobalState, AppButton, AppDrawer },
  props: { ctx: { type: Object, required: true } },
  data() {
    const tab = String(this.$route.query.tab || 'overview')
    return {
      loading: true,
      error: '',
      errorCode: '',
      detail: null,
      activeTab: VALID_TABS.has(tab) ? tab : 'overview',
      tabs: [
        { key: 'overview', label: '当前关注' }, { key: 'basic', label: '基础信息' },
        { key: 'status', label: '学籍与状态' }, { key: 'campus', label: '迎新与在校' },
        { key: 'academic', label: '学业过程' }, { key: 'career', label: '实习 · 毕设 · 就业' },
        { key: 'risk', label: '风险与跟进' }, { key: 'audit', label: '更正与审计' }
      ],
      affairsLoading: false,
      affairsLoaded: false,
      affairsError: '',
      affairsProfile: null,
      affairsTimeline: [],
      loadSeq: 0,
      editDrawer: { visible: false, form: { name: '', phone: '', counselorName: '' }, error: '', submitting: false },
      exportDialog: { visible: false, submitting: false }
    }
  },
  computed: {
    roleName() { return this.ctx?.currentRole?.roleName || '' },
    scopeName() { return this.ctx?.dataScope?.scopeName || '按当前身份' },
    counselorOptions() { return Array.isArray(this.ctx?.filterOptions?.counselors) ? this.ctx.filterOptions.counselors : [] },
    canViewPage() { return canCode(this.ctx, 'student.profile.view') || canCode(this.ctx, 'studentAffairs.student.view') },
    canLoadAffairs() { return canCode(this.ctx, 'studentAffairs.student.view') },
    canSensitive() {
      const action = this.ctx?.permissionActions?.viewSensitive
      return !!(action?.visible && action?.allowed)
    },
    pageState() {
      if (!this.canViewPage) return 'forbidden'
      if (this.loading) return 'loading'
      if (this.errorCode && FORBIDDEN_CODES.has(this.errorCode)) return 'forbidden'
      if (this.errorCode && EMPTY_CODES.has(this.errorCode)) return 'empty'
      if (this.error) return 'error'
      return this.detail ? 'ready' : 'empty'
    },
    stateTitle() {
      if (this.pageState === 'forbidden') return '当前身份无权查看学生360'
      if (this.pageState === 'empty') return '未找到可查看的学生主档'
      if (this.pageState === 'error') return '学生360加载失败'
      return ''
    },
    stateDescription() {
      if (this.pageState === 'forbidden') return '权限与数据范围必须同时满足；请返回列表选择当前范围内学生，或联系管理员核对授权。'
      if (this.pageState === 'empty') return '该学生不存在、已超出当前数据范围，或主档已按服务端规则不可见。'
      return this.error || ''
    },
    projectionStatus() {
      if (!this.canLoadAffairs) return 'restricted'
      if (this.affairsLoading) return 'loading'
      if (this.affairsError) return 'degraded'
      if (this.affairsProfile) return 'ready'
      return this.affairsLoaded ? 'empty' : 'loading'
    },
    projectionMeta() {
      return {
        ready: { type: 'success', label: '学工摘要 · REAL' }, loading: { type: 'processing', label: '学工摘要加载中' },
        degraded: { type: 'warning', label: '学工摘要 · DEGRADED' }, restricted: { type: 'info', label: '仅主档权限' },
        empty: { type: 'default', label: '学工摘要未返回' }
      }[this.projectionStatus]
    },
    toolbarActions() {
      const actions = [{ key: 'back', label: '返回列表', variant: 'ghost', disabled: false }]
      const permissions = this.ctx?.permissionActions || {}
      if (permissions.editStudent?.visible) actions.push({ key: 'edit', label: '编辑基础信息', disabled: !!this.detail?.voided || !permissions.editStudent.allowed, disabledReason: this.detail?.voided ? '该主档已作废，仅可查阅与导出' : permissions.editStudent.reason })
      if (permissions.exportStudents?.visible) actions.push({ key: 'export', label: '导出学生档案', disabled: !permissions.exportStudents.allowed, disabledReason: permissions.exportStudents.reason })
      return actions
    },
    quickActions() {
      if (this.detail?.voided) return []
      return [
        { key: 'talk', label: '发起谈话', icon: '谈', permission: 'studentAffairs.talk.create', path: '/admin/student-affairs/talk' },
        { key: 'family', label: '登记家校联系', icon: '家', permission: 'studentAffairs.homeSchool.record.create', path: '/admin/student-affairs/family' },
        { key: 'risk', label: '新建风险', icon: '险', permission: 'studentAffairs.risk.create', path: '/admin/student-affairs/risk' },
        { key: 'dorm', label: '发起调宿', icon: '宿', permission: 'studentAffairs.dorm.transfer.create', path: '/admin/student-affairs/dorm/transfer' },
        { key: 'aid', label: '受理困难', icon: '困', permission: 'studentAffairs.aid.create', path: '/admin/student-affairs/aid' },
        { key: 'funding', label: '受理奖助', icon: '助', permission: 'studentAffairs.funding.create', path: '/admin/student-affairs/funding' }
      ].filter((action) => canCode(this.ctx, action.permission))
    },
    avatar() { return String(this.detail?.name || '生').trim().slice(0, 1) },
    completeness() {
      const value = Number(this.detail?.dataCompleteness)
      return Number.isFinite(value) ? Math.max(0, Math.min(100, Math.round(value))) : 0
    },
    orgLine() { return [this.detail?.collegeName, this.detail?.majorName, this.detail?.className, this.detail?.grade].filter(Boolean).join(' / ') || '组织归属未登记' },
    riskTopLevel() { return String(this.affairsProfile?.riskSummary?.topLevel || this.detail?.riskLevel || 'NONE').toUpperCase() },
    conclusion() {
      if (this.detail?.voided) return `该学生主档已作废，仅可查阅历史事实${this.detail.voidReason ? `；原因：${this.detail.voidReason}` : ''}。`
      if (this.projectionStatus === 'restricted') return '学生主档已加载；当前身份只可查看已授权的主档信息。'
      if (this.projectionStatus === 'loading') return '学生主档已加载，正在读取当前身份可见的学工摘要。'
      if (this.projectionStatus === 'degraded') return '学生主档已加载；部分学工摘要暂不可用。'
      const risk = Number(this.affairsProfile?.riskSummary?.openCount || 0)
      const discipline = this.affairsProfile?.disciplineSummary || {}
      if (risk > 0) return `当前有 ${risk} 条未关闭风险，最高等级为${this.riskLevelLabel(this.riskTopLevel)}。`
      if (!discipline.restricted && Number(discipline.activeCount || 0) > 0) return `当前有 ${Number(discipline.activeCount)} 条生效处分摘要，可进入正式工作台继续查看。`
      return '当前学工聚合未发现需要在本页强调的未关闭风险；可继续查阅历史事实和已授权业务。'
    },
    conclusionDetail() {
      if (this.projectionStatus === 'degraded') return '失败域不会显示为 0；请重试摘要或进入有权限的原业务工作台核查。'
      if (this.projectionStatus === 'restricted') return '页面不会因缺少学工权限而扩大查询范围；敏感字段仍按主档权限脱敏。'
      return '本页只汇总服务端真实只读事实，不推断统一下一次回访，也不替代各业务状态机生成推荐动作。'
    },
    heroMetrics() {
      const base = [
        { key: 'completeness', label: '主档完整度', value: `${this.completeness}%`, hint: '学生主档真实字段' },
        { key: 'status', label: '学籍状态', value: this.statusLabel(this.detail?.studentStatus), hint: '只读投影', text: true }
      ]
      if (this.affairsProfile) {
        base.push(
          { key: 'risk', label: '未关闭风险', value: `${this.realNumber(this.affairsProfile.riskSummary?.openCount)} 条`, hint: `最高等级 ${this.riskLevelLabel(this.riskTopLevel)}` },
          { key: 'talk', label: '谈话记录', value: `${this.realNumber(this.affairsProfile.talkSummary?.total)} 条`, hint: this.affairsProfile.talkSummary?.lastTalkAt ? `最近 ${this.formatDate(this.affairsProfile.talkSummary.lastTalkAt)}` : '暂无最近时间' }
        )
      } else {
        base.push(
          { key: 'identity', label: '身份核验', value: this.identityLabel(this.detail?.identityVerifyStatus), hint: '主档投影', text: true },
          { key: 'account', label: '账号状态', value: this.bindLabel(this.detail?.accountBindStatus), hint: '主档投影', text: true }
        )
      }
      return base
    },
    focusCards() {
      const p = this.affairsProfile
      if (!p) return []
      const studentId = String(this.detail.studentId)
      const risk = p.riskSummary || {}, leave = p.leaveSummary || {}, dorm = p.dormSummary || {}, aid = p.aidSummary || {}, funding = p.fundingSummary || {}, discipline = p.disciplineSummary || {}, talk = p.talkSummary || {}, family = p.familySummary || {}
      return [
        { key: 'risk', label: '风险', icon: '险', tone: Number(risk.openCount || 0) ? 'risk' : 'normal', value: `${this.realNumber(risk.openCount)} 条未关闭`, tag: this.riskLevelLabel(risk.topLevel), tagType: ['HIGH', 'CRITICAL'].includes(String(risk.topLevel || '').toUpperCase()) ? 'danger' : (Number(risk.openCount || 0) ? 'warning' : 'success'), description: '学生级真实风险摘要；具体动作继续由风险记录 allowedActions 与 version 决定。', path: this.canDomain('studentAffairs.risk.view') ? this.routeWithContext('/admin/student-affairs/risk', { studentId, status: 'OPEN' }) : '' },
        { key: 'leave', label: '请假与返校', icon: '假', tone: 'normal', value: `${this.realNumber(leave.total)} 条记录`, tag: '历史总数', tagType: 'info', description: '是否待审、在假、待销假或逾期，请进入正式请假工作区查看当前状态。', path: this.canDomain('studentAffairs.leave.view') ? this.routeWithContext('/admin/student-affairs/leave/ledger', { studentId }) : '' },
        { key: 'talk', label: '谈话与回访', icon: '谈', tone: 'normal', value: `${this.realNumber(talk.total)} 条记录`, tag: talk.lastTalkAt ? `最近 ${this.formatDate(talk.lastTalkAt)}` : '暂无时间', tagType: talk.lastTalkAt ? 'processing' : 'default', description: '只展示真实累计与最近谈话时间；统一 nextFollowAt 仍是 DATA GAP。', path: this.canDomain('studentAffairs.talk.view') ? this.routeWithContext('/admin/student-affairs/talk', { studentId }) : '' },
        { key: 'dorm', label: '宿舍与公寓', icon: '宿', tone: dorm.hasDorm ? 'normal' : 'muted', value: dorm.hasDorm ? (dorm.text || '已入住') : '暂无入住摘要', tag: dorm.hasDorm ? '当前住宿' : '未返回', tagType: dorm.hasDorm ? 'success' : 'default', description: '来自当前住宿关系；调宿、检查和异常继续进入宿舍工作区。', path: this.canDomain('studentAffairs.dorm.view') ? this.routeWithContext('/admin/student-affairs/dormitory', { studentId }) : '' },
        { key: 'aid', label: '困难与资助', icon: '助', tone: aid.inLibrary ? 'attention' : 'normal', value: aid.inLibrary ? `困难库 · ${aid.difficultLevel || '已认定'}` : '未进入困难库', tag: `${this.realNumber(funding.grantedCount)} 次资助`, tagType: Number(funding.grantedCount || 0) ? 'success' : 'default', description: '资格事实与资助次数来自现有服务端聚合；家庭经济明文继续受敏感权限与审计控制。', path: this.canDomain('studentAffairs.aid.view') ? this.routeWithContext('/admin/student-affairs/aid', { studentId }) : (this.canDomain('studentAffairs.funding.view') ? this.routeWithContext('/admin/student-affairs/funding', { studentId }) : '') },
        { key: 'discipline', label: '违纪处分', icon: '纪', tone: discipline.restricted ? 'muted' : (Number(discipline.activeCount || 0) ? 'attention' : 'normal'), value: discipline.restricted ? '摘要受限' : `${this.realNumber(discipline.activeCount)} 条生效`, tag: discipline.restricted ? '按角色限制' : '真实计数', tagType: discipline.restricted ? 'info' : (Number(discipline.activeCount || 0) ? 'warning' : 'success'), description: discipline.restricted ? '当前角色只可见必要提示，不展示处分明细。' : '审批、生效、申诉和解除继续进入正式处分工作台。', path: !discipline.restricted && this.canDomain('studentAffairs.discipline.view') ? this.routeWithContext('/admin/student-affairs/discipline', { studentId }) : '' },
        { key: 'family', label: '家校联系', icon: '家', tone: family.hasContact ? 'normal' : 'muted', value: `${this.realNumber(family.logCount)} 条联系记录`, tag: `${this.realNumber(family.contactCount)} 位联系人`, tagType: family.hasContact ? 'processing' : 'default', description: '只显示数量，不在 Student 360 回传家长手机号等敏感明文。', path: this.canDomain('studentAffairs.homeSchool.view') ? this.routeWithContext('/admin/student-affairs/family', { studentId }) : '' },
        { key: 'mental', label: '心理必要摘要', icon: '心', tone: p.psyFlag === '需关注' ? 'risk' : 'normal', value: p.psyFlag || '未返回', tag: '不含心理明细', tagType: p.psyFlag === '需关注' ? 'warning' : 'success', description: '普通 Student 360 只显示必要摘要；专项明细继续服从逐生授权。', path: this.canDomain('studentAffairs.risk.psyDetail.view') ? this.routeWithContext('/admin/student-affairs/mental', { studentId }) : '' }
      ]
    },
    timelineItems() {
      return (Array.isArray(this.affairsTimeline) ? this.affairsTimeline : []).map((item, index) => ({ eventId: item.eventId || `${item.eventType || 'event'}-${index}`, title: item.title || '学工阶段事件', detail: item.detail || '', occurredAt: this.formatDateTime(item.occurredAt), moduleLabel: MODULE_LABELS[item.module] || item.module || '学工事件' }))
    },
    basicKvs() {
      const d = this.detail || {}
      return [
        { key: 'name', label: '姓名', value: d.name || '未登记' }, { key: 'studentNo', label: '学号', value: d.studentNo || '未登记' },
        { key: 'gender', label: '性别', value: d.gender || '未登记' }, { key: 'phone', label: '手机号', value: this.mask(d.phone, 'phone') },
        { key: 'idCard', label: '身份证号', value: this.mask(d.idCard, 'idCard') }, { key: 'college', label: '学院', value: d.collegeName || '未登记' },
        { key: 'major', label: '专业', value: d.majorName || '未登记' }, { key: 'class', label: '班级', value: d.className || '未分班' },
        { key: 'grade', label: '年级', value: d.grade || '未登记' }, { key: 'enrollDate', label: '入学日期', value: d.enrollDate || '未登记' },
        { key: 'counselor', label: '辅导员', value: d.counselorName || '未配置' }, { key: 'updatedAt', label: '最近更新', value: d.updatedAt || '未记录' }
      ]
    },
    statusHistory() { return Array.isArray(this.detail?.statusHistory) ? this.detail.statusHistory : [] },
    orientationSteps() { return Array.isArray(this.detail?.orientation?.steps) ? this.detail.orientation.steps : [] },
    corrections() { return Array.isArray(this.detail?.corrections) ? this.detail.corrections : [] },
    auditTrail() { return Array.isArray(this.detail?.auditTrail) ? this.detail.auditTrail : [] },
    isAcademicPartial() { return this.detail?.capabilityStatus?.crossModule360Aggregation === 'PARTIAL' },
    hasAcademicData() {
      const academic = this.detail?.academic
      return !!(academic && ((Array.isArray(academic.courses) && academic.courses.length) || academic.gpa || Number(academic.earnedCredits) || Number(academic.requiredCredits) || academic.warningLevel))
    },
    academicCreditText() {
      const academic = this.detail?.academic || {}
      if (this.isAcademicPartial && !academic.earnedCredits && !academic.requiredCredits) return '未返回完整学分聚合'
      return `${academic.earnedCredits ?? '—'} / ${academic.requiredCredits ?? '—'}`
    },
    careerCards() {
      const d = this.detail || {}
      return [
        { key: 'internship', title: '岗位实习', subtitle: '企业、岗位、过程与指导', record: d.internship || null, gap: '当前 Student 360 接口未返回可信实习聚合。', items: d.internship ? [{ label: '企业 / 岗位', value: `${d.internship.enterpriseName || '未返回'} · ${d.internship.positionName || '未返回'}` }, { label: '状态', value: d.internship.statusLabel || d.internship.status || '未返回' }, { label: '近30天出勤率', value: d.internship.attendanceRate || '未返回' }, { label: '指导教师', value: d.internship.advisorName || '未返回' }] : [] },
        { key: 'graduation', title: '毕业设计', subtitle: '课题、阶段、成绩与指导', record: d.graduationDesign || null, gap: '当前 Student 360 接口未返回可信毕设聚合。', items: d.graduationDesign ? [{ label: '课题', value: d.graduationDesign.topic || '未返回' }, { label: '当前阶段', value: d.graduationDesign.stage || '未返回' }, { label: '指导教师', value: d.graduationDesign.advisorName || '未返回' }, { label: '成绩', value: d.graduationDesign.score || '未评定' }] : [] },
        { key: 'employment', title: '就业去向', subtitle: '意向、录用、协议与跟踪', record: d.employment || null, gap: '当前 Student 360 接口未返回可信就业聚合。', items: d.employment ? [{ label: '就业意向', value: d.employment.intent || '未返回' }, { label: '录用通知数', value: d.employment.offerCount ?? '未返回' }, { label: '协议状态', value: this.agreementStatusLabel(d.employment.agreementStatus) }, { label: '跟踪状态', value: this.trackStatusLabel(d.employment.trackStatus) }] : [] }
      ]
    },
    dormText() { return this.affairsProfile?.dormSummary?.hasDorm ? (this.affairsProfile.dormSummary.text || '已入住') : '暂无入住摘要' },
    aidText() { return this.affairsProfile?.aidSummary?.inLibrary ? `困难库 · ${this.affairsProfile.aidSummary.difficultLevel || '已认定'}` : '未进入困难库' },
    disciplineText() {
      const value = this.affairsProfile?.disciplineSummary || {}
      return value.restricted ? '按角色限制' : `${this.realNumber(value.activeCount)} 条`
    }
  },
  watch: {
    '$route.params.studentId'() { this.load() },
    '$route.query.tab'(value) { const tab = String(value || 'overview'); if (VALID_TABS.has(tab)) this.activeTab = tab }
  },
  created() { this.load() },
  methods: {
    canDomain(code) { return canCode(this.ctx, code) },
    optionLabel(group, value, fallback) {
      const rows = Array.isArray(this.ctx?.statusOptions?.[group]) ? this.ctx.statusOptions[group] : []
      return rows.find((item) => item.value === value)?.label || fallback
    },
    statusLabel(value) { return this.optionLabel('studentStatus', value, '学籍状态待确认') },
    statusTone(value) { return { ADMITTED: 'processing', ACTIVE: 'success', SUSPENDED: 'warning', GRADUATED: 'info', DROPPED: 'default', VOIDED: 'default' }[value] || 'default' },
    identityLabel(value) { return this.optionLabel('identityVerifyStatus', value, '核验状态待确认') },
    bindLabel(value) { return this.optionLabel('accountBindStatus', value, '账号状态待确认') },
    warningLevelLabel(value) { return this.optionLabel('warningLevel', value, value ? '预警等级待确认' : '未返回') },
    riskLevelLabel(value) { return ({ NONE: '无未关闭风险', LOW: '低风险', MEDIUM: '中风险', HIGH: '高风险', CRITICAL: '危急风险' })[String(value || 'NONE').toUpperCase()] || '风险等级待确认' },
    agreementStatusLabel(value) { return ({ NOT_SIGNED: '未签约', SIGNED: '已签约', VERIFIED: '已核验', TERMINATED: '已解除' })[String(value || '').toUpperCase()] || '协议状态待确认' },
    trackStatusLabel(value) { return ({ SEEKING: '求职中', EMPLOYED: '已就业', FURTHER_STUDY: '升学', ENTREPRENEURSHIP: '创业', UNEMPLOYED: '待就业' })[String(value || '').toUpperCase()] || '跟踪状态待确认' },
    auditActionLabel(row) { return presentAuditRecord(row).displayAction },
    realNumber(value) { const number = Number(value); return Number.isFinite(number) ? number : '—' },
    formatDate(value) { const text = String(value || '').replace('T', ' '); return text ? text.slice(0, 10) : '' },
    formatDateTime(value) { const text = String(value || '').replace('T', ' '); return text ? text.slice(0, 16) : '' },
    mask(value, type) {
      if (!value) return '未登记'
      if (this.canSensitive) return value
      const text = String(value)
      if (type === 'phone') return text.length >= 7 ? `${text.slice(0, 3)}****${text.slice(-4)}` : '已脱敏'
      return text.length >= 10 ? `${text.slice(0, 6)}********${text.slice(-4)}` : '已脱敏'
    },
    setTab(key) {
      if (!VALID_TABS.has(key)) return
      this.activeTab = key
      const query = { ...this.$route.query }
      if (key === 'overview') delete query.tab
      else query.tab = key
      this.$router.replace({ query }).catch(() => {})
    },
    internalReturnTo() {
      const fullPath = String(this.$route.fullPath || '')
      if (fullPath.startsWith('/admin/student/')) return fullPath
      return `/admin/student/${encodeURIComponent(String(this.detail?.studentId || this.$route.params.studentId || ''))}`
    },
    routeWithContext(path, query = {}) {
      if (!path) return ''
      return { path, query: { ...query, from: 'student360', returnTo: this.internalReturnTo() } }
    },
    openFocus(card) { if (card?.path) this.$router.push(card.path).catch(() => {}) },
    openRiskWorkbench() {
      if (!this.detail) return
      this.$router.push(this.routeWithContext('/admin/student-affairs/risk', { studentId: String(this.detail.studentId), status: 'OPEN' })).catch(() => {})
    },
    goBack() {
      const back = this.$router.options.history.state?.back
      if (back && String(back).startsWith('/admin/')) this.$router.back()
      else this.$router.push('/admin/student/list')
    },
    onToolbar(key) {
      if (key === 'back') this.goBack()
      if (key === 'edit' && this.detail?.voided) { toast.error('该学生主档已作废，仅可查阅与导出'); return }
      if (key === 'edit' && this.detail) this.editDrawer = { visible: true, error: '', submitting: false, form: { name: this.detail.name, phone: this.detail.phone, counselorName: this.detail.counselorName } }
      if (key === 'export') this.exportDialog = { visible: true, submitting: false }
    },
    startStudentAction(action) {
      if (!this.detail || !action || this.detail.voided) return
      this.$router.push({ path: action.path, query: { studentId: String(this.detail.studentId), studentNo: this.detail.studentNo || undefined, studentName: this.detail.name || undefined, intent: 'create', from: 'student360', returnTo: this.internalReturnTo() } }).catch(() => {})
    },
    async submitEdit() {
      if (!this.detail || this.detail.voided) return
      this.editDrawer.submitting = true
      this.editDrawer.error = ''
      const res = await studentApi.updateStudent(this.detail.studentId, { ...this.editDrawer.form, expectedVersion: this.detail.version })
      this.editDrawer.submitting = false
      if (res.code === 0) { this.editDrawer.visible = false; toast.success('基础信息已更新（已留痕）'); this.load() }
      else this.editDrawer.error = res.message || '保存失败'
    },
    async submitExport({ reason }) {
      if (!this.detail) return
      this.exportDialog.submitting = true
      const res = await studentApi.createExport({ scope: 'SELECTED', fieldKeys: ['name', 'studentNo', 'orgPath', 'studentStatus', 'phone', 'idCard'], purpose: 'WORK', remark: reason, rowCount: 1 })
      this.exportDialog.submitting = false
      if (res.code === 0) { this.exportDialog.visible = false; toast.success(`档案导出任务已创建：已脱敏、含水印，审计编号 ${res.data.auditId}`) }
      else toast.error(res.message || '导出任务创建失败')
    },
    resetAffairs() { this.affairsLoading = false; this.affairsLoaded = false; this.affairsError = ''; this.affairsProfile = null; this.affairsTimeline = [] },
    async loadAffairsProjection(studentId, seq = this.loadSeq) {
      this.resetAffairs()
      if (!this.canLoadAffairs || !studentId) { this.affairsLoaded = true; return }
      this.affairsLoading = true
      const [profileResult, timelineResult] = await Promise.allSettled([
        studentAffairsApi.getProfile(studentId),
        studentAffairsApi.getTimeline(studentId, { page: 1, pageSize: 20 })
      ])
      if (seq !== this.loadSeq || String(studentId) !== String(this.$route.params.studentId)) return
      const errors = []
      if (profileResult.status === 'fulfilled') this.affairsProfile = profileResult.value?.data || null
      else errors.push(profileResult.reason?.message || '学工画像摘要加载失败')
      if (timelineResult.status === 'fulfilled') {
        const payload = timelineResult.value?.data
        this.affairsTimeline = Array.isArray(payload) ? payload : (Array.isArray(payload?.items) ? payload.items : [])
      } else errors.push(timelineResult.reason?.message || '成长时间线加载失败')
      this.affairsError = [...new Set(errors)].join('；')
      this.affairsLoaded = true
      this.affairsLoading = false
    },
    async load() {
      const seq = ++this.loadSeq
      this.loading = true
      this.error = ''
      this.errorCode = ''
      this.detail = null
      this.resetAffairs()
      if (!this.canViewPage) { this.loading = false; return }
      const studentId = String(this.$route.params.studentId || '')
      const res = await studentApi.getStudentDetail(studentId)
      if (seq !== this.loadSeq) return
      if (res.code === 0 && res.data) {
        this.detail = res.data
        this.loading = false
        this.loadAffairsProjection(studentId, seq)
        return
      }
      this.error = res.message || '学生主档加载失败'
      this.errorCode = String(res.bizCode || res.errorCode || '')
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.s360-page{display:grid;gap:var(--space-4);min-width:0}.s360-state-actions{display:flex;gap:var(--space-2);justify-content:center;flex-wrap:wrap}.s360-btn,.s360-link,.s360-banner button{min-height:36px;padding:0 var(--space-3);border:1px solid var(--border-base);border-radius:var(--radius-md);background:var(--bg-card);color:var(--text-secondary);font-size:var(--font-size-sm);font-weight:var(--font-weight-medium);cursor:pointer}.s360-btn.is-primary{border-color:var(--pri);background:var(--btn-p-bg);color:var(--text-inverse)}
.s360-hero{position:relative;isolation:isolate;overflow:hidden;display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:var(--space-6);min-height:158px;padding:var(--space-6);border:1px solid var(--hero-bd);border-radius:var(--radius-xl);background:var(--hero-grad);box-shadow:var(--hero-shadow);color:var(--hero-tx)}.s360-hero:before{content:'';position:absolute;inset:0;z-index:-1;background-image:linear-gradient(var(--hero-grid) 1px,transparent 1px),linear-gradient(90deg,var(--hero-grid) 1px,transparent 1px);background-size:30px 30px}.s360-hero:after{content:'';position:absolute;right:-76px;top:-138px;z-index:-1;width:250px;height:250px;border:1px solid var(--hero-chip-bd);border-radius:var(--radius-full);box-shadow:0 0 0 42px var(--hero-chip-bg),0 0 0 86px color-mix(in srgb,var(--hero-chip-bg),transparent 62%)}.s360-hero__eyebrow{display:block;color:var(--hero-sub);font-size:var(--font-size-xs);font-weight:var(--font-weight-bold);letter-spacing:.06em}.s360-hero h2{max-width:860px;margin:var(--space-1) 0 var(--space-2);color:var(--hero-tx);font-size:var(--font-size-xl);line-height:30px;font-weight:var(--font-weight-semibold);overflow-wrap:anywhere}.s360-hero p{max-width:900px;margin:0;color:var(--hero-sub);font-size:var(--font-size-sm);line-height:22px}.s360-hero__tags{display:flex;gap:var(--space-2);margin-top:var(--space-3);flex-wrap:wrap}.s360-hero__metrics{display:grid;grid-template-columns:repeat(2,minmax(116px,1fr));gap:var(--space-2);min-width:280px;margin:0}.s360-hero__metrics>div{min-width:0;padding:var(--space-3);border:1px solid var(--hero-chip-bd);border-radius:var(--radius-lg);background:var(--hero-chip-bg)}.s360-hero dt{color:var(--hero-sub);font-size:var(--font-size-xs)}.s360-hero dd{margin:var(--space-1) 0 0;color:var(--hero-tx);font-size:var(--font-size-2xl);line-height:32px;font-weight:var(--font-weight-semibold);font-variant-numeric:tabular-nums;overflow-wrap:anywhere}.s360-hero dd.is-text{font-size:var(--font-size-md);line-height:24px}.s360-hero dd.is-gap{color:var(--hero-warn)}.s360-hero small{display:block;margin-top:var(--space-1);color:var(--hero-dim);font-size:var(--font-size-xs)}
.s360-truth{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:start;gap:var(--space-3);padding:var(--space-3);border:1px solid var(--primary-100);border-radius:var(--radius-lg);background:color-mix(in srgb,var(--primary-50),var(--bg-card) 52%)}.s360-truth__icon{display:grid;place-items:center;width:30px;height:30px;border-radius:var(--radius-md);background:var(--primary-100);color:var(--primary-700);font-weight:var(--font-weight-bold)}.s360-truth strong{color:var(--text-primary);font-size:var(--font-size-sm)}.s360-truth p{margin:var(--space-1) 0 0;color:var(--text-secondary);font-size:var(--font-size-xs);line-height:20px}.s360-truth__tags{display:flex;gap:var(--space-2);flex-wrap:wrap;justify-content:flex-end}
.s360-banner{display:flex;align-items:center;gap:var(--space-3);padding:var(--space-3);border:1px solid var(--border-base);border-radius:var(--radius-lg);background:var(--bg-card);color:var(--text-secondary);font-size:var(--font-size-sm)}.s360-banner strong{color:var(--text-primary)}.s360-banner span{flex:1}.s360-banner.is-warning{border-color:var(--warning-100);background:var(--warning-50)}.s360-banner.is-danger{border-color:var(--danger-100);background:var(--danger-50)}
.s360-profile{display:flex;align-items:center;gap:var(--space-4);padding:var(--space-4);border:1px solid var(--border-base);border-radius:var(--radius-card-sm);background:var(--bg-card);box-shadow:var(--shadow-card)}.s360-avatar{display:grid;place-items:center;flex:0 0 auto;width:56px;height:56px;border:1px solid var(--primary-100);border-radius:var(--radius-lg);background:var(--primary-50);color:var(--primary-700);font-size:var(--font-size-xl);font-weight:var(--font-weight-semibold)}.s360-profile__main{flex:1;min-width:0}.s360-profile__main>strong{font-size:var(--font-size-lg);color:var(--text-primary)}.s360-profile__main>p{margin:var(--space-1) 0 0;color:var(--text-secondary);font-size:var(--font-size-sm);overflow-wrap:anywhere}.s360-profile__main>div{display:flex;gap:var(--space-3);margin-top:var(--space-2);flex-wrap:wrap;color:var(--text-tertiary);font-size:var(--font-size-xs)}.s360-completeness{flex:0 0 140px;text-align:right}.s360-completeness b{display:block;color:var(--text-primary);font-size:var(--font-size-xl);font-variant-numeric:tabular-nums}.s360-completeness span{display:block;color:var(--text-tertiary);font-size:var(--font-size-xs)}.s360-completeness i{display:block;height:6px;margin-top:var(--space-1);overflow:hidden;border-radius:var(--radius-full);background:var(--bg-section)}.s360-completeness em{display:block;height:100%;border-radius:var(--radius-full);background:var(--pri)}
.s360-quick{display:grid;grid-template-columns:minmax(220px,.78fr) minmax(0,2fr);gap:var(--space-4);padding:var(--space-4);border:1px solid var(--primary-100);border-radius:var(--radius-card-sm);background:linear-gradient(135deg,var(--primary-50),var(--bg-card) 62%);box-shadow:var(--shadow-card)}.s360-quick__copy{display:grid;align-content:center;gap:var(--space-1)}.s360-quick__copy>span{color:var(--primary-700);font-size:var(--font-size-xs);font-weight:var(--font-weight-bold);letter-spacing:.06em}.s360-quick__copy>strong{color:var(--text-primary);font-size:var(--font-size-lg)}.s360-quick__copy>small{color:var(--text-secondary);font-size:var(--font-size-xs);line-height:20px}.s360-quick__grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:var(--space-2)}.s360-quick__grid button{display:grid;grid-template-columns:34px minmax(0,1fr);align-items:center;gap:2px var(--space-2);min-height:64px;padding:var(--space-2) var(--space-3);border:1px solid var(--primary-100);border-radius:var(--radius-lg);background:var(--bg-card);color:var(--text-primary);text-align:left;cursor:pointer}.s360-quick__grid button:hover,.s360-quick__grid button:focus-visible{border-color:var(--primary-500);box-shadow:var(--shadow-card-hover)}.s360-quick__grid button>span{grid-row:1/span 2;display:grid;place-items:center;width:34px;height:34px;border-radius:var(--radius-md);background:var(--primary-50);color:var(--primary-700);font-weight:var(--font-weight-bold)}.s360-quick__grid b{font-size:var(--font-size-sm)}.s360-quick__grid em{color:var(--text-tertiary);font-size:var(--font-size-xs);font-style:normal}
.s360-tabs{display:flex;gap:var(--space-1);max-width:100%;padding:var(--space-1);overflow-x:auto;border:1px solid var(--border-light);border-radius:var(--radius-lg);background:var(--bg-section);scrollbar-gutter:stable}.s360-tabs button{flex:0 0 auto;min-height:36px;padding:0 var(--space-3);border:0;border-radius:var(--radius-md);background:transparent;color:var(--text-secondary);font-size:var(--font-size-sm);font-weight:var(--font-weight-medium);cursor:pointer}.s360-tabs button.is-active{background:var(--bg-card);color:var(--primary-700);box-shadow:var(--shadow-sm)}
.s360-overview{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(330px,.72fr);gap:var(--space-4);align-items:start}.s360-card{min-width:0;overflow:hidden;border:1px solid var(--border-base);border-radius:var(--radius-card-sm);background:var(--bg-card);box-shadow:var(--shadow-card)}.s360-card>header{display:flex;align-items:flex-start;justify-content:space-between;gap:var(--space-3);padding:var(--space-4);border-bottom:1px solid var(--border-light)}.s360-card h3{margin:0;color:var(--text-primary);font-size:var(--font-size-md);line-height:24px}.s360-card header p{margin:2px 0 0;color:var(--text-tertiary);font-size:var(--font-size-xs);line-height:18px}.s360-card>:not(header){margin:var(--space-4)}.s360-card>.s360-table-wrap{margin:0}.s360-link{min-height:32px;padding:0 var(--space-2);border-color:transparent;background:transparent;color:var(--primary-700)}.s360-loading{display:flex;align-items:center;justify-content:center;min-height:120px;color:var(--text-tertiary);font-size:var(--font-size-sm)}
.s360-domain-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--space-3)}.s360-domain-grid>button{min-width:0;min-height:150px;padding:var(--space-3);border:1px solid var(--border-base);border-radius:var(--radius-lg);background:var(--bg-card);color:var(--text-primary);text-align:left;cursor:pointer}.s360-domain-grid>button:hover:not(:disabled),.s360-domain-grid>button:focus-visible:not(:disabled){border-color:var(--primary-500);box-shadow:var(--shadow-card-hover)}.s360-domain-grid>button.is-risk{background:linear-gradient(145deg,var(--bg-card) 64%,var(--danger-50))}.s360-domain-grid>button.is-attention{background:linear-gradient(145deg,var(--bg-card) 64%,var(--warning-50))}.s360-domain-grid>button.is-muted{background:var(--bg-section)}.s360-domain-grid>button.is-disabled{cursor:default}.s360-domain-grid>button>div{display:flex;align-items:center;gap:var(--space-2);flex-wrap:wrap}.s360-domain-grid>button>div strong{flex:1;min-width:70px;font-size:var(--font-size-sm)}.s360-domain-icon{display:grid;place-items:center;width:32px;height:32px;border-radius:var(--radius-md);background:var(--primary-50);color:var(--primary-700);font-weight:var(--font-weight-bold)}.s360-domain-grid>button>b{display:block;margin-top:var(--space-3);font-size:var(--font-size-lg);line-height:26px;overflow-wrap:anywhere}.s360-domain-grid>button>p{margin:var(--space-1) 0 0;color:var(--text-secondary);font-size:var(--font-size-xs);line-height:20px}.s360-domain-grid>button>small{display:block;margin-top:var(--space-2);color:var(--primary-700);font-size:var(--font-size-xs);font-weight:var(--font-weight-medium)}
.s360-timeline-card{max-height:600px}.s360-timeline-card>:not(header){overflow-y:auto;max-height:500px}.s360-timeline{position:relative;display:grid;gap:var(--space-4);padding:0 0 0 var(--space-1);list-style:none}.s360-timeline:before{content:'';position:absolute;left:9px;top:6px;bottom:8px;width:1px;background:var(--border-base)}.s360-timeline li{position:relative;display:grid;grid-template-columns:20px minmax(0,1fr);gap:var(--space-2)}.s360-timeline li>span{position:relative;z-index:1;width:13px;height:13px;margin-top:3px;border:3px solid var(--primary-500);border-radius:var(--radius-full);background:var(--bg-card)}.s360-timeline strong{color:var(--text-primary);font-size:var(--font-size-sm)}.s360-timeline p{margin:var(--space-1) 0;color:var(--text-secondary);font-size:var(--font-size-xs);line-height:19px}.s360-timeline small{color:var(--text-tertiary);font-size:var(--font-size-xs)}
.s360-kv-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:0 var(--space-6)}.s360-kv-grid>div,.s360-kv-list>div{display:flex;align-items:flex-start;justify-content:space-between;gap:var(--space-3);min-height:48px;padding:var(--space-3) 0;border-bottom:1px solid var(--border-light)}.s360-kv-grid span,.s360-kv-list span{color:var(--text-tertiary);font-size:var(--font-size-xs)}.s360-kv-grid strong,.s360-kv-list strong{color:var(--text-primary);font-size:var(--font-size-sm);text-align:right;overflow-wrap:anywhere}.s360-two-col{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--space-4);align-items:start}.s360-three-col{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:var(--space-4);align-items:start}.s360-risk-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:var(--space-3)}.s360-risk-summary>div{min-height:88px;padding:var(--space-3);border:1px solid var(--border-light);border-radius:var(--radius-lg);background:var(--bg-section)}.s360-risk-summary span{display:block;color:var(--text-tertiary);font-size:var(--font-size-xs)}.s360-risk-summary strong{display:block;margin-top:var(--space-2);color:var(--text-primary);font-size:var(--font-size-xl);font-variant-numeric:tabular-nums}.s360-boundary{padding:var(--space-3);border:1px solid var(--primary-100);border-radius:var(--radius-md);background:var(--primary-50);color:var(--text-secondary);font-size:var(--font-size-xs);line-height:20px}
.s360-table-wrap{max-width:100%;overflow:auto}.s360-table{width:100%;min-width:620px;border-collapse:separate;border-spacing:0;font-size:var(--font-size-sm)}.s360-table th{height:42px;padding:0 var(--space-3);background:var(--bg-section);color:var(--text-secondary);font-size:var(--font-size-xs);font-weight:var(--font-weight-semibold);text-align:left}.s360-table td{min-height:48px;padding:var(--space-3);border-bottom:1px solid var(--border-light);color:var(--text-secondary);vertical-align:top}.s360-table td strong{color:var(--text-primary)}
.s360-form{display:grid;gap:var(--space-3)}.s360-form label{display:grid;gap:var(--space-1)}.s360-form label>span{color:var(--text-tertiary);font-size:var(--font-size-xs)}.s360-form input,.s360-form select{min-height:38px;padding:0 var(--space-2);border:1px solid var(--border-base);border-radius:var(--radius-md);background:var(--bg-card);color:var(--text-primary)}.s360-form>div{display:flex;justify-content:flex-end;gap:var(--space-2)}.s360-form>small{color:var(--text-tertiary);font-size:var(--font-size-xs);line-height:20px}.s360-form__error{margin:0;color:var(--danger-600);font-size:var(--font-size-sm)}
button:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid var(--primary-500);outline-offset:2px}@media(max-width:1366px){.s360-hero{grid-template-columns:1fr}.s360-hero__metrics{grid-template-columns:repeat(4,minmax(0,1fr));min-width:0}.s360-overview{grid-template-columns:1fr}.s360-timeline-card{max-height:none}.s360-timeline-card>:not(header){max-height:420px}}@media(max-width:1120px){.s360-quick{grid-template-columns:1fr}.s360-three-col{grid-template-columns:1fr}.s360-two-col{grid-template-columns:1fr}}@media(max-width:900px){.s360-hero__metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.s360-truth{grid-template-columns:auto minmax(0,1fr)}.s360-truth__tags{grid-column:2;justify-content:flex-start}.s360-quick__grid,.s360-domain-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.s360-banner{align-items:flex-start;flex-wrap:wrap}.s360-banner button{margin-left:var(--space-10)}}@media(max-width:620px){.s360-profile{align-items:flex-start;flex-wrap:wrap}.s360-completeness{flex-basis:100%;text-align:left}.s360-quick__grid,.s360-domain-grid,.s360-risk-summary{grid-template-columns:1fr}.s360-hero{padding:var(--space-4)}}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
</style>
