import dash
import pandas as pd
from dash import Dash, html, dcc, callback, Output, Input
import plotly.express as px
from datetime import datetime, timedelta
from db import get_connection
import os
import google.generativeai as genai


dash.register_page(__name__, path="/cr")

app = Dash()

conn = get_connection()
df = pd.read_sql("SELECT * FROM cr_report", conn)
df = df[
    df["Owner Work Group Name"].isin(["IT Support (ALC)", "IT Support (EVSM)"])
].reset_index(drop=True)
PENDING_STATUSES = [
    "In Progress", "Requested", "Approved", "Pre-Migration Approved",
    "Pre-Migration Approved 1", "Migration date finalized",
    "Pending Further Review", "UAT Approved", "Draft", "Approved by Owner"
]

# ── Pre-compute global KPIs ───────────────────────────────────────────────────
total_pending    = int((df["Status"].isin(PENDING_STATUSES)).sum())
total_resolved   = int((df["Status"].isin(["Implementation Review Closed", "Closed", "Implemented"])).sum())
critical_priority = int((df["Priority"] == "High").sum())

pending_df = df[df["Status"].isin(PENDING_STATUSES)].copy()
pending_df["age_days"] = (datetime.now() - pd.to_datetime(pending_df["Request Registration Time"], errors="coerce")).dt.days
avg_aging = round(pending_df["age_days"].mean(), 1)

# age_days on full df for detail panel
df["age_days"] = (datetime.now() - pd.to_datetime(df["Request Registration Time"], errors="coerce")).dt.days

bins   = [0, 5, 10, 15, 30, float("inf")]
labels = ["0-5", "6-10", "11-15", "16-30", ">30"]
pending_df["age_bucket"] = pd.cut(pending_df["age_days"], bins=bins, labels=labels)

# ── Static charts (no filter dependency) ─────────────────────────────────────
fig_aging = px.bar(
    pending_df["age_bucket"].value_counts().sort_index().reset_index(),
    x="age_bucket", y="count",
)
fig_aging.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), xaxis_title="", yaxis_title="")

fig_workgroup = px.bar(
    df["Owner Work Group Name"].value_counts().reset_index(),
    x="Owner Work Group Name", y="count",
)
fig_workgroup.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), xaxis_title="", yaxis_title="")

fig_status = px.pie(
    df["Status"].value_counts().reset_index(),
    names="Status", values="count",
)

# ── Filter option helpers ─────────────────────────────────────────────────────
def make_opts(series):
    vals = sorted([v for v in series.dropna().unique() if str(v).strip()])
    return [{"label": v, "value": v} for v in vals]

status_opts        = make_opts(df["Status"])
priority_opts      = make_opts(df["Priority"])
risk_opts          = make_opts(df["Risk"])
change_type_opts   = make_opts(df["Change Type Name"])
category_opts      = make_opts(df["Category"])
workgroup_opts     = make_opts(df["Owner Work Group Name"])
change_cat_opts    = make_opts(df["Change Category Name"])

# ── Styling helpers ───────────────────────────────────────────────────────────
CARD  = {"background": "white", "border": "1px solid #e0e0e0", "borderRadius": "8px", "padding": "16px"}
LABEL = {"fontSize": "11px", "color": "#888", "marginBottom": "6px",
         "textTransform": "uppercase", "letterSpacing": "0.05em", "fontWeight": "600"}
DD    = {"fontSize": "13px"}

def filter_label(text):
    return html.Div(text, style=LABEL)

def kpi_card(label, value, delta):
    return html.Div([
        html.Div(label, style={"fontSize": "11px", "color": "#888", "marginBottom": "8px"}),
        html.Div(str(value), style={"fontSize": "32px", "fontWeight": "800", "marginBottom": "8px"}),
        html.Div(delta, style={"fontSize": "12px", "color": "#888"}),
    ], style={"flex": "1", "padding": "24px", **CARD})

