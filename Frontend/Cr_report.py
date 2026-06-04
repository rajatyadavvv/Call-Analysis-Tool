import dash
import pandas as pd
from dash import Dash, html, dcc, callback, Output, Input
import plotly.express as px
from datetime import datetime
from db import get_connection

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

        # ── CR Detail Lookup ─────────────────────────────────────────────────
        html.Div([
            html.Div("CR Detail Lookup", style={"fontWeight": "700", "fontSize": "16px", "marginBottom": "16px"}),

            # Filter row 1 — dropdowns
            html.Div([
                html.Div([
                    filter_label("Status"),
                    dcc.Dropdown(id="f-status", options=status_opts, multi=True,
                                 placeholder="All statuses", style=DD),
                ], style={"flex": "1"}),
                html.Div([
                    filter_label("Priority"),
                    dcc.Dropdown(id="f-priority", options=priority_opts, multi=True,
                                 placeholder="All priorities", style=DD),
                ], style={"flex": "1"}),
                html.Div([
                    filter_label("Risk"),
                    dcc.Dropdown(id="f-risk", options=risk_opts, multi=True,
                                 placeholder="All risks", style=DD),
                ], style={"flex": "1"}),
                html.Div([
                    filter_label("Change Type"),
                    dcc.Dropdown(id="f-change-type", options=change_type_opts, multi=True,
                                 placeholder="All types", style=DD),
                ], style={"flex": "1"}),
            ], style={"display": "flex", "gap": "12px", "marginBottom": "12px"}),

            # Filter row 2
            html.Div([
                html.Div([
                    filter_label("Category"),
                    dcc.Dropdown(id="f-category", options=category_opts, multi=True,
                                 placeholder="All categories", style=DD),
                ], style={"flex": "1"}),
                html.Div([
                    filter_label("Owner Workgroup"),
                    dcc.Dropdown(id="f-workgroup", options=workgroup_opts, multi=True,
                                 placeholder="All workgroups", style=DD),
                ], style={"flex": "2"}),
                html.Div([
                    filter_label("Change Category"),
                    dcc.Dropdown(id="f-change-cat", options=change_cat_opts, multi=True,
                                 placeholder="All change categories", style=DD),
                ], style={"flex": "2"}),
            ], style={"display": "flex", "gap": "12px", "marginBottom": "12px"}),

            # Filter row 3 — aging range + CR search
            html.Div([
                html.Div([
                    filter_label("Pending Age (days)"),
                    dcc.RangeSlider(
                        id="f-age",
                        min=0, max=200, step=1, value=[0, 200],
                        marks={0: "0", 30: "30", 60: "60", 90: "90", 120: "120", 200: "200+"},
                        tooltip={"placement": "bottom", "always_visible": False},
                    ),
                ], style={"flex": "2"}),
                html.Div([
                    filter_label("Select CR"),
                    dcc.Dropdown(id="cr-select", options=[], placeholder="Search or select…",
                                 searchable=True, clearable=True, style=DD),
                ], style={"flex": "2"}),
            ], style={"display": "flex", "gap": "12px", "alignItems": "flex-end", "marginBottom": "20px"}),

            # Result count
            html.Div(id="cr-filter-count", style={"fontSize": "13px", "color": "#888", "marginBottom": "12px"}),

            # Detail panel
            html.Div(id="cr-detail-panel"),

        ], style={"margin": "24px", **CARD, "padding": "20px 24px"}),
    ])


# ── Callback 1: update CR dropdown based on filters ──────────────────────────
@callback(
    Output("cr-select",       "options"),
    Output("cr-select",       "value"),
    Output("cr-filter-count", "children"),
    Input("f-status",      "value"),
    Input("f-priority",    "value"),
    Input("f-risk",        "value"),
    Input("f-change-type", "value"),
    Input("f-category",    "value"),
    Input("f-workgroup",   "value"),
    Input("f-change-cat",  "value"),
    Input("f-age",         "value"),
)
def update_cr_dropdown(statuses, priorities, risks, change_types,
                       categories, workgroups, change_cats, age_range):
    filt = df.copy()

    if statuses:
        filt = filt[filt["Status"].isin(statuses)]
    if priorities:
        filt = filt[filt["Priority"].isin(priorities)]
    if risks:
        filt = filt[filt["Risk"].isin(risks)]
    if change_types:
        filt = filt[filt["Change Type Name"].isin(change_types)]
    if categories:
        filt = filt[filt["Category"].isin(categories)]
    if workgroups:
        filt = filt[filt["Owner Work Group Name"].isin(workgroups)]
    if change_cats:
        filt = filt[filt["Change Category Name"].isin(change_cats)]
    if age_range:
        lo, hi = age_range
        filt = filt[(filt["age_days"] >= lo) & (filt["age_days"] <= hi)]

    opts = [
        {
            "label": f"CR-{row['Change Request Id']}  |  {str(row['Description'])[:55]}…",
            "value": row["Change Request Id"],
        }
        for _, row in filt.iterrows()
    ]
    count_text = f"{len(filt)} CR{'s' if len(filt) != 1 else ''} match the filters"
    return opts, None, count_text


