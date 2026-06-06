import dash
import pandas as pd
from dash import html, dcc, callback, Output, Input
import plotly.express as px
from db import get_connection
from datetime import datetime, timedelta
from openai import OpenAI
import os
import dotenv
import re

dotenv.load_dotenv()

dash.register_page(__name__, path="/incident")

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)

# ── Load data ─────────────────────────────────────────────────────────────────
conn = get_connection()
df_raw = pd.read_sql("SELECT * FROM incident_report", conn)
conn.close()

base_df = df_raw[df_raw["Workgroup"].isin(["IT Support (ALC)", "IT Support (EVSM)"])].reset_index(drop=True)
base_df["date"] = pd.to_datetime(base_df["Log Time"], format="%d/%m/%y %H:%M", errors="coerce")
base_df["month_year"] = base_df["date"].dt.strftime("%Y-%m")
base_df["month_year_label"] = base_df["date"].dt.strftime("%B %Y")
base_df["age_days"] = (datetime.now() - base_df["date"]).dt.days

# ── Month options ─────────────────────────────────────────────────────────────
month_opts = (
    base_df[["month_year", "month_year_label"]]
    .drop_duplicates()
    .dropna()
    .sort_values("month_year")
)
month_options = [{"label": r["month_year_label"], "value": r["month_year"]}
                 for _, r in month_opts.iterrows()]
min_month = month_opts["month_year"].min()
max_month = month_opts["month_year"].max()

PENDING_STATUSES = ["In-Progress", "Pending", "Open"]

INCIDENT_CATEGORIES = [
    "System Bug",
    "Data Request",
    "Lack of Functional/Operational Knowledge",
    "Master Data Request",
]

# ── Styling ───────────────────────────────────────────────────────────────────
CARD  = {"background": "white", "border": "1px solid #e0e0e0", "borderRadius": "8px", "padding": "16px"}
LABEL = {"fontSize": "11px", "color": "#888", "marginBottom": "6px",
         "textTransform": "uppercase", "letterSpacing": "0.05em", "fontWeight": "600"}
DD    = {"fontSize": "13px"}

def kpi_card(label, value, delta):
    return html.Div([
        html.Div(label, style={"fontSize": "11px", "color": "#888", "marginBottom": "8px"}),
        html.Div(str(value), style={"fontSize": "32px", "fontWeight": "800", "marginBottom": "8px"}),
        html.Div(delta, style={"fontSize": "12px", "color": "#888"}),
    ], style={"flex": "1", "padding": "24px", **CARD})


# ── Helper: build figures ─────────────────────────────────────────────────────
def build_figures(fdf):
    fig_location = px.bar(fdf["Location"].value_counts().reset_index(), x="Location", y="count")
    fig_location.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), xaxis_title="", yaxis_title="")

    fig_category = px.pie(fdf["Status"].value_counts().reset_index(), names="Status", values="count")

    fig_classification = px.bar(fdf["Classification"].value_counts().reset_index(), x="Classification", y="count")
    fig_classification.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), xaxis_title="", yaxis_title="")

    fig_workgroup = px.bar(fdf["Workgroup"].value_counts().reset_index(), x="Workgroup", y="count")
    fig_workgroup.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), xaxis_title="", yaxis_title="")

    month_counts = fdf["month_year_label"].value_counts().reset_index()
    month_counts.columns = ["month_year_label", "count"]
    fig_month = px.line(month_counts, x="month_year_label", y="count", markers=True)
    fig_month.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), xaxis_title="", yaxis_title="")

    return fig_location, fig_category, fig_classification, fig_workgroup, fig_month

active  = int(base_df["Status"].isin(PENDING_STATUSES).sum())
res     = int((base_df["Status"].isin(["Resolved", "Closed"])).sum())
rej     = int((base_df["Status"] == "Rejected").sum())
rate    = round(res / len(base_df) * 100, 1) if len(base_df) > 0 else 0


# ── Callback: month filter → charts + KPIs ───────────────────────────────────
@callback(
    Output("graph-month",         "figure"),
    Output("graph-location",      "figure"),
    Output("graph-status",        "figure"),
    Output("graph-classification","figure"),
    Output("graph-workgroup",     "figure"),
    Input("filter-from-month",    "value"),
    Input("filter-to-month",      "value"),
)
def update_charts(from_month, to_month):
    fdf = base_df.copy()
    if from_month:
        fdf = fdf[fdf["month_year"] >= from_month]
    if to_month:
        fdf = fdf[fdf["month_year"] <= to_month]

    if fdf.empty:
        empty_fig = px.bar(title="No data")
        return (
            html.Div("No data for selected range.", style={"color": "#888", "padding": "24px"}),
            empty_fig, empty_fig, empty_fig, empty_fig, empty_fig,
        )

    fig_loc, fig_cat, fig_cls, fig_wg, fig_mo = build_figures(fdf)

    return  fig_mo, fig_loc, fig_cat, fig_cls, fig_wg


