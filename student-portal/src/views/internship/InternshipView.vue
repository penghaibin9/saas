<template>
  <div class="sp-page" :class="'view-' + tab">
    <p v-if="tab==='overview' && overviewLoading" role="status">正在核对最新办理进度…</p>
    <div v-if="tab==='overview' && overviewError" role="alert" class="sp-source-state sp-source-state--error">{{ overviewError }}<button type="button" class="sp-btn sp-btn--ghost" @click="refreshProgress">重新读取进度</button></div>
    <div v-if="!loading && !error && my.hasData && tab !== 'overview'" class="sp-contextbar"><span>当前实习批次 <strong>{{ my.batchName || '批次名称待核对' }}</strong></span><StatusTag :text="statusText(my.status)" /><button type="button" class="sp-link" @click="selectTab('overview')">查看实习安排</button></div>
    <section v-if="!loading && !error && my.hasData && tab === 'overview'" class="sp-card sp-now" aria-labelledby="sp-now-title">
      <div class="sp-now__copy">
        <span class="sp-now__eyebrow">当前实习事项</span>
        <h2 id="sp-now-title">{{ currentAction.title }}</h2>
        <p>{{ currentAction.reason }}</p>
        <div class="sp-now__meta">
          <span>最近变化：{{ currentAction.recentChange }}</span>
          <span>完成后：{{ currentAction.nextActor }}</span>
        </div>
      </div>
      <button v-if="currentAction.tab !== tab" type="button" class="sp-btn" @click="selectTab(currentAction.tab)">{{ currentAction.action }} →</button>
    </section>

    <nav class="sp-process-nav" aria-label="实习办理分组">
      <details v-for="group in tabGroups" :key="group.key" class="sp-process-group" :open="groupOpen(group)">
        <summary><span><b>{{ group.label }}</b></span><span class="sp-process-group__current">{{ activeGroupLabel(group) }}</span></summary>
        <div class="sp-process-group__items">
          <button v-for="item in group.tabs" :key="item.key" type="button" :class="{ 'is-active': tab === item.key }"
            :aria-current="tab === item.key ? 'page' : undefined" @click="selectTab(item.key)">{{ item.label }}</button>
        </div>
      </details>
    </nav>

    <StateBlock v-if="loading" type="loading" text="正在加载实习信息…" />
    <StateBlock v-else-if="error" type="error" :text="error" />
    <template v-else>
      <section v-if="my.hasData && currentSource.status === 'loading'" class="sp-source-state" aria-live="polite">
        <StateBlock type="loading" :text="`${currentSource.label}正在加载…`" />
      </section>
      <section v-else-if="my.hasData && currentSource.status === 'error'" class="sp-source-state sp-source-state--error" aria-live="assertive">
        <StateBlock type="error" :text="currentSource.message" />
        <button class="sp-btn sp-btn--ghost" type="button" @click="retryCurrentSource">重试当前内容</button>
      </section>

      <section v-if="my.needSelect && internshipCandidates.length" class="sp-card" style="margin-bottom:16px">
        <div class="sp-panel__head">请选择要办理的实习批次</div>
        <p class="sp-muted" style="margin-bottom:12px">你有多条进行中的实习记录。系统不会替你猜测；选择后，本页后续查询与办理都会固定使用同一批次。</p>
        <div style="display:flex;flex-direction:column;gap:10px">
          <button v-for="candidate in internshipCandidates" :key="candidate.recordId" type="button" class="sp-btn sp-btn--ghost" style="display:flex;justify-content:space-between;align-items:center;text-align:left" @click="selectInternshipBatch(candidate.batchId)">
            <span><strong>{{ candidate.batchName || `批次 ${candidate.batchId}` }}</strong><small style="display:block;margin-top:4px">状态 {{ statusText(candidate.status) }} · 记录 {{ candidate.recordId }}</small></span>
            <span>选择 ›</span>
          </button>
        </div>
      </section>

      <section v-else-if="!my.hasData" class="sp-notice" style="border-color:#FFD591;background:#FFFBE6">
        <div><strong style="color:#613400">暂无实习记录</strong><p class="sp-muted" style="margin:6px 0 0;color:#8b5c00">{{ my.message || '你尚未被纳入实习安排，建档后此处会显示企业、岗位与周月报待办。' }}</p></div>
      </section>

      <!-- 通知公告 SP01 -->
      <template v-else-if="tab === 'notices'">
        <section class="sp-card">
          <div class="sp-panel__head">通知公告 <span class="sp-muted">当前批次 {{ notices.length }} 条</span></div>
          <p class="sp-muted" style="margin:-4px 0 14px">学校或院系发布的岗位实习通知；附件统一走文件安全授权，不拼接原始存储地址。</p>
          <StateBlock v-if="!notices.length" type="empty" text="当前批次暂无有效通知公告" />
          <div v-else style="display:flex;flex-direction:column;gap:12px">
            <article v-for="item in notices" :key="item.id" style="padding:14px;border:1px solid var(--line);border-radius:12px;background:var(--bg2)">
              <div style="display:flex;justify-content:space-between;gap:16px;align-items:flex-start">
                <div style="min-width:0">
                  <strong style="display:block;font-size:15px">{{ item.title }}</strong>
                  <span class="sp-muted">{{ noticeTypeText(item.noticeType) }} · {{ item.senderName || '学校' }} · {{ fmt(item.publishedAt) }}</span>
                  <span v-if="item.schoolCategory" class="sp-muted"> · 学校分类：{{ item.schoolCategory }}</span>
                </div>
                <StatusTag :text="noticeUrgencyText(item.urgency)" :tone="item.urgency === 'URGENT' ? 'danger' : item.urgency === 'IMPORTANT' ? 'warn' : 'primary'" />
              </div>
              <p style="margin:12px 0 0;line-height:1.75;white-space:pre-wrap;word-break:break-word">{{ item.content }}</p>
              <p v-if="item.validFrom || item.validUntil" class="sp-muted" style="margin:8px 0 0">有效期：{{ noticeDate(item.validFrom) }} 至 {{ noticeDate(item.validUntil) }}</p>
              <div v-if="item.attachments?.length" style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px">
                <button v-for="file in item.attachments" :key="file.fileId" type="button" class="sp-btn sp-btn--ghost sp-btn--sm" @click="openNoticeAttachment(file)">
                  {{ file.fileName || '通知附件' }}
                </button>
              </div>
            </article>
          </div>
        </section>
      </template>

      <InternshipConsentPanel v-else-if="tab === 'consent'" :context="my" />

      <!-- 我的实习 -->
      <template v-else-if="tab === 'overview'">
        <section v-if="internshipCandidates.length > 1" class="sp-card" style="margin-bottom:16px">
          <div class="sp-fieldlabel">当前实习批次</div>
          <select v-model="selectedBatchId" class="sp-inp" @change="changeInternshipBatch">
            <option v-for="candidate in internshipCandidates" :key="candidate.recordId" :value="String(candidate.batchId)">
              {{ candidate.batchName || `批次 ${candidate.batchId}` }} · {{ statusText(candidate.status) }}
            </option>
          </select>
        </section>
        <div class="sp-preparation">
          <section class="sp-card sp-preparation__main">
            <div class="sp-preparation__head"><div><span class="sp-preparation__eyebrow">我的实习安排</span><h2>{{ my.batchName || '当前实习批次' }}</h2></div><StatusTag :text="statusText(my.status)" :tone="my.historyMode ? 'neutral' : 'info'" /></div>
            <dl class="sp-preparation__facts">
              <div><dt>实习岗位</dt><dd>{{ my.positionName || '待落实岗位' }}</dd></div><div><dt>实习企业</dt><dd>{{ my.enterpriseName || '待落实企业' }}</dd></div>
              <div><dt>校内指导教师</dt><dd>{{ my.advisorName || '学校待分配' }}</dd></div><div><dt>企业导师</dt><dd>{{ my.enterpriseMentor || '待落实' }}</dd></div>
            </dl>
            <FlowSteps :steps="flowSteps" />
          </section>
          <aside class="sp-card sp-qualification" aria-labelledby="sp-qualification-title">
            <span class="sp-preparation__eyebrow">学校资格认定</span>
            <div class="sp-qualification__title"><h2 id="sp-qualification-title">实习资格</h2><StatusTag :text="qualification.label" :tone="qualification.status === 'QUALIFIED' ? 'success' : qualification.status === 'UNQUALIFIED' ? 'danger' : 'warn'" /></div>
            <p>{{ qualification.reason || qualificationHint }}</p>
            <span v-if="qualification.reviewedAt" class="sp-muted">更新于 {{ fmt(qualification.reviewedAt) }}</span>
            <div class="sp-qualification__next"><strong>下一步</strong><p>{{ !['PREPARING','READY'].includes(my.status) ? '按当前实习安排继续办理；资格资料需核对时，请联系学校。' : qualification.status === 'QUALIFIED' ? '继续落实实习岗位，按学校要求完成上岗准备。' : '关注学校认定结果；如需补充材料，请联系校内指导教师。' }}</p></div>
            <button type="button" class="sp-btn sp-btn--ghost" @click="load">刷新认定结果</button>
          </aside>
        </div>
        <section class="sp-card sp-completion" :class="{'is-current':['ASSESSING','ARCHIVED','ENDED'].includes(my.status)}">
          <div>
            <span class="sp-preparation__eyebrow">结项与归档</span>
            <h2>{{ my.status === 'ARCHIVED' ? '实习结果已归档' : my.score ? '正式成绩已发布' : ['ASSESSING','ENDED'].includes(my.status) ? '实习进入结项考核' : '结项进度' }}</h2>
            <p class="sp-muted">{{ my.status === 'ARCHIVED' ? '实习档案已形成历史记录；正式成绩、鉴定与归档材料均在本系统留存，可继续查看。' : my.score ? '学校已发布正式成绩，可查看总分、分项与鉴定；归档由学校继续办理。' : ['ASSESSING','ENDED'].includes(my.status) ? '请完成实习总结、自评和评价，等待学校核算并发布正式成绩。' : '可提前查看结项要求；正式成绩与归档结果将在完成实习考核后显示。' }}</p>
          </div>
          <div class="sp-completion__actions">
            <button type="button" class="sp-btn sp-btn--ghost" @click="selectTab('eval')">查看鉴定与成绩</button>
            <button type="button" class="sp-btn" @click="router.push('/employment')">进入就业中心</button>
          </div>
        </section>
        <details class="sp-card"><summary>手机上继续办理的事项</summary><p>月度工资单、就业上报和免签申请请打开学生移动端，在首页选择同一实习批次后进入“轮岗与工资”“就业上报”或“实习打卡”。已提交的原单和教师审核结果保存在同一平台，无需在电脑重复提交。</p><p>学校要求的实习材料可从电脑端或学生移动端“实习材料”提交；招聘季的实践与证明材料也可从电脑端“实习档案”继续维护。</p></details>
        <section v-if="!['PREPARING', 'READY'].includes(my.status)" class="sp-card sp-home-attendance">
          <div class="sp-panel__head">首页考勤状态 <button type="button" class="sp-link" @click="selectTab('checkin')">查看全部</button></div>
          <div class="sp-home-attendance__grid">
            <div><span>已签到</span><strong>{{ attendance.summary?.CHECKIN || 0 }}</strong></div>
            <div><span>未签到</span><strong>{{ attendance.summary?.ABSENT || 0 }}</strong></div>
            <div><span>请假</span><strong>{{ attendance.summary?.LEAVE || 0 }}</strong></div>
            <div><span>补签</span><strong>{{ attendance.summary?.MAKEUP || 0 }}</strong></div>
            <div><span>免签</span><strong>{{ attendance.summary?.EXEMPT || 0 }}</strong></div>
          </div>
        </section>
        <section v-if="!['PREPARING', 'READY'].includes(my.status)" class="sp-card sp-report-progress">
          <div class="sp-panel__head">报告提交进度 <button type="button" class="sp-link" @click="selectTab('report')">查看报告</button></div>
          <div class="sp-report-progress__grid">
            <div v-for="item in reportProgress" :key="item.key" class="sp-report-progress__item">
              <div class="sp-report-progress__row">
                <strong>{{ item.label }}</strong>
                <span>{{ item.submitted == null ? '正在读取篇数' : item.required > 0 ? item.submitted + '/' + item.required : item.submitted + ' 篇 · 应交数未配置' }}</span>
              </div>
              <div v-if="item.rate != null" class="sp-report-progress__track">
                <span :style="{ width: (item.rate == null ? 0 : item.rate) + '%' }"></span>
              </div>
            </div>
          </div>
          <p v-if="reportProgress.some((item) => item.required === 0)" class="sp-muted" style="margin:10px 0 0">应交篇数未配置的类型不计算完成率，避免把“已交过”误当成“已完成”。</p>
        </section>
        <div v-if="!['PREPARING', 'READY'].includes(my.status)" class="m4">
          <div v-for="m in metrics" :key="m.t" class="sp-metric"><div class="sp-metric__label">{{ m.t }}</div><div class="sp-metric__value" :style="{color:m.c}">{{ m.v }}<small>{{ m.u }}</small></div></div>
        </div>
      </template>

      <!-- 三方协议 -->
      <template v-else-if="tab === 'agreement'">
        <div class="two">
          <section class="sp-card" aria-live="polite">
            <div class="sp-panel__head">实习三方协议 <StatusTag :text="agreementStatusText" :tone="agreementTone" /></div>
            <p v-if="my.historyMode" class="sp-muted">历史实习协议仅供阅读和下载打印件，不能提交确认或原因。</p>
            <div v-if="agreementReceipt" class="agreement-receipt" role="status"><strong>{{ agreementReceipt.text }}</strong><p>{{ agreementReceipt.readback ? agreementNextStep(agreementDetail?.status) : '办理已提交，最新结果暂未读回；请重新打开协议核对，不必重复提交。' }}</p><p v-if="agreementReceipt.reason">已提交原因：{{ agreementReceipt.reason }}</p></div>
            <StateBlock v-if="agreementReading" type="loading" text="正在读取学校保存的协议正文…" />
            <template v-else-if="agreementDetail">
              <p class="sp-muted">协议 {{ agreementDetail.id }} · 第{{ agreementDetail.version }}版 · {{ agreementDetail.templateName || '三方协议' }}</p>
              <p class="sp-muted">企业：{{ agreementDetail.enterpriseName || '待核实' }} · 岗位：{{ agreementDetail.positionName || '待核实' }}</p>
              <article v-if="agreementDetail.renderedBody" class="agreement" aria-label="学校保存的协议正文">{{ agreementDetail.renderedBody }}</article>
              <p v-else class="agreement-error">学校尚未生成协议正文，请联系指导教师核实。</p>
              <p v-if="agreementDetail.rejectReason" class="sp-muted">已提交原因：{{ agreementDetail.rejectReason }}</p>
              <template v-if="agreementDetail.status === 'PENDING_STUDENT' && !my.historyMode">
                <label class="agreement-reason">无法确认原因<textarea v-model="agreementReason" class="sp-inp" rows="3" maxlength="500" :disabled="agreementBusy" placeholder="如无法确认，请填写具体原因（至少5个字）" /></label>
                <div class="agreement-actions"><button type="button" class="sp-btn" :disabled="!agreementCanAct" @click="confirmAgreement('CONFIRM')">已阅读并确认协议</button><button type="button" class="sp-btn sp-btn--ghost" :disabled="!agreementCanAct" @click="confirmAgreement('REJECT')">提交无法确认原因</button></div>
              </template>
              <p v-else class="sp-muted">{{ agreementNextStep(agreementDetail.status) }}</p>
              <button type="button" class="sp-btn sp-btn--ghost" :disabled="!agreementCanPrint" @click="printAgreement">下载协议打印件</button>
            </template>
            <StateBlock v-else type="empty" :text="activeAgreement ? '请选择协议，打开学校正文后办理。' : '暂无三方协议，请等待学校生成并下发。'" />
            <p v-if="agreementError" class="agreement-error" role="alert">{{ agreementError }}</p>
            <button v-if="activeAgreement && !agreementReading && (!agreementDetail || agreementConflict || agreementReceipt?.readback === false)" type="button" class="sp-btn sp-btn--ghost" :disabled="agreementBusy || busy" @click="openAgreement(activeAgreement)">重新打开正文核对</button>
            <p class="sp-muted" style="margin-top:10px">企业纸质签署材料由学校登记；学生确认后，可在同一协议查看后续办理结果。</p>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">协议列表 <button type="button" class="sp-btn sp-btn--ghost sp-btn--sm" :disabled="agreementBusy || busy || agreementReading" @click="loadTab('agreement', true)">刷新协议</button></div>
            <p v-if="!agreements.length" class="sp-muted">当前批次暂无协议。</p>
            <div v-else class="agreement-list"><button v-for="item in agreements" :key="item.id" type="button" class="agreement-item" :aria-pressed="activeAgreement?.id === item.id" :disabled="agreementBusy || busy" @click="openAgreement(item)"><span><strong>{{ item.enterpriseName || '企业待核实' }}</strong><small>{{ item.positionName || '岗位待核实' }} · 协议 {{ item.id }}</small></span><StatusTag :text="agreementLabel(item.status)" :tone="item.status === 'EFFECTIVE' ? 'success' : 'warn'" /></button></div>
          </section>
        </div>
      </template>

      <!-- 签到考勤统计 SP03 -->
      <template v-else-if="tab === 'checkin'">
        <div class="two">
          <section class="sp-card">
            <div class="sp-panel__head">签到考勤概览 <button type="button" class="sp-link" :disabled="busy" @click="downloadAttendancePdf">下载考勤打印件</button></div>
            <div class="sp-attendance-overview">
              <div class="sp-attendance-ring" :style="attendanceChartStyle"><div><strong>{{ attendance.totalCountedDays || 0 }}</strong><span>已统计天数</span></div></div>
              <div class="sp-attendance-legend">
                <div><span class="dot checkin"></span><b>已签到</b><strong>{{ attendance.summary?.CHECKIN || 0 }}</strong></div>
                <div><span class="dot absent"></span><b>未签到</b><strong>{{ attendance.summary?.ABSENT || 0 }}</strong></div>
                <div><span class="dot leave"></span><b>请假</b><strong>{{ attendance.summary?.LEAVE || 0 }}</strong></div>
                <div><span class="dot makeup"></span><b>补签</b><strong>{{ attendance.summary?.MAKEUP || 0 }}</strong></div>
                <div><span class="dot exempt"></span><b>免签</b><strong>{{ attendance.summary?.EXEMPT || 0 }}</strong></div>
              </div>
            </div>
            <p class="sp-muted">统计区间 {{ attendance.internshipStartDate || '—' }} 至 {{ attendance.throughDate || '—' }}；未来日期不计入未签到。</p>
            <div class="notebox">电脑端无定位登记先保留打卡时间；核实并完成补卡审核后才计入有效出勤。需要定位、水印照片和围栏核验时请使用学生移动端。</div>
            <button class="sp-btn" style="margin-top:12px" :disabled="busy || my.todayCheckin?.done" @click="doCheckin">{{ my.todayCheckin?.done ? '今日已打卡' : '登记今日打卡' }}</button>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">全部签到考勤记录 <span class="sp-muted">{{ attendance.items?.length || 0 }} 条</span></div>
            <StateBlock v-if="!(attendance.items||[]).length" type="empty" text="当前统计区间暂无考勤记录" />
            <div v-else class="sp-attendance-list">
              <div v-for="row in attendance.items" :key="row.date" class="sp-attendance-row">
                <div><strong>{{ row.date }}</strong><span>{{ row.time ? fmt(row.time) : (row.address || '—') }}</span></div>
                <StatusTag :text="attendanceStatusText(row.status)" :tone="row.status==='CHECKIN'||row.status==='MAKEUP'||row.status==='EXEMPT'?'success':row.status==='ABSENT'||row.status==='PENDING'?'danger':'warn'" />
              </div>
            </div>
          </section>
        </div>
      </template>

      <!-- 实习请假 -->
      <template v-else-if="tab === 'leave'">
        <div v-if="leaveReceipt" class="makeup-receipt" role="status">
          <strong>{{ leaveReceipt.actionLabel }}</strong>
          <span>记录编号 {{ leaveReceipt.id }} · {{ leaveReceipt.statusLabel }} · 第{{ leaveReceipt.version }}版</span>
          <span>{{ leaveReceipt.nextStep }}</span>
        </div>
        <p v-if="leaveError" class="makeup-error" role="alert">{{ leaveError }}</p>
        <p v-if="!leaveWritable" class="sp-muted">当前记录仅供查看；在岗或考核阶段且请假记录读取成功后才能办理。</p>
        <div class="two">
          <section class="sp-card">
            <div class="sp-panel__head">{{ leaveBase ? `原请假单 ${leaveBase.id} · 补正重交` : '发起请假' }}</div>
            <p v-if="leaveBase" class="makeup-review-note">原第{{ leaveBase.version }}版 · 退回原因：{{ leaveBase.reviewComment || '请核对原单审批意见' }}</p>
            <p class="sp-muted leave-lead">填写请假时间和真实事由。病假或连续3天及以上必须上传证明，提交后按学校配置逐级审批。</p>
            <fieldset :disabled="busy || leaveReading || !leaveWritable" style="border:0;margin:0;padding:0;min-width:0">
            <div class="sp-fieldlabel">请假类型</div>
            <select v-model="leaveForm.leaveType" class="sp-inp" style="margin-bottom:12px">
              <option value="SICK">病假</option>
              <option value="PERSONAL">事假</option>
              <option value="OTHER">其他</option>
            </select>
            <div class="sp-fieldlabel">开始日期</div>
            <AppDatePicker v-model="leaveForm.startDate" class="sp-inp" style="margin-bottom:12px" role="start" :end-value="leaveForm.endDate" label="开始日期" />
            <div class="sp-fieldlabel">结束日期</div>
            <AppDatePicker v-model="leaveForm.endDate" class="sp-inp" style="margin-bottom:12px" role="end" :start-value="leaveForm.startDate" label="结束日期" />
            <div class="sp-fieldlabel">事由</div>
            <textarea v-model.trim="leaveForm.reason" class="sp-inp" style="margin-bottom:12px" maxlength="500" placeholder="如：发热就医，已上传门诊证明" />
            <div class="sp-fieldlabel">证明材料 {{ leaveEvidenceRequired ? '（必需）' : '（选传）' }}</div>
            <input type="file" class="sp-inp" style="margin-bottom:6px" :disabled="busy" @change="uploadLeaveEvidence" />
            <p class="sp-muted" style="margin-bottom:12px">{{ leaveForm.fileName || leaveEvidenceHint }}</p>
            <p v-if="leaveFile" class="sp-muted">{{ leaveFile.statusText || (leaveFile.readyForBusiness ? '安全可用' : '文件状态待核对') }} <button v-if="!leaveFile.readyForBusiness" class="sp-btn sp-btn--ghost" @click="refreshLeaveEvidence">读取安全检查结果</button></p>
            <button class="sp-btn" :disabled="busy || leaveReading || !leaveCanSubmit" @click="submitLeave">{{ busy ? '提交中…' : leaveBase ? '原单补正重交' : '提交请假' }}</button>
            <button v-if="leaveHasDraft || leaveConflict" class="sp-btn sp-btn--ghost" :disabled="busy" @click="cancelLeaveEdit">取消填写，清除本次草稿</button>
            </fieldset>
            <div v-if="leaveConflict" class="makeup-review-note" role="alert">
              <p>输入、证明及原版本已保留。先读取当前记录，再确认是否继续办理。</p>
              <button class="sp-btn sp-btn--ghost" :disabled="busy || leaveReading" @click="rereadLeave">读取当前记录核对</button>
              <button class="sp-btn" :disabled="busy || !leaveConflictRead || (leaveBase ? !['REJECTED', 'NEEDS_REVISION'].includes(leaveDetail?.status) : leaves.some(item => item.status === 'PENDING'))" @click="continueLeaveAfterConflict">已核对，继续办理</button>
            </div>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">我的请假与返岗</div>
            <StateBlock v-if="sourceStates.leave.status === 'empty'" type="empty" text="暂无请假记录" />
            <div v-else-if="sourceStates.leave.status === 'data'" style="display:flex;flex-direction:column;gap:10px">
              <div v-for="lv in leaves" :key="lv.id" class="repitem" style="flex-direction:column;align-items:stretch;gap:6px">
                <div style="display:flex;align-items:center;justify-content:space-between;gap:8px">
                  <div>
                    <div style="font-size:13.5px;color:var(--t1)">{{ leaveTypeText(lv.leaveType) }} · {{ lv.startDate }} ~ {{ lv.endDate }}</div>
                    <div style="font-size:12px;color:var(--t4);margin-top:2px">{{ lv.reason }}</div>
                  </div>
                  <StatusTag :text="internshipLeaveStage(lv).label" :tone="internshipLeaveStage(lv).tone" />
                </div>
                <div style="display:flex;gap:8px">
                  <span class="sp-muted">{{ internshipLeaveStage(lv).next }}</span>
                  <button class="sp-btn sp-btn--ghost" :disabled="busy || leaveReading" @click="openLeave(lv)">查看原单与历次提交</button>
                  <button v-if="['REJECTED', 'NEEDS_REVISION'].includes(lv.status)" class="sp-btn" :disabled="busy || leaveReading || !leaveWritable || leaveConflict" @click="editLeave(lv)">原单补正重交</button>
                  <button v-if="lv.status==='PENDING'" class="sp-btn sp-btn--ghost" style="align-self:flex-start" :disabled="busy || !leaveWritable" @click="withdrawLeave(lv)">撤回</button>
                  <button v-if="['APPROVED','OVERDUE'].includes(lv.status)" class="sp-btn sp-btn--ghost" style="align-self:flex-start" :disabled="busy || !leaveWritable" @click="openReturnLeave(lv)">办理销假</button>
                </div>
                <div v-if="returnDraft.id === String(lv.id)" class="leave-return-editor">
                  <strong>确认已经返岗</strong>
                  <p>提交后由指导教师核实返岗情况；超期记录仍会保留完整风险留痕。</p>
                  <textarea v-model="returnDraft.note" class="sp-inp" maxlength="500" :disabled="busy" placeholder="填写销假说明，如：已按期返回实习岗位" />
                  <div class="leave-return-editor__actions">
                    <button class="sp-btn sp-btn--ghost" :disabled="busy" @click="closeReturnLeave">取消</button>
                    <button class="sp-btn" :disabled="busy || !leaveWritable || returnDraft.conflict || returnDraft.note.trim().length < 2" @click="confirmReturnLeave">确认销假</button>
                  </div>
                  <div v-if="returnDraft.conflict"><p>说明及原版本已保留，请读取当前原单核对。</p><button class="sp-btn sp-btn--ghost" :disabled="busy || leaveReading" @click="rereadLeave">读取当前记录核对</button><button class="sp-btn" :disabled="busy || !leaveConflictRead || !['APPROVED','OVERDUE'].includes(leaveDetail?.status)" @click="continueReturnAfterConflict">已核对，继续销假</button></div>
                </div>
                <div v-if="lv.returnNote" class="makeup-review-note">销假说明：{{ lv.returnNote }}</div>
                <div v-if="lv.reviewComment" class="makeup-review-note">{{ lv.status === 'NEEDS_REVISION' ? '补正要求' : lv.status === 'REJECTED' ? '驳回原因' : '审批意见' }}：{{ lv.reviewComment }}</div>
                <p v-if="lv.reviewAt" class="sp-muted">审批时间：{{ fmt(lv.reviewAt) }}</p>
              </div>
            </div>
          </section>
        </div>
        <section v-if="leaveDetail" class="sp-card" style="margin-top:16px">
          <div class="sp-panel__head">请假原单 {{ leaveDetail.id }} · 第{{ leaveDetail.version }}版</div>
          <p>{{ internshipLeaveStage(leaveDetail).label }} · {{ leaveDetail.startDate }} 至 {{ leaveDetail.endDate }}</p>
          <p style="white-space:pre-wrap">{{ leaveDetail.reason }}</p>
          <p v-if="leaveDetail.reviewComment">审批意见：{{ leaveDetail.reviewComment }} · {{ fmt(leaveDetail.reviewAt) }}</p>
          <section v-if="leaveDetail.approvalProgress" aria-label="审批进度"><strong>{{ leaveDetail.approvalProgress.label }}</strong><ol><li v-for="(step,index) in leaveDetail.approvalProgress.steps" :key="index">{{ step.label }} · {{ step.assignee }} · {{ step.statusLabel }}<p v-if="step.comment">{{ step.comment }}</p></li></ol></section>
          <p v-if="leaveDetail.status === 'RETURNED'">{{ leaveDetail.returnAcknowledged ? '指导教师已确认返岗' : '等待指导教师确认返岗' }}</p>
          <button v-if="leaveDetail.evidenceFileId" class="sp-btn sp-btn--ghost" @click="downloadLeaveEvidence(leaveDetail.evidenceFileId, leaveDetail.attachment?.fileName)">下载当前证明</button>
          <details v-for="(snapshot,index) in leaveDetail.submissionHistory || []" :key="index" style="margin-top:12px">
            <summary>第{{ snapshot.version }}版提交 · {{ snapshot.startDate }} 至 {{ snapshot.endDate }}</summary>
            <p style="white-space:pre-wrap">{{ snapshot.reason }}</p><p>提交时间：{{ fmt(snapshot.submittedAt) }}</p>
            <p v-if="snapshot.reviewComment">当次审批意见：{{ snapshot.reviewComment }} · {{ fmt(snapshot.reviewAt) }}</p>
            <button v-if="snapshot.evidenceFileId" class="sp-btn sp-btn--ghost" @click="downloadLeaveEvidence(snapshot.evidenceFileId)">下载该版证明</button>
          </details>
        </section>
      </template>

      <!-- 补卡申请 -->
      <template v-else-if="tab === 'makeup'">
        <div class="two">
          <section class="sp-card makeup-apply">
            <div class="sp-panel__head">申请补卡</div>
            <p class="sp-muted makeup-apply__lead">提交后由指导教师核对。定位异常补卡必须上传定位、考勤或现场佐证；通过后系统才会补写打卡留痕。</p>
            <div v-if="makeupReceipt" class="makeup-receipt" role="status">
              <strong>{{ makeupReceipt.statusLabel || '已提交待审核' }}</strong>
              <span>申请编号 {{ makeupReceipt.id }} · 第{{ makeupReceipt.version ?? 0 }}版</span>
              <span>下一步：指导教师核对申请；结果会回到“我的补卡”。</span>
            </div>
            <p v-if="makeupError" class="makeup-error" role="alert">{{ makeupError }}</p>
            <div class="sp-fieldlabel">补卡类型</div>
            <select v-model="makeupForm.makeupType" class="sp-inp" style="margin-bottom:12px" :disabled="busy">
              <option value="MISSING">缺卡补录</option>
              <option value="OUT_OF_RANGE">定位异常补录</option>
            </select>
            <div class="sp-fieldlabel">缺卡日期</div>
            <AppDatePicker v-model="makeupForm.checkinDate" class="sp-inp" style="margin-bottom:12px" label="缺卡日期" />
            <div class="sp-fieldlabel">事由</div>
            <textarea v-model="makeupForm.reason" class="sp-inp" style="margin-bottom:12px" maxlength="300" placeholder="详细说明缺卡原因（不少于5字）" />
            <div class="sp-fieldlabel">证据材料 {{ makeupEvidenceRequired ? '（必需）' : '（选传）' }}</div>
            <input type="file" class="sp-inp" style="margin-bottom:6px" :disabled="busy" @change="uploadMakeupEvidence" />
            <p class="sp-muted" style="margin-bottom:12px">
              {{ makeupForm.fileName || (makeupEvidenceRequired ? '请上传定位截图、考勤或现场佐证' : '普通缺卡可按学校要求选传佐证') }}
            </p>
            <button class="sp-btn" :disabled="busy || !makeupCanSubmit" @click="submitMakeup">{{ busy ? '提交中…' : '提交补卡申请' }}</button>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">我的补卡 · 办理进度</div>
            <div v-if="!makeups.length" class="sp-muted">暂无补卡申请</div>
            <div v-else style="display:flex;flex-direction:column;gap:10px">
              <div v-for="m in makeups" :key="m.id" class="repitem" style="flex-direction:column;align-items:stretch;gap:6px">
                <div style="display:flex;justify-content:space-between;align-items:center">
                  <span>{{ m.checkinDate }} · {{ m.makeupTypeLabel || m.makeupType || '补卡' }}</span>
                  <StatusTag :text="m.statusLabel || '待确认'" :tone="m.status==='APPROVED'?'success':m.status==='REJECTED'?'danger':'warn'" />
                </div>
                <div class="sp-muted" style="font-size:12px">{{ m.reason }}</div>
                <div v-if="m.reviewComment" class="makeup-review-note">教师意见：{{ m.reviewComment }}</div>
                <div style="display:flex;justify-content:space-between;align-items:center;gap:10px">
                  <span class="sp-muted" style="font-size:11px">第{{ m.version ?? 0 }}版 · {{ m.hasEvidence || m.evidenceFileId ? '已附证据' : '无附件' }}</span>
                  <button v-if="m.status === 'PENDING'" class="sp-btn sp-btn--ghost" :disabled="busy" @click="withdrawMakeup(m)">撤回</button>
                </div>
              </div>
            </div>
          </section>
        </div>
      </template>

      <!-- 岗位意向 -->
      <template v-else-if="tab === 'intention'">
        <p v-if="intentionReceipt" class="sp-receipt" role="status">{{ intentionReceipt }}</p>
        <p v-if="intentionError" class="sp-command-error" role="alert">{{ intentionError }}</p>
        <section v-if="['data','empty'].includes(sourceStates.intention.status)" class="sp-card sp-intention">
          <div class="sp-panel__head"><span>岗位意向</span><StatusTag :text="intentionMeta.statusLabel || '尚未填写'" /></div>
          <p class="sp-muted">意向供学校匹配岗位参考；保存不等于提交，也不等于正式申请通过或去向落实。</p>
          <p v-if="!intentionFlags.canEdit && !intentionFlags.canSubmit && !intentionFlags.canWithdraw" class="sp-result-note">{{ intentionReason || '当前暂不能办理，请联系学校核对。' }}</p>
          <div v-if="intentionMeta.preferredPositionId" class="sp-result-note">原意向岗位：{{ intentionMeta.preferredPositionTitle || '岗位名称待核对' }} · {{ intentionMeta.preferredCompanyName || '企业名称待核对' }}。保存更正仍保留该岗位偏好。</div>
          <div v-if="intentionConflict" class="sp-conflict" role="alert">
            <p>原单或办理条件已变化，当前输入仍保留。重新读取后，请核对下方最新记录再继续。</p>
            <button class="sp-btn sp-btn--ghost" :disabled="intentionBusy" @click="loadTab('intention', true)">重新读取最新记录</button>
            <template v-if="intentionLatest">
              <p>最新状态：{{ intentionLatest.intention?.statusLabel || '尚未填写' }}；城市：{{ intentionLatest.intention?.preferredCity || '未填写' }}；行业：{{ intentionLatest.intention?.preferredIndustry || '未填写' }}</p>
              <p>{{ intentionLatest.intention?.intentionNote || '暂无说明' }}</p>
              <button class="sp-btn sp-btn--ghost" :disabled="intentionBusy" @click="continueIntentionAfterConflict">已核对最新原单，保留输入继续</button>
            </template>
          </div>
          <template v-if="intentionFlags.canEdit || intentionConflict">
            <label class="sp-fieldlabel" for="intention-city">意向城市</label>
            <input id="intention-city" v-model.trim="intentionForm.preferredCity" class="sp-inp" maxlength="100" :disabled="!intentionCanEdit || intentionBusy" />
            <label class="sp-fieldlabel" for="intention-industry">意向行业</label>
            <input id="intention-industry" v-model.trim="intentionForm.preferredIndustry" class="sp-inp" maxlength="100" :disabled="!intentionCanEdit || intentionBusy" />
            <label class="sp-fieldlabel" for="intention-note">补充说明</label>
            <textarea id="intention-note" v-model.trim="intentionForm.intentionNote" class="sp-inp" maxlength="500" :disabled="!intentionCanEdit || intentionBusy" />
          </template>
          <dl v-else class="sp-result-facts"><div><dt>意向城市</dt><dd>{{ intentionMeta.preferredCity || '未填写' }}</dd></div><div><dt>意向行业</dt><dd>{{ intentionMeta.preferredIndustry || '未填写' }}</dd></div><div><dt>补充说明</dt><dd>{{ intentionMeta.intentionNote || '未填写' }}</dd></div></dl>
          <div class="sp-action-row">
            <button v-if="intentionCanEdit" class="sp-btn sp-btn--ghost" :disabled="intentionBusy" @click="saveIntention">{{ intentionBusy ? '正在办理…' : intentionMeta.status==='SUBMITTED' ? '保存更正' : '保存草稿' }}</button>
            <button v-if="intentionCanSubmit" class="sp-btn" :disabled="intentionBusy" @click="submitIntention">{{ intentionBusy ? '正在办理…' : intentionMeta.status==='WITHDRAWN' ? '重新提交原意向' : '提交意向' }}</button>
            <button v-if="intentionCanWithdraw" class="sp-btn sp-btn--ghost" :disabled="intentionBusy" @click="withdrawIntention">撤回意向</button>
            <button v-if="intentionCommitted" class="sp-btn sp-btn--ghost" :disabled="intentionBusy" @click="loadTab('intention', true)">重新读取办理结果</button>
          </div>
          <details v-if="intentionDirty && !intentionFlags.canEdit"><summary>查看保留的未提交内容</summary><p>{{ intentionForm.preferredCity }} · {{ intentionForm.preferredIndustry }}</p><p>{{ intentionForm.intentionNote }}</p></details>
        </section>
      </template>

      <!-- 正式申请 -->
      <template v-else-if="tab === 'application'">
        <section v-if="appPlaced" class="sp-card sp-result-summary">
          <div class="sp-panel__head"><span>本次实习去向</span><StatusTag :text="statusText(my.status)" /></div>
          <h2>{{ my.destinationType==='EXEMPTED' ? '本批次免实习已批准' : '实习去向已落实' }}</h2>
          <p>当前阶段仅可核对已有安排，无需重新填写正式申请。</p>
          <dl class="sp-result-facts"><div><dt>实习企业</dt><dd>{{ my.enterpriseName || '学校待核对' }}</dd></div><div><dt>实习岗位</dt><dd>{{ my.positionName || '学校待核对' }}</dd></div><div><dt>指导教师</dt><dd>{{ my.advisorName || '学校待分配' }}</dd></div></dl>
          <div class="sp-action-row"><button class="sp-btn" type="button" @click="selectTab('agreement')">查看三方协议</button><button class="sp-btn sp-btn--ghost" type="button" @click="selectTab('insurance')">查看实习保险</button><button v-if="applications.length" class="sp-btn sp-btn--ghost" type="button" :aria-expanded="applicationHistoryOpen" @click="applicationHistoryOpen=!applicationHistoryOpen">{{ applicationHistoryOpen ? '收起原申请与历史' : '查看原申请与历史' }}</button></div>
          <p v-if="appError" role="alert" class="report-error">{{ appError }}<button type="button" class="sp-btn sp-btn--ghost" @click="loadTab('application',true)">重新读取原申请</button></p>
          <p v-if="!appError && ['data','empty'].includes(sourceStates.application.status) && !applications.length" class="sp-muted">{{ my.destinationType==='ASSIGNED' ? '本次由学校安排去向，当前没有另行提交的普通申请记录。' : '当前没有普通申请记录；实习安排以上方已有结果为准。' }}</p>
        </section>
        <div v-show="!appPlaced || applicationHistoryOpen" class="two">
          <section class="sp-card">
            <div class="sp-panel__head">{{ appBase ? '查看或继续原申请' : '填写正式申请' }}</div>
            <p v-if="appReceipt" role="status">{{ appReceipt }}</p>
            <p v-if="appError" role="alert" class="report-error">{{ appError }}</p>
            <p v-if="appBase">原申请编号 {{ appBase.id }} · 第{{ appBase.version }}版 · {{ applicationStatusText(appBase.status) }}<br/>{{ appBase.reviewComment ? '审核意见：'+appBase.reviewComment : appBase.status==='APPROVED'?'学校已完成本次申请审核，可查看办理记录':appForm.applicationType==='EXEMPTION'?'提交后由学校审核免实习资格':'提交后由指导教师办理' }}</p>
            <p v-if="!appWritable">{{ my.historyMode ? '历史实习记录仅可查看。' : '当前申请或实习状态不可修改，请核对办理结果。' }}</p>
            <div v-if="appConflict" class="report-feedback"><p>原输入、附件和版本已保留；请先读取最新原单核对，系统不会自动覆盖。</p><button type="button" class="sp-btn sp-btn--ghost" :disabled="appBusy || appReading" @click="rereadApplication">读取最新原单核对</button><template v-if="appLatest"><p>最新第{{ appLatest.version }}版 · {{ applicationStatusText(appLatest.status) }} · {{ appLatest.companyName || '未填企业' }} · {{ appLatest.positionName || '未填岗位' }}</p><details><summary>查看最新原单填写内容</summary><p v-for="field in appFields" :key="field.key">{{ field.label }}：{{ appLatest[field.key] ?? '未填写' }}</p><p>专业对口：{{ appLatest.majorMatch===true?'是':appLatest.majorMatch===false?'否':'未填写' }}；薪资：{{ appLatest.agreedSalary ?? '未填写' }}</p><p>申请说明：{{ appLatest.applicationNote || '未填写' }}</p><p>审核意见：{{ appLatest.reviewComment || '无' }}</p></details><button type="button" class="sp-btn" :disabled="appBusy || appReading" @click="adoptLatestApplication">采用最新原单并重新修改</button></template></div>
            <fieldset :disabled="appBusy || appReading || !appWritable || appConflict" style="border:0;padding:0;min-width:0">
            <div class="sp-fieldlabel">申请类型</div>
            <select v-model="appForm.applicationType" :disabled="!!appBase" class="sp-inp" style="margin-bottom:12px" @change="newApplication(appForm.applicationType)">
              <option value="POSITION">校内岗位志愿</option>
              <option value="SELF_ARRANGED">自主实习</option>
              <option value="EXEMPTION">免实习申请</option>
            </select>
            <template v-if="appForm.applicationType === 'POSITION'">
              <div class="sp-fieldlabel">选择岗位</div>
              <select v-model="appForm.positionId" class="sp-inp" style="margin-bottom:12px">
                <option value="">请选择企业岗位</option>
                <option v-if="appForm.positionId && !appPositions.some(row=>String(row.id)===String(appForm.positionId))" :value="appForm.positionId">原岗位尚未在当前页读取，请继续加载核对</option>
                <option v-for="position in appPositions" :key="position.id" :value="String(position.id)" :disabled="!position.canSelect">
                  {{ position.companyName }} · {{ position.title }} · {{ position.workLocation || '地点待定' }}
                </option>
              </select>
              <p>已读取 {{ appPositions.length }} / {{ appPositionsTotal }} 个当前批次岗位</p><p v-if="appPositionsError" role="alert">{{ appPositionsError }}</p><button v-if="appPositionsMore" type="button" class="sp-btn sp-btn--ghost" :disabled="appPositionsLoading" @click="loadMoreApplicationPositions">继续加载岗位</button>
            </template>
            <template v-else-if="appForm.applicationType === 'EXEMPTION'">
              <p>填写免实习原因和后续去向，上传学校认可的佐证。提交后由学校审核；已有岗位去向须先按正式变更流程办理。</p>
              <label>免实习类型 *<select v-model="appForm.exemptionType" class="sp-inp"><option value="">请选择</option><option v-for="type in exemptionTypes" :key="type.value" :value="type.value">{{ type.label }}</option></select></label>
              <label>免实习后去向 *<input v-model.trim="appForm.exemptionDestination" maxlength="200" class="sp-inp" placeholder="填写升学学校、入伍或其他后续去向" /></label>
              <label>免实习原因 *<textarea v-model.trim="appForm.exemptionReason" maxlength="500" class="sp-inp" placeholder="不少于5字" /></label>
              <label>免实习佐证材料 *<input type="file" aria-label="免实习佐证材料" class="sp-inp" @change="uploadApplicationEvidence($event,'evidence')" /></label>
            </template>
            <template v-else-if="appForm.applicationType === 'SELF_ARRANGED'">
              <p>{{ appBase?.companyRegistryVerified ? '该原单企业登记信息已由授权数据源核验。' : '企业登记信息尚未通过授权数据源核验；填写信息不等于企业认证。' }}</p>
              <label v-for="field in appFields" :key="field.key" style="display:block;margin-bottom:12px">{{ field.label }}{{ field.min?' *':'' }}
                <select v-if="field.options" v-model="appForm[field.key]" class="sp-inp"><option value="">请选择</option><option v-if="appForm[field.key] && !field.options.includes(appForm[field.key])" :value="appForm[field.key]">{{ appForm[field.key] }}</option><option v-for="option in field.options" :key="option" :value="option">{{ option }}</option></select>
                <textarea v-else-if="field.key==='workContent'" v-model="appForm[field.key]" :maxlength="field.max" class="sp-inp" />
                <input v-else v-model="appForm[field.key]" :type="field.type" :maxlength="field.max" class="sp-inp" />
              </label>
              <label>专业是否对口 *<select v-model="appForm.majorMatch" class="sp-inp"><option :value="null">请选择</option><option :value="true">是</option><option :value="false">否</option></select></label>
              <label>约定实习薪资（元/月）*<input v-model="appForm.agreedSalary" type="number" min="0" max="100000000" step="0.01" class="sp-inp" /></label>
              <div class="sp-fieldlabel">自主实习证明材料</div>
              <input type="file" aria-label="自主实习证明材料" class="sp-inp" @change="uploadApplicationEvidence($event,'evidence')" />
              <div class="sp-fieldlabel">三方协议照片（选填，最多9份）</div><input type="file" aria-label="三方协议照片" accept="image/*" :disabled="appForm.agreementFileIds.length>=9" class="sp-inp" @change="uploadApplicationEvidence($event,'agreement')" />
            </template>
            <template v-if="appForm.applicationType!=='POSITION'"><button type="button" class="sp-btn sp-btn--ghost" @click="refreshApplicationFiles">刷新材料安全检查</button><p v-if="!appAttachmentsReady">材料安全检查未完成，填写内容会保留，请刷新检查结果。</p></template>
            <template v-if="appForm.applicationType!=='EXEMPTION'"><div class="sp-fieldlabel">申请说明</div>
            <textarea v-model.trim="appForm.applicationNote" class="sp-inp" style="margin-bottom:12px" placeholder="不少于 5 字" /></template>
            <button type="button" class="sp-btn sp-btn--ghost" :disabled="!appAttachmentsReady" @click="saveApplicationDraft">保存草稿</button>
            <button type="button" class="sp-btn" :disabled="!appAttachmentsReady" @click="submitApplication">{{ appBase?.status==='REJECTED'?'原单补正后提交':'保存并提交' }}</button>
            </fieldset>
            <button v-if="appBase?.status==='PENDING_REVIEW' && !my.historyMode" type="button" class="sp-btn sp-btn--ghost" :disabled="appBusy || appReading" @click="withdrawApplication">撤回当前申请</button>
            <div v-if="appFiles.length"><p v-for="file in appFiles" :key="file.fileId">{{ file.fileName || '申请材料' }} · {{ file.statusText || '状态待核实' }} <button type="button" class="sp-btn sp-btn--ghost" :disabled="appBusy || appReading || file.readyForBusiness!==true || !file.canDownload" @click="downloadApplicationFile(file)">下载材料</button><button v-if="appWritable" type="button" class="sp-btn sp-btn--ghost" :disabled="appBusy || appReading || appConflict" @click="removeApplicationFile(file.fileId)">移除材料</button></p></div>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">我的申请</div>
            <p v-if="!applications.length">暂无申请，可以填写新申请。</p>
            <article v-for="item in applications" :key="item.id" class="report-feedback"><strong>{{ item.applicationTypeLabel }} · {{ applicationStatusText(item.status) }}</strong><p>{{ item.companyName || item.exemptionDestination || '去向待填写' }} · {{ item.positionName || '' }}</p><p>{{ item.applicationNote }}</p><p v-if="item.reviewComment">审核意见：{{ item.reviewComment }}</p><button type="button" class="sp-btn sp-btn--ghost" :disabled="appBusy || appReading" @click="openApplication(item)">查看或继续原单</button></article>
            <button type="button" class="sp-btn sp-btn--ghost" :disabled="appBusy || appReading" @click="loadApplications">刷新申请列表</button>
          </section>
        </div>
      </template>

      <!-- 调岗退岗 -->
      <template v-else-if="tab === 'change'">
        <div class="two">
          <section class="sp-card">
            <div class="sp-panel__head">{{ changeEditing ? '补正原变更申请' : '发起变更' }}</div>
            <p v-if="!changeWritable">当前为历史实习记录，仅可查看处理记录，不能再发起或补正变更。</p>
            <p v-if="changeEditing">原申请 #{{ changeEditing.id }} · 第 {{ changeEditing.version }} 版<br />教师意见：{{ changeEditing.reviewComment || '请补充变更说明' }}<br /><span v-if="changeNeedsTarget">请重新核对并选择当前可申请岗位。</span></p>
            <p v-if="changeError" role="alert">{{ changeError }} <button class="sp-btn" :disabled="changeBusy" @click="loadChanges(changeHistoryPage)">重新读取处理记录</button></p>
            <p v-if="changeReceipt" role="status">{{ changeReceipt.actionLabel }}：申请 #{{ changeReceipt.id }} · 第 {{ changeReceipt.version }} 版 · {{ changeReceipt.statusLabel }}。{{ changeReceipt.status === 'PENDING' ? '下一步由指导教师审核，审核前可撤回。' : '可在处理记录中回读结果。' }}</p>
            <div class="sp-fieldlabel">变更类型</div>
            <select v-model="changeForm.changeType" aria-label="变更类型" :disabled="!changeWritable || !!changeEditing || changeBusy" class="sp-inp" style="margin-bottom:12px" @change="changeTypePicked">
              <option value="CHANGE_POSITION">换岗</option>
              <option value="CHANGE_ENTERPRISE">换实习单位</option>
              <option value="SELF_ARRANGED">转自主实习</option>
              <option value="WITHDRAW_POST">退岗</option>
            </select>
            <template v-if="changeNeedsTarget">
              <div style="display:flex;gap:8px;margin-bottom:12px"><input v-model="changeKeyword" aria-label="搜索目标岗位" maxlength="100" class="sp-inp" style="flex:1;min-width:0;width:auto" placeholder="搜索企业、岗位或地点" @keyup.enter="loadChangeTargets(1)" /><button class="sp-btn" style="flex-shrink:0;white-space:nowrap" :disabled="changeTargetLoading || changeBusy" @click="loadChangeTargets(1)">搜索</button></div>
              <p v-if="changeTargetError" role="alert">{{ changeTargetError }} <button class="sp-btn" @click="loadChangeTargets(changeTargetPage)">重试岗位查询</button></p>
              <p v-else-if="changeTargetLoading">正在核验本批次目标岗位…</p>
              <p v-else-if="!changeTargets.length">本页暂无目标岗位，可调整搜索或翻页。</p>
              <div class="sp-fieldlabel">目标岗位（必选）</div>
              <select v-model="changeForm.targetPositionId" aria-label="目标岗位" :disabled="changeBusy || changeTargetLoading" class="sp-inp" style="margin-bottom:12px" @change="selectChangeTarget">
                <option value="">请选择目标岗位</option>
                <option v-for="position in changeTargets" :key="position.id" :value="String(position.positionId)" :disabled="position.canSelect !== true">
                  {{ position.companyName }} · {{ position.title }} · {{ position.workLocation || '地点待定' }} · 余 {{ position.remaining }} 个名额{{ position.canSelect !== true ? ' · 暂不可选：' + (position.selectionReason || '岗位条件待核验') : '' }}
                </option>
              </select>
              <p v-if="changeSelectedTarget">已选：{{ changeSelectedTarget.companyName }} · {{ changeSelectedTarget.title }}。审批时将再次核验准入和名额。</p>
              <div style="display:flex;gap:8px;align-items:center;margin-bottom:12px"><button class="sp-btn" :disabled="changeTargetLoading || changeTargetPage <= 1" @click="loadChangeTargets(changeTargetPage-1)">上一页岗位</button><span>第 {{ changeTargetPage }} 页</span><button class="sp-btn" :disabled="changeTargetLoading || !changeTargetMore" @click="loadChangeTargets(changeTargetPage+1)">下一页岗位</button></div>
            </template>
            <template v-if="changeForm.changeType === 'SELF_ARRANGED'">
              <div class="sp-fieldlabel">目标企业名称</div>
              <input v-model.trim="changeForm.targetEnterpriseName" :disabled="changeBusy" class="sp-inp" style="margin-bottom:12px" />
              <div class="sp-fieldlabel">目标岗位名称</div>
              <input v-model.trim="changeForm.targetPositionName" :disabled="changeBusy" class="sp-inp" style="margin-bottom:12px" />
            </template>
            <div class="sp-fieldlabel">事由（不少于 5 字）</div>
            <textarea v-model.trim="changeForm.reason" aria-label="变更事由" maxlength="500" :disabled="changeBusy" class="sp-inp" style="margin-bottom:12px" />
            <p>审核通过后，原岗位名额与企业指导关系结束，原知情确认及协议失效；需按新去向重新办理合规上岗。</p>
            <button class="sp-btn" :disabled="!changeWritable || busy || changeBusy || !changeForm.reason || changeForm.reason.length < 5" @click="submitChange">{{ changeBusy ? '办理中…' : changeEditing ? '补正后重交原申请' : '提交变更' }}</button>
            <button v-if="changeEditing" class="sp-btn" :disabled="changeBusy" @click="cancelChangeEditing">取消补正</button>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">我的变更</div>
            <p v-if="!changes.length">暂无变更申请</p>
            <article v-for="item in changes" :key="item.id" style="padding:12px 0;border-bottom:1px solid var(--border)">
              <strong>{{ item.changeTypeLabel }} · {{ item.statusLabel }}</strong><p>申请 #{{ item.id }} · 第 {{ item.version }} 版</p><p>{{ item.reason }}</p>
              <p v-if="item.targetEnterpriseName || item.targetPositionName">目标：{{ item.targetEnterpriseName }} · {{ item.targetPositionName }}</p><p v-if="item.reviewComment">教师意见：{{ item.reviewComment }}</p>
              <button v-if="item.status === 'PENDING'" class="sp-btn" :disabled="!changeWritable || busy || changeBusy" @click="withdrawChange(item)">撤回申请</button>
              <button v-if="item.status === 'REJECTED'" class="sp-btn" :disabled="!changeWritable || busy || changeBusy" @click="editChange(item)">原单补正重交</button>
            </article>
            <div style="display:flex;gap:8px;align-items:center;margin-top:12px"><button class="sp-btn" :disabled="changeBusy || changeHistoryPage <= 1" @click="loadChanges(changeHistoryPage-1)">上一页记录</button><span>第 {{ changeHistoryPage }} 页</span><button class="sp-btn" :disabled="changeBusy || !changeHistoryMore" @click="loadChanges(changeHistoryPage+1)">下一页记录</button></div>
          </section>
        </div>
      </template>

      <!-- 企业岗位库 -->
      <template v-else-if="tab === 'enterprises'">
        <section class="sp-card">
          <div class="sp-panel__head">企业岗位库</div>
          <p>本页展示普通正式申请岗位。学校招聘季的企业详情、三志愿和投递结果，请进入实习选岗。</p>
          <button type="button" class="sp-btn" @click="selectTab('selection')">进入实习选岗</button>
          <div style="display:flex;gap:10px;margin-bottom:12px">
            <input v-model.trim="enterpriseCity" class="sp-inp" placeholder="搜索企业、岗位或地点" />
            <button class="sp-btn" :disabled="busy" @click="loadEnterprises">查询</button>
          </div>
          <AutoTable :rows="enterprises" empty="暂无已发布岗位" :columns="[{key:'companyName',label:'企业'},{key:'title',label:'岗位'},{key:'workLocation',label:'地点'},{key:'remaining',label:'余量'}]" />
          <p>第{{ enterprisePage }}页 · 共{{ enterpriseTotal }}个当前批次岗位</p><button type="button" class="sp-btn sp-btn--ghost" :disabled="busy || enterprisePage<=1" @click="pageEnterprises(-1)">上一页</button><button type="button" class="sp-btn sp-btn--ghost" :disabled="busy || !enterpriseMore" @click="pageEnterprises(1)">下一页</button>
        </section>
      </template>

      <!-- 实习保险 -->
      <template v-else-if="tab === 'insurance'">
        <section v-if="insuranceReadOnly && ['data','empty'].includes(sourceStates.insurance.status)" class="sp-card sp-result-summary">
          <div class="sp-panel__head"><span>保险核验结果</span><StatusTag :text="insuranceMeta?.statusLabel || '状态待学校核实'" /></div>
          <h2>{{ insuranceMeta?.status==='VERIFIED' ? '本次保单已核验' : '保险记录（只读）' }}</h2>
          <dl class="sp-result-facts"><div><dt>承保机构</dt><dd>{{ insuranceMeta?.insurerName || insForm.insurerName || '未填写' }}</dd></div><div><dt>保单号</dt><dd>{{ insuranceMeta?.policyNo || insForm.policyNo || '未填写' }}</dd></div><div><dt>险种</dt><dd>{{ insuranceMeta?.coverageType || insForm.coverageType || '未填写' }}</dd></div><div><dt>保障期间</dt><dd>{{ insForm.effectiveDate || '未填写' }} 至 {{ insForm.expiryDate || '未填写' }}</dd></div></dl>
          <p v-if="insuranceMeta?.verifyComment" class="sp-result-note">核验意见：{{ insuranceMeta.verifyComment }}</p>
          <p class="sp-muted">{{ my.historyMode ? '历史保单仅可核对原结果与凭证。' : '当前无需重复提交。实习安排变化时，按学校允许的续保条件办理。' }}</p>
          <div v-if="insuranceMeta?.fileId" class="sp-action-row"><button class="sp-btn" type="button" :disabled="insuranceProofBusy" @click="openInsuranceProof(false)">查看保险凭证</button><button class="sp-btn sp-btn--ghost" type="button" :disabled="insuranceProofBusy" @click="openInsuranceProof(true)">下载保险凭证</button></div>
          <section v-if="insuranceProof" class="sp-insurance-preview" aria-label="保险凭证预览"><div class="sp-action-row"><strong>{{ insuranceProof.name }}</strong><button type="button" class="sp-btn sp-btn--ghost" @click="closeInsuranceProof">关闭凭证预览</button></div><img v-if="insuranceProof.image" :src="insuranceProof.url" alt="当前保单的保险凭证" /><iframe v-else :src="insuranceProof.url" title="当前保单的保险凭证" /></section>
          <p v-if="insuranceError" class="sp-command-error" role="alert">{{ insuranceError }}</p>
        </section>
        <div v-else-if="!insuranceReadOnly" class="two">
          <section class="sp-card">
            <div class="sp-panel__head">{{ insuranceMeta?.canRenew ? '更新保障并重新核验' : insuranceMeta?.status === 'REJECTED' ? '补正保险材料' : '提交保险信息' }}</div>
            <p v-if="insuranceMeta?.verifyComment" class="sp-muted" role="status">核验意见：{{ insuranceMeta.verifyComment }}</p>
            <p v-if="insuranceMeta?.coverageReason" class="sp-muted" role="status">{{ insuranceMeta.coverageReason }}</p>
            <p v-if="insuranceError" role="alert">{{ insuranceError }}</p>
            <fieldset :disabled="busy || insuranceReadOnly" style="border:0;margin:0;padding:0;min-width:0">
            <div class="sp-fieldlabel">保单号</div>
            <input v-model.trim="insForm.policyNo" aria-label="保单号" class="sp-inp" style="margin-bottom:12px" />
            <div class="sp-fieldlabel">承保机构</div>
            <input v-model.trim="insForm.insurerName" aria-label="承保机构" class="sp-inp" style="margin-bottom:12px" />
            <div class="sp-fieldlabel">险种</div>
            <input v-model.trim="insForm.coverageType" aria-label="险种" class="sp-inp" style="margin-bottom:12px" />
            <div class="sp-fieldlabel">生效日</div>
            <AppDatePicker v-model="insForm.effectiveDate" class="sp-inp" style="margin-bottom:12px" role="start" :end-value="insForm.expiryDate" label="生效日期" />
            <div class="sp-fieldlabel">失效日</div>
            <AppDatePicker v-model="insForm.expiryDate" class="sp-inp" style="margin-bottom:12px" role="end" :start-value="insForm.effectiveDate" label="到期日期" />
            <div class="sp-fieldlabel">保单扫描件</div>
            <label class="sp-btn sp-btn--ghost" :aria-disabled="busy">
              上传保单扫描件
              <input type="file" aria-label="上传保单扫描件" style="position:absolute;width:1px;height:1px;opacity:0" :disabled="busy" @change="uploadInsurancePolicy" />
            </label>
            <p class="sp-muted" style="margin-bottom:12px">{{ insForm.fileId ? '保单文件已上传' : '请上传保单扫描件' }}</p>
            <div v-if="pendingInsuranceFile" role="status">
              <p>{{ pendingInsuranceFile.fileName }} · {{ pendingInsuranceFile.statusText }}</p>
              <button type="button" class="sp-btn sp-btn--ghost" :disabled="busy" @click="refreshPendingInsurance">查看保单扫描结果</button>
              <p class="sp-muted">填写内容已保留，扫描通过后可继续提交；被拒绝的文件请更换。</p>
            </div>
            </fieldset>
            <button class="sp-btn" :disabled="busy || insuranceConflict || insuranceReadOnly || !!pendingInsuranceFile" @click="saveInsurance">{{ busy ? '处理中…' : insuranceMeta?.canRenew ? '更新保单并提交核验' : insuranceMeta?.status === 'REJECTED' ? '补正并重新提交' : '提交保险' }}</button>
            <button v-if="insuranceConflict" class="sp-btn" :disabled="busy" @click="loadTab('insurance', true)">重新读取最新保单</button>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">当前保险</div>
            <p class="sp-muted">状态：{{ insuranceMeta?.statusLabel || '未提交' }}</p>
            <p v-if="insuranceMeta?.policyNo" class="sp-muted">保单号：{{ insuranceMeta.policyNo }} · {{ insuranceMeta.insurerName }}</p>
            <p v-if="insuranceMeta?.status === 'PENDING_VERIFY'" class="sp-muted">已交学校核验，核验结果会在这里更新。</p>
            <p v-if="insuranceMeta?.canRenew" class="sp-muted">更新后交学校重新核验，旧保单的核验记录会保留。新保障确认前，不能凭本次提交办理上岗。</p>
            <p v-else-if="insuranceMeta?.status === 'VERIFIED'" class="sp-muted">保单已核验，当前无需更新。实习安排变化时请先联系学校核实。</p>
          </section>
        </div>
      </template>

      <!-- 实习计划 / 多方案 -->
      <template v-else-if="tab === 'plan'">
        <section v-if="planAssignments.length > 1" class="sp-card sp-plan-switch">
          <div class="sp-fieldlabel">当前实习方案</div>
          <select v-model="selectedPlanId" class="sp-inp" :disabled="busy || planHasDraft || sourceStates.plan.status === 'loading'" @change="changePlan">
            <option v-for="item in planAssignments" :key="item.planId" :value="String(item.planId)">
              {{ item.isPrimary ? '主方案 · ' : '' }}{{ item.planTitle }} · {{ item.batchName }}
            </option>
          </select>
          <p class="sp-muted" style="margin:8px 0 0">每份方案单独确认、单独记录任务进度；切换不会改变你的实习主记录。</p>
          <p v-if="planHasDraft" class="sp-muted">当前方案有未提交的任务填写，请提交或清除后再切换方案，避免丢失内容。</p>
        </section>
        <section class="sp-card">
          <div class="sp-panel__head">实习计划书 <span v-if="planMeta?.isPrimary" class="sp-muted">主方案</span></div>
          <p v-if="sourceStates.plan.status === 'loading'" class="sp-muted">正在读取所选计划…</p>
          <template v-else-if="planMeta && (planMeta.title || planMeta.planTitle || planMeta.id)">
            <p style="font-size:15px;font-weight:600">{{ planMeta.title || planMeta.planTitle || '实习计划' }}</p>
            <p class="sp-muted" style="margin-top:8px">
              {{ planMeta.internshipTypeLabel || '' }}
              <span v-if="planMeta.batchName"> · {{ planMeta.batchName }}</span>
              · {{ planMeta.ackStatusLabel || (planMeta.ackStatus === 'ACKNOWLEDGED' ? '已确认' : '待确认') }}
            </p>
            <p v-if="planMeta.objectives" class="sp-muted" style="margin-top:10px;white-space:pre-wrap"><b>实习目的：</b>{{ planMeta.objectives }}</p>
            <p v-if="planMeta.requirements" class="sp-muted" style="margin-top:10px;white-space:pre-wrap"><b>实习要求：</b>{{ planMeta.requirements }}</p>
            <p v-if="planMeta.content || planMeta.summary" class="sp-muted" style="margin-top:10px;white-space:pre-wrap"><b>实习内容：</b>{{ planMeta.content || planMeta.summary }}</p>
            <details style="margin-top:12px">
              <summary>计划详情与附件</summary>
              <p>计划编号：{{ planMeta.planNo || '未填写' }} · 适用专业：{{ planMeta.majorName || '未填写' }} · 培养层次：{{ planMeta.educationLevel || '未填写' }}</p>
              <p>实习对象：{{ planMeta.targetAudience || '未填写' }} · 负责人：{{ planMeta.responsibleName || '未填写' }}</p>
              <p>计划人数：{{ planMeta.basicSnapshot?.plannedCount ?? '未配置' }} · 实习日期：{{ planMeta.basicSnapshot?.startDate || '未配置' }} 至 {{ planMeta.basicSnapshot?.endDate || '未配置' }} · 周数：{{ planMeta.basicSnapshot?.internshipWeeks ?? '未配置' }}</p>
              <p>补贴标准：{{ planMeta.subsidyStandard || '未填写' }}</p>
              <p>应签到：{{ planMeta.rulesSnapshot?.requiredCheckinDays ?? '未配置' }}天 · 周记：{{ planMeta.rulesSnapshot?.weeklyRequiredCount ?? '未配置' }}篇 · 每篇至少{{ planMeta.rulesSnapshot?.weeklyMinWordCount ?? '未配置' }}字</p>
              <p>考核内容：{{ planMeta.assessmentContent || '未填写' }}</p>
              <p>考核比例：<span v-for="(item, index) in planMeta.rulesSnapshot?.scoreComponents || []" :key="index">{{ item.name }} {{ Math.round(Number(item.weight || 0) * 100) }}% </span></p>
              <button v-for="file in planMeta.attachments || []" :key="file.fileId" type="button" class="sp-btn sp-btn--ghost sp-btn--sm" @click="openPlanAttachment(file)">下载{{ file.fileName || '计划附件' }}</button>
            </details>
            <button v-if="planMeta.ackStatus !== 'ACKNOWLEDGED'" class="sp-btn" style="margin-top:12px" :disabled="busy" @click="ackPlan">确认当前方案</button>
          </template>
          <p v-else class="sp-muted">暂无已发布计划</p>
        </section>
        <section v-if="planMeta?.id && sourceStates.plan.status !== 'loading'" class="sp-card sp-plan-tasks">
          <div class="sp-panel__head">方案任务 <span class="sp-muted">{{ planTaskSummary.approved || 0 }}/{{ planTaskSummary.total || 0 }} 已完成</span></div>
          <p v-if="planMeta.ackStatus !== 'ACKNOWLEDGED'" class="sp-muted">请先确认当前方案，再提交任务完成情况。</p>
          <StateBlock v-else-if="!planTasks.length" type="empty" text="当前方案暂无任务" />
          <div v-else class="sp-plan-task-list">
            <article v-for="task in planTasks" :key="task.sortOrder" class="sp-plan-task">
              <div class="sp-plan-task__head">
                <div><strong>{{ task.sortOrder }}. {{ task.name }}</strong><p>{{ task.requirement || '未填写完成要求' }}</p></div>
                <StatusTag :text="task.progressStatusLabel || task.progressStatus" :tone="task.progressStatus === 'APPROVED' ? 'success' : task.progressStatus === 'REJECTED' ? 'danger' : task.progressStatus === 'SUBMITTED' ? 'warn' : 'neutral'" />
              </div>
              <p v-if="task.deadline" class="sp-muted">截止：{{ fmt(task.deadline) }}</p>
              <p v-if="task.reviewComment" class="report-feedback"><strong>教师意见</strong>{{ task.reviewComment }}</p>
              <template v-if="planMeta.ackStatus === 'ACKNOWLEDGED' && !['APPROVED','SUBMITTED'].includes(task.progressStatus)">
                <div class="sp-fieldlabel">完成说明 <span>至少 {{ planTaskMinimumWords }} 字</span></div>
                <textarea v-model="task._note" class="sp-inp" style="margin-bottom:8px" :disabled="busy" placeholder="说明完成过程、结果与收获" />
                <div class="sp-fieldlabel">任务凭证（选传）</div>
                <input type="file" class="sp-inp" :disabled="busy" @change="uploadPlanTaskEvidence($event, task)" />
                <p v-if="task._evidenceFileName" class="sp-muted">{{ task._evidenceFileName }}</p>
                <button v-if="task._evidenceFileId && task._evidenceFileId !== task.evidenceFileId" type="button" class="sp-btn sp-btn--ghost sp-btn--sm" :disabled="busy" @click="task._evidenceFileId = task.evidenceFileId || ''; task._evidenceFileName = task.evidenceFileId ? '已上传凭证' : ''">移除未提交凭证</button>
                <button class="sp-btn" style="margin-top:10px" :disabled="busy || String(task._note || '').trim().length < planTaskMinimumWords" @click="submitPlanTask(task)">提交任务</button>
              </template>
              <p v-else-if="task.studentNote" class="sp-muted" style="white-space:pre-wrap">完成说明：{{ task.studentNote }}</p>
            </article>
          </div>
        </section>
      </template>

      <!-- 实习求助 -->
      <template v-else-if="tab === 'help'">
        <p v-if="helpReceipt" class="sp-receipt" role="status">求助单 {{ helpReceipt.id }} 已登记，当前办理状态以下方原单进度为准。</p>
        <p v-if="helpError" class="report-error" role="alert">{{ helpError }}</p>
        <div v-if="['data','empty'].includes(sourceStates.help.status)" class="two">
          <section class="sp-card">
            <div class="sp-panel__head">向指导教师求助</div>
            <p class="sp-muted">岗位适应、工作安排或安全方面需要帮助时，填写具体情况，提交后沿同一份求助单查看处理进度。</p>
            <p v-if="my.historyMode">历史实习仅可查看求助记录。</p>
            <p v-else-if="helpHasOpen" class="sp-result-note">已有未办结或待核对的求助单，请查看右侧进度；本次输入保留，暂不重复新建。</p>
            <fieldset :disabled="helpBusy || helpCommitted || helpHasOpen || my.historyMode" style="border:0;padding:0;margin:0;min-width:0">
              <label class="sp-fieldlabel" for="help-level">紧急程度</label><select id="help-level" v-model="helpForm.riskLevel" class="sp-inp" style="margin-bottom:16px"><option value="LOW">一般</option><option value="MEDIUM">较急</option><option value="HIGH">紧急</option></select>
              <label class="sp-fieldlabel" for="help-title">标题（可选）</label><input id="help-title" v-model.trim="helpForm.title" maxlength="200" class="sp-inp" style="margin-bottom:16px" placeholder="默认：学生实习求助" />
              <label class="sp-fieldlabel" for="help-content">情况说明（5至500字）</label><textarea id="help-content" v-model.trim="helpForm.content" maxlength="500" class="sp-inp" style="margin-bottom:16px" placeholder="说明遇到的情况和希望老师协助的事项" />
              <button type="button" class="sp-btn" :disabled="!helpCanSubmit" @click="submitHelp">{{ helpBusy ? '正在提交…' : '提交求助' }}</button>
            </fieldset>
          </section>
          <section class="sp-card"><div class="sp-panel__head">我的求助进度</div><button type="button" class="sp-btn sp-btn--ghost" :disabled="helpBusy" @click="loadTab('help',true)">刷新求助进度</button><p v-if="!helpRows.length" class="sp-muted">当前实习没有求助记录。</p><article v-for="row in helpRows" :key="row.id" class="report-original" style="margin-top:18px"><strong>{{ row.title || '学生实习求助' }}</strong><p>求助单 {{ row.id }} · <StatusTag :text="helpStatus(row.status)" :tone="['RESOLVED','CLOSED'].includes(row.status)?'success':'warn'" /></p><p v-if="row.latestFeedback" class="report-full-text">最新记录：{{ row.latestFeedback }}</p><p class="sp-muted">更新于 {{ fmt(row.updatedAt) }}</p><p>{{ ['RESOLVED','CLOSED'].includes(row.status)?'本次求助已结束，原单及处理记录保留。':'由指导教师继续跟进，请按原单进度与老师联系。' }}</p></article></section>
        </div>
      </template>

      <!-- 周报/月报/总结 -->
      <template v-else-if="tab === 'report'">
        <div class="report-head">
          <div><strong>过程报告</strong><p>按周期记录工作与收获；退回后从原记录继续修改，重新提交仍保留历史版本。</p></div>
          <span>提交后交给指导教师批阅</span>
        </div>
        <div class="report-tabs" aria-label="报告类型">
          <button v-for="r in reportTabs" :key="r" class="sp-tab" :class="{'is-active':reportTab===r}" @click="switchReportTab(r)">{{ r }}</button>
        </div>
        <div v-if="reportReceipt" class="report-receipt" role="status">
          <strong>✓ {{ reportReceipt.actionLabel }}</strong>
          <span>报告 {{ reportReceipt.id }} · 第{{ reportReceipt.version }}版 · {{ reportReceipt.statusLabel }}</span>
          <span>{{ reportReceipt.nextStep }}</span>
          <button type="button" @click="reportReceipt = null">关闭</button>
        </div>
        <div v-if="reportError" class="report-error" role="alert">{{ reportError }}</div>
        <div class="two report-workspace">
          <section class="sp-card report-editor">
            <div class="sp-panel__head"><span>{{ reportReadMode ? '原单正文与批阅历史' : reportEditorTitle }}</span><button v-if="reportReadMode" type="button" class="sp-btn sp-btn--ghost" @click="returnToReportDraft">返回继续填写</button></div>
            <p v-if="weeklyReading || processReading" role="status">正在读取原单正文…</p>
              <article v-if="weeklyDetail && (reportReadMode || weeklyConflict)" class="report-original" aria-label="周报原单全文与历史">
                <strong>第{{ weeklyDetail.week }}周 · 第{{ weeklyDetail.reportVersion }}版 · {{ reviewText(weeklyDetail.status) }}</strong>
                <div v-for="field in weeklyFields" :key="field.key"><h4>{{ field.label }}</h4><p class="report-full-text">{{ weeklyDetail[field.key] || '未填写' }}</p></div>
                <p v-if="weeklyDetail.reviewComment">教师意见：{{ weeklyDetail.reviewComment }}</p>
                <p v-if="weeklyDetail.review?.ratingLevel">教师评分：{{ weeklyDetail.review.ratingLevel }}级</p>
                <details v-for="version in weeklyDetail.immutableVersions || []" :key="version.versionNo">
                  <summary>第{{ version.versionNo }}版 · {{ fmt(version.submittedAt) }} · {{ version.review?.action === 'RETURN' ? '已退回' : version.review?.action === 'APPROVE' ? '已通过' : '已提交' }}</summary>
                  <div v-for="field in weeklyFields" :key="field.key"><h4>{{ field.label }}</h4><p class="report-full-text">{{ version.content?.[field.key] || '未填写' }}</p></div>
                  <p v-if="version.review?.comment">该版教师意见：{{ version.review.comment }}</p>
                  <p v-if="version.review?.ratingLevel">该版评分：{{ version.review.ratingLevel }}级</p>
                  <button v-for="file in version.attachments || []" :key="file.fileId" type="button" class="report-revise" @click="openReportAttachment(file)">{{ file.fileName || '查看该版附件' }}</button>
                </details>
                <button v-if="weeklyConflict && weeklyDetail.status === 'RETURNED'" type="button" class="sp-btn" :disabled="busy" @click="continueWeeklyAfterConflict">已核对，保留填写内容继续修改</button>
                <button v-else-if="weeklyDetail.status==='RETURNED' && !my.historyMode" type="button" class="sp-btn" :disabled="busy" @click="editWeekly(weeklyDetail)">按意见修改这份原单</button>
              </article>
              <article v-if="processDetail && (reportReadMode || processConflict)" class="report-original" aria-label="过程报告原单全文与历史">
                <strong>{{ processDetail.reportTypeLabel }} · 第{{ processDetail.reportVersion }}次提交 · {{ reviewText(processDetail.status) }}</strong>
                <p class="report-full-text">{{ processDetail.content }}</p>
                <p v-if="processDetail.reviewComment">教师意见：{{ processDetail.reviewComment }}</p>
                <button v-if="processDetail.status==='RETURNED' && !my.historyMode && !processConflict" type="button" class="sp-btn" :disabled="busy" @click="editProcessReport(processDetail)">按意见修改这份原单</button>
                <p v-if="processDetail.review?.summaryScore != null">总结评分：{{ processDetail.review.summaryScore }}分（百分制）</p>
                <p v-else-if="processDetail.review?.ratingLevel">教师评价：{{ processDetail.review.ratingLevel }}级</p>
                <details v-for="version in processDetail.immutableVersions || []" :key="version.versionNo">
                  <summary>第{{ version.versionNo }}次提交 · {{ fmt(version.submittedAt) }} · {{ version.review?.action === 'RETURN' ? '已退回' : version.review?.action === 'APPROVE' ? '已通过' : '等待批阅' }}</summary>
                  <p class="report-full-text">{{ version.content }}</p>
                  <p v-if="version.review?.summaryScore != null">总结评分：{{ version.review.summaryScore }}分（百分制）</p>
                  <p v-else-if="version.review?.ratingLevel">教师评价：{{ version.review.ratingLevel }}级</p>
                  <p v-if="version.review?.comment">该次教师意见：{{ version.review.comment }}</p>
                  <button v-for="file in version.attachments || []" :key="file.fileId" type="button" class="report-revise" @click="openReportAttachment(file)">{{ file.fileName || '查看该次附件' }}</button>
                </details>
              </article>
            <template v-if="!reportReadMode">
            <template v-if="reportTab==='周报'">
              <label class="sp-fieldlabel" for="report-week">周次</label><input id="report-week" v-model.number="weeklyForm.week" type="number" min="1" :disabled="busy || weeklyEditing" class="sp-inp" style="margin-bottom:12px" placeholder="第几周" />
              <div v-if="weeklyExisting && !weeklyEditing" class="sp-result-note"><strong>本周已有{{ reviewText(weeklyExisting.status) }}的原单</strong><p>请查看原单和教师意见；修改退回内容时仍使用同一份记录。</p><button type="button" class="sp-btn" @click="openWeekly(weeklyExisting)">查看本周原单</button><button v-if="weeklyExisting.status==='RETURNED' && !my.historyMode" type="button" class="sp-btn sp-btn--ghost" @click="editWeekly(weeklyExisting)">按意见修改</button></div>
              <template v-if="!weeklyExisting || weeklyEditing">
              <label class="sp-fieldlabel" for="report-workContent">本周工作内容</label><textarea id="report-workContent" v-model="weeklyForm.workContent" maxlength="2000" :disabled="busy" class="sp-inp" style="margin-bottom:12px" placeholder="具体说明完成了什么任务、产出了什么结果" />
              <label class="sp-fieldlabel" for="report-harvestContent">收获与体会</label><textarea id="report-harvestContent" v-model="weeklyForm.harvestContent" maxlength="2000" :disabled="busy" class="sp-inp" style="margin-bottom:12px" placeholder="记录技能、经验和需要改进的地方" />
              <label class="sp-fieldlabel" for="report-planContent">下周计划</label><textarea id="report-planContent" v-model.trim="weeklyForm.planContent" maxlength="2000" :disabled="busy" class="sp-inp" style="margin-bottom:12px" placeholder="下周安排" />
              <div class="report-count">正文合计 {{ weeklyWordCount }} 字，{{ Number(reportRules.weeklyMinWords ?? 30)===0 ? '未设最低字数' : '至少'+(reportRules.weeklyMinWords ?? 30)+'字' }}，每段不超过2000字</div>
              <div v-if="weeklyConflict" class="report-error" role="alert">填写内容已保留。请先打开最新正文核对，再继续修改。<button type="button" class="sp-btn sp-btn--ghost" :disabled="busy || weeklyReading" @click="rereadWeeklyAfterConflict">读取最新原单核对</button></div>
              <div v-else-if="weeklyExisting && !weeklyEditing" class="report-feedback">该周已有记录；退回后请从右侧原单“按意见修改”，保留原单及历史版本。</div>
              <div class="sp-fieldlabel">附件（图片、视频、压缩包、文档或表格）</div>
              <label class="sp-btn sp-btn--ghost" :aria-disabled="busy">
                添加周报附件
                <input type="file" aria-label="添加周报附件" style="position:absolute;width:1px;height:1px;opacity:0" :disabled="busy" accept="image/*,video/*,.rar,.zip,.doc,.docx,.pdf,.xls,.xlsx" @change="uploadReportAttachment($event,'weekly')" />
              </label>
              <div v-if="weeklyForm.attachments.length" style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px">
                <div v-for="(file,index) in weeklyForm.attachments" :key="file.fileId">
                  <span role="status">{{ file.fileName }} · {{ file.statusText || '已提交的附件' }}</span>
                  <button type="button" class="sp-btn sp-btn--ghost sp-btn--sm" :disabled="busy" @click="removeReportAttachment('weekly',index)">移除附件</button>
                </div>
              </div>
              <button v-if="!scanFilesReady(weeklyForm.attachments)" type="button" class="sp-btn sp-btn--ghost" :disabled="busy" @click="refreshReportScans('weekly')">查看周报附件扫描结果</button>
              <button class="sp-btn" :disabled="busy || !weeklyCanSubmit || !scanFilesReady(weeklyForm.attachments)" @click="submitWeekly">{{ weeklyEditing ? '重新提交周报' : '提交周报' }}</button>
              </template>
            </template>
            <template v-else>
              <template v-if="reportTab === '日报'">
                <label class="sp-fieldlabel" for="report-day">报告日期</label><input id="report-day" v-model="reportForm.periodKey" type="date" :disabled="busy || processEditing" class="sp-inp" style="margin-bottom:12px" />
              </template>
              <template v-if="reportTab === '月报'">
                <label class="sp-fieldlabel" for="report-month">报告月份</label><input id="report-month" v-model="reportForm.periodKey" type="month" :disabled="busy || processEditing" class="sp-inp" style="margin-bottom:12px" />
              </template>
              <div v-if="processExisting && !processEditing" class="sp-result-note"><strong>本周期已有{{ reviewText(processExisting.status) }}的原单</strong><p>已提交正文、附件和批阅历史均保留在原单中。</p><button type="button" class="sp-btn" @click="openProcessReport(processExisting)">查看本周期原单</button><button v-if="processExisting.status==='RETURNED' && !my.historyMode" type="button" class="sp-btn sp-btn--ghost" @click="editProcessReport(processExisting)">按意见修改</button></div>
              <template v-if="!processExisting || processEditing">
              <label class="sp-fieldlabel" for="report-content">正文 <span>{{ reportMinimum===0 ? '未设最低字数' : '至少 '+reportMinimum+' 字' }}</span></label><textarea id="report-content" v-model="reportForm.content" :disabled="busy" class="sp-inp" style="min-height:220px;margin-bottom:6px" :placeholder="reportPlaceholder" />
              <div v-if="processConflict" class="report-error" role="alert">填写内容已保留，请读取最新原单核对。<button type="button" class="sp-btn sp-btn--ghost" :disabled="busy" @click="rereadProcessReport">读取最新原单核对</button><template v-if="processLatest"><p class="report-full-text">最新保存的正文：{{ processLatest.content }}</p><p>教师意见：{{ processLatest.reviewComment || '暂无' }}</p><button v-if="processLatest.status === 'RETURNED'" type="button" class="sp-btn" @click="continueProcessAfterConflict">已核对，保留填写内容继续修改</button></template></div>
              <div class="report-count">{{ reportForm.content.trim().length }} / {{ reportMinimum }} 字</div>
              <div class="sp-fieldlabel" style="margin-top:12px">附件（图片、视频、压缩包、文档或表格）</div>
              <label class="sp-btn sp-btn--ghost" :aria-disabled="busy">
                添加报告附件
                <input type="file" aria-label="添加报告附件" style="position:absolute;width:1px;height:1px;opacity:0" :disabled="busy" accept="image/*,video/*,.rar,.zip,.doc,.docx,.pdf,.xls,.xlsx" @change="uploadReportAttachment($event,'process')" />
              </label>
              <div v-if="reportForm.attachments.length" style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px">
                <div v-for="(file,index) in reportForm.attachments" :key="file.fileId">
                  <span role="status">{{ file.fileName }} · {{ file.statusText || '已提交的附件' }}</span>
                  <button type="button" class="sp-btn sp-btn--ghost sp-btn--sm" :disabled="busy" @click="removeReportAttachment('process',index)">移除附件</button>
                </div>
              </div>
              <button v-if="!scanFilesReady(reportForm.attachments)" type="button" class="sp-btn sp-btn--ghost" :disabled="busy" @click="refreshReportScans('process')">查看报告附件扫描结果</button>
              <button class="sp-btn" :disabled="busy || !reportCanSubmit || !scanFilesReady(reportForm.attachments)" @click="submitReport">{{ processEditing ? '重新提交' : '提交' }}{{ reportTab }}</button>
              </template>
            </template>
            </template>
          </section>
          <section class="sp-card report-index" aria-label="报告历史索引">
            <div class="sp-panel__head">{{ reportTab }}记录</div>
            <template v-if="reportTab === '周报'">
              <StateBlock v-if="!(my.weeklyReports||[]).length" type="empty" text="暂无周报" />
              <div v-else class="report-list">
                <div v-for="w in my.weeklyReports" :key="w.id || w.week" class="repitem report-item">
                  <div style="display:flex;align-items:center;justify-content:space-between">
                    <div style="flex:1"><strong>第 {{ w.week }} 周周报</strong><div class="report-item__meta">{{ fmt(w.submittedAt) }} · 第 {{ w.reportVersion || 1 }} 版</div></div>
                    <StatusTag :text="reviewText(w.status)" :tone="w.status==='APPROVED'?'success':w.status==='RETURNED'?'danger':'warn'" />
                  </div>
                  <p class="report-item__summary">{{ w.workContent || '正文未返回' }}</p>
                  <div v-if="w.attachments?.length" style="display:flex;flex-wrap:wrap;gap:6px;margin:8px 0">
                    <button v-for="file in w.attachments" :key="file.fileId" type="button" class="sp-btn sp-btn--ghost sp-btn--sm" @click="openReportAttachment(file)">{{ file.fileName || '附件' }}</button>
                  </div>
                  <div v-if="w.reviewComment" class="report-feedback"><strong>教师意见</strong>{{ w.reviewComment }}</div>
                  <div style="display:flex;gap:8px;flex-wrap:wrap">
                    <button type="button" class="report-revise" :disabled="busy || weeklyReading" @click="openWeekly(w)">查看正文与批阅历史</button>
                    <button type="button" class="report-revise" :disabled="busy" @click="downloadReportPdf('WEEKLY',w)">下载文档</button>
                    <button v-if="w.status === 'RETURNED' && !my.historyMode" type="button" class="report-revise" :disabled="busy" @click="editWeekly(w)">按意见修改</button>
                  </div>
                </div>
              </div>
              <button v-if="reportPages.WEEKLY.hasMore" class="sp-btn sp-btn--ghost" :disabled="busy || reportMoreBusy" @click="loadMoreReports('WEEKLY')">{{ reportMoreBusy ? '正在读取…' : '继续加载周报' }}</button>
              <p v-if="weeklyReading" role="status">正在读取原单正文…</p>

            </template>
            <template v-else>
              <StateBlock v-if="!processReportRows.length" type="empty" :text="'暂无' + reportTab + '记录'" />
              <div v-else class="report-list">
                <div v-for="p in processReportRows" :key="p.id" class="repitem report-item">
                  <div style="display:flex;align-items:center;justify-content:space-between">
                    <div style="flex:1"><strong>{{ p.periodKey === 'FINAL' ? '实习总结' : p.periodKey }}</strong><div class="report-item__meta">{{ fmt(p.submittedAt) }} · 第{{ p.reportVersion }}次提交</div></div>
                    <StatusTag :text="reviewText(p.status)" :tone="p.status==='APPROVED'?'success':p.status==='RETURNED'?'danger':'warn'" />
                  </div>
                  <p class="report-item__summary">{{ p.content || '正文未返回' }}</p>
                  <div v-if="p.attachments?.length" style="display:flex;flex-wrap:wrap;gap:6px;margin:8px 0">
                    <button v-for="file in p.attachments" :key="file.fileId" type="button" class="sp-btn sp-btn--ghost sp-btn--sm" @click="openReportAttachment(file)">{{ file.fileName || '附件' }}</button>
                  </div>
                  <div v-if="p.reviewComment" class="report-feedback"><strong>教师意见</strong>{{ p.reviewComment }}</div>
                  <div style="display:flex;gap:8px;flex-wrap:wrap">
                    <button type="button" class="report-revise" :disabled="busy || processReading" @click="openProcessReport(p)">查看正文与批阅历史</button>
                    <button type="button" class="report-revise" :disabled="busy" @click="downloadReportPdf('PROCESS',p)">下载文档</button>
                    <button v-if="p.status === 'RETURNED' && !my.historyMode" type="button" class="report-revise" :disabled="busy" @click="editProcessReport(p)">按意见修改</button>
                  </div>
                </div>
              </div>
              <button v-if="reportPages[processType].hasMore" class="sp-btn sp-btn--ghost" :disabled="busy || reportMoreBusy" @click="loadMoreReports(processType)">{{ reportMoreBusy ? '正在读取…' : '继续加载' + reportTab }}</button>
              <p v-if="processReading" role="status">正在读取原报告…</p>

            </template>
          </section>
        </div>
      </template>

      <!-- 实习成绩/自评 -->
      <template v-else-if="tab === 'eval'">
        <div v-if="evalReceipt" class="eval-receipt" role="status">
          <strong>✓ {{ evalReceipt.actionLabel }}</strong>
          <span>鉴定编号 {{ evalReceipt.id }} · 记录版本 {{ evalReceipt.version }} · {{ evalReceipt.statusLabel }}</span>
          <span>{{ evalReceipt.nextStep }}</span>
          <button type="button" @click="evalReceipt = null">关闭</button>
        </div>
        <section class="sp-card sp-formal-docs">
          <div class="sp-panel__head"><button type="button" class="sp-btn sp-btn--ghost" @click="selectTab('materials')">上传盖章企业鉴定表</button></div>
          <p>从学校发布的材料收件任务进入，上传后交指导教师审核；电脑与移动端共用原单和附件。</p>
          <div class="sp-panel__head">正式鉴定与证明 <span class="sp-muted">根据已审核正式业务事实生成</span></div>
          <div class="sp-formal-docs__grid">
            <div>
              <strong>企业实习鉴定表</strong>
              <p>包含性别、学生与校企导师电话、签到补签、日志/周记/月报/总结数量、企业评分等级及签章区；缺失资料如实标注。</p>
              <div class="sp-formal-docs__actions">
                <button v-if="!my.historyMode && my.status !== 'ARCHIVED'" class="sp-btn" :disabled="busy" @click="generateFormalDocument('ENTERPRISE_EVALUATION')">生成最新文书</button>
                <button v-if="latestFormalDocument('ENTERPRISE_EVALUATION')" class="sp-btn sp-btn--ghost" :disabled="busy" @click="downloadFormalDocument(latestFormalDocument('ENTERPRISE_EVALUATION'))">下载第 {{ latestFormalDocument('ENTERPRISE_EVALUATION').documentVersion }} 版</button>
              </div>
            </div>
            <div>
              <strong>学生实习证明</strong>
              <p>实习结束进入考核/归档后生成；有效签到与已批准补签按实习日期去重，异常和实习期外记录不计入。</p>
              <div class="sp-formal-docs__actions">
                <button v-if="!my.historyMode && my.status !== 'ARCHIVED'" class="sp-btn" :disabled="busy" @click="generateFormalDocument('INTERNSHIP_CERTIFICATE')">生成最新文书</button>
                <button v-if="latestFormalDocument('INTERNSHIP_CERTIFICATE')" class="sp-btn sp-btn--ghost" :disabled="busy" @click="downloadFormalDocument(latestFormalDocument('INTERNSHIP_CERTIFICATE'))">下载第 {{ latestFormalDocument('INTERNSHIP_CERTIFICATE').documentVersion }} 版</button>
              </div>
            </div>
          </div>
        </section>
        <div class="two">
          <section class="sp-card">
            <div class="sp-panel__head">实习自评 / 鉴定</div>
            <p v-if="selfEvalMeta?.id" class="sp-muted">记录版本 {{ selfEvalMeta.version }} · {{ selfEvalMeta.reviewStatusLabel || '等待学校审核' }}</p>
            <p v-if="selfEvalMeta?.reviewComment" class="sp-muted">学校意见：{{ selfEvalMeta.reviewComment }}</p>
            <p v-if="selfEvalMeta?.advisorOpinion" class="sp-muted">指导教师意见：{{ selfEvalMeta.advisorOpinion }}</p>
            <p v-if="evalConflict" role="alert">鉴定已变化，填写内容和原版本已保留。请核对最新记录后再决定是否采用。</p>
            <button v-if="evalConflict" class="sp-btn sp-btn--ghost" :disabled="busy" @click="adoptLatestEvaluation">核对并采用最新鉴定</button>
            <fieldset class="eval-fields" :disabled="busy || !evalCanEdit">
            <div class="sp-fieldlabel">工作表现自评</div><textarea v-model.trim="evalForm.performance" class="sp-inp" style="margin-bottom:12px" placeholder="请描述实习期间的工作表现" />
            <div class="sp-fieldlabel">收获与反思</div><textarea v-model.trim="evalForm.reflection" class="sp-inp" style="margin-bottom:12px" placeholder="请描述实习收获与不足" />
            <div class="sp-fieldlabel">存在问题</div><textarea v-model.trim="evalForm.problems" class="sp-inp" style="margin-bottom:12px" placeholder="实习中遇到的问题与改进方向" />
            <div class="score-grid" style="margin-bottom:12px">
              <label><span class="sp-fieldlabel">对企业评分</span><select v-model.number="evalForm.enterpriseRating" class="sp-inp"><option :value="null">请选择</option><option v-for="n in 5" :key="'e'+n" :value="n">{{ n }} 分</option></select></label>
              <label><span class="sp-fieldlabel">对岗位评分</span><select v-model.number="evalForm.positionRating" class="sp-inp"><option :value="null">请选择</option><option v-for="n in 5" :key="'p'+n" :value="n">{{ n }} 分</option></select></label>
            </div>
            <div class="sp-fieldlabel">对企业评价</div><textarea v-model.trim="evalForm.enterpriseFeedback" class="sp-inp" style="margin-bottom:12px" placeholder="可填写企业管理、培养和保障体验" />
            <div class="sp-fieldlabel">对岗位评价</div><textarea v-model.trim="evalForm.positionFeedback" class="sp-inp" style="margin-bottom:12px" placeholder="可填写岗位内容与专业匹配体验" />
            </fieldset>
            <button v-if="evalCanEdit" class="sp-btn" :disabled="busy || evalForm.performance.trim().length<20" @click="submitSelfEval">{{ selfEvalMeta?.id ? '修改并重新提交自评' : '提交自评' }}</button>
            <p v-else-if="selfEvalMeta?.reviewStatus==='APPROVED'" class="sp-muted">自评已通过学校审核，当前只读。</p>
            <p v-else-if="selfEvalMeta?.id && !evalConflict" class="sp-muted">当前自评正在审核，请等待处理结果。</p>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">成绩与申诉</div>
            <template v-if="my.score">
              <div style="display:flex;align-items:baseline;gap:10px;margin-bottom:10px">
                <div style="font-size:32px;font-weight:700;color:var(--pri)">{{ my.score.totalScore ?? '—' }}</div>
                <StatusTag v-if="my.score.gradeLevel" :text="my.score.gradeLevel" tone="warn" />
                <StatusTag :text="my.score.isPass ? '合格' : '不合格'" :tone="my.score.isPass ? 'success' : 'danger'" />
              </div>
              <p class="sp-muted" style="margin-bottom:8px">企业评价分只读取当前正式安置下已审核的企业在线评价或学校代录纸质证据；等次为百分制派生展示。</p>
              <dl class="score-grid">
                <div><dt>打卡</dt><dd>{{ my.score.checkinScore ?? '—' }}</dd></div>
                <div><dt>周报</dt><dd>{{ my.score.weeklyScore ?? '—' }}</dd></div>
                <div><dt>月报/总结</dt><dd>{{ my.score.monthlyScore ?? '—' }}</dd></div>
                <div><dt>企业评价</dt><dd>{{ my.score.enterpriseScore ?? '—' }}</dd></div>
                <div><dt>指导教师</dt><dd>{{ my.score.schoolScore ?? '—' }}</dd></div>
              </dl>
              <p class="sp-muted" style="margin-top:8px">发布时间：{{ fmt(my.score.publishedAt) }}</p>
            </template>
            <p v-else class="sp-muted">综合成绩由企业导师、指导教师、周月报打卡按权重生成，发布后可在此查看。</p>
            <div v-if="appealMeta?.hasAppeal" class="notebox" style="margin-top:14px">
              最近申诉：{{ appealMeta.statusLabel || '待确认' }}
              <span v-if="appealMeta.status === 'APPROVED_RECALCULATING'"> · 原成绩已撤回，学校正在重新核算</span>
              <span v-else-if="appealMeta.status === 'CLOSED'"> · 新成绩已重新发布</span>
            </div>
            <div class="sp-fieldlabel" style="margin-top:14px">成绩申诉理由</div>
            <textarea v-model.trim="appealReason" class="sp-inp" style="margin-bottom:12px" placeholder="对成绩有异议？请说明理由" />
            <button class="sp-btn sp-btn--ghost"
              :disabled="busy || !appealReason || !my.score || ['PENDING','APPROVED_RECALCULATING'].includes(appealMeta?.status)"
              @click="submitAppeal">提交成绩申诉</button>
          </section>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup>
