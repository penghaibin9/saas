/**
 * 迁移：岗位实习核心流程（实习计划 / 实习分配 / GPS打卡 + 实习单位坐标）。
 * 幂等：表用 CREATE TABLE IF NOT EXISTS；企业新增列先查 information_schema。
 * 运行：node scripts/migrate-intern-core.js
 */
require('dotenv').config();
const pool = require('../config/db');

async function columnExists(table, column) {
  const [rows] = await pool.query(
    `SELECT 1 FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? AND COLUMN_NAME = ?`,
    [table, column]
  );
  return rows.length > 0;
}

async function tableExists(table) {
  const [rows] = await pool.query(
    `SELECT 1 FROM information_schema.TABLES
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ?`,
    [table]
  );
  return rows.length > 0;
}

async function run() {
  try {
    // 1) 企业表增加地理坐标与打卡范围（基础表缺失时跳过，提示先初始化）
    if (!(await tableExists('t_enterprise'))) {
      console.warn('⚠️  t_enterprise 不存在，跳过经纬度列。请先执行 npm run init:db 建立基础表结构后重跑本迁移。');
    } else {
      const geoCols = [
        ["longitude", "ADD COLUMN longitude DECIMAL(10,6) NULL COMMENT '经度' AFTER description"],
        ["latitude", "ADD COLUMN latitude DECIMAL(10,6) NULL COMMENT '纬度' AFTER longitude"],
        ["checkin_radius", "ADD COLUMN checkin_radius INT DEFAULT 0 COMMENT '打卡有效半径(米)，0为不约束' AFTER latitude"],
      ];
      for (const [col, clause] of geoCols) {
        if (!(await columnExists('t_enterprise', col))) {
          await pool.query(`ALTER TABLE t_enterprise ${clause}`);
          console.log(`✅ t_enterprise 增加列 ${col}`);
        } else {
          console.log(`↩️  t_enterprise.${col} 已存在`);
        }
      }
    }

    // 2) 实习计划表
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_intern_plan (
        id INT AUTO_INCREMENT PRIMARY KEY,
        college_id INT NOT NULL COMMENT '所属分院',
        major_id INT COMMENT '限定专业(null=全院)',
        class_id INT COMMENT '限定班级(null=不限)',
        title VARCHAR(200) NOT NULL COMMENT '计划标题',
        start_date DATE COMMENT '实习开始',
        end_date DATE COMMENT '实习结束',
        purpose TEXT COMMENT '实习目的',
        content TEXT COMMENT '实习内容',
        requirement TEXT COMMENT '实习要求',
        checkin_count INT DEFAULT 0 COMMENT '需签到次数',
        weekly_count INT DEFAULT 0 COMMENT '需周报篇数',
        monthly_count INT DEFAULT 0 COMMENT '需月报篇数',
        summary_required TINYINT DEFAULT 1 COMMENT '是否需实习总结',
        materials VARCHAR(500) COMMENT '需上传材料类型(逗号分隔)',
        assess_method TEXT COMMENT '考核方式及占比',
        attachment_url VARCHAR(255) COMMENT '计划附件',
        status TINYINT DEFAULT 1 COMMENT '1申报,2通过,3开启,4结束,5驳回',
        reject_reason VARCHAR(255) COMMENT '驳回原因',
        created_by INT COMMENT '提交人',
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_college (college_id),
        INDEX idx_status (status)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '实习计划表'
    `);
    console.log('✅ t_intern_plan 就绪');

    // 3) 实习分配表
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_assignment (
        id INT AUTO_INCREMENT PRIMARY KEY,
        plan_id INT COMMENT '关联实习计划',
        student_id INT NOT NULL COMMENT '学生',
        teacher_id INT COMMENT '指导老师',
        enterprise_id INT COMMENT '实习企业',
        status TINYINT DEFAULT 1 COMMENT '1有效,0移除',
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_plan (plan_id),
        INDEX idx_student (student_id),
        INDEX idx_teacher (teacher_id),
        INDEX idx_enterprise (enterprise_id)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '实习分配表'
    `);
    console.log('✅ t_assignment 就绪');

    // 4) 打卡签到表
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_checkin (
        id INT AUTO_INCREMENT PRIMARY KEY,
        student_id INT NOT NULL COMMENT '学生',
        assignment_id INT COMMENT '关联分配',
        enterprise_id INT COMMENT '打卡对应企业',
        latitude DECIMAL(10,6) COMMENT '打卡纬度',
        longitude DECIMAL(10,6) COMMENT '打卡经度',
        distance INT COMMENT '距企业坐标(米)',
        within_range TINYINT DEFAULT 1 COMMENT '是否在有效范围内',
        address VARCHAR(255) COMMENT '打卡地址',
        remark VARCHAR(255) COMMENT '备注',
        checkin_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '打卡时间',
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_student (student_id),
        INDEX idx_checkin_time (checkin_time)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '打卡签到表'
    `);
    console.log('✅ t_checkin 就绪');

    console.log('🎉 实习核心表迁移完成');
  } catch (err) {
    console.error('❌ 迁移失败：', err.message);
    process.exitCode = 1;
  } finally {
    await pool.end();
  }
}

run();
