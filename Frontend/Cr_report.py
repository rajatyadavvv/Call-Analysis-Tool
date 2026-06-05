import dash
import pandas as pd
from dash import Dash, html, dcc, callback, Output, Input, State
import plotly.express as px
from datetime import datetime, timedelta
from db import get_connection  # Database connection intact
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)

dash.register_page(__name__, path="/cr")

PENDING_STATUSES = [
    "In Progress", "Requested", "Approved", "Pre-Migration Approved",
    "Pre-Migration Approved 1", "Migration date finalized",
    "Pending Further Review", "UAT Approved", "Draft", "Approved by Owner"
]

def categorize_cr(desc):
    desc = str(desc).lower()
    if any(word in desc for word in ['bug', 'error', 'fix', 'issue', 'fail', 'not working', 'incorrect']):
        return 'System Bug'
    elif any(word in desc for word in ['data', 'report', 'extract', 'query', 'download']):
        return 'Data Request'
    elif any(word in desc for word in ['access', 'permission', 'role', 'password', 'unlock', 'vpn']):
        return 'Access/Security'
    elif any(word in desc for word in ['enhance', 'new', 'upgrade', 'update', 'modify', 'logic', 'requirement']):
        return 'Enhancement'
    elif any(word in desc for word in ['server', 'storage', 'migration', 'patch', 'os', 'network', 'switch']):
        return 'Infrastructure'
    else:
        return 'General/Other'

# ── HELPER: Build Oldest UI ───────────────────────────────────────────────────
def build_oldest_ui(oldest_df, empty_message):
    items = []
    if oldest_df is not None and not oldest_df.empty:
        for _, row in oldest_df.iterrows():
            age = int(row["age_days"]) if pd.notna(row["age_days"]) else 0
            color = "#EF4444" if age > 30 else "#F59E0B" if age > 14 else "#888"
            desc  = str(row["Description"])
            short = desc[:45] + "..." if len(desc) > 45 else desc
            items.append(
                html.Div([
                    html.Div([
                        html.Div(f"{row['Change Request Id']} - {str(row['Owner Work Group Name']).split(' ')[-1]}", style={"fontWeight": "700", "fontSize": "13px"}),
                        html.Div(short, style={"fontSize": "11px", "color": "#888", "marginTop": "2px"}),
                    ]),
                    html.Div(f"{age} Days", style={"fontWeight": "700", "color": color, "fontSize": "13px"}),
                ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "padding": "10px 0", "borderBottom": "1px solid #f0f0f0"})
            )
    if not items:
        items = [html.Div(empty_message, style={"color": "#888", "fontSize": "12px", "marginTop": "10px"})]
    return items


# ── INITIAL DATA LOAD FOR DATE PICKER ─────────────────────────────────────────
conn = get_connection()
df_init = pd.read_sql("SELECT * FROM cr_report", conn)
conn.close()

# Strict filter for ALC & EVSM
df_init = df_init[df_init["Owner Work Group Name"].isin(["IT Support (ALC)", "IT Support (EVSM)"])]
df_init['Request Registration Time'] = pd.to_datetime(df_init['Request Registration Time'], errors='coerce')

# Get min and max dates for the global Date Picker
min_date = df_init['Request Registration Time'].min().date() if not df_init.empty else datetime.now().date()
max_date = df_init['Request Registration Time'].max().date() if not df_init.empty else datetime.now().date()

# ── Styling Templates ─────────────────────────────────────────────────────────
CARD = {"background": "white", "border": "1px solid #e0e0e0", "borderRadius": "8px", "padding": "16px"}

# Base style for the sliding side panel
SIDE_PANEL_BASE_STYLE = {
    "position": "fixed",
    "top": "0",
    "right": "0",
    "width": "400px",
    "height": "100vh",
    "backgroundColor": "white",
    "boxShadow": "-4px 0 15px rgba(0,0,0,0.1)",
    "zIndex": "9999",
    "transition": "transform 0.3s ease-in-out",
    "transform": "translateX(100%)", # Hidden to the right by default
    "display": "flex",
    "flexDirection": "column"
}


