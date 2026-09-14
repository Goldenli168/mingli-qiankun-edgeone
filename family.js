// ============================================================
// P82: 家庭分析模块(ziwei.html 用)
// 父母画像/父亲事业财富/父母健康/手足情况 四段(LLM)
// 取象规则经盘3/盘4人工验证后沉淀于服务端 /api/family
// 缓存:localStorage(与verify同款隐私策略,仅存浏览器);
//   不随主分析强制刷新重算(省token),用户可点"重新生成"显式刷新
// 依赖页面元素: #year #month #day #hour #familySection #famBody, 全局 currentSex
// ============================================================
var FamilyModule = (function () {
  // ---- 注入样式 ----
  (function injectStyle() {
    var s = document.createElement('style');
    s.textContent =
      '.fam-section{max-width:720px;margin:0 auto 20px;padding:0 20px}' +
      '.fam-card{background:linear-gradient(135deg,rgba(212,175,55,0.08),rgba(212,175,55,0.02));border:1px solid var(--border);border-radius:12px;padding:18px 20px}' +
      '.fam-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}' +
      '.fam-title{color:var(--gold);font-size:1.02em;letter-spacing:2px}' +
      '.fam-refresh{background:none;border:1px solid var(--border);border-radius:6px;color:var(--text-dim);font-size:0.75em;cursor:pointer;font-family:inherit;padding:4px 10px}' +
      '.fam-refresh:hover{border-color:var(--gold);color:var(--gold)}' +
      '.fam-block{margin-bottom:14px;padding:12px 14px;background:var(--bg-card2);border-radius:8px;border-left:3px solid var(--gold)}' +
      '.fam-block:last-child{margin-bottom:0}' +
      '.fam-block-title{color:var(--gold);font-size:0.88em;letter-spacing:1px;margin-bottom:6px}' +
      '.fam-block-content{font-size:0.85em;line-height:1.8;color:var(--text);white-space:pre-wrap}' +
      '.fam-loading{text-align:center;color:var(--text-dim);font-size:0.82em;padding:14px 0}';
    document.head.appendChild(s);
  })();

  var _getProfile = function () { return null; };  // 页面注入

  function _storeKey() {
    var y = document.getElementById('year').value, m = document.getElementById('month').value,
        d = document.getElementById('day').value, h = document.getElementById('hour').value;
    return 'mingli_family:' + y + '_' + m + '_' + d + '_' + h + '_' + currentSex;
  }
  function _load() {
    try { return JSON.parse(localStorage.getItem(_storeKey()) || 'null'); } catch (e) { return null; }
  }
  function _save(sections, raw) {
    try {
      localStorage.setItem(_storeKey(), JSON.stringify({ sections: sections, raw: raw, ts: Date.now() }));
    } catch (e) {}
  }

  function start() {
    var sec = document.getElementById('familySection');
    if (!sec) return;
    var y = document.getElementById('year').value, m = document.getElementById('month').value,
        d = document.getElementById('day').value;
    if (!y || !m || !d) { sec.style.display = 'none'; return; }
    var cached = _load();
    if (cached && (cached.sections || cached.raw)) {
      render(cached.sections, cached.raw);
      return;
    }
    generate(false);
  }

  function generate(isRefresh) {
    var sec = document.getElementById('familySection');
    sec.style.display = 'block';
    document.getElementById('famBody').innerHTML =
      '<div class="fam-loading">🏠 正在生成家庭分析（父母/手足），约20-40秒…</div>';
    fetch('/api/family', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-API-Key': 'mingli-qiankun-v7' },
      body: JSON.stringify({
        year: +document.getElementById('year').value,
        month: +document.getElementById('month').value,
        day: +document.getElementById('day').value,
        hour: +document.getElementById('hour').value,
        sex: currentSex,
        profile: _getProfile(),
        refresh: !!isRefresh
      })
    })
    .then(function (r) { return r.json(); })
    .then(function (resp) {
      if (!resp.ok || !resp.family) {
        sec.style.display = 'none';  // 静默降级,不影响主分析
        return;
      }
      var f = resp.family;
      if (!f.sections && !f.raw) { sec.style.display = 'none'; return; }
      _save(f.sections, f.raw);
      render(f.sections, f.raw);
    })
    .catch(function () { sec.style.display = 'none'; });
  }

  function render(sections, raw) {
    var sec = document.getElementById('familySection');
    sec.style.display = 'block';
    var html = '';
    if (sections && sections.length) {
      sections.forEach(function (b) {
        html += '<div class="fam-block">' +
          '<div class="fam-block-title">【' + b.title + '】</div>' +
          '<div class="fam-block-content">' + b.content + '</div></div>';
      });
    } else if (raw) {
      html = '<div class="fam-block"><div class="fam-block-content">' + raw + '</div></div>';
    }
    document.getElementById('famBody').innerHTML = html;
  }

  return {
    init: function (opts) { if (opts && opts.getProfile) _getProfile = opts.getProfile; },
    start: start,
    regenerate: function () { generate(true); }
  };
})();
