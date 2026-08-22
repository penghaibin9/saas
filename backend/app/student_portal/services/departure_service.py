"""学生 PC 门户 · 离校清单（V3 施工手册 SP-D01~SP-D04）。

本文件只是门户侧的薄 facade：真正的跨域编排在
:mod:`app.services.departure_projection_service`，那里不依赖 student_portal，
以便将来教师端需要同一份离校事实时可以直接复用，而不是再抄一遍。
"""
from __future__ import annotations

from app.services import departure_projection_service as projection


def my(user: dict) -> dict:
    return projection.build_my_departure(user)
