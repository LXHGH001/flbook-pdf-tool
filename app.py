import os
import tempfile
from PIL import Image
import img2pdf
import streamlit as st

# 尝试导入 playwright
try:
  from playwright.sync_api import sync_playwright
except ImportError:
  sync_playwright = None

st.set_page_config(
    page_title="FLBook & 云展网转 PDF 工具", page_icon="📚", layout="centered"
)

st.title("📚 FLBook & 云展网电子书转 PDF 工具")
st.markdown(
    "输入电子书链接，使用**浏览器内核全自动渲染抓取**并生成高质量 PDF！支持"
    " **FLBook (`flbook.com.cn`)** 和 **云展网 (`yunzhan365.com`)**。"
)

url = st.text_input("请输入电子书网址 (URL):", "https://book.yunzhan365.com/yhqe/uiqi/mobile/index.html")
total_pages = st.number_input("预估图书总页数 (用于控制浏览翻页次数):", min_value=1, max_value=500, value=20)

if st.button("启动浏览器内核抓取并生成 PDF", type="primary", use_container_width=True):
  if not url:
    st.warning("请输入有效的网址！")
  elif not sync_playwright:
    st.error("环境未安装 playwright 依赖，请检查 requirements.txt！")
  else:
    with st.status("正在通过浏览器内核渲染提取...", expanded=True) as status:
      st.write("1. 正在启动云端无头 Chromium 浏览器...")

      image_urls_captured = []

      try:
        with sync_playwright() as p:
          # 启动浏览器
          browser = p.chromium.launch(
              headless=True,
              args=[
                  "--no-sandbox",
                  "--disable-setuid-sandbox",
                  "--disable-dev-shm-usage",
              ],
          )
          context = browser.new_context(
              user_agent=(
                  "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
                  "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 "
                  "Mobile/15E148 Safari/604.1"
              ),
              viewport={"width": 430, "height": 932},
          )
          page = context.new_page()

          # 监听网络请求，拦截所有图片资源
          def handle_request(request):
            req_url = request.url.lower()
            # 捕获云展网或FLBook的高清书页图片
            if any(
                k in req_url
                for k in ["mobile", "files/mobile", "ext/page", "large", "book"]
            ):
              if any(req_url.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                if req_url not in image_urls_captured:
                  image_urls_captured.append(request.url)

          page.on("request", handle_request)

          st.write("2. 正在打开网页并等待翻页加载...")
          page.goto(url, timeout=30000)
          
          # 等待页面基础元素加载
          page.wait_for_timeout(4000)

          st.write(f"3. 正在模拟自动翻页（共计 {total_pages} 页）以触发图片加载...")
          progress_bar = st.progress(0)

          # 模拟键盘向右键或点击翻页，强制让浏览器加载每一页
          for i in range(int(total_pages)):
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(600)  # 稍微停顿让图片加载
            progress_bar.progress(min((i + 1) / total_pages, 1.0))

          # 额外等待最后几张图加载完成
          page.wait_for_timeout(3000)
          browser.close()

      except Exception as e:
        status.update(label="浏览器渲染出错", state="error")
        st.error(f"详细错误: {e}")
        st.stop()

      st.write(f"4. 浏览器拦截到 {len(image_urls_captured)} 个图片资源，开始下载清洗...")

      if not image_urls_captured:
        status.update(label="未捕获到图片", state="error")
        st.error(
            "未能从该页面拦截到有效书页图片。该链接可能需要登录账号或包含访问密码。"
        )
        st.stop()

      with tempfile.TemporaryDirectory() as tmpdir:
        image_files = []
        valid_count = 0

        for i, img_url in enumerate(image_urls_captured):
          try:
            # 使用获取到的浏览器 cookie/headers 重新下载高清图
            r = requests.get(img_url, timeout=5)
            if r.status_code == 200 and len(r.content) > 3000:
              tmp_path = os.path.join(tmpdir, f"raw_{i}.jpg")
              with open(tmp_path, "wb") as f:
                f.write(r.content)

              img_rgb = Image.open(tmp_path).convert("RGB")
              file_path = os.path.join(tmpdir, f"page_{valid_count+1:03d}.jpg")
              img_rgb.save(file_path, "JPEG", quality=95)

              image_files.append(file_path)
              valid_count += 1
          except:
            pass

        if not image_files:
          status.update(label="下载失败", state="error")
          st.error("成功拦截了图片链接，但在下载时被服务器拒绝。")
          st.stop()

        st.write(f"5. 成功整理 {len(image_files)} 页，正在无损合成为 PDF...")
        output_pdf = os.path.join(tmpdir, "yunzhan_full.pdf")

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
        use_container_width=True,
    )
