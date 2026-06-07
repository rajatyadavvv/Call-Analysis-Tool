import dash
import pandas as pd
from dash import Dash, html, dcc, callback, Output, Input, State, MATCH, ALL
import plotly.express as px
from datetime import datetime, timedelta
from db import get_connection
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)

dash.register_page(__name__, path="/cr")

Active_statuses  = ["In Progress"]
PENDING_STATUSES = [
    "Requested", "Approved", "Pre-Migration Approved",
    "Pre-Migration Approved 1", "Migration date finalized",
    "Pending Further Review", "UAT Approved", "Draft", "Approved by Owner"
]
Closed_statuses  = ["Implementation Review Closed", "Closed", "Implemented"]

# ── Professional neutral color palette ───────────────────────────────────────
NEUTRAL_COLORS   = ["#8080EB", "#7FA6EE", "#6363ED", "#9EEDF9", "#C4C4D4", "#BBE798"]
PIE_COLORS       = ["#1A1A2E", "#3D3D5C", "#6B6B8A", "#9494B0", "#B8B8CE", "#D8D8E8"]
RISK_COLOR_MAP   = {"High": "#1A1A2E", "Medium": "#6B6B8A", "Low": "#C4C4D4"}

def categorize_cr(desc):
    desc = str(desc).lower()
    if any(w in desc for w in ['bug', 'error', 'fix', 'issue', 'fail', 'not working', 'incorrect']):
        return 'System Bug'
    elif any(w in desc for w in ['data', 'report', 'extract', 'query', 'download']):
        return 'Data Request'
    elif any(w in desc for w in ['access', 'permission', 'role', 'password', 'unlock', 'vpn']):
        return 'Access/Security'
    elif any(w in desc for w in ['enhance', 'new', 'upgrade', 'update', 'modify', 'logic', 'requirement']):
        return 'Enhancement'
    elif any(w in desc for w in ['server', 'storage', 'migration', 'patch', 'os', 'network', 'switch']):
        return 'Infrastructure'
    else:
        return 'General/Other'


def build_oldest_ui(oldest_df, empty_message):
    items = []
    if oldest_df is not None and not oldest_df.empty:
        for _, row in oldest_df.iterrows():
            age   = int(row["age_days"]) if pd.notna(row["age_days"]) else 0
            color = "#EF4444" if age > 30 else "#F59E0B" if age > 14 else "#888"
            desc  = str(row["Description"])
            short = desc[:45] + "..." if len(desc) > 45 else desc
            items.append(html.Div([
                html.Div([
                    html.Div(f"{row['Change Request Id']} - {str(row['Owner Work Group Name']).split(' ')[-1]}",
                             style={"fontWeight": "700", "fontSize": "13px"}),
                    html.Div(short, style={"fontSize": "11px", "color": "#888", "marginTop": "2px"}),
                ]),
                html.Div(f"{age} Days", style={"fontWeight": "700", "color": color, "fontSize": "13px"}),
            ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center",
                      "padding": "10px 0", "borderBottom": "1px solid #f0f0f0"}))
    if not items:
        items = [html.Div(empty_message, style={"color": "#888", "fontSize": "12px", "marginTop": "10px"})]
    return items


# ── Load data ─────────────────────────────────────────────────────────────────
conn        = get_connection()
df          = pd.read_sql("SELECT * FROM cr_report", conn)
conn.close()

filtered_df = df[df["Owner Work Group Name"].isin(["IT Support (ALC)", "IT Support (EVSM)"])].copy()
filtered_df["Request Registration Time"] = pd.to_datetime(
    filtered_df["Request Registration Time"], errors="coerce"
)

min_date = filtered_df["Request Registration Time"].min().date() if not filtered_df.empty else datetime.now().date()
max_date = filtered_df["Request Registration Time"].max().date() if not filtered_df.empty else datetime.now().date()

CARD = {"background": "white", "border": "1px solid #e0e0e0", "borderRadius": "8px", "padding": "16px"}

