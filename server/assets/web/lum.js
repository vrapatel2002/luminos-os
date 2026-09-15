/* lum.js -- the bits all four pages share.
   [REDESIGN: 2026-09-14]

   Served from /lum.js by both processes, beside app.css. Loaded before each page's
   own script. Plain IIFE, one global (window.LUM), no build step, no dependency.

   It owns three things worth having in one place:

     1. Formatting. The server sends raw byte counts and the client formats them --
        that split is what lets a number travel between polls instead of snapping.
     2. Interpolation. LUM.num() is a value that eases toward a target. Poll rates
        are fixed (hub 15s, space 5s, server caches 10s behind that) and are never
        shortened to make motion smoother; the client interpolates instead.
     3. The ambient governor. One requestAnimationFrame loop for the whole page,
        which stops itself when: the tab is hidden, the reader has not touched the
        page for IDLE_AFTER, or prefers-reduced-motion is set. This is a phone held
        in bed, so an idle page must cost nothing to leave open. */
(function () {
  "use strict";

  var LUM = {};
  var IDLE_AFTER = 90000;        /* phone put down -> ambient motion stops */

  LUM.reduced = window.matchMedia
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---- formatting ---------------------------------------------------------- */
  var UNITS = ["B", "KB", "MB", "GB", "TB", "PB"];
  function split(n) {
    n = Number(n) || 0;
    var i = 0;
    while (Math.abs(n) >= 1024 && i < UNITS.length - 1) { n /= 1024; i++; }
    return { n: (i < 2 ? n.toFixed(0) : n.toFixed(1)), u: UNITS[i] };
  }
  LUM.split = split;
  LUM.size = function (n) { var s = split(n); return s.n + " " + s.u; };

  var MONTH = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  LUM.ago = function (iso) {
    var t = Date.parse(iso);
    if (isNaN(t)) { return "\u2013"; }
    var d = new Date(t), days = Math.floor((Date.now() - t) / 86400000);
    if (days <= 0) { return "today"; }
    if (days === 1) { return "yesterday"; }
    if (days < 14) { return days + " days ago"; }
    return d.getDate() + " " + MONTH[d.getMonth()];
  };

  /* NZBGet sends '00:14:22'; the arrs send '00:14:22.0000000'. Both are worth
     shortening on a phone. */
  LUM.eta = function (s) {
    var m = /^(\d+):(\d\d):(\d\d)/.exec(String(s || ""));
    if (!m) { return null; }
    var h = +m[1], mi = +m[2];
    if (h > 0) { return "~" + h + "h " + mi + "m"; }
    if (mi > 0) { return "~" + mi + " min"; }
    return "< 1 min";
  };

  /* ---- nodes, never strings -------------------------------------------------
     Nothing in this product is ever assembled as HTML. Every release name on this
     box was written by a stranger on the internet, so text only ever enters the
     document through .textContent and an escaping bug is not possible to write. */
  LUM.el = function (tag, cls, parent) {
    var n = document.createElement(tag);
    if (cls) { n.className = cls; }
    if (parent) { parent.appendChild(n); }
    return n;
  };
  LUM.txt = function (tag, cls, parent, s) {
    var n = LUM.el(tag, cls, parent);
    n.textContent = s;
    return n;
  };
  LUM.svg = function (tag, cls, parent) {
    var n = document.createElementNS("http://www.w3.org/2000/svg", tag);
    if (cls) { n.setAttribute("class", cls); }
    if (parent) { parent.appendChild(n); }
    return n;
  };
  LUM.caret = function (parent) {
    var s = LUM.svg("svg", "caret", parent);
    s.setAttribute("viewBox", "0 0 10 10");
    LUM.svg("path", null, s).setAttribute("d", "M2 0 L8 5 L2 10 Z");
    return s;
  };

  /* Initials for an invented plate. Two characters, from words, digits kept --
     "28 Days Later" -> "28", "House of Cards (US)" -> "HC". */
  LUM.initials = function (title) {
    var words = String(title || "").replace(/[^\w\s]/g, " ").trim().split(/\s+/);
    if (!words[0]) { return "\u2014"; }
    if (/^\d+$/.test(words[0])) { return words[0].slice(0, 2); }
    var a = words[0][0];
    var b = "";
    for (var i = 1; i < words.length; i++) {
      if (words[i].length > 2 || /^\d/.test(words[i])) { b = words[i][0]; break; }
    }
    return (a + b).toUpperCase();
  };

  /* ---- the frame loop -------------------------------------------------------
     LUM.loop(fn) registers a per-frame callback. fn(dt) returns truthy to stay
     registered for the next frame. The rAF is only alive while at least one
     callback wants it, so a settled page runs zero frames. */
  var cbs = [], persist = [], pending = false, last = 0;
  function frame(now) {
    pending = false;
    var dt = Math.min(0.05, (now - last) / 1000) || 0.016;
    last = now;
    var keep = [];
    for (var i = 0; i < cbs.length; i++) {
      try { if (cbs[i](dt)) { keep.push(cbs[i]); } }
      catch (e) { /* a broken visual must never take the page with it */ }
    }
    cbs = keep;
    arm();
  }
  /* Ask for the next frame, but never trust that one was already asked for: a
     dropped or throttled rAF -- a backgrounded tab, an iframe the compositor is
     not painting -- would otherwise leave the loop believing it is still running
     and kill every later animation on the page. */
  function arm() {
    if (!cbs.length || document.hidden) { return; }
    if (pending && (performance.now() - last) < 1200) { return; }
    pending = true;
    if (!last) { last = performance.now(); }
    requestAnimationFrame(frame);
  }

  /* `keepAwake` marks a callback as ambient: it is allowed to return false and
     stand down, and LUM.wake() puts it back. Without that list a loop that has
     stopped -- which is the whole point of the governor -- could never restart. */
  LUM.loop = function (fn, keepAwake) {
    if (typeof fn !== "function") { return; }
    if (keepAwake && persist.indexOf(fn) < 0) { persist.push(fn); }
    if (cbs.indexOf(fn) < 0) { cbs.push(fn); }
    arm();
  };

  /* Has the reader touched the page lately, and is motion wanted at all. Ambient
     visuals ask this every frame and stop themselves when the answer is no. */
  var touched = Date.now();
  LUM.awake = function () {
    return !LUM.reduced && !document.hidden && (Date.now() - touched) < IDLE_AFTER;
  };
  LUM.wake = function () {
    touched = Date.now();
    persist.forEach(function (f) { if (cbs.indexOf(f) < 0) { cbs.push(f); } });
    arm();
    if (LUM.onwake) { LUM.onwake(); }
  };
  ["pointerdown", "pointermove", "keydown", "scroll", "touchstart", "wheel"]
    .forEach(function (ev) {
      window.addEventListener(ev, LUM.wake, { passive: true });
    });
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) { LUM.wake(); }
  });

  /* ---- an interpolated value ------------------------------------------------
     .to(x) sets where it is going; .step(dt) moves it there. Under reduced motion
     it arrives immediately, which is what "truly disable motion" means. */
  LUM.num = function (v) {
    return {
      v: v || 0, t: v || 0, rate: 4.5,
      to: function (x) { this.t = Number(x) || 0; if (LUM.reduced) { this.v = this.t; } return this; },
      set: function (x) { this.v = this.t = Number(x) || 0; return this; },
      step: function (dt) {
        var k = 1 - Math.exp(-this.rate * dt);
        this.v += (this.t - this.v) * k;
        if (Math.abs(this.t - this.v) < 0.00001) { this.v = this.t; }
        return this.v;
      },
      done: function () { return this.v === this.t; }
    };
  };

  /* A figure that counts. Writes a formatted byte count into a node with a
     separate small unit span, and eases between polls rather than snapping. */
  LUM.figure = function (node) {
    var n = LUM.num(0), sfx = "";
    var val = LUM.el("span", null, node), unit = LUM.el("span", "u", node);
    function draw() {
      var s = split(n.v);
      val.textContent = s.n;
      unit.textContent = s.u + sfx;
    }
    function tick(dt) { n.step(dt); draw(); return !n.done(); }
    draw();
    return {
      to: function (x, immediate) {
        if (immediate || n.v === 0) { n.set(x); draw(); return; }
        n.to(x); LUM.loop(tick);
      },
      /* "MB" on the room, "MB/s" on the wire: same figure, two registers. */
      unit: function (s) { sfx = s || ""; draw(); },
      node: node
    };
  };

  /* ---- parallax -------------------------------------------------------------
     The field behind the page moves at a fraction of the scroll. One custom
     property, one transform, no layout, and nothing at all under reduced motion. */
  LUM.parallax = function () {
    if (LUM.reduced) { return; }
    var pending = false;
    window.addEventListener("scroll", function () {
      if (pending) { return; }
      pending = true;
      requestAnimationFrame(function () {
        pending = false;
        document.documentElement.style.setProperty(
          "--py", (window.scrollY * -0.06).toFixed(1) + "px");
      });
    }, { passive: true });
  };

  /* ---- one line of feedback, over the content, out of the way of the thumb --- */
  var msgTimer = null;
  LUM.say = function (t) {
    var m = document.getElementById("msg");
    if (!m) { return; }
    m.textContent = t;
    m.classList.remove("off");
    clearTimeout(msgTimer);
    msgTimer = setTimeout(function () { m.classList.add("off"); }, 9000);
  };

  /* ---- fetching -------------------------------------------------------------
     [CHANGE: claude-code | 2026-09-15] The design build shipped a demo shim here
     that fell back to a sample-*.json file beside the page whenever the real
     endpoint 404'd, 403'd or failed at the transport. That is fine on an artboard
     and wrong on this box: a missing token is a 403, so the shim would answer a
     credential failure by painting last week's fixture and the page would look
     healthy while showing numbers that are not true. Rejections are passed
     through; every caller already has a catch that says so out loud. */
  LUM.get = function (url) {
    function ok(r) { return r.ok ? r.json() : Promise.reject(r.status); }
    return fetch(url, { cache: "no-store" }).then(ok);
  };

  /* Same reasoning: a failed POST reports a failure, never a fabricated success. */
  LUM.post = function (url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (r) { return r.json(); })
      .catch(function () { return { ok: false, message: "no reply" }; });
  };

  /* ---- keyed list rendering -------------------------------------------------
     Nodes are kept and reused across polls, keyed on identity. Rebuilding would
     re-request every poster on every poll and flash the page for no reason. */
  LUM.keyed = function (container, items, key, make, fill, emptyNode) {
    var old = container._by || {}, now = {}, kids = [];
    items.forEach(function (it) {
      var k = key(it), node = old[k] || make(it);
      fill(node, it);
      now[k] = node;
      kids.push(node);
    });
    container._by = now;
    if (!kids.length) {
      container._by = {};
      kids.push(emptyNode ? emptyNode() : LUM.txt("div", "empty", null,
        container.getAttribute("data-empty") || "nothing here"));
    }
    container.replaceChildren.apply(container, kids);
  };

  window.LUM = LUM;
}());
