# Nhiệm vụ: Map văn bản tham chiếu từ thuvienphapluat.vn (TVPL) sang nguồn chính thức vbpl.vn (VBPL)

## Bối cảnh

Eval set (256 câu hỏi luật ngân hàng/thanh toán, đã lọc tay còn 251) dùng `reference` là URL trỏ tới **thuvienphapluat.vn** (nguồn tổng hợp tư nhân) — cần map sang **vbpl.vn** (Cơ sở dữ liệu Quốc gia Văn bản quy phạm pháp luật, nguồn chính thức của Bộ Tư pháp) để dùng làm nguồn trích dẫn/ingest chính thức cho hệ thống.

Đã trích sẵn **48 văn bản duy nhất** cần map, mỗi văn bản đã được parse ra `law_type` (loại văn bản) và `law_label` (số hiệu dạng "39/2014/TT-NHNN" — 37/48 văn bản có, 11/48 không có vì là Luật/Bộ luật không có số hiệu chuẩn trong slug URL, ví dụ "Bo-Luat-lao-dong-2019").

## File đính kèm (đã chuẩn bị sẵn, dùng làm điểm bắt đầu)

1. `unique_docs_to_map.json` — danh sách 48 văn bản cần map, mỗi phần tử có `doc_base_url` (TVPL), `law_type`, `law_label`, `parse_status`.
2. `map_tvpl_to_vbpl.py` — script khung đã viết sẵn logic map, **NHƯNG CHƯA CHẠY THỬ TRÊN DỮ LIỆU THẬT** (môi trường viết script không có mạng tới huggingface.co để test). Cần bạn debug/chỉnh sửa khi chạy thật, không coi đây là code đã verify.

## Cách tiếp cận — 2 phương án, thử theo thứ tự

### Phương án A (ưu tiên): dataset công khai `tmquan/vbpl-vn` trên HuggingFace

- 158.822 văn bản, license CC-BY-4.0, không gated.
- Trường quan trọng: `doc_number` (list số hiệu chuẩn hóa), `source_url` (link vbpl.vn), `item_id`, `doc_type`, `legal_type`.
- Cài: `pip install datasets huggingface_hub`
- Chạy thử: `python map_tvpl_to_vbpl.py unique_docs_to_map.json vbpl_mapping.jsonl`
- **Kiểm tra trước khi tin dùng**: dataset card mô tả field theo lời một model tóm tắt (tôi đọc qua WebFetch, không phải đọc trực tiếp schema/code), có thể sai lệch nhỏ về tên field hoặc kiểu dữ liệu thực tế — bước đầu tiên nên là load 1 vài dòng đầu, in ra `print(ds[0])` để xác nhận đúng cấu trúc trước khi chạy full script.

### Phương án B (dự phòng, nếu A không tải được hoặc dataset chất lượng kém)

- Tìm trực tiếp qua trang tìm kiếm chính thức: `https://vbpl.vn/Pages/vbpq-timkiem.aspx` — tra theo số hiệu.
- Hoặc dùng Google với cú pháp `site:vbpl.vn "<số hiệu>"` — đã kiểm chứng thủ công 1 trường hợp thật và ra đúng kết quả: tra `site:vbpl.vn "39/2014/TT-NHNN"` → `https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=44361`, khớp đúng Thông tư 39/2014/TT-NHNN.
- Cách này chậm hơn (không tự động hóa hàng loạt dễ dàng) nhưng đáng tin vì đã test thật.

## Yêu cầu cụ thể

1. **Verify trước khi tin số liệu**: chạy thử script/phương án, nhưng đừng báo cáo kết quả cuối cùng nếu chưa tự kiểm tra tay ít nhất 5-10 case (nhất là các case `match_method = name_year_fuzzy` — script hiện chỉ so khớp mờ theo trùng từ khóa, ngưỡng đang đặt tạm là "≥2 từ trùng", rất có thể cho kết quả sai, cần bạn tự đọc và xác nhận từng case này bằng mắt, không tự tin theo output script).
2. **Không tự bịa URL nếu không chắc** — nếu không tìm được match đáng tin cậy cho 1 văn bản, để `matched: false`, đừng đoán bừa 1 URL "trông có vẻ đúng".
3. **Xử lý riêng 11 văn bản không có `law_label`** (Luật/Bộ luật) — các văn bản này quan trọng (Bộ luật Dân sự, Bộ luật Hình sự, Luật Các TCTD, Luật NHNN Việt Nam...) nên đáng để tra tay từng cái nếu script không match được tự động, không nên bỏ qua.
4. **Đối chiếu ngữ nghĩa, không chỉ so khớp chuỗi** — với mỗi match (kể cả loại `doc_number_exact`), nên xác nhận nhanh tiêu đề văn bản ở vbpl.vn có thực sự khớp nội dung/loại văn bản với bên TVPL không (ví dụ tránh trường hợp trùng số hiệu nhưng khác cơ quan ban hành).
5. **Output cuối**: file `vbpl_mapping.jsonl` (48 dòng, đúng định dạng script đã định nghĩa) + báo cáo ngắn gồm: số match chính xác / match mờ (đã tự kiểm tra tay) / không match được, và liệt kê rõ danh sách các văn bản không match được để xử lý tay sau.

## Không cần làm ngay

- Chưa cần tích hợp `vbpl_mapping.jsonl` vào pipeline retrieval/KG chính — bước này chỉ là chuẩn bị dữ liệu, việc dùng nó để thay `reference` (TVPL) bằng `vbpl_source_url` trong eval set sẽ làm ở bước sau, sau khi bạn xác nhận chất lượng mapping đủ tin cậy.
