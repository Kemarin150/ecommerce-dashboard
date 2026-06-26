"""实验七：层次数据可视化 — 产品分析"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from utils import load_data, TUFTE_COLORS, TUFTE_CATEGORICAL, PLOTLY_TUFTE_LAYOUT, get_valid_orders
_axis = dict(gridcolor="#EEEEEE", zeroline=False, linecolor="#CCCCCC")

st.set_page_config(page_title="产品分析", page_icon="📦", layout="wide")
orders, products, customers = load_data()

st.title("📦 产品分析")
st.markdown("*实验七：层次数据可视化 — 产品类别层级钻取、ABC分析、盈利能力评估*")

valid = get_valid_orders(orders)
prod_sales = valid.drop(columns=["unit_price"]).merge(products, on="product_id")

# ---- 侧边栏 ----
with st.sidebar:
    st.subheader("🔍 筛选")
    cats = sorted(products["category"].dropna().astype(str).unique().tolist())
    sel_cat = st.selectbox("选择大类", ["全部"] + cats)
    if sel_cat != "全部":
        subs = sorted(products[products["category"]==sel_cat]["subcategory"].dropna().astype(str).unique().tolist())
        sel_sub = st.selectbox("选择子类", ["全部"] + subs)
    else:
        sel_sub = "全部"
    st.markdown("---")
    st.subheader("📐 图表选项")
    chart_type = st.radio("层次图类型", ["树图 (Treemap)", "旭日图 (Sunburst)"])

# ---- 筛选 ----
if sel_cat != "全部":
    prod_sales_f = prod_sales[prod_sales["category"] == sel_cat]
    if sel_sub != "全部":
        prod_sales_f = prod_sales_f[prod_sales_f["subcategory"] == sel_sub]
else:
    prod_sales_f = prod_sales

# ---- KPI ----
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("产品数", prod_sales_f["product_id"].nunique())
with col2:
    st.metric("销售额", f"¥{prod_sales_f['total_amount'].sum():,.0f}")
with col3:
    margin = ((prod_sales_f["unit_price"] - prod_sales_f["unit_cost"]) * prod_sales_f["quantity"]).sum()
    st.metric("毛利", f"¥{margin:,.0f}")
with col4:
    avg_margin = (prod_sales_f["unit_price"] - prod_sales_f["unit_cost"]).mean() / prod_sales_f["unit_price"].mean() * 100
    st.metric("平均毛利率", f"{avg_margin:.1f}%")

st.markdown("---")

# ---- 层次图 ----
row1_l, row1_r = st.columns([3, 2])

with row1_l:
    if chart_type == "树图 (Treemap)":
        st.markdown("### 🌳 产品层级树图")
        tree_data = prod_sales.groupby(["category", "subcategory", "name"])["total_amount"].sum().reset_index()
        tree_data["path"] = tree_data["category"] + " / " + tree_data["subcategory"] + " / " + tree_data["name"]

        fig = px.treemap(tree_data, path=["category", "subcategory", "name"],
                          values="total_amount", color="total_amount",
                          color_continuous_scale="Blues")
        fig.update_layout(**PLOTLY_TUFTE_LAYOUT)
        fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
        fig.update_traces(texttemplate="%{label}<br>¥%{value:,.0f}", hovertemplate="%{label}<br>¥%{value:,.2f}")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown("### ☀️ 品类旭日图")
        sun_data = prod_sales.groupby(["category", "subcategory", "name"])["total_amount"].sum().reset_index()
        fig = px.sunburst(sun_data, path=["category", "subcategory", "name"],
                           values="total_amount", color="total_amount",
                           color_continuous_scale="Blues")
        fig.update_layout(**PLOTLY_TUFTE_LAYOUT)
        fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)

with row1_r:
    st.markdown("### 📊 品类销售占比")
    cat_data = prod_sales_f.groupby("category")["total_amount"].sum().reset_index()
    fig = px.pie(cat_data, names="category", values="total_amount", hole=0.5,
                 color="category", color_discrete_sequence=TUFTE_COLORS)
    fig.update_layout(**PLOTLY_TUFTE_LAYOUT, showlegend=False)
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

# ---- 帕累托图 (ABC分析) ----
st.markdown("---")
st.markdown("### 📐 帕累托分析 (ABC 分类)")

pareto_data = prod_sales_f.groupby("name")["total_amount"].sum().sort_values(ascending=False).reset_index()
pareto_data["cumsum"] = pareto_data["total_amount"].cumsum()
pareto_data["cumpct"] = pareto_data["cumsum"] / pareto_data["total_amount"].sum() * 100
pareto_data["abc"] = pareto_data["cumpct"].apply(lambda x: "A类 (0-70%)" if x <= 70 else ("B类 (70-90%)" if x <= 90 else "C类 (90-100%)"))

fig = go.Figure()
fig.add_trace(go.Bar(x=pareto_data["name"], y=pareto_data["total_amount"],
                      name="销售额", marker_color=TUFTE_COLORS[0], opacity=0.8))
fig.add_trace(go.Scatter(x=pareto_data["name"], y=pareto_data["cumpct"],
                          name="累计占比 (%)", yaxis="y2", line=dict(color=TUFTE_COLORS[1], width=3)))
fig.add_hline(y=70, line_dash="dash", line_color=TUFTE_COLORS[3], yref="y2", annotation_text="70%线")
fig.add_hline(y=90, line_dash="dash", line_color=TUFTE_COLORS[4], yref="y2", annotation_text="90%线")
fig.update_layout(**PLOTLY_TUFTE_LAYOUT)
fig.update_layout(title="",
    yaxis=dict(title="销售额 (元)", **_axis),
    yaxis2=dict(title="累计占比 (%)", side="right", overlaying="y", range=[0,105], **_axis),
    xaxis=dict(tickangle=-45, tickfont_size=8, showticklabels=len(pareto_data)<=30, **_axis),
    legend=dict(orientation="h"), hovermode="x")
st.plotly_chart(fig, use_container_width=True)

abc_summary = pareto_data.groupby("abc")["total_amount"].agg(["sum", "count"]).reset_index()
abc_summary.columns = ["分类", "销售额", "产品数"]
abc_summary["占比"] = (abc_summary["销售额"] / abc_summary["销售额"].sum() * 100).round(1)
col_a, col_b, col_c = st.columns(3)
for col, (_, row) in zip([col_a, col_b, col_c], abc_summary.iterrows()):
    col.metric(row["分类"], f"¥{row['销售额']:,.0f}", f"{row['产品数']}个产品 | {row['占比']}%")

# ---- 价格-销量气泡图 ----
st.markdown("---")
st.markdown("### 🫧 价格-销量-利润气泡图")

bubble = prod_sales_f.groupby(["name", "category", "subcategory"]).agg(
    avg_price=("unit_price", "mean"),
    total_qty=("quantity", "sum"),
    total_sales=("total_amount", "sum"),
    total_cost=("unit_cost", lambda x: (x * prod_sales_f.loc[x.index, "quantity"]).sum()),
).reset_index()
bubble["profit_margin"] = (bubble["total_sales"] - bubble["total_cost"]) / bubble["total_sales"] * 100

fig = px.scatter(bubble, x="avg_price", y="total_qty", size="total_sales",
                  color="category", hover_name="name",
                  color_discrete_sequence=TUFTE_COLORS, size_max=45,
                  labels={"avg_price":"平均售价 (元)", "total_qty":"总销量"})
fig.update_layout(**PLOTLY_TUFTE_LAYOUT, title="")
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
col_m1, col_m2 = st.columns(2)

with col_m1:
    st.markdown("### 💹 各品类毛利率对比")
    margin_cat = prod_sales.groupby("category").apply(
        lambda x: ((x["unit_price"] - x["unit_cost"]) * x["quantity"]).sum() / x["total_amount"].sum() * 100
    ).reset_index(name="margin")
    margin_cat.columns = ["category", "profit_margin"]
    fig = px.bar(margin_cat.sort_values("profit_margin"), x="profit_margin", y="category",
                 orientation="h", color="category", color_discrete_sequence=TUFTE_COLORS,
                 text=margin_cat["profit_margin"].apply(lambda x: f"{x:.1f}%"))
    fig.update_layout(**PLOTLY_TUFTE_LAYOUT, title="", xaxis_title="毛利率 (%)", yaxis_title="",
                       showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

with col_m2:
    st.markdown("### 🏅 子类别销售额对比")
    sub_sales = prod_sales_f.groupby(["category", "subcategory"])["total_amount"].sum().reset_index()
    sub_sales = sub_sales.sort_values("total_amount", ascending=True).tail(12)
    fig = px.bar(sub_sales, x="total_amount", y="subcategory", color="category",
                 color_discrete_sequence=TUFTE_COLORS, orientation="h")
    fig.update_layout(**PLOTLY_TUFTE_LAYOUT, title="", xaxis_title="销售额 (元)", yaxis_title="",
                       showlegend=True, legend=dict(title=""))
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption("产品层次分析完成 · 遵循 Tufte 可视化原则")
