const pool = require('../config/db');
const XLSX = require('xlsx');

const DOC_TYPES = ['proposal', 'midterm', 'draft', 'final', 'other'];
const DOC_LABELS = { proposal: '开题报告', midterm: '中期检查', draft: '论文初稿', final: '论文定稿', other: '其他成果' };

function toMysqlDatetime(v) {
  if (!v) return null;
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString().slice(0, 19).replace('T', ' ');
}

const benchmarkModel = {
  DOC_TYPES,
  DOC_LABELS,

  /* ---------- 纯函数：可独立单元测试，不依赖数据库 ---------- */

  /**
   * 选题互选匹配（纯函数）。
   * @param {Array<{id:number, student_id:number, pool_id:number, priority:number}>} choices 学生志愿
   * @param {Object<number, number>} remainingByPool 各课题剩余名额 { poolId: remaining }
   * @returns {Array} 录取的志愿对象（按录取顺序）。保证：一人最多录取一次；不超过各课题剩余名额。
   */
  planTopicMatches(choices, remainingByPool = {}) {
    const remain = { ...remainingByPool };
    const ordered = (choices || []).slice().sort((a, b) => (a.priority - b.priority) || (a.id - b.id));
    const assigned = new Set();
    const winners = [];
    for (const c of ordered) {
      if (assigned.has(c.student_id)) continue;
      if (!(remain[c.pool_id] > 0)) continue;
      remain[c.pool_id] -= 1;
      assigned.add(c.student_id);
      winners.push(c);
    }
    return winners;
  },

  /**
   * 实习综合考评加权（纯函数）。缺失分项不参与、按已到位分项权重折算。
   * @param {Array<{key:string, score:number|null, weight:number}>} components
   * @returns {{total:number|null, missing:string[], incomplete:0|1}}
   */
  scoreInternComponents(components) {
    const list = components || [];
    const present = list.filter(c => c.score != null && c.weight > 0);
    const missing = list.filter(c => c.score == null).map(c => c.key);
    const presentWeight = present.reduce((s, c) => s + c.weight, 0);
    const total = presentWeight > 0
      ? Math.round(present.reduce((s, c) => s + c.score * c.weight, 0) / presentWeight)
      : null;
    return { total, missing, incomplete: missing.length > 0 ? 1 : 0 };
  },

  async ensureTables() {
    await this.reconcileTeacherVisitTable();
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_gd_task_book (
        id INT AUTO_INCREMENT PRIMARY KEY,
        student_id INT NOT NULL, topic_id INT NULL, teacher_id INT NULL,
        title VARCHAR(200) NOT NULL, content TEXT NULL, file_url VARCHAR(255) NULL,
        status TINYINT DEFAULT 0 COMMENT '0待学生确认1已确认',
        student_confirmed TINYINT DEFAULT 0, confirm_time DATETIME NULL,
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uniq_student (student_id),
        INDEX idx_teacher (teacher_id)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='毕设任务书'
    `);
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_parent_consent (
        id INT AUTO_INCREMENT PRIMARY KEY,
        student_id INT NOT NULL, assignment_id INT NULL,
        file_url VARCHAR(255) NOT NULL, status TINYINT DEFAULT 0 COMMENT '0待审1通过2驳回',
        reject_reason VARCHAR(255) NULL, reviewer_id INT NULL, review_time DATETIME NULL,
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_student (student_id), INDEX idx_status (status)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='家长知情同意书'
    `);
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_intern_appraisal (
        id INT AUTO_INCREMENT PRIMARY KEY,
        student_id INT NOT NULL, assignment_id INT NULL,
        file_url VARCHAR(255) NOT NULL, enterprise_comment VARCHAR(500) NULL,
        status TINYINT DEFAULT 0 COMMENT '0待审1通过2驳回',
        reject_reason VARCHAR(255) NULL,
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uniq_student (student_id)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='实习鉴定表'
    `);
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_teacher_visit (
        id INT AUTO_INCREMENT PRIMARY KEY,
        teacher_id INT NOT NULL, student_id INT NOT NULL, assignment_id INT NULL,
        visit_date DATE NOT NULL, location VARCHAR(200) NULL, content TEXT NULL,
        photo_url VARCHAR(255) NULL, problems TEXT NULL,
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_teacher (teacher_id), INDEX idx_student (student_id)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='教师巡访记录'
    `);
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_employment_destination (
        id INT AUTO_INCREMENT PRIMARY KEY,
        student_id INT NOT NULL,
        dest_type VARCHAR(20) NOT NULL COMMENT 'employment|study|other',
        company_name VARCHAR(200) NULL, position_title VARCHAR(100) NULL,
        city VARCHAR(50) NULL, salary_range VARCHAR(50) NULL, remark TEXT NULL,
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uniq_student (student_id)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='就业去向'
    `);
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_intern_alternative (
        id INT AUTO_INCREMENT PRIMARY KEY,
        student_id INT NOT NULL,
        alt_type VARCHAR(20) NOT NULL COMMENT 'exempt|study|business|military|other',
        reason TEXT NOT NULL, file_url VARCHAR(255) NULL,
        status TINYINT DEFAULT 0 COMMENT '0待审1通过2驳回',
        reviewer_id INT NULL, review_remark VARCHAR(255) NULL, review_time DATETIME NULL,
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_student (student_id), INDEX idx_status (status)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='免实习/其他去向'
    `);
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_gd_topic_pool (
        id INT AUTO_INCREMENT PRIMARY KEY,
        teacher_id INT NOT NULL, college_id INT NULL,
        title VARCHAR(200) NOT NULL, type VARCHAR(50) NULL, source VARCHAR(50) NULL,
        description TEXT NULL, quota INT DEFAULT 1, chosen_count INT DEFAULT 0,
        status TINYINT DEFAULT 1 COMMENT '0下架1发布',
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_teacher (teacher_id)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='毕设课题池'
    `);
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_gd_topic_round (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL, max_choices INT DEFAULT 3,
        status TINYINT DEFAULT 0 COMMENT '0未开始1进行中2已结束',
        start_time DATETIME NULL, end_time DATETIME NULL,
        college_id INT NULL, is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='选题互选轮次'
    `);
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_gd_topic_choice (
        id INT AUTO_INCREMENT PRIMARY KEY,
        round_id INT NOT NULL, student_id INT NOT NULL,
        pool_id INT NOT NULL, priority INT DEFAULT 1,
        status TINYINT DEFAULT 0 COMMENT '0待处理1已匹配2未匹配',
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_round (round_id), INDEX idx_student (student_id)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='学生选题志愿'
    `);
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_intern_score_config (
        id INT AUTO_INCREMENT PRIMARY KEY,
        college_id INT NULL,
        checkin_weight DECIMAL(5,2) DEFAULT 20,
        weekly_weight DECIMAL(5,2) DEFAULT 20,
        monthly_weight DECIMAL(5,2) DEFAULT 10,
        enterprise_weight DECIMAL(5,2) DEFAULT 30,
        school_weight DECIMAL(5,2) DEFAULT 20,
        pass_line DECIMAL(5,2) DEFAULT 60,
        is_deleted TINYINT DEFAULT 0,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uniq_college (college_id)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='实习成绩权重'
    `);
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_intern_final_score (
        id INT AUTO_INCREMENT PRIMARY KEY,
        student_id INT NOT NULL, assignment_id INT NULL,
        checkin_score DECIMAL(5,2) NULL, log_score DECIMAL(5,2) NULL,
        enterprise_score DECIMAL(5,2) NULL, school_score DECIMAL(5,2) NULL,
        total_score DECIMAL(5,2) NULL, published TINYINT DEFAULT 0,
        remark VARCHAR(255) NULL, is_deleted TINYINT DEFAULT 0,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uniq_student (student_id)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='实习综合考评'
    `);
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_gd_plagiarism (
        id INT AUTO_INCREMENT PRIMARY KEY,
        student_id INT NOT NULL, achievement_id INT NOT NULL,
        similarity DECIMAL(5,2) NULL, aigc_rate DECIMAL(5,2) NULL,
        status TINYINT DEFAULT 0 COMMENT '0检测中1完成2失败',
        report_url VARCHAR(255) NULL, is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_achievement (achievement_id)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='查重/AIGC(演示)'
    `);
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_checkin_points (
        student_id INT PRIMARY KEY,
        points INT DEFAULT 0, streak_days INT DEFAULT 0,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='签到积分'
    `);
    await pool.query(`INSERT IGNORE INTO t_intern_score_config (college_id, checkin_weight, weekly_weight, monthly_weight, enterprise_weight, school_weight, pass_line) VALUES (NULL, 20, 20, 10, 30, 20, 60)`);
    await this.ensureColumns();
    console.log('✅ benchmark tables');
  },

  /** 给既有表补充 benchmark 依赖的列（幂等），使启动即可自愈，无需单独跑迁移脚本 */
  async ensureColumns() {
    const addColumn = async (table, col, ddl) => {
      const [rows] = await pool.query(
        `SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=? AND COLUMN_NAME=?`,
        [table, col]);
      if (!rows.length) await pool.query(`ALTER TABLE ${table} ADD COLUMN ${col} ${ddl}`);
    };
    const [[t]] = await pool.query(
      `SELECT COUNT(*) AS c FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='t_checkin'`);
    if (t.c) {
      await addColumn('t_checkin', 'is_makeup', 'TINYINT DEFAULT 0');
      await addColumn('t_checkin', 'makeup_status', 'TINYINT NULL COMMENT "0待审1通过2驳回"');
      await addColumn('t_checkin', 'makeup_reason', 'VARCHAR(255) NULL');
      await addColumn('t_checkin', 'slot', "VARCHAR(10) DEFAULT 'day' COMMENT 'day全天/am上班/pm下班'");
    }
    const [[g]] = await pool.query(
      `SELECT COUNT(*) AS c FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='t_gd_achievement'`);
    if (g.c) {
      await addColumn('t_gd_achievement', 'doc_type', "VARCHAR(20) DEFAULT 'other' COMMENT 'proposal|midterm|draft|final|other'");
      await addColumn('t_gd_achievement', 'version', 'INT DEFAULT 1');
      await addColumn('t_gd_achievement', 'review_comment', 'VARCHAR(500) NULL COMMENT "教师过程批注"');
    }
    const [[gr]] = await pool.query(
      `SELECT COUNT(*) AS c FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='t_gd_grade'`);
    if (gr.c) {
      await addColumn('t_gd_grade', 'published', 'TINYINT DEFAULT 0');
      await addColumn('t_gd_grade', 'review_teacher_id', 'INT NULL');
      await addColumn('t_gd_grade', 'review_score_2', 'DECIMAL(5,2) NULL COMMENT "双评"');
      await addColumn('t_gd_grade', 'blind_review', 'TINYINT DEFAULT 0');
    }
    // 查重记录：标记数据来源与是否演示，避免"假功能冒充真功能"
    await addColumn('t_gd_plagiarism', 'provider', "VARCHAR(20) DEFAULT 'demo'");
    await addColumn('t_gd_plagiarism', 'is_demo', 'TINYINT DEFAULT 1');
    // 实习综合考评：记录各分项是否到位 + 校内评分录入人
    await addColumn('t_intern_final_score', 'school_scored_by', 'INT NULL COMMENT "校内评分录入教师"');
    await addColumn('t_intern_final_score', 'incomplete', 'TINYINT DEFAULT 0 COMMENT "1=存在缺失分项,总分待补"');
    const [[cl]] = await pool.query(
      `SELECT COUNT(*) AS c FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='t_class'`);
    if (cl.c) {
      await addColumn('t_class', 'head_teacher_id', 'INT NULL COMMENT "班主任"');
    }
  },

  /** 旧版 t_teacher_visit 与商用巡访表结构冲突时迁移 */
  async reconcileTeacherVisitTable() {
    const [tables] = await pool.query(
      `SELECT 1 FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='t_teacher_visit'`
    );
    if (!tables.length) return;
    const [cols] = await pool.query(
      `SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='t_teacher_visit'`
    );
    const names = new Set(cols.map(c => c.COLUMN_NAME));
    if (names.has('visit_date') && names.has('assignment_id')) return;
    const legacy = 't_teacher_visit_legacy_' + Date.now();
    await pool.query(`RENAME TABLE t_teacher_visit TO ${legacy}`);
    console.log(`↪ 已迁移旧表 t_teacher_visit → ${legacy}`);
  },

  async studentFlowStatus(studentId) {
    const [[tb]] = await pool.query(
      'SELECT id, student_confirmed FROM t_gd_task_book WHERE student_id=? AND is_deleted=0 LIMIT 1', [studentId]);
    const [[pc]] = await pool.query(
      'SELECT id, status FROM t_parent_consent WHERE student_id=? AND is_deleted=0 ORDER BY id DESC LIMIT 1', [studentId]);
    const [[ap]] = await pool.query(
      'SELECT id, status FROM t_intern_appraisal WHERE student_id=? AND is_deleted=0 LIMIT 1', [studentId]);
    const [[emp]] = await pool.query(
      'SELECT id FROM t_employment_destination WHERE student_id=? AND is_deleted=0 LIMIT 1', [studentId]);
    const [[score]] = await pool.query(
      'SELECT total_score, published FROM t_intern_final_score WHERE student_id=? AND is_deleted=0 LIMIT 1', [studentId]);
    const [rounds] = await pool.query(
      'SELECT id, name FROM t_gd_topic_round WHERE status=1 AND is_deleted=0 ORDER BY id DESC LIMIT 1');
    const [[choice]] = rounds.length ? await pool.query(
      'SELECT id FROM t_gd_topic_choice WHERE round_id=? AND student_id=? AND is_deleted=0 LIMIT 1',
      [rounds[0].id, studentId]) : [[null]];
    const [[plag]] = await pool.query(
      `SELECT p.id FROM t_gd_plagiarism p JOIN t_gd_achievement a ON p.achievement_id=a.id
       WHERE a.student_id=? AND p.is_deleted=0 AND a.is_deleted=0 LIMIT 1`, [studentId]);
    return {
      taskBook: tb ? (tb.student_confirmed ? 'confirmed' : 'pending_confirm') : 'missing',
      parentConsent: !pc ? 'missing' : (pc.status === 1 ? 'approved' : pc.status === 2 ? 'rejected' : 'pending'),
      appraisal: !ap ? 'missing' : (ap.status === 1 ? 'approved' : ap.status === 2 ? 'rejected' : 'pending'),
      employment: emp ? 'filled' : 'missing',
      internScore: !score ? 'none' : (score.published ? 'published' : 'computed'),
      topicRound: rounds[0] || null,
      topicChoiceSubmitted: !!choice,
      plagiarismDone: !!plag
    };
  },

  async teacherFlowPending(teacherId) {
    const [parentPending] = await pool.query(
      `SELECT COUNT(*) AS c FROM t_parent_consent pc
       JOIN t_assignment a ON pc.student_id=a.student_id AND a.teacher_id=? AND a.status=1
       WHERE pc.status=0 AND pc.is_deleted=0`, [teacherId]);
    const [appraisalPending] = await pool.query(
      `SELECT COUNT(*) AS c FROM t_intern_appraisal ia
       JOIN t_assignment a ON ia.student_id=a.student_id AND a.teacher_id=? AND a.status=1
       WHERE ia.status=0 AND ia.is_deleted=0`, [teacherId]);
    const [noTaskBook] = await pool.query(
      `SELECT COUNT(*) AS c FROM t_assignment a
       LEFT JOIN t_gd_task_book tb ON tb.student_id=a.student_id AND tb.is_deleted=0
       WHERE a.teacher_id=? AND a.status=1 AND a.is_deleted=0 AND tb.id IS NULL`, [teacherId]);
    return {
      parentConsentPending: parentPending[0].c,
      appraisalPending: appraisalPending[0].c,
      taskBookMissing: noTaskBook[0].c
    };
  },

  /* ---------- 任务书 ---------- */
  async listTaskBooks(filter = {}, { page = 1, pageSize = 20 } = {}) {
    let w = 'WHERE tb.is_deleted = 0';
    const p = [];
    if (filter.studentId) { w += ' AND tb.student_id = ?'; p.push(filter.studentId); }
    if (filter.teacherId) { w += ' AND tb.teacher_id = ?'; p.push(filter.teacherId); }
    if (filter.collegeId) { w += ' AND s.college_id = ?'; p.push(filter.collegeId); }
    const offset = (page - 1) * pageSize;
    const [[{ total }]] = await pool.query(`SELECT COUNT(*) AS total FROM t_gd_task_book tb LEFT JOIN t_user s ON tb.student_id=s.id ${w}`, p);
    const [rows] = await pool.query(
      `SELECT tb.*, s.real_name AS student_name, s.eeid AS student_eeid,
              s.college_id AS student_college_id, t.real_name AS teacher_name
       FROM t_gd_task_book tb LEFT JOIN t_user s ON tb.student_id=s.id LEFT JOIN t_user t ON tb.teacher_id=t.id
       ${w} ORDER BY tb.update_time DESC LIMIT ? OFFSET ?`, [...p, pageSize, offset]);
    return { list: rows, total, page, pageSize };
  },
  async upsertTaskBook(row) {
    const [ex] = await pool.query('SELECT id FROM t_gd_task_book WHERE student_id=? AND is_deleted=0', [row.student_id]);
    if (ex.length) {
      if (row.file_url === undefined) {
        await pool.query(
          `UPDATE t_gd_task_book SET topic_id=?, teacher_id=?, title=?, content=?, status=0, student_confirmed=0 WHERE id=?`,
          [row.topic_id, row.teacher_id, row.title, row.content, ex[0].id]);
      } else {
        await pool.query(
          `UPDATE t_gd_task_book SET topic_id=?, teacher_id=?, title=?, content=?, file_url=?, status=0, student_confirmed=0 WHERE id=?`,
          [row.topic_id, row.teacher_id, row.title, row.content, row.file_url, ex[0].id]);
      }
      return ex[0].id;
    }
    const [r] = await pool.query(
      `INSERT INTO t_gd_task_book (student_id, topic_id, teacher_id, title, content, file_url) VALUES (?,?,?,?,?,?)`,
      [row.student_id, row.topic_id, row.teacher_id, row.title, row.content, row.file_url || null]);
    return r.insertId;
  },
  async confirmTaskBook(studentId) {
    const [r] = await pool.query(
      `UPDATE t_gd_task_book SET student_confirmed=1, status=1, confirm_time=NOW() WHERE student_id=? AND is_deleted=0`, [studentId]);
    return r.affectedRows;
  },
  async getTaskBook(id) {
    const [rows] = await pool.query(
      `SELECT tb.*, s.real_name AS student_name, s.eeid AS student_eeid,
              s.college_id AS student_college_id, t.real_name AS teacher_name
       FROM t_gd_task_book tb LEFT JOIN t_user s ON tb.student_id=s.id LEFT JOIN t_user t ON tb.teacher_id=t.id
       WHERE tb.id=? AND tb.is_deleted=0`, [id]);
    return rows[0] || null;
  },
  // 学生下拉选项（轻量）：院校管理员看全部，其余按学院过滤
  async studentOptions({ collegeId } = {}) {
    let w = 'WHERE u.role=4 AND u.is_deleted=0 AND u.status=1';
    const p = [];
    if (collegeId) { w += ' AND u.college_id=?'; p.push(collegeId); }
    const [rows] = await pool.query(
      `SELECT u.id, u.real_name, u.eeid, u.username FROM t_user u ${w} ORDER BY u.eeid LIMIT 1000`, p);
    return { list: rows };
  },

  /* ---------- 家长知情 / 鉴定 / 巡访 / 去向 / 免实习 ---------- */
  async listSimple(table, filter, joinSql, { page = 1, pageSize = 30 } = {}) {
    const map = {
      parent: { t: 't_parent_consent', alias: 'x', assignmentJoin: 'LEFT JOIN t_assignment a ON x.assignment_id=a.id', teacherSelect: 'a.teacher_id' },
      appraisal: { t: 't_intern_appraisal', alias: 'x', assignmentJoin: 'LEFT JOIN t_assignment a ON x.assignment_id=a.id', teacherSelect: 'a.teacher_id' },
      alternative: { t: 't_intern_alternative', alias: 'x', assignmentJoin: '', teacherSelect: 'NULL' },
    };
    const m = map[table];
    let w = `WHERE ${m.alias}.is_deleted=0`;
    const p = [];
    if (filter.studentId) { w += ` AND ${m.alias}.student_id=?`; p.push(filter.studentId); }
    if (filter.teacherId && m.assignmentJoin) { w += ' AND a.teacher_id=?'; p.push(filter.teacherId); }
    if (filter.teacherId && !m.assignmentJoin && table === 'alternative') {
      w += ` AND EXISTS (
        SELECT 1 FROM t_assignment ta
        WHERE ta.student_id=${m.alias}.student_id AND ta.teacher_id=?
          AND ta.status=1 AND ta.is_deleted=0
      )`;
      p.push(filter.teacherId);
    }
    if (filter.status !== undefined) { w += ` AND ${m.alias}.status=?`; p.push(filter.status); }
    if (filter.collegeId) { w += ' AND s.college_id=?'; p.push(filter.collegeId); }
    const offset = (page - 1) * pageSize;
    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM ${m.t} ${m.alias}
       LEFT JOIN t_user s ON ${m.alias}.student_id=s.id
       ${m.assignmentJoin} ${w}`, p);
    const [rows] = await pool.query(
      `SELECT ${m.alias}.*, s.real_name AS student_name, s.eeid AS student_eeid,
              s.college_id AS student_college_id, ${m.teacherSelect} AS assignment_teacher_id
       FROM ${m.t} ${m.alias}
       LEFT JOIN t_user s ON ${m.alias}.student_id=s.id
       ${m.assignmentJoin} ${w}
       ORDER BY ${m.alias}.update_time DESC LIMIT ? OFFSET ?`, [...p, pageSize, offset]);
    return { list: rows, total, page, pageSize };
  },

  async createParentConsent(row) {
    const [r] = await pool.query(`INSERT INTO t_parent_consent (student_id, assignment_id, file_url) VALUES (?,?,?)`,
      [row.student_id, row.assignment_id, row.file_url]);
    return r.insertId;
  },
  async reviewParentConsent(id, status, reviewerId, rejectReason) {
    await pool.query(`UPDATE t_parent_consent SET status=?, reviewer_id=?, reject_reason=?, review_time=NOW() WHERE id=?`,
      [status, reviewerId, rejectReason || null, id]);
  },
  async getParentConsent(id) {
    const [rows] = await pool.query(
      `SELECT x.*, s.college_id AS student_college_id, a.teacher_id AS assignment_teacher_id
       FROM t_parent_consent x
       LEFT JOIN t_user s ON x.student_id=s.id
       LEFT JOIN t_assignment a ON x.assignment_id=a.id
       WHERE x.id=? AND x.is_deleted=0`, [id]);
    return rows[0] || null;
  },

  async upsertAppraisal(row) {
    const [ex] = await pool.query('SELECT id FROM t_intern_appraisal WHERE student_id=? AND is_deleted=0', [row.student_id]);
    if (ex.length) {
      await pool.query(`UPDATE t_intern_appraisal SET file_url=?, enterprise_comment=?, status=0 WHERE id=?`,
        [row.file_url, row.enterprise_comment, ex[0].id]);
      return ex[0].id;
    }
    const [r] = await pool.query(`INSERT INTO t_intern_appraisal (student_id, assignment_id, file_url, enterprise_comment) VALUES (?,?,?,?)`,
      [row.student_id, row.assignment_id, row.file_url, row.enterprise_comment]);
    return r.insertId;
  },
  async reviewAppraisal(id, status, rejectReason) {
    await pool.query(`UPDATE t_intern_appraisal SET status=?, reject_reason=? WHERE id=?`, [status, rejectReason || null, id]);
  },
  async getAppraisal(id) {
    const [rows] = await pool.query(
      `SELECT x.*, s.real_name AS student_name, s.eeid AS student_eeid,
              s.college_id AS student_college_id, a.teacher_id AS assignment_teacher_id
       FROM t_intern_appraisal x
       LEFT JOIN t_user s ON x.student_id=s.id
       LEFT JOIN t_assignment a ON x.assignment_id=a.id
       WHERE x.id=? AND x.is_deleted=0`, [id]);
    return rows[0] || null;
  },

  async listVisits(filter = {}, { page = 1, pageSize = 30 } = {}) {
    let w = 'WHERE v.is_deleted=0';
    const p = [];
    if (filter.teacherId) { w += ' AND v.teacher_id=?'; p.push(filter.teacherId); }
    if (filter.studentId) { w += ' AND v.student_id=?'; p.push(filter.studentId); }
    if (filter.collegeId) { w += ' AND s.college_id=?'; p.push(filter.collegeId); }
    const offset = (page - 1) * pageSize;
    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_teacher_visit v LEFT JOIN t_user s ON v.student_id=s.id ${w}`, p);
    const [rows] = await pool.query(
      `SELECT v.*, s.real_name AS student_name, t.real_name AS teacher_name, e.name AS enterprise_name
       FROM t_teacher_visit v
       LEFT JOIN t_user s ON v.student_id=s.id LEFT JOIN t_user t ON v.teacher_id=t.id
       LEFT JOIN t_assignment a ON v.assignment_id=a.id LEFT JOIN t_enterprise e ON a.enterprise_id=e.id
       ${w} ORDER BY v.visit_date DESC LIMIT ? OFFSET ?`, [...p, pageSize, offset]);
    return { list: rows, total, page, pageSize };
  },
  async createVisit(row) {
    const [r] = await pool.query(
      `INSERT INTO t_teacher_visit (teacher_id, student_id, assignment_id, visit_date, location, content, photo_url, problems) VALUES (?,?,?,?,?,?,?,?)`,
      [row.teacher_id, row.student_id, row.assignment_id, row.visit_date, row.location, row.content, row.photo_url, row.problems]);
    return r.insertId;
  },

  async upsertEmployment(row) {
    const [ex] = await pool.query('SELECT id FROM t_employment_destination WHERE student_id=? AND is_deleted=0', [row.student_id]);
    if (ex.length) {
      await pool.query(`UPDATE t_employment_destination SET dest_type=?, company_name=?, position_title=?, city=?, salary_range=?, remark=? WHERE id=?`,
        [row.dest_type, row.company_name, row.position_title, row.city, row.salary_range, row.remark, ex[0].id]);
      return ex[0].id;
    }
    const [r] = await pool.query(
      `INSERT INTO t_employment_destination (student_id, dest_type, company_name, position_title, city, salary_range, remark) VALUES (?,?,?,?,?,?,?)`,
      [row.student_id, row.dest_type, row.company_name, row.position_title, row.city, row.salary_range, row.remark]);
    return r.insertId;
  },
  async getEmployment(studentId) {
    const [rows] = await pool.query('SELECT * FROM t_employment_destination WHERE student_id=? AND is_deleted=0', [studentId]);
    return rows[0] || null;
  },

  /** 就业大盘:去向分布 + 就业率（已登记去向 / 在册学生），可按学院过滤 */
  async employmentStats(collegeId) {
    const col = collegeId ? ' AND u.college_id=?' : '';
    const p = collegeId ? [collegeId] : [];
    // 在册毕业班学生总数（role=4）
    const [[tot]] = await pool.query(
      `SELECT COUNT(*) AS c FROM t_user u WHERE u.role=4 AND u.status=1 AND u.is_deleted=0 ${col}`, p);
    const total = tot.c || 0;
    // 已登记去向（按类型分组）
    const [byType] = await pool.query(
      `SELECT e.dest_type, COUNT(*) AS c FROM t_employment_destination e
       JOIN t_user u ON e.student_id=u.id
       WHERE e.is_deleted=0 ${col} GROUP BY e.dest_type`, p);
    const labelMap = { employment: '就业', study: '升学', business: '创业', military: '参军', other: '其他' };
    const dist = byType.map(r => ({ type: r.dest_type, label: labelMap[r.dest_type] || r.dest_type, count: r.c }));
    const filled = dist.reduce((s, d) => s + d.count, 0);
    // 城市 Top5
    const [cities] = await pool.query(
      `SELECT e.city, COUNT(*) AS c FROM t_employment_destination e
       JOIN t_user u ON e.student_id=u.id
       WHERE e.is_deleted=0 AND e.city IS NOT NULL AND e.city<>'' ${col}
       GROUP BY e.city ORDER BY c DESC LIMIT 5`, p);
    const rate = total ? Math.round((filled / total) * 1000) / 10 : 0;
    return { total, filled, rate, dist, topCities: cities.map(c => ({ city: c.city, count: c.c })) };
  },

  async createAlternative(row) {
    const [r] = await pool.query(`INSERT INTO t_intern_alternative (student_id, alt_type, reason, file_url) VALUES (?,?,?,?)`,
      [row.student_id, row.alt_type, row.reason, row.file_url]);
    return r.insertId;
  },
  async getAlternative(id) {
    const [rows] = await pool.query(
      `SELECT x.*, s.college_id AS student_college_id
       FROM t_intern_alternative x
       LEFT JOIN t_user s ON x.student_id=s.id
       WHERE x.id=? AND x.is_deleted=0`, [id]);
    return rows[0] || null;
  },
  async reviewAlternative(id, status, reviewerId, remark) {
    await pool.query(`UPDATE t_intern_alternative SET status=?, reviewer_id=?, review_remark=?, review_time=NOW() WHERE id=?`,
      [status, reviewerId, remark || null, id]);
  },

  /* ---------- 选题互选 ---------- */
  async listTopicPool(filter = {}) {
    let w = 'WHERE p.is_deleted=0 AND p.status=1';
    const par = [];
    if (filter.teacherId) { w += ' AND p.teacher_id=?'; par.push(filter.teacherId); }
    if (filter.collegeId) { w += ' AND (p.college_id=? OR p.college_id IS NULL)'; par.push(filter.collegeId); }
    const [rows] = await pool.query(
      `SELECT p.*, t.real_name AS teacher_name FROM t_gd_topic_pool p LEFT JOIN t_user t ON p.teacher_id=t.id ${w} ORDER BY p.id DESC`, par);
    return rows;
  },
  async createTopicPool(row) {
    const [r] = await pool.query(
      `INSERT INTO t_gd_topic_pool (teacher_id, college_id, title, type, source, description, quota) VALUES (?,?,?,?,?,?,?)`,
      [row.teacher_id, row.college_id, row.title, row.type, row.source, row.description, row.quota || 1]);
    return r.insertId;
  },
  async listRounds(collegeId) {
    let w = 'WHERE is_deleted=0';
    const p = [];
    if (collegeId) { w += ' AND (college_id=? OR college_id IS NULL)'; p.push(collegeId); }
    const [rows] = await pool.query(`SELECT * FROM t_gd_topic_round ${w} ORDER BY id DESC`, p);
    return rows;
  },
  async createRound(row) {
    const [r] = await pool.query(`INSERT INTO t_gd_topic_round (name, max_choices, status, start_time, end_time, college_id) VALUES (?,?,?,?,?,?)`,
      [row.name, row.max_choices, row.status || 0, toMysqlDatetime(row.start_time), toMysqlDatetime(row.end_time), row.college_id]);
    return r.insertId;
  },
  async setRoundStatus(id, status) {
    await pool.query('UPDATE t_gd_topic_round SET status=? WHERE id=?', [status, id]);
  },
  async submitChoices(roundId, studentId, choices) {
    await pool.query('UPDATE t_gd_topic_choice SET is_deleted=1 WHERE round_id=? AND student_id=?', [roundId, studentId]);
    for (const c of choices) {
      await pool.query(`INSERT INTO t_gd_topic_choice (round_id, student_id, pool_id, priority) VALUES (?,?,?,?)`,
        [roundId, studentId, c.pool_id, c.priority]);
    }
  },
  async listChoices(roundId, filter = {}) {
    let w = 'WHERE c.is_deleted=0 AND c.round_id=?';
    const p = [roundId];
    if (filter.studentId) { w += ' AND c.student_id=?'; p.push(filter.studentId); }
    const [rows] = await pool.query(
      `SELECT c.*, s.real_name AS student_name, p.title AS topic_title, t.real_name AS teacher_name
       FROM t_gd_topic_choice c
       LEFT JOIN t_user s ON c.student_id=s.id
       LEFT JOIN t_gd_topic_pool p ON c.pool_id=p.id
       LEFT JOIN t_user t ON p.teacher_id=t.id ${w} ORDER BY c.priority`, p);
    return rows;
  },
  async matchRound(roundId) {
    const choices = await this.listChoices(roundId);
    // 取相关课题的剩余名额，交给纯函数做分配（一人最多一项、不超 quota）
    const poolIds = [...new Set(choices.map(c => c.pool_id))];
    const poolInfo = {};
    const remainingByPool = {};
    for (const pid of poolIds) {
      const [[tp]] = await pool.query('SELECT * FROM t_gd_topic_pool WHERE id=?', [pid]);
      poolInfo[pid] = tp || null;
      remainingByPool[pid] = tp ? Math.max(0, tp.quota - tp.chosen_count) : 0;
    }
    const winners = this.planTopicMatches(choices, remainingByPool);

    let matched = 0;
    for (const c of winners) {
      const topicPool = poolInfo[c.pool_id];
      if (!topicPool) continue;
      await pool.query('UPDATE t_gd_topic_choice SET status=1 WHERE id=?', [c.id]);
      await pool.query('UPDATE t_gd_topic_pool SET chosen_count=chosen_count+1 WHERE id=?', [c.pool_id]);

      const [stuRows] = await pool.query('SELECT college_id, class_id, major_id FROM t_user WHERE id=?', [c.student_id]);
      const u = stuRows[0];
      const [existing] = await pool.query('SELECT id FROM t_gd_topic WHERE student_id=? AND is_deleted=0', [c.student_id]);
      if (existing.length) {
        await pool.query('UPDATE t_gd_topic SET title=?, teacher_id=?, status=2 WHERE id=?',
          [topicPool.title, topicPool.teacher_id, existing[0].id]);
      } else {
        await pool.query(
          `INSERT INTO t_gd_topic (title, student_id, teacher_id, college_id, major_id, class_id, type, source, status) VALUES (?,?,?,?,?,?,?,?,2)`,
          [topicPool.title, c.student_id, topicPool.teacher_id, u?.college_id, u?.major_id, u?.class_id, topicPool.type, topicPool.source]);
      }
      matched++;
    }
    // 未匹配上的志愿标记为未匹配(2)，便于前端展示
    await pool.query('UPDATE t_gd_topic_choice SET status=2 WHERE round_id=? AND is_deleted=0 AND status=0', [roundId]);
    await pool.query('UPDATE t_gd_topic_round SET status=2 WHERE id=?', [roundId]);
    return matched;
  },

  /* ---------- 实习成绩 ---------- */
  async getScoreConfig(collegeId) {
    const [rows] = await pool.query(
      'SELECT * FROM t_intern_score_config WHERE is_deleted=0 AND (college_id=? OR college_id IS NULL) ORDER BY college_id DESC LIMIT 1',
      [collegeId || null]);
    return rows[0] || null;
  },
  async saveScoreConfig(row) {
    const ex = await this.getScoreConfig(row.college_id);
    if (ex) {
      await pool.query(
        `UPDATE t_intern_score_config SET checkin_weight=?, weekly_weight=?, monthly_weight=?, enterprise_weight=?, school_weight=?, pass_line=? WHERE id=?`,
        [row.checkin_weight, row.weekly_weight, row.monthly_weight, row.enterprise_weight, row.school_weight, row.pass_line, ex.id]);
      return ex.id;
    }
    const [r] = await pool.query(
      `INSERT INTO t_intern_score_config (college_id, checkin_weight, weekly_weight, monthly_weight, enterprise_weight, school_weight, pass_line) VALUES (?,?,?,?,?,?,?)`,
      [row.college_id, row.checkin_weight, row.weekly_weight, row.monthly_weight, row.enterprise_weight, row.school_weight, row.pass_line]);
    return r.insertId;
  },
  /**
   * 核算实习综合考评。
   * 过程分（打卡/日志）由真实数据计算；企业评价取真实企业评分，缺失则置空（不再写死 80）；
   * 校内评分由教师录入（opts.schoolScore），缺失则置空（不再写死 85）。
   * 存在缺失分项时按"已到位分项的权重"折算出临时总分并标记 incomplete=1，避免凭空造分。
   */
  async computeInternScore(studentId, opts = {}) {
    const cfg = await this.getScoreConfig(null);
    const [[a]] = await pool.query(
      `SELECT a.*, p.checkin_count AS req_checkin, p.weekly_count AS req_weekly, p.monthly_count AS req_monthly
       FROM t_assignment a LEFT JOIN t_intern_plan p ON a.plan_id=p.id
       WHERE a.student_id=? AND a.status=1 AND a.is_deleted=0 LIMIT 1`, [studentId]);
    if (!a) return null;
    const [[ck]] = await pool.query('SELECT COUNT(*) AS c FROM t_checkin WHERE student_id=? AND (makeup_status IS NULL OR makeup_status=1)', [studentId]);
    const [[wk]] = await pool.query("SELECT COUNT(*) AS c FROM t_intern_log WHERE student_id=? AND type='weekly' AND status IN (1,2) AND is_deleted=0", [studentId]);
    const [[mo]] = await pool.query("SELECT COUNT(*) AS c FROM t_intern_log WHERE student_id=? AND type='monthly' AND status IN (1,2) AND is_deleted=0", [studentId]);
    let ev = { s: null };
    try { const [[r]] = await pool.query('SELECT AVG(score_overall) AS s FROM t_enterprise_eval WHERE student_id=? AND status=1 AND is_deleted=0', [studentId]); ev = r || ev; } catch (_) {}

    const reqC = a.req_checkin || 1, reqW = a.req_weekly || 1, reqM = a.req_monthly || 1;
    const checkinScore = Math.min(100, Math.round((ck.c / reqC) * 100));
    const logScore = Math.min(100, Math.round(((wk.c / reqW) * 0.6 + (mo.c / reqM) * 0.4) * 100));
    // 企业评价：真实评分（按 5 分制换算百分制）；无评价则为 null（待企业评价）
    const enterpriseScore = ev.s != null ? Math.min(100, Math.round(Number(ev.s) * 20)) : null;

    // 校内评分：本次教师录入优先；否则沿用历史录入值；都没有则 null（待录入）
    let schoolScore = null, schoolScoredBy = null;
    if (opts.schoolScore != null && opts.schoolScore !== '') {
      schoolScore = Math.max(0, Math.min(100, Number(opts.schoolScore)));
      schoolScoredBy = opts.scoredBy || null;
    } else {
      const [[prev]] = await pool.query('SELECT school_score, school_scored_by FROM t_intern_final_score WHERE student_id=? AND is_deleted=0', [studentId]);
      if (prev && prev.school_score != null) { schoolScore = Number(prev.school_score); schoolScoredBy = prev.school_scored_by; }
    }

    const w = cfg || { checkin_weight: 20, weekly_weight: 20, monthly_weight: 10, enterprise_weight: 30, school_weight: 20 };
    const logW = Number(w.weekly_weight) + Number(w.monthly_weight);
    const components = [
      { key: 'checkin', score: checkinScore, weight: Number(w.checkin_weight) },
      { key: 'log', score: logScore, weight: logW },
      { key: 'enterprise', score: enterpriseScore, weight: Number(w.enterprise_weight) },
      { key: 'school', score: schoolScore, weight: Number(w.school_weight) }
    ];
    const { total, missing, incomplete } = this.scoreInternComponents(components);

    await pool.query(
      `INSERT INTO t_intern_final_score (student_id, assignment_id, checkin_score, log_score, enterprise_score, school_score, school_scored_by, total_score, incomplete)
       VALUES (?,?,?,?,?,?,?,?,?) ON DUPLICATE KEY UPDATE checkin_score=VALUES(checkin_score), log_score=VALUES(log_score),
       enterprise_score=VALUES(enterprise_score), school_score=VALUES(school_score), school_scored_by=VALUES(school_scored_by),
       total_score=VALUES(total_score), incomplete=VALUES(incomplete), assignment_id=VALUES(assignment_id)`,
      [studentId, a.id, checkinScore, logScore, enterpriseScore, schoolScore, schoolScoredBy, total, incomplete]);
    const [rows] = await pool.query('SELECT * FROM t_intern_final_score WHERE student_id=?', [studentId]);
    const row = rows[0];
    if (row) row._missing = missing;
    return row;
  },
  async publishInternScore(studentId) {
    await pool.query('UPDATE t_intern_final_score SET published=1 WHERE student_id=?', [studentId]);
  },
  async getInternScore(studentId, allowUnpublished) {
    const [rows] = await pool.query('SELECT * FROM t_intern_final_score WHERE student_id=? AND is_deleted=0', [studentId]);
    const s = rows[0];
    if (s && !s.published && !allowUnpublished) return null;
    return s;
  },

  /* ---------- 催办名单 ---------- */
  async urgeList(collegeId, days = 3) {
    const col = collegeId ? ' AND s.college_id=?' : '';
    const p = collegeId ? [collegeId] : [];
    const [noCheckin] = await pool.query(
      `SELECT s.id AS student_id, s.real_name AS student_name, s.eeid AS student_eeid, e.name AS enterprise_name,
              (SELECT MAX(checkin_time) FROM t_checkin WHERE student_id=s.id) AS last_checkin
       FROM t_assignment a JOIN t_user s ON a.student_id=s.id LEFT JOIN t_enterprise e ON a.enterprise_id=e.id
       WHERE a.status=1 AND a.is_deleted=0 ${col}
         AND NOT EXISTS (SELECT 1 FROM t_checkin c WHERE c.student_id=s.id AND DATE(c.checkin_time)=CURDATE())`, p);
    const [noWeekly] = await pool.query(
      `SELECT s.id AS student_id, s.real_name AS student_name, s.eeid AS student_eeid,
              (SELECT COUNT(*) FROM t_intern_log l WHERE l.student_id=s.id AND l.type='weekly' AND l.status IN (1,2) AND l.is_deleted=0) AS weekly_count,
              p.weekly_count AS req_weekly
       FROM t_assignment a JOIN t_user s ON a.student_id=s.id JOIN t_intern_plan p ON a.plan_id=p.id
       WHERE a.status=1 AND a.is_deleted=0 ${col}
         AND (SELECT COUNT(*) FROM t_intern_log l WHERE l.student_id=s.id AND l.type='weekly' AND l.status IN (1,2) AND l.is_deleted=0) < IFNULL(p.weekly_count,1)`, p);
    const [noConsent] = await pool.query(
      `SELECT s.id AS student_id, s.real_name AS student_name FROM t_assignment a JOIN t_user s ON a.student_id=s.id
       WHERE a.status=1 AND a.is_deleted=0 ${col}
         AND NOT EXISTS (SELECT 1 FROM t_parent_consent pc WHERE pc.student_id=s.id AND pc.status=1 AND pc.is_deleted=0)`, p);
    const [noAppraisal] = await pool.query(
      `SELECT s.id AS student_id, s.real_name AS student_name FROM t_assignment a JOIN t_user s ON a.student_id=s.id
       WHERE a.status=1 AND a.is_deleted=0 ${col}
         AND NOT EXISTS (SELECT 1 FROM t_intern_appraisal ia WHERE ia.student_id=s.id AND ia.status=1 AND ia.is_deleted=0)`, p);
    return { noCheckin, noWeekly, noConsent, noAppraisal };
  },

  /* ---------- 签到积分 ---------- */
  async addCheckinPoints(studentId) {
    await pool.query(`INSERT INTO t_checkin_points (student_id, points, streak_days) VALUES (?,10,1)
      ON DUPLICATE KEY UPDATE points=points+10, streak_days=streak_days+1`, [studentId]);
    const [rows] = await pool.query('SELECT * FROM t_checkin_points WHERE student_id=?', [studentId]);
    return rows[0];
  },

  /* ---------- 查重 / AIGC（可插拔，未对接第三方时为演示数据） ---------- */
  async runPlagiarism(studentId, achievementId, fileUrl) {
    const plagiarism = require('../utils/plagiarism');
    let result;
    try {
      result = await plagiarism.detect(fileUrl);
    } catch (e) {
      // 第三方检测失败：记录失败状态，不伪造数据
      await pool.query('UPDATE t_gd_plagiarism SET is_deleted=1 WHERE achievement_id=?', [achievementId]);
      const [fr] = await pool.query(
        `INSERT INTO t_gd_plagiarism (student_id, achievement_id, status, provider, is_demo) VALUES (?,?,2,?,0)`,
        [studentId, achievementId, 'external']);
      const [frows] = await pool.query('SELECT * FROM t_gd_plagiarism WHERE id=?', [fr.insertId]);
      const row = frows[0];
      row._error = e.message;
      return row;
    }
    await pool.query('UPDATE t_gd_plagiarism SET is_deleted=1 WHERE achievement_id=?', [achievementId]);
    const [r] = await pool.query(
      `INSERT INTO t_gd_plagiarism (student_id, achievement_id, similarity, aigc_rate, status, report_url, provider, is_demo)
       VALUES (?,?,?,?,1,?,?,?)`,
      [studentId, achievementId, result.similarity, result.aigc, result.reportUrl, result.provider, result.isDemo ? 1 : 0]);
    const [rows] = await pool.query('SELECT * FROM t_gd_plagiarism WHERE id=?', [r.insertId]);
    return rows[0];
  },
  async getPlagiarism(achievementId) {
    const [rows] = await pool.query('SELECT * FROM t_gd_plagiarism WHERE achievement_id=? AND is_deleted=0 ORDER BY id DESC LIMIT 1', [achievementId]);
    return rows[0] || null;
  },

  /* ---------- 学信网导出 ---------- */
  chsiExportRows(students) {
    return students.map(s => ({
      '学号': s.eeid || '', '姓名': s.real_name || '', '性别': '',
      '专业名称': s.major_name || '', '班级': s.class_name || '',
      '实习单位': s.enterprise_name || '', '实习岗位': s.position_title || '',
      '实习开始日期': s.start_date || '', '实习结束日期': s.end_date || '',
      '指导教师': s.teacher_name || '', '实习形式': '岗位实习', '是否对口': '是'
    }));
  },

  async chsiData(collegeId) {
    let w = 'WHERE a.status=1 AND a.is_deleted=0 AND s.role=4';
    const p = [];
    if (collegeId) { w += ' AND s.college_id=?'; p.push(collegeId); }
    const [rows] = await pool.query(
      `SELECT s.eeid, s.real_name, m.name AS major_name, cl.name AS class_name,
              e.name AS enterprise_name,
              (SELECT pos.title FROM t_application app JOIN t_position pos ON app.position_id=pos.id
               WHERE app.student_id=s.id AND app.status=5 AND app.is_deleted=0 ORDER BY app.id DESC LIMIT 1) AS position_title,
              DATE(a.create_time) AS start_date, p.end_date, t.real_name AS teacher_name
       FROM t_assignment a
       JOIN t_user s ON a.student_id=s.id
       LEFT JOIN t_user t ON a.teacher_id=t.id
       LEFT JOIN t_major m ON s.major_id=m.id LEFT JOIN t_class cl ON s.class_id=cl.id
       LEFT JOIN t_enterprise e ON a.enterprise_id=e.id
       LEFT JOIN t_intern_plan p ON a.plan_id=p.id ${w}`, p);
    return rows;
  },

  /* ---------- 班主任本班学生 ---------- */
  async classTeacherStudents(teacherId) {
    const [rows] = await pool.query(
      `SELECT s.id, s.real_name, s.eeid, cl.name AS class_name
       FROM t_class cl JOIN t_user s ON s.class_id=cl.id
       WHERE cl.head_teacher_id=? AND s.role=4 AND s.status=1`, [teacherId]);
    return rows;
  },

  async studentDefense(studentId) {
    const [rows] = await pool.query(
      `SELECT g.*, m.seq, m.final_score, s.real_name AS student_name
       FROM t_defense_member m
       JOIN t_defense_group g ON m.group_id=g.id
       JOIN t_user s ON m.student_id=s.id
       WHERE m.student_id=? AND m.is_deleted=0 AND g.is_deleted=0 LIMIT 1`, [studentId]);
    return rows[0] || null;
  },
};

module.exports = benchmarkModel;
