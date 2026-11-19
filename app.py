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

      st.write("2. 正在解析页面图片序列...")

      # 更精确的匹配：寻找形如 mobile/... 或类似翻页书页面的图片链接
      # 许多 FLBook 页面图片存放在 /files/mobile/ 或包含类似序列
      # 同时尝试匹配页面中所有高分辨率图片
      img_urls = re.findall(r'https?://[^\s<>"]+?\.(?:jpg|jpeg|png)', html)

      page_urls = []
      for u in img_urls:
        # 过滤掉头像、logo、小图标等，只保留符合书页特征的链接
        u_lower = u.lower()
        if any(
            k in u_lower
            for k in ["mobile", "shot", "page", "files/files", "book"]
        ):
          if (
              "logo" not in u_lower
              and "icon" not in u_lower
              and "avatar" not in u_lower
          ):
            if u not in page_urls:
              page_urls.append(u)

      # 如果正则过滤后为空，回退到匹配所有较大图片
      if not page_urls:
        page_urls = [
            u
            for u in img_urls
            if "logo" not in u.lower() and "icon" not in u.lower()
        ]

      # 去重并排序
      page_urls = list(dict.fromkeys(page_urls))

      if not page_urls or len(page_urls) < 2:
        status.update(label="解析失败", state="error")
        st.error(
            "未能自动从该网页提取到有效的电子书页面图片。该图书可能加密或结构特殊。"
        )
        st.stop()

      st.write(
          f"3. 检测到约 {len(page_urls)} 个潜在页面，正在批量下载并校验..."
      )

      with tempfile.TemporaryDirectory() as tmpdir:
        image_files = []
        progress_bar = st.progress(0)

        valid_count = 0
        for i, img_url in enumerate(page_urls):
          try:
            r = requests.get(img_url, headers=headers, timeout=10)
            if r.status_code == 200 and len(r.content) > 5000:  # 排除小图标
              # 校验是否为真正可读的图片
              tmp_path = os.path.join(tmpdir, f"raw_{i}.jpg")
              with open(tmp_path, "wb") as f:
                f.write(r.content)

              # 用 PIL 验证图片有效性
              img = Image.open(tmp_path)
              img.verify()

              # 如果验证通过，保存为正式处理的页面
              file_path = os.path.join(
                  tmpdir, f"page_{valid_count+1:03d}.jpg"
              )
              # 如果原图是 RGBA/PNG，转换成 RGB 以便 img2pdf 处理
              img_rgb = Image.open(tmp_path).convert("RGB")
              img_rgb.save(file_path, "JPEG")

              image_files.append(file_path)
              valid_count += 1
          except Exception:
            # 自动跳过无效或损坏的图片链接
            pass
          progress_bar.progress((i + 1) / len(page_urls))

        if not image_files:
          status.update(label="转换失败", state="error")
          st.error(
              "未能成功下载或识别任何有效的书页图片，请检查链接是否正确。"
          )
          st.stop()

        st.write("4. 正在将页面图片无损合成为 PDF 文件...")
        output_pdf = os.path.join(tmpdir, "flbook_output.pdf")

        with open(output_pdf, "wb") as f:
          f.write(img2pdf.convert(image_files))

        with open(output_pdf, "rb") as f:
          pdf_bytes = f.read()

        status.update(label="转换成功！", state="complete")

    st.success("🎉 电子书已成功转换为 PDF！")
    st.download_button(
        label="📥 点击下载生成的 PDF 文件",
        data=pdf_bytes,
        file_name="flbook_converted.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
