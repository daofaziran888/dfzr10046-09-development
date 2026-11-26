"""快照签核 ↔ 维度发布跨模块流程测试：双人规则、修订绑定、并发互斥。"""
from __future__ import annotations

import concurrent.futures

import pytest

from app.store import store
from app.services.snapshot_signoff import SnapshotSignoffService
from app.services.dim_publish import DimPublishService
from app.services.dim_snapshot import DimSnapshotService


@pytest.fixture(autouse=True)
def fresh_store():
    store.reset()
    yield
    store.reset()


@pytest.fixture()
def signoff():
    return SnapshotSignoffService()


@pytest.fixture()
def publish():
    return DimPublishService()


def _submit(signoff, maker="张三", snapshot_id=1):
    ok, msg, row = signoff.submit_signoff(
        {"snapshot_id": snapshot_id, "制单人": maker},
    )
    assert ok, msg
    return row


class TestTwoPersonRule:
    def test_same_person_rejected(self, signoff):
        row = _submit(signoff, "alice")
        ok, msg, updated = signoff.confirm_signoff(row["id"], signer="alice")
        assert not ok
        assert "同一人" in msg and "拒绝受理" in msg
        assert updated["status"] == "待签核"

    def test_other_operator_approves(self, signoff):
        row = _submit(signoff, "alice")
        ok, msg, updated = signoff.confirm_signoff(
            row["id"], signer="bob", opinion="ok",
        )
        assert ok
        assert updated["status"] == "已签核"
        assert updated["签核人"] == "bob"
        usable, code, _ = signoff.usability(updated)
        assert usable and code == "usable"

    def test_confirm_requires_signer(self, signoff):
        row = _submit(signoff)
        ok, msg, _ = signoff.confirm_signoff(row["id"], signer="  ")
        assert not ok and "签核人" in msg

    def test_seed_signoff_is_usable(self, signoff):
        row = store.find("snapshot_signoff", 1)
        usable, code, _ = signoff.usability(row)
        assert row["status"] == "已签核"
        assert usable and code == "usable"


class TestRevisionBinding:
    def test_amendment_invalidates_old_signoff(self, signoff):
        seed = store.find("snapshot_signoff", 1)
        assert signoff.usability(seed)[0]
        entry, msg = DimSnapshotService().amend_snapshot(1)
        assert entry["修订号"] == "R2" and "R2" in msg
        refreshed = store.find("snapshot_signoff", 1)
        assert refreshed["status"] == "已失效"
        assert not signoff.usability(refreshed)[0]

    def test_new_signoff_required_for_new_revision(self, signoff):
        DimSnapshotService().amend_snapshot(1)
        row = _submit(signoff, "maker-2")
        assert row["修订号"] == "R2"
        ok, _, approved = signoff.confirm_signoff(row["id"], signer="signer-2")
        assert ok and approved["usable"]

    def test_cannot_confirm_stale_revision(self, signoff):
        row = _submit(signoff, "maker-3")  # binds R1
        DimSnapshotService().amend_snapshot(1)      # snapshot -> R2，制单被连带失效
        ok, msg, updated = signoff.confirm_signoff(row["id"], signer="signer-3")
        assert not ok
        assert "修订" in msg or "失效" in msg
        assert updated["status"] == "已失效"


class TestPublishWithValidSignoff:
    def test_apply_writes_application_and_consumes_signoff(self, signoff, publish):
        seed = store.find("snapshot_signoff", 1)
        ok, msg, pub, code = publish.create_application(
            {"signoff_id": seed["id"], "申请说明": "说明", "发布人": "wang"},
        )
        assert ok and code == 200 and pub["status"] == "待发布"
        assert pub["签核单编号"] == seed["签核单编号"]
        assert pub["申请说明"] == "说明"
        so = store.find("snapshot_signoff", 1)
        assert so["status"] == "已使用" and so["发布申请编号"] == pub["发布编号"]

    def test_cannot_apply_with_withdrawn_signoff(self, signoff, publish):
        signoff.withdraw_signoff(1, operator="lisi", reason="x")
        ok, msg, pub, code = publish.create_application({"signoff_id": 1})
        assert not ok and code == 409 and pub is None
        assert "撤回" in msg

    def test_cannot_apply_twice(self, publish):
        ok, _, first, _ = publish.create_application({"signoff_id": 1})
        assert ok
        ok2, msg, second, code = publish.create_application({"signoff_id": 1})
        assert not ok2 and code == 409 and second is None
        assert "已用于" in msg or "已存在发布申请" in msg or "已使用" in msg
        # 只有第一次写入了一笔申请
        pubs = [p for p in store.rows("dim_publish") if p.get("签核单编号")]
        assert len(pubs) == 1 and pubs[0]["id"] == first["id"]


class TestParallelRace:
    def test_publish_vs_withdraw_exactly_one_wins(self, signoff, publish):
        def attempt(_round):
            store.reset()

            def do_publish():
                return publish.create_application(
                    {"signoff_id": 1, "申请说明": "race"},
                )[0]

            def do_withdraw():
                return signoff.withdraw_signoff(1, operator="lisi")[0]

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                fp = pool.submit(do_publish)
                fw = pool.submit(do_withdraw)
                pub_ok, wd_ok = fp.result(), fw.result()

            assert int(bool(pub_ok)) + int(bool(wd_ok)) == 1
            so = store.find("snapshot_signoff", 1)
            if pub_ok:
                assert so["status"] == "已使用"
            else:
                assert so["status"] == "已撤回"
            pubs = [p for p in store.rows("dim_publish") if int(p["id"]) > 2]
            assert len(pubs) == (1 if pub_ok else 0)

        for i in range(10):
            attempt(i)
