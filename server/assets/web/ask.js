/* ask.js -- asking for a title, absorbed from Jellyseerr.
   [CHANGE: claude-code | 2026-09-13]

   Served by luminos-space at /ask.js. Same token, same rules as space.js: no HTML
   strings anywhere, and the one button that mutates something confirms first.

   Every title on this page was written by a stranger on the internet, which is the
   whole reason nodes are constructed rather than concatenated. */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };

  var TOKEN = new URLSearchParams(location.search).get("token") || "";
  function q(path) { return path + "?token=" + encodeURIComponent(TOKEN); }

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

  var msgTimer = null;
  function say(t) {
    var m = $("msg");
    m.textContent = t;
    m.classList.remove("off");
    clearTimeout(msgTimer);
    msgTimer = setTimeout(function () { m.classList.add("off"); }, 9000);
  }

  /* The way back carries the token, because every route on this origin needs it and
     the hub -- which has no token -- must never be given one to hold (§6.4). */
  $("home").href = q("/");

  function render(d) {
    var root = $("res");
    root.replaceChildren();
    if (d.error) {
      $("res-aux").textContent = "";
      txt("div", "empty", root, "cannot reach Jellyseerr \u2014 " + d.error);
      return;
    }
    var rows = d.results || [];
    $("res-aux").textContent = rows.length ? rows.length + " found" : "";
    if (!rows.length) {
      txt("div", "empty", root, "nothing by that name");
      return;
    }
    var frag = document.createDocumentFragment();
    rows.forEach(function (r) {
      var ent = el("div", "ent", frag);
      var hdr = el("div", "hdr", ent);
      el("span", "pad", hdr);
      txt("span", "nm", hdr, r.title);
      txt("span", "amt", hdr, r.year || "");

      var sub = el("div", "sub", ent);
      txt("span", null, sub, r.kind === "tv" ? "series" : "film");
      /* The one fact that stops a pointless request, so it gets the loud colour. */
      if (r.have) { txt("span", "twin", sub, r.have); }

      if (r.blurb) { txt("p", "blurb", ent, r.blurb); }

      /* Already here, or already asked for -- there is nothing useful to press. */
      if (r.have) { return; }
      var acts = el("div", "acts", ent);
      var b = txt("button", "btn", acts, "ask for this");
      b.type = "button";
      b.dataset.id = String(r.id);
      b.dataset.kind = r.kind;
      b.dataset.label = r.title + (r.year ? " (" + r.year + ")" : "");
    });
    root.appendChild(frag);
  }

  var seq = 0;
  function search(term) {
    var mine = ++seq;
    $("res-aux").textContent = "looking\u2026";
    fetch(q("/api/search") + "&q=" + encodeURIComponent(term))
      .then(function (r) { return r.json(); })
      .then(function (d) { if (mine === seq) { render(d); } })
      .catch(function () {
        if (mine === seq) { render({ error: "no reply" }); }
      });
  }

  $("form").addEventListener("submit", function (e) {
    e.preventDefault();
    var term = $("q").value.trim();
    if (term) { search(term); }
  });

  $("res").addEventListener("click", function (e) {
    var b = e.target.closest("button.btn");
    if (!b) { return; }
    /* Asking is not destructive, but it does spend disk and bandwidth on someone
       else's schedule, so it still names what it is about to fetch. */
    if (!confirm("Ask for " + b.dataset.label + "?")) { return; }
    b.disabled = true;
    fetch(q("/api/request"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind: b.dataset.kind, id: Number(b.dataset.id) })
    }).then(function (r) { return r.json(); })
      .then(function (d) {
        say(d.message || (d.ok ? "asked" : "failed"));
        if (d.ok) { b.textContent = "asked for"; } else { b.disabled = false; }
      })
      .catch(function () { say("no reply"); b.disabled = false; });
  });

  $("q").focus();
}());
