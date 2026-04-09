# SPEC - AI Product Hackathon

**Nhóm:** Nhom70
**Track:** ☐ VinFast · ☐ Vinmec · ☐ VinUni-VinSchool · ☐ XanhSM · ☑ Open
<br>
**Problem statement (1 câu):** Cư dân và khách tại Vinhomes thường mất thời gian khi cần tra cứu FAQ/chính sách, gửi phản ánh sự cố, hoặc lên kế hoạch đi chơi ở Ocean Park; chatbot AI giúp định tuyến đúng nhu cầu, hỏi bổ sung khi thiếu thông tin, tra cứu dữ liệu đúng lúc, tạo ticket mock sau xác nhận và sinh itinerary phù hợp hơn.

---

## 1. AI Product Canvas

|   | Value | Trust | Feasibility |
|---|-------|-------|-------------|
| **Câu hỏi** | User nào? Pain gì? AI giải gì? | Khi AI sai thì sao? User sửa bằng cách nào? | Cost/latency bao nhiêu? Risk chính? |
| **Trả lời** | User chính gồm cư dân, khách thuê và người muốn đi chơi ở Vinhomes Ocean Park. Họ có 3 nhu cầu lặp lại: hỏi FAQ/chính sách, báo sự cố để tạo ticket, và xin gợi ý lịch trình đi chơi. Hiện tại thông tin bị phân tán giữa app, hotline, thông báo nội khu và trải nghiệm thủ công. Prototype AI đóng vai trò router + assistant: nhận diện đúng intent, hỏi làm rõ nếu thiếu dữ liệu, trả lời FAQ từ KB, thu thập đủ field để tạo ticket, hoặc chạy planner loop để dựng itinerary. | Khi AI sai, user có thể sửa ngay trong từng flow. Với FAQ, user bổ sung khu/tòa/loại phí hoặc phản hồi là câu trả lời chưa đúng. Với ticket, user sửa loại sự cố, mức độ khẩn cấp, vị trí hoặc thông tin liên hệ trước khi tạo. Với trip planner, user đổi ngày đi, số người, ngân sách hay sở thích để bot lên lại kế hoạch. Ngoài ra sản phẩm đã có feedback `like/dislike`, trace, metrics và snapshot state để theo dõi lỗi ở mức phiên chat. | Cost phụ thuộc số lần gọi LLM và số vòng lặp planner. Mục tiêu latency: FAQ đơn giản <3s, ticket ask/confirm <8s, trip plan nháp <10s. Risk chính: FAQ dùng dữ liệu cũ hoặc web fallback kém tin cậy, hiểu sai mức độ khẩn cấp của ticket, planner dựng itinerary khi chưa đủ constraint, và lưu PII trong session/log nếu không kiểm soát tốt. |

**Automation hay augmentation?** ☐ Automation · ☑ Augmentation
<br>
Justify: Augmentation - chatbot hỗ trợ định tuyến, hỏi làm rõ, tạo ticket nháp và dựng itinerary nháp; user vẫn xác nhận ở bước ticket, còn các câu hỏi mơ hồ hoặc không chắc chắn sẽ được hỏi lại thay vì tự động quyết định.

**Learning signal:**

1. User correction đi vào đâu? Correction được lưu theo từng intent `faq_policy`, `ticket_issue`, `trip_plan`, gồm câu hỏi gốc, output bot, phần user sửa, bước nào bot fail và đáp án/constraint đúng sau cùng. Hiện prototype đã lưu feedback vào `data/chat_feedback.jsonl` và lưu session/state vào `data/chat_sessions.json`.
2. Product thu signal gì để biết tốt lên hay tệ đi? Tỷ lệ router chọn đúng intent, tỷ lệ FAQ cần clarify, tỷ lệ FAQ phải fallback web, tỷ lệ ticket đủ field trước khi create, tỷ lệ user xác nhận ticket draft, số vòng lặp trung bình của trip planner, tỷ lệ user chấp nhận itinerary đầu tiên, latency và token theo node, CSAT/feedback sau chat.
3. Data thuộc loại nào? ☑ User-specific · ☑ Domain-specific · ☑ Real-time · ☑ Human-judgment · ☑ Khác: Workflow-specific
<br>
   Có marginal value không? Có. Model nền biết tiếng Việt và kiến thức chung, nhưng không biết chính xác FAQ nội bộ Vinhomes, schema ticket của prototype, logic validate, hay preference thực tế của user khi đi chơi Ocean Park.

