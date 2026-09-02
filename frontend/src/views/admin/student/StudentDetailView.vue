<template>
  <ModulePageShell
    :title="detail ? `${detail.name || '未命名学生'} · 学生360` : '学生360'"
    subtitle="围绕同一名学生查看全生命周期事实；敏感字段按真实权限脱敏，具体办理仍进入原业务工作区。"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="学生360查阅"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <AppGlobalState
      :state="pageState"
      :title="stateTitle"
      :description="stateDescription"
      loading-text="正在加载学生360真实数据…"
      @retry="load"
      @back="goBack"
    >
      <template #actions>
        <div class="sd-state-actions">
          <button
            v-if="pageState === 'error' || pageState === 'empty'"
            type="button"
            class="sd-state-button sd-state-button--primary"
            @click="load"
          >
            重新加载
          </button>
          <button type="button" class="sd-state-button" @click="goBack">返回学生列表</button>
        </div>
      </template>

      <div v-if="isDegraded" class="sd-degraded" role="status" aria-live="polite">
        <span class="sd-degraded__icon" aria-hidden="true">!</span>
        <div>
          <strong>学生主档已加载，部分学工摘要暂不可用</strong>
          <p>{{ affairsError || '当前身份未授权读取学工画像摘要' }}。不可用内容以 DATA GAP 标记，不解释为 0。</p>
        </div>
        <button v-if="canLoadAffairsProjection" type="button" @click="loadAffairsProjection">重试摘要</button>
      </div>

      <section v-if="detail" class="sd-hero" aria-labelledby="sd-student-conclusion">
        <div class="sd-hero__identity">
          <span class="sd-hero__avatar" aria-hidden="true">{{ studentAvatar }}</span>
          <div class="sd-hero__copy">
            <div class="sd-hero__name-line">
              <span class="sd-hero__eyebrow">STUDENT 360 · 当前学生结论</span>
              <AppStatusTag
                :type="statusTone(detail.studentStatus)"
                :label="statusLabel(detail.studentStatus)"
                dot
              />
              <RiskTag v-if="effectiveRiskLevel !== 'NONE'" :level="effectiveRiskLevel" />
            </div>
            <h2 id="sd-student-conclusion">{{ currentConclusion }}</h2>
            <p>{{ studentIdentityLine }}</p>
          </div>
        </div>
        <div class="sd-hero__stats" aria-label="学生360关键真值">
          <article v-for="item in overviewMetrics" :key="item.key" class="sd-hero-stat">
            <span>{{ item.label }}</span>
            <strong :class="{ 'is-gap': item.isGap }">{{ item.value }}</strong>
            <small>{{ item.hint }}</small>
          </article>
        </div>
      </section>

      <div v-if="detail" class="sd-truthbar" role="note">
        <span class="sd-truthbar__icon" aria-hidden="true">真</span>
        <div>
          <strong>数据真值边界</strong>
          <p>
            基础主档来自现有学生详情接口；请假、宿舍、困难、奖助、处分、风险、谈话、家校、心理摘要和成长时间线仅使用现有学工画像接口。
            当前接口没有完整学业、实习、毕设和就业聚合时，页面明确显示 DATA GAP。
          </p>
        </div>
        <AppStatusTag :type="hasAffairsProjection ? 'success' : 'warning'" :label="hasAffairsProjection ? '学工摘要已加载' : '摘要 DATA GAP'" />
      </div>

      <AppSectionCard
        v-if="detail"
        class="sd-flow-card"
        title="学生问题黄金闭环"
        subtitle="学生360负责看完整背景；风险、谈话、家校与回访继续使用原业务状态机"
      >
        <ol class="sd-flow" aria-label="学生问题处理闭环">
          <li
            v-for="(step, index) in studentLoopSteps"
            :key="step.title"
            class="sd-flow__item"
            :class="{ 'is-current': index === 1 }"
          >
            <span>{{ index + 1 }}</span>
            <strong>{{ step.title }}</strong>
            <small>{{ step.subtitle }}</small>
          </li>
        </ol>
      </AppSectionCard>

      <section v-if="detail && quickActions.length" class="mp-card sd-quick">
        <div class="sd-quick__copy">
          <span>围绕当前学生办理</span>
          <strong>把学生上下文带入正式工作台</strong>
          <small>这里只提供权限化深链；资格、数据范围、状态和 allowedActions 仍由目标页面与服务端重新校验。</small>
        </div>
        <div class="sd-quick__actions">
          <button
            v-for="action in quickActions"
            :key="action.key"
            type="button"
            class="sd-quick__btn"
            @click="startStudentAction(action)"
          >
            <span aria-hidden="true">{{ action.icon }}</span>
            <b>{{ action.label }}</b>
            <em>去办理 →</em>
          </button>
        </div>
      </section>

      <nav v-if="detail" class="sd-tabs" aria-label="学生360内容页签">
        <button
          v-for="t in tabs"
          :key="t.key"
          type="button"
          class="sd-tab"
          :class="{ 'is-active': activeTab === t.key }"
          :aria-current="activeTab === t.key ? 'page' : undefined"
          @click="setTab(t.key)"
        >
          {{ t.label }}
        </button>
      </nav>

      <div v-if="detail && activeTab === 'overview'" class="sd-overview-grid">
        <AppSectionCard
          class="sd-panel"
          title="当前关注事项"
          subtitle="同一学生的跨域事实放在一起；点击后进入各域正式工作台"
        >
          <div class="sd-domain-grid">
            <article
              v-for="item in concernCards"
              :key="item.key"
              class="sd-domain-card"
              :class="[`is-${item.tone}`, { 'is-actionable': item.path && item.allowed }]"
              :tabindex="item.path && item.allowed ? 0 : undefined"
              :role="item.path && item.allowed ? 'link' : undefined"
              @click="openConcern(item)"
              @keydown.enter.prevent="openConcern(item)"
              @keydown.space.prevent="openConcern(item)"
            >
              <div class="sd-domain-card__head">
                <span>{{ item.label }}</span>
                <AppStatusTag :type="item.tagType" :label="item.status" />
              </div>
              <strong>{{ item.conclusion }}</strong>
              <p>{{ item.detail }}</p>
              <small v-if="item.path && item.allowed">进入业务 →</small>
              <small v-else-if="!item.allowed">当前身份无权查看明细</small>
            </article>
          </div>
        </AppSectionCard>

        <AppSectionCard
          class="sd-panel sd-panel--timeline"
          title="近期成长时间线"
          subtitle="服务端学生阶段事件倒序投影；具体业务明细仍按各域权限控制"
        >
          <div v-if="affairsLoading" class="sd-inline-loading">正在加载成长时间线…</div>
          <ol v-else-if="timelineRecords.length" class="sd-timeline">
            <li v-for="item in timelineRecords" :key="item.id">
              <span class="sd-timeline__dot" aria-hidden="true" />
              <strong>{{ item.action }}</strong>
              <p>{{ item.reason || '已形成正式业务事件' }}</p>
              <small>{{ item.at || '时间待确认' }} · {{ item.actor }}</small>
            </li>
          </ol>
          <div v-else class="sd-gap-panel">
            <AppStatusTag type="warning" label="DATA GAP" />
            <strong>{{ timelineGapTitle }}</strong>
            <p>{{ timelineGapDescription }}</p>
          </div>
        </AppSectionCard>
      </div>

      <section v-if="detail && activeTab === 'basic'" class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">基础信息</span>
          <span class="mp-note">{{ canSensitive ? '当前角色可见授权明文' : '敏感字段已脱敏' }}</span>
        </div>
        <div class="mp-card__body sd-kv-grid">
          <div v-for="kv in basicKvs" :key="kv.k" class="mp-kv">
            <span class="mp-kv__k">{{ kv.k }}</span>
            <span class="mp-kv__v">{{ kv.v }}</span>
          </div>
        </div>
      </section>

      <section v-if="detail && activeTab === 'status'" class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">学籍状态历史</span>
          <button class="mp-link" type="button" @click="$router.push('/admin/student/status')">学籍异动台账 ›</button>
        </div>
        <div class="mp-card__body">
          <ul v-if="detail.statusHistory && detail.statusHistory.length" class="mp-timeline">
            <li v-for="r in detail.statusHistory" :key="r.id" class="mp-timeline__item">
              <div class="mp-timeline__title">{{ statusLabel(r.fromStatus) }} → {{ statusLabel(r.toStatus) }}</div>
              <div class="mp-timeline__desc">{{ r.reason || '未填写原因' }}<template v-if="r.attachment"> · 附件：{{ r.attachment }}</template></div>
              <div class="mp-timeline__time">{{ r.operatedAt || '—' }} · {{ r.operator || '系统' }}<template v-if="r.roleName">（{{ r.roleName }}）</template></div>
            </li>
          </ul>
          <CapabilityGap
            v-else
            title="当前详情接口未返回学籍变更历史"
            description="这不表示学生从未发生学籍异动；请进入正式学籍异动台账查询。"
          />
        </div>
      </section>

      <div v-if="detail && activeTab === 'campus'" class="mp-grid-2">
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">数字迎新</span></div>
          <div class="mp-card__body">
            <ul v-if="detail.orientation && detail.orientation.steps && detail.orientation.steps.length" class="mp-timeline">
              <li v-for="s in detail.orientation.steps" :key="s.name + s.time" class="mp-timeline__item is-success">
                <div class="mp-timeline__title">{{ s.name }}</div>
                <div class="mp-timeline__time">{{ s.time || '—' }}</div>
              </li>
            </ul>
            <CapabilityGap
              v-else
              title="迎新步骤未进入当前聚合合同"
              description="请通过数字迎新工作区查看报到资格、办理进度和异常闭环。"
            />
          </div>
        </section>
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">在校服务摘要</span></div>
          <div class="mp-card__body">
            <div v-if="hasAffairsProjection" class="sd-campus-facts">
              <div><span>累计请假</span><strong>{{ leaveSummaryText }}</strong></div>
              <div><span>当前宿舍</span><strong>{{ dormText }}</strong></div>
              <div><span>困难认定</span><strong>{{ aidText }}</strong></div>
              <div><span>已获资助</span><strong>{{ fundingSummaryText }}</strong></div>
            </div>
            <CapabilityGap
              v-else
              title="学工在校服务摘要暂不可用"
              :description="affairsGapDescription"
            />
          </div>
        </section>
      </div>

      <section v-if="detail && activeTab === 'academic'" class="mp-card">
        <div class="mp-card__head"><span class="mp-card__title">学业过程</span></div>
        <div class="mp-card__body">
          <template v-if="hasAcademicData">
            <div class="sd-kv-grid">
              <div class="mp-kv"><span class="mp-kv__k">平均绩点</span><span class="mp-kv__v">{{ detail.academic.gpa }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">已修学分</span><span class="mp-kv__v">{{ detail.academic.earnedCredits }} / {{ detail.academic.requiredCredits }}</span></div>
            </div>
            <table v-if="detail.academic.courses.length" class="mp-audit sd-gap-top">
              <thead><tr><th>课程</th><th>学期</th><th>成绩</th><th>重修</th></tr></thead>
              <tbody>
                <tr v-for="c in detail.academic.courses" :key="c.name + c.term">
                  <td class="is-who">{{ c.name }}</td><td>{{ c.term }}</td><td>{{ c.score }}</td><td>{{ c.retake ? '是' : '—' }}</td>
                </tr>
              </tbody>
            </table>
          </template>
          <CapabilityGap
            v-else
            title="完整学业聚合仍是 DATA GAP"
            description="当前学生详情门面未返回可信课程、学分和预警聚合；页面不以 0 或空数组冒充“学业正常”。"
          />
        </div>
      </section>

      <div v-if="detail && activeTab === 'career'" class="mp-grid-cards">
        <CareerCard title="岗位实习" :record="detail.internship" gap-text="当前学生详情接口未返回可信实习聚合。" />
        <CareerCard title="毕业设计" :record="detail.graduationDesign" gap-text="当前学生详情接口未返回可信毕设聚合。" />
        <CareerCard title="就业去向" :record="detail.employment" gap-text="当前学生详情接口未返回可信就业聚合。" />
      </div>

      <section v-if="detail && activeTab === 'risk'" class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">风险与跟进</span>
          <button type="button" class="mp-link" @click="goRisk">进入风险中心 ›</button>
        </div>
        <div class="mp-card__body">
          <div v-if="hasAffairsProjection" class="sd-risk-summary">
            <RiskTag v-if="effectiveRiskLevel !== 'NONE'" :level="effectiveRiskLevel" />
            <AppStatusTag v-else type="success" label="当前无未关闭风险" />
            <strong>{{ riskSummaryText }}</strong>
            <p>这里只展示服务端学生级风险摘要；分派、跟进、转办、升级、关闭和重开继续服从风险记录的 allowedActions 与 version。</p>
          </div>
          <div v-if="detail.riskTags && detail.riskTags.length" class="mp-stack sd-gap-top">
            <article v-for="t in detail.riskTags" :key="t.id" class="sd-risk">
              <div class="sd-risk__head">
                <RiskTag :level="t.level" />
                <span class="sd-risk__title">{{ t.title }}</span>
                <AppStatusTag :label="riskStatusLabel(t.status)" :type="t.status === 'RESOLVED' ? 'success' : 'warning'" />
                <span class="mp-note">{{ t.tagTypeLabel }} · {{ t.sourceLabel }} · 责任人 {{ t.owner || '待分派' }}</span>
              </div>
              <p class="sd-risk__desc">{{ t.description }}</p>
            </article>
          </div>
          <CapabilityGap
            v-else-if="!hasAffairsProjection"
            title="风险摘要暂不可用"
            :description="affairsGapDescription"
          />
        </div>
      </section>

      <div v-if="detail && activeTab === 'audit'" class="mp-grid-2">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">信息更正申请</span>
            <button type="button" class="mp-link" @click="$router.push('/admin/student/corrections')">更正审核 ›</button>
          </div>
          <div class="mp-card__body">
            <div v-if="detail.corrections && detail.corrections.length">
              <div v-for="c in detail.corrections" :key="c.id" class="mp-kv">
                <span class="mp-kv__k">{{ c.fieldLabel }} · {{ c.submitTime }}</span>
                <span class="mp-kv__v"><AppStatusTag :status="c.status" /></span>
              </div>
            </div>
            <CapabilityGap
              v-else
              title="当前详情接口未返回更正记录"
              description="这不表示没有更正申请；请进入信息更正审核工作区查询。"
            />
          </div>
        </section>
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">审计记录</span></div>
          <div class="mp-card__body">
            <table v-if="detail.auditTrail && detail.auditTrail.length" class="mp-audit">
              <thead><tr><th>时间</th><th>操作人</th><th>动作</th><th>说明</th></tr></thead>
              <tbody>
                <tr v-for="a in detail.auditTrail" :key="a.id">
                  <td>{{ a.time }}</td><td class="is-who">{{ a.operator }}</td><td>{{ auditActionLabel(a) }}</td><td>{{ a.detail }}</td>
                </tr>
              </tbody>
            </table>
            <CapabilityGap
              v-else
              title="详情审计聚合暂未返回"
              description="编辑和导出仍由原接口写入审计；此处不使用全局审计分页冒充当前学生完整审计。"
            />
          </div>
        </section>
      </div>
    </AppGlobalState>

    <AppDrawer
      :visible="editDrawer.visible"
      title="编辑基础信息"
      @update:visible="editDrawer.visible = $event"
    >
      <div class="mp-stack">
        <label class="sd-field">
          <span class="sd-field__label">姓名</span>
          <input v-model="editDrawer.form.name" class="sd-field__control" />
        </label>
        <label class="sd-field">
          <span class="sd-field__label">手机号</span>
          <input v-model="editDrawer.form.phone" class="sd-field__control" />
        </label>
        <label class="sd-field">
          <span class="sd-field__label">辅导员</span>
          <select v-model="editDrawer.form.counselorName" class="sd-field__control">
            <option
              v-for="c in counselorOptions"
              :key="c.value"
              :value="c.value"
            >
              {{ c.label }}
            </option>
          </select>
        </label>
        <p v-if="editDrawer.error" class="mp-form-err">{{ editDrawer.error }}</p>
        <div class="sd-drawer-ops">
          <AppButton variant="ghost" @click="editDrawer.visible = false">取消</AppButton>
          <AppButton variant="primary" :disabled="editDrawer.submitting" @click="submitEdit">保存变更</AppButton>
        </div>
        <p class="mp-note">变更继续携带 expectedVersion 并写字段级审计；证件类关键字段请走信息更正审核流程。</p>
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
import { h } from 'vue'
import {
  ModulePageShell,
  ModuleToolbar,
  StatusTag as AppStatusTag,
  RiskTag
} from '@/components/business'
import { AppConfirmDialog, AppGlobalState, AppSectionCard } from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { studentApi } from '@/modules/student/api/student.api'
import studentAffairsApi from '@/modules/studentAffairs/api/studentAffairsB.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'
import { toast } from '@/utils/toast'
import { presentAuditRecord } from '@/utils/presentationSafety'

const CapabilityGap = {
  name: 'Student360CapabilityGap',
  props: {
    title: { type: String, required: true },
    description: { type: String, required: true }
  },
  setup(props) {
    return () => h('div', { class: 'sd-gap-panel', role: 'note' }, [
      h(AppStatusTag, { type: 'warning', label: 'DATA GAP' }),
      h('strong', props.title),
      h('p', props.description)
    ])
  }
}

const CareerCard = {
  name: 'Student360CareerCard',
  props: {
    title: { type: String, required: true },
    record: { type: Object, default: null },
    gapText: { type: String, required: true }
  },
  setup(props) {
    return () => h('section', { class: 'mp-card' }, [
      h('div', { class: 'mp-card__head' }, [
        h('span', { class: 'mp-card__title' }, props.title)
      ]),
      h('div', { class: 'mp-card__body' }, [
        props.record
          ? h('div', { class: 'sd-record-json' }, Object.entries(props.record).map(([key, value]) =>
              h('div', { class: 'mp-kv', key }, [
                h('span', { class: 'mp-kv__k' }, key),
                h('span', { class: 'mp-kv__v' }, value === null || value === '' ? '—' : String(value))
              ])
            ))
          : h(CapabilityGap, { title: `${props.title}聚合未返回`, description: props.gapText })
      ])
    ])
  }
}

export default {
  name: 'StudentDetailView',
  components: {
    ModulePageShell,
    ModuleToolbar,
    AppStatusTag,
    RiskTag,
    AppGlobalState,
    AppSectionCard,
    AppConfirmDialog,
    AppButton,
    AppDrawer,
    CapabilityGap,
    CareerCard
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    const requestedTab = String(this.$route.query.tab || 'overview')
    return {
      loading: true,
      error: '',
      detail: null,
      affairsLoading: false,
      affairsError: '',
      affairsProfile: null,
      affairsTimeline: [],
      activeTab: requestedTab,
      tabs: [
        { key: 'overview', label: '当前关注' },
        { key: 'basic', label: '基础信息' },
        { key: 'status', label: '学籍与状态' },
        { key: 'campus', label: '迎新与在校' },
        { key: 'academic', label: '学业过程' },
        { key: 'career', label: '实习 · 毕设 · 就业' },
        { key: 'risk', label: '风险与跟进' },
        { key: 'audit', label: '更正与审计' }
      ],
      editDrawer: {
        visible: false,
        form: { name: '', phone: '', counselorName: '' },
        error: '',
        submitting: false
      },
      exportDialog: { visible: false, submitting: false }
    }
  },
  computed: {
    roleName() {
      return this.ctx?.currentRole?.roleName || ''
    },
    dataScopeName() {
      return this.ctx?.dataScope?.scopeName || '按当前身份'
    },
    counselorOptions() {
      return Array.isArray(this.ctx?.filterOptions?.counselors) ? this.ctx.filterOptions.counselors : []
    },
    canViewPage() {
      return canCode(this.ctx, 'student.profile.view') || canCode(this.ctx, 'studentAffairs.student.view')
    },
    canLoadAffairsProjection() {
      return canCode(this.ctx, 'studentAffairs.student.view')
    },
    canSensitive() {
      const pa = this.ctx?.permissionActions?.viewSensitive
      return !!(pa && pa.visible && pa.allowed)
    },
    pageState() {
      if (!this.canViewPage) return 'forbidden'
      if (this.loading) return 'loading'
      if (this.error) return 'error'
      if (!this.detail) return 'empty'
      return 'ready'
    },
    stateTitle() {
      if (this.pageState === 'forbidden') return '当前身份无权查看学生360'
      if (this.pageState === 'empty') return '未找到学生主档'
      if (this.pageState === 'error') return '学生360加载失败'
      return ''
    },
    stateDescription() {
      if (this.pageState === 'forbidden') return '需要学生主档查看权限或学工学生查看权限；请切换授权身份或联系管理员。'
      if (this.pageState === 'empty') return '当前学生不存在、已超出数据范围，或主档已按服务端规则不可见。'
      if (this.pageState === 'error') return this.error
      return ''
    },
    isDegraded() {
      return !!this.detail && (!this.canLoadAffairsProjection || !!this.affairsError)
    },
    hasAffairsProjection() {
      return !!this.affairsProfile?.baseInfo
    },
    studentAvatar() {
      return String(this.detail?.name || '学').slice(0, 1)
    },
    effectiveRiskLevel() {
      return String(this.affairsProfile?.riskSummary?.topLevel || this.detail?.riskLevel || 'NONE').toUpperCase()
    },
    openRiskCount() {
      return this.hasAffairsProjection ? Number(this.affairsProfile.riskSummary?.openCount || 0) : null
    },
    currentConclusion() {
      if (!this.detail) return '正在读取学生主档'
      const facts = []
      if (this.openRiskCount !== null && this.openRiskCount > 0) facts.push(`${this.openRiskCount} 条未关闭风险`)
      if (this.hasAffairsProjection && Number(this.affairsProfile.leaveSummary?.total || 0) > 0) {
        facts.push(`累计请假 ${Number(this.affairsProfile.leaveSummary.total)} 次`)
      }
      if (this.hasAffairsProjection && Number(this.affairsProfile.disciplineSummary?.activeCount || 0) > 0) {
        facts.push(`${Number(this.affairsProfile.disciplineSummary.activeCount)} 条生效处分`)
      }
      if (facts.length) return `当前已确认：${facts.join('，')}；请进入对应工作区查看真实状态与可执行动作。`
      if (this.hasAffairsProjection) return '当前学工摘要未发现需要在本页强调的未关闭事项；具体业务仍以各工作区实时状态为准。'
      return '学生主档已加载；当前身份尚未获得完整学工摘要，页面不以空值推断“无事项”。'
    },
    studentIdentityLine() {
      const d = this.detail || {}
      return [d.studentNo, d.collegeName, d.majorName, d.className, d.grade, d.counselorName ? `辅导员 ${d.counselorName}` : '']
        .filter(Boolean)
        .join(' · ') || '组织归属信息未完整返回'
    },
    overviewMetrics() {
      const gap = (label) => ({ value: '—', hint: `${label}未授权或未返回`, isGap: true })
      return [
        {
          key: 'completeness',
          label: '主档完整度',
          value: Number.isFinite(Number(this.detail?.dataCompleteness)) ? `${Number(this.detail.dataCompleteness)}%` : '—',
          hint: '学生主档真实字段',
          isGap: !Number.isFinite(Number(this.detail?.dataCompleteness))
        },
        {
          key: 'risk',
          label: '未关闭风险',
          ...(this.openRiskCount === null ? gap('风险摘要') : { value: `${this.openRiskCount} 条`, hint: `最高等级 ${this.effectiveRiskLevel}`, isGap: false })
        },
        {
          key: 'leave',
          label: '累计请假',
          ...(this.hasAffairsProjection ? { value: `${Number(this.affairsProfile.leaveSummary?.total || 0)} 次`, hint: '学工画像服务端聚合', isGap: false } : gap('请假摘要'))
        },
        {
          key: 'talk',
          label: '谈话记录',
          ...(this.hasAffairsProjection ? { value: `${Number(this.affairsProfile.talkSummary?.total || 0)} 次`, hint: this.lastTalkText, isGap: false } : gap('谈话摘要'))
        }
      ]
    },
    studentLoopSteps() {
      return [
        { title: '今日发现', subtitle: '统一待办' },
        { title: '学生360', subtitle: '完整背景' },
        { title: '风险处置', subtitle: '明确责任' },
        { title: '谈话/家校', subtitle: '真实沟通' },
        { title: '回访', subtitle: '约定时间' },
        { title: '关闭沉淀', subtitle: '留时间线' }
      ]
    },
    toolbarActions() {
      const pa = this.ctx?.permissionActions || {}
      return [
        { key: 'back', label: '返回列表', variant: 'ghost', perm: 'viewList' },
        { key: 'edit', label: '编辑基础信息', perm: 'editStudent' },
        { key: 'export', label: '导出学生档案', perm: 'exportArchive' }
      ]
        .filter((action) => action.key === 'back' || (pa[action.perm] && pa[action.perm].visible))
        .map((action) => ({
          ...action,
          disabled: action.key === 'back' ? false : !pa[action.perm]?.allowed,
          disabledReason: action.key === 'back' ? '' : pa[action.perm]?.reason
        }))
    },
    quickActions() {
      const actions = [
        { key: 'talk', label: '发起谈话', icon: '谈', permission: 'studentAffairs.talk.create', path: '/admin/student-affairs/talk' },
        { key: 'family', label: '登记家校联系', icon: '家', permission: 'studentAffairs.homeSchool.record.create', path: '/admin/student-affairs/family' },
        { key: 'risk', label: '新建风险', icon: '险', permission: 'studentAffairs.risk.create', path: '/admin/student-affairs/risk' },
        { key: 'dorm', label: '发起调宿', icon: '宿', permission: 'studentAffairs.dorm.transfer.create', path: '/admin/student-affairs/dorm/transfer' },
        { key: 'aid', label: '受理困难', icon: '困', permission: 'studentAffairs.aid.create', path: '/admin/student-affairs/aid' },
        { key: 'funding', label: '受理奖助', icon: '助', permission: 'studentAffairs.funding.create', path: '/admin/student-affairs/funding' }
      ]
      return actions.filter((action) => canCode(this.ctx, action.permission))
    },
    concernCards() {
      const unavailable = (key, label, path, permission) => ({
        key, label, status: 'DATA GAP', conclusion: '摘要未授权或未返回', detail: this.affairsGapDescription,
        tone: 'gap', tagType: 'warning', path, permission, allowed: canCode(this.ctx, permission)
      })
      if (!this.hasAffairsProjection) {
        return [
          unavailable('risk', '风险', '/admin/student-affairs/risk', 'studentAffairs.risk.view'),
          unavailable('leave', '请假与返校', '/admin/student-affairs/leave/ledger', 'studentAffairs.leave.view'),
          unavailable('dorm', '宿舍', '/admin/student-affairs/dorm/transfer', 'studentAffairs.dorm.view'),
          unavailable('aid', '困难与资助', '/admin/student-affairs/aid', 'studentAffairs.aid.view'),
          unavailable('discipline', '违纪处分', '/admin/student-affairs/discipline', 'studentAffairs.discipline.view'),
          unavailable('talk', '谈话与家校', '/admin/student-affairs/talk', 'studentAffairs.talk.view')
        ]
      }
      const p = this.affairsProfile
      const riskOpen = Number(p.riskSummary?.openCount || 0)
      const activeDiscipline = p.disciplineSummary?.restricted ? null : Number(p.disciplineSummary?.activeCount || 0)
      return [
        {
          key: 'risk', label: '风险', status: riskOpen ? `${riskOpen} 条未关闭` : '暂无未关闭',
          conclusion: riskOpen ? `最高风险等级 ${p.riskSummary?.topLevel || '待确认'}` : '当前风险摘要无未关闭记录',
          detail: '处置动作继续由风险记录 allowedActions 与 version 决定。',
          tone: riskOpen ? 'risk' : 'normal', tagType: riskOpen ? 'danger' : 'success',
          path: '/admin/student-affairs/risk', permission: 'studentAffairs.risk.view', allowed: canCode(this.ctx, 'studentAffairs.risk.view')
        },
        {
          key: 'leave', label: '请假与返校', status: `${Number(p.leaveSummary?.total || 0)} 次`,
          conclusion: '累计请假摘要已加载', detail: '当前审批、在假、销假与逾期状态请进入正式请假工作区。',
          tone: 'normal', tagType: 'info', path: '/admin/student-affairs/leave/ledger', permission: 'studentAffairs.leave.view', allowed: canCode(this.ctx, 'studentAffairs.leave.view')
        },
        {
          key: 'dorm', label: '宿舍', status: p.dormSummary?.hasDorm ? '已入住' : '暂无入住摘要',
          conclusion: this.dormText, detail: '宿舍信息继续服从楼栋与学生数据范围。',
          tone: 'normal', tagType: p.dormSummary?.hasDorm ? 'success' : 'default', path: '/admin/student-affairs/dorm/transfer', permission: 'studentAffairs.dorm.view', allowed: canCode(this.ctx, 'studentAffairs.dorm.view')
        },
        {
          key: 'aid', label: '困难与资助', status: p.aidSummary?.inLibrary ? '困难库在库' : '暂无困难认定',
          conclusion: `${this.aidText}；${this.fundingSummaryText}`, detail: '家庭经济明文仍需专项权限、业务理由与敏感审计。',
          tone: p.aidSummary?.inLibrary ? 'attention' : 'normal', tagType: p.aidSummary?.inLibrary ? 'warning' : 'default', path: '/admin/student-affairs/aid', permission: 'studentAffairs.aid.view', allowed: canCode(this.ctx, 'studentAffairs.aid.view')
        },
        {
          key: 'discipline', label: '违纪处分', status: activeDiscipline === null ? '受限可见' : `${activeDiscipline} 条生效`,
          conclusion: activeDiscipline === null ? '当前角色仅可见受限摘要' : (activeDiscipline ? '存在生效处分' : '当前无生效处分'),
          detail: '处分登记、审批、生效、申诉与解除继续走原状态机。',
          tone: activeDiscipline ? 'attention' : 'normal', tagType: activeDiscipline ? 'warning' : 'default', path: '/admin/student-affairs/discipline', permission: 'studentAffairs.discipline.view', allowed: canCode(this.ctx, 'studentAffairs.discipline.view')
        },
        {
          key: 'talk', label: '谈话与家校', status: `${Number(p.talkSummary?.total || 0)} 次谈话`,
          conclusion: this.familySummaryText, detail: `最近谈话：${this.lastTalkText}；下一次回访统一真值仍是 DATA GAP。`,
          tone: p.psyFlag === '需关注' ? 'sensitive' : 'normal', tagType: p.psyFlag === '需关注' ? 'warning' : 'info', path: '/admin/student-affairs/talk', permission: 'studentAffairs.talk.view', allowed: canCode(this.ctx, 'studentAffairs.talk.view')
        }
      ]
    },
    basicKvs() {
      const d = this.detail || {}
      return [
        { k: '姓名', v: d.name || '—' },
        { k: '学号', v: d.studentNo || '—' },
        { k: '性别', v: d.gender || '—' },
        { k: '手机号', v: this.mask(d.phone, 'phone') },
        { k: '身份证号', v: this.mask(d.idCard, 'idCard') },
        { k: '学院', v: d.collegeName || '—' },
        { k: '专业', v: d.majorName || '—' },
        { k: '班级', v: d.className || '未分班' },
        { k: '年级', v: d.grade || '—' },
        { k: '入学日期', v: d.enrollDate || '—' },
        { k: '辅导员', v: d.counselorName || '—' },
        { k: '最近更新', v: d.updatedAt || '—' }
      ]
    },
    timelineRecords() {
      return this.affairsTimeline.map((item) => ({
        id: item.eventId,
        action: item.title || item.eventType || '业务事件',
        actor: item.module || 'system',
        reason: item.detail || '',
        at: String(item.occurredAt || '').replace('T', ' ').slice(0, 19)
      }))
    },
    timelineGapTitle() {
      return this.canLoadAffairsProjection ? '暂无服务端成长时间线事件' : '当前身份无学工时间线权限'
    },
    timelineGapDescription() {
      if (this.affairsError) return this.affairsError
      return this.canLoadAffairsProjection
        ? '这不表示没有其他业务记录；当前时间线只包含已进入 StudentStageEvent 的正式事件。'
        : '需要 studentAffairs.student.view，并继续服从当前学生的数据范围。'
    },
    affairsGapDescription() {
      return this.affairsError || (this.canLoadAffairsProjection ? '服务端学工画像暂未返回。' : '当前身份没有 studentAffairs.student.view。')
    },
    dormText() {
      const d = this.affairsProfile?.dormSummary
      return d?.hasDorm && d.text ? d.text : '暂无宿舍入住摘要'
    },
    aidText() {
      const a = this.affairsProfile?.aidSummary || {}
      if (a.inLibrary) return `困难库在库 · ${a.difficultLevel || '已认定'}`
      return '暂无困难认定摘要'
    },
    fundingSummaryText() {
      return this.hasAffairsProjection ? `已获资助 ${Number(this.affairsProfile.fundingSummary?.grantedCount || 0)} 项` : '资助摘要未返回'
    },
    leaveSummaryText() {
      return this.hasAffairsProjection ? `${Number(this.affairsProfile.leaveSummary?.total || 0)} 次` : '未返回'
    },
    familySummaryText() {
      const f = this.affairsProfile?.familySummary
      if (!f) return '家校摘要未返回'
      if (!f.hasContact) return '暂无授权可见的家庭联系人或家校联系摘要'
      return `联系人 ${Number(f.contactCount || 0)} 条 · 家校联系 ${Number(f.logCount || 0)} 条`
    },
    lastTalkText() {
      const value = this.affairsProfile?.talkSummary?.lastTalkAt
      return value ? String(value).replace('T', ' ').slice(0, 16) : '暂无有效时间'
    },
    riskSummaryText() {
      if (!this.hasAffairsProjection) return '风险摘要未返回'
      return this.openRiskCount ? `当前有 ${this.openRiskCount} 条未关闭风险` : '当前无未关闭风险摘要'
    },
    hasAcademicData() {
      const a = this.detail?.academic
      return !!(a && (a.courses?.length || (a.gpa && a.gpa !== '—') || Number(a.earnedCredits) || Number(a.requiredCredits)))
    }
  },
  watch: {
    '$route.params.studentId'() {
      this.load()
    },
    '$route.query.tab'(value) {
      const next = String(value || 'overview')
      if (this.tabs.some((tab) => tab.key === next)) this.activeTab = next
    }
  },
  created() {
    if (!this.tabs.some((tab) => tab.key === this.activeTab)) this.activeTab = 'overview'
    this.load()
  },
  methods: {
    auditActionLabel(row) {
      return presentAuditRecord(row).displayAction
    },
    setTab(key) {
      if (!this.tabs.some((tab) => tab.key === key)) return
      this.activeTab = key
      const query = { ...this.$route.query }
      if (key === 'overview') delete query.tab
      else query.tab = key
      this.$router.replace({ query }).catch(() => {})
    },
    mask(value, type) {
      if (!value) return '未登记'
      if (this.canSensitive) return value
      const text = String(value)
      if (type === 'phone' && text.length >= 7) return `${text.slice(0, 3)}****${text.slice(-4)}`
      if (type === 'idCard' && text.length >= 10) return `${text.slice(0, 6)}********${text.slice(-4)}`
      return '已脱敏'
    },
    statusLabel(value) {
      const options = this.ctx?.statusOptions?.studentStatus || []
      return options.find((item) => item.value === value)?.label || '学籍状态待确认'
    },
    statusTone(value) {
      return {
        ADMITTED: 'processing', ACTIVE: 'success', SUSPENDED: 'warning',
        GRADUATED: 'info', DROPPED: 'default', VOIDED: 'default'
      }[value] || 'default'
    },
    riskStatusLabel(value) {
      const options = this.ctx?.statusOptions?.riskTagStatus || []
      return options.find((item) => item.value === value)?.label || '风险状态待确认'
    },
    goBack() {
      const back = this.$router.options.history.state && this.$router.options.history.state.back
      if (back && String(back).startsWith('/admin/')) this.$router.back()
      else this.$router.push('/admin/student/list')
    },
    onToolbar(key) {
      if (key === 'back') this.goBack()
      if (key === 'edit' && this.detail) {
        this.editDrawer = {
          visible: true,
          error: '',
          submitting: false,
          form: {
            name: this.detail.name,
            phone: this.detail.phone,
            counselorName: this.detail.counselorName
          }
        }
      }
      if (key === 'export') this.exportDialog = { visible: true, submitting: false }
    },
    startStudentAction(action) {
      if (!this.detail || !action) return
      this.$router.push({
        path: action.path,
        query: {
          studentId: String(this.detail.studentId),
          studentNo: this.detail.studentNo || undefined,
          studentName: this.detail.name || undefined,
          intent: 'create',
          from: 'student360'
        }
      })
    },
    openConcern(item) {
      if (!item?.path || !item.allowed) return
      this.$router.push({
        path: item.path,
        query: {
          studentId: String(this.detail.studentId),
          studentNo: this.detail.studentNo || undefined,
          studentName: this.detail.name || undefined,
          from: 'student360'
        }
      })
    },
    goRisk() {
      if (!this.detail || !canCode(this.ctx, 'studentAffairs.risk.view')) return
      this.$router.push({
        path: '/admin/student-affairs/risk',
        query: { studentId: String(this.detail.studentId), status: 'OPEN', from: 'student360' }
      })
    },
    async submitEdit() {
      if (!this.detail) return
      const drawer = this.editDrawer
      drawer.submitting = true
      drawer.error = ''
      const res = await studentApi.updateStudent(
        this.detail.studentId,
        { ...drawer.form, expectedVersion: this.detail.version }
      )
      drawer.submitting = false
      if (res.code === 0) {
        drawer.visible = false
        toast.success('基础信息已更新（已留痕）')
        this.load()
      } else {
        drawer.error = res.message || '保存失败'
      }
    },
    async submitExport({ reason }) {
      this.exportDialog.submitting = true
      const res = await studentApi.createExport({
        scope: 'SELECTED',
        fieldKeys: ['name', 'studentNo', 'orgPath', 'studentStatus', 'phone', 'idCard'],
        purpose: 'WORK',
        remark: reason,
        rowCount: 1
      })
      this.exportDialog.submitting = false
      if (res.code === 0) {
        this.exportDialog.visible = false
        toast.success(`档案导出任务已创建：已脱敏、含水印，审计编号 ${res.data.auditId}`)
      } else {
        toast.error(res.message || '导出任务创建失败')
      }
    },
    async loadAffairsProjection() {
      if (!this.detail || !this.canLoadAffairsProjection) return
      this.affairsLoading = true
      this.affairsError = ''
      try {
        const [profileRes, timelineRes] = await Promise.all([
          studentAffairsApi.getProfile(this.detail.studentId),
          studentAffairsApi.getTimeline(this.detail.studentId, { page: 1, pageSize: 20 })
        ])
        this.affairsProfile = profileRes.data || null
        this.affairsTimeline = timelineRes.data?.items || []
      } catch (error) {
        this.affairsProfile = null
        this.affairsTimeline = []
        this.affairsError = error?.message || '学工画像摘要加载失败'
      } finally {
        this.affairsLoading = false
      }
    },
    async load() {
      if (!this.canViewPage) {
        this.loading = false
        this.detail = null
        return
      }
      this.loading = true
      this.error = ''
      this.affairsError = ''
      this.affairsProfile = null
      this.affairsTimeline = []
      const res = await studentApi.getStudentDetail(this.$route.params.studentId)
      if (res.code === 0 && res.data) {
        this.detail = res.data
        this.loading = false
        if (this.canLoadAffairsProjection) await this.loadAffairsProjection()
      } else {
        this.detail = null
        this.error = res.message || '学生主档详情加载失败'
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.sd-state-actions,
.sd-drawer-ops {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.sd-state-button {
  min-height: 36px;
  padding: 0 var(--space-4);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
}

.sd-state-button--primary {
  border-color: var(--pri);
  background: var(--pri);
  color: var(--text-inverse);
}

.sd-degraded {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--warning-100);
  border-radius: var(--radius-card-sm);
  background: var(--warning-50);
  color: var(--warning-700);
}

.sd-degraded__icon {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: var(--radius-md);
  background: var(--warning-100);
  font-weight: var(--font-weight-bold);
}

.sd-degraded strong,
.sd-degraded p {
  margin: 0;
}

.sd-degraded strong {
  color: var(--text-primary);
  font-size: var(--font-size-sm);
}

.sd-degraded p {
  margin-top: var(--space-1);
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  line-height: var(--line-height-base);
}

.sd-degraded button {
  min-height: 34px;
  padding: 0 var(--space-3);
  border: 1px solid var(--warning-100);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  color: var(--warning-700);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
}

.sd-hero {
  position: relative;
  isolation: isolate;
  overflow: hidden;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(400px, 0.76fr);
  align-items: center;
  gap: var(--space-6);
  min-height: 168px;
  padding: var(--space-6);
  border: 1px solid var(--hero-bd);
  border-radius: var(--radius-xl);
  background: var(--hero-grad);
  box-shadow: var(--hero-shadow);
  color: var(--hero-tx);
}

.sd-hero::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: -1;
  background-image:
    linear-gradient(var(--hero-grid) 1px, transparent 1px),
    linear-gradient(90deg, var(--hero-grid) 1px, transparent 1px);
  background-size: 30px 30px;
}

.sd-hero::after {
  content: '';
  position: absolute;
  z-index: -1;
  top: -132px;
  right: -80px;
  width: 260px;
  height: 260px;
  border: 1px solid var(--hero-chip-bd);
  border-radius: var(--radius-full);
  box-shadow: 0 0 0 42px var(--hero-chip-bg), 0 0 0 86px color-mix(in srgb, var(--hero-chip-bg), transparent 48%);
}

.sd-hero__identity {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  min-width: 0;
}

.sd-hero__avatar {
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  width: 62px;
  height: 62px;
  border: 1px solid var(--hero-chip-bd);
  border-radius: var(--radius-full);
  background: var(--hero-chip-bg);
  color: var(--hero-chip-hot-tx);
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-bold);
}

.sd-hero__copy {
  min-width: 0;
}

.sd-hero__name-line {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.sd-hero__eyebrow {
  color: var(--hero-sub);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  letter-spacing: 0.06em;
}

.sd-hero h2,
.sd-hero p {
  margin: 0;
}

.sd-hero h2 {
  margin-top: var(--space-2);
  max-width: 860px;
  color: var(--hero-tx);
  font-size: var(--font-size-xl);
  line-height: 1.5;
  font-weight: var(--font-weight-semibold);
  letter-spacing: -0.015em;
}

.sd-hero p {
  margin-top: var(--space-2);
  color: var(--hero-sub);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-base);
  overflow-wrap: anywhere;
}

.sd-hero__stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-2);
}

.sd-hero-stat {
  min-width: 0;
  padding: var(--space-3);
  border: 1px solid var(--hero-chip-bd);
  border-radius: var(--radius-card-sm);
  background: var(--hero-chip-bg);
}

.sd-hero-stat span,
.sd-hero-stat strong,
.sd-hero-stat small {
  display: block;
}

.sd-hero-stat span {
  color: var(--hero-sub);
  font-size: var(--font-size-xs);
}

.sd-hero-stat strong {
  margin-top: var(--space-1);
  color: var(--hero-tx);
  font-size: var(--font-size-metric-sm);
  line-height: 1.35;
  font-weight: var(--font-weight-semibold);
  font-variant-numeric: tabular-nums;
}

.sd-hero-stat strong.is-gap {
  color: var(--hero-warn);
}

.sd-hero-stat small {
  margin-top: var(--space-1);
  color: var(--hero-dim);
  font-size: var(--font-size-xs);
  line-height: 1.45;
}

.sd-truthbar {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: start;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-card-sm);
  background: var(--info-50);
}

