# import pandas as pd
# import yfinance as yf

# COLUMN_MAP = {
#     "Name, Div % Yield": "Name",
#     "Sym": "Symbol",
#     "Close": "Price",
#     "EPS": "EPS RTG",
#     "RS": "REL STR",
#     "SECTOR": "Sector"
# }


# def get_returns(symbol):

#     try:

#         hist = yf.download(
#             symbol,
#             period="30mo",
#             auto_adjust=True,
#             progress=False
#         )

#         if hist.empty:
#             return None, None

#         latest_price = float(hist["Close"].iloc[-1])

#         six_month_cutoff = hist.index.max() - pd.DateOffset(months=6)
#         twentyfour_month_cutoff = hist.index.max() - pd.DateOffset(months=24)

#         six_df = hist.loc[hist.index <= six_month_cutoff]
#         tf_df = hist.loc[hist.index <= twentyfour_month_cutoff]

#         if len(six_df) == 0 or len(tf_df) == 0:
#             return None, None

#         price_6m = float(six_df["Close"].iloc[-1])
#         price_24m = float(tf_df["Close"].iloc[-1])

#         r6 = ((latest_price / price_6m) - 1) * 100
#         r24 = ((latest_price / price_24m) - 1) * 100

#         return round(r6, 2), round(r24, 2)

#     except Exception:
#         return None, None


# def process_excel(input_file, output_file):

#     df = pd.read_excel(input_file)

#     df.rename(columns=COLUMN_MAP, inplace=True)

#     df = df[
#         [
#             "Name",
#             "Symbol",
#             "Price",
#             "EPS RTG",
#             "REL STR",
#             "Sector"
#         ]
#     ]

#     df["EPS RTG"] = pd.to_numeric(
#         df["EPS RTG"],
#         errors="coerce"
#     )

#     df["REL STR"] = pd.to_numeric(
#         df["REL STR"],
#         errors="coerce"
#     )

#     standard_filter = (
#         (df["EPS RTG"] >= 80)
#         &
#         (df["REL STR"] >= 80)
#     )

#     exception_filter = (
#         (df["EPS RTG"] >= 91)
#         &
#         (df["REL STR"].between(77,79))
#     )

#     df = df[
#         standard_filter | exception_filter
#     ].copy()

#     six_month_returns = []
#     twentyfour_month_returns = []

#     # Batch download historical close prices for all symbols in one request
#     symbols = list(df["Symbol"].astype(str))

#     if symbols:
#         try:
#             hist = yf.download(
#                 tickers=symbols,
#                 period="30mo",
#                 auto_adjust=True,
#                 progress=False,
#                 threads=True
#             )
#         except Exception:
#             hist = None

#         # Extract Close prices; handle single-symbol (Series) and multi-symbol (DataFrame)
#         close = None
#         if isinstance(hist, pd.DataFrame):
#             try:
#                 close = hist["Close"]
#             except Exception:
#                 # In some yfinance versions the structure may differ
#                 close = hist

#         for symbol in symbols:
#             try:
#                 if close is None:
#                     six_month_returns.append(None)
#                     twentyfour_month_returns.append(None)
#                     continue

#                 if isinstance(close, pd.DataFrame):
#                     if symbol not in close.columns:
#                         six_month_returns.append(None)
#                         twentyfour_month_returns.append(None)
#                         continue
#                     series = close[symbol].dropna()
#                 else:
#                     # single-series case
#                     series = close.dropna()

#                 if series.empty:
#                     six_month_returns.append(None)
#                     twentyfour_month_returns.append(None)
#                     continue

#                 latest_price = float(series.iloc[-1])
#                 max_date = series.index.max()

#                 six_month_cutoff = max_date - pd.DateOffset(months=6)
#                 twentyfour_month_cutoff = max_date - pd.DateOffset(months=24)

#                 six_series = series.loc[series.index <= six_month_cutoff].dropna()
#                 tf_series = series.loc[series.index <= twentyfour_month_cutoff].dropna()

#                 if six_series.empty or tf_series.empty:
#                     six_month_returns.append(None)
#                     twentyfour_month_returns.append(None)
#                     continue

#                 price_6m = float(six_series.iloc[-1])
#                 price_24m = float(tf_series.iloc[-1])

#                 r6 = ((latest_price / price_6m) - 1) * 100
#                 r24 = ((latest_price / price_24m) - 1) * 100

#                 six_month_returns.append(round(r6, 2))
#                 twentyfour_month_returns.append(round(r24, 2))

#             except Exception:
#                 six_month_returns.append(None)
#                 twentyfour_month_returns.append(None)

