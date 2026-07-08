<template>
  <BasePortalLayout title="组件开发预览" subtitle="基础能力验证" :menus="[]" active-key="">
    <section class="dev-section">
      <h1>基础能力验证</h1>
      <p>状态语义、数据安全、全局反馈与关键操作组件（非商业首页内容）</p>

      <div class="verification-block">
        <h3>状态与风险语义</h3>
        <div class="tag-row">
          <AppStatusTag v-for="s in statuses" :key="s" :status="s" :dot="s === 'REVIEWING'" />
          <AppRiskTag v-for="r in riskLevels" :key="r" :level="r" />
        </div>
      </div>

      <div class="verification-grid">
        <div class="verification-block">
          <h3>敏感信息保护</h3>
          <div class="data-list">
            <div>
              <span>手机号码</span><AppSensitiveText type="phone" value="13512346867" revealable />
            </div>
            <div>
              <span>身份证号</span
              ><AppSensitiveText type="idcard" value="430102200601011234" revealable />
            </div>
            <div>
              <span>学生姓名</span
              ><AppSensitiveText type="name" value="示例姓名" code="S2026-000001" />
            </div>
          </div>
        </div>
        <div class="verification-block">
          <h3>关键操作确认</h3>
          <AppInlineAlert
            type="warning"
            title="材料需要补充"
            description="材料页码不完整，请补充后重新提交。"
          >
            <template #actions
              ><button class="dev-btn dev-btn--primary" @click="showReturn = true">
                发起退回
              </button></template
            >
          </AppInlineAlert>
        </div>
      </div>

      <div class="verification-block">
        <h3>全局状态</h3>
        <div class="tag-row">
          <button
            v-for="s in globalStates"
            :key="s"
            class="dev-chip"
            :class="{ 'is-active': currentState === s }"
            @click="currentState = s"
          >
            {{ s }}
          </button>
        </div>
        <AppGlobalState :state="currentState" error-code="DEMO_500" @retry="currentState = 'ready'">
          <div class="ready-state">业务内容已就绪，默认插槽渲染正常。</div>
        </AppGlobalState>
      </div>

      <h2 class="dev-h2">第一阶段交付级公共组件</h2>
      <p class="dev-sub">安全体验 · 审计留痕 · 附件 · 批量 · 审批（均为展示/交互层，真实校验与流转由后端负责）</p>

      <div class="verification-grid">
        <div class="verification-block">
          <h3>权限体验按钮 AppPermissionButton</h3>
          <div class="tag-row">
            <AppPermissionButton :allowed="true" @click="onDemoClick('有权限-通过')">发起审批</AppPermissionButton>
            <AppPermissionButton :allowed="false" reason="无“成绩发布”权限，请联系教务处">发布成绩</AppPermissionButton>
            <AppPermissionButton :allowed="true" variant="danger" @click="onDemoClick('危险操作')">删除批次</AppPermissionButton>
            <AppPermissionButton :allowed="true" :loading="true">提交中</AppPermissionButton>
          </div>
          <p class="dev-note">🔒 = 前端体验层，越权拦截仍由后端接口完成。</p>
        </div>

        <div class="verification-block">
          <h3>导出 Excel AppExportButton</h3>
          <div class="tag-row">
            <AppExportButton :export-fn="demoExportFn">导出学生台账</AppExportButton>
            <AppExportButton :export-fn="demoExportFn" :has-permission="false">无权限导出</AppExportButton>
          </div>
          <p class="dev-note">演示环境未接后端导出，点击会真实提示失败（不伪造成功）。</p>
        </div>
      </div>

      <div class="verification-block">
        <h3>附件清单 AppFileList</h3>
        <AppFileList
          :files="demoFiles"
          removable
          @preview="onDemoClick('预览附件')"
          @download="onDemoClick('下载附件-写审计')"
          @remove="onDemoClick('移除附件')"
        />
      </div>

      <div class="verification-block">
        <h3>批量操作条 AppBatchActionBar</h3>
        <div class="tag-row">
          <button class="dev-chip" @click="batchCount = Math.min(batchCount + 3, 42)">+ 选中 3 项</button>
          <button class="dev-chip" @click="batchCount = 0">清空选择</button>
          <span class="dev-note">当前选中 {{ batchCount }} 项（选中后底部浮出操作条）</span>
        </div>
        <AppBatchActionBar
          :count="batchCount"
          :total="42"
          :actions="batchActions"
          :float="false"
          @action="onBatchAction"
          @clear="batchCount = 0"
          @select-all="batchCount = 42"
        />
      </div>

      <div class="verification-grid">
        <div class="verification-block">
          <h3>审批面板 AppApprovalPanel</h3>
          <AppApprovalPanel
            title="请假审批"
            status="PENDING_APPROVE"
            current-node="辅导员审批"
            current-handler="张老师"
            :history="demoApprovalHistory"
            :can-approve="true"
            :can-return="true"
            :can-reject="true"
            @approve="onApprove"
            @return="onApprove"
            @reject="onApprove"
          />
        </div>
        <div class="verification-block">
          <h3>操作留痕 AppAuditTrail</h3>
          <AppAuditTrail :records="demoAuditRecords" />
        </div>
      </div>

      <h2 class="dev-h2">第二阶段可用版公共组件</h2>
      <p class="dev-sub">工作台 · 展示 · 表单辅助</p>

      <div class="verification-block">
        <h3>指标卡 AppMetricCard（含 loading 骨架）</h3>
        <div class="metric-row">
          <AppMetricCard title="在读学生" :value="12480" unit="人" updated-at="09:00" trend-type="up" trend-quality="good" trend-label="较上周 +32" />
          <AppMetricCard title="高风险预警" :value="18" unit="人" accent="risk" trend-type="up" trend-quality="bad" trend-label="需处理" drillable @drill="onDemoClick('下钻预警')" />
          <AppMetricCard title="待审批" :value="7" unit="项" accent="warning" />
          <AppMetricCard title="加载中" value="—" :loading="true" />
        </div>
      </div>

      <div class="verification-grid">
        <div class="verification-block">
          <h3>工作流时间线 AppWorkflowTimeline</h3>
          <AppWorkflowTimeline :nodes="demoWfNodes" :current-index="2" />
        </div>
        <div class="verification-block">
          <h3>待办面板 AppTodoPanel</h3>
          <AppTodoPanel
            :items="demoTodos"
            show-more
            @open="onDemoClick('打开待办')"
            @action="onDemoClick('处理待办')"
            @more="onDemoClick('查看全部待办')"
          />
        </div>
      </div>

      <div class="verification-grid">
        <div class="verification-block">
          <h3>消息面板 AppNotificationPanel</h3>
          <AppNotificationPanel
            :items="demoNotifs"
            @open="onDemoClick('打开消息')"
            @read-all="markAllRead"
          />
        </div>
        <div class="verification-block">
          <h3>文本辅助 · 复制 / 帮助 / 字段提示</h3>
          <div class="data-list">
            <div><span>学号</span><AppCopyableText value="S2026-000188" @copied="onDemoClick('已复制学号')" /></div>
            <div>
              <span>综合测评得分
                <AppHelpTooltip content="综合测评 = 学业成绩70% + 素质拓展30%，每学期末结算。" />
              </span>
              <AppBadge :count="8" type="danger" />
            </div>
          </div>
          <AppFieldHint type="hint" text="请输入 11 位手机号，用于接收报到通知。" />
          <AppFieldHint type="error" text="手机号格式不正确。" />
          <AppFieldHint type="success" text="校验通过。" />
        </div>
      </div>

      <p class="dev-back"><router-link to="/">← 返回产品概览首页</router-link></p>
    </section>

    <AppConfirmDialog
      v-model:visible="showReturn"
      type="warning"
      title="确认退回"
      message="退回后将生成学生待办和消息，学生修改后可重新提交。"
      confirm-text="确认退回"
      require-reason
      reason-label="退回原因"
      show-notify
      @confirm="showReturn = false"
    />
  </BasePortalLayout>
