/* =====================================================================================
   TabDeck - script della pagina (gira sul tablet: Chrome 81, Android 4.4, CPU/GPU lente).
   Il server inserisce i valori iniziali al posto dei segnaposto __NOME__ (vedi render_page).
   Dettagli: docs/ARCHITETTURA.md

   MAPPA (cerca questi commenti)
     barra e stato ......... status/setText/tick, batteria, schermo intero
     tocchi ................ activate (cosa fa un riquadro), bind (tap / tieni premuto / scorrimenti)
     Generale .............. volume, ping (/state), app attive (renderRun), striscia Finestre (renderWins),
                             azioni finestre (winAct, menu tieni-premuto)
     Helldivers 2 .......... equipaggiamento, applyCd/paintCd (ricariche), Sync
     Audio ................. brano (renderNP), mixer (renderMix), microfono, tasti Discord
     Discord ............... server / canali / chiamata, volume per persona, microfono
     Touchpad / Monitor .... pad, tastiera, grafici
     Impostazioni .......... setOpen/setTab, editor delle righe (ED), scorciatoie (KE), Discord, riavvio
     gesto a due dita ...... cambio sezione (gMove)

   SICUREZZA
     - Ogni richiesta porta l'intestazione X-Token; il token sparisce subito dalla barra indirizzi.
     - Testo che viene da fuori (titoli, nomi, brani) solo con esc() dentro innerHTML o con textContent.
       Mai eval / new Function / HTML costruito con dati non escapati.

   PRESTAZIONI (misurate sul tablet: non romperle)
     - setText: non riscrivere testo uguale (forza un ridisegno).
     - Ricostruire liste solo se cambia il contenuto (confronto di una chiave); altrimenti solo classi.
       Mai ricostruire sotto il dito (controllo di .on / .held).
     - Nessun listener touchmove non-passivo permanente sul documento (blocca lo scorrimento).
     - Ogni sezione interroga il PC solo quando e' aperta (curTab) e la pagina e' visibile.
   ===================================================================================== */
var TABS = __TABS__, TAB_NAMES = __TABNAMES__;
var CD0 = __CD__, CD = {}, PEND = null, ARR = null, NA = [], USE = {};
/* ID del dispositivo (approvazione dal PC): anche in localStorage, perche' l'app dalla schermata Home di iOS
   ha cookie suoi. Va in X-Device su ogni richiesta. */
var DEVICE = "__DEVICE__", APPR = __APPR__;
(function () { var a = document.getElementById("apprst"); if (a) { a.textContent = APPR ? "Attiva" : "Disattivata"; } })();
try { if (DEVICE) { localStorage.setItem("tdd", DEVICE); } else { DEVICE = localStorage.getItem("tdd") || ""; } } catch (e) {}
var TOKEN = "__TOKEN__", LOADOUT = __LOADOUT__, SETTINGS = __SETTINGS__, ALWAYS = __ALWAYS__, HOLD_MS = __HOLD__, editMode = false, online = true, multiActive = false;
document.body.className = "pos-" + SETTINGS.pos + (SETTINGS.theme && SETTINGS.theme !== "hd" ? " th-" + SETTINGS.theme : "");
var HASH = (location.hash || "").slice(1);  /* #mix, #set-td ... apre subito una sezione */
var IOS = /iPhone|iPad|iPod/.test(navigator.userAgent);
/* il token sparisce dalla barra indirizzi. Su iPhone resta: "Aggiungi alla schermata Home" salva l'indirizzo
   della pagina e l'app aggiunta non condivide i cookie di Safari (senza token non si aprirebbe). */
try { history.replaceState(null, "", IOS ? "/?t=" + TOKEN : "/"); } catch (e) {}
/* iPhone: Safari ignora user-scalable=no; niente zoom con due dita (ruberebbe i gesti di TabDeck) */
document.addEventListener("gesturestart", function (e) { e.preventDefault(); }, false);  /* il token sparisce dalla barra indirizzi */
var st = document.getElementById("st"), ck = document.getElementById("clock");
function status(c, txt) { var k = "mono " + c; if (st.className !== k) { st.className = k; } if (st.textContent !== txt) { st.textContent = txt; } }
function setText(el, t) { t = String(t); if (el.textContent !== t) { el.textContent = t; } }
function tick() { var d = new Date(), m = d.getMinutes(); setText(ck, d.getHours() + ":" + (m < 10 ? "0" : "") + m); }
tick(); setInterval(tick, 10000);
/* batteria del tablet (si aggiorna solo quando cambia) */
if (navigator.getBattery) {
  navigator.getBattery().then(function (b) {
    var el = document.getElementById("batt");
    function p() { el.textContent = Math.round(b.level * 100) + "%" + (b.charging ? " +" : ""); cls(el, "low", b.level < 0.2 && !b.charging); }
    p(); b.addEventListener("levelchange", p); b.addEventListener("chargingchange", p);
  });
}
/* impostazioni di QUESTO dispositivo (non del PC): schermo intero.
   Salvate nel browser; se il browser non le conserva valgono i valori predefiniti. */
var LOCAL = {fs: "on", tpside: "right", kb: "on"}, LOCAL_OK = {fs: ["on", "off"], tpside: ["right", "left"], kb: ["on", "off"]};
(function () {
  for (var k in LOCAL) {
    var v = null;
    try { v = localStorage.getItem("td_" + k); } catch (e) {}
    if (v && LOCAL_OK[k].indexOf(v) >= 0) { LOCAL[k] = v; }
  }
})();
function setLocal(k, v) {
  LOCAL[k] = v;
  try { localStorage.setItem("td_" + k, v); } catch (e) {}
  paintLocal();
}
function paintLocal() {
  cls(document.body, "tp-left", LOCAL.tpside === "left");
  cls(document.body, "kb-off", LOCAL.kb === "off");
  [].forEach.call(document.querySelectorAll(".lseg"), function (seg) {
    [].forEach.call(seg.children, function (o) { cls(o, "sel", LOCAL[seg.getAttribute("data-l")] === o.getAttribute("data-v")); });
  });
}
[].forEach.call(document.querySelectorAll(".lseg div"), function (o) {
  o.addEventListener("click", function () {
    var k = o.parentNode.getAttribute("data-l"), v = o.getAttribute("data-v");
    setLocal(k, v);
    if (k === "fs") { if (v === "off") { if (document.fullscreenElement) { document.exitFullscreen(); } } else { goFull(); } }
  }, false);
});
paintLocal();
if (!document.documentElement.requestFullscreen) {
  var fsOpt = document.querySelector('.lseg[data-l="fs"]');
  if (fsOpt) { fsOpt.parentNode.style.display = "none"; }
}
/* schermo intero: Chrome lo concede solo dopo un tocco, quindi lo chiediamo al primo tocco (se non e' disattivato) */
function goFull(e) {
  var d = document.documentElement;
  if (e && e.target && e.target.closest && e.target.closest(".lseg")) { return; }   /* il tocco sull'opzione decide da se' */
  if (LOCAL.fs === "on" && !document.fullscreenElement && d.requestFullscreen) {
    var p = d.requestFullscreen({navigationUI: "hide"});
    if (p && p.catch) { p.catch(function () {}); }
  }
}
document.addEventListener("touchend", goFull, true);
function cls(el, c, on) { el.classList[on ? "add" : "remove"](c); }
function flash(el, c) {
  cls(el, "on", false); cls(el, c, true);
  setTimeout(function () { cls(el, c, false); }, 400);
}
function post(path, body, cb, ms) {
  var x = new XMLHttpRequest();
  x.open("POST", path, true);
  x.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");
  x.setRequestHeader("X-Token", TOKEN); if (DEVICE) { x.setRequestHeader("X-Device", DEVICE); }
  x.timeout = ms || 4000;
  x.onreadystatechange = function () { if (x.readyState === 4) { cb(x.status, x.responseText); } };
  x.send(body);
}
function name(el) { return el.getAttribute("data-n"); }
function activate(el, alt) {
  if (el.hasAttribute("data-go")) { showTab(el.getAttribute("data-go")); return; }
  if (el.hasAttribute("data-mic")) { micTap(el); return; }
  if (el.hasAttribute("data-dcg")) { dcPickGuild(el.getAttribute("data-dcg")); return; }
  if (el.hasAttribute("data-dcc")) { dcJoin(el); return; }
  if (el.hasAttribute("data-dcu")) { dcUser(el.getAttribute("data-dcu")); return; }
  if (el.hasAttribute("data-dca")) { dcAct(el.getAttribute("data-dca")); return; }
  if (el.hasAttribute("data-yta")) { ytBtn(el.getAttribute("data-yta"), el); return; }
  if (el.hasAttribute("data-ytp")) { ytPick(el, +el.getAttribute("data-ytp"), false); return; }
  if (el.hasAttribute("data-ytq")) { ytPick(el, +el.getAttribute("data-ytq"), true); return; }
  if (el.hasAttribute("data-ytup")) { ytAct("up", "i=" + el.getAttribute("data-ytup")); return; }
  if (el.hasAttribute("data-ytrm")) { ytAct("rm", "i=" + el.getAttribute("data-ytrm")); return; }
  if (el.hasAttribute("data-ytv")) { ytView(el.getAttribute("data-ytv")); return; }
  if (el.hasAttribute("data-yts")) { ytPickSug(+el.getAttribute("data-yts")); return; }
  if (!alt && !editMode) { var ra = runOf(el); if (ra) { runTap(el, ra); return; } }
  if (!alt && el.getAttribute("data-id") === "discord" && !el.closest(".gpop")) { showTab("dc"); return; }   /* anche con Discord chiuso */
  if (el.hasAttribute("data-grp")) { openGroup(el.getAttribute("data-grp")); return; }
  if (el.hasAttribute("data-hw")) { focusWin(el); return; }
  if (el.hasAttribute("data-mc")) { mediaCmd(el); return; }
  var id = el.getAttribute("data-id"), pop = el.closest(".gpop");
  if (pop) { setTimeout(function () { cls(pop, "show", false); }, 350); }
  if (editMode && el.classList.contains("s")) {
    if (el.classList.contains("mis")) { status("", "Sempre disponibile: non serve sceglierlo"); return; }
    togglePin(id); return;
  }
  cls(el, "on", true);
  post("/press", "id=" + encodeURIComponent(id), function (code, txt) {
    var ok = code === 200;
    flash(el, ok ? "ok" : "err");
    if (ok) {
      status("ok", "✓ " + name(el));
      if (el.classList.contains("s")) { try { applyCd(JSON.parse(txt).hd); } catch (e) {} }
    }
    else { status("err", code === 0 ? "PC non raggiungibile" : code === 409 ? "Apri prima HELLDIVERS 2" : "Errore " + code); }
    if (code === 0) { online = false; }
  });
}
/* Tocco: il comando parte al RILASCIO, solo se il dito non si e' mosso e la lista non ha scorso.
   Tenendo premuto uno stratagemma oltre HOLD_MS se ne vede il nome, senza attivarlo. */
/* Qualsiasi scorrimento (pagina del telefono, liste, strisce laterali) segna l'ora: un tocco che arriva mentre
   la pagina scorre ancora (per fermarla) o durante il quale qualcosa ha scorso non preme il riquadro. */
var lastScroll = 0;
document.addEventListener("scroll", function () { lastScroll = Date.now(); }, {capture: true, passive: true});
function bind(el) {
  var sx = 0, sy = 0, t0 = 0, sc = 0, live = false, lastTouch = 0, multi = false, ht = null;
  var scroller = el.closest(".scroll") || document.body;
  function unhold() { if (ht) { clearTimeout(ht); ht = null; } cls(el, "held", false); }
  el.addEventListener("touchstart", function (e) {
    if (e.touches.length > 1) { live = false; multi = true; unhold(); cls(el, "on", false); return; }  /* gesto a due dita: nessun tasto */
    var p = e.touches[0]; sx = p.clientX; sy = p.clientY; t0 = Date.now(); sc = scroller.scrollTop; multi = false;
    live = t0 - lastScroll > 150;       /* la pagina stava ancora scorrendo: questo tocco la ferma soltanto */
    if (!live) { return; }
    cls(el, "on", true);
    unhold();
    ht = setTimeout(function () {
      ht = null;
      var hw = live && !editMode && winOf(el);
      if (!hw) { return; }
      /* finestra aperta: il menu si apre SUBITO, col dito ancora giu' (su iPhone il sistema annulla i tocchi
         lunghi prima del rilascio, quindi aspettare il rilascio non funzionerebbe) */
      live = false; cls(el, "on", false); openWinMenu(el, hw, true);
    }, HOLD_MS);
  }, {passive: true});
  el.addEventListener("touchmove", function (e) {
    if (e.touches.length > 1) { multi = true; }
    if (!live) { return; }
    if (e.touches.length > 1) { live = false; unhold(); cls(el, "on", false); return; }
    var p = e.touches[0];
    if (Math.abs(p.clientX - sx) > 10 || Math.abs(p.clientY - sy) > 10) { live = false; unhold(); cls(el, "on", false); }
  }, {passive: true});
  el.addEventListener("touchcancel", function () { live = false; unhold(); cls(el, "on", false); }, false);
  el.addEventListener("touchend", function (e) {
    lastTouch = Date.now();
    if (e.cancelable) { e.preventDefault(); }
    cls(el, "on", false); unhold();
    /* scorrimento su una finestra: su = ingrandisci / ripristina, giu' = riduci a icona */
    var ct = e.changedTouches && e.changedTouches[0];
    if (ct && !live && !multi && !multiActive && !editMode && scroller.scrollTop === sc && lastScroll < t0) {
      var dx = ct.clientX - sx, dy = ct.clientY - sy, sw = winOf(el);
      if (sw && !el.classList.contains("wbt") && Math.abs(dy) > 40 && Math.abs(dy) > 1.5 * Math.abs(dx)) { winAct(el, sw, dy < 0 ? "max" : "min"); return; }
      /* riquadro YouTube: scorri su = apri (o porta davanti) il player sul PC */
      if (el.hasAttribute("data-yt") && dy < -40 && Math.abs(dy) > 1.5 * Math.abs(dx)) { flash(el, "ok"); ytBtn("open", el); return; }
    }
    if (!live || multiActive) { live = false; return; }
    live = false;
    if (scroller.scrollTop !== sc || lastScroll >= t0) { return; }
    if (!editMode && Date.now() - t0 >= HOLD_MS) { var hw = winOf(el); if (hw) { openWinMenu(el, hw); return; } }   /* finestra aperta: menu */
    if (el.classList.contains("s") && !editMode && Date.now() - t0 >= HOLD_MS) {
      status("", name(el) + "  " + el.getAttribute("data-c")); return;
    }
    activate(el);
  }, false);
  el.addEventListener("click", function () { if (Date.now() - lastTouch > 800) { activate(el); } }, false);
}
/* volume: il PC resta la fonte di verita'. In Generale c'e' solo il riquadro "Volume" (tocco = scheda Audio) */
var VOL = {vol: 0, mute: false}, dragging = false, lastSent = 0, inflight = false;
var valEl = document.getElementById("volval"), svolEl = document.getElementById("svol");
function paintVol() { if (valEl) { setText(valEl, VOL.vol); cls(svolEl, "muted", VOL.mute); } }   /* il riquadro puo' essere tolto */
function ping() {
  var x = new XMLHttpRequest();
  x.open("GET", "/state?" + (curTab === "grid" ? "g=1&" : "") + "_=" + Date.now(), true);
  x.setRequestHeader("X-Token", TOKEN); if (DEVICE) { x.setRequestHeader("X-Device", DEVICE); }
  x.timeout = 3000;
  x.onreadystatechange = function () {
    if (x.readyState !== 4) { return; }
    var ok = x.status === 200;
    if (x.status === 403 && /"(pending|refused|locked)"/.test(x.responseText)) { location.reload(); return; }   /* tolto o in attesa: pagina d'attesa */
    if (ok) {
      try {
        var s = JSON.parse(x.responseText);
        if (s.rev !== undefined) { cfgSeen(s.rev); }
        if (s.hd) { applyCd(s.hd); }
        if (s.run) { renderRun(s.run); }
        if (s.wins) { renderWins(s.wins); }
        if (s.dc) { paintDcTile(s.dc); }
        if (s.mic) { renderMic(s.mic); }
        if ("vol" in s && !dragging && !inflight && Date.now() - lastSent > 1500) { VOL = {vol: s.vol, mute: s.mute}; paintVol(); }
      } catch (e) {}
    }
    if (ok !== online) { online = ok; status(ok ? "ok" : "err", ok ? "connesso" : "offline, riprovo..."); }
  };
  try { x.send(); } catch (e) { online = false; }
}
/* configurazione cambiata sul PC (es. "Annulla ultima modifica"): Generale e impostazioni si rifanno sul posto */
var cfgRev = null;
function cfgSeen(rev) {
  if (cfgRev === null) { cfgRev = rev; return; }
  if (rev === cfgRev) { return; }
  cfgRev = rev;
  refreshGeneral(function () {
    if (document.body.classList.contains("setopen") && document.getElementById("sp_fav").classList.contains("show")) { favLoad(); }
  });
}
var pingN = 0;
ping();
setInterval(function () {
  pingN++;
  if (curTab === "hd2") { return; }                       /* gia' coperto dal ping da 0,5 s */
  if (curTab !== "grid" && pingN % 3) { return; }         /* Audio/Discord/Monitor/Touchpad: solo "sono online?" */
  ping();
}, 1500);
setInterval(function () { if (curTab === "hd2" && !document.hidden) { ping(); } }, 500);   /* ricariche piu' reattive */
/* finestre del PC: fascia fissa a destra in ogni sezione (vicina alla mano). Tocco = porta in primo piano,
   tenendo premuto = menu della finestra. La maniglia in alto (o uno scorrimento verso sinistra) allarga la fascia
   coi titoli; un tocco fuori o la scelta di una finestra la richiude. */
