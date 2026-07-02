-- 毕业设计及岗位实习管理平台 数据库初始化脚本
-- 创建数据库
CREATE DATABASE IF NOT EXISTS internship_management DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE internship_management;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS t_notification;
DROP TABLE IF EXISTS t_report;
DROP TABLE IF EXISTS t_application;
DROP TABLE IF EXISTS t_position;
DROP TABLE IF EXISTS t_enterprise;
DROP TABLE IF EXISTS t_user;
DROP TABLE IF EXISTS t_class;
DROP TABLE IF EXISTS t_major;
DROP TABLE IF EXISTS t_college;
SET FOREIGN_KEY_CHECKS = 1;

-- 学院表
CREATE TABLE IF NOT EXISTS t_college (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL COMMENT '学院名称',
  code VARCHAR(50) NOT NULL UNIQUE COMMENT '学院编码',
  description TEXT COMMENT '学院描述',
  status TINYINT DEFAULT 1 COMMENT '状态：1启用，0禁用',
  is_deleted TINYINT DEFAULT 0 COMMENT '逻辑删除',
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  INDEX idx_code (code),
  INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '学院表';

-- 专业表
CREATE TABLE IF NOT EXISTS t_major (
  id INT AUTO_INCREMENT PRIMARY KEY,
  college_id INT NOT NULL COMMENT '所属学院ID',
  name VARCHAR(100) NOT NULL COMMENT '专业名称',
  code VARCHAR(50) NOT NULL UNIQUE COMMENT '专业编码',
  description TEXT COMMENT '专业描述',
  status TINYINT DEFAULT 1 COMMENT '状态：1启用，0禁用',
  is_deleted TINYINT DEFAULT 0 COMMENT '逻辑删除',
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  FOREIGN KEY (college_id) REFERENCES t_college(id),
  INDEX idx_college (college_id),
  INDEX idx_code (code),
  INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '专业表';

-- 班级表
CREATE TABLE IF NOT EXISTS t_class (
  id INT AUTO_INCREMENT PRIMARY KEY,
  college_id INT NOT NULL COMMENT '所属学院ID',
  major_id INT NOT NULL COMMENT '所属专业ID',
  name VARCHAR(100) NOT NULL COMMENT '班级名称',
  grade INT COMMENT '年级（如2024）',
  status TINYINT DEFAULT 1 COMMENT '状态：1启用，0禁用',
  is_deleted TINYINT DEFAULT 0 COMMENT '逻辑删除',
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  FOREIGN KEY (college_id) REFERENCES t_college(id),
  FOREIGN KEY (major_id) REFERENCES t_major(id),
  INDEX idx_college (college_id),
  INDEX idx_major (major_id),
  INDEX idx_grade (grade)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '班级表';

-- 用户表
CREATE TABLE IF NOT EXISTS t_user (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
  password VARCHAR(255) NOT NULL COMMENT '密码（bcrypt加密）',
  real_name VARCHAR(100) NOT NULL COMMENT '真实姓名',
  phone VARCHAR(20) COMMENT '手机号',
  email VARCHAR(100) COMMENT '邮箱',
  role INT NOT NULL COMMENT '角色：1院校管理员,2分院管理员,3指导教师,4学生',
  college_id INT COMMENT '所属学院ID',
  major_id INT COMMENT '所属专业ID',
  class_id INT COMMENT '所属班级ID',
  eeid VARCHAR(50) COMMENT '学工号',
  last_login_time DATETIME COMMENT '最后登录时间',
  status TINYINT DEFAULT 1 COMMENT '状态：1启用，0禁用',
  must_change_password TINYINT DEFAULT 0 COMMENT '是否需要强制修改密码：1是,0否',
  is_deleted TINYINT DEFAULT 0 COMMENT '逻辑删除',
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  FOREIGN KEY (college_id) REFERENCES t_college(id),
  FOREIGN KEY (major_id) REFERENCES t_major(id),
  FOREIGN KEY (class_id) REFERENCES t_class(id),
  INDEX idx_username (username),
  INDEX idx_role (role),
  INDEX idx_college (college_id),
  INDEX idx_eeid (eeid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '用户表';

-- 企业表
CREATE TABLE IF NOT EXISTS t_enterprise (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(200) NOT NULL COMMENT '企业名称',
  short_name VARCHAR(100) COMMENT '企业简称',
  industry VARCHAR(100) COMMENT '行业',
  address VARCHAR(255) COMMENT '地址',
  contact_name VARCHAR(100) COMMENT '联系人',
  contact_phone VARCHAR(20) COMMENT '联系电话',
  description TEXT COMMENT '企业描述',
  status TINYINT DEFAULT 1 COMMENT '状态：1启用，0禁用',
  is_deleted TINYINT DEFAULT 0 COMMENT '逻辑删除',
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  INDEX idx_name (name),
  INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '企业表';

-- 岗位表
CREATE TABLE IF NOT EXISTS t_position (
  id INT AUTO_INCREMENT PRIMARY KEY,
  enterprise_id INT NOT NULL COMMENT '企业ID',
  title VARCHAR(200) NOT NULL COMMENT '岗位名称',
  description TEXT COMMENT '岗位描述',
  requirement TEXT COMMENT '岗位要求',
  salary VARCHAR(100) COMMENT '薪资',
  headcount INT DEFAULT 1 COMMENT '招聘人数',
  location VARCHAR(200) COMMENT '工作地点',
  start_date DATE COMMENT '实习开始日期',
  end_date DATE COMMENT '实习结束日期',
  college_id INT COMMENT '限定学院ID（null表示全校）',
  status TINYINT DEFAULT 1 COMMENT '状态：1上架，0下架',
  is_deleted TINYINT DEFAULT 0 COMMENT '逻辑删除',
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  FOREIGN KEY (enterprise_id) REFERENCES t_enterprise(id),
  FOREIGN KEY (college_id) REFERENCES t_college(id),
  INDEX idx_enterprise (enterprise_id),
  INDEX idx_college (college_id),
  INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '岗位表';

-- 申请表
CREATE TABLE IF NOT EXISTS t_application (
  id INT AUTO_INCREMENT PRIMARY KEY,
  student_id INT NOT NULL COMMENT '学生ID',
  position_id INT NOT NULL COMMENT '岗位ID',
  enterprise_id INT NOT NULL COMMENT '企业ID',
  teacher_id INT COMMENT '指导教师ID',
  student_remark TEXT COMMENT '学生备注',
  teacher_opinion TEXT COMMENT '教师意见',
  admin_opinion TEXT COMMENT '管理员意见',
  status INT DEFAULT 0 COMMENT '状态：0待审核,1教师同意,2教师拒绝,3院校通过,4院校拒绝,5已录用,6未录用',
  apply_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '申请时间',
  is_deleted TINYINT DEFAULT 0 COMMENT '逻辑删除',
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  FOREIGN KEY (student_id) REFERENCES t_user(id),
  FOREIGN KEY (position_id) REFERENCES t_position(id),
  FOREIGN KEY (enterprise_id) REFERENCES t_enterprise(id),
  FOREIGN KEY (teacher_id) REFERENCES t_user(id),
  INDEX idx_student (student_id),
  INDEX idx_position (position_id),
  INDEX idx_teacher (teacher_id),
  INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '申请表';

-- 实习报告表
CREATE TABLE IF NOT EXISTS t_report (
  id INT AUTO_INCREMENT PRIMARY KEY,
  application_id INT NOT NULL COMMENT '申请ID',
  student_id INT NOT NULL COMMENT '学生ID',
  title VARCHAR(200) NOT NULL COMMENT '报告标题',
  content LONGTEXT COMMENT '报告内容',
  file_url VARCHAR(255) COMMENT '报告附件URL',
  teacher_score INT COMMENT '教师评分（0-100）',
  teacher_comment TEXT COMMENT '教师评语',
  status INT DEFAULT 0 COMMENT '状态：0草稿,1已提交,2已评阅',
  submit_time DATETIME COMMENT '提交时间',
  is_deleted TINYINT DEFAULT 0 COMMENT '逻辑删除',
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  FOREIGN KEY (application_id) REFERENCES t_application(id),
  FOREIGN KEY (student_id) REFERENCES t_user(id),
  INDEX idx_application (application_id),
  INDEX idx_student (student_id),
  INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '实习报告表';

-- 通知表
CREATE TABLE IF NOT EXISTS t_notification (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL COMMENT '用户ID',
  title VARCHAR(100) NOT NULL COMMENT '通知标题',
  content TEXT NOT NULL COMMENT '通知内容',
  type VARCHAR(30) DEFAULT 'info' COMMENT '通知类型：info,warning,success,error',
  is_read TINYINT DEFAULT 0 COMMENT '是否已读',
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  FOREIGN KEY (user_id) REFERENCES t_user(id),
  INDEX idx_user (user_id),
  INDEX idx_is_read (is_read)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '通知表';

-- 初始数据：创建超级管理员账户
INSERT INTO t_user (username, password, real_name, role, status)
VALUES ('admin', '$2a$10$W9bAM9wKWFSLYCrKRXDvFe2oPCxGxNGwLKBH5FI3sJhKD0F/uZJy6', '系统管理员', 1, 1)
ON DUPLICATE KEY UPDATE role=VALUES(role);

-- 创建默认学院和专业（示例数据）
INSERT IGNORE INTO t_college (name, code, description, status) VALUES 
('工程学院', 'ENG', '工程类专业学院', 1),
('文理学院', 'ARTS', '文理类专业学院', 1);

INSERT IGNORE INTO t_major (college_id, name, code) VALUES
(1, '计算机科学与技术', 'CS'),
(1, '软件工程', 'SE'),
(2, '英语', 'EN');

INSERT IGNORE INTO t_class (college_id, major_id, name, grade, status) VALUES
(1, 1, '2024级计算机一班', 2024, 1),
(1, 2, '2024级软件一班', 2024, 1),
(2, 3, '2024级英语班', 2024, 1);

INSERT IGNORE INTO t_user (username, password, real_name, phone, email, role, college_id, major_id, class_id, eeid, status) VALUES
('teacher1', '$2a$10$W9bAM9wKWFSLYCrKRXDvFe2oPCxGxNGwLKBH5FI3sJhKD0F/uZJy6', '指导教师张老师', '13800138001', 'teacher1@example.com', 3, 1, 1, 1, 'T1001', 1),
('student1', '$2a$10$W9bAM9wKWFSLYCrKRXDvFe2oPCxGxNGwLKBH5FI3sJhKD0F/uZJy6', '学生李明', '13800138002', 'student1@example.com', 4, 1, 1, 1, 'S1001', 1),
('student2', '$2a$10$W9bAM9wKWFSLYCrKRXDvFe2oPCxGxNGwLKBH5FI3sJhKD0F/uZJy6', '学生王芳', '13800138003', 'student2@example.com', 4, 1, 2, 2, 'S1002', 1);

INSERT IGNORE INTO t_enterprise (name, short_name, industry, address, contact_name, contact_phone, description, status) VALUES
('杭州软件科技有限公司', '杭州软件', '软件', '杭州市西湖区', '陈经理', '0571-12345678', '提供校企实习岗位的互联网企业', 1),
('上海外语培训中心', '上海外语', '教育', '上海市浦东新区', '刘老师', '021-87654321', '面向英语专业学生的实习机构', 1);

INSERT IGNORE INTO t_position (enterprise_id, title, description, requirement, salary, headcount, location, start_date, end_date, college_id, status) VALUES
(1, 'Web开发实习生', '参与后台开发与前端维护', '熟悉JavaScript、Node.js', '3000/月', 2, '杭州', '2024-07-01', '2024-12-31', 1, 1),
(1, '软件测试实习生', '负责测试案例编写与执行', '细心、熟悉测试流程', '2800/月', 1, '杭州', '2024-07-10', '2024-12-31', 1, 1),
(2, '英语助教实习生', '协助教学与资料整理', '英语四级及以上', '2500/月', 1, '上海', '2024-07-05', '2024-12-31', 2, 1);

INSERT IGNORE INTO t_application (student_id, position_id, enterprise_id, teacher_id, student_remark, teacher_opinion, admin_opinion, status) VALUES
(3, 1, 1, 2, '希望锻炼项目经验', '同意申请', '通过初审', 3),
(4, 2, 1, 2, '希望了解测试流程', '同意申请', '待复审', 1);

INSERT IGNORE INTO t_report (application_id, student_id, title, content, file_url, teacher_score, teacher_comment, status, submit_time) VALUES
(1, 3, '第一周实习报告', '本周完成了任务需求分析与接口设计。', '/uploads/report1.docx', 85, '内容良好，继续加油', 2, '2024-07-15 10:00:00');

INSERT IGNORE INTO t_notification (user_id, title, content, type, is_read) VALUES
(1, '系统初始化完成', '管理员账户和测试数据已创建', 'success', 0),
(2, '您有新的学生申请', '学生李明提交了申请，请尽快审核', 'info', 0),
(3, '申请通过通知', '您的实习申请已通过院校审核', 'success', 0),
(4, '岗位更新提醒', '软件测试实习生岗位已更新', 'info', 0);
