"""快照签核 ↔ 维度发布的跨模块流程接口。

这些路径把“制单提交 / 双人签核 / 撤回 / 凭单开单 / 可用性查询”显式化，
并在并发冲突时返回 409 + 与统一动作接口一致的 ActionResult 载荷。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.schemas import (
    PublishApplyPayload,
    SignoffActionPayload,
    SignoffSubmitPayload,
)
from app.services.dim_publish import DimPublishService
from app.services.snapshot_signoff import SnapshotSignoffService

router = APIRouter(prefix="/api", tags=["签核发布流程"])

signoff_service = SnapshotSignoffService()
publish_service = DimPublishService()


def _context(request: Request, payload: Any = None) -> dict[str, Any]:
    operator = ""
    if payload is not None and getattr(payload, "operator", None):
        operator = str(payload.operator).strip()
    if not operator:
        operator = (request.headers.get("x-operator") or "").strip()
    if not operator:
        operator = str(request.query_params.get("operator") or "").strip()
    context: dict[str, Any] = {"operator": operator}
    if payload is not None:
        for key in (
            "signer", "签核人", "撤回人", "reason", "撤回原因",
            "conclusion", "签核结论", "opinion", "签核意见", "remark",
            "expected_version",
        ):
            value = getattr(payload, key, None)
            if value is not None:
                context[key] = value
    return context


def _result(ok: bool, message: str, entry: dict[str, Any] | None, code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=code,
        content={"ok": ok, "message": message, "entry": entry, "detail_state": entry},
    )


# ---------------- 快照签核单 ----------------

@router.post("/snapshot_signoff/submit")
@router.post("/signoff/submit")
def submit_signoff(payload: SignoffSubmitPayload, request: Request) -> JSONResponse:
    values = payload.model_dump(exclude_none=True)
    context = _context(request, payload)
    ok, message, entry = signoff_service.submit_signoff(values, context=context)
    return _result(ok, message, entry, 200 if ok else 422)


@router.get("/snapshot_signoff/todos")
@router.get("/signoff/todos")
@router.get("/dim_publish/todos")
@router.get("/publish/todos")
def signoff_todos() -> dict[str, Any]:
    todos = signoff_service.publish_todos()
    return {"items": todos, "total": len(todos)}


@router.get("/snapshot_signoff/{entry_id}/usability")
def signoff_usability(entry_id: int) -> JSONResponse:
    row = signoff_service.get_entry(entry_id)
    if row is None:
        return JSONResponse(status_code=404, content={"usable": False, "code": "missing", "reason": "签核单不存在"})
    usable, code, reason = signoff_service.usability(row)
    return JSONResponse(content={
        "usable": usable, "code": code, "reason": reason,
        "status": row.get("status"), "entry": row,
        "next_step": signoff_service.next_step(row),
    })


@router.post("/snapshot_signoff/{entry_id}/confirm")
@router.post("/signoff/{entry_id}/confirm")
def confirm_signoff(entry_id: int, payload: SignoffActionPayload, request: Request) -> JSONResponse:
    context = _context(request, payload)
    signer = payload.签核人 or payload.signer or payload.operator or request.headers.get("x-operator")
    ok, message, row = signoff_service.confirm_signoff(
        entry_id, context=context, signer=signer,
        conclusion=payload.签核结论 or payload.conclusion,
        opinion=payload.签核意见 or payload.opinion or payload.remark,
    )
    return _result(ok, message, row, 200 if ok else 409 if row and row.get("status") != "待签核" else 422)


@router.post("/snapshot_signoff/{entry_id}/withdraw")
@router.post("/signoff/{entry_id}/withdraw")
def withdraw_signoff(entry_id: int, payload: SignoffActionPayload, request: Request) -> JSONResponse:
    context = _context(request, payload)
    operator = payload.撤回人 or payload.operator or request.headers.get("x-operator")
    ok, message, row = signoff_service.withdraw_signoff(
        entry_id, context=context, operator=operator,
        reason=payload.撤回原因 or payload.reason or payload.remark,
        expected_version=payload.expected_version,
    )
    if ok:
        code = 200
    elif row is not None and row.get("status") in ("已使用",):
        code = 409
    elif row is not None and "冲突" in message:
        code = 409
    else:
        code = 422
    return _result(ok, message, row, code)


@router.post("/snapshot_signoff/{entry_id}/reject")
def reject_signoff(entry_id: int, payload: SignoffActionPayload, request: Request) -> JSONResponse:
    context = _context(request, payload)
    row, message = signoff_service.reject_signoff(entry_id, context=context)
    return _result(row is not None and row.get("status") == "已驳回", message, row)


# ---------------- 维度发布开单 ----------------

@router.post("/dim_publish/apply")
@router.post("/dim_publish/applications")
@router.post("/publish/apply")
def publish_apply(payload: PublishApplyPayload, request: Request) -> JSONResponse:
    values = payload.model_dump(exclude_none=True)
    context = _context(request, payload)
    ok, message, entry, code = publish_service.create_application(values, context=context)
    return _result(ok, message, entry, code if not ok else 200)