var winKey = "", curTab = "grid", WORDER = [], wband = document.createElement("div"), wlist;
wband.id = "wband";
wband.innerHTML = '<div class="wbg"><span>&lsaquo;</span></div><div class="wbl scroll"></div>';
document.body.appendChild(wband);
wlist = wband.querySelector(".wbl");
function wbPeek(on) { cls(wband, "peek", on); }
/* la fascia finisce dove comincia la barra in basso (alta in modo diverso su telefono) */
function wbFit() { var bar = document.getElementById("bar"); if (bar) { wband.style.bottom = bar.offsetHeight + "px"; } }
window.addEventListener("resize", wbFit, false);
wbFit();
function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
function hue(s) { var h = 0; for (var i = 0; i < s.length; i++) { h = (h * 31 + s.charCodeAt(i)) % 360; } return h; }
function renderWins(list) {
  var byH = {}, i;
  list.forEach(function (w) { byH[w.h] = w; });
  WORDER = WORDER.filter(function (h) { return byH[h]; });
  for (i = list.length - 1; i >= 0; i--) { if (WORDER.indexOf(list[i].h) < 0) { WORDER.push(list[i].h); } }   /* nuove in fondo */
  var ord = WORDER.map(function (h) { return byH[h]; }), key = JSON.stringify(ord.map(function (w) { return [w.h, w.x, w.i, w.t]; }));
  if (key === winKey || wlist.querySelector(".on, .held")) {   /* stesse finestre: solo le classi (o niente sotto il dito) */
    if (key === winKey) {
      [].forEach.call(wlist.getElementsByClassName("wbt"), function (el) {
        var w = byH[el.getAttribute("data-hw")]; if (w) { cls(el, "fg", w.fg); cls(el, "mn", w.min); }
      });
    }
    return;
  }
  winKey = key;
  wlist.innerHTML = ord.map(function (w) {
    var app = w.x.replace(/\.exe$/i, ""), mono = app.replace(/[^A-Za-z0-9]/g, "").slice(0, 2).toUpperCase() || "?";
    var img = w.i ? '<img src="/appicon/' + w.i + '.png" alt="" onload="this.previousSibling.style.visibility=\'hidden\'" onerror="this.parentNode.removeChild(this)">' : "";
    return '<button class="b wbt' + (w.fg ? " fg" : "") + (w.min ? " mn" : "") + '" data-hw="' + w.h + '" data-n="' + esc(w.t) +
      '" style="--c:hsl(' + hue(app.toLowerCase()) + ',65%,62%)"><span class="wbi"><span>' + esc(mono) + "</span>" + img +
      '</span><span class="wbtt"><b>' + esc(w.t) + "</b><i>" + esc(app) + "</i></span></button>";
  }).join("") || '<div class="wbe">&ndash;</div>';
  [].forEach.call(wlist.getElementsByClassName("wbt"), bind);
}
document.addEventListener("contextmenu", function (e) { e.preventDefault(); }, false);   /* niente menu del tablet tenendo premuto */
/* maniglia: tocco = allarga/stringe; scorrimento orizzontale sulla fascia = allarga (verso sinistra) o stringe */
(function () {
  var g = wband.querySelector(".wbg"), x0 = 0, y0 = 0;
  g.addEventListener("touchend", function (e) { if (e.cancelable) { e.preventDefault(); } wbPeek(!wband.classList.contains("peek")); }, false);
  g.addEventListener("click", function () { wbPeek(!wband.classList.contains("peek")); }, false);   /* mouse */
  wband.addEventListener("touchstart", function (e) { if (e.touches.length === 1) { x0 = e.touches[0].clientX; y0 = e.touches[0].clientY; } }, {passive: true});
  wband.addEventListener("touchend", function (e) {
    var t = e.changedTouches && e.changedTouches[0], dx, dy;
    if (!t) { return; }
    dx = t.clientX - x0; dy = t.clientY - y0;
    if (Math.abs(dx) > 30 && Math.abs(dx) > 1.5 * Math.abs(dy)) { wbPeek(dx < 0); }
  }, {passive: true});
  document.addEventListener("touchstart", function (e) {
    if (wband.classList.contains("peek") && !(e.target.closest && e.target.closest("#wband"))) { wbPeek(false); }
  }, {capture: true, passive: true});
})();
/* fuori da Generale le finestre non arrivano con /state: si chiedono a parte, solo a pagina visibile */
var wbBusy = false;
setInterval(function () {
  if (wbBusy || curTab === "grid" || document.hidden || document.body.classList.contains("setopen")) { return; }
  wbBusy = true;
  dcGet("/windows", function (code, j) { wbBusy = false; if (code === 200 && j && j.length !== undefined) { renderWins(j); } });
}, 1200);
function focusWin(el) {
  if (wband.classList.contains("peek")) { setTimeout(function () { wbPeek(false); }, 600); }
  cls(el, "on", true);
  post("/focus", "h=" + encodeURIComponent(el.getAttribute("data-hw")), function (code, txt) {
    cls(el, "on", false);
    var r = null;
    if (code === 200 || code === 409) { try { r = JSON.parse(txt); renderWins(r.w); } catch (e) {} }
    if (code === 200) { status("ok", (r && r.a === "min" ? "↓ ridotta: " : "✓ ") + name(el)); }
    else { status("err", code === 409 ? "Windows non l'ha portata avanti" : code === 404 ? "Finestra chiusa" : code === 0 ? "PC non raggiungibile" : "Errore " + code); }
  });
}
/* app attive (scheda Generale): il PC dice quali riquadri hanno una finestra aperta.
   Tocco = porta in primo piano (o apre la sezione di TabDeck del gioco); tenendo premuto = comportamento normale. */
var RUN = {apps: {}, grp: {}}, runKey = "", GRP_HTML = {};
function runOf(el) {
  var g = el.getAttribute("data-grp"), id = g ? RUN.grp[g] : el.getAttribute("data-id");
  return (id && RUN.apps[id]) || null;
}
function renderRun(r) {
  var key = JSON.stringify(r);
  if (key === runKey) { return; }
  runKey = key; RUN = r;
  [].forEach.call(document.querySelectorAll("#grid .b[data-id], #grid .b[data-grp], .gpop .b[data-id]"), function (el) {
    cls(el, "run", !!runOf(el));
  });
  [].forEach.call(document.querySelectorAll("#grid .b[data-grp]"), function (el) {
    var g = el.getAttribute("data-grp"), id = RUN.grp[g];
    if (!(g in GRP_HTML)) { GRP_HTML[g] = el.innerHTML; }
    if (!id) { el.innerHTML = GRP_HTML[g]; return; }
    var a = RUN.apps[id], it = document.querySelector('.gpop .b[data-id="' + id + '"]'), mo = it && it.querySelector(".mo");
    el.innerHTML = '<span class="ic"><span class="mo">' + esc(mo ? mo.textContent : "") + '</span>' +
      (a.i ? '<img src="/appicon/' + a.i + '.png" alt="" onload="this.previousSibling.style.visibility=\'hidden\'" onerror="this.parentNode.removeChild(this)">' : "") +
      '</span><span class="l">' + esc(a.n) + '</span><span class="h mono">attivo &middot; tieni per la lista</span>';
  });
}
/* riquadro Discord dei Preferiti: mentre un gioco e' aperto mostra se sei muto / senza cuffie */
var dcTile = document.querySelector('#grid .b[data-id="discord"]'), dcHint = dcTile && dcTile.querySelector(".h");
function paintDcTile(d) {
  if (!dcTile) { return; }
  var game = !!(RUN.grp && RUN.grp.giochi), ok = game && d.s === "ok";
  if (dcHint) { setText(dcHint, !ok ? "app" : d.deaf ? "cuffie off" : d.mute ? "muto" : "mic attivo"); }
  cls(dcTile, "dcoff", ok && (d.mute || d.deaf));
}
function runTap(el, r) {
  var pop = el.closest(".gpop");
  if (pop) { setTimeout(function () { cls(pop, "show", false); }, 350); }
  if (r.tab) { showTab(r.tab); return; }
  focusPost(el, r, false);
}
function focusPost(el, r, keep) {
  cls(el, "on", true);
  post("/focus", (keep ? "keep=1&" : "") + "h=" + encodeURIComponent(r.h), function (code, txt) {
    cls(el, "on", false); flash(el, code === 200 ? "ok" : "err");
    var j = null; try { j = JSON.parse(txt); } catch (e) {}
    if (code === 200) { status("ok", (j && j.a === "min" ? "↓ ridotta: " : "✓ ") + r.n); }
    else { status("err", code === 409 ? "Windows non l'ha portata avanti" : code === 404 ? "Finestra chiusa" : code === 0 ? "PC non raggiungibile" : "Errore " + code); }
    afterWin(j);
  });
}
/* dopo un'azione su una finestra: aggiorna subito l'elenco visibile */
function afterWin(j) {
  if (j && j.w) { renderWins(j.w); }
  if (curTab === "grid") { setTimeout(ping, 300); }
}
/* finestra legata a un riquadro: riquadri della scheda Finestre o app attive di Generale */
function winOf(el) {
  if (el.hasAttribute("data-hw")) { return {h: el.getAttribute("data-hw"), n: name(el)}; }
  return runOf(el);
}
function winAct(el, r, a) {
  cls(el, "on", true);
  post("/winact", "a=" + a + "&h=" + encodeURIComponent(r.h), function (code, txt) {
    cls(el, "on", false); flash(el, code === 200 ? "ok" : "err");
    var j = null; try { j = JSON.parse(txt); } catch (e) {}
    if (code === 200) { status("ok", (j ? j.r : a) + ": " + r.n); }
    else {
      /* 409: di solito una finestra avviata come amministratore (es. Gestione attivita'): Windows non lascia che
         un programma normale come TabDeck la comandi */
      status("err", code === 404 ? "Finestra chiusa" : code === 409 ? "Windows non lo permette: app avviata come amministratore" :
        code === 0 ? "PC non raggiungibile" : "Errore " + code);
    }
    afterWin(j);
  });
}
/* menu (tenendo premuto): accanto al riquadro, azioni grandi da toccare */
var wmenu = document.getElementById("wmenu"), wbox = document.getElementById("wbox");
/* Il menu si apre col dito ancora giu': finche' quel dito non si alza (e per un attimo dopo) il menu ignora i
   tocchi, altrimenti il "tap" che Safari manda al rilascio lo chiuderebbe o premerebbe la voce sotto il dito.
   Dopo il rilascio si ignora solo quel tap: un dito che tocca di nuovo e' una scelta vera e vale subito
   (prima c'era una pausa fissa di 450 ms che su iPhone mangiava i tocchi veloci sulle voci). */
