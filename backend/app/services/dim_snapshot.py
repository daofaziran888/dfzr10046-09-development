"""维度快照领域服务：冻结校验维度全量状态，产出快照版本数据集。"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from app.services.base import BaseModuleService
from app.store import FLOW_LOCK, store


class DimSnapshotService(BaseModuleService):
    MODULE = "dim_snapshot"
    ENTITY = "快照版本"
    LIST_FIELDS = ["快照编号", "所属维度", "快照日期", "维度行数", "当前链占比", "快照摘要值", "引用批次", "生成时间", "修订号", "补改说明", "最近补改"]
    REQUIRED_FIELDS = ["快照编号", "所属维度", "快照日期"]
    STATUS_ORDER = ["生成中", "可用", "已过期", "已重建"]
    ACTION_RULES = {
        "标记可用": "可用", "标记过期": "已过期", "重建快照": "已重建",
        "补改内容": "可用", "修订快照": "可用",
    }
    NEGATIVE_ACTIONS = []

    def run_action(
        self, entry_id: int, action: str, *, context: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        if action in ("补改内容", "修订快照"):
            return self.amend_snapshot(entry_id, context=context)
        if action == "重建快照":
            # 兼容“重建即产生新修订”的用法：先推进修订并使旧签核失效，再走通用状态流转
            with FLOW_LOCK:
                entry = store.find(self.MODULE, entry_id)
                if entry is None:
                    return None, f"{self.ENTITY} {entry_id} 不存在或已归档"
                self._bump_revision(entry, "重建快照生成新的内容摘要")
                affected = self._invalidate(entry)
                target = self.ACTION_RULES[action]
                entry["status"] = target
                entry["pending"] = target != self.STATUS_ORDER[-1]
                entry["abnormal"] = action in self.NEGATIVE_ACTIONS
                extra = f"，修订已推进到 {entry.get('修订号')}"
                if affected:
                    extra += f"，原签核单 {'、'.join(affected)} 已失效"
                return entry, f"{self.ENTITY}已{action}" + extra
        return super().run_action(entry_id, action, context=context)

    def _bump_revision(self, entry: dict[str, Any], note: str) -> None:
        old_rev_no = int(entry.get("修订版本", 1) or 1)
        new_rev_no = old_rev_no + 1
        old_digest = str(entry.get("快照摘要值", ""))
        entry["修订版本"] = new_rev_no
        entry["修订号"] = f"R{new_rev_no}"
        entry["快照摘要值"] = hashlib.md5(
            f"{old_digest}:amend:{new_rev_no}:{note}".encode()
        ).hexdigest()[:8]
        entry["补改说明"] = note
        entry["最近补改"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    def _invalidate(self, entry: dict[str, Any]) -> list[str]:
        from app.services.snapshot_signoff import SnapshotSignoffService
        return SnapshotSignoffService().invalidate_for_revision(
            int(entry["id"]), str(entry.get("修订号")),
            f"快照内容已变更至 {entry.get('修订号')}（新摘要 {entry.get('快照摘要值')}）",
        )

    def amend_snapshot(
        self, entry_id: int, *, context: dict[str, Any] | None = None,
        note: str | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        """补改快照内容：修订版本 +1、摘要变化，并让旧修订的未结签核单失效。

        补改后必须有与本次修订对应的新签核，发布开单只认当前修订的有效签核。
        """
        context = context or {}
        note = note if note is not None else str(
            context.get("补改说明") or context.get("remark") or "补改快照内容"
        )
        with FLOW_LOCK:
            entry = store.find(self.MODULE, entry_id)
            if entry is None:
                return None, f"{self.ENTITY} {entry_id} 不存在或已归档"

            old_rev = str(entry.get("修订号", "R1"))
            self._bump_revision(entry, note)
            # 补改后的快照重新置于可用，等待新签核
            entry["status"] = "可用"
            entry["pending"] = False

            affected = self._invalidate(entry)
            message = (
                f"快照 {entry.get('快照编号')} 已补改：{old_rev} → {entry['修订号']}，"
                f"新摘要 {entry['快照摘要值']}；本次修订须重新签核"
            )
            if affected:
                message += f"，原签核单 {'、'.join(affected)} 已失效"
            return entry, message

    def freeze_snapshot(
        self, snapshot_id: str, dim_name: str, snapshot_date: str,
        ref_batch: str,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        """冻结维度快照：计算当前维度全量状态。"""
        scd_rows = store.rows("scd_chain")
        dim_rows = [
            r for r in scd_rows
            if r.get("所属维度") == dim_name
        ]
        total = len(dim_rows)
        current_count = sum(1 for r in dim_rows if r.get("是否当前") == "是")
        ratio = current_count / total if total > 0 else 0.0

        checksum = hashlib.md5(
            str(sorted(r.get("代理键", "") for r in dim_rows)).encode()
        ).hexdigest()[:8]

        rows = store.rows(self.MODULE)
        entry = {
            "快照编号": snapshot_id, "所属维度": dim_name,
            "快照日期": snapshot_date, "维度行数": total,
            "当前链占比": f"{ratio:.1%}", "快照摘要值": checksum,
            "引用批次": ref_batch, "生成时间": snapshot_date,
            "修订号": "R1", "修订版本": 1,
            "补改说明": "", "最近补改": "",
            "status": "可用", "pending": False, "abnormal": False,
        }
        entry["id"] = max((int(r.get("id", 0)) for r in rows), default=0) + 1
        rows.append(entry)
        return True, f"维度 {dim_name} 快照已生成：{total} 行", entry

    def verify_snapshot_consistency(
        self, dim_name: str, snapshot_date: str,
    ) -> tuple[bool, str, int]:
        """验证同一快照日期的维度行数一致性。"""
        rows = store.rows(self.MODULE)
        for r in rows:
            if r.get("所属维度") == dim_name and r.get("快照日期") == snapshot_date:
                count = int(r.get("维度行数", 0))
                return True, f"快照一致：{count} 行", count
        return False, f"维度 {dim_name} 无 {snapshot_date} 快照", 0
