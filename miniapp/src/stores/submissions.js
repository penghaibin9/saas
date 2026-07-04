/**
 * 本地提交记录（mock，仅内存）
 * 学生提交的申请/周报先存这里，页面即时可见，形成“提交→可查看”的闭环。
 * 不接后端、不持久化到数据库。
 */
import { defineStore } from 'pinia'

let seq = 1
function genNo(prefix) {
  const d = new Date()
  const pad = (n) => (n < 10 ? '0' + n : '' + n)
  return prefix + d.getFullYear() + pad(d.getMonth() + 1) + pad(d.getDate()) + pad(seq++)
}

export const useSubmissionsStore = defineStore('submissions', {
  state: () => ({
    applications: [], // 学生提交的服务申请
    weeklyReports: [] // 学生提交的实习周报
  }),
  actions: {
    addApplication({ name, dept, needApprove, detail }) {
      const item = {
        id: 'my_' + Date.now(),
        no: genNo('SV'),
        name,
        group: needApprove ? 'processing' : 'done',
        status: needApprove ? 'REVIEWING' : 'COMPLETED',
        applyTime: new Date().toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-'),
        dept: dept || '相关部门',
        handler: needApprove ? '待分配' : '系统',
        eta: '—',
        lastOpinion: needApprove ? '已提交，等待审核' : '已受理',
        hasResult: !needApprove,
        detail: detail || ''
      }
      this.applications.unshift(item)
      return item
    },
    addWeeklyReport(report) {
      this.weeklyReports.unshift({ id: 'wr_' + Date.now(), ...report, submittedAt: new Date().toLocaleString('zh-CN', { hour12: false }) })
    },
    hasWeekly(week) {
      return this.weeklyReports.some((r) => r.week === week)
    }
  }
})

export default useSubmissionsStore