var menuHold = false, menuQuietUntil = 0;
function menuRelease() { if (menuHold) { menuHold = false; menuQuietUntil = Date.now() + 450; } }
document.addEventListener("touchstart", function () { if (!menuHold) { menuQuietUntil = 0; } }, {capture: true, passive: true});
document.addEventListener("touchend", function (e) { if (!e.touches || e.touches.length === 0) { menuRelease(); } }, {capture: true, passive: true});
document.addEventListener("touchcancel", menuRelease, {capture: true, passive: true});
function openWinMenu(el, r, held) {
  menuHold = !!held;
  var items = [];
  if (r.tab) { items.push(["front", "Porta davanti"]); }
  if (el.hasAttribute("data-grp")) { items.push(["list", "Lista"]); }
  else if (el.hasAttribute("data-id")) { items.push(["new", "Nuova finestra"]); }
  items.push(["min", "Minimizza"], ["max", "Massimizza"], ["close", "Chiudi"]);
  wbox.innerHTML = '<div class="wmt">' + esc(r.n) + "</div>" + items.map(function (it) {
    return '<div class="wmi wm-' + it[0] + '" data-a="' + it[0] + '">' + it[1] + "</div>";
  }).join("");
  [].forEach.call(wbox.getElementsByClassName("wmi"), function (mi) {
    mi.addEventListener("click", function (e) {
      e.stopPropagation(); cls(wmenu, "show", false);
      var a = mi.getAttribute("data-a");
      if (a === "list") { openGroup(el.getAttribute("data-grp")); }
      else if (a === "new") { activate(el, true); }
      else if (a === "front") { focusPost(el, r, true); }
      else { winAct(el, r, a); }
    }, false);
  });
  cls(wmenu, "show", true);
  var rc = el.getBoundingClientRect(), bw = wbox.offsetWidth, bh = wbox.offsetHeight, W = window.innerWidth, H = window.innerHeight;
  var left = Math.max(8, Math.min(W - bw - 8, rc.left + rc.width / 2 - bw / 2)), top = rc.bottom + 6;
  if (top + bh > H - 8) { top = rc.top - bh - 6; }
  if (top < 8) { top = Math.max(8, Math.min(H - bh - 8, rc.top + rc.height / 2 - bh / 2)); left = rc.right + 6 + bw > W - 8 ? Math.max(8, rc.left - bw - 6) : rc.right + 6; }
  wbox.style.left = left + "px"; wbox.style.top = top + "px";
}
wmenu.addEventListener("click", function (e) {      /* fase di cattura: prima delle voci del menu */
  if (menuHold || Date.now() < menuQuietUntil) { e.stopPropagation(); e.preventDefault(); }
}, true);
wmenu.addEventListener("click", function (e) { if (e.target === wmenu) { cls(wmenu, "show", false); } }, false);
/* gruppi (browser, launcher, giochi): si aprono in una finestra */
function openGroup(id) { cls(document.getElementById("pop_" + id), "show", true); }
function bindPop(p) {
  p.addEventListener("click", function (e) { if (e.target === p || e.target.classList.contains("gx")) { cls(p, "show", false); } }, false);
}
[].forEach.call(document.getElementsByClassName("gpop"), bindPop);
/* Generale rifatto dal PC (dopo aver salvato i pulsanti): si sostituisce sul posto, senza ricaricare la pagina.
   I riferimenti tenuti da parte (volume, microfono, Discord, gruppi) vanno ripresi dai nuovi riquadri. */
function refreshGeneral(done) {
  dcGet("/general", function (code, j) {
    if (code !== 200 || !j || typeof j.secs !== "string") { location.reload(); return; }   /* ripiego sicuro */
    if (j.rev !== undefined) { cfgRev = j.rev; }
    if (j.settings) { SETTINGS = j.settings; paintSettings(); }
    var grid = document.getElementById("grid"), tmp = document.createElement("div"), fresh = [grid], nodes, ref;
    grid.innerHTML = j.secs;
    tmp.innerHTML = j.pops;
    nodes = [].slice.call(tmp.childNodes);
    nodes.forEach(function (p) { var old = p.id && document.getElementById(p.id); if (old) { old.parentNode.removeChild(old); } });
    ref = grid.nextSibling;   /* preso dopo aver tolto i vecchi: potevano essere proprio loro */
    nodes.forEach(function (p) {
      grid.parentNode.insertBefore(p, ref);
      if (p.classList && p.classList.contains("gpop")) { bindPop(p); fresh.push(p); }
    });
    fresh.forEach(function (box) { [].forEach.call(box.querySelectorAll(".b"), bind); });
    valEl = document.getElementById("volval"); svolEl = document.getElementById("svol");
    micEls = [document.getElementById("vmic"), document.getElementById("smic")].filter(function (e) { return e; });
    dcTile = document.querySelector('#grid .b[data-id="discord"]'); dcHint = dcTile && dcTile.querySelector(".h");
    GRP_HTML = {}; runKey = ""; renderRun(RUN); paintVol();
    if (curTab === "grid") { ping(); }
    if (done) { done(); }
  });
}
function tile(id) { return document.querySelector('#hd2all .s[data-id="' + id + '"]'); }
function cloneInto(box, id) {
  var t = tile(id); if (!t) { return; }
  var c = t.cloneNode(true);
  cls(c, "pin", false); cls(c, "on", false);
  bind(c); box.appendChild(c);
}
function buildLoadout() {
  cdSig = "";   /* riquadri nuovi: va ridisegnato tutto */
  var row = document.getElementById("lo"), fx = document.getElementById("fixed"),
      all = document.getElementById("hd2all").getElementsByClassName("s"), i, eagle = false;
  row.innerHTML = ""; fx.innerHTML = "";
  for (i = 0; i < all.length; i++) { cls(all[i], "pin", LOADOUT.indexOf(all[i].getAttribute("data-id")) >= 0); }
  for (i = 0; i < LOADOUT.length; i++) {
    cloneInto(row, LOADOUT[i]);
    if (LOADOUT[i].indexOf("hd2_e_") === 0) { eagle = true; }
  }
  for (i = 0; i < ALWAYS.length; i++) {
    if (ALWAYS[i] === "hd2_eagle_rearm" && !eagle) { continue; }
    cloneInto(fx, ALWAYS[i]);
  }
  if (!LOADOUT.length) {
    row.innerHTML = '<div class="hint">Tocca «Modifica» e scegli gli stratagemmi che hai equipaggiato in gioco.</div>';
  }
  if (editMode) { status("", "scegli " + LOADOUT.length + "/4, poi «Fine»"); }
}
/* salto rapido a un gruppo */
[].forEach.call(document.getElementsByClassName("jc"), function (c) {
  c.addEventListener("click", function () {
    var sc = document.getElementById("hd2all"), g = document.getElementById(c.getAttribute("data-g"));
    sc.scrollTop = g.offsetTop - sc.offsetTop - 4;
  }, false);
});
function togglePin(id) {
  var k = LOADOUT.indexOf(id);
  if (k >= 0) { LOADOUT.splice(k, 1); }
  else if (LOADOUT.length < 4) { LOADOUT.push(id); }
  else { status("err", "Massimo 4: togline uno"); return; }
  buildLoadout();
}
/* ricarica degli stratagemmi chiamati dal tablet (tempi approssimativi) */
/* stato dal PC: ricariche in corso + stratagemma inserito ma non ancora lanciato */
function applyCd(st) {
  if (!st) { return; }
  var k, now = Date.now();
  for (k in CD) { if (!(k in st.cd)) { CD[k].end = 0; } }    /* finito/annullato: paintCd lo toglie */
  for (k in st.cd) { CD[k] = {end: now + st.cd[k][0] * 1000, tot: st.cd[k][1]}; }
  PEND = st.p; ARR = st.a || null; NA = st.na || []; USE = st.u || {};
  if (curTab === "hd2") { paintCd(); }
}
applyCd(CD0);
var cdSig = "";
function paintCd() {
  var now = Date.now(), k, i, els, el, left, ov, tx, sig = JSON.stringify([PEND, ARR, NA, USE]);
  if (sig !== cdSig) { cdSig = sig; paintCdStatic(); }
  for (k in CD) {
    left = (CD[k].end - now) / 1000;
    els = document.querySelectorAll('.s[data-id="' + k + '"]');
    for (i = 0; i < els.length; i++) {
      el = els[i]; ov = el.getElementsByClassName("cd")[0]; tx = el.getElementsByClassName("cdt")[0];
      if (left <= 0) { if (ov) { el.removeChild(ov); el.removeChild(tx); } continue; }
      if (!ov) {
        ov = document.createElement("span"); ov.className = "cd"; el.appendChild(ov);
        tx = document.createElement("span"); tx.className = "cdt mono"; el.appendChild(tx);
      }
      ov.style.transform = "scaleY(" + Math.min(1, left / CD[k].tot).toFixed(3) + ")";
      var t = String(left >= 60 ? Math.floor(left / 60) + ":" + ("0" + Math.floor(left % 60)).slice(-2) : Math.ceil(left));
      if (tx.textContent !== t) { tx.textContent = t; }
    }
    if (left <= 0) { delete CD[k]; }
  }
}
function paintCdStatic() {
  [].forEach.call(document.querySelectorAll(".s.pend"), function (e) { if (e.getAttribute("data-id") !== PEND) { cls(e, "pend", false); } });
  if (PEND) { [].forEach.call(document.querySelectorAll('.s[data-id="' + PEND + '"]'), function (e) { cls(e, "pend", true); }); }
  [].forEach.call(document.querySelectorAll("#hd2 .s"), function (e) {
    var id = e.getAttribute("data-id"), u = USE[id], b = e.getElementsByClassName("us")[0];
    cls(e, "na", NA.indexOf(id) >= 0);
    if (!u) { if (b) { e.removeChild(b); } return; }
    if (!b) { b = document.createElement("span"); b.className = "us mono"; e.appendChild(b); }
    var txt = u[0] + "/" + u[1];
    if (b.textContent !== txt) { b.textContent = txt; }
    cls(b, "z", u[0] === 0);
  });
  [].forEach.call(document.querySelectorAll(".s.arr"), function (e) { if (e.getAttribute("data-id") !== ARR) { cls(e, "arr", false); } });
  if (ARR) { [].forEach.call(document.querySelectorAll('.s[data-id="' + ARR + '"]'), function (e) { cls(e, "arr", true); }); }
}
setInterval(function () { if (curTab === "hd2") { paintCd(); } }, 1000);
/* sincronizzazione: in gioco si apre per un attimo il menu stratagemmi e si legge dallo schermo */
document.getElementById("sync").addEventListener("click", function () {
  var b = document.getElementById("sync");
  if (b.classList.contains("on")) { return; }
  cls(b, "on", true); status("", "lettura del menu in gioco...");
  post("/hd2sync", "", function (code, txt) {
    cls(b, "on", false);
    if (code === 200) {
      try { LOADOUT = JSON.parse(txt).ids; } catch (e) {}
      buildLoadout(); paintCd(); status("ok", "Equipaggiamento sincronizzato (" + LOADOUT.length + ")");
    } else {
      status("err", code === 409 ? "Apri prima HELLDIVERS 2 (in missione)" : code === 422 ? "Menu non riconosciuto: immagine salvata per migliorarlo" : code === 0 ? "PC non raggiungibile" : "Errore " + code);
    }
  });
}, false);
function toggleEdit() {
  var ed = document.getElementById("edit");
  if (!editMode) { editMode = true; cls(document.body, "editing", true); ed.textContent = "Fine"; buildLoadout(); return; }
  post("/loadout", "ids=" + encodeURIComponent(LOADOUT.join(",")), function (code) {
    if (code === 200) {
      editMode = false; cls(document.body, "editing", false); ed.textContent = "Modifica";
      status("ok", "Equipaggiamento salvato"); buildLoadout();
    } else { status("err", code === 0 ? "PC non raggiungibile" : "Errore " + code); }
  });
}
document.getElementById("edit").addEventListener("click", toggleEdit, false);
/* impostazioni */
var setEl = document.getElementById("set");
function paintSettings() {
  [].forEach.call(document.querySelectorAll(".seg"), function (seg) {
    [].forEach.call(seg.children, function (o) { cls(o, "sel", SETTINGS[seg.getAttribute("data-k")] === o.getAttribute("data-v")); });
  });
  cls(document.body, "pos-left", SETTINGS.pos === "left"); cls(document.body, "pos-right", SETTINGS.pos === "right");
  cls(document.body, "pos-top", SETTINGS.pos === "top"); cls(document.body, "pos-bottom", SETTINGS.pos === "bottom");
  ["notte", "discord", "term", "rosso", "oled"].forEach(function (t) { cls(document.body, "th-" + t, SETTINGS.theme === t); });
}
[].forEach.call(document.querySelectorAll(".seg div"), function (o) {
  o.addEventListener("click", function () {
    var k = o.parentNode.getAttribute("data-k"), v = o.getAttribute("data-v"), old = SETTINGS[k];
    SETTINGS[k] = v; paintSettings();
    post("/settings", k + "=" + encodeURIComponent(v), function (code, txt) {
      if (code === 200) {
        status("ok", "Impostazione salvata");
        try { cfgRev = JSON.parse(txt).rev; } catch (e) {}   /* modifica nostra: niente aggiornamento doppio */
      }
      else { SETTINGS[k] = old; paintSettings(); status("err", code === 0 ? "PC non raggiungibile" : "Errore " + code); }
    });
  }, false);
});
/* impostazioni aperte: sotto non si disegna niente (il tablet ha una GPU debole: niente strati trasparenti sovrapposti) */
function setOpen(on) { cls(setEl, "show", on); cls(document.body, "setopen", on); }
document.getElementById("gear").addEventListener("click", function () { setOpen(true); setTab("fav"); }, false);
function setTab(n) {
  [].forEach.call(document.querySelectorAll(".stab"), function (t) { cls(t, "sel", t.getAttribute("data-sp") === n); });
  [].forEach.call(document.querySelectorAll(".spn"), function (p) { cls(p, "show", p.id === "sp_" + n); });
  if (n === "fav") { favLoad(); }
  if (n === "dc") { dcSetPaint(); }
  if (n === "td") { document.getElementById("tdinfo").textContent = location.host; updPost("status"); }
}
/* aggiornamenti (POST /update): stato, controllo su GitHub, aggiorna / torna indietro */
var UPD = null;
function updPaint() {
  var j = UPD, t;
  if (!j) { return; }
  t = "TabDeck " + j.cur;
  if (!j.repo) { t += " · aggiornamenti non configurati"; }
  else if (j.newer) { t += " · disponibile la " + j.latest; }
  else if (j.latest) { t += " · sei aggiornato"; }
  setText(document.getElementById("updst"), t);
  setText(document.getElementById("updnotes"), j.newer ? j.notes : "");
  document.getElementById("updchk").style.display = j.repo ? "" : "none";
  document.getElementById("updgo").style.display = j.newer ? "" : "none";
  document.getElementById("updback").style.display = j.backup ? "" : "none";
  cls(document.getElementById("gear"), "upd", !!j.newer);
}
function updResult(r) {
  if (!r) { return; }
  if (r.ok) { status("ok", r.from === r.to ? "TabDeck " + r.to : "TabDeck aggiornato: ora " + r.to); }
  else { status("err", "Aggiornamento non riuscito: " + r.error); }
}
function updPost(a, cb) {
  post("/update", "a=" + a, function (code, txt) {
    var j = null;
    try { j = JSON.parse(txt); } catch (e) {}
    if (code !== 200 || !j) { status("err", code === 0 ? "PC non raggiungibile" : "Errore " + code); return; }
    if (j.error) { status("err", j.error); return; }
    if (j.cur) { UPD = j; updPaint(); }
    if (cb) { cb(j); }
  }, a === "status" ? 4000 : 45000);
}
document.getElementById("updchk").addEventListener("click", function () {
  status("", "Controllo su GitHub...");
  updPost("check", function (j) { status("ok", j.newer ? "Nuova versione " + j.latest : "Sei aggiornato"); });
}, false);
document.getElementById("updgo").addEventListener("click", function () {
  if (!UPD || !UPD.newer) { return; }
  if (!confirm("Aggiornare TabDeck alla " + UPD.latest + "? Le tue impostazioni restano; la versione attuale viene salvata e, se la nuova non parte, viene ripristinata da sola.")) { return; }
  status("", "Scarico la " + UPD.latest + "...");
  updPost("apply", function () { status("", "Aggiornamento in corso..."); setOpen(false); setTimeout(function () { location.reload(); }, 20000); });
}, false);
document.getElementById("updback").addEventListener("click", function () {
  if (!confirm("Tornare alla versione precedente di TabDeck? Le tue impostazioni restano.")) { return; }
  updPost("rollback", function () { status("", "Ritorno alla versione precedente..."); setOpen(false); setTimeout(function () { location.reload(); }, 15000); });
}, false);
updPost("status", function (j) { updResult(j.result); });
[].forEach.call(document.querySelectorAll(".stab"), function (t) {
  t.addEventListener("click", function () { setTab(t.getAttribute("data-sp")); }, false);
});
/* editor delle righe (Preferiti / Sistema / Strumenti): modifiche locali finche' non si preme Salva.
   Per restare veloce sul tablet: un tocco cambia solo le classi; le liste si ricostruiscono solo quando cambia cosa c'e' nella riga. */
