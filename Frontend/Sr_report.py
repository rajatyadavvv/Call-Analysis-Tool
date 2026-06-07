import dash
import pandas as pd
from dash import html, dcc, callback, Output, Input, State
import plotly.express as px
from datetime import datetime, timedelta
from openai import OpenAI
from db import get_connection
import os
import dotenv

dotenv.load_dotenv()

dash.register_page(__name__, path="/sr")

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)

# ── Notion/Linear color palette ──────────────────────────────────────────────
BLUE_GREY  = ["#2F3542", "#57606F", "#A4B0BE", "#CDD6E0", "#E8EDF2", "#F1F4F7"]
PIE_COLORS = ["#2F3542", "#546DE5", "#778CA3", "#A4B0BE", "#CDD6E0", "#E8EDF2"]
LINE_COLOR = "#546DE5"
BAR_COLOR  = "#546DE5"

# ── Load data ─────────────────────────────────────────────────────────────────
conn = get_connection()
df_raw = pd.read_sql("SELECT * FROM sr_report", conn)
conn.close()

base_df = df_raw[df_raw["Workgroup"].isin(["IT Support (ALC)", "IT Support (EVSM)"])].reset_index(drop=True)
base_df["date"] = pd.to_datetime(base_df["LogTime"], format="%m/%d/%Y %H:%M", errors="coerce")
base_df["month_year"] = base_df["date"].dt.strftime("%Y-%m")
base_df["month_year_label"] = base_df["date"].dt.strftime("%B %Y")
base_df["age_days"] = (datetime.now() - base_df["date"]).dt.days

min_date = base_df["date"].min().date() if not base_df.empty else datetime.now().date()
max_date = base_df["date"].max().date() if not base_df.empty else datetime.now().date()

PENDING_STATUSES = ["In-Progress", "Pending", "Pending for Approval"]

CARD = {"background": "white", "border": "1px solid #E8EDF2", "borderRadius": "8px", "padding": "16px"}

CHART_LAYOUT = dict(
    plot_bgcolor="white", paper_bgcolor="white",
    height=300, margin=dict(l=0, r=0, t=10, b=0),
    xaxis_title="", yaxis_title="",
    font=dict(family="Inter, DM Sans, sans-serif", size=11, color="#57606F"),
)


def kpi_card(label, value, delta):
    return html.Div([
        html.Div(label,      style={"fontSize": "11px", "color": "#778CA3", "marginBottom": "8px",
                                    "fontWeight": "600", "letterSpacing": "0.04em"}),
        html.Div(str(value), style={"fontSize": "30px", "fontWeight": "800", "marginBottom": "6px",
                                    "color": "#2F3542"}),
        html.Div(delta,      style={"fontSize": "12px", "color": "#A4B0BE"}),
    ], style={"flex": "1", "padding": "22px", **CARD})


def build_oldest_ui(oldest_df, empty_message):
    items = []
    if oldest_df is not None and not oldest_df.empty:
        for _, row in oldest_df.iterrows():
            age   = int(row["age_days"]) if pd.notna(row["age_days"]) else 0
            color = "#EF4444" if age > 5 else "#F59E0B" if age > 2 else "#A4B0BE"
            subj  = str(row.get("Subject", ""))
            short = subj[:50] + "..." if len(subj) > 50 else subj
            items.append(html.Div([
                html.Div([
                    html.Div(str(row.get("Service Request ID", "")),
                             style={"fontWeight": "700", "fontSize": "13px", "color": "#2F3542"}),
                    html.Div(short, style={"fontSize": "11px", "color": "#778CA3", "marginTop": "2px"}),
                    html.Div(str(row.get("Status", "")),
                             style={"fontSize": "10px", "color": "#546DE5", "marginTop": "2px"}),
                ], style={"flex": "1"}),
                html.Div(f"{age} Days", style={"fontWeight": "700", "color": color, "fontSize": "13px"}),
            ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center",
                      "padding": "10px 0", "borderBottom": "1px solid #F1F4F7"}))
    if not items:
        items = [html.Div(empty_message, style={"color": "#A4B0BE", "fontSize": "12px", "marginTop": "10px"})]
    return items