#     df["6-Month Return"] = six_month_returns
#     df["24-Month Return"] = twentyfour_month_returns

#     df["Weighted Return"] = (
#         df["6-Month Return"] * 0.35 +
#         df["24-Month Return"] * 0.65
#     ).round(2)

#         # Convert return columns to numeric (handles None values)
#     df["6-Month Return"] = pd.to_numeric(
#         df["6-Month Return"],
#         errors="coerce"
#     )

#     df["24-Month Return"] = pd.to_numeric(
#         df["24-Month Return"],
#         errors="coerce"
#     )

#     df["Weighted Return"] = pd.to_numeric(
#         df["Weighted Return"],
#         errors="coerce"
#     )

#     # Remove rows where return values could not be calculated
#     df = df.dropna(
#         subset=[
#             "6-Month Return",
#             "24-Month Return",
#             "Weighted Return"
#         ]
#     )

#     # New Screening Rule:
#     # Disqualify stocks whose 6-Month Return is greater than the 24-Month Return
#     df = df[
#         df["6-Month Return"] <= df["24-Month Return"]
#     ].copy()

#     # Sort by Weighted Return (highest first)
#     df.sort_values(
#         by="Weighted Return",
#         ascending=False,
#         inplace=True
#     )

#     # Reset index for clean Excel output
#     df.reset_index(drop=True, inplace=True)

#     # Write to Excel
#     df.to_excel(
#         output_file,
#         index=False
#     )


import pandas as pd
import yfinance as yf

COLUMN_MAP = {
    "Name, Div % Yield": "Name",
    "Sym": "Symbol",
    "Close": "Price",
    "EPS": "EPS RTG",
    "RS": "REL STR",
    "SECTOR": "Sector"
}


