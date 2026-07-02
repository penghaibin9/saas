const pool = require('../config/db');

/**
 * 数据报送模型（面向省级/全国职业院校实习管理平台的标准报送包）
 * 与 filingModel（逐生备案/回执）互补：此处负责把在册实习学生汇聚成一份
 * "标准字段映射"的报送数据集，供导出标准报送包或经配置的网关推送上报。
 */

// 标准报送字段映射：内部字段 -> 报送列名（可按各省模板调整）
const FIELD_MAP = [
  { key: 'eeid', label: '学号' },
  { key: 'student_name', label: '姓名' },
  { key: 'phone', label: '联系电话' },
  { key: 'college_name', label: '学院/分院' },
  { key: 'major_name', label: '专业' },
  { key: 'class_name', label: '班级' },
  { key: 'enterprise_name', label: '实习单位' },
  { key: 'teacher_name', label: '指导教师' },
  { key: 'start_date', label: '实习开始' },
  { key: 'end_date', label: '实习结束' },
  { key: 'status_text', label: '实习状态' },
];

const STATUS_TEXT = { 1: '实习中', 0: '已移除' };

const reportingModel = {
  fieldMap() { return FIELD_MAP; },

  /**
   * 拉取报送数据集：在册学生 + 其最新有效实习分配 + 单位 + 计划起止。
   * @param {{collegeId?:number, batchYear?:string, onlyAssigned?:boolean}} filter
   */
  async fetchRecords(filter = {}) {
    let where = ' WHERE u.role = 4 AND u.is_deleted = 0';
    const params = [];
    if (filter.collegeId) { where += ' AND u.college_id = ?'; params.push(filter.collegeId); }
    if (filter.batchYear) { where += ' AND YEAR(p.start_date) = ?'; params.push(Number(filter.batchYear)); }
    if (filter.onlyAssigned) { where += ' AND a.id IS NOT NULL'; }

    const [rows] = await pool.query(
      `SELECT u.eeid, u.real_name AS student_name, u.phone,
              c.name AS college_name, m.name AS major_name, cl.name AS class_name,
              e.name AS enterprise_name, t.real_name AS teacher_name,
              p.start_date, p.end_date, a.status AS assign_status
       FROM t_user u
       LEFT JOIN (
         SELECT student_id, MAX(id) AS aid FROM t_assignment WHERE is_deleted = 0 GROUP BY student_id
       ) la ON la.student_id = u.id
       LEFT JOIN t_assignment a ON a.id = la.aid
       LEFT JOIN t_enterprise e ON e.id = a.enterprise_id
       LEFT JOIN t_user t       ON t.id = a.teacher_id
       LEFT JOIN t_intern_plan p ON p.id = a.plan_id
       LEFT JOIN t_college c    ON c.id = u.college_id
       LEFT JOIN t_major m      ON m.id = u.major_id
       LEFT JOIN t_class cl     ON cl.id = u.class_id
       ${where}
       ORDER BY u.college_id, u.class_id, u.eeid`,
      params
    );
    return rows.map((r) => ({
      eeid: r.eeid || '',
      student_name: r.student_name || '',
      phone: r.phone || '',
      college_name: r.college_name || '',
      major_name: r.major_name || '',
      class_name: r.class_name || '',
      enterprise_name: r.enterprise_name || '',
      teacher_name: r.teacher_name || '',
      start_date: r.start_date ? new Date(r.start_date).toISOString().slice(0, 10) : '',
      end_date: r.end_date ? new Date(r.end_date).toISOString().slice(0, 10) : '',
      status_text: r.enterprise_name ? (STATUS_TEXT[r.assign_status] || '未分配') : '未分配',
    }));
  },

  // 将记录数组按标准列名映射为可导出的二维表（用于 xlsx / CSV / 报送包）
  toStandardRows(records) {
    return records.map((rec) => {
      const o = {};
      for (const f of FIELD_MAP) o[f.label] = rec[f.key] ?? '';
      return o;
    });
  },
};

module.exports = reportingModel;
