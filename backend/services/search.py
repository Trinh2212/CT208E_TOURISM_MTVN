"""
Tầng nghiệp vụ Tìm kiếm Đa phương thức (Multimodal Search Service):
- Khởi tạo lười (Lazy Singleton) các mô hình VnCoreNLP, PhoBERT, ViT và chỉ mục FAISS.
- Hỗ trợ 3 chế độ truy vấn:
  1. Chỉ Văn bản (text): PhoBERT trên Kho 1 (268 đoạn mô tả description_parts).
  2. Chỉ Hình ảnh (image): ViT trên Kho 2 (866 vector ảnh).
  3. Đa phương thức (multimodal): Pair-level Late Fusion (0.5 - 0.5) kèm chuẩn hóa Min-Max
     trên 866 cặp ảnh - chú thích ở Kho 2.
- Gom điểm theo place_id bằng toán tử MAX, kết hợp bộ lọc hành chính / loại hình du lịch
  từ MongoDB qua TourismService và trả về Top-K địa điểm kèm matched_evidence.
"""

from io import BytesIO
import json
import os
from pathlib import Path
from threading import Lock
import unicodedata
import warnings

from PIL import Image, UnidentifiedImageError
from werkzeug.exceptions import BadRequest, NotFound

from backend.config import Settings
from backend.services.tourism import PLACE_FIELDS, TourismService, image_url

MAX_IMAGE_SIZE = 10 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}
PHOBERT_MODEL_NAME = "vinai/phobert-base"
VIT_MODEL_NAME = "google/vit-base-patch16-224"
EPSILON = 1e-8
DEFAULT_TOP_K = 3

_ENGINE_LOCK = Lock()
_SHARED_SEGMENTER = None
_SHARED_SEGMENTER_DIR = None
_SEGMENT_CALL_LOCK = Lock()


