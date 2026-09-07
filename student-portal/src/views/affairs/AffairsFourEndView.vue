<template>
  <div class="sp-page">
    <nav class="sp-tabs">
      <button v-for="item in tabs" :key="item.key" class="sp-tab" :class="{ 'is-active': tab === item.key }" @click="router.push({ path: route.path, query: { ...route.query, tab: item.key } })">{{ item.label }}</button>
    </nav>

    <WorkStudyStudentView v-if="tab === 'work-study'" />
    <LoanStudentView v-else-if="tab === 'loan'" />
    <ReductionStudentView v-else-if="tab === 'reduction'" />
    <StateBlock v-else-if="loading && !(tab === 'leave' && loadedTabs.leave) && !(tab === 'funding' && loadedTabs.funding)" type="loading" :text="`${activeTabLabel}加载中…`" />
    <template v-else>
      <div v-if="tabError" class="domain-error"><strong>当前业务暂不可用</strong><span>{{ tabError }}</span><button class="sp-btn sp-btn--ghost" @click="reload">重新加载</button></div>

      <LeaveWorkspace v-if="tab === 'leave'" :items="leave.items || []" :busy="busy" @reload="reload" @edit="editLeave" @cancel="cancelLeave" @extend="openExtend">
        <template #apply>
        <section class="sp-card">
          <div class="sp-panel__head">请假申请</div>
          <div class="form-grid">
            <label><span>请假类型</span><select v-model="leaveForm.leaveType" class="sp-inp"><option value="PERSONAL">事假</option><option value="SICK">病假</option><option value="HOME">探亲假</option><option value="HOSPITAL">住院假</option><option value="GOOUT">外出</option><option value="OTHER">其他</option></select></label>
            <label><span>开始日期</span><AppDatePicker v-model="leaveForm.startTime" class="sp-inp" :min="today" label="开始日期" /></label>
            <label><span>结束日期</span><AppDatePicker v-model="leaveForm.endTime" class="sp-inp" :min="leaveForm.startTime || today" label="结束日期" /></label>
            <label class="wide"><span>请假事由（5-300字）</span><textarea v-model.trim="leaveForm.reason" maxlength="300" class="sp-inp" placeholder="请客观填写请假事由" /></label>
          </div>
          <p v-if="leaveForm.startTime && leaveForm.endTime && leaveForm.endTime < leaveForm.startTime" class="field-error">结束日期不能早于开始日期</p>
          <button class="sp-btn" :disabled="busy || !validLeave" @click="applyLeave">提交请假</button>
        </section>
        </template>
        <template #followup="{ item }">
            <div v-if="extendId === item.leaveId" class="inline-form">
              <label><span>原结束日期</span><strong>{{ fmt(item.endTime) }}</strong></label>
              <label><span>新结束日期</span><AppDatePicker v-model="extendForm.newEndTime" class="sp-inp" :min="dayAfter(fmt(item.endTime))" label="新结束日期" /></label>
              <label><span>续假事由（5-300字）</span><textarea v-model.trim="extendForm.reason" maxlength="300" class="sp-inp" /></label>
              <div class="actions"><button class="sp-btn sp-btn--ghost" :disabled="busy" @click="extendId = ''">取消</button><button class="sp-btn" :disabled="busy || !validExtend(item)" @click="submitExtend(item)">提交续假</button></div>
            </div>
        </template>
      </LeaveWorkspace>

      <section v-else-if="tab === 'aid'" class="sp-card">
        <div class="sp-panel__head">家庭经济困难认定 <StatusTag :text="enumText(aid.currentLevel || '未认定')" :tone="aid.currentLevel ? 'success' : 'default'" /><button class="sp-btn sp-btn--ghost" :disabled="busy || loading" @click="reload">刷新进度</button></div>
        <p class="sp-muted">选择学校开放的批次，如实填写家庭情况。提交后可在这里或小程序查看评议、审核与公示进度。</p>
        <details class="aid-application" :open="!(aid.items || []).length">
        <summary>发起新的认定申请</summary>
        <div class="form-grid compact">
          <div class="wide aid-batch-search">
            <label><span>查找开放批次</span><input v-model.trim="aidBatchQuery" maxlength="100" class="sp-inp" placeholder="按批次名称或学年搜索" @keydown.enter.prevent="loadAidBatches()" /></label>
            <button type="button" class="sp-btn sp-btn--ghost" :disabled="aidBatchLoading" @click="loadAidBatches()">搜索</button>
          </div>
          <label class="wide"><span>开放批次</span><select v-model="aidForm.batchId" class="sp-inp" @change="selectAidBatch"><option value="">请选择</option><option v-for="b in aidBatchOptions" :key="b.batchId" :value="b.batchId">{{ b.batchName || b.schoolYear }}（截止 {{ fmt(b.applyEnd) || '不限' }}）</option></select></label>
          <div class="wide aid-batch-results" role="status"><span>{{ aidBatchLoading ? '正在查找开放批次…' : `已加载 ${aidBatches.length} / ${aidBatchTotal} 个匹配批次` }}</span><button v-if="aidBatches.length < aidBatchTotal" type="button" class="sp-btn sp-btn--ghost" :disabled="aidBatchLoading" @click="loadAidBatches(true)">加载更多批次</button><span v-if="aidBatchError" class="field-error">{{ aidBatchError }}</span><button v-if="aidBatchError" type="button" class="sp-btn sp-btn--ghost" @click="loadAidBatches()">重试</button></div>
          <label><span>申请等级</span><select v-model="aidForm.applyLevel" class="sp-inp"><option value="GENERAL">一般困难</option><option value="DIFFICULT">困难</option><option value="SPECIAL">特别困难</option></select></label>
          <label><span>家庭成员数（1-30）</span><input v-model.number="aidForm.memberCount" type="number" min="1" max="30" step="1" class="sp-inp" /></label>
          <label><span>家庭年收入（元）</span><input v-model.number="aidForm.annualIncome" type="number" min="0" step="0.01" class="sp-inp" /></label>
          <label><span>家庭债务（元）</span><input v-model.number="aidForm.debt" type="number" min="0" step="0.01" class="sp-inp" /></label>
          <label class="wide"><span>特殊情况标签</span><input v-model.trim="aidForm.specialTags" maxlength="200" class="sp-inp" placeholder="低保、孤残、重大疾病等，用逗号分隔" /></label>
          <label class="wide"><span>困难情况说明（10-500字）</span><textarea v-model.trim="aidForm.statement" maxlength="500" class="sp-inp" /></label>
        </div>
        <p v-if="aidValidationError" class="field-error">{{ aidValidationError }}</p>
        <label class="check"><input v-model="aidForm.confirm" type="checkbox" />本人确认填写的信息真实、完整，并提交学校审核。</label>
        <button class="sp-btn" :disabled="busy || !validAid" @click="submitAid">提交认定申请</button>
        </details>
        <div class="section-title">认定记录</div>
        <StateBlock v-if="!(aid.items || []).length" type="empty" text="暂无认定记录" />
        <article v-for="item in (aid.items || [])" :key="item.applyId" class="record">
          <p v-if="item.progressHint" class="sp-muted" role="status">{{ item.progressHint }}</p>
          <div class="record-head"><div><strong>申请等级：{{ enumText(item.applyLevel) }}</strong><div class="sp-muted">{{ enumText(item.statusLabel || item.status) }}</div><div v-if="item.returnReason" class="warn">意见：{{ item.returnReason }}</div></div><StatusTag :text="item.statusLabel || item.status" tone="default" /></div>
          <div class="actions"><button class="sp-btn sp-btn--ghost" :disabled="busy" @click="aidDetailId = String(item.applyId)">查看申请详情</button><button v-if="allows(item, 'EDIT_RETURNED') || allows(item, 'RESUBMIT')" class="sp-btn sp-btn--ghost" :disabled="busy" @click="editAid(item)">修改后重提</button></div>
          <div v-if="allows(item, 'SUBMIT_OBJECTION')" class="inline-form"><textarea v-model.trim="aidObjections[item.applyId]" maxlength="500" class="sp-inp" placeholder="公示异议理由（5-500字）" /><button class="sp-btn" :disabled="busy || !validReason(aidObjections[item.applyId], 5, 500)" @click="submitAidObjection(item)">提交异议</button></div>
          <div v-if="item.hasPendingObjection" class="sp-muted">异议已进入具体老师待办，等待复核。</div>
        </article>
      </section>

      <section v-else-if="tab === 'funding'" class="sp-card">
        <div class="sp-panel__head">奖学金与助学金</div>
        <p class="sp-muted">本入口办理奖学金和助学金；勤工、贷款、减免与临补请使用上方对应入口。</p>
        <div class="form-grid compact">
          <label><span>类型</span><select v-model="fundForm.projectType" :disabled="busy" class="sp-inp" @change="changeFundingType"><option value="SCHOLARSHIP">奖学金</option><option value="GRANT">助学金</option></select></label>
          <div class="wide aid-batch-search"><label><span>查找开放批次</span><input v-model.trim="fundingBatchQuery" maxlength="100" class="sp-inp" placeholder="按项目名称或学年搜索" @keydown.enter.prevent="loadFundingBatches()" /></label><button type="button" class="sp-btn sp-btn--ghost" :disabled="fundingBatchLoading" @click="loadFundingBatches()">搜索</button></div>
          <label class="wide"><span>开放批次</span><select v-model="fundForm.batchId" :disabled="busy" class="sp-inp" @change="selectFundingBatch"><option value="">请选择申请批次</option><option v-for="b in fundingBatchOptions" :key="b.batchId" :value="b.batchId">{{ b.batchName || b.schoolYear }}（截止 {{ fmt(b.applyEnd) || '不限' }}）</option></select></label>
          <div class="wide aid-batch-results" role="status"><span>{{ fundingBatchLoading ? '正在查找开放批次…' : `已加载 ${fundingBatches.length} / ${fundingBatchTotal} 个匹配批次` }}</span><button v-if="fundingBatches.length < fundingBatchTotal" type="button" class="sp-btn sp-btn--ghost" :disabled="fundingBatchLoading" @click="loadFundingBatches(true)">加载更多批次</button><span v-if="fundingBatchError" class="field-error">{{ fundingBatchError }}</span><button v-if="fundingBatchError" type="button" class="sp-btn sp-btn--ghost" :disabled="fundingBatchLoading" @click="loadFundingBatches()">重试</button><span v-else-if="!fundingBatchLoading && !fundingBatchTotal">没有匹配的开放批次，可修改搜索条件或等待学校发布。</span></div>
          <label class="wide"><span>申请理由（5-1000字）</span><textarea v-model.trim="fundForm.statement" :disabled="busy" maxlength="1000" class="sp-inp" /></label>
          <FundingAttachments class="wide" :key="fundingAttachmentEpoch" :initial-files="fundingAttachments.items" :disabled="busy" @change="Object.assign(fundingAttachments, $event)" />
        </div>
        <label class="check"><input v-model="fundForm.confirm" :disabled="busy" type="checkbox" />本人确认所选批次与申请信息真实。</label>
        <button class="sp-btn" :disabled="busy || !validFunding" @click="submitFunding">提交申请</button>
        <div class="section-title">我的奖助记录</div>
        <StateBlock v-if="!(funding.items || []).length" type="empty" text="暂无奖助记录" />
        <article v-for="item in (funding.items || [])" :key="item.applicationId" class="record"><div class="record-head"><div><strong>{{ item.projectName || fundingLabel(item.projectType) }}</strong><div class="sp-muted">{{ item.schoolYear || '学年待核对' }} · {{ fundingLabel(item.projectType) }}<template v-if="item.batchId"> · 批次 {{ item.batchId }}</template> · 申请 {{ item.applicationId }}</div><div v-if="item.returnReason" class="warn">意见：{{ item.returnReason }}</div></div><StatusTag :text="item.hasPendingAppeal ? '申诉待复核' : (item.statusLabel || item.status)" :tone="item.hasPendingAppeal ? 'warn' : 'default'" /></div><div class="actions"><button class="sp-btn sp-btn--ghost" :disabled="busy" @click="fundingDetailId = String(item.applicationId)">查看申请详情</button><button class="sp-btn sp-btn--ghost" :disabled="busy" @click="fundingMaterialId = fundingMaterialId === item.applicationId ? '' : item.applicationId">{{ fundingMaterialId === item.applicationId ? '收起材料' : '查看申请材料' }}</button><button v-if="allows(item, 'EDIT_RETURNED') || allows(item, 'RESUBMIT')" class="sp-btn sp-btn--ghost" :disabled="busy" @click="editFunding(item)">修改后重提</button></div><FundingEvidence v-if="fundingMaterialId === item.applicationId" :application-id="String(item.applicationId)" /><div v-if="allows(item, 'SUBMIT_APPEAL')" class="inline-form"><textarea v-model.trim="fundAppeals[item.applicationId]" maxlength="1000" class="sp-inp" placeholder="公示申诉理由（5-1000字）" /><button class="sp-btn" :disabled="busy || !validReason(fundAppeals[item.applicationId], 5, 1000)" @click="submitFundingAppeal(item)">提交申诉</button></div></article>
      </section>

      <section v-else-if="tab === 'dorm'" class="sp-card">
        <div class="sp-panel__head">我的宿舍</div>
        <div class="presence-card">
          <div><span>归寝状态</span><strong>{{ dorm.presence?.statusLabel || '未知' }}</strong></div>
          <div><span>最近可靠事件</span><strong>{{ fmtTime(dorm.presence?.lastEventAt) }}</strong></div>
          <div><span>Provider</span><strong>{{ dorm.presenceProvider?.providerLabel || '未配置' }} · {{ dorm.presenceProvider?.healthStatus || 'DISABLED' }}</strong></div>
          <p>{{ dorm.presence?.summary || '暂无可靠归寝数据' }}<template v-if="dorm.presence?.status === 'UNKNOWN'">。“未知”不等同于“未归”。</template></p>
        </div>
        <div v-if="!dorm.hasBed && dorm.hasAllocation" class="allocation-card">
          <strong>{{ dorm.allocation?.hiddenUntilCheckin ? '宿舍已安排' : '床位已确认' }}</strong>
          <p v-if="!dorm.allocation?.hiddenUntilCheckin">{{ [dorm.allocation?.building, dorm.allocation?.room && `${dorm.allocation.room}室`, dorm.allocation?.bedNo && `${dorm.allocation.bedNo}床`].filter(Boolean).join(' / ') }}</p>
          <p class="sp-muted">{{ dorm.studentNotice }}</p>
        </div>
        <StateBlock v-else-if="!dorm.hasBed" type="empty" :text="dormStays.some(x => x.status === 'ENDED') && !dorm.canSelfSelect ? '住宿已结束，当前无在住床位。记录可在下方住宿历史查看；如需重新住宿，请联系宿管。' : (dorm.studentNotice || '暂无住宿安排')" />
        <template v-if="dorm.hasBed">
          <div class="bed-grid"><div><span>楼栋</span><strong>{{ dorm.myBed?.building }}</strong></div><div><span>房间</span><strong>{{ dorm.myBed?.room }}</strong></div><div><span>床位</span><strong>{{ dorm.myBed?.bedNo }}</strong></div><div><span>入住时间</span><strong>{{ fmt(dorm.myBed?.occupiedAt) }}</strong></div></div>
          <p class="sp-muted">已有床位时只能提交正式调宿申请；审批完成前原床保持不变。</p>
          <p v-if="pendingDormTransfer" class="warn">已有调宿申请处理中：{{ enumText(pendingDormTransfer.statusLabel || pendingDormTransfer.status || pendingDormTransfer.currentNode) }}</p>
          <button v-else class="sp-btn sp-btn--ghost" :disabled="busy || !!dormTransferError" @click="loadDormOptions">申请调宿</button>
        </template>
        <button v-else-if="dorm.canSelfSelect" class="sp-btn" :disabled="busy" @click="loadDormOptions">首次选床</button>
        <div v-if="dormForm.visible" class="inline-form dorm-form">
          <select v-model="dormForm.buildingId" class="sp-inp" @change="loadRooms"><option value="">选择目标楼栋</option><option v-for="b in dormBuildings" :key="b.buildingId" :value="b.buildingId">{{ b.buildingName }}（空{{ b.vacantBeds }}）</option></select>
          <select v-model="dormForm.roomId" class="sp-inp" :disabled="!dormForm.buildingId" @change="loadBeds"><option value="">选择房间</option><option v-for="r in dormRooms" :key="r.roomId" :value="r.roomId">{{ r.floorNo }}层 {{ r.roomNo }}（空{{ r.vacantBeds }}）</option></select>
          <select v-model="dormForm.bedId" class="sp-inp" :disabled="!dormForm.roomId"><option value="">选择床位</option><option v-for="b in availableDormBeds" :key="b.bedId" :value="b.bedId">{{ b.bedNo }}</option></select>
          <p v-if="dormForm.bedId" class="selected-target">目标床位：{{ selectedDormTarget }}</p>
          <textarea v-if="dorm.hasBed" v-model.trim="dormForm.reason" maxlength="300" class="sp-inp" placeholder="调宿原因（5-300字）" />
          <p v-else class="warn">确认后床位将为你预留，不能自行更换；如需调整必须走正式调宿。</p>
          <div class="actions"><button class="sp-btn sp-btn--ghost" :disabled="busy" @click="closeDormForm">取消</button><button class="sp-btn" :disabled="busy || !validDormAction" @click="submitDormAction">{{ dorm.hasBed ? '核对并提交调宿' : '核对并确认床位' }}</button></div>
        </div>
        <div class="section-title">调宿申请记录</div><p v-if="dormTransferError" class="sp-notice">{{ dormTransferError }}</p><AutoTable v-else :rows="dormTransfers" :columns="DORM_TRANSFER_COLS" empty="暂无调宿申请" />
        <div class="section-title">住宿历史</div><AutoTable :rows="dormStays" :columns="DORM_STAY_COLS" empty="暂无住宿历史" />
        <div class="section-title">我的检查整改</div>
        <StateBlock v-if="!dormRectifications.length" type="empty" text="暂无宿舍整改任务" />
        <article v-for="item in dormRectifications" :key="item.rectificationId" class="record rect-card">
          <div class="record-head"><div><strong>{{ item.buildingName }} · {{ item.roomNo }}室</strong><div class="sp-muted">{{ item.taskName }} · {{ severityText(item.severity) }} · 截止 {{ fmtTime(item.deadlineAt) }}</div><p class="rect-requirement">{{ item.requirement }}</p></div><StatusTag :text="rectStatusText(item.status)" :tone="item.overdue ? 'warn' : (item.status === 'CLOSED' ? 'success' : 'default')" /></div>
          <div v-if="item.allowedActions?.includes('START')" class="actions"><button class="sp-btn sp-btn--ghost" :disabled="busy" @click="startDormRectification(item)">开始整改</button></div>
          <div v-if="item.allowedActions?.includes('SUBMIT')" class="inline-form"><textarea v-model.trim="rectNotes[item.rectificationId]" maxlength="1000" class="sp-inp" placeholder="整改说明（5-1000字）" /><label class="file-pick"><span>整改照片证据（必填）</span><input type="file" accept="image/*" :disabled="busy" @change="pickRectFile(item, $event)" /></label><p v-if="rectFiles[item.rectificationId]" class="selected-target">已上传：{{ rectFiles[item.rectificationId].fileName }}</p><button class="sp-btn" :disabled="busy || !validReason(rectNotes[item.rectificationId], 5, 1000) || !rectFiles[item.rectificationId]" @click="submitDormRectification(item)">提交复检</button></div>
          <p v-if="item.status === 'WAITING_RECHECK'" class="sp-muted">整改证据已提交，等待宿管现场复检。</p>
          <p v-if="item.recheckNote" class="sp-muted">复检意见：{{ item.recheckNote }}</p>
        </article>
      </section>

      <section v-else-if="tab === 'discipline'" class="sp-card">
        <div class="sp-panel__head">处分申诉</div><p class="sp-muted">本入口用于处分生效后的申诉，不冒充处分决定前的陈述申辩。具体期限以学校处分决定书与规章为准。</p>
        <StateBlock v-if="!(discipline.items || []).length" type="empty" text="暂无处分记录" />
        <article v-for="item in (discipline.items || [])" :key="item.caseId" class="record"><div class="record-head"><div><strong>{{ enumText(item.discTypeLabel || item.discType) }}</strong><div class="sp-muted">{{ fmt(item.effectiveAt) }} 生效</div><div v-if="item.removedAt" class="sp-muted">{{ fmt(item.removedAt) }} 解除</div><div v-if="item.appealReviewOpinion" class="sp-muted">复核意见：{{ item.appealReviewOpinion }}</div></div><StatusTag :text="disciplineStatusLabel(item)" :tone="item.caseStatus === 'REMOVED' ? 'success' : 'default'" /></div><div v-if="allows(item, 'SUBMIT_APPEAL')" class="inline-form"><textarea v-model.trim="disciplineAppeals[item.caseId]" maxlength="1000" class="sp-inp" placeholder="处分申诉理由（5-1000字）" /><button class="sp-btn" :disabled="busy || !validReason(disciplineAppeals[item.caseId], 5, 1000)" @click="submitDisciplineAppeal(item)">提交处分申诉</button></div></article>
      </section>

      <section v-else-if="tab === 'psy'" class="sp-card psy-workspace">
        <div class="sp-panel__head">心理健康自评</div>
        <p class="sp-muted">用于了解近期情绪、睡眠和压力。自评不是医学诊断；只有主动求助或达到关注条件时，才登记人工关注。</p>
        <div v-if="psyResult" class="psy-receipt" role="status">
          <strong>本次自评已提交</strong>
          <span>{{ psyResult.triggeredAttention ? '已登记人工关注，请留意老师联系。' : '记录已保存，如有需要可随时联系辅导员或心理中心。' }}</span>
        </div>
        <StateBlock v-if="!(psy.questions || []).length" type="empty" text="暂无自评问卷" />
        <div v-else class="psy-form">
          <div v-for="(q, index) in (psy.questions || [])" :key="q.key" class="question">
            <strong>{{ index + 1 }}. {{ q.text }}</strong>
            <div class="options"><button v-for="(option, oi) in q.options" :key="oi" type="button" class="seg" :class="{ on: psyAnswers[q.key] === oi }" :aria-pressed="psyAnswers[q.key] === oi" @click="psyAnswers[q.key] = oi">{{ option }}</button></div>
          </div>
          <label class="psy-contact"><input v-model="psyWantsContact" type="checkbox" :disabled="busy" />希望近期有老师主动联系我聊聊</label>
          <button class="sp-btn" :disabled="busy || !psyComplete" @click="submitPsy">{{ busy ? '提交中…' : '提交自评' }}</button>
        </div>
        <div class="section-title">我的历史</div>
        <StateBlock v-if="!(psyHistory.items || []).length" type="empty" text="暂无自评记录" />
        <div v-else class="psy-history">
          <article v-for="item in (psyHistory.items || [])" :key="item.submissionId" class="record">
            <div class="record-head"><div><strong>{{ fmtTime(item.submittedAt) }}</strong><div class="sp-muted">本人自评记录 · {{ item.wantsContact ? '已申请老师联系' : '未申请主动联系' }}</div></div><StatusTag :text="item.triggeredAttention ? '已登记人工关注' : '已保存'" :tone="item.triggeredAttention ? 'warn' : 'success'" /></div>
          </article>
        </div>
      </section>

      <section v-else-if="tab === 'activity'">
        <div class="score-card sp-card"><div><strong>正式第二课堂成绩单</strong><p class="sp-muted">仅统计老师确认后已入账流水，不使用活动配置值自行估算。</p></div><div class="score"><span>原始 {{ secondClass.rawTotal || 0 }}</span><span>加权 {{ secondClass.weightedTotal || 0 }}</span></div></div>
        <div class="two"><section class="sp-card"><div class="sp-panel__head">可报名活动</div><StateBlock v-if="!(activities.available || []).length" type="empty" text="暂无可报名活动" /><article v-for="item in (activities.available || [])" :key="item.activityId" class="record"><div class="record-head"><div><strong>{{ item.activityName }}</strong><div class="sp-muted">{{ fmt(item.startAt) }} · {{ item.location || '未填写地点' }}</div></div><button v-if="!item.mySignupStatus || item.mySignupStatus === 'CANCELLED'" class="sp-btn" :disabled="busy" @click="enroll(item)">报名</button><StatusTag v-else :text="item.mySignupStatus" tone="default" /></div></article></section><section class="sp-card"><div class="sp-panel__head">入账明细</div><StateBlock v-if="!(secondClass.items || []).length" type="empty" text="暂无已确认入账记录" /><article v-for="item in (secondClass.items || [])" :key="`${item.activityId}-${item.grantedAt}`" class="record"><div class="record-head"><div><strong>{{ item.remark || '第二课堂记录' }}</strong><div class="sp-muted">{{ creditLabel(item.creditType) }} · {{ fmt(item.grantedAt) }}</div></div><div><strong>+{{ item.creditValue }}</strong><button class="link" @click="openCreditAppeal(item)">记错申诉</button></div></div></article><button class="sp-btn sp-btn--ghost" @click="openCreditAppeal(null)">有活动缺记？提交缺记申诉</button></section></div>
        <section class="sp-card" style="margin-top:16px"><div class="sp-panel__head">我的积分申诉</div><AutoTable :rows="creditAppeals" :columns="CREDIT_APPEAL_COLS" empty="暂无积分申诉" /></section>
      </section>

      <section v-else-if="tab === 'talk'" class="sp-card"><div class="sp-panel__head">我的谈心谈话摘要</div><p class="sp-muted">学生端只展示时间、主题、状态和是否需回访，不显示老师内部记录或心理明细。</p><StateBlock v-if="!talkItems.length" type="empty" text="暂无谈话记录" /><article v-for="item in talkItems" :key="item.talkId" class="record" :class="{ 'is-focused-record': String(item.talkId) === focusedTalkId }"><div class="record-head"><div><strong>{{ enumText(item.talkTypeLabel || item.talkType) }}</strong><div class="sp-muted">{{ item.topic }} · {{ fmt(item.talkAt) || '时间待定' }}</div><div v-if="item.needFollow" class="warn">需要后续回访</div></div><StatusTag :text="item.statusLabel || item.status" tone="default" /></div></article></section>
    </template>

    <AidApplicationDetail v-if="aidDetailId && tab === 'aid'" :key="aidDetailId" :apply-id="aidDetailId" @close="closeAidDetail" @edit="editAidDetail" />
    <FundingApplicationDetail v-if="fundingDetailId && tab === 'funding'" :key="fundingDetailId" :application-id="fundingDetailId" @close="fundingDetailId = ''" @edit="editFundingDetail" />
    <div v-if="modal.type" class="mask" @click.self="closeModal">
      <section class="sp-card modal">
        <div class="sp-panel__head">{{ modal.title }}</div><p v-if="modal.notice" class="warn">{{ modal.notice }}</p>
        <template v-if="modal.type === 'leave'"><div class="form-grid"><label><span>类型</span><select v-model="modal.form.leaveType" class="sp-inp"><option value="PERSONAL">事假</option><option value="SICK">病假</option><option value="HOME">探亲假</option><option value="HOSPITAL">住院假</option><option value="GOOUT">外出</option><option value="OTHER">其他</option></select></label><label><span>开始日期</span><AppDatePicker v-model="modal.form.startTime" class="sp-inp" label="开始日期" /></label><label><span>结束日期</span><AppDatePicker v-model="modal.form.endTime" class="sp-inp" role="end" :start-value="modal.form.startTime" label="结束日期" /></label><label class="wide"><span>事由（5-300字）</span><textarea v-model.trim="modal.form.reason" maxlength="300" class="sp-inp" /></label></div></template>
        <template v-else-if="modal.type === 'aid'"><div class="form-grid"><label><span>等级</span><select v-model="modal.form.applyLevel" class="sp-inp"><option value="GENERAL">一般困难</option><option value="DIFFICULT">困难</option><option value="SPECIAL">特别困难</option></select></label><label><span>成员数（1-30）</span><input v-model.number="modal.form.memberCount" type="number" min="1" max="30" step="1" class="sp-inp" /></label><label><span>年收入</span><input v-model.number="modal.form.annualIncome" type="number" min="0" step="0.01" class="sp-inp" /></label><label><span>债务</span><input v-model.number="modal.form.debt" type="number" min="0" step="0.01" class="sp-inp" /></label><label class="wide"><span>特殊情况标签</span><input v-model.trim="modal.form.specialTags" maxlength="200" class="sp-inp" /></label><label class="wide"><span>情况说明（10-500字）</span><textarea v-model.trim="modal.form.statement" maxlength="500" class="sp-inp" /></label></div></template>
        <template v-else-if="modal.type === 'funding'"><label><span>申请理由（5-1000字）</span><textarea v-model.trim="modal.form.statement" maxlength="1000" class="sp-inp" /></label></template>
        <template v-else-if="modal.type === 'credit'"><p class="sp-muted">{{ modal.form.activityName ? `涉及活动：${modal.form.activityName}` : '缺记申诉可不指定活动' }}</p><select v-model="modal.form.claimCreditType" class="sp-inp"><option value="SECOND_CLASS">第二课堂</option><option value="MORAL">德育积分</option><option value="VOLUNTEER_HOUR">志愿时长</option></select><input v-model="modal.form.claimValue" type="number" min="0.01" max="9999.99" step="0.01" class="sp-inp" placeholder="主张数值（必填，0.01-9999.99）" /><p v-if="creditClaimError" class="field-error">{{ creditClaimError }}</p><textarea v-model.trim="modal.form.reason" maxlength="1000" class="sp-inp" placeholder="申诉理由（5-1000字）" /></template>
        <template v-else-if="modal.type === 'dormConfirm'"><div class="confirm-summary"><strong>目标床位</strong><span>{{ modal.form.target }}</span><p>{{ dorm.hasBed ? '提交后进入正式调宿审批，完成前原床保持不变。' : '确认后床位将为你预留，后续变更须走正式调宿。' }}</p></div></template>
        <template v-else-if="modal.type === 'leaveCancel'"><div class="confirm-summary"><strong>销假确认</strong><span>{{ modal.form.period }}</span><p>请确认你已返校或请假事项已结束。提交后将进入销假流程。</p></div></template>
        <p v-if="modalValidationError" class="field-error">{{ modalValidationError }}</p>
        <div class="actions"><button class="sp-btn sp-btn--ghost" :disabled="busy" @click="closeModal">取消</button><button class="sp-btn" :disabled="busy || !modalValid" @click="submitModal">{{ modal.type === 'dormConfirm' ? (dorm.hasBed ? '确认提交调宿' : '确认选择床位') : (modal.type === 'leaveCancel' ? '确认提交销假' : '保存并提交') }}</button></div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, reactive, ref, watch } from 'vue'
