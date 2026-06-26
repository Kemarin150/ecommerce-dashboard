"""实验五：地理空间数据可视化 — 地理分布分析"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from utils import load_data, TUFTE_COLORS, PLOTLY_TUFTE_LAYOUT, get_valid_orders

st.set_page_config(page_title="地理分布", page_icon="🗺️", layout="wide")
orders, products, customers = load_data()

st.title("🗺️ 地理空间数据可视化")
st.markdown("*实验五：地理空间数据可视化 — 省份销售分布、城市气泡地图、区域对比分析*")

valid = get_valid_orders(orders)

# ---- 中国主要城市经纬度 ----
CITY_COORDS = {
    "北京市": (39.90, 116.40), "上海市": (31.23, 121.47),
    "广州市": (23.13, 113.26), "深圳市": (22.54, 114.06),
    "杭州市": (30.27, 120.15), "南京市": (32.06, 118.80),
    "成都市": (30.57, 104.07), "武汉市": (30.59, 114.31),
    "西安市": (34.34, 108.94), "重庆市": (29.43, 106.91),
    "长沙市": (28.23, 112.94), "郑州市": (34.75, 113.63),
    "济南市": (36.65, 116.99), "青岛市": (36.07, 120.38),
    "合肥市": (31.82, 117.23), "福州市": (26.07, 119.30),
    "厦门市": (24.48, 118.09), "沈阳市": (41.81, 123.43),
    "大连市": (38.91, 121.61), "宁波市": (29.87, 121.54),
    "温州市": (28.00, 120.70), "无锡市": (31.49, 120.31),
    "苏州市": (31.30, 120.59), "东莞市": (23.02, 113.75),
    "佛山市": (23.02, 113.12), "洛阳市": (34.62, 112.45),
    "宜昌市": (30.69, 111.29), "绵阳市": (31.47, 104.68),
    "咸阳市": (34.33, 108.71), "株洲市": (27.83, 113.13),
    "烟台市": (37.46, 121.45), "芜湖市": (31.35, 118.43),
}

# ---- 省份聚合 ----
prov_data = valid.groupby("province").agg(
    sales=("total_amount", "sum"),
    orders=("order_id", "nunique"),
    customers=("customer_id", "nunique"),
).reset_index()
prov_data["avg_order"] = (prov_data["sales"] / prov_data["orders"]).round(0)
prov_data = prov_data.sort_values("sales", ascending=False)

# ---- 城市聚合 + 经纬度 ----
city_data = valid.groupby("city").agg(
    sales=("total_amount", "sum"),
    orders=("order_id", "nunique"),
    customers=("customer_id", "nunique"),
).reset_index()

# 优先用数据自带的经纬度列（上传数据），否则用内置坐标
if "city_lat" in valid.columns and "city_lon" in valid.columns:
    coords = valid[["city", "city_lat", "city_lon"]].drop_duplicates()
    city_data = city_data.merge(coords, on="city", how="left")
    city_data.rename(columns={"city_lat": "lat", "city_lon": "lon"}, inplace=True)
else:
    city_data["lat"] = city_data["city"].map(lambda c: CITY_COORDS.get(c, (None, None))[0])
    city_data["lon"] = city_data["city"].map(lambda c: CITY_COORDS.get(c, (None, None))[1])
city_mapped = city_data.dropna(subset=["lat", "lon"]).copy()
city_unmapped = city_data[city_data["lat"].isna()]

# ---- 侧边栏 ----
with st.sidebar:
    st.subheader("🗺️ 视图")
    view_mode = st.radio("选择视图", ["📊 省份销售分布", "📍 城市气泡地图", "🧭 区域对比分析"])
    st.markdown("---")
    st.caption(f"覆盖 {len(prov_data)} 个省份 · {len(city_mapped)} 个城市有坐标")

# ---- KPI ----
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("覆盖省份", len(prov_data))
with col2:
    st.metric("覆盖城市", len(city_data))
with col3:
    top_prov = prov_data.iloc[0]
    st.metric("Top省份", top_prov["province"], f"¥{top_prov['sales']:,.0f}")
with col4:
    st.metric("省份均客单价", f"¥{prov_data['avg_order'].mean():,.0f}")

st.markdown("---")

# ================================================================
# 视图1: 省份销售分布
# ================================================================
if view_mode == "📊 省份销售分布":
    st.markdown("### 📊 各省份销售额分布")

    col_l, col_r = st.columns([3, 2])

    with col_l:
        st.markdown("#### 省份销售柱状图 (Top 16)")
        top16 = prov_data.head(16).sort_values("sales", ascending=True)
        fig = px.bar(top16, x="sales", y="province", orientation="h",
                     text=top16["sales"].apply(lambda x: f"¥{x/10000:.1f}万"),
                     color="sales", color_continuous_scale="Blues")
        fig.update_layout(**PLOTLY_TUFTE_LAYOUT)
        fig.update_layout(title="", yaxis_title="", xaxis_title="销售额 (元)",
                          showlegend=False, height=500)
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.markdown("#### 省份销售占比")
        fig = px.pie(prov_data.head(8), names="province", values="sales",
                     hole=0.4, color_discrete_sequence=TUFTE_COLORS)
        fig.update_layout(**PLOTLY_TUFTE_LAYOUT)
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), showlegend=True)
        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig, use_container_width=True)

    # 数据明细表
    st.markdown("---")
    st.markdown("#### 📋 省份数据明细 (按销售额降序)")
    display_df = prov_data.copy().reset_index(drop=True)
    display_df.index = range(1, len(display_df) + 1)
    display_df["销售额"] = display_df["sales"].apply(lambda x: f"¥{x:,.0f}")
    display_df["平均客单价"] = display_df["avg_order"].apply(lambda x: f"¥{x:,.0f}")
    st.dataframe(
        display_df[["province", "销售额", "orders", "customers", "平均客单价"]]
        .rename(columns={"province": "省份", "orders": "订单数", "customers": "客户数"}),
        use_container_width=True, height=400
    )

# ================================================================
# 视图2: 城市气泡地图
# ================================================================
elif view_mode == "📍 城市气泡地图":
    st.markdown("### 📍 城市级别销售分布")

    if len(city_unmapped) > 0:
        missing = ", ".join(city_unmapped["city"].tolist())
        st.warning(f"以下城市缺少坐标数据，未在地图显示：{missing}")

    col_map, col_chart = st.columns([3, 2])

    with col_map:
        st.markdown("#### 城市销售气泡地图 (Plotly ScatterGeo)")

        fig = px.scatter_geo(
            city_mapped, lat="lat", lon="lon",
            size="sales", color="sales",
            color_continuous_scale="Blues",
            hover_name="city",
            hover_data={"sales": ":,.0f", "orders": True, "customers": True, "lat": False, "lon": False},
            size_max=40,
            projection="natural earth",
            labels={"sales": "销售额", "orders": "订单数", "customers": "客户数"}
        )

        # 地图中心根据数据自动计算
        map_center = dict(lat=city_mapped["lat"].mean(), lon=city_mapped["lon"].mean())
        fig.update_geos(
            center=map_center,
            projection_scale=3,
            showland=True, landcolor="#F8F8F8",
            showcountries=True, countrycolor="#DDDDDD",
            coastlinecolor="#CCCCCC",
            showocean=True, oceancolor="#F0F8FF",
            fitbounds="locations",
        )
        fig.update_layout(**PLOTLY_TUFTE_LAYOUT)
        fig.update_layout(title="", height=550, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with col_chart:
        st.markdown("#### 🏙️ 城市 Top 15")
        top15 = city_mapped.sort_values("sales", ascending=True).tail(15)
        fig = px.bar(top15, x="sales", y="city", orientation="h",
                     text=top15["sales"].apply(lambda x: f"¥{x/10000:.1f}万"),
                     color="sales", color_continuous_scale="Blues")
        fig.update_layout(**PLOTLY_TUFTE_LAYOUT)
        fig.update_layout(title="", yaxis_title="", xaxis_title="销售额 (元)",
                          showlegend=False, height=500)
        st.plotly_chart(fig, use_container_width=True)

    # 城市销售 vs 订单量散点
    st.markdown("---")
    st.markdown("#### 城市销售额 vs 订单量 (气泡大小=客户数)")
    fig = px.scatter(city_mapped, x="orders", y="sales", size="customers",
                      text="city", color="sales", color_continuous_scale="Blues",
                      hover_name="city",
                      labels={"orders": "订单数", "sales": "销售额 (元)", "customers": "客户数"})
    fig.update_layout(**PLOTLY_TUFTE_LAYOUT)
    fig.update_layout(title="", height=450)
    fig.update_traces(textposition="top center", textfont_size=10)
    st.plotly_chart(fig, use_container_width=True)

# ================================================================
# 视图3: 区域对比分析
# ================================================================
else:
    st.markdown("### 🧭 区域对比分析")

    # 区域映射
    prov_region_map = customers[["province", "region"]].drop_duplicates()
    region_data = valid.merge(prov_region_map, on="province")
    region_agg = region_data.groupby("region").agg(
        sales=("total_amount", "sum"),
        orders=("order_id", "nunique"),
        customers=("customer_id", "nunique"),
        provinces=("province", "nunique"),
    ).reset_index()
    region_agg["avg_order"] = round(region_agg["sales"] / region_agg["orders"], 0)

    col_a, col_b = st.columns([3, 2])

    with col_a:
        st.markdown("#### 区域销售额分布")
        fig = px.treemap(region_agg, path=["region"], values="sales",
                          color="sales", color_continuous_scale="Blues",
                          hover_data={"orders": True, "avg_order": True})
        fig.update_layout(**PLOTLY_TUFTE_LAYOUT)
        fig.update_layout(title="", height=400)
        fig.update_traces(texttemplate="%{label}<br>¥%{value:,.0f}")
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.markdown("#### 区域核心指标")
        for _, row in region_agg.iterrows():
            pct = row["sales"] / region_agg["sales"].sum() * 100
            st.metric(
                f"🔹 {row['region']}",
                f"¥{row['sales']:,.0f}",
                f"占比 {pct:.1f}% | {row['orders']}单 | {row['customers']}客户"
            )

    st.markdown("---")

    # 区域 x 品类热力图
    st.markdown("#### 区域 × 品类 交叉热力图")
    region_cat = region_data.merge(products[["product_id", "category"]], on="product_id")
    heat_data = region_cat.groupby(["region", "category"])["total_amount"].sum().unstack(fill_value=0)

    fig = px.imshow(heat_data.values, x=heat_data.columns, y=heat_data.index,
                    color_continuous_scale="YlOrRd", text_auto=".0f", aspect="auto",
                    labels={"x": "品类", "y": "区域", "color": "销售额"})
    fig.update_layout(**PLOTLY_TUFTE_LAYOUT)
    fig.update_layout(title="", height=300)
    st.plotly_chart(fig, use_container_width=True)

    # 省份散点
    st.markdown("---")
    st.markdown("#### 省份销售额 vs 订单量")
    fig = px.scatter(prov_data, x="orders", y="sales", size="customers",
                      text="province", color="sales", color_continuous_scale="Blues",
                      labels={"orders": "订单数", "sales": "销售额 (元)", "customers": "客户数"})
    fig.update_layout(**PLOTLY_TUFTE_LAYOUT)
    fig.update_layout(title="")
    fig.update_traces(textposition="top center")
    st.plotly_chart(fig, use_container_width=True)

    # 区域汇总表
    st.markdown("---")
    st.markdown("#### 📋 区域数据汇总")
    summary = region_agg.copy()
    summary["销售额"] = summary["sales"].apply(lambda x: f"¥{x:,.0f}")
    summary["占比"] = (summary["sales"] / summary["sales"].sum() * 100).apply(lambda x: f"{x:.1f}%")
    summary["客单价"] = summary["avg_order"].apply(lambda x: f"¥{x:,.0f}")
    st.dataframe(
        summary[["region", "销售额", "占比", "orders", "customers", "客单价", "provinces"]]
        .rename(columns={"region": "区域", "orders": "订单数", "customers": "客户数", "provinces": "省份数"}),
        use_container_width=True, hide_index=True
    )

st.markdown("---")
st.caption("地理空间分析完成 · 省份 + 城市 + 区域多维度钻取 · 基于 Plotly 构建")