---

## 2. User Stories - 4 paths

Mỗi feature chính = 1 bảng. AI trả lời xong -> chuyện gì xảy ra?

### Feature 1: Hỏi đáp FAQ, chính sách và tiện ích

**Trigger:** User hỏi: "Phí gửi xe máy là bao nhiêu?", "Bể bơi mở cửa lúc mấy giờ?", "Có được nuôi thú cưng không?"

| Path | Câu hỏi thiết kế | Mô tả |
|------|-------------------|-------|
| Happy - AI đúng, tự tin | User thấy gì? Flow kết thúc ra sao? | Bot route đúng sang `faq_policy`, trích xuất FAQ query, hỏi làm rõ nếu cần, ưu tiên search KB nội bộ rồi trả lời ngắn gọn bằng tiếng Việt. Nếu có docs phù hợp, bot dùng LLM để diễn đạt lại từ ngữ cảnh retrieved docs. |
| Low-confidence - AI không chắc | System báo "không chắc" bằng cách nào? User quyết thế nào? | Nếu câu hỏi còn mơ hồ như thiếu loại phí/khu/tòa, bot không đoán mà hỏi lại đúng 1 câu ngắn. Nếu user trả lời kiểu "gì cũng được", bot giữ query cũ và ưu tiên search thay vì hỏi lặp. |
| Failure - AI sai | User biết AI sai bằng cách nào? Recover ra sao? | Bot có thể trả lời từ dữ liệu web fallback hoặc dữ liệu không đúng category. User phát hiện vì không khớp thông báo nội bộ và báo lại. Bot xin lỗi, ghi nhận correction và đề nghị user xác minh lại bằng nguồn chính thức. |
| Correction - user sửa | User sửa bằng cách nào? Data đó đi vào đâu? | User bổ sung khu/tòa, dán thông báo hoặc nói lại điều khoản đúng. Dữ liệu vào correction log/feedback để đội vận hành cập nhật KB và cải thiện prompt extract. |

### Feature 2: Gửi phản ánh và tạo ticket cho ban quản lý

**Trigger:** User nhắn: "Thang máy block A bị kẹt", "Nhà tôi bị rò nước", "Có xe đậu sai chỗ ở hầm B2".

| Path | Câu hỏi thiết kế | Mô tả |
|------|-------------------|-------|
| Happy - AI đúng, tự tin | User thấy gì? Flow kết thúc ra sao? | Bot route đúng sang `ticket_issue`, trích xuất được các field đã có, gọi schema/validation để biết còn thiếu gì, hỏi tiếp trường còn thiếu, tóm tắt ticket draft và chỉ tạo ticket sau khi user xác nhận. Ticket được lưu mock vào `data/mock_tickets.jsonl`. |
| Low-confidence - AI không chắc | System báo "không chắc" bằng cách nào? User quyết thế nào? | Nếu mô tả mơ hồ như "chỗ này hỏng rồi", bot không tự gán loại sự cố mà hỏi rõ đó là điện, nước, thang máy, an ninh hay vệ sinh. Flow quay lại validate sau khi user bổ sung. |
| Failure - AI sai | User biết AI sai bằng cách nào? Recover ra sao? | Bot draft ticket sai loại sự cố hoặc sai mức độ khẩn cấp. User nhìn thấy ở màn hình tóm tắt trước khi gửi và sửa lại. Nếu đã tạo, correction vẫn được lưu để cải thiện extraction/validation. |
| Correction - user sửa | User sửa bằng cách nào? Data đó đi vào đâu? | User chỉnh `issue_type`, `urgency`, `location`, `description` hoặc `contact_phone`. Dữ liệu được ghi vào log/session để cải thiện prompt extract và các rule validate trong tương lai. |

