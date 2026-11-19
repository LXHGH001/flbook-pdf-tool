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
    "输入电子书链接，一键自动抓取并生成高质量 PDF 文档，直接在网页端下载！支持"
    " **FLBook (`flbook.com.cn`)** 和 **云展网 (`yunzhan365.com`)**。"
)

url = st.text_input("请输入电子书网址 (URL):", "https://flbook.com.cn/c/kzf3IpcEpy")

if st.button("开始转换并生成 PDF", type="primary", use_container_width=True):
  if not url:
    st.warning("请输入有效的网址！")
  else:
    with st.status("正在处理中...", expanded=True) as status:
      st.write("1. 正在连接并提取网页图书配置...")
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

      st.write("2. 正在深度解析图书页数与图片模板...")

      page_urls = []

      # 策略 A：尝试在网页源码中寻找高画质移动端图片或连续图片规律
      # FLBook 常见图片路径特征：包含 mobile/ 或 files/ 且以数字命名
      img_urls = re.findall(r'https?://[^\s<>"]+?/(?:mobile|shot|pages?)/[^\s<>"]+?\.(?:jpg|jpeg|png)', html)
      
      # 如果找不到专属 mobile 路径，匹配所有可能是书页的大图
      if not img_urls:
          img_urls = re.findall(r'https?://[^\s<>"]+?\.(?:jpg|jpeg|png)', html)

      # 过滤掉头像、logo等
      filtered_imgs = []
      for u in img_urls:
          u_lower = u.lower()
          if not any(k in u_lower for k in ["logo", "icon", "avatar", "qrcode", "loading"]):
              if u not in filtered_imgs:
                  filtered_imgs.append(u)

      # 策略 B：如果找到了某个典型的图片 URL（例如 .../mobile/1.jpg 或类似结构），推导整本书的页面
      base_pattern_found = False
      for u in filtered_imgs:
          # 寻找形如 .../1.jpg 或 .../page_1.jpg 的结构
          m = re.search(r'(.+?/)(?:mobile/|shot/|page[s]?/)?(\d+)\.(jpg|jpeg|png)$', u, re.IGNORECASE)
          if m:
              prefix, page_num_str, ext = m.groups()
              # 尝试智能推测总页数（通常翻页书在 10 ~ 300 页之间，这里我们尝试推导到 150 页，或根据检测到的最大页数）
              # 为了保险，我们通过并发/依次探测后续页码是否存在来获取整本书
              st.write(f"检测到书页图片模板，正在自动探测整本书籍页数...")
              
              # 先把已知的加进去
              test_prefix = m.group(1)
              # 让我们尝试往后探测，直到连续 5 页不存在为止
              valid_book_pages = []
              
              # 顺便把前面收集到的所有图片也作为候选
              for p in range(1, 200): # 最多探测 200 页
                  # 常见的几种 FLBook 命名格式
                  candidate_urls = [
                      f"{test_prefix}mobile/{p}.{ext}",
                      f"{test_prefix}{p}.{ext}",
                      f"{test_prefix}shot/{p}.{ext}",
                      f"{test_prefix}page_{p}.{ext}"
                  ]
                  found_this_page = False
                  for cu in candidate_urls:
                      try:
                          head_r = requests.head(cu, headers=headers, timeout=3)
                          if head_r.status_code == 200:
                              valid_book_pages.append(cu)
                              found_this_page = True
                              break
                      except:
                          pass
                  
                  # 如果连续多页都找不到，说明书已经结束了
                  if not found_this_page and p > 10:
                      # 再多试几次确认真的结束了
                      consecutive_misses = 0
                      for check_p in range(p, p + 3):
                          try:
                              test_u = f"{test_prefix}mobile/{check_p}.{ext}"
                              if requests.head(test_u, headers=headers, timeout=2).status_code != 200:
                                  consecutive_misses += 1
                          except:
                              consecutive_misses += 1
                      if consecutive_misses >= 3:
                          break
              
              if len(valid_book_pages) > 2:
                  page_urls = valid_book_pages
                  base_pattern_found = True
                  break

      # 如果智能探测没触发，退回到直接使用过滤后的所有图片列表
      if not base_pattern_found:
          page_urls = filtered_imgs

      # 去重
      page_urls = list(dict.fromkeys(page_urls))

      if not page_urls or len(page_urls) < 1:
          status.update(label="解析失败", state="error")
          st.error("未能自动探测到该图书的完整页面。")
          st.stop()

      st.write(f"3. 成功锁定共计 **{len(page_urls)}** 个页面，正在批量下载...")

      with tempfile.TemporaryDirectory() as tmpdir:
        image_files = []
        progress_bar = st.progress(0)

        valid_count = 0
        for i, img_url in enumerate(page_urls):
          try:
            r = requests.get(img_url, headers=headers, timeout=10)
            if r.status_code == 200 and len(r.content) > 3000:
              tmp_path = os.path.join(tmpdir, f"raw_{i}.jpg")
              with open(tmp_path, "wb") as f:
                f.write(r.content)

              # 用 PIL 验证并转换格式
              img_rgb = Image.open(tmp_path).convert("RGB")
              file_path = os.path.join(tmpdir, f"page_{valid_count+1:03d}.jpg")
              img_rgb.save(file_path, "JPEG", quality=95)

              image_files.append(file_path)
              valid_count += 1
          except Exception:
            pass
          progress_bar.progress((i + 1) / len(page_urls))

        if not image_files:
          status.update(label="下载失败", state="error")
          st.error("下载页面失败，未能获取到任何有效图片。")
          st.stop()

        st.write("4. 正在将所有页面无损合成为完整的 PDF 文件...")
        output_pdf = os.path.join(tmpdir, "flbook_output.pdf")

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