def preprocess_text(text: str) -> str:
    """Chuẩn hóa bảng mã Unicode dựng sẵn (NFC) và loại bỏ khoảng trắng thừa."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFC", str(text))
    return " ".join(normalized.strip().split())


def min_max_normalize(scores, eps: float = EPSILON):
    """Chuẩn hóa Min-Max mảng điểm Cosine về đoạn [0, 1] với epsilon = 1e-8."""
    import numpy as np

    s_min = float(np.min(scores))
    s_max = float(np.max(scores))
    return (scores - s_min) / (s_max - s_min + eps)


def aggregate_and_rank(scores, mapping: list, *, allowed_place_ids=None, top_k: int = DEFAULT_TOP_K) -> list:
    """
    Gom điểm theo place_id bằng toán tử MAX (giữ lại best_evidence),
    lọc theo allowed_place_ids (nếu có) và xếp hạng lấy Top-K địa điểm.
    """
    best_per_place = {}
    for idx, sc in enumerate(scores):
        score_val = float(sc)
        item_meta = mapping[idx]
        pid = item_meta["place_id"]
        if allowed_place_ids is not None and pid not in allowed_place_ids:
            continue
        if pid not in best_per_place or score_val > best_per_place[pid]["score"]:
            best_per_place[pid] = {
                "place_id": pid,
                "place_name": item_meta.get("place_name", ""),
                "score": score_val,
                "best_evidence": item_meta,
            }

    ranked = sorted(best_per_place.values(), key=lambda x: x["score"], reverse=True)
    if top_k is not None:
        ranked = ranked[:top_k]
    for r_idx, entry in enumerate(ranked, start=1):
        entry["rank"] = r_idx
    return ranked


def load_query_image(file_storage) -> Image.Image:
    """
    Kiểm tra bảo mật và giải mã file ảnh truy vấn từ multipart/form-data:
    - Dung lượng > 0 và <= 10 MB.
    - Định dạng thực tế phải thuộc JPEG, PNG, WEBP, GIF.
    - Chuyển kênh màu sang RGB.
    Ném BadRequest (HTTP 400) nếu ảnh không hợp lệ.
    """
    if file_storage is None or not getattr(file_storage, "filename", ""):
        raise BadRequest("Vui lòng chọn một ảnh hợp lệ.")

    stream = getattr(file_storage, "stream", file_storage)
    try:
        stream.seek(0)
    except (AttributeError, OSError):
        pass

    raw_bytes = stream.read(MAX_IMAGE_SIZE + 1)
    if not raw_bytes:
        raise BadRequest("Tệp ảnh đang trống. Hãy chọn ảnh khác.")
    if len(raw_bytes) > MAX_IMAGE_SIZE:
        raise BadRequest("Ảnh quá lớn. Vui lòng chọn ảnh tối đa 10 MB.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw_bytes)) as img:
                fmt = (img.format or "").upper()
                if fmt not in ALLOWED_IMAGE_FORMATS:
                    raise BadRequest("Hãy chọn ảnh JPG, PNG, WebP hoặc GIF hợp lệ.")
                rgb_image = img.convert("RGB")
                rgb_image.load()
                return rgb_image
    except BadRequest:
        raise
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        OSError,
        SyntaxError,
        ValueError,
    ):
        raise BadRequest("Không đọc được nội dung ảnh. Hãy chọn một tệp ảnh hợp lệ.") from None


def _get_or_init_segmenter(vncorenlp_dir: Path):
    """Khởi tạo VnCoreNLP duy nhất một lần trong tiến trình JVM và bảo toàn cwd."""
    global _SHARED_SEGMENTER, _SHARED_SEGMENTER_DIR
    resolved_dir = vncorenlp_dir.resolve()
    if not (resolved_dir / "VnCoreNLP-1.2.jar").is_file():
        raise RuntimeError(f"Không tìm thấy VnCoreNLP-1.2.jar tại {resolved_dir}")

    if _SHARED_SEGMENTER is None:
        import py_vncorenlp

        cwd = os.getcwd()
        try:
            _SHARED_SEGMENTER = py_vncorenlp.VnCoreNLP(
                save_dir=str(resolved_dir),
                annotators=["wseg"],
            )
            _SHARED_SEGMENTER_DIR = resolved_dir
        finally:
            os.chdir(cwd)
    return _SHARED_SEGMENTER


def _format_matched_evidence(mode: str, evidence: dict) -> dict:
    """Chuyển đổi best_evidence nội bộ sang matched_evidence chuẩn cho API response."""
    if mode == "text":
        return {
            "type": "text",
            "desc_id": evidence["desc_id"],
            "snippet": evidence["text_snippet"],
        }
    image_id = evidence["image_id"]
    image_obj = {
        "id": image_id,
        "url": image_url(image_id),
    }
    if mode == "image":
        return {
            "type": "image",
            "image": image_obj,
        }
    return {
        "type": "multimodal",
        "image": image_obj,
        "snippet": evidence["caption_snippet"],
    }


class SearchService:
    """
    Dịch vụ tìm kiếm đa phương thức theo cơ chế Lazy Singleton.
    Chỉ nạp VnCoreNLP, PhoBERT, ViT và 3 FAISS index khi có truy vấn đầu tiên.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._lock = Lock()
        self._loaded = False
        self._device = None
        self._rdrsegmenter = None
        self._phobert_tokenizer = None
        self._phobert_model = None
        self._vit_processor = None
        self._vit_model = None
        self._index_desc_phobert = None
        self._index_img_vit = None
        self._index_cap_phobert = None
        self._desc_mapping = None
        self._pair_mapping = None

    def _ensure_loaded(self):
        """Nạp một lần duy nhất các mô hình và chỉ mục FAISS vào bộ nhớ (thread-safe)."""
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            with _ENGINE_LOCK:
                import faiss
                import torch
                from transformers import AutoModel, AutoTokenizer, ViTImageProcessor, ViTModel

                store_dir = self.settings.faiss_store_dir.resolve()
                desc_index_path = store_dir / "desc_phobert.index"
                img_index_path = store_dir / "img_vit.index"
                cap_index_path = store_dir / "cap_phobert.index"
                desc_map_path = store_dir / "desc_mapping.json"
                pair_map_path = store_dir / "pair_mapping.json"

                for path in (desc_index_path, img_index_path, cap_index_path, desc_map_path, pair_map_path):
                    if not path.is_file():
                        raise RuntimeError(f"Thiếu tệp chỉ mục/ánh xạ FAISS: {path.name}")

                desc_mapping = json.loads(desc_map_path.read_text(encoding="utf-8"))
                pair_mapping = json.loads(pair_map_path.read_text(encoding="utf-8"))

                index_desc = faiss.read_index(str(desc_index_path))
                index_img = faiss.read_index(str(img_index_path))
                index_cap = faiss.read_index(str(cap_index_path))

                if index_desc.ntotal != len(desc_mapping):
                    raise RuntimeError("Kích thước desc_phobert.index không khớp desc_mapping.json")
                if index_img.ntotal != len(pair_mapping) or index_cap.ntotal != len(pair_mapping):
                    raise RuntimeError("Kích thước img_vit.index / cap_phobert.index không khớp pair_mapping.json")

                segmenter = _get_or_init_segmenter(self.settings.vncorenlp_dir)

                device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                phobert_tokenizer = AutoTokenizer.from_pretrained(PHOBERT_MODEL_NAME)
                phobert_model = AutoModel.from_pretrained(PHOBERT_MODEL_NAME).to(device)
                phobert_model.eval()

                vit_processor = ViTImageProcessor.from_pretrained(VIT_MODEL_NAME)
                vit_model = ViTModel.from_pretrained(VIT_MODEL_NAME).to(device)
                vit_model.eval()

                self._device = device
                self._rdrsegmenter = segmenter
                self._phobert_tokenizer = phobert_tokenizer
                self._phobert_model = phobert_model
                self._vit_processor = vit_processor
                self._vit_model = vit_model
                self._index_desc_phobert = index_desc
                self._index_img_vit = index_img
                self._index_cap_phobert = index_cap
                self._desc_mapping = desc_mapping
                self._pair_mapping = pair_mapping
                self._loaded = True

    def segment_vietnamese(self, text: str) -> str:
        """Chuẩn hóa NFC, tách từ bằng VnCoreNLP (thread-safe) và nối thành 1 chuỗi duy nhất."""
        clean_text = preprocess_text(text)
        if not clean_text:
            return ""
        self._ensure_loaded()
        with _SEGMENT_CALL_LOCK:
            sentences = self._rdrsegmenter.word_segment(clean_text)
        return " ".join(sentences)

    def encode_query_text(self, query_text: str):
        """Tách từ tiếng Việt, mã hóa bằng PhoBERT (Mean Pooling + L2) -> (1, 768) float32."""
        import numpy as np
        import torch
        import torch.nn.functional as F

        self._ensure_loaded()
        seg_text = self.segment_vietnamese(query_text)
        if not seg_text:
            raise BadRequest("Vui lòng nhập nội dung văn bản hợp lệ để tìm kiếm.")

        with torch.no_grad():
            encoded = self._phobert_tokenizer(
                [seg_text],
                max_length=256,
                padding=True,
                truncation=True,
                return_tensors="pt",
            ).to(self._device)
            outputs = self._phobert_model(**encoded)
            last_hidden = outputs.last_hidden_state
            mask = encoded["attention_mask"].unsqueeze(-1).expand(last_hidden.size()).float()
            sum_vecs = torch.sum(last_hidden * mask, dim=1)
            sum_mask = torch.clamp(mask.sum(dim=1), min=1e-9)
            mean_vec = sum_vecs / sum_mask
            l2_vec = F.normalize(mean_vec, p=2, dim=1)
            return np.ascontiguousarray(l2_vec.cpu().numpy(), dtype=np.float32)

    def encode_query_image(self, rgb_image: Image.Image):
        """Mã hóa ảnh RGB bằng ViT ([CLS] + L2) -> (1, 768) float32."""
        import numpy as np
        import torch
        import torch.nn.functional as F

        self._ensure_loaded()
        rgb = rgb_image.convert("RGB")
        with torch.no_grad():
            inputs = self._vit_processor(images=[rgb], return_tensors="pt").to(self._device)
            outputs = self._vit_model(**inputs)
            cls_vec = outputs.last_hidden_state[:, 0, :]
            l2_vec = F.normalize(cls_vec, p=2, dim=1)
            return np.ascontiguousarray(l2_vec.cpu().numpy(), dtype=np.float32)

    def _allowed_place_ids(self, database, catalogs, province_id=None, tourism_type_id=None):
        """Lấy tập hợp các place_id thỏa mãn bộ lọc province_id và tourism_type_id từ MongoDB."""
        if province_id is None and tourism_type_id is None:
            return None
        provinces, types, _ = catalogs
        query = {}
        if province_id is not None:
            province = provinces.get(province_id)
            if province is None:
                raise NotFound("Không tìm thấy tỉnh/thành.")
            query["province_former_id"] = (
                {"$in": province["former_province_ids"]} if province["scheme"] == "current" else province_id
            )
        if tourism_type_id is not None:
            if tourism_type_id not in types:
                raise NotFound("Không tìm thấy loại hình du lịch.")
            query["tourism_type_ids"] = tourism_type_id
        return {doc["_id"] for doc in database.places.find(query, {"_id": 1})}

    def search(
        self,
        database,
        *,
        query_text: str = "",
        query_image: Image.Image | None = None,
        province_id: str | None = None,
        tourism_type_id: str | None = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> dict:
        """
        Thực thi tìm kiếm đa phương thức trên FAISS, kết hợp lọc từ MongoDB
        và chuẩn hóa kết quả qua TourismService.
        """
        import numpy as np

        clean_text = preprocess_text(query_text) if query_text else ""
        has_text = bool(clean_text)
        has_image = query_image is not None

        if not has_text and not has_image:
            raise BadRequest("Vui lòng nhập mô tả hoặc chọn một ảnh để tìm kiếm.")

        tourism_service = TourismService(database)
        catalogs = tourism_service._catalogs()
        allowed_ids = self._allowed_place_ids(
            database,
            catalogs,
            province_id=province_id,
            tourism_type_id=tourism_type_id,
        )

        self._ensure_loaded()

        if has_image and has_text:
            mode = "multimodal"
            n = len(self._pair_mapping)
            q_img = self.encode_query_image(query_image)
            d_img, i_img = self._index_img_vit.search(q_img, n)
            s_img = np.empty(n, dtype=np.float32)
            s_img[i_img[0]] = d_img[0]

            q_txt = self.encode_query_text(clean_text)
            d_cap, i_cap = self._index_cap_phobert.search(q_txt, n)
            s_cap = np.empty(n, dtype=np.float32)
            s_cap[i_cap[0]] = d_cap[0]

            s_img_norm = min_max_normalize(s_img)
            s_cap_norm = min_max_normalize(s_cap)
            scores = 0.5 * s_img_norm + 0.5 * s_cap_norm
            mapping = self._pair_mapping
        elif has_image:
            mode = "image"
            n = len(self._pair_mapping)
            q_img = self.encode_query_image(query_image)
            d_img, i_img = self._index_img_vit.search(q_img, n)
            scores = np.empty(n, dtype=np.float32)
            scores[i_img[0]] = d_img[0]
            mapping = self._pair_mapping
        else:
            mode = "text"
            n = len(self._desc_mapping)
            q_txt = self.encode_query_text(clean_text)
            d_desc, i_desc = self._index_desc_phobert.search(q_txt, n)
            scores = np.empty(n, dtype=np.float32)
            scores[i_desc[0]] = d_desc[0]
            mapping = self._desc_mapping

        ranked_places = aggregate_and_rank(
            scores,
            mapping,
            allowed_place_ids=allowed_ids,
            top_k=top_k,
        )

        if not ranked_places:
            return {
                "mode": mode,
                "top_k": top_k,
                "total": 0,
                "items": [],
            }

        place_ids = [item["place_id"] for item in ranked_places]
        docs = list(database.places.find({"_id": {"$in": place_ids}}, PLACE_FIELDS))
        place_map = {doc["_id"]: tourism_service._place_item(doc, catalogs) for doc in docs}

        items = []
        for ranked_item in ranked_places:
            pid = ranked_item["place_id"]
            if pid not in place_map:
                continue
            item = dict(place_map[pid])
            item["rank"] = len(items) + 1
            item["score"] = round(float(ranked_item["score"]), 4)
            item["matched_evidence"] = _format_matched_evidence(mode, ranked_item["best_evidence"])
            items.append(item)

        return {
            "mode": mode,
            "top_k": top_k,
            "total": len(items),
            "items": items,
        }

