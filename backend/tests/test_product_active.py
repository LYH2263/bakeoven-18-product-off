from fastapi.testclient import TestClient


def _product_id(client: TestClient, name: str) -> int:
    rows = client.get("/api/products").json()
    return next(p["id"] for p in rows if p["name"] == name)


def _gantt_code(client: TestClient, code: str) -> list[dict]:
    return [b for b in client.get("/api/gantt").json() if b["code"] == code]


def test_product_active_flag_persists(client: TestClient):
    pid = _product_id(client, "黄油可颂")
    assert all(p["active"] for p in client.get("/api/products").json())

    r = client.patch(f"/api/products/{pid}", json={"active": False})
    assert r.status_code == 200
    assert r.json()["active"] is False

    # 离开再进来（重新 GET）状态还在
    assert client.get("/api/products").json()[1]["active"] is False

    r = client.patch(f"/api/products/{pid}", json={"active": True})
    assert r.status_code == 200
    assert r.json()["active"] is True


def test_disabled_product_batch_rejected_and_gantt_untouched(client: TestClient):
    pid = _product_id(client, "黄油可颂")
    ovens = client.get("/api/ovens").json()
    before = _gantt_code(client, "BO-1030")
    assert before  # 种子批次在甘特上

    client.patch(f"/api/products/{pid}", json={"active": False})

    # 指定已停用产品创建：拒绝，说明是“产品已停用”，不是时间重叠
    r = client.post(
        "/api/batches",
        json={"product_id": pid, "oven_id": ovens[2]["id"], "start_min": 12 * 60},
    )
    assert r.status_code == 409
    assert "产品已停用" in r.json()["detail"]
    assert "重叠" not in r.json()["detail"]

    # 没有写进冲突日志（不是时间冲突），也没有写进甘特
    conflicts = client.get("/api/conflicts").json()
    assert all("产品已停用" not in c["detail"] for c in conflicts)
    batches = client.get("/api/batches").json()
    assert sum(1 for b in batches if b["product_id"] == pid and b["code"] != "BO-1030") == 0

    # BO-1030 甘特端点不变（发酵止 10:55、烘烤止 11:15）
    after = _gantt_code(client, "BO-1030")
    assert after == before
    phases = {b["phase"]: b for b in after}
    assert phases["ferment"]["start_min"] == 630 and phases["ferment"]["end_min"] == 655
    assert phases["bake"]["start_min"] == 655 and phases["bake"]["end_min"] == 675


def test_windows_empty_while_disabled(client: TestClient):
    pid = _product_id(client, "黄油可颂")
    assert client.get("/api/windows", params={"product_id": pid}).json()

    client.patch(f"/api/products/{pid}", json={"active": False})
    assert client.get("/api/windows", params={"product_id": pid}).json() == []


def test_reenabled_product_can_schedule_on_empty_oven(client: TestClient):
    pid = _product_id(client, "黄油可颂")
    # 二层石板炉（ovens[2]）没有种子批次，是空炉
    empty_oven = client.get("/api/ovens").json()[2]

    client.patch(f"/api/products/{pid}", json={"active": False})
    r = client.post(
        "/api/batches",
        json={"product_id": pid, "oven_id": empty_oven["id"], "start_min": 12 * 60},
    )
    assert r.status_code == 409

    # 重新启用后，同一开工时间、空炉可以再排
    client.patch(f"/api/products/{pid}", json={"active": True})
    r = client.post(
        "/api/batches",
        json={"product_id": pid, "oven_id": empty_oven["id"], "start_min": 12 * 60},
    )
    assert r.status_code == 200
    b = r.json()
    assert b["product_id"] == pid
    assert b["ferment_end"] == 12 * 60 + 25
    assert b["bake_end"] == 12 * 60 + 45


def test_seed_batches_behave_normally_while_all_active(client: TestClient):
    # 未停用时，窗口照常返回炉，重叠仍按时间冲突处理
    pid = _product_id(client, "黄油可颂")
    assert client.get("/api/windows", params={"product_id": pid}).json()

    # BO-1030 占着一层 1 号炉 10:30 起，再排同炉同时段 → 时间重叠
    oven1 = client.get("/api/ovens").json()[0]
    r = client.post(
        "/api/batches",
        json={"product_id": pid, "oven_id": oven1["id"], "start_min": 10 * 60 + 40},
    )
    assert r.status_code == 409
    assert "重叠" in r.json()["detail"]
