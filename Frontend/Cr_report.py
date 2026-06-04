import dash
import pandas as pd
from dash import Dash, html, dcc, callback, Output, Input
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

conn = get_connection()
df = pd.read_sql("SELECT * FROM cr_report", conn)
conn.close()

df = df[
    df["Owner Work Group Name"].isin(["IT Support (ALC)", "IT Support (EVSM)"])
].reset_index(drop=True)

PENDING_STATUSES = [
    "In Progress", "Requested", "Approved", "Pre-Migration Approved",
    "Pre-Migration Approved 1", "Migration date finalized",
    "Pending Further Review", "UAT Approved", "Draft", "Approved by Owner"
]

# ── Pre-compute global KPIs ───────────────────────────────────────────────────
total_pending     = int((df["Status"].isin(PENDING_STATUSES)).sum())
total_resolved    = int((df["Status"].isin(["Implementation Review Closed", "Closed", "Implemented"])).sum())
critical_priority = int((df["Priority"] == "High").sum())

pending_df = df[df["Status"].isin(PENDING_STATUSES)].copy()
pending_df["age_days"] = (datetime.now() - pd.to_datetime(pending_df["Request Registration Time"], errors="coerce")).dt.days
avg_aging = round(pending_df["age_days"].mean(), 1)

df["age_days"] = (datetime.now() - pd.to_datetime(df["Request Registration Time"], errors="coerce")).dt.days

bins   = [0, 5, 10, 15, 30, float("inf")]
labels = ["0-5", "6-10", "11-15", "16-30", ">30"]
pending_df["age_bucket"] = pd.cut(pending_df["age_days"], bins=bins, labels=labels)

# ── Static charts ─────────────────────────────────────────────────────────────
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

# ── Filter options ────────────────────────────────────────────────────────────
def make_opts(series):
    vals = sorted([v for v in series.dropna().unique() if str(v).strip()])
    return [{"label": v, "value": v} for v in vals]

change_cat_opts = make_opts(df["Change Category Name"])

# ── Styling ───────────────────────────────────────────────────────────────────
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


