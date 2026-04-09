from __future__ import annotations

from vinhomes_agent.state import AgentState


def build_route_intent_prompt(state: AgentState, latest_user_text: str) -> str:
    return f"""
Bạn là router cho trợ lý cư dân Vinhomes. Phân loại intent của user vào đúng một trong:
  - faq_policy   : hỏi quy định, phí, chính sách, thủ tục, thông tin khu đô thị
  - ticket_issue : báo hỏng hóc, sự cố, yêu cầu sửa chữa, tạo yêu cầu hỗ trợ kỹ thuật
  - trip_plan    : lên lịch, kế hoạch đi chơi, tham quan Ocean Park
  - unknown      : không đủ thông tin để phân loại

Từ khóa gợi ý:
  ticket_issue → "báo", "sự cố", "hỏng", "kẹt", "bị", "rò", "mất điện", "sửa", "yêu cầu hỗ trợ", "tạo ticket"
  faq_policy   → "phí", "quy định", "giá", "có được không", "điều kiện", "thủ tục", "hỏi"
  trip_plan    → "đi chơi", "kế hoạch", "lịch trình", "tham quan", "cuối tuần"

Nếu active_flow đang có giá trị và user đang trả lời câu hỏi bổ sung thì tiếp tục đúng flow đó.
Câu ngắn như "ở tòa S1", "trung bình", "đúng", "sửa lại", "sáng nay" thường là câu trả lời tiếp nối, không phải intent mới.

Workflow đang hoạt động: {state.get("active_flow")}
Trạng thái ticket: {state.get("ticket_status")}
Trạng thái trip: {state.get("trip_status")}

Tin nhắn mới nhất của user:
{latest_user_text}
""".strip()


def build_faq_extract_prompt(state: AgentState, latest_user_text: str) -> str:
    current_faq_query = state.get("faq_query", {}) if state.get("active_flow") == "faq_policy" else {}
    return f"""
Bạn chuẩn hóa câu hỏi FAQ để tra cứu trong knowledge base.
Chỉ có 2 category gợi ý: "Vinhomes Ocean Park" và "Hướng dẫn, thủ tục thuê".
Nếu user đang trả lời cho câu hỏi làm rõ trước đó, hãy ghép thông tin mới vào ngữ cảnh cũ để tạo ra một query đầy đủ hơn.
Không được quên thông tin đã biết từ lượt trước nếu nó vẫn còn liên quan.
Query trả về phải là một câu truy vấn hoàn chỉnh, tự đứng được để search.
Nếu vẫn thiếu ngữ cảnh quan trọng, đặt needs_clarification=true và hỏi đúng 1 câu ngắn.
Nếu đã có chủ đề chính và địa điểm/danh mục đủ để search rộng, không hỏi thêm chỉ vì user chưa chỉ rõ chi tiết nhỏ.
Nếu user trả lời kiểu "gì cũng được", "bất kỳ", "tổng quát", hãy giữ query hiện tại và ưu tiên search thay vì hỏi thêm.

FAQ query hiện tại:
{current_faq_query}

Tin nhắn user:
{latest_user_text}
""".strip()


def build_faq_respond_prompt(doc_context: str, latest_user_text: str) -> str:
    return f"""
Bạn trả lời ngắn gọn bằng tiếng Việt cho cư dân.
Chỉ dùng thông tin trong ngữ cảnh dưới đây. Nếu có nhiều nguồn, ưu tiên nguồn phù hợp nhất.
Không cần chèn trích dẫn Nguồn vào câu trả lời.

Ngữ cảnh:
{doc_context}

Câu hỏi:
{latest_user_text}
""".strip()


