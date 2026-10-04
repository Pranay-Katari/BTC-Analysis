# Kalshi Terminal Trader

`ktrade` is an installable, safe-by-default command-line interface for viewing
Kalshi markets and submitting limit orders. It uses demo mode and order previews
unless production and live submission are both selected explicitly.

## Install

```bash
python3 -m pip install -e .
```

Credentials are loaded from `KALSHI_KEY_ID` plus `KALSHI_PRIVATE_KEY`, or from
the existing `kalshi_key_id.txt` and `kalshi_private.pem` files in this project.

## Read-only commands

```bash
ktrade balance
ktrade markets KXBTC15M
ktrade quote KXBTC15M-... --side yes
ktrade position KXBTC15M-...
ktrade orders --ticker KXBTC15M-... --status resting
ktrade order ORDER_ID
```

Add `--prod` immediately after `ktrade` to query production:

```bash
ktrade --prod balance
```

## Limit orders

Commands preview without submitting:

```bash
ktrade --prod buy  KXBTC15M-... yes 10 --limit 62
ktrade --prod sell KXBTC15M-... yes 10 --limit 71 --reduce-only
ktrade --prod buy  KXBTC15M-... no   5 --limit 44 --ioc
```

Review the preview, then add `--live` to submit the exact order:

```bash
ktrade --prod buy KXBTC15M-... yes 10 --limit 62 --live
```

Prices are expressed in cents for the selected economic side. For example,
`buy ... no --limit 63` means buy NO at no more than 63¢; the package safely
converts that to the exchange's YES-book representation.

`--ioc` makes the limit immediate-or-cancel. Without it, the order may rest until
filled or canceled. Use `cancel` and `cancel-all` in preview mode first, then add
`--live` to perform the cancellation.

```bash
ktrade --prod cancel ORDER_ID
ktrade --prod cancel ORDER_ID --live
ktrade --prod cancel-all KXBTC15M-... --live
```

This is execution software, not investment advice. A limit controls price, not
whether an order fills, and partially filled orders can leave open exposure.
