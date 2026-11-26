"""统一资源接口：查询、导出、登记和动作按模块 key 分派到领域服务。"""
from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.schemas import ActionPayload, ActionResult, EntryPayload, PageResult
from app.services import service_for

router = APIRouter(prefix="/api", tags=["业务资源"])


def require_service(module: str):
    service = service_for(module)
    if service is None:
        raise HTTPException(status_code=404, detail=f"未知业务模块：{module}")
    return service


def operator_context(request: Request, payload: EntryPayload | ActionPayload | None = None) -> dict[str, Any]:
    """汇总操作人上下文：请求体 operator 优先，其次 X-Operator 头与 operator 查询参数。"""
    operator = ""
    if payload is not None and getattr(payload, "operator", None):
        operator = str(payload.operator).strip()
    if not operator:
        operator = (request.headers.get("x-operator") or "").strip()
    if not operator:
        operator = str(request.query_params.get("operator") or "").strip()
    context: dict[str, Any] = {"operator": operator}
    if payload is not None:
        # 顶层额外字段（如 签核人/撤回原因）也并入上下文
        extra_top = getattr(payload, "model_extra", None)
        if isinstance(extra_top, dict):
            for key, value in extra_top.items():
                if value is not None:
                    context.setdefault(key, value)
        remark = getattr(payload, "remark", None)
        if remark:
            context["remark"] = remark
        extra = getattr(payload, "values", None)
        if isinstance(extra, dict):
            context.update(extra)
        expected_version = getattr(payload, "expected_version", None)
        if expected_version is not None:
            context["expected_version"] = expected_version
    return context


@router.get("/{module}", response_model=PageResult[dict])
def list_entries(
    module: str,
    request: Request,
    keyword: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
) -> PageResult[dict]:
    service = require_service(module)
    filters = {
        key: value.strip()
        for key, value in request.query_params.items()
        if key in service.LIST_FIELDS and value.strip()
    }
    items, total = service.list_entries(
        filters=filters, keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/{module}/export")
def export_entries(
    module: str,
    request: Request,
    keyword: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> StreamingResponse:
    service = require_service(module)
    filters = {
        key: value.strip()
        for key, value in request.query_params.items()
        if key in service.LIST_FIELDS and value.strip()
    }
    items, _ = service.list_entries(
        filters=filters, keyword=keyword, status=status, page=1, size=1_000_000)
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["id", *service.LIST_FIELDS, "status"])
    for item in items:
        values = [item.get("id"), *(item.get(field, "") for field in service.LIST_FIELDS),
                  item.get("status", "")]
        writer.writerow([
            "'" + str(value) if str(value or "").startswith(("=", "+", "-", "@")) else value
            for value in values
        ])
    return StreamingResponse(
        iter([output.getvalue()]), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{module}.csv"'},
    )


@router.get("/{module}/{entry_id}", response_model=dict)
def get_entry(module: str, entry_id: int) -> dict[str, Any]:
    service = require_service(module)
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"{service.ENTITY} {entry_id} 不存在或已归档")
    return entry


@router.post("/{module}", response_model=ActionResult)
def create_entry(module: str, payload: EntryPayload, request: Request) -> ActionResult:
    service = require_service(module)
    context = operator_context(request, payload)
    values = dict(payload.values or {})
    # 顶层 operator/remark 也并入 values，方便领域服务统一取值
    if payload.operator and not values.get("operator"):
        values["operator"] = payload.operator
    if payload.remark and not values.get("remark"):
        values["remark"] = payload.remark

    # 快照签核单：走带完整话术的制单提交
    submit_signoff = getattr(service, "submit_signoff", None)
    if callable(submit_signoff):
        ok, message, entry = submit_signoff(values, context=context)
        return ActionResult(ok=ok, message=message, entry=entry)

    # 维度发布：带签核单引用时走原子开单
    signoff_ref = values.get("signoff_id") or values.get("签核单编号") or values.get("signoff_no")
    apply_fn = getattr(service, "create_application", None)
    if signoff_ref not in (None, "") and callable(apply_fn):
        ok, message, entry, _code = apply_fn(values, context=context)
        return ActionResult(ok=ok, message=message, entry=entry)

    entry, missing = service.create_entry(values, context=context)
    if missing:
        # 领域服务用 __business__: 前缀返回完整业务拒绝话术
        first = str(missing[0])
        if first.startswith("__business__:"):
            return ActionResult(ok=False, message=first.split(":", 1)[1], entry=None)
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message=f"{service.ENTITY}已登记", entry=entry)


@router.post("/{module}/{entry_id}/actions", response_model=ActionResult)
def run_action(
    module: str, entry_id: int, payload: ActionPayload, request: Request,
) -> ActionResult:
    service = require_service(module)
    context = operator_context(request, payload)
    entry, message = service.run_action(
        entry_id, payload.action.strip(), context=context,
    )
    return ActionResult(ok=entry is not None, message=message, entry=entry)