.sd-truthbar__icon {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-md);
  background: var(--primary-100);
  color: var(--primary-700);
  font-weight: var(--font-weight-bold);
}

.sd-truthbar strong,
.sd-truthbar p {
  margin: 0;
}

.sd-truthbar strong {
  color: var(--text-primary);
  font-size: var(--font-size-sm);
}

.sd-truthbar p {
  margin-top: var(--space-1);
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  line-height: var(--line-height-base);
}

.sd-flow-card :deep(.app-section-card__body) {
  padding-top: 0;
}

.sd-flow {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.sd-flow__item {
  display: grid;
  justify-items: center;
  align-content: center;
  min-height: 76px;
  padding: var(--space-2);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-card-sm);
  background: var(--bg-section);
  text-align: center;
}

.sd-flow__item.is-current {
  border-color: var(--primary-500);
  background: var(--primary-50);
}

.sd-flow__item > span {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-full);
  background: var(--primary-100);
  color: var(--primary-700);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-bold);
}

.sd-flow__item.is-current > span {
  background: var(--pri);
  color: var(--text-inverse);
}

.sd-flow__item strong {
  margin-top: var(--space-1);
  color: var(--text-primary);
  font-size: var(--font-size-xs);
}

.sd-flow__item small {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}

.sd-quick {
  display: grid;
  grid-template-columns: minmax(240px, 0.8fr) minmax(0, 2fr);
  gap: var(--space-4);
  padding: var(--space-4);
  border-color: var(--primary-100);
  background: linear-gradient(135deg, var(--primary-50), var(--bg-card) 62%);
}

