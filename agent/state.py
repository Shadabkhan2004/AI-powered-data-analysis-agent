from typing import Annotated, TypedDict, Any
from pydantic import BaseModel, ConfigDict
from typing import Optional
from pydantic import BaseModel



class TimeRange(BaseModel):
    column: str
    start: Optional[str] = None
    end: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    quarter: Optional[int] = None
    model_config = ConfigDict(extra="forbid")


class ParsedIntent(BaseModel):
    target_metric: str                        
    aggregation: str                          
    filters: Optional[dict[str, str | list[str]]] = None      
    group_by: list[str]                       
    time_range: Optional[TimeRange] = None        
    sort_by: Optional[str] = None              
    sort_order: Optional[str] = None               
    limit: Optional[int] = None                  
    table_name: str = "superstore"
    model_config = ConfigDict(extra="forbid")


class VisualizationSpec(BaseModel):
    chart_type: str        
    x_column: str
    y_column: str
    color_column: Optional[str]
    title: str
    model_config = ConfigDict(extra="forbid")


class AgentState(TypedDict):
    # Input
    user_question: str

    # Intent
    parsed_intent: dict

    # SQL Pipeline
    generated_sql: str
    sql_attempt_count: int
    sql_error: Optional[str]
    validation_errors: list[str]

    # Results
    query_results: list[dict]
    result_summary: dict

    # Output
    interpretation: str
    visualization_spec: dict
    visualization_figure: Any

    # Control
    error_message: Optional[str]

