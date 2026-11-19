import os
import time
import tempfile
from PIL import Image
import img2pdf
import requests
import streamlit as st

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys

st.set_page_config(
    page_title="FLBook & 云展网转 PDF 工具", page_icon="📚", layout="centered"
)

st.title("📚 FLBook & 云展网电子书转 PDF 工具")
st.markdown("输入正确的电子书链接，使用**无头浏览器内核**动态渲染并生成高质量 PDF！")

url = st.text_input("请输入电子书网址 (URL):", "https://book.yunzhan365.com/yhqej/uiqj/mobile/index.html")
total_pages = st.number_input("预估图书总页数 (测试时可填 3):", min_value=1, max_value=500, value=3)

if st.button("启动浏览器内核渲染并生成 PDF", type="primary", use_container_width=True):
  if not url:
    st.warning("请输入有效的网址！")
  else:
    with st.status("正在通过无头浏览器内核渲染...", expanded=True) as status:
      st.write("1. 正在初始化云端系统 Chromium 浏览器...")
      image_urls_captured = []

      try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=430,932")
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
        )

        # 直接调用 Streamlit 云端自带的 chromium
        chrome_options.binary_location = "/usr/bin/chromium"
        service = Service("/usr/bin/chromedriver")
        
        driver = webdriver.Chrome(service=service, options=chrome_options)

        st.write("2. 正在打开网页并等待动态加载...")
        driver.get(url)
        time.sleep(5)  # 等待 JS 加载

        st.write(f"3. 正在自动模拟翻页（共 {total_pages} 页）以触发高清图加载...")
        progress_bar = st.progress(0)
        body = driver.find_element("tag name", "body")

        for i in range(int(total_pages)):
          body.send_keys(Keys.ARROW_RIGHT)
          time.sleep(0.8)
          
          # 实时抓取页面中加载出的图片
          imgs = driver.find_elements("tag name", "img")
          for img in imgs:
              src = img.get_attribute("src")
              if src and src not in image_urls_captured:
                  if any(k in src.lower() for k in ["mobile", "files", "page", "ext", "yhqej"]):
                      image_urls_captured.append(src)

          progress_bar.progress(min((i + 1) / total_pages, 1.0))

        time.sleep(3)
        
        # 兜底再全盘扫描一次图片标签
        for img in driver.find_elements("tag name", "img"):
            src = img.get_attribute("src")
            if src and src not in image_urls_captured:
                image_urls_captured.append(src)

        driver.quit()

      except Exception as e:
        status.update(label="浏览器渲染失败", state="error")
        st.error(f"详细错误: {e}")
        st.stop()

      st.write(f"4. 浏览器成功捕获到 {len(image_urls_captured)} 个图片资源，开始下载...")

      if not image_urls_captured:
        status.update(label="未捕获到图片", state="error")
        st.error("未能从浏览器中捕获到有效书页。")
        st.stop()

      with tempfile.TemporaryDirectory() as tmpdir:
        image_files = []
        valid_count = 0

        for i, img_url in enumerate(image_urls_captured):
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
          st.error("下载图片时被服务器拒绝。")
          st.stop()

        st.write(f"5. 成功整理 {len(image_files)} 页，正在合成为 PDF...")
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