.sd-quick__copy {
  display: grid;
  align-content: center;
  gap: var(--space-1);
}

.sd-quick__copy > span {
  color: var(--primary-700);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-bold);
  letter-spacing: 0.06em;
}

.sd-quick__copy > strong {
  color: var(--text-primary);
  font-size: var(--font-size-lg);
}

.sd-quick__copy > small {
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  line-height: var(--line-height-base);
}

.sd-quick__actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-2);
}

.sd-quick__btn {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  align-items: center;
  gap: 2px var(--space-2);
  min-height: 66px;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-card-sm);
  background: var(--bg-card);
  color: var(--text-primary);
  text-align: left;
  cursor: pointer;
}

.sd-quick__btn:hover,
.sd-quick__btn:focus-visible {
  border-color: var(--primary-500);
  box-shadow: var(--shadow-card-hover);
}

.sd-quick__btn > span {
  grid-row: 1 / span 2;
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: var(--radius-md);
  background: var(--primary-50);
  color: var(--primary-700);
  font-weight: var(--font-weight-bold);
}

.sd-quick__btn b {
  font-size: var(--font-size-sm);
}

.sd-quick__btn em {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  font-style: normal;
}

.sd-tabs {
  display: flex;
  gap: var(--space-1);
  max-width: 100%;
  padding: var(--space-1);
  overflow-x: auto;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-card-sm);
  background: var(--bg-card);
  box-shadow: var(--shadow-card);
  scrollbar-gutter: stable;
}

