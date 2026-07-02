const pool = require('../config/db');
const benchmarkModel = require('./benchmarkModel');

async function count(sql, params) {
  const [[{ c }]] = await pool.query(sql, params);
  return c;
}

const workbenchModel = {
  async teacher(teacherId) {
    const [
      assignedStudents, pendingApplications, pendingLogs, pendingLeaves,
      pendingReports, pendingAchievements, pendingQuality, topicCount,
      pendingAsgChanges, pendingComplaints, pendingAgreements
    ] = await Promise.all([
      count('SELECT COUNT(DISTINCT student_id) AS c FROM t_assignment WHERE teacher_id = ? AND status = 1 AND is_deleted = 0', [teacherId]),
      count('SELECT COUNT(*) AS c FROM t_application WHERE teacher_id = ? AND status = 0 AND is_deleted = 0', [teacherId]),
      count("SELECT COUNT(*) AS c FROM t_intern_log WHERE teacher_id = ? AND status = 1 AND is_deleted = 0", [teacherId]),
      count('SELECT COUNT(*) AS c FROM t_leave WHERE teacher_id = ? AND status = 1 AND is_deleted = 0', [teacherId]),
      count(`SELECT COUNT(*) AS c FROM t_report r JOIN t_application a ON r.application_id = a.id
             WHERE a.teacher_id = ? AND r.status = 1 AND r.is_deleted = 0`, [teacherId]),
      count('SELECT COUNT(*) AS c FROM t_gd_achievement WHERE teacher_id = ? AND status = 0 AND is_deleted = 0', [teacherId]),
      count('SELECT COUNT(*) AS c FROM t_quality_check WHERE checker_id = ? AND status = 0 AND is_deleted = 0', [teacherId]),
      count('SELECT COUNT(*) AS c FROM t_gd_topic WHERE teacher_id = ? AND is_deleted = 0', [teacherId]),
      count(`SELECT COUNT(*) AS c FROM t_assignment_change c
             JOIN t_assignment a ON c.assignment_id = a.id
             WHERE c.status = 0 AND c.is_deleted = 0 AND a.teacher_id = ?`, [teacherId]),
      count(`SELECT COUNT(*) AS c FROM t_complaint c
             JOIN t_assignment a ON c.student_id = a.student_id AND a.teacher_id = ? AND a.status = 1 AND a.is_deleted = 0
             WHERE c.status IN (0,1) AND c.is_deleted = 0`, [teacherId]),
      count(`SELECT COUNT(*) AS c FROM t_agreement ag
             JOIN t_assignment a ON ag.student_id = a.student_id AND a.teacher_id = ? AND a.status = 1
             WHERE ag.student_signed = 1 AND (ag.teacher_signed = 0 OR ag.teacher_signed IS NULL)
               AND ag.status NOT IN (2,3) AND ag.is_deleted = 0`, [teacherId])
    ]);
    const pending = {
      applications: pendingApplications,
      internLogs: pendingLogs,
      leaves: pendingLeaves,
      reports: pendingReports,
      achievements: pendingAchievements,
      qualityChecks: pendingQuality,
      asgChanges: pendingAsgChanges,
      complaints: pendingComplaints,
      agreements: pendingAgreements,
      total: pendingApplications + pendingLogs + pendingLeaves + pendingReports +
        pendingAchievements + pendingQuality + pendingAsgChanges + pendingComplaints + pendingAgreements
    };
    const benchmark = await benchmarkModel.teacherFlowPending(teacherId).catch(() => ({}));
    pending.total += (benchmark.parentConsentPending || 0) + (benchmark.appraisalPending || 0);
    return { assignedStudents, topicCount, pending, benchmark };
  },

  async student(studentId) {
    const [aRows] = await pool.query(
      `SELECT a.id, a.teacher_id, a.enterprise_id, e.name AS enterprise_name, t.real_name AS teacher_name,
              p.checkin_count AS req_checkin, p.weekly_count AS req_weekly, p.monthly_count AS req_monthly,
              p.title AS plan_title
       FROM t_assignment a
       LEFT JOIN t_enterprise e ON a.enterprise_id = e.id
       LEFT JOIN t_user t ON a.teacher_id = t.id
       LEFT JOIN t_intern_plan p ON a.plan_id = p.id
       WHERE a.student_id = ? AND a.status = 1 AND a.is_deleted = 0
       ORDER BY a.create_time DESC LIMIT 1`, [studentId]
    );
    const assignment = aRows[0] || null;

    const [
      checkinCount, weeklyCount, monthlyCount, pendingLeaves,
      unsignedAgreements, asgChangePending, insuranceWarn
    ] = await Promise.all([
      count('SELECT COUNT(*) AS c FROM t_checkin WHERE student_id = ?', [studentId]),
      count("SELECT COUNT(*) AS c FROM t_intern_log WHERE student_id = ? AND type = 'weekly' AND status IN (1,2) AND is_deleted = 0", [studentId]),
      count("SELECT COUNT(*) AS c FROM t_intern_log WHERE student_id = ? AND type = 'monthly' AND status IN (1,2) AND is_deleted = 0", [studentId]),
      count('SELECT COUNT(*) AS c FROM t_leave WHERE student_id = ? AND status = 1 AND is_deleted = 0', [studentId]),
      count(`SELECT COUNT(*) AS c FROM t_agreement WHERE student_id = ? AND (student_signed = 0 OR student_signed IS NULL)
             AND status NOT IN (2,3) AND is_deleted = 0`, [studentId]),
      count('SELECT COUNT(*) AS c FROM t_assignment_change WHERE student_id = ? AND status IN (0,1) AND is_deleted = 0', [studentId]),
      count(`SELECT COUNT(*) AS c FROM t_insurance WHERE student_id = ? AND is_deleted = 0
             AND end_date IS NOT NULL AND end_date <= DATE_ADD(CURDATE(), INTERVAL 30 DAY)`, [studentId])
    ]);

    const [[checkedToday]] = await pool.query(
      'SELECT COUNT(*) AS c FROM t_checkin WHERE student_id = ? AND DATE(checkin_time) = CURDATE()', [studentId]);
    const [gradeRows] = await pool.query(
      'SELECT review_score, defense_score, total_score FROM t_gd_grade WHERE student_id = ? AND is_deleted = 0 LIMIT 1', [studentId]
    );
    const [asgRow] = await pool.query(
      `SELECT id, change_type, status FROM t_assignment_change WHERE student_id = ? AND status IN (0,1) AND is_deleted = 0
       ORDER BY create_time DESC LIMIT 1`, [studentId]
    );
    const [topicRows] = await pool.query(
      `SELECT id, title, status, teacher_id FROM t_gd_topic WHERE student_id = ? AND is_deleted = 0
       ORDER BY create_time DESC LIMIT 1`, [studentId]
    );
    const [
      achievementCount, achievementNeedAction, achievementPending, guidanceCount, qualityPending
    ] = await Promise.all([
      count('SELECT COUNT(*) AS c FROM t_gd_achievement WHERE student_id = ? AND is_deleted = 0', [studentId]),
      count('SELECT COUNT(*) AS c FROM t_gd_achievement WHERE student_id = ? AND status IN (2,3) AND is_deleted = 0', [studentId]),
      count('SELECT COUNT(*) AS c FROM t_gd_achievement WHERE student_id = ? AND status = 0 AND is_deleted = 0', [studentId]),
      count('SELECT COUNT(*) AS c FROM t_gd_guidance WHERE student_id = ? AND is_deleted = 0', [studentId]),
      count('SELECT COUNT(*) AS c FROM t_quality_check WHERE student_id = ? AND status = 0 AND is_deleted = 0', [studentId])
    ]);
    const gdTopic = topicRows[0] || null;
    const benchmark = await benchmarkModel.studentFlowStatus(studentId).catch(() => ({}));

    return {
      assignment,
      progress: {
        checkinCount, reqCheckin: assignment ? (assignment.req_checkin || 0) : 0,
        weeklyCount, reqWeekly: assignment ? (assignment.req_weekly || 0) : 0,
        monthlyCount, reqMonthly: assignment ? (assignment.req_monthly || 0) : 0,
        checkedToday: checkedToday.c > 0
      },
      pending: {
        leaves: pendingLeaves,
        unsignedAgreements,
        asgChange: asgChangePending,
        insuranceWarn
      },
      asgChangeActive: asgRow[0] || null,
      grade: gradeRows[0] || null,
      gd: {
        topic: gdTopic,
        topicPendingConfirm: !!(gdTopic && gdTopic.status === 0),
        achievementCount,
        achievementNeedAction,
        achievementPending,
        guidanceCount,
        qualityPending,
        hasGrade: !!gradeRows[0]
      },
      benchmark
    };
  },

  /** 院校/分院管理员待办聚合 */
  async admin(collegeId) {
    const colEnt = collegeId ? ' AND s.college_id = ?' : '';
    const colAsg = collegeId ? ' AND st.college_id = ?' : '';
    const colFil = collegeId ? ' AND s.college_id = ?' : '';
    const colCp = collegeId ? ' AND c.college_id = ?' : '';
    const p = collegeId ? [collegeId] : [];

    const [
      entAudit, posAudit, complaintsPending, asgAdminReview, filingPending, insuranceWarn
    ] = await Promise.all([
      count(`SELECT COUNT(*) AS c FROM t_enterprise WHERE audit_status = 0 AND is_deleted = 0`),
      count(`SELECT COUNT(*) AS c FROM t_position WHERE status = 0 AND is_deleted = 0`),
      count(`SELECT COUNT(*) AS c FROM t_complaint c WHERE c.status = 0 AND c.is_deleted = 0${colCp}`, p),
      count(`SELECT COUNT(*) AS c FROM t_assignment_change c
             JOIN t_user st ON c.student_id = st.id
             WHERE c.status = 1 AND c.is_deleted = 0${colAsg}`, p),
      count(`SELECT COUNT(*) AS c FROM t_filing_record f
             JOIN t_user s ON f.student_id = s.id
             WHERE f.status IN (0,1) AND f.is_deleted = 0${colFil}`, p),
      count(`SELECT COUNT(*) AS c FROM t_insurance i
             JOIN t_user s ON i.student_id = s.id
             WHERE i.is_deleted = 0 AND i.end_date IS NOT NULL AND i.end_date <= DATE_ADD(CURDATE(), INTERVAL 30 DAY)${colEnt}`, p)
    ]);

    return {
      pending: { entAudit, posAudit, complaintsPending, asgAdminReview, filingPending, insuranceWarn,
        total: entAudit + posAudit + complaintsPending + asgAdminReview + filingPending + insuranceWarn }
    };
  },

  /** 构建流程待办提醒（前端跳转用） */
  buildAlerts(role, data, labels = {}) {
    const L = (k, d) => labels[k] || d;
    const alerts = [];
    const p = data.pending || {};

    if (role === 3) {
      if (p.applications) alerts.push({ key: 'reviewhub', nav: '待批阅中心', title: L('application_review', '待审实习申请'), desc: `${p.applications} 份`, level: 'info' });
      if (p.internLogs) alerts.push({ key: 'reviewhub', nav: '待批阅中心', title: L('intern_log_review', '待批周报/月报'), desc: `${p.internLogs} 份`, level: 'warning' });
      if (p.asgChanges) alerts.push({ key: 'reviewhub', nav: '待批阅中心', title: L('assignment_change_teacher', '换岗/终止待审'), desc: `${p.asgChanges} 条`, level: 'warning' });
      if (p.complaints) alerts.push({ key: 'riskcomplaint', nav: '风险与投诉', title: L('complaint_handle', '本组投诉待处理'), desc: `${p.complaints} 条`, level: 'error' });
      if (p.agreements) alerts.push({ key: 'reviewhub', nav: '待批阅中心', title: L('agreement_sign', '协议待会签'), desc: `${p.agreements} 份`, level: 'info' });
      if (p.leaves) alerts.push({ key: 'reviewhub', nav: '待批阅中心', title: L('leave_review', '待批请假'), desc: `${p.leaves} 条`, level: 'info' });
      const tbm = data.benchmark || {};
      if (tbm.parentConsentPending) alerts.push({ key: 'parentconsent', nav: '家长知情书', title: '家长知情待审', desc: `${tbm.parentConsentPending} 份`, level: 'warning' });
      if (tbm.appraisalPending) alerts.push({ key: 'appraisal', nav: '实习鉴定表', title: '鉴定表待审', desc: `${tbm.appraisalPending} 份`, level: 'warning' });
      if (tbm.taskBookMissing) alerts.push({ key: 'taskbook', nav: '任务书', title: '未下达任务书', desc: `${tbm.taskBookMissing} 人`, level: 'info' });
    } else if (role === 4) {
      const pd = data.pending || {};
      if (pd.unsignedAgreements) alerts.push({ key: 'agreements', nav: '实习协议', title: '待签署协议', desc: `${pd.unsignedAgreements} 份`, level: 'warning' });
      if (data.asgChangeActive) {
        const st = { 0: '待教师审批', 1: '待管理员审批' };
        alerts.push({ key: 'asgchange', nav: '换岗/终止', title: '换岗/终止申请进行中', desc: st[data.asgChangeActive.status] || '', level: 'info' });
      }
      if (pd.insuranceWarn) alerts.push({ key: 'insurancehub', nav: '保险管理', title: '保险即将到期', desc: `${pd.insuranceWarn} 份`, level: 'warning' });
      if (!data.progress?.checkedToday && data.assignment) alerts.push({ key: 'checkins', nav: '打卡签到', title: '今日尚未打卡', desc: data.assignment.enterprise_name || '', level: 'info' });
      const gd = data.gd || {};
      if (gd.topicPendingConfirm) alerts.push({ key: 'gd-home', nav: '毕设工作台', title: '选题待确认', desc: (gd.topic && gd.topic.title) || '请尽快确认选题', level: 'warning' });
      if (gd.achievementNeedAction) alerts.push({ key: 'gd-achievements', nav: '设计成果', title: '成果需修改重交', desc: `${gd.achievementNeedAction} 份待处理`, level: 'warning' });
      else if (gd.topic && gd.topic.status === 2 && !gd.achievementCount) alerts.push({ key: 'gd-achievements', nav: '设计成果', title: '尚未提交设计成果', desc: '请上传论文/设计文档', level: 'info' });
      if (gd.qualityPending) alerts.push({ key: 'quality', nav: '质量监控/互查', title: '质量检查待反馈', desc: `${gd.qualityPending} 项`, level: 'info' });
      const bm = data.benchmark || {};
      if (bm.taskBook === 'pending_confirm') alerts.push({ key: 'taskbook', nav: '任务书', title: '任务书待确认', desc: '请阅读并确认', level: 'warning' });
      if (bm.taskBook === 'missing') alerts.push({ key: 'taskbook', nav: '任务书', title: '任务书未下达', desc: '等待指导教师', level: 'info' });
      if (bm.topicRound && !bm.topicChoiceSubmitted) alerts.push({ key: 'topicround', nav: '选题互选', title: '选题互选进行中', desc: bm.topicRound.name || '请提交志愿', level: 'warning' });
      if (bm.parentConsent === 'missing' || bm.parentConsent === 'rejected') alerts.push({ key: 'parentconsent', nav: '家长知情书', title: '家长知情书', desc: bm.parentConsent === 'rejected' ? '已驳回，请重传' : '待上传', level: 'warning' });
      if (bm.appraisal === 'missing' || bm.appraisal === 'rejected') alerts.push({ key: 'appraisal', nav: '实习鉴定表', title: '实习鉴定表', desc: bm.appraisal === 'rejected' ? '已驳回' : '待上传', level: 'warning' });
      if (data.assignment && bm.internScore === 'none') alerts.push({ key: 'internscore', nav: '实习考评', title: '实习考评未核算', desc: '完成打卡/周报后可核算', level: 'info' });
      if (gd.achievementCount && !bm.plagiarismDone) alerts.push({ key: 'plagiarism', nav: '查重检测', title: '成果待查重', desc: '提交查重检测', level: 'info' });
    } else if (role === 1 || role === 2) {
      if (p.entAudit) alerts.push({ key: 'entpos', nav: '单位与岗位', title: L('enterprise_audit', '企业入驻待审'), desc: `${p.entAudit} 家`, level: 'warning' });
      if (p.posAudit) alerts.push({ key: 'entpos', nav: '单位与岗位', title: L('position_audit', '岗位待审上架'), desc: `${p.posAudit} 个`, level: 'warning' });
      if (p.complaintsPending) alerts.push({ key: 'riskcomplaint', nav: '风险与投诉', title: L('complaint_handle', '投诉待处理'), desc: `${p.complaintsPending} 条`, level: 'error' });
      if (p.asgAdminReview) alerts.push({ key: 'asgchange', nav: '换岗/终止', title: L('assignment_change_admin', '换岗/终止待终审'), desc: `${p.asgAdminReview} 条`, level: 'warning' });
      if (p.filingPending) alerts.push({ key: 'filinghub', nav: '备案与报告', title: L('filing_submit', '备案待提交'), desc: `${p.filingPending} 条`, level: 'info' });
      if (p.insuranceWarn) alerts.push({ key: 'insurancehub', nav: '保险管理', title: '保险到期预警', desc: `${p.insuranceWarn} 人`, level: 'warning' });
    }
    return alerts;
  }
};

module.exports = workbenchModel;
