import dash
import pandas as pd
from dash import Dash, html, dcc, callback, Output, Input
import dash_ag_grid as dag
import plotly.express as px
from datetime import datetime
from db import get_connection

dash.register_page(__name__, path="/sr")


app = Dash()



conn = get_connection()

df = pd.read_sql("SELECT * FROM sr_report", conn)

filtered_df = df[
    df["Workgroup"].isin(["IT Support (ALC)", "IT Support (EVSM)"])
].reset_index(drop=True)

active_srs = (filtered_df["Status"].isin(["In-Progress","Pending"])).sum()

pending_approval = (filtered_df["Status"] == "Pending for Approval").sum()

resolved = (filtered_df["Status"] == "Resolved").sum()

rejected = (filtered_df["Status"] == "Rejected").sum()

fulfillment_rate = round(
    (filtered_df["Status"] == "Resolved").sum() / len(filtered_df) * 100, 1
)

approved_df = filtered_df[filtered_df["Status"].isin(["In-Progress","Pending"])].reset_index()

# print(filtered_df.columns)
approved_df["age_days"] = (datetime.now() - pd.to_datetime(approved_df["Final Approval Time"])).dt.days

bins = [0, 1, 3, 5, 7, float("inf")]
labels = ["0-1", "2-3", "4-5", "5-7", ">7"]
approved_df["age_bucket"] = pd.cut(approved_df["age_days"], bins=bins, labels=labels)

fig_aging = px.bar(
    approved_df["age_bucket"].value_counts().sort_index().reset_index(),
    x="age_bucket",
    y="count",
)
fig_aging.update_layout(
    height=300,
    margin=dict(l=0, r=0, t=10, b=0),
    xaxis_title="",
    yaxis_title="",
)
# Bar chart
fig_location = px.bar(filtered_df["Location"].value_counts().reset_index(), 
                      x="Location", y="count")

# Pie chart
fig_category = px.pie(filtered_df["Status"].value_counts().reset_index(), names="Status", values="count")

# Horizontal bar
# fig_workgroup = px.bar(filtered_df, x="count_column", y="workgroup_column", orientation="h")

# Line chart
# fig_aging = px.line(filtered_df, x="date_column", y="count_column")

def kpi_card(label, value, delta):
    return html.Div(
        [
            html.Div(
                label,
                style={"fontSize": "11px", "color": "#888", "marginBottom": "8px"},
            ),
            html.Div(
                str(value),
                style={"fontSize": "32px", "fontWeight": "800", "marginBottom": "8px"},
            ),
            html.Div(delta, style={"fontSize": "12px", "color": "#888"}),
        ],
        style={
            "flex": "1",
            "padding": "24px",
            "background": "white",
            "border": "1px solid #e0e0e0",
            "borderRadius": "8px",
        },
    )


def layout():
    return html.Div(
        [
            html.Div(
                [
                    html.Span("Dashboards / Service Requests"),
                    html.Div(
                        [
                            html.Span("🔔", style={"padding": "12px 20px"}),
                            html.Span("👤", style={"padding": "12px 20px"}),
                        ]
                    ),
                ],
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "padding": "16px 24px",
                    "borderBottom": "1px solid #e0e0e0",
                    "background": "#F3F3F3",
                },
            ),
            html.H1(
                "Service Request (SR) Overview",
                style={"padding": "12px 20px", "marginBottom": "0px"},
            ),
            html.Div(
                [
                    kpi_card("ACTIVE SRS", active_srs, "↑ 4% vs last week"),
                    kpi_card(
                        "FULFILLMENT RATE",
                        f"{fulfillment_rate}%",
                        "↓ 1.2% vs last week",
                    ),
                    kpi_card("Rejected", rejected, "— Stable"),
                    kpi_card(
                        "Pending for Approval", pending_approval, "↑ 0.5% vs last week"
                    ),
                ],
                style={"display": "flex", "gap": "16px", "padding": "24px"},
            ),
            html.Div(
                [
                    # Row 1
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        "SRs by Location",
                                        style={
                                            "fontWeight": "600",
                                            "marginBottom": "12px",
                                        },
                                    ),
                                    dcc.Graph(figure=fig_location),
                                ],
                                style={
                                    "flex": "1",
                                    "background": "white",
                                    "border": "1px solid #e0e0e0",
                                    "borderRadius": "8px",
                                    "padding": "16px",
                                },
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        "Status Category Distribution",
                                        style={
                                            "fontWeight": "600",
                                            "marginBottom": "12px",
                                        },
                                    ),
                                    dcc.Graph(figure=fig_category),
                                ],
                                style={
                                    "flex": "1",
                                    "background": "white",
                                    "border": "1px solid #e0e0e0",
                                    "borderRadius": "8px",
                                    "padding": "16px",
                                },
                            ),
                        ],
                        style={
                            "display": "flex",
                            "gap": "16px",
                            "marginBottom": "16px",
                        },
                    ),
                    # Row 2
                    html.Div(
                        [
                            html.Div(
                                "SR aging Distribution",
                                style={
                                            "fontWeight": "600",
                                            "marginBottom": "12px",
                                        },
                            ),
                            dcc.Graph(figure=fig_aging, config={"displayModeBar": False})
                        ],
                        style={
                                    "flex": "1",
                                    "background": "white",
                                    "border": "1px solid #e0e0e0",
                                    "borderRadius": "8px",
                                    "padding": "16px",
                                },
                    ),
                ],
                style={"padding": "24px"},
            ),
        ]
    )
