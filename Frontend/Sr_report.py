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

# ── Load data ─────────────────────────────────────────────────────────────────
conn = get_connection()
df_raw = pd.read_sql("SELECT * FROM sr_report", conn)
conn.close()

base_df = df_raw[df_raw["Workgroup"].isin(["IT Support (ALC)", "IT Support (EVSM)"])].reset_index(drop=True)
base_df["date"] = pd.to_datetime(base_df["LogTime"], format="%m/%d/%Y %H:%M", errors="coerce")
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

PENDING_STATUSES = ["In-Progress", "Pending", "Pending for Approval"]

# ── Styling ───────────────────────────────────────────────────────────────────
CARD = {"background": "white", "border": "1px solid #e0e0e0", "borderRadius": "8px", "padding": "16px"}


def kpi_card(label, value, delta):
    return html.Div([
        html.Div(label,      style={"fontSize": "11px", "color": "#888", "marginBottom": "8px"}),
        html.Div(str(value), style={"fontSize": "32px", "fontWeight": "800", "marginBottom": "8px"}),
        html.Div(delta,      style={"fontSize": "12px", "color": "#888"}),
    ], style={"flex": "1", "padding": "24px", **CARD})


# ── Helper: build figures ─────────────────────────────────────────────────────
def build_figures(fdf):
    fig_location = px.bar(fdf["Location"].value_counts().reset_index(), x="Location", y="count")
    fig_location.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), xaxis_title="", yaxis_title="")

    fig_status = px.pie(fdf["Status"].value_counts().reset_index(), names="Status", values="count")

    fig_workgroup = px.bar(
        fdf["Workgroup"].value_counts().reset_index(),
        x="count", y="Workgroup", orientation="h",
    )
    fig_workgroup.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), xaxis_title="", yaxis_title="")

    # Monthly volume sorted correctly
    month_counts = (
        fdf.groupby(["month_year", "month_year_label"])
        .size()
        .reset_index(name="count")
        .sort_values("month_year")
    )
    fig_month = px.line(month_counts, x="month_year_label", y="count", markers=True)
    fig_month.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), xaxis_title="", yaxis_title="")
    fig_month.update_xaxes(categoryorder="array", categoryarray=month_counts["month_year_label"].tolist())

    # Aging chart — pending only
    pending = fdf[fdf["Status"].isin(PENDING_STATUSES)].copy()
    pending["age_days_calc"] = (datetime.now() - pending["date"]).dt.days
    bins   = [0, 1, 3, 5, 7, float("inf")]
    labels = ["0-1", "2-3", "4-5", "5-7", ">7"]
    pending["age_bucket"] = pd.cut(pending["age_days_calc"], bins=bins, labels=labels)
    fig_aging = px.bar(
        pending["age_bucket"].value_counts().sort_index().reset_index(),
        x="age_bucket", y="count",
        category_orders={"age_bucket": ["0-1", "2-3", "4-5", "5-7", ">7"]},
    )
    fig_aging.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), xaxis_title="", yaxis_title="")

    return fig_location, fig_status, fig_workgroup, fig_month, fig_aging


def build_kpis(fdf):
    active   = int(fdf["Status"].isin(PENDING_STATUSES).sum())
    res      = int((fdf["Status"] == "Resolved").sum())
    rej      = int((fdf["Status"] == "Rejected").sum())
    pend_app = int((fdf["Status"] == "Pending for Approval").sum())
    rate     = round(res / len(fdf) * 100, 1) if len(fdf) > 0 else 0
    return active, res, rej, pend_app, rate


