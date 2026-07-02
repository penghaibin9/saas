const pool = require('../config/db');
const logger = require('../utils/logger');

const DEMO_FLOW = [
  { title: '学校大屏', description: '看全校实习规模、风险、二级学院排名', tag: 'PC' },
  { title: '学生手机端', description: '岗位申请、定位签到、提交周报', tag: 'H5/小程序' },
  { title: '教师手机端', description: '批阅报告、巡访记录、风险提醒', tag: '移动端' },
  { title: '企业端', description: '岗位发布、学生确认、实习评价', tag: '校企协同' },
  { title: '数据报送', description: '导出标准台账、支撑检查与验收', tag: '交付' }
];

const MOCK_RANKING = [
  { collegeName: '示例学院 A', students: 928, inPostRate: 98.2, reportSubmitRate: 95.4, riskAlerts: 3, status: 'excellent' },
  { collegeName: '示例学院 B', students: 816, inPostRate: 97.1, reportSubmitRate: 93.9, riskAlerts: 6, status: 'normal' },
  { collegeName: '示例学院 C', students: 734, inPostRate: 94.6, reportSubmitRate: 90.8, riskAlerts: 11, status: 'warning' },
  { collegeName: '示例学院 D', students: 612, inPostRate: 91.5, reportSubmitRate: 84.3, riskAlerts: 17, status: 'danger' }
];

const MOCK_KPIS = {
  students: 4286,
  inPostStudents: 4149,
  inPostRate: 96.8,
  todayCheckins: 3972,
  checkinRate: 92.7,
  submittedReports: 3995,
  reportSubmitRate: 93.2,
  riskAlerts: 37,
  activePositions: 1248,
  teachers: 318,
  enterprises: 426,
  pendingTeacherTasks: 86
};

const METRIC_DEFINITIONS = {
  students: '当前租户中未删除的学生账号数（role=4）',
  inPostStudents: '存在状态为 3 或 5 的实习申请的去重学生数；当前未按学年或实习计划筛选',
  inPostRate: 'inPostStudents / students',
  todayCheckins: '按服务器当天日期有打卡记录的去重学生数',
  checkinRate: 'todayCheckins / students；当前分母为全部学生账号',
  submittedReports: '历史上存在已提交或已批阅报告（status=1/2）的去重学生数',
  reportSubmitRate: 'submittedReports / students；当前未限定报告周期',
  riskAlerts: '历史全部打卡中 risk_level 非空且不为 none 的记录数；当前未按处置状态去重',
  activePositions: '状态有效且未删除的岗位数',
  teachers: '当前租户中未删除的教师账号数（role=3）',
  enterprises: '当前租户中未删除的企业数',
  pendingTeacherTasks: '状态为待批阅（status=1）且未删除的报告数'
};

function metricContext() {
  return {
    scope: 'current-tenant',
    timezone: process.env.TZ || 'Asia/Shanghai',
    batchYear: null,
    planId: null,
    note: '当前版本为全量租户口径；正式验收前应按学校确认的学年、批次和实习计划配置统计范围。'
  };
}

function demoOverview(source, note, errors = []) {
  return {
    source,
    generatedAt: new Date().toISOString(),
    kpis: { ...MOCK_KPIS },
    metricDefinitions: { ...METRIC_DEFINITIONS },
    metricContext: metricContext(),
    collegeRanking: MOCK_RANKING.map((row) => ({ ...row })),
    demoFlow: DEMO_FLOW.map((item) => ({ ...item })),
    diagnostics: { errors, fallbackUsed: true, note }
  };
}

function collectQueryError(errors, label, err) {
  // 对客户端只暴露稳定错误码，避免数据库结构、主机等内部信息进入响应。
  errors.push({ label, code: 'STAT_QUERY_FAILED' });
  logger.warn('school_readiness_query_failed', {
    metric: label,
    code: err && err.code,
    error: err && err.message
  });
}

function pct(numerator, denominator) {
  const n = Number(numerator || 0);
  const d = Number(denominator || 0);
  if (!d) return 0;
  return Number(((n / d) * 100).toFixed(1));
}

async function scalar(sql, params, fallback, errors, label) {
  try {
    const [[row]] = await pool.read.query(sql, params || []);
    return Number(row && Object.values(row)[0]) || 0;
  } catch (err) {
    collectQueryError(errors, label, err);
    return fallback;
  }
}

async function rows(sql, params, fallback, errors, label) {
  try {
    const [result] = await pool.read.query(sql, params || []);
    return result;
  } catch (err) {
    collectQueryError(errors, label, err);
    return fallback;
  }
}

function statusOf(inPostRate, reportSubmitRate, riskAlerts) {
  if (riskAlerts >= 15 || reportSubmitRate < 85 || inPostRate < 92) return 'danger';
  if (riskAlerts >= 8 || reportSubmitRate < 92 || inPostRate < 95) return 'warning';
  if (inPostRate >= 98 && reportSubmitRate >= 95 && riskAlerts <= 3) return 'excellent';
  return 'normal';
}

