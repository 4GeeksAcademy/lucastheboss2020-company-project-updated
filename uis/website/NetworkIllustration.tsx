/** Original schematic of TrackFlow's two locations; not live shipment data. */
export default function NetworkIllustration() {
  return <div className="tf-network-art">
    <div className="tf-art-heading"><span className="tf-eyebrow">Our operations footprint</span><span className="tf-art-chip">US + Spain</span></div>
    <svg className="tf-network-svg" viewBox="0 0 540 350" role="img" aria-labelledby="tf-network-title tf-network-desc">
      <title id="tf-network-title">TrackFlow operations in Los Angeles and Zaragoza</title><desc id="tf-network-desc">A schematic connecting our United States and Spain locations, with a warehouse illustration below.</desc>
      <defs><pattern id="tf-grid" width="26" height="26" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="#bed2d5" /></pattern><linearGradient id="tf-roof" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#82beb3" /><stop offset="1" stopColor="#429a8e" /></linearGradient></defs>
      <rect width="540" height="350" fill="url(#tf-grid)" />
      <path d="m58 62 42-21 34 7 18-14 28 13 15 32-16 18-12 28-21 8-2 29-21 3-15-28-24-11-8-34-23-8ZM156 178l31-8 24 18 5 28-17 34-12 41-18-18-4-40-17-24ZM347 62l21-16 24 8 17-9 25 11-1 23-28 13-7 25-24 6-21-23-18-9ZM366 134l30-8 36 19 9 33-21 26-13 35-22-2-15-39-16-28Z" fill="#dbe8e5" stroke="#c2d8d2" strokeWidth="1.5" />
      <path d="M111 113C180 10 307 8 391 79" fill="none" stroke="#087f74" strokeWidth="2.5" strokeDasharray="6 7" />
      <circle cx="111" cy="113" r="15" fill="#087f74" fillOpacity=".12" /><circle cx="111" cy="113" r="6" fill="#087f74" stroke="white" strokeWidth="3" /><circle cx="391" cy="79" r="15" fill="#087f74" fillOpacity=".12" /><circle cx="391" cy="79" r="6" fill="#087f74" stroke="white" strokeWidth="3" />
      <rect x="35" y="140" width="154" height="49" rx="10" fill="white" stroke="#d7e3e5" /><text x="49" y="161" fill="#163c52" fontSize="13" fontWeight="700">Los Angeles</text><text x="49" y="177" fill="#526574" fontSize="10">United States · Warehouse</text><rect x="339" y="105" width="167" height="49" rx="10" fill="white" stroke="#d7e3e5" /><text x="353" y="126" fill="#163c52" fontSize="13" fontWeight="700">Zaragoza</text><text x="353" y="142" fill="#526574" fontSize="10">Spain · Warehouse</text>
      <ellipse cx="300" cy="304" rx="148" ry="27" fill="#c9dcda" fillOpacity=".48" /><path d="m197 223 110-48 108 51-108 49Z" fill="url(#tf-roof)" /><path d="m197 223 110 52v49l-110-53Z" fill="#f8fbfa" stroke="#c4d9d5" /><path d="m307 275 108-49v49l-108 49Z" fill="#e0ece9" stroke="#c4d9d5" /><path d="m219 245 22 10v35l-22-10ZM257 263l23 11v35l-23-11Z" fill="#163c52" /><path d="m328 280 21-9v25l-21 10ZM365 263l21-10v25l-21 10Z" fill="#7aa99f" /><path d="m243 203 107 51M269 192l108 50" stroke="#afd2c9" strokeWidth="2" />
      <path d="m144 279 24-11 25 12-24 12Z" fill="#f1d8aa" /><path d="m144 279 25 13v25l-25-13Z" fill="#dcc08e" /><path d="m169 292 24-12v25l-24 12Z" fill="#c8a875" /><path d="m418 292 19-9 19 10-19 9Z" fill="#f1d8aa" /><path d="m418 292 19 10v20l-19-10Z" fill="#dcc08e" /><path d="m437 302 19-9v20l-19 9Z" fill="#c8a875" />
    </svg><div className="tf-art-caption"><span className="tf-art-caption-dot" /><span>Two markets. One logistics partner.</span></div>
  </div>;
}
