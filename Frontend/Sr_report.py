import pandas as pd
from dash import Dash, html, dcc, callback, Output, Input
import dash_ag_grid as dag
import plotly.express as px
from db import get_connection

conn = get_connection()
app = Dash()

df = pd.read_sql('select * from sr_report', conn)

Filtered_df = df[
    (df['Workgroup'] == 'IT Support (ALC)') |
    (df['Workgroup'] == 'IT Support (EVSM)')
]

location_count = (
    Filtered_df['Location']
    .value_counts()
    .reset_index()
)

location_count.columns = ['Location', 'Count']
status_count = (

    Filtered_df['Status']

    .value_counts()

    .reset_index()

)

status_count.columns = ['Status', 'Count']
status_counts = Filtered_df['Status'].value_counts()
fig = px.bar(

    location_count,

    x='Location',

    y='Count',

    title='Location Wise Ticket Count',

    text='Count'

)

fig.update_layout(

    xaxis_title='Location',

    yaxis_title='Number of Tickets'

)


fig_status = px.pie(

    status_count,

    names='Status',

    values='Count',

    title='Status Distribution'

)

fig_status.update_traces(

    textposition='inside',

    textinfo='percent+label'

)
status_cards = html.Div(

    [

        html.Div(

            [

                html.H4(status),

                html.H2(count)

            ],

            style={

                "border": "1px solid #ddd",

                "borderRadius": "10px",

                "padding": "15px",

                "width": "180px",

                "textAlign": "center",

                "boxShadow": "2px 2px 5px rgba(0,0,0,0.1)"

            }

        )

        for status, count in status_counts.items()

    ],

    style={

        "display": "flex",

        "gap": "20px",

        "flexWrap": "wrap"

    }

)

app.layout= [
    html.H1("Call Analysis Dashboard"),
    html.Div(children="SR Report Data"),
    dag.AgGrid(
        rowData=Filtered_df.to_dict('records'),
        columnDefs=[{"field": i } for i in Filtered_df.columns]
    ),
    dcc.Graph(figure=fig),
    status_cards,
    dcc.Graph(figure=fig_status)
]

if __name__ == '__main__':
    app.run()