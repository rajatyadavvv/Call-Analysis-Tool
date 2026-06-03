import dash
import pandas as pd
from dash import Dash, html, dcc, callback, Output, Input
import dash_ag_grid as dag
import plotly.express as px
from db import get_connection
dash.register_page(__name__, path="/cr")

conn = get_connection()

