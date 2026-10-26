# -*- coding: utf-8 -*-
"""P90: 流日/流月 六维度命理提醒邮件脚本(cron 调用)
用法:
  python liuri_remind.py daily              # 今日流日提醒
  python liuri_remind.py monthly            # 本月流月分析
  python liuri_remind.py daily --dry-run    # 只生成不发送(打印HTML到stdout)
环境变量:
  ML_SMTP_USER  QQ邮箱地址(发件)
  ML_SMTP_PASS  QQ邮箱SMTP授权码
  ML_MAIL_TO    收件地址(默认=发件人)
  DEEPSEEK_API_KEY  (liuri_core LLM 调用需要)
"""
import os
import sys
import json
import datetime
import smtplib
import traceback
from email.mime.text import MIMEText
from email.header import Header

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "..", "cloud-functions", "api"))

LOG_FILE = "/opt/mingli-qiankun/logs/liuri_remind.log"

# 命主档案(后续支持多用户时改为读取配置文件)
OWNER = {"year": 1987, "month": 7, "day": 8, "hour": 19, "sex": "男", "name": "命主"}

_DIM_META = [("事业", "💼"), ("财运", "💰"), ("健康", "🌿"),
             ("夫妻", "💑"), ("父母", "🏠"), ("儿女", "👶")]


def _log(msg):
    line = f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _score_block(r: dict) -> str:
    """总运指数+定调头部块(v2)"""
    sc, hl = r.get("score"), r.get("headline", "")
    if sc is None and not hl:
        return ""
    sc_txt = f'<span style="font-size:34px;font-weight:bold;color:#c8a45a">{sc}</span><span style="color:#999;font-size:13px">/100</span>' if sc is not None else ""
    hl_txt = f'<div style="font-size:16px;color:#8a6d2f;font-weight:bold;margin-top:2px">{hl}</div>' if hl else ""
    return (f'<div style="text-align:center;background:#faf5e8;border:1px solid #e8d9b0;border-radius:8px;'
            f'padding:14px;margin:10px 0">{sc_txt}{hl_txt}</div>')


def render_daily(r: dict) -> str:
    cards = "".join(
        f'<div style="background:#fdf8ee;border-left:3px solid #c8a45a;border-radius:6px;padding:10px 14px;margin:8px 0">'
        f'<div style="color:#8a6d2f;font-weight:bold;margin-bottom:4px">{icon} {name}</div>'
        f'<div style="color:#333;font-size:14px;line-height:1.7">{r["dims"].get(name, "—")}</div></div>'
        for name, icon in _DIM_META)
    s = r["sihua"]
    return f"""<div style="max-width:640px;margin:0 auto;font-family:Microsoft YaHei,sans-serif">
<h2 style="color:#8a6d2f;border-bottom:2px solid #c8a45a;padding-bottom:8px">🔮 命理乾坤 · 流日提醒 {r['date']}</h2>
<p style="color:#666;font-size:13px">大限 {r['decadal_ganzhi']} · 流年 {r['yearly_ganzhi']} · 流月 {r['month_ganzhi']} · <b>流日 {r['day_ganzhi']}</b><br>
日四化: 化禄{s['禄']} · 化权{s['权']} · 化科{s['科']} · 化忌{s['忌']}</p>
{_score_block(r)}
{cards}
<div style="display:flex;gap:10px;margin-top:12px">
<div style="flex:1;background:#eef7ee;border-radius:6px;padding:10px 14px"><b style="color:#3a7d3a">宜</b><br><span style="font-size:13px;color:#333">{'、'.join(r['yi'])}</span></div>
<div style="flex:1;background:#fbeeee;border-radius:6px;padding:10px 14px"><b style="color:#a03a3a">忌</b><br><span style="font-size:13px;color:#333">{'、'.join(r['ji'])}</span></div>
</div>
<p style="color:#999;font-size:12px;margin-top:16px">命理乾坤 mingli-qiankun.com · 流日引擎 {r.get('_ver','')}</p></div>"""