# ── Callback 2: render detail panel ──────────────────────────────────────────
@callback(
    Output("cr-detail-panel", "children"),
    Input("cr-select", "value"),
)
def show_cr_detail(cr_id):
    if cr_id is None:
        return html.Div("Select a CR above to view its details.",
                        style={"color": "#aaa", "fontSize": "14px",
                               "textAlign": "center", "padding": "20px"})

    row = df[df["Change Request Id"] == cr_id].iloc[0]
    age = int(row["age_days"]) if pd.notna(row["age_days"]) else None
    is_pending = row["Status"] in PENDING_STATUSES

    age_color  = "#D7263D" if (age and age > 30) else "#E87C2A" if (age and age > 15) else "#2E8B57"
    aging_text = f"{age} days pending" if (is_pending and age) else (f"{age} days (closed)" if age else "—")

    pri_color  = {"High": "#D7263D", "Medium": "#E87C2A"}.get(str(row["Priority"]), "#333")

    return html.Div([
        # Header
        html.Div([
            html.Div([
                html.Span(f"CR-{row['Change Request Id']}",
                          style={"fontWeight": "800", "fontSize": "20px"}),
                html.Span(row["Status"], style={
                    "marginLeft": "12px", "fontSize": "12px", "fontWeight": "600",
                    "background": "#EEF2FF" if is_pending else "#E8F5E9",
                    "color": "#3730A3" if is_pending else "#2E7D32",
                    "padding": "3px 10px", "borderRadius": "999px",
                }),
            ], style={"display": "flex", "alignItems": "center"}),
            html.Div(aging_text, style={
                "fontSize": "13px", "fontWeight": "700", "color": age_color,
                "background": "#FFF5F5" if (age and age > 30) else "#F0FFF0",
                "padding": "6px 14px", "borderRadius": "6px",
                "border": f"1px solid {age_color}",
            }),
        ], style={"display": "flex", "justifyContent": "space-between",
                  "alignItems": "center", "marginBottom": "16px"}),

        # Change Category Name (full width highlight)
        html.Div([
            html.Div("Change Category", style={**LABEL, "marginBottom": "6px"}),
            html.Div(row["Change Category Name"] if pd.notna(row["Change Category Name"]) else "—",
                     style={"fontSize": "14px", "fontWeight": "600", "color": "#1A1A2E"}),
        ], style={"background": "#EEF2FF", "border": "1px solid #C7D2FE",
                  "borderRadius": "6px", "padding": "12px 16px", "marginBottom": "14px"}),

        # Description
        html.Div([
            html.Div("Description", style={**LABEL, "marginBottom": "6px"}),
            html.Div(row["Description"] if pd.notna(row["Description"]) else "—",
                     style={"fontSize": "14px", "lineHeight": "1.6", "color": "#333"}),
        ], style={"background": "#F8F8F8", "border": "1px solid #e0e0e0",
                  "borderRadius": "6px", "padding": "14px 16px", "marginBottom": "14px"}),

        # Badges row 1 — metadata
        html.Div([
            detail_badge("Priority",     row["Priority"],         color=pri_color),
            detail_badge("Risk",         row["Risk"]),
            detail_badge("Category",     row["Category"]),
            detail_badge("Change Type",  row["Change Type Name"]),
            detail_badge("Impact",       row["Impact Name"]),
            detail_badge("Category Type",row["Category Type Name"]),
        ], style={"display": "flex", "flexWrap": "wrap", "gap": "10px", "marginBottom": "10px"}),

        # Badges row 2 — people
        html.Div([
            detail_badge("Owner Workgroup",    row["Owner Work Group Name"]),
            detail_badge("Requested By",       row["Requested By User Name"]),
            detail_badge("Requestor",          row["Requestor User Name"]),
            detail_badge("Assigned Executive", row["Assigned Executive User Name"]),
        ], style={"display": "flex", "flexWrap": "wrap", "gap": "10px", "marginBottom": "10px"}),

        # Badges row 3 — dates
        html.Div([
            detail_badge("Registered On",    row["Request Registration Time"]),
            detail_badge("Actual Start",     row["Actual Start Time"]),
            detail_badge("Actual End",       row["Actual End Time"]),
            detail_badge("Implemented Date", row["Implemented Date"]),
        ], style={"display": "flex", "flexWrap": "wrap", "gap": "10px"}),
    ])