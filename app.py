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
st.markdown("输入正确的电子书链接，使用 **2倍超高清视口 + 强制单页渲染引擎** 获得极致清晰的图文 PDF！")

url = st.text_input("请输入电子书网址 (URL):", "https://book.yunzhan365.com/yhqej/uiqj/mobile/index.html")
total_pages = st.number_input("图书总页数:", min_value=1, max_value=500, value=30)

if st.button("开始超高清单页转换并生成 PDF", type="primary", use_container_width=True):
    if not url:
        st.warning("请输入有效的网址！")
    else:
        image_files = []
        pdf_bytes = None

        with st.status("正在进行超高清单页渲染...", expanded=True) as status:
            st.write("1. 正在初始化 2倍超高清视口浏览器...")

            try:
                chrome_options = Options()
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-gpu")
                # 核心：使用超大高清分辨率 (1200x1800)，保证文字极度清晰
                chrome_options.add_argument("--window-size=1200,1800")
                chrome_options.add_argument(
                    "user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
                )

                chrome_options.binary_location = "/usr/bin/chromium"
                service = Service("/usr/bin/chromedriver")
                
                driver = webdriver.Chrome(service=service, options=chrome_options)

                st.write("2. 正在打开网页并强制注入单页显示模式...")
                driver.get(url)
                time.sleep(5)  # 等待首屏加载

                # 核心：通过 JS 强行将云展网的视图切换为单页模式，并放大画布
                driver.execute_script("""
                    try {
                        // 尝试调用云展网内置的单页切换函数
                        if (typeof switchViewMode === 'function') { switchViewMode('single'); }
                        if (window.bookConfig) { window.bookConfig.singlePage = true; window.bookConfig.isDouble = false; }
                        
                        // 暴力修改 DOM：隐藏双页容器或调整宽度让其单页展示
                        var dualContainers = document.querySelectorAll('.double-page, .book-double');
                        dualContainers.forEach(el => el.style.display = 'none');
                        
                        var singleContainers = document.querySelectorAll('.single-page, .book-single');
                        singleContainers.forEach(el => el.style.display = 'block');
                    } catch(e) {}
                """)
                time.sleep(1)

                st.write(f"3. 正在逐页进行 2倍超高清单页截图（共 {int(total_pages)} 页）...")
                progress_bar = st.progress(0)

                with tempfile.TemporaryDirectory() as tmpdir:
                    for i in range(int(total_pages)):
                        time.sleep(0.9)  # 留出高清渲染时间

                        screenshot_path = os.path.join(tmpdir, f"page_{i+1:03d}.png")
                        driver.save_screenshot(screenshot_path)

                        # 使用高质量 PIL 转换，保持超高清晰度
                        img = Image.open(screenshot_path)
                        img_rgb = img.convert("RGB")
                        
                        jpg_path = os.path.join(tmpdir, f"page_{i+1:03d}.jpg")
                        img_rgb.save(jpg_path, "JPEG", quality=98, subsampling=0) # subsampling=0 保证文字边缘不发糊
                        image_files.append(jpg_path)

                        st.write(f"✓ 已成功截取超高清单页第 {i+1} 页")
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

                    st.write("4. 成功完成所有超高清单页截图，正在合成为精美 PDF...")
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
            st.success(f"🎉 电子书已成功转换为超高清单页 PDF（共 {len(image_files)} 页）！")
            st.download_button(
                label="📥 点击下载生成的完整 PDF 文件",
                data=pdf_bytes,
                file_name="yunzhan_book.pdf",
                mime="application/pdf",
                use_container_width=True
            )
