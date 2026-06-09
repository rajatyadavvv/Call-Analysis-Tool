import dash
from dash import html, dcc, callback, Output, Input
from datetime import datetime
import requests

dash.register_page(__name__, path="/plm", name="PLM")


# ACCENT = "#546DE5"
# CARD   = {"background": "white", "border": "1px solid #E8EDF2", "borderRadius": "8px", "padding": "20px"}

# # ── Device registry ───────────────────────────────────────────────────────────
# DEVICES = [
#     {
#         "id":    "evsm-01",
#         "label": "EVSM Computer",
#         "url":   "http://10.148.254.79:5000/health",   # ← change to actual IP
#     },
#     # Add more devices:
#     # {"id": "alc-01", "label": "ALC Station 01", "url": "http://192.168.1.102:5000/health"},
# ]


# def fetch_device(device: dict) -> dict:
#     try:
#         resp = requests.get(device["url"], timeout=3)
#         if resp.status_code == 200:
#             data = resp.json()
#             data["status"] = "ONLINE"
#             return data
#         return {"status": False, "error": f"HTTP {resp.status_code}"}
#     except requests.exceptions.ConnectionError:
#         return {"status": False, "error": "Connection refused"}
#     except requests.exceptions.Timeout:
#         return {"status": False, "error": "Timed out"}
#     except Exception as e:
#         return {"status": False, "error": str(e)}


# def metric_bar(label: str, pct) -> html.Div:
#     if pct is None:
#         return html.Div()
#     pct   = round(float(pct), 1)
#     color = "#EF4444" if pct > 85 else "#F59E0B" if pct > 65 else "#10B981"
#     return html.Div([
#         html.Div([
#             html.Span(label, style={"fontSize": "10px", "color": "#A4B0BE", "fontWeight": "600"}),
#             html.Span(f"{pct}%", style={"fontSize": "11px", "color": "#2F3542", "fontWeight": "700"}),
#         ], style={"display": "flex", "justifyContent": "space-between", "marginBottom": "3px"}),
#         html.Div(
#             html.Div(style={"width": f"{min(pct,100)}%", "height": "5px",
#                             "background": color, "borderRadius": "3px"}),
#             style={"background": "#F1F4F7", "borderRadius": "3px", "height": "5px"},
#         ),
#     ], style={"marginBottom": "10px"})


# def status_badge(label, color, bg):
#     return html.Span([
#         html.Span("●", style={"color": color, "marginRight": "5px", "fontSize": "10px"}),
#         html.Span(label, style={"fontSize": "10px", "fontWeight": "700", "color": color}),
#     ], style={"background": bg, "padding": "3px 10px", "borderRadius": "20px",
#               "display": "inline-flex", "alignItems": "center"})


# def build_device_card(device: dict, data: dict) -> html.Div:
#     reachable = data.get("status")

#     if not reachable:
#         border_color = "#EF4444"
#         badge = status_badge("OFFLINE", "#991B1B", "#FEE2E2")
#         body  = html.Div([
#             html.Div(data.get("error", "Unreachable"),
#                      style={"fontSize": "12px", "color": "#EF4444", "marginTop": "8px"}),
#         ])
#     else:
#         app_running = data.get("application_running", False)
#         cpu         = data.get("cpu_percent")
#         mem         = data.get("memory_percent")
#         disk        = data.get("disk_percent")
#         ports       = data.get("ports", {})
#         uptime      = data.get("uptime_hours")
#         app_name    = data.get("application", "Unknown App")
#         hostname    = data.get("hostname", "")
#         ip          = data.get("ip_address", "")

#         if not app_running:
#             border_color = "#F59E0B"
#             badge        = status_badge("APP DOWN", "#92400E", "#FEF3C7")
#         else:
#             border_color = "#10B981"
#             badge        = status_badge("ONLINE", "#065F46", "#D1FAE5")

#         port_pills = [
#             html.Span(f":{port}", style={
#                 "fontSize": "10px", "fontWeight": "600", "padding": "2px 8px",
#                 "borderRadius": "4px", "marginRight": "5px",
#                 "background": "#D1FAE5" if state == "OPEN" else "#FEE2E2",
#                 "color":      "#065F46" if state == "OPEN" else "#991B1B",
#                 "border":     f"1px solid {'#6EE7B7' if state == 'OPEN' else '#FCA5A5'}",
#             }) for port, state in ports.items()
#         ]

#         body = html.Div([
#             # Hostname + IP
#             html.Div([
#                 html.Span(hostname, style={"fontSize": "11px", "color": "#57606F", "fontWeight": "600"}),
#                 html.Span(f" • {ip}", style={"fontSize": "11px", "color": "#A4B0BE", "fontFamily": "monospace"}),
#             ], style={"marginBottom": "12px"}),

