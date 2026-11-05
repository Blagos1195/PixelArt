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
  const fraction=dominant[0]/n,weight=Math.min(.9,.35+.5*(1-fraction)+Math.min(.15,edgeMean/510));
  const color=s.map((v,c)=>Math.round(v/n*(1-weight)+dominant[c+1]/dominant[0]*weight));
  const sx=r-l>base,sy=b-t>base,split=(std>preset.variation||edgeMean>6)&&(sx||sy),force=(r-l>maxBlock||b-t>maxBlock);
  if(!force&&!split){blocks.push([l,t,r,b,[...color,Math.round(alpha/n)]]);return}
  const xs=sx?[l,Math.floor((l+r)/2),r]:[l,r],ys=sy?[t,Math.floor((t+b)/2),b]:[t,b];
  for(let yy=0;yy<ys.length-1;yy++)for(let xx=0;xx<xs.length-1;xx++)region(xs[xx],ys[yy],xs[xx+1],ys[yy+1]);
 }
 region(0,0,w,h);
 const paletteCount=opts.colours==="auto"?null:Number(opts.colours);
 const samples=blocks.filter(b=>b[4][3]).map(b=>b[4].slice(0,3));
 let count=paletteCount||[2,4,6,8,12,16,24,32,48,64].find(n=>samples.length<=n*3)||64;
 count=Math.max(2,Math.min(256,count));
 const centers=[];
 if(samples.length){for(let i=0;i<count;i++){const p=samples[Math.floor(i*samples.length/count)];centers.push(p.slice())}
  for(let round=0;round<5;round++){const sums=centers.map(()=>[0,0,0,0]);for(const p of samples){let best=0,bd=Infinity;for(let j=0;j<centers.length;j++){const d=dist(p,centers[j]);if(d<bd){bd=d;best=j}}const s=sums[best];s[0]++;s[1]+=p[0];s[2]+=p[1];s[3]+=p[2]}for(let j=0;j<centers.length;j++)if(sums[j][0])centers[j]=sums[j].slice(1).map(v=>Math.round(v/sums[j][0]))}
 }
 const mapped=blocks.map(b=>{let c=b[4];if(c[3]&&centers.length){let best=centers[0],bd=Infinity;for(const p of centers){const d=dist(c,p);if(d<bd){bd=d;best=p}}c=[...best.map(v=>v<=20?0:v),c[3]];if(bg&&dist(c,bg)<=36)c=[...bg,c[3]]}return [...b.slice(0,4),c]});
 const adjacency=new Map();for(let i=0;i<mapped.length;i++){const [l,t,r,b,c]=mapped[i],area=(r-l)*(b-t),lum=.2126*c[0]+.7152*c[1]+.0722*c[2];if(area>Math.max(2,base*base*.2)||lum<32||!c[3])continue;let edges=new Map();for(let j=0;j<mapped.length;j++){if(i===j)continue;const [a,y,x,z,n]=mapped[j];if(!n[3])continue;let shared=0;if(x===l||r===a)shared=Math.max(0,Math.min(b,z)-Math.max(t,y));if(z===t||b===y)shared=Math.max(shared,Math.max(0,Math.min(r,x)-Math.max(l,a)));if(shared)edges.set(n.slice(0,3).join(","),(edges.get(n.slice(0,3).join(","))||0)+shared)}let best=[null,0];for(const e of edges)if(e[1]>best[1])best=e;if(best[0]&&best[1]/[...edges.values()].reduce((a,v)=>a+v,0)>=.75){const replacement=best[0].split(",").map(Number);if(dist(c,replacement)<=45)mapped[i][4]=[...replacement,c[3]]}}
 return {width:w,height:h,blocks:mapped};
}
self.onmessage=e=>{try{const result=processImage(e.data.image,e.data.options);self.postMessage({id:e.data.id,result})}catch(error){self.postMessage({id:e.data.id,error:error.message||String(error)})}};
