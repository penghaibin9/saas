"""公共 Excel 底座 · 模块接入契约（V1.1）。

后续每个业务模块「只写配置，不写 Excel 代码」：定义 ColumnSpec 列表 + ImportSpec/ExportSpec，
把校验、模板、错误行、台账、脱敏、审计等通用能力交给底座（pipeline.py）。

设计原则（CLAUDE.md §38/§39）：
- 底座只负责通用能力；业务模块只提供「字段配置 + 校验规则 + 保存逻辑 + 导出查询」。
- 不重复造轮子：底层 xlsx 读写复用 app.services.xlsx_util。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# 行内自定义校验器签名：fn(value: str, col: ColumnSpec) -> str | None
CellValidator = Callable[[str, "ColumnSpec"], Optional[str]]
# 库内查重扩展点：fn(rows: list[dict]) -> dict[int, str]  （1-based 行号 → 冲突原因）
DuplicateCheck = Callable[[list[dict]], dict]
# 业务规则校验扩展点：fn(row: dict, row_no: int) -> str | None
BusinessValidate = Callable[[dict, int], Optional[str]]
# 行转换扩展点：fn(row: dict) -> dict（清洗/映射为落库结构）
TransformRow = Callable[[dict], dict]
# 落库扩展点：fn(rows: list[dict]) -> dict（返回 {created:int,...} 统计）
PersistRows = Callable[[list[dict]], dict]
# 导出查询扩展点：fn(**filters) -> list[dict]
ExportQuery = Callable[..., list]


@dataclass
class ColumnSpec:
    """单列定义：既是「导入列」也可复用为「导出列」。"""
    key: str                                  # 内部字段 key
    title: str                                # Excel 表头文字
    required: bool = False                    # 是否必填（导入）
    type: str = "str"                         # str/int/decimal/date/phone/idcard/creditcode/email/enum
    max_length: Optional[int] = None          # 最大长度
    options: Optional[list] = None            # enum 可选值
    example: Any = ""                         # 模板示例值
    help_text: str = ""                       # 填写说明
    unique_in_file: bool = False              # 文件内查重键
    validators: list[CellValidator] = field(default_factory=list)  # 追加自定义校验
    mask: Optional[Callable[[Any], Any]] = None                    # 导出脱敏函数


@dataclass
class ImportSpec:
    """一个业务导入的完整契约。"""
    module_key: str                           # e.g. "internship"
    biz_type: str                             # e.g. "position"
    template_name: str                        # 模板文件名 / 弹窗标题
    columns: list[ColumnSpec]
    notes: list[str] = field(default_factory=list)          # 模板「填写说明」页
    duplicate_check: Optional[DuplicateCheck] = None        # 库内查重扩展点
    business_validate: Optional[BusinessValidate] = None    # 业务规则扩展点
    transform_row: Optional[TransformRow] = None            # 行清洗
    persist_rows: Optional[PersistRows] = None              # 落库
    permission_key: Optional[str] = None                    # 权限 key（后端拦截扩展点）
    audit_action: Optional[str] = None                      # 审计动作名
    template_version: str = "v1"
    max_preview_errors: int = 200                           # 预校验回传错误上限

    @property
    def header_map(self) -> dict:
        """表头文字 → 字段 key（供 xlsx_util.read_xlsx）。"""
        return {c.title: c.key for c in self.columns}

    @property
    def headers(self) -> list:
        return [c.title for c in self.columns]

    @property
    def required_titles(self) -> list:
        return [c.title for c in self.columns if c.required]

    @property
    def unique_columns(self) -> list:
        return [c for c in self.columns if c.unique_in_file]

    def row_values(self, row: dict) -> list:
        """按列顺序取值（错误行 Excel 用）。"""
        return [row.get(c.key, "") for c in self.columns]


@dataclass
class ExportSpec:
    """一个业务导出的完整契约。"""
    module_key: str
    biz_type: str
    sheet_title: str
    columns: list[ColumnSpec]
    file_name: str = ""                       # 台账文件名（缺省用 sheet_title）
    export_query: Optional[ExportQuery] = None
    permission_key: Optional[str] = None
    audit_action: Optional[str] = None

    @property
    def headers(self) -> list:
        return [c.title for c in self.columns]

    def to_row(self, item: dict) -> list:
        """把一条业务数据映射为一行导出值，逐列应用脱敏。"""
        out = []
        for c in self.columns:
            v = item.get(c.key, "")
            if c.mask and v not in (None, ""):
                v = c.mask(v)
            out.append("" if v is None else v)
        return out
