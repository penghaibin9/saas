# 页面族定向浏览器回归工具验证记录

## 工具

- 文件：`tools/run-page-family-regression.mjs`
- 底层执行器：`tools/run-browser-regression.mjs`
- 目标：在不修改原型工作区的前提下，精确运行某一页面族的浏览器回归。

## 支持的固定页面族

| 参数 | Manifest 来源 | 固定 HTML 数量 | 三档渲染量 |
|---|---|---:|---:|
| `--family=student-affairs-key` | `300-student-affairs-key.json` | 11 | 33 |
| `--family=student-affairs-all` | `300` + `330` | 15 | 45 |
| `--family=graduation` | `320-graduation.json` | 8 | 24 |

同时支持：

- `--prefix=<目录前缀>`
- `--html=<精确文件1,精确文件2>`
- `--list-only`
- `--keep-temp`
- 底层浏览器执行器的 `--viewports`、`--concurrency`、`--timeout-ms`、`--virtual-time-ms`、`--screenshots` 和 `--report-dir`

## 防误用机制

工具启动 Chrome 前会检查：

1. 总 Manifest 聚合 HTML 数量必须等于 `coverage.uniqueHtmlFiles`；
2. 固定页面族必须分别保持 11、15、8 页；
3. 精确指定的 HTML 必须存在于总 Manifest；
4. 选中的 HTML 必须真实存在；
5. 筛选结果不得为 0；
6. 临时快照不复制 `node_modules` 或 `.git`；
7. 临时 Manifest 只在系统临时目录生成；
8. 默认执行完成后删除临时快照；
9. 原始 `prototype-manifest.json` 和原型文件不被修改。

## 已完成验证

### 1. 语法检查

```text
node --check tools/run-page-family-regression.mjs
PASS
```

### 2. 隔离同构夹具

构造与真实目录关系一致的隔离夹具，包含：

- 学工关键页 11 个；
- 学工扩展页 4 个；
- 毕业设计页 8 个；
- 总 Manifest、300、330、320 分片；
- 一个用于确认临时 Manifest 的浏览器执行器桩。

执行：

```bash
node tools/run-page-family-regression.mjs \
  --family=graduation \
  --list-only
```

结果：准确选中 **8 个 HTML**。

继续执行完整包装链：

```bash
node tools/run-page-family-regression.mjs \
  --family=graduation \
  --report-dir=/tmp/family-report
```

隔离子执行器读取临时 Manifest，确认：

```text
STUB_SELECTED=8
PASS
```

验证覆盖：页面族选择、固定数量保护、临时目录复制、临时 Manifest 生成、参数转发、子执行器调用和临时目录清理。

## 当前未完成

尚未在完整真实 PR 分支快照中执行：

```bash
node tools/run-page-family-regression.mjs --family=student-affairs-key ...
node tools/run-page-family-regression.mjs --family=graduation ...
```

因此当前不能把工具验证写成：

- 学工 33 / 33 浏览器回归通过；
- 毕业设计 24 / 24 浏览器回归通过；
- 当前完整 HEAD 已完成页面族回归。

## 结论

当前可确认：工具语法通过，页面族筛选与临时执行链在隔离同构夹具中通过。

最终冻结仍要求在完整真实分支快照中运行真实 Chrome / Chromium，并把 JSON、Markdown 和必要截图保存在临时目录或 CI Artifact；只有真实浏览器结果才能增加 546 / 870 的累计通过数。
