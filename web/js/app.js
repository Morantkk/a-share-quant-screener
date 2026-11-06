/* 应用核心：登录、路由、热榜、自选池、数据管理 */
const App = {
  pages: ["hotlist", "screen", "pattern", "quote", "calendar", "watchlist", "manage"],
  inited: {},

  showLogin() {
    localStorage.removeItem("qs_token"); API.token = "";
    document.getElementById("login-mask").style.display = "flex";
  },

  async tryLogin() {
    const pw = document.getElementById("login-pw").value;
    const r = await fetch("/api/login", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: pw }),
    }).then(x => x.json()).catch(() => null);
    if (r && r.ok) {
      API.token = r.token; localStorage.setItem("qs_token", r.token);
      document.getElementById("login-mask").style.display = "none";
      this.boot();
    } else {
      document.getElementById("login-err").textContent = "密码错误";
    }
  },

  boot() {
    const hash = (location.hash || "#hotlist").slice(1);
    this.go(this.pages.includes(hash) ? hash : "hotlist");
    this.loadDataState();
  },

  go(page) {
    location.hash = page;
    this.pages.forEach(p => {
      document.getElementById("page-" + p).style.display = (p === page) ? "" : "none";
    });
    document.querySelectorAll("#nav a").forEach(a => a.classList.toggle("active", a.dataset.page === page));
    if (!this.inited[page]) {
      this.inited[page] = true;
      const init = { hotlist: Hotlist, screen: Screen, pattern: Pattern, quote: Quote, calendar: CalendarPage, watchlist: Watchlist, manage: Manage }[page];
      if (init && init.init) init.init();
    }
    const refresh = { hotlist: Hotlist, watchlist: Watchlist, manage: Manage }[page];
    if (refresh && refresh.load) refresh.load();
  },

  async loadDataState() {
    const r = await API.get("/api/fetch/status").catch(() => null);
    if (!r) return;
    const el = document.getElementById("hotlist-data-state");
    if (el) el.innerHTML = `行情覆盖 <b>${r.stock_count}</b> 只股票<br>最新数据日期 <b>${r.last_date || "无"}</b>`;
  },
};

window.addEventListener("hashchange", () => {
  const hash = location.hash.slice(1);
  if (App.pages.includes(hash)) App.go(hash);
});

document.getElementById("login-btn").onclick = () => App.tryLogin();
document.getElementById("login-pw").addEventListener("keydown", e => { if (e.key === "Enter") App.tryLogin(); });
document.getElementById("logout-btn").onclick = () => App.showLogin();
document.querySelectorAll("#nav a").forEach(a => a.onclick = e => { e.preventDefault(); App.go(a.dataset.page); });

/* ---------------- 热榜 ---------------- */
const Hotlist = {
  cats: ["全部", "宏观", "海外", "行业", "个股", "快讯"],

  init() {
    const sel = document.getElementById("hotlist-cat");
    sel.innerHTML = this.cats.map(c => `<option>${c}</option>`).join("");
    sel.onchange = () => this.load();
    document.getElementById("hotlist-refresh").onclick = async () => {
      toast("正在抓取多源快讯…", 3000);
      const r = await API.post("/api/news/refresh");
      toast(r.msg || "完成");
      this.load();
    };
    this.load();
    this.loadTodayEvents();
  },

  load() {
    const cat = document.getElementById("hotlist-cat").value;
    const day = todayStr();
    API.get(`/api/news/hotlist?day=${day}&category=${encodeURIComponent(cat)}`).then(r => {
      const el = document.getElementById("hotlist-list");
      if (!r.ok || !r.results.length) {
        el.innerHTML = `<div class="empty">暂无数据，点击右上角「抓取最新」</div>`;
        return;
      }
      document.getElementById("hotlist-meta").textContent = `共 ${r.results.length} 条`;
      el.innerHTML = r.results.map(n => `
        <div class="news-item">
          <div class="news-rank">${n.rank}</div>
          <div class="news-body">
            <div class="news-title">${esc(n.title)}</div>
            <div class="news-meta">
              <span class="tag ${catCls(n.category)}">${n.category}</span>
              <span>${srcName(n.source)}</span>
              <span>${(n.published_at || "").slice(5, 16)}</span>
              <span>热度 ${n.score}</span>
              ${n.related_code ? `<a class="link" href="#quote" onclick="Quote.open('${n.related_code}')">📈 ${esc(n.related_name || n.related_code)}</a>` : ""}
            </div>
          </div>
        </div>`).join("");
    });
  },

  async loadTodayEvents() {
    const day = todayStr();
    const r = await API.get(`/api/calendar?start=${day}&end=${day}`);
    const el = document.getElementById("hotlist-today-events");
    if (!r.ok || !r.results.length) { el.innerHTML = `<div class="muted small">今日暂无重要日程</div>`; return; }
    el.innerHTML = r.results.map(e => `
      <div class="cal-row" style="padding:6px 2px">
        <div style="flex:1">
          <div>${stars(e.importance)} ${e.region === "US" ? "🇺🇸" : "🇨🇳"} ${esc(e.title)}</div>
          ${e.note ? `<div class="muted small">${esc(e.note)}</div>` : ""}
        </div>
      </div>`).join("");
  },
};

