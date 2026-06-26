import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from io import StringIO

DATA_DIR = Path(__file__).parent / "data"

TUFTE_COLORS = ["#2B3E50", "#E74C3C", "#3498DB", "#27AE60", "#F39C12",
                "#9B59B6", "#1ABC9C", "#E67E22", "#95A5A6", "#34495E"]

TUFTE_CATEGORICAL = {
    "电子产品": "#3498DB", "服装鞋帽": "#E74C3C", "食品饮料": "#27AE60",
    "家居用品": "#F39C12", "运动户外": "#9B59B6",
}

PLOTLY_TUFTE_LAYOUT = dict(
    font=dict(family="Microsoft YaHei, SimHei, sans-serif", size=12, color="#2B3E50"),
    paper_bgcolor="white",
    plot_bgcolor="white",
    colorway=TUFTE_COLORS,
)

MARGIN_DEFAULT = dict(l=40, r=20, t=50, b=40)
AXIS_DEFAULTS = dict(gridcolor="#EEEEEE", zeroline=False, linecolor="#CCCCCC")

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "figure.facecolor": "white",
})


# ---- 列名动态映射 ----
# 每个目标列对应一组可能出现在上传文件中的别名（大小写不敏感，模糊匹配）
COLUMN_ALIASES = {
    # 订单表
    "date":         ["date", "order_date", "order_purchase_timestamp", "purchase_date",
                     "下单时间", "订单日期", "日期", "时间", "purchase_time", "created_at"],
    "province":     ["province", "state", "prov", "省份", "省", "customer_state",
                     "shipping_state", "region"],
    "city":         ["city", "城市", "customer_city", "shipping_city", "town"],
    "total_amount": ["total_amount", "amount", "total", "price", "payment_value",
                     "销售额", "金额", "总价", "total_price", "order_amount"],
    "product_id":   ["product_id", "product", "sku", "item_id", "商品编号", "产品id",
                     "product_code", "asin"],
    "status":       ["status", "order_status", "状态", "订单状态", "state"],
    "customer_id":  ["customer_id", "customer", "user_id", "buyer_id", "客户编号",
                     "用户id", "customer_unique_id"],
    "quantity":     ["quantity", "qty", "数量", "count", "amount"],
    "unit_price":   ["unit_price", "price", "单价", "售价", "item_price", "sales_price"],
    "payment_method": ["payment_method", "payment_type", "支付方式", "付款方式",
                       "payment", "pay_type"],
    # 产品表
    "category":     ["category", "product_category", "品类", "类别", "分类",
                     "product_category_name", "category_name", "cate"],
    "name":         ["name", "product_name", "商品名", "产品名", "产品名称", "title",
                     "product_title", "description"],
    "subcategory":  ["subcategory", "sub_category", "子类", "子类别", "sub_cate"],
    "unit_cost":    ["unit_cost", "cost", "成本", "cost_price", "purchase_price"],
    # 客户表
    "registration_date": ["registration_date", "register_date", "注册日期", "注册时间",
                          "signup_date", "created_date", "join_date"],
    "age_group":    ["age_group", "age", "年龄段", "年龄", "age_range"],
    "gender":       ["gender", "sex", "性别", "sexuality"],
    "segment":      ["segment", "会员", "等级", "tier", "membership", "vip_level", "level"],
    "region":       ["region", "区域", "大区", "area", "district"],
    # 地理坐标列（上传数据若自带经纬度可自动识别）
    "province_lat": ["province_lat", "province_latitude", "state_lat", "state_latitude"],
    "province_lon": ["province_lon", "province_longitude", "province_lng",
                     "state_lon", "state_lng", "state_longitude"],
    "city_lat":     ["city_lat", "city_latitude", "town_lat", "town_latitude"],
    "city_lon":     ["city_lon", "city_longitude", "city_lng", "town_lon", "town_lng"],
}


def _normalize_col(col_name: str) -> str:
    """去除下划线、空格、大小写差异，用于模糊匹配"""
    return col_name.strip().lower().replace("_", "").replace(" ", "")


def _find_column(df, target):
    """在 DataFrame 中查找匹配 target 的列，返回原列名或 None"""
    if target in df.columns:
        return target
    aliases = COLUMN_ALIASES.get(target, [target])
    norm_map = {_normalize_col(c): c for c in df.columns}
    for alias in aliases:
        key = _normalize_col(alias)
        if key in norm_map:
            return norm_map[key]
    return None


def _map_columns(df, targets, label=""):
    """将 DataFrame 的列映射到目标列名，返回 (mapped_df, mapping_log)"""
    used_sources = set()   # 已被占用的源列
    rename_map = {}
    log = []
    for target in targets:
        found = _find_column(df, target)
        if found and found in used_sources:
            # 同一源列匹配多个目标 — 直接复制值，后续 _auto_fill_missing 可再调整
            df[target] = df[found]
            log.append(f"  {target} (复用 {found}，已复制值)")
            continue
        if found and found != target:
            rename_map[found] = target
            used_sources.add(found)
            log.append(f"  {found} -> {target}")
        elif found == target:
            used_sources.add(found)
            log.append(f"  {target} (精确匹配)")
        else:
            log.append(f"  {target} (未找到，将自动生成)")
    if rename_map:
        df = df.rename(columns=rename_map)
    return df, log


