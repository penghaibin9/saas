<template>
  <div class="sp-page">
    <section v-if="!loading && !error && my.hasData" class="sp-card sp-now" aria-labelledby="sp-now-title">
      <div class="sp-now__copy">
        <span class="sp-now__eyebrow">NOW ACTION</span>
        <h2 id="sp-now-title">{{ currentAction.title }}</h2>
        <p>{{ currentAction.reason }}</p>
        <div class="sp-now__meta">
          <span>最近变化：{{ currentAction.recentChange }}</span>
          <span>完成后：{{ currentAction.nextActor }}</span>
        </div>
      </div>
      <button type="button" class="sp-btn" @click="selectTab(currentAction.tab)">{{ currentAction.action }} →</button>
    </section>

    <nav class="sp-process-nav" aria-label="实习办理分组">
      <details v-for="group in tabGroups" :key="group.key" class="sp-process-group" :open="groupOpen(group)">
        <summary>
          <span><b>{{ group.label }}</b><small>{{ group.hint }}</small></span>
          <span class="sp-process-group__current">{{ activeGroupLabel(group) }}</span>
        </summary>
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
      <section v-else-if="my.hasData && currentSource.status === 'empty'" class="sp-source-state" aria-live="polite">
        <StateBlock type="empty" :text="`${currentSource.label}暂无历史记录；如有可办理事项，仍可在下方发起。`" />
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
        <section class="sp-card" style="margin-bottom:16px">
          <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:20px;flex-wrap:wrap">
            <div>
              <div style="font-size:18px;font-weight:600">{{ my.enterpriseName }} · {{ my.positionName }}</div>
              <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px">
                <span class="pill"><span style="color:#A9B0BD">指导教师</span>{{ my.advisorName || '待分配' }}</span>
                <span class="pill"><span style="color:#A9B0BD">风险等级</span>{{ riskText(my.riskLevel) }}</span>
              </div>
            </div>
            <span class="statepill"><span class="dot" />{{ statusText(my.status) }}</span>
          </div>
          <FlowSteps :steps="flowSteps" style="margin-top:22px" />
        </section>
        <div class="m4">
          <div v-for="m in metrics" :key="m.t" class="sp-metric"><div class="sp-metric__label">{{ m.t }}</div><div class="sp-metric__value" :style="{color:m.c}">{{ m.v }}<small>{{ m.u }}</small></div></div>
        </div>
      </template>

      <!-- 三方协议 -->
      <template v-else-if="tab === 'agreement'">
        <div class="two">
          <section class="sp-card">
            <div class="sp-panel__head">实习三方协议 <StatusTag :text="agreementStatusText" :tone="agreementTone" /></div>
            <div class="agreement">甲方（学校）：{{ brandSchool }}<br />乙方（企业）：{{ my.enterpriseName }}<br />丙方（学生）：{{ studentName }}<br />实习岗位：{{ my.positionName }} · 指导教师：{{ my.advisorName || '待分配' }}</div>
            <div style="display:flex;gap:10px;margin-top:16px;flex-wrap:wrap">
              <button class="sp-btn sp-btn--ghost" :disabled="busy" @click="printAgreement">打印协议</button>
              <button v-if="activeAgreement?.status==='PENDING_STUDENT'" class="sp-btn" :disabled="busy" @click="confirmAgreement('CONFIRM')">确认协议</button>
              <button v-if="activeAgreement?.status==='PENDING_STUDENT'" class="sp-btn sp-btn--ghost" :disabled="busy" @click="confirmAgreement('REJECT')">驳回协议</button>
            </div>
            <p class="sp-muted" style="margin-top:10px">盖章件由学校代录企业纸质签署；学生确认/驳回两端同一数据。来源口径为「学校录入」，不是企业端登录签署。</p>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">协议列表</div>
            <AutoTable :rows="agreements" empty="暂无协议" :columns="[{key:'enterpriseName',label:'企业'},{key:'statusLabel',label:'状态'},{key:'positionName',label:'岗位'}]" />
          </section>
        </div>
      </template>

      <!-- 每日打卡 -->
      <template v-else-if="tab === 'checkin'">
        <div class="two2">
          <section class="sp-card" style="text-align:center">
            <div class="sp-muted">今日打卡</div>
            <div style="font-size:30px;font-weight:700;margin-top:4px;font-variant-numeric:tabular-nums">{{ my.todayCheckin?.done ? (my.todayCheckin.time || '已打卡') : '未打卡' }}</div>
            <div class="sp-muted" style="margin-top:6px">累计出勤 {{ my.todayCheckin?.totalDays ?? 0 }} 天</div>
            <div class="notebox">PC 门户可登记打卡；带地理围栏的精确核验仍以学生小程序为准。无定位时记为「已记录」，不会自动认定作弊。</div>
            <button class="sp-btn" style="margin-top:12px" :disabled="busy || my.todayCheckin?.done" @click="doCheckin">{{ my.todayCheckin?.done ? '今日已打卡' : '登记今日打卡' }}</button>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">考勤异常</div>
            <AutoTable :rows="my.attendanceExceptions" empty="暂无考勤异常" :columns="[{key:'type',label:'类型'},{key:'status',label:'状态'},{key:'date',label:'日期'}]" />
          </section>
        </div>
      </template>

      <!-- 实习请假 -->
      <template v-else-if="tab === 'leave'">
        <div class="two">
          <section class="sp-card">
            <div class="sp-panel__head">发起请假</div>
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
            <textarea v-model.trim="leaveForm.reason" class="sp-inp" style="margin-bottom:12px" placeholder="如：发热就医，已上传门诊证明" />
            <button class="sp-btn" :disabled="busy || !leaveForm.startDate || !leaveForm.endDate || !leaveForm.reason" @click="submitLeave">提交请假</button>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">我的请假</div>
            <StateBlock v-if="!(leaves||[]).length" type="empty" text="暂无请假记录" />
            <div v-else style="display:flex;flex-direction:column;gap:10px">
              <div v-for="lv in leaves" :key="lv.id" class="repitem" style="flex-direction:column;align-items:stretch;gap:6px">
                <div style="display:flex;align-items:center;justify-content:space-between;gap:8px">
                  <div>
                    <div style="font-size:13.5px;color:var(--t1)">{{ lv.leaveTypeLabel || lv.leaveType }} · {{ lv.startDate }} ~ {{ lv.endDate }}</div>
                    <div style="font-size:12px;color:var(--t4);margin-top:2px">{{ lv.reason }}</div>
                  </div>
                  <StatusTag :text="lv.statusLabel || lv.status" :tone="lv.status==='APPROVED'||lv.status==='RETURNED'?'success':lv.status==='REJECTED'?'danger':'warn'" />
                </div>
                <div style="display:flex;gap:8px">
                  <button v-if="lv.status==='PENDING'" class="sp-btn sp-btn--ghost" style="align-self:flex-start" :disabled="busy" @click="withdrawLeave(lv)">撤回</button>
                  <button v-if="lv.status==='APPROVED'" class="sp-btn sp-btn--ghost" style="align-self:flex-start" :disabled="busy" @click="returnLeave(lv.id)">办理销假</button>
                </div>
              </div>
            </div>
          </section>
        </div>
      </template>

      <!-- 补卡申请 -->
      <template v-else-if="tab === 'makeup'">
        <div class="two">
          <section class="sp-card">
            <div class="sp-panel__head">申请补卡</div>
            <div class="sp-fieldlabel">缺卡日期</div>
            <AppDatePicker v-model="makeupForm.checkinDate" class="sp-inp" style="margin-bottom:12px" label="缺卡日期" />
            <div class="sp-fieldlabel">事由</div>
            <textarea v-model.trim="makeupForm.reason" class="sp-inp" style="margin-bottom:12px" placeholder="说明缺卡原因（不少于2字）" />
            <button class="sp-btn" :disabled="busy || !makeupForm.checkinDate || !makeupForm.reason" @click="submitMakeup">提交补卡</button>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">我的补卡</div>
            <div v-if="!makeups.length" class="sp-muted">暂无补卡申请</div>
            <div v-else style="display:flex;flex-direction:column;gap:10px">
              <div v-for="m in makeups" :key="m.id" class="repitem" style="flex-direction:column;align-items:stretch;gap:6px">
                <div style="display:flex;justify-content:space-between;align-items:center">
                  <span>{{ m.checkinDate }} · {{ m.statusLabel || m.status }}</span>
                  <button v-if="m.status === 'PENDING'" class="sp-btn sp-btn--ghost" :disabled="busy" @click="withdrawMakeup(m)">撤回</button>
                </div>
                <div class="sp-muted" style="font-size:12px">{{ m.reason }}</div>
              </div>
            </div>
          </section>
        </div>
      </template>

      <!-- 岗位意向 -->
      <template v-else-if="tab === 'intention'">
        <section class="sp-card">
          <div class="sp-panel__head">岗位意向</div>
          <div class="sp-fieldlabel">意向城市</div>
          <input v-model.trim="intentionForm.preferredCity" class="sp-inp" style="margin-bottom:12px" :disabled="!intentionCanEdit" />
          <div class="sp-fieldlabel">意向行业</div>
          <input v-model.trim="intentionForm.preferredIndustry" class="sp-inp" style="margin-bottom:12px" :disabled="!intentionCanEdit" />
          <div class="sp-fieldlabel">补充说明</div>
          <textarea v-model.trim="intentionForm.intentionNote" class="sp-inp" style="margin-bottom:12px" :disabled="!intentionCanEdit" />
          <div style="display:flex;gap:10px;flex-wrap:wrap">
            <button v-if="intentionCanEdit" class="sp-btn sp-btn--ghost" :disabled="busy" @click="saveIntention">保存草稿</button>
            <button v-if="intentionCanSubmit" class="sp-btn" :disabled="busy" @click="submitIntention">提交意向</button>
            <button v-if="intentionCanWithdraw" class="sp-btn sp-btn--ghost" :disabled="busy" @click="withdrawIntention">撤回意向</button>
          </div>
          <p class="sp-muted" style="margin-top:10px">当前状态：{{ intentionMeta.statusLabel || intentionMeta.status || '未填写' }}（匹配只认已提交）</p>
        </section>
      </template>

      <!-- 正式申请 -->
      <template v-else-if="tab === 'application'">
        <div class="two">
          <section class="sp-card">
            <div class="sp-panel__head">提交正式申请</div>
            <div class="sp-fieldlabel">申请类型</div>
            <select v-model="appForm.applicationType" class="sp-inp" style="margin-bottom:12px">
              <option value="POSITION">校内岗位志愿</option>
              <option value="SELF_ARRANGED">自主实习</option>
            </select>
            <template v-if="appForm.applicationType === 'POSITION'">
              <div class="sp-fieldlabel">选择岗位</div>
              <select v-model="appForm.positionId" class="sp-inp" style="margin-bottom:12px">
                <option value="">请选择企业岗位</option>
                <option v-for="position in enterprises" :key="position.id" :value="String(position.id)">
                  {{ position.companyName }} · {{ position.title }} · {{ position.workLocation || '地点待定' }}
                </option>
              </select>
            </template>
            <template v-else>
              <div class="sp-fieldlabel">企业名称</div>
              <input v-model.trim="appForm.companyName" class="sp-inp" style="margin-bottom:12px" placeholder="不少于 2 字" />
              <div class="sp-fieldlabel">岗位名称</div>
              <input v-model.trim="appForm.positionName" class="sp-inp" style="margin-bottom:12px" placeholder="不少于 2 字" />
              <div class="sp-fieldlabel">工作地址</div>
              <input v-model.trim="appForm.workAddress" class="sp-inp" style="margin-bottom:12px" placeholder="不少于 5 字" />
              <div class="sp-fieldlabel">单位联系人</div>
              <input v-model.trim="appForm.contactName" class="sp-inp" style="margin-bottom:12px" />
              <div class="sp-fieldlabel">联系人电话</div>
              <input v-model.trim="appForm.contactPhone" class="sp-inp" style="margin-bottom:12px" placeholder="手机号" />
              <div class="sp-fieldlabel">自主实习证明材料</div>
              <input type="file" class="sp-inp" style="margin-bottom:6px" :disabled="busy" @change="uploadApplicationEvidence" />
              <p class="sp-muted" style="margin-bottom:12px">{{ appForm.evidenceFileId ? '材料已上传' : '请上传盖章证明或接收函' }}</p>
            </template>
            <div class="sp-fieldlabel">申请说明</div>
            <textarea v-model.trim="appForm.applicationNote" class="sp-inp" style="margin-bottom:12px" placeholder="不少于 5 字" />
            <button class="sp-btn" :disabled="busy || !appForm.applicationNote || appForm.applicationNote.length < 5" @click="submitApplication">保存并提交</button>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">我的申请</div>
            <AutoTable :rows="applications" empty="暂无申请" :columns="[{key:'applicationTypeLabel',label:'类型'},{key:'statusLabel',label:'状态'},{key:'applicationNote',label:'说明'}]" />
          </section>
        </div>
      </template>

      <!-- 调岗退岗 -->
      <template v-else-if="tab === 'change'">
        <div class="two">
          <section class="sp-card">
            <div class="sp-panel__head">发起变更</div>
            <div class="sp-fieldlabel">变更类型</div>
            <select v-model="changeForm.changeType" class="sp-inp" style="margin-bottom:12px">
              <option value="CHANGE_POSITION">换岗</option>
              <option value="CHANGE_ENTERPRISE">换实习单位</option>
              <option value="SELF_ARRANGED">转自主实习</option>
              <option value="WITHDRAW_POST">退岗</option>
            </select>
            <template v-if="changeForm.changeType === 'CHANGE_POSITION'">
              <div class="sp-fieldlabel">目标岗位（必选）</div>
              <select v-model="changeForm.targetPositionId" class="sp-inp" style="margin-bottom:12px">
                <option value="">请选择目标岗位</option>
                <option v-for="position in enterprises" :key="position.id" :value="String(position.id)">
                  {{ position.companyName }} · {{ position.title }} · {{ position.workLocation || '地点待定' }}
                </option>
              </select>
            </template>
            <template v-if="changeForm.changeType === 'CHANGE_ENTERPRISE' || changeForm.changeType === 'SELF_ARRANGED'">
              <div class="sp-fieldlabel">目标企业名称</div>
              <input v-model.trim="changeForm.targetEnterpriseName" class="sp-inp" style="margin-bottom:12px" />
              <div class="sp-fieldlabel">目标岗位名称</div>
              <input v-model.trim="changeForm.targetPositionName" class="sp-inp" style="margin-bottom:12px" />
            </template>
            <div class="sp-fieldlabel">事由（不少于 5 字）</div>
            <textarea v-model.trim="changeForm.reason" class="sp-inp" style="margin-bottom:12px" />
            <button class="sp-btn" :disabled="busy || !changeForm.reason || changeForm.reason.length < 5" @click="submitChange">提交变更</button>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">我的变更</div>
            <AutoTable :rows="changes" empty="暂无变更申请" :columns="[{key:'changeTypeLabel',label:'类型'},{key:'statusLabel',label:'状态'},{key:'reason',label:'事由'}]" />
          </section>
        </div>
      </template>

      <!-- 企业岗位库 -->
      <template v-else-if="tab === 'enterprises'">
        <section class="sp-card">
          <div class="sp-panel__head">企业岗位库</div>
          <div style="display:flex;gap:10px;margin-bottom:12px">
            <input v-model.trim="enterpriseCity" class="sp-inp" placeholder="按城市筛选（可选）" />
            <button class="sp-btn" :disabled="busy" @click="loadEnterprises">查询</button>
          </div>
          <AutoTable :rows="enterprises" empty="暂无已发布岗位" :columns="[{key:'companyName',label:'企业'},{key:'title',label:'岗位'},{key:'workLocation',label:'地点'},{key:'remaining',label:'余量'}]" />
        </section>
      </template>

      <!-- 实习保险 -->
      <template v-else-if="tab === 'insurance'">
        <div class="two">
          <section class="sp-card">
            <div class="sp-panel__head">提交保险信息</div>
            <div class="sp-fieldlabel">保单号</div>
            <input v-model.trim="insForm.policyNo" class="sp-inp" style="margin-bottom:12px" />
            <div class="sp-fieldlabel">承保机构</div>
            <input v-model.trim="insForm.insurerName" class="sp-inp" style="margin-bottom:12px" />
            <div class="sp-fieldlabel">险种</div>
            <input v-model.trim="insForm.coverageType" class="sp-inp" style="margin-bottom:12px" />
            <div class="sp-fieldlabel">生效日</div>
            <AppDatePicker v-model="insForm.effectiveDate" class="sp-inp" style="margin-bottom:12px" role="start" :end-value="insForm.expiryDate" label="生效日期" />
            <div class="sp-fieldlabel">失效日</div>
            <AppDatePicker v-model="insForm.expiryDate" class="sp-inp" style="margin-bottom:12px" role="end" :start-value="insForm.effectiveDate" label="到期日期" />
            <div class="sp-fieldlabel">保单扫描件</div>
            <input type="file" class="sp-inp" style="margin-bottom:6px" :disabled="busy" @change="uploadInsurancePolicy" />
            <p class="sp-muted" style="margin-bottom:12px">{{ insForm.fileId ? '保单文件已上传' : '请上传保单扫描件' }}</p>
            <button class="sp-btn" :disabled="busy" @click="saveInsurance">提交保险</button>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">当前保险</div>
            <p class="sp-muted">状态：{{ insuranceMeta?.statusLabel || insuranceMeta?.status || '未提交' }}</p>
            <p v-if="insuranceMeta?.policyNo" class="sp-muted">保单号：{{ insuranceMeta.policyNo }} · {{ insuranceMeta.insurerName }}</p>
          </section>
        </div>
      </template>

      <!-- 实习计划 -->
      <template v-else-if="tab === 'plan'">
        <section class="sp-card">
          <div class="sp-panel__head">实习计划书</div>
          <template v-if="planMeta && (planMeta.title || planMeta.planTitle || planMeta.id)">
            <p style="font-size:15px;font-weight:600">{{ planMeta.title || planMeta.planTitle || '实习计划' }}</p>
            <p class="sp-muted" style="margin-top:8px">状态：{{ planMeta.statusLabel || planMeta.status || '—' }}</p>
            <p v-if="planMeta.content || planMeta.summary" class="sp-muted" style="margin-top:10px;white-space:pre-wrap">{{ planMeta.content || planMeta.summary }}</p>
            <button v-if="planMeta.canAcknowledge !== false && planMeta.status !== 'ACKNOWLEDGED'" class="sp-btn" style="margin-top:12px" :disabled="busy" @click="ackPlan">确认计划</button>
          </template>
          <p v-else class="sp-muted">暂无已发布计划</p>
        </section>
      </template>

      <!-- 实习求助 -->
      <template v-else-if="tab === 'help'">
        <section class="sp-card">
          <div class="sp-panel__head">向指导教师求助</div>
          <p class="sp-muted" style="margin-bottom:12px">用于岗位不适、安全隐患等。进入实习风险台由导师跟进；不登记就业去向，也不伪造监管上报。</p>
          <div class="sp-fieldlabel">紧急程度</div>
          <select v-model="helpForm.riskLevel" class="sp-inp" style="margin-bottom:12px">
            <option value="LOW">一般</option>
            <option value="MEDIUM">较急</option>
            <option value="HIGH">紧急</option>
          </select>
          <div class="sp-fieldlabel">标题（可选）</div>
          <input v-model.trim="helpForm.title" class="sp-inp" style="margin-bottom:12px" placeholder="默认：学生实习求助" />
          <div class="sp-fieldlabel">情况说明</div>
          <textarea v-model.trim="helpForm.content" class="sp-inp" style="margin-bottom:12px" placeholder="不少于 5 字" />
          <button class="sp-btn" :disabled="busy || (helpForm.content || '').length < 5" @click="submitHelp">提交求助</button>
        </section>
      </template>

      <!-- 周报/月报/总结 -->
      <template v-else-if="tab === 'report'">
        <div style="display:flex;gap:8px;margin-bottom:16px">
          <button v-for="r in reportTabs" :key="r" class="sp-tab" :class="{'is-active':reportTab===r}" @click="reportTab=r">{{ r }}</button>
        </div>
        <div class="two">
          <section class="sp-card">
            <div class="sp-panel__head">{{ reportTab }}编辑</div>
            <template v-if="reportTab==='周报'">
              <div class="sp-fieldlabel">周次</div><input v-model.number="weeklyForm.week" type="number" min="1" class="sp-inp" style="margin-bottom:12px" placeholder="第几周" />
              <div class="sp-fieldlabel">本周工作内容</div><textarea v-model.trim="weeklyForm.workContent" class="sp-inp" style="margin-bottom:12px" placeholder="本周主要完成的工作" />
              <div class="sp-fieldlabel">收获与体会</div><textarea v-model.trim="weeklyForm.harvestContent" class="sp-inp" style="margin-bottom:12px" placeholder="本周收获" />
              <div class="sp-fieldlabel">下周计划</div><textarea v-model.trim="weeklyForm.planContent" class="sp-inp" style="margin-bottom:12px" placeholder="下周安排" />
              <button class="sp-btn" :disabled="busy || !weeklyForm.workContent" @click="submitWeekly">提交周报</button>
            </template>
            <template v-else>
              <div class="sp-fieldlabel">报告标题</div><input v-model.trim="reportForm.title" class="sp-inp" style="margin-bottom:12px" :placeholder="reportTab + '标题'" />
              <div class="sp-fieldlabel">正文（长文档）</div><textarea v-model.trim="reportForm.content" class="sp-inp" style="min-height:200px;margin-bottom:12px" :placeholder="reportTab + '正文'" />
              <button class="sp-btn" :disabled="busy || !reportForm.content" @click="submitReport">提交{{ reportTab }}</button>
            </template>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">{{ reportTab === '周报' ? '周报记录' : '月报/总结记录' }}</div>
            <template v-if="reportTab === '周报'">
              <StateBlock v-if="!(my.weeklyReports||[]).length" type="empty" text="暂无周报" />
              <div v-else style="display:flex;flex-direction:column;gap:10px">
                <div v-for="w in my.weeklyReports" :key="w.week" class="repitem" style="flex-direction:column;align-items:stretch;gap:4px">
                  <div style="display:flex;align-items:center;justify-content:space-between">
                    <div style="flex:1"><div style="font-size:13.5px;color:var(--t1)">第 {{ w.week }} 周周报</div><div style="font-size:12px;color:var(--t4);margin-top:2px">{{ fmt(w.submittedAt) }}</div></div>
                    <StatusTag :text="reviewText(w.status)" :tone="w.status==='APPROVED'?'success':w.status==='REJECTED'?'danger':'warn'" />
                  </div>
                  <div v-if="w.reviewComment" class="sp-muted" style="font-size:12px">老师意见：{{ w.reviewComment }}</div>
                </div>
              </div>
            </template>
            <template v-else>
              <StateBlock v-if="!(my.processReports||[]).length" type="empty" text="暂无月报/总结记录" />
              <div v-else style="display:flex;flex-direction:column;gap:10px">
                <div v-for="p in my.processReports" :key="p.id" class="repitem" style="flex-direction:column;align-items:stretch;gap:4px">
                  <div style="display:flex;align-items:center;justify-content:space-between">
                    <div style="flex:1"><div style="font-size:13.5px;color:var(--t1)">{{ p.periodKey }}（{{ p.reportType === 'MONTHLY' ? '月报' : '实习总结' }}）</div><div style="font-size:12px;color:var(--t4);margin-top:2px">{{ fmt(p.submittedAt) }}</div></div>
                    <StatusTag :text="reviewText(p.status)" :tone="p.status==='APPROVED'?'success':p.status==='RETURNED'?'danger':'warn'" />
                  </div>
                  <div v-if="p.reviewComment" class="sp-muted" style="font-size:12px">老师意见：{{ p.reviewComment }}</div>
                </div>
              </div>
            </template>
          </section>
        </div>
      </template>

      <!-- 实习成绩/自评 -->
      <template v-else-if="tab === 'eval'">
        <div v-if="evalReceipt" class="eval-receipt" role="status">
          <strong>✓ {{ evalReceipt.actionLabel }}</strong>
          <span>#{{ evalReceipt.id }} · v{{ evalReceipt.version }} · {{ evalReceipt.statusLabel }}</span>
          <span>{{ evalReceipt.nextStep }}</span>
          <button type="button" @click="evalReceipt = null">关闭</button>
        </div>
        <div class="two">
          <section class="sp-card">
            <div class="sp-panel__head">实习自评 / 鉴定</div>
            <div class="sp-fieldlabel">工作表现自评</div><textarea v-model.trim="evalForm.performance" class="sp-inp" style="margin-bottom:12px" placeholder="请描述实习期间的工作表现" />
            <div class="sp-fieldlabel">收获与反思</div><textarea v-model.trim="evalForm.reflection" class="sp-inp" style="margin-bottom:12px" placeholder="请描述实习收获与不足" />
            <div class="sp-fieldlabel">存在问题</div><textarea v-model.trim="evalForm.problems" class="sp-inp" style="margin-bottom:12px" placeholder="实习中遇到的问题与改进方向" />
            <div class="score-grid" style="margin-bottom:12px">
              <label><span class="sp-fieldlabel">对企业评分</span><select v-model.number="evalForm.enterpriseRating" class="sp-inp"><option :value="null">请选择</option><option v-for="n in 5" :key="'e'+n" :value="n">{{ n }} 分</option></select></label>
              <label><span class="sp-fieldlabel">对岗位评分</span><select v-model.number="evalForm.positionRating" class="sp-inp"><option :value="null">请选择</option><option v-for="n in 5" :key="'p'+n" :value="n">{{ n }} 分</option></select></label>
            </div>
            <div class="sp-fieldlabel">对企业评价</div><textarea v-model.trim="evalForm.enterpriseFeedback" class="sp-inp" style="margin-bottom:12px" placeholder="可填写企业管理、培养和保障体验" />
            <div class="sp-fieldlabel">对岗位评价</div><textarea v-model.trim="evalForm.positionFeedback" class="sp-inp" style="margin-bottom:12px" placeholder="可填写岗位内容与专业匹配体验" />
            <button class="sp-btn" :disabled="busy || !evalForm.performance" @click="submitSelfEval">提交自评</button>
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
              最近申诉：{{ appealMeta.statusLabel || appealMeta.status }}
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
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import AutoTable from '../../components/AutoTable.vue'
import AppDatePicker from '../../components/AppDatePicker.vue'
import FlowSteps from '../../components/FlowSteps.vue'
import { portalApi } from '../../services/portalApi'
import { internshipCoreApi } from '../../services/internshipCoreApi'
import { usePortalConfigStore } from '../../stores/portalConfig'
import { useSessionStore } from '../../stores/session'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const cfg = usePortalConfigStore()
const session = useSessionStore()
const route = useRoute()
const router = useRouter()
const tabs = [
  { key: 'overview', label: '我的实习' }, { key: 'agreement', label: '三方协议' },
  { key: 'checkin', label: '每日打卡' }, { key: 'leave', label: '实习请假' },
  { key: 'makeup', label: '补卡申请' }, { key: 'intention', label: '岗位意向' },
  { key: 'application', label: '正式申请' }, { key: 'change', label: '调岗退岗' },
  { key: 'enterprises', label: '企业岗位库' }, { key: 'insurance', label: '实习保险' },
  { key: 'plan', label: '实习计划' }, { key: 'help', label: '实习求助' },
  { key: 'report', label: '周报/月报/总结' }, { key: 'eval', label: '实习成绩/自评' }
]
const tab = ref('overview')
const tabGroups = [
  { key: 'onboard', label: '安排与入岗', hint: '确认实习安排与上岗前条件', tabs: tabs.filter((item) => ['overview', 'plan', 'insurance', 'agreement'].includes(item.key)) },
  { key: 'selection', label: '选岗与申请', hint: '查岗位、填意向、提交正式申请', tabs: tabs.filter((item) => ['enterprises', 'intention', 'application'].includes(item.key)) },
  { key: 'process', label: '在岗办理', hint: '打卡、补卡、请假与过程报告', tabs: tabs.filter((item) => ['checkin', 'makeup', 'leave', 'report'].includes(item.key)) },
  { key: 'change-result', label: '变更与结果', hint: '调岗退岗、求助、评价与成绩', tabs: tabs.filter((item) => ['change', 'help', 'eval'].includes(item.key)) }
]
const reportTab = ref('周报')
const reportTabs = ['周报', '月报', '实习总结']
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const my = ref({})
const sourceStates = reactive(Object.fromEntries(tabs.map((item) => [item.key, {
  label: item.label, status: 'idle', message: '',
}])))
const currentSource = computed(() => sourceStates[tab.value] || { label: '当前内容', status: 'idle', message: '' })
const INTERNSHIP_BATCH_KEY = 'student_portal_internship_batch_v1'
const selectedBatchId = ref('')
const internshipCandidates = ref([])
const weeklyForm = reactive({ week: null, workContent: '', harvestContent: '', planContent: '' })
const reportForm = reactive({ title: '', content: '' })
const evalForm = reactive({ performance: '', reflection: '', problems: '', enterpriseRating: null,
  enterpriseFeedback: '', positionRating: null, positionFeedback: '' })