</template>

<script>
import {
  AppStatusTag,
  AppRiskTag,
  AppGlobalState,
  AppSensitiveText,
  AppConfirmDialog,
  AppInlineAlert,
  AppPermissionButton,
  AppExportButton,
  AppFileList,
  AppBatchActionBar,
  AppApprovalPanel,
  AppAuditTrail,
  AppMetricCard,
  AppWorkflowTimeline,
  AppTodoPanel,
  AppNotificationPanel,
  AppCopyableText,
  AppHelpTooltip,
  AppFieldHint
} from '@/components/common'
import { AppBadge } from '@/components/ui'
import { toast } from '@/utils/toast'
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'

export default {
  name: 'ComponentDevPreview',
  components: {
    BasePortalLayout,
    AppStatusTag,
    AppRiskTag,
    AppGlobalState,
    AppSensitiveText,
    AppConfirmDialog,
    AppInlineAlert,
    AppPermissionButton,
    AppExportButton,
    AppFileList,
    AppBatchActionBar,
    AppApprovalPanel,
    AppAuditTrail,
    AppMetricCard,
    AppWorkflowTimeline,
    AppTodoPanel,
    AppNotificationPanel,
    AppCopyableText,
    AppHelpTooltip,
    AppFieldHint,
    AppBadge
  },
  data() {
    return {
      showReturn: false,
      currentState: 'ready',
      batchCount: 0,
      batchActions: [
        { key: 'export', label: '批量导出', icon: '⬇' },
        { key: 'assign', label: '批量分配' },
        { key: 'delete', label: '批量删除', danger: true }
      ],
      demoFiles: [
        { id: 1, name: '开题报告.pdf', size: 348160, uploadedAt: '2026-06-20', uploader: '李同学', status: 'done' },
        { id: 2, name: '困难认定材料.jpg', size: 1258291, uploadedAt: '2026-06-21', sensitive: true, status: 'done' },
        { id: 3, name: '实习周报.docx', size: 51200, status: 'uploading', progress: 62 },
        { id: 4, name: '成绩单.xlsx', size: 20480, status: 'error' }
      ],
      demoApprovalHistory: [
        { id: 1, node: '学生提交', result: '已提交', handler: '李同学', at: '2026-06-20 09:12' },
        { id: 2, node: '班主任预审', result: '已通过', handler: '王老师', at: '2026-06-20 10:03', comment: '情况属实，同意上报。' }
      ],
      demoAuditRecords: [
        { id: 1, action: '导出学生名单', actor: '张老师', actorRole: '辅导员', reason: '学院例会名单核对', ip: '10.12.3.44', at: '2026-06-22 14:20', result: '成功' },
        { id: 2, action: '查看完整手机号', actor: '李老师', actorRole: '资助老师', reason: '奖助电话核实', ip: '10.12.3.88', at: '2026-06-22 15:01', result: '成功' },
        { id: 3, action: '尝试跨班级查看', actor: '赵老师', actorRole: '专业课教师', ip: '10.12.4.10', at: '2026-06-22 16:30', result: '越权拒绝' }
      ],
      demoWfNodes: [
        { name: '学生提交', result: '已提交', handler: '李同学', at: '06-20 09:12' },
        { name: '班主任预审', result: '已通过', handler: '王老师', at: '06-20 10:03' },
        { name: '辅导员审批', result: '审批中', handler: '张老师' },
        { name: '学院复核', handler: '待处理' },
        { name: '归档' }
      ],
      demoTodos: [
        { id: 1, title: '3 份请假单待审批', meta: '计算机2301班', tag: '请假', priority: 'high', actionText: '去审批' },
        { id: 2, title: '困难认定材料待复核', meta: '2 人', at: '今天', overdue: true, actionText: '去处理' },
        { id: 3, title: '毕设中期检查提醒', meta: '本周截止', priority: 'normal' }
      ],
      demoNotifs: [
        { id: 1, title: '成绩发布审批已通过', desc: '《数据结构》期末成绩已通过教务处审核并发布。', at: '10 分钟前', read: false, type: 'success' },
        { id: 2, title: '高风险预警：出勤异常', desc: '张三近 7 天缺勤 3 次，请及时谈话。', at: '1 小时前', read: false, type: 'danger' },
        { id: 3, title: '待你审批：调停课申请', at: '昨天', read: true, type: 'approval' }
      ],
      statuses: [
        'DRAFT',
        'PENDING_REVIEW',
        'REVIEWING',
        'APPROVED',
        'RETURNED',
        'REJECTED',
        'OVERDUE',
        'ARCHIVED',
        'READONLY'
      ],
      riskLevels: ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'],
      globalStates: [
        'ready',
        'loading',
        'empty',
        'error',
        'forbidden',
        'offline',
        'readonly',
        'noLicense'
      ]
    }
  },
  methods: {
    onDemoClick(label) {
      toast.success(`触发：${label}`)
    },
    onBatchAction(a) {
      toast.success(`批量动作：${a.label}（对 ${this.batchCount} 项）`)
    },
    onApprove(payload) {
      toast.success(`审批已提交${payload && payload.reason ? '：' + payload.reason : ''}`)
    },
    markAllRead() {
      this.demoNotifs = this.demoNotifs.map((m) => ({ ...m, read: true }))
      toast.success('已全部标为已读')
    },
    // 演示环境：不接后端，真实返回失败，绝不伪造导出成功
    async demoExportFn() {
      return { code: 1, message: '演示环境未接后端导出接口' }
    }
  }
}
</script>

