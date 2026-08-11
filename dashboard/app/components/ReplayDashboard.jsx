"use client";

import { useEffect, useState } from "react";
import { CandleChart } from "./CandleChart";
import { LineChart } from "./LineChart";
import { RollingTrace } from "./RollingTrace";

const API = process.env.NEXT_PUBLIC_LIVE_API ?? "http://localhost:8000";
const WS = process.env.NEXT_PUBLIC_LIVE_WS ?? "ws://localhost:8000/ws";
const blankSource = { status: "connecting", age_ms: null };
const empty = { mode:"live", market:{}, latest:null, history:[], candles:[], sources:{kalshi_benchmark:blankSource,coinbase:blankSource,kalshi_ws:blankSource,kalshi_rest:blankSource}, errors:[] };
const CONTRACT_SERIES = [{key:"yes_price",color:"#21e6a4",label:"YES"},{key:"no_price",color:"#ff5d78",label:"NO"}];
const fmt = (value, digits=2) => value.toLocaleString(undefined,{minimumFractionDigits:digits,maximumFractionDigits:digits});
const signed = (value, digits=3) => `${value>=0?"+":""}${value.toFixed(digits)}`;

export function ReplayDashboard() {
  const [state,setState] = useState(empty);
  const [spotTrace,setSpotTrace] = useState([]);
  const [coinbaseTrace,setCoinbaseTrace] = useState([]);
  const [connected,setConnected] = useState(false);
  useEffect(()=>{
    fetch(`${API}/api/state`).then(r=>r.json()).then(setState).catch(()=>undefined);
    let socket; let retry; let frame; let stopped=false;
    let pendingSpot;
    const flushSpot=()=>{
      frame=undefined;
      const spot=pendingSpot; pendingSpot=undefined;
      if(!spot)return;
      setSpotTrace(current=>[...current,{at:spot.timestamp_ms,price:spot.price}].slice(-300));
      setState(current=>{
        const candles=[...current.candles];
        if(candles.at(-1)?.time===spot.candle.time)candles[candles.length-1]=spot.candle;
        else candles.push(spot.candle);
        const target=current.market.target_price??0;
        const latest=current.latest?{...current.latest,btc_price:spot.price,margin_pct:target?((spot.price-target)/target)*100:0}:null;
        return {...current,latest,candles:candles.slice(-240)};
      });
    };
    const connect=()=>{
      socket=new WebSocket(WS);
      socket.onopen=()=>setConnected(true);
      socket.onclose=()=>{setConnected(false);if(!stopped)retry=window.setTimeout(connect,1200)};
      socket.onmessage=(event)=>{
        const message=JSON.parse(event.data);
        if(message.type==="snapshot"||message.type==="status") setState(message.data);
        if(message.type==="spot"){
          pendingSpot=message;
          if(frame===undefined)frame=requestAnimationFrame(flushSpot);
        }
        if(message.type==="coinbase")setCoinbaseTrace(current=>[...current,{at:message.timestamp_ms,price:message.price}].slice(-300));
        if(message.type==="quote")setState(current=>{
          if(!current.latest)return current;
          const yes=(message.yes_bid_c+message.yes_ask_c)/2;
          return {...current,latest:{...current.latest,yes_bid_c:message.yes_bid_c,yes_ask_c:message.yes_ask_c,yes_price:yes,no_price:100-yes,spread_cents:message.yes_ask_c-message.yes_bid_c,volume:message.volume}};
        });
        if(message.type==="tick")setState(current=>({...current,market:message.market,sources:message.sources,errors:message.errors,latest:message.data,history:[...current.history,message.data].slice(-900)}));
      };
    }; connect(); return()=>{stopped=true;clearTimeout(retry);if(frame!==undefined)cancelAnimationFrame(frame);socket?.close()};
  },[]);

  const p=state.latest;
  const consensus=p?(p.yes_price>=50?"YES":"NO"):"—";
  const consensusPrice=p?Math.max(p.yes_price,p.no_price):0;
  const coinbasePrice=coinbaseTrace.at(-1)?.price;
  const venueBasis=p&&coinbasePrice!==undefined?p.btc_price-coinbasePrice:undefined;

  return <main>
    <nav><div className="brand"><i/>MARKET<span>LAB</span></div><div className="nav-links"><b>Markets</b><span>Analytics</span><span>System</span></div><div className={`connection ${connected?"live":"offline"}`}><i/>{connected?"DASHBOARD LIVE":"BACKEND OFFLINE"}</div></nav>
    <header><div><p className="eyebrow">BTC / 15 MIN · LIVE MARKET INTELLIGENCE</p><h1>Bitcoin above the opening price?</h1><p className="subtitle">{state.market.ticker||"Discovering active KXBTC15M market…"}</p></div><WindowClock closeTs={state.market.close_ts}/></header>

    <section className="ticker-strip">
      <Quote label="BTC REFERENCE" value={p?`$${fmt(p.btc_price)}`:"—"} detail={p?`${signed(p.margin_pct)}% vs target`:"Kalshi BRTI"} tone={(p?.margin_pct??0)>=0?"up":"down"}/>
      <Quote label="CONSENSUS" value={p?`${consensus} ${fmt(consensusPrice,1)}¢`:"—"} detail={p?`YES ${fmt(p.yes_price,1)}¢ · NO ${fmt(p.no_price,1)}¢`:"Kalshi ticker"} tone="up"/>
      <Quote label="TO BEAT" value={p?`$${fmt(p.target_price)}`:"—"} detail={state.market.title||"REST market metadata"}/>
      <Quote label="MARKET VOLUME" value={p?fmt(p.volume,0):"—"} detail={p?`${fmt(p.spread_cents,1)}¢ spread`:"Waiting for quote"}/>
    </section>

    <section className="comparison-panel panel">
      <div className="comparison-head"><div><span>DUAL-VENUE BTC MONITOR</span><h2>Kalshi BRTI vs Coinbase BTC-USD</h2><p>Frame-interpolated 30-second comparison · raw market values remain authoritative</p></div><b><i/>BOTH FEEDS LIVE</b></div>
      <div className="comparison-body">
        <div className="comparison-stats">
          <div><span>KALSHI BRTI</span><strong>{p?`$${fmt(p.btc_price)}`:"—"}</strong><em>{state.sources.kalshi_benchmark.age_ms==null?"waiting":`${state.sources.kalshi_benchmark.age_ms}ms feed age`}</em></div>
          <div><span>COINBASE BTC-USD</span><strong>{coinbasePrice!==undefined?`$${fmt(coinbasePrice)}`:"—"}</strong><em>{state.sources.coinbase.age_ms==null?"waiting":`${state.sources.coinbase.age_ms}ms feed age`}</em></div>
          <div><span>VENUE BASIS</span><strong className={(venueBasis??0)>=0?"positive":"negative"}>{venueBasis===undefined?"—":`${signed(venueBasis,2)} USD`}</strong><em>Kalshi reference minus Coinbase</em></div>
        </div>
        <RollingTrace points={spotTrace} comparisonPoints={coinbaseTrace}/>
      </div>
    </section>

    <section className="workspace">
      <div className="primary-column">
        <article className="panel btc-panel"><PanelTitle eyebrow="UNDERLYING MARKET" title="Kalshi BRTI · 5 second candles" badge="KALSHI WS"/><CandleChart candles={state.candles} target={p?.target_price}/><div className="chart-footer"><span>OPEN {state.candles.length?`$${fmt(state.candles[0].open)}`:"—"}</span><span>HIGH {state.candles.length?`$${fmt(Math.max(...state.candles.map(c=>c.high)))}`:"—"}</span><span>LOW {state.candles.length?`$${fmt(Math.min(...state.candles.map(c=>c.low)))}`:"—"}</span><span>{state.candles.length} CANDLES</span></div></article>
        <article className="panel"><PanelTitle eyebrow="PREDICTION MARKET" title="Live executable contract price" badge="KALSHI WS"/><LineChart points={state.history} series={CONTRACT_SERIES}/></article>
      </div>
      <aside>
        <article className="panel analytics"><PanelTitle eyebrow="LIVE ANALYTICS" title="Real-time market state" badge={p?.regime??"WARMING UP"}/>
          <Metric label="BTC velocity" value={p?`${signed(p.btc_velocity)} $/s`:"—"}/><Metric label="BTC acceleration" value={p?`${signed(p.btc_acceleration)} $/s²`:"—"}/><Metric label="Contract velocity" value={p?`${signed(p.contract_velocity)} ¢/s`:"—"}/><Metric label="Contract acceleration" value={p?`${signed(p.contract_acceleration)} ¢/s²`:"—"}/><Metric label="Volatility" value={p?`${fmt(p.volatility_bps,3)} bps`:"—"}/><Metric label="BTC target margin" value={p?`${signed(p.margin_pct)}%`:"—"} accent/>
        </article>
        <article className="panel feeds"><PanelTitle eyebrow="DATA PLANE" title="Feed health"/><Feed name="Kalshi BTC benchmark" source={state.sources.kalshi_benchmark}/><Feed name="Coinbase comparison" source={state.sources.coinbase}/><Feed name="Kalshi ticker stream" source={state.sources.kalshi_ws}/><Feed name="Kalshi market REST" source={state.sources.kalshi_rest}/>{Object.values(state.sources).some(source=>source.status!=="live")&&state.errors.slice(-1).map(error=><p className="feed-error" key={error}>{error}</p>)}</article>
      </aside>
    </section>
    <footer>Live monitoring only · Real-time analytics · Python feed orchestration · No order execution</footer>
  </main>;
}

