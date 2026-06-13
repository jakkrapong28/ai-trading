// --- TradingView Chart Widget ---
const TradingViewWidget = ({ symbol }: { symbol: string }) => {
  const getTradingViewSymbol = (sym: string) => {
    if (sym === "XAUUSD") return "OANDA:XAUUSD";
    if (sym === "EURUSD") return "FX:EURUSD";
    if (sym === "TSLA") return "NASDAQ:TSLA";
    if (sym === "AAPL") return "NASDAQ:AAPL";
    if (sym === "NVDA") return "NASDAQ:NVDA";
    if (sym === "MSFT") return "NASDAQ:MSFT";
    if (sym === "AMZN") return "NASDAQ:AMZN";
    if (sym.endsWith("USDT")) return `BINANCE:${sym}`;
    return `BINANCE:${sym}`;
  };

  const tvSymbol = getTradingViewSymbol(symbol);

  return (
    <div className="w-full h-full bg-[#0c0d14]">
      <iframe
        key={tvSymbol}
        id="tradingview-widget"
        src={`https://s.tradingview.com/widgetembed/?frameElementId=tradingview-widget&symbol=${tvSymbol}&interval=5&hidesidetoolbar=1&symboledit=0&saveimage=1&toolbarbg=131722&studies=%5B%5D&theme=dark&style=1&timezone=Asia%2FBangkok&studies_overrides=%7B%7D&overrides=%7B%7D&enabled_features=%5B%5D&disabled_features=%5B%5D&locale=th`}
        style={{ width: "100%", height: "100%", border: "none" }}
        allowFullScreen
      />
    </div>
  );
};

export default TradingViewWidget;
