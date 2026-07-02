-- ============================================================
-- 毕业设计 + 岗位实习管理平台 —— 本轮新增/修改表结构汇总
-- 说明：建议用 `npm run migrate:all`（幂等、安全）执行；
--       本文件供查阅与论文附录使用。ALTER 语句仅可执行一次。
-- 数据库：internship_management  字符集：utf8mb4  引擎：InnoDB
-- ============================================================
USE internship_management;

-- ---------- 用户表新增字段：强制首次改密 ----------
ALTER TABLE t_user
  ADD COLUMN must_change_password TINYINT DEFAULT 0
  COMMENT '是否需要强制修改密码：1是,0否' AFTER status;

-- ---------- 企业表新增字段：实习单位坐标 + 打卡范围 ----------
ALTER TABLE t_enterprise
  ADD COLUMN longitude DECIMAL(10,6) NULL COMMENT '经度' AFTER description,
  ADD COLUMN latitude  DECIMAL(10,6) NULL COMMENT '纬度' AFTER longitude,
  ADD COLUMN checkin_radius INT DEFAULT 0 COMMENT '打卡有效半径(米)，0为不约束' AFTER latitude;

-- ============================================================
-- 岗位实习子系统
-- ============================================================

-- 实习计划
CREATE TABLE IF NOT EXISTS t_intern_plan (
  id INT AUTO_INCREMENT PRIMARY KEY,
  college_id INT NOT NULL COMMENT '所属分院',
  major_id INT COMMENT '限定专业(null=全院)',
  class_id INT COMMENT '限定班级(null=不限)',
  title VARCHAR(200) NOT NULL COMMENT '计划标题',
  start_date DATE, end_date DATE,
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
  INDEX idx_college (college_id), INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '实习计划表';

-- 实习分配
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
  INDEX idx_plan (plan_id), INDEX idx_student (student_id),
  INDEX idx_teacher (teacher_id), INDEX idx_enterprise (enterprise_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '实习分配表';

-- 打卡签到
CREATE TABLE IF NOT EXISTS t_checkin (
  id INT AUTO_INCREMENT PRIMARY KEY,
  student_id INT NOT NULL COMMENT '学生',
  assignment_id INT COMMENT '关联分配',
  enterprise_id INT COMMENT '打卡对应企业',
  latitude DECIMAL(10,6), longitude DECIMAL(10,6),
  distance INT COMMENT '距企业坐标(米)',
  within_range TINYINT DEFAULT 1 COMMENT '是否在有效范围内',
  address VARCHAR(255), remark VARCHAR(255),
  checkin_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_student (student_id), INDEX idx_checkin_time (checkin_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '打卡签到表';

-- 实习周报/月报
CREATE TABLE IF NOT EXISTS t_intern_log (
  id INT AUTO_INCREMENT PRIMARY KEY,
  student_id INT NOT NULL, assignment_id INT, plan_id INT, teacher_id INT,
  type VARCHAR(10) NOT NULL DEFAULT 'weekly' COMMENT 'weekly周报,monthly月报',
  title VARCHAR(200) NOT NULL, content LONGTEXT, file_url VARCHAR(255),
  status TINYINT DEFAULT 0 COMMENT '0草稿,1提交,2通过,3驳回',
  teacher_comment TEXT, reject_reason VARCHAR(255),
  submit_time DATETIME, review_time DATETIME,
  is_deleted TINYINT DEFAULT 0,
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_student (student_id), INDEX idx_teacher (teacher_id),
  INDEX idx_type (type), INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '实习周报/月报表';

-- 请假申请
CREATE TABLE IF NOT EXISTS t_leave (
  id INT AUTO_INCREMENT PRIMARY KEY,
  student_id INT NOT NULL, assignment_id INT, teacher_id INT,
  start_date DATE, end_date DATE, days DECIMAL(4,1),
  reason TEXT, status TINYINT DEFAULT 0 COMMENT '0草稿,1提交,2通过,3驳回',
  reject_reason VARCHAR(255), submit_time DATETIME, review_time DATETIME,
  is_deleted TINYINT DEFAULT 0,
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_student (student_id), INDEX idx_teacher (teacher_id), INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '请假申请表';

-- 实习保险单
CREATE TABLE IF NOT EXISTS t_insurance (
  id INT AUTO_INCREMENT PRIMARY KEY,
  student_id INT NOT NULL, insurance_type VARCHAR(100), policy_no VARCHAR(100),
  company VARCHAR(200), start_date DATE, end_date DATE, college_id INT, remark VARCHAR(255),
  is_deleted TINYINT DEFAULT 0,
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_student (student_id), INDEX idx_college (college_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '实习保险单表';

-- ============================================================
-- 毕业设计子系统
-- ============================================================

-- 公示信息/通知公告
CREATE TABLE IF NOT EXISTS t_announcement (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(200) NOT NULL,
  category VARCHAR(50) DEFAULT '公示信息',
  content LONGTEXT, file_url VARCHAR(255), college_id INT, publisher_id INT,
  status TINYINT DEFAULT 1 COMMENT '1发布,0草稿', publish_time DATETIME,
  is_deleted TINYINT DEFAULT 0,
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_category (category), INDEX idx_college (college_id), INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '公示信息/通知公告表';

-- 毕设任务时间节点
CREATE TABLE IF NOT EXISTS t_gd_task (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(200) NOT NULL, parent_id INT, scope VARCHAR(100), college_id INT,
  require_time DATE, actual_time DATE, description TEXT,
  status TINYINT DEFAULT 0 COMMENT '0未开始,1进行中,2已完成', sort_order INT DEFAULT 0,
  is_deleted TINYINT DEFAULT 0,
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_parent (parent_id), INDEX idx_college (college_id), INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '毕业设计任务时间节点表';

-- 选题与指导老师
CREATE TABLE IF NOT EXISTS t_gd_topic (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(200) NOT NULL, student_id INT, teacher_id INT,
  college_id INT, major_id INT, class_id INT,
  source VARCHAR(100), type VARCHAR(100), description TEXT,
  status TINYINT DEFAULT 0 COMMENT '0待确认,1已指派,2已确认',
  is_deleted TINYINT DEFAULT 0,
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_student (student_id), INDEX idx_teacher (teacher_id), INDEX idx_college (college_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '毕业设计选题及指导老师表';

-- 成绩（每生唯一）
CREATE TABLE IF NOT EXISTS t_gd_grade (
  id INT AUTO_INCREMENT PRIMARY KEY,
  student_id INT NOT NULL, topic_id INT, teacher_id INT, class_id INT,
  topic_title VARCHAR(200),
  review_score DECIMAL(5,2), defense_score DECIMAL(5,2), total_score DECIMAL(5,2),
  remark VARCHAR(255), is_deleted TINYINT DEFAULT 0,
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uniq_student (student_id), INDEX idx_teacher (teacher_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '毕业设计成绩表';

-- 设计成果上传/审阅
CREATE TABLE IF NOT EXISTS t_gd_achievement (
  id INT AUTO_INCREMENT PRIMARY KEY,
  student_id INT NOT NULL, topic_id INT, teacher_id INT,
  title VARCHAR(200) NOT NULL, link VARCHAR(500), file_url VARCHAR(255),
  status TINYINT DEFAULT 0 COMMENT '0待审阅,1通过,2驳回,3未完成',
  reject_reason VARCHAR(255), submit_time DATETIME, review_time DATETIME,
  is_deleted TINYINT DEFAULT 0,
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_student (student_id), INDEX idx_teacher (teacher_id), INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '毕业设计成果表';

-- 质量监控/互查
CREATE TABLE IF NOT EXISTS t_quality_check (
  id INT AUTO_INCREMENT PRIMARY KEY,
  batch_name VARCHAR(200) NOT NULL,
  check_type VARCHAR(10) DEFAULT 'census' COMMENT 'census普查,sample抽查',
  scope VARCHAR(10) DEFAULT 'cross' COMMENT 'self自查,cross互查',
  checker_id INT, student_id INT NOT NULL, achievement_id INT, college_id INT,
  status TINYINT DEFAULT 0 COMMENT '0待审阅,1通过,2驳回,3未完成',
  opinion VARCHAR(500), review_time DATETIME,
  is_deleted TINYINT DEFAULT 0,
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_checker (checker_id), INDEX idx_student (student_id),
  INDEX idx_college (college_id), INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '毕业设计质量监控/互查表';

-- 毕业设计指导记录
CREATE TABLE IF NOT EXISTS t_gd_guidance (
  id INT AUTO_INCREMENT PRIMARY KEY,
  topic_id INT, student_id INT NOT NULL, teacher_id INT NOT NULL, college_id INT,
  title VARCHAR(200), content TEXT, guidance_date DATE, file_url VARCHAR(255),
  is_deleted TINYINT DEFAULT 0,
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_student (student_id), INDEX idx_teacher (teacher_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '毕业设计指导记录表';

-- 企业满意度评价
CREATE TABLE IF NOT EXISTS t_satisfaction (
  id INT AUTO_INCREMENT PRIMARY KEY,
  enterprise_id INT NOT NULL, student_id INT, college_id INT,
  score TINYINT NOT NULL COMMENT '满意度评分 1-5', content VARCHAR(500), created_by INT,
  is_deleted TINYINT DEFAULT 0,
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_enterprise (enterprise_id), INDEX idx_college (college_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '企业满意度评价表';

-- 教师月报/寻访记录
CREATE TABLE IF NOT EXISTS t_teacher_record (
  id INT AUTO_INCREMENT PRIMARY KEY,
  teacher_id INT NOT NULL, type VARCHAR(10) NOT NULL DEFAULT 'monthly' COMMENT 'monthly月报,visit寻访',
  title VARCHAR(200) NOT NULL, content LONGTEXT, file_url VARCHAR(255), record_date DATE,
  student_id INT, enterprise_id INT, college_id INT,
  status TINYINT DEFAULT 0 COMMENT '0草稿,1已提交',
  is_deleted TINYINT DEFAULT 0,
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_teacher (teacher_id), INDEX idx_type (type), INDEX idx_college (college_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '教师工作记录(月报/寻访)表';

-- 省厅毕业生名单
CREATE TABLE IF NOT EXISTS t_province_student (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL, gender VARCHAR(10), id_card VARCHAR(30), eeid VARCHAR(50),
  cert_no VARCHAR(50), edu_system VARCHAR(20), major_code VARCHAR(50), major_name VARCHAR(100),
  batch_year INT, matched TINYINT DEFAULT 0, local_student_id INT,
  achievement_link VARCHAR(500), uploaded TINYINT DEFAULT 0, upload_time DATETIME,
  is_deleted TINYINT DEFAULT 0,
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_eeid (eeid), INDEX idx_matched (matched)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '省厅毕业生名单表';
