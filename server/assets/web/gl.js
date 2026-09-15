/* gl.js -- the two drives, as objects.
   [REDESIGN: 2026-09-14]

   Hand-written WebGL1. No library, no vendored file, no `eval`, no `new Function`,
   so no CSP change: this runs unmodified under `default-src 'none'; script-src 'self'`.
   Three.js would have been ~600 KB unminified (~170 KB gzipped for a trimmed
   build) to draw twelve triangles and one light, against a third of the entire
   JS budget for the product. This file is ~9 KB.

   What the geometry is FOR: the internal is 875 GB of SATA, the external is a
   457 GB USB disk with no readable SMART that is expected to fail without warning
   (DECISION 91). They are not interchangeable and must never be pooled into one
   bar. Two solids, standing next to each other, unequal heights, one of them
   marked -- you read the comparison before you read a single digit.

   Height is capacity. Filled volume is usage. Drag turns the pair.

   Budget: 2 objects, 4 draw calls each, 36 triangles, one directional light plus a
   hemisphere term, no post-processing, no shadow map, no texture. It renders only
   while something is moving -- a settled, idle, or backgrounded page runs no
   frames at all, because this is a phone held in bed.

   If anything at all goes wrong -- no context, a failed compile, a lost context --
   mount() returns null and the caller reveals the SVG solids instead. WebGL is
   allowed to fail. */
