import dash
import os
from dash import html, dcc
import dash_bootstrap_components as dbc

app = dash.Dash(
    __name__,
    use_pages=True,
    pages_folder=os.path.dirname(os.path.abspath(__file__)),         
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title="IT sahay data dashboard",
)

app.layout = html.Div([
    dcc.Location(id="url"),
    dash.page_container,
])

if __name__ == "__main__":
    app.run(debug=True)