"""综合高级分析：相关性、漏斗、帕累托、支付分析"""
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go
import plotly.express as px
from utils import load_data, TUFTE_COLORS, PLOTLY_TUFTE_LAYOUT, get_valid_orders

st.set_page_config(page_title="高级分析", page_icon="🔬", layout="wide")
orders, products, customers = load_data()

st.title("🔬 高级综合分析")
st.markdown("*综合应用：相关性分析、漏斗分析、支付方式、利润结构等高级分析技术*")

valid = get_valid_orders(orders)
prod_sales = valid.drop(columns=["unit_price"]).merge(products, on="product_id")

# ---- 侧边栏 ----
with st.sidebar:
    st.subheader("🔬 分析模块")
    analysis = st.radio("选择分析", [
        "📊 相关性热力图",
        "🔽 销售漏斗",
        "💳 支付方式分析",
        "💹 毛利结构分析",
        "📦 客单价分析",
    ])
    st.markdown("---")
    if analysis == "📊 相关性热力图":
        st.caption("使用 Seaborn 热力图展示数值指标之间的线性相关性")

# ---- 分析模块 ----
if analysis == "📊 相关性热力图":
    st.markdown("### 📊 数值指标相关性分析")
    st.markdown("皮尔逊相关系数热力图 — 探索各业务指标间的关联强度")

    col_a, col_b = st.columns([2, 3])

    with col_a:
        st.markdown("#### 月度指标")
        monthly = valid.set_index("date").resample("ME")
        monthly_metrics = pd.DataFrame({
            "销售额": monthly["total_amount"].sum(),
            "订单数": monthly["order_id"].nunique(),
            "客户数": monthly["customer_id"].nunique(),
            "平均客单价": monthly["total_amount"].sum() / monthly["order_id"].nunique(),
            "退货数": monthly.apply(lambda x: len(x) - len(get_valid_orders(x))),
        }).dropna()

        corr = monthly_metrics.corr()
        fig, ax = plt.subplots(figsize=(6, 5))
        mask = np.triu(np.ones_like(corr, dtype=bool))
        sns.heatmap(corr, annot=True, fmt=".3f", cmap="RdBu_r", center=0,
                     mask=mask, ax=ax, square=True, linewidths=.5,
                     cbar_kws={"shrink": .5})
        ax.set_title("月度指标相关性", fontsize=13, fontweight="bold")
        st.pyplot(fig)

        st.markdown("#### 每日指标")
        daily = valid.set_index("date").resample("D")
        daily_metrics = pd.DataFrame({
            "销售额": daily["total_amount"].sum(),
            "订单数": daily["order_id"].nunique(),
            "客户数": daily["customer_id"].nunique(),
            "平均客单价": daily["total_amount"].sum() / daily["order_id"].nunique().clip(lower=1),
        }).dropna()

        corr_d = daily_metrics.corr()
        fig, ax = plt.subplots(figsize=(6, 5))
        sns.heatmap(corr_d, annot=True, fmt=".3f", cmap="RdBu_r", center=0,
                     mask=np.triu(np.ones_like(corr_d, dtype=bool)),
                     ax=ax, square=True, linewidths=.5, cbar_kws={"shrink": .5})
        ax.set_title("每日指标相关性", fontsize=13, fontweight="bold")
        st.pyplot(fig)

    with col_b:
        st.markdown("#### 品类×月份 销售额热力图")
        cat_month = prod_sales.copy()
        cat_month["month"] = cat_month["date"].dt.month
        hm = cat_month.groupby(["category", "month"])["total_amount"].sum().unstack()

        fig = px.imshow(hm.values, x=[f"{m}月" for m in hm.columns], y=hm.index,
                        color_continuous_scale="YlOrRd", text_auto=".0f", aspect="auto")
        fig.update_layout(**PLOTLY_TUFTE_LAYOUT, title="", height=400,
                           xaxis_title="月份", yaxis_title="品类")
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### 各品类利润散点矩阵 (气泡)")
        bubble = prod_sales.groupby(["category", "name"]).agg(
            total_sales=("total_amount", "sum"),
            total_qty=("quantity", "sum"),
            avg_price=("unit_price", "mean"),
            avg_cost=("unit_cost", "mean"),
        ).reset_index()
        bubble["margin"] = bubble["total_sales"] - bubble["total_qty"] * bubble["avg_cost"]
        bubble["margin_pct"] = bubble["margin"] / bubble["total_sales"] * 100

        fig = px.scatter(bubble, x="avg_price", y="total_qty", size="total_sales",
                          color="category", hover_name="name",
                          color_discrete_sequence=TUFTE_COLORS,
                          labels={"avg_price": "价格", "total_qty": "销量", "total_sales": "销售额"})
        fig.update_layout(**PLOTLY_TUFTE_LAYOUT, title="", height=400)
        st.plotly_chart(fig, use_container_width=True)