import { INTERNSHIP_TABS as tabs, INTERNSHIP_TAB_GROUPS as tabGroups } from '../../modules/internshipRecruitment/navigation.js'
import { internshipLeaveStage } from '../../services/internshipPresentation.js'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import InternshipConsentPanel from './InternshipConsentPanel.vue'
import AutoTable from '../../components/AutoTable.vue'
import AppDatePicker from '../../components/AppDatePicker.vue'
import FlowSteps from '../../components/FlowSteps.vue'
import { portalApi } from '../../services/portalApi'
import { internshipCoreApi } from '../../services/internshipCoreApi'
import { currentSessionGeneration, fetchFileBlob } from '../../services/request'
import fileSdk from '../../services/fileSdk'
import { scanState, scanFilesReady, refreshScanFiles } from '../../services/fileScanState'
import { useSessionStore } from '../../stores/session'
import { useUiStore } from '../../stores/ui'
import { systemConfirm } from '../../services/systemDialog'

const ui = useUiStore()
const session = useSessionStore()
const route = useRoute()
const router = useRouter()

const tab = ref('overview')
const reportTab = ref('周报')
const reportTabs = ['日报', '周报', '月报', '实习总结']
const currentMonth = () => {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const my = ref({})
const overviewLoading=ref(false),overviewError=ref('')
let overviewSequence=0
const sourceStates = reactive(Object.fromEntries(tabs.map((item) => [item.key, {
  label: item.label, status: 'idle', message: '',
}])))
const currentSource = computed(() => sourceStates[tab.value] || { label: '当前内容', status: 'idle', message: '' })
const INTERNSHIP_BATCH_KEY = 'student_portal_internship_batch_v1'
const selectedBatchId = ref('')
const internshipCandidates = ref([])
const weeklyForm = reactive({ week: null, workContent: '', harvestContent: '', planContent: '', attachments: [] })
const reportForm = reactive({ periodKey: currentMonth(), content: '', attachments: [] })
const reportRules = ref({
  dailyMinWords: 30, weeklyMinWords: 30, monthlyMinWords: 100, summaryMinWords: 300,
  dailyRequiredCount: 0, weeklyRequiredCount: 0, monthlyRequiredCount: 0, summaryRequiredCount: 1
})
const REPORT_DRAFT_KEY = 'student_portal_report_draft_v1'
let reportDraftContext = ''
let reportDraftGeneration = 0
const reportReceipt = ref(null)
const reportError = ref('')
const weeklyBase = ref(null), processBase = ref(null)
const weeklyConflict = ref(false), processConflict = ref(false)
const weeklyDetail = ref(null), weeklyReading = ref(false)
const processDetail = ref(null), processReading = ref(false)
const processLatest = ref(null)
const reportKinds = ['WEEKLY', 'DAILY', 'MONTHLY', 'SUMMARY']
const reportPages = reactive(Object.fromEntries(reportKinds.map(kind => [kind, { page: 1, total: null, hasMore: false }])))
const reportMoreBusy = ref(false)
const reportReadMode = ref(false)
const processDrafts = reactive({})
let processDraftKind = 'MONTHLY', reportFocusTarget = ''
let reportMoreSequence = 0
const weeklyFields = [{ key: 'workContent', label: '本周工作内容' }, { key: 'harvestContent', label: '收获与体会' }, { key: 'planContent', label: '下周计划' }]
let reportEpoch = 0, weeklyReadSequence = 0, processReadSequence = 0, reportSourceSequence = 0
let attachmentEpoch = 0
const pendingInsuranceFile = ref(null)
const weeklyExisting = computed(() => (my.value.weeklyReports || []).find(item => Number(item.weekNo || item.week) === Number(weeklyForm.week)))
const weeklyEditing = computed(() => !!weeklyBase.value && Number(weeklyBase.value.weekNo || weeklyBase.value.week) === Number(weeklyForm.week))
const processType = computed(() => ({
  '日报': 'DAILY',
  '月报': 'MONTHLY',
  '实习总结': 'SUMMARY'
})[reportTab.value] || 'MONTHLY')
const processReportRows = computed(() => (my.value.processReports || []).filter((item) => item.reportType === processType.value))
const processEditing = computed(() => !!processBase.value && processBase.value.reportType === processType.value
  && processBase.value.periodKey === (processType.value === 'SUMMARY' ? 'FINAL' : reportForm.periodKey))
const processExisting = computed(() => processReportRows.value.find(row => row.periodKey === (processType.value === 'SUMMARY' ? 'FINAL' : reportForm.periodKey)))
const reportMinimum = computed(() => ({
  DAILY: Number(reportRules.value.dailyMinWords ?? 30),
  MONTHLY: Number(reportRules.value.monthlyMinWords ?? 100),
  SUMMARY: Number(reportRules.value.summaryMinWords ?? 300)
})[processType.value] ?? 30)
const weeklyWordCount = computed(() =>
  weeklyForm.workContent.trim().length + weeklyForm.harvestContent.trim().length + weeklyForm.planContent.trim().length)
const weeklyCanSubmit = computed(() =>
  !!my.value.hasData && !my.value.historyMode && !weeklyConflict.value
  && ['data', 'empty'].includes(sourceStates.report.status)
  && (!weeklyExisting.value || weeklyEditing.value)
  && Number.isInteger(Number(weeklyForm.week)) && Number(weeklyForm.week) >= 1
  && weeklyForm.workContent.trim().length >= 1
  && weeklyForm.harvestContent.trim().length >= 1
  && weeklyFields.every(field => weeklyForm[field.key].trim().length <= 2000)
  && weeklyWordCount.value >= Number(reportRules.value.weeklyMinWords ?? 30))
const reportCanSubmit = computed(() => !!my.value.hasData && !my.value.historyMode && !processConflict.value
  && ['data', 'empty'].includes(sourceStates.report.status)
  && (!processExisting.value || processEditing.value)
  && (processType.value === 'SUMMARY' || !!reportForm.periodKey) && reportForm.content.trim().length > 0 && reportForm.content.trim().length >= reportMinimum.value)
const reportEditorTitle = computed(() => reportTab.value === '周报'
  ? (weeklyEditing.value ? `第 ${weeklyForm.week} 周 · 修改重交` : '填写周报')
  : (processEditing.value ? `${reportTab.value} · 修改重交` : `填写${reportTab.value}`))
const reportPlaceholder = computed(() => processType.value === 'SUMMARY'
  ? '建议按“岗位与职责、主要成果、能力提升、不足与改进”分段填写。'
  : processType.value === 'DAILY'
    ? '记录当天岗位工作、学习收获、问题与改进。'
    : '建议按“本月工作、主要成果、能力提升、问题与下月计划”分段填写。')
const evalForm = reactive({ performance: '', reflection: '', problems: '', enterpriseRating: null,
  enterpriseFeedback: '', positionRating: null, positionFeedback: '' })
const leaveForm = reactive({ leaveType: 'SICK', startDate: '', endDate: '', reason: '', evidenceFileId: '', fileName: '' })
const leaves = ref([])
const leaveReceipt = ref(null)
const leaveError = ref('')
const leaveBase = ref(null), leaveDetail = ref(null), leaveConflict = ref(false), leaveFile = ref(null), leaveReading = ref(false)
const leaveConflictRead = ref(false)
const leaveHasDraft = computed(() => !!(leaveBase.value || leaveForm.startDate || leaveForm.endDate || leaveForm.reason.trim() || leaveForm.evidenceFileId || leaveFile.value))
let leaveEpoch = 0, leaveSourceSequence = 0, leaveReadSequence = 0, leaveOperation = 0
const returnDraft = reactive({ id: '', note: '', version: null, conflict: false })
const makeupForm = reactive({ checkinDate: '', reason: '', makeupType: 'MISSING', evidenceFileId: '', fileName: '' })
const makeups = ref([])
const makeupReceipt = ref(null)
const makeupError = ref('')
const intentionForm = reactive({ preferredCity: '', preferredIndustry: '', intentionNote: '' })
const intentionMeta = ref({})
const intentionFlags = ref({ canEdit: false, canSubmit: false, canWithdraw: false })
const intentionReason = ref(''), intentionBusy = ref(false), intentionError = ref(''), intentionReceipt = ref('')
const intentionConflict = ref(false), intentionLatest = ref(null), intentionCommitted = ref(false)
let intentionEpoch = 0, intentionSourceSequence = 0
const applicationOptions = {
  companyScale:['微型','小型','中型','大型','其他'],
  companyNature:['国有企业','民营企业','外商投资企业','港澳台投资企业','集体企业','事业单位','社会组织','其他'],
  companyIndustry:['农林牧渔','制造业','建筑业','信息传输/软件/信息技术','批发和零售','交通运输/仓储/邮政','住宿和餐饮','金融业','教育','卫生和社会工作','文化/体育/娱乐','公共管理/社会保障','其他'],
  positionCategory:['生产操作','技术研发','工程技术','信息技术','运营','管理','市场销售','客户服务','行政支持','教育教学','其他'],
  internshipMode:['集中实习','自主实习','认识实习','岗位实习','其他']
}
const appFields = [
  ['companyName','企业名称',200,2],['companyCreditCode','统一社会信用代码',18,18],['companyPrincipal','企业负责人',100,2],
  ['companyScale','企业规模',50,1],['companyPhone','企业联系电话',64,7],['companyEmail','企业邮箱',200,3],
  ['companyNature','单位性质',50,1],['companyIndustry','所属行业',100,1],['companyProvince','单位所在省',50,1],
  ['companyCity','单位所在市',50,1],['companyDistrict','单位所在区县',50,1],['companyRegisteredAddress','单位注册地址',300,5],
  ['companyPostalCode','邮编（选填）',20,0],['contactName','单位联系人',100,2],['contactPhone','联系人电话',64,7],
  ['internshipDepartment','实习部门或科室',100,1],['positionName','实习岗位',100,2],['positionCategory','岗位类别',50,1],
  ['workContent','工作内容',4000,5],['enterpriseMentorName','企业带教老师',100,2],['enterpriseMentorPhone','企业老师电话',64,7],
  ['workCountry','实习国家或地区（选填）',100,0],['workProvince','岗位所在省',50,1],['workCity','岗位所在市',50,1],
  ['workDistrict','岗位所在区县',50,1],['workAddress','岗位详细地址',300,5],
  ['internshipStartDate','实习开始日期',10,1],['internshipEndDate','实习结束日期',10,1],['internshipMode','实习方式',30,1]
].map(([key,label,max,min])=>({key,label,max,min,options:applicationOptions[key],type:key.endsWith('Date')?'date':key==='companyEmail'?'email':'text'}))
const exemptionTypes=[{value:'FURTHER_STUDY',label:'升学'},{value:'MILITARY',label:'参军入伍'},{value:'HEALTH',label:'健康原因'},{value:'OTHER',label:'其他'}]
function blankApplication(type='SELF_ARRANGED') { return {...Object.fromEntries(appFields.map(field=>[field.key,''])),applicationType:type,positionId:'',applicationNote:'',majorMatch:null,agreedSalary:'',evidenceFileId:'',agreementFileIds:[],exemptionType:'',exemptionDestination:'',exemptionReason:''} }
const appForm = reactive(blankApplication())
const applications = ref([])
const appBase=ref(null),appLatest=ref(null),appConflict=ref(false),appError=ref(''),appReceipt=ref(''),appBusy=ref(false),appReading=ref(false),appFiles=ref([])
const appPositions=ref([]),appPositionsTotal=ref(0),appPositionsMore=ref(false),appPositionsLoading=ref(false),appPositionsError=ref('')
const enterprisePage=ref(1),enterpriseMore=ref(false),enterpriseTotal=ref(0)
let appPositionsPage=1
let appEpoch=0,appListSequence=0
const applicationEditableStatuses=['DRAFT','REJECTED','WITHDRAWN']
const appWritable=computed(()=>['data','empty'].includes(sourceStates.application.status) && !!my.value.hasData && !my.value.historyMode && ['PREPARING','READY'].includes(my.value.status) && !['ASSIGNED','SELF_ARRANGED','EXEMPTED'].includes(my.value.destinationType) && ['POSITION','SELF_ARRANGED','EXEMPTION'].includes(appForm.applicationType) && (!appBase.value || applicationEditableStatuses.includes(appBase.value.status)))
const appPlaced=computed(()=>!!my.value.hasData && (!['PREPARING','READY'].includes(my.value.status) || ['ASSIGNED','SELF_ARRANGED','EXEMPTED'].includes(my.value.destinationType)))
const applicationHistoryOpen=ref(false), insuranceProofBusy=ref(false)
const insuranceProof=ref(null)
let insuranceProofSequence = 0
const appAttachmentIds=computed(()=>[appForm.evidenceFileId,...appForm.agreementFileIds].filter(Boolean).map(String))
const appAttachmentsReady=computed(()=>appAttachmentIds.value.every(id=>appFiles.value.some(file=>String(file.fileId)===id && file.readyForBusiness===true)))
const changeForm = reactive({
  changeType: 'CHANGE_POSITION', reason: '', targetPositionId: '',
  targetEnterpriseName: '', targetPositionName: ''
})
const changes = ref([])
const changeEditing = ref(null)
const changeReceipt = ref(null)
const changeError = ref('')
const changeBusy = ref(false)
const changeTargets = ref([])
const changeSelectedTarget = ref(null)
const changeKeyword = ref('')
const changeTargetLoading = ref(false)
const changeTargetError = ref('')
const changeTargetPage = ref(1)
const changeTargetMore = ref(false)
const changeHistoryPage = ref(1)
const changeHistoryMore = ref(false)
let changeEpoch = 0, changeTargetSequence = 0, changeHistorySequence = 0, loadSequence = 0
let changeAlive = true
const changeNeedsTarget = computed(() => ['CHANGE_POSITION', 'CHANGE_ENTERPRISE'].includes(changeForm.changeType))
const changeWritable = computed(() => !!my.value.hasData && !my.value.historyMode && ['PREPARING', 'READY', 'ONBOARD', 'ASSESSING'].includes(my.value.status))
const changeStatusLabel = status => ({ PENDING: '待教师审核', APPROVED: '已通过', REJECTED: '已退回，请补正', WITHDRAWN: '已撤回' })[status] || '状态待核对'
const changeTypeLabel = type => ({ CHANGE_POSITION: '换岗', CHANGE_ENTERPRISE: '换实习单位', SELF_ARRANGED: '转自主实习', WITHDRAW_POST: '退岗' })[type] || '变更类型待核对'
function changeErrorText(e) {
  if (e?.bizCode === 'DATA_CONFLICT' || Number(e?.code) === 409001) return '申请或岗位已变化，填写内容和原版本已保留，请重新读取后核对'
  if ([403001, 403002].includes(Number(e?.code))) return '暂无办理权限，请联系学校管理员'
  return '操作未完成，填写内容已保留，请检查网络或稍后重试'
}
function changeCurrent(epoch, generation, ctx) {
  return changeAlive && epoch === changeEpoch && generation === currentSessionGeneration()
    && String(ctx.batchId) === String(my.value.batchId)
    && String(ctx.internshipId) === String(my.value.recordId || my.value.internshipId)
}
function resetChangeDraft() {
  changeEditing.value = null; changeError.value = ''; changeReceipt.value = null
  Object.assign(changeForm, { reason: '', targetPositionId: '', targetEnterpriseName: '', targetPositionName: '' })
  changeSelectedTarget.value = null
}
function selectChangeTarget() { if (!changeBusy.value) changeSelectedTarget.value = changeTargets.value.find(item => String(item.positionId) === String(changeForm.targetPositionId) && item.canSelect === true) || null }
function cancelChangeEditing() { if (!changeBusy.value) resetChangeDraft() }
async function loadChangeTargets(page = 1) {
  if (!my.value.hasData || !changeNeedsTarget.value) return
  const ctx = currentInternshipContext(), epoch = changeEpoch, generation = currentSessionGeneration()
  const type = changeForm.changeType, keyword = changeKeyword.value, seq = ++changeTargetSequence
  const current = () => changeCurrent(epoch, generation, ctx) && seq === changeTargetSequence && type === changeForm.changeType
  changeTargetLoading.value = true; changeTargetError.value = ''
  try {
    const data = await internshipCoreApi.changeTargets(ctx, type, keyword, page)
    if (!current()) return
    changeTargets.value = rowsFrom(data); changeTargetPage.value = page; changeTargetMore.value = !!data?.hasMore
  } catch (e) { if (current()) changeTargetError.value = changeErrorText(e) }
  finally { if (current()) changeTargetLoading.value = false }
}
async function changeTypePicked() {
  if (changeBusy.value || changeEditing.value) return
  changeTargetSequence++; changeForm.targetPositionId = ''; changeSelectedTarget.value = null; changeTargets.value = []; changeKeyword.value = ''
  changeForm.targetEnterpriseName = ''; changeForm.targetPositionName = ''; changeTargetError.value = ''
  if (changeNeedsTarget.value) await loadChangeTargets(1)
}
async function loadChanges(page = 1) {
  const ctx = currentInternshipContext(), epoch = changeEpoch, generation = currentSessionGeneration(), seq = ++changeHistorySequence
  const current = () => changeCurrent(epoch, generation, ctx) && seq === changeHistorySequence
  try {
    const data = await internshipCoreApi.changes(ctx, page); if (!current()) return
    changes.value = rowsFrom(data).map(item => ({ ...item, statusLabel: changeStatusLabel(item.status), changeTypeLabel: changeTypeLabel(item.changeType) }))
    changeHistoryPage.value = page; changeHistoryMore.value = !!data?.hasMore
  } catch (e) { if (current()) changeError.value = changeErrorText(e) }
}
function editChange(item) {
  if (!changeWritable.value || changeBusy.value || busy.value || item.status !== 'REJECTED') return
  resetChangeDraft(); changeEditing.value = { id: String(item.id), version: item.version, reviewComment: item.reviewComment || '' }
  Object.assign(changeForm, { changeType: item.changeType, reason: item.reason || '', targetEnterpriseName: item.targetEnterpriseName || '', targetPositionName: item.targetPositionName || '' })
  changeTargets.value = []; changeKeyword.value = ''; if (changeNeedsTarget.value) loadChangeTargets(1)
}
const agreements = ref([])
const activeAgreement = ref(null)
const agreementDetail = ref(null), agreementReading = ref(false), agreementBusy = ref(false)
const agreementReason = ref(''), agreementError = ref(''), agreementConflict = ref(false), agreementReceipt = ref(null)
let agreementSequence = 0
const enterpriseCity = ref('')
const enterprises = ref([])
const insForm = reactive({
  policyNo: '', insurerName: '', coverageType: '', effectiveDate: '', expiryDate: '', fileId: ''
})
const insuranceMeta = ref(null)
const insuranceError = ref(''), insuranceConflict = ref(false)
const insuranceReadOnly = computed(() => !['data','empty'].includes(sourceStates.insurance.status) || !!my.value.historyMode || (insuranceMeta.value?.status === 'VERIFIED' && insuranceMeta.value.canRenew !== true))
let insuranceEpoch = 0
const attendance = ref({ summary: { CHECKIN:0, ABSENT:0, LEAVE:0, MAKEUP:0, EXEMPT:0 }, items: [], totalCountedDays: 0 })
const notices = ref([])
const planMeta = ref(null)
const planAssignments = ref([])
const selectedPlanId = ref('')
const planTasks = ref([])
const planTaskSummary = ref({ total: 0, approved: 0, rate: 0 })
const planTaskMinimumWords = ref(10)
const planHasDraft = computed(() => planTasks.value.some(task =>
  !['APPROVED','SUBMITTED'].includes(task.progressStatus) && (
    String(task._note || '') !== String(task.progressStatus === 'REJECTED' ? task.studentNote || '' : '') ||
    String(task._evidenceFileId || '') !== String(task.evidenceFileId || ''))))
let planSourceSequence = 0
const helpForm = reactive({ title: '', content: '', riskLevel: 'MEDIUM' })
const helpRows=ref([]),helpBusy=ref(false),helpError=ref(''),helpReceipt=ref(null),helpCommitted=ref(false)
let helpEpoch=0,helpReadSequence=0
const helpHasOpen=computed(()=>helpRows.value.some(row=>!['RESOLVED','CLOSED'].includes(row.status)))
const helpCanSubmit=computed(()=>!!my.value.hasData && !my.value.historyMode && !helpBusy.value && !helpCommitted.value && !helpHasOpen.value && ['data','empty'].includes(sourceStates.help.status) && ['LOW','MEDIUM','HIGH'].includes(helpForm.riskLevel) && helpForm.content.trim().length>=5)
const appealReason = ref('')
const appealMeta = ref(null)
const selfEvalMeta = ref(null)
const evalBaseline = ref(''),evalScope=ref(''),evalConflict=ref(false)
let evalSourceSequence=0
const evalCanEdit = computed(()=>!!my.value.hasData&&!my.value.historyMode&&['data','empty'].includes(sourceStates.eval.status)&&!evalConflict.value&&selfEvalMeta.value?.reviewStatus!=='APPROVED'&&!(selfEvalMeta.value?.submitStatus==='SUBMITTED'&&selfEvalMeta.value?.reviewStatus==='PENDING'))
const evalReceipt = ref(null)
const formalDocuments = ref([])

const STATUS_MAP = { ONBOARD: '实习中', PENDING: '待入职', ENDED: '已结束', PAUSED: '暂停', READY: '待上岗', PREPARING: '准备中', ASSESSING: '考核中', ARCHIVED: '已归档' }
const RISK_MAP = { NONE: '无', LOW: '低', MEDIUM: '中', HIGH: '高', MID: '中' }
const REVIEW_MAP = { PENDING_REVIEW: '待审阅', APPROVED: '已通过', REJECTED: '已退回', RETURNED: '已退回' }
const AGREEMENT_MAP = {
  DRAFT: '草稿', PENDING_STUDENT: '待学生确认', PENDING_ENTERPRISE: '待企业确认',
  PENDING_SCHOOL: '待学校确认', EFFECTIVE: '已生效', REJECTED: '已驳回', VOIDED: '已作废', ARCHIVED: '已归档'
}
function statusText(s) { return STATUS_MAP[s] || s || '—' }
function riskText(s) { return RISK_MAP[s] || s || '—' }
function noticeTypeText(value) {
  return ({ AGREEMENT: '实习协议', TRAINING: '岗前培训', SAFETY: '安全条例', NOTICE: '通知公告', OTHER: '其他' })[String(value || '').toUpperCase()] || '通知公告'
}
function noticeUrgencyText(value) {
  return ({ NORMAL: '普通', IMPORTANT: '重要', URGENT: '紧急' })[String(value || '').toUpperCase()] || '普通'
}
async function openNoticeAttachment(file) {
  try {
    const blob = await fileSdk.fetchPreviewBlob(String(file.fileId))
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank', 'noopener,noreferrer')
    setTimeout(() => URL.revokeObjectURL(url), 60000)
  } catch (e) {
    ui.notify(e?.message || '通知附件暂时无法打开')
  }
}
function reviewText(s) { return REVIEW_MAP[s] || '状态待核实' }
function noticeDate(value) {
  if (!value) return '不限'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
}
function fmt(t) {
  if (!t) return '—'
  const date = new Date(t)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })
}
const agreementLabel = value => AGREEMENT_MAP[value] || '状态待学校核实'
const agreementStatusText = computed(() => activeAgreement.value ? agreementLabel(agreementDetail.value?.status || activeAgreement.value.status) : '未下发')
const agreementTone = computed(() => agreementDetail.value?.status === 'EFFECTIVE' ? 'success' : ['REJECTED', 'VOIDED'].includes(agreementDetail.value?.status) ? 'danger' : 'warn')
const agreementCanPrint = computed(() => !busy.value && !agreementBusy.value && !agreementReading.value && !agreementConflict.value && !!agreementDetail.value?.renderedBody?.trim() && Object.hasOwn(AGREEMENT_MAP, agreementDetail.value.status))
const agreementCanAct = computed(() => agreementCanPrint.value && !my.value.historyMode && agreementDetail.value.status === 'PENDING_STUDENT' && sourceStates.agreement.status === 'data')
const intentionReady = computed(() => ['data','empty'].includes(sourceStates.intention.status) && !my.value.historyMode && !intentionConflict.value && !intentionCommitted.value)
const intentionCanEdit = computed(() => intentionReady.value && intentionFlags.value.canEdit === true)
const intentionCanSubmit = computed(() => intentionReady.value && intentionFlags.value.canSubmit === true)
const intentionCanWithdraw = computed(() => intentionReady.value && intentionFlags.value.canWithdraw === true)
const intentionDirty = computed(() => ['preferredCity','preferredIndustry','intentionNote'].some(key => intentionForm[key] !== (intentionMeta.value[key] || '')))
const makeupEvidenceRequired = computed(() => makeupForm.makeupType === 'OUT_OF_RANGE')
const makeupCanSubmit = computed(() => !!makeupForm.checkinDate
  && makeupForm.reason.trim().length >= 5
  && (!makeupEvidenceRequired.value || !!makeupForm.evidenceFileId))