def kpi_card(label, value, delta):
    return html.Div([
        html.Div(label, style={"fontSize": "11px", "color": "#888", "marginBottom": "8px", "fontWeight": "600"}),
        html.Div(str(value), style={"fontSize": "32px", "fontWeight": "800", "marginBottom": "8px"}),
        html.Div(delta, style={"fontSize": "12px", "color": "#888"}),
    ], style={"flex": "1", "padding": "24px", **CARD})


# ── LAYOUT ────────────────────────────────────────────────────────────────────
def layout():
    return html.Div([
        # Main Dashboard Content Wrapper
        html.Div([
            html.Div([
                html.Span("Dashboards / Change Requests (ALC & EVSM Only)"),
                html.Div([
                    html.Span("🔔", style={"padding": "12px 20px"}),
                    html.Span("👤", style={"padding": "12px 20px"}),
                ]),
            ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "padding": "16px 24px", "borderBottom": "1px solid #e0e0e0", "background": "#F3F3F3"}),

            html.H1("ALC & EVSM Change Requests", style={"padding": "12px 20px", "marginBottom": "0px"}),

            # Global Date Range Picker
            html.Div([
                html.Div("FILTER DASHBOARD BY DATE RANGE:", style={"fontWeight": "700", "marginBottom": "8px", "fontSize": "11px", "color": "#555", "letterSpacing": "0.05em"}),
                dcc.DatePickerRange(
                    id='date-picker-range',
                    start_date=min_date,
                    end_date=max_date,
                    display_format='MMM D, YYYY',
                    style={"marginBottom": "24px"}
                )
            ], style={"padding": "0 24px"}),

            # Dynamic KPIs Container
            html.Div(id="kpi-row", style={"display": "flex", "gap": "16px", "padding": "0 24px 24px 24px"}),

            # Dynamic Charts Container
            html.Div([
                html.Div([
                    html.Div([html.Div("Monthly Volume by Incident Type", style={"fontWeight": "600", "marginBottom": "12px"}), dcc.Graph(id="chart-month", config={"displayModeBar": False})], style={"flex": "1", **CARD}),
                    html.Div([html.Div("Incident Categorization", style={"fontWeight": "600", "marginBottom": "12px"}), dcc.Graph(id="chart-category", config={"displayModeBar": False})], style={"flex": "1", **CARD}),
                ], style={"display": "flex", "gap": "16px", "marginBottom": "16px"}),

                html.Div([
                    html.Div([html.Div("Risk Distribution", style={"fontWeight": "600", "marginBottom": "12px"}), dcc.Graph(id="chart-risk", config={"displayModeBar": False})], style={"flex": "1", **CARD}),
                    html.Div([html.Div("Status Distribution", style={"fontWeight": "600", "marginBottom": "12px"}), dcc.Graph(id="chart-status", config={"displayModeBar": False})], style={"flex": "1", **CARD}),
                ], style={"display": "flex", "gap": "16px", "marginBottom": "16px"}),

                html.Div([
                    html.Div([html.Div("ALC vs EVSM Volume", style={"fontWeight": "600", "marginBottom": "12px"}), dcc.Graph(id="chart-workgroup", config={"displayModeBar": False})], style={"flex": "1", **CARD}),
                    html.Div([html.Div("CR Aging Distribution (Pending)", style={"fontWeight": "600", "marginBottom": "12px"}), dcc.Graph(id="chart-aging", config={"displayModeBar": False})], style={"flex": "1", **CARD}),
                ], style={"display": "flex", "gap": "16px", "marginBottom": "16px"}),
            ], style={"padding": "0 24px"}),

            # AI Insights & Oldest Pending Section
            html.Div([
                html.Div([
                    
                    # LEFT SIDE: AI Generator
                    html.Div([
                        html.Div([
                            html.Span("✦ ", style={"fontSize": "18px"}),
                            html.Span("Click to generate insight", style={"fontWeight": "700", "fontSize": "16px"}),
                        ], style={"marginBottom": "16px", "display": "flex", "alignItems": "center"}),
                        
                        html.Div([
                            html.Div("Select AI Analysis Period (relative to End Date):", style={"fontSize": "11px", "fontWeight": "600", "color": "#888", "marginBottom": "6px"}),
                            dcc.Dropdown(
                                id="ai-months-dropdown",
                                options=[
                                    {"label": "Last 1 Month", "value": 1},
                                    {"label": "Last 2 Months", "value": 2},
                                    {"label": "Last 3 Months", "value": 3},
                                    {"label": "Last 6 Months", "value": 6},
                                    {"label": "Entire Selection", "value": 100},
                                ],
                                value=1,
                                clearable=False,
                                style={"width": "220px", "marginBottom": "16px"}
                            ),
                        ]),

                        html.Button("Generate AI Insights", id="btn-generate-ai", style={
                            "background": "#111827", "color": "white", "border": "none",
                            "padding": "10px 16px", "borderRadius": "6px", "cursor": "pointer",
                            "fontWeight": "600", "marginBottom": "16px", "fontSize": "12px"
                        }),

                        dcc.Loading(
                            html.Div(
                                id="ai-insights-output-cr",
                                children="Select a date range above, choose an AI monthly period, and click generate.",
                                style={"fontSize": "13px", "color": "#333", "lineHeight": "1.6", "whiteSpace": "pre-wrap", "fontFamily": "inherit"}
                            ), type="circle", color="#111827"
                        ),
                    ], style={"flex": "1", "paddingRight": "24px", "borderRight": "1px solid #e0e0e0"}),

                    # RIGHT SIDE: Oldest Pending
                    html.Div([
                        dcc.Loading(
                            html.Div(id="oldest-pending-output"),
                            type="circle", color="#111827"
                        )
                    ], style={"flex": "1", "paddingLeft": "24px"}),

                ], style={"display": "flex"}),
            ], style={"padding": "24px", "background": "white", "margin": "0 24px 40px 24px", "border": "1px solid #e0e0e0", "borderRadius": "8px"}),
        ]),

        # ── NEW: Slide-Out Side Panel for Drill-down Details ─────────────────
        html.Div(id="side-panel-container", style=SIDE_PANEL_BASE_STYLE, children=[
            # Header
            html.Div([
                html.Div("Chart Drill-down", style={"fontWeight": "700", "fontSize": "16px", "color": "#111827"}),
                html.Button("✖", id="close-panel-btn", style={
                    "background": "transparent", "border": "none", "fontSize": "18px", 
                    "cursor": "pointer", "color": "#888"
                })
            ], style={"padding": "20px", "borderBottom": "1px solid #e0e0e0", "display": "flex", "justifyContent": "space-between", "alignItems": "center", "backgroundColor": "#f9fafb"}),
            
            # Content Area
            html.Div(id="side-panel-content", style={"padding": "20px", "overflowY": "auto", "flex": "1"})
        ])

    ])


