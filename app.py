import os
import time
import tempfile
from PIL import Image
import img2pdf
import streamlit as st

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

st.set_page_config(
    page_title="FLBook & 云展网转 PDF 工具", page_icon="📚", layout="centered"
)

st.title("📚 FLBook & 云展网电子书转 PDF 工具")
st.markdown("输入正确的电子书链接，使用 **无头浏览器高清视口截图引擎** 完美保留图文并生成 PDF！")

url = st.text_input("请输入电子书网址 (URL):", "https://book.yunzhan365.com/yhqej/uiqj/mobile/index.html")
total_pages = st.number_input("图书总页数:", min_value=1, max_value=500, value=30)

if st.button("开始高清截图转换并生成 PDF", type="primary", use_container_width=True):
  if not url:
    st.warning("请输入有效的网址！")
  else:
    with st.status("正在进行高清截图渲染...", expanded=True) as status:
      st.write("1. 正在初始化系统原生 Chromium...")
      
      image_files = []

      try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        # 设置标准手机高清视口尺寸，确保截图极其清晰
        chrome_options.add_argument("--window-size=800,1200")
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
        )

        chrome_options.binary_location = "/usr/bin/chromium"
        service = Service("/usr/bin/chromedriver")
        
        driver = webdriver.Chrome(service=service, options=chrome_options)

        st.write("2. 正在打开网页并等待初始化...")
        driver.get(url)
        time.sleep(5)  # 等待首屏加载

        st.write(f"3. 正在逐页翻页并进行高清截图（共 {total_pages} 页）...")
        progress_bar = st.progress(0)

        with tempfile.TemporaryDirectory() as tmpdir:
          for i in range(int(total_pages)):
            # 留出当前页文字和图层的渲染时间
            time.sleep(0.8)

            # 核心：直接对当前视口进行高清截图保存！
            screenshot_path = os.path.join(tmpdir, f"page_{i+1:03d}.png")
            driver.save_screenshot(screenshot_path)

            # 转换格式并压缩为高质量 JPEG
            img_rgb = Image.open(screenshot_path).convert("RGB")
            jpg_path = os.path.join(tmpdir, f"page_{i+1:03d}.jpg")
            img_rgb.save(jpg_path, "JPEG", quality=95)
            image_files.append(jpg_path)

            st.write(f"✓ 已成功截取并保存第 {i+1} 页（含图文）")
            progress_bar.progress(min((i + 1) / total_pages, 1.0))

            # 通过纯 JS 翻到下一页
            driver.execute_script("""
                var event = new KeyboardEvent('keydown', {
                    key: 'ArrowRight',
                    code: 'ArrowRight',
                    keyCode: 39,
                    which: 39,
                    bubbles: true
                });
                document.dispatchEvent(event);
            """)

          time.sleep(1.5)
          driver.quit()

          if not image_files:
            status.update(label="截图失败", state="error")
            st.error("未能截取到任何页面图像。")
            st.stop()

          st.write(f"4. 成功完成所有页面截图，正在合成为完整 PDF...")
          output_pdf = os.path.join(tmpdir, "yunzhan_book.pdf")

          with open(output_pdf, "wb") as f:
            f.write(img2pdf.convert(image_files))

          with open(output_pdf, "rb") as f:
            pdf_bytes = f.read()

        status.update(label="转换成功！", state="complete")

    st.success(f"🎉 电子书已成功转换为高清晰度图文 PDF（共 {len(image_files)} 页）！")
    st.download_button(
        label="📥 点击下载生成的完整 PDF 文件",
        data=pdf_bytes,
        file_name="yunzhan_book.pdf",
        mime="application/pdf",
        use_container_width=True
    )