import FundingAttachments from './FundingAttachments.vue'
import FundingEvidence from './FundingEvidence.vue'
import AidApplicationDetail from './AidApplicationDetail.vue'
import FundingApplicationDetail from './FundingApplicationDetail.vue'
import WorkStudyStudentView from './WorkStudyStudentView.vue'
import LoanStudentView from './LoanStudentView.vue'
import ReductionStudentView from './ReductionStudentView.vue'
import { useRoute, useRouter } from 'vue-router'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import AutoTable from '../../components/AutoTable.vue'
import AppDatePicker from '../../components/AppDatePicker.vue'
import LeaveWorkspace from './LeaveWorkspace.vue'
import { leaveDate, leaveError } from '../../services/leavePresentation'
import { portalApi } from '../../services/portalApi'
import { affairsFourEndApi } from '../../services/affairsFourEndApi'
import { localizeVisibleEnumText } from '../../services/visibleEnumLocalization'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const allows = (item, action) => Array.isArray(item?.allowedActions) && item.allowedActions.includes(action)
const DORM_TRANSFER_COLS = [
  { key: 'fromBedLabel', label: '原床位' }, { key: 'toBedLabel', label: '目标床位' },
  { key: 'createdAt', label: '申请时间', formatter: (value) => fmt(value) || '—' },
  { key: 'status', label: '状态', formatter: (value) => value === 'EXECUTED' ? '已完成调宿' : enumText(value) },
  { key: 'returnReason', label: '退回或驳回原因' }
]
const DORM_STAY_STATUS = {
  RESERVED: '待入住',
  ACTIVE: '当前在住',
  ENDED: '已退宿',
  CANCELLED: '已取消'
}
const DORM_STAY_COLS = [
  { key: 'bedLabel', label: '楼 / 房 / 床' }, { key: 'checkinAt', label: '入住时间' },
  { key: 'checkoutAt', label: '退宿时间' },
  { key: 'status', label: '状态', formatter: (value) => DORM_STAY_STATUS[String(value || '').toUpperCase()] || '状态待确认' }
]
const CREDIT_APPEAL_COLS = [
  { key: 'creditType', label: '积分类型' }, { key: 'claimValue', label: '申诉数值' },
  { key: 'reason', label: '申诉理由' }, { key: 'status', label: '状态' },
  { key: 'reviewNote', label: '审核意见' }
]
const tabs = [{ key: 'leave', label: '请假销假' }, { key: 'aid', label: '困难认定' }, { key: 'funding', label: '奖学金与助学金' }, { key: 'work-study', label: '勤工助学' }, { key: 'loan', label: '助学贷款' }, { key: 'reduction', label: '减免与临补' }, { key: 'dorm', label: '我的宿舍' }, { key: 'discipline', label: '处分申诉' }, { key: 'psy', label: '心理自评' }, { key: 'activity', label: '活动与第二课堂' }, { key: 'talk', label: '谈心谈话' }]
const route = useRoute()
const router = useRouter()
const aidDetailId = ref('')
const fundingDetailId = ref('')
watch(() => [route.query.tab, route.query.recordId], ([kind, id]) => {
  aidDetailId.value = kind === 'aid' && /^\d+$/.test(String(id || '')) ? String(id) : ''
  fundingDetailId.value = kind === 'funding' && /^\d+$/.test(String(id || '')) ? String(id) : ''
}, { immediate: true })
function editAidDetail(item) { aidDetailId.value = ''; editAid(item) }
function editFundingDetail(item) { fundingDetailId.value = ''; editFunding(item) }
function closeAidDetail() { aidDetailId.value = ''; reload() }
// V3 SP-M02：消息/首页深链带 ?tab= 指定要打开哪个分 tab（例如请假退回通知）。
// 只接受已登记的合法 tab key，非法/未知值一律回落默认 tab，不信任外部字符串。
const initialTab = tabs.some((item) => item.key === route.query.tab) ? String(route.query.tab) : 'leave'
const tab = ref(initialTab)
watch(() => route.query.tab, (key) => {
  tab.value = tabs.some(item => item.key === key) ? String(key) : 'leave'
})
const busy = ref(false)
const focusedTalkId = computed(() => tab.value === 'talk' && /^[1-9]\d*$/.test(String(route.query.recordId || '')) ? String(route.query.recordId) : '')
const errors = reactive({})
const loadedTabs = reactive({})
const loadingTabs = reactive({})
const inflight = new Map()
const loadEpoch = Object.create(null)
let viewActive = true

