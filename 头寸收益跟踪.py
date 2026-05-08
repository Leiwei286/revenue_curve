import json
import os
from datetime import datetime, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import tushare as ts


TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")
SKIP_TIME_CHECK = os.getenv("SKIP_TIME_CHECK", "0") == "1"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POSITIONS_FILE = os.path.join(BASE_DIR, "持仓录入.csv")
HISTORY_FILE = os.path.join(BASE_DIR, "portfolio_history.csv")
DETAIL_FILE = os.path.join(BASE_DIR, "portfolio_detail_latest.csv")
PLOT_FILE = os.path.join(BASE_DIR, "portfolio_pnl_ratio_curve.png")
SUMMARY_FILE = os.path.join(BASE_DIR, "latest_summary.json")


def build_api():
    if not TUSHARE_TOKEN:
        raise RuntimeError("TUSHARE_TOKEN environment variable is not set.")
    ts.set_token(TUSHARE_TOKEN)
    return ts.pro_api()


def load_positions():
    if not os.path.exists(POSITIONS_FILE):
        raise FileNotFoundError("Positions file not found: {}".format(POSITIONS_FILE))

    positions = pd.read_csv(POSITIONS_FILE)
    required_columns = ["ts_code", "position_qty", "cost_price"]
    missing = [column for column in required_columns if column not in positions.columns]
    if missing:
        raise ValueError("Positions file is missing columns: " + ",".join(missing))

    positions = positions.copy()
    positions["ts_code"] = positions["ts_code"].astype(str).str.strip()
    positions["position_qty"] = positions["position_qty"].astype(float)
    positions["cost_price"] = positions["cost_price"].astype(float)
    positions = positions[positions["ts_code"] != ""]
    if positions.empty:
        raise ValueError("No valid positions found in positions file.")

    return positions


def get_latest_trade_date(pro, ts_code, now):
    end_date = now.strftime("%Y%m%d")
    start_date = (now - timedelta(days=30)).strftime("%Y%m%d")
    df = pro.daily(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        fields="trade_date",
    )
    if df.empty:
        raise RuntimeError("No recent daily data found for {}".format(ts_code))

    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    latest_trade_date = df["trade_date"].max()
    return latest_trade_date.strftime("%Y%m%d")


def get_portfolio_trade_date(pro, positions, now):
    trade_dates = []
    for ts_code in positions["ts_code"].tolist():
        trade_dates.append(get_latest_trade_date(pro, ts_code, now))
    return min(trade_dates)


def fetch_position_details(pro, positions, trade_date):
    details = []
    for _, row in positions.iterrows():
        ts_code = row["ts_code"]
        df = pro.daily(
            ts_code=ts_code,
            trade_date=trade_date,
            fields="ts_code,trade_date,close,pct_chg",
        )
        if df.empty:
            raise RuntimeError("No daily snapshot returned for {}".format(ts_code))

        daily_row = df.iloc[0]
        position_qty = float(row["position_qty"])
        cost_price = float(row["cost_price"])
        close_price = float(daily_row["close"])
        pct_chg = float(daily_row["pct_chg"])
        cost_value = position_qty * cost_price
        market_value = position_qty * close_price
        pnl = market_value - cost_value
        pnl_ratio = pnl / cost_value if cost_value else 0.0

        details.append(
            {
                "trade_date": daily_row["trade_date"],
                "ts_code": ts_code,
                "position_qty": position_qty,
                "cost_price": cost_price,
                "close": close_price,
                "pct_chg": pct_chg,
                "cost_value": round(cost_value, 2),
                "market_value": round(market_value, 2),
                "pnl": round(pnl, 2),
                "pnl_ratio": round(pnl_ratio, 6),
            }
        )

    detail_df = pd.DataFrame(details)
    detail_df = detail_df.sort_values("ts_code").reset_index(drop=True)
    return detail_df


