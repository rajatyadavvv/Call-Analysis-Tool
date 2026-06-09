import dash
from dash import html, dcc, callback, Output, Input, State
from datetime import datetime
import pandas as pd
from db import get_connection

dash.register_page(__name__, path="/notifications", name="Notifications")

CARD   = {"background": "white", "border": "1px solid #E8EDF2", "borderRadius": "8px", "padding": "20px"}
ACCENT = "#546DE5"

PENDING_CR  = ["Requested", "Approved", "Pre-Migration Approved", "Pre-Migration Approved 1",
               "Migration date finalized", "Pending Further Review", "UAT Approved", "Draft", "Approved by Owner"]
PENDING_SR  = ["In-Progress", "Pending", "Pending for Approval"]
PENDING_INC = ["In-Progress", "Pending", "Open"]

# Age thresholds (days)
CR_THRESHOLD  = 3
SR_THRESHOLD  = 3
INC_THRESHOLD = 1


def fetch_alerts(existing_read_ids: set = None) -> list:
    """
    Fetch aged alerts from DB.
    existing_read_ids: set of IDs already marked read — preserved across refreshes.
    """
    if existing_read_ids is None:
        existing_read_ids = set()

    alerts = []
    now    = datetime.now()

    try:
        conn = get_connection()

        # ── CR ────────────────────────────────────────────────────────────────
        try:
            cr = pd.read_sql("SELECT * FROM cr_report", conn)
            cr = cr[cr["Owner Work Group Name"].isin(["IT Support (ALC)", "IT Support (EVSM)"])].copy()
            cr["_date"] = pd.to_datetime(cr["Request Registration Time"], errors="coerce")
            cr["_age"]  = (now - cr["_date"]).dt.days
            for _, row in cr[cr["Status"].isin(PENDING_CR) & (cr["_age"] >= CR_THRESHOLD)].iterrows():
                age   = int(row["_age"]) if pd.notna(row["_age"]) else 0
                aid   = f"CR-{row.get('Change Request Id','')}"
                alerts.append({
                    "id":     aid,
                    "source": "CR",
                    "title":  str(row.get("Description", ""))[:60],
                    "age":    age,
                    "status": str(row.get("Status", "")),
                    "level":  "critical" if age > 14 else "warning",
                    "time":   str(row["_date"].date()) if pd.notna(row["_date"]) else "",
                    "read":   aid in existing_read_ids,
                })
        except Exception:
            pass

        # ── SR ────────────────────────────────────────────────────────────────
        try:
            sr = pd.read_sql("SELECT * FROM sr_report", conn)
            sr = sr[sr["Workgroup"].isin(["IT Support (ALC)", "IT Support (EVSM)"])].copy()
            sr["_date"] = pd.to_datetime(sr["LogTime"], format="%m/%d/%Y %H:%M", errors="coerce")
            sr["_age"]  = (now - sr["_date"]).dt.days
            for _, row in sr[sr["Status"].isin(PENDING_SR) & (sr["_age"] >= SR_THRESHOLD)].iterrows():
                age = int(row["_age"]) if pd.notna(row["_age"]) else 0
                aid = f"SR-{row.get('Service Request ID','')}"
                alerts.append({
                    "id":     aid,
                    "source": "SR",
                    "title":  str(row.get("Subject", ""))[:60],
                    "age":    age,
                    "status": str(row.get("Status", "")),
                    "level":  "critical" if age > 7 else "warning",
                    "time":   str(row["_date"].date()) if pd.notna(row["_date"]) else "",
                    "read":   aid in existing_read_ids,
                })
        except Exception:
            pass

        # ── Incident ──────────────────────────────────────────────────────────
        try:
            inc = pd.read_sql("SELECT * FROM incident_report", conn)
            inc = inc[inc["Workgroup"].isin(["IT Support (ALC)", "IT Support (EVSM)"])].copy()
            inc["_date"] = pd.to_datetime(inc["Log Time"], format="%d/%m/%y %H:%M", errors="coerce")
            inc["_age"]  = (now - inc["_date"]).dt.days
            for _, row in inc[inc["Status"].isin(PENDING_INC) & (inc["_age"] >= INC_THRESHOLD)].iterrows():
                age = int(row["_age"]) if pd.notna(row["_age"]) else 0
                aid = f"INC-{row.get('Incident ID','')}"
                alerts.append({
                    "id":     aid,
                    "source": "Incident",
                    "title":  str(row.get("Symptom", ""))[:60],
                    "age":    age,
                    "status": str(row.get("Status", "")),
                    "level":  "critical" if age > 3 else "warning",
                    "time":   str(row["_date"].date()) if pd.notna(row["_date"]) else "",
                    "read":   aid in existing_read_ids,
                })
        except Exception:
            pass

        conn.close()
    except Exception:
        pass

    return sorted(alerts, key=lambda x: (x["read"], -x["age"]))


