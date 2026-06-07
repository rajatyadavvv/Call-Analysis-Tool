import dash
from dash import html, dcc, callback, Output, Input, State

dash.register_page(__name__, path="/profile", name="Profile")

CARD   = {"background": "white", "border": "1px solid #E8EDF2", "borderRadius": "8px", "padding": "24px"}
ACCENT = "#546DE5"

LABEL_STYLE = {"fontSize": "10px", "color": "#A4B0BE", "fontWeight": "700",
               "letterSpacing": "0.05em", "marginBottom": "5px", "display": "block"}
INPUT_STYLE = {
    "width": "100%", "padding": "9px 12px", "fontSize": "13px",
    "border": "1px solid #E8EDF2", "borderRadius": "6px",
    "outline": "none", "background": "white", "color": "#2F3542",
    "boxSizing": "border-box",
}


def field(label, input_id, value="", placeholder="", input_type="text"):
    return html.Div([
        html.Label(label, style=LABEL_STYLE),
        dcc.Input(id=input_id, value=value, placeholder=placeholder,
                  type=input_type, style=INPUT_STYLE),
    ], style={"marginBottom": "16px"})


def section_title(text):
    return html.Div(text, style={
        "fontSize": "12px", "fontWeight": "700", "color": "#2F3542",
        "letterSpacing": "0.03em", "marginBottom": "16px",
        "paddingBottom": "10px", "borderBottom": "1px solid #F1F4F7",
    })


