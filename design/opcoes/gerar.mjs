// Three visual directions for Sonar's main screen, same real content, different look and motion.
//   node gerar.mjs   → 1-instrumento.html, 2-editorial.html, 3-acolhedor.html
import { writeFileSync } from "node:fs";

import { D } from "./dados.mjs";

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

// Shared structure: only the score visual changes per direction.
function corpo(notaVisual) {
  const lista = D.vagas
    .map(
      (v, i) => `<li class="item${i === 0 ? " ativo nova" : ""}" style="--i:${i}">
  <span class="nota-mini" data-num="${v.nota}">${v.nota}</span>
  <span class="item-txt"><b>${esc(v.titulo)}</b><small>${esc(v.empresa)} · ${v.modo} · ${v.fonte}</small></span>
  <span class="conf" title="Confiança">${v.conf}</span>
</li>`,
    )
    .join("");
  const fortes = D.fortes
    .map(
      (f, i) => `<li class="ponto" style="--i:${i}"><b>${esc(f.t)}</b>
  <span class="cita"><em>Vaga</em> “${esc(f.vaga)}”</span>
  <span class="cita"><em>Você</em> “${esc(f.cv)}”</span></li>`,
    )
    .join("");
  const lacunas = D.lacunas.map((f) => `<li class="ponto lacuna"><b>${esc(f.t)}</b><span class="cita"><em>Vaga</em> “${esc(f.vaga)}”</span></li>`).join("");
  const sinais = D.sinais.map((s) => `<li>${esc(s)}</li>`).join("");
  const v = D.vagas[0];
  return `<header class="topo">
  <div class="marca"><span class="logo"></span>Sonar</div>
  <div class="perfil">${esc(D.perfil)}</div>
  <div class="placar"><span><b data-num="3119">${D.lidas}</b> vagas lidas hoje</span><span><b data-num="541">${D.escondidas}</b> escondidas por parecerem fantasma</span></div>
</header>
<main class="tela">
  <section class="lista">
    <h2>Para você hoje</h2>
    <ul>${lista}</ul>
    <aside class="fantasma">
      <p class="rotulo">Escondida</p>
      <p><b>${esc(D.fantasma.titulo)}</b> · ${esc(D.fantasma.empresa)}</p>
      <p class="motivo">${esc(D.fantasma.motivo)}</p>
    </aside>
  </section>
  <section class="detalhe">
    <div class="cabeca">
      <div>
        <p class="empresa">${esc(v.empresa)} · ${v.modo}</p>
        <h1>${esc(v.titulo)}</h1>
        <p class="resumo">${esc(D.resumo)}</p>
      </div>
      ${notaVisual(v.nota)}
    </div>
    <h3>Por que encaixa</h3><ul class="pontos">${fortes}</ul>
    <h3>O que falta</h3><ul class="pontos">${lacunas}</ul>
    <h3>Confiança ${v.conf}</h3><ul class="sinais">${sinais}</ul>
    <div class="acoes"><a class="primario">Abrir a vaga</a><a class="secundario">Escrever minha mensagem</a></div>
  </section>
</main>`;
}