# ── Render AI insights ────────────────────────────────────────────────────────
def render_insights(text):
    blocks = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("PATTERNS"):
            blocks.append(html.Div("ALL PATTERNS", style={
                "fontSize": "10px", "fontWeight": "700", "color": "#888",
                "letterSpacing": "0.05em", "marginTop": "8px", "marginBottom": "6px",
            }))
        elif line.startswith("PATTERN:"):
            parts     = line.replace("PATTERN:", "").split("|")
            title     = parts[0].strip() if len(parts) > 0 else line
            severity  = parts[1].strip() if len(parts) > 1 else ""
            sev_color = "#EF4444" if "High" in severity else "#F59E0B" if "Medium" in severity else "#10B981"
            blocks.append(html.Div([
                html.Span(title,    style={"fontWeight": "700", "fontSize": "13px", "color": "#1A1A2E"}),
                html.Span(severity, style={
                    "fontSize": "10px", "color": sev_color, "fontWeight": "700",
                    "marginLeft": "8px", "padding": "2px 6px",
                    "background": "#f5f5f5", "borderRadius": "4px",
                }),
            ], style={"marginTop": "12px", "marginBottom": "2px", "display": "flex", "alignItems": "center"}))
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
        elif line.startswith(("•", "-")):
            blocks.append(html.Div(line, style={"fontSize": "12px", "color": "#333", "marginBottom": "4px"}))
        else:
            blocks.append(html.Div(line, style={"fontSize": "12px", "color": "#555", "marginBottom": "2px"}))
    return html.Div(blocks)


