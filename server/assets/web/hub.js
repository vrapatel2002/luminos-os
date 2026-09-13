/* hub.js -- the landing page's client.
   [CHANGE: claude-code | 2026-09-13]

   Served by luminos-hub at /app.js from /usr/local/share/luminos/web/hub.js.
   It is a real file at a real route, not an inline <script>, so the page can run
   under `script-src 'self'` with no 'unsafe-inline'.

   Three rules it never breaks:
     - Nothing is ever assembled as an HTML string. Nodes are constructed and text
       goes in through .textContent, so an escaping bug is not possible to write.
       Every release name on this box is attacker-chosen; see FINDINGS §5.
     - The server sends raw byte counts. Formatting happens here so a number can
       move between polls instead of snapping.
     - The poll interval is 15s and is never shortened. The server caches for 10s
       behind it. */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };

  /* ---- outbound links -------------------------------------------------------
     Ports are server-rendered onto data-port so the links are correct on the very
     first frame; only the host is filled in here, because the same page is reached
     on the LAN address and the tailnet address and must work on both. */
  var host = location.hostname;
  Array.prototype.forEach.call(document.querySelectorAll("a[data-port]"), function (a) {
    a.href = "https://" + host + ":" + a.getAttribute("data-port") + "/";
  });

  /* /offline is served by the same process and needs the link-filling above, but
     has nothing to poll. Everything past this point is the landing page. */
  if (!$("state-sub")) { return; }

  /* ---- formatting ---------------------------------------------------------- */
  var UNITS = ["B", "KB", "MB", "GB", "TB", "PB"];
  function size(n) {
    n = Number(n) || 0;
    var i = 0;
    while (Math.abs(n) >= 1024 && i < UNITS.length - 1) { n /= 1024; i++; }
    return (i < 2 ? n.toFixed(0) : n.toFixed(1)) + " " + UNITS[i];
  }

  var MONTH = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  function ago(iso) {
    var t = Date.parse(iso);
    if (isNaN(t)) { return "\u2013"; }
    var d = new Date(t);
    var days = Math.floor((Date.now() - t) / 86400000);
    if (days <= 0) { return "today"; }
    if (days === 1) { return "yesterday"; }
    if (days < 14) { return days + " days ago"; }
    return d.getDate() + " " + MONTH[d.getMonth()];
  }

  /* NZBGet's own eta strings are '00:14:22'; the arrs send '00:14:22.0000000'.
     Both are hours:minutes:seconds and both are worth shortening on a phone. */
  function eta(s) {
    var m = /^(\d+):(\d\d):(\d\d)/.exec(String(s || ""));
    if (!m) { return null; }
    var h = +m[1], mi = +m[2];
    if (h > 0) { return "~" + h + "h " + mi + "m"; }
    if (mi > 0) { return "~" + mi + " min"; }
    return "< 1 min";
  }

  /* ---- the room -------------------------------------------------------------
     Two isometric solids: height is capacity, filled height is usage. Volume is
     the honest encoding for two drives of unequal size -- a single pooled bar
     would claim they are interchangeable, and they are not (DECISION 91: the
     external is USB, has no readable SMART, and is expected to die unannounced).

     Drawn as plain SVG polygons. ~1 KB, no WebGL, and identical with hardware
     acceleration switched off because there is no canvas that can fail. */
  var W = 34, HH = 17, TALL = 96;          /* half-width, half-depth, tallest solid */

  function pts(a) {
    var s = [], i;
    for (i = 0; i < a.length; i += 2) { s.push(a[i].toFixed(1) + "," + a[i + 1].toFixed(1)); }
    return s.join(" ");
  }
  function topFace(h) { return [0, HH - h, W, -h, 0, -HH - h, -W, -h]; }
  function rightFace(h) { return [0, HH, W, 0, W, -h, 0, HH - h]; }
  function leftFace(h) { return [0, HH, -W, 0, -W, -h, 0, HH - h]; }
  function silhouette(h) { return [0, -HH - h, W, -h, W, 0, 0, HH, -W, 0, -W, -h]; }

  function solid(i, disk, tallest) {
    var g = $("v" + i);
    if (!disk) { g.classList.add("off"); $("fig" + i).classList.add("off"); return; }
    g.classList.remove("off");
    $("fig" + i).classList.remove("off");

    var full = TALL * Math.min(1, (disk.total || 1) / (tallest || 1));
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

    /* Colour is rationed: the solid only leaves the neutral greys once the drive
       is genuinely close to full. Below that it is material, not a warning. */
    var f = $("f" + i);
    f.classList.toggle("warnfill", pct >= 85 && pct < 95);
    f.classList.toggle("dangerfill", pct >= 95);

    var fig = $("fig" + i);
    fig.classList.toggle("tight", pct >= 85 && pct < 95);
    fig.classList.toggle("full", pct >= 95);
    $("w" + i).textContent = disk.name;
    $("g" + i).classList.toggle("off", !disk.risky);
    $("e" + i).textContent = size(disk.free);
    $("u" + i).textContent = "free of " + size(disk.total);
  }

  /* ---- keyed list rendering -------------------------------------------------
     Nodes are kept and reused across polls, keyed on the release name. Rebuilding
     the list would re-request every poster every 15 seconds and flash the page
     for no reason. Nothing here touches innerHTML. */
  function keyed(container, items, key, make, fill) {
    var old = container._by || {}, now = {}, kids = [];
    items.forEach(function (it) {
      var k = key(it), node = old[k];
      if (!node) { node = make(it); }
      fill(node, it);
      now[k] = node;
      kids.push(node);
    });
    container._by = now;
    if (!kids.length) {
      var e = document.createElement("div");
      e.className = "empty";
      e.textContent = container.getAttribute("data-empty") || "nothing here";
      kids.push(e);
      container._by = {};
    }
    container.replaceChildren.apply(container, kids);
  }

  function el(tag, cls, parent) {
    var n = document.createElement(tag);
    if (cls) { n.className = cls; }
    if (parent) { parent.appendChild(n); }
    return n;
  }

  /* ---- downloading ---------------------------------------------------------- */
  function makeQueue() {
    var n = el("div", "item");
    n._t = el("div", "t", n);
    var track = el("div", "track", n);
    n._track = track;
    n._bar = el("i", null, track);
    n._meta = el("div", "meta", n);
    n._pct = el("span", "on", n._meta);
    n._size = el("span", null, n._meta);
    n._eta = el("span", null, n._meta);
    n._app = el("span", null, n._meta);
    return n;
  }
  function fillQueue(n, r) {
    n._t.textContent = r.title;
    /* transform, not width: it stays on the compositor and animates for free. */
    n._bar.style.transform = "scaleX(" + (Math.max(0, Math.min(100, r.pct)) / 100) + ")";
    /* NZBGet's Status string lags up to 16 s and reports par2 repair as PAUSED.
       The byte delta is the truthful signal, so the bar leads and the chip is
       never allowed to contradict it -- see FINDINGS §5. */
    n._track.classList.toggle("held", !!r.held);
    n._pct.classList.toggle("on", !r.held);
    n._pct.textContent = r.pct.toFixed(0) + "%";
    n._size.textContent = size(r.bytes - r.left) + " of " + size(r.bytes);
    n._eta.textContent = r.held ? "held" : (eta(r.eta) || "\u2013");
    n._app.textContent = r.app;
  }

  /* ---- arrived --------------------------------------------------------------
     Artwork comes from the arrs' own MediaCover directory, read off disk by the
     server. Their HTTP route 302s to /login without a session, so proxying it
     would need an API key in the browser, which §6.3 forbids outright. */
  function makeArr(r) {
    var n = el("div", "item arr");
    if (r.art) {
      var img = el("img", null, n);
      img.width = 46; img.height = 68;     /* reserved, so nothing shifts on load */
      img.alt = "";
      img.loading = "lazy";
      img.src = r.art;
      /* A poster that 404s should leave a slot, not a broken-image glyph. */
      img.addEventListener("error", function () { img.classList.add("off"); });
    }
    var body = el("div", "body", n);
    n._nm = el("div", "nm", body);
    var meta = el("div", "meta", body);
    n._kind = el("span", null, meta);
    n._count = el("span", null, meta);
    n._when = el("span", null, meta);
    n._t = el("div", "t", body);
    return n;
  }
  function fillArr(n, r) {
    n._nm.textContent = r.title;
    n._kind.textContent = r.kind;
    var noun = r.kind === "tv" ? "episode" : "file";
    n._count.textContent = r.count + " " + noun + (r.count === 1 ? "" : "s");
    n._when.textContent = ago(r.when);
    /* The release name still matters -- it is the only thing that says 2160p or
       which group -- but it is not what you are scanning for here. */
    n._t.textContent = r.last;
  }

  /* ---- the readout ----------------------------------------------------------
     The single question this page exists to answer: is it doing anything. It is
     four times the size of everything else because that is the hierarchy, and
     because 61 % of downloads on this box fail -- idle is the normal state and
     must be stated plainly rather than styled as a fault (FINDINGS §5). */
  function state(d) {
    var r = $("state"), s = $("state-sub");
    r.classList.remove("live", "held");
    if (d.paused) {
      r.textContent = "HELD";
      r.classList.add("held");
      s.textContent = "Downloads are paused. Nothing will arrive until they are resumed.";
      return;
    }
    if (d.speed > 0) {
      r.textContent = size(d.speed) + "/s";
      r.classList.add("live");
      var left = d.queue.reduce(function (a, q) { return a + (q.left || 0); }, 0);
      s.replaceChildren();
      s.appendChild(document.createTextNode(
        d.queue.length + (d.queue.length === 1 ? " file" : " files") + ", "));
      var b = el("b", null, s);
      b.textContent = size(left);
      s.appendChild(document.createTextNode(" still to come."));
      return;
    }
    if (d.queue.length) {
      r.textContent = "QUEUED";
      s.textContent = d.queue.length + (d.queue.length === 1 ? " item is" : " items are")
        + " waiting, none moving yet.";
      return;
    }
    r.textContent = "IDLE";
    s.textContent = "Nothing is downloading.";
  }

  /* ---- poll ------------------------------------------------------------------ */
  function paint(d) {
    state(d);

    var tallest = d.disks.reduce(function (a, x) { return Math.max(a, x.total || 0); }, 0);
    solid(0, d.disks[0], tallest);
    solid(1, d.disks[1], tallest);
    var freeAll = d.disks.reduce(function (a, x) { return a + (x.free || 0); }, 0);
    $("room-aux").textContent = size(freeAll) + " free across "
      + d.disks.length + (d.disks.length === 1 ? " drive" : " drives");

    keyed($("queue"), d.queue, function (r) { return r.app + "\u0000" + r.title; },
          makeQueue, fillQueue);
    $("q-aux").textContent = d.queue.length ? String(d.queue.length) : "";

    keyed($("recent"), d.recent, function (r) { return r.kind + "\u0000" + r.title; },
          makeArr, fillArr);

    $("clock").textContent = d.at;
    document.body.classList.remove("stale");
  }

  function fail() {
    var r = $("state");
    r.classList.remove("live", "held");
    r.textContent = "NO REPLY";
    $("state-sub").textContent = "The server did not answer. It may be asleep or rebooting.";
    document.body.classList.add("stale");
  }

  function load() {
    fetch("/api/summary", { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
      .then(paint)
      .catch(fail);
  }

  load();
  setInterval(load, 15000);
  /* Coming back to a backgrounded tab should not show a stale number, and this
     costs nothing while the page is hidden. */
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) { load(); }
  });
}());