def detail_badge(label, value, color="#1A1A2E"):
    return html.Div([
        html.Div(label, style={**LABEL, "marginBottom": "4px"}),
        html.Div(str(value) if pd.notna(value) and str(value).strip() else "—",
                 style={"fontSize": "14px", "fontWeight": "600", "color": color}),
    ], style={"background": "#F8F8F8", "border": "1px solid #e0e0e0",
              "borderRadius": "6px", "padding": "10px 14px", "minWidth": "140px"})

@callback(
    Output("ai-insights-output-cr", "children"),
    Input("insights-range-cr", "value"),
)

def update_insights(weeks):
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM cr_report", conn)
    conn.close()
    
    # Filter by selected weeks
    cutoff = datetime.now() - timedelta(weeks=weeks)
    filtered_df = df[pd.to_datetime(df["Request Registration Time"]) >= cutoff]
    
    # Process filtered_df and send to AI
    
    return html.Div("insights will show here")

# ── Layout ────────────────────────────────────────────────────────────────────
def layout():
    return html.Div([

        # Top bar
        html.Div([
            html.Span("Dashboards / Change Requests"),
            html.Div([
                html.Span("🔔", style={"padding": "12px 20px"}),
                html.Span("👤", style={"padding": "12px 20px"}),
            ]),
        ], style={
            "display": "flex", "justifyContent": "space-between", "alignItems": "center",
            "padding": "16px 24px", "borderBottom": "1px solid #e0e0e0", "background": "#F3F3F3",
        }),

        html.H1("Change Request (CR) Overview", style={"padding": "12px 20px", "marginBottom": "0px"}),

        # KPI cards
        html.Div([
            kpi_card("TOTAL PENDING",    total_pending,    "Active in pipeline"),
            kpi_card("TOTAL RESOLVED",   total_resolved,   "Closed successfully"),
            kpi_card("AVG AGING",        f"{avg_aging} Days", "Pending CRs only"),
            kpi_card("CRITICAL PRIORITY",critical_priority,"High priority CRs"),
        ], style={"display": "flex", "gap": "16px", "padding": "24px"}),

        # Charts
        html.Div([
            html.Div([
                html.Div([
                    html.Div("CRs by Workgroup", style={"fontWeight": "600", "marginBottom": "12px"}),
                    dcc.Graph(figure=fig_workgroup),
                ], style={"flex": "1", **CARD}),
                html.Div([
                    html.Div("Status Distribution", style={"fontWeight": "600", "marginBottom": "12px"}),
                    dcc.Graph(figure=fig_status),
                ], style={"flex": "1", **CARD}),
            ], style={"display": "flex", "gap": "16px", "marginBottom": "16px"}),

            html.Div([
                html.Div("CR Aging Distribution", style={"fontWeight": "600", "marginBottom": "12px"}),
                dcc.Graph(figure=fig_aging, config={"displayModeBar": False}),
            ], style={**CARD}),
        ], style={"padding": "0 24px"}),

        html.Div([
            html.Div([
                html.Div("AI Insights", style={"fontWeight": "600", "marginBottom": "12px"}),
                    dcc.Dropdown(
                        id="insights-range-cr",
                        options=[
                            {"label": "1 Week", "value": 1},
                            {"label": "2 Weeks", "value": 2},
                            {"label": "3 Weeks", "value": 3},
                            {"label": "4 Weeks", "value": 4},
                        ],
                        value=1,
                        clearable=False,
                        style={"width": "200px", "marginBottom": "16px"},
                    ),
                    # Insights output
                    html.Div(
                        id="ai-insights-output-cr",
                        children="Select a time range to generate insights.",
                    ),
                ],
                style={
                    "margin": "24px",
                    "padding": "16px",
                    "background": "white",
                    "border": "1px solid #e0e0e0",
                    "borderRadius": "8px",
                },
            ),

        ], style={"padding": "0 24px", "marginBottom": "40px"}),  
    ])