# ── Callback: AI insights ─────────────────────────────────────────────────────
@callback(
    Output("ai-insights-output-incident", "children"),
    Input("insights-range-incident",      "value"),
)
def update_insights(weeks):
    # ── Load fresh data ───────────────────────────────────────────────────────
    conn_cb = get_connection()
    df_cb   = pd.read_sql("SELECT * FROM incident_report", conn_cb)
    conn_cb.close()
 
    df_cb = df_cb[df_cb["Workgroup"].isin(["IT Support (ALC)", "IT Support (EVSM)"])].reset_index(drop=True)
    df_cb["date"] = pd.to_datetime(df_cb["Log Time"], format="%d/%m/%y %H:%M", errors="coerce")

    # ── Time windows ──────────────────────────────────────────────────────────
    now    = df_cb["date"].max()

    if weeks == 9999:
        current = df_cb.copy()
    else:
        cutoff  = now - timedelta(weeks=weeks)
        current = df_cb[df_cb["date"] >= cutoff].copy()

    prev_cutoff = (now - timedelta(weeks=weeks + 4)) if weeks != 9999 else None
    previous    = df_cb[(df_cb["date"] >= prev_cutoff) & (df_cb["date"] < (now - timedelta(weeks=weeks)))] if prev_cutoff is not None else pd.DataFrame(columns=df_cb.columns)
    cutoff      = now - timedelta(weeks=weeks)
    current     = df_cb[df_cb["date"] >= cutoff].copy()
    prev_cutoff = cutoff - timedelta(weeks=4)
    previous    = df_cb[(df_cb["date"] >= prev_cutoff) & (df_cb["date"] < cutoff)].copy()

    if current.empty:
        return html.Div("No incidents found for selected range.",
                        style={"color": "#888", "fontSize": "13px"})

    # ── Category breakdown ────────────────────────────────────────────────────
    def count_cat(frame, cat):
        return int(frame["Classification"].str.contains(cat, case=False, na=False).sum())

    cat_rows = []
    for cat in INCIDENT_CATEGORIES:
        curr_c = count_cat(current, cat)
        prev_c = count_cat(previous, cat)
        chg    = round((curr_c - prev_c) / prev_c * 100, 1) if prev_c > 0 else (100.0 if curr_c > 0 else 0.0)
        trend  = "↑" if chg > 0 else ("↓" if chg < 0 else "→")
        tcolor = "#EF4444" if chg > 0 else ("#10B981" if chg < 0 else "#888")
        cat_rows.append(html.Div([
            html.Div(cat,                    style={"fontSize": "12px", "fontWeight": "600", "flex": "2"}),
            html.Div(str(curr_c),            style={"fontSize": "13px", "fontWeight": "800", "flex": "1", "textAlign": "center"}),
            html.Div(f"{trend} {abs(chg)}%", style={"fontSize": "12px", "color": tcolor, "fontWeight": "600", "flex": "1", "textAlign": "right"}),
        ], style={"display": "flex", "alignItems": "center", "padding": "8px 0", "borderBottom": "1px solid #f0f0f0"}))

    category_panel = html.Div([
        html.Div([
            html.Div("CATEGORY",   style={"fontSize": "10px", "color": "#888", "fontWeight": "700", "flex": "2"}),
            html.Div("COUNT",      style={"fontSize": "10px", "color": "#888", "fontWeight": "700", "flex": "1", "textAlign": "center"}),
            html.Div("VS PREV 4W", style={"fontSize": "10px", "color": "#888", "fontWeight": "700", "flex": "1", "textAlign": "right"}),
        ], style={"display": "flex", "marginBottom": "4px"}),
        html.Div(cat_rows),
    ])

    # ── Split open vs resolved ────────────────────────────────────────────────
    open_inc     = current[current["Status"].isin(PENDING_STATUSES)].copy()
    resolved_inc = df_cb[df_cb["Status"].isin(["Resolved", "Closed"])].copy()

    # ── Find similar resolved incidents by symptom keywords ──────────────────
    def find_similar(symptom, resolved_df, top_n=3):
        if pd.isna(symptom) or str(symptom).strip() == "":
            return []
        keywords = [w for w in str(symptom).lower().split() if len(w) > 3]
        if not keywords:
            return []
        mask = resolved_df["Symptom"].str.lower().apply(
            lambda s: any(k in str(s) for k in keywords)
        )
        return resolved_df[mask].head(top_n)[["Symptom", "Solution"]].to_dict("records")

    # ── Build text for AI ─────────────────────────────────────────────────────
    lines = []
    for _, row in open_inc.iterrows():
        similar      = find_similar(row.get("Symptom"), resolved_inc)
        similar_text = ""
        if similar:
            similar_text = " | Similar past cases: " + "; ".join(
                [f"[{s['Symptom']} → {s['Solution']}]" for s in similar]
            )
        lines.append(
            f"ID: {row.get('Incident ID', '')} | "
            f"Category: {row.get('Classification', '')} | "
            f"Priority: {row.get('Priority', '')} | "
            f"Symptom: {row.get('Symptom', '')}"
            f"{similar_text}"
        )

    if not lines:
        return html.Div([
            html.Div("No open incidents in selected range.",
                     style={"color": "#888", "fontSize": "13px", "marginBottom": "16px"}),
            html.Div([
                html.Div("CATEGORY BREAKDOWN", style={
                    "fontSize": "10px", "color": "#888", "fontWeight": "700",
                    "letterSpacing": "0.05em", "marginBottom": "12px",
                }),
                category_panel,
            ]),
        ])

    prompt = f"""
You are an IT operations analyst. Analyze these incidents from the last {weeks} week(s).
Where similar past cases are provided, use their solutions to suggest fixes.

Respond in this EXACT format with NO extra text:

PATTERN 1: [4-5 word title]
[One sentence detail]
Suggested fix: [One sentence based on similar past solutions if available]

PATTERN 2: [4-5 word title]
[One sentence detail]
Suggested fix: [One sentence]

PATTERN 3: [4-5 word title]
[One sentence detail]
Suggested fix: [One sentence]

REDUCTION TIPS:
• [One tip based on patterns]
• [One tip based on solutions]
• [One tip based on category trends]

Incidents:
{chr(10).join(lines)}
"""

    # ── Call AI ───────────────────────────────────────────────────────────────
    try:
        response = client.chat.completions.create(
            model="google/gemma-4-31b-it:free",
            messages=[{"role": "user", "content": prompt}],
        )
        insights_text = response.choices[0].message.content
    except Exception as e:
        insights_text = f"Error fetching insights: {str(e)}"

    # ── Render insights ───────────────────────────────────────────────────────
    def render_insights(text):
        blocks = []
        for line in text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("PATTERN"):
                parts = line.split(":", 1)
                blocks.append(html.Div(
                    parts[1].strip() if len(parts) > 1 else line,
                    style={"fontWeight": "700", "fontSize": "13px", "color": "#1A1A2E",
                           "marginTop": "12px", "marginBottom": "2px"},
                ))
            elif line.startswith("Suggested fix:"):
                blocks.append(html.Div(line, style={
                    "fontSize": "11px", "color": "#4F46E5", "fontStyle": "italic",
                    "borderLeft": "3px solid #4F46E5", "paddingLeft": "8px", "marginTop": "4px",
                }))
            elif line.startswith("REDUCTION TIPS"):
                blocks.append(html.Div("REDUCTION TIPS", style={
                    "fontSize": "10px", "fontWeight": "700", "color": "#888",
                    "letterSpacing": "0.05em", "marginTop": "16px", "marginBottom": "6px",
                }))
            elif line.startswith("•"):
                blocks.append(html.Div(line, style={"fontSize": "12px", "color": "#333", "marginBottom": "4px"}))
            else:
                blocks.append(html.Div(line, style={"fontSize": "12px", "color": "#555", "marginBottom": "2px"}))
        return html.Div(blocks)

    return html.Div([
        html.Div([
            # Left — AI patterns
            html.Div([
                html.Div("DETECTED PATTERNS", style={
                    "fontSize": "10px", "color": "#888", "fontWeight": "700",
                    "letterSpacing": "0.05em", "marginBottom": "12px",
                }),
                render_insights(insights_text),
            ], style={"flex": "1.5", "paddingRight": "24px", "borderRight": "1px solid #e0e0e0"}),

            # Right — category breakdown
            html.Div([
                html.Div("CATEGORY BREAKDOWN", style={
                    "fontSize": "10px", "color": "#888", "fontWeight": "700",
                    "letterSpacing": "0.05em", "marginBottom": "12px",
                }),
                category_panel,
            ], style={"flex": "1", "paddingLeft": "24px"}),
        ], style={"display": "flex"}),
    ])


