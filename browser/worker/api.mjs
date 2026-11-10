const json=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
const finite=(n,min=0,max=1e12)=>typeof n==='number'&&Number.isFinite(n)&&n>=min&&n<=max;
export function validSave(p){
 if(!p||p.version!==1||!finite(p.marketStart,1,Date.now()/1000+60)||!p.state||typeof p.state!=='object')return false;
 const s=p.state;
 for(const k of ['cash','market_elapsed','elapsed','speed_until','notice_until'])if(!finite(s[k]))return false;
 if(!finite(s.x,17,943)||!finite(s.y,119,925)||!Number.isInteger(s.bag_size)||!finite(s.bag_size,12,1e6)||![1,-1].includes(s.facing)||typeof s.won!=='boolean')return false;
 for(const k of ['supplies','goods','demand','costs','prices'])if(!Array.isArray(s[k])||s[k].length!==4||!s[k].every(n=>Number.isInteger(n)&&finite(n)))return false;
 if(!Array.isArray(s.orders)||s.orders.length!==4||!s.orders.every(o=>o===null||(o&&Number.isInteger(o.quantity)&&finite(o.quantity,1)&&finite(o.ready_at))))return false;
 if(!(s.power_up===null||[0,1,2].includes(s.power_up)))return false;
 if(!(s.market_event===null||(Array.isArray(s.market_event)&&s.market_event.length===2&&s.market_event.every(x=>typeof x==='string'&&x.length<=500))))return false;
 for(const k of ['notice','message'])if(typeof s[k]!=='string'||s[k].length>1000)return false;
 const pr=s.profile;if(!pr||typeof pr.name!=='string'||pr.name.length>24||!['Peach','Amber','Brown','Mint','Lilac'].includes(pr.body)||!['Chestnut','Black','Blonde','Silver','Pink'].includes(pr.hair)||!['Builder','Chef','Explorer','Racer','Astronaut','Wizard'].includes(pr.costume))return false;
 const keys=['cash','supplies','goods','orders','demand','market_elapsed','costs','prices','market_event','elapsed','x','y','facing','won','bag_size','speed_until','power_up','profile','notice','notice_until','message'];
 return Object.keys(s).every(k=>keys.includes(k))&&keys.every(k=>Object.hasOwn(s,k));
}
export async function api(request,env){
 const user=request.headers.get('oai-authenticated-user-id');if(!user)return json({error:'Sign in to save or continue your game.'},401);
 if(request.method!=='GET'&&request.method!=='PUT')return new Response(null,{status:405,headers:{Allow:'GET, PUT'}});
 if(request.method==='PUT'){
  const origin=request.headers.get('Origin');if(origin&&origin!==new URL(request.url).origin)return json({error:'Invalid origin'},403);
 }
 if(!env.BUCKET)return json({error:'Save storage is unavailable. Your local backup is safe.'},503);
 // The dispatch-provided user ID selects the save; callers cannot choose another user's key.
 const key='foundry-saves/v1/'+encodeURIComponent(user)+'.json';
 try{
  if(request.method==='GET'){
   const obj=await env.BUCKET.get(key);if(!obj)return json({save:null});
   return json({save:await obj.json(),revision:obj.etag});
  }
  if(Number(request.headers.get('Content-Length'))>32768)return json({error:'Save is too large'},413);
  const text=await request.text();if(text.length>32768)return json({error:'Save is too large'},413);
  let data;try{data=JSON.parse(text)}catch{return json({error:'Invalid JSON'},400)}
  if(!validSave(data))return json({error:'Invalid game save'},400);
  const expected=request.headers.get('If-Match');if(!expected)return json({error:'Load your cloud save before saving.'},428);
  const savedAt=new Date().toISOString();
  const result=await env.BUCKET.put(key,JSON.stringify({version:1,state:data.state,marketStart:data.marketStart,savedAt}),{httpMetadata:{contentType:'application/json'},onlyIf:expected==='none'?{etagDoesNotMatch:'*'}:{etagMatches:expected}});
  if(!result)return json({error:'A newer cloud save exists. Return to the menu and reload it before saving.'},409);
  return json({savedAt,revision:result.etag});
 }catch{return json({error:'Cloud save failed. Your browser backup is still available.'},503)}
}