elif analysis == "🔽 销售漏斗":
    st.markdown("### 🔽 订单转化漏斗分析")

    # 模拟漏斗: 浏览→加购→下单→支付→完成
    total_visitors = len(valid) * 8  # 假设流量
    funnel_stages = pd.DataFrame({
        "阶段": ["浏览商品", "加入购物车", "提交订单", "完成支付", "确认收货"],
        "数量": [
            total_visitors,
            int(total_visitors * 0.35),
            int(total_visitors * 0.15),
            int(total_visitors * 0.12),
            len(valid),
        ]
    })

    col_flow, col_rate = st.columns([2, 1])

    with col_flow:
        fig = px.funnel(funnel_stages, x="数量", y="阶段",
                        color_discrete_sequence=[TUFTE_COLORS[0]])
        fig.update_layout(**PLOTLY_TUFTE_LAYOUT, title="", height=400)
        st.plotly_chart(fig, use_container_width=True)

    with col_rate:
        st.markdown("#### 转化率")
        for i in range(1, len(funnel_stages)):
            rate = funnel_stages.iloc[i]["数量"] / funnel_stages.iloc[i-1]["数量"] * 100
            st.metric(
                f"{funnel_stages.iloc[i-1]['阶段']} → {funnel_stages.iloc[i]['阶段']}",
                f"{rate:.1f}%"
            )
        overall = funnel_stages.iloc[-1]["数量"] / funnel_stages.iloc[0]["数量"] * 100
        st.metric("整体转化率", f"{overall:.2f}%")

    st.markdown("---")
    st.markdown("#### 📊 实际订单状态分布")
    all_status = orders.groupby("status")["order_id"].count().reset_index()
    all_status.columns = ["状态", "数量"]
    status_colors_map = {s: c for s, c in zip(all_status["状态"], TUFTE_COLORS)}
    fig = px.funnel(all_status, x="数量", y="状态", color="状态",
                    color_discrete_map=status_colors_map)
    fig.update_layout(**PLOTLY_TUFTE_LAYOUT, title="", height=300)
    st.plotly_chart(fig, use_container_width=True)

