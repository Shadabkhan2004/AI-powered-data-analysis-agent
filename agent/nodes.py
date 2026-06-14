import json
import pandas as pd
import sqlite3
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from agent.state import ParsedIntent,VisualizationSpec
from agent.state import AgentState
import plotly.express as px
from pathlib import Path

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
conn = sqlite3.connect(BASE_DIR / "data" / "mydatabase.db", check_same_thread=False)

llm = ChatOpenAI(model='gpt-4o-mini')

parsed_intent_llm = llm.with_structured_output(ParsedIntent)

visualization_spec_llm = llm.with_structured_output(VisualizationSpec)



def parse_question(state: AgentState):
  user_question = state["user_question"]

  prompt = f"""You are a data analyst assistant working with a Superstore Sales dataset.

Your job is to extract structured intent from the user's question.

TABLE: superstore
COLUMNS:
- Dimensions: Ship Mode, Customer ID, Customer Name, Segment, Country, City, State, Postal Code, Region, Product ID, Category, Sub-Category, Product Name, Order ID, Order Date, Ship Date
- Metrics: Sales, Profit, Quantity, Discount

RULES:
- target_metric must only be one of: Sales, Profit, Quantity, Discount
- Row ID and Order ID are not metrics, never use them as target_metric
- aggregation must be one of: SUM, AVG, COUNT, MAX, MIN
- filters must map exact column names to values from the dataset
- group_by must be a list of valid dimension column names
- time_range uses "Order Date" as the column unless explicitly stated otherwise
- If no limit is specified, set limit to null
- If no sort is specified, set sort_by and sort_order to null
- If no time range is specified, set time_range to null
- table_name is always "superstore"

User question: {user_question}"""
  try:
    response = parsed_intent_llm.invoke(prompt)

    return {"parsed_intent": response.model_dump()}
  except Exception as e:
    return {"error_message": str(e)}
  

def generate_sql(state: AgentState):
  parsed_intent = state["parsed_intent"]

  if not state.get("sql_error") and not state.get("validation_errors"):
    prompt = f"""You are a SQL expert working with a SQLite database.

    Convert the following parsed intent into a valid SQLite query.

    PARSED INTENT:
    {parsed_intent}

    RULES:
    - Table name is always "superstore"
    - Use exact column names as provided in parsed intent
    - Wrap column names with spaces in double quotes e.g. "Order Date"
    - Order Date is stored as text in M/D/YYYY format e.g. '11/8/2016'
    - For year filtering use: strftime('%Y', "Order Date") = '2017'
    - For month filtering use: strftime('%m', "Order Date") = '01'
    - For date range filtering use: "Order Date" BETWEEN '1/1/2017' AND '12/31/2017'
    - Return only the SQL query, no explanation, no markdown, no preamble
    - Always alias aggregated columns e.g. SUM("Sales") AS total_Sales

    SQL:"""

    response = llm.invoke(prompt).content
    response = response.strip().strip("```sql").strip("```").strip()

    return {"generated_sql": response,"sql_attempt_count": state.get("sql_attempt_count",0) + 1}
  else:
    generated_sql = state.get("generated_sql")
    sql_error = state.get("sql_error") or "\n".join(state.get("validation_errors",[]))

    prompt = f"""You are a SQL expert working with a SQLite database.

    Your previous SQL query failed. Rewrite it to fix the error.

    PARSED INTENT:
    {parsed_intent}

    PREVIOUS SQL:
    {generated_sql}

    ERROR:
    {sql_error}

    RULES:
    - Table name is always "superstore"
    - Use exact column names as provided in parsed intent
    - Wrap column names with spaces in double quotes e.g. "Order Date"
    - Order Date is stored as text in M/D/YYYY format e.g. '11/8/2016'
    - For year filtering use: strftime('%Y', "Order Date") = '2017'
    - For month filtering use: strftime('%m', "Order Date") = '01'
    - For date range filtering use: "Order Date" BETWEEN '1/1/2017' AND '12/31/2017'
    - Return only the SQL query, no explanation, no markdown, no preamble
    - Always alias aggregated columns e.g. SUM("Sales") AS total_Sales

    CORRECTED SQL:"""

    response = llm.invoke(prompt).content
    response = response.strip().strip("```sql").strip("```").strip()

    return {"generated_sql": response,"sql_attempt_count": state.get("sql_attempt_count",0) + 1}
  