const tabError = computed(() => errors[tab.value] || '')
const loading = computed(() => !!loadingTabs[tab.value])
const activeTabLabel = computed(() => tabs.find((item) => item.key === tab.value)?.label || '学工数据')

const leave = ref({ items: [] }); const aid = ref({ items: [] }); const funding = ref({ items: [] }); const dorm = ref({}); const discipline = ref({ items: [] }); const psy = ref({ questions: [] }); const psyHistory = ref({ items: [] }); const activities = ref({ available: [], mine: [] }); const talk = ref({ items: [] }); const aidBatches = ref([]); const fundingBatches = ref([]); const secondClass = ref({ items: [], byType: [] }); const creditAppeals = ref([]); const dormTransfers = ref([]); const dormStays = ref([]); const dormRectifications = ref([]); const dormTransferError = ref(''); const rectNotes = reactive({}); const rectFiles = reactive({}); const rectRequests = reactive({})
const talkItems = computed(() => {
  const rows = talk.value.items || []
  if (!focusedTalkId.value) return rows
  const index = rows.findIndex((item) => String(item.talkId) === focusedTalkId.value)
  return index > 0 ? [rows[index], ...rows.slice(0, index), ...rows.slice(index + 1)] : rows
})
const leaveForm = reactive({ leaveType: 'PERSONAL', startTime: '', endTime: '', reason: '' }); const extendId = ref(''); const extendForm = reactive({ newEndTime: '', reason: '' }); const aidForm = reactive({ batchId: '', applyLevel: 'GENERAL', memberCount: null, annualIncome: null, debt: null, specialTags: '', statement: '', confirm: false }); const fundForm = reactive({ projectType: 'SCHOLARSHIP', batchId: '', statement: '', confirm: false }); const aidObjections = reactive({}); const fundAppeals = reactive({}); const disciplineAppeals = reactive({}); const psyAnswers = reactive({}); const psyWantsContact = ref(false); const psyResult = ref(null); const dormBuildings = ref([]); const dormRooms = ref([]); const dormBeds = ref([]); const dormForm = reactive({ visible: false, buildingId: '', roomId: '', bedId: '', reason: '' }); const modal = reactive({ type: '', title: '', notice: '', item: null, form: {} })

