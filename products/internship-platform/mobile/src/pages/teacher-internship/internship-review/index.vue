<template>
  <view class="mobile-page mobile-teacher page-wrap teacher-process internship-flow">
    <view :inert="weeklyReviewPanel ? true : undefined" :aria-hidden="weeklyReviewPanel ? 'true' : undefined">
    <MobileNavBar variant="teacher" :title="tab === 'weekly' ? '周报批阅' : tab === 'visit' ? '巡访计划任务' : '打卡异常办理'" show-back />
    <MobileGlobalState :state="state" :title="state === 'empty' ? '暂无可办理的实习批次' : ''"
      :description="loadError" @retry="focusVisitId ? loadFocusedVisit() : load()">
      <view v-if="data">
        <view v-if="batches.length" class="page-pad ir__batch">
          <text class="ir__batch-label">当前实习批次</text>
          <picker class="mobile-picker" :range="batches" range-key="name" :value="batchIndex" :disabled="acting || visitActing" @change="onBatchChange">
            <view class="ir__batch-choice"><text>{{ currentBatchLabel }}</text><text>切换 ›</text></view>
          </picker>
        </view>
        <button v-if="!focusReportId" class="mobile-control btn btn-ghost" :aria-expanded="moreEntriesOpen" @click="moreEntriesOpen=!moreEntriesOpen">{{ moreEntriesOpen ? '收起其他业务入口' : '其他业务入口' }}</button><view v-if="moreEntriesOpen" class="page-pad ir__quick">
          <button class="mobile-control ir__quick-btn" @click="openExemptions">免签审批</button>
          <button class="mobile-control ir__quick-btn" @click="openMaterials">材料审核</button>
          <button class="mobile-control ir__quick-btn" @click="openPayroll">工资单审核</button>
          <button v-if="internshipContext.can('internship.stats.view')" class="mobile-control ir__quick-btn" @click="openSchoolStats">校级统计</button>
        </view>
        <view class="ir__tabs page-pad"><MobileSegmented :items="tabs" v-model="tab" /></view>
        <view class="page-pad ir__page" style="padding-top:0;">
          <view v-if="weeklyReceipt && tab === 'weekly'" class="card flow-review-receipt" role="status">
            <view class="flow-result-head"><MobileTaskIcon :name="weeklyReceipt.type === 'pass' ? 'check' : 'alert-circle'" :tone="weeklyReceipt.type === 'pass' ? 'teal' : 'amber'" /><view class="flex-1"><text class="flow-title">{{ weeklyReceipt.type === 'pass' ? '批阅已通过' : '已退回，等待学生修改' }}</text><text class="flow-copy">{{ weeklyReceipt.student }} · {{ weeklyReceipt.week }}</text></view></view>
            <text v-if="weeklyReceipt.comment">本次意见：{{ weeklyReceipt.comment }}</text><text v-if="weeklyReceipt.ratingLevel">五级评价：{{ weeklyReceipt.ratingLevel }}级</text>
            <text class="flow-copy">{{ weeklyReceipt.type === 'pass' ? '本次批阅已完成，学生可查看结果；历史提交版本继续保留。' : '接下来由学生修改原周报并重新提交，原版本继续保留。' }}</text>
            <view class="flow-review-footer"><button class="mobile-control btn btn-ghost" @click="returnToTodos">返回待办</button><button class="mobile-control btn btn-primary" @click="weeklyReceipt = null">继续查看列表</button></view>
          </view>
          <ReportObligations v-if="tab === 'weekly' && batchId && !hidden && !focusReportId" :key="batchId" :batch-id="batchId" :can-review="internshipContext.can('internship.report.review')" initial-type="WEEKLY" />
          <view v-if="!focusReportId && (tab === 'visit' ? visitPlans.length > 0 : tab === 'weekly' ? data.reports.length > 0 : data.abnormal.length > 0)" class="card ir__summary">
            <view class="ir__summary-main">
              <text class="ir__summary-label">{{ tabSummaryLabel }}</text>
              <view class="ir__summary-value"><text>{{ tabSummaryCount }}</text><text>{{ tabSummaryUnit }}</text></view>
              <text class="ir__summary-note">{{ tabSummaryConclusion }}</text>
            </view>
            <view class="ir__summary-metrics" v-if="tab === 'weekly'">
              <view class="ir__metric"><text>{{ weeklyPendingCount }}</text><text>待批阅</text></view>
              <view class="ir__metric is-danger"><text>{{ overdueCount }}</text><text>逾期</text></view>
              <view class="ir__metric is-warning"><text>{{ weeklyRiskCount }}</text><text>已加载风险提示</text></view>
            </view>
            <view class="ir__summary-metrics" v-else-if="tab === 'visit'">
              <view class="ir__metric"><text>{{ visitState === 'ready' ? visitTotal : '—' }}</text><text>巡访计划总数</text></view>
              <view class="ir__metric is-success"><text>{{ visitedStudentCount }}</text><text>已加载计划已巡访</text></view>
              <view class="ir__metric is-warning"><text>{{ pendingVisitStudentCount }}</text><text>已加载计划待巡访</text></view>
            </view>
            <view class="ir__summary-metrics" v-else>
              <view class="ir__metric is-danger"><text>{{ abnormalPendingCount }}</text><text>待处理</text></view>
              <view class="ir__metric"><text>{{ data.abnormal.length }}</text><text>已加载</text></view>
              <view class="ir__metric"><text>{{ data.pagination?.exceptionTotal || 0 }}</text><text>待处理总数</text></view>
            </view>
          </view>

          <MobileInlineAlert v-if="data.errors && data.errors.length" type="warning" title="部分实习数据暂不可用" :description="data.errors.map(item => item.message || '请刷新后重试，恢复前不能把空列表当作已处理完成').join('；')" />
          <MobileInlineAlert v-if="tab !== 'weekly'" :type="tab === 'abnormal' ? 'warning' : 'info'" :description="tabHelpText" />

          <view v-if="tab !== 'visit' && sequentialItems.length > 1" class="ir__queue-bar">
            <text class="ir__queue-note">逐条处理 {{ sequentialItems.length }} 条{{ tab === 'weekly' ? '周报' : '异常' }}</text>
            <button class="mobile-control ir__queue-toggle" :aria-pressed="sequentialMode" @click="sequentialMode ? stopSequential() : startSequential()">{{ sequentialMode ? '退出连续处理' : '连续处理' }}</button>
          </view>

          <MobileSequentialQueue
            v-if="tab !== 'visit' && sequentialMode"
            :title="tab === 'weekly' ? '周报连续批阅' : '异常连续处理'"
            :items="sequentialItems"
            :current-index="sequentialIndex"
            :loading="acting"
            :conflict="sequentialConflict"
            @open="openSequentialItem"
            @next="nextSequential"
          >
            <template #default="{ item, blocked }">
              <view v-if="tab === 'weekly'" class="ir ir__queue-item" :class="{ 'is-risk': item.riskFlag }">
                <view class="row-between ir__head">
                  <view class="flex-1 ir__identity"><view class="row" style="gap:6px;"><text class="t-md t-bold">{{ item.student }}</text><text class="ir__week">{{ item.week }}</text></view><text class="ir__company">{{ item.company }}{{ item.post ? ' · ' + item.post : '' }}</text></view>
                  <MobileStatusTag :status="item.status" :label="item.statusLabel" />
                </view>
                <view class="ir__meta">
                  <view><text>正文长度</text><text>{{ item.wordCount || 0 }} 字</text></view>
                  <view><text>提交版本</text><text>第 {{ item.version || 1 }} 版</text></view>
                  <view :class="{ 'is-danger': item.riskFlag }"><text>内容风险</text><text>{{ item.riskFlag ? '有风险提示' : '未标记' }}</text></view>
                </view>
                <view v-if="item._body === 'ready'" class="ir__body">
                  <view class="ir__section"><text class="ir__label">本周工作</text><text class="ir__text">{{ item.tasks || '—' }}</text></view>
                  <view class="ir__section"><text class="ir__label">主要收获</text><text class="ir__text">{{ item.gain || '—' }}</text></view>
                  <view class="ir__section"><text class="ir__label">问题与计划</text><text class="ir__text">{{ item.problem || '—' }}</text></view>
                  <view v-if="(item.attachments || []).length" class="ir__section">
                    <text class="ir__label">图片/视频附件</text>
                    <view v-for="file in item.attachments" :key="file.fileId" class="ir__attachment" @click.stop="openWeeklyAttachment(file)">
                      <text class="ir__text flex-1">{{ file.fileName || '附件' }}</text><text class="ir__attachment-open">查看</text>
                    </view>
                  </view>
                </view>
                <view v-else-if="item._body === 'loading'" class="ir__bodyhint">正在加载周报正文…</view>
                <view v-else-if="item._body === 'error'" class="ir__bodyhint is-link" @click="loadBody(item)">正文加载失败，点击重试</view>
                <view v-else class="ir__bodybtn" @click="loadBody(item)"><text>展开查看完整正文 ▾</text></view>
                <view class="ir__actions">
                  <button class="mobile-control btn btn-ghost flex-1" :disabled="blocked" @click="review(item, 'return')">退回修改</button>
                  <button class="mobile-control ir__pass flex-1" :disabled="blocked" @click="review(item, 'pass')">批阅通过</button>
                </view>
                <button v-if="sequentialConflict" class="mobile-control btn btn-ghost" @click="restartSequential">已刷新，重新开始当前队列</button>
              </view>

              <view v-else class="ir ir__queue-item is-risk">
                <view class="row-between ir__head"><view class="flex-1 ir__identity"><text class="t-md t-bold">{{ item.student }}</text><text class="ir__company">{{ [item.className, item.company, item.post].filter(Boolean).join(' · ') || '实习信息待核对' }}</text></view><MobileStatusTag :status="item.status" :label="item.statusLabel" /></view>
                <view class="ir__ck">
                  <view class="ir__ck-row"><text class="ir__label">异常类型</text><text class="ir__text is-danger">{{ item.typeLabel || '打卡异常' }}</text></view>
                  <view class="ir__ck-row"><text class="ir__label">异常编号</text><text class="ir__text">{{ item.id || '—' }}</text></view>
                  <view class="ir__ck-row"><text class="ir__label">异常时间</text><text class="ir__text">{{ item.time || '—' }}</text></view>
                  <view class="ir__ck-row"><text class="ir__label">距离信息</text><text class="ir__text">{{ item.distance || '—' }}</text></view>
                  <view class="ir__ck-row"><text class="ir__label">定位精度</text><text class="ir__text">{{ item.accuracy || '—' }}</text></view>
                  <view class="ir__ck-row"><text class="ir__label">打卡地址</text><text class="ir__text flex-1">{{ item.address || '—' }}</text></view>
                  <view class="ir__ck-row"><text class="ir__label">设备风险</text><text class="ir__text">{{ item.deviceRisk || '—' }}</text></view>
                  <view v-if="item.streak" class="ir__ck-row"><text class="ir__label">连续异常</text><text class="ir__text">{{ item.streak }}</text></view>
                  <view class="ir__ck-row"><text class="ir__label">学生说明</text><text class="ir__text flex-1">{{ item.note || '学生未填写说明' }}</text></view>
                  <view v-if="item.appealStatus || item.appealNote" class="ir__ck-row"><text class="ir__label">学生申诉</text><text class="ir__text flex-1">{{ item.appealNote || item.appealStatusLabel || '申诉状态待核对' }}</text></view>
                </view>
                <MobileInlineAlert v-if="!canDecideException(item)" type="danger" title="证据不足，暂不能处理" :description="decisionFactMessage(item)" />
                <view class="ir__next is-warning"><text class="ir__next-label">处理原则</text><text class="ir__next-text">超范围不直接认定作弊，应结合学生说明、定位信息和实际工作情况人工判断。</text></view>
                <view class="ir__actions is-three">
                  <button class="mobile-control btn btn-ghost flex-1" :disabled="blocked || !canDecideException(item)" @click="ck(item, 'reject')">异常计入</button>
                  <button class="mobile-control ir__pass flex-1" :disabled="blocked || !canDecideException(item)" @click="ck(item, 'ok')">标记合理</button>
                  <button class="mobile-control ir__risk flex-1" :disabled="blocked || !canDecideException(item)" @click="ck(item, 'risk')">转风险</button>
                </view>
                <button v-if="sequentialConflict" class="mobile-control btn btn-ghost" @click="restartSequential">已刷新，重新开始当前队列</button>
              </view>
            </template>
          </MobileSequentialQueue>

          <view v-else-if="tab === 'weekly'" class="stack">
            <MobileGlobalState v-if="weeklySourceError" state="error" title="周报暂无法读取" :description="weeklySourceError.message" />
            <MobileGlobalState v-else-if="!data.reports.length" state="empty" title="暂无待批阅周报" description="学生提交或重新提交后，会在这里等待批阅。" />
            <view v-for="w in pagedSlice(data.reports)" :key="w.id" class="ir card" :class="{ 'is-risk': w.riskFlag || w.overdue }">
              <view class="row-between ir__head">
                <view class="flex-1 ir__identity"><view class="row" style="gap:6px;"><text class="t-md t-bold">{{ w.student }}</text><text class="ir__week">{{ w.week }}</text></view><text class="ir__company">{{ w.company }}{{ w.post ? ' · ' + w.post : '' }}</text></view>
                <MobileStatusTag :status="w.status" :label="w.statusLabel" />
              </view>
              <MobileInlineAlert v-if="w.overdue" type="danger" description="本周周报逾期未交，5分钟内不可重复提醒。" />
              <template v-else>
                <view class="ir__meta">
                  <view><text>正文长度</text><text>{{ w.wordCount || 0 }} 字</text></view>
                  <view><text>提交版本</text><text>{{ w.isResubmit ? `重交第 ${w.version || 1} 版` : `第 ${w.version || 1} 版` }}</text></view>
                  <view :class="{ 'is-danger': w.riskFlag }"><text>内容风险</text><text>{{ w.riskFlag ? '有风险提示' : '未标记' }}</text></view>
                </view>
                <view v-if="w._body === 'ready'" class="ir__body">
                  <view class="ir__section"><text class="ir__label">本周工作</text><text class="ir__text">{{ w.tasks || '—' }}</text></view>
                  <view class="ir__section"><text class="ir__label">主要收获</text><text class="ir__text">{{ w.gain || '—' }}</text></view>
                  <view class="ir__section"><text class="ir__label">问题与计划</text><text class="ir__text">{{ w.problem || '—' }}</text></view>
                  <view v-if="(w.attachments || []).length" class="ir__section">
                    <text class="ir__label">图片/视频附件</text>
                    <view v-for="file in w.attachments" :key="file.fileId" class="ir__attachment" @click.stop="openWeeklyAttachment(file)">
                      <text class="ir__text flex-1">{{ file.fileName || '附件' }}</text><text class="ir__attachment-open">查看</text>
                    </view>
                  </view>
                </view>
                <view v-else-if="w._body === 'loading'" class="ir__bodyhint">正在加载周报正文…</view>
                <view v-else-if="w._body === 'error'" class="ir__bodyhint is-link" @click="loadBody(w)">正文加载失败，点击重试</view>
                <view v-else class="ir__bodybtn" @click="loadBody(w)"><text>展开查看完整正文 ▾</text></view>
                <view v-if="w.feedback" class="ir__feedback"><text class="ir__feedback-label">最近评阅意见</text><text class="ir__feedback-text">{{ w.feedback }}</text><text v-if="w.score" class="ir__score">评级 {{ w.score }}</text></view>
                <view class="ir__next"><text class="ir__next-label">批阅重点</text><text class="ir__next-text">先阅读完整正文，核对工作内容、收获和问题是否具体；退回时写明可执行修改要求。</text></view>
              </template>
              <view class="ir__actions">
                <template v-if="w.overdue">
                  <button class="mobile-control ir__pass flex-1" :disabled="remindActingId === String(w.id)" @click="remindWeekly(w)">{{ remindActingId === String(w.id) ? '发送中…' : '发送催交' }}</button>
                </template>
                <template v-else-if="w.status === 'PENDING_REVIEW'">
                  <button class="mobile-control btn btn-ghost flex-1" :disabled="acting" @click="review(w, 'return')">退回修改</button>
                  <button class="mobile-control ir__pass flex-1" :disabled="acting" @click="review(w, 'pass')">批阅通过</button>
                </template>
                <text v-else class="ir__done-text flex-1">该周报已完成批阅</text>
              </view>
            </view>
            <button v-if="queueFooter('weekly') === 'more'" class="mobile-control ir__paging" :disabled="pagingBusy" @click="loadMoreQueue('weekly')">{{ pagingBusy ? '正在加载…' : '加载更多周报' }}</button>
            <view v-else-if="!weeklySourceError && queueFooter('weekly') === 'end'" class="ir__paging is-end">没有更多了</view>
          </view>

          <view v-else-if="tab === 'visit'" class="stack">
            <view class="card ir"><input class="mobile-input" v-model="visitKeyword" placeholder="按当前实习企业查找学生" maxlength="100" /><button class="mobile-control" :disabled="visitActing || visitPaging || !!visitTarget" @click="searchVisitTargets">查询企业与学生</button></view>
            <MobileGlobalState v-if="visitState === 'loading'" state="loading" />
            <MobileGlobalState v-else-if="visitState === 'error'" state="error" @retry="loadVisits" />
            <MobileGlobalState v-else-if="!visitPlans.length" state="empty" title="暂无待执行巡访计划" description="等待学校下发；临时指导可从工作台新增。" />
            <template v-else>
              <view v-for="p in visitPlans" :key="p.id" class="ir card">
                <view class="row-between ir__head"><view class="flex-1 ir__identity"><text class="t-md t-bold">{{ p.enterpriseName || '企业待定' }}</text><text class="ir__company" v-if="p.location">{{ p.location }}</text></view><text class="ir__week">{{ p.planDate || '待定日期' }}</text></view>
                <view class="ir__visit-summary"><text>计划学生 {{ p.studentTotal }} 人</text><text>已巡访 {{ p.visitedStudentCount }} 人</text></view>
                <view class="ir__visit-students">
                  <text v-if="!p.students.length">本计划当前没有匹配企业的可查看学生。</text>
                  <view v-for="s in p.students" :key="s.name + ':' + s.internshipId" class="ir__visit-row">
                    <view class="flex-1 ir__visit-copy"><text class="t-md">{{ s.name }}</text><text>{{ s.visited ? '本计划已留巡访记录' : '尚未记录巡访执行证据' }}</text></view>
                    <text v-if="s.visited" class="ir__visit-done">已巡访</text>
                    <button v-if="s.visited && s.visitId" class="mobile-control ir__visit-btn" :disabled="visitActing" @click="openRecordedVisit(s, p)">查看记录</button>
                    <button v-else class="mobile-control ir__visit-btn" :disabled="!s.resolvable || visitActing" @click="openVisitForm(s, p)">{{ s.resolvable ? '记录巡访' : '未匹配学生' }}</button>
                  </view>
                </view>
                <button class="mobile-control" v-if="p.studentHasMore" :disabled="p.loadingStudents || visitActing" @click="loadMoreVisitStudents(p)">{{ p.loadingStudents ? '正在加载…' : '加载本计划更多学生' }}</button>
              </view>
              <button class="mobile-control" v-if="visitHasMore" :disabled="visitPaging || visitActing" @click="loadVisits({ append: true })">{{ visitPaging ? '正在加载…' : '加载更多巡访计划' }}</button>
            </template>
          </view>

          <view v-else class="stack">
            <MobileGlobalState v-if="abnormalSourceError" state="error" title="考勤异常暂无法读取" :description="abnormalSourceError.message" />
            <MobileGlobalState v-else-if="!data.abnormal.length" state="empty" title="暂无打卡异常" description="学生打卡异常（超范围或定位失败）会出现在这里。" />
            <view v-for="c in pagedSlice(data.abnormal)" :key="c.id" class="ir card is-risk">
              <view class="row-between ir__head"><view class="flex-1 ir__identity"><text class="t-md t-bold">{{ c.student }}</text><text class="ir__company">{{ [c.className, c.company, c.post].filter(Boolean).join(' · ') || '实习信息待核对' }}</text></view><MobileStatusTag :status="c.status" :label="c.statusLabel" /></view>
              <view class="ir__ck">
                <view class="ir__ck-row"><text class="ir__label">异常类型</text><text class="ir__text is-danger">{{ c.typeLabel || '打卡异常' }}</text></view>
                <view class="ir__ck-row"><text class="ir__label">异常编号</text><text class="ir__text">{{ c.id || '—' }}</text></view>
                <view class="ir__ck-row"><text class="ir__label">异常时间</text><text class="ir__text">{{ c.time || '—' }}</text></view>
                <view class="ir__ck-row"><text class="ir__label">距离信息</text><text class="ir__text">{{ c.distance || '—' }}</text></view>
                <view class="ir__ck-row"><text class="ir__label">定位精度</text><text class="ir__text">{{ c.accuracy || '—' }}</text></view>
                <view class="ir__ck-row"><text class="ir__label">打卡地址</text><text class="ir__text flex-1">{{ c.address || '—' }}</text></view>
                <view class="ir__ck-row"><text class="ir__label">设备风险</text><text class="ir__text">{{ c.deviceRisk || '—' }}</text></view>
                <view v-if="c.streak" class="ir__ck-row"><text class="ir__label">连续异常</text><text class="ir__text">{{ c.streak }}</text></view>
                <view class="ir__ck-row"><text class="ir__label">学生说明</text><text class="ir__text flex-1">{{ c.note || '学生未填写说明' }}</text></view>
                <view v-if="c.appealStatus || c.appealNote" class="ir__ck-row"><text class="ir__label">学生申诉</text><text class="ir__text flex-1">{{ c.appealNote || c.appealStatusLabel || '申诉状态待核对' }}</text></view>
              </view>
              <MobileInlineAlert v-if="!canDecideException(c)" type="danger" title="证据不足，暂不能处理" :description="decisionFactMessage(c)" />
              <view class="ir__next is-warning"><text class="ir__next-label">处理原则</text><text class="ir__next-text">超范围不直接认定作弊；转风险会形成 正式高风险记录，必须填写原因。</text></view>
              <view class="ir__actions is-three" v-if="c.status === 'PENDING_HANDLE'">
                <button class="mobile-control btn btn-ghost flex-1" :disabled="acting || !canDecideException(c)" @click="ck(c, 'reject')">异常计入</button>
                <button class="mobile-control ir__pass flex-1" :disabled="acting || !canDecideException(c)" @click="ck(c, 'ok')">标记合理</button>
                <button class="mobile-control ir__risk flex-1" :disabled="acting || !canDecideException(c)" @click="ck(c, 'risk')">转风险</button>
              </view>
              <text v-else class="ir__done-text">该异常已处理</text>
            </view>
            <button v-if="queueFooter('abnormal') === 'more'" class="mobile-control ir__paging" :disabled="pagingBusy" @click="loadMoreQueue('abnormal')">{{ pagingBusy ? '正在加载…' : '加载更多异常' }}</button>
            <view v-else-if="!abnormalSourceError && queueFooter('abnormal') === 'end'" class="ir__paging is-end">没有更多了</view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
    <view v-if="tab === 'visit' && (visitTarget || visitReceipt)" class="page-pad stack">
      <view v-if="visitReceipt" class="card ir">
        <text class="t-md t-bold">{{ visitReceipt.name }}的巡访已登记 · 原单 {{ visitReceipt.visitId }}</text>
        <text>登记结果已提交，学校可按权限查看；需要跟进时继续本条巡访。</text>
        <text v-if="visitResultError" role="alert">{{ visitResultError }}</text>
        <button class="mobile-control" v-if="visitResultError" :disabled="visitActing" @click="refreshVisitReceipt">重新读取登记结果</button>
        <text v-if="visitDetail">{{ visitDetail.title || '历史记录未填写标题' }} · {{ visitDetail.rectifyStatusLabel }}</text>
        <text v-if="visitDetail">{{ visitDetail.monthlyReport }}</text>
        <text v-if="visitDetail">{{ visitDetail.locationStatusLabel }}</text>
        <button class="mobile-control" v-if="visitDetail?.hasLocation && visitDetail?.canViewLocation" :disabled="visitLocationBusy" @click="readVisitLocation">查看本次巡访位置（留痕）</button>
        <text v-if="visitLocation">纬度 {{ visitLocation.latitude }}，经度 {{ visitLocation.longitude }}，精度约 {{ Math.round(visitLocation.accuracyM) }} 米；{{ visitLocation.coordinateSystem === 'WGS84' ? '全球卫星定位坐标' : '国内地图坐标' }}</text>
        <button class="mobile-control" v-if="visitDetail?.attachment?.fileId" @click="openVisitAttachment">查看巡访照片</button>
        <text v-if="visitDetail?.attachmentError" role="alert">{{ visitDetail.attachmentError }}</text>
        <text v-if="visitFollowResult">{{ visitFollowResult }}</text>
        <button class="mobile-control" v-if="visitDetail?.rectifyStatus === 'PENDING' && !visitFollowDraft" :disabled="visitActing || !!visitTarget" @click="beginVisitFollow">继续本条巡访整改</button>
        <view v-if="visitFollowDraft" class="stack">
          <textarea v-model="visitFollowDraft.note" class="mobile-textarea ir__follow-note" maxlength="500" :disabled="visitActing" placeholder="填写实际跟进情况及处理结果，不少于2字" />
          <template v-if="visitFollowDraft.conflict">
            <text>巡访状态已变化，原说明和版本已保留，请先重读核对。</text>
            <button class="mobile-control" :disabled="visitActing" @click="refreshVisitReceipt">重读本条巡访</button>
            <button class="mobile-control" v-if="visitFollowDraft.comparison?.rectifyStatus === 'PENDING'" :disabled="visitActing" @click="adoptVisitFollow">已核对，采用当前版本继续</button>
            <text v-else-if="visitFollowDraft.comparison">当前已无需继续整改，请关闭草稿。</text>
          </template>
          <button class="mobile-control" :disabled="visitActing || visitFollowDraft.conflict" @click="submitVisitFollow('PENDING')">记录跟进，继续整改</button>
          <button class="mobile-control" :disabled="visitActing || visitFollowDraft.conflict" @click="submitVisitFollow('DONE')">确认整改完成</button>
          <button class="mobile-control" :disabled="visitActing" @click="visitFollowDraft = null">关闭跟进草稿</button>
        </view>
      </view>
      <InternshipVisitEvidenceForm v-if="visitTarget" :key="visitTarget.planId + ':' + visitTarget.internshipId"
        :target="visitTarget" :submitting="visitActing" :active="!hidden && visitTarget.batchId === batchId"
        :conflicted="visitConflict" @adopt="adoptVisitContext" @submit="submitVisit" @cancel="closeVisitForm" />
    </view>
    <ReportFilePreview ref="reportPreview" />
    </view>
    <view v-if="weeklyReviewPanel" class="flow-review-overlay" @keydown.esc="closeWeeklyReview">
      <view class="flow-review-mask" @click="closeWeeklyReview" @touchmove.stop.prevent />
      <view ref="weeklyReviewSheet" class="flow-review-sheet" role="dialog" aria-modal="true" aria-labelledby="weekly-review-title">
        <view class="row-between"><view class="flex-1"><text id="weekly-review-title" class="flow-title">本次批阅</text><text class="flow-copy">{{ weeklyReviewPanel.row.student }} · {{ weeklyReviewPanel.row.week }} · 第 {{ weeklyReviewPanel.row.version || 1 }} 版</text></view><button class="mobile-control flow-review-close" :disabled="acting" @click="closeWeeklyReview">关闭</button></view>
        <view class="flow-review-choices" role="group" aria-label="批阅结果">
          <button class="mobile-control" :class="{ 'is-on': weeklyReviewPanel.draft.type === 'pass' }" :aria-pressed="weeklyReviewPanel.draft.type === 'pass'" :disabled="acting" @click="setWeeklyReviewType('pass')">通过</button>
          <button class="mobile-control" :class="{ 'is-on': weeklyReviewPanel.draft.type === 'return' }" :aria-pressed="weeklyReviewPanel.draft.type === 'return'" :disabled="acting" @click="setWeeklyReviewType('return')">退回修改</button>
        </view>
        <template v-if="weeklyReviewPanel.draft.type === 'pass'">
          <text class="flow-review-label">五级评价（必选）</text>
          <view class="flow-review-choices" role="group" aria-label="五级评价"><button v-for="level in 5" :key="level" class="mobile-control" :class="{ 'is-on': weeklyReviewPanel.draft.ratingLevel === level }" :aria-pressed="weeklyReviewPanel.draft.ratingLevel === level" :disabled="acting" @click="weeklyReviewPanel.draft.ratingLevel = level; weeklyReviewError = ''">{{ level }}级</button></view>
          <text class="flow-copy">1级需明显改进 · 3级合格 · 5级优秀</text>
        </template>
        <label for="weekly-review-comment" class="flow-review-label">{{ weeklyReviewPanel.draft.type === 'return' ? '修改要求（必填，至少5字）' : '评阅意见（选填）' }}</label>
        <textarea id="weekly-review-comment" v-model="weeklyReviewPanel.draft.comment" class="mobile-textarea flow-review-input" :disabled="acting" :maxlength="-1" :cursor-spacing="100" :adjust-position="true" :focus="true" placeholder="写清具体意见，方便学生理解和继续办理" @input="weeklyReviewError = ''" />
        <text class="flow-copy">{{ weeklyReviewPanel.draft.type === 'return' ? '学生将按此修改原周报，原提交版本继续保留。' : '确认前请核对原文、附件和评价等级。' }}</text>
        <text v-if="weeklyReviewError" class="flow-review-error" role="alert">{{ weeklyReviewError }}</text>
        <view class="flow-review-footer"><button class="mobile-control btn btn-ghost" :disabled="acting" @click="closeWeeklyReview">取消</button><button class="mobile-control btn btn-primary" :disabled="acting" @click="submitWeeklyReview">{{ acting ? '正在提交…' : weeklyReviewPanel.draft.type === 'pass' ? '确认通过' : '确认退回' }}</button></view>
      </view>
    </view>
  </view>
