"""Bilingual response templates. Answers follow the language the user wrote in."""
import unicodedata

VIETNAMESE_MARKS = ("ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộ"
                    "ờớởỡợùúủũụừứửữựỳýỷỹỵ")
# Tokens that stay recognisably Vietnamese after diacritics are stripped. Short strings
# that also occur in English travel questions ("to", "in", "la", "co") are excluded.
VIETNAMESE_TOKENS = (
    "toi ", "minh ", "muon", "voi ", "gia dinh", "nguoi yeu", "ban be", "ban gai", "ban trai",
    "chuyen di", "du lich", "o dau", "bao nhieu", "uu tien", "tre nho", "tre em", "con nho",
    "khong", "duoc", "nhung", "cho toi", "tim tour", "dat tour", "xac nhan", "thich",
    "ngan sach", "lich trinh", "nguoi", "ngay", "dia phuong", "mot minh", "chill hon",
)


def _fold(text):
    text = unicodedata.normalize("NFD", str(text).lower().replace("đ", "d"))
    return "".join(c for c in text if not unicodedata.combining(c))


def detect_language(text):
    """Return 'vi', 'en', or None when the text carries no language signal.

    A reply like a bare phone number must not switch the conversation's language, so
    callers treat None as "keep whatever the user was already speaking".
    """
    lowered = str(text).lower()
    if any(ch in VIETNAMESE_MARKS for ch in lowered):
        return "vi"
    padded = " " + _fold(text) + " "
    if any(token in padded for token in VIETNAMESE_TOKENS):
        return "vi"
    return "en" if any(ch.isalpha() for ch in padded) else None


def money(amount, language="en"):
    formatted = f"{int(amount):,}"
    return formatted.replace(",", ".") if language == "vi" else formatted


INTEREST_LABELS = {
    "history": {"en": "history", "vi": "lịch sử"},
    "culture": {"en": "culture", "vi": "văn hóa"},
    "food": {"en": "food", "vi": "ẩm thực"},
    "nature": {"en": "nature", "vi": "thiên nhiên"},
    "beach": {"en": "beach", "vi": "biển"},
    "photography": {"en": "photography", "vi": "chụp ảnh"},
    "shopping": {"en": "shopping", "vi": "mua sắm"},
    "adventure": {"en": "adventure", "vi": "mạo hiểm"},
    "relaxation": {"en": "relaxation", "vi": "nghỉ dưỡng"},
    "nightlife": {"en": "nightlife", "vi": "về đêm"},
    "local_experience": {"en": "local experience", "vi": "trải nghiệm địa phương"},
}
PARTY_LABELS = {
    "family": {"en": "family trip", "vi": "chuyến đi gia đình"},
    "couple": {"en": "couple trip", "vi": "chuyến đi của hai người"},
    "friends": {"en": "trip with friends", "vi": "chuyến đi cùng bạn bè"},
    "solo": {"en": "solo trip", "vi": "chuyến đi một mình"},
}
PACE_LABELS = {
    "relaxed": {"en": "relaxed pace", "vi": "nhịp thư giãn"},
    "balanced": {"en": "balanced pace", "vi": "nhịp cân bằng"},
    "busy": {"en": "busy pace", "vi": "nhịp dày đặc"},
}
# Bare adjectives, for sentences that already supply the word "pace".
PACE_WORDS_ONLY = {
    "relaxed": {"en": "relaxed", "vi": "thư giãn"},
    "balanced": {"en": "balanced", "vi": "cân bằng"},
    "busy": {"en": "busy", "vi": "dày đặc"},
}
CONSTRAINT_LABELS = {
    "place": {"en": "destination", "vi": "điểm đến"},
    "max_price": {"en": "budget", "vi": "ngân sách"},
    "start_date": {"en": "start date", "vi": "ngày khởi hành"},
    "status": {"en": "tour status", "vi": "trạng thái tour"},
}

