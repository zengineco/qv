// ============================================================
// QV (QikVote) v0.1.0 — service worker
// The soul of the product: vote from the notification, nothing opens.
// F-Keys | www.f-keys.com
// ============================================================
//
// WORKFLOW STACK:
// 1. push event -> parse {id,q,la,lb,ch} -> showNotification with two
//    action buttons (the ballot's own labels)
// 2. notificationclick with action -> read voter token from IndexedDB
//    -> POST qv-vote -> replace notification with "Counted" tally
// 3. notificationclick without action (body tap) -> open the ballot page
//
// ASSET MANIFEST:
// - Edge function: qv-vote
// - IndexedDB 'qv' / store 'kv' / key 'token' (written by index.html)
//
// BOOT ORDER: install -> activate (claim) -> event-driven
// ============================================================

var FN = 'https://ihclxurachkewtgnrldc.supabase.co/functions/v1';

self.addEventListener('install', function (e) {
  self.skipWaiting();
});

self.addEventListener('activate', function (e) {
  e.waitUntil(self.clients.claim());
});

// tiny IndexedDB kv (SW has no localStorage)
function idbOpen() {
  return new Promise(function (resolve, reject) {
    var rq = indexedDB.open('qv', 1);
    rq.onupgradeneeded = function () { rq.result.createObjectStore('kv'); };
    rq.onsuccess = function () { resolve(rq.result); };
    rq.onerror = function () { reject(rq.error); };
  });
}
function idbGet(k) {
  return idbOpen().then(function (db) {
    return new Promise(function (resolve, reject) {
      var rq = db.transaction('kv', 'readonly').objectStore('kv').get(k);
      rq.onsuccess = function () { resolve(rq.result); };
      rq.onerror = function () { reject(rq.error); };
    });
  });
}
function idbPut(k, v) {
  return idbOpen().then(function (db) {
    return new Promise(function (resolve, reject) {
      var tx = db.transaction('kv', 'readwrite');
      tx.objectStore('kv').put(v, k);
      tx.oncomplete = function () { resolve(true); };
      tx.onerror = function () { reject(tx.error); };
    });
  });
}

// READS: IndexedDB token / WRITES: new token if missing
function getToken() {
  return idbGet('token').then(function (t) {
    if (t) return t;
    var buf = new Uint8Array(16);
    crypto.getRandomValues(buf);
    var s = '';
    for (var i = 0; i < buf.length; i++) s += buf[i].toString(16).padStart(2, '0');
    return idbPut('token', s).then(function () { return s; });
  });
}

self.addEventListener('push', function (event) {
  var data = null;
  try { data = event.data ? event.data.json() : null; } catch (err) { console.error('push parse:', err); }
  if (!data || !data.id || !data.q) return;
  var actions = [];
  // browsers cap notification actions at 2 — exactly our two options
  actions.push({ action: 'A', title: String(data.la || 'YES') });
  actions.push({ action: 'B', title: String(data.lb || 'NO') });
  event.waitUntil(
    self.registration.showNotification('QV LIVE — ' + data.q, {
      body: '#' + (data.ch || 'general') + ' · vote from the buttons, or tap to open',
      tag: 'qv-' + data.id,
      renotify: false,
      icon: 'icon.svg',
      data: { id: data.id, la: data.la, lb: data.lb },
      actions: actions
    })
  );
});

// READS: notification data + IDB token / WRITES: vote via qv-vote, replacement notification
function voteFromNotification(data, choice) {
  var labels = { A: data.la || 'YES', B: data.lb || 'NO' };
  return getToken().then(function (t) {
    return fetch(FN + '/qv-vote', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ id: data.id, choice: choice, t: t })
    });
  }).then(function (r) { return r.json(); }).then(function (out) {
    if (out && out.ok) {
      var tot = out.a + out.b;
      var pa = tot > 0 ? Math.round(out.a * 100 / tot) : 50;
      return self.registration.showNotification('Counted ✓ ' + labels[choice], {
        body: labels.A + ' ' + pa + '% · ' + labels.B + ' ' + (100 - pa) + '% · ' + (tot + out.p) + ' votes',
        tag: 'qv-' + data.id,
        renotify: false,
        icon: 'icon.svg',
        silent: true,
        data: { id: data.id, la: data.la, lb: data.lb }
      });
    }
    var why = out && out.error === 'closed' ? 'Ballot closed before your vote landed.' : 'Vote failed — tap to open the ballot.';
    return self.registration.showNotification('QV — not counted', {
      body: why,
      tag: 'qv-' + data.id,
      icon: 'icon.svg',
      data: { id: data.id, la: data.la, lb: data.lb }
    });
  }).catch(function (err) {
    console.error('voteFromNotification:', err);
    return self.registration.showNotification('QV — not counted', {
      body: 'Network error — tap to open the ballot and vote there.',
      tag: 'qv-' + data.id,
      icon: 'icon.svg',
      data: { id: data.id, la: data.la, lb: data.lb }
    });
  });
}

self.addEventListener('notificationclick', function (event) {
  var data = event.notification.data || {};
  if (event.action === 'A' || event.action === 'B') {
    // the one-tap vote: no window opens, the fetch happens right here
    event.waitUntil(voteFromNotification(data, event.action));
    return;
  }
  event.notification.close();
  if (data.id) {
    event.waitUntil(self.clients.openWindow(self.registration.scope + 'b.html?id=' + encodeURIComponent(data.id)));
  }
});
