import React, {useEffect, useMemo, useState} from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'
import { SectorBar, GainersBar, Histogram } from './charts.jsx'
import PriceVolume from './PriceVolume.jsx'
import PayoffChart from './PayoffChart.jsx'
import Glossary from './Glossary.jsx'

const API = "http://localhost:8000"
const Panel = ({title, children, desc}) => (
  <section className="panel"><h3>{title}</h3>{desc && <div className="help">{desc}</div>}{children}</section>
)

function Table({rows, columns, caption, onRowClick}){
  if (!rows?.length) return <div className="help">No rows.</div>
  return (
    <div className="table-wrap">
      <table>
        {caption && <caption className="help" style={{textAlign:'left', marginBottom:6}}>{caption}</caption>}
        <thead><tr>{columns.map(c=><th key={c.key}>{c.label}</th>)}</tr></thead>
        <tbody>
          {rows.map((r,i)=><tr key={i} onClick={onRowClick?()=>onRowClick(r):undefined} style={{cursor:onRowClick?'pointer':'default'}}>
            {columns.map(c=><td key={c.key}>{c.render? c.render(r[c.key], r): r[c.key]}</td>)}
          </tr>)}
        </tbody>
      </table>
    </div>
  )
}

function SuggestionCard({sug}){
  if (!sug) return null
  const c=sug.suggestion||sug
  return (
    <div className="card" style={{flex:'1 1 360px', minWidth:300}}>
      <div style={{fontWeight:600}}>{sug.symbol || 'Idea'}</div>
      {sug.under_price>0 && <div className="help">Underlying: <b>${sug.under_price.toFixed(2)}</b></div>}
      <div className="help">Type: <b>{c.type}</b> &nbsp; Exp: <b>{c.expiry}</b> &nbsp; Strike: <b>${Number(c.strike).toFixed(2)}</b></div>
      <div className="help">Premium: <b>${Number(c.mid_price).toFixed(2)}</b> &nbsp; Δ: <b>{(Number(c.delta)??0).toFixed(2)}</b> &nbsp; Breakeven: <b>${Number(c.breakeven).toFixed(2)}</b></div>
      {"conf" in sug && <div className="help">Confidence: <b>{sug.confidence || sug.conf || 0}</b> / 100</div>}
      {sug.explanation && <div className="help" style={{marginTop:6}}><b>Plain-English:</b> {sug.explanation}</div>}
      <div className="row" style={{marginTop:8}}>
        <div style={{flex:'1 1 420px', minWidth:260}}>
          <div className="help" style={{marginBottom:6}}>Payoff at expiry (1x)</div>
          <PayoffChart s0={sug.under_price||0} type={String(c.type).toUpperCase()} strike={Number(c.strike)} premium={Number(c.mid_price||0)} />
        </div>
        <div style={{flex:'1 1 420px', minWidth:260}}>
          <div className="help" style={{marginBottom:6}}>Simulated P/L (samples)</div>
          {sug.sim?.pl_p50!==undefined
            ? <Histogram values={[sug.sim.pl_p5, sug.sim.pl_p50, sug.sim.pl_p95]} bins={3} color="#60a5fa"/>
            : <div className="help">No simulation</div>}
        </div>
      </div>
    </div>
  )
}

