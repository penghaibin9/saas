#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

runner = Path(__file__).with_name("apply_miniapp_stage_a.py")
source = runner.read_text(encoding="utf-8")
old = '''# Permanent release workflow: add contracts and H5 build.
rel = ".github/workflows/miniapp-mp-weixin-release.yml"
text = read(rel)
text = replace_once(
    text,
    """      - name: 构建微信小程序生产包
        run: npm run build:mp-weixin:release
""",
    """      - name: 阶段A前端合同测试
        run: npm test

      - name: 构建 H5 兼容产物
        run: npm run build:h5

      - name: 构建微信小程序生产包
        run: npm run build:mp-weixin:release
""",
    "permanent workflow tests",
)
write(rel, text)
'''
new = '''# 当前权威验证工作流已执行合同测试、H5和微信生产构建。
# 永久精简工作流在阶段A源码正式提交时恢复，避免施工器修改正在运行的工作流。
'''
if source.count(old) != 1:
    raise RuntimeError(f"permanent workflow block matches={source.count(old)}")
runner.write_text(source.replace(old, new, 1), encoding="utf-8")
print("stage A runner workflow tail hotfixed")
