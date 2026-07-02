const pool = require('../config/db');

// 答辩管理：分组 / 评委 / 答辩学生 / 评分。
const defenseModel = {
  /* ---------------- 答辩组 ---------------- */
  async listGroups({ collegeId, status, teacherId } = {}, { page = 1, pageSize = 50 } = {}) {
    const offset = (page - 1) * pageSize;
    let where = 'WHERE g.is_deleted = 0';
    const params = [];
    if (collegeId !== undefined) { where += ' AND g.college_id = ?'; params.push(collegeId); }
    if (status !== undefined)    { where += ' AND g.status = ?';     params.push(status); }
    let join = '';
    if (teacherId !== undefined) {
      join = 'JOIN t_defense_committee c ON c.group_id = g.id AND c.is_deleted = 0 AND c.teacher_id = ?';
      params.unshift(teacherId);
    }
    const [[{ total }]] = await pool.query(
      `SELECT COUNT(DISTINCT g.id) AS total FROM t_defense_group g ${join} ${where}`, params
    );
    const [rows] = await pool.query(
      `SELECT g.*,
         (SELECT COUNT(*) FROM t_defense_member m WHERE m.group_id = g.id AND m.is_deleted = 0) AS member_count,
         (SELECT COUNT(*) FROM t_defense_committee c2 WHERE c2.group_id = g.id AND c2.is_deleted = 0) AS judge_count
       FROM t_defense_group g ${join} ${where}
       ORDER BY g.defense_date DESC, g.id DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  async getGroup(id) {
    const [rows] = await pool.query('SELECT * FROM t_defense_group WHERE id = ? AND is_deleted = 0', [id]);
    return rows[0] || null;
  },
  async createGroup(g) {
    const [r] = await pool.query(
      `INSERT INTO t_defense_group (name, defense_date, location, college_id, remark, status)
       VALUES (?, ?, ?, ?, ?, 0)`,
      [g.name, g.defense_date || null, g.location || null, g.college_id || null, g.remark || null]
    );
    return r.insertId;
  },
  async updateGroup(id, f) {
    const allowed = ['name', 'defense_date', 'location', 'remark', 'status'];
    const set = [], params = [];
    for (const k of allowed) if (f[k] !== undefined) { set.push(`${k} = ?`); params.push(f[k]); }
    if (!set.length) return 0;
    params.push(id);
    const [r] = await pool.query(`UPDATE t_defense_group SET ${set.join(', ')} WHERE id = ? AND is_deleted = 0`, params);
    return r.affectedRows;
  },
  async removeGroup(id) {
    await pool.query('UPDATE t_defense_group SET is_deleted = 1 WHERE id = ?', [id]);
    await pool.query('UPDATE t_defense_committee SET is_deleted = 1 WHERE group_id = ?', [id]);
    await pool.query('UPDATE t_defense_member SET is_deleted = 1 WHERE group_id = ?', [id]);
  },

  /* ---------------- 评委 ---------------- */
  async listCommittee(groupId) {
    const [rows] = await pool.query(
      `SELECT c.*, t.real_name AS teacher_name FROM t_defense_committee c
       LEFT JOIN t_user t ON c.teacher_id = t.id
       WHERE c.group_id = ? AND c.is_deleted = 0 ORDER BY c.role, c.id`, [groupId]
    );
    return rows;
  },
  async addCommittee(groupId, teacherId, role) {
    await pool.query(
      `INSERT INTO t_defense_committee (group_id, teacher_id, role) VALUES (?, ?, ?)
       ON DUPLICATE KEY UPDATE role = VALUES(role), is_deleted = 0`,
      [groupId, teacherId, role || 'member']
    );
  },
  async removeCommittee(id) {
    await pool.query('UPDATE t_defense_committee SET is_deleted = 1 WHERE id = ?', [id]);
  },
  async isJudge(groupId, teacherId) {
    const [rows] = await pool.query(
      'SELECT id FROM t_defense_committee WHERE group_id = ? AND teacher_id = ? AND is_deleted = 0 LIMIT 1',
      [groupId, teacherId]
    );
    return rows.length > 0;
  },

  /* ---------------- 答辩学生 ---------------- */
  async listMembers(groupId) {
    const [rows] = await pool.query(
      `SELECT m.*, s.real_name AS student_name, s.eeid AS student_eeid, a.title AS achievement_title
       FROM t_defense_member m
       LEFT JOIN t_user s ON m.student_id = s.id
       LEFT JOIN t_gd_achievement a ON m.achievement_id = a.id
       WHERE m.group_id = ? AND m.is_deleted = 0 ORDER BY m.seq, m.id`, [groupId]
    );
    return rows;
  },
  async getMember(id) {
    const [rows] = await pool.query('SELECT * FROM t_defense_member WHERE id = ? AND is_deleted = 0', [id]);
    return rows[0] || null;
  },
  async addMember(groupId, studentId, achievementId, seq) {
    await pool.query(
      `INSERT INTO t_defense_member (group_id, student_id, achievement_id, seq) VALUES (?, ?, ?, ?)
       ON DUPLICATE KEY UPDATE achievement_id = VALUES(achievement_id), seq = VALUES(seq), is_deleted = 0`,
      [groupId, studentId, achievementId || null, seq || 0]
    );
  },
  async removeMember(id) {
    await pool.query('UPDATE t_defense_member SET is_deleted = 1 WHERE id = ?', [id]);
  },
  async setRecommended(id, val) {
    await pool.query('UPDATE t_defense_member SET recommended = ? WHERE id = ?', [val ? 1 : 0, id]);
  },

  /* ---------------- 评分 ---------------- */
  async upsertScore(groupId, studentId, judgeId, score, comment) {
    await pool.query(
      `INSERT INTO t_defense_score (group_id, student_id, judge_id, score, comment) VALUES (?, ?, ?, ?, ?)
       ON DUPLICATE KEY UPDATE score = VALUES(score), comment = VALUES(comment)`,
      [groupId, studentId, judgeId, score, comment || null]
    );
  },
  // 某评委对某组所有学生的评分（用于评分表回填，双盲下仅返回本人）
  async judgeScores(groupId, judgeId) {
    const [rows] = await pool.query(
      'SELECT student_id, score, comment FROM t_defense_score WHERE group_id = ? AND judge_id = ?',
      [groupId, judgeId]
    );
    const map = {};
    rows.forEach(r => { map[r.student_id] = { score: r.score, comment: r.comment }; });
    return map;
  },
  // 某学生全部评委评分（管理员视角）
  async studentScores(studentId) {
    const [rows] = await pool.query(
      `SELECT sc.*, t.real_name AS judge_name FROM t_defense_score sc
       LEFT JOIN t_user t ON sc.judge_id = t.id WHERE sc.student_id = ? ORDER BY sc.id`, [studentId]
    );
    return rows;
  },
  // 汇总：将每个学生的评委均分写入 final_score
  async finalizeGroup(groupId) {
    const [rows] = await pool.query(
      `SELECT student_id, ROUND(AVG(score), 2) AS avg_score, COUNT(*) AS n
       FROM t_defense_score WHERE group_id = ? GROUP BY student_id`, [groupId]
    );
    for (const r of rows) {
      await pool.query('UPDATE t_defense_member SET final_score = ? WHERE group_id = ? AND student_id = ?',
        [r.avg_score, groupId, r.student_id]);
    }
    await pool.query('UPDATE t_defense_group SET status = 2 WHERE id = ?', [groupId]);
    return rows.length;
  }
};

module.exports = defenseModel;