const leaveForm = reactive({ leaveType: 'SICK', startDate: '', endDate: '', reason: '' })
const leaves = ref([])
const makeupForm = reactive({ checkinDate: '', reason: '' })
const makeups = ref([])
const intentionForm = reactive({ preferredCity: '', preferredIndustry: '', intentionNote: '' })
const intentionMeta = ref({})
const intentionFlags = ref({ canEdit: true, canSubmit: false, canWithdraw: false })
const appForm = reactive({
  applicationType: 'SELF_ARRANGED', positionId: '', applicationNote: '',
  companyName: '', positionName: '', workAddress: '', contactName: '', contactPhone: '', evidenceFileId: ''
})
const applications = ref([])
const changeForm = reactive({
  changeType: 'CHANGE_POSITION', reason: '', targetPositionId: '',
  targetEnterpriseName: '', targetPositionName: ''
})
const changes = ref([])
const agreements = ref([])
const activeAgreement = ref(null)
const enterpriseCity = ref('')
const enterprises = ref([])
const insForm = reactive({
  policyNo: '', insurerName: '', coverageType: '', effectiveDate: '', expiryDate: '', fileId: ''
})
const insuranceMeta = ref(null)
const planMeta = ref(null)
const helpForm = reactive({ title: '', content: '', riskLevel: 'MEDIUM' })
const appealReason = ref('')
const appealMeta = ref(null)
const selfEvalMeta = ref(null)
const evalReceipt = ref(null)