def alert_card(alert: dict) -> html.Div:
    level_colors = {
        "critical": {"bg": "#FEF2F2", "border": "#FCA5A5", "dot": "#EF4444", "label": "CRITICAL"},
        "warning":  {"bg": "#FFFBEB", "border": "#FCD34D", "dot": "#F59E0B", "label": "WARNING"},
    }
    s  = level_colors.get(alert["level"], level_colors["warning"])
    sc = {"CR": "#546DE5", "SR": "#10B981", "Incident": "#F59E0B"}.get(alert["source"], "#778CA3")
    is_read = alert.get("read", False)

    return html.Div([
        html.Div([
            html.Div([
                html.Div(style={
                    "width": "8px", "height": "8px", "borderRadius": "50%",
                    "background": "#A4B0BE" if is_read else s["dot"],
                    "marginRight": "10px", "marginTop": "3px", "flexShrink": "0",
                }),
                html.Div([
                    html.Div([
                        html.Span(alert["id"], style={"fontWeight": "700", "fontSize": "13px",
                                                       "color": "#A4B0BE" if is_read else "#2F3542"}),
                        html.Span(alert["source"], style={
                            "fontSize": "10px", "fontWeight": "700", "color": "white",
                            "background": sc if not is_read else "#A4B0BE",
                            "padding": "2px 7px", "borderRadius": "4px", "marginLeft": "8px",
                        }),
                        html.Span(s["label"], style={
                            "fontSize": "9px", "fontWeight": "700",
                            "color": "#A4B0BE" if is_read else s["dot"],
                            "background": "#F1F4F7" if is_read else s["bg"],
                            "border": f"1px solid {'#E8EDF2' if is_read else s['border']}",
                            "padding": "2px 6px", "borderRadius": "4px", "marginLeft": "6px",
                        }),
                        html.Span("✓ Read", style={
                            "fontSize": "9px", "color": "#10B981", "marginLeft": "8px", "fontWeight": "600",
                        }) if is_read else None,
                    ], style={"display": "flex", "alignItems": "center", "marginBottom": "3px"}),
                    html.Div(alert["title"], style={
                        "fontSize": "12px", "color": "#A4B0BE" if is_read else "#57606F", "lineHeight": "1.4",
                    }),
                    html.Div([
                        html.Span(f"Status: {alert['status']}", style={"fontSize": "10px", "color": "#A4B0BE", "marginRight": "12px"}),
                        html.Span(f"Opened: {alert['time']}", style={"fontSize": "10px", "color": "#A4B0BE"}),
                    ], style={"marginTop": "4px"}),
                ]),
            ], style={"display": "flex", "alignItems": "flex-start", "flex": "1"}),

            html.Div(f"{alert['age']}d", style={
                "fontWeight": "700", "fontSize": "14px", "flexShrink": "0",
                "color": "#A4B0BE" if is_read else ("#EF4444" if alert["level"] == "critical" else "#F59E0B"),
            }),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-start"}),
    ], style={
        "background":   "#F9FAFB" if is_read else (s["bg"]),
        "border":       f"1px solid {'#E8EDF2' if is_read else s['border']}",
        "borderRadius": "8px",
        "padding":      "14px 16px",
        "marginBottom": "10px",
        "opacity":      "0.7" if is_read else "1",
        "transition":   "opacity 0.2s",
    })


def layout():
    # On page load, read state comes from global store — but we don't have it yet
    # so we load fresh with no read state; the callback will merge immediately
    alerts = fetch_alerts()

    total    = len(alerts)
    critical = sum(1 for a in alerts if a["level"] == "critical")
    by_src   = {k: sum(1 for a in alerts if a["source"] == k) for k in ["CR", "SR", "Incident"]}

    return html.Div(style={"background": "#F7F9FC", "minHeight": "100vh"}, children=[

        # Topbar
        html.Div([
            html.Span("Notifications", style={"fontWeight": "700", "fontSize": "15px", "color": "#2F3542"}),
            html.Div([
                html.Span(f"Alerts: CR ≥{CR_THRESHOLD}d  •  SR ≥{SR_THRESHOLD}d  •  Incident ≥{INC_THRESHOLD}d",
                          style={"fontSize": "11px", "color": "#A4B0BE"}),
            ]),
        ], style={"padding": "16px 24px", "borderBottom": "1px solid #E8EDF2", "background": "white",
                  "display": "flex", "justifyContent": "space-between", "alignItems": "center"}),

        html.Div(style={"padding": "24px"}, children=[

            # KPI row
            html.Div([
                html.Div([
                    html.Div("TOTAL ALERTS", style={"fontSize": "10px", "color": "#A4B0BE", "fontWeight": "700", "marginBottom": "6px"}),
                    html.Div(id="kpi-total", children=str(total),
                             style={"fontSize": "28px", "fontWeight": "800", "color": "#2F3542"}),
                ], style={"flex": "1", "padding": "18px 20px", "background": "white",
                          "border": "1px solid #E8EDF2", "borderRadius": "8px"}),
                html.Div([
                    html.Div("CRITICAL", style={"fontSize": "10px", "color": "#EF4444", "fontWeight": "700", "marginBottom": "6px"}),
                    html.Div(id="kpi-critical", children=str(critical),
                             style={"fontSize": "28px", "fontWeight": "800", "color": "#EF4444"}),
                ], style={"flex": "1", "padding": "18px 20px", "background": "#FEF2F2",
                          "border": "1px solid #FCA5A5", "borderRadius": "8px"}),
                html.Div([
                    html.Div("FROM CR", style={"fontSize": "10px", "color": "#546DE5", "fontWeight": "700", "marginBottom": "6px"}),
                    html.Div(id="kpi-cr", children=str(by_src["CR"]),
                             style={"fontSize": "28px", "fontWeight": "800", "color": "#546DE5"}),
                ], style={"flex": "1", "padding": "18px 20px", "background": "white",
                          "border": "1px solid #E8EDF2", "borderRadius": "8px"}),
                html.Div([
                    html.Div("FROM SR", style={"fontSize": "10px", "color": "#10B981", "fontWeight": "700", "marginBottom": "6px"}),
                    html.Div(id="kpi-sr", children=str(by_src["SR"]),
                             style={"fontSize": "28px", "fontWeight": "800", "color": "#10B981"}),
                ], style={"flex": "1", "padding": "18px 20px", "background": "white",
                          "border": "1px solid #E8EDF2", "borderRadius": "8px"}),
                html.Div([
                    html.Div("FROM INCIDENT", style={"fontSize": "10px", "color": "#F59E0B", "fontWeight": "700", "marginBottom": "6px"}),
                    html.Div(id="kpi-inc", children=str(by_src["Incident"]),
                             style={"fontSize": "28px", "fontWeight": "800", "color": "#F59E0B"}),
                ], style={"flex": "1", "padding": "18px 20px", "background": "white",
                          "border": "1px solid #E8EDF2", "borderRadius": "8px"}),
            ], style={"display": "flex", "gap": "14px", "marginBottom": "24px"}),

            # Filter bar
            html.Div([
                html.Div("FILTER:", style={"fontSize": "10px", "color": "#A4B0BE",
                                            "fontWeight": "700", "marginRight": "12px", "alignSelf": "center"}),
                dcc.RadioItems(
                    id="notif-filter",
                    options=[
                        {"label": "All",      "value": "All"},
                        {"label": "CR",       "value": "CR"},
                        {"label": "SR",       "value": "SR"},
                        {"label": "Incident", "value": "Incident"},
                        {"label": "Unread",   "value": "Unread"},
                    ],
                    value="All", inline=True,
                    inputStyle={"marginRight": "5px"},
                    labelStyle={"marginRight": "18px", "fontSize": "13px",
                                "color": "#57606F", "cursor": "pointer"},
                ),
                html.Div(style={"flex": "1"}),
                html.Button("Mark All Read", id="mark-read-btn", n_clicks=0, style={
                    "padding": "7px 14px", "background": "white", "color": ACCENT,
                    "border": f"1px solid {ACCENT}", "borderRadius": "6px",
                    "cursor": "pointer", "fontSize": "12px", "fontWeight": "600",
                }),
                html.Button("Refresh", id="notif-refresh-btn", n_clicks=0, style={
                    "padding": "7px 14px", "background": ACCENT, "color": "white",
                    "border": "none", "borderRadius": "6px",
                    "cursor": "pointer", "fontSize": "12px", "fontWeight": "600",
                    "marginLeft": "8px",
                }),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "16px",
                      "padding": "12px 16px", "background": "white",
                      "border": "1px solid #E8EDF2", "borderRadius": "8px"}),

            # Alert list
            html.Div(id="notif-list", children=[alert_card(a) for a in alerts]),
        ]),

        # Local store — persists read state within the session on this page
        dcc.Store(id="notif-read-store", storage_type="session", data=[]),
    ])


@callback(
    Output("notif-list",       "children"),
    Output("notif-read-store", "data"),
    Output("global-notif-store","data"),
    Output("kpi-total",        "children"),
    Output("kpi-critical",     "children"),
    Output("kpi-cr",           "children"),
    Output("kpi-sr",           "children"),
    Output("kpi-inc",          "children"),
    Input("notif-filter",      "value"),
    Input("mark-read-btn",     "n_clicks"),
    Input("notif-refresh-btn", "n_clicks"),
    State("notif-read-store",  "data"),
    prevent_initial_call=False,
)
def update_notifications(source_filter, mark_read, refresh, read_ids_stored):
    ctx         = dash.callback_context
    triggered   = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else ""
    read_ids    = set(read_ids_stored or [])

    if triggered == "mark-read-btn":
        # Fetch fresh and mark all read
        alerts   = fetch_alerts(read_ids)
        read_ids = {a["id"] for a in alerts}
        alerts   = [{**a, "read": True} for a in alerts]
    elif triggered == "notif-refresh-btn":
        # Re-fetch from DB but preserve existing read state
        alerts = fetch_alerts(read_ids)
    else:
        # Filter change or initial load — use existing read state
        alerts = fetch_alerts(read_ids)

    # Update KPIs
    total    = len(alerts)
    critical = sum(1 for a in alerts if a["level"] == "critical")
    by_src   = {k: sum(1 for a in alerts if a["source"] == k) for k in ["CR", "SR", "Incident"]}

    # Apply filter
    if source_filter == "Unread":
        filtered = [a for a in alerts if not a.get("read")]
    elif source_filter != "All":
        filtered = [a for a in alerts if a["source"] == source_filter]
    else:
        filtered = alerts

    cards = [alert_card(a) for a in filtered] if filtered else [
        html.Div("No alerts for the selected filter.",
                 style={"color": "#A4B0BE", "fontSize": "13px", "padding": "20px"})
    ]

    return (
        cards,
        list(read_ids),
        alerts,                    # update global store for badge count
        str(total),
        str(critical),
        str(by_src["CR"]),
        str(by_src["SR"]),
        str(by_src["Incident"]),
    )