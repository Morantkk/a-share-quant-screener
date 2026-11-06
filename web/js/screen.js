/* 条件选股页 */
const Screen = {
  types: [],
  conditions: [],
  logic: "and",
  charts: {},

  async init() {
    const r = await API.get("/api/screen/types");
    this.types = r.types || [];
    document.getElementById("cond-chips").innerHTML =
      this.types.map(t => `<span class="chip" data-type="${t.type}">${t.label}</span>`).join("");
    document.querySelectorAll("#cond-chips .chip").forEach(c => c.onclick = () => this.add(c.dataset.type));

    document.getElementById("logic-toggle").onclick = () => {
      this.logic = this.logic === "and" ? "or" : "and";
      document.getElementById("logic-toggle").textContent =
        this.logic === "and" ? "且（全部满足）" : "或（满足其一）";
      this.renderConnectors();
    };
    document.getElementById("screen-run").onclick = () => this.run();
    document.getElementById("strategy-save").onclick = () => this.saveStrategy();
    document.getElementById("strategy-del").onclick = () => this.delStrategy();
    document.getElementById("strategy-select").onchange = () => this.loadStrategy();
    this.loadStrategies();
    this.render();
  },

  add(type) {
    const t = this.types.find(x => x.type === type);
    if (!t) return;
    const params = {};
    t.params.forEach(p => params[p.key] = p.default);
    this.conditions.push({ type, params, desc: "" });
    this.render();
  },

  remove(i) { this.conditions.splice(i, 1); this.render(); },

  render() {
    const list = document.getElementById("cond-list");
    document.getElementById("cond-count").textContent = this.conditions.length ? `（${this.conditions.length} 个）` : "";
    if (!this.conditions.length) {
      list.innerHTML = `<div class="muted small">尚未添加条件。点击上方指标库中的积木块开始组合，例如：MA(5)上穿MA(20) + 量比>2 + 换手率5%~10%。</div>`;
      return;
    }
    list.innerHTML = this.conditions.map((c, i) => {
      const t = this.types.find(x => x.type === c.type);
      const params = t.params.map(p => this.renderParam(c, p)).join("");
      return `<div class="cond-item">
        <div class="cond-title"><span>${t.label}</span>
          <button class="btn ghost small" onclick="Screen.remove(${i})">删除</button></div>
        <div class="cond-params">${params}</div>
      </div>
      <div class="cond-connector" ${i === this.conditions.length - 1 ? 'style="display:none"' : ""}>
        <button onclick="Screen.toggleLogic()">${this.logic === "and" ? "且" : "或"}</button>
      </div>`;
    }).join("");
  },

  renderConnectors() { this.render(); },

  toggleLogic() { document.getElementById("logic-toggle").click(); },

  renderParam(c, p) {
    const v = c.params[p.key];
    if (p.type === "select") {
      const opts = p.options.map(o => {
        const [val, label] = o.split(":");
        return `<option value="${val}" ${String(v) === val ? "selected" : ""}>${label || val}</option>`;
      }).join("");
      return `<span class="p">${p.label} <select onchange="Screen.setParam('${c.type}', '${p.key}', this.value)">${opts}</select></span>`;
    }
    return `<span class="p">${p.label} <input type="number" step="any" value="${v === null || v === undefined ? "" : v}"
      placeholder="不限" onchange="Screen.setParamNum('${c.type}', '${p.key}', this.value)"></span>`;
  },

  setParam(type, key, val) {
    // 同类型条件共享参数（v1 简化：同类型只加一个）
    this.conditions.filter(c => c.type === type).forEach(c => c.params[key] = val);
    this.render();
  },

  setParamNum(type, key, val) {
    const v = val === "" ? null : parseFloat(val);
    this.conditions.filter(c => c.type === type).forEach(c => c.params[key] = v);
  },

  async run() {
    if (!this.conditions.length) { toast("请先添加条件"); return; }
    const btn = document.getElementById("screen-run");
    btn.disabled = true; btn.textContent = "筛选中…";
    const body = {
      conditions: this.conditions.map(c => ({ type: c.type, params: c.params })),
      logic: this.logic,
      exclude_st: document.getElementById("exclude-st").checked,
      limit: 200,
    };
    const r = await API.post("/api/screen", body);
    btn.disabled = false; btn.textContent = "开始筛选";
    const box = document.getElementById("screen-result");
    box.style.display = "";
    if (!r.ok) { document.getElementById("screen-table").innerHTML = `<div class="empty">${r.msg}</div>`; return; }
    document.getElementById("screen-result-meta").textContent =
      `命中 ${r.total} 只${r.total > 200 ? "（仅显示前200）" : ""}`;
    document.getElementById("screen-table").innerHTML =
      `<table class="tbl"><thead><tr>
        <th>代码</th><th>名称</th><th>最新价</th><th>涨跌幅</th><th>换手率</th><th>量比</th><th>数据日期</th><th></th>
      </tr></thead><tbody>` +
      (r.results || []).map(s => `<tr>
        <td><a class="link" onclick="Quote.open('${s.code}')">${s.code}</a></td>
        <td>${esc(s.name)}</td>
        <td>${fmt(s.close)}</td>
        <td>${pctHtml(s.pct_chg)}</td>
        <td>${fmt(s.turnover, "%")}</td>
        <td>${fmt(s.volume_ratio)}</td>
        <td class="muted">${s.date}</td>
        <td><button class="btn small" onclick="Watchlist.add('${s.code}', '${esc(s.name)}')">+自选</button></td>
      </tr>`).join("") + "</tbody></table>";
  },

  async saveStrategy() {
    const name = document.getElementById("strategy-name").value.trim();
    if (!name) { toast("请填写策略名称"); return; }
    if (!this.conditions.length) { toast("没有可保存的条件"); return; }
    await API.post("/api/strategies", {
      name, logic: this.logic,
      conditions: this.conditions.map(c => ({ type: c.type, params: c.params })),
    });
    toast("策略已保存");
    this.loadStrategies();
  },

  async loadStrategies() {
    const r = await API.get("/api/strategies");
    const sel = document.getElementById("strategy-select");
    const cur = sel.value;
    sel.innerHTML = `<option value="">载入已存策略…</option>` +
      (r.results || []).map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join("");
    if (cur) sel.value = cur;
  },

  loadStrategy() {
    const id = document.getElementById("strategy-select").value;
    if (!id) return;
    API.get("/api/strategies").then(r => {
      const s = (r.results || []).find(x => String(x.id) === id);
      if (!s) return;
      this.conditions = s.conditions.map(c => ({ type: c.type, params: c.params }));
      this.logic = s.logic || "and";
      document.getElementById("logic-toggle").textContent =
        this.logic === "and" ? "且（全部满足）" : "或（满足其一）";
      document.getElementById("strategy-name").value = s.name;
      this.render();
      toast("已载入策略：" + s.name);
    });
  },

  async delStrategy() {
    const id = document.getElementById("strategy-select").value;
    if (!id) { toast("请先选择要删除的策略"); return; }
    if (!confirm("确认删除该策略？")) return;
    await API.del("/api/strategies/" + id);
    toast("已删除");
    this.loadStrategies();
  },
};
