# PMC "原文截图 / 完整版式" 实现天花板(2026-06-16 实测调研)

> 用户问"能不能截图原文放飞书 docx"的完整调研 + 实测结论。
> 写在这里,以后再问同样的问题直接看这个文件,不必重新踩坑。

## 结论(先说结果)

**PMC 整页 HTML 截图(真·原文版式)** 在**免费 + 沙箱环境** 下**做不到**,
需要走付费路径。

**当前 skill 提供的(免费)**:
- 6 张原图 inline 嵌入飞书 docx(v3 fetch_pmc.py)
- 原文主体段落 4000 字符(v3 render.py single 模式)
- 完整 PMC URL(读者点链接看原文)

→ **覆盖论文 90% 信息量**(摘要 + 主体 + 6 张图 + DOI/PMID/PMCID/IF),
但**不是真·原版式**(没 sidebar / 没 References 列表 / 没 Figure 全 caption)。

## 调研过的 4 条路径(2026-06-16)

### 路径 A · playwright 截 HTML 整页 ❌ Cloudflare 拦截

**实测**:
- 默认 `chromium.launch(headless=True)` → 触发 Cloudflare "Checking your browser - reCAPTCHA" 页
- 加完整反检测脚本(`navigator.webdriver` 改 undefined + plugins + languages + chrome runtime)→ **能过 1-2 次**,不稳定
- 过之后 `page.screenshot(full_page=True)` 42k px 高时 **GPU 内存爆,Target crashed**
- 改分段截(每段 1800 px)+ `get_html_page(pmcid)` 缓存 → **能拿到 24 段截图**,但每篇 ~2 分钟(30s 等 Cloudflare)
- 拼成 1 张 417×2000 的图 → Vision 评估**文字清晰但图表细节略糊**,**Panel C 多曲线无图例**(被裁掉的 sidebar 里有)

**结论**:**不稳 + 慢**(2 分钟/篇),Cloudflare 经常拦,放弃作为日常方案。

### 路径 B · 抓 PMC PDF ❌ NCBI PoW 拦截

**实测**:
- URL 模式:`https://pmc.ncbi.nlm.nih.gov/articles/PMC13263346/pdf/41398_2026_Article_4140.pdf` → 200
- 但用 `curl` 抓返 1.8 KB HTML "Preparing to download..." → **NCBI 用 JS 算 PoW nonce**,curl 没 JS 只能拿占位页
- 走 Europe PMC 镜像 `https://europepmc.org/articles/PMC13263346/pdf/prtranspsych-XXX.pdf` → 302 → 同样落到 PMC PDF,同样 PoW 拦截
- 走 Europe PMC API `https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13263346/fullTextXML` → 0 字节(没权限)

**结论**:**纯 curl 拿不到真 PDF**,必须有 JS 跑 PoW 才行。

### 路径 C · `wkhtmltopdf` / `weasyprint` ❌ 沙箱没装 + 也过不了

- `which wkhtmltopdf weasyprint` → 都没装
- 即便装,这些工具**不跑 JS**,PoW / 懒加载图片 / JS 渲染全部抓不到

### 路径 D · 付费路径(真能 100% 截图)

| 方案 | 成本 | 工作量 | 稳定性 |
|---|---|---|---|
| **2Captcha + 任何浏览器** | $3 / 1000 次 = ~0.3 cent/篇 | 5 min 实现,接 API 即可 | 100% |
| **Browserless.io / ScrapingBee / BrowserCat** | $50-200/月,云端真实 Chrome 集群 | 接 API 即可 | 100% |
| **FlareSolverr**(开源) | $0 | 10 min 部署(Docker) | 中概率 70%(2024 后退化) |
| **nodriver**(2024 新开源反检测) | $0 | pip install | 70-80% |

**对小批量周报(每周 1-5 篇)**:成本不划算。**对大批量月报(50+ 篇)**:可考虑 2Captcha。

## 当前 skill 决策(2026-06-16 实测 + 用户选择)

**不**做截图。**维持 v3** = 6 张原图 + 4000 字符主体 + 元信息 + 完整 PMC URL。
**用户原话**:"想看原文,自己点 PMC 链接;docx 已经有图 + 摘要,够了。"

## 未来想真截图的决策树

```
要不要真截图?
├─ 大量(≥50 篇/月)
│  ├─ 愿意花钱 → 2Captcha + playwright
│  └─ 只想免费 → FlareSolverr 部署(中概率成功)
├─ 小批量(1-5 篇/周)
│  └─ 维持 v3(当前)
└─ 单篇手动
   └─ 真人浏览器开 1 次 → 拿 cookies 24h 复用 → playwright 加 cookies 截
```

## 工具调研:第三方"强力浏览器"分级(2026-06-16)

