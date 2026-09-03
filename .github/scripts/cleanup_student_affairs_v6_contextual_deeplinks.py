from pathlib import Path
import re


BASE_IMPORT = "import { projectStudentAffairsWorkspaceDeepLinks } from '@/config/studentAffairsWorkspaceDeepLinks'\n"
RISK_IMPORT = "import { resolveRiskQueueIntent } from '@/modules/studentAffairs/utils/riskRouteQueueIntent'\n"


def keep_one_line(text: str, line: str, label: str) -> str:
    seen = False
    output = []
    for current in text.splitlines(keepends=True):
        if current == line:
            if seen:
                continue
            seen = True
        output.append(current)
    result = ''.join(output)
    if result.count(line) != 1:
        raise SystemExit(f'{label}: expected exactly one import, got {result.count(line)}')
    return result


layout_path = Path('frontend/src/layouts/BasePortalLayout.vue')
layout = keep_one_line(layout_path.read_text(encoding='utf-8'), BASE_IMPORT, 'BasePortal helper')

workspace_block = re.compile(
    r"/\* 学工 V6 只在带 workspaceTitle 的投影中收紧一级轨并给三级标签足够宽度。 \*/\n"
    r"\.bpl-aside--workspace \{\n  width: 214px;\n  padding: 12px 9px 14px;\n\}\n"
    r"\.base-portal-layout:has\(\.bpl-aside--workspace\) \.bpl-rail \{\n  width: 68px;\n\}\n"
    r"\.base-portal-layout:has\(\.bpl-aside--workspace\) \.bpl-rail__item \{\n"
    r"  width: 56px;\n  padding-block: 8px 6px;\n  border-radius: 11px;\n\}\n"
)
layout = workspace_block.sub('', layout)

contextual_block = re.compile(
    r"/\* D\(\) 低频页面在当前工作区中可见，但用轻量类型标识与主工作台区分。 \*/\n"
    r"\.bpl-tree \.bpl-tree__leaf\.is-contextual \{\n"
    r"  color: var\(--t2\);\n"
    r"  background: color-mix\(in srgb, var\(--bg-card\) 72%, var\(--pri-bg\)\);\n"
    r"\}\n"
    r"\.bpl-tree \.bpl-tree__leaf\.is-contextual:hover,\n"
    r"\.bpl-tree \.bpl-tree__leaf\.is-contextual\.is-active \{\n"
    r"  color: var\(--pri\);\n"
    r"  background: var\(--pri-bg\);\n"
    r"\}\n"
    r"\.bpl-tree \.bpl-tree__leaf \.bpl-planbadge--implemented \{\n"
    r"  color: var\(--t3\);\n"
    r"  background: var\(--bg-section\);\n"
    r"  border: 1px solid var\(--border-light\);\n"
    r"\}\n"
    r"\.bpl-tree \.bpl-tree__leaf\.is-contextual\.is-active \.bpl-planbadge--implemented \{\n"
    r"  color: var\(--pri\);\n"
    r"  border-color: var\(--pri-100\);\n"
    r"  background: var\(--bg-card\);\n"
    r"\}\n"
)
layout = contextual_block.sub('', layout)

layout = layout.replace(
    '/* ══ 学工 V6 工作区侧栏：三波 / 12 工作区 / 分阶段三级深链 ══ */\n.bpl-aside--workspace {\n  width: 228px;',
    '/* ══ 学工 V6 工作区侧栏：三波 / 12 工作区 / 分阶段三级深链 ══ */\n.bpl-aside--workspace {\n  width: 214px;',
    1
)
layout = layout.replace(
    '@media (max-width: 1450px) {\n  .bpl-aside--workspace {\n    width: 218px;',
    '@media (max-width: 1450px) {\n  .bpl-aside--workspace {\n    width: 208px;',
    1
)

final_css = """
/* V6 学工工作区：一级轨与当前工作区的低频真实三级页。 */
.base-portal-layout:has(.bpl-aside--workspace) .bpl-rail {
  width: 68px;
}
.base-portal-layout:has(.bpl-aside--workspace) .bpl-rail__item {
  width: 56px;
  padding-block: 8px 6px;
  border-radius: 11px;
}
.bpl-tree .bpl-tree__leaf.is-contextual {
  color: var(--t2);
  background: color-mix(in srgb, var(--bg-card) 72%, var(--pri-bg));
}
.bpl-tree .bpl-tree__leaf.is-contextual:hover,
.bpl-tree .bpl-tree__leaf.is-contextual.is-active {
  color: var(--pri);
  background: var(--pri-bg);
}
.bpl-tree .bpl-tree__leaf .bpl-planbadge--implemented {
  color: var(--t3);
  background: var(--bg-section);
  border: 1px solid var(--border-light);
}
.bpl-tree .bpl-tree__leaf.is-contextual.is-active .bpl-planbadge--implemented {
  color: var(--pri);
  border-color: var(--pri-100);
  background: var(--bg-card);
}
"""
if '/* V6 学工工作区：一级轨与当前工作区的低频真实三级页。 */' not in layout:
    layout = layout.replace('\n</style>\n', final_css + '\n</style>\n', 1)

if layout.count(BASE_IMPORT) != 1:
    raise SystemExit('BasePortal helper import duplication remains')
if layout.count('/* V6 学工工作区：一级轨与当前工作区的低频真实三级页。 */') != 1:
    raise SystemExit('V6 final CSS block is not unique')
if layout.count("return projectStudentAffairsWorkspaceDeepLinks(group, permissionPatterns)") != 1:
    raise SystemExit('workspace projection call is missing or duplicated')
layout_path.write_text(layout, encoding='utf-8')

risk_path = Path('frontend/src/modules/studentAffairs/views/StudentAffairsRiskListView.vue')
risk = keep_one_line(risk_path.read_text(encoding='utf-8'), RISK_IMPORT, 'risk intent helper')
inline_intent = re.compile(
    r"      // V6 侧栏快捷队列只投影既有服务端过滤参数；不在浏览器本地筛选或扩大 allowedActions。\n"
    r"      this\.activeQueue = String\(q\.priority \|\| ''\) === 'HIGH_CRITICAL' \? 'HIGH'\n"
    r"        : String\(q\.overdueOnly \|\| ''\)\.toLowerCase\(\) === 'true' \? 'OVERDUE'\n"
    r"          : String\(q\.unassignedOnly \|\| ''\)\.toLowerCase\(\) === 'true' \? 'UNASSIGNED'\n"
    r"            : String\(q\.ownerId \|\| ''\) === 'me' \? 'MINE'\n"
    r"              : String\(q\.status \|\| ''\)\.toUpperCase\(\) === 'FOLLOWING' \? 'FOLLOWING'\n"
    r"                : 'ALL'"
)
risk = inline_intent.sub(
    "      // V6 侧栏快捷队列只投影既有服务端过滤参数；不在浏览器本地筛选或扩大 allowedActions。\n"
    "      this.activeQueue = resolveRiskQueueIntent(q)",
    risk,
    count=1
)
if risk.count(RISK_IMPORT) != 1:
    raise SystemExit('risk helper import duplication remains')
if risk.count('this.activeQueue = resolveRiskQueueIntent(q)') != 1:
    raise SystemExit('risk helper call is missing or duplicated')
risk_path.write_text(risk, encoding='utf-8')
