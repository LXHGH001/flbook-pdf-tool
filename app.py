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
    "输入电子书链接，一键全自动穿透并生成高质量 PDF！支持"
    " **FLBook (`flbook.com.cn`)** 和 **云展网 (`yunzhan365.com`)**。"
)

url = st.text_input("请输入电子书网址 (URL):", "https://book.yunzhan365.com/yhqe/uiqi/mobile/index.html")
total_pages = st.number_input("请输入或预估图书总页数:", min_value=1, max_value=1000, value=20)

if st.button("开始全自动穿透抓取", type="primary", use_container_width=True):
  if not url:
    st.warning("请输入有效的网址！")
  else:
    with st.status("正在全自动穿透中...", expanded=True) as status:
      st.write("1. 正在深度连接目标书本页面...")
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

      st.write("2. 正在提取云展网/FLBook 核心资产路径...")

      # 提取书本唯一标识符 (例如 yhqe/uiqi)
      book_id_path = ""
      match_id = re.search(r'yunzhan365\.com/([^/]+/[^/]+)', url)
      if match_id:
          book_id_path = match_id.group(1) # 例如 yhqe/uiqi

      # 构建云展网超级候选前缀库
      candidate_base_urls = []
      if book_id_path:
          candidate_base_urls.extend([
              f"https://book.yunzhan365.com/{book_id_path}/files/mobile/",
              f"https://online.yunzhan365.com/{book_id_path}/files/mobile/",
              f"https://static.yunzhan365.com/{book_id_path}/files/mobile/",
              f"https://book.yunzhan365.com/{book_id_path}/mobile/files/mobile/",
              f"https://online.yunzhan365.com/{book_id_path}/mobile/files/mobile/",
              f"https://book.yunzhan365.com/{book_id_path}/files/ext/",
              f"https://online.yunzhan365.com/{book_id_path}/files/ext/",
          ])

      # 顺便从网页源码中提取任何包含图片或资源的绝对路径
      all_links = re.findall(r'https?://[^\s<>"]+?\.(?:jpg|jpeg|png|webp)', html)
      for link in all_links:
          if "mobile" in link or "files" in link:
              base_dir = link.rsplit('/', 1)[0] + "/"
              if base_dir not in candidate_base_urls:
                  candidate_base_urls.insert(0, base_dir)

      # 通用兜底
      candidate_base_urls.extend([
          "https://online.yunzhan365.com/files/mobile/",
          "https://book.yunzhan365.com/files/mobile/",
          "https://flbook.com.cn/files/files/mobile/",
          "https://flbook.com.cn/files/files/"
      ])

      st.write(f"3. 正在按总页数 {total_pages} 页进行多路 CDN 并行扫描下载...")

      with tempfile.TemporaryDirectory() as tmpdir:
        image_files = []
        progress_bar = st.progress(0)

        valid_count = 0
        # 我们用智能探测：如果某页连续尝试所有前缀都失败，说明书已经读完了
        consecutive_failures = 0

        for p in range(1, int(total_pages) + 1):
          img_data = None
          
          # 遍历所有候选前缀和常见后缀
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
              # 如果连续 5 页都找不到，且已经下载了至少几页，说明书已经到底了，提前结束
              if consecutive_failures >= 5 and valid_count > 2:
                  break

          progress_bar.progress(p / total_pages)

        if not image_files:
          status.update(label="下载失败", state="error")
          st.error("未能下载到任何页面图片。该云展网电子书可能设置了严格的访问权限或动态 Token 校验。")
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
