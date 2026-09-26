import { useEffect, useState } from "react";
import { api } from "../api/client";
type P = { id: number; name: string; ferment_min: number; bake_min: number; is_active: boolean };
export default function ProductsPage() {
  const [rows, setRows] = useState<P[]>([]);
  const [err, setErr] = useState("");
  const reload = () => api<P[]>("/products").then(setRows);
  useEffect(() => { reload(); }, []);
  async function setActive(p: P, is_active: boolean) {
    setErr("");
    try {
      const updated = await api<P>(`/products/${p.id}/active`, {
        method: "POST", body: JSON.stringify({ is_active }),
      });
      setRows(rs => rs.map(r => r.id === updated.id ? updated : r));
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  }
  return (<>
    <h2>产品（配方时长）</h2>
    {err && <div className="err" style={{ marginBottom: ".75rem" }}>{err}</div>}
    <table className="table"><thead><tr><th>名称</th><th>发酵 min</th><th>烘烤 min</th><th>合计</th><th>状态</th><th></th></tr></thead>
    <tbody>{rows.map(p => <tr key={p.id} className={p.is_active ? "" : "row-off"}>
      <td>{p.name}{!p.is_active && <span className="off-tag">已停用</span>}</td>
      <td className="mono">{p.ferment_min}</td><td className="mono">{p.bake_min}</td>
      <td className="mono">{p.ferment_min + p.bake_min}</td>
      <td>{p.is_active ? "启用中" : "已停用"}</td>
      <td>{p.is_active
        ? <button className="btn-ghost" onClick={() => setActive(p, false)}>停用</button>
        : <button className="btn-ghost btn-ghost--on" onClick={() => setActive(p, true)}>重新启用</button>}
      </td>
    </tr>)}</tbody></table>
  </>);
}
