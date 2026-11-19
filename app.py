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
st.markdown("输入正确的电子书链接，使用 **2倍 Retina 超高清无损视口引擎** 完美呈现出版级图文！")

url = st.text_input("请输入电子书网址 (URL):", "https://book.yunzhan365.com/yhqej/uiqj/mobile/index.html")
total_pages = st.number_input("图书总页数:", min_value=1, max_value=500, value=30)

if st.button("开始 2倍 Retina 超高清转换并生成 PDF", type="primary", use_container_width=True):
    if not url:
        st.warning("请输入有效的网址！")
    else:
        image_files = []
        pdf_bytes = None

        with st.status("正在进行 2倍超高清无损渲染...", expanded=True) as status:
            st.write("1. 正在初始化 2倍 Retina 视口浏览器...")

            try:
                chrome_options = Options()
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-gpu")
                # 核心：设置超大视口尺寸 (1440x2160)，确保拥有充裕的物理像素
                chrome_options.add_argument("--window-size=1440,2160")
                # 核心：强制开启 2 倍设备像素比（Retina 级别），让文字和线条极度锐利
                chrome_options.add_argument("--force-device-scale-factor=2")
                chrome_options.add_argument(
                    "user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
                )

                chrome_options.binary_location = "/usr/bin/chromium"
                service = Service("/usr/bin/chromedriver")
                
                driver = webdriver.Chrome(service=service, options=chrome_options)

                st.write("2. 正在打开网页并等待高清首屏加载...")
                driver.get(url)
                time.sleep(6)  # 给予充足时间加载高清字体和矢量图层

                # 尝试通过 JS 强制云展网单页显示
                try:
                    driver.execute_script("""
                        if (typeof switchViewMode === 'function') { switchViewMode('single'); }
                        if (window.bookConfig) { window.bookConfig.singlePage = true; }
                    """)
                except:
                    pass
                time.sleep(1)

                st.write(f"3. 正在逐页进行 2倍 Retina 高清截图（共 {int(total_pages)} 页）...")
                progress_bar = st.progress(0)

                with tempfile.TemporaryDirectory() as tmpdir:
                    for i in range(int(total_pages)):
                        time.sleep(1.0)  # 留出高清图层完全渲染时间

                        # 保存为无损 PNG 格式，彻底保留所有字体边缘的细节
                        screenshot_path = os.path.join(tmpdir, f"page_{i+1:03d}.png")
                        driver.save_screenshot(screenshot_path)

                        # 直接以无损 RGB 格式打包进 PDF，绝不压缩文字
                        img = Image.open(screenshot_path)
                        img_rgb = img.convert("RGB")
                        
                        jpg_path = os.path.join(tmpdir, f"page_{i+1:03d}.jpg")
                        img_rgb.save(jpg_path, "JPEG", quality=100, subsampling=0)
                        image_files.append(jpg_path)

                        st.write(f"✓ 已成功生成 2倍高清第 {i+1} 页")
                        progress_bar.progress(min((i + 1) / total_pages, 1.0))

                        # 模拟向右翻单页
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

                    time.sleep(2.0)
                    driver.quit()

                    if not image_files:
                        status.update(label="截图失败", state="error")
                        st.error("未能截取到任何页面图像。")
                        st.stop()

                    st.write("4. 成功完成所有 2倍 Retina 截图，正在合成为出版级 PDF...")
                    output_pdf = os.path.join(tmpdir, "yunzhan_book.pdf")

                    with open(output_pdf, "wb") as f:
                        f.write(img2pdf.convert(image_files))

                    with open(output_pdf, "rb") as f:
                        pdf_bytes = f.read()

                status.update(label="转换成功！", state="complete")

            except Exception as e:
                status.update(label="运行出错", state="error")
                st.error(f"详细错误: {e}")
                st.stop()

        if pdf_bytes:
            st.success(f"🎉 电子书已成功转换为 2倍 Retina 超高清 PDF（共 {len(image_files)} 页）！")
            st.download_button(
                label="📥 点击下载生成的完整出版级 PDF 文件",
                data=pdf_bytes,
                file_name="yunzhan_book_hd.pdf",
                mime="application/pdf",
                use_container_width=True
            )
