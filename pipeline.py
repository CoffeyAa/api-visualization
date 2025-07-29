import os
import requests
import pandas as pd
import json
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()
api_url = os.getenv("API_URL")
api_key = os.getenv("API_KEY")
database_url = os.getenv("DATABASE_URL")
series_ids = os.getenv("SERIES_IDS").split(",")
start_year = os.getenv("START_YEAR")
end_year = os.getenv("END_YEAR")

def fetch_data():
    headers = {'Content-type': 'application/json'}
    data = json.dumps({"seriesid": series_ids, "startyear":start_year, "endyear":end_year, "catalog":True, "registrationkey":api_key})
    response = requests.post(api_url, data=data, headers=headers)
    print(f"headers: {headers} \ndata:{data} \nresponse:{response} \napi_url:{api_url} \nseries_ids:{series_ids}")
    response.raise_for_status()
    return response.json()

def transform_data(json_data):
    series = json_data.get("Results", {}).get("series", [])
    if not series:
        raise ValueError("No series data found in API response")

    all_data = []
    for s in series:
        for entry in s.get("data", []):
            row = entry.copy()
            row["seriesID"] = s.get("seriesID")
            all_data.append(row)

    df = pd.DataFrame(all_data)
    df.columns = df.columns.str.lower()

    for col in df.columns:
        if df[col].apply(lambda x: isinstance(x, dict)).any():
            print(f"Converting column '{col}' from dict to JSON string")
            df[col] = df[col].apply(json.dumps)

    if "year" in df.columns and "period" in df.columns:
        df["date"] = pd.to_datetime(df["year"] + df["period"].str[1:], format="%Y%m")

    print(f"DATA FRAME:\n{df.head()}")
    return df

def save_to_postgres(df, table_name="api_data"):
    engine = create_engine(database_url)
    with engine.begin() as connection:
        df.to_sql(table_name, con=connection, if_exists="replace", index=False)
    engine.dispose()
    print(f"Saved {len(df)} rows to {table_name}")

def main():
    print("Running pipeline.....")
    data = fetch_data()
    df = transform_data(data)
    save_to_postgres(df)

if __name__ == "__main__":
    main()