.sd-tab {
  flex: 0 0 auto;
  min-height: 36px;
  padding: 0 var(--space-3);
  border: 0;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
}

.sd-tab.is-active {
  background: var(--primary-50);
  color: var(--primary-700);
}

.sd-overview-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.68fr);
  align-items: start;
  gap: var(--space-4);
}

.sd-panel {
  overflow: hidden;
  border-radius: var(--radius-card-sm);
}

.sd-panel :deep(.app-section-card__body) {
  padding: var(--space-4);
}

.sd-domain-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}

.sd-domain-card {
  min-width: 0;
  min-height: 142px;
  padding: var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-card-sm);
  background: var(--bg-card);
}

.sd-domain-card.is-actionable {
  cursor: pointer;
}

.sd-domain-card.is-actionable:hover,
.sd-domain-card.is-actionable:focus-visible {
  border-color: var(--primary-500);
  background: var(--primary-25);
  box-shadow: var(--shadow-card-hover);
  outline: none;
}

.sd-domain-card.is-risk {
  border-color: var(--danger-100);
  background: var(--danger-50);
}

.sd-domain-card.is-attention {
  border-color: var(--warning-100);
  background: var(--warning-50);
}

.sd-domain-card.is-sensitive {
  border-color: var(--info-100);
  background: var(--info-50);
}