def render_monthly(r: dict) -> str:
    cards = "".join(
        f'<div style="background:#fdf8ee;border-left:3px solid #c8a45a;border-radius:6px;padding:10px 14px;margin:8px 0">'
        f'<div style="color:#8a6d2f;font-weight:bold;margin-bottom:4px">{icon} {name}</div>'
        f'<div style="color:#333;font-size:14px;line-height:1.7">{r["dims"].get(name, "—")}</div></div>'
        for name, icon in _DIM_META)
    days = "".join(f'<li style="margin:4px 0">{d}</li>' for d in r["key_days"])
    s = r["sihua"]
    return f"""<div style="max-width:640px;margin:0 auto;font-family:Microsoft YaHei,sans-serif">
<h2 style="color:#8a6d2f;border-bottom:2px solid #c8a45a;padding-bottom:8px">📅 命理乾坤 · 流月分析 {r['month']}</h2>
<p style="color:#666;font-size:13px">大限 {r['decadal_ganzhi']} · 流年 {r['yearly_ganzhi']} · <b>流月 {r['month_ganzhi']}</b><br>
月四化: 化禄{s['禄']} · 化权{s['权']} · 化科{s['科']} · 化忌{s['忌']}</p>
{_score_block(r)}
<div style="background:#f5edd8;border-radius:6px;padding:10px 14px;margin:10px 0"><b style="color:#8a6d2f">本月总纲</b><br>
<span style="font-size:14px;color:#333">{r['summary']}</span></div>
{cards}
<div style="background:#eef3fb;border-radius:6px;padding:10px 14px;margin-top:12px"><b style="color:#3a5a8d">⭐ 本月重点日</b>
<ul style="margin:6px 0;padding-left:20px;color:#333;font-size:14px">{days}</ul></div>
<p style="color:#999;font-size:12px;margin-top:16px">命理乾坤 mingli-qiankun.com · 流月引擎 {r.get('_ver','')}</p></div>"""


def send_mail(subject: str, html: str) -> bool:
    user = os.environ.get("ML_SMTP_USER", "")
    pwd = os.environ.get("ML_SMTP_PASS", "")
    to = os.environ.get("ML_MAIL_TO", user)
    if not user or not pwd:
        _log("ERROR: ML_SMTP_USER/ML_SMTP_PASS 未配置")
        return False
    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = user
    msg["To"] = to
    for attempt in range(2):
        try:
            with smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=30) as smtp:
                smtp.login(user, pwd)
                smtp.sendmail(user, [to], msg.as_string())
            _log(f"邮件发送成功 -> {to} | {subject}")
            return True
        except Exception as e:
            _log(f"邮件发送失败(第{attempt + 1}次): {str(e)[:200]}")
    return False


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "daily"
    dry = "--dry-run" in sys.argv
    from utils.liuri_core import daily_analysis, monthly_analysis
    today = datetime.date.today()

    if mode == "monthly":
        r = monthly_analysis(OWNER["year"], OWNER["month"], OWNER["day"], OWNER["hour"],
                             OWNER["sex"], today.year, today.month)
        if r.get("error"):
            _log("ERROR: " + r["error"])
            sys.exit(1)
        html = render_monthly(r)
        hl = f"｜{r['headline']}" if r.get("headline") else ""
        subject = f"📅 流月分析 {r['month']}（{r['month_ganzhi']}月）{hl} · 命理乾坤"
    else:
        r = daily_analysis(OWNER["year"], OWNER["month"], OWNER["day"], OWNER["hour"],
                           OWNER["sex"], today)
        if r.get("error"):
            _log("ERROR: " + r["error"])
            sys.exit(1)
        html = render_daily(r)
        hl = f"｜{r['headline']}" if r.get("headline") else ""
        subject = f"🔮 流日提醒 {r['date']}（{r['day_ganzhi']}日）{hl} · 命理乾坤"

    if dry:
        print(html)
        _log(f"dry-run 完成 ({mode}), 未发送")
        return
    ok = send_mail(subject, html)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