const brandSchool = computed(() => cfg.brand?.schoolName || '学校')
const studentName = computed(() => session.user?.realName || '同学')
const STATUS_MAP = { ONBOARD: '实习中', PENDING: '待入职', ENDED: '已结束', PAUSED: '暂停', READY: '待上岗', PREPARING: '准备中', ASSESSING: '考核中', ARCHIVED: '已归档' }
const RISK_MAP = { NONE: '无', LOW: '低', MEDIUM: '中', HIGH: '高', MID: '中' }
const REVIEW_MAP = { PENDING_REVIEW: '待审阅', APPROVED: '已通过', REJECTED: '已退回', RETURNED: '已退回' }
const AGREEMENT_MAP = {
  DRAFT: '草稿', PENDING_STUDENT: '待学生确认', PENDING_ENTERPRISE: '待企业确认',
  PENDING_SCHOOL: '待学校确认', EFFECTIVE: '已生效', REJECTED: '已驳回', VOIDED: '已作废', ARCHIVED: '已归档'
}
function statusText(s) { return STATUS_MAP[s] || s || '—' }
function riskText(s) { return RISK_MAP[s] || s || '—' }
function reviewText(s) { return REVIEW_MAP[s] || s || '—' }
function fmt(t) { return t ? String(t).replace('T', ' ').slice(0, 16) : '—' }
const agreementStatusText = computed(() => AGREEMENT_MAP[my.value.agreementStatus] || my.value.agreementStatusLabel || my.value.agreementStatus || activeAgreement.value?.statusLabel || '未发起')
const agreementTone = computed(() => ((my.value.agreementStatus || activeAgreement.value?.status) === 'EFFECTIVE' ? 'success' : 'warn'))
const intentionCanEdit = computed(() => intentionFlags.value.canEdit !== false && (intentionMeta.value.status || 'DRAFT') !== 'SUBMITTED')
const intentionCanSubmit = computed(() => intentionFlags.value.canSubmit || ['DRAFT', '', undefined, null].includes(intentionMeta.value.status))
const intentionCanWithdraw = computed(() => intentionFlags.value.canWithdraw || intentionMeta.value.status === 'SUBMITTED')

