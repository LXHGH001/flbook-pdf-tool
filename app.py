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
st.markdown("输入正确的电子书链接，**源码全局深度直链扫描引擎**生成高质量 PDF！")

url = st.text_input("请输入电子书网址 (URL):", "https://book.yunzhan365.com/yhqej/uiqj/mobile/index.html")
fallback_pages = st.number_input("预估图书总页数:", min_value=1, max_value=500, value=3)

if st.button("开始深度扫描并生成 PDF", type="primary", use_container_width=True):
  if not url:
    st.warning("请输入有效的网址！")
  else:
    with st.status("正在进行源码全局深度扫描...", expanded=True) as status:
      st.write("1. 正在深度访问网页并获取完整 HTML 源码...")
      
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

      st.write("2. 正在抓取并合并所有的 JS 配置文件...")
      
      # 寻找所有引用的 JS 文件并全部下载拼起来
      full_blob = html
      script_srcs = re.findall(r'<script[^>]*src=["\']([^"\']+)["\']', html)
      for src in script_srcs:
          if not src.startswith("http"):
              src = urljoin(url, src)
          try:
              sr = requests.get(src, headers=headers, timeout=5)
              if sr.status_code == 200:
                  full_blob += "\n" + sr.text
          except:
              pass

      st.write("3. 正在从源码与配置中提取真实的图片直链前缀...")

      # 寻找任何带有图片特征的完整 URL 片段
      found_links = re.findall(r'https?://[^\s<>"\']+(?:/mobile/|/files/|/ext/|/large/)[^\s<>"\']*?\.(?:jpg|jpeg|png|webp)', full_blob, re.IGNORECASE)
      
      extracted_bases = []
      for fl in found_links:
          # 尝试切出基础路径（去掉最后的页码和后缀）
          m = re.search(r'(.+?/)(?:page_)?\d+\.(?:jpg|jpeg|png|webp)$', fl, re.IGNORECASE)
          if m:
              base_p = m.group(1)
              if base_p not in extracted_bases:
                  extracted_bases.insert(0, base_p)
          else:
              # 如果没匹配到数字，把目录作为候选
              parts = fl.rsplit('/', 1)
              if len(parts) == 2 and parts[0] + '/' not in extracted_bases:
                  extracted_bases.append(parts[0] + '/')

      st.write(f"-> 共在源码中捕获到 {len(extracted_bases)} 个潜在图片 CDN 目录")

      # 自动识别总页数
      total_pages = fallback_pages
      pm = re.search(r'(?:pageCount|totalPages|totalPage|sumPages)\s*[:=]\s*(\d+)', full_blob, re.IGNORECASE)
      if pm:
          detected_p = int(pm.group(1))
          if detected_p > 2:
              total_pages = detected_p
              st.write(f"-> 自动识别到图书总页数：{total_pages} 页")

      # 补充常规兜底候选路径
      match_id = re.search(r'yunzhan365\.com/([^/]+/[^/]+)', url)
      book_path = match_id.group(1) if match_id else "yhqej/uiqj"
      
      fallback_bases = [
          f"https://book.yunzhan365.com/{book_path}/files/mobile/",
          f"https://online.yunzhan365.com/{book_path}/files/mobile/",
          f"https://static.yunzhan365.com/{book_path}/files/mobile/",
          f"https://book.yunzhan365.com/{book_path}/files/large/",
      ]
      
      for fb in fallback_bases:
          if fb not in extracted_bases:
              extracted_bases.append(fb)

      st.write(f"4. 正在按总页数 {total_pages} 页批量并行下载...")

      with tempfile.TemporaryDirectory() as tmpdir:
        image_files = []
        progress_bar = st.progress(0)
        valid_count = 0

        for p in range(1, int(total_pages) + 1):
          img_data = None
          success_url = ""
          
          for base_url in extracted_bases:
              variations = [
                  f"{base_url}{p}.jpg",
                  f"{base_url}{p}.png",
                  f"{base_url}page_{p}.jpg",
                  f"{base_url}{p:02d}.jpg",
                  f"{base_url}{p:03d}.jpg",
              ]
              
              for cu in variations:
                  try:
                      r = requests.get(cu, headers=headers, timeout=2)
                      if r.status_code == 200 and len(r.content) > 1000:
                          img_data = r.content
                          success_url = cu
                          break
                  except:
                      pass
              if img_data:
                  break

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
                  st.write(f"✓ 成功下载第 {p} 页 (来源: {success_url})")
              except Exception as e:
                  st.write(f"! 第 {p} 页解析图片失败: {e}")
          else:
              st.write(f"✗ 第 {p} 页未能在任何候选目录中命中")

          progress_bar.progress(p / total_pages)

        if not image_files:
          status.update(label="下载失败", state="error")
          st.error("未能从源码中捕获到有效页面图片。")
          st.stop()

        st.write(f"5. 成功获取 {len(image_files)} 页高清页面，正在合成为 PDF...")
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
