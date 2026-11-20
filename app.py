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
st.markdown("输入任意电子书链接，使用 **全自动交互防卡死翻页引擎** 生成出版级 PDF！")

# 默认填入你新换的网址，或允许你随时更换
url = st.text_input("请输入电子书网址 (URL):", "https://book.yunzhan365.com/yhqej/uiqj/mobile/index.html")
total_pages = st.number_input("预估图书总页数 (支持智能到底自动结束):", min_value=1, max_value=500, value=50)

if st.button("开始全自动高清转换并生成 PDF", type="primary", use_container_width=True):
    if not url:
        st.warning("请输入有效的网址！")
    else:
        image_files = []
        pdf_bytes = None

        with st.status("正在进行全自动高清渲染...", expanded=True) as status:
            st.write("1. 正在初始化交互式视口浏览器...")

            try:
                chrome_options = Options()
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-gpu")
                chrome_options.add_argument("--window-size=600,1100")
                chrome_options.add_argument("--force-device-scale-factor=2")
                chrome_options.add_argument(
                    "user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
                )

                chrome_options.binary_location = "/usr/bin/chromium"
                service = Service("/usr/bin/chromedriver")
                
                driver = webdriver.Chrome(service=service, options=chrome_options)

                st.write("2. 正在打开网页并执行首屏交互点击（跳过封面卡顿）...")
                driver.get(url)
                time.sleep(6)  # 等待首屏加载

                # 核心：模拟一次屏幕中央或右侧点击，用来点掉封面的“进入/阅读”按钮
                driver.execute_script("""
                    // 触发全屏点击以唤醒图书交互
                    var clickEvent = new MouseEvent('click', {
                        view: window,
                        bubbles: true,
                        cancelable: true,
                        clientX: window.innerWidth / 2,
                        clientY: window.innerHeight / 2
                    });
                    document.body.dispatchEvent(clickEvent);
                """)
                time.sleep(2)

                st.write(f"3. 正在逐页多维触发翻页与防漂移高清截图（上限 {int(total_pages)} 页）...")
                progress_bar = st.progress(0)

                with tempfile.TemporaryDirectory() as tmpdir:
                    last_screenshot_size = 0
                    consecutive_same_pages = 0

                    for i in range(int(total_pages)):
                        if i > 0:
                            # 多维组合翻页：同时触发键盘右键、点击屏幕右侧、以及模拟向左滑动
                            driver.execute_script("""
                                // 1. 键盘右键
                                var kbEvent = new KeyboardEvent('keydown', {
                                    key: 'ArrowRight', code: 'ArrowRight', keyCode: 39, which: 39, bubbles: true
                                });
                                document.dispatchEvent(kbEvent);

                                // 2. 点击右侧边缘
                                var clickRight = new MouseEvent('click', {
                                    bubbles: true, clientX: window.innerWidth * 0.85, clientY: window.innerHeight / 2
                                });
                                document.body.dispatchEvent(clickRight);
                            """)
                            time.sleep(1.0)  # 给予充足的翻页动画时间

                        # 每次截图前强制视口归零，防止漂移
                        driver.execute_script("window.scrollTo(0, 0);")
                        time.sleep(0.3)

                        # 截取当前单页
                        screenshot_path = os.path.join(tmpdir, f"page_{i+1:03d}.png")
                        driver.save_screenshot(screenshot_path)

                        # 智能去重到底检测
                        current_size = os.path.getsize(screenshot_path)
                        if i > 0 and current_size == last_screenshot_size:
                            consecutive_same_pages += 1
                            if consecutive_same_pages >= 3: # 连续3页完全一样才判定到底
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

                        st.write(f"✓ 已成功捕获第 {i+1} 页")
                        progress_bar.progress(min((i + 1) / total_pages, 1.0))

                    driver.quit()

                    if not image_files:
                        status.update(label="截图失败", state="error")
                        st.error("未能截取到任何页面图像。")
                        st.stop()

                    st.write("4. 成功完成所有页面截图，正在合成为完整 PDF...")
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
            st.success(f"🎉 电子书已成功转换为全自动高清 PDF（共 {len(image_files)} 页）！")
            st.download_button(
                label="📥 点击下载生成的完整出版级 PDF 文件",
                data=pdf_bytes,
                file_name="yunzhan_book_hd.pdf",
                mime="application/pdf",
                use_container_width=True
            )