const currentAction = computed(() => {
  const agreementStatus = my.value.agreementStatus || activeAgreement.value?.status
  if (agreementStatus === 'PENDING_STUDENT') return {
    tab: 'agreement', title: '确认三方协议', action: '核对并确认',
    reason: '协议正在等待你确认。请先核对学校、企业、岗位和纸质签署来源，再决定确认或驳回。',
    recentChange: activeAgreement.value?.updatedAt ? fmt(activeAgreement.value.updatedAt) : '协议已进入学生确认节点',
    nextActor: '确认后交由企业或学校继续办理；驳回则返回经办人修正'
  }
  if (sourceStates.insurance.status === 'empty' && ['PREPARING', 'READY'].includes(my.value.status)) return {
    tab: 'insurance', title: '补齐实习保险', action: '提交保险信息',
    reason: '当前实习记录还没有可核验的保险信息，上岗前需要补齐保单与有效期。',
    recentChange: '尚未取得有效保险记录', nextActor: '提交后等待学校核验'
  }
  if (sourceStates.plan.status === 'data' && planMeta.value && !['ACKNOWLEDGED', 'CONFIRMED'].includes(planMeta.value.ackStatus || planMeta.value.status)) return {
    tab: 'plan', title: '确认实习计划', action: '查看计划',
    reason: '学校已下发实习计划，确认前请阅读任务、时间和指导要求。',
    recentChange: planMeta.value.updatedAt ? fmt(planMeta.value.updatedAt) : '计划已下发',
    nextActor: '确认后进入在岗执行与过程记录'
  }
  if (my.value.status === 'ONBOARD' && !my.value.todayCheckin?.done) return {
    tab: 'checkin', title: '完成今日打卡', action: '去打卡',
    reason: '今天尚未留下出勤记录。PC 可登记打卡，精确地理围栏核验仍在学生小程序完成。',
    recentChange: `累计出勤 ${my.value.todayCheckin?.totalDays ?? 0} 天`,
    nextActor: '打卡后形成服务端时间记录；异常只作为人工核实信号'
  }
  if (my.value.status === 'ASSESSING') return {
    tab: 'eval', title: '完成实习自评', action: '填写自评',
    reason: '实习已进入考核评价阶段，请核对成绩构成并完成本人自评。',
    recentChange: '实习状态已进入考核中', nextActor: '提交后等待指导教师与学校审核'
  }
  if (!my.value.enterpriseName || !my.value.positionName) return {
    tab: 'enterprises', title: '选择合适岗位', action: '查看岗位',
    reason: '当前记录还没有已确认的企业岗位，可先查看已发布岗位，再填写意向或申请。',
    recentChange: '岗位尚未落实', nextActor: '提交申请后进入学校与企业审核'
  }
  return {
    tab: 'report', title: '继续记录实习过程', action: '写周报 / 总结',
    reason: '岗位与上岗条件已建立，下一步是持续提交周报、月报和实习总结。',
    recentChange: `已提交 ${(my.value.weeklyReports || []).length} 篇周报`,
    nextActor: '提交后等待指导教师批阅；退回后按原因修订重交'
  }
})