<style scoped>
.dev-section {
  max-width: 960px;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.dev-section h1 {
  margin: 0;
  font-size: var(--font-size-xl);
}
.dev-section > p {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}
.verification-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}
.verification-block {
  padding: var(--space-5);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-card-sm);
  background: var(--bg-card);
  box-shadow: var(--shadow-card);
}
.verification-block h3 {
  margin: 0 0 var(--space-4);
  font-size: var(--font-size-base);
}
.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.data-list {
  display: grid;
  gap: var(--space-3);
}
.data-list div {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.ready-state {
  padding: var(--space-6);
  border: 1px dashed var(--border-base);
  border-radius: var(--radius-md);
  text-align: center;
  color: var(--text-secondary);
}
.dev-btn {
  height: 36px;
  padding: 0 var(--space-4);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-base);
  cursor: pointer;
}
.dev-btn--primary {
  background: var(--primary-600);
  color: #fff;
  border-color: var(--primary-600);
}
.dev-chip {
  height: 30px;
  padding: 0 var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-full);
  background: var(--bg-card);
  cursor: pointer;
  font-size: var(--font-size-xs);
}
.dev-chip.is-active {
  border-color: var(--primary-100);
  background: var(--primary-50);
  color: var(--primary-700);
}
.dev-h2 {
  margin: var(--space-6) 0 0;
  font-size: var(--font-size-lg);
  border-top: 1px solid var(--border-light);
  padding-top: var(--space-6);
}
.dev-sub {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}
.dev-note {
  margin: var(--space-3) 0 0;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.metric-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-3);
}
@media (max-width: 760px) {
  .metric-row { grid-template-columns: 1fr 1fr; }
}
.dev-back {
  margin-top: var(--space-4);
  font-size: var(--font-size-sm);
}
.dev-back a {
  color: var(--primary-600);
  text-decoration: none;
}
@media (max-width: 760px) {
  .verification-grid {
    grid-template-columns: 1fr;
  }
}
</style>