def toggle(label, toggle_id, checked=True, sublabel=""):
    return html.Div([
        html.Div([
            html.Div([
                html.Div(label,    style={"fontSize": "13px", "fontWeight": "500", "color": "#2F3542"}),
                html.Div(sublabel, style={"fontSize": "11px", "color": "#A4B0BE"}),
            ]),
            dcc.Checklist(
                id=toggle_id,
                options=[{"label": "", "value": "on"}],
                value=["on"] if checked else [],
                inputStyle={"width": "16px", "height": "16px", "cursor": "pointer",
                            "accentColor": ACCENT},
            ),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"}),
    ], style={"marginBottom": "12px"})


def layout():
    return html.Div(style={"background": "#F7F9FC", "minHeight": "100vh"}, children=[

        # Topbar
        html.Div([
            html.Span("Profile & Settings", style={"fontWeight": "700", "fontSize": "15px", "color": "#2F3542"}),
        ], style={"padding": "16px 24px", "borderBottom": "1px solid #E8EDF2",
                  "background": "white", "display": "flex", "alignItems": "center"}),

        html.Div(style={"padding": "24px"}, children=[

            html.Div([

                # Left column
                html.Div([

                    # Avatar + name
                    html.Div([
                        html.Div([
                            html.Div("AU", style={
                                "width":          "64px",
                                "height":         "64px",
                                "borderRadius":   "50%",
                                "background":     ACCENT,
                                "color":          "white",
                                "display":        "flex",
                                "alignItems":     "center",
                                "justifyContent": "center",
                                "fontSize":       "20px",
                                "fontWeight":     "700",
                                "marginRight":    "16px",
                                "flexShrink":     "0",
                            }),
                            html.Div([
                                html.Div("Admin User", style={"fontWeight": "800", "fontSize": "16px", "color": "#2F3542"}),
                                html.Div("Lead Critical Analyst", style={"fontSize": "12px", "color": "#778CA3"}),
                                html.Div([
                                    html.Span("●", style={"color": "#10B981", "marginRight": "4px", "fontSize": "10px"}),
                                    html.Span("Active", style={"fontSize": "11px", "color": "#10B981", "fontWeight": "600"}),
                                ], style={"marginTop": "4px"}),
                            ]),
                        ], style={"display": "flex", "alignItems": "center"}),
                    ], style={"marginBottom": "24px"}),

                    # User Identity card
                    html.Div([
                        section_title("User Identity"),
                        html.Div([
                            html.Div([field("FIRST NAME", "inp-first", "Admin")],      style={"flex": "1", "marginRight": "12px"}),
                            html.Div([field("LAST NAME",  "inp-last",  "User")],       style={"flex": "1"}),
                        ], style={"display": "flex"}),
                        field("PRIMARY EMAIL",    "inp-email",    "admin@datadash.sys",   input_type="email"),
                        field("PHONE NUMBER",     "inp-phone",    "+91 98765 43210"),
                        field("ROLE / ACCESS LEVEL","inp-role",   "Lead Critical Analyst"),
                        field("DEPARTMENT",       "inp-dept",     "IT Operations"),

                        html.Button("Save Changes", id="save-identity-btn", n_clicks=0, style={
                            "padding": "9px 20px", "background": ACCENT, "color": "white",
                            "border": "none", "borderRadius": "6px", "cursor": "pointer",
                            "fontSize": "13px", "fontWeight": "600",
                        }),
                        html.Div(id="save-identity-msg", style={"marginTop": "8px", "fontSize": "12px"}),
                    ], style={"marginBottom": "16px", **CARD}),

                    # Password card
                    html.Div([
                        section_title("Change Password"),
                        field("CURRENT PASSWORD", "inp-curr-pass", input_type="password"),
                        field("NEW PASSWORD",      "inp-new-pass",  input_type="password"),
                        field("CONFIRM PASSWORD",  "inp-conf-pass", input_type="password"),
                        html.Button("Update Password", id="save-pass-btn", n_clicks=0, style={
                            "padding": "9px 20px", "background": "#2F3542", "color": "white",
                            "border": "none", "borderRadius": "6px", "cursor": "pointer",
                            "fontSize": "13px", "fontWeight": "600",
                        }),
                        html.Div(id="save-pass-msg", style={"marginTop": "8px", "fontSize": "12px"}),
                    ], style={**CARD}),

                ], style={"flex": "1.2", "marginRight": "16px"}),

                # Right column
                html.Div([

                    # System preferences
                    html.Div([
                        section_title("System Preferences"),
                        html.Div([
                            html.Label("TIMEZONE", style=LABEL_STYLE),
                            dcc.Dropdown(
                                id="inp-timezone",
                                options=[
                                    {"label": "UTC — Coordinated Universal Time", "value": "UTC"},
                                    {"label": "IST — India Standard Time (UTC+5:30)", "value": "IST"},
                                    {"label": "EST — Eastern Standard Time (UTC-5)", "value": "EST"},
                                    {"label": "PST — Pacific Standard Time (UTC-8)", "value": "PST"},
                                    {"label": "CET — Central European Time (UTC+1)", "value": "CET"},
                                ],
                                value="IST", clearable=False,
                                style={"fontSize": "13px", "marginBottom": "16px"},
                            ),
                        ]),
                        html.Div([
                            html.Label("DATE FORMAT", style=LABEL_STYLE),
                            dcc.Dropdown(
                                id="inp-dateformat",
                                options=[
                                    {"label": "DD/MM/YYYY", "value": "dmy"},
                                    {"label": "MM/DD/YYYY", "value": "mdy"},
                                    {"label": "YYYY-MM-DD", "value": "ymd"},
                                ],
                                value="dmy", clearable=False,
                                style={"fontSize": "13px", "marginBottom": "16px"},
                            ),
                        ]),
                        html.Div([
                            html.Label("ASSIGNED ENTITY", style=LABEL_STYLE),
                            dcc.Input(id="inp-entity", value="IT Support (ALC), IT Support (EVSM)",
                                      style={**INPUT_STYLE, "marginBottom": "16px"}),
                        ]),
                    ], style={"marginBottom": "16px", **CARD}),

                    # Notification preferences
                    html.Div([
                        section_title("Notification Preferences"),
                        toggle("CR Alerts (aged > 14 days)",    "tog-cr",      True,  "Critical and warning alerts"),
                        toggle("SR Alerts (aged > 5 days)",     "tog-sr",      True,  "Pending service requests"),
                        toggle("Incident Alerts (aged > 1 day)","tog-incident", True, "Open incident notifications"),
                        toggle("Browser Notifications",          "tog-browser", True,  "Push notifications every 10 min"),
                        toggle("Weekly Summary Email",           "tog-email",   False, "Aggregated weekly report"),
                    ], style={"marginBottom": "16px", **CARD}),

                    # Danger zone
                    html.Div([
                        html.Div("Danger Zone", style={
                            "fontSize": "12px", "fontWeight": "700", "color": "#EF4444",
                            "marginBottom": "12px", "paddingBottom": "10px",
                            "borderBottom": "1px solid #FEE2E2",
                        }),
                        html.Div("Permanently delete all data associated with this account.",
                                 style={"fontSize": "12px", "color": "#778CA3", "marginBottom": "14px"}),
                        html.Button("Initiate Account Deletion", style={
                            "padding": "8px 16px", "background": "white", "color": "#EF4444",
                            "border": "1px solid #EF4444", "borderRadius": "6px",
                            "cursor": "pointer", "fontSize": "12px", "fontWeight": "600",
                        }),
                    ], style={**CARD, "border": "1px solid #FEE2E2"}),

                ], style={"flex": "1"}),

            ], style={"display": "flex", "alignItems": "flex-start"}),
        ]),
    ])


@callback(
    Output("save-identity-msg", "children"),
    Output("save-identity-msg", "style"),
    Input("save-identity-btn",  "n_clicks"),
    prevent_initial_call=True,
)
def save_identity(n):
    return "✓ Changes saved successfully", {"marginTop": "8px", "fontSize": "12px", "color": "#10B981"}


@callback(
    Output("save-pass-msg", "children"),
    Output("save-pass-msg", "style"),
    Input("save-pass-btn",  "n_clicks"),
    prevent_initial_call=True,
)
def save_password(n):
    return "✓ Password updated", {"marginTop": "8px", "fontSize": "12px", "color": "#10B981"}