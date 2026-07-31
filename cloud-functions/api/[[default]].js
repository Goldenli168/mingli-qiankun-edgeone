/**
 * 命理乾坤 · Edge Functions (Node.js)
 * 紫微斗数 + 八字 排盘 API
 */

var iztro = require('iztro');

// DeepSeek LLM 调用
function llmCall(prompt, maxTokens) {
    var apiKey = typeof DEEPSEEK_API_KEY !== 'undefined' ? DEEPSEEK_API_KEY : '';
    if (!apiKey) {
        return Promise.resolve(null);
    }
    return fetch('https://api.deepseek.com/v1/chat/completions', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + apiKey
        },
        body: JSON.stringify({
            model: 'deepseek-chat',
            messages: [{ role: 'user', content: prompt }],
            max_tokens: maxTokens || 800,
            temperature: 0.7,
            stream: false
        })
    })
    .then(function(resp) { return resp.json(); })
    .then(function(data) {
        if (data.choices && data.choices[0] && data.choices[0].message) {
            return data.choices[0].message.content.trim();
        }
        return null;
    })
    .catch(function(e) {
        console.error('LLM error:', e);
        return null;
    });
}

// 时辰映射：0-23点 → 0-11时辰
function hourToShichen(hour) {
    if (hour >= 23 || hour < 1) return 0;
    if (hour >= 1 && hour < 3) return 1;
    if (hour >= 3 && hour < 5) return 2;
    if (hour >= 5 && hour < 7) return 3;
    if (hour >= 7 && hour < 9) return 4;
    if (hour >= 9 && hour < 11) return 5;
    if (hour >= 11 && hour < 13) return 6;
    if (hour >= 13 && hour < 15) return 7;
    if (hour >= 15 && hour < 17) return 8;
    if (hour >= 17 && hour < 19) return 9;
    if (hour >= 19 && hour < 21) return 10;
    if (hour >= 21 && hour < 23) return 11;
    return 0;
}

// 排盘主函数
function fullZiweiAnalysis(year, month, day, hour, sex) {
    var shichen = hourToShichen(hour);
    var astrolabe = iztro.astro.astrolabeBySolarDate(
        year + '-' + month + '-' + day,
        shichen,
        sex,
        true,
        'zh-CN'
    );

    var palaces = [];
    for (var i = 0; i < astrolabe.palaces.length; i++) {
        var p = astrolabe.palaces[i];
        var majorStars = [];
        for (var j = 0; j < p.majorStars.length; j++) {
            majorStars.push(p.majorStars[j].name);
        }
        var minorStars = [];
        for (var k = 0; k < p.minorStars.length; k++) {
            minorStars.push(p.minorStars[k].name);
        }
        palaces.push({
            '宫名': p.name,
            '宫位': p.earthlyBranch,
            '天干': p.heavenlyStem,
            '地支': p.earthlyBranch,
            '主星': majorStars,
            '辅星': minorStars,
            '是否命宫': p.name === '命宫',
            '是否身宫': p.name === '身宫',
            '大限': p.decadal ? p.decadal.range[0] + '-' + p.decadal.range[1] + '岁' : ''
        });
    }

    return {
        '基本信息': {'性别': sex, '公历': year + '年' + month + '月' + day + '日', '农历': ''},
        '命宫地支': '',
        '身宫地支': '',
        '五行局': '',
        '十二宫': palaces,
        '四化': {'年干': '', '化禄': '', '化权': '', '化科': '', '化忌': ''},
        '大运': [],
        '流年': [],
        '飞化分析': {'飞化': [], '串联': [], '大运四化': [], '流年四化': []},
        '八字联合': {},
        '八字专项': {}
    };
}

// Edge Functions 入口
export function onRequest(context) {
    var request = context.request;
    var url = new URL(request.url);
    var path = url.pathname;

    var headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type, X-API-Key',
        'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
        'Content-Type': 'application/json'
    };

    if (request.method === 'OPTIONS') {
        return new Response(null, { headers: headers });
    }

    var apiKey = request.headers.get('X-API-Key') || '';
    if (path !== '/api/health' && apiKey !== 'mingli-qiankun-v7') {
        return new Response(JSON.stringify({ error: '未授权访问' }), { status: 401, headers: headers });
    }

    if (path === '/api/health') {
        return new Response(JSON.stringify({
            status: 'ok',
            version: 'v9.1-nodejs-llm-test',
            has_iztro: true,
            has_llm: true
        }), { headers: headers });
    }

    if (path === '/api/ziwei' && request.method === 'POST') {
        return request.json().then(function(body) {
            try {
                var result = fullZiweiAnalysis(
                    parseInt(body.year),
                    parseInt(body.month),
                    parseInt(body.day),
                    parseInt(body.hour || 12),
                    body.sex || '男'
                );

                // P56: LLM 调用（验证超时时间）
                var prompt = '你是资深命理师。请为以下命盘写一段180字全局总结。生于' + body.year + '年，命宫' + (result['十二宫'].find(function(p){return p['是否命宫']}) || {})['宫名'] + '。语气专业有温度，直接输出。';
                return llmCall(prompt, 800).then(function(llmResult) {
                    if (llmResult) {
                        result['命盘总结'] = llmResult;
                    }
                    return new Response(JSON.stringify(result), { headers: headers });
                });
            } catch (e) {
                return new Response(JSON.stringify({ error: '分析异常: ' + e.message }), { status: 500, headers: headers });
            }
        });
    }

    return new Response(JSON.stringify({ error: 'Not Found' }), { status: 404, headers: headers });
}
