import React from 'react'

export default function PayoffChart({s0, type, strike, premium}){
  if(!(s0>0 && strike>0)) return <div className="help">No payoff chart</div>
  const xs = [], ys = []
  const lo = Math.max(0, s0*0.5), hi = s0*1.5
  for(let S=lo; S<=hi; S+= (hi-lo)/120){
    let y = 0
    if (type === 'CALL'){
      y = Math.max(S - strike, 0) - premium
    } else {
      y = Math.max(strike - S, 0) - premium
    }
    xs.push(S); ys.push(y)
  }
  const pts = xs.map((x,i)=> `${((x-lo)/(hi-lo))*100},${50-ys[i]}`)
  return <svg viewBox="0 0 100 100" style={{width:'100%', height:220, background:'#0b1220', border:'1px solid #1f2937', borderRadius:8}}>
    <polyline fill="none" stroke="#22d3ee" strokeWidth="1.6" points={pts.join(' ')} />
    <text x="4" y="10" fill="#9aa4af" fontSize="4">Payoff vs price</text>
  </svg>
}
