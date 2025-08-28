import React, {useEffect, useRef, useState} from "react"
import { createRoot } from "react-dom/client"

const API = (p)=>`http://localhost:8000${p}`

async function getJSON(url, signal){
  const r=await fetch(url,{signal}); if(!r.ok) throw new Error(`${r.status}`); return r.json()
}

const Btn = ({children, onClick, kind="primary", disabled=false, style={}})=>{
  const base={
    border:"none", borderRadius:8, padding:"8px 12px", cursor:"pointer",
    fontWeight:700, letterSpacing:"0.2px"
  }
  const colors = kind==="primary"
    ? {background:"var(--accent2)", color:"#fff"}
    : kind==="ok" ? {background:"var(--ok)", color:"#000"} 
    : {background:"#263046", color:"#dfe6f3"}
  return <button onClick={onClick} disabled={disabled} style={{...base,...colors,opacity:disabled?.8:1,...style}}>{children}</button>
}

const Panel = ({title, children})=>(
  <div style={{background:"var(--panel)",borderRadius:14,padding:16,margin:"16px 0",boxShadow:"0 1px 0 rgba(255,255,255,0.05)"}}>
    <div style={{fontWeight:800,marginBottom:8}}>{title}</div>
    {children}
  </div>
)

function Spark({series=[]}) {
  if (!series?.length) return <div style={{height:24}}/>
  const w=120,h=24
  const min=Math.min(...series), max=Math.max(...series)
  const norm = v => (h-2) - ( (v-min)/(max-min||1) )*(h-4)
  const pts = series.map((v,i)=> `${(i*(w-4))/(series.length-1||1)+2},${norm(v)}`).join(' ')
  return <svg width={w} height={h}><polyline fill="none" stroke="#4dd2ff" strokeWidth="1.6" points={pts}/></svg>
}

function BigLine({series=[],height=160}) {
  if (!series?.length) return <div style={{height}}/>
  const w=Math.max(series.length*4,480), h=height
  const min=Math.min(...series), max=Math.max(...series)
  const norm=v=>(h-10)-((v-min)/(max-min||1))*(h-20)
  const pts=series.map((v,i)=>`${(i*(w-20))/(series.length-1||1)+10},${norm(v)}`).join(' ')
  return <div style={{overflowX:"auto"}}><svg width={w} height={h}>
    <rect x="0" y="0" width={w} height={h} fill="#0e1522"/>
    <polyline fill="none" stroke="#66e2ff" strokeWidth="2" points={pts}/>
  </svg></div>
}

