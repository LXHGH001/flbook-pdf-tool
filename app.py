import streamlit as st
import requests
import re
import os
import tempfile
import img2pdf

st.set_page_config(
    page_title="FLBook & 云展网转 PDF 工具",
    page_icon="📚",
    layout="centered"
)

st.title("📚 FLBook & 云展网电子书转 PDF 工具")
st.markdown("输入电子书链接，一键自动抓取并生成高质量 PDF 文档，直接在网页端下载！支持 **FLBook (`flbook.com.cn`)** 和 **云展网 (`yunzhan365.com`)**。")

# 输入框
url = st.text_input(
    "请输入电子书网址 (URL):", 
    "https://flbook.com.cn/c/kzf3IpcEpy"
)

col1, col2 = st.columns([1, 1])
with col1:
    download_btn = st.button("开始转换并生成 PDF", type="primary", use_container_width=True)

if download_btn:
    if not url:
        st.warning("请输入有效的网址！")
    else:
        with st.status("正在处理中...", expanded=True) as status:
            st.write("1. 正在连接并提取网页内容...")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            try:
                resp = requests.get(url, headers=headers, timeout=15)
                html = resp.text
            except Exception as e:
                status.update(label="访问网页失败", state="error")
                st.error(f"错误详情: {e}")
                st.stop()

            st.write("2. 正在解析电子书页面图片资源...")
            # 提取页面图片资源
            img_urls = re.findall(r'https?://[^\s<>"]+?\.(?:jpg|png|webp)', html)
            page_urls = []
            for u in img_urls:
                if ("files" in u or "book" in u or "mobile" in u or "shot" in u) and u not in page_urls:
                    page_urls.append(u)

            if not page_urls:
                status.update(label="解析失败", state="error")
                st.error("未能自动从该网页直接提取到图片列表。该页面可能采用了动态加密加载，建议通过截图或源文件处理。")
                st.stop()

            st.write(f"3. 检测到约 {len(page_urls)} 个页面，正在批量下载...")
            
            with tempfile.TemporaryDirectory() as tmpdir:
                image_files = []
                progress_bar = st.progress(0)

                for i, img_url in enumerate(page_urls):
                    try:
                        img_data = requests.get(img_url, headers=headers, timeout=10).content
                        file_path = os.path.join(tmpdir, f"page_{i+1:03d}.jpg")
                        with open(file_path, "wb") as f:
                            f.write(img_data)
                        image_files.append(file_path)
                    except Exception:
                        pass
                    progress_bar.progress((i + 1) / len(page_urls))

                if not image_files:
                    status.update(label="下载失败", state="error")
                    st.error("下载页面失败，未能获取到任何有效图片。")
                    st.stop()

                st.write("4. 正在将页面图片无损合成为 PDF 文件...")
                output_pdf = os.path.join(tmpdir, "flbook_output.pdf")
                with open(output_pdf, "wb") as f:
                    f.write(img2pdf.convert(image_files))

                with open(output_pdf, "rb") as f:
                    pdf_bytes = f.read()

                status.update(label="转换成功！", state="complete")

        st.success("🎉 电子书已成功转换为 PDF！")
        st.download_button(
            label="📥 点击下载生成的 PDF 文件",
            data=pdf_bytes,
            file_name="flbook_converted.pdf",
            mime="application/pdf",
            use_container_width=True
        )

st.markdown("---")
st.markdown("💡 **使用提示**：你可以将此脚本保存为 `app.py`，执行 `streamlit run app.py` 即可在本地浏览器中享受免安装、纯可视化的转换体验！")
