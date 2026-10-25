"""DDL for the snapshot. Every TIMESTAMP is naive UTC (see ``app.ingestion.records``)."""

SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE forecasts (
        publish_time TIMESTAMP NOT NULL,
        target_time TIMESTAMP NOT NULL,
        generation_mw INTEGER NOT NULL,
        PRIMARY KEY (publish_time, target_time)
    )
    """,
    """
    CREATE TABLE actuals (
        target_time TIMESTAMP NOT NULL PRIMARY KEY,
        generation_mw INTEGER NOT NULL
    )
    """,
    # One row, written by each ingestion run.
    """
    CREATE TABLE ingestion_metadata (
        ingested_at TIMESTAMP NOT NULL,
        windfor_publish_from TIMESTAMP NOT NULL,
        windfor_publish_to TIMESTAMP NOT NULL,
        fuelhh_settlement_from DATE NOT NULL,
        fuelhh_settlement_to DATE NOT NULL,
        delivery_day_first DATE NOT NULL,
        delivery_day_last DATE NOT NULL,
        forecast_rows_received INTEGER NOT NULL,
        forecast_rows_malformed INTEGER NOT NULL,
        forecast_duplicates_removed INTEGER NOT NULL,
        excluded_forecasts INTEGER NOT NULL,
        forecast_gap_hours INTEGER NOT NULL,
        actual_rows_received INTEGER NOT NULL,
        actual_rows_malformed INTEGER NOT NULL,
        actual_duplicates_removed INTEGER NOT NULL,
        actual_gap_periods INTEGER NOT NULL
    )
    """,
)
