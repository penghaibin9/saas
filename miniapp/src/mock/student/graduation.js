/** 毕业设计 mock（05 毕业设计中心） */
export const studentGraduation = {
  hasBatch: true,
  batch: '2026 届毕业设计',
  topic: '基于 Vue3 的高校学生服务小程序设计与实现',
  mentor: '张明远',
  currentNode: 'MID', // 当前节点：中期
  nodes: [
    { id: 'g1', title: '选题', status: 'COMPLETED', deadline: '2025-11-10' },
    { id: 'g2', title: '导师确认', status: 'COMPLETED', deadline: '2025-11-15' },
    { id: 'g3', title: '任务书', status: 'COMPLETED', deadline: '2025-11-25' },
    { id: 'g4', title: '开题报告', status: 'APPROVED', deadline: '2025-12-20' },
    { id: 'g5', title: '中期检查', status: 'PENDING_SUBMIT', deadline: '2026-07-08', current: true },
    { id: 'g6', title: '成果提交', status: 'NOT_STARTED', deadline: '2026-05-10' },
    { id: 'g7', title: '查重', status: 'NOT_STARTED', deadline: '2026-05-15' },
    { id: 'g8', title: '答辩', status: 'NOT_STARTED', deadline: '2026-05-28' },
    { id: 'g9', title: '成绩与归档', status: 'NOT_STARTED', deadline: '2026-06-10' }
  ],
  primaryAction: { title: '提交中期检查报告', desc: '距截止 4 天，请上传中期进展与遗留问题', actionText: '提交中期' },
  returnedNote: '',
  guideLogs: [
    { id: 'gl1', date: '2026-06-20', from: '张明远', text: '开题通过。中期请重点说明已完成模块与测试情况。' },
    { id: 'gl2', date: '2026-06-05', from: '张明远', text: '任务书已确认，按里程碑推进。' }
  ],
  entries: ['我的课题', '任务书', '开题报告', '中期检查', '成果提交', '查重报告', '答辩安排', '成绩查询', '归档材料', '指导记录']
}
export default studentGraduation