TEMPLATES = {
    "abstention": {
        "en": "No reliable information was found in the available heritage sources for this question.",
        "vi": "Mình không tìm thấy thông tin đáng tin cậy cho câu hỏi này trong các nguồn di sản hiện có."},
    "service_unavailable": {
        "en": "A travel service is unavailable. Please try again. No booking success is assumed.",
        "vi": "Một dịch vụ du lịch đang không phản hồi. Bạn thử lại giúp mình nhé. "
              "Chưa có đặt tour nào được ghi nhận."},
    "clarify": {
        "en": "Please clarify your travel request.",
        "vi": "Bạn có thể nói rõ hơn về chuyến đi mong muốn không?"},
    "out_of_domain": {
        "en": "I help with Vietnam travel, heritage, group itineraries and tour registrations. "
              "Please ask a travel question.",
        "vi": "Mình hỗ trợ du lịch Việt Nam, di sản, lịch trình nhóm và đăng ký tour. "
              "Bạn hỏi giúp mình một câu về chuyến đi nhé."},
    "need_destination": {
        "en": "Which destination should I use for your group?",
        "vi": "Bạn muốn nhóm mình đi đâu để mình tìm tour phù hợp?"},
    "prefs_noted_need_destination": {
        "en": "Noted: {prefs}. Which destination should I search?",
        "vi": "Mình đã ghi nhận: {prefs}. Bạn muốn đi đâu để mình tìm tour?"},
    "refined": {
        "en": "Updated your trip profile: {prefs}. Your destination and budget are unchanged; "
              "here are the same tours re-ranked:",
        "vi": "Mình đã cập nhật hồ sơ chuyến đi: {prefs}. Điểm đến và ngân sách giữ nguyên; "
              "danh sách được sắp xếp lại:"},
    "select_tour_first": {
        "en": "Please select a tour from the results first.",
        "vi": "Bạn chọn giúp mình một tour trong danh sách kết quả trước nhé."},
    "tour_gone": {
        "en": "This tour is no longer available.",
        "vi": "Tour này hiện không còn khả dụng."},
    "itinerary_needs_day": {
        "en": "Choose a day in the current itinerary and the number of activities to keep.",
        "vi": "Bạn chọn giúp mình ngày trong lịch trình hiện tại và số hoạt động muốn giữ lại."},
    "itinerary_updated": {
        "en": "Day {day} now has {count} activities. Other days are unchanged.",
        "vi": "Ngày {day} còn {count} hoạt động. Các ngày khác giữ nguyên."},
    "need_phone": {
        "en": "Please provide the phone number used for registration.",
        "vi": "Bạn cho mình số điện thoại đã dùng để đăng ký nhé."},
    "no_registrations": {
        "en": "No registrations found.",
        "vi": "Không tìm thấy đăng ký nào."},
    "zero_results_head": {
        "en": "No tour matches every constraint you gave. I kept all of them: {kept}.",
        "vi": "Chưa có tour nào thỏa mãn toàn bộ điều kiện bạn đưa ra. Mình vẫn giữ nguyên: {kept}."},
    "zero_results_blocking": {
        "en": "The constraint that rules everything out is the {blocking}.",
        "vi": "Điều kiện khiến không còn lựa chọn nào là {blocking}."},
    "zero_results_blocking_many": {
        "en": "No single constraint explains it; the combination of {blocking} leaves nothing.",
        "vi": "Không phải do một điều kiện riêng lẻ; kết hợp của {blocking} khiến không còn lựa chọn."},
    "zero_results_closest": {
        "en": "Closest options I can see, and the tradeoff each one needs:",
        "vi": "Những lựa chọn gần nhất mình thấy, kèm điểm phải đánh đổi:"},
    "zero_results_none": {
        "en": "I could not find a nearby option under these constraints either.",
        "vi": "Mình cũng chưa tìm được lựa chọn nào gần với các điều kiện này."},
    "zero_results_no_relax": {
        "en": "I will not change your budget, dates or destination on my own.",
        "vi": "Mình sẽ không tự ý thay đổi ngân sách, ngày đi hay điểm đến của bạn."},
    "ask_relax_budget": {
        "en": "Would you like to raise the budget to {amount} VND/person, or keep it and try "
              "another destination?",
        "vi": "Bạn muốn nâng ngân sách lên {amount} VND/người, hay giữ nguyên và đổi điểm đến?"},
    "ask_relax_date": {
        "en": "Would you like to accept a departure on {date}, or keep your date and change "
              "destination?",
        "vi": "Bạn muốn nhận chuyến khởi hành ngày {date}, hay giữ ngày và đổi điểm đến?"},
    "ask_relax_place": {
        "en": "Which other destination should I try, or should I widen the search?",
        "vi": "Bạn muốn mình thử điểm đến nào khác, hay mở rộng phạm vi tìm kiếm?"},
    "ask_relax_status": {
        "en": "Should I also show tours in another status?",
        "vi": "Mình có nên hiển thị cả tour ở trạng thái khác không?"},
    "ask_relax_generic": {
        "en": "Which one of these constraints may I relax?",
        "vi": "Mình được nới điều kiện nào trong số này?"},
    "tradeoff_price": {
        "en": "{amount} VND/person over your budget",
        "vi": "cao hơn ngân sách {amount} VND/người"},
    "tradeoff_date": {
        "en": "departs on {date}, before your date",
        "vi": "khởi hành ngày {date}, sớm hơn ngày bạn chọn"},
    "tradeoff_place": {
        "en": "in {place}, not {wanted}",
        "vi": "ở {place}, không phải {wanted}"},
    "tradeoff_status": {
        "en": "status is {status}",
        "vi": "trạng thái là {status}"},
    "booking_none_pending": {
        "en": "No complete booking is awaiting confirmation. Select a tour and provide your "
              "phone number first.",
        "vi": "Không có đơn đặt tour nào hoàn chỉnh đang chờ xác nhận. Bạn chọn tour và cho "
              "mình số điện thoại trước nhé."},
    "booking_expired": {
        "en": "Confirmation expired. Please request the booking again.",
        "vi": "Xác nhận đã hết hiệu lực. Bạn vui lòng yêu cầu đặt tour lại."},
    "booking_confirmed": {
        "en": "Tour registration confirmed.",
        "vi": "Đã xác nhận đăng ký tour."},
    "booking_duplicate": {
        "en": "This phone number is already registered for this tour.",
        "vi": "Số điện thoại này đã đăng ký tour này rồi."},
    "booking_changed": {
        "en": "Tour details changed. Request the booking again to review them.",
        "vi": "Thông tin tour đã thay đổi. Bạn yêu cầu đặt lại để xem lại chi tiết nhé."},
    "booking_unavailable": {
        "en": "This tour is not currently bookable.",
        "vi": "Tour này hiện chưa thể đặt."},
    "booking_missing": {
        "en": "This tour no longer exists.",
        "vi": "Tour này không còn tồn tại."},
    "booking_failed": {
        "en": "Booking could not be completed.",
        "vi": "Chưa hoàn tất được việc đặt tour."},
    "booking_pick_tour": {
        "en": "Select a specific tour to book, for example: Book the first tour.",
        "vi": "Bạn chọn một tour cụ thể để đặt nhé, ví dụ: đặt tour thứ nhất."},
    "booking_cancelled": {
        "en": "Pending booking cancelled.",
        "vi": "Đã hủy yêu cầu đặt tour đang chờ."},
    "booking_review": {
        "en": "Review booking: {title} ({tour_id}), {price} {unit}, {start} to {end} UTC+7, "
              "status: {status}.",
        "vi": "Xem lại thông tin đặt tour: {title} ({tour_id}), {price} {unit}, {start} đến "
              "{end} UTC+7, trạng thái: {status}."},
    "booking_ask_confirm": {
        "en": 'Phone ending {digits}. Reply "confirm booking" or use the confirmation button.',
        "vi": 'Số điện thoại kết thúc bằng {digits}. Bạn trả lời "xác nhận đặt tour" '
              "hoặc bấm nút xác nhận nhé."},
    "booking_ask_phone": {
        "en": "Please provide your phone number. Confirmation will be requested next.",
        "vi": "Bạn cho mình số điện thoại nhé. Sau đó mình sẽ xin xác nhận."},
    "ui_review_booking": {
        "en": "Review your booking", "vi": "Xem lại thông tin đặt tour"},
    "ui_select_tour": {"en": "Select a tour", "vi": "Chọn một tour"},
    "ui_only_target": {
        "en": "Only this exact target will be registered after confirmation.",
        "vi": "Chỉ đúng tour này sẽ được đăng ký sau khi bạn xác nhận."},
    "ui_need_phone_first": {
        "en": "Enter your phone number in the chat to enable confirmation.",
        "vi": "Bạn nhập số điện thoại trong khung chat để mở nút xác nhận nhé."},
    "ui_phone_on_file": {
        "en": "Confirming with the phone number ending {digits}.",
        "vi": "Sẽ xác nhận với số điện thoại kết thúc bằng {digits}."},
    "ui_confirm_booking": {"en": "Confirm booking", "vi": "Xác nhận đặt tour"},
    "ui_cancel_booking": {"en": "Cancel booking", "vi": "Hủy đặt tour"},
    "per_person": {"en": "VND/person", "vi": "VND/người"},
    "why_prefix": {"en": "matches", "vi": "phù hợp"},
    "budget_fit": {"en": "within budget", "vi": "trong ngân sách"},
    "evidence_heading": {"en": "Evidence", "vi": "Trích dẫn"},
    "sources_heading": {"en": "Sources", "vi": "Nguồn"},
    "heritage_heading": {"en": "Heritage evidence", "vi": "Bằng chứng di sản"},
    "plan_intro": {
        "en": "Proposed plan for {people} people, {days} days in {place}. Pace: {pace}. "
              "Tour subtotal: {cost} {unit}; {total} VND/group.",
        "vi": "Kế hoạch đề xuất cho {people} người, {days} ngày ở {place}. Nhịp: {pace}. "
              "Tạm tính tiền tour: {cost} {unit}; {total} VND/nhóm."},
    "plan_disclaimer": {
        "en": "Meals, transport and unverified tickets are not included. Times are suggestions; "
              "check actual tour dates and duration before booking.",
        "vi": "Chưa bao gồm ăn uống, di chuyển và vé chưa được xác minh. Giờ giấc chỉ là gợi ý; "
              "vui lòng kiểm tra ngày và thời lượng tour thực tế trước khi đặt."},
}


def t(key, language="en", **kwargs):
    entry = TEMPLATES[key]
    text = entry.get(language) or entry["en"]
    return text.format(**kwargs) if kwargs else text


def label(mapping, value, language="en"):
    entry = mapping.get(value)
    if not entry:
        return str(value).replace("_", " ")
    return entry.get(language) or entry["en"]


def preference_summary(profile, language="en"):
    """Describe only preferences actually recorded; never invent a party, interest or pace."""
    parts = []
    if profile.get("travel_party"):
        parts.append(label(PARTY_LABELS, profile["travel_party"], language))
    interests = profile.get("interests") or []
    if interests:
        parts.append(", ".join(label(INTEREST_LABELS, i, language) for i in interests))
    if profile.get("pace"):
        parts.append(label(PACE_LABELS, profile["pace"], language))
    return "; ".join(parts)
