# Apify 抓取工具

夜间批处理用的 Apify Actor 编排层。当前环境**未配置 APIFY_API_TOKEN**，
抓取类任务会自动跳过；配置后无需改代码即可运行。

## 配置 Token

```bash
# 写入 ~/.zshrc（换成真实 token，Apify Console > Settings > Integrations）
export APIFY_API_TOKEN=apify_api_xxxxxxxxxxxxxxxx
```

## 用法

```bash
cd tools/apify
python3 run_actor.py --list          # 列出所有可用 target
python3 run_actor.py --check         # 验证 token + 列出账号下 Actor Task
python3 run_actor.py nex_meta_ads    # 跑 Meta 广告库
python3 run_actor.py nex_facebook_page
python3 run_actor.py nex_meta_ads '{"count":500}'   # 覆盖默认 input
```

## Target 一览

| target | Actor | 输出 |
|---|---|---|
| `nex_meta_ads` | `curious_coder/facebook-ads-library-scraper` | `data/nex_playground/meta_ads.json` |
| `nex_facebook_page` | `apify/facebook-pages-scraper` | `data/nex_playground/facebook_page.json` |
| `nex_independent_site` | 无需 Apify（Shopify 公开 JSON） | `data/nex_playground/products.json` |
| `tiktok_affiliate_creator` | `clockworks/free-tiktok-scraper` | `data/tiktok/affiliate_creators.json` |
| `facebook_creator_search` | `apify/facebook-pages-scraper` | `data/facebook/creators.json` |

## 不需要 Apify 的替代路径

- **独立站页面文案**：`tools/crawl_nex_site.py`（读 sitemap + 解析 HTML，已验证可用，83 页）
- **独立站商品**：`tools/fetch_shopify_site.py`（Shopify `/products.json`）
- **博客发布时间**：`tools/fetch_shopify_blog_dates.py`（JSON-LD `datePublished`）

## Meta 广告库说明

`facebook.com/ads/library` 是纯前端渲染，直接 HTTP 拉取只能拿到 "Ad Library" 空壳。
必须走 Apify Actor 或带浏览器渲染的抓取。已实测确认。

## 退出码

`0` 成功 | `2` 无 token | `3` target 不存在/无 actor | `4` 运行失败