# ── Callback: oldest open incidents ──────────────────────────────────────────
@callback(
    Output("oldest-incidents-panel", "children"),
    Input("filter-from-month",       "value"),
    Input("filter-to-month",         "value"),
)
def update_oldest(from_month, to_month):
    fdf = base_df[base_df["Status"].isin(PENDING_STATUSES)].copy()
    if from_month:
        fdf = fdf[fdf["month_year"] >= from_month]
    if to_month:
        fdf = fdf[fdf["month_year"] <= to_month]

    oldest = fdf.nlargest(5, "age_days")
    if oldest.empty:
        return html.Div("No open incidents.", style={"color": "#888", "fontSize": "13px"})

    rows = []
    for _, row in oldest.iterrows():
        age   = int(row["age_days"]) if pd.notna(row["age_days"]) else 0
        color = "#EF4444" if age > 7 else "#F59E0B" if age > 3 else "#888"
        desc  = str(row.get("Symptom", ""))
        short = desc[:60] + "..." if len(desc) > 60 else desc
        rows.append(html.Div([
            html.Div([
                html.Div(str(row.get("Incident ID", "")),
                         style={"fontWeight": "700", "fontSize": "13px"}),
                html.Div(short, style={"fontSize": "11px", "color": "#888", "marginTop": "2px"}),
                html.Div(str(row.get("Status", "")),
                         style={"fontSize": "10px", "color": "#4F46E5", "marginTop": "2px"}),
            ], style={"flex": "1"}),
            html.Div(f"{age} Days", style={"fontWeight": "700", "color": color, "fontSize": "13px"}),
        ], style={
            "display": "flex", "justifyContent": "space-between", "alignItems": "center",
            "padding": "10px 0", "borderBottom": "1px solid #f0f0f0",
        }))

    return html.Div(rows)