def get_valid_orders(orders):
    """排除已取消/已退货的订单，返回有效订单。适配任意数据集的状态值。"""
    if "status" not in orders.columns:
        return orders
    cancelled = {"已取消", "已退货", "canceled", "cancelled", "returned", "refunded"}
    mask = ~orders["status"].astype(str).str.strip().str.lower().isin(
        {c.lower() for c in cancelled}
    )
    return orders[mask]



def _auto_fill_missing(df, targets):
    """为缺失的必要列自动填充默认值"""
    if "date" in targets and "date" not in df.columns:
        df["date"] = pd.Timestamp("2023-01-01")
    if "total_amount" in targets and "total_amount" not in df.columns:
        # 尝试 quantity * unit_price
        if "quantity" in df.columns and "unit_price" in df.columns:
            df["total_amount"] = df["quantity"] * df["unit_price"]
        else:
            df["total_amount"] = 0
    if "quantity" in targets and "quantity" not in df.columns:
        df["quantity"] = 1
    if "unit_price" in targets and "unit_price" not in df.columns and "total_amount" in df.columns:
        df["unit_price"] = df["total_amount"] / df.get("quantity", 1)
    if "status" in targets and "status" not in df.columns:
        df["status"] = "已完成"
    if "payment_method" in targets and "payment_method" not in df.columns:
        df["payment_method"] = "其他"
    if "unit_cost" in targets and "unit_cost" not in df.columns and "unit_price" in df.columns:
        df["unit_cost"] = (df["unit_price"] * 0.5).round(2)
    if "subcategory" in targets and "subcategory" not in df.columns and "category" in df.columns:
        df["subcategory"] = df["category"]
    if "name" in targets and "name" not in df.columns:
        if "product_id" in df.columns:
            df["name"] = df["product_id"]
        elif "category" in df.columns:
            df["name"] = df["category"]
        else:
            df["name"] = "未知产品"
    if "registration_date" in targets and "registration_date" not in df.columns:
        df["registration_date"] = pd.Timestamp("2022-01-01")
    if "age_group" in targets and "age_group" not in df.columns:
        df["age_group"] = "未知"
    if "gender" in targets and "gender" not in df.columns:
        df["gender"] = "未知"
    if "segment" in targets and "segment" not in df.columns:
        df["segment"] = "普通会员"
    if "region" in targets and "region" not in df.columns and "province" in df.columns:
        df["region"] = "其他"
    return df


STATUS_TRANSLATE = {
    "delivered": "已完成", "shipped": "已完成", "approved": "已完成",
    "invoiced": "已完成", "processing": "已完成",
    "canceled": "已取消", "unavailable": "已取消", "created": "已取消",
    "returned": "已退货", "refunded": "已退货",
}


def _parse_dates(df):
    """自动检测并转换日期列"""
    for col in df.columns:
        if "date" in _normalize_col(col) or "时间" in col or "日期" in col:
            try:
                df[col] = pd.to_datetime(df[col])
            except Exception:
                pass


def _translate_status(df):
    """将英文/其它语言订单状态统一翻译为中文"""
    if "status" not in df.columns:
        return df
    df["status"] = df["status"].astype(str).str.strip().str.lower()
    df["status"] = df["status"].map(STATUS_TRANSLATE).fillna(df["status"])
    return df


def load_data():
    """加载数据：优先使用上传文件，否则使用本地生成的模拟数据"""
    uploaded = st.session_state.get("uploaded_data", None)
    if uploaded is not None:
        orders = uploaded.get("orders")
        products = uploaded.get("products")
        customers = uploaded.get("customers")
        if all(v is not None for v in [orders, products, customers]):
            return orders, products, customers

    # 回退到本地 CSV 文件
    orders = pd.read_csv(DATA_DIR / "orders.csv", parse_dates=["date"])
    products = pd.read_csv(DATA_DIR / "products.csv")
    customers = pd.read_csv(DATA_DIR / "customers.csv", parse_dates=["registration_date"])
    return orders, products, customers


def parse_uploaded_file(uploaded_file, name_hint=""):
    """解析上传的 CSV 文件，自动识别并映射列名"""
    if uploaded_file is None:
        return None
    try:
        raw = uploaded_file.getvalue().decode("utf-8-sig")
        df = pd.read_csv(StringIO(raw))
        if df.empty:
            st.error(f"{name_hint}: 文件为空")
            return None
        return df
    except Exception as e:
        st.error(f"解析文件失败 ({name_hint}): {e}")
        return None


