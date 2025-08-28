import React from 'react'

export default function PriceVolume({closes=[], volumes=[]}){
  if(!closes?.length) return <div className="help">No history.</div>
  const maxC = Math.max(...closes), minC = Math.min(...closes)
  const w=420, h=180
  const pts = closes.map((c,i)=> `${(i/(closes.length-1))*w},${h-( (c-minC)/(maxC-minC+1e-9) )*h}`)
  return <svg viewBox={`0 0 ${w} ${h}`} style={{width:'100%', height:h, background:'#0b1220', border:'1px solid #1f2937', borderRadius:8}}>
    <polyline fill="none" stroke="#2dd4bf" strokeWidth="2" points={pts.join(' ')} />
  </svg>
}
