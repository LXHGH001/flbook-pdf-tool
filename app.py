import os
import time
import tempfile
from PIL import Image
import img2pdf
import requests
import streamlit as st
import asyncio

from playwright.async_api import async_playwright

st.set_page_config(
    page_title="FLBook & 云展网转 PDF 工具", page_icon="📚", layout="centered"
)

st.title("📚 FLBook & 云展网电子书转 PDF 工具")
st.markdown("输入正确的电子书链接，使用 **Playwright 真实浏览器内核** 完美渲染并生成 PDF！")

url = st.text_input("请输入电子书网址 (URL):", "https://book.yunzhan365.com/yhqej/uiqj/mobile/index.html")
total_pages = st.number_input("预估图书总页数 (测试时可填 3):", min_value=1, max_value=500, value=3)

async def scrape_book(target_url, pages):
    image_urls = []
    async with async_playwright() as p:
        # 启动无头浏览器
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            viewport={"width": 430, "height": 932}
        )
        page = await context.new_page()
        
        # 拦截所有网络请求，精准捕获图片 CDN 直链
        page.on("request", lambda req: image_urls.append(req.url) if any(k in req.url.lower() for k in [".jpg", ".png", "files/mobile", "ext/page"]) else None)

        await page.goto(target_url, timeout=60000)
        await page.wait_for_timeout(4000)

        # 模拟翻页触发加载
        for _ in range(int(pages)):
            await page.keyboard.press("ArrowRight")
            await page.wait_for_timeout(600)

        await browser.close()
    return image_urls

if st.button("启动真实浏览器内核渲染并生成 PDF", type="primary", use_container_width=True):
  if not url:
    st.warning("请输入有效的网址！")
  else:
    with st.status("正在通过 Playwright 浏览器渲染...", expanded=True) as status:
      st.write("1. 正在云端启动无头 Chromium 浏览器...")
      
      try:
          loop = asyncio.new_event_loop()
          asyncio.set_event_loop(loop)
          captured_links = loop.run_until_complete(scrape_book(url, total_pages))
      except Exception as e:
          status.update(label="浏览器渲染失败", state="error")
          st.error(f"详细错误: {e}")
          st.stop()

      st.write(f"2. 浏览器网络拦截成功，捕获到 {len(captured_links)} 个资源链接，正在筛选高清书页...")

      valid_img_urls = []
      for link in captured_links:
          if any(ext in link.lower() for ext in [".jpg", ".jpeg", ".png"]) and not any(ic in link.lower() for ic in ["icon", "logo", "avatar", "thumb"]):
              if link not in valid_img_urls:
                  valid_img_urls.append(link)

      st.write(f"-> 筛选出有效的高清书页图片共 {len(valid_img_urls)} 张，开始高速下载...")

      if not valid_img_urls:
          status.update(label="未捕获到图片", state="error")
          st.error("未能从浏览器拦截到有效书页图片。")
          st.stop()

      with tempfile.TemporaryDirectory() as tmpdir:
        image_files = []
        valid_count = 0

        for i, img_url in enumerate(valid_img_urls[:int(pages)*2] if 'pages' in locals() else valid_img_urls):
          try:
            r = requests.get(img_url, timeout=5)
            if r.status_code == 200 and len(r.content) > 3000:
              tmp_path = os.path.join(tmpdir, f"raw_{i}.jpg")
              with open(tmp_path, "wb") as f:
                f.write(r.content)

              img_rgb = Image.open(tmp_path).convert("RGB")
              file_path = os.path.join(tmpdir, f"page_{valid_count+1:03d}.jpg")
              img_rgb.save(file_path, "JPEG", quality=95)

              image_files.append(file_path)
              valid_count += 1
          except:
            pass

        if not image_files:
          status.update(label="下载失败", state="error")
          st.error("下载捕获到的图片时被拒绝。")
          st.stop()

        st.write(f"3. 成功整理 {len(image_files)} 页高清页面，正在合成为 PDF...")
        output_pdf = os.path.join(tmpdir, "yunzhan_book.pdf")

        with open(output_pdf, "wb") as f:
          f.write(img2pdf.convert(image_files))

        with open(output_pdf, "rb") as f:
          pdf_bytes = f.read()

        status.update(label="转换成功！", state="complete")

    st.success(f"🎉 电子书已成功转换为 PDF（共 {len(image_files)} 页）！")
    st.download_button(
        label="📥 点击下载生成的完整 PDF 文件",
        data=pdf_bytes,
        file_name="yunzhan_book.pdf",
        mime="application/pdf",
        use_container_width=True
    )