### Feature 3: Lên kế hoạch đi chơi ở Vinhomes Ocean Park

**Trigger:** User hỏi: "Cuối tuần này mình muốn đi Ocean Park 2 người, ngân sách vừa phải, gợi ý lịch trình giúp mình."

| Path | Câu hỏi thiết kế | Mô tả |
|------|-------------------|-------|
| Happy - AI đúng, tự tin | User thấy gì? Flow kết thúc ra sao? | Bot route đúng sang `trip_plan`, trích xuất constraint đã có, dùng `trip_agent_decide` để chọn đúng bước tiếp theo, gọi helper/context/itinerary rồi trả ra lịch trình theo buổi với chi phí, ngân sách còn lại/vượt ngân sách, thời tiết và cách di chuyển. |
| Low-confidence - AI không chắc | System báo "không chắc" bằng cách nào? User quyết thế nào? | Nếu user nói quá ngắn như "lên plan đi chơi giúp mình", bot không dựng plan ngay mà hỏi thêm ngày đi, số người, ngân sách và sở thích. Chỉ khi đủ constraint tối thiểu bot mới build itinerary. |
| Failure - AI sai | User biết AI sai bằng cách nào? Recover ra sao? | Bot lên kế hoạch lệch nhu cầu, ví dụ quá đắt, không phù hợp trẻ em hoặc không thuận tiện di chuyển. User phản hồi như "bớt chi phí" hoặc "có trẻ em" để bot reset context và chạy lại planner loop. |
| Correction - user sửa | User sửa bằng cách nào? Data đó đi vào đâu? | User thay đổi `trip_date`, `party_size`, `budget_level`, `budget_amount_vnd`, `origin` hoặc `interests`. Dữ liệu được giữ trong state và lưu theo session để biết constraint nào bot thường bỏ sót, bước nào gây nhiều revision nhất. |

---

## 3. Eval metrics + threshold

**Optimize precision hay recall?** ☑ Precision · ☐ Recall
<br>
Tại sao? Với FAQ và ticket, trả lời sai nhưng nghe rất tự tin nguy hiểm hơn nhiều so với việc hỏi lại. Flow hiện tại được thiết kế để khi thiếu thông tin thì phải clarify, validate hoặc gọi tool đúng lúc thay vì đoán. Với trip planner có thể chấp nhận revision, nhưng cũng không nên dựng itinerary khi chưa đủ constraint tối thiểu.

Nếu sai ngược lại thì chuyện gì xảy ra? Nếu quá ưu tiên precision mà hỏi lại quá nhiều, user sẽ thấy chatbot chậm, flow FAQ kém tự nhiên và trip planner mất cảm giác trợ lý. Vì vậy cần precision cao ở quyết định quan trọng, nhưng vẫn giữ số vòng clarify/tool loop ở mức hợp lý.