# ── Callback ──────────────────────────────────────────────────────────────────
@callback(
    Output("ai-insights-output-cr", "children"),
    Input("insights-range-cr", "value"),
)
def update_insights(weeks):
    conn = get_connection()
    df_cb = pd.read_sql("SELECT * FROM cr_report", conn)
    conn.close()

    df_cb = df_cb[
        df_cb["Owner Work Group Name"].isin(["IT Support (ALC)", "IT Support (EVSM)"])
    ].reset_index(drop=True)

    # Filter by selected weeks
    cutoff = datetime.now() - timedelta(weeks=weeks)
    filtered_df = df_cb[
        pd.to_datetime(df_cb["Request Registration Time"], errors="coerce") >= cutoff
    ]

    # Build text for Gemini
    cr_lines = []
    for _, row in filtered_df.iterrows():
        cr_lines.append(
            f"ID: {row['Change Request Id']} | "
            f"Status: {row['Status']} | "
            f"Category: {row['Change Category Name']} | "
            f"Priority: {row['Priority']} | "
            f"Risk: {row['Risk']} | "
            f"Description: {row['Description']}"
        )
    cr_text = "\n".join(cr_lines)

    if not cr_lines:
        return html.Div("No CRs found for the selected time range.",
                        style={"color": "#888", "fontSize": "13px"})

    prompt = f"""
You are an IT operations analyst. Analyze these Change Requests and provide exactly 2-3 detected patterns.
For each pattern provide:
- A short bold title
- One sentence detail
- One suggested action (prefix with "Suggested action:")

Also flag any repeating issues or common queries across multiple CRs.
Keep it concise and actionable.

Change Requests:
{cr_text}
"""

    try:
        response = client.chat.completions.create(
        model="google/gemma-4-31b-it:free",  # free model on OpenRouter
        messages=[{"role": "user", "content": prompt}],
        )   
        insights_text = response.choices[0].message.content
    except Exception as e:
        insights_text = f"Error fetching insights: {str(e)}"

    # Oldest pending CRs
    pending = df_cb[df_cb["Status"].isin(PENDING_STATUSES)].copy()
    pending["age_days"] = (
        datetime.now() - pd.to_datetime(pending["Request Registration Time"], errors="coerce")
    ).dt.days
    oldest = pending.nlargest(3, "age_days")

    oldest_items = []
    for _, row in oldest.iterrows():
        age = int(row["age_days"]) if pd.notna(row["age_days"]) else 0
        color = "#EF4444" if age > 30 else "#F59E0B" if age > 14 else "#888"
        desc  = str(row["Description"])
        short = desc[:50] + "..." if len(desc) > 50 else desc
        oldest_items.append(
            html.Div([
                html.Div([
                    html.Div(str(row["Change Request Id"]),
                             style={"fontWeight": "700", "fontSize": "13px"}),
                    html.Div(short, style={"fontSize": "11px", "color": "#888", "marginTop": "2px"}),
                ]),
                html.Div(f"{age} Days", style={"fontWeight": "700", "color": color, "fontSize": "13px"}),
            ], style={
                "display": "flex", "justifyContent": "space-between",
                "alignItems": "center", "padding": "10px 0",
                "borderBottom": "1px solid #f0f0f0",
            }),
        )

    return html.Div([
        html.Div([
            # Left — AI patterns
            html.Div([
                html.Div("DETECTED PATTERNS", style={
                    "fontSize": "11px", "color": "#888", "fontWeight": "600",
                    "marginBottom": "16px", "letterSpacing": "0.05em",
                }),
                html.Pre(insights_text, style={
                    "whiteSpace": "pre-wrap", "fontSize": "13px",
                    "lineHeight": "1.6", "color": "#333", "margin": "0",
                    "fontFamily": "inherit",
                }),
            ], style={"flex": "1", "paddingRight": "24px", "borderRight": "1px solid #e0e0e0"}),

            # Right — oldest pending
            html.Div([
                html.Div("ATTENTION REQUIRED: OLDEST PENDING", style={
                    "fontSize": "11px", "color": "#888", "fontWeight": "600",
                    "marginBottom": "16px", "letterSpacing": "0.05em",
                }),
                html.Div(oldest_items),
            ], style={"flex": "1", "paddingLeft": "24px"}),

        ], style={"display": "flex"}),
    ])


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
            kpi_card("TOTAL PENDING",     total_pending,          "Active in pipeline"),
            kpi_card("TOTAL RESOLVED",    total_resolved,         "Closed successfully"),
            kpi_card("AVG AGING",         f"{avg_aging} Days",    "Pending CRs only"),
            kpi_card("CRITICAL PRIORITY", critical_priority,      "High priority CRs"),
        ], style={"display": "flex", "gap": "16px", "padding": "24px"}),

        # Charts
        html.Div([
            html.Div([
                html.Div([
                    html.Div("CRs by Workgroup", style={"fontWeight": "600", "marginBottom": "12px"}),
                    dcc.Graph(figure=fig_workgroup, config={"displayModeBar": False}),
                ], style={"flex": "1", **CARD}),
                html.Div([
                    html.Div("Status Distribution", style={"fontWeight": "600", "marginBottom": "12px"}),
                    dcc.Graph(figure=fig_status, config={"displayModeBar": False}),
                ], style={"flex": "1", **CARD}),
            ], style={"display": "flex", "gap": "16px", "marginBottom": "16px"}),

            html.Div([
                html.Div("CR Aging Distribution", style={"fontWeight": "600", "marginBottom": "12px"}),
                dcc.Graph(figure=fig_aging, config={"displayModeBar": False}),
            ], style={**CARD}),
        ], style={"padding": "0 24px"}),

        # AI Insights
        html.Div([
            html.Div([
                html.Div([
                    html.Span("✦ ", style={"fontSize": "18px"}),
                    html.Span("AI Insights", style={"fontWeight": "700", "fontSize": "16px"}),
                ], style={"marginBottom": "16px", "display": "flex", "alignItems": "center"}),

                dcc.Dropdown(
                    id="insights-range-cr",
                    options=[
                        {"label": "1 Week",  "value": 1},
                        {"label": "2 Weeks", "value": 2},
                        {"label": "3 Weeks", "value": 3},
                        {"label": "4 Weeks", "value": 4},
                    ],
                    value=1,
                    clearable=False,
                    style={"width": "200px", "marginBottom": "16px"},
                ),

                html.Div(
                    id="ai-insights-output-cr",
                    children="Select a time range to generate insights.",
                    style={"fontSize": "13px", "color": "#888"},
                ),
            ], style={
                "padding": "20px",
                "background": "white",
                "border": "1px solid #e0e0e0",
                "borderRadius": "8px",
            }),
        ], style={"padding": "24px", "marginBottom": "40px"}),

    ])