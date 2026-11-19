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
    "输入电子书链接和总页数，一键自动批量组装整本书并生成高质量 PDF！支持"
    " **FLBook (`flbook.com.cn`)** 和 **云展网 (`yunzhan365.com`)**。"
)

url = st.text_input("请输入电子书网址 (URL):", "https://book.yunzhan365.com/yhqe/uiqi/mobile/index.html")
total_pages = st.number_input("请输入图书总页数 (如果不清楚可填大概页数):", min_value=1, max_value=1000, value=30)

if st.button("开始批量抓取并生成 PDF", type="primary", use_container_width=True):
  if not url:
    st.warning("请输入有效的网址！")
  else:
    with st.status("正在处理中...", expanded=True) as status:
      st.write("1. 正在解析链接中的图书唯一标识...")
      headers = {
          "User-Agent": (
              "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
              " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
          ),
          "Referer": "https://book.yunzhan365.com/",
      }

      possible_prefixes = []

      # 针对云展网提取路径：例如 https://book.yunzhan365.com/yhqe/uiqi/mobile/index.html -> yhqe/uiqi
      if "yunzhan365.com" in url:
          match_yz = re.search(r'yunzhan365\.com/([^/]+/[^/]+)', url)
          if match_yz:
              book_path = match_yz.group(1) # 例如 yhqe/uiqi
              possible_prefixes.append(f"https://online.yunzhan365.com/{book_path}/files/mobile/")
              possible_prefixes.append(f"https://book.yunzhan365.com/{book_path}/files/mobile/")
              possible_prefixes.append(f"https://static.yunzhan365.com/{book_path}/files/mobile/")
          
          # 备用：直接从 URL 提取所有斜杠路径组合
          parts = url.split('/')
          if len(parts) >= 5:
              base_p = f"{parts[0]}//{parts[2]}/{parts[3]}/{parts[4]}/files/mobile/"
              possible_prefixes.append(base_p)

      # 针对 FLBook
      if "flbook.com.cn" in url:
          possible_prefixes.append("https://flbook.com.cn/files/files/mobile/")
          possible_prefixes.append("https://flbook.com.cn/files/files/")

      # 通用兜底
      possible_prefixes.append("https://online.yunzhan365.com/files/mobile/")
      
      st.write(f"2. 已锁定目标目录，开始按总页数 {total_pages} 页批量下载高清页面...")

      with tempfile.TemporaryDirectory() as tmpdir:
        image_files = []
        progress_bar = st.progress(0)

        valid_count = 0
        for p in range(1, int(total_pages) + 1):
          img_data = None
          
          # 依次尝试每个候选前缀和常见后缀
          for bp in possible_prefixes:
              candidate_urls = [
                  f"{bp}{p}.jpg",
                  f"{bp}{p}.png",
                  f"{bp}page_{p}.jpg",
                  f"{bp}{p:02d}.jpg",
                  f"{bp}{p:03d}.jpg"
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
              except:
                  pass

          progress_bar.progress(p / total_pages)

        if not image_files:
          status.update(label="下载失败", state="error")
          st.error("未能下载到任何页面图片。请核对该云展网链接是否正确（需包含具体的书本路径，如 /yhqe/uiqi/）。")
          st.stop()

        st.write(f"3. 成功获取 {len(image_files)} 页，正在无损合成为完整的 PDF...")
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