const dateText = (d = new Date()) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const today = dateText()
const fmt = (value) => tab.value === 'leave' ? leaveDate(value) : (value || '').slice(0, 10)
const fmtTime = (value) => String(value || '').slice(0, 16).replace('T', ' ') || '—'
const enumText = (value) => localizeVisibleEnumText(value)
const dayAfter = (value) => { if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) return ''; const d = new Date(`${value}T00:00:00`); if (Number.isNaN(d.getTime())) return ''; d.setDate(d.getDate() + 1); return dateText(d) }
const validReason = (value, min, max) => { const n = String(value || '').trim().length; return n >= min && n <= max }
const nonNegativeOrBlank = (value) => value === '' || value === null || value === undefined || (Number.isFinite(Number(value)) && Number(value) >= 0)
const aidValidationError = computed(() => { if (!Number.isInteger(Number(aidForm.memberCount)) || Number(aidForm.memberCount) < 1 || Number(aidForm.memberCount) > 30) return '家庭成员数应为1-30人的整数'; if (!nonNegativeOrBlank(aidForm.annualIncome)) return '家庭年收入不得为负数'; if (!nonNegativeOrBlank(aidForm.debt)) return '家庭债务不得为负数'; if (!validReason(aidForm.statement, 10, 500)) return '困难情况说明需10-500字'; return '' })
const validLeave = computed(() => !!leaveForm.startTime && !!leaveForm.endTime && leaveForm.endTime >= leaveForm.startTime && validReason(leaveForm.reason, 5, 300))
const validAid = computed(() => !!aidForm.batchId && !aidValidationError.value && aidForm.confirm)
const fundingAttachments = reactive({ fileIds: [], ready: true, hasDraft: false, busy: false, items: [] })
const fundingAttachmentEpoch = ref(0)
const fundingMaterialId = ref('')
const validFunding = computed(() => !!fundForm.batchId && validReason(fundForm.statement, 5, 1000) && fundForm.confirm && fundingAttachments.ready)
const psyComplete = computed(() => (psy.value.questions || []).length > 0 && (psy.value.questions || []).every((q) => psyAnswers[q.key] != null))
const pendingDormTransfer = computed(() => dormTransfers.value.find((x) => ['SUBMITTED', 'COUNSELOR_REVIEW', 'DORM_MANAGER_REVIEW', 'DORM_REVIEW', 'PENDING'].includes(x.status || x.currentNode)) || null)
const availableDormBeds = computed(() => dormBeds.value.filter((x) => x.status === 'VACANT' && !x.isCurrent))
const selectedDormTarget = computed(() => { const b = dormBuildings.value.find((x) => String(x.buildingId) === String(dormForm.buildingId)) || {}; const r = dormRooms.value.find((x) => String(x.roomId) === String(dormForm.roomId)) || {}; const bd = dormBeds.value.find((x) => String(x.bedId) === String(dormForm.bedId)) || {}; return [b.buildingName, r.roomNo && `${r.roomNo}室`, bd.bedNo && `${bd.bedNo}床`].filter(Boolean).join(' / ') || `床位 #${dormForm.bedId}` })
const validDormAction = computed(() => !!dormForm.bedId && !pendingDormTransfer.value && (!dorm.value.hasBed || validReason(dormForm.reason, 5, 300)))
const creditClaimError = computed(() => { if (modal.type !== 'credit') return ''; const value = Number(modal.form.claimValue); if (!Number.isFinite(value) || value <= 0) return '主张数值必须大于0'; if (value > 9999.99) return '主张数值不得超过9999.99'; if (Math.abs(Math.round(value * 100) - value * 100) > 1e-8) return '主张数值最多保留2位小数'; return '' })
const modalValidationError = computed(() => { const f = modal.form || {}; if (modal.type === 'leave') return (!f.startTime || !f.endTime || f.endTime < f.startTime || !validReason(f.reason, 5, 300)) ? '请填写有效起止日期和5-300字事由' : ''; if (modal.type === 'aid') { if (!Number.isInteger(Number(f.memberCount)) || Number(f.memberCount) < 1 || Number(f.memberCount) > 30) return '家庭成员数应为1-30人的整数'; if (!nonNegativeOrBlank(f.annualIncome) || !nonNegativeOrBlank(f.debt)) return '年收入和债务不得为负数'; return validReason(f.statement, 10, 500) ? '' : '困难情况说明需10-500字' } if (modal.type === 'funding') return validReason(f.statement, 5, 1000) ? '' : '申请理由需5-1000字'; if (modal.type === 'credit') return creditClaimError.value || (validReason(f.reason, 5, 1000) ? '' : '申诉理由需5-1000字'); return '' })
const modalValid = computed(() => !!modal.type && !modalValidationError.value)

