from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class InternshipCompletedEvent:
    tenant_id: int
    student_id: int
    internship_id: int
    batch_id: int | None


class LifecycleGateway(Protocol):
    """替代 SaaS platform.document_lifecycle 对岗位实习核心域的反向依赖。"""

    def internship_completed(self, event: InternshipCompletedEvent) -> None: ...


class StandaloneLifecycleGateway:
    def internship_completed(self, event: InternshipCompletedEvent) -> None:
        # Standalone 没有 Student360/平台生命周期时保持 no-op；
        # 调用方仍可在本域审计中记录正式完成事实。
        return None


lifecycle_gateway: LifecycleGateway = StandaloneLifecycleGateway()