| Metric | Threshold | Red flag (dừng khi) |
|--------|-----------|---------------------|
| Intent classification accuracy cho `faq_policy` / `ticket_issue` / `trip_plan` | ≥85% trong pilot | <75% trong 1 tuần hoặc nhầm nhiều giữa ticket và FAQ |
| FAQ clarification rate | 20-45% câu hỏi FAQ cần hỏi thêm | >60% nghĩa là prompt extract hoặc router đang yếu |
| FAQ grounded answer rate | ≥95% với câu hỏi về phí, chính sách, nội quy | Có câu trả lời quan trọng không grounded vào KB hoặc phụ thuộc web fallback không kiểm chứng |
| Ticket draft completion before create | ≥90% ticket được đủ field trước khi tạo | Ticket tạo ra vẫn thiếu trường bắt buộc hoặc phải sửa nhiều sau khi tóm tắt |
| Ticket confirmation acceptance rate | ≥80% user xác nhận draft sau tối đa 1 lần sửa | <60% nghĩa là extract/summary sai nhiều |
| Trip first-plan acceptance rate | ≥60% user chấp nhận itinerary đầu tiên hoặc chỉ sửa nhẹ | <40% nghĩa là bot build plan khi chưa hiểu đúng constraint |
| Avg. trip loop steps | ≤4 bước tool/decision cho mỗi request trip | >6 bước trung bình, trải nghiệm sẽ dài và tốn cost |
| CSAT / feedback positive rate | ≥4/5 hoặc ≥80% feedback tích cực | <3.5/5 hoặc feedback tiêu cực kéo dài 2 tuần |

---

## 4. Top 3 failure modes

*Liệt kê cách product có thể fail - không phải list features.*
*"Failure mode nào user KHÔNG BIẾT bị sai? Đó là cái nguy hiểm nhất."*

| # | Trigger | Hậu quả | Mitigation |
|---|---------|---------|------------|
| 1 | User hỏi FAQ/chính sách nhưng KB thiếu dữ liệu mới hoặc bot phải fallback web | AI trả lời sai nhưng nghe chắc chắn, user làm theo thông tin cũ hoặc không chính thức | Tách rõ bước clarify và bước search, ưu tiên KB nội bộ, chỉ fallback web 1 lần, nếu vẫn không chắc thì trả lời là chưa có dữ liệu phù hợp |
| 2 | User mô tả sự cố mơ hồ hoặc khẩn cấp nhưng bot extract sai `issue_type` hay `urgency` | Ticket đi sai hướng hoặc xử lý chậm, ảnh hưởng an toàn cư dân | Luôn validate với schema, hỏi tiếp field còn thiếu, bắt buộc user xác nhận draft trước khi create |
| 3 | Bot dựng trip plan khi chưa đủ constraint như ngày đi, số người, ngân sách hay sở thích | Itinerary không thực tế, tốn nhiều vòng sửa, user mất niềm tin vào planner | Dùng `get_trip_requirements_helper` để chặn trường hợp thiếu constraint tối thiểu, reset context khi có revision, có `trip_step_count` guard tránh loop quá dài |

---

## 5. ROI 3 kịch bản

|   | Conservative | Realistic | Optimistic |
|---|-------------|-----------|------------|
| **Assumption** | 300 user/ngày, 50% FAQ được xử lý xong, 60% ticket đủ field sau 2 lượt, 30 trip requests/ngày | 1.000 user/ngày, 65% FAQ được xử lý xong, 80% ticket đủ field sau 2 lượt, 120 trip requests/ngày | 3.000 user/ngày, 75% FAQ được xử lý xong, 90% ticket đủ field sau 2 lượt, 400 trip requests/ngày |
| **Cost** | ~180.000 VND/ngày inference + vận hành KB/mock tools | ~600.000 VND/ngày inference + monitoring + ticket store | ~1.800.000 VND/ngày inference + observability + tối ưu planner loop |
| **Benefit** | Giảm 3-5 giờ support/ngày, giảm câu hỏi lặp lại và chuẩn hóa intake ticket | Giảm 12-18 giờ support/ngày, ticket vào đúng bộ phận nhanh hơn, trip planner tăng tương tác và giữ user trong hệ sinh thái | Giảm 35-45 giờ support/ngày, tăng hài lòng cư dân, mở cơ hội cross-sell dịch vụ/điểm đến trong Ocean Park |
| **Net** | Có ích nếu triển khai pilot nhỏ, dùng dữ liệu FAQ và ticket mock sẵn có | ROI tốt nếu giảm được khối lượng FAQ/ticket thủ công ở ca cao điểm | Rất tốt nếu mở rộng cho nhiều khu và biến trip planner thành entry point giữ chân người dùng |

