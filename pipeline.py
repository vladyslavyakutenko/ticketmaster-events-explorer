import pandas as pd
import sqlalchemy as sa
import requests
import gzip
import json
from config_local import (
    TICKETMASTER_API_KEY,
    TICKETMASTER_RESERVE_KEY,
    MYSQL_HOST,
    MYSQL_USER,
    MYSQL_PASSWORD,
    MYSQL_DATABASE
)

personal_key = TICKETMASTER_API_KEY
personal_key_reserve = TICKETMASTER_RESERVE_KEY ## in case of "quata reach Error"

# Creating mapping dictionaries
rename_map = {
    'eventId': 'event_api_id',
    'eventName': 'event_name',
    'eventStatus': 'event_status',
    'eventStartLocalDate': 'event_start_local_date',
    'eventStartLocalTime': 'event_start_local_time',
    'classificationSegment': 'classification_segment',
    'classificationGenre': 'classification_genre',
    'classificationSubGenre': 'classification_sub_genre',
    'venue.venueCountryCode': 'venue_country_code',
    'venue.venueCity': 'venue_city',
    'eventStartDateTimeUTC': 'event_start_datetime_utc',
    'eventEndDateTimeUTC': 'event_end_datetime_utc',
    'onsaleStartDateTimeUTC': 'onsale_start_datetime_utc',
    'onsaleEndDateTimeUTC': 'onsale_end_datetime_utc'
}

country_map = {
    'IE': 'Ireland',
    'GB': 'United Kingdom',
    'AT': 'Austria',
    'BE': 'Belgium',
    'DE': 'Germany',
    'DK': 'Denmark',
    'ES': 'Spain',
    'FI': 'Finland',
    'NL': 'Netherlands',
    'NO': 'Norway',
    'PL': 'Poland',
    'SE': 'Sweden',
    'CH': 'Switzerland',
    'CZ': 'Czechia',
    'IT': 'Italy',
    'FR': 'France'
}

def get_all_data(personal_key = personal_key) -> pd.DataFrame:
    iteration = 0
    countries = [
    "IE", "GB", "AT", "BE", "DE", "DK", "ES", "FI",
    "NL", "NO", "PL", "SE", "CH", "CZ", "IT", "FR"]
    dataframes_list: list[pd.DataFrame] = []
    root_url: str = "https://app.ticketmaster.com/discovery-feed/v2/events.json"
    for country_code in countries:
        response = requests.get(root_url, params={
            "apikey": personal_key,
            "countryCode": country_code
        }, timeout=120)
        if response.status_code != 200:
            raise requests.HTTPError(f"Something went wrong with {country_code},\
                                     HTTP error code: {response.status_code}", response=response)
        unpacked = gzip.decompress(response.content)
        events = json.loads(unpacked)
        df_var = pd.json_normalize(events["events"])
        dataframes_list.append(df_var)
        iteration += 1
        print(f"Progress: {iteration}/{len(countries)}")
    if not dataframes_list:
        raise ValueError("No DataFrame to concat")
    df: pd.DataFrame = pd.concat(dataframes_list, ignore_index=True)
    if df.empty:
        raise ValueError("Empty DataFrame, nothing to return")
    return df


def data_prep(dataframe: pd.DataFrame) -> pd.DataFrame:
    df = dataframe[['eventId', 'eventName', 'eventStatus','eventStartDateTime', 'eventEndDateTime', 
                        'eventStartLocalDate', 'eventStartLocalTime','onsaleStartDateTime', 'onsaleEndDateTime', 
                        'classificationSegment', 'classificationGenre', 'classificationSubGenre',
                        'venue.venueCountryCode', 'venue.venueCity']]
    # Handling duplicates
    if len(df[df['eventId'].duplicated()]) / len(df) * 100 < 0.1:
        df = df.drop_duplicates(subset=['eventId'])
    else:
        raise ValueError("Too many duplicates in 'eventId'")
    
    # Formating date, time and values
    df['eventStartDateTimeUTC'] = pd.to_datetime(df['eventStartDateTime'], format="%Y-%m-%dT%H:%M:%SZ")
    df['eventEndDateTimeUTC'] = pd.to_datetime(df['eventEndDateTime'], format="%Y-%m-%dT%H:%M:%SZ")
    df['eventStartLocalDate'] = pd.to_datetime(df['eventStartLocalDate'], format="%Y-%m-%d")
    df['eventStartLocalTime'] = pd.to_datetime(df['eventStartLocalTime'], format="mixed").dt.time
    df['onsaleStartDateTimeUTC'] = pd.to_datetime(df['onsaleStartDateTime'], format="%Y-%m-%dT%H:%M:%SZ")
    df['onsaleEndDateTimeUTC'] = pd.to_datetime(df['onsaleEndDateTime'], format="%Y-%m-%dT%H:%M:%SZ")
    df = df.drop(columns=['eventStartDateTime', 'eventEndDateTime', 'onsaleStartDateTime', 
                          'onsaleEndDateTime'])

    # Adding a column with a full country name and renaming columns 
    # as a part of transfer preparation process
    df['venue_country_name'] = df['venue.venueCountryCode'].map(country_map)
    df = df.rename(columns=rename_map)
    return df
    
