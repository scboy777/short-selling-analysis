# =============================================================================
# 공매도 + 주가 + 수급 4-Panel Chart 예시
# =============================================================================
#
# 4개 패널 (같은 X축 공유):
#   Panel 1: 주가 (xbbg PX_LAST)
#   Panel 2: 외국인 누적 순매수
#   Panel 3: 기관 누적 순매수
#   Panel 4: 공매도 잔고비중 (short_data repo)
#
# 사용법:
#   python short_chart_example.py          → 삼성전자 기본
#   python short_chart_example.py 000660   → SK하이닉스
# =============================================================================

import sys
from datetime import date, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ── 설정 ──
TICKER = sys.argv[1] if len(sys.argv) > 1 else "005930"
LOOKBACK_DAYS = 180   # 최근 N 거래일
REPO_DIR = Path("short_data")

# =============================================================================
# 1. 공매도 잔고비중 — short_data/{ticker}.csv에서 로드
# =============================================================================

short_path = REPO_DIR / f"{TICKER}.csv"
if short_path.exists():
    short_df = pd.read_csv(short_path, dtype={"date": str})
    short_df["date"] = pd.to_datetime(short_df["date"], format="%Y%m%d")
    short_df = short_df.set_index("date").sort_index()

    # 잔고비중 컬럼 (한국어 or 영어)
    if "잔고비중" in short_df.columns:
        bal_pct = short_df["잔고비중"].tail(LOOKBACK_DAYS)
    elif "bal_pct" in short_df.columns:
        bal_pct = short_df["bal_pct"].tail(LOOKBACK_DAYS)
    else:
        bal_pct = pd.Series(dtype=float)
else:
    print(f"[WARNING] {short_path} 없음 — 공매도 잔고 패널은 빈 상태로 표시됩니다")
    bal_pct = pd.Series(dtype=float)

# =============================================================================
# 2. 주가 — xbbg에서 가져오기
# =============================================================================

try:
    from xbbg import blp
    end_date = date.today()
    start_date = end_date - timedelta(days=int(LOOKBACK_DAYS * 1.5))  # 여유있게
    bbg_ticker = f"{TICKER} KS Equity"

    price_df = blp.bdh(bbg_ticker, "PX_LAST",
                       start_date.strftime("%Y-%m-%d"),
                       end_date.strftime("%Y-%m-%d"))
    price = price_df[(bbg_ticker, "PX_LAST")].dropna().tail(LOOKBACK_DAYS)
    price.index = pd.to_datetime(price.index)
except Exception as e:
    print(f"[WARNING] Bloomberg 가격 로드 실패: {e}")
    print("  → short_data CSV의 px_last 컬럼을 대신 사용합니다")
    if short_path.exists() and "px_last" in short_df.columns:
        price = short_df["px_last"].dropna().tail(LOOKBACK_DAYS)
    else:
        price = pd.Series(dtype=float)

# =============================================================================
# 3. 수급 — pykrx에서 투자자별 순매수 가져오기
# =============================================================================
#
# pykrx의 get_market_trading_value_by_date()는 종목 하나의 투자자별 순매수를 반환.
# 컬럼: 기관합계, 기타법인, 개인, 외국인합계 (단위: 원)
#
# 이걸 cumsum() 하면 "해당 기간 동안의 누적 순매수" = 돈의 방향이 보임.
# =============================================================================

try:
    # pykrx auth (이미 init 되어있으면 skip)
    sys.path.insert(0, str(Path.cwd() / "AI" / "kr_disclosure"))
    sys.path.insert(0, str(Path.cwd() / "AI" / "emailer"))
    from krx_auth import init_krx_auth
    from pykrx import stock
    init_krx_auth()

    start_s = (date.today() - timedelta(days=int(LOOKBACK_DAYS * 1.5))).strftime("%Y%m%d")
    end_s = date.today().strftime("%Y%m%d")

    flow = stock.get_market_trading_value_by_date(start_s, end_s, TICKER)
    flow.index = pd.to_datetime(flow.index)
    flow = flow.tail(LOOKBACK_DAYS)

    # 누적 순매수 (0부터 시작)
    foreign_cum = flow["외국인합계"].cumsum() / 1e8   # 억원 단위
    insto_cum = flow["기관합계"].cumsum() / 1e8
    retail_cum = flow["개인"].cumsum() / 1e8

except Exception as e:
    print(f"[WARNING] pykrx 수급 로드 실패: {e}")
    foreign_cum = pd.Series(dtype=float)
    insto_cum = pd.Series(dtype=float)
    retail_cum = pd.Series(dtype=float)

# =============================================================================
# 4. 4-Panel Chart
# =============================================================================

fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True,
                         gridspec_kw={"height_ratios": [3, 1.5, 1.5, 1.5]})
fig.suptitle(f"{TICKER} — Price + Supply/Demand + Short Balance",
             fontsize=14, fontweight="bold")

# ── Panel 1: 주가 ──
if not price.empty:
    axes[0].plot(price.index, price.values, color="steelblue", linewidth=1.2)
    axes[0].fill_between(price.index, price.values, alpha=0.05, color="steelblue")
axes[0].set_ylabel("Price (KRW)")
axes[0].set_title("Stock Price", fontsize=10, loc="left", color="#666")
axes[0].grid(True, alpha=0.15)

# ── Panel 2: 외국인 누적 순매수 ──
if not foreign_cum.empty:
    color = np.where(foreign_cum >= 0, "#2563eb", "#dc2626")
    axes[1].bar(foreign_cum.index, foreign_cum.values, color=color, width=1, alpha=0.7)
    axes[1].axhline(0, color="gray", lw=0.5)
axes[1].set_ylabel("억원")
axes[1].set_title("Foreign Cumulative Net Buy", fontsize=10, loc="left", color="#666")
axes[1].grid(True, alpha=0.15)

# ── Panel 3: 기관 누적 순매수 ──
if not insto_cum.empty:
    color = np.where(insto_cum >= 0, "#7c3aed", "#dc2626")
    axes[2].bar(insto_cum.index, insto_cum.values, color=color, width=1, alpha=0.7)
    axes[2].axhline(0, color="gray", lw=0.5)
axes[2].set_ylabel("억원")
axes[2].set_title("Institutional Cumulative Net Buy", fontsize=10, loc="left", color="#666")
axes[2].grid(True, alpha=0.15)

# ── Panel 4: 공매도 잔고비중 ──
if not bal_pct.empty:
    axes[3].fill_between(bal_pct.index, bal_pct.values, alpha=0.4, color="#ef4444")
    axes[3].plot(bal_pct.index, bal_pct.values, color="#ef4444", linewidth=1)
axes[3].set_ylabel("잔고비중 (%)")
axes[3].set_title("Short Balance Ratio", fontsize=10, loc="left", color="#666")
axes[3].grid(True, alpha=0.15)

# ── 공통 설정 ──
for ax in axes:
    ax.tick_params(axis="x", rotation=30)
    ax.margins(x=0.01)

plt.tight_layout()
plt.savefig(f"{TICKER}_short_chart.png", dpi=150, bbox_inches="tight")
plt.show()
print(f"\nSaved: {TICKER}_short_chart.png")