var ED = null, edRow = "avvio", edSel = -1, edOrig = "", RIDS = ["avvio", "sistema", "strumenti"], ROWN = {avvio: "Preferiti", sistema: "Sistema", strumenti: "Strumenti"};
var favrow = document.getElementById("favrow"), favact = document.getElementById("favact"), favsave = document.getElementById("favsave"), faedit = document.getElementById("faedit");
var EDL = {adkeys: "keys", favopen: "open", favknown: "apps", adspec: "spec"};
function lid(x) { return x.k ? "x:" + x.k : x.id; }
function edKey() { return ED ? RIDS.map(function (r) { return ED.rows[r].map(function (f) { return f.id; }).join(","); }).join("|") : ""; }
function edSet(j) {   /* nuovi dati dal PC: liste sempre, righe solo se richiesto */
  ED.lists = {keys: j.keys, open: j.open, apps: j.apps, spec: j.spec};
  ED.max = j.max;
}
function favLoad() {
  dcGet("/layout", function (code, j) {
    if (code !== 200 || !j) { status("err", "Errore " + code); return; }
    ED = {rows: j.rows}; edSet(j);
    edOrig = edKey(); edPaintRow(); edPaintLists(); edPaintBar();
  });
}
function edPaintRow() {
  edSel = -1;
  favrow.innerHTML = ED.rows[edRow].map(function (f, i) { return '<div class="fi" data-i="' + i + '">' + f.h + "</div>"; }).join("") ||
    '<div class="od">Riga vuota: aggiungi qui sotto.</div>';
}
function edPaintLists() {
  var inRow = {};
  ED.rows[edRow].forEach(function (f) { inRow[f.id] = 1; });
  Object.keys(EDL).forEach(function (box) {
    document.getElementById(box).innerHTML = ED.lists[EDL[box]].filter(function (x) { return !inRow[lid(x)]; }).map(function (x) {
      return '<div class="fi" data-add="' + lid(x) + '">' + x.h + (x.edit ? '<span class="fe" data-edit="' + x.id + '">✎</span>' : "") + "</div>";
    }).join("") || '<div class="od">Niente da aggiungere.</div>';
  });
}
function edIsMine(id) { return ED.lists.keys.some(function (k) { return k.id === id && k.edit; }); }
function edPaintBar() {
  var cur = edSel >= 0 ? ED.rows[edRow][edSel] : null;
  cls(favact, "show", !!cur);
  cls(faedit, "hide", !(cur && edIsMine(cur.id)));
  cls(favsave, "dirty", edKey() !== edOrig);
}
function edSelect(i) {
  var els = favrow.children;
  if (edSel >= 0 && els[edSel]) { cls(els[edSel], "sel", false); }
  edSel = edSel === i ? -1 : i;
  if (edSel >= 0 && els[edSel]) { cls(els[edSel], "sel", true); }
  edPaintBar();
}
function edReindex() { [].forEach.call(favrow.children, function (el, i) { el.setAttribute("data-i", i); }); }
var favNoClick = false;   /* il clic che chiude un trascinamento col mouse non e' una selezione */
favrow.addEventListener("click", function (e) {
  if (favNoClick) { favNoClick = false; return; }
  var fi = e.target.closest(".fi"); if (fi && ED) { edSelect(+fi.getAttribute("data-i")); }
}, false);
/* trascinare un riquadro della riga lo sposta (le frecce restano). Un tocco senza movimento = selezione, come prima.
   Il dito su un riquadro non fa scorrere le impostazioni: per scorrere si tocca fuori dalla riga. */