# ── Callback: check aged incidents every 10 min ───────────────────────────────
@callback(
    Output("aged-incidents-store", "data"),
    Input("notif-interval",        "n_intervals"),
)
def check_aged_incidents(n):
    open_df = base_df[base_df["Status"].isin(PENDING_STATUSES)].copy()
    aged    = open_df[open_df["age_days"] >= 1]
    result  = []
    for _, row in aged.iterrows():
        result.append({
            "id":      str(row.get("Incident ID", "")),
            "symptom": str(row.get("Symptom", ""))[:60],
            "age":     int(row["age_days"]) if pd.notna(row["age_days"]) else 0,
        })
    return result


# ── Clientside callback: store → browser notification ────────────────────────
dash.clientside_callback(
    """
    function(incidents) {
        if (!incidents || incidents.length === 0) return '';
        if (Notification.permission === 'default') {
            Notification.requestPermission().then(function(perm) {
                if (perm === 'granted') {
                    incidents.forEach(function(inc) {
                        new Notification('⚠️ Aged Incident: ' + inc.id, {
                            body: inc.symptom + ' — ' + inc.age + ' day(s) old',
                        });
                    });
                }
            });
        } else if (Notification.permission === 'granted') {
            incidents.forEach(function(inc) {
                new Notification('⚠️ Aged Incident: ' + inc.id, {
                    body: inc.symptom + ' — ' + inc.age + ' day(s) old',
                });
            });
        }
        return '';
    }
    """,
    Output("notif-trigger",        "children"),
    Input("aged-incidents-store",  "data"),
)


