'use strict';

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const nf = new Intl.NumberFormat('pt-BR');
const N = x => (x == null ? '—' : nf.format(x));
const dec = (x, d) => x.toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d });
const P = (x, d = 1) => (x == null || isNaN(x) ? '—' : dec(x * 100, d) + '%');
const PP = (x, d = 1) => (x == null ? '—' : (x > 0 ? '+' : x < 0 ? '−' : '') + dec(Math.abs(x * 100), d) + ' pts');
const Z = x => (x == null ? '—' : (x < 0 ? '−' : '') + dec(Math.abs(x), 1));
const S = x => (x == null ? '—' : (x > 0 ? '+' : x < 0 ? '−' : '') + nf.format(Math.abs(x)));
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const norm = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const nome = s => esc(String(s).toLowerCase().replace(/(^|[\s'(-])(\p{L})/gu, (m, a, b) => a + b.toUpperCase())
  .replace(/ (De|Da|Do|Das|Dos|E|Del) /g, w => w.toLowerCase()));

const STATUS = {
  'aberta': ['aberta', 'Em aberto'],
  'explicada em parte': ['aberta', 'Explicada em parte'],
  'explicada': ['explicada', 'Explicada'],
  'sem sinal': ['sem-sinal', 'Sem sinal'],
  'fora do alcance': ['fora', 'Fora do alcance'],
};
const ORDEM_STATUS = { 'aberta': 0, 'explicada em parte': 1, 'explicada': 2, 'sem sinal': 3, 'fora do alcance': 4 };
const selo = st => { const [c, t] = STATUS[st] || ['fora', st]; return `<span class="selo ${c}">${t}</span>`; };

const ALERTA = {
  z_cresc: ['eleitorado cresceu muito desde 2022', 'crescimento'],
  z_turn: ['comparecimento fora do padrão', 'crescimento'],
  z_swing: ['mudou muito desde 2022', 'estados'],
  z_biom: ['muita liberação sem digital', 'biometria'],
  'Flávio perdeu votos': ['Flávio perdeu votos no 2º turno', 'segundo_turno'],
  'Lula perdeu votos': ['Lula perdeu votos no 2º turno', 'segundo_turno'],
  'Lula ganhou mais que o bolo': ['Lula ganhou mais que os votos em disputa', 'segundo_turno'],
  'salto de comparecimento': ['salto de comparecimento no 2º turno', 'segundo_turno'],
  'mais eleitores que moradores': ['mais eleitores que moradores', 'cadastro'],
  'virou desde 2022': ['virou de lado desde 2022', 'viradas'],
};

const E = { d: null, uf: 'CE', aba: 'panorama', mun: null, camada: 'nav', vb: [0, 0, 660, 640], feitas: new Set() };

/* ---------- utilitários de visualização ---------- */
const TABS = new Map();
let tabSeq = 0;
function tabela(cols, rows, opts = {}) {
  const id = 't' + tabSeq++;
  TABS.set(id, { cols, base: rows, rows, ord: opts.ord ?? null, dir: opts.dir ?? -1, lim: opts.lim || 150 });
  let filtro = '';
  if (opts.uf) {
    const ufs = [...new Set(rows.map(r => r.uf))].sort();
    filtro = `<div class="controles-tab"><label>Estado <select data-tabuf="${id}"><option value="">Todos (${N(rows.length)})</option>${ufs.map(u => `<option>${u}</option>`).join('')}</select></label></div>`;
  }
  return `${filtro}<div class="tabela-rola" data-tab="${id}">${corpoTab(id)}</div>`;
}
function corpoTab(id) {
  const t = TABS.get(id);
  let rows = [...t.rows];
  if (t.ord != null) {
    const c = t.cols[t.ord];
    const v = r => (c.v ? c.v(r) : r[c.k]);
    rows.sort((a, b) => {
      const x = v(a), y = v(b);
      if (x == null) return 1;
      if (y == null) return -1;
      return (x > y ? 1 : x < y ? -1 : 0) * t.dir;
    });
  }
  const cab = t.cols.map((c, i) => `<th data-ord="${i}" class="${c.n ? 'n' : ''}" aria-sort="${t.ord === i ? (t.dir > 0 ? 'ascending' : 'descending') : 'none'}">${c.t}${t.ord === i ? (t.dir > 0 ? ' ▲' : ' ▼') : ''}</th>`).join('');
  const corpo = rows.slice(0, t.lim).map(r => `<tr>${t.cols.map(c => `<td class="${c.n ? 'n' : ''}">${c.f ? c.f(r) : esc(r[c.k])}</td>`).join('')}</tr>`).join('');
  const mais = rows.length > t.lim ? `<p class="pequeno texto-2" style="padding:8px 10px;margin:0">Mostrando ${t.lim} de ${N(rows.length)}. Ordene pelas colunas ou filtre por estado.</p>` : '';
  return `<table><thead><tr>${cab}</tr></thead><tbody>${corpo}</tbody></table>${mais}`;
}
document.addEventListener('click', ev => {
  const th = ev.target.closest('th[data-ord]');
  if (!th) return;
  const box = th.closest('[data-tab]');
  const t = TABS.get(box.dataset.tab);
  const i = +th.dataset.ord;
  if (t.ord === i) t.dir *= -1; else { t.ord = i; t.dir = -1; }
  box.innerHTML = corpoTab(box.dataset.tab);
});
document.addEventListener('change', ev => {
  const sel = ev.target.closest('[data-tabuf]');
  if (!sel) return;
  const id = sel.dataset.tabuf, t = TABS.get(id);
  t.rows = sel.value ? t.base.filter(r => r.uf === sel.value) : t.base;
  $(`[data-tab="${id}"]`).innerHTML = corpoTab(id);
});

function barras(items, { fmt = Z, cor = 'var(--ciano)', sinal = false, max = null } = {}) {
  const M = max || Math.max(...items.map(i => Math.abs(i.v ?? 0))) || 1;
  return `<div class="barras">${items.map(i => {
    const v = i.v ?? 0;
    let st;
    if (sinal) {
      const w = Math.abs(v) / M * 50;
      st = v >= 0 ? `left:50%;width:${w}%` : `left:${50 - w}%;width:${w}%`;
    } else st = `left:0;width:${(v / M) * 100}%`;
    return `<div class="barra"><span>${i.rot}</span><div class="trilho">${sinal ? '<span class="zero" style="left:50%"></span>' : ''}<i style="${st};background:${i.cor || cor}"></i></div><b class="n">${fmt(i.v)}</b></div>`;
  }).join('')}</div>`;
}
function colunas(items, { fmt = Z } = {}) {
  const M = Math.max(...items.map(i => i.v)) || 1;
  return `<div class="colunas">${items.map(i => `<div class="coluna"><span>${fmt(i.v)}</span><i style="height:${(i.v / M) * 82}%;background:${i.cor || 'var(--ciano)'}"></i></div>`).join('')}</div>
  <div class="coluna-rot">${items.map(i => `<span>${i.rot}</span>`).join('')}</div>`;
}
const numeros = lista => `<div class="numeros">${lista.map(([v, t]) => `<div class="numero"><b>${v}</b><span>${t}</span></div>`).join('')}</div>`;
const viz = (titulo, html) => `<div class="viz"><h4>${titulo}</h4>${html}</div>`;
const pistaLink = (id, txt) => `<a href="#analises/${id}">${txt}</a>`;

function mistura(a, b, t) {
  const h = s => [1, 3, 5].map(i => parseInt(s.slice(i, i + 2), 16));
  const [x, y] = [h(a), h(b)];
  return '#' + x.map((v, i) => Math.round(v + (y[i] - v) * Math.max(0, Math.min(1, t))).toString(16).padStart(2, '0')).join('');
}

/* ---------- placar ---------- */
function placar() {
  const t = E.d.turno2;
  const pl = t.lula / (t.lula + t.flavio) * 100;
  $('#placar').innerHTML = `
    <div class="lado esq"><div class="faixas"></div><span class="selo-ia">ilustração · IA</span>
      <img class="retrato" src="img/lula_ia.jpg" alt="Lula, ilustração gerada por IA">
      <div class="info"><div class="nome">LULA</div><div class="partido">PT · 13</div>
        <div class="pct">${t.pl}%</div><div class="votos">${N(t.lula)} votos</div></div></div>
    <div class="centro"><div class="rotulo">BRASIL · 2º TURNO</div>
      <small>100% das seções totalizadas · ${esc(t.hora)}</small>
      <div class="barra-dupla" role="img" aria-label="Lula ${t.pl}%, Flávio ${t.pf}%"><i class="l" style="width:${pl}%"></i><i class="f" style="width:${100 - pl}%"></i></div>
      <div class="margem">Diferença: <b>${N(t.margem)}</b> votos · comparecimento ${N(t.comparecimento)}</div></div>
    <div class="lado dir"><div class="faixas"></div><span class="selo-ia">ilustração · IA</span>
      <img class="retrato" src="img/flavio_ia.jpg" alt="Flávio Bolsonaro, ilustração gerada por IA">
      <div class="info"><div class="nome">FLÁVIO BOLSONARO</div><div class="partido">PL · 22</div>
        <div class="pct">${t.pf}%</div><div class="votos">${N(t.flavio)} votos</div></div></div>`;
}

/* ---------- mapa ---------- */
const CAMADAS = {
  nav: { valor: () => null },
  t2: { valor: e => e.sl2, cor: v => v == null ? null : v >= .5 ? mistura('#4a6386', '#f0545a', (v - .5) / .25) : mistura('#4a6386', '#2fa8f0', (.5 - v) / .25),
    legenda: () => `<span>Flávio</span><i class="grad" style="background:linear-gradient(90deg,#2fa8f0,#4a6386,#f0545a)"></i><span>Lula</span>` },
  escola: { valor: e => e.escola, rot: 'seções que destoam' },
  cadastro: { valor: e => e.cad_exc, rot: 'eleitores além da população' },
  migr: { valor: e => E.migrUF[e.uf] ?? 0, rot: 'municípios onde Flávio perdeu votos' },
  migrL: { valor: e => E.migrUFL[e.uf] ?? 0, rot: 'municípios onde Lula perdeu votos' },
  direita: { valor: e => e.transf?.direita ? e.transf.direita.flavio / ((e.transf.direita.lula + e.transf.direita.flavio) || 1) : null,
    cor: v => v == null ? null : v >= .5 ? mistura('#4a6386', '#2fa8f0', (v - .5) / .4) : mistura('#4a6386', '#f0545a', (.5 - v) / .4),
    legenda: () => `<span>mais para o Lula</span><i class="grad" style="background:linear-gradient(90deg,#f0545a,#4a6386,#2fa8f0)"></i><span>mais para o Flávio · eleitores de Renan, Caiado e Zema (DF sem estimativa)</span>` },
  manual: { valor: e => e.logs?.manual_pct, rot: 'votos liberados sem digital', fmt: v => P(v), min: true },
};
function corCamada(uf) {
  const c = CAMADAS[E.camada], e = E.d.estados[uf];
  if (!c.cor && !c.rot) return null;
  const v = c.valor(e);
  if (c.cor) return c.cor(v);
  const vals = Object.values(E.d.estados).filter(x => x.uf !== 'ZZ').map(c.valor).filter(x => x != null);
  const mx = Math.max(...vals), mn = c.min ? Math.min(...vals) : 0;
  return v == null ? null : mistura('#2b3f5c', '#fbbf24', (v - mn) / ((mx - mn) || 1));
}
function legenda() {
  const c = CAMADAS[E.camada];
  if (c.legenda) return c.legenda();
  if (!c.rot) return '';
  const vals = Object.values(E.d.estados).filter(x => x.uf !== 'ZZ').map(c.valor).filter(x => x != null);
  const f = c.fmt || N;
  return `<span>${f(c.min ? Math.min(...vals) : 0)}</span><i class="grad" style="background:linear-gradient(90deg,#2b3f5c,#fbbf24)"></i><span>${f(Math.max(...vals))} ${c.rot}</span>`;
}

function desenharMapa() {
  const m = E.d.mapa;
  const fora = ['RN', 'PB', 'PE', 'AL', 'SE'];
  const lateral = { ES: [44, 6], RJ: [36, 20] };
  const pos = {};
  let ult = -1e9;
  for (const uf of [...fora].sort((a, b) => m[a].cy - m[b].cy)) {
    const y = Math.max(m[uf].cy, ult + 17);
    pos[uf] = [626, y];
    ult = y;
  }
  for (const [uf, d] of Object.entries(lateral)) pos[uf] = [m[uf].cx + d[0], m[uf].cy + d[1]];
  E.rotulo = {};
  let estados = '', guias = '', rotulos = '';
  for (const [uf, g] of Object.entries(m)) {
    const [lx, ly] = pos[uf] || [g.cx, g.cy];
    E.rotulo[uf] = [lx, ly, !!pos[uf]];
    estados += `<g class="uf" data-uf="${uf}" tabindex="0" role="button" aria-label="${esc(E.d.nomes_uf[uf])}"><path d="${g.d}"/></g>`;
    if (pos[uf]) guias += `<path class="guia" d="M${g.cx},${g.cy}L${lx - 5},${ly}"/><circle class="guia-ponto" cx="${g.cx}" cy="${g.cy}" r="2"/>`;
    rotulos += `<text class="rot${pos[uf] ? ' externo' : ''}" data-uf="${uf}" x="${lx}" y="${ly}" text-anchor="${pos[uf] ? 'start' : 'middle'}" dominant-baseline="central">${uf}</text>`;
  }
  $('#mapa').innerHTML = `<g id="m-estados">${estados}</g><g>${guias}</g><g>${rotulos}</g><g id="balao"></g>`;
  aplicarVB();
}
function pintarMapa() {
  const svg = $('#mapa');
  svg.classList.toggle('colorido', E.camada !== 'nav');
  for (const g of $$('.uf', svg)) {
    const c = corCamada(g.dataset.uf);
    if (c) g.style.setProperty('--c', c); else g.style.removeProperty('--c');
    g.classList.toggle('sel', g.dataset.uf === E.uf);
    g.setAttribute('aria-pressed', g.dataset.uf === E.uf);
  }
  for (const t of $$('.rot', svg)) t.classList.toggle('sel', t.dataset.uf === E.uf);
  const r = E.rotulo[E.uf];
  $('#balao').innerHTML = r && !r[2] ? `<g class="balao"><rect x="${r[0] - 17}" y="${r[1] - 36}" width="34" height="20" rx="5"/><path d="M${r[0] - 5},${r[1] - 16.5}L${r[0]},${r[1] - 11}L${r[0] + 5},${r[1] - 16.5}Z" fill="#f2f7fd"/><text x="${r[0]}" y="${r[1] - 26}" text-anchor="middle" dominant-baseline="central">${E.uf}</text></g>` : '';
  $('#legenda').innerHTML = legenda();
}
function aplicarVB() { $('#mapa').setAttribute('viewBox', E.vb.map(v => v.toFixed(1)).join(' ')); }
function zoom(f) {
  const [x, y, w, h] = E.vb;
  const nw = Math.max(150, Math.min(660, w * f)), nh = nw * 640 / 660;
  E.vb = [x + (w - nw) / 2, y + (h - nh) / 2, nw, nh];
  if (nw >= 660) E.vb = [0, 0, 660, 640];
  aplicarVB();
}
function ligarMapa() {
  const svg = $('#mapa');
  let arr = null, moveu = false;
  svg.addEventListener('pointerdown', ev => { if (E.vb[2] < 660) { arr = [ev.clientX, ev.clientY, ...E.vb]; moveu = false; } });
  svg.addEventListener('pointermove', ev => {
    if (!arr) return;
    const k = E.vb[2] / svg.getBoundingClientRect().width;
    const dx = ev.clientX - arr[0], dy = ev.clientY - arr[1];
    if (Math.abs(dx) + Math.abs(dy) > 4) moveu = true;
    if (moveu) { E.vb = [arr[2] - dx * k, arr[3] - dy * k, arr[4], arr[5]]; aplicarVB(); }
  });
  window.addEventListener('pointerup', () => { arr = null; });
  svg.addEventListener('click', ev => {
    if (moveu) { moveu = false; return; }
    const alvo = ev.target.closest('[data-uf]');
    if (alvo) escolherUF(alvo.dataset.uf);
  });
  svg.addEventListener('keydown', ev => {
    const alvo = ev.target.closest('.uf');
    if (alvo && (ev.key === 'Enter' || ev.key === ' ')) { ev.preventDefault(); escolherUF(alvo.dataset.uf); }
  });
  $('#zoom-mais').onclick = () => zoom(.72);
  $('#zoom-menos').onclick = () => zoom(1 / .72);
  $('#camada').onchange = ev => { E.camada = ev.target.value; pintarMapa(); };
}

function escolherUF(uf, aba = 'panorama', mun = null) {
  E.uf = uf; E.aba = aba; E.mun = mun;
  pintarMapa();
  painel();
}

/* ---------- painel ---------- */
function trilha() {
  const e = E.d.estados[E.uf];
  const m = E.mun && E.munPorId[E.mun];
  $('#trilha').innerHTML = `<button type="button" data-ir="br">Brasil</button><span aria-hidden="true">/</span>${m
    ? `<button type="button" data-ir="uf">${esc(e.nome)}</button><span aria-hidden="true">/</span><span aria-current="location">${nome(m.n)}</span>`
    : `<span aria-current="location">${esc(e.nome)}</span>`}`;
}
function silhueta(uf) {
  const g = E.d.mapa[uf];
  if (!g) return '';
  const b = E.bbox[uf];
  return `<svg class="silhueta" viewBox="${b.join(' ')}" aria-hidden="true"><path d="${g.d}"/></svg>`;
}
function painel() {
  const e = E.d.estados[E.uf];
  trilha();
  const abas = [['panorama', 'Panorama'], ['municipios', 'Municípios'], ['secoes', 'Seções']];
  const corpo = E.aba === 'municipios' ? (E.mun ? fichaMunicipio() : listaMunicipios()) : E.aba === 'secoes' ? secoesUF() : panorama();
  $('#painel').innerHTML = `
    <div class="painel-rotulo">Estado selecionado</div>
    ${silhueta(E.uf)}
    <div><div class="painel-nome">${esc(e.nome)}</div><div class="painel-sub">${E.uf === 'ZZ' ? 'Seções no exterior' : `${E.uf} · ${e.regiao}`}</div></div>
    <div class="subabas" role="tablist">${abas.map(([k, t]) => `<button type="button" role="tab" data-aba="${k}" aria-selected="${E.aba === k}">${t}</button>`).join('')}</div>
    <div class="painel-corpo" role="tabpanel">${corpo}</div>
    <button class="ir" type="button" data-hash="#fontes">Ver fontes e método ↗</button>`;
}
function linhaRes(rot, l, f) {
  if (l == null) return '';
  const fv = f ?? 0;
  return `<div class="linha-res"><span>${rot}</span><div class="trilho"><i style="width:${l * 100}%;background:var(--lula)"></i><i style="width:${fv * 100}%;background:var(--flavio);margin-left:auto"></i></div><span class="n">${P(l)} × ${f == null ? '—' : P(f)}</span></div>`;
}
function linhaTransf(rot, x) {
  const fx = f => `${P(f[0], 0)}–${P(f[1], 0)}`;
  return `<div style="margin-top:8px"><div class="pequeno"><b>${rot}</b> · ${N(x.n)} eleitores no 1º turno${x.incerta ? ' · <span class="texto-2">estimativa incerta (poucos municípios)</span>' : ''}</div>
    ${linhaRes('', x.lula / x.n, x.flavio / x.n)}
    <div class="pequeno texto-2">Lula ≈ ${N(x.lula)} (${fx(x.lf)}) · Flávio ≈ ${N(x.flavio)} (${fx(x.ff)}) · o resto votou branco/nulo ou não votou</div></div>`;
}
function caixaTransf(e) {
  const t = e.transf;
  if (!t) return `<div class="caixa"><h4>Para onde foram os votos dos eliminados</h4><p class="pequeno texto-2" style="margin:0">Sem estimativa: o método compara municípios dentro do estado, e ${esc(e.nome)} tem poucos.</p></div>`;
  return `<div class="caixa"><h4>Para onde foram os votos dos eliminados <span class="pequeno">(estimativa)</span></h4>
    ${t.direita ? linhaTransf('Renan, Caiado e Zema', t.direita) : ''}
    ${t.elim ? linhaTransf('Todos os eliminados', t.elim) : ''}
    <p class="pequeno texto-2" style="margin:6px 0 0">O voto é secreto: o número é inferido comparando os municípios do estado. A faixa mostra a incerteza. <a href="#analises/segundo_turno">Como é calculado</a></p></div>`;
}
function panorama() {
  const e = E.d.estados[E.uf];
  const muns = E.munsUF[E.uf] || [];
  const conta = a => muns.filter(m => m.a.includes(a)).length;
  const lg = e.logs;
  const sinais = [
    [e.escola, 'seções destoam da própria escola', 'escola'],
    [conta('z_cresc'), 'municípios com eleitorado crescendo fora do padrão', 'crescimento'],
    [e.cad_mun, `municípios com mais eleitores que moradores${e.cad_exc ? ` (${N(e.cad_exc)} além da população)` : ''}`, 'cadastro'],
    [conta('Flávio perdeu votos'), 'municípios onde o Flávio perdeu votos no 2º turno', 'segundo_turno'],
    [conta('Lula perdeu votos'), 'municípios onde o Lula perdeu votos no 2º turno', 'segundo_turno'],
    [conta('Lula ganhou mais que o bolo'), 'municípios onde o Lula ganhou mais que os votos em disputa', 'segundo_turno'],
    [conta('virou desde 2022'), 'municípios que viraram de lado desde 2022', 'viradas'],
    [e.klimek, 'seções com quase 100% de votos num candidato', 'klimek'],
  ];
  const st = id => E.pista[id]?.status;
  return `
    <div class="caixa">
      <span class="selo etapa">AUDITORIA · 1º TURNO</span>
      <h4 style="margin-top:10px">Boletins de urna × totalização</h4>
      <div class="grande"><span class="ponto${e.dif ? ' ambar' : ''}"></span>${N(e.dif)} diferença${e.dif === 1 ? '' : 's'}</div>
      <p class="pequeno texto-2" style="margin:4px 0 0">Conferido voto a voto, seção a seção</p>
      <div class="dois"><div><b>${N(e.secoes)}</b> <span>seções</span></div><div><b>${N(e.bu_reg)}</b> <span>registros</span></div></div>
    </div>
    <div class="caixa">
      <h4>Resultado <span class="pequeno">(<span style="color:var(--lula)">Lula</span> × <span style="color:var(--flavio)">Flávio</span>)</span></h4>
      ${linhaRes('2022', e.sl22, null)}
      ${linhaRes('1º t.', e.sl1, e.sf1)}
      ${linhaRes('2º t.', e.sl2, e.sl2 == null ? null : 1 - e.sl2)}
      <p class="pequeno texto-2" style="margin:6px 0 0">2022: Lula no 1º turno daquele ano. 1º turno 2026 inclui os outros 11 candidatos.</p>
    </div>
    ${caixaTransf(e)}
    <div class="caixa">
      <h4>Pontos para conferir neste estado</h4>
      <ul class="sinais">${sinais.map(([n, t, id]) => `<li><b class="${n ? '' : 'n0'}">${N(n)}</b><span>${t}</span><a href="#analises/${id}" aria-label="Ver análise">${selo(st(id))}</a></li>`).join('')}</ul>
    </div>
    ${lg ? `<div class="caixa">
      <h4>Diário das urnas · amostra do 1º turno</h4>
      <p class="pequeno" style="margin:0 0 6px">${N(lg.urnas)} urnas sorteadas, ${N(lg.votos)} votos</p>
      <ul class="sinais">
        <li><b>${P(lg.manual_pct)}</b><span>votos liberados sem digital (Brasil: 3,8% a 8,3% por estado)</span><a href="#analises/biometria">${selo(st('biometria'))}</a></li>
        <li><b class="${lg.concentrado_fim ? '' : 'n0'}">${N(lg.concentrado_fim)}</b><span>urnas com liberações concentradas no fim do dia</span><a href="#analises/logs">${selo(st('logs'))}</a></li>
        <li><b class="${lg.rapidos_20s ? '' : 'n0'}">${N(lg.rapidos_20s)}</b><span>votos em menos de 20 s após o anterior</span><a href="#analises/logs">${selo(st('logs'))}</a></li>
      </ul></div>` : ''}
    <div>
      <h3 style="margin:4px 0 4px">O que isso significa?</h3>
      <p class="pequeno texto-2" style="margin:0">${e.dif === 0
        ? 'Os boletins impressos pelas urnas deste estado somam exatamente o resultado oficial. Isso descarta alteração na transmissão e na totalização, mas não verifica sozinho o que acontece dentro da urna.'
        : 'Há diferença entre boletins e totalização neste estado. Vale conferir com os boletins impressos.'}
      Os demais números são pontos de atenção: cada um tem uma explicação inocente que foi testada. Clique na etiqueta para ver o teste.</p>
    </div>`;
}
function listaMunicipios() {
  const muns = (E.munsUF[E.uf] || []).filter(m => m.a.length || m.esc).sort((a, b) => (b.a.length + b.esc) - (a.a.length + a.esc) || b.apt - a.apt);
  const total = (E.munsUF[E.uf] || []).length;
  return `<p class="pequeno texto-2" style="margin:0">${N(muns.length)} de ${N(total)} municípios têm algum ponto de atenção. Os demais estão dentro do padrão em todos os testes.</p>
  <input class="filtro-mun" type="search" placeholder="Filtrar municípios" aria-label="Filtrar municípios" style="background:var(--fundo-2);border:1px solid var(--borda-forte);border-radius:8px;padding:7px 10px">
  <ul class="lista-mun">${muns.map(m => `<li data-n="${esc(norm(m.n))}"><button type="button" data-mun="${m.id}"><b>${nome(m.n)}</b><span class="pequeno texto-2">${N(m.apt)} eleitores</span>
    <span class="etiquetas">${m.esc ? `<span class="tag">${m.esc} seç${m.esc > 1 ? 'ões destoam' : 'ão destoa'} da escola</span>` : ''}${m.a.map(a => `<span class="tag${a.startsWith('Flávio') || a.startsWith('Lula') ? ' neutra' : ''}">${esc(ALERTA[a]?.[0] || a)}</span>`).join('')}</span></button></li>`).join('')}</ul>`;
}
function fichaMunicipio() {
  const m = E.munPorId[E.mun];
  const secs = E.d.escola.filter(s => s.id.startsWith(m.id + '-'));
  const kl = E.d.klimek.filter(s => s.id.startsWith(m.id + '-'));
  const mg = E.migrPorId[m.id];
  const cad = E.cadPorId[m.id];
  const vir = E.d.viradas.find(v => v.id === m.id);
  const v2 = m.v2l != null ? m.v2l + m.v2f : null;
  return `<button type="button" class="voltar" data-aba="municipios">← Municípios de ${esc(E.d.estados[E.uf].nome)}</button>
    <div class="painel-nome" style="font-size:24px">${nome(m.n)}</div>
    <div class="caixa"><h4>Lula ao longo do tempo</h4>
      ${linhaRes('2022', m.l22, null)}${linhaRes('1º t.', m.l1, null)}${linhaRes('2º t.', m.l2, m.l2 == null ? null : 1 - m.l2)}
      ${v2 ? `<p class="pequeno texto-2" style="margin:6px 0 0">2º turno: Lula ${N(m.v2l)} × Flávio ${N(m.v2f)}</p>` : ''}</div>
    ${numeros([[N(m.sec), 'seções'], [N(m.apt), 'eleitores aptos'], [P(m.turn), 'comparecimento 1º t.'], [P(m.bio), 'liberação sem digital'], [PP(m.sw), 'Lula desde 2022'], [P(m.cr), 'crescimento dos votos válidos']])}
    ${m.a.length ? `<div class="caixa"><h4>Por que aparece na lista</h4><ul class="sinais">${m.a.map(a => `<li><span class="tag">!</span><span>${esc(ALERTA[a]?.[0] || a)}</span>${ALERTA[a] ? pistaLink(ALERTA[a][1], selo(E.pista[ALERTA[a][1]]?.status)) : ''}</li>`).join('')}</ul></div>` : ''}
    ${cad ? `<div class="caixa destaque"><b>${N(cad.aptos)}</b> eleitores aptos para <b>${N(cad.populacao)}</b> moradores estimados pelo IBGE (${dec(cad.aptos_pop, 2)}×). Comparecimento: ${N(cad.comparecimento)}.</div>` : ''}
    ${mg ? `<div class="caixa"><h4>Entre os turnos</h4><p class="pequeno" style="margin:0">Lula ${N(mg.lula1)} → ${N(mg.lula2)} (${S(mg.lula2 - mg.lula1)}) · Flávio ${N(mg.flavio1)} → ${N(mg.flavio2)} (${S(mg.flavio2 - mg.flavio1)})<br>Votos dos eliminados: ${N(mg.eliminados)} (de direita: ${N(mg.direita)}) · comparecimento ${N(mg.comp1)} → ${N(mg.comp2)}</p></div>` : ''}
    ${vir ? `<div class="caixa"><h4>Virada desde 2022</h4><p class="pequeno" style="margin:0">Variação de ${PP(vir.virada)} para o Lula; ${vir.mesma_direcao} de ${vir.secoes} seções andaram na mesma direção (de ${PP(vir.min)} a ${PP(vir.max)}).</p></div>` : ''}
    ${secs.length ? `<div class="caixa"><h4>Seções que destoam da escola</h4>${secs.map(s => linhaSecao(s)).join('')}</div>` : ''}
    ${kl.length ? `<div class="caixa"><h4>Seções com quase 100% num candidato</h4>${kl.map(s => `<p class="pequeno" style="margin:4px 0">${nome(s.local)} · ${esc(s.candidato)} ${P(s.share_2026, 0)} · ${s.identificados_digital} de ${s.comparecimento} pela digital</p>`).join('')}</div>` : ''}`;
}
function linhaSecao(s) {
  const [, , z, sec] = s.id.split('-');
  return `<div style="border-top:1px solid var(--borda);padding:8px 0;font-size:13px">
    <b>Zona ${z} · seção ${sec}</b> ${s.nova ? '<span class="tag neutra">nova</span>' : '<span class="tag">já existia</span>'}<br>
    <span class="texto-2">${nome(s.local)}</span><br>
    Lula ${N(s.votos_lula)} × Flávio ${N(s.votos_flavio)} · a favor de <b style="color:${s.a_favor === 'Lula' ? 'var(--lula)' : 'var(--flavio)'}">${esc(s.a_favor)}</b> · ${PP(s.res_2026)} contra as vizinhas (z ${Z(s.z)})${s.res_2022 != null ? ` · em 2022: ${PP(s.res_2022)}` : ''}</div>`;
}
function secoesUF() {
  const secs = E.d.escola.filter(s => s.id.startsWith(E.uf + '-'));
  const kl = E.d.klimek.filter(s => s.id.startsWith(E.uf + '-'));
  return `<div class="caixa"><h4>${secs.length} seç${secs.length === 1 ? 'ão destoa' : 'ões destoam'} da própria escola ${selo(E.pista.escola.status)}</h4>
    <p class="pequeno texto-2" style="margin:0 0 4px">Votaram muito diferente das outras seções do mesmo local de votação (z robusto acima de 5 e diferença de 5 pontos ou mais).</p>
    ${secs.length ? secs.sort((a, b) => Math.abs(b.z) - Math.abs(a.z)).map(s => `<p class="pequeno" style="margin:6px 0 0"><b>${nome(s.municipio)}</b></p>${linhaSecao(s)}`).join('') : '<p class="pequeno texto-2">Nenhuma neste estado.</p>'}</div>
    <div class="caixa"><h4>${kl.length} seç${kl.length === 1 ? 'ão' : 'ões'} com quase 100% num candidato ${selo(E.pista.klimek.status)}</h4>
    ${kl.length ? kl.map(s => `<p class="pequeno" style="margin:6px 0"><b>${nome(s.municipio)}</b> · ${nome(s.local)}<br>${esc(s.tipo_local || '')} · ${esc(s.candidato)} ${P(s.share_2026, 0)}, comparecimento ${P(s.turn, 0)} · ${s.identificados_digital} de ${s.comparecimento} pela digital</p>`).join('') : '<p class="pequeno texto-2">Nenhuma neste estado.</p>'}</div>`;
}
document.addEventListener('click', ev => {
  const b = ev.target.closest('[data-aba],[data-mun],[data-hash],[data-ir]');
  if (!b) return;
  if (b.dataset.hash) { location.hash = b.dataset.hash; return; }
  if (b.dataset.ir === 'br') { E.vb = [0, 0, 660, 640]; aplicarVB(); escolherUF(E.uf); return; }
  if (b.dataset.ir === 'uf') { escolherUF(E.uf, 'municipios'); return; }
  if (b.dataset.mun) { E.mun = b.dataset.mun; painel(); $('.painel-corpo').scrollTop = 0; return; }
  if (b.dataset.aba && b.closest('#painel')) { E.aba = b.dataset.aba; E.mun = null; painel(); }
});
document.addEventListener('input', ev => {
  if (!ev.target.matches('.filtro-mun')) return;
  const q = norm(ev.target.value);
  for (const li of $$('.lista-mun li')) li.hidden = !li.dataset.n.includes(q);
});

/* ---------- busca ---------- */
function ligarBusca() {
  const inp = $('#busca'), ul = $('#busca-lista');
  const idx = [
    ...Object.values(E.d.estados).map(e => ({ t: 'uf', id: e.uf, rot: e.nome, sub: e.uf, k: norm(e.nome + ' ' + e.uf) })),
    ...E.d.municipios.map(m => ({ t: 'mun', id: m.id, uf: m.uf, rot: m.n, sub: m.uf, k: norm(m.n) })),
  ];
  let itens = [], ativo = -1;
  const fechar = () => { ul.hidden = true; inp.setAttribute('aria-expanded', 'false'); };
  const escolher = i => {
    const it = itens[i];
    if (!it) return;
    if (it.t === 'uf') escolherUF(it.id); else escolherUF(it.uf, 'municipios', it.id);
    inp.value = ''; fechar();
    $('#painel').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };
  const desenhar = () => {
    ul.innerHTML = itens.map((it, i) => `<li role="option" id="op${i}" aria-selected="${i === ativo}" data-i="${i}">${it.t === 'uf' ? esc(it.rot) : nome(it.rot)}<small>${it.t === 'uf' ? 'estado' : it.sub}</small></li>`).join('') || '<li aria-disabled="true">Nada encontrado</li>';
    ul.hidden = false; inp.setAttribute('aria-expanded', 'true');
    inp.setAttribute('aria-activedescendant', ativo >= 0 ? 'op' + ativo : '');
  };
  inp.setAttribute('role', 'combobox');
  inp.addEventListener('input', () => {
    const q = norm(inp.value.trim());
    if (q.length < 2) { fechar(); return; }
    itens = idx.filter(x => x.k.includes(q)).sort((a, b) => (a.t === 'uf' ? -1 : 0) - (b.t === 'uf' ? -1 : 0) || a.k.indexOf(q) - b.k.indexOf(q)).slice(0, 12);
    ativo = itens.length ? 0 : -1;
    desenhar();
  });
  inp.addEventListener('keydown', ev => {
    if (ul.hidden) return;
    if (ev.key === 'ArrowDown') { ativo = Math.min(itens.length - 1, ativo + 1); desenhar(); ev.preventDefault(); }
    else if (ev.key === 'ArrowUp') { ativo = Math.max(0, ativo - 1); desenhar(); ev.preventDefault(); }
    else if (ev.key === 'Enter') { escolher(ativo); ev.preventDefault(); }
    else if (ev.key === 'Escape') fechar();
  });
  ul.addEventListener('mousedown', ev => { const li = ev.target.closest('[data-i]'); if (li) { ev.preventDefault(); escolher(+li.dataset.i); } });
  inp.addEventListener('blur', () => setTimeout(fechar, 120));
}

/* ---------- entenda ---------- */
const ICONE = {
  doc: '<svg viewBox="0 0 24 24"><path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4M9.5 12h6M9.5 15h6M9.5 18h4"/></svg>',
  barras: '<svg viewBox="0 0 24 24"><path d="M5 20V12M10 20V6M15 20v-9M20 20V9M3 20h19"/></svg>',
  casa: '<svg viewBox="0 0 24 24"><path d="M4 11 12 4l8 7v9H4z"/><path d="M10 20v-5h4v5"/></svg>',
  setas: '<svg viewBox="0 0 24 24"><path d="M4 8h13l-3-3M20 16H7l3 3"/></svg>',
  pessoas: '<svg viewBox="0 0 24 24"><circle cx="9" cy="8" r="3"/><circle cx="17" cy="9" r="2.5"/><path d="M3 20c0-3.5 2.7-6 6-6s6 2.5 6 6M15 14.5c3 0 6 2 6 5.5"/></svg>',
  virada: '<svg viewBox="0 0 24 24"><path d="M20 12a8 8 0 1 1-2.3-5.6M20 4v5h-5"/></svg>',
};
function entenda() {
  const d = E.d;
  const excesso = d.cadastro.reduce((s, c) => s + Math.max(0, c.aptos - c.populacao), 0);
  const cresc = d.municipios.filter(m => m.a.includes('z_cresc')).length;
  const cards = [
    ['escola', 'barras', 'Seções que destoam', `${N(d.escola.length)} seções apontadas para conferir; saldo de ${E.pista.escola.impacto.replace(/\D+/g, ' ').trim()} votos.`],
    ['cadastro', 'pessoas', 'Mais eleitores que moradores', `${N(d.cadastro.length)} municípios, ${N(excesso)} eleitores além da população.`],
    ['segundo_turno', 'setas', 'A virada do 2º turno', `Lula levou ${P(d.migracao.nacional.parcela_lula, 0)} dos votos em disputa; Flávio perdeu votos em ${N(d.migracao.nacional.alertas['Flávio perdeu votos'])} cidades.`],
    ['crescimento', 'casa', 'Eleitorado que cresceu demais', `${N(cresc)} municípios fora do padrão desde 2022.`],
    ['viradas', 'virada', 'Cidades que viraram de lado', `${d.viradas.length} viradas em 2026, contra 0 a 2 nas trocas anteriores.`],
  ];
  if (d.prorrogacao) {
    const b = d.prorrogacao['3221'];
    cards.push(['prorrogacao', 'doc', 'Votação até 19h (Zanin)', `${P(b.apos17h / b.votos, 3)} dos votos depois das 17h; só ${b.urnas_15min} de ${N(b.urnas)} urnas ficaram abertas.`]);
  }
  $('#entenda').innerHTML = cards.map(([id, ic, t, txt]) => `<a class="mini" href="#analises/${id}"><span class="icone">${ICONE[ic]}</span><span><strong>${t}</strong>${selo(E.pista[id].status)}<p>${txt}</p></span><span class="seta" aria-hidden="true">›</span></a>`).join('')
    + `<a class="mini" href="#analises/logs"><span class="icone">${ICONE.doc}</span><span><strong>Diário das urnas · 2 turnos</strong>${selo(E.pista.logs.status)}<p>10.800 urnas sorteadas em cada turno: nenhuma com liberações sem digital em rajada no fim do dia.</p></span><span class="seta" aria-hidden="true">›</span></a>`;
}

/* ---------- análises ---------- */
function vizPista(id) {
  const d = E.d;
  const ufs = Object.values(d.estados);
  switch (id) {
    case 'integridade':
      return numeros([[N(d.gerado.secoes), 'seções conferidas'], [N(d.gerado.registros_bu), 'registros de boletim'], ['0', 'diferenças'], ['28', 'arquivos com SHA-512 conferido']])
        + viz('Por estado', tabela([
          { t: 'UF', k: 'uf' }, { t: 'Seções', k: 'secoes', n: 1, f: r => N(r.secoes) }, { t: 'Registros', k: 'bu_reg', n: 1, f: r => N(r.bu_reg) },
          { t: 'Votos no boletim', k: 'bu_votos', n: 1, f: r => N(r.bu_votos) }, { t: 'Votos na totalização', k: 'tot_votos', n: 1, f: r => N(r.tot_votos) },
          { t: 'Diferenças', k: 'dif', n: 1, f: r => N(r.dif) }], ufs, { ord: 1 }));
    case 'logs': {
      const lu = Object.entries(d.logs3220.por_uf).map(([uf, v]) => ({ uf, ...v }));
      return numeros([['988 / 988', 'logs das seções suspeitas batem com o boletim'], ['10.800', 'urnas sorteadas no 1º turno (400 por estado)'], [N(lu.reduce((s, x) => s + x.concentrado_fim, 0)), 'urnas com liberações concentradas no fim'], [d.logs3221 ? N(Object.values(d.logs3221.por_uf).reduce((s, x) => s + x.concentrado_fim, 0)) : '—', 'idem no 2º turno (mesmas 10.800 urnas)']])
        + viz('Seções suspeitas × amostra aleatória de controle', tabela([
          { t: 'Grupo', k: 'grupo' }, { t: 'Seções', k: 'secoes', n: 1 }, { t: 'Log bate com BU', k: 'log_bate_bu', n: 1, f: r => `${r.log_bate_bu} de ${r.com_log}` },
          { t: 'Liberação sem digital', k: 'manual_pct', n: 1, f: r => P(r.manual_pct) }, { t: 'Intervalo mediano', k: 'intervalo_s', n: 1, f: r => `${N(r.intervalo_s)} s` },
          { t: 'Votos na última hora', k: 'ultima_hora', n: 1, f: r => P(r.ultima_hora) }, { t: 'Padrão “última hora”', k: 'padrao_ultima_hora', n: 1 }], d.logs_grupos))
        + viz('Amostra nacional do 1º turno, por estado', tabela([
          { t: 'UF', k: 'uf' }, { t: 'Urnas', k: 'urnas', n: 1 }, { t: 'Votos', k: 'votos', n: 1, f: r => N(r.votos) },
          { t: 'Sem digital', k: 'manual_pct', n: 1, f: r => P(r.manual_pct) }, { t: '10+ seguidas sem digital', k: 'seq10', n: 1 },
          { t: 'Concentradas no fim', k: 'concentrado_fim', n: 1 }, { t: 'Votos < 20 s', k: 'rapidos_20s', n: 1 },
          { t: 'Votos após 17h', k: 'votos_apos_17h_pct', n: 1, f: r => P(r.votos_apos_17h_pct) }], lu, { ord: 3 }));
    }
    case 'biometria':
      return viz('Efeito da liberação sem digital no voto do Lula, conforme o que entra no modelo', barras(
        d.biometria_modelos.filter(m => m.variavel === 'biom').map(m => ({ rot: esc(m.modelo) + ` <span class="texto-2">(z ${Z(m.z)})</span>`, v: m.coef })), { fmt: v => PP(v) }))
        + '<p class="pequeno texto-2">Quando a idade entra na conta, o efeito praticamente some: a digital falha mais em idosos, e eles votam diferente.</p>'
        + viz('Por faixa de liberação sem digital: diferença para as vizinhas', tabela([
          { t: 'Faixa', k: 'faixa' }, { t: 'Seções', k: 'secoes', n: 1, f: r => N(r.secoes) }, { t: '2022', k: 'res_2022', n: 1, f: r => PP(r.res_2022, 2) },
          { t: '2026', k: 'res_2026', n: 1, f: r => PP(r.res_2026, 2) }, { t: 'Mudança', k: 'mudanca', n: 1, f: r => PP(r.mudanca, 2) }], d.biometria_faixas));
    case 'klimek':
      return viz(`${d.klimek.length} seções`, tabela([
        { t: 'UF', k: 'uf' }, { t: 'Município', k: 'municipio', f: r => nome(r.municipio) }, { t: 'Local', k: 'local', f: r => nome(r.local) }, { t: 'Tipo', k: 'tipo_local' },
        { t: 'Candidato', k: 'candidato' }, { t: 'Comparec.', k: 'turn', n: 1, f: r => P(r.turn, 0) }, { t: 'Votos 2026', k: 'share_2026', n: 1, f: r => P(r.share_2026, 0) },
        { t: 'Em 2022', k: 'share_2022', n: 1, f: r => P(r.share_2022, 0) }, { t: 'Pela digital', k: 'identificados_digital', n: 1, f: r => `${r.identificados_digital}/${r.comparecimento}` }],
        d.klimek.map(r => ({ ...r, uf: r.id.split('-')[0] })), { uf: 1, ord: 6 }));
    case 'escola': {
      const lula = d.escola.filter(s => s.a_favor === 'Lula').length;
      const novas = d.escola.filter(s => s.nova).length;
      return numeros([[N(d.escola.length), `de ${N(d.gerado.secoes_testaveis_escola)} seções testáveis`], [`${lula} × ${d.escola.length - lula}`, 'a favor do Lula × do Flávio'], [N(novas), 'são seções novas (não existiam em 2022)'], ['3.460', 'votos de saldo, no total']])
        + viz('Todas as seções apontadas', tabela([
          { t: 'UF', k: 'uf' }, { t: 'Município', k: 'municipio', f: r => nome(r.municipio) }, { t: 'Local', k: 'local', f: r => nome(r.local) },
          { t: 'Zona/seção', k: 'id', f: r => r.id.split('-').slice(2).join('/') }, { t: 'A favor', k: 'a_favor', f: r => `<b style="color:${r.a_favor === 'Lula' ? 'var(--lula)' : 'var(--flavio)'}">${r.a_favor}</b>` },
          { t: 'z', k: 'z', n: 1, v: r => Math.abs(r.z), f: r => Z(r.z) }, { t: 'Nova?', k: 'nova', f: r => (r.nova ? 'sim' : 'não') },
          { t: 'vs vizinhas 2026', k: 'res_2026', n: 1, f: r => PP(r.res_2026) }, { t: 'em 2022', k: 'res_2022', n: 1, f: r => PP(r.res_2022) },
          { t: 'Lula', k: 'votos_lula', n: 1 }, { t: 'Flávio', k: 'votos_flavio', n: 1 }, { t: 'Sem digital', k: 'log_manual', n: 1 }],
          d.escola.map(r => ({ ...r, uf: r.id.split('-')[0] })), { uf: 1, ord: 5 }));
    }
    case 'viradas':
      return viz('Municípios que trocaram de vencedor, por eleição', colunas(d.viradas_base.map(v => ({ rot: v.periodo, v: v.municipios, cor: v.periodo.endsWith('2026') ? 'var(--ambar)' : 'var(--ciano)' })), { fmt: N }))
        + viz('As viradas de 2026', tabela([
          { t: 'UF', k: 'uf' }, { t: 'Município', k: 'municipio', f: r => nome(r.municipio) }, { t: 'Variação do Lula', k: 'virada', n: 1, f: r => PP(r.virada) },
          { t: 'Seções na mesma direção', k: 'mesma_direcao', n: 1, f: r => `${r.mesma_direcao} de ${r.secoes}` }, { t: 'Faixa', k: 'min', f: r => `${PP(r.min)} a ${PP(r.max)}` }], d.viradas))
        + viz('Candidatos locais muito acima do estado', tabela([
          { t: 'UF', k: 'uf' }, { t: 'Município', k: 'municipio', f: r => nome(r.municipio) }, { t: 'Cargo', k: 'cargo' }, { t: 'Candidato', k: 'candidato', f: r => nome(r.candidato) },
          { t: 'Partido', k: 'partido' }, { t: 'Na cidade', k: 'share_cidade', n: 1, f: r => P(r.share_cidade) }, { t: 'No estado', k: 'share_estado', n: 1, f: r => P(r.share_estado) }], d.lideres));
    case 'crescimento':
      return viz('Municípios fora do padrão', tabela([
        { t: 'UF', k: 'uf' }, { t: 'Município', k: 'n', f: r => nome(r.n) }, { t: 'Eleitores', k: 'apt', n: 1, f: r => N(r.apt) },
        { t: 'Crescimento dos válidos', k: 'cr', n: 1, f: r => P(r.cr) }, { t: 'z', k: 'zc', n: 1, f: r => Z(r.zc) },
        { t: 'Comparecimento', k: 'turn', n: 1, f: r => P(r.turn) }, { t: 'Sem digital', k: 'bio', n: 1, f: r => P(r.bio) }],
        d.municipios.filter(m => m.a.includes('z_cresc') || m.a.includes('z_turn')), { ord: 4 }));
    case 'prorrogacao': {
      const pr = d.prorrogacao, a = pr['3220'], b = pr['3221'];
      return numeros([[N(b.apos17h), `votos depois das 17h, de ${N(b.votos)} na amostra do 2º turno`], [P(b.apos17h / b.votos, 3), 'dos votos do 2º turno (1º turno: ' + P(a.apos17h / a.votos, 2) + ')'], [`${N(b.urnas_15min)} de ${N(b.urnas)}`, 'urnas votaram 15+ min além das 17h'], ['≈ 39 mil', `votos no máximo, no país (margem: ${N(d.turno2.margem)})`]])
        + viz('Votos computados depois das 17h, mesmas 10.800 urnas', colunas([
          { rot: '1º turno<br><small>sem prorrogação</small>', v: a.apos17h / a.votos, cor: 'var(--cinza)' },
          { rot: '2º turno<br><small>liminar até 19h</small>', v: b.apos17h / b.votos, cor: 'var(--ambar)' }], { fmt: v => P(v, 2) }))
        + viz('Margem do Lula × teto de votos após as 17h', barras([
          { rot: 'Margem do Lula', v: d.turno2.margem, cor: 'var(--lula)' },
          { rot: 'Teto de votos tardios', v: 39434, cor: 'var(--ambar)' }], { fmt: N }));
    }
    case 'horarios':
      return viz('Registros de processo', tabela([{ t: 'Ocorrência', k: 'problema' }, { t: 'Seções', k: 'secoes', n: 1, f: r => N(r.secoes) }], d.problemas));
    case 'ultimo_digito':
      return viz('Excesso de finais 0 e 5 nos votos do Flávio, por estado (z; alarme acima de 5)', barras(
        ufs.filter(e => e.z05 != null).sort((a, b) => b.z05 - a.z05).map(e => ({ rot: e.uf, v: e.z05 })), { sinal: true }));
    case 'estados':
      return viz('Distância de cada estado do padrão nacional, 2022 → 2026 (z; alarme acima de 5)', barras(
        ufs.filter(e => e.z_sw != null).sort((a, b) => b.z_sw - a.z_sw).map(e => ({ rot: `${e.uf} <span class="texto-2">${PP(e.sw)}</span>`, v: e.z_sw })), { sinal: true }));
    case 'benford':
      return numeros([['13%', 'dos testes com desvio no papel (1994)'], ['12%', 'dos testes com desvio na urna (2002–2026)']])
        + viz('Testes por estado com desvio, por eleição (só os que passaram no teste de forma)', colunas(d.benford_ano.map(a => ({ rot: `${a.ano}<br><small>${a.meio}</small>`, v: a.desvios / a.testes, cor: a.meio === 'urna' ? 'var(--ciano)' : 'var(--ambar)' })), { fmt: v => P(v, 0) }));
    case 'segundo_turno':
      return viz('Parcela do Lula nos votos em disputa, conforme quanto dos votos em jogo era de direita', barras(
        d.migracao.faixas.map(f => ({ rot: `${f.direita_no_bolo} <span class="texto-2">(${N(f.municipios)} mun.)</span>`, v: f.parcela_lula, cor: 'var(--lula)' })), { fmt: v => P(v, 0) }))
        + `<p><a class="botao-contorno" style="text-decoration:none;display:inline-block;color:var(--texto)" href="#turnos">Ver a comparação completa entre os turnos →</a></p>`;
    case 'cadastro': {
      const a = d.realidade.acima;
      return numeros([[N(a.municipios), 'municípios com mais eleitores que moradores'], [N(a.aptos - a.populacao), 'eleitores além da população'], ['708.713', 'votos no pior caso possível'], [N(d.turno2.margem), 'margem do Lula no 2º turno']])
        + viz('Municípios (IBGE 2025 × eleitorado TSE)', tabela([
          { t: 'UF', k: 'uf' }, { t: 'Município', k: 'municipio', f: r => nome(r.municipio) }, { t: 'Moradores', k: 'populacao', n: 1, f: r => N(r.populacao) },
          { t: 'Eleitores', k: 'aptos', n: 1, f: r => N(r.aptos) }, { t: 'Eleitores / moradores', k: 'aptos_pop', n: 1, f: r => dec(r.aptos_pop, 2) + '×' },
          { t: 'Votantes / moradores', k: 'comp_pop', n: 1, f: r => dec(r.comp_pop, 2) + '×' }, { t: 'Lula 2º t.', k: 'lula', n: 1, f: r => N(r.lula) }, { t: 'Flávio 2º t.', k: 'flavio', n: 1, f: r => N(r.flavio) }],
          d.cadastro, { uf: 1, ord: 4 }));
    }
    default: return '';
  }
}
function analises() {
  const lista = [...E.d.pistas].sort((a, b) => ORDEM_STATUS[a.status] - ORDEM_STATUS[b.status] || a.ordem - b.ordem);
  const grupos = [['todas', 'Todas'], ['aberta', 'Em aberto'], ['explicada', 'Explicadas'], ['sem-sinal', 'Sem sinal'], ['fora', 'Fora do alcance']];
  const cls = p => STATUS[p.status]?.[0] || 'fora';
  $('#filtros').innerHTML = grupos.map(([k, t]) => `<button type="button" data-filtro="${k}" aria-pressed="${k === 'todas'}">${t} (${k === 'todas' ? lista.length : lista.filter(p => cls(p) === k).length})</button>`).join('');
  $('#analises-lista').innerHTML = lista.map(cartaoAnalise).join('');
  $('#filtros').addEventListener('click', ev => {
    const b = ev.target.closest('[data-filtro]');
    if (!b) return;
    $$('[data-filtro]').forEach(x => x.setAttribute('aria-pressed', x === b));
    $$('.pista').forEach(p => { p.hidden = b.dataset.filtro !== 'todas' && p.dataset.classe !== b.dataset.filtro; });
  });
  $('#analises-lista').addEventListener('toggle', ev => {
    const alvo = ev.target;
    if (!alvo.open) return;
    const lugar = alvo.classList.contains('tecnico') ? alvo.querySelector('.viz-tec') : alvo.querySelector(':scope > .pista-corpo > .viz-simples');
    if (!lugar || lugar.dataset.ok) return;
    lugar.innerHTML = lugar.classList.contains('viz-tec') ? vizPista(lugar.dataset.viz) : vizSimples(lugar.dataset.viz);
    lugar.dataset.ok = 1;
  }, true);
}

/* ---------- turnos ---------- */
function turnos() {
  const d = E.d, b = d.balanco, mn = d.migracao.nacional;
  const linhas = [['Eleitores aptos', b.aptos], ['Comparecimento', b.comparecimento], ['Lula', b.lula], ['Flávio', b.flavio], ['Brancos e nulos', b.bn]];
  const porUF = Object.values(d.estados).filter(e => e.mig).map(e => ({ uf: e.uf, sl1: e.sl1, sl2: e.sl2, ...e.mig }));
  const p = E.pista.segundo_turno;
  const ps = SIMPLES.segundo_turno;
  $('#turnos-conteudo').innerHTML = `
    <div class="cartao bloco">
      <p class="resposta r-ok" style="font-size:17px"><b>Resposta curta:</b> ${esc(ps.resposta)}</p>
      ${vizSegundoTurno(false)}
      <div class="conferido"><b>✓ O que conferimos depois</b><p>${esc(ps.conferimos)}</p></div>
      <p class="pequeno texto-2">Situação: ${selo(p.status)} · <a href="#analises/segundo_turno">ver a análise completa</a></p>
    </div>
    <div class="cartao bloco"><h2>Balanço 1º → 2º turno</h2>
      <div class="tabela-rola" style="margin-top:10px"><table><thead><tr><th></th><th class="n">1º turno</th><th class="n">2º turno</th><th class="n">Diferença</th></tr></thead><tbody>
      ${linhas.map(([t, [a, c]]) => `<tr><td>${t}</td><td class="n">${N(a)}</td><td class="n">${N(c)}</td><td class="n">${S(c - a)}</td></tr>`).join('')}</tbody></table></div>
      ${viz('Votos dos candidatos eliminados no 1º turno', barras(b.eliminados.map(([n, v]) => ({ rot: n, v, cor: 'var(--cinza)' })), { fmt: N }))}
    </div>
    <div class="cartao bloco"><h2>O voto da direita eliminada</h2>
      <p class="texto-2">Se os eleitores escolhem, a parcela do Lula deve cair onde os eliminados eram mais de direita (Caiado, Renan, Zema). É o que acontece:</p>
      ${barras(d.migracao.faixas.map(f => ({ rot: `${f.direita_no_bolo} de direita <span class="texto-2">(${N(f.municipios)})</span>`, v: f.parcela_lula, cor: 'var(--lula)' })), { fmt: v => P(v, 0) })}
      ${viz('Para onde foi cada eleitorado (estimativa; cada linha soma 100%)', tabela([
        { t: 'Eleitores de', k: 'origem' }, { t: 'Votos no 1º t.', k: 'votos_1t', n: 1, f: r => N(r.votos_1t) },
        ...[['lula', 'Lula'], ['flavio', 'Flávio'], ['bn', 'Branco/nulo'], ['abst', 'Não votou']].map(([k, t]) => (
          { t: 'Para ' + (k === 'lula' || k === 'flavio' ? 'o ' : '') + t, k, n: 1,
            f: r => `${P(r[k], 0)} <span class="texto-2">(${P(r[k + '_faixa'][0], 0)}–${P(r[k + '_faixa'][1], 0)})</span>` }))], d.matriz))}
      <p class="pequeno texto-2">O voto é secreto: o número é inferido comparando municípios do mesmo estado. Cada grupo do 1º turno é dividido entre os quatro destinos, sem passar de 100% nem ficar abaixo de 0%. A faixa junta o intervalo de 95% e uma segunda versão do modelo. No 2º turno de 2026 o modelo acerta a margem final com erro de 26 mil votos; em 2022, a mesma conta feita por município e por seção difere em ~2 pontos.</p>
    </div>
    <div class="cartao bloco"><h2>Para onde foram os eleitores de Renan, Caiado e Zema, por estado</h2>
      <p class="texto-2">Estimativa: cada grupo do 1º turno é dividido entre Lula, Flávio, branco/nulo e quem não votou, comparando os municípios do mesmo estado. A faixa junta o intervalo de 95% e uma segunda versão do modelo. Faixas largas (estados com poucos municípios) são só indicação.</p>
      ${tabela([
        { t: 'UF', k: 'uf' }, { t: 'Eleitores no 1º t.', k: 'n', n: 1, f: r => N(r.n) },
        { t: 'Para o Lula', k: 'lula', n: 1, f: r => `${N(r.lula)} <span class="texto-2">(${P(r.lf[0], 0)}–${P(r.lf[1], 0)})</span>` },
        { t: 'Para o Flávio', k: 'flavio', n: 1, f: r => `${N(r.flavio)} <span class="texto-2">(${P(r.ff[0], 0)}–${P(r.ff[1], 0)})</span>` },
        { t: 'Saldo do Flávio', k: 'saldo', n: 1, f: r => S(r.saldo) },
        { t: 'Confiança', k: 'incerta', f: r => r.incerta ? 'baixa' : 'boa' }],
        Object.values(d.estados).filter(e => e.transf?.direita).map(e => ({ uf: e.uf, ...e.transf.direita, saldo: e.transf.direita.flavio - e.transf.direita.lula })),
        { ord: 1 })}
      <p class="pequeno texto-2">DF fica de fora: é um município só, e o método precisa comparar vários.</p>
    </div>
    <div class="cartao bloco"><h2>Por estado</h2>
      ${tabela([
        { t: 'UF', k: 'uf' }, { t: 'Lula 1º t.', k: 'sl1', n: 1, f: r => P(r.sl1) }, { t: 'Lula 2º t.', k: 'sl2', n: 1, f: r => P(r.sl2) },
        { t: 'Ganho do Lula', k: 'ganho_lula', n: 1, f: r => S(r.ganho_lula) }, { t: 'Ganho do Flávio', k: 'ganho_flavio', n: 1, f: r => S(r.ganho_flavio) },
        { t: 'Eliminados', k: 'eliminados', n: 1, f: r => N(r.eliminados) }, { t: 'Δ comparecimento', k: 'dcomp', n: 1, f: r => S(r.dcomp) }], porUF, { ord: 3 })}
    </div>
    <div class="cartao bloco"><h2>Municípios com o padrão estranho</h2>
      ${numeros(Object.entries(mn.alertas).map(([k, v]) => [N(v), esc(ALERTA[k]?.[0] || k)]))}
      <p class="texto-2 pequeno">“Flávio perdeu votos” e “Lula perdeu votos”: o candidato teve menos votos no 2º turno do que no 1º. “Lula ganhou mais que os votos em disputa”: o ganho dele supera a soma de eliminados, brancos e nulos que sobraram e novos votantes do município.</p>
      ${tabela([
        { t: 'UF', k: 'uf' }, { t: 'Município', k: 'municipio', f: r => nome(r.municipio) }, { t: 'Alertas', k: 'alertas' },
        { t: 'Lula', k: 'lula2', n: 1, v: r => r.lula2 - r.lula1, f: r => `${N(r.lula1)} → ${N(r.lula2)}` },
        { t: 'Flávio', k: 'flavio2', n: 1, v: r => r.flavio2 - r.flavio1, f: r => `${N(r.flavio1)} → ${N(r.flavio2)}` },
        { t: 'Eliminados', k: 'eliminados', n: 1, f: r => N(r.eliminados) }, { t: 'Δ comparecimento', k: 'dturn', n: 1, f: r => PP(r.dturn) }],
        d.migracao_mun, { uf: 1, ord: 4, dir: 1 })}
    </div>`;
}

/* ---------- fontes ---------- */
function fontes() {
  const d = E.d;
  $('#fontes-conteudo').innerHTML = `
    <div class="cartao bloco"><h2>Regras que seguimos</h2>
      <ol class="regras">
        <li><b>Nenhum sinal vira acusação sem enfrentar uma explicação inocente testável.</b> Por isso cada análise mostra as duas hipóteses lado a lado.</li>
        <li><b>Alerta exige ser improvável e grande ao mesmo tempo:</b> z robusto acima de 5 e diferença de pelo menos 5 pontos. Com milhares de comparações, z alto sozinho aparece por acaso.</li>
        <li><b>Toda medida tem controle:</b> a mesma conta em 2022, as vizinhas da mesma escola, ou uma amostra aleatória de urnas.</li>
        <li><b>Lei de Benford só no total por município</b> e só quando a forma dos dados permite (teste de Fourier). Em votos por seção ela não se aplica.</li>
        <li><b>Estatística aponta onde olhar; não prova nada.</b> A prova é o boletim de urna impresso e assinado conferido contra a totalização, o que foi feito para as 499.206 seções do 1º turno.</li>
      </ol>
    </div>
    <div class="cartao bloco"><h2>Recorte</h2>
      <p>1º turno: arquivos definitivos de boletim de urna, votação por seção e logs. 2º turno: API oficial de divulgação, ${N(d.turno2.secoes)} seções, 100% totalizado em ${esc(d.turno2.hora)}. População: estimativas IBGE 2025. Mapa: malha do IBGE.</p>
      <p class="texto-2 pequeno">Gerado por <code>site/gerar_dados.py</code> a partir de <code>dados/derivados/dossie/</code> e <code>resultados/</code>.</p>
    </div>
    <div class="cartao bloco"><h2>Arquivos baixados do TSE</h2>
      ${tabela([{ t: 'Arquivo', k: 'arquivo', f: r => `<a href="${esc(r.url)}" rel="noopener">${esc(r.arquivo)}</a>` }, { t: 'Conteúdo', k: 'tipo' }, { t: 'SHA-512', k: 'sha512', f: r => `<span class="hash" title="${esc(r.sha512)}">${esc((r.sha512 || '').slice(0, 24))}…</span>` }], d.fontes, { lim: 100 })}
    </div>`;
}

/* ---------- rotas ---------- */
function rota() {
  const [pg, sub] = (location.hash.slice(1) || 'visao').split('/');
  const pag = ['visao', 'turnos', 'analises', 'fontes'].includes(pg) ? pg : 'visao';
  $$('.pagina').forEach(s => { s.hidden = s.id !== pag; });
  $$('.abas a').forEach(a => (a.dataset.rota === pag ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current')));
  if (!E.feitas.has(pag)) {
    E.feitas.add(pag);
    ({ turnos, analises, fontes })[pag]?.();
  }
  if (pag === 'analises' && sub) {
    const el = document.getElementById('p-' + sub);
    if (el) {
      $$('[data-filtro]').forEach(x => x.setAttribute('aria-pressed', x.dataset.filtro === 'todas'));
      $$('.pista').forEach(p => { p.hidden = false; });
      el.open = true;
      requestAnimationFrame(() => el.scrollIntoView({ behavior: 'smooth', block: 'start' }));
      return;
    }
  }
  window.scrollTo(0, 0);
}

async function iniciar() {
  const r = await fetch('dados/site.json');
  E.d = await r.json();
  const d = E.d;
  E.pista = Object.fromEntries(d.pistas.map(p => [p.id, p]));
  E.munPorId = Object.fromEntries(d.municipios.map(m => [m.id, m]));
  E.munsUF = {};
  for (const m of d.municipios) (E.munsUF[m.uf] ||= []).push(m);
  E.migrPorId = Object.fromEntries(d.migracao_mun.map(m => [m.id, m]));
  E.cadPorId = Object.fromEntries(d.cadastro.map(c => [c.id, c]));
  E.migrUF = {};
  E.migrUFL = {};
  for (const m of d.municipios) {
    if (m.a.includes('Flávio perdeu votos')) E.migrUF[m.uf] = (E.migrUF[m.uf] || 0) + 1;
    if (m.a.includes('Lula perdeu votos')) E.migrUFL[m.uf] = (E.migrUFL[m.uf] || 0) + 1;
  }
  E.bbox = {};
  for (const [uf, g] of Object.entries(d.mapa)) {
    const xs = [], ys = [];
    for (const [, x, y] of g.d.matchAll(/(-?[\d.]+),(-?[\d.]+)/g)) { xs.push(+x); ys.push(+y); }
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const s = Math.max(x1 - x0, y1 - y0);
    E.bbox[uf] = [x0 - (s - (x1 - x0)) / 2, y0 - (s - (y1 - y0)) / 2, s, s].map(v => +v.toFixed(1));
  }
  $$('.n-pistas').forEach(el => { el.textContent = d.pistas.length; });
  $('#rodape-texto').textContent = `Fonte: arquivos públicos do TSE e do IBGE • 2º turno 100% totalizado em ${d.turno2.hora} (BRT)`;
  placar();
  desenharMapa();
  ligarMapa();
  ligarBusca();
  escolherUF('CE');
  entenda();
  $('#abrir-sobre').onclick = () => $('#sobre').showModal();
  window.addEventListener('hashchange', rota);
  rota();
}
iniciar().catch(err => {
  document.querySelector('main').insertAdjacentHTML('afterbegin', `<p class="cartao bloco">Não foi possível carregar os dados (${esc(err.message)}). Sirva a pasta <code>site/</code> por HTTP: <code>python3 -m http.server -d site</code>.</p>`);
});
