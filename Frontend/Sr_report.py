import dash
import pandas as pd
from dash import Dash, html, dcc, callback, Output, Input
import dash_ag_grid as dag
import plotly.express as px
from db import get_connection
dash.register_page(__name__, path="/sr")

app = Dash()

conn = get_connection()

df = pd.read_sql("SELECT * FROM sr_report",conn)

filtered_df = df[df['Workgroup'].isin([
    'IT Support (ALC)',
    'IT Support (EVSM)'
])].reset_index(drop=True)

def layout():
    conn = get_connection()
    return html.Div("SR page works")