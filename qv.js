// ============================================================
// QV (QikVote) v0.1.0 — qv.js embed loader
// Drop-in: <script src="https://qv.f-keys.com/qv.js" data-ballot="ID" async></script>
// Injects an iframe with the compact live ballot (e.html).
// F-Keys | www.f-keys.com
// ============================================================
//
// WORKFLOW STACK:
// 1. Find own <script> tag (document.currentScript)
// 2. Read data-ballot id, derive base URL from own src
// 3. Insert a sandbox-safe iframe pointing at e.html?id=...
//
// ASSET MANIFEST: none (loads e.html from the same origin as this file)
// BOOT ORDER: executes inline at parse time
// ============================================================

(function () {
  try {
    var tag = document.currentScript;
    if (!tag) { console.error('qv.js: no currentScript'); return; }
    var id = (tag.getAttribute('data-ballot') || '').toLowerCase();
    if (!/^[a-z0-9]{4,16}$/.test(id)) { console.error('qv.js: bad data-ballot id'); return; }
    var src = tag.src || '';
    var base = src.slice(0, src.lastIndexOf('/') + 1);
    var frame = document.createElement('iframe');
    frame.src = base + 'e.html?id=' + encodeURIComponent(id);
    frame.title = 'QV live ballot';
    frame.loading = 'lazy';
    frame.style.width = '100%';
    frame.style.maxWidth = '480px';
    frame.style.height = '190px';
    frame.style.border = '0';
    frame.style.borderRadius = '12px';
    frame.style.background = 'transparent';
    frame.style.colorScheme = 'dark';
    tag.parentNode.insertBefore(frame, tag.nextSibling);
  } catch (err) {
    console.error('qv.js:', err);
  }
})();
