# Teacher PC V2 冻结验证工具

本目录工具只读取仓库和原型文件；默认报告写到 `/tmp` 或调用方指定目录，不把截图、浏览器缓存、运行日志和报告提交仓库。

## 运行环境

- Node.js 20+
- 完整检出 `codex/teacher-pc-v2-html-library` 分支
- 浏览器回归需要本机安装 Chrome / Chromium
- 默认从环境变量 `CHROME_PATH`，或常见 Chrome / Chromium 安装路径查找浏览器

## 1. Manifest / 文件 / 相对资源一致性

```bash
cd docs/ui/teacher-pc-v2-html
node tools/check-prototype-consistency.mjs \
  --report=/tmp/teacher-pc-v2-freeze/consistency.json
```

冻结前严格模式：

```bash
node tools/check-prototype-consistency.mjs \
  --strict \
  --require-screenshots \
  --report=/tmp/teacher-pc-v2-freeze/consistency-final.json
```

普通收口阶段不使用 `--require-screenshots`，历史或计划截图路径只记为警告；最终冻结证据齐全后才启用。

## 2. 岗位实习 101 叶子 / 99 URL 审计

```bash
node tools/check-internship-route-audit.mjs \
  --report=/tmp/teacher-pc-v2-freeze/internship-route-audit.json
```

通过条件：

- 12 个生产二级模块；
- 101 个生产三级叶子；
- 99 个唯一 URL；
- 2 个显式共享 URL；
- 99 个 URL 均只有一个原型 owner；
- 每个 URL 的生产权限被 owner 权限契约覆盖；
- 每个 owner 都有字段、状态和 API 参数契约；
- 无过时 URL、无漏 URL、无重复认领。

## 3. 毕业设计 8 工作区 / 50 叶子审计

```bash
node tools/check-graduation-workspace-audit.mjs \
  --report=/tmp/teacher-pc-v2-freeze/graduation-workspace-audit.json
```

脚本直接读取生产：

```text
frontend/src/modules/graduation/config/graduationWorkspaces.js
```

并与：

```text
docs/ui/teacher-pc-v2-html/manifest-parts/320-graduation.json
```

逐项比较。通过条件：

- 8 个生产工作区；
- 50 个生产三级叶子；
- 48 个唯一 URL；
- 2 个共享 URL 及 owner 完全一致；
- 8 个 workspace key、名称和主入口一致；
- 每个工作区 `coveredRoutes` 与生产叶子集合一致；
- 每个工作区权限候选覆盖全部生产权限；
- 8 个 HTML 均存在且一页只属于一个工作区；
- 每个工作区具备字段、状态和业务边界契约；
- 无过时工作区、漏工作区或过时共享 URL。

该脚本已完成 `node --check`，并在隔离同构目录中跑通；最终冻结必须在完整真实分支快照中再次执行。

## 4. 页面族定向浏览器回归

`run-page-family-regression.mjs` 会复制一份临时原型快照，生成只包含目标页面的临时 Manifest，再调用正式浏览器执行器。它不会修改工作区文件，也不会把临时 Manifest 写入仓库。

### 学工 11 个关键工作台

先核对选中页面：

```bash
node tools/run-page-family-regression.mjs \
  --family=student-affairs-key \
  --list-only
```

执行三档 33 次回归：

```bash
node tools/run-page-family-regression.mjs \
  --family=student-affairs-key \
  --concurrency=3 \
  --report-dir=/tmp/teacher-pc-v2-freeze/student-affairs-key
```

### 学工全部 15 页

```bash
node tools/run-page-family-regression.mjs \
  --family=student-affairs-all \
  --concurrency=3 \
  --report-dir=/tmp/teacher-pc-v2-freeze/student-affairs-all
```

### 毕业设计现行 8 工作区

先核对选中页面：

```bash
node tools/run-page-family-regression.mjs \
  --family=graduation \
  --list-only
```

执行三档 24 次回归：

```bash
node tools/run-page-family-regression.mjs \
  --family=graduation \
  --concurrency=3 \
  --report-dir=/tmp/teacher-pc-v2-freeze/graduation-browser
```

### 自定义页面族

按目录前缀：

```bash
node tools/run-page-family-regression.mjs \
  --prefix=academic-affairs/stats/ \
  --report-dir=/tmp/teacher-pc-v2-freeze/academic-stats
```

按精确 HTML，多个文件使用逗号分隔：

```bash
node tools/run-page-family-regression.mjs \
  --html=graduation/overview.html,graduation/defense.html \
  --viewports=1440x1000 \
  --report-dir=/tmp/teacher-pc-v2-freeze/graduation-smoke
```

页面族固定数量保护：

- `student-affairs-key` 必须为 11 页；
- `student-affairs-all` 必须为 15 页；
- `graduation` 必须为 8 页。

Manifest 数量不符、目标 HTML 不存在或筛选结果为空时，工具会直接失败，不会启动 Chrome。添加 `--keep-temp` 可在失败后保留临时快照用于排查；默认自动删除。

## 5. 三档分辨率浏览器全量回归

当前总 Manifest 登记 **290 个唯一 HTML**，因此基础回归是：

```text
290 × 3 = 870 次渲染
```

运行：

```bash
node tools/run-browser-regression.mjs \
  --concurrency=4 \
  --timeout-ms=25000 \
  --virtual-time-ms=4500 \
  --report-dir=/tmp/teacher-pc-v2-freeze/browser
```

先做少量冒烟：

```bash
node tools/run-browser-regression.mjs \
  --smoke=10 \
  --concurrency=2 \
  --report-dir=/tmp/teacher-pc-v2-freeze/browser-smoke
```

需要本地截图证据时添加 `--screenshots`。截图目录必须保留在临时目录或 CI Artifact，不得直接提交到本 PR。

浏览器执行器检查：

- 页面是否完成加载、是否白屏；
- `console.error`、运行时错误、未处理 Promise；
- CSS、图片和其他资源加载失败；
- 重复 `id`；
- 根页面横向溢出；
- 可操作元素是否能获得焦点；
- 已打开对话框焦点是否仍在外部；
- 正 `tabindex`、无交互元素和 `console.warn` 警告；
- 可选三档截图。

## 6. 冻结顺序

```bash
node tools/check-prototype-consistency.mjs --report=/tmp/teacher-pc-v2-freeze/consistency.json
node tools/check-internship-route-audit.mjs --report=/tmp/teacher-pc-v2-freeze/internship-route-audit.json
node tools/check-graduation-workspace-audit.mjs --report=/tmp/teacher-pc-v2-freeze/graduation-workspace-audit.json
node tools/run-page-family-regression.mjs --family=student-affairs-key --report-dir=/tmp/teacher-pc-v2-freeze/student-affairs-key
node tools/run-page-family-regression.mjs --family=graduation --report-dir=/tmp/teacher-pc-v2-freeze/graduation-browser
node tools/run-browser-regression.mjs --concurrency=4 --report-dir=/tmp/teacher-pc-v2-freeze/browser
```

机器检查全部 PASS 后，仍需人工完成打印页、特殊状态、业务红线和公共交互复核。只有 `prototype-freeze-gates.md` 的 G0–G7 全部通过，才能记录冻结 HEAD、把 Manifest 状态改为 `FROZEN` 并生成四条生产施工总控提示词。
