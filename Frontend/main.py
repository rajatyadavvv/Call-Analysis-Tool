import dash
import os
from dash import html, dcc
import dash_bootstrap_components as dbc

app = dash.Dash(
    __name__,
    use_pages=True,
    pages_folder=os.path.dirname(os.path.abspath(__file__)),         
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title="Data dashboard",
)

app.layout = html.Div([
    dcc.Location(id="url"),
    html.Div([
    # Brand
    html.Div([
        html.Div("DataDash", style={"fontWeight": "800", "fontSize": "18px", "color": "#111"}),
    ], style={"padding": "24px 20px 32px"}),

    # Nav buttons
    dcc.Link(html.Div([
        html.Span("CR"),
    ], style={"padding": "12px 20px", "cursor": "pointer", "borderRadius": "8px",
              "display": "flex", "alignItems": "center"}),
    href="/cr", style={"textDecoration": "none", "color": "#333"}),

    dcc.Link(html.Div([
        html.Span("SR"),
    ], style={"padding": "12px 20px", "cursor": "pointer", "borderRadius": "8px",
              "display": "flex", "alignItems": "center", "background": "#e8e8e8"}),
    href="/sr", style={"textDecoration": "none", "color": "#333"}),

    dcc.Link(html.Div([
        html.Span("Incident"),
    ], style={"padding": "12px 20px", "cursor": "pointer", "borderRadius": "8px",
              "display": "flex", "alignItems": "center"}),
    href="/incident", style={"textDecoration": "none", "color": "#333"}),

    dcc.Link(html.Div([
        html.Span("Settings"),
    ], style={"padding": "12px 20px", "cursor": "pointer", "borderRadius": "8px",
              "display": "flex", "alignItems": "center"}),
    href="/settings", style={"textDecoration": "none", "color": "#333"}),

    # Bottom user
    html.Div([
        html.Span("👤", style={"marginRight": "10px"}),
        html.Span("Admin User", style={"fontSize": "13px", "color": "#555"}),
    ], style={"position": "absolute", "bottom": "24px", "left": "20px",
              "display": "flex", "alignItems": "center"}),

], style={
    "width": "220px",
    "height": "100vh",
    "background": "#f0f0f0",
    "position": "fixed",
    "top": 0,
    "left": 0,
}),
    html.Div([
        dash.page_container,
    ], style={"marginLeft": "230px"}),
])

if __name__ == "__main__":
    app.run(debug=True)