// --------- Market Highlights with Sector → top symbols → detail ----------
function MarketHighlights(){
  const [sectors, setSectors] = useState([])
  const [gainers, setGainers] = useState([])
  const [activeSector, setActiveSector] = useState(null)
  const [sectorSymbols, setSectorSymbols] = useState([])
  const [detail, setDetail] = useState(null)
  const [note, setNote] = useState(null)
  const [loading, setLoading] = useState(false)
  const acRef = useRef()

  const reload = async ()=>{
    setLoading(true); setNote(null); setActiveSector(null); setSectorSymbols([]); setDetail(null)
    acRef.current?.abort(); acRef.current = new AbortController()
    try{
      const [sec, mov] = await Promise.all([
        getJSON(API("/api/screener/sectors"), acRef.current.signal),
        getJSON(API("/api/screener/top-movers"), acRef.current.signal).catch(()=>({top_gainers:[]})),
      ])
      setSectors(sec?.sectors||[])
      setGainers((mov?.top_gainers||[]).slice(0,8))
      setNote(sec?.note||null)
    }catch(e){ setNote("Provider temporarily unavailable. Try again in a minute.") }
    finally{ setLoading(false) }
  }

  useEffect(()=>{ reload(); return ()=>acRef.current?.abort() },[])

  const loadSector = async (sectorSymbol)=>{
    setActiveSector(sectorSymbol); setDetail(null)
    try{
      const data = await getJSON(API(`/api/screener/sector/top?sector_symbol=${encodeURIComponent(sectorSymbol)}&limit=8`))
      setSectorSymbols(data?.symbols||[])
    }catch{ setSectorSymbols([]) }
  }

  const loadDetail = async (sym)=>{
    try{
      const d = await getJSON(API(`/api/screener/stock_summary?symbol=${encodeURIComponent(sym)}`))
      setDetail(d?.summary||null)
    }catch{ setDetail(null) }
  }

  return (
    <Panel title="Market Highlights">
      <div style={{display:"grid", gridTemplateColumns:"1fr 360px", gap:16}}>
        <div>
          <div style={{display:"flex", alignItems:"center", gap:10, marginBottom:8}}>
            <Btn kind="ok" onClick={reload} disabled={loading} style={{padding:"4px 10px"}}>{loading?"Loading…":"Reload"}</Btn>
            <span style={{color:"var(--muted)"}}>Top sectors & verified top gainers.</span>
          </div>

          {/* Sector list (clickable) */}
          <table style={{width:"100%", borderCollapse:"collapse"}}>
            <thead><tr><th style={{textAlign:"left"}}>Sector</th><th style={{textAlign:"right"}}>5d %</th></tr></thead>
            <tbody>
              {(sectors||[]).map((r,i)=>(
                <tr key={i}
                    onClick={()=>loadSector(r.symbol)}
                    style={{borderTop:"1px solid var(--border)", cursor:"pointer",
                            background: activeSector===r.symbol ? "#111b2b" : undefined}}>
                  <td style={{padding:"8px 0"}}>{r.sector} <span style={{opacity:.6}}>({r.symbol})</span></td>
                  <td style={{padding:"8px 0", textAlign:"right", color:r.change_5d>=0?"var(--ok)":"var(--danger)"}}>{r.change_5d.toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>

          {note && <div style={{marginTop:8, color:"#ffcc66"}}>Note: {note}</div>}

          {/* If a sector is selected, show its top symbols */}
          {activeSector && (
            <div style={{marginTop:12, padding:12, background:"#141d2e", borderRadius:10}}>
              <div style={{fontWeight:700, marginBottom:6}}>Top symbols in {activeSector}</div>
              {(sectorSymbols||[]).map((s,i)=>(
                <div key={i} onClick={()=>loadDetail(s.symbol)} style={{
                  display:"grid", gridTemplateColumns:"100px 1fr 80px 80px", gap:8, padding:"6px 0",
                  borderTop: i? "1px solid var(--border)" : "none", cursor:"pointer"
                }}>
                  <div>{s.symbol}</div>
                  <div><Spark series={s.closes?.slice(-40)}/></div>
                  <div style={{textAlign:"right"}}>${s.price?.toFixed(2)}</div>
                  <div style={{textAlign:"right"}}>{s.score?.toFixed(2)}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right column: global gainers, or stock detail if selected */}
        <div>
          {!detail ? (
            <div style={{background:"#141d2e", borderRadius:10, padding:12}}>
              <div style={{opacity:0.8, marginBottom:6}}>Top gainers (real tickers)</div>
              {(gainers||[]).length ? (gainers||[]).map((g,i)=>(
                <div key={i} style={{display:"flex", justifyContent:"space-between", padding:"6px 0",
                  borderBottom:i<(gainers.length-1)?"1px solid var(--border)":undefined}}>
                  <div style={{opacity:0.9}}>{g.ticker}</div>
                  <div style={{opacity:0.8}}>${Number(g.price).toFixed(2)}</div>
                  <div style={{color:String(g.change_percentage).includes('-')?"var(--danger)":"var(--ok)"}}>
                    {String(g.change_percentage)}
                  </div>
                </div>
              )) : <div style={{opacity:0.7}}>No top gainers right now.</div>}
            </div>
          ) : (
            <div style={{background:"#141d2e", borderRadius:10, padding:12}}>
              <div style={{fontWeight:700, marginBottom:6}}>{detail.symbol} — stock summary</div>
              <BigLine series={detail.closes?.slice(-180)}/>
              <div style={{marginTop:8}}>
                <div>Price: ${detail.price?.toFixed(2)} | RSI(14): {detail.rsi?.toFixed(1)} | EMA(12/26): {detail.ema_short?.toFixed(2)} / {detail.ema_long?.toFixed(2)}</div>
                <div>20-day probability up: {detail.prob_up_20d!=null ? `${(detail.prob_up_20d*100).toFixed(0)}%` : "—"}</div>
                <div style={{marginTop:6, opacity:0.9}}>{detail.explain}</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </Panel>
  )
}

// --------- Quick Screener (unchanged behavior, styled) ----------
function QuickScreener(){
  const [tickers,setTickers]=useState("AAPL,MSFT,NVDA,TSLA,AMZN")
  const [rows,setRows]=useState([]),[sel,setSel]=useState(null)
  const [note,setNote]=useState(null),[loading,setLoading]=useState(false)
  const scan=async()=>{
    setLoading(true); setNote(null)
    try{
      const d=await getJSON(API(`/api/screener/scan?symbols=${encodeURIComponent(tickers)}`))
      const sorted=(d?.results||[]).slice().sort((a,b)=>b.score-a.score)
      setRows(sorted); setSel(sorted[0]||null); setNote(d?.note||null)
    }catch{ setRows([]); setSel(null); setNote("Provider temporarily unavailable.") }
    finally{ setLoading(false) }
  }
  useEffect(()=>{ scan() },[])
  return (
    <Panel title="Quick Screener">
      <div style={{display:"flex",gap:8,alignItems:"center",marginBottom:8}}>
        <input value={tickers} onChange={e=>setTickers(e.target.value)} style={{flex:1,padding:8,borderRadius:8,border:"1px solid var(--border)",background:"#0f1524",color:"var(--text)"}}/>
        <Btn onClick={scan} disabled={loading}>{loading?"Scanning…":"Scan"}</Btn>
      </div>
      {note && <div style={{color:"#ffcc66",marginBottom:8}}>Note: {note}</div>}
      <div style={{display:"grid",gridTemplateColumns:"1fr 360px",gap:16}}>
        <div style={{overflowX:"auto"}}>
          <table style={{width:"100%",borderCollapse:"collapse"}}>
            <thead><tr>
              <th style={{textAlign:"left"}}>Symbol</th><th style={{textAlign:"right"}}>Price</th>
              <th style={{textAlign:"right"}}>RSI</th><th style={{textAlign:"right"}}>5d %</th>
              <th style={{textAlign:"right"}}>Score</th><th style={{textAlign:"center"}}>Spark</th>
            </tr></thead>
            <tbody>
              {rows.map((r,i)=>(
                <tr key={i} onClick={()=>setSel(r)}
                    style={{borderTop:"1px solid var(--border)",cursor:"pointer",background: sel?.symbol===r.symbol?"#101a2b":undefined}}>
                  <td>{r.symbol}</td>
                  <td style={{textAlign:"right"}}>${r.price?.toFixed(2)}</td>
                  <td style={{textAlign:"right"}}>{r.rsi?.toFixed(1)}</td>
                  <td style={{textAlign:"right",color:(r.mom_5d>=0?"var(--ok)":"var(--danger)")}}>{(r.mom_5d*100).toFixed(2)}%</td>
                  <td style={{textAlign:"right"}}>{r.score?.toFixed(2)}</td>
                  <td style={{textAlign:"center"}}><Spark series={r.closes?.slice(-40)}/></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div>
          {sel ? (
            <div style={{background:"#141d2e",borderRadius:10,padding:12}}>
              <div style={{fontWeight:700,marginBottom:6}}>{sel.symbol} — last {sel.closes?.length||0} days</div>
              <BigLine series={sel.closes?.slice(-180)}/>
              <div style={{marginTop:8}}>
                <div>Price: ${sel.price?.toFixed(2)} | RSI(14): {sel.rsi?.toFixed(1)} | EMA(12/26): {sel.ema_short?.toFixed(2)} / {sel.ema_long?.toFixed(2)}</div>
                <div style={{marginTop:6,opacity:0.9}}>{sel.explain}</div>
              </div>
            </div>
          ) : <div style={{opacity:.8}}>Click a row to see details.</div>}
        </div>
      </div>
    </Panel>
  )
}

// --------- Options ----------
function OptionsIdea(){
  const [symbol,setSymbol]=useState("AAPL")
  const [bp,setBp]=useState(300)
  const [res,setRes]=useState(null), [loading,setLoading]=useState(false), [note,setNote]=useState(null)
  const go=async ()=>{
    setLoading(true); setRes(null); setNote(null)
    try{
      const d=await getJSON(API(`/api/options/idea?symbol=${encodeURIComponent(symbol)}&buying_power=${encodeURIComponent(bp)}`))
      setRes(d); if(d?.note) setNote(d.note)
    }catch{ setNote("Provider temporarily unavailable. Try again in a minute.") }
    finally{ setLoading(false) }
  }
  return (
    <Panel title="Options — My Ticker">
      <div style={{display:"flex",gap:8,alignItems:"end",marginBottom:8}}>
        <div style={{flex:1}}>
          <div style={{opacity:.7}}>Symbol</div>
          <input value={symbol} onChange={e=>setSymbol(e.target.value.toUpperCase())}
                 style={{width:"100%",padding:8,borderRadius:8,border:"1px solid var(--border)",background:"#0f1524",color:"var(--text)"}}/>
        </div>
        <div style={{width:180}}>
          <div style={{opacity:.7}}>Buying power ($)</div>
          <input type="number" value={bp} onChange={e=>setBp(Number(e.target.value||0))}
                 style={{width:"100%",padding:8,borderRadius:8,border:"1px solid var(--border)",background:"#0f1524",color:"var(--text)"}}/>
        </div>
        <Btn kind="ok" onClick={go} disabled={loading}>{loading?"Getting…":"Get idea"}</Btn>
      </div>
      {note && <div style={{color:"#ffcc66",marginBottom:8}}>Note: {note}</div>}
      {res && res.suggestions?.length>0 ? (
        <div style={{background:"#141d2e",padding:12,borderRadius:10}}>
          <div>Underlier ~ ${res.under_price?.toFixed(2)}. We picked up to 3 contracts:</div>
          <table style={{width:"100%",borderCollapse:"collapse",marginTop:8}}>
            <thead><tr><th align="left">Type</th><th align="right">Strike</th><th align="right">Expiry</th><th align="right">Price</th><th align="right">Delta</th><th align="right">Conf.</th><th align="right">Breakeven</th></tr></thead>
            <tbody>{res.suggestions.map((c,i)=>(
              <tr key={i} style={{borderTop:"1px solid var(--border)"}}>
                <td>{c.type}</td><td align="right">${c.strike?.toFixed(2)}</td>
                <td align="right">{c.expiry}</td><td align="right">${c.mid_price?.toFixed(2)}</td>
                <td align="right">{(c.delta??0).toFixed(2)}</td><td align="right">{c.conf??0}</td>
                <td align="right">${c.breakeven?.toFixed(2)}</td>
              </tr>
            ))}</tbody>
          </table>
          {res?.sim?.prob_profit!=null && <div style={{marginTop:8}}>Probability of profit (sim): {(res.sim.prob_profit*100).toFixed(0)}%</div>}
          <div style={{marginTop:8,opacity:.9}}>{res.explanation}</div>
        </div>
      ) : <div style={{opacity:.8}}>No suggestion yet.</div>}
    </Panel>
  )
}

function App(){
  return (
    <div style={{minHeight:"100vh",padding:"20px 24px"}}>
      <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:8}}>
        <div style={{fontSize:24,fontWeight:800}}>Quant Assistant</div>
        <div style={{background:"rgba(39,209,127,0.2)",color:"var(--ok)",border:"1px solid rgba(39,209,127,0.5)",padding:"2px 8px",borderRadius:999,fontWeight:700,fontSize:12}}>API: OK</div>
      </div>
      <div style={{opacity:.8,marginBottom:16}}>This is general information only and not financial advice. For personal guidance, please talk to a licensed professional.</div>
      <MarketHighlights/>
      <QuickScreener/>
      <OptionsIdea/>
    </div>
  )
}

createRoot(document.getElementById("root")).render(<App/>)
