import pandas as pd
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent
csv_path = BASE_DIR / "data" / "superstore.csv"
db_path = BASE_DIR / "data" / "mydatabase.db"

df = pd.read_csv(csv_path, encoding='latin1')
conn = sqlite3.connect(db_path)
df.to_sql(name="superstore", con=conn, if_exists="replace", index=False)
conn.close()
print("Database setup complete.")