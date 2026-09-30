"""Reading RFT data and group configurations."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .interpret import GroupConfig

# Alternative column names accepted on input -> standard names used internally
COLUMN_ALIASES: Dict[str, str] = {
    "Well_Name": "Well",
    "Depth_TVDSS_ft": "Depth_TVDSS",
    "Pressure_Formation_psia": "P_res",
    "Mobility_mD_cP": "Mobility",
    "Temperature_degF": "Temp",
}
REQUIRED = ["Well", "Depth_TVDSS", "P_res"]
NUMERIC = ["Depth_MD", "Depth_TVDSS", "P_res", "Mobility", "Temp"]


def load_data(csv_path, column_aliases: Optional[Dict[str, str]] = None) -> pd.DataFrame:
    """
    Load an RFT CSV. Expected columns (units):
        Well, Depth_MD (ft, optional), Depth_TVDSS (ft), P_res (psia),
        Mobility (mD/cP, optional), Temp (degF, optional)
    Rows without Depth_TVDSS or P_res (e.g. tight tests) are dropped.
    """
    df = pd.read_csv(csv_path)
    aliases = {**COLUMN_ALIASES, **(column_aliases or {})}
    df = df.rename(columns={k: v for k, v in aliases.items() if k in df.columns})

    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required column(s): {missing}")

    for col in NUMERIC:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["Well"] = df["Well"].astype(str)
    return df.dropna(subset=["Depth_TVDSS", "P_res"])


def load_groups(json_path) -> List[GroupConfig]:
    """
    Load group configurations from JSON:
        {"groups": [{"name": ..., "wells": [...], "oil_grad": ..., "wat_grad": ...,
                     "rmse_limit": ..., "min_points": ..., "segment_penalty": ...}]}
    """
    spec = json.loads(Path(json_path).read_text())
    return [GroupConfig(**g) for g in spec["groups"]]
