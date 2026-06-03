import dash
import pandas as pd
from dash import Dash, html, dcc, callback, Output, Input
import dash_ag_grid as dag
import plotly.express as px
from db import get_connection
dash.register_page(__name__, path="/sr")

conn = get_connection()

df = pd.read_sql("SELECT * FROM sr_report",conn)

def layout():
    conn = get_connection()
    return html.Div("SR page works")