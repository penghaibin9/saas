# 最终 AI 施工总控提示词（分阶段 PR）

基线：`penghaibin9/saas@936101f00afdcf5c9803c8dd06e71b226ae5c16e`。不要把全部问题塞进一个大 PR，不合并 main。

## 阶段 A：7 个 P0 + 正式路由 mock 门禁

```text
你现在在 GitHub 仓库 penghaibin9/saas 施工。
基线先以最新 main 为准；如果 main 已不是 936101f00afdcf5c9803c8dd06e71b226ae5c16e，先比较差异并重新验证问题，不允许机械套旧行号。

目标：只收口 P0-01~P0-07 与正式路由 mock 可达性门禁，不做纯 UI 美化，不合并 main。

硬规则：
1. 保留现有 frontend/src/services/http/config.js 与 client.js 的生产 fail-closed；不要重造请求层。
2. 每项先输出“正式路由 → 页面 → API facade → adapter/backend”证据链。
3. 前端不得合成业务终态；RETURN/REJECT 必须独立。
4. 生产正式路由不可达 mocks/**、_mock*、mockStudents、roleProfiles、前端内存写路径。
5. 写操作必须有 tenant/dataScope/permission/state/version/idempotency/audit。
6. 成功提示必须有服务端持久化依据。
7. 每包专项测试 + 自我复审后再进入下一包。
8. 禁 git add -A；精确暂存。
9. 完成后提交、推送、Draft PR；不要合并。

施工顺序：
A1 P0-01 + P0-04 审批状态机/审批中心真实化；
A2 P0-02 + P0-03 学生事实/权限/写入真实化；
A3 P0-05 就业内存方法清零；
A4 P0-06 驾驶舱报表/上下文服务端化；
A5 P0-07 平台正式布局/看板脱离 platform.api.js；
A6 CI 正式路由依赖图门禁。

验收：7 个 P0 均可在数据库/审计/跨端状态得到证明；断网不得显示演示事实或假成功。
```

## 阶段 B：9 个 P1 + 10 个高频任务成熟厂家化

```text
你现在继续 penghaibin9/saas 页面收口。
前提：阶段 A 的 P0 已通过复审。不要合并 main。

目标：
- 完成 P1-01~P1-09；
- 同时按 `04_10_high_frequency_mature_vendor_workflows.md` 把 10 个高频任务做到成熟厂家水平。

优先级：
1. P1-01/P1-02/P1-04/P1-07/P1-09：建立 capability + typed route + todo deep-link 单一事实源。
2. P1-03：教师小程序 pending/done/mine 真分页 + 姓名/学号/单号搜索。
3. P1-05：BasePortalLayout <900px 汉堡 + 一级/二级抽屉。
4. P1-06：统一 useDirtyFormGuard，先覆盖实习批次、企业表单，再扫描同类长表单。
5. P1-08：身份核验区分 NOT_CONFIGURED / EMPTY / ERROR / FORBIDDEN。
6. 高频审批进入连续工作队列；学生材料入口全部指向真实 /materials，而不是重做一套上传。

每项必须：正常、空、403、409、5xx、重复点击、刷新恢复；页面成功后局部刷新，不用整页回跳。
完成后 Draft PR，不合并。
```

## 阶段 C：P2/P3 与工程清理

```text
前提：P0/P1 全部通过。

完成：
P2-01 教师学生分页搜索；
P2-02 132 小程序页面分包；
P2-03 学生 PC 窄屏搜索；
P2-04 管理 PC 404；
P2-05 旧详情路由参数保真；
P3-01 单一 PortalLayout；
P3-02 清除 transition:all；
P3-03 realFirstStrict 语义收口；
P3-04 旧 academic mock 实现归档/清理但保留兼容 redirect。

禁止把兼容路由 ID/query 丢失；构建/路由/分包/旧书签都要测试。
完成后 Draft PR，不合并。
```

## 阶段 D：四端逐页视觉与运行验收

```text
不要再改业务事实，除非验收暴露真实缺陷。

读取 `02_all_frontend_pages_matrix.md` 和 `05_runtime_visual_acceptance_gate.md`：
1. 按矩阵逐页跑管理 PC、学生 PC、教师小程序、学生小程序。
2. PC 跑 1920/1440/1366/1280/1024/900/899/820/768 + 125/150%。
3. 小程序跑开发者工具 + iOS + Android；核心页跑弱网、键盘、安全区、上传、上拉。
4. 每页记录 Normal/Loading/Empty/Error/403/409/Repeat 七态。
5. 修复时优先信息层级、首屏结论、状态识别、异常恢复、操作效率，再统一间距/字号/圆角。
6. 不新增大面积渐变/模糊/重阴影；不使用 transition:all。
7. 最终输出每页 PASS/FAIL、截图索引、剩余问题；P0/P1 必须为 0。

完成后只开最终 UI closeout Draft PR，不合并 main。
```