.sd-domain-card.is-gap {
  border-style: dashed;
}

.sd-domain-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.sd-domain-card__head > span {
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
}

.sd-domain-card > strong,
.sd-domain-card > p,
.sd-domain-card > small {
  display: block;
}

.sd-domain-card > strong {
  margin-top: var(--space-3);
  color: var(--text-primary);
  font-size: var(--font-size-base);
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.sd-domain-card > p {
  margin: var(--space-1) 0 0;
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  line-height: var(--line-height-base);
  overflow-wrap: anywhere;
}

.sd-domain-card > small {
  margin-top: var(--space-2);
  color: var(--primary-700);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
}

.sd-panel--timeline :deep(.app-section-card__body) {
  max-height: 520px;
  overflow-y: auto;
  scrollbar-gutter: stable;
}

.sd-timeline {
  position: relative;
  display: grid;
  gap: var(--space-4);
  margin: 0;
  padding: 0 0 0 var(--space-5);
  list-style: none;
}

.sd-timeline::before {
  content: '';
  position: absolute;
  top: 6px;
  bottom: 8px;
  left: 7px;
  width: 1px;
  background: var(--border-base);
}

.sd-timeline li {
  position: relative;
}

.sd-timeline__dot {
  position: absolute;
  top: 4px;
  left: calc(var(--space-5) * -1);
  width: 11px;
  height: 11px;
  border: 3px solid var(--primary-500);
  border-radius: var(--radius-full);
  background: var(--bg-card);
}

.sd-timeline strong,
.sd-timeline p,
.sd-timeline small {
  display: block;
}

.sd-timeline strong {
  color: var(--text-primary);
  font-size: var(--font-size-sm);
}

.sd-timeline p {
  margin: var(--space-1) 0 0;
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  line-height: var(--line-height-base);
}

.sd-timeline small {
  margin-top: var(--space-1);
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}

.sd-inline-loading {
  padding: var(--space-5);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  text-align: center;
}

.sd-gap-panel {
  display: grid;
  justify-items: start;
  gap: var(--space-2);
  padding: var(--space-4);
  border: 1px dashed var(--warning-100);
  border-radius: var(--radius-card-sm);
  background: var(--warning-50);
}

.sd-gap-panel strong,
.sd-gap-panel p {
  margin: 0;
}

.sd-gap-panel strong {
  color: var(--text-primary);
  font-size: var(--font-size-sm);
}

.sd-gap-panel p {
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  line-height: var(--line-height-base);
}

.sd-kv-grid,
.sd-campus-facts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  column-gap: var(--space-6);
}