function activeGroupLabel(group) {
  return group.tabs.find((item) => item.key === tab.value)?.label || `${group.tabs.length} 项`
}

function groupOpen(group) {
  return group.tabs.some((item) => item.key === tab.value)
}

function selectTab(key) {
  if (!tabs.some((item) => item.key === key)) return
  if (key === 'enterprises') {
    router.push('/internship/selection')
    return
  }
  tab.value = key
  router.replace({ query: { ...route.query, view: key } })
  if (my.value.hasData) loadTab(key)
}

watch(() => route.query.view, (value) => {
  if (typeof value === 'string' && tabs.some((item) => item.key === value)) {
    tab.value = value
    if (my.value.hasData) loadTab(value)
  }
}, { immediate: true })

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
  await load()
}

async function changeInternshipBatch() {
  persistInternshipBatch(selectedBatchId.value)
  await load()
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
  const order = ['协议签署', '岗前培训', '在岗实习', '考核评价', '归档']
  const cur = my.value.status === 'ENDED' ? 4 : 2
  return order.map((name, i) => ({ name, state: i < cur ? 'done' : i === cur ? 'current' : 'todo' }))
})
const metrics = computed(() => [
  { t: '累计出勤', v: my.value.todayCheckin?.totalDays ?? 0, u: '天', c: 'var(--t1)' },
  { t: '周报数', v: (my.value.weeklyReports || []).length, u: '篇', c: 'var(--t1)' },
  { t: '考勤异常', v: (my.value.attendanceExceptions || []).length, u: '次', c: (my.value.attendanceExceptions || []).length ? 'var(--warn-fg)' : 'var(--ok-fg)' },
  { t: '风险等级', v: riskText(my.value.riskLevel), u: '', c: my.value.riskLevel === 'HIGH' ? 'var(--danger-fg)' : 'var(--ok-fg)' }
])

