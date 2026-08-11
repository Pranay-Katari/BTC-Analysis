"use client";

import { memo, useEffect, useRef } from "react";

export const RollingTrace = memo(function RollingTrace({ points, comparisonPoints, windowMs = 30_000 }) {
  const canvas = useRef(null);
  const displayedPrice = useRef(null);
  const displayedComparison = useRef(null);

  useEffect(() => {
    const node = canvas.current;
    if (!node) return;
    let width = 0, height = 0, ratio = 1, frame = 0;
    const targetPrice = points.at(-1)?.price ?? displayedPrice.current;
    const transitionFrom = displayedPrice.current ?? targetPrice;
    const comparisonTarget = comparisonPoints.at(-1)?.price ?? displayedComparison.current;
    const comparisonFrom = displayedComparison.current ?? comparisonTarget;
    const transitionStarted = performance.now();
    const transitionDuration = 340;
    const resize = () => {
      const rect = node.getBoundingClientRect();
      ratio = window.devicePixelRatio || 1;
      width = rect.width; height = rect.height;
      node.width = Math.round(width * ratio); node.height = Math.round(height * ratio);
    };
    const draw = () => {
      const context = node.getContext("2d");
      if (!context || !width || !height) { frame = requestAnimationFrame(draw); return; }
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.clearRect(0, 0, width, height);
      const now = Date.now(), highResolutionNow = performance.now(), pad = { top: 10, right: 14, bottom: 18, left: 14 };
      const visible = points.filter(point => point.at >= now - windowMs);
      const comparisonVisible = comparisonPoints.filter(point => point.at >= now - windowMs);
      const progress = Math.min(1, Math.max(0, (highResolutionNow - transitionStarted) / transitionDuration));
      const eased = 1 - Math.pow(1 - progress, 3);
      const visualPrice = targetPrice == null ? null : (transitionFrom ?? targetPrice) + (targetPrice - (transitionFrom ?? targetPrice)) * eased;
      displayedPrice.current = visualPrice;
      const comparisonVisual = comparisonTarget == null ? null : (comparisonFrom ?? comparisonTarget) + (comparisonTarget - (comparisonFrom ?? comparisonTarget)) * eased;
      displayedComparison.current = comparisonVisual;
      const values = [...visible.map(point => point.price), ...comparisonVisible.map(point=>point.price), ...(visualPrice == null ? [] : [visualPrice]), ...(comparisonVisual == null ? [] : [comparisonVisual])];
      const rawLow = values.length ? Math.min(...values) : 0, rawHigh = values.length ? Math.max(...values) : 1;
      const range = Math.max(rawHigh - rawLow, Math.abs(rawHigh) * .000025, .5);
      const low = rawLow - range * .25, high = rawHigh + range * .25;
      const xFor = (at) => pad.left + ((at - (now - windowMs)) / windowMs) * (width - pad.left - pad.right);
      const yFor = (price) => pad.top + (high - price) / (high - low) * (height - pad.top - pad.bottom);

      context.strokeStyle = "#202723"; context.lineWidth = 1;
      for (let row = 0; row < 3; row += 1) { const y = pad.top + row * (height-pad.top-pad.bottom)/2; context.beginPath(); context.moveTo(pad.left,y); context.lineTo(width-pad.right,y); context.stroke(); }
      const drawTrace=(trace,visual,rawColor,lineColor,pulseColor)=>{
        if(!trace.length||visual==null)return;
        context.beginPath();context.strokeStyle=rawColor;context.lineWidth=1;trace.forEach((point,index)=>{const x=xFor(point.at),y=yFor(point.price);if(index)context.lineTo(x,y);else context.moveTo(x,y)});context.stroke();
        let filtered=trace[0].price;const smooth=trace.map((point,index)=>{filtered=index===0?point.price:filtered+(point.price-filtered)*.42;return{at:point.at,price:filtered}});smooth.push({at:now,price:visual});
        context.beginPath();context.strokeStyle=lineColor;context.lineWidth=2.1;context.lineJoin="round";context.lineCap="round";smooth.forEach((point,index)=>{const x=xFor(point.at),y=yFor(point.price);if(index===0){context.moveTo(x,y);return}const previous=smooth[index-1],midX=(xFor(previous.at)+x)/2;context.quadraticCurveTo(xFor(previous.at),yFor(previous.price),midX,(yFor(previous.price)+y)/2);if(index===smooth.length-1)context.quadraticCurveTo(midX,(yFor(previous.price)+y)/2,x,y)});context.stroke();
        const genuine=trace.at(-1);context.fillStyle=pulseColor;context.beginPath();context.arc(xFor(genuine.at),yFor(genuine.price),2.2,0,Math.PI*2);context.fill();
        const x=xFor(now),y=yFor(visual),pulse=3.5+Math.sin(highResolutionNow/160)*1.1;context.fillStyle=lineColor;context.beginPath();context.arc(x,y,2.3,0,Math.PI*2);context.fill();context.strokeStyle=pulseColor+"88";context.lineWidth=2;context.beginPath();context.arc(x,y,pulse,0,Math.PI*2);context.stroke();
      };
      drawTrace(comparisonVisible,comparisonVisual,"#34516a","#5b8cff","#5b8cff");
      drawTrace(visible,visualPrice,"#4d5b56","#d8e8ff","#21e6a4");
      context.fillStyle="#66706b";context.font="9px ui-monospace, monospace";context.textAlign="left";context.fillText("−30s",pad.left,height-4);context.textAlign="right";context.fillText("NOW",width-pad.right,height-4);
      frame = requestAnimationFrame(draw);
    };
    const observer = new ResizeObserver(resize); observer.observe(node); resize(); frame=requestAnimationFrame(draw);
    return () => { cancelAnimationFrame(frame); observer.disconnect(); };
  }, [comparisonPoints, points, windowMs]);

  return <div className="rolling-wrap"><div className="rolling-legend"><span className="brti-line">KALSHI BRTI</span><span className="coinbase-line">COINBASE</span></div><canvas ref={canvas} className="rolling-canvas" aria-label="Smoothed rolling Kalshi BRTI and Coinbase BTC trace"/></div>;
});
