/* API 封装 */
const API = {
  token: localStorage.getItem("qs_token") || "",

  async call(method, url, body, isForm) {
    const opt = { method, headers: { "Authorization": "Bearer " + this.token } };
    if (body && !isForm) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
    if (body && isForm) opt.body = body;
    const r = await fetch(url, opt);
    if (r.status === 401) { App.showLogin(); throw new Error("未登录"); }
    return r.json();
  },
  get(url) { return this.call("GET", url); },
  post(url, body) { return this.call("POST", url, body); },
  del(url) { return this.call("DELETE", url); },
  upload(url, file) {
    const fd = new FormData(); fd.append("file", file);
    return this.call("POST", url, fd, true);
  },
};

function todayStr() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function toast(msg, ms) {
  let t = document.createElement("div");
  t.className = "toast"; t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), ms || 2200);
}

function fmt(v, suffix, digits) {
  if (v === null || v === undefined || v !== v) return "—";
  return Number(v).toFixed(digits === undefined ? 2 : digits) + (suffix || "");
}

function pctHtml(v) {
  if (v === null || v === undefined || v !== v) return "<span>—</span>";
  const cls = v > 0 ? "up" : (v < 0 ? "down" : "");
  const s = v > 0 ? "+" : "";
  return `<span class="${cls}">${s}${Number(v).toFixed(2)}%</span>`;
}
