/* ask.js -- asking for a title, absorbed from Jellyseerr.
   [REDESIGN: 2026-09-14]

   Served by luminos-space at /ask.js. Same token, same rules as space.js: no HTML
   strings anywhere, and the one button that spends disk and bandwidth on someone
   else's schedule confirms first.

   Every title on this page was written by a stranger on the internet, which is the
   whole reason nodes are constructed rather than concatenated. */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var el = LUM.el, txt = LUM.txt;

  var TOKEN = new URLSearchParams(location.search).get("token") || "";
  function q(path) { return path + "?token=" + encodeURIComponent(TOKEN); }

  /* The way back carries the token, because every route on this origin needs it
     and the hub -- which has no token -- must never be handed one to hold.
     ROUTES: "/" on the server. */
  $("home").href = q("/");

  LUM.parallax();

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
    rows.forEach(function (r, i) {
      var hit = el("div", "hit", frag);

      /* The invented plate: a rule and the result's index, cropped by the frame.
         It gives the page visual rhythm without a single byte fetched off-origin,
         and it is meant to look invented rather than look like a missing poster. */
      var idx = el("div", "idx", hit);
      el("s", null, idx);
      txt("b", null, idx, String(i + 1).padStart(2, "0"));

      var body = el("div", "body", hit);
      var ttl = el("div", "ttl", body);
      ttl.appendChild(document.createTextNode(r.title));
      if (r.year) { txt("span", "yr", ttl, String(r.year)); }

      var sub = el("div", "sub-facts", body);
      txt("span", null, sub, r.kind === "tv" ? "series" : "film");

      /* The one fact that stops a pointless request, so it gets the loud colour
         and a line of its own rather than sitting in the row of grey facts. */
      if (r.have) { txt("div", "have", body, r.have); }
      if (r.blurb) { txt("p", "blurb", body, r.blurb); }

      /* Already here, on the way, partly here, asked for -- there is nothing
         useful to press, so there is no button. */
      if (r.have) { return; }
      var acts = el("div", "acts", body);
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
    LUM.get(q("/api/search") + "&q=" + encodeURIComponent(term))
      .then(function (d) {
        if (mine !== seq) { return; }
        render(d);
      })
      .catch(function () { if (mine === seq) { render({ error: "no reply" }); } });
  }

  $("form").addEventListener("submit", function (e) {
    e.preventDefault();
    var term = $("q").value.trim();
    if (term) { search(term); }
  });

  $("res").addEventListener("click", function (e) {
    var b = e.target.closest("button.btn");
    if (!b) { return; }
    if (!confirm("Ask for " + b.dataset.label + "?")) { return; }
    b.disabled = true;
    LUM.post(q("/api/request"), { kind: b.dataset.kind, id: Number(b.dataset.id) })
      .then(function (d) {
        LUM.say(d.message || (d.ok ? "asked" : "failed"));
        if (d.ok) { b.textContent = "asked for"; } else { b.disabled = false; }
      });
  });

  /* Nothing has been asked yet. The results slot says so rather than sitting as
     an empty rule under a label. */
  txt("div", "empty", $("res"), "Type a name. Nothing is requested until you press a button.");

  /* DEMO SHIM: ?q=dune prefills the field and runs the search, so the results
     state is reachable without a Jellyseerr behind the page. */
  var pre = new URLSearchParams(location.search).get("q");
  if (pre) { $("q").value = pre; search(pre); }

  $("q").focus();
}());