# ── MASTER CALLBACK (Updates Dashboard UI & Oldest Items on Date Change) ────────
@callback(
    Output("kpi-row", "children"),
    Output("chart-month", "figure"),
    Output("chart-category", "figure"),
    Output("chart-risk", "figure"),
    Output("chart-status", "figure"),
    Output("chart-workgroup", "figure"),
    Output("chart-aging", "figure"),
    Output("oldest-pending-output", "children"), 
    Input("date-picker-range", "start_date"),
    Input("date-picker-range", "end_date"),
)
def update_dashboard(start_date, end_date):
    conn = get_connection()
    df_full = pd.read_sql("SELECT * FROM cr_report", conn)
    conn.close()

    df_full = df_full[df_full["Owner Work Group Name"].isin(["IT Support (ALC)", "IT Support (EVSM)"])].reset_index(drop=True)
    df_full['Category'] = df_full['Description'].apply(categorize_cr)
    df_full['Request Registration Time'] = pd.to_datetime(df_full['Request Registration Time'], errors='coerce')
    df_full['Month_Value'] = df_full['Request Registration Time'].dt.to_period('M').astype(str)

    pending_overall = df_full[df_full["Status"].isin(PENDING_STATUSES)].copy()
    pending_overall["age_days"] = (datetime.now() - pending_overall["Request Registration Time"]).dt.days
    oldest_overall = pending_overall.nlargest(3, "age_days")

    df = df_full.copy()
    if start_date and end_date:
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date).replace(hour=23, minute=59, second=59)
        df = df[(df['Request Registration Time'] >= start_dt) & (df['Request Registration Time'] <= end_dt)].copy()

    pending_selection = df[df["Status"].isin(PENDING_STATUSES)].copy()
    if not pending_selection.empty:
        pending_selection["age_days"] = (datetime.now() - pending_selection["Request Registration Time"]).dt.days
        oldest_selection = pending_selection.nlargest(3, "age_days")
    else:
        oldest_selection = pd.DataFrame()

    combined_oldest_layout = html.Div([
        html.Div("OLDEST PENDING (IN SELECTED DATE RANGE)", style={"fontSize": "11px", "color": "#888", "fontWeight": "600", "marginBottom": "8px", "letterSpacing": "0.05em"}),
        html.Div(build_oldest_ui(oldest_selection, "No pending items for this timeframe."), style={"marginBottom": "32px"}),
        html.Div("OLDEST PENDING (ALL TIME OVERALL)", style={"fontSize": "11px", "color": "#888", "fontWeight": "600", "marginBottom": "8px", "letterSpacing": "0.05em"}),
        html.Div(build_oldest_ui(oldest_overall, "No pending items overall.")),
    ])

    if df.empty:
        empty_fig = px.bar(title="No Data Available for this Range")
        empty_fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        kpi_empty = [
            kpi_card("TOTAL PENDING", 0, "Active in pipeline"),
            kpi_card("TOTAL RESOLVED", 0, "Closed successfully"),
            kpi_card("AVG AGING", "0 Days", "Pending CRs only"),
            kpi_card("CRITICAL PRIORITY", 0, "High priority CRs")
        ]
        return kpi_empty, empty_fig, empty_fig, empty_fig, empty_fig, empty_fig, empty_fig, combined_oldest_layout

    total_pending = int((df["Status"].isin(PENDING_STATUSES)).sum())
    total_resolved = int((df["Status"].isin(["Implementation Review Closed", "Closed", "Implemented"])).sum())
    critical_priority = int((df["Priority"] == "High").sum())

    avg_aging = round(pending_selection["age_days"].mean(), 1) if not pending_selection.empty and pd.notna(pending_selection["age_days"].mean()) else 0

    kpi_children = [
        kpi_card("TOTAL PENDING", total_pending, "Active in pipeline"),
        kpi_card("TOTAL RESOLVED", total_resolved, "Closed successfully"),
        kpi_card("AVG AGING", f"{avg_aging} Days", "Pending CRs only"),
        kpi_card("CRITICAL PRIORITY", critical_priority, "High priority CRs"),
    ]

    month_cat_counts = df.groupby(['Month_Value', 'Category']).size().reset_index(name='count')
    month_cat_counts['Month_Label'] = pd.to_datetime(month_cat_counts['Month_Value']).dt.strftime('%b %y')
    month_cat_counts = month_cat_counts.sort_values('Month_Value')

    fig_month = px.bar(
        month_cat_counts, x="Month_Label", y="count", color="Category", text="count", 
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    fig_month.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), xaxis_title="", yaxis_title="Total CRs", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), title_text="", plot_bgcolor="rgba(0,0,0,0)",)
    fig_month.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#f0f0f0')
    fig_month.update_traces(textposition='inside', textfont=dict(color='white', size=11))

    cat_counts = df['Category'].value_counts().sort_values(ascending=True).reset_index()
    fig_category = px.bar(cat_counts, y='Category', x='count', orientation='h', color='Category')
    fig_category.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), xaxis_title="", yaxis_title="", showlegend=False)

    if df['Risk'].dropna().empty:
        fig_risk = px.pie(title="No Risk Data")
    else:
        fig_risk = px.pie(df['Risk'].dropna().value_counts().reset_index(), names='Risk', values='count', hole=0.4, color='Risk', color_discrete_map={'High': '#EF4444', 'Medium': '#F59E0B', 'Low': '#10B981'})
    fig_risk.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0))

    fig_status = px.pie(df["Status"].value_counts().reset_index(), names="Status", values="count", hole=0.4)
    fig_status.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)

    wg_counts = df["Owner Work Group Name"].value_counts().sort_values(ascending=True).reset_index()
    fig_workgroup = px.bar(wg_counts, y="Owner Work Group Name", x="count", orientation='h')
    fig_workgroup.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), xaxis_title="", yaxis_title="")

    if not pending_selection.empty:
        bins = [0, 5, 10, 15, 30, float("inf")]
        labels = ["0-5", "6-10", "11-15", "16-30", ">30"]
        pending_selection["age_bucket"] = pd.cut(pending_selection["age_days"], bins=bins, labels=labels)
        fig_aging = px.bar(pending_selection["age_bucket"].value_counts().sort_index().reset_index(), x="age_bucket", y="count")
    else:
        fig_aging = px.bar(title="No Pending CRs")
    fig_aging.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), xaxis_title="", yaxis_title="", plot_bgcolor="rgba(0,0,0,0)")

    return kpi_children, fig_month, fig_category, fig_risk, fig_status, fig_workgroup, fig_aging, combined_oldest_layout


