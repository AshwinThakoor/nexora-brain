CATEGORY_KEYWORDS = {
    "risk_management": ["risk management","stop loss","position size","drawdown","risk reward","account equity","daily loss"],
    "candlesticks": ["candlestick","engulfing","doji","hammer","shooting star","morning star","evening star"],
    "chart_patterns": ["bear flag","bull flag","head and shoulders","triangle","double top","double bottom","wedge"],
    "strategies": ["strategy","trend following","mean reversion","breakout","scalping","momentum"],
    "market_psychology": ["psychology","fear","greed","discipline","revenge trading","fomo"],
    "market_behavior": ["market regime","volatility","liquidity","market structure","trend","range"],
}
def classify_text(text: str) -> str:
    lowered = text.lower()
    scores = {category: sum(lowered.count(k) for k in keys) for category, keys in CATEGORY_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"
