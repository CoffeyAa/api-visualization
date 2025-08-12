import os
import requests
import pandas as pd
import json
from datetime import datetime
from sqlalchemy import create_engine, Integer, DateTime, Float, String, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from dotenv import load_dotenv

load_dotenv()
api_url = os.getenv("API_URL")
api_key = os.getenv("API_KEY")
database_url = os.getenv("DATABASE_URL")
series_ids = os.getenv("SERIES_IDS").split(",") # type: ignore
start_year = os.getenv("START_YEAR")
end_year = os.getenv("END_YEAR")

def extract_data():
    """
    Uses pythons request library to make a post call to our API url.
    Raises HTTPError if unsuccessful.
    
    Returns
    --------
    json object of the response data
    """
    headers = {'Content-type': 'application/json'}
    data = json.dumps({"seriesid": series_ids, "startyear":start_year, "endyear":end_year, "catalog":True, "registrationkey":api_key})
    response = requests.post(api_url, data=data, headers=headers) # type: ignore
    response.raise_for_status()
    return response.json()

def transform_data(json_data)->pd.DataFrame:
    """
    Takes json data from API call and transforms it into a dataframe.
    BLS has different cassing for catalog vs data k,v pairs (Very annoying) so everything has been converted to lowercase
    """
    series = json_data.get("Results", {}).get("series", [])
    if not series:
        raise ValueError("No series data found in API response")
    all_data = []
    for s in series:
        title_info_dict = s.get("catalog", {})
        title_info_dict = {k.replace("_", ""): v for k,v in title_info_dict.items()}
        for entry in s.get("data", []):
            row_dict = entry.copy()
            row_dict["seriesid"] = s.get("seriesID")
            row_dict.update(title_info_dict)
            all_data.append(row_dict)
    df = pd.DataFrame(all_data)
    df.columns = df.columns.str.lower()
    df["latest"] = df["latest"].fillna(False).astype(bool)
    df["latest"] = df["latest"].replace("true", True).astype(bool)
    return df

def load_to_postgres(df, table_name="api_data"):
    """
    Creates a sqlalchmey engine, converts the DF to sql, and loads it into the postgresql table
    """
    print("saving data to postgres...")
    engine = create_engine(database_url) # type: ignore
    with engine.begin() as connection:
        df.to_sql(
            table_name, 
            con=connection, 
            if_exists="replace", 
            index=False,
            dtype={
                "year": Integer,
                "period": String,
                "periodname": String,
                "value": Float,
                "latest": Boolean,
                "footnotes": JSONB,
                "seriesid": String,
                "date": DateTime
            }
        )
    engine.dispose()
    print(f"Saved {len(df)} rows to {table_name}")

def main():
    start = datetime.now()
    print("Running pipeline.....")
    data = extract_data()
    df = transform_data(data)
    load_to_postgres(df)
    end = datetime.now()
    print(f"Pipeline completed in {end-start} seconds")

if __name__ == "__main__":
    main()

