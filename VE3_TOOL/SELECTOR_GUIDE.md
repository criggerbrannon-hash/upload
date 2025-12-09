# Hướng dẫn tìm và cập nhật CSS Selectors cho Flows Lab

## Mục lục
1. [Giới thiệu về CSS Selectors](#1-giới-thiệu-về-css-selectors)
2. [Cách sử dụng DevTools](#2-cách-sử-dụng-devtools)
3. [Các loại Selector phổ biến](#3-các-loại-selector-phổ-biến)
4. [Hướng dẫn từng bước](#4-hướng-dẫn-từng-bước)
5. [Cập nhật file flowslab_automation.py](#5-cập-nhật-file-flowslab_automationpy)
6. [Mẹo và Best Practices](#6-mẹo-và-best-practices)

---

## 1. Giới thiệu về CSS Selectors

CSS Selector là cách để "chỉ định" một element HTML trên trang web. Selenium dùng selector để tìm và tương tác với các element như:
- Ô nhập liệu (input, textarea)
- Nút bấm (button)
- Hình ảnh, video
- Các container chứa nội dung

### Ví dụ:
```html
<button id="generate-btn" class="btn primary-btn" data-action="generate">
    Generate Image
</button>
```

Có thể được chọn bằng:
- `#generate-btn` (theo ID)
- `.btn.primary-btn` (theo class)
- `button[data-action='generate']` (theo attribute)
- `button` (theo tag - không khuyến khích vì không unique)

---

## 2. Cách sử dụng DevTools

### Bước 1: Mở DevTools
1. Mở Chrome/Edge, truy cập `https://app.flowslab.io`
2. Nhấn **F12** hoặc **Ctrl+Shift+I** (Windows) / **Cmd+Option+I** (Mac)

### Bước 2: Chọn Element
1. Click vào icon **Select element** (mũi tên ở góc trái DevTools)
   - Hoặc nhấn **Ctrl+Shift+C**
2. Di chuột lên element cần tìm trên trang
3. Click vào element → DevTools sẽ highlight code HTML

![DevTools Select Element](https://i.imgur.com/example.png)

### Bước 3: Lấy Selector

**Cách 1 - Copy tự động:**
1. Right-click vào element trong tab Elements
2. Chọn **Copy** → **Copy selector**

**Cách 2 - Tự viết (khuyến khích):**
Nhìn vào HTML và xác định attribute unique:
```html
<input type="email" id="login-email" class="form-control auth-input" placeholder="Enter email">
```

Selector tốt nhất theo thứ tự ưu tiên:
1. `#login-email` (ID - unique nhất)
2. `input[type='email']` (attribute unique)
3. `.auth-input` (class nếu unique)
4. `input.form-control.auth-input` (kết hợp)

### Bước 4: Test Selector
Trong DevTools Console (tab Console), gõ:
```javascript
document.querySelector("#login-email")
// Nếu trả về element → selector đúng
// Nếu trả về null → selector sai
```

---

## 3. Các loại Selector phổ biến

### 3.1. Selector theo ID
```css
#element-id
```
- **Ưu điểm:** Unique nhất, nhanh nhất
- **Nhược điểm:** Không phải element nào cũng có ID

### 3.2. Selector theo Class
```css
.class-name
.class1.class2     /* element có cả 2 class */
```

### 3.3. Selector theo Attribute
```css
input[type='email']
button[data-action='submit']
[name='username']
[href*='login']    /* href chứa 'login' */
[class^='btn-']    /* class bắt đầu bằng 'btn-' */
```

### 3.4. Selector theo Tag + Class/Attribute
```css
input.form-control
button.btn-primary
textarea[name='prompt']
```

### 3.5. Selector lồng nhau (Descendant)
```css
.form-container input
#login-form .submit-btn
div.result-area img
```

### 3.6. Selector trực tiếp con (Child)
```css
.container > .child     /* chỉ con trực tiếp */
```

### 3.7. Selector nhiều lựa chọn
```css
#email, input[type='email'], .email-input
```
Tool sẽ thử từng selector cho đến khi tìm được.

---

## 4. Hướng dẫn từng bước

### 4.1. Tìm Selector cho Trang Login

1. Mở `https://app.flowslab.io/login`
2. Dùng DevTools inspect ô **Email**:
   ```html
   <!-- Ví dụ HTML có thể thấy -->
   <input type="email" class="auth-field" name="email" placeholder="Email">
   ```
   → Selector: `input[type='email']` hoặc `input[name='email']`

3. Inspect ô **Password**:
   ```html
   <input type="password" class="auth-field" name="password">
   ```
   → Selector: `input[type='password']` hoặc `input[name='password']`

4. Inspect nút **Login**:
   ```html
   <button type="submit" class="btn login-btn">Sign In</button>
   ```
   → Selector: `button[type='submit']` hoặc `.login-btn`

5. Xác định **indicator đã login thành công**:
   - Tìm element chỉ xuất hiện sau khi login (ví dụ: avatar, menu user, dashboard)
   ```html
   <div class="user-avatar">...</div>
   <nav class="dashboard-nav">...</nav>
   ```
   → Selector: `.user-avatar` hoặc `.dashboard-nav`

### 4.2. Tìm Selector cho Trang Tạo Ảnh

1. Mở trang tạo ảnh (image generation)
2. Inspect **ô nhập prompt**:
   ```html
   <textarea class="prompt-textarea" placeholder="Enter your prompt..."></textarea>
   ```
   → Selector: `textarea.prompt-textarea` hoặc `textarea[placeholder*='prompt']`

3. Inspect **nút upload ảnh tham chiếu** (nếu có):
   ```html
   <input type="file" class="reference-upload" accept="image/*">
   ```
   → Selector: `input[type='file'].reference-upload` hoặc `input[accept='image/*']`

4. Inspect **nút Generate**:
   ```html
   <button class="generate-btn primary">Generate</button>
   ```
   → Selector: `.generate-btn` hoặc `button.generate-btn`

5. Inspect **loading indicator**:
   ```html
   <div class="loading-spinner active">...</div>
   <div class="generating-overlay">...</div>
   ```
   → Selector: `.loading-spinner` hoặc `.generating-overlay`

6. Inspect **kết quả ảnh**:
   ```html
   <div class="result-container">
       <img src="..." class="generated-image">
   </div>
   ```
   → Selector container: `.result-container`
   → Selector ảnh: `.result-container img` hoặc `.generated-image`

7. Inspect **nút Download**:
   ```html
   <button class="download-btn" data-action="download">Download</button>
   ```
   → Selector: `.download-btn` hoặc `button[data-action='download']`

### 4.3. Tìm Selector cho Trang Tạo Video

Tương tự như trang tạo ảnh, tìm:
- Upload ảnh nguồn
- Ô nhập video prompt
- Nút Generate
- Loading indicator
- Kết quả video
- Nút Download

---

## 5. Cập nhật file flowslab_automation.py

### Bước 1: Mở file
```
VE3_TOOL/modules/flowslab_automation.py
```

### Bước 2: Tìm class Selectors (khoảng dòng 51-92)

### Bước 3: Cập nhật từng selector

**Ví dụ cập nhật:**

```python
class Selectors:
    """
    CSS selectors for Flows Lab UI elements.
    CẬP NHẬT: [Ngày bạn cập nhật]
    """

    # ----- Login Page -----
    # TODO: Thay thế bằng selector thực tế từ Flows Lab
    LOGIN_EMAIL_INPUT = "input[name='email']"  # ← Cập nhật
    LOGIN_PASSWORD_INPUT = "input[name='password']"  # ← Cập nhật
    LOGIN_SUBMIT_BUTTON = "button[type='submit']"  # ← Cập nhật
    LOGIN_SUCCESS_INDICATOR = ".dashboard, .user-menu"  # ← Cập nhật

    # ----- Image Generation Page -----
    IMG_PROMPT_TEXTAREA = "textarea.prompt-input"  # ← Cập nhật
    IMG_REFERENCE_UPLOAD = "input[type='file']"  # ← Cập nhật
    IMG_GENERATE_BUTTON = "button.generate-btn"  # ← Cập nhật
    IMG_RESULT_CONTAINER = ".result-container"  # ← Cập nhật
    IMG_DOWNLOAD_BUTTON = ".download-btn"  # ← Cập nhật
    IMG_LOADING_INDICATOR = ".loading-spinner, .generating"  # ← Cập nhật

    # ----- Video Generation Page -----
    VID_SOURCE_IMAGE_UPLOAD = "input[type='file']"  # ← Cập nhật
    VID_PROMPT_TEXTAREA = "textarea.video-prompt"  # ← Cập nhật
    VID_GENERATE_BUTTON = "button.generate-video"  # ← Cập nhật
    VID_RESULT_CONTAINER = ".video-result"  # ← Cập nhật
    VID_DOWNLOAD_BUTTON = ".download-video-btn"  # ← Cập nhật
    VID_LOADING_INDICATOR = ".video-generating"  # ← Cập nhật
```

### Bước 4: Test từng selector

Chạy tool ở chế độ debug:
```python
# Thêm vào code tạm thời để test
client.driver.get("https://app.flowslab.io/login")
element = client._wait_and_find(Selectors.LOGIN_EMAIL_INPUT)
print(f"Found: {element}")  # Nếu None → selector sai
```

---

## 6. Mẹo và Best Practices

### 6.1. Ưu tiên Selector ổn định
Thứ tự ưu tiên từ ổn định nhất đến dễ thay đổi:
1. **ID** (`#element-id`) - Ổn định nhất
2. **name attribute** (`[name='field']`) - Thường không đổi
3. **data-* attributes** (`[data-testid='button']`) - Dành cho testing
4. **type + class** (`input.form-field`) - Khá ổn định
5. **Class alone** (`.class-name`) - Có thể thay đổi
6. **Tag alone** (`button`, `input`) - Không unique

### 6.2. Tránh Selector động
❌ **Tránh:**
```css
#react-root-123456    /* ID có số random */
.css-1abc2de          /* Class tự động generate */
div > div > div > span /* Quá phụ thuộc vào cấu trúc */
```

✅ **Nên dùng:**
```css
[data-testid='login-button']
input[placeholder='Enter email']
.login-form input[type='email']
```

### 6.3. Sử dụng nhiều selector backup
```python
# Tool sẽ thử từng selector theo thứ tự
LOGIN_EMAIL = "input#email, input[name='email'], input[type='email']"
```

### 6.4. Xử lý element động (load sau)
Nếu element xuất hiện sau khi page load (AJAX), tăng timeout:
```python
element = client._wait_and_find(selector, timeout=20)
```

### 6.5. Xử lý iframe
Nếu element nằm trong iframe:
```python
# Chuyển vào iframe trước
iframe = driver.find_element(By.CSS_SELECTOR, "iframe.content-frame")
driver.switch_to.frame(iframe)

# Tìm element trong iframe
element = driver.find_element(By.CSS_SELECTOR, ".target-element")

# Quay về main page
driver.switch_to.default_content()
```

### 6.6. Screenshot để debug
Khi selector không hoạt động:
```python
client.take_screenshot("debug_login_page")
# Xem screenshot trong thư mục debug_screenshots/
```

---

## Checklist cập nhật Selector

- [ ] Login page
  - [ ] Email input
  - [ ] Password input
  - [ ] Submit button
  - [ ] Success indicator (sau login)
  - [ ] Error message (login failed)

- [ ] Image Generation page
  - [ ] Prompt textarea
  - [ ] Reference image upload (nếu có)
  - [ ] Generate button
  - [ ] Loading indicator
  - [ ] Result container
  - [ ] Download button

- [ ] Video Generation page
  - [ ] Source image upload
  - [ ] Video prompt textarea
  - [ ] Generate button
  - [ ] Loading indicator
  - [ ] Result container
  - [ ] Download button

- [ ] Common
  - [ ] Cookie consent (nếu có)
  - [ ] Modal close button
  - [ ] Error toast/message

---

## Cần hỗ trợ?

Nếu gặp khó khăn:
1. Chụp screenshot HTML của element
2. Ghi lại các selector đã thử
3. Mô tả lỗi gặp phải