(function () {
  var d = null, tT = 0;
  function start(target, x, y) {
    var fi = target.closest && target.closest(".fi"), r;
    if (!fi || !ED) { d = null; return; }
    r = fi.getBoundingClientRect();
    d = {el: fi, x0: x, y0: y, dx: x - r.left, dy: y - r.top, w: r.width, h: r.height, g: null};
  }
  favrow.addEventListener("touchstart", function (e) {
    tT = Date.now();
    if (d && d.g) { return; }   /* trascinamento in corso: il dito in piu' si ignora */
    if (e.touches.length !== 1) { d = null; return; }
    start(e.target, e.touches[0].clientX, e.touches[0].clientY);
  }, false);
  favrow.addEventListener("touchmove", function (e) {
    if (!d) { return; }
    if (e.cancelable) { e.preventDefault(); }
    move(e.touches[0]);
  }, false);
  favrow.addEventListener("mousedown", function (e) {
    if (e.button !== 0 || Date.now() - tT < 800 || !(e.target.closest && e.target.closest(".fi"))) { return; }
    e.preventDefault();   /* niente trascinamento dell'immagine ne' selezione del testo */
    start(e.target, e.clientX, e.clientY);
  }, false);
  document.addEventListener("mousemove", function (e) { if (d) { move(e); } }, false);
  document.addEventListener("mouseup", function () {
    if (!d) { return; }
    if (d.g) { favNoClick = true; setTimeout(function () { favNoClick = false; }, 0); }
    end(null);
  }, false);
  function move(p) {
    var t, o, r;
    if (!d.g) {
      if (Math.abs(p.clientX - d.x0) < 8 && Math.abs(p.clientY - d.y0) < 8) { return; }
      d.g = d.el.cloneNode(true); d.g.id = "fghost"; d.g.style.width = d.w + "px"; d.g.style.height = d.h + "px";
      document.body.appendChild(d.g); cls(d.el, "fdrag", true);
    }
    d.g.style.left = (p.clientX - d.dx) + "px"; d.g.style.top = (p.clientY - d.dy) + "px";
    t = document.elementFromPoint(p.clientX, p.clientY);
    o = t && t.closest && t.closest("#favrow > .fi");
    if (!o || o === d.el) { return; }
    r = o.getBoundingClientRect();
    favrow.insertBefore(d.el, p.clientX < r.left + r.width / 2 ? o : o.nextSibling);
  }
  function end(e) {
    if (!d) { return; }
    var moved = !!d.g, L, sel;
    if (moved) {
      if (e && e.cancelable) { e.preventDefault(); }   /* niente "click": era uno spostamento, non una selezione */
      d.g.parentNode.removeChild(d.g); cls(d.el, "fdrag", false);
      L = ED.rows[edRow];
      ED.rows[edRow] = [].map.call(favrow.children, function (el) { return L[+el.getAttribute("data-i")]; });
      sel = favrow.querySelector(".fi.sel");
      edReindex();
      edSel = sel ? +sel.getAttribute("data-i") : -1;
      edPaintBar();
    }
    d = null;
  }
  favrow.addEventListener("touchend", end, false);
  favrow.addEventListener("touchcancel", end, false);
})();
document.getElementById("rsel").addEventListener("click", function (e) {
  var d = e.target.closest("[data-r]"); if (!d || !ED) { return; }
  edRow = d.getAttribute("data-r");
  [].forEach.call(this.children, function (c) { cls(c, "sel", c === d); });
  edPaintRow(); edPaintLists(); edPaintBar();
}, false);
function edAdd(id, src) {
  var L = ED.rows[edRow], r, k;
  if (L.length >= ED.max) { status("err", "Massimo " + ED.max + " riquadri per riga"); return; }
  for (k = 0; k < RIDS.length; k++) {   /* un riquadro sta in una sola riga: aggiungerlo qui lo sposta */
    r = RIDS[k];
    if (r !== edRow) { ED.rows[r] = ED.rows[r].filter(function (f) { if (f.id === id) { status("", "Spostato da " + ROWN[r]); return false; } return true; }); }
  }
  L.push({id: id, h: src.h});
  edPaintRow(); edPaintLists(); edSelect(L.length - 1);
}
function edAddClick(e) {
  if (!ED) { return; }
  var ed = e.target.closest("[data-edit]");
  if (ed) { e.stopPropagation(); keOpen(ed.getAttribute("data-edit")); return; }
  var fi = e.target.closest(".fi"); if (!fi) { return; }
  var id = fi.getAttribute("data-add"), all = ED.lists.keys.concat(ED.lists.open, ED.lists.apps, ED.lists.spec);
  var src = all.filter(function (x) { return lid(x) === id; })[0];
  if (src) { edAdd(id, src); }
}
Object.keys(EDL).forEach(function (box) { document.getElementById(box).addEventListener("click", edAddClick, false); });
[].forEach.call(favact.children, function (b) {
  b.addEventListener("click", function () {
    if (edSel < 0) { return; }
    var a = b.getAttribute("data-fa"), L = ED.rows[edRow], els = favrow.children, t, j;
    if (a === "edit") { keOpen(L[edSel].id); return; }
    if (a === "del") {
      L.splice(edSel, 1); favrow.removeChild(els[edSel]); edSel = -1; edReindex();
      if (!L.length) { edPaintRow(); }
      edPaintLists(); edPaintBar(); return;
    }
    j = a === "left" ? edSel - 1 : edSel + 1;
    if (j < 0 || j >= L.length) { return; }
    t = L[edSel]; L[edSel] = L[j]; L[j] = t;   /* scambio dei due nodi, senza ricostruire */
    if (a === "left") { favrow.insertBefore(els[edSel], els[j]); } else { favrow.insertBefore(els[j], els[edSel]); }
    edSel = j; edReindex(); edPaintBar();
  }, false);
});
document.getElementById("favundo").addEventListener("click", function () { edRow = edRow; favLoad(); }, false);
document.getElementById("favok").addEventListener("click", function () {
  var body = RIDS.map(function (r) { return r + "=" + encodeURIComponent(ED.rows[r].map(function (f) { return f.id; }).join(",")); }).join("&");
  post("/layout", body, function (code, txt) {
    if (code === 200) { refreshGeneral(function () { status("ok", "Pulsanti salvati"); favLoad(); }); }
    else { status("err", txt && code !== 0 ? txt : code === 0 ? "PC non raggiungibile" : "Errore " + code); }
  });
}, false);
/* scorciatoie personali: nome, modificatori + un tasto, icona */
var KE = null, kedit = document.getElementById("kedit");
function keOpen(id) {
  var k = id ? ED.lists.keys.filter(function (x) { return x.id === id && x.edit; })[0] : null;
  KE = {id: k ? k.id : "", mods: {}, key: "", icon: k ? (k.icon || "") : ""};
  if (k) { k.keys.forEach(function (x, i) { if (i < k.keys.length - 1) { KE.mods[x] = 1; } else { KE.key = x; } }); }
  document.getElementById("kename").value = k ? k.label : "";
  document.getElementById("kehd").textContent = k ? "Modifica scorciatoia" : "Nuova scorciatoia";
  cls(document.getElementById("kedel"), "hide", !k);
  kePaint(); cls(kedit, "show", true); kedit.scrollTop = 0;
}
function keKeys() { return ["CTRL", "SHIFT", "ALT", "WIN"].filter(function (m) { return KE.mods[m]; }).concat(KE.key ? [KE.key] : []); }
function kePaint() {
  [].forEach.call(document.querySelectorAll("#kmods div"), function (d) { cls(d, "sel", !!KE.mods[d.getAttribute("data-m")]); });
  [].forEach.call(document.querySelectorAll("#kkeys div"), function (d) { cls(d, "sel", d.getAttribute("data-k") === KE.key); });
  [].forEach.call(document.querySelectorAll("#kicons div"), function (d) { cls(d, "sel", d.getAttribute("data-i") === KE.icon); });
  setText(document.getElementById("keprev"), keKeys().map(function (x) {
    var el = document.querySelector('#kmods [data-m="' + x + '"], #kkeys [data-k="' + x + '"]'); return el ? el.textContent : x;
  }).join(" + ") || "scegli i tasti");
}
document.getElementById("kmods").addEventListener("click", function (e) { var d = e.target.closest("[data-m]"); if (d) { var m = d.getAttribute("data-m"); KE.mods[m] = !KE.mods[m]; kePaint(); } }, false);
document.getElementById("kkeys").addEventListener("click", function (e) { var d = e.target.closest("[data-k]"); if (d) { KE.key = d.getAttribute("data-k"); kePaint(); } }, false);
document.getElementById("kicons").addEventListener("click", function (e) { var d = e.target.closest("[data-i]"); if (d) { KE.icon = d.getAttribute("data-i"); kePaint(); } }, false);
document.getElementById("kecancel").addEventListener("click", function () { cls(kedit, "show", false); }, false);
function keDone(j, isNew) {   /* aggiorna liste e riquadri gia' nelle righe, senza perdere le modifiche non salvate */
  var all = {};
  edSet(j);
  RIDS.forEach(function (r) { j.rows[r].forEach(function (f) { all[f.id] = f.h; }); });
  j.keys.forEach(function (k) { all[k.id] = k.h; });
  RIDS.forEach(function (r) { ED.rows[r] = ED.rows[r].filter(function (f) { return f.id.indexOf("k_") !== 0 || all[f.id]; }).map(function (f) { return all[f.id] ? {id: f.id, h: all[f.id]} : f; }); });
  cls(kedit, "show", false);
  if (isNew && j["new"] && ED.rows[edRow].length < ED.max) { edAdd(j["new"], {h: all[j["new"]]}); status("ok", "Scorciatoia creata e aggiunta: premi Salva"); }
  else { edPaintRow(); edPaintLists(); edPaintBar(); }
}
document.getElementById("kesave").addEventListener("click", function () {
  var name = document.getElementById("kename").value.trim();
  if (!name) { status("err", "Scrivi un nome"); return; }
  if (!KE.key) { status("err", "Scegli un tasto"); return; }
  var isNew = !KE.id;
  post("/layout", "a=key&id=" + encodeURIComponent(KE.id) + "&label=" + encodeURIComponent(name) + "&keys=" + encodeURIComponent(keKeys().join("+")) +
    "&icon=" + encodeURIComponent(KE.icon), function (code, txt) {
    if (code !== 200) { status("err", code === 0 ? "PC non raggiungibile" : "Errore " + code); return; }
    try { keDone(JSON.parse(txt), isNew); } catch (e) {}
    refreshGeneral();
  });
}, false);
document.getElementById("kedel").addEventListener("click", function () {
  if (!KE.id) { return; }
  post("/layout", "a=delkey&id=" + encodeURIComponent(KE.id), function (code, txt) {
    if (code !== 200) { status("err", "Errore " + code); return; }
    try { keDone(JSON.parse(txt), false); status("ok", "Scorciatoia eliminata"); } catch (e) {}
    refreshGeneral();
  });
}, false);
document.getElementById("newkey").addEventListener("click", function () { if (ED) { keOpen(null); } }, false);
/* Discord e TabDeck */
function dcSetPaint() {
  var t = DC.s === "ok" ? "Collegato" + (DC.mute ? " · muto" : "") + (DC.deaf ? " · cuffie off" : "") :
    DC.s === "auth" ? "Da autorizzare (sezione Discord)" : DC.s === "wait" ? "In attesa del popup su Discord" : (DC.msg || "Non collegato");
  document.getElementById("dcsetst").textContent = t;
}
[].forEach.call(document.querySelectorAll("[data-sa]"), function (b) {
  b.addEventListener("click", function () {
    var a = b.getAttribute("data-sa");
    if (a === "reload") { location.reload(); return; }
    if (a === "restart") {
      post("/restart", "", function (code) {
        if (code !== 200) { status("err", "Errore " + code); return; }
        status("", "Riavvio TabDeck..."); setOpen(false);
        setTimeout(function () { location.reload(); }, 9000);
      });
      return;
    }
    post("/discord", "a=" + a, function (code, txt) {
      if (code !== 200) { status("err", "Errore " + code); return; }
      try { DC = JSON.parse(txt); } catch (e) {}
      status("ok", a === "logout" ? "TabDeck scollegato da Discord" : "Conferma il popup di Discord sul PC");
      setTimeout(function () { dcGet("/dc", function (c, j) { if (j) { DC = j.st; dcSetPaint(); paintDc(); } }); }, 1500);
      dcSetPaint();
    });
  }, false);
});
document.getElementById("setclose").addEventListener("click", function () { setOpen(false); }, false);
setEl.addEventListener("click", function (e) { if (e.target === setEl) { setOpen(false); } }, false);
paintSettings();
/* scheda Audio: brano in riproduzione (sessione multimediale di Windows) + volume per singola app */
var MIX = {}, mixKey = "", coverKey = null, audioBusy = false, stripsEl = document.getElementById("strips"), npEl = document.getElementById("np");
var NP = {dur: 0, pos: 0, t0: 0, play: false}, npAppKey = "";
var MUTE_SVG = '__SVG_mute__', MASTER_SVG = '__SVG_vol_up__', SYS_SVG = '__SVG_monitor__';
function $(id) { return document.getElementById(id); }
function fmt(s) {
  s = Math.max(0, Math.floor(s));
  var h = Math.floor(s / 3600), m = Math.floor(s / 60) % 60, r = s % 60;
  return (h ? h + ":" + (m < 10 ? "0" : "") : "") + m + ":" + (r < 10 ? "0" : "") + r;
}
function npNow() { return Math.min(NP.dur, NP.pos + (NP.play ? (Date.now() - NP.t0) / 1000 : 0)); }
function paintNP() {
  if (!NP.dur) { return; }
  var p = npNow();
  $("npfill").style.transform = "scaleX(" + (p / NP.dur) + ")";
  $("npp").textContent = fmt(p);
}
function setCover(c) {
  if (c === coverKey) { return; }
  coverKey = c;
  var box = $("npc"), old = box.getElementsByTagName("img")[0];
  if (old) { box.removeChild(old); }
  if (c) {
    var img = new Image();
    img.onerror = function () { if (img.parentNode) { img.parentNode.removeChild(img); } };
    img.src = "/cover/" + c; box.appendChild(img);
  }
}
function setPlaying(on) { NP.play = on; cls(npEl, "playing", on); }
function renderNP(m) {
  var on = !!(m && m.on);
  cls(npEl, "off", !on);
  if (!on) {
    $("npt").textContent = "Niente in riproduzione"; $("npa").textContent = "";
    setCover(null); setPlaying(false); NP.dur = 0; cls(npEl, "nodur", true); return;
  }
  $("npt").textContent = m.t || "(senza titolo)";
  $("npa").textContent = (m.a || "") + (m.al && m.al !== m.t ? " · " + m.al : "");
  var ak = m.i + "|" + m.an;
  if (ak !== npAppKey) {
    npAppKey = ak;
    $("npapp").innerHTML = (m.i ? '<img src="/appicon/' + m.i + '.png" alt="">' : "") + "<span>" + esc(m.an) + "</span>";
  }
  NP.dur = m.dur; NP.pos = m.pos; NP.t0 = Date.now(); setPlaying(m.st === "play");
  cls(npEl, "nodur", !m.dur);
  $("npd").textContent = fmt(m.dur); paintNP();
  setCover(m.c);
}
function mediaCmd(el) {
  var cmd = el.getAttribute("data-mc");
  cls(el, "on", true);
  post("/media", "cmd=" + cmd, function (code) {
    flash(el, code === 200 ? "ok" : "err");
    if (code === 200) {
      if (cmd === "toggle") { NP.pos = npNow(); NP.t0 = Date.now(); setPlaying(!NP.play); }
      setTimeout(loadAudio, 500);
    } else { status("err", code === 409 ? "L'app ha rifiutato il comando" : code === 0 ? "PC non raggiungibile" : "Errore " + code); }
  });
}
/* tocco sulla barra = salta a quel punto */
(function () {
  var bar = $("npbar"), sx = 0, sy = 0;
  function seek(x) {
    if (!NP.dur) { return; }
    var r = bar.getBoundingClientRect(), p = Math.max(0, Math.min(1, (x - r.left) / r.width)) * NP.dur;
    NP.pos = p; NP.t0 = Date.now(); paintNP();
    post("/media", "pos=" + p.toFixed(1), function (code) {
      if (code !== 200) { status("err", code === 409 ? "Quest'app non permette di saltare" : "Errore " + code); }
      setTimeout(loadAudio, 500);
    });
  }
  bar.addEventListener("touchstart", function (e) { var t = e.touches[0]; sx = t.clientX; sy = t.clientY; }, {passive: true});
  bar.addEventListener("touchend", function (e) {
    var t = e.changedTouches[0];
    if (e.cancelable) { e.preventDefault(); }
    if (!multiActive && Math.abs(t.clientY - sy) < 20) { seek(t.clientX); }
  }, false);
  bar.addEventListener("click", function (e) { seek(e.clientX); }, false);
})();
function paintStrip(s) {
  if (s.raf) { return; }
  s.raf = true;
  requestAnimationFrame(function () {
    s.raf = false;
    s.fill.style.transform = "scaleY(" + (s.vol / 100) + ")";
    s.knob.style.transform = "translateY(" + (-s.vol) + "%)";
    s.val.textContent = s.vol;
    cls(s.el, "muted", s.mute);
  });
}
function stripPost(s, body) {
  s.lastSent = Date.now(); s.inflight = true;
  post(s.k === "master" ? "/volume" : "/appvol", (s.k === "master" ? "" : "k=" + s.k + "&") + body, function (code) {
    s.inflight = false;
    if (code !== 200) {
      status("err", code === 0 ? "PC non raggiungibile" : code === 404 ? "App chiusa" : "Errore volume " + code);
      if (code === 404) { mixKey = ""; loadAudio(); }
      return;
    }
    if (s.want) { stripPush(s); }
  });
  if (s.k === "master") { VOL = {vol: s.vol, mute: s.mute}; lastSent = Date.now(); paintVol(); }
}
function stripPush(s) {
  if (s.inflight) { s.want = true; return; }
  s.want = false; stripPost(s, "vol=" + s.vol);
}
function stripSet(s, y) {
  var v = Math.max(0, Math.min(100, Math.round((s.rect.bottom - y) / s.rect.height * 100)));
  if (v !== s.vol) { s.vol = v; paintStrip(s); stripPush(s); }
}
function makeStrip(el) {
  var s = {k: el.getAttribute("data-k"), el: el, vol: -1, mute: false, drag: false, inflight: false, want: false, lastSent: 0, raf: false,
           fill: el.querySelector(".mff"), knob: el.querySelector(".mfk"), val: el.querySelector(".msv")};
  var f = el.querySelector(".mf");
  f.addEventListener("touchstart", function (e) {
    e.preventDefault();
    if (e.touches.length > 1) { s.drag = false; return; }
    s.drag = true; s.rect = f.getBoundingClientRect(); stripSet(s, e.touches[0].clientY);
  }, {passive: false});
  f.addEventListener("touchmove", function (e) { e.preventDefault(); if (s.drag && !multiActive) { stripSet(s, e.touches[0].clientY); } }, {passive: false});
  f.addEventListener("touchend", function (e) { e.preventDefault(); if (s.drag) { s.drag = false; stripPush(s); } }, {passive: false});
  f.addEventListener("mousedown", function (e) { s.drag = true; s.rect = f.getBoundingClientRect(); stripSet(s, e.clientY); }, false);
  document.addEventListener("mousemove", function (e) { if (s.drag && e.buttons) { stripSet(s, e.clientY); } }, false);
  document.addEventListener("mouseup", function () { if (s.drag) { s.drag = false; stripPush(s); } }, false);
  el.querySelector(".mm").addEventListener("click", function () {
    s.mute = !s.mute; paintStrip(s); stripPost(s, "mute=" + (s.mute ? 1 : 0));
  }, false);
  return s;
}
/* scorrimento orizzontale delle colonne fatto a mano (quello nativo su Chrome 81 non parte):
   si trascina fuori dai fader; un dito solo, cosi' il gesto a due dita cambia ancora sezione */
