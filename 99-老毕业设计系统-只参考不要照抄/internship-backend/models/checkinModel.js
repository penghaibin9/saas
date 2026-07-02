const pool = require('../config/db');

const checkinModel = {
  // 幂等增补反作弊列（精度/模拟定位/设备/风险）；查 information_schema 只补缺失的
  async ensureAntiCheatColumns() {
    const cols = [
      ['accuracy', 'INT NULL'],
      ['is_mock', 'TINYINT DEFAULT 0'],
      ['device_id', 'VARCHAR(128) NULL'],
      ['risk_level', "VARCHAR(10) DEFAULT 'none'"],
      ['risk_reason', 'VARCHAR(255) NULL'],
    ];
    for (const [name, def] of cols) {
      const [rows] = await pool.query(
        `SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 't_checkin' AND column_name = ? LIMIT 1`,
        [name]
      );
      if (!rows.length) await pool.query(`ALTER TABLE t_checkin ADD COLUMN ${name} ${def}`);
    }
  },

  async findAll({ studentId, enterpriseId, collegeId, teacherId, dateFrom, dateTo } = {}, { page = 1, pageSize = 20 } = {}) {
    const offset = (page - 1) * pageSize;
    let where = 'WHERE 1=1';
    const params = [];
    if (studentId !== undefined)    { where += ' AND ck.student_id = ?';    params.push(studentId); }
    if (enterpriseId !== undefined) { where += ' AND ck.enterprise_id = ?'; params.push(enterpriseId); }
    if (collegeId !== undefined)    { where += ' AND s.college_id = ?';     params.push(collegeId); }
    if (teacherId !== undefined)    { where += ' AND a.teacher_id = ?';     params.push(teacherId); }
    if (dateFrom)                   { where += ' AND ck.checkin_time >= ?'; params.push(dateFrom); }
    if (dateTo)                     { where += ' AND ck.checkin_time <= ?'; params.push(dateTo); }

    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_checkin ck
       LEFT JOIN t_user s ON ck.student_id = s.id
       LEFT JOIN t_assignment a ON ck.assignment_id = a.id ${where}`,
      params
    );
    const [rows] = await pool.query(
      `SELECT ck.*, s.real_name AS student_name, s.eeid AS student_eeid,
              e.name AS enterprise_name
       FROM t_checkin ck
       LEFT JOIN t_user s ON ck.student_id = s.id
       LEFT JOIN t_assignment a ON ck.assignment_id = a.id
       LEFT JOIN t_enterprise e ON ck.enterprise_id = e.id
       ${where} ORDER BY ck.checkin_time DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  async create({ student_id, assignment_id, enterprise_id, latitude, longitude, distance, within_range, address, photo_url, remark, checkin_time, slot,
                 accuracy, is_mock, device_id, risk_level, risk_reason }) {
    const [result] = await pool.query(
      `INSERT INTO t_checkin
        (student_id, assignment_id, enterprise_id, latitude, longitude, distance, within_range, address, photo_url, remark, slot, checkin_time,
         accuracy, is_mock, device_id, risk_level, risk_reason)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [student_id, assignment_id || null, enterprise_id || null,
       latitude ?? null, longitude ?? null, distance ?? null,
       within_range ? 1 : 0, address || null, photo_url || null, remark || null, slot || 'day', checkin_time || new Date(),
       accuracy ?? null, is_mock ? 1 : 0, device_id || null, risk_level || 'none', risk_reason || null]
    );
    return result.insertId;
  },

  // 取该学生最近一次有定位的打卡（用于位移突变检测）
  async findLastGeoByStudent(studentId) {
    const [rows] = await pool.query(
      `SELECT latitude, longitude, checkin_time FROM t_checkin
       WHERE student_id = ? AND latitude IS NOT NULL AND longitude IS NOT NULL
       ORDER BY checkin_time DESC LIMIT 1`, [studentId]
    );
    return rows[0] || null;
  },

  // 当天指定班次是否已打卡（slot: day=全天一次 / am=上午/上班 / pm=下午/下班）
  async hasCheckedInToday(studentId, slot = 'day') {
    const [rows] = await pool.query(
      `SELECT id FROM t_checkin
       WHERE student_id = ? AND DATE(checkin_time) = CURDATE() AND (slot = ? OR (? = 'day' AND slot IS NULL)) LIMIT 1`,
      [studentId, slot, slot]
    );
    return rows.length > 0;
  },

  async countByStudent(studentId) {
    const [[{ total }]] = await pool.query(
      'SELECT COUNT(*) AS total FROM t_checkin WHERE student_id = ?', [studentId]
    );
    return total;
  }
};

module.exports = checkinModel;
