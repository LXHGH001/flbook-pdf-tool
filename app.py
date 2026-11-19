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
    "输入电子书链接，一键全自动暴力穿透并生成高质量 PDF！支持"
    " **FLBook (`flbook.com.cn`)** 和 **云展网 (`yunzhan365.com`)**。"
)

url = st.text_input("请输入电子书网址 (URL):", "https://book.yunzhan365.com/yhqe/uiqi/mobile/index.html")
total_pages = st.number_input("请输入或预估图书总页数:", min_value=1, max_value=1000, value=20)

if st.button("开始深度暴力穿透抓取", type="primary", use_container_width=True):
  if not url:
    st.warning("请输入有效的网址！")
  else:
    with st.status("正在进行深度暴力穿透...", expanded=True) as status:
      st.write("1. 正在以移动端真实设备身份连接书本...")
      # 强伪装移动端 UA，逼迫云展网返回标准静态图片结构
      headers = {
          "User-Agent": (
              "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
              "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 "
              "Mobile/15E148 Safari/604.1"
          ),
          "Referer": url,
          "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      }
      try:
        resp = requests.get(url, headers=headers, timeout=15)
        html = resp.text
      except Exception as e:
        status.update(label="访问网页失败", state="error")
        st.error(f"错误详情: {e}")
        st.stop()

      st.write("2. 正在深度解析云展网动态 Config 配置文件...")

      # 尝试寻找引用的 config.js 或 json
      config_data_text = html
      script_urls = re.findall(r'<script[^>]*src=["\']([^"\']+)["\']', html)
      for src in script_urls:
          if "config" in src or "book" in src or "data" in src:
              if not src.startswith("http"):
                  from urllib.parse import urljoin
                  src = urljoin(url, src)
              try:
                  sr = requests.get(src, headers=headers, timeout=5)
                  if sr.status_code == 200:
                      config_data_text += "\n" + sr.text
              except:
                  pass

      # 尝试在配置中匹配页数
      pm = re.search(r'(?:pageCount|totalPages|totalPage)\s*[:=]\s*(\d+)', config_data_text, re.IGNORECASE)
      if pm:
          detected_p = int(pm.group(1))
          if detected_p > 2:
              total_pages = detected_p
              st.write(f"-> 成功从底层配置中自动识别总页数：{total_pages} 页")

      # 提取云展网图书 ID 路径
      book_id_path = ""
      match_id = re.search(r'yunzhan365\.com/([^/]+/[^/]+)', url)
      if match_id:
          book_id_path = match_id.group(1) # 例如 yhqe/uiqi

      # 构建云展网超级暴力前缀库
      candidate_base_urls = []
      if book_id_path:
          candidate_base_urls.extend([
              f"https://book.yunzhan365.com/{book_id_path}/files/mobile/",
              f"https://online.yunzhan365.com/{book_id_path}/files/mobile/",
              f"https://static.yunzhan365.com/{book_id_path}/files/mobile/",
              f"https://book.yunzhan365.com/{book_id_path}/mobile/files/mobile/",
              f"https://online.yunzhan365.com/{book_id_path}/mobile/files/mobile/",
              f"https://book.yunzhan365.com/{book_id_path}/files/ext/page/",
              f"https://online.yunzhan365.com/{book_id_path}/files/ext/page/",
              f"https://book.yunzhan365.com/{book_id_path}/files/large/",
              f"https://online.yunzhan365.com/{book_id_path}/files/large/",
          ])

      # 通用兜底
      candidate_base_urls.extend([
          "https://online.yunzhan365.com/files/mobile/",
          "https://book.yunzhan365.com/files/mobile/",
          "https://flbook.com.cn/files/files/mobile/",
      ])

      st.write(f"3. 正在按总页数 {total_pages} 页启动多线程CDN暴力扫描...")

      with tempfile.TemporaryDirectory() as tmpdir:
        image_files = []
        progress_bar = st.progress(0)

        valid_count = 0
        consecutive_failures = 0

        for p in range(1, int(total_pages) + 1):
          img_data = None
          
          for base_url in candidate_base_urls:
              variations = [
                  f"{base_url}{p}.jpg",
                  f"{base_url}{p}.png",
                  f"{base_url}page_{p}.jpg",
                  f"{base_url}{p:02d}.jpg",
                  f"{base_url}{p:03d}.jpg",
                  f"{base_url}p_{p}.jpg"
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
              if consecutive_failures >= 8 and valid_count > 2:
                  break

          progress_bar.progress(p / total_pages)

        if not image_files:
          status.update(label="下载失败", state="error")
          st.error("未能下载到任何页面图片。该云展网电子书可能设置了高级会员密码保护。")
          st.stop()

        st.write(f"4. 成功捕获 {len(image_files)} 页高清页面，正在合成为 PDF...")
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
