/* hub.js -- the front door's client.
   [REDESIGN: 2026-09-14]

   Served by luminos-hub at /app.js. A real file at a real route, never an inline
   <script>, so the page runs under `script-src 'self'` with no 'unsafe-inline'.

   Four rules it never breaks:
     - Nothing is ever assembled as an HTML string. Nodes are constructed, text goes
       in through .textContent. Every release name on this box was chosen by a
       stranger on the internet.
     - The server sends raw byte counts; formatting happens here, so a number can
       travel between polls instead of snapping.
     - The poll interval is 15s and is never shortened. The server caches 10s behind
       it. Smoothness comes from interpolation, never from asking more often.
     - When the server stops answering the page goes visibly stale rather than
       continuing to look current. */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var size = LUM.size, el = LUM.el, txt = LUM.txt;

  /* ---- outbound links -------------------------------------------------------
     Ports are server-rendered onto data-port so the links are right on the first
     frame; only the host is filled in, because this page is reached both on the
     LAN address and on the tailnet address and must work on both. */
  var host = location.hostname;
  Array.prototype.forEach.call(document.querySelectorAll("a[data-port]"), function (a) {
    a.href = "https://" + host + ":" + a.getAttribute("data-port") + "/";
  });
  if (!$("sub")) { return; }          /* /offline shares this file for the links */

  LUM.parallax();

  /* ---- the room -------------------------------------------------------------
     Try for objects. Fall back to the same two solids in SVG -- ~1 KB, no canvas,
     identical with hardware acceleration switched off -- on no context, a failed
     compile, a lost context, or ?flat=1 in the URL for a deliberate comparison. */
  var forceFlat = new URLSearchParams(location.search).has("flat");
  var scene = forceFlat ? null : (window.GLDrives && GLDrives.mount($("drives")));
  if (!scene) { goFlat(); } else { scene.onlost = goFlat; scene.onturn = turned; }

  function goFlat() {
    scene = null;
    $("stage").classList.add("off");
    $("flat").classList.remove("off");
    if (lastDisks) { flatSolids(lastDisks); }
  }
  function turned() { $("stage").classList.add("turning"); }

  /* ---- the room is the door to Space ----------------------------------------
     [CHANGE: claude-code | 2026-09-14]
     The whole block is an anchor, but the canvas inside it is draggable, so a
     turn must not navigate. Measure the pointer rather than asking gl.js: under
     6px of travel and under 600ms is a click, anything longer or further is a
     turn. That works for touch and mouse with no knowledge of the scene.

     `e.detail` is 0 when a click came from the keyboard, which carries no
     coordinates -- those must always pass, or the door stops being reachable by
     tab + Enter. */
  var door = $("roomdoor");
  if (door) {
    var downX = 0, downY = 0, downAt = 0;
    door.addEventListener("pointerdown", function (e) {
      downX = e.clientX; downY = e.clientY; downAt = Date.now();
    });
    door.addEventListener("click", function (e) {
      if (!e.detail) { return; }
      if (Math.abs(e.clientX - downX) > 6 || Math.abs(e.clientY - downY) > 6
          || Date.now() - downAt > 600) {
        e.preventDefault();
      }
    });
  }

  /* The SVG fallback. Height is capacity, filled height is usage, three faces lit
     from the top left -- the same object the shader draws, by hand. */
  var FW = 34, FH = 17, TALL = 96;
  function pts(a) {
    var s = [], i;
    for (i = 0; i < a.length; i += 2) { s.push(a[i].toFixed(1) + "," + a[i + 1].toFixed(1)); }
    return s.join(" ");
  }
  function topFace(h) { return [0, FH - h, FW, -h, 0, -FH - h, -FW, -h]; }
  function rightFace(h) { return [0, FH, FW, 0, FW, -h, 0, FH - h]; }
  function leftFace(h) { return [0, FH, -FW, 0, -FW, -h, 0, FH - h]; }
  function silhouette(h) { return [0, -FH - h, FW, -h, FW, 0, 0, FH, -FW, 0, -FW, -h]; }

  function flatSolids(disks) {
    var tallest = disks.reduce(function (a, x) { return Math.max(a, x.total || 0); }, 0) || 1;
    [0, 1].forEach(function (i) {
      var g = $("v" + i), disk = disks[i];
      if (!g) { return; }
      if (!disk) { g.classList.add("off"); return; }
      g.classList.remove("off");
      var full = TALL * Math.min(1, (disk.total || 1) / tallest);
      var frac = disk.total ? disk.used / disk.total : 0;
      var fill = Math.max(1, full * frac);
      $("o" + i).setAttribute("points", pts(silhouette(full)));
      $("r" + i).setAttribute("points", pts(topFace(full)));
      $("ft" + i).setAttribute("points", pts(topFace(fill)));
      $("fr" + i).setAttribute("points", pts(rightFace(fill)));
      $("fl" + i).setAttribute("points", pts(leftFace(fill)));
      $("o" + i).classList.toggle("risky", !!disk.risky);
      var pct = Math.round(frac * 100);
      $("c" + i).textContent = pct + "%";
      var f = $("f" + i);
      f.classList.toggle("warnfill", pct >= 85 && pct < 95);
      f.classList.toggle("dangerfill", pct >= 95);
    });
  }

  /* The figures beside the objects. Colour only once a drive is genuinely close to
     full; below that a disk is material, not a warning. */
  var freeFig = [];
  function figures(disks) {
    [0, 1].forEach(function (i) {
      var disk = disks[i], fig = $("fig" + i);
      if (!disk) { fig.classList.add("off"); return; }
      fig.classList.remove("off");
      var pct = disk.total ? Math.round(disk.used / disk.total * 100) : 0;
      fig.classList.toggle("tight", pct >= 85 && pct < 95);
      fig.classList.toggle("full", pct >= 95);
      $("w" + i).textContent = disk.name;
      $("p" + i).textContent = pct + "% used";
      $("g" + i).classList.toggle("off", !disk.risky);
      if (!freeFig[i]) {
        $("e" + i).textContent = "";
        freeFig[i] = LUM.figure($("e" + i));
      }
      freeFig[i].to(disk.free);
      $("u" + i).textContent = "free of " + size(disk.total);
    });
  }

  /* ---- throughput, as a shape ----------------------------------------------
     One sample per poll, 40 samples, so roughly the last ten minutes. Only drawn
     while something is actually moving: at rest there is no line to look at and
     pretending otherwise would be decoration. */
  var hist = [];
  function trace(speed) {
    hist.push(Number(speed) || 0);
    if (hist.length > 40) { hist.shift(); }
    var peak = Math.max.apply(null, hist.concat([1]));
    var pl = [], i, x, y;
    for (i = 0; i < hist.length; i++) {
      x = hist.length === 1 ? 240 : (i / (hist.length - 1)) * 240;
      y = 39 - (hist[i] / peak) * 36;
      pl.push(x.toFixed(1) + "," + y.toFixed(1));
    }
    var line = pl.join(" ");
    $("trace-l").setAttribute("points", line);
    $("trace-f").setAttribute("points", "0,39 " + line + " 240,39");
    $("trace").classList.toggle("off", !hist.some(function (v) { return v > 0; }));
  }

  /* ---- downloading ---------------------------------------------------------- */
  function makeQueue() {
    var n = el("div", "item");
    n._t = el("div", "t", n);
    n._track = el("div", "track", n);
    n._bar = el("i", null, n._track);
    n._meta = el("div", "meta", n);
    n._pct = el("span", "on", n._meta);
    n._size = el("span", null, n._meta);
    n._eta = el("span", null, n._meta);
    n._app = el("span", null, n._meta);
    return n;
  }
  function fillQueue(n, r) {
    n._t.textContent = r.title;
    /* transform, not width: it stays on the compositor and animates for free.
       NZBGet's Status string lags up to 16s and calls par2 repair PAUSED, so the
       byte delta leads and the chip is never allowed to contradict the bar. */
    n._bar.style.transform = "scaleX(" + (Math.max(0, Math.min(100, r.pct)) / 100) + ")";
    n.classList.toggle("moving", !r.held);
    n._track.classList.toggle("held", !!r.held);
    n._pct.classList.toggle("on", !r.held);
    n._pct.textContent = r.pct.toFixed(0) + "%";
    n._size.textContent = size(r.bytes - r.left) + " of " + size(r.bytes);
    n._eta.textContent = r.held ? "held" : (LUM.eta(r.eta) || "\u2013");
    n._app.textContent = r.app;
  }

  /* ---- arrived --------------------------------------------------------------
     Artwork comes off the arrs' own MediaCover directory, read from disk by the
     server, so it is same-origin and allowed. The plate underneath is drawn first
     and stays if the poster 404s: a missing image degrades to a designed object
     rather than a broken-image glyph. */
  function makeCard(r) {
    var n = el("div", "card");
    var plate = el("div", "plate", n);
    el("span", "rule", plate);
    n._ini = txt("span", "ini", plate, "");
    if (r.art) {
      var img = el("img", null, plate);
      img.width = 118; img.height = 174;
      img.alt = "";
      img.loading = "lazy";
      img.addEventListener("load", function () { img.classList.add("in"); });
      img.src = r.art;
    }
    n._nm = el("div", "nm", n);
    var mt = el("div", "mt", n);
    n._kind = el("span", "k", mt);
    n._when = el("span", null, mt);
    n._count = el("div", "mt", n);
    return n;
  }
  function fillCard(n, r) {
    n._ini.textContent = LUM.initials(r.title);
    n._nm.textContent = r.title;
    n._kind.textContent = r.kind === "tv" ? "series" : "film";
    n._when.textContent = " \u00b7 " + LUM.ago(r.when);
    var noun = r.kind === "tv" ? "episode" : "file";
    n._count.textContent = r.count + " " + noun + (r.count === 1 ? "" : "s");
  }

  /* ---- the hero -------------------------------------------------------------
     The single question the page exists to answer. The five machine states all
     still appear, in .sig, in full -- but at rest the biggest type on the page is
     a true number about the house rather than the word IDLE. 61% of downloads on
     this box fail and the queue is usually empty; the normal state should read as
     the server at rest, not as an empty result. */
  var heroFig = null;
  function figureBytes(v, suffix) {
    if (!heroFig) { $("figure").textContent = ""; heroFig = LUM.figure($("figure")); }
    heroFig.unit(suffix || "");
    heroFig.to(v);
  }
  function figureWord(w) {
    heroFig = null;
    $("figure").textContent = w;
  }

  function hero(d) {
    var h = $("hero"), sig = $("sig"), sub = $("sub");
    h.classList.remove("running", "held", "gone");
    sig.classList.remove("live", "held", "gone");
    $("pip").classList.toggle("beat", d.speed > 0);

    if (d.paused) {
      h.classList.add("held"); sig.classList.add("held");
      sig.textContent = "held";
      figureWord("HELD");
      sub.textContent = "Downloads are paused. Nothing will arrive until they are resumed.";
      return;
    }
    if (d.speed > 0) {
      h.classList.add("running"); sig.classList.add("live");
      sig.textContent = "running";
      figureBytes(d.speed, "/s");
      var left = d.queue.reduce(function (a, q) { return a + (q.left || 0); }, 0);
      sub.replaceChildren();
      sub.appendChild(document.createTextNode(
        d.queue.length + (d.queue.length === 1 ? " file" : " files") + ", "));
      txt("b", null, sub, size(left));
      sub.appendChild(document.createTextNode(" still to come."));
      return;
    }
    if (d.queue.length) {
      sig.textContent = "queued";
      figureWord("QUEUED");
      sub.textContent = d.queue.length + (d.queue.length === 1 ? " item is" : " items are")
        + " waiting, none moving yet.";
      return;
    }
    /* At rest. The weather: how much room there is, and what the room did lately. */
    sig.textContent = "at rest";
    var free = d.disks.reduce(function (a, x) { return a + (x.free || 0); }, 0);
    figureBytes(free);
    sub.replaceChildren();
    sub.appendChild(document.createTextNode("Free, across "
      + d.disks.length + (d.disks.length === 1 ? " drive" : " drives") + ". Nothing is downloading"));
    var fresh = d.recent.filter(function (r) {
      return (Date.now() - Date.parse(r.when)) < 7 * 86400000;
    }).length;
    if (fresh) {
      sub.appendChild(document.createTextNode(" \u2014 "));
      txt("b", null, sub, fresh + (fresh === 1 ? " title" : " titles"));
      sub.appendChild(document.createTextNode(" landed this week."));
    } else {
      sub.appendChild(document.createTextNode("."));
    }
  }

  /* ---- poll ----------------------------------------------------------------- */
  var lastDisks = null;
  function paint(d) {
    d.disks = d.disks || []; d.queue = d.queue || []; d.recent = d.recent || [];
    hero(d);
    trace(d.speed);

    lastDisks = d.disks;
    if (scene) { scene.update(d.disks); } else { flatSolids(d.disks); }
    figures(d.disks);
    var freeAll = d.disks.reduce(function (a, x) { return a + (x.free || 0); }, 0);
    $("room-aux").textContent = size(freeAll) + " free of "
      + size(d.disks.reduce(function (a, x) { return a + (x.total || 0); }, 0));

    LUM.keyed($("queue"), d.queue, function (r) { return r.app + "\u0000" + r.title; },
              makeQueue, fillQueue, function () {
      /* An empty queue is the normal state and must not read as a fault. It says
         what the machine is doing -- waiting -- and nothing more. */
      var e = el("div", "empty");
      e.appendChild(document.createTextNode("Nothing in flight. "));
      txt("b", null, e, "The indexers are checked on Sonarr and Radarr's own schedule;");
      e.appendChild(document.createTextNode(" anything found turns up here on its own."));
      return e;
    });
    $("q-aux").textContent = d.queue.length ? String(d.queue.length) : "";

    LUM.keyed($("recent"), d.recent, function (r) { return r.kind + "\u0000" + r.title; },
              makeCard, fillCard);
    $("r-aux").textContent = d.recent.length ? d.recent.length + " lately" : "";

    $("clock").textContent = d.at;
    document.body.classList.remove("stale");
  }

  function fail() {
    var h = $("hero"), sig = $("sig");
    h.classList.remove("running", "held");
    h.classList.add("gone");
    sig.classList.remove("live", "held");
    sig.classList.add("gone");
    sig.textContent = "no reply";
    figureWord("NO REPLY");
    $("sub").textContent = "The server did not answer. It may be asleep or rebooting. "
      + "Everything on this page is as it was at " + ($("clock").textContent || "last poll") + ".";
    $("pip").classList.remove("beat");
    document.body.classList.add("stale");
  }

  function load() {
    LUM.get("/api/summary").then(paint).catch(fail);
  }

  load();
  setInterval(load, 15000);
  /* Returning to a backgrounded tab must not show a stale number, and this costs
     nothing while the page is hidden. */
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) { load(); }
  });
}());