**Kill criteria:** Dừng hoặc pivot nếu sau 2 tháng pilot CSAT <3.5/5, intent accuracy <75%, ticket confirmation acceptance <60%, avg. trip loop >6 bước, hoặc xuất hiện lỗi nghiêm trọng về FAQ chính sách/ticket khẩn cấp mà mitigation không xử lý được.

---

## 6. Mini AI spec (1 trang)

Sản phẩm là chatbot AI cho hệ sinh thái nhu cầu thường gặp quanh Vinhomes, với 3 intent chính: `faq_policy`, `ticket_issue`, và `trip_plan`. Người dùng có thể hỏi FAQ/chính sách nội bộ, báo sự cố để tạo ticket, hoặc xin gợi ý kế hoạch đi chơi tại Vinhomes Ocean Park. Điểm pain hiện tại là user phải tự phân biệt nên hỏi ở đâu, phải cung cấp lại thông tin nhiều lần, còn đội vận hành phải tiếp nhận nhiều yêu cầu lặp lại nhưng chất lượng đầu vào không đồng đều.

AI hoạt động theo hướng augmentation, không thay thế hoàn toàn ban quản lý hay nhân viên hỗ trợ. Ở bước đầu tiên, hệ thống route intent để đưa user vào đúng flow. Với FAQ, bot trích xuất câu hỏi và kiểm tra đã đủ thông tin chưa; nếu thiếu thì hỏi làm rõ, nếu đủ thì mới quyết định có cần tra cứu KB hay không. Với ticket, bot trích xuất các field hiện có, dùng schema và validation để xác định thiếu gì, hỏi tiếp đúng trường cần bổ sung, tạo bản tóm tắt rồi chỉ tạo ticket khi user xác nhận. Với trip planner, bot cập nhật dần constraint, để agent quyết định nên hỏi thêm, gọi helper/context hay build itinerary, sau đó lặp cho tới khi ra được kế hoạch hợp lý.

Chất lượng nên tối ưu precision hơn recall ở các quyết định quan trọng. FAQ về phí, chính sách, nội quy phải grounded vào dữ liệu nội bộ khi cần; ticket chỉ được tạo sau khi đủ field và có xác nhận; trip plan không được build nếu còn thiếu constraint tối thiểu. Mục tiêu pilot là intent accuracy >=85%, FAQ grounded answer rate >=95%, ticket confirmation acceptance >=80%, trip first-plan acceptance >=60%, avg. trip loop <=4 và CSAT >=4/5.

Risk chính gồm trả lời FAQ từ dữ liệu cũ hoặc web fallback, phân loại sai ticket khẩn cấp, bot planner tự suy diễn khi thiếu constraint, và xử lý PII chưa chặt. Mitigation gồm tách rõ bước hỏi làm rõ và bước gọi tool, dùng validation/schema cho ticket, giới hạn planner bằng tool registry cố định, lưu correction log theo từng intent, lưu session/feedback để trace lại lỗi, và tiến tới masking dữ liệu nhạy cảm trong log/analytics.

Data flywheel đến từ những lần user sửa câu trả lời FAQ, sửa ticket draft, đổi constraint trip, feedback `like/dislike`, trace/metrics cho từng lượt chat, và những request phải clarify nhiều lần. Các tín hiệu này giúp cải thiện router, prompt extract, rule validate và thứ tự hỏi trong planner loop. Giá trị dữ liệu tăng dần theo thời gian vì nó phản ánh đúng workflow nội bộ và hành vi người dùng thực tế, không phải kiến thức chung mà model nền đã biết sẵn.

## Phân công
- 2A202600081 - Hồ Trọng Duy Quang: Canvas + failure modes
- 2A202600080 - Hồ Trần Đình Nguyên: User stories 4 paths, Prototype research
- 2A202600057 - Hồ Đắc Toàn: Eval metrics + ROI, prompt test

---