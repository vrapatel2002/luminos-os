'use strict';
// Tiny JS lexer + function scanner for the ambient tests (not a test file itself).
// Honest heuristics, not a parser: blanks strings, template text, regex literals and
// comments so braces inside them are never counted. Node built-ins only.

const REGEX_AFTER_WORD = new Set(['return', 'typeof', 'instanceof', 'in', 'of', 'new', 'delete',
  'void', 'throw', 'case', 'do', 'else', 'yield', 'await']);
const BLOCK_KEYWORDS = new Set(['if', 'for', 'while', 'switch', 'catch', 'with']);
const BLOCK_WORDS = new Set(['else', 'try', 'finally', 'do']);

/**
 * lex(src) -> { code, noComments, strings: [{text, line}] }
 *  code:       same length as src; comments AND literal contents blanked (newlines kept)
 *  noComments: same length as src; only comments blanked (strings kept)
 */
function lex(src) {
  const code = src.split('');
  const nc = src.split('');
  const strings = [];
  const n = src.length;
  const tmplStack = []; // 'code' for a normal brace, 'tmpl' for a ${ ... } hole
  let prev = '';
  let i = 0;
  const lineAt = (off) => { let l = 1; for (let k = 0; k < off; k++) if (src[k] === '\n') l++; return l; };
  const blank = (arr, a, b) => { for (let k = a; k < b; k++) if (arr[k] !== '\n') arr[k] = ' '; };
  const regexAllowed = () => {
    if (prev === '') return true;
    if (prev === 'lit') return false;
    if (prev.startsWith('w:')) return REGEX_AFTER_WORD.has(prev.slice(2));
    return '(,=:[!&|?{};+-*%<>~^'.includes(prev);
  };
  // reads template text starting at j (just after ` or a closing } of a hole)
  const readTemplate = (j) => {
    const start = j;
    while (j < n) {
      if (src[j] === '\\') { j += 2; continue; }
      if (src[j] === '`') {
        strings.push({ text: src.slice(start, j), line: lineAt(start) });
        blank(code, start, j); prev = 'lit'; return j + 1;
      }
      if (src[j] === '$' && src[j + 1] === '{') {
        strings.push({ text: src.slice(start, j), line: lineAt(start) });
        blank(code, start, j + 2); tmplStack.push('tmpl'); prev = '('; return j + 2;
      }
      j++;
    }
    blank(code, start, n); return n;
  };
  while (i < n) {
    const c = src[i];
    const d = src[i + 1];
    if (c === '/' && d === '/') {
      const j = src.indexOf('\n', i); const e = j < 0 ? n : j;
      blank(code, i, e); blank(nc, i, e); i = e; continue;
    }
    if (c === '/' && d === '*') {
      const j = src.indexOf('*/', i + 2); const e = j < 0 ? n : j + 2;
      blank(code, i, e); blank(nc, i, e); i = e; continue;
    }
    if (c === '"' || c === "'") {
      let j = i + 1;
      while (j < n && src[j] !== c && src[j] !== '\n') { if (src[j] === '\\') j++; j++; }
      strings.push({ text: src.slice(i + 1, j), line: lineAt(i) });
      blank(code, i + 1, j); i = j + 1; prev = 'lit'; continue;
    }
    if (c === '`') { i = readTemplate(i + 1); continue; }
    if (c === '}' && tmplStack.length && tmplStack[tmplStack.length - 1] === 'tmpl') {
      tmplStack.pop(); code[i] = ' '; i = readTemplate(i + 1); continue;
    }
    if (c === '/' && regexAllowed()) {
      let j = i + 1; let inClass = false;
      while (j < n && src[j] !== '\n') {
        if (src[j] === '\\') { j += 2; continue; }
        if (src[j] === '[') inClass = true;
        else if (src[j] === ']') inClass = false;
        else if (src[j] === '/' && !inClass) break;
        j++;
      }
      blank(code, i + 1, j); j++;
      while (j < n && /[a-z]/i.test(src[j])) j++;
      i = j; prev = 'lit'; continue;
    }
    if (/[A-Za-z_$]/.test(c)) {
      let j = i; while (j < n && /[\w$]/.test(src[j])) j++;
      prev = 'w:' + src.slice(i, j); i = j; continue;
    }
    if (/[0-9]/.test(c)) {
      let j = i; while (j < n && /[\w.]/.test(src[j])) j++;
      prev = 'lit'; i = j; continue;
    }
    if (c === '{') tmplStack.push('code');
    else if (c === '}') tmplStack.pop();
    if (!/\s/.test(c)) prev = c;
    i++;
  }
  return { code: code.join(''), noComments: nc.join(''), strings };
}

