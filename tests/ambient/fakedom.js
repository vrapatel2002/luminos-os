'use strict';
// Minimal fake browser for content.js (helper for content.dom.test.js; not a test file).
// Unknown properties read on fake objects are recorded in h.missing so a failure can name
// the DOM API the fake lacks. Forbidden APIs (rAF, setInterval, MutationObserver, WebGL,
// getImageData) are recorded in h.forbidden and throw.
const vm = require('node:vm');

const IGNORE = new Set(['then', 'toJSON', 'asymmetricMatch', 'inspect', 'nodeName', '$$typeof']);
const camel = (s) => s.trim().replace(/^-webkit-/, 'webkit-').replace(/-([a-z])/g, (_, c) => c.toUpperCase());
const kebab = (s) => s.replace(/[A-Z]/g, (m) => '-' + m.toLowerCase());

function makeHarness() {
  const h = {
    missing: new Set(), forbidden: [], errors: [], warns: [], now: 1000, nextId: 0,
    timers: new Map(), maxPending: 0, delays: [], ctxCalls: [], ios: [], onScreen: true,
    store: {}, storageListeners: [], winListeners: [], drawThrows: false, inTimer: false,
  };
  const watch = (obj, label) => new Proxy(obj, {
    get(t, p, r) {
      if (typeof p === 'symbol' || p in t || IGNORE.has(p)) return Reflect.get(t, p, r);
      h.missing.add(`${label}.${p}`);
      return undefined;
    },
  });
  const forbid = (name) => function () { h.forbidden.push(name); throw new Error(`forbidden API used: ${name}`); };
  h.note = () => {
    const parts = [];
    if (h.missing.size) parts.push(`fake DOM lacked (read as undefined): ${[...h.missing].join(', ')}`);
    if (h.errors.length) parts.push(`uncaught errors in callbacks:\n    ${h.errors.join('\n    ')}`);
    if (h.forbidden.length) parts.push(`forbidden APIs: ${h.forbidden.join(', ')}`);
    return parts.length ? `\n  [harness] ${parts.join('\n  [harness] ')}` : '';
  };
  const guard = (fn, where) => { try { return fn(); } catch (e) { h.errors.push(`${where}: ${(e && e.stack) || e}`); return undefined; } };

  // ----- style / classList / dataset -----
  function makeStyle() {
    const props = Object.create(null);
    const api = {
      setProperty(n, v) { if (v === '' || v == null) delete props[camel(n)]; else props[camel(n)] = String(v).replace(/\s*!important\s*$/, ''); },
      getPropertyValue(n) { return props[camel(n)] || ''; },
      removeProperty(n) { const v = props[camel(n)] || ''; delete props[camel(n)]; return v; },
    };
    const setCss = (txt) => {
      for (const k of Object.keys(props)) delete props[k];
      for (const decl of String(txt).split(';')) {
        const i = decl.indexOf(':');
        if (i > 0) api.setProperty(decl.slice(0, i), decl.slice(i + 1).trim());
      }
    };
    return new Proxy(props, {
      get(t, p) {
        if (p === 'cssText') return Object.keys(t).map((k) => `${kebab(k)}: ${t[k]};`).join(' ');
        if (typeof p === 'symbol') return undefined;
        if (p in api) return api[p];
        return t[p] || '';
      },
      set(t, p, v) {
        if (p === 'cssText') setCss(v);
        else if (v === '' || v == null) delete t[p];
        else t[p] = String(v);
        return true;
      },
    });
  }
  function makeClassList() {
    const list = [];
    return {
      _list: list,
      add(...c) { for (const x of c) if (!list.includes(x)) list.push(x); },
      remove(...c) { for (const x of c) { const i = list.indexOf(x); if (i >= 0) list.splice(i, 1); } },
      contains(c) { return list.includes(c); },
      toggle(c, force) {
        const want = force === undefined ? !list.includes(c) : !!force;
        if (want) this.add(c); else this.remove(c);
        return want;
      },
      replace(a, b) { const i = list.indexOf(a); if (i < 0) return false; list[i] = b; return true; },
      get length() { return list.length; },
      get value() { return list.join(' '); },
      toString() { return list.join(' '); },
    };
  }
  const makeDataset = () => new Proxy({}, { set(t, p, v) { t[p] = String(v); return true; } });

  // ----- events -----
  function listen(arr, type, fn, opts) {
    if (!fn) return;
    const capture = opts === true || !!(opts && opts.capture);
    if (arr.some((l) => l.type === type && l.fn === fn && l.capture === capture)) return;
    arr.push({ type, fn, capture, once: !!(opts && opts.once) });
  }
  function unlisten(arr, type, fn, opts) {
    const capture = opts === true || !!(opts && opts.capture);
    const i = arr.findIndex((l) => l.type === type && l.fn === fn && l.capture === capture);
    if (i >= 0) arr.splice(i, 1);
  }
  function invoke(arr, ev, phaseCapture, cur) {
    for (const l of arr.slice()) {
      if (l.type !== ev.type || (phaseCapture !== null && l.capture !== phaseCapture)) continue;
      if (l.once) unlisten(arr, l.type, l.fn, l.capture);
      ev.currentTarget = cur;
      guard(() => (typeof l.fn === 'function' ? l.fn.call(cur, ev) : l.fn.handleEvent(ev)), `listener "${ev.type}"`);
    }
  }
  h.fire = (target, type, bubbles = false) => {
    const path = [];
    for (let n = target.parentNode; n; n = n.parentNode) path.unshift(n);
    if (target !== h.window) path.unshift(h.window);
    const ev = { type, target, bubbles, cancelable: false, defaultPrevented: false, isTrusted: true, timeStamp: h.now,
      preventDefault() {}, stopPropagation() {}, stopImmediatePropagation() {}, composedPath: () => [target, ...path.slice().reverse()] };
    const ls = (n) => (n === h.window ? h.winListeners : n._listeners);
    for (const n of path) invoke(ls(n), ev, true, n);
    invoke(ls(target), ev, null, target);
    if (bubbles) for (const n of path.slice().reverse()) invoke(ls(n), ev, false, n);
  };

  // ----- selectors (tag, #id, .class, descendant, >) -----
  function matchCompound(el, comp) {
    const m = /^(\*|[a-zA-Z][\w-]*)?((?:[#.][\w-]+)*)$/.exec(comp);
    if (!m) { h.missing.add(`selector support for "${comp}"`); return false; }
    if (m[1] && m[1] !== '*' && el.localName !== m[1].toLowerCase()) return false;
    for (const part of m[2].match(/[#.][\w-]+/g) || []) {
      if (part[0] === '#' && el.id !== part.slice(1)) return false;
      if (part[0] === '.' && !el.classList.contains(part.slice(1))) return false;
    }
    return true;
  }
  function matchComplex(el, toks) {
    if (!el || !el.localName || !matchCompound(el, toks[toks.length - 1])) return false;
    if (toks.length === 1) return true;
    const comb = toks[toks.length - 2];
    if (comb === '>') return matchComplex(el.parentNode, toks.slice(0, -2));
    for (let a = el.parentNode; a; a = a.parentNode) if (matchComplex(a, toks.slice(0, -1))) return true;
    return false;
  }
  const matches = (el, sel) => String(sel).split(',').some((s) => {
    const toks = s.trim().replace(/\s*>\s*/g, ' > ').split(/\s+/);
    return matchComplex(el, toks);
  });
  function descendants(root) {
    const out = [];
    const walk = (n) => { for (const c of n.children) { out.push(c); walk(c); } };
    walk(root);
    return out;
  }

  // ----- elements -----
  class Node {}
  class Element extends Node {
    constructor(tag) {
      super();
      this.localName = tag.toLowerCase(); this.tagName = tag.toUpperCase(); this.nodeType = 1;
      this.children = []; this.parentNode = null; this._attrs = {}; this._listeners = [];
      this.style = makeStyle(); this.classList = makeClassList(); this.dataset = makeDataset();
      this.textContent = ''; this.hidden = false; this.ownerDocument = null;
    }
    get nodeName() { return this.tagName; }
    get childNodes() { return this.children; }
    get firstChild() { return this.children[0] || null; }
    get firstElementChild() { return this.children[0] || null; }
    get parentElement() { return this.parentNode && this.parentNode.localName ? this.parentNode : null; }
    get id() { return this._attrs.id || ''; }
    set id(v) { this._attrs.id = String(v); }
    get className() { return this.classList.value; }
    set className(v) { this.classList._list.length = 0; this.classList.add(...String(v).split(/\s+/).filter(Boolean)); }
    get isConnected() { let n = this; while (n.parentNode) n = n.parentNode; return n === h.document; }
    getAttribute(n) { return n === 'style' ? this.style.cssText : n === 'class' ? this.className : n in this._attrs ? this._attrs[n] : null; }
    setAttribute(n, v) {
      if (n === 'style') this.style.cssText = v;
      else if (n === 'class') this.className = v;
      else if (n.startsWith('data-')) this.dataset[camel(n.slice(5))] = v;
      else this._attrs[n] = String(v);
    }
    removeAttribute(n) { if (n === 'style') this.style.cssText = ''; else if (n === 'class') this.className = ''; else delete this._attrs[n]; }
    hasAttribute(n) { return this.getAttribute(n) !== null; }
    appendChild(c) { if (c.parentNode) c.remove(); this.children.push(c); c.parentNode = this; return c; }
    append(...cs) { for (const c of cs) this.appendChild(c); }
    prepend(...cs) { for (const c of cs.reverse()) { if (c.parentNode) c.remove(); this.children.unshift(c); c.parentNode = this; } }
    insertBefore(c, ref) {
      if (c.parentNode) c.remove();
      const i = ref ? this.children.indexOf(ref) : -1;
      if (i < 0) this.children.push(c); else this.children.splice(i, 0, c);
      c.parentNode = this; return c;
    }
    removeChild(c) { const i = this.children.indexOf(c); if (i >= 0) this.children.splice(i, 1); c.parentNode = null; return c; }
    remove() { if (this.parentNode) this.parentNode.removeChild(this); }
    contains(n) { for (; n; n = n.parentNode) if (n === this) return true; return false; }
    matches(sel) { return matches(this, sel); }
    closest(sel) { for (let n = this; n && n.localName; n = n.parentNode) if (matches(n, sel)) return n; return null; }
    querySelector(sel) { return descendants(this).find((e) => matches(e, sel)) || null; }
    querySelectorAll(sel) { return descendants(this).filter((e) => matches(e, sel)); }
    getElementsByTagName(t) { return descendants(this).filter((e) => t === '*' || e.localName === t.toLowerCase()); }
    addEventListener(t, f, o) { listen(this._listeners, t, f, o); }
    removeEventListener(t, f, o) { unlisten(this._listeners, t, f, o); }
    dispatchEvent(ev) { h.fire(this, ev.type, !!ev.bubbles); return true; }
    getBoundingClientRect() { return rectObj(0, 0, 0, 0); }
    get offsetWidth() { return this.getBoundingClientRect().width; }
    get offsetHeight() { return this.getBoundingClientRect().height; }
    get clientWidth() { return this.getBoundingClientRect().width; }
    get clientHeight() { return this.getBoundingClientRect().height; }
  }
  class HTMLElement extends Element {}
  class HTMLCanvasElement extends HTMLElement {
    constructor() { super('canvas'); this._w = 300; this._h = 150; this._ctx = null; }
    get width() { return this._w; }
    set width(v) { this._w = Math.max(0, Math.floor(Number(v)) || 0); }
    get height() { return this._h; }
    set height(v) { this._h = Math.max(0, Math.floor(Number(v)) || 0); }
    getContext(type, opts) {
      if (type !== '2d') { h.forbidden.push(`getContext('${type}')`); return null; }
      if (!this._ctx) this._ctx = makeCtx(this, opts);
      return this._ctx;
    }
  }
  class HTMLMediaElement extends HTMLElement {}
  class HTMLVideoElement extends HTMLMediaElement {
    constructor() {
      super('video');
      Object.assign(this, { videoWidth: 1920, videoHeight: 1080, paused: true, ended: false, readyState: 4,
        currentTime: 0, duration: 600, muted: true, src: 'blob:https://www.youtube.com/x', currentSrc: 'blob:https://www.youtube.com/x',
        loop: false, playbackRate: 1, _rect: rectObj(0, 0, 0, 0) });
    }
    getBoundingClientRect() { return { ...this._rect }; }
    play() { this.paused = false; h.fire(this, 'play'); h.fire(this, 'playing'); return Promise.resolve(); }
    pause() { this.paused = true; h.fire(this, 'pause'); }
  }
  const CLASSES = { canvas: HTMLCanvasElement, video: HTMLVideoElement };
  function create(tag) {
    const C = CLASSES[String(tag).toLowerCase()];
    const el = C ? new C() : new HTMLElement(String(tag));
    return watch(el, `<${String(tag).toLowerCase()}>`);
  }
  function rectObj(left, top, width, height) {
    return { left, top, width, height, x: left, y: top, right: left + width, bottom: top + height };
  }
  h.rectObj = rectObj;

  function makeCtx(canvas, opts) {
    const state = { canvas, globalAlpha: 1, globalCompositeOperation: 'source-over', imageSmoothingEnabled: true,
      imageSmoothingQuality: 'low', filter: 'none', fillStyle: '#000000', strokeStyle: '#000000', _opts: opts };
    state.drawImage = (...args) => {
      h.ctxCalls.push({ name: 'drawImage', canvas, w: canvas.width, h: canvas.height, src: args[0], inTimer: h.inTimer });
      if (h.drawThrows) { const e = new Error('SecurityError: tainted'); e.name = 'SecurityError'; throw e; }
    };
    state.getImageData = forbid('getImageData');
    // factory methods must return real-shaped objects (a 2D context never returns undefined here)
    const gradient = () => ({ addColorStop() {} });
    const rec = (name, ret) => (...args) => { h.ctxCalls.push({ name, canvas, w: canvas.width, h: canvas.height, inTimer: h.inTimer, args }); return ret(); };
    state.createLinearGradient = rec('createLinearGradient', gradient);
    state.createRadialGradient = rec('createRadialGradient', gradient);
    state.createConicGradient = rec('createConicGradient', gradient);
    state.createPattern = rec('createPattern', () => ({ setTransform() {} }));
    state.measureText = rec('measureText', () => ({ width: 0, actualBoundingBoxAscent: 0, actualBoundingBoxDescent: 0 }));
    state.getTransform = rec('getTransform', () => ({ a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 }));
    state.isPointInPath = rec('isPointInPath', () => false);
    state.getLineDash = rec('getLineDash', () => []);
    state.getContextAttributes = () => opts || {};
    return new Proxy(state, {
      get(t, p) {
        if (typeof p === 'symbol' || p in t) return t[p];
        return (...args) => { h.ctxCalls.push({ name: p, canvas, w: canvas.width, h: canvas.height, inTimer: h.inTimer, args }); };
      },
    });
  }

  // ----- document -----
  class Document {
    constructor() { this._listeners = []; this.nodeType = 9; this.hidden = false; this.visibilityState = 'visible';
      this.fullscreenElement = null; this.readyState = 'complete'; this.parentNode = null; }
    get children() { return [this.documentElement]; }
    createElement(t) { return create(t); }
    getElementById(id) { return [this.documentElement, ...descendants(this.documentElement)].find((e) => e.id === id) || null; }
    querySelector(s) { return [this.documentElement, ...descendants(this.documentElement)].find((e) => matches(e, s)) || null; }
    querySelectorAll(s) { return [this.documentElement, ...descendants(this.documentElement)].filter((e) => matches(e, s)); }
    getElementsByTagName(t) { return this.querySelectorAll(t); }
    contains(n) { for (; n; n = n.parentNode) if (n === this) return true; return false; }
    addEventListener(t, f, o) { listen(this._listeners, t, f, o); }
    removeEventListener(t, f, o) { unlisten(this._listeners, t, f, o); }
    dispatchEvent(ev) { h.fire(this, ev.type, !!ev.bubbles); return true; }
  }
  const doc = watch(new Document(), 'document');
  h.document = doc;
  const html = create('html'); const head = create('head'); const body = create('body');
  html.parentNode = doc; doc.documentElement = html; doc.head = head; doc.body = body;
  html.appendChild(head); html.appendChild(body);

  // YouTube-ish watch page
  const build = (tag, attrs, parent) => {
    const el = create(tag);
    if (attrs.id) el.id = attrs.id;
    if (attrs.cls) el.className = attrs.cls;
    parent.appendChild(el); return el;
  };
  const app = build('ytd-app', {}, body);
  const flexy = build('ytd-watch-flexy', {}, build('div', { id: 'content' }, app));
  const player = build('div', { id: 'movie_player', cls: 'html5-video-player' }, build('div', { id: 'player' }, flexy));
  h.player = player;
  h.container = build('div', { cls: 'html5-video-container' }, player);
  h.video = build('video', { cls: 'video-stream html5-main-video' }, h.container);
  const preview = build('ytd-video-preview', {}, app);
  h.previewVideo = build('video', { cls: 'video-stream' }, preview);
  h.playerParent = player.parentNode;
  h.miniplayer = build('ytd-miniplayer', {}, app);
  h.html = html; h.body = body;
  h.setVideoRect = (v, l, t, w, hh) => { v._rect = rectObj(l, t, w, hh); };

  // ----- IntersectionObserver -----
  class IntersectionObserver {
    constructor(cb, opts) { this._cb = cb; this._opts = opts || {}; this._targets = new Map(); h.ios.push(this);
      this.root = this._opts.root || null; this.rootMargin = this._opts.rootMargin || '0px'; this.thresholds = [].concat(this._opts.threshold || 0); }
    observe(t) { if (!this._targets.has(t)) this._targets.set(t, undefined); }
    unobserve(t) { this._targets.delete(t); }
    disconnect() { this._targets.clear(); }
    takeRecords() { return []; }
  }
  // deliver one specific entry to every observer (even for a target no longer observed), as a
  // queued-but-stale IO notification would arrive in a real browser
  h.deliverIO = (target, isIntersecting) => {
    for (const io of h.ios.slice()) {
      const r = target.getBoundingClientRect();
      const entry = { target, isIntersecting, intersectionRatio: isIntersecting ? 1 : 0, boundingClientRect: r,
        intersectionRect: isIntersecting ? r : rectObj(0, 0, 0, 0), rootBounds: null, time: h.now };
      guard(() => io._cb([entry], io), 'IntersectionObserver callback');
    }
  };
  h.flushIO = () => {
    for (const io of h.ios) {
      const entries = [];
      for (const [t, last] of io._targets) {
        if (last === h.onScreen) continue;
        io._targets.set(t, h.onScreen);
        const r = t.getBoundingClientRect();
        entries.push({ target: t, isIntersecting: h.onScreen, intersectionRatio: h.onScreen ? 1 : 0, boundingClientRect: r,
          intersectionRect: h.onScreen ? r : rectObj(0, 0, 0, 0), rootBounds: null, time: h.now });
      }
      if (entries.length) guard(() => io._cb(entries, io), 'IntersectionObserver callback');
    }
  };

  // ----- timers -----
  let seq = 0;
  h.pending = () => h.timers.size;
  h.runNextTimer = () => {
    let best = null;
    for (const [id, t] of h.timers) if (!best || t.at < best[1].at || (t.at === best[1].at && t.seq < best[1].seq)) best = [id, t];
    if (!best) return false;
    h.timers.delete(best[0]);
    h.now = Math.max(h.now, best[1].at);
    h.inTimer = true;
    guard(() => best[1].fn(...best[1].args), 'setTimeout callback');
    h.inTimer = false;
    return true;
  };
  h.advance = (ms) => { h.now += ms; };

  // ----- chrome.storage -----
  const KEY = 'luminosAmbient';
  const select = (keys) => {
    if (keys == null) return { ...h.store };
    if (typeof keys === 'string') return keys in h.store ? { [keys]: h.store[keys] } : {};
    if (Array.isArray(keys)) return Object.fromEntries(keys.filter((k) => k in h.store).map((k) => [k, h.store[k]]));
    return Object.fromEntries(Object.keys(keys).map((k) => [k, k in h.store ? h.store[k] : keys[k]]));
  };
  const local = {
    get(keys, cb) {
      dead();
      const res = JSON.parse(JSON.stringify(select(keys)));
      if (typeof keys === 'function') { const c = keys; Promise.resolve().then(() => guard(() => c({ ...h.store }), 'storage.get cb')); return undefined; }
      if (cb) { Promise.resolve().then(() => guard(() => cb(res), 'storage.get cb')); return undefined; }
      return Promise.resolve(res);
    },
    set(obj, cb) {
      dead();
      for (const [k, v] of Object.entries(obj)) h.setStored(k, v);
      if (cb) Promise.resolve().then(() => guard(cb, 'storage.set cb'));
      return Promise.resolve();
    },
    onChanged: { addListener(fn) { h.storageListeners.push({ fn, local: true }); }, removeListener() {}, hasListener: () => true },
  };
  h.setStored = (k, v) => {
    const oldValue = h.store[k];
    h.store[k] = v;
    const changes = { [k]: { oldValue, newValue: v } };
    for (const l of h.storageListeners.slice()) {
      guard(() => (l.local ? l.fn(JSON.parse(JSON.stringify(changes))) : l.fn(JSON.parse(JSON.stringify(changes)), 'local')), 'storage.onChanged listener');
    }
  };
  h.setSettings = (v) => h.setStored(KEY, v);
  const runtime = { id: 'test', lastError: undefined };
  const dead = () => { if (h.orphaned) throw new Error('Extension context invalidated.'); };
  // Extension disabled/reloaded: runtime.id disappears and chrome.* calls throw (as in Chrome).
  h.orphan = () => { h.orphaned = true; runtime.id = undefined; };
  const chrome = watch({
    storage: watch({
      local: watch(local, 'chrome.storage.local'),
      onChanged: watch({ addListener(fn) { h.storageListeners.push({ fn, local: false }); }, removeListener(fn) {
        h.storageListeners = h.storageListeners.filter((l) => l.fn !== fn); }, hasListener: () => true }, 'chrome.storage.onChanged'),
    }, 'chrome.storage'),
    runtime: watch(runtime, 'chrome.runtime'),
  }, 'chrome');

  // ----- window / global -----
  const g = {
    document: doc, chrome, IntersectionObserver, Node, Element, HTMLElement, HTMLCanvasElement, HTMLMediaElement, HTMLVideoElement, Document,
    console: { log() {}, info() {}, debug() {}, warn: (...a) => h.warns.push(a.map(String).join(' ')), error: (...a) => h.warns.push('[error] ' + a.map(String).join(' ')) },
    setTimeout(fn, delay, ...args) {
      if (typeof fn !== 'function') { h.forbidden.push('setTimeout(string)'); throw new Error('setTimeout(string) not allowed'); }
      const id = ++h.nextId;
      const d = Math.max(0, Number(delay) || 0);
      h.timers.set(id, { fn, at: h.now + d, args, seq: ++seq });
      h.delays.push({ delay: d, fromTimer: h.inTimer });
      h.maxPending = Math.max(h.maxPending, h.timers.size);
      return id;
    },
    clearTimeout(id) { h.timers.delete(id); },
    setInterval: forbid('setInterval'), requestAnimationFrame: forbid('requestAnimationFrame'),
    cancelAnimationFrame: forbid('cancelAnimationFrame'), MutationObserver: forbid('MutationObserver'),
    WebGLRenderingContext: forbid('WebGLRenderingContext'), WebGL2RenderingContext: forbid('WebGL2RenderingContext'),
    performance: { now: () => h.now },
    scrollX: 0, scrollY: 0, innerWidth: 1280, innerHeight: 800, devicePixelRatio: 1,
    location: { href: 'https://www.youtube.com/watch?v=test', pathname: '/watch', hostname: 'www.youtube.com', origin: 'https://www.youtube.com', search: '?v=test' },
    addEventListener(t, f, o) { listen(h.winListeners, t, f, o); },
    removeEventListener(t, f, o) { unlisten(h.winListeners, t, f, o); },
    getComputedStyle: (el) => el.style,
    queueMicrotask: (fn) => Promise.resolve().then(() => guard(fn, 'microtask')),
  };
  Object.defineProperty(g, 'pageXOffset', { get: () => g.scrollX, enumerable: true });
  Object.defineProperty(g, 'pageYOffset', { get: () => g.scrollY, enumerable: true });
  g.window = g; g.self = g;
  h.context = vm.createContext(g);
  h.window = h.context;
  h.setScroll = (x, y) => { h.context.scrollX = x; h.context.scrollY = y; };
  h.run = (code, filename) => vm.runInContext(code, h.context, { filename });
  return h;
}

module.exports = { makeHarness };