# ── Layout ────────────────────────────────────────────────────────────────────
def layout():
    return html.Div([

        dcc.Interval(id="notif-interval", interval=10 * 60 * 1000, n_intervals=0),
        html.Div(id="notif-trigger", style={"display": "none"}),
        dcc.Store(id="aged-incidents-store"),

        # Topbar
        html.Div([
            html.Span("Dashboards / Incident Report"),
            html.Div([
                html.Span("🔔", style={"padding": "12px 20px"}),
                html.Span("👤", style={"padding": "12px 20px"}),
            ]),
        ], style={
            "display": "flex", "justifyContent": "space-between", "alignItems": "center",
            "padding": "16px 24px", "borderBottom": "1px solid #e0e0e0", "background": "#F3F3F3",
        }),

        html.H1("Incident Report Overview", style={"padding": "12px 20px", "marginBottom": "0px"}),

        # Month filter
        html.Div([
            html.Div([
                html.Div("FROM", style={"fontSize": "10px", "color": "#888",
                                        "fontWeight": "700", "marginBottom": "4px"}),
                dcc.Dropdown(id="filter-from-month", options=month_options,
                             value=min_month, clearable=False, style={"width": "180px"}),
            ]),
            html.Div([
                html.Div("TO", style={"fontSize": "10px", "color": "#888",
                                      "fontWeight": "700", "marginBottom": "4px"}),
                dcc.Dropdown(id="filter-to-month", options=month_options,
                             value=max_month, clearable=False, style={"width": "180px"}),
            ]),
        ], style={"display": "flex", "gap": "16px", "padding": "16px 24px",
                  "background": "white", "borderBottom": "1px solid #e0e0e0", "alignItems": "flex-end"}),

        # KPI cards
                html.Div([
            kpi_card("Active Incidents",  active,          "Active in pipeline"),
            kpi_card("TOTAL RESOLVED",    res,         "Closed successfully"),
            kpi_card("Fullfilment rate",         f"{rate}%",    "fullfillment rate in %"),
            kpi_card("rejected", rej,      "Rejected"),
        ], style={"display": "flex", "gap": "16px", "padding": "24px"}),

        # Charts
        html.Div([
            html.Div([
                html.Div([

                    html.Div("Monthly Volume Trends", style={"fontWeight": "600", "marginBottom": "12px"}),
                    dcc.Graph(id="graph-month", config={"displayModeBar": False}),
                ], style={"flex": "1", **CARD}),
                html.Div([
                    html.Div("Incidents by Location", style={"fontWeight": "600", "marginBottom": "12px"}),
                    dcc.Graph(id="graph-location", config={"displayModeBar": False}),
                ], style={"flex": "1", **CARD}),
                html.Div([
                    html.Div("Status Distribution", style={"fontWeight": "600", "marginBottom": "12px"}),
                    dcc.Graph(id="graph-status", config={"displayModeBar": False}),
                ], style={"flex": "1", **CARD}),
            ], style={"display": "flex", "gap": "16px", "marginBottom": "16px"}),

            html.Div([
                html.Div([
                    html.Div("Classification Distribution", style={"fontWeight": "600", "marginBottom": "12px"}),
                    dcc.Graph(id="graph-classification", config={"displayModeBar": False}),
                ], style={"flex": "1", **CARD}),
                html.Div([
                    html.Div("Workgroup Distribution", style={"fontWeight": "600", "marginBottom": "12px"}),
                    dcc.Graph(id="graph-workgroup", config={"displayModeBar": False}),
                ], style={"flex": "1", **CARD}),
            ], style={"display": "flex", "gap": "16px", "marginBottom": "16px"}),
        ], style={"padding": "0 24px"}),

        # AI Insights
        html.Div([
            html.Div([
                html.Div([
                    html.Span("✦ ", style={"fontSize": "18px"}),
                    html.Span("AI Insights", style={"fontWeight": "700", "fontSize": "16px"}),
                ], style={"marginBottom": "16px", "display": "flex", "alignItems": "center"}),
                dcc.Dropdown(
                            id="insights-range-incident",
                            options=[
                                {"label": "1 Week",    "value": 1},
                                {"label": "2 Weeks",   "value": 2},
                                {"label": "3 Weeks",   "value": 3},
                                {"label": "4 Weeks",   "value": 4},
                                {"label": "6 Months",  "value": 26},
                                {"label": "All Time",  "value": 9999},
                            ],
                            value=1,
                            clearable=False,
                            style={"width": "200px", "marginBottom": "16px"},
                        ),
                html.Div(
                    id="ai-insights-output-incident",
                    children="Select a time range to generate insights.",
                    style={"fontSize": "13px", "color": "#888"},
                ),
            ], style={"padding": "20px", **CARD}),
        ], style={"padding": "24px 24px 0"}),

        # Oldest open incidents
        html.Div([
            html.Div([
                html.Div("⏱ Oldest Open Incidents",
                         style={"fontWeight": "700", "fontSize": "15px", "marginBottom": "16px"}),
                html.Div(id="oldest-incidents-panel"),
            ], style={"padding": "20px", **CARD}),
        ], style={"padding": "16px 24px 40px"}),

    ])