const BASE = `*{box-sizing:border-box;margin:0;padding:0} ul{list-style:none} a{cursor:pointer;text-decoration:none}
body{min-height:100vh;-webkit-font-smoothing:antialiased}
.topo{display:grid;grid-template-columns:auto 1fr auto;gap:28px;align-items:center;padding:20px 48px}
.marca{display:flex;align-items:center;gap:10px;font-weight:700;font-size:20px;letter-spacing:-.01em}
.placar{display:flex;gap:24px;font-size:13px}
.tela{display:grid;grid-template-columns:minmax(360px,1fr) 1.35fr;gap:40px;padding:28px 48px 48px;max-width:1440px}
.lista h2{font-size:13px;letter-spacing:.12em;text-transform:uppercase;margin-bottom:14px}
.item{display:grid;grid-template-columns:52px 1fr auto;gap:14px;align-items:center;padding:14px 16px;margin-bottom:8px;cursor:pointer}
.item-txt{display:flex;flex-direction:column;gap:3px;min-width:0} .item-txt b{font-weight:600;font-size:15px;line-height:1.3} .item-txt small{font-size:12.5px}
.fantasma{margin-top:22px;padding:14px 16px;font-size:13.5px;line-height:1.5} .rotulo{font-size:11px;letter-spacing:.14em;text-transform:uppercase;margin-bottom:4px}
.cabeca{display:grid;grid-template-columns:1fr auto;gap:28px;align-items:start}
.empresa{font-size:13px;letter-spacing:.06em;text-transform:uppercase} h1{margin:6px 0 12px;line-height:1.15}
.resumo{font-size:17px;line-height:1.55;max-width:56ch}
h3{font-size:12px;letter-spacing:.14em;text-transform:uppercase;margin:30px 0 12px}
.ponto{display:grid;gap:4px;padding:12px 0} .ponto b{font-weight:600}
.cita{font-size:13.5px;line-height:1.45} .cita em{font-style:normal;font-size:11px;letter-spacing:.1em;text-transform:uppercase;margin-right:8px}
.sinais{display:flex;flex-wrap:wrap;gap:8px} .sinais li{font-size:13px;padding:6px 12px}
.acoes{display:flex;gap:12px;margin-top:30px} .acoes a{padding:13px 22px;font-weight:600;font-size:15px}
@keyframes subir{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
.item,.ponto{animation:subir .6s cubic-bezier(.2,.8,.2,1) both;animation-delay:calc(var(--i)*90ms + 150ms)}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}`;

const CONTAR = `<script>
// Numbers count up once, like an instrument settling on a reading.
for (const el of document.querySelectorAll("[data-num]")) {
  const alvo = +el.dataset.num, ini = performance.now(), dur = 1100;
  const fmt = (n) => n.toLocaleString("pt-BR");
  const passo = (t) => { const k = Math.min(1, (t - ini) / dur), e = 1 - Math.pow(1 - k, 3);
    el.textContent = fmt(Math.round(alvo * e)); if (k < 1) requestAnimationFrame(passo); };
  requestAnimationFrame(passo);
}
</script>`;