const aidBatchQuery = ref(''); const aidBatchTotal = ref(0); const aidBatchPage = ref(0)
const aidBatchLoading = ref(false); const aidBatchError = ref(''); const aidSelectedBatch = ref(null)
let aidBatchSeq = 0; let aidBatchAppliedQuery = ''
const aidBatchOptions = computed(() => aidSelectedBatch.value && !aidBatches.value.some(x => x.batchId === aidSelectedBatch.value.batchId) ? [aidSelectedBatch.value, ...aidBatches.value] : aidBatches.value)
function selectAidBatch() { aidSelectedBatch.value = aidBatchOptions.value.find(x => x.batchId === aidForm.batchId) || null }
async function loadAidBatches(more = false) {
  if (more && aidBatchLoading.value) return
  const seq = ++aidBatchSeq
  const page = more ? aidBatchPage.value + 1 : 1
  const keyword = more ? aidBatchAppliedQuery : aidBatchQuery.value.trim()
  aidBatchLoading.value = true; aidBatchError.value = ''
  try {
    const data = await portalApi.affairsAidBatches({ page, pageSize: 20, keyword })
    if (!viewActive || seq !== aidBatchSeq) return
    const rows = data?.items || []
    aidBatches.value = more ? [...new Map([...aidBatches.value, ...rows].map(x => [x.batchId, x])).values()] : rows
    aidBatchTotal.value = data?.total ?? rows.length; aidBatchPage.value = page; aidBatchAppliedQuery = keyword
  } catch {
    if (seq === aidBatchSeq) aidBatchError.value = '批次查找失败，已选批次和填写内容已保留，请重试。'
  } finally { if (seq === aidBatchSeq) aidBatchLoading.value = false }
}

