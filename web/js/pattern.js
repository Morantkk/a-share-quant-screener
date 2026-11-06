/* 形态匹配页 */
const Pattern = {
  charts: {},
  // 模板来源：select=行情页框选；upload=截图
  template: null,   // {closes:[], vols:[], code, dates}

  init() {
    document.querySelectorAll("#pattern-tabs .tab").forEach(t => t.onclick = () => {
      document.querySelectorAll("#pattern-tabs .tab").forEach(x => x.classList.remove("active"));
      t.classList.add("active");
      document.getElementById("pattern-tab-select").style.display = t.dataset.tab === "select" ? "" : "none";
      document.getElementById("pattern-tab-upload").style.display = t.dataset.tab === "upload" ? "" : "none";
    });
    document.getElementById("pattern-file").onchange = () => this.upload();
    document.getElementById("pattern-run").onclick = () => this.run();
    this.refreshTemplate();
  },

  refreshTemplate() {
    const tpl = JSON.parse(localStorage.getItem("qs_template") || "null");
    this.template = tpl;
    const box = document.getElementById("pattern-template-preview");
    if (!tpl) {
      box.innerHTML = `<div class="empty">当前没有模板。到「行情」页框选一段K线后自动带入。</div>`;
      return;
    }
    box.innerHTML = `
      <p class="small">已带入模板：${tpl.code}（${tpl.dates[0]} ~ ${tpl.dates[tpl.dates.length - 1]}，共 ${tpl.closes.length} 根）</p>
      <div id="tpl-chart" class="chart-sm"></div>
      <button class="btn small" onclick="localStorage.removeItem('qs_template');Pattern.refreshTemplate()">清除模板</button>`;
    const chart = echarts.init(document.getElementById("tpl-chart"));
    this.charts.tpl = chart;
    const x = tpl.dates.map((d, i) => i + 1);
    chart.setOption({
      grid: { left: 40, right: 10, top: 10, bottom: 20 },
      xAxis: { type: "category", data: x, axisLabel: { show: false } },
      yAxis: { type: "value", scale: true, splitLine: { lineStyle: { color: "#f0f2f5" } } },
      series: [{ type: "line", data: tpl.closes, symbol: "none", lineStyle: { color: "#185fa5", width: 2 }, areaStyle: { color: "rgba(24,95,165,.08)" } }],
    });
  },

  async upload() {
    const f = document.getElementById("pattern-file").files[0];
    if (!f) return;
    const box = document.getElementById("pattern-upload-preview");
    box.innerHTML = `<p class="muted small">识别中…</p>`;
    const r = await API.upload("/api/pattern/upload", f);
    if (!r.ok) { box.innerHTML = `<p class="small" style="color:var(--red)">${r.msg}</p>`; return; }
    this.template = { closes: r.series, vols: null, code: "", dates: r.series.map((_, i) => i + 1) };
    this.fromUpload = true;
    box.innerHTML = `
      <p class="small">${r.note}（识别 ${r.count} 根）</p>
      <div id="up-chart" class="chart-sm"></div>
      <button class="btn primary small" onclick="Pattern.run()">用此走势匹配</button>`;
    const chart = echarts.init(document.getElementById("up-chart"));
    chart.setOption({
      grid: { left: 40, right: 10, top: 10, bottom: 20 },
      xAxis: { type: "category", data: r.series.map((_, i) => i + 1), axisLabel: { show: false } },
      yAxis: { type: "value", splitLine: { lineStyle: { color: "#f0f2f5" } } },
      series: [{ type: "line", data: r.series, symbol: "none", lineStyle: { color: "#534AB7", width: 2 } }],
    });
  },

  async run() {
    if (!this.template) { toast("请先提供模板"); return; }
    const btn = document.getElementById("pattern-run");
    btn.disabled = true;
    document.getElementById("pattern-status").textContent = "正在全市场匹配…";
    const r = await API.post("/api/pattern/match", {
      template_close: this.template.closes,
      template_vol: this.template.vols || null,
      match_volume: document.getElementById("pattern-vol").checked && !!this.template.vols,
      top: parseInt(document.getElementById("pattern-top").value) || 30,
      scan_windows: document.getElementById("pattern-scope").value === "any",
      exclude_code: this.template.code || "",
      exclude_st: document.getElementById("pattern-exst").checked,
    });
    btn.disabled = false;
    document.getElementById("pattern-status").textContent = r.ok ? `完成，命中 ${r.total} 只` : (r.msg || "失败");
    this.renderResults(r);
  },

  renderResults(r) {
    const box = document.getElementById("pattern-result");
    Object.values(this.charts).forEach(c => c && c.dispose && c.dispose());
    this.charts = {};
    if (!r.ok) { box.innerHTML = `<div class="card"><div class="empty">${r.msg || "无结果"}</div></div>`; return; }
    box.innerHTML = (r.results || []).map(h => `
      <div class="card match-item">
        <div class="match-info">
          <div class="big">#${h.rank} <a class="link" onclick="Quote.open('${h.code}')">${h.code}</a> ${esc(h.name)}</div>
          <div class="muted small">${h.seg_start} ~ ${h.seg_end} ${h.is_recent ? "｜<b style='color:#0f8a4d'>最近走势</b>" : "｜历史段"}</div>
          <div class="score-bar"><div style="width:${h.score}%"></div></div>
          <div class="small">相似度 <b>${h.score}%</b> ｜ 现价 ${fmt(h.last_close)} ${pctHtml(h.last_pct)}</div>
          <div style="margin-top:8px">
            <button class="btn small" onclick="Quote.open('${h.code}')">查看K线</button>
            <button class="btn small" onclick="Watchlist.add('${h.code}', '${esc(h.name)}')">+自选</button>
          </div>
        </div>
        <div id="mchart-${h.code}" class="chart-sm" style="height:140px"></div>
      </div>`).join("");
    // 归一化对比小图：模板（蓝） vs 匹配段（橙）
    const tpl = this.template.closes;
    const norm = a => { const mn = Math.min(...a), mx = Math.max(...a); return a.map(v => (v - mn) / (mx - mn || 1) * 100); };
    r.results.forEach(h => {
      const el = document.getElementById("mchart-" + h.code);
      if (!el) return;
      const c = echarts.init(el);
      this.charts[h.code] = c;
      c.setOption({
        grid: { left: 40, right: 10, top: 8, bottom: 18 },
        xAxis: { type: "category", data: tpl.map((_, i) => i + 1), axisLabel: { show: false } },
        yAxis: { type: "value", splitLine: { lineStyle: { color: "#f0f2f5" } }, axisLabel: { show: false } },
        series: [
          { type: "line", data: norm(tpl), symbol: "none", lineStyle: { color: "#185fa5", width: 2 } },
          { type: "line", data: norm(h.seg_close), symbol: "none", lineStyle: { color: "#ef9f27", width: 2, type: "dashed" } },
        ],
      });
    });
  },
};
