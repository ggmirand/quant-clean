import React from 'react'
export default function Glossary(){
  return (
    <div className="panel">
      <h3>Glossary</h3>
      <div className="help">
        <b>Delta</b>: how much an option moves for a $1 change in the stock.<br/>
        <b>Breakeven</b>: stock price where the option breaks even at expiry.<br/>
        <b>IV</b>: implied volatility—higher IV means pricier options.<br/>
        This is educational only and not financial advice.
      </div>
    </div>
  )
}
