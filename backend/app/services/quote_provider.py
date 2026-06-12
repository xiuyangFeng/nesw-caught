from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number


def _coerce_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(slots=True)
class NormalizedSymbol:
    symbol: str
    market: str
    provider_symbol: str


@dataclass(slots=True)
class QuoteRecord:
    symbol: str
    market: str
    provider_symbol: str
    price: float | None
    change_amount: float | None
    change_percent: float | None
    open_price: float | None
    previous_close: float | None
    day_high: float | None
    day_low: float | None
    volume: int | None
    status: str
    source: str
    message: str | None
    fetched_at: datetime


def equivalent_symbol_candidates(symbol: str, market: str | None = None) -> list[str]:
    raw = symbol.strip().upper()
    candidates: list[str] = [raw]

    try:
        normalized = normalize_symbol(raw, market)
    except ValueError:
        return candidates

    if normalized.symbol not in candidates:
        candidates.append(normalized.symbol)

    if normalized.market == "cn":
        digits, suffix = normalized.symbol.split(".", 1)
        for candidate in (digits, f"SH{digits}" if suffix == "SH" else f"SZ{digits}"):
            if candidate not in candidates:
                candidates.append(candidate)

    return candidates


def normalize_symbol(symbol: str, market: str | None = None) -> NormalizedSymbol:
    raw = symbol.strip().upper()
    inferred_market = (market or "").lower()

    if raw.endswith(".SH"):
        digits = raw[:-3]
        if digits.isdigit() and len(digits) == 6:
            return NormalizedSymbol(symbol=f"{digits}.SH", market="cn", provider_symbol=f"{digits}.SS")

    if raw.endswith(".SS"):
        digits = raw[:-3]
        if digits.isdigit() and len(digits) == 6:
            return NormalizedSymbol(symbol=f"{digits}.SH", market="cn", provider_symbol=f"{digits}.SS")

    if raw.endswith(".SZ"):
        digits = raw[:-3]
        if digits.isdigit() and len(digits) == 6:
            return NormalizedSymbol(symbol=f"{digits}.SZ", market="cn", provider_symbol=f"{digits}.SZ")

    if raw.startswith("SH") and raw[2:].isdigit() and len(raw[2:]) == 6:
        digits = raw[2:]
        return NormalizedSymbol(symbol=f"{digits}.SH", market="cn", provider_symbol=f"{digits}.SS")

    if raw.startswith("SZ") and raw[2:].isdigit() and len(raw[2:]) == 6:
        digits = raw[2:]
        return NormalizedSymbol(symbol=f"{digits}.SZ", market="cn", provider_symbol=f"{digits}.SZ")

    if inferred_market == "cn" and raw.isdigit() and len(raw) == 6:
        if raw.startswith("6"):
            return NormalizedSymbol(symbol=f"{raw}.SH", market="cn", provider_symbol=f"{raw}.SS")
        if raw.startswith(("0", "3")):
            return NormalizedSymbol(symbol=f"{raw}.SZ", market="cn", provider_symbol=f"{raw}.SZ")
        raise ValueError(f"unsupported symbol: {symbol}")

    if raw.isdigit() and len(raw) == 6:
        if raw.startswith("6"):
            return NormalizedSymbol(symbol=f"{raw}.SH", market="cn", provider_symbol=f"{raw}.SS")
        if raw.startswith(("0", "3")):
            return NormalizedSymbol(symbol=f"{raw}.SZ", market="cn", provider_symbol=f"{raw}.SZ")

    if raw.endswith(".HK"):
        digits = raw[:-3]
        if digits.isdigit():
            return NormalizedSymbol(symbol=raw, market="hk", provider_symbol=f"{digits.zfill(4)}.HK")

    if raw.startswith("HK") and raw[2:].isdigit():
        return NormalizedSymbol(symbol=raw, market="hk", provider_symbol=f"{raw[2:].zfill(4)}.HK")

    if inferred_market == "hk" and raw.isdigit():
        return NormalizedSymbol(symbol=raw, market="hk", provider_symbol=f"{raw.zfill(4)}.HK")

    if "." not in raw and raw.replace("-", "").isalnum():
        return NormalizedSymbol(symbol=raw, market="us", provider_symbol=raw)

    raise ValueError(f"unsupported symbol: {symbol}")


