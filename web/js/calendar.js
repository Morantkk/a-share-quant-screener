/* 财经日历页 */
const CalendarPage = {
  year: 0, month: 0, // 当前显示的年月（month: 0-11）
  events: [],

  init() {
    const now = new Date();
    this.year = now.getFullYear(); this.month = now.getMonth();
    document.getElementById("cal-prev").onclick = () => this.shift(-1);
    document.getElementById("cal-next").onclick = () => this.shift(1);
    document.getElementById("cal-today").onclick = () => {
      const n = new Date(); this.year = n.getFullYear(); this.month = n.getMonth(); this.load();
    };
    document.getElementById("cal-region").onchange = () => this.load();
    document.getElementById("cal-imp").onchange = () => this.load();
    document.getElementById("cal-refresh").onclick = async () => {
      const r = await API.post("/api/calendar/refresh");
      toast(r.msg || "已刷新");
      this.load();
    };
    document.getElementById("cal-add").onclick = () => {
      const f = document.getElementById("cal-add-form");
      f.style.display = f.style.display === "none" ? "" : "none";
      document.getElementById("cal-f-date").value = todayStr();
    };
    document.getElementById("cal-f-save").onclick = () => this.saveEvent();
    this.load();
  },

  shift(d) {
    this.month += d;
    if (this.month < 0) { this.month = 11; this.year--; }
    if (this.month > 11) { this.month = 0; this.year++; }
    this.load();
  },

  async load() {
    const start = new Date(this.year, this.month, 1);
    const end = new Date(this.year, this.month + 1, 0);
    const pad = n => String(n).padStart(2, "0");
    const s = `${start.getFullYear()}-${pad(start.getMonth() + 1)}-01`;
    const e = `${end.getFullYear()}-${pad(end.getMonth() + 1)}-${pad(end.getDate())}`;
    const region = document.getElementById("cal-region").value;
    const imp = document.getElementById("cal-imp").value;
    const r = await API.get(`/api/calendar?start=${s}&end=${e}&region=${region}&importance=${imp}`);
    this.events = r.results || [];
    document.getElementById("cal-range").textContent = `${this.year}年${this.month + 1}月`;
    this.renderGrid();
    this.renderList();
  },

  renderGrid() {
    const first = new Date(this.year, this.month, 1);
    const startWeek = first.getDay();
    const days = new Date(this.year, this.month + 1, 0).getDate();
    const today = todayStr();
    const byDate = {};
    this.events.forEach(e => { (byDate[e.date] = byDate[e.date] || []).push(e); });

    let html = ["日", "一", "二", "三", "四", "五", "六"].map(d => `<div class="cal-head">${d}</div>`).join("");
    for (let i = 0; i < startWeek; i++) html += `<div class="cal-cell other"></div>`;
    for (let d = 1; d <= days; d++) {
      const ds = `${this.year}-${String(this.month + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
      const evs = byDate[ds] || [];
      html += `<div class="cal-cell ${ds === today ? "today" : ""}">
        <div class="d">${d}</div>
        ${evs.slice(0, 3).map(e =>
          `<div class="cal-ev ${e.region} ${e.importance >= 3 ? "i3" : ""} ${e.source === "manual" ? "manual" : ""}"
            title="${esc(e.title)} ${e.time || ""}">${e.region === "US" ? "美" : "中"}·${esc(e.title).slice(0, 10)}</div>`).join("")}
        ${evs.length > 3 ? `<div class="muted small">还有${evs.length - 3}条…</div>` : ""}
      </div>`;
    }
    document.getElementById("cal-grid").innerHTML = html;
  },

  renderList() {
    const el = document.getElementById("cal-list");
    if (!this.events.length) { el.innerHTML = `<div class="empty">该月暂无日程，可点「刷新日历」生成，或手动添加事件</div>`; return; }
    document.getElementById("cal-list-meta").textContent = `（${this.events.length} 条）`;
    el.innerHTML = this.events.map(e => `
      <div class="cal-row">
        <div class="date">${e.date} ${e.time || ""}</div>
        <div style="flex:1">${e.region === "US" ? '<span class="tag oversea">海外</span>' : '<span class="tag macro">国内</span>'}
          ${stars(e.importance)} ${esc(e.title)}
          ${e.note ? `<span class="muted small">${esc(e.note)}</span>` : ""}</div>
        ${e.source === "manual" ? `<button class="btn small" onclick="CalendarPage.delEvent(${e.id})">删除</button>` : ""}
      </div>`).join("");
  },

  async saveEvent() {
    const b = {
      date: document.getElementById("cal-f-date").value,
      title: document.getElementById("cal-f-title").value.trim(),
      region: document.getElementById("cal-f-region").value,
      importance: parseInt(document.getElementById("cal-f-imp").value),
      time: document.getElementById("cal-f-time").value.trim(),
      note: "手动添加",
    };
    if (!b.date || !b.title) { toast("请填写日期和标题"); return; }
    await API.post("/api/calendar/event", b);
    toast("已添加");
    document.getElementById("cal-add-form").style.display = "none";
    this.load();
  },

  async delEvent(id) { await API.del("/api/calendar/event/" + id); this.load(); },
};
