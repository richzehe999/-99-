"""
News/catalyst parser for enhanced hot stock skill.

This module is intentionally provider-agnostic. It can read local CSV news,
RSS-normalized CSV, or any dataframe with date/title/summary/keywords columns.

Educational/research use only. Not financial advice.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Dict, List, Optional
import re
import pandas as pd


@dataclass
class CatalystHit:
    theme: str
    keyword: str
    title: str
    source: str
    date: str
    score: float


def _safe_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def load_local_news(csv_path: str | Path) -> pd.DataFrame:
    path = Path(csv_path)
    if not path.exists():
        return pd.DataFrame(columns=["date", "title", "source", "summary", "keywords"])
    df = pd.read_csv(path)
    for col in ["date", "title", "source", "summary", "keywords"]:
        if col not in df.columns:
            df[col] = ""
    return df


def parse_theme_hits(news_df: pd.DataFrame, themes: List[dict], lookback_days: int = 7) -> pd.DataFrame:
    if news_df.empty:
        return pd.DataFrame(columns=["theme", "keyword", "title", "source", "date", "score"])

    df = news_df.copy()
    df["date_dt"] = pd.to_datetime(df["date"], errors="coerce")
    cutoff = pd.Timestamp(datetime.now().date() - timedelta(days=lookback_days))
    df = df[(df["date_dt"].isna()) | (df["date_dt"] >= cutoff)]

    hits: List[dict] = []
    for _, row in df.iterrows():
        blob = " ".join([_safe_text(row.get("title")), _safe_text(row.get("summary")), _safe_text(row.get("keywords"))])
        for theme in themes:
            theme_name = theme.get("name", "未知主题")
            for kw in theme.get("keywords", []):
                if not kw:
                    continue
                count = len(re.findall(re.escape(str(kw)), blob, flags=re.IGNORECASE))
                if count:
                    # Title hits are weighted higher because they usually represent stronger market attention.
                    title_bonus = 1.5 if re.search(re.escape(str(kw)), _safe_text(row.get("title")), flags=re.IGNORECASE) else 1.0
                    hits.append({
                        "theme": theme_name,
                        "keyword": kw,
                        "title": _safe_text(row.get("title")),
                        "source": _safe_text(row.get("source")),
                        "date": _safe_text(row.get("date")),
                        "score": float(count * title_bonus),
                    })

    return pd.DataFrame(hits)


def theme_catalyst_strength(hits_df: pd.DataFrame) -> pd.DataFrame:
    if hits_df.empty:
        return pd.DataFrame(columns=["theme", "catalyst_score", "hit_count", "top_keywords", "top_titles"])

    grouped = []
    for theme, g in hits_df.groupby("theme"):
        score = float(g["score"].sum())
        hit_count = int(len(g))
        top_keywords = ",".join(g["keyword"].value_counts().head(5).index.astype(str).tolist())
        top_titles = " | ".join(g["title"].drop_duplicates().head(3).astype(str).tolist())
        grouped.append({
            "theme": theme,
            "catalyst_score": score,
            "hit_count": hit_count,
            "top_keywords": top_keywords,
            "top_titles": top_titles,
        })

    out = pd.DataFrame(grouped).sort_values("catalyst_score", ascending=False).reset_index(drop=True)
    max_score = out["catalyst_score"].max()
    out["catalyst_score_norm"] = (out["catalyst_score"] / max_score * 100).round(2) if max_score else 0
    return out
