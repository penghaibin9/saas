/**
 * 商业级改造 · Tier2/Tier3 迁移
 *  - t_user 增 wx_openid（订阅消息触达）、skill_tags（岗位匹配）
 *  - t_position 增 tags（岗位标签，用于智能匹配）
 *  - 答辩管理：t_defense_group / t_defense_committee / t_defense_member / t_defense_score
 *  - 企业导师评价：t_enterprise_eval（含免登录 token）
 * 幂等：列存在性判断 + CREATE TABLE IF NOT EXISTS。
 * 运行：node scripts/migrate-commercial-t23.js
 */
require('dotenv').config();
const pool = require('../config/db');

async function columnExists(table, column) {
  const [rows] = await pool.query(
    `SELECT COUNT(*) AS c FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? AND COLUMN_NAME = ?`,
    [table, column]
  );
  return rows[0].c > 0;
}
async function indexExists(table, indexName) {
  const [rows] = await pool.query(
    `SELECT COUNT(*) AS c FROM information_schema.STATISTICS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? AND INDEX_NAME = ?`,
    [table, indexName]
  );
  return rows[0].c > 0;
}
async function addColumn(table, column, ddl) {
  if (!(await columnExists(table, column))) {
    await pool.query(`ALTER TABLE ${table} ADD COLUMN ${ddl}`);
    console.log(`✅ ${table}.${column} 已添加`);
  } else {
    console.log(`· ${table}.${column} 已存在，跳过`);
  }
}

async function run() {
  try {
    await addColumn('t_user', 'wx_openid', `wx_openid VARCHAR(64) NULL COMMENT '微信openid(订阅消息)'`);
    await addColumn('t_user', 'skill_tags', `skill_tags VARCHAR(255) NULL COMMENT '学生技能标签,逗号分隔'`);
    await addColumn('t_position', 'tags', `tags VARCHAR(255) NULL COMMENT '岗位标签,逗号分隔(智能匹配)'`);

    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_defense_group (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(150) NOT NULL COMMENT '答辩组名称',
        defense_date DATE COMMENT '答辩日期',
        location VARCHAR(150) COMMENT '答辩地点',
        college_id INT COMMENT '学院',
        remark VARCHAR(255) COMMENT '备注',
        status TINYINT DEFAULT 0 COMMENT '0筹备,1进行中,2已完成',
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_college (college_id), INDEX idx_status (status)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '答辩分组表'
    `);
    console.log('✅ t_defense_group 就绪');

    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_defense_committee (
        id INT AUTO_INCREMENT PRIMARY KEY,
        group_id INT NOT NULL COMMENT '答辩组',
        teacher_id INT NOT NULL COMMENT '评委教师',
        role VARCHAR(20) DEFAULT 'member' COMMENT 'chair组长,secretary秘书,member评委',
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uniq_group_teacher (group_id, teacher_id),
        INDEX idx_teacher (teacher_id)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '答辩评委表'
    `);
    console.log('✅ t_defense_committee 就绪');

    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_defense_member (
        id INT AUTO_INCREMENT PRIMARY KEY,
        group_id INT NOT NULL COMMENT '答辩组',
        student_id INT NOT NULL COMMENT '答辩学生',
        achievement_id INT COMMENT '关联毕设成果',
        seq INT DEFAULT 0 COMMENT '答辩顺序',
        final_score DECIMAL(5,2) COMMENT '汇总成绩(评委均分)',
        recommended TINYINT DEFAULT 0 COMMENT '是否推优',
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uniq_group_student (group_id, student_id),
        INDEX idx_student (student_id)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '答辩学生表'
    `);
    console.log('✅ t_defense_member 就绪');

    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_defense_score (
        id INT AUTO_INCREMENT PRIMARY KEY,
        group_id INT NOT NULL COMMENT '答辩组',
        student_id INT NOT NULL COMMENT '答辩学生',
        judge_id INT NOT NULL COMMENT '评委教师',
        score DECIMAL(5,2) NOT NULL COMMENT '评分',
        comment VARCHAR(500) COMMENT '评语',
        blind TINYINT DEFAULT 1 COMMENT '是否双盲(评委互不可见)',
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uniq_group_student_judge (group_id, student_id, judge_id),
        INDEX idx_group (group_id)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '答辩评分表'
    `);
    console.log('✅ t_defense_score 就绪');

    // 修正历史唯一键：旧版误用 (student_id, judge_id)，缺少 group_id，
    // 会导致同一学生在不同答辩组重复评分时更新到旧组记录。改为 (group_id, student_id, judge_id)。
    if (await indexExists('t_defense_score', 'uniq_student_judge')) {
      await pool.query('ALTER TABLE t_defense_score DROP INDEX uniq_student_judge');
      console.log('· t_defense_score 删除旧唯一键 uniq_student_judge');
    }
    if (!(await indexExists('t_defense_score', 'uniq_group_student_judge'))) {
      await pool.query('ALTER TABLE t_defense_score ADD UNIQUE KEY uniq_group_student_judge (group_id, student_id, judge_id)');
      console.log('· t_defense_score 添加唯一键 uniq_group_student_judge');
    }

    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_enterprise_eval (
        id INT AUTO_INCREMENT PRIMARY KEY,
        student_id INT NOT NULL COMMENT '被评价学生',
        enterprise_id INT COMMENT '企业',
        assignment_id INT COMMENT '实习分配',
        college_id INT COMMENT '学院',
        token VARCHAR(64) NOT NULL COMMENT '免登录评价令牌',
        mentor_name VARCHAR(100) COMMENT '企业导师姓名',
        mentor_title VARCHAR(100) COMMENT '导师职务',
        score_overall TINYINT COMMENT '综合(1-5)',
        score_attitude TINYINT COMMENT '工作态度(1-5)',
        score_skill TINYINT COMMENT '专业能力(1-5)',
        score_discipline TINYINT COMMENT '纪律性(1-5)',
        comment VARCHAR(1000) COMMENT '评语',
        status TINYINT DEFAULT 0 COMMENT '0待评价,1已评价',
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        submit_time DATETIME COMMENT '提交时间',
        UNIQUE KEY uniq_token (token),
        INDEX idx_student (student_id), INDEX idx_college (college_id), INDEX idx_status (status)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '企业导师评价表'
    `);
    console.log('✅ t_enterprise_eval 就绪');

    console.log('🎉 Tier2/3 迁移完成');
  } catch (err) {
    console.error('❌ 迁移失败：', err.message);
    process.exitCode = 1;
  } finally {
    await pool.end();
  }
}

run();
