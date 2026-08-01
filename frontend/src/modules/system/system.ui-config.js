/**
 * 系统管理纯展示配置。
 *
 * 这里只保存表格列、Excel 模板说明和导出选项，不包含用户、角色、组织、
 * 权限结果或业务数据。运行态事实必须由 /system/context 和对应业务 API 返回。
 */
export const SYSTEM_STATUS_OPTIONS = {
  userStatus: [
    { value: 'ACTIVE', label: '启用中' },
    { value: 'DISABLED', label: '已停用' },
    { value: 'LOCKED', label: '已锁定' }
  ],
  roleStatus: [
    { value: 'ENABLED', label: '启用中' },
    { value: 'DEPRECATED', label: '已作废' }
  ],
  roleType: [
    { value: 'BUILTIN', label: '内置角色' },
    { value: 'CUSTOM', label: '自定义角色' }
  ],
  ruleStatus: [
    { value: 'ENABLED', label: '启用中' },
    { value: 'DEPRECATED', label: '已作废' }
  ],
  scopeTypes: []
}

export const SYSTEM_FIELD_COLUMNS = {
  staffAccounts: [
    { key: 'user', title: '教职工', locked: true, defaultVisible: true },
    { key: 'org', title: '业务归属', locked: false, defaultVisible: true },
    { key: 'roles', title: '角色', locked: false, defaultVisible: true },
    { key: 'phone', title: '手机号（脱敏）', locked: false, defaultVisible: true },
    { key: 'status', title: '状态', locked: false, defaultVisible: true },
    { key: 'lastLoginAt', title: '最近登录', locked: false, defaultVisible: true },
    { key: 'source', title: '账号来源', locked: false, defaultVisible: false },
    { key: 'createdAt', title: '创建时间', locked: false, defaultVisible: false },
    { key: 'actions', title: '操作', locked: true, defaultVisible: true }
  ],
  studentAccounts: [
    { key: 'user', title: '学生', locked: true, defaultVisible: true },
    { key: 'collegeName', title: '学院', locked: false, defaultVisible: true },
    { key: 'majorName', title: '专业', locked: false, defaultVisible: true },
    { key: 'grade', title: '年级', locked: false, defaultVisible: true },
    { key: 'className', title: '班级', locked: false, defaultVisible: true },
    { key: 'studentStatus', title: '学籍状态', locked: false, defaultVisible: true },
    { key: 'status', title: '账号状态', locked: false, defaultVisible: true },
    { key: 'phone', title: '手机号（脱敏）', locked: false, defaultVisible: false },
    { key: 'lastLoginAt', title: '最近登录', locked: false, defaultVisible: true },
    { key: 'createdAt', title: '创建时间', locked: false, defaultVisible: false },
    { key: 'actions', title: '操作', locked: true, defaultVisible: true }
  ]
}

export const SYSTEM_BATCH_ACTIONS = {
  users: [
    { key: 'batchAssignRole', label: '批量分配角色', permissionKey: 'assignRole' },
    { key: 'batchDisableUsers', label: '批量停用', permissionKey: 'batchDisableUsers', danger: true },
    { key: 'exportSelected', label: '导出所选', permissionKey: 'exportUsers' }
  ]
}

export const SYSTEM_IMPORT_TEMPLATES = {
  users: {
    key: 'users',
    name: '老师和学生账号导入模板',
    version: 'v4.0',
    fileName: '师生账号导入模板.xlsx',
    fields: ['账号类型（TEACHER/STUDENT）', '工号/学号', '姓名', '所属组织编码', '预设角色编码（教师可多选）', '数据范围类型', '数据范围引用'],
    rules: [
      '只支持系统下载的标准 .xlsx，不提供 CSV 导入',
      '本菜单是批量创建账号的唯一入口',
      '工号/学号在本校内唯一，重复导入只补缺失角色',
      '教师只能选择 SaaS 预设角色，学生固定绑定 STUDENT',
      '初始密码仅在回执显示一次',
      '单次最多 2,000 行'
    ]
  }
}

