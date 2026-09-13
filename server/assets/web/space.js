/* space.js -- the library and downloads tool.
   [CHANGE: claude-code | 2026-09-13]

   Served by luminos-space at /app.js from /usr/local/share/luminos/web/space.js,
   beside the identical app.css the landing page uses. Real routes rather than an
   inline <script>, so the page runs under `script-src 'self'`.

   This page can delete things, so two rules are absolute:

     - Nothing is ever built as an HTML string. The old page concatenated release
       names into innerHTML behind an esc() helper; every name here was chosen by
       a stranger, and one missed call is an injection. Nodes are constructed and
       text goes in through .textContent, which makes the bug impossible rather
       than merely absent.
     - A delete button is never reachable without opening the row it belongs to,
       and the confirmation names the title and the bytes that actually come back
       -- which is frequently not the same as the size on the row. */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };

  /* The token stays a query-string parameter, read from the URL and put straight
     back on each request. Never a cookie, never localStorage: a cookie would be
     sent by the browser on requests this page did not make, and localStorage would
     outlive the tab that was handed the link. */
  var TOKEN = new URLSearchParams(location.search).get("token") || "";
  function q(path) { return path + "?token=" + encodeURIComponent(TOKEN); }

  /* The way through to /request. Built here rather than server-rendered so the token
     is never written into a page constant, and it stays on this origin -- the hub has
     no token and must not be handed one. */
  $("ask").href = q("/request");

  var UNITS = ["B", "KB", "MB", "GB", "TB", "PB"];
  function size(n) {
    n = Number(n) || 0;
    var i = 0;
    while (Math.abs(n) >= 1024 && i < UNITS.length - 1) { n /= 1024; i++; }
    return (i < 2 ? n.toFixed(0) : n.toFixed(1)) + " " + UNITS[i];
  }

  function el(tag, cls, parent) {
    var n = document.createElement(tag);
    if (cls) { n.className = cls; }
    if (parent) { parent.appendChild(n); }
    return n;
  }
  function txt(tag, cls, parent, s) {
    var n = el(tag, cls, parent);
    n.textContent = s;
    return n;
  }

  var CARET = "M2 0 L8 5 L2 10 Z";
  function caret(parent) {
    var s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    s.setAttribute("class", "caret");
    s.setAttribute("viewBox", "0 0 10 10");
    var p = document.createElementNS("http://www.w3.org/2000/svg", "path");
    p.setAttribute("d", CARET);
    s.appendChild(p);
    parent.appendChild(s);
    return s;
  }

  var msgTimer = null;
  function say(t) {
    var m = $("msg");
    m.textContent = t;
    m.classList.remove("off");
    clearTimeout(msgTimer);
    msgTimer = setTimeout(function () { m.classList.add("off"); }, 9000);
  }

  /* Which rows are expanded. A refresh must not collapse the tree under someone
     mid-scroll, and a delete refreshes the tree. */
  var open = new Set();
  var biggest = 1;

  /* ---- one entry in the tree ------------------------------------------------
     `o` needs: key, title, bytes, frees, twins, and optional facts[] / acts[]. */
  function entry(o, parent) {
    var ent = el("div", "ent", parent);
    if (o.key && open.has(o.key)) { ent.classList.add("open"); }
    if (o.bytes >= biggest * 0.5) { ent.classList.add("big"); }

    var hdr = el("button", "hdr", ent);
    hdr.type = "button";
    if (o.key) {
      caret(hdr);
      hdr.setAttribute("aria-expanded", open.has(o.key) ? "true" : "false");
      hdr.dataset.tog = o.key;
    } else {
      el("span", "pad", hdr);
      hdr.disabled = true;
    }
    txt("span", "nm", hdr, o.title);
    txt("span", "amt", hdr, size(o.bytes));

    var meas = el("div", "meas", ent);
    el("i", null, meas).style.transform =
      "scaleX(" + Math.max(0.004, o.bytes / biggest).toFixed(4) + ")";

    var sub = el("div", "sub", ent);
    (o.facts || []).forEach(function (f) { txt("span", null, sub, f); });
    /* The whole reason this tool exists. 45 % of this library is one series
       stored under two names for one inode; Sonarr's own delete would free
       nothing, and this one frees everything. Say so on the row. */
    if (o.twins > 0) {
      txt("span", "twin", sub, o.twins + (o.twins === 1 ? " twinned copy" : " twinned copies"));
    }
    /* frees < bytes means something outside the downloads tree still holds the
       inode. It does not happen on demand -- NZBGet's completed directory is not
       walked, deliberately, because walking it would put its files on the delete
       path -- but when it does happen the size on the row is a lie and must say so. */
    if (o.frees < o.bytes) {
      txt("span", "stuck", sub, "frees only " + size(o.frees));
    }
    if (!sub.childNodes.length) { sub.classList.add("off"); }

    var kids = null;
    if (o.key) {
      kids = el("div", "kids", ent);
      if (!open.has(o.key)) { kids.classList.add("off"); }
    }
    if (o.acts) { o.acts(kids || ent); }
    return kids;
  }

  /* `face` is what the button says, and it is never just "delete". A season's
     button is the first thing inside the season's open body, directly above
     episode one, so an unlabelled one reads as episode one's. Naming what each
     button destroys is the cheapest part of §6.6. */
  function deleteBtn(parent, face, label, kind, id, season, frees) {
    var acts = el("div", "acts", parent);
    var b = txt("button", "btn danger", acts, face);
    b.type = "button";
    b.dataset.kind = kind;
    b.dataset.id = String(id);
    b.dataset.label = label;
    b.dataset.frees = String(frees);
    if (season !== null) { b.dataset.season = String(season); }
  }

  /* ---- library --------------------------------------------------------------- */
  function library(d) {
    var root = $("lib");
    biggest = Math.max(1,
      Math.max.apply(null, d.series.map(function (s) { return s.bytes; }).concat([0])),
      Math.max.apply(null, d.movies.map(function (m) { return m.bytes; }).concat([0])));

    var frag = document.createDocumentFragment();

    d.series.forEach(function (s) {
      var eps = s.seasons.reduce(function (a, x) { return a + x.episodes; }, 0);
      var kids = entry({
        key: "s" + s.id, title: s.title, bytes: s.bytes, frees: s.frees, twins: s.twins,
        facts: [s.seasons.length + (s.seasons.length === 1 ? " season" : " seasons"),
                eps + (eps === 1 ? " file" : " files")]
      }, frag);

      s.seasons.forEach(function (se) {
        var facts = [se.episodes + (se.episodes === 1 ? " file" : " files")];
        if (!se.monitored) { facts.push("not monitored"); }
        var epk = entry({
          key: "s" + s.id + "e" + se.season,
          title: se.season === 0 ? "Specials" : "Season " + se.season,
          bytes: se.bytes, frees: se.frees, twins: se.twins, facts: facts,
          acts: function (into) {
            deleteBtn(into,
                      "delete all " + se.episodes
                      + (se.episodes === 1 ? " file" : " files") + " below",
                      s.title + " \u2014 Season " + se.season,
                      "season", s.id, se.season, se.frees);
          }
        }, kids);

        se.eps.forEach(function (ep) {
          entry({
            key: null,
            title: "E" + String(ep.episode).padStart(2, "0")
                   + (ep.title ? "  " + ep.title : ""),
            bytes: ep.bytes, frees: ep.frees, twins: ep.twins,
            acts: function (into) {
              deleteBtn(into, "delete this episode",
                        s.title + " S" + se.season + "E" + ep.episode,
                        "episode", ep.fileId, null, ep.frees);
            }
          }, epk);
        });
      });
    });

    d.movies.forEach(function (m) {
      entry({
        key: "m" + m.id,
        title: m.title + (m.year ? " (" + m.year + ")" : ""),
        bytes: m.bytes, frees: m.frees, twins: m.twins,
        acts: function (into) {
          deleteBtn(into, "delete this film", m.title, "movie", m.id, null, m.frees);
        }
      }, frag);
    });

    if (!frag.childNodes.length) { txt("div", "empty", frag, "nothing with files"); }
    root.replaceChildren(frag);

    var titles = d.series.length + d.movies.length;
    var held = d.series.reduce(function (a, s) { return a + s.bytes; }, 0)
             + d.movies.reduce(function (a, m) { return a + m.bytes; }, 0);
    $("lib-aux").textContent = titles + (titles === 1 ? " title" : " titles")
      + " \u00b7 " + size(held);

    $("free").textContent = size(d.disk.free);
    $("free-sub").replaceChildren();
    $("free-sub").appendChild(document.createTextNode("free of " + size(d.disk.total)
      + " across " + d.disks.length + (d.disks.length === 1 ? " drive. " : " drives. ")));
    var twinned = d.series.reduce(function (a, s) { return a + (s.twins || 0); }, 0)
                + d.movies.reduce(function (a, m) { return a + (m.twins || 0); }, 0);
    if (twinned) {
      var b = el("b", null, $("free-sub"));
      b.textContent = twinned + " file" + (twinned === 1 ? "" : "s");
      $("free-sub").appendChild(document.createTextNode(
        " here also exist under downloads; deleting from this page removes both."));
    }
  }

  /* ---- downloads -------------------------------------------------------------
     Polled every 5 s, so nodes are reused rather than rebuilt -- a rebuild would
     destroy the button under a thumb that is already on its way down. */
  function makeDl() {
    var n = el("div", "item");
    n._t = el("div", "t", n);
    n._track = el("div", "track", n);
    n._bar = el("i", null, n._track);
    n._meta = el("div", "meta", n);
    n._pct = el("span", "on", n._meta);
    n._size = el("span", null, n._meta);
    n._state = el("span", null, n._meta);
    n._health = el("span", "bad", n._meta);
    n._acts = el("div", "acts", n);
    n._pause = txt("button", "btn", n._acts, "pause");
    n._top = txt("button", "btn", n._acts, "to the front");
    n._cancel = txt("button", "btn danger", n._acts, "cancel");
    [n._pause, n._top, n._cancel].forEach(function (b) {
      b.type = "button";
      b.dataset.kind = "dl";
    });
    n._top.dataset.act = "top";
    n._cancel.dataset.act = "delete";
    return n;
  }
  function fillDl(n, it) {
    var pct = it.bytes ? (it.done / it.bytes * 100) : 0;
    n._t.textContent = it.name;
    n._bar.style.transform = "scaleX(" + (pct / 100).toFixed(4) + ")";
    n._track.classList.toggle("held", it.paused);
    n._pct.classList.toggle("on", !it.paused);
    n._pct.textContent = pct.toFixed(0) + "%";
    n._size.textContent = size(it.done) + " of " + size(it.bytes);
    /* `paused` is not NZBGet's Status string: that reads DOWNLOADING for 3-6 s
       after a pause while connections drain, and PausedSizeMB alone is the par2
       set every healthy group holds back. The server settles both before it
       answers -- see group_paused(). */
    n._state.textContent = it.paused ? "held" : (it.status || "").toLowerCase();
    n._health.textContent = it.health < 100 ? "health " + it.health.toFixed(0) + "%" : "";
    n._pause.textContent = it.paused ? "resume" : "pause";
    n._pause.classList.toggle("on", it.paused);
    n._pause.dataset.act = it.paused ? "resume" : "pause";
    [n._pause, n._top, n._cancel].forEach(function (b) { b.dataset.id = String(it.id); });
    n._cancel.dataset.label = it.name;
  }

  var dlBy = {};
  function downloads(d) {
    var root = $("dl");
    if (d.error) {
      dlBy = {};
      root.replaceChildren();
      txt("div", "empty", root, "cannot reach NZBGet \u2014 " + d.error);
      $("dl-aux").textContent = "";
      $("allbtn").classList.add("off");
      return;
    }

    var all = $("allbtn");
    /* An empty queue has nothing to pause, so the button goes away. It stays when
       the queue is empty but paused, because "resume everything" still does
       something then -- it is what lets the next grab start. */
    all.classList.toggle("off", !d.items.length && !d.globalPaused);
    all.textContent = d.globalPaused ? "resume everything" : "pause everything";
    all.classList.toggle("on", d.globalPaused);
    all.dataset.act = d.globalPaused ? "resumeall" : "pauseall";

    $("dl-aux").textContent = d.items.length
      ? size(d.rate) + "/s \u00b7 " + size(d.remaining) + " left"
      : size(d.free) + " free to unpack into";

    var now = {}, kids = [];
    d.items.forEach(function (it) {
      var node = dlBy[it.id] || makeDl();
      fillDl(node, it);
      now[it.id] = node;
      kids.push(node);
    });
    dlBy = now;
    if (!kids.length) { kids.push(txt("div", "empty", null, "nothing downloading")); }
    root.replaceChildren.apply(root, kids);
  }

  /* ---- loading ---------------------------------------------------------------- */
  function loadLib() {
    /* A delete reloads this whole tree. Hold the scroll position, or the row you
       were looking at jumps away the moment you act on it. */
    var y = window.scrollY;
    return fetch(q("/api/data"), { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
      .then(function (d) { library(d); window.scrollTo(0, y); })
      .catch(function (e) {
        $("free").textContent = e === 403 ? "NO TOKEN" : "NO REPLY";
        $("free-sub").textContent = e === 403
          ? "This page is reached through the front door, which adds the token for you."
          : "The server did not answer.";
      });
  }

  function loadDl() {
    return fetch(q("/api/downloads"), { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
      .then(downloads)
      .catch(function () { downloads({ error: "no reply", items: [] }); });
  }

  function post(path, body) {
    return fetch(q(path), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (r) { return r.json(); });
  }

  /* ---- one listener, so no handler is ever written into markup ---------------- */
  document.addEventListener("click", function (ev) {
    var t = ev.target.closest("button");
    if (!t) { return; }

    if (t.dataset.tog) {
      var k = t.dataset.tog, ent = t.parentNode;
      if (open.has(k)) { open.delete(k); } else { open.add(k); }
      ent.classList.toggle("open", open.has(k));
      t.setAttribute("aria-expanded", open.has(k) ? "true" : "false");
      ent.querySelector(".kids").classList.toggle("off", !open.has(k));
      return;
    }

    var d = t.dataset;
    if (d.kind === "dl") {
      if (d.act === "delete" && !confirm("Cancel this download?\n\n" + d.label)) { return; }
      t.disabled = true;
      post("/api/download-action", { action: d.act, id: d.id ? Number(d.id) : null })
        .then(function (r) { say(r.message); })
        .catch(function () { say("that did not reach the server"); })
        .then(loadDl);
      return;
    }

    if (d.kind === "season" || d.kind === "movie" || d.kind === "episode") {
      /* The confirmation names the title and the bytes that really come back --
         which is not the row's size when something else holds the inode. */
      if (!confirm("Delete " + d.label + "?\n\nThis frees "
                   + size(Number(d.frees)) + " and cannot be undone.")) { return; }
      t.disabled = true;
      say("deleting " + d.label + "\u2026");
      post("/api/delete", {
        kind: d.kind, id: Number(d.id), season: d.season ? Number(d.season) : 0
      }).then(function (r) { say(r.message); })
        .catch(function () { say("that did not reach the server"); })
        .then(function () { loadLib(); loadDl(); });
    }
  });

  loadLib();
  loadDl();
  setInterval(loadDl, 5000);
}());