const leaveDays = computed(() => {
  if (!leaveForm.startDate || !leaveForm.endDate) return 0
  const start = Date.parse(`${leaveForm.startDate}T00:00:00Z`)
  const end = Date.parse(`${leaveForm.endDate}T00:00:00Z`)
  return Number.isFinite(start) && Number.isFinite(end) && end >= start ? Math.floor((end - start) / 86400000) + 1 : 0
})
const leaveEvidenceRequired = computed(() => leaveForm.leaveType === 'SICK' || leaveDays.value >= 3)
const leaveEvidenceHint = computed(() => leaveForm.leaveType === 'SICK'
  ? '病假必须上传医疗或就诊证明'
  : leaveDays.value >= 3 ? '连续3天及以上请假必须上传证明' : '短期事假可按学校要求选传证明')
const leaveWritable = computed(() => !!my.value.hasData && !my.value.historyMode && ['ONBOARD', 'ASSESSING'].includes(my.value.status)
  && ['data', 'empty'].includes(sourceStates.leave.status))
const leaveCanSubmit = computed(() => leaveWritable.value && !leaveReading.value && !leaveConflict.value && (!leaveFile.value || leaveFile.value.readyForBusiness === true)
  && !!leaveForm.startDate && !!leaveForm.endDate && leaveDays.value > 0
  && leaveForm.reason.trim().length >= 2 && leaveForm.reason.trim().length <= 500 && (!leaveEvidenceRequired.value || !!leaveForm.evidenceFileId))

