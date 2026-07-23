<template>
  <div class="sp-page">
    <nav class="sp-tabs">
      <button v-for="t in tabs" :key="t.key" class="sp-tab" :class="{ 'is-active': tab === t.key }" @click="tab = t.key">{{ t.label }}</button>
    </nav>

    <StateBlock v-if="loading" type="loading" text="加载中…" />
    <StateBlock v-else-if="error" type="error" :text="error" />
    <template v-else>
      <!-- 我的课表 -->
      <section v-if="tab === 'schedule'" class="sp-card">
        <div class="sp-panel__head">
          <span>我的课表 <span class="sp-muted">{{ schedule.note || '' }}</span></span>
          <button class="sp-btn sp-btn--ghost sp-btn--sm" :disabled="busy" @click="printSchedule">打印课表</button>
        </div>
        <StateBlock v-if="!(schedule.items||[]).length" type="empty" text="暂无已发布课表" />
        <div v-else class="sched-grid">
          <div /><div v-for="d in days" :key="d" class="sched-day">{{ d }}</div>
          <template v-for="row in scheduleRows" :key="row.label">
            <div class="sched-time">{{ row.label }}</div>
            <div v-for="(cell, ci) in row.cells" :key="ci" class="sched-cell">
              <div v-if="cell" class="sched-course"><div style="font-weight:600;color:var(--pri)">{{ cell.name }}</div><div style="font-size:11px;color:var(--t2);margin-top:3px">{{ cell.room }}</div><div style="font-size:11px;color:var(--t4)">{{ cell.teacher }}</div></div>
            </div>
          </template>
        </div>
      </section>

      <!-- 选课中心 -->
      <section v-else-if="tab === 'select'">
        <div class="select-grid">
          <div class="sp-card" style="padding:0;overflow:hidden">
            <div style="display:flex;align-items:center;justify-content:space-between;padding:16px 18px;border-bottom:1px solid var(--line2)"><span style="font-size:16px;font-weight:600">选课</span><span class="sp-muted">已选 {{ selectedCourses.length }} 门 · {{ selectedCredit }} 学分</span></div>
            <StateBlock v-if="!courses.length" type="empty" text="当前没有开放的选课批次" />
            <table v-else class="sp-table">
              <thead><tr><th>课程</th><th>教师</th><th>学分</th><th>容量</th><th style="text-align:right">操作</th></tr></thead>
              <tbody>
                <tr v-for="c in courses" :key="c.selectionCourseId || c.courseId">
                  <td style="font-weight:500;color:var(--t1)">{{ c.courseName || '—' }}</td>
                  <td>{{ c.teacherName || '—' }}</td>
                  <td>{{ c.credit ?? '—' }}</td>
                  <td>余 {{ c.remain ?? '—' }} / {{ c.capacity ?? '—' }}</td>
                  <td style="text-align:right">
                    <button v-if="isSelectedCourse(c)" class="mini mini--ghost" :disabled="busy" @click="drop(c)">退课</button>
                    <button v-else class="mini" :disabled="busy || c.remain === 0" @click="enroll(c)">选课</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="sp-card" style="position:sticky;top:0">
            <div class="sp-panel__head">选课统计</div>
            <div style="display:flex;align-items:baseline;gap:4px">
              <span style="font-size:30px;font-weight:700;color:var(--pri);font-variant-numeric:tabular-nums">{{ selectedCredit }}</span>
              <span class="sp-muted">学分{{ suggestedCredit ? ' / 建议 ' + suggestedCredit : '' }}</span>
            </div>
            <div class="bar"><span :style="{ width: creditBarPct + '%' }" /></div>
            <div style="margin-top:14px;display:flex;flex-direction:column;gap:8px;font-size:13px;color:var(--t2)">
              <div style="display:flex;justify-content:space-between"><span>已选门数</span><span>{{ selectedCourses.length }} 门</span></div>
            </div>
          </div>
        </div>
        <AutoTable :rows="selectionRecords" empty="暂无选课记录" title="我的选课记录" style="margin-top:16px" />
        <section v-if="activeSelectionRecords.length" class="sp-card" style="margin-top:12px;padding:0;overflow:hidden">
          <div style="padding:14px 18px;border-bottom:1px solid var(--line2);font-weight:600">已选课程（可退课）</div>
          <table class="sp-table">
            <thead><tr><th>课程</th><th>状态</th><th style="text-align:right">操作</th></tr></thead>
            <tbody>
              <tr v-for="r in activeSelectionRecords" :key="r.selectionCourseId || r.recordId">
                <td>{{ r.courseName || '—' }}</td>
                <td>{{ r.status || '—' }}</td>
                <td style="text-align:right">
                  <button class="mini mini--ghost" :disabled="busy" @click="drop({ selectionCourseId: r.selectionCourseId })">退课</button>
                </td>
              </tr>
            </tbody>
          </table>
        </section>
      </section>

      <!-- 我的成绩 -->
      <section v-else-if="tab === 'grades'">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
          <span style="font-size:15px;font-weight:600">我的成绩</span>
          <span class="sp-muted">已获学分 <b style="color:var(--pri)">{{ transcript.earnedCredits ?? 0 }}</b> · GPA <b style="color:var(--pri)">{{ transcript.gpa ?? '—' }}</b> · 不及格 {{ transcript.failCount ?? 0 }} 门</span>
        </div>
        <StateBlock v-if="!(transcript.items||[]).length" type="empty" :text="transcript.note || '暂无学业记录'" />
        <section v-for="t in gradeTerms" :key="t.term" class="sp-card" style="padding:0;overflow:hidden;margin-bottom:16px">
          <div style="display:flex;align-items:center;justify-content:space-between;padding:14px 18px;border-bottom:1px solid var(--line2)"><span style="font-size:14px;font-weight:600">{{ t.term || '未分学期' }}</span><span class="sp-muted">{{ t.rows.length }} 门 · {{ t.credit }} 学分</span></div>
          <table class="sp-table">
            <thead><tr><th>课程名称</th><th>学分</th><th>成绩</th><th>结果</th></tr></thead>
            <tbody>
              <tr v-for="(g, i) in t.rows" :key="i">
                <td style="color:var(--t1)">{{ g.courseName }}</td>
                <td>{{ g.credit }}</td>
                <td :style="{ color: scoreColor(g.score), fontWeight: 600 }">{{ g.score ?? '—' }}</td>
                <td><StatusTag :text="g.passStatus === 'PASSED' ? '及格' : '不及格'" :tone="g.passStatus === 'PASSED' ? 'success' : 'danger'" /></td>
              </tr>
            </tbody>
          </table>
        </section>
      </section>

      <!-- 成绩单打印 -->
      <section v-else-if="tab === 'transcript'">
        <div class="two">
          <div class="sp-card">
            <div class="tr-preview">
              <div class="tr-wm">{{ brandSchool }} · 仅供查验</div>
              <div style="position:relative;text-align:center;font-size:17px;font-weight:700">{{ brandSchool }}学生成绩单</div>
              <div style="position:relative;text-align:center;font-size:12px;color:var(--t4);margin-top:4px">Official Academic Transcript</div>
              <div style="position:relative;display:grid;grid-template-columns:1fr 1fr;gap:8px 24px;margin-top:18px;font-size:13px;color:var(--t2)">
                <div>姓名：{{ studentName }}</div><div>学号：{{ info.studentNo || '—' }}</div>
                <div>学院：{{ info.collegeName || '—' }}</div><div>专业：{{ info.majorName || '—' }}</div>
              </div>
              <div style="position:relative;margin-top:16px;font-size:12.5px;color:var(--t4)">已修课程 {{ (transcript.items||[]).length }} 门 · 已获学分 {{ transcript.earnedCredits ?? 0 }} · 平均绩点 {{ transcript.gpa ?? '—' }}</div>
            </div>
          </div>
          <div class="sp-card">
            <div class="sp-panel__head">开具成绩单</div>
            <div class="sp-fieldlabel">开具事由（必填，将写入审计）</div>
            <input v-model.trim="printReason" class="sp-inp" style="margin-bottom:12px" placeholder="如：入党材料 / 转学申请 / 个人留存" />
            <button class="sp-btn" :disabled="busy || !printReason" @click="printTranscript(printReason)">生成并下载（带水印）</button>
          </div>
        </div>
      </section>

      <!-- 学生评教（匿名，与小程序同口径） -->
      <section v-else-if="tab === 'evaluation'">
        <div class="sp-card" style="margin-bottom:16px">
          <div class="sp-panel__head">学生评教</div>
          <p class="sp-muted" style="margin:0">匿名提交，仅对本班开放窗口内课程打分；提交后教务按班级合计统计，不回传个人身份。</p>
        </div>
        <StateBlock v-if="!(evaluation.list||[]).length" type="empty" :text="evaluation.note || '暂无开放中的评教任务'" />
        <section v-else class="sp-card" style="padding:0;overflow:hidden">
          <table class="sp-table">
            <thead>
              <tr>
                <th>课程</th><th>教师</th><th>批次</th><th>班级已交</th><th style="width:280px">综合分（0-100）</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in evaluation.list" :key="t.taskId">
                <td style="font-weight:500;color:var(--t1)">{{ t.courseName || '—' }}</td>
                <td>{{ t.teacherName || '—' }}</td>
                <td>{{ t.batchName || '—' }}</td>
                <td>{{ t.submittedCount ?? 0 }}</td>
                <td>
                  <div style="display:flex;gap:8px;align-items:center">
                    <input class="sp-inp" style="width:88px;margin:0" type="number" min="0" max="100"
                           v-model.number="evalScores[t.taskId]" placeholder="如 90" />
                    <button class="mini" :disabled="busy || !canSubmitEval(t.taskId)"
                            @click="submitEvaluation(t)">匿名提交</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </section>
      </section>

      <!-- 成绩复查（真实落库，与小程序同口径） -->
      <section v-else-if="tab === 'appeal'">
        <div class="two">
          <section class="sp-card" style="max-width:640px">
            <div class="sp-panel__head">发起成绩复查</div>
            <div class="sp-fieldlabel">选择已发布成绩</div>
            <select v-model="appealForm.gradeId" class="sp-inp" style="margin-bottom:12px">
              <option value="">请选择</option>
              <option v-for="g in recheckableGrades" :key="g.gradeId" :value="String(g.gradeId)">
                {{ g.courseName }}{{ g.term ? ' · ' + g.term : '' }}（{{ g.score ?? '—' }} 分）
              </option>
            </select>
            <div class="sp-fieldlabel">复查事由（≥5 字）</div>
            <textarea v-model.trim="appealForm.reason" class="sp-inp" style="margin-bottom:12px"
                      placeholder="如：核对卷面分 / 漏统计平时分" />
            <button class="sp-btn" :disabled="busy || !canSubmitRecheck" @click="submitRecheck">提交复查申请</button>
            <p class="sp-muted" style="margin-top:10px">仅可复查本人已发布成绩；同一门成绩在途复查仅限一条。结果将在消息通知告知。</p>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">我的复查申请</div>
            <AutoTable :rows="recheck.items" empty="暂无复查申请" />
          </section>
        </div>
      </section>

      <!-- 学籍异动申请 -->
      <section v-else-if="tab === 'status'" class="sp-card">
        <div class="sp-panel__head">学籍异动申请向导</div>
        <div class="wiz">
          <div v-for="(w, i) in wizSteps" :key="w.n" class="wiz__seg">
            <div class="wiz__node"><span class="wiz__c" :class="wizClass(w.n)">{{ w.n }}</span><span class="wiz__t" :class="{ on: wizStep >= w.n }">{{ w.t }}</span></div>
            <span v-if="i < wizSteps.length-1" class="wiz__line" :style="{ background: wizStep > w.n ? 'var(--pri)' : '#E5E8EE' }" />
          </div>
        </div>
        <template v-if="wizStep === 1">
          <div class="sp-muted" style="margin-bottom:12px">当前学籍：<StatusTag :text="statusText(status.studentStatus)" :tone="status.studentStatus==='NORMAL'?'success':'warn'" /> · 请选择异动类型</div>
          <div style="display:flex;gap:12px;flex-wrap:wrap">
            <button v-for="ct in changeTypes" :key="ct.k" class="typecard" :class="{ on: statusForm.changeType === ct.k }" @click="statusForm.changeType = ct.k">
              <div style="font-size:14px;font-weight:600" :style="{ color: statusForm.changeType===ct.k ? 'var(--pri)' : 'var(--t1)' }">{{ ct.t }}</div>
              <div class="sp-muted" style="margin-top:5px">{{ ct.desc }}</div>
            </button>
          </div>
          <button class="sp-btn" style="margin-top:20px" @click="wizStep = 2">下一步</button>
        </template>
        <template v-else-if="wizStep === 2">
          <div v-if="statusForm.changeType === 'TRANSFER_MAJOR'" style="margin-bottom:12px">
            <div class="sp-fieldlabel">目标专业（必选）</div>
            <select v-model="statusForm.toMajorId" class="sp-inp" style="margin-bottom:8px">
              <option value="">请选择目标专业</option>
              <option v-for="m in transferOptions.majors" :key="m.majorId" :value="String(m.majorId)">
                {{ m.collegeName ? m.collegeName + ' · ' : '' }}{{ m.majorName }}
              </option>
            </select>
            <div class="sp-fieldlabel">目标班级（可选）</div>
            <select v-model="statusForm.toClassId" class="sp-inp" style="margin-bottom:8px" :disabled="!statusForm.toMajorId">
              <option value="">暂不指定班级</option>
              <option v-for="c in majorTargetClasses" :key="c.classId" :value="String(c.classId)">{{ c.className }}{{ c.grade ? ' · ' + c.grade : '' }}</option>
            </select>
          </div>
          <div v-if="statusForm.changeType === 'TRANSFER_CLASS'" style="margin-bottom:12px">
            <div class="sp-fieldlabel">目标班级（必选，同专业）</div>
            <select v-model="statusForm.toClassId" class="sp-inp" style="margin-bottom:8px">
              <option value="">请选择目标班级</option>
              <option v-for="c in transferOptions.classes" :key="c.classId" :value="String(c.classId)">{{ c.className }}{{ c.grade ? ' · ' + c.grade : '' }}</option>
            </select>
          </div>
          <div class="sp-fieldlabel">申请事由</div>
          <textarea v-model.trim="statusForm.reason" class="sp-inp" style="margin-bottom:12px" placeholder="请详细说明申请原因" />
          <div style="display:flex;gap:10px">
            <button class="sp-btn sp-btn--ghost" @click="wizStep = 1">上一步</button>
            <button class="sp-btn" :disabled="!canNextStatusStep" @click="wizStep = 3">下一步：预览</button>
          </div>
        </template>
        <template v-else>
          <div class="preview">
            异动类型：<b>{{ changeLabel(statusForm.changeType) }}</b><br />
            申请人：{{ studentName }}（{{ info.studentNo }}）<br />
            <template v-if="statusForm.changeType === 'TRANSFER_MAJOR'">目标专业：{{ majorLabel(statusForm.toMajorId) }}<br /></template>
            <template v-if="statusForm.toClassId">目标班级：{{ classLabel(statusForm.toClassId) }}<br /></template>
            事由：{{ statusForm.reason }}
          </div>
          <div style="display:flex;gap:10px;margin-top:16px">
            <button class="sp-btn sp-btn--ghost" @click="wizStep = 2">上一步</button>
            <button class="sp-btn" :disabled="busy" @click="submitStatusChange">提交并下载申请表</button>
          </div>
        </template>
        <AutoTable :rows="status.changes" empty="暂无异动记录" title="历史异动记录" style="margin-top:16px" />
      </section>

      <!-- 免修/缓考/补考重修 + 我的考试安排 -->
      <section v-else-if="tab === 'exam'">
        <div style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap">
          <button v-for="e in examTabs" :key="e" class="sp-tab" :class="{ 'is-active': examTab === e }" @click="examTab = e">{{ e }}</button>
        </div>
        <section v-if="examTab === '我的考试'" class="sp-card" style="padding:0;overflow:hidden">
          <div style="padding:14px 18px;border-bottom:1px solid var(--line2);font-weight:600">我的考试安排</div>
          <StateBlock v-if="!(examSchedule.items||[]).length" type="empty" :text="examSchedule.note || '暂无已发布的个人考试安排'" />
          <table v-else class="sp-table">
            <thead><tr><th>课程</th><th>日期</th><th>时间</th><th>考场</th><th>座位</th><th>准考证</th></tr></thead>
            <tbody>
              <tr v-for="it in examSchedule.items" :key="it.examCourseId">
                <td style="font-weight:500">{{ it.courseName }}</td>
                <td>{{ it.examDate || '—' }}</td>
                <td>{{ it.startTime || '' }}{{ it.endTime ? ' - ' + it.endTime : '' }}</td>
                <td>{{ it.classroom || '—' }}</td>
                <td>{{ it.seatNo ?? '—' }}</td>
                <td>{{ it.admissionNo || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </section>
        <div v-else class="two">
          <section class="sp-card">
            <div class="sp-panel__head">{{ examTab }}</div>
            <template v-if="examTab === '缓考申请'">
              <div class="sp-fieldlabel">选择未开考课程</div>
              <select v-model="deferForm.examCourseId" class="sp-inp" style="margin-bottom:12px">
                <option value="">请选择</option>
                <option v-for="c in deferOptions" :key="c.examCourseId" :value="String(c.examCourseId)"
                        :disabled="c.hasActiveDefer">
                  {{ c.courseName }} · {{ c.examDate || '未排定' }} {{ c.startTime || '' }}{{ c.hasActiveDefer ? '（申请中）' : '' }}
                </option>
              </select>
              <div class="sp-fieldlabel">缓考事由类型</div>
              <select v-model="deferForm.reasonType" class="sp-inp" style="margin-bottom:12px">
                <option v-for="r in deferReasons" :key="r.v" :value="r.v">{{ r.t }}</option>
              </select>
              <div class="sp-fieldlabel">原因说明</div>
              <textarea v-model.trim="deferForm.reason" class="sp-inp" style="margin-bottom:12px" placeholder="如病假需附材料请线下提交辅导员" />
              <button class="sp-btn" :disabled="busy || !deferForm.examCourseId" @click="submitDefer">提交缓考申请</button>
            </template>
            <template v-else>
              <div class="sp-fieldlabel">课程名称</div>
              <input v-model.trim="examForm.courseName" class="sp-inp" style="margin-bottom:12px" placeholder="如：高等数学(下)" />
              <div class="sp-fieldlabel">申请理由</div>
              <textarea v-model.trim="examForm.reason" class="sp-inp" style="margin-bottom:12px" placeholder="请说明申请理由并准备佐证材料" />
              <button class="sp-btn" :disabled="busy || !examForm.reason || !examForm.courseName" @click="submitExam">提交申请</button>
            </template>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">申请记录</div>
            <template v-if="examTab === '缓考申请'">
              <AutoTable :rows="examDefer.items" empty="暂无申请记录" />
              <div v-if="returnedDefers.length" style="margin-top:12px">
                <div class="sp-fieldlabel">待补材料重提</div>
                <div v-for="r in returnedDefers" :key="r.deferId" style="display:flex;justify-content:space-between;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid var(--line2)">
                  <div>
                    <div style="font-weight:500">{{ r.courseName }}</div>
                    <div class="sp-muted">{{ r.returnReason || '请按退回意见补材料后重提' }}</div>
                  </div>
                  <button class="mini" :disabled="busy" @click="resubmitDefer(r)">补材料重提</button>
                </div>
              </div>
            </template>
            <AutoTable v-else-if="examTab === '免修申请'" :rows="exemptionRows" :columns="EXEMPTION_COLS" empty="暂无申请记录" />
            <AutoTable v-else :rows="retakeRows" :columns="RETAKE_COLS" empty="暂无申请记录" />
          </section>
        </div>
      </section>

      <!-- 学分修读 -->
      <section v-else-if="tab === 'credits'">
        <section class="sp-card">
          <div class="sp-panel__head">学分修读</div>
          <div class="sp-muted">已获 <b style="color:var(--pri)">{{ credits.obtainedCredits ?? 0 }}</b> / 应修 {{ credits.requiredCredits ?? '—' }} · GPA {{ credits.gpa ?? '—' }} · 不及格 {{ credits.failCount ?? 0 }} 门</div>
          <div class="bar" style="margin-top:12px"><span :style="{ width: creditPct + '%' }" /></div>
        </section>
        <AutoTable :rows="credits.passedCourses" empty="暂无已通过课程" title="已通过课程" />
      </section>

      <!-- 学业预警 -->
      <section v-else-if="tab === 'warning'" class="sp-card">
        <div class="sp-panel__head">我的学业预警</div>
        <AutoTable :rows="warning.items" empty="暂无学业预警" />
      </section>

      <!-- 教材领用 -->
      <section v-else-if="tab === 'textbook'">
        <section class="sp-card">
          <div class="sp-panel__head">教材费用汇总</div>
          <pre class="sp-muted" style="white-space:pre-wrap;margin:0;font-family:inherit">{{ textbookFeeText }}</pre>
        </section>
        <section class="sp-card" style="padding:0;overflow:hidden">
          <div style="padding:14px 18px;border-bottom:1px solid var(--line2);font-weight:600">领用记录</div>
          <StateBlock v-if="!(textbook.distributions||[]).length" type="empty" text="暂无教材发放记录" />
          <table v-else class="sp-table">
            <thead><tr><th>教材</th><th>状态</th><th style="text-align:right">操作</th></tr></thead>
            <tbody>
              <tr v-for="d in textbook.distributions" :key="d.recordId || d.id">
                <td>{{ d.bookName || d.textbookName || d.courseName || '—' }}</td>
                <td>{{ d.status || d.signStatus || '—' }}</td>
                <td style="text-align:right">
                  <button v-if="canSignTextbook(d)" class="mini" :disabled="busy" @click="signTextbook(d)">签收</button>
                  <span v-else class="sp-muted">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </section>
      </section>

      <!-- 等级考试 -->
      <section v-else-if="tab === 'level'">
        <div class="two">
          <section class="sp-card" style="padding:0;overflow:hidden">
            <div style="padding:14px 18px;border-bottom:1px solid var(--line2);font-weight:600">开放报名</div>
            <StateBlock v-if="!(levelExam.openExams||[]).length" type="empty" text="暂无开放中的等级考试" />
            <table v-else class="sp-table">
              <thead><tr><th>考试</th><th>报名截止</th><th style="text-align:right">操作</th></tr></thead>
              <tbody>
                <tr v-for="e in levelExam.openExams" :key="e.examId">
                  <td style="font-weight:500">{{ e.examName || e.name || '—' }}</td>
                  <td>{{ e.regEndAt || e.endAt || '—' }}</td>
                  <td style="text-align:right">
                    <button v-if="!isLevelRegistered(e.examId)" class="mini" :disabled="busy" @click="registerLevel(e)">报名</button>
                    <span v-else class="sp-muted">已报名</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">我的报名</div>
            <StateBlock v-if="!(levelExam.myRegs||[]).length" type="empty" text="暂无报名记录" />
            <table v-else class="sp-table">
              <thead><tr><th>考试</th><th>状态</th><th style="text-align:right">操作</th></tr></thead>
              <tbody>
                <tr v-for="r in levelExam.myRegs" :key="r.regId || r.examId">
                  <td>{{ levelExamName(r.examId) }}</td>
                  <td>{{ r.status || '—' }}{{ r.feeStatus === 'PAID' ? ' · 已缴费' : '' }}</td>
                  <td style="text-align:right">
                    <button v-if="canCancelLevel(r)" class="mini mini--ghost" :disabled="busy" @click="cancelLevel(r)">取消</button>
                    <span v-else class="sp-muted">—</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </section>
        </div>
      </section>

      <!-- 专业分流 -->
      <section v-else-if="tab === 'split'">
        <StateBlock v-if="!(majorSplit.openBatches||[]).length && !(majorSplit.myVolunteers||[]).length"
                    type="empty" text="暂无开放中的分流批次" />
        <section v-for="b in (majorSplit.openBatches || [])" :key="b.batchId" class="sp-card" style="margin-bottom:16px">
          <div class="sp-panel__head">{{ b.batchName }} · {{ b.grade }} 级（至多 {{ b.maxChoices }} 志愿）</div>
          <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px">
            <button v-for="o in (b.options || [])" :key="o.majorId" type="button" class="typecard"
                    :class="{ on: splitRank(b.batchId, o.majorId) > 0 }"
                    style="width:auto;min-width:140px"
                    @click="toggleSplit(b, o)">
              <div style="font-size:14px;font-weight:600">{{ o.majorName }}</div>
              <div class="sp-muted" style="margin-top:4px">余 {{ o.remain }}/{{ o.capacity }}
                <span v-if="splitRank(b.batchId, o.majorId)"> · 第{{ splitRank(b.batchId, o.majorId) }}志愿</span>
              </div>
            </button>
          </div>
          <button class="sp-btn" :disabled="busy || !(splitPicks[b.batchId]||[]).length" @click="submitSplit(b)">提交志愿</button>
        </section>
        <AutoTable :rows="majorSplit.myVolunteers" empty="暂无已提交志愿" title="我的志愿与结果" />
      </section>

      <!-- 成绩认定 -->
      <section v-else-if="tab === 'recognition'">
        <div class="two">
          <section class="sp-card" style="max-width:640px">
            <div class="sp-panel__head">成绩认定 / 课程替代</div>
            <div class="sp-fieldlabel">原课程名称</div>
            <input v-model.trim="recogForm.sourceCourseName" class="sp-inp" style="margin-bottom:12px" placeholder="校外/原修课程名" />
            <div class="sp-fieldlabel">原成绩（60–100）</div>
            <input v-model.number="recogForm.sourceScore" class="sp-inp" style="margin-bottom:12px" type="number" min="60" max="100" />
            <div class="sp-fieldlabel">原学分（选填）</div>
            <input v-model.number="recogForm.sourceCredit" class="sp-inp" style="margin-bottom:12px" type="number" min="0" step="0.5" />
            <div class="sp-fieldlabel">来源说明</div>
            <input v-model.trim="recogForm.sourceOrigin" class="sp-inp" style="margin-bottom:12px" placeholder="原专业/原学校/证书折算" />
            <div class="sp-fieldlabel">目标校内课程</div>
            <input v-model.trim="recogForm.targetCourseName" class="sp-inp" style="margin-bottom:12px" placeholder="培养计划课程名" />
            <div class="sp-fieldlabel">申请理由</div>
            <textarea v-model.trim="recogForm.reason" class="sp-inp" style="margin-bottom:12px" placeholder="选填" />
            <button class="sp-btn" :disabled="busy || !canSubmitRecog" @click="submitRecognition">提交认定申请</button>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">我的认定申请</div>
            <AutoTable :rows="recognition.items" empty="暂无认定申请" />
          </section>
        </div>
      </section>

      <!-- 毕业资格自查 -->
      <section v-else-if="tab === 'audit'">
        <section class="sp-card">
          <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px">
            <div><div style="font-size:16px;font-weight:600">毕业资格达成度</div><div class="sp-muted" style="margin-top:6px">{{ audit.progress?.note || '数据每日更新' }}</div></div>
            <div style="display:flex;align-items:baseline;gap:6px"><span style="font-size:32px;font-weight:700;color:var(--pri);font-variant-numeric:tabular-nums">{{ auditPct }}</span><span class="sp-muted">%</span></div>
          </div>
          <div class="bar" style="margin-top:14px;height:10px"><span :style="{ width: auditPct + '%' }" /></div>
        </section>
        <section class="sp-card" style="padding:0;overflow:hidden">
          <table class="sp-table">
            <thead><tr><th>培养环节</th><th>要求学分</th><th>已修学分</th><th>状态</th></tr></thead>
            <tbody>
              <tr><td>总学分</td><td>{{ audit.credits?.requiredCredits ?? '—' }}</td><td>{{ audit.credits?.obtainedCredits ?? 0 }}</td><td><StatusTag :text="(audit.credits?.obtainedCredits||0) >= (audit.credits?.requiredCredits||999) ? '已达标' : '进行中'" :tone="(audit.credits?.obtainedCredits||0) >= (audit.credits?.requiredCredits||999) ? 'success':'warn'" /></td></tr>
              <tr v-for="(w, i) in (audit.warnings?.items || [])" :key="i"><td>{{ w.name || w.category || '预警项' }}</td><td>—</td><td>—</td><td><StatusTag :text="w.text || '预警'" tone="danger" /></td></tr>
            </tbody>
          </table>
          <StateBlock v-if="!(audit.warnings?.items||[]).length" type="empty" text="暂无毕业预警" />
        </section>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import AutoTable from '../../components/AutoTable.vue'
import { portalApi } from '../../services/portalApi'
import { usePortalConfigStore } from '../../stores/portalConfig'
import { useSessionStore } from '../../stores/session'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const cfg = usePortalConfigStore()
const session = useSessionStore()
const tabs = [
  { key: 'schedule', label: '我的课表' }, { key: 'select', label: '选课中心' }, { key: 'grades', label: '我的成绩' },
  { key: 'transcript', label: '成绩单打印' }, { key: 'evaluation', label: '学生评教' }, { key: 'appeal', label: '成绩复查' },
  { key: 'status', label: '学籍异动' }, { key: 'exam', label: '考试/缓考/免修' },
  { key: 'credits', label: '学分修读' }, { key: 'warning', label: '学业预警' },
  { key: 'textbook', label: '教材领用' }, { key: 'level', label: '等级考试' },
  { key: 'split', label: '专业分流' }, { key: 'recognition', label: '成绩认定' },
  { key: 'audit', label: '毕业自查' }
]
const tab = ref('schedule')
const examTab = ref('我的考试')
const examTabs = ['我的考试', '免修申请', '缓考申请', '补考重修申请']
const wizStep = ref(1)
const loading = ref(true)
const busy = ref(false)
const error = ref('')

const schedule = ref({})
const courses = ref([])
const selectionRecords = ref([])
const transcript = ref({})
const evaluation = ref({ list: [], total: 0 })
const evalScores = reactive({})
const status = ref({})
const examDefer = ref({})
const examSchedule = ref({ items: [] })
const deferOptions = ref([])
const makeup = ref({})
const audit = ref({})
const info = ref({})
const recheck = ref({ items: [] })
const credits = ref({})
const warning = ref({ items: [] })
const textbook = ref({ distributions: [], fees: {} })
const levelExam = ref({ openExams: [], myRegs: [] })
const majorSplit = ref({ openBatches: [], myVolunteers: [] })
const recognition = ref({ items: [] })
const splitPicks = reactive({})

const printReason = ref('')
const appealForm = reactive({ gradeId: '', reason: '' })
const statusForm = reactive({ changeType: 'SUSPEND', reason: '', toMajorId: '', toClassId: '' })
const transferOptions = ref({ majors: [], classes: [], majorClasses: {} })
const examForm = reactive({ reason: '', courseName: '' })
const deferForm = reactive({ examCourseId: '', reasonType: 'SICK', reason: '' })
const recogForm = reactive({
  sourceCourseName: '', sourceScore: 60, sourceCredit: null, sourceOrigin: '', targetCourseName: '', reason: '',
})
const deferReasons = [
  { v: 'SICK', t: '因病' }, { v: 'CONFLICT', t: '考试冲突' }, { v: 'FAMILY', t: '家事' }, { v: 'OTHER', t: '其他' }
]

const days = ['周一', '周二', '周三', '周四', '周五']
const wizSteps = [{ n: 1, t: '选择类型' }, { n: 2, t: '填写事由' }, { n: 3, t: '预览提交' }]
const changeTypes = [
  { k: 'SUSPEND', t: '休学', desc: '暂停学业，学籍状态变为休学' },
  { k: 'PRESERVE', t: '保留学籍', desc: '应征入伍/联合培养等离校保留学籍' },
  { k: 'RESUME', t: '复学', desc: '休学或保留学籍期满恢复学习' },
  { k: 'TRANSFER_MAJOR', t: '转专业', desc: '跨专业调整，须选目标专业' },
  { k: 'TRANSFER_CLASS', t: '转班', desc: '同专业换班，须选目标班级' },
  { k: 'RETAIN', t: '留级', desc: '降级继续修读' },
  { k: 'WITHDRAW', t: '退学', desc: '终止学业注销学籍' }
]
const brandSchool = computed(() => cfg.brand?.schoolName || '学校')
const studentName = computed(() => session.user?.realName || '同学')
const selectedCourses = computed(() => selectionRecords.value)
const selectedCredit = computed(() => selectionRecords.value.reduce((a, c) => a + (Number(c.credit) || 0), 0))
const activeSelectionRecords = computed(() =>
  (selectionRecords.value || []).filter((r) => ['SELECTED', 'LOCKED'].includes(String(r.status || '').toUpperCase())))
const returnedDefers = computed(() =>
  (examDefer.value.items || []).filter((r) => String(r.status || '').toUpperCase() === 'RETURNED'))
const canSubmitRecog = computed(() => {
  const s = Number(recogForm.sourceScore)
  return !!(recogForm.sourceCourseName || '').trim()
    && !!(recogForm.targetCourseName || '').trim()
    && !Number.isNaN(s) && s >= 60 && s <= 100
})
const TIME_ROWS = ['第1-2节\n08:00-09:40', '第3-4节\n10:00-11:40', '第5-6节\n14:00-15:40', '第7-8节\n16:00-17:40', '第9-10节\n19:00-20:40']
const scheduleRows = computed(() => {
  const items = schedule.value.items || []
  const rows = TIME_ROWS.map((label) => ({ label, cells: [null, null, null, null, null] }))
  for (const it of items) {
    const day = Number(it.weekday ?? it.dayOfWeek ?? it.day) // 1..7
    const sec = Number(it.slotNo ?? it.section ?? it.period) // 节次(1/3/5/7/9 或 1..10)
    const di = (day >= 1 && day <= 5) ? day - 1 : -1
    let ri = -1
    if (sec >= 1 && sec <= 5) ri = sec - 1
    else if (sec >= 1 && sec <= 10) ri = Math.floor((sec - 1) / 2)
    if (di >= 0 && ri >= 0 && !rows[ri].cells[di]) {
      rows[ri].cells[di] = { name: it.courseName || it.name, room: it.classroom || it.room || '', teacher: it.teacherName || it.teacher || '' }
    }
  }
  return rows
})
const gradeTerms = computed(() => {
  const map = {}
  for (const g of (transcript.value.items || [])) {
    const key = g.term || ''
    if (!map[key]) map[key] = { term: key, rows: [], credit: 0 }
    map[key].rows.push(g)
    if (g.passStatus === 'PASSED') map[key].credit += Number(g.credit || 0)
  }
  return Object.values(map).sort((a, b) => (a.term < b.term ? 1 : -1))
})
const retakeRows = computed(() => makeup.value.retakes || [])
const exemptionRows = computed(() => makeup.value.exemptions || [])
const RETAKE_COLS = [
  { key: 'courseName', label: '课程名称' }, { key: 'termCode', label: '学期' },
  { key: 'reason', label: '申请理由' }, { key: 'retakeCount', label: '第几次' },
  { key: 'status', label: '状态' }, { key: 'reviewReason', label: '审核意见' }
]
const EXEMPTION_COLS = [
  { key: 'courseName', label: '课程名称' }, { key: 'termCode', label: '学期' },
  { key: 'reason', label: '申请理由' }, { key: 'status', label: '状态' },
  { key: 'returnReason', label: '退回原因' }
]
const auditPct = computed(() => {
  const c = audit.value.credits || {}
  if (!c.requiredCredits) return 0
  return Math.min(100, Math.round((c.obtainedCredits || 0) / c.requiredCredits * 100))
})
const recheckableGrades = computed(() => (transcript.value.items || []).filter((g) => g.gradeId != null))
const canSubmitRecheck = computed(() => !!appealForm.gradeId && String(appealForm.reason || '').trim().length >= 5)
const creditPct = computed(() => {
  const req = Number(credits.value.requiredCredits || 0)
  if (!req) return 0
  return Math.min(100, Math.round((Number(credits.value.obtainedCredits || 0) / req) * 100))
})
const textbookFeeText = computed(() => {
  const f = textbook.value.fees
  if (!f || typeof f !== 'object') return '暂无费用汇总'
  const items = Array.isArray(f.items) ? f.items : []
  const head = `应缴 ${f.totalDue ?? 0} · 已缴 ${f.totalPaid ?? 0} · 欠费 ${f.unpaid ?? Math.max(0, Number(f.totalDue || 0) - Number(f.totalPaid || 0))}`
  if (!items.length) return head + '（无明细）'
  const lines = items.map((it) => `${it.textbookName || '教材'}：应缴 ${it.amount ?? 0} / 已缴 ${it.paidAmount ?? 0}（${it.status || '—'}）`)
  return head + '\n' + lines.join('\n')
})
const STATUS_MAP = {
  NORMAL: '正常', REGISTERED: '在籍注册', SUSPENDED: '休学', PRESERVED: '保留学籍',
  RETAINED: '留级', TRANSFERRED: '转学', WITHDRAWN: '退学', GRADUATED: '毕业'
}
const suggestedCredit = computed(() => Number(credits.value.requiredCredits || credits.value.planCredits || 0))
const creditBarPct = computed(() => {
  if (!suggestedCredit.value) return selectedCredit.value ? 100 : 0
  return Math.min(100, Math.round((selectedCredit.value / suggestedCredit.value) * 100))
})
const canNextStatusStep = computed(() => {
  if (String(statusForm.reason || '').trim().length < 5) return false
  if (statusForm.changeType === 'TRANSFER_MAJOR' && !statusForm.toMajorId) return false
  if (statusForm.changeType === 'TRANSFER_CLASS' && !statusForm.toClassId) return false
  return true
})
const majorTargetClasses = computed(() => {
  const mid = String(statusForm.toMajorId || '')
  if (!mid) return []
  return (transferOptions.value.majorClasses && transferOptions.value.majorClasses[mid]) || []
})
function majorLabel(id) {
  const m = (transferOptions.value.majors || []).find((x) => String(x.majorId) === String(id))
  return m ? `${m.collegeName ? m.collegeName + ' · ' : ''}${m.majorName}` : (id || '—')
}
function classLabel(id) {
  const mid = String(statusForm.toMajorId || '')
  const fromMajor = ((transferOptions.value.majorClasses && transferOptions.value.majorClasses[mid]) || [])
    .find((x) => String(x.classId) === String(id))
  if (fromMajor) return fromMajor.className
  const c = (transferOptions.value.classes || []).find((x) => String(x.classId) === String(id))
  return c ? c.className : (id || '—')
}
watch(() => statusForm.changeType, () => {
  statusForm.toMajorId = ''
  statusForm.toClassId = ''
})
watch(() => statusForm.toMajorId, () => {
  if (statusForm.changeType === 'TRANSFER_MAJOR') statusForm.toClassId = ''
})
function statusText(s) { return STATUS_MAP[s] || s || '正常' }
function changeLabel(k) { return (changeTypes.find((c) => c.k === k) || {}).t || k }
function scoreColor(s) { const n = Number(s); return n >= 90 ? 'var(--ok-fg)' : n >= 60 ? 'var(--t1)' : 'var(--warn-fg)' }
function wizClass(n) { return wizStep.value > n ? 'done' : wizStep.value === n ? 'cur' : 'todo' }
function canSignTextbook(d) {
  return String(d.status || '').toUpperCase() === 'PENDING'
}
function splitRank(batchId, majorId) {
  const arr = splitPicks[batchId] || []
  return arr.indexOf(String(majorId)) + 1
}
function isSelectedCourse(c) {
  const id = String(c.selectionCourseId || '')
  return activeSelectionRecords.value.some((r) => String(r.selectionCourseId) === id)
}
function isLevelRegistered(examId) {
  return (levelExam.value.myRegs || []).some((r) =>
    String(r.examId) === String(examId) && String(r.status || '').toUpperCase() === 'REGISTERED')
}
function levelExamName(examId) {
  const e = (levelExam.value.openExams || []).find((x) => String(x.examId) === String(examId))
  return e?.examName || e?.name || (`考试#${examId}`)
}
function canCancelLevel(r) {
  return String(r.status || '').toUpperCase() === 'REGISTERED'
    && (levelExam.value.openExams || []).some((x) => String(x.examId) === String(r.examId))
}

async function loadAll() {
  loading.value = true; error.value = ''
  try {
    const [sc, tr, st, ex, mk, au, cs, rec, en, ev, exam, opts, rc, cr, wn, tb, lv, sp, rg, to] = await Promise.allSettled([
      portalApi.academicSchedule(), portalApi.academicTranscript(), portalApi.academicStatus(),
      portalApi.academicExamDefer(), portalApi.academicMakeup(), portalApi.academicGraduationAudit(),
      portalApi.academicCourseSelection(), portalApi.academicSelectionRecords(), portalApi.profileEnrollment(),
      portalApi.academicEvaluationTasks(), portalApi.academicExam(), portalApi.academicExamDeferOptions(),
      portalApi.academicGradeRecheck(), portalApi.academicCredits(), portalApi.academicWarning(),
      portalApi.academicTextbook(), portalApi.academicLevelExam(), portalApi.academicMajorSplit(),
      portalApi.academicRecognition(), portalApi.academicTransferOptions()
    ])
    const val = (r, d) => (r.status === 'fulfilled' ? (r.value ?? d) : d)
    schedule.value = val(sc, {}); transcript.value = val(tr, {}); status.value = val(st, {})
    examDefer.value = val(ex, {}); makeup.value = val(mk, {}); audit.value = val(au, {})
    const c = val(cs, []); courses.value = Array.isArray(c) ? c.flatMap((x) => x.courses || []) : (c.courses || c.items || [])
    const r = val(rec, []); selectionRecords.value = Array.isArray(r) ? r : (r.items || [])
    info.value = val(en, {})
    evaluation.value = val(ev, { list: [], total: 0 })
    for (const t of (evaluation.value.list || [])) {
      if (evalScores[t.taskId] == null) evalScores[t.taskId] = 90
    }
    examSchedule.value = val(exam, { items: [] })
    deferOptions.value = val(opts, { items: [] }).items || []
    recheck.value = val(rc, { items: [] })
    credits.value = val(cr, {})
    warning.value = val(wn, { items: [] })
    textbook.value = val(tb, { distributions: [], fees: {} })
    levelExam.value = val(lv, { openExams: [], myRegs: [] })
    majorSplit.value = val(sp, { openBatches: [], myVolunteers: [] })
    recognition.value = val(rg, { items: [] })
    transferOptions.value = val(to, { majors: [], classes: [], majorClasses: {} })
    for (const b of (majorSplit.value.openBatches || [])) {
      if (!splitPicks[b.batchId]) {
        const mine = (majorSplit.value.myVolunteers || []).find((v) => String(v.batchId) === String(b.batchId))
        splitPicks[b.batchId] = mine && mine.choices ? mine.choices.map(String) : []
      }
    }
  } catch (e) { error.value = e?.message || '学业数据加载失败' } finally { loading.value = false }
}
async function printTranscript(reason) {
  if (!reason || busy.value) return
  busy.value = true
  try {
    const res = await portalApi.academicTranscriptPrint({ reason })
    downloadAcademicHtml('成绩单', res, buildTranscriptHtml(res))
    ui.notify('已下载成绩单（含水印留痕）')
  } catch (e) { ui.notify(e?.message || '打印失败') } finally { busy.value = false }
}
async function printSchedule() {
  if (busy.value) return
  busy.value = true
  try {
    const res = await portalApi.academicSchedulePrint({ reason: '个人课表' })
    downloadAcademicHtml('个人课表', res, buildScheduleHtml(res))
    ui.notify('已下载课表（含水印留痕）')
  } catch (e) { ui.notify(e?.message || '打印失败') } finally { busy.value = false }
}
function downloadAcademicHtml(title, res, bodyHtml) {
  const wm = res?.watermark || studentName.value || ''
  const at = res?.loggedAt || ''
  const html = `<!DOCTYPE html><html><head><meta charset="utf-8"/><title>${title}</title>
<style>body{font-family:Segoe UI,Microsoft YaHei,sans-serif;padding:24px;color:#111}
.wm{position:fixed;inset:20% 10%;font-size:42px;color:rgba(0,0,0,.08);transform:rotate(-24deg);pointer-events:none;text-align:center}
h1{font-size:20px;margin:0 0 8px} .meta{color:#666;font-size:12px;margin-bottom:16px}
table{width:100%;border-collapse:collapse;font-size:13px} th,td{border:1px solid #ddd;padding:6px 8px;text-align:left}
th{background:#f5f7fa}</style></head><body>
<div class="wm">${wm}</div><h1>${title}</h1>
<div class="meta">水印：${wm} · 留痕时间：${at}${res?.printReason ? ' · 事由：' + res.printReason : ''}</div>
${bodyHtml}</body></html>`
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${title}-${Date.now()}.html`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
function buildTranscriptHtml(res) {
  const doc = res?.document || transcript.value || {}
  const items = doc.items || []
  const rows = items.map((g) => `<tr><td>${g.courseName || '—'}</td><td>${g.term || '—'}</td><td>${g.score ?? '—'}</td><td>${g.credit ?? '—'}</td><td>${g.gpa ?? '—'}</td></tr>`).join('')
  return `<p>学号 ${info.value.studentNo || '—'} · 已获学分 ${doc.earnedCredits ?? 0} · GPA ${doc.gpa ?? '—'}</p>
<table><thead><tr><th>课程</th><th>学期</th><th>成绩</th><th>学分</th><th>绩点</th></tr></thead><tbody>${rows || '<tr><td colspan="5">暂无成绩</td></tr>'}</tbody></table>`
}
function buildScheduleHtml(res) {
  const doc = res?.document || schedule.value || {}
  const items = doc.items || doc.courses || []
  const rows = items.map((c) => `<tr><td>${c.courseName || c.name || '—'}</td><td>${c.weekday || c.weekDay || '—'}</td><td>${c.period || c.sections || '—'}</td><td>${c.classroom || c.room || '—'}</td><td>${c.teacherName || c.teacher || '—'}</td></tr>`).join('')
  return `<table><thead><tr><th>课程</th><th>星期</th><th>节次</th><th>教室</th><th>教师</th></tr></thead><tbody>${rows || '<tr><td colspan="5">暂无课表</td></tr>'}</tbody></table>`
}
function buildStatusChangeHtml(res, form) {
  const doc = res?.document || {}
  const major = form.changeType === 'TRANSFER_MAJOR' ? `<p>目标专业：${majorLabel(form.toMajorId)}</p>` : ''
  const cls = form.toClassId ? `<p>目标班级：${classLabel(form.toClassId)}</p>` : ''
  return `<p>申请人：${doc.realName || studentName.value}（${doc.studentNo || info.value.studentNo || '—'}）</p>
<p>当前学籍：${doc.studentStatus || status.value.studentStatus || '—'}</p>
<p>异动类型：${changeLabel(form.changeType)}</p>
${major}${cls}
<p>申请事由：${form.reason || '—'}</p>`
}
async function enroll(c) {
  busy.value = true
  try { await portalApi.academicEnroll({ selectionCourseId: c.selectionCourseId }); ui.notify('选课成功'); loadAll() }
  catch (e) { ui.notify(e?.message || '选课失败') } finally { busy.value = false }
}
async function drop(c) {
  if (!c?.selectionCourseId || busy.value) return
  busy.value = true
  try { await portalApi.academicDrop({ selectionCourseId: c.selectionCourseId }); ui.notify('已退课'); loadAll() }
  catch (e) { ui.notify(e?.message || '退课失败') } finally { busy.value = false }
}
function canSubmitEval(taskId) {
  const n = Number(evalScores[taskId])
  return !Number.isNaN(n) && n >= 0 && n <= 100
}
async function submitEvaluation(t) {
  if (!canSubmitEval(t.taskId) || busy.value) return
  busy.value = true
  try {
    const score = Number(evalScores[t.taskId])
    await portalApi.academicEvaluationSubmit({
      taskId: t.taskId, objectiveScore: score, answers: { overall: score },
    })
    ui.notify('已匿名提交'); loadAll()
  } catch (e) { ui.notify(e?.message || '提交失败') } finally { busy.value = false }
}
async function submitRecheck() {
  if (!canSubmitRecheck.value || busy.value) return
  busy.value = true
  try {
    await portalApi.academicGradeRecheckSubmit({ acadGradeId: appealForm.gradeId, reason: appealForm.reason.trim() })
    ui.notify('复查申请已提交'); appealForm.gradeId = ''; appealForm.reason = ''; loadAll()
  } catch (e) { ui.notify(e?.message || '提交失败') } finally { busy.value = false }
}
async function submitDefer() {
  if (!deferForm.examCourseId || busy.value) return
  busy.value = true
  try {
    await portalApi.academicExamDeferApply({
      examCourseId: deferForm.examCourseId,
      reasonType: deferForm.reasonType,
      reason: deferForm.reason || undefined,
    })
    ui.notify('缓考申请已提交'); deferForm.examCourseId = ''; deferForm.reason = ''; loadAll()
  } catch (e) { ui.notify(e?.message || '提交失败') } finally { busy.value = false }
}
async function resubmitDefer(r) {
  if (!r?.deferId || busy.value) return
  busy.value = true
  try { await portalApi.academicExamDeferResubmit(r.deferId); ui.notify('已重提'); loadAll() }
  catch (e) { ui.notify(e?.message || '重提失败') } finally { busy.value = false }
}
async function signTextbook(d) {
  const id = d.recordId || d.id
  if (!id || busy.value) return
  busy.value = true
  try { await portalApi.academicTextbookSign(id); ui.notify('已签收'); loadAll() }
  catch (e) { ui.notify(e?.message || '签收失败') } finally { busy.value = false }
}
async function registerLevel(e) {
  const id = e.examId || e.id
  if (!id || busy.value) return
  busy.value = true
  try { await portalApi.academicLevelRegister(id); ui.notify('已报名'); loadAll() }
  catch (err) { ui.notify(err?.message || '报名失败') } finally { busy.value = false }
}
async function cancelLevel(r) {
  const id = r.examId
  if (!id || busy.value) return
  busy.value = true
  try { await portalApi.academicLevelCancel(id); ui.notify('已取消报名'); loadAll() }
  catch (e) { ui.notify(e?.message || '取消失败') } finally { busy.value = false }
}
function toggleSplit(b, o) {
  const key = b.batchId
  const arr = (splitPicks[key] || []).slice()
  const mid = String(o.majorId)
  const i = arr.indexOf(mid)
  if (i >= 0) arr.splice(i, 1)
  else {
    if (arr.length >= (b.maxChoices || 3)) { ui.notify(`最多填 ${b.maxChoices} 个志愿`); return }
    arr.push(mid)
  }
  splitPicks[key] = arr
}
async function submitSplit(b) {
  const choices = splitPicks[b.batchId] || []
  if (!choices.length || busy.value) return
  busy.value = true
  try {
    await portalApi.academicMajorSplitSubmit({ batchId: b.batchId, choices })
    ui.notify('志愿已提交'); loadAll()
  } catch (e) { ui.notify(e?.message || '提交失败') } finally { busy.value = false }
}
async function submitRecognition() {
  if (!canSubmitRecog.value || busy.value) return
  busy.value = true
  try {
    await portalApi.academicRecognitionSubmit({
      sourceCourseName: recogForm.sourceCourseName.trim(),
      sourceScore: Number(recogForm.sourceScore),
      sourceCredit: recogForm.sourceCredit != null && recogForm.sourceCredit !== '' ? Number(recogForm.sourceCredit) : undefined,
      sourceOrigin: recogForm.sourceOrigin.trim() || undefined,
      targetCourseName: recogForm.targetCourseName.trim(),
      reason: recogForm.reason.trim() || undefined,
    })
    ui.notify('认定申请已提交')
    Object.assign(recogForm, {
      sourceCourseName: '', sourceScore: 60, sourceCredit: null, sourceOrigin: '', targetCourseName: '', reason: '',
    })
    loadAll()
  } catch (e) { ui.notify(e?.message || '提交失败') } finally { busy.value = false }
}
async function submitStatusChange() {
  if (!canNextStatusStep.value || busy.value) return
  busy.value = true
  try {
    const payload = {
      changeType: statusForm.changeType,
      reason: statusForm.reason.trim(),
      toMajorId: statusForm.changeType === 'TRANSFER_MAJOR' ? (statusForm.toMajorId || undefined) : undefined,
      toClassId: (statusForm.changeType === 'TRANSFER_MAJOR' || statusForm.changeType === 'TRANSFER_CLASS')
        ? (statusForm.toClassId || undefined) : undefined,
    }
    await portalApi.academicStatusChange(payload)
    const printed = await portalApi.academicStatusChangePrint(payload)
    downloadAcademicHtml('学籍异动申请审批表', printed, buildStatusChangeHtml(printed, payload))
    ui.notify('异动申请已提交，申请表已下载')
    wizStep.value = 1
    statusForm.reason = ''
    statusForm.toMajorId = ''
    statusForm.toClassId = ''
    loadAll()
  } catch (e) { ui.notify(e?.message || '提交失败') } finally { busy.value = false }
}
async function submitExam() {
  busy.value = true
  try {
    const body = { reason: examForm.reason, courseName: examForm.courseName }
    if (examTab.value === '免修申请') await portalApi.academicExemptionApply(body)
    else await portalApi.academicRetakeApply(body)
    ui.notify('申请已提交'); examForm.reason = ''; examForm.courseName = ''; loadAll()
  } catch (e) { ui.notify(e?.message || '提交失败') } finally { busy.value = false }
}
onMounted(loadAll)
</script>

<style scoped>
.sched-grid { display: grid; grid-template-columns: 96px repeat(5, 1fr); gap: 6px; }
.sched-day { text-align: center; font-size: 13px; font-weight: 600; color: var(--t2); padding: 8px 0; }
.sched-time { font-size: 11.5px; color: var(--t4); padding: 10px 6px; white-space: pre-line; line-height: 1.4; }
.sched-cell { min-height: 64px; border-radius: 9px; border: 1px solid #F0F1F3; padding: 8px; }
.sched-course { background: var(--pri-50); border-radius: 7px; padding: 7px 8px; height: 100%; font-size: 12.5px; }
.select-grid { display: grid; grid-template-columns: 1fr 260px; gap: 18px; align-items: start; }
.bar { margin-top: 10px; height: 8px; border-radius: 4px; background: #F0F1F3; overflow: hidden; }
.bar span { display: block; height: 100%; border-radius: 4px; background: var(--pri); }
.mini { all: unset; cursor: pointer; padding: 7px 14px; border-radius: 8px; font-size: 12.5px; font-weight: 600; background: var(--pri); color: #fff; }
.mini:disabled { opacity: .5; cursor: not-allowed; }
.mini--ghost { background: #fff; color: var(--pri); border: 1px solid var(--pri); box-sizing: border-box; }
.two { display: grid; grid-template-columns: 1.3fr 1fr; gap: 18px; align-items: start; }
.tr-preview { border: 1.5px solid #DDE1E8; border-radius: 10px; padding: 24px; position: relative; overflow: hidden; }
.tr-wm { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 44px; font-weight: 700; color: rgba(37,99,235,.05); transform: rotate(-18deg); pointer-events: none; white-space: nowrap; }
.wiz { display: flex; align-items: center; margin-bottom: 22px; }
.wiz__seg { display: flex; align-items: center; flex: 1; }
.wiz__node { display: flex; align-items: center; gap: 8px; flex: none; }
.wiz__c { width: 26px; height: 26px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; background: #fff; border: 2px solid #DDE1E8; color: #A9B0BD; }
.wiz__c.cur { border-color: var(--pri); color: var(--pri); }
.wiz__c.done { background: var(--pri); border-color: var(--pri); color: #fff; }
.wiz__t { font-size: 13px; color: #A9B0BD; white-space: nowrap; }
.wiz__t.on { color: var(--t1); font-weight: 600; }
.wiz__line { flex: 1; height: 2px; margin: 0 10px; }
.typecard { all: unset; box-sizing: border-box; cursor: pointer; width: 170px; padding: 16px; border-radius: 12px; border: 1.5px solid var(--line); background: #fff; }
.typecard.on { border-color: var(--pri); background: var(--pri-50); }
.preview { padding: 16px; border: 1px solid var(--line); border-radius: 10px; max-width: 520px; font-size: 13px; color: var(--t2); line-height: 1.8; }
@media (max-width: 900px) { .select-grid, .two { grid-template-columns: 1fr; } }
</style>
