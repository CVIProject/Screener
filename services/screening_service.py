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


def get_returns(symbol):

    try:

        hist = yf.download(
            symbol,
            period="30mo",
            auto_adjust=True,
            progress=False
        )

        if hist.empty:
            return None, None

        latest_price = float(hist["Close"].iloc[-1])

        six_month_cutoff = hist.index.max() - pd.DateOffset(months=6)
        twentyfour_month_cutoff = hist.index.max() - pd.DateOffset(months=24)

        six_df = hist.loc[hist.index <= six_month_cutoff]
        tf_df = hist.loc[hist.index <= twentyfour_month_cutoff]

        if len(six_df) == 0 or len(tf_df) == 0:
            return None, None

        price_6m = float(six_df["Close"].iloc[-1])
        price_24m = float(tf_df["Close"].iloc[-1])

        r6 = ((latest_price / price_6m) - 1) * 100
        r24 = ((latest_price / price_24m) - 1) * 100

        return round(r6, 2), round(r24, 2)

    except Exception:
        return None, None


def process_excel(input_file, output_file):

    df = pd.read_excel(input_file)

    df.rename(columns=COLUMN_MAP, inplace=True)

    df = df[
        [
            "Name",
            "Symbol",
            "Price",
            "EPS RTG",
            "REL STR",
            "Sector"
        ]
    ]

    df["EPS RTG"] = pd.to_numeric(
        df["EPS RTG"],
        errors="coerce"
    )

    df["REL STR"] = pd.to_numeric(
        df["REL STR"],
        errors="coerce"
    )

    standard_filter = (
        (df["EPS RTG"] >= 80)
        &
        (df["REL STR"] >= 80)
    )

    exception_filter = (
        (df["EPS RTG"] >= 91)
        &
        (df["REL STR"].between(77,79))
    )

    df = df[
        standard_filter | exception_filter
    ].copy()

    six_month_returns = []
    twentyfour_month_returns = []

    # Batch download historical close prices for all symbols in one request
    symbols = list(df["Symbol"].astype(str))

    if symbols:
        try:
            hist = yf.download(
                tickers=symbols,
                period="30mo",
                auto_adjust=True,
                progress=False,
                threads=True
            )
        except Exception:
            hist = None

        # Extract Close prices; handle single-symbol (Series) and multi-symbol (DataFrame)
        close = None
        if isinstance(hist, pd.DataFrame):
            try:
                close = hist["Close"]
            except Exception:
                # In some yfinance versions the structure may differ
                close = hist

        for symbol in symbols:
            try:
                if close is None:
                    six_month_returns.append(None)
                    twentyfour_month_returns.append(None)
                    continue

                if isinstance(close, pd.DataFrame):
                    if symbol not in close.columns:
                        six_month_returns.append(None)
                        twentyfour_month_returns.append(None)
                        continue
                    series = close[symbol].dropna()
                else:
                    # single-series case
                    series = close.dropna()

                if series.empty:
                    six_month_returns.append(None)
                    twentyfour_month_returns.append(None)
                    continue

                latest_price = float(series.iloc[-1])
                max_date = series.index.max()

                six_month_cutoff = max_date - pd.DateOffset(months=6)
                twentyfour_month_cutoff = max_date - pd.DateOffset(months=24)

                six_series = series.loc[series.index <= six_month_cutoff].dropna()
                tf_series = series.loc[series.index <= twentyfour_month_cutoff].dropna()

                if six_series.empty or tf_series.empty:
                    six_month_returns.append(None)
                    twentyfour_month_returns.append(None)
                    continue

                price_6m = float(six_series.iloc[-1])
                price_24m = float(tf_series.iloc[-1])

                r6 = ((latest_price / price_6m) - 1) * 100
                r24 = ((latest_price / price_24m) - 1) * 100

                six_month_returns.append(round(r6, 2))
                twentyfour_month_returns.append(round(r24, 2))

            except Exception:
                six_month_returns.append(None)
                twentyfour_month_returns.append(None)

    df["6-Month Return"] = six_month_returns
    df["24-Month Return"] = twentyfour_month_returns

    df["Weighted Return"] = (
        df["6-Month Return"] * 0.35 +
        df["24-Month Return"] * 0.65
    ).round(2)

    df.to_excel(
        output_file,
        index=False
    )