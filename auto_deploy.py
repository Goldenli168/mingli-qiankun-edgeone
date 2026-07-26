"""EdgeOne Makers Delete + Recreate (v8.32)
已验证: 普通 Redeploy 不更新云函数，必须 Delete + Recreate。
"""
from playwright.sync_api import sync_playwright
import time, re

EMAIL = "631262338@qq.com"
PASSWORD = "Anolovelzh168@"
PID = "makers-5umvnzbicklj"
PROJ = f"https://console.tencentcloud.com/edgeone/makers/project/{PID}"
HOME = "https://console.tencentcloud.com/edgeone/makers"
REPO = "Goldenli168/mingli-qiankun-edgeone"
BRANCH = "main"

def find_el(page, texts, tag="button"):
    for el in page.query_selector_all(tag):
        try:
            if not el.is_visible(): continue
            t = (el.text_content() or "").strip()
            if any(k in t for k in texts):
                return el, t
        except: pass
    return None, ""

def click_el(page, texts, tag="button", wait=3):
    el, t = find_el(page, texts, tag)
    if el:
        print(f"    > {t[:80]}")
        el.click()
        time.sleep(wait)
        return True
    return False

def page_diag(page, label=""):
    """打印当前页面诊断信息"""
    print(f"  [{label}] URL: {page.url[:100]}")
    try:
        btns = []
        for b in page.query_selector_all("button"):
            try:
                if b.is_visible():
                    t = (b.text_content() or "").strip()
                    if t: btns.append(t[:50])
            except: pass
        if btns: print(f"  [{label}] buttons: {btns[:12]}")
    except: pass

def login(page):
    print("[1/4] login ...")
    page.goto(PROJ, timeout=60000)
    page.wait_for_load_state("domcontentloaded")
    time.sleep(4)

    if "login" not in page.url.lower() and "makers" in page.url:
        print("  session ok")
        return True

    print("  login page detected")
    page.wait_for_selector("input", timeout=15000)

    for inp in page.query_selector_all("input"):
        t = inp.get_attribute("type") or "text"
        if t != "password":
            inp.fill(EMAIL)
            time.sleep(1)
            break

    pwds = page.query_selector_all('input[type="password"]')
    if pwds:
        pwds[0].fill(PASSWORD)
        time.sleep(1)

    for btn in page.query_selector_all("button, [type='submit']"):
        text = (btn.text_content() or "").strip().lower()
        if any(k in text for k in ["login", "sign in", "log in"]):
            btn.click()
            break

    time.sleep(8)
    for i in range(30):
        if "login" not in page.url.lower():
            print("  login ok")
            break
        time.sleep(2)

    page.goto(PROJ, timeout=60000)
    page.wait_for_load_state("domcontentloaded")
    time.sleep(5)
    page_diag(page, "after_login")
    page.screenshot(path="edgeone_01_login.png")
    return True

