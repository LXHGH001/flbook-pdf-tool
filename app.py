import os
import time
import tempfile
import hashlib
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
st.markdown("使用 **视口渲染 + 智能点击激活 + MD5 查重防护引擎**，完美生成出版级 PDF！")

url = st.text_input("请输入电子书网址 (URL):", "https://book.yunzhan365.com/rsfdc/zmgw/mobile/index.html")
total_pages = st.number_input("预估图书总页数 (支持智能查重自动停止):", min_value=1, max_value=500, value=60)

if st.button("开始智能转换并生成 PDF", type="primary", use_container_width=True):
    if not url:
        st.warning("请输入有效的网址！")
    else:
        pdf_bytes = None

        with st.status("正在进行智能高清渲染与查重采集...", expanded=True) as status:
            st.write("1. 正在初始化无头浏览器...")

            try:
                chrome_options = Options()
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-gpu")
                # 移动端竖屏视口
                chrome_options.add_argument("--window-size=600,1100")
                chrome_options.add_argument("--force-device-scale-factor=2")
                chrome_options.add_argument(
                    "user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
                )

                chrome_options.binary_location = "/usr/bin/chromium"
                service = Service("/usr/bin/chromedriver")
                
                driver = webdriver.Chrome(service=service, options=chrome_options)

                st.write("2. 正在打开网页并执行首屏激活点击...")
                driver.get(url)
                time.sleep(7)  # 等待完全加载

                # 强行点开封面：模拟点击屏幕右侧或正中央，唤醒翻页控件
                driver.execute_script("""
                    try {
                        // 寻找封面上的开始按钮并点击
                        var btn = document.querySelector('.start-read, .enter-btn, .read-btn, .book-cover');
                        if (btn) { btn.click(); }
                        
                        // 在右侧边缘触发点击以进入正文
                        var clickRight = new MouseEvent('click', {
                            bubbles: true, cancelable: true,
                            clientX: window.innerWidth * 0.85,
                            clientY: window.innerHeight / 2
                        });
                        document.body.dispatchEvent(clickRight);
                    } catch(e) {}
                """)
                time.sleep(3)

                st.write(f"3. 正在逐页采集并进行 MD5 查重校验（上限 {int(total_pages)} 页）...")
                progress_bar = st.progress(0)

                with tempfile.TemporaryDirectory() as tmpdir:
                    valid_images = []
                    seen_hashes = set()
                    consecutive_duplicates = 0

                    for i in range(1, int(total_pages) + 1):
                        # 如果不是第一页，执行翻页
                        if i > 1:
                            driver.execute_script("""
                                try {
                                    // 1. 调用云展网自带翻页函数
                                    if (window.book && window.book.next) { window.book.next(); }
                                    else if (window.turn && window.turn.next) { window.turn.next(); }
                                    else {
                                        // 2. 模拟点击右侧翻页区
                                        var clickEvent = new MouseEvent('click', {
                                            bubbles: true, cancelable: true,
                                            clientX: window.innerWidth * 0.9,
                                            clientY: window.innerHeight / 2
                                        });
                                        document.body.dispatchEvent(clickEvent);
                                        
                                        // 3. 辅助键盘右键
                                        var kb = new KeyboardEvent('keydown', {key: 'ArrowRight', keyCode: 39, bubbles: true});
                                        document.dispatchEvent(kb);
                                    }
                                } catch(e) {}
                            """)
                            time.sleep(1.2)  # 等待翻页动画完成

                        # 截图前滚动归零
                        driver.execute_script("window.scrollTo(0, 0);")
                        time.sleep(0.3)

                        screenshot_path = os.path.join(tmpdir, f"page_{i:03d}.png")
                        driver.save_screenshot(screenshot_path)

                        # 计算 MD5 Hash，检测是否重复卡在封面
                        with open(screenshot_path, "rb") as f:
                            file_hash = hashlib.md5(f.read()).hexdigest()

                        if file_hash in seen_hashes:
                            consecutive_duplicates += 1
                            # 如果连续 3 页内容和前面完全一样，说明书已经读完了或者卡住了，安全退出
                            if consecutive_duplicates >= 3:
                                st.write(f"-> 检测到已到达书本末尾（连续重复），停止采集，共获得 {len(valid_images)} 页。")
                                os.remove(screenshot_path)
                                break
                        else:
                            consecutive_duplicates = 0
                            seen_hashes.add(file_hash)

                            # 保存高质量 JPG
                            img = Image.open(screenshot_path).convert("RGB")
                            jpg_path = os.path.join(tmpdir, f"page_{i:03d}.jpg")
                            img.save(jpg_path, "JPEG", quality=98, subsampling=0)
                            valid_images.append(jpg_path)

                            st.write(f"✓ 成功捕获并校验第 {i} 页")
                            progress_bar.progress(min(i / total_pages, 1.0))

                    driver.quit()

                    if not valid_images:
                        status.update(label="采集失败", state="error")
                        st.error("未能采集到任何有效页面图像。")
                        st.stop()

                    st.write("4. 校验完成，正在合成为出版级 PDF...")
                    output_pdf = os.path.join(tmpdir, "yunzhan_book.pdf")
                    with open(output_pdf, "wb") as f:
                        f.write(img2pdf.convert(valid_images))
                    with open(output_pdf, "rb") as f:
                        pdf_bytes = f.read()

                status.update(label="转换成功！", state="complete")

            except Exception as e:
                status.update(label="运行出错", state="error")
                st.error(f"详细错误: {e}")
                st.stop()

        if pdf_bytes:
            st.success(f"🎉 电子书已成功转换为高清 PDF（共 {len(valid_images)} 页）！")
            st.download_button(
                label="📥 点击下载生成的完整出版级 PDF 文件",
                data=pdf_bytes,
                file_name="yunzhan_book_verified.pdf",
                mime="application/pdf",
                use_container_width=True
            )