(function () {
  var sx = 0, sy = 0, sl = 0, mode = 0;   /* 0 = da decidere, 1 = scorre, -1 = ignora */
  stripsEl.addEventListener("touchstart", function (e) {
    var t = e.touches[0];
    mode = e.touches.length > 1 || (e.target.closest && e.target.closest(".mf")) ? -1 : 0;
    sx = t.clientX; sy = t.clientY; sl = stripsEl.scrollLeft;
  }, {passive: true});
  stripsEl.addEventListener("touchmove", function (e) {
    if (mode < 0 || multiActive || e.touches.length > 1) { mode = -1; return; }
    var t = e.touches[0], dx = t.clientX - sx;
    if (mode === 0 && Math.abs(dx) > 8) { mode = 1; }
    if (mode === 1) { if (e.cancelable) { e.preventDefault(); } stripsEl.scrollLeft = sl - dx; }
  }, {passive: false});
  /* dopo uno scorrimento il dito si alza magari su "muto": niente click */
  stripsEl.addEventListener("touchend", function (e) { if (mode === 1 && e.cancelable) { e.preventDefault(); } }, false);
})();
function renderMix(apps, master) {
  var list = (master ? [{k: "master", n: "Generale", i: "", vol: master.vol, mute: master.mute, on: true}] : []).concat(apps || []);
  var key = list.map(function (a) { return a.k + ":" + a.n; }).join("|"), k;
  if (key !== mixKey) {
    for (k in MIX) { if (MIX[k].drag) { return; } }   /* non ricostruire sotto il dito */
    mixKey = key; MIX = {};
    stripsEl.innerHTML = list.map(function (a) {
      var mono = a.n.replace(/[^A-Za-z0-9]/g, "").slice(0, 2).toUpperCase() || "?";
      var ic = a.k === "master" ? MASTER_SVG : a.k === "system" ? SYS_SVG : "<span>" + esc(mono) + "</span>";
      return '<div class="ms' + (a.k === "master" ? " master" : "") + '" data-k="' + a.k + '" style="--wc:' +
        (a.k === "master" ? "var(--amber)" : "hsl(" + hue(a.n.toLowerCase()) + ",65%,62%)") + '"><div class="msi">' + ic +
        '</div><div class="msn">' + esc(a.n) + '</div><div class="msv mono">--</div><div class="mf"><div class="mff"></div><div class="mfk"><i></i></div></div>' +
        '<div class="mm">' + MUTE_SVG + "</div></div>";
    }).join("");
    [].forEach.call(stripsEl.getElementsByClassName("ms"), function (el) {
      var s = makeStrip(el); MIX[s.k] = s;
    });
    list.forEach(function (a) {
      if (!a.i) { return; }
      var box = MIX[a.k].el.querySelector(".msi"), img = new Image();
      img.onload = function () { box.firstChild.style.visibility = "hidden"; box.appendChild(img); };
      img.src = "/appicon/" + a.i + ".png";
    });
  }
  list.forEach(function (a) {
    var s = MIX[a.k];
    cls(s.el, "idle", !a.on);
    if (!s.drag && !s.inflight && Date.now() - s.lastSent > 1500) { s.vol = a.vol; s.mute = a.mute; paintStrip(s); }
  });
}
/* microfono di Windows: il PC resta la fonte di verita' */
var micEls = [document.getElementById("vmic"), document.getElementById("smic")].filter(function (e) { return e; }), micBusy = false, micSent = 0;
function micCls(c, on) { micEls.forEach(function (el) { cls(el, c, on); }); }
function renderMic(m) {
  micCls("na", !m);
  if (m && !micBusy && Date.now() - micSent > 1500) { micCls("off", m.mute); }
}
function micTap(micEl) {
  if (micBusy || micEl.classList.contains("na")) { return; }
  var want = !micEl.classList.contains("off");
  micBusy = true; micSent = Date.now(); micCls("off", want); micCls("busy", true);
  post("/mic", "mute=" + (want ? 1 : 0), function (code, txt) {
    micBusy = false; micCls("busy", false);
    if (code !== 200) { micCls("off", !want); status("err", code === 0 ? "PC non raggiungibile" : "Errore microfono " + code); return; }
    try { var m = JSON.parse(txt).mute; micCls("off", m); status("ok", m ? "Microfono muto" : "Microfono attivo"); } catch (e) {}
  });
}
micEls[0].addEventListener("click", function () { micTap(micEls[0]); }, false);
/* Discord (RPC): s = off | auth | wait | ok */
var DC = {s: "off"}, dcSent = 0, dcM = document.getElementById("vdmute"), dcD = document.getElementById("vddeaf");
function dcLabel(el, t) { el.querySelector(".vl").textContent = t; }
function paintDc() {
  var ok = DC.s === "ok", ask = DC.s === "auth" || DC.s === "wait";
  [dcM, dcD].forEach(function (el) { cls(el, "na", !ok && !ask); cls(el, "ask", ask); });
  cls(dcM, "off", ok && (DC.mute || DC.deaf)); cls(dcD, "off", ok && DC.deaf);
  dcLabel(dcM, ok ? "Discord" : DC.s === "auth" ? "Autorizza" : DC.s === "wait" ? "Vedi PC" : "Discord");
  dcLabel(dcD, ok ? "Cuffie" : DC.s === "off" ? (DC.msg === "Discord chiuso" ? "Chiuso" : "Cuffie") : "Discord");
}
function renderDc(d) {
  if (!d || Date.now() - dcSent < 1500) { return; }
  DC = d; paintDc();
}
function dcPost(body) {
  dcSent = Date.now();
  post("/discord", body, function (code, txt) {
    if (code !== 200) { status("err", code === 0 ? "PC non raggiungibile" : "Errore Discord " + code); return; }
    try { DC = JSON.parse(txt); paintDc(); } catch (e) {}
  });
}
function dcTap(deafBtn) {
  if (DC.s === "auth") { DC.s = "wait"; paintDc(); dcPost("a=auth"); return; }
  if (DC.s !== "ok") { return; }
  if (deafBtn) { DC.deaf = !DC.deaf; dcPost("deaf=" + (DC.deaf ? 1 : 0)); }
  else if (DC.mute || DC.deaf) { DC.mute = false; DC.deaf = false; dcPost("mute=0&deaf=0"); }
  else { DC.mute = true; dcPost("mute=1"); }
  paintDc();
}
dcM.addEventListener("click", function () { dcTap(false); }, false);
dcD.addEventListener("click", function () { dcTap(true); }, false);
/* ---- sezione Discord: server (sinistra), canali vocali (centro), chiamata (destra) ---- */
var DCV = null, dcGuild = null, dcGuilds = [], dcGuildAt = 0, dcGKey = "", dcCKey = "", dcMKey = "", dcPolling = false, dcChBusy = false, dcTick = 0;
var dcPane = document.getElementById("dc"), dcgEl = document.getElementById("dcg"), dclEl = document.getElementById("dclist");
var dcmEl = document.getElementById("dcmem"), dcvn = document.getElementById("dcvname"), dcLeave = document.getElementById("dcleave");
var dcBM = document.getElementById("dcbm"), dcBD = document.getElementById("dcbd"), dcObtn = document.getElementById("dcobtn");
var SPK_SVG = '__SVG_vol_up__', MICOFF_SVG = '__SVG_mic_off__', HSOFF_SVG = '__SVG_headset_off__';
try { dcGuild = localStorage.getItem("tabdeck_dcg"); } catch (e) {}
function dcGet(path, cb) {
  var x = new XMLHttpRequest();
  x.open("GET", path + (path.indexOf("?") < 0 ? "?" : "&") + "_=" + Date.now(), true);
  x.setRequestHeader("X-Token", TOKEN); if (DEVICE) { x.setRequestHeader("X-Device", DEVICE); }
  x.timeout = 15000;
  x.onreadystatechange = function () {
    if (x.readyState !== 4) { return; }
    var j = null; try { j = JSON.parse(x.responseText); } catch (e) {}
    cb(x.status, j);
  };
  x.send();
}
function avatar(u) { return u.av ? "https://cdn.discordapp.com/avatars/" + u.id + "/" + u.av + ".png?size=64" : ""; }
function pic(url, n) {
  var ini = (n || "?").replace(/[^A-Za-z0-9]/g, "").slice(0, 2).toUpperCase() || "?";
  return '<span class="dpic" style="--wc:hsl(' + hue((n || "").toLowerCase()) + ',60%,62%)"><span>' + esc(ini) + "</span>" +
    (url ? '<img src="' + esc(url) + '" alt="" onload="this.previousSibling.style.visibility=\'hidden\'" onerror="this.parentNode.removeChild(this)">' : "") + "</span>";
}
var dcinv = document.getElementById("dcinv"), dcinvv = document.getElementById("dcinvv"), invT = null, invSent = 0;
function paintInv() {
  if (Date.now() - invSent < 2000 || typeof DC.inv !== "number") { return; }
  if (+dcinv.value !== DC.inv) { dcinv.value = DC.inv; }
  setText(dcinvv, DC.inv + "%");
}
function invPost() { post("/discord", "inv=" + dcinv.value, function (code) { if (code !== 200) { status("err", "Errore Discord " + code); } }); }
dcinv.addEventListener("input", function () {
  invSent = Date.now(); setText(dcinvv, dcinv.value + "%");
  if (invT) { return; }
  invT = setTimeout(function () { invT = null; invPost(); }, 200);
}, false);
dcinv.addEventListener("change", function () { invSent = Date.now(); invPost(); }, false);
function dcPaintState() {
  var ok = DC.s === "ok";
  paintInv();
  cls(dcPane, "dcok", ok);
  cls(dcBM, "off", ok && (DC.mute || DC.deaf)); cls(dcBD, "off", ok && DC.deaf);
  if (!ok) {
    dcPane.querySelector(".dcmsg").textContent = DC.s === "auth" ? "TabDeck va autorizzato in Discord" :
      DC.s === "wait" ? "Conferma il popup di Discord sul PC" : DC.msg === "da configurare" ? "Discord non configurato" : "Discord è chiuso";
    var auth = DC.s === "auth";
    dcObtn.setAttribute("data-dca", auth ? "auth" : "open");
    dcObtn.querySelector(".l").textContent = auth ? "Autorizza" : DC.s === "wait" ? "Attendo..." : "Apri Discord";
  }
}
function renderGuilds() {
  var key = JSON.stringify([dcGuilds, dcGuild, DCV && DCV.g]);
  if (key === dcGKey || dcgEl.querySelector(".on")) { return; }
  dcGKey = key;
  dcgEl.innerHTML = dcGuilds.map(function (g) {
    return '<button class="dg' + (g.id === dcGuild ? " sel" : "") + (DCV && DCV.g === g.id ? " live" : "") + '" data-dcg="' + esc(g.id) +
      '" data-n="' + esc(g.n) + '">' + pic(g.i, g.n) + "</button>";
  }).join("");
  [].forEach.call(dcgEl.getElementsByClassName("dg"), bind);
}
function renderCh(list) {
  var key = JSON.stringify([list, DCV && DCV.id]);
  if (key === dcCKey || dclEl.querySelector(".on")) { return; }
  dcCKey = key;
  var g = dcGuilds.filter(function (x) { return x.id === dcGuild; })[0];
  document.getElementById("dcgname").textContent = g ? g.n : "Server";
  dclEl.innerHTML = list.length ? list.map(function (c) {
    return '<button class="dch' + (DCV && DCV.id === c.id ? " cur" : "") + '" data-dcc="' + esc(c.id) + '" data-n="' + esc(c.n) + '"><span class="dchn">' +
      SPK_SVG + "<span>" + esc(c.n) + "</span></span>" + (c.m.length ? '<span class="dchm">' + c.m.map(function (m) {
        return '<span class="dmi">' + pic(avatar(m), m.n) + "<span>" + esc(m.n) + "</span></span>";
      }).join("") + "</span>" : "") + "</button>";
  }).join("") : '<div class="dcempty">Nessun canale vocale in questo server</div>';
  [].forEach.call(dclEl.getElementsByClassName("dch"), bind);
}
function renderVc() {
  setText(dcvn, DCV ? DCV.n : "Non sei in un canale vocale");
  var gg = DCV && dcGuilds.filter(function (x) { return x.id === DCV.g; })[0];
  setText(document.getElementById("dcvsrv"), gg ? gg.n : "");
  cls(document.getElementById("dcvc"), "none", !DCV);
  cls(dcLeave, "na", !DCV);
  var base = DCV ? DCV.m.map(function (m) { return [m.id, m.n, m.av, m.vol, m.lm, m.sm, m.sd]; }) : [], key = JSON.stringify([DCV && DCV.id, base]);
  if (key !== dcMKey && !dcmEl.querySelector(".on")) {
    dcMKey = key;
    var mem = DCV ? DCV.m.slice().sort(function (a, b) { return (b.id === DCV.me) - (a.id === DCV.me); }) : [];   /* tu per primo */
    dcmEl.innerHTML = DCV ? mem.map(function (m) {
      var me = m.id === DCV.me, x = "";
      if (m.sd) { x += HSOFF_SVG; } else if (m.sm) { x += MICOFF_SVG; }
      if (m.lm) { x += '<span class="dv lm">muto</span>'; }
      else if (!me && m.vol !== 100) { x += '<span class="dv mono">' + m.vol + "%</span>"; }
      return '<button class="dm' + (me ? " me" : "") + '" data-dcu="' + esc(m.id) + '" data-n="' + esc(m.n) + '">' + pic(avatar(m), m.n) +
        '<span class="dmn">' + esc(m.n) + '</span><span class="dmx">' + x + "</span></button>";
    }).join("") : '<div class="dcempty">Tocca un canale vocale per entrare</div>';
    [].forEach.call(dcmEl.getElementsByClassName("dm"), bind);
  }
  if (DCV) {   /* chi parla: solo le classi, senza ricostruire */
    var sp = {}; DCV.m.forEach(function (m) { sp[m.id] = m.sp; });
    [].forEach.call(dcmEl.getElementsByClassName("dm"), function (el) { cls(el, "sp", !!sp[el.getAttribute("data-dcu")]); });
  }
}
function dcLoadGuilds() {
  dcGuildAt = Date.now();
  dcGet("/dcguilds", function (code, j) {
    if (code !== 200 || !j) { dcGuildAt = 0; if (j && j.err) { status("err", "Discord: " + j.err); } return; }
    dcGuilds = j;
    var ids = j.map(function (g) { return g.id; });
    if (ids.indexOf(dcGuild) < 0) { dcGuild = (DCV && DCV.g) || ids[0] || null; }
    renderGuilds(); dcLoadCh();
  });
}
function dcLoadCh() {
  if (!dcGuild || dcChBusy) { return; }
  dcChBusy = true;
  var g = dcGuild;
  dcGet("/dcch?g=" + g, function (code, j) {
    dcChBusy = false;
    if (g !== dcGuild) { dcLoadCh(); return; }
    if (code === 200 && j) { renderCh(j); } else if (j && j.err) { status("err", "Discord: " + j.err); }
  });
}
function dcPoll() {
  if (dcPolling) { return; }
  dcPolling = true;
  dcGet("/dc", function (code, j) {
    dcPolling = false;
    if (code !== 200 || !j) { return; }
    if (Date.now() - dcSent > 1500) { DC = j.st; paintDc(); }
    dcPaintState();
    var prev = DCV && DCV.id;
    DCV = j.vc; renderVc();
    if (DC.s !== "ok") { return; }
    if (!dcGuilds.length || Date.now() - dcGuildAt > 60000) { if (Date.now() - dcGuildAt > 3000) { dcLoadGuilds(); } }
    else { renderGuilds(); if ((DCV && DCV.id) !== prev || ++dcTick % 7 === 0) { dcLoadCh(); } }
  });
}
setInterval(function () { if (curTab === "dc" && !document.hidden) { dcPoll(); } }, 600);
function dcPickGuild(id) {
  dcGuild = id; dcCKey = "";
  try { localStorage.setItem("tabdeck_dcg", id); } catch (e) {}
  dclEl.innerHTML = '<div class="dcempty">Carico...</div>';
  renderGuilds(); dcLoadCh();
}
function dcJoin(el) {
  var id = el.getAttribute("data-dcc");
  if (DCV && DCV.id === id) { status("", "Sei già in " + name(el)); return; }
  status("", "Entro in " + name(el) + "...");
  post("/discord", "a=join&c=" + id, function (code, txt) {
    var j = null; try { j = JSON.parse(txt); } catch (e) {}
    if (code === 200) { status("ok", "✓ " + name(el)); if (j) { DCV = j.vc; renderVc(); } dcCKey = ""; dcLoadCh(); }
    else { status("err", j && j.err ? "Discord: " + j.err : code === 0 ? "PC non raggiungibile" : "Errore " + code); }
  });
}
function dcAct(a) {
  if (a === "mute" || a === "deaf") { dcTap(a === "deaf"); dcPaintState(); return; }
  if (a === "auth") { dcTap(false); return; }
  if (a === "open") { post("/press", "id=discord", function (code) { status(code === 200 ? "ok" : "err", code === 200 ? "Apro Discord..." : "Errore " + code); }); return; }
  if (a === "leave") {
    if (!DCV) { return; }
    post("/discord", "a=leave", function (code, txt) {
      var j = null; try { j = JSON.parse(txt); } catch (e) {}
      if (code === 200) { status("ok", "Uscito dalla chiamata"); DCV = null; renderVc(); dcCKey = ""; dcLoadCh(); }
      else { status("err", j && j.err ? "Discord: " + j.err : "Errore " + code); }
    });
    return;
  }
  if (a === "u100") { dcur.value = 100; dcuval.textContent = "100%"; dcUSend("uvol", 100); return; }
  if (a === "umute" && dcU) { dcU.lm = !dcU.lm; cls(dcum, "off", dcU.lm); dcUSend("umute", dcU.lm ? 1 : 0); }
}
/* volume e muto di una persona (solo per te), come nel menu di Discord */
var dcU = null, dcuT = null, dcur = document.getElementById("dcur"), dcuval = document.getElementById("dcuval"), dcum = document.getElementById("dcum");
function dcUser(id) {
  var m = DCV && DCV.m.filter(function (x) { return x.id === id; })[0];
  if (!m) { return; }
  if (m.id === DCV.me) { status("", "Sei tu: usa Muto / Cuffie qui sotto"); return; }
  dcU = {id: id, lm: m.lm};
  document.getElementById("dcun").textContent = m.n;
  dcur.value = m.vol; dcuval.textContent = m.vol + "%"; cls(dcum, "off", m.lm);
  cls(document.getElementById("pop_dcu"), "show", true);
}
function dcUSend(a, v) {
  if (!dcU) { return; }
  dcSent = Date.now();
  post("/discord", "a=" + a + "&u=" + dcU.id + "&v=" + v, function (code, txt) {
    var j = null; try { j = JSON.parse(txt); } catch (e) {}
    if (code !== 200) { status("err", j && j.err ? "Discord: " + j.err : "Errore " + code); }
  });
}
dcur.addEventListener("input", function () {
  dcuval.textContent = dcur.value + "%";
  if (dcuT) { return; }
  dcuT = setTimeout(function () { dcuT = null; dcUSend("uvol", dcur.value); }, 200);
}, false);
dcur.addEventListener("change", function () { dcUSend("uvol", dcur.value); }, false);
function loadAudio() {
  if (audioBusy) { return; }
  audioBusy = true;
  var x = new XMLHttpRequest();
  x.open("GET", "/audio?_=" + Date.now(), true);
  x.setRequestHeader("X-Token", TOKEN); if (DEVICE) { x.setRequestHeader("X-Device", DEVICE); }
  x.timeout = 5000;
  x.onreadystatechange = function () {
    if (x.readyState !== 4) { return; }
    audioBusy = false;
    if (x.status !== 200) { return; }
    try { var r = JSON.parse(x.responseText); renderNP(r.m); renderMix(r.apps, r.master); renderMic(r.mic); renderDc(r.dc); } catch (e) {}
  };
  x.send();
}
setInterval(function () { if (curTab === "mix" && !document.hidden) { loadAudio(); } }, 1500);
setInterval(function () { if (curTab === "mix" && NP.play) { paintNP(); } }, 1000);
/* scheda Touchpad: movimenti accumulati e spediti con al massimo una richiesta in volo (si adatta alla rete) */
var PADQ = {dx: 0, dy: 0, w: 0, hw: 0, b: [], busy: false}, PAD_SPEED = {slow: 1.3, med: 2.1, fast: 3.2};
function padFlush() {
  var q = PADQ;
  if (q.busy) { return; }
  var dx = Math.round(q.dx), dy = Math.round(q.dy), w = Math.round(q.w), hw = Math.round(q.hw);
  if (!dx && !dy && !w && !hw && !q.b.length) { return; }
  var body = "dx=" + dx + "&dy=" + dy + "&w=" + w + "&hw=" + hw + "&b=" + q.b.join(",");
  q.dx -= dx; q.dy -= dy; q.w -= w; q.hw -= hw; q.b = []; q.busy = true;
  post("/mouse", body, function (code) {
    q.busy = false;
    if (code !== 200) { status("err", code === 0 ? "PC non raggiungibile" : code === 500 ? "Windows ha bloccato il mouse (finestra admin?)" : "Errore " + code); }
    padFlush();
  });
}
/* la tastiera Android chiusa col tasto Indietro lascia il campo attivo: toccando il touchpad si riaprirebbe */
function kBlur() { var k = document.getElementById("kin"); if (document.activeElement === k) { k.blur(); } }
function padBtn(b) { PADQ.b.push(b); padFlush(); }
(function () {
  var tp = $("tp"), pts = {}, maxN = 0, t0 = 0, travel = 0;
  function k() { return PAD_SPEED[SETTINGS.pad] || 2.1; }
  function snap(e) {
    var r = {}, i, t;
    for (i = 0; i < e.targetTouches.length; i++) { t = e.targetTouches[i]; r[t.identifier] = {x: t.clientX, y: t.clientY}; }
    return r;
  }
  tp.addEventListener("touchstart", function (e) {
    e.preventDefault();
    kBlur();
    if (!maxN) { t0 = Date.now(); travel = 0; }
    pts = snap(e); maxN = Math.max(maxN, e.targetTouches.length); cls(tp, "on", true);
  }, {passive: false});
  tp.addEventListener("touchmove", function (e) {
    e.preventDefault();
    var now = snap(e), id, n = 0, sx = 0, sy = 0, d, f;
    for (id in now) { if (pts[id]) { sx += now[id].x - pts[id].x; sy += now[id].y - pts[id].y; n++; } }
    pts = now;
    if (!n) { return; }
    sx /= n; sy /= n; travel += Math.abs(sx) + Math.abs(sy);
    if (e.targetTouches.length === 1 && maxN === 1) {
      d = Math.abs(sx) + Math.abs(sy); f = k() * (d > 12 ? 1.8 : d > 5 ? 1.3 : 1);  /* un po' di accelerazione */
      PADQ.dx += sx * f; PADQ.dy += sy * f;
    } else if (e.targetTouches.length >= 2) {
      PADQ.w += sy * 6; PADQ.hw -= sx * 6;   /* scorrimento "naturale" come sul telefono */
    }
    padFlush();
  }, {passive: false});
  function end(e) {
    e.preventDefault();
    pts = snap(e);
    if (e.targetTouches.length) { return; }
    cls(tp, "on", false);
    if (travel < 12 && Date.now() - t0 < 300 && !multiActive) { padBtn(maxN >= 3 ? "mc" : maxN === 2 ? "rc" : "lc"); }
    maxN = 0;
  }
  tp.addEventListener("touchend", end, {passive: false});
  tp.addEventListener("touchcancel", end, {passive: false});
  /* pulsanti: giu' al tocco, su al rilascio (cosi' si puo' trascinare) */
  (function () {
    var w = document.querySelector("#tpb .tw"), y = null, moved = 0, wT = 0;
    w.addEventListener("touchstart", function (e) {
      if (e.cancelable) { e.preventDefault(); }
      kBlur(); wT = Date.now(); y = e.touches[0].clientY; moved = 0; cls(w, "on", true);
    }, {passive: false});
    w.addEventListener("touchmove", function (e) {
      if (e.cancelable) { e.preventDefault(); }
      if (y === null) { return; }
      var ny = e.touches[0].clientY, dy = ny - y;
      y = ny; moved += Math.abs(dy);
      if (moved > 6) { PADQ.w += dy * 6; padFlush(); }
    }, {passive: false});
    function wend(e) {
      if (e.cancelable) { e.preventDefault(); }
      if (y !== null && moved <= 6) { padBtn("mc"); }
      y = null; cls(w, "on", false);
    }
    w.addEventListener("touchend", wend, {passive: false});
    w.addEventListener("touchcancel", function () { y = null; cls(w, "on", false); }, false);
    w.addEventListener("click", function () { if (y === null && Date.now() - wT > 800) { padBtn("mc"); } }, false);   /* col mouse sul PC */
    w.addEventListener("wheel", function (e) { e.preventDefault(); PADQ.w -= e.deltaY; padFlush(); }, {passive: false});
  })();
  [].forEach.call(document.querySelectorAll("#tpb .tb:not(.tw)"), function (el) {
    var b = el.getAttribute("data-b"), down = false;
    function dn(e) { if (e.cancelable) { e.preventDefault(); } kBlur(); if (!down) { down = true; cls(el, "on", true); padBtn(b + "d"); } }
    function up(e) { if (e.cancelable) { e.preventDefault(); } if (down) { down = false; cls(el, "on", false); padBtn(b + "u"); } }
    el.addEventListener("touchstart", dn, {passive: false});
    el.addEventListener("touchend", up, {passive: false});
    el.addEventListener("touchcancel", up, {passive: false});
    el.addEventListener("mousedown", dn, false);
    el.addEventListener("mouseup", up, false);
    el.addEventListener("mouseleave", up, false);
  });
})();
/* pannello tastiera: "Nascondi" lo toglie (il touchpad si allarga), la linguetta lo riporta. Ricordato per dispositivo */
$("kbx").addEventListener("click", function () { kBlur(); setLocal("kb", "off"); }, false);
$("kbshow").addEventListener("click", function () { setLocal("kb", "on"); }, false);
/* tastiera: il campo tiene uno spazio "sentinella" all'inizio, cosi' anche la cancellazione a campo vuoto si vede;
   a ogni modifica si spedisce la differenza (backspace + testo nuovo), in ordine, una richiesta alla volta */
