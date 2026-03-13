import plotly.graph_objects as go
import pandas as pd
import datetime

idx = pd.date_range(end=datetime.date.today(), periods=10)
fig = go.Figure(go.Scatter(x=idx, y=list(range(10))))

try:
    fig.add_vline(x=str(datetime.date.today()), annotation_text="Today")
    print("str works")
except Exception as e:
    print(f"str fails: {e}")

try:
    fig2 = go.Figure(go.Scatter(x=idx, y=list(range(10))))
    fig2.add_vline(x=datetime.date.today(), annotation_text="Today")
    print("date works")
except Exception as e:
    print(f"date fails: {e}")

try:
    fig3 = go.Figure(go.Scatter(x=idx, y=list(range(10))))
    fig3.add_vline(x=pd.Timestamp(datetime.date.today()).timestamp() * 1000, annotation_text="Today")
    print("timestamp ms works")
except Exception as e:
    print(f"timestamp ms fails: {e}")

