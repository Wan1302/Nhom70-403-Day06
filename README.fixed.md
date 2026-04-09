## Vinhomes Agent Demo

LangGraph agent loop cho 3 luồng:

- FAQ / quy định / phí dịch vụ
- Tạo ticket sự cố
- Lên kế hoạch đi chơi ở Vinhomes Ocean Park Gia Lâm

### Cấu trúc

- `vinhomes_agent/tools.py`: các tool nội bộ
- `vinhomes_agent/state.py`: shared state cho LangGraph
- `vinhomes_agent/graph.py`: router và các node của graph
- `vinhomes_agent/main.py`: CLI demo
- `vinhomes_agent/web.py`: FastAPI app cho bản web
- `data/vinhomes_faq_selected.csv`: dữ liệu FAQ đã lọc
- `data/vinhomes_places.json`: dữ liệu địa điểm cho trip planner

### Cài đặt

```bash
pip install -r requirements.txt
```

Tạo file `.env` từ `.env_exp` rồi điền các biến phù hợp:

```env
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o
OPENWEATHER_API_KEY=optional
```

Ghi chú:

- `OPENAI_API_KEY`: bắt buộc để chạy agent
- `OPENAI_MODEL`: tùy chọn, mặc định là `gpt-4o`
- `OPENWEATHER_API_KEY`: tùy chọn, dùng để lấy thời tiết thật cho trip planner

### Tạo môi trường riêng

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Hoặc dùng script:

```powershell
.\scripts\setup_venv.ps1
.\.venv\Scripts\Activate.ps1
```

Nếu Python `3.14` cài package lỗi, nên dùng Python `3.11` hoặc `3.12` để ổn định hơn với hệ LangChain/LangGraph.

### Check phiên bản package

```powershell
python .\scripts\check_env.py
```

### Tạo lock file

Sau khi đã cài xong môi trường:

```powershell
.\scripts\freeze_lock.ps1
```

Lệnh này sẽ sinh `requirements.lock.txt`.

### Chạy thử CLI

```bash
python -m vinhomes_agent.main
```

### Chạy bản web

```bash
uvicorn vinhomes_agent.web:app --reload
```

Sau đó mở:

```text
http://127.0.0.1:8000
```

### Các trang chính

- `http://127.0.0.1:8000/`: landing page giới thiệu demo
- `http://127.0.0.1:8000/chat`: chat workspace, có lịch sử phiên, ping backend, gửi tin nhắn dạng stream, ghim/đổi tên/xóa phiên và gửi feedback
- `http://127.0.0.1:8000/sessions`: dashboard quản lý phiên, xem trace lượt gần nhất, metrics và snapshot state

### Giao diện web

- landing page giới thiệu sản phẩm
- trang chat riêng tập trung vào hội thoại
- sidebar lịch sử session ngay trong trang chat
- trang quản lý phiên riêng để xem dashboard của từng session
- lịch sử session được lưu vào `data/chat_sessions.json`
- feedback người dùng được lưu vào `data/chat_feedback.jsonl`
- ticket mock được lưu vào `data/mock_tickets.jsonl`

### Xem token và thời gian

CLI hiện sẽ in metrics sau mỗi lượt chạy:

- node nào đã chạy
- thời gian xử lý theo `ms`
- `input_tokens`
- `output_tokens`
- `total_tokens`

Trang `/sessions` hiển thị thêm:

- trace lượt chat gần nhất
- bảng metrics của lượt gần nhất
- snapshot state để kiểm tra agent đang giữ dữ liệu gì

### Ghi chú

- Router và các node extract dùng model lấy từ biến `OPENAI_MODEL`, mặc định là `gpt-4o`.
- FAQ search ưu tiên dữ liệu cục bộ trong repo, nếu không có kết quả thì fallback sang web search.
- Ticket hiện được lưu mock vào `data/mock_tickets.jsonl`.
- Trip planner dùng dữ liệu địa điểm local kết hợp thời tiết từ OpenWeather nếu có `OPENWEATHER_API_KEY`.