</template>

<script>
import InternshipVisitEvidenceForm from '@/components/teacher/InternshipVisitEvidenceForm.vue'
import MobileSequentialQueue from '@/components/teacher/MobileSequentialQueue.vue'
import ReportFilePreview from '@/components/ReportFilePreview.vue'
import ReportObligations from '@/components/teacher/ReportObligations.vue'
import { teacherApi } from '@/services/teacherApi'
import { teacherInternshipEvidenceV3Api } from '@/services/teacherInternshipEvidenceV3Api'
import { handleCheckin as handleCheckinV3 } from '@/services/teacherSequentialV3Api'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { normalizeError } from '@/services/request'
import { listPaging } from '@/utils/listPaging'
import { toast } from '@/utils/nav'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { fileSdk } from '@/services/fileSdk'

export default {
  components: { InternshipVisitEvidenceForm, MobileSequentialQueue, ReportFilePreview, ReportObligations },
  mixins: [listPaging(20)],
  data() {
    return {
      weeklyReviewPanel:null, weeklyReviewError:'', weeklyReceipt:null, moreEntriesOpen:false, data: null, state: 'loading', loadError: '', tab: 'weekly', acting: false, commandDrafts: {}, draftGeneration: currentSessionGeneration(),
      tabs: [{ key: 'weekly', label: '周报批阅' }, { key: 'visit', label: '巡访任务' }, { key: 'abnormal', label: '打卡异常' }],
      visitPlans: [], visitState: 'loading', visitActing: false, visitTarget: null, visitKeyword: '', visitSearch: '',
      visitLocation: null, visitLocationBusy: false, visitLocationEpoch: 0,
      visitPage: 1, visitTotal: 0, visitHasMore: false, visitPaging: false, visitOperation: 0,
      visitConflict: false, visitReceipt: null, visitDetail: null, visitResultError: '',
      focusVisitId: '', visitFollowDraft: null, visitFollowResult: '',
      remindActingId: '', sequentialMode: false, sequentialIndex: 0, sequentialConflict: false,
      pagingBusy: false, context: null, batches: [], batchId: '', batchIndex: 0,
      routeBatchId: '', focusReportId: '', focusExceptionId: '', readEpoch: 0, visitEpoch: 0, hidden: false
    }
  },
  computed: {
    internshipContext() { return useInternshipContextStore() },
    currentBatchLabel() {
      const batch = this.batches[this.batchIndex]
      return batch ? batch.name || batch.batchNo || '未命名批次' : '请选择实习批次'
    },
    weeklySourceError() { return this.data?.errors?.find(row => row.source === 'weeklyReport') },
    abnormalSourceError() { return this.data?.errors?.find(row => row.source === 'attendanceException') },
    weeklyPendingCount() { return this.weeklySourceError ? '—' : Number(this.data?.pagination?.weeklyPendingTotal || 0) },
    overdueCount() { return this.weeklySourceError ? '—' : Number(this.data?.pagination?.weeklyOverdueTotal || 0) },
    weeklyRiskCount() { return (this.data?.reports || []).filter((item) => item.riskFlag).length },
    abnormalPendingCount() { return this.abnormalSourceError ? '—' : Number(this.data?.pagination?.exceptionTotal || 0) },
    visitedStudentCount() { return this.visitState === 'ready' ? this.visitPlans.reduce((total, plan) => total + Number(plan.visitedStudentCount || 0), 0) : '—' },
    pendingVisitStudentCount() { return this.visitState === 'ready' ? this.visitPlans.reduce((total, plan) => total + Number(plan.studentTotal || 0) - Number(plan.visitedStudentCount || 0), 0) : '—' },
    tabSummaryLabel() { return this.tab === 'weekly' ? '周报办理情况' : this.tab === 'visit' ? '指导巡访进度' : '打卡异常办理情况' },
    tabSummaryCount() { return this.tab === 'weekly' ? this.weeklyPendingCount : this.tab === 'visit' ? this.pendingVisitStudentCount : this.abnormalPendingCount },
    tabSummaryUnit() { return this.tab === 'visit' ? '人待巡访' : '条待处理' },
    tabSummaryConclusion() {
      if ((this.tab === 'weekly' && this.weeklySourceError) || (this.tab === 'abnormal' && this.abnormalSourceError)) return '当前来源暂无法读取，请核对权限或稍后重试，不能据此判断待办数量。'
      if (this.tab === 'weekly') {
        if (this.overdueCount) return `有 ${this.overdueCount} 条逾期周报，可直接发送站内催交。`
        if (this.weeklyRiskCount) return `有 ${this.weeklyRiskCount} 条内容风险提示，展开正文重点核对。`
        return this.weeklyPendingCount ? '按提交顺序展开正文并完成批阅。' : '当前没有待批阅周报。'
      }
      if (this.tab === 'visit') {
        if (this.visitState !== 'ready') return '计划正在读取或读取失败，当前不能判断完成情况。'
        return `已加载 ${this.visitPlans.length}/${this.visitTotal} 份计划，其中有 ${this.pendingVisitStudentCount} 人次待巡访；同一学生在不同计划分别记录。`
      }
      return this.abnormalPendingCount ? `有 ${this.abnormalPendingCount} 条异常需要人工判断。` : '当前没有待处理打卡异常。'
    },
    tabHelpText() {
      if (this.tab === 'weekly') return '逾期催交通过站内消息提醒学生；待批周报仍先展开正文再逐条批阅。'
      if (this.tab === 'visit') return '教师位置默认不采集。'
      return '定位异常不等于作弊，请核实后处理；标记合理只办结异常，有效出勤仍以正常签到或已批准补卡为准。转风险须说明原因。'
    },
    sequentialItems() {
      if (!this.data || this.tab === 'visit') return []
      if (this.tab === 'weekly') return (this.data.reports || []).filter((item) => !item.overdue && item.status === 'PENDING_REVIEW')
      return (this.data.abnormal || []).filter((item) => item.status === 'PENDING_HANDLE')
    },
    sequentialCurrent() { return this.sequentialItems[this.sequentialIndex] || null }
  },
  onLoad(query) {
    if (['weekly', 'visit', 'abnormal'].includes(query?.tab)) this.tab = query.tab
    this.routeBatchId = String(query?.batchId || '')
    this.focusReportId = String(query?.recordId || '')
    this.focusExceptionId = String(query?.exceptionId || '')
    if (this.focusExceptionId) this.tab = 'abnormal'
    this.focusVisitId = String(query?.visitId || '')
    if (this.focusVisitId) { this.tab = 'visit'; this.loadFocusedVisit(); return }
    this.load(); this.loadVisits()
  },
  onShow() {
    if (this.hidden) {
      if (this.visitTarget && this.visitTarget.generation !== currentSessionGeneration()) this.visitTarget = null
      if (this.visitReceipt && this.visitReceipt.generation !== currentSessionGeneration()) {
        this.visitReceipt = null; this.visitDetail = null; this.visitFollowDraft = null; this.visitFollowResult = ''
        this.visitResultError = ''; this.focusVisitId = ''; this.routeBatchId = ''
      }
      this.hidden = false; this.load(); this.loadVisits()
      if (this.visitReceipt?.generation === currentSessionGeneration()) this.refreshVisitReceipt()
    }
  },
  onHide() { this.invalidateReads() },
  onUnload() { this.invalidateReads() },
  onReachBottom() { if (!this.sequentialMode && this.tab !== 'visit') this.loadMoreQueue(this.tab) },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    Promise.allSettled([this.load(), this.loadVisits()]).finally(() => uni.stopPullDownRefresh())
  },
  watch: {
    tab() {
      this.clearVisitLocation()
      this.pagedReset(); this.stopSequential()
      if (this.tab !== 'visit') {
        this.visitOperation++; this.visitActing = false; this.closeVisitForm()
        if (this.visitFollowDraft) { this.visitFollowDraft.conflict = true; this.visitFollowDraft.comparison = null }
      }
    }
  },
  methods: {
    openExemptions() { uni.navigateTo({ url: '/pages/teacher-internship/checkin-exemption/index' }) },
    openMaterials() { uni.navigateTo({ url: '/pages/teacher-internship/material-review/index' }) },
    openPayroll() { uni.navigateTo({ url: '/pages/teacher-internship/payroll-review/index' }) },
    openSchoolStats() { uni.navigateTo({ url: '/pages/teacher-internship/school-stats/index' }) },
    toast,
    invalidateReads() {
      this.clearVisitLocation()
      this.weeklyReviewPanel = null; this.weeklyReceipt = null; this.weeklyReviewError = ''
      this.hidden = true; this.readEpoch++; this.visitEpoch++; this.visitOperation++
      if (this.visitActing && this.visitTarget) this.visitConflict = true
      if (this.visitFollowDraft) { this.visitFollowDraft.conflict = true; this.visitFollowDraft.comparison = null }
      this.visitActing = false; this.visitPaging = false; this.pagingBusy = false; this.acting = false
      this.$refs.reportPreview?.reset()
    },
    readIsCurrent(epoch, generation) { return !this.hidden && epoch === this.readEpoch && generation === currentSessionGeneration() },
    async ensureBatchContext() {
      if (!this.context) this.context = useInternshipContextStore()
      if (!this.context.loaded) {
        this.context.restore()
        await this.context.load(true)
      }
      this.batches = this.context.batches || []
      if (this.routeBatchId) {
        if (!this.context.selectBatch(this.routeBatchId)) {
          throw { code: 'NO_PERMISSION', message: '此实习批次不在当前指导范围内' }
        }
      }
      this.batchId = String(this.context.selectedBatchId || '')
      this.batchIndex = Math.max(0, this.batches.findIndex((item) => String(item.id) === this.batchId))
      if (!this.batchId && !this.focusReportId && !this.focusExceptionId) {
        throw { code: 'BATCH_REQUIRED', message: '当前没有可办理的实习批次' }
      }
      return this.batchId
    },
    onBatchChange(event) {
      if (this.acting || this.visitActing) return
      this.commandDrafts = {}; this.weeklyReviewPanel = null; this.weeklyReceipt = null
      const selected = this.batches[Number(event?.detail?.value)]
      if (!selected || !this.context || !this.context.selectBatch(selected.id)) return
      this.batchId = String(this.context.selectedBatchId || '')
      this.batchIndex = Math.max(0, this.batches.findIndex((item) => String(item.id) === this.batchId))
      // 用户明确切换批次后不能继续带着另一批次待办的 recordId 请求。
      this.focusReportId = ''; this.focusExceptionId = ''; this.routeBatchId = ''
      this.visitEpoch++; this.visitOperation++; this.visitPlans = []; this.visitTotal = 0
      this.clearVisitLocation(); this.visitKeyword = ''; this.visitSearch = ''
      this.visitReceipt = null; this.visitDetail = null; this.visitResultError = ''; this.visitPaging = false
      this.focusVisitId = ''; this.visitFollowDraft = null; this.visitFollowResult = ''
      this.stopSequential(); this.closeVisitForm()
      this.load(); this.loadVisits()
    },
    pagingList() {
      if (!this.data) return []
      return this.tab === 'weekly' ? (this.data.reports || []) : (this.data.abnormal || [])
    },
    queueFooter(kind) {
      const list = kind === 'weekly' ? (this.data?.reports || []) : (this.data?.abnormal || [])
      if (!list.length) return ''
      if (this.pagerShown < list.length) return 'more'
      const pagination = this.data?.pagination || {}
      return (kind === 'weekly' ? pagination.weeklyHasMore : pagination.exceptionHasMore) ? 'more' : 'end'
    },
    async loadMoreQueue(kind) {
      if (this.pagingBusy || !this.data || !['weekly', 'abnormal'].includes(kind)) return
      const list = kind === 'weekly' ? this.data.reports : this.data.abnormal
      if (this.pagerShown < list.length) { this.pagedLoadMore(); return }
      const pagination = this.data.pagination || {}
      const hasMore = kind === 'weekly' ? pagination.weeklyHasMore : pagination.exceptionHasMore
      if (!hasMore) return
      const epoch = this.readEpoch, generation = currentSessionGeneration(), batchId = this.batchId
      this.pagingBusy = true
      try {
        const next = await teacherApi.getWeeklyReports({
          weeklyPage: kind === 'weekly' ? Number(pagination.weeklyPage || 1) + 1 : Number(pagination.weeklyPage || 1),
          exceptionPage: kind === 'abnormal' ? Number(pagination.exceptionPage || 1) + 1 : Number(pagination.exceptionPage || 1),
          batchId, pageSize: Number(pagination.pageSize || 20), append: true
        })
        if (!this.readIsCurrent(epoch, generation) || this.batchId !== batchId) return
        const key = kind === 'weekly' ? 'reports' : 'abnormal'
        const known = new Set((this.data[key] || []).map((item) => String(item.id)))
        this.data[key].push(...(next[key] || []).filter((item) => !known.has(String(item.id))))
        this.data.pagination = { ...pagination, ...(next.pagination || {}) }
        this.pagedLoadMore()
      } catch (e) {
        if (this.readIsCurrent(epoch, generation)) toast(normalizeError(e).text)
      } finally {
        if (this.readIsCurrent(epoch, generation)) this.pagingBusy = false
      }
    },
    startSequential() {
      if (!this.sequentialItems.length || this.tab === 'visit') return
      this.sequentialMode = true; this.sequentialIndex = 0; this.sequentialConflict = false
    },
    stopSequential() { this.sequentialMode = false; this.sequentialIndex = 0; this.sequentialConflict = false },
    restartSequential() { this.sequentialConflict = false; this.sequentialIndex = Math.max(0, Math.min(this.sequentialIndex, this.sequentialItems.length - 1)) },
    openSequentialItem(item) { if (item) toast(`${item.student || '当前学生'} · ${this.tab === 'weekly' ? item.week || '周报' : item.typeLabel || '异常'}`) },
    canDecideException(item) { return !!item?.decisionFactsComplete && Number.isInteger(item?.expectedVersion) && item.expectedVersion >= 0 },
    decisionFactMessage(item) {
      const missing = Array.isArray(item?.missingDecisionFacts) ? item.missingDecisionFacts.filter(Boolean) : []
      if (!Number.isInteger(item?.expectedVersion) || item.expectedVersion < 0) missing.push('对象版本')
      return `缺少${missing.length ? missing.join('、') : '完整定位或设备'}事实。请刷新；仍不完整时改在 PC 端核对完整证据。`
    },
    nextSequential() { if (!this.sequentialConflict && !this.acting && this.sequentialIndex < this.sequentialItems.length - 1) this.sequentialIndex += 1 },
    load(done) {
      const epoch = ++this.readEpoch, generation = currentSessionGeneration()
      if (this.draftGeneration !== generation) { this.weeklyReviewPanel = null; this.weeklyReceipt = null; this.commandDrafts = {}; this.draftGeneration = generation }
      this.state = 'loading'; this.loadError = ''; this.pagedReset()
      const currentId = this.sequentialCurrent && String(this.sequentialCurrent.id)
      this.data = null; this.pagingBusy = false
      const request = this.ensureBatchContext().then(() => {
        if (!this.readIsCurrent(epoch, generation)) return null
        // 从统一待办来的 URL 仅含 recordId 时，后端负责验证对象范围并回填真正
        // 批次；普通页面进入则严格使用已选批次，绝不以本地缓存猜测。
        const batchId = (this.focusReportId || this.focusExceptionId) && !this.routeBatchId ? '' : this.batchId
        return teacherApi.getWeeklyReports({
          batchId, focusReportId: this.focusReportId, focusExceptionId: this.focusExceptionId, weeklyPage: 1, exceptionPage: 1, pageSize: 20
        })
      }).then((d) => {
        if (!d || !this.readIsCurrent(epoch, generation)) return
        if (d.batchId) {
          if (!this.context.selectBatch(d.batchId)) throw { code: 'DATA_CONFLICT', message: '待办所属批次不在当前指导范围内' }
          this.batchId = String(d.batchId)
          this.batchIndex = Math.max(0, this.batches.findIndex((item) => String(item.id) === this.batchId))
        }
        this.focusReportId = ''
        this.focusExceptionId = ''
        d.reports.forEach((r) => { if (!r._body) r._body = 'idle' })
        this.data = d
        if (d.focusReportId) {
          const focused = this.data.reports.find(item => String(item.id) === d.focusReportId)
          if (focused && !focused.overdue) this.loadBody(focused)
        }
        this.tabs[0].badge = d.reports.filter((r) => r.status === 'PENDING_REVIEW').length
        this.tabs[2].badge = d.abnormal.filter((a) => a.status === 'PENDING_HANDLE').length
        if (this.sequentialMode && currentId) {
          const found = this.sequentialItems.findIndex((item) => String(item.id) === currentId)
          if (found >= 0) this.sequentialIndex = found
          else this.sequentialIndex = Math.max(0, Math.min(this.sequentialIndex, this.sequentialItems.length - 1))
          if (!this.sequentialItems.length) this.stopSequential()
        }
        this.state = 'ready'
        return d
      }).catch((e) => {
        if (!this.readIsCurrent(epoch, generation)) return
        if (e?.code === 'BATCH_REQUIRED') {
          this.state = 'empty'
          this.loadError = '当前指导范围内没有实习批次，请联系学校实习管理员核对批次与指导安排。'
        } else {
          const error = normalizeError(e)
          this.state = error.pageState || 'error'; this.loadError = error.text || ''
        }
      }).finally(() => { if (typeof done === 'function') done() })
      return request
    },
    afterSequentialSuccess(processedId, oldIndex) {
      if (!this.sequentialMode) return
      if (!this.sequentialItems.length) return this.stopSequential()
      const stillThere = this.sequentialItems.findIndex((item) => String(item.id) === String(processedId))
      if (stillThere >= 0) this.sequentialIndex = Math.min(stillThere + 1, this.sequentialItems.length - 1)
      else this.sequentialIndex = Math.max(0, Math.min(oldIndex, this.sequentialItems.length - 1))
    },
    loadBody(w) {
      if (!w || w._body === 'loading' || w._body === 'ready') return
      if (!/^\d+$/.test(String(w.id))) { w._body = 'error'; return }
      w._body = 'loading'
      const epoch = this.readEpoch, generation = currentSessionGeneration(), batchId = this.batchId
      const current = () => this.readIsCurrent(epoch, generation) && this.batchId === batchId && this.data?.reports?.includes(w)
      return teacherApi.getWeeklyDetail(w.id).then((d) => {
        if (!current()) return
        if (String(d.id) !== String(w.id) || String(d.batchId) !== String(batchId) || !Number.isInteger(d.version)) throw new Error('周报对象或版本不一致，请刷新原单')
        w.tasks = d.work; w.gain = d.harvest; w.problem = d.plan
        w.expectedVersion = d.version; w.status = d.status
        w.attachments = d.attachments || []
        w.immutableVersions = d.immutableVersions || []
        if (d.positionName) w.post = d.positionName
        if (d.reviewComment && !w.feedback) w.feedback = d.reviewComment
        w._body = 'ready'
      }).catch((e) => { if (current()) { w._body = 'error'; toast(normalizeError(e).text) } })
    },
    async openWeeklyAttachment(file) {
      await this.$refs.reportPreview.open(file)
      if (!this.hidden) uni.pageScrollTo({ selector: '.report-preview', duration: 200 })
    },
    remindWeekly(w) {
      const id = String(w && w.id || '')
      if (this.remindActingId || !/^\d+$/.test(id) || !w.overdue) return
      this.remindActingId = id
      teacherInternshipEvidenceV3Api.remindWeekly(id)
        .then(() => toast('站内催交提醒已发送'))
        .catch((e) => toast(normalizeError(e).text))
        .finally(() => { this.remindActingId = '' })
    },
    async loadVisits({ append = false } = {}) {
      if (this.hidden || (append && (this.visitPaging || !this.visitHasMore))) return
      const epoch = ++this.visitEpoch, generation = currentSessionGeneration()
      let batchId = this.batchId
      const current = () => !this.hidden && epoch === this.visitEpoch && generation === currentSessionGeneration() && batchId === this.batchId
      if (!append) { this.visitState = 'loading'; this.visitPlans = []; this.visitTotal = 0 }
      this.visitPaging = true
      try {
        batchId = await this.ensureBatchContext()
        if (!current()) return
        const page = append ? this.visitPage + 1 : 1
        const d = await teacherApi.getInternshipVisitPlans(batchId, { page, keyword: this.visitSearch })
        if (!current()) return
        if (String(d?.batchId) !== batchId || !Array.isArray(d?.plans)) throw new Error('巡访计划上下文不一致')
        const plans = d.plans.map(p => ({ ...p, loadingStudents: false }))
        this.visitPlans = append ? [...this.visitPlans, ...plans.filter(p => !this.visitPlans.some(old => old.id === p.id))] : plans
        this.visitPage = page; this.visitTotal = d.total; this.visitHasMore = d.hasMore === true
        this.tabs[1].badge = this.visitPlans.reduce((total, plan) => total + Number(plan.studentTotal || 0) - Number(plan.visitedStudentCount || 0), 0)
        this.visitState = 'ready'
        return d
      } catch (e) {
        if (!current()) return
        if (append) toast('更多巡访计划读取失败，请重试')
        else this.visitState = 'error'
      } finally { if (current()) this.visitPaging = false }
    },
    async loadMoreVisitStudents(plan) {
      if (this.hidden || this.visitActing || plan.loadingStudents || !plan.studentHasMore) return
      const epoch = this.visitEpoch, generation = currentSessionGeneration(), batchId = this.batchId
      const current = () => !this.hidden && epoch === this.visitEpoch && generation === currentSessionGeneration() &&
        batchId === this.batchId && this.visitPlans.includes(plan)
      plan.loadingStudents = true
      try {
        const d = await teacherApi.getInternshipVisitPlans(batchId, { planId: String(plan.id), studentPage: Number(plan.studentPage || 1) + 1, keyword: this.visitSearch })
        if (!current()) return
        const fresh = d?.plans?.find(p => String(p.id) === String(plan.id))
        if (String(d?.batchId) !== batchId || !fresh) throw new Error('计划已变化')
        const students = [...plan.students, ...fresh.students.filter(s => !plan.students.some(old => old.internshipId === s.internshipId))]
        Object.assign(plan, fresh, { students })
      } catch (e) { if (current()) toast('本计划更多学生读取失败，请刷新核对') }
      finally { if (current()) plan.loadingStudents = false }
    },
    searchVisitTargets() {
      if (this.visitActing || this.visitPaging || this.visitTarget || this.hidden) return
      this.visitSearch = this.visitKeyword.trim(); this.loadVisits()
    },
    openVisitForm(s, plan) {
      if (this.hidden || this.visitActing || !s?.resolvable || s.visited || String(plan?.batchId) !== this.batchId || String(s.batchId) !== this.batchId) return
      if (this.visitTarget) return toast('请先保存或关闭当前巡访草稿')
      if (this.visitFollowDraft) return toast('请先保存或关闭当前整改跟进草稿')
      this.visitConflict = false
      this.visitTarget = {
        generation: currentSessionGeneration(), batchId: this.batchId, planId: String(plan.id), planDate: plan.planDate,
        expectedVersion: s.expectedVersion, expectedPlanVersion: s.expectedPlanVersion,
        internshipId: String(s.internshipId), name: s.name || '当前学生',
        enterpriseName: plan.enterpriseName || s.enterpriseName || ''
      }
    },
    closeVisitForm() { if (!this.visitActing) { this.visitOperation++; this.visitTarget = null; this.visitConflict = false } },
    adoptVisitContext(context) {
      if (this.visitActing || this.hidden || !this.visitTarget || context.target !== this.visitTarget) return
      Object.assign(this.visitTarget, { expectedVersion: context.expectedVersion, expectedPlanVersion: context.expectedPlanVersion })
      this.visitConflict = false
    },
    async submitVisit(body) {
      if (this.hidden || this.visitActing || this.visitConflict || !this.visitTarget) return
      const target = this.visitTarget, generation = currentSessionGeneration(), op = ++this.visitOperation
      const batchId = this.batchId
      const current = () => !this.hidden && generation === currentSessionGeneration() && op === this.visitOperation && batchId === this.batchId
      if (target.generation !== generation || body.batchId !== batchId || String(body.planId) !== target.planId ||
        body.expectedVersion !== target.expectedVersion || body.expectedPlanVersion !== target.expectedPlanVersion) return
      this.visitActing = true
      this.visitResultError = ''
      try {
        const saved = await teacherInternshipEvidenceV3Api.createVisit(target.internshipId, body)
        if (!current() || target !== this.visitTarget) return
        this.visitReceipt = { ...saved, name: target.name, batchId, internshipId: target.internshipId,
          generation, fileId: String(body.fileIds?.[0] || '') }
        this.visitTarget = null; this.visitDetail = null; this.visitFollowResult = ''; this.visitEpoch++
        await this.readVisitReceipt(this.visitReceipt, current)
      } catch (e) {
        if (!current()) return
        const error = normalizeError(e)
        this.visitConflict = error.kind === 'conflict' || e?.httpStatus === 409 || (e?.bizCode || e?.code) === 'DATA_CONFLICT'
        toast(this.visitConflict ? '计划或实习状态已变化，原输入已保留，请重读核对' : error.text)
      } finally { if (current()) this.visitActing = false }
    },
    async readVisitReceipt(receipt, current) {
      this.clearVisitLocation()
      try {
        const detail = await teacherInternshipEvidenceV3Api.visitDetail(String(receipt.visitId || ''))
        if (!current() || receipt !== this.visitReceipt) return
        if (String(detail?.id) !== String(receipt.visitId) || String(detail?.batchId) !== receipt.batchId ||
          String(detail?.internId) !== receipt.internshipId || (receipt.fileId && String(detail.attachment?.fileId) !== receipt.fileId)) throw new Error('登记结果上下文不一致')
        this.visitDetail = detail
        if (this.visitFollowDraft && this.visitFollowDraft.id === String(detail.id)) {
          if (this.visitFollowDraft.version !== detail.version) this.visitFollowDraft.conflict = true
          if (this.visitFollowDraft.conflict) this.visitFollowDraft.comparison = detail
        }
        const plans = await this.loadVisits()
        if (!current() || receipt !== this.visitReceipt) return
        this.visitResultError = plans ? '' : '巡访已登记，计划状态回读未完成；请重新读取，不要再次登记'
      } catch (e) {
        if (current() && receipt === this.visitReceipt) this.visitResultError = '巡访已登记，结果回读未完成；请重新读取，不要再次登记'
      }
    },
    async refreshVisitReceipt() {
      if (this.hidden || this.visitActing || !this.visitReceipt) return
      const receipt = this.visitReceipt, op = ++this.visitOperation
      const current = () => !this.hidden && op === this.visitOperation && receipt === this.visitReceipt &&
        receipt.batchId === this.batchId && receipt.generation === currentSessionGeneration()
      if (!current()) return
      if (this.visitFollowDraft?.id === String(receipt.visitId)) this.visitFollowDraft.comparison = null
      this.visitActing = true
      try { await this.readVisitReceipt(receipt, current) }
      finally { if (current()) this.visitActing = false }
    },
    async openVisitAttachment() {
      if (this.hidden || !this.visitDetail?.attachment?.fileId) return
      const detail = this.visitDetail, generation = currentSessionGeneration()
      try { await fileSdk.open(String(detail.attachment.fileId)) }
      catch (e) { if (!this.hidden && detail === this.visitDetail && generation === currentSessionGeneration()) toast('巡访照片打开未完成，请重试') }
    },
    clearVisitLocation() { this.visitLocationEpoch++; this.visitLocation = null; this.visitLocationBusy = false },
    async readVisitLocation() {
      const detail = this.visitDetail, batchId = this.batchId, generation = currentSessionGeneration()
      if (this.hidden || this.visitLocationBusy || !detail?.hasLocation || !detail.canViewLocation) return
      this.clearVisitLocation()
      const op = this.visitLocationEpoch
      const current = () => !this.hidden && op === this.visitLocationEpoch && detail === this.visitDetail &&
        batchId === this.batchId && generation === currentSessionGeneration()
      this.visitLocationBusy = true
      try {
        const data = await teacherInternshipEvidenceV3Api.visitLocation(detail.id, { batchId, expectedVersion: detail.version, reason: '核对本次巡访发生位置' })
        if (!current()) return
        if (String(data.visitId) !== String(detail.id) || String(data.batchId) !== batchId) throw new Error('巡访位置与当前记录不一致，请重新读取')
        this.visitLocation = data.location
      } catch (e) { if (current()) toast(normalizeError(e).text) }
      finally { if (current()) this.visitLocationBusy = false }
    },
    openRecordedVisit(student, plan) {
      if (this.hidden || this.visitActing || this.visitTarget || String(plan.batchId) !== this.batchId || !student.visitId) return
      if (this.visitFollowDraft) return toast('请先保存或关闭当前整改跟进草稿')
      this.focusVisitId = String(student.visitId)
      this.loadFocusedVisit({ batchId: this.batchId, internshipId: String(student.internshipId) })
    },
    async loadFocusedVisit(expected = {}) {
      this.clearVisitLocation()
      const epoch = ++this.readEpoch, generation = currentSessionGeneration(), id = this.focusVisitId
      const current = () => this.readIsCurrent(epoch, generation) && id === this.focusVisitId
      this.state = 'loading'; this.loadError = ''
      try {
        const detail = await teacherInternshipEvidenceV3Api.visitDetail(id)
        if (!current()) return
        if (String(detail?.id) !== id || !/^\d+$/.test(String(detail.batchId || ''))) throw new Error('巡访原单上下文不一致')
        if ((expected.batchId && String(detail.batchId) !== expected.batchId) ||
          (expected.internshipId && String(detail.internId) !== expected.internshipId)) throw new Error('巡访原单与所选学生不一致')
        this.routeBatchId = String(detail.batchId)
        await this.ensureBatchContext()
        if (!current()) return
        this.visitReceipt = { visitId: id, name: detail.studentName, batchId: this.batchId,
          internshipId: String(detail.internId), generation, fileId: String(detail.attachment?.fileId || '') }
        this.visitDetail = detail; this.visitFollowResult = ''; this.visitResultError = ''
        await Promise.allSettled([this.load(), this.loadVisits()])
      } catch (e) {
        if (current()) { this.state = 'error'; this.loadError = '原巡访暂无法读取，请核对权限后重试，不能打开其他对象代办' }
      }
    },
    beginVisitFollow() {
      if (this.hidden || this.visitActing || this.visitTarget || this.visitDetail?.rectifyStatus !== 'PENDING' ||
        this.visitReceipt?.generation !== currentSessionGeneration() || this.visitReceipt.batchId !== this.batchId ||
        String(this.visitDetail.id) !== String(this.visitReceipt.visitId) ||
        !Number.isInteger(this.visitDetail.version) || this.visitDetail.version < 0) return
      this.visitFollowDraft = { id: String(this.visitDetail.id), version: this.visitDetail.version, note: '', conflict: false, comparison: null }
    },
    adoptVisitFollow() {
      const draft = this.visitFollowDraft, fresh = draft?.comparison
      if (this.hidden || this.visitActing || !draft?.conflict || !fresh || String(fresh.id) !== draft.id ||
        this.visitReceipt?.generation !== currentSessionGeneration() ||
        String(fresh.batchId) !== this.batchId || String(fresh.internId) !== this.visitReceipt.internshipId ||
        !Number.isInteger(fresh.version) || fresh.version < 0 || fresh.rectifyStatus !== 'PENDING') return
      draft.version = fresh.version; draft.conflict = false; draft.comparison = null
    },
    async submitVisitFollow(status) {
      const draft = this.visitFollowDraft, receipt = this.visitReceipt
      if (this.hidden || this.visitActing || !draft || draft.conflict || !['PENDING', 'DONE'].includes(status) ||
        draft.note.trim().length < 2 || receipt?.generation !== currentSessionGeneration() || receipt.batchId !== this.batchId) return
      const op = ++this.visitOperation
      const current = () => !this.hidden && op === this.visitOperation && receipt === this.visitReceipt &&
        receipt.batchId === this.batchId && receipt.generation === currentSessionGeneration()
      this.visitActing = true; this.visitFollowResult = ''; this.visitResultError = ''
      try {
        const saved = await teacherInternshipEvidenceV3Api.rectifyVisit(draft.id, { batchId: receipt.batchId,
          expectedVersion: draft.version, status, note: draft.note.trim() })
        if (!current() || draft !== this.visitFollowDraft) return
        if (String(saved?.id) !== draft.id) throw new Error('整改回执对象不一致')
        this.visitFollowResult = saved.rectifyStatus === 'DONE' ? '本条巡访整改已完成，相关待办已办结' : '跟进说明已保存，仍需继续整改'
        this.visitFollowDraft = null
        await this.readVisitReceipt(receipt, current)
      } catch (e) {
        if (!current() || draft !== this.visitFollowDraft) return
        draft.conflict = normalizeError(e).kind === 'conflict' || e?.httpStatus === 409 || (e?.bizCode || e?.code) === 'DATA_CONFLICT'
        draft.comparison = null; toast('跟进未完成，原说明已保留，请核对后重试')
      } finally { if (current()) this.visitActing = false }
    },
    _actErr(e) {
      const normalized = normalizeError(e)
      if (normalized.kind === 'conflict' || (e && String(e.code).startsWith('409'))) {
        toast('对象已变化，连续处理已停止，原意见已保留，请核对最新事实')
        if (this.sequentialMode) this.sequentialConflict = true
        return { ...normalized, kind: 'conflict' }
      }
      toast(normalized.text)
      return normalized
    },
    review(w, type) {
      if (this.acting || this.state !== 'ready' || this.hidden) return
      if (w?._body !== 'ready') { toast('请先展开原单正文核对后批阅'); return }
      const epoch = this.readEpoch, generation = currentSessionGeneration(), batchId = this.batchId
      const key = `${batchId}:weekly:${w.id}`, draft = this.commandDrafts[key], version = w.expectedVersion
      if (draft && draft.version !== version) draft.conflicted = true
      if (draft?.conflicted) {
        if (draft.version === version) { toast('原意见和评分已保留，请刷新并重新打开最新正文'); return }
        uni.showModal({ title: '采用已核对的周报版本', content: `原第${draft.version}版，现第${version}版。确认保留原意见和评分继续？`, success: m => {
          if (!m.confirm || !this.readIsCurrent(epoch, generation) || batchId !== this.batchId) return
          draft.version = version; draft.conflicted = false; this.review(w, type)
        } }); return
      }
      const savedDraft = draft?.type === type ? draft : { type, comment: draft?.comment || '', ratingLevel: null, version, conflicted: false }
      this.commandDrafts[key] = savedDraft
      this.weeklyReviewError = ''
      this.weeklyReviewPanel = { row: w, draft: savedDraft, key, epoch, generation, batchId, version }
      // #ifdef H5
      this.weeklyReviewOpener = typeof document !== 'undefined' ? document.activeElement : null
      this.$nextTick?.(() => {
        const el = this.$refs.weeklyReviewSheet?.$el || this.$refs.weeklyReviewSheet
        el?.addEventListener?.('keydown', this.onWeeklyReviewKeydown)
        el?.querySelector?.('button, uni-button')?.focus?.()
      })
      // #endif
    },
    setWeeklyReviewType(type) {
      if (this.acting || !this.weeklyReviewPanel || !['pass', 'return'].includes(type)) return
      this.weeklyReviewPanel.draft.type = type; this.weeklyReviewError = ''
    },
    closeWeeklyReview() {
      if (this.acting) return
      const panel = this.weeklyReviewPanel, opener = this.weeklyReviewOpener
      this.weeklyReviewPanel = null; this.weeklyReviewError = ''
      this.$nextTick?.(() => { if (panel && this.readIsCurrent(panel.epoch, panel.generation) && panel.batchId === this.batchId) opener?.focus?.() })
    },
    onWeeklyReviewKeydown(event) {
      if (event.key === 'Escape') { event.preventDefault(); this.closeWeeklyReview(); return }
      if (event.key === 'Tab') {
        const el = this.$refs.weeklyReviewSheet?.$el || this.$refs.weeklyReviewSheet
        const controls = [...(el?.querySelectorAll?.('button, uni-button, input, textarea') || [])].filter(item => !item.hasAttribute('disabled') && item.getClientRects().length)
        const first = controls[0], last = controls[controls.length - 1]
        if (first && ((event.shiftKey && event.target === first) || (!event.shiftKey && event.target === last))) { event.preventDefault(); (event.shiftKey ? last : first).focus() }
      } else if (!this.acting && ['Enter', ' '].includes(event.key) && ['BUTTON', 'UNI-BUTTON'].includes(event.target?.tagName)) { event.preventDefault(); event.target.click() }
    },
    returnToTodos() { uni.navigateTo({ url: '/pages/teacher-internship/todos/index?group=REPORT' }) },
    async submitWeeklyReview() {
      const panel = this.weeklyReviewPanel
      if (!panel || this.acting || !this.readIsCurrent(panel.epoch, panel.generation) || panel.batchId !== this.batchId) return
      const { row: w, draft, key, epoch, generation, batchId, version } = panel
      if (w._body !== 'ready' || draft.conflicted || w.expectedVersion !== version) { this.weeklyReviewError = '原单已变化，请关闭后重新读取并核对正文。'; return }
      if (!/^\d+$/.test(String(w.id)) || !Number.isInteger(version) || version < 0) { this.weeklyReviewError = '周报编号或版本已失效，请重新读取。'; return }
      const type = draft.type, comment = draft.comment || '', ratingLevel = type === 'pass' ? draft.ratingLevel : null
      if (type === 'return' && comment.trim().length < 5) { this.weeklyReviewError = '退回需填写至少 5 字意见'; return }
      if (type === 'pass' && (!Number.isInteger(ratingLevel) || ratingLevel < 1 || ratingLevel > 5)) { this.weeklyReviewError = '请选择本次五级评价'; return }
      const oldIndex = this.sequentialIndex
      this.acting = true
      try {
        const res = await teacherApi.reviewWeekly(w.id, type === 'pass' ? 'APPROVE' : 'RETURN', comment, version, ratingLevel)
        if (!this.readIsCurrent(epoch, generation) || batchId !== this.batchId) return
        delete this.commandDrafts[key]
        w.status = res.status || (type === 'pass' ? 'APPROVED' : 'RETURNED'); w.feedback = comment
        if (res.ratingLevel) w.score = res.ratingLevel
        this.weeklyReviewPanel = null
        this.weeklyReceipt = { type, student: w.student, week: w.week, comment, ratingLevel }
        this.acting = false
        const data = await this.load()
        if (data && !this.hidden && generation === currentSessionGeneration() && this.batchId === batchId) this.afterSequentialSuccess(w.id, oldIndex)
      } catch (error) {
        if (!this.readIsCurrent(epoch, generation) || batchId !== this.batchId) return
        this.acting = false
        const normalized = this._actErr(error)
        this.weeklyReviewError = normalized.text || '批阅未完成，意见已保留，请重试。'
        if (normalized.kind === 'conflict') { draft.conflicted = true; this.weeklyReviewPanel = null; await this.load().catch(() => {}) }
      } finally {
        if (this.readIsCurrent(epoch, generation) && batchId === this.batchId) this.acting = false
      }
    },
    ck(c, type) {
      if (this.acting || this.state !== 'ready' || this.hidden) return
      const epoch = this.readEpoch, generation = currentSessionGeneration()
      if (!this.canDecideException(c)) { toast(this.decisionFactMessage(c)); return }
      const batchId = this.batchId, key = `${batchId}:abnormal:${c.id}`, draft = this.commandDrafts[key], version = c.expectedVersion
      if (draft?.conflicted) {
        if (draft.version === version) { toast('原处理意见已保留，请刷新并核对最新异常事实'); return }
        uni.showModal({ title: '采用已核对的异常版本', content: `原第${draft.version}版，现第${version}版。确认保留原意见继续？`, success: m => {
          if (!m.confirm || !this.readIsCurrent(epoch, generation) || batchId !== this.batchId || !this.canDecideException(c)) return
          draft.version = version; draft.conflicted = false; this.ck(c, type)
        } }); return
      }
      const isRisk = type === 'risk'
      const action = type === 'ok' ? 'REASONABLE' : isRisk ? 'TO_RISK' : 'ABNORMAL'
      const title = type === 'ok' ? '标记合理' : isRisk ? '转为高风险跟进' : '异常计入'
      uni.showModal({ title, editable: true, content: draft?.type === type ? draft.comment : '', placeholderText: isRisk ? '填写转风险原因（至少 5 字）' : '填写处理意见（至少 5 字）', success: (r) => {
        if (!r.confirm || this.acting || !this.readIsCurrent(epoch, generation)) return
        if (!r.content || r.content.trim().length < 5) { toast(isRisk ? '转风险原因至少 5 字' : '处理意见至少 5 字'); return }
        if (!/^\d+$/.test(String(c.id))) { toast('当前为离线数据，无法处理，请恢复网络后重试'); return }
        const oldIndex = this.sequentialIndex
        const savedDraft = { type, comment: r.content.trim(), version, conflicted: false }
        this.commandDrafts[key] = savedDraft
        this.acting = true
        const command = isRisk
          ? handleCheckinV3(c.id, action, r.content.trim(), 'HIGH')
          : teacherApi.handleCheckin(c.id, action, r.content.trim())
        command.then((res) => {
          if (!this.readIsCurrent(epoch, generation) || batchId !== this.batchId) return
          delete this.commandDrafts[key]
          c.status = res.status || 'COMPLETED'; toast(isRisk ? '已转高风险跟进' : (res.statusLabel || '已处理'))
          this.acting = false
          return this.load().then(() => this.afterSequentialSuccess(c.id, oldIndex))
        }).catch((e) => { if (!this.readIsCurrent(epoch, generation) || batchId !== this.batchId) return; const n = this._actErr(e); if (n.kind === 'conflict') { savedDraft.conflicted = true; this.acting = false; return this.load().catch(() => {}) } })
          .finally(() => { if (this.readIsCurrent(epoch, generation)) this.acting = false })
      } })
    }
  }
}
</script>

