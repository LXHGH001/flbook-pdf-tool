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
st.markdown("输入正确的电子书链接，**源码深度直链捕获**完美生成高质量 PDF！")

url = st.text_input("请输入电子书网址 (URL):", "https://book.yunzhan365.com/yhqej/uiqj/mobile/index.html")
total_pages = st.number_input("预估图书总页数:", min_value=1, max_value=500, value=3)

if st.button("开始深度捕获并生成 PDF", type="primary", use_container_width=True):
  if not url:
    st.warning("请输入有效的网址！")
  else:
    with st.status("正在深度捕获中...", expanded=True) as status:
      st.write("1. 正在深度访问网页并获取源码结构...")
      
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

      st.write("2. 正在源码中提取真实的图片 CDN 路径与文件名格式...")

      # 在网页源码中寻找所有包含图片的链接
      all_img_links = re.findall(r'https?://[^\s<>"]+?\.(?:jpg|jpeg|png|webp)', html)
      
      sample_base = ""
      sample_ext = "jpg"
      
      for link in all_img_links:
          # 寻找带有数字编号的图片，例如 .../1.jpg 或 .../mobile/1.jpg
          m = re.search(r'(.+?/)(?:mobile/|files/|ext/)?(\d+)\.(jpg|jpeg|png|webp)$', link, re.IGNORECASE)
          if m:
              sample_base = m.group(1)
              sample_ext = m.group(3)
              st.write(f"-> 成功捕捉到真实图片服务器前缀：{sample_base}")
              break

      # 如果没直接匹配到带数字的，尝试提取任何包含 files 或 mobile 的路径前缀
      if not sample_base:
          for link in all_img_links:
              if "mobile" in link or "files" in link:
                  parts = link.rsplit('/', 1)
                  if len(parts) == 2:
                      sample_base = parts[0] + "/"
                      break

      # 兜底标准云展网路径
      match_id = re.search(r'yunzhan365\.com/([^/]+/[^/]+)', url)
      if not sample_base and match_id:
          book_path = match_id.group(1)
          sample_base = f"https://online.yunzhan365.com/{book_path}/files/mobile/"

      st.write(f"3. 正在按总页数 {total_pages} 页进行批量下载...")

      with tempfile.TemporaryDirectory() as tmpdir:
        image_files = []
        progress_bar = st.progress(0)
        valid_count = 0

        for p in range(1, int(total_pages) + 1):
          img_data = None
          
          # 组合候选链接
          candidate_urls = [
              f"{sample_base}{p}.{sample_ext}",
              f"{sample_base}page_{p}.{sample_ext}",
              f"{sample_base}{p:02d}.{sample_ext}",
              f"{sample_base}{p:03d}.{sample_ext}",
              # 经典云展网常见结构备用
              f"https://online.yunzhan365.com/files/mobile/{p}.jpg",
              f"https://book.yunzhan365.com/files/mobile/{p}.jpg",
          ]

          for cu in candidate_urls:
              try:
                  r = requests.get(cu, headers=headers, timeout=3)
                  if r.status_code == 200 and len(r.content) > 1500:
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
          st.error("未能从源码中解析出有效的图片。请检查该网址是否正确。")
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