class YahooFinanceQuoteProvider:
    source_name = "yahoo_finance"

    def fetch_quote(self, normalized: NormalizedSymbol) -> QuoteRecord:
        try:
            import yfinance as yf
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise RuntimeError("yfinance is not installed") from exc

        ticker = yf.Ticker(normalized.provider_symbol)
        history = ticker.history(period="5d", interval="1d", auto_adjust=False)
        if history.empty:
            raise RuntimeError(f"no quote data for {normalized.provider_symbol}")

        latest = history.iloc[-1]
        previous_row = history.iloc[-2] if len(history.index) >= 2 else None

        fast_info = getattr(ticker, "fast_info", {}) or {}
        price = _coerce_float(getattr(fast_info, "get", lambda *_: None)("lastPrice")) or _coerce_float(latest.get("Close"))
        if price is None:
            raise RuntimeError(f"price unavailable for {normalized.provider_symbol}")
        previous_close = _coerce_float(getattr(fast_info, "get", lambda *_: None)("previousClose"))
        if previous_close is None and previous_row is not None:
            previous_close = _coerce_float(previous_row.get("Close"))
        open_price = _coerce_float(latest.get("Open"))
        day_high = _coerce_float(latest.get("High"))
        day_low = _coerce_float(latest.get("Low"))
        volume = _coerce_int(latest.get("Volume"))
        change_amount = price - previous_close if price is not None and previous_close is not None else None
        change_percent = ((change_amount / previous_close) * 100) if change_amount is not None and previous_close else None

        return QuoteRecord(
            symbol=normalized.symbol,
            market=normalized.market,
            provider_symbol=normalized.provider_symbol,
            price=price,
            change_amount=change_amount,
            change_percent=change_percent,
            open_price=open_price,
            previous_close=previous_close,
            day_high=day_high,
            day_low=day_low,
            volume=volume,
            status="ok",
            source=self.source_name,
            message=None,
            fetched_at=datetime.now(timezone.utc),
        )

    def fetch_quotes_batch(self, normalized_list: list[NormalizedSymbol]) -> list[QuoteRecord]:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        if not normalized_list:
            return []

        max_workers = min(len(normalized_list), 10)
        results_map: dict[str, QuoteRecord] = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ns = {
                executor.submit(self.fetch_quote, ns): ns
                for ns in normalized_list
            }
            for future in as_completed(future_to_ns):
                ns = future_to_ns[future]
                try:
                    record = future.result()
                    results_map[ns.symbol] = record
                except Exception as exc:
                    results_map[ns.symbol] = QuoteRecord(
                        symbol=ns.symbol,
                        market=ns.market,
                        provider_symbol=ns.provider_symbol,
                        price=None,
                        change_amount=None,
                        change_percent=None,
                        open_price=open_price if 'open_price' in locals() else None,
                        previous_close=previous_close if 'previous_close' in locals() else None,
                        day_high=day_high if 'day_high' in locals() else None,
                        day_low=day_low if 'day_low' in locals() else None,
                        volume=None,
                        status="fetch_failed",
                        source=self.source_name,
                        message=str(exc),
                        fetched_at=datetime.now(timezone.utc),
                    )

        return [results_map[ns.symbol] for ns in normalized_list]


