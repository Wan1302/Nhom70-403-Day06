# Use Cases Test

File này dùng để test nhanh 3 luồng chính của agent:

- `faq_policy`
- `ticket_issue`
- `trip_plan`

Mỗi use case gồm:

- `Input`: câu user nhập để bắt đầu
- `Expected route`: nhánh mà router nên chọn
- `Expected behavior`: điều bot nên làm

---

## 1. FAQ / Quy định / Phí

### FAQ-01: Hỏi phí gửi xe máy

- Input: `Phí gửi xe máy ở Vinhomes Ocean Park là bao nhiêu?`
- Expected route: `faq_policy`
- Expected behavior:
- Bot gọi `search_faq_kb`
- Bot trả lời grounded từ dữ liệu FAQ
- Bot có nguồn ở cuối câu trả lời

### FAQ-02: Hỏi phí dịch vụ chung cư

- Input: `Phí dịch vụ tại Vinhomes Ocean Park bao nhiêu?`
- Expected route: `faq_policy`
- Expected behavior:
- Bot tìm đúng record về phí dịch vụ
- Bot tóm tắt ngắn gọn, không chép nguyên văn quá dài
- Bot đính kèm nguồn

### FAQ-03: Hỏi quy định thú cưng

- Input: `Căn hộ thuê ở đây có được mang thú cưng vào không?`
- Expected route: `faq_policy`
- Expected behavior:
- Bot nhận ra đây là nhóm `Hướng dẫn, thủ tục thuê`
- Bot trả lời theo dữ liệu về quy định thú cưng
- Bot có nguồn

### FAQ-04: Câu hỏi mơ hồ cần hỏi lại

- Input: `Phí ở đây thế nào?`
- Expected route: `faq_policy`
- Expected behavior:
- Bot chưa trả lời ngay
- Bot hỏi lại để làm rõ loại phí, ví dụ phí gửi xe hay phí dịch vụ

### FAQ-05: Không có dữ liệu chắc chắn

- Input: `Sân tennis ở Ocean Park mở tới mấy giờ?`
- Expected route: `faq_policy`
- Expected behavior:
- Nếu KB không có câu trả lời phù hợp, bot nói chưa đủ chắc chắn
- Bot không được bịa
- Bot có thể hỏi rõ hơn hoặc gợi ý chuyển sang hỗ trợ khác

---

## 2. Ticket / Sự cố

### TICKET-01: Báo sự cố thang máy

- Input: `Thang máy block A bị kẹt rồi`
- Expected route: `ticket_issue`
- Expected behavior:
- Bot bắt đầu luồng tạo ticket
- Bot hỏi thêm các trường còn thiếu như mức độ khẩn cấp, vị trí cụ thể, thời điểm, thông tin liên hệ
- Bot chưa tạo ticket ngay

### TICKET-02: Báo rò nước với nhiều thông tin sẵn có

- Input: `Nhà tôi ở tòa S2.05, căn 1203 bị rò nước từ trần từ sáng nay, tôi là Nam số 0901234567`
- Expected route: `ticket_issue`
- Expected behavior:
- Bot tự điền được nhiều field vào ticket draft
- Bot chỉ hỏi thêm các trường còn thiếu, ví dụ mức độ khẩn cấp hoặc loại sự cố

### TICKET-03: User xác nhận ticket

- Input:
- Turn 1: `Điện hành lang tầng 8 tòa S1.03 bị tắt, tôi là Linh số 0988111222`
- Turn 2: trả lời bổ sung các field bot hỏi
- Turn 3: `đúng`
- Expected route: `ticket_issue`
- Expected behavior:
- Bot tạo bản nháp ticket
- Bot hỏi xác nhận
- Sau khi user trả lời `đúng`, bot gọi `create_ticket`
- Bot trả về `ticket_id`

### TICKET-04: User sửa ticket sau bản nháp

- Input:
- Turn 1: `Có xe đỗ sai chỗ ở hầm B2`
- Turn 2: trả lời các câu hỏi bổ sung
- Turn 3: `Sửa lại giúp mình, không phải hầm B2 mà là hầm B1`
- Expected route: `ticket_issue`
- Expected behavior:
- Bot cập nhật lại `location`
- Bot sinh lại bản nháp mới
- Bot chưa tạo ticket trước khi user xác nhận

### TICKET-05: Dữ liệu chưa hợp lệ