(function () {
  "use strict";

  /* ---- 4x4 maths, only the four operations actually needed ------------------ */
  function mul(a, b) {
    var o = new Float32Array(16), i, j, k, s;
    for (i = 0; i < 4; i++) {
      for (j = 0; j < 4; j++) {
        s = 0;
        for (k = 0; k < 4; k++) { s += a[k * 4 + j] * b[i * 4 + k]; }
        o[i * 4 + j] = s;
      }
    }
    return o;
  }
  function persp(fovy, asp, n, f) {
    var t = 1 / Math.tan(fovy / 2);
    return new Float32Array([t / asp, 0, 0, 0, 0, t, 0, 0,
                             0, 0, (f + n) / (n - f), -1,
                             0, 0, (2 * f * n) / (n - f), 0]);
  }
  function norm(v) {
    var l = Math.hypot(v[0], v[1], v[2]) || 1;
    return [v[0] / l, v[1] / l, v[2] / l];
  }
  function cross(a, b) {
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  }
  function look(eye, c, up) {
    var z = norm([eye[0] - c[0], eye[1] - c[1], eye[2] - c[2]]);
    var x = norm(cross(up, z)), y = cross(z, x);
    function d(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
    return new Float32Array([x[0], y[0], z[0], 0, x[1], y[1], z[1], 0,
                             x[2], y[2], z[2], 0,
                             -d(x, eye), -d(y, eye), -d(z, eye), 1]);
  }
  function trs(tx, ty, tz, sx, sy, sz) {
    return new Float32Array([sx, 0, 0, 0, 0, sy, 0, 0, 0, 0, sz, 0, tx, ty, tz, 1]);
  }

  /* ---- a unit box, y from 0 to 1, centred on x/z ---------------------------- */
  var F = [                                        /* face: normal, 4 corners */
    [[0, 0, 1], [-.5, 0, .5], [.5, 0, .5], [.5, 1, .5], [-.5, 1, .5]],
    [[0, 0, -1], [.5, 0, -.5], [-.5, 0, -.5], [-.5, 1, -.5], [.5, 1, -.5]],
    [[1, 0, 0], [.5, 0, .5], [.5, 0, -.5], [.5, 1, -.5], [.5, 1, .5]],
    [[-1, 0, 0], [-.5, 0, -.5], [-.5, 0, .5], [-.5, 1, .5], [-.5, 1, -.5]],
    [[0, 1, 0], [-.5, 1, .5], [.5, 1, .5], [.5, 1, -.5], [-.5, 1, -.5]],
    [[0, -1, 0], [-.5, 0, -.5], [.5, 0, -.5], [.5, 0, .5], [-.5, 0, .5]]
  ];
  function boxData() {
    var v = [], idx = [], i, f, c;
    for (i = 0; i < F.length; i++) {
      f = F[i];
      for (c = 1; c <= 4; c++) {
        v.push(f[c][0], f[c][1], f[c][2], f[0][0], f[0][1], f[0][2]);
      }
      var o = i * 4;
      idx.push(o, o + 1, o + 2, o, o + 2, o + 3);
    }
    return { v: new Float32Array(v), i: new Uint16Array(idx) };
  }
  function edgeData() {
    var p = [], q = [[-.5, 0, -.5], [.5, 0, -.5], [.5, 0, .5], [-.5, 0, .5]], i;
    for (i = 0; i < 4; i++) {
      var a = q[i], b = q[(i + 1) % 4];
      p.push(a[0], 0, a[2], 0, 0, 0, b[0], 0, b[2], 0, 0, 0);          /* bottom */
      p.push(a[0], 1, a[2], 0, 0, 0, b[0], 1, b[2], 0, 0, 0);          /* top */
      p.push(a[0], 0, a[2], 0, 0, 0, a[0], 1, a[2], 0, 0, 0);          /* upright */
    }
    return new Float32Array(p);
  }

  var VS = [
    "attribute vec3 aP;attribute vec3 aN;",
    "uniform mat4 uMVP;uniform vec3 uScale;",
    "varying vec3 vN;varying vec3 vW;",
    "void main(){vN=normalize(aN/uScale);vW=aP;",
    "gl_Position=uMVP*vec4(aP,1.0);}"
  ].join("\n");

  /* Cheap lighting, deliberately: one directional term, one hemisphere term for
     the sky, one rim term for the warm light in the room. No specular map, no
     shadow, no ambient occlusion. The three face tones it resolves to are the
     same --face-top / --face-r / --face-l the SVG fallback paints by hand, so the
     canvas and the fallback are recognisably the same object. */
  var FS = [
    "precision mediump float;",
    "varying vec3 vN;varying vec3 vW;",
    "uniform vec3 uTint;uniform vec3 uL;uniform float uAlpha;",
    "uniform float uFlat;uniform float uRim;",
    "void main(){",
    " if(uFlat>0.5){gl_FragColor=vec4(uTint,uAlpha);return;}",
    " vec3 n=normalize(vN);",
    " float d=max(dot(n,normalize(uL)),0.0);",
    " float hemi=0.5+0.5*n.y;",
    " vec3 c=uTint*(0.26+0.68*d+0.26*hemi);",
    " float f=pow(1.0-abs(n.z),2.5);",
    " c+=vec3(1.0,0.48,0.09)*f*uRim;",
    " gl_FragColor=vec4(c,uAlpha);}"
  ].join("\n");

  function hex(s) {
    s = String(s || "").trim().replace("#", "");
    if (s.length !== 6) { return [0.4, 0.38, 0.35]; }
    return [parseInt(s.slice(0, 2), 16) / 255,
            parseInt(s.slice(2, 4), 16) / 255,
            parseInt(s.slice(4, 6), 16) / 255];
  }
  function token(name, fallback) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(name);
    return hex(v || fallback);
  }

  /* ---- mount ---------------------------------------------------------------- */
  window.GLDrives = {
    mount: function (canvas) {
      var gl = null;
      try {
        gl = canvas.getContext("webgl", {
          alpha: true, antialias: true, depth: true, premultipliedAlpha: false,
          /* kept on so the canvas survives a screenshot and a compositor hiccup;
             at 36 triangles the cost of not discarding the buffer is nil */
          preserveDrawingBuffer: true,
          powerPreference: "low-power", failIfMajorPerformanceCaveat: false
        });
      } catch (e) { gl = null; }
      if (!gl) { return null; }

      function shader(type, src) {
        var s = gl.createShader(type);
        gl.shaderSource(s, src);
        gl.compileShader(s);
        if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) { return null; }
        return s;
      }
      var vs = shader(gl.VERTEX_SHADER, VS), fs = shader(gl.FRAGMENT_SHADER, FS);
      if (!vs || !fs) { return null; }
      var prog = gl.createProgram();
      gl.attachShader(prog, vs); gl.attachShader(prog, fs); gl.linkProgram(prog);
      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) { return null; }
      gl.useProgram(prog);

      var box = boxData();
      var vbo = gl.createBuffer(), ibo = gl.createBuffer(), ebo = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, vbo);
      gl.bufferData(gl.ARRAY_BUFFER, box.v, gl.STATIC_DRAW);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ibo);
      gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, box.i, gl.STATIC_DRAW);
      var edges = edgeData();
      gl.bindBuffer(gl.ARRAY_BUFFER, ebo);
      gl.bufferData(gl.ARRAY_BUFFER, edges, gl.STATIC_DRAW);

      var aP = gl.getAttribLocation(prog, "aP"), aN = gl.getAttribLocation(prog, "aN");
      var uMVP = gl.getUniformLocation(prog, "uMVP");
      var uScale = gl.getUniformLocation(prog, "uScale");
      var uTint = gl.getUniformLocation(prog, "uTint");
      var uL = gl.getUniformLocation(prog, "uL");
      var uAlpha = gl.getUniformLocation(prog, "uAlpha");
      var uFlat = gl.getUniformLocation(prog, "uFlat");
      var uRim = gl.getUniformLocation(prog, "uRim");
      gl.enableVertexAttribArray(aP);
      gl.enableVertexAttribArray(aN);
      gl.enable(gl.DEPTH_TEST);
      gl.enable(gl.BLEND);
      gl.enable(gl.CULL_FACE);
      gl.cullFace(gl.BACK);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

      var C = {
        face: token("--fill", "#8A7F72"),
        top: token("--face-top", "#6E655B"),
        line: token("--line-hi", "#3D362E"),
        warn: token("--warn", "#E8C547"),
        danger: token("--danger", "#FF4D3D"),
        accent: token("--accent", "#FF7A18")
      };

      var api = {}, drives = [], W = 1, H = 1, dpr = 1;
      var yaw = -0.52, pitch = 0.44, spin = 0, vel = 0, t = 0;
      var lost = false;

      canvas.addEventListener("webglcontextlost", function (e) {
        e.preventDefault(); lost = true;
        if (api.onlost) { api.onlost(); }
      });

      function resize() {
        dpr = Math.min(window.devicePixelRatio || 1, 2);
        var r = canvas.getBoundingClientRect();
        W = Math.max(1, Math.round(r.width * dpr));
        H = Math.max(1, Math.round(r.height * dpr));
        if (canvas.width !== W || canvas.height !== H) {
          canvas.width = W; canvas.height = H;
        }
      }
      resize();
      if (window.ResizeObserver) {
        new ResizeObserver(function () { resize(); api.kick(); }).observe(canvas);
      } else {
        window.addEventListener("resize", function () { resize(); api.kick(); });
      }

      /* ---- drag to turn, with inertia and a slow return to rest ------------- */
      var dragging = false, lastX = 0, moved = false;
      canvas.addEventListener("pointerdown", function (e) {
        dragging = true; moved = false; lastX = e.clientX;
        canvas.setPointerCapture(e.pointerId);
        api.kick();
      });
      canvas.addEventListener("pointermove", function (e) {
        if (!dragging) { return; }
        var dx = e.clientX - lastX;
        lastX = e.clientX;
        if (Math.abs(dx) > 0) { moved = true; }
        spin += dx * 0.012;
        vel = dx * 0.012;
        if (api.onturn) { api.onturn(); }
        api.kick();
      });
      function up() { dragging = false; }
      canvas.addEventListener("pointerup", up);
      canvas.addEventListener("pointercancel", up);

      function draw() {
        if (lost) { return; }
        gl.viewport(0, 0, W, H);
        gl.clearColor(0, 0, 0, 0);
        gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

        /* The light drifts. This is the ambient life at idle: nothing moves except
           where the light falls, which is exactly what a room at rest does. */
        var lx = Math.cos(t * 0.11) * 0.75, lz = 0.55 + Math.sin(t * 0.09) * 0.35;
        gl.uniform3f(uL, lx, 0.95, lz);

        var asp = W / H;
        var view = look([Math.sin(yaw + spin) * 3.45, 1.95 + pitch,
                         Math.cos(yaw + spin) * 3.45], [0, 0.52, 0], [0, 1, 0]);
        var vp = mul(persp(0.58, asp, 0.1, 40), view);

        var i, d;
        gl.bindBuffer(gl.ARRAY_BUFFER, vbo);
        gl.vertexAttribPointer(aP, 3, gl.FLOAT, false, 24, 0);
        gl.vertexAttribPointer(aN, 3, gl.FLOAT, false, 24, 12);
        gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ibo);
        gl.uniform1f(uFlat, 0);

        /* pass 1: the fills -- what is actually on the disk. Opaque, lit, and the
           only thing here with a colour: neutral material below 85% used, warn
           above it, danger above 95%. */
        gl.depthMask(true);
        for (i = 0; i < drives.length; i++) {
          d = drives[i];
          var fh = Math.max(0.014, d.h * d.fill.v);
          gl.uniform3f(uScale, d.w, fh, d.dp);
          gl.uniformMatrix4fv(uMVP, false, mul(vp, trs(d.x, 0, 0, d.w, fh, d.dp)));
          gl.uniform3f(uTint, d.tint[0], d.tint[1], d.tint[2]);
          gl.uniform1f(uAlpha, 1);
          gl.uniform1f(uRim, 0.20);
          gl.drawElements(gl.TRIANGLES, box.i.length, gl.UNSIGNED_SHORT, 0);
        }
        /* pass 2: the shells -- the whole capacity, as glass over the fill. Depth
           writes off so the two solids never fight each other. */
        gl.depthMask(false);
        for (i = 0; i < drives.length; i++) {
          d = drives[i];
          gl.uniform3f(uScale, d.w * 1.035, d.h, d.dp * 1.05);
          gl.uniformMatrix4fv(uMVP, false,
            mul(vp, trs(d.x, 0, 0, d.w * 1.035, d.h, d.dp * 1.05)));
          gl.uniform3f(uTint, 0.10, 0.092, 0.078);
          gl.uniform1f(uAlpha, 0.34);
          gl.uniform1f(uRim, 0.85);
          gl.drawElements(gl.TRIANGLES, box.i.length, gl.UNSIGNED_SHORT, 0);
        }
        /* pass 3: the capacity cage. The risky drive's is drawn in warn -- machine
           state, not decoration. */
        gl.depthMask(true);
        gl.disable(gl.CULL_FACE);
        gl.bindBuffer(gl.ARRAY_BUFFER, ebo);
        gl.vertexAttribPointer(aP, 3, gl.FLOAT, false, 24, 0);
        gl.vertexAttribPointer(aN, 3, gl.FLOAT, false, 24, 12);
        gl.uniform1f(uFlat, 1);
        for (i = 0; i < drives.length; i++) {
          d = drives[i];
          gl.uniform3f(uScale, 1, 1, 1);
          gl.uniformMatrix4fv(uMVP, false,
            mul(vp, trs(d.x, 0, 0, d.w * 1.035, d.h, d.dp * 1.05)));
          var c = d.risky ? C.warn : C.line;
          gl.uniform3f(uTint, c[0], c[1], c[2]);
          gl.uniform1f(uAlpha, d.risky ? 0.7 : 0.95);
          gl.drawArrays(gl.LINES, 0, edges.length / 6);
        }
        gl.enable(gl.CULL_FACE);
      }

      /* One frame callback for the canvas. It returns false -- and so unregisters
         itself and lets the rAF loop die -- the moment nothing is moving and the
         page is not awake. An idle page costs nothing. */
      function tick(dt) {
        t += dt;
        var busy = false, i;
        for (i = 0; i < drives.length; i++) {
          drives[i].fill.step(dt);
          if (!drives[i].fill.done()) { busy = true; }
        }
        if (dragging) { busy = true; }
        else if (Math.abs(vel) > 0.0002) {
          spin += vel; vel *= 0.90; busy = true;
        } else {
          vel = 0;
          /* return to rest, slowly, so the pair is always readable again */
          if (Math.abs(spin) > 0.0008) { spin *= 0.985; busy = true; }
          else { spin = 0; }
        }
        var ambient = window.LUM && LUM.awake();
        draw();
        return busy || ambient;
      }

      /* Paint first, schedule second. A frame loop is an optimisation, not the
         thing that makes the picture: rAF does not run in a hidden document, and
         a canvas that waits for one shows the blank box the brief forbids. */
      api.kick = function () {
        if (lost) { return; }
        draw();
        LUM.loop(tick, true);
      };

      /* ---- the data ---------------------------------------------------------
         disks[] straight off /api/summary: name, risky, total, used, free. No
         invented fields. Heights are capacity against the largest drive present,
         so the 457 GB USB disk is visibly a smaller object than the 875 GB one. */
      api.update = function (disks) {
        var tallest = disks.reduce(function (a, x) { return Math.max(a, x.total || 0); }, 0) || 1;
        drives = disks.map(function (dk, i) {
          var frac = dk.total ? dk.used / dk.total : 0;
          var pct = Math.round(frac * 100);
          var tint = pct >= 95 ? C.danger : (pct >= 85 ? C.warn : C.face);
          var prev = drives[i];
          var f = prev ? prev.fill : LUM.num(0);
          f.rate = 2.2;
          /* Filling up is worth watching, but only if anyone is looking. Hidden
             or reduced-motion, the solid simply arrives at its real height. */
          if (document.hidden) { f.set(frac); } else { f.to(frac); }
          return {
            x: (i - (disks.length - 1) / 2) * 1.08,
            w: 0.60, dp: 0.42,
            h: 0.28 + 1.00 * ((dk.total || 1) / tallest),
            fill: f, tint: tint, risky: !!dk.risky, pct: pct
          };
        });
        api.kick();
      };
      api.gl = true;
      return api;
    }
  };
}());