export const SYSTEM_EXPORT_OPTIONS = {
  staffAccounts: {
    scopes: [
      { value: 'FILTERED', label: '当前筛选结果（无筛选时为全部）' }
    ],
    fields: [
      { key: 'userNo', label: '工号', sensitive: true, defaultChecked: true, maskNote: '默认脱敏' },
      { key: 'name', label: '姓名', sensitive: false, defaultChecked: true },
      { key: 'org', label: '业务归属', sensitive: false, defaultChecked: true },
      { key: 'roles', label: '角色', sensitive: false, defaultChecked: true },
      { key: 'status', label: '账号状态', sensitive: false, defaultChecked: true },
      { key: 'lastLoginAt', label: '最近登录', sensitive: false, defaultChecked: false }
    ],
    watermark: true,
    note: '导出文件自动附加操作人和时间水印；手机号不进入默认导出。'
  },
  studentAccounts: {
    scopes: [
      { value: 'FILTERED', label: '当前筛选结果（无筛选时为全部）' }
    ],
    fields: [
      { key: 'studentNo', label: '学号', sensitive: true, defaultChecked: true, maskNote: '按导出权限控制' },
      { key: 'name', label: '姓名', sensitive: false, defaultChecked: true },
      { key: 'collegeName', label: '学院', sensitive: false, defaultChecked: true },
      { key: 'majorName', label: '专业', sensitive: false, defaultChecked: true },
      { key: 'grade', label: '年级', sensitive: false, defaultChecked: true },
      { key: 'className', label: '班级', sensitive: false, defaultChecked: true },
      { key: 'studentStatus', label: '学籍状态', sensitive: false, defaultChecked: true },
      { key: 'status', label: '账号状态', sensitive: false, defaultChecked: true }
    ],
    watermark: true,
    note: '学生账号导出不包含角色和心理等敏感业务字段；文件附加操作人和时间水印。'
  },
  users: {
    scopes: [
      { value: 'FILTERED', label: '当前筛选结果' },
      { value: 'SELECTED', label: '仅所选记录' },
      { value: 'ALL', label: '数据范围内全部' }
    ],
    fields: [
      { key: 'userNo', label: '工号/账号', sensitive: true, defaultChecked: true, maskNote: '默认脱敏' },
      { key: 'name', label: '姓名', sensitive: false, defaultChecked: true },
      { key: 'org', label: '所属组织', sensitive: false, defaultChecked: true },
      { key: 'roles', label: '角色', sensitive: false, defaultChecked: true },
      { key: 'phone', label: '手机号', sensitive: true, defaultChecked: false, maskNote: '默认脱敏' },
      { key: 'status', label: '状态', sensitive: false, defaultChecked: true },
      { key: 'lastLoginAt', label: '最近登录', sensitive: false, defaultChecked: false }
    ],
    watermark: true,
    note: '导出文件自动附加操作人和时间水印；敏感字段默认脱敏。'
  },
  logs: {
    scopes: [
      { value: 'FILTERED', label: '当前筛选结果' },
      { value: 'RANGE_30D', label: '近 30 天' }
    ],
    fields: [
      { key: 'time', label: '时间', sensitive: false, defaultChecked: true },
      { key: 'who', label: '操作人', sensitive: false, defaultChecked: true },
      { key: 'action', label: '动作', sensitive: false, defaultChecked: true },
      { key: 'target', label: '对象', sensitive: false, defaultChecked: true },
      { key: 'ip', label: 'IP（脱敏）', sensitive: true, defaultChecked: true, maskNote: '固定脱敏' },
      { key: 'detail', label: '详情', sensitive: false, defaultChecked: false }
    ],
    watermark: true,
    note: '审计日志仅支持导出；导出动作本身也会写入审计日志。'
  }
}
