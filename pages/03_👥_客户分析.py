"""实验六：高维非空间数据可视化 — 客户分析"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from utils import load_data, TUFTE_COLORS, PLOTLY_TUFTE_LAYOUT, get_valid_orders

st.set_page_config(page_title="客户分析", page_icon="👥", layout="wide")
orders, products, customers = load_data()

st.title("👥 客户分析")
st.markdown("*实验六：高维非空间数据可视化 — RFM分析、客户分群、多维特征探索*")

valid = get_valid_orders(orders)

# ---- RFM 计算 ----
ref_date = valid["date"].max() + pd.Timedelta(days=1)
rfm = valid.groupby("customer_id").agg(
    recency=("date", lambda x: (ref_date - x.max()).days),
    frequency=("order_id", "nunique"),
    monetary=("total_amount", "sum"),
).reset_index()

# ---- K-Means 分群 ----
features = rfm[["recency", "frequency", "monetary"]]
scaler = StandardScaler()
features_scaled = scaler.fit_transform(features)
kmeans = KMeans(n_clusters=4, random_state=42, n_init=10)
rfm["cluster"] = kmeans.fit_predict(features_scaled)

cluster_labels = {
    0: "潜力客户",
    1: "重要价值客户",
    2: "一般客户",
    3: "流失风险客户",
}
rfm["segment"] = rfm["cluster"].map(cluster_labels)

# 计算每个cluster的平均值来重命名
cluster_means = rfm.groupby("cluster")[["recency", "frequency", "monetary"]].mean()
# 根据均值重新映射segment到更准确的名称
high_value_cluster = cluster_means["monetary"].idxmax()
freq_cluster = cluster_means["frequency"].idxmax()
low_value_cluster = cluster_means["monetary"].idxmin()

for cid in rfm["cluster"].unique():
    if cid == high_value_cluster:
        cluster_labels[cid] = "高价值客户"
    elif cid == low_value_cluster:
        cluster_labels[cid] = "低活跃客户"
    elif cluster_means.loc[cid, "recency"] < cluster_means["recency"].median():
        cluster_labels[cid] = "活跃新客"
    else:
        cluster_labels[cid] = "沉睡客户"

rfm["segment"] = rfm["cluster"].map(cluster_labels)
seg_colors = {"高价值客户": "#27AE60", "活跃新客": "#3498DB", "沉睡客户": "#E74C3C", "低活跃客户": "#95A5A6"}

# ---- 侧边栏 ----
with st.sidebar:
    st.subheader("🔍 筛选")
    sel_seg = st.multiselect("客户分层", list(cluster_labels.values()), default=list(cluster_labels.values()))
    st.markdown("---")
    st.markdown("### 📊 分群统计")
    seg_counts = rfm["segment"].value_counts()
    for seg, cnt in seg_counts.items():
        color = seg_colors.get(seg, "#888")
        st.markdown(f"<span style='color:{color}'>●</span> {seg}: **{cnt}** 人", unsafe_allow_html=True)

# ---- KPI ----
rfm_f = rfm[rfm["segment"].isin(sel_seg)]

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("客户总数", len(rfm_f))
with col2:
    st.metric("总销售额", f"¥{rfm_f['monetary'].sum():,.0f}")
with col3:
    st.metric("人均消费", f"¥{rfm_f['monetary'].mean():,.0f}")
with col4:
    st.metric("人均频次", f"{rfm_f['frequency'].mean():.1f}次")
with col5:
    st.metric("平均最近天数", f"{rfm_f['recency'].mean():.0f}天")

st.markdown("---")

# ---- RFM 3D 散点图 ----
row1_l, row1_r = st.columns([3, 2])

with row1_l:
    st.markdown("### 🎯 RFM 三维客户分群")
    fig = px.scatter_3d(rfm_f, x="recency", y="frequency", z="monetary",
                         color="segment", color_discrete_map=seg_colors,
                         hover_data={"customer_id": True, "recency": True, "frequency": True, "monetary": True},
                         opacity=0.7, size_max=8)
    fig.update_layout(**PLOTLY_TUFTE_LAYOUT,
        scene=dict(xaxis_title="最近购买 (天)", yaxis_title="购买频次", zaxis_title="消费金额 (元)"),
        legend=dict(title=""), height=500)
    fig.update_traces(marker=dict(size=5))
    st.plotly_chart(fig, use_container_width=True)

with row1_r:
    st.markdown("### 📊 客户分层占比")
    seg_pie = rfm_f.groupby("segment")["customer_id"].count().reset_index()
    seg_pie.columns = ["segment", "count"]
    seg_pie = seg_pie.sort_values("count", ascending=False)
    fig = px.pie(seg_pie, names="segment", values="count", hole=0.5,
                 color="segment", color_discrete_map=seg_colors)
    fig.update_layout(**PLOTLY_TUFTE_LAYOUT, showlegend=False)
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

# ---- 平行坐标图 ----
st.markdown("---")
st.markdown("### 🔗 多维特征平行坐标图 (Parallel Coordinates)")

pc_data = rfm_f.sample(min(300, len(rfm_f)), random_state=42).copy()
pc_data["seg_id"] = pc_data["cluster"]

# 标准化用于平行坐标
cols_to_plot = ["recency", "frequency", "monetary"]
pc_scaled = pc_data.copy()
for col in cols_to_plot:
    pc_scaled[col] = (pc_data[col] - pc_data[col].min()) / (pc_data[col].max() - pc_data[col].min() + 1e-9)
pc_scaled["segment"] = pc_data["segment"]

fig = px.parallel_coordinates(pc_scaled, dimensions=["recency", "frequency", "monetary"],
                               color="seg_id", color_continuous_scale="Viridis",
                               labels={"recency":"最近天数", "frequency":"购买频次", "monetary":"消费金额"})
fig.update_layout(**PLOTLY_TUFTE_LAYOUT, title="", height=400)
st.plotly_chart(fig, use_container_width=True)

# ---- 客户价值分布 & 新老客趋势 ----
st.markdown("---")
col_a, col_b = st.columns(2)

with col_a:
    st.markdown("### 💎 客户价值分布")
    fig = px.histogram(rfm_f, x="monetary", nbins=40, color="segment",
                        color_discrete_map=seg_colors, marginal="box",
                        labels={"monetary": "消费金额 (元)", "count": "客户数"})
    fig.update_layout(**PLOTLY_TUFTE_LAYOUT, title="", legend=dict(title=""))
    st.plotly_chart(fig, use_container_width=True)

with col_b:
    st.markdown("### 🆕 新客 vs 老客 月度趋势")
    monthly_cust = valid.merge(customers[["customer_id", "registration_date"]], on="customer_id")
    monthly_cust["reg_month"] = monthly_cust["registration_date"].dt.to_period("M").dt.to_timestamp()
    monthly_cust["order_month"] = monthly_cust["date"].dt.to_period("M").dt.to_timestamp()
    monthly_cust["is_new"] = monthly_cust["order_month"] == monthly_cust["reg_month"]

    new_vs_return = monthly_cust.groupby(["order_month", "is_new"])["customer_id"].nunique().reset_index()
    new_vs_return["type"] = new_vs_return["is_new"].map({True: "新客户", False: "老客户"})

    fig = px.area(new_vs_return, x="order_month", y="customer_id", color="type",
                  color_discrete_map={"新客户": TUFTE_COLORS[1], "老客户": TUFTE_COLORS[0]},
                  labels={"order_month": "月份", "customer_id": "客户数", "type": ""})
    fig.update_layout(**PLOTLY_TUFTE_LAYOUT, title="", legend=dict(title=""))
    st.plotly_chart(fig, use_container_width=True)

# ---- 客户画像 ----
st.markdown("---")
st.markdown("### 🧬 客户画像雷达图")

# 按分群汇总
profile = rfm.merge(customers[["customer_id", "age_group", "gender"]], on="customer_id")
seg_profile = profile.groupby("segment").agg(
    avg_recency=("recency", "mean"),
    avg_frequency=("frequency", "mean"),
    avg_monetary=("monetary", "mean"),
    total_customers=("customer_id", "nunique"),
).reset_index()

# 标准化用于雷达图
radar_cols = ["avg_recency", "avg_frequency", "avg_monetary"]
radar_norm = seg_profile.copy()
for c in radar_cols:
    mn, mx = radar_norm[c].min(), radar_norm[c].max()
    if mx > mn:
        radar_norm[c] = (radar_norm[c] - mn) / (mx - mn)
# Recency低 = 更好 (最近购买 = 好), 反转
radar_norm["avg_recency"] = 1 - radar_norm["avg_recency"]

fig = go.Figure()
for _, row in radar_norm.iterrows():
    fig.add_trace(go.Scatterpolar(
        r=[row["avg_recency"], row["avg_frequency"], row["avg_monetary"], row["avg_recency"]],
        theta=["活跃度", "购买频次", "消费力", "活跃度"],
        fill="toself", name=row["segment"],
        line=dict(color=seg_colors.get(row["segment"], "#888"))))
fig.update_layout(**PLOTLY_TUFTE_LAYOUT, title="",
    polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
    legend=dict(title=""), height=400)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption("客户高维分析完成 · K-Means 聚类 (k=4) · 平行坐标 + RFM 三维散点")