elif analysis == "💳 支付方式分析":
    st.markdown("### 💳 支付方式多维分析")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("#### 支付方式占比")
        pay_data = valid.groupby("payment_method")["total_amount"].agg(["sum", "count"]).reset_index()
        pay_data.columns = ["method", "amount", "count"]

        fig = px.pie(pay_data, names="method", values="amount", hole=0.5,
                     color_discrete_sequence=TUFTE_COLORS)
        fig.update_layout(**PLOTLY_TUFTE_LAYOUT)
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=10))
        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.markdown("#### 支付方式 × 品类 交叉分析")
        pay_cat = prod_sales.groupby(["payment_method", "category"])["total_amount"].sum().unstack(fill_value=0)

        fig = px.imshow(pay_cat.values, x=pay_cat.columns, y=pay_cat.index,
                        color_continuous_scale="Blues", text_auto=".0f", aspect="auto")
        fig.update_layout(**PLOTLY_TUFTE_LAYOUT, title="", height=350,
                           xaxis_title="品类", yaxis_title="支付方式")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("#### 支付方式月度趋势")
    pay_monthly = valid.copy()
    pay_monthly["month"] = pay_monthly["date"].dt.to_period("M").dt.to_timestamp()
    pay_trend = pay_monthly.groupby(["month", "payment_method"])["total_amount"].sum().reset_index()

    fig = px.area(pay_trend, x="month", y="total_amount", color="payment_method",
                  color_discrete_sequence=TUFTE_COLORS,
                  labels={"month": "月份", "total_amount": "销售额 (元)", "payment_method": "支付方式"})
    fig.update_layout(**PLOTLY_TUFTE_LAYOUT, title="", legend=dict(title=""))
    st.plotly_chart(fig, use_container_width=True)

