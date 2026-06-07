import dash
from dash import html, dcc, callback, Output, Input, State
from datetime import datetime, timedelta
import pandas as pd
from db import get_connection

dash.register_page(__name__, path="/notifications", name="Notifications")

# ── Palette ───────────────────────────────────────────────────────────────────
CARD  = {"background": "white", "border": "1px solid #E8EDF2", "borderRadius": "8px", "padding": "20px"}
ACCENT = "#546DE5"

PENDING_CR  = ["Requested", "Approved", "Pre-Migration Approved", "Pre-Migration Approved 1",
               "Migration date finalized", "Pending Further Review", "UAT Approved", "Draft", "Approved by Owner"]
PENDING_SR  = ["In-Progress", "Pending", "Pending for Approval"]
PENDING_INC = ["In-Progress", "Pending", "Open"]


def fetch_alerts():
    """Pull aged items from all three tables and return as a list of alert dicts."""
    alerts = []
    now    = datetime.now()

    try:
        conn = get_connection()

        # CR — aged > 14 days
        try:
            cr = pd.read_sql("SELECT * FROM cr_report", conn)
            cr = cr[cr["Owner Work Group Name"].isin(["IT Support (ALC)", "IT Support (EVSM)"])].copy()
            cr["_date"] = pd.to_datetime(cr["Request Registration Time"], errors="coerce")
            cr["_age"]  = (now - cr["_date"]).dt.days
            cr_aged = cr[cr["Status"].isin(PENDING_CR) & (cr["_age"] >= 14)]
            for _, row in cr_aged.iterrows():
                age = int(row["_age"]) if pd.notna(row["_age"]) else 0
                alerts.append({
                    "id":       f"CR-{row.get('Change Request Id','')}",
                    "source":   "CR",
                    "title":    str(row.get("Description", ""))[:60],
                    "age":      age,
                    "status":   str(row.get("Status", "")),
                    "level":    "critical" if age > 30 else "warning",
                    "time":     str(row["_date"].date()) if pd.notna(row["_date"]) else "",
                    "read":     False,
                })
        except Exception:
            pass

        # SR — aged > 5 days
        try:
            sr = pd.read_sql("SELECT * FROM sr_report", conn)
            sr = sr[sr["Workgroup"].isin(["IT Support (ALC)", "IT Support (EVSM)"])].copy()
            sr["_date"] = pd.to_datetime(sr["LogTime"], format="%m/%d/%Y %H:%M", errors="coerce")
            sr["_age"]  = (now - sr["_date"]).dt.days
            sr_aged = sr[sr["Status"].isin(PENDING_SR) & (sr["_age"] >= 5)]
            for _, row in sr_aged.iterrows():
                age = int(row["_age"]) if pd.notna(row["_age"]) else 0
                alerts.append({
                    "id":     f"SR-{row.get('Service Request ID','')}",
                    "source": "SR",
                    "title":  str(row.get("Subject", ""))[:60],
                    "age":    age,
                    "status": str(row.get("Status", "")),
                    "level":  "critical" if age > 10 else "warning",
                    "time":   str(row["_date"].date()) if pd.notna(row["_date"]) else "",
                    "read":   False,
                })
        except Exception:
            pass

        # Incident — aged > 1 day
        try:
            inc = pd.read_sql("SELECT * FROM incident_report", conn)
            inc = inc[inc["Workgroup"].isin(["IT Support (ALC)", "IT Support (EVSM)"])].copy()
            inc["_date"] = pd.to_datetime(inc["Log Time"], format="%d/%m/%y %H:%M", errors="coerce")
            inc["_age"]  = (now - inc["_date"]).dt.days
            inc_aged = inc[inc["Status"].isin(PENDING_INC) & (inc["_age"] >= 1)]
            for _, row in inc_aged.iterrows():
                age = int(row["_age"]) if pd.notna(row["_age"]) else 0
                alerts.append({
                    "id":     f"INC-{row.get('Incident ID','')}",
                    "source": "Incident",
                    "title":  str(row.get("Symptom", ""))[:60],
                    "age":    age,
                    "status": str(row.get("Status", "")),
                    "level":  "critical" if age > 7 else "warning",
                    "time":   str(row["_date"].date()) if pd.notna(row["_date"]) else "",
                    "read":   False,
                })
        except Exception:
            pass

        conn.close()
    except Exception:
        pass

    return sorted(alerts, key=lambda x: x["age"], reverse=True)