const qualification = computed(() => my.value.eligibilityReview || { status: 'UNKNOWN', label: '暂未取得认定结果', reason: '' })
const qualificationHint = computed(() => ({
  QUALIFIED: '学校已认定本批次实习资格合格。',
  UNQUALIFIED: '本次资格认定未通过，请联系指导教师了解后续安排。',
  PENDING: '学校正在核对本批次实习资格，请关注认定进度。'
})[qualification.value.status] || '请刷新结果；暂时无法取得时，可联系指导教师核对。')
const currentAction = computed(() => {
  if (my.value.historyMode) return {
    tab: 'overview', title: '查看本次实习记录', action: '查看实习概况',
    reason: my.value.status === 'ARCHIVED' ? '该实习已归档，可查看本次安排与已保存结果。' : '当前记录仅可查看，是否开放办理以学校批次安排和实际状态为准。',
    recentChange: `当前状态：${statusText(my.value.status)}（只读）`, nextActor: '如需核对资料，请联系指导教师'
  }
  if (['PREPARING','READY'].includes(my.value.status) && ['PENDING', 'UNQUALIFIED', 'UNKNOWN'].includes(qualification.value.status)) return {
    tab: 'overview', title: qualification.value.status === 'UNQUALIFIED' ? '查看资格认定说明' : '关注实习资格认定', action: '查看资格结果',
    reason: qualification.value.reason || qualificationHint.value,
    recentChange: qualification.value.reviewedAt ? fmt(qualification.value.reviewedAt) : '尚无认定时间',
    nextActor: '由学校经办人核对资格并更新结果'
  }

  if (my.value.destinationType === 'EXEMPTED') return {
    tab: 'application', title: '本批次免实习已批准', action: '查看免实习原申请',
    reason: '学校已审核落实本批次免实习，可以查看原申请、佐证和办理意见。',
    recentChange: '实习去向已标记为免实习', nextActor: '后续事项按学校安排办理'
  }
  if (my.value.status === 'PREPARING' && !my.value.positionName && (!my.value.destinationType || my.value.destinationType === 'NONE')) return {
    tab: 'selection', title: '落实本批次实习岗位', action: '查看招聘季与岗位',
    reason: '实习资格已合格。可查看学校发布的岗位，按本批次安排填写意向或提交申请。',
    recentChange: '岗位尚未落实', nextActor: '学校与企业审核申请后确认实习去向'
  }

  const currentAgreement = agreements.value.find(item => String(item.internId) === String(my.value.recordId || my.value.internshipId) && String(item.batchId) === String(my.value.batchId))
  const agreementStatus = sourceStates.agreement.status === 'data' ? currentAgreement?.status : sourceStates.agreement.status === 'idle' ? my.value.agreementStatus : ''
  if (agreementStatus === 'PENDING_STUDENT') return {
    tab: 'agreement', title: '确认三方协议', action: '核对并确认',
    reason: '协议正在等待你确认。请先核对学校、企业、岗位和纸质签署来源，再决定确认或驳回。',
    recentChange: currentAgreement?.updatedAt ? fmt(currentAgreement.updatedAt) : '协议已进入学生确认节点',
    nextActor: '确认后交由企业或学校继续办理；驳回则返回经办人修正'
  }
  if (sourceStates.insurance.status === 'empty' && ['PREPARING', 'READY'].includes(my.value.status)) return {
    tab: 'insurance', title: '补齐实习保险', action: '提交保险信息',
    reason: '当前实习记录还没有可核验的保险信息，上岗前需要补齐保单与有效期。',
    recentChange: '尚未取得有效保险记录', nextActor: '提交后等待学校核验'
  }
  if (sourceStates.plan.status === 'data' && planMeta.value?.id && !['ACKNOWLEDGED', 'CONFIRMED'].includes(planMeta.value.ackStatus || planMeta.value.status)) return {
    tab: 'plan', title: '确认实习计划', action: '查看计划',
    reason: '学校已下发实习计划，确认前请阅读任务、时间和指导要求。',
    recentChange: planMeta.value.updatedAt ? fmt(planMeta.value.updatedAt) : '计划已下发',
    nextActor: '确认后进入在岗执行与过程记录'
  }
  if (['PREPARING', 'READY'].includes(my.value.status)) return {
    tab: 'safety', title: '继续完成上岗准备', action: '核对上岗条件与安全教育',
    reason: '请按学校安排核对协议、保险和岗前要求，等待学校确认上岗。',
    recentChange: statusText(my.value.status), nextActor: '学校核验条件并确认上岗后，开始考勤与过程记录'
  }
  if (my.value.status === 'ONBOARD' && !my.value.todayCheckin?.done) return {
    tab: 'checkin', title: '完成今日打卡', action: '去打卡',
    reason: '今天尚未留下出勤记录。电脑端可登记打卡，精确地理围栏核验仍在学生小程序完成。',
    recentChange: `累计出勤 ${my.value.todayCheckin?.totalDays ?? 0} 天`,
    nextActor: '打卡后形成系统时间记录；异常只作为人工核实信号'
  }
  if (my.value.score) return {
    tab:'eval',title:'查看最终成绩',action:'查看成绩',reason:'学校已发布正式成绩，可核对总分、各分项和已审核鉴定。',
    recentChange:my.value.score.publishedAt?fmt(my.value.score.publishedAt):'正式成绩已发布',nextActor:'核对后保留结果；如有异议，可向学校提交成绩申诉'
  }
  if (my.value.status==='ASSESSING'&&selfEvalMeta.value?.id&&selfEvalMeta.value.reviewStatus!=='RETURNED') return {
    tab:'eval',title:selfEvalMeta.value.reviewStatus==='APPROVED'?'等待学校发布成绩':'查看自评审核进度',action:'查看办理进度',
    reason:'当前自评已提交，无需重复填写。',recentChange:selfEvalMeta.value.reviewStatusLabel||'等待审核',nextActor:'指导教师与学校继续审核、核分和发布'
  }
  if (my.value.status === 'ASSESSING') return {
    tab: 'eval', title: '查看自评与考核进度', action: '查看考核进度',
    reason: '实习已进入考核评价阶段，请打开本人的自评与学校审核结果，按当前状态继续办理。',
    recentChange: '实习状态已进入考核中', nextActor: '提交后等待指导教师与学校审核'
  }
  return {
    tab: 'report', title: '继续记录实习过程', action: '写周报 / 总结',
    reason: '岗位与上岗条件已建立，下一步是持续提交周报、月报和实习总结。',
    recentChange: reportPages.WEEKLY.total == null ? '周报总数暂未取得' : `已提交 ${reportPages.WEEKLY.total} 篇周报`,
    nextActor: '提交后等待指导教师批阅；退回后按原因修订重交'
  }
})

function insuranceHasDraft() {
  return !!pendingInsuranceFile.value || insuranceConflict.value || Object.keys(insForm).some(key =>
    String(insForm[key] ?? '') !== String(insuranceMeta.value?.[key] ?? ''))
}
function activeGroupLabel(group) {
  return group.tabs.find((item) => item.key === tab.value)?.label || `${group.tabs.length} 项`
}
function groupOpen(group) {
  return group.tabs.some((item) => item.key === tab.value)
}
function selectTab(key) {
  if (!tabs.some((item) => item.key === key)) return
  const path = ({enterprises:'/internship/selection',selection:'/internship/selection',profile:'/internship/profile',safety:'/internship/compliance',materials:'/internship/materials'})[key]
  if (path) { router.push({path,query:my.value.batchId ? {batchId:String(my.value.batchId)} : {}}); return }
  tab.value = key
  router.replace({ query: { ...route.query, view: key } })
  if (my.value.hasData) loadTab(key, key === 'agreement' || (key === 'insurance' && !insuranceHasDraft()))
}