# ── AI INSIGHTS CALLBACK ────────────────────────────────────────────────────────
@callback(
    Output("ai-insights-output-cr", "children"),
    Input("btn-generate-ai", "n_clicks"),
    State("date-picker-range", "start_date"),
    State("date-picker-range", "end_date"),
    State("ai-months-dropdown", "value"),
    prevent_initial_call=True
)
def update_ai_insights(n_clicks, start_date, end_date, ai_months):
    conn = get_connection()
    df_full = pd.read_sql("SELECT * FROM cr_report", conn)
    conn.close()

    df_full = df_full[df_full["Owner Work Group Name"].isin(["IT Support (ALC)", "IT Support (EVSM)"])].reset_index(drop=True)
    df_full['Category'] = df_full['Description'].apply(categorize_cr)
    df_full['Request Registration Time'] = pd.to_datetime(df_full['Request Registration Time'], errors='coerce')

    df_cb = df_full.copy()
    if start_date and end_date:
        end_dt = pd.to_datetime(end_date).replace(hour=23, minute=59, second=59)
        if ai_months == 100:
            start_dt = pd.to_datetime(start_date)
        else:
            start_dt = end_dt - pd.DateOffset(months=ai_months)
        df_cb = df_cb[(df_cb['Request Registration Time'] >= start_dt) & (df_cb['Request Registration Time'] <= end_dt)].copy()

    cr_lines = []
    for _, row in df_cb.iterrows():
        cr_lines.append(
            f"ID: {row['Change Request Id']} | Type: {row['Category']} | "
            f"Status: {row['Status']} | Risk: {row['Risk']} | Desc: {row['Description']}"
        )
    cr_text = "\n".join(cr_lines)

    if not cr_lines:
        return "No CRs found for this specific monthly time frame."
    else:
        prompt = f"""
        You are an AI IT Operations Analyst. Analyze these Change Requests for the ALC and EVSM workgroups based on the selected time period. 
        Provide exactly 2-3 detected patterns or risks specific to these teams.
        For each pattern provide:
        - A short bold title
        - One sentence detail
        - One suggested action (prefix with "Suggested action:")
        
        Change Requests:
        {cr_text}
        """
        try:
            response = client.chat.completions.create(
                model="google/gemma-4-31b-it:free",
                messages=[{"role": "user", "content": prompt}],
            )   
            return response.choices[0].message.content
        except Exception as e:
            return f"Error fetching insights: {str(e)}"


