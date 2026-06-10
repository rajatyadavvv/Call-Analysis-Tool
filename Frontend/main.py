import dash
import os
from dash import html, dcc, Input, Output, callback
import dash_bootstrap_components as dbc
from Chatbot_Component.chatbot_ui import create_chatbot_layout, register_chatbot_callbacks

app = dash.Dash(
    __name__,
    use_pages=True,
    pages_folder=os.path.dirname(os.path.abspath(__file__)),
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title="DataDash",
)

# ── Notion/Linear palette (matches page files) ────────────────────────────────
SIDEBAR_BG   = "#FFFFFF"
SIDEBAR_BORD = "#E8EDF2"
TEXT_DARK    = "#2F3542"
TEXT_MID     = "#57606F"
TEXT_MUTED   = "#A4B0BE"
ACCENT       = "#546DE5"
HOVER_BG     = "#F1F4F7"

NAV_ITEMS = [
    {"label": "CR",       "href": "/cr"},
    {"label": "SR",       "href": "/sr"},
    {"label": "Incident", "href": "/incident"},
    {"label": "Notifications", "href": "/notifications"},
]


def nav_link(label, href):
    return dcc.Link(
        html.Div([
            html.Span(label, style={"fontSize": "13px", "fontWeight": "500"}),
        ], style={
            "padding":       "10px 16px",
            "cursor":        "pointer",
            "borderRadius":  "6px",
            "display":       "flex",
            "alignItems":    "center",
            "color":         TEXT_MID,
            "marginBottom":  "2px",
        }),
        href=href,
        style={"textDecoration": "none"},
    )


app.layout = html.Div([
    dcc.Location(id="url"),

    # Global store for notifications (persists across pages)
    dcc.Store(id="global-notif-store", storage_type="session", data=[]),

    # ── Sidebar ───────────────────────────────────────────────────────────────
    html.Div([
        # Brand
        html.Div([
            html.Div("DataDash", style={
                "fontWeight": "800", "fontSize": "17px", "color": TEXT_DARK, "letterSpacing": "-0.3px",
            }),
            html.Div("Critical Analytics", style={"fontSize": "11px", "color": TEXT_MUTED, "marginTop": "2px"}),
        ], style={"padding": "22px 20px 28px"}),

        # Nav links
        html.Div([nav_link(i["label"], i["href"]) for i in NAV_ITEMS],
                 style={"padding": "0 10px"}),

        # Bottom — bell + user
        html.Div([
            # Bell with badge
            dcc.Link(
                html.Div([
                    html.Span("🔔", style={"fontSize": "16px"}),
                    html.Span(id="notif-badge", style={
                        "position":      "absolute",
                        "top":           "-4px",
                        "right":         "-4px",
                        "background":    "#EF4444",
                        "color":         "white",
                        "borderRadius":  "50%",
                        "fontSize":      "9px",
                        "fontWeight":    "700",
                        "width":         "16px",
                        "height":        "16px",
                        "display":       "flex",
                        "alignItems":    "center",
                        "justifyContent":"center",
                    }),
                ], style={"position": "relative", "cursor": "pointer",
                          "padding": "8px", "borderRadius": "6px"}),
                href="/notifications",
                style={"textDecoration": "none"},
            ),
            # User icon
            dcc.Link(
                html.Div([
                    html.Div("AU", style={
                        "width":          "30px",
                        "height":         "30px",
                        "borderRadius":   "50%",
                        "background":     ACCENT,
                        "color":          "white",
                        "display":        "flex",
                        "alignItems":     "center",
                        "justifyContent": "center",
                        "fontSize":       "11px",
                        "fontWeight":     "700",
                        "cursor":         "pointer",
                    }),
                ]),
                href="/profile",
                style={"textDecoration": "none"},
            ),
        ], style={
            "position":      "absolute",
            "bottom":        "20px",
            "left":          "0",
            "right":         "0",
            "padding":       "0 20px",
            "display":       "flex",
            "alignItems":    "center",
            "gap":           "12px",
            "borderTop":     f"1px solid {SIDEBAR_BORD}",
            "paddingTop":    "16px",
        }),

    ], style={
        "width":        "220px",
        "minWidth":     "220px",
        "height":       "100vh",
        "background":   SIDEBAR_BG,
        "borderRight":  f"1px solid {SIDEBAR_BORD}",
        "position":     "fixed",
        "top":          0,
        "left":         0,
        "zIndex":       100,
        "overflowY":    "auto",
    }),

    # ── Page content ──────────────────────────────────────────────────────────
    html.Div([
        dash.page_container,
    ], style={"marginLeft": "220px", "background": "#F7F9FC", "minHeight": "100vh"}),

    # Chatbot component
    create_chatbot_layout()

])


# ── Badge count callback ──────────────────────────────────────────────────────
@callback(
    Output("notif-badge", "children"),
    Output("notif-badge", "style"),
    Input("global-notif-store", "data"),
)
def update_badge(notifications):
    base_style = {
        "position":       "absolute",
        "top":            "-4px",
        "right":          "-4px",
        "background":     "#EF4444",
        "color":          "white",
        "borderRadius":   "50%",
        "fontSize":       "9px",
        "fontWeight":     "700",
        "width":          "16px",
        "height":         "16px",
        "display":        "flex",
        "alignItems":     "center",
        "justifyContent": "center",
    }
    if not notifications:
        return "", {**base_style, "display": "none"}
    unread = sum(1 for n in notifications if not n.get("read", False))
    if unread == 0:
        return "", {**base_style, "display": "none"}
    return str(unread), base_style

register_chatbot_callbacks(app)

if __name__ == "__main__":
    app.run(debug=True)