SIDE_PANEL_BASE_STYLE = {
    "position": "fixed", "top": "0", "right": "0",
    "width": "400px", "height": "100vh",
    "backgroundColor": "white", "boxShadow": "-4px 0 15px rgba(0,0,0,0.1)",
    "zIndex": "9999", "transition": "transform 0.3s ease-in-out",
    "transform": "translateX(100%)", "display": "flex", "flexDirection": "column",
}


def kpi_card(label, value, delta):
    return html.Div([
        html.Div(label,      style={"fontSize": "11px", "color": "#888", "marginBottom": "8px", "fontWeight": "600"}),
        html.Div(str(value), style={"fontSize": "32px", "fontWeight": "800", "marginBottom": "8px"}),
        html.Div(delta,      style={"fontSize": "12px", "color": "#888"}),
    ], style={"flex": "1", "padding": "24px", **CARD})


# ── Layout ────────────────────────────────────────────────────────────────────
def layout():
    return html.Div([
        html.Div([
            # Topbar
            html.Div([
                html.Span("Dashboards / Change Requests Report"),
            ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center",
                      "padding": "16px 24px", "borderBottom": "1px solid #e0e0e0", "background": "#F3F3F3"}),

            html.H1("Change Requests (CR) Overview", style={"padding": "12px 20px", "marginBottom": "0px"}),

            dcc.Interval(id="auto-refresh-interval", interval=5 * 60 * 1000, n_intervals=0),

            # Two independent date pickers
            html.Div([
                html.Div("FILTER DASHBOARD BY DATE RANGE:", style={
                    "fontWeight": "700", "marginBottom": "12px",
                    "fontSize": "11px", "color": "#555", "letterSpacing": "0.05em",
                }),
                html.Div([
                    html.Div([
                        html.Div("FROM", style={"fontSize": "10px", "color": "#888",
                                                "fontWeight": "700", "marginBottom": "4px"}),
                        dcc.DatePickerSingle(
                            id="cr-start-date",
                            date=min_date,
                            display_format="MMM D, YYYY",
                        ),
                    ]),
                    html.Div([
                        html.Div("TO", style={"fontSize": "10px", "color": "#888",
                                              "fontWeight": "700", "marginBottom": "4px"}),
                        dcc.DatePickerSingle(
                            id="cr-end-date",
                            date=max_date,
                            display_format="MMM D, YYYY",
                        ),
                    ]),
                ], style={"display": "flex", "gap": "24px", "alignItems": "flex-end"}),
            ], style={"padding": "16px 24px", "background": "white", "borderBottom": "1px solid #e0e0e0"}),

            # KPIs
            html.Div(id="kpi-row", style={"display": "flex", "gap": "16px", "padding": "24px"}),

            # Charts
            html.Div([
                html.Div([
                    html.Div([html.Div("Monthly Volume by CR Type", style={"fontWeight": "600", "marginBottom": "12px"}),
                              dcc.Graph(id="chart-month", config={"displayModeBar": False})], style={"flex": "1", **CARD}),
                    html.Div([html.Div("CR Categorization", style={"fontWeight": "600", "marginBottom": "12px"}),
                              dcc.Graph(id="chart-category", config={"displayModeBar": False})], style={"flex": "1", **CARD}),
                ], style={"display": "flex", "gap": "16px", "marginBottom": "16px"}),
                html.Div([
                    html.Div([html.Div("CR Risk Distribution", style={"fontWeight": "600", "marginBottom": "12px"}),
                              dcc.Graph(id="chart-risk", config={"displayModeBar": False})], style={"flex": "1", **CARD}),
                    html.Div([html.Div("CR Status Distribution", style={"fontWeight": "600", "marginBottom": "12px"}),
                              dcc.Graph(id="chart-status", config={"displayModeBar": False})], style={"flex": "1", **CARD}),
                ], style={"display": "flex", "gap": "16px", "marginBottom": "16px"}),
                html.Div([
                    html.Div([html.Div("CR Workgroup Distribution", style={"fontWeight": "600", "marginBottom": "12px"}),
                              dcc.Graph(id="chart-workgroup", config={"displayModeBar": False})], style={"flex": "1", **CARD}),
                    html.Div([html.Div("CR Aging Distribution (Pending)", style={"fontWeight": "600", "marginBottom": "12px"}),
                              dcc.Graph(id="chart-aging", config={"displayModeBar": False})], style={"flex": "1", **CARD}),
                ], style={"display": "flex", "gap": "16px", "marginBottom": "16px"}),
            ], style={"padding": "0 24px"}),

            # AI Insights + Oldest
            html.Div([
                html.Div([
                    # Left — AI
                    html.Div([
                        html.Div([
                            html.Span("✦ ", style={"fontSize": "18px"}),
                            html.Span("AI Insights", style={"fontWeight": "700", "fontSize": "16px"}),
                        ], style={"marginBottom": "16px", "display": "flex", "alignItems": "center"}),
                        html.Div("Select AI Analysis Period (relative to End Date):", style={
                            "fontSize": "11px", "fontWeight": "600", "color": "#888", "marginBottom": "6px",
                        }),
                        html.Div([
                            dcc.Dropdown(
                                id="ai-months-dropdown",
                                options=[
                                    {"label": "Last 1 Month",   "value": 1},
                                    {"label": "Last 2 Months",  "value": 2},
                                    {"label": "Last 3 Months",  "value": 3},
                                    {"label": "Last 6 Months",  "value": 6},
                                    {"label": "Entire Selection","value": 100},
                                ],
                                value=1, clearable=False,
                                style={"width": "200px"},
                            ),
                            html.Button("Generate AI Insights", id="btn-generate-ai", style={
                                "background": "#111827", "color": "white", "border": "none",
                                "padding": "8px 16px", "borderRadius": "6px", "cursor": "pointer",
                                "fontWeight": "600", "fontSize": "12px",
                            }),
                        ], style={"display": "flex", "gap": "12px", "alignItems": "center", "marginBottom": "16px"}),
                        dcc.Loading(
                            html.Div(
                                id="ai-insights-output-cr",
                                children="Select a date range, choose an AI period, and click generate.",
                                style={"fontSize": "13px", "color": "#333", "lineHeight": "1.6",
                                       "whiteSpace": "pre-wrap", "fontFamily": "inherit"},
                            ), type="circle", color="#111827",
                        ),
                    ], style={"flex": "1", "paddingRight": "24px", "borderRight": "1px solid #e0e0e0"}),

                    # Right — Oldest
                    html.Div([
                        dcc.Loading(html.Div(id="oldest-pending-output"), type="circle", color="#111827"),
                    ], style={"flex": "1", "paddingLeft": "24px"}),

                ], style={"display": "flex"}),
            ], style={"padding": "24px", "background": "white",
                      "margin": "0 24px 40px 24px", "border": "1px solid #e0e0e0", "borderRadius": "8px"}),
        ]),

        # Slide-out panel
        html.Div(id="side-panel-container", style=SIDE_PANEL_BASE_STYLE, children=[
            html.Div([
                html.Div("Chart Drill-down", style={"fontWeight": "700", "fontSize": "16px", "color": "#111827"}),
                html.Button("✖", id="close-panel-btn", style={
                    "background": "transparent", "border": "none", "fontSize": "18px",
                    "cursor": "pointer", "color": "#888",
                }),
            ], style={"padding": "20px", "borderBottom": "1px solid #e0e0e0", "display": "flex",
                      "justifyContent": "space-between", "alignItems": "center", "backgroundColor": "#f9fafb"}),
            html.Div(id="side-panel-content", style={"padding": "20px", "overflowY": "auto", "flex": "1"}),
        ]),
    ])


