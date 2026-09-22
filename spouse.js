// ============================================================
// P83: 夫妻分析模块(ziwei.html 用)
// 配偶画像/婚恋应期/婚姻互动 三段(LLM,服务端 /api/spouse)
// 支持录入配偶生辰直排(已婚时展开填写,有则本盘精度,无则夫妻宫隔层)
// marital称谓红线:非已婚服务端严禁"丈夫/妻子"称谓(parse_spouse闸门)
// 缓存:localStorage(与family同款隐私策略,仅存浏览器);
//   不随主分析强制刷新重算(省token),用户可点"重新生成"显式刷新
// 依赖页面元素: #year #month #day #hour #spouseSection #spoBody, 全局 currentSex
// ============================================================
var SpouseModule = (function () {
  // ---- 注入样式 ----
  (function injectStyle() {
    var s = document.createElement('style');
    s.textContent =
      '.spo-input{background:var(--bg-card2);border:1px solid var(--border);border-radius:8px;padding:10px 14px;margin-bottom:12px;font-size:0.82em;color:var(--text)}' +
      '.spo-input select,.spo-input input{background:var(--bg-card);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:0.95em;font-family:inherit;padding:5px 8px}' +
      '.spo-input label{color:var(--text-dim);margin-right:6px}' +
      '.spo-birth{margin-top:8px;display:none;padding-top:8px;border-top:1px dashed var(--border)}' +
      '.spo-hint{color:var(--text-dim);font-size:0.9em;margin-top:6px;line-height:1.5}';
    document.head.appendChild(s);
  })();

  var _getProfile = function () { return null; };  // 页面注入

  var HOURS = [[0,'子时 (23-01点)'],[1,'丑时 (01-03点)'],[3,'寅时 (03-05点)'],[5,'卯时 (05-07点)'],
               [7,'辰时 (07-09点)'],[9,'巳时 (09-11点)'],[11,'午时 (11-13点)'],[13,'未时 (13-15点)'],
               [15,'申时 (15-17点)'],[17,'酉时 (17-19点)'],[19,'戌时 (19-21点)'],[21,'亥时 (21-23点)']];

  function _birthKey() {
    var y = document.getElementById('year').value, m = document.getElementById('month').value,
        d = document.getElementById('day').value, h = document.getElementById('hour').value;
    return y + '_' + m + '_' + d + '_' + h + '_' + currentSex;
  }
  function _inputKey() { return 'mingli_spouse_input:' + _birthKey(); }

  function _loadInput() {
    try { return JSON.parse(localStorage.getItem(_inputKey()) || 'null') || {}; } catch (e) { return {}; }
  }
  function _saveInput() {
    var inp = {
      marital: document.getElementById('spoMarital').value,
      sp: {
        year: document.getElementById('spoYear').value,
        month: document.getElementById('spoMonth').value,
        day: document.getElementById('spoDay').value,
        hour: document.getElementById('spoHour').value,
        sex: document.getElementById('spoSex').value
      }
    };
    try { localStorage.setItem(_inputKey(), JSON.stringify(inp)); } catch (e) {}
  }

  // 展示缓存key含录入内容hash——改婚姻状态/配偶生辰后旧结果不串
  function _storeKey() {
    var inp = _loadInput();
    var s = (inp.marital || '') + '|' + (inp.sp ? [inp.sp.year, inp.sp.month, inp.sp.day, inp.sp.hour, inp.sp.sex].join('_') : '');
    var h = 0;
    for (var i = 0; i < s.length; i++) { h = ((h << 5) - h + s.charCodeAt(i)) | 0; }
    return 'mingli_spouse:' + _birthKey() + ':' + Math.abs(h).toString(36);
  }
  function _load() {
    try { return JSON.parse(localStorage.getItem(_storeKey()) || 'null'); } catch (e) { return null; }
  }
  function _save(sections, raw, direct) {
    try {
      localStorage.setItem(_storeKey(), JSON.stringify({ sections: sections, raw: raw, direct: direct, ts: Date.now() }));
    } catch (e) {}
  }

  function _spousePayload() {
    var m = document.getElementById('spoMarital').value;
    var sp = null;
    if (m === '已婚' || m === '再婚' || m === '恋爱中') {
      var y = document.getElementById('spoYear').value,
          mo = document.getElementById('spoMonth').value,
          d = document.getElementById('spoDay').value;
      if (y && mo && d) {
        sp = { year: +y, month: +mo, day: +d,
               hour: +document.getElementById('spoHour').value,
               sex: document.getElementById('spoSex').value };
      }
    }
    return { marital: m, spouse: sp };
  }

  function _renderInput() {
    var inp = _loadInput();
    var sp = inp.sp || {};
    var opts = ['', '未婚', '恋爱中', '已婚', '离异', '丧偶'];
    var mHtml = '';
    for (var i = 0; i < opts.length; i++) {
      var lab = opts[i] || '请选择';
      mHtml += '<option value="' + opts[i] + '"' + (inp.marital === opts[i] ? ' selected' : '') + '>' + lab + '</option>';
    }
    var hHtml = '';
    for (var j = 0; j < HOURS.length; j++) {
      var hv = (sp.hour !== undefined && sp.hour !== '' && +sp.hour === HOURS[j][0]);
      hHtml += '<option value="' + HOURS[j][0] + '"' + (hv ? ' selected' : '') + '>' + HOURS[j][1] + '</option>';
    }
    var show = (inp.marital === '已婚' || inp.marital === '再婚' || inp.marital === '恋爱中');
    var html =
      '<label>婚姻状态</label><select id="spoMarital" onchange="SpouseModule.onInputChange()">' + mHtml + '</select>' +
      '<div class="spo-birth" id="spoBirth" style="display:' + (show ? 'block' : 'none') + '">' +
        '<label>对象生辰(选填,录入后按对象本盘直排,精度更高)</label><br>' +
        '<input type="number" id="spoYear" placeholder="年" min="1930" max="2026" style="width:70px" value="' + (sp.year || '') + '" onchange="SpouseModule.onInputChange()"> ' +
        '<input type="number" id="spoMonth" placeholder="月" min="1" max="12" style="width:52px" value="' + (sp.month || '') + '" onchange="SpouseModule.onInputChange()"> ' +
        '<input type="number" id="spoDay" placeholder="日" min="1" max="31" style="width:52px" value="' + (sp.day || '') + '" onchange="SpouseModule.onInputChange()"> ' +
        '<select id="spoHour" onchange="SpouseModule.onInputChange()">' + hHtml + '</select> ' +
        '<select id="spoSex" onchange="SpouseModule.onInputChange()">' +
          '<option value="' + (currentSex === '男' ? '女' : '男') + '"' + (sp.sex !== currentSex ? ' selected' : '') + '>' + (currentSex === '男' ? '女' : '男') + '</option>' +
          '<option value="' + currentSex + '"' + (sp.sex === currentSex ? ' selected' : '') + '>' + currentSex + '</option>' +
        '</select>' +
      '</div>' +
      '<div class="spo-hint">填写婚姻状态后点「生成」——已婚/恋爱中可继续录对象生辰走双盘直排；未录则按命主夫妻宫推断对象类型。</div>';
    document.getElementById('spoInput').innerHTML = html;
  }

  function start() {
    var sec = document.getElementById('spouseSection');
    if (!sec) return;
    var y = document.getElementById('year').value, m = document.getElementById('month').value,
        d = document.getElementById('day').value;
    if (!y || !m || !d) { sec.style.display = 'none'; return; }
    sec.style.display = 'block';
    _renderInput();
    var inp = _loadInput();
    if (!inp.marital) {
      // 未填婚姻状态:只展示录入区,不自动调LLM(省token,称谓闸门需要事实前提)
      document.getElementById('spoBody').innerHTML = '';
      return;
    }
    var cached = _load();
    if (cached && (cached.sections || cached.raw)) {
      render(cached.sections, cached.raw, cached.direct);
      return;
    }
    generate(false);
  }

  function generate(isRefresh) {
    var sec = document.getElementById('spouseSection');
    sec.style.display = 'block';
    var pl = _spousePayload();
    if (!pl.marital) {
      document.getElementById('spoBody').innerHTML =
        '<div class="fam-loading">请先选择婚姻状态再生成</div>';
      return;
    }
    _saveInput();
    document.getElementById('spoBody').innerHTML =
      '<div class="fam-loading">💑 正在生成夫妻分析（配偶/婚恋/相处），约20-40秒…</div>';
    var profile = _getProfile();
    if (profile) { profile = Object.assign({}, profile, { marital: pl.marital }); }
    fetch('/api/spouse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-API-Key': 'mingli-qiankun-v7' },
      body: JSON.stringify({
        year: +document.getElementById('year').value,
        month: +document.getElementById('month').value,
        day: +document.getElementById('day').value,
        hour: +document.getElementById('hour').value,
        sex: currentSex,
        profile: profile,
        marital: pl.marital,
        spouse: pl.spouse,
        refresh: !!isRefresh
      })
    })
    .then(function (r) { return r.json(); })
    .then(function (resp) {
      if (!resp.ok || !resp.spouse) {
        document.getElementById('spoBody').innerHTML = '';  // 静默降级,录入区保留
        return;
      }
      var f = resp.spouse;
      if (!f.sections && !f.raw) { document.getElementById('spoBody').innerHTML = ''; return; }
      _save(f.sections, f.raw, !!f.direct_chart);
      render(f.sections, f.raw, !!f.direct_chart);
    })
    .catch(function () { document.getElementById('spoBody').innerHTML = ''; });
  }

  function render(sections, raw, direct) {
    var html = '';
    if (direct) {
      html += '<div style="color:var(--text-dim);font-size:0.78em;margin-bottom:10px">✓ 已按配偶本盘直排分析（双盘联动）</div>';
    }
    if (sections && sections.length) {
      sections.forEach(function (b) {
        html += '<div class="fam-block">' +
          '<div class="fam-block-title">【' + b.title + '】</div>' +
          '<div class="fam-block-content">' + b.content + '</div></div>';
      });
    } else if (raw) {
      html += '<div class="fam-block"><div class="fam-block-content">' + raw + '</div></div>';
    }
    document.getElementById('spoBody').innerHTML = html;
  }

  return {
    init: function (opts) { if (opts && opts.getProfile) _getProfile = opts.getProfile; },
    start: start,
    regenerate: function () { generate(true); },
    generate: function () { generate(false); },
    onInputChange: function () {
      var m = document.getElementById('spoMarital').value;
      document.getElementById('spoBirth').style.display =
        (m === '已婚' || m === '再婚' || m === '恋爱中') ? 'block' : 'none';
      _saveInput();
    }
  };
})();
