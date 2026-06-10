import dash
import pandas as pd
from dash import html, dcc, callback, Output, Input, State
import plotly.express as px
from db import get_connection
from datetime import datetime, timedelta
from openai import OpenAI
import os
import dotenv

dotenv.load_dotenv()

dash.register_page(__name__, path="/incident")

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)

# ── Notion/Linear palette ─────────────────────────────────────────────────────
PIE_COLORS = ["#2F3542", "#546DE5", "#778CA3", "#A4B0BE", "#CDD6E0", "#E8EDF2"]
BAR_COLOR  = "#546DE5"
LINE_COLOR = "#546DE5"

CHART_LAYOUT = dict(
    plot_bgcolor="white", paper_bgcolor="white",
    height=300, margin=dict(l=0, r=0, t=10, b=0),
    xaxis_title="", yaxis_title="",
    font=dict(family="Inter, DM Sans, sans-serif", size=11, color="#57606F"),
)

# ── Load data ─────────────────────────────────────────────────────────────────
conn = get_connection()
df_raw = pd.read_sql("SELECT * FROM incident_report", conn)
conn.close()

base_df = df_raw[df_raw["Workgroup"].isin(["IT Support (ALC)", "IT Support (EVSM)"])].reset_index(drop=True)
base_df["date"] = pd.to_datetime(base_df["Log Time"], format="%m/%d/%Y %H:%M", errors="coerce")
base_df["month_year"] = base_df["date"].dt.strftime("%Y-%m")
base_df["month_year_label"] = base_df["date"].dt.strftime("%B %Y")
base_df["age_days"] = (datetime.now() - base_df["date"]).dt.days

min_date = base_df["date"].min().date() if not base_df.empty else datetime.now().date()
max_date = base_df["date"].max().date() if not base_df.empty else datetime.now().date()

PENDING_STATUSES = ["In-Progress", "Pending", "Open"]

INCIDENT_CATEGORIES = [
    "System Bug",
    "Data Request",
    "Lack of Functional/Operational Knowledge",
    "Master Data Request",
]

CARD = {"background": "white", "border": "1px solid #E8EDF2", "borderRadius": "8px", "padding": "16px"}


def kpi_card(label, value, delta):
    return html.Div([
        html.Div(label,      style={"fontSize": "11px", "color": "#778CA3", "marginBottom": "8px",
                                    "fontWeight": "600", "letterSpacing": "0.04em"}),
        html.Div(str(value), style={"fontSize": "30px", "fontWeight": "800", "marginBottom": "6px", "color": "#2F3542"}),
        html.Div(delta,      style={"fontSize": "12px", "color": "#A4B0BE"}),
    ], style={"flex": "1", "padding": "22px", **CARD})


def build_figures(fdf):
    def base_bar(df, x, y, horizontal=False):
        fig = px.bar(df, x=x if not horizontal else y, y=y if not horizontal else x,
                     orientation="h" if horizontal else "v",
                     color_discrete_sequence=[BAR_COLOR])
        fig.update_layout(**CHART_LAYOUT)
        fig.update_traces(marker_line_width=0)
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=True, gridcolor="#F1F4F7")
        return fig

    fig_location       = base_bar(fdf["Location"].value_counts().reset_index(), "Location", "count")
    fig_classification = base_bar(fdf["Classification"].value_counts().reset_index(), "Classification", "count")
    fig_workgroup      = px.bar(fdf["Workgroup"].value_counts().reset_index(), "count", "Workgroup", orientation="h", color_discrete_sequence=[BAR_COLOR])
    fig_workgroup.update_yaxes(showgrid=True, gridcolor="#F1F4F7")

    fig_status = px.pie(
        fdf["Status"].value_counts().reset_index(),
        names="Status", values="count", hole=0.45,
        color_discrete_sequence=PIE_COLORS,
    )
    fig_status.update_layout(
        height=300, margin=dict(l=0, r=0, t=10, b=40),
        legend=dict(orientation="h", y=-0.15, font=dict(size=10)),
        paper_bgcolor="white", font=dict(size=11, color="#57606F"),
    )
    fig_status.update_traces(textfont_color="white", textfont_size=11)

    # Monthly — sorted ascending
    month_counts = (
        fdf.groupby(["month_year", "month_year_label"])
        .size().reset_index(name="count")
        .sort_values("month_year")
    )
    fig_month = px.line(month_counts, x="month_year_label", y="count", markers=True,
                        color_discrete_sequence=[LINE_COLOR])
    fig_month.update_layout(**CHART_LAYOUT)
    fig_month.update_xaxes(
        categoryorder="array",
        categoryarray=month_counts["month_year_label"].tolist(),
        showgrid=False,
    )
    fig_month.update_yaxes(showgrid=True, gridcolor="#F1F4F7")
    fig_month.update_traces(line=dict(width=2), marker=dict(size=6))

    return fig_location, fig_status, fig_classification, fig_workgroup, fig_month


