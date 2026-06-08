import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import pandas as pd
import re
from openai import OpenAI

try:
    from db import get_connection
except ImportError:
    # Fallback if db isn't found
    get_connection = None

STOP_WORDS = {"a", "an", "the", "and", "or", "but", "if", "is", "are", "was", "were", "to", "in", "on", "with", "for", "of", "how", "what", "where", "why", "when", "help", "me", "i", "need", "issue", "error", "problem", "recommendation", "recommend", "solution", "solutions"}

# Local LM Studio Client
# Ensure LM Studio's local server is running on port 1234
client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

# Local Built-in Logic for Chatbot
def get_chatbot_response(user_text):
    user_text = user_text.lower().strip()
    if not user_text:
        return "Please ask a question."
        
    # Basic intent matching
    if user_text in ["hi", "hello", "hey", "help"]:
        return "Hello Admin! I'm your local assistant. Describe an issue, and I will instantly search the database for past solutions."
        
    if get_connection is None:
        return "I am currently unable to connect to the database."
        
    # Extract keywords
    words = re.findall(r'\b\w+\b', user_text)
    keywords = [w for w in words if w not in STOP_WORDS and len(w) > 2]
    
    if not keywords:
        return "Could you provide more specific keywords about the issue?"

    try:
        conn = get_connection()
        # Create a SQL query using LIKE for each keyword
        conditions = " OR ".join(["`Symptom` LIKE %s"] * len(keywords))
        query = f"SELECT `Incident ID`, `Symptom`, `Solution`, `Status` FROM incident_report WHERE ({conditions}) AND `Solution` IS NOT NULL AND `Solution` != '' LIMIT 5"
        
        params = tuple([f"%{kw}%" for kw in keywords])
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        
        context_str = ""
        if not df.empty:
            for _, row in df.iterrows():
                context_str += f"- ID {row.get('Incident ID')} ({row.get('Status')}): {row.get('Symptom')}\n  Fix: {row.get('Solution')}\n"
                
        # Send prompt to LM Studio
        prompt = f"""
You are an intelligent offline IT Support Assistant inside an admin dashboard. 
The user is asking: "{user_text}"

Here is some context retrieved from your local database of past resolved incidents (if any matches were found):
{context_str if context_str else "No direct matches found in past incidents."}

Please provide a helpful, concise answer based on this context. If past solutions are relevant, mention them to help the admin.
"""

        try:
            response = client.chat.completions.create(
                model="local-model", # LM studio will use whatever model is loaded
                messages=[
                    {"role": "system", "content": "You are a helpful IT assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
            )
            ai_text = response.choices[0].message.content
            return html.Div(ai_text, style={"whiteSpace": "pre-wrap", "fontSize": "13px"})
        except Exception as e:
            return f"LM Studio connection error: Make sure the Local Server is running in LM Studio on port 1234. Details: {str(e)}"

    except Exception as e:
        return f"Database error: {str(e)}"

def create_chatbot_layout():
    return html.Div([
        # Floating Chatbot Button
        html.Div(
            "💬",
            id="chatbot-button",
            style={
                "position": "fixed",
                "bottom": "30px",
                "right": "30px",
                "width": "60px",
                "height": "60px",
                "borderRadius": "30px",
                "backgroundColor": "#546DE5",
                "color": "white",
                "fontSize": "30px",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
                "cursor": "pointer",
                "boxShadow": "0 4px 10px rgba(0,0,0,0.3)",
                "zIndex": 9999
            }
        ),
        
        # Chat Window
        html.Div(
            id="chatbot-window",
            style={
                "position": "fixed",
                "bottom": "100px",
                "right": "30px",
                "width": "350px",
                "height": "450px",
                "backgroundColor": "white",
                "border": "1px solid #E8EDF2",
                "borderRadius": "12px",
                "boxShadow": "0 8px 16px rgba(0,0,0,0.15)",
                "display": "none",
                "flexDirection": "column",
                "zIndex": 9999,
                "overflow": "hidden"
            },
            children=[
                # Header
                html.Div(
                    [
                        html.Span("Admin Assistant", style={"fontWeight": "600", "color": "white", "fontSize": "16px"}),
                        html.Span("✕", id="chatbot-close", style={"cursor": "pointer", "color": "white", "fontWeight": "bold", "fontSize": "18px"})
                    ],
                    style={
                        "backgroundColor": "#546DE5",
                        "padding": "12px 16px",
                        "display": "flex",
                        "justifyContent": "space-between",
                        "alignItems": "center"
                    }
                ),
                # Messages Area
                html.Div(
                    id="chatbot-messages",
                    style={
                        "flex": "1",
                        "padding": "15px",
                        "overflowY": "auto",
                        "backgroundColor": "#F7F9FC",
                        "display": "flex",
                        "flexDirection": "column",
                        "gap": "12px"
                    },
                    children=[
                        html.Div("Hi Admin, I'm here to help with information and recommendations based on past solutions. Ask me anything!", 
                                 style={"backgroundColor": "#E8EDF2", "color": "#2F3542", "padding": "10px 14px", "borderRadius": "12px", "alignSelf": "flex-start", "maxWidth": "85%", "fontSize": "14px"})
                    ]
                ),
                # Input Area
                html.Div(
                    style={
                        "padding": "12px",
                        "borderTop": "1px solid #E8EDF2",
                        "display": "flex",
                        "gap": "8px",
                        "backgroundColor": "white"
                    },
                    children=[
                        dcc.Input(
                            id="chatbot-input",
                            type="text",
                            placeholder="Type a message...",
                            style={
                                "flex": "1", 
                                "padding": "10px", 
                                "borderRadius": "8px", 
                                "border": "1px solid #D1D5DB",
                                "outline": "none",
                                "fontSize": "14px"
                            }
                        ),
                        html.Button(
                            "Send",
                            id="chatbot-send",
                            style={
                                "backgroundColor": "#546DE5",
                                "color": "white",
                                "border": "none",
                                "borderRadius": "8px",
                                "padding": "0 16px",
                                "cursor": "pointer",
                                "fontWeight": "500"
                            }
                        )
                    ]
                )
            ]
        )
    ])

def register_chatbot_callbacks(app):
    @app.callback(
        Output("chatbot-window", "style"),
        [Input("chatbot-button", "n_clicks"), Input("chatbot-close", "n_clicks")],
        [State("chatbot-window", "style")]
    )
    def toggle_chatbot(btn_click, close_click, current_style):
        ctx = dash.callback_context
        if not ctx.triggered:
            return current_style
        
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        if button_id == 'chatbot-button':
            if current_style.get('display') == 'none':
                current_style['display'] = 'flex'
            else:
                current_style['display'] = 'none'
        elif button_id == 'chatbot-close':
            current_style['display'] = 'none'
            
        return current_style

    @app.callback(
        Output("chatbot-messages", "children"),
        Output("chatbot-input", "value"),
        [Input("chatbot-send", "n_clicks"), Input("chatbot-input", "n_submit")],
        [State("chatbot-input", "value"), State("chatbot-messages", "children")],
        prevent_initial_call=True
    )
    def update_messages(n_clicks, n_submit, user_text, current_messages):
        if not user_text or not user_text.strip():
            return dash.no_update, dash.no_update
            
        # Add user message
        new_messages = current_messages.copy()
        new_messages.append(
            html.Div(user_text, style={"backgroundColor": "#546DE5", "color": "white", "padding": "10px 14px", "borderRadius": "12px", "alignSelf": "flex-end", "maxWidth": "85%", "fontSize": "14px"})
        )
        
        # Add bot response
        bot_response = get_chatbot_response(user_text)
        new_messages.append(
            html.Div(bot_response, style={"backgroundColor": "#E8EDF2", "color": "#2F3542", "padding": "10px 14px", "borderRadius": "12px", "alignSelf": "flex-start", "maxWidth": "85%", "fontSize": "14px"})
        )
        
        return new_messages, ""