.sd-campus-facts {
  gap: var(--space-3);
}

.sd-campus-facts > div {
  display: grid;
  gap: var(--space-1);
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-card-sm);
  background: var(--bg-section);
}

.sd-campus-facts span {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}

.sd-campus-facts strong {
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  overflow-wrap: anywhere;
}

.sd-risk-summary {
  display: grid;
  justify-items: start;
  gap: var(--space-2);
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-card-sm);
  background: var(--bg-section);
}

.sd-risk-summary strong {
  color: var(--text-primary);
  font-size: var(--font-size-base);
}

.sd-risk-summary p {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  line-height: var(--line-height-base);
}

.sd-risk {
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-card-sm);
}

.sd-risk__head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.sd-risk__title {
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
}

.sd-risk__desc {
  margin: var(--space-2) 0 0;
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  line-height: var(--line-height-base);
}

.sd-gap-top {
  margin-top: var(--space-3);
}

.sd-record-json {
  display: grid;
}

.sd-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.sd-field__label {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}

.sd-field__control {
  min-height: 36px;
  padding: 0 var(--space-2);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
}

.sd-field__control:focus-visible {
  border-color: var(--primary-500);
  outline: 2px solid var(--primary-100);
  outline-offset: 1px;
}

@media (max-width: 1366px) {
  .sd-hero {
    grid-template-columns: 1fr;
  }

  .sd-hero__stats {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .sd-overview-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 1120px) {
  .sd-flow {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .sd-quick {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .sd-hero__stats,
  .sd-quick__actions,
  .sd-domain-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .sd-degraded,
  .sd-truthbar {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .sd-degraded > button,
  .sd-truthbar > :deep(.app-status-tag) {
    grid-column: 2;
    justify-self: start;
  }
}

@media (max-width: 600px) {
  .sd-hero {
    padding: var(--space-4);
  }

  .sd-hero__identity {
    align-items: flex-start;
  }

  .sd-hero__stats,
  .sd-quick__actions,
  .sd-domain-grid,
  .sd-flow {
    grid-template-columns: 1fr;
  }
}
</style>
