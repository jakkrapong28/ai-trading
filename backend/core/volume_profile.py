import pandas as pd
import numpy as np
from typing import Dict, Any

def calculate_volume_profile(df: pd.DataFrame, num_bins: int = 50) -> Dict[str, Any]:
    """
    Calculate Volume Profile metrics: Point of Control (POC), Value Area High (VAH),
    Value Area Low (VAL), Volume Weighted Average Price (VWAP), and Delta Volume.
    """
    # Standardize column naming if tick data passes 'price' and 'volume' or 'tick_volume'
    prices = df['price'] if 'price' in df else df.get('close', pd.Series([]))
    volumes = df['volume'] if 'volume' in df else df.get('tick_volume', pd.Series([1.0]*len(prices)))
    
    if prices.empty:
        return {"poc": 0.0, "vah": 0.0, "val": 0.0, "vwap": 0.0, "delta_volume": 0.0}

    # Calculate VWAP
    cum_vol = volumes.sum()
    if cum_vol <= 0:
        cum_vol = len(volumes)
        volumes = pd.Series([1.0]*len(prices))
        
    vwap = (prices * volumes).sum() / cum_vol

    min_p, max_p = prices.min(), prices.max()
    if min_p == max_p:
        return {
            "poc": float(min_p),
            "vah": float(min_p),
            "val": float(min_p),
            "vwap": float(vwap),
            "delta_volume": 0.0
        }

    # Bins
    bins = np.linspace(min_p, max_p, num_bins + 1)
    bin_volumes = np.zeros(num_bins)
    bin_delta = np.zeros(num_bins)

    price_diff = prices.diff().fillna(0)
    for i in range(len(prices)):
        p = prices.iloc[i]
        v = volumes.iloc[i]
        diff = price_diff.iloc[i]

        b_idx = np.digitize(p, bins) - 1
        b_idx = min(max(b_idx, 0), num_bins - 1)
        bin_volumes[b_idx] += v
        if diff >= 0:
            bin_delta[b_idx] += v
        else:
            bin_delta[b_idx] -= v

    # POC
    poc_idx = np.argmax(bin_volumes)
    poc = float((bins[poc_idx] + bins[poc_idx + 1]) / 2.0)

    # Value Area (70% of total volume centered around POC)
    target_vol = cum_vol * 0.70
    current_vol = bin_volumes[poc_idx]
    lower_idx = poc_idx
    upper_idx = poc_idx

    while current_vol < target_vol:
        left_vol = bin_volumes[lower_idx - 1] if lower_idx > 0 else 0
        right_vol = bin_volumes[upper_idx + 1] if upper_idx < num_bins - 1 else 0

        if left_vol == 0 and right_vol == 0:
            break

        if left_vol >= right_vol:
            lower_idx -= 1
            current_vol += left_vol
        else:
            upper_idx += 1
            current_vol += right_vol

    val = float(bins[lower_idx])
    vah = float(bins[upper_idx + 1])
    delta_volume = float(bin_delta.sum())

    return {
        "poc": poc,
        "vah": vah,
        "val": val,
        "vwap": float(vwap),
        "delta_volume": delta_volume
    }
