"""维度发布领域服务：版本化发布维度快照数据集给下游，校验导出版本不得静默替换。

新增“凭有效快照签核单创建发布申请”：开单与签核撤回共用 FLOW_LOCK，
校验签核单当前仍有效后才写入实际发布申请，并把签核单置为「已使用」。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.base import BaseModuleService
from app.store import FLOW_LOCK, store


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


class DimPublishService(BaseModuleService):
    MODULE = "dim_publish"
    ENTITY = "发布版本"
    LIST_FIELDS = ["发布编号", "所属维度", "发布版本", "快照日期", "可见范围", "下游引用数", "发布标签", "发布时间", "申请说明", "发布申请人", "签核单编号", "签核修订号", "申请时间"]
    REQUIRED_FIELDS = ["发布编号", "所属维度", "发布版本"]
    STATUS_ORDER = ["待发布", "发布中", "已发布", "已撤回"]
    ACTION_RULES = {"启动发布": "发布中", "确认发布": "已发布", "撤回发布": "已撤回"}
    NEGATIVE_ACTIONS = []

    def create_entry(
        self,
        values: dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, list[str]]:
        # 只要带了签核单引用，就必须走签核校验开单，不能绕过双人签核
        signoff_ref = (
            values.get("signoff_id") or values.get("签核单编号")
            or values.get("signoff_no")
        )
        if signoff_ref not in (None, ""):
            ok, message, entry, status_code = self.create_application(
                values, context=context,
            )
            if ok and entry is not None:
                return entry, []
            # 业务拒绝：用一个特殊错误片段返回，路由层识别后原样展示
            return None, [f"__business__:{message}"]

        # 无签核引用的普通登记沿用通用骨架
        return super().create_entry(values, context=context)

    def create_application(
        self,
        payload: dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
    ) -> tuple[bool, str, dict[str, Any] | None, int]:
        """凭有效签核单创建维度发布申请（实际写入 dim_publish）。

        返回 (ok, message, entry, http_status)。并发撤回时 http_status=409。
        """
        context = context or {}
        operator = str(
            payload.get("发布人") or payload.get("发布申请人")
            or payload.get("operator") or context.get("operator") or ""
        ).strip()
        signoff_ref = (
            payload.get("signoff_id") or payload.get("签核单编号")
            or payload.get("signoff_no") or payload.get("signoffId")
        )
        description = str(
            payload.get("申请说明") or payload.get("说明")
            or payload.get("description") or payload.get("remark") or ""
        ).strip()

        # 延迟导入避免循环依赖
        from app.services.snapshot_signoff import SnapshotSignoffService
        signoff_service = SnapshotSignoffService()

        # 全程持锁：与撤回互斥，保证“校验有效 → 写申请 → 占用签核单”原子完成
        with FLOW_LOCK:
            signoff = signoff_service.resolve(signoff_ref)
            if signoff is None:
                return False, "开单失败：未找到对应的快照签核单，请先取得有效签核", None, 404

            usable, code, reason = signoff_service.usability(signoff)
            if not usable:
                status_code = 409 if code in ("withdrawn", "used", "revision_stale", "stale") else 422
                return False, f"开单被拒绝：{reason}", None, status_code

            # 双保险：同一签核单至多写入一笔发布申请
            signoff_no = str(signoff.get("签核单编号", ""))
            for pub in store.rows(self.MODULE):
                if str(pub.get("签核单编号", "")) == signoff_no:
                    return False, (
                        f"开单冲突：签核单 {signoff_no} 已存在发布申请 "
                        f"{pub.get('发布编号')}，不能重复开单"
                    ), pub, 409

            rows = store.rows(self.MODULE)
            next_id = max((int(r.get("id", 0)) for r in rows), default=0) + 1
            dim_name = str(
                payload.get("所属维度") or signoff.get("所属维度") or ""
            ).strip()
            version = str(payload.get("发布版本") or "").strip() or (
                f"v{datetime.now():%Y%m%d}-{signoff.get('修订号', 'R1')}"
            )
            publish_no = str(
                payload.get("发布编号") or payload.get("publish_no") or ""
            ).strip() or f"PUB-APP-{next_id:03d}"

            # 同维度同版本已有正式发布时不得静默替换
            for r in rows:
                if r.get("所属维度") == dim_name and r.get("发布版本") == version \
                        and r.get("status") == "已发布":
                    return False, (
                        f"维度 {dim_name} 版本 {version} 已有发布记录，不得静默替换；"
                        "请更换发布版本号"
                    ), None, 409

            entry: dict[str, Any] = {
                "id": next_id,
                "status": "待发布",
                "pending": True,
                "abnormal": False,
                "发布编号": publish_no,
                "所属维度": dim_name,
                "发布版本": version,
                "快照日期": str(
                    payload.get("快照日期") or signoff.get("快照日期") or ""
                ),
                "可见范围": str(payload.get("可见范围") or "内部").strip(),
                "下游引用数": "0",
                "发布标签": str(payload.get("发布标签") or "申请待发布").strip(),
                "发布时间": "",
                "申请说明": description,
                "发布申请人": operator,
                "申请时间": now_text(),
                "签核单编号": signoff_no,
                "签核修订号": str(signoff.get("修订号", "")),
            }
            rows.append(entry)

            # 占用签核单：并发撤回在锁外等待，拿到锁后会看到「已使用」而失败
            signoff["status"] = "已使用"
            signoff["pending"] = False
            signoff["发布申请编号"] = publish_no
            signoff["version"] = int(signoff.get("version", 1)) + 1
            signoff_service.annotate(signoff)

            return True, (
                f"发布申请 {publish_no} 已创建并写入维度发布（状态：待发布），"
                f"凭签核单 {signoff_no}（修订 {signoff.get('修订号')}）开单成功，"
                "该签核单已标记为已使用"
            ), entry, 200

    def publish_version(
        self, publish_id: str, dim_name: str, version: str,
        snapshot_date: str, visible_scope: str, label: str,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        """发布维度版本：绑定快照日期与可见范围。"""
        rows = store.rows(self.MODULE)
        for r in rows:
            if r.get("所属维度") == dim_name and r.get("发布版本") == version \
                    and r.get("status") == "已发布":
                return False, (
                    f"维度 {dim_name} 版本 {version} 已有发布记录，不得静默替换"
                ), None

        entry = {
            "发布编号": publish_id, "所属维度": dim_name,
            "发布版本": version, "快照日期": snapshot_date,
            "可见范围": visible_scope, "下游引用数": "0",
            "发布标签": label, "发布时间": "2026-11-21",
            "status": "已发布", "pending": False, "abnormal": False,
        }
        entry["id"] = max((int(r.get("id", 0)) for r in rows), default=0) + 1
        rows.append(entry)
        return True, f"维度 {dim_name} 版本 {version} 已发布", entry

    def withdraw_publish(self, publish_id: str) -> tuple[bool, str]:
        """撤回发布：更新已撤回状态。"""
        rows = store.rows(self.MODULE)
        for r in rows:
            if r.get("发布编号") == publish_id:
                if r.get("status") == "已撤回":
                    return False, f"发布 {publish_id} 已撤回"
                r["status"] = "已撤回"
                r["pending"] = False
                return True, f"发布 {publish_id} 已撤回"
        return False, f"发布 {publish_id} 不存在"

    def count_downstream_refs(self, dim_name: str) -> int:
        """统计下游引用数。"""
        rows = store.rows(self.MODULE)
        return sum(1 for r in rows if r.get("所属维度") == dim_name and r.get("status") == "已发布")
