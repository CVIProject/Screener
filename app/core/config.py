from pathlib import Path
class Settings:
    BASE_DIR=Path(__file__).resolve().parent.parent.parent
    DATA_DIR=BASE_DIR/'data'; OUTPUT_DIR=BASE_DIR/'output'
    APP_TITLE='CVI Stock Screener and Market Regime Service'; APP_VERSION='2.0.0'
    FRED_CSV_URL='https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLH0A0HYM2'
    EXPECTED_SHEET_NAME=None; DATE_COLUMN='observation_date'; VALUE_COLUMN='BAMLH0A0HYM2'
    SLOPE_COLUMN='90-Day Slope'; MEDIAN_90_COLUMN='90- Day Median'; MEDIAN_10Y_COLUMN='10-year Median'
    QUAD_COLUMN='QUAD BASED ON MEDIAN'; RULE_3_COLUMN='3 day consecutive Rule'; QAD_VALUE_COLUMN='QAD Value'
    RULE_7_COLUMN='7 day Consecutive Rule'; CONFIRMED_COLUMN='Confirmed Regime (5-Day Streak)'
    TRADE_COLUMN='Trade Regime (5-Day + 15-Day Confirmation)'; CONFIRMATION_START_EXCEL_ROW=2612
    CONFIRM_DAYS=5; TRADE_LOOKBACK_DAYS=15; TRADE_THRESHOLD=9
settings=Settings(); settings.DATA_DIR.mkdir(parents=True,exist_ok=True); settings.OUTPUT_DIR.mkdir(parents=True,exist_ok=True)
