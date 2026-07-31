# Teacher PC V2 冻结验证工具

本目录的工具只读取仓库和原型文件；默认报告写到 `/tmp` 或调用方指定目录，不把截图、浏览器缓存、运行日志和报告提交仓库。

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

## 3. 三档分辨率浏览器全量回归

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

## 4. 冻结顺序

```bash
node tools/check-prototype-consistency.mjs --report=/tmp/teacher-pc-v2-freeze/consistency.json
node tools/check-internship-route-audit.mjs --report=/tmp/teacher-pc-v2-freeze/internship-route-audit.json
node tools/run-browser-regression.mjs --concurrency=4 --report-dir=/tmp/teacher-pc-v2-freeze/browser
```

三项全部 PASS 后，仍需人工完成打印页、特殊状态、业务红线和公共交互复核。只有 `prototype-freeze-gates.md` 的 G0–G7 全部通过，才能记录冻结 HEAD、把 Manifest 状态改为 `FROZEN` 并生成四条生产施工总控提示词。