async function overview({ preferMockWhenEmpty = false, demoOnly = false } = {}) {
  // 公开演示必须与租户真实数据物理隔离：在任何数据库查询发生前直接返回样例聚合快照。
  if (demoOnly) {
    return demoOverview('mock-public-demo', '公开销售演示固定使用样例聚合数据，不读取学校真实数据。');
  }

  const errors = [];

  const students = await scalar(`SELECT COUNT(*) AS total FROM t_user WHERE role = 4 AND is_deleted = 0`, [], 0, errors, 'students');
  const teachers = await scalar(`SELECT COUNT(*) AS total FROM t_user WHERE role = 3 AND is_deleted = 0`, [], 0, errors, 'teachers');
  const enterprises = await scalar(`SELECT COUNT(*) AS total FROM t_enterprise WHERE is_deleted = 0`, [], 0, errors, 'enterprises');
  const activePositions = await scalar(`SELECT COUNT(*) AS total FROM t_position WHERE status = 1 AND is_deleted = 0`, [], 0, errors, 'activePositions');
  const inPostStudents = await scalar(`SELECT COUNT(DISTINCT student_id) AS total FROM t_application WHERE status IN (3,5) AND is_deleted = 0`, [], 0, errors, 'inPostStudents');
  const todayCheckins = await scalar(`SELECT COUNT(DISTINCT student_id) AS total FROM t_checkin WHERE DATE(checkin_time) = CURDATE()`, [], 0, errors, 'todayCheckins');
  const submittedReports = await scalar(`SELECT COUNT(DISTINCT student_id) AS total FROM t_report WHERE status IN (1,2) AND is_deleted = 0`, [], 0, errors, 'submittedReports');
  const pendingTeacherTasks = await scalar(`SELECT COUNT(*) AS total FROM t_report WHERE status = 1 AND is_deleted = 0`, [], 0, errors, 'pendingTeacherTasks');
  const riskAlerts = await scalar(`SELECT COUNT(*) AS total FROM t_checkin WHERE risk_level IS NOT NULL AND risk_level <> 'none'`, [], 0, errors, 'riskAlerts');

  if (preferMockWhenEmpty && students === 0 && teachers === 0 && enterprises === 0 && activePositions === 0) {
    return demoOverview(
      errors.length ? 'mock-query-fallback' : 'mock-empty-database',
      errors.length ? '统计查询暂不可用，已降级为样例聚合数据。' : '当前数据库为空，返回销售演示数据。',
      errors
    );
  }

  const rankingRows = await rows(
    `SELECT COALESCE(c.name, '未分学院') AS collegeName,
            COUNT(DISTINCT u.id) AS students,
            COUNT(DISTINCT CASE WHEN a.status IN (3,5) THEN u.id END) AS inPostStudents,
            COUNT(DISTINCT CASE WHEN r.status IN (1,2) THEN u.id END) AS submittedStudents,
            COUNT(DISTINCT CASE WHEN ck.risk_level IS NOT NULL AND ck.risk_level <> 'none' THEN ck.id END) AS riskAlerts
     FROM t_user u
     LEFT JOIN t_college c ON u.college_id = c.id
     LEFT JOIN t_application a ON a.student_id = u.id AND a.is_deleted = 0
     LEFT JOIN t_report r ON r.student_id = u.id AND r.is_deleted = 0
     LEFT JOIN t_checkin ck ON ck.student_id = u.id
     WHERE u.role = 4 AND u.is_deleted = 0
     GROUP BY c.id, c.name
     ORDER BY students DESC
     LIMIT 6`, [], [], errors, 'collegeRanking'
  );

  const collegeRanking = rankingRows.map((row) => {
    const studentCount = Number(row.students || 0);
    const inPostRate = row.inPostRate !== undefined ? Number(row.inPostRate) : pct(row.inPostStudents, studentCount);
    const reportSubmitRate = row.reportSubmitRate !== undefined ? Number(row.reportSubmitRate) : pct(row.submittedStudents, studentCount);
    const riskCount = Number(row.riskAlerts || 0);
    return {
      collegeName: row.collegeName || row.college_name || '未分学院',
      students: studentCount,
      inPostRate,
      reportSubmitRate,
      riskAlerts: riskCount,
      status: row.status || statusOf(inPostRate, reportSubmitRate, riskCount)
    };
  });

  return {
    source: errors.length ? 'mixed' : 'database',
    generatedAt: new Date().toISOString(),
    kpis: {
      students,
      inPostStudents,
      inPostRate: pct(inPostStudents, students),
      todayCheckins,
      checkinRate: pct(todayCheckins, students),
      submittedReports,
      reportSubmitRate: pct(submittedReports, students),
      riskAlerts,
      activePositions,
      teachers,
      enterprises,
      pendingTeacherTasks
    },
    metricDefinitions: { ...METRIC_DEFINITIONS },
    metricContext: metricContext(),
    collegeRanking,
    demoFlow: DEMO_FLOW,
    diagnostics: {
      errors,
      fallbackUsed: errors.length > 0,
      note: errors.length ? '部分统计读取失败，已返回其余可用聚合结果。' : '全部统计来自当前租户数据库。'
    }
  };
}

module.exports = { overview, pct };