def build_kpis(fdf):
    active = int(fdf["Status"].isin(PENDING_STATUSES).sum())
    res    = int(fdf["Status"].isin(["Resolved", "Closed"]).sum())
    rej    = int((fdf["Status"] == "Rejected").sum())
    rate   = round(res / len(fdf) * 100, 1) if len(fdf) > 0 else 0
    return active, res, rej, rate


# ── Callback: date filter → charts + KPIs ────────────────────────────────────
@callback(
    Output("inc-kpi-row",          "children"),
    Output("graph-month",          "figure"),
    Output("graph-location",       "figure"),
    Output("graph-status",         "figure"),
    Output("graph-classification", "figure"),
    Output("graph-workgroup",      "figure"),
    Output("oldest-incidents-panel","children"),
    Input("inc-start-date",        "date"),
    Input("inc-end-date",          "date"),
)
def update_charts(start_date, end_date):
    fdf = base_df.copy()
    if start_date and end_date:
        fdf = fdf[(fdf["date"] >= pd.to_datetime(start_date)) &
                  (fdf["date"] <= pd.to_datetime(end_date).replace(hour=23, minute=59, second=59))].copy()

    if fdf.empty:
        empty_fig = px.bar(title="No data")
        empty_kpis = html.Div([kpi_card(l, 0, "") for l in
                                ["ACTIVE", "RESOLVED", "REJECTED", "FULFILMENT RATE"]],
                               style={"display": "flex", "gap": "16px", "padding": "24px"})
        return empty_kpis, empty_fig, empty_fig, empty_fig, empty_fig, empty_fig, html.Div()

    active, res, rej, rate = build_kpis(fdf)
    fig_loc, fig_stat, fig_cls, fig_wg, fig_mo = build_figures(fdf)

    kpis = html.Div([
        kpi_card("ACTIVE INCIDENTS", active,    "Active in pipeline"),
        kpi_card("TOTAL RESOLVED",   res,       "Closed successfully"),
        kpi_card("FULFILMENT RATE",  f"{rate}%","Resolved / Total"),
        kpi_card("REJECTED",         rej,       "— Stable"),
    ], style={"display": "flex", "gap": "16px", "padding": "24px"})

    # Oldest
    pending_sel = fdf[fdf["Status"].isin(PENDING_STATUSES)].copy()
    oldest_sel  = pending_sel.nlargest(5, "age_days") if not pending_sel.empty else pd.DataFrame()

    rows = []
    if not oldest_sel.empty:
        for _, row in oldest_sel.iterrows():
            age   = int(row["age_days"]) if pd.notna(row["age_days"]) else 0
            color = "#EF4444" if age > 7 else "#F59E0B" if age > 3 else "#A4B0BE"
            desc  = str(row.get("Symptom", ""))
            short = desc[:60] + "..." if len(desc) > 60 else desc
            rows.append(html.Div([
                html.Div([
                    html.Div(str(row.get("Incident ID", "")),
                             style={"fontWeight": "700", "fontSize": "13px", "color": "#2F3542"}),
                    html.Div(short, style={"fontSize": "11px", "color": "#778CA3", "marginTop": "2px"}),
                    html.Div(str(row.get("Status", "")),
                             style={"fontSize": "10px", "color": "#546DE5", "marginTop": "2px"}),
                ], style={"flex": "1"}),
                html.Div(f"{age} Days", style={"fontWeight": "700", "color": color, "fontSize": "13px"}),
            ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center",
                      "padding": "10px 0", "borderBottom": "1px solid #F1F4F7"}))
    else:
        rows = [html.Div("No open incidents.", style={"color": "#A4B0BE", "fontSize": "12px"})]

    oldest_panel = html.Div(rows)
    return kpis, fig_mo, fig_loc, fig_stat, fig_cls, fig_wg, oldest_panel


