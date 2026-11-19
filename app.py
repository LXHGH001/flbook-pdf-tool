import os
import re
import tempfile
from PIL import Image
import img2pdf
import requests
import streamlit as st

st.set_page_config(
    page_title="FLBook & 云展网转 PDF 工具", page_icon="📚", layout="centered"
)

st.title("📚 FLBook & 云展网电子书转 PDF 工具")
st.markdown(
    "输入电子书链接，一键自动解析配置并生成高质量 PDF！支持"
    " **FLBook (`flbook.com.cn`)** 和 **云展网 (`yunzhan365.com`)**。"
)

url = st.text_input("请输入电子书网址 (URL):", "https://book.yunzhan365.com/yhqe/uiqi/mobile/index.html")
fallback_pages = st.number_input("如果未能自动识别页数，手动指定大概总页数:", min_value=1, max_value=1000, value=30)

if st.button("开始智能解析并生成 PDF", type="primary", use_container_width=True):
  if not url:
    st.warning("请输入有效的网址！")
  else:
    with st.status("正在智能解析中...", expanded=True) as status:
      st.write("1. 正在访问网页并提取图书底层配置...")
      headers = {
          "User-Agent": (
              "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
              " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
          ),
          "Referer": url,
      }
      try:
        resp = requests.get(url, headers=headers, timeout=15)
        html = resp.text
      except Exception as e:
        status.update(label="访问网页失败", state="error")
        st.error(f"错误详情: {e}")
        st.stop()

      st.write("2. 正在分析图书页数与图片直链规则...")

      page_urls = []
      
      # 策略 A：尝试从云展网/FLBook 页面中直接寻找引用的外部 JS 配置文件（如 bookConfig.js 或 config.js）
      script_srcs = re.findall(r'<script[^>]*src=["\']([^"\']+)["\'][^>]*>', html)
      config_html = html
      
      for src in script_srcs:
          if "config" in src or "book" in src or "javascript" in src:
              if not src.startswith("http"):
                  # 拼接绝对路径
                  from urllib.parse import urljoin
                  src = urljoin(url, src)
              try:
                  sr = requests.get(src, headers=headers, timeout=5)
                  if sr.status_code == 200:
                      config_html += "\n" + sr.text
              except:
                  pass

      # 尝试在源码中匹配总页数
      total_pages = fallback_pages
      page_match = re.search(r'(?:pageCount|totalPages|totalPage|sumPages)\s*[:=]\s*(\d+)', config_html, re.IGNORECASE)
      if page_match:
          detected_pages = int(page_match.group(1))
          if detected_pages > 2:
              total_pages = detected_pages
              st.write(f"-> 成功自动识别到图书总页数：{total_pages} 页")

      # 尝试提取图片 URL 模板前缀
      # 云展网通常图片存放在类似 https://online.yunzhan365.com/xxx/files/mobile/1.jpg
      img_base = None
      
      # 寻找形如 .../files/mobile/ 的路径
      m_base = re.search(r'(https?://[^/]+/.+?/files/mobile/)', config_html)
      if m_base:
          img_base = m_base.group(1)
      else:
          # 尝试从 URL 直接推导
          if "yunzhan365.com" in url:
              match_yz = re.search(r'(https?://[^/]+/[^/]+/[^/]+)', url)
              if match_yz:
                  img_base = match_yz.group(1) + "/files/mobile/"

      if not img_base:
          img_base = "https://online.yunzhan365.com/files/mobile/"

      st.write(f"3. 锁定目标图床，准备批量下载 {total_pages} 页高清页面...")

      with tempfile.TemporaryDirectory() as tmpdir:
        image_files = []
        progress_bar = st.progress(0)

        valid_count = 0
        for p in range(1, int(total_pages) + 1):
          img_data = None
          candidate_urls = [
              f"{img_base}{p}.jpg",
              f"{img_base}{p}.png",
              f"{img_base}page_{p}.jpg",
              f"{img_base}{p:02d}.jpg",
              f"{img_base}{p:03d}.jpg",
              # 兼容备用目录
              f"https://online.yunzhan365.com/files/mobile/{p}.jpg",
              f"https://book.yunzhan365.com/files/mobile/{p}.jpg"
          ]
          
          for cu in candidate_urls:
              try:
                  r = requests.get(cu, headers=headers, timeout=3)
                  if r.status_code == 200 and len(r.content) > 2000:
                      img_data = r.content
                      break
              except:
                  pass

          if img_data:
              try:
                  tmp_path = os.path.join(tmpdir, f"raw_{p}.jpg")
                  with open(tmp_path, "wb") as f:
                      f.write(img_data)

                  img_rgb = Image.open(tmp_path).convert("RGB")
                  file_path = os.path.join(tmpdir, f"page_{valid_count+1:03d}.jpg")
                  img_rgb.save(file_path, "JPEG", quality=95)

                  image_files.append(file_path)
                  valid_count += 1
              except:
                  pass

          progress_bar.progress(p / total_pages)

        if not image_files:
          status.update(label="下载失败", state="error")
          st.error("未能下载到页面图片。该云展网链接可能受密码保护或采用了非标准加密存储。")
          st.stop()

        st.write(f"4. 成功获取 {len(image_files)} 页，正在无损合成为完整的 PDF...")
        output_pdf = os.path.join(tmpdir, "book_full.pdf")

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