function Quote({label,value,detail,tone}){return <div className="quote"><span>{label}</span><strong className={tone}>{value}</strong><em>{detail}</em></div>}
function PanelTitle({eyebrow,title,badge}){return <div className="panel-title"><div><span>{eyebrow}</span><h2>{title}</h2></div>{badge&&<b>{badge}</b>}</div>}
function Metric({label,value,accent=false}){return <div className="metric"><span>{label}</span><strong className={accent?"accent":""}>{value}</strong></div>}
function Feed({name,source}){const live=source.status==="live";return <div className="feed"><i className={live?"live":""}/><div><strong>{name}</strong><span>{source.status.toUpperCase()}</span></div><em>{source.age_ms==null?"—":source.age_ms<1000?`${source.age_ms}ms`:`${(source.age_ms/1000).toFixed(1)}s`}</em></div>}
function WindowClock({closeTs}){
  const [now,setNow]=useState(Date.now());
  useEffect(()=>{const timer=setInterval(()=>setNow(Date.now()),250);return()=>clearInterval(timer)},[]);
  const remaining=Math.max(0,Math.floor(((closeTs??0)*1000-now)/1000));
  const clock=`${String(Math.floor(remaining/60)).padStart(2,"0")}:${String(remaining%60).padStart(2,"0")}`;
  return <div className="window"><span>WINDOW CLOSE</span><strong>{clock}</strong><em>{remaining?"LIVE":"ROLLOVER"}</em></div>;
}