# ── Master callback ───────────────────────────────────────────────────────────
@callback(
    Output("kpi-row",              "children"),
    Output("chart-month",          "figure"),
    Output("chart-category",       "figure"),
    Output("chart-risk",           "figure"),
    Output("chart-status",         "figure"),
    Output("chart-workgroup",      "figure"),
    Output("chart-aging",          "figure"),
    Output("oldest-pending-output","children"),
    Input("cr-start-date",         "date"),
    Input("cr-end-date",           "date"),
    Input("auto-refresh-interval", "n_intervals"),
)
def update_dashboard(start_date, end_date, _intervals, filtered_df=filtered_df):
    fdf = filtered_df.copy()
    fdf["Category"]    = fdf["Description"].apply(categorize_cr)
    fdf["Month_Value"] = fdf["Request Registration Time"].dt.to_period("M").astype(str)

    # Oldest overall (all time)
    pending_all = fdf[fdf["Status"].isin(PENDING_STATUSES)].copy()
    pending_all["age_days"] = (datetime.now() - pending_all["Request Registration Time"]).dt.days
    oldest_all  = pending_all.nlargest(3, "age_days")

    # Apply date filter
    if start_date and end_date:
        start_dt = pd.to_datetime(start_date)
        end_dt   = pd.to_datetime(end_date).replace(hour=23, minute=59, second=59)
        fdf      = fdf[(fdf["Request Registration Time"] >= start_dt) &
                       (fdf["Request Registration Time"] <= end_dt)].copy()

    pending_sel = fdf[fdf["Status"].isin(PENDING_STATUSES)].copy()
    if not pending_sel.empty:
        pending_sel["age_days"] = (datetime.now() - pending_sel["Request Registration Time"]).dt.days
        oldest_sel = pending_sel.nlargest(3, "age_days")
    else:
        oldest_sel = pd.DataFrame()

    combined_oldest = html.Div([
        html.Div("OLDEST PENDING (SELECTED RANGE)", style={
            "fontSize": "11px", "color": "#888", "fontWeight": "600",
            "marginBottom": "8px", "letterSpacing": "0.05em",
        }),
        html.Div(build_oldest_ui(oldest_sel, "No pending items for this timeframe."),
                 style={"marginBottom": "28px"}),
        html.Div("OLDEST PENDING (ALL TIME)", style={
            "fontSize": "11px", "color": "#888", "fontWeight": "600",
            "marginBottom": "8px", "letterSpacing": "0.05em",
        }),
        html.Div(build_oldest_ui(oldest_all, "No pending items overall.")),
    ])

    if fdf.empty:
        empty_fig = px.bar(title="No Data Available for this Range")
        empty_fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        return (
            [kpi_card(l, 0, d) for l, d in [
                ("TOTAL ACTIVE","Active CRs"), ("TOTAL PENDING","Pending CRs"),
                ("TOTAL RESOLVED","Closed"), ("FULFILMENT RATE","Rate"), ("CANCELLED","Cancelled"),
            ]],
            empty_fig, empty_fig, empty_fig, empty_fig, empty_fig, empty_fig, combined_oldest,
        )

    active           = int(fdf["Status"].isin(Active_statuses).sum())
    total_pending    = int(fdf["Status"].isin(PENDING_STATUSES).sum())
    total_resolved   = int(fdf["Status"].isin(Closed_statuses).sum())
    fulfilment_rate  = int(total_resolved / len(fdf) * 100) if len(fdf) > 0 else 0
    cancelled        = int((fdf["Status"] == "Canceled").sum())

    kpi_children = [
        kpi_card("TOTAL ACTIVE",    active,          "Active CRs"),
        kpi_card("TOTAL PENDING",   total_pending,   "Pending CRs"),
        kpi_card("TOTAL RESOLVED",  total_resolved,  "Closed successfully"),
        kpi_card("FULFILMENT RATE", f"{fulfilment_rate}%", "Fulfilment rate"),
        kpi_card("CANCELLED",       cancelled,       "Cancelled CRs"),
    ]

    # Monthly — sorted ascending
    month_cat = (
        fdf.groupby(["Month_Value", "Category"])
        .size().reset_index(name="count")
        .sort_values("Month_Value")
    )
    month_cat["Month_Label"] = pd.to_datetime(month_cat["Month_Value"]).dt.strftime("%b %y")
    ordered_months = month_cat["Month_Label"].unique().tolist()

    fig_month = px.bar(
        month_cat, x="Month_Label", y="count", color="Category", text="count",
        color_discrete_sequence=NEUTRAL_COLORS,
        category_orders={"Month_Label": ordered_months},
    )
    fig_month.update_layout(
        height=320, margin=dict(l=0, r=0, t=10, b=0),
        xaxis_title="", yaxis_title="Total CRs",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig_month.update_yaxes(showgrid=True, gridwidth=1, gridcolor="#f0f0f0")
    fig_month.update_traces(textposition="inside", textfont=dict(color="white", size=11))

    cat_counts = fdf["Category"].value_counts().sort_values(ascending=True).reset_index()
    fig_category = px.bar(cat_counts, y="Category", x="count", orientation="h")
    fig_category.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0),
                                xaxis_title="", yaxis_title="", showlegend=False,
                                plot_bgcolor="rgba(0,0,0,0)")
    fig_category.update_xaxes(showgrid=True, gridcolor="#f0f0f0")

    fig_risk = px.pie(
        fdf["Risk"].dropna().value_counts().reset_index(),
        names="Risk", values="count", hole=0.45,
        color="Risk", color_discrete_map=RISK_COLOR_MAP,
    ) if not fdf["Risk"].dropna().empty else px.pie(title="No Risk Data")
    fig_risk.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0),
                           legend=dict(orientation="h", y=-0.1))
    fig_risk.update_traces(textfont_color="white")

    fig_status = px.pie(
        fdf["Status"].value_counts().reset_index(),
        names="Status", values="count", hole=0.45,
        color_discrete_sequence=PIE_COLORS,
    )
    fig_status.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0))
    fig_status.update_traces(textfont_color="white")

    wg_counts = fdf["Owner Work Group Name"].value_counts().sort_values(ascending=True).reset_index()
    fig_workgroup = px.bar(wg_counts, y="Owner Work Group Name", x="count", orientation="h")
    fig_workgroup.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0),
                                xaxis_title="", yaxis_title="", plot_bgcolor="rgba(0,0,0,0)")
    fig_workgroup.update_xaxes(showgrid=True, gridcolor="#f0f0f0")

    if not pending_sel.empty:
        bins   = [0, 5, 10, 15, 30, float("inf")]
        labels = ["0-5", "6-10", "11-15", "16-30", ">30"]
        pending_sel["age_bucket"] = pd.cut(pending_sel["age_days"], bins=bins, labels=labels)
        fig_aging = px.bar(
            pending_sel["age_bucket"].value_counts().sort_index().reset_index(),
            x="age_bucket", y="count",
            category_orders={"age_bucket": labels},
        )
    else:
        fig_aging = px.bar(title="No Pending CRs")
    fig_aging.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0),
                            xaxis_title="", yaxis_title="", plot_bgcolor="rgba(0,0,0,0)")
    fig_aging.update_yaxes(showgrid=True, gridcolor="#f0f0f0")

    return kpi_children, fig_month, fig_category, fig_risk, fig_status, fig_workgroup, fig_aging, combined_oldest