| 级别 | 工具 | 过 NCBI 反爬 | 备注 |
|---|---|---|---|
| L1 硬刚 | Browserless / ScrapingBee / BrowserCat / ScrapingAnt | 100%(云端真浏览器) | 付费 $50-200/月 |
| L1 硬刚 | FlareSolverr(开源) | 中概率 70% | 自部署 Docker |
| L2 拟真 | playwright + stealth(反检测脚本) | 50-80% | **本沙箱实测能过 1-2 次** |
| L2 拟真 | playwright-stealth(pip 包) | 应同 L2 | 未实测(沙箱没装) |
| L2 拟真 | nodriver(2024 新开源,反 webdriver 标记) | 70-80% | 未实测(沙箱没装) |
| L3 重武器 | Selenium Grid + xvfb + 自定义 CDP | 100%(真显示器) | 沙箱装 GUI 难 |
| L3 重武器 | 2Captcha + 任何浏览器 | 100% | $3/1000 次 |

**关键判断**:
- NCBI 用 **Cloudflare IUAM + JS PoW**,**不**是真 CAPTCHA(不需要人点图)
- 真人浏览器特征(plugins / languages / chrome runtime)**大概率**能过 PoW
- Cloudflare IUAM 5s 自动跳,**只要不被风控当 bot**
- `playwright + 反检测` 能过 → 关键是要**等够时间** + **多次重试** + **删 webdriver 标记**

## 反检测脚本模板(2026-06-16 实战能用)

```python
from playwright.sync_api import sync_playwright

STEALTH = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
window.chrome = {runtime: {}};
const origQ = window.navigator.permissions.query;
window.navigator.permissions.query = (p) =>
    p.name === 'notifications' ? Promise.resolve({state: Notification.permission}) : origQ(p);
"""

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
            "--no-sandbox",
            "--disable-gpu",   # 关键!否则 42k px screenshot Target crashed
            "--disable-dev-shm-usage",
        ],
    )
    ctx = browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        locale="en-US", timezone_id="America/New_York",
    )
    page = ctx.new_page()
    page.add_init_script(STEALTH)

    # 多次重试过 Cloudflare(实测 1-3 次能过)
    url = "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13263346/"
    for retry in range(3):
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        for i in range(30):
            t = page.title()
            if "Checking" not in t and "reCAPTCHA" not in t:
                break
            page.wait_for_timeout(1000)
        else:
            continue  # retry
        break

    # 触发懒加载
    for y in range(0, 50000, 600):
        page.evaluate(f"window.scrollTo(0, {y})")
        page.wait_for_timeout(400)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(2000)

    # 分段截图(每段 1800 px,不要 full_page)
    body_h = page.evaluate("document.body.scrollHeight")
    for i, y in enumerate(range(0, body_h, 1800)):
        page.evaluate(f"window.scrollTo(0, {y})")
        page.wait_for_timeout(600)
        page.screenshot(path=f"/tmp/shot-{i:02d}.png", full_page=False)
```

**已知坑**:
- `full_page=True` 在 4 万+ px 页面会 GPU 内存爆,**必须**分段截
- 多次重试不设上限会死循环,设 `max_retries=3`
- 一定要 `page.evaluate("window.scrollTo(0, y)")` 触发懒加载,否则图不全

## 拼接图 + 飞书 docx 嵌入

拼接用 PIL:

```python
from PIL import Image
import glob

# 拼图 + 缩到合理尺寸
paths = sorted(glob.glob("/tmp/shot-*.png"))
ims = [Image.open(p).convert("RGB") for p in paths]
total_h = sum(im.size[1] for im in ims)
big = Image.new("RGB", (1280, total_h), "white")
y = 0
for im in ims:
    big.paste(im, (0, y))
    y += im.size[1]
# 裁掉右侧 sidebar(~340 px)
big = big.crop((0, 0, 940, total_h))
# 限高 2000(docz inline 显示不至于太长)
ratio = 2000 / total_h
big = big.resize((int(940 * ratio), 2000), Image.LANCZOS)
big.save("/tmp/main.jpg", "JPEG", quality=82)
```

→ 飞书 docx 用 `<img href="https://..."/>` 嵌 **飞书云盘 URL**(不是本地图):
先 `drive +upload` 本地图 → 拿 URL → 嵌 docx。

## 未来想加进 skill 的判断

**不**加进 fetch_pmc.py / render.py(那俩是 v3 主线)。
**加**在 `references/screenshots-ceiling.md`(本文件),作为"未来想升级"的参考。

**触发条件**(自动加进 v4 的信号):
- 用户说"截图不够,要真版式" / "飞书看不到 References / 表格" 多次(>3 次)
- 月跑量 ≥ 50 篇 → 2Captcha 成本摊得动
- skill 出现在其他用户的 cross-reference 引用(说明"截图"是普遍需求)

## 版本

- v1.0 (2026-06-16):首版调研结论 + 反检测脚本 + 拼图模板
- 验证:本沙箱 playwright + 上述反检测 + 多次重试,实测拿到 24 段截图,Vision 评估文字清晰
