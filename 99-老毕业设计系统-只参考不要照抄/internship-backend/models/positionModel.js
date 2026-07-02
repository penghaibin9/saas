const pool = require('../config/db');

const positionModel = {
  async findAll({ enterpriseId, collegeId, status, keyword, internType } = {}, { page = 1, pageSize = 20 } = {}) {
    const offset = (page - 1) * pageSize;
    let where = 'WHERE p.is_deleted = 0';
    const params = [];
    if (enterpriseId !== undefined) { where += ' AND p.enterprise_id = ?'; params.push(enterpriseId); }
    if (collegeId !== undefined)    { where += ' AND (p.college_id = ? OR p.college_id IS NULL)'; params.push(collegeId); }
    if (status !== undefined)       { where += ' AND p.status = ?'; params.push(status); }
    if (internType !== undefined)   { where += ' AND p.intern_type = ?'; params.push(internType); }
    if (keyword) {
      where += ' AND (p.title LIKE ? OR e.name LIKE ?)';
      params.push(`%${keyword}%`, `%${keyword}%`);
    }

    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_position p
       LEFT JOIN t_enterprise e ON p.enterprise_id = e.id ${where}`,
      params
    );
    const [rows] = await pool.query(
      `SELECT p.*, e.name AS enterprise_name, e.short_name AS enterprise_short_name
       FROM t_position p
       LEFT JOIN t_enterprise e ON p.enterprise_id = e.id
       ${where} ORDER BY p.create_time DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  async findById(id) {
    const [rows] = await pool.query(
      `SELECT p.*, e.name AS enterprise_name, e.short_name AS enterprise_short_name
       FROM t_position p
       LEFT JOIN t_enterprise e ON p.enterprise_id = e.id
       WHERE p.id = ? AND p.is_deleted = 0`,
      [id]
    );
    return rows[0] || null;
  },

  async create({ enterprise_id, title, description, requirement, salary, headcount, location, start_date, end_date, college_id, tags, intern_type, major_req, edu_req, work_time, welfare, to_regular, deadline }) {
    const [result] = await pool.query(
      `INSERT INTO t_position
        (enterprise_id, title, description, requirement, salary, headcount, location, start_date, end_date, college_id, tags,
         intern_type, major_req, edu_req, work_time, welfare, to_regular, deadline)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [enterprise_id, title, description || null, requirement || null, salary || null,
       headcount || 1, location || null, start_date || null, end_date || null, college_id || null, tags || null,
       intern_type || null, major_req || null, edu_req || null, work_time || null, welfare || null, to_regular ? 1 : 0, deadline || null]
    );
    return result.insertId;
  },

  // 岗位智能匹配：按标签重合度 + 专业/学院相关性 + 在招状态打分排序
  async recommendForStudent(student, limit = 10) {
    const [rows] = await pool.query(
      `SELECT p.*, e.name AS enterprise_name, e.short_name AS enterprise_short_name
       FROM t_position p
       LEFT JOIN t_enterprise e ON p.enterprise_id = e.id
       WHERE p.is_deleted = 0 AND p.status = 1
         AND (p.college_id IS NULL OR p.college_id = ?)
       ORDER BY p.create_time DESC LIMIT 200`,
      [student.college_id || null]
    );
    const stuTags = String(student.skill_tags || '').split(/[,，;；\s]+/).map(t => t.trim().toLowerCase()).filter(Boolean);
    const scored = rows.map(p => {
      const posTags = String(p.tags || '').split(/[,，;；\s]+/).map(t => t.trim().toLowerCase()).filter(Boolean);
      let overlap = 0;
      for (const t of stuTags) if (posTags.includes(t)) overlap++;
      let score = overlap * 30;
      const matchTags = posTags.filter(t => stuTags.includes(t));
      // 同学院加成；岗位文本命中学生标签加成
      if (p.college_id && student.college_id && p.college_id === student.college_id) score += 15;
      const text = `${p.title || ''} ${p.requirement || ''} ${p.description || ''}`.toLowerCase();
      for (const t of stuTags) if (t && text.includes(t)) score += 5;
      return Object.assign({}, p, { match_score: score, match_tags: matchTags });
    });
    scored.sort((a, b) => b.match_score - a.match_score || b.id - a.id);
    return scored.slice(0, limit);
  },

  async update(id, fields) {
    const allowed = ['enterprise_id','title','description','requirement','salary','headcount','location','start_date','end_date','college_id','status','tags','intern_type','major_req','edu_req','work_time','welfare','to_regular','deadline'];
    const setClauses = [];
    const params = [];
    for (const key of allowed) {
      if (fields[key] !== undefined) { setClauses.push(`${key} = ?`); params.push(fields[key]); }
    }
    if (!setClauses.length) return 0;
    params.push(id);
    const [result] = await pool.query(
      `UPDATE t_position SET ${setClauses.join(', ')} WHERE id = ? AND is_deleted = 0`,
      params
    );
    return result.affectedRows;
  },

  async remove(id) {
    const [result] = await pool.query(
      'UPDATE t_position SET is_deleted = 1 WHERE id = ?',
      [id]
    );
    return result.affectedRows;
  }
};

module.exports = positionModel;
