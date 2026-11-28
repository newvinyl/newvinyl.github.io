/* Beta-Raum (User 28.11.): punkig, Club-Toilette, Tags und Sticker, Tiefe und Dramaturgie.
   Alles prozedural gezeichnet, kein Bildmaterial. Test: /beta/?raum=a|b|c */
(function(){
const M=(location.search.match(/[?&]raum=([abc])/)||[])[1];if(!M)return;
const cv=document.createElement("canvas");cv.id="raum";cv.setAttribute("aria-hidden","true");
cv.style.cssText="position:fixed;inset:0;width:100vw;height:100vh;z-index:-1;pointer-events:none";
document.body.prepend(cv);
const css=document.createElement("style");
css.textContent="html,body{background:transparent!important}.top,.bar{background:rgba(8,8,8,.78)!important;backdrop-filter:blur(3px)}"+
 "@media (min-width:861px){.side{background:linear-gradient(90deg,rgba(6,6,6,0),rgba(6,6,6,.88) 14%,rgba(6,6,6,.93));padding-left:28px;margin-left:-28px}}";
document.head.appendChild(css);

let seed=1;const R=()=>{seed=(seed*16807)%2147483647;return (seed-1)/2147483646},rr=(a,b)=>a+R()*(b-a),pick=a=>a[Math.floor(R()*a.length)];
const NEON=["#ff2bd6","#39ff14","#fff200","#ff5f1f","#00e5ff","#ff1744","#b388ff","#ffffff"];
const WORDS=["NO SKIPS","DIG DEEPER","B-SIDE","VINYL ONLY","WAX","ACID","DUB","LOUD","SPIN","KRACH","ZOFF","NO FUTURE","PRESS PLAY","SIDE A","33 RPM","45","MINT","VG+","OPEN LATE","LOCAL","RARE","HANDS OFF MY CRATE","DUBPLATE","WHITE LABEL","TEST PRESS","FLIP IT","BASS","1987","1979","SOUND SYSTEM","NO REFUNDS","LAST COPY","DANCE OR DIE","RAVE","TRUST THE DIGGER","EAT SLEEP DIG","STAY LOUD","HOUSE","TECHNO","ELECTRO","BREAKS","JUNGLE","STUDIO 4","ROOM 2","CHECK THE GROOVE"];
const TAGS=["KRK","ZOE","DSK","MUFF","REX","OKB","SIFT","WAXX","DUBZ","LOOP","NOIZ","RPM","TONI","ACK","GRVE","MOFO","BLITZ","RATZ"];

/* Ebenen der Raumschachtel (Fluchtpunkt), bilinear */
const lerp=(a,b,t)=>[a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t];
const Q=q=>(u,v)=>lerp(lerp(q[0],q[1],u),lerp(q[3],q[2],u),v);// q: tl,tr,br,bl
function quad(c,q,fill){c.beginPath();c.moveTo(...q[0]);c.lineTo(...q[1]);c.lineTo(...q[2]);c.lineTo(...q[3]);c.closePath();if(fill){c.fillStyle=fill;c.fill()}}
/* lokale Affinabbildung an (u,v): Einheitsquadrat (w,h in Ebenen-Einheiten) */
function at(c,P,u,v,du,dv,rot){const p=P(u,v),px=P(u+du,v),py=P(u,v+dv);const ax=px[0]-p[0],ay=px[1]-p[1],bx=py[0]-p[0],by=py[1]-p[1];
  c.setTransform(ax,ay,bx,by,p[0],p[1]);if(rot){c.translate(.5,.5);c.rotate(rot);c.translate(-.5,-.5)}}

function grime(c,q,n,col,a){const P=Q(q);for(let i=0;i<n;i++){const u=R(),v=R(),r=rr(.03,.22);at(c,P,u-r/2,v-r/2,r,r);const g=c.createRadialGradient(.5,.5,0,.5,.5,.5);g.addColorStop(0,col.replace("A",rr(a*.3,a)));g.addColorStop(1,col.replace("A",0));c.fillStyle=g;c.fillRect(0,0,1,1)}c.setTransform(1,0,0,1,0,0)}

function tiles(c,q,nu,nv,base,grout,var_){const P=Q(q);for(let i=0;i<nu;i++)for(let j=0;j<nv;j++){const a=P(i/nu,j/nv),b=P((i+1)/nu,j/nv),d=P((i+1)/nu,(j+1)/nv),e=P(i/nu,(j+1)/nv);
  const l=rr(-var_,var_);quad(c,[a,b,d,e],grout);const s=.06;const A=P((i+s)/nu,(j+s)/nv),B=P((i+1-s)/nu,(j+s)/nv),D=P((i+1-s)/nu,(j+1-s)/nv),E=P((i+s)/nu,(j+1-s)/nv);
  quad(c,[A,B,D,E],shade(base,l));if(R()<.04){c.strokeStyle="rgba(0,0,0,.5)";c.lineWidth=.8;c.beginPath();c.moveTo(...lerp(A,B,R()));c.lineTo(...lerp(E,D,R()));c.stroke()}}}
function bricks(c,q,nu,nv,cols,mortar){const P=Q(q);quad(c,q,mortar);for(let j=0;j<nv;j++){const off=j%2?.5:0;for(let i=-1;i<nu+1;i++){const u0=Math.max(0,(i+off)/nu),u1=Math.min(1,(i+off+1)/nu);if(u1<=u0)continue;
  const g=.07;const A=P(u0+g/nu,(j+g)/nv),B=P(u1-g/nu,(j+g)/nv),D=P(u1-g/nu,(j+1-g)/nv),E=P(u0+g/nu,(j+1-g)/nv);quad(c,[A,B,D,E],shade(pick(cols),rr(-.12,.08)))}}}
function shade(h,l){let n=parseInt(h.slice(1),16),r=n>>16,g=n>>8&255,b=n&255;const f=l<0?0:255,t=Math.abs(l);r=Math.round(r+(f-r)*t);g=Math.round(g+(f-g)*t);b=Math.round(b+(f-b)*t);return `rgb(${r},${g},${b})`}

/* Sticker */
function sticker(c,P,u,v,s,asp){const kind=R();const rot=rr(-.5,.5);at(c,P,u,v,s*asp,s,rot);c.save();
  const col=pick(NEON),dark=R()<.3,txt=pick(WORDS);
  const path=()=>{c.beginPath();const n=10;for(let i=0;i<=n;i++)c.lineTo(i/n,rr(-.02,.02));for(let i=0;i<=n;i++)c.lineTo(1+rr(-.01,.01),i/n);for(let i=n;i>=0;i--)c.lineTo(i/n,1+rr(-.02,.02));for(let i=n;i>=0;i--)c.lineTo(rr(-.01,.01),i/n);c.closePath()};
  c.shadowColor="rgba(0,0,0,.45)";c.shadowBlur=2;c.shadowOffsetY=1;
  if(kind<.18){c.beginPath();c.ellipse(.5,.5,.5,.5,0,0,7);c.fillStyle=col;c.fill();c.shadowColor="transparent";c.fillStyle="#111";txtFit(c,txt.split(" ")[0],.5,.55,.8,.34)}
  else if(kind<.34){path();c.fillStyle="#f4f1ea";c.fill();c.shadowColor="transparent";c.fillStyle="#d8232a";c.fillRect(0,0,1,.34);c.fillStyle="#fff";txtFit(c,"HELLO my name is",.5,.2,.9,.16);
    c.strokeStyle=pick(["#111","#1a237e","#b71c1c"]);c.lineWidth=.035;c.lineCap="round";scrib(c,.12,.48,.76,.4,3+Math.floor(R()*2))}
  else{path();c.fillStyle=dark?"#121212":col;c.fill();c.shadowColor="transparent";c.fillStyle=dark?col:(col=="#ffffff"||col=="#fff200"||col=="#39ff14"?"#111":"#fff");txtFit(c,txt,.5,.56,.9,.5)}
  if(R()<.35){c.globalCompositeOperation="destination-out";c.beginPath();const y=rr(.2,.8);c.moveTo(1.05,y-.3);for(let i=0;i<6;i++)c.lineTo(rr(.55,.85),y-.3+i*.12);c.lineTo(1.05,y+.4);c.fill();c.globalCompositeOperation="source-over"}
  c.restore();c.setTransform(1,0,0,1,0,0)}
function txtFit(c,t,x,y,w,h){c.save();c.textAlign="center";c.textBaseline="middle";c.font="900 100px 'Helvetica Neue',Helvetica,Arial,sans-serif";const m=c.measureText(t).width;
  const k=Math.min(w/m,h/100);c.translate(x,y);c.scale(k,k);c.fillText(t,0,0);c.restore()}
/* Tag: gekritzelte Buchstaben aus Kurven, mit Umriss und Tropfen */
function scrib(c,x,y,w,h,n){for(let i=0;i<n;i++){const cx=x+w*(i+.5)/n,cw=w/n;c.beginPath();let px=cx+rr(-.5,.5)*cw,py=y+rr(-.5,.5)*h;c.moveTo(px,py);
  for(let k=0;k<3;k++){const nx=cx+rr(-.6,.6)*cw,ny=y+rr(-.5,.5)*h;c.quadraticCurveTo(cx+rr(-.8,.8)*cw,y+rr(-.7,.7)*h,nx,ny)}c.stroke()}}
function tag(c,P,u,v,s,col,outline,drip){const w=s*rr(2.2,4),txtN=3+Math.floor(R()*3);at(c,P,u,v,w,s,rr(-.25,.15));c.lineCap="round";c.lineJoin="round";
  const st=seed;if(outline){c.strokeStyle=outline;c.lineWidth=.16;scrib(c,.05,.5,.9,.8,txtN);seed=st}
  c.strokeStyle=col;c.lineWidth=rr(.05,.1);scrib(c,.05,.5,.9,.8,txtN);
  if(drip){c.lineWidth=.025;for(let i=0;i<4;i++){const x=rr(.1,.9),y=rr(.5,.8);c.beginPath();c.moveTo(x,y);c.lineTo(x,y+rr(.2,1.1));c.stroke()}}
  if(R()<.4){c.lineWidth=.04;c.beginPath();c.moveTo(.02,.95);c.quadraticCurveTo(.5,1.15,.98,.9);c.stroke()}
  c.setTransform(1,0,0,1,0,0)}
function poster(c,P,u,v,s){at(c,P,u,v,s*.72,s,rr(-.06,.06));const bg=pick(["#ff2bd6","#fff200","#39ff14","#ff5f1f","#f2efe6","#00e5ff","#111"]);c.fillStyle=bg;c.fillRect(0,0,1,1);
  const fg=bg=="#111"?pick(NEON):"#111";c.fillStyle=fg;txtFit(c,pick(["TONIGHT","ALL NIGHT","LIVE","SOUND CLASH","WAREHOUSE","BLOCK PARTY","NO SLEEP","CLUB NIGHT"]),.5,.18,.9,.2);
  c.fillRect(.08,.32,.84,.012);txtFit(c,pick(TAGS)+" + "+pick(TAGS),.5,.45,.84,.1);c.globalAlpha=.85;for(let i=0;i<5;i++)c.fillRect(.1,.58+i*.06,rr(.3,.8),.022);c.globalAlpha=1;
  if(R()<.6){c.globalCompositeOperation="destination-out";c.beginPath();c.moveTo(-.1,rr(.6,1));for(let i=0;i<8;i++)c.lineTo(i/7,rr(.75,1.05));c.lineTo(1.1,1.2);c.lineTo(-.1,1.2);c.fill();c.globalCompositeOperation="source-over"}
  c.setTransform(1,0,0,1,0,0)}

function cover(c,q,cfg){const P=Q(q);
  for(let i=0;i<cfg.posters;i++)poster(c,P,rr(-.05,.95),rr(-.05,.8),rr(.12,.3));
  for(let i=0;i<cfg.tagsBig;i++)tag(c,P,rr(-.05,.9),rr(0,.85),rr(.05,.14),pick(cfg.tagCols),cfg.outline,R()<.5);
  for(let i=0;i<cfg.stickers;i++){const s=rr(.025,.075);sticker(c,P,rr(-.02,.98),Math.pow(R(),cfg.low||1)*.95,s,rr(.9,2.6))}
  for(let i=0;i<cfg.tags;i++)tag(c,P,rr(-.05,.95),rr(0,.95),rr(.015,.05),pick(cfg.tagCols),R()<.3?cfg.outline:null,R()<.25)}

function draw(){const dpr=Math.min(2,devicePixelRatio||1),W=innerWidth,H=innerHeight;cv.width=W*dpr;cv.height=H*dpr;const c=cv.getContext("2d");c.setTransform(dpr,0,0,dpr,0,0);
  if(!c._S)c._S=c.setTransform.bind(c);const S=c._S;c.setTransform=(a,b,d,e,f,g)=>S(a*dpr,b*dpr,d*dpr,e*dpr,f*dpr,g*dpr);
  seed=({a:11,b:23,c:37})[M];
  const st=document.getElementById("stage"),r=st?st.getBoundingClientRect():{left:0,width:W,top:0,height:H};
  const vx=r.left+r.width/2,vy=r.top+r.height*.42;const bw=W*.34,bh=H*.42;
  const b0=[vx-bw/2,vy-bh*.62],b1=[vx+bw/2,vy-bh*.62],b2=[vx+bw/2,vy+bh*.38],b3=[vx-bw/2,vy+bh*.38];
  const k=3.2,ex=p=>[vx+(p[0]-vx)*k,vy+(p[1]-vy)*k];const f0=ex(b0),f1=ex(b1),f2=ex(b2),f3=ex(b3);
  const back=[b0,b1,b2,b3],left=[f0,b0,b3,f3],right=[b1,f1,f2,b2],floor=[b3,b2,f2,f3],ceil=[f0,f1,b1,b0];
  const walls=[left,back,right];
  if(M=="a"){/* Club-Toilette: verschmutzte Fliesen, Neonröhre grünstichig */
    walls.forEach(w=>tiles(c,w,w==back?10:14,9,"#cfd3c4","#6f6a5c",.08));tiles(c,floor,10,10,"#1b1b1b","#0c0c0c",.06);
    {const P=Q(floor);for(let i=0;i<10;i++)for(let j=0;j<10;j++)if((i+j)%2){quad(c,[P(i/10,j/10),P((i+1)/10,j/10),P((i+1)/10,(j+1)/10),P(i/10,(j+1)/10)],"rgba(225,222,210,.55)")}}
    quad(c,ceil,"#202020");walls.forEach(w=>grime(c,w,40,"rgba(60,45,20,A)",.35));
    walls.forEach(w=>cover(c,w,{posters:w==back?3:5,tagsBig:w==back?7:12,stickers:w==back?150:260,tags:w==back?60:110,tagCols:["#111","#111","#ff2bd6","#1a237e","#d50000","#00c853"],outline:null}));
    tint(c,W,H,"rgba(170,255,190,.10)");spot(c,W,H,vx,r.top+r.height*.1,"rgba(220,255,225,.0)",.86);
  } else if(M=="b"){/* Altes Gewölbe: Backstein, pinke Neonröhre, Plakate */
    const bc=["#7a3b26","#8c4a2f","#6b2f1f","#94553a","#5e2a1c","#7f4630"];walls.forEach(w=>bricks(c,w,w==back?9:14,18,bc,"#2a201b"));
    quad(c,floor,"#141210");grime(c,floor,30,"rgba(0,0,0,A)",.6);quad(c,ceil,"#16110f");
    walls.forEach(w=>grime(c,w,50,"rgba(0,0,0,A)",.55));
    walls.forEach(w=>cover(c,w,{posters:w==back?7:12,tagsBig:w==back?6:10,stickers:w==back?90:170,tags:w==back?30:60,tagCols:["#f5f5f5","#fff200","#ff2bd6","#39ff14"],outline:"#000",low:1.4}));
    neon(c,lerp(b0,b1,.18),lerp(b0,b1,.82),vy-bh*.5,"#ff2bd6");tint(c,W,H,"rgba(255,40,160,.08)");spot(c,W,H,vx,r.top,"rgba(255,180,120,.0)",.8);
  } else {/* Plakatwand-Chaos: schwarz gestrichen, Lagen von Plakaten, Neonsprays, rotes Licht */
    walls.forEach(w=>quad(c,w,"#151515"));quad(c,floor,"#0e0e0e");quad(c,ceil,"#0a0a0a");
    walls.forEach(w=>cover(c,w,{posters:w==back?22:40,tagsBig:w==back?14:24,stickers:w==back?120:220,tags:w==back?70:120,tagCols:["#ff2bd6","#39ff14","#fff200","#00e5ff","#ff5f1f","#ffffff","#c0c0c0"],outline:"#000"}));
    walls.forEach(w=>grime(c,w,30,"rgba(0,0,0,A)",.5));tint(c,W,H,"rgba(255,20,40,.12)");spot(c,W,H,vx,r.top+r.height*.05,"",.84);
  }
  /* Alterung: Farben vergilbt und entsättigt, Licht fällt zum Betrachter hin ab */
  const AG={a:[.30,"rgba(214,196,150,.45)"],b:[.25,"rgba(205,170,130,.4)"],c:[.18,"rgba(220,200,170,.3)"]}[M];
  walls.forEach(w=>{c.globalCompositeOperation="saturation";quad(c,w,`rgba(128,128,128,${AG[0]})`);c.globalCompositeOperation="multiply";quad(c,w,AG[1]);c.globalCompositeOperation="source-over";grime(c,w,70,"rgba(70,50,20,A)",.28);
    const n=w==left?lerp(w[0],w[3],.5):w==right?lerp(w[1],w[2],.5):null,f=w==left?lerp(w[1],w[2],.5):w==right?lerp(w[0],w[3],.5):null;
    if(n){const g=c.createLinearGradient(...n,...f);g.addColorStop(0,"rgba(0,0,0,.6)");g.addColorStop(1,"rgba(0,0,0,0)");quad(c,w,g)}});
  {const g=c.createLinearGradient(0,H,0,b3[1]);g.addColorStop(0,"rgba(0,0,0,.7)");g.addColorStop(1,"rgba(0,0,0,.1)");quad(c,floor,g)}
  /* Kanten der Raumschachtel */
  c.strokeStyle="rgba(0,0,0,.6)";c.lineWidth=3;[[b0,f0],[b1,f1],[b2,f2],[b3,f3]].forEach(([a,b])=>{c.beginPath();c.moveTo(...a);c.lineTo(...b);c.stroke()});quad(c,back);c.stroke();
  c.setTransform(1,0,0,1,0,0)}
function tint(c,W,H,col){c.fillStyle=col;c.globalCompositeOperation="overlay";c.fillRect(0,0,W,H);c.globalCompositeOperation="source-over"}
function neon(c,a,b,y,col){c.save();c.lineCap="round";for(const [w,al] of [[60,.10],[30,.2],[12,.5],[4,1]]){c.strokeStyle=w==4?"#ffe9fb":col;c.globalAlpha=al;c.lineWidth=w;c.beginPath();c.moveTo(a[0],y);c.lineTo(b[0],y);c.stroke()}c.restore();
  const g=c.createRadialGradient((a[0]+b[0])/2,y,0,(a[0]+b[0])/2,y,(b[0]-a[0])*1.2);g.addColorStop(0,"rgba(255,43,214,.28)");g.addColorStop(1,"rgba(255,43,214,0)");c.fillStyle=g;c.globalCompositeOperation="screen";c.fillRect(0,0,innerWidth,innerHeight);c.globalCompositeOperation="source-over"}
/* Dramaturgie: Lichtkegel auf die Kiste, Rest fällt ins Dunkel */
function spot(c,W,H,x,y,_,dark){const g=c.createRadialGradient(x,y+H*.35,H*.08,x,y+H*.35,Math.max(W,H)*.75);g.addColorStop(0,"rgba(0,0,0,0)");g.addColorStop(.45,`rgba(0,0,0,${dark*.45})`);g.addColorStop(1,`rgba(0,0,0,${dark})`);c.fillStyle=g;c.fillRect(0,0,W,H);
  const t=c.createLinearGradient(0,0,0,H*.3);t.addColorStop(0,"rgba(0,0,0,.6)");t.addColorStop(1,"rgba(0,0,0,0)");c.fillStyle=t;c.fillRect(0,0,W,H*.3);
  for(let i=0;i<9000;i++){c.fillStyle=`rgba(${R()<.5?0:255},${R()<.5?0:255},${R()<.5?0:255},.05)`;c.fillRect(R()*W,R()*H,1,1)}}
let tm;addEventListener("resize",()=>{clearTimeout(tm);tm=setTimeout(draw,200)});
if(document.readyState==="complete")setTimeout(draw,50);else addEventListener("load",()=>setTimeout(draw,50));
})();
