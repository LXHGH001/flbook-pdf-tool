import os
import re
import json
import tempfile
from PIL import Image
import img2pdf
import requests
import streamlit as st

st.set_page_config(
    page_title="FLBook & 云展网转 PDF 工具", page_icon="📚", layout="centered"
)

st.title("📚 FLBook & 云展网电子书转 PDF 工具")
st.markdown("输入正确的电子书链接，**内联配置暴力逆向引擎**生成高质量 PDF！")

url = st.text_input("请输入电子书网址 (URL):", "https://book.yunzhan365.com/yhqej/uiqj/mobile/index.html")
fallback_pages = st.number_input("预估图书总页数:", min_value=1, max_value=500, value=3)

if st.button("开始暴力逆向并生成 PDF", type="primary", use_container_width=True):
  if not url:
    st.warning("请输入有效的网址！")
  else:
    with st.status("正在进行内联配置暴力逆向...", expanded=True) as status:
      st.write("1. 正在深度访问网页主页面...")
      
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

      st.write("2. 正在解析内联配置变量 (bookConfig / json)...")

      # 在网页源码中寻找 bookConfig 或类似配置对象
      extracted_bases = []
      total_pages = fallback_pages

      # 尝试匹配 bookConfig = {...} 或类似 JSON
      config_match = re.search(r'(?:bookConfig|g_data|data)\s*=\s*(\{.+?\});', html, re.DOTALL)
      if config_match:
          try:
              cfg_str = config_match.group(1)
              # 简单的键值提取
              pm = re.search(r'["\']?(?:pageCount|totalPages|sumPages)["\']?\s*[:=]\s*(\d+)', cfg_str)
              if pm:
                  total_pages = int(pm.group(1))
                  st.write(f"-> 成功从内联配置中提取总页数：{total_pages} 页")
          except:
              pass

      # 在源码中暴力搜寻所有带 mobile 或 files 的图片路径
      all_urls = re.findall(r'https?://[^\s<>"\']+', html)
      for u in all_urls:
          if "files/mobile" in u or "mobile/files" in u or "ext/page" in u:
              base_p = u.rsplit('/', 1)[0] + '/'
              if base_p not in extracted_bases:
                  extracted_bases.append(base_p)

      # 补充标准云展网高强度候选路径
      match_id = re.search(r'yunzhan365\.com/([^/]+/[^/]+)', url)
      book_path = match_id.group(1) if match_id else "yhqej/uiqj"
      
      standard_bases = [
          f"https://book.yunzhan365.com/{book_path}/files/mobile/",
          f"https://online.yunzhan365.com/{book_path}/files/mobile/",
          f"https://static.yunzhan365.com/{book_path}/files/mobile/",
          f"https://book.yunzhan365.com/{book_path}/mobile/files/mobile/",
          f"https://book.yunzhan365.com/{book_path}/files/large/",
          f"https://online.yunzhan365.com/{book_path}/files/large/",
      ]
      
      for sb in standard_bases:
          if sb not in extracted_bases:
              extracted_bases.append(sb)

      st.write(f"3. 正在按总页数 {total_pages} 页进行高效并行下载...")

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
          st.error("未能下载到任何页面图片。")
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