def build_figures(fdf):
    def base_bar(df, x, y, horizontal=False):
        if horizontal:
            fig = px.bar(df, x=x, y=y, orientation="h", color_discrete_sequence=[BAR_COLOR])
        else:
            fig = px.bar(df, x=x, y=y, color_discrete_sequence=[BAR_COLOR])
        fig.update_layout(**CHART_LAYOUT)
        fig.update_traces(marker_line_width=0)
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=True, gridcolor="#F1F4F7")
        return fig

    fig_classification = base_bar(fdf["Classification"].value_counts().reset_index(), "Classification", "count")
    fig_location       = base_bar(fdf["Location"].value_counts().reset_index(), "Location", "count")
    fig_workgroup      = base_bar(fdf["Workgroup"].value_counts().reset_index(), "count", "Workgroup", horizontal=True)

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

    # Aging
    pending = fdf[fdf["Status"].isin(PENDING_STATUSES)].copy()
    pending["age_days_calc"] = (datetime.now() - pending["date"]).dt.days
    bins   = [0, 1, 3, 5, 7, float("inf")]
    labels = ["0-1", "2-3", "4-5", "5-7", ">7"]
    pending["age_bucket"] = pd.cut(pending["age_days_calc"], bins=bins, labels=labels)
    fig_aging = px.bar(
        pending["age_bucket"].value_counts().sort_index().reset_index(),
        x="age_bucket", y="count",
        category_orders={"age_bucket": labels},
        color_discrete_sequence=[BAR_COLOR],
    )
    fig_aging.update_layout(**CHART_LAYOUT)
    fig_aging.update_traces(marker_line_width=0)
    fig_aging.update_xaxes(showgrid=False)
    fig_aging.update_yaxes(showgrid=True, gridcolor="#F1F4F7")

    return fig_classification, fig_location, fig_status, fig_workgroup, fig_month, fig_aging


def build_kpis(fdf):
    active   = int(fdf["Status"].isin(PENDING_STATUSES).sum())
    res      = int((fdf["Status"] == "Resolved").sum())
    rej      = int((fdf["Status"] == "Rejected").sum())
    pend_app = int((fdf["Status"] == "Pending for Approval").sum())
    rate     = round(res / len(fdf) * 100, 1) if len(fdf) > 0 else 0
    return active, res, rej, pend_app, rate