watch(() => route.query.view, (value) => {
  if (typeof value === 'string' && tabs.some((item) => item.key === value)) {
    tab.value = value
    if (my.value.hasData) loadTab(value, value === 'agreement' || (value === 'insurance' && !insuranceHasDraft()))
  }
}, { immediate: true })

watch(tab, (value, previous) => {
  if (value === 'overview' && value !== previous) refreshProgress()
  if(previous==='help' && value!==previous){helpEpoch++;helpBusy.value=false;sourceStates.help.status='idle'}
  if (previous === 'insurance' && value !== previous) { insuranceProofSequence++; insuranceProofBusy.value = false; closeInsuranceProof() }
  if (previous === 'intention' && value !== previous) { intentionEpoch++; intentionBusy.value = false; sourceStates.intention.status = 'idle' }
  if (previous === 'application' && value !== previous) { applicationLeaving(); sourceStates.application.status = 'idle' }
  if (previous === 'leave' && value !== previous) { invalidateLeave(); sourceStates.leave.status = 'idle' }
  if (previous === 'report' && value !== previous) { reportEpoch++; weeklyReadSequence++; reportSourceSequence++; weeklyReading.value = false; busy.value = false; sourceStates.report.status = 'idle' }
  if (previous === 'agreement' && value !== previous) { agreementSequence++; agreementDetail.value = null; agreementReading.value = false; agreementBusy.value = false }
  if (value === 'agreement' && activeAgreement.value && !agreementDetail.value && !agreementReading.value) openAgreement(activeAgreement.value)
})
watch(() => route.query.batchId, (value, previous) => {
  if (['leave','application','report','intention'].includes(tab.value) && value !== previous && String(value)!==String(my.value.batchId) && my.value.hasData && /^\d+$/.test(String(value || ''))) load()
})
watch(() => [route.query.leaveId, tab.value, sourceStates.leave.status], () => {
  const id = String(route.query.leaveId || '')
  if (tab.value === 'leave' && /^\d+$/.test(id) && ['data', 'empty'].includes(sourceStates.leave.status)
    && String(leaveDetail.value?.id) !== id) {
    if (route.query.batchId && String(route.query.batchId) !== String(my.value.batchId)) leaveError.value = '请先选择原单所属实习批次'
    else openLeave({ id })
  }
})

function persistInternshipBatch(batchId) {
  const value = String(batchId || '').trim()
  selectedBatchId.value = /^\d+$/.test(value) ? value : ''
  try {
    if (selectedBatchId.value) sessionStorage.setItem(INTERNSHIP_BATCH_KEY, selectedBatchId.value)
    else sessionStorage.removeItem(INTERNSHIP_BATCH_KEY)
  } catch { /* storage unavailable */ }
}

async function selectInternshipBatch(batchId) {
  persistInternshipBatch(batchId)
  const query={...route.query,batchId:String(batchId)};delete query.reportId;delete query.reportType;delete query.leaveId
  await router.replace({query})
  await load()
}

async function changeInternshipBatch() {
  await selectInternshipBatch(selectedBatchId.value)
}

function currentInternshipContext() {
  const batchId = my.value.batchId
  const internshipId = my.value.recordId || my.value.internshipId
  if (!batchId || !internshipId) {
    throw new Error('当前实习批次上下文已失效，请刷新页面后重试')
  }
  return { batchId, internshipId }
}

const flowSteps = computed(() => {
  const order = ['实习准备', '待上岗', '在岗实习', '考核评价', '归档']
  const cur = { PREPARING: 0, READY: 1, ONBOARD: 2, ASSESSING: 3, ARCHIVED: 4, ENDED: 4 }[my.value.status] ?? -1
  return order.map((name, i) => ({ name, state: i < cur ? 'done' : i === cur ? 'current' : 'todo' }))
})
const attendanceChartStyle = computed(() => {
  const s = attendance.value?.summary || {}
  const values = [
    Number(s.CHECKIN || 0),
    Number(s.ABSENT || 0),
    Number(s.LEAVE || 0),
    Number(s.MAKEUP || 0),
    Number(s.EXEMPT || 0)
  ]
  const total = values.reduce((sum, value) => sum + value, 0)
  if (!total) return { background: 'var(--bg2)' }
  const colors = ['var(--ok-fg)', 'var(--danger-fg)', 'var(--warn-fg)', 'var(--pri)', 'var(--t4)']
  let start = 0
  const parts = values.map((value, index) => {
    const end = start + value * 100 / total
    const part = colors[index] + ' ' + start.toFixed(2) + '% ' + end.toFixed(2) + '%'
    start = end
    return part
  })
  return { background: 'conic-gradient(' + parts.join(',') + ')' }
})
const metrics = computed(() => [
  { t: '累计出勤', v: my.value.todayCheckin?.totalDays ?? 0, u: '天', c: 'var(--t1)' },
  { t: '周报数', v: reportPages.WEEKLY.total ?? '—', u: '篇', c: 'var(--t1)' },
  { t: '考勤异常', v: (my.value.attendanceExceptions || []).length, u: '次', c: (my.value.attendanceExceptions || []).length ? 'var(--warn-fg)' : 'var(--ok-fg)' },
  { t: '风险等级', v: riskText(my.value.riskLevel), u: '', c: my.value.riskLevel === 'HIGH' ? 'var(--danger-fg)' : 'var(--ok-fg)' }
])
const reportProgress = computed(() => {
  const current = [
    { key: 'daily', label: '日报', required: Number(reportRules.value.dailyRequiredCount || 0), submitted: reportPages.DAILY.total },
    { key: 'weekly', label: '周报', required: Number(reportRules.value.weeklyRequiredCount || 0), submitted: reportPages.WEEKLY.total },
    { key: 'monthly', label: '月报', required: Number(reportRules.value.monthlyRequiredCount || 0), submitted: reportPages.MONTHLY.total },
    { key: 'summary', label: '总结', required: Number(reportRules.value.summaryRequiredCount || 0), submitted: reportPages.SUMMARY.total }
  ]
  return current.map((item) => ({
    ...item,
    rate: item.required > 0 && item.submitted != null ? Math.min(100, Math.round(item.submitted * 100 / item.required)) : null
  }))
})

function resetSourceStates() {
  applicationHistoryOpen.value=false;insuranceProofBusy.value=false;closeInsuranceProof()
  helpEpoch++;helpReadSequence++;helpRows.value=[];helpBusy.value=false;helpError.value='';helpReceipt.value=null;helpCommitted.value=false
  Object.assign(helpForm,{title:'',content:'',riskLevel:'MEDIUM'})
  invalidateApplication();Object.assign(appForm,blankApplication());appBase.value=null;appLatest.value=null;appConflict.value=false;appError.value='';appReceipt.value='';appFiles.value=[];appPositions.value=[];appPositionsTotal.value=0;appPositionsMore.value=false;appPositionsPage=1;appPositionsError.value=''
  invalidateLeave(); resetLeaveDraft(); leaveDetail.value = null
  changeEpoch++; changeTargetSequence++; changeHistorySequence++
  resetChangeDraft(); changeForm.changeType = 'CHANGE_POSITION'; changeBusy.value = false; changeTargets.value = []
  changeKeyword.value = ''; changeTargetError.value = ''; changeTargetLoading.value = false
  changeTargetPage.value = 1; changeTargetMore.value = false
  changeHistoryPage.value = 1; changeHistoryMore.value = false
  attachmentEpoch++
  pendingInsuranceFile.value = null
  reportEpoch++; reportSourceSequence++; weeklyReadSequence++; weeklyReading.value = false
  reportMoreSequence++; reportMoreBusy.value = false
  reportKinds.forEach(kind => Object.assign(reportPages[kind], { page: 1, total: null, hasMore: false }))
  weeklyBase.value = null; processBase.value = null; weeklyConflict.value = false; processConflict.value = false
  weeklyDetail.value = null; processLatest.value = null; reportReceipt.value = null; reportError.value = ''
  processReadSequence++; processReading.value = false; processDetail.value = null
  Object.assign(weeklyForm, { week: null, workContent: '', harvestContent: '', planContent: '', attachments: [] })
  Object.assign(reportForm, { periodKey: currentMonth(), content: '', attachments: [] })
  Object.keys(processDrafts).forEach(key => delete processDrafts[key]); processDraftKind = 'MONTHLY'; reportReadMode.value = false
  busy.value = false
  Object.values(sourceStates).forEach((state) => Object.assign(state, { status: 'idle', message: '' }))
  leaves.value = []
  leaveReceipt.value = null
  leaveError.value = ''
  Object.assign(returnDraft, { id: '', note: '', version: null, conflict: false })
  makeups.value = []
  makeupReceipt.value = null
  makeupError.value = ''
  intentionEpoch++; intentionSourceSequence++
  intentionMeta.value = {}; intentionLatest.value = null; intentionConflict.value = false; intentionCommitted.value = false
  intentionFlags.value = { canEdit: false, canSubmit: false, canWithdraw: false }
  Object.assign(intentionForm, { preferredCity:'', preferredIndustry:'', intentionNote:'' })
  intentionReason.value = ''; intentionError.value = ''; intentionReceipt.value = ''; intentionBusy.value = false
  applications.value = []
  changes.value = []
  agreements.value = []
  activeAgreement.value = null
  agreementSequence++; agreementDetail.value = null; agreementReading.value = false; agreementBusy.value = false
  agreementReason.value = ''; agreementError.value = ''; agreementConflict.value = false; agreementReceipt.value = null
  enterprises.value = []
  enterprisePage.value=1;enterpriseMore.value=false;enterpriseTotal.value=0
  insuranceMeta.value = null
  insuranceEpoch++; insuranceError.value = ''; insuranceConflict.value = false
  Object.keys(insForm).forEach(key => { insForm[key] = '' })
  attendance.value = { summary: { CHECKIN:0, ABSENT:0, LEAVE:0, MAKEUP:0, EXEMPT:0 }, items: [], totalCountedDays: 0 }
  notices.value = []
  reportRules.value = {
    dailyMinWords: 30, weeklyMinWords: 30, monthlyMinWords: 100, summaryMinWords: 300,
    dailyRequiredCount: 0, weeklyRequiredCount: 0, monthlyRequiredCount: 0, summaryRequiredCount: 1
  }
  planMeta.value = null
  planAssignments.value = []
  selectedPlanId.value = ''
  planTasks.value = []
  planTaskSummary.value = { total: 0, approved: 0, rate: 0 }
  planTaskMinimumWords.value = 10
  selfEvalMeta.value = null
  evalBaseline.value='';evalScope.value='';evalConflict.value=false
  evalSourceSequence++
  Object.assign(evalForm,{performance:'',reflection:'',problems:'',enterpriseRating:null,enterpriseFeedback:'',positionRating:null,positionFeedback:''})
  appealMeta.value = null
  formalDocuments.value = []
}

function rowsFrom(data) {
  return data?.items || data?.list || (Array.isArray(data) ? data : [])
}

async function fetchTabSource(key) {
  const context = () => currentInternshipContext()
  if (key === 'overview') return true
  if (key === 'checkin') {
    attendance.value = await internshipCoreApi.attendance(context())
    return true
  }
  if (key === 'notices') {
    notices.value = rowsFrom(await internshipCoreApi.notices(context()))
    return notices.value.length > 0
  }
  if (key === 'leave') {
    leaveReadSequence++; leaveReading.value = false
    const t = captureLeaveContext(), seq = ++leaveSourceSequence
    const rows = rowsFrom(await internshipCoreApi.leaves(t.ctx))
    if (!leaveIsCurrent(t, false) || seq !== leaveSourceSequence) return false
    rows.forEach(row => assertLeave(row, t))
    leaves.value = rows
    return leaves.value.length > 0
  }
  if (key === 'makeup') {
    makeups.value = rowsFrom(await internshipCoreApi.makeups(context()))
    return makeups.value.length > 0
  }
  if (key === 'intention') {
    const t = captureIntention(), seq = ++intentionSourceSequence
    intentionFlags.value = { canEdit:false, canSubmit:false, canWithdraw:false }
    const data = await portalApi.internshipIntentionMy(t.ctx)
    if (!intentionCurrent(t) || seq !== intentionSourceSequence) return false
    applyIntention(data, intentionDirty.value || intentionConflict.value)
    intentionCommitted.value = false
    return !!data.intention
  }
  if (key === 'application') {
    const hasRows=await loadApplications()
    if(appError.value)throw new Error(appError.value)
    return hasRows
  }
  if(key==='help'){
    const t=captureHelp(),sequence=++helpReadSequence
    const result=await portalApi.internshipHelpMy(t.ctx)
    if(!helpCurrent(t) || sequence!==helpReadSequence)return false
    if(!Array.isArray(result?.items) || result.items.some(row=>!/^\d+$/.test(String(row.id || ''))))throw new Error('求助进度暂时无法核对，请重新读取')
    if(helpCommitted.value && helpReceipt.value?.id && !result.items.some(row=>String(row.id)===helpReceipt.value.id))throw new Error('求助回执尚未在原单进度中读到，请重新读取核对')
    helpRows.value=result.items;helpCommitted.value=false;helpError.value=''
    return helpRows.value.length>0
  }
  if (key === 'change') {
    await Promise.all([loadChanges(1), loadChangeTargets(1)])
    return true
  }
  if (key === 'report') {
    const t = captureReportContext(), seq = ++reportSourceSequence
    reportMoreSequence++; reportMoreBusy.value = false
    const results = await Promise.all([
      internshipCoreApi.weeklyReports(t.ctx),
      ...reportKinds.slice(1).map(kind => internshipCoreApi.reports(t.ctx, 1, 20, kind)),
    ])
    if (!reportIsCurrent(t, false) || seq !== reportSourceSequence) return false
    const pages = results.map((result, index) => readReportPage(reportKinds[index], result, t.ctx))
    my.value.weeklyReports = pages[0].items
    my.value.processReports = pages.slice(1).flatMap(page => page.items)
    pages.forEach((page, index) => { reportPages[reportKinds[index]] = { page: page.page, total: page.total, hasMore: page.hasMore } })
    const latestWeekly = my.value.weeklyReports.find(row => String(row.id) === String(weeklyBase.value?.id))
    if (latestWeekly && (latestWeekly.status !== 'RETURNED' || latestWeekly.version !== weeklyBase.value.version)) weeklyConflict.value = true
    const latestProcess = my.value.processReports.find(row => String(row.id) === String(processBase.value?.id))
    if (latestProcess && (latestProcess.status !== 'RETURNED' || latestProcess.version !== processBase.value.version)) processConflict.value = true
    reportRules.value = {
      ...reportRules.value,
      ...Object.assign({}, ...results.map(result => result?.rules || {}))
    }
    return my.value.weeklyReports.length > 0 || my.value.processReports.length > 0
  }
  if (key === 'agreement') {
    const epoch = changeEpoch, generation = currentSessionGeneration(), key = agreementContextKey()
    const context = currentInternshipContext()
    const result = rowsFrom(await internshipCoreApi.agreements(context))
    if (!changeAlive || epoch !== changeEpoch || generation !== currentSessionGeneration() || key !== agreementContextKey()) return false
    if (result.some(row => String(row.batchId) !== String(context.batchId) || String(row.internId) !== String(context.internshipId))) throw new Error('协议列表与当前实习记录不一致，请重新读取')
    agreements.value = result
    activeAgreement.value = result.find(item => String(item.id) === String(activeAgreement.value?.id)) || result.find(item => item.status === 'PENDING_STUDENT') || result[0] || null
    if (tab.value === 'agreement' && activeAgreement.value) await openAgreement(activeAgreement.value)
    return agreements.value.length > 0
  }
  if (key === 'insurance') {
    const epoch = ++insuranceEpoch
    const result = await internshipCoreApi.insurance(currentInternshipContext())
    if (epoch !== insuranceEpoch) return false
    insuranceMeta.value = result
    insuranceError.value = ''; insuranceConflict.value = false
    if (!insuranceMeta.value?.id && !insuranceMeta.value?.policyNo) return false
    Object.assign(insForm, {
      policyNo: insuranceMeta.value.policyNo || '',
      insurerName: insuranceMeta.value.insurerName || '',
      coverageType: insuranceMeta.value.coverageType || '',
      effectiveDate: insuranceMeta.value.effectiveDate || '',
      expiryDate: insuranceMeta.value.expiryDate || '',
      fileId: insuranceMeta.value.fileId || '',
    })
    return true
  }
  if (key === 'plan') {
    const context = currentInternshipContext(), epoch = changeEpoch, generation = currentSessionGeneration(), sequence = ++planSourceSequence
    const current = () => changeAlive && epoch === changeEpoch && sequence === planSourceSequence && generation === currentSessionGeneration() &&
      String(context.batchId) === String(currentInternshipContext().batchId) && String(context.internshipId) === String(currentInternshipContext().internshipId)
    const sameContext = data => String(data?.context?.batchId || '') === String(context.batchId) && String(data?.context?.internshipId || '') === String(context.internshipId)
    const listData = await internshipCoreApi.plans(context)
    if (!current()) return false
    if (!Array.isArray(listData?.items) || !sameContext(listData)) throw new Error('实习计划与当前实习记录不一致，请重新读取')
    planAssignments.value = rowsFrom(listData)
    const selected = planAssignments.value.find((item) => String(item.planId) === String(selectedPlanId.value || ''))
      || planAssignments.value.find((item) => item.isPrimary)
      || planAssignments.value[0]
    selectedPlanId.value = selected ? String(selected.planId) : ''
    if (!selectedPlanId.value) {
      planMeta.value = null
      planTasks.value = []
      planTaskSummary.value = { total: 0, approved: 0, rate: 0 }
      return false
    }
    const [plan, taskData] = await Promise.all([
      internshipCoreApi.plan(selectedPlanId.value, context),
      internshipCoreApi.planTasks(selectedPlanId.value, context)
    ])
    if (!current()) return false
    if (!sameContext(plan) || !sameContext(taskData) || !Array.isArray(taskData?.tasks) ||
      String(plan?.id || plan?.planId) !== selectedPlanId.value || String(taskData?.planId) !== selectedPlanId.value ||
      (plan.version ?? plan.planVersion) !== taskData.planVersion) throw new Error('实习计划已变化，请重新读取')
    planMeta.value = plan || null
    planTaskMinimumWords.value = Number(taskData?.minimumWords || 10)
    planTaskSummary.value = taskData?.summary || plan?.taskSummary || { total: 0, approved: 0, rate: 0 }
    planTasks.value = rowsFrom(taskData?.tasks || []).map((task) => ({
      ...task,
      _note: task.progressStatus === 'REJECTED' ? (task.studentNote || '') : '',
      _evidenceFileId: task.evidenceFileId || '',
      _evidenceFileName: task.evidenceFileId ? '已上传凭证' : ''
    }))
    return !!planMeta.value?.id
  }
  if (key === 'eval') {
    const seq=++evalSourceSequence,ctx=context(),epoch=changeEpoch,generation=currentSessionGeneration(),scope=JSON.stringify([generation,ctx])
    const preserve=evalScope.value===scope&&JSON.stringify(evalForm)!==evalBaseline.value
    const [selfEval, appeal, docs] = await Promise.all([
      internshipCoreApi.selfEval(ctx),
      portalApi.internshipScoreAppealStatus(ctx),
      internshipCoreApi.formalDocuments(ctx),
    ])
    if(seq!==evalSourceSequence||!changeCurrent(epoch,generation,ctx))return false
    if(preserve){if(String(selfEval?.id||'')!==String(selfEvalMeta.value?.id||'')||selfEval?.version!==selfEvalMeta.value?.version)evalConflict.value=true}
    else{
      selfEvalMeta.value = selfEval?.id ? selfEval : null
      Object.assign(evalForm,{performance:selfEval?.selfSummary||'',reflection:selfEval?.selfHarvest||'',problems:selfEval?.selfProblem||'',
        enterpriseRating:selfEval?.enterpriseRating??null,enterpriseFeedback:selfEval?.enterpriseFeedback||'',positionRating:selfEval?.positionRating??null,positionFeedback:selfEval?.positionFeedback||''})
      evalBaseline.value=JSON.stringify(evalForm);evalConflict.value=false
    }
    evalScope.value=scope
    appealMeta.value = appeal || null
    formalDocuments.value = rowsFrom(docs)
    return !!selfEvalMeta.value || !!appealMeta.value || !!my.value.score || formalDocuments.value.length > 0
  }
  if (key === 'enterprises') {
    const t=captureApplication(),page=enterprisePage.value
    const data=await internshipCoreApi.positions(t.ctx,page,enterpriseCity.value)
    if(t.generation!==currentSessionGeneration() || String(t.ctx.batchId)!==String(currentInternshipContext().batchId) || String(t.ctx.internshipId)!==String(currentInternshipContext().internshipId))return false
    if(String(data.batchId)!==String(t.ctx.batchId) || String(data.internshipId)!==String(t.ctx.internshipId))throw new Error('岗位库不属于当前实习记录')
    enterprises.value = rowsFrom(data);enterpriseTotal.value=data.total;enterpriseMore.value=!!data.hasMore
    return enterprises.value.length > 0
  }
  return true
}

async function loadTab(key, force = false) {
  if (key === 'consent') return // 知情工作区自行管理列表、正文与办理状态。
  const state = sourceStates[key]
  if (!state || !my.value.hasData) return
  if (['agreement','insurance'].includes(key) && state.status === 'loading') return
  if (!force && ['loading', 'data', 'empty'].includes(state.status)) return
  state.status = 'loading'
  state.message = ''
  const epoch = changeEpoch, generation = currentSessionGeneration(), reportsEpoch = reportEpoch
  const leavesEpoch = leaveEpoch
  const intentionsEpoch = intentionEpoch
  const helpsEpoch=helpEpoch
  let reportsSequence = reportSourceSequence
  let leavesSequence = leaveSourceSequence
  let plansSequence = planSourceSequence
  let evaluationsSequence = evalSourceSequence
  let intentionsSequence = intentionSourceSequence
  let helpsSequence=helpReadSequence
  const current = () => changeAlive && epoch === changeEpoch && generation === currentSessionGeneration()
    && (key !== 'report' || (reportsEpoch === reportEpoch && reportsSequence === reportSourceSequence))
    && (key !== 'leave' || (leavesEpoch === leaveEpoch && leavesSequence === leaveSourceSequence))
    && (key !== 'plan' || plansSequence === planSourceSequence)
    && (key !== 'eval' || evaluationsSequence === evalSourceSequence)
    && (key !== 'intention' || (intentionsEpoch === intentionEpoch && intentionsSequence === intentionSourceSequence))
    && (key !== 'help' || (helpsEpoch===helpEpoch && helpsSequence===helpReadSequence))
  try {
    const request = fetchTabSource(key)
    reportsSequence = reportSourceSequence
    leavesSequence = leaveSourceSequence
    plansSequence = planSourceSequence
    evaluationsSequence = evalSourceSequence
    intentionsSequence = intentionSourceSequence
    helpsSequence=helpReadSequence
    const hasData = await request
    if (current()) state.status = hasData ? 'data' : 'empty'
  } catch (e) {
    if (!current()) return
    state.status = 'error'
    state.message = e?.message || `${state.label}加载失败，请重试`
  }
}

async function retryCurrentSource() {
  await loadTab(tab.value, true)
}

async function loadEnterprises() {
  enterprisePage.value=1
  await loadTab('enterprises', true)
}
async function pageEnterprises(delta){if(busy.value)return;enterprisePage.value=Math.max(1,enterprisePage.value+delta);await loadTab('enterprises',true)}