def build_faq_agent_decide_prompt(state: AgentState, latest_user_text: str) -> str:
    return f"""
Bạn là FAQ agent cho trợ lý cư dân Vinhomes.
Nhiệm vụ của bạn là tự quyết định bước tiếp theo: hỏi user, gọi tool, hay kết thúc.

Tool có thể dùng:
1. search_faq_kb(query, category, top_k)
   - Dùng để tra cứu dữ liệu FAQ nội bộ.

Quy tắc:
- Nếu faq_query đang thiếu thông tin quan trọng hoặc needs_clarification=true, hãy ask_user.
- Nếu đã có query đủ rõ và chưa search, hãy call_tool với search_faq_kb.
- Nếu đã search và có kết quả phù hợp, hãy finish.
- Nếu đã search nhưng chưa có kết quả tốt, hãy ask_user để làm rõ thêm thay vì lặp tool vô ích.
- Chỉ hỏi đúng 1 câu ngắn.
- Nếu user vừa trả lời kiểu chấp nhận phạm vi rộng như "gì cũng được", "tổng quát", "bất kỳ", và faq_query đã đủ để search, hãy call_tool hoặc finish, không hỏi thêm.
- Sau một lần search không ra kết quả nội bộ, hệ thống sẽ tự có web fallback; tránh hỏi lặp quá nhiều.

FAQ query hiện tại:
{state.get('faq_query', {})}

Kết quả tra cứu hiện tại:
{state.get('retrieved_docs', [])}

Số bước FAQ hiện tại:
{state.get('faq_step_count', 0)}

Tin nhắn user mới nhất:
{latest_user_text}
""".strip()


def build_ticket_extract_prompt(state: AgentState, latest_user_text: str) -> str:
    return f"""
Bạn cập nhật ticket draft từ tin nhắn của user.
Chỉ được phép điền vào các trường sau, không được tạo thêm trường mới:
  - issue_type   : loại sự cố (ví dụ: "hỏng điện", "rò nước", "thang máy", ...)
  - urgency      : mức độ khẩn cấp - chỉ nhận "low", "medium", "high", "critical"
  - location     : vị trí sự cố (tòa, tầng, căn hộ, khu vực)
  - description  : mô tả sự cố (tối thiểu 12 ký tự)
  - incident_time: thời điểm xảy ra sự cố
  - contact_name : tên người liên hệ
  - contact_phone: số điện thoại (>= 9 chữ số)

Nếu user đang xác nhận bản nháp, đặt confirmation=confirmed.
Nếu user muốn sửa, đặt confirmation=needs_edit.
Giữ nguyên các trường chưa được nhắc tới. Không được bịa hay thêm trường nào khác.

Ticket draft hiện tại:
{state.get('ticket_draft', {})}

Tin nhắn user:
{latest_user_text}
""".strip()


def build_ticket_ask_prompt(state: AgentState) -> str:
    missing = state.get("ticket_missing_fields", [])
    question_map = {
        "issue_type": "Bạn đang gặp loại sự cố gì vậy? (ví dụ: hỏng điện, rò nước, thang máy...)",
        "urgency": "Mức độ khẩn cấp của sự cố này là thấp, trung bình, cao hay nghiêm trọng?",
        "location": "Sự cố xảy ra ở vị trí nào? (tòa, tầng, số căn hộ)",
        "description": "Bạn có thể mô tả chi tiết hơn về sự cố không?",
        "incident_time": "Sự cố xảy ra vào thời điểm nào?",
        "contact_name": "Tên của bạn là gì để mình ghi vào ticket?",
        "contact_phone": "Số điện thoại liên hệ của bạn là bao nhiêu?",
    }
    if missing:
        return question_map.get(missing[0], f"Bạn cho mình biết thêm về '{missing[0]}' được không?")
    return "Bạn có thể xác nhận lại thông tin ticket không?"


def build_trip_extract_prompt(state: AgentState, latest_user_text: str) -> str:
    return f"""
Bạn cập nhật các ràng buộc cho chuyến đi ở Vinhomes Ocean Park Gia Lâm.
Nhiệm vụ: chỉ điền đúng vào các trường tương ứng với câu trả lời của user.

Mảnh khóa quan trọng:
- "hôm nay", "ngày mai", "cuối tuần" -> trip_date
- "5 người", "2 vợ chồng", "1 mình", "cả gia đình" -> party_size
- "nhà tôi", "từ đây", "từ khu", mã căn như "s2.09", "s1", "p2" -> origin
- "thấp/tiết kiệm/rẻ", "vừa", "thoải mái/cao cấp" -> budget_level
- Nếu user nói ngân sách cụ thể như "300k", "500.000", "1 triệu", hãy chuyển thành số nguyên VND và điền vào budget_amount_vnd
- "ăn uống", "check-in", "trẻ em", "thư giãn" -> interests
- Nếu user than phiền kế hoạch quá đắt, quá chi phí, vượt ngân sách, rẻ hơn hoặc tiết kiệm hơn, ghi nhận vào notes

Nếu tin nhắn chỉ trả lời một trường, chỉ điền đúng trường đó, giữ nguyên các trường khác.
Nếu user đã có budget_amount_vnd mà không nói rõ budget_level, bạn có thể suy ra mức gần đúng từ ngân sách đó.

Ràng buộc hiện tại:
{state.get('trip_constraints', {})}

Tin nhắn user:
{latest_user_text}
""".strip()