const DIRECOES = {
  "1-instrumento": {
    fontes: "family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700",
    css: `:root{--fundo:#07131a;--painel:#0c1d26;--linha:#163240;--texto:#d7e7ee;--apagado:#7f9aa6;--sinal:#3ef0c0;--sinal-suave:rgba(62,240,192,.12);--alerta:#ff8a5c}
body{background:radial-gradient(1200px 600px at 70% -10%,#0f2a36 0,transparent 60%),var(--fundo);color:var(--texto);font-family:"Space Grotesk",sans-serif}
.topo{border-bottom:1px solid var(--linha)} .perfil{color:var(--apagado);font-size:14px}
.logo{width:22px;height:22px;border-radius:50%;border:2px solid var(--sinal);position:relative;box-shadow:0 0 12px var(--sinal-suave)}
.logo::after{content:"";position:absolute;inset:-7px;border-radius:50%;border:1px solid var(--sinal);opacity:0;animation:ping 2.4s ease-out infinite}
@keyframes ping{0%{transform:scale(.6);opacity:.8}100%{transform:scale(1.5);opacity:0}}
.placar{color:var(--apagado)} .placar b{color:var(--texto);font-family:"JetBrains Mono"}
.lista h2,h3,.rotulo,.cita em{color:var(--apagado)}
.item{background:var(--painel);border:1px solid var(--linha);border-radius:12px;transition:border-color .2s,transform .2s}
.item:hover{border-color:#24506a;transform:translateX(3px)} .item.ativo{border-color:var(--sinal);box-shadow:0 0 0 1px var(--sinal) inset,0 0 24px -8px var(--sinal)}
.nota-mini{font:700 20px "JetBrains Mono";color:var(--sinal)} .item-txt small{color:var(--apagado)}
.conf{font:500 12px "JetBrains Mono";color:var(--apagado);border:1px solid var(--linha);border-radius:6px;padding:3px 7px}
.fantasma{border:1px dashed #3a2a24;border-radius:12px;color:var(--apagado)} .fantasma .rotulo{color:var(--alerta)} .fantasma b{color:var(--texto);text-decoration:line-through;text-decoration-color:var(--alerta)}
.detalhe{background:var(--painel);border:1px solid var(--linha);border-radius:18px;padding:30px 32px}
.empresa{color:var(--sinal);font-family:"JetBrains Mono"} h1{font-size:30px;font-weight:600;letter-spacing:-.01em}
.resumo{color:#b8cdd6} .ponto{border-top:1px solid var(--linha)} .cita{color:#a9c0ca}
.lacuna b{color:var(--alerta)} .sinais li{border:1px solid var(--linha);border-radius:999px;color:#b8cdd6} .sinais li::before{content:"● ";color:var(--sinal)}
.primario{background:var(--sinal);color:#05211a;border-radius:10px} .secundario{border:1px solid var(--linha);border-radius:10px;color:var(--texto)}
.radar{position:relative;width:150px;height:150px;border-radius:50%;display:grid;place-items:center;background:radial-gradient(circle,transparent 46%,var(--linha) 47%,transparent 48%,transparent 70%,var(--linha) 71%,transparent 72%)}
.radar::before{content:"";position:absolute;inset:0;border-radius:50%;background:conic-gradient(from 0deg,var(--sinal-suave),transparent 25%);animation:girar 3.2s linear infinite}
@keyframes girar{to{transform:rotate(360deg)}}
.radar b{position:relative;font:700 44px "JetBrains Mono";color:var(--sinal);text-shadow:0 0 18px rgba(62,240,192,.45)} .radar small{position:absolute;bottom:26px;font-size:11px;letter-spacing:.14em;color:var(--apagado)}`,
    nota: (n) => `<div class="radar"><b data-num="${n}">${n}</b><small>ENCAIXE</small></div>`,
  },
  "2-editorial": {
    fontes: "family=Instrument+Serif:ital@0;1&family=Geist:wght@400;500;600;700",
    css: `:root{--papel:#f7f6f2;--tinta:#111;--apagado:#6d6a63;--linha:#dcd8cf;--sinal:#ff4f1f}
body{background:var(--papel);color:var(--tinta);font-family:Geist,sans-serif}
.topo{border-bottom:1px solid var(--tinta)} .marca{font:400 30px "Instrument Serif";letter-spacing:0} .logo{width:10px;height:10px;background:var(--sinal);border-radius:50%}
.perfil{font-size:14px;color:var(--apagado)} .placar{color:var(--apagado)} .placar b{color:var(--tinta);font-variant-numeric:tabular-nums}
.lista h2,h3{color:var(--tinta);font-weight:600} .rotulo,.cita em{color:var(--apagado)}
.lista ul{border-top:1px solid var(--tinta)} .item{border-bottom:1px solid var(--linha);padding:16px 4px;transition:background .25s}
.item:hover{background:#efede6} .item.ativo{background:var(--tinta);color:var(--papel)} .item.ativo small{color:#bdbab2}
.nota-mini{font:400 36px "Instrument Serif";font-variant-numeric:tabular-nums} .item.ativo .nota-mini{color:var(--sinal)} .item-txt small{color:var(--apagado)}
.conf{font-size:12px;color:var(--apagado)} .item.ativo .conf{color:#bdbab2}
.fantasma{border:1px solid var(--linha)} .fantasma .rotulo{color:var(--sinal)} .fantasma b{text-decoration:line-through;text-decoration-color:var(--sinal)} .motivo{color:var(--apagado)}
.empresa{color:var(--sinal);font-weight:600} h1{font:400 46px/1.05 "Instrument Serif";letter-spacing:-.01em}
.resumo{font-size:18px;color:#2b2a27} h3{border-top:1px solid var(--tinta);padding-top:10px;transform-origin:left;animation:linha .9s cubic-bezier(.2,.8,.2,1) both .3s}
@keyframes linha{from{clip-path:inset(0 100% 0 0)}to{clip-path:inset(0 0 0 0)}}
.ponto{border-bottom:1px solid var(--linha)} .cita{color:#3d3b37} .lacuna b{color:var(--sinal)}
.sinais li{border:1px solid var(--tinta);border-radius:999px} .primario{background:var(--tinta);color:var(--papel)} .primario:hover{background:var(--sinal)} .secundario{border:1px solid var(--tinta);color:var(--tinta)}
.numeral{text-align:right} .numeral b{display:block;font:400 132px/0.8 "Instrument Serif";color:var(--sinal);font-variant-numeric:tabular-nums;animation:subir .8s cubic-bezier(.2,.8,.2,1) both}
.numeral small{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--apagado)}`,
    nota: (n) => `<div class="numeral"><b data-num="${n}">${n}</b><small>de encaixe</small></div>`,
  },
  "3-acolhedor": {
    fontes: "family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700&family=DM+Sans:wght@400;500;600",
    css: `:root{--areia:#f3efe7;--cartao:#fffdf9;--tinta:#1d2b24;--apagado:#6f746c;--linha:#e4ddd0;--verde:#1f6f4a;--verde-suave:#e2efe7;--ambar:#b5701b}
body{background:var(--areia);color:var(--tinta);font-family:"DM Sans",sans-serif}
.marca{font:700 24px "Bricolage Grotesque"} .logo{width:26px;height:26px;border-radius:9px;background:var(--verde);box-shadow:inset 0 0 0 6px var(--verde-suave)}
.perfil{justify-self:start;background:var(--cartao);border:1px solid var(--linha);border-radius:999px;padding:7px 14px;font-size:13.5px;color:var(--apagado)}
.placar{color:var(--apagado)} .placar b{color:var(--tinta)}
.lista h2,h3,.rotulo,.cita em{color:var(--apagado)}
.item{background:var(--cartao);border:1px solid var(--linha);border-radius:18px;transition:transform .35s cubic-bezier(.3,1.5,.5,1),box-shadow .35s}
.item:hover{transform:translateY(-3px);box-shadow:0 14px 30px -18px rgba(29,43,36,.35)} .item.ativo{border-color:var(--verde);box-shadow:0 0 0 3px var(--verde-suave)}
.nota-mini{width:44px;height:44px;border-radius:14px;display:grid;place-items:center;background:var(--verde-suave);color:var(--verde);font:700 17px "Bricolage Grotesque"}
.item-txt small{color:var(--apagado)} .conf{font-size:12px;color:var(--apagado)}
.fantasma{background:#f7ebe0;border-radius:18px;color:#6b4a2a} .fantasma .rotulo{color:var(--ambar)} .fantasma b{text-decoration:line-through}
.detalhe{background:var(--cartao);border:1px solid var(--linha);border-radius:26px;padding:30px 32px;box-shadow:0 30px 60px -40px rgba(29,43,36,.4)}
.empresa{color:var(--verde);font-weight:600} h1{font:700 32px/1.1 "Bricolage Grotesque";letter-spacing:-.02em}
.resumo{color:#3a4a41} .ponto{border-top:1px solid var(--linha)} .cita{color:#4d5a52} .lacuna b{color:var(--ambar)}
.sinais li{background:var(--verde-suave);color:var(--verde);border-radius:999px} .primario{background:var(--verde);color:#fff;border-radius:14px} .secundario{background:var(--areia);border-radius:14px;color:var(--tinta)}
.arco{position:relative;width:140px} .arco svg{transform:rotate(-90deg)}
.arco circle{fill:none;stroke-width:12;stroke-linecap:round} .arco .trilho{stroke:var(--verde-suave)}
.arco .valor{stroke:var(--verde);stroke-dasharray:377;stroke-dashoffset:377;animation:encher 1.4s cubic-bezier(.2,.8,.2,1) .2s forwards}
@keyframes encher{to{stroke-dashoffset:calc(377 - 377 * var(--n) / 100)}}
.arco b{position:absolute;top:0;left:0;width:140px;height:140px;display:grid;place-items:center;font:700 40px "Bricolage Grotesque";color:var(--verde)} .arco small{display:block;margin-top:6px;text-align:center;font-size:12px;color:var(--apagado)}`,
    nota: (n) =>
      `<div class="arco" style="--n:${n}"><svg viewBox="0 0 140 140" width="140" height="140"><circle class="trilho" cx="70" cy="70" r="60"/><circle class="valor" cx="70" cy="70" r="60"/></svg><b data-num="${n}">${n}</b><small>de encaixe</small></div>`,
  },
  "4-acolhedor-final": {
    fontes: "family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700&family=DM+Sans:wght@400;500;600",
    css: `:root{--areia:#f3efe7;--cartao:#fffdf9;--tinta:#1d2b24;--apagado:#6b7068;--linha:#e2dacb;--linha-forte:#cfc4b0;--verde:#1f6f4a;--verde-suave:#e2efe7;--ambar:#a8651a}
body{background:var(--areia);color:var(--tinta);font-family:"DM Sans",sans-serif}
.topo{border-bottom:1px solid var(--linha)}
.marca{font:700 24px "Bricolage Grotesque";letter-spacing:-.02em}
.logo{width:22px;height:22px;border-radius:50%;border:2px solid var(--verde);position:relative}
.logo::before{content:"";position:absolute;inset:5px;border-radius:50%;background:var(--verde)}
.perfil{font-size:14px;color:var(--apagado)} .perfil::before{content:"Seu perfil  ";color:var(--tinta);font-weight:600}
.placar{color:var(--apagado)} .placar b{color:var(--tinta);font-variant-numeric:tabular-nums}
.lista h2,h3,.rotulo,.cita em{color:var(--apagado)}
/* Cards: small radius, thin border, no glow. Hover is a border change, not a float. */
.item{background:var(--cartao);border:1px solid var(--linha);border-radius:10px;transition:border-color .2s,background .2s}
.item:hover{border-color:var(--linha-forte)} .item.ativo{border-color:var(--verde);background:#fbfdfa}
.nota-mini{position:relative;width:44px;height:44px;border-radius:12px;display:grid;place-items:center;background:var(--verde-suave);color:var(--verde);font:700 17px "Bricolage Grotesque";font-variant-numeric:tabular-nums}
.item-txt small{color:var(--apagado)} .conf{font-size:12px;color:var(--apagado);font-variant-numeric:tabular-nums} .conf::before{content:"confiança ";}
.fantasma{border:1px dashed var(--linha-forte);border-radius:10px;color:var(--apagado)} .fantasma .rotulo{color:var(--ambar)} .fantasma b{color:var(--tinta);text-decoration:line-through;text-decoration-color:var(--ambar)}
.detalhe{background:var(--cartao);border:1px solid var(--linha);border-radius:14px;padding:32px 34px}
.empresa{color:var(--verde);font-weight:600} h1{font:700 32px/1.1 "Bricolage Grotesque";letter-spacing:-.02em}
.resumo{color:#3a4a41} .ponto{border-top:1px solid var(--linha)} .cita{color:#4d5a52} .lacuna b{color:var(--ambar)}
/* Signals as a plain list with a mark, not pills. */
.sinais{flex-direction:column;gap:6px} .sinais li{padding:0;font-size:14px;color:#3a4a41} .sinais li::before{content:"✓";color:var(--verde);font-weight:700;margin-right:10px}
.primario{background:var(--verde);color:#fff;border-radius:10px} .primario:hover{background:#185a3c}
.secundario{border:1px solid var(--linha-forte);border-radius:10px;color:var(--tinta)} .secundario:hover{border-color:var(--tinta)}
/* The score: an arc that fills up to the value. */
.leitura{position:relative;width:140px;height:140px;flex-shrink:0}
.leitura svg{position:absolute;inset:0;transform:rotate(-90deg)}
.leitura circle{fill:none;stroke-width:10;stroke-linecap:round} .leitura .trilho{stroke:var(--verde-suave)}
.leitura .valor{stroke:var(--verde);stroke-dasharray:377;stroke-dashoffset:377;animation:encher 1.4s cubic-bezier(.2,.8,.2,1) .2s forwards}
@keyframes encher{to{stroke-dashoffset:calc(377 - 377 * var(--n) / 100)}}
.leitura b{position:absolute;inset:0;display:grid;place-items:center;font:700 42px "Bricolage Grotesque";color:var(--verde);font-variant-numeric:tabular-nums}
.leitura small{position:absolute;bottom:-18px;left:0;right:0;text-align:center;font-size:12px;color:var(--apagado)}`,
    nota: (n) =>
      `<div class="leitura" style="--n:${n}"><svg viewBox="0 0 140 140" width="140" height="140"><circle class="trilho" cx="70" cy="70" r="60"/><circle class="valor" cx="70" cy="70" r="60"/></svg><b data-num="${n}">${n}</b><small>de encaixe</small></div>`,
  },
};

for (const [nome, d] of Object.entries(DIRECOES)) {
  writeFileSync(
    new URL(`./${nome}.html`, import.meta.url),
    `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sonar · ${nome}</title><link rel="stylesheet" href="https://fonts.googleapis.com/css2?${d.fontes}&display=swap">
<style>${BASE}\n${d.css}</style></head><body>${corpo(d.nota)}${CONTAR}</body></html>`,
  );
}
console.log("ok");
