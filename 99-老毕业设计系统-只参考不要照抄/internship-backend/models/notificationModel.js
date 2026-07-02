const pool = require('../config/db');

const notificationModel = {
  async ensureTable() {
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_notification (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        user_id     INT NOT NULL,
        title       VARCHAR(100) NOT NULL,
        content     TEXT NOT NULL,
        type        VARCHAR(30) DEFAULT 'info',
        is_read     TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT NOW(),
        INDEX idx_user (user_id)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    `);
  },

  async create({ user_id, title, content, type = 'info' }) {
    const [result] = await pool.query(
      `INSERT INTO t_notification (user_id, title, content, type) VALUES (?, ?, ?, ?)`,
      [user_id, title, content, type]
    );
    return result.insertId;
  },

  async findByUser(userId, { page = 1, pageSize = 20 } = {}) {
    const offset = (page - 1) * pageSize;
    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_notification WHERE user_id = ?`, [userId]
    );
    const [rows] = await pool.query(
      `SELECT * FROM t_notification WHERE user_id = ? ORDER BY create_time DESC LIMIT ? OFFSET ?`,
      [userId, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  async unreadCount(userId) {
    const [[{ cnt }]] = await pool.query(
      `SELECT COUNT(*) AS cnt FROM t_notification WHERE user_id = ? AND is_read = 0`, [userId]
    );
    return cnt;
  },

  async markRead(id, userId) {
    await pool.query(
      `UPDATE t_notification SET is_read = 1 WHERE id = ? AND user_id = ?`, [id, userId]
    );
  },

  async markAllRead(userId) {
    await pool.query(
      `UPDATE t_notification SET is_read = 1 WHERE user_id = ?`, [userId]
    );
  }
};

module.exports = notificationModel;
