"use client";

import { memo, useEffect, useRef } from "react";

export const CandleChart = memo(function CandleChart({ candles, target }) {
  const canvas = useRef(null);
  const actual = candles.at(-1)?.close;
  const difference = actual !== undefined && target ? ((actual - target) / target) * 100 : undefined;

  useEffect(() => {
    const node = canvas.current;
    if (!node) return;
    const draw = () => {
      const rect = node.getBoundingClientRect();
      const ratio = window.devicePixelRatio || 1;
      node.width = Math.round(rect.width * ratio);
      node.height = Math.round(rect.height * ratio);
      const context = node.getContext("2d");
      if (!context) return;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.clearRect(0, 0, rect.width, rect.height);
      const pad = { top: 24, right: 80, bottom: 24, left: 18 };
      const width = rect.width - pad.left - pad.right;
      const height = rect.height - pad.top - pad.bottom;
      const values = candles.flatMap(candle => [candle.high, candle.low]);
      if (target) values.push(target);
      if (!values.length) return;
      const rawLow = Math.min(...values), rawHigh = Math.max(...values);
      const naturalRange = Math.max(rawHigh - rawLow, Math.abs(rawHigh) * .00015, 1);
      const low = rawLow - naturalRange * .12, high = rawHigh + naturalRange * .12;
      const yFor = (value) => pad.top + height - ((value-low)/(high-low))*height;

      context.strokeStyle = "#252b28"; context.lineWidth = 1;
      [high,(high+low)/2,low].forEach(value=>{
        const y=yFor(value); context.beginPath(); context.moveTo(pad.left,y); context.lineTo(rect.width-pad.right,y); context.stroke();
        context.fillStyle="#737d78"; context.font="10px ui-monospace, monospace"; context.textAlign="left"; context.fillText(`$${value.toLocaleString(undefined,{maximumFractionDigits:2})}`,rect.width-pad.right+9,y+4);
      });
      if(target){const y=yFor(target);context.setLineDash([6,5]);context.strokeStyle="#ff5d78";context.beginPath();context.moveTo(pad.left,y);context.lineTo(rect.width-pad.right,y);context.stroke();context.setLineDash([]);context.fillStyle="#ff5d78";context.font="800 9px ui-monospace, monospace";context.fillText("TARGET",rect.width-pad.right+9,y-6)}

      const step=width/Math.max(candles.length,1), bodyWidth=Math.max(2,Math.min(9,step*.62));
      const points=[];
      candles.forEach((candle,index)=>{
        const x=pad.left+step*index+step/2, up=candle.close>=candle.open;
        context.globalAlpha=.78;context.strokeStyle=up?"#21e6a4":"#ff5d78";context.fillStyle=context.strokeStyle;context.lineWidth=1.2;
        context.beginPath();context.moveTo(x,yFor(candle.high));context.lineTo(x,yFor(candle.low));context.stroke();
        const top=yFor(Math.max(candle.open,candle.close)), body=Math.max(1.5,Math.abs(yFor(candle.open)-yFor(candle.close)));
        context.fillRect(x-bodyWidth/2,top,bodyWidth,body);points.push({x,y:yFor(candle.close)});
      });
      context.globalAlpha=1;
      if(points.length){
        const trace=(color,lineWidth)=>{context.beginPath();context.strokeStyle=color;context.lineWidth=lineWidth;context.lineCap="round";context.lineJoin="round";context.moveTo(points[0].x,points[0].y);for(let index=1;index<points.length;index++){const previous=points[index-1],before=points[index-2]??previous,point=points[index],after=points[index+1]??point;context.bezierCurveTo(previous.x+(point.x-before.x)/6,previous.y+(point.y-before.y)/6,point.x-(after.x-previous.x)/6,point.y-(after.y-previous.y)/6,point.x,point.y)}context.stroke()};
        context.globalAlpha=.18;trace("#72a7ff",7);context.globalAlpha=1;trace("#d8e8ff",2);
        const last=points.at(-1);context.fillStyle="#fff";context.strokeStyle="#72a7ff";context.lineWidth=2;context.beginPath();context.arc(last.x,last.y,3.8,0,Math.PI*2);context.fill();context.stroke();
      }
    };
    draw();
    const observer=new ResizeObserver(draw);observer.observe(node);return()=>observer.disconnect();
  },[candles,target]);

  return <div className="candle-shell">
    <div className="candle-legend"><span><i className="candle-key"/>OHLC</span><span><i className="line-key"/>BRTI</span></div>
    {actual !== undefined && target && difference !== undefined && <div className="chart-margin"><span>ACTUAL VS TARGET</span><strong className={difference>=0?"positive":"negative"}>{difference>=0?"+":""}{difference.toFixed(4)}%</strong><em>${actual.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})} − ${target.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}</em></div>}
    <canvas ref={canvas} className="candle-canvas" aria-label="Live Kalshi BRTI candlestick chart"/>
    {!candles.length&&<div className="chart-wait">Waiting for Kalshi BRTI ticks…</div>}
  </div>;
});
