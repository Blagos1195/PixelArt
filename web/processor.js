const PRESETS={
balanced:{detail:80,variation:22,background:64,grid:false},
photo:{detail:120,variation:18,background:64,grid:false},
illustration:{detail:100,variation:22,background:64,grid:false},
"pixel-art":{detail:80,variation:24,background:64,grid:false},
"grid-drawing":{detail:100,variation:22,background:96,grid:true},
"line-art":{detail:110,variation:18,background:64,grid:false}
};
const dist=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1],a[2]-b[2]);
function borderColour(data,w,h){
 const bins=new Map(),add=i=>{const a=data[i+3];if(!a)return;const k=[data[i]>>3,data[i+1]>>3,data[i+2]>>3].join(","),v=bins.get(k)||[0,0,0,0];v[0]++;v[1]+=data[i];v[2]+=data[i+1];v[3]+=data[i+2];bins.set(k,v)};
 for(let x=0;x<w;x++){add(x*4);add(((h-1)*w+x)*4)}
 for(let y=1;y<h-1;y++){add(y*w*4);add((y*w+w-1)*4)}
 let best=null;for(const v of bins.values())if(!best||v[0]>best[0])best=v;
 return best?[Math.round(best[1]/best[0]),Math.round(best[2]/best[0]),Math.round(best[3]/best[0])]:null;
}
function medianGrid(data,w,h){
 const copy=data.slice(),at=(x,y,c)=>data[(Math.max(0,Math.min(h-1,y))*w+Math.max(0,Math.min(w-1,x)))*4+c];
 for(let y=0;y<h;y++)for(let x=0;x<w;x++){const i=(y*w+x)*4;for(let c=0;c<3;c++){const a=[];for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++)a.push(at(x+dx,y+dy,c));a.sort((a,b)=>a-b);copy[i+c]=a[4]}}
 return copy;
}
function buildPalette(histogram,count){
 const entries=Array.from(histogram.values());
 if(!entries.length)return [];
 const range=box=>{const bounds=[0,1,2].map(c=>[Infinity,-Infinity]);for(const e of box)for(let c=0;c<3;c++){bounds[c][0]=Math.min(bounds[c][0],e.bin[c]);bounds[c][1]=Math.max(bounds[c][1],e.bin[c])}return bounds.map(v=>v[1]-v[0])};
 const boxes=[entries];
 while(boxes.length<count){
  let selected=-1,priority=-1,channel=0;
  for(let i=0;i<boxes.length;i++){
   const box=boxes[i];if(box.length<2)continue;
   const ranges=range(box),axis=ranges.indexOf(Math.max(...ranges));
   const score=ranges[axis]*box.reduce((n,e)=>n+e.count,0);
   if(score>priority){priority=score;selected=i;channel=axis}
  }
  if(selected<0)break;
  const box=boxes.splice(selected,1)[0].slice().sort((a,b)=>a.bin[channel]-b.bin[channel]);
  const half=box.reduce((n,e)=>n+e.count,0)/2;
  let total=0,cut=0;
  for(;cut<box.length-1;cut++){total+=box[cut].count;if(total>=half){cut++;break}}
  boxes.push(box.slice(0,cut),box.slice(cut));
 }
 return boxes.map(box=>{
  const totals=[0,0,0],weight=box.reduce((n,e)=>n+e.count,0);
  for(const e of box)for(let c=0;c<3;c++)totals[c]+=e.sum[c];
  return totals.map(v=>Math.round(v/weight));
 });
}
function nearestPaletteColor(color,palette){
 let best=palette[0],bestDistance=Infinity;
 for(const candidate of palette){const d=dist(color,candidate);if(d<bestDistance){bestDistance=d;best=candidate}}
 return best;
}
function paletteRms(histogram,palette){
 let error=0,total=0;
 for(const e of histogram.values()){
  const source=e.sum.map(v=>v/e.count),mapped=nearestPaletteColor(source,palette);
  error+=(e.squares[0]-2*mapped[0]*e.sum[0]+e.count*mapped[0]**2+e.squares[1]-2*mapped[1]*e.sum[1]+e.count*mapped[1]**2+e.squares[2]-2*mapped[2]*e.sum[2]+e.count*mapped[2]**2)/3;
  total+=e.count;
 }
 return total?Math.sqrt(error/total):0;
}
function processImage(source,opts){
 const preset=PRESETS[opts.preset]||PRESETS.balanced,detail=opts.detail||preset.detail;
 let w=source.width,h=source.height,data=source.data.slice();
 if(Math.max(w,h)>512){const scale=512/Math.max(w,h),nw=Math.max(1,Math.round(w*scale)),nh=Math.max(1,Math.round(h*scale)),canvas=new OffscreenCanvas(nw,nh),ctx=canvas.getContext("2d");const temp=new OffscreenCanvas(w,h);temp.getContext("2d").putImageData(new ImageData(data,w,h),0,0);ctx.imageSmoothingEnabled=true;ctx.drawImage(temp,0,0,nw,nh);data=ctx.getImageData(0,0,nw,nh).data.slice();w=nw;h=nh}
 const bg=borderColour(data,w,h),bgThreshold=preset.grid||opts.grid?Math.max(preset.background,96):preset.background;
 if(bg)for(let i=0;i<data.length;i+=4)if(data[i+3]&&dist([data[i],data[i+1],data[i+2]],bg)<=bgThreshold){data[i]=bg[0];data[i+1]=bg[1];data[i+2]=bg[2]}
 if(preset.grid||opts.grid)data=medianGrid(data,w,h);
 const gray=new Uint8Array(w*h);
 for(let i=0;i<w*h;i++){const p=i*4;gray[i]=.2126*data[p]+.7152*data[p+1]+.0722*data[p+2]}
 const edgeAt=(x,y)=>{const l=gray[y*w+Math.max(0,x-1)],r=gray[y*w+Math.min(w-1,x+1)],u=gray[Math.max(0,y-1)*w+x],d=gray[Math.min(h-1,y+1)*w+x];return Math.abs(r-l)+Math.abs(d-u)};
 const base=Math.max(w,h)/detail,maxBlock=base*1.75,blocks=[];
 function region(l,t,r,b){
  let n=0,s=[0,0,0],sq=[0,0,0],bins=new Map(),edge=0,alpha=0;
  const step=Math.max(1,Math.floor(Math.sqrt((r-l)*(b-t)/1600)));
  for(let y=t;y<b;y+=step)for(let x=l;x<r;x+=step){const i=(y*w+x)*4,a=data[i+3];if(!a)continue;n++;alpha+=a;for(let c=0;c<3;c++){s[c]+=data[i+c];sq[c]+=data[i+c]*data[i+c]}const k=[data[i]>>3,data[i+1]>>3,data[i+2]>>3].join(","),v=bins.get(k)||[0,0,0,0];v[0]++;v[1]+=data[i];v[2]+=data[i+1];v[3]+=data[i+2];bins.set(k,v);edge+=edgeAt(x,y)}
  if(!n){blocks.push([l,t,r,b,[0,0,0,0]]);return}
  const std=Math.sqrt(sq.reduce((a,v,c)=>a+v/n-(s[c]/n)**2,0)/3),edgeMean=edge/n;
  let dominant=null;for(const v of bins.values())if(!dominant||v[0]>dominant[0])dominant=v;
  const fraction=dominant[0]/n,weight=edgeMean>6&&fraction<.9?1:Math.min(.9,.35+.5*(1-fraction)+Math.min(.15,edgeMean/510));
  const color=s.map((v,c)=>Math.round(v/n*(1-weight)+dominant[c+1]/dominant[0]*weight));
  const sx=r-l>Math.max(1,base),sy=b-t>Math.max(1,base),split=(std>preset.variation||edgeMean>16)&&(sx||sy),force=(r-l>maxBlock||b-t>maxBlock);
  if((!force&&!split)||(!sx&&!sy)){blocks.push([l,t,r,b,[...color,Math.round(alpha/n)]]);return}
  const gap=Math.max(1,Math.floor(base*.35));
  let cutX=null,cutY=null,bestX=0,bestY=0;
  if(sx&&r-l>gap*2+1){const sampleStep=Math.max(1,Math.floor((b-t)/128));for(let x=l+gap;x<=r-gap;x++){let sum=0,nSamples=0,strong=0;for(let y=t;y<b;y+=sampleStep){const contrast=Math.abs(gray[y*w+x]-gray[y*w+x-1]);sum+=contrast;if(contrast>=24)strong++;nSamples++}const score=sum/nSamples;if(score>bestX){bestX=score;cutX=strong/nSamples>=.2?x:null}}if(bestX<20)cutX=null}
  if(sy&&b-t>gap*2+1){const sampleStep=Math.max(1,Math.floor((r-l)/128));for(let y=t+gap;y<=b-gap;y++){let sum=0,nSamples=0,strong=0;for(let x=l;x<r;x+=sampleStep){const contrast=Math.abs(gray[y*w+x]-gray[(y-1)*w+x]);sum+=contrast;if(contrast>=24)strong++;nSamples++}const score=sum/nSamples;if(score>bestY){bestY=score;cutY=strong/nSamples>=.2?y:null}}if(bestY<20)cutY=null}
  const xs=sx?[l,cutX??Math.floor((l+r)/2),r]:[l,r],ys=sy?[t,cutY??Math.floor((t+b)/2),b]:[t,b];
  for(let yy=0;yy<ys.length-1;yy++)for(let xx=0;xx<xs.length-1;xx++)region(xs[xx],ys[yy],xs[xx+1],ys[yy+1]);
 }
 region(0,0,w,h);
 const histogram=new Map(),totalArea=w*h,sampleLimit=4096;
 for(const block of blocks){
  const [l,t,r,b,color]=block;if(!color[3])continue;
  const weight=Math.max(1,Math.round((r-l)*(b-t)*sampleLimit/totalArea));
  const key=[color[0]>>3,color[1]>>3,color[2]>>3].join(",");
  const entry=histogram.get(key)||{bin:key.split(",").map(Number),count:0,sum:[0,0,0],squares:[0,0,0]};
  entry.count+=weight;
  for(let c=0;c<3;c++){entry.sum[c]+=color[c]*weight;entry.squares[c]+=color[c]*color[c]*weight;}
  histogram.set(key,entry);
 }
 const paletteCount=opts.colours==="auto"?null:Number(opts.colours);
 const candidates=[2,4,6,8,12,16,24,32,48,64];
 let count=paletteCount;
 if(count===null){count=candidates[candidates.length-1];for(const candidate of candidates){const palette=buildPalette(histogram,candidate);if(paletteRms(histogram,palette)<=8){count=candidate;break}}}
 count=Math.max(2,Math.min(256,count));
 const palette=buildPalette(histogram,count);
 const mapped=blocks.map(b=>{let c=b[4];if(c[3]&&palette.length){const nearest=nearestPaletteColor(c,palette);c=[...nearest.map(v=>v<=20?0:v),c[3]];if(bg&&dist(c,bg)<=bgThreshold)c=[...bg,c[3]]}return [...b.slice(0,4),c]});
 const owner=new Int32Array(w*h);owner.fill(-1);
 for(let i=0;i<mapped.length;i++){const [l,t,r,b]=mapped[i];for(let y=t;y<b;y++)owner.fill(i,y*w+l,y*w+r)}
 for(let i=0;i<mapped.length;i++){const [l,t,r,b,c]=mapped[i],area=(r-l)*(b-t),lum=.2126*c[0]+.7152*c[1]+.0722*c[2];if(area>Math.max(2,base*base*.2)||lum<32||!c[3])continue;const edges=new Map(),count=j=>{if(j<0||j===i)return;const n=mapped[j][4];if(!n[3])return;const key=n.slice(0,3).join(",");edges.set(key,(edges.get(key)||0)+1)};if(l>0)for(let y=t;y<b;y++)count(owner[y*w+l-1]);if(r<w)for(let y=t;y<b;y++)count(owner[y*w+r]);if(t>0)for(let x=l;x<r;x++)count(owner[(t-1)*w+x]);if(b<h)for(let x=l;x<r;x++)count(owner[b*w+x]);let best=null,shared=0,total=0;for(const [key,value] of edges){total+=value;if(value>shared){best=key;shared=value}}if(best&&shared/total>=.75){const replacement=best.split(",").map(Number);if(dist(c,replacement)<=45)mapped[i][4]=[...replacement,c[3]]}} return {width:w,height:h,blocks:mapped};
}
self.onmessage=e=>{try{const result=processImage(e.data.image,e.data.options);self.postMessage({id:e.data.id,result})}catch(error){self.postMessage({id:e.data.id,error:error.message||String(error)})}};