# ── AI Insights callback ──────────────────────────────────────────────────────
@callback(
    Output("ai-insights-output-cr", "children"),
    Input("btn-generate-ai",        "n_clicks"),
    State("cr-start-date",          "date"),
    State("cr-end-date",            "date"),
    State("ai-months-dropdown",     "value"),
    prevent_initial_call=True,
)
def update_ai_insights(n_clicks, start_date, end_date, ai_months):
    conn    = get_connection()
    df_full = pd.read_sql("SELECT * FROM cr_report", conn)
    conn.close()

    df_full = df_full[df_full["Owner Work Group Name"].isin(["IT Support (ALC)", "IT Support (EVSM)"])].reset_index(drop=True)
    df_full["Category"] = df_full["Description"].apply(categorize_cr)
    df_full["Request Registration Time"] = pd.to_datetime(df_full["Request Registration Time"], errors="coerce")

    df_cb = df_full.copy()
    if start_date and end_date:
        end_dt   = pd.to_datetime(end_date).replace(hour=23, minute=59, second=59)
        start_dt = pd.to_datetime(start_date) if ai_months == 100 else end_dt - pd.DateOffset(months=ai_months)
        df_cb    = df_cb[(df_cb["Request Registration Time"] >= start_dt) &
                         (df_cb["Request Registration Time"] <= end_dt)].copy()

    if df_cb.empty:
        return "No CRs found for this time frame."

    cr_lines = [
        f"ID: {row['Change Request Id']} | Type: {row['Category']} | "
        f"Status: {row['Status']} | Risk: {row['Risk']} | Desc: {row['Description']}"
        for _, row in df_cb.iterrows()
    ]

    prompt = f"""
You are an IT Operations Analyst. Analyze these Change Requests for the ALC and EVSM workgroups.

Find ALL unique patterns. Do not limit to 3.

Respond in EXACTLY this format:

PATTERN: [4-5 word title] | [High/Medium/Low]
[One sentence detail]
Suggested action: [One sentence]

PATTERN: [4-5 word title] | [High/Medium/Low]
[One sentence detail]
Suggested action: [One sentence]

REDUCTION TIPS:
- [tip 1]
- [tip 2]
- [tip 3]

Change Requests:
{chr(10).join(cr_lines)}
"""
    try:
        response = client.chat.completions.create(
            model="google/gemma-4-31b-it:free",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.choices[0].message.content
    except Exception as e:
        return f"Error fetching insights: {str(e)}"

    # Render structured output
    blocks = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("PATTERN:"):
            parts    = line.replace("PATTERN:", "").split("|")
            title    = parts[0].strip()
            sev      = parts[1].strip() if len(parts) > 1 else ""
            sc       = "#1A1A2E" if "High" in sev else "#6B6B8A" if "Medium" in sev else "#9B9BB0"
            blocks.append(html.Div([
                html.Span(title, style={"fontWeight": "700", "fontSize": "13px", "color": "#1A1A2E"}),
                html.Span(sev,   style={"fontSize": "10px", "color": sc, "fontWeight": "700",
                                        "marginLeft": "8px", "padding": "2px 6px",
                                        "background": "#f5f5f5", "borderRadius": "4px"}),
            ], style={"marginTop": "12px", "marginBottom": "2px", "display": "flex", "alignItems": "center"}))
        elif line.startswith("Suggested action:"):
            blocks.append(html.Div(line, style={
                "fontSize": "11px", "color": "#4F46E5", "fontStyle": "italic",
                "borderLeft": "3px solid #4F46E5", "paddingLeft": "8px", "marginTop": "4px",
            }))
        elif line.startswith("REDUCTION TIPS"):
            blocks.append(html.Div("REDUCTION TIPS", style={
                "fontSize": "10px", "fontWeight": "700", "color": "#888",
                "letterSpacing": "0.05em", "marginTop": "16px", "marginBottom": "6px",
            }))
        elif line.startswith("-"):
            blocks.append(html.Div(line, style={"fontSize": "12px", "color": "#333", "marginBottom": "4px"}))
        else:
            blocks.append(html.Div(line, style={"fontSize": "12px", "color": "#555", "marginBottom": "2px"}))
    return html.Div(blocks)


# ── Side panel drill-down ─────────────────────────────────────────────────────
@callback(
    Output("side-panel-content",   "children"),
    Output("side-panel-container", "style"),
    Input("chart-month",     "clickData"),
    Input("chart-category",  "clickData"),
    Input("chart-risk",      "clickData"),
    Input("chart-status",    "clickData"),
    Input("chart-workgroup", "clickData"),
    Input("chart-aging",     "clickData"),
    Input("close-panel-btn", "n_clicks"),
    State("cr-start-date",   "date"),
    State("cr-end-date",     "date"),
    prevent_initial_call=True,
)
def update_drilldown_side_panel(c_month, c_cat, c_risk, c_stat, c_wg, c_aging,
                                close_btn, start_date, end_date):
    ctx          = dash.callback_context
    current_style = SIDE_PANEL_BASE_STYLE.copy()
    if not ctx.triggered:
        return dash.no_update, dash.no_update

    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if triggered_id == "close-panel-btn":
        current_style["transform"] = "translateX(100%)"
        return dash.no_update, current_style

    conn = get_connection()
    df   = pd.read_sql("SELECT * FROM cr_report", conn)
    conn.close()

    df = df[df["Owner Work Group Name"].isin(["IT Support (ALC)", "IT Support (EVSM)"])].reset_index(drop=True)
    df["AI_Category"] = df["Description"].apply(categorize_cr)
    df["Request Registration Time"] = pd.to_datetime(df["Request Registration Time"], errors="coerce")
    df["Month_Label"] = df["Request Registration Time"].dt.strftime("%b %y")

    if start_date and end_date:
        df = df[(df["Request Registration Time"] >= pd.to_datetime(start_date)) &
                (df["Request Registration Time"] <= pd.to_datetime(end_date).replace(hour=23, minute=59, second=59))].copy()

    pending_df = df[df["Status"].isin(PENDING_STATUSES)].copy()
    if not pending_df.empty:
        pending_df["age_days"] = (datetime.now() - pending_df["Request Registration Time"]).dt.days
        pending_df["age_bucket"] = pd.cut(pending_df["age_days"],
                                          bins=[0, 5, 10, 15, 30, float("inf")],
                                          labels=["0-5", "6-10", "11-15", "16-30", ">30"])

    filtered_df = pd.DataFrame()
    filter_text = ""
    try:
        if triggered_id == "chart-month"    and c_month: filtered_df = df[df["Month_Label"] == c_month["points"][0]["x"]];           filter_text = f"Month: {c_month['points'][0]['x']}"
        elif triggered_id == "chart-category" and c_cat:  filtered_df = df[df["AI_Category"] == c_cat["points"][0]["y"]];             filter_text = f"Category: {c_cat['points'][0]['y']}"
        elif triggered_id == "chart-risk"    and c_risk:  filtered_df = df[df["Risk"] == c_risk["points"][0]["label"]];               filter_text = f"Risk: {c_risk['points'][0]['label']}"
        elif triggered_id == "chart-status"  and c_stat:  filtered_df = df[df["Status"] == c_stat["points"][0]["label"]];             filter_text = f"Status: {c_stat['points'][0]['label']}"
        elif triggered_id == "chart-workgroup" and c_wg:  filtered_df = df[df["Owner Work Group Name"] == c_wg["points"][0]["y"]];    filter_text = f"Workgroup: {c_wg['points'][0]['y']}"
        elif triggered_id == "chart-aging"   and c_aging: filtered_df = pending_df[pending_df["age_bucket"] == c_aging["points"][0]["x"]]; filter_text = f"Aging: {c_aging['points'][0]['x']} Days"
    except (KeyError, TypeError, IndexError):
        current_style["transform"] = "translateX(0%)"
        return html.Div("Could not process selection.", style={"color": "red"}), current_style

    if filtered_df.empty:
        current_style["transform"] = "translateX(0%)"
        return html.Div("No records found.", style={"color": "#888"}), current_style

    cards = []
    for _, row in filtered_df.iterrows():
        ticket_id    = str(row.get("Change Request Id"))
        desc         = str(row.get("Description", ""))
        cat          = row.get("AI_Category", "General")
        payload_text = f"Category: {cat} | Risk: {row.get('Risk')} | Workgroup: {row.get('Owner Work Group Name')} | Description: {desc}"
        cards.append(html.Details([
            html.Summary([html.Div([
                html.Span(f"#{ticket_id}", style={"fontWeight": "800", "fontSize": "14px", "color": "#111827"}),
                html.Span(f" • {row.get('Status','N/A')}", style={"fontSize": "12px", "color": "#059669"}),
                html.Span(f" • Risk: {row.get('Risk','N/A')}", style={"fontSize": "12px", "color": "#D97706"}),
            ], style={"display": "flex", "alignItems": "center", "gap": "8px"})],
                style={"padding": "12px", "cursor": "pointer", "backgroundColor": "#f9fafb",
                       "borderRadius": "4px", "marginBottom": "4px", "border": "1px solid #e5e7eb", "listStyle": "none"}),
            html.Div([
                html.Div([html.B("Category: "), cat], style={"marginBottom": "8px"}),
                html.Div([html.B("Owner: "), row.get("Owner Work Group Name", "N/A")], style={"marginBottom": "8px"}),
                html.Div([html.B("Description:"), html.P(desc, style={"marginTop": "4px", "color": "#555", "fontSize": "12px"})]),
                html.Div(payload_text, id={"type": "ticket-payload", "index": ticket_id}, style={"display": "none"}),
                html.Button("Generate AI Action Plan", id={"type": "btn-ticket-ai", "index": ticket_id}, style={
                    "background": "#111827", "color": "white", "border": "none",
                    "padding": "8px 12px", "borderRadius": "6px", "cursor": "pointer",
                    "fontSize": "11px", "fontWeight": "600", "marginTop": "8px", "width": "100%",
                }),
                dcc.Loading(
                    html.Div(id={"type": "ticket-ai-output", "index": ticket_id},
                             style={"marginTop": "12px", "fontSize": "12px", "color": "#374151",
                                    "lineHeight": "1.5", "padding": "8px", "backgroundColor": "#F3F4F6",
                                    "borderRadius": "6px", "display": "none"}),
                    type="dot", color="#111827",
                ),
            ], style={"padding": "16px", "fontSize": "13px", "border": "1px solid #e5e7eb",
                      "borderTop": "none", "borderRadius": "0 0 4px 4px"}),
        ], style={"marginBottom": "8px"}))

    current_style["transform"] = "translateX(0%)"
    return html.Div([
        html.Div(f"{len(filtered_df)} items for '{filter_text}'",
                 style={"fontWeight": "600", "marginBottom": "16px", "color": "#111827",
                        "fontSize": "13px", "padding": "8px"}),
        html.Div(cards),
    ]), current_style


# ── Individual ticket AI ──────────────────────────────────────────────────────
@callback(
    Output({"type": "ticket-ai-output", "index": MATCH}, "children"),
    Output({"type": "ticket-ai-output", "index": MATCH}, "style"),
    Input({"type": "btn-ticket-ai",     "index": MATCH}, "n_clicks"),
    State({"type": "ticket-payload",    "index": MATCH}, "children"),
    State({"type": "ticket-ai-output",  "index": MATCH}, "style"),
    prevent_initial_call=True,
)
def generate_single_ticket_insight(n_clicks, payload, current_style):
    if not n_clicks:
        return dash.no_update, dash.no_update
    prompt = f"""
You are an IT Operations Expert. Review this Change Request and provide:
**1. Root Cause Hypothesis:** (1 sentence)
**2. Recommended SOP / Action:** (1-2 sentences)

Ticket: {payload}
"""
    try:
        response  = client.chat.completions.create(
            model="google/gemma-4-31b-it:free",
            messages=[{"role": "user", "content": prompt}],
        )
        new_style = {**current_style, "display": "block"}
        return dcc.Markdown(response.choices[0].message.content), new_style
    except Exception as e:
        return f"Error: {str(e)}", {**current_style, "display": "block"}