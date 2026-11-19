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

st.set_page_config(
    page_title="FLBook & 云展网转 PDF 工具", page_icon="📚", layout="centered"
)

st.title("📚 FLBook & 云展网电子书转 PDF 工具")
st.markdown("输入正确的电子书链接，使用 **系统原生 Chromium 浏览器内核** 完美渲染并生成 PDF！")

url = st.text_input("请输入电子书网址 (URL):", "https://book.yunzhan365.com/yhqej/uiqj/mobile/index.html")
total_pages = st.number_input("预估图书总页数:", min_value=1, max_value=500, value=30)

if st.button("启动系统浏览器内核渲染并生成 PDF", type="primary", use_container_width=True):
  if not url:
    st.warning("请输入有效的网址！")
  else:
    with st.status("正在通过系统 Chromium 渲染...", expanded=True) as status:
      st.write("1. 正在初始化系统原生 Chromium...")
      
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

        chrome_options.binary_location = "/usr/bin/chromium"
        service = Service("/usr/bin/chromedriver")
        
        driver = webdriver.Chrome(service=service, options=chrome_options)

        st.write("2. 正在打开网页并建立会话...")
        driver.get(url)
        time.sleep(5)  # 等待 JS 动态加载

        st.write(f"3. 正在通过纯 JS 触发模拟翻页并收集图片（共 {total_pages} 页）...")
        progress_bar = st.progress(0)

        for i in range(int(total_pages)):
          # 纯 JS 触发翻页键
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

          time.sleep(0.7)  # 留出图片渲染时间
          
          # 核心修复：通过安全 JS 直接获取当前页面所有图片的 src 字符串列表，彻底杜绝 stale element 错误！
          current_page_srcs = driver.execute_script("""
              var srcs = [];
              var imgs = document.getElementsByTagName('img');
              for (var j = 0; j < imgs.length; j++) {
                  if (imgs[j].src) {
                      srcs.push(imgs[j].src);
                  }
              }
              return srcs;
          """)

          for src in current_page_srcs:
              if src and src not in image_urls_captured:
                  if any(k in src.lower() for k in ["mobile", "files", "page", "ext", "yhqej"]):
                      image_urls_captured.append(src)

          progress_bar.progress(min((i + 1) / total_pages, 1.0))

        time.sleep(2)
        
        # 最终兜底全盘扫描一次
        final_srcs = driver.execute_script("""
            var srcs = [];
            var imgs = document.getElementsByTagName('img');
            for (var j = 0; j < imgs.length; j++) {
                if (imgs[j].src) {
                    srcs.push(imgs[j].src);
                }
            }
            return srcs;
        """)
        for src in final_srcs:
            if src and src not in image_urls_captured:
                image_urls_captured.append(src)

        driver.quit()

      except Exception as e:
        status.update(label="浏览器渲染失败", state="error")
        st.error(f"详细错误: {e}")
        st.stop()

      st.write(f"4. 捕获到 {len(image_urls_captured)} 个图片资源，开始下载...")

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
