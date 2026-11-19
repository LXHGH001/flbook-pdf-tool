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
total_pages = st.number_input("请输入图书总页数 (如果不清楚可填大概页数):", min_value=1, max_value=1000, value=20)

if st.button("开始批量抓取并生成 PDF", type="primary", use_container_width=True):
  if not url:
    st.warning("请输入有效的网址！")
  else:
    with st.status("正在处理中...", expanded=True) as status:
      st.write("1. 正在连接并分析网页结构...")
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

      st.write("2. 正在识别平台类型并提取图书资源前缀...")

      is_yunzhan = "yunzhan365.com" in url
      base_prefixes = []

      # 提取网页中现有的图片链接来推导规律
      img_urls = re.findall(r'https?://[^\s<>"]+?\.(?:jpg|jpeg|png|webp)', html)

      for u in img_urls:
          u_lower = u.lower()
          if "mobile" in u_lower or "files" in u_lower or "book" in u_lower:
              # 尝试剥离文件名，保留目录前缀
              parts = u.rsplit('/', 1)
              if len(parts) == 2 and parts[0] not in base_prefixes:
                  base_prefixes.append(parts[0] + "/")

      # 针对云展网和 FLBook 的常见目录结构进行精准预设
      if is_yunzhan:
          # 云展网常见结构：https://online.yunzhan365.com/.../files/mobile/1.jpg 或类似
          # 我们尝试从 URL 中提取基础路径
          match_yz = re.search(r'(https?://[^/]+/.+?)/mobile/', url)
          if match_yz:
              yz_base = match_yz.group(1)
              base_prefixes.insert(0, f"{yz_base}/files/mobile/")
              base_prefixes.insert(0, f"{yz_base}/mobile/")
          
          # 同时把网页中提取到的有效前缀加入
          for u in img_urls:
              if "files/mobile" in u or "mobile/" in u:
                  p_dir = u.rsplit('/', 1)[0] + "/"
                  if p_dir not in base_prefixes:
                      base_prefixes.insert(0, p_dir)
      else:
          # FLBook 默认结构
          match_fl = re.search(r'(https?://[^/]+/.+?)/', url)
          if match_fl:
              base_prefixes.append("https://flbook.com.cn/files/files/")

      # 兜底通用前缀
      base_prefixes.append("https://online.yunzhan365.com/files/mobile/")
      base_prefixes.append("https://flbook.com.cn/files/files/")

      st.write(f"3. 正在按总页数 {total_pages} 页批量下载并匹配高清页面...")

      with tempfile.TemporaryDirectory() as tmpdir:
        image_files = []
        progress_bar = st.progress(0)

        valid_count = 0
        for p in range(1, int(total_pages) + 1):
          img_data = None
          
          # 遍历所有可能的前缀和后缀组合尝试下载
          for bp in base_prefixes:
              candidate_urls = [
                  f"{bp}{p}.jpg",
                  f"{bp}{p}.png",
                  f"{bp}page_{p}.jpg",
                  f"{bp}{p:02d}.jpg",
                  f"{bp}{p:03d}.jpg"
              ]
              
              for cu in candidate_urls:
                  try:
                      r = requests.get(cu, headers=headers, timeout=4)
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
          st.error("未能下载到任何页面图片。云展网链接可能带有动态 Token 或需要特殊的 Referer，请确保网址为该书的具体阅读页。")
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
        file_name="book_converted.pdf",
        mime="application/pdf",
        use_container_width=True
    )
