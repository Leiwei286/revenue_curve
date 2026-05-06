# Portfolio Daily Report

This project tracks a stock portfolio with Tushare data, generates a daily PnL ratio curve, and sends the chart by email from GitHub Actions.

## Files

- `持仓录入.csv`: portfolio input file with columns `ts_code`, `position_qty`, `cost_price`
- `run_portfolio.py`: entry point for scheduled runs
- `头寸收益跟踪.py`: portfolio calculation logic
- `send_email.py`: sends the latest chart email
- `.github/workflows/portfolio_report.yml`: GitHub Actions workflow

## Local usage

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the portfolio update:

```bash
python run_portfolio.py
```

## GitHub Actions setup

Create these repository secrets in GitHub Actions:

- `TUSHARE_TOKEN`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `EMAIL_FROM`

Recommended SMTP values for a 163 mailbox:

- `SMTP_HOST=smtp.163.com`
- `SMTP_PORT=465`
- `EMAIL_FROM=<your_163_email>`

The workflow runs on weekdays at `08:20 UTC`, which is `16:20` Beijing time.

## Email recipient

The default recipient is:

- `15223347847@163.com`

If you want to override it later, add an `EMAIL_TO` repository secret.