def auto_map_uploaded_data(orders, products, customers):
    """对上传的三张表进行列名自动映射和缺失列填充"""
    o_targets = ["date", "province", "city", "total_amount", "product_id",
                 "customer_id", "status", "quantity", "unit_price", "payment_method"]
    p_targets = ["product_id", "category", "name", "subcategory", "unit_cost", "unit_price"]
    c_targets = ["customer_id", "province", "city", "region", "registration_date",
                 "age_group", "gender", "segment", "name"]

    o_mapped, o_log = _map_columns(orders, o_targets, "orders")
    p_mapped, p_log = _map_columns(products, p_targets, "products")
    c_mapped, c_log = _map_columns(customers, c_targets, "customers")

    o_mapped = _auto_fill_missing(o_mapped, o_targets)
    p_mapped = _auto_fill_missing(p_mapped, p_targets)
    c_mapped = _auto_fill_missing(c_mapped, c_targets)

    full_log = ["**列名映射结果:**"]
    full_log.append("\n*订单表:*")
    full_log.extend(o_log)
    full_log.append("\n*产品表:*")
    full_log.extend(p_log)
    full_log.append("\n*客户表:*")
    full_log.extend(c_log)

    # 从客户表向订单表补充缺失的地址列
    if any(col not in o_mapped.columns for col in ["province", "city"]):
        if "customer_id" in c_mapped.columns and "customer_id" in o_mapped.columns:
            addr_cols = []
            for ac in ["province", "city", "region"]:
                if ac in c_mapped.columns and ac not in o_mapped.columns:
                    addr_cols.append(ac)
            if addr_cols:
                addr_map = c_mapped[["customer_id"] + addr_cols].drop_duplicates("customer_id")
                o_mapped = o_mapped.merge(addr_map, on="customer_id", how="left", suffixes=("", "_c"))
                for ac in addr_cols:
                    if ac + "_c" in o_mapped.columns:
                        o_mapped[ac] = o_mapped[ac + "_c"].fillna(o_mapped[ac])
                        o_mapped.drop(columns=[ac + "_c"], inplace=True)
                full_log.append("\n*跨表补充:* 从客户表向订单表合并了 " + ", ".join(addr_cols))

    _translate_status(o_mapped)
    _parse_dates(o_mapped)
    _parse_dates(c_mapped)

    return o_mapped, p_mapped, c_mapped, "\n".join(full_log)


def get_data_source():

    if st.session_state.get("uploaded_data"):
        return "用户上传"
    return "内置模拟数据 (2023-2024 电商交易)"


def filter_by_date(orders, start_date, end_date):

    mask = (orders["date"] >= pd.Timestamp(start_date)) & (orders["date"] <= pd.Timestamp(end_date))
    return orders[mask]


def compute_kpis(orders):

    total_sales = orders["total_amount"].sum()
    total_orders = orders["order_id"].nunique()
    avg_order_value = total_sales / total_orders if total_orders > 0 else 0
    active_cust = get_valid_orders(orders)["customer_id"].nunique()
    return {
        "total_sales": total_sales,
        "total_orders": total_orders,
        "avg_order_value": avg_order_value,
        "active_customers": active_cust,
    }


def kpi_card(title, value, prefix="", suffix="", delta=None, delta_color="normal"):

    formatted = f"{prefix}{value:,.2f}{suffix}" if isinstance(value, (int, float)) else f"{prefix}{value}{suffix}"
    st.metric(label=title, value=formatted, delta=delta, delta_color=delta_color)


def tufte_bar(data, x, y, title="", color=None, horizontal=False, **kwargs):

    if horizontal:
        fig = px.bar(data, x=y, y=x, title=title, color=color,
                      color_discrete_sequence=TUFTE_COLORS, **kwargs)
    else:
        fig = px.bar(data, x=x, y=y, title=title, color=color,
                      color_discrete_sequence=TUFTE_COLORS, **kwargs)
    fig.update_layout(**PLOTLY_TUFTE_LAYOUT)
    fig.update_traces(marker_line_width=0)
    return fig


def tufte_line(data, x, y, title="", color=None, **kwargs):

    fig = px.line(data, x=x, y=y, title=title, color=color,
                  color_discrete_sequence=TUFTE_COLORS, **kwargs)
    fig.update_layout(**PLOTLY_TUFTE_LAYOUT)
    fig.update_traces(line_width=2)
    return fig


def tufte_pie(data, names, values, title="", hole=0.45, **kwargs):

    fig = px.pie(data, names=names, values=values, title=title, hole=hole,
                 color_discrete_sequence=TUFTE_COLORS, **kwargs)
    fig.update_layout(**PLOTLY_TUFTE_LAYOUT)
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return fig


def empty_chart_placeholder(message="请选择筛选条件后查看图表"):
    st.info(f"📋 {message}")
