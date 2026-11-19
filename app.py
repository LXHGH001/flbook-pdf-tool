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
st.markdown("输入正确的电子书链接，使用 **单页高清视口截图引擎** 完美呈现每一页的高清图文！")

url = st.text_input("请输入电子书网址 (URL):", "https://book.yunzhan365.com/yhqej/uiqj/mobile/index.html")
total_pages = st.number_input("图书总页数:", min_value=1, max_value=500, value=30)

if st.button("开始单页高清截图并生成 PDF", type="primary", use_container_width=True):
    if not url:
        st.warning("请输入有效的网址！")
    else:
        image_files = []
        pdf_bytes = None

        with st.status("正在进行单页高清渲染...", expanded=True) as status:
            st.write("1. 正在初始化单页高清视口浏览器...")

            try:
                chrome_options = Options()
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-gpu")
                # 核心：设置为标准的单页竖屏手机尺寸 (430x932)，强制云展网以单页大图模式渲染
                chrome_options.add_argument("--window-size=430,932")
                chrome_options.add_argument(
                    "user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
                )

                chrome_options.binary_location = "/usr/bin/chromium"
                service = Service("/usr/bin/chromedriver")
                
                driver = webdriver.Chrome(service=service, options=chrome_options)

                st.write("2. 正在打开网页并等待单页初始化...")
                driver.get(url)
                time.sleep(5)  # 等待首屏加载

                # 尝试通过 JS 强制云展网切换为单页模式（如果支持的话）
                try:
                    driver.execute_script("""
                        if (window.bookConfig) { window.bookConfig.singlePage = true; }
                        if (typeof switchViewMode === 'function') { switchViewMode('single'); }
                    """)
                except:
                    pass

                st.write(f"3. 正在逐页单页翻页并进行高清截图（共 {int(total_pages)} 页）...")
                progress_bar = st.progress(0)

                with tempfile.TemporaryDirectory() as tmpdir:
                    for i in range(int(total_pages)):
                        time.sleep(0.9)  # 留出单页高清渲染时间

                        screenshot_path = os.path.join(tmpdir, f"page_{i+1:03d}.png")
                        driver.save_screenshot(screenshot_path)

                        img_rgb = Image.open(screenshot_path).convert("RGB")
                        jpg_path = os.path.join(tmpdir, f"page_{i+1:03d}.jpg")
                        img_rgb.save(jpg_path, "JPEG", quality=95)
                        image_files.append(jpg_path)

                        st.write(f"✓ 已成功截取单页高清第 {i+1} 页")
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

                    time.sleep(1.5)
                    driver.quit()

                    if not image_files:
                        status.update(label="截图失败", state="error")
                        st.error("未能截取到任何页面图像。")
                        st.stop()

                    st.write("4. 成功完成所有单页高清截图，正在合成为精美 PDF...")
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
            st.success(f"🎉 电子书已成功转换为单页高清图文 PDF（共 {len(image_files)} 页）！")
            st.download_button(
                label="📥 点击下载生成的完整 PDF 文件",
                data=pdf_bytes,
                file_name="yunzhan_book.pdf",
                mime="application/pdf",
                use_container_width=True
            )
