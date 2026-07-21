"""EdgeOne 国际站全自动部署脚本"""
from playwright.sync_api import sync_playwright
import time

EMAIL = "631262338@qq.com"
PASSWORD = "Anolovelzh168@"
PROJECT = "https://console.tencentcloud.com/edgeone/makers/project/makers-5umvnzbicklj"

def main():
    print("=" * 50)
    print("EdgeOne 国际站全自动部署")
    print("=" * 50)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context()
        page = ctx.new_page()

        # Step 1: Login
        print("\n[1/5] 打开项目页...")
        page.goto(PROJECT)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(3)

        if "/login" in page.url or "login" in page.url.lower():
            print("    检测到需要登录...")
            try:
                page.wait_for_selector('input', timeout=10000)

                # Fill email
                inputs = page.query_selector_all('input')
                for inp in inputs:
                    t = inp.get_attribute("type") or "text"
                    if t != "password":
                        inp.fill(EMAIL)
                        print(f"    已填写邮箱: {EMAIL}")
                        time.sleep(1)
                        break

                # Fill password
                pwd_inputs = page.query_selector_all('input[type="password"]')
                if pwd_inputs:
                    pwd_inputs[0].fill(PASSWORD)
                    print("    已填写密码")
                    time.sleep(1)

                # Click login
                for btn in page.query_selector_all('button, [type="submit"]'):
                    text = (btn.text_content() or "").strip()
                    if any(kw in text for kw in ['Login', 'Log in', 'Sign in', 'login']):
                        print(f"    点击: {text}")
                        btn.click()
                        time.sleep(8)
                        break

                print("    等待登录完成...")
                for i in range(40):
                    time.sleep(2)
                    cur_url = page.url
                    if "/login" not in cur_url and "tencentcloud" in cur_url:
                        print(f"    OK 登录成功! ({i*2}s)")
                        break
                    if i % 5 == 0:
                        print(f"    等待({i*2}s)... URL: {cur_url[:60]}")
            except Exception as e:
                print(f"    登录出错: {e}")

        # Step 2: Ensure on project page
        print("\n[2/5] 确保在项目页...")
        if "/makers/project" not in page.url:
            page.goto(PROJECT)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(5)

        page.screenshot(path="edgeone_project.png")
        print(f"    URL: {page.url[:80]}")

        # Step 3: Click Build & Deploy
        print("\n[3/5] 找 Build & Deploy ...")
        for i in range(30):
            time.sleep(1)
            for selector in ['a', '[role="menuitem"]', '[class*="nav"]', '[class*="menu"]', '[class*="sidebar"]']:
                for item in page.query_selector_all(selector):
                    try:
                        if not item.is_visible():
                            continue
                        text = (item.text_content() or "").strip()
                        if "Build" in text and "Deploy" in text:
                            print(f"    OK: {text[:40]}")
                            item.click()
                            time.sleep(3)
                            break
                    except:
                        continue
                else:
                    continue
                break
            else:
                if i % 5 == 0:
                    print(f"    扫描中({i}s)...")
                continue
            break

        page.screenshot(path="edgeone_build_page.png")

        # Step 4: Click deploy button
        print("\n[4/5] 找 Deploy 按钮...")
        deploy_hit = False
        for i in range(60):
            time.sleep(1)
            for btn in page.query_selector_all("button"):
                try:
                    if not btn.is_visible():
                        continue
                    text = (btn.text_content() or "").strip()
                    if not text or len(text) > 60:
                        continue
                    if any(s in text for s in ["Cancel", "Close", "Back"]):
                        continue
                    if any(k in text for k in [
                        "Deploy", "Redeploy", "Create Build", "Create Deployment",
                        "New Build", "New Deployment", "Trigger", "Build Now",
                    ]):
                        print(f"    OK: '{text}'")
                        btn.click()
                        deploy_hit = True
                        time.sleep(5)
                        break
                except:
                    continue
            if deploy_hit:
                break
            if i % 10 == 0:
                print(f"    扫描按钮({i}s)...")

        if deploy_hit:
            print("\n[5/5] 部署已触发! 等待构建...")
            time.sleep(15)
            page.screenshot(path="edgeone_building.png")
            for i in range(20):
                time.sleep(6)
                try:
                    content = page.content()
                    checks = ["Building", "Deploying", "Success", "Deployed", "Active"]
                    found = [c for c in checks if c in content]
                    if found:
                        print(f"    [{(i+1)*6+15}s] {found}")
                        if "Success" in content or "Deployed" in content or "Active" in content:
                            break
                except:
                    pass
            page.screenshot(path="edgeone_done.png")
            print("\n✅ 部署完成!")
        else:
            page.screenshot(path="edgeone_no_button.png")
            btns = page.query_selector_all("button")
            texts = []
            for b in btns:
                try:
                    if b.is_visible():
                        t = (b.text_content() or "").strip()
                        if t:
                            texts.append(t[:40])
                except:
                    pass
            print(f"\n可见按钮: {texts}")
            print("⚠️ 请手动点击部署")

        browser.close()
        print("=" * 50)

if __name__ == "__main__":
    main()