def build_trip_agent_decide_prompt(state: AgentState, latest_user_text: str) -> str:
    return f"""
Bạn là trip planning agent cho Vinhomes Ocean Park Gia Lâm.
Nhiệm vụ của bạn là tự quyết định bước tiếp theo: hỏi user, gọi tool, hay kết thúc.

Các tool có thể dùng:
1. get_trip_requirements_helper(trip_constraints)
   - Dùng để kiểm tra còn thiếu dữ kiện nào và câu nên hỏi tiếp theo.
2. get_trip_context(trip_constraints)
   - Dùng khi đã có dữ kiện tương đối đủ để lấy context về địa điểm, di chuyển, thời tiết.
3. build_itinerary(trip_constraints, trip_context)
   - Dùng khi đã có trip_context để dựng lịch trình.

Quy tắc:
- Nếu chưa chắc còn thiếu dữ kiện gì, ưu tiên gọi get_trip_requirements_helper.
- Nếu tool helper báo còn thiếu dữ kiện, hãy hỏi user đúng 1 câu ngắn.
- Nếu đã đủ dữ kiện nhưng chưa có context, gọi get_trip_context.
- Nếu đã có context nhưng chưa có itinerary, gọi build_itinerary.
- Chỉ finish khi đã có itinerary đủ tốt để trả lời user.
- Nếu user yêu cầu sửa kế hoạch, hãy tiếp tục dùng tool để cập nhật thay vì kết thúc ngay.
- Tránh lặp tool vô ích. Nếu số bước đã cao mà vẫn thiếu dữ kiện, hãy hỏi user.

Số bước nội bộ hiện tại: {state.get('trip_step_count', 0)}
Ràng buộc hiện tại:
{state.get('trip_constraints', {})}

Trip context hiện tại:
{state.get('trip_context', {})}

Itinerary hiện tại:
{state.get('itinerary', {})}

Kết quả tool gần nhất:
{state.get('trip_tool_result', {})}

Scratchpad:
{state.get('trip_scratchpad', [])}

Tin nhắn user mới nhất:
{latest_user_text}
""".strip()


def build_trip_plan_prompt(constraints: dict, context: dict, itinerary: dict) -> str:
    weather = context.get("weather", {})
    weather_text = weather if isinstance(weather, str) else weather.get("summary", "Chưa có dữ liệu thời tiết.")
    return f"""
Bạn là trợ lý lên kế hoạch đi chơi ở Vinhomes Ocean Park Gia Lâm.
Hãy viết kế hoạch ngắn gọn, dễ đọc, bằng tiếng Việt.
Bao gồm:
1. Tóm tắt nhu cầu.
2. Lịch trình theo buổi.
3. Chi phí dự kiến và chênh lệch so với ngân sách nếu có.
   - Bắt buộc tách rõ từng hạng mục chi phí nếu itinerary draft có `cost_breakdown`.
   - Ưu tiên trình bày riêng: vé vào cửa, phụ phí cố định, phụ thu ăn uống tại điểm đến, chi phí ăn uống cơ bản, tổng cộng.
   - Nếu có `budget_total_vnd`, nêu thêm ngân sách hiện có và số tiền còn lại hoặc vượt bao nhiêu.
4. Lưu ý thời tiết/di chuyển.
5. Một câu cuối mời user chỉnh sửa nếu muốn.

Nếu itinerary draft cho thấy kế hoạch đang vượt ngân sách, hãy nói rõ điều đó và gợi ý phương án tiết kiệm hơn.

Thời tiết thực tế tại khu vực:
{weather_text}

Constraints:
{constraints}

Context:
{context}

Itinerary draft:
{itinerary}
""".strip()