def delete_project(page):
    print("[2/4] delete project ...")

    # 确保在项目页(非首页)
    if "/makers/project/" not in page.url:
        page.goto(PROJ, timeout=60000)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(6)

    page_diag(page, "delete_start")
    page.screenshot(path="edgeone_02_delete_start.png")

    # 找 Settings 链接并点击(侧边栏)
    for attempt in range(4):
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(2)
        if click_el(page, ["Settings", "settings", "setting"], tag="a, button, span, li, div"):
            time.sleep(4)
            break
        # 也可能在 tabs 里
        if click_el(page, ["Settings", "settings"], tag="[class*='tab'], [class*='Tab']"):
            time.sleep(4)
            break
        time.sleep(2)

    page_diag(page, "after_settings")
    page.screenshot(path="edgeone_03_settings.png")

    # 滚到底部找 Delete
    for attempt in range(4):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(3)
        if click_el(page, ["Delete Project", "Delete", "Remove", "delete this project",
                            "delete project"], tag="button, a, span, td, div[role='button']"):
            time.sleep(3)
            page.screenshot(path="edgeone_04_confirm.png")
            break
    else:
        # 暴力扫描
        print("  brute force scan ...")
        for el in page.query_selector_all("*"):
            try:
                if not el.is_visible(): continue
                t = (el.text_content() or "").strip()
                if t.lower() in ["delete project", "delete", "remove", "delete this project"]:
                    el.click()
                    time.sleep(3)
                    break
            except: pass

    # 确认对话框
    time.sleep(3)
    # 可能需输入项目名
    for inp in page.query_selector_all("input"):
        try:
            if not inp.is_visible(): continue
            ph = (inp.get_attribute("placeholder") or "").lower()
            if any(k in ph for k in ["project", "name", "delete", "confirm"]):
                inp.fill(PID)
                print(f"  filled confirm: {PID}")
                time.sleep(1)
                break
        except: pass

    click_el(page, ["Delete", "Confirm", "OK", "ok", "delete", "confirm", "remove"],
             tag="button", wait=6)
    time.sleep(8)
    page.screenshot(path="edgeone_05_deleted.png")
    print("  delete done")
    return True

def create_project(page):
    print("[3/4] create project ...")
    page.goto(HOME, timeout=60000)
    page.wait_for_load_state("domcontentloaded")
    time.sleep(5)
    page.screenshot(path="edgeone_06_home.png")
    page_diag(page, "home")

    # 找 Create / Import / New 按钮
    for attempt in range(5):
        if click_el(page, ["Create Project", "New Project", "Import", "Create",
                            "create project", "new project"],
                    tag="button, a, span, div", wait=4):
            time.sleep(4)
            break
        time.sleep(2)

    page.screenshot(path="edgeone_07_create_page.png")
    page_diag(page, "create_page")

    # 选 GitHub
    click_el(page, ["GitHub", "github", "Github"],
             tag="button, div, span, a, img", wait=5)
    time.sleep(4)

    # 搜索仓库
    print(f"  search repo: {REPO}")
    for inp in page.query_selector_all("input"):
        try:
            if not inp.is_visible(): continue
            ph = (inp.get_attribute("placeholder") or "").lower()
            if any(k in ph for k in ["search", "repo", "repository"]):
                inp.fill(REPO)
                time.sleep(3)
                break
        except: pass

    page.screenshot(path="edgeone_08_search.png")

    # 点搜索结果
    time.sleep(3)
    click_el(page, [REPO, "mingli-qiankun-edgeone"],
             tag="div, span, a, li, tr", wait=4)

    # 选分支
    time.sleep(3)
    click_el(page, [BRANCH, "main"],
             tag="div, span, button, input, option", wait=3)

    page.screenshot(path="edgeone_09_before_create.png")

    # 创建
    click_el(page, ["Create Project", "Deploy", "Create", "create", "Finish"],
             tag="button", wait=8)

    print("[4/4] waiting for build ...")
    for i in range(40):
        time.sleep(10)
        try:
            content = page.content()
            for kw in ["Success", "Deployed", "Active", "Ready", "success"]:
                if kw in content:
                    print(f"  build done! ({kw})")
                    page.screenshot(path="edgeone_10_done.png")
                    return True
        except: pass
        if i % 3 == 0:
            page.screenshot(path=f"edgeone_build_{i}.png")
            print(f"  ... {(i+1)*10}s")

    page.screenshot(path="edgeone_10_final.png")
    return True

def main():
    print("=" * 50)
    print(f"EdgeOne Delete+Recreate  v8.32")
    print(f"{PID} -> {REPO}/{BRANCH}")
    print("=" * 50)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context()
        page = ctx.new_page()

        try:
            login(page)
            delete_project(page)
            create_project(page)
        except Exception as e:
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()
            page.screenshot(path="edgeone_error.png")
        finally:
            browser.close()
            print("=" * 50)

if __name__ == "__main__":
    main()
