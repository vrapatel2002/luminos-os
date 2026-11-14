/* space.js -- the library and downloads tool.
   [REDESIGN: 2026-09-14]

   Served by luminos-space at /app.js, beside the identical app.css the hub uses.

   This page can delete things, so two rules are absolute:

     - Nothing is ever built as an HTML string. Every name here was chosen by a
       stranger on the internet, and one missed escape is an injection. Nodes are
       constructed and text goes in through .textContent, which makes the bug
       impossible rather than merely absent.
     - A delete button is never reachable without opening the row it belongs to,
       and the confirmation names the title and the bytes that actually come back
       -- frequently not the same as the size printed on the row. */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var size = LUM.size, el = LUM.el, txt = LUM.txt;

  /* The token stays a query-string parameter, read from the URL and put straight
     back on every request and every internal link. Never a cookie -- the browser
     would attach it to requests this page did not make -- and never localStorage,
     which would outlive the tab that was handed the link. */
  var TOKEN = new URLSearchParams(location.search).get("token") || "";
  function q(path) { return path + "?token=" + encodeURIComponent(TOKEN); }

  /* ROUTES: "/request" on the server. */
  $("ask").href = q("/request");

  LUM.parallax();

  /* ---- the pool ------------------------------------------------------------- */
  var freeFig = null;
  function pool(d) {
    if (!freeFig) { $("free").textContent = ""; freeFig = LUM.figure($("free")); }
    freeFig.to(d.disk.free);
    $("sig").textContent = "free";
    var sub = $("free-sub");
    sub.replaceChildren();
    // [CHANGE: cowork | 2026-11-13] DECISION 190: one bar per drive beside the figure.
    var md = $("mdrv");
    if (md) {
      var rows = (d.disks || []).map(function (k) {
        var r = el("div", "mdrv-row");
        txt("span", null, r, k.path.indexOf("external") >= 0 ? "external" : "internal");
        el("i", null, el("span", "mdrv-bar", r)).style.setProperty(
          "--w", (k.total ? k.used / k.total : 0).toFixed(4));
        txt("span", null, r, size(k.free) + " free of " + size(k.total));
        return r;
      });
      md.replaceChildren.apply(md, rows);
    }
    sub.appendChild(document.createTextNode("of " + size(d.disk.total) + " across "
      + d.disks.length + (d.disks.length === 1 ? " drive. " : " drives. ")));
    var twinned = d.series.reduce(function (a, s) { return a + (s.twins || 0); }, 0)
                + d.movies.reduce(function (a, m) { return a + (m.twins || 0); }, 0);
    if (twinned) {
      txt("b", null, sub, twinned + " file" + (twinned === 1 ? "" : "s"));
      sub.appendChild(document.createTextNode(
        " here also exist under downloads; deleting from this page removes both copies."));
    }
  }
  /* Deleting 150 GB should feel like 150 GB. The freed bytes land in the figure,
     which counts up from where it was and takes the light for a second. */
  function credit() {
    $("free").classList.remove("credited");
    void $("free").offsetWidth;
    if (!LUM.reduced) { $("free").classList.add("credited"); }
  }

  /* ---- one entry in the tree ------------------------------------------------
     `o` needs: key, title, bytes, frees, twins, and optional facts[] / acts(). */
  var open = new Set();
  var biggest = 1;

  /* [CHANGE: cowork | 2026-11-13] Who wants what -- DECISION 185. The server works out
     the verdict (one place, testable); this only draws it. A person blocks a delete if
     they have not finished it and they started it, hearted it in Jellyfin or requested
     it in Jellyseerr. */
  var FILTER = "all";
  function hm(m) { m = Math.round(m || 0); return m >= 60 ? Math.floor(m / 60) + "h " + (m % 60) + "m" : m + "m"; }
  function day(d) {
    if (!d) { return ""; }
    var t = new Date(d + "T12:00:00");
    return isNaN(t) ? d : t.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }
  function personLine(p, parent) {
    var row = el("div", "pp", parent);
    var who = el("span", "who", row);
    who.appendChild(document.createTextNode(p.name));
    if (p.fav) { txt("span", "hr", who, " \u2665"); }
    if (p.req) { txt("span", "rq", who, " requested"); }
    var bar = el("span", "bar", row);
    var frac = p.minsTotal ? p.mins / p.minsTotal : (p.total ? p.done / p.total : 0);
    var fill = el("i", p.total && p.done === p.total ? "done" : null, bar);
    fill.style.setProperty("--w", Math.min(1, frac).toFixed(4));
    var what = p.total > 1 ? p.done + "/" + p.total + " eps"
      : (p.done ? "finished" : (p.mins ? Math.round(frac * 100) + "%" : "not started"));
    var meta = what + " \u00b7 " + hm(p.mins) + " of " + hm(p.minsTotal);
    if (p.last) { meta += " \u00b7 last " + day(p.last); }
    txt("span", "meta", row, meta);
  }
  function verdictBlock(v, parent) {
    if (!v) { return; }
    var box = el("div", "vdw", parent);
    txt("span", "vd " + v.state, box, v.text);
    (v.people || []).forEach(function (p) { personLine(p, box); });
  }
  function filters() {
    var root = $("filt");
    if (!root || root.childNodes.length) { return; }
    [["all", "everything"], ["ok", "watched & safe"], ["warn", "someone still wants it"],
     ["none", "nobody started"]].forEach(function (f) {
      var b = txt("button", "btn" + (f[0] === FILTER ? " on" : ""), root, f[1]);
      b.type = "button";
      b.dataset.filt = f[0];
    });
  }
  function shown(v) { return FILTER === "all" || (v && v.state === FILTER); }

  function entry(o, parent) {
    var ent = el("div", "ent", parent);
    if (o.key && open.has(o.key)) { ent.classList.add("open"); }
    if (o.bytes >= biggest * 0.5) { ent.classList.add("big"); }

    var hdr = el("button", "hdr", ent);
    hdr.type = "button";
    if (o.key) {
      LUM.caret(hdr);
      hdr.setAttribute("aria-expanded", open.has(o.key) ? "true" : "false");
      hdr.dataset.tog = o.key;
    } else {
      el("span", "pad", hdr);
      hdr.disabled = true;
    }
    txt("span", "nm", hdr, o.title);
    txt("span", "amt", hdr, size(o.bytes));

    /* Size as volume, one slab per row, ranked against the largest thing in the
       library. A custom property rather than a width, so the transition runs on
       the compositor and the page carries no inline style attribute in markup. */
    var meas = el("div", "meas", ent);
    el("i", null, meas).style.setProperty(
      "--w", Math.max(0.004, o.bytes / biggest).toFixed(4));

    var sub = el("div", "sub-facts", ent);
    (o.facts || []).forEach(function (f) { txt("span", null, sub, f); });
    /* The whole reason this tool exists: 45% of this library is one series stored
       under two names for one inode. Sonarr's own delete would free nothing here
       and this one frees everything, so the row says so. */
    if (o.twins > 0) {
      txt("span", "twin", sub, o.twins + (o.twins === 1 ? " twinned copy" : " twinned copies"));
    }
    /* frees < bytes means something outside our view still holds the inode, so the
       size on this row is a lie. Rare, and the only case of it in the product. */
    if (o.frees < o.bytes) {
      txt("span", "stuck", sub, "frees only " + size(o.frees));
    }
    if (!sub.childNodes.length) { sub.classList.add("off"); }
    if (o.verdict) { verdictBlock(o.verdict, ent); }

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
     episode one, so an unlabelled one would read as episode one's. */
  function deleteBtn(parent, face, label, kind, id, season, frees, v) {
    var acts = el("div", "acts", parent);
    var b = txt("button", "btn danger", acts, face);
    b.type = "button";
    b.dataset.kind = kind;
    b.dataset.id = String(id);
    b.dataset.label = label;
    b.dataset.frees = String(frees);
    if (season !== null) { b.dataset.season = String(season); }
    if (v && v.state === "warn") { b.dataset.why = v.text; }
  }

  /* ---- library --------------------------------------------------------------- */
  function library(d) {
    var root = $("lib");
    biggest = Math.max(1,
      Math.max.apply(null, d.series.map(function (s) { return s.bytes; }).concat([0])),
      Math.max.apply(null, d.movies.map(function (m) { return m.bytes; }).concat([0])));

    var frag = document.createDocumentFragment();

    d.series.forEach(function (s) {
      if (!shown(s.verdict)) { return; }
      var eps = s.seasons.reduce(function (a, x) { return a + x.episodes; }, 0);
      var sf = [s.seasons.length + (s.seasons.length === 1 ? " season" : " seasons"),
                eps + (eps === 1 ? " episode" : " episodes")];
      if (s.mins) { sf.push(hm(s.mins) + " total"); }
      var kids = entry({
        key: "s" + s.id, title: s.title, bytes: s.bytes, frees: s.frees, twins: s.twins,
        facts: sf, verdict: s.verdict
      }, frag);

      s.seasons.forEach(function (se) {
        var facts = [se.episodes + (se.episodes === 1 ? " episode" : " episodes")];
        if (se.mins) { facts.push(hm(se.mins)); }
        if (se.added) { facts.push("on disk since " + day(se.added)); }
        if (!se.monitored) { facts.push("not monitored"); }
        var epk = entry({
          key: "s" + s.id + "e" + se.season,
          title: se.season === 0 ? "Specials" : "Season " + se.season,
          bytes: se.bytes, frees: se.frees, twins: se.twins, facts: facts,
          verdict: se.verdict,
          acts: function (into) {
            deleteBtn(into,
                      "delete all " + se.episodes
                      + (se.episodes === 1 ? " file" : " files") + " below",
                      s.title + " \u2014 Season " + se.season,
                      "season", s.id, se.season, se.frees, se.verdict);
          }
        }, kids);

        se.eps.forEach(function (ep) {
          var ef = [];
          if (ep.mins) { ef.push(hm(ep.mins)); }
          (d.people || []).forEach(function (n) {
            var w = (ep.w || {})[n];
            ef.push(n + (w ? (w.pct >= 90 ? " \u2713" : " " + w.pct + "%") : " \u2014"));
          });
          entry({
            key: null, facts: ef,
            title: "E" + String(ep.episode).padStart(2, "0")
                   + (ep.title ? "  " + ep.title : ""),
            bytes: ep.bytes, frees: ep.frees, twins: ep.twins,
            acts: function (into) {
              deleteBtn(into, "delete this episode",
                        s.title + " S" + se.season + "E" + ep.episode,
                        "episode", ep.fileId, null, ep.frees, ep.verdict);
            }
          }, epk);
        });
      });
    });

    d.movies.forEach(function (m) {
      if (!shown(m.verdict)) { return; }
      var mf = ["film"];
      if (m.mins) { mf.push(hm(m.mins)); }
      if (m.added) { mf.push("on disk since " + day(m.added)); }
      entry({
        key: "m" + m.id,
        title: m.title + (m.year ? " (" + m.year + ")" : ""),
        bytes: m.bytes, frees: m.frees, twins: m.twins, facts: mf, verdict: m.verdict,
        acts: function (into) {
          deleteBtn(into, "delete this film", m.title, "movie", m.id, null, m.frees, m.verdict);
        }
      }, frag);
    });

    if (!frag.childNodes.length) {
      txt("div", "empty", frag, FILTER === "all" ? "nothing with files" : "nothing matches this filter");
    }
    filters();
    if (d.watch && !d.watch.ok) {
      txt("div", "empty", frag, "Who-watched-what is unavailable right now: " + (d.watch.error || "Jellyfin did not answer"));
    }
    root.replaceChildren(frag);

    var titles = d.series.length + d.movies.length;
    var held = d.series.reduce(function (a, s) { return a + s.bytes; }, 0)
             + d.movies.reduce(function (a, m) { return a + m.bytes; }, 0);
    $("lib-aux").textContent = titles + (titles === 1 ? " title" : " titles")
      + " \u00b7 " + size(held) + " \u00b7 largest " + size(biggest);

    pool(d);
  }

  /* ---- downloads, grouped -----------------------------------------------------
     [CHANGE: cowork | 2026-11-13] DECISION 190. One row per show+season (or film);
     a season opens into one compact line per file, each with its own controls, and
     the group row carries "pause all / to the front / cancel all". Polled every 5s,
     so group AND row nodes are reused (LUM.keyed), never rebuilt: a rebuild would
     destroy the button under a thumb already on its way down. */
  var DCAP = 4, dOpen = {}, dAll = false, lastDl = null;

  function abtn(parent, cls, act) {
    var b = txt("button", cls, parent, "");
    b.type = "button";
    b.dataset.kind = "dl";
    b.dataset.act = act;
    return b;
  }
  function makeRow() {
    var r = el("div", "dg-row");
    r._n = el("span", "n", r);
    r._t = el("span", "t", r);
    r._s = el("span", "s", r);
    r._p = el("span", "p", r);
    var ib = el("span", "ib", r);
    r._pause = abtn(ib, "ibtn", "pause");
    r._top = abtn(ib, "ibtn", "top");
    r._top.textContent = "front";
    r._x = abtn(ib, "ibtn danger", "delete");
    r._x.textContent = "×";
    r._x.setAttribute("aria-label", "cancel");
    return r;
  }
  function fillRow(r, x) {
    var it = x.it, pct = it.bytes ? it.done / it.bytes * 100 : 0;
    r._n.textContent = x.p.ep ? "E" + LUM.pad2(x.p.ep) : "";
    r._t.textContent = x.p.epTitle || (x.p.ep ? "Episode " + x.p.ep : it.name);
    r._t.title = it.name;
    r._s.textContent = size(it.bytes);
    r._p.textContent = it.paused ? "held" : pct.toFixed(0) + "%";
    r._p.classList.toggle("on", !it.paused);
    r._pause.textContent = it.paused ? "resume" : "pause";
    r._pause.dataset.act = it.paused ? "resume" : "pause";
    r._pause.classList.toggle("on", it.paused);
    [r._pause, r._top, r._x].forEach(function (b) { b.dataset.id = String(it.id); b.disabled = false; });
    r._x.dataset.label = it.name;
  }
  function makeGroup() {
    var n = el("div", "dg");
    n._head = el("button", "dg-head", n);
    n._head.type = "button";
    el("span", "dg-caret", n._head);
    var t = el("span", "dg-t", n._head);
    n._tt = el("span", null, t);
    n._sub = el("small", null, t);
    n._amt = el("span", "dg-amt", n._head);
    n._bar = el("i", null, el("span", "dg-bar", n._head));
    n._meta = el("span", "dg-meta", n._head);
    n._pct = el("span", "on", n._meta);
    n._state = el("span", null, n._meta);
    n._health = el("span", "bad", n._meta);
    var acts = el("div", "dg-acts", n);
    n._pause = abtn(acts, "btn", "pause");
    n._top = abtn(acts, "btn", "top");
    n._top.textContent = "to the front";
    n._x = abtn(acts, "btn danger", "delete");
    n._body = el("div", "dg-body", n);
    return n;
  }
  function fillGroup(n, g) {
    var multi = g.items.length > 1, its = g.items.map(function (x) { return x.it; });
    var bytes = its.reduce(function (a, i) { return a + i.bytes; }, 0);
    var done = its.reduce(function (a, i) { return a + i.done; }, 0);
    var held = its.every(function (i) { return i.paused; });
    var moving = its.filter(function (i) { return !i.paused && /DOWNLOAD/i.test(i.status || ""); }).length;
    var worst = Math.min.apply(null, its.map(function (i) { return i.health; }));
    var frac = bytes ? Math.max(0, Math.min(1, done / bytes)) : 0;
    var ids = its.map(function (i) { return i.id; }).join(",");
    n._head.dataset.gtog = multi ? g.key : "";
    n.classList.toggle("multi", multi);
    n.classList.toggle("open", multi && !!dOpen[g.key]);
    n.classList.toggle("moving", !held);
    n.classList.toggle("held", held);
    n._tt.textContent = g.show;
    n._sub.textContent = g.season
      ? "  Season " + g.season + (multi ? " · " + its.length + " episodes"
                                       : " · E" + LUM.pad2(g.items[0].p.ep))
      : (g.year ? "  " + g.year : "");
    n._amt.textContent = size(done) + " / " + size(bytes);
    n._bar.style.transform = "scaleX(" + frac.toFixed(4) + ")";
    n._pct.textContent = (frac * 100).toFixed(0) + "%";
    n._state.textContent = held ? "held"
      : (moving ? moving + " downloading" : "waiting")
        + (multi && its.length - moving > 0 ? " · " + (its.length - moving) + " queued" : "");
    n._health.textContent = worst < 100 ? "health " + worst.toFixed(0) + "%" : "";
    var label = g.show + (g.season ? " — Season " + g.season : "")
      + (multi ? " (" + its.length + " files)" : "");
    n._pause.textContent = (held ? "resume" : "pause") + (multi ? " all" : "");
    n._pause.dataset.act = held ? "resume" : "pause";
    n._pause.classList.toggle("on", held);
    n._x.textContent = multi ? "cancel all" : "cancel";
    [n._pause, n._top, n._x].forEach(function (b) {
      b.dataset.ids = ids; b.dataset.label = label; b.disabled = false;
    });
    if (multi) {
      LUM.keyed(n._body, g.items, function (x) { return String(x.it.id); }, makeRow, fillRow);
    } else {
      n._body.replaceChildren();
      n._body._by = {};
    }
  }

  function downloads(d) {
    var root = $("dl");
    lastDl = d;
    if (d.error) {
      root._by = {};
      root.replaceChildren();
      txt("div", "empty", root, "cannot reach NZBGet — " + d.error);
      $("dl-aux").textContent = "";
      $("allbtn").classList.add("off");
      $("dl-more").classList.add("off");
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

    var groups = LUM.groupDownloads(d.items, function (it) { return it.name; });
    $("dl-aux").textContent = d.items.length
      ? size(d.rate) + "/s · " + size(d.remaining) + " left · "
        + groups.length + (groups.length === 1 ? " title" : " titles")
      : size(d.free) + " free to unpack into";

    LUM.keyed(root, dAll ? groups : groups.slice(0, DCAP), function (g) { return g.key; },
              makeGroup, fillGroup, function () {
      return txt("div", "empty", null,
        "Nothing downloading. The queue is empty most of the time on this box.");
    });
    var more = $("dl-more");
    more.classList.toggle("off", groups.length <= DCAP);
    more.textContent = dAll ? "show fewer"
      : "show all " + groups.length + " titles (" + d.items.length + " files)";
  }

  /* ---- loading ---------------------------------------------------------------- */
  var LAST = null;
  function loadLib() {
    /* A delete reloads this whole tree. Hold the scroll position, or the row you
       were looking at jumps away the moment you act on it. */
    var y = window.scrollY;
    return LUM.get(q("/api/data"))
      .then(function (d) { LAST = d; library(d); window.scrollTo(0, y); })
      .catch(function (e) {
        $("sig").textContent = e === 403 ? "no token" : "no reply";
        $("sig").classList.add("gone");
        $("free").textContent = e === 403 ? "NO TOKEN" : "NO REPLY";
        $("free-sub").textContent = e === 403
          ? "This page is reached through the front door, which adds the token for you."
          : "The server did not answer.";
        document.body.classList.add("stale");
      });
  }

  function loadDl() {
    return LUM.get(q("/api/downloads"))
      .then(downloads)
      .catch(function () { downloads({ error: "no reply", items: [] }); });
  }

  /* ---- one listener, so no handler is ever written into markup ---------------- */
  document.addEventListener("click", function (ev) {
    var t = ev.target.closest("button");
    if (!t) { return; }

    if (t.dataset.filt) {
      FILTER = t.dataset.filt;
      Array.prototype.forEach.call($("filt").children, function (b) {
        b.classList.toggle("on", b === t);
      });
      if (LAST) { library(LAST); }
      return;
    }

    if (t.dataset.tog) {
      var k = t.dataset.tog, ent = t.parentNode;
      if (open.has(k)) { open.delete(k); } else { open.add(k); }
      ent.classList.toggle("open", open.has(k));
      t.setAttribute("aria-expanded", open.has(k) ? "true" : "false");
      ent.querySelector(".kids").classList.toggle("off", !open.has(k));
      return;
    }

    // [CHANGE: cowork | 2026-11-13] DECISION 190: grouped downloads.
    if (t.id === "dl-more") { dAll = !dAll; if (lastDl) { downloads(lastDl); } return; }
    if (t.dataset.gtog) {
      dOpen[t.dataset.gtog] = !dOpen[t.dataset.gtog];
      if (lastDl) { downloads(lastDl); }
      return;
    }

    var d = t.dataset;
    if (d.kind === "dl") {
      var ids = d.ids ? d.ids.split(",").map(Number) : null;
      if (d.act === "delete" && !confirm((ids && ids.length > 1
            ? "Cancel all " + ids.length + " downloads?" : "Cancel this download?")
            + "\n\n" + d.label)) { return; }
      t.disabled = true;
      if (!ids) {
        LUM.post(q("/api/download-action"),
                 { action: d.act, id: d.id ? Number(d.id) : null })
          .then(function (r) { LUM.say(r.message); })
          .then(loadDl);
        return;
      }
      /* One call per file, in order. "to the front" goes last-first so the group
         lands at the top in its own episode order. */
      if (d.act === "top") { ids.reverse(); }
      var okN = 0, last = "";
      ids.reduce(function (p, id) {
        return p.then(function () {
          return LUM.post(q("/api/download-action"), { action: d.act, id: id })
            .then(function (r) { if (r.ok !== false) { okN++; } last = r.message; });
        });
      }, Promise.resolve()).then(function () {
        LUM.say(ids.length === 1 ? last : okN + " of " + ids.length + " done \u2014 " + last);
      }).then(loadDl);
      return;
    }

    if (d.kind === "season" || d.kind === "movie" || d.kind === "episode") {
      /* The confirmation names the title and the bytes that really come back --
         which is not the row's size when something else holds the inode. */
      /* [CHANGE: cowork | 2026-11-13] DECISION 185: someone still wants this -> say who,
         first, before the usual question. Two dialogs, so it cannot be one stray tap. */
      if (d.why && !confirm("HOLD ON \u2014 " + d.why + ".\n\nDelete " + d.label
                            + " anyway?")) { return; }
      if (!confirm("Delete " + d.label + "?\n\nThis frees "
                   + size(Number(d.frees)) + " and cannot be undone.")) { return; }
      t.disabled = true;
      LUM.say("deleting " + d.label + "\u2026");
      LUM.post(q("/api/delete"),
               { kind: d.kind, id: Number(d.id), season: d.season ? Number(d.season) : 0 })
        /* The free figure only flashes when something was actually freed. */
        .then(function (r) { LUM.say(r.message); if (r.ok) { credit(); } })
        .then(function () { loadLib(); loadDl(); });
    }
  });

  loadLib();
  loadDl();
  setInterval(loadDl, 5000);
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) { loadDl(); }
  });
}());
