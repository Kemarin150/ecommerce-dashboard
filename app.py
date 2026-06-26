"""电商BI看板 - 概览仪表板"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import load_data, filter_by_date, compute_kpis, kpi_card
from utils import tufte_bar, tufte_line, tufte_pie, TUFTE_COLORS, PLOTLY_TUFTE_LAYOUT
from utils import parse_uploaded_file, get_data_source, auto_map_uploaded_data, get_valid_orders

st.set_page_config(page_title="电商BI看板", page_icon="📊", layout="wide")

# ---- Sidebar: 数据上传 ----
with st.sidebar:
    st.image("https://img.icons8.com/color/96/shopping-cart--v1.png", width=64)
    st.title("电商BI看板")

    st.markdown("---")
    with st.expander("📂 上传自定义数据", expanded=False):
        st.caption("上传 CSV 文件替换内置模拟数据")
        orders_file = st.file_uploader("订单表 (orders.csv)", type="csv", key="upload_orders")
        products_file = st.file_uploader("产品表 (products.csv)", type="csv", key="upload_products")
        customers_file = st.file_uploader("客户表 (customers.csv)", type="csv", key="upload_customers")

        if st.button("🔄 加载上传数据", use_container_width=True):
            if orders_file or products_file or customers_file:
                o = parse_uploaded_file(orders_file, "订单表") if orders_file else None
                p = parse_uploaded_file(products_file, "产品表") if products_file else None
                c = parse_uploaded_file(customers_file, "客户表") if customers_file else None
                if o is not None and p is not None and c is not None:
                    o, p, c, mapping_log = auto_map_uploaded_data(o, p, c)
                    st.session_state["uploaded_data"] = {"orders": o, "products": p, "customers": c}
                    st.session_state["mapping_log"] = mapping_log
                else:
                    st.session_state["uploaded_data"] = {"orders": None, "products": None, "customers": None}
                    st.session_state["mapping_log"] = None
                st.rerun()
            else:
                st.warning("请先上传文件")

        if st.button("🔄 恢复默认数据", use_container_width=True):
            st.session_state["uploaded_data"] = None
            st.rerun()

    st.markdown("---")

# ---- 加载数据 ----
orders, products, customers = load_data()

# ---- Sidebar: 筛选器 ----
with st.sidebar:
    st.subheader("🔍 数据筛选")

    date_min = orders["date"].min().date()
    date_max = orders["date"].max().date()
    date_range = st.date_input("日期范围", value=(date_min, date_max),
                                min_value=date_min, max_value=date_max)

    cats = sorted(products["category"].dropna().astype(str).unique().tolist())
    categories = ["全部"] + cats
    selected_cat = st.selectbox("产品品类", categories)

    st.markdown("---")
    source = get_data_source()
    st.caption(f"📦 数据来源: {source}")
    st.caption(f"📅 {date_min} ~ {date_max}")
    st.caption(f"📋 订单: {len(orders):,} | 产品: {len(products)} | 客户: {len(customers)}")

    # 显示列名映射日志
    mapping_log = st.session_state.get("mapping_log", None)
    if mapping_log:
        with st.expander("🔍 列名映射详情"):
            st.markdown(mapping_log)
            st.caption("系统自动识别上传文件中的列名并映射到看板所需格式。未匹配的列已自动填充默认值。")

# ---- 数据筛选 ----
if len(date_range) == 2:
    orders_f = filter_by_date(orders, date_range[0], date_range[1])
else:
    orders_f = orders.copy()

if selected_cat != "全部":
    cat_pids = products[products["category"] == selected_cat]["product_id"].tolist()
    orders_f = orders_f[orders_f["product_id"].isin(cat_pids)]

valid_orders = get_valid_orders(orders_f)
kpis = compute_kpis(valid_orders)

# ---- 页面标题 ----
st.title("📊 电商销售数据多维分析平台")
st.markdown("基于 Tufte 可视化原则的交互式 BI 看板 — 请使用左侧筛选器探索数据")

# ---- KPI 卡片 ----
st.markdown("### 📌 核心指标")
col1, col2, col3, col4 = st.columns(4)
delta_sales = None
if selected_cat == "全部":
    prev_orders = valid_orders[valid_orders["date"] < valid_orders["date"].max() - pd.Timedelta(days=30)]
    if len(prev_orders) > 0:
        prev_sales = prev_orders["total_amount"].sum()
        cur_sales = valid_orders[valid_orders["date"] >= valid_orders["date"].max() - pd.Timedelta(days=30)]["total_amount"].sum()
        if prev_sales > 0:
            delta_sales = f"{(cur_sales/prev_sales - 1)*100:.1f}% vs 上月"

with col1:
    kpi_card("总销售额 (元)", kpis["total_sales"], prefix="¥", delta=delta_sales)
with col2:
    kpi_card("总订单数", kpis["total_orders"], delta=delta_sales)
with col3:
    kpi_card("平均客单价 (元)", kpis["avg_order_value"], prefix="¥")
with col4:
    kpi_card("活跃客户数", kpis["active_customers"])

st.markdown("---")

row1_left, row1_right = st.columns([3, 2])

with row1_left:
    st.markdown("#### 📈 月度销售额趋势")
    monthly = valid_orders.groupby(pd.Grouper(key="date", freq="ME"))["total_amount"].sum().reset_index()
    monthly["year"] = monthly["date"].dt.year
    monthly["month"] = monthly["date"].dt.month

    fig = go.Figure()
    for yr in sorted(monthly["year"].unique()):
        d = monthly[monthly["year"] == yr]
        fig.add_trace(go.Scatter(x=d["month"], y=d["total_amount"], mode="lines+markers",
                                  name=str(yr), line=dict(width=2.5)))
    fig.update_layout(**PLOTLY_TUFTE_LAYOUT)
    fig.update_layout(title="",
                       xaxis=dict(tickmode="array", tickvals=list(range(1, 13)),
                                   ticktext=["1月","2月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"]),
                       yaxis=dict(title="销售额 (元)"),
                       legend_title="年份")
    st.plotly_chart(fig, use_container_width=True)

with row1_right:
    if selected_cat == "全部":
        st.markdown("#### 🍩 品类销售占比")
        cat_sales = valid_orders.merge(products[["product_id", "category"]], on="product_id")
        cat_pie = cat_sales.groupby("category")["total_amount"].sum().reset_index()
        fig = tufte_pie(cat_pie, "category", "total_amount", title="", hole=0.5)
    else:
        st.markdown(f"#### 🍩 {selected_cat} — 子类别占比")
        sub_sales = valid_orders.merge(products[["product_id", "subcategory"]], on="product_id")
        sub_pie = sub_sales.groupby("subcategory")["total_amount"].sum().reset_index()
        fig = tufte_pie(sub_pie, "subcategory", "total_amount", title="", hole=0.5)
    st.plotly_chart(fig, use_container_width=True)

row2_left, row2_right = st.columns([3, 2])

with row2_left:
    st.markdown("#### 🏆 Top 10 产品销售额")
    prod_sales = valid_orders.merge(products[["product_id", "name"]], on="product_id")
    top10 = prod_sales.groupby("name")["total_amount"].sum().sort_values(ascending=True).tail(10).reset_index()
    fig = tufte_bar(top10, y="name", x="total_amount", title="", orientation="h")
    fig.update_layout(yaxis_title="", xaxis_title="销售额 (元)", showlegend=False, height=350)
    st.plotly_chart(fig, use_container_width=True)

with row2_right:
    st.markdown("#### 🗺️ 省份销售热力")

    # 中国省份中心坐标（内置数据用）
    PROVINCE_COORDS = {
        "北京": (39.90, 116.40), "上海": (31.23, 121.47),
        "广东": (23.13, 113.26), "浙江": (30.27, 120.15),
        "江苏": (32.06, 118.80), "四川": (30.57, 104.07),
        "湖北": (30.59, 114.31), "山东": (36.65, 116.99),
        "福建": (26.07, 119.30), "河南": (34.75, 113.63),
        "湖南": (28.23, 112.94), "重庆": (29.43, 106.91),
        "陕西": (34.34, 108.94), "辽宁": (41.81, 123.43),
        "安徽": (31.82, 117.23),
    }

    prov_sales = valid_orders.groupby("province")["total_amount"].sum().reset_index()
    prov_sales.columns = ["province", "sales"]

    # 优先用数据自带的经纬度列（上传数据），否则用内置坐标
    if "province_lat" in valid_orders.columns and "province_lon" in valid_orders.columns:
        coords = valid_orders[["province", "province_lat", "province_lon"]].drop_duplicates()
        prov_sales = prov_sales.merge(coords, on="province", how="left")
        prov_sales.rename(columns={"province_lat": "lat", "province_lon": "lon"}, inplace=True)
    else:
        prov_sales["lat"] = prov_sales["province"].map(lambda p: PROVINCE_COORDS.get(p, (None, None))[0])
        prov_sales["lon"] = prov_sales["province"].map(lambda p: PROVINCE_COORDS.get(p, (None, None))[1])

    has_coords = prov_sales["lat"].notna().any()
    if has_coords:
        map_center = dict(lat=prov_sales["lat"].mean(), lon=prov_sales["lon"].mean())
        fig = px.scatter_geo(
            prov_sales, lat="lat", lon="lon",
            size="sales", color="sales",
            color_continuous_scale="Blues",
            hover_name="province",
            hover_data={"sales": ":,.0f", "lat": False, "lon": False},
            size_max=35,
            projection="natural earth",
        )
        fig.update_geos(
            center=map_center,
            projection_scale=3.5,
            showland=True, landcolor="#F8F8F8",
            showcountries=True, countrycolor="#DDDDDD",
            coastlinecolor="#CCCCCC",
            showocean=True, oceancolor="#F0F8FF",
            fitbounds="locations",
        )
        fig.update_layout(**PLOTLY_TUFTE_LAYOUT)
        fig.update_layout(title="", height=350, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("暂无省份坐标数据，以下为销售额排名")
        fig = tufte_bar(prov_sales.sort_values("sales", ascending=True).tail(10),
                         y="province", x="sales", title="", orientation="h")
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

# ---- 第三行: 近30天趋势 + 客户概览 ----
row3_left, row3_right = st.columns([3, 2])

with row3_left:
    st.markdown("#### 📅 近30天日销售额趋势")
    recent30 = valid_orders[valid_orders["date"] >= valid_orders["date"].max() - pd.Timedelta(days=30)]
    daily30 = recent30.groupby("date")["total_amount"].sum().reset_index()
    daily30["ma7"] = daily30["total_amount"].rolling(7, min_periods=1).mean()

    fig = go.Figure()
    fig.add_trace(go.Bar(x=daily30["date"], y=daily30["total_amount"], name="日销售额",
                          marker_color=TUFTE_COLORS[0], opacity=0.7))
    fig.add_trace(go.Scatter(x=daily30["date"], y=daily30["ma7"], name="7日均线",
                              line=dict(color=TUFTE_COLORS[1], width=2.5)))
    fig.update_layout(**PLOTLY_TUFTE_LAYOUT)
    fig.update_layout(title="", yaxis_title="销售额 (元)",
                       xaxis_title="", hovermode="x")
    st.plotly_chart(fig, use_container_width=True)

with row3_right:
    st.markdown("#### 🏷️ 订单状态分布")
    status_cnt = valid_orders.groupby("status")["order_id"].count().reset_index()
    status_cnt.columns = ["status", "count"]
    status_colors = {s: c for s, c in zip(valid_orders["status"].unique(), TUFTE_COLORS)}
    fig = px.pie(status_cnt, names="status", values="count", title="", hole=0.5,
                 color="status", color_discrete_map=status_colors)
    fig.update_layout(**PLOTLY_TUFTE_LAYOUT)
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption("电商BI看板 · 期末大作业 · 基于 Streamlit + Plotly 构建 · 遵循 Tufte 可视化原则")
