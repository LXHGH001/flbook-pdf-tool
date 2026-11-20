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
st.markdown("输入任意电子书链接，使用 **全自动激活与深度渲染引擎** 生成出版级 PDF！")

url = st.text_input("请输入电子书网址 (URL):", "https://book.yunzhan365.com/yhqej/uiqj/mobile/index.html")
total_pages = st.number_input("预估图书总页数 (支持智能到底自动结束):", min_value=1, max_value=500, value=50)

if st.button("开始智能激活转换并生成 PDF", type="primary", use_container_width=True):
    if not url:
        st.warning("请输入有效的网址！")
    else:
        image_files = []
        pdf_bytes = None

        with st.status("正在进行智能激活与高清渲染...", expanded=True) as status:
            st.write("1. 正在初始化智能激活浏览器...")

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

                st.write("2. 正在打开网页并执行深度激活（跳过封面锁定）...")
                driver.get(url)
                time.sleep(8)  # 给予充足时间让云展网完成重型 JS 加载

                # 核心突破：强行点击封面或唤醒正文渲染
                driver.execute_script("""
                    try {
                        // 1. 尝试调用所有可能的翻页和初始化函数
                        if (typeof window.nextPage === 'function') { window.nextPage(); }
                        if (window.book && typeof window.book.next === 'function') { window.book.next(); }
                        
                        // 2. 强行点击页面上的封面、开始按钮、中央区域
                        var targets = document.querySelectorAll('div, button, a, span');
                        for (var t of targets) {
                            var cls = (t.className || '').toLowerCase();
                            var txt = (t.innerText || '').toLowerCase();
                            if (cls.includes('cover') || cls.includes('start') || cls.includes('enter') || cls.includes('read') || txt.includes('点击') || txt.includes('开始')) {
                                t.click();
                            }
                        }
                        
                        // 3. 在屏幕正中央模拟一次点击
                        var centerX = window.innerWidth / 2;
                        var centerY = window.innerHeight / 2;
                        var mClick = new MouseEvent('click', {
                            bubbles: true, cancelable: true, view: window,
                            clientX: centerX, clientY: centerY
                        });
                        document.body.dispatchEvent(mClick);
                    } catch(e) {}
                """)
                time.sleep(3)  # 等待正文从封面展开

                st.write(f"3. 正在逐页智能翻页与高清截图（上限 {int(total_pages)} 页）...")
                progress_bar = st.progress(0)

                with tempfile.TemporaryDirectory() as tmpdir:
                    last_screenshot_size = 0
                    consecutive_same_pages = 0

                    for i in range(int(total_pages)):
                        if i > 0:
                            # 核心：联合翻页组合拳（向右键 + 右侧点击 + 触控滑动 + API调用）
                            driver.execute_script("""
                                try {
                                    // 键盘右键
                                    var kb = new KeyboardEvent('keydown', {key: 'ArrowRight', code: 'ArrowRight', keyCode: 39, bubbles: true});
                                    document.dispatchEvent(kb);

                                    // 右侧点击
                                    var rightClick = new MouseEvent('click', {
                                        bubbles: true, cancelable: true,
                                        clientX: window.innerWidth * 0.85, clientY: window.innerHeight / 2
                                    });
                                    document.body.dispatchEvent(rightClick);

                                    // 触控左滑
                                    var tStart = new TouchEvent('touchstart', {bubbles: true, cancelable: true, touches: [{clientX: 500, clientY: 500}]});
                                    var tEnd = new TouchEvent('touchend', {bubbles: true, cancelable: true, changedTouches: [{clientX: 100, clientY: 500}]});
                                    document.body.dispatchEvent(tStart);
                                    document.body.dispatchEvent(tEnd);

                                    // 内核 API
                                    if (window.book && window.book.next) { window.book.next(); }
                                } catch(e) {}
                            """)
                            time.sleep(1.5)  # 给予充分的动画渲染缓冲时间

                        # 截图前强制视口归零
                        driver.execute_script("window.scrollTo(0, 0);")
                        time.sleep(0.4)

                        # 截取当前单页
                        screenshot_path = os.path.join(tmpdir, f"page_{i+1:03d}.png")
                        driver.save_screenshot(screenshot_path)

                        # 智能去重到底检测
                        current_size = os.path.getsize(screenshot_path)
                        if i > 0 and current_size == last_screenshot_size:
                            consecutive_same_pages += 1
                            if consecutive_same_pages >= 3:
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
            st.success(f"🎉 电子书已成功转换为智能激活高清 PDF（共 {len(image_files)} 页）！")
            st.download_button(
                label="📥 点击下载生成的完整出版级 PDF 文件",
                data=pdf_bytes,
                file_name="yunzhan_book_hd.pdf",
                mime="application/pdf",
                use_container_width=True
            )
