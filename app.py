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
    "输入电子书链接，使用**轻量级 API 智能探测**并生成高质量 PDF！支持"
    " **FLBook (`flbook.com.cn`)** 和 **云展网 (`yunzhan365.com`)**。"
)

url = st.text_input("请输入电子书网址 (URL):", "https://book.yunzhan365.com/yhqe/uiqi/mobile/index.html")
fallback_pages = st.number_input("若未能自动识别页数，预估总页数:", min_value=1, max_value=500, value=20)

if st.button("开始智能解析并生成 PDF", type="primary", use_container_width=True):
  if not url:
    st.warning("请输入有效的网址！")
  else:
    with st.status("正在智能解析中...", expanded=True) as status:
      st.write("1. 正在深度连接目标网页并搜寻底层配置接口...")
      headers = {
          "User-Agent": (
              "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
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

      st.write("2. 正在提取图书动态配置 (Config / JSON)...")

      # 尝试寻找引用的 config.js 或 json 或从源码中解析书本路径
      config_text = html
      script_urls = re.findall(r'<script[^>]*src=["\']([^"\']+)["\']', html)
      
      for src in script_urls:
          if any(k in src.lower() for k in ["config", "book", "data", "main", "app"]):
              if not src.startswith("http"):
                  from urllib.parse import urljoin
                  src = urljoin(url, src)
              try:
                  sr = requests.get(src, headers=headers, timeout=5)
                  if sr.status_code == 200:
                      config_text += "\n" + sr.text
              except:
                  pass

      # 提取总页数
      total_pages = fallback_pages
      pm = re.search(r'(?:pageCount|totalPages|totalPage|sumPages)\s*[:=]\s*(\d+)', config_text, re.IGNORECASE)
      if pm:
          detected_p = int(pm.group(1))
          if detected_p > 2:
              total_pages = detected_p
              st.write(f"-> 自动识别到图书总页数：{total_pages} 页")

      # 提取云展网图书唯一标识 (例如 yhqe/uiqi)
      book_id_path = ""
      match_id = re.search(r'yunzhan365\.com/([^/]+/[^/]+)', url)
      if match_id:
          book_id_path = match_id.group(1)

      # 构造精准图床候选前缀
      candidate_prefixes = []
      if book_id_path:
          candidate_prefixes.extend([
              f"https://book.yunzhan365.com/{book_id_path}/files/mobile/",
              f"https://online.yunzhan365.com/{book_id_path}/files/mobile/",
              f"https://static.yunzhan365.com/{book_id_path}/files/mobile/",
              f"https://book.yunzhan365.com/{book_id_path}/mobile/files/mobile/",
          ])

      # 尝试从源码中匹配任何合法的图片 CDN 路径
      found_imgs = re.findall(r'https?://[^\s<>"]+?/(?:files/mobile|mobile|large)/[^\s<>"]+?\.(?:jpg|jpeg|png)', config_text)
      for fi in found_imgs:
          base_p = fi.rsplit('/', 1)[0] + "/"
          if base_p not in candidate_prefixes:
              candidate_prefixes.insert(0, base_p)

      # 通用兜底
      candidate_prefixes.extend([
          "https://online.yunzhan365.com/files/mobile/",
          "https://book.yunzhan365.com/files/mobile/",
          "https://flbook.com.cn/files/files/mobile/"
      ])

      st.write(f"3. 正在按总页数 {total_pages} 页批量下载高清页面...")

      with tempfile.TemporaryDirectory() as tmpdir:
        image_files = []
        progress_bar = st.progress(0)

        valid_count = 0
        consecutive_failures = 0

        for p in range(1, int(total_pages) + 1):
          img_data = None
          
          for bp in candidate_prefixes:
              variations = [
                  f"{bp}{p}.jpg",
                  f"{bp}{p}.png",
                  f"{bp}page_{p}.jpg",
                  f"{bp}{p:02d}.jpg",
                  f"{bp}{p:03d}.jpg"
              ]
              
              for cu in variations:
                  try:
                      r = requests.get(cu, headers=headers, timeout=2)
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
              if consecutive_failures >= 10 and valid_count > 2:
                  break

          progress_bar.progress(p / total_pages)

        if not image_files:
          status.update(label="下载失败", state="error")
          st.error("未能下载到任何页面图片。该云展网链接可能受访问密码或高级权限保护。")
          st.stop()

        st.write(f"4. 成功获取 {len(image_files)} 页，正在无损合成为 PDF...")
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