function App(){
  const [apiOk,setApiOk]=useState(null)
  useEffect(()=>{ fetch(API+"/health").then(r=>r.json()).then(()=>setApiOk(true)).catch(()=>setApiOk(false)) },[])

  // Market highlights
  const [sectors,setSectors]=useState(null)
  const [gainers,setGainers]=useState(null)
  const loadHighlights=async()=>{
    try{
      const a = await fetch(API+"/api/market/sectors"); const ja=await a.json()
      const b = await fetch(API+"/api/market/top-gainers"); const jb=await b.json()
      setSectors(ja); setGainers(jb)
    }catch(e){ setSectors({note:String(e)}); setGainers({top_gainers:[]}) }
  }
  useEffect(()=>{ loadHighlights() },[])
  const topSectors = useMemo(()=>{
    const m = sectors?.["Rank A: Real-Time Performance"] || {}
    return Object.entries(m).map(([sector,v])=>({sector, change: parseFloat(String(v).replace('%',''))}))
      .filter(x=>isFinite(x.change)).sort((a,b)=>b.change-a.change).slice(0,8)
  },[sectors])

  // Screener
  const [tickers,setTickers]=useState("AAPL,MSFT,NVDA,TSLA,AMZN")
  const [scan,setScan]=useState(null)
  const runScan=async()=>{
    const u=new URL(API+"/api/screener/scan")
    u.searchParams.set("symbols", tickers)
    u.searchParams.set("include_history", "1")
    u.searchParams.set("history_days", "180")
    const r=await fetch(u); setScan(await r.json())
  }
  useEffect(()=>{ runScan() },[])
  const cols=[
    {key:'symbol', label:'Symbol'},
    {key:'price', label:'Price', render:v=>Number(v).toFixed(2)},
    {key:'rsi', label:'RSI', render:v=>Number(v).toFixed(1)},
    {key:'mom_5d', label:'5d %', render:v=> (Number(v)*100).toFixed(1)+'%'},
    {key:'ema_short', label:'EMA(12)', render:v=>Number(v).toFixed(2)},
    {key:'ema_long', label:'EMA(26)', render:v=>Number(v).toFixed(2)},
  ]
  const rows = useMemo(()=> (scan?.results||[]), [scan])

  // Options: my ticker
  const [sym,setSym]=useState("AAPL"), [bp,setBP]=useState(3000), [idea,setIdea]=useState(null), [note,setNote]=useState(null)
  const getIdea=async()=>{
    setNote(null); setIdea(null)
    try{
      const u=new URL(API+"/api/options/idea"); u.searchParams.set("symbol",sym); u.searchParams.set("buying_power", String(bp))
      const r=await fetch(u); const j=await r.json(); setIdea(j)
      if(j.note) setNote(j.note)
    }catch(e){ setNote(String(e)) }
  }

  // Options: market ideas
  const [mIdeas,setMIdeas]=useState(null)
  const runMIdeas=async()=>{
    const u=new URL(API+"/api/options/market-ideas")
    u.searchParams.set("buying_power", String(bp)); u.searchParams.set("limit","3")
    const r=await fetch(u); setMIdeas(await r.json())
  }
  useEffect(()=>{ runMIdeas() },[])

  return (
    <div className="container">
      <header className="header">
        <h2 style={{margin:0}}>Quant Assistant</h2>
        <span className="badge"><span className={`dot ${apiOk? 'ok': (apiOk===false?'err':'')}`} /> API: {apiOk==null?'…':(apiOk?'OK':'down')}</span>
      </header>
      <div className="help">This is general information only and not financial advice. For personal guidance, please talk to a licensed professional.</div>

      <Panel title="Market Highlights" desc="Top sectors & verified top gainers.">
        <div className="row">
          <div style={{flex:'1 1 420px', minWidth:320}}>
            <div className="help" style={{marginBottom:6, display:'flex', gap:8, alignItems:'center'}}>
              <span>Sector performance</span>
              <button className="button" onClick={loadHighlights}>Reload</button>
            </div>
            <SectorBar rows={topSectors}/>
            {!topSectors.length && <div className="help">{sectors?.note || 'No sector data.'}</div>}
          </div>
          <div style={{flex:'1 1 420px', minWidth:320}}>
            <div className="help" style={{marginBottom:6}}>Top gainers (real tickers)</div>
            <GainersBar rows={(gainers?.top_gainers||[]).slice(0,8)}/>
          </div>
        </div>
      </Panel>

      <Panel title="Quick Screener" desc="Type tickers, run, then click a row to see details.">
        <form className="row" onSubmit={(e)=>{e.preventDefault();runScan()}}>
          <div className="input" style={{flex:'1 1 520px'}}><label>Tickers</label><input value={tickers} onChange={e=>setTickers(e.target.value)} /></div>
          <div className="input"><label>&nbsp;</label><button className="button" type="submit">Scan</button></div>
        </form>
        {scan?.note && <div className="help" style={{color:'var(--danger)'}}>{scan.note}</div>}
        <Table rows={rows} columns={cols} caption="Ranked by composite score" />
        {rows[0] && (
          <div className="row" style={{marginTop:10}}>
            <div style={{flex:'1 1 560px', minWidth:320}}>
              <div className="help">{rows[0].symbol} — last {rows[0].closes?.length||0} days</div>
              <PriceVolume closes={rows[0].closes||[]} volumes={rows[0].volumes||[]} />
            </div>
          </div>
        )}
      </Panel>

      <Panel title="Options — My Ticker" desc="We pick 1–3 contracts with Δ≈0.30 and near-month expiry, filter by affordability.">
        <form className="row" onSubmit={(e)=>{e.preventDefault();getIdea()}}>
          <div className="input"><label>Symbol</label><input value={sym} onChange={e=>setSym(e.target.value.toUpperCase())}/></div>
          <div className="input"><label>Buying power ($)</label><input type="number" min="0" value={bp} onChange={e=>setBP(+e.target.value)}/></div>
          <div className="input"><label>&nbsp;</label><button className="button" type="submit">Get idea</button></div>
        </form>
        {note && <div className="help" style={{color:'var(--danger)'}}>{note}</div>}
        {idea?.suggestions?.length
          ? <div className="row">{idea.suggestions.map((s,i)=><SuggestionCard key={i} sug={{...idea, suggestion:s}} />)}</div>
          : <div className="help">No suggestion yet.</div>}
      </Panel>

      <Panel title="Options — Market Ideas" desc="Scans a watchlist and shows the top suggestions by confidence.">
        <div className="help" style={{marginBottom:6}}>Uses your buying power: ${bp}</div>
        {(mIdeas?.ideas||[]).length
          ? <div className="row">{mIdeas.ideas.map((s,i)=><SuggestionCard key={i} sug={s} />)}</div>
          : <div className="help">No market ideas yet.</div>}
      </Panel>

      <Glossary/>
      <footer className="help" style={{marginTop:14}}>
        This is general information only and not financial advice. For personal guidance, please talk to a licensed professional.
      </footer>
    </div>
  )
}

createRoot(document.getElementById('root')).render(<App/>)
