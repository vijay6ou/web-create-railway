"""
STOXXO Order Book CSV Parser
Parses raw broker execution log, computes VWAP per strike,
calculates realized P&L, and invokes charge engine.
"""
import csv
import re
import io
from collections import defaultdict
from charge_engine import compute_charges


def parse_symbol(symbol: str) -> dict:
    """
    Parse STOXXO option symbol like NIFTY2640722600PE or SENSEX2641677800CE
    Returns: {index, expiry, strike, option_type}
    """
    m = re.match(
        r'^(NIFTY|BANKNIFTY|SENSEX|FINNIFTY|MIDCPNIFTY)(\d{5,6})(\d{4,6})(CE|PE)$',
        symbol.upper()
    )
    if not m:
        return {"index": symbol, "expiry": None, "strike": None, "option_type": None}

    index      = m.group(1)
    expiry_raw = m.group(2)   # YMMDD format
    strike     = int(m.group(3))
    opt_type   = m.group(4)

    # Parse expiry
    try:
        year  = 2000 + int(expiry_raw[:2])
        month = int(expiry_raw[2:4])
        day   = int(expiry_raw[4:])
        expiry = f"{day:02d}/{month:02d}/{year}"
    except Exception:
        expiry = expiry_raw

    return {
        "index": index,
        "expiry": expiry,
        "strike": strike,
        "option_type": opt_type
    }


def parse_orderbook_csv(csv_text: str) -> dict:
    """
    Parse STOXXO order book CSV text.

    Expected columns (order may vary):
    Symbol, OrderDateTime, Side (BUY/SELL), TradeQty, TradePrice, Status

    Returns computed session data dict.
    """
    warnings = []

    # Try to detect delimiter
    sample = csv_text[:2000]
    delimiter = ',' if sample.count(',') > sample.count('\t') else '\t'

    reader = csv.DictReader(io.StringIO(csv_text), delimiter=delimiter)

    # Normalize column names (strip spaces, lowercase)
    rows = []
    for row in reader:
        normalized = {k.strip().lower().replace(' ', '_'): v.strip() for k, v in row.items()}
        rows.append(normalized)

    if not rows:
        return {"error": "No data rows found in CSV"}

    # Column name aliases (STOXXO uses different names)
    def get_col(row, *names):
        for n in names:
            if n in row:
                return row[n]
        return None

    # Aggregate fills per symbol
    # Structure: {symbol: {buys: [{qty, price}], sells: [{qty, price}]}}
    fills = defaultdict(lambda: {"buys": [], "sells": []})

    executed_count = 0
    rejected_count = 0
    total_buy_val  = 0.0
    total_sell_val = 0.0

    for row in rows:
        status = (get_col(row, 'status', 'orderstatus', 'order_status') or '').upper()

        if 'REJECT' in status or 'CANCEL' in status:
            rejected_count += 1
            continue

        if 'COMPLETE' not in status and 'TRADED' not in status and 'FILLED' not in status:
            if status:
                continue

        symbol = get_col(row, 'symbol', 'tradingsymbol', 'trading_symbol', 'scripname') or ''
        symbol = symbol.strip().upper()
        if not symbol:
            continue

        side  = (get_col(row, 'side', 'transactiontype', 'transaction_type', 'buy/sell') or '').upper()
        qty   = get_col(row, 'tradeqty', 'trade_qty', 'qty', 'filledqty', 'filled_qty', 'quantity')
        price = get_col(row, 'tradeprice', 'trade_price', 'price', 'averageprice', 'average_price', 'avg_price')

        try:
            qty   = float(str(qty).replace(',', ''))
            price = float(str(price).replace(',', ''))
        except (ValueError, TypeError):
            warnings.append(f"Could not parse qty/price for row: {symbol}")
            continue

        if qty <= 0 or price <= 0:
            continue

        executed_count += 1
        value = qty * price

        if 'BUY' in side or 'B' == side:
            fills[symbol]["buys"].append({"qty": qty, "price": price})
            total_buy_val += value
        elif 'SELL' in side or 'S' == side:
            fills[symbol]["sells"].append({"qty": qty, "price": price})
            total_sell_val += value
        else:
            warnings.append(f"Unknown side '{side}' for {symbol}")

    if not fills:
        return {"error": "No valid executed trades found. Check CSV format."}

    total_turnover = total_buy_val + total_sell_val

    # Compute VWAP and P&L per symbol
    strikes = []
    gross_pnl    = 0.0
    total_ce_pnl = 0.0
    total_pe_pnl = 0.0

    for symbol, data in fills.items():
        buys  = data["buys"]
        sells = data["sells"]

        buy_qty   = sum(f["qty"] for f in buys)
        sell_qty  = sum(f["qty"] for f in sells)
        buy_vwap  = sum(f["qty"] * f["price"] for f in buys) / buy_qty  if buy_qty  else 0
        sell_vwap = sum(f["qty"] * f["price"] for f in sells) / sell_qty if sell_qty else 0

        matched_qty = min(buy_qty, sell_qty)

        if matched_qty > 0:
            realized = (sell_vwap - buy_vwap) * matched_qty
        else:
            realized = 0.0

        open_qty  = abs(buy_qty - sell_qty)
        open_side = "BUY" if buy_qty > sell_qty else "SELL" if sell_qty > buy_qty else None

        sym_info = parse_symbol(symbol)

        strike_data = {
            "symbol":      symbol,
            "index":       sym_info["index"],
            "strike":      sym_info["strike"],
            "option_type": sym_info["option_type"],
            "expiry":      sym_info["expiry"],
            "buy_qty":     buy_qty,
            "sell_qty":    sell_qty,
            "buy_vwap":    round(buy_vwap, 2),
            "sell_vwap":   round(sell_vwap, 2),
            "matched_qty": matched_qty,
            "realized":    round(realized, 2),
            "open_qty":    open_qty,
            "open_side":   open_side,
            "is_carry":    open_qty > 0
        }
        strikes.append(strike_data)
        gross_pnl += realized

        if sym_info["option_type"] == "CE":
            total_ce_pnl += realized
        elif sym_info["option_type"] == "PE":
            total_pe_pnl += realized

    # Compute charges
    charges = compute_charges(total_buy_val, total_sell_val, total_turnover)
    net_pnl = gross_pnl - charges["total"]

    # Detect index (most common)
    indices = [s["index"] for s in strikes if s["index"]]
    index_name = max(set(indices), key=indices.count) if indices else "Unknown"

    # Sort strikes by realized P&L descending
    strikes.sort(key=lambda x: x["realized"], reverse=True)

    return {
        "index_name":    index_name,
        "gross_pnl":     round(gross_pnl, 2),
        "net_pnl":       round(net_pnl, 2),
        "ce_pnl":        round(total_ce_pnl, 2),
        "pe_pnl":        round(total_pe_pnl, 2),
        "total_buy_val":  round(total_buy_val, 2),
        "total_sell_val": round(total_sell_val, 2),
        "total_turnover": round(total_turnover, 2),
        "charges_breakdown": charges,
        "total_charges": charges["total"],
        "executed":      executed_count,
        "rejected":      rejected_count,
        "strikes":       strikes,
        "warnings":      warnings,
        "carry_positions": [s for s in strikes if s["is_carry"]]
    }
