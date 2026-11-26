"""通用接口契约；模块字段由领域服务持有，不再为每个模块复制一份模型类。"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    size: int = 20


class ActionResult(BaseModel):
    ok: bool
    message: str
    entry: dict[str, Any] | None = None
    # 冲突/校验失败时可附带当前最新状态，方便两页直接说明“这张单还能不能用”
    detail_state: dict[str, Any] | None = None


class EntryPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    values: dict[str, Any] = Field(default_factory=dict)
    remark: str | None = None
    operator: str | None = None


class ActionPayload(BaseModel):
    # 允许 {"action": "确认签核", "签核人": "李四"} 这类顶层中文操作字段
    model_config = ConfigDict(extra="allow")

    action: str
    remark: str | None = None
    operator: str | None = None
    # 双人签核/撤回时的操作人及附加字段（签核人、撤回原因、结论等）
    values: dict[str, Any] | None = None
    expected_version: int | None = None


class SignoffSubmitPayload(BaseModel):
    snapshot_id: int | str | None = None
    snapshot_no: str | None = None
    快照编号: str | None = None
    maker: str | None = None
    制单人: str | None = None
    operator: str | None = None
    制单说明: str | None = None
    remark: str | None = None
    签核单编号: str | None = None


class SignoffActionPayload(BaseModel):
    operator: str | None = None
    signer: str | None = None
    签核人: str | None = None
    撤回人: str | None = None
    reason: str | None = None
    撤回原因: str | None = None
    conclusion: str | None = None
    签核结论: str | None = None
    opinion: str | None = None
    签核意见: str | None = None
    remark: str | None = None
    expected_version: int | None = None


class PublishApplyPayload(BaseModel):
    signoff_id: int | str | None = None
    signoff_no: str | None = None
    签核单编号: str | None = None
    signoffId: int | str | None = None
    申请说明: str | None = None
    说明: str | None = None
    description: str | None = None
    remark: str | None = None
    发布人: str | None = None
    发布申请人: str | None = None
    operator: str | None = None
    发布编号: str | None = None
    发布版本: str | None = None
    所属维度: str | None = None
    快照日期: str | None = None
    可见范围: str | None = None
    发布标签: str | None = None
