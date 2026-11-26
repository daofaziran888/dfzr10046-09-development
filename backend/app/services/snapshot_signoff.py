"""快照签核单领域服务：制单提交 → 另一位操作员双人确认 → 撤回/失效/被发布占用。

核心约束：
1. 制单人与签核确认人不能是同一人，同一人受理直接拒绝；
2. 签核单绑定快照的“修订号 + 内容摘要”，快照补改产生新修订后，旧签核不再对当前修订有效；
3. 发布开单与签核撤回共用 store.FLOW_LOCK，在锁内完成状态校验与写入，
   并发时同一张签核单至多有一个生效结果（要么已使用，要么已撤回）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.base import BaseModuleService
from app.store import FLOW_LOCK, store

# 状态常量
PENDING = "待签核"
APPROVED = "已签核"
USED = "已使用"
WITHDRAWN = "已撤回"
STALE = "已失效"
REJECTED = "已驳回"

# 仍可被另一位操作员确认的状态
CONFIRMABLE = {PENDING}
# 允许撤回的状态（制单后、以及已签核尚未被发布使用时）
WITHDRAWABLE = {PENDING, APPROVED}


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _next_id(rows: list[dict[str, Any]]) -> int:
    return max((int(r.get("id", 0)) for r in rows), default=0) + 1


class SnapshotSignoffService(BaseModuleService):
    MODULE = "snapshot_signoff"
    ENTITY = "快照签核单"
    LIST_FIELDS = [
        "签核单编号", "快照编号", "所属维度", "快照日期", "修订号", "快照摘要值",
        "制单人", "制单说明", "提交时间",
        "签核人", "签核结论", "签核意见", "签核时间",
        "撤回人", "撤回原因", "撤回时间",
        "发布申请编号", "失效原因",
    ]
    REQUIRED_FIELDS = ["快照编号", "制单人"]
    STATUS_ORDER = [PENDING, APPROVED, USED, WITHDRAWN, STALE, REJECTED]
    # 通用动作入口也能驱动完整流转（测试锚点 action-{id}-动作名）
    ACTION_RULES = {
        "确认签核": APPROVED,
        "签核通过": APPROVED,
        "签核": APPROVED,
        "驳回": REJECTED,
        "撤回": WITHDRAWN,
        "撤回签核": WITHDRAWN,
    }
    NEGATIVE_ACTIONS = ["驳回"]

    # ---------- 查询与可用性说明 ----------

    def list_entries(self, **kwargs: Any):  # type: ignore[override]
        rows, total = super().list_entries(**kwargs)
        for row in rows:
            self.annotate(row)
        return rows, total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = super().get_entry(entry_id)
        if row is not None:
            self.annotate(row)
        return row

    def find_by_no(self, signoff_no: str) -> dict[str, Any] | None:
        signoff_no = (signoff_no or "").strip()
        for row in store.rows(self.MODULE):
            if str(row.get("签核单编号", "")) == signoff_no:
                return row
        return None

    def resolve(self, ref: Any) -> dict[str, Any] | None:
        """按数字 id、签核单编号或引用对象定位签核单。"""
        if ref is None:
            return None
        if isinstance(ref, dict):
            if ref.get("id") is not None:
                found = store.find(self.MODULE, int(ref["id"]))
                if found is not None:
                    return found
            return self.find_by_no(str(ref.get("签核单编号", "")))
        text = str(ref).strip()
        if text.isdigit():
            found = store.find(self.MODULE, int(text))
            if found is not None:
                return found
        return self.find_by_no(text)

    def bound_snapshot(self, row: dict[str, Any]) -> dict[str, Any] | None:
        snapshot_id = row.get("snapshot_id")
        if snapshot_id not in (None, ""):
            snap = store.find("dim_snapshot", int(snapshot_id))
            if snap is not None:
                return snap
        snap_no = row.get("快照编号")
        for snap in store.rows("dim_snapshot"):
            if str(snap.get("快照编号", "")) == str(snap_no):
                return snap
        return None

    def usability(self, row: dict[str, Any]) -> tuple[bool, str, str]:
        """返回 (是否可用于发布开单, 机器码, 人读说明)。两个页面共用这一份判定。"""
        status = str(row.get("status", ""))
        if status == APPROVED:
            snap = self.bound_snapshot(row)
            if snap is None:
                return False, "snapshot_missing", "签核单绑定的快照不存在，本单不可使用"
            bound_rev = str(row.get("修订号", ""))
            current_rev = str(snap.get("修订号", bound_rev))
            bound_digest = str(row.get("快照摘要值", ""))
            current_digest = str(snap.get("快照摘要值", ""))
            if bound_rev != current_rev or (bound_digest and bound_digest != current_digest):
                return (
                    False, "revision_stale",
                    f"修订不匹配：本单签核的是修订 {bound_rev}（摘要 {bound_digest or '—'}），"
                    f"快照已补改为修订 {current_rev}（摘要 {current_digest or '—'}），"
                    "本单不能用于本次修订的发布，须按当前修订重新制单签核",
                )
            return (
                True, "usable",
                f"签核有效：签核修订 {bound_rev} 与快照当前修订一致，本单可用于维度发布开单",
            )
        if status == USED:
            pub_no = row.get("发布申请编号") or "（见维度发布页）"
            return False, "used", f"本单已用于发布申请 {pub_no}，不能再次开单，也不能撤回"
        if status == WITHDRAWN:
            reason = row.get("撤回原因") or "制单/签核人主动撤回"
            return False, "withdrawn", f"本单已撤回（{reason}），即刻起不可用于发布开单"
        if status == STALE:
            reason = row.get("失效原因") or "快照内容已补改，修订版本不一致"
            return False, "stale", f"本单已失效：{reason}，须按快照当前修订重新制单签核"
        if status == REJECTED:
            return False, "rejected", "本单签核结论为驳回，不可用于发布开单"
        return False, "pending", "本单尚待另一位操作员双人确认，暂不可用于发布开单"

    def annotate(self, row: dict[str, Any]) -> dict[str, Any]:
        usable, code, reason = self.usability(row)
        row["usable"] = usable
        row["usability_code"] = code
        row["usability_reason"] = reason
        row["can_confirm"] = row.get("status") in CONFIRMABLE
        row["can_withdraw"] = row.get("status") in WITHDRAWABLE
        row["next_step"] = self.next_step(row)
        if row.get("status") == APPROVED and usable:
            row["发布待办"] = "待创建发布申请"
        elif row.get("status") == APPROVED:
            row["发布待办"] = "修订已失效"
        elif row.get("status") == USED:
            row["发布待办"] = f"已开单：{row.get('发布申请编号', '')}"
        elif row.get("status") == WITHDRAWN:
            row["发布待办"] = "待办已撤销"
        else:
            row["发布待办"] = ""
        return row

    def next_step(self, row: dict[str, Any], operator: str = "") -> str:
        """给操作人的下一步指引，签核页与发布页据此说明“此人下一步能做什么”。"""
        status = str(row.get("status", ""))
        me = (operator or "").strip()
        maker = str(row.get("制单人", "")).strip()
        if status == PENDING:
            if me and maker and me == maker:
                return "下一步：制单人与签核人不能为同一人，请切换为另一位操作员后再确认签核"
            return "下一步：由非制单人的另一位操作员填写本人标识并确认签核；签核通过后会生成维度发布待办"
        if status == APPROVED:
            usable, code, _ = self.usability(row)
            if usable:
                return "下一步：发布人打开「维度发布」页，凭本有效签核单填写说明并创建发布申请"
            return "下一步：按快照当前修订重新发起快照签核，旧签核不能用于本次修订"
        if status == USED:
            pub_no = row.get("发布申请编号") or ""
            return f"下一步：发布申请 {pub_no} 已在「维度发布」页写入，可继续启动发布、确认发布；本签核单已结案"
        if status == WITHDRAWN:
            return "下一步：本单已撤回不可恢复使用；如仍需发布，请由制单人按当前修订重新发起签核"
        if status == STALE:
            return "下一步：快照已有新修订，请按当前修订重新制单并由另一位操作员签核"
        if status == REJECTED:
            return "下一步：可根据签核意见修改后重新制单，再由另一位操作员签核"
        return ""

    # ---------- 制单提交 ----------

    def create_entry(
        self, values: dict[str, Any], *, context: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, list[str]]:
        ok, _message, entry = self.submit_signoff(values, context=context)
        if entry is not None and ok:
            return entry, []
        # 兼容通用资源路由的 missing 字段提示
        missing = [
            field for field in self.REQUIRED_FIELDS
            if not str(values.get(field) or values.get(self._alias(field)) or "").strip()
        ]
        if missing:
            return None, missing
        return None, [_message or "快照签核单受理失败"]

    @staticmethod
    def _alias(field: str) -> str:
        aliases = {"快照编号": "snapshot_no", "制单人": "operator"}
        return aliases.get(field, field)

    def submit_signoff(
        self, values: dict[str, Any], *, context: dict[str, Any] | None = None,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        context = context or {}
        operator = (
            values.get("制单人") or values.get("maker") or values.get("submitter")
            or context.get("operator") or ""
        )
        operator = str(operator).strip()
        snapshot_ref = (
            values.get("snapshot_id") or values.get("快照编号")
            or values.get("snapshot_no") or values.get("snapshotId")
        )
        snapshot = None
        if snapshot_ref not in (None, ""):
            text = str(snapshot_ref).strip()
            if text.isdigit():
                snapshot = store.find("dim_snapshot", int(text))
            if snapshot is None:
                for snap in store.rows("dim_snapshot"):
                    if str(snap.get("快照编号", "")) == text:
                        snapshot = snap
                        break
        if snapshot is None and isinstance(snapshot_ref, int):
            snapshot = store.find("dim_snapshot", snapshot_ref)

        if not operator:
            return False, "拒绝受理：请填写制单人（操作员工号或姓名）", None
        if snapshot is None:
            return False, "拒绝受理：请选择一笔真实存在的维度快照", None

        with FLOW_LOCK:
            rows = store.rows(self.MODULE)
            next_id = _next_id(rows)
            signoff_no = str(
                values.get("签核单编号") or values.get("signoff_no") or ""
            ).strip()
            if not signoff_no:
                signoff_no = f"QH-{datetime.now():%Y%m%d}-{next_id:03d}"
            if any(str(r.get("签核单编号")) == signoff_no for r in rows):
                return False, f"签核单编号 {signoff_no} 已存在，不能重复制单", None

            rev_no = str(snapshot.get("修订号") or "R1")
            entry: dict[str, Any] = {
                "id": next_id,
                "status": PENDING,
                "pending": True,
                "abnormal": False,
                "签核单编号": signoff_no,
                "snapshot_id": int(snapshot["id"]),
                "快照编号": snapshot.get("快照编号", ""),
                "所属维度": snapshot.get("所属维度", ""),
                "快照日期": snapshot.get("快照日期", ""),
                "修订号": rev_no,
                "修订版本": int(snapshot.get("修订版本", 1) or 1),
                "快照摘要值": snapshot.get("快照摘要值", ""),
                "制单人": operator,
                "制单说明": str(values.get("制单说明") or values.get("remark") or "").strip(),
                "提交时间": now_text(),
                "签核人": "", "签核结论": "", "签核意见": "", "签核时间": "",
                "撤回人": "", "撤回原因": "", "撤回时间": "",
                "发布申请编号": "", "失效原因": "",
                "version": 1,
            }
            rows.append(entry)
            self.annotate(entry)

            # 兼容“一张表单同时填制单人与签核人”的实现：若显式给了不同的签核人，
            # 制单提交后立即完成确认；同一人则按规则拒绝受理。
            inline_signer = str(
                values.get("签核人") or values.get("signer")
                or values.get("confirmer") or ""
            ).strip()
            if inline_signer:
                if inline_signer == operator:
                    return False, (
                        f"拒绝受理：制单人与签核人属于同一人「{operator}」，"
                        "双人签核要求由另一位操作员确认"
                    ), entry
                ok2, message2, confirmed = self.confirm_signoff(
                    entry["id"],
                    signer=inline_signer,
                    conclusion=str(values.get("签核结论") or "通过"),
                    opinion=str(values.get("签核意见") or ""),
                )
                return ok2, message2, confirmed

            return True, (
                f"快照签核单 {signoff_no} 已由制单人 {operator} 提交，"
                "等待另一位操作员确认；制单与签核不得为同一人"
            ), entry

    # ---------- 签核确认 / 驳回（双人规则） ----------

    def run_action(
        self, entry_id: int, action: str, *, context: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        context = context or {}
        if action in ("确认签核", "签核通过", "签核", "审核通过", "审核", "批准", "同意"):
            ok, message, row = self.confirm_signoff(entry_id, context=context)
            return (row if ok else None), message
        if action in ("撤回", "撤回签核", "撤销", "撤销签核"):
            ok, message, row = self.withdraw_signoff(entry_id, context=context)
            return (row if ok else None), message
        if action in ("驳回", "拒绝签核", "审核驳回"):
            return self.reject_signoff(entry_id, context=context)
        if action in ("提交", "提交签核"):
            # 已存在的草稿/待签核单无需重复提交
            row = store.find(self.MODULE, entry_id)
            if row is None:
                return None, f"快照签核单 {entry_id} 不存在或已归档"
            return row, f"签核单 {row.get('签核单编号')} 当前为「{row.get('status')}」"
        if action in ("发布开单", "生成发布申请", "创建发布申请", "凭单开单", "开单"):
            # 跨模块开单：签核单动作也能直接创建维度发布申请，与 /api/dim_publish/apply 等价
            from app.services.dim_publish import DimPublishService
            payload = {"signoff_id": entry_id}
            if isinstance(context, dict):
                payload.update(context)
            ok, message, pub_entry, _code = DimPublishService().create_application(
                payload, context=context,
            )
            return (pub_entry if ok else None), message
        return None, f"动作「{action}」不属于{self.MODULE}可执行范围"

    def confirm_signoff(
        self, entry_id: int, *, context: dict[str, Any] | None = None,
        signer: str | None = None, conclusion: str | None = None,
        opinion: str | None = None,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        context = context or {}
        operator = (
            signer or context.get("签核人") or context.get("operator")
            or context.get("signer") or ""
        )
        operator = str(operator).strip()
        opinion = opinion if opinion is not None else str(
            context.get("签核意见") or context.get("remark") or ""
        )
        conclusion = conclusion or str(context.get("签核结论") or "通过")

        with FLOW_LOCK:
            row = store.find(self.MODULE, entry_id)
            if row is None:
                return False, f"快照签核单 {entry_id} 不存在或已归档", None
            if not operator:
                return False, "拒绝受理：请填写签核人（必须是另一位操作员）", row
            maker = str(row.get("制单人", "")).strip()
            if operator == maker:
                row["abnormal"] = True
                return False, (
                    f"拒绝受理：制单人与签核人属于同一人「{operator}」，"
                    "双人签核要求由另一位操作员确认"
                ), row
            if row.get("status") != PENDING:
                return False, (
                    f"签核单 {row.get('签核单编号')} 当前状态为「{row.get('status')}」，"
                    "不能重复签核"
                ), row

            # 签核时再次核对快照修订：不允许给已经补改过的旧内容背书
            snap = self.bound_snapshot(row)
            if snap is not None:
                bound_rev = str(row.get("修订号", ""))
                current_rev = str(snap.get("修订号", bound_rev))
                if bound_rev != current_rev:
                    row["status"] = STALE
                    row["pending"] = False
                    row["失效原因"] = f"签核期间快照已补改至 {current_rev}"
                    self.annotate(row)
                    return False, (
                        f"拒绝签核：本单对应修订 {bound_rev}，快照已补改为 {current_rev}，"
                        "请按本次修订重新制单"
                    ), row

            row["签核人"] = operator
            row["签核结论"] = conclusion or "通过"
            row["签核意见"] = str(opinion).strip()
            row["签核时间"] = now_text()
            row["status"] = APPROVED
            row["pending"] = False
            row["abnormal"] = False
            row["version"] = int(row.get("version", 1)) + 1

            # 同一快照同一修订只保留一份有效签核：新签核通过后，旧的已签核单被替代
            for other in store.rows(self.MODULE):
                if other.get("id") == row.get("id"):
                    continue
                if other.get("snapshot_id") == row.get("snapshot_id") \
                        and str(other.get("修订号")) == str(row.get("修订号")) \
                        and other.get("status") == APPROVED:
                    other["status"] = STALE
                    other["pending"] = False
                    other["失效原因"] = f"已被更新的有效签核单 {row.get('签核单编号')} 替代"
                    other["version"] = int(other.get("version", 1)) + 1

            self.annotate(row)
            return True, (
                f"签核单 {row.get('签核单编号')} 已由 {operator} 确认，"
                "签核结论：通过；已生成维度发布待办，发布人可凭此有效签核单创建发布申请"
            ), row

    def reject_signoff(
        self, entry_id: int, *, context: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        context = context or {}
        operator = str(context.get("operator") or context.get("签核人") or "").strip()
        with FLOW_LOCK:
            row = store.find(self.MODULE, entry_id)
            if row is None:
                return None, f"快照签核单 {entry_id} 不存在或已归档"
            maker = str(row.get("制单人", "")).strip()
            if operator and operator == maker:
                return row, (
                    f"拒绝受理：制单人与签核人属于同一人「{operator}」，双人签核要求另一位操作员确认"
                )
            if row.get("status") != PENDING:
                return row, f"签核单当前状态为「{row.get('status')}」，不能驳回"
            row["status"] = REJECTED
            row["pending"] = False
            row["abnormal"] = True
            row["签核人"] = operator or row.get("签核人", "")
            row["签核结论"] = "驳回"
            row["签核意见"] = str(context.get("remark") or context.get("签核意见") or "").strip()
            row["签核时间"] = now_text()
            self.annotate(row)
            return row, f"签核单 {row.get('签核单编号')} 已驳回"

    # ---------- 撤回（与发布开单竞争） ----------

    def withdraw_signoff(
        self, ref: Any, *, context: dict[str, Any] | None = None,
        operator: str | None = None, reason: str | None = None,
        expected_version: int | None = None,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        context = context or {}
        operator = str(
            operator or context.get("撤回人") or context.get("operator") or ""
        ).strip()
        reason = reason if reason is not None else str(
            context.get("撤回原因") or context.get("reason")
            or context.get("remark") or ""
        )
        if expected_version is None and context.get("expected_version") is not None:
            try:
                expected_version = int(context["expected_version"])
            except (TypeError, ValueError):
                expected_version = None

        with FLOW_LOCK:
            row = self.resolve(ref) if not isinstance(ref, int) else store.find(self.MODULE, ref)
            if row is None and isinstance(ref, int):
                row = store.find(self.MODULE, ref)
            if row is None:
                return False, f"快照签核单 {ref} 不存在或已归档", None

            current_version = int(row.get("version", 1))
            if expected_version is not None and expected_version != current_version:
                # 乐观锁：并行的另一个操作已经提交
                self.annotate(row)
                return False, (
                    f"操作冲突：签核单 {row.get('签核单编号')} 版本已变化"
                    f"（期望 v{expected_version}，当前 v{current_version}），请刷新后重试"
                ), row

            status = str(row.get("status", ""))
            if status == WITHDRAWN:
                return False, f"签核单 {row.get('签核单编号')} 已是「已撤回」状态，不能重复撤回", row
            if status == USED:
                pub_no = row.get("发布申请编号") or "另一笔发布申请"
                return False, (
                    f"撤回冲突：签核单 {row.get('签核单编号')} 已被发布申请 {pub_no} "
                    "使用，开单已先生效，不能撤回；该签核结果仍有效且已结案"
                ), row
            if status not in WITHDRAWABLE:
                return False, (
                    f"签核单 {row.get('签核单编号')} 当前为「{status}」，不能撤回"
                ), row

            row["status"] = WITHDRAWN
            row["pending"] = False
            row["撤回人"] = operator
            row["撤回原因"] = str(reason).strip() or "未填写原因"
            row["撤回时间"] = now_text()
            row["version"] = current_version + 1
            self.annotate(row)
            return True, (
                f"签核单 {row.get('签核单编号')} 已撤回，"
                "本单即刻起不可用于发布开单；维度发布待办同步撤销"
            ), row

    # ---------- 快照补改联动 ----------

    def invalidate_for_revision(
        self, snapshot_id: int, new_rev: str, reason: str,
    ) -> list[str]:
        """快照补改产生新修订后，把绑定旧修订的未结签核单置为已失效。"""
        affected: list[str] = []
        with FLOW_LOCK:
            for row in store.rows(self.MODULE):
                if int(row.get("snapshot_id", 0) or 0) != int(snapshot_id):
                    continue
                if row.get("status") in (PENDING, APPROVED):
                    row["status"] = STALE
                    row["pending"] = False
                    row["失效原因"] = reason or f"快照已补改为修订 {new_rev}"
                    row["version"] = int(row.get("version", 1)) + 1
                    self.annotate(row)
                    affected.append(str(row.get("签核单编号")))
        return affected

    def publish_todos(self) -> list[dict[str, Any]]:
        """签核通过且仍可用的单，即“维度发布待办”。"""
        todos = []
        for row in store.rows(self.MODULE):
            self.annotate(row)
            if row.get("status") == APPROVED and row.get("usable"):
                todos.append(row)
        return todos
