/**
 * 迁移：毕业设计子系统基础（公示信息 t_announcement / 任务时间节点 t_gd_task）。
 * 幂等：CREATE TABLE IF NOT EXISTS。
 * 运行：node scripts/migrate-gd-core.js
 */
require('dotenv').config();
const pool = require('../config/db');

async function run() {
  try {
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_announcement (
        id INT AUTO_INCREMENT PRIMARY KEY,
        title VARCHAR(200) NOT NULL COMMENT '标题',
        category VARCHAR(50) DEFAULT '公示信息' COMMENT '分类：公示信息/管理机构/管理制度/相关标准/工作布置/任务下达等',
        content LONGTEXT COMMENT '正文',
        file_url VARCHAR(255) COMMENT '附件',
        college_id INT COMMENT '可见学院(null=全校)',
        publisher_id INT COMMENT '发布人',
        status TINYINT DEFAULT 1 COMMENT '1发布,0草稿',
        publish_time DATETIME COMMENT '发布时间',
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_category (category),
        INDEX idx_college (college_id),
        INDEX idx_status (status)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '公示信息/通知公告表'
    `);
    console.log('✅ t_announcement 就绪');

    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_gd_task (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(200) NOT NULL COMMENT '任务名称',
        parent_id INT COMMENT '父任务(根任务为空)',
        scope VARCHAR(100) COMMENT '所属范围(全校/学院/专业等)',
        college_id INT COMMENT '所属学院',
        require_time DATE COMMENT '要求完成时间',
        actual_time DATE COMMENT '实际完成时间',
        description TEXT COMMENT '情况描述',
        status TINYINT DEFAULT 0 COMMENT '0未开始,1进行中,2已完成',
        sort_order INT DEFAULT 0 COMMENT '排序',
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_parent (parent_id),
        INDEX idx_college (college_id),
        INDEX idx_status (status)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '毕业设计任务时间节点表'
    `);
    console.log('✅ t_gd_task 就绪');

    console.log('🎉 毕业设计基础表迁移完成');
  } catch (err) {
    console.error('❌ 迁移失败：', err.message);
    process.exitCode = 1;
  } finally {
    await pool.end();
  }
}

run();