def build_portfolio_snapshot(detail_df):
    trade_date = str(detail_df["trade_date"].iloc[0])
    total_cost = float(detail_df["cost_value"].sum())
    total_market_value = float(detail_df["market_value"].sum())
    total_pnl = total_market_value - total_cost
    total_pnl_ratio = total_pnl / total_cost if total_cost else 0.0

    return {
        "trade_date": trade_date,
        "position_count": int(len(detail_df)),
        "total_cost_value": round(total_cost, 2),
        "total_market_value": round(total_market_value, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_ratio": round(total_pnl_ratio, 6),
    }


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return pd.DataFrame()
    return pd.read_csv(HISTORY_FILE)


def normalize_trade_date_series(series):
    normalized = series.astype(str).str.replace("-", "", regex=False).str.strip()
    return pd.to_datetime(normalized, format="%Y%m%d")


def save_outputs(detail_df, snapshot):
    detail_df.to_csv(DETAIL_FILE, index=False, encoding="utf-8-sig")

    history = load_history()
    is_new_trade_date = True
    if not history.empty:
        existing_trade_dates = set(history["trade_date"].astype(str).tolist())
        is_new_trade_date = snapshot["trade_date"] not in existing_trade_dates

    latest = pd.DataFrame([snapshot])
    if history.empty:
        merged = latest
    else:
        merged = pd.concat([history, latest], ignore_index=True)
        merged = merged.drop_duplicates(subset=["trade_date"], keep="last")

    merged["trade_date"] = normalize_trade_date_series(merged["trade_date"])
    merged = merged.sort_values("trade_date").reset_index(drop=True)
    merged["trade_date"] = merged["trade_date"].dt.strftime("%Y%m%d")
    merged.to_csv(HISTORY_FILE, index=False, encoding="utf-8-sig")
    return merged, is_new_trade_date


def plot_curve(history):
    plot_history = history.copy()
    plot_history["trade_date"] = normalize_trade_date_series(plot_history["trade_date"])
    plt.figure(figsize=(10, 5))
    plt.plot(
        plot_history["trade_date"],
        plot_history["total_pnl_ratio"] * 100,
        marker="o",
        linewidth=1.8,
    )
    plt.axhline(0, color="gray", linestyle="--", linewidth=1)
    plt.title("Portfolio PnL Ratio")
    plt.xlabel("Trade Date")
    plt.ylabel("PnL Ratio (%)")
    plt.grid(True, linestyle="--", alpha=0.35)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(PLOT_FILE, dpi=150)
    plt.close()


def write_summary(snapshot, is_new_trade_date):
    summary = {
        "is_new_trade_date": is_new_trade_date,
        "trade_date": snapshot["trade_date"],
        "position_count": snapshot["position_count"],
        "total_cost_value": snapshot["total_cost_value"],
        "total_market_value": snapshot["total_market_value"],
        "total_pnl": snapshot["total_pnl"],
        "total_pnl_ratio": snapshot["total_pnl_ratio"],
        "positions_file": POSITIONS_FILE,
        "detail_file": DETAIL_FILE,
        "history_file": HISTORY_FILE,
        "plot_file": PLOT_FILE,
    }
    with open(SUMMARY_FILE, "w", encoding="utf-8") as file_obj:
        json.dump(summary, file_obj, ensure_ascii=False, indent=2)


def main():
    now = datetime.now()
    positions = load_positions()
    pro = build_api()
    trade_date = get_portfolio_trade_date(pro, positions, now)
    detail_df = fetch_position_details(pro, positions, trade_date)
    snapshot = build_portfolio_snapshot(detail_df)
    history, is_new_trade_date = save_outputs(detail_df, snapshot)
    plot_curve(history)
    write_summary(snapshot, is_new_trade_date)

    print("Update finished")
    print("trade_date: {}".format(snapshot["trade_date"]))
    print("position_count: {}".format(snapshot["position_count"]))
    print("total_cost_value: {}".format(snapshot["total_cost_value"]))
    print("total_market_value: {}".format(snapshot["total_market_value"]))
    print("total_pnl: {}".format(snapshot["total_pnl"]))
    print("total_pnl_ratio: {:.2f}%".format(snapshot["total_pnl_ratio"] * 100))
    print("is_new_trade_date: {}".format(is_new_trade_date))
    print("positions_file: {}".format(POSITIONS_FILE))
    print("detail_file: {}".format(DETAIL_FILE))
    print("history_file: {}".format(HISTORY_FILE))
    print("plot_file: {}".format(PLOT_FILE))
    print("summary_file: {}".format(SUMMARY_FILE))


if __name__ == "__main__":
    main()