function matchParenBack(code, close) {
  let depth = 0;
  for (let k = close; k >= 0; k--) {
    if (code[k] === ')') depth++;
    else if (code[k] === '(') { depth--; if (depth === 0) return k; }
  }
  return -1;
}

function nameFromAssignment(head) {
  const h = head.replace(/\basync\s*$/, '').trimEnd();
  const m = /([\w$.]+)\s*(?:=|:)\s*$/.exec(h);
  return m ? m[1] : null;
}

function arrowName(before) {
  let head = before.slice(0, -2).trimEnd();
  if (head.endsWith(')')) {
    const p = matchParenBack(head, head.length - 1);
    head = p < 0 ? '' : head.slice(0, p);
  } else {
    head = head.replace(/[\w$]+$/, '');
  }
  return nameFromAssignment(head.trimEnd()) || '<arrow>';
}

// returns { kind: 'func'|'block'|'obj', name }
function classify(code, i) {
  const before = code.slice(0, i).trimEnd();
  if (before.endsWith('=>')) return { kind: 'func', name: arrowName(before) };
  if (before.endsWith(')')) {
    const p = matchParenBack(before, before.length - 1);
    const head = p < 0 ? '' : before.slice(0, p).trimEnd();
    const fm = /\bfunction\b\s*\*?\s*([\w$]*)$/.exec(head);
    if (fm) {
      const assigned = nameFromAssignment(head.slice(0, fm.index).trimEnd());
      return { kind: 'func', name: fm[1] || assigned || '<function>' };
    }
    const wm = /([\w$]+)$/.exec(head);
    if (wm && !BLOCK_KEYWORDS.has(wm[1])) return { kind: 'func', name: wm[1] };
    return { kind: 'block', name: null };
  }
  const wm = /([\w$]+)$/.exec(before);
  if (wm) return { kind: BLOCK_WORDS.has(wm[1]) ? 'block' : 'obj', name: null };
  if (before === '' || /[{};]$/.test(before)) return { kind: 'block', name: null };
  return { kind: 'obj', name: null };
}

/**
 * scanFunctions(src) -> [{ name, startLine, endLine, lines, maxDepth, iife }]
 * maxDepth = deepest block-statement nesting inside the function body, counted from the body
 * (body itself = 0). Nested functions reset the count (ESLint max-depth semantics).
 * Object-literal / class-body braces are matched but not counted as nesting.
 */
function scanFunctions(src) {
  const { code } = lex(src);
  const lineStarts = [0];
  for (let k = 0; k < code.length; k++) if (code[k] === '\n') lineStarts.push(k + 1);
  const lineOf = (off) => {
    let lo = 0; let hi = lineStarts.length - 1;
    while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (lineStarts[mid] <= off) lo = mid; else hi = mid - 1; }
    return lo + 1;
  };
  const stack = [];
  const funcs = [];
  for (let i = 0; i < code.length; i++) {
    if (code[i] === '{') {
      const { kind, name } = classify(code, i);
      const top = stack[stack.length - 1];
      let fn = null;
      for (let k = stack.length - 1; k >= 0; k--) if (stack[k].kind === 'func') { fn = stack[k]; break; }
      const entry = { kind, name, depth: 0, startLine: lineOf(i) };
      if (kind === 'func') { entry.maxDepth = 0; funcs.push(entry); } else {
        const base = top ? top.depth : 0;
        entry.depth = kind === 'block' ? base + 1 : base;
        if (top && top.kind === 'func' && kind === 'block') entry.depth = 1;
        if (fn && entry.depth > fn.maxDepth) fn.maxDepth = entry.depth;
      }
      stack.push(entry);
    } else if (code[i] === '}') {
      const e = stack.pop();
      if (e && e.kind === 'func') {
        e.endLine = lineOf(i); e.lines = e.endLine - e.startLine + 1;
        // IIFE: `(function () {...})()`, `(() => {...})()` or `(function () {...}())`
        const rest = code.slice(i + 1, i + 40);
        e.iife = /^\s*\)\s*\(/.test(rest) || /^\s*\([^)]*\)\s*\)/.test(rest);
      }
    }
  }
  return funcs.map((f) => ({ name: f.name, startLine: f.startLine, endLine: f.endLine,
    lines: f.lines, maxDepth: f.maxDepth, iife: !!f.iife }));
}

function countLines(text) {
  if (text === '') return 0;
  const parts = text.split('\n');
  return text.endsWith('\n') ? parts.length - 1 : parts.length;
}

module.exports = { lex, scanFunctions, countLines };