#             # App status
#             html.Div([
#                 html.Div("MONITORED APPLICATION", style={"fontSize": "10px", "color": "#A4B0BE",
#                                                           "fontWeight": "700", "marginBottom": "6px"}),
#                 html.Div([
#                     html.Span(app_name, style={
#                         "fontSize": "12px", "fontWeight": "600", "padding": "4px 12px",
#                         "borderRadius": "6px", "marginRight": "8px",
#                         "background": "#D1FAE5" if app_running else "#FEE2E2",
#                         "color":      "#065F46" if app_running else "#991B1B",
#                         "border":     f"1px solid {'#6EE7B7' if app_running else '#FCA5A5'}",
#                     }),
#                     html.Span(
#                         "Running ✓" if app_running else "Not Running ✗",
#                         style={"fontSize": "11px", "fontWeight": "600",
#                                "color": "#10B981" if app_running else "#EF4444"},
#                     ),
#                 ]),
#             ], style={"marginBottom": "14px"}),

#             # Metrics
#             metric_bar("CPU",  cpu),
#             metric_bar("RAM",  mem),
#             metric_bar("DISK", disk),

#             # Ports
#             html.Div([
#                 html.Div("PORTS", style={"fontSize": "10px", "color": "#A4B0BE",
#                                           "fontWeight": "700", "marginBottom": "6px"}),
#                 html.Div(port_pills),
#             ], style={"marginBottom": "12px"}) if port_pills else html.Div(),

#             # Uptime
#             html.Div([
#                 html.Span("UPTIME ", style={"fontSize": "10px", "color": "#A4B0BE", "fontWeight": "700"}),
#                 html.Span(f"{uptime}h" if uptime else "—",
#                           style={"fontSize": "11px", "color": "#57606F", "fontWeight": "600"}),
#             ]) if uptime else html.Div(),
#         ])

#     return html.Div([
#         html.Div([
#             html.Div(device["label"], style={"fontWeight": "700", "fontSize": "14px", "color": "#2F3542"}),
#             badge,
#         ], style={"display": "flex", "justifyContent": "space-between",
#                   "alignItems": "center", "marginBottom": "14px"}),
#         body,
#     ], style={**CARD, "borderLeft": f"3px solid {border_color}"})


# def layout():
#     return html.Div(style={"background": "#F7F9FC", "minHeight": "100vh"}, children=[

#         dcc.Interval(id="device-interval", interval=15_000, n_intervals=0),

#         html.Div([
#             html.Div([
#                 html.Span("Production Line", style={"fontWeight": "700", "fontSize": "15px", "color": "#2F3542"}),
#                 html.Span(" / Device Monitor", style={"fontSize": "13px", "color": "#A4B0BE"}),
#             ]),
#             html.Div([
#                 html.Span(id="device-last-refresh", style={"fontSize": "11px", "color": "#A4B0BE"}),
#                 html.Span("● LIVE", style={"fontSize": "11px", "color": "#10B981",
#                                             "fontWeight": "700", "marginLeft": "12px"}),
#             ]),
#         ], style={"padding": "14px 24px", "borderBottom": "1px solid #E8EDF2",
#                   "background": "white", "display": "flex",
#                   "justifyContent": "space-between", "alignItems": "center"}),

#         html.Div(style={"padding": "24px"}, children=[
#             html.Div(id="device-kpi-row", style={"display": "flex", "gap": "14px", "marginBottom": "24px"}),
#             html.Div(id="device-grid"),
#         ]),
#     ])


# @callback(
#     Output("device-kpi-row",      "children"),
#     Output("device-grid",         "children"),
#     Output("device-last-refresh", "children"),
#     Input("device-interval",      "n_intervals"),
# )
# def refresh_devices(n):
#     results = {d["id"]: fetch_device(d) for d in DEVICES}


#     online  = sum(1 for d in DEVICES if results[d["id"]].get("status") and results[d["id"]].get("application_running"))
#     app_dwn = sum(1 for d in DEVICES if results[d["id"]].get("status") and not results[d["id"]].get("application_running"))
#     offline = sum(1 for d in DEVICES if not results[d["id"]].get("status"))

#     kpi_cfg = [
#         ("TOTAL",    len(DEVICES), "#2F3542", "white",   "#E8EDF2"),
#         ("ONLINE",   online,       "#065F46", "#D1FAE5", "#6EE7B7"),
#         ("APP DOWN", app_dwn,      "#92400E", "#FEF3C7", "#FCD34D"),
#         ("OFFLINE",  offline,      "#991B1B", "#FEE2E2", "#FCA5A5"),
#     ]
#     kpis = [
#         html.Div([
#             html.Div(label, style={"fontSize": "10px", "color": tc, "fontWeight": "700", "marginBottom": "6px"}),
#             html.Div(str(val), style={"fontSize": "28px", "fontWeight": "800", "color": tc}),
#         ], style={"flex": "1", "padding": "18px 20px", "background": bg,
#                   "border": f"1px solid {bord}", "borderRadius": "8px"})
#         for label, val, tc, bg, bord in kpi_cfg
#     ]

#     cards = [build_device_card(d, results[d["id"]]) for d in DEVICES]
#     grid  = html.Div(cards, style={
#         "display": "grid",
#         "gridTemplateColumns": "repeat(auto-fill, minmax(340px, 1fr))",
#         "gap": "16px",
#     })

#     return kpis, grid, f"Last refreshed {datetime.now().strftime('%H:%M:%S')}"