function esc(s) { return String(s || "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
function stars(n) { return "★".repeat(Math.max(1, Math.min(3, n))) + "☆".repeat(3 - Math.max(1, Math.min(3, n))); }
function catCls(c) { return { 宏观: "macro", 海外: "oversea", 行业: "industry", 个股: "stock" }[c] || ""; }
function srcName(s) { return { em: "东方财富", sina: "新浪财经", ths: "同花顺", cls: "财联社", cjzc: "财经早餐" }[s] || s; }

/* ---------------- 自选池 ---------------- */
const Watchlist = {
  init() {},

  load() {
    API.get("/api/watchlist").then(r => {
      const el = document.getElementById("watchlist-wrap");
      if (!r.ok || !r.results.length) { el.innerHTML = `<div class="empty">自选池为空，可在「条件选股」「形态匹配」结果中添加</div>`; return; }
      el.innerHTML = `<table class="tbl"><thead><tr>
        <th>代码</th><th>名称</th><th>最新价</th><th>涨跌幅</th><th>换手率</th><th>数据日期</th><th>操作</th>
      </tr></thead><tbody>` +
        r.results.map(s => `<tr>
          <td><a class="link" onclick="Quote.open('${s.code}')">${s.code}</a></td>
          <td>${esc(s.name)}</td>
          <td>${fmt(s.close)}</td>
          <td>${pctHtml(s.pct_chg)}</td>
          <td>${fmt(s.turnover, "%")}</td>
          <td class="muted">${s.date || ""}</td>
          <td><button class="btn small" onclick="Watchlist.del('${s.code}')">移除</button></td>
        </tr>`).join("") + "</tbody></table>";
    });
  },

  async del(code) { await API.del("/api/watchlist/" + code); this.load(); },

  async add(code, name) {
    const r = await API.post("/api/watchlist", { code, name });
    if (r.ok) toast("已加入自选池");
  },
};

/* ---------------- 数据管理 ---------------- */
const Manage = {
  timer: null,

  init() {
    document.getElementById("fetch-inc").onclick = () => this.startFetch("incremental");
    document.getElementById("fetch-full").onclick = () => {
      if (!confirm("全量重抓将清空现有行情数据并重新抓取（约5-15分钟），确认？")) return;
      this.startFetch("full");
    };
    document.querySelectorAll(".job-btn").forEach(b => b.onclick = async () => {
      const r = await API.post("/api/jobs/" + b.dataset.job);
      toast(r.msg || "已启动");
    });
    this.load();
  },

  async startFetch(mode) {
    const r = await API.post("/api/fetch/start?mode=" + mode);
    toast(r.msg || "已启动", 2500);
    this.poll();
  },

  poll() {
    if (this.timer) clearInterval(this.timer);
    document.getElementById("fetch-progress").style.display = "";
    this.timer = setInterval(async () => {
      const r = await API.get("/api/fetch/status").catch(() => null);
      if (!r) return;
      const pct = r.total ? Math.round(r.done / r.total * 100) : 0;
      document.getElementById("fetch-bar").style.width = pct + "%";
      document.getElementById("fetch-msg").textContent =
        `${r.phase || ""} ${r.message || ""}` + (r.running ? "" : "（已结束）");
      if (!r.running) { clearInterval(this.timer); this.timer = null; this.load(); App.loadDataState(); }
    }, 2000);
  },

  load() {
    API.get("/api/system/stats").then(r => {
      document.getElementById("manage-stats").innerHTML = `
        <div class="stat"><div class="k">股票数量</div><div class="v">${r.stock_count}<small> 只</small></div></div>
        <div class="stat"><div class="k">日K记录</div><div class="v">${(r.daily_count / 10000).toFixed(1)}<small> 万条</small></div></div>
        <div class="stat"><div class="k">数据最新日期</div><div class="v" style="font-size:18px">${r.last_date || "无数据"}</div></div>
        <div class="stat"><div class="k">热榜最近抓取</div><div class="v" style="font-size:18px">${(r.news_last || "未抓取").slice(5, 16)}</div></div>`;
      document.getElementById("manage-jobs").innerHTML =
        `行情增量更新：每天 <b>${r.config.quotes_time}</b> ｜ 热榜抓取：每天 <b>${r.config.news_time}</b> ｜ 日历刷新：每天 <b>${r.config.calendar_time}</b>（均自动执行）`;
      if (r.fetch && r.fetch.running) this.poll();
    });
  },
};

/* 启动 */
(async function () {
  if (!API.token) { App.showLogin(); return; }
  const ping = await API.get("/api/system/stats").catch(() => null);
  if (ping && ping.ok) {
    document.getElementById("login-mask").style.display = "none";
    App.boot();
  } else {
    App.showLogin();
  }
})();