def validate_sql(state: AgentState):
  cursor = conn.cursor()

  cursor.execute("PRAGMA table_info(superstore)")
  columns = cursor.fetchall()
  column_names = [column[1] for column in columns]

  parsed_intent = state["parsed_intent"]
  validation_errors = []

  cursor.execute("SELECT name from sqlite_master WHERE type='table'")
  tables = [row[0] for row in cursor.fetchall()]
  if parsed_intent["table_name"] not in tables:
    validation_errors.append(f"Table '{parsed_intent["table_name"]}' not found in database")

  referenced_columns = []

  referenced_columns.append(parsed_intent["target_metric"])
  
  if parsed_intent["group_by"]:
    referenced_columns.extend(parsed_intent["group_by"])
  if parsed_intent["filters"]:
    referenced_columns.extend(parsed_intent["filters"].keys())

  if parsed_intent["sort_by"]:
    referenced_columns.append(parsed_intent["sort_by"])
  if parsed_intent["time_range"] and parsed_intent["time_range"].get("column"):
    referenced_columns.append(parsed_intent["time_range"]["column"])

  for column_name in referenced_columns:
    if column_name not in column_names:
      validation_errors.append(f"Column '{column_name}' not found in schema")
  
  return {"validation_errors": validation_errors}


def execute_query(state: AgentState):
  try:
    results = pd.read_sql(state["generated_sql"],conn)

    if not results.empty:
      query_results = results.to_dict(orient="records")
      return {
        "query_results": query_results,
        "sql_error": None,
        "result_summary": {
        "row_count": len(results),
        "columns": results.columns.tolist(),
        "sample_rows": results.head(5).to_dict(orient="records")
      }}
    else:
      return {"sql_error": "Query returned no results"}
    
  except Exception as e:
    return {"sql_error": str(e)}
  

def cannot_execute(state: AgentState):
    errors = state.get("sql_error") or "\n".join(state.get("validation_errors", []))
    return {"error_message": f"Failed after 3 attempts. Last error: {errors}"}


def interpret_results(state: AgentState):
  user_question = state["user_question"]
  result_summary = json.dumps(state["result_summary"],indent=2)

  prompt = f"""You are a data analyst explaining query results to a business user.

    QUESTION:
    {user_question}

    RESULT SUMMARY:
    {result_summary}

    RULES:
    - Explain the results in plain English
    - Be concise, 2-3 sentences max
    - Highlight the most important insight
    - Use actual numbers from the results
    - Do not mention SQL, databases, or technical terms
    - Use $ symbol for currency values, never backticks
    - Do not use any markdown formatting in your response
    - Do not make up data that is not in the results"""
  try:
    response = llm.invoke(prompt).content
    response = response.replace("`", "")
    
    return {"interpretation": response}
  except Exception as e:
    return {"error_message": str(e)}
  


def generate_visualization(state: AgentState):
  user_question = state["user_question"]
  result_summary = state["result_summary"]

  prompt = f"""You are a data visualization expert.

    Given a user question and query results, decide the best chart to visualize the data.

    QUESTION:
    {user_question}

    RESULT SUMMARY:
    {result_summary}

    RULES:
    - Choose chart_type from: bar, line, scatter, pie
    - x_column and y_column must be exact column names from the result
    - color_column is optional, set to null if not needed
    - pie chart only when data has 2 columns and represents parts of a whole
    - line chart only when data has a time dimension
    - bar chart for comparisons and rankings
    - scatter for correlations between two metrics
    - title should be a clean business-friendly description of the chart"""
  
  try:
    if len(state["result_summary"]["columns"]) > 1 and state["result_summary"]["row_count"] > 1:
      response = visualization_spec_llm.invoke(prompt)
      spec = response.model_dump()

      df = pd.DataFrame(state["query_results"])
      chart_type = spec["chart_type"]
      x = spec["x_column"]
      y = spec["y_column"]
      color = spec.get("color_column")
      title = spec["title"]

      if chart_type == "bar":
        fig = px.bar(df, x=x, y=y, color=color, title=title)
      elif chart_type == "line":
        fig = px.line(df, x=x, y=y, color=color, title=title)
      elif chart_type == "scatter":
        fig = px.scatter(df, x=x, y=y, color=color, title=title)
      elif chart_type == "pie":
        fig = px.pie(df, names=x, values=y, title=title)
      else:
        fig = None

      return {
        "visualization_spec": spec,
        "visualization_figure": fig
      }
    else:
      return {"visualization_spec": None, "visualization_figure": None}
  except Exception as e:
    return {"error_message": str(e)}