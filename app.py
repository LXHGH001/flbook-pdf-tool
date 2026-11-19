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

url = st.text_input("请输入电子书网址 (URL):", "https://flbook.com.cn/c/kzf3IpcEpy")
total_pages = st.number_input("请输入图书总页数 (如果不清楚可填大概页数):", min_value=1, max_value=1000, value=50)

if st.button("开始批量抓取并生成 PDF", type="primary", use_container_width=True):
  if not url:
    st.warning("请输入有效的网址！")
  else:
    with st.status("正在处理中...", expanded=True) as status:
      st.write("1. 正在分析网页结构并获取图书资源特征...")
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

      st.write("2. 正在提取图书基础图片路径模式...")

      # 从网页中提取任意一张图片作为 URL 前缀模板
      img_urls = re.findall(r'https?://[^\s<>"]+?\.(?:jpg|jpeg|png)', html)
      
      base_prefix = None
      ext = "jpg"
      
      for u in img_urls:
          # 寻找形如 .../mobile/1.jpg 或类似结构的链接
          m = re.search(r'(.+?/)(?:mobile/|shot/|page[s]?/)?\d+\.(jpg|jpeg|png)$', u, re.IGNORECASE)
          if m:
              base_prefix = m.group(1)
              ext = m.group(2)
              break

      # 如果没匹配到特征，尝试从网页中找任何包含 files 的链接推导
      if not base_prefix:
          for u in img_urls:
              if "files" in u or "book" in u:
                  parts = u.rsplit('/', 1)
                  if len(parts) == 2:
                      base_prefix = parts[0] + "/"
                      break

      if not base_prefix:
          # 默认兜底策略：使用 FLBook 常见的静态资源服务前缀
          base_prefix = "https://flbook.com.cn/files/files/"

      st.write(f"3. 锁定前缀，开始按总页数 {total_pages} 页批量下载高清页面...")

      with tempfile.TemporaryDirectory() as tmpdir:
        image_files = []
        progress_bar = st.progress(0)

        valid_count = 0
        # 按照用户输入的总页数进行循环抓取
        for p in range(1, int(total_pages) + 1):
          # 尝试多种常见的翻页书图片命名组合
          candidate_urls = [
              f"{base_prefix}mobile/{p}.{ext}",
              f"{base_prefix}shot/{p}.{ext}",
              f"{base_prefix}{p}.{ext}",
              f"{base_prefix}page_{p}.{ext}"
          ]
          
          img_data = None
          for cu in candidate_urls:
              try:
                  r = requests.get(cu, headers=headers, timeout=5)
                  if r.status_code == 200 and len(r.content) > 3000:
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
          st.error("未能下载到任何页面图片。请核对链接是否正确或图书是否需要登录。")
          st.stop()

        st.write(f"4. 成功获取 {len(image_files)} 页，正在无损合成为完整的 PDF...")
        output_pdf = os.path.join(tmpdir, "flbook_full.pdf")

        with open(output_pdf, "wb") as f:
          f.write(img2pdf.convert(image_files))

        with open(output_pdf, "rb") as f:
          pdf_bytes = f.read()

        status.update(label="转换成功！", state="complete")

    st.success(f"🎉 电子书已成功转换为 PDF（共 {len(image_files)} 页）！")
    st.download_button(
        label="📥 点击下载生成的完整 PDF 文件",
        data=pdf_bytes,
        file_name="flbook_full.pdf",
        mime="application/pdf",
        use_container_width=True
    )
