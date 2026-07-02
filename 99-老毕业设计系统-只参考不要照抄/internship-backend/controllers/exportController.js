const path = require('path');
const XLSX = require('xlsx');
const multer = require('multer');
const pwdHash = require('../utils/password');
const pool = require('../config/db');
const { internStatsModel } = require('../models');
const { success, error } = require('../utils/response');
const { isValidEmail, isValidPhone } = require('../utils/validate');

const MAX_IMPORT_ROWS = 1000;

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 5 * 1024 * 1024 },
  fileFilter: (req, file, cb) => {
    const ext = path.extname(file.originalname).toLowerCase();
    if (['.xlsx', '.xls'].includes(ext)) cb(null, true);
    else cb(new Error('仅支持 .xlsx / .xls 格式的 Excel 文件'));
  }
});

function toExcelBuffer(data, sheetName) {
  const ws = XLSX.utils.json_to_sheet(data);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, sheetName);
  return XLSX.write(wb, { type: 'buffer', bookType: 'xlsx' });
}

const exportController = {
  // 导出申请列表
  async exportApplications(req, res) {
    try {
      const { status, page_size = 5000 } = req.query;
      let where = 'WHERE a.is_deleted = 0';
      const params = [];
      if (status !== undefined) { where += ' AND a.status = ?'; params.push(Number(status)); }
      if (req.user.role === 3)  { where += ' AND a.teacher_id = ?'; params.push(req.user.id); }
      if (req.user.role === 4)  { where += ' AND a.student_id = ?'; params.push(req.user.id); }
      if (req.user.role === 2 && req.user.collegeId) { where += ' AND u.college_id = ?'; params.push(req.user.collegeId); }

      const statusMap = { 0:'待审核', 1:'教师同意', 2:'教师拒绝', 3:'院校通过', 4:'院校拒绝', 5:'已录用', 6:'未录用' };
      const [rows] = await pool.query(
        `SELECT u.real_name AS 学生姓名, u.eeid AS 学号,
                p.title AS 申请岗位, e.name AS 企业名称,
                a.status AS _status,
                DATE_FORMAT(a.apply_time,'%Y-%m-%d') AS 申请日期,
                t.real_name AS 指导教师,
                a.student_remark AS 学生备注,
                a.teacher_opinion AS 教师意见,
                a.admin_opinion AS 管理员意见
         FROM t_application a
         LEFT JOIN t_user u       ON a.student_id   = u.id
         LEFT JOIN t_position p   ON a.position_id  = p.id
         LEFT JOIN t_enterprise e ON a.enterprise_id = e.id
         LEFT JOIN t_user t       ON a.teacher_id   = t.id
         ${where} ORDER BY a.apply_time DESC LIMIT ?`,
        [...params, Number(page_size)]
      );
      const data = rows.map(r => ({ ...r, 审核状态: statusMap[r._status] || r._status, _status: undefined }));

      const buf = toExcelBuffer(data, '申请列表');
      res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      res.setHeader('Content-Disposition', 'attachment; filename="applications.xlsx"');
      return res.send(buf);
    } catch (err) {
      return error(res, '导出失败：' + err.message, 500);
    }
  },

  // 导出用户列表（可选 ?role=3|4 按角色导出；分院管理员仅本学院）
  async exportUsers(req, res) {
    try {
      const roleMap = { 1:'院校管理员', 2:'分院管理员', 3:'指导教师', 4:'学生' };
      let where = 'WHERE u.is_deleted = 0';
      const params = [];
      if (req.query.role !== undefined) {
        where += ' AND u.role = ?';
        params.push(Number(req.query.role));
      }
      if (req.user.role === 2 && req.user.collegeId) {
        where += ' AND u.college_id = ?';
        params.push(req.user.collegeId);
      }
      const [rows] = await pool.query(
        `SELECT u.username AS 用户名, u.real_name AS 姓名, u.eeid AS 学工号,
                u.role AS _role, u.phone AS 手机号, u.email AS 邮箱,
                c.name AS 学院, m.name AS 专业, cl.name AS 班级,
                IF(u.status=1,'启用','禁用') AS 状态,
                DATE_FORMAT(u.create_time,'%Y-%m-%d') AS 注册日期
         FROM t_user u
         LEFT JOIN t_college c  ON u.college_id = c.id
         LEFT JOIN t_major m    ON u.major_id   = m.id
         LEFT JOIN t_class cl   ON u.class_id   = cl.id
         ${where} ORDER BY u.role, u.create_time`,
        params
      );
      const data = rows.map(r => ({ ...r, 角色: roleMap[r._role] || r._role, _role: undefined }));
      const roleNum = req.query.role !== undefined ? Number(req.query.role) : null;
      const sheetName = roleNum === 4 ? '学生档案' : roleNum === 3 ? '教师档案' : '用户列表';
      const filename = roleNum === 4 ? 'students.xlsx' : roleNum === 3 ? 'teachers.xlsx' : 'users.xlsx';

      const buf = toExcelBuffer(data, sheetName);
      res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
      return res.send(buf);
    } catch (err) {
      return error(res, '导出失败：' + err.message, 500);
    }
  },

  // 导出报告列表
  async exportReports(req, res) {
    try {
      const statusMap = { 0:'草稿', 1:'已提交', 2:'已评阅' };
      let where = 'WHERE r.is_deleted = 0';
      const params = [];
      if (req.user.role === 3)  { where += ' AND a.teacher_id = ?'; params.push(req.user.id); }
      if (req.user.role === 4)  { where += ' AND a.student_id = ?'; params.push(req.user.id); }

      const [rows] = await pool.query(
        `SELECT u.real_name AS 学生姓名, u.eeid AS 学号,
                r.title AS 报告标题, r.status AS _status,
                r.teacher_score AS 教师评分, r.teacher_comment AS 教师评语,
                DATE_FORMAT(r.submit_time,'%Y-%m-%d') AS 提交时间,
                p.title AS 实习岗位, e.name AS 企业名称
         FROM t_report r
         JOIN t_application a ON r.application_id=a.id
         LEFT JOIN t_user u       ON a.student_id=u.id
         LEFT JOIN t_position p   ON a.position_id=p.id
         LEFT JOIN t_enterprise e ON a.enterprise_id=e.id
         ${where} ORDER BY r.submit_time DESC LIMIT 5000`,
        params
      );
      const data = rows.map(r => ({ ...r, 状态: statusMap[r._status] || r._status, _status: undefined }));

      const buf = toExcelBuffer(data, '报告列表');
      res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      res.setHeader('Content-Disposition', 'attachment; filename="reports.xlsx"');
      return res.send(buf);
    } catch (err) {
      return error(res, '导出失败：' + err.message, 500);
    }
  },

  // 导出实习学生档案（逐学生实习过程汇总）
  async exportInternArchive(req, res) {
    try {
      const { list } = await internStatsModel.processStats(req.user, { page: 1, pageSize: 5000 });
      const data = list.map(r => ({
        学号: r.student_eeid,
        姓名: r.student_name,
        实习企业: r.enterprise_name,
        指导老师: r.teacher_name,
        已签到次数: r.checkin_count,
        要求签到次数: r.req_checkin ?? '-',
        已交周报: r.weekly_count,
        要求周报: r.req_weekly ?? '-',
        已交月报: r.monthly_count,
        要求月报: r.req_monthly ?? '-',
        最近签到: r.last_checkin ? new Date(r.last_checkin).toLocaleString('zh-CN') : '未签到'
      }));
      const buf = toExcelBuffer(data, '实习学生档案');
      res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      res.setHeader('Content-Disposition', 'attachment; filename="intern_archive.xlsx"');
      return res.send(buf);
    } catch (err) {
      return error(res, '导出实习档案失败：' + err.message, 500);
    }
  },

  // 导出实习分配名单
  async exportAssignments(req, res) {
    try {
      let where = 'WHERE a.is_deleted = 0 AND a.status = 1';
      const params = [];
      if (req.user.role === 2) { where += ' AND s.college_id = ?'; params.push(req.user.collegeId); }
      if (req.user.role === 3) { where += ' AND a.teacher_id = ?'; params.push(req.user.id); }
      const [rows] = await pool.query(
        `SELECT s.real_name AS 学生姓名, s.eeid AS 学号, t.real_name AS 指导老师,
                e.name AS 实习企业, p.title AS 实习计划,
                DATE_FORMAT(a.create_time,'%Y-%m-%d') AS 分配时间
         FROM t_assignment a
         LEFT JOIN t_user s ON a.student_id = s.id
         LEFT JOIN t_user t ON a.teacher_id = t.id
         LEFT JOIN t_enterprise e ON a.enterprise_id = e.id
         LEFT JOIN t_intern_plan p ON a.plan_id = p.id
         ${where} ORDER BY s.eeid LIMIT 10000`, params);
      const buf = toExcelBuffer(rows, '实习分配');
      res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      res.setHeader('Content-Disposition', 'attachment; filename="assignments.xlsx"');
      return res.send(buf);
    } catch (err) {
      return error(res, '导出失败：' + err.message, 500);
    }
  },

  // 导出打卡记录
  async exportCheckins(req, res) {
    try {
      let where = 'WHERE 1=1';
      const params = [];
      if (req.user.role === 2) { where += ' AND s.college_id = ?'; params.push(req.user.collegeId); }
      if (req.user.role === 3) { where += ' AND a.teacher_id = ?'; params.push(req.user.id); }
      const [rows] = await pool.query(
        `SELECT s.real_name AS 学生姓名, s.eeid AS 学号, e.name AS 企业,
                DATE_FORMAT(ck.checkin_time,'%Y-%m-%d %H:%i') AS 打卡时间,
                ck.distance AS 距离米, IF(ck.within_range=1,'有效','超范围') AS 状态,
                ck.address AS 地址
         FROM t_checkin ck
         LEFT JOIN t_user s ON ck.student_id = s.id
         LEFT JOIN t_enterprise e ON ck.enterprise_id = e.id
         LEFT JOIN t_assignment a ON ck.assignment_id = a.id
         ${where} ORDER BY ck.checkin_time DESC LIMIT 10000`, params);
      const buf = toExcelBuffer(rows, '打卡记录');
      res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      res.setHeader('Content-Disposition', 'attachment; filename="checkins.xlsx"');
      return res.send(buf);
    } catch (err) {
      return error(res, '导出失败：' + err.message, 500);
    }
  },

  // 导出毕业设计选题及指导老师一览表
  async exportGdTopics(req, res) {
    try {
      let where = 'WHERE tp.is_deleted = 0';
      const params = [];
      if (req.user.role === 2) { where += ' AND tp.college_id = ?'; params.push(req.user.collegeId); }
      if (req.user.role === 3) { where += ' AND tp.teacher_id = ?'; params.push(req.user.id); }
      const [rows] = await pool.query(
        `SELECT s.real_name AS 学生姓名, s.eeid AS 学号, tp.title AS 选题名称,
                t.real_name AS 指导老师, tp.source AS 课题来源, tp.type AS 课题类型,
                cl.name AS 班级
         FROM t_gd_topic tp
         LEFT JOIN t_user s ON tp.student_id = s.id
         LEFT JOIN t_user t ON tp.teacher_id = t.id
         LEFT JOIN t_class cl ON tp.class_id = cl.id
         ${where} ORDER BY cl.name, s.eeid LIMIT 10000`, params);
      const buf = toExcelBuffer(rows, '选题及指导老师一览表');
      res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      res.setHeader('Content-Disposition', 'attachment; filename="gd_topics.xlsx"');
      return res.send(buf);
    } catch (err) {
      return error(res, '导出失败：' + err.message, 500);
    }
  },

  // 导出毕业设计成绩汇总表
  async exportGdGrades(req, res) {
    try {
      let where = 'WHERE g.is_deleted = 0';
      const params = [];
      if (req.user.role === 2) { where += ' AND s.college_id = ?'; params.push(req.user.collegeId); }
      if (req.user.role === 3) { where += ' AND g.teacher_id = ?'; params.push(req.user.id); }
      const [rows] = await pool.query(
        `SELECT s.real_name AS 学生姓名, s.eeid AS 学号, cl.name AS 班级,
                g.topic_title AS 选题名称, g.review_score AS 评阅成绩,
                g.defense_score AS 答辩成绩, g.total_score AS 综合成绩
         FROM t_gd_grade g
         LEFT JOIN t_user s ON g.student_id = s.id
         LEFT JOIN t_class cl ON g.class_id = cl.id
         ${where} ORDER BY cl.name, s.eeid LIMIT 10000`, params);
      const buf = toExcelBuffer(rows, '毕业设计成绩汇总');
      res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      res.setHeader('Content-Disposition', 'attachment; filename="gd_grades.xlsx"');
      return res.send(buf);
    } catch (err) {
      return error(res, '导出失败：' + err.message, 500);
    }
  },

  // 导入学生（Excel 批量创建）
  uploadMiddleware: upload.single('file'),

  async importStudents(req, res) {
    if (!req.file) return error(res, '请上传 Excel 文件', 400);

    let conn;
    try {
      const wb = XLSX.read(req.file.buffer, { type: 'buffer' });
      const ws = wb.Sheets[wb.SheetNames[0]];
      const rows = XLSX.utils.sheet_to_json(ws);

      if (!rows.length) return error(res, 'Excel 文件为空', 400);
      if (rows.length > MAX_IMPORT_ROWS) {
        return error(res, `单次最多导入 ${MAX_IMPORT_ROWS} 条，请分批导入`, 400);
      }

      const results = { success: 0, skip: 0, errors: [] };
      const defaultPwd = await pwdHash.hash('123456');
      // 分院管理员导入的学生归属本学院
      const collegeId = req.user.role === 2 ? req.user.collegeId : null;

      conn = await pool.getConnection();
      await conn.beginTransaction();

      for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        const lineNo = i + 2; // 含表头，数据从第 2 行起
        const username = String(row['用户名'] || row['username'] || '').trim();
        const realName = String(row['姓名'] || row['real_name'] || '').trim();
        const eeid     = String(row['学号']  || row['eeid']      || '').trim();
        const phone    = String(row['手机号'] || row['phone']     || '').trim();
        const email    = String(row['邮箱']  || row['email']     || '').trim();

        if (!username || !realName) { results.errors.push(`第 ${lineNo} 行：用户名或姓名为空`); continue; }
        if (phone && !isValidPhone(phone)) { results.errors.push(`第 ${lineNo} 行：手机号格式不正确`); continue; }
        if (email && !isValidEmail(email)) { results.errors.push(`第 ${lineNo} 行：邮箱格式不正确`); continue; }

        const [exist] = await conn.query(
          'SELECT id FROM t_user WHERE username = ? AND is_deleted = 0 LIMIT 1', [username]
        );
        if (exist.length) { results.skip++; continue; }

        // 学生账号默认密码 123456，首次登录强制改密
        await conn.query(
          `INSERT INTO t_user (username, password, real_name, phone, email, role, college_id, eeid, status, must_change_password)
           VALUES (?, ?, ?, ?, ?, 4, ?, ?, 1, 1)`,
          [username, defaultPwd, realName, phone || null, email || null, collegeId, eeid || null]
        );
        results.success++;
      }

      await conn.commit();
      return success(res, results, `导入完成：成功 ${results.success} 条，跳过 ${results.skip} 条，失败 ${results.errors.length} 条`);
    } catch (err) {
      if (conn) { try { await conn.rollback(); } catch (_) { /* ignore */ } }
      return error(res, '导入失败：' + err.message, 500);
    } finally {
      if (conn) conn.release();
    }
  },

  // 下载学生导入模板
  async downloadTemplate(req, res) {
    const data = [{ 用户名: 'stu001', 姓名: '张三', 学号: '20240001', 手机号: '13800000001', 邮箱: 'zhangsan@example.com' }];
    const buf = toExcelBuffer(data, '学生导入模板');
    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    res.setHeader('Content-Disposition', 'attachment; filename="student_import_template.xlsx"');
    return res.send(buf);
  },

  // 导入教师（Excel 批量创建）
  async importTeachers(req, res) {
    if (!req.file) return error(res, '请上传 Excel 文件', 400);

    let conn;
    try {
      const wb = XLSX.read(req.file.buffer, { type: 'buffer' });
      const ws = wb.Sheets[wb.SheetNames[0]];
      const rows = XLSX.utils.sheet_to_json(ws);

      if (!rows.length) return error(res, 'Excel 文件为空', 400);
      if (rows.length > MAX_IMPORT_ROWS) {
        return error(res, `单次最多导入 ${MAX_IMPORT_ROWS} 条，请分批导入`, 400);
      }

      const results = { success: 0, skip: 0, errors: [] };
      const defaultPwd = await pwdHash.hash('123456');
      const collegeId = req.user.role === 2 ? req.user.collegeId : null;

      conn = await pool.getConnection();
      await conn.beginTransaction();

      for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        const lineNo = i + 2;
        const username = String(row['用户名'] || row['username'] || '').trim();
        const realName = String(row['姓名'] || row['real_name'] || '').trim();
        const eeid     = String(row['工号']  || row['eeid']      || '').trim();
        const phone    = String(row['手机号'] || row['phone']     || '').trim();
        const email    = String(row['邮箱']  || row['email']     || '').trim();

        if (!username || !realName) { results.errors.push(`第 ${lineNo} 行：用户名或姓名为空`); continue; }
        if (phone && !isValidPhone(phone)) { results.errors.push(`第 ${lineNo} 行：手机号格式不正确`); continue; }
        if (email && !isValidEmail(email)) { results.errors.push(`第 ${lineNo} 行：邮箱格式不正确`); continue; }

        const [exist] = await conn.query(
          'SELECT id FROM t_user WHERE username = ? AND is_deleted = 0 LIMIT 1', [username]
        );
        if (exist.length) { results.skip++; continue; }

        await conn.query(
          `INSERT INTO t_user (username, password, real_name, phone, email, role, college_id, eeid, status, must_change_password)
           VALUES (?, ?, ?, ?, ?, 3, ?, ?, 1, 1)`,
          [username, defaultPwd, realName, phone || null, email || null, collegeId, eeid || null]
        );
        results.success++;
      }

      await conn.commit();
      return success(res, results, `导入完成：成功 ${results.success} 条，跳过 ${results.skip} 条，失败 ${results.errors.length} 条`);
    } catch (err) {
      if (conn) { try { await conn.rollback(); } catch (_) { /* ignore */ } }
      return error(res, '导入失败：' + err.message, 500);
    } finally {
      if (conn) conn.release();
    }
  },

  // 下载教师导入模板
  async downloadTeacherTemplate(req, res) {
    const data = [{ 用户名: 'tea001', 姓名: '李老师', 工号: 'T2024001', 手机号: '13900000001', 邮箱: 'teacher@example.com' }];
    const buf = toExcelBuffer(data, '教师导入模板');
    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    res.setHeader('Content-Disposition', 'attachment; filename="teacher_import_template.xlsx"');
    return res.send(buf);
  }
};

module.exports = exportController;
