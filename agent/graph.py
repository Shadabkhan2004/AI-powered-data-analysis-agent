from langgraph.graph import StateGraph, START,END, add_messages
import json
import plotly.express as px
from agent.state import AgentState
from agent.nodes import parse_question,generate_sql,validate_sql,execute_query,cannot_execute,interpret_results,generate_visualization


def check_val_errors_condition(state: AgentState):
  if state.get("validation_errors") and state.get("sql_attempt_count") < 3:
    return "generate_sql"
  elif state.get("validation_errors") and state.get("sql_attempt_count") >= 3:
    return "cannot_execute"
  else:
    return "execute_query"
  
def check_execution_condition(state: AgentState):
    if state.get("sql_error"):
        if state.get("sql_attempt_count", 0) >= 3:
            return "cannot_execute"
        return "generate_sql"
    return "interpret_results"

graph = StateGraph(AgentState)

graph.add_node("parse_question",parse_question)
graph.add_node("generate_sql",generate_sql)
graph.add_node("validate_sql",validate_sql)
graph.add_node("execute_query",execute_query)
graph.add_node("cannot_execute",cannot_execute)
graph.add_node("interpret_results",interpret_results)
graph.add_node("generate_visualization",generate_visualization)

graph.add_edge(START,"parse_question")
graph.add_edge("parse_question","generate_sql")
graph.add_edge("generate_sql","validate_sql")
graph.add_conditional_edges("validate_sql",check_val_errors_condition)
graph.add_conditional_edges("execute_query",check_execution_condition)

graph.add_edge("interpret_results","generate_visualization")
graph.add_edge("generate_visualization",END)
graph.add_edge("cannot_execute",END)
agent = graph.compile()
  

