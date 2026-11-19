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
st.markdown("输入正确的电子书链接，**秒级直连官方 CDN** 完美生成高质量 PDF！")

# 默认填入你给的正确链接
url = st.text_input("请输入电子书网址 (URL):", "https://book.yunzhan365.com/yhqej/uiqj/mobile/index.html")
total_pages = st.number_input("预估图书总页数:", min_value=1, max_value=500, value=30)

if st.button("开始一键转换并生成 PDF", type="primary", use_container_width=True):
  if not url:
    st.warning("请输入有效的网址！")
  else:
    with st.status("正在高速下载中...", expanded=True) as status:
      st.write("1. 正在解析链接中的图书唯一标识...")
      
      headers = {
          "User-Agent": (
              "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
              "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
          ),
          "Referer": url,
      }

      # 精准提取书本路径标识 (例如 yhqej/uiqj)
      book_id_path = ""
      match_id = re.search(r'yunzhan365\.com/([^/]+/[^/]+)', url)
      if match_id:
          book_id_path = match_id.group(1)
          st.write(f"-> 成功锁定书本 ID 路径：{book_id_path}")

      candidate_bases = []
      if book_id_path:
          candidate_bases.extend([
              f"https://book.yunzhan365.com/{book_id_path}/files/mobile/",
              f"https://online.yunzhan365.com/{book_id_path}/files/mobile/",
              f"https://static.yunzhan365.com/{book_id_path}/files/mobile/",
              f"https://book.yunzhan365.com/{book_id_path}/mobile/files/mobile/",
          ])
      
      candidate_bases.extend([
          "https://online.yunzhan365.com/files/mobile/",
          "https://book.yunzhan365.com/files/mobile/",
      ])

      st.write(f"2. 正在按总页数 {total_pages} 页进行高速直连并行下载...")

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
              if consecutive_failures >= 8 and valid_count > 2:
                  break

          progress_bar.progress(p / total_pages)

        if not image_files:
          status.update(label="下载失败", state="error")
          st.error("未能下载到页面图片。请核对链接是否正确。")
          st.stop()

        st.write(f"3. 成功获取 {len(image_files)} 页高清页面，正在合成为 PDF...")
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