async function refreshProgress() {
  if (!my.value.hasData) return
  const context=currentInternshipContext(),epoch=changeEpoch,generation=currentSessionGeneration(),sequence=++overviewSequence
  const current=()=>changeCurrent(epoch,generation,context) && sequence===overviewSequence && tab.value==='overview'
  overviewLoading.value=true;overviewError.value=''
  try {
    const data=await portalApi.internshipMy(context.batchId)
    if(!current())return
    if(!data?.hasData || String(data.batchId)!==String(context.batchId) || String(data.recordId||data.internshipId)!==String(context.internshipId))throw Error('context')
    my.value={...my.value,...data,weeklyReports:my.value.weeklyReports,processReports:my.value.processReports}
  }catch{if(current())overviewError.value='最新办理进度未能读取，当前展示上次读取结果，请重新核对。'}
  finally{if(sequence===overviewSequence)overviewLoading.value=false}
}
async function load() {
  if(!session.user?.userId || !session.user?.tenantId){resetSourceStates();my.value={};loading.value=false;return}
  saveReportDraft()
  reportDraftContext = ''
  loading.value = true; error.value = ''
  resetSourceStates()
  const seq = ++loadSequence, generation = currentSessionGeneration()
  const current = () => changeAlive && seq === loadSequence && generation === currentSessionGeneration()
  try {
    try { selectedBatchId.value = String(sessionStorage.getItem(INTERNSHIP_BATCH_KEY) || '') } catch { selectedBatchId.value = '' }
    if (/^[1-9]\d*$/.test(String(route.query.batchId || ''))) persistInternshipBatch(route.query.batchId)
    const data = await portalApi.internshipMy(selectedBatchId.value) || {}
    if (!current()) return
    my.value = data
    if (Array.isArray(data.candidates) && data.candidates.length) internshipCandidates.value = data.candidates
    if (data.needSelect) {
      persistInternshipBatch('')
      return
    }
    if (data.batchId) persistInternshipBatch(data.batchId)
    if (!data.hasData) return
    reportDraftContext = reportDraftScope()
    reportDraftGeneration = generation
    const initialSources = [...new Set(['agreement', 'insurance', 'plan', 'report', 'checkin', tab.value])]
    await Promise.all(initialSources.map((key) => loadTab(key, true)))
    if (current()) restoreReportDraft()
  } catch (e) { if (current()) error.value = e?.message || '实习信息加载失败' } finally { if (current()) { loading.value = false; focusReportFromRoute() } }
}
function attendanceStatusText(value) {
  return ({ CHECKIN:'已签到', ABSENT:'未签到', PENDING:'未签到', LEAVE:'请假', MAKEUP:'补签', EXEMPT:'免签' })[value] || '状态待确认'
}
async function downloadAttendancePdf() {
  if (busy.value) return
  busy.value = true
  try {
    const data = await internshipCoreApi.attendancePdf(currentInternshipContext())
    const raw = atob(String(data?.contentBase64 || ''))
    const bytes = new Uint8Array(raw.length)
    for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i)
    const blob = new Blob([bytes], { type: data?.mediaType || 'application/pdf' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = data?.filename || '岗位实习签到考勤记录.pdf'
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    ui.notify('考勤打印件已生成')
  } catch (e) {
    ui.notify(e?.message || '考勤打印件生成失败')
  } finally {
    busy.value = false
  }
}
async function doCheckin() {
  if (busy.value || my.value.historyMode || !['ONBOARD', 'ASSESSING'].includes(my.value.status)) return
  const ctx = currentInternshipContext(), epoch = changeEpoch, generation = currentSessionGeneration()
  const current = () => changeCurrent(epoch, generation, ctx)
  busy.value = true
  try {
    await portalApi.internshipCheckin({
      ...ctx,
      source: 'PORTAL', note: '学生PC门户登记打卡',
      idempotencyKey: `portal-checkin-${new Date().toISOString().slice(0, 10)}`
    })
    if (!current()) return
    ui.notify('打卡已记录')
    const [freshAttendance, freshMy] = await Promise.all([
      internshipCoreApi.attendance(ctx),
      portalApi.internshipMy(ctx.batchId)
    ])
    if (!current()) return
    attendance.value = freshAttendance || attendance.value
    my.value = freshMy || my.value
  } catch (e) { if (current()) ui.notify(e?.message || '打卡失败') } finally { if (current()) busy.value = false }
}
async function submitMakeup() {
  if (busy.value) return
  makeupError.value = ''
  if (!makeupCanSubmit.value) {
    makeupError.value = makeupEvidenceRequired.value && !makeupForm.evidenceFileId
      ? '定位异常补卡必须先上传定位、考勤或现场佐证。'
      : '请填写缺卡日期和不少于5个字的详细事由。'
    return
  }
  busy.value = true
  try {
    const result = await internshipCoreApi.applyMakeup({
      checkinDate: makeupForm.checkinDate,
      reason: makeupForm.reason.trim(),
      makeupType: makeupForm.makeupType,
      evidenceFileId: makeupForm.evidenceFileId || '',
      ...currentInternshipContext()
    })
    makeupReceipt.value = result
    ui.notify('补卡申请已提交')
    makeupForm.checkinDate = ''
    makeupForm.reason = ''
    makeupForm.makeupType = 'MISSING'
    makeupForm.evidenceFileId = ''
    makeupForm.fileName = ''
    await loadTab('makeup', true)
  } catch (e) {
    makeupError.value = e?.message || '补卡提交失败，已保留填写内容，请稍后重试。'
    ui.notify(makeupError.value)
  } finally { busy.value = false }
}
async function uploadMakeupEvidence(event) {
  if (busy.value) return
  const file = event?.target?.files?.[0]
  if (!file) return
  if (Number(file.size || 0) > 20 * 1024 * 1024) {
    makeupError.value = '单个证据文件不能超过20MB。'
    if (event?.target) event.target.value = ''
    return
  }
  busy.value = true
  makeupError.value = ''
  try {
    const uploaded = await internshipCoreApi.uploadMakeupEvidence(file)
    const fileId = uploaded?.fileId || uploaded?.id
    if (!fileId) throw new Error('上传响应缺少文件标识')
    makeupForm.evidenceFileId = String(fileId)
    makeupForm.fileName = uploaded?.fileName || file.name || '补卡证据'
    ui.notify('证据材料已上传')
  } catch (e) {
    makeupError.value = e?.message || '证据材料上传失败，表单内容已保留。'
  } finally {
    busy.value = false
    if (event?.target) event.target.value = ''
  }
}
async function withdrawMakeup(item) {
  busy.value = true
  try {
    await internshipCoreApi.withdrawMakeup(item.id, {
      ...currentInternshipContext(),
      expectedVersion: item.version
    })
    ui.notify('已撤回'); await loadTab('makeup', true)
  } catch (e) { ui.notify(e?.message || '撤回失败') } finally { busy.value = false }
}
function captureIntention() { return { ctx:currentInternshipContext(), epoch:intentionEpoch, generation:currentSessionGeneration() } }
function intentionCurrent(t) { if(!changeAlive || document?.hidden || tab.value!=='intention' || t.epoch!==intentionEpoch || t.generation!==currentSessionGeneration() || !my.value.batchId || !(my.value.recordId || my.value.internshipId))return false;const ctx=currentInternshipContext();return String(t.ctx.batchId)===String(ctx.batchId) && String(t.ctx.internshipId)===String(ctx.internshipId) }
function applyIntention(data, preserveDraft=false) {
  const row=data.intention || {}
  intentionLatest.value=data; intentionReason.value=data.readOnlyReason || '当前暂不能办理，请联系学校核对。'
  intentionFlags.value={canEdit:data.canEdit===true,canSubmit:data.canSubmit===true,canWithdraw:data.canWithdraw===true}
  if(preserveDraft && (intentionConflict.value || String(row.id||'')!==String(intentionMeta.value.id||'') || row.version!==intentionMeta.value.version)) { intentionConflict.value=true;return }
  intentionMeta.value=row
  if(!preserveDraft)Object.assign(intentionForm,{preferredCity:row.preferredCity||'',preferredIndustry:row.preferredIndustry||'',intentionNote:row.intentionNote||''})
  intentionConflict.value=false
}
function continueIntentionAfterConflict() {
  if(!intentionLatest.value || intentionBusy.value)return
  const retained={...intentionForm};applyIntention(intentionLatest.value);Object.assign(intentionForm,retained)
  intentionError.value='';intentionCommitted.value=false
}
function intentionBody(ctx, row=intentionMeta.value) {
  return {...ctx,...intentionForm,preferredPositionId:row.preferredPositionId||'',...(row.id?{id:String(row.id),expectedVersion:row.version}:{})}
}
async function mutateIntention(action) {
  if(intentionBusy.value || !intentionReady.value || (action==='SAVE'&&!intentionCanEdit.value) || (action==='SUBMIT'&&!intentionCanSubmit.value) || (action==='WITHDRAW'&&!intentionCanWithdraw.value))return
  const t=captureIntention(), frozen=intentionBody(t.ctx)
  const retainedDraft=intentionDirty.value && (action==='WITHDRAW' || (action==='SUBMIT' && !intentionCanEdit.value)) ? {...intentionForm} : null
  intentionBusy.value=true;intentionError.value='';intentionReceipt.value=''
  try {
    if(action==='WITHDRAW') {
      const confirmed=await systemConfirm({title:'撤回当前意向',message:'撤回后学校不再按本次意向继续匹配，原记录仍保留。',confirmText:'撤回意向'})
      if(!confirmed || !intentionCurrent(t))return
    }
    let result=null
    if(action==='SAVE' || (action==='SUBMIT' && intentionCanEdit.value && intentionDirty.value)) {
      result=await portalApi.internshipIntentionSave(frozen)
      if(!intentionCurrent(t))return
      applyIntention(result);intentionCommitted.value=true
    }
    if(action==='SUBMIT') {
      if(result && result.canSubmit!==true) {
        intentionReceipt.value='修改已保存，当前暂不能提交，请核对最新意向状态。'
      } else {
        const row=result?.intention || intentionMeta.value
        result=await portalApi.internshipIntentionSubmit({...t.ctx,id:String(row.id),expectedVersion:row.version})
        if(!intentionCurrent(t))return
        applyIntention(result);intentionCommitted.value=true;intentionReceipt.value='意向已提交，下一步由学校按已提交意向匹配岗位。'
      }
    } else if(action==='WITHDRAW') {
      result=await portalApi.internshipIntentionWithdraw({...t.ctx,id:frozen.id,expectedVersion:frozen.expectedVersion})
      if(!intentionCurrent(t))return
      applyIntention(result);intentionCommitted.value=true;intentionReceipt.value='意向已撤回，原记录已保留，可在本页重新提交原意向。'
    } else intentionReceipt.value=result?.intention?.status==='SUBMITTED'?'已提交意向的更正已保存，学校将读取最新内容。':'意向草稿已保存；提交后才进入学校匹配范围。'
    try {
      const latest=await portalApi.internshipIntentionMy(t.ctx)
      if(!intentionCurrent(t))return
      applyIntention(latest);sourceStates.intention.status=latest.intention?'data':'empty';intentionCommitted.value=false
    } catch {
      if(intentionCurrent(t))intentionError.value='办理已保存，最新结果暂未读回。请重新读取，不必重复提交。'
    }
  } catch(error) {
    if(!intentionCurrent(t))return
    if(error?.bizCode==='DATA_CONFLICT'){intentionConflict.value=true;intentionLatest.value=null}
    intentionError.value=error?.bizCode==='DATA_CONFLICT'?'意向版本或办理条件已变化，输入已保留。请重新读取并核对。':error?.bizCode==='NO_PERMISSION'?'当前账号无权办理此意向，请联系学校核对。':'意向办理未完成，输入已保留，请核对内容和所选岗位后重试。'
  } finally { if(intentionCurrent(t)){if(retainedDraft)Object.assign(intentionForm,retainedDraft);intentionBusy.value=false} }
}
function saveIntention(){return mutateIntention('SAVE')}
function submitIntention(){return mutateIntention('SUBMIT')}
function withdrawIntention(){return mutateIntention('WITHDRAW')}
function intentionVisibilityChanged(){
  if(tab.value!=='intention')return
  intentionEpoch++;intentionBusy.value=false
  if(document.hidden)sourceStates.intention.status='idle'
  else loadTab('intention',true)
}
function applicationStatusText(status) { return ({DRAFT:'草稿',PENDING_REVIEW:'待审核',REJECTED:'已退回',APPROVED:'已通过',WITHDRAWN:'已撤回',CANCELLED:'已取消'})[status] || '状态待核实' }
function captureApplication() { return {ctx:currentInternshipContext(),epoch:appEpoch,generation:currentSessionGeneration()} }
function applicationCurrent(t) { const ctx=currentInternshipContext();return changeAlive && !document?.hidden && tab.value==='application' && t.epoch===appEpoch && t.generation===currentSessionGeneration() && String(t.ctx.batchId)===String(ctx.batchId) && String(t.ctx.internshipId)===String(ctx.internshipId) }
function invalidateApplication(){appEpoch++;appListSequence++;appBusy.value=false;appReading.value=false;appPositionsLoading.value=false}
function applicationLeaving(){const writing=appBusy.value;invalidateApplication();if(writing){appConflict.value=true;appError.value='离开时请求结果尚未确认，输入已保留，请回读原单后继续'}}
function applicationVisibilityChanged(){if(document?.hidden && tab.value==='application')applicationLeaving()}
function newApplication(type='SELF_ARRANGED') { if(appBusy.value || appReading.value)return;invalidateApplication();Object.assign(appForm,blankApplication(type));appBase.value=null;appLatest.value=null;appConflict.value=false;appError.value='';appReceipt.value='';appFiles.value=[] }
function fillApplication(row){
  appBase.value={...row,id:String(row.id)};Object.assign(appForm,blankApplication(row.applicationType))
  for(const key of Object.keys(appForm))if(row[key]!==undefined && row[key]!==null)appForm[key]=Array.isArray(row[key])?[...row[key]]:row[key]
  appForm.evidenceFileId=String(row.evidenceFileId||'');appForm.agreementFileIds=(row.agreementFileIds||[]).map(String)
  appFiles.value=appAttachmentIds.value.map(fileId=>({fileId,fileName:'申请材料',readyForBusiness:false,statusText:'正在核对安全状态'}))
}
async function openApplication(row){
  if(appBusy.value || appReading.value)return
  const t=captureApplication()
  if(appBase.value && !await systemConfirm({title:'打开原申请',message:'打开后将读取所选原单，当前未保存修改不会带入。',confirmText:'打开原单'}))return
  if(!applicationCurrent(t))return
  invalidateApplication();fillApplication(row);appConflict.value=false;appLatest.value=null;appError.value='';appReceipt.value=''
  await refreshApplicationFiles()
}
async function loadApplications(){
  const t=captureApplication(),sequence=++appListSequence
  try{const [raw,library]=await Promise.all([internshipCoreApi.applications(t.ctx),internshipCoreApi.positions(t.ctx)])
    if(!applicationCurrent(t) || sequence!==appListSequence)return false
    if(String(library.batchId)!==String(t.ctx.batchId) || String(library.internshipId)!==String(t.ctx.internshipId))throw new Error('岗位库不属于当前实习记录，请重新读取')
    const rows=rowsFrom(raw);appPositions.value=library.items||[];appPositionsTotal.value=library.total;appPositionsMore.value=!!library.hasMore;appPositionsPage=1;appPositionsError.value=''
    applications.value=rows;appError.value=''
    if(!appBase.value && JSON.stringify(appForm)===JSON.stringify(blankApplication(appForm.applicationType))){const own=rows.find(row=>row.applicationType===(my.value.destinationType==='EXEMPTED'?'EXEMPTION':appForm.applicationType));if(own){fillApplication(own);await refreshApplicationFiles()}}
    return rows.length>0
  }catch(error){if(applicationCurrent(t) && sequence===appListSequence)appError.value=error?.message||'申请列表读取失败，请重试';return false}
}
async function loadMoreApplicationPositions(){
  if(!appPositionsMore.value || appPositionsLoading.value)return
  const t=captureApplication(),page=appPositionsPage+1;appPositionsLoading.value=true;appPositionsError.value=''
  try{const data=await internshipCoreApi.positions(t.ctx,page);if(!applicationCurrent(t))return
    if(String(data.batchId)!==String(t.ctx.batchId) || String(data.internshipId)!==String(t.ctx.internshipId))throw new Error('后续岗位不属于当前实习记录')
    const ids=new Set(appPositions.value.map(row=>String(row.id)));appPositions.value.push(...(data.items||[]).filter(row=>!ids.has(String(row.id))))
    appPositionsPage=page;appPositionsTotal.value=data.total;appPositionsMore.value=!!data.hasMore
  }catch(error){if(applicationCurrent(t))appPositionsError.value=error?.message||'后续岗位读取失败，已加载岗位和选择保留'}finally{if(applicationCurrent(t))appPositionsLoading.value=false}
}
function applicationError(error){
  if(error?.bizCode==='DATA_CONFLICT' || Number(error?.status)===409 || Number(error?.code)===409001){appConflict.value=true;appLatest.value=null;return '原单已变化，填写内容和原版本已保留，请读取最新原单核对'}
  return error?.bizCode==='FILE_ZIP_REJECTED'?'压缩包未通过安全检查，已拒绝上传，原材料已保留':(error?.message||'申请办理未完成，填写内容和原版本已保留')
}
async function rereadApplication(){
  if(appBusy.value || appReading.value)return
  const t=captureApplication();appReading.value=true;appLatest.value=null
  try{const rows=rowsFrom(await internshipCoreApi.applications(t.ctx));if(!applicationCurrent(t))return;applications.value=rows
    appLatest.value=rows.find(row=>appBase.value?String(row.id)===String(appBase.value.id):row.applicationType===appForm.applicationType)||null
    if(!appLatest.value)appError.value='未读取到可核对原单，请重试或联系指导教师；原输入仍保留'
  }catch(error){if(applicationCurrent(t))appError.value=error?.message||'最新原单读取失败，原输入已保留'}finally{if(applicationCurrent(t))appReading.value=false}
}
async function adoptLatestApplication(){
  if(!appLatest.value || appBusy.value || appReading.value)return
  const t=captureApplication(),latest=appLatest.value
  const accepted=await systemConfirm({title:'采用最新原单',message:'这会以已查看的最新原单替换当前未保存输入，请确认已经核对内容。',confirmText:'采用最新原单'})
  if(!accepted || !applicationCurrent(t))return
  invalidateApplication();fillApplication(latest);appConflict.value=false;appLatest.value=null;appError.value='';await refreshApplicationFiles()
}
async function refreshApplicationFiles(){
  if(appBusy.value || appReading.value)return false
  const t=captureApplication(),ids=[...appAttachmentIds.value];if(!ids.length){appFiles.value=[];return true}
  appReading.value=true;appError.value='';appFiles.value=ids.map(fileId=>({...appFiles.value.find(f=>String(f.fileId)===fileId),fileId,readyForBusiness:false}))
  try{const files=await Promise.all(ids.map(async fileId=>{const meta=await fileSdk.metadata(fileId);if(String(meta?.fileId)!==fileId)throw new Error('材料编号不一致，请重新核对');return scanState(meta)}))
    if(!applicationCurrent(t))return false;appFiles.value=files
    if(!appAttachmentsReady.value)appError.value='材料安全检查尚未完成，请刷新检查结果后再保存；正文与附件已保留'
    return appAttachmentsReady.value
  }catch(error){if(applicationCurrent(t))appError.value=error?.message||'材料安全状态读取失败，请重试';return false}finally{if(applicationCurrent(t))appReading.value=false}
}
async function uploadApplicationEvidence(event,target='evidence'){
  const file=event?.target?.files?.[0];if(!file || appBusy.value || appReading.value || !appWritable.value || appConflict.value)return
  if(target==='agreement' && appForm.agreementFileIds.length>=9){appError.value='三方协议照片最多9份';return}
  const t=captureApplication();appBusy.value=true;appError.value=''
  try{const uploaded=await fileSdk.upload(file,{bizType:'INTERNSHIP_APPLICATION_EVIDENCE'});if(!applicationCurrent(t))return
    if(!uploaded?.fileId)throw new Error('材料接收结果缺少编号，请重试')
    const meta=scanState(uploaded),id=String(meta.fileId)
    if(target==='agreement')appForm.agreementFileIds=[...appForm.agreementFileIds,id];else appForm.evidenceFileId=id
    appFiles.value=[...appFiles.value.filter(f=>appAttachmentIds.value.includes(String(f.fileId))),{...meta,fileId:id,fileName:meta.fileName||file.name}]
    if(!meta.readyForBusiness)appError.value='材料已接收，安全检查尚未完成，请稍后刷新检查结果'
  }catch(error){if(applicationCurrent(t))appError.value=applicationError(error)}finally{if(applicationCurrent(t))appBusy.value=false;if(event?.target)event.target.value=''}
}
function removeApplicationFile(id){if(appBusy.value || appReading.value || !appWritable.value || appConflict.value)return;if(String(appForm.evidenceFileId)===String(id))appForm.evidenceFileId='';appForm.agreementFileIds=appForm.agreementFileIds.filter(fileId=>String(fileId)!==String(id));appFiles.value=appFiles.value.filter(file=>String(file.fileId)!==String(id))}
async function downloadApplicationFile(file){
  if(appBusy.value || appReading.value || !appAttachmentIds.value.includes(String(file.fileId)))return
  const t=captureApplication();appReading.value=true;appError.value=''
  try{const meta=scanState(await fileSdk.metadata(file.fileId));if(!applicationCurrent(t))return;if(String(meta.fileId)!==String(file.fileId) || !meta.readyForBusiness || !meta.canDownload)throw new Error('材料尚未安全可用或没有下载权限，请刷新检查结果');await fileSdk.download(String(meta.fileId),meta.fileName||file.fileName||'申请材料')}
  catch(error){if(applicationCurrent(t))appError.value=error?.message||'材料下载失败，请重试'}finally{if(applicationCurrent(t))appReading.value=false}
}
function validateApplication(complete){
  if(appForm.applicationType==='SELF_ARRANGED'){
    for(const field of appFields){const value=String(appForm[field.key]??'').trim();if((complete && value.length<field.min) || value.length>field.max)return `${field.label}请填写${field.min?`至少${field.min}字、`:''}最多${field.max}字`}
    if(complete && !/^[0-9A-HJ-NPQRTUWXY]{18}$/i.test(appForm.companyCreditCode))return '请填写18位规范统一社会信用代码'
    for(const key of ['companyPhone','contactPhone','enterpriseMentorPhone'])if(appForm[key] && !/^[0-9+() -]{7,32}$/.test(appForm[key]))return '请核对企业、联系人及带教老师联系电话'
    if(appForm.companyEmail && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(appForm.companyEmail))return '企业邮箱格式不正确'
    if(appForm.internshipStartDate && appForm.internshipEndDate && appForm.internshipStartDate>appForm.internshipEndDate)return '实习结束日期不能早于开始日期'
    if(complete && typeof appForm.majorMatch!=='boolean')return '请选择岗位是否专业对口'
    const amount=appForm.agreedSalary;if((complete && amount==='') || (amount!=='' && (!Number.isFinite(Number(amount)) || Number(amount)<0 || Number(amount)>100000000)))return '实习薪资请填写0到100000000之间的金额，0元有效'
    if(complete && !appForm.evidenceFileId)return '请上传自主实习证明材料'
  }else if(appForm.applicationType==='EXEMPTION'){
    if((complete || appForm.exemptionType) && !exemptionTypes.some(type=>type.value===appForm.exemptionType))return '请选择免实习类型'
    if((complete && appForm.exemptionDestination.trim().length<2) || appForm.exemptionDestination.length>200)return '免实习后去向请填写2到200字'
    if((complete && appForm.exemptionReason.trim().length<5) || appForm.exemptionReason.length>500)return '免实习原因请填写5到500字'
    if(complete && !appForm.evidenceFileId)return '请上传免实习佐证材料'
  }else if(appForm.applicationType==='POSITION'){const position=appPositions.value.find(row=>String(row.id)===String(appForm.positionId));if(!position || !position.canSelect)return position?.selectionReason||'请从当前已读取目录选择可申请岗位'}else return '此申请请在原业务入口办理'
  if(complete && appForm.applicationType!=='EXEMPTION' && appForm.applicationNote.trim().length<5)return '申请说明不少于5字'
  return ''
}
async function saveApplicationDraft(){return writeApplication(false)}
async function submitApplication(){return writeApplication(true)}
async function writeApplication(submit){
  if(appBusy.value || appReading.value || !appWritable.value || appConflict.value)return
  appError.value=validateApplication(submit);if(appError.value)return
  const t=captureApplication();if(!await refreshApplicationFiles() || !applicationCurrent(t))return
  appBusy.value=true;appReceipt.value=''
  const body={...appForm,agreementFileIds:[...appForm.agreementFileIds],...t.ctx,...(appBase.value?{id:appBase.value.id,expectedVersion:appBase.value.version}:{})}
  if(body.applicationType==='EXEMPTION')body.applicationNote=body.exemptionReason.trim()
  try{
    const saved=await internshipCoreApi.saveApplication(body);if(!applicationCurrent(t))return
    appBase.value={...saved};appReceipt.value='原单草稿已保存，可继续填写或提交'
    if(submit){const result=await internshipCoreApi.submitApplication(saved.id,{...t.ctx,expectedVersion:saved.version});if(!applicationCurrent(t))return;appBase.value={...saved,...result};appReceipt.value=body.applicationType==='EXEMPTION'?'原免实习申请已提交，下一步由学校审核；可在本页刷新查看结果':'原单已提交，下一步由指导教师审核；可在本页刷新查看结果'}
    applications.value=[appBase.value,...applications.value.filter(row=>String(row.id)!==String(appBase.value.id))]
    try{const rows=rowsFrom(await internshipCoreApi.applications(t.ctx));if(applicationCurrent(t))applications.value=rows}catch{if(applicationCurrent(t))appError.value='办理已提交，列表暂未回读，请刷新申请列表核对，不要重复提交'}
  }catch(error){if(applicationCurrent(t))appError.value=applicationError(error)}finally{if(applicationCurrent(t))appBusy.value=false}
}
async function withdrawApplication(){
  if(appBusy.value || appReading.value || my.value.historyMode || appBase.value?.status!=='PENDING_REVIEW')return
  const t=captureApplication(),base={...appBase.value};appBusy.value=true;appError.value=''
  try{const result=await internshipCoreApi.withdrawApplication(base.id,{...t.ctx,expectedVersion:base.version});if(!applicationCurrent(t))return;appBase.value={...base,...result};appReceipt.value='原单已撤回，可补充修改后重新提交';applications.value=applications.value.map(row=>String(row.id)===String(base.id)?appBase.value:row)}catch(error){if(applicationCurrent(t))appError.value=applicationError(error)}finally{if(applicationCurrent(t))appBusy.value=false}
}
async function submitChange() {
  if (busy.value || changeBusy.value || !changeWritable.value) return
  if ((changeForm.reason || '').trim().length < 5) {
    return ui.notify('变更事由不少于 5 字')
  }
  const selected = changeSelectedTarget.value
  if (changeNeedsTarget.value && (!selected || selected.canSelect !== true)) return ui.notify('请选择当前可申请的真实目标岗位')
  if (changeForm.changeType === 'SELF_ARRANGED' && (changeForm.targetEnterpriseName.trim().length < 2 || changeForm.targetPositionName.trim().length < 2)) return ui.notify('请填写完整的自主实习企业和岗位')
  const ctx = currentInternshipContext(), epoch = changeEpoch, generation = currentSessionGeneration()
  const current = () => changeCurrent(epoch, generation, ctx)
  const editing = changeEditing.value
  const body = { ...ctx, changeType: changeForm.changeType, reason: changeForm.reason.trim(), expectedVersion: editing ? editing.version : 0 }
  if (changeNeedsTarget.value) body.targetPositionId = String(selected.positionId)
  if (changeForm.changeType === 'SELF_ARRANGED') Object.assign(body, { targetEnterpriseName: changeForm.targetEnterpriseName, targetPositionName: changeForm.targetPositionName })
  changeBusy.value = true; changeError.value = ''
  try {
    const result = editing ? await internshipCoreApi.resubmitChange(editing.id, body) : await internshipCoreApi.applyChange(body)
    if (!current()) return
    resetChangeDraft(); changeReceipt.value = { ...result, actionLabel: editing ? '原变更单已补正重交' : '变更申请已提交', statusLabel: changeStatusLabel(result.status) }
    await loadChanges(1)
  } catch (e) { if (current()) changeError.value = changeErrorText(e) }
  finally { if (current()) changeBusy.value = false }
}
async function withdrawChange(item) {
  if (busy.value || changeBusy.value || !changeWritable.value) return
  const ctx = currentInternshipContext(), epoch = changeEpoch, generation = currentSessionGeneration()
  const current = () => changeCurrent(epoch, generation, ctx)
  changeBusy.value = true; changeError.value = ''
  try {
    const result = await internshipCoreApi.withdrawChange(String(item.id), { ...ctx, expectedVersion: item.version })
    if (!current()) return
    changeReceipt.value = { ...result, actionLabel: '变更申请已撤回', statusLabel: changeStatusLabel(result.status) }; await loadChanges(1)
  } catch (e) { if (current()) changeError.value = changeErrorText(e) }
  finally { if (current()) changeBusy.value = false }
}
function captureLeaveContext() { return { ctx: currentInternshipContext(), epoch: changeEpoch, generation: currentSessionGeneration(), leavesEpoch: leaveEpoch } }
function leaveIsCurrent(t, visible = true) {
  return t.leavesEpoch === leaveEpoch && changeCurrent(t.epoch, t.generation, t.ctx)
    && (!visible || (tab.value === 'leave' && (typeof document === 'undefined' || !document.hidden)))
}
function invalidateLeave() { leaveEpoch++; leaveSourceSequence++; leaveReadSequence++; leaveOperation++; leaveReading.value = false; busy.value = false }
function leaveVisibilityChanged() { if (tab.value === 'leave') { invalidateLeave(); if (!document.hidden && my.value.hasData) loadTab('leave', true) } }
function resetLeaveDraft() {
  leaveBase.value = null; leaveConflict.value = false; leaveConflictRead.value = false; leaveFile.value = null
  Object.assign(leaveForm, { leaveType: 'SICK', startDate: '', endDate: '', reason: '', evidenceFileId: '', fileName: '' })
}
function cancelLeaveEdit() { if (!busy.value) { resetLeaveDraft(); leaveError.value = '' } }
function leaveStatusText(status) { return ({ PENDING: '审批中', APPROVED: '已通过', REJECTED: '已驳回', NEEDS_REVISION: '已退回，请补正', WITHDRAWN: '已撤回', OVERDUE: '超期未返岗', RETURNED: '已登记返岗' })[status] || '状态待核对' }
function leaveTypeText(type) { return ({ SICK: '病假', PERSONAL: '事假', OTHER: '其他' })[type] || '请假类型待核对' }
function leaveIsConflict(e) { return e?.bizCode === 'DATA_CONFLICT' || e?.status === 409 || Number(e?.code) === 409001 }
function assertLeave(row, t, id = row?.id) {
  if (!row || String(row.id) !== String(id) || String(row.batchId) !== String(t.ctx.batchId)
    || String(row.internshipId) !== String(t.ctx.internshipId) || !Number.isInteger(row.version) || row.version < 0) throw new Error('请假原单所属批次、实习或版本不一致，请重新读取')
}
async function openLeave(item) {
  if (!item?.id || busy.value) return
  const t = captureLeaveContext(), seq = ++leaveReadSequence
  leaveReading.value = true; leaveDetail.value = null
  try {
    const detail = await internshipCoreApi.leaveDetail(t.ctx, String(item.id))
    if (!leaveIsCurrent(t) || seq !== leaveReadSequence) return
    assertLeave(detail, t, item.id); leaveDetail.value = detail
    leaves.value = leaves.value.map(row => String(row.id) === String(detail.id) ? detail : row)
    return detail
  } catch (e) { if (leaveIsCurrent(t) && seq === leaveReadSequence) leaveError.value = '请假详情读取失败，请核对当前原单后重试' }
  finally { if (leaveIsCurrent(t) && seq === leaveReadSequence) leaveReading.value = false }
}
async function refreshLeaveAfterWrite(t, op, id) {
  const opened = String(leaveDetail.value?.id) === String(id)
  if (opened) leaveDetail.value = null
  await loadTab('leave', true)
  if (!leaveIsCurrent(t) || op !== leaveOperation) return
  busy.value = false
  if (opened && ['data', 'empty'].includes(sourceStates.leave.status)) await openLeave({ id })
}
async function editLeave(item) {
  if (!leaveWritable.value || busy.value || leaveConflict.value || !['REJECTED', 'NEEDS_REVISION'].includes(item?.status)) return
  if (leaveHasDraft.value) { leaveError.value = '请先完成当前草稿，或明确清除后再补正其他原单'; return }
  const detail = await openLeave(item)
  if (!detail || !leaveWritable.value || !['REJECTED', 'NEEDS_REVISION'].includes(detail.status)) return
  resetLeaveDraft(); leaveBase.value = { ...detail }; leaveError.value = ''; leaveReceipt.value = null
  Object.assign(leaveForm, { leaveType: detail.leaveType, startDate: detail.startDate, endDate: detail.endDate,
    reason: detail.reason || '', evidenceFileId: detail.evidenceFileId || '', fileName: detail.attachment?.fileName || '' })
}
async function rereadLeave() {
  if (busy.value) return
  const t = captureLeaveContext(), id = leaveBase.value?.id || returnDraft.id
  leaveConflictRead.value = false
  await loadTab('leave', true)
  if (!leaveIsCurrent(t) || !['data', 'empty'].includes(sourceStates.leave.status)) return
  if (id) await openLeave({ id })
  if (leaveIsCurrent(t) && (!id || String(leaveDetail.value?.id) === String(id))) leaveConflictRead.value = true
}
function continueLeaveAfterConflict() {
  if (busy.value || !leaveWritable.value || !leaveConflict.value || !leaveConflictRead.value) return
  if (leaveBase.value) {
    if (String(leaveDetail.value?.id) !== String(leaveBase.value.id) || !['REJECTED', 'NEEDS_REVISION'].includes(leaveDetail.value?.status)) return
    leaveBase.value = { ...leaveDetail.value }
  } else if (leaves.value.some(row => row.status === 'PENDING')) return
  leaveConflict.value = false; leaveConflictRead.value = false; leaveError.value = ''
}
function continueReturnAfterConflict() {
  if (busy.value || !leaveWritable.value || !returnDraft.conflict || !leaveConflictRead.value
    || String(leaveDetail.value?.id) !== returnDraft.id || !['APPROVED', 'OVERDUE'].includes(leaveDetail.value.status)) return
  returnDraft.version = leaveDetail.value.version; returnDraft.conflict = false; leaveConflictRead.value = false; leaveError.value = ''
}
async function submitLeave() {
  if (busy.value || !leaveWritable.value || leaveConflict.value) return
  leaveError.value = ''
  if (!leaveCanSubmit.value) { leaveError.value = '请核对有效起止日期、2至500字事由及安全可用的证明材料'; return }
  const t = captureLeaveContext(), op = ++leaveOperation, base = leaveBase.value
  const current = () => leaveIsCurrent(t) && op === leaveOperation
  const body = { ...t.ctx, leaveType: leaveForm.leaveType, startDate: leaveForm.startDate, endDate: leaveForm.endDate,
    reason: leaveForm.reason.trim(), fileId: leaveForm.evidenceFileId || '', expectedVersion: base?.version ?? 0 }
  busy.value = true
  try {
    const result = base ? await internshipCoreApi.resubmitLeave(String(base.id), body) : await internshipCoreApi.applyLeave(body)
    if (!current()) return
    resetLeaveDraft(); leaveReceipt.value = { ...result, statusLabel: leaveStatusText(result.status),
      actionLabel: base ? '原请假单已补正重交' : '请假申请已提交', nextStep: '等待当前责任人审批；全部必需节点通过后请假才生效，返岗时请及时办理销假。' }
    await refreshLeaveAfterWrite(t, op, result.id)
  } catch (e) {
    if (!current()) return
    if (leaveIsConflict(e)) { leaveConflict.value = true; leaveConflictRead.value = false }
    leaveError.value = leaveIsConflict(e) ? '原单或实习状态已变化，输入和原版本已保留，请重新读取后核对' : '提交未完成，填写内容已保留，请核对后重试'
  } finally { if (current()) busy.value = false }
}
async function uploadLeaveEvidence(event) {
  if (busy.value || !leaveWritable.value) return
  const file = event?.target?.files?.[0]
  if (!file) return
  if (Number(file.size || 0) > 20 * 1024 * 1024) { leaveError.value = '单个证明文件不能超过20MB'; return }
  const t = captureLeaveContext(), op = ++leaveOperation, current = () => leaveIsCurrent(t) && op === leaveOperation
  busy.value = true; leaveError.value = ''
  try {
    const uploaded = scanState(await fileSdk.upload(file, { bizType: 'INTERNSHIP' }))
    if (!current()) return
    if (!uploaded?.fileId) throw new Error('缺少文件标识')
    leaveFile.value = uploaded; leaveForm.evidenceFileId = uploaded.readyForBusiness === true ? String(uploaded.fileId) : ''
    leaveForm.fileName = uploaded.fileName || file.name || '请假证明'
  } catch (e) { if (current()) leaveError.value = '证明材料上传未完成，表单已保留，请重试' }
  finally { if (current()) { busy.value = false; if (event?.target) event.target.value = '' } }
}
async function refreshLeaveEvidence() {
  if (busy.value || !leaveWritable.value || !leaveFile.value) return
  const t = captureLeaveContext(), op = ++leaveOperation, original = leaveFile.value
  const current = () => leaveIsCurrent(t) && op === leaveOperation && original === leaveFile.value
  busy.value = true
  try {
    const updated = await refreshScanFiles([original], id => fileSdk.metadata(id), current)
    if (!updated || !current()) return
    leaveFile.value = updated[0]; leaveForm.evidenceFileId = updated[0].readyForBusiness ? String(updated[0].fileId) : ''
  } catch (e) { if (current()) leaveError.value = '证明安全状态读取失败，材料与填写内容已保留' }
  finally { if (leaveIsCurrent(t) && op === leaveOperation) busy.value = false }
}
async function downloadLeaveEvidence(fileId, fileName = '请假证明') {
  if (busy.value || !fileId) return
  const t = captureLeaveContext()
  try {
    const blob = await fetchFileBlob(`/files/download/${encodeURIComponent(String(fileId))}`)
    if (!leaveIsCurrent(t)) return
    const url = URL.createObjectURL(blob), link = document.createElement('a')
    link.href = url; link.download = fileName
    document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url)
  }
  catch (e) { if (leaveIsCurrent(t)) leaveError.value = '证明下载未完成，请重新读取原单后重试' }
}
async function withdrawLeave(item) {
  if (busy.value || leaveReading.value || !leaveWritable.value || item?.status !== 'PENDING') return
  const t = captureLeaveContext(), op = ++leaveOperation, current = () => leaveIsCurrent(t) && op === leaveOperation
  const id = String(item.id), version = item.version
  assertLeave(item, t); busy.value = true; leaveError.value = ''
  try {
    const result = await internshipCoreApi.withdrawLeave(id, { ...t.ctx, expectedVersion: version })
    if (!current()) return
    leaveReceipt.value = { ...result, statusLabel: leaveStatusText(result.status), actionLabel: '请假申请已撤回', nextStep: '本次申请已结束；如仍需请假，可重新提交。' }
    await refreshLeaveAfterWrite(t, op, id)
  } catch (e) { if (current()) leaveError.value = '撤回未完成，请重新读取原单核对后重试' }
  finally { if (current()) busy.value = false }
}
function openReturnLeave(item) {
  if (busy.value || leaveReading.value || !leaveWritable.value || returnDraft.id || !['APPROVED', 'OVERDUE'].includes(item?.status)) return
  if (leaveHasDraft.value) { leaveError.value = '请先完成或明确清除当前请假草稿，再办理销假'; return }
  assertLeave(item, captureLeaveContext())
  Object.assign(returnDraft, { id: String(item.id), note: '', version: item.version, conflict: false }); leaveError.value = ''
}
function closeReturnLeave() { if (!busy.value) Object.assign(returnDraft, { id: '', note: '', version: null, conflict: false }) }
async function confirmReturnLeave() {
  if (busy.value || leaveReading.value || !leaveWritable.value || !returnDraft.id || returnDraft.conflict || returnDraft.note.trim().length < 2 || returnDraft.note.trim().length > 500) return
  const t = captureLeaveContext(), op = ++leaveOperation, current = () => leaveIsCurrent(t) && op === leaveOperation
  const id = returnDraft.id, body = { ...t.ctx, note: returnDraft.note.trim(), expectedVersion: returnDraft.version }
  busy.value = true; leaveError.value = ''
  try {
    const result = await internshipCoreApi.returnLeave(id, body)
    if (!current()) return
    leaveReceipt.value = { ...result, statusLabel: leaveStatusText(result.status), actionLabel: '销假已登记', nextStep: '等待指导教师核实返岗并完成风险同步。' }
    Object.assign(returnDraft, { id: '', note: '', version: null, conflict: false }); await refreshLeaveAfterWrite(t, op, id)
  } catch (e) {
    if (!current()) return
    if (leaveIsConflict(e)) { returnDraft.conflict = true; leaveConflictRead.value = false }
    leaveError.value = '销假未完成，说明和原版本已保留，请重新读取原单后核对'
  } finally { if (current()) busy.value = false }
}
function agreementContextKey() { return [my.value.batchId, my.value.recordId || my.value.internshipId, !!my.value.historyMode, session.user?.tenantId, session.user?.userId].join('|') }
function agreementCapture(id) { return { id: String(id), key: agreementContextKey(), sequence: agreementSequence, generation: currentSessionGeneration() } }
function agreementCurrent(t) { return changeAlive && t.sequence === agreementSequence && t.generation === currentSessionGeneration() && t.key === agreementContextKey() && String(activeAgreement.value?.id) === t.id && tab.value === 'agreement' }
function assertAgreement(row, t) {
  if (!row || String(row.id) !== t.id || String(row.internId) !== String(my.value.recordId || my.value.internshipId) || String(row.batchId) !== String(my.value.batchId)) throw { bizCode: 'DATA_CONFLICT' }
}
function agreementErrorText(e) {
  if (e?.bizCode === 'DATA_CONFLICT' || e?.status === 409) return '协议已更新，原正文、版本和填写原因已保留。请重新打开正文核对后办理。'
  if (e?.status === 403 || e?.bizCode === 'NO_PERMISSION') return '当前账号无权办理这份协议，请联系学校核实。'
  return '操作未完成，请检查网络或稍后重试；已填写的原因仍保留。'
}
function agreementNextStep(status) { return ({ DRAFT: '学校尚未下发，请等待学校办理。', PENDING_STUDENT: '请阅读正文，核对后确认或提交无法确认原因。', PENDING_ENTERPRISE: '学生已确认，等待学校登记企业纸质签署材料。', PENDING_SCHOOL: '企业材料已登记，等待学校确认协议生效。', EFFECTIVE: '协议已生效；上岗仍由学校核对全部条件后办理。', REJECTED: '原因已交学校核实，请等待修订后的协议重新下发。', VOIDED: '本协议已作废，保留历史正文供查询。', ARCHIVED: '本协议已归档，保留历史正文供查询。' })[status] || '协议状态待学校核实，暂不能办理。' }
async function openAgreement(item) {
  if (!item?.id || agreementBusy.value || busy.value) return
  if (String(item.id) !== String(activeAgreement.value?.id)) { agreementReason.value = ''; agreementReceipt.value = null }
  activeAgreement.value = item; agreementDetail.value = null; agreementError.value = ''; agreementConflict.value = false
  agreementSequence++; const t = agreementCapture(item.id)
  agreementReading.value = true
  try {
    const detail = await internshipCoreApi.agreement(t.id)
    if (!agreementCurrent(t)) return
    assertAgreement(detail, t)
    agreementDetail.value = detail
    if (!detail.renderedBody?.trim()) agreementError.value = '学校尚未生成协议正文，请联系指导教师核实。'
  } catch (e) { if (agreementCurrent(t)) { agreementConflict.value = true; agreementError.value = agreementErrorText(e) } }
  finally { if (agreementCurrent(t)) agreementReading.value = false }
}
async function confirmAgreement(action) {
  if (!agreementCanAct.value || !['CONFIRM', 'REJECT'].includes(action) || document.hidden) return
  const reason = action === 'REJECT' ? agreementReason.value.trim() : ''
  if (action === 'REJECT' && reason.length < 5) { agreementError.value = '请填写至少5个字的具体原因。'; return }
  const t = agreementCapture(agreementDetail.value.id)
  const body = { ...currentInternshipContext(), action, reason, expectedVersion: agreementDetail.value.version }
  agreementBusy.value = true; agreementError.value = ''
  try {
    const accepted = await systemConfirm({ title: action === 'CONFIRM' ? '确认已阅读的协议' : '提交无法确认原因', message: action === 'CONFIRM' ? `请确认已阅读协议${t.id}第${body.expectedVersion}版正文，并核对企业和岗位；确认后交学校办理企业纸质签署材料。` : reason, confirmText: action === 'CONFIRM' ? '已阅读并确认' : '提交原因' })
    if (!accepted || !agreementCurrent(t) || document.hidden) return
    const result = await internshipCoreApi.confirmAgreement(t.id, body)
    if (!agreementCurrent(t)) return
    agreementDetail.value = { ...agreementDetail.value, ...result }
    agreements.value = agreements.value.map(item => String(item.id) === t.id ? { ...item, ...result } : item)
    agreementReceipt.value = { text: action === 'CONFIRM' ? '协议确认已提交' : '无法确认原因已提交', reason, readback: false }
    try {
      const [detail, list] = await Promise.all([internshipCoreApi.agreement(t.id), internshipCoreApi.agreements(body)])
      if (!agreementCurrent(t)) return
      assertAgreement(detail, t); agreementDetail.value = detail; agreements.value = rowsFrom(list)
      activeAgreement.value = agreements.value.find(x => String(x.id) === t.id) || detail
      agreementReceipt.value.readback = true
    } catch { if (agreementCurrent(t)) agreementError.value = '办理已提交，最新结果暂未读回。请重新打开协议核对，不必重复提交。' }
  } catch (e) { if (agreementCurrent(t)) { agreementConflict.value = e?.bizCode === 'DATA_CONFLICT' || e?.status === 409; agreementError.value = agreementErrorText(e) } }
  finally { if (agreementCurrent(t)) agreementBusy.value = false }
}
async function uploadInsurancePolicy(event) {
  if (busy.value || insuranceReadOnly.value) return
  const file = event?.target?.files?.[0]
  if (!file) return
  const epoch = insuranceEpoch
  busy.value = true
  try {
    const uploaded = await internshipCoreApi.uploadInsurancePolicy(file)
    if (epoch !== insuranceEpoch) return
    const fileId = uploaded?.fileId || uploaded?.id
    if (!fileId) throw new Error('上传响应缺少文件标识')
    const normalized = scanState(uploaded)
    if (!normalized.readyForBusiness) {
      pendingInsuranceFile.value = normalized
      ui.notify('保单已接收，请等待安全扫描后查看结果')
      return
    }
    pendingInsuranceFile.value = null
    insForm.fileId = String(fileId)
    ui.notify('保单文件已上传')
  } catch (e) {
    if (epoch === insuranceEpoch) insuranceError.value = e?.message || '保单上传失败，原材料已保留'
  } finally {
    busy.value = false
    if (event?.target) event.target.value = ''
  }
}
function closeInsuranceProof() { if(insuranceProof.value)URL.revokeObjectURL(insuranceProof.value.url);insuranceProof.value=null }
async function openInsuranceProof(download = false) {
  if(insuranceProofBusy.value || !insuranceMeta.value?.fileId)return
  const sequence=++insuranceProofSequence
  const t={ctx:currentInternshipContext(),epoch:insuranceEpoch,generation:currentSessionGeneration(),fileId:String(insuranceMeta.value.fileId),version:insuranceMeta.value.version}
  const current=()=>sequence===insuranceProofSequence && changeAlive && !document?.hidden && tab.value==='insurance' && t.epoch===insuranceEpoch && t.generation===currentSessionGeneration() && String(my.value.batchId)===String(t.ctx.batchId) && String(my.value.recordId || my.value.internshipId)===String(t.ctx.internshipId) && String(insuranceMeta.value?.fileId)===t.fileId && insuranceMeta.value?.version===t.version
  insuranceProofBusy.value=true;insuranceError.value=''
  try {
    const file=await fileSdk.metadata(t.fileId)
    if(!current())return
    if(String(file.fileId)!==t.fileId)throw new Error('凭证编号不一致')
    const image=/^image\/(png|jpeg|gif|webp)$/.test(file.mimeType || ''),pdf=file.mimeType==='application/pdf'
    if(!download && file.canPreview && (image || pdf)) {
      const blob=await fileSdk.fetchPreviewBlob(t.fileId)
      if(!current())return
      closeInsuranceProof();insuranceProof.value={url:URL.createObjectURL(blob),name:file.fileName || '保险凭证',image}
    } else if(file.canDownload) await fileSdk.download(t.fileId,file.fileName || '保险凭证')
    else insuranceError.value='当前凭证暂无可用读取授权，请联系学校核对。'
  } catch { if(current())insuranceError.value='保险凭证暂时无法读取，请重试；原保单记录仍保留。' }
  finally { if(current())insuranceProofBusy.value=false }
}
async function saveInsurance() {
  if (busy.value || insuranceConflict.value || insuranceReadOnly.value || pendingInsuranceFile.value) return
  insuranceError.value = ''
  if (insuranceMeta.value?.id && !Number.isInteger(insuranceMeta.value.version)) { insuranceError.value = '当前保单版本缺失，请重新读取后再提交。'; return }
  const epoch = insuranceEpoch
  busy.value = true
  try {
    await internshipCoreApi.saveInsurance({ ...insForm, ...currentInternshipContext(), expectedVersion: insuranceMeta.value?.version })
    if (epoch !== insuranceEpoch) return
    ui.notify('保险信息已提交'); await loadTab('insurance', true)
  } catch (e) {
    if (epoch !== insuranceEpoch) return
    insuranceConflict.value = Number(e?.code) === 409 || Math.floor(Number(e?.code) / 1000) === 409
    insuranceError.value = insuranceConflict.value ? '保单已被更新。填写内容已保留；重新读取会载入最新保单，请核对后再提交。' : (e?.message || '保险提交失败，填写内容已保留')
  } finally { busy.value = false }
}
async function changePlan() {
  if (busy.value || !selectedPlanId.value) return
  if (planHasDraft.value) { selectedPlanId.value = String(planMeta.value?.id || ''); return }
  await loadTab('plan', true)
}
function capturePlanContext() {
  return { ctx: currentInternshipContext(), epoch: changeEpoch, generation: currentSessionGeneration(), planId: String(planMeta.value?.id || '') }
}
function planIsCurrent(t) {
  return changeCurrent(t.epoch, t.generation, t.ctx) && tab.value === 'plan' &&
    t.planId === String(planMeta.value?.id || '') && t.planId === String(selectedPlanId.value || '')
}
async function openPlanAttachment(file) {
  const t = capturePlanContext()
  if (!file?.fileId || !planIsCurrent(t)) return
  try {
    const blob = await fetchFileBlob('/files/download/' + encodeURIComponent(String(file.fileId)))
    if (!planIsCurrent(t)) return
    const url = URL.createObjectURL(blob), link = document.createElement('a')
    link.href = url; link.download = file.fileName || '计划附件'
    document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url)
  } catch (e) { if (planIsCurrent(t)) ui.notify(e?.message || '计划附件下载未完成，请重试') }
}
async function uploadPlanTaskEvidence(event, task) {
  if (busy.value || !task || !planTasks.value.includes(task)) return
  const t = capturePlanContext()
  const file = event?.target?.files?.[0]
  if (!file) return
  if (Number(file.size || 0) > 20 * 1024 * 1024) {
    ui.notify('单个任务凭证不能超过20MB')
    if (event?.target) event.target.value = ''
    return
  }
  busy.value = true
  try {
    const uploaded = await internshipCoreApi.uploadPlanTaskEvidence(file)
    if (!planIsCurrent(t) || !planTasks.value.includes(task)) return
    const fileId = uploaded?.fileId || uploaded?.id
    if (!fileId) throw new Error('上传响应缺少文件标识')
    task._evidenceFileId = String(fileId)
    task._evidenceFileName = uploaded?.fileName || file.name || '任务凭证'
    ui.notify('任务凭证已上传')
  } catch (e) {
    if (planIsCurrent(t)) ui.notify(e?.message || '任务凭证上传失败')
  } finally {
    if (planIsCurrent(t)) busy.value = false
    if (event?.target) event.target.value = ''
  }
}
async function submitPlanTask(task) {
  if (busy.value || !task || !planMeta.value?.id || !planTasks.value.includes(task)) return
  const t = capturePlanContext()
  const note = String(task._note || '').trim()
  if (note.length < planTaskMinimumWords.value) return ui.notify(`完成说明至少 ${planTaskMinimumWords.value} 字`)
  busy.value = true
  try {
    await internshipCoreApi.submitPlanTask(task.sortOrder, {
      ...t.ctx,
      planId: t.planId,
      planVersion: planMeta.value.version,
      expectedVersion: Number(task.progressVersion ?? task.version ?? 0),
      studentNote: note,
      evidenceFileId: task._evidenceFileId || ''
    })
    if (!planIsCurrent(t)) return
    ui.notify('任务已提交，等待指导教师确认')
    await loadTab('plan', true)
  } catch (e) {
    if (planIsCurrent(t)) ui.notify(e?.message || '任务提交失败，填写内容已保留')
  } finally {
    if (planIsCurrent(t)) busy.value = false
  }
}
async function ackPlan() {
  if (busy.value || !planMeta.value?.id) return
  const t = capturePlanContext()
  busy.value = true
  try {
    await internshipCoreApi.acknowledgePlan({
      ...t.ctx,
      planId: t.planId,
      planVersion: planMeta.value?.version,
      expectedVersion: planMeta.value?.ackVersion
    })
    if (!planIsCurrent(t)) return
    ui.notify('已确认实习计划'); await loadTab('plan', true)
  } catch (e) { if (planIsCurrent(t)) ui.notify(e?.message || '确认失败') } finally { if (planIsCurrent(t)) busy.value = false }
}
function helpStatus(status){return ({PENDING_HANDLE:'待处理',PROCESSING:'处理中',RESOLVED:'已化解',CLOSED:'已关闭'})[status] || '状态待核对'}
function captureHelp(){return {ctx:currentInternshipContext(),epoch:helpEpoch,generation:currentSessionGeneration()}}
function helpCurrent(t){return changeAlive && !document?.hidden && tab.value==='help' && t.epoch===helpEpoch && t.generation===currentSessionGeneration() && String(my.value.batchId)===String(t.ctx.batchId) && String(my.value.recordId || my.value.internshipId)===String(t.ctx.internshipId)}
function helpVisibilityChanged(){if(tab.value!=='help')return;helpEpoch++;helpBusy.value=false;sourceStates.help.status='idle';if(!document.hidden)loadTab('help',true)}
async function submitHelp() {
  if(!helpCanSubmit.value)return
  const t=captureHelp(),body={...t.ctx,...helpForm}
  helpBusy.value=true;helpError.value='';helpReceipt.value=null
  try {
    const result=await portalApi.internshipHelp(body)
    if(!helpCurrent(t))return
    helpCommitted.value=true
    if(!/^\d+$/.test(String(result?.id || '')))throw new Error('办理结果需要重新读取核对')
    helpReceipt.value={id:String(result.id)}
    await loadTab('help',true)
    if(!helpCurrent(t))return
    if(sourceStates.help.status==='error'){helpError.value='求助已登记，进度暂未读回。请重新读取，不必重复提交。';return}
    helpForm.content='';helpForm.title=''
  } catch(error) {
    if(!helpCurrent(t))return
    if(error?.bizCode==='DATA_CONFLICT'){
      await loadTab('help',true)
      if(helpCurrent(t))helpError.value='已有求助单或办理状态发生变化，请核对原单进度；本次输入已保留。'
    }else helpError.value=helpCommitted.value?'求助可能已经登记，请重新读取核对，不要重复提交。':'求助暂未提交成功，输入已保留，请重试。'
  } finally {if(helpCurrent(t))helpBusy.value=false}
}
function reportDraftScope() {
  if (!my.value.hasData || !my.value.batchId || !(my.value.recordId || my.value.internshipId)) return ''
  const user = session.user, ctx = currentInternshipContext()
  return user?.userId && user?.tenantId && ctx.batchId && ctx.internshipId
    ? JSON.stringify([String(user.tenantId), String(user.userId), user.roleCode, String(ctx.batchId), String(ctx.internshipId)]) : ''
}
function saveReportDraft() {
  if (!my.value.hasData || loading.value || reportDraftGeneration !== currentSessionGeneration()
    || reportDraftContext !== reportDraftScope() || !reportDraftContext) return
  try {
    const storedProcessDrafts = { ...processDrafts, [processDraftKind]: { ...reportForm, base: processBase.value, conflict: processConflict.value } }
    const hasInput = Object.values(storedProcessDrafts).some(draft => draft.content || draft.attachments?.length) || weeklyForm.workContent || weeklyForm.harvestContent || weeklyForm.planContent || weeklyForm.attachments.length || reportForm.content || reportForm.attachments.length
    if (!hasInput) { sessionStorage.removeItem(REPORT_DRAFT_KEY); return }
    sessionStorage.setItem(REPORT_DRAFT_KEY, JSON.stringify({ scope: reportDraftContext, reportTab: reportTab.value,
      weeklyForm, reportForm, processDrafts: storedProcessDrafts, processDraftKind, weeklyBase: weeklyBase.value, processBase: processBase.value,
      weeklyConflict: weeklyConflict.value, processConflict: processConflict.value }))
  } catch { reportError.value = '本机草稿保存失败，刷新前请复制正文并保留附件名称。' }
}
function restoreReportDraft() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(REPORT_DRAFT_KEY) || 'null')
    if (!saved || saved.scope !== reportDraftContext || !reportTabs.includes(saved.reportTab)
      || !Array.isArray(saved.weeklyForm?.attachments) || !Array.isArray(saved.reportForm?.attachments)) return
    reportTab.value = saved.reportTab
    Object.assign(weeklyForm, saved.weeklyForm); Object.assign(reportForm, saved.reportForm)
    processDraftKind = ['DAILY','MONTHLY','SUMMARY'].includes(saved.processDraftKind) ? saved.processDraftKind : saved.reportTab==='日报'?'DAILY':saved.reportTab==='实习总结'?'SUMMARY':'MONTHLY'
    if (saved.processDrafts) Object.assign(processDrafts, saved.processDrafts)
    weeklyBase.value = saved.weeklyBase; processBase.value = saved.processBase
    // Restored originals keep their captured versions until the student explicitly compares the current original.
    weeklyConflict.value = !!(saved.weeklyConflict || saved.weeklyBase)
    processConflict.value = !!(saved.processConflict || saved.processBase)
  } catch { reportError.value = '本机草稿读取失败，请核对后继续填写。' }
}
watch(() => [reportTab.value, weeklyForm, reportForm, weeklyBase.value, processBase.value,
  weeklyConflict.value, processConflict.value], saveReportDraft, { deep: true })
