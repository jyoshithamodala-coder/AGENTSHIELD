const API='http://127.0.0.1:8000';let auditData=[];
const $=id=>document.getElementById(id);
const esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(path,opts={}){const r=await fetch(API+path,{headers:{'Content-Type':'application/json'},...opts});const t=await r.text();let d;try{d=t?JSON.parse(t):{}}catch{d={detail:t}}if(!r.ok)throw Error(d.detail||`HTTP ${r.status}`);return d}
function rowsOf(d){return Array.isArray(d)?d:(d.results||d.logs||d.items||[])}
function badge(d){let s=String(d||'UNKNOWN').toUpperCase();return `<b style="color:${s==='ALLOW'?'var(--green)':s==='DENY'?'var(--red)':'var(--amber)'}">${esc(s)}</b>`}
function time(v){return v?new Date(v).toLocaleString(): '—'}
async function refresh(){try{let h=await api('/api/health');$('backendStatus').textContent='● Backend connected';$('backendStatus').style.color='var(--green)'}catch(e){$('backendStatus').textContent='● Backend offline: '+e.message;$('backendStatus').style.color='var(--red)'}
try{auditData=rowsOf(await api('/api/audit?limit=50'));let n=d=>auditData.filter(x=>String(x.decision).toUpperCase()===d).length;
$('total').textContent=auditData.length;$('allowed').textContent=n('ALLOW');$('blocked').textContent=n('DENY');$('pending').textContent=n('REQUIRE_APPROVAL');
$('recent').innerHTML=auditData.slice(0,7).map(x=>`<tr><td>${esc(time(x.timestamp))}</td><td>${esc(x.tool_name||x.operation)}</td><td>${badge(x.decision)}</td><td>${esc(x.risk_level)}</td></tr>`).join('')||'<tr><td colspan="4">No audit records returned.</td></tr>';
$('securityEvents').innerHTML=auditData.slice(0,15).map(x=>`<p>${badge(x.decision)} &nbsp; ${esc(x.tool_name||x.operation)} · ${esc(x.risk_level)}<br>${esc(x.reason)}</p>`).join('')||'No events.';if(window.renderAudit)window.renderAudit();
}catch(e){$('recent').innerHTML=`<tr><td colspan="4">${esc(e.message)}</td></tr>`;$('auditRows').innerHTML=`<tr><td colspan="7">${esc(e.message)}</td></tr>`}}
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v.id===b.dataset.view));document.querySelectorAll('[data-view]').forEach(x=>x.classList.toggle('active',x===b));$('title').textContent=b.textContent.trim()});
$('refresh').onclick=refresh;refresh();