- Input: `Nhà tôi bị hỏng nước, tôi là An số 123`
- Expected route: `ticket_issue`
- Expected behavior:
- Bot nhận diện số điện thoại có vẻ chưa hợp lệ
- Bot hỏi lại thông tin liên hệ đúng hơn

---

## 3. Trip Plan / Kế hoạch đi chơi

### TRIP-01: Bắt đầu rất mơ hồ

- Input: `Cuối tuần này lên kế hoạch đi chơi ở Ocean Park cho mình`
- Expected route: `trip_plan`
- Expected behavior:
- Bot không lập kế hoạch ngay
- Bot dùng `get_trip_requirements_helper`
- Bot hỏi lần lượt các dữ kiện còn thiếu như ngày đi, số người, điểm xuất phát, ngân sách, sở thích

### TRIP-02: Có khá đủ thông tin từ đầu

- Input: `Thứ bảy này lên lịch đi Ocean Park cho 4 người, đi từ Hà Nội, ngân sách vừa phải, ưu tiên chụp ảnh và ăn uống`
- Expected route: `trip_plan`
- Expected behavior:
- Bot trích xuất được phần lớn constraint
- Nếu còn thiếu thì chỉ hỏi ngắn thêm 1 câu
- Khi đủ dữ kiện, bot gọi `get_trip_context` và `build_itinerary`
- Bot trả về lịch trình theo buổi

### TRIP-03: Gia đình có trẻ em

- Input: `Chủ nhật này mình đi Ocean Park cùng gia đình 5 người, có 2 trẻ em, muốn đi nhẹ nhàng`
- Expected route: `trip_plan`
- Expected behavior:
- Bot lưu `audience` phù hợp với gia đình có trẻ em
- Bot ưu tiên địa điểm phù hợp trẻ em và thư giãn

### TRIP-04: User muốn chỉnh lại kế hoạch

- Input:
- Turn 1: `Lên kế hoạch đi chơi ở Ocean Park cho 3 người`
- Turn 2..n: trả lời các câu bot hỏi
- Turn cuối: `Cho mình chỉnh lại theo hướng tiết kiệm hơn`
- Expected route: `trip_plan`
- Expected behavior:
- Bot cập nhật constraint về ngân sách
- Bot tạo lại itinerary mới

### TRIP-05: Câu hỏi lẫn planner và transport

- Input: `Đi Ocean Park từ nội thành Hà Nội thì nên đi gì, tiện thể lên giúp mình lịch trình nửa ngày`
- Expected route: `trip_plan`
- Expected behavior:
- Bot vẫn đi theo nhánh planner
- Bot thu thập đủ dữ kiện tối thiểu
- Bot đưa ra gợi ý di chuyển trong phần context và build itinerary ngắn

---

## 4. Edge Cases

### EDGE-01: Intent không rõ

- Input: `Mình cần hỗ trợ`
- Expected route: `unknown`
- Expected behavior:
- Bot hỏi lại user muốn hỏi FAQ, tạo ticket, hay lên kế hoạch đi chơi

### EDGE-02: User đang ở giữa flow ticket nhưng trả lời ngắn

- Input:
- Turn 1: `Thang máy hỏng`
- Turn 2: `ở tòa S1.02`
- Expected route: `ticket_issue`
- Expected behavior:
- Router vẫn giữ flow ticket đang active
- Không nhảy sang FAQ hay trip

### EDGE-03: User đang ở giữa flow trip nhưng chỉ trả lời một field

- Input:
- Turn 1: `Lên kế hoạch đi Ocean Park cho mình`
- Turn 2: `đi từ Long Biên`
- Expected route: `trip_plan`
- Expected behavior:
- Bot cập nhật đúng `origin`
- Bot tiếp tục hỏi field còn thiếu khác

---

## 5. Bộ câu test nhanh

Bạn có thể copy từng câu dưới đây để test nhanh CLI:

```text
Phí gửi xe máy ở Vinhomes Ocean Park là bao nhiêu?
Phí ở đây thế nào?
Căn hộ có được mang thú cưng vào không?
Thang máy block A bị kẹt rồi
Nhà tôi ở tòa S2.05 căn 1203 bị rò nước từ sáng nay, tôi là Nam số 0901234567
đúng
Cuối tuần này lên kế hoạch đi chơi ở Ocean Park cho mình
Thứ bảy này lên lịch đi Ocean Park cho 4 người, đi từ Hà Nội, ngân sách vừa phải, ưu tiên chụp ảnh và ăn uống
Cho mình chỉnh lại theo hướng tiết kiệm hơn
Mình cần hỗ trợ
```