# Callback: AI insights — generate button only
@callback(
    Output("ai-insights-output-incident", "children"),
    Input("inc-generate-btn",             "n_clicks"),
    State("insights-range-incident",      "value"),
    prevent_initial_call=True,
)
def update_insights(n_clicks, weeks):
    conn_cb = get_connection()
    df_cb   = pd.read_sql("SELECT * FROM incident_report", conn_cb)
    conn_cb.close()

    df_cb = df_cb[df_cb["Workgroup"].isin(["IT Support (ALC)", "IT Support (EVSM)"])].reset_index(drop=True)
    df_cb["date"] = pd.to_datetime(df_cb["Log Time"], format="%d/%m/%y %H:%M", errors="coerce")

    now = df_cb["date"].max()

    if weeks == 9999:
        current  = df_cb.copy()
        previous = pd.DataFrame(columns=df_cb.columns)
    else:
        cutoff      = now - timedelta(weeks=weeks)
        current     = df_cb[df_cb["date"] >= cutoff].copy()
        prev_cutoff = cutoff - timedelta(weeks=4)
        previous    = df_cb[(df_cb["date"] >= prev_cutoff) & (df_cb["date"] < cutoff)].copy()

    if current.empty:
        return html.Div("No incidents found.", style={"color": "#A4B0BE", "fontSize": "13px"})

    # Category breakdown
    def count_cat(frame, cat):
        return int(frame["Classification"].str.contains(cat, case=False, na=False).sum())

    cat_rows = []
    for cat in INCIDENT_CATEGORIES:
        curr_c = count_cat(current, cat)
        prev_c = count_cat(previous, cat)
        chg    = round((curr_c - prev_c) / prev_c * 100, 1) if prev_c > 0 else (100.0 if curr_c > 0 else 0.0)
        trend  = "↑" if chg > 0 else ("↓" if chg < 0 else "→")
        tc     = "#EF4444" if chg > 0 else ("#10B981" if chg < 0 else "#A4B0BE")
        cat_rows.append(html.Div([
            html.Div(cat,                    style={"fontSize": "12px", "fontWeight": "600", "flex": "2", "color": "#2F3542"}),
            html.Div(str(curr_c),            style={"fontSize": "13px", "fontWeight": "800", "flex": "1", "textAlign": "center", "color": "#2F3542"}),
            html.Div(f"{trend} {abs(chg)}%", style={"fontSize": "12px", "color": tc, "fontWeight": "600", "flex": "1", "textAlign": "right"}),
        ], style={"display": "flex", "alignItems": "center", "padding": "8px 0", "borderBottom": "1px solid #F1F4F7"}))

    category_panel = html.Div([
        html.Div([
            html.Div("CATEGORY",   style={"fontSize": "10px", "color": "#A4B0BE", "fontWeight": "700", "flex": "2"}),
            html.Div("COUNT",      style={"fontSize": "10px", "color": "#A4B0BE", "fontWeight": "700", "flex": "1", "textAlign": "center"}),
            html.Div("VS PREV 4W", style={"fontSize": "10px", "color": "#A4B0BE", "fontWeight": "700", "flex": "1", "textAlign": "right"}),
        ], style={"display": "flex", "marginBottom": "4px"}),
        html.Div(cat_rows),
    ])

    open_inc     = current[current["Status"].isin(PENDING_STATUSES)].copy()
    resolved_inc = df_cb[df_cb["Status"].isin(["Resolved", "Closed"])].copy()

    def find_similar(symptom, resolved_df, top_n=3):
        if pd.isna(symptom) or not str(symptom).strip():
            return []
        keywords = [w for w in str(symptom).lower().split() if len(w) > 3]
        if not keywords:
            return []
        mask = resolved_df["Symptom"].str.lower().apply(lambda s: any(k in str(s) for k in keywords))
        return resolved_df[mask].head(top_n)[["Symptom", "Solution"]].to_dict("records")

    lines = []
    for _, row in open_inc.iterrows():
        similar      = find_similar(row.get("Symptom"), resolved_inc)
        similar_text = (" | Past solutions: " + "; ".join([s.get("Solution","") for s in similar if s.get("Solution")])) if similar else ""
        lines.append(
            f"Classification: {row.get('Classification','')} | "
            f"Priority: {row.get('Priority','')} | "
            f"Symptom: {row.get('Symptom','')}{similar_text}"
        )

    label = "all time" if weeks == 9999 else f"last {weeks} week(s)"
    prompt = f"""
You are an IT operations analyst. Analyze ALL these incidents from the {label}.
Categorize each into: System Bug / Data Request / Lack of Functional Knowledge / Master Data Request.
Find ALL unique patterns. Do not limit to 3.

Respond in EXACTLY this format:

CATEGORY SUMMARY:
System Bug: [count] - [High/Medium/Low]
Data Request: [count] - [High/Medium/Low]
Lack of Functional/Operational Knowledge: [count] - [High/Medium/Low]
Master Data Request: [count] - [High/Medium/Low]

PATTERNS:
PATTERN: [4-5 word title] | [High/Medium/Low]
[One sentence detail]
Suggested fix: [One sentence, use past solutions if available]

REDUCTION TIPS:
- [tip 1]
- [tip 2]
- [tip 3]

Incidents:
{chr(10).join(lines) if lines else "No open incidents — analyzing all current period incidents."}
"""

    try:
        response      = client.chat.completions.create(
            model="google/gemma-4-31b-it:free", max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        insights_text = response.choices[0].message.content
    except Exception as e:
        insights_text = f"Error: {str(e)}"

    def render_insights(text):
        blocks = []
        for line in text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("CATEGORY SUMMARY"):
                blocks.append(html.Div("CATEGORY SUMMARY", style={
                    "fontSize": "10px", "fontWeight": "700", "color": "#A4B0BE",
                    "letterSpacing": "0.05em", "marginTop": "8px", "marginBottom": "6px",
                }))
            elif line.startswith("PATTERNS"):
                blocks.append(html.Div("ALL PATTERNS", style={
                    "fontSize": "10px", "fontWeight": "700", "color": "#A4B0BE",
                    "letterSpacing": "0.05em", "marginTop": "16px", "marginBottom": "6px",
                }))
            elif line.startswith("PATTERN:"):
                parts = line.replace("PATTERN:", "").split("|")
                title = parts[0].strip()
                sev   = parts[1].strip() if len(parts) > 1 else ""
                sc    = "#EF4444" if "High" in sev else "#F59E0B" if "Medium" in sev else "#10B981"
                blocks.append(html.Div([
                    html.Span(title, style={"fontWeight": "700", "fontSize": "13px", "color": "#2F3542"}),
                    html.Span(sev,   style={"fontSize": "10px", "color": sc, "fontWeight": "700",
                                            "marginLeft": "8px", "padding": "2px 6px",
                                            "background": "#F1F4F7", "borderRadius": "4px"}),
                ], style={"marginTop": "12px", "marginBottom": "2px", "display": "flex", "alignItems": "center"}))
            elif line.startswith("Suggested fix:"):
                blocks.append(html.Div(line, style={
                    "fontSize": "11px", "color": "#546DE5", "fontStyle": "italic",
                    "borderLeft": "3px solid #546DE5", "paddingLeft": "8px", "marginTop": "4px",
                }))
            elif line.startswith("REDUCTION TIPS"):
                blocks.append(html.Div("REDUCTION TIPS", style={
                    "fontSize": "10px", "fontWeight": "700", "color": "#A4B0BE",
                    "letterSpacing": "0.05em", "marginTop": "16px", "marginBottom": "6px",
                }))
            elif line.startswith(("-", "•")):
                blocks.append(html.Div(line, style={"fontSize": "12px", "color": "#57606F", "marginBottom": "4px"}))
            elif any(cat in line for cat in ["System Bug", "Data Request", "Lack of", "Master Data"]):
                parts = line.split("-")
                cl    = parts[0].strip()
                sv    = parts[1].strip() if len(parts) > 1 else ""
                sc    = "#EF4444" if "High" in sv else "#F59E0B" if "Medium" in sv else "#10B981"
                blocks.append(html.Div([
                    html.Span(cl, style={"fontSize": "12px", "flex": "1", "color": "#2F3542"}),
                    html.Span(sv, style={"fontSize": "11px", "color": sc, "fontWeight": "700"}),
                ], style={"display": "flex", "justifyContent": "space-between",
                          "padding": "4px 0", "borderBottom": "1px solid #F1F4F7"}))
            else:
                blocks.append(html.Div(line, style={"fontSize": "12px", "color": "#778CA3", "marginBottom": "2px"}))
        return html.Div(blocks)

    return html.Div([
        html.Div([
            html.Div([
                html.Div("DETECTED PATTERNS", style={
                    "fontSize": "10px", "color": "#A4B0BE", "fontWeight": "700",
                    "letterSpacing": "0.05em", "marginBottom": "12px",
                }),
                render_insights(insights_text),
            ], style={"flex": "1.5", "paddingRight": "24px", "borderRight": "1px solid #E8EDF2"}),
            html.Div([
                html.Div("CATEGORY BREAKDOWN", style={
                    "fontSize": "10px", "color": "#A4B0BE", "fontWeight": "700",
                    "letterSpacing": "0.05em", "marginBottom": "12px",
                }),
                category_panel,
            ], style={"flex": "1", "paddingLeft": "24px"}),
        ], style={"display": "flex"}),
    ])


@callback(
    Output("aged-incidents-store", "data"),
    Input("notif-interval",        "n_intervals"),
)
def check_aged_incidents(n):
    open_df = base_df[base_df["Status"].isin(PENDING_STATUSES)].copy()
    aged    = open_df[open_df["age_days"] >= 1]
    return [{"id": str(r.get("Incident ID","")), "symptom": str(r.get("Symptom",""))[:60],
             "age": int(r["age_days"]) if pd.notna(r["age_days"]) else 0}
            for _, r in aged.iterrows()]


dash.clientside_callback(
    """
    function(incidents) {
        if (!incidents || incidents.length === 0) return '';
        if (Notification.permission === 'default') {
            Notification.requestPermission().then(p => {
                if (p === 'granted') incidents.forEach(inc =>
                    new Notification('⚠️ Aged Incident: ' + inc.id, {body: inc.symptom + ' — ' + inc.age + ' day(s) old'}));
            });
        } else if (Notification.permission === 'granted') {
            incidents.forEach(inc => new Notification('⚠️ Aged Incident: ' + inc.id, {body: inc.symptom + ' — ' + inc.age + ' day(s) old'}));
        }
        return '';
    }
    """,
    Output("notif-trigger",       "children"),
    Input("aged-incidents-store", "data"),
)


def layout():
    return html.Div(style={"background": "#F7F9FC", "minHeight": "100vh"}, children=[

        dcc.Interval(id="notif-interval", interval=10 * 60 * 1000, n_intervals=0),
        html.Div(id="notif-trigger", style={"display": "none"}),
        dcc.Store(id="aged-incidents-store"),

        html.Div([
            html.Span("Dashboards / Incident Report", style={"color": "#57606F", "fontSize": "13px"}),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center",
                  "padding": "14px 24px", "borderBottom": "1px solid #E8EDF2", "background": "white"}),

        html.H1("Incident Report Overview",
                style={"padding": "16px 24px 4px", "fontSize": "22px", "fontWeight": "800", "color": "#2F3542"}),

        # Two date pickers
        html.Div([
            html.Div("FILTER BY DATE RANGE", style={"fontSize": "10px", "color": "#A4B0BE",
                                                     "fontWeight": "700", "marginBottom": "10px", "letterSpacing": "0.05em"}),
            html.Div([
                html.Div([
                    html.Div("FROM", style={"fontSize": "10px", "color": "#778CA3", "fontWeight": "700", "marginBottom": "4px"}),
                    dcc.DatePickerSingle(id="inc-start-date", date=min_date, display_format="MMM D, YYYY"),
                ]),
                html.Div([
                    html.Div("TO", style={"fontSize": "10px", "color": "#778CA3", "fontWeight": "700", "marginBottom": "4px"}),
                    dcc.DatePickerSingle(id="inc-end-date", date=max_date, display_format="MMM D, YYYY"),
                ]),
            ], style={"display": "flex", "gap": "24px", "alignItems": "flex-end"}),
        ], style={"padding": "16px 24px", "background": "white", "borderBottom": "1px solid #E8EDF2"}),

        # KPIs
        html.Div(id="inc-kpi-row", style={"display": "flex", "gap": "16px", "padding": "24px"}),

        # Charts
        html.Div([
            html.Div([
                html.Div([html.Div("Monthly Volume Trends", style={"fontWeight": "600", "marginBottom": "12px", "color": "#2F3542"}),
                          dcc.Graph(id="graph-month", config={"displayModeBar": False})], style={"flex": "1", **CARD}),
                html.Div([html.Div("Incidents by Location", style={"fontWeight": "600", "marginBottom": "12px", "color": "#2F3542"}),
                          dcc.Graph(id="graph-location", config={"displayModeBar": False})], style={"flex": "1", **CARD}),
                html.Div([html.Div("Status Distribution", style={"fontWeight": "600", "marginBottom": "12px", "color": "#2F3542"}),
                          dcc.Graph(id="graph-status", config={"displayModeBar": False})], style={"flex": "1", **CARD}),
            ], style={"display": "flex", "gap": "16px", "marginBottom": "16px"}),
            html.Div([
                html.Div([html.Div("Classification Distribution", style={"fontWeight": "600", "marginBottom": "12px", "color": "#2F3542"}),
                          dcc.Graph(id="graph-classification", config={"displayModeBar": False})], style={"flex": "1", **CARD}),
                html.Div([html.Div("Workgroup Distribution", style={"fontWeight": "600", "marginBottom": "12px", "color": "#2F3542"}),
                          dcc.Graph(id="graph-workgroup", config={"displayModeBar": False})], style={"flex": "1", **CARD}),
            ], style={"display": "flex", "gap": "16px", "marginBottom": "16px"}),
        ], style={"padding": "0 24px"}),

        # AI Insights + Oldest
        html.Div([
            html.Div([
                # Left — AI
                html.Div([
                    html.Div([
                        html.Span("✦ ", style={"fontSize": "16px", "color": "#080809"}),
                        html.Span("AI Insights", style={"fontWeight": "700", "fontSize": "15px", "color": "#2F3542"}),
                    ], style={"marginBottom": "12px", "display": "flex", "alignItems": "center"}),
                    html.Div("Analysis period (independent of date filter):", style={
                        "fontSize": "11px", "fontWeight": "600", "color": "#A4B0BE", "marginBottom": "6px",
                    }),
                    html.Div([
                        dcc.Dropdown(
                            id="insights-range-incident",
                            options=[
                                {"label": "1 Week",   "value": 1},
                                {"label": "2 Weeks",  "value": 2},
                                {"label": "3 Weeks",  "value": 3},
                                {"label": "4 Weeks",  "value": 4},
                                {"label": "6 Months", "value": 26},
                                {"label": "All Time", "value": 9999},
                            ],
                            value=1, clearable=False, style={"width": "150px"},
                        ),
                        html.Button("Generate Insights", id="inc-generate-btn", n_clicks=0, style={
                            "padding": "8px 16px", "background": "#0A0A0A", "color": "white",
                            "border": "none", "borderRadius": "6px", "cursor": "pointer",
                            "fontSize": "12px", "fontWeight": "600",
                        }),
                    ], style={"display": "flex", "gap": "10px", "alignItems": "center", "marginBottom": "16px"}),
                    dcc.Loading(
                        html.Div(id="ai-insights-output-incident",
                                 children="Select a period and click Generate Insights.",
                                 style={"fontSize": "13px", "color": "#A4B0BE"}),
                        type="circle", color="#0E0E0F",
                    ),
                ], style={"flex": "1.5", "paddingRight": "24px", "borderRight": "1px solid #E8EDF2"}),

                # Right — Oldest
                html.Div([
                    html.Div("⏱ OLDEST OPEN INCIDENTS", style={
                        "fontSize": "10px", "color": "#A4B0BE", "fontWeight": "700",
                        "letterSpacing": "0.05em", "marginBottom": "12px",
                    }),
                    html.Div(id="oldest-incidents-panel"),
                ], style={"flex": "1", "paddingLeft": "24px"}),
            ], style={"display": "flex"}),
        ], style={"padding": "24px", "background": "white", "margin": "0 24px 40px 24px",
                  "border": "1px solid #E8EDF2", "borderRadius": "8px"}),
    ])