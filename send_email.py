import json
import mimetypes
import os
import smtplib
from email.message import EmailMessage


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SUMMARY_FILE = os.path.join(BASE_DIR, "latest_summary.json")

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.163.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USERNAME)
EMAIL_TO = os.getenv("EMAIL_TO", "15223347847@163.com")


def load_summary():
    with open(SUMMARY_FILE, "r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def build_email(summary):
    message = EmailMessage()
    trade_date = summary["trade_date"]
    pnl_ratio_pct = summary["total_pnl_ratio"] * 100
    message["Subject"] = "Portfolio PnL Curve {}".format(trade_date)
    message["From"] = EMAIL_FROM
    message["To"] = EMAIL_TO

    body = "\n".join(
        [
            "trade_date: {}".format(trade_date),
            "position_count: {}".format(summary["position_count"]),
            "total_cost_value: {}".format(summary["total_cost_value"]),
            "total_market_value: {}".format(summary["total_market_value"]),
            "total_pnl: {}".format(summary["total_pnl"]),
            "total_pnl_ratio: {:.2f}%".format(pnl_ratio_pct),
        ]
    )
    message.set_content(body)

    plot_file = summary["plot_file"]
    mime_type, _ = mimetypes.guess_type(plot_file)
    if not mime_type:
        mime_type = "application/octet-stream"
    maintype, subtype = mime_type.split("/", 1)
    with open(plot_file, "rb") as file_obj:
        message.add_attachment(
            file_obj.read(),
            maintype=maintype,
            subtype=subtype,
            filename=os.path.basename(plot_file),
        )

    return message


def validate_env():
    required = {
        "SMTP_USERNAME": SMTP_USERNAME,
        "SMTP_PASSWORD": SMTP_PASSWORD,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError("Missing email environment variables: " + ",".join(missing))


def main():
    validate_env()
    summary = load_summary()
    if not summary.get("is_new_trade_date", False):
        print("No new trade date. Skip sending email.")
        return

    message = build_email(summary)
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
        smtp.send_message(message)

    print("Email sent to {}".format(EMAIL_TO))


if __name__ == "__main__":
    main()