<style scoped>
.ir__quick{display:flex;gap:8px;padding-bottom:0}.ir__quick-btn{flex:1;margin:0;min-height:38px;border:1px solid var(--teacher-200,#bfdbfe);border-radius:8px;background:var(--teacher-50,#eff6ff);color:var(--teacher-700,#1d4ed8);font-size:13px}.ir__quick-btn::after{border:none}
.ir__batch{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding-top:var(--space-2);padding-bottom:0}.ir__batch-label{flex-shrink:0;font-size:var(--font-size-xs);color:var(--text-tertiary)}.ir__batch-choice{display:flex;align-items:center;gap:var(--space-2);max-width:260px;padding:7px 10px;border-radius:var(--radius-md);background:var(--teacher-50,#eff6ff);color:var(--teacher-700);font-size:var(--font-size-sm)}.ir__batch-choice text:first-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ir__batch-choice text:last-child{flex-shrink:0;font-size:var(--font-size-xs)}.ir__tabs{padding-bottom:var(--space-3)}.ir__page{display:flex;flex-direction:column;gap:var(--space-3)}.ir__summary{display:flex;align-items:stretch;gap:var(--space-3);padding:var(--space-3)}.ir__summary-main{flex:1;min-width:0}.ir__summary-label{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary)}.ir__summary-value{display:flex;align-items:baseline;gap:4px;margin-top:4px}.ir__summary-value text:first-child{font-size:34px;line-height:1;font-weight:700;color:var(--teacher-700)}.ir__summary-value text:last-child{font-size:var(--font-size-sm);color:var(--text-secondary)}.ir__summary-note{display:block;margin-top:8px;font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.ir__summary-metrics{width:50%;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));background:var(--gray-50);border-radius:var(--radius-md);overflow:hidden}.ir__metric{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;padding:10px 3px;border-left:1px solid var(--border-light);text-align:center}.ir__metric:first-child{border-left:0}.ir__metric text:first-child{font-size:var(--font-size-lg);font-weight:700;color:var(--text-primary)}.ir__metric.is-danger text:first-child{color:var(--danger-600)}.ir__metric.is-warning text:first-child{color:var(--warning-700)}.ir__metric.is-success text:first-child{color:var(--success-700)}.ir__metric text:last-child{font-size:10px;line-height:1.25;color:var(--text-tertiary)}.ir{display:flex;flex-direction:column;gap:var(--space-3);padding:var(--space-3)}.ir.is-risk{border-left:4px solid var(--warning-500)}.ir__head{align-items:flex-start}.ir__identity{min-width:0}.ir__week{font-size:var(--font-size-xs);color:var(--teacher-700);background:var(--teacher-50);padding:2px 8px;border-radius:var(--radius-full)}.ir__company{display:block;font-size:var(--font-size-sm);color:var(--text-secondary);margin-top:3px;word-break:break-word}.ir__meta{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;padding:var(--space-2);background:var(--gray-50);border-radius:var(--radius-md)}.ir__meta>view{min-width:0;display:flex;flex-direction:column;gap:3px}.ir__meta text:first-child{font-size:10px;color:var(--text-tertiary)}.ir__meta text:last-child{font-size:var(--font-size-xs);font-weight:600;color:var(--text-primary);word-break:break-word}.ir__meta>view.is-danger text:last-child{color:var(--danger-600)}.ir__body{padding:var(--space-2) var(--space-3);border:1px solid var(--border-light);border-radius:var(--radius-md)}.ir__section+.ir__section{margin-top:var(--space-3);padding-top:var(--space-3);border-top:1px dashed var(--border-light)}.ir__bodybtn{text-align:center;padding:10px;border:1px solid var(--teacher-200,#bfdbfe);border-radius:var(--radius-md);background:var(--teacher-50,#eff6ff)}.ir__bodybtn text{font-size:var(--font-size-sm);color:var(--teacher-700)}.ir__attachment{display:flex;align-items:center;gap:8px;padding:8px 10px;border:1px solid var(--border-light);border-radius:var(--radius-md);margin-top:6px}.ir__attachment-open{flex-shrink:0;font-size:var(--font-size-xs);color:var(--teacher-700)}.ir__bodyhint{font-size:var(--font-size-sm);color:var(--text-tertiary);text-align:center;padding:var(--space-3) 0}.ir__bodyhint.is-link{color:var(--danger-600)}.ir__label{font-size:var(--font-size-xs);font-weight:600;color:var(--text-tertiary)}.ir__text{display:block;font-size:var(--font-size-base);color:var(--text-primary);margin-top:4px;line-height:1.65;white-space:pre-wrap;word-break:break-word}.ir__text.is-danger{color:var(--danger-600)}.ir__ck{background:var(--gray-50);border-radius:var(--radius-md);padding:var(--space-2) var(--space-3)}.ir__ck-row{display:flex;gap:var(--space-3);padding:5px 0}.ir__ck-row .ir__label{width:62px;flex-shrink:0}.ir__feedback{background:var(--success-50);border-radius:var(--radius-md);padding:var(--space-2) var(--space-3)}.ir__feedback-label{font-size:var(--font-size-xs);font-weight:600;color:var(--success-700)}.ir__feedback-text{display:block;font-size:var(--font-size-sm);color:var(--text-primary);margin-top:4px;line-height:1.55;word-break:break-word}.ir__score{display:inline-block;margin-top:5px;font-size:var(--font-size-xs);color:var(--success-700)}.ir__next{display:flex;gap:10px;padding:10px 12px;border-radius:var(--radius-md);background:var(--teacher-50,#eff6ff)}.ir__next.is-warning{background:var(--warning-50,#fff7ed)}.ir__next-label{flex-shrink:0;font-size:var(--font-size-xs);font-weight:600;color:var(--text-secondary)}.ir__next-text{font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.ir__actions{display:flex;gap:var(--space-2)}.ir__actions.is-three button{font-size:var(--font-size-sm);padding-left:4px;padding-right:4px}.ir__pass{min-height:var(--touch-target-min);border-radius:var(--radius-md);border:none;background:var(--teacher-600);color:#fff;font-size:var(--font-size-md)}.ir__pass::after{border:none}.ir__risk{min-height:var(--touch-target-min);border-radius:var(--radius-md);border:1px solid var(--danger-500);background:var(--bg-card);color:var(--danger-600);font-size:var(--font-size-md)}.ir__risk::after{border:none}.ir__done-text{text-align:center;color:var(--text-tertiary);font-size:var(--font-size-sm);line-height:var(--touch-target-min)}.ir__paging{text-align:center;padding:var(--space-3) 0;font-size:var(--font-size-sm);color:var(--teacher-700)}.ir__paging.is-end{color:var(--text-tertiary)}.ir__visit-summary{display:flex;justify-content:space-between;gap:12px;padding:var(--space-2) var(--space-3);border-radius:var(--radius-md);background:var(--gray-50);font-size:var(--font-size-xs);color:var(--text-secondary)}.ir__visit-students{border-top:1px solid var(--border-light);padding-top:var(--space-2)}.ir__visit-row{display:flex;align-items:center;gap:var(--space-2);padding:var(--space-2) 0;border-bottom:1px solid var(--border-light)}.ir__visit-row:last-child{border-bottom:0}.ir__visit-copy{min-width:0}.ir__visit-copy>text:last-child{display:block;margin-top:2px;font-size:10px;color:var(--text-tertiary)}.ir__visit-done{font-size:var(--font-size-sm);color:var(--success-600)}.ir__visit-btn{font-size:var(--font-size-sm);color:#fff;background:var(--teacher-600);border:none;border-radius:var(--radius-md);padding:7px 14px;flex-shrink:0}.ir__visit-btn[disabled]{background:var(--gray-300);color:var(--text-tertiary)}.ir__queue-bar{display:flex;align-items:center;justify-content:space-between;gap:var(--space-2)}.ir__queue-note{font-size:var(--font-size-sm);color:var(--text-secondary)}.ir__queue-toggle{font-size:var(--font-size-sm);color:var(--teacher-700);flex-shrink:0}.ir__queue-item{padding:0}@media(max-width:360px){.ir__batch{align-items:flex-start;flex-direction:column;gap:5px}.ir__batch-choice{max-width:100%}.ir__summary{flex-direction:column}.ir__summary-metrics{width:100%}.ir__meta{grid-template-columns:1fr}.ir__ck-row{flex-direction:column;gap:3px}.ir__ck-row .ir__label{width:auto}.ir__actions.is-three{flex-direction:column}}
.ir__paging{width:100%;border:0;background:transparent}.ir__paging::after{border:0}.ir__queue-toggle{margin:0;padding:0;border:0;background:transparent;line-height:var(--touch-target-min)}.ir__queue-toggle::after{border:0}
.ir__follow-note{box-sizing:border-box;width:100%;min-height:140px;padding:10px 12px;border:1px solid var(--border-base);border-radius:var(--radius-md);background:var(--bg-card);font-size:var(--font-size-base);line-height:1.55;color:var(--text-primary)}
.teacher-process :deep(.page-pad){width:100%;max-width:760px;margin-left:auto;margin-right:auto;box-sizing:border-box}.teacher-process .card{border-radius:8px;box-shadow:none}.teacher-process button,.teacher-process input{min-height:44px;font-size:15px}.ir__batch-label,.ir__batch-choice,.ir__quick-btn,.ir__summary-label,.ir__summary-note,.ir__metric text:last-child,.ir__week,.ir__meta text,.ir__label,.ir__feedback-label,.ir__feedback-text,.ir__next-label,.ir__next-text,.ir__attachment-open,.ir__visit-summary,.ir__visit-copy>text:last-child,.ir__queue-note{font-size:14px;line-height:22px}.ir__summary{flex-wrap:wrap}.ir__summary-main{flex-basis:100%}.ir__summary-metrics{width:100%}.ir__meta{grid-template-columns:repeat(2,minmax(0,1fr))}.ir__batch-choice{min-height:44px;display:flex;align-items:center}.ir__visit-row{flex-wrap:wrap}.ir__quick{flex-wrap:wrap}.ir__quick-btn{min-height:44px}.ir__summary-value text:first-child{font-size:28px}
</style>