var KQ = [], kBusy = false, kin = $("kin"), kSent = " ";
function kFlush() {
  if (kBusy || !KQ.length) { return; }
  var it = KQ.shift(); kBusy = true;
  post(it[0], it[1], function (code) {
    kBusy = false;
    if (code !== 200) { KQ = []; status("err", code === 0 ? "PC non raggiungibile" : "Errore tastiera " + code); return; }
    kFlush();
  });
}
function kPush(path, body) { KQ.push([path, body]); kFlush(); }
function kReset() { kin.value = " "; kSent = " "; try { kin.setSelectionRange(1, 1); } catch (e) {} }
kReset();
kin.addEventListener("input", function () {
  var v = kin.value, i = 0;
  while (i < v.length && i < kSent.length && v.charAt(i) === kSent.charAt(i)) { i++; }
  var bs = kSent.length - i, add = v.slice(i);
  if (bs || add) { kPush("/type", "bs=" + bs + "&t=" + encodeURIComponent(add)); }
  kSent = v;
  if (v.charAt(0) !== " " || (v.length > 40 && v.charAt(v.length - 1) === " ")) { kReset(); }
}, false);
kin.addEventListener("keydown", function (e) {
  if (e.keyCode === 13) { e.preventDefault(); kPush("/key", "k=ENTER"); kReset(); }
}, false);
kin.addEventListener("focus", function () { setTimeout(function () { try { kin.setSelectionRange(kin.value.length, kin.value.length); } catch (e) {} }, 0); }, false);
[].forEach.call(document.getElementsByClassName("kk"), function (el) {
  var live = false;
  var kx = 0, ky = 0;
  el.addEventListener("touchstart", function (e) { live = true; kx = e.touches[0].clientX; ky = e.touches[0].clientY; cls(el, "on", true); }, {passive: true});
  el.addEventListener("touchmove", function (e) {
    var t = e.touches[0];
    if (Math.abs(t.clientX - kx) > 12 || Math.abs(t.clientY - ky) > 12) { live = false; cls(el, "on", false); }
  }, {passive: true});
  el.addEventListener("touchend", function (e) {
    if (e.cancelable) { e.preventDefault(); }   /* la tastiera Android resta aperta */
    cls(el, "on", false);
    if (live && !multiActive) { kPush("/key", "k=" + encodeURIComponent(el.getAttribute("data-k"))); }
    live = false;
  }, false);
  el.addEventListener("mousedown", function (e) { e.preventDefault(); kPush("/key", "k=" + encodeURIComponent(el.getAttribute("data-k"))); }, false);
});
/* scheda Monitor: valori ogni 1,5 s; lo storico (60 s) arriva alla prima richiesta, poi si accoda in locale */
var MH = null, monBusy = false, CORES_N = -1;
function rate(b) {
  if (b < 1024) { return b + "<small>B/s</small>"; }
  if (b < 1048576) { return (b / 1024).toFixed(b < 10240 ? 1 : 0) + "<small>KB/s</small>"; }
  return (b / 1048576).toFixed(b < 10485760 ? 1 : 0) + "<small>MB/s</small>";
}
function spark(id, data, color) {
  var c = $(id), w = c.clientWidth, h = c.clientHeight, r = window.devicePixelRatio || 1, x = c.getContext("2d"), i, n = 60;
  if (!w || !h) { return; }
  if (c.width !== Math.round(w * r) || c.height !== Math.round(h * r)) { c.width = Math.round(w * r); c.height = Math.round(h * r); }
  x.setTransform(r, 0, 0, r, 0, 0); x.clearRect(0, 0, w, h);
  x.strokeStyle = "rgba(255,255,255,.07)"; x.lineWidth = 1; x.beginPath();
  for (i = 1; i < 4; i++) { x.moveTo(0, Math.round(h * i / 4) + 0.5); x.lineTo(w, Math.round(h * i / 4) + 0.5); }
  x.stroke();
  if (data.length < 2) { return; }
  var st = w / (n - 1), x0 = w - (data.length - 1) * st;
  x.beginPath(); x.moveTo(x0, h);
  for (i = 0; i < data.length; i++) { x.lineTo(x0 + i * st, h - Math.max(0, Math.min(100, data[i])) / 100 * (h - 2) - 1); }
  x.lineTo(w, h); x.closePath(); x.globalAlpha = 0.18; x.fillStyle = color; x.fill(); x.globalAlpha = 1;
  x.beginPath();
  for (i = 0; i < data.length; i++) { x[i ? "lineTo" : "moveTo"](x0 + i * st, h - Math.max(0, Math.min(100, data[i])) / 100 * (h - 2) - 1); }
  x.strokeStyle = color; x.lineWidth = 2; x.stroke();
}
var MCOL = {cpu: "#f5c518", gpu: "#5cc45a", ram: "#4fb3ff", vram: "#b48cff"};
function setPct(id, v) { var e = $(id); e.textContent = v === undefined ? "--" : v; cls(e, "hot", v >= 90); }
function renderMon(s) {
  var k;
  if (s.hist) { MH = s.hist; }
  else if (MH) { for (k in MH) { MH[k].push(s[k] || 0); if (MH[k].length > 60) { MH[k].shift(); } } }
  setPct("m_cpu", s.cpu); setPct("m_gpu", s.gpu); setPct("m_ram", s.ram); setPct("m_vram", s.vram);
  $("m_cn").textContent = s.cn || ""; $("m_gn").textContent = s.gn || "nessuna GPU NVIDIA";
  $("m_cpuf").innerHTML = s.mhz ? (s.mhz / 1000).toFixed(2) + " <i>GHz</i>" : "";
  $("m_gpuf").innerHTML = s.gt !== undefined ? s.gt + "<i>&deg;C</i> &nbsp;" + s.gw + "<i>W</i> &nbsp;" + s.gc + "<i>MHz</i> &nbsp;<i>ventola</i> " + s.gf + "<i>%</i>" : "";
  $("m_rams").textContent = s.rt ? s.rt + " GB" : "";
  $("m_ramf").innerHTML = s.ru !== undefined ? s.ru + " <i>/ " + s.rt + " GB in uso</i>" : "";
  $("m_vramf").innerHTML = s.vu !== undefined ? s.vu + " <i>/ " + s.vt + " GB in uso</i>" : "";
  $("m_rx").innerHTML = s.rx !== undefined ? rate(s.rx) : "--"; $("m_tx").innerHTML = s.tx !== undefined ? rate(s.tx) : "--";
  $("m_dr").innerHTML = s.dr !== undefined ? rate(s.dr) : "--"; $("m_dw").innerHTML = s.dw !== undefined ? rate(s.dw) : "--";
  $("m_disk").textContent = "attività " + (s.disk !== undefined ? s.disk : "--") + "%";
  var cores = s.cores || [], box = $("mcores"), i;
  if (cores.length !== CORES_N) {
    CORES_N = cores.length; $("m_ncores").textContent = CORES_N ? CORES_N + " thread" : "";
    box.innerHTML = cores.map(function () { return "<div><i></i></div>"; }).join("");
  }
  var bars = box.getElementsByTagName("i");
  for (i = 0; i < cores.length; i++) { bars[i].style.transform = "scaleY(" + (cores[i] / 100) + ")"; }
  if (MH) { for (k in MCOL) { spark("g_" + k, MH[k] || [], MCOL[k]); } }
}
function loadMon() {
  if (monBusy) { return; }
  monBusy = true;
  var x = new XMLHttpRequest();
  x.open("GET", "/stats?" + (MH ? "" : "h=1&") + "_=" + Date.now(), true);
  x.setRequestHeader("X-Token", TOKEN); if (DEVICE) { x.setRequestHeader("X-Device", DEVICE); }
  x.timeout = 4000;
  x.onreadystatechange = function () {
    if (x.readyState !== 4) { return; }
    monBusy = false;
    if (x.status === 200) { try { renderMon(JSON.parse(x.responseText)); } catch (e) {} }
  };
  x.send();
}
setInterval(function () { if (curTab === "mon" && !document.hidden) { loadMon(); } }, 1000);
/* ------------------------------------------------------------ YouTube: cerca dal tablet, suona nel browser del PC */
var ytPane = document.getElementById("yt"), ytQ = document.getElementById("ytq"), ytRes = document.getElementById("ytres"),
  ytQueue = document.getElementById("ytqueue"), ytR = document.getElementById("ytr"), ytSeek = document.getElementById("ytseek"),
  ytVol = document.getElementById("ytvol"), ytPlay = document.getElementById("ytplay"), ytNote = document.getElementById("ytnote");
