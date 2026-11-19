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
st.markdown("输入正确的电子书链接，使用 **防漂移单页锁定引擎** 生成完美的出版级 PDF！")

url = st.text_input("请输入电子书网址 (URL):", "https://book.yunzhan365.com/yhqej/uiqj/mobile/index.html")
total_pages = st.number_input("预估图书总页数 (支持智能到底自动结束):", min_value=1, max_value=500, value=30)

if st.button("开始防漂移高清转换并生成 PDF", type="primary", use_container_width=True):
    if not url:
        st.warning("请输入有效的网址！")
    else:
        image_files = []
        pdf_bytes = None

        with st.status("正在进行防漂移高清渲染...", expanded=True) as status:
            st.write("1. 正在初始化防漂移单页视口浏览器...")

            try:
                chrome_options = Options()
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-gpu")
                # 核心修正：采用更极端的竖屏长条比例 (600x1100) + 2倍 Retina 像素比，彻底锁死单页
                chrome_options.add_argument("--window-size=600,1100")
                chrome_options.add_argument("--force-device-scale-factor=2")
                chrome_options.add_argument(
                    "user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
                )

                chrome_options.binary_location = "/usr/bin/chromium"
                service = Service("/usr/bin/chromedriver")
                
                driver = webdriver.Chrome(service=service, options=chrome_options)

                st.write("2. 正在打开网页并加载图书...")
                driver.get(url)
                time.sleep(5)  # 等待首屏加载

                # 强制单页模式与横向滚动锁定
                driver.execute_script("""
                    try {
                        if (typeof switchViewMode === 'function') { switchViewMode('single'); }
                        if (window.bookConfig) { window.bookConfig.singlePage = true; window.bookConfig.isDouble = false; }
                    } catch(e) {}
                """)
                time.sleep(1)

                st.write(f"3. 正在逐页防漂移高清截图（上限 {int(total_pages)} 页，支持智能到底）...")
                progress_bar = st.progress(0)

                with tempfile.TemporaryDirectory() as tmpdir:
                    last_screenshot_size = 0
                    consecutive_same_pages = 0

                    for i in range(int(total_pages)):
                        if i > 0:
                            # 触发向右翻页
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
                            time.sleep(0.8)

                        # 核心防漂移：每次截图前，强制将页面横向和纵向滚动条归零，彻底防止画面向右偏移！
                        driver.execute_script("window.scrollTo(0, 0);")
                        time.sleep(0.3)  # 留出归零渲染缓冲

                        # 截取当前单页
                        screenshot_path = os.path.join(tmpdir, f"page_{i+1:03d}.png")
                        driver.save_screenshot(screenshot_path)

                        # 智能去重到底检测
                        current_size = os.path.getsize(screenshot_path)
                        if i > 0 and current_size == last_screenshot_size:
                            consecutive_same_pages += 1
                            if consecutive_same_pages >= 2:
                                st.write(f"-> 检测到已到达书本末尾，提前结束截取（共 {i} 页）。")
                                os.remove(screenshot_path)
                                break
                        else:
                            consecutive_same_pages = 0

                        last_screenshot_size = current_size

                        # 无损高画质转换
                        img = Image.open(screenshot_path)
                        img_rgb = img.convert("RGB")
                        
                        jpg_path = os.path.join(tmpdir, f"page_{i+1:03d}.jpg")
                        img_rgb.save(jpg_path, "JPEG", quality=98, subsampling=0)
                        image_files.append(jpg_path)

                        st.write(f"✓ 已完美锁定并生成第 {i+1} 页单页高清图")
                        progress_bar.progress(min((i + 1) / total_pages, 1.0))

                    driver.quit()

                    if not image_files:
                        status.update(label="截图失败", state="error")
                        st.error("未能截取到任何页面图像。")
                        st.stop()

                    st.write("4. 成功完成所有防漂移截图，正在极速合成为 PDF...")
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
            st.success(f"🎉 电子书已成功转换为防漂移单页高清 PDF（共 {len(image_files)} 页）！")
            st.download_button(
                label="📥 点击下载生成的完整出版级 PDF 文件",
                data=pdf_bytes,
                file_name="yunzhan_book_hd.pdf",
                mime="application/pdf",
                use_container_width=True
            )