def alert_card(alert):
    level_colors = {
        "critical": {"bg": "#FEF2F2", "border": "#FCA5A5", "dot": "#EF4444", "label": "CRITICAL"},
        "warning":  {"bg": "#FFFBEB", "border": "#FCD34D", "dot": "#F59E0B", "label": "WARNING"},
    }
    s = level_colors.get(alert["level"], level_colors["warning"])

    source_colors = {"CR": "#546DE5", "SR": "#10B981", "Incident": "#F59E0B"}
    sc = source_colors.get(alert["source"], "#778CA3")

    return html.Div([
        html.Div([
            # Left — dot + id + source badge
            html.Div([
                html.Div(style={
                    "width": "8px", "height": "8px", "borderRadius": "50%",
                    "background": s["dot"], "marginRight": "10px", "marginTop": "2px", "flexShrink": "0",
                }),
                html.Div([
                    html.Div([
                        html.Span(alert["id"], style={"fontWeight": "700", "fontSize": "13px", "color": "#2F3542"}),
                        html.Span(alert["source"], style={
                            "fontSize": "10px", "fontWeight": "700", "color": "white",
                            "background": sc, "padding": "2px 7px", "borderRadius": "4px",
                            "marginLeft": "8px",
                        }),
                        html.Span(s["label"], style={
                            "fontSize": "9px", "fontWeight": "700", "color": s["dot"],
                            "background": s["bg"], "border": f"1px solid {s['border']}",
                            "padding": "2px 6px", "borderRadius": "4px", "marginLeft": "6px",
                        }),
                    ], style={"display": "flex", "alignItems": "center", "marginBottom": "3px"}),
                    html.Div(alert["title"], style={"fontSize": "12px", "color": "#57606F", "lineHeight": "1.4"}),
                    html.Div([
                        html.Span(f"Status: {alert['status']}", style={"fontSize": "10px", "color": "#A4B0BE", "marginRight": "12px"}),
                        html.Span(f"Opened: {alert['time']}", style={"fontSize": "10px", "color": "#A4B0BE"}),
                    ], style={"marginTop": "4px"}),
                ]),
            ], style={"display": "flex", "alignItems": "flex-start", "flex": "1"}),

            # Right — age
            html.Div(f"{alert['age']}d", style={
                "fontWeight": "700", "fontSize": "14px",
                "color": "#EF4444" if alert["level"] == "critical" else "#F59E0B",
                "flexShrink": "0",
            }),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-start"}),
    ], style={
        "background":    s["bg"] if not alert.get("read") else "white",
        "border":        f"1px solid {s['border'] if not alert.get('read') else '#E8EDF2'}",
        "borderRadius":  "8px",
        "padding":       "14px 16px",
        "marginBottom":  "10px",
        "opacity":       "0.6" if alert.get("read") else "1",
    })


def layout():
    alerts = fetch_alerts()

    # Summary counts
    total    = len(alerts)
    critical = sum(1 for a in alerts if a["level"] == "critical")
    by_src   = {"CR": 0, "SR": 0, "Incident": 0}
    for a in alerts:
        by_src[a["source"]] = by_src.get(a["source"], 0) + 1

    return html.Div(style={"background": "#F7F9FC", "minHeight": "100vh"}, children=[

        # Topbar
        html.Div([
            html.Span("Notifications", style={"fontWeight": "700", "fontSize": "15px", "color": "#2F3542"}),
        ], style={"padding": "16px 24px", "borderBottom": "1px solid #E8EDF2",
                  "background": "white", "display": "flex", "alignItems": "center"}),

        html.Div(style={"padding": "24px"}, children=[

            # Summary KPI row
            html.Div([
                html.Div([
                    html.Div("TOTAL ALERTS", style={"fontSize": "10px", "color": "#A4B0BE", "fontWeight": "700", "marginBottom": "6px"}),
                    html.Div(str(total), style={"fontSize": "28px", "fontWeight": "800", "color": "#2F3542"}),
                ], style={"flex": "1", "padding": "18px 20px", **{"background": "white", "border": "1px solid #E8EDF2", "borderRadius": "8px"}}),
                html.Div([
                    html.Div("CRITICAL", style={"fontSize": "10px", "color": "#EF4444", "fontWeight": "700", "marginBottom": "6px"}),
                    html.Div(str(critical), style={"fontSize": "28px", "fontWeight": "800", "color": "#EF4444"}),
                ], style={"flex": "1", "padding": "18px 20px", **{"background": "#FEF2F2", "border": "1px solid #FCA5A5", "borderRadius": "8px"}}),
                html.Div([
                    html.Div("FROM CR", style={"fontSize": "10px", "color": "#546DE5", "fontWeight": "700", "marginBottom": "6px"}),
                    html.Div(str(by_src["CR"]), style={"fontSize": "28px", "fontWeight": "800", "color": "#546DE5"}),
                ], style={"flex": "1", "padding": "18px 20px", **{"background": "white", "border": "1px solid #E8EDF2", "borderRadius": "8px"}}),
                html.Div([
                    html.Div("FROM SR", style={"fontSize": "10px", "color": "#10B981", "fontWeight": "700", "marginBottom": "6px"}),
                    html.Div(str(by_src["SR"]), style={"fontSize": "28px", "fontWeight": "800", "color": "#10B981"}),
                ], style={"flex": "1", "padding": "18px 20px", **{"background": "white", "border": "1px solid #E8EDF2", "borderRadius": "8px"}}),
                html.Div([
                    html.Div("FROM INCIDENT", style={"fontSize": "10px", "color": "#F59E0B", "fontWeight": "700", "marginBottom": "6px"}),
                    html.Div(str(by_src["Incident"]), style={"fontSize": "28px", "fontWeight": "800", "color": "#F59E0B"}),
                ], style={"flex": "1", "padding": "18px 20px", **{"background": "white", "border": "1px solid #E8EDF2", "borderRadius": "8px"}}),
            ], style={"display": "flex", "gap": "14px", "marginBottom": "24px"}),

            # Filter + list
            html.Div([
                # Filter bar
                html.Div([
                    html.Div("FILTER BY SOURCE:", style={"fontSize": "10px", "color": "#A4B0BE",
                                                          "fontWeight": "700", "marginRight": "12px",
                                                          "alignSelf": "center"}),
                    dcc.RadioItems(
                        id="notif-filter",
                        options=[
                            {"label": "All",      "value": "All"},
                            {"label": "CR",       "value": "CR"},
                            {"label": "SR",       "value": "SR"},
                            {"label": "Incident", "value": "Incident"},
                        ],
                        value="All",
                        inline=True,
                        inputStyle={"marginRight": "5px"},
                        labelStyle={"marginRight": "18px", "fontSize": "13px",
                                    "color": "#57606F", "cursor": "pointer"},
                    ),
                    html.Div(style={"flex": "1"}),
                    html.Button("Mark All Read", id="mark-read-btn", n_clicks=0, style={
                        "padding": "7px 14px", "background": "white", "color": "#546DE5",
                        "border": "1px solid #546DE5", "borderRadius": "6px",
                        "cursor": "pointer", "fontSize": "12px", "fontWeight": "600",
                    }),
                    html.Button("Refresh", id="notif-refresh-btn", n_clicks=0, style={
                        "padding": "7px 14px", "background": "#546DE5", "color": "white",
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
        ]),

        # Hidden store with all alerts for this page
        dcc.Store(id="notif-page-store", data=alerts),
    ])


@callback(
    Output("notif-list",       "children"),
    Output("global-notif-store","data"),
    Input("notif-filter",      "value"),
    Input("mark-read-btn",     "n_clicks"),
    Input("notif-refresh-btn", "n_clicks"),
    State("notif-page-store",  "data"),
    prevent_initial_call=False,
)
def filter_notifications(source_filter, mark_read, refresh, stored):
    ctx = dash.callback_context
    triggered = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else ""

    if triggered == "notif-refresh-btn":
        alerts = fetch_alerts()
    else:
        alerts = stored or fetch_alerts()

    if triggered == "mark-read-btn":
        alerts = [{**a, "read": True} for a in alerts]

    filtered = alerts if source_filter == "All" else [a for a in alerts if a["source"] == source_filter]

    if not filtered:
        cards = [html.Div("No alerts for the selected filter.",
                          style={"color": "#A4B0BE", "fontSize": "13px", "padding": "20px"})]
    else:
        cards = [alert_card(a) for a in filtered]

    return cards, alerts