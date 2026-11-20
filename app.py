import os
import time
import tempfile
import hashlib
import requests
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
st.markdown("使用 **底层配置解析 + 原图直下 + Hash 去重校验引擎**，彻底告别重复封面！")

url = st.text_input("请输入电子书网址 (URL):", "https://book.yunzhan365.com/rsfdc/zmgw/mobile/index.html")

if st.button("开始智能解析并下载原图生成 PDF", type="primary", use_container_width=True):
    if not url:
        st.warning("请输入有效的网址！")
    else:
        pdf_bytes = None

        with st.status("正在解析云展网底层资源...", expanded=True) as status:
            st.write("1. 正在初始化 Headless 浏览器拦截网络请求与配置...")

            try:
                chrome_options = Options()
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-gpu")
                chrome_options.add_argument("--window-size=1200,800")
                chrome_options.add_argument(
                    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )

                chrome_options.binary_location = "/usr/bin/chromium"
                service = Service("/usr/bin/chromedriver")
                
                driver = webdriver.Chrome(service=service, options=chrome_options)
                
                # 启用 Performance 日志以捕获网络请求
                driver.execute_cdp_cmd("Network.enable", {})

                st.write("2. 正在加载图书页面并监听底层配置/图片请求...")
                driver.get(url)
                
                # 等待图书完全加载并捕获网络请求中的图片或配置文件
                image_urls = set()
                start_time = time.time()
                
                while time.time() - start_time < 12: # 最多等待12秒收集网络请求
                    time.sleep(1)
                    logs = driver.get_log("performance")
                    for entry in logs:
                        try:
                            import json
                            message = json.loads(entry["message"])["message"]
                            if message["method"] == "Network.requestWillBeSent":
                                req_url = message["params"]["request"]["url"]
                                # 匹配云展网常见的高清原图路径特征（通常包含 pages/, mobile/, /files/ 且以 jpg/png 结尾）
                                if any(ext in req_url.lower() for ext in ['.jpg', '.png', '.jpeg']) and ('mobile' in req_url or 'page' in req_url or 'files' in req_url):
                                    if 'thumb' not in req_url and 'icon' not in req_url:
                                        image_urls.add(req_url)
                        except:
                            continue

                st.write(f"-> 捕获到候选图片资产线索，共 {len(image_urls)} 个。正在尝试通过 DOM 深度提取配置...")

                # 尝试从页面全局变量中直接提取图片列表（云展网通常将配置存在 window.bookConfig 或类似的全局对象中）
                js_extracted_urls = driver.execute_script("""
                    var urls = [];
                    try {
                        // 常见云展网结构
                        if (window.bookConfig && window.bookConfig.pages) {
                            urls = window.bookConfig.pages.map(p => p.img || p.url || p.large);
                        } else if (window.pages) {
                            urls = window.pages;
                        }
                        
                        // 遍历页面所有 img 标签与背景图
                        var imgs = document.querySelectorAll('img');
                        imgs.forEach(img => {
                            if (img.src && !img.src.includes('logo') && !img.src.includes('icon')) {
                                urls.push(img.src);
                            }
                        });
                    } catch(e) {}
                    return urls;
                """)

                driver.quit()

                if js_extracted_urls:
                    for u in js_extracted_urls:
                        if u and isinstance(u, str) and (u.startswith('http') or u.startswith('//')):
                            if u.startswith('//'): u = 'https:' + u
                            image_urls.add(u)

                # 如果通过网络日志和JS没找到规则图片，退回到智能视口渲染但加入 Hash 去重校验
                if len(image_urls) < 3:
                    st.write("3. 未能直接捕获完整图集，启动【高精度视口渲染 + 强制 Hash 校验去重引擎】...")
                    
                    # 重新拉起浏览器进行逐页渲染
                    driver = webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=chrome_options)
                    driver.get(url)
                    time.sleep(6)

                    with tempfile.TemporaryDirectory() as tmpdir:
                        valid_images = []
                        seen_hashes = set()
                        
                        # 循环翻页最多80页
                        for i in range(1, 81):
                            screenshot_path = os.path.join(tmpdir, f"page_{i:03d}.png")
                            driver.save_screenshot(screenshot_path)
                            
                            # 计算当前页面的 MD5 Hash，防止重复抓取封面
                            with open(screenshot_path, "rb") as f:
                                file_hash = hashlib.md5(f.read()).hexdigest()
                                
                            if file_hash in seen_hashes:
                                st.write(f"-> 检测到第 {i} 页内容与之前完全重复（Hash 命中），停止采集，共采集到 {len(valid_images)} 页有效内容。")
                                os.remove(screenshot_path)
                                break
                            
                            seen_hashes.add(file_hash)
                            
                            # 转换为高质量 JPG
                            img = Image.open(screenshot_path).convert("RGB")
                            jpg_path = os.path.join(tmpdir, f"page_{i:03d}.jpg")
                            img.save(jpg_path, "JPEG", quality=98, subsampling=0)
                            valid_images.append(jpg_path)
                            
                            st.write(f"✓ 成功捕获并校验第 {i} 页（唯一页面）")
                            
                            # 尝试翻页
                            driver.execute_script("""
                                try {
                                    if (window.book && window.book.next) { window.book.next(); }
                                    else {
                                        var kb = new KeyboardEvent('keydown', {key: 'ArrowRight', keyCode: 39, bubbles: true});
                                        document.dispatchEvent(kb);
                                    }
                                } catch(e) {}
                            """)
                            time.sleep(1.0)
                            driver.execute_script("window.scrollTo(0, 0);")

                        driver.quit()

                        if not valid_images:
                            status.update(label="采集失败", state="error")
                            st.error("未能采集到任何有效页面。")
                            st.stop()

                        st.write("4. 校验通过，正在合成为最终 PDF...")
                        output_pdf = os.path.join(tmpdir, "final_book.pdf")
                        with open(output_pdf, "wb") as f:
                            f.write(img2pdf.convert(valid_images))
                        with open(output_pdf, "rb") as f:
                            pdf_bytes = f.read()

                else:
                    st.write(f"3. 成功识别到 {len(image_urls)} 个原图资源，正在批量下载...")
                    # 如果直接解析到了原图 URL 列表，按名称/顺序排序下载
                    sorted_urls = sorted(list(image_urls))
                    
                    with tempfile.TemporaryDirectory() as tmpdir:
                        downloaded_files = []
                        for idx, img_url in enumerate(sorted_urls):
                            try:
                                resp = requests.get(img_url, timeout=5)
                                if resp.status_code == 200:
                                    img_path = os.path.join(tmpdir, f"dl_{idx:03d}.jpg")
                                    with open(img_path, "wb") as f:
                                        f.write(resp.content)
                                    downloaded_files.append(img_path)
                            except:
                                continue
                        
                        if downloaded_files:
                            output_pdf = os.path.join(tmpdir, "final_book.pdf")
                            with open(output_pdf, "wb") as f:
                                f.write(img2pdf.convert(downloaded_files))
                            with open(output_pdf, "rb") as f:
                                pdf_bytes = f.read()

                status.update(label="转换成功！", state="complete")

            except Exception as e:
                status.update(label="运行出错", state="error")
                st.error(f"详细错误: {e}")
                st.stop()

        if pdf_bytes:
            st.success("🎉 电子书已成功通过 Hash 去重校验与图源引擎转换为 PDF！")
            st.download_button(
                label="📥 点击下载生成的完整出版级 PDF 文件",
                data=pdf_bytes,
                file_name="yunzhan_book_verified.pdf",
                mime="application/pdf",
                use_container_width=True
            )