def render_insights(text):
    blocks = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("PATTERN:"):
            parts    = line.replace("PATTERN:", "").split("|")
            title    = parts[0].strip()
            severity = parts[1].strip() if len(parts) > 1 else ""
            sc       = "#EF4444" if "High" in severity else "#F59E0B" if "Medium" in severity else "#10B981"
            blocks.append(html.Div([
                html.Span(title,    style={"fontWeight": "700", "fontSize": "13px", "color": "#2F3542"}),
                html.Span(severity, style={"fontSize": "10px", "color": sc, "fontWeight": "700",
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
        elif line.startswith(("•", "-")):
            blocks.append(html.Div(line, style={"fontSize": "12px", "color": "#57606F", "marginBottom": "4px"}))
        else:
            blocks.append(html.Div(line, style={"fontSize": "12px", "color": "#778CA3", "marginBottom": "2px"}))
    return html.Div(blocks)


@callback(
    Output("sr-kpi-row",             "children"),
    Output("sr-graph-month",         "figure"),
    Output("sr-graph-location",      "figure"),
    Output("sr-graph-classification","figure"),
    Output("sr-graph-status",        "figure"),
    Output("sr-graph-workgroup",     "figure"),
    Output("sr-graph-aging",         "figure"),
    Output("sr-oldest-output",       "children"),
    Input("sr-start-date", "date"),
    Input("sr-end-date",   "date"),
)
def update_dashboard(start_date, end_date):
    fdf = base_df.copy()
    if start_date and end_date:
        fdf = fdf[(fdf["date"] >= pd.to_datetime(start_date)) &
                  (fdf["date"] <= pd.to_datetime(end_date).replace(hour=23, minute=59, second=59))].copy()

    if fdf.empty:
        empty_fig = px.bar(title="No data for selected range")
        empty_kpis = html.Div([kpi_card(l, 0, "") for l in
                                ["ACTIVE SRS","FULFILLMENT RATE","REJECTED","PENDING APPROVAL"]],
                               style={"display": "flex", "gap": "16px"})
        return empty_kpis, empty_fig, empty_fig, empty_fig, empty_fig, empty_fig, empty_fig, html.Div()

    active, res, rej, pend_app, rate = build_kpis(fdf)
    fig_cls, fig_loc, fig_stat, fig_wg, fig_mo, fig_aging = build_figures(fdf)

    kpis = html.Div([
        kpi_card("ACTIVE SRS",           active,    "Active in pipeline"),
        kpi_card("FULFILLMENT RATE",      f"{rate}%","Resolved / Total"),
        kpi_card("REJECTED",              rej,       "— Stable"),
        kpi_card("PENDING FOR APPROVAL",  pend_app,  "Awaiting approval"),
    ], style={"display": "flex", "gap": "16px"})

    pending_sel = fdf[fdf["Status"].isin(PENDING_STATUSES)].copy()
    oldest_sel  = pending_sel.nlargest(3, "age_days") if not pending_sel.empty else pd.DataFrame()
    pending_all = base_df[base_df["Status"].isin(PENDING_STATUSES)].copy()
    oldest_all  = pending_all.nlargest(3, "age_days") if not pending_all.empty else pd.DataFrame()

    oldest_layout = html.Div([
        html.Div("OLDEST PENDING (SELECTED RANGE)", style={
            "fontSize": "10px", "color": "#A4B0BE", "fontWeight": "700",
            "marginBottom": "8px", "letterSpacing": "0.05em",
        }),
        html.Div(build_oldest_ui(oldest_sel, "No pending SRs for this timeframe."), style={"marginBottom": "24px"}),
        html.Div("OLDEST PENDING (ALL TIME)", style={
            "fontSize": "10px", "color": "#A4B0BE", "fontWeight": "700",
            "marginBottom": "8px", "letterSpacing": "0.05em",
        }),
        html.Div(build_oldest_ui(oldest_all, "No pending SRs overall.")),
    ])

    return kpis, fig_mo, fig_loc, fig_cls, fig_stat, fig_wg, fig_aging, oldest_layout


@callback(
    Output("sr-ai-insights-output", "children"),
    Input("sr-generate-btn",        "n_clicks"),
    State("sr-insights-range",      "value"),
    prevent_initial_call=True,
)
def update_insights(n_clicks, weeks):
    conn_cb = get_connection()
    df_cb   = pd.read_sql("SELECT * FROM sr_report", conn_cb)
    conn_cb.close()

    df_cb = df_cb[df_cb["Workgroup"].isin(["IT Support (ALC)", "IT Support (EVSM)"])].reset_index(drop=True)
    df_cb["date"] = pd.to_datetime(df_cb["LogTime"], format="%m/%d/%Y %H:%M", errors="coerce")
    now = df_cb["date"].max()

    if weeks == 9999:
        current = df_cb.copy()
    else:
        cutoff  = now - timedelta(weeks=weeks)
        current = df_cb[df_cb["date"] >= cutoff].copy()

    if current.empty:
        return html.Div("No SRs found.", style={"color": "#A4B0BE", "fontSize": "13px"})

    resolved_srs = df_cb[df_cb["Status"] == "Resolved"].copy()

    def find_similar(subject, resolved_df, top_n=3):
        if pd.isna(subject) or not str(subject).strip():
            return []
        keywords = [w for w in str(subject).lower().split() if len(w) > 3]
        if not keywords:
            return []
        mask = resolved_df["Subject"].str.lower().apply(lambda s: any(k in str(s) for k in keywords))
        matches = resolved_df[mask].head(top_n)
        return matches[["Subject", "Solution"]].to_dict("records") if "Solution" in matches.columns else matches[["Subject"]].to_dict("records")

    lines = []
    for _, row in current.iterrows():
        similar      = find_similar(row.get("Subject"), resolved_srs)
        similar_text = (" | Similar resolved: " + "; ".join([str(s.get("Solution", s.get("Subject", ""))) for s in similar])) if similar else ""
        lines.append(
            f"Status: {row.get('Status','')} | Category: {row.get('Category','')} | "
            f"Classification: {row.get('Classification','')} | Subject: {row.get('Subject','')} | "
            f"Solution: {row.get('Solution','')}{similar_text}"
        )

    label = "all time" if weeks == 9999 else f"last {weeks} week(s)"
    prompt = f"""
You are a Senior IT service desk analyst. Analyze ALL these Service Requests from the {label}.
Find ALL unique patterns. Do not limit to 3. One pattern per unique issue type.

Respond in EXACTLY this format with no extra text:

PATTERN: [4-5 word title] | [High/Medium/Low]
[One sentence detail]
Suggested fix: [One sentence]

REDUCTION TIPS:
- [tip 1]
- [tip 2]
- [tip 3]

Service Requests:
{chr(10).join(lines)}
"""
    try:
        response      = client.chat.completions.create(
            model="google/gemma-4-31b-it:free", max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        insights_text = response.choices[0].message.content
    except Exception as e:
        insights_text = f"Error: {str(e)}"

    return html.Div([
        html.Div("DETECTED PATTERNS", style={
            "fontSize": "10px", "color": "#A4B0BE", "fontWeight": "700",
            "letterSpacing": "0.05em", "marginBottom": "12px",
        }),
        render_insights(insights_text),
    ])


@callback(
    Output("sr-aged-store",    "data"),
    Input("sr-notif-interval", "n_intervals"),
)
def check_aged_srs(n):
    open_df = base_df[base_df["Status"].isin(PENDING_STATUSES)].copy()
    aged    = open_df[open_df["age_days"] >= 5]
    return [{"id": str(r.get("Service Request ID","")), "subject": str(r.get("Subject",""))[:60],
             "age": int(r["age_days"]) if pd.notna(r["age_days"]) else 0}
            for _, r in aged.iterrows()]


dash.clientside_callback(
    """
    function(srs) {
        if (!srs || srs.length === 0) return '';
        if (Notification.permission === 'default') {
            Notification.requestPermission().then(p => {
                if (p === 'granted') srs.forEach(sr =>
                    new Notification('⚠️ Aged SR: ' + sr.id, {body: sr.subject + ' — ' + sr.age + ' day(s) old'}));
            });
        } else if (Notification.permission === 'granted') {
            srs.forEach(sr => new Notification('⚠️ Aged SR: ' + sr.id, {body: sr.subject + ' — ' + sr.age + ' day(s) old'}));
        }
        return '';
    }
    """,
    Output("sr-notif-trigger", "children"),
    Input("sr-aged-store",     "data"),
)


def layout():
    return html.Div(style={"background": "#F7F9FC", "minHeight": "100vh"}, children=[

        dcc.Interval(id="sr-notif-interval", interval=10 * 60 * 1000, n_intervals=0),
        html.Div(id="sr-notif-trigger", style={"display": "none"}),
        dcc.Store(id="sr-aged-store"),

        html.Div([
            html.Span("Dashboards / Service Requests", style={"color": "#57606F", "fontSize": "13px"}),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center",
                  "padding": "14px 24px", "borderBottom": "1px solid #E8EDF2", "background": "white"}),

        html.H1("Service Request (SR) Overview",
                style={"padding": "16px 24px 4px", "fontSize": "22px", "fontWeight": "800", "color": "#2F3542"}),

        # Date pickers
        html.Div([
            html.Div("FILTER BY DATE RANGE", style={"fontSize": "10px", "color": "#A4B0BE",
                                                     "fontWeight": "700", "marginBottom": "10px", "letterSpacing": "0.05em"}),
            html.Div([
                html.Div([
                    html.Div("FROM", style={"fontSize": "10px", "color": "#778CA3", "fontWeight": "700", "marginBottom": "4px"}),
                    dcc.DatePickerSingle(id="sr-start-date", date=min_date, display_format="MMM D, YYYY"),
                ]),
                html.Div([
                    html.Div("TO", style={"fontSize": "10px", "color": "#778CA3", "fontWeight": "700", "marginBottom": "4px"}),
                    dcc.DatePickerSingle(id="sr-end-date", date=max_date, display_format="MMM D, YYYY"),
                ]),
            ], style={"display": "flex", "gap": "24px", "alignItems": "flex-end"}),
        ], style={"padding": "16px 24px", "background": "white", "borderBottom": "1px solid #E8EDF2"}),

        html.Div(id="sr-kpi-row", style={"display": "flex", "gap": "16px", "padding": "24px"}),

        html.Div([
            html.Div([
                html.Div([html.Div("Monthly SR Volume", style={"fontWeight": "600", "marginBottom": "12px", "color": "#2F3542"}),
                          dcc.Graph(id="sr-graph-month", config={"displayModeBar": False})], style={"flex": "1", **CARD}),
                html.Div([html.Div("SRs by Location", style={"fontWeight": "600", "marginBottom": "12px", "color": "#2F3542"}),
                          dcc.Graph(id="sr-graph-location", config={"displayModeBar": False})], style={"flex": "1", **CARD}),
            ], style={"display": "flex", "gap": "16px", "marginBottom": "16px"}),
            html.Div([
                html.Div([html.Div("Classification Distribution", style={"fontWeight": "600", "marginBottom": "12px", "color": "#2F3542"}),
                          dcc.Graph(id="sr-graph-classification", config={"displayModeBar": False})], style={"flex": "1", **CARD}),
                html.Div([html.Div("Status Distribution", style={"fontWeight": "600", "marginBottom": "12px", "color": "#2F3542"}),
                          dcc.Graph(id="sr-graph-status", config={"displayModeBar": False})], style={"flex": "1", **CARD}),
            ], style={"display": "flex", "gap": "16px", "marginBottom": "16px"}),
            html.Div([
                html.Div([html.Div("SR Aging Distribution", style={"fontWeight": "600", "marginBottom": "12px", "color": "#2F3542"}),
                          dcc.Graph(id="sr-graph-aging", config={"displayModeBar": False})], style={"flex": "1", **CARD}),
                html.Div([html.Div("Workgroup Distribution", style={"fontWeight": "600", "marginBottom": "12px", "color": "#2F3542"}),
                          dcc.Graph(id="sr-graph-workgroup", config={"displayModeBar": False})], style={"flex": "1", **CARD}),
            ], style={"display": "flex", "gap": "16px", "marginBottom": "16px"}),
        ], style={"padding": "0 24px"}),

        # AI + Oldest
        html.Div([
            html.Div([
                html.Div([
                    html.Div([
                        html.Span("✦ ", style={"fontSize": "16px", "color": "#0A0A0A"}),
                        html.Span("AI Insights", style={"fontWeight": "700", "fontSize": "15px", "color": "#2F3542"}),
                    ], style={"marginBottom": "12px", "display": "flex", "alignItems": "center"}),
                    html.Div("Analysis period (independent of date filter):", style={
                        "fontSize": "11px", "fontWeight": "600", "color": "#A4B0BE", "marginBottom": "6px",
                    }),
                    html.Div([
                        dcc.Dropdown(
                            id="sr-insights-range",
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
                        html.Button("Generate Insights", id="sr-generate-btn", n_clicks=0, style={
                            "padding": "8px 16px", "background": "#01030E", "color": "white",
                            "border": "none", "borderRadius": "6px", "cursor": "pointer",
                            "fontSize": "12px", "fontWeight": "600",
                        }),
                    ], style={"display": "flex", "gap": "10px", "alignItems": "center", "marginBottom": "16px"}),
                    dcc.Loading(
                        html.Div(id="sr-ai-insights-output",
                                 children="Select a period and click Generate Insights.",
                                 style={"fontSize": "13px", "color": "#A4B0BE"}),
                        type="circle", color="#546DE5",
                    ),
                ], style={"flex": "1", "paddingRight": "24px", "borderRight": "1px solid #E8EDF2"}),

                html.Div([html.Div(id="sr-oldest-output")], style={"flex": "1", "paddingLeft": "24px"}),
            ], style={"display": "flex"}),
        ], style={"padding": "24px", "background": "white", "margin": "0 24px 40px 24px",
                  "border": "1px solid #E8EDF2", "borderRadius": "8px"}),
    ])