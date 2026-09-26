"""停用/启用产品的端到端行为：拒绝建批、甘特保留、窗口为空、恢复后可再排。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import ConflictLog
from app.services.seed import seed_if_empty


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSession()
    seed_if_empty(db)
    db.close()

    def override_get_db():
        s = TestingSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    # 不用 with：避免触发连 Postgres 的 lifespan；表与种子已在 sqlite 中备好。
    yield TestClient(app)
    app.dependency_overrides.clear()


def _product(client, name):
    rows = client.get("/api/products").json()
    return next(p for p in rows if p["name"] == name)


def test_deactivate_blocks_create_with_reason_and_no_conflict_log(client):
    croissant = _product(client, "黄油可颂")
    assert croissant["is_active"] is True

    r = client.post(
        f"/api/products/{croissant['id']}/active", json={"is_active": False}
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is False

    # 停用后即使炉位空闲也拒绝，理由是“产品已停用”，而不是时间重叠。
    r = client.post(
        "/api/batches",
        json={"product_id": croissant["id"], "oven_id": 3, "start_min": 12 * 60},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "产品已停用"

    # 拒绝不写冲突日志（种子里原本只有一条 BO-试排）。
    db = next(app.dependency_overrides[get_db]())
    try:
        codes = [c.batch_code for c in db.scalars(select(ConflictLog)).all()]
    finally:
        db.close()
    assert codes == ["BO-试排"]


def test_gantt_keeps_scheduled_batch_while_inactive(client):
    croissant = _product(client, "黄油可颂")
    before = [b for b in client.get("/api/gantt").json() if b["code"] == "BO-1030"]
    assert [(b["phase"], b["start_min"], b["end_min"]) for b in before] == [
        ("ferment", 10 * 60 + 30, 10 * 60 + 30 + 25),
        ("bake", 10 * 60 + 30 + 25, 10 * 60 + 30 + 25 + 20),
    ]

    client.post(f"/api/products/{croissant['id']}/active", json={"is_active": False})

    after = [b for b in client.get("/api/gantt").json() if b["code"] == "BO-1030"]
    assert after == before  # 甘特端点不变：发酵止、烘烤止都不动


def test_windows_empty_while_inactive(client):
    croissant = _product(client, "黄油可颂")
    active = client.get(f"/api/windows?product_id={croissant['id']}").json()
    assert active  # 未停用时窗口正常返回

    client.post(f"/api/products/{croissant['id']}/active", json={"is_active": False})
    assert client.get(f"/api/windows?product_id={croissant['id']}").json() == []


def test_reactivate_allows_new_batch_on_free_oven(client):
    croissant = _product(client, "黄油可颂")
    client.post(f"/api/products/{croissant['id']}/active", json={"is_active": False})
    client.post(f"/api/products/{croissant['id']}/active", json={"is_active": True})

    # 重新启用后，同一开工时刻在空炉（3 号石板炉种子无批次）上可以再排。
    r = client.post(
        "/api/batches",
        json={"product_id": croissant["id"], "oven_id": 3, "start_min": 10 * 60 + 30},
    )
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["status"] == "scheduled"
    # 发酵止 655、烘烤止 675，与 BO-1030 一致。
    assert b["ferment_end"] == 10 * 60 + 30 + 25
    assert b["bake_end"] == 10 * 60 + 30 + 25 + 20
