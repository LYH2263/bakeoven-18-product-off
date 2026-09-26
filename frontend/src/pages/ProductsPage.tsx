import { useEffect, useState } from "react";
import { api } from "../api/client";
type P = { id: number; name: string; ferment_min: number; bake_min: number; active: boolean };
export default function ProductsPage() {
  const [rows, setRows] = useState<P[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [err, setErr] = useState("");
  const reload = () => api<P[]>("/products").then(setRows);
  useEffect(() => { reload(); }, []);
  async function toggle(p: P) {
    setErr(""); setBusyId(p.id);
    try {
      await api<P>(`/products/${p.id}`, { method: "PATCH", body: JSON.stringify({ active: !p.active }) });
      await reload();
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setBusyId(null); }
  }
  return (<>
    <h2>产品（配方时长）</h2>
    {err && <div className="err">{err}</div>}
    <table className="table"><thead><tr><th>名称</th><th>发酵 min</th><th>烘烤 min</th><th>合计</th><th>状态</th><th></th></tr></thead>
    <tbody>{rows.map(p => <tr key={p.id}><td>{p.name}</td><td className="mono">{p.ferment_min}</td><td className="mono">{p.bake_min}</td><td className="mono">{p.ferment_min + p.bake_min}</td>
      <td>{p.active ? "启用中" : <span className="muted">已停用</span>}</td>
      <td><button disabled={busyId === p.id} onClick={() => toggle(p)}>{p.active ? "停用" : "重新启用"}</button></td></tr>)}</tbody></table>
  </>);
}
