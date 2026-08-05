class Settings:
    MAX_UPLOAD_SIZE_MB = 50

    DATE_COLUMN = "observation_date"
    VALUE_COLUMN = "BAMLH0A0HYM2"

    SLOPE_COLUMN = "90-Day Slope"
    MEDIAN_90_COLUMN = "90-Day Median"
    MEDIAN_10Y_COLUMN = "10-year Median"
    QUAD_COLUMN = "QUAD BASED ON MEDIAN"
    RULE_3_COLUMN = "3 day consecutive Rule"
    QAD_VALUE_COLUMN = "QAD Value"
    RULE_7_COLUMN = "7 day Consecutive Rule"
    CONFIRMED_COLUMN = "Confirmed Regime (5-Day Streak)"
    TRADE_COLUMN = "Trade Regime (5-Day + 15-Day Confirmation)"

    SLOPE_WINDOW = 87
    MEDIAN_90_WINDOW = 89
    MEDIAN_10Y_WINDOW = 2599

    CONFIRM_DAYS = 5
    TRADE_LOOKBACK_DAYS = 15
    TRADE_THRESHOLD = 9


settings = Settings()