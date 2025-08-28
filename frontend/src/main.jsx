import React, {useEffect, useRef, useState} from "react"
import { createRoot } from "react-dom/client"

const API = (path) => `http://localhost:8000${path}`

// ---------- helpers ----------
async function getJSON(url, signal) {
  const res = await fetch(url, {signal})
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

function Spark({series=[]}) {
  if (!series?.length) return <div style={{height:24}}/>
  const w=120,h=24
  const min=Math.min(...series), max=Math.max(...series)
  const norm = v => (h-2) - ( (v-min)/(max-min||1) )*(h-4)
  const pts = series.map((v,i)=> `${(i*(w-4))/(series.length-1||1)+2},${norm(v)}`).join(' ')
  return <svg width={w} height={h}><polyline fill="none" stroke="#5ac8fa" strokeWidth="1.5" points={pts}/></svg>
}

// bigger inline chart for the selected row
function InlineChart({series=[], height=160}) {
  if (!series?.length) return <div style={{height}}/>
  const w = Math.max(series.length*4, 420)
  const h = height
  const min=Math.min(...series), max=Math.max(...series)
  const norm = v => (h-10) - ( (v-min)/(max-min||1) )*(h-20)
  const pts = series.map((v,i)=> `${(i*(w-20))/(series.length-1||1)+10},${norm(v)}`).join(' ')
  return (
    <div style={{overflowX:"auto"}}>
      <svg width={w} height={h}>
        <rect x="0" y="0" width={w} height={h} fill="#101522"/>
        <polyline fill="none" stroke="#4dd2ff" strokeWidth="2" points={pts}/>
      </svg>
    </div>
  )
}

function Section({title, children}) {
  return (
    <div style={{background:"#1e2330", borderRadius:12, padding:16, margin:"16px 0", boxShadow:"0 1px 0 rgba(255,255,255,0.05)"}}>
      <div style={{fontWeight:700, marginBottom:8}}>{title}</div>
      {children}
    </div>
  )
}

// ---------- Market Highlights ----------
function MarketHighlights() {
  const [sectors, setSectors] = useState([])
  const [gainers, setGainers] = useState([])
  const [loading, setLoading] = useState(false)
  const [note, setNote] = useState(null)
  const acRef = useRef()

  const reload = async () => {
    setLoading(true); setNote(null)
    acRef.current?.abort(); acRef.current = new AbortController()
    try {
      const [sec, mov] = await Promise.all([
        getJSON(API("/api/screener/sectors"), acRef.current.signal),
        getJSON(API("/api/screener/top-movers"), acRef.current.signal).catch(()=>({top_gainers:[]})),
      ])
      setSectors(sec?.sectors||[])
      setGainers((mov?.top_gainers||[]).slice(0,8))
      setNote(sec?.note||null)
    } catch(e) {
      setNote("Provider temporarily unavailable. Try again in a minute.")
    } finally { setLoading(false) }
  }

  useEffect(()=>{ reload(); return ()=>acRef.current?.abort() }, [])

  return (
    <Section title="Market Highlights">
      <div style={{display:"flex", gap:16, alignItems:"flex-start"}}>
        <div style={{flex:1}}>
          <div style={{opacity:0.8, marginBottom:6}}>Top sectors & verified top gainers.</div>
          <button onClick={reload} disabled={loading} style={{background:"#27d17f",color:"#000",padding:"4px 8px",borderRadius:6,border:"none",cursor:"pointer"}}>
            {loading?"Loading...":"Reload"}
          </button>
          <div style={{marginTop:12, color:"#b0b7c3"}}>
            {sectors?.length ? (
              <table style={{width:"100%", borderCollapse:"collapse"}}>
                <thead><tr><th style={{textAlign:"left"}}>Sector</th><th style={{textAlign:"right"}}>5d %</th></tr></thead>
                <tbody>
                  {sectors.map((r,i)=>(
                    <tr key={i} style={{borderTop:"1px solid rgba(255,255,255,0.05)"}}>
                      <td style={{padding:"6px 0"}}>{r.sector} <span style={{opacity:0.6}}>({r.symbol})</span></td>
                      <td style={{padding:"6px 0", textAlign:"right", color:r.change_5d>=0?"#27d17f":"#ff7272"}}>{r.change_5d?.toFixed(2)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : <div>No sector data.</div>}
            {note && <div style={{marginTop:6, color:"#ffcc66"}}>Note: {note}</div>}
          </div>
        </div>
        <div style={{width:320}}>
          <div style={{opacity:0.8, marginBottom:6}}>Top gainers (real tickers)</div>
          <div style={{background:"#171b26", borderRadius:8, padding:8}}>
            {gainers?.length ? gainers.map((g,i)=>(
              <div key={i} style={{display:"flex", justifyContent:"space-between", padding:"4px 0", borderBottom:i<gainers.length-1?"1px solid rgba(255,255,255,0.06)":undefined}}>
                <div style={{opacity:0.9}}>{g.ticker}</div>
                <div style={{opacity:0.8}}>${Number(g.price).toFixed(2)}</div>
                <div style={{color:(String(g.change_percentage).includes('-')?"#ff7272":"#27d17f")}}>{String(g.change_percentage)}</div>
              </div>
            )) : <div style={{opacity:0.7}}>No top gainers right now.</div>}
          </div>
        </div>
      </div>
    </Section>
  )
}

// ---------- Quick Screener ----------
function QuickScreener() {
  const [tickers, setTickers] = useState("AAPL,MSFT,NVDA,TSLA,AMZN")
  const [rows, setRows] = useState([])
  const [sel, setSel] = useState(null)
  const [loading, setLoading] = useState(false)
  const [note, setNote] = useState(null)

  const scan = async () => {
    setLoading(true); setNote(null)
    try {
      const data = await getJSON(API(`/api/screener/scan?symbols=${encodeURIComponent(tickers)}`))
      const sorted = (data?.results||[]).slice().sort((a,b)=>b.score-a.score)
      setRows(sorted)
      // auto-select top result so the chart always has something
      setSel(sorted[0] || null)
      setNote(data?.note||null)
    } catch(e) {
      setRows([]); setSel(null)
      setNote("Provider temporarily unavailable. Try again in a minute.")
    } finally { setLoading(false) }
  }

  useEffect(()=>{ scan() },[])

  return (
    <Section title="Quick Screener">
      <div style={{display:"flex", gap:8, alignItems:"center", marginBottom:8}}>
        <div style={{flex:1}}>
          <div style={{opacity:0.7, marginBottom:6}}>Type tickers, run, then click a row to see details.</div>
          <input value={tickers} onChange={e=>setTickers(e.target.value)} placeholder="AAPL,MSFT,..." style={{width:"100%", padding:8, borderRadius:6, border:"1px solid #2b3242", background:"#141824", color:"#dfe6f3"}}/>
        </div>
        <button onClick={scan} disabled={loading} style={{background:"#2f6fed",color:"#fff",padding:"8px 12px",border:"none",borderRadius:6,cursor:"pointer"}}>{loading?"Scanning...":"Scan"}</button>
      </div>

      {note && <div style={{color:"#ffcc66", marginBottom:8}}>Note: {note}</div>}

      <div style={{display:"grid", gridTemplateColumns:"1fr 360px", gap:16}}>
        <div style={{overflowX:"auto"}}>
          <table style={{width:"100%", borderCollapse:"collapse"}}>
            <thead>
              <tr style={{opacity:0.8}}>
                <th style={{textAlign:"left"}}>Symbol</th>
                <th style={{textAlign:"right"}}>Price</th>
                <th style={{textAlign:"right"}}>RSI</th>
                <th style={{textAlign:"right"}}>5d %</th>
                <th style={{textAlign:"right"}}>Score</th>
                <th style={{textAlign:"center"}}>Spark</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r,i)=>(
                <tr
                  key={i}
                  onClick={()=>setSel(r)}
                  style={{
                    borderTop:"1px solid rgba(255,255,255,0.06)",
                    cursor:"pointer",
                    background: sel?.symbol===r.symbol ? "#141a2a" : undefined
                  }}>
                  <td style={{padding:"6px 0"}}>{r.symbol}</td>
                  <td style={{padding:"6px 0", textAlign:"right"}}>${r.price?.toFixed(2)}</td>
                  <td style={{padding:"6px 0", textAlign:"right"}}>{r.rsi?.toFixed(1)}</td>
                  <td style={{padding:"6px 0", textAlign:"right", color:(r.mom_5d>=0?"#27d17f":"#ff7272")}}>{(r.mom_5d*100).toFixed(2)}%</td>
                  <td style={{padding:"6px 0", textAlign:"right"}}>{r.score?.toFixed(2)}</td>
                  <td style={{padding:"6px 0", textAlign:"center"}}><Spark series={r.closes?.slice(-40)}/></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div>
          {sel ? (
            <div style={{background:"#171b26", padding:12, borderRadius:8}}>
              <div style={{fontWeight:700, marginBottom:6}}>{sel.symbol} — last {sel.closes?.length||0} days</div>
              <InlineChart series={sel.closes?.slice(-180)}/>
              <div style={{marginTop:8}}>
                <div>Price: ${sel.price?.toFixed(2)} | RSI(14): {sel.rsi?.toFixed(1)} | EMA(12/26): {sel.ema_short?.toFixed(2)} / {sel.ema_long?.toFixed(2)}</div>
                <div style={{marginTop:6, opacity:0.9}}>{sel.explain}</div>
              </div>
            </div>
          ) : (
            <div style={{opacity:0.8}}>Click a row to see details here.</div>
          )}
        </div>
      </div>
    </Section>
  )
}

// ---------- Options ----------
function OptionsIdea() {
  const [symbol, setSymbol] = useState("AAPL")
  const [bp, setBp] = useState(300)
  const [res, setRes] = useState(null)
  const [loading, setLoading] = useState(false)
  const [note, setNote] = useState(null)

  const getIdea = async () => {
    setLoading(true); setRes(null); setNote(null)
    try {
      const data = await getJSON(API(`/api/options/idea?symbol=${encodeURIComponent(symbol)}&buying_power=${encodeURIComponent(bp)}`))
      setRes(data); if (data?.note) setNote(data.note)
    } catch(e) {
      setNote("Provider temporarily unavailable. Try again in a minute.")
    } finally { setLoading(false) }
  }

  return (
    <Section title="Options — My Ticker">
      <div style={{display:"flex", gap:8, alignItems:"end", marginBottom:8}}>
        <div style={{flex:1}}>
          <div style={{opacity:0.7}}>Symbol</div>
          <input value={symbol} onChange={e=>setSymbol(e.target.value.toUpperCase())} style={{width:"100%", padding:8, borderRadius:6, border:"1px solid #2b3242", background:"#141824", color:"#dfe6f3"}}/>
        </div>
        <div style={{width:180}}>
          <div style={{opacity:0.7}}>Buying power ($)</div>
          <input type="number" value={bp} onChange={e=>setBp(Number(e.target.value||0))} style={{width:"100%", padding:8, borderRadius:6, border:"1px solid #2b3242", background:"#141824", color:"#dfe6f3"}}/>
        </div>
        <button onClick={getIdea} disabled={loading} style={{background:"#27d17f", color:"#000", padding:"10px 14px", border:"none", borderRadius:6, cursor:"pointer"}}>
          {loading?"Getting...":"Get idea"}
        </button>
      </div>
      {note && <div style={{color:"#ffcc66", marginBottom:8}}>Note: {note}</div>}
      {res && res.suggestions?.length>0 ? (
        <div style={{background:"#171b26", padding:12, borderRadius:8}}>
          <div style={{marginBottom:6}}>Underlier ~ ${res.under_price?.toFixed(2)}. We picked up to 3 contracts:</div>
          <table style={{width:"100%", borderCollapse:"collapse"}}>
            <thead><tr><th align="left">Type</th><th align="right">Strike</th><th align="right">Expiry</th><th align="right">Price</th><th align="right">Delta</th><th align="right">Conf.</th><th align="right">Breakeven</th></tr></thead>
            <tbody>
              {res.suggestions.map((c,i)=>(
                <tr key={i} style={{borderTop:"1px solid rgba(255,255,255,0.06)"}}>
                  <td>{c.type}</td>
                  <td align="right">${c.strike?.toFixed(2)}</td>
                  <td align="right">{c.expiry}</td>
                  <td align="right">${c.mid_price?.toFixed(2)}</td>
                  <td align="right">{(c.delta??0).toFixed(2)}</td>
                  <td align="right">{c.conf??0}</td>
                  <td align="right">${c.breakeven?.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{marginTop:8, opacity:0.9}}>{res.explanation}</div>
        </div>
      ) : (
        <div style={{opacity:0.8}}>No suggestion yet.</div>
      )}
    </Section>
  )
}

function App() {
  return (
    <div style={{minHeight:"100vh", background:"#0f1422", color:"#dfe6f3", padding:"20px 24px", fontFamily:"ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto"}}>
      <div style={{fontSize:24, fontWeight:800, marginBottom:8}}>Quant Assistant <span style={{color:"#27d17f", fontSize:14, fontWeight:700}}>● API: OK</span></div>
      <div style={{opacity:0.8, marginBottom:16}}>This is general information only and not financial advice. For personal guidance, please talk to a licensed professional.</div>
      <MarketHighlights/>
      <QuickScreener/>
      <OptionsIdea/>
    </div>
  )
}

createRoot(document.getElementById("root")).render(<App/>)