function captureReportContext() {
  return { ctx: currentInternshipContext(), epoch: changeEpoch, generation: currentSessionGeneration(), reportsEpoch: reportEpoch }
}
function readReportPage(kind, result, context) {
  const items = rowsFrom(result)
  if ((result?.batchId != null && String(result.batchId) !== String(context.batchId))
    || (result?.internshipId != null && String(result.internshipId) !== String(context.internshipId))
    || items.some(row => (row.internshipId != null && String(row.internshipId) !== String(context.internshipId))
      || (kind !== 'WEEKLY' && row.reportType !== kind))) throw new Error('报告所属实习记录或类型不一致，请重新读取')
  const page = Number(result?.page || 1), total = Number(result?.total ?? items.length)
  return { items, page, total, hasMore: result?.hasMore === true }
}
async function loadMoreReports(kind) {
  if (busy.value || reportMoreBusy.value || !reportPages[kind]?.hasMore) return
  const t = captureReportContext(), seq = ++reportMoreSequence, nextPage = reportPages[kind].page + 1
  reportMoreBusy.value = true; reportError.value = ''
  try {
    const result = kind === 'WEEKLY' ? await internshipCoreApi.weeklyReports(t.ctx, nextPage, 20)
      : await internshipCoreApi.reports(t.ctx, nextPage, 20, kind)
    if (!reportIsCurrent(t) || seq !== reportMoreSequence) return
    const page = readReportPage(kind, result, t.ctx)
    if (page.page !== nextPage) throw new Error('报告分页位置已变化，请重新读取')
    const key = kind === 'WEEKLY' ? 'weeklyReports' : 'processReports'
    my.value[key] = [...new Map([...(my.value[key] || []), ...page.items].map(row => [String(row.id), row])).values()]
    reportPages[kind] = { page: page.page, total: page.total, hasMore: page.hasMore }
  } catch (error) {
    if (reportIsCurrent(t) && seq === reportMoreSequence) reportError.value = error?.message || '后续报告读取失败，原有记录和填写内容已保留'
  } finally { if (reportIsCurrent(t, false) && seq === reportMoreSequence) reportMoreBusy.value = false }
}
function reportIsCurrent(t, visible = true) {
  return reportEpoch === t.reportsEpoch && changeCurrent(t.epoch, t.generation, t.ctx)
    && (!visible || (tab.value === 'report' && (typeof document === 'undefined' || !document.hidden)))
}
function reportVisibilityChanged() {
  if (tab.value !== 'report') return
  reportEpoch++; weeklyReadSequence++; reportSourceSequence++; weeklyReading.value = false; busy.value = false
  reportMoreSequence++; reportMoreBusy.value = false
  processReadSequence++; processReading.value = false
  if (!document.hidden && my.value.hasData) loadTab('report', true)
}
function saveReportBlob(blob, filename, t) {
  if (!reportIsCurrent(t)) return
  const url = URL.createObjectURL(blob), link = document.createElement('a')
  link.href = url; link.download = filename
  document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url)
}
async function openWeekly(item) {
  if (!item?.id || busy.value) return
  const t = captureReportContext(), seq = ++weeklyReadSequence
  weeklyReading.value = true; weeklyDetail.value = null
  try {
    const detail = await internshipCoreApi.weeklyReportDetail(t.ctx, String(item.id))
    if (!reportIsCurrent(t) || seq !== weeklyReadSequence) return
    if (String(detail?.id) !== String(item.id) || String(detail.batchId) !== String(t.ctx.batchId)
      || String(detail.internshipId) !== String(t.ctx.internshipId)) throw new Error('周报所属实习记录不一致，请重新打开当前原单')
    weeklyDetail.value = detail
    reportReceipt.value = null
    reportReadMode.value = !weeklyConflict.value
    if (reportReadMode.value) updateReportLink('WEEKLY', detail.id)
    my.value.weeklyReports = (my.value.weeklyReports || []).map(row => String(row.id) === String(detail.id) ? detail : row)
  } catch (e) { if (reportIsCurrent(t) && seq === weeklyReadSequence) reportError.value = e?.message || '周报正文读取失败，填写内容已保留' }
  finally { if (reportIsCurrent(t) && seq === weeklyReadSequence) weeklyReading.value = false }
}
async function openProcessReport(item) {
  if (!item?.id || busy.value) return
  const t = captureReportContext(), seq = ++processReadSequence, expectedType = item.reportType || processType.value
  processReading.value = true; processDetail.value = null
  try {
    const detail = await internshipCoreApi.processReportDetail(t.ctx, String(item.id))
    if (!reportIsCurrent(t) || seq !== processReadSequence) return
    if (String(detail?.id) !== String(item.id) || String(detail.batchId) !== String(t.ctx.batchId)
      || String(detail.internshipId) !== String(t.ctx.internshipId) || detail.reportType !== expectedType) throw new Error('报告所属实习记录或类型不一致，请重新打开当前原单')
    processDetail.value = detail
    reportReceipt.value = null
    reportReadMode.value = !processConflict.value
    if (reportReadMode.value) updateReportLink(detail.reportType, detail.id)
    my.value.processReports = (my.value.processReports || []).map(row => String(row.id) === String(detail.id) ? detail : row)
  } catch (e) { if (reportIsCurrent(t) && seq === processReadSequence) reportError.value = e?.message || '报告正文读取失败，填写内容已保留' }
  finally { if (reportIsCurrent(t) && seq === processReadSequence) processReading.value = false }
}
function continueWeeklyAfterConflict() {
  const latest = weeklyDetail.value
  if (busy.value || !weeklyConflict.value || latest?.status !== 'RETURNED'
    || Number(latest.weekNo || latest.week) !== Number(weeklyForm.week)
    || (weeklyBase.value && String(latest.id) !== String(weeklyBase.value.id))) return
  weeklyBase.value = { ...latest }; weeklyConflict.value = false; reportError.value = ''; reportReadMode.value = false
}
async function rereadWeeklyAfterConflict() {
  if (busy.value || !weeklyConflict.value) return
  const t = captureReportContext()
  let original = weeklyBase.value || (my.value.weeklyReports || []).find(row => Number(row.weekNo || row.week) === Number(weeklyForm.week))
  if (!original) {
    await loadTab('report', true)
    if (!reportIsCurrent(t) || sourceStates.report.status === 'error') return
    original = (my.value.weeklyReports || []).find(row => Number(row.weekNo || row.week) === Number(weeklyForm.week))
  }
  if (original) await openWeekly(original)
  else reportError.value = '当前列表尚未读到该周原单，填写内容已保留，请继续加载记录后重新核对'
}
async function rereadProcessReport() {
  if (busy.value || !processConflict.value) return
  const t = captureReportContext()
  processLatest.value = null
  let original = processBase.value || (my.value.processReports || []).find(row => row.reportType === processType.value
    && row.periodKey === (processType.value === 'SUMMARY' ? 'FINAL' : reportForm.periodKey))
  if (!original) {
    await loadTab('report', true)
    if (!reportIsCurrent(t) || sourceStates.report.status === 'error') return
    original = (my.value.processReports || []).find(row => row.reportType === processType.value
      && row.periodKey === (processType.value === 'SUMMARY' ? 'FINAL' : reportForm.periodKey))
  }
  if (!original) { reportError.value = '填写内容已保留，请继续加载记录，找到该周期原单后重新核对'; return }
  await openProcessReport(original)
  if (reportIsCurrent(t) && String(processDetail.value?.id) === String(original.id)) processLatest.value = { ...processDetail.value }
}
function continueProcessAfterConflict() {
  if (busy.value || !processConflict.value || processLatest.value?.status !== 'RETURNED'
    || (processBase.value && String(processLatest.value.id) !== String(processBase.value.id))) return
  processBase.value = { ...processLatest.value }; processLatest.value = null; processConflict.value = false; reportError.value = ''
}
async function downloadReportPdf(kind, row) {
  if (busy.value || !row?.id) return
  busy.value = true
  reportError.value = ''
  const t = captureReportContext()
  try {
    const data = await internshipCoreApi.reportPdf(t.ctx, kind, row.id)
    if (!reportIsCurrent(t)) return
    const raw = atob(String(data?.contentBase64 || ''))
    const bytes = new Uint8Array(raw.length)
    for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i)
    const blob = new Blob([bytes], { type: data?.mediaType || 'application/pdf' })
    saveReportBlob(blob, data?.filename || '实习报告.pdf', t)
    ui.notify('报告文档已生成')
  } catch (e) {
    if (!reportIsCurrent(t)) return
    reportError.value = e?.message || '报告文档生成失败'
    ui.notify(reportError.value)
  } finally {
    if (reportIsCurrent(t)) busy.value = false
  }
}
async function uploadReportAttachment(event, target) {
  const input = event?.target
  const file = input?.files?.[0]
  if (!file || busy.value) return
  busy.value = true
  reportError.value = ''
  const epoch = attachmentEpoch
  const t = captureReportContext()
  const list = target === 'weekly' ? weeklyForm.attachments : reportForm.attachments
  try {
    const uploaded = await fileSdk.upload(file, { bizType: 'INTERNSHIP_REPORT' })
    if (!reportIsCurrent(t) || epoch !== attachmentEpoch || list !== (target === 'weekly' ? weeklyForm.attachments : reportForm.attachments)) return
    if (!uploaded?.fileId) throw new Error('附件上传响应缺少文件标识')
    if (!list.some((item) => String(item.fileId) === String(uploaded.fileId))) {
      list.push({
        ...scanState(uploaded),
        fileId: String(uploaded.fileId),
        fileName: uploaded.fileName || file.name || '报告附件',
        mimeType: uploaded.mimeType || file.type || '',
        sizeBytes: Number(uploaded.sizeBytes || file.size || 0),
        ext: uploaded.ext || ''
      })
    }
    ui.notify(uploaded.readyForBusiness ? '报告附件已上传' : '附件已接收，请等待安全扫描后查看结果')
  } catch (e) {
    if (!reportIsCurrent(t) || epoch !== attachmentEpoch) return
    reportError.value = e?.bizCode === 'FILE_ZIP_REJECTED'
      ? '压缩包未通过安全检查，已拒绝上传。请检查内容并重新打包后再试，报告正文和原有附件已保留。'
      : (e?.message || '报告附件上传失败')
    ui.notify(reportError.value)
  } finally {
    if (reportIsCurrent(t)) busy.value = false
    if (input) input.value = ''
  }
}
function removeReportAttachment(target, index) {
  if (busy.value) return
  const list = target === 'weekly' ? weeklyForm.attachments : reportForm.attachments
  list.splice(index, 1)
}
async function refreshPendingInsurance() {
  if (busy.value || !pendingInsuranceFile.value) return
  const epoch = insuranceEpoch
  const original = pendingInsuranceFile.value
  busy.value = true
  insuranceError.value = ''
  try {
    const refreshed = await refreshScanFiles([original], id => fileSdk.metadata(id),
      () => epoch === insuranceEpoch && original === pendingInsuranceFile.value)
    if (!refreshed) return
    pendingInsuranceFile.value = refreshed[0]
    if (refreshed[0].readyForBusiness) {
      insForm.fileId = refreshed[0].fileId
      pendingInsuranceFile.value = null
      ui.notify('保单安全扫描通过，可提交核验')
    }
  } catch (e) {
    if (epoch === insuranceEpoch) insuranceError.value = '扫描结果读取失败，保单和填写内容已保留，请重试'
  } finally { busy.value = false }
}
async function refreshReportScans(target) {
  if (busy.value) return
  const form = target === 'weekly' ? weeklyForm : reportForm
  const original = form.attachments
  const epoch = attachmentEpoch
  const t = captureReportContext()
  busy.value = true
  reportError.value = ''
  try {
    const refreshed = await refreshScanFiles(original, id => fileSdk.metadata(id),
      () => reportIsCurrent(t) && epoch === attachmentEpoch && original === form.attachments)
    if (refreshed) form.attachments = refreshed
  } catch (e) {
    if (reportIsCurrent(t) && epoch === attachmentEpoch) reportError.value = '扫描结果读取失败，正文和附件已保留，请重试'
  } finally { if (reportIsCurrent(t)) busy.value = false }
}
async function openReportAttachment(file) {
  const t = captureReportContext()
  try {
    const mime = String(file?.mimeType || '').toLowerCase()
    const ext = String(file?.ext || file?.fileName?.split('.').pop() || '').toLowerCase()
    if (mime.startsWith('image/') || mime.startsWith('video/') || ext === 'pdf') {
      const blob = await fileSdk.fetchPreviewBlob(String(file.fileId))
      if (!reportIsCurrent(t)) return
      const url = URL.createObjectURL(blob)
      window.open(url, '_blank', 'noopener,noreferrer')
      setTimeout(() => URL.revokeObjectURL(url), 60000)
    } else {
      const blob = await fetchFileBlob('/files/download/' + encodeURIComponent(String(file.fileId)))
      saveReportBlob(blob, file.fileName || '报告附件', t)
    }
  } catch (e) {
    if (reportIsCurrent(t)) ui.notify(e?.message || '报告附件打开失败')
  }
}
function clearReportLink() {
  if (!route.query.reportId && !route.query.reportType) return
  const query={...route.query};delete query.reportId;delete query.reportType
  router.replace({query})
}
function updateReportLink(kind,id) {
  if (String(route.query.reportId || '')===String(id) && route.query.reportType===kind) return
  router.replace({query:{...route.query,view:'report',batchId:String(my.value.batchId),reportType:kind,reportId:String(id)}})
}
function cancelReportRead() { weeklyReadSequence++;processReadSequence++;weeklyReading.value=false;processReading.value=false;reportFocusTarget='';reportReadMode.value=false }
function returnToReportDraft() { cancelReportRead();clearReportLink() }
function focusReportFromRoute() {
  if (loading.value || tab.value!=='report' || !my.value.hasData || !['data','empty'].includes(sourceStates.report.status)) return
  const kind=String(route.query.reportType || ''),id=String(route.query.reportId || '')
  if (!id && !kind) { if(reportFocusTarget)cancelReportRead();return }
  if (!reportKinds.includes(kind) || !/^\d+$/.test(id) || /^0+$/.test(id)) { cancelReportRead();reportError.value='报告链接不完整，请从右侧记录打开原单';return }
  if (route.query.batchId && String(route.query.batchId)!==String(my.value.batchId)) { cancelReportRead();reportError.value='请先选择原单所属实习批次';return }
  const selected=kind==='WEEKLY'?weeklyDetail.value:processDetail.value
  const target=JSON.stringify([String(my.value.batchId),kind,id])
  if ((String(selected?.id)===id && reportReadMode.value && (kind==='WEEKLY'?reportTab.value==='周报':selected.reportType===kind)) || (reportFocusTarget===target && (kind==='WEEKLY'?weeklyReading.value:processReading.value))) return
  const label={WEEKLY:'周报',DAILY:'日报',MONTHLY:'月报',SUMMARY:'实习总结'}[kind]
  if (reportTab.value!==label) switchReportTab(label,true)
  reportFocusTarget=target
  if (kind==='WEEKLY') openWeekly({id});else openProcessReport({id})
}
watch(() => [route.query.reportId,route.query.reportType,route.query.batchId,loading.value,sourceStates.report.status],focusReportFromRoute)
function switchReportTab(value, fromRoute = false) {
  if (!reportTabs.includes(value) || busy.value) return
  processDrafts[processDraftKind] = { ...reportForm, attachments: reportForm.attachments.map(file => ({...file})), base: processBase.value, conflict: processConflict.value }
  reportTab.value = value
  reportReadMode.value = false
  if (!fromRoute) clearReportLink()
  reportError.value = ''
  weeklyReadSequence++; weeklyReading.value = false; weeklyDetail.value = null
  processReadSequence++; processReading.value = false; processDetail.value = null
  if (value !== '周报') {
    processDraftKind = processType.value
    const draft = processDrafts[processDraftKind]
    if (draft) { Object.assign(reportForm, {periodKey:draft.periodKey, content:draft.content, attachments:draft.attachments.map(file=>({...file}))}); processBase.value=draft.base || null; processConflict.value=!!draft.conflict; return }
    Object.assign(reportForm,{content:'',attachments:[]}); processBase.value=null; processConflict.value=false
  }
  if (value === '日报') {
    const now = new Date()
    reportForm.periodKey = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  }
  if (value === '月报') reportForm.periodKey = currentMonth()
  if (value === '实习总结') reportForm.periodKey = 'FINAL'
}
function editWeekly(item) {
  if (busy.value || my.value.historyMode || item?.status !== 'RETURNED') return
  if (weeklyConflict.value) { reportError.value = '填写内容已保留，请读取最新原单核对后继续修改'; return }
  if (String(item.internshipId) !== String(currentInternshipContext().internshipId)) return
  reportReadMode.value = false; clearReportLink()
  weeklyBase.value = { ...item }
  Object.assign(weeklyForm, {
    week: Number(item.weekNo || item.week),
    workContent: item.workContent || '',
    harvestContent: item.harvestContent || '',
    planContent: item.planContent || '',
    attachments: Array.isArray(item.attachments) ? item.attachments.map((file) => ({ ...file })) : []
  })
  reportError.value = ''
  reportReceipt.value = null
}
function editProcessReport(item) {
  if (busy.value || my.value.historyMode || item?.status !== 'RETURNED' || processConflict.value) return
  reportReadMode.value = false; clearReportLink()
  processDrafts[processDraftKind] = { ...reportForm, base:processBase.value, conflict:processConflict.value }
  processDraftKind = item.reportType
  processBase.value = { ...item }
  reportReceipt.value = null
  reportTab.value = item.reportType === 'SUMMARY' ? '实习总结' : item.reportType === 'DAILY' ? '日报' : '月报'
  Object.assign(reportForm, {
    periodKey: item.periodKey || (item.reportType === 'SUMMARY' ? 'FINAL' : currentMonth()),
    content: item.content || '',
    attachments: Array.isArray(item.attachments) ? item.attachments.map((file) => ({ ...file })) : []
  })
  reportError.value = ''
}
async function submitWeekly() {
  if (busy.value || weeklyConflict.value || !scanFilesReady(weeklyForm.attachments)) return
  if (!weeklyCanSubmit.value) { reportError.value = '请核对当前原单、周次和正文；每段不超过2000字，正文合计至少' + Number(reportRules.value.weeklyMinWords ?? 30) + '字'; return }
  const existing = weeklyEditing.value ? weeklyBase.value : null
  await submitReportCommand({ ...currentInternshipContext(), expectedVersion: existing?.version ?? 0,
    weekNo: weeklyForm.week, workContent: weeklyForm.workContent, harvestContent: weeklyForm.harvestContent,
    planContent: weeklyForm.planContent, attachmentFileIds: weeklyForm.attachments.map(file => String(file.fileId)) }, '周报', existing)
}
async function submitReport() {
  if (busy.value || processConflict.value || !scanFilesReady(reportForm.attachments)) return
  if (!reportCanSubmit.value) {
    reportError.value = ['DAILY', 'MONTHLY'].includes(processType.value) && !reportForm.periodKey
      ? (processType.value === 'DAILY' ? '请选择报告日期。' : '请选择报告月份。')
      : reportTab.value + '正文至少填写 ' + reportMinimum.value + ' 字。'
    return
  }
  const reportType = processType.value, periodKey = reportType === 'SUMMARY' ? 'FINAL' : reportForm.periodKey
  const existing = processEditing.value ? processBase.value : null
  if (!existing && processReportRows.value.some(row => row.periodKey === periodKey)) { reportError.value = '该周期已有记录，请从原单按意见修改'; return }
  await submitReportCommand({ ...currentInternshipContext(), reportType, periodKey, content: reportForm.content,
    attachmentFileIds: reportForm.attachments.map(file => String(file.fileId)), expectedVersion: existing?.version ?? 0 }, reportTab.value, existing)
}
async function submitReportCommand(payload, label, existing) {
  const t = captureReportContext(), weekly = label === '周报'
  reportError.value = ''; busy.value = true
  try {
    const result = weekly ? await internshipCoreApi.submitWeeklyReport(payload) : await internshipCoreApi.submitReport(payload)
    if (!reportIsCurrent(t)) return
    const listKey = weekly ? 'weeklyReports' : 'processReports'
    const rows = my.value[listKey] || [], row = { ...existing, ...result }
    my.value[listKey] = rows.some(item => String(item.id) === String(row.id))
      ? rows.map(item => String(item.id) === String(row.id) ? row : item) : [row, ...rows]
    reportReceipt.value = { ...result, version: result.reportVersion ?? result.version,
      statusLabel: '待批阅', actionLabel: label + (existing ? '已重新提交' : '已提交'),
      nextStep: '已提交，等待指导教师批阅；退回后从原单继续修改。' }
    ui.notify(reportReceipt.value.actionLabel)
    if (weekly) {
      weeklyBase.value = null; weeklyDetail.value = null
      Object.assign(weeklyForm, { week: null, workContent: '', harvestContent: '', planContent: '', attachments: [] })
    } else {
      processBase.value = null
      Object.assign(reportForm, { periodKey: payload.periodKey, content: '', attachments: [] })
    }
    await loadTab('report', true)
    if (reportIsCurrent(t) && sourceStates.report.status === 'error') reportReceipt.value.nextStep = '已提交，最新结果回读失败；请重新读取记录，不必重复提交。'
  } catch (e) {
    if (!reportIsCurrent(t)) return
    const conflict = e?.bizCode === 'DATA_CONFLICT' || e?.code === 'DATA_CONFLICT' || Number(e?.status || e?.statusCode) === 409 || Number(e?.code) === 409001
    if (conflict) { if (weekly) weeklyConflict.value = true; else processConflict.value = true }
    reportError.value = conflict ? '原单已变化，填写内容与读取版本已保留，请先重新读取核对' : e?.message || `${label}提交失败，填写内容已保留`
    ui.notify(reportError.value)
  } finally { if (reportIsCurrent(t)) { busy.value = false; saveReportDraft() } }
}
function latestFormalDocument(type) {
  return formalDocuments.value
    .filter((item) => item.documentType === type && item.status === 'GENERATED')
    .sort((a, b) => Number(b.documentVersion || 0) - Number(a.documentVersion || 0))[0] || null
}
async function downloadPackedPdf(data, fallbackName) {
  const raw = atob(String(data?.contentBase64 || ''))
  const bytes = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i)
  const blob = new Blob([bytes], { type: data?.mediaType || 'application/pdf' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = data?.filename || fallbackName
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
async function generateFormalDocument(type) {
  if (busy.value) return
  busy.value = true
  try {
    const row = await internshipCoreApi.generateFormalDocument(currentInternshipContext(), type)
    ui.notify(row?.reused ? '正式文书已是最新版本' : '正式文书已生成')
    formalDocuments.value = rowsFrom(await internshipCoreApi.formalDocuments(currentInternshipContext()))
    await downloadFormalDocument(row)
  } catch (e) {
    ui.notify(e?.message || '正式文书生成失败')
  } finally {
    busy.value = false
  }
}
async function downloadFormalDocument(row) {
  if (!row?.id) return
  try {
    const data = await internshipCoreApi.formalDocumentPdf(currentInternshipContext(), row.id)
    await downloadPackedPdf(data, (row.documentTypeLabel || '岗位实习正式文书') + '.pdf')
  } catch (e) {
    ui.notify(e?.message || '正式文书下载失败')
  }
}
async function submitSelfEval() {
  if(busy.value||!evalCanEdit.value||evalForm.performance.trim().length<20)return
  const ctx=currentInternshipContext(),epoch=changeEpoch,generation=currentSessionGeneration(),current=()=>changeCurrent(epoch,generation,ctx)
  busy.value = true
  try {
    const result = await internshipCoreApi.submitSelfEval({
      ...ctx,
      expectedVersion: selfEvalMeta.value?.version ?? 0,
      selfSummary: evalForm.performance,
      selfHarvest: evalForm.reflection,
      selfProblem: evalForm.problems,
      enterpriseRating: evalForm.enterpriseRating,
      enterpriseFeedback: evalForm.enterpriseFeedback,
      positionRating: evalForm.positionRating,
      positionFeedback: evalForm.positionFeedback
    })
    if(!current())return
    evalReceipt.value = { actionLabel: '学生自评已提交', id: result?.id || '', version: result?.version,
      statusLabel: result?.reviewStatusLabel || result?.reviewStatus || '待审核', nextStep: '等待导师填写评价并由学校审核' }
    ui.notify('自评已提交');evalBaseline.value=JSON.stringify(evalForm);await loadTab('eval', true)
  } catch (e) { if(current()){if(e?.bizCode==='DATA_CONFLICT')evalConflict.value=true;ui.notify(e?.message || '自评提交失败，填写内容已保留')} } finally { if(current())busy.value = false }
}
async function adoptLatestEvaluation(){
  if(busy.value)return
  const ctx=currentInternshipContext(),epoch=changeEpoch,generation=currentSessionGeneration()
  if(!await systemConfirm({title:'采用最新鉴定',message:'这会以最新已保存记录替换当前未提交输入，请先确认已保留需要的内容。',confirmText:'采用最新鉴定'}))return
  if(!changeCurrent(epoch,generation,ctx))return
  evalBaseline.value=JSON.stringify(evalForm);evalConflict.value=false
  await loadTab('eval',true)
}
async function submitAppeal() {
  busy.value = true
  try {
    const result = await portalApi.internshipScoreAppeal({ ...currentInternshipContext(), reason: appealReason.value })
    evalReceipt.value = { actionLabel: '成绩申诉已提交', id: result?.id || '', version: result?.version,
      statusLabel: result?.statusLabel || '待处理',
      nextStep: `学校处理时将校验成绩编号 ${result?.scoreId || '—'} 的 v${result?.scoreVersion ?? '—'} 快照` }
    ui.notify('成绩申诉已提交')
    appealReason.value = ''
    appealMeta.value = await portalApi.internshipScoreAppealStatus(currentInternshipContext())
  }
  catch (e) { ui.notify(e?.message || '提交失败') } finally { busy.value = false }
}
async function printAgreement() {
  if (!agreementCanPrint.value || document.hidden) return
  const t = agreementCapture(agreementDetail.value.id), body = { ...currentInternshipContext(), expectedVersion: agreementDetail.value.version }
  agreementBusy.value = true; agreementError.value = ''
  try {
    const data = await internshipCoreApi.agreementPdf(t.id, body)
    if (!agreementCurrent(t) || document.hidden) return
    if (String(data?.agreementId) !== t.id || data.agreementVersion !== body.expectedVersion || String(data.batchId) !== String(body.batchId) || String(data.internshipId) !== String(body.internshipId) || data.mediaType !== 'application/pdf') throw { bizCode: 'DATA_CONFLICT' }
    const raw = atob(data.contentBase64 || '')
    if (!raw.startsWith('%PDF-')) throw new Error('Invalid agreement PDF')
    const bytes = Uint8Array.from(raw, char => char.charCodeAt(0))
    const url = URL.createObjectURL(new Blob([bytes], { type: 'application/pdf' })), link = document.createElement('a')
    try { link.href = url; link.download = data.filename; document.body.appendChild(link); link.click() }
    finally { link.remove(); setTimeout(() => URL.revokeObjectURL(url), 60000) }
    ui.notify('已下载当前协议版本的打印件，可打开后打印；下载已留痕。')
  } catch (e) { if (agreementCurrent(t)) { agreementConflict.value = e?.bizCode === 'DATA_CONFLICT' || e?.status === 409; agreementError.value = agreementErrorText(e) } }
  finally { if (agreementCurrent(t)) agreementBusy.value = false }
}
onBeforeUnmount(() => { closeInsuranceProof(); invalidateApplication(); saveReportDraft(); if (typeof window !== 'undefined') window.removeEventListener('beforeunload', saveReportDraft); changeAlive = false; changeEpoch++; loadSequence++; reportEpoch++; invalidateLeave(); if (typeof document !== 'undefined') { document.removeEventListener?.('visibilitychange', reportVisibilityChanged); document.removeEventListener?.('visibilitychange', leaveVisibilityChanged); document.removeEventListener?.('visibilitychange', applicationVisibilityChanged); document.removeEventListener?.('visibilitychange', intentionVisibilityChanged); document.removeEventListener?.('visibilitychange', helpVisibilityChanged) } })
onMounted(() => { if (typeof window !== 'undefined') window.addEventListener('beforeunload', saveReportDraft); if (typeof document !== 'undefined') { document.addEventListener?.('visibilitychange', reportVisibilityChanged); document.addEventListener?.('visibilitychange', leaveVisibilityChanged); document.addEventListener?.('visibilitychange', applicationVisibilityChanged); document.addEventListener?.('visibilitychange', intentionVisibilityChanged); document.addEventListener?.('visibilitychange', helpVisibilityChanged) } return load() })
</script>

<style scoped>
.eval-fields{border:0;margin:0;padding:0;min-width:0}
.report-full-text{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.7}.report-feedback details{margin-top:12px}.report-feedback summary{cursor:pointer}
.sp-plan-switch{margin-bottom:14px}.sp-plan-task-list{display:grid;gap:10px}.sp-plan-task{padding:14px;border:1px solid var(--line);border-radius:10px;background:var(--bg2)}.sp-plan-task__head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px}.sp-plan-task__head strong{font-size:14px;color:var(--t1)}.sp-plan-task__head p{margin:5px 0 0;color:var(--t3);font-size:12px;line-height:1.6;white-space:pre-wrap}.sp-plan-tasks{margin-top:14px}.sp-report-progress{margin-bottom:14px}.sp-report-progress__grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.sp-report-progress__item{padding:12px;border:1px solid var(--line);border-radius:10px;background:var(--bg2)}.sp-report-progress__row{display:flex;justify-content:space-between;gap:10px;font-size:12px}.sp-report-progress__row span{color:var(--t3)}.sp-report-progress__track{height:7px;margin-top:9px;border-radius:999px;background:#e8edf5;overflow:hidden}.sp-report-progress__track span{display:block;height:100%;border-radius:999px;background:var(--pri)}@media(max-width:900px){.sp-report-progress__grid{grid-template-columns:1fr 1fr}}
.sp-now { display: flex; align-items: center; justify-content: space-between; gap: 28px; margin-bottom: 14px; padding: 20px 22px; border-color: color-mix(in srgb, var(--pri) 28%, var(--line)); background: linear-gradient(120deg, color-mix(in srgb, var(--pri) 8%, white), white 68%); box-shadow: 0 12px 32px rgba(30, 64, 175, .08); }
.sp-now__copy { min-width: 0; }
.sp-now__eyebrow { color: var(--pri); font-size: 10px; font-weight: 800; letter-spacing: .12em; }
.sp-now h2 { margin: 4px 0 5px; color: var(--t1); font-size: 19px; }
.sp-now p { margin: 0; color: var(--t2); font-size: 13px; line-height: 1.6; }
.sp-now__meta { display: flex; flex-wrap: wrap; gap: 8px 18px; margin-top: 9px; color: var(--t4); font-size: 12px; }
.sp-source-state { margin-bottom: 14px; border: 1px solid var(--line); border-radius: 12px; background: var(--card, #fff); overflow: hidden; }
.sp-source-state--error { padding-bottom: 14px; border-color: color-mix(in srgb, var(--danger-fg) 28%, var(--line)); }
.sp-source-state--error .sp-btn { margin-left: 16px; }
.sp-process-nav { display:flex; gap:8px; margin-bottom:18px; align-items:flex-start; }
.sp-process-group { flex:1; min-width:0; border:1px solid var(--line); border-radius:10px; background:var(--card,#fff); }
.sp-process-group[open] { flex:2.2; min-width:320px; border-color:color-mix(in srgb,var(--pri) 28%,var(--line)); }
.sp-process-group summary { display: flex; align-items: center; justify-content: space-between; gap: 10px; min-height: 44px; padding: 8px 10px; cursor: pointer; list-style: none; }
.sp-process-group summary::-webkit-details-marker { display: none; }
.sp-process-group summary span:first-child { display: flex; flex-direction: column; min-width: 0; }
.sp-process-group summary b { color: var(--t1); font-size: 13px; }
.sp-process-group summary small { display:none; overflow: hidden; margin-top: 2px; color: var(--t4); font-size: 10px; white-space: nowrap; text-overflow: ellipsis; }
.sp-process-group__current { flex: none; color: var(--pri); font-size: 11px; font-weight: 600; }
.sp-process-group__items { display: flex; flex-wrap: wrap; gap: 4px; padding: 0 8px 8px; }
.sp-process-group__items button { min-height: 32px; padding: 0 8px; border: 1px solid var(--line); border-radius: 9px; background: #fff; color: var(--t2); cursor: pointer; }
.sp-process-group__items button:hover { border-color: var(--pri); color: var(--pri); }
.sp-process-group__items button.is-active { border-color: color-mix(in srgb, var(--pri) 35%, white); background: var(--pri-50); color: var(--pri); font-weight: 600; }
.pill { display: inline-flex; align-items: center; gap: 5px; height: 26px; padding: 0 10px; background: #F5F7FA; border: 1px solid #EDEFF3; border-radius: 7px; font-size: 12.5px; color: var(--t2); }
.statepill { display: inline-flex; align-items: center; gap: 7px; padding: 8px 13px; background: var(--pri-50); border-radius: 9px; color: var(--pri); font-weight: 600; font-size: 13.5px; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--pri); }
.m4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.two { display: grid; grid-template-columns: 1.2fr 1fr; gap: 18px; align-items: start; }
.two2 { display: grid; grid-template-columns: 1fr 1.3fr; gap: 18px; align-items: start; }
.agreement { border: 1px solid var(--line); border-radius: 11px; padding: 18px; font-size: 13.5px; color: var(--t2); line-height: 2; white-space: pre-wrap; overflow-wrap: anywhere; }
.agreement-list{display:grid;gap:10px}.agreement-item{display:flex;justify-content:space-between;align-items:center;gap:12px;width:100%;padding:12px;border:1px solid var(--line);border-radius:10px;background:var(--bg2);text-align:left;color:var(--t1);cursor:pointer}.agreement-item[aria-pressed=true]{border-color:var(--pri)}.agreement-item small{display:block;margin-top:6px;color:var(--t3)}.agreement-item:focus-visible{outline:2px solid var(--pri);outline-offset:2px}.agreement-reason{display:grid;gap:8px;margin-top:14px}.agreement-reason textarea{box-sizing:border-box;width:100%;resize:vertical}.agreement-actions{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0}.agreement-error{color:var(--danger,#b42318);line-height:1.6}.agreement-receipt{padding:12px;border:1px solid var(--line);border-radius:10px}.agreement-receipt p{margin:6px 0;line-height:1.6}
.notebox { margin-top: 14px; padding: 12px 14px; background: #F2F7FF; border-radius: 10px; font-size: 12.5px; color: var(--t2); line-height: 1.6; }
.eval-receipt { display: grid; grid-template-columns: auto auto 1fr auto; align-items: center; gap: 12px; margin-bottom: 14px; padding: 12px 14px; border: 1px solid #86efac; border-radius: 10px; background: #f0fdf4; color: #166534; font-size: 12px; }.eval-receipt button { border: 0; background: transparent; color: inherit; }
.repitem { display: flex; align-items: center; gap: 12px; padding: 12px 14px; border: 1px solid var(--line); border-radius: 11px; }
.score-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; }
.score-grid dt { font-size: 12px; color: var(--t3); margin-bottom: 4px; }
.score-grid dd { margin: 0; font-size: 15px; font-weight: 600; color: var(--t1); }
.makeup-apply__lead{margin:-4px 0 16px;line-height:1.65}.makeup-receipt{display:flex;flex-direction:column;gap:4px;margin:0 0 16px;padding:12px 14px;border:1px solid #bbf7d0;border-radius:10px;background:#f0fdf4;color:#166534;font-size:12px}.makeup-receipt strong{font-size:14px}.makeup-error{margin:0 0 14px;padding:10px 12px;border-radius:9px;background:#fef2f2;color:#b91c1c;font-size:12px;line-height:1.55}.makeup-review-note{padding:8px 10px;border-left:3px solid #f59e0b;border-radius:6px;background:#fffbeb;color:#92400e;font-size:12px;line-height:1.55}
.leave-lead{margin:-2px 0 14px;line-height:1.65}.leave-return-editor{display:flex;flex-direction:column;gap:8px;margin-top:4px;padding:12px;border:1px solid color-mix(in srgb,var(--pri) 28%,var(--line));border-radius:10px;background:var(--pri-50)}.leave-return-editor strong{color:var(--t1);font-size:13px}.leave-return-editor p{margin:0;color:var(--t3);font-size:12px;line-height:1.55}.leave-return-editor__actions{display:flex;justify-content:flex-end;gap:8px}.leave-return-editor__actions .sp-btn{width:auto}
.report-head{display:flex;align-items:flex-start;justify-content:space-between;gap:24px;margin-bottom:12px;padding:16px 18px;border:1px solid color-mix(in srgb,var(--pri) 24%,var(--line));border-radius:12px;background:linear-gradient(120deg,var(--pri-50),#fff)}.report-head strong{display:block;color:var(--t1);font-size:18px}.report-head p{margin:5px 0 0;color:var(--t3);font-size:12.5px;line-height:1.6}.report-head>span{flex:none;padding:6px 10px;border-radius:999px;background:#fff;color:var(--pri);font-size:12px}.report-tabs{display:flex;gap:8px;margin-bottom:14px}.report-receipt{display:grid;grid-template-columns:auto auto 1fr auto;align-items:center;gap:12px;margin-bottom:14px;padding:12px 14px;border:1px solid #86efac;border-radius:10px;background:#f0fdf4;color:#166534;font-size:12px}.report-receipt button{border:0;background:transparent;color:inherit;cursor:pointer}.report-error{margin-bottom:14px;padding:10px 12px;border-radius:9px;background:#fef2f2;color:#b91c1c;font-size:12px;line-height:1.55}.report-editor .sp-fieldlabel{display:flex;justify-content:space-between}.report-editor .sp-fieldlabel span,.report-count,.report-item__meta{color:var(--t4);font-size:11.5px}.report-count{margin:0 0 12px;text-align:right}.report-list{display:flex;flex-direction:column;gap:10px}.report-item{align-items:stretch;flex-direction:column;gap:7px}.report-item strong{color:var(--t1);font-size:13.5px}.report-item__summary{display:-webkit-box;overflow:hidden;margin:0;color:var(--t3);font-size:12px;line-height:1.6;-webkit-box-orient:vertical;-webkit-line-clamp:2;white-space:pre-wrap}.report-feedback{padding:9px 10px;border-left:3px solid #f59e0b;border-radius:6px;background:#fffbeb;color:#92400e;font-size:12px;line-height:1.55}.report-feedback strong{display:block;margin-bottom:2px;color:inherit;font-size:11px}.report-revise{align-self:flex-end;border:0;background:transparent;color:var(--pri);font-weight:600;cursor:pointer}
@media (max-width: 900px) { .score-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 900px) { .sp-process-nav { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); } .sp-process-group[open] { grid-column:span 2; min-width:0; } .m4 { grid-template-columns: repeat(2,1fr); } .two, .two2 { grid-template-columns: 1fr; } }
@media (max-width: 640px) { .sp-now { align-items: stretch; flex-direction: column; gap: 14px; } .sp-process-nav { grid-template-columns:1fr; } .sp-process-group[open] { grid-column: span 1; } .report-head{flex-direction:column;gap:10px}.report-receipt{grid-template-columns:1fr}.report-tabs{overflow-x:auto} }

.sp-preparation{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(270px,1fr);gap:20px;margin-bottom:20px}.sp-preparation__head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.sp-preparation h2{font-size:20px;line-height:1.5;margin:7px 0 0}.sp-preparation__eyebrow{font-size:12px;color:var(--sp-text-muted,#6b7688)}.sp-preparation__facts{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin:26px 0}.sp-preparation__facts dt{font-size:12px;color:#6b7688;margin-bottom:6px}.sp-preparation__facts dd{font-size:14px;margin:0;line-height:1.7;overflow-wrap:anywhere}.sp-qualification__title{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:8px 0 18px}.sp-qualification__title h2{font-size:18px;margin:0}.sp-qualification p{font-size:14px;line-height:1.8;white-space:pre-wrap;overflow-wrap:anywhere;color:#475569}.sp-qualification__next{border-top:1px solid #e9edf3;margin:22px 0 16px;padding-top:18px}.sp-qualification__next strong{font-size:12px;color:#6b7688}.sp-qualification__next p{font-size:13px;margin:6px 0 0}
.sp-completion{display:flex;align-items:center;justify-content:space-between;gap:24px;margin-bottom:20px;border-left:4px solid var(--pri)}.sp-completion h2{margin:6px 0 4px;font-size:18px}.sp-completion p{margin:0;line-height:1.6}.sp-completion__actions{display:flex;flex-shrink:0;gap:10px}@media(max-width:720px){.sp-completion{align-items:flex-start;flex-direction:column}.sp-completion__actions{width:100%;flex-wrap:wrap}}
@media(max-width:1000px){.sp-preparation{grid-template-columns:1fr}.sp-preparation__facts{gap:20px}}
.sp-attendance-overview{display:flex;align-items:center;gap:22px;margin:12px 0 16px}.sp-attendance-ring{width:150px;height:150px;border-radius:50%;display:grid;place-items:center;flex:0 0 auto;position:relative}.sp-attendance-ring::after{content:'';position:absolute;width:94px;height:94px;border-radius:50%;background:var(--card)}.sp-attendance-ring>div{position:relative;z-index:1;text-align:center;display:flex;flex-direction:column}.sp-attendance-ring strong{font-size:25px}.sp-attendance-ring span{font-size:11px;color:var(--t3)}.sp-attendance-legend{display:grid;gap:8px;flex:1}.sp-attendance-legend>div{display:grid;grid-template-columns:10px 1fr auto;align-items:center;gap:8px;font-size:12px}.sp-attendance-legend .dot{width:9px;height:9px;border-radius:50%}.dot.checkin{background:var(--ok-fg)}.dot.absent{background:var(--danger-fg)}.dot.leave{background:var(--warn-fg)}.dot.makeup{background:var(--pri)}.dot.exempt{background:var(--t4)}.sp-attendance-list{display:flex;flex-direction:column;max-height:520px;overflow:auto}.sp-attendance-row{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:10px 0;border-bottom:1px solid var(--line)}.sp-attendance-row>div{display:flex;flex-direction:column;gap:3px}.sp-attendance-row span{font-size:11px;color:var(--t3)}@media(max-width:760px){.sp-attendance-overview{align-items:flex-start;flex-direction:column}}
.sp-home-attendance{margin-bottom:14px}.sp-home-attendance__grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}.sp-home-attendance__grid>div{padding:11px 12px;border:1px solid var(--line);border-radius:9px;background:var(--bg2);display:flex;flex-direction:column;gap:5px}.sp-home-attendance__grid span{font-size:11px;color:var(--t3)}.sp-home-attendance__grid strong{font-size:20px}@media(max-width:900px){.sp-home-attendance__grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
.sp-formal-docs{margin-bottom:14px}.sp-formal-docs__grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.sp-formal-docs__grid>div{padding:14px;border:1px solid var(--line);border-radius:10px;background:var(--bg2)}.sp-formal-docs__grid strong{font-size:14px}.sp-formal-docs__grid p{min-height:42px;margin:6px 0 12px;color:var(--t3);font-size:12px;line-height:1.6}.sp-formal-docs__actions{display:flex;gap:8px;flex-wrap:wrap}@media(max-width:800px){.sp-formal-docs__grid{grid-template-columns:1fr}}
.sp-contextbar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:20px;padding:0 2px 14px;border-bottom:1px solid var(--line);color:var(--t3);font-size:13px}.sp-contextbar strong{margin-left:8px;color:var(--t1)}.sp-contextbar .sp-link{margin-left:auto}
.view-overview{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.view-overview>.sp-now{grid-column:1/-1;order:0;margin:0;padding:20px 22px;background:var(--surface,#fff)}
.view-overview>.sp-preparation{grid-column:1/-1;order:1;margin:0;grid-template-columns:minmax(0,2.2fr) minmax(270px,1fr);gap:16px}.view-overview .sp-preparation__main{padding:18px 22px}.view-overview .sp-preparation__facts{margin:14px 0;gap:12px 24px}.view-overview .sp-qualification{padding:18px}.view-overview .sp-qualification__next{padding-top:10px;margin-top:10px}
.view-overview>.sp-home-attendance,.view-overview>.sp-report-progress{order:2;margin:0}.view-overview>.m4{grid-column:1/-1;order:3}.view-overview>.sp-completion{grid-column:1/-1;order:4;margin:0}.view-overview>.sp-completion.is-current{order:1}.view-overview>.sp-source-state,.view-overview>.sp-state{grid-column:1/-1}
.sp-now__copy h2{font-size:22px}.sp-now__copy p{font-size:14px;line-height:1.6}.sp-now__meta{font-size:13px}.sp-preparation__eyebrow{font-size:12px}.sp-preparation__facts dt{font-size:13px}.sp-preparation__facts dd{font-size:15px}.sp-qualification p{font-size:14px;line-height:1.6}
.sp-home-attendance__grid{gap:6px}.sp-home-attendance__grid>div{padding:10px 8px}.sp-home-attendance__grid span,.sp-report-progress__row span{font-size:12px}.sp-report-progress__grid{grid-template-columns:repeat(2,minmax(0,1fr))}.sp-report-progress__item{padding:8px 10px}.sp-report-progress__row{gap:8px;flex-wrap:wrap}
.sp-preparation__eyebrow,.sp-preparation__facts dt,.sp-qualification__next strong{color:var(--t3)}.sp-qualification p{color:var(--t2)}.sp-qualification__next{border-top-color:var(--line)}.sp-report-progress__track{background:var(--line)}
.sp-insurance-preview{margin-top:20px;border-top:1px solid var(--line);padding-top:16px}.sp-insurance-preview img{display:block;max-width:100%;max-height:640px;object-fit:contain;margin-top:18px}.sp-insurance-preview iframe{width:100%;height:600px;border:1px solid var(--line);margin-top:18px}
.sp-action-row{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:18px}.sp-result-summary h2{margin:12px 0;font-size:22px}.sp-result-facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px 24px;margin:22px 0}.sp-result-facts>div{min-width:0}.sp-result-facts dt{color:var(--t3);font-size:13px}.sp-result-facts dd{margin:5px 0 0;font-size:15px;overflow-wrap:anywhere;white-space:pre-wrap}.sp-result-note{padding:14px 16px;border:1px solid var(--line);border-radius:8px;background:var(--bg2);line-height:1.7}
.sp-intention{max-width:920px}.sp-intention>.sp-inp{margin-bottom:18px}.sp-intention>textarea.sp-inp{min-height:180px}.sp-receipt{padding:14px 16px;border-radius:8px;border:1px solid #acd6b7;background:#eef9f1;color:#166534}.sp-command-error{color:var(--danger-fg);line-height:1.7}.sp-conflict{padding:14px 16px;background:var(--bg2);border:1px solid var(--line);border-radius:8px;margin:16px 0}
.repitem{min-width:0}.repitem>.sp-muted{display:block}.view-leave .repitem>div:first-child{align-items:flex-start!important}.view-leave .repitem .sp-action-row,.view-leave .repitem>div[style*="gap:8px"]{flex-wrap:wrap;align-items:center}.view-leave .repitem [class*=status]{white-space:nowrap;flex-shrink:0}.view-enterprises .sp-inp{min-width:0}.view-enterprises .sp-btn{white-space:nowrap}
.report-head{background:var(--surface,#fff);padding:14px 18px}.report-head strong{font-size:18px}.report-head p,.report-head>span{font-size:13px}.report-tabs{margin:14px 0}.report-tabs .sp-tab{min-height:40px;font-size:14px}.report-item__meta{font-size:12px}.report-item__summary{font-size:13px;line-height:1.7}
@media(max-width:1100px){.view-overview>.sp-preparation{grid-template-columns:minmax(0,1.6fr) minmax(250px,1fr)}.view-overview{grid-template-columns:1fr}.view-overview>.sp-home-attendance,.view-overview>.sp-report-progress{grid-column:1/-1}}
@media(max-width:850px){.view-overview>.sp-preparation{grid-template-columns:1fr}.sp-result-facts{grid-template-columns:1fr}.sp-contextbar .sp-link{margin-left:0}}
.report-workspace{grid-template-columns:minmax(0,1fr) 320px;align-items:start}.report-editor,.report-index{min-width:0}.report-editor .sp-inp{font-size:15px;line-height:1.8}.report-editor textarea{min-height:180px}.report-original{font-size:15px;line-height:1.8;color:var(--t2);padding:0 0 20px}.report-original>strong{font-size:18px;color:var(--t1)}.report-original h4{font-size:15px;margin:20px 0 6px}.report-original details{margin-top:16px;border-top:1px solid var(--line);padding-top:12px}.report-original summary{min-height:40px;cursor:pointer;font-weight:600}.report-index .report-item{padding:14px 0}.report-index .report-revise{min-height:40px;text-align:left}.report-index .report-item__meta{font-size:13px}.report-index .report-item__summary,.report-feedback{font-size:14px}.report-head{background:var(--pri-50)}.report-head>span{background:var(--surface)}.report-feedback{background:var(--warn-bg);color:var(--warn-fg)}.report-editor .sp-fieldlabel span,.report-count{font-size:13px}.report-editor .sp-panel__head{display:flex;align-items:center;justify-content:space-between;gap:16px}.report-tabs{flex-wrap:wrap}
@media(max-width:1100px){.report-workspace{grid-template-columns:minmax(0,1fr)}.report-head{flex-wrap:wrap}.report-receipt{grid-template-columns:minmax(0,1fr)}}
</style>
