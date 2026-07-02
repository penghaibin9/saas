const pool = require('../config/db');

// 实习质量报告：聚合多维统计，供一键生成报告。collegeId 可选（分院维度）。
const qualityReportModel = {
  async generate({ collegeId } = {}) {
    const cFilter = collegeId !== undefined ? ' AND s.college_id = ?' : '';
    const cParam = collegeId !== undefined ? [collegeId] : [];

    // 在岗学生数（有效实习分配）
    const [[{ students }]] = await pool.query(
      `SELECT COUNT(DISTINCT a.student_id) AS students FROM t_assignment a
       JOIN t_user s ON a.student_id = s.id
       WHERE a.status = 1 AND a.is_deleted = 0 ${cFilter}`, cParam
    );

    // 打卡：总数 / 在范围数 / 今日
    const [[ck]] = await pool.query(
      `SELECT COUNT(*) AS total,
              SUM(CASE WHEN ck.within_range = 1 THEN 1 ELSE 0 END) AS in_range,
              SUM(CASE WHEN DATE(ck.checkin_time) = CURDATE() THEN 1 ELSE 0 END) AS today,
              SUM(CASE WHEN ck.photo_url IS NOT NULL THEN 1 ELSE 0 END) AS with_photo
       FROM t_checkin ck JOIN t_user s ON ck.student_id = s.id WHERE 1=1 ${cFilter}`, cParam
    );

    // 周报/月报提交
    const [[logs]] = await pool.query(
      `SELECT
         SUM(CASE WHEN l.type='weekly'  AND l.status IN (1,2) THEN 1 ELSE 0 END) AS weekly_submitted,
         SUM(CASE WHEN l.type='monthly' AND l.status IN (1,2) THEN 1 ELSE 0 END) AS monthly_submitted,
         SUM(CASE WHEN l.status = 2 THEN 1 ELSE 0 END) AS passed
       FROM t_intern_log l JOIN t_user s ON l.student_id = s.id WHERE l.is_deleted = 0 ${cFilter}`, cParam
    );

    // 请假
    const [[leaves]] = await pool.query(
      `SELECT COUNT(*) AS total, SUM(CASE WHEN l.status = 2 THEN 1 ELSE 0 END) AS approved
       FROM t_leave l JOIN t_user s ON l.student_id = s.id WHERE 1=1 ${cFilter}`, cParam
    ).catch(() => [[{ total: 0, approved: 0 }]]);

    // 电子协议
    const agFilter = collegeId !== undefined ? ' AND college_id = ?' : '';
    const [[agreements]] = await pool.query(
      `SELECT COUNT(*) AS total, SUM(CASE WHEN status = 2 THEN 1 ELSE 0 END) AS effective
       FROM t_agreement WHERE is_deleted = 0 ${agFilter}`, cParam
    );

    // 企业导师评价
    const [[evals]] = await pool.query(
      `SELECT COUNT(*) AS total, SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END) AS submitted,
              ROUND(AVG(score_overall), 2) AS avg_overall
       FROM t_enterprise_eval WHERE is_deleted = 0 ${agFilter}`, cParam
    );

    // 答辩与推优
    const [[defense]] = await pool.query(
      `SELECT
         (SELECT COUNT(*) FROM t_defense_group g WHERE g.is_deleted = 0 ${collegeId !== undefined ? 'AND g.college_id = ?' : ''}) AS group_count,
         (SELECT COUNT(*) FROM t_defense_member m JOIN t_user s ON m.student_id = s.id WHERE m.recommended = 1 AND m.is_deleted = 0 ${cFilter}) AS recommended`,
      collegeId !== undefined ? [collegeId, collegeId] : []
    );

    const rate = (n, d) => d > 0 ? Math.round((n / d) * 100) : 0;
    return {
      generated_at: new Date().toISOString(),
      scope: collegeId !== undefined ? '本学院' : '全校',
      students,
      checkin: {
        total: ck.total || 0, in_range: ck.in_range || 0, today: ck.today || 0, with_photo: ck.with_photo || 0,
        in_range_rate: rate(ck.in_range || 0, ck.total || 0), photo_rate: rate(ck.with_photo || 0, ck.total || 0)
      },
      logs: { weekly_submitted: logs.weekly_submitted || 0, monthly_submitted: logs.monthly_submitted || 0, passed: logs.passed || 0 },
      leaves: { total: leaves.total || 0, approved: leaves.approved || 0 },
      agreements: { total: agreements.total || 0, effective: agreements.effective || 0, effective_rate: rate(agreements.effective || 0, agreements.total || 0) },
      enterprise_eval: { total: evals.total || 0, submitted: evals.submitted || 0, avg_overall: evals.avg_overall || 0, submit_rate: rate(evals.submitted || 0, evals.total || 0) },
      defense: { groups: defense.group_count || 0, recommended: defense.recommended || 0 }
    };
  }
};

module.exports = qualityReportModel;
