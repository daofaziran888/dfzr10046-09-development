"""业务路由汇总：跨模块流程路由先注册，通用资源路由兜底分派。"""
from __future__ import annotations

from app.routers import flow, resource

ROUTERS = [flow, resource]
