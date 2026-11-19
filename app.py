import os
import re
import tempfile
from PIL import Image
import img2pdf
import requests
import streamlit as st
from urllib.parse import urljoin

st.set_page_config(
    page_title="FLBook & 云展网转 PDF 工具", page_icon="📚", layout="centered"
)

st.title("📚 FLBook & 云展网电子书转 PDF 工具")
st.markdown("输入正确的电子书链接，**Config 配置文件深度逆向引擎**完美生成 PDF！")

url = st.text_input("请输入电子书网址 (URL):", "https://book.yunzhan365.com/yhqej/uiqj/mobile/index.html")
fallback_pages = st.number_input("预估图书总页数:", min_value=1, max_value=500, value=30)

if st.button("开始配置文件逆向转换并生成 PDF", type="primary", use_container_width=True):
  if not url:
    st.warning("请输入有效的网址！")
  else:
    with st.status("正在进行配置文件逆向...", expanded=True) as status:
      st.write("1. 正在访问主页面并搜寻所有引用的 JS 配置文件...")
      
      headers = {
          "User-Agent": (
              "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
              "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
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

      # 抓取页面中所有的 script 链接并下载其内容（特别是 config.js / bookConfig 等）
      config_blob = html
      script_srcs = re.findall(r'<script[^>]*src=["\']([^"\']+)["\']', html)
      
      for src in script_srcs:
          if not src.startswith("http"):
              src = urljoin(url, src)
          try:
              sr = requests.get(src, headers=headers, timeout=5)
              if sr.status_code == 200:
                  config_blob += "\n" + sr.text
          except:
              pass

      st.write("2. 正在从配置文件中逆向真实的图片服务器与路径前缀...")

      # 尝试在配置中寻找图片存储路径前缀（如 files/mobile/ 或自定义目录）
      real_image_base = ""
      
      # 寻找类似 "path":"..." 或 "bookpath":"..." 或包含 files 的 URL 片段
      path_matches = re.findall(r'["\'](https?://[^"\']+?/(?:files|mobile|ext|book/[^"\']+?)[^"\']*?)(?=/ \d+\.jpg|\d+\.png|\b)', config_blob)
      for pm in path_matches:
          if "yunzhan365" in pm or "flbook" in pm or "files" in pm:
              real_image_base = pm if pm.endswith('/') else pm + '/'
              break

      # 如果没直接搜到，通过正则提取任何形如 http.../files/mobile/ 的前缀
      if not real_image_base:
          m_base = re.search(r'(https?://[^\s<>"]+?/(?:yhqej/uiqj|[^/]+/[^/]+)/files/mobile/)', config_blob)
          if m_base:
              real_image_base = m_base.group(1)

      # 兜底构造标准路径
      match_id = re.search(r'yunzhan365\.com/([^/]+/[^/]+)', url)
      book_path = match_id.group(1) if match_id else "yhqej/uiqj"
      
      candidate_bases = []
      if real_image_base:
          candidate_bases.append(real_image_base)
      
      candidate_bases.extend([
          f"https://book.yunzhan365.com/{book_path}/files/mobile/",
          f"https://online.yunzhan365.com/{book_path}/files/mobile/",
          f"https://static.yunzhan365.com/{book_path}/files/mobile/",
          f"https://book.yunzhan365.com/{book_path}/mobile/files/mobile/",
      ])

      # 自动提取总页数
      total_pages = fallback_pages
      pm = re.search(r'(?:pageCount|totalPages|totalPage|sumPages)\s*[:=]\s*(\d+)', config_blob, re.IGNORECASE)
      if pm:
          total_pages = int(pm.group(1))
          st.write(f"-> 成功逆向识别到图书总页数：{total_pages} 页")

      st.write(f"3. 正在按总页数 {total_pages} 页进行高速下载...")

      with tempfile.TemporaryDirectory() as tmpdir:
        image_files = []
        progress_bar = st.progress(0)
        valid_count = 0
        consecutive_failures = 0

        for p in range(1, int(total_pages) + 1):
          img_data = None
          
          for base_url in candidate_bases:
              variations = [
                  f"{base_url}{p}.jpg",
                  f"{base_url}{p}.png",
                  f"{base_url}page_{p}.jpg",
                  f"{base_url}{p:02d}.jpg",
                  f"{base_url}{p:03d}.jpg",
              ]
              
              for cu in variations:
                  try:
                      r = requests.get(cu, headers=headers, timeout=3)
                      if r.status_code == 200 and len(r.content) > 1500:
                          img_data = r.content
                          break
                  except:
                      pass
              if img_data:
                  break

          if img_data:
              consecutive_failures = 0
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
          else:
              consecutive_failures += 1
              if consecutive_failures >= 15 and valid_count > 2:
                  break

          progress_bar.progress(p / total_pages)

        if not image_files:
          status.update(label="下载失败", state="error")
          st.error("未能下载到页面图片。该书可能包含高级防盗链或需要登录鉴权。")
          st.stop()

        st.write(f"4. 成功获取 {len(image_files)} 页高清页面，正在合成为 PDF...")
        output_pdf = os.path.join(tmpdir, "yunzhan_book.pdf")

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
