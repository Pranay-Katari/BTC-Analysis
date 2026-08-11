"use client";

import { memo, useEffect, useRef } from "react";

export const LineChart=memo(function LineChart({points,series,target}){
  const canvas=useRef(null);
  useEffect(()=>{
    const node=canvas.current;if(!node)return;
    const draw=()=>{
      const rect=node.getBoundingClientRect(),ratio=window.devicePixelRatio||1;node.width=Math.round(rect.width*ratio);node.height=Math.round(rect.height*ratio);
      const context=node.getContext("2d");if(!context)return;context.setTransform(ratio,0,0,ratio,0,0);context.clearRect(0,0,rect.width,rect.height);
      const pad={top:10,right:10,bottom:16,left:10},width=rect.width-pad.left-pad.right,height=rect.height-pad.top-pad.bottom;
      context.strokeStyle="#252b28";context.lineWidth=1;for(let row=0;row<=3;row++){const y=pad.top+height*row/3;context.beginPath();context.moveTo(pad.left,y);context.lineTo(rect.width-pad.right,y);context.stroke()}
      const values=points.flatMap(point=>series.map(item=>Number(point[item.key])).filter(Number.isFinite));if(target!==undefined)values.push(target);if(values.length<2)return;
      const rawLow=Math.min(...values),rawHigh=Math.max(...values),range=Math.max(rawHigh-rawLow,1),low=rawLow-range*.12,high=rawHigh+range*.12;
      const yFor=(value)=>pad.top+height-((value-low)/(high-low))*height;
      series.forEach(item=>{context.beginPath();context.strokeStyle=item.color;context.lineWidth=2;context.lineJoin="round";context.lineCap="round";points.forEach((point,index)=>{const value=Number(point[item.key]);if(!Number.isFinite(value))return;const x=pad.left+(points.length===1?width:width*index/(points.length-1));if(index)context.lineTo(x,yFor(value));else context.moveTo(x,yFor(value))});context.stroke()});
    };draw();const observer=new ResizeObserver(draw);observer.observe(node);return()=>observer.disconnect();
  },[points,series,target]);
  return <div className="chart-shell"><div className="legend">{series.map(item=><span key={String(item.key)}><i style={{background:item.color}}/>{item.label}</span>)}</div><canvas ref={canvas} className="line-canvas" aria-label="Live Kalshi contract chart"/></div>;
});