function resetSourceStates() {
  Object.values(sourceStates).forEach((state) => Object.assign(state, { status: 'idle', message: '' }))
  leaves.value = []
  makeups.value = []
  intentionMeta.value = {}
  intentionFlags.value = { canEdit: true, canSubmit: false, canWithdraw: false }
  applications.value = []
  changes.value = []
  agreements.value = []
  activeAgreement.value = null
  enterprises.value = []
  insuranceMeta.value = null
  planMeta.value = null
  selfEvalMeta.value = null
  appealMeta.value = null
}

function rowsFrom(data) {
  return data?.items || data?.list || (Array.isArray(data) ? data : [])
}

async function fetchTabSource(key) {
  const context = () => currentInternshipContext()
  if (['overview', 'checkin', 'help'].includes(key)) return true
  if (key === 'leave') {
    leaves.value = rowsFrom(await internshipCoreApi.leaves(context()))
    return leaves.value.length > 0
  }
  if (key === 'makeup') {
    makeups.value = rowsFrom(await internshipCoreApi.makeups(context()))
    return makeups.value.length > 0
  }
  if (key === 'intention') {
    const data = await portalApi.internshipIntentionMy()
    intentionFlags.value = {
      canEdit: data?.canEdit !== false,
      canSubmit: !!data?.canSubmit,
      canWithdraw: !!data?.canWithdraw,
    }
    intentionMeta.value = data?.intention || data || {}
    intentionForm.preferredCity = intentionMeta.value.preferredCity || ''
    intentionForm.preferredIndustry = intentionMeta.value.preferredIndustry || ''
    intentionForm.intentionNote = intentionMeta.value.intentionNote || ''
    return Object.keys(intentionMeta.value).length > 0
  }
  if (key === 'application') {
    applications.value = rowsFrom(await internshipCoreApi.applications(context()))
    return applications.value.length > 0
  }
  if (key === 'change') {
    const [changeRows, positionRows] = await Promise.all([
      internshipCoreApi.changes(context()),
      portalApi.internshipEnterprises(enterpriseCity.value),
    ])
    changes.value = rowsFrom(changeRows)
    enterprises.value = rowsFrom(positionRows)
    return changes.value.length > 0 || enterprises.value.length > 0
  }
  if (key === 'report') {
    const [weekly, reports] = await Promise.all([
      internshipCoreApi.weeklyReports(context()),
      internshipCoreApi.reports(context()),
    ])
    my.value.weeklyReports = rowsFrom(weekly)
    my.value.processReports = rowsFrom(reports)
    return my.value.weeklyReports.length > 0 || my.value.processReports.length > 0
  }
  if (key === 'agreement') {
    agreements.value = rowsFrom(await internshipCoreApi.agreements())
    activeAgreement.value = agreements.value.find((item) => item.status === 'PENDING_STUDENT') || agreements.value[0] || null
    return agreements.value.length > 0
  }
  if (key === 'insurance') {
    insuranceMeta.value = await internshipCoreApi.insurance()
    if (!insuranceMeta.value) return false
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
    planMeta.value = await internshipCoreApi.plan()
    return !!planMeta.value
  }
  if (key === 'eval') {
    const [selfEval, appeal] = await Promise.all([
      internshipCoreApi.selfEval(),
      portalApi.internshipScoreAppealStatus(context()),
    ])
    selfEvalMeta.value = selfEval || null
    appealMeta.value = appeal || null
    return !!selfEvalMeta.value || !!appealMeta.value || !!my.value.score
  }
  if (key === 'enterprises') {
    enterprises.value = rowsFrom(await portalApi.internshipEnterprises(enterpriseCity.value))
    return enterprises.value.length > 0
  }
  return true
}

async function loadTab(key, force = false) {
  const state = sourceStates[key]
  if (!state || !my.value.hasData) return
  if (!force && ['loading', 'data', 'empty'].includes(state.status)) return
  state.status = 'loading'
  state.message = ''
  try {
    state.status = await fetchTabSource(key) ? 'data' : 'empty'
  } catch (e) {
    state.status = 'error'
    state.message = e?.message || `${state.label}加载失败，请重试`
  }
}

async function retryCurrentSource() {
  await loadTab(tab.value, true)
}

async function loadEnterprises() {
  await loadTab('enterprises', true)
}

