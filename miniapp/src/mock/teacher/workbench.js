/** 教师工作台 mock（08B 7.2 今日工作台）。按身份返回不同摘要。 */
export const workbenchByRole = {
  counselor: {
    contextTitle: '辅导员', contextScope: '软件工程 2401 班',
    metrics: [
      { key: 'todo', label: '今日待办', value: 8 },
      { key: 'risk', label: '风险学生', value: 3 },
      { key: 'unread', label: '未读消息', value: 5 },
      { key: 'nocontact', label: '待联系', value: 4 }
    ],
    dueSoon: [
      { id: 'd1', title: '请假审批（孙雨桐 病假）', student: '孙雨桐', module: '在校服务', deadline: '2026-07-04 12:00', level: 'high', status: 'PENDING_REVIEW' },
      { id: 'd2', title: '关怀回访（赵启航）', student: '赵启航', module: '学工', deadline: '2026-07-04 18:00', level: 'normal', status: 'PENDING_HANDLE' }
    ],
    riskStudents: [
      { id: 'S002', name: '李思远', className: '软件2401', type: '实习打卡异常', level: 'HIGH', time: '2026-07-03 09:10', handled: false },
      { id: 'S004', name: '赵启航', className: '软件2401', type: '学业预警×2', level: 'HIGH', time: '2026-07-02 16:00', handled: false },
      { id: 'S001', name: '陈子涵', className: '软件2401', type: '3天未登录', level: 'MEDIUM', time: '2026-07-03 08:00', handled: false }
    ],
    recent: [
      { id: 'r1', name: '王梓萱', text: '提交了毕设中期报告', time: '2026-07-03 10:12' },
      { id: 'r2', name: '孙雨桐', text: '发起病假申请', time: '2026-07-03 08:30' }
    ]
  },
  mentor: {
    contextTitle: '毕业设计指导教师', contextScope: '指导学生 12 人',
    metrics: [
      { key: 'review', label: '待批阅', value: 4 },
      { key: 'return', label: '待整改', value: 1 },
      { key: 'defense', label: '答辩安排', value: 2 },
      { key: 'unread', label: '未读', value: 3 }
    ],
    dueSoon: [
      { id: 'd3', title: '批阅中期报告（王梓萱）', student: '王梓萱', module: '毕业设计', deadline: '2026-07-05 18:00', level: 'high', status: 'PENDING_REVIEW' },
      { id: 'd4', title: '批阅开题（吴佳怡）', student: '吴佳怡', module: '毕业设计', deadline: '2026-07-06 18:00', level: 'normal', status: 'PENDING_REVIEW' }
    ],
    riskStudents: [
      { id: 'S010', name: '黄子豪', className: '软件2402', type: '中期逾期未交', level: 'HIGH', time: '2026-07-02 22:00', handled: false }
    ],
    recent: [
      { id: 'r3', name: '王梓萱', text: '提交中期报告，待批阅', time: '2026-07-03 10:12' }
    ]
  },
  intern_mentor: {
    contextTitle: '实习指导教师', contextScope: '实习学生 18 人',
    metrics: [
      { key: 'weekly', label: '周报待批', value: 6 },
      { key: 'abnormal', label: '打卡异常', value: 2 },
      { key: 'leave', label: '请假待批', value: 1 },
      { key: 'risk', label: '风险', value: 2 }
    ],
    dueSoon: [
      { id: 'd5', title: '批阅第 8 周周报（李思远）', student: '李思远', module: '岗位实习', deadline: '2026-07-04 20:00', level: 'high', status: 'PENDING_REVIEW' },
      { id: 'd6', title: '处理打卡异常（李思远）', student: '李思远', module: '岗位实习', deadline: '2026-07-04 12:00', level: 'high', status: 'ABNORMAL' }
    ],
    riskStudents: [
      { id: 'S002', name: '李思远', className: '软件2401', type: '打卡异常+周报逾期', level: 'HIGH', time: '2026-07-03 09:10', handled: false }
    ],
    recent: [
      { id: 'r4', name: '郑一鸣', text: '提交第 8 周周报', time: '2026-07-03 11:00' }
    ]
  },
  employment: {
    contextTitle: '就业老师', contextScope: '信息工程学院',
    metrics: [
      { key: 'unemployed', label: '未就业', value: 37 },
      { key: 'follow', label: '待跟进', value: 12 },
      { key: 'verify', label: '待核验', value: 8 },
      { key: 'rate', label: '就业率', value: '81%' }
    ],
    dueSoon: [
      { id: 'd7', title: '就业去向跟进（周浩然）', student: '周浩然', module: '就业', deadline: '2026-07-05 18:00', level: 'normal', status: 'PENDING_HANDLE' }
    ],
    riskStudents: [
      { id: 'S006', name: '周浩然', className: '软件2401', type: '毕业临近未落实', level: 'MEDIUM', time: '2026-07-01 09:00', handled: false }
    ],
    recent: [
      { id: 'r5', name: '林可欣', text: '填报就业意向：互联网/长沙', time: '2026-07-02 17:00' }
    ]
  },
  academic: {
    contextTitle: '教务老师', contextScope: '信息工程学院',
    metrics: [
      { key: 'warning', label: '学业预警', value: 15 },
      { key: 'status', label: '学籍异动', value: 3 },
      { key: 'approval', label: '待审批', value: 6 },
      { key: 'exam', label: '临考安排', value: 4 }
    ],
    dueSoon: [
      { id: 'd8', title: '学业预警确认（赵启航）', student: '赵启航', module: '学业', deadline: '2026-07-05 18:00', level: 'high', status: 'PENDING_HANDLE' }
    ],
    riskStudents: [
      { id: 'S004', name: '赵启航', className: '软件2401', type: '2门不及格', level: 'HIGH', time: '2026-07-02 16:00', handled: false }
    ],
    recent: [
      { id: 'r6', name: '教务系统', text: '期末考试安排已发布', time: '2026-07-01 10:00' }
    ]
  },
  college_admin: {
    contextTitle: '学院管理员', contextScope: '信息工程学院',
    metrics: [
      { key: 'students', label: '在校学生', value: 1286 },
      { key: 'risk', label: '风险学生', value: 24 },
      { key: 'todo', label: '待办汇总', value: 46 },
      { key: 'intern', label: '实习中', value: 210 }
    ],
    dueSoon: [
      { id: 'd9', title: '本周风险学生处理汇总', student: '—', module: '学院', deadline: '2026-07-05 18:00', level: 'normal', status: 'PENDING_HANDLE' }
    ],
    riskStudents: [
      { id: 'S002', name: '李思远', className: '软件2401', type: '实习异常', level: 'HIGH', time: '2026-07-03 09:10', handled: false },
      { id: 'S004', name: '赵启航', className: '软件2401', type: '学业预警', level: 'HIGH', time: '2026-07-02 16:00', handled: false }
    ],
    recent: [
      { id: 'r7', name: '软件教研室', text: '毕设中期完成率 68%', time: '2026-07-03 09:00' }
    ]
  }
}
export default workbenchByRole