const fundingLabel = (type) => ({ SCHOLARSHIP: '奖学金', GRANT: '助学金', WORK_STUDY: '勤工助学', LOAN: '助学贷款', TUITION_REDUCTION: '学费减免', TEMPORARY_AID: '临时补助' }[type] || type)
const appealLabel = (status) => ({ SUBMITTED: '申诉已提交', REVIEWING: '复核中', UPHELD: '维持原处分', REVISED: '处分已变更', REVOKED: '处分已撤销' }[status] || status || '未申诉')
const disciplineStatusLabel = (item) => item?.caseStatus === 'REMOVED' ? '处分已解除' : appealLabel(item?.appealStatus)
const creditLabel = (type) => ({ SECOND_CLASS: '第二课堂', MORAL: '德育积分', VOLUNTEER_HOUR: '志愿时长' }[type] || type)
const severityText = (value) => ({ LOW: '低风险', MEDIUM: '中风险', HIGH: '高风险', CRITICAL: '重大风险' }[value] || value)
const rectStatusText = (value) => ({ OPEN: '待整改', RECTIFYING: '整改中', WAITING_RECHECK: '待复检', CLOSED: '已关闭', ESCALATED: '已升级' }[value] || value)
const clientRequestId = () => `dorm-rectify-${globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`}`.slice(0, 100)
const notifyError = (e, fallback) => ui.notify(tab.value === 'leave' ? leaveError(e, fallback) : (e?.message || fallback))

const fundingBatchQuery = ref(''); const fundingBatchTotal = ref(0); const fundingBatchPage = ref(0)
const fundingBatchLoading = ref(false); const fundingBatchError = ref(''); const fundingSelectedBatch = ref(null)
let fundingBatchSeq = 0; let fundingBatchAppliedQuery = ''
const fundingBatchOptions = computed(() => fundingSelectedBatch.value && !fundingBatches.value.some(x => x.batchId === fundingSelectedBatch.value.batchId) ? [fundingSelectedBatch.value, ...fundingBatches.value] : fundingBatches.value)
function selectFundingBatch() { fundingSelectedBatch.value = fundingBatchOptions.value.find(x => x.batchId === fundForm.batchId) || null; fundForm.confirm = false }
function changeFundingType() {
  fundForm.batchId = ''; fundForm.confirm = false; fundingSelectedBatch.value = null
  fundingBatches.value = []; fundingBatchTotal.value = 0; fundingBatchPage.value = 0
  return loadFundingBatches()
}
async function loadFundingBatches(more = false) {
  if (more && fundingBatchLoading.value) return
  const seq = ++fundingBatchSeq
  const page = more ? fundingBatchPage.value + 1 : 1
  const keyword = more ? fundingBatchAppliedQuery : fundingBatchQuery.value.trim()
  fundingBatchLoading.value = true; fundingBatchError.value = ''
  try {
    const data = await portalApi.affairsFundingBatches({ page, pageSize: 20, keyword, projectType: fundForm.projectType })
    if (!viewActive || seq !== fundingBatchSeq) return
    const rows = data?.items || []
    fundingBatches.value = more ? [...new Map([...fundingBatches.value, ...rows].map(x => [x.batchId, x])).values()] : rows
    fundingBatchTotal.value = data?.total ?? rows.length; fundingBatchPage.value = page; fundingBatchAppliedQuery = keyword
  } catch {
    if (seq === fundingBatchSeq) fundingBatchError.value = '批次查找失败，已选批次和填写内容已保留，请重试。'
  } finally { if (seq === fundingBatchSeq) fundingBatchLoading.value = false }
}

const TAB_LOADERS = {
  leave: [{ load: () => portalApi.affairsLeave(), apply: (value) => { leave.value = value || { items: [] } } }],
  aid: [{ load: () => portalApi.affairsAid(), apply: (value) => { aid.value = value || { items: [] } } }, { load: () => loadAidBatches(), apply: () => {} }],
  funding: [{ load: () => portalApi.affairsFunding(), apply: (value) => { funding.value = value || { items: [] } } }, { load: () => loadFundingBatches(), apply: () => {} }],
  dorm: [{ load: () => portalApi.affairsDorm(), apply: (value) => { dorm.value = value || {} } }, { load: () => affairsFourEndApi.myDormTransfers(), optional: true, apply: (value) => { dormTransferError.value = ''; dormTransfers.value = value?.items || [] }, fail: () => { dormTransfers.value = []; dormTransferError.value = '调宿申请记录暂时无法读取，当前宿舍与床位信息仍可正常查看。' } }, { load: () => affairsFourEndApi.myDormStays(), apply: (value) => { dormStays.value = value?.items || [] } }, { load: () => affairsFourEndApi.myDormRectifications({ pageSize: 200 }), apply: (value) => { dormRectifications.value = value?.items || [] } }],
  discipline: [{ load: () => portalApi.affairsDiscipline(), apply: (value) => { discipline.value = value || { items: [] } } }],
  psy: [{ load: () => portalApi.affairsPsyQuestions(), apply: (value) => { psy.value = value || { questions: [] } } }, { load: () => portalApi.affairsPsyHistory(), apply: (value) => { psyHistory.value = value || { items: [] } } }],
  activity: [{ load: () => portalApi.affairsActivitiesMy(), apply: (value) => { activities.value = value || { available: [], mine: [] } } }, { load: () => affairsFourEndApi.secondClassReport(), apply: (value) => { secondClass.value = { items: [], byType: [], ...(value || {}) } } }, { load: () => affairsFourEndApi.myCreditAppeals(), apply: (value) => { creditAppeals.value = value?.items || [] } }],
  talk: [{ load: () => portalApi.affairsTalk(), apply: (value) => { talk.value = value || { items: [] } } }]
}

function loadTab(key, { force = false } = {}) {
  const entries = TAB_LOADERS[key]
  if (!entries) return Promise.resolve()
  if (!force && loadedTabs[key]) return Promise.resolve()
  if (inflight.has(key)) return inflight.get(key)
  const epoch = (loadEpoch[key] || 0) + 1
  loadEpoch[key] = epoch
  loadingTabs[key] = true
  delete errors[key]
  const promise = Promise.allSettled(entries.map((entry) => entry.load()))
    .then((results) => {
      if (!viewActive || loadEpoch[key] !== epoch) return
      const failures = []
      results.forEach((result, index) => {
        if (result.status === 'fulfilled') entries[index].apply(result.value)
        else if (entries[index].optional) entries[index].fail?.(result.reason)
        else failures.push(key === 'leave' ? leaveError(result.reason, '请假记录加载失败，请重试。') : result.reason?.message || '数据加载失败')
      })
      if (failures.length) errors[key] = [...new Set(failures)].join('；')
      loadedTabs[key] = true
    })
    .finally(() => {
      if (loadEpoch[key] === epoch) loadingTabs[key] = false
      if (inflight.get(key) === promise) inflight.delete(key)
    })
  inflight.set(key, promise)
  return promise
}

function reload() { return loadTab(tab.value, { force: true }) }

async function run(task, success, fallback, refreshKey = tab.value) {
  busy.value = true
  try {
    const data = await task()
    ui.notify(success)
    await loadTab(refreshKey, { force: true })
    return { ok: true, data }
  } catch (e) {
    notifyError(e, fallback)
    return { ok: false, error: e }
  } finally {
    busy.value = false
  }
}

async function applyLeave() { if (!validLeave.value) return ui.notify('请填写有效日期和5-300字事由'); const result = await run(() => portalApi.affairsLeaveApply({ ...leaveForm }), '请假已提交', '请假提交失败', 'leave'); if (result.ok) leaveForm.reason = '' }
function cancelLeave(item) { Object.assign(modal, { type: 'leaveCancel', title: '确认提交销假', notice: '', item, form: { period: `${leaveDate(item.startTime)} 至 ${leaveDate(item.endTime)}` } }) }
function openExtend(item) { extendId.value = item.leaveId; extendForm.newEndTime = dayAfter(leaveDate(item.endTime)); extendForm.reason = '' }
function validExtend(item) { return !!extendForm.newEndTime && extendForm.newEndTime > leaveDate(item.endTime) && validReason(extendForm.reason, 5, 300) }
async function submitExtend(item) { if (!validExtend(item)) return ui.notify('新结束日期必须晚于原结束日期，续假事由需5-300字'); const result = await run(() => affairsFourEndApi.extendLeave(item.leaveId, item.version, extendForm.newEndTime, extendForm.reason), '续假申请已提交', '续假提交失败', 'leave'); if (result.ok) extendId.value = '' }
async function editLeave(item) { busy.value = true; try { const data = await affairsFourEndApi.getReturnedLeave(item.leaveId); Object.assign(modal, { type: 'leave', title: '修改退回请假', notice: data.returnReason || item.returnReason, item: data, form: { leaveType: data.leaveType, startTime: leaveDate(data.startTime), endTime: leaveDate(data.endTime), reason: data.reason || '' } }) } catch (e) { notifyError(e, '加载失败') } finally { busy.value = false } }
async function submitAid() { if (!validAid.value) return ui.notify(aidValidationError.value || '请完成本人确认'); const body = { batchId: aidForm.batchId, applyLevel: aidForm.applyLevel, memberCount: Number(aidForm.memberCount), annualIncome: aidForm.annualIncome === '' || aidForm.annualIncome == null ? null : Number(aidForm.annualIncome), debt: aidForm.debt === '' || aidForm.debt == null ? null : Number(aidForm.debt), specialTags: aidForm.specialTags.split(/[,，]/).map((x) => x.trim()).filter(Boolean), statement: aidForm.statement, confirm: true }; const result = await run(() => portalApi.affairsAidApply(body), '困难认定申请已提交', '提交失败', 'aid'); if (result.ok) { aidForm.statement = ''; aidForm.confirm = false } }
async function editAid(item) { busy.value = true; try { const data = await affairsFourEndApi.getReturnedAid(item.applyId); Object.assign(modal, { type: 'aid', title: '修改退回认定申请', notice: item.returnReason, item: data, form: { applyLevel: data.applyLevel, memberCount: data.memberCount, annualIncome: data.annualIncome, debt: data.debt, specialTags: Array.isArray(data.specialTags) ? data.specialTags.join('，') : '', statement: data.statement || '' } }) } catch (e) { notifyError(e, '加载失败') } finally { busy.value = false } }
async function submitAidObjection(item) { if (!validReason(aidObjections[item.applyId], 5, 500)) return ui.notify('异议理由需5-500字'); const result = await run(() => portalApi.affairsAidObjection({ applyId: item.applyId, reason: aidObjections[item.applyId] }), '异议已提交并进入老师待办', '异议提交失败', 'aid'); if (result.ok) aidObjections[item.applyId] = '' }
async function submitFunding() { if (busy.value || fundingAttachments.busy) return; if (!fundingAttachments.ready) return ui.notify('附件尚未全部就绪，请检查状态或移除不可用文件'); if (!validFunding.value) return ui.notify('请选择批次、填写5-1000字申请理由并确认'); const result = await run(() => portalApi.affairsFundingApply({ batchId: fundForm.batchId, statement: fundForm.statement, confirm: true, fileIds: fundingAttachments.fileIds }), '奖助申请已提交', '提交失败', 'funding'); if (result.ok) { fundForm.statement = ''; fundForm.confirm = false; fundingAttachmentEpoch.value++; Object.assign(fundingAttachments, { fileIds: [], ready: true, hasDraft: false, busy: false, items: [] }) } }
async function editFunding(item) { busy.value = true; try { const data = await affairsFourEndApi.getReturnedFunding(item.applicationId); Object.assign(modal, { type: 'funding', title: '修改退回奖助申请', notice: item.returnReason, item: data, form: { statement: data.statement || '' } }) } catch (e) { notifyError(e, '加载失败') } finally { busy.value = false } }
async function submitFundingAppeal(item) { if (!validReason(fundAppeals[item.applicationId], 5, 1000)) return ui.notify('申诉理由需5-1000字'); const result = await run(() => portalApi.affairsFundingAppeal({ applicationId: item.applicationId, reason: fundAppeals[item.applicationId] }), '申诉已提交并进入老师待办', '申诉提交失败', 'funding'); if (result.ok) fundAppeals[item.applicationId] = '' }
async function loadDormOptions() { if (dorm.value.hasBed && dormTransferError.value) return ui.notify('请先刷新调宿记录后再申请'); if (pendingDormTransfer.value) return ui.notify('已有调宿申请处理中，不能重复提交'); busy.value = true; try { const data = await (dorm.value.hasBed ? affairsFourEndApi.dormTransferOptions() : affairsFourEndApi.dormSelectOptions()); dormBuildings.value = data.items || data.buildings || []; dormForm.visible = true } catch (e) { notifyError(e, dorm.value.hasBed ? '调宿选项加载失败' : '可选床位加载失败') } finally { busy.value = false } }
async function loadRooms() { dormForm.roomId = ''; dormForm.bedId = ''; dormRooms.value = []; dormBeds.value = []; if (!dormForm.buildingId) return; try { const data = await (dorm.value.hasBed ? affairsFourEndApi.dormTransferRooms(dormForm.buildingId) : affairsFourEndApi.dormSelectRooms(dormForm.buildingId)); dormRooms.value = data.items || [] } catch (e) { notifyError(e, '房间加载失败') } }
async function loadBeds() { dormForm.bedId = ''; dormBeds.value = []; if (!dormForm.roomId) return; try { const data = await (dorm.value.hasBed ? affairsFourEndApi.dormTransferBeds(dormForm.roomId) : affairsFourEndApi.dormSelectBeds(dormForm.roomId)); dormBeds.value = data.items || [] } catch (e) { notifyError(e, '床位加载失败') } }
function closeDormForm() { if (!busy.value) Object.assign(dormForm, { visible: false, buildingId: '', roomId: '', bedId: '', reason: '' }) }
function submitDormAction() { if (!validDormAction.value) return ui.notify(dorm.value.hasBed ? '请选择目标床位并填写5-300字调宿原因' : '请选择床位'); Object.assign(modal, { type: 'dormConfirm', title: dorm.value.hasBed ? '确认提交调宿' : '确认选择床位', notice: '', item: null, form: { target: selectedDormTarget.value } }) }
async function startDormRectification(item) { await run(() => affairsFourEndApi.startDormRectification(item.rectificationId, item.version), '整改已开始', '开始整改失败', 'dorm') }
async function pickRectFile(item, event) { const file = event.target?.files?.[0]; if (!file) return; busy.value = true; try { const uploaded = await affairsFourEndApi.uploadDormEvidence(file); rectFiles[item.rectificationId] = { fileId: String(uploaded.fileId || uploaded.id), fileName: uploaded.fileName || file.name } } catch (e) { notifyError(e, '整改照片上传失败') } finally { busy.value = false; event.target.value = '' } }
async function submitDormRectification(item) {
  const note = String(rectNotes[item.rectificationId] || '').trim()
  const file = rectFiles[item.rectificationId]
  if (!validReason(note, 5, 1000) || !file) return ui.notify('请填写5-1000字整改说明并上传照片')
  const payload = { expectedVersion: item.version, note, fileIds: [file.fileId] }
  const signature = JSON.stringify(payload)
  let request = rectRequests[item.rectificationId]
  if (!request || request.signature !== signature) {
    request = { signature, id: clientRequestId() }
    rectRequests[item.rectificationId] = request
  }
  const result = await run(() => affairsFourEndApi.submitDormRectification(item.rectificationId, { ...payload, clientRequestId: request.id }), '整改已提交复检', '整改提交失败', 'dorm')
  if (result.ok) {
    rectNotes[item.rectificationId] = ''
    delete rectFiles[item.rectificationId]
    delete rectRequests[item.rectificationId]
  }
}
async function submitDisciplineAppeal(item) { if (!validReason(disciplineAppeals[item.caseId], 5, 1000)) return ui.notify('处分申诉理由需5-1000字'); const result = await run(() => portalApi.affairsDisciplineAppeal({ caseId: item.caseId, reason: disciplineAppeals[item.caseId] }), '处分申诉已提交', '申诉提交失败', 'discipline'); if (result.ok) disciplineAppeals[item.caseId] = '' }
async function submitPsy() {
  if (!psyComplete.value) return ui.notify('请完成全部题目')
  const answers = (psy.value.questions || []).map((q) => ({ qKey: q.key, score: psyAnswers[q.key] }))
  const result = await run(() => portalApi.affairsPsySubmit({ answers, wantsContact: psyWantsContact.value }), '心理自评已提交', '自评提交失败', 'psy')
  if (result.ok) {
    psyResult.value = result.data
    Object.keys(psyAnswers).forEach((key) => delete psyAnswers[key])
    psyWantsContact.value = false
  }
}
async function enroll(item) { await run(() => portalApi.affairsActivityEnroll(item.activityId), '报名成功', '报名失败', 'activity') }
function openCreditAppeal(item) { Object.assign(modal, { type: 'credit', title: item ? '第二课堂记错申诉' : '第二课堂缺记申诉', notice: '', item, form: { appealType: item ? 'WRONG' : 'MISSING', activityId: item?.activityId || '', activityName: item?.remark || '', claimCreditType: item?.creditType || 'SECOND_CLASS', claimValue: item?.creditValue == null ? '' : String(item.creditValue), reason: '' } }) }
function closeModal() { if (!busy.value) Object.assign(modal, { type: '', title: '', notice: '', item: null, form: {} }) }
async function submitUpdatedAndResubmit({ update, resubmit, success, refreshKey }) { busy.value = true; try { const updated = await update(); modal.item = { ...(modal.item || {}), ...(updated || {}), version: updated?.version ?? modal.item?.version }; try { await resubmit(modal.item.version) } catch (e) { modal.notice = `修改已保存，但重新提交失败：${e?.message || '请保留当前内容后重试'}`; notifyError(e, '重新提交失败'); return false } ui.notify(success); await loadTab(refreshKey, { force: true }); setTimeout(() => closeModal(), 0); return true } catch (e) { notifyError(e, '保存修改失败'); return false } finally { busy.value = false } }
async function submitReturnedFunding() {
  if (busy.value) return
  const id = String(modal.item.applicationId)
  const submitted = await submitUpdatedAndResubmit({
    update: () => affairsFourEndApi.updateReturnedFunding(id, { ...modal.form, version: modal.item.version }),
    resubmit: (version) => affairsFourEndApi.resubmitFunding(id, version),
    success: '奖助申请已修改并重新提交', refreshKey: 'funding'
  })
  if (submitted) fundingDetailId.value = id
}
async function submitModal() {
  if (!modalValid.value) return ui.notify(modalValidationError.value)
  if (modal.type === 'leave') { const id = modal.item.leaveId || modal.item.id; await submitUpdatedAndResubmit({ update: () => affairsFourEndApi.updateReturnedLeave(id, { ...modal.form, version: modal.item.version }), resubmit: (version) => affairsFourEndApi.resubmitLeave(id, version), success: '请假已修改并重新提交', refreshKey: 'leave' }) }
  else if (modal.type === 'aid') { const id = modal.item.applyId; const body = { ...modal.form, memberCount: Number(modal.form.memberCount), annualIncome: modal.form.annualIncome === '' || modal.form.annualIncome == null ? null : Number(modal.form.annualIncome), debt: modal.form.debt === '' || modal.form.debt == null ? null : Number(modal.form.debt), specialTags: String(modal.form.specialTags || '').split(/[,，]/).map((x) => x.trim()).filter(Boolean), version: modal.item.version }; await submitUpdatedAndResubmit({ update: () => affairsFourEndApi.updateReturnedAid(id, body), resubmit: (version) => affairsFourEndApi.resubmitAid(id, version), success: '认定申请已修改并重新提交', refreshKey: 'aid' }) }
  else if (modal.type === 'funding') { await submitReturnedFunding() }
  else if (modal.type === 'credit') { const result = await run(() => affairsFourEndApi.submitCreditAppeal({ ...modal.form, claimValue: Number(modal.form.claimValue) }), '积分申诉已提交', '申诉提交失败', 'activity'); if (result.ok) setTimeout(() => closeModal(), 0) }
  else if (modal.type === 'dormConfirm') { const result = await run(() => dorm.value.hasBed ? affairsFourEndApi.submitDormTransfer(dormForm.bedId, dormForm.reason) : affairsFourEndApi.selfSelectDormBed(dormForm.bedId), dorm.value.hasBed ? '调宿申请已提交' : '床位已确认', dorm.value.hasBed ? '调宿提交失败' : '选床失败', 'dorm'); if (result.ok) { closeModal(); closeDormForm() } }
  else if (modal.type === 'leaveCancel') { const item = modal.item; const result = await run(() => affairsFourEndApi.cancelLeave(item.leaveId, item.version, '学生本人申请销假'), '销假申请已提交', '销假提交失败', 'leave'); if (result.ok) closeModal() }
}

const registerWorkspaceForm = inject('registerWorkspaceForm', null)
let unregisterFundingForm
function fundingHasEdits() {
  return busy.value || fundingAttachments.busy || fundingAttachments.hasDraft || !!fundForm.statement.trim() || fundForm.confirm ||
    Object.values(fundAppeals).some(value => String(value || '').trim()) || modal.type === 'funding'
}
function dormHasEdits() {
  return busy.value || (dormForm.visible && !!(dormForm.buildingId || dormForm.roomId || dormForm.bedId || dormForm.reason.trim())) ||
    Object.values(rectNotes).some(value => String(value || '').trim()) || Object.values(rectFiles).some(Boolean)
}
watch(tab, (key) => { loadTab(key, { force: key === 'dorm' }) }, { immediate: true })
watch(tab, (key) => {
  unregisterFundingForm?.(); unregisterFundingForm = null
  if (key === 'funding') unregisterFundingForm = registerWorkspaceForm?.(fundingHasEdits, () => busy.value || fundingAttachments.busy)
  if (key === 'dorm') unregisterFundingForm = registerWorkspaceForm?.(dormHasEdits, () => busy.value)
}, { immediate: true })
onBeforeUnmount(() => {
  unregisterFundingForm?.()
  viewActive = false
  Object.keys(loadEpoch).forEach((key) => { loadEpoch[key] += 1 })
  inflight.clear()
})
</script>

<style scoped>
.aid-batch-search, .aid-batch-results { display: flex; align-items: end; gap: 10px; flex-wrap: wrap; }
.aid-batch-search label { flex: 1; min-width: 180px; }
.aid-batch-results { align-items: center; font-size: 12px; color: var(--text-secondary); }
.aid-application { margin: 16px 0; border: 1px solid var(--border-light); border-radius: 12px; padding: 12px 16px; }
.aid-application summary { cursor: pointer; color: var(--text-primary); font-weight: 600; padding: 4px 0; }
.aid-application[open] summary { margin-bottom: 16px; }
.allocation-card { margin:12px 0;padding:14px;border-radius:10px;background:#eff6ff;border:1px solid #bfdbfe }.allocation-card p { margin:6px 0 0 }
.presence-card { display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:12px 0;padding:14px;border:1px solid #dbeafe;border-radius:10px;background:#f8fafc }.presence-card span,.presence-card strong { display:block }.presence-card span { color:var(--t3);font-size:12px;margin-bottom:4px }.presence-card p { grid-column:1/-1;margin:0;color:var(--t2);font-size:12.5px }
.rect-card { border:1px solid #e2e8f0;border-radius:10px;padding:14px;margin-top:10px }.rect-requirement { margin:7px 0 0;color:var(--t2);line-height:1.6 }.file-pick { display:grid;gap:6px;color:var(--t3);font-size:12px }.file-pick input { padding:8px;border:1px solid #e2e8f0;border-radius:8px;background:#fff }
.confirm-summary { display:grid;gap:8px;padding:14px;border-radius:10px;background:#f8fafc }.confirm-summary strong { color:var(--t3);font-size:12px }.confirm-summary span { color:var(--t1);font-weight:700 }.confirm-summary p { margin:4px 0 0;color:#b45309;font-size:12.5px }
.two { display:grid;grid-template-columns:1fr 1fr;gap:18px;align-items:start }.form-grid { display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px }.form-grid.compact { max-width:760px }.form-grid label span,.inline-form label span { display:block;font-size:12px;color:var(--t3);margin-bottom:5px }.wide { grid-column:1/-1 }.record { padding:13px 0;border-bottom:1px solid #edf0f4 }.record.is-focused-record { margin:0 -10px;padding:13px 10px;border-left:3px solid var(--pri);background:var(--pri-50) }.record-head { display:flex;justify-content:space-between;align-items:flex-start;gap:12px }.actions { display:flex;gap:8px;flex-wrap:wrap;margin-top:10px }.inline-form { margin-top:10px;padding:12px;background:#f8fafc;border-radius:10px;display:grid;gap:9px }.check { display:flex;align-items:flex-start;gap:8px;font-size:12.5px;color:var(--t2);margin:10px 0 }.warn { color:#b45309;font-size:12.5px;margin-top:5px }.field-error { color:#dc2626;font-size:12.5px;margin:5px 0 }.selected-target { padding:9px 11px;border-radius:8px;background:#eff6ff;color:#1d4ed8;font-weight:600 }.section-title { font-size:15px;font-weight:650;margin:24px 0 8px }.domain-error { display:flex;gap:12px;align-items:center;padding:12px 16px;background:#fff7ed;border:1px solid #fed7aa;border-radius:10px;color:#9a3412;margin-bottom:16px }.bed-grid { display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:14px 0 }.bed-grid div { background:#f8fafc;padding:12px;border-radius:9px }.bed-grid span,.bed-grid strong { display:block }.bed-grid span { font-size:12px;color:var(--t3);margin-bottom:4px }.question { padding:16px 0;border-bottom:1px solid #edf0f4 }.options { display:flex;gap:8px;flex-wrap:wrap;margin-top:8px }.seg { all:unset;cursor:pointer;padding:7px 12px;border-radius:8px;background:#f1f5f9;font-size:12.5px }.seg.on { background:var(--pri-50);color:var(--pri);font-weight:600 }.psy-workspace{max-width:1100px}.psy-form{max-width:850px}.psy-contact{display:flex;align-items:center;gap:9px;padding:16px 0;font-size:13px;color:var(--t2)}.psy-receipt{display:flex;gap:12px;align-items:center;padding:12px 14px;margin:14px 0;border-left:3px solid #16a34a;background:#f0fdf4;color:#166534}.psy-receipt span{font-size:13px}.psy-history{max-width:850px}.score-card { display:flex;justify-content:space-between;align-items:center;margin-bottom:16px }.score { display:flex;gap:18px;font-size:18px;font-weight:700;color:var(--pri) }.link { all:unset;display:block;cursor:pointer;color:var(--pri);font-size:12px;margin-top:5px }.mask { position:fixed;inset:0;background:rgba(15,23,42,.5);z-index:1000;display:flex;align-items:center;justify-content:center;padding:24px }.modal { width:min(680px,100%);max-height:88vh;overflow:auto }.dorm-form { max-width:700px }
@media(max-width:900px){.two,.form-grid,.presence-card{grid-template-columns:1fr}.presence-card p{grid-column:auto}.wide{grid-column:auto}.bed-grid{grid-template-columns:1fr 1fr}.score-card{align-items:flex-start;gap:14px;flex-direction:column}}
</style>