var YTR = [], YTS = null, ytQKey = "", ytCurKey = "", ytSeekDrag = false, ytVolDrag = false, ytBusy = false;
function ytFmt(s) { s = Math.max(0, Math.floor(s || 0)); var m = Math.floor(s / 60); s = s % 60; return m + ":" + (s < 10 ? "0" : "") + s; }
function ytThumb(id) { return "https://i.ytimg.com/vi/" + id + "/mqdefault.jpg"; }
function ytItem(it) {
  return "id=" + encodeURIComponent(it.id) + "&title=" + encodeURIComponent(it.title) + "&channel=" + encodeURIComponent(it.channel) +
    "&dur=" + encodeURIComponent(it.dur);
}
/* suggerimenti: dopo 250 ms senza scrivere; una risposta arrivata tardi (testo cambiato o ricerca gia' partita) si ignora */
var ytSug = document.getElementById("ytsug"), YTSG = [], ytSugT = null, ytSugSeq = 0;
function ytSugHide() { ytSugSeq++; if (ytSugT) { clearTimeout(ytSugT); ytSugT = null; } cls(ytSug, "show", false); }
function ytSugAsk() {
  var q = ytQ.value.replace(/^\s+|\s+$/g, ""), seq = ++ytSugSeq;
  if (!q || q.length > 200) { cls(ytSug, "show", false); return; }
  dcGet("/ytsug?q=" + encodeURIComponent(q), function (code, j) {
    if (seq !== ytSugSeq || document.activeElement !== ytQ) { return; }
    YTSG = (code === 200 && j && j.s) || [];
    ytSug.innerHTML = YTSG.map(function (t, i) { return '<button class="ytsg" data-yts="' + i + '" data-n="' + esc(t) + '">' + esc(t) + "</button>"; }).join("");
    [].forEach.call(ytSug.getElementsByClassName("ytsg"), bind);
    cls(ytSug, "show", YTSG.length > 0);
  });
}
ytQ.addEventListener("input", function () { if (ytSugT) { clearTimeout(ytSugT); } ytSugT = setTimeout(ytSugAsk, 250); }, false);
/* il tocco su un suggerimento arriva dopo che il campo ha perso il fuoco: la lista si chiude con un po' di ritardo */
ytQ.addEventListener("blur", function () { setTimeout(function () { if (document.activeElement !== ytQ) { ytSugHide(); } }, 400); }, false);
function ytPickSug(i) { var t = YTSG[i]; if (!t) { return; } ytQ.value = t; ytSearch(); }
function ytSearch() {
  var q = ytQ.value.replace(/^\s+|\s+$/g, "");
  ytSugHide();
  if (!q || ytBusy) { return; }
  ytQ.blur(); ytBusy = true;
  ytRes.innerHTML = '<div class="dcempty">Cerco&hellip;</div>';
  dcGet("/yts?q=" + encodeURIComponent(q), function (code, j) {
    ytBusy = false;
    if (code !== 200 || !j) {
      ytRes.innerHTML = '<div class="dcempty">' + (code === 0 ? "PC non raggiungibile" : "Ricerca non riuscita") + "</div>";
      return;
    }
    YTR = j.r || [];
    ytRes.innerHTML = YTR.length ? YTR.map(function (it, i) {
      return '<div class="ytrw"><button class="ytrow" data-ytp="' + i + '" data-n="' + esc(it.title) + '"><span class="ytth"><img src="' +
        ytThumb(it.id) + '" alt="">' + (it.dur ? '<span class="ytd mono">' + esc(it.dur) + "</span>" : "") +
        '</span><span class="ytx"><b>' + esc(it.title) + "</b><span>" + esc(it.channel) + "</span></span></button>" +
        '<button class="ytadd" data-ytq="' + i + '" data-n="+ coda">+</button></div>';
    }).join("") : '<div class="dcempty">Nessun risultato</div>';
    ytRes.scrollTop = 0;
    [].forEach.call(ytRes.querySelectorAll(".ytrow, .ytadd"), bind);
    if (ytPane.classList.contains("vq")) { ytView("res"); }
  });
}
ytQ.addEventListener("keydown", function (e) { if (e.keyCode === 13) { e.preventDefault(); ytSearch(); } }, false);
function ytAct(a, extra, cb) {
  post("/yt", "a=" + a + (extra ? "&" + extra : ""), function (code, txt) {
    var j = null; try { j = JSON.parse(txt); } catch (e) {}
    if (code === 200 && j) { paintYt(j); }
    else { status("err", code === 0 ? "PC non raggiungibile" : "Errore " + code); }
    if (cb) { cb(code, j); }
  });
}
function ytPick(el, i, add) {
  var it = YTR[i]; if (!it) { return; }
  flash(el, "ok");
  ytAct(add ? "add" : "play", ytItem(it), function (code) {
    if (code === 200) { status("ok", (add ? "+ in coda: " : "▶ ") + it.title); }
  });
}
function ytBtn(a, el) {
  if (a === "search") { ytSearch(); return; }
  if (a === "web") {
    var n = YTS && YTS.notice;
    if (n && n.kind !== "blocked") { ytAct("web", "id=" + encodeURIComponent(n.id)); status("ok", "Aperto su YouTube"); }
    return;
  }
  if (a === "open") {
    ytAct("open", "", function (code, j) {
      if (code !== 200 || !j) { return; }
      if (j.open_r === "unavailable") { status("err", "Player non disponibile sul PC"); } else { status("ok", "YouTube sul PC"); }
    });
    return;
  }
  ytAct(a);
}
function ytView(v) {
  cls(ytPane, "vq", v === "queue");
  [].forEach.call(document.querySelectorAll(".ytt"), function (t) { cls(t, "sel", t.getAttribute("data-ytv") === v); });
}
[].forEach.call(document.querySelectorAll(".ytt, .ytsm"), bind);
ytSeek.addEventListener("touchstart", function () { ytSeekDrag = true; }, {passive: true});
ytSeek.addEventListener("input", function () { ytSeekDrag = true; setText(document.getElementById("ytpos"), ytFmt(+ytSeek.value)); }, false);
ytSeek.addEventListener("change", function () { ytSeekDrag = false; ytAct("seek", "s=" + ytSeek.value); }, false);
ytVol.addEventListener("touchstart", function () { ytVolDrag = true; }, {passive: true});
ytVol.addEventListener("input", function () { ytVolDrag = true; setText(document.getElementById("ytvolv"), ytVol.value); }, false);
ytVol.addEventListener("change", function () { ytVolDrag = false; ytAct("vol", "v=" + ytVol.value); }, false);
function ytNoteText(n) {
  if (n.kind === "blocked") {
    return "Il browser del PC blocca l'avvio automatico: consentilo per il player " +
      "(Firefox: Impostazioni › Privacy › Riproduzione automatica › localhost:" + ((+location.port || 8765) + 100) + ")";
  }
  return "«" + n.title + "» non riproducibile qui";
}
function paintYt(s) {
  YTS = s;
  var c = s.cur, open = !!s.open;
  cls(ytR, "closed", !open);
  var ck = c ? c.id + "|" + c.title : "";
  if (ck !== ytCurKey) {
    ytCurKey = ck;
    document.getElementById("ytpic").innerHTML = c ? '<img src="' + ytThumb(c.id) + '" alt="">' : "";
  }
  setText(document.getElementById("yttitle"), c ? c.title : "Niente in riproduzione");
  setText(document.getElementById("ytch"), c ? c.channel + (s.state === "ad" ? " · pubblicità" : s.state === "buffering" ? " · carico…" : "") : "");
  cls(ytPlay, "pl", s.state === "playing" || s.state === "ad" || s.state === "buffering");
  if (!ytSeekDrag) {
    var d = String(Math.max(1, Math.floor(s.dur || 0)));
    if (ytSeek.max !== d) { ytSeek.max = d; }
    var pv = String(Math.floor(s.pos || 0)); if (ytSeek.value !== pv) { ytSeek.value = pv; }
    setText(document.getElementById("ytpos"), ytFmt(s.pos));
  }
  setText(document.getElementById("ytdur"), ytFmt(s.dur));
  if (!ytVolDrag) { var vv = String(s.vol); if (ytVol.value !== vv) { ytVol.value = vv; } setText(document.getElementById("ytvolv"), s.vol); }
  var n = s.notice;
  cls(ytNote, "show", !!n);
  if (n) { setText(document.getElementById("ytnmsg"), ytNoteText(n)); cls(document.getElementById("ytweb"), "na", n.kind === "blocked"); }
  setText(document.getElementById("ytqh"), "Coda (" + s.queue.length + ")");
  setText(document.querySelector('.ytt[data-ytv="queue"]'), "Coda (" + s.queue.length + ")");
  var qk = JSON.stringify(s.queue.map(function (x) { return x.id + x.title; }));
  if (qk !== ytQKey && !ytQueue.querySelector(".on")) {
    ytQKey = qk;
    ytQueue.innerHTML = s.queue.length ? s.queue.map(function (it, i) {
      return '<div class="ytqr"><span class="ytqt">' + (i + 1) + ". " + esc(it.title) + "</span>" +
        (i > 0 ? '<button class="ytqb" data-ytup="' + i + '" data-n="su">&uarr;</button>' : "") +
        '<button class="ytqb" data-ytrm="' + i + '" data-n="togli">&times;</button></div>';
    }).join("") : '<div class="dcempty">Coda vuota: tocca + su un risultato</div>';
    [].forEach.call(ytQueue.getElementsByClassName("ytqb"), bind);
  }
}
function ytPoll() { dcGet("/yt", function (code, j) { if (code === 200 && j) { paintYt(j); } }); }
setInterval(function () { if (curTab === "yt" && !document.hidden) { ytPoll(); } }, 1000);
function showTab(n) {
  var ps = document.getElementsByClassName("pane"), ts = document.getElementsByClassName("tab"), i;
  for (i = 0; i < ps.length; i++) { cls(ps[i], "show", ps[i].id === n); }
  for (i = 0; i < ts.length; i++) { cls(ts[i], "sel", ts[i].getAttribute("data-tab") === n); }
  document.getElementById("navname").textContent = TAB_NAMES[n];
  try { localStorage.setItem("tabdeck_tab", n); } catch (e) {}
  curTab = n;
  if (n === "grid") { ping(); }
  if (n === "dc") { dcGuildAt = 0; dcPoll(); }
  if (n === "mix") { loadAudio(); }
  if (n === "hd2") { cdSig = ""; paintCd(); }
  if (n === "mon") { MH = null; loadMon(); }
  if (n === "yt") { ytPoll(); }   /* storico fresco a ogni apertura */
}
/* menu sezioni: il pulsante in basso apre l'elenco; ogni riquadro porta alla sua sezione */
var navPop = document.getElementById("navpop");
document.getElementById("nav").addEventListener("click", function () { cls(navPop, "show", true); }, false);
[].forEach.call(document.getElementsByClassName("tab"), function (t) {
  t.addEventListener("click", function () { showTab(t.getAttribute("data-tab")); cls(navPop, "show", false); }, false);
});
/* scorrimento a DUE dita a sinistra/destra = scheda successiva/precedente */

var gx0 = 0, gy0 = 0, gx = 0, gy = 0;
function avg(ts, k) { var s = 0; for (var i = 0; i < ts.length; i++) { s += ts[i][k]; } return s / ts.length; }
function gMove(e) {
  if (!multiActive) { return; }
  if (e.touches.length >= 2) { gx = avg(e.touches, "clientX"); gy = avg(e.touches, "clientY"); }
  if (e.cancelable) { e.preventDefault(); }   /* niente scroll della lista durante il gesto */
}
document.addEventListener("touchstart", function (e) {
  if (curTab === "pad" && e.target.closest && e.target.closest("#tpwrap")) { return; }  /* nel touchpad 2 dita = scorrere */
  if (e.touches.length >= 2 && !multiActive) {
    multiActive = true;
    gx0 = gx = avg(e.touches, "clientX"); gy0 = gy = avg(e.touches, "clientY");
    document.addEventListener("touchmove", gMove, {capture: true, passive: false});
  }
}, {capture: true, passive: true});
function gestureEnd(e) {
  if (!multiActive || e.touches.length > 0) { return; }
  multiActive = false;
  document.removeEventListener("touchmove", gMove, true);
  var dx = gx - gx0, dy = gy - gy0;
  if (Math.abs(dx) < 80 || Math.abs(dx) < Math.abs(dy) * 1.5) { return; }
  var i = TABS.indexOf(curTab) + (dx < 0 ? 1 : -1);
  if (i < 0 || i >= TABS.length) { return; }
  setOpen(false);
  [].forEach.call(document.getElementsByClassName("gpop"), function (p) { cls(p, "show", false); });
  showTab(TABS[i]);
  status("", (dx < 0 ? "▶ " : "◀ ") + TAB_NAMES[TABS[i]]);
}
document.addEventListener("touchend", gestureEnd, false);      /* fase di bolla: dopo i tasti */
document.addEventListener("touchcancel", gestureEnd, false);
try { var savedTab = localStorage.getItem("tabdeck_tab"); if (TABS.indexOf(savedTab) > 0) { showTab(savedTab); } } catch (e) {}
if (TABS.indexOf(HASH) >= 0) { showTab(HASH); }
if (HASH.indexOf("set") === 0) { setOpen(true); setTab(HASH.split("-")[1] || "fav"); }
[].forEach.call(document.querySelectorAll(".b, #hd2all .s"), bind);
buildLoadout();
