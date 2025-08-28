import React from 'react'
import { Bar } from 'react-chartjs-2'
import { Chart, CategoryScale, LinearScale, BarElement, Tooltip, Legend } from 'chart.js'
Chart.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend)

const baseOpts = {
  responsive:true,
  plugins:{ legend:{display:false}, tooltip:{mode:'index', intersect:false} },
  scales:{ x:{ grid:{display:false} }, y:{ grid:{color:'rgba(148,163,184,0.15)'} } }
}

export function SectorBar({rows=[], onBarClick}){
  const data = {
    labels: rows.map(r=>r.sector),
    datasets: [{ label:'% chg', data: rows.map(r=>r.change), backgroundColor:'#22d3ee' }]
  }
  return <div style={{minHeight:250}}>
    <Bar data={data} options={{...baseOpts, onClick:(e,els)=>{ if(!els?.length) return; const i=els[0].index; onBarClick && onBarClick(rows[i]) }}}/>
  </div>
}

export function GainersBar({rows=[]}){
  const labels = rows.map(x=>x.ticker)
  const vals   = rows.map(x=>parseFloat(String(x.change_percentage||x.change).replace('%','')))
  const data = { labels, datasets:[{label:'gainers', data: vals, backgroundColor:'#60a5fa'}] }
  return <div className="card"><Bar data={data} options={baseOpts}/></div>
}

export function Histogram({values=[], bins=20, color='#60a5fa', title='Histogram'}){
  if (!values.length) return <div className="help">No data</div>
  const min = Math.min(...values), max = Math.max(...values), step=(max-min||1)/bins
  const counts = Array.from({length:bins}, ()=>0)
  values.forEach(v => { const idx = Math.min(bins-1, Math.max(0, Math.floor((v-min)/step))); counts[idx]++ })
  const labels = counts.map((_,i)=> (min + i*step).toFixed(0))
  const data = { labels, datasets:[{label:title, data:counts, backgroundColor:color}] }
  return <Bar data={data} options={baseOpts}/>
}