async function load() {
  loading.value = true; error.value = ''
  resetSourceStates()
  try {
    try { selectedBatchId.value = String(sessionStorage.getItem(INTERNSHIP_BATCH_KEY) || '') } catch { selectedBatchId.value = '' }
    const data = await portalApi.internshipMy() || {}
    my.value = data
    if (Array.isArray(data.candidates) && data.candidates.length) internshipCandidates.value = data.candidates
    if (data.needSelect) {
      persistInternshipBatch('')
      return
    }
    if (data.batchId) persistInternshipBatch(data.batchId)
    if (!data.hasData) return
    const initialSources = [...new Set(['agreement', 'insurance', 'plan', tab.value])]
    await Promise.all(initialSources.map((key) => loadTab(key, true)))
  } catch (e) { error.value = e?.message || '实习信息加载失败' } finally { loading.value = false }
}
async function doCheckin() {
  if (busy.value) return
  busy.value = true
  try {
    await portalApi.internshipCheckin({
      source: 'PORTAL', note: '学生PC门户登记打卡',
      idempotencyKey: `portal-checkin-${new Date().toISOString().slice(0, 10)}`
    })
    ui.notify('打卡已记录')
    await load()
  } catch (e) { ui.notify(e?.message || '打卡失败') } finally { busy.value = false }
}
async function submitMakeup() {
  busy.value = true
  try {
    await internshipCoreApi.applyMakeup({
      ...makeupForm,
      ...currentInternshipContext()
    })
    ui.notify('补卡申请已提交')
    makeupForm.reason = ''
    await loadTab('makeup', true)
  } catch (e) { ui.notify(e?.message || '补卡失败') } finally { busy.value = false }
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
async function saveIntention() {
  busy.value = true
  try {
    await portalApi.internshipIntentionSave({ ...intentionForm })
    ui.notify('意向草稿已保存'); await loadTab('intention', true)
  } catch (e) { ui.notify(e?.message || '意向保存失败') } finally { busy.value = false }
}
async function submitIntention() {
  busy.value = true
  try {
    await portalApi.internshipIntentionSave({ ...intentionForm })
    await portalApi.internshipIntentionSubmit()
    ui.notify('意向已提交'); await loadTab('intention', true)
  } catch (e) { ui.notify(e?.message || '意向提交失败') } finally { busy.value = false }
}
async function withdrawIntention() {
  busy.value = true
  try {
    await portalApi.internshipIntentionWithdraw()
    ui.notify('意向已撤回'); await loadTab('intention', true)
  } catch (e) { ui.notify(e?.message || '撤回失败') } finally { busy.value = false }
}
async function uploadApplicationEvidence(event) {
  const file = event?.target?.files?.[0]
  if (!file) return
  busy.value = true
  try {
    const uploaded = await internshipCoreApi.uploadApplicationEvidence(file)
    appForm.evidenceFileId = uploaded?.fileId || uploaded?.id || ''
    if (!appForm.evidenceFileId) throw new Error('上传响应缺少文件标识')
    ui.notify('证明材料已上传')
  } catch (e) {
    appForm.evidenceFileId = ''
    ui.notify(e?.message || '证明材料上传失败')
  } finally {
    busy.value = false
    if (event?.target) event.target.value = ''
  }
}
async function submitApplication() {
  if (appForm.applicationType === 'POSITION' && !appForm.positionId) {
    return ui.notify('请选择拟申请岗位')
  }
  if (appForm.applicationType === 'SELF_ARRANGED') {
    if ((appForm.companyName || '').trim().length < 2) return ui.notify('请填写企业名称')
    if ((appForm.positionName || '').trim().length < 2) return ui.notify('请填写岗位名称')
    if ((appForm.workAddress || '').trim().length < 5) return ui.notify('请填写工作地址')
    if ((appForm.contactName || '').trim().length < 2) return ui.notify('请填写联系人')
    if (!(appForm.contactPhone || '').trim()) return ui.notify('请填写联系电话')
    if (!(appForm.evidenceFileId || '').trim()) return ui.notify('请先上传证明材料')
  }
  if ((appForm.applicationNote || '').trim().length < 5) {
    return ui.notify('申请说明不少于 5 字')
  }
  busy.value = true
  try {
    const body = {
      ...currentInternshipContext(),
      applicationType: appForm.applicationType,
      applicationNote: appForm.applicationNote,
      positionId: appForm.applicationType === 'POSITION' ? appForm.positionId : undefined,
      companyName: appForm.companyName,
      positionName: appForm.positionName,
      workAddress: appForm.workAddress,
      contactName: appForm.contactName,
      contactPhone: appForm.contactPhone,
      evidenceFileId: appForm.evidenceFileId
    }
    const saved = await internshipCoreApi.saveApplication(body)
    await internshipCoreApi.submitApplication(saved.id, {
      ...currentInternshipContext(),
      expectedVersion: saved.version
    })
    ui.notify('申请已提交'); appForm.applicationNote = ''; await loadTab('application', true)
  } catch (e) { ui.notify(e?.message || '申请失败') } finally { busy.value = false }
}
async function submitChange() {
  if ((changeForm.reason || '').trim().length < 5) {
    return ui.notify('变更事由不少于 5 字')
  }
  if (changeForm.changeType === 'CHANGE_POSITION' && !(changeForm.targetPositionId || '').trim()) {
    return ui.notify('换岗须填写目标岗位编号')
  }
  busy.value = true
  try {
    const context = currentInternshipContext()
    const selected = enterprises.value.find(
      (item) => String(item.id) === String(changeForm.targetPositionId)
    )
    await internshipCoreApi.applyChange({
      ...changeForm,
      ...context,
      expectedVersion: 0,
      targetEnterpriseId: selected?.companyId || undefined,
      targetEnterpriseName: selected?.companyName || changeForm.targetEnterpriseName,
      targetPositionName: selected?.title || changeForm.targetPositionName
    })
    ui.notify('变更申请已提交'); changeForm.reason = ''; await loadTab('change', true)
  } catch (e) { ui.notify(e?.message || '变更申请失败') } finally { busy.value = false }
}
async function submitLeave() {
  busy.value = true
  try {
    await internshipCoreApi.applyLeave({
      ...leaveForm,
      ...currentInternshipContext()
    })
    ui.notify('请假申请已提交')
    Object.assign(leaveForm, { reason: '' })
    await loadTab('leave', true)
  } catch (e) { ui.notify(e?.message || '请假提交失败') } finally { busy.value = false }
}
async function withdrawLeave(item) {
  busy.value = true
  try {
    await internshipCoreApi.withdrawLeave(item.id, {
      ...currentInternshipContext(),
      expectedVersion: item.version
    })
    ui.notify('已撤回'); await loadTab('leave', true)
  } catch (e) { ui.notify(e?.message || '撤回失败') } finally { busy.value = false }
}
async function returnLeave(id) {
  const note = (window.prompt('请填写销假说明（至少 2 字，如：已返岗）') || '').trim()
  if (note.length < 2) return ui.notify('销假说明至少 2 字')
  busy.value = true
  try {
    const item = leaves.value.find((row) => String(row.id) === String(id))
    await internshipCoreApi.returnLeave(id, {
      ...currentInternshipContext(),
      note,
      expectedVersion: item?.version
    })
    ui.notify('销假已登记'); await loadTab('leave', true)
  } catch (e) { ui.notify(e?.message || '销假失败') } finally { busy.value = false }
}
async function confirmAgreement(action) {
  if (!activeAgreement.value?.id) return ui.notify('暂无可操作协议')
  busy.value = true
  try {
    const reason = action === 'REJECT' ? (window.prompt('请填写驳回原因') || '') : ''
    if (action === 'REJECT' && reason.trim().length < 5) {
      busy.value = false
      return ui.notify('驳回原因不少于 5 字')
    }
    const detail = await internshipCoreApi.agreement(activeAgreement.value.id)
    await internshipCoreApi.confirmAgreement(activeAgreement.value.id, {
      ...currentInternshipContext(),
      action,
      reason,
      expectedVersion: detail.version
    })
    ui.notify(action === 'CONFIRM' ? '协议已确认' : '协议已驳回')
    await load()
  } catch (e) { ui.notify(e?.message || '协议操作失败') } finally { busy.value = false }
}
async function uploadInsurancePolicy(event) {
  const file = event?.target?.files?.[0]
  if (!file) return
  busy.value = true
  try {
    const uploaded = await internshipCoreApi.uploadInsurancePolicy(file)
    insForm.fileId = uploaded?.fileId || uploaded?.id || ''
    if (!insForm.fileId) throw new Error('上传响应缺少文件标识')
    ui.notify('保单文件已上传')
  } catch (e) {
    insForm.fileId = ''
    ui.notify(e?.message || '保单上传失败')
  } finally {
    busy.value = false
    if (event?.target) event.target.value = ''
  }
}
async function saveInsurance() {
  busy.value = true
  try {
    await internshipCoreApi.saveInsurance({ ...insForm })
    ui.notify('保险信息已提交'); await loadTab('insurance', true)
  } catch (e) { ui.notify(e?.message || '保险提交失败') } finally { busy.value = false }
}
async function ackPlan() {
  busy.value = true
  try {
    await internshipCoreApi.acknowledgePlan({
      ...currentInternshipContext(),
      planVersion: planMeta.value?.version,
      expectedVersion: planMeta.value?.ackVersion
    })
    ui.notify('已确认实习计划'); await loadTab('plan', true)
  } catch (e) { ui.notify(e?.message || '确认失败') } finally { busy.value = false }
}
async function submitHelp() {
  if ((helpForm.content || '').trim().length < 5) return ui.notify('情况说明不少于 5 字')
  busy.value = true
  try {
    const d = await portalApi.internshipHelp({ ...helpForm })
    ui.notify(d?.message || '求助已提交')
    helpForm.content = ''; helpForm.title = ''
  } catch (e) { ui.notify(e?.message || '提交失败') } finally { busy.value = false }
}
async function submitWeekly() {
  if (!weeklyForm.week) return ui.notify('请填写周次')
  busy.value = true
  try {
    const context = currentInternshipContext()
    const existing = (my.value.weeklyReports || []).find(
      (item) => Number(item.weekNo || item.week) === Number(weeklyForm.week)
    )
    await internshipCoreApi.submitWeeklyReport({
      ...context,
      expectedVersion: existing?.version ?? 0,
      weekNo: weeklyForm.week,
      workContent: weeklyForm.workContent,
      harvestContent: weeklyForm.harvestContent,
      planContent: weeklyForm.planContent
    })
    ui.notify('周报已提交')
    Object.assign(weeklyForm, { workContent: '', harvestContent: '', planContent: '' })
    await loadTab('report', true)
  }
  catch (e) { ui.notify(e?.message || '提交失败') } finally { busy.value = false }
}
async function submitReport() {
  busy.value = true
  try {
    const RT = { 月报: 'MONTHLY', 实习总结: 'SUMMARY' }
    const reportType = RT[reportTab.value] || 'MONTHLY'
    const periodKey = reportType === 'SUMMARY' ? 'FINAL' : (reportForm.title || reportTab.value)
    const existing = (my.value.processReports || []).find(
      (item) => item.reportType === reportType && item.periodKey === periodKey
    )
    await internshipCoreApi.submitReport({
      ...currentInternshipContext(),
      reportType,
      periodKey,
      content: reportForm.content,
      expectedVersion: existing?.version ?? 0
    })
    ui.notify(reportTab.value + '已提交')
    Object.assign(reportForm, { title: '', content: '' })
    await loadTab('report', true)
  }
  catch (e) { ui.notify(e?.message || '提交失败') } finally { busy.value = false }
}
async function submitSelfEval() {
  busy.value = true
  try {
    const result = await internshipCoreApi.submitSelfEval({
      ...currentInternshipContext(),
      expectedVersion: selfEvalMeta.value?.version ?? 0,
      selfSummary: evalForm.performance,
      selfHarvest: evalForm.reflection,
      selfProblem: evalForm.problems,
      enterpriseRating: evalForm.enterpriseRating,
      enterpriseFeedback: evalForm.enterpriseFeedback,
      positionRating: evalForm.positionRating,
      positionFeedback: evalForm.positionFeedback
    })
    evalReceipt.value = { actionLabel: '学生自评已提交', id: result?.id || '', version: result?.version,
      statusLabel: result?.reviewStatusLabel || result?.reviewStatus || '待审核', nextStep: '等待导师填写评价并由学校审核' }
    ui.notify('自评已提交'); Object.assign(evalForm, { performance: '', reflection: '', problems: '', enterpriseRating: null,
      enterpriseFeedback: '', positionRating: null, positionFeedback: '' }); await loadTab('eval', true)
  } catch (e) { ui.notify(e?.message || '自评提交失败') } finally { busy.value = false }
}
async function submitAppeal() {
  busy.value = true
  try {
    const result = await portalApi.internshipScoreAppeal({ ...currentInternshipContext(), reason: appealReason.value })
    evalReceipt.value = { actionLabel: '成绩申诉已提交', id: result?.id || '', version: result?.version,
      statusLabel: result?.statusLabel || result?.status || '待处理',
      nextStep: `学校处理时将校验成绩 #${result?.scoreId || '—'} 的 v${result?.scoreVersion ?? '—'} 快照` }
    ui.notify('成绩申诉已提交')
    appealReason.value = ''
    appealMeta.value = await portalApi.internshipScoreAppealStatus(currentInternshipContext())
  }
  catch (e) { ui.notify(e?.message || '提交失败') } finally { busy.value = false }
}
async function printAgreement() {
  busy.value = true
  try { await portalApi.internshipAgreementPrint({}); ui.notify('已生成三方协议打印留痕') }
  catch (e) { ui.notify(e?.message || '打印失败（演示租户为只读）') } finally { busy.value = false }
}
onMounted(load)
</script>

<style scoped>
.sp-now { display: flex; align-items: center; justify-content: space-between; gap: 28px; margin-bottom: 14px; padding: 20px 22px; border-color: color-mix(in srgb, var(--pri) 28%, var(--line)); background: linear-gradient(120deg, color-mix(in srgb, var(--pri) 8%, white), white 68%); box-shadow: 0 12px 32px rgba(30, 64, 175, .08); }
.sp-now__copy { min-width: 0; }
.sp-now__eyebrow { color: var(--pri); font-size: 10px; font-weight: 800; letter-spacing: .12em; }
.sp-now h2 { margin: 4px 0 5px; color: var(--t1); font-size: 19px; }
.sp-now p { margin: 0; color: var(--t2); font-size: 13px; line-height: 1.6; }
.sp-now__meta { display: flex; flex-wrap: wrap; gap: 8px 18px; margin-top: 9px; color: var(--t4); font-size: 12px; }
.sp-source-state { margin-bottom: 14px; border: 1px solid var(--line); border-radius: 12px; background: var(--card, #fff); overflow: hidden; }
.sp-source-state--error { padding-bottom: 14px; border-color: color-mix(in srgb, var(--danger-fg) 28%, var(--line)); }
.sp-source-state--error .sp-btn { margin-left: 16px; }
.sp-process-nav { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-bottom: 18px; }
.sp-process-group { min-width: 0; border: 1px solid var(--line); border-radius: 12px; background: var(--card, #fff); }
.sp-process-group[open] { grid-column: span 2; border-color: color-mix(in srgb, var(--pri) 28%, var(--line)); box-shadow: 0 8px 20px rgba(15, 23, 42, .05); }
.sp-process-group summary { display: flex; align-items: center; justify-content: space-between; gap: 10px; min-height: 58px; padding: 10px 12px; cursor: pointer; list-style: none; }
.sp-process-group summary::-webkit-details-marker { display: none; }
.sp-process-group summary span:first-child { display: flex; flex-direction: column; min-width: 0; }
.sp-process-group summary b { color: var(--t1); font-size: 13px; }
.sp-process-group summary small { overflow: hidden; margin-top: 2px; color: var(--t4); font-size: 10px; white-space: nowrap; text-overflow: ellipsis; }
.sp-process-group__current { flex: none; color: var(--pri); font-size: 11px; font-weight: 600; }
.sp-process-group__items { display: flex; flex-wrap: wrap; gap: 7px; padding: 0 10px 10px; }
.sp-process-group__items button { min-height: 38px; padding: 0 12px; border: 1px solid var(--line); border-radius: 9px; background: #fff; color: var(--t2); cursor: pointer; }
.sp-process-group__items button:hover { border-color: var(--pri); color: var(--pri); }
.sp-process-group__items button.is-active { border-color: color-mix(in srgb, var(--pri) 35%, white); background: var(--pri-50); color: var(--pri); font-weight: 600; }
.pill { display: inline-flex; align-items: center; gap: 5px; height: 26px; padding: 0 10px; background: #F5F7FA; border: 1px solid #EDEFF3; border-radius: 7px; font-size: 12.5px; color: var(--t2); }
.statepill { display: inline-flex; align-items: center; gap: 7px; padding: 8px 13px; background: var(--pri-50); border-radius: 9px; color: var(--pri); font-weight: 600; font-size: 13.5px; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--pri); }
.m4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.two { display: grid; grid-template-columns: 1.2fr 1fr; gap: 18px; align-items: start; }
.two2 { display: grid; grid-template-columns: 1fr 1.3fr; gap: 18px; align-items: start; }
.agreement { border: 1px solid var(--line); border-radius: 11px; padding: 18px; font-size: 13.5px; color: var(--t2); line-height: 2; }
.notebox { margin-top: 14px; padding: 12px 14px; background: #F2F7FF; border-radius: 10px; font-size: 12.5px; color: var(--t2); line-height: 1.6; }
.eval-receipt { display: grid; grid-template-columns: auto auto 1fr auto; align-items: center; gap: 12px; margin-bottom: 14px; padding: 12px 14px; border: 1px solid #86efac; border-radius: 10px; background: #f0fdf4; color: #166534; font-size: 12px; }.eval-receipt button { border: 0; background: transparent; color: inherit; }
.repitem { display: flex; align-items: center; gap: 12px; padding: 12px 14px; border: 1px solid var(--line); border-radius: 11px; }
.score-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; }
.score-grid dt { font-size: 12px; color: var(--t3); margin-bottom: 4px; }
.score-grid dd { margin: 0; font-size: 15px; font-weight: 600; color: var(--t1); }
@media (max-width: 900px) { .score-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 900px) { .sp-process-nav { grid-template-columns: repeat(2, minmax(0, 1fr)); } .sp-process-group[open] { grid-column: span 2; } .m4 { grid-template-columns: repeat(2,1fr); } .two, .two2 { grid-template-columns: 1fr; } }
@media (max-width: 640px) { .sp-now { align-items: stretch; flex-direction: column; gap: 14px; } .sp-process-nav { grid-template-columns: 1fr; } .sp-process-group[open] { grid-column: span 1; } }
</style>
