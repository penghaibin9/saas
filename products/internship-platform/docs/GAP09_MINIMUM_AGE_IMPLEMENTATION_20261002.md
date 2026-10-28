# GAP-09 实习最低年龄门禁 · 增量施工记录

日期：2026-10-02
PR：#275（保持 Draft，未合并）
分支：`feat/internship-standalone-yiyang-v1`
施工起点：`d5a3f8860999d9bdec618b138ea0ccefe24dfb9e`
状态：**CODE_IMPLEMENTED / RUNTIME_ACCEPTANCE_BLOCKED**。不是整体验收完成声明。

## 本轮源码变更

- 新增 `internship_student_age.py` 作为共同年龄事实源；使用学生主档出生日期或校验后的加密身份证信息，不向前端返回身份证明文或出生日期。缺失、解密失败、校验失败、未来日期均不能作为成年/满16岁的证据。
- 在岗位申请/分配评估、目录查询投影、学校合规评估和学生本人合规评估接入独立 `minimumAge` BLOCK 项。不能通过关闭可选 `workRights` 或配置 `minimumAge.required=false` 放行。
- 核实运行时公开豁免接口会由 `internship_evidence_authority_guard` 接管，已在实际入口及旧兼容入口同时拒绝年龄豁免申请、批准。历史 APPROVED 年龄豁免在原证据复验机制中失效并保留 INVALIDATE 审计；具体 MySQL 落库验收仍待完成。
- 监护人适用性、未成年人夜班判定、特殊备案触发与学生/学校年龄判断共用同一来源；保留16岁门禁与18岁监护人条件的区别，不以监护人同意替代最低年龄。
- 管理端豁免页增加不可豁免说明；台账依据后端 `exemptible` 字段隐藏禁止项批准动作，深链打开批准也被拦截，仍可拒绝遗留待审申请。
- 不将批次早期开班日期误当晚加入学生的实际上岗日期；已记录的历史未满16岁开岗不会因后续生日自动洗白；未来计划日期也不能绕过当前年龄门禁。
- 保留学校已批准的“免实习”终态：免实习不是年龄豁免，不新增到岗要求。

## 已实际执行的验证

| 检查 | 本轮结果 | 边界 |
|---|---|---|
| 改前复现 | 4项失败，15岁申请/分配/上岗/继续实习评估均错误放行 | 已保存改前日志 |
| 年龄、保险、监护人、安全课程、学生门面契约定向测试 | **67 passed** | 单元/契约测试，不等同真实用户办理 |
| 后端 app 与新增测试编译检查 | exit 0 | 语法检查 |
| 管理端路由闭合、导入闭合和生产构建 | exit 0 | 保留第三方大分块体积警告；非浏览器验收 |
| 独立数据库迁移与读回 | 已读到 MySQL **8.4.11**、Alembic **ix0024** | 只证明当时建库/迁移可用，不证明业务验收 |
| 新增 MySQL/API 专项测试 | **未完成** | 随后连接无响应，socket超时，Docker Desktop容器查询/统计接口返回500；终止了本轮挂起的测试进程 |
| 扩展旧工作台MySQL回归 | **15项 setup error** | 独立测试目录缺少 `db_mode` fixture；没有伪装为跳过后通过 |
| 真实浏览器、多角色办理、手机实机 | **未执行** | 不以构建或单元测试替代 |

复跑已通过专项：

```text
cd products/internship-platform/backend
python -m pytest -q tests/test_yiyang_gap09_minimum_age.py tests/test_internship_round3_compliance_unit.py tests/test_internship_student_compliance.py tests/test_internship_student_facade_review_contract.py
```

依赖测试环境的加密密钥和JWT密钥应由隔离环境提供，不写入源码或日志。新增
`test_yiyang_gap09_minimum_age_mysql.py` 使用正式登录/RBAC/路由，不覆盖鉴权依赖；
必须显式设置 `GAP09_MYSQL_ACCEPTANCE=1`、`APP_ENV=test` 并指定独立测试MySQL库。
未完成的用例不得报告为通过。

## 原工作区、交付位置与限制

原桌面275工作区存在既有未提交代码，未重置、未暂存或覆盖。本轮在
`D:/YuekeInternshipPR275-20261002` 的同名分支隔离副本施工。
本机执行证据保存在 `local-evidence/gap09/`，包括改前/改后测试、构建、迁移、扩展失败和清理结果。
本轮仅尝试清理自己创建的 `pr275-gap09-mysql-20261002`，未重启Docker、未操作其他项目容器；
由于Docker接口故障，清理未能确认，详情见 `runtime-cleanup.json`。

没有改main、没有合并PR、没有部署生产，没有触发或重跑完整Actions。
提交中的 `[skip ci]` 仅用于遵守本轮不重跑Actions约束，不是CI成功证据。

## 唯一下一步

先恢复独立MySQL运行环境，跑完新增API用例、解决旧工作台 `db_mode` 测试装配，
再做真实管理员/学生浏览器复验：拒绝低龄分配与上岗后数据不变、正常学生成功上岗并回读、
旧豁免不可批准且拒绝/失效有审计。上述证据齐全前 GAP-09 继续保持验收中。
GAP-06报告相似度、GAP-11整本手册等后续项，本轮未重复宣称完成。
