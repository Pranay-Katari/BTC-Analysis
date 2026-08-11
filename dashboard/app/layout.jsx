import "./globals.css";
import "./overlay.css";

export const metadata = {
  title: "BTC Live Market Lab",
  description: "Live Kalshi BTC benchmark candles, contract data, and real-time market analytics",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