class TencentQuoteProvider:
    source_name = "tencent_finance"

    def fetch_quote(self, normalized: NormalizedSymbol) -> QuoteRecord:
        if normalized.market not in ("cn", "hk"):
            raise ValueError(f"Tencent provider only supports cn/hk, got: {normalized.market}")

        if normalized.market == "cn":
            digits, suffix = normalized.symbol.split(".", 1)
            code = f"{suffix.lower()}{digits}"
        else:
            digits = "".join(filter(str.isdigit, normalized.symbol))
            code = f"hk{digits.zfill(5)}"

        url = f"http://qt.gtimg.cn/q={code}"

        try:
            import urllib.request
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                content = response.read().decode("gbk")
        except Exception as exc:
            raise RuntimeError(f"failed to fetch data from tencent: {exc}") from exc

        if not content or "=" not in content:
            raise RuntimeError(f"empty or invalid response from tencent for {normalized.symbol}")

        try:
            parts = content.split("=", 1)[1].strip().strip('"').strip(';').split("~")
            if len(parts) < 35:
                raise RuntimeError(f"incomplete data returned from tencent: expected >= 35 fields, got {len(parts)}")

            price = _coerce_float(parts[3])
            previous_close = _coerce_float(parts[4])
            open_price = _coerce_float(parts[5])

            raw_vol = _coerce_float(parts[6])
            if raw_vol is not None:
                volume = int(raw_vol * 100) if normalized.market == "cn" else int(raw_vol)
            else:
                volume = None

            change_amount = _coerce_float(parts[31])
            change_percent = _coerce_float(parts[32])
            day_high = _coerce_float(parts[33])
            day_low = _coerce_float(parts[34])

            if price is None or previous_close is None:
                raise RuntimeError(f"invalid price/close data from tencent: {content}")

            return QuoteRecord(
                symbol=normalized.symbol,
                market=normalized.market,
                provider_symbol=code,
                price=price,
                change_amount=change_amount,
                change_percent=change_percent,
                open_price=open_price,
                previous_close=previous_close,
                day_high=day_high,
                day_low=day_low,
                volume=volume,
                status="ok",
                source=self.source_name,
                message=None,
                fetched_at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            raise RuntimeError(f"failed to parse tencent response: {exc}") from exc

    def fetch_quotes_batch(self, normalized_list: list[NormalizedSymbol]) -> list[QuoteRecord]:
        if not normalized_list:
            return []

        results_map: dict[str, QuoteRecord] = {}
        codes: list[str] = []
        ns_map: dict[str, NormalizedSymbol] = {}

        for ns in normalized_list:
            if ns.market == "cn":
                digits, suffix = ns.symbol.split(".", 1)
                code = f"{suffix.lower()}{digits}"
            elif ns.market == "hk":
                digits = "".join(filter(str.isdigit, ns.symbol))
                code = f"hk{digits.zfill(5)}"
            else:
                results_map[ns.symbol] = QuoteRecord(
                    symbol=ns.symbol,
                    market=ns.market,
                    provider_symbol=ns.provider_symbol,
                    price=None,
                    change_amount=None,
                    change_percent=None,
                    open_price=None,
                    previous_close=None,
                    day_high=None,
                    day_low=None,
                    volume=None,
                    status="fetch_failed",
                    source=self.source_name,
                    message=f"Tencent provider only supports cn/hk, got {ns.market}",
                    fetched_at=datetime.now(timezone.utc),
                )
                continue

            codes.append(code)
            ns_map[code] = ns

        if not codes:
            return [results_map[ns.symbol] for ns in normalized_list]

        url = f"http://qt.gtimg.cn/q={','.join(codes)}"

        try:
            import urllib.request
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                content = response.read().decode("gbk")
        except Exception as exc:
            for code in codes:
                ns = ns_map[code]
                results_map[ns.symbol] = QuoteRecord(
                    symbol=ns.symbol,
                    market=ns.market,
                    provider_symbol=ns.provider_symbol,
                    price=None,
                    change_amount=None,
                    change_percent=None,
                    open_price=None,
                    previous_close=None,
                    day_high=None,
                    day_low=None,
                    volume=None,
                    status="fetch_failed",
                    source=self.source_name,
                    message=str(exc),
                    fetched_at=datetime.now(timezone.utc),
                )
            return [results_map[ns.symbol] for ns in normalized_list]

        lines = [line.strip() for line in content.split("\n") if line.strip() and "=" in line]

        for line in lines:
            try:
                left, right = line.split("=", 1)
                code = left.replace("v_", "").strip()
                ns = ns_map.get(code)
                if not ns:
                    continue

                parts = right.strip().strip('"').strip(';').split("~")
                if len(parts) < 35:
                    raise RuntimeError(f"incomplete fields: expected >= 35, got {len(parts)}")

                price = _coerce_float(parts[3])
                previous_close = _coerce_float(parts[4])
                open_price = _coerce_float(parts[5])

                raw_vol = _coerce_float(parts[6])
                if raw_vol is not None:
                    volume = int(raw_vol * 100) if ns.market == "cn" else int(raw_vol)
                else:
                    volume = None

                change_amount = _coerce_float(parts[31])
                change_percent = _coerce_float(parts[32])
                day_high = _coerce_float(parts[33])
                day_low = _coerce_float(parts[34])

                results_map[ns.symbol] = QuoteRecord(
                    symbol=ns.symbol,
                    market=ns.market,
                    provider_symbol=code,
                    price=price,
                    change_amount=change_amount,
                    change_percent=change_percent,
                    open_price=open_price,
                    previous_close=previous_close,
                    day_high=day_high,
                    day_low=day_low,
                    volume=volume,
                    status="ok",
                    source=self.source_name,
                    message=None,
                    fetched_at=datetime.now(timezone.utc),
                )
            except Exception as exc:
                pass

        for code in codes:
            ns = ns_map[code]
            if ns.symbol not in results_map:
                results_map[ns.symbol] = QuoteRecord(
                    symbol=ns.symbol,
                    market=ns.market,
                    provider_symbol=ns.provider_symbol,
                    price=None,
                    change_amount=None,
                    change_percent=None,
                    open_price=None,
                    previous_close=None,
                    day_high=None,
                    day_low=None,
                    volume=None,
                    status="fetch_failed",
                    source=self.source_name,
                    message="no response or parse error",
                    fetched_at=datetime.now(timezone.utc),
                )

        return [results_map[ns.symbol] for ns in normalized_list]

