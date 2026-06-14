from pathlib import Path
import pandas as pd
import sqlite3

db_path = Path("data/mydatabase.db")
if not db_path.exists():
    df = pd.read_csv("data/superstore.csv", encoding='latin1')
    conn = sqlite3.connect(db_path)
    df.to_sql(name="superstore", con=conn, if_exists="replace", index=False)
    conn.close()

import streamlit as st
from agent.graph import agent


st.set_page_config(page_title="Superstore Sales Agent", layout="wide")
st.title("Superstore Sales Agent")

user_question = st.text_input("Ask a question about the data")

if st.button("Run") and user_question:
    with st.spinner("Thinking..."):
        result = agent.invoke({"user_question": user_question})

    if result.get("error_message"):
        st.error(result["error_message"])
    else:
        st.subheader("Interpretation")
        st.write(result["interpretation"])

        st.subheader("Data")
        st.dataframe(result["query_results"])

        if result.get("visualization_figure"):
            st.subheader("Chart")
            st.plotly_chart(result["visualization_figure"], width='stretch')