def data_transfer(df: pd.DataFrame, reserve_key_used: bool = False) -> None:
    # Connecting to a MySQL database with SQLAlchemy
    events_loaded = df.shape[0]
    config = {
        "drivername": "mysql+mysqlconnector",
        "host": MYSQL_HOST,
        "username": MYSQL_USER,
        "password": MYSQL_PASSWORD,
        "database": MYSQL_DATABASE
        }

    url = sa.URL.create(**config)
    engine = sa.create_engine(url)

    # Transfering a DataFrame to the database
    
    try:
        with engine.begin() as conn:
            df.to_sql(
                con=conn,
                name='europe_data_current',
                if_exists='delete_rows',
                index=False,
                chunksize=1000)

        # Transfering a DataFrame to the database
            events_disappeared = conn.exec_driver_sql(
                """
                UPDATE europe_data_archive as a
                LEFT JOIN europe_data_current as c
                    ON a.event_api_id = c.event_api_id
                SET a.is_current = FALSE
                WHERE c.event_api_id IS NULL
                    AND a.is_current = TRUE;
                """
            ).rowcount

            events_rewritten = conn.exec_driver_sql(
                """
                UPDATE europe_data_archive as a
                INNER JOIN europe_data_current as c
                    ON a.event_api_id = c.event_api_id
                SET a.event_start_local_date = c.event_start_local_date,
                    a.event_start_datetime_utc = c.event_start_datetime_utc,
                    a.event_status = c.event_status,
                    a.is_current = TRUE
                WHERE NOT
                    (c.event_start_local_date <=> a.event_start_local_date)
                    OR NOT
                    (c.event_start_datetime_utc <=> a.event_start_datetime_utc)
                    OR NOT
                    (c.event_status <=> a.event_status)
                    OR 
                    a.is_current = FALSE;
                """
            ).rowcount
                    
            new_events_loaded = conn.exec_driver_sql(
                """
                INSERT INTO europe_data_archive(
                    event_api_id,
                    event_name,
                    event_status,
                    event_start_local_date,
                    event_start_local_time, 
                    event_start_datetime_utc, 
                    event_end_datetime_utc,
                    onsale_start_datetime_utc,
                    onsale_end_datetime_utc,
                    venue_country_code,
                    venue_country_name,
                    venue_city,
                    classification_segment,
                    classification_genre,
                    classification_sub_genre,
                    is_current
                )
                SELECT  
                    c.event_api_id,
                    c.event_name,
                    c.event_status,
                    c.event_start_local_date,
                    c.event_start_local_time,
                    c.event_start_datetime_utc,
                    c.event_end_datetime_utc,
                    c.onsale_start_datetime_utc,
                    c.onsale_end_datetime_utc,
                    c.venue_country_code,
                    c.venue_country_name,
                    c.venue_city,
                    c.classification_segment,
                    c.classification_genre,
                    c.classification_sub_genre,
                    TRUE 
                FROM europe_data_current as c
                LEFT JOIN europe_data_archive as a
                    ON c.event_api_id = a.event_api_id
                WHERE a.event_api_id IS NULL;

                """
            ).rowcount

            conn.exec_driver_sql(
                """
                INSERT INTO pipeline_log(
                    iteration_dt,
                    iteration_status,
                    events_loaded,
                    new_events_loaded,
                    events_rewritten,
                    events_disappeared
                )
                VALUES(
                    NOW(),
                    %(iteration_status)s,
                    %(events_loaded)s,
                    %(new_events_loaded)s,
                    %(events_rewritten)s,
                    %(events_disappeared)s
                )
                """, {"iteration_status": ("successful: reserve key used" 
                                           if reserve_key_used
                                           else "successful"),
                      "events_loaded": events_loaded,
                      "new_events_loaded": new_events_loaded,
                      "events_rewritten": events_rewritten,
                      "events_disappeared": events_disappeared}
            )
    except Exception as error:
        print(error)
        try:
            with engine.begin() as error_log_conn:
                error_log_conn.exec_driver_sql(
                    """
                    INSERT INTO pipeline_log(
                        iteration_dt,
                        iteration_status,
                        error_text
                    )
                    VALUES(
                        NOW(),
                        'error occurred',
                        %(error_text)s
                    )
                    """, {"error_text": str(error)}
                )
        except Exception as log_error:
            print(f"logging not successful, error_text: {log_error}")
        raise    
    finally:
        engine.dispose()



def main():
    print("Pipeline started")
    reserve_key_used = False
    try:
        try:
            raw_df = get_all_data()
        except requests.HTTPError as error:
            if error.response.status_code == 429:
                raw_df = get_all_data(personal_key=personal_key_reserve)
                reserve_key_used = True
            else:
                raise

        prepared_df = data_prep(raw_df)
        data_transfer(prepared_df, reserve_key_used)
        print("Pipeline finished")

    except (requests.HTTPError, ValueError) as error:
        print(error)
        raise


if __name__ == "__main__":
    main()
    