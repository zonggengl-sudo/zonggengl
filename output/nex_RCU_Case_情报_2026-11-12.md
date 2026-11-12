# Nex Playground「Remote Control Case / RCU Case」情报（2026-11-12）

> 数据来源：线上 sitemap URL 集合 diff + 89 页本地快照 + 5 个商城页直连抓取。纯本地，免 Apify Key。

## 1. 发现

- 线上 sitemap 1067 → **1072（+5）**，新增 5 条全部指向 `/shop/playground-rcu-case`：主站 + `en-ca` / `en-gb` / `en-ie` / `fr-ca` 四个本地化商城页，删除 0 条。
- 主站页已被 `crawl_nex_site.py` 纳入营销页清单（88 → **89 页**），标题 `Nex Playground | Remote Control Case`。
- 4 个 locale 页仍被营销页过滤规则排除（爬虫盲区，沿用 11-09 处置），本晚单独直连抓取。
- 全站 88 页同步出现 `Find Stores Merch` → `Remote Case Find Stores`（导航新增入口），每页 +6 字符 —— 属模板噪声，非内容重写。

## 2. 主站页文案（本地快照全文）

```
Please note: Nex Playground Remote not included. This case will only fit the latest version of the Nex Remote Control.
Keep your Nex Playground Remote protected with a lightweight case made from eco-friendly polymer. The secure fit helps prevent bumps and scratches, while the strap makes it easy to grab and bring along—whether you’re traveling, tidying up, or adding a tracker tag.
Nex Playground Remote not included.
BUY Shipping & Delivery Estimated delivery time is 3 business days (Express Shipping) and 6 business days (Standard Shipping).We only ship to addresses in the United States at the moment.Change your mind? Enjoy hassle-free returns within 30 days of delivery. Product Specs Case: 135.5 x 32 x 20mmWrist Strap: 180 x 6.5mmGross Weight 28.5gNet Weight 19g Move with us. Sign up for our newsletter to get all the latest news and updates from Nex.
[H3] Play
[H3] Help
[H3] Company
[H3] Socials
🇺🇸 United States Select your country or region
🇺🇸 United States🇨🇦 Canada EnglishFrançais🇬🇧 United Kingdom🇮🇪 Ireland © 2026 Nex Team Inc. All rights reserved.
NEX Store Playground Play Pass Travel Case Remote Remote Case Find Stores Quiet Basketball Your cart Your cart is empty
```

## 3. 5 个商城页直连抓取

> ⚠️ 竞品 title 含管道符 `XXX | Nex Playground`，写表格前已按 10-11 增补做 `split("|")[0]` 剥离，否则会撑破列。

| locale | HTTP | 字节 | 标题（剥离管道符后） | 价格命中 | 加购按钮 | 售罄 |
|---|---|---|---|---|---|---|
| 主站 | 200 | 102667 | Nex Playground | $17.97 | 是 | — |
| en-ca | 200 | 92091 | Nex Playground | $26 | 是 | — |
| en-gb | 200 | 91247 | Nex Playground | US$17.97 | 是 | — |
| en-ie | 200 | 91226 | Nex Playground | US$17.97 | 是 | — |
| fr-ca | 200 | 96874 | Nex Playground | — | — | — |

**分市场定价 / 页面配置**：

| 市场 | 页面 | 价格 | 加购 | 观察 |
|---|---|---|---|---|
| 美国（主站） | `/shop/playground-rcu-case` | **US$17.97** | ✅ | 基准价 |
| 加拿大英语 | `/en-ca/…` | **$26**（≈CA$26） | ✅ | 已本地币种 |
| 英国 | `/en-gb/…` | `US$17.97` | ✅ | 仍用美元，未本地化 |
| 爱尔兰 | `/en-ie/…` | `US$17.97` | ✅ | 仍用美元 |
| 加拿大法语 | `/fr-ca/…` | 未命中 | ❌ | 加购按钮缺失，页面似未配置完整 |

→ 结论：竞品新 SKU 默认铺多语言商城页，但**币种与结算本地化尚未跟上**（GB/IE 仍显示 US$，fr-ca 未配置加购）。这是国际化推进中的可执行缺口，也说明其海外上架流程仍偏「页面先行、交易后补」。

## 4. 研判

- **硬件周边矩阵继续扩**：此前已有 `Travel Case`（旅行收纳箱）、`Playground Remote`（遥控器）、`Quiet Basketball`（静音篮球）、`shop/quiet-basketball`；本晚上线 `Remote Control Case`（遥控器保护/收纳壳），SKU 从主机大件向小配件、低客单价延伸。
- **国际化从「定价」推进到「商城 SKU」**：11-09 上线 CA$ 加拿大定价 + UK/IE/CA 本地化页 + 英国 5 站巡展；本晚新配件一次性铺 4 个 locale 商城页（en-ca / fr-ca / en-gb / en-ie），说明新增 SKU 默认按多市场上架，而非先美国后外扩。
- **导航权重提升**：全站页脚/导航把 `Merch` 换成 `Remote Case` 独立入口，说明竞品把配件当作一条正式产品线运营，不是隐藏 SKU。
- **对我方启示**：竞品正围绕「主机 + 订阅 + 配件」搭建实体商品矩阵，配件类长尾内容（保护壳 / 收纳 / 配件兼容性 / 选购指南）目前仍是我方内容缺口；可评估提前布局配件类 SEO 与博客选题，避开其强 IP 内容正面竞争。

## 5. 待办

- 4 个 locale 页若需进飞书留档，需扩展 `crawl_nex_site.py` 的 URL 过滤白名单（本晚未擅自改爬虫）。
- 飞书恢复授权后，`--apply --refresh` 会新增 1 条 RCU Case 记录并刷新 88 条导航模板文案。