# ── UPDATED: SIDE-PANEL DRILL-DOWN CALLBACK ───────────────────────────────────
# ── UPDATED: SIDE-PANEL DRILL-DOWN CALLBACK ───────────────────────────────────
@callback(
    Output("side-panel-content", "children"),
    Output("side-panel-container", "style"),
    Input("chart-month", "clickData"),
    Input("chart-category", "clickData"),
    Input("chart-risk", "clickData"),
    Input("chart-status", "clickData"),
    Input("chart-workgroup", "clickData"),
    Input("chart-aging", "clickData"),
    Input("close-panel-btn", "n_clicks"),
    State("date-picker-range", "start_date"),
    State("date-picker-range", "end_date"),
    prevent_initial_call=True
)
def update_drilldown_side_panel(c_month, c_cat, c_risk, c_stat, c_wg, c_aging, close_btn, start_date, end_date):
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update

    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    current_style = SIDE_PANEL_BASE_STYLE.copy()

    # If the user clicked the close button, hide the panel
    if triggered_id == "close-panel-btn":
        current_style["transform"] = "translateX(100%)"
        return dash.no_update, current_style

    # 1. Fetch & prep data
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM cr_report", conn)
    conn.close()

    df = df[df["Owner Work Group Name"].isin(["IT Support (ALC)", "IT Support (EVSM)"])].reset_index(drop=True)
    df['Category'] = df['Description'].apply(categorize_cr)
    df['Request Registration Time'] = pd.to_datetime(df['Request Registration Time'], errors='coerce')
    df['Month_Label'] = df['Request Registration Time'].dt.strftime('%b %y')
    
    if start_date and end_date:
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date).replace(hour=23, minute=59, second=59)
        df = df[(df['Request Registration Time'] >= start_dt) & (df['Request Registration Time'] <= end_dt)].copy()

    # Pre-calculate aging logic
    pending_df = df[df["Status"].isin(PENDING_STATUSES)].copy()
    if not pending_df.empty:
        pending_df["age_days"] = (datetime.now() - pending_df["Request Registration Time"]).dt.days
        bins = [0, 5, 10, 15, 30, float("inf")]
        labels = ["0-5", "6-10", "11-15", "16-30", ">30"]
        pending_df["age_bucket"] = pd.cut(pending_df["age_days"], bins=bins, labels=labels)

    # 2. Filter logic
    filtered_df = pd.DataFrame()
    filter_text = ""
    try:
        if triggered_id == "chart-month" and c_month:
            clicked_val = c_month['points'][0]['x']
            filtered_df = df[df['Month_Label'] == clicked_val]
            filter_text = f"Month: {clicked_val}"
        elif triggered_id == "chart-category" and c_cat:
            clicked_val = c_cat['points'][0]['y'] 
            filtered_df = df[df['Category'] == clicked_val]
            filter_text = f"Category: {clicked_val}"
        elif triggered_id == "chart-risk" and c_risk:
            clicked_val = c_risk['points'][0]['label'] 
            filtered_df = df[df['Risk'] == clicked_val]
            filter_text = f"Risk: {clicked_val}"
        elif triggered_id == "chart-status" and c_stat:
            clicked_val = c_stat['points'][0]['label'] 
            filtered_df = df[df['Status'] == clicked_val]
            filter_text = f"Status: {clicked_val}"
        elif triggered_id == "chart-workgroup" and c_wg:
            clicked_val = c_wg['points'][0]['y']
            filtered_df = df[df['Owner Work Group Name'] == clicked_val]
            filter_text = f"Workgroup: {clicked_val}"
        elif triggered_id == "chart-aging" and c_aging:
            clicked_val = c_aging['points'][0]['x']
            filtered_df = pending_df[pending_df['age_bucket'] == clicked_val]
            filter_text = f"Aging: {clicked_val} Days"
    except (KeyError, TypeError, IndexError):
        current_style["transform"] = "translateX(0%)"
        return html.Div("Could not process the selection.", style={"color": "red"}), current_style

    if filtered_df.empty:
        current_style["transform"] = "translateX(0%)"
        return html.Div("No records found.", style={"color": "#888"}), current_style

    # 3. Create ACCORDION cards with DETAILED SUMMARY
    cards = []
    for _, row in filtered_df.iterrows():
        cards.append(
            html.Details([
                html.Summary([
                    # Detailed Summary Header
                    html.Div([
                        html.Span(f"#{row.get('Change Request Id', 'N/A')}", style={"fontWeight": "800", "fontSize": "14px", "color": "#111827"}),
                        html.Span(f" • {row.get('Status', 'N/A')}", style={"fontSize": "12px", "color": "#059669", "fontWeight": "600"}),
                        
                        html.Span(" ▾", style={"float": "right", "color": "#888"})
                    ], style={"display": "flex", "alignItems": "center", "gap": "8px"})
                ], style={"padding": "12px", "cursor": "pointer", "backgroundColor": "#f9fafb", "borderRadius": "4px", "marginBottom": "4px", "listStyle": "none", "border": "1px solid #e5e7eb"}),
                
                # Expanded Details Content
                html.Div([
                    html.Div([html.B("Category: "), f"{row.get('Category', 'N/A')}"], style={"marginBottom": "8px"}),
                    html.Div([html.B("Priority: "), f"{row.get('Priority', 'N/A')}"], style={"marginBottom": "8px"}),
                    html.Div([html.B("Owner: "), f"{row.get('Owner Work Group Name', 'N/A')}"], style={"marginBottom": "8px"}),
                    html.Div([html.B("Description:"), html.P(f"{str(row.get('Description', ''))}", style={"marginTop": "4px", "color": "#555", "fontSize": "12px"})]),
                ], style={"padding": "16px", "fontSize": "13px", "border": "1px solid #e5e7eb", "borderTop": "none", "borderRadius": "0 0 4px 4px"})
            ], style={"marginBottom": "8px"})
        )

    content_layout = html.Div([
        html.Div(f"{len(filtered_df)} items found for '{filter_text}'", style={"fontWeight": "600", "marginBottom": "16px", "color": "#111827", "fontSize": "13px", "padding": "8px"}),
        html.Div(cards)
    ])

    current_style["transform"] = "translateX(0%)"
    return content_layout, current_style

    # 3. Create UI Cards for the filtered results
    cards = []
    for _, row in filtered_df.iterrows():
        cards.append(html.Div([
            html.Div([
                html.Span(f"{row.get('Change Request Id', 'N/A')}", style={"fontWeight": "700", "color": "#111827", "fontSize": "13px"}),
            ], style={"marginBottom": "4px"}),
            
            html.Div([
                html.Span(f"Status: {row.get('Status', 'N/A')}", style={"marginRight": "12px", "color": "#10B981", "fontWeight": "600"}),
                html.Span(f"Risk: {row.get('Risk', 'N/A')}", style={"marginRight": "12px", "color": "#F59E0B", "fontWeight": "600"}),
            ], style={"marginBottom": "6px", "fontSize": "11px"}),
            
            html.Div(f"{str(row.get('Description', ''))}", style={"fontSize": "12px", "color": "#555", "lineHeight": "1.4", "wordWrap": "break-word"})
        ], style={"borderBottom": "1px solid #f0f0f0", "padding": "12px 0"}))

    content_layout = html.Div([
        html.Div(f"{len(filtered_df)} items found for '{filter_text}'", style={"fontWeight": "600", "marginBottom": "16px", "color": "#111827", "fontSize": "13px", "backgroundColor": "#f3f4f6", "padding": "8px", "borderRadius": "4px"}),
        html.Div(cards)
    ])

    # Show the panel
    current_style["transform"] = "translateX(0%)"
    
    return content_layout, current_style