# ── Callback: month filter → charts + KPIs ───────────────────────────────────
@callback(
    Output("sr-kpi-row",        "children"),
    Output("sr-graph-month",    "figure"),
    Output("sr-graph-location", "figure"),
    Output("sr-graph-status",   "figure"),
    Output("sr-graph-workgroup","figure"),
    Output("sr-graph-aging",    "figure"),
    Input("sr-filter-from",     "value"),
    Input("sr-filter-to",       "value"),
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

    active, res, rej, pend_app, rate = build_kpis(fdf)
    fig_loc, fig_stat, fig_wg, fig_mo, fig_aging = build_figures(fdf)

    kpis = html.Div([
        kpi_card("ACTIVE SRS",          active,    "Active in pipeline"),
        kpi_card("FULFILLMENT RATE",     f"{rate}%","Resolved / Total"),
        kpi_card("REJECTED",             rej,       "— Stable"),
        kpi_card("PENDING FOR APPROVAL", pend_app,  "Awaiting approval"),
    ], style={"display": "flex", "gap": "16px"})

    return kpis, fig_mo, fig_loc, fig_stat, fig_wg, fig_aging


# ── Callback: AI insights — only fires on button click ───────────────────────
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
        current  = df_cb.copy()
        previous = pd.DataFrame(columns=df_cb.columns)
    else:
        cutoff      = now - timedelta(weeks=weeks)
        current     = df_cb[df_cb["date"] >= cutoff].copy()
        prev_cutoff = cutoff - timedelta(weeks=4)
        previous    = df_cb[(df_cb["date"] >= prev_cutoff) & (df_cb["date"] < cutoff)].copy()

    if current.empty:
        return html.Div("No SRs found for selected range.", style={"color": "#888", "fontSize": "13px"})

    resolved_srs = df_cb[df_cb["Status"] == "Resolved"].copy()

    def find_similar(subject, resolved_df, top_n=3):
        if pd.isna(subject) or str(subject).strip() == "":
            return []
        keywords = [w for w in str(subject).lower().split() if len(w) > 3]
        if not keywords:
            return []
        mask = resolved_df["Subject"].str.lower().apply(
            lambda s: any(k in str(s) for k in keywords)
        )
        matches = resolved_df[mask].head(top_n)
        if "Solution" in matches.columns:
            return matches[["Subject", "Solution"]].to_dict("records")
        return matches[["Subject"]].to_dict("records")

    lines = []
    for _, row in current.iterrows():
        similar      = find_similar(row.get("Subject"), resolved_srs)
        similar_text = ""
        if similar:
            similar_text = " | Similar resolved: " + "; ".join([
                str(s.get("Solution", s.get("Subject", ""))) for s in similar
            ])
        lines.append(
            f"Status: {row.get('Status', '')} | "
            f"Category: {row.get('Category', '')} | "
            f"Subject: {row.get('Subject', '')} | "
            f"Solution: {row.get('Solution', '')}"
            f"{similar_text}"
        )

    if not lines:
        return html.Div("No SRs in selected range.", style={"color": "#888", "fontSize": "13px"})

    label = "all time" if weeks == 9999 else f"last {weeks} week(s)"
    prompt = f"""
You are an IT service desk analyst. Analyze ALL these Service Requests from the {label}.

Find ALL unique patterns. Do not limit to 3. One pattern per unique issue type.

Respond in EXACTLY this format with no extra text:

PATTERNS:
PATTERN: [4-5 word title] | [High/Medium/Low]
[One sentence detail]
Suggested fix: [One sentence, use similar resolved SRs if provided]

PATTERN: [4-5 word title] | [High/Medium/Low]
[One sentence detail]
Suggested fix: [One sentence]

REDUCTION TIPS:
- [tip 1]
- [tip 2]
- [tip 3]

Service Requests (Status | Category | Subject | Solution | Similar resolved):
{chr(10).join(lines)}
"""

    try:
        response = client.chat.completions.create(
            model="google/gemma-4-31b-it:free",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        insights_text = response.choices[0].message.content
    except Exception as e:
        insights_text = f"Error fetching insights: {str(e)}"

    return html.Div([
        html.Div([
            html.Div("DETECTED PATTERNS", style={
                "fontSize": "10px", "color": "#888", "fontWeight": "700",
                "letterSpacing": "0.05em", "marginBottom": "12px",
            }),
            render_insights(insights_text),
        ]),
    ])


# ── Callback: oldest open SRs ─────────────────────────────────────────────────
@callback(
    Output("sr-oldest-panel", "children"),
    Input("sr-filter-from",   "value"),
    Input("sr-filter-to",     "value"),
)
def update_oldest(from_month, to_month):
    fdf = base_df[base_df["Status"].isin(PENDING_STATUSES)].copy()
    if from_month:
        fdf = fdf[fdf["month_year"] >= from_month]
    if to_month:
        fdf = fdf[fdf["month_year"] <= to_month]

    oldest = fdf.nlargest(5, "age_days")
    if oldest.empty:
        return html.Div("No open SRs.", style={"color": "#888", "fontSize": "13px"})

    rows = []
    for _, row in oldest.iterrows():
        age   = int(row["age_days"]) if pd.notna(row["age_days"]) else 0
        color = "#EF4444" if age > 5 else "#F59E0B" if age > 2 else "#888"
        subj  = str(row.get("Subject", ""))
        short = subj[:60] + "..." if len(subj) > 60 else subj
        rows.append(html.Div([
            html.Div([
                html.Div(str(row.get("Service Request ID", "")),
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


# ── Callback: check aged SRs every 10 min ────────────────────────────────────
@callback(
    Output("sr-aged-store",   "data"),
    Input("sr-notif-interval","n_intervals"),
)
def check_aged_srs(n):
    open_df = base_df[base_df["Status"].isin(PENDING_STATUSES)].copy()
    aged    = open_df[open_df["age_days"] >= 5]
    result  = []
    for _, row in aged.iterrows():
        result.append({
            "id":      str(row.get("Service Request ID", "")),
            "subject": str(row.get("Subject", ""))[:60],
            "age":     int(row["age_days"]) if pd.notna(row["age_days"]) else 0,
        })
    return result


# ── Clientside callback: store → browser notification ────────────────────────
dash.clientside_callback(
    """
    function(srs) {
        if (!srs || srs.length === 0) return '';
        if (Notification.permission === 'default') {
            Notification.requestPermission().then(function(perm) {
                if (perm === 'granted') {
                    srs.forEach(function(sr) {
                        new Notification('⚠️ Aged SR: ' + sr.id, {
                            body: sr.subject + ' — ' + sr.age + ' day(s) old',
                        });
                    });
                }
            });
        } else if (Notification.permission === 'granted') {
            srs.forEach(function(sr) {
                new Notification('⚠️ Aged SR: ' + sr.id, {
                    body: sr.subject + ' — ' + sr.age + ' day(s) old',
                });
            });
        }
        return '';
    }
    """,
    Output("sr-notif-trigger", "children"),
    Input("sr-aged-store",     "data"),
)


# ── Layout ────────────────────────────────────────────────────────────────────
def layout():
    return html.Div([

        dcc.Interval(id="sr-notif-interval", interval=10 * 60 * 1000, n_intervals=0),
        html.Div(id="sr-notif-trigger", style={"display": "none"}),
        dcc.Store(id="sr-aged-store"),

        # Topbar
        html.Div([
            html.Span("Dashboards / Service Requests"),
            html.Div([
                html.Span("🔔", style={"padding": "12px 20px"}),
                html.Span("👤", style={"padding": "12px 20px"}),
            ]),
        ], style={
            "display": "flex", "justifyContent": "space-between", "alignItems": "center",
            "padding": "16px 24px", "borderBottom": "1px solid #e0e0e0", "background": "#F3F3F3",
        }),

        html.H1("Service Request (SR) Overview",
                style={"padding": "12px 20px", "marginBottom": "0px"}),

        # Month filter
        html.Div([
            html.Div([
                html.Div("FROM", style={"fontSize": "10px", "color": "#888",
                                        "fontWeight": "700", "marginBottom": "4px"}),
                dcc.Dropdown(id="sr-filter-from", options=month_options,
                             value=min_month, clearable=False, style={"width": "180px"}),
            ]),
            html.Div([
                html.Div("TO", style={"fontSize": "10px", "color": "#888",
                                      "fontWeight": "700", "marginBottom": "4px"}),
                dcc.Dropdown(id="sr-filter-to", options=month_options,
                             value=max_month, clearable=False, style={"width": "180px"}),
            ]),
        ], style={"display": "flex", "gap": "16px", "padding": "16px 24px",
                  "background": "white", "borderBottom": "1px solid #e0e0e0",
                  "alignItems": "flex-end"}),

        # KPI cards
        html.Div(id="sr-kpi-row", style={"display": "flex", "gap": "16px", "padding": "24px"}),

        # Charts
        html.Div([
            html.Div([
                html.Div([
                    html.Div("Monthly SR Volume", style={"fontWeight": "600", "marginBottom": "12px"}),
                    dcc.Graph(id="sr-graph-month", config={"displayModeBar": False}),
                ], style={"flex": "1", **CARD}),
                html.Div([
                    html.Div("SRs by Location", style={"fontWeight": "600", "marginBottom": "12px"}),
                    dcc.Graph(id="sr-graph-location", config={"displayModeBar": False}),
                ], style={"flex": "1", **CARD}),
                html.Div([
                    html.Div("Status Distribution", style={"fontWeight": "600", "marginBottom": "12px"}),
                    dcc.Graph(id="sr-graph-status", config={"displayModeBar": False}),
                ], style={"flex": "1", **CARD}),
            ], style={"display": "flex", "gap": "16px", "marginBottom": "16px"}),

            html.Div([
                html.Div([
                    html.Div("SR Aging Distribution", style={"fontWeight": "600", "marginBottom": "12px"}),
                    dcc.Graph(id="sr-graph-aging", config={"displayModeBar": False}),
                ], style={"flex": "1", **CARD}),
                html.Div([
                    html.Div("Workgroup Distribution", style={"fontWeight": "600", "marginBottom": "12px"}),
                    dcc.Graph(id="sr-graph-workgroup", config={"displayModeBar": False}),
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

                # Range + button row
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
                        value=1,
                        clearable=False,
                        style={"width": "160px"},
                    ),
                    html.Button(
                        "Generate Insights",
                        id="sr-generate-btn",
                        n_clicks=0,
                        style={
                            "padding":       "8px 18px",
                            "background":    "#1A1A2E",
                            "color":         "white",
                            "border":        "none",
                            "borderRadius":  "6px",
                            "cursor":        "pointer",
                            "fontSize":      "13px",
                            "fontWeight":    "600",
                        },
                    ),
                ], style={"display": "flex", "gap": "12px",
                          "alignItems": "center", "marginBottom": "16px"}),

                html.Div(
                    id="sr-ai-insights-output",
                    children="Select a time range and click Generate Insights.",
                    style={"fontSize": "13px", "color": "#888"},
                ),
            ], style={"padding": "20px", **CARD}),
        ], style={"padding": "24px 24px 0"}),

        # Oldest open SRs
        html.Div([
            html.Div([
                html.Div("⏱ Oldest Open SRs",
                         style={"fontWeight": "700", "fontSize": "15px", "marginBottom": "16px"}),
                html.Div(id="sr-oldest-panel"),
            ], style={"padding": "20px", **CARD}),
        ], style={"padding": "16px 24px 40px"}),

    ])