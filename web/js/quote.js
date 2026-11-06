/* 个股行情页：K线图 + 鼠标框选 */
const Quote = {
  chart: null,
  bars: [],
  code: "",
  selRange: null,

  init() {
    const input = document.getElementById("quote-search");
    input.oninput = () => this.suggest(input.value);
    input.onblur = () => setTimeout(() => document.getElementById("quote-suggest").style.display = "none", 200);
    document.getElementById("quote-brush-match").onclick = () => this.useSelection();
    this.chart = echarts.init(document.getElementById("quote-chart"));
    window.addEventListener("resize", () => this.chart && this.chart.resize());
  },

  async suggest(q) {
    q = (q || "").trim();
    const box = document.getElementById("quote-suggest");
    if (!q) { box.style.display = "none"; return; }
    const r = await API.get("/api/search?q=" + encodeURIComponent(q));
    if (!r.ok || !r.results.length) { box.style.display = "none"; return; }
    box.innerHTML = r.results.map(s =>
      `<div onclick="Quote.open('${s.code}')"><b>${s.code}</b> ${esc(s.name)} ${s.is_st ? '<span class="tag">ST</span>' : ""}</div>`).join("");
    box.style.display = "";
  },

  async open(code) {
    this.code = code;
    location.hash = "quote";
    App.go("quote");
    document.getElementById("quote-search").value = code;
    const r = await API.get(`/api/kline?code=${code}&days=130`);
    if (!r.ok || !r.bars || !r.bars.length) {
      document.getElementById("quote-title").textContent = code + "（暂无数据，请先在「数据管理」抓取行情）";
      return;
    }
    this.bars = r.bars;
    document.getElementById("quote-title").textContent =
      `${r.stock.name}（${code}）  最新 ${fmt(r.bars[r.bars.length - 1].close)} ${pctHtml(r.bars[r.bars.length - 1].pct_chg)}`;
    this.render();
  },

  render() {
    const bars = this.bars;
    const closes = bars.map(b => b.close);
    const ma = n => closes.map((_, i) => i < n - 1 ? null :
      (closes.slice(i - n + 1, i + 1).reduce((a, b) => a + b, 0) / n));
    const k = bars.map(b => [b.open, b.close, b.low, b.high]);
    this.chart.setOption({
      animation: false,
      axisPointer: { link: [{ xAxisIndex: "all" }] },
      grid: [
        { left: 60, right: 20, top: 20, height: 300 },
        { left: 60, right: 20, top: 340, height: 80 },
      ],
      xAxis: [
        { type: "category", data: bars.map(b => b.date), gridIndex: 0, boundaryGap: true, axisLine: { lineStyle: { color: "#c4ccd8" } } },
        { type: "category", data: bars.map(b => b.date), gridIndex: 1, axisLabel: { show: false }, axisTick: { show: false } },
      ],
      yAxis: [
        { scale: true, gridIndex: 0, splitLine: { lineStyle: { color: "#f0f2f5" } } },
        { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { show: false }, splitLine: { show: false } },
      ],
      dataZoom: [
        { type: "inside", xAxisIndex: [0, 1], start: 40, end: 100 },
        { type: "slider", xAxisIndex: [0, 1], bottom: 2, height: 18, start: 40, end: 100 },
      ],
      brush: { toolbox: ["lineX"], xAxisIndex: 0, brushLink: "all",
        outOfBrush: { colorAlpha: 0.3 }, brushStyle: { color: "rgba(24,95,165,.15)" } },
      toolbox: { feature: { brush: { type: ["lineX"] } }, right: 20 },
      series: [
        { name: "日K", type: "candlestick", data: k, xAxisIndex: 0, yAxisIndex: 0,
          itemStyle: { color: "#d93025", color0: "#0f8a4d", borderColor: "#d93025", borderColor0: "#0f8a4d" } },
        { name: "MA5", type: "line", data: ma(5), symbol: "none", lineStyle: { width: 1, color: "#ef9f27" } },
        { name: "MA10", type: "line", data: ma(10), symbol: "none", lineStyle: { width: 1, color: "#534ab7" } },
        { name: "MA20", type: "line", data: ma(20), symbol: "none", lineStyle: { width: 1, color: "#0f8a4d" } },
        { name: "成交量", type: "bar", data: bars.map(b => b.volume), xAxisIndex: 1, yAxisIndex: 1,
          itemStyle: { color: (p) => bars[p.dataIndex] && bars[p.dataIndex].close >= bars[p.dataIndex].open ? "#d93025" : "#0f8a4d" } },
      ],
      tooltip: {
        trigger: "axis", axisPointer: { type: "cross" },
        formatter: ps => {
          const b = bars[ps[0].dataIndex];
          if (!b) return "";
          return `${b.date}<br>开 ${fmt(b.open)} 高 ${fmt(b.high)}<br>低 ${fmt(b.low)} 收 ${fmt(b.close)} ${pctHtml(b.pct_chg)}<br>成交量 ${(b.volume / 10000).toFixed(1)}万手 换手 ${fmt(b.turnover, "%")}`;
        },
      },
    }, true);
    this.chart.dispatchAction({ type: "takeGlobalCursor", key: "brush", brushOption: { brushType: "lineX", brushMode: "single" } });
    this.chart.off("brushEnd");
    this.chart.on("brushEnd", params => {
      const areas = params.areas || [];
      if (!areas.length) { this.selRange = null; document.getElementById("quote-brush-match").style.display = "none"; return; }
      const a = areas[0].coordRange || [];
      if (!a.length) return;
      const i0 = bars.findIndex(b => b.date >= a[0]);
      const i1 = bars.findIndex(b => b.date >= a[1]);
      const start = Math.max(0, i0);
      const end = i1 === -1 ? bars.length - 1 : Math.max(start + 4, i1 - 1);
      this.selRange = [start, end];
      document.getElementById("quote-brush-match").style.display = "";
      toast(`已选择 ${bars[start].date} ~ ${bars[end].date}（${end - start + 1} 根K线）`);
    });
  },

  useSelection() {
    if (!this.selRange) return;
    const [s, e] = this.selRange;
    const seg = this.bars.slice(s, e + 1);
    if (seg.length < 5) { toast("选区太短，至少选5根K线"); return; }
    const tpl = {
      code: this.code,
      closes: seg.map(b => b.close),
      vols: seg.map(b => b.volume),
      dates: seg.map(b => b.date),
    };
    localStorage.setItem("qs_template", JSON.stringify(tpl));
    toast(`已保存模板（${tpl.dates.length} 根），前往形态匹配`);
    App.go("pattern");
    Pattern.refreshTemplate();
  },
};