elif analysis == "💹 毛利结构分析":
    st.markdown("### 💹 毛利结构分析")

    prod_sales["cost_total"] = prod_sales["unit_cost"] * prod_sales["quantity"]
    prod_sales["profit"] = prod_sales["total_amount"] - prod_sales["cost_total"]
    prod_sales["margin_pct"] = prod_sales["profit"] / prod_sales["total_amount"] * 100

    col_a, col_b, col_c = st.columns(3)
    total_profit = prod_sales["profit"].sum()
    total_sales = prod_sales["total_amount"].sum()
    with col_a:
        st.metric("总毛利", f"¥{total_profit:,.0f}")
    with col_b:
        st.metric("综合毛利率", f"{total_profit/total_sales*100:.1f}%")
    with col_c:
        st.metric("盈亏产品数", f"{len(prod_sales[prod_sales['profit']>0]['product_id'].unique())}/{products['product_id'].nunique()}")

    st.markdown("---")

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("#### 品类毛利率对比 (箱线图)")
        fig, ax = plt.subplots(figsize=(6, 5))
        order_cats = prod_sales.groupby("category")["margin_pct"].median().sort_values().index.tolist()
        sns.boxplot(data=prod_sales, x="category", y="margin_pct", order=order_cats,
                    palette=[TUFTE_COLORS[i % len(TUFTE_COLORS)] for i in range(len(order_cats))],
                    ax=ax, width=0.5)
        ax.axhline(y=0, color="red", linewidth=1, linestyle="--", alpha=0.5)
        ax.set_title("各品类毛利率分布", fontsize=13, fontweight="bold")
        ax.set_xlabel(""); ax.set_ylabel("毛利率 (%)")
        ax.tick_params(axis="x", rotation=30)
        st.pyplot(fig)

    with col_r:
        st.markdown("#### 毛利率月度趋势")
        margin_monthly = prod_sales.copy()
        margin_monthly["month"] = margin_monthly["date"].dt.to_period("M").dt.to_timestamp()
        mm = margin_monthly.groupby(["month", "category"])["profit"].sum().reset_index()

        fig = px.line(mm, x="month", y="profit", color="category",
                      color_discrete_sequence=TUFTE_COLORS,
                      labels={"month": "月份", "profit": "毛利 (元)", "category": "品类"})
        fig.update_layout(**PLOTLY_TUFTE_LAYOUT, title="", legend=dict(title=""))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("#### 产品利润率排名 (Top & Bottom)")
    prod_margin = prod_sales.groupby("name").agg(
        total_profit=("profit", "sum"),
        avg_margin=("margin_pct", "mean"),
        total_sales=("total_amount", "sum"),
    ).reset_index().sort_values("avg_margin", ascending=False)

    col_top, col_bot = st.columns(2)
    with col_top:
        top_profitable = prod_margin.head(5)
        fig = px.bar(top_profitable, x="avg_margin", y="name", orientation="h",
                     color="avg_margin", color_continuous_scale="Greens",
                     text=top_profitable["avg_margin"].apply(lambda x: f"{x:.1f}%"))
        fig.update_layout(**PLOTLY_TUFTE_LAYOUT, title="Top 5 高毛利产品", yaxis_title="",
                           xaxis_title="平均毛利率 (%)", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_bot:
        bottom_profitable = prod_margin.tail(5)
        fig = px.bar(bottom_profitable, x="avg_margin", y="name", orientation="h",
                     color="avg_margin", color_continuous_scale="Reds",
                     text=bottom_profitable["avg_margin"].apply(lambda x: f"{x:.1f}%"))
        fig.update_layout(**PLOTLY_TUFTE_LAYOUT, title="Bottom 5 低毛利产品", yaxis_title="",
                           xaxis_title="平均毛利率 (%)", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

elif analysis == "📦 客单价分析":
    st.markdown("### 📦 客单价 & 订单结构分析")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("#### 客单价分布 (直方图)")
        order_values = valid.groupby("order_id")["total_amount"].sum()
        fig = px.histogram(order_values, nbins=50, marginal="box",
                           color_discrete_sequence=[TUFTE_COLORS[0]],
                           labels={"value": "客单价 (元)", "count": "订单数"})
        fig.update_layout(**PLOTLY_TUFTE_LAYOUT, title="")
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.markdown("#### 客单价月度变化 (箱线图)")
        valid_month = valid.copy()
        valid_month["month"] = valid_month["date"].dt.to_period("M").dt.to_timestamp()
        order_monthly = valid_month.groupby(["order_id", "month"])["total_amount"].sum().reset_index()

        fig = px.box(order_monthly, x="month", y="total_amount",
                     color_discrete_sequence=[TUFTE_COLORS[0]],
                     labels={"month": "月份", "total_amount": "客单价 (元)"})
        fig.update_layout(**PLOTLY_TUFTE_LAYOUT, title="", height=400, showlegend=False)
        fig.update_traces(marker_size=3)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("#### 每单商品数量分布")
    items_per_order = valid.groupby("order_id")["quantity"].sum()

    col_c, col_d = st.columns(2)
    with col_c:
        fig = px.histogram(items_per_order, nbins=int(items_per_order.max()),
                           color_discrete_sequence=[TUFTE_COLORS[2]],
                           labels={"value": "商品数量", "count": "订单数"})
        fig.update_layout(**PLOTLY_TUFTE_LAYOUT, title="")
        st.plotly_chart(fig, use_container_width=True)

        avg_items = items_per_order.mean()
        st.metric("平均每单商品数", f"{avg_items:.1f} 件")

    with col_d:
        st.markdown("#### 高/低客单价对比")
        median_val = order_values.median()
        high_orders = order_values[order_values > median_val].count()
        low_orders = order_values[order_values <= median_val].count()

        comparison = pd.DataFrame({
            "类型": ["高客单价 (>中位数)", "低客单价 (≤中位数)"],
            "订单数": [high_orders, low_orders],
            "平均金额": [order_values[order_values>median_val].mean(), order_values[order_values<=median_val].mean()],
        })

        fig = px.bar(comparison, x="类型", y="平均金额", color="类型",
                     color_discrete_sequence=[TUFTE_COLORS[0], TUFTE_COLORS[4]],
                     text=comparison["平均金额"].apply(lambda x: f"¥{x:,.0f}"))
        fig.update_layout(**PLOTLY_TUFTE_LAYOUT, title="", yaxis_title="平均客单价 (元)",
                           showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown(f"- 中位数客单价: **¥{median_val:,.0f}**")
        st.markdown(f"- 最高客单价: **¥{order_values.max():,.0f}**")
        st.markdown(f"- 最高单笔商品数: **{int(items_per_order.max())} 件**")

st.markdown("---")
st.caption("高级综合分析完成 · 多维度数据探索")
