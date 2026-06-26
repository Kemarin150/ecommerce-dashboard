"""实验四：时序数据可视化 — 销售趋势分析"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from utils import load_data, TUFTE_COLORS, PLOTLY_TUFTE_LAYOUT, get_valid_orders
_axis = dict(gridcolor="#EEEEEE", zeroline=False, linecolor="#CCCCCC")

st.set_page_config(page_title="销售趋势", page_icon="📈", layout="wide")
orders, products, customers = load_data()

st.title("📈 销售趋势分析")
st.markdown("*实验四：时序数据可视化 — 探索销售额的时间维度模式与季节性规律*")

# ---- 侧边栏 ----
with st.sidebar:
    st.subheader("⏱️ 时间粒度")
    granularity = st.radio("选择粒度", ["日", "周", "月"], horizontal=True)
    show_ma = st.checkbox("显示移动平均线", True)
    if show_ma:
        ma_window = st.slider("移动平均窗口 (天)", 3, 90, 30, step=1)
    show_yoy = st.checkbox("显示同比增长率", True)
    st.markdown("---")
    st.subheader("🎯 销售峰值标注")
    show_promo = st.checkbox("标注销售峰值", True)
    if show_promo:
        promo_mode = st.radio("标注方式", ["自动检测异常峰值", "手动输入日期"], horizontal=True)
        if promo_mode == "手动输入日期":
            promo_input = st.text_input(
                "日期列表 (YYYY-MM-DD=标签, 逗号分隔)",
                value="",
                placeholder="例: 2023-06-18=促销A, 2023-11-11=促销B",
            )
            promo_colors_input = st.text_input(
                "颜色列表 (逗号分隔, 留空自动分配)",
                value="",
                placeholder="例: #E74C3C, #F39C12",
            )
            auto_mode = False
        else:
            auto_mode = True
            promo_sensitivity = st.slider("峰值灵敏度", 1.0, 4.0, 2.0, 0.5,
                                          help="标准差倍数阈值，越低标注越多")
            promo_max_count = st.slider("最多标注数", 1, 15, 6)

# ---- 主区域 ----
valid = get_valid_orders(orders)

if granularity == "日":
    freq = "D"; fmt = "%m/%d"
elif granularity == "周":
    freq = "W"; fmt = "%m/%d"
else:
    freq = "ME"; fmt = "%Y/%m"

ts = valid.set_index("date").resample(freq)["total_amount"].agg(["sum", "count"]).reset_index()
ts.columns = ["date", "sales", "orders"]
ts["year"] = ts["date"].dt.year

col1, col2 = st.columns([3, 1])
with col1:
    st.markdown("### 💰 销售额 & 订单量趋势")
with col2:
    metric_cols = st.columns(2)
    total_s = ts["sales"].sum()
    avg_daily = ts["sales"].mean()
    metric_cols[0].metric("累计销售额", f"¥{total_s:,.0f}")
    metric_cols[1].metric("日均/周/月均", f"¥{avg_daily:,.0f}")

# 双轴图：柱状图(销售额) + 折线(订单量)
fig = go.Figure()
fig.add_trace(go.Bar(x=ts["date"], y=ts["sales"], name="销售额",
                      marker_color=TUFTE_COLORS[0], opacity=0.7, yaxis="y"))
fig.add_trace(go.Scatter(x=ts["date"], y=ts["orders"], name="订单量",
                          line=dict(color=TUFTE_COLORS[2], width=2.5), yaxis="y2"))

if show_ma:
    ts["sales_ma"] = ts["sales"].rolling(ma_window, min_periods=1, center=True).mean()
    fig.add_trace(go.Scatter(x=ts["date"], y=ts["sales_ma"], name=f"{ma_window}期均线",
                              line=dict(color=TUFTE_COLORS[1], width=2, dash="dash")))

fig.update_layout(**PLOTLY_TUFTE_LAYOUT)
fig.update_layout(title="",
    yaxis=dict(title="销售额 (元)", side="left", **_axis),
    yaxis2=dict(title="订单量", side="right", overlaying="y", showgrid=False, **_axis),
    hovermode="x unified", legend=dict(orientation="h", y=1.15))

# ---- 峰值标注：竖线 + 色带 + 图例 ----
if show_promo:
    promos = []
    if auto_mode:
        # 自动检测：销售额超出 rolling_mean + N*rolling_std 的日期
        daily = valid.set_index("date").resample("D")["total_amount"].sum()
        roll_mean = daily.rolling(14, min_periods=7, center=True).mean()
        roll_std = daily.rolling(14, min_periods=7, center=True).std()
        threshold = roll_mean + promo_sensitivity * roll_std
        peaks = daily[daily > threshold].sort_values(ascending=False).head(promo_max_count)
        # 去重：合并相邻7天内的峰值，保留最高的
        merged = []
        used_dates = set()
        for peak_date, val in peaks.items():
            if any(abs((peak_date - d).days) < 7 for d in used_dates):
                continue
            merged.append((peak_date, val))
            used_dates.add(peak_date)
        # 按日期排序，分配颜色
        merged.sort(key=lambda x: x[0])
        peak_colors = ["#E74C3C", "#F39C12", "#9B59B6", "#3498DB", "#E67E22", "#27AE60"]
        for i, (d, val) in enumerate(merged):
            label = d.strftime("%m/%d")
            color = peak_colors[i % len(peak_colors)]
            promos.append((d, label, color))
    else:
        # 手动输入模式
        date_parts = [p.strip() for p in promo_input.split(",") if p.strip()]
        color_parts = [c.strip() for c in promo_colors_input.split(",") if c.strip()]
        for i, part in enumerate(date_parts):
            if "=" in part:
                date_str, label = part.split("=", 1)
            else:
                date_str = part
                label = part
            try:
                d = pd.Timestamp(date_str.strip())
                c = color_parts[i] if i < len(color_parts) else TUFTE_COLORS[i % len(TUFTE_COLORS)]
                promos.append((d, label.strip(), c))
            except Exception:
                continue

    promo_colors_added = set()
    promos_in_range = []
    y_max = ts["sales"].max()
    for promo_date, label, color in promos:
        d = promo_date
        if d >= ts["date"].min() and d <= ts["date"].max():
            promos_in_range.append((d, label, color))
            # 粗实线竖线
            fig.add_vline(x=d, line_width=3, line_dash="solid", line_color=color,
                          opacity=0.85)
            # 顶部标签
            fig.add_annotation(x=d, y=y_max * 0.97, text=f"<b>{label}</b>",
                              showarrow=False, font=dict(size=14, color="white"),
                              bgcolor=color, bordercolor=color, borderwidth=1,
                              borderpad=4, opacity=0.95)
            # 色带
            if granularity == "月":
                span_days = 18
            elif granularity == "周":
                span_days = 10
            else:
                span_days = 7
            fig.add_vrect(x0=d - pd.Timedelta(days=span_days),
                          x1=d + pd.Timedelta(days=span_days),
                          fillcolor=color, opacity=0.22, line_width=0,
                          layer="below")
            # 图例
            if color not in promo_colors_added:
                promo_colors_added.add(color)
                fig.add_trace(go.Scatter(
                    x=[None], y=[None], mode="lines",
                    line=dict(color=color, width=4),
                    name=label, showlegend=True,
                ))
    if promos_in_range:
        source = "自动检测" if auto_mode else "手动标注"
        st.markdown(
            "📢 {src} **{n}** 个销售峰值：".format(src=source, n=len(promos_in_range))
            + " &nbsp; ".join([
                '<span style="color:{c};font-weight:bold;font-size:1.1em">● {l}</span>'.format(c=c, l=l)
                for _, l, c in promos_in_range[:6]
            ]),
            unsafe_allow_html=True,
        )
    elif auto_mode:
        st.info("未检测到显著销售峰值，可降低灵敏度或切换为手动输入")

st.plotly_chart(fig, use_container_width=True)

# ---- 同比增长率 ----
if show_yoy:
    st.markdown("---")
    st.markdown("### 📊 同比增长率分析")
    monthly = valid.set_index("date").resample("ME")["total_amount"].sum().reset_index()
    monthly["year"] = monthly["date"].dt.year
    monthly["month"] = monthly["date"].dt.month

    pivot = monthly.pivot_table(values="total_amount", index="month", columns="year", aggfunc="sum")
    if len(pivot.columns) >= 2:
        y1, y2 = pivot.columns[-2], pivot.columns[-1]
        pivot["yoy"] = ((pivot[y2] - pivot[y1]) / pivot[y1] * 100).round(1)

        fig = go.Figure()
        fig.add_trace(go.Bar(x=pivot.index, y=pivot["yoy"],
                              marker_color=[TUFTE_COLORS[1] if v < 0 else TUFTE_COLORS[3] for v in pivot["yoy"]],
                              text=[f"{v:+.1f}%" for v in pivot["yoy"]], textposition="outside"))
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.update_layout(**PLOTLY_TUFTE_LAYOUT)
        fig.update_layout(title="",
            xaxis=dict(tickmode="array", tickvals=list(range(1,13)),
                        ticktext=["1月","2月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"],
                        **_axis),
            yaxis=dict(**_axis, title="同比增长率 (%)"),
            showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

# ---- 季节性热力图 ----
st.markdown("---")
st.markdown("### 🔥 月度销售季节性热力图")
heatmap_data = valid.copy()
heatmap_data["year"] = heatmap_data["date"].dt.year
heatmap_data["month"] = heatmap_data["date"].dt.month
hm = heatmap_data.groupby(["year", "month"])["total_amount"].sum().unstack()

fig = px.imshow(hm.values, x=[f"{m}月" for m in hm.columns], y=hm.index,
                color_continuous_scale="YlOrRd", text_auto=".0f", aspect="auto")
fig.update_layout(**PLOTLY_TUFTE_LAYOUT, title="", xaxis_title="月份", yaxis_title="年份", height=250)
st.plotly_chart(fig, use_container_width=True)

# ---- 工作日 vs 周末 ----
st.markdown("---")
col_a, col_b = st.columns(2)

with col_a:
    st.markdown("### 📅 工作日 vs 周末 对比")
    valid_wd = valid.copy()
    valid_wd["is_weekend"] = valid_wd["date"].dt.dayofweek >= 5
    wd_summary = valid_wd.groupby("is_weekend")["total_amount"].agg(["sum", "mean", "count"]).reset_index()
    wd_summary["label"] = wd_summary["is_weekend"].map({True: "周末", False: "工作日"})

    fig = go.Figure()
    fig.add_trace(go.Bar(x=wd_summary["label"], y=wd_summary["sum"],
                          marker_color=[TUFTE_COLORS[4], TUFTE_COLORS[0]], text=wd_summary["sum"].apply(lambda x: f"¥{x:,.0f}")))
    fig.update_layout(**PLOTLY_TUFTE_LAYOUT)
    fig.update_layout(title="", yaxis_title="总销售额 (元)", showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

with col_b:
    st.markdown("### 🕐 各月份平均销售额")
    month_avg = heatmap_data.groupby("month")["total_amount"].mean().reset_index()
    month_avg.columns = ["month", "avg_sales"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=month_avg["month"], y=month_avg["avg_sales"], mode="lines+markers",
                              line=dict(color=TUFTE_COLORS[0], width=3), marker=dict(size=10),
                              fill="tozeroy", fillcolor="rgba(52,152,219,0.1)"))
    fig.update_layout(**PLOTLY_TUFTE_LAYOUT)
    fig.update_layout(title="",
        xaxis=dict(tickmode="array", tickvals=list(range(1,13)),
                    ticktext=["1月","2月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"],
                    **_axis),
        yaxis=dict(**_axis, title="平均销售额 (元)"),
        showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption("时序分析完成 · 粒度: {} · 数据条数: {:,}".format(granularity, len(ts)))
