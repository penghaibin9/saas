/** 学业进度 mock（04 学业过程中心） */
export const studentAcademic = {
  summary: { gpa: 3.62, rank: '12 / 46', creditEarned: 78, creditTotal: 165, warning: false },
  termProgress: [
    { term: '2024-2025 秋', gpa: 3.55, credit: 22, status: 'COMPLETED' },
    { term: '2024-2025 春', gpa: 3.68, credit: 24, status: 'COMPLETED' },
    { term: '2025-2026 秋', gpa: 3.66, credit: 20, status: 'PROCESSING' }
  ],
  courses: [
    { id: 'ac1', name: '数据库原理', teacher: '李强', credit: 3, score: null, status: 'PROCESSING', progress: 70 },
    { id: 'ac2', name: '软件工程导论', teacher: '张明远', credit: 3, score: null, status: 'PROCESSING', progress: 66 },
    { id: 'ac3', name: '数据结构', teacher: '王芳', credit: 4, score: 92, status: 'COMPLETED', progress: 100 },
    { id: 'ac4', name: '高等数学(下)', teacher: '陈立', credit: 5, score: 85, status: 'COMPLETED', progress: 100 },
    { id: 'ac5', name: '大学英语(三)', teacher: '刘洋', credit: 3, score: 88, status: 'COMPLETED', progress: 100 }
  ],
  exams: [
    { id: 'ex1', name: '数据库原理 期末', time: '2026-07-12 09:00', place: '教学楼 B-201', seat: '第 18 号' },
    { id: 'ex2', name: '软件工程导论 期末', time: '2026-07-14 14:00', place: '实训楼 A-305', seat: '第 06 号' }
  ],
  warnings: []
}
export default studentAcademic
