import dash
from dash import html, dcc
import dash_bootstrap_components as dbc

app = dash.Dash(
    __name__,
    use_pages=True,
    pages_folder="",          # ← pages are in the same folder as main.py
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title="DataDash",
)

app.layout = html.Div([
    dcc.Location(id="url"),
    dash.page_container,
])

if __name__ == "__main__":
    app.run(debug=True)