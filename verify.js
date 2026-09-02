// ============================================================
// P80: 过三关验证模块(ziwei.html / index.html 共用)
// 先断前事 → 用户确认/纠正 → 反馈校准后续LLM分析
// 隐私:验证数据仅存浏览器localStorage;纠正原文只随请求传递,服务端不落盘
// 依赖页面元素: #year #month #day #hour #chkRefresh #verifySection #vfyBody
//   #vfyProgress #vfyBarWrap #vfyBar, 全局 currentSex, 函数 doAnalyze()
// ============================================================
var VerifyModule = (function () {
  // ---- 注入样式(两页共用,避免重复维护) ----
  (function injectStyle() {
    var s = document.createElement('style');
    s.textContent =
      '.vfy-section{max-width:720px;margin:0 auto 20px;padding:0 20px}' +
      '.vfy-card{background:linear-gradient(135deg,rgba(212,175,55,0.10),rgba(212,175,55,0.03));border:1px solid var(--gold);border-radius:12px;padding:18px 20px}' +
      '.vfy-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}' +
      '.vfy-title{color:var(--gold);font-size:1.02em;letter-spacing:2px}' +
      '.vfy-progress{font-size:0.78em;color:var(--text-dim)}' +
      '.vfy-bar{height:4px;background:var(--bg-card2);border-radius:2px;margin-bottom:14px;overflow:hidden}' +
      '.vfy-bar>i{display:block;height:100%;background:var(--gold);transition:width .3s}' +
      '.vfy-claim{font-size:0.95em;line-height:1.7;color:var(--text);margin-bottom:6px}' +
      '.vfy-basis{font-size:0.75em;color:var(--text-dim);margin-bottom:14px}' +
      '.vfy-btns{display:flex;gap:8px;flex-wrap:wrap}' +
      '.vfy-btn{flex:1;min-width:100px;padding:9px 6px;border-radius:8px;border:1px solid var(--border);background:var(--bg-card2);color:var(--text);cursor:pointer;font-size:0.85em;font-family:inherit;transition:all .2s}' +
      '.vfy-btn:hover{border-color:var(--gold);transform:translateY(-1px)}' +
      '.vfy-btn.sel-match{background:rgba(46,160,67,0.18);border-color:#2ea043}' +
      '.vfy-btn.sel-partial{background:rgba(212,175,55,0.18);border-color:var(--gold)}' +
      '.vfy-btn.sel-mismatch{background:rgba(231,76,60,0.15);border-color:#e74c3c}' +
      '.vfy-corr{width:100%;margin-top:10px;padding:9px 12px;border:1px solid var(--border);border-radius:8px;background:var(--bg-card2);color:var(--text);font-size:0.82em;font-family:inherit;resize:vertical;min-height:52px;box-sizing:border-box}' +
      '.vfy-foot{display:flex;justify-content:space-between;align-items:center;margin-top:14px}' +
      '.vfy-skip{background:none;border:none;color:var(--text-dim);font-size:0.78em;cursor:pointer;font-family:inherit;text-decoration:underline}' +
      '.vfy-submit{padding:9px 22px;background:var(--gold);color:#1a1a1a;border:none;border-radius:8px;cursor:pointer;font-size:0.85em;font-family:inherit;letter-spacing:1px}' +
      '.vfy-submit:disabled{opacity:0.4;cursor:not-allowed}' +
      '.vfy-rate{font-size:2.2em;color:var(--gold);font-weight:bold;text-align:center;margin:6px 0}' +
      '.vfy-advice{text-align:center;font-size:0.85em;color:var(--text);line-height:1.7;margin-bottom:12px}' +
      '.vfy-done-list{font-size:0.75em;color:var(--text-dim);line-height:1.8;margin-bottom:12px;max-height:120px;overflow-y:auto}' +
      '.vfy-tag{display:inline-block;padding:1px 6px;border-radius:4px;font-size:0.72em;margin-right:4px}' +
      '.vfy-tag.m{background:rgba(46,160,67,0.2);color:#3fb950}' +
      '.vfy-tag.p{background:rgba(212,175,55,0.2);color:var(--gold)}' +
      '.vfy-tag.x{background:rgba(231,76,60,0.2);color:#e74c3c}' +
      '.vfy-loading{text-align:center;color:var(--text-dim);font-size:0.82em;padding:14px 0}';
    document.head.appendChild(s);
  })();

  var _vfy = { items: [], idx: 0, answers: {}, chartKey: '', submitted: false, pendingRecal: false };
  var _getProfile = function () { return null; };  // 页面注入

  function _storeKey() {
    var y = document.getElementById('year').value, m = document.getElementById('month').value,
        d = document.getElementById('day').value, h = document.getElementById('hour').value;
    return 'mingli_verify:' + y + '_' + m + '_' + d + '_' + h + '_' + currentSex;
  }
  function _load() {
    try { return JSON.parse(localStorage.getItem(_storeKey()) || 'null'); } catch (e) { return null; }
  }
  function _save() {
    try {
      localStorage.setItem(_storeKey(), JSON.stringify({
        items: _vfy.items, answers: _vfy.answers, chartKey: _vfy.chartKey,
        submitted: _vfy.submitted, score: _vfy.score || null, advice: _vfy.advice || '',
        pendingRecal: _vfy.pendingRecal, ts: Date.now()
      }));
    } catch (e) {}
  }

  // 校准反馈:仅在用户点了"重新校准"或勾选强制刷新时才随analyze提交
  function pendingFeedback() {
    var vs = _load();
    if (!vs || !vs.submitted) return null;
    var isRefresh = document.getElementById('chkRefresh') && document.getElementById('chkRefresh').checked;
    if (!vs.pendingRecal && !isRefresh) return null;
    var answers = [];
    (vs.items || []).forEach(function (it) {
      var a = vs.answers[it.id];
      if (a) answers.push({ claim: it.claim, verdict: a.verdict, correction: a.correction || '' });
    });
    return answers.length ? { answers: answers } : null;
  }

  function clearPending() {
    if (_vfy.pendingRecal) { _vfy.pendingRecal = false; _save(); }
  }

  function start() {
    var sec = document.getElementById('verifySection');
    if (!sec) return;
    var y = document.getElementById('year').value, m = document.getElementById('month').value,
        d = document.getElementById('day').value;
    if (!y || !m || !d) { sec.style.display = 'none'; return; }

    var vs = _load();
    if (vs && vs.items && vs.items.length) {
      _vfy.items = vs.items; _vfy.answers = vs.answers || {};
      _vfy.chartKey = vs.chartKey || ''; _vfy.submitted = !!vs.submitted;
      _vfy.score = vs.score; _vfy.advice = vs.advice;
      _vfy.pendingRecal = !!vs.pendingRecal;
      _vfy.idx = _vfy.items.findIndex(function (it) { return !_vfy.answers[it.id]; });
      if (_vfy.idx < 0) _vfy.idx = _vfy.items.length;  // 全部已答未提交→完成页
      sec.style.display = 'block';
      if (_vfy.submitted) renderScore(); else renderCard();
      return;
    }

    // 首次:请求断语生成
    _vfy = { items: [], idx: 0, answers: {}, chartKey: '', submitted: false, pendingRecal: false };
    sec.style.display = 'block';
    document.getElementById('vfyBarWrap').style.display = 'none';
    document.getElementById('vfyProgress').textContent = '';
    document.getElementById('vfyBody').innerHTML = '<div class="vfy-loading">🔮 正在生成验证断语（过三关），约10-30秒…</div>';
    fetch('/api/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-API-Key': 'mingli-qiankun-v7' },
      body: JSON.stringify({
        year: +y, month: +m, day: +d,
        hour: +document.getElementById('hour').value, sex: currentSex,
        profile: _getProfile()
      })
    })
    .then(function (r) { return r.json(); })
    .then(function (resp) {
      if (!resp.ok || !resp.verify || !resp.verify.items || !resp.verify.items.length) {
        sec.style.display = 'none';  // 静默降级,不影响主分析
        return;
      }
      _vfy.items = resp.verify.items;
      _vfy.chartKey = resp.chart_key || '';
      _vfy.idx = 0;
      _save();
      renderCard();
    })
    .catch(function () { sec.style.display = 'none'; });
  }

  function renderCard() {
    var body = document.getElementById('vfyBody');
    var total = _vfy.items.length;
    if (_vfy.idx < 0) _vfy.idx = 0;
    if (_vfy.idx >= total) {  // 全部答完
      var done = Object.keys(_vfy.answers).length;
      body.innerHTML =
        '<div class="vfy-claim" style="text-align:center">已完成 ' + done + '/' + total + ' 条验证</div>' +
        '<div class="vfy-foot"><button class="vfy-skip" onclick="VerifyModule.skip()">跳过验证直接看分析</button>' +
        '<button class="vfy-submit" onclick="VerifyModule.submit()">完成验证，查看准确度 →</button></div>';
      document.getElementById('vfyProgress').textContent = done + '/' + total;
      document.getElementById('vfyBar').style.width = '100%';
      return;
    }
    var it = _vfy.items[_vfy.idx];
    var cur = _vfy.answers[it.id] || {};
    var answered = Object.keys(_vfy.answers).length;
    document.getElementById('vfyProgress').textContent = '第 ' + (_vfy.idx + 1) + '/' + total + ' 条';
    document.getElementById('vfyBarWrap').style.display = 'block';
    document.getElementById('vfyBar').style.width = Math.round(answered / total * 100) + '%';
    body.innerHTML =
      '<div class="vfy-claim">「' + it.claim + '」</div>' +
      '<div class="vfy-basis">依据：' + it.basis + '</div>' +
      '<div class="vfy-btns">' +
        '<button class="vfy-btn ' + (cur.verdict === 'match' ? 'sel-match' : '') + '" onclick="VerifyModule.answer(\'match\')">✅ 完全符合</button>' +
        '<button class="vfy-btn ' + (cur.verdict === 'partial' ? 'sel-partial' : '') + '" onclick="VerifyModule.answer(\'partial\')">🟡 部分符合</button>' +
        '<button class="vfy-btn ' + (cur.verdict === 'mismatch' ? 'sel-mismatch' : '') + '" onclick="VerifyModule.answer(\'mismatch\')">❌ 不符</button>' +
      '</div>' +
      '<textarea class="vfy-corr" id="vfyCorr" placeholder="实际情况（选填，帮助校准后续分析）" style="display:' +
        (cur.verdict === 'mismatch' ? 'block' : 'none') + '">' + (cur.correction || '') + '</textarea>' +
      '<div class="vfy-foot"><button class="vfy-skip" onclick="VerifyModule.skip()">跳过验证直接看分析</button>' +
      '<span style="font-size:0.75em;color:var(--text-dim)">选择后自动进入下一条</span></div>';
  }

  function answer(verdict) {
    var it = _vfy.items[_vfy.idx];
    var corr = (document.getElementById('vfyCorr') || {}).value || '';
    _vfy.answers[it.id] = { verdict: verdict, correction: corr.trim() };
    _save();
    if (verdict === 'mismatch' && !corr) {
      renderCard();  // 展开纠正输入框,停留当前条
      return;
    }
    _vfy.idx++;
    renderCard();
  }

  function skip() {
    document.getElementById('verifySection').style.display = 'none';
  }

  function submit() {
    var answers = [];
    _vfy.items.forEach(function (it) {
      var a = _vfy.answers[it.id];
      if (a) answers.push({ claim: it.claim, verdict: a.verdict, correction: a.correction || '' });
    });
    if (!answers.length) { skip(); return; }
    var body = document.getElementById('vfyBody');
    body.innerHTML = '<div class="vfy-loading">正在计算吻合度…</div>';
    fetch('/api/verify-feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-API-Key': 'mingli-qiankun-v7' },
      body: JSON.stringify({ chart_key: _vfy.chartKey || _storeKey(), feedback: { answers: answers } })
    })
    .then(function (r) { return r.json(); })
    .then(function (resp) {
      if (!resp.ok) {
        body.innerHTML = '<div class="vfy-claim" style="text-align:center">' +
          (resp.message || '提交失败,请稍后重试') + '</div>';
        return;
      }
      _vfy.submitted = true;
      _vfy.score = resp.score;
      _vfy.advice = resp.advice;
      _save();
      renderScore();
    })
    .catch(function () {
      body.innerHTML = '<div class="vfy-claim" style="text-align:center">网络异常,请稍后重试</div>';
    });
  }

  function renderScore() {
    var s = _vfy.score || { rate: 0, match: 0, partial: 0, mismatch: 0 };
    document.getElementById('vfyProgress').textContent = '';
    document.getElementById('vfyBarWrap').style.display = 'block';
    document.getElementById('vfyBar').style.width = s.rate + '%';
    var list = _vfy.items.map(function (it) {
      var a = _vfy.answers[it.id] || {};
      var tag = a.verdict === 'match' ? '<span class="vfy-tag m">符合</span>' :
                a.verdict === 'partial' ? '<span class="vfy-tag p">部分</span>' :
                a.verdict === 'mismatch' ? '<span class="vfy-tag x">不符</span>' : '';
      return '<div>' + tag + it.claim + '</div>';
    }).join('');
    document.getElementById('vfyBody').innerHTML =
      '<div class="vfy-rate">' + s.rate + '%</div>' +
      '<div class="vfy-advice">' + (_vfy.advice || '') +
        '<br><span style="font-size:0.78em;color:var(--text-dim)">符合 ' + s.match + ' · 部分 ' + s.partial + ' · 不符 ' + s.mismatch + '</span></div>' +
      '<div class="vfy-done-list">' + list + '</div>' +
      '<div class="vfy-foot"><button class="vfy-skip" onclick="VerifyModule.skip()">收起验证区</button>' +
      '<button class="vfy-submit" onclick="VerifyModule.recalibrate()">📊 用验证结果校准分析</button></div>';
  }

  function recalibrate() {
    _vfy.pendingRecal = true;
    _save();
    var chk = document.getElementById('chkRefresh');
    if (chk) chk.checked = true;  // 校准必须全量重算(服务端缓存key含反馈hash)
    doAnalyze();
  }

  return {
    init: function (opts) { if (opts && opts.getProfile) _getProfile = opts.getProfile; },
    start: start,
    skip: skip,
    answer: answer,
    submit: submit,
    recalibrate: recalibrate,
    pendingFeedback: pendingFeedback,
    clearPending: clearPending
  };
})();