def process_excel(
        input_file,
        biblical_file,
        output_file
):

    print("Reading input Excel...")

    df = pd.read_excel(input_file)
    screen_df = pd.read_excel(biblical_file)

    df.rename(columns=COLUMN_MAP, inplace=True)

    required_columns = [
        "Name",
        "Symbol",
        "Price",
        "EPS RTG",
        "REL STR",
        "Sector"
    ]

    df = df[required_columns].copy()

    df["EPS RTG"] = pd.to_numeric(df["EPS RTG"], errors="coerce")
    df["REL STR"] = pd.to_numeric(df["REL STR"], errors="coerce")

    #############################################################
    # Initial Screening
    #############################################################

    standard_filter = (
        (df["EPS RTG"] >= 80) &
        (df["REL STR"] >= 80)
    )

    exception_filter = (
        (df["EPS RTG"] >= 91) &
        (df["REL STR"].between(77, 79))
    )

    df = df.loc[
        standard_filter | exception_filter
    ].copy()

    print(f"Stocks after EPS/RS filtering : {len(df)}")

    #############################################################
    # Download Historical Prices
    #############################################################

    symbols = (
        df["Symbol"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    if len(symbols) == 0:
        df.to_excel(output_file, index=False)
        return

    print("Downloading latest market data from Yahoo Finance...")

    try:

        history = yf.download(
            tickers=symbols,
            period="30mo",
            auto_adjust=True,
            progress=False,
            threads=True,
            group_by="ticker"
        )

    except Exception as ex:
        raise Exception(f"Yahoo Finance Download Failed : {ex}")

    #############################################################
    # Calculate Returns
    #############################################################

    current_price_dict = {}
    six_month_dict = {}
    twentyfour_month_dict = {}


    volatility_dict = {}
    trend_score_dict = {}
    technical_score_dict = {}

    for symbol in symbols:

        try:

            if len(symbols) == 1:
                prices = history["Close"].dropna()

            else:

                if symbol not in history.columns.levels[0]:
                    continue

                prices = history[symbol]["Close"].dropna()

            if prices.empty:
                continue

            latest_price = float(prices.iloc[-1])

            latest_date = prices.index.max()

            six_month_date = latest_date - pd.DateOffset(months=6)
            twentyfour_month_date = latest_date - pd.DateOffset(months=24)

            six_prices = prices.loc[
                prices.index <= six_month_date
            ]

            tf_prices = prices.loc[
                prices.index <= twentyfour_month_date
            ]

            if six_prices.empty or tf_prices.empty:
                continue

            price_6m = float(six_prices.iloc[-1])
            price_24m = float(tf_prices.iloc[-1])

            six_return = (
                (latest_price / price_6m) - 1
            ) * 100

            twentyfour_return = (
                (latest_price / price_24m) - 1
            ) * 100

            current_price_dict[symbol] = round(latest_price, 2)

            six_month_dict[symbol] = round(six_return, 2)

            twentyfour_month_dict[symbol] = round(
                twentyfour_return,
                2
            )


            ########################################################
            # Volatility
            ########################################################

            daily_returns = prices.pct_change().dropna()

            volatility = daily_returns.std() * (252 ** 0.5)

            volatility_dict[symbol] = round(volatility * 100, 2)

            ########################################################
            # Trend Score
            ########################################################

            positive_days = (daily_returns > 0).sum()

            trend_score = (
                positive_days /
                len(daily_returns)
            ) * 100

            trend_score_dict[symbol] = round(trend_score, 2)

            ########################################################
            # Technical Score
            ########################################################

            sma50 = prices.rolling(50).mean().iloc[-1]

            sma200 = prices.rolling(200).mean().iloc[-1]

            score = 0

            if latest_price > sma50:
                score += 1

            if latest_price > sma200:
                score += 1

            if sma50 > sma200:
                score += 1

            technical_score_dict[symbol] = score

        except Exception:
            continue

    #############################################################
    # Populate DataFrame
    #############################################################

    df["Price"] = df["Symbol"].map(current_price_dict)

    df["6-Month Return"] = df["Symbol"].map(
        six_month_dict
    )

    df["24-Month Return"] = df["Symbol"].map(
        twentyfour_month_dict
    )


    df["Volatility"] = df["Symbol"].map(volatility_dict)

    df["Trend Score"] = df["Symbol"].map(trend_score_dict)

    df["Technical Score"] = df["Symbol"].map(technical_score_dict)

    #############################################################
    # Weighted Return
    #############################################################

    df["Weighted Return"] = (
        (df["6-Month Return"] * 0.35)
        +
        (df["24-Month Return"] * 0.65)
    ).round(2)

    #############################################################
    # Remove Missing Data
    #############################################################

    df.dropna(
    subset=[
        "Price",
        "6-Month Return",
        "24-Month Return",
        "Weighted Return",
        "Volatility",
        "Trend Score",
        "Technical Score"
    ],
    inplace=True
)

    #############################################################
    # Additional Screening Rule
    #############################################################

    # Remove stocks where 6 Month Return > 24 Month Return

    df = df[
        df["6-Month Return"]
        <=
        df["24-Month Return"]
    ].copy()



    df["Overall Rank"] = (
    df["Weighted Return"]
      .rank(method="dense", ascending=False)
      .astype(int)
    )

    

        #############################################################
    # Rank Within Each Sector
    #############################################################

    # Sort by Sector and Weighted Return
    df.sort_values(
        by=["Sector", "Weighted Return"],
        ascending=[True, False],
        inplace=True
    )

    # Rank securities inside each sector
    df["Sector Rank"] = (
        df.groupby("Sector")["Weighted Return"]
        .rank(method="dense", ascending=False)
        .astype(int)
    )

    df.sort_values(
        by=[
            "Sector",
            "Sector Rank"
        ],
        ascending=[
            True,
            True
        ],
        inplace=True
    )



    #############################################################
    # Biblical Screening (Fail List)
    #############################################################

    import re

    # Read fail list
    fail_df = pd.read_excel(biblical_file)

    fail_df.columns = fail_df.columns.str.strip()


    def normalize_name(name):
        if pd.isna(name):
            return ""

        name = str(name).upper().strip()

        # Remove punctuation
        name = re.sub(r'[^A-Z0-9 ]', '', name)

        # Remove multiple spaces
        name = " ".join(name.split())

        return name


    # Normalize names in fail file
    fail_df["Name"] = (
        fail_df["Name"]
        .apply(normalize_name)
    )

    # Normalize names in filtered stocks
    df["Name"] = (
        df["Name"]
        .apply(normalize_name)
    )

    #############################################################
    # Convert fail names to a Set
    #############################################################

    fail_names = set(fail_df["Name"])

    #############################################################
    # Remove Failed Stocks
    #############################################################

    df = df[
        ~df["Name"].isin(fail_names)
    ].copy()

    #############################################################
    # Add Screen Test Column
    #############################################################

    df["Screen Test"] = "Pass"

    df.reset_index(
        drop=True,
        inplace=True
    )

   
    #############################################################
    # Export Excel
    #############################################################

    df.to_excel(
        output_file,
        index=False
    )

    print("===================================")
    print("Screening Completed Successfully")
    print(f"Stocks Selected : {len(df)}")
    print(f"Output File : {output_file}")